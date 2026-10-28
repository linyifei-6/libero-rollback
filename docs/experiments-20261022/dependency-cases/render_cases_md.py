#!/usr/bin/env python3
"""Render CASE_CATALOG.md from cases.json (review-only; no GPU)."""
import json
from pathlib import Path

OUT = Path("/home/tarowang/workspace/roboot/libero-rollback/runs/expand-tasks-20261022/artifacts/dependency-cases")
cat = json.loads((OUT / "cases.json").read_text())
tasks = cat["goal_tasks"]
counts = cat["counts"]
orig = cat["ordered_pairs"]["original_45"]
rev = cat["ordered_pairs"]["reversed_45"]
native = cat["dependency_native"]
synt = cat["synthetic_candidates"]

PAT = {"container_move": "容器移动（A 放 B 上/里 → B 移到 C）",
       "turnon_then_place": "先开火再放（Turnon F → 物体放 F）",
       "reverse_dependency": "反向依赖（先移动 B → 再把 A 放 B 上）"}
RISK = {"low": "低", "medium": "中", "high": "高"}


def prior_text(pr):
    if not pr or not pr.get("episodes"):
        return "未测（上一轮未覆盖）"
    if pr.get("success"):
        steps = ",".join(str(s) for s in (pr.get("success_steps") or [])[:3])
        return "成功（%d 条；成功步数 %s；runs: %s）" % (pr["episodes"], steps, ",".join(pr.get("runs") or []))
    return "失败（%d 条；最多完成子任务 %s）" % (pr["episodes"], pr.get("max_subtasks_completed"))


def task_table():
    rows = ["| idx | task 名 | 官方 language | BDDL goal atoms |", "|---|---|---|---|"]
    for t in tasks:
        rows.append("| %d | %s | %s | %s |" % (
            t["idx"], t["name"], t["language"], "<br>".join(t["goal_atoms"])))
    return "\n".join(rows)


def ordered_table(items, title):
    rows = [f"### {title}", "",
            "| pair_id | 顺序 | instruction | goal atoms | 依赖模式 | 上一轮结果 |",
            "|---|---|---|---|---|---|"]
    for e in items:
        pat = PAT.get(e.get("dependency_pattern"), "—")
        rows.append("| %s | %d→%d | %s | %s | %s | %s |" % (
            e["pair_id"], e["first_task"], e["second_task"], e["instruction"],
            "<br>".join(e["goal_atoms"]), pat, prior_text(e.get("prior_result"))))
    return "\n".join(rows)


def native_section():
    out = ["### 3.1 原生依赖（container_move：A 放 B → B 移到 C）", ""]
    out.append("| case | instruction | goal atoms | 上一轮结果 | 说明 |")
    out.append("|---|---|---|---|---|")
    for e in native["container_move"]:
        note = "与反向 %s 同 goal" % ("01_06" if e["pair_id"] == "06_01" else
                                      "03_06" if e["pair_id"] == "06_03" else
                                      "04_06" if e["pair_id"] == "06_04" else "08_06")
        if e["pair_id"] == "06_08":
            note = "上一轮唯一成功过的 GOAL 组合之一（pilot 318 步；dependency 复测 278 步）"
        out.append("| %s | %s | %s | %s | %s |" % (
            e["pair_id"], e["instruction"], "<br>".join(e["goal_atoms"]),
            prior_text(e.get("prior_result")), note))
    out += ["", "### 3.2 原生依赖（turnon_then_place：先开火，再放物体）", ""]
    out.append("| case | instruction | goal atoms | 上一轮结果 | 说明 |")
    out.append("|---|---|---|---|---|")
    for e in native["turnon_then_place"]:
        out.append("| %s | %s | %s | %s | 与反向 01_07 同 goal |" % (
            e["pair_id"], e["instruction"], "<br>".join(e["goal_atoms"]),
            prior_text(e.get("prior_result"))))
    out += ["", "### 3.3 反向依赖（先移动 B，再把 A 放到 B 上）", "",
            "| case | instruction | goal atoms | 上一轮结果 | 说明 |", "|---|---|---|---|---|"]
    for e in native["reverse_dependency"]:
        note = "把 06→01/03/04/08 的自然依赖顺序反写；goal 与 06_0x 相同（不是新任务）"
        if e["pair_id"] == "08_06":
            note = "与 06_08 同 goal；该顺序在上一轮 pilot 中成功过（318 步）——但 goal 相同，顺序本身不是新任务"
        out.append("| %s | %s | %s | %s | %s |" % (
            e["pair_id"], e["instruction"], "<br>".join(e["goal_atoms"]),
            prior_text(e.get("prior_result")), note))
    return "\n".join(out)


