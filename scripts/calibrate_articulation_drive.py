"""Sweep articulation drive envelopes to find one that reaches the setback target.

The measured failure (`ARTICULATION_SETBACK_INCOMPLETE`, achieved 0.0074 m of a
requested 0.020 m while the joint reacted at 182 N against a 40 N drive limit)
means the envelope copied from the millimetre-nudge templates is too weak for a
centimetre-scale reopening.

This script re-runs one articulation case per envelope variant and reports the
achieved setback, so the envelope can be chosen from measurement. Run it after the
main grid sweep: it starts a second model process.

Usage:
    python scripts/calibrate_articulation_drive.py --dry-run
    python scripts/calibrate_articulation_drive.py --case libero-10-01-black-bowl-drawer-close-after-s06
"""


from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

VARIANTS = [
    # stove knob (hinge, range [-0.005, 2.1] rad). The gate allows
    # max_drive_window_joint_step_change <= angular_velocity * 0.05 * 2.0, and the joint
    # overshoots its servo ramp, so a lower torque limit is what keeps it inside.
    ("stove_v05_t08", {
        "linear_velocity_m_s": 0.08, "angular_velocity_rad_s": 0.50,
        "linear_force_limit_n": 40.0, "angular_torque_limit_nm": 8.0,
        "monitor_steps_after_completion": 60,
    }),
    ("stove_v06_t04", {
        "linear_velocity_m_s": 0.08, "angular_velocity_rad_s": 0.60,
        "linear_force_limit_n": 30.0, "angular_torque_limit_nm": 4.0,
        "monitor_steps_after_completion": 60,
    }),
    ("stove_v06_t02", {
        "linear_velocity_m_s": 0.06, "angular_velocity_rad_s": 0.60,
        "linear_force_limit_n": 20.0, "angular_torque_limit_nm": 2.0,
        "monitor_steps_after_completion": 80,
    }),
]


ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "dataset/early-p1/cases"
RUNTIME = ROOT / "runs/full-coverage/runtime"
PLUS = ROOT.parent / "libero-plus"
PYTHON = PLUS / "openvla-oft-env/bin/python"
CHECKPOINT = PLUS / "models/openvla-7b-oft-finetuned-libero-spatial-object-goal-10"
CASES = CASES_DIR
OUTPUT = ROOT / "runs/articulation-drive"

# envelope variants: (label, drive parameters)
VARIANTS: list[tuple[str, dict]] = [
    ("base_40n", {
        "linear_velocity_m_s": 0.20, "angular_velocity_rad_s": 0.60,
        "linear_force_limit_n": 40.0, "angular_torque_limit_nm": 4.0,
        "monitor_steps_after_completion": 5,
    }),
    ("force_300n", {
        "linear_velocity_m_s": 0.20, "angular_velocity_rad_s": 0.60,
        "linear_force_limit_n": 300.0, "angular_torque_limit_nm": 30.0,
        "monitor_steps_after_completion": 5,
    }),
    ("force_300n_steps_40", {
        "linear_velocity_m_s": 0.20, "angular_velocity_rad_s": 0.60,
        "linear_force_limit_n": 300.0, "angular_torque_limit_nm": 30.0,
        "monitor_steps_after_completion": 40,
    }),
    ("force_600n_fast_steps_60", {
        "linear_velocity_m_s": 0.60, "angular_velocity_rad_s": 1.20,
        "linear_force_limit_n": 600.0, "angular_torque_limit_nm": 60.0,
        "monitor_steps_after_completion": 60,
    }),
    # The hinge (T78 microwave door) overshot into penetration with the slide
    # envelope, so its own, gentler variants are measured separately.
    ("door_80n_slow", {
        "linear_velocity_m_s": 0.08, "angular_velocity_rad_s": 0.20,
        "linear_force_limit_n": 80.0, "angular_torque_limit_nm": 8.0,
        "monitor_steps_after_completion": 80,
    }),
    ("door_150n_slow", {
        "linear_velocity_m_s": 0.08, "angular_velocity_rad_s": 0.20,
        "linear_force_limit_n": 150.0, "angular_torque_limit_nm": 15.0,
        "monitor_steps_after_completion": 80,
    }),
    ("door_250n_slow", {
        "linear_velocity_m_s": 0.10, "angular_velocity_rad_s": 0.25,
        "linear_force_limit_n": 250.0, "angular_torque_limit_nm": 25.0,
        "monitor_steps_after_completion": 80,
    }),
]



SEVERITY_BY_SETBACK = {
    0.02: "l3_grid_art_s02_after",
    0.06: "l3_grid_art_s06_after",
    0.10: "l3_grid_art_s10_after",
    0.04: "l3_grid_art_h04_after",
    0.07: "l3_grid_art_h07_after",
    0.12: "l3_grid_art_s12_after",
    0.30: "l3_grid_art_h30_after",
    0.60: "l3_grid_art_h60_after",
}


def build_binding(case: dict, drive: dict) -> dict:
    setback = float(case["rollback_target"]["state_change"]["setback"])
    try:
        variant = SEVERITY_BY_SETBACK[setback]
    except KeyError as exc:
        raise SystemExit(f"no severity variant for setback {setback}") from exc
    parameters = {"zero_velocity": True, **drive}
    return {
        "perturbation_binding": {
            "task_profile": f"libero_10_{case['task']['source_task_locator'].lower()}",
            "enabled_cases": [{
                "case_name": "driveprobe_" + case["case_id"].replace("-", "_"),
                "template": "hv_articulation_goal_rollback",
                "severities": [variant],
                "trigger_event": case["trigger"]["event"],
                "actor_role": "articulation_target",
                "parameters": parameters,
                "description": case["intervention_description"],
            }],
        }
    }


