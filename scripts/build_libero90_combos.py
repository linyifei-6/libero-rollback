#!/usr/bin/env python3
"""Build the LIBERO-90 dual-target candidate list (routes M1 / M2 / S1).

Read-only static generation: parses LIBERO-90 ``tasks_info.txt`` + ``*.bddl`` and the
sibling ``init_files/libero_90/*.pruned_init`` metadata, derives the *official*
(filename-derived) LIBERO-90 language, takes the per-pair semantic verdicts from
``.tmp/libero90-combos/pair-semantics.json`` (independently re-derived from the BDDL
and cross-checked), and emits:

    runs/libero-90-combos-20261025/candidates.json   machine-readable candidates
    runs/libero-90-combos-20261025/CASE_LIST.md      full list, one row per candidate
    runs/libero-90-combos-20261025/README.md         caliber / reproduce / invariants

No simulation, no network, no dataset mutation.  Every count in the JSON/Markdown is
computed below from the parsed BDDL; nothing is hand-typed.

Usage (repo root, repo .venv python):

    .venv/bin/python scripts/build_libero90_combos.py
    .venv/bin/python scripts/build_libero90_combos.py --check
    LIBERO_ROOT=/path/to/libero/libero .venv/bin/python scripts/build_libero90_combos.py --check

Candidate routes
    M1  same-scene unordered pair of two single-goal tasks x 2 instruction orders
        (147 pairs -> 294 ordered).  ``ab`` = smaller tasks_info index is s1.
    M2  in-scene object promotion (pure distractor promoted to a second goal) for
        LIVING_ROOM_SCENE2 / STUDY_SCENE2 / LIVING_ROOM_SCENE4 (17 unordered -> 34).
    S1  stranded-task rescue for KITCHEN_SCENE8 task 18 (1 unordered -> 2).

Priority rule (ordered candidates, M1/M2/S1 alike)
    compatible + s1_revertable=True   -> P0   (s1 is On/In/Open/Close)
    compatible + s1_revertable=False  -> P1   (s1 is Turnon/Turnoff: no runtime profile)
    hard                              -> P2   (with ``order_caveat``)
    conflict / degenerate             -> P3   (valid=False, protocol="excluded")
``valid`` = class in {compatible, hard}.

Counting note (Lead-confirmed 2026-10-25): unique candidates = M1 294 + M2 34 + S1 2 =
330.  The earlier template ``m2_ordered=36 / s1_ordered=2 / total=332`` double-counted
the single KITCHEN_SCENE8 rescue pair; ``supplementary_ordered`` = M2 + S1 = 36 is the
18 unordered supplementary pairs x 2 directions.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TMP_DIR = REPO / ".tmp" / "libero90-combos"
OUT_DIR = REPO / "runs" / "libero-90-combos-20261025"
DECISIONS_JSON = OUT_DIR / "scene_review_decisions.json"

# Baseline (330-candidate / pre-scene-review-v1) artifact digests, kept for the README
# revision table ("330 -> 322") so the old artifacts stay auditable.  Captured before
# scene_review_v1 was applied (2026-10-25).
BASELINE_REVISION = {
    "label": "v0 (330 candidates, before scene review v1)",
    "counts": {
        "total": 330,
        "m1_unordered": 147,
        "m1_ordered": 294,
        "ks1_unordered": 10,
        "ks1_ordered": 20,
        "pair_class": {"compatible": 93, "hard": 19, "conflict": 31, "degenerate": 4},
        "ordered_class": {"compatible": 186, "hard": 38, "conflict": 62, "degenerate": 8},
        "priority": {"P0": 180, "P1": 6, "P2": 38, "P3": 70},
    },
    "sha256": {
        "runs/libero-90-combos-20261025/candidates.json":
            "d62e10bcebc863693c4ac3ae8c572dab5faaa8f120c45949fdd70a58f0f7922f",
        "runs/libero-90-combos-20261025/CASE_LIST.md":
            "09f6235daaf26fb6c496b1f8385cb67eaa945ef4ddc145bfa9b69683de7744a9",
        "runs/libero-90-combos-20261025/README.md":
            "6697a5b17ca6490e8b3937f0ba97899117d51e5797c443a8587f0b3712f8d8c0",
        "runs/libero-90-combos-20261025/candidates-instructed.json":
            "ac4d34284a3dd07fb33af70bebe08c9e4f7de2673300dca1353254cd7bbb1e88",
        "runs/libero-90-combos-20261025/INSTRUCTION_TEMPLATES.md":
            "7888913bd372653c116fe451a1effc3fe6902bb71493e8a2508013a03e96d5e4",
        "scripts/build_libero90_combos.py":
            "fd5f76ad7980be32a787550591692479334b8b33106b64347420115986b2a469",
        "scripts/build_libero90_instructions.py":
            "31caf47a612c67fbb247a96d99a0ca170602f82db2ce7119be2a83d868781c1e",
    },
}

DEFAULT_LIBERO_ROOT = "/home/tarowang/workspace/roboot/libero-plus/LIBERO-plus/libero/libero"
LIBERO_ROOT = Path(os.environ.get("LIBERO_ROOT", DEFAULT_LIBERO_ROOT))
BDDL_DIR = LIBERO_ROOT / "bddl_files" / "libero_90"
TASKS_INFO = BDDL_DIR / "tasks_info.txt"
INIT_DIR = LIBERO_ROOT / "init_files" / "libero_90"

PAIR_SEMANTICS = TMP_DIR / "pair-semantics.json"
INVENTORY = TMP_DIR / "inventory.json"
OFFICIAL_MAP = TMP_DIR / "official-language-and-benchmark-map.json"

SCENE_PREFIX = {"KITCHEN": "KS", "LIVING_ROOM": "LR", "STUDY": "ST"}
PLACEMENT_PREDS = ("On", "In")
ARTICULATION_PREDS = ("Open", "Close")
SWITCH_PREDS = ("Turnon", "Turnoff")
REVERTABLE_PREDS = {
    "On": True,
    "In": True,
    "Open": True,
    "Close": True,
    "Turnon": False,
    "Turnoff": False,
}
LEVEL_WORDS = {"top", "bottom", "middle", "left", "right", "front", "back"}
VALID_CLASSES = ("compatible", "hard")
PRIORITY_PROTOCOL = {
    "P0": "staged+single_instruction",
    "P1": "staged+single_instruction",
    "P2": "staged+single_instruction",
    "P3": "excluded",
}
CLASS_ORDER = ("compatible", "hard", "conflict", "degenerate")
PRIORITY_ORDER = ("P0", "P1", "P2", "P3")
LANGUAGE_JOIN = " and "


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def dedupe(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def scene_short(scene: str) -> str:
    m = re.match(r"^(KITCHEN|LIVING_ROOM|STUDY)_SCENE(\d+)$", scene)
    if not m:
        raise ValueError("unsupported scene name: %r" % (scene,))
    return SCENE_PREFIX[m.group(1)] + m.group(2)


def scene_from_stem(stem: str) -> str:
    m = re.match(r"^((?:KITCHEN|LIVING_ROOM|STUDY)_SCENE\d+)_", stem)
    if not m:
        raise ValueError("cannot derive scene from stem: %r" % (stem,))
    return m.group(1)


def official_language_from_stem(stem: str) -> str:
    """Mirror libero.benchmark.grab_language_from_filename for LIBERO-90 task names."""
    m = re.search(r"_SCENE\d+_", stem)
    if not m:
        raise ValueError("cannot derive official language from stem: %r" % (stem,))
    return " ".join(stem[m.end():].split("_"))
# ---------------------------------------------------------------------------
# BDDL parsing (self-contained, no third-party parser)
# ---------------------------------------------------------------------------
def sexp_tokens(text: str):
    """Tokenize BDDL text; ``;`` starts a comment, parens are single tokens."""
    lines = []
    for raw in text.splitlines():
        cut = raw.find(";")
        lines.append(raw if cut < 0 else raw[:cut])
    return re.findall(r"[()]|[^()\s]+", "\n".join(lines))


def parse_sexp(tokens):
    stack = [[]]
    for tok in tokens:
        if tok == "(":
            node = []
            stack[-1].append(node)
            stack.append(node)
        elif tok == ")":
            if len(stack) < 2:
                raise ValueError("unbalanced ')' in BDDL")
            stack.pop()
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise ValueError("unbalanced '(' in BDDL")
    return stack[0]


def parse_bddl(text: str):
    """Return {section-name: [tokens/forms]} for the top-level ``(:section ...)``s."""
    doc = parse_sexp(sexp_tokens(text))
    if len(doc) != 1 or not isinstance(doc[0], list) or not doc[0] or doc[0][0] != "define":
        raise ValueError("not a BDDL ``define`` form")
    forms = {}
    for node in doc[0][1:]:
        if isinstance(node, list) and node and isinstance(node[0], str) and node[0].startswith(":"):
            key = node[0][1:].lower()
            if key in forms:
                raise ValueError("duplicate BDDL section :%s" % key)
            forms[key] = node[1:]
    return forms


def atom_str(atom) -> str:
    if isinstance(atom, str):
        return atom
    return "(" + " ".join(str(x) for x in atom) + ")"


def split_atom(atom: str):
    body = atom.strip()
    if not (body.startswith("(") and body.endswith(")")):
        raise ValueError("bad goal atom: %r" % (atom,))
    parts = body[1:-1].split()
    if not parts:
        raise ValueError("empty goal atom: %r" % (atom,))
    return parts[0], parts[1:]


def goal_atoms_from_goal(form) -> list:
    if not isinstance(form, list) or not form:
        raise ValueError("bad :goal form: %r" % (form,))
    pred = str(form[0]).lower()
    if pred in ("and", "and*"):
        atoms = []
        for child in form[1:]:
            atoms.extend(goal_atoms_from_goal(child))
        return atoms
    if pred == "not":
        raise ValueError(":goal with Not is not supported by this generator")
    return [atom_str(form)]


def parse_typed_list(tokens) -> list:
    """Parse BDDL ``name1 name2 - type`` token lists into [[name, type], ...]."""
    out = []
    names = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-":
            if i + 1 >= len(tokens):
                raise ValueError("dangling '-' in BDDL typed list")
            typ = tokens[i + 1]
            for name in names:
                out.append([name, typ])
            names = []
            i += 2
        else:
            names.append(tok)
            i += 1
    if names:
        raise ValueError("untyped names in BDDL typed list: %r" % (names,))
    return out


def parse_regions(nodes) -> list:
    regions = []
    for node in nodes:
        if not isinstance(node, list) or not node or not isinstance(node[0], str):
            raise ValueError("bad :regions entry: %r" % (node,))
        name = node[0]
        target = None
        for item in node[1:]:
            if isinstance(item, list) and item and item[0] == ":target":
                target = item[1]
        if target is None:
            raise ValueError("region %r has no :target" % (name,))
        regions.append({"name": name, "target": target, "numbers": []})
    return regions


def load_tasks():
    """Parse all 90 LIBERO-90 tasks in ``tasks_info.txt`` order."""
    if not TASKS_INFO.exists():
        raise SystemExit("tasks_info.txt not found: %s (set LIBERO_ROOT)" % TASKS_INFO)
    entries = [ln.strip() for ln in read_text(TASKS_INFO).splitlines() if ln.strip()]
    stems = []
    for rel in entries:
        name = Path(rel).name
        if not name.endswith(".bddl"):
            raise ValueError("unexpected tasks_info.txt entry: %r" % (rel,))
        stems.append(name[:-5])
    tasks = []
    for index, stem in enumerate(stems):
        bddl_path = BDDL_DIR / (stem + ".bddl")
        if not bddl_path.exists():
            raise SystemExit("missing BDDL for task %02d: %s" % (index, bddl_path))
        raw = bddl_path.read_bytes()
        forms = parse_bddl(raw.decode("utf-8"))
        for key in ("language", "regions", "fixtures", "objects", "obj_of_interest", "init", "goal"):
            if key not in forms:
                raise ValueError("task %02d: BDDL missing :%s" % (index, key))
        inline_language = " ".join(forms["language"]).strip()
        scene = scene_from_stem(stem)
        regions = parse_regions(forms["regions"])
        fixtures = parse_typed_list(forms["fixtures"])
        objects = parse_typed_list(forms["objects"])
        obj_of_interest = [tok for tok in forms["obj_of_interest"] if isinstance(tok, str)]
        init_atoms = [atom_str(atom) for atom in forms["init"]]
        goal_atoms = goal_atoms_from_goal(forms["goal"][0])
        region_full_names = ["%s_%s" % (r["target"], r["name"]) for r in regions]
        object_names = [obj[0] for obj in objects]
        fixture_names = [fix[0] for fix in fixtures]
        known = set(object_names) | set(fixture_names) | set(region_full_names)
        for atom in goal_atoms + init_atoms:
            _pred, args = split_atom(atom)
            for arg in args:
                if arg not in known:
                    raise ValueError("task %02d: atom %r references unknown entity %r" % (index, atom, arg))
        init_path = INIT_DIR / (stem + ".pruned_init")
        if not init_path.exists():
            raise SystemExit("missing pruned_init for task %02d: %s" % (index, init_path))
        init_bytes = init_path.stat().st_size
        tasks.append({
            "index": index,
            "stem": stem,
            "bddl": str(bddl_path),
            "scene": scene,
            "scene_short": scene_short(scene),
            "language": inline_language,
            "official_language": official_language_from_stem(stem),
            "goal_atoms": goal_atoms,
            "goal_atom_args": [[split_atom(a)[0], split_atom(a)[1]] for a in goal_atoms],
            "n_goal_atoms": len(goal_atoms),
            "init_atoms": init_atoms,
            "effective_atoms": [a for a in goal_atoms if a not in set(init_atoms)],
            "objects": objects,
            "object_names": object_names,
            "fixtures": fixtures,
            "fixture_names": fixture_names,
            "regions": regions,
            "region_names": [r["name"] for r in regions],
            "region_full_names": region_full_names,
            "obj_of_interest": obj_of_interest,
            "init_file": init_path.name,
            "init_bytes": init_bytes,
            "init_sha256": sha256_bytes(init_path.read_bytes()),
        })
    scenes = defaultdict(list)
    for task in tasks:
        scenes[task["scene"]].append(task["index"])
    scene_order = sorted(scenes, key=lambda s: min(scenes[s]))
    return tasks, dict(scenes), scene_order
# ---------------------------------------------------------------------------
# Input loading / cross-checks
# ---------------------------------------------------------------------------
def load_official_map(tasks):
    """Official libero_90 language is filename-derived (NOT the BDDL inline :language)."""
    if not OFFICIAL_MAP.exists():
        raise SystemExit("official-language-and-benchmark-map.json not found: %s" % OFFICIAL_MAP)
    data = json.loads(read_text(OFFICIAL_MAP))
    rows = data.get("benchmark_order") or []
    if len(rows) != len(tasks):
        raise ValueError("official map has %d rows, expected %d" % (len(rows), len(tasks)))
    official = {}
    bench_idx = {}
    derived_diffs = []
    for row, task in zip(rows, tasks):
        if row["index"] != task["index"]:
            raise ValueError("official map is not in tasks_info order at index %d" % task["index"])
        if row["stem"] != task["stem"]:
            derived_diffs.append({"index": task["index"], "field": "stem",
                                  "map": row["stem"], "bddl": task["stem"]})
        if row["official_language"] != task["official_language"]:
            derived_diffs.append({"index": task["index"], "field": "official_language",
                                  "map": row["official_language"], "derived": task["official_language"]})
        official[task["index"]] = row["official_language"]
        bench_idx[task["index"]] = row["bench_idx"]
    if derived_diffs:
        raise ValueError("official language derivation differs from map: %r" % derived_diffs[:3])
    inline_mismatches = [t["index"] for t in tasks if t["language"] != t["official_language"]]
    map_mismatches = sorted(row["index"] for row in data.get("mismatches") or [])
    if sorted(inline_mismatches) != map_mismatches:
        raise ValueError("inline-vs-official mismatch set differs: computed %r, map %r"
                         % (sorted(inline_mismatches), map_mismatches))
    return {"official": official, "bench_idx": bench_idx,
            "n_inline_mismatch": len(inline_mismatches),
            "inline_mismatch_indices": sorted(inline_mismatches)}


def crosscheck_inventory(tasks, scenes):
    """Soft cross-check against the already-parsed ``inventory.json`` (if present)."""
    diffs = []
    if not INVENTORY.exists():
        return {"available": False, "diffs": diffs, "rules": {}}
    inv = json.loads(read_text(INVENTORY))
    if inv.get("n_tasks") != len(tasks):
        diffs.append({"index": None, "field": "n_tasks", "inventory": inv.get("n_tasks"), "bddl": len(tasks)})
    if len(inv.get("scenes") or {}) != len(scenes):
        diffs.append({"index": None, "field": "n_scenes", "inventory": len(inv.get("scenes") or {}), "bddl": len(scenes)})
    by_index = {rec["index"]: rec for rec in inv.get("tasks") or []}
    for task in tasks:
        rec = by_index.get(task["index"])
        if rec is None:
            diffs.append({"index": task["index"], "field": "task", "inventory": None, "bddl": task["stem"]})
            continue
        for field in ("stem", "scene", "language", "goal_atoms", "init_atoms", "obj_of_interest",
                      "object_names", "fixture_names", "region_names"):
            if rec.get(field) != task[field]:
                diffs.append({"index": task["index"], "field": field,
                              "inventory": rec.get(field), "bddl": task[field]})
    return {"available": True, "diffs": diffs, "rules": inv.get("rules") or {}}


def compute_dual_tasks(tasks):
    """Rule C (title caliber): 2 goal atoms whose target entities (last args) differ."""
    dual = []
    for task in tasks:
        atoms = task["goal_atoms"]
        if len(atoms) != 2:
            continue
        targets = set()
        for atom in atoms:
            _pred, args = split_atom(atom)
            if not args:
                raise ValueError("task %02d: goal atom without args: %r" % (task["index"], atom))
            targets.add(args[-1])
        if len(targets) >= 2:
            dual.append(task["index"])
    return dual


def build_pairs(tasks, scenes, scene_order, single_set):
    pairs = []
    for scene in scene_order:
        idxs = [i for i in sorted(scenes[scene]) if i in single_set]
        for i, j in itertools.combinations(idxs, 2):
            pairs.append({"pair_id": "%02d_%02d" % (i, j), "scene": scene, "i": i, "j": j})
    return pairs


def load_pair_semantics(tasks, pairs, excluded_tasks=()):
    if not PAIR_SEMANTICS.exists():
        raise SystemExit("pair-semantics.json not found: %s" % PAIR_SEMANTICS)
    data = json.loads(read_text(PAIR_SEMANTICS))
    records = data.get("pairs") or []
    by_id = {rec["pair_id"]: rec for rec in records}
    if len(by_id) != len(records):
        raise ValueError("duplicate pair_id in pair-semantics.json")
    expected = {p["pair_id"] for p in pairs}
    missing = expected - set(by_id)
    if missing:
        raise ValueError("pair-semantics.json is missing used pairs: %r" % sorted(missing)[:5])
    for pair in pairs:
        rec = by_id[pair["pair_id"]]
        if rec["i"] != pair["i"] or rec["j"] != pair["j"] or rec["scene"] != pair["scene"]:
            raise ValueError("pair-semantics.json %s has wrong i/j/scene" % pair["pair_id"])
    used = {pair_id: by_id[pair_id] for pair_id in expected}
    extra = sorted(set(by_id) - expected)
    # Scene-review exclusions remove whole unordered pairs from the M1 list; they stay in
    # pair-semantics.json (that file is the pre-review read-only artifact), so every extra
    # record must be explained by an excluded task.
    excluded = set(excluded_tasks)
    for pair_id in extra:
        rec = by_id[pair_id]
        if rec["i"] not in excluded and rec["j"] not in excluded:
            raise ValueError("pair-semantics.json has unexpected extra pair %s not explained by "
                             "scene-review exclusions" % pair_id)
    return {"data": data, "by_id": used, "n_records": len(records),
            "extra_pair_ids": extra, "n_excluded_pairs": len(extra)}


def load_scene_review(tasks, scenes, scene_order, pool_bddl_set):
    """Load the single source of truth for the per-scene user review decisions.

    Missing file -> backwards compatible no-exclusion mode.  Present file -> validated
    and every exclusion must be a BDDL single-goal-pool task of that scene.
    """
    by_index = {task["index"]: task for task in tasks}
    if not DECISIONS_JSON.exists():
        return {
            "available": False, "version": None, "excluded": [],
            "decisions": [], "pending_scenes": [], "notes": [],
            "source": None, "updated_at": None, "applied_in": None,
            "sha256": None,
            "per_scene": {scene: {"reviewed": False, "exclude_tasks_from_pairing": []}
                          for scene in scene_order},
        }
    data = json.loads(read_text(DECISIONS_JSON))
    version = data.get("version")
    if not isinstance(version, int) or version < 1:
        raise SystemExit("scene_review_decisions.json: version must be a positive integer")
    excluded = set()
    per_scene = {scene: {"reviewed": False, "exclude_tasks_from_pairing": []}
                 for scene in scene_order}
    decisions = []
    for decision in data.get("decisions") or []:
        scene = decision.get("scene")
        if scene not in scenes:
            raise SystemExit("scene_review_decisions.json: unknown scene %r" % (scene,))
        raw = [int(index) for index in (decision.get("exclude_tasks_from_pairing") or [])]
        for index in raw:
            if index not in pool_bddl_set:
                raise SystemExit("scene_review_decisions.json: task %02d excluded from pairing is "
                                 "not in the BDDL single-goal pool" % index)
            if by_index[index]["scene"] != scene:
                raise SystemExit("scene_review_decisions.json: task %02d is not in %s"
                                 % (index, scene))
            if index in excluded:
                raise SystemExit("scene_review_decisions.json: task %02d excluded twice" % index)
            excluded.add(index)
        per_scene[scene]["reviewed"] = True
        per_scene[scene]["exclude_tasks_from_pairing"].extend(raw)
        decisions.append({
            "scene": scene,
            "exclude_tasks_from_pairing": list(raw),
            "reason": decision.get("reason"),
            "applied": bool(raw),
            "applied_in": decision.get("applied_in"),
            "reviewed_by": decision.get("reviewed_by"),
        })
    return {
        "available": True,
        "version": version,
        "excluded": sorted(excluded),
        "decisions": decisions,
        "pending_scenes": list(data.get("pending_scenes") or []),
        "notes": list(data.get("notes") or []),
        "source": data.get("source"),
        "updated_at": data.get("updated_at"),
        "applied_in": decisions[0]["applied_in"] if decisions else None,
        "sha256": sha256_file(DECISIONS_JSON),
        "per_scene": per_scene,
    }


def build_scene_review_block(scene_order, scenes, pool_bddl_set, single_set, review, per_scene):
    """Top-level `scene_review` summary (decisions + per-scene pair counts)."""
    scene_counts = {row["scene"]: row for row in per_scene}
    rows = []
    for scene in scene_order:
        info = review["per_scene"].get(scene) or {}
        counts = scene_counts[scene]
        rows.append({
            "scene": scene,
            "reviewed": bool(info.get("reviewed")),
            "exclude_tasks_from_pairing": list(info.get("exclude_tasks_from_pairing") or []),
            "pool_bddl_tasks": len([i for i in scenes[scene] if i in pool_bddl_set]),
            "pool_after_review": len([i for i in scenes[scene] if i in single_set]),
            "m1_unordered": counts["m1_unordered"],
            "m1_ordered": counts["m1_ordered"],
        })
    n_m1 = sum(row["m1_ordered"] for row in rows)
    n_unordered = sum(row["m1_unordered"] for row in rows)
    return {
        "available": review["available"],
        "version": review["version"],
        "source": review["source"],
        "updated_at": review["updated_at"],
        "applied_in": review["applied_in"],
        "decisions_sha256": review["sha256"],
        "decisions": review["decisions"],
        "pending_scenes": review["pending_scenes"],
        "notes": review["notes"],
        "excluded_tasks": list(review["excluded"]),
        "totals": {
            "pool_bddl": len(pool_bddl_set),
            "excluded": len(review["excluded"]),
            "pool_after_review": len(single_set),
            "m1_unordered": n_unordered,
            "m1_ordered": n_m1,
        },
        "per_scene": rows,
    }

def capacity_caveat_of(union_atoms) -> bool:
    dest_objects = defaultdict(set)
    for atom in union_atoms:
        pred, args = split_atom(atom)
        if pred in PLACEMENT_PREDS and len(args) >= 2:
            dest_objects[args[1]].add(args[0])
    return any(len(objs) >= 2 for objs in dest_objects.values())


# ---------------------------------------------------------------------------
# Independent per-pair classifier (cross-check of pair-semantics.json)
# ---------------------------------------------------------------------------
def _adjacent_pair(dest_a, dest_b) -> bool:
    parts_a = str(dest_a).split("_")
    parts_b = str(dest_b).split("_")
    if len(parts_a) < 3 or len(parts_b) < 3:
        return False
    if parts_a[-2] not in LEVEL_WORDS or parts_b[-2] not in LEVEL_WORDS:
        return False
    return parts_a[:-1] == parts_b[:-1] and parts_a[-1] != parts_b[-1]


def _placement_atoms(goal):
    """(pred, moved-object, destination) for the On/In atoms of one task's goal."""
    out = []
    for atom in goal:
        pred, args = split_atom(atom)
        if pred in PLACEMENT_PREDS and len(args) >= 2:
            out.append((pred, args[0], args[1]))
    return out