def synthetic_section():
    out = ["### 4.1 新 goal 候选（推荐优先审核）", "",
           "| case_id | 类型/模式 | instruction | goal atoms | risk | 建议 | 备注 |",
           "|---|---|---|---|---|---|---|"]
    for c in synt:
        if not c.get("is_new_goal"):
            continue
        out.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            c["case_id"], c.get("family") or c.get("pattern"), c["instruction"],
            "<br>".join(c["goal_atoms"]), RISK.get(c["risk"], c["risk"]),
            c["recommend"], c.get("note") or ""))
    out += ["", "### 4.2 已有 goal 的 instruction 变体（**不是新任务**，仅用于对照）", "",
            "| case_id | instruction | 与已有 goal 的关系 | goal atoms |", "|---|---|---|---|"]
    for c in synt:
        if c.get("is_new_goal"):
            continue
        out.append("| %s | %s | %s | %s |" % (
            c["case_id"], c["instruction"], c.get("note") or "同已有 goal",
            "<br>".join(c["goal_atoms"])))
    return "\n".join(out)


md = []
A = md.append
A("# LIBERO-GOAL 依赖型双子任务 case 目录（供审核，尚未跑动态实验）")
A("")
A("> 目的：拓展 **“put A on/in B, and put B on/in C”** 类型的双子任务（A→B→C 链式依赖）。")
A("> 本文件只做**静态罗列与分类**，不含新的动态运行数据；数据来源：LIBERO 原始 GOAL bddl/init、")
A("> `docs/experiments-20261019/`（上一轮 45 对结果与 10 任务清单）。")
A("")
A("## 0. 摘要与关键结论")
A("")
A("| 项目 | 数量 |")
A("|---|---|")
A("| GOAL 单任务 | %d |" % counts["goal_tasks"])
A("| 原有 ordered 组合（i<j，上一轮 45 对） | %d |" % counts["ordered_original_45"])
A("| 反向 ordered 组合（j→i，本次补齐的 45 对） | %d |" % counts["ordered_reversed_45"])
A("| 原生依赖 case（GOAL 10 任务内部可构成） | %d（container_move %d / turnon_then_place %d / reverse_dependency %d） |" % (
    counts["native_dependency_total"], counts["native_container_move"],
    counts["native_turnon_then_place"], counts["native_reverse_dependency"]))
