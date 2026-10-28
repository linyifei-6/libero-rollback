"""Optional evaluator extensions, copied into an isolated external environment.

All changes use installed native task predicates. No simulator dependency belongs
in the dataset package. Failed candidate searches restore the entire state.
"""

from __future__ import annotations

import numpy as np


class CompletedPoseMixin:
    def native_goal_snapshot(self, context):
        goals = context._predicate_env.parsed_problem["goal_state"]
        if goals and str(goals[0]).lower() == "and":
            goals = goals[1:]
        return {
            tuple(str(x).lower() for x in goal): bool(context._predicate_env._eval_predicate(goal))
            for goal in goals
        }

    def check_protected_native_goals(self, context, before, selected):
        selected = tuple(str(x).lower() for x in selected)
        after = self.native_goal_snapshot(context)
        if any(before[g] != after[g] for g in before if g != selected):
            raise ValueError("ROLLBACK_CHANGED_PROTECTED_NATIVE_GOAL")

    def check_actor_release(self, context, role):
        if context.metrics.get("role_robot_contact", {}).get(role, False):
            raise ValueError("ROLLBACK_ACTOR_NOT_RELEASED")

    def activate_relation_set(self, env, context):
        """Atomic endpoint reset of explicit, verified native task relations."""
        relations = self.spec.intervention.parameters["relation_set"]
        self.check_completion_precondition(context)
        predicate_env = context._predicate_env
        # Goal predicates are read from the actual installed BDDL, not inferred
        # from profile completion history (which omits articulation goals).
        goals = predicate_env.parsed_problem["goal_state"]
        if goals and str(goals[0]).lower() == "and":
            goals = goals[1:]
        goals = [tuple(str(x).lower() for x in g) for g in goals]
        selected = [tuple(str(x).lower() for x in r["predicate"]) for r in relations]
        if len(set(selected)) != len(selected) or any(g not in goals for g in selected):
            raise ValueError("RELATION_SET_NOT_DISTINCT_NATIVE_GOALS")
        pre = {g: bool(predicate_env._eval_predicate(g)) for g in goals}
        if not all(pre[g] for g in selected):
            raise ValueError("RELATION_SET_PRECONDITION_FALSE")
        original_qpos = env.sim.data.qpos.copy()
        original_qvel = env.sim.data.qvel.copy()
        writes = []
        try:
            for relation in relations:
                role = relation["actor_role"]
                body = context.body_id(role)
                if context.metrics.get("role_robot_contact", {}).get(role, False):
                    raise ValueError("RELATION_SET_ACTOR_NOT_RELEASED")
                if relation["restore"] == "episode_initial_pose":
                    subgoal = context.subgoal_by_id(relation["subgoal_id"])
                    if subgoal.actor_role != role or tuple(
                        context.subgoal_predicate_state(subgoal)
                    ) != tuple(relation["predicate"]):
                        raise ValueError("RELATION_SET_PROFILE_MISMATCH")
                    joint = self._joint_addresses(env, body)
                    if joint is None:
                        raise ValueError("RELATION_SET_ACTOR_NOT_FREE")
                    address, velocity = joint["qpos_address"], joint["qvel_address"]
                    pose = context.initial_state[role]
                    env.sim.data.qpos[address : address + 3] = pose["position"]
                    env.sim.data.qpos[address + 3 : address + 7] = pose["quaternion"]
                    env.sim.data.qvel[velocity : velocity + 6] = 0.0
                else:
                    if relation["joint_name"] != context.task_profile.articulation["joint_name"]:
                        raise ValueError("RELATION_SET_JOINT_PROFILE_MISMATCH")
                    jid = env.sim.model.joint_name2id(relation["joint_name"])
                    address = int(env.sim.model.jnt_qposadr[jid])
                    velocity = int(env.sim.model.jnt_dofadr[jid])
                    env.sim.data.qpos[address] = context._rollback_initial_qpos[address]
                    env.sim.data.qvel[velocity] = 0.0
                writes.append({"actor_role": role, "body_id": body})
            env.sim.forward()
            post = {g: bool(predicate_env._eval_predicate(g)) for g in goals}
            if any(post[g] for g in selected):
                raise ValueError("RELATION_SET_TARGET_STILL_TRUE")
            if any(pre[g] != post[g] for g in goals if g not in selected):
                raise ValueError("RELATION_SET_CHANGED_PROTECTED_GOAL")
            for write in writes:
                self.check_protected_contacts(env, context, write["body_id"])
                penetration, _ = self._penetration(env, write["body_id"])
                if penetration > float(self.spec.severity.parameters["maximum_penetration_m"]):
                    raise ValueError("RELATION_SET_PATHOLOGICAL_PENETRATION")
        except Exception:
            env.sim.data.qpos[:] = original_qpos
            env.sim.data.qvel[:] = original_qvel
            env.sim.forward()
            raise
        self._relation_set = selected
        self._predicate_env = predicate_env
        self._executed = True
        self.report.rule_executed = True
        self.report.injection_step = int(context.sim_step)
        self.report.placements.extend(writes)
        self.report.intervention["requested"] = {"relation_set": relations, "atomic": True}
        self.report.intervention["observed"] = {
            "pre_predicate": True,
            "post_predicate": False,
            "relations": [{"predicate": list(g), "pre": pre[g], "post": post[g]} for g in selected],
            "protected_relations": [
                {"predicate": list(g), "pre": pre[g], "post": post[g]}
                for g in goals
                if g not in selected
            ],
            "repair_completed": False,
            "repair_step": None,
            "policy_queries_after_rollback": 0,
            "truth_trace": [{"sim_step": int(context.sim_step), "predicate": False}],
        }

    def update_relation_set(self, context):
        observed = self.report.intervention["observed"]
        truths = [bool(self._predicate_env._eval_predicate(g)) for g in self._relation_set]
        repaired = all(truths)
        if repaired != observed["truth_trace"][-1]["predicate"]:
            observed["truth_trace"].append(
                {"sim_step": int(context.sim_step), "predicate": repaired, "relations": truths}
            )
        if repaired and not observed["repair_completed"]:
            observed["repair_completed"] = True
            observed["repair_step"] = int(context.sim_step)

    def finalize_relation_set(self, context):
        observed = self.report.intervention["observed"]
        errors = []
        if observed["policy_queries_after_rollback"] < 1:
            errors.append(
                {"name": "RELATION_SET_NO_CONTINUATION", "detail": "No policy query after reset"}
            )
        observed["final_relation_states"] = [
            bool(self._predicate_env._eval_predicate(g)) for g in self._relation_set
        ]
        self.report.intervention["cleaned_up"] = True
        self.report.validation.update({"passed": not errors, "errors": errors})
        self.report.errors.extend(errors)
        self.report.episode_validity = "injection_failed" if errors else "valid"

    def check_completion_precondition(self, context):
        if self.spec.intervention.parameters.get("require_task_complete"):
            if not context._predicate_env._check_success():
                raise ValueError("COMPLETION_BOUNDARY_NATIVE_TASK_NOT_COMPLETE")

    def record_temporal_protocol(self, context):
        state = self._transient
        if state is None:
            return
        spec = state["spec"]
        observed = self.report.intervention["observed"]
        observed["temporal_protocol"] = {
            "gate": spec.get("gate", "elapsed_steps"),
            "destination": spec["destination"],
            "second_event_applied": state["applied"],
            "second_event_step": state["applied_step"],
            # `pre_injection` means the evaluator itself restores the pre-injection pose.
             # The `progress-pulse` family that used it was de-scoped on 2026-10-16
             # (archive/pulse-descoped-20261016), so no current case reaches this flag; it is
             # kept so archived runs keep their recorded semantics and so the pathway can be
             # revived with the family.
             "external_restoration": spec["destination"] == "pre_injection",
            "complete": bool(state["applied"]),
            "end_step": int(context.sim_step),
        }

    def check_protected_contacts(self, env, context, actor, reference_state=None):
        """Reject newly placed bodies contacting robot or a different goal actor."""
        moved = {actor}
        if reference_state:
            moved.add(context.body_id(reference_state["role"]))
            penetration, _ = self._penetration(env, context.body_id(reference_state["role"]))
            if penetration > float(self.spec.severity.parameters["maximum_penetration_m"]):
                raise ValueError("REFERENCE_PATHOLOGICAL_PENETRATION")
        protected = {context.body_id(s.actor_role) for s in context.task_profile.subgoals}
        for body in moved:
            position = env.sim.data.body_xpos[body]
            for axis, bounds in context.task_profile.workspace.items():
                coordinate = position[{"x": 0, "y": 1, "z": 2}[axis]]
                if not bounds[0] <= coordinate <= bounds[1]:
                    raise ValueError("ROLLBACK_OUTSIDE_WORKSPACE")
        protected -= moved
        model = env.sim.model
        for contact in env.sim.data.contact[: env.sim.data.ncon]:
            bodies = {int(model.geom_bodyid[contact.geom1]), int(model.geom_bodyid[contact.geom2])}
            if not bodies & moved:
                continue
            other = bodies - moved
            if other & protected or any(
                str(model.body_id2name(b)).startswith(("robot", "gripper", "mount")) for b in other
            ):
                raise ValueError("ROLLBACK_CONTACTS_PROTECTED_BODY")

    def resolve_relation_boundary(
        self,
        env,
        context,
        subgoal,
        body_id,
        joint,
        predicate_env,
        predicate_state,
        position,
        quaternion,
    ):
        """Find adjacent predicate-inside/outside candidates along world XY rays.

        Both poses must pass penetration, native other-goal truth and protected
        contact checks. The grid resolution is a sampling tolerance, not a
        claimed physical boundary. Vertical pose and orientation are preserved.
        """
        spec = self.spec.intervention.parameters["boundary"]
        step = float(spec["resolution_m"])
        maximum = float(spec["max_distance_m"])
        side = spec["side"]
        original_qpos = env.sim.data.qpos.copy()
        original_qvel = env.sim.data.qvel.copy()
        address = int(joint["qpos_address"])
        limit = float(self.spec.severity.parameters["maximum_penetration_m"])
        others = {
            s.subgoal_id: bool(predicate_env._eval_predicate(context.subgoal_predicate_state(s)))
            for s in context.task_profile.subgoals
            if s.subgoal_id != subgoal.subgoal_id
        }
        tested = 0
        candidates = []
        try:
            for direction in ([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, -1.0, 0.0]):
                last_inside = None
                for distance in np.arange(step, maximum + step / 2, step):
                    target = position + np.array(direction) * distance
                    env.sim.data.qpos[:] = original_qpos
                    env.sim.data.qvel[:] = original_qvel
                    env.sim.data.qpos[address : address + 3] = target
                    env.sim.data.qpos[address + 3 : address + 7] = quaternion
                    env.sim.forward()
                    tested += 1
                    truth = bool(predicate_env._eval_predicate(predicate_state))
                    penetration, _ = self._penetration(env, body_id)
                    protected_ok = True
                    try:
                        self.check_protected_contacts(env, context, body_id)
                    except ValueError:
                        protected_ok = False
                    other_ok = all(
                        bool(predicate_env._eval_predicate(context.subgoal_predicate_state(s)))
                        == others[s.subgoal_id]
                        for s in context.task_profile.subgoals
                        if s.subgoal_id in others
                    )
                    legal = penetration <= limit and protected_ok and other_ok
                    if truth:
                        last_inside = target.copy() if legal else None
                    elif legal and last_inside is not None:
                        candidates.append(
                            (
                                float(np.linalg.norm(target - position)),
                                last_inside,
                                target.copy(),
                                direction,
                            )
                        )
                        break
                    elif not truth:
                        # A collision at the boundary cannot be skipped to create
                        # a falsely labelled close-boundary pair.
                        break
            if not candidates:
                raise ValueError("NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR")
            _, inside, outside, direction = min(candidates, key=lambda c: c[0])
            chosen = inside if side == "inside" else outside
            self._boundary_evidence = {
                "region": getattr(subgoal, "goal_state_name", None),
                "predicate": list(predicate_state),
                "side": side,
                "resolution_m": step,
                "candidates_tested": tested,
                "inside_position": inside.tolist(),
                "outside_position": outside.tolist(),
                "direction_world": direction,
                "reference_position": position.tolist(),
            }
            return chosen
        finally:
            env.sim.data.qpos[:] = original_qpos
            env.sim.data.qvel[:] = original_qvel
            env.sim.forward()

    def update_transient_gate(self, env, context):
        state = self._transient
        if state is None or state["applied"]:
            return
        spec = state["spec"]
        injection = int(self.report.injection_step)
        if int(context.sim_step) - injection < int(spec["after_steps"]):
            return
        if spec.get("gate", "elapsed_steps") == "relation_recovered":
            subgoal = context.subgoal_by_id(self._rolled_subgoal_id)
            true = bool(
                self._predicate_env._eval_predicate(context.subgoal_predicate_state(subgoal))
            )
            if not true:
                state["gate_step"] = None
                return
            if state["gate_step"] is None:
                state["gate_step"] = int(context.sim_step)
            if int(context.sim_step) - state["gate_step"] < int(spec.get("hold_steps", 1)):
                return
        self._apply_transient(env, context)
        observed = self.report.intervention["observed"]
        if spec["destination"] == "pre_injection":
            observed["externally_restored_step"] = int(context.sim_step)
        else:
            # Recovery after the first event does not prove recovery after both.
            observed["first_repair_step"] = observed.get("repair_step")
            observed["repair_completed"] = False
            observed["repair_step"] = None

    def check_transient_write(self, env, context, destination, penetration):
        subgoal = context.subgoal_by_id(self._rolled_subgoal_id)
        truth = bool(self._predicate_env._eval_predicate(context.subgoal_predicate_state(subgoal)))
        expected = destination == "pre_injection"
        if truth != expected:
            raise ValueError("TRANSIENT_NATIVE_RELATION_MISMATCH")
        if penetration > float(self.spec.severity.parameters["maximum_penetration_m"]):
            raise ValueError("TRANSIENT_PATHOLOGICAL_PENETRATION")
        self.check_protected_contacts(env, context, int(self._transient["body_id"]))