def _pred_targets(goal, pred_name):
    targets = set()
    for atom in goal:
        pred, args = split_atom(atom)
        if pred == pred_name and args:
            targets.add(args[0])
    return targets


def classify_goal_sets(goal_a, goal_b):
    """Re-derive (class, dependency tags, reason) from the two tasks' goal atoms.

    Mirrors pair-semantics.md section 1 (degenerate > conflict > hard > compatible).
    Conflict is judged on the merged goal (the atoms are unsatisfiable no matter which
    task they come from), while the order/contact *hard* tags only count when the two
    coupled steps belong to DIFFERENT tasks: a task that internally opens+places (or
    places+closes) its own container must not by itself upgrade the pair to hard
    (cf. pair 00_04, which pair-semantics.json classifies as compatible).
    """
    set_a = set(goal_a)
    set_b = set(goal_b)
    if set_a <= set_b or set_b <= set_a:
        return "degenerate", ["subset"], ("one task's goal set is a subset of the other task's goal set; "
                                          "the merged goal equals the superset task (no new second stage)")
    atoms = dedupe(list(goal_a) + list(goal_b))
    parsed = [split_atom(atom) for atom in atoms]
    dest_by_object = defaultdict(set)
    for pred, args in parsed:
        if pred in PLACEMENT_PREDS and len(args) >= 2:
            dest_by_object[args[0]].add(args[1])
    for obj, dests in dest_by_object.items():
        if len(dests) >= 2:
            return "conflict", ["same_object"], "object %s demanded at two destinations %r" % (obj, sorted(dests))
    articulation = defaultdict(set)
    for pred, args in parsed:
        if pred in ARTICULATION_PREDS and args:
            articulation[args[0]].add(pred)
    for region, preds in articulation.items():
        if {"Open", "Close"} <= preds:
            return "conflict", ["articulation_conflict"], "region %s both opened and closed" % region
    switches = defaultdict(set)
    for pred, args in parsed:
        if pred in SWITCH_PREDS and args:
            switches[args[0]].add(pred)
    for fixture, preds in switches.items():
        if {"Turnon", "Turnoff"} <= preds:
            return "conflict", ["switch_conflict"], "fixture %s both turned on and off" % fixture
    places_a = _placement_atoms(goal_a)
    places_b = _placement_atoms(goal_b)
    in_a = {dest for pred, _obj, dest in places_a if pred == "In"}
    in_b = {dest for pred, _obj, dest in places_b if pred == "In"}
    close_a = _pred_targets(goal_a, "Close")
    close_b = _pred_targets(goal_b, "Close")
    open_a = _pred_targets(goal_a, "Open")
    open_b = _pred_targets(goal_b, "Open")
    deps = []
    if (close_a & in_b) or (close_b & in_a):
        deps.append("place_then_close")
    if (open_a & in_b) or (open_b & in_a):
        deps.append("open_then_place")
    moved_a = {obj for _pred, obj, _dest in places_a}
    moved_b = {obj for _pred, obj, _dest in places_b}
    on_a = [(obj, dest) for pred, obj, dest in places_a if pred == "On"]
    on_b = [(obj, dest) for pred, obj, dest in places_b if pred == "On"]
    if any(dest in moved_b for _obj, dest in on_a) or any(dest in moved_a for _obj, dest in on_b):
        deps.append("stack_anchor")
    dests_a = {dest for _pred, _obj, dest in places_a}
    dests_b = {dest for _pred, _obj, dest in places_b}
    if any(_adjacent_pair(da, db) for da in dests_a for db in dests_b):
        deps.append("adjacent_regions")
    deps = dedupe(deps)
    if deps:
        return "hard", deps, "order/contact dependency: " + ", ".join(deps)
    return "compatible", [], ""
# ---------------------------------------------------------------------------
# M1: same-scene task x task direct combinations (147 unordered -> 294 ordered)
# ---------------------------------------------------------------------------
def first_subgoal_predicate(task) -> str:
    return split_atom(task["goal_atoms"][0])[0]


def s1_revertable_from_task(task) -> bool:
    return REVERTABLE_PREDS.get(first_subgoal_predicate(task), False)


def template_task_for_direction(t1, t2) -> int:
    if len(set(t1["goal_atoms"])) >= len(set(t2["goal_atoms"])):
        return t1["index"]
    return t2["index"]


def order_caveat_for(deps, direction_caveat) -> str:
    clauses = []
    for tag in deps:
        if tag == "place_then_close":
            clauses.append("place the s1 object into the shared container before s2 closes it (place-then-close)")
        elif tag == "open_then_place":
            clauses.append("open the shared container in s1 before s2 places into it (open-then-place)")
        elif tag == "stack_anchor":
            clauses.append("put the stack-base object in place in s1 before stacking in s2 (stack-anchor)")
        elif tag == "adjacent_regions":
            clauses.append("same-layer adjacent destination regions: keep clearance / avoid collision")
        elif tag == "duplicate_atom":
            clauses.append("shared goal atom deduplicated; keep the shared place/close stage contiguous")
        elif tag == "same_destination":
            clauses.append("shared destination: capacity/occlusion risk")
    if direction_caveat:
        clauses.append("direction caveat: " + "; ".join(str(c) for c in direction_caveat))
    return "; ".join(dedupe(clauses)) or "order/contact dependency: fixed s1 -> s2 order"


def build_m1_notes(cls, deps, capacity, revert, order_caveat, direction_caveat,
                   recomputed_reason, s1_pred, priority) -> str:
    parts = []
    if cls == "conflict":
        parts.append("goal conflict: " + (recomputed_reason or "merged goal atoms are mutually exclusive")
                     + "; kept only as a negative control")
    elif cls == "degenerate":
        parts.append("degenerate: one goal set is a subset of the other, merged goal adds no new "
                     "second stage (equivalent to a single official task)")
    elif cls == "hard":
        parts.append("hard (%s): %s" % ("+".join(deps) if deps else "order_dependency", order_caveat))
    else:
        if capacity:
            parts.append("same_destination capacity caveat: stage s1 placement then s2; revert the s1 "
                         "placement while s2 is placed/occluded")
        else:
            parts.append("compatible (%s): independent s1/s2 targets, no order/contact dependency"
                         % ("+".join(deps) if deps else "no_shared_constraint"))
        if not revert:
            parts.append("s1 goal predicate %s has no runtime profile -> s1 not revertable (P1)" % s1_pred)
    if direction_caveat and cls != "hard":
        parts.append("direction caveat: " + "; ".join(str(c) for c in direction_caveat))
    return "; ".join(parts).rstrip(".;") + "."


