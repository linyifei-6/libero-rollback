# Runtime dimension grid, 2026-10-09

Release 1.2.0 expands the rollback dataset from five labels per task to the full
dimension grid implemented in `../libero-plus/libero-runtime`. The grid is bounded
by what the engine actually supports, verified against the runtime source rather
than assumed from the benchmark documents.

## 1. Goal predicates per task

Each LIBERO-10 task is a conjunction of goals. Placement predicates and
articulation predicates (`Close`, `Turnon`) are separate revocable goals, and the
engine scores both: `effective_success` is the native LIBERO goal check, and the
`completed_subgoal_rollback` handler does not override it.

| task | runtime idx | goal predicates | articulation modelled |
| --- | --- | --- | --- |
| 00 | T0 | `(Turnon flat_stove_1)`, `(On moka_pot_1 flat_stove_1_cook_region)` | no |
| 01 | T33 | `(Close white_cabinet_1_bottom_region)`, `(In akita_black_bowl_1 ...)` | yes |
| 02 | T78 | `(In white_yellow_mug_1 microwave_1_heating_region)`, `(Close microwave_1)` | yes |
| 03 | T133 | `(On moka_pot_1 ...)`, `(On moka_pot_2 ...)`, `(Turnon flat_stove_1)` | no |
| 04 | T137 | two `In ... basket_1_contain_region` | no |
| 05 | T145 | two `In ... basket_1_contain_region` | no |
| 06 | T158 | two `In ... basket_1_contain_region` | no |
| 07 | T193 | `(On porcelain_mug_1 plate_1)`, `(On white_yellow_mug_1 plate_2)` | no |
| 08 | T237 | `(On porcelain_mug_1 plate_1)`, `(On chocolate_pudding_1 ...)` | no |
| 09 | T276 | `(In black_book_1 desk_caddy_1_back_contain_region)` | no |

## 2. Engine constraints the grid must respect

1. **The rollback target is the first completed subgoal.**
   `completed_subgoal_rollback.py:278` selects
   `context.subgoal_completion_order[0]`; `actor_role`/`reference_role` are only
   membership-checked (`:256`, `:260`) and do not choose the object. The
   `completed_subgoal_object` alias resolves to that subgoal's actor role at run
   time (`context.py:624-636`), so a binding must pass the role name the profile
   actually uses for its first subgoal (`subgoal_object_a` for T33/T78/T133/T193,
   `subgoal_object_0` for T0/T137/T145/T158/T237/T276).
2. **Articulation rollback is a different handler.** `articulation_setback`
   requires the profile to declare an `articulation` block and
   `actor_role == articulation.body_role` (`setback.py:103-112`); only T33 and T78
   qualify. Its intervention parameter set must equal its own whitelist exactly
   (`setback.py:52`), and its severity parameters must be exactly
   `{setback, position_tolerance}` (`:86-93`).
3. **The closure instant is not a placement trigger.**
   `completed_subgoal_rollback` accepts eight rollback events and
   `enter_articulation_completed` is not among them (`:20-29`, `:219-222`), so the
   closure time point is used by the articulation goal only.
4. **Event coverage decides the usable time points.** T0/T133/T137/T145/T158/
   T193/T237/T276 declare `next_subgoal_*` milestones (early/mid/later); T33/T78
   declare `post_completion_retreat`, `x3a_actuation` and `articulation_completed`
   instead. No profile declares `articulation_approach`.
5. **`container_above` needs a goal region.** It resolves the hover pose from the
   subgoal's `goal_state_name`, so only T33 (`white_cabinet_1_bottom_region`) and
   T78 (`microwave_1_heating_region`) can use it; T0, T193 and T276 have no region
   in their profile.

## 3. The grid as released

| task | time points | destinations | cases |
| --- | --- | --- | --- |
| 00 | closure only | initial pose, 4 offsets, pre-grasp checkpoint | 6 |
| 01 | early / mid / later, plus closure for the articulation goal | 6 placement + 2 container-above + 3 articulation setbacks | 33 |
| 02 | as task 01 | as task 01 | 33 |
| 03–08 | early / mid / later | initial pose, 4 offsets, pre-grasp checkpoint | 18 each |
| 09 | closure only | initial pose, 4 offsets, pre-grasp checkpoint | 6 |