class FunctionalBoundaryMixin:
    """Drive a stove joint to a native functional threshold's inside/outside."""

    def functional_target(self, env, context, pre_position, fallback):
        spec = self.spec.intervention.parameters.get("functional_boundary")
        if spec is None:
            return fallback
        self._functional_context = context
        predicate = [
            "turnon",
            context.task_profile.roles[context.task_profile.subgoals[0].goal_role].name,
        ]
        self._functional_predicate = predicate
        if not context._predicate_env._eval_predicate(predicate):
            raise ValueError("FUNCTIONAL_RELATION_PRECONDITION_FALSE")
        # Resolve the installed object's own native threshold; refuse missing data.
        obj = context._predicate_env.objects_dict.get(predicate[1])
        if obj is None:
            obj = context._predicate_env.fixtures_dict[predicate[1]]
        threshold = min(obj.object_properties["articulation"]["default_turnon_ranges"])
        self._functional_threshold = float(threshold)
        return float(threshold) + (1 if spec["side"] == "inside" else -1) * float(
            spec["margin_rad"]
        )

    def record_functional_completion(self, env):
        if not hasattr(self, "_functional_context"):
            return
        context = self._functional_context
        env.sim.forward()
        truth = bool(context._predicate_env._eval_predicate(self._functional_predicate))
        observed = self.report.intervention["observed"]
        observed.update(
            {
                "pre_predicate": True,
                "post_predicate": truth,
                "native_threshold_rad": self._functional_threshold,
            }
        )