def measure(out_dir: Path) -> dict | None:
    for result_path in sorted(out_dir.rglob("results.json")):
        document = json.loads(result_path.read_text())
        for task_data in document.values():
            for value in (task_data.get("results") or {}).values():
                if not isinstance(value, dict) or value.get("kind") != "perturbation":
                    continue
                report = value.get("report") or {}
                observed = (report.get("intervention") or {}).get("observed") or {}
                return {
                    "injection_valid": report.get("injection_valid"),
                    "task_success": value.get("success"),
                    "achieved_setback": observed.get("actual_setback") or observed.get("actual_setback_m"),
                    "position_error": observed.get("position_error") or observed.get("position_error_m"),
                    "peak_reaction_n": observed.get("peak_joint_reaction_effort"),
                    "control_steps": observed.get("control_steps"),
                    "errors": [e.get("name") for e in (report.get("errors") or [])
                               if isinstance(e, dict)],
                }
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="libero-10-00-moka-pot-stove-rollback-s1-s2-early-p1")
    parser.add_argument("--variants", nargs="*", default=[],
                        help="labels to run (default: all)")
    parser.add_argument("--max-steps", type=int, default=400)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-n", type=float, help="override linear force limit (N)")
    parser.add_argument("--velocity", type=float, help="override linear velocity (m/s)")
    parser.add_argument("--steps", type=int, help="override monitor_steps_after_completion")
    args = parser.parse_args()

    case_path = CASES / f"{args.case}.yaml"
    if not case_path.is_file():
        raise SystemExit(f"case not found: {case_path}")
    case = yaml.safe_load(case_path.read_text())
    setback = case["rollback_target"]["state_change"]["setback"]
    print(f"case: {args.case}")
    print(f"  joint setback target : {setback}")
    print(f"  trigger              : {case['trigger']['event']}")
    print(f"  task profile         : libero_10_{case['task']['source_task_locator'].lower()}")

    selected = [v for v in VARIANTS if not args.variants or v[0] in args.variants]
    if args.force_n or args.velocity or args.steps:
        override = dict(selected[-1][1])
        if args.force_n:
            override["linear_force_limit_n"] = args.force_n
            override["angular_torque_limit_nm"] = args.force_n / 10.0
        if args.velocity:
            override["linear_velocity_m_s"] = args.velocity
            override["angular_velocity_rad_s"] = args.velocity * 2.0
        if args.steps:
            override["monitor_steps_after_completion"] = args.steps
        label = f"override_{int(override['linear_force_limit_n'])}n_{override['linear_velocity_m_s']}v_{override['monitor_steps_after_completion']}s"
        selected = [(label, override)]
        print(f"override drive: {override}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LIBERO_VIDEO_ENCODER_PYTHON"] = str(PLUS / "openpi/.venv/bin/python")
    env["PYTHONPATH"] = os.pathsep.join([str(PLUS / "LIBERO-plus"), str(RUNTIME)])

    print(f"\nvariants: {len(selected)}")
    results = []
    for label, drive in selected:
        out_dir = OUTPUT / args.case / label
        out_dir.mkdir(parents=True, exist_ok=True)
        binding_path = out_dir / "binding.yaml"
        binding_path.write_text(
            yaml.safe_dump(build_binding(case, drive), sort_keys=False), encoding="utf-8"
        )
        command = [
            str(PYTHON), str(RUNTIME / "tools/run_benchmark.py"),
            "--model", "openvla_oft", "--mode", "perturbation", "--suite", "LIBERO_10",
            "--task-idx", case["task"]["source_task_locator"][1:],
            "--binding", str(binding_path), "--dimension", "rollback",
            "--seed-ids", "0", "--max-steps", str(args.max_steps),
            "--replan-steps", "10", "--checkpoint", str(CHECKPOINT),
            "--output", str(out_dir),
        ]
        # The articulation trigger coincides with task success, so the episode must
        # survive the first success signal for the injection to execute.
        command.append("--post-success-window")
        print(f"\n[{label}] drive={drive}")
        if args.dry_run:
            print("   dry run; binding written to", binding_path)
            continue
        with (out_dir / "runner.log").open("w") as log:
            proc = subprocess.run(command, cwd=str(RUNTIME), env=env, stdout=log,
                                  stderr=subprocess.STDOUT)
        measured = measure(out_dir)
        results.append((label, proc.returncode, measured))
        print(f"   rc={proc.returncode} -> {json.dumps(measured, ensure_ascii=False)}")

    if results and not args.dry_run:
        print("\n=== envelope comparison ===")
        print(f"{'variant':<26}{'rc':<5}{'valid':<7}{'achieved':<12}{'target':<9}{'error':<10}{'reaction N'}")
        for label, rc, measured in results:
            if not measured:
                print(f"{label:<26}{rc:<5}no measurement")
                continue
            print(f"{label:<26}{rc:<5}{str(measured['injection_valid']):<7}"
                  f"{str(measured['achieved_setback']):<12}{setback:<9}"
                  f"{str(measured['position_error']):<10}{measured['peak_reaction_n']}")
        (OUTPUT / args.case / "comparison.json").write_text(
            json.dumps({"case": args.case, "setback_target": setback,
                        "results": [{"variant": l, "returncode": r, "measured": m}
                                    for l, r, m in results]}, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