Offsets are signed task-frame vectors: `n3`/`n5`/`n8` move towards the robot,
`p5`/`p10` move away, all on the support surface. Container hover uses
`clearance_m` 0.05 or 0.20 with `above_container_top`. Articulation setbacks are
0.02/0.06/0.12 m for the sliding drawer and 0.10/0.30/0.60 rad for the microwave
hinge.

## 4. Runtime contract added by this release

Two templates are generated into the runtime overlay:

* `hv_completed_subgoal_rollback_grid` — 30 severity variants named
  `l{1,2}_grid_<destination>_<time point>` for placement rollback;
* `hv_articulation_goal_rollback` — 18 variants named
  `l3_grid_art_<setback label>_<time point>` for articulation rollback.

The dataset bridges to them through `runtime_binding`, which derives the variant
from the case's destination label and trigger event. Severity variant names must
match the runtime pattern `l[123](_[a-z0-9_]+)?` (`spec.py:834`).

## 5. Open items

* Magnitudes (offsets, clearances, setbacks) are project design choices and still
  need episode-specific physical preflight; the validity constraints in each case
  are the checklist for that preflight.
* Tasks 00 and 03 cannot roll back their `Turnon` goal until their profiles gain
  an articulation block; the stove joint name is not recorded anywhere in the
  configuration tree.
* The second placement of a two-placement task cannot be revoked selectively
  without changing the handler's target selection.

## 6. The remaining gap: stove activation (tasks 00 and 03)

Tasks 00 and 03 carry a `(Turnon flat_stove_1)` goal that the runtime does not
model for them, so that goal cannot be revoked yet. The engine is capable; both
profiles are missing configuration.

**Correction to an earlier note:** `libero_10_t0.yaml` does *not* declare an
`articulation_target` role. That role belongs to `libero_goal_t270.yaml`. Both
`libero_10_t0.yaml` and `libero_10_t133.yaml` therefore need the same three
additions:

1. a role resolving to the knob body,
   `articulation_target: {kind: body, name: flat_stove_1_button}`;
2. an `articulation` block,
   `{joint_name: flat_stove_1_button, body_role: articulation_target,
   direction: increasing, success_threshold_rad: 0.5}` — the joint name is the
   MuJoCo joint (`context.py:493` resolves it through `joint_name2id`), and
   `flat_stove.xml` declares `<joint name="button" type="hinge" axis="0 0 1">`
   inside the button body, so the scene-namespaced joint is `flat_stove_1_button`;
3. an `articulation_completed: {}` milestone so `enter_articulation_completed`
   exists (`triggers.py:196-206` requires the milestone key to be present).

The binding must also pass `actor_role: articulation_target`, because
`articulation_setback` requires the actor role to equal `articulation.body_role`
(`setback.py:103-112`).

**Verified before/after.** A staged copy of the config tree with exactly those
changes (`runs/stove-articulation-staging/configs/`) compiles an
articulation-goal binding for both tasks:

```
staged config : OK   trigger: enter_articulation_completed | actor: articulation_target | setback: 0.06
live config   : FAIL template references unknown profile role 'articulation_target'
```

**Still required before merging:** calibrate `success_threshold_rad`. The value
0.5 is copied from the working T270 profile, not measured for tasks 00/03. Run a
baseline episode of each and confirm `articulation_completed` flips exactly when
the episode reports success; otherwise the closure trigger fires at the wrong step.
Also note `context.py:520,578` compares the absolute joint position, not progress
relative to the initial pose.

Once merged the case counts become 14 for task 00 (6 placement + 8 articulation)
and 26 for task 03 (18 placement + 8 articulation), and `Turnon` becomes a
first-class revocable goal for both.

Ordering: a profile edit changes the compiled spec of every case of that task, so
it must not be made while a sweep is running.

## 7. Mechanism dimensions: staged, verified, not yet in the sweep

The delivered RB-3 suite carries two mechanism dimensions that the 1.2.0 grid does
not yet include. Both are implemented by the same handler parameter, and both
payload shapes were copied from the delivered bindings and compiled successfully:

| mechanism | payload | source binding |
| --- | --- | --- |
| transient failure: the relation is restored shortly after revocation, then fails again | `transient_pose: {after_steps: 20, destination: pre_injection}` | `configs/perturbation_bindings/pfcr_rb3_t33_rollback.yaml` (`rb_rb3_transient`) |
| consecutive revocation: a second write happens while recovery is under way | `transient_pose: {after_steps: 60, destination: initial_offset, offset_m: [0.05, 0.05, 0], offset_frame: task_frame}` | same file (`rb_rb3_second`) |

