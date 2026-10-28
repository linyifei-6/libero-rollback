# Dataset card

## Purpose

LIBERO Rollback Dataset records model-independent evaluation cases in which an external event invalidates a relation that had already been confirmed during a LIBERO-10 manipulation task. A case defines the task, completed relation, trigger window, state change, static validity conditions, provenance, and intended evaluation semantics.

## Scope

The target suite is the ten base LIBERO-10 BDDL tasks listed in `dataset/current/coverage.yaml`. The task inventory was checked against the LIBERO-plus source tree recorded in `dataset/current/sources.yaml`; task names and goal predicates are taken from those BDDL definitions. Historical task locators from the reference source are preserved only as provenance aliases. Coverage status `documented` means a source-described case is present; it does not claim that simulator preflight has passed. `candidate` marks a plausible relation that needs more scenario definition, while `requires_research` marks an unresolved task-level question.

The repository versions scenario definitions, schema, coverage, provenance, and lightweight validation code. An optional process bridge invokes an independently installed evaluator; isolated validation overlays implement candidate interventions in that environment. The repository supplies no recovery algorithm, controller, simulator, model or weights. The static validator does not prove physical feasibility: an external evaluator must perform the declared execution validity checks.

## Dataset and case contents

Cases are YAML documents validated with `schemas/rollback-case.v1.schema.json`. Task coverage is separate from case definitions so that unresolved tasks remain visible without being represented as runnable cases. `templates.yaml` defines reusable transformations and the task-specific parameters each instance must supply. Concrete cases remain self-contained and name their template, task, relation, trigger, and sources. `sources.yaml` records the task-definition source and separate scenario-reference groups. The manifest lists dataset files, their roles, case IDs, source IDs, SHA-256 digests, and the static validation status.

Scenario definitions are distinct from run results. Model outputs, logs, videos, success labels, and measured simulator state belong to an external evaluator's result store and must not be added to case files.

## Limitations

Version 1.0.0 current catalog contains 288 definitions from four separately identified collections: 129 two-subtask, 57 rollback-battery, 4 reference-object, and 98 progress-failure cases. The 24 `progress-pulse-*` cases (all from progress-failure) were de-scoped on 2026-10-16: the evaluator restored the revoked relation itself, so the family could not measure model repair, and its shortest window was shorter than one policy query period. Definitions, data, reports and a code snapshot are archived in `archive/pulse-descoped-20261016/`. All ten tasks have definitions; task 09 has one completion-boundary candidate and no invented second goal. The 98 progress-failure cases (case version 1.8.0) are unreleased proposals with explicit assumptions and open questions. Static acceptance and native-state preflight do not establish full model-recovery acceptance. The catalog preserves each case's original dataset_version and does not silently merge source semantics. Existing run artifacts are external evidence and do not change the definitions. Current validation status is maintained in implementation-status.md.

## Versioning

Dataset and case documents use semantic dataset versions (`MAJOR.MINOR.PATCH`); the schema identifier carries its own major version (`libero-rollback.case.v1`).

- Add cases or backward-compatible optional metadata in a minor release. Keep existing case IDs and meanings unchanged.
- Make a correction that cannot change interpretation in a patch release and document it in the release notes.
- A schema-incompatible change or a change to the meaning of an existing case requires a new major dataset release and a new schema version. Preserve the old release and assign a new case ID to changed semantics; never silently replace a published case.
- Update the manifest digests whenever a released file changes. A digest update does not by itself justify changing the dataset version; classify the semantic impact first.

### Working dataset label revision, 2026-10-09

At the dataset owner's request, this working tree retains version `1.0.0`
while replacing its earlier severity labels and case filenames/IDs with
`d0/d1/d2/d3/checkpoint`. No legacy aliases are accepted. Source references
R01-R05 and the defined state transformations are preserved. The manifest
digests have been refreshed. This is an explicit exception for the current
working dataset; future published revisions follow the rules above.
Historical local run artifacts retain their original identifiers and must
not be treated as results from the newly named files without checking the
case transformation and provenance.

## Citation

No standalone paper citation is defined for this dataset. Until one is assigned, cite the repository, release version, and exact case IDs, for example:

> LIBERO Rollback Dataset, catalog version 1.0.0, case `libero-10-01-black-bowl-drawer-rollback-s1-mid-initial-pose`, case version 1.6.0.

Include the source registry and access date in archival or benchmark publications. Do not cite historical experiment outcomes as dataset definitions.
