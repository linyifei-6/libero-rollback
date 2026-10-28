"""Optional native-state preflight during a real, unperturbed baseline.

Imported only by an isolated external evaluator. Every trial restores simulator
coordinates; no model is queried for trials and no recovery score is produced.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

import yaml


def json_value(value):
    """Thaw immutable compiler parameters while preserving booleans/numbers."""
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if hasattr(value, "item"):
        return json_value(value.item())
    return value


class NativePreflight:
    def __init__(self, env, context):
        self.env = env
        self.context = context
        self.pending = {}
        self.rows = {}
        self.specs = {}
        self.first_native_success_step = None
        self.post_success_window_steps = 40
        self.directory = os.environ.get("ROLLBACK_PREFLIGHT_OUTPUT")
        if not self.directory:
            return
        from libero_runtime.engine.spec import SpecCompiler

        from libero_rollback.runtime import runtime_binding

        root = Path(os.environ["ROLLBACK_DATASET_ROOT"])
        manifest = yaml.safe_load((root / "dataset/current/manifest.yaml").read_text())
        compiler = SpecCompiler(str(Path(__file__).parent / "configs"))
        with tempfile.TemporaryDirectory() as temporary:
            for entry in manifest["cases"]:
                path = root / entry["path"]
                case = yaml.safe_load(path.read_text())
                binding = runtime_binding(case)
                if (
                    binding["perturbation_binding"]["task_profile"]
                    != context.task_profile.profile_id
                ):
                    continue
                binding_path = Path(temporary) / "binding.yaml"
                binding_path.write_text(yaml.safe_dump(binding))
                specs = compiler.compile_binding(str(binding_path))
                self.specs[case["case_id"]] = (
                    case,
                    specs[0],
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )

    def continue_after_success(self, sim_step, native_success):
        """Bounded baseline observation until released completion triggers occur."""
        if not self.directory or not native_success:
            return False
        if self.first_native_success_step is None:
            self.first_native_success_step = int(sim_step)
        missing = any(
            case["trigger"].get("time_point") == "all_done" and case_id not in self.rows
            for case_id, (case, _, _) in self.specs.items()
        )
        return missing and int(sim_step) - self.first_native_success_step < (
            self.post_success_window_steps
        )

    def step(self, events):
        if not self.directory:
            return
        for case_id, (case, spec, digest) in self.specs.items():
            if case_id in self.rows or case_id in self.pending:
                continue
            if case["trigger"]["event"] in events:
                self.pending[case_id] = self.context.sim_step + case["trigger"].get(
                    "delay_steps", 0
                )
        for case_id, step in list(self.pending.items()):
            if self.context.sim_step < step:
                continue
            del self.pending[case_id]
            self.trial(case_id)

    def trial(self, case_id):
        from libero_runtime.engine.executor import ExecutionReport
        from libero_runtime.engine.interventions.completed_subgoal_rollback import (
            CompletedSubgoalRollbackHandler,
        )

        case, spec, digest = self.specs[case_id]
        row = {
            "case_id": case_id,
            "case_sha256": digest,
            "step": int(self.context.sim_step),
            "kind": "native_baseline_preflight",
            "model_recovery_evaluated": False,
        }
        if spec.intervention.handler != "completed_subgoal_rollback":
            row.update(
                status="requires_dynamic_drive_validation",
                reason="Joint drive requires an independent stepped episode",
            )
            self.rows[case_id] = row
            return
        env = self.env
        original_qpos = env.sim.data.qpos.copy()
        original_qvel = env.sim.data.qvel.copy()
        saved_arrays = {
            name: getattr(env.sim.data, name).copy()
            for name in ("ctrl", "act", "qacc_warmstart")
            if hasattr(env.sim.data, name)
        }
        report = ExecutionReport(pert_id=spec.case_id, report_kind="compiled")
        try:
            handler = CompletedSubgoalRollbackHandler(
                spec=spec, report=report, log_fn=lambda *args: None
            )
            handler.reset(env, self.context)
            handler.activate(env, self.context)
            observed = report.intervention.get("observed", {})
            requested = report.intervention.get("requested", {})
            if case["rollback_target"]["state_change"]["kind"] != "restore_native_relation_set":
                from libero_runtime.engine.validators.completed_subgoal_rollback import (
                    CompletedSubgoalRollbackValidator,
                )

                # Check immediate physical conditions without inventing a policy
                # query or pretending the temporal continuation was executed.
                errors = CompletedSubgoalRollbackValidator().validate(
                    requested=requested, observed=observed, cleaned_up=False
                )
                errors = [
                    e
                    for e in errors
                    if e["name"]
                    not in {
                        "ROLLBACK_NOT_EXPOSED_TO_POLICY",
                        "ROLLBACK_NOT_CLEANED",
                    }
                ]
                row["validation_errors"] = errors
                if errors:
                    raise ValueError("; ".join(e["name"] for e in errors))
            post = observed.get("post_predicate")
            if observed.get("pre_predicate") is not True or not isinstance(post, bool):
                raise ValueError("PREFLIGHT_NATIVE_TRUTH_UNVERIFIED")
            row.update(
                status="preflight_control" if post else "preflight_rollback",
                observed=observed,
                requested=requested,
            )
            if case.get("transient"):
                row["protocol_scope"] = (
                    "first_write_only; temporal continuation requires a live episode"
                )
            if case.get("pose_role") == "measured_relation_probe" and post:
                row["status"] = "preflight_relation_preserving_probe"
        except Exception as exc:
            row.update(status="preflight_rejected", reason=f"{type(exc).__name__}: {exc}")
        finally:
            env.sim.data.qpos[:] = original_qpos
            env.sim.data.qvel[:] = original_qvel
            env.sim.forward()
            for name, saved in saved_arrays.items():
                getattr(env.sim.data, name)[:] = saved
            row["coordinates_restored"] = bool(
                (env.sim.data.qpos == original_qpos).all()
                and (env.sim.data.qvel == original_qvel).all()
            )
        self.rows[case_id] = row

    def finish(self):
        if not self.directory:
            return
        for case_id, (_, _, digest) in self.specs.items():
            self.rows.setdefault(
                case_id,
                {
                    "case_id": case_id,
                    "case_sha256": digest,
                    "status": "trigger_not_reached",
                    "model_recovery_evaluated": False,
                },
            )
        result = {
            "schema_version": "libero-rollback.native-preflight.v1",
            "task_profile": self.context.task_profile.profile_id,
            "baseline_native_success": bool(self.context._predicate_env._check_success()),
            "first_native_success_step": self.first_native_success_step,
            "post_success_observation_limit_steps": self.post_success_window_steps,
            "cases": self.rows,
        }
        output = Path(self.directory)
        output.mkdir(parents=True, exist_ok=True)
        (output / f"{self.context.task_profile.profile_id}.json").write_text(
            json.dumps(json_value(result), indent=2)
        )
