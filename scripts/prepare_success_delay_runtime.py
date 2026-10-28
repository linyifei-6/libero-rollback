"""Build a disposable evaluator overlay that supports ``--success-delay``.

The sibling ``libero-plus/libero-runtime`` checkout is read-only reference
material.  This script copies an existing evaluator overlay (or any runtime
directory that contains ``tools/run_benchmark.py``), patches the *copy*, and
installs the simulator-free :mod:`libero_rollback.success_window` helper next
to it.  The reference checkout is never modified.

Usage::

    uv run python scripts/prepare_success_delay_runtime.py \
        --base runs/validation-runtime-20261019-v19 \
        --output runs/validation-runtime-20261020-v20-success-delay

The output overlay advertises the ``success_window`` capability in
``rollback-capabilities.json``; ``libero-rollback evaluate --success-delay``
and the baseline runners refuse an overlay that does not advertise it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUCCESS_WINDOW_SOURCE = ROOT / "src/libero_rollback/success_window.py"
CAPABILITY = "success_window"
SCHEMA = "libero.success-delay-overlay.v1"

REPLACEMENTS: list[tuple[str, str, str]] = [
    ('import', 'from libero_runtime.evaluation.instruction_switch import (\n    InstructionSwitchMonitor,\n    InstructionSwitchSpec,\n    load_cases as load_instruction_switch_cases,\n)\n', 'from libero_runtime.evaluation.instruction_switch import (\n    InstructionSwitchMonitor,\n    InstructionSwitchSpec,\n    load_cases as load_instruction_switch_cases,\n)\nfrom success_window import SuccessWindow\n'),
    ('run_episode signature', '    arm_reentry_capsule_window: int = 60,\n    post_success_observation: bool = False,\n) -> Dict[str, Any]:\n', '    arm_reentry_capsule_window: int = 60,\n    post_success_observation: bool = False,\n    success_delay: int = 0,\n    success_check_interval: int = 1,\n) -> Dict[str, Any]:\n'),
    ('run_episode validation', '    if replan_steps <= 0:\n        raise ValueError("replan_steps must be positive")\n', '    if replan_steps <= 0:\n        raise ValueError("replan_steps must be positive")\n    if success_delay < 0:\n        raise ValueError("success_delay must be nonnegative")\n    if success_check_interval < 1:\n        raise ValueError("success_check_interval must be positive")\n    if success_delay > 0 and post_success_observation:\n        raise ValueError(\n            "success_delay and post_success_observation are mutually exclusive: "\n            "the hold window owns the terminal decision, while the post-success "\n            "observation window runs to the budget to expose a late intervention"\n        )\n    if success_delay > 0 and (pfcr_bridge is not None or t0_anchor_handoff):\n        raise ValueError(\n            "success_delay is not defined for PFCR or T0-anchor handoff arms"\n        )\n    if success_delay > 0 and instruction_switch_monitor is not None:\n        raise ValueError(\n            "success_delay cannot follow an instruction switch: the effective "\n            "success predicate changes mid-episode"\n        )\n'),
    ('episode counters', '    success = False\n    sim_step = 0\n    done = False\n    episode_error = None\n', '    success = False\n    sim_step = 0\n    done = False\n    episode_error = None\n    success_window = (\n        SuccessWindow(success_delay, success_check_interval)\n        if success_delay > 0\n        else None\n    )\n    # Once the first success arms the hold window the episode may run past\n    # max_steps: the extra tail is verification budget, not a second attempt.\n    episode_step_limit = max_steps\n'),
    ('main loop condition', '        while sim_step < max_steps and not done and (\n            post_success_observation or not success\n        ):\n', '        while (\n            sim_step < episode_step_limit\n            and not done\n            and (\n                post_success_observation\n                or not success\n                or (\n                    success_window is not None\n                    and success_window.armed\n                    and not success_window.finished\n                )\n            )\n        ):\n'),
    ('action_count budget', '            action_count = min(len(chunk), replan_steps, max_steps - sim_step)\n', '            action_count = min(len(chunk), replan_steps, episode_step_limit - sim_step)\n'),
    ('success window step logic', '                if success:\n                    break\n                if force_pfcr_replan or runtime_replan is not None:\n                    break\n    except Exception as exc:\n', '                # Success hold window (--success-delay): observe the final\n                # effective predicate for this control step.  Once armed, the\n                # window owns the terminal decision.\n                if success_window is not None:\n                    window_event = success_window.observe(int(sim_step), bool(success))\n                    if window_event == "armed":\n                        episode_step_limit = int(sim_step) + success_window.delay\n                    if window_event in {"armed", "checkpoint", "stable", "lost"}:\n                        log_fn(\n                            "[SUCCESS_WINDOW] "\n                            + json.dumps(\n                                {\n                                    "event": window_event,\n                                    "sim_step": int(sim_step),\n                                    "success": bool(success),\n                                    "delay": success_window.delay,\n                                    "check_interval": success_window.check_interval,\n                                    "first_success_step": success_window.first_success_step,\n                                },\n                                ensure_ascii=False,\n                                separators=(",", ":"),\n                            )\n                        )\n                    if success_window.finished:\n                        success = success_window.passed\n                        break\n                window_active = bool(\n                    success_window is not None\n                    and success_window.armed\n                    and not success_window.finished\n                )\n                if success and not window_active:\n                    break\n                if force_pfcr_replan or runtime_replan is not None:\n                    break\n            if success_window is not None and success_window.finished:\n                break\n    except Exception as exc:\n'),
    ('result finalize', '    elapsed = time.time() - t0\n    result = {\n        "steps": sim_step,\n        "time_s": round(elapsed, 0),\n        "success": success,\n', '    if success_window is not None:\n        # Only a completed hold window can certify stable success; a censored\n        # window (environment done, runtime error) or a lost checkpoint cannot.\n        success = bool(success_window.passed)\n    first_hit_success = (\n        bool(success_window.armed) if success_window is not None else bool(success)\n    )\n    first_hit_step = (\n        success_window.first_success_step if success_window is not None else None\n    )\n    if success_window is None:\n        success_window_payload = {\n            "schema": "libero.success-window.v1",\n            "enabled": False,\n            "delay": 0,\n            "check_interval": success_check_interval,\n        }\n    else:\n        success_window_payload = success_window.to_dict()\n    elapsed = time.time() - t0\n    result = {\n        "steps": sim_step,\n        "time_s": round(elapsed, 0),\n        "success": success,\n        "first_hit_success": first_hit_success,\n        "first_hit_step": first_hit_step,\n        "success_window": success_window_payload,\n'),
    ('termination status', '    result["termination"] = {\n        "schema": "pfcr.termination.v1",\n        "status": (\n            "success"\n            if success\n            else "environment_done"\n            if terminated_by_environment_done\n            else "max_steps"\n        ),\n', '    result["termination"] = {\n        "schema": "pfcr.termination.v1",\n        "status": (\n            "success_stable"\n            if success_window is not None and success_window.passed\n            else "success_unstable"\n            if success_window is not None and success_window.failed\n            else "success_window_censored"\n            if success_window is not None and success_window.armed\n            else "success"\n            if success\n            else "environment_done"\n            if terminated_by_environment_done\n            else "max_steps"\n        ),\n'),
    ('results snapshot fields', '                        "success": value["success"],\n                        "recovery_cost": value.get("recovery_cost", {}),\n', '                        "success": value["success"],\n                        "first_hit_success": value.get("first_hit_success"),\n                        "first_hit_step": value.get("first_hit_step"),\n                        "success_window": value.get("success_window"),\n                        "recovery_cost": value.get("recovery_cost", {}),\n'),
    ('all_results fields (baseline)', '                        "kind": "baseline",\n                        "steps": result["steps"],\n                        "time_s": result["time_s"],\n                        "success": result["success"],\n                        "recovery_cost": result["recovery_cost"],\n', '                        "kind": "baseline",\n                        "steps": result["steps"],\n                        "time_s": result["time_s"],\n                        "success": result["success"],\n                        "first_hit_success": result.get("first_hit_success"),\n                        "first_hit_step": result.get("first_hit_step"),\n                        "success_window": result.get("success_window"),\n                        "recovery_cost": result["recovery_cost"],\n'),
    ('all_results fields (perturbation)', '                        "kind": "perturbation",\n                        "steps": result["steps"],\n                        "time_s": result["time_s"],\n                        "success": result["success"],\n                        "recovery_cost": result["recovery_cost"],\n', '                        "kind": "perturbation",\n                        "steps": result["steps"],\n                        "time_s": result["time_s"],\n                        "success": result["success"],\n                        "first_hit_success": result.get("first_hit_success"),\n                        "first_hit_step": result.get("first_hit_step"),\n                        "success_window": result.get("success_window"),\n                        "recovery_cost": result["recovery_cost"],\n'),
    ('baseline gate uses first hit', '                if args.require_successful_baseline and result["success"] is not True:\n', '                if args.require_successful_baseline and (\n                    result.get("first_hit_success", result["success"]) is not True\n                ):\n'),
    ('run_episode call', '                        post_success_observation=bool(args.post_success_window),\n', '                        post_success_observation=bool(args.post_success_window),\n                        success_delay=int(args.success_delay),\n                        success_check_interval=int(args.success_check_interval),\n'),
    ('ignore_done capability', '                        ignore_done=(\n                            pfcr_requires_post_success_observation(pfcr_settings)\n                            or bool(args.post_success_window)\n                        ),\n', '                        ignore_done=(\n                            pfcr_requires_post_success_observation(pfcr_settings)\n                            or bool(args.post_success_window)\n                            or bool(args.success_delay)\n                        ),\n'),
    ('CLI arguments', '    p.add_argument(\n        "--post-success-window",\n        action="store_true",\n        help=(\n            "keep stepping after the task predicate first becomes true.  Only "\n            "the A3 protection cases need it: they revoke one of two relations "\n            "that are both already complete, and without the window the episode "\n            "ends on the very step the trigger fires, so the intervention never "\n            "executes (INTERVENTION_NOT_EXECUTED)."\n        ),\n    )\n', '    p.add_argument(\n        "--post-success-window",\n        action="store_true",\n        help=(\n            "keep stepping after the task predicate first becomes true.  Only "\n            "the A3 protection cases need it: they revoke one of two relations "\n            "that are both already complete, and without the window the episode "\n            "ends on the very step the trigger fires, so the intervention never "\n            "executes (INTERVENTION_NOT_EXECUTED)."\n        ),\n    )\n    p.add_argument(\n        "--success-delay",\n        type=int,\n        default=0,\n        help=(\n            "after the task predicate first becomes true, require it to stay "\n            "true for this many additional control steps before reporting a "\n            "stable success; 0 keeps the legacy immediate stop.  The "\n            "verification tail is appended to --max-steps rather than taken "\n            "out of the active budget"\n        ),\n    )\n    p.add_argument(\n        "--success-check-interval",\n        type=int,\n        default=1,\n        help=(\n            "sample the task predicate every N steps inside the hold window; "\n            "1 (default) is the strict consecutive-step definition"\n        ),\n    )\n'),
    ('main validation', 'def main():\n    args = parse_args()\n    custom_bddl_paths: list[str] = []\n', 'def main():\n    args = parse_args()\n    if args.success_delay < 0:\n        raise SystemExit("--success-delay must be nonnegative")\n    if args.success_check_interval < 1:\n        raise SystemExit("--success-check-interval must be positive")\n    if args.success_delay and args.post_success_window:\n        raise SystemExit(\n            "--success-delay and --post-success-window are mutually exclusive"\n        )\n    custom_bddl_paths: list[str] = []\n'),
]


def replace_once(text: str, old: str, new: str, name: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(
            f"runtime source changed: {name!r} expected one anchor, found {count}. "
            "Rebase the success-delay overlay patch onto the new evaluator."
        )
    return text.replace(old, new, 1)


def patch_runner_source(text: str) -> str:
    """Apply every success-delay replacement to a runner source string."""

    for name, old, new in REPLACEMENTS:
        text = replace_once(text, old, new, name)
    return text


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge_capabilities(output: Path) -> None:
    """Advertise ``success_window`` in the overlay capability document."""

    path = output / "rollback-capabilities.json"
    document: dict[str, object] = {"protocol_version": 1, "capabilities": []}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            document.update(loaded)
    capabilities = document.get("capabilities")
    if not isinstance(capabilities, list):
        capabilities = []
    document["capabilities"] = sorted({str(item) for item in capabilities} | {CAPABILITY})
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def prepare(base: Path, output: Path) -> Path:
    """Copy ``base`` to ``output`` and install the success-delay patch."""

    base = base.resolve()
    output = output.resolve()
    runner = base / "tools/run_benchmark.py"
    if not runner.is_file():
        raise ValueError(f"base runtime has no tools/run_benchmark.py: {base}")
    if output.exists():
        raise ValueError(f"refusing to overwrite existing overlay: {output}")
    if not SUCCESS_WINDOW_SOURCE.is_file():
        raise ValueError(f"success window module missing: {SUCCESS_WINDOW_SOURCE}")
    shutil.copytree(
        base,
        output,
        symlinks=False,
        ignore=shutil.ignore_patterns("__pycache__", ".git", ".venv"),
    )
    runner_path = output / "tools/run_benchmark.py"
    runner_path.write_text(
        patch_runner_source(runner_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    shutil.copy2(SUCCESS_WINDOW_SOURCE, output / "success_window.py")
    merge_capabilities(output)
    (output / "success-delay-provenance.json").write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "base": str(base),
                "capability": CAPABILITY,
                "runner_sha256": _sha256(runner_path),
                "success_window_sha256": _sha256(output / "success_window.py"),
                "patch_count": len(REPLACEMENTS),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        required=True,
        help="existing evaluator overlay to copy (must contain tools/run_benchmark.py)",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="new overlay directory (must not exist)"
    )
    args = parser.parse_args(argv)
    try:
        output = prepare(args.base, args.output)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"success-delay overlay: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
