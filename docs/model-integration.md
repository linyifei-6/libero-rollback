# External evaluator integration contract

The dataset has no model SDK dependency. An evaluator or model adapter reads immutable case definitions, executes them in its own environment, and stores results outside the case files.

## Read cases

Read `dataset/current/manifest.yaml` to discover the release, schema, case IDs, and case paths. Parse each YAML case and validate it with the declared JSON Schema before use. Resolve the `task_id` using the referenced LIBERO-10 task definition; do not use historical `source_task_locator` values as task IDs. Preserve `case_id` unchanged through planning, execution, and reporting.

Example Python read path:

```python
from pathlib import Path

import yaml

case_path = Path("dataset/two-subtask/cases/libero-10-02-yellow-white-mug-microwave-rollback-s1-mid-offset-n3.yaml")
case = yaml.safe_load(case_path.read_text(encoding="utf-8"))
case_id = case["case_id"]
task_id = case["task"]["task_id"]
```

The `libero-rollback` CLI validates the case before a runner consumes it. A case definition alone does not guarantee that an episode reached the trigger or that the intervention was physically valid.

## Runner responsibilities

An external evaluator should associate each run with at least the dataset version, `case_id`, task ID, evaluator/adapter version, seed or episode identifier, trigger observation, intervention validity, and a result reference. It must independently check the case's `validity_constraints`, including whether the completed relation was true before intervention, the target relation became false, and the resulting state remains in the declared workspace and feasible task domain.

Store execution outcomes, model outputs, simulator state, logs, and media in the evaluator's result store. Do not mutate case YAML. The optional bridge writes a separately versioned `libero-rollback.run-result.v1` normalized record in `case_result.json`; it is not part of the case schema. Associate results with the exact case ID, case hash, case version, binding and runtime hashes, model, seed and execution settings.

## Optional dependencies

The default package installs only PyYAML and `jsonschema`. Model frameworks, model service clients, GPU/CUDA libraries, and simulators are out of scope and must be installed by a separate evaluator environment if needed.

## Local runtime bridge

For a local evaluator that follows the runtime layout used by LIBERO-plus, the
repository provides the unified `libero-rollback evaluate` command (`run-case`
remains an alias). The command requires explicit
paths for the external Python executable, LIBERO checkout, runtime checkout,
adapter identifier, and checkpoint. It first validates the case, maps its
`source_task_locator` (for example `T33`) and `rollback_target.state_change`
to a temporary runtime binding, then invokes the external runner in `--mode
both` by default so a paired baseline and rollback episode are recorded. Case
selection accepts one or more YAML paths, repeatable `--case-id` or `--task`
filters, or `--all-cases`. Batch runs execute cases independently and write an
`evaluation-summary.json` alongside per-case result directories.
The command exposes model, suite, perturbation dimension, severity override,
maximum steps, seed, replanning interval, execution mode, output path, and
optional video recording. Dataset v1 accepts only suite `LIBERO_10` and
dimension `rollback`; unsupported suites or dimensions fail before launching
the evaluator. Severity selects one of the source-defined variants while the
case's concrete state-change parameters remain the scenario definition.

The bridge writes `manifest.json`, `runtime-binding.yaml`, `binding.yaml`, `execution-plan.json`, `runtime-provenance.json`, `completion.json`, `runner.log`, and a
normalized `case_result.json` below `runs/<timestamp>/<case_id>/`. The result
contains the dataset version, immutable case ID, adapter/checkpoint, seed,
trigger and intervention fields when the runner reports them, the observed
pre/post relation booleans when available, validity, and a copy of the raw
perturbation record. A missing trigger or an unsuccessful episode is recorded
as a runtime outcome; it does not alter the case YAML.
The command exits successfully when the external result was written and the
intervention was valid. A model failure remains visible in
`episode_success`, `baseline_success`, and the original `runner_returncode`;
it is a valid negative evaluation outcome rather than a bridge crash. Missing
results or invalid injection evidence still produce a non-zero exit status.

The bridge maps state-change kinds and labels currently present in the catalog. New handlers require explicit mapping, capability negotiation, schema/template review and negative tests. The optional isolated overlay advertises `completed_pose`, `native_boundary`, `functional_boundary`, `recovery_gate`, `completion_precondition`, `articulation_delay` and `atomic_relation_set`; unsupported evaluators fail before model loading.

Output directories containing results or completion records cannot be overwritten. Report selection prioritizes matching provenance, then latest attempt, without choosing successful outcomes. Stale definition/binding records, missing baselines, invalid injections, controls, relation-preserving probes, external restorations and incomplete protocols are excluded from the model rollback recovery denominator. A multi-relation recovery additionally requires exact predicate identity and all final target truths.

`scripts/run_grid_cases.py --native-preflight --baseline-only` runs independent injection trials on real baseline states and restores simulator coordinates after each trial. It does not query a model for recovery or prove temporal continuation. Joint drives require independent stepped validation. Live paired episodes remain the recovery evaluation mechanism; preflight evidence and run outcomes are stored separately.
