"""Generate docs/libero-90-task-inventory.md from the LIBERO-90 BDDL suite.

The English instructions, goal atoms and stage counts are parsed from the source
BDDL files; the Chinese translations, tier labels and notes are authored here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_libero90_tasks import (  # noqa: E402
    DEFAULT_SUITE,
    describe_atom,
    find_block,
    flatten_goal,
    parse_sexp,
    scene_of,
    tokenize,
)

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "libero-90-task-inventory.md"

ZH = {
    0: "打开橱柜上层抽屉，把碗放进去",
    1: "把黑碗放到橱柜顶上",
    2: "把黑碗放到盘子上",
    3: "打开橱柜上层抽屉",
    4: "打开橱柜下层抽屉",
    5: "打开炉子，把煎锅放上去",
    6: "把煎锅放到炉子上",
    7: "把摩卡壶放到炉子上",
    8: "打开炉子",
    9: "关上橱柜下层抽屉，打开上层抽屉",
    10: "把酒瓶放到酒架上",
    11: "把黑碗放到橱柜顶上",
    12: "把黑碗放进橱柜下层抽屉",
    13: "把酒瓶放进橱柜下层抽屉",
    14: "关上橱柜下层抽屉",
    15: "把黄白马克杯放到白瓷杯前面",
    16: "关上微波炉",
    17: "把右边的摩卡壶放到炉子上",
    18: "关掉炉子",
    19: "打开炉子，把煎锅放上去",
    20: "把煎锅放到柜架顶上",
    21: "把白碗放到柜架顶上",
    22: "把煎锅放到柜架隔板上",
    23: "把煎锅放到柜架隔板下面",
    24: "打开炉子",
    25: "关上橱柜上层抽屉，把黑碗放到柜顶",
    26: "把前排的黄油放进橱柜上层抽屉并关上",
    27: "把后排的黄油放进橱柜上层抽屉并关上",
    28: "把巧克力布丁放进橱柜上层抽屉并关上",
    29: "把黑碗放进橱柜上层抽屉",
    30: "关上橱柜上层抽屉",
    31: "拿起番茄沙司放进篮子",
    32: "拿起奶油芝士盒放进篮子",
    33: "拿起字母汤罐头放进篮子",
    34: "拿起番茄酱罐头放进篮子",
    35: "拿起橙汁放进篮子",
    36: "拿起牛奶放进篮子",
    37: "拿起黄油放进篮子",
    38: "拿起字母汤罐头放进篮子",
    39: "拿起番茄酱罐头放进篮子",
    40: "把左边的碗叠到右边的碗上，再把两只碗一起放进托盘",
    41: "把右边的碗叠到左边的碗上，再把两只碗一起放进托盘",
    42: "拿起左边的黑碗放进托盘",
    43: "拿起沙拉酱放进托盘",
    44: "拿起巧克力布丁放进托盘",
    45: "把白瓷杯放到左边的盘子上",
    46: "把黄白马克杯放到右边的盘子上",
    47: "把红马克杯放到左边的盘子上",
    48: "把红马克杯放到右边的盘子上",
    49: "把白瓷杯放到盘子上",
    50: "把红马克杯放到盘子上",
    51: "把巧克力布丁放到盘子左边",
    52: "把巧克力布丁放到盘子右边",
    53: "把后排的黑碗放到盘子上",
    54: "把前排的黑碗放到盘子上",
    55: "把中间的黑碗放到盘子上",
    56: "把中间的黑碗放到橱柜顶上",
    57: "打开橱柜上层抽屉",
    58: "把中间的黑碗叠到前排的黑碗上",
    59: "把前排的黑碗叠到中间的黑碗上",
    60: "把黑碗放进橱柜上层抽屉",
    61: "把黑碗放到盘子上",
    62: "把番茄沙司放进橱柜上层抽屉",
    63: "把黑碗放到橱柜顶上",
    64: "关上橱柜上层抽屉",
    65: "把白碗放到盘子上",
    66: "把白碗放到盘子右边",
    67: "打开微波炉",
    68: "拿起书放进收纳架的左格",
    69: "拿起书放进收纳架的右格",
    70: "拿起书放进收纳架的前格",
    71: "拿起黄白马克杯放到收纳架右边",
    72: "拿起书放进收纳架的左格",
    73: "拿起书放进收纳架的右格",
    74: "拿起书放进收纳架的前格",
    75: "拿起书放进收纳架的后格",
    76: "拿起书放进收纳架的左格",
    77: "拿起书放进收纳架的右格",
    78: "拿起书放进收纳架的前格",
    79: "拿起白瓷杯放到收纳架右侧",
    80: "拿起红马克杯放到收纳架右侧",
    81: "拿起右边的书放到柜架隔板下面",
    82: "拿起中间的书放到柜架隔板上",
    83: "拿起左边的书放到架子顶上",
    84: "拿起右边的书放到柜架隔板上",
    85: "拿起字母汤罐头放进托盘",
    86: "拿起番茄酱罐头放进托盘",
    87: "拿起黄油放进托盘",
    88: "拿起奶油芝士放进托盘",
    89: "拿起番茄沙司放进托盘",
}

# Selected rollback base candidates: s1 / s2 decomposition, tier and rationale.
SELECTED = {
    26: dict(
        tier="A",
        prio="P0",
        s1="`(In butter_1 wooden_cabinet_1_top_region)` 前排黄油入上层抽屉",
        s2="`(Close wooden_cabinet_1_top_region)` 关上上层抽屉",
        mech="放置 + 关节回退（`revert_articulation_goal`，slide）",
        note="与 LIBERO-10 `/01`（t33 黑碗入下层抽屉 + 关抽屉）同构，已跑通的三段合法窗口（`post_completion_retreat` / `x3a_actuation` / `x3b_completion_approach`）可直接迁移；与 #27 构成前排/后排对照。",
    ),
    27: dict(
        tier="A",
        prio="P0",
        s1="`(In butter_2 wooden_cabinet_1_top_region)` 后排黄油入上层抽屉",
        s2="`(Close wooden_cabinet_1_top_region)` 关上上层抽屉",
        mech="放置 + 关节回退（slide）",
        note="与 #26 同场景、同关节，只替换被放置物体；两者对照可分离“物体身份/初始位姿”与“关节回退”两个因素。",
    ),
    28: dict(
        tier="A",
        prio="P0",
        s1="`(In chocolate_pudding_1 wooden_cabinet_1_top_region)` 布丁入上层抽屉",
        s2="`(Close wooden_cabinet_1_top_region)` 关上上层抽屉",
        mech="放置 + 关节回退（slide）",
        note="同场景第三种物体，验证结论不依赖单一物体几何（黄油盒 vs 布丁杯）。",
    ),
    0: dict(
        tier="A",
        prio="P1",
        s1="`(Open wooden_cabinet_1_top_region)` 打开上层抽屉",
        s2="`(In akita_black_bowl_1 wooden_cabinet_1_top_region)` 把碗放进抽屉",
        mech="关节回退（slide）+ 放置",
        note="与 #26–28 顺序相反：s1 是关节、s2 是放置，回滚 s1 等于把已打开的抽屉重新推回。覆盖“开放型关节目标被撤销”，现有数据集只有“关闭型”（t33/t78）。需确认回滚窗口内机械臂正持碗接近抽屉时抽屉回退不与之碰撞。",
    ),
    25: dict(
        tier="A",
        prio="P1",
        s1="`(Close wooden_cabinet_1_top_region)` 关上上层抽屉",
        s2="`(On akita_black_bowl_1 wooden_cabinet_1_top_side)` 把黑碗放到柜顶",
        mech="关节回退（slide）+ 放置",
        note="s2 的落点是柜顶平面（`top_side`）而非容器内部，可与 #26–28 对照“恢复后关系是否仍可达成”；回滚 s1 会让抽屉朝机械臂方向滑出，需在有效性约束中显式检查碰撞。",
    ),
    9: dict(
        tier="A",
        prio="P2",
        s1="`(Close white_cabinet_1_bottom_region)` 关上下层抽屉（初始为开）",
        s2="`(Open white_cabinet_1_top_region)` 打开上层抽屉",
        mech="关节回退 + 关节回退（同一柜体两个关节）",
        note="唯一一条两段都是关节的目标。可检验“同一刚体上另一个关节正在动作时回退已完成的关节”。前提：上层与下层必须是可独立寻址的两个 joint_role，需在 runtime profile 中确认。",
    ),
    40: dict(
        tier="B",
        prio="P3",
        s1="`(On akita_black_bowl_1 akita_black_bowl_2)` 把左碗叠到右碗上",
        s2="`(In akita_black_bowl_2 wooden_tray_1_contain_region)` 把叠好的碗一起放进托盘",
        mech="放置 + 放置",
        note="机制可用，但 s2 期间两碗作为一个整体在夹爪中移动，回滚 s1（把上碗取下）只能在放置完成后或搬运中的极窄窗口进行，需先定义可干预时机；完成后可分别撤销“入托盘”和“叠放”两个关系。",
    ),
    41: dict(
        tier="B",
        prio="P3",
        s1="`(On akita_black_bowl_2 akita_black_bowl_1)` 把右碗叠到左碗上",
        s2="`(In akita_black_bowl_1 wooden_tray_1_contain_region)` 把叠好的碗一起放进托盘",
        mech="放置 + 放置",
        note="#40 的镜像，用于检验恢复顺序是否被固定物体身份影响。限制同 #40。",
    ),
    5: dict(
        tier="C",
        prio="暂不推荐",
        s1="`(Turnon flat_stove_1)` 打开炉子",
        s2="`(On chefmate_8_frypan_1 flat_stove_1_cook_region)` 把煎锅放上炉子",
        mech="开关目标（当前未建模）+ 放置",
        note="与 LIBERO-10 `/00`（t0）同构：runtime profile 未建模 Turnon，没有对应的 articulation/joint 段，s1 目前无法回滚。需先补开关建模配置才可入选。",
    ),
    19: dict(
        tier="C",
        prio="暂不推荐",
        s1="`(Turnon flat_stove_1)` 打开炉子",
        s2="`(On chefmate_8_frypan_1 flat_stove_1_cook_region)` 把煎锅放上炉子",
        mech="开关目标（当前未建模）+ 放置",
        note="#05 的同指令不同场景（KITCHEN_SCENE9，场景内另有白碗与双层架）。与 #05 同时入选才有对照价值，单独入选收益有限。",
    ),
}

REJECTED = {
    17: "`(Turnon flat_stove_1)` 已出现在 `:init` 中，初始即为真，实际只有“把摩卡壶放上炉子”一段有效阶段，不构成两段子任务。",
}

MULTI_ONLY = [58, 59]


def main() -> None:
    suite = DEFAULT_SUITE
    listing = [
        ln.strip() for ln in (suite / "tasks_info.txt").read_text().splitlines() if ln.strip()
    ]
    rows = []
    for i, entry in enumerate(listing):
        name = Path(entry).stem
        tree, _ = parse_sexp(tokenize((suite / f"{name}.bddl").read_text()))
        lang = " ".join(find_block(tree, ":language")[1:])
        atoms = [describe_atom(a) for a in flatten_goal(find_block(tree, ":goal"))]
        init_block = find_block(tree, ":init") or []
        inits = {describe_atom((n[0], tuple(str(a) for a in n[1:]))) for n in init_block[1:]}
        effective = [a for a in atoms if a not in inits]
        rows.append(
            dict(
                index=i,
                scene=scene_of(name),
                lang=lang,
                atoms=atoms,
                effective=effective,
                n_effective=len(effective),
            )
        )

    n_multi = sum(1 for r in rows if len(r["atoms"]) >= 2)
    scenes = sorted({r["scene"] for r in rows})

    out: list[str] = []
    w = out.append
    w("# LIBERO-90 任务清单与 rollback 基础测试集筛选")
    w("")
    w("这是对 LIBERO-90 的静态清点与候选筛选结果，不是数据集版本，也不含任何仿真验证证据。")
    w("")
    w("## 来源与解析口径")
    w("")
    w(
        "- 任务顺序、BDDL 路径取自 `libero-plus` 源码 `libero/libero/bddl_files/libero_90/tasks_info.txt`（90 条，无缺项、无多余项），"
    )
    w("  逐条解析同目录 BDDL 的 `:language`、`:goal`、`:init`。")
    w("- 本文件的任务编号 `00`–`89` 按该清单顺序固定，只在本文件内使用，不是数据集任务 ID。")
    w(
        f"- 90 条任务分布在 {len(scenes)} 个场景；其中 {n_multi} 条的目标是双原子条件，其余 {90 - n_multi} 条为单一目标。"
    )
    w("- 复现：`python3 scripts/analyze_libero90_tasks.py`（只读解析，不运行仿真，不写数据集）。")
    w("")
    w("## 判定规则：什么算“至少两段子任务”")
    w("")
    w("rollback 基础用例要求存在“已完成的前序子任务 s1”和“正在执行的后续子任务 s2”，")
    w("合法性口径见 [`subtask-stages.md`](subtask-stages.md)。因此这里按三条同时成立来判定：")
    w("")
    w("1. BDDL `:goal` 至少有两个原子条件；")
    w("2. 这些原子条件在 `:init` 中都不成立——初始即为真的条件不构成独立执行段；")
    w("3. 两段有固定先后顺序，s2 执行期间 s1 已完成且可被外部撤销。")
    w("")
    w("按此规则，11 条双原子任务中 10 条成立，`17` 因 `Turnon` 已在 `:init` 成立而落选。")
    w("")
    w("分级依据引擎现有机制（`revert_articulation_goal` 等回退效果见")
    w("[`rollback-case.v1.schema.json`](../schemas/rollback-case.v1.schema.json)）：")
    w("")
    w("| 级别 | 含义 |")
    w("| --- | --- |")
    w("| A | s1、s2 都落在已建模机制内（放置关系 On/In、关节回退 Open/Close），可直接构造用例 |")
    w("| B | 机制可用，但 s1 与 s2 共用同一组物体、s2 期间物体在夹爪中，合法干预窗口受限 |")
    w("| C | 含开关类目标（Turnon/Turnoff），当前 runtime profile 未建模，需先补配置 |")
    w("")
    w("pi05 baseline 实测：单 seed（seed 3）见 "
      "[`libero-90-baseline-pi05-seed3.md`](libero-90-baseline-pi05-seed3.md)，"
      "5 种子扫描与失败原因诊断见 "
      "[`libero-90-baseline-seed-sweep.md`](libero-90-baseline-seed-sweep.md)。")
    w("")
    w("## 筛选结果：10 条基础候选")
    w("")
    w("| 序号 | 指令 | s1（已完成，可回滚） | s2（执行中） | 机制 | 级别 | 建议优先级 |")
    w("| --- | --- | --- | --- | --- | --- | --- |")
    order = [26, 27, 28, 0, 25, 9, 40, 41, 5, 19]
    for i in order:
        r = rows[i]
        s = SELECTED[i]
        w(
            f"| `{i:02d}` | {ZH[i]} | {s['s1']} | {s['s2']} | {s['mech']} | {s['tier']} | {s['prio']} |"
        )
    w("")
    w("### 逐条说明")
    w("")
    for i in order:
        r = rows[i]
        s = SELECTED[i]
        w(f"#### `{i:02d}` {ZH[i]}")
        w("")
        w(f"- 英文指令：`{r['lang']}`")
        w(f"- 目标谓词：{' ; '.join(f'`{a}`' for a in r['atoms'])}")
        w(f"- s1：{s['s1']}")
        w(f"- s2：{s['s2']}")
        w(f"- 机制：{s['mech']}")
        w(f"- 级别 / 优先级：{s['tier']} / {s['prio']}")
        w(f"- 说明：{s['note']}")
        w("")
    w("## 落选说明")
    w("")
    w("| 序号 | 指令 | 目标谓词 | 落选原因 |")
    w("| --- | --- | --- | --- |")
    for i in sorted(REJECTED):
        r = rows[i]
        w(f"| `{i:02d}` | {ZH[i]} | {' ; '.join(f'`{a}`' for a in r['atoms'])} | {REJECTED[i]} |")
    for i in MULTI_ONLY:
        r = rows[i]
        w(
            f"| `{i:02d}` | {ZH[i]} | {' ; '.join(f'`{a}`' for a in r['atoms'])} | "
            "目标是单一 `On` 关系（叠放本身），只有一段执行阶段；"
            "`58`/`59` 是镜像对，可作为同一阶段内的物体选择变量，不满足两段要求。 |"
        )
    w("")
    w(
        f"其余 {90 - n_multi} 条任务的目标都是单一原子条件（一个 `On`/`In`/`Open`/`Close`/`Turnon`/`Turnoff`），"
        "只有一段执行阶段。"
    )
    w("说明：其中“把物体放进抽屉/微波炉”一类任务的容器在 `:init` 中已经是打开状态")
    w("（如 `12`/`13`/`29`/`60`/`62`、`68`–`84` 的收纳架格），不存在隐含的“先开容器”阶段；")
    w("“pick up … and put it in …” 的 `pick up` 是达成同一目标的抓取过程，不是独立子任务。")
    w("")
    w("`58` 另有一处来源标注不一致：指令写 “the black bowl at the front”，")
    w("但目标谓词叠到的是 `akita_black_bowl_3`，其初始位姿在 `..._back_init_region`。")
    w("本文件按指令原文翻译；若后续要用这条任务，必须先核对实际目标对象。")
    w("")
    w("单目标任务并非不能做 rollback，但只能在完成边界撤销，")
    w("与“s2 执行中回滚 s1”不是同一类场景，因此不计入本基础测试集。")
    w("")
    w("## 全部 90 条任务描述")
    w("")
    w("“有效阶段数”= `:goal` 中在 `:init` 未成立的原子条件数。")
    w("")
    w("| 序号 | 场景 | 英文指令（`:language`） | 中文 | 目标谓词 | 有效阶段数 | 入选 |")
    w("| --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        i = r["index"]
        goal = " ; ".join(f"`{a}`" for a in r["atoms"])
        picked = "A" if i in SELECTED and SELECTED[i]["tier"] == "A" else ""
        if not picked and i in SELECTED:
            picked = SELECTED[i]["tier"]
        w(
            f"| `{i:02d}` | {r['scene']} | {r['lang']} | {ZH[i]} | {goal} | "
            f"{r['n_effective']} | {picked} |"
        )
    w("")

    OUT.write_text("\n".join(out) + "\n")
    print(f"wrote {OUT}")
    missing = sorted(set(range(90)) - set(ZH))
    if missing:
        raise SystemExit(f"missing translations: {missing}")


if __name__ == "__main__":
    main()
