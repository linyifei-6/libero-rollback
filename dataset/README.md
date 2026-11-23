# LIBERO-Rollback dataset card (draft)

> Version: `2.0.0.dev0` ｜ Phase 1 (M1 data migration) ｜ authoritative contract: [`../docs/SPEC.md`](../docs/SPEC.md)
> Machine-readable sources of truth: the CSVs in [`matrices/`](matrices/) and [`manifest.yaml`](manifest.yaml).
> This card is honest about what is frozen, what is provisional, and what is missing.

## 1. What is in this directory

| File | Rows | Status | Meaning |
|---|---:|---|---|
| [`matrices/a-matrix.csv`](matrices/a-matrix.csv) | 40 | frozen | A `single-intact`: the 40 B-matrix task keys, no perturbation |
| `libero-rollback/completion-rollback.csv` | 442 | canonical | B `completion-boundary-rollback` (`C0/L0/L1/L2`) |
| `libero-rollback/in-execution-rollback.csv` | 180 | canonical | C: 9 L10 tasks × `early/mid/later`, no C0 |
| [`matrices/b-matrix.csv`](matrices/b-matrix.csv) | 442 | legacy | old B source; not in manifest/splits |
| [`matrices/d-native-matrix.csv`](matrices/d-native-matrix.csv) | 189 | legacy | old D-native; C canonical is 180 |
| [`matrices/d-compose-provisional.csv`](matrices/d-compose-provisional.csv) | 360 | **legacy** | old D-compose placeholder; superseded by the compose suite `intact.csv` + `rollback.csv` |
| compose suite: `intact.csv` | 176 | frozen definitions | D-intact valid n=2 goal/object |
| compose suite: `rollback.csv` | 528 | frozen definitions | D-rollback 176 × 3 windows × L0 |
| [`compose/bddl/`](compose/) | 352 files | frozen assets | 176 BDDL + 176 sibling init for D |
| [`manifest.yaml`](manifest.yaml) | — | generated | counts + per-file sha256 + evaluation splits ([SPEC §8](../docs/SPEC.md)) |
| [`lite.yaml`](lite.yaml) | 30 | generated | the deterministic `lite` smoke/reproduction split ([SPEC §10](../docs/SPEC.md)) |
| [`sources.yaml`](sources.yaml) | — | hand-maintained | provenance, upstream pin, import sha256 ([SPEC §9](../docs/SPEC.md)) |

Build/verification commands (no simulation, no GPU needed):

```bash
python scripts/validate_dataset.py --dataset dataset   # static dataset contract + sha256 + hygiene
python scripts/build_manifest.py --check               # manifest.yaml / lite.yaml are 0-diff reproducible
python scripts/build_compose_suite.py --check          # D-intact 176 + D-rollback 528 definitions
python scripts/build_suite_matrices.py --check         # B/C suite views
python scripts/build_a_matrix.py --libero-home "$LIBERO_HOME" --check   # A matrix is a pure function of BDDL + B tasks
python -m pytest tests/test_dataset.py                 # pytest mirror of the same checks
```

All data files are UTF-8 without BOM with LF line endings, and contain **no absolute
host paths**. Imported rows were re-normalised from CRLF to LF on import (the repository
pins `eol=lf`); `sources.yaml` records both the observed source hash and the frozen hash.

## 2. Suites in Phase 1

- **A (40).** One row per `(suite, task_idx)` task key of B, so A↔B pairing is one-to-one.
  `instruction` and `n_goals` are read verbatim from the upstream LIBERO BDDL of that task
  (`:language` line, `:goal` atoms after `And` expansion); `init_source` is LIBERO_HOME-relative.
- **B (442).** Canonical view: `libero-rollback/completion-rollback.csv`; base `b-matrix.csv`
  levels `C0` 40 / `L0` 60 / `L1` 180 / `L2` 162; every task has one `C0` control.
- **C (180).** Canonical view: `libero-rollback/in-execution-rollback.csv`; 9 L10 tasks ×
  `early/mid/later`; no `all_done_control` (B owns it); levels `L0` 27 / `L1` 81 / `L2` 72.
- **D-intact (176).** the compose suite `intact.csv`: 76 goal + 100 object valid n=2 structures.
- **D-rollback (528).** the compose suite `rollback.csv`: 176 structures × 3 windows × `L0`.
- Legacy files `b-matrix.csv` / `d-native-matrix.csv` / `d-compose-provisional.csv` are
  retained for provenance but are not in `manifest.files` or any split.

## 3. Splits