A("| **新 goal 候选（真正新增任务）** | **%d** |" % counts["new_goal_candidates"])
A("| instruction 变体（已有 goal，**不算新任务**） | %d |" % counts["instruction_variant_candidates"])
A("")
A("**关键结论**")
A("")
A("- 顺序/措辞变体不构成新任务（见 §6 与你的第 1 点）：同一 goal+init 的不同 instruction 只是同一任务的不同说法；")
A("  VLA 对指令不敏感时，甚至不给指令也会按原任务执行——因此本目录中 `instruction_variant` 条目只作对照，不计入任务扩充。")
A("- 真正可扩充的是 **新 goal 组合**：把 A→B→C 链中的 C 换成场景中其他可放置/可移动目标（§4.1 的 10 个候选）；")
A("  其中 native container_move 4 个已经是现有 GOAL 任务能构成的组合（06_01/06_03/06_04/06_08），其余为槽位替换。")
A("- 上一轮唯一成功的 GOAL 组合 06_08（cheese→bowl→plate）正是该依赖类型的代表：**结构上合理、B 移动目标近（plate）**；")
A("  而 06_01/06_03/06_04 上一轮（反向书写）都失败，说明“依赖结构”并不自动保证可解，仍需逐条验证。")
A("- `goal_pair_04_07` 的成功更像偶然（见 §5）：单 seed 的成功不能作为“可解 baseline”的依据，必须多 seed 复核。")
A("")
A("## 1. LIBERO-GOAL 10 个单任务")
A("")
A(task_table())
A("")
A("说明：场景是同一个 kitchen/living-room 场景，可动物体只有 `akita_black_bowl_1`、`cream_cheese_1`、`wine_bottle_1`、`plate_1`；")
A("`plate_1` 是“可推动”（任务 5）而不是常规抓取物体；`wooden_cabinet_1`、`flat_stove_1`、`wine_rack_1`、`main_table` 为 fixture。")
A("")
A("## 2. 45 + 45 个 ordered 组合（补齐顺序维度）")
A("")
A("> 注意：每组 ordered pair 与 canonical（i<j）**goal/init 完全相同**，只是 instruction 两个子句顺序不同；")
A("> 按第 1 点，它们**不是新任务**。这里列出是为了把依赖方向显式化，并让后续实验的 instruction 与实际操作顺序一致。")
A("")
A(ordered_table(orig, "2.1 原有 45 个 ordered 组合（i<j，上一轮已评估 goal）"))
A("")
A(ordered_table(rev, "2.2 本次补齐的 45 个反向 ordered 组合（j→i，**不是新任务**）"))
A("")
A("## 3. 原生依赖 case（GOAL 10 任务内部即可构成）")
A("")
A("依赖模式定义：")
A("")
A("- **container_move**：第一个子任务把 A 放到 B（可动物体）上/里，第二个子任务把 B 移到 C；")
A("- **turnon_then_place**：第一个子任务打开 fixture，第二个子任务把物体放到该 fixture 上；")
A("- **reverse_dependency**：先移动 B，再把 A 放到 B 上（与 container_move 同 goal、顺序相反）。")
A("")
A(native_section())
A("")
A("## 4. 新 goal 候选（真正可扩充的任务）")
A("")
A("生成规则：B=`akita_black_bowl_1`、A=`cream_cheese_1` 固定；C 从 GOAL 场景 region/object 中枚举；")
A("instruction 均写成“put the cream cheese on the bowl and <把 bowl 移到 C>”；goal atoms =")
A("`(On cream_cheese_1 akita_black_bowl_1)` + `(On/In bowl C)`。风险为静态物理判断（低/中/高），未跑动态。")
A("")
A(synthetic_section())
A("")
A("## 5. 关于 04_07 的“幸运成功”：对任务扩充的启发")
A("")
A("`goal_pair_04_07`（bowl on cabinet top + turn on stove）上一轮单 seed 成功（397 步），但从视频看：")
A("完成 subtask1 后模型先去开了抽屉、又尝试多次才完成 subtask2——**不是干净的依赖链执行，而是探索/重试后的偶然成功**。启发：")
A("")
A("1. **单 seed 成功不能作为“任务可解”的判据**；新任务必须用多 seed（建议 ≥3）复核，并记录成功步数分布（04_07 的 397 步已接近 600 上限）。")
A("2. 组合任务的“可解”应定义为**稳定的成功率**（如 3 seed 中 ≥2 成功），而不是偶尔一次通过；否则 rollback 的 baseline/injection 时机会不稳定。")
A("3. 正向 case 的价值在于提示：**两个子任务都落在模型熟悉技能内时，模型可能靠探索完成第二个**；")
A("   因此新任务的可解性更取决于“第二子任务是否在模型技能分布内 + 目标可达”，而不是语义依赖本身。")
A("4. 对 rollback 用例设计：模型有自己的失败→重试行为（开抽屉、重新抓取），rollback 注入点应避开这类“探索期”，")
A("   或在实验中显式记录 exploration 步数作为协变量。")
A("")
A("## 6. 关于“顺序/paraphrase 变体不算新任务”的确认")
A("")
A("- 同意：任务身份 = 环境 + 初始状态 + goal 判定 + 必要技能序列；instruction 顺序/措辞不改变 goal/init，因此**不是新任务**。")
A("- 现有实验也支持：`ord_*` 顺序变体 6/6 成功只是模型按原 goal 执行，并不是新任务被解决；")
A("  `then/andthen/swap` 等 7 条变体在未知组合上 0/7 也说明顺序不是关键变量。")
A("- 本目录把 45 反向 ordered 列出来只用于**确认依赖方向与自然语言顺序**，不应计入“任务扩充”的 KPI。")
A("")
A("## 7. 建议的下一步（等审核）")
A("")
A("1. **先跑原生依赖 5 条**（06_01/06_03/06_04/06_08/07_01）作为“自然依赖顺序”的基线（虽然与已有 goal 相同，但可验证 instruction 顺序是否真的不影响结果；预计 06_08 成功、其余失败）。")
A("2. **新 goal 候选优先 5–6 条**（低/中风险）：`synthetic_dep_bowl_woodencabinet1middle`、`synthetic_dep_bowl_woodencabinet1bottom`、")
A("   `synthetic_dep_bowl_maintablestovefront`、`synthetic_chain_cheese_bowl_stove_on`、`synthetic_dep_bowl_winerack1top`（高风险备选）。")
A("3. **高风险的 plate 移动/三段链**先只做静态验证与单 seed 试探；不在第一轮全量跑。")
A("4. 所有新候选先做：生成 bddl（沿用源任务 init）→ BDDL/env 静态冒烟（初始 success=False、atoms 可解析）→ 多 seed 动态（≥3，600 步；三段链 800+）。")
A("5. 通过标准建议：多 seed 成功 ≥2/3 且成功步数 <80% max_steps，才纳入 baseline 任务池。")
A("")
A("## 8. 审核问题")
A("")
A("1. **新 goal 候选 10 条**是否全部进入静态验证？还是先按推荐 5–6 条？")
A("2. plate 作为 B 的 3 条（推动 plate）风险高：是否只保留 `push the plate to the front of the stove` 一条？")
A("3. 三段链（cheese→bowl→plate→stove front）是否纳入本轮，还是等二段链验证后再做？")
A("4. 原生依赖 5 条（与已有 goal 相同）是否值得先跑？我们预期结果与上一轮相同（06_08 成功、其余失败）。")
A("5. 多 seed 门槛用 3 seed 中 ≥2 成功是否合适？")
A("")
A("---")
A("")
A("_生成脚本：`runs/expand-tasks-20261022/artifacts/dependency-cases/build_cases.py`；数据：`cases.json`；本文件只读静态目录，未运行新动态 episode。_")

(OUT / "CASE_CATALOG.md").write_text("\n".join(md) + "\n")
print("wrote", OUT / "CASE_CATALOG.md", "lines:", len(md))
