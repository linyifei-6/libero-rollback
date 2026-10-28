"""Build an isolated evaluator overlay; never edit the sibling runtime.

The dataset's default Python environment does not import these simulator extensions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"runtime source changed: expected one anchor {old[:100]!r}")
    return text.replace(old, new, 1)


def prepare(output: Path) -> Path:
    if output.exists():
        raise ValueError(f"refusing to overwrite existing overlay: {output}")
    base = ROOT / "runs/full-coverage/runtime"
    shutil.copytree(base, output, symlinks=False, ignore=shutil.ignore_patterns("__pycache__"))
    # Catalog profiles are versioned inputs. The base evaluator may lack newer
    # milestones (e.g. full completion for placement + Close tasks).
    for profile in sorted((ROOT / "dataset/runtime-profiles").glob("*.yaml")):
        shutil.copy2(profile, output / "configs/task_profiles" / profile.name)
    shutil.copy2(ROOT / "scripts/runtime_extensions.py", output / "rollback_extensions.py")
    shutil.copy2(ROOT / "scripts/runtime_preflight.py", output / "rollback_preflight.py")
    handler = output / "libero_runtime/engine/interventions/completed_subgoal_rollback.py"
    s = handler.read_text()
    s = replace_once(
        s,
        "class CompletedSubgoalRollbackHandler(InterventionHandler):",
        "from rollback_extensions import CompletedPoseMixin\n\n\n"
        "class CompletedSubgoalRollbackHandler(CompletedPoseMixin, InterventionHandler):",
    )
    s = replace_once(
        s,
        '            "reference_object",',
        '            "reference_object",\n            "expected_post_predicate",\n'
        '            "boundary",\n            "require_task_complete",\n'
        '            "relation_set",',
    )
    s = replace_once(
        s,
        '            "container_above",\n        }:',
        '            "container_above",\n            "completed_offset",\n'
        '            "relation_boundary",\n        }:',
    )
    s = s.replace(
        'if destination == "initial_offset":',
        'if destination in {"initial_offset", "completed_offset"}:',
    )
    s = replace_once(
        s,
        "        else:\n            source_pose = initial",
        '        elif destination in {"completed_offset", "relation_boundary"}:\n'
        '            source_pose = {"position": env.sim.data.body_xpos[body_id].copy(),\n'
        '                           "quaternion": env.sim.data.body_xquat[body_id].copy()}\n'
        "        else:\n            source_pose = initial",
    )
    # A world-axis delta premultiplies the completed orientation.
    s = replace_once(
        s,
        "            target_quaternion, orientation_delta\n",
        "            orientation_delta, target_quaternion\n",
    )
    s = replace_once(
        s,
        "else env.sim.data.qpos[qpos_address + 3 : qpos_address + 7],",
        'else env.sim.data.qpos[joint["qpos_address"] + 3 : joint["qpos_address"] + 7],',
    )
    s = replace_once(
        s,
        '        if destination == "container_above":\n            #',
        "        self._boundary_evidence = None\n"
        '        if destination == "relation_boundary":\n'
        "            target_position = self.resolve_relation_boundary(\n"
        "                env, context, subgoal, body_id, joint, predicate_env,\n"
        "                predicate_state, pre_position, pre_quaternion)\n"
        '        if destination == "container_above":\n            #',
    )
    s = replace_once(
        s,
        '                "pre_predicate": pre_predicate,',
        '                "boundary_search": self._boundary_evidence,\n'
        '                "pre_predicate": pre_predicate,',
    )
    s = replace_once(
        s,
        '                "stage": str(self.spec.severity.parameters["stage"]),',
        '                "expected_post_predicate": self.spec.intervention.parameters.get(\n'
        '                    "expected_post_predicate", False),\n'
        '                "stage": str(self.spec.severity.parameters["stage"]),',
    )
    s = replace_once(
        s,
        "            reference_state = self._apply_reference_object(env, context)\n"
        "            env.sim.forward()",
        "            reference_state = self._apply_reference_object(env, context)\n"
        "            env.sim.forward()\n"
        "            self.check_protected_contacts(env, context, body_id, reference_state)",
    )
    s = replace_once(
        s,
        "        subgoal_id = self._select_subgoal(context)",
        "        self.check_completion_precondition(context)\n"
        "        subgoal_id = self._select_subgoal(context)",
    )
    s = replace_once(
        s,
        "        if not context.subgoal_completion_order:",
        '        if self.spec.intervention.parameters.get("relation_set"):\n'
        "            self.activate_relation_set(env, context)\n            return\n"
        "        if not context.subgoal_completion_order:",
    )
    s = replace_once(
        s,
        "    def after_step(self, env, context, obs) -> None:\n"
        "        if not self._executed or self._rolled_subgoal_id is None:",
        "    def after_step(self, env, context, obs) -> None:\n"
        '        if self._executed and hasattr(self, "_relation_set"):\n'
        "            self.update_relation_set(context)\n            return\n"
        "        if not self._executed or self._rolled_subgoal_id is None:",
    )
    s = replace_once(
        s,
        "    def finalize(self, env, context) -> None:\n",
        "    def finalize(self, env, context) -> None:\n"
        '        if self._executed and hasattr(self, "_relation_set"):\n'
        "            self.finalize_relation_set(context)\n            return\n",
    )
    s = replace_once(
        s,
        '        observed["final_subgoal_states"] = final_states',
        "        self.record_temporal_protocol(context)\n"
        '        observed["final_subgoal_states"] = final_states',
    )
    s = replace_once(
        s,
        '            allowed_transient = {"after_steps", "destination", "offset_m", "offset_frame"}',
        '            allowed_transient = {"after_steps", "destination", "offset_m", "offset_frame",\n'
        '                                 "gate", "hold_steps"}',
    )
    s = replace_once(
        s,
        '                "pre_quaternion": pre_quaternion.tolist(),\n                "applied": False,',
        '                "pre_quaternion": pre_quaternion.tolist(),\n'
        '                "gate_step": None,\n                "applied": False,',
    )
    a = s.index(
        '        if self._transient is not None and not self._transient["applied"]:\n',
        s.index("    def after_step("),
    )
    b = s.index("        subgoal = context.subgoal_by_id(self._rolled_subgoal_id)", a)
    s = s[:a] + "        self.update_transient_gate(env, context)\n" + s[b:]
    s = replace_once(
        s,
        '            penetration, offenders = self._penetration(env, int(state["body_id"]))',
        '            penetration, offenders = self._penetration(env, int(state["body_id"]))\n'
        "            self.check_transient_write(env, context, destination, penetration)",
    )
    s = replace_once(
        s,
        "        self._actor_role = actor_role",
        "        self.check_actor_release(context, actor_role)\n"
        "        native_goals_before = self.native_goal_snapshot(context)\n"
        "        self._actor_role = actor_role",
    )
    s = replace_once(
        s,
        "            other_after = {",
        "            self.check_protected_native_goals(context, native_goals_before, predicate_state)\n"
        "            other_after = {",
    )
    handler.write_text(s)
    # Completion order is historical and may contain predicates that have since
    # become false. Completion-boundary injection needs current native success,
    # current truth and released actors, including single-placement profiles.
    triggers = output / "libero_runtime/engine/triggers.py"
    trigger_text = triggers.read_text()
    trigger_text = replace_once(
        trigger_text,
        '            active = len(\n                getattr(context, "subgoal_completion_order", ())\n            ) >= 2',
        "            active = bool(context._predicate_env._check_success()) and all(\n"
        "                context.subgoal_states.values()) and bool(context.subgoal_states)\n"
        "            active = active and all(\n"
        '                not context.metrics.get("role_robot_contact", {}).get(s.actor_role, False)\n'
        '                and context.metrics.get("role_linear_speed_m_s", {}).get(s.actor_role, 0.) <= .02\n'
        "                for s in context.task_profile.subgoals)",
    )
    # Settling must never accumulate while the relation itself is false.
    trigger_text = replace_once(
        trigger_text,
        "        first = context.subgoal_by_id(order[0])",
        "        first = context.subgoal_by_id(order[0])\n"
        "        if not context.subgoal_states.get(first.subgoal_id, False):\n"
        "            context.placement_settle_steps[first.subgoal_id] = 0\n"
        '            context.milestones["first_subgoal_settled"] = False\n'
        "            return",
    )
    trigger_text = replace_once(
        trigger_text,
        "        self._write_row(events=set())",
        "        from rollback_preflight import NativePreflight\n"
        "        self._rollback_preflight = NativePreflight(env, self.context)\n"
        "        self._write_row(events=set())",
    )
    trigger_text = replace_once(
        trigger_text,
        "        events = self.fsm.update(self.context)",
        "        events = self.fsm.update(self.context)\n"
        "        self._rollback_preflight.step(events)",
    )
    trigger_text = replace_once(
        trigger_text,
        "    def summary(self) -> dict[str, Any]:\n",
        "    def summary(self) -> dict[str, Any]:\n        self._rollback_preflight.finish()\n",
    )
    triggers.write_text(trigger_text)
    runner = output / "tools/run_benchmark.py"
    runner_text = runner.read_text()
    runner_text = replace_once(
        runner_text,
        "                        camera_widths=cam,\n                    )\n"
        "                    result = run_episode(",
        "                        camera_widths=cam,\n"
        '                        ignore_done=bool(os.environ.get("ROLLBACK_PREFLIGHT_OUTPUT")),\n'
        "                    )\n                    result = run_episode(",
    )
    runner_text = replace_once(
        runner_text,
        "                if success:\n                    break\n"
        "                if force_pfcr_replan or runtime_replan is not None:",
        "                if phase_probe is not None and (\n"
        "                    phase_probe._rollback_preflight.continue_after_success(sim_step, success)\n"
        "                ):\n                    success = False\n                    done = False\n"
        "                if success:\n                    break\n"
        "                if force_pfcr_replan or runtime_replan is not None:",
    )
    runner.write_text(runner_text)
    context_path = output / "libero_runtime/engine/context.py"
    context_text = context_path.read_text()
    context_text = replace_once(
        context_text,
        "        self.roles = resolve_roles(env, raw_obs, self.task_profile)",
        "        self._rollback_initial_qpos = env.sim.data.qpos.copy()\n"
        "        self.roles = resolve_roles(env, raw_obs, self.task_profile)",
    )
    context_path.write_text(context_text)
    validator = output / "libero_runtime/engine/validators/completed_subgoal_rollback.py"
    s = validator.read_text().replace(
        'if observed.get("post_predicate") is not False:',
        'if requested.get("expected_post_predicate") != "measure" and observed.get("post_predicate") is not requested.get("expected_post_predicate", False):',
    )
    validator.write_text(s)
    (output / "rollback-capabilities.json").write_text(
        json.dumps(
            {
                "protocol_version": 1,
                "capabilities": [
                    "completed_pose",
                    "native_boundary",
                    "functional_boundary",
                    "recovery_gate",
                    "completion_precondition",
                    "articulation_delay",
                    "atomic_relation_set",
                ],
            },
            indent=2,
        )
    )
    # Articulation delays must be honoured by the executor, not silently dropped.
    articulation = output / "libero_runtime/engine/interventions/articulation_setback.py"
    s = articulation.read_text()
    s = s.replace(
        "if set(spec.intervention.parameters) != expected_intervention:",
        'if set(spec.intervention.parameters) - {"delay_steps"} != expected_intervention:',
    )
    s = replace_once(
        s,
        "        self.spec = spec",
        '        self.delay_steps = int(spec.intervention.parameters.get("delay_steps", 0))\n'
        "        self.spec = spec",
    )
    s = replace_once(
        s,
        "class ArticulationSetbackHandler(InterventionHandler):",
        "from rollback_extensions import FunctionalBoundaryMixin\n\n\n"
        "class ArticulationSetbackHandler(FunctionalBoundaryMixin, InterventionHandler):",
    )
    s = s.replace(
        ' - {"delay_steps"}', ' - {"delay_steps", "functional_boundary", "position_tolerance"}'
    )
    s = replace_once(s, "        self.spec = spec", "        self.spec = spec")
    # Explicit tolerance is passed by new functional-boundary definitions.
    s = s.replace(
        'float(self.spec.severity.parameters["position_tolerance"])',
        'float(self.spec.intervention.parameters.get("position_tolerance", self.spec.severity.parameters["position_tolerance"]))',
    )
    s = s.replace(
        'self.spec.severity.parameters["position_tolerance"]\n',
        'self.spec.intervention.parameters.get("position_tolerance", self.spec.severity.parameters["position_tolerance"])\n',
    )
    s = replace_once(
        s,
        "        lower, upper = (float(value) for value in model.jnt_range[joint_id])",
        "        raw_target = self.functional_target(env, context, pre_position, raw_target)\n"
        "        lower, upper = (float(value) for value in model.jnt_range[joint_id])",
    )
    s = replace_once(
        s,
        '        requested = {\n            "joint_name":',
        '        requested = {\n            "expected_post_predicate": self.spec.intervention.parameters.get(\n'
        '                "functional_boundary", {}).get("side") == "inside",\n'
        '            "functional_boundary": self.spec.intervention.parameters.get("functional_boundary"),\n'
        '            "joint_name":',
    )
    s = replace_once(
        s,
        '        self.report.intervention["observed"]["completed"] = True',
        '        self.report.intervention["observed"]["completed"] = True\n'
        "        self.record_functional_completion(env)",
    )
    articulation.write_text(s)
    validator = output / "libero_runtime/engine/validators/articulation_setback.py"
    s = validator.read_text()
    s = replace_once(
        s,
        "        errors: list[dict] = []",
        "        errors: list[dict] = []\n"
        '        if requested.get("functional_boundary") is not None and (\n'
        '                observed.get("pre_predicate") is not True or\n'
        '                observed.get("post_predicate") != requested["expected_post_predicate"]):\n'
        '            errors.append(self._error("FUNCTIONAL_NATIVE_RELATION_MISMATCH",\n'
        '                                      "native Turnon predicate did not match boundary definition"))',
    )
    validator.write_text(s)
    hashes = {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.suffix in {".py", ".yaml"}
    }
    (output / "overlay-provenance.json").write_text(
        json.dumps(
            {
                "base": str(base),
                "extensions": "scripts/runtime_extensions.py",
                "sha256": hashes,
            },
            indent=2,
        )
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(prepare(parser.parse_args().output.resolve()))
