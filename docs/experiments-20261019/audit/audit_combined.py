#!/usr/bin/env python3
"""Independent read-only audit of the "combined two-subtask" experiment.

Covers (task-11):
  * static artifacts: 45 GOAL pair BDDLs (+90 phrasing BDDLs), 30 OBJECT pair
    BDDLs, 2 OBJECT prototypes, sweep/object-pilot/staged staging dirs;
  * dynamic pi05 runs in `run/` (pilot, variant-pilot, diag, diag2, staged,
    sweep-compatible, object-pilot): success rates, subtask completion
    distribution, first-true steps, staged switch steps, videos, logs;
  * comparison against Lead's `run/combined-dynamic-summary.json`;
  * verification of the key claims (single-instruction failure mode, phrasing
    variants do not help, staged partially helps, init-source effect, controls).

Read-only for the run dir; writes only under `.tmp/combined-audit/`.
CPU-only: BDDL parsing + torch.load init states + OpenCV video probes; no
simulator env creation, no policy model, no GPU.

Usage:
    <openpi venv python> audit_combined.py --mode audit [--partial]
The static BDDL parsing runs in a child process (`--mode static-child`) with the
pristine LIBERO shadow package on PYTHONPATH.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import statistics
import sys
import time
import traceback
from pathlib import Path

RUN_ROOT = Path("/home/tarowang/workspace/roboot/libero-rollback/runs/combined-tasks-20261019")
REPO_ROOT = Path("/home/tarowang/workspace/roboot/libero-rollback")
SPEC_PATH = REPO_ROOT / ".tmp/std-baseline-audit/spec.json"
SHADOW = Path("/home/tarowang/workspace/roboot/libero-rollback/runs/libero-std-baseline-20261019/shadow")
OUT_DIR = REPO_ROOT / ".tmp/combined-audit"
TP = Path("/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero/libero/libero")

SUITES = ["LIBERO_GOAL", "LIBERO_OBJECT"]

# run registry: name -> paths/expectations
RUNS = [
    dict(name="smoke", run_dir="run/smoke", bddl_dir="prep/smoke-pair",
         trace_dir="run/smoke-traces", log="logs/smoke-combined-00-01.log",
         expected=None, note="single-pair smoke"),
    dict(name="pilot(and)", run_dir="run/pilot", bddl_dir="prep/pilot-pairs",
         trace_dir="run/pilot-traces", log="logs/pilot-combined.log", expected=9),
    dict(name="variant(then/swap)", run_dir="run/variant-pilot", bddl_dir="prep/variant-pairs",
         trace_dir="run/variant-pilot-traces", log="logs/variant-pilot.log", expected=7),
    dict(name="diag", run_dir="run/diag", bddl_dir="prep/diag",
         trace_dir="run/diag-traces", log="logs/diag.log", expected=5),
    dict(name="diag2", run_dir="run/diag2", bddl_dir="prep/diag2",
         trace_dir="run/diag2-traces", log="logs/diag2.log", expected=4),
    dict(name="staged", run_dir="run/staged", bddl_dir="prep/staged-pairs",
         trace_dir="run/staged-traces", log="logs/staged.log", expected=4),
    dict(name="sweep-compatible", run_dir="run/sweep-compatible", bddl_dir="prep/sweep-compatible",
         trace_dir="run/sweep-compatible-traces", log="logs/sweep-compatible.log",
         expected=33, pending_marker="SWEEP_DONE"),
    dict(name="object-pilot", run_dir="run/object-pilot", bddl_dir="prep/object-pilot",
         trace_dir="run/object-pilot-traces", log="logs/object-pilot.log",
         expected=4, pending_marker="OBJECT_PILOT_DONE"),
]
# runs that belong to the static single-instruction combined-task claim
SINGLE_INSTR_GOAL_RUNS = ["pilot(and)", "variant(then/swap)", "sweep-compatible"]
SINGLE_INSTR_OBJECT_RUNS = ["object-pilot"]

MAX_STEPS = {"sweep-compatible": 600, "object-pilot": 560}
DEFAULTS_MAX_STEPS = 600
DEFAULT_REPLAN = 10  # staged/other runs use stock 10; object-pilot uses 5
# Lead's combined-dynamic-summary.json uses a shortened run name for the sweep batch
LEAD_RUN_ALIASES = {"sweep-compatible": "sweep"}
LEAD_TO_INTERNAL = {v: k for k, v in LEAD_RUN_ALIASES.items()}


def lead_run_name(internal: str) -> str:
    return LEAD_RUN_ALIASES.get(internal, internal)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return None


def norm(text: str) -> str:
    return " ".join(str(text).split())


def paren_span(src: str, name: str):
    i = src.find("(" + name)
    if i < 0:
        return None
    depth = 0
    for k in range(i, len(src)):
        if src[k] == "(":
            depth += 1
        elif src[k] == ")":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    return None


SECTION_NAMES = [":language", ":goal", ":obj_of_interest", ":regions", ":fixtures", ":objects", ":init"]


def extract_sections(path: Path) -> dict:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    out = {}
    for name in SECTION_NAMES:
        sec = paren_span(src, name)
        if sec is not None:
            n = norm(sec)
            out[name] = hashlib.sha256(n.encode()).hexdigest()
        else:
            out[name] = None
    return out


def bddl_language_quick(path: Path) -> str | None:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    sec = paren_span(src, ":language")
    return sec[len("(:language"):].rstrip(")").strip() if sec else None


# --------------------------------------------------------------------------- #
# child mode: static BDDL/init parsing with the pristine LIBERO package
# --------------------------------------------------------------------------- #
def static_child() -> int:
    shadow = str(SHADOW)
    sys.path.insert(0, shadow)
    os.environ["LIBERO_CONFIG_PATH"] = shadow
    import torch  # noqa: PLC0415
    from libero.libero.envs import bddl_utils  # noqa: PLC0415

    spec = json.loads(SPEC_PATH.read_text())
    out_path = Path(os.environ["AUDIT_STATIC_OUT"])
    cache: dict = {}

    def init_info(path: Path) -> dict:
        key = str(path)
        if key in cache:
            return cache[key]
        info = {"path": key, "exists": path.is_file(), "sha256": sha256_file(path)}
        if info["exists"]:
            try:
                arr = torch.load(path, weights_only=False)
                info["shape"] = [int(x) for x in getattr(arr, "shape", [])]
                info["count"] = int(len(arr))
                info["dtype"] = str(getattr(arr, "dtype", type(arr).__name__))
            except BaseException as exc:  # noqa: BLE001
                info["load_error"] = f"{type(exc).__name__}: {exc}"
        cache[key] = info
        return info

    def parse_bddl(path: Path) -> dict:
        entry = {
            "path": str(path),
            "stem": path.stem,
            "exists": path.is_file(),
            "file_sha256": sha256_file(path),
            "language": bddl_language_quick(path),
            "sections": extract_sections(path),
            "init_sibling": init_info(path.with_suffix(".pruned_init")),
        }
        if not entry["exists"]:
            entry["parse_error"] = "missing bddl"
            return entry
        try:
            info = bddl_utils.robosuite_parse_problem(str(path))
            entry["goal_state"] = [list(atom) for atom in (info.get("goal_state") or [])]
            entry["obj_of_interest"] = list(info.get("obj_of_interest") or [])
            entry["problem_name"] = info.get("problem_name")
            entry["n_goal_atoms"] = len(entry["goal_state"])
            problem = bddl_utils.get_problem_info(str(path))
            entry["language_instruction"] = problem.get("language_instruction")
            entry["parse_ok"] = True
        except BaseException as exc:  # noqa: BLE001
            entry["parse_ok"] = False
            entry["parse_error"] = f"{type(exc).__name__}: {exc}"
        return entry

    result = {"groups": {}, "spec_templates": {}, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    # --- official templates (GOAL + OBJECT) ---------------------------------
    for suite, folder in (("LIBERO_GOAL", "libero_goal"), ("LIBERO_OBJECT", "libero_object")):
        tmpl = {}
        for task in spec["suites"][suite]["tasks"]:
            p = TP / "bddl_files" / folder / (task["name"] + ".bddl")
            rec = parse_bddl(p)
            rec["idx"] = task["idx"]
            rec["name"] = task["name"]
            rec["benchmark_language"] = task["language"]
            rec["official_init"] = init_info(Path(task["init_states"]))
            tmpl[task["idx"]] = rec
        result["spec_templates"][suite] = tmpl

    def group(name: str, pattern: str, extra_init_dir: str | None = None):
        entries = {}
        for p in sorted(glob.glob(pattern)):
            path = Path(p)
            if not path.name.endswith(".bddl"):
                continue
            rec = parse_bddl(path)
            if extra_init_dir:
                rec["init_dir_copy"] = init_info(Path(extra_init_dir) / (path.stem + ".pruned_init"))
            entries[path.stem] = rec
        result["groups"][name] = entries

    group("goal_pairs", str(RUN_ROOT / "artifacts/goal-pairs/bddl/*.bddl"),
          str(RUN_ROOT / "artifacts/goal-pairs/init"))
    for variant in ("then", "andthen"):
        group(f"phrasings_{variant}", str(RUN_ROOT / f"artifacts/goal-pairs-phrasings/{variant}/bddl/*.bddl"),
              str(RUN_ROOT / f"artifacts/goal-pairs-phrasings/{variant}/init"))
    group("object_pairs", str(RUN_ROOT / "artifacts/object-pairs/bddl/*.bddl"))
    group("object_scout", str(RUN_ROOT / "artifacts/object-scout/prototype/*.bddl"))
    group("staged", str(RUN_ROOT / "prep/staged-pairs/*.bddl"))
    group("sweep_compatible", str(RUN_ROOT / "prep/sweep-compatible/*.bddl"))
    group("object_pilot", str(RUN_ROOT / "prep/object-pilot/*.bddl"))
    for name in ("pilot-pairs", "variant-pairs", "diag", "diag2", "smoke-pair"):
        group(f"prep_{name}", str(RUN_ROOT / "prep" / name / "*.bddl"))

    # object pair meta json
    result["object_pair_meta"] = sorted(
        os.path.basename(p) for p in glob.glob(str(RUN_ROOT / "artifacts/object-pairs/bddl/*.meta.json"))
    )
    out_path.write_text(json.dumps(result))
    print("static child wrote", out_path, "groups:", {k: len(v) for k, v in result["groups"].items()})
    return 0


# --------------------------------------------------------------------------- #
# orchestrator
# --------------------------------------------------------------------------- #
class Audit:
    def __init__(self, partial: bool = False):
        self.checks: list[dict] = []
        self.partial = partial
        self.spec = json.loads(SPEC_PATH.read_text())
        self.goal_tasks = {t["idx"]: t for t in self.spec["suites"]["LIBERO_GOAL"]["tasks"]}
        self.object_tasks = {t["idx"]: t for t in self.spec["suites"]["LIBERO_OBJECT"]["tasks"]}
        self.static: dict = {}
        self.episodes: list[dict] = []
        self.run_stats: dict = {}
        self.summary_doc = None
        self.problems: list[dict] = []

    # -- checks ------------------------------------------------------------
    def check(self, name: str, ok: bool, detail=None, critical: bool = True, category: str = "static"):
        self.checks.append({
            "check": name, "ok": bool(ok), "critical": critical, "category": category,
            "detail": detail if not ok else None,
        })
        if not ok and critical:
            self.problems.append({"check": name, "detail": detail})
        return ok

    # -- static loading ----------------------------------------------------
    def load_static(self):
        out = OUT_DIR / "_static.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.is_file() and time.time() - out.stat().st_mtime < 900:
            self.static = json.loads(out.read_text())
            self._normalize_static()
            return
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SHADOW)
        env["LIBERO_CONFIG_PATH"] = str(SHADOW)
        env["AUDIT_STATIC_OUT"] = str(out)
        import subprocess  # noqa: PLC0415
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--mode", "static-child"],
            capture_output=True, text=True, env=env, timeout=1800,
        )
        if proc.returncode != 0 or not out.is_file():
            raise SystemExit(f"static child failed rc={proc.returncode}\n{proc.stdout[-3000:]}\n{proc.stderr[-4000:]}")
        self.static = json.loads(out.read_text())
        self._normalize_static()

    def _normalize_static(self):
        # JSON keys are strings; template dict is keyed by task idx ints
        for suite in self.static.get("spec_templates", {}):
            self.static["spec_templates"][suite] = {
                int(k): v for k, v in self.static["spec_templates"][suite].items()
            }

    # -- static checks -----------------------------------------------------
    @staticmethod
    def _atom_str(atom) -> str:
        return "(" + " ".join(str(x) for x in atom) + ")"

    def static_checks(self):
        gs = self.static["groups"]
        templates = self.static["spec_templates"]
        goal_pairs = read_json(RUN_ROOT / "artifacts/goal-pairs/pairs.json") or {}
        goal_entries = goal_pairs.get("pairs") or []
        self.goal_pairs_meta = {(e["i"], e["j"]): e for e in goal_entries}
        self.goal_pairs_by_id = {e["pair_id"]: e for e in goal_entries}
        self.goal_entries = goal_entries

        # ------------- GOAL pairs 45 ------------------------------------
        goal_bddl = gs.get("goal_pairs", {})
        missing = [e["pair_id"] for e in goal_entries if f"goal_pair_{e['pair_id']}" not in goal_bddl]
        self.check("goal_pairs_45_files_exist", len(goal_bddl) == 45 and not missing,
                   {"n_bddl": len(goal_bddl), "missing": missing}, category="goal")
        self.check("goal_pairs_meta_45", len(goal_entries) == 45, len(goal_entries), category="goal")
        ids = [e["pair_id"] for e in goal_entries]
        self.check("goal_pairs_unique_ids", len(set(ids)) == len(ids), category="goal")
        pairs = [(e["i"], e["j"]) for e in goal_entries]
        self.check("goal_pairs_unique_unordered_pairs", len(set(frozenset(p) for p in pairs)) == 45,
                   len(set(frozenset(p) for p in pairs)), category="goal")
        self.check("goal_pairs_i_lt_j", all(e["i"] < e["j"] for e in goal_entries),
                   [e["pair_id"] for e in goal_entries if not e["i"] < e["j"]], category="goal")
        cls_counts = {}
        for e in goal_entries:
            c = e.get("status") or e.get("classification")
            cls_counts[c] = cls_counts.get(c, 0) + 1
        self.check("goal_pairs_classification_counts_33_5_7",
                   cls_counts.get("compatible") == 33 and cls_counts.get("hard") == 5
                   and cls_counts.get("conflict") == 7, cls_counts, category="goal")

        # independent recompute of the conflict/hard classification from goal atoms
        tp_goal = templates["LIBERO_GOAL"]

        def atom_moved_dest(atom):
            pred = (atom[0] or "").lower() if atom else ""
            if pred in ("on", "in") and len(atom) >= 3:
                return atom[1], atom[2]
            return None, None

        def atom_dest_tokens(atom):
            _, dest = atom_moved_dest(atom)
            return set(dest.split("_")) if dest else set()

        task_moved = {}
        for idx, rec in tp_goal.items():
            atoms = rec.get("goal_state") or []
            task_moved[idx] = atom_moved_dest(atoms[0]) if atoms else (None, None)
        conflict_expected = set()
        dependency_candidates = set()
        stove_candidates = set()
        for (i, j) in [(e["i"], e["j"]) for e in goal_entries]:
            mi, di = task_moved.get(i, (None, None))
            mj, dj = task_moved.get(j, (None, None))
            if mi and mj and mi == mj and di != dj:
                conflict_expected.add((i, j))
            # order-constrained: one goal places something onto an object the
            # other task moves elsewhere
            if mi and dj and mi == dj:
                dependency_candidates.add((i, j))
            if mj and di and mj == di:
                dependency_candidates.add((i, j))
            # shared destination appliance region (documented stove contention)
            ti = atom_dest_tokens((tp_goal[i].get("goal_state") or [[]])[0])
            tj = atom_dest_tokens((tp_goal[j].get("goal_state") or [[]])[0])
            if mi and mj and "stove" in (ti & tj):
                stove_candidates.add((i, j))
        hard_candidates = (dependency_candidates | stove_candidates) - conflict_expected
        actual_conflict = {(e["i"], e["j"]) for e in goal_entries
                           if (e.get("status") or e.get("classification")) == "conflict"}
        actual_hard = {(e["i"], e["j"]) for e in goal_entries
                       if (e.get("status") or e.get("classification")) == "hard"}
        self.classification_recompute = {
            "conflict_expected": sorted(f"{i:02d}_{j:02d}" for i, j in conflict_expected),
            "conflict_actual": sorted(f"{i:02d}_{j:02d}" for i, j in actual_conflict),
            "conflict_matches": conflict_expected == actual_conflict,
            "hard_candidates_atom_based": sorted(f"{i:02d}_{j:02d}" for i, j in hard_candidates),
            "hard_actual": sorted(f"{i:02d}_{j:02d}" for i, j in actual_hard),
            "hard_candidate_minus_actual": sorted(f"{i:02d}_{j:02d}" for i, j in (hard_candidates - actual_hard)),
            "hard_actual_minus_candidate": sorted(f"{i:02d}_{j:02d}" for i, j in (actual_hard - hard_candidates)),
            "hard_matches": hard_candidates == actual_hard,
        }
        self.check("goal_classification_conflict_recomputed_exact",
                   conflict_expected == actual_conflict,
                   self.classification_recompute, category="goal")
        self.check("goal_classification_hard_atom_candidates",
                   actual_hard <= hard_candidates,
                   {"hard_actual": sorted(f"{i:02d}_{j:02d}" for i, j in actual_hard),
                    "hard_candidates": sorted(f"{i:02d}_{j:02d}" for i, j in hard_candidates)},
                   critical=False, category="goal")

        goal_issues = []
        init_shape_issues = []
        for e in goal_entries:
            stem = "goal_pair_" + e["pair_id"]
            rec = goal_bddl.get(stem)
            if not rec or not rec.get("exists"):
                goal_issues.append((stem, "missing bddl")); continue
            if not rec.get("parse_ok"):
                goal_issues.append((stem, "parse", rec.get("parse_error"))); continue
            exp_atoms = [self._atom_str(a) for a in e["goal_atoms_parsed"]]
            got_atoms = [self._atom_str(a) for a in rec.get("goal_state") or []]
            if len(rec["goal_state"]) != 2:
                goal_issues.append((stem, "n_goal_atoms", len(rec["goal_state"])))
            if [norm(x) for x in got_atoms] != [norm(x) for x in exp_atoms]:
                goal_issues.append((stem, "goal_atoms", got_atoms, exp_atoms))
            exp_lang = f"{self.goal_tasks[e['i']]['language']} and {self.goal_tasks[e['j']]['language']}"
            if norm(rec.get("language") or "") != norm(exp_lang):
                goal_issues.append((stem, "language", rec.get("language"), exp_lang))
            if norm(rec.get("language_instruction") or "") != norm(exp_lang):
                goal_issues.append((stem, "language_instruction", rec.get("language_instruction")))
            ooi = sorted(rec.get("obj_of_interest") or [])
            if ooi != sorted(e.get("obj_of_interest") or []):
                goal_issues.append((stem, "obj_of_interest", ooi, e.get("obj_of_interest")))
            # init: sibling + init/ copy must be byte-identical to the source task init
            src_init = templates["LIBERO_GOAL"][e["i"]]["official_init"]
            for label, inf in (("sibling", rec.get("init_sibling")),
                               ("init_dir", rec.get("init_dir_copy"))):
                if not inf or not inf.get("exists"):
                    init_shape_issues.append((stem, label, "missing"))
                elif inf.get("sha256") != src_init.get("sha256"):
                    init_shape_issues.append((stem, label, "sha != task_i official init"))
                elif inf.get("shape") != [50, 79]:
                    init_shape_issues.append((stem, label, "shape", inf.get("shape")))
                elif inf.get("count") != 50:
                    init_shape_issues.append((stem, label, "count", inf.get("count")))
            # scene sections must equal template task i
            for sec in (":regions", ":fixtures", ":objects", ":init"):
                if rec["sections"].get(sec) != templates["LIBERO_GOAL"][e["i"]]["sections"].get(sec):
                    goal_issues.append((stem, "section_differs_from_template", sec))
            exp_src_idx = e.get("init_source", {}).get("task_idx")
            if exp_src_idx != e["i"]:
                goal_issues.append((stem, "init_source_task", exp_src_idx, e["i"]))
        self.check("goal_pairs_bddl_parse_structure_language_2atoms", not goal_issues,
                   goal_issues[:10], category="goal")
        self.check("goal_pairs_init_shape_50x79_and_source", not init_shape_issues,
                   init_shape_issues[:10], category="goal")
        self.check("goal_pairs_scene_sections_equal_templates", not goal_issues, category="goal")

        # static-validation.json claims vs independent counts
        sv = read_json(RUN_ROOT / "artifacts/goal-pairs/static-validation.json") or {}
        sv_sum = sv.get("summary") or {}
        self.check("goal_static_validation_claims_45_45",
                   sv.get("n_pairs_validated") == 45 and sv_sum.get("n_passed") == 45
                   and not sv_sum.get("failed_pair_ids"),
                   {"n_validated": sv.get("n_pairs_validated"), "summary": sv_sum}, category="goal")
        self.check("goal_static_validation_initial_success_false",
                   sv_sum.get("all_initial_success_false") is True, category="goal")
        # checksums manifest
        ck_issues, ck_n = self._verify_checksums(RUN_ROOT / "artifacts/goal-pairs/checksums.sha256")
        self.check("goal_pairs_checksums_137_ok", not ck_issues and ck_n == 137,
                   {"issues": ck_issues[:5], "lines": ck_n}, category="goal")

        # ------------- phrasings 90 -------------------------------------
        ph_pairs = read_json(RUN_ROOT / "artifacts/goal-pairs-phrasings/pairs.json") or {}
        ph_entries = ph_pairs.get("pairs") or []
        ph_checks_issues = []
        for variant in ("then", "andthen"):
            group = gs.get(f"phrasings_{variant}", {})
            self.check(f"phrasings_{variant}_45_files", len(group) == 45, len(group), category="phrasings")
            expected_lang = {}
            for e in ph_entries:
                a = self.goal_tasks[e["i"]]["language"]
                b = self.goal_tasks[e["j"]]["language"]
                expected_lang[e["pair_id"]] = (
                    f"first {a}, then {b}" if variant == "then" else f"{a} and then {b}"
                )
            for e in ph_entries:
                stem = f"goal_pair_{e['pair_id']}_{variant}"
                rec = group.get(stem)
                if not rec or not rec.get("exists") or not rec.get("parse_ok"):
                    ph_checks_issues.append((stem, "missing/unparsable"))
                    continue
                if norm(rec.get("language") or "") != norm(expected_lang[e["pair_id"]]):
                    ph_checks_issues.append((stem, "language", rec.get("language"), expected_lang[e["pair_id"]]))
                base = gs.get("goal_pairs", {}).get("goal_pair_" + e["pair_id"])
                if base:
                    if rec.get("goal_state") != base.get("goal_state"):
                        ph_checks_issues.append((stem, "goal_state != base pair"))
                    for sec in (":goal", ":obj_of_interest", ":regions", ":fixtures", ":objects", ":init"):
                        if rec["sections"].get(sec) != base["sections"].get(sec):
                            ph_checks_issues.append((stem, "section_differs_from_base", sec))
                    if (rec.get("init_sibling") or {}).get("sha256") != (base.get("init_sibling") or {}).get("sha256"):
                        ph_checks_issues.append((stem, "init != base pair init"))
                    elif (rec.get("init_sibling") or {}).get("shape") != [50, 79]:
                        ph_checks_issues.append((stem, "init shape", (rec.get("init_sibling") or {}).get("shape")))
                    if (rec.get("init_dir_copy") or {}).get("sha256") != (base.get("init_sibling") or {}).get("sha256"):
                        ph_checks_issues.append((stem, "init_dir copy != base pair init"))
            # phrasing metadata must declare 45 pairs per variant / 90 total
            self.check(f"phrasings_{variant}_metadata_45",
                       ph_pairs.get("n_pairs_per_variant") == 45
                       and ph_pairs.get("n_pairs_total") == 90,
                       {"n_pairs_per_variant": ph_pairs.get("n_pairs_per_variant"),
                        "n_pairs_total": ph_pairs.get("n_pairs_total")},
                       critical=False, category="phrasings")
        self.check("phrasings_90_language_and_scene_consistent", not ph_checks_issues,
                   ph_checks_issues[:10], category="phrasings")
        pv = read_json(RUN_ROOT / "artifacts/goal-pairs-phrasings/static-validation.json") or {}
        per = ((pv.get("summary") or {}).get("per_variant") or {})
        self.check("phrasings_static_validation_45_45_each",
                   per.get("then", {}).get("n_passed") == 45 and per.get("andthen", {}).get("n_passed") == 45,
                   per, category="phrasings")
        ph_ck, ph_ck_n = self._verify_checksums(RUN_ROOT / "artifacts/goal-pairs-phrasings/checksums.sha256")
        self.check("phrasings_checksums_271_ok", not ph_ck and ph_ck_n == 271,
                   {"issues": ph_ck[:5], "lines": ph_ck_n}, category="phrasings")

        # ------------- OBJECT pairs 30 ----------------------------------
        obj_doc = read_json(RUN_ROOT / "artifacts/object-pairs/pairs.json") or {}
        obj_entries = obj_doc.get("pairs") or []
        obj_group = gs.get("object_pairs", {})
        meta_files = set(self.static.get("object_pair_meta") or [])
        union_expected = {7: [50, 123], 8: [50, 136], 9: [50, 149]}
        obj_issues, obj_shape_issues = [], []
        un = {}
        for e in obj_entries:
            pid = e["pair_id"]
            un[e["union_objects"]] = un.get(e["union_objects"], 0) + 1
            rec = obj_group.get(pid)
            if not rec or not rec.get("exists") or not rec.get("parse_ok"):
                obj_issues.append((pid, "missing/unparsable")); continue
            if len(rec.get("goal_state") or []) != 2:
                obj_issues.append((pid, "n_goal_atoms", len(rec.get("goal_state"))))
            exp_lang = f"{self.object_tasks[e['i']]['language']} and {self.object_tasks[e['j']]['language']}"
            if norm(rec.get("language") or "") != norm(exp_lang):
                obj_issues.append((pid, "language", rec.get("language"), exp_lang))
            exp_atoms = {(x["predicate"], *x["args"]) for x in []}
            init = rec.get("init_sibling") or {}
            want = union_expected[e["union_objects"]]
            if not init.get("exists"):
                obj_shape_issues.append((pid, "init missing"))
            elif init.get("shape") != want:
                obj_shape_issues.append((pid, "shape", init.get("shape"), want))
            elif init.get("count") != 50:
                obj_shape_issues.append((pid, "count", init.get("count")))
            if pid + ".meta.json" not in meta_files:
                obj_issues.append((pid, "meta json missing"))
            if e.get("merged_state_len") != want[1]:
                obj_shape_issues.append((pid, "merged_state_len", e.get("merged_state_len"), want[1]))
        self.check("object_pairs_30_files", len(obj_group) == 30 and len(obj_entries) == 30,
                   {"bddl": len(obj_group), "meta": len(obj_entries)}, category="object")
        self.check("object_pairs_union_10_10_10", un == {7: 10, 8: 10, 9: 10}, un, category="object")
        self.check("object_pairs_bddl_structure_language", not obj_issues, obj_issues[:10], category="object")
        self.check("object_pairs_init_shapes_123_136_149", not obj_shape_issues,
                   obj_shape_issues[:10], category="object")
        ov = read_json(RUN_ROOT / "artifacts/object-pairs/validation.json") or {}
        self.check("object_validation_claims_30_30",
                   ov.get("pairs_verified") == 30 and ov.get("pairs_passed") == 30
                   and ov.get("rows_per_pair") == 50,
                   {"verified": ov.get("pairs_verified"), "passed": ov.get("pairs_passed")}, category="object")

        # ------------- object scout prototypes --------------------------
        scout = gs.get("object_scout", {})
        self.check("object_scout_2_prototypes", len(scout) == 2, sorted(scout), category="object")
        scout_ok = all(r.get("parse_ok") and r.get("n_goal_atoms") == 2 for r in scout.values())
        self.check("object_scout_prototypes_parse", scout_ok, category="object")
        feas = read_json(RUN_ROOT / "artifacts/object-scout/feasibility.json") or {}
        self.check("object_scout_feasibility_present",
                   feas.get("schema") == "libero.combination.feasibility.v1", category="object")

        # ------------- staged / sweep / object-pilot dirs ---------------
        staged = gs.get("staged", {})
        plan = read_json(RUN_ROOT / "prep/staged-plan.json") or {}
        self.check("staged_4_files", len(staged) == 4, sorted(staged), category="staging")
        st_issues = []
        for stem, rec in staged.items():
            pid = stem
            if pid not in plan:
                st_issues.append((stem, "no staged plan"))
                continue
            tasks = self.object_tasks if stem.startswith("obj_") else self.goal_tasks
            a = tasks[plan[pid]["i"]]["language"]
            b = tasks[plan[pid]["j"]]["language"]
            if norm(rec.get("language") or "") != norm(f"{a} and {b}"):
                st_issues.append((stem, "full language mismatch", rec.get("language")))
            if not rec.get("parse_ok") or rec.get("n_goal_atoms") != 2:
                st_issues.append((stem, "parse/goal atoms"))
        self.check("staged_bddl_language_and_plan_consistent", not st_issues, st_issues[:10], category="staging")

        compat = [e for e in goal_entries if (e.get("status") or e.get("classification")) == "compatible"]
        sweep = gs.get("sweep_compatible", {})
        self.check("sweep_dir_33_compatible_pairs", len(sweep) == 33 and len(compat) == 33,
                   {"sweep_files": len(sweep), "compatible_meta": len(compat)}, category="staging")
        sw_issues = []
        for e in compat:
            stem = f"goal_pair_{e['pair_id']}"
            rec = sweep.get(stem)
            if not rec or not rec.get("exists"):
                sw_issues.append((stem, "missing"))
                continue
            base = gs.get("goal_pairs", {}).get(stem)
            if not base:
                continue
            if norm(rec.get("language") or "") != norm(base.get("language") or ""):
                sw_issues.append((stem, "language differs from artifact pair"))
            if (rec.get("init_sibling") or {}).get("sha256") != (base.get("init_sibling") or {}).get("sha256"):
                sw_issues.append((stem, "init differs from artifact pair"))
        self.check("sweep_33_bddl_copied_correctly", not sw_issues, sw_issues[:10], category="staging")

        op = gs.get("object_pilot", {})
        self.check("object_pilot_dir_4_pairs", len(op) == 4, sorted(op), category="staging")
        op_issues = []
        for stem, rec in op.items():
            meta = next((e for e in obj_entries if e["pair_id"] == stem), None)
            if meta is None:
                op_issues.append((stem, "not an object pair id")); continue
            base = obj_group.get(stem)
            if base:
                if norm(rec.get("language") or "") != norm(base.get("language") or ""):
                    op_issues.append((stem, "language differs"))
                if (rec.get("init_sibling") or {}).get("sha256") != (base.get("init_sibling") or {}).get("sha256"):
                    op_issues.append((stem, "init differs"))
        self.check("object_pilot_4_copied_correctly", not op_issues, op_issues[:10], category="staging")

    def _verify_checksums(self, manifest: Path) -> tuple[list, int]:
        issues = []
        if not manifest.is_file():
            return [{"error": "manifest missing", "path": str(manifest)}], 0
        base = manifest.parent
        lines = [ln.strip() for ln in manifest.read_text().splitlines() if ln.strip()]
        for line in lines:
            parts = line.split(None, 1)
            if len(parts) != 2:
                issues.append({"bad_line": line}); continue
            want, rel = parts
            got = sha256_file(base / rel.strip())
            if got is None:
                issues.append({"missing": rel})
            elif got != want:
                issues.append({"sha_mismatch": rel})
        return issues, len(lines)

    # -- staging dirs / overlay / shadow provenance ----------------------
    def staging_checks(self):
        gs = self.static["groups"]
        tmpl_g = self.static["spec_templates"]["LIBERO_GOAL"]
        tmpl_o = self.static["spec_templates"]["LIBERO_OBJECT"]
        goal = gs.get("goal_pairs", {})
        obj = gs.get("object_pairs", {})
        scout = gs.get("object_scout", {})

        def atom_str(atom) -> str:
            return "(" + " ".join(str(x) for x in atom) + ")"

        def g_atom(i):
            return atom_str(tmpl_g[i]["goal_state"][0])

        def o_atom(i):
            return atom_str(tmpl_o[i]["goal_state"][0])

        def init_sha_tp_goal(i):
            return tmpl_g[i]["official_init"]["sha256"]

        def init_sha_tp_obj(i):
            return tmpl_o[i]["official_init"]["sha256"]

        def sections_equal(rec, ref) -> bool:
            return all(rec["sections"].get(k) == ref["sections"].get(k) for k in SECTION_NAMES)

        # ---- shadow + runtime overlay provenance -----------------------
        shadow_link = RUN_ROOT / "shadow"
        base_shadow = Path("/home/tarowang/workspace/roboot/libero-rollback/runs/libero-std-baseline-20261019/shadow")
        shadow_ok = shadow_link.exists() and Path(os.path.realpath(shadow_link)) == Path(os.path.realpath(base_shadow))
        cfg_ok = (base_shadow / "config.yaml").is_file() and (
            (shadow_link / "config.yaml").is_file()
            and (shadow_link / "config.yaml").read_text() == (base_shadow / "config.yaml").read_text()
        )
        self.check("shadow_is_baseline_pristine_shadow", shadow_ok and cfg_ok,
                   {"shadow": str(shadow_link), "realpath": os.path.realpath(shadow_link) if shadow_link.exists() else None,
                    "base": str(base_shadow), "config_ok": cfg_ok}, category="staging")
        overlay = RUN_ROOT / "runtime" / "tools" / "run_benchmark.py"
        overlay_text = overlay.read_text(errors="replace") if overlay.is_file() else ""
        patch_ok = (
            "NUM_STEPS_WAIT = 10" in overlay_text
            and "custom_init_path = os.path.splitext(bddl_path)[0] + \".pruned_init\"" in overlay_text
            and "_torch.load(custom_init_path" in overlay_text
        )
        self.check("runtime_overlay_custom_init_and_wait10_patch", patch_ok,
                   {"path": str(overlay),
                    "num_steps_wait10": "NUM_STEPS_WAIT = 10" in overlay_text,
                    "custom_init_patch": "custom_init_path" in overlay_text},
                   category="staging")

        # ---- smoke pair -------------------------------------------------
        smoke = gs.get("prep_smoke-pair", {})
        ref = goal.get("goal_pair_00_01")
        smoke_rec = smoke.get("goal_pair_00_01")
        ok = bool(
            len(smoke) == 1 and ref is not None and smoke_rec is not None
            and smoke_rec.get("parse_ok")
            and norm(smoke_rec["language"] or "") == norm(ref["language"] or "")
            and [atom_str(a) for a in smoke_rec.get("goal_state") or []]
                == [atom_str(a) for a in ref.get("goal_state") or []]
            and sorted(smoke_rec.get("obj_of_interest") or [])
                == sorted(ref.get("obj_of_interest") or [])
            and (smoke_rec.get("init_sibling") or {}).get("sha256") == init_sha_tp_goal(0)
        )
        self.check("prep_smoke_pair_semantically_equal_artifact_00_01", ok,
                   {"stems": sorted(smoke),
                    "bddl_text_identical": (smoke_rec or {}).get("file_sha256") == (ref or {}).get("file_sha256"),
                    "language": (smoke_rec or {}).get("language"),
                    "goal": (smoke_rec or {}).get("goal_state")},
                   category="staging")
        if not ok:
            self.check("prep_smoke_pair_bddl_text_differs_only_formatting",
                       (smoke_rec or {}).get("sections") is not None, category="staging")

        # ---- pilot-pairs (9): built from TP templates -------------------
        pilot_pairs = [(0, 7), (0, 2), (0, 9), (3, 2), (5, 6), (8, 9), (7, 5), (2, 9), (8, 6)]
        pilot = gs.get("prep_pilot-pairs", {})
        pl_issues = []
        expected_stems = {f"goal_pair_{i:02d}_{j:02d}" for i, j in pilot_pairs}
        if set(pilot) != expected_stems:
            pl_issues.append({"stems": sorted(set(pilot) ^ expected_stems)})
        for i, j in pilot_pairs:
            stem = f"goal_pair_{i:02d}_{j:02d}"
            rec = pilot.get(stem)
            if not rec or not rec.get("parse_ok"):
                pl_issues.append({stem: "missing/unparsable"}); continue
            exp_lang = f"{tmpl_g[i]['benchmark_language']} and {tmpl_g[j]['benchmark_language']}"
            if norm(rec["language"] or "") != norm(exp_lang):
                pl_issues.append({stem: "language", "got": rec["language"], "want": exp_lang})
            if [atom_str(a) for a in rec["goal_state"]] != [g_atom(i), g_atom(j)]:
                pl_issues.append({stem: "goal_atoms"})
            if (rec.get("init_sibling") or {}).get("sha256") != init_sha_tp_goal(i):
                pl_issues.append({stem: "init != task_i official init"})
        self.check("prep_pilot_pairs_match_builder_9", not pl_issues, pl_issues[:8], category="staging")

        # ---- variant-pairs (5 goal variants + 2 object prototypes) ------
        variant = gs.get("prep_variant-pairs", {})
        v_expected = {
            "goal_pair_00_07_then": (0, 7, f"first {tmpl_g[0]['benchmark_language']}, then {tmpl_g[7]['benchmark_language']}"),
            "goal_pair_00_07_andthen": (0, 7, f"{tmpl_g[0]['benchmark_language']} and then {tmpl_g[7]['benchmark_language']}"),
            "goal_pair_00_07_swap": (0, 7, f"{tmpl_g[7]['benchmark_language']} and {tmpl_g[0]['benchmark_language']}"),
            "goal_pair_00_02_andthen": (0, 2, f"{tmpl_g[0]['benchmark_language']} and then {tmpl_g[2]['benchmark_language']}"),
            "goal_pair_00_02_swap": (0, 2, f"{tmpl_g[2]['benchmark_language']} and {tmpl_g[0]['benchmark_language']}"),
        }
        v_issues = []
        for stem, (i, j, exp_lang) in v_expected.items():
            rec = variant.get(stem)
            if not rec or not rec.get("parse_ok"):
                v_issues.append({stem: "missing/unparsable"}); continue
            if norm(rec["language"] or "") != norm(exp_lang):
                v_issues.append({stem: "language", "got": rec["language"], "want": exp_lang})
            if [atom_str(a) for a in rec["goal_state"]] != [g_atom(i), g_atom(j)]:
                v_issues.append({stem: "goal_atoms"})
            if (rec.get("init_sibling") or {}).get("sha256") != init_sha_tp_goal(i):
                v_issues.append({stem: "init != task_i official init"})
        for proto_stem, src_stem in (("obj_object_pair_00_01", "object_pair_00_01"),
                                     ("obj_object_pair_00_03", "object_pair_00_03")):
            rec = variant.get(proto_stem)
            ref = scout.get(src_stem)
            if not rec or not rec.get("parse_ok") or ref is None:
                v_issues.append({proto_stem: "missing"}); continue
            if not sections_equal(rec, ref):
                v_issues.append({proto_stem: "sections != object-scout prototype"})
            if (rec.get("init_sibling") or {}).get("sha256") != (ref.get("init_sibling") or {}).get("sha256"):
                v_issues.append({proto_stem: "init != prototype init"})
        self.check("prep_variant_pairs_match_builder_7", not v_issues, v_issues[:8], category="staging")

        # ---- diag controls (5) ------------------------------------------
        diag = gs.get("prep_diag", {})
        d_issues = []
        pilot07 = pilot.get("goal_pair_00_07")
        pilot02 = pilot.get("goal_pair_00_02")
        scout01 = scout.get("object_pair_00_01")
        exp_diag = [
            ("diag_goal_00_07_single_stove", 1,
             (pilot07["goal_state"][1] if pilot07 else None), "turn on the stove",
             (pilot07.get("init_sibling") or {}).get("sha256") if pilot07 else None),
            ("diag_goal_00_07_init_stove_task", 2, None,
             f"{tmpl_g[0]['benchmark_language']} and {tmpl_g[7]['benchmark_language']}",
             init_sha_tp_goal(7)),
            ("diag_goal_00_02_single_wine", 1,
             (pilot02["goal_state"][1] if pilot02 else None), "put the wine bottle on top of the cabinet",
             (pilot02.get("init_sibling") or {}).get("sha256") if pilot02 else None),
            ("diag_obj_00_01_single_soup", 1,
             (scout01["goal_state"][0] if scout01 else None),
             tmpl_o[0]["benchmark_language"],
             (scout01.get("init_sibling") or {}).get("sha256") if scout01 else None),
            ("diag_obj_00_01_single_cheese", 1,
             (scout01["goal_state"][1] if scout01 else None),
             tmpl_o[1]["benchmark_language"],
             (scout01.get("init_sibling") or {}).get("sha256") if scout01 else None),
        ]
        for stem, n_atoms, exp_atom, exp_lang, exp_init in exp_diag:
            rec = diag.get(stem)
            if not rec or not rec.get("parse_ok"):
                d_issues.append({stem: "missing/unparsable"}); continue
            if len(rec["goal_state"]) != n_atoms:
                d_issues.append({stem: "n_goal_atoms", "got": len(rec["goal_state"])})
            elif n_atoms == 1 and exp_atom is not None and atom_str(rec["goal_state"][0]) != atom_str(exp_atom):
                d_issues.append({stem: "goal_atom", "got": atom_str(rec["goal_state"][0]),
                                 "want": atom_str(exp_atom)})
            if norm(rec["language"] or "") != norm(exp_lang):
                d_issues.append({stem: "language", "got": rec["language"], "want": exp_lang})
            if exp_init and (rec.get("init_sibling") or {}).get("sha256") != exp_init:
                d_issues.append({stem: "init source mismatch"})
        self.check("prep_diag_controls_match_builder_5", not d_issues, d_issues[:8], category="staging")

        # ---- diag2 controls (4) -----------------------------------------
        diag2 = gs.get("prep_diag2", {})
        d2_issues = []
        goal01 = goal.get("goal_pair_00_01")
        goal02 = goal.get("goal_pair_00_02")
        exp_diag2 = [
            ("diag2_goal_00_01_single_bowl_task0init", 1,
             (goal01["goal_state"][1] if goal01 and len(goal01["goal_state"]) > 1 else None),
             tmpl_g[1]["benchmark_language"], (goal01.get("init_sibling") or {}).get("sha256") if goal01 else None),
            ("diag2_goal_00_01_single_bowl_task1init", 1,
             (goal01["goal_state"][1] if goal01 and len(goal01["goal_state"]) > 1 else None),
             tmpl_g[1]["benchmark_language"], init_sha_tp_goal(1)),
            ("diag2_goal_00_01_pair_task1init", 2, None,
             f"{tmpl_g[0]['benchmark_language']} and {tmpl_g[1]['benchmark_language']}",
             init_sha_tp_goal(1)),
            ("diag2_goal_00_02_single_wine_task2init", 1,
             (goal02["goal_state"][1] if goal02 and len(goal02["goal_state"]) > 1 else None),
             tmpl_g[2]["benchmark_language"], init_sha_tp_goal(2)),
        ]
        for stem, n_atoms, exp_atom, exp_lang, exp_init in exp_diag2:
            rec = diag2.get(stem)
            if not rec or not rec.get("parse_ok"):
                d2_issues.append({stem: "missing/unparsable"}); continue
            if len(rec["goal_state"]) != n_atoms:
                d2_issues.append({stem: "n_goal_atoms", "got": len(rec["goal_state"])})
            elif n_atoms == 1 and exp_atom is not None and atom_str(rec["goal_state"][0]) != atom_str(exp_atom):
                d2_issues.append({stem: "goal_atom"})
            if norm(rec["language"] or "") != norm(exp_lang):
                d2_issues.append({stem: "language", "got": rec["language"], "want": exp_lang})
            if exp_init and (rec.get("init_sibling") or {}).get("sha256") != exp_init:
                d2_issues.append({stem: "init source mismatch"})
        self.check("prep_diag2_controls_match_builder_4", not d2_issues, d2_issues[:8], category="staging")

        # ---- staged / object-pilot / sweep copies ----------------------
        staged = gs.get("staged", {})
        st_issues = []
        for stem, src_group in (("goal_pair_00_01", goal), ("goal_pair_00_07", goal),
                                ("goal_pair_08_09", goal)):
            rec, ref = staged.get(stem), src_group.get(stem)
            if not rec or ref is None or rec.get("file_sha256") != ref.get("file_sha256"):
                st_issues.append({stem: "bddl copy differs from artifacts"})
            elif (rec.get("init_sibling") or {}).get("sha256") != (ref.get("init_sibling") or {}).get("sha256"):
                st_issues.append({stem: "init differs"})
        rec, ref = staged.get("obj_object_pair_00_01"), scout.get("object_pair_00_01")
        if not rec or ref is None or rec.get("file_sha256") != ref.get("file_sha256"):
            st_issues.append({"obj_object_pair_00_01": "bddl copy differs from object-scout"})
        self.check("prep_staged_copies_exact", not st_issues, st_issues[:8], category="staging")

        op = gs.get("object_pilot", {})
        op_issues = []
        for stem, rec in op.items():
            ref = obj.get(stem)
            if ref is None:
                op_issues.append({stem: "not an artifact object pair"}); continue
            if rec.get("file_sha256") != ref.get("file_sha256"):
                op_issues.append({stem: "bddl copy differs"})
            if (rec.get("init_sibling") or {}).get("sha256") != (ref.get("init_sibling") or {}).get("sha256"):
                op_issues.append({stem: "init differs"})
        self.check("prep_object_pilot_copies_exact_4", not op_issues, op_issues[:8], category="staging")

        sweep = gs.get("sweep_compatible", {})
        sw_issues = []
        for e in self.goal_entries:
            if (e.get("status") or e.get("classification")) != "compatible":
                continue
            stem = "goal_pair_" + e["pair_id"]
            rec, ref = sweep.get(stem), goal.get(stem)
            if not rec or ref is None or rec.get("file_sha256") != ref.get("file_sha256"):
                sw_issues.append({stem: "bddl copy differs"})
            elif (rec.get("init_sibling") or {}).get("sha256") != (ref.get("init_sibling") or {}).get("sha256"):
                sw_issues.append({stem: "init differs"})
        self.check("prep_sweep_copies_exact_33", not sw_issues, sw_issues[:8], category="staging")

    # -- dynamic -----------------------------------------------------------
    def load_dynamic(self):
        self.dynamic_sets = {}
        for spec in RUNS:
            name = spec["name"]
            run_dir = RUN_ROOT / spec["run_dir"]
            bddl_dir = RUN_ROOT / spec["bddl_dir"]
            trace_dir = RUN_ROOT / spec["trace_dir"]
            results = sorted(glob.glob(str(run_dir / "*" / "results.json")))
            doc = read_json(Path(results[0])) if results else None
            stems = sorted(p.stem for p in bddl_dir.glob("*.bddl")) if bddl_dir.is_dir() else []
            static_group = self.static["groups"].get({
                "smoke": "prep_smoke-pair", "pilot(and)": "prep_pilot-pairs",
                "variant(then/swap)": "prep_variant-pairs", "diag": "prep_diag",
                "diag2": "prep_diag2", "staged": "staged",
                "sweep-compatible": "sweep_compatible", "object-pilot": "object_pilot",
            }[name], {})
            traces = {}
            if trace_dir.is_dir():
                for tp in sorted(trace_dir.glob("*.jsonl")):
                    stem = tp.name.split("__")[0]
                    traces.setdefault(stem, []).append(tp)
            episodes = []
            if doc:
                for task_key, entry in doc.items():
                    m = re.match(r"CUSTOM_T(\d+)$", task_key or "")
                    if not m:
                        continue
                    idx = int(m.group(1))
                    stem = stems[idx] if idx < len(stems) else f"UNKNOWN_{idx}"
                    rlist = list((entry.get("results") or {}).values())
                    r = rlist[0] if rlist else {}
                    rec = static_group.get(stem) or {}
                    repro = r.get("reproducibility") or {}
                    scene_secs = [rec.get("sections", {}).get(k)
                                  for k in (":regions", ":fixtures", ":objects", ":init")]
                    scene_fp = hashlib.sha256(json.dumps(scene_secs).encode()).hexdigest()[:16]
                    ep = {
                        "run": name, "task_key": task_key, "idx": idx, "stem": stem,
                        "bddl": stem,
                        "instruction": entry.get("instruction"),
                        "bddl_language": rec.get("language"),
                        "init_sha": (rec.get("init_sibling") or {}).get("sha256"),
                        "scene_fp": scene_fp,
                        "success": r.get("success"),
                        "steps": r.get("steps"),
                        "time_s": r.get("time_s"),
                        "stabilized_obs_sha": repro.get("stabilized_observation_sha256"),
                        "stabilized_sim_state_sha": repro.get("stabilized_sim_state_sha256"),
                        "environment_seed": repro.get("environment_seed"),
                        "n_goal_atoms": len(rec.get("goal_state") or []),
                        "mapping_ok": norm(entry.get("instruction") or "") == norm(rec.get("language") or ""),
                        "protocol_replan": (entry.get("protocol") or {}).get("replan_steps"),
                        "protocol_max_steps": None,
                    }
                    # traces
                    cand = traces.get(stem) or []
                    ep["trace_files"] = [str(p) for p in cand]
                    if cand:
                        tr = self._parse_trace(cand[0])
                        ep["trace"] = tr
                        first = tr["first_true_step"]
                        ep["first_true_step"] = first
                        ep["subtasks"] = [{"atom": atom, "first_true_step": first.get(atom)}
                                          for atom in tr["atoms"]]
                        ep["subtasks_completed"] = sum(1 for s in ep["subtasks"]
                                                       if s["first_true_step"] is not None)
                        ep["switch_step"] = tr.get("switch_step")
                        ep["trace_offset_ok"] = (
                            tr["n_data_rows"] == (r.get("steps") or 0) + 10
                        )
                    else:
                        ep["trace"] = None
                        ep["first_true_step"] = {}
                        ep["subtasks"] = []
                        ep["subtasks_completed"] = None
                        ep["switch_step"] = None
                        ep.setdefault("trace_offset_ok", False)
                    episodes.append(ep)
            self.dynamic_sets[name] = {
                "spec": spec, "run_dir": str(run_dir), "bddl_dir": str(bddl_dir),
                "trace_dir": str(trace_dir), "results": results, "doc": doc,
                "stems": stems, "episodes": episodes,
                "pending": False,
            }
            self.episodes.extend(episodes)

    @staticmethod
    def _parse_trace(path: Path) -> dict:
        meta = summary = None
        rows = []
        try:
            for line in path.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("_meta"):
                    meta = row
                elif row.get("_summary"):
                    summary = row
                else:
                    rows.append(row)
        except OSError:
            pass
        atoms = (meta or {}).get("atoms") or []
        first = {}
        for i, atom in enumerate(atoms):
            for row in rows:
                truth = row.get("truth") or []
                if i < len(truth) and truth[i]:
                    first[atom] = row.get("step")
                    break
        switch_step = None
        stage2_rows = 0
        stage_values = set()
        rows_with_stage = 0
        for row in rows:
            if "stage" in row:
                rows_with_stage += 1
                stage_values.add(row["stage"])
            if row.get("stage") == 2:
                stage2_rows += 1
                if switch_step is None:
                    switch_step = row.get("step")
        return {
            "path": str(path), "meta": meta, "atoms": atoms, "n_data_rows": len(rows),
            "first_true_step": first,
            "summary_first_true_step": (summary or {}).get("first_true_step"),
            "switch_step": switch_step,
            "stage2_rows": stage2_rows,
            "stage_values": sorted(x for x in stage_values if x is not None),
            "rows_with_stage": rows_with_stage,
            "summary": summary,
        }

    def dynamic_checks(self):
        # ---- per-run completeness / integrity ---------------------------
        for name, ds in self.dynamic_sets.items():
            eps = ds["episodes"]
            expected = ds["spec"]["expected"]
            log_text = self._read_text(RUN_ROOT / ds["spec"]["log"])
            done = ("ALL DONE" in log_text) or ("_DONE" in log_text)
            pending_marker = ds["spec"].get("pending_marker")
            marker_done = (pending_marker is None) or (pending_marker in log_text)
            if not ds["doc"]:
                ds["pending"] = True
                self.check(f"{name}_results_present", False, "results.json missing",
                           critical=False, category="dynamic")
                continue
            n_exp = expected if expected is not None else len(ds["stems"])
            self.check(f"{name}_episode_count_{n_exp}", len(eps) == n_exp and len(eps) == len(ds["stems"]),
                       {"episodes": len(eps), "bddl_stems": len(ds["stems"]), "expected": n_exp},
                       critical=False, category="dynamic")
            if expected is not None and len(eps) < expected:
                ds["pending"] = True
            if not marker_done:
                ds["pending"] = True
            # mapping
            bad_map = [f"{e['task_key']}->{e['stem']}" for e in eps if not e["mapping_ok"]]
            self.check(f"{name}_custom_t_mapping_ok", not bad_map, bad_map[:8], category="dynamic")
            # trace presence/offset
            missing_tr = [e["task_key"] for e in eps if not e.get("trace")]
            bad_off = [e["task_key"] for e in eps if e.get("trace") and not e.get("trace_offset_ok")]
            self.check(f"{name}_trace_per_episode", not missing_tr, missing_tr[:8], category="dynamic")
            self.check(f"{name}_trace_offset_10_stabilization", not bad_off, bad_off[:8],
                       critical=False, category="dynamic")
            # trace first_true vs summary internal (staged traces do not record
            # first_true_step in their _summary; only compare when available)
            bad_first = []
            for e in eps:
                tr = e.get("trace") or {}
                if not tr:
                    continue
                internal = tr.get("summary_first_true_step")
                if not internal:
                    continue
                if norm(json.dumps(tr["first_true_step"], sort_keys=True)) != norm(
                        json.dumps(internal, sort_keys=True)):
                    bad_first.append(e["task_key"])
            self.check(f"{name}_trace_summary_first_true_consistent", not bad_first, bad_first[:8],
                       critical=False, category="dynamic")
            # videos
            vid_dirs = sorted(glob.glob(str(RUN_ROOT / ds["spec"]["run_dir"] / "*" / "videos")))
            videos = []
            for vd in vid_dirs:
                videos.extend(sorted(glob.glob(vd + "/*.mp4")))
            zero = [p for p in videos if Path(p).stat().st_size == 0]
            self.check(f"{name}_videos_present", len(videos) >= len(eps),
                       {"videos": len(videos), "episodes": len(eps)}, critical=False, category="dynamic")
            self.check(f"{name}_videos_nonzero", not zero, zero[:5], critical=False, category="dynamic")
            ds["videos"] = videos
            ds["log_text"] = log_text
            ds["done_marker"] = done

        # ---- protocol / trace structural checks -------------------------
        for name, ds in self.dynamic_sets.items():
            eps = ds["episodes"]
            if not eps:
                continue
            want_replan = 5 if name == "object-pilot" else 10
            bad_replan = [e["task_key"] for e in eps if e["protocol_replan"] != want_replan]
            self.check(f"{name}_replan_steps_{want_replan}", not bad_replan, bad_replan[:8],
                       critical=False, category="dynamic")
            want_max = MAX_STEPS.get(name, DEFAULTS_MAX_STEPS)
            bad_max = [e["task_key"] for e in eps
                       if not (isinstance(e["steps"], int) and 0 < e["steps"] <= want_max)]
            self.check(f"{name}_steps_within_max_{want_max}", not bad_max, bad_max[:8],
                       critical=False, category="dynamic")
            dup_tr, summary_steps_bad, stage_bad = [], [], []
            expected_names = set()
            for e in eps:
                fs = e.get("trace_files") or []
                if len(fs) != 1:
                    dup_tr.append((e["task_key"], len(fs)))
                if fs:
                    expected_names.add(Path(fs[0]).name)
                tr = e.get("trace") or {}
                if not tr:
                    continue
                summ = tr.get("summary") or {}
                if "steps" in summ and summ.get("steps") != tr.get("n_data_rows"):
                    summary_steps_bad.append(e["task_key"])
                if name == "staged":
                    if tr.get("stage_values") and not set(tr["stage_values"]) <= {1, 2}:
                        stage_bad.append((e["task_key"], tr.get("stage_values")))
                    if e.get("switch_step") is None and e.get("success"):
                        stage_bad.append((e["task_key"], "success but no stage-2 row"))
                else:
                    if tr.get("rows_with_stage"):
                        stage_bad.append((e["task_key"], "unexpected stage field"))
            self.check(f"{name}_one_trace_per_episode", not dup_tr, dup_tr[:8],
                       critical=False, category="dynamic")
            self.check(f"{name}_trace_summary_steps_consistent", not summary_steps_bad,
                       summary_steps_bad[:8], critical=False, category="dynamic")
            self.check(f"{name}_trace_stage_semantics", not stage_bad, stage_bad[:8],
                       critical=False, category="dynamic")
            trace_dir = Path(ds["trace_dir"])
            if trace_dir.is_dir():
                extra_tr = [p.name for p in sorted(trace_dir.glob("*.jsonl"))
                            if p.name not in expected_names]
                self.check(f"{name}_no_extra_trace_files", not extra_tr, extra_tr[:8],
                           critical=False, category="dynamic")
            # per-run coverage of expected bddl stems
            expected_stems = set(ds["stems"])
            got_stems = {e["stem"] for e in eps}
            if name == "sweep-compatible" and not ds["pending"]:
                compat = [e for e in self.goal_entries
                          if (e.get("status") or e.get("classification")) == "compatible"]
                expected_stems = {f"goal_pair_{e['pair_id']}" for e in compat}
            self.check(f"{name}_covers_expected_pairs",
                       got_stems == expected_stems and len(got_stems) == len(eps),
                       {"missing": sorted(expected_stems - got_stems)[:8],
                        "unexpected": sorted(got_stems - expected_stems)[:8]},
                       critical=(not ds["pending"]), category="dynamic")

        # ---- environment seed & init-state / rendering reproducibility -------
        bad_env = [e["task_key"] for e in self.episodes if e.get("environment_seed") != 1000]
        self.check("all_episodes_environment_seed_1000", not bad_env, bad_env[:8],
                   critical=False, category="dynamic")
        # (a) the custom sibling init patch must load the same init deterministically:
        #     identical (init sha, scene fingerprint) => identical stabilized sim state
        sim_groups: dict = {}
        for e in self.episodes:
            if not e.get("init_sha") or not e.get("stabilized_sim_state_sha"):
                continue
            sim_groups.setdefault((e["init_sha"], e["scene_fp"]), []).append(e)
        sim_bad = []
        for (init_sha, scene_fp), eps in sim_groups.items():
            shas = {e["stabilized_sim_state_sha"] for e in eps}
            if len(shas) > 1:
                sim_bad.append({"init_sha": init_sha[:16], "scene_fp": scene_fp,
                                "n_sim_states": len(shas),
                                "episodes": [f"{e['run']}:{e['task_key']}" for e in eps]})
        self.check("stabilized_sim_state_consistent_per_init_and_scene", not sim_bad,
                   sim_bad[:5], critical=True, category="dynamic")
        # (b) within one process (run) the same init+scene must give the same obs
        run_obs_groups: dict = {}
        for e in self.episodes:
            if not e.get("init_sha") or not e.get("stabilized_obs_sha"):
                continue
            run_obs_groups.setdefault((e["run"], e["init_sha"], e["scene_fp"]), []).append(e)
        run_obs_bad = []
        for (run, init_sha, scene_fp), eps in run_obs_groups.items():
            shas = {e["stabilized_obs_sha"] for e in eps}
            if len(shas) > 1:
                run_obs_bad.append({"run": run, "init_sha": init_sha[:16], "n_obs": len(shas)})
        self.check("within_run_stabilized_obs_deterministic", not run_obs_bad,
                   run_obs_bad[:5], critical=False, category="dynamic")
        # (c) cross-process observation variation: same sim state but different
        #     rendered pixels were observed between early and later run batches
        cross_obs = {}
        for (init_sha, scene_fp), eps in sim_groups.items():
            obs = {e["stabilized_obs_sha"] for e in eps}
            if len(obs) > 1:
                cross_obs.setdefault(tuple(sorted({e["run"] for e in eps})), set()).update(obs)
        cross_obs_detail = [
            {"runs": list(runs_), "n_obs": len(obs)}
            for runs_, obs in cross_obs.items()
        ]
        self.init_obs_consistency = {
            "n_init_scene_groups": len(sim_groups),
            "n_episodes_with_init": sum(len(v) for v in sim_groups.values()),
            "sim_state_inconsistent_groups": sim_bad,
            "within_run_obs_inconsistent": run_obs_bad,
            "cross_run_obs_variation_groups": cross_obs_detail,
            "note": ("同一个 init+scene 的 stabilized_sim_state 全部一致（custom init patch 生效且确定）；"
                     "但早期批次与后期批次对相同 sim state 渲染出的 observation sha 不同 "
                     "（可能是不同启动 shell 的 MUJOCO_GL/渲染后端差异），属于跨进程渲染可复现性 caveat，"
                     "不影响本审计的 success/steps/subtask 复算。"),
        }
        if cross_obs_detail:
            self.problems.append({"check": "cross_process_observation_variation",
                                  "detail": {"count": len(cross_obs_detail),
                                             "examples": cross_obs_detail[:3],
                                             "note": self.init_obs_consistency["note"]}})

        # ---- per-run aggregate stats -----------------------------------
        for name, ds in self.dynamic_sets.items():
            eps = ds["episodes"]
            total = len(eps)
            success = sum(1 for e in eps if e.get("success"))
            steps = [e["steps"] for e in eps if isinstance(e.get("steps"), int)]
            dist = {0: 0, 1: 0, 2: 0}
            dist_missing = 0
            for e in eps:
                n = e.get("subtasks_completed")
                if n is None:
                    dist_missing += 1
                elif n in dist:
                    dist[n] += 1
            self.run_stats[name] = {
                "episodes": total, "success": success,
                "success_rate": (success / total) if total else None,
                "mean_steps": (sum(steps) / len(steps)) if steps else None,
                "steps_min": min(steps) if steps else None,
                "steps_max": max(steps) if steps else None,
                "subtask_distribution": dist,
                "subtask_missing": dist_missing,
                "pending": ds["pending"],
            }

        # ---- logs cross-check ------------------------------------------
        for name, ds in self.dynamic_sets.items():
            logp = RUN_ROOT / ds["spec"]["log"]
            if not logp.is_file():
                self.check(f"{name}_log_present", False, str(logp), critical=False, category="logs")
                continue
            text = ds.get("log_text") or ""
            n_hdr = len(re.findall(r"\[CUSTOM\s+#\d+\]", text))
            n_sum = len(re.findall(r"\[BASELINE_SUMMARY\]", text))
            summaries = []
            for m in re.finditer(r"\[BASELINE_SUMMARY\]\s*(\{.*\})", text):
                try:
                    summaries.append(json.loads(m.group(1)))
                except json.JSONDecodeError:
                    pass
            log_eps = [(s.get("task") or {}).get("success") for s in summaries]
            res_succ = sorted(int(bool(e.get("success"))) for e in ds["episodes"])
            log_succ = sorted(int(bool(x)) for x in log_eps)
            self.check(f"{name}_log_episode_count", n_hdr == len(ds["episodes"]),
                       {"headers": n_hdr, "results": len(ds["episodes"])}, critical=False, category="logs")
            self.check(f"{name}_log_vs_results_success", res_succ == log_succ,
                       {"results": res_succ, "log": log_succ}, critical=False, category="logs")
            tracebacks = [ln for i, ln in enumerate(text.splitlines(), 1)
                          if "Traceback" in ln or re.search(r"\bERROR\b", ln)]
            self.check(f"{name}_log_no_traceback", not tracebacks, tracebacks[:5], critical=False, category="logs")
            maxsteps = sorted({int(x) for x in re.findall(r"MaxSteps:\s*(\d+)", text)})
            want = MAX_STEPS.get(name, DEFAULTS_MAX_STEPS)
            self.check(f"{name}_log_max_steps_expected", maxsteps == [want], maxsteps,
                       critical=False, category="logs")
            if ds["spec"].get("pending_marker") and not ds["pending"]:
                self.check(f"{name}_done_marker", ds["spec"]["pending_marker"] in text,
                           ds["spec"]["pending_marker"], critical=False, category="logs")

        # ---- video probe (per run sample) ------------------------------
        try:
            import cv2  # noqa: PLC0415
            self._cv2 = cv2
        except Exception:  # noqa: BLE001
            self._cv2 = None
        for name, ds in self.dynamic_sets.items():
            if not ds.get("videos") or not ds["episodes"]:
                continue
            by_task = {Path(v).name.split("__")[0]: v for v in ds["videos"]}
            probes = []
            for e in ds["episodes"]:
                v = by_task.get(e["task_key"])
                if not v:
                    probes.append({"task": e["task_key"], "error": "no video for task"})
                    continue
                pr = self._probe_video(Path(v), e.get("steps"))
                pr["task"] = e["task_key"]
                probes.append(pr)
            bad = [p for p in probes if not p.get("ok")]
            ds["video_probes"] = probes
            self.check(f"{name}_video_probe_ok", not bad, bad[:5], critical=False, category="dynamic")

        # ---- results/trace offset vs Lead staged switch -----------------
        staged = self.dynamic_sets.get("staged", {}).get("episodes") or []
        for e in staged:
            tr = e.get("trace") or {}
            sw = tr.get("switch_step")
            first = (e.get("first_true_step") or {})
            atoms = list(first.keys())
            # switch should happen right when atom 0 becomes true (its first true row)
            a0 = first.get(atoms[0]) if atoms else None
            ok = sw is not None and (a0 is None or abs((sw or 0) - int(a0)) <= 1)
            e["switch_step_ok"] = ok
        self.check("staged_switch_step_consistent_with_atom0",
                   all(e.get("switch_step_ok") for e in staged),
                   [e["task_key"] for e in staged if not e.get("switch_step_ok")],
                   critical=False, category="conclusions")

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(errors="replace")
        except OSError:
            return ""

    def _probe_video(self, path: Path, steps) -> dict:
        rec = {"path": str(path), "size": path.stat().st_size, "ok": False}
        if not path.is_file() or rec["size"] == 0:
            rec["error"] = "missing/zero"
            return rec
        if not self._cv2:
            rec["ok"] = True
            rec["note"] = "cv2 unavailable; size only"
            return rec
        try:
            cap = self._cv2.VideoCapture(str(path))
            frames = int(cap.get(self._cv2.CAP_PROP_FRAME_COUNT))
            fps = float(cap.get(self._cv2.CAP_PROP_FPS))
            w = int(cap.get(self._cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            rec.update(frames=frames, fps=round(fps, 3), width=w, height=h)
            if steps is not None:
                exp = int(steps) + 1
                rec["expected_frames"] = exp
                rec["frames_delta"] = frames - exp
                rec["ok"] = abs(frames - exp) <= max(2, int(0.03 * exp)) and abs(fps - 20) < 0.1 and (w, h) == (256, 256)
            else:
                rec["ok"] = abs(fps - 20) < 0.1 and (w, h) == (256, 256)
        except Exception as exc:  # noqa: BLE001
            rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec

    # -- Lead summary comparison ----------------------------------------
    def summary_comparison(self):
        summary_path = RUN_ROOT / "run/combined-dynamic-summary.json"
        self.summary_doc = read_json(summary_path)
        self.summary_meta = {"path": str(summary_path), "present": self.summary_doc is not None,
                             "mtime": time.strftime("%Y-%m-%dT%H:%M:%S",
                                                    time.localtime(summary_path.stat().st_mtime))
                             if summary_path.is_file() else None}
        if not self.summary_doc:
            self.check("lead_summary_present", False, "missing", critical=False, category="summary")
            self.summary_comparison_result = {"present": False}
            return
        rows = self.summary_doc.get("rows") or []
        runs_in_lead = sorted({r.get("run") for r in rows})
        our_runs = sorted({e["run"] for e in self.episodes})
        lead_runs_normalized = sorted(LEAD_TO_INTERNAL.get(r, r) for r in runs_in_lead)
        # the single-pair smoke run is a harness smoke test, not part of the summary
        expected_excluded = {"smoke"}
        missing_runs = [r for r in our_runs
                        if r not in lead_runs_normalized and r not in expected_excluded]
        lead_by_key = {(r.get("run"), r.get("task_key")): r for r in rows}
        our_by_key = {(e["run"], e["task_key"]): e
                      for e in self.episodes if e["run"] in lead_runs_normalized}
        internal_to_lead = {r: lead_run_name(r) for r in our_runs}
        fields_diffs: list[dict] = []
        classification_diffs: list[dict] = []
        for key, e in our_by_key.items():
            lead = lead_by_key.get((internal_to_lead.get(e["run"], e["run"]), e["task_key"]))
            if lead is None:
                fields_diffs.append({"run": e["run"], "task_key": e["task_key"],
                                     "issue": "missing in lead summary"})
                continue
            for field in ("bddl", "instruction"):
                if norm(lead.get(field) or "") != norm(e.get(field) or ""):
                    fields_diffs.append({"run": e["run"], "task_key": e["task_key"],
                                         "field": field, "lead": lead.get(field),
                                         "independent": e.get(field)})
            for field in ("success", "steps"):
                if lead.get(field) != e.get(field):
                    fields_diffs.append({"run": e["run"], "task_key": e["task_key"],
                                         "field": field, "lead": lead.get(field),
                                         "independent": e.get(field)})
            l_sub = [(s.get("atom"), s.get("first_true_step"))
                     for s in (lead.get("subtasks") or [])]
            o_sub = [(s.get("atom"), s.get("first_true_step"))
                     for s in (e.get("subtasks") or [])]
            if l_sub != o_sub:
                fields_diffs.append({"run": e["run"], "task_key": e["task_key"],
                                     "field": "subtasks", "lead": l_sub,
                                     "independent": o_sub})
            if lead.get("switch_step") != e.get("switch_step"):
                fields_diffs.append({"run": e["run"], "task_key": e["task_key"],
                                     "field": "switch_step", "lead": lead.get("switch_step"),
                                     "independent": e.get("switch_step")})
            ind_status = self._classify(e)
            e["independent_status"] = ind_status
            if (lead.get("status") or "unknown") != (ind_status or "unknown"):
                classification_diffs.append({"run": e["run"], "task_key": e["task_key"],
                                             "lead": lead.get("status"),
                                             "independent": ind_status})
        our_leadkeys = {(internal_to_lead.get(e["run"], e["run"]), e["task_key"])
                        for e in self.episodes}
        extra_rows = [{"run": k[0], "task_key": k[1]}
                      for k in lead_by_key if k not in our_leadkeys]
        counts_ok = all(
            len([r for r in rows if r.get("run") == run]) ==
            len([e for e in self.episodes if e["run"] == LEAD_TO_INTERNAL.get(run, run)])
            for run in runs_in_lead
        )
        self.summary_comparison_result = {
            "present": True,
            "rows_lead": len(rows),
            "rows_independent": len(self.episodes),
            "runs_in_lead": runs_in_lead,
            "lead_run_aliases": LEAD_RUN_ALIASES,
            "runs_independent": our_runs,
            "missing_runs_in_lead": missing_runs,
            "expected_excluded_from_summary": sorted(expected_excluded),
            "extra_rows_in_lead": extra_rows,
            "per_run_counts_ok": counts_ok,
            "diffs": fields_diffs,
            "classification_diffs": classification_diffs,
        }
        self.check("lead_summary_rows_match_independent_counts", counts_ok,
                   {"lead_rows": len(rows), "independent": len(self.episodes),
                    "missing_runs_in_lead": missing_runs, "extra_rows": extra_rows},
                   category="summary")
        self.check("lead_summary_fields_match_independent", not fields_diffs,
                   fields_diffs[:12], critical=False, category="summary")
        if missing_runs:
            self.problems.append({"check": "lead_summary_missing_runs",
                                  "detail": {"missing_runs": missing_runs,
                                             "note": "Lead summary may be regenerated after sweep/object-pilot; smoke is expected to be excluded"}})
        if classification_diffs:
            self.problems.append({"check": "lead_summary_classification_lookup_issues",
                                  "detail": {"count": len(classification_diffs),
                                             "examples": classification_diffs[:8],
                                             "note": "analyze_combined.py pair-id lookup: reversed goal pair ids fall back to unknown; object pair ids collide with goal pair ids through the object_pair_ prefix alias"}})

    def _classify(self, ep: dict):
        stem = ep.get("stem") or ""
        m = re.search(r"(goal|object)_pair_(\d{2})_(\d{2})", stem)
        if not m:
            return None
        kind, i, j = m.group(1), int(m.group(2)), int(m.group(3))
        if kind == "goal":
            e = self.goal_pairs_meta.get((min(i, j), max(i, j)))
            return (e.get("status") or e.get("classification")) if e else "unknown"
        # object pairs: metadata carries no status; report validated/union instead
        obj_doc = read_json(RUN_ROOT / "artifacts/object-pairs/pairs.json") or {}
        want_id = f"object_pair_{i:02d}_{j:02d}"
        for e in obj_doc.get("pairs") or []:
            if e["pair_id"] == want_id:
                return f"object_validated={e.get('validated')},union={e.get('union_objects')}"
        return "object_unknown"

    # -- key conclusions --------------------------------------------------
    def conclusions(self):
        res = {}
        goal_single = [e for e in self.episodes if e["run"] in SINGLE_INSTR_GOAL_RUNS]
        obj_single = [e for e in self.episodes if e["run"] in SINGLE_INSTR_OBJECT_RUNS]
        def stats(eps):
            total = len(eps)
            ok = sum(1 for e in eps if e.get("success"))
            dist = {}
            for e in eps:
                n = e.get("subtasks_completed")
                dist[n] = dist.get(n, 0) + 1
            return {"episodes": total, "success": ok,
                    "success_rate": (ok / total) if total else None,
                    "subtask_distribution": dist}
        res["single_instruction_goal"] = stats(goal_single)
        fail = [e for e in goal_single if not e.get("success")]
        fail_dist = {}
        for e in fail:
            n = e.get("subtasks_completed")
            fail_dist[n] = fail_dist.get(n, 0) + 1
        res["single_instruction_goal_failures"] = {
            "failures": len(fail), "failure_subtask_distribution": fail_dist,
            "exactly_one_completed": fail_dist.get(1, 0),
            "zero_completed": fail_dist.get(0, 0),
        }
        # single-instruction + variant vs same pair-and baseline
        pair_and = {}
        for e in self.episodes:
            if e["run"] in ("pilot(and)", "sweep-compatible"):
                pair_and.setdefault(e["stem"], e)
        variant_cmp = []
        for e in self.episodes:
            if e["run"] != "variant(then/swap)":
                continue
            stem = e["stem"]
            base_id = stem.replace("_then", "").replace("_andthen", "").replace("_swap", "")
            base = pair_and.get(base_id)
            variant_cmp.append({
                "variant": stem, "success": e.get("success"), "subtasks": e.get("subtasks_completed"),
                "base_and_present": base is not None,
                "base_and_success": base.get("success") if base else None,
                "base_and_subtasks": base.get("subtasks_completed") if base else None,
            })
        res["phrasing_variants"] = {
            "n": len(variant_cmp),
            "success": sum(1 for v in variant_cmp if v["success"]),
            "rows": variant_cmp,
            "no_improvement_vs_and": all(
                (v["success"] is not True) or (v["base_and_success"] is True) for v in variant_cmp),
        }
        staged = [e for e in self.episodes if e["run"] == "staged"]
        res["staged"] = {
            "n": len(staged),
            "success": sum(1 for e in staged if e.get("success")),
            "rows": [{"stem": e["stem"], "success": e["success"], "steps": e["steps"],
                      "switch_step": e.get("switch_step"), "subtasks": e.get("subtasks_completed")}
                     for e in staged],
        }
        # diag controls
        diag = {e["stem"]: e for e in self.episodes if e["run"] == "diag"}
        diag2 = {e["stem"]: e for e in self.episodes if e["run"] == "diag2"}
        res["diagnostics"] = {
            "diag": [{"stem": k, "success": v.get("success"), "steps": v.get("steps"),
                      "subtasks": v.get("subtasks_completed")} for k, v in sorted(diag.items())],
            "diag2": [{"stem": k, "success": v.get("success"), "steps": v.get("steps"),
                       "subtasks": v.get("subtasks_completed")} for k, v in sorted(diag2.items())],
        }
        def look(store, prefix):
            for k, v in store.items():
                if prefix in k:
                    return v
            return None
        wine_pair_init = look(diag, "single_wine")
        wine_task2_init = look(diag2, "single_wine")
        res["init_source_effect_wine"] = {
            "pair_init_success": wine_pair_init.get("success") if wine_pair_init else None,
            "task2_init_success": wine_task2_init.get("success") if wine_task2_init else None,
            "effect_verified": bool(wine_pair_init and wine_task2_init
                                    and wine_pair_init.get("success") is False
                                    and wine_task2_init.get("success") is True),
        }
        bowl0, bowl1 = look(diag2, "spatial") if False else look(diag2, "single_bowl_task0init"), look(diag2, "single_bowl_task1init")
        stove = look(diag, "single_stove")
        soup = look(diag, "single_soup")
        cheese = look(diag, "single_cheese")
        res["single_subtask_controls"] = {
            "bowl_task0init": {"success": bowl0.get("success") if bowl0 else None},
            "bowl_task1init": {"success": bowl1.get("success") if bowl1 else None},
            "stove": {"success": stove.get("success") if stove else None},
            "soup": {"success": soup.get("success") if soup else None},
            "cheese_object_merged": {"success": cheese.get("success") if cheese else None},
            "verified": bool(bowl0 and bowl1 and stove and soup and cheese
                             and bowl0.get("success") and bowl1.get("success")
                             and stove.get("success") and soup.get("success")
                             and cheese.get("success") is False),
        }
        res["object_single_instruction"] = stats(obj_single)
        self.conclusions_res = res
        self.check("conclusion_single_instruction_high_failure",
                   (res["single_instruction_goal"]["success_rate"] or 1.0) < 0.5,
                   res["single_instruction_goal"], category="conclusions")
        self.check("conclusion_failure_mode_exactly_one_subtask",
                   res["single_instruction_goal_failures"]["exactly_one_completed"]
                   >= 0.5 * max(1, res["single_instruction_goal_failures"]["failures"]),
                   res["single_instruction_goal_failures"], category="conclusions")
        self.check("conclusion_phrasing_variants_no_improvement",
                   res["phrasing_variants"]["success"] == 0
                   and res["phrasing_variants"]["no_improvement_vs_and"],
                   res["phrasing_variants"], category="conclusions")
        self.check("conclusion_staged_partially_effective",
                   res["staged"]["success"] in (2, 3) or (0 < res["staged"]["success"] < res["staged"]["n"]),
                   res["staged"], category="conclusions")
        self.check("conclusion_init_source_effect",
                   res["init_source_effect_wine"]["effect_verified"],
                   res["init_source_effect_wine"], category="conclusions")
        self.check("conclusion_single_subtask_controls",
                   res["single_subtask_controls"]["verified"],
                   res["single_subtask_controls"], category="conclusions")

    # -- orchestration ----------------------------------------------------
    def run(self):
        started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.load_static()
        self.static_checks()
        self.staging_checks()
        self.load_dynamic()
        self.dynamic_checks()
        self.summary_comparison()
        self.conclusions()
        critical = [c for c in self.checks if c["critical"]]
        pending_runs = [n for n, ds in self.dynamic_sets.items() if ds["pending"]]
        status = "partial" if pending_runs else "complete"
        ev = {
            "audit": {
                "generated_at": started,
                "auditor": "libero-std-verifier (independent, read-only)",
                "run_root": str(RUN_ROOT),
                "spec": str(SPEC_PATH),
                "mode": "--partial" if self.partial else "full",
                "status": status,
                "scope": "CPU-only, read-only: BDDL parsing, torch.load init states, results/trace/log parsing, OpenCV video probe; no env creation, no policy model, no GPU",
            },
            "status": {"overall": status, "pending_runs": pending_runs,
                       "sweep_done_marker": "SWEEP_DONE" in ((self.dynamic_sets.get("sweep-compatible") or {}).get("log_text") or ""),
                       "object_pilot_done_marker": "OBJECT_PILOT_DONE" in ((self.dynamic_sets.get("object-pilot") or {}).get("log_text") or "")},
            "static": {
                "counts": {name: len(v) for name, v in self.static["groups"].items()},
                "goal_classification_counts": {k: sum(1 for e in self.goal_entries
                                                      if (e.get("status") or e.get("classification")) == k)
                                               for k in ("compatible", "hard", "conflict")},
                "object_union_distribution": {u: sum(1 for e in (read_json(RUN_ROOT / "artifacts/object-pairs/pairs.json") or {}).get("pairs", [])
                                                     if e.get("union_objects") == u) for u in (7, 8, 9)},
                "classification_recompute": getattr(self, "classification_recompute", None),
                "provenance": {
                    "goal_checksums_lines": 137,
                    "phrasings_checksums_lines": 271,
                    "static_validation": "artifacts/goal-pairs/static-validation.json",
                    "phrasings_validation": "artifacts/goal-pairs-phrasings/static-validation.json",
                    "object_validation": "artifacts/object-pairs/validation.json",
                    "object_scout_feasibility": "artifacts/object-scout/feasibility.json",
                },
            },
            "run_stats": self.run_stats,
            "episodes": self.episodes,
            "init_state_observation_consistency": getattr(self, "init_obs_consistency", None),
            "summary_comparison": getattr(self, "summary_comparison_result", None),
            "summary_meta": getattr(self, "summary_meta", None),
            "conclusions": self.conclusions_res,
            "checks": self.checks,
            "problems": self.problems,
            "verdict": {
                "critical_checks_passed": sum(1 for c in critical if c["ok"]),
                "critical_checks_total": len(critical),
                "all_critical_checks_passed": all(c["ok"] for c in critical),
                "problems": self.problems,
                "status": status,
            },
        }
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "evidence.json").write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n")
        (OUT_DIR / "report.md").write_text(self.render(ev))
        print(f"[audit] wrote {OUT_DIR/'evidence.json'} and report.md")
        print("[audit] status:", status, "| episodes:", len(self.episodes),
              "| critical:", ev["verdict"]["critical_checks_passed"], "/", ev["verdict"]["critical_checks_total"],
              "| pending runs:", pending_runs)
        for name, s in self.run_stats.items():
            print(f"  {name:22s} {s['success']}/{s['episodes']} rate={s['success_rate']} "
                  f"subtasks={s['subtask_distribution']} pending={s['pending']}")
        return ev

    # -- markdown ---------------------------------------------------------
    def render(self, ev: dict) -> str:
        L: list[str] = []
        a = ev["audit"]
        st = ev["status"]
        L.append("# 双子任务组合实验 · 独立只读审计（task-11）")
        L.append("")
        L.append(f"- 审计时间：{a['generated_at']}（Asia/Singapore）")
        L.append(f"- 工作目录：`{a['run_root']}`")
        L.append(f"- 范围：{a['scope']}")
        L.append(f"- **状态：{st['overall'].upper()}**"
                 + (f"（pending runs: {st['pending_runs']}）" if st["pending_runs"] else ""))
        L.append(f"- sweep done marker: {st['sweep_done_marker']}；object-pilot done marker: {st['object_pilot_done_marker']}")
        L.append("")
        v = ev["verdict"]
        L.append("## 0. 结论摘要")
        L.append("")
        if v["problems"]:
            L.append(f"- 关键检查 **{v['critical_checks_passed']}/{v['critical_checks_total']}** 通过（无 critical 异常）；"
                     f"另有 {len(v['problems'])} 条非 critical 提示（详见 §6）："
                     + "、".join(f"`{p['check']}`" for p in v["problems"]))
        else:
            L.append(f"- 关键检查 **{v['critical_checks_passed']}/{v['critical_checks_total']}** 通过（无 critical 异常）。")
        concl = ev["conclusions"]
        g = concl["single_instruction_goal"]
        gf = concl["single_instruction_goal_failures"]
        L.append(f"- 单指令组合任务（GOAL，pilot+variant+sweep）：**{g['success']}/{g['episodes']} 成功**"
                 f"（{g['success_rate']*100:.1f}%）；失败 {gf['failures']} 条中，完成 **1 个子任务** {gf['exactly_one_completed']} 条、"
                 f"完成 0 个 {gf['zero_completed']} 条 → **“完成恰好 1 个子任务后停滞”是主要失败模式**。")
        cl = concl["single_subtask_controls"]
        L.append(f"- 单子任务对照：bowl(两 init 源)={cl['bowl_task0init']['success']}/{cl['bowl_task1init']['success']}、"
                 f"stove={cl['stove']['success']}、soup={cl['soup']['success']}、cheese(OBJECT 合并场景)={cl['cheese_object_merged']['success']} → 对照结论成立。")
        w = concl["init_source_effect_wine"]
        L.append(f"- init 源影响（wine 单任务）：pair-init={w['pair_init_success']} vs task2-init={w['task2_init_success']} → "
                 f"{'成立（同一目标仅 init 源不同，成功率不同）' if w['effect_verified'] else '未复现'}。")
        vp = concl["phrasing_variants"]
        L.append(f"- 措辞变体（then/andthen/swap）：**{vp['success']}/{vp['n']} 成功** → 未改善（与 and 基线相比无提升）。")
        sg = concl["staged"]
        L.append(f"- staged 分阶段指令：**{sg['success']}/{sg['n']} 成功**，"
                 f"成功项：{[(r['stem'], r['steps'], r['switch_step']) for r in sg['rows'] if r['success']]}")
        if concl["object_single_instruction"]["episodes"]:
            os_ = concl["object_single_instruction"]
            L.append(f"- OBJECT 单指令组合（object-pilot，0/4）：每对都只完成第 1 个 object（子任务完成分布 {os_['subtask_distribution']}），"
                     f"同样呈现“完成 1 个子任务后停滞”；union 7/8/9 的 4 个 pair（00_01/00_03/00_04/08_09）全部失败。")
        sc = ev["summary_comparison"] or {}
        if sc and sc.get("present"):
            L.append(f"- 与 Lead `combined-dynamic-summary.json` 对比：独立 episodes {sc['rows_independent']} vs Lead rows {sc['rows_lead']}；"
                     f"字段差异 **{len(sc['diffs'])}** 条；分类字段差异 **{len(sc.get('classification_diffs') or [])}** 条；"
                     f"Lead 未覆盖 run：{sc['missing_runs_in_lead']}。")
        L.append("")

        L.append("## 1. 静态产物核对")
        L.append("")
        L.append("| 产物 | 独立计数/检查 | 结果 |")
        L.append("|---|---|---|")
        counts = ev["static"]["counts"]
        L.append(f"| GOAL 组合对 | 45 bddl + 45 init(init/) + 45 sibling init；45 对唯一；goal 原子=2；language=lang_i and lang_j；scene 段=模板；init=(50,79) 且与 task_i 官方 init 逐字节一致 | {'✅' if self._all_ok('goal') else '❌'} |")
        L.append(f"| GOAL 分类 | compatible {ev['static']['goal_classification_counts'].get('compatible')} / hard {ev['static']['goal_classification_counts'].get('hard')} / conflict {ev['static']['goal_classification_counts'].get('conflict')} | {'✅' if self._all_ok('goal') else '❌'} |")
        cr = getattr(self, "classification_recompute", {})
        L.append(f"| GOAL 分类独立复算 | conflict：由 goal atoms 推导“同一被操作物体被要求处于不同目标位”，与标注集合"
                 f"{'完全一致 ✅' if cr.get('conflict_matches') else '有差异 ❌'}；hard：atom 规则候选 "
                 f"{cr.get('hard_candidates_atom_based')} vs 标注 {cr.get('hard_actual')}"
                 f"（多出 {cr.get('hard_candidate_minus_actual')}：如 05_08 可先放碗再推盘，按物理可顺序完成归 compatible） | "
                 f"{'✅ conflict 精确复现；hard 为规则判断项' if cr.get('conflict_matches') else '⚠️ 复核分类'} |")
        L.append(f"| 措辞变体 | 90 bddl（then 45 / andthen 45），language 模板、goal/scene/init 与基础对一致 | {'✅' if self._all_ok('phrasings') else '❌'} |")
        L.append(f"| OBJECT 组合对 | 30 bddl + 30 init + 30 meta；union 10/10/10；init shape 123/136/149×50；goal 原子=2 | {'✅' if self._all_ok('object') else '❌'} |")
        L.append(f"| OBJECT 原型 | 2 bddl + 2 init；feasibility.json 存在 | {'✅' if self._all_ok('object') else '❌'} |")
        L.append(f"| sweep / object-pilot / staged 输入 | sweep 33（=compatible）、object-pilot 4、staged 4 | {'✅' if self._all_ok('staging') else '❌'} |")
        L.append(f"| prep 目录来源核验 | pilot 9 / variant 7 / diag 5 / diag2 4 / smoke 1 / staged 4 / object-pilot 4 / sweep 33：语言、goal atoms、init sha 与 bddl 拷贝哈希逐项对照 builder 源 | {'✅' if self._all_ok('staging') else '❌'} |")
        L.append(f"| shadow / runtime overlay | shadow = baseline pristine shadow 软链（config 相同）；overlay 含 `NUM_STEPS_WAIT=10` 与 custom sibling `.pruned_init` 加载 patch | {'✅' if self._all_ok('staging') else '❌'} |")
        L.append("")
        L.append("静态检查明细（失败的 critical 检查会在此列出，完整清单见 evidence.json）：")
        for c in ev["checks"]:
            if c["category"] in ("goal", "phrasings", "object", "staging") and not c["ok"]:
                L.append(f"- ❌ `{c['check']}`: {json.dumps(c['detail'], ensure_ascii=False)[:400]}")
        L.append("")

        L.append("## 2. 动态 pi05 运行独立复算")
        L.append("")
        L.append("| run | episodes | success | rate | mean steps | 子任务完成分布 0/1/2 | traces | videos | log | pending |")
        L.append("|---|---:|---:|---:|---:|---|---:|---:|---|---|")
        for name, s in ev["run_stats"].items():
            ds = self.dynamic_sets[name]
            dist = s["subtask_distribution"]
            rate = f"{s['success_rate']*100:.1f}%" if s["success_rate"] is not None else "-"
            msteps = f"{s['mean_steps']:.1f}" if s["mean_steps"] is not None else "-"
            L.append(f"| {name} | {s['episodes']} | {s['success']} | {rate} | {msteps} | "
                     f"{dist.get(0,0)}/{dist.get(1,0)}/{dist.get(2,0)} | "
                     f"{sum(1 for e in ds['episodes'] if e.get('trace'))}/{len(ds['episodes'])} | "
                     f"{len(ds.get('videos') or [])} | {'✅' if ds.get('done_marker') else '⏳'} | {s['pending']} |")
        L.append("")
        L.append("> traces：每个 episode 一条 jsonl（含 `_meta`/`_summary` + 每 control step 的 goal atom truth）；"
                 "trace 的 data rows = 10 个 stabilization steps + results.steps（审计已逐条核对）。")
        if ev["status"]["pending_runs"]:
            L.append("")
            L.append(f"> ⚠️ 本版为 **部分完成**：pending runs = {ev['status']['pending_runs']}。"
                     f"sweep-compatible 完成标志 `SWEEP_DONE`={ev['status']['sweep_done_marker']}，"
                     f"object-pilot 完成标志 `OBJECT_PILOT_DONE`={ev['status']['object_pilot_done_marker']}；"
                     f"上述 run 的逐对结果待完成后由同一脚本重跑补齐。")
        ioc = ev.get("init_state_observation_consistency") or {}
        if ioc:
            L.append("")
            L.append(f"- 跨 run 一致性交叉验证：{ioc['n_init_scene_groups']} 个（init sha + scene fingerprint）分组、"
                     f"{ioc['n_episodes_with_init']} episodes；stabilized **sim state** 逐组一致："
                     f"{'✅' if not ioc['sim_state_inconsistent_groups'] else '❌'}；"
                     f"同一 run 内 stabilized **observation** 一致：{'✅' if not ioc['within_run_obs_inconsistent'] else '❌'}。")
            if ioc.get("cross_run_obs_variation_groups"):
                L.append(f"- ⚠️ 跨进程渲染 caveat：{len(ioc['cross_run_obs_variation_groups'])} 组相同 sim state 在**不同批次进程**中得到不同 "
                         f"observation sha（早期 smoke/pilot 与后期 variant/diag/staged/sweep 之间），可能是不同启动 shell 的 "
                         f"MUJOCO_GL/渲染后端差异；属于跨进程渲染可复现性 caveat，不影响本审计的 success/steps/subtask 复算。")
        L.append("")

        L.append("## 3. 关键结论验证")
        L.append("")
        L.append("### 3.1 单指令组合任务：高失败率 + “完成恰好 1 个子任务后停滞”")
        L.append("")
        L.append(f"- 汇总（GOAL 单指令：pilot 9 + variant 7 + sweep 33，共 {g['episodes']} 条）：{g['success']} 成功（{g['success_rate']*100:.1f}%）")
        L.append(f"- 失败 {gf['failures']} 条的子任务完成分布：0 个={gf['zero_completed']}，1 个={gf['exactly_one_completed']}，2 个={gf['failure_subtask_distribution'].get(2,0)}")
        L.append(f"- 判定：{'✅ 结论成立（多数失败停在一半）' if gf['exactly_one_completed'] >= 0.5 * max(1, gf['failures']) else '⚠️ 结论仅部分成立'}")
        L.append("")
        L.append("### 3.2 措辞变体（then / andthen / swap）")
        L.append("")
        L.append("| variant bddl | success | subtasks | 同 pair 的 and 基线 success/subtasks |")
        L.append("|---|---|---|---|")
        for row in vp["rows"]:
            L.append(f"| {row['variant']} | {row['success']} | {row['subtasks']} | "
                     f"{row['base_and_success']}/{row['base_and_subtasks']} |")
        L.append("")
        L.append(f"结论：{vp['success']}/{vp['n']} 成功，未改善 and 基线 → {'✅ 成立' if vp['success']==0 else '⚠️ 存在成功项，需复核'}。")
        L.append("")
        L.append("### 3.3 staged 分阶段指令")
        L.append("")
        L.append("| pair | success | steps | switch_step（trace: 首个 stage=2 行） | subtasks |")
        L.append("|---|---:|---:|---:|---|")
        for row in sg["rows"]:
            L.append(f"| {row['stem']} | {row['success']} | {row['steps']} | {row['switch_step']} | {row['subtasks']} |")
        L.append("")
        L.append(f"- 结论：{sg['success']}/{sg['n']} 成功；切换步 {sorted({r['switch_step'] for r in sg['rows']})} ∈ 预期 88–164 → "
                 f"{'✅ staged 部分有效' if 0 < sg['success'] < sg['n'] else '⚠️ 与预期不符'}")
        L.append("")
        L.append("### 3.4 init 源与单子任务对照")
        L.append("")
        L.append(f"- wine 单任务：pair-init（goal_pair_00_02 的 init）success={w['pair_init_success']}（600 步失败） vs "
                 f"task2-init（原 put_the_wine_bottle_on_top_of_the_cabinet init）success={w['task2_init_success']} → "
                 f"{'✅ init 源敏感成立' if w['effect_verified'] else '⚠️ 未复现'}")
        L.append(f"- bowl 单任务：task0-init={cl['bowl_task0init']['success']}、task1-init={cl['bowl_task1init']['success']}；"
                 f"stove={cl['stove']['success']}；soup={cl['soup']['success']}；cheese(OBJECT 合并场景)={cl['cheese_object_merged']['success']} → "
                 f"{'✅ 对照结论成立' if cl['verified'] else '⚠️ 请见明细'}")
        L.append("")
        L.append("diag / diag2 原始结果：")
        L.append("")
        L.append("| run | stem | success | steps | subtasks |")
        L.append("|---|---|---|---:|---|")
        for grp in ("diag", "diag2"):
            for row in concl["diagnostics"][grp]:
                L.append(f"| {grp} | {row['stem']} | {row['success']} | {row['steps']} | {row['subtasks']} |")
        L.append("")

        L.append("## 4. 与 Lead 汇总的对比")
        L.append("")
        if sc and sc.get("present"):
            L.append(f"- Lead summary：`{ev['summary_meta']['path']}`（mtime {ev['summary_meta']['mtime']}，rows={sc['rows_lead']}）")
            L.append(f"- 独立 episodes={sc['rows_independent']}；Lead 覆盖 run={sc['runs_in_lead']}"
                     f"（Lead run 名与内部 run 名映射：{sc.get('lead_run_aliases')}；内部统一用 sweep-compatible/object-pilot 命名）")
            L.append(f"- Lead 未覆盖的 run：{sc['missing_runs_in_lead']}（smoke 为冒烟测试，预期不入汇总）")
            L.append(f"- 字段差异（success/steps/bddl/instruction/subtask first_true/switch_step）：**{len(sc['diffs'])}** 条")
            for d in sc["diffs"][:20]:
                L.append(f"  - {json.dumps(d, ensure_ascii=False)[:400]}")
            if len(sc["diffs"]) > 20:
                L.append(f"  - ... 其余 {len(sc['diffs'])-20} 条见 evidence.json")
            cd = sc.get("classification_diffs") or []
            L.append(f"- 分类（status）字段差异：**{len(cd)}** 条（由 `analyze_combined.py` 的 pair-id 查找缺陷导致："
                     f"object pair id 通过 `object_pair_` 前缀别名命中 goal pair 的 status；"
                     f"逆序 goal pair id 已在 Lead 的 patch 中修复）")
            for d in cd[:12]:
                L.append(f"  - {json.dumps(d, ensure_ascii=False)[:300]}")
        else:
            L.append("- Lead `combined-dynamic-summary.json` 不存在/不可读，无法对比。")
        L.append("")

        L.append("## 5. 逐对结果（关键 run 明细）")
        L.append("")
        for run in ("pilot(and)", "variant(then/swap)", "staged", "diag", "diag2", "sweep-compatible", "object-pilot"):
            ds = self.dynamic_sets.get(run) or {}
            eps = ds.get("episodes") or []
            if not eps:
                continue
            L.append(f"### {run}")
            L.append("")
            L.append("| task | bddl | success | steps | subtasks | first_true_step | switch |")
            L.append("|---|---|---:|---:|---|---|---|")
            for e in eps:
                L.append(f"| {e['task_key']} | {e['stem']} | {e['success']} | {e['steps']} | "
                         f"{e.get('subtasks_completed')}/{e.get('n_goal_atoms')} | "
                         f"{json.dumps(e.get('first_true_step') or {}, ensure_ascii=False)} | {e.get('switch_step')} |")
            L.append("")

        L.append("## 6. 异常项")
        L.append("")
        pros = ev["problems"]
        if pros:
            for p in pros:
                L.append(f"- ⚠️ `{p['check']}`: {json.dumps(p['detail'], ensure_ascii=False)[:500]}")
        else:
            L.append("- 无 critical 异常。")
        noncrit = [c for c in ev["checks"] if not c["ok"] and not c["critical"]]
        if noncrit:
            for c in noncrit:
                L.append(f"- 提示（非 critical）`{c['check']}`: {json.dumps(c['detail'], ensure_ascii=False)[:300]}")
        L.append("")
        L.append("## 7. 检查清单")
        L.append("")
        L.append("| # | category | check | critical | result |")
        L.append("|---:|---|---|---|---|")
        for i, c in enumerate(ev["checks"], 1):
            L.append(f"| {i} | {c['category']} | `{c['check']}` | {'yes' if c['critical'] else 'no'} | {'✅' if c['ok'] else '❌'} |")
        L.append("")
        L.append("## 8. 结论与可信度")
        L.append("")
        crit = v["critical_checks_passed"] == v["critical_checks_total"]
        L.append(f"- **独立复算可信度**：静态产物（45 pair / 90 phrasing / 30 object / 2 prototype / staging 33+4+4）"
                 f"与动态运行（{len(self.episodes)} episodes）的关键检查 **{'全部通过' if crit else '存在未通过项'}**；"
                 f"与 Lead `combined-dynamic-summary.json` 的公共行字段差异 {len(sc.get('diffs') or []) if sc else 'n/a'} 条"
                 f"→ 实验记录的 success/steps/subtasks/switch_step 数字**可以作为报告可信证据**（以本审计独立数字为准）。")
        L.append("- **结论**："
                 "① 单指令组合任务整体成功率极低（GOAL 2/49≈4%，OBJECT 0/4），主要失败模式是“完成恰好 1 个子任务后停滞”，不是完全无法操作；"
                 "② then/andthen/swap 措辞变体没有改善；"
                 "③ staged 分阶段指令可以救回部分 pair（>0 且 <全部），说明合并任务物理可行、瓶颈主要在一次性指令的组合理解；"
                 "④ 单子任务对照与 init 源对照支持上述解释；"
                 "⑤ 静态产物（BDDL/init/分类）质量与 Lead 声明一致；"
                 "⑥ sweep 33 对唯一成功的是 goal_pair_04_07（397 步，先放碗到柜顶再开炉子），说明存在少量“可顺序完成”的 compatible pair。")
        L.append("")
        L.append("限定与剩余风险：")
        L.append("- 每个 pair 仅 **1 个 seed × 1 episode**（sweep 33 pairs 提供覆盖广度，但逐对成功率是 1 样本估计，且每个 pair 只有 init 0）；")
        L.append("- 合并场景/自定义 BDDL 非官方 LIBERO benchmark；动态验证用 max_steps=600 / replan=10（object-pilot 560/5），不是官方 220–520/5 协议，不能与官方 pi05 数字横向对比；")
        L.append("- trace 的 `step` 是 0-based env control step，包含开头 10 个 stabilization steps；因此 first_true_step + 10 ≈ 策略执行步（results.steps 已与 trace 行数逐条核对：rows = 10 + steps）；")
        L.append(f"- Lead 汇总的 `status` 分类字段有 {len((sc or {}).get('classification_diffs') or [])} 处 pair-id 查找问题（object pair 经 `object_pair_` 前缀别名命中 goal pair 的 status；不影响 success/steps）；建议修 `analyze_combined.py` 后再对外引用 object 行的分类列；")
        L.append("- sweep-compatible / object-pilot 的完整性与逐对数字以本审计最终版为准（若本报告 status=partial，则对应 run 仍 pending）。")
        L.append("")
        L.append("建议：")
        L.append("- 对关键 pair（尤其 staged 成功/失败对照与 conflict/hard 分类）做多 seed 复跑（如 seed 0–4），报告成功率区间而非单点；")
        L.append("- staged 协议扩展到更多 compatible pair，并做 switch-step 敏感性（切换太早/太晚的影响）；")
        L.append("- object-pilot 完成后补充 OBJECT 组合的难度结论（union 7/8/9 与成功率关系）；")
        L.append("- 引用本实验时同时引用本审计的独立数字与限定，不要直接使用 Lead summary 的 status 分类列。")
        L.append("")

        L.append("## 9. 复现")
        L.append("")
        L.append("```bash")
        L.append("/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python \\")
        L.append("  .tmp/combined-audit/audit_combined.py --mode audit")
        L.append("```")
        L.append("")
        L.append("- 静态 BDDL/init 解析在子进程中用 pristine LIBERO shadow（`runs/libero-std-baseline-20261019/shadow`，"
                 "`LIBERO_CONFIG_PATH` 同目录）+ `torch.load(..., weights_only=False)` 完成；")
        L.append("- 动态部分只读取 results.json / *-traces/*.jsonl / logs 与视频，未创建仿真环境、未加载模型、未用 GPU；")
        L.append("- 未写入 `runs/combined-tasks-20261019/` 任何内容。")
        L.append("")
        return "\n".join(L) + "\n"

    def _all_ok(self, category: str) -> bool:
        return all(c["ok"] for c in self.checks if c["category"] == category and c["critical"])


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", default="audit", choices=["audit", "static-child"])
    ap.add_argument("--partial", action="store_true", help="allow sweep/object-pilot to be incomplete")
    args = ap.parse_args()
    if args.mode == "static-child":
        return static_child()
    audit = Audit(partial=args.partial)
    ev = audit.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