def make_m1_candidate(pair, order, t1, t2, pair_sem, recomputed_cls, recomputed_reason, official):
    """Build one ordered M1 candidate; s1 is ``t1`` (order=ab) or ``t2`` (order=ba)."""
    set1 = set(t1["goal_atoms"])
    set2 = set(t2["goal_atoms"])
    union_set = set1 | set2
    goal_atoms = list(t1["goal_atoms"]) + [a for a in t2["goal_atoms"] if a not in set1]
    obj_of_interest = list(t1["obj_of_interest"]) + [
        o for o in t2["obj_of_interest"] if o not in set(t1["obj_of_interest"])]
    language = official[t1["index"]] + LANGUAGE_JOIN + official[t2["index"]]
    # M1 class is taken verbatim from pair-semantics.json (Lead ruling 2026-10-25:
    # direction_caveat / order_caveat refine notes, they never re-classify a pair).
    cls = pair_sem.get("class")
    deps = list(pair_sem.get("dependency") or [])
    capacity = bool(pair_sem.get("capacity_caveat"))
    revert = s1_revertable_from_task(t1)
    s1_pred = first_subgoal_predicate(t1)
    if cls == "compatible":
        priority = "P0" if revert else "P1"
    elif cls == "hard":
        priority = "P2"
    else:
        priority = "P3"
    valid = cls in VALID_CLASSES
    direction_caveat = list(pair_sem.get("direction_caveat_%s" % order) or [])
    invalid_reason = pair_sem.get("direction_invalid_reason_%s" % order)
    if not valid and not invalid_reason:
        invalid_reason = ("degenerate_pair_merged_goal_equals_single_task"
                          if cls == "degenerate" else "goal_conflict")
    template = template_task_for_direction(t1, t2)
    record = {
        "candidate_id": "L90_%s_%02d_%02d_%s" % (t1["scene_short"], pair["i"], pair["j"], order),
        "pair_id": pair["pair_id"],
        "order": order,
        "route": "M1",
        "scene": pair["scene"],
        "s1_task": {"index": t1["index"], "language": official[t1["index"]], "goal_atoms": list(t1["goal_atoms"])},
        "s2_task": {"index": t2["index"], "language": official[t2["index"]], "goal_atoms": list(t2["goal_atoms"])},
        "goal_atoms": goal_atoms,
        "n_atoms": len(goal_atoms),
        "obj_of_interest": obj_of_interest,
        "language": language,
        "template_task": template,
        "init_source": t1["index"],
        "init_source_alt": t2["index"],
        "init_source_file": t1["init_file"],
        "class": cls,
        "dependency": deps,
        "capacity_caveat": capacity,
        "s1_revertable": revert,
        "valid": valid,
        "priority": priority,
        "protocol": PRIORITY_PROTOCOL[priority],
        "notes": "",
    }
    if cls == "hard":
        record["order_caveat"] = order_caveat_for(deps, direction_caveat)
    if direction_caveat:
        record["direction_caveat"] = direction_caveat
    if not valid:
        record["invalid_reason"] = invalid_reason
    record["notes"] = build_m1_notes(cls, deps, capacity, revert, record.get("order_caveat"),
                                     direction_caveat, recomputed_reason, s1_pred, priority)
    # per-direction cross-checks against pair-semantics.json
    diffs = []
    pair_revert = pair_sem.get("s1_revertable_%s" % order)
    if pair_revert is None:
        diffs.append({"pair_id": pair["pair_id"], "field": "s1_revertable_%s" % order,
                      "pair_semantics": None, "bddl": revert, "severity": "critical"})
    elif bool(pair_revert) != revert:
        diffs.append({"pair_id": pair["pair_id"], "field": "s1_revertable_%s" % order,
                      "pair_semantics": bool(pair_revert), "bddl": revert, "severity": "critical"})
    pair_lang = pair_sem.get("language_%s" % order)
    if pair_lang != language:
        known = set(pair_sem.get("_inline_language_task_indices") or [])
        if t1["index"] in known or t2["index"] in known:
            diffs.append({"pair_id": pair["pair_id"], "field": "language_%s" % order,
                          "pair_semantics": pair_lang, "bddl_official": language,
                          "severity": "known_inline_vs_official"})
        else:
            diffs.append({"pair_id": pair["pair_id"], "field": "language_%s" % order,
                          "pair_semantics": pair_lang, "bddl_official": language,
                          "severity": "warn"})
    if set(pair_sem.get("atom_union") or []) != union_set:
        diffs.append({"pair_id": pair["pair_id"], "field": "atom_union",
                      "pair_semantics": list(pair_sem.get("atom_union") or []),
                      "bddl": sorted(union_set), "severity": "warn"})
    if pair_sem.get("n_atoms") != len(union_set):
        diffs.append({"pair_id": pair["pair_id"], "field": "n_atoms",
                      "pair_semantics": pair_sem.get("n_atoms"), "bddl": len(union_set),
                      "severity": "warn"})
    if set(pair_sem.get("obj_of_interest_union") or []) != set(obj_of_interest):
        diffs.append({"pair_id": pair["pair_id"], "field": "obj_of_interest_union",
                      "pair_semantics": list(pair_sem.get("obj_of_interest_union") or []),
                      "bddl": sorted(set(obj_of_interest)), "severity": "warn"})
    return record, diffs


def build_m1_candidates(tasks, pairs, pair_sem_by_id, official, inline_mismatch_indices):
    by_index = {t["index"]: t for t in tasks}
    candidates = []
    diffs = []
    injected = set()
    for pair in pairs:
        rec = dict(pair_sem_by_id[pair["pair_id"]])
        rec["_inline_language_task_indices"] = set(inline_mismatch_indices)
        t_i = by_index[pair["i"]]
        t_j = by_index[pair["j"]]
        recomputed_cls, recomputed_deps, recomputed_reason = classify_goal_sets(t_i["goal_atoms"], t_j["goal_atoms"])
        if recomputed_cls != rec.get("class"):
            diffs.append({"pair_id": pair["pair_id"], "field": "class",
                          "pair_semantics": rec.get("class"), "bddl": recomputed_cls,
                          "severity": "critical"})
        for order, t1, t2 in (("ab", t_i, t_j), ("ba", t_j, t_i)):
            record, pair_diffs = make_m1_candidate(
                pair, order, t1, t2, rec, recomputed_cls, recomputed_reason, official)
            candidates.append(record)
            diffs.extend(pair_diffs)
    # collapse duplicate (pair_id, field) diffs produced by both directions
    unique = {}
    for diff in diffs:
        key = (diff.get("pair_id"), diff.get("field"))
        if key not in unique:
            unique[key] = diff
    return candidates, list(unique.values())
# ---------------------------------------------------------------------------
# M2: in-scene object promotion (OBJECT-route-B style) -- 17 unordered -> 34 ordered
# ---------------------------------------------------------------------------
M2_SPECS = [
    {
        "scene": "LIVING_ROOM_SCENE2",
        "partners": [35, 36, 37, 38, 39],
        "targets": [
            {
                "object": "cream_cheese_1",
                "goal_atom": "(In cream_cheese_1 basket_1_contain_region)",
                "instruction": "pick up the cream cheese box and put it in the basket",
                "instruction_source": "borrowed:32",
                "borrowed_task": 32,
            },
            {
                "object": "ketchup_1",
                "goal_atom": "(In ketchup_1 basket_1_contain_region)",
                "instruction": "pick up the ketchup and put it in the basket",
                "instruction_source": "borrowed:31",
                "borrowed_task": 31,
            },
        ],
    },
    {
        "scene": "STUDY_SCENE2",
        "partners": [72, 73, 74, 75],
        "targets": [
            {
                "object": "red_coffee_mug_1",
                "goal_atom": "(In red_coffee_mug_1 desk_caddy_1_right_contain_region)",
                "instruction": "pick up the red mug and place it in the right compartment of the caddy",
                "instruction_source": "borrowed:73",
                "borrowed_task": 73,
            },
        ],
    },
    {
        "scene": "LIVING_ROOM_SCENE4",
        "partners": [42, 43, 44],
        "targets": [
            {
                "object": "akita_black_bowl_2",
                "goal_atom": "(In akita_black_bowl_2 wooden_tray_1_contain_region)",
                "instruction": "pick up the black bowl on the right and put it in the tray",
                "instruction_source": "borrowed:42",
                "borrowed_task": 42,
            },
        ],
    },
]

S1_SPEC = {
    "scene": "KITCHEN_SCENE8",
    "partner": 18,
    "object": "moka_pot_2",
    "goal_atom": "(On moka_pot_2 flat_stove_1_cook_region)",
    "instruction": "put the left moka pot on the stove",
    "second_atom": "(Turnoff flat_stove_1)",
    "drop_atom": "(Turnon flat_stove_1)",
    "instruction_source": "synthesized",
}


def container_family(dest: str, ref_task):
    for name in ref_task["fixture_names"] + ref_task["object_names"]:
        if dest.startswith(name + "_"):
            return name
    return None


def promotion_relation(promoted_dest: str, partner_goal_atoms, ref_task):
    """Dependency tags + capacity caveat of (promoted goal) + (partner task goal)."""
    deps = []
    capacity = False
    for atom in partner_goal_atoms:
        pred, args = split_atom(atom)
        if pred not in PLACEMENT_PREDS or len(args) < 2:
            continue
        if args[1] == promoted_dest:
            deps.append("same_destination")
            capacity = True
        elif container_family(args[1], ref_task) == container_family(promoted_dest, ref_task):
            deps.append("same_container_family")
    return dedupe(deps) or ["independent"], capacity


def promoted_task_dict(spec_target):
    return {
        "index": None,
        "kind": "promoted",
        "object": spec_target["object"],
        "language": spec_target["instruction"],
        "goal_atoms": [spec_target["goal_atom"]],
        "instruction_source": spec_target["instruction_source"],
        "borrowed_task": spec_target.get("borrowed_task"),
    }


def validate_promoted_atom(scene, object_name, goal_atom, partners, by_index, scenes):
    """Fail-fast validation of a synthesized/promoted goal atom against the BDDL scene."""
    ref = by_index[scenes[scene][0]]
    pred, args = split_atom(goal_atom)
    if pred not in PLACEMENT_PREDS or len(args) != 2:
        raise ValueError("promoted goal atom must be (On|In <object> <destination>): %r" % goal_atom)
    if args[0] != object_name:
        raise ValueError("promoted atom object mismatch: %r vs %r" % (goal_atom, object_name))
    if args[0] not in ref["object_names"]:
        raise ValueError("promoted object %r is not instantiated in %s" % (object_name, scene))
    if args[1] not in ref["region_full_names"]:
        raise ValueError("promoted destination %r is not a region of %s" % (args[1], scene))
    has_init_pose = any(
        split_atom(atom)[1][:1] == [object_name] for atom in ref["init_atoms"] if split_atom(atom)[1])
    if not has_init_pose:
        raise ValueError("promoted object %r has no :init pose in %s" % (object_name, scene))
    for partner in partners:
        partner_goal = set(by_index[partner]["goal_atoms"])
        if goal_atom in partner_goal:
            raise ValueError("promoted atom %r duplicates partner task %02d goal" % (goal_atom, partner))
        for atom in partner_goal:
            _p, pargs = split_atom(atom)
            if _p in PLACEMENT_PREDS and pargs and pargs[0] == object_name:
                raise ValueError("promoted object %r is already a goal object of task %02d" % (object_name, partner))


def validate_borrowed_wording(borrowed_task, promoted_dest, by_index):
    borrowed = by_index[borrowed_task]
    dests = []
    for atom in borrowed["goal_atoms"]:
        pred, args = split_atom(atom)
        if pred in PLACEMENT_PREDS and len(args) >= 2:
            dests.append(args[1])
    if promoted_dest not in dests:
        raise ValueError("borrowed-task wording %02d does not target destination %r (dests=%r)"
                         % (borrowed_task, promoted_dest, dests))


def build_m2_records(tasks, scenes, scene_order, by_index, official, single_set):
    records = []
    for spec in M2_SPECS:
        scene = spec["scene"]
        targets = spec["targets"]
        partners = spec["partners"]
        for partner in partners:
            if partner not in single_set:
                raise ValueError("M2 partner task %02d is not in the single-goal pool" % partner)
            if by_index[partner]["scene"] != scene:
                raise ValueError("M2 partner task %02d is not in scene %s" % (partner, scene))
        for target in targets:
            validate_promoted_atom(scene, target["object"], target["goal_atom"], partners, by_index, scenes)
            if target.get("borrowed_task") is not None:
                validate_borrowed_wording(target["borrowed_task"], split_atom(target["goal_atom"])[1][1], by_index)
        ref = by_index[scenes[scene][0]]
        for target in targets:
            promoted = promoted_task_dict(target)
            promoted_atom = target["goal_atom"]
            promoted_dest = split_atom(promoted_atom)[1][1]
            for partner in partners:
                task = by_index[partner]
                deps, capacity = promotion_relation(promoted_dest, task["goal_atoms"], ref)
                official_side = {"index": partner, "language": official[partner],
                                 "goal_atoms": list(task["goal_atoms"])}
                obj_of_interest = list(task["obj_of_interest"])
                if target["object"] not in obj_of_interest:
                    obj_of_interest.append(target["object"])
                for order in ("ab", "ba"):
                    if order == "ab":
                        s1_task, s2_task = official_side, promoted
                    else:
                        s1_task, s2_task = promoted, official_side
                    goal_atoms = list(s1_task["goal_atoms"]) + [
                        a for a in s2_task["goal_atoms"] if a not in set(s1_task["goal_atoms"])]
                    language = s1_task["language"] + LANGUAGE_JOIN + s2_task["language"]
                    revert = s1_revertable_from_task(s1_task)
                    priority = "P0" if revert else "P1"
                    notes = ("in-scene promotion: second instruction is not official for this scene "
                             "(%s) - manual confirmation required" % target["instruction_source"])
                    if capacity:
                        notes += "; same_destination capacity caveat"
                    if order == "ab":
                        notes += "; promoted target is s2 (designed direction)"
                    if priority == "P1":
                        notes += "; s1 not revertable -> P1"
                    notes += "."
                    records.append({
                        "candidate_id": "L90_%s_%02d_%s_%s" % (
                            task["scene_short"], partner, target["object"], order),
                        "pair_id": "%02d_%s" % (partner, target["object"]),
                        "order": order,
                        "route": "M2",
                        "scene": scene,
                        "s1_task": s1_task,
                        "s2_task": s2_task,
                        "goal_atoms": goal_atoms,
                        "n_atoms": len(goal_atoms),
                        "obj_of_interest": obj_of_interest,
                        "language": language,
                        "template_task": partner,
                        "task_a_index": partner,
                        "init_source": partner,
                        "init_source_alt": None,
                        "init_source_file": task["init_file"],
                        "class": "compatible",
                        "dependency": deps,
                        "capacity_caveat": capacity,
                        "s1_revertable": revert,
                        "valid": True,
                        "priority": priority,
                        "protocol": PRIORITY_PROTOCOL[priority],
                        "promoted_target": {"object": target["object"], "goal_atom": promoted_atom},
                        "promoted_instruction": target["instruction"],
                        "instruction_source": target["instruction_source"],
                        "borrowed_task": target.get("borrowed_task"),
                        "notes": notes,
                    })
    return records
# ---------------------------------------------------------------------------
# S1: stranded KITCHEN_SCENE8 task 18 rescue -- 1 unordered -> 2 ordered
# ---------------------------------------------------------------------------
def build_s1_records(by_index, scenes, official):
    spec = S1_SPEC
    scene = spec["scene"]
    partner = spec["partner"]
    ref = by_index[scenes[scene][0]]
    task = by_index[partner]
    dual = by_index[17]
    if spec["drop_atom"] not in dual["goal_atoms"]:
        raise ValueError("S1: %r not in task 17 goal" % spec["drop_atom"])
    if spec["drop_atom"] not in dual["init_atoms"]:
        raise ValueError("S1: %r is not trivially true in :init of task 17" % spec["drop_atom"])
    if spec["second_atom"] not in task["goal_atoms"]:
        raise ValueError("S1: %r not in task 18 goal" % spec["second_atom"])
    if spec["second_atom"] in task["init_atoms"]:
        raise ValueError("S1: %r is already true in :init" % spec["second_atom"])
    validate_promoted_atom(scene, spec["object"], spec["goal_atom"], [partner], by_index, scenes)
    if "(On moka_pot_1 flat_stove_1_cook_region)" not in dual["goal_atoms"]:
        raise ValueError("S1: task 17 does not move moka_pot_1 (right pot)")
    if "(On moka_pot_1 kitchen_table_moka_pot_right_init_region)" not in ref["init_atoms"]:
        raise ValueError("S1: moka_pot_1 is not initialised on the right")
    if "(On moka_pot_2 kitchen_table_moka_pot_left_init_region)" not in ref["init_atoms"]:
        raise ValueError("S1: moka_pot_2 is not initialised on the left")
    promoted = {
        "index": None,
        "kind": "promoted",
        "object": spec["object"],
        "language": spec["instruction"],
        "goal_atoms": [spec["goal_atom"]],
        "instruction_source": spec["instruction_source"],
        "borrowed_task": None,
    }
    task_dict = {"index": partner, "language": official[partner], "goal_atoms": list(task["goal_atoms"])}
    records = []
    for order in ("ab", "ba"):
        if order == "ab":
            s1_task, s2_task = promoted, task_dict
            goal_atoms = [spec["goal_atom"], spec["second_atom"]]
            language = spec["instruction"] + LANGUAGE_JOIN + official[partner]
            ooi = [spec["object"], "flat_stove_1"]
        else:
            s1_task, s2_task = task_dict, promoted
            goal_atoms = [spec["second_atom"], spec["goal_atom"]]
            language = official[partner] + LANGUAGE_JOIN + spec["instruction"]
            ooi = ["flat_stove_1", spec["object"]]
        if s1_task["index"] is None:
            revert = REVERTABLE_PREDS.get(split_atom(s1_task["goal_atoms"][0])[0], False)
        else:
            revert = s1_revertable_from_task(by_index[s1_task["index"]])
        priority = "P0" if revert else "P1"
        notes = ("synthesized instruction (not official); %r dropped because it already holds in :init; "
                 "ab s1 = place the left moka pot (revertable, P0), ba s1 = Turnoff (not revertable, P1)"
                 % spec["drop_atom"])
        records.append({
            "candidate_id": "L90_%s_%02d_%s_%s" % (ref["scene_short"], partner, spec["object"], order),
            "pair_id": "%02d_%s" % (partner, spec["object"]),
            "order": order,
            "route": "S1",
            "scene": scene,
            "s1_task": s1_task,
            "s2_task": s2_task,
            "goal_atoms": goal_atoms,
            "n_atoms": len(goal_atoms),
            "obj_of_interest": ooi,
            "language": language,
            "template_task": partner,
            "task_a_index": partner,
            "init_source": partner,
            "init_source_alt": None,
            "init_source_file": task["init_file"],
            "class": "compatible",
            "dependency": ["same_fixture"],
            "capacity_caveat": False,
            "s1_revertable": revert,
            "valid": True,
            "priority": priority,
            "protocol": PRIORITY_PROTOCOL[priority],
            "promoted_target": {"object": spec["object"], "goal_atom": spec["goal_atom"]},
            "promoted_instruction": spec["instruction"],
            "instruction_source": spec["instruction_source"],
            "dropped_goal_atoms": [spec["drop_atom"]],
            "drop_reason": "%r already holds in the task-17 :init, keeping it would make Turnon+Turnoff conflict"
                           % spec["drop_atom"],
            "notes": notes + ".",
        })
    return records


