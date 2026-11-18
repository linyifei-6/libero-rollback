# Per-model environment locks

Each model runs in its **own isolated Python environment**. The benchmark
environment (static tools, matrices, evidence) and the simulation environment
(LIBERO + MuJoCo) are separate on purpose: three responsibilities, three
environments, never merged (README §8, SPEC §12).

```
repo `.venv`            static layer: stdlib + PyYAML + jsonschema (CPU)
repo `.venv-sim`        simulation: numpy / robosuite / mujoco / bddl / gym / torch
`.venvs/<model>/`       one environment per model family (inference only)
```

`configs/envs/<model>.lock` records **what was actually installed** so a
leaderboard entry can be reproduced months later. Locks are committed; they
must not contain host-absolute paths or checkpoint blobs. Model weights and
LIBERO assets are never committed (README §9.4).

## How a lock is generated

```bash
# 1. Make the simulation assets verifiable first (hard failure on mismatch).
export LIBERO_HOME=/path/to/LIBERO
export LIBERO_CONFIG_PATH="$PWD/.cache/libero"
uv run python scripts/bootstrap_libero.py --libero-home "$LIBERO_HOME" --out "$LIBERO_CONFIG_PATH"
uv run python scripts/verify_libero.py --libero-home "$LIBERO_HOME" --allow-dirty

# 2. Create the model environment (dry-run first: prints the exact commands).
bash scripts/setup_env.sh pi05 \
  --openpi-root /path/to/openpi \
  --checkpoint  /path/to/pi05_libero

# 3. Repeat with `--execute` once the plan looks right. This creates
#    .venvs/pi05/ and writes configs/envs/pi05.lock.
bash scripts/setup_env.sh pi05 --openpi-root /path/to/openpi \
  --checkpoint /path/to/pi05_libero --execute
```

`scripts/setup_env.sh` is plan-by-default: without `--execute` it only prints
the commands it would run (creating environments and downloading weights are
explicitly opt-in). It checks `LIBERO_HOME` so a lock never claims a LIBERO pin
that was not verified on the machine.

## Lock schema (v1)

```yaml
schema_version: 1
model: pi05
generated_by: scripts/setup_env.sh --execute
generated_at: "2026-11-18T00:00:00Z"      # UTC, ISO-8601
python_version: "3.11.x"                  # reported by the created interpreter
uv_version: "0.x.y"
adapter: libero_rollback.policies.pi05
libero_commit: f78abd68ee283de9f9be3c8f7e2a9ad60246e95c
checkpoint:
  env: PI05_CHECKPOINT
  name: pi05_libero                        # basename only, never a host path
  digest: null                             # sha256 of a checkpoint manifest, Phase 2
packages:                                  # sorted `uv pip freeze` lines
  - "numpy==1.26.4"
  - "..."
packages_sha256: null                      # sha256 of the packages list, Phase 2
notes: "optional, free text"
```

Rules:

1. **No absolute paths.** Record the environment-variable *name* and the
   checkpoint basename; the runner resolves the actual path at run time.
2. **No invented digests.** Leave `digest` / `packages_sha256` as `null` until
   a script computes them; never hand-write a hex string.
3. **One lock per model family.** `pi0` / `pi0_fast` share the OpenPI stack but
   keep separate locks because checkpoints and training configs differ.
4. A lock is evidence only for the environment it was generated on; the run’s
   `provenance.json` records the per-run resolution (interpreter path, ckpt
   sha, `pip freeze` digest, argv, environment variables).

## Current status (Phase 1)

| model | lock | status |
|---|---|---|
| `pi05` (OpenPI) | `configs/envs/pi05.lock` | ⬜ not generated — needs a GPU/model stack |
| `pi0`, `pi0_fast` (OpenPI) | `configs/envs/pi0.lock`, `pi0_fast.lock` | ⬜ not generated |
| `openvla_oft` (Py3.10 / torch 2.2.0) | `configs/envs/openvla_oft.lock` | ⬜ not generated |
| `smolvla` (LeRobot) | `configs/envs/smolvla.lock` | ⬜ not generated |

The registry itself (`configs/models.yaml`) is committed; the per-model stacks
are Phase 2 work (see `docs/implementation-status.md`). Do not claim a lock
exists until `scripts/setup_env.sh --execute` has actually produced it.

## Related environment variables

| variable | purpose |
|---|---|
| `LIBERO_HOME` | upstream LIBERO checkout (the directory containing the `libero` package) |
| `LIBERO_CONFIG_PATH` | repo-local LIBERO config dir (`.cache/libero`); never `~/.libero` |
| `MUJOCO_GL` | `egl` on GPU machines, `osmesa` on CPU/CI |
| `PI05_PYTHON` / `PI0_PYTHON` / `PI0_FAST_PYTHON` | interpreter inside the model env |
| `PI05_CHECKPOINT` / `PI0_CHECKPOINT` / `PI0_FAST_CHECKPOINT` | OpenPI checkpoint directory |
| `OPENVLA_OFT_PYTHON` / `OPENVLA_OFT_CHECKPOINT` | OpenVLA-OFT interpreter / checkpoint |
| `SMOLVLA_PYTHON` / `SMOLVLA_CHECKPOINT` | SmolVLA interpreter / checkpoint |

See `.env.example` for a copyable template.