| split | content | size |
|---|---|---:|
| `lite` | 10 A + 10 B + 5 C + 2 D-intact + 3 D-rollback | 30 cases |
| `core` | `a` + `b` + `c` + `d_intact` + `d_rollback` | 1,366 cases |
| `variance` | 40 A + 30 B + 15 C + 9 D-intact + 6 D-rollback at init rows 0–4 | 100 structures × 5 init = 500 episodes |
| legacy | old `b-matrix.csv` / `d-native-matrix.csv` / `d-compose-provisional.csv` | not executable, not in splits |

The `lite` and `variance` selections are pure functions of the matrices, so they are
reproducible with `scripts/build_manifest.py`.

## 4. Known data debts and limitations (must be resolved or carried forward before release)

1. **`task_idx` numbering vs SPEC §2.2.** SPEC §2.2 describes `task_idx` as a stable
   0–9 renumbering, but the imported B/D rows use the source's LIBERO global task indices
   (e.g. `goal/t030`, `l10/t237`), and A is derived from those keys to keep A↔B pairing.
   The data currently keeps the imported numbering; the SPEC sentence is stale relative to
   the frozen matrices and must be reconciled (rename SPEC or renumber data) before publishing.
2. **D-native `trigger_criterion` labels are legacy strings** (`"s1 first true"`,
   `"s2 displacement > 5 cm"`, `"distance to s2 goal < 8 cm"`, `"no injection"`), not the
   SPEC §3.4 event names (`enter_first_subgoal_completed`, …). Rows were imported verbatim;
   the runner must map them (or the data must be re-issued as a versioned change). The
   deprecated 5 cm / 8 cm geometry criteria must not be re-introduced as runtime criteria.
3. **D-compose is a placeholder.** `instruction`, `revoked_predicate` and `revoked_object`
   are the literal marker `<from C>`; no C structure is bound. It is excluded from every
   executable split and listed under `manifest.provisional`.
4. **C suite is missing** (0 rows): no `c-matrix.csv`, no `dataset/compose/` assets. D-compose
   cannot execute until C ships, and the `EGC`, `PP` and A↔C comparison claims are Phase 2.
5. **`n_targets` (B/D) and `n_goals` (A) are different quantities.** A's `n_goals` is the
   BDDL `:goal` arity after `And` expansion; B/D's `n_targets` is the source matrix's
   runtime-tracked goal-atom count (e.g. `goal/t030` has 1 BDDL goal atom but `n_targets=3`
   because of tracked preconditions). Do not compare the two columns directly.
6. **`L1`/`L2` are not difficulty levels.** They are two perturbation *shapes* (translation
   extrapolation vs world-z yaw); reading them as a monotone difficulty ladder is wrong.
7. **Construction-level valid ≠ physically verified.** The matrices were validated at the
   construction level; injection validity, solvability (C3) and restorability (C4) oracles are
   Phase 2 work. No episode-level evidence is claimed here.
8. **External assets are not vendored.** A/D rows reference upstream LIBERO BDDL/init files via
   `LIBERO_HOME`; nothing from `libero/libero/assets` is copied into this repository.
9. **B mixes n=1 and n=2 tasks** (`l10` has native multi-goal tasks); report B by suite and
   keep B(`l10`) separate from the strictly n=1 anchors ([README §9.3](../README.md)).

## 5. Certificate status (Phase 1)

| Certificate | Status |
|---|---|
| C1 completeness | matrix-level counts/hashes/coverage enforced by `validate_dataset.py` + manifest |
| C2 initial state | not yet run (needs the simulation smoke test; `scripts/smoke_env.py`) |
| C3 solvability | Phase 2 (script oracle) |
| C4 restorability | Phase 2 (script oracle) |
| C5 non-degeneracy | construction-level only (A↔B task keys and B target/level contracts) |
| C6 negative controls | `C0` rows present and validated as "must stay true"; execution evidence Phase 2 |
| C7 GT recording | trace/`gt_atoms_raw` format defined in SPEC; runner evidence Phase 2 |
| C8 cost | protocol constants pinned; measured cost Phase 3 |

## 6. Provenance and licensing

The upstream LIBERO pin is
`f78abd68ee283de9f9be3c8f7e2a9ad60246e95c` (MIT). The B/D matrix rows come from the
frozen legacy case-matrix snapshot; exact source path, import date, source hash and frozen
hash are recorded in [`sources.yaml`](sources.yaml). The A matrix is generated in-repo from
the upstream BDDL files and the B task keys (`scripts/build_a_matrix.py`). C-suite definitions
(Phase 2) will be generated in-repo, not imported. See `THIRD_PARTY_NOTICES.md` and the
attribution notes for the full upstream notice.

This dataset contains no model weights, no demonstration data and no LIBERO scene assets.