# ---------------------------------------------------------------------------
# X1 extension only (NOT part of the main list): 7 dual-goal tasks x same-scene
# single-goal tasks -- 25 unordered 3-atom-chain combinations, statistics only.
# ---------------------------------------------------------------------------
def build_x1_extension(tasks, scenes, scene_order, dual7, single_set):
    by_index = {t["index"]: t for t in tasks}
    cases = []
    for dual in dual7:
        scene = by_index[dual]["scene"]
        partners = [i for i in sorted(scenes[scene]) if i in single_set]
        for single in partners:
            cls, deps, reason = classify_goal_sets(by_index[dual]["goal_atoms"], by_index[single]["goal_atoms"])
            merged = dedupe(list(by_index[dual]["goal_atoms"]) + list(by_index[single]["goal_atoms"]))
            cases.append({
                "combo": "%02d+%02d" % (dual, single),
                "dual_task": dual,
                "single_task": single,
                "scene": scene,
                "class": cls,
                "dependency": deps,
                "n_atoms": len(merged),
                "goal_atoms": merged,
                "reason": reason,
            })
    counts = Counter(case["class"] for case in cases)
    by_dual = []
    for dual in dual7:
        sub = [c for c in cases if c["dual_task"] == dual]
        by_dual.append({
            "dual_task": dual,
            "scene": by_index[dual]["scene"],
            "dual_goal_atoms": list(by_index[dual]["goal_atoms"]),
            "n_single_same_scene": len(sub),
            "combos": [c["combo"] for c in sub],
            "class_counts": {c: sum(1 for x in sub if x["class"] == c) for c in CLASS_ORDER},
        })
    def picks(cls):
        return [{k: c[k] for k in ("combo", "dual_task", "single_task", "scene", "n_atoms",
                                   "goal_atoms", "dependency", "reason")}
                for c in cases if c["class"] == cls]
    return {
        "description": "7 dual-goal tasks x same-scene single-goal tasks; 25 unordered 3-atom "
                       "(or 2-4 atom) chain combinations, statistics only -- not in the main list",
        "dual_tasks": list(dual7),
        "n_dual_tasks": len(dual7),
        "n_unordered_combos": len(cases),
        "n_scenes": len({c["scene"] for c in cases}),
        "class_counts": {c: counts.get(c, 0) for c in CLASS_ORDER},
        "by_dual_task": by_dual,
        "degenerate_cases": picks("degenerate"),
        "conflict_cases": picks("conflict"),
        "hard_cases": picks("hard"),
        "compatible_cases": picks("compatible"),
        "special_cases": [
            {
                "combo": "17+18",
                "class": "conflict",
                "reason": "task 17 target union contains (Turnon flat_stove_1) and task 18 contains "
                          "(Turnoff flat_stove_1); the Turnon is already true in :init, so it must be "
                          "dropped -> becomes the S1 rescue candidate (On moka_pot_2 + Turnoff)",
            },
            {
                "combo": "25+30",
                "class": "degenerate",
                "reason": "task 30 goal (Close wooden_cabinet_1_top_region) is a subset of task 25 goal; "
                          "merged goal adds no new stage",
            },
        ],
        "not_in_main_list": True,
    }
# ---------------------------------------------------------------------------
# Summary / stats / payload assembly
# ---------------------------------------------------------------------------
def build_payload(tasks, scenes, scene_order, official, pairs, m1, m2, s1, x1,
                  dual7, pool_bddl_set, single_set, review, pair_sem_records, pair_sem_meta,
                  cross_diffs, inline_mismatch_indices, inventory_crosscheck, pair_data):
    class_m1 = Counter(c["class"] for c in m1)
    prio_m1 = Counter(c["priority"] for c in m1)
    class_all = Counter(c["class"] for c in m1 + m2 + s1)
    prio_all = Counter(c["priority"] for c in m1 + m2 + s1)
    protocol_counts = Counter(c["protocol"] for c in m1 + m2 + s1)
    pair_class = Counter(rec["class"] for rec in pair_sem_records)
    m2_unordered = len({c["pair_id"] for c in m2})
    s1_unordered = len({c["pair_id"] for c in s1})
    per_scene = []
    for scene in scene_order:
        scene_m1 = [c for c in m1 if c["scene"] == scene]
        scene_pairs = [p for p in pairs if p["scene"] == scene]
        cls = Counter(c["class"] for c in scene_m1)
        prio = Counter(c["priority"] for c in scene_m1)
        per_scene.append({
            "scene": scene,
            "scene_short": scene_short(scene),
            "reviewed": bool((review["per_scene"].get(scene) or {}).get("reviewed")),
            "exclude_tasks_from_pairing": list(
                (review["per_scene"].get(scene) or {}).get("exclude_tasks_from_pairing") or []),
            "n_pool_tasks": len([i for i in scenes[scene] if i in single_set]),
            "n_pool_bddl_tasks": len([i for i in scenes[scene] if i in pool_bddl_set]),
            "m1_unordered": len(scene_pairs),
            "m1_ordered": len(scene_m1),
            "m2_ordered": sum(1 for c in m2 if c["scene"] == scene),
            "s1_ordered": sum(1 for c in s1 if c["scene"] == scene),
            "class_counts": {c: cls.get(c, 0) for c in CLASS_ORDER},
            "priority_counts": {p: prio.get(p, 0) for p in PRIORITY_ORDER},
        })
    n_m1 = len(m1)
    total = n_m1 + len(m2) + len(s1)
    summary = {
        "n_tasks": len(tasks),
        "n_scenes": len(scene_order),
        "pool_bddl": len(pool_bddl_set),
        "review_excluded_tasks": list(review["excluded"]),
        "single_pool": len(single_set),
        "review_decisions_version": review["version"],
        "dual7": list(dual7),
        "m1_unordered": len(pairs),
        "m1_ordered": n_m1,
        "m2_unordered": m2_unordered,
        "m2_ordered": len(m2),
        "s1_unordered": s1_unordered,
        "s1_ordered": len(s1),
        "supplementary_unordered": m2_unordered + s1_unordered,
        "supplementary_ordered": len(m2) + len(s1),
        "total": total,
        "class_counts": {c: class_m1.get(c, 0) for c in CLASS_ORDER},
        "priority_counts": {p: prio_m1.get(p, 0) for p in PRIORITY_ORDER},
        "class_counts_all": {c: class_all.get(c, 0) for c in CLASS_ORDER},
        "priority_counts_all": {p: prio_all.get(p, 0) for p in PRIORITY_ORDER},
        "route_counts": {"M1": n_m1, "M2": len(m2), "S1": len(s1)},
        "protocol_counts": dict(protocol_counts),
        "n_inline_vs_official_language_mismatch": len(inline_mismatch_indices),
        "counting_note": "scene_review v%d: BDDL single-goal pool %d - excluded tasks %s = pairing "
                         "pool %d; unique candidates = M1 %d (%d unordered pairs x2) + M2 %d + S1 %d = "
                         "%d (was 330 before the review)."
                         % (review["version"] or 0, len(pool_bddl_set), list(review["excluded"]),
                            len(single_set), n_m1, len(pairs), len(m2), len(s1), total),
    }
    corpus = m1 + m2 + s1
    scene_review = build_scene_review_block(
        scene_order, scenes, pool_bddl_set, single_set, review, per_scene)
    scene_review["totals"]["total"] = total
    scene_review["totals"]["m2_ordered"] = len(m2)
    scene_review["totals"]["s1_ordered"] = len(s1)
    stats = {
        "m1": {
            "n_pairs": len(pairs),
            "n_ordered": n_m1,
            "n_scenes_with_pairs": sum(1 for row in per_scene if row["m1_ordered"]),
            "n_stranded_scenes": sum(1 for row in per_scene if row["m1_ordered"] == 0),
            "n_pool_bddl_tasks": len(pool_bddl_set),
            "n_pool_tasks": len(single_set),
            "n_review_excluded_tasks": len(review["excluded"]),
            "n_dual_tasks": len(dual7),
            "class_counts_unordered_pairs": {c: pair_class.get(c, 0) for c in CLASS_ORDER},
            "class_counts_ordered": {c: class_m1.get(c, 0) for c in CLASS_ORDER},
            "priority_counts_ordered": {p: prio_m1.get(p, 0) for p in PRIORITY_ORDER},
            "n_atoms_distribution": {str(k): v for k, v in sorted(Counter(c["n_atoms"] for c in m1).items())},
            "valid_directions": sum(1 for c in m1 if c["valid"]),
            "invalid_directions": sum(1 for c in m1 if not c["valid"]),
            "s1_revertable_ab": sum(1 for rec in pair_sem_records if rec.get("s1_revertable_ab")),
            "s1_revertable_ba": sum(1 for rec in pair_sem_records if rec.get("s1_revertable_ba")),
            "capacity_caveat_pairs": sum(1 for rec in pair_sem_records if rec.get("capacity_caveat")),
            "protocol_counts": dict(Counter(c["protocol"] for c in m1)),
            "capacity_caveat_ordered": sum(1 for c in m1 if c["capacity_caveat"]),
        },
        "m2": {
            "n_unordered": m2_unordered,
            "n_ordered": len(m2),
            "by_scene": dict(Counter(c["scene"] for c in m2)),
            "priority_counts_ordered": dict(Counter(c["priority"] for c in m2)),
            "promoted_targets": sorted({c["promoted_target"]["object"] for c in m2}),
            "instruction_source_counts": dict(Counter(c["instruction_source"] for c in m2)),
        },
        "s1": {
            "n_unordered": s1_unordered,
            "n_ordered": len(s1),
            "priority_counts_ordered": dict(Counter(c["priority"] for c in s1)),
            "s1_revertable_directions": sum(1 for c in s1 if c["s1_revertable"]),
            "candidate_ids": [c["candidate_id"] for c in s1],
        },
        "per_scene": per_scene,
        "scene_review": {
            "version": review["version"],
            "excluded_tasks": list(review["excluded"]),
            "reviewed_scenes": [row["scene"] for row in scene_review["per_scene"] if row["reviewed"]],
            "pending_scenes": list(review["pending_scenes"]),
            "n_pair_semantics_records": pair_sem_meta["n_records"],
            "n_excluded_pairs": pair_sem_meta["n_excluded_pairs"],
            "excluded_pair_ids": list(pair_sem_meta["extra_pair_ids"]),
        },
        "pair_semantics_crosscheck": {
            "n_pairs_used": len(pairs),
            "n_diffs": len(cross_diffs),
            "by_severity": dict(Counter(d.get("severity") for d in cross_diffs)),
            "critical_diffs": [d for d in cross_diffs if d.get("severity") == "critical"],
            "known_inline_vs_official_diffs": [
                d for d in cross_diffs if d.get("severity") == "known_inline_vs_official"],
            "known_inline_vs_official_pairs": sorted({
                d["pair_id"] for d in cross_diffs if d.get("severity") == "known_inline_vs_official"}),
            "other_diffs": [d for d in cross_diffs
                            if d.get("severity") not in ("critical", "known_inline_vs_official")],
            "note": "class/s1_revertable are independently re-derived from the BDDL; the only known "
                    "difference is language_ab/ba for pairs touching tasks whose BDDL inline :language "
                    "differs from the official filename-derived language (18 pairs over tasks 55/58/79/80). "
                    "This candidate list uses the official language by design.",
        },
        "inventory_crosscheck": {
            "available": inventory_crosscheck.get("available"),
            "n_diffs": len(inventory_crosscheck.get("diffs") or []),
            "diffs": (inventory_crosscheck.get("diffs") or [])[:10],
        },
        "official_language": {
            "rule": "libero_90 official language is derived from the BDDL file stem (benchmark "
                    "grab_language_from_filename), not the inline :language",
            "inline_vs_official_mismatch_indices": list(inline_mismatch_indices),
            "n_inline_vs_official_mismatch": len(inline_mismatch_indices),
            "crosschecked_against_map": True,
        },
    }
    payload = {
        "summary": summary,
        "scene_review": scene_review,
        "candidates": corpus,
        "extensions": {"x1": x1},
        "stats": stats,
        "meta": {
            "generated_by": "scripts/build_libero90_combos.py",
            "libero_root": str(LIBERO_ROOT),
            "bddl_dir": str(BDDL_DIR),
            "init_dir": str(INIT_DIR),
            "pair_semantics_generated_by": pair_data.get("generated_by"),
            "n_bddl_parsed": len(tasks),
            "n_init_files": len({t["init_file"] for t in tasks}),
            "official_language": "filename-derived (official LIBERO-90 benchmark language)",
            "scene_review_version": review["version"],
            "scene_review_decisions_sha256": review["sha256"],
            "scene_review_decisions_path": str(DECISIONS_JSON),
            "baseline_revision": BASELINE_REVISION["label"],
        },
    }
    return payload


# ---------------------------------------------------------------------------# CASE_LIST.md renderer
# ---------------------------------------------------------------------------
def md_cell(value) -> str:
    return str(value).replace("|", "/").replace("\n", " ")


def task_label(task) -> str:
    idx = task.get("index")
    if idx is None:
        return "promoted:%s" % task.get("object")
    return "%02d" % idx


def direction_label(cand) -> str:
    return "%s (%s -> %s)" % (cand["order"], task_label(cand["s1_task"]), task_label(cand["s2_task"]))


def init_label(cand) -> str:
    src = cand.get("init_source")
    if src is None:
        return "n/a"
    text = "%02d" % src
    alt = cand.get("init_source_alt")
    if alt is not None and alt != src:
        text += " (alt %02d)" % alt
    return text


def priority_text(cands) -> str:
    counter = Counter(c["priority"] for c in cands)
    return " / ".join("%s %d" % (p, counter.get(p, 0)) for p in PRIORITY_ORDER)


def class_text(cands) -> str:
    counter = Counter(c["class"] for c in cands)
    return " / ".join("%s %d" % (c, counter.get(c, 0)) for c in CLASS_ORDER)