`transient_pose` is on the handler whitelist (`completed_subgoal_rollback.py:59`)
and validated at `:166-201`; the handler applies at most two writes per episode
(`:783`), so the pair above is the strongest form the engine supports.

Four staged cases (two mechanisms × two tasks) live in `runs/mechanism-staging/`
with their compiled bindings; see that directory's README for the integration
steps. They are deliberately outside `the source case collections recorded by dataset/current/manifest.yaml` because a sweep
enumerates that directory and adding files mid-sweep would mix incomparable
episodes into one result set.

## 8. Offset legality is per task, and the first sweep violation is measured

The signed task-frame offsets (`n3`/`n5`/`p5`/`p10`, plus the mechanism probes on
`n5`) were chosen as a shared grid so the same destination means the same thing on
every task. The first sweep measurements show that assumption does not hold
everywhere: an offset that is legal on a living-room table can push the object into
a fixture on a kitchen scene.

Measured on task 00 (runtime idx 0), the longest "away" vector is rejected:

```
case    libero-10-00-moka-pot-stove-place-early-p10
offset  [-0.10, -0.08, 0.0]
result  injection_valid = false, rule_executed = false, injection_step = 0
error   INTERVENTION_ACTIVATION_FAILED
        invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATION
```

The engine's penetration gate refused the write, so the episode ran the
unperturbed prefix to completion and reports `success: true`. That is **not** a
model recovery: the perturbation never happened. The analyzer and the report
already exclude it (`injection_valid is True` gates the recovery numerator), which
matches the documented rule that invalid injections are coverage records and are
never counted as model-recovery failures.

Task 00's legal offsets measured so far: `[0.03,0.03,0]`, `[0.05,0.05,0]`,
`[-0.05,-0.05,0]`, initial pose and the pre-grasp checkpoint all inject validly;
`[-0.10,-0.08,0]` does not.

### Consequence for the grid

Two options, and they should not be mixed silently:

1. **Record and report.** Keep the offsets as a shared grid, report the invalid
   cells per task, and let the recovery rate be computed only over valid
   injections. This keeps the grid comparable across tasks and produces a real
   finding: which destinations are physically reachable per task.
2. **Calibrate per task.** Replace a rejected vector with the largest legal one for
   that task, so every grid cell injects. This raises coverage but makes the
   magnitude task-specific, so cross-task comparison must then be done per
   direction rather than per label.

The sweep in flight uses option 1. Any later calibration must bump the dataset
version and re-run the affected cells; editing offsets now would make already
collected episodes and later ones non-comparable.

### 8.1 Articulation drive envelope needs its own calibration

The same sweep measured a second legality class, this time on the articulation
channel: the drive was overpowered by the joint it must move. Requested a 0.020 m
drawer setback, achieved 0.0074 m (error 0.0126 > `position_tolerance` 0.005) while
the joint reacted at 182.2 N against a `linear_force_limit_n` of 40 — an envelope
copied from templates that only nudge 3–5 mm. See
`runs/stove-articulation-staging/README.md` for the full measurement and the four
parameters that must be calibrated before articulation cells can count.

The envelope sweep is implemented in `scripts/calibrate_articulation_drive.py`
(four variants, all verified to compile). It runs after the grid sweep because it
starts a second model process.

## 9. Release 1.3 plan (calibrated articulation vocabulary)

1.2.0 shipped guessed articulation magnitudes. Running them measured exactly what was
wrong, so the corrected vocabulary ships as 1.3.0 while 1.2.0 stays intact as the
evidence for that finding.

### Calibration ledger

| quantity | measured | consequence |
| --- | --- | --- |
| drawer drive at 40 N | reached 0.0205 m of a requested 0.060 m; joint reacted at 182.2 N | envelope too weak |
| drawer drive at 300 N | reached 0.0614 m but tripped the per-step body-jump gate | force alone is not enough |
| drawer drive at 600 N, 0.60 m·s⁻¹, 60 monitor steps | reached exactly 0.060 m, zero position error, injection valid | adopted as the envelope |
| drawer setback 0.12 m on that envelope | reached 0.12 m but rejected: `ARTICULATION_STEP_CHANGE_TOO_LARGE` | largest magnitude needs a lower velocity |
| door drive at 80 / 150 / 250 N | reaction only 0.8 / 1.6 / 3.4 N; reached 0.080 / 0.212 / 0.258 rad of a requested 0.30 rad, all stopping at 148 control steps | the door is nearly frictionless; the drive stops for another reason |
| delivered door templates | nudge only 0.03–0.07 rad | the supported door band is far below 0.10–0.60 rad |

