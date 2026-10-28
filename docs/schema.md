# Case schema v1

The normative schema is [`../schemas/rollback-case.v1.schema.json`](../schemas/rollback-case.v1.schema.json). Each YAML case describes a scenario, not an execution.

| Field | Meaning |
| --- | --- |
| `schema_version` | Schema contract identifier; incompatible field or semantic changes require a new major schema. |
| `dataset_version`, `case_id` | Dataset release and stable unique case identity. |
| `template_id` | Reusable scenario pattern declared in `dataset/current/templates.yaml`; each concrete case still stores its resolved task parameters. |
| `source` | IDs from `dataset/current/sources.yaml` plus the precise source-case locator. `supporting_source_ids` cites documents that define secondary interpretation such as severity labels or trigger delay. |
| `task` | LIBERO-10 suite, stable base-task ID, list index, source BDDL, and optional source locator. |
| `stage`, `trigger`, `intervention_description` | Completed task stage, event/window, and source-described external event. `delay_steps` is the number of control steps from the trigger to the specified intervention; zero is explicit and is not inferred. |
| `completed_relations` | Predicate(s) already confirmed when the event occurs, with whether the predicate appears in the source task goal. A selector can represent a source-defined dynamic choice, such as the first completed subgoal in execution order. |
| `rollback_target` | Relation to invalidate, affected object and state transformation. Explicit actors resolve to their profile subgoal; `selected_relation_actor` selects the actual first completed relation. A historical completion ledger never substitutes for current native truth. |
| `validity_constraints` | Static requirements an evaluator must establish for an actual run. These are not assertions that preflight has passed. |
| `scenario_type`, `severity`, `severity_rationale` | Broad scenario category, source-specific position/mechanism label, and its rationale. Historical `d0/d1/d2/d3/checkpoint` and current grid labels are described below; these are transformations, not measured model difficulty. Source labels R01-R05 remain in `source.case_reference`. |
| `expected_evaluation_semantics` | Scope: `relation_only`, `relation_then_resume`, `protected_partial`, `unsupported_boundary`, or `relation_holds_control`. This is an evaluation contract, not a predicted model outcome. |
| `assumptions`, `open_questions` | Explicit construction assumptions and unresolved details. Empty lists mean the source review identified none for that field, not that a simulator run has validated the case. |

Source-adapted parameters retain their source interpretation. Project-authored candidates explicitly mark numeric parameters as construction proposals and record unresolved feasibility. Offsets always declare their reference frame; native completed-pose probes may supply an axis-angle rotation. An angle alone does not establish relation failure. Result payloads are prohibited by `additionalProperties: false` and belong in a separate evaluator-owned format.

## State changes and protocols

| State-change kind | Definition and verification |
| --- | --- |
| `restore_episode_initial_pose`, `apply_episode_initial_offset` | Reset to initial pose, optionally with a recorded signed offset. |
| `restore_captured_checkpoint_pose` | Restore an actually captured checkpoint; unavailable checkpoints invalidate execution. |
| `restore_container_above_pose` | Define a container-relative endpoint; penetration and native false truth must be checked. |
| `revert_articulation_goal` | Revoke a joint goal with an external stepped drive; optional `functional_boundary` selects the native threshold side. |
| `displace_from_completed_pose` | Translate/rotate the achieved endpoint in world coordinates; `pose_role=measured_relation_probe` permits relation-preserving outcomes to be classified separately. |
| `displace_reference_object` | Move the named reference role and verify the selected native relation and all protected goals. |
| `translate_relation_pair` | Move both relation endpoints by the same vector; a relation-preserving control must remain true. |
| `displace_to_relation_boundary` | Search a legal horizontal pair at a declared resolution and distance bound; inside is a control, outside must revoke truth. No legal pair means rejection, not permission to skip collision checks. |
| `restore_native_relation_set` | Atomically reset distinct explicit native goals to episode-initial free-body/joint endpoints. All selected predicates must be true before and false after; protect other goals. This defines an endpoint intervention, not a demonstrated continuous collision-free trajectory. |

`transient` defines a second external write. `pre_injection` restores the pre-intervention pose after a specified number of control steps and is external restoration, not model repair. `initial_offset` with `gate=relation_recovered` re-revokes only after native recovery holds for the required steps. An absent second event is an incomplete protocol. Complete live episodes must retain policy-query and truth evidence.

`time_point=all_done` requires actual native task success, released actors and a continuation window after success. Task 09 has a single native goal; no two-goal case is constructed for it. Canonical task identity and runtime BDDL variants remain separate (task 09 canonical T256, installed runtime T276).

## Perturbation labels

The current catalog preserves labels from separate source collections. d0/d1/d2/d3/checkpoint are
historical distance or checkpoint labels; n/p/r05 encode signed offsets; above, articulation,
pose, and reference identify mechanism families. A label is not a cross-task difficulty score.
The authoritative state change and numeric parameters are in each case's rollback_target field.
