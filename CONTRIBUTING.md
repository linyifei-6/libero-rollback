# Contributing

Thanks for helping improve LIBERO-Rollback. This repository is a **benchmark**:
the frozen test sets are part of the scientific contract, so some changes are
intentionally harder than in a normal code repository.

## Ground rules

1. **Frozen data is immutable.** `case_id` values and case semantics never change
   silently. Any data change goes through a dataset version bump plus a
   `dataset/manifest.yaml` update (see `docs/SPEC.md`).
2. **Do not add new assets, scenes or visual distributions.** The benchmark only
   perturbs the causal structure of LIBERO tasks. New task families need a
   design note and a coverage proof first.
3. **No method contributions.** Do not add recovery algorithms, controllers,
   test-time harnesses, training code or VLM judges to the metric path.
4. **Independence.** Runtime code must not import the precursor research
   repositories (`libero_compose`, `libero_runtime`) and must not embed
   machine-specific absolute paths. CI enforces this.
5. **Every number carries a protocol.** When you add results to a report or the
   README, include model/checkpoint, number of initial states, step budget and CI.

## Development workflow

```bash
uv sync --extra dev
bash scripts/ci_check.sh   # ruff + pytest + dataset validation + independence guards
```

For runtime changes (simulation / model adapters):

```bash
export LIBERO_HOME=/path/to/LIBERO
export MUJOCO_GL=egl
uv venv --python 3.11 .venv-sim
uv pip install --python .venv-sim/bin/python -r requirements-sim.lock.txt
uv run python scripts/bootstrap_libero.py --libero-home "$LIBERO_HOME" --out .cache/libero
uv run python scripts/verify_libero.py --libero-home "$LIBERO_HOME"
uv run python scripts/smoke_env.py --libero-home "$LIBERO_HOME"
```

## Adding a model

1. Create an isolated environment for the model (one environment per model
   family; do not share it with the simulation/benchmark environments).
2. Add an entry to `configs/models.yaml` (adapter, interpreter env var,
   checkpoint env var, action horizon, preprocessing flags).
3. Implement the adapter in `src/libero_rollback/policies/` with the same
   contract as the existing ones: `reset(seed)` and
   `predict(observation, instruction) -> (T, 7)`.
4. Run a single-case smoke (`scripts/run_b_matrix.py --policy <id> --max-cases 1`)
   and attach the exact command + environment to the PR.

## Adding cases

Cases are generated from matrices, never hand-edited. A new case matrix needs:

- a documented construction rule and completeness certificate (C1, C5);
- an initial-state check (`success=False`, no penetration) (C2);
- a no-op control where applicable (C6);
- an entry in `dataset/sources.yaml` / `dataset/manifest.yaml`.

## Reporting issues

Please include: dataset version, matrix file + case id, model/checkpoint id,
exact command, environment (`uv run libero-rollback --version`, LIBERO commit),
and the relevant `summary.json` / `trace.jsonl` lines.