### Vocabulary change (implemented in `scripts/generate_grid_cases.py`)

| task | joint | old magnitudes | new magnitudes |
| --- | --- | --- | --- |
| 01 (T33) | slide drawer | 0.02 / 0.06 / 0.12 m | 0.02 / 0.06 / 0.10 m |
| 02 (T78) | hinge door | 0.10 / 0.30 / 0.60 rad | 0.02 / 0.04 / 0.07 rad |

Driven envelope (already applied to the runtime template and the bridge):
`linear_force_limit_n: 600`, `linear_velocity_m_s: 0.60`,
`angular_torque_limit_nm: 60`, `monitor_steps_after_completion: 60`.

### Remaining steps to ship 1.3.0

1. `scripts/build_grid_release.py` still hardcodes `dataset/current`; generalise it to
   take `--release`/`--version` (the generator already does);
2. regenerate: `scripts/generate_grid_cases.py --release dataset/current --version 1.3.0 --write`;
3. rebuild the release, refresh digests with `scripts/update_model_digests.py`
   (see `scripts/update_manifest_digests.py --dataset-root dataset/current`);
4. update the runtime template's `l3_grid_art_*` variants to the new magnitudes
   (`s02/s06/s10`, `h02/h04/h07`);
5. re-run the sweep: `scripts/run_grid_cases.py --output runs/v1.3-grid --video`;
6. report with `scripts/build_grid_report.py --sweep runs/v1.3-grid`.

### Known-invalid cells carried into 1.3.0 unless calibrated

* offset `p10` = `[-0.10,-0.08,0]`: rejected on task 00 as
  `ROLLBACK_PATHOLOGICAL_PENETRATION`; the other nine tasks are unmeasured.
* the largest drawer magnitude may still need a per-magnitude velocity.

Neither is a blocker: injection validity gates the recovery numerator, so invalid
cells are reported as coverage records.

## 10. Release 1.3.0 status

Built and validated on 2026-10-09.

| item | state |
| --- | --- |
| cases | 186, same grid shape as 1.2.0 |
| corrected articulation vocabulary | drawer 0.02/0.06/0.10 m, door 0.02/0.04/0.07 rad |
| calibrated drive envelope | 600 N, 0.60 m·s⁻¹, 60 monitor steps (template and bridge synced) |
| `validate-dataset` / `check-manifest` | pass |
| binding compilation | 186/186 through the runtime SpecCompiler |
| reuse of 1.2.0 evidence | 174 of 186 cases are binding-identical; the envelope change only affects the `articulation_setback` handler, so 1.2.0 episodes for the unchanged cells stay valid. Episodes are seeded into `runs/v1.3-grid` and recorded in `runs/v1.3-grid/REUSE-NOTES.json`. |
| sweep | running: `run_grid_cases.py --output runs/v1.3-grid --max-steps 400 --video` |

Rebuild commands:

```
python scripts/generate_grid_cases.py --release dataset/current --version 1.3.0 --write
python scripts/build_grid_release.py --release dataset/current --version 1.3.0
python scripts/update_manifest_digests.py --dataset-root dataset/current
python scripts/run_grid_cases.py --output runs/v1.3-grid --max-steps 400 --video
python scripts/build_grid_report.py --sweep runs/v1.3-grid
```

Known open items: the offset `p10` legality question (section 8) and the largest
drawer magnitude needing a per-magnitude velocity (section 9).

### Milestone: the corrected articulation envelope injects validly

First measured episode of the corrected grid
(`libero-10-01-black-bowl-drawer-close-later-s02`):

```
injection_valid : True
requested 0.02 m setback, achieved 0.01999999999999999 m, position error 0.0
peak joint reaction recorded, drive envelope 600 N / 0.60 m·s⁻¹ / 60 steps
```

This closes the articulation-envelope finding from section 8.1: with the calibrated
envelope the drawer rollback reaches its target exactly, whereas the 40 N envelope
reached only 0.0205 m of a requested 0.060 m.