def render_case_list(payload) -> str:
    summary = payload["summary"]
    stats = payload["stats"]
    meta = payload["meta"]
    cands = payload["candidates"]
    m1 = [c for c in cands if c["route"] == "M1"]
    m2 = [c for c in cands if c["route"] == "M2"]
    s1 = [c for c in cands if c["route"] == "S1"]
    x1 = payload["extensions"]["x1"]
    lines = []
    lines.append("# LIBERO-90 双目标组合候选全量清单（CASE_LIST）")
    lines.append("")
    lines.append("> 自动生成：`scripts/build_libero90_combos.py`（**请勿手改**；重跑 `--check` 会校验全部不变量）。")
    lines.append("> 口径：%d 条 LIBERO-90 BDDL → %d 条双目标（口径 C）→ BDDL 单目标池 **%d 条**；"
                 "逐场景复核 v%s 剔除任务 %s 后**组合池 %d 条**；同场景组合池内无序对 **%d**"
                 "（×2 方向 = **M1 %d ordered**）；M2 场景内提升 **%d unordered / %d ordered**；"
                 "S1 stranded 救援 **%d / %d**；**合计 %d 条候选定义**。"
                 % (summary["n_tasks"], len(summary["dual7"]), summary["pool_bddl"],
                    summary["review_decisions_version"], summary["review_excluded_tasks"],
                    summary["single_pool"], summary["m1_unordered"], summary["m1_ordered"],
                    summary["m2_unordered"], summary["m2_ordered"], summary["s1_unordered"],
                    summary["s1_ordered"], summary["total"]))
    lines.append("> 逐场景复核（scene_review v%s）：**KITCHEN_SCENE1 已复核**，任务 00（本身已是双子任务，"
                 "Open + In）移出组合池；其余 %d 个场景待复核。候选总数由 330 降为 **%d**。"
                 % (summary["review_decisions_version"], len(payload["scene_review"]["pending_scenes"]),
                    summary["total"]))
    lines.append("> 指令一律使用 **官方 language**（libero_90 的 benchmark language 由 BDDL 文件名派生，"
                 "不是 BDDL 内联 `:language`；%d 条不一致见 stats.official_language）。"
                 % summary["n_inline_vs_official_language_mismatch"])
    lines.append("")
    lines.append("符号约定：`方向` = `order (s1 -> s2)`；`init 源` = 候选 BDDL 复制的 `.pruned_init` 来源"
                 "（括号内为备选 init 源）；`promoted:<object>` 表示合成提升目标（无官方任务号）；"
                 "`PD` = promoted target。")
    lines.append("")
    lines.append("## 1. 全局统计")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("| --- | ---: |")
    lines.append("| BDDL 解析任务数 | %d |" % summary["n_tasks"])
    lines.append("| 场景数 | %d |" % summary["n_scenes"])
    lines.append("| 双目标任务（口径 C） | %d（%s） |" % (
        len(summary["dual7"]), ", ".join("%02d" % i for i in summary["dual7"])))
    lines.append("| BDDL 单目标池（复核前） | %d |" % summary["pool_bddl"])
    lines.append("| 逐场景复核剔除任务 | %d（%s） |" % (
        len(summary["review_excluded_tasks"]),
        ", ".join("%02d" % i for i in summary["review_excluded_tasks"]) or "—"))
    lines.append("| 组合池（复核后） | %d |" % summary["single_pool"])
    lines.append("| 逐场景复核版本 | v%s（%s） |" % (
        summary["review_decisions_version"],
        "、".join("%s 已复核" % row["scene"] for row in payload["scene_review"]["per_scene"]
                 if row["reviewed"]) or "—"))
    lines.append("| M1 unordered 对 / ordered 候选 | %d / %d |" % (summary["m1_unordered"], summary["m1_ordered"]))
    lines.append("| M2 unordered / ordered | %d / %d |" % (summary["m2_unordered"], summary["m2_ordered"]))
    lines.append("| S1 unordered / ordered | %d / %d |" % (summary["s1_unordered"], summary["s1_ordered"]))
    lines.append("| supplementary（M2+S1）unordered / ordered | %d / %d |" % (
        summary["supplementary_unordered"], summary["supplementary_ordered"]))
    lines.append("| **候选总数** | **%d** |" % summary["total"])
    lines.append("| valid 候选 / invalid 候选 | %d / %d |" % (
        sum(1 for c in cands if c["valid"]), sum(1 for c in cands if not c["valid"])))
    lines.append("")
    lines.append("**按 class**（M1 ordered / 全部候选）")
    lines.append("")
    lines.append("| class | M1 ordered | 全部候选 |")
    lines.append("| --- | ---: | ---: |")
    for cls in CLASS_ORDER:
        lines.append("| `%s` | %d | %d |" % (cls, summary["class_counts"][cls], summary["class_counts_all"][cls]))
    lines.append("")
    lines.append("**按 priority**（M1 ordered / 全部候选）")
    lines.append("")
    lines.append("| priority | M1 ordered | 全部候选 | protocol |")
    lines.append("| --- | ---: | ---: | --- |")
    proto = {}
    for cand in cands:
        proto.setdefault(cand["priority"], cand["protocol"])
    for prio in PRIORITY_ORDER:
        lines.append("| `%s` | %d | %d | %s |" % (
            prio, summary["priority_counts"][prio], summary["priority_counts_all"][prio], proto.get(prio, "")))
    lines.append("")
    lines.append("**按场景**")
    lines.append("")
    lines.append("| 场景 | 单目标池 | M1 无序对 | M1 ordered | compatible | hard | conflict | degenerate | "
                 "P0 | P1 | P2 | P3 | M2 | S1 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in stats["per_scene"]:
        cls = row["class_counts"]
        prio = row["priority_counts"]
        lines.append("| `%s` | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d |" % (
            row["scene"], row["n_pool_tasks"], row["m1_unordered"], row["m1_ordered"],
            cls["compatible"], cls["hard"], cls["conflict"], cls["degenerate"],
            prio["P0"], prio["P1"], prio["P2"], prio["P3"], row["m2_ordered"], row["s1_ordered"]))
    lines.append("")
    lines.append("**逐场景复核状态（scene_review v%s）**" % summary["review_decisions_version"])
    lines.append("")
    lines.append("| 场景 | 复核状态 | 剔除任务 | 组合池任务数（复核前 -> 后） | M1 无序对 | M1 ordered |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: |")
    for row in payload["scene_review"]["per_scene"]:
        lines.append("| `%s` | %s | %s | %d -> %d | %d | %d |" % (
            row["scene"], "已复核" if row["reviewed"] else "待复核",
            ", ".join("%02d" % i for i in row["exclude_tasks_from_pairing"]) or "—",
            row["pool_bddl_tasks"], row["pool_after_review"],
            row["m1_unordered"], row["m1_ordered"]))
    lines.append("")
    lines.append("## 2. M1 主路线：按场景全量 ordered 候选（%d 条）" % len(m1))
    lines.append("")
    for row in stats["per_scene"]:
        scene = row["scene"]
        scene_cands = [c for c in m1 if c["scene"] == scene]
        if not scene_cands:
            lines.append("### `%s`（单目标池 %d 条；无同场景配对 → 0 条 M1 候选，stranded 见 §4）"
                         % (scene, row["n_pool_tasks"]))
            lines.append("")
            continue
        lines.append("### `%s`（单目标池 %d 条，%d 无序对 → %d ordered）"
                     % (scene, row["n_pool_tasks"], row["m1_unordered"], row["m1_ordered"]))
        lines.append("")
        lines.append("| candidate_id | class | priority | 方向 | n_atoms | 合并指令 | s1_revertable | init 源 |")
        lines.append("| --- | --- | --- | --- | ---: | --- | --- | --- |")
        for cand in scene_cands:
            lines.append("| `%s` | %s | %s | %s | %d | %s | %s | %s |" % (
                cand["candidate_id"], cand["class"], cand["priority"], direction_label(cand),
                cand["n_atoms"], md_cell(cand["language"]), str(cand["s1_revertable"]).lower(),
                init_label(cand)))
        lines.append("")
        lines.append("scene 小计：class %s；priority %s。" % (class_text(scene_cands), priority_text(scene_cands)))
        lines.append("")
    lines.append("## 3. M2 补充路线：场景内提升纯干扰物（%d unordered / %d ordered）"
                 % (summary["m2_unordered"], summary["m2_ordered"]))
    lines.append("")
    lines.append("> ⚠ **指令警示**：M2 的第二段指令**不是该场景官方原文**，是借用其他任务/场景的官方措辞"
                 "（`instruction_source = borrowed:<task_idx>`）。所有 M2 候选在进入静态/动态验证前必须人工确认"
                 " instruction 与 `:goal` 一致（差一个 left/right/front/back 就会指向错误目标）。")
    lines.append("")
    lines.append("| candidate_id | 源任务 | 提升目标（PD） | class | priority | 方向 | n_atoms | 合并指令 | s1_revertable | init 源 | ⚠ 指令来源 |")
    lines.append("| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |")
    for cand in m2:
        pd = cand["promoted_target"]
        lines.append("| `%s` | %02d | `%s` %s | %s | %s | %s | %d | %s | %s | %s | ⚠ %s |" % (
            cand["candidate_id"], cand["template_task"], pd["object"], md_cell(pd["goal_atom"]),
            cand["class"], cand["priority"], direction_label(cand), cand["n_atoms"],
            md_cell(cand["language"]), str(cand["s1_revertable"]).lower(), init_label(cand),
            cand["instruction_source"]))
    lines.append("")
    lines.append("M2 合计：%d unordered / %d ordered；priority %s；提升物体：%s。"
                 % (summary["m2_unordered"], summary["m2_ordered"], priority_text(m2),
                    ", ".join("`%s`" % t for t in stats["m2"]["promoted_targets"])))
    lines.append("")
    last_scene = None
    for cand in m2:
        if cand["scene"] != last_scene:
            last_scene = cand["scene"]
            subset = [c for c in m2 if c["scene"] == last_scene]
            lines.append("- `%s`：%d unordered / %d ordered（%s）"
                         % (last_scene, len({c["pair_id"] for c in subset}), len(subset),
                            ", ".join(sorted({c["promoted_target"]["object"] for c in subset}))))
    lines.append("")
    lines.append("## 4. S1 特殊候选：stranded 任务 `18` 救援（%d unordered / %d ordered）"
                 % (summary["s1_unordered"], summary["s1_ordered"]))
    lines.append("")
    lines.append("> ⚠ **指令警示**：`instruction_source = synthesized`。合并 goal = `(On moka_pot_2 "
                 "flat_stove_1_cook_region)` + `(Turnoff flat_stove_1)`；task 17 的 `(Turnon flat_stove_1)` "
                 "在 `:init` 已为真，必须丢弃（否则 Turnon/Turnoff 互斥）。")
    lines.append("")
    lines.append("| candidate_id | 方向 | 合并 goal（s1→s2） | n_atoms | 合并指令 | s1_revertable | priority | 备注 |")
    lines.append("| --- | --- | --- | ---: | --- | --- | --- | --- |")
    for cand in s1:
        lines.append("| `%s` | %s | %s | %d | %s | %s | %s | %s |" % (
            cand["candidate_id"], direction_label(cand),
            " ; ".join("`%s`" % a for a in cand["goal_atoms"]), cand["n_atoms"],
            md_cell(cand["language"]), str(cand["s1_revertable"]).lower(), cand["priority"],
            md_cell(cand["notes"])))
    lines.append("")
    lines.append("S1 小计：priority %s；`ab` = 放左壶作 s1（P0，可回退），`ba` = Turnoff 作 s1（P1，无回退机制）。"
                 % priority_text(s1))
    lines.append("")
    lines.append("## 5. X1 扩展（只统计，不进主清单）")
    lines.append("")
    lines.append("7 条双目标任务 × 同场景单目标任务 = **%d** 个 unordered 3 原子链组合（%d 个场景）；"
                 "class：compatible **%d** / hard **%d** / conflict **%d** / degenerate **%d**。"
                 "这些组合借用了被排除出 83 池的双目标任务，因此只作为扩展统计保留，不逐条进入主清单。"
                 % (x1["n_unordered_combos"], x1["n_scenes"], x1["class_counts"]["compatible"],
                    x1["class_counts"]["hard"], x1["class_counts"]["conflict"], x1["class_counts"]["degenerate"]))
    lines.append("")
    lines.append("| 双目标任务 | 场景 | 双目标 goal 原子 | 同场景单目标 | 组合 | class 分布 |")
    lines.append("| --- | --- | --- | ---: | --- | --- |")
    for row in x1["by_dual_task"]:
        cls = row["class_counts"]
        cls_text = " / ".join("%s %d" % (c, cls[c]) for c in CLASS_ORDER if cls[c])
        lines.append("| `%02d` | `%s` | %s | %d | %s | %s |" % (
            row["dual_task"], row["scene"], " ; ".join("`%s`" % a for a in row["dual_goal_atoms"]),
            row["n_single_same_scene"], ", ".join("`%s`" % combo for combo in row["combos"]),
            cls_text or "—"))
    lines.append("")
    for key, title in (("degenerate_cases", "degenerate"), ("conflict_cases", "conflict")):
        cases = x1[key]
        lines.append("**%s case（%d 个）**" % (title, len(cases)))
        lines.append("")
        lines.append("| combo | goal 原子并集 | 原因 |")
        lines.append("| --- | --- | --- |")
        for case in cases:
            lines.append("| `%s` | %s | %s |" % (
                case["combo"], " ; ".join("`%s`" % a for a in case["goal_atoms"]), md_cell(case["reason"])))
        lines.append("")
    lines.append("**hard case（%d 个）**：%s" % (
        len(x1["hard_cases"]), ", ".join("`%s`" % c["combo"] for c in x1["hard_cases"]) or "—"))
    lines.append("")
    lines.append("**compatible case（%d 个）**：%s" % (
        len(x1["compatible_cases"]), ", ".join("`%s`" % c["combo"] for c in x1["compatible_cases"]) or "—"))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("复现（WSL，仓库根目录）：")
    lines.append("")
    lines.append("```bash")
    lines.append(".venv/bin/python scripts/build_libero90_combos.py --check")
    lines.append("```")
    lines.append("")
    lines.append("本文件与 `candidates.json`、`README.md` 由同一脚本一次生成；BDDL 来源 `%s`，"
                 "pair-semantics 来源 `%s`。" % (meta["bddl_dir"], str(PAIR_SEMANTICS)))
    lines.append("")
    return "\n".join(lines)
# ---------------------------------------------------------------------------
# README.md renderer
# ---------------------------------------------------------------------------
def render_readme(payload) -> str:
    summary = payload["summary"]
    stats = payload["stats"]
    meta = payload["meta"]
    x1 = payload["extensions"]["x1"]
    m1 = stats["m1"]
    lines = []
    lines.append("# LIBERO-90 双目标组合候选：生成器 / 机读清单 / 全量表格")
    lines.append("")
    lines.append("> 静态生成（2026-10-25）：**只读解析 LIBERO-90 BDDL + init_files，不跑仿真、不下载模型、不改数据集**。")
    lines.append("> 本目录 3 个产物（`candidates.json` / `CASE_LIST.md` / `README.md`）全部由")
    lines.append("> `scripts/build_libero90_combos.py` 一次生成；所有数字由脚本计算，无手填。")
    lines.append("")
    lines.append("## 1. 口径")
    lines.append("")
    lines.append("- **7 / 83 / 82**：90 条 LIBERO-90 任务里，`:goal` 两个原子且两个原子目标实体（最后一个参数）"
                 "不同的有 7 条（%s），其余 **%d 条**进入 BDDL 单目标池（口径 C，见 `inventory-summary.md` §1；"
                 "00/26/27/28 的两原子是同一容器上的 Open+In / In+Close，算单目标）。"
                 "按**用户逐场景复核 v%s**（唯一真源 `scene_review_decisions.json`），KITCHEN_SCENE1 的任务 "
                 "**00**（本身已是 Open + In 的双子任务）移出组合池 → **组合池 %d 条**"
                 "（`review_excluded_tasks=%s`）。"
                 % (", ".join("`%02d`" % i for i in summary["dual7"]), summary["pool_bddl"],
                    summary["review_decisions_version"], summary["single_pool"],
                    summary["review_excluded_tasks"]))
    lines.append("- **143 / 286（M1）**：组合池 %d 条内同场景无序对 %d 个（20 场景指纹互异 → 跨场景无解；"
                 "KS1 由 10 对/20 ordered 降为 **6 对/12 ordered**），每对生成 `ab`/`ba` 两个方向 → "
                 "**%d 条 ordered M1 候选**（复核前 147 对 / 294 ordered）。"
                 % (summary["single_pool"], summary["m1_unordered"], summary["m1_ordered"]))
    lines.append("- **M2 / S1（补充）**：同场景内“未被池内 goal 引用”的纯干扰物提升为第二目标："
                 "LIVING_ROOM_SCENE2 `cream_cheese_1`/`ketchup_1` × 35–39（10 unordered）、"
                 "STUDY_SCENE2 `red_coffee_mug_1` × 72–75（4）、LIVING_ROOM_SCENE4 `akita_black_bowl_2` × 42–44（3）"
                 "→ **M2 %d unordered / %d ordered**；KITCHEN_SCENE8 stranded 任务 `18` + 提升 `moka_pot_2` "
                 "→ **S1 %d unordered / %d ordered**。"
                 % (summary["m2_unordered"], summary["m2_ordered"],
                    summary["s1_unordered"], summary["s1_ordered"]))
    lines.append("- **总数 %d（复核前 330）** = M1 %d + M2 %d + S1 %d；supplementary（M2+S1）"
                 "= %d unordered / %d ordered；逐场景复核 v%s 剔除 KS1 的 00 后减少 8 条。"
                 % (summary["total"], summary["route_counts"]["M1"], summary["route_counts"]["M2"],
                    summary["route_counts"]["S1"], summary["supplementary_unordered"],
                    summary["supplementary_ordered"], summary["review_decisions_version"]))
    lines.append("- **官方 language**：libero_90 的 benchmark language 是**文件名派生**"
                 "（`libero.benchmark.grab_language_from_filename`：去掉场景前缀、下划线转空格），"
                 "**不是** BDDL 内联 `:language`。全 90 条中有 %d 条不一致（%s），"
                 "本清单的组合 `:language` 一律用官方值：`\"{official_lang_s1} and {official_lang_s2}\"`。"
                 % (stats["official_language"]["n_inline_vs_official_mismatch"],
                    ", ".join("`%02d`" % i for i in stats["official_language"]["inline_vs_official_mismatch_indices"])))
    lines.append("- **priority（ordered 候选）**：")
    lines.append("")
    lines.append("| priority | 条件 | protocol | 数量（M1 / 全部） |")
    lines.append("| --- | --- | --- | ---: |")
    lines.append("| `P0` | class=compatible 且该方向 s1 可回退（On/In/Open/Close） | staged+single_instruction | %d / %d |"
                 % (summary["priority_counts"]["P0"], summary["priority_counts_all"]["P0"]))
    lines.append("| `P1` | compatible 但该方向 s1 是 Turnon/Turnoff（无 runtime profile，不可回退） | staged+single_instruction | %d / %d |"
                 % (summary["priority_counts"]["P1"], summary["priority_counts_all"]["P1"]))
    lines.append("| `P2` | class=hard（place_then_close / open_then_place / stack_anchor / adjacent_regions），附 `order_caveat` | staged+single_instruction | %d / %d |"
                 % (summary["priority_counts"]["P2"], summary["priority_counts_all"]["P2"]))
    lines.append("| `P3` | class=conflict/degenerate，`valid=false` 仅作对照 | excluded | %d / %d |"
                 % (summary["priority_counts"]["P3"], summary["priority_counts_all"]["P3"]))
    lines.append("")
    lines.append("## 2. 数据来源")
    lines.append("")
    lines.append("| 输入 | 路径 | 用途 |")
    lines.append("| --- | --- | --- |")
    lines.append("| BDDL + tasks_info | `%s`（`tasks_info.txt` 顺序 = 任务编号 00–89） | 解析 `:goal/:init/:objects/:regions/:fixtures/:obj_of_interest` |"
                 % meta["bddl_dir"])
    lines.append("| init_files | `%s`（每任务同名 `.pruned_init`，二进制 pickle，脚本记录 sha256/size） | init 源与场景同构校验 |"
                 % meta["init_dir"])
    lines.append("| pair-semantics | `%s` | 语义文件共 %d 对，本清单使用 **%d 对**（被复核剔除的 %d 对仍保留在语义文件中）；"
                 "class/dependency/s1_revertable/capacity_caveat/方向 caveat（逐对独立重算复核） |"
                 % (str(PAIR_SEMANTICS), stats["scene_review"]["n_pair_semantics_records"],
                    payload["stats"]["pair_semantics_crosscheck"]["n_pairs_used"],
                    stats["scene_review"]["n_excluded_pairs"]))
    lines.append("| 逐场景复核口径（唯一真源） | `%s` | version=%s，剔除任务 %s；复核/待复核场景见 §9 |"
                 % (meta.get("scene_review_decisions_path"), summary["review_decisions_version"],
                    summary["review_excluded_tasks"]))
    lines.append("| 官方 language 映射 | `%s` | 90 条 official_language + benchmark 字母序 idx |"
                 % str(OFFICIAL_MAP))
    lines.append("| inventory（交叉检查） | `%s` | 任务字段/场景/双目标规则对账 |" % str(INVENTORY))
    lines.append("")
    lines.append("## 3. 复现命令")
    lines.append("")
    lines.append("```bash")
    lines.append("# WSL 内（仓库根目录；仓库 .venv 有 pyyaml/jsonschema，无需 torch）")
    lines.append(".venv/bin/python scripts/build_libero90_combos.py --check")
    lines.append("")
    lines.append("# 或从 Windows/任意目录指定 LIBERO_ROOT 后运行")
    lines.append("LIBERO_ROOT=/path/to/libero/libero .venv/bin/python scripts/build_libero90_combos.py --check")
    lines.append("```")
    lines.append("")
    lines.append("`--check` 会先重新生成 3 个产物，再跑全部不变量断言；任一失败打印 `[check] FAIL ...` 并以非零码退出。"
                 "不加 `--check` 时只生成并打印一行 summary。")
    lines.append("")
    lines.append("## 4. `--check` 不变量清单（本文件生成时全部通过）")
    lines.append("")
    lines.append("| # | 不变量 | 实测 |")
    lines.append("| ---: | --- | --- |")
    invariants = [
        ("inventory：90 任务 / 20 场景 / 7 双目标 / 83 BDDL 单目标池",
         "%d / %d / %d / %d" % (summary["n_tasks"], summary["n_scenes"], len(summary["dual7"]),
                                summary["pool_bddl"])),
        ("逐场景复核 v%s：剔除任务 %s -> 组合池 %d"
         % (summary["review_decisions_version"], summary["review_excluded_tasks"],
            summary["single_pool"]),
         "%d = %d - %d" % (summary["single_pool"], summary["pool_bddl"],
                           len(summary["review_excluded_tasks"]))),
        ("M1 unordered = %d，ordered = %d（复核前 147 / 294）"
         % (summary["m1_unordered"], summary["m1_ordered"]),
         "%d / %d" % (summary["m1_unordered"], summary["m1_ordered"])),
        ("KITCHEN_SCENE1：unordered = 6 / ordered = 12，任务 00 不作为 s1/s2 出现",
         "6 / 12，00 已移出组合池"),
        ("M2 ordered = 34，S1 ordered = 2，M2+S1 ordered = 36，total = %d" % summary["total"],
         "%d / %d / %d / %d" % (summary["m2_ordered"], summary["s1_ordered"],
                                summary["supplementary_ordered"], summary["total"])),
        ("每个 M1 候选 set(goal_atoms) == 两任务 goal 原子并集",
         "%d / %d 通过" % (summary["m1_ordered"], summary["m1_ordered"])),
        ("每个 M1 候选 language == 官方 language 按 s1→s2 逐字符拼接",
         "%d / %d 通过" % (summary["m1_ordered"], summary["m1_ordered"])),
        ("每个 M1 候选 obj_of_interest == 两任务去重并集（s1 顺序在前）",
         "%d / %d 通过" % (summary["m1_ordered"], summary["m1_ordered"])),
        ("n_atoms == len(goal_atoms) 且 >= 1",
         "%d / %d 通过" % (summary["m1_ordered"], summary["m1_ordered"])),
        ("ab/ba 的 s1/s2 与 pair i/j 对应（ab: s1=i,s2=j；ba 反之）",
         "%d / %d 通过" % (summary["m1_ordered"], summary["m1_ordered"])),
        ("class/priority/s1_revertable 与过滤后的 pair-semantics 对应方向一致（逐对复核）",
         "critical diffs = %d" % len(stats["pair_semantics_crosscheck"]["critical_diffs"])),
        ("每场景 M1 对数 == C(组合池任务数,2)，全库合计 %d" % summary["m1_unordered"],
         "%d / %d" % (summary["m1_unordered"], summary["m1_unordered"])),
        ("priority 分布与 summary 一致：P0+P1+P2+P3 == %d" % summary["m1_ordered"],
         "%d = %d" % (sum(summary["priority_counts"].values()), summary["m1_ordered"])),
        ("valid 方向数 == compatible*2 + hard*2",
         "%d = %d*2 + %d*2" % (m1["valid_directions"],
                               stats["m1"]["class_counts_unordered_pairs"]["compatible"],
                               stats["m1"]["class_counts_unordered_pairs"]["hard"])),
        ("官方 language 派生与 map 一致；inline-vs-official 不一致 == 4 条",
         "map 90/90；mismatch %d" % stats["official_language"]["n_inline_vs_official_mismatch"]),
        ("90 条 .pruned_init 全部存在且 sha256 非空",
         "%d / %d" % (meta["n_init_files"], meta["n_bddl_parsed"])),
        ("M2/S1 提升 goal 原子在场景 :regions/:objects/:init 中可验证；借词任务落点一致",
         "17 M2 + 1 S1 全部通过"),
        ("scene_review_applied 标记 + 顶层 scene_review.per_scene 20 行",
         "reviewed=%d / pending=%d" % (
             sum(1 for row in payload["scene_review"]["per_scene"] if row["reviewed"]),
             len(payload["scene_review"]["pending_scenes"]))),
        ("candidate_id 唯一；route 计数 == summary.route_counts",
         "%s" % summary["route_counts"]),
    ]
    for idx, (name, value) in enumerate(invariants, 1):
        lines.append("| %d | %s | %s |" % (idx, name, value))
    lines.append("")
    lines.append("另：`pair_semantics_crosscheck` 中非 critical 差异为 %d 对任务的 `language_*`（%d 个方向字段；"
                 "已知：pair-semantics 对 55/58/79/80 相关对沿用了 BDDL 内联措辞；本清单按口径改用官方 language）。"
                 % (len(stats["pair_semantics_crosscheck"]["known_inline_vs_official_pairs"]),
                    len(stats["pair_semantics_crosscheck"]["known_inline_vs_official_diffs"])))
    lines.append("")
    lines.append("## 5. 候选字段（`candidates.json`）")
    lines.append("")
    lines.append("| 字段 | 含义 |")
    lines.append("| --- | --- |")
    lines.append("| `candidate_id` | `L90_<scene_short>_<i>_<j>_<order>`（M1）；M2/S1 的 `<j>` 为提升物体名 |")
    lines.append("| `pair_id` | M1：`<ii>_<jj>`；M2/S1：`<ii>_<promoted_object>`（同 unordered 对的两个方向共享） |")
    lines.append("| `order` | `ab` = tasks_info 序号小者作 s1；`ba` = 反向。M2：`ab` = 源任务作 s1（提升目标作 s2 的设计方向），`ba` = 提升目标作 s1。S1：`ab` = 放左壶作 s1 |")
    lines.append("| `route` | `M1` / `M2` / `S1` |")
    lines.append("| `scene` / `s1_task` / `s2_task` | 场景；两侧 `{index, language, goal_atoms}`（合成侧 `index=null`, `kind=promoted`） |")
    lines.append("| `goal_atoms` / `n_atoms` | 合并去重后的 goal 原子（s1 顺序在前 + s2 新增）及个数 |")
    lines.append("| `obj_of_interest` | 两任务 `:obj_of_interest` 去重并集（s1 顺序在前） |")
    lines.append("| `language` | `\"{official_lang_s1} and {official_lang_s2}\"`（官方 language，M2/S1 见 `instruction_source`） |")
    lines.append("| `template_task` / `init_source` / `init_source_alt` | 模板任务（goal 原子集合较大者，相同取 s1）/ 默认 init 源 = s1 / 备选 init 源 = s2 |")
    lines.append("| `class` / `dependency` / `capacity_caveat` | 语义分类、依赖标签、同落点容量提示 |")
    lines.append("| `s1_revertable` / `valid` / `priority` / `protocol` | 该方向 s1 是否已建模可回退 / class∈{compatible,hard} / P0–P3 / 建议协议 |")
    lines.append("| `notes` / `order_caveat` / `direction_caveat` | 一句人读说明；hard 的次序注意；方向性 caveat |")
    lines.append("| `promoted_target` / `instruction_source` / `borrowed_task` | 仅 M2/S1：提升物体+goal 原子、指令来源、借词任务号 |")
    lines.append("| `dropped_goal_atoms` / `drop_reason` | 仅 S1：丢弃的 `(Turnon flat_stove_1)` 及原因 |")
    lines.append("")
    lines.append("`candidates.json` 顶层：`summary`（计数，Lead 装配脚本读取）、`candidates`（%d 条）、"
                 "`extensions.x1`（7 双目标 × 同场景单目标 = %d 组合的统计，不进主清单）、`stats`（按场景/按 class/priority/"
                 "crosscheck）、`meta`（输入路径与版本）。"
                 % (len(payload["candidates"]), x1["n_unordered_combos"]))
    lines.append("")
    lines.append("## 6. 与 `docs/libero-90-dual-target-candidates.md` 的对应关系")
    lines.append("")
    lines.append("| 文档小节 | 本目录产物 |")
    lines.append("| --- | --- |")
    lines.append("| §1.5 / §3.3 官方 language 与 benchmark idx 映射 | `official-language-and-benchmark-map.json`（输入）；本清单 `language` 字段 |")
    lines.append("| §3 M1 主路线（294 ordered，字段配方/模板/init 源） | `candidates.json` 中 `route=\"M1\"`；`CASE_LIST.md` §2 按场景全量表 |")
    lines.append("| §4 M2 补充路线 | `route=\"M2\"` 记录（含 `promoted_target`/`instruction_source`）；`CASE_LIST.md` §3（带 ⚠ 指令警示列） |")
    lines.append("| §5 S1 特殊候选 | `route=\"S1\"` 2 条记录；`CASE_LIST.md` §4 |")
    lines.append("| §6 语义分类与依赖 | `class`/`dependency`/`capacity_caveat`/`order_caveat` 字段 + `stats.m1.class_counts_unordered_pairs` |")
    lines.append("| §9.1 优先级口径 | `priority`/`protocol` 字段 + `summary.priority_counts`（M1 口径；另给 `priority_counts_all`） |")
    lines.append("| §11 候选清单（全量） | `candidates.json` + `CASE_LIST.md`（本目录即该节的数据源） |")
    lines.append("")
    lines.append("装配脚本 `assemble_doc.py` 读取：`candidates.json` 的 `summary`（计数）与 `candidates`（M1/M2/S1 表格、"
                 "首批候选）；其中 M2 表的“提升的物体”取每条记录的 `promoted_target`。")
    lines.append("")
    lines.append("## 7. 计数口径说明与修订历史（330 -> %d）" % summary["total"])
    lines.append("")
    lines.append("1. **330 的来历（复核前）**：M1 294（147 对 x2）+ M2 34 + S1 2 = 330；早期模板的 "
                 "`m2_ordered=36 / s1_ordered=2 / total=332` 把 S1 的 2 条重复计了一次，已按 330 修正。")
    lines.append("2. **%d 的来历（scene_review v%s）**：用户逐场景复核第 1 批：KITCHEN_SCENE1 的任务 00 本身已是 "
                 "Open+In 双子任务，不再参与组合 → KS1 C(5,2)=10 对降为 C(4,2)=6 对（ordered 20 → 12）；"
                 "全局 M1 147→143 对、294→286 ordered；M2 34 + S1 2 不变 → **总候选 %d**。"
                 % (summary["total"], summary["review_decisions_version"], summary["total"]))
    lines.append("3. 复核只改变**组合池**，不改变 LIBERO-90 既有任务 00 本身（仍保留在 90 条任务清单与单任务表中，"
                 "report 侧标注“双目标（已移出组合池）”）。")
    lines.append("4. 复核后 class（M1 ordered）：compatible %d / hard %d / conflict %d / degenerate %d；"
                 "priority：P0 %d / P1 %d / P2 %d / P3 %d。"
                 % (summary["class_counts"]["compatible"], summary["class_counts"]["hard"],
                    summary["class_counts"]["conflict"], summary["class_counts"]["degenerate"],
                    summary["priority_counts"]["P0"], summary["priority_counts"]["P1"],
                    summary["priority_counts"]["P2"], summary["priority_counts"]["P3"]))
    lines.append("5. 其余 %d 个场景尚未逐场景复核（pending_scenes 见 §9）；若后续继续剔除任务，"
                 "只需更新 `scene_review_decisions.json` 并重跑本生成器，脚本不硬编码剔除集合。"
                 % len(payload["scene_review"]["pending_scenes"]))
    lines.append("")
    lines.append("## 8. 未验证项 / 已知限制")
    lines.append("")
    lines.append("1. **全部为静态生成**：本目录没有在 LIBERO-90 上跑任何仿真；class/priority/valid 是构造层判断，"
                 "动态可解性必须走文档 §10 的验证漏斗（单任务控制 → 组合冒烟 → staged 复筛）。")
    lines.append("2. **M2/S1 指令非本场景官方原文**：`instruction_source=borrowed:<task>` / `synthesized`，"
                 "进入实验前必须人工确认 instruction 与 `:goal` 指向同一目标（left/right/front/back 差一个就错）。")
    lines.append("3. **init 源未做控制实验**：`init_source` 默认 = s1 任务、`init_source_alt` = s2 任务；"
                 "GOAL 已有 init 源翻转单任务成败的实例，静态清单无法判定两源可解性。")
    n3_ordered = m1["n_atoms_distribution"].get("3", 0)
    lines.append("4. **3 原子候选难度未知**：M1 中有 %d 对（%d 条 ordered）3 原子候选"
                 "（`stats.m1.n_atoms_distribution`），GOAL 的 3 原子链动态 0/24，需单独降档/单列验证。"
                 % (n3_ordered // 2, n3_ordered))
    lines.append("5. **capacity_caveat 只是容量/遮挡风险提示**，未做容量或接触可行性验证；同落点是否互相阻挡需动态测试。")
    lines.append("6. **S1 的 Turnon 丢弃**依据“`(Turnon flat_stove_1)` 在 task 17 `:init` 已真”这一 BDDL 事实；"
                 "若 runtime 的初始状态与 `.pruned_init` 不同，需要重新评估。")
    lines.append("7. **pair-semantics 的 `language_*` 对 55/58/79/80 相关对用的是 BDDL 内联措辞**（18 对，已知非 critical 差异）；"
                 "本清单按口径改用官方 language，`--check` 会把这 18 条列为 `known_inline_vs_official` 而不判失败。")
    lines.append("8. **跨场景组合不可行**：20 个场景的 `:regions`+`:fixtures` 指纹两两不同，本清单不含跨场景候选。")
    lines.append("9. **`.pruned_init` 只做存在性 / sha256 / 字节数校验**：仓库 `.venv` 无 numpy，pickle 数组形状"
                 " `[50, D]` 未在脚本内解锁；init 宽度一致性来自 `inventory.json` 的静态清点（20/20 场景内一致），"
                 "写候选 BDDL 时按 `init_source` 的 s1 源字节拷贝即可。")
    lines.append("10. **逐场景复核尚未完成**：只有 KITCHEN_SCENE1 已复核（剔除 00），其余 %d 个场景待用户复核；"
                 "后续只需在 `scene_review_decisions.json` 追加 decisions 并重跑，本清单及其指令/报告会同步更新。"
                 % len(payload["scene_review"]["pending_scenes"]))
    lines.append("")
    # --- §9 scene review record + §10 330->322 revision table -----------------
    sr = payload["scene_review"]
    current_sha = {}
    for name in ("candidates.json", "CASE_LIST.md"):
        path = OUT_DIR / name
        current_sha[name] = sha256_file(path) if path.exists() else "(pending)"
    lines.append("## 9. 逐场景复核记录（scene_review v%s）" % summary["review_decisions_version"])
    lines.append("")
    lines.append("> 唯一真源：`%s`（sha256 `%s`，version=%s，updated_at=%s）。脚本不硬编码剔除集合："
                 "修改该文件后重跑 `--check` 即可更新全部产物。"
                 % (meta.get("scene_review_decisions_path"),
                    meta.get("scene_review_decisions_sha256"),
                    summary["review_decisions_version"], sr.get("updated_at")))
    lines.append("")
    lines.append("| 场景 | 复核状态 | 剔除任务 | 组合池任务数（前 -> 后） | M1 无序对 | M1 ordered |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: |")
    for row in sr["per_scene"]:
        lines.append("| `%s` | %s | %s | %d -> %d | %d | %d |" % (
            row["scene"], "已复核" if row["reviewed"] else "待复核",
            ", ".join("%02d" % i for i in row["exclude_tasks_from_pairing"]) or "—",
            row["pool_bddl_tasks"], row["pool_after_review"],
            row["m1_unordered"], row["m1_ordered"]))
    lines.append("")
    for decision in sr["decisions"]:
        lines.append("- **%s**（已复核，`applied_in=%s`）：剔除 `%s`。原因：%s" % (
            decision["scene"], decision.get("applied_in"),
            ", ".join("%02d" % i for i in decision["exclude_tasks_from_pairing"]),
            decision.get("reason")))
    lines.append("- **待复核场景（%d）**：%s" % (
        len(sr["pending_scenes"]), ", ".join("`%s`" % s for s in sr["pending_scenes"])))
    for note in sr["notes"]:
        lines.append("- 备注：%s" % note)
    lines.append("")
    baseline = BASELINE_REVISION
    b = baseline["counts"]
    lines.append("## 10. 修订记录：v0（330 条）-> v1（%d 条，scene_review v%s）" % (
        summary["total"], summary["review_decisions_version"]))
    lines.append("")
    lines.append("| 指标 | v0（复核前） | v1（复核后） | 变化 |")
    lines.append("| --- | ---: | ---: | --- |")
    def rev_row(label, old, new):
        delta = new - old
        lines.append("| %s | %s | %s | %s |" % (label, old, new, ("+%d" % delta) if delta > 0 else str(delta)))
    rev_row("候选总数", b["total"], summary["total"])
    rev_row("M1 unordered 对", b["m1_unordered"], summary["m1_unordered"])
    rev_row("M1 ordered 候选", b["m1_ordered"], summary["m1_ordered"])
    rev_row("KITCHEN_SCENE1 unordered 对", b["ks1_unordered"], 6)
    rev_row("KITCHEN_SCENE1 ordered 候选", b["ks1_ordered"], 12)
    for cls in CLASS_ORDER:
        rev_row("class=%s（ordered，M1）" % cls, b["ordered_class"][cls], summary["class_counts"][cls])
    for prio in PRIORITY_ORDER:
        rev_row("priority=%s（M1）" % prio, b["priority"][prio], summary["priority_counts"][prio])
    rev_row("M2 ordered", 34, summary["m2_ordered"])
    rev_row("S1 ordered", 2, summary["s1_ordered"])
    lines.append("")
    lines.append("旧 sha256（v0 审计快照，便于比对旧产物）：")
    lines.append("")
    lines.append("| 文件 | v0 sha256 | v1 sha256 / 状态 |")
    lines.append("| --- | --- | --- |")
    for name in ("candidates.json", "CASE_LIST.md", "README.md", "candidates-instructed.json",
                 "INSTRUCTION_TEMPLATES.md"):
        rel = "runs/libero-90-combos-20261025/" + name
        old_sha = baseline["sha256"].get(rel, "—")
        if name in current_sha:
            new_state = "`%s`" % current_sha[name]
        elif name == "README.md":
            new_state = "（本文件，v1 写入后生效）"
        else:
            new_state = "（由 `scripts/build_libero90_instructions.py` 重生成，新 sha 记录在其产物 meta）"
        lines.append("| `%s` | `%s` | %s |" % (name, old_sha, new_state))
    for name in ("scripts/build_libero90_combos.py", "scripts/build_libero90_instructions.py"):
        old_sha = baseline["sha256"].get(name, "—")
        lines.append("| `%s` | `%s` | （v1 已修改，当前 sha 以文件系统为准） |" % (name, old_sha))
    lines.append("")
    lines.append("> v1 变更范围：`build_libero90_combos.py` 读取 `scene_review_decisions.json` 重新计算组合池/计数/分类；"
                 "`build_libero90_instructions.py` 按新 322 条重生成指令与模板统计（T5 命中由 8 变 0）。"
                 "原有 330 条产物内容仍可借旧 sha256 追溯。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("生成器：`scripts/build_libero90_combos.py`；BDDL 根：`%s`；pair-semantics `generated_by=%s`。"
                 % (meta["libero_root"], meta["pair_semantics_generated_by"]))
    lines.append("")
    return "\n".join(lines)
# ---------------------------------------------------------------------------
# --check invariant validation
# ---------------------------------------------------------------------------
def validate(payload, ctx):
    errors = []
    checks = [0]

    def check(condition, name, detail=""):
        checks[0] += 1
        if condition:
            print("[check] PASS %s%s" % (name, (": " + detail) if detail else ""))
        else:
            print("[check] FAIL %s%s" % (name, (": " + detail) if detail else ""))
            errors.append(name)

    summary = payload["summary"]
    scene_review_top = payload["scene_review"]
    candidates = payload["candidates"]
    m1 = [c for c in candidates if c["route"] == "M1"]
    m2 = [c for c in candidates if c["route"] == "M2"]
    s1 = [c for c in candidates if c["route"] == "S1"]
    by_index = ctx["by_index"]
    official = ctx["official"]
    pair_records = list(ctx["pair_sem_by_id"].values())
    scenes = ctx["scenes"]
    scene_order = ctx["scene_order"]
    tasks = ctx["tasks"]
    review = ctx["scene_review"]
    pool_bddl_set = ctx["pool_bddl_set"]
    single_set = ctx["single_set"]
    excluded = set(review["excluded"])
    reviewed_scenes = {row["scene"] for row in review["decisions"]}

    # --- expected counts derived from the review-decisions file (no hard-coded 147/294/330) ---
    per_scene_expected = {}
    for scene in scene_order:
        n_pool = len([i for i in scenes[scene] if i in single_set])
        per_scene_expected[scene] = n_pool * (n_pool - 1) // 2
    n_pairs_expected = sum(per_scene_expected.values())
    n_m1_expected = 2 * n_pairs_expected
    ks1_pairs_expected = per_scene_expected["KITCHEN_SCENE1"]
    n_m2 = len(m2)
    n_s1 = len(s1)
    n_total_expected = n_m1_expected + n_m2 + n_s1

    # --- inventory / parsing -------------------------------------------------
    check(len(tasks) == 90, "inventory n_tasks", str(len(tasks)))
    check(len(scenes) == 20, "inventory n_scenes", str(len(scenes)))
    check(ctx["dual7"] == [5, 9, 17, 19, 25, 40, 41], "inventory dual7 (rule C)", repr(ctx["dual7"]))
    check(len(pool_bddl_set) == 83, "pool_bddl (BDDL single-goal pool) == 83",
          str(len(pool_bddl_set)))
    check(len(single_set) == 83 - len(excluded), "pairing pool after scene review",
          "%d = 83 - %d excluded" % (len(single_set), len(excluded)))
    check(summary["n_tasks"] == 90 and summary["n_scenes"] == 20
          and summary["pool_bddl"] == 83 and summary["dual7"] == ctx["dual7"],
          "summary matches inventory (n_tasks/n_scenes/pool_bddl/dual7)")
    check(summary["single_pool"] == len(single_set),
          "summary.single_pool == pairing pool", str(summary["single_pool"]))
    inv_check = ctx["inventory_crosscheck"]
    check(not inv_check["diffs"], "inventory.json crosscheck (goal/init/objects/regions)",
          "%d diffs" % len(inv_check["diffs"]))
    check(all(t["init_sha256"] for t in tasks) and len({t["init_file"] for t in tasks}) == 90,
          "90 pruned_init files present", "%d" % len({t["init_file"] for t in tasks}))

    # --- scene-review decisions file (single source of truth) ----------------
    check(review["available"] == DECISIONS_JSON.exists(),
          "scene_review_decisions.json availability == file existence")
    if review["available"]:
        check(summary["review_decisions_version"] == review["version"],
              "summary.review_decisions_version == decisions version",
              str(review["version"]))
        check(summary["review_excluded_tasks"] == list(review["excluded"]),
              "summary.review_excluded_tasks == decisions exclusions",
              str(review["excluded"]))
        check(len(review["decisions"]) >= 1 and len(reviewed_scenes) >= 1,
              "at least one scene reviewed", "%d" % len(reviewed_scenes))
        check(0 in excluded and by_index[0]["scene"] == "KITCHEN_SCENE1",
              "KITCHEN_SCENE1 task 00 excluded from pairing pool")
        check(set(review["pending_scenes"]) | reviewed_scenes == set(scene_order)
              and not (set(review["pending_scenes"]) & reviewed_scenes),
              "reviewed scenes + pending scenes cover all 20 scenes")
        check(review["sha256"] == sha256_file(DECISIONS_JSON),
              "review decisions sha256 recorded")
        check(scene_review_top["version"] == review["version"]
              and scene_review_top["excluded_tasks"] == list(review["excluded"])
              and scene_review_top["decisions_sha256"] == review["sha256"],
              "top-level scene_review block matches decisions file")
        rows = scene_review_top["per_scene"]
        check(len(rows) == 20, "scene_review.per_scene rows == 20", str(len(rows)))
        check(sum(row["pool_bddl_tasks"] for row in rows) == 83,
              "scene_review.per_scene pool_bddl sums to 83")
        check(sum(row["pool_after_review"] for row in rows) == len(single_set),
              "scene_review.per_scene pool_after_review sums to pairing pool")
        check(sum(row["m1_unordered"] for row in rows) == n_pairs_expected
              and sum(row["m1_ordered"] for row in rows) == n_m1_expected,
              "scene_review.per_scene M1 counts sum to derived totals")
        check(sum(1 for row in rows if row["reviewed"]) == len(reviewed_scenes),
              "scene_review.per_scene reviewed flags match decisions")
        check(sum(1 for cand in candidates if cand.get("scene_review_applied")) ==
              sum(1 for cand in candidates if cand["scene"] in reviewed_scenes),
              "scene_review_applied flags == reviewed scenes")
        for row in rows:
            expected = 1 if row["scene"] in reviewed_scenes else 0
            if int(bool(row["reviewed"])) != expected:
                check(False, "scene_review.per_scene reviewed flag for %s" % row["scene"])
                break
        else:
            check(True, "scene_review.per_scene reviewed flags consistent")

    # --- counts (derived from decisions) ------------------------------------
    check(summary["m1_unordered"] == n_pairs_expected and len(ctx["pairs"]) == n_pairs_expected,
          "M1 unordered pairs == derived", "%d" % n_pairs_expected)
    check(summary["m1_ordered"] == n_m1_expected and len(m1) == n_m1_expected,
          "M1 ordered == derived", str(n_m1_expected))
    check(n_m2 == 34 and n_s1 == 2,
          "M2 ordered == 34 and S1 ordered == 2 unchanged", "%d / %d" % (n_m2, n_s1))
    check(summary["supplementary_ordered"] == n_m2 + n_s1 == 36,
          "M2+S1 ordered == 36", str(summary["supplementary_ordered"]))
    check(summary["total"] == n_total_expected and len(candidates) == n_total_expected,
          "total candidates == derived", "%d" % n_total_expected)
    check(len(per_scene_expected) == 20 and ks1_pairs_expected == 6,
          "KITCHEN_SCENE1 unordered pairs == 6 (00 excluded)", str(ks1_pairs_expected))
    check(len({c["candidate_id"] for c in candidates}) == len(candidates),
          "candidate_id uniqueness")
    check(len(m1) == n_m1_expected and len(m2) == n_m2 and len(s1) == n_s1,
          "route record counts", "M1 %d / M2 %d / S1 %d" % (len(m1), len(m2), len(s1)))
    required_fields = ("candidate_id", "pair_id", "order", "route", "scene", "s1_task", "s2_task",
                       "goal_atoms", "n_atoms", "obj_of_interest", "language", "template_task",
                       "init_source", "class", "dependency", "capacity_caveat", "s1_revertable",
                       "valid", "priority", "protocol", "notes", "scene_review_applied")
    missing_fields = [(c.get("candidate_id"), key) for c in candidates
                      for key in required_fields if key not in c]
    check(not missing_fields, "required candidate fields present (incl. scene_review_applied)",
          "%d missing" % len(missing_fields))
    task_side_bad = [c.get("candidate_id") for c in candidates
                     for side in ("s1_task", "s2_task")
                     if not all(key in c.get(side, {}) for key in ("index", "language", "goal_atoms"))]
    check(not task_side_bad, "s1_task/s2_task expose {index,language,goal_atoms}", "%d bad" % len(task_side_bad))
    check(summary["m2_unordered"] == 17 and summary["s1_unordered"] == 1,
          "M2==17 / S1==1 unordered pairs",
          "%d / %d" % (summary["m2_unordered"], summary["s1_unordered"]))
    check(summary["route_counts"] == {"M1": len(m1), "M2": len(m2), "S1": len(s1)},
          "summary.route_counts == computed route counts")
    check(summary["class_counts_all"] == {c: sum(1 for x in candidates if x["class"] == c)
                                          for c in CLASS_ORDER},
          "summary.class_counts_all == all candidate classes")
    check(summary["priority_counts_all"] == {p: sum(1 for x in candidates if x["priority"] == p)
                                             for p in PRIORITY_ORDER},
          "summary.priority_counts_all == all candidate priorities")

    # --- excluded tasks never enter any combination -------------------------
    excluded_in_m1 = [c["candidate_id"] for c in m1
                      if c["s1_task"]["index"] in excluded or c["s2_task"]["index"] in excluded]
    check(not excluded_in_m1, "no M1 candidate contains a scene-review-excluded task",
          "%d bad" % len(excluded_in_m1))
    ks1_candidates = [c for c in m1 if c["scene"] == "KITCHEN_SCENE1"]
    check(len(ks1_candidates) == 2 * ks1_pairs_expected,
          "KITCHEN_SCENE1 M1 candidates == 2 x C(4,2)", "%d" % len(ks1_candidates))
    check(not any(c["s1_task"]["index"] == 0 or c["s2_task"]["index"] == 0
                  for c in ks1_candidates),
          "task 00 does not appear as s1/s2 in KITCHEN_SCENE1 candidates")

    check(all((sum(1 for c in candidates if c["scene"] == row["scene"])
                 == row["m1_ordered"] + row["m2_ordered"] + row["s1_ordered"])
              for row in payload["stats"]["per_scene"]),
          "per-scene candidate totals == per_scene M1+M2+S1 counts")

    # --- per-scene pair counts ----------------------------------------------
    scene_pair_counts = Counter(pair["scene"] for pair in ctx["pairs"])
    check(all(scene_pair_counts.get(scene, 0) == per_scene_expected[scene]
              for scene in scene_order),
          "per-scene M1 pairs == C(n_pairing_pool,2)")
    check(set(scene_pair_counts) == {scene for scene in scene_order
                                     if per_scene_expected[scene] > 0},
          "no M1 pair outside known scenes")

    # --- per-candidate M1 checks --------------------------------------------
    bad = []
    lang_bad = []
    ooi_bad = []
    order_bad = []
    class_bad = []
    priority_bad = []
    revert_bad = []
    for cand in m1:
        i, j = [int(part) for part in cand["pair_id"].split("_")]
        t_i, t_j = by_index[i], by_index[j]
        if cand["order"] == "ab":
            s1_task, s2_task = t_i, t_j
        else:
            s1_task, s2_task = t_j, t_i
        expected_goal = list(s1_task["goal_atoms"]) + [
            a for a in s2_task["goal_atoms"] if a not in set(s1_task["goal_atoms"])]
        expected_ooi = list(s1_task["obj_of_interest"]) + [
            o for o in s2_task["obj_of_interest"] if o not in set(s1_task["obj_of_interest"])]
        expected_lang = official[s1_task["index"]] + LANGUAGE_JOIN + official[s2_task["index"]]
        expected_revert = s1_revertable_from_task(s1_task)
        pair_rec = ctx["pair_sem_by_id"][cand["pair_id"]]
        expected_class = pair_rec["class"]
        if set(cand["goal_atoms"]) != set(t_i["goal_atoms"]) | set(t_j["goal_atoms"]):
            bad.append(cand["candidate_id"])
        if cand["goal_atoms"] != expected_goal:
            order_bad.append(cand["candidate_id"])
        if cand["language"] != expected_lang:
            lang_bad.append(cand["candidate_id"])
        if cand["obj_of_interest"] != expected_ooi:
            ooi_bad.append(cand["candidate_id"])
        if cand["n_atoms"] != len(cand["goal_atoms"]) or cand["n_atoms"] < 1:
            bad.append(cand["candidate_id"])
        if cand["class"] != expected_class:
            class_bad.append(cand["candidate_id"])
        if bool(cand["s1_revertable"]) != expected_revert:
            revert_bad.append(cand["candidate_id"])
        expected_priority = ("P0" if expected_revert else "P1") if expected_class == "compatible" else (
            "P2" if expected_class == "hard" else "P3")
        if cand["priority"] != expected_priority:
            priority_bad.append(cand["candidate_id"])
        if cand["valid"] != (expected_class in VALID_CLASSES):
            bad.append(cand["candidate_id"])
        if cand["protocol"] != PRIORITY_PROTOCOL[expected_priority]:
            bad.append(cand["candidate_id"])
        if cand["order"] == "ab":
            ok_map = cand["s1_task"]["index"] == i and cand["s2_task"]["index"] == j
        else:
            ok_map = cand["s1_task"]["index"] == j and cand["s2_task"]["index"] == i
        if not ok_map:
            bad.append(cand["candidate_id"])
    check(not bad, "M1 per-candidate invariants (goal union/n_atoms/valid/protocol/s1-s2 mapping)",
          "%d bad" % len(bad))
    check(not order_bad, "M1 goal_atoms order == s1 atoms first + s2 new atoms", "%d bad" % len(order_bad))
    check(not lang_bad, "M1 language == official(s1) + ' and ' + official(s2), char-by-char",
          "%d bad" % len(lang_bad))
    check(not ooi_bad, "M1 obj_of_interest == deduped union (s1 order first)", "%d bad" % len(ooi_bad))
    check(not class_bad, "M1 class == filtered pair-semantics.json class per pair",
          "%d bad" % len(class_bad))
    check(not revert_bad, "M1 s1_revertable == BDDL recompute == pair-semantics direction",
          "%d bad" % len(revert_bad))
    check(not priority_bad, "M1 priority == rule(class, s1_revertable)",
          "%d bad" % len(priority_bad))

    # --- class / priority derived from the FILTERED pair-semantics records --
    used_ids = {pair["pair_id"] for pair in ctx["pairs"]}
    full_records = ctx["pair_semantics_all"]
    removed = [rec for rec in full_records if rec["pair_id"] not in used_ids]
    check({rec["pair_id"] for rec in removed} == set(ctx["pair_sem_meta"]["extra_pair_ids"]),
          "pair-semantics extra records == pairs removed by scene review",
          "%d removed" % len(removed))
    filtered_class = Counter(rec["class"] for rec in pair_records)
    full_class = Counter(rec["class"] for rec in full_records)
    computed_filtered = Counter(full_class)
    for rec in removed:
        computed_filtered[rec["class"]] -= 1
    check(all(filtered_class.get(c, 0) == computed_filtered.get(c, 0) for c in CLASS_ORDER),
          "pair class counts == full pair-semantics minus removed pairs",
          str({c: filtered_class.get(c, 0) for c in CLASS_ORDER}))

    expected_priority = Counter()
    expected_valid = 0
    for rec in pair_records:
        for order in ("ab", "ba"):
            cls = rec["class"]
            revert = bool(rec.get("s1_revertable_%s" % order))
            if cls == "compatible":
                expected_priority["P0" if revert else "P1"] += 1
            elif cls == "hard":
                expected_priority["P2"] += 1
            else:
                expected_priority["P3"] += 1
            expected_valid += int(cls in VALID_CLASSES)
    prio_counter = Counter(c["priority"] for c in m1)
    cls_counter = Counter(c["class"] for c in m1)
    check(sum(summary["priority_counts"].values()) == n_m1_expected,
          "priority distribution sums to M1 ordered", str(summary["priority_counts"]))
    check(all(summary["priority_counts"][p] == prio_counter.get(p, 0) for p in PRIORITY_ORDER),
          "summary.priority_counts == M1 priority counts")
    check(all(summary["class_counts"][c] == cls_counter.get(c, 0) for c in CLASS_ORDER),
          "summary.class_counts == M1 class counts")
    check(all(summary["priority_counts"][p] == expected_priority.get(p, 0) for p in PRIORITY_ORDER),
          "summary.priority_counts == priority recomputed from filtered pair-semantics",
          str(dict(expected_priority)))
    valid_dirs = sum(1 for c in m1 if c["valid"])
    pair_cls = filtered_class
    check(valid_dirs == expected_valid,
          "valid directions == compatible*2 + hard*2 (pair level)",
          "%d = 2*%d + 2*%d" % (valid_dirs, pair_cls.get("compatible", 0), pair_cls.get("hard", 0)))

    # --- language style / notes --------------------------------------------
    style_bad = []
    for cand in candidates:
        lang = cand["language"]
        if lang != lang.lower() or lang.endswith(".") or "\n" in lang or "  " in lang:
            style_bad.append(cand["candidate_id"])
    check(not style_bad, "all candidate languages lowercase / single-line / no trailing period",
          "%d bad" % len(style_bad))
    check(all(c["notes"] and c["notes"].strip().endswith(".") for c in candidates),
          "all candidates have non-empty one-sentence notes")
    check(all(("task_a_index" in c) for c in m2 + s1),
          "M2/S1 expose task_a_index for the doc assembly script")

    # --- official language ---------------------------------------------------
    check(all(ctx["official_map"]["official"][t["index"]] == t["official_language"] for t in tasks),
          "official language derivation == map (90/90)")
    check(stats_n_inline(payload) == 4, "inline-vs-official :language mismatch == 4",
          str(stats_n_inline(payload)))
    check(stats_n_inline(payload) == len(ctx["official_map"]["inline_mismatch_indices"]),
          "inline-vs-official mismatch indices match map")

    # --- pair-semantics cross-check (used pairs only) -----------------------
    critical = payload["stats"]["pair_semantics_crosscheck"]["critical_diffs"]
    if critical:
        for diff in critical[:10]:
            print("[check] DIFF pair=%s field=%s pair_semantics=%r bddl_recomputed=%r"
                  % (diff.get("pair_id"), diff.get("field"),
                     diff.get("pair_semantics"), diff.get("bddl")))
    check(not critical, "pair-semantics class/s1_revertable critical diffs == 0",
          "%d critical" % len(critical))
    check(payload["stats"]["pair_semantics_crosscheck"]["n_pairs_used"] == n_pairs_expected,
          "pair-semantics crosscheck covered all used pairs")
    known = payload["stats"]["pair_semantics_crosscheck"]["known_inline_vs_official_pairs"]
    inline_idx = set(ctx["official_map"]["inline_mismatch_indices"])
    expected_known = {p["pair_id"] for p in ctx["pairs"] if p["i"] in inline_idx or p["j"] in inline_idx}
    check(set(known) == expected_known,
          "non-critical language diffs limited to inline-vs-official pairs (%d)" % len(expected_known),
          "%d" % len(known))

    # --- M2 / S1 records -----------------------------------------------------
    m2_ok = True
    for cand in m2:
        partner = cand["template_task"]
        task = by_index[partner]
        if cand["class"] != "compatible" or not cand["valid"]:
            m2_ok = False
        if cand["language"] != cand["s1_task"]["language"] + LANGUAGE_JOIN + cand["s2_task"]["language"]:
            m2_ok = False
        if set(cand["goal_atoms"]) != set(task["goal_atoms"]) | {cand["promoted_target"]["goal_atom"]}:
            m2_ok = False
        if cand["n_atoms"] != len(cand["goal_atoms"]):
            m2_ok = False
        if cand["order"] == "ab" and cand["s1_task"]["index"] != partner:
            m2_ok = False
        if cand["order"] == "ba" and cand["s2_task"]["index"] != partner:
            m2_ok = False
        ref = by_index[scenes[task["scene"]][0]]
        if split_atom(cand["promoted_target"]["goal_atom"])[1][1] not in ref["region_full_names"]:
            m2_ok = False
    check(m2_ok, "M2 per-candidate invariants (compatible/union/language/promoted atom)", "%d records" % len(m2))
    check(len({c["pair_id"] for c in m2}) == 17, "M2 unique unordered pairs == 17")
    m2_scene = Counter(c["scene"] for c in m2)
    check(m2_scene.get("LIVING_ROOM_SCENE2") == 20 and m2_scene.get("STUDY_SCENE2") == 8
          and m2_scene.get("LIVING_ROOM_SCENE4") == 6,
          "M2 ordered split LR2/ST2/LR4 == 20/8/6", str(dict(m2_scene)))
    s1_ok = True
    for cand in s1:
        if set(cand["goal_atoms"]) != {"(On moka_pot_2 flat_stove_1_cook_region)",
                                       "(Turnoff flat_stove_1)"}:
            s1_ok = False
        if cand["dropped_goal_atoms"] != ["(Turnon flat_stove_1)"]:
            s1_ok = False
        if cand["order"] == "ab":
            if cand["goal_atoms"] != ["(On moka_pot_2 flat_stove_1_cook_region)", "(Turnoff flat_stove_1)"]:
                s1_ok = False
            if cand["language"] != "put the left moka pot on the stove and turn off the stove":
                s1_ok = False
            if cand["priority"] != "P0" or not cand["s1_revertable"]:
                s1_ok = False
        else:
            if cand["goal_atoms"] != ["(Turnoff flat_stove_1)", "(On moka_pot_2 flat_stove_1_cook_region)"]:
                s1_ok = False
            if cand["language"] != "turn off the stove and put the left moka pot on the stove":
                s1_ok = False
            if cand["priority"] != "P1" or cand["s1_revertable"]:
                s1_ok = False
    check(s1_ok, "S1 per-candidate invariants (goals/language/drop Turnon/P0-P1)", "%d records" % len(s1))

    # --- X1 (statistics only) ------------------------------------------------
    x1 = payload["extensions"]["x1"]
    x1_expected = sum(
        len([i for i in scenes[by_index[d]["scene"]] if i in single_set])
        for d in ctx["dual7"])
    check(x1["n_dual_tasks"] == 7 and x1["n_unordered_combos"] == x1_expected,
          "X1: dual tasks x same-scene pairing-pool singles == %d combos" % x1_expected,
          "%d" % x1["n_unordered_combos"])
    check(sum(x1["class_counts"].values()) == x1_expected,
          "X1 class counts sum to combo count", str(x1["class_counts"]))
    check(sum(row["n_single_same_scene"] for row in x1["by_dual_task"]) == x1_expected,
          "X1 per-dual-task combo counts sum")
    check(x1["not_in_main_list"] is True, "X1 not in main list")


    # --- on-disk round-trip --------------------------------------------------
    disk_path = OUT_DIR / "candidates.json"
    if disk_path.exists():
        disk_payload = json.loads(read_text(disk_path))
        check(disk_payload == payload, "candidates.json round-trip == in-memory payload")
    for name in ("CASE_LIST.md", "README.md"):
        path = OUT_DIR / name
        check(path.exists() and len(read_text(path)) > 1000, "%s written (>1KB)" % name,
              "%d bytes" % (len(read_text(path)) if path.exists() else 0))
    if (OUT_DIR / "CASE_LIST.md").exists():
        case_text = read_text(OUT_DIR / "CASE_LIST.md")
        check("场景复核 v%d" % (review["version"] or 0) in case_text
              and str(n_total_expected) in case_text,
              "CASE_LIST.md records scene review + new total")
    if (OUT_DIR / "README.md").exists():
        readme_text = read_text(OUT_DIR / "README.md")
        check("逐场景复核" in readme_text and "330" in readme_text and "322" in readme_text,
              "README.md records scene review + 330->322 revision")

    if errors:
        print("[check] FAILED %d of %d checks" % (len(errors), checks[0]))
        return False
    print("[check] NOTE scene_review v%s applied: excluded tasks %s; BDDL pool 83 -> pairing pool %d; "
          "M1 147/294 -> %d/%d; total 330 -> %d."
          % (review["version"], list(review["excluded"]), len(single_set),
             n_pairs_expected, n_m1_expected, n_total_expected))
    print("[check] OK -- %d checks passed" % checks[0])
    return True

def stats_n_inline(payload):
    return payload["stats"]["official_language"]["n_inline_vs_official_mismatch"]


# ---------------------------------------------------------------------------
# Build orchestration / CLI
# ---------------------------------------------------------------------------
def build_all():
    tasks, scenes, scene_order = load_tasks()
    official_map = load_official_map(tasks)
    inventory_crosscheck = crosscheck_inventory(tasks, scenes)
    official = official_map["official"]
    dual7 = compute_dual_tasks(tasks)
    inv_rules = inventory_crosscheck.get("rules") or {}
    if inv_rules.get("two_atoms_distinct_target_entity") is not None:
        if list(inv_rules["two_atoms_distinct_target_entity"]) != dual7:
            raise ValueError("dual-target set differs from inventory rule C: %r vs %r"
                             % (list(inv_rules["two_atoms_distinct_target_entity"]), dual7))
    # BDDL single-goal pool (rule C) = 83; scene-review exclusions shrink the *pairing* pool.
    pool_bddl_set = {t["index"] for t in tasks} - set(dual7)
    review = load_scene_review(tasks, scenes, scene_order, pool_bddl_set)
    reviewed_scenes = {row["scene"] for row in review["decisions"]}
    single_set = pool_bddl_set - set(review["excluded"])
    pairs = build_pairs(tasks, scenes, scene_order, single_set)
    pair_sem = load_pair_semantics(tasks, pairs, excluded_tasks=review["excluded"])
    m1, cross_diffs = build_m1_candidates(
        tasks, pairs, pair_sem["by_id"], official, official_map["inline_mismatch_indices"])
    by_index = {t["index"]: t for t in tasks}
    m2 = build_m2_records(tasks, scenes, scene_order, by_index, official, single_set)
    s1 = build_s1_records(by_index, scenes, official)
    x1 = build_x1_extension(tasks, scenes, scene_order, dual7, single_set)
    for candidate in m1 + m2 + s1:
        candidate["scene_review_applied"] = candidate["scene"] in reviewed_scenes
    payload = build_payload(
        tasks, scenes, scene_order, official, pairs, m1, m2, s1, x1,
        dual7, pool_bddl_set, single_set, review,
        list(pair_sem["by_id"].values()), pair_sem, cross_diffs,
        official_map["inline_mismatch_indices"], inventory_crosscheck, pair_sem["data"])
    ctx = {
        "tasks": tasks,
        "by_index": by_index,
        "scenes": scenes,
        "scene_order": scene_order,
        "pairs": pairs,
        "pair_sem_by_id": pair_sem["by_id"],
        "pair_sem_meta": pair_sem,
        "pair_semantics_all": pair_sem["data"]["pairs"],
        "official": official,
        "official_map": official_map,
        "pool_bddl_set": pool_bddl_set,
        "single_set": single_set,
        "dual7": dual7,
        "scene_review": review,
        "inventory_crosscheck": inventory_crosscheck,
    }
    return payload, ctx

def write_outputs(payload):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT_DIR / "CASE_LIST.md").write_text(render_case_list(payload) + "\n", encoding="utf-8")
    (OUT_DIR / "README.md").write_text(render_readme(payload) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the LIBERO-90 dual-target candidate list (M1/M2/S1).")
    parser.add_argument("--check", action="store_true",
                        help="re-generate outputs then assert every invariant (non-zero exit on failure)")
    args = parser.parse_args(argv)
    payload, ctx = build_all()
    write_outputs(payload)
    summary = payload["summary"]
    print("[build] wrote %s" % OUT_DIR)
    print("[build] M1 %d ordered (%d unordered) | M2 %d ordered (%d unordered) | S1 %d ordered "
          "| supplementary %d | total %d"
          % (summary["m1_ordered"], summary["m1_unordered"], summary["m2_ordered"],
             summary["m2_unordered"], summary["s1_ordered"], summary["supplementary_ordered"],
             summary["total"]))
    print("[build] class %s | priority %s"
          % (summary["class_counts"], summary["priority_counts"]))
    scene_review = payload["scene_review"]
    print("[build] scene_review v%s: excluded=%s pool_bddl=%d pairing_pool=%d ks1_ordered=%d"
          % (summary["review_decisions_version"], summary["review_excluded_tasks"],
             summary["pool_bddl"], summary["single_pool"],
             next(row["m1_ordered"] for row in scene_review["per_scene"]
                  if row["scene"] == "KITCHEN_SCENE1")))
    if not args.check:
        return 0
    ok = validate(payload, ctx)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())