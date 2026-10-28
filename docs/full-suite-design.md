> Historical design note: this document describes an earlier candidate release. The authoritative current catalog is dataset/current and the current matrix is docs/case-matrix-current.md.\n\n# Full-suite rollback definitions, 2026-10-09

Candidate release 1.1.0 preserves the 20 source-adapted cases from 1.0.0 and adds
30 project-authored cases for tasks 00, 04, 05, 06, 08, and 09. These new cases
are not attributed to the historical R01-R05 source. Task predicates come from
the authoritative BDDL inventory; transformation parameters are explicit
project design choices. Numeric values are proposals until physical preflight.

Each task has d0 (initial pose), d1 ([0.05,0.05,0] m), d2 ([-0.08,0.06,0] m),
d3 ([0.10,0.08,0] m), and checkpoint (captured pregrasp pose). Offset vectors
use the runtime task frame, whose lateral axis is +Y and vertical axis is +Z.
Their physical validity is evaluated individually, not inferred across tasks.

For the three basket tasks and mug/pudding task, select the first completed
placement in actual execution order. Rollback must change its predicate from
true to false, after release, and leave the remaining placement feasible.
For task 00, revoke the pot placement, retain the stove state and instruction;
it may occur at task completion. For task 09, revoke the book's only placement.
Tasks 00 and 09 use an explicit post-success continuation protocol so that a
completion signal does not terminate the episode before intervention. Their
results must be identified as completion-boundary evaluations, not silently
combined with nonterminal multi-placement rollback.

The test budget is 600 control steps, seed 0 initially, paired baseline and
perturbation with video. Non-triggered and invalid injections are reported as
coverage attempts, never counted as valid rollback or model recovery failures.
Actual BDDL names must be recorded because LIBERO-plus exposes generated scene
variants at runtime indices. Additional seeds or destination revisions may be
needed after observing failure evidence. Validity checks do not prove a general
geometric solution; release, support, collision and solvability evidence remain
mandatory review items.

Runtime profiles are generated into an ignored disposable overlay under runs/;
the sibling repository remains unchanged. The overlay reuses existing runner,
policy and intervention implementations, with task-specific roles and predicates.
No model, simulator or ML dependency is installed into the dataset environment.
