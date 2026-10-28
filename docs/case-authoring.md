# Adding cases and extending the dataset

Version 1 separates reusable scenario patterns from concrete task instances:

- `dataset/current/templates.yaml` describes the supported state-change pattern, required validity constraints, source documents, and task-specific parameters.
- `paths listed by dataset/current/manifest.yaml (the files remain in their source collections)` is the runnable definition consumed by an evaluator. Each file repeats the resolved task, relation, actor or selector, trigger, transform, source locator, assumptions, and open questions; it does not require a private template engine to interpret.
- `dataset/current/coverage.yaml` keeps all ten base tasks visible, including tasks for which the sources do not yet support a clear case.

## Add an instance of an existing template

1. Confirm the base task and goal predicate from its source BDDL. Record its stable `libero_10/NN` ID, BDDL filename, and any historical task locator separately.
2. Find an existing template in `templates.yaml`. Copy a concrete case that uses it, assign a new stable `case_id`, and replace all task-specific values. Keep signed vectors, axis order, trigger semantics, and source wording exactly traceable to the cited source.
3. Set `source.case_reference` to the exact source row or case ID and include the source-registry IDs for the case definition, task definition, and task-locator crosswalk. Add `supporting_source_ids` when another document defines an interpretation used by the case, such as a severity label or trigger delay.
4. Add the case ID to its coverage row and add the case path and source ID to `manifest.yaml`. Regenerate SHA-256 digests for every entry in `manifest.files` after the data and schema changes are final.
5. Run `uv run libero-rollback validate-case <path>`, `uv run libero-rollback validate-dataset`, `uv run libero-rollback check-manifest`, `uv run pytest`, and `uv run ruff check .`.

`validate-dataset` checks that each case names a known template, uses its declared state-change kind, includes all template validity constraints, matches the task ID/index/BDDL in the coverage matrix, and references declared sources. It also checks that a static rollback target was declared as completed, or that a dynamic rollback selector resolves to a declared selector.

## Add a new reusable pattern

Add a template when source material or an explicitly identified project proposal defines a distinct reusable transformation or selection rule. Give it a stable versioned `template_id`, list its supporting source IDs, state-change kind, required validity constraints, and task-specific parameters. Project proposals must label parameters as assumptions and remain candidates until execution checks pass. Extend the case schema only if the new pattern needs fields the current schema cannot express. Then add positive and negative schema tests, static cross-reference checks, and concrete cases before updating manifest digests.

Do not copy measured coordinates or physical thresholds from another task. Source omissions belong in `open_questions`. A new project proposal may explicitly define angle/duration/search-resolution parameters, but cannot call them source measurements or proven feasible states. The `severity` field preserves collection-specific mechanism labels as well as `d0/d1/d2/d3/checkpoint`; see schema.md. `checkpoint` specifically means captured pregrasp restoration. Source labels such as R01-R05 belong only in source references.

To reproduce the extension, run `uv run python scripts/generate_progress_failure_cases.py`, `uv run python scripts/build_current_catalog.py`, and `uv run python scripts/build_case_matrix_doc.py`. Existing source collections remain separate. Extending a mechanism requires coordinated schema, generator, template, bridge-capability and negative-test updates. External preflight/live evidence stays under runs/, with case hashes and exact binding provenance.

## Provenance and releases

Different source collections remain separately identified by `case_source_id` and `case_reference`. A case can also cite a task-definition source and a task-locator crosswalk source. Keep source aliases out of the stable task ID. If an existing case's interpretation changes, create a new case ID and follow the major-version rules in the dataset card.
