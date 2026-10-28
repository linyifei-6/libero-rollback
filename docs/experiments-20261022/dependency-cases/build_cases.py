#!/usr/bin/env python3
"""Build the LIBERO-GOAL dependency-case catalog (for user review; no GPU)."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path("/home/tarowang/workspace/roboot/libero-rollback")
TP = Path("/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero/libero/libero")
BDDL_DIR = TP / "bddl_files/libero_goal"
OUT = REPO / "runs/expand-tasks-20261022/artifacts/dependency-cases"
PAIR_CAT = json.loads((REPO / "docs/experiments-20261019/goal_pair_catalog.json").read_text())
SPEC = json.loads((REPO / "docs/experiments-20261019/libero_std_task_spec.json").read_text())
PRIOR = json.loads((REPO / "docs/experiments-20261019/combined_twosubtask.json").read_text())


def section(src, name):
    i = src.find("(" + name)
    depth = 0
    k = i
    while k < len(src):
        if src[k] == "(":
            depth += 1
        elif src[k] == ")":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return src[i:k + 1]


def parse_bddl(name):
    src = (BDDL_DIR / (name + ".bddl")).read_text(encoding="utf-8")
    m = re.search(r"\(:language\s+([^()]*)\)", src)
    goals = re.findall(r"\((?:Open|In|On|Turnon|Turnoff)\s+[^()]*\)", section(src, ":goal"))
    regions = {}
    for mm in re.finditer(r"\((\w+)\s+\n?\s*\(:target\s+(\w+)\)", section(src, ":regions")):
        regions[mm.group(1)] = mm.group(2)
    objs = re.findall(r"(\w[\w\-]*)\s*-\s*(\w[\w\-]*)", section(src, ":objects"))
    return {"bddl_language": m.group(1).strip() if m else "",
            "goal_atoms": goals, "regions": regions,
            "objects": [{"instance": a, "type": b} for a, b in objs]}


idx_name = {}
for p in PAIR_CAT["pairs"]:
    idx_name.setdefault(p["i"], p["tasks"][0])
    idx_name.setdefault(p["j"], p["tasks"][1])
spec_lang = {t["idx"]: t["language"] for t in SPEC["suites"]["LIBERO_GOAL"]["tasks"]}
spec_name = {t["idx"]: t["name"] for t in SPEC["suites"]["LIBERO_GOAL"]["tasks"]}
tasks = []
for i in range(10):
    name = idx_name.get(i) or spec_name[i]
    info = parse_bddl(name)
    tasks.append({"idx": i, "name": name, "language": spec_lang[i],
                  "bddl_language": info["bddl_language"], "goal_atoms": info["goal_atoms"],
                  "regions": info["regions"], "objects": info["objects"]})

prior_eps = {}
for e in PRIOR.get("episodes") or []:
    m = re.match(r"^goal_pair_(\d+)_(\d+)$", e.get("bddl") or "")
    if not m:
        continue
    key = "%02d_%02d" % tuple(sorted((int(m.group(1)), int(m.group(2)))))
    prior_eps.setdefault(key, []).append(e)
prior_result = {}
for key, eps in prior_eps.items():
    ok = any(e.get("success") for e in eps)
    steps = [e.get("steps") for e in eps if e.get("success")][:3]
    runs = sorted({e.get("run") for e in eps if e.get("run")})
    sub = [sum(1 for s in e.get("subtasks") or [] if s.get("first_true_step") is not None) for e in eps]
    prior_result[key] = {"success": ok, "runs": runs, "success_steps": steps,
                         "episodes": len(eps), "max_subtasks_completed": max(sub) if sub else None}

official = {t["idx"]: t["language"] for t in tasks}
bddl_lang = {t["idx"]: t["bddl_language"] for t in tasks}
cat_by_id = {p["pair_id"]: p for p in PAIR_CAT["pairs"]}

MOVABLE = {"akita_black_bowl_1", "plate_1"}


def place_relation(atom):
    parts = atom.strip("()").split()
    if len(parts) == 3 and parts[0] in ("On", "In"):
        return parts[0], parts[1], parts[2]
    return None


def dependency_of(i, j):
    a1, a2 = tasks[i]["goal_atoms"], tasks[j]["goal_atoms"]
    for atom1 in a1:
        pr = place_relation(atom1)
        if not pr:
            continue
        rel, a, b = pr
        if b not in MOVABLE or a in MOVABLE:
            continue
        for atom2 in a2:
            pr2 = place_relation(atom2)
            if pr2 and pr2[1] == b:
                return "container_move", {"A": a, "B": b, "C": pr2[2], "atom1": atom1, "atom2": atom2}
    for atom1 in a1:
        if atom1.startswith("(Turnon "):
            f = atom1.strip("()").split()[1]
            for atom2 in a2:
                if f in atom2:
                    return "turnon_then_place", {"F": f, "atom1": atom1, "atom2": atom2}
    for atom1 in a1:
        pr = place_relation(atom1)
        if pr and pr[1] in MOVABLE and pr[0] in ("On", "In"):
            b = pr[1]
            for atom2 in a2:
                pr2 = place_relation(atom2)
                if pr2 and pr2[2] == b and pr2[1] not in MOVABLE:
                    return "reverse_dependency", {"B": b, "A": pr2[1], "atom1": atom1, "atom2": atom2}
    return None, None


original_45, reversed_45 = [], []
for p in PAIR_CAT["pairs"]:
    i, j = p["i"], p["j"]
    pat_o, det_o = dependency_of(i, j)
    pat_r, det_r = dependency_of(j, i)
    original_45.append({
        "pair_id": p["pair_id"], "order": "original(i<j)", "first_task": i, "second_task": j,
        "tasks": p.get("tasks"), "instruction": p.get("language"),
        "goal_atoms": p.get("goal_atoms"), "classification": p.get("classification"),
        "dependency_pattern": pat_o, "dependency_detail": det_o,
        "prior_result": prior_result.get(p["pair_id"], {}),
    })
    canonical = "%02d_%02d" % (min(i, j), max(i, j))
    reversed_45.append({
        "pair_id": "%02d_%02d" % (j, i), "order": "reversed(j>i)", "first_task": j, "second_task": i,
        "tasks": [tasks[j]["name"], tasks[i]["name"]],
        "instruction": official[j] + " and " + official[i],
        "goal_atoms": cat_by_id[canonical]["goal_atoms"],
        "canonical_goal": canonical, "classification": p.get("classification"),
        "dependency_pattern": pat_r, "dependency_detail": det_r,
        "prior_result": prior_result.get(canonical, {}),
        "note": "与 %s 同 goal，仅 instruction 顺序不同；顺序/措辞本身不构成新任务" % canonical,
    })

native = {}
for e in original_45 + reversed_45:
    if e["dependency_pattern"]:
        native[e["pair_id"]] = dict(e)


def dest_atom(obj, dest, rel):
    return "(%s %s %s)" % (rel, obj, dest)


bowl, cheese, plate = "akita_black_bowl_1", "cream_cheese_1", "plate_1"
dest_bowl = [
    # dest, relation, instruction phrase, origin(native/synthetic), native pair, risk
    ("flat_stove_1_cook_region", "On", "put the bowl on the stove", "native", "06_01", "low"),
    ("wooden_cabinet_1_top_side", "On", "put the bowl on the top of the cabinet", "native", "06_04", "low"),
    ("plate_1", "On", "put the bowl on the plate", "native", "06_08", "low"),
    ("wooden_cabinet_1_top_region", "In", "open the top drawer of the cabinet and put the bowl inside", "native", "06_03", "medium"),
    ("wooden_cabinet_1_middle_region", "In", "open the middle drawer of the cabinet and put the bowl inside", "synthetic", None, "medium"),
    ("wooden_cabinet_1_bottom_region", "In", "open the bottom drawer of the cabinet and put the bowl inside", "synthetic", None, "medium"),
    ("wine_rack_1_top_region", "On", "put the bowl on the wine rack", "synthetic", None, "high"),
    ("main_table_stove_front_region", "On", "put the bowl at the front of the stove", "synthetic", None, "medium"),
]
synthetic = []
for dest, rel, phrase, origin, pair, risk in dest_bowl:
    cid = ("goal_pair_" + pair) if pair else ("synthetic_dep_bowl_" + dest.replace("_region", "").replace("_", ""))
    synthetic.append({
        "case_id": cid, "family": "container_move",
        "pattern": "把 A 放到 B 上/里；再把 B 移到 C",
        "A": cheese, "B": bowl, "C": dest,
        "instruction": "put the cream cheese on the bowl and " + phrase,
        "goal_atoms": ["(On cream_cheese_1 akita_black_bowl_1)", dest_atom(bowl, dest, rel)],
        "origin": origin,
        "region_exists": True, "risk": risk,
        "prior_result": prior_result.get(pair, {}) if pair else {},
        "note": ("与已有 pair %s 相同 goal（仅 instruction 顺序不同，不是新任务）" % pair)
                if pair else "新 goal 组合：场景 region 存在；需生成 bddl 后做静态/动态验证",
        "recommend": "推荐" if risk == "low" else ("备选" if risk == "medium" else "风险高/最后"),
    })

plate_cases = [
    ("main_table_stove_front_region", "push the plate to the front of the stove", "On", "high"),
    ("wooden_cabinet_1_top_side", "put the plate on the top of the cabinet", "On", "high"),
    ("flat_stove_1_cook_region", "put the plate on the stove", "On", "high"),
]
for dest, phrase, rel, risk in plate_cases:
    synthetic.append({
        "case_id": "synthetic_dep_plate_" + dest.replace("_region", "").replace("_", ""),
        "family": "container_move_plate",
        "pattern": "把 A 放到 plate 上；再移动 plate 到 C",
        "A": cheese, "B": plate, "C": dest,
        "instruction": "put the cream cheese on the plate and " + phrase,
        "goal_atoms": ["(On cream_cheese_1 plate_1)", dest_atom(plate, dest, rel)],
        "origin": "synthetic", "region_exists": True, "risk": risk, "prior_result": {},
        "note": "plate 是可推动物体（任务5）但非抓取物体；推动中 cheese 可能滑落 → 高风险",
        "recommend": "风险高/最后",
    })

chains = [
    ("synthetic_chain_cheese_bowl_plate_stove_front", "extended_chain",
     "A→B、B→C、C→D 三段链",
     "put the cream cheese on the bowl, put the bowl on the plate, and push the plate to the front of the stove",
     ["(On cream_cheese_1 akita_black_bowl_1)", "(On akita_black_bowl_1 plate_1)",
      "(On plate_1 main_table_stove_front_region)"], "high",
     "三段链；600 步可能不够，建议 800–1000+"),
    ("synthetic_chain_cheese_bowl_stove_on", "extended_chain",
     "A→B、B→C、turnon C",
     "put the cream cheese on the bowl, put the bowl on the stove, and turn on the stove",
     ["(On cream_cheese_1 akita_black_bowl_1)", "(On akita_black_bowl_1 flat_stove_1_cook_region)",
      "(Turnon flat_stove_1)"], "medium", "三段链；最后 turnon 是 GOAL 任务7 目标"),
    ("synthetic_chain_open_top_bowl_cheese", "extended_chain",
     "打开容器 → 把 B 放入 → 把 A 放到 B 上",
     "put the cream cheese on the bowl, open the top drawer of the cabinet, and put the bowl inside",
     ["(On cream_cheese_1 akita_black_bowl_1)",
      "(In akita_black_bowl_1 wooden_cabinet_1_top_region)"], "medium",
     "与 06_03 相同 goal（仅 instruction 多写明 open），不是新任务"),
    ("synthetic_chain_open_middle_bowl_cheese", "extended_chain",
     "打开容器 → 把 B 放入 → 把 A 放到 B 上",
     "open the middle drawer of the cabinet, put the bowl inside, and put the cream cheese on the bowl",
     ["(Open wooden_cabinet_1_middle_region)",
      "(In akita_black_bowl_1 wooden_cabinet_1_middle_region)",
      "(On cream_cheese_1 akita_black_bowl_1)"], "high",
     "含 open 原子；抽屉打开后放碗；碗在抽屉里再放 cheese 可能不可达"),
]
for cid, family, pattern, instr, atoms, risk, note in chains:
    synthetic.append({"case_id": cid, "family": family, "pattern": pattern,
                      "A": cheese, "B": bowl, "C": "", "instruction": instr,
                      "goal_atoms": atoms, "origin": "synthetic", "region_exists": True,
                      "risk": risk, "prior_result": {}, "note": note,
                      "recommend": "备选" if risk == "medium" else "风险高/最后"})

# 标记“是否新 goal”（native pair / 重复 goal 的变体不算新任务）
native_goals = {tuple(sorted(e["goal_atoms"])) for e in native.values()}
for c in synthetic:
    if c["origin"] == "native":
        c["is_new_goal"] = False
        c["task_kind"] = "instruction_variant_of_existing_goal"
    else:
        key = tuple(sorted(c["goal_atoms"]))
        c["is_new_goal"] = key not in native_goals
        c["task_kind"] = "new_goal" if c["is_new_goal"] else "instruction_variant_of_existing_goal"

catalog = {
    "suite": "LIBERO-GOAL",
    "purpose": "dependency-style two-subtask case catalog (for review; no dynamic runs yet)",
    "goal_tasks": tasks,
    "ordered_pairs": {"original_45": original_45, "reversed_45": reversed_45,
                      "ref_note": "顺序/措辞变体不构成新任务；仅用于按依赖方向组织 instruction。"},
    "dependency_native": {k: [e for e in native.values() if e["dependency_pattern"] == k]
                          for k in ("container_move", "turnon_then_place", "reverse_dependency")},
    "synthetic_candidates": synthetic,
    "counts": {
        "goal_tasks": 10,
        "ordered_original_45": len(original_45),
        "ordered_reversed_45": len(reversed_45),
        "native_dependency_total": len(native),
        "native_container_move": len([e for e in native.values() if e["dependency_pattern"] == "container_move"]),
        "native_turnon_then_place": len([e for e in native.values() if e["dependency_pattern"] == "turnon_then_place"]),
        "native_reverse_dependency": len([e for e in native.values() if e["dependency_pattern"] == "reverse_dependency"]),
        "new_goal_candidates": len([c for c in synthetic if c.get("is_new_goal")]),
        "instruction_variant_candidates": len([c for c in synthetic if not c.get("is_new_goal")]),
        "total_candidates_for_review": len(synthetic),
    },
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "cases.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False))
print("wrote", OUT / "cases.json")
print("counts:", json.dumps(catalog["counts"], ensure_ascii=False))
print("\nnative dependency:")
for k, arr in catalog["dependency_native"].items():
    for e in arr:
        print(" ", k, "|", e["pair_id"], "|", e["instruction"])
print("\nnew synthetic candidates:")
for c in synthetic:
    if c["origin"] == "synthetic":
        print(" ", c["case_id"], "|", c["risk"], "|", c["instruction"])
