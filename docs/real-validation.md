> 历史验证记录：本文对应早期用例与运行时，不能代表当前327条catalog。最新定义见 [case-matrix-current.md](case-matrix-current.md)，本轮验证见 [validation-current.md](validation-current.md)。

# Real simulation validation

The dataset package stays lightweight and does not install a simulator or an
adapter. A local validation can use the existing sibling checkout at
`../libero-plus`; no model download is needed.

## Reproduce

From the repository root:

```bash
bash scripts/run_local_validation.sh
```

The script defaults to the locally available OpenVLA-OFT environment and
checkpoint. These variables select another already-installed setup:

```bash
LIBERO_ADAPTER=your-adapter \
LIBERO_PYTHON=/path/to/python \
LIBERO_CHECKPOINT=/path/to/checkpoint \
LIBERO_OUTPUT=runs/my-validation \
bash scripts/run_local_validation.sh
```

The external runner performs a paired baseline and rollback episode. Results
are written under `runs/`, which is ignored by the repository. The normalized
`case_result.json` is an execution record and is not part of dataset v1.

## v1 verification record

The table uses the current case names after the 2026-10-09 label revision.
The historical artifacts in `runs/` retain their original IDs; they have not
been rewritten or rerun as part of that revision. The recorded initial-pose
transformations are unchanged.

On 2026-10-09, the default local setup used the already-installed OpenVLA-OFT
checkpoint from the sibling `libero-plus` checkout. Four representative cases
were executed with seed `0` (T33 used 600 maximum steps; the others used 300):

| case | baseline | trigger | injection | rollback episode |
| --- | --- | ---: | --- | --- |
| `libero-10-01-black-bowl-drawer-d0-early` (T33) | success, 246 steps | 148 | valid; true → false | not recovered within 600 steps |
| `libero-10-02-yellow-white-mug-microwave-d0-early` (T78) | success, 252 steps | 141 | valid; true → false | not recovered within 300 steps |
| `libero-10-03-first-moka-pot-stove-d0-early` (T133) | not complete within 300 steps | 170 | valid; true → false | not recovered within 300 steps |
| `libero-10-07-white-mug-left-plate-d0-early` (T193) | success, 227 steps | 110 | valid; true → false | not recovered within 300 steps |

The model loaded on `cuda:0` and the simulator, intervention validator, and
result normalizer completed for all four runs. A negative rollback outcome is a
valid evaluation result; it does not imply that a recovery algorithm failed in
general. Run artifacts are kept under the ignored `runs/` directory and are not
part of dataset v1.

These runs verify the repository's case loading, runtime binding, simulator
creation, model inference, intervention, and result normalization path. They do
not claim that the other 16 cases have passed physical preflight or that one
model's outcome defines the dataset.

## Pi05 smoke verification

Pi05 can be checked without adding OpenPI or simulator dependencies to this
repository. The grid runner selects the already-installed OpenPI environment
from the sibling checkout:

```bash
uv run python scripts/run_grid_cases.py \
  --model pi05 --cases dataset/two-subtask/cases --task 01 --limit 1 \
  --max-steps 40 --output runs/pi05-smoke
```

On 2026-10-10 this completed one real Pi05 episode and wrote
`results.json`, `evaluation_summary.json`, and `episode_details.jsonl` under
`runs/pi05-smoke/`. The process returned exit code `2`, which denotes a valid
evaluation whose rollback injection was not valid or whose task did not
recover; it is not a model startup error. The log contains the Pi05 model
episode and the normalized predicate trace. A longer run and video recording
can be enabled with `--max-steps 600 --video`.

The same path is available through the unified CLI. For cached Pi05, omit
`--checkpoint`; for adapters with an explicit local checkpoint, keep the flag:

```bash
uv run libero-rollback evaluate \
  dataset/two-subtask/cases/libero-10-01-black-bowl-drawer-rollback-s1-mid-offset-n3.yaml \
  --python ../libero-plus/openpi/.venv/bin/python \
  --libero-root ../libero-plus/LIBERO-plus \
  --runtime-root runs/full-coverage/runtime \
  --model pi05 --max-steps 600 --output runs/pi05-cli
```
