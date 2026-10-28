# 逐任务 rollback 用例语义清单

> **历史记录（勿按当前 catalog 解读）**：本文记录 逐任务用例清单 的实验，其中的用例总数（312 / 327 / 122 条）与逐条数字均为**当时口径**。2026-10-16 起 `progress-pulse-*`（24 条）已退出数据集（理由见 `archive/pulse-descoped-20261016/README.md`），当前 catalog 为 **288 条**。本文的数字未改写，以保证历史结论可追溯；需要当前口径时以 `docs/case-matrix-current.md` 与 `dataset/current/manifest.yaml` 为准。

更新日期：2026-10-16。本文由 [case-matrix-current.md](case-matrix-current.md)（2026-10-14，327 条定义）逐任务展开，只收录 rollback 相关用例，剔除 progress-failure 来源的 122 条 progress 用例，共 **205 条 rollback 用例**，覆盖任务 00–08；任务 09 的唯一定义是 progress 候选，因此没有 rollback 用例。

## 读取口径

- **收录范围**：`two-subtask` 129 条、`rollback-battery` 57 条、`pose-control` 15 条、`reference-object` 4 条。旧来源不因标签相同而合并，case_id 保持矩阵原样。
- **描述粒度为语义层**：每行只写时机（任务窗口＋原生触发事件，必要时附注入延迟）、目标（被撤销的已完成关系或关节目标）、状态/位置（注入把目标物体放到哪里、或把关节驱动到哪里）、评测语义、补充（未列出的条件默认为“其他不变”，即指令与其它的任务目标保持不变）。带符号位移、悬停净空、倾转角度、搜索精度等数值参数不在此展开，以矩阵与用例定义文件为准。
- **时机**＝任务窗口 early/mid/later/all_done 与它对应的原生里程碑事件；窗口名字面保留英文，冒号后是语义说明。
- **状态/位置的方向口径**：带符号水平位移沿用来源设计口径的一侧命名——负向一侧朝向机械手、正向一侧远离机械手，两族都带同向侧向分量，且都是贴着支撑面的水平移动（当前用例定义把该向量记录为 world 帧）；幅度只用小幅（约 3 厘米级）/中幅（约 5 厘米级）/大幅（约 8 厘米级以上）三档表达。
- **评测语义**：`要求失效→需恢复` 表示注入后目标关系必须为假、由模型负责在后续重新完成；`关系保持对照` 表示预期关系仍为真，属对照项，不进恢复率分母。
- **baseline 视频与首帧**：逐任务取 [validation-current.md](validation-current.md)“当前选择的逐任务证据”所选的 Pi05、600 步、录制视频的无扰动 baseline 运行；任务 03 与 06 为 seed 1，其余为 seed 0。10 条 baseline 全部成功。首帧取该 baseline 视频第 0 帧，即 episode 初始状态。
- **baseline 运行目录名**：选定 baseline 所在的运行目录沿用触发该次预检的用例名，其中数个目录名带 `progress` 字样（例如任务 00/01/02/03/09 的 v12 live 批次与任务 05/08 的 v11 记录）。目录名只标识运行批次来源，不代表本文收录 progress 用例；本文的用例行只来自矩阵中非 progress-failure 来源的 205 条。
- **两份并行记录**：同一扰动常有“显式谓词版”（case_id 含被撤销谓词，来自 two-subtask 集合）与“动态选择器版”（case_id 为 `*-rollback-s1-*`，目标由运行时按实际完成顺序解析，来自 rollback-battery 集合）两份记录，二者不合并。
- **悬停族的两份记录**：`*-rollback-s1-*-above` 使用已验证悬停参数套件，`*-rollback-s1-*-container-above` 是早期参考套件的移植记录，扰动相同、来源不同。
- **pose-control 的 15 条**（任务 01/04/07 各 5 条）在当前 catalog 快照的 manifest 与 coverage（各 312 条）中不存在，只在矩阵行与运行证据中保留；本文按矩阵收录。

## 总览

| 任务 | 任务名 | rollback 用例数 | 机制分布 | baseline seed | baseline 成功步数 |
| --- | --- | ---: | --- | ---: | ---: |
| libero_10/00 | 打开灶台并把摩卡壶放上去 | 3 | 关节回退 3 | 0 | 255 |
| libero_10/01 | 把黑碗放进柜子底抽屉并关上 | 32 | 带符号水平平移 17、初始位姿复位 4、容器上方悬停 6、姿态探针 5 | 0 | 328 |
| libero_10/02 | 把黄白马克杯放进微波炉并关上 | 27 | 带符号水平平移 17、初始位姿复位 4、容器上方悬停 6 | 0 | 231 |
| libero_10/03 | 把两个摩卡壶都放到灶面上 | 23 | 带符号水平平移 19、初始位姿复位 4 | 1 | 409 |
| libero_10/04 | 把字母汤罐头和奶油奶酪盒放进篮子 | 28 | 带符号水平平移 18、初始位姿复位 3、姿态探针 5、参照物移动 1、成对平移对照 1 | 0 | 240 |
| libero_10/05 | 把字母汤罐头和番茄酱放进篮子 | 21 | 带符号水平平移 18、初始位姿复位 3 | 0 | 278 |
| libero_10/06 | 把奶油奶酪盒和黄油放进篮子 | 21 | 带符号水平平移 18、初始位姿复位 3 | 1 | 257 |
| libero_10/07 | 把白杯放到左盘、黄白马克杯放到右盘 | 29 | 带符号水平平移 18、初始位姿复位 4、姿态探针 5、参照物移动 1、成对平移对照 1 | 0 | 241 |
| libero_10/08 | 把白杯放到盘上、巧克力布丁放到盘子右侧 | 21 | 带符号水平平移 18、初始位姿复位 3 | 0 | 272 |
| libero_10/09 | 拿起书并放进收纳架后格 | 0 | — | 0 | 219 |
| **合计** | — | **205** | — | — | — |

## libero_10/00 — Turn on the stove and put the moka pot on it

**打开灶台并把摩卡壶放上去**

- **任务 baseline 视频**：[LIBERO_10_T0__baseline_seed0.mp4](../runs/progress-live-20261014-v12/libero-10-00-progress-both-goals-all-done/pi05_20261014_115103/videos/LIBERO_10_T0__baseline_seed0.mp4)（v12 live 批次基线预检；Pi05 / seed 0 / 600 步预算，255 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/00 初始第一帧](assets/rollback-cases/task-00-baseline-first-frame.png)

- **回滚目标**：灶台开关（Turnon 关节目标）
- **用例数**：3 条 rollback（任务定义共 8 条，其中 progress 5 条不计入）

| 序号 | 用例 ID | 时机 | 目标 | 状态/位置 | 评测语义 | 补充 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `libero-10-00-moka-pot-stove-rollback-s1-s2-early-p1` | early：开始接近下一子目标，延迟 10 步 | 灶台开关（Turnon 关节目标） | 关节回退：把灶台旋钮驱动回关闭（turnoff）一侧，撤销已完成的 Turnon 目标 | 要求失效→需恢复 | 其他不变；以原生 Turnon 谓词翻假为准，不以关节位移量判定 |
| 2 | `libero-10-00-moka-pot-stove-rollback-s1-s2-mid-p1` | mid：开始接近下一子目标 | 灶台开关（Turnon 关节目标） | 关节回退：把灶台旋钮驱动回关闭（turnoff）一侧，撤销已完成的 Turnon 目标 | 要求失效→需恢复 | 其他不变；以原生 Turnon 谓词翻假为准，不以关节位移量判定 |
| 3 | `libero-10-00-moka-pot-stove-rollback-s1-s2-later-p1` | later：下一子目标抬升阶段 | 灶台开关（Turnon 关节目标） | 关节回退：把灶台旋钮驱动回关闭（turnoff）一侧，撤销已完成的 Turnon 目标 | 要求失效→需恢复 | 其他不变；以原生 Turnon 谓词翻假为准，不以关节位移量判定 |

## libero_10/01 — Put the black bowl in the bottom drawer and close it

**把黑碗放进柜子底抽屉并关上**

- **任务 baseline 视频**：[LIBERO_10_T33__baseline_seed0.mp4](../runs/progress-live-20261014-v12/libero-10-01-progress-both-goals-all-done/pi05_20261014_115629/videos/LIBERO_10_T33__baseline_seed0.mp4)（v12 live 批次基线预检；Pi05 / seed 0 / 600 步预算，328 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/01 初始第一帧](assets/rollback-cases/task-01-baseline-first-frame.png)

- **回滚目标**：黑碗在柜子底抽屉内的关系
- **用例数**：32 条 rollback（任务定义共 46 条，其中 progress 14 条不计入）

| 序号 | 用例 ID | 时机 | 目标 | 状态/位置 | 评测语义 | 补充 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `libero-10-01-black-rollback-s1-early-offset-n3` | early：第一子目标刚完成 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 2 | `libero-10-01-black-rollback-s1-early-offset-p3` | early：第一子目标刚完成 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 3 | `libero-10-01-black-rollback-s1-early-offset-n5` | early：第一子目标刚完成 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 4 | `libero-10-01-black-rollback-s1-early-offset-p5` | early：第一子目标刚完成 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 5 | `libero-10-01-black-rollback-s1-early-offset-n8` | early：第一子目标刚完成 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 6 | `libero-10-01-black-rollback-s1-early-offset-p10` | early：第一子目标刚完成 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 7 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-offset-n3` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 8 | `libero-10-01-black-rollback-s1-mid-offset-n3` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 9 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-offset-p3` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 10 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-offset-n5` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 11 | `libero-10-01-black-rollback-s1-mid-offset-n5` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 12 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-offset-p5` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 13 | `libero-10-01-black-rollback-s1-later-offset-n3` | later：第二子目标动作执行阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 14 | `libero-10-01-black-bowl-drawer-rollback-s1-later-offset-n8` | later：第二子目标动作执行阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 15 | `libero-10-01-black-bowl-drawer-rollback-s1-later-offset-p8` | later：第二子目标动作执行阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 16 | `libero-10-01-black-bowl-drawer-rollback-s1-later-offset-p10` | later：第二子目标动作执行阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 17 | `libero-10-01-black-bowl-drawer-rollback-s1-later-offset-r05` | later：第二子目标动作执行阶段 | 黑碗在柜子底抽屉内的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 18 | `libero-10-01-black-bowl-drawer-place-early-t0` | early：第一子目标刚完成 | 黑碗在柜子底抽屉内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；落点须在支撑面上、无碰撞、在工作区内且朝向保持 |
| 19 | `libero-10-01-black-rollback-s1-early-initial-pose` | early：第一子目标刚完成 | 黑碗在柜子底抽屉内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 20 | `libero-10-01-black-rollback-s1-mid-initial-pose` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 21 | `libero-10-01-black-rollback-s1-later-initial-pose` | later：第二子目标动作执行阶段 | 黑碗在柜子底抽屉内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 22 | `libero-10-01-black-bowl-drawer-rollback-s1-early-above` | early：第一子目标刚完成，延迟 10 步 | 黑碗在柜子底抽屉内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；悬停点须落在容器开口正上方 |
| 23 | `libero-10-01-black-rollback-s1-early-container-above` | early：第一子目标刚完成 | 黑碗在柜子底抽屉内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析；悬停点须落在容器开口正上方 |
| 24 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-above` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；悬停点须落在容器开口正上方 |
| 25 | `libero-10-01-black-rollback-s1-mid-container-above` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析；悬停点须落在容器开口正上方 |
| 26 | `libero-10-01-black-bowl-drawer-rollback-s1-later-above` | later：第二子目标动作执行阶段 | 黑碗在柜子底抽屉内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；悬停点须落在容器开口正上方 |
| 27 | `libero-10-01-black-rollback-s1-later-container-above` | later：第二子目标动作执行阶段 | 黑碗在柜子底抽屉内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析；悬停点须落在容器开口正上方 |
| 28 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll15` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 姿态探针：平面位置不变，仅绕水平轴小幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 29 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll30` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 姿态探针：平面位置不变，仅绕水平轴中幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 30 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll45` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 姿态探针：平面位置不变，仅绕水平轴较大幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 31 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll60` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 姿态探针：平面位置不变，仅绕水平轴大幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 32 | `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-spin180` | mid：完成后撤离阶段 | 黑碗在柜子底抽屉内的关系 | 姿态探针：平面位置不变，仅绕竖直轴旋转半圈 | 关系保持对照 | 其他不变；预期保持为真，不进恢复率分母；翻假即说明物体并非关于竖直轴对称 |

## libero_10/02 — Put the yellow and white mug in the microwave and close it

**把黄白马克杯放进微波炉并关上**

- **任务 baseline 视频**：[LIBERO_10_T78__baseline_seed0.mp4](../runs/progress-live-20261014-v12/libero-10-02-progress-both-goals-all-done/pi05_20261014_120315/videos/LIBERO_10_T78__baseline_seed0.mp4)（v12 live 批次基线预检；Pi05 / seed 0 / 600 步预算，231 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/02 初始第一帧](assets/rollback-cases/task-02-baseline-first-frame.png)

- **回滚目标**：黄白马克杯在微波炉加热区内的关系
- **用例数**：27 条 rollback（任务定义共 41 条，其中 progress 14 条不计入）

| 序号 | 用例 ID | 时机 | 目标 | 状态/位置 | 评测语义 | 补充 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `libero-10-02-yellow-rollback-s1-early-offset-n3` | early：第一子目标刚完成 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 2 | `libero-10-02-yellow-rollback-s1-early-offset-p3` | early：第一子目标刚完成 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 3 | `libero-10-02-yellow-rollback-s1-early-offset-n5` | early：第一子目标刚完成 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 4 | `libero-10-02-yellow-rollback-s1-early-offset-n8` | early：第一子目标刚完成 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 5 | `libero-10-02-yellow-rollback-s1-early-offset-p8` | early：第一子目标刚完成 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 6 | `libero-10-02-yellow-rollback-s1-early-offset-p10` | early：第一子目标刚完成 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 7 | `libero-10-02-yellow-rollback-s1-mid-offset-n3` | mid：完成后撤离阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 8 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-mid-offset-n3` | mid：完成后撤离阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 9 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-mid-offset-p3` | mid：完成后撤离阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 10 | `libero-10-02-yellow-rollback-s1-mid-offset-n5` | mid：完成后撤离阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 11 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-mid-offset-n5` | mid：完成后撤离阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 12 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-mid-offset-p5` | mid：完成后撤离阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 13 | `libero-10-02-yellow-rollback-s1-later-offset-n3` | later：第二子目标动作执行阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 14 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-later-offset-n8` | later：第二子目标动作执行阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 15 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-later-offset-p8` | later：第二子目标动作执行阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 16 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-later-offset-p10` | later：第二子目标动作执行阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 17 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-later-offset-r05` | later：第二子目标动作执行阶段 | 黄白马克杯在微波炉加热区内的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 18 | `libero-10-02-yellow-rollback-s1-early-initial-pose` | early：第一子目标刚完成 | 黄白马克杯在微波炉加热区内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 19 | `libero-10-02-yellow-white-mug-microwave-place-early-t0` | early：第一子目标刚完成 | 黄白马克杯在微波炉加热区内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；落点须在支撑面上、无碰撞、在工作区内且朝向保持 |
| 20 | `libero-10-02-yellow-rollback-s1-mid-initial-pose` | mid：完成后撤离阶段 | 黄白马克杯在微波炉加热区内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 21 | `libero-10-02-yellow-rollback-s1-later-initial-pose` | later：第二子目标动作执行阶段 | 黄白马克杯在微波炉加热区内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 22 | `libero-10-02-yellow-rollback-s1-early-container-above` | early：第一子目标刚完成 | 黄白马克杯在微波炉加热区内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析；悬停点须落在容器开口正上方 |
| 23 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-early-above` | early：第一子目标刚完成，延迟 10 步 | 黄白马克杯在微波炉加热区内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；悬停点须落在容器开口正上方 |
| 24 | `libero-10-02-yellow-rollback-s1-mid-container-above` | mid：完成后撤离阶段 | 黄白马克杯在微波炉加热区内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析；悬停点须落在容器开口正上方 |
| 25 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-mid-above` | mid：完成后撤离阶段 | 黄白马克杯在微波炉加热区内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；悬停点须落在容器开口正上方 |
| 26 | `libero-10-02-yellow-rollback-s1-later-container-above` | later：第二子目标动作执行阶段 | 黄白马克杯在微波炉加热区内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析；悬停点须落在容器开口正上方 |
| 27 | `libero-10-02-yellow-white-mug-microwave-rollback-s1-later-above` | later：第二子目标动作执行阶段 | 黄白马克杯在微波炉加热区内的关系 | 容器上方悬停：抬到容器开口正上方悬停，不进入容器内部 | 要求失效→需恢复 | 其他不变；悬停点须落在容器开口正上方 |

## libero_10/03 — Put both moka pots on the stove

**把两个摩卡壶都放到灶面上**

- **任务 baseline 视频**：[LIBERO_10_T133__baseline_seed1.mp4](../runs/progress-live-20261014-v12/libero-10-03-progress-both-goals-all-done/pi05_20261014_120913/videos/LIBERO_10_T133__baseline_seed1.mp4)（v12 live 批次基线预检；Pi05 / seed 1 / 600 步预算，409 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/03 初始第一帧](assets/rollback-cases/task-03-baseline-first-frame.png)

- **回滚目标**：第一个摩卡壶落在灶面区域的关系
- **用例数**：23 条 rollback（任务定义共 36 条，其中 progress 13 条不计入）

| 序号 | 用例 ID | 时机 | 目标 | 状态/位置 | 评测语义 | 补充 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `libero-10-03-first-rollback-s1-early-offset-n3` | early：第一子目标刚完成 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 2 | `libero-10-03-first-rollback-s1-early-offset-p3` | early：第一子目标刚完成 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 3 | `libero-10-03-first-rollback-s1-early-offset-n5` | early：第一子目标刚完成 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 4 | `libero-10-03-first-rollback-s1-early-offset-p5` | early：第一子目标刚完成 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 5 | `libero-10-03-first-rollback-s1-early-offset-n8` | early：第一子目标刚完成 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 6 | `libero-10-03-first-rollback-s1-early-offset-p10` | early：第一子目标刚完成 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 7 | `libero-10-03-first-rollback-s1-early-offset-r05` | early：第一子目标刚完成 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 8 | `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-n3` | mid：开始接近下一子目标 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 9 | `libero-10-03-first-rollback-s1-mid-offset-n3` | mid：开始接近下一子目标 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 10 | `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-p3` | mid：开始接近下一子目标 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 11 | `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-n5` | mid：开始接近下一子目标 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 12 | `libero-10-03-first-rollback-s1-mid-offset-n5` | mid：开始接近下一子目标 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 13 | `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-p5` | mid：开始接近下一子目标 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 14 | `libero-10-03-first-rollback-s1-later-offset-n3` | later：下一子目标抬升阶段 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 15 | `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-n8` | later：下一子目标抬升阶段 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 16 | `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-p8` | later：下一子目标抬升阶段 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 17 | `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-p10` | later：下一子目标抬升阶段 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 18 | `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-r05` | later：下一子目标抬升阶段 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 19 | `libero-10-03-first-rollback-s1-all_done-offset-n3` | all_done：全部子目标完成后 | 第一个摩卡壶落在灶面区域的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 20 | `libero-10-03-first-moka-pot-stove-place-early-t0` | early：第一子目标刚完成 | 第一个摩卡壶落在灶面区域的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；落点须在支撑面上、无碰撞、在工作区内且朝向保持 |
| 21 | `libero-10-03-first-rollback-s1-early-initial-pose` | early：第一子目标刚完成 | 第一个摩卡壶落在灶面区域的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 22 | `libero-10-03-first-rollback-s1-mid-initial-pose` | mid：开始接近下一子目标 | 第一个摩卡壶落在灶面区域的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 23 | `libero-10-03-first-rollback-s1-later-initial-pose` | later：下一子目标抬升阶段 | 第一个摩卡壶落在灶面区域的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |

## libero_10/04 — Put the alphabet soup and cream cheese box in the basket

**把字母汤罐头和奶油奶酪盒放进篮子**

- **任务 baseline 视频**：[LIBERO_10_T137__baseline_seed0.mp4](../runs/catalog-native-preflight-20261014-v12/libero-10-04-soup-cheese-basket-rollback-s1-mid-ref-moved/pi05_20261014_122059/videos/LIBERO_10_T137__baseline_seed0.mp4)（v12 补充基线；Pi05 / seed 0 / 600 步预算，240 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/04 初始第一帧](assets/rollback-cases/task-04-baseline-first-frame.png)

- **回滚目标**：汤罐头在篮子内的关系
- **用例数**：28 条 rollback（任务定义共 42 条，其中 progress 14 条不计入）

| 序号 | 用例 ID | 时机 | 目标 | 状态/位置 | 评测语义 | 补充 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `libero-10-04-soup-cheese-basket-rollback-s1-early-p2` | early：第一子目标刚完成，延迟 10 步 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 2 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-offset-n3` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 3 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-p2` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 4 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-offset-p3` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 5 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-offset-n5` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 6 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-offset-p5` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 7 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-offset-n8` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 8 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-offset-p8` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 9 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-offset-p10` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 10 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-offset-r05` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 11 | `libero-10-04-soup-cheese-basket-rollback-s1-later-p2` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 12 | `libero-10-04-soup-cheese-basket-rollback-s1-later-offset-p3` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 13 | `libero-10-04-soup-cheese-basket-rollback-s1-later-offset-n5` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 14 | `libero-10-04-soup-cheese-basket-rollback-s1-later-offset-p5` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 15 | `libero-10-04-soup-cheese-basket-rollback-s1-later-offset-n8` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 16 | `libero-10-04-soup-cheese-basket-rollback-s1-later-offset-p8` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 17 | `libero-10-04-soup-cheese-basket-rollback-s1-later-offset-p10` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 18 | `libero-10-04-soup-cheese-basket-rollback-s1-later-offset-r05` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 19 | `libero-10-04-soup-cheese-basket-rollback-s1-early-p1` | early：第一子目标刚完成，延迟 10 步 | 汤罐头在篮子内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |
| 20 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-p1` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |
| 21 | `libero-10-04-soup-cheese-basket-rollback-s1-later-p1` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |
| 22 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-pose-roll15` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 姿态探针：平面位置不变，仅绕水平轴小幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 23 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-pose-roll30` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 姿态探针：平面位置不变，仅绕水平轴中幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 24 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-pose-roll45` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 姿态探针：平面位置不变，仅绕水平轴较大幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 25 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-pose-roll60` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 姿态探针：平面位置不变，仅绕水平轴大幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 26 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-pose-spin180` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 姿态探针：平面位置不变，仅绕竖直轴旋转半圈 | 关系保持对照 | 其他不变；预期保持为真，不进恢复率分母；翻假即说明物体并非关于竖直轴对称 |
| 27 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-ref-moved` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 参照物移动：只把可移动参照物（低矮篮筐）移开，被撤销物体保持原位不动 | 要求失效→需恢复 | 其他不变；参照物须为非固定物体，且移动不得扰动当前正在处理的对象 |
| 28 | `libero-10-04-soup-cheese-basket-rollback-s1-mid-pair-moved` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 成对平移对照：被撤销物体与参照物一起平移同一向量，两者相对关系不变 | 关系保持对照 | 其他不变；关系应保持，不进恢复率分母 |

## libero_10/05 — Put the alphabet soup and tomato sauce in the basket

**把字母汤罐头和番茄酱放进篮子**

- **任务 baseline 视频**：[LIBERO_10_T145__baseline_seed0.mp4](../runs/catalog-native-preflight-20261014-v11/libero-10-05-progress-both-goals-all-done/pi05_20261014_113757/videos/LIBERO_10_T145__baseline_seed0.mp4)（v11 基线预检（保留）；Pi05 / seed 0 / 600 步预算，278 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/05 初始第一帧](assets/rollback-cases/task-05-baseline-first-frame.png)

- **回滚目标**：汤罐头在篮子内的关系
- **用例数**：21 条 rollback（任务定义共 37 条，其中 progress 16 条不计入）

| 序号 | 用例 ID | 时机 | 目标 | 状态/位置 | 评测语义 | 补充 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `libero-10-05-soup-sauce-basket-rollback-s1-early-p2` | early：第一子目标刚完成，延迟 10 步 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 2 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-n3` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 3 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-p2` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 4 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-p3` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 5 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-n5` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 6 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-p5` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 7 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-n8` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 8 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-p8` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 9 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-p10` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 10 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-r05` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 11 | `libero-10-05-soup-sauce-basket-rollback-s1-later-p2` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 12 | `libero-10-05-soup-sauce-basket-rollback-s1-later-offset-p3` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 13 | `libero-10-05-soup-sauce-basket-rollback-s1-later-offset-n5` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 14 | `libero-10-05-soup-sauce-basket-rollback-s1-later-offset-p5` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 15 | `libero-10-05-soup-sauce-basket-rollback-s1-later-offset-n8` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 16 | `libero-10-05-soup-sauce-basket-rollback-s1-later-offset-p8` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 17 | `libero-10-05-soup-sauce-basket-rollback-s1-later-offset-p10` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 18 | `libero-10-05-soup-sauce-basket-rollback-s1-later-offset-r05` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 19 | `libero-10-05-soup-sauce-basket-rollback-s1-early-p1` | early：第一子目标刚完成，延迟 10 步 | 汤罐头在篮子内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |
| 20 | `libero-10-05-soup-sauce-basket-rollback-s1-mid-p1` | mid：开始接近下一子目标 | 汤罐头在篮子内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |
| 21 | `libero-10-05-soup-sauce-basket-rollback-s1-later-p1` | later：下一子目标抬升阶段 | 汤罐头在篮子内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |

## libero_10/06 — Put the cream cheese box and butter in the basket

**把奶油奶酪盒和黄油放进篮子**

- **任务 baseline 视频**：[LIBERO_10_T158__baseline_seed1.mp4](../runs/catalog-native-preflight-20261014-v12/libero-10-06-progress-both-goals-all-done/pi05_20261014_122259/videos/LIBERO_10_T158__baseline_seed1.mp4)（v12 补充基线；Pi05 / seed 1 / 600 步预算，257 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/06 初始第一帧](assets/rollback-cases/task-06-baseline-first-frame.png)

- **回滚目标**：奶油奶酪盒在篮子内的关系
- **用例数**：21 条 rollback（任务定义共 37 条，其中 progress 16 条不计入）

| 序号 | 用例 ID | 时机 | 目标 | 状态/位置 | 评测语义 | 补充 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `libero-10-06-cheese-butter-basket-rollback-s1-early-p2` | early：第一子目标刚完成，延迟 10 步 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 2 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-n3` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 3 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-p2` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 4 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-p3` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 5 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-n5` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 6 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-p5` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 7 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-n8` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 8 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-p8` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 9 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-p10` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 10 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-r05` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 11 | `libero-10-06-cheese-butter-basket-rollback-s1-later-p2` | later：下一子目标抬升阶段 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 12 | `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-p3` | later：下一子目标抬升阶段 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 13 | `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-n5` | later：下一子目标抬升阶段 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 14 | `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-p5` | later：下一子目标抬升阶段 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 15 | `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-n8` | later：下一子目标抬升阶段 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 16 | `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-p8` | later：下一子目标抬升阶段 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 17 | `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-p10` | later：下一子目标抬升阶段 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 18 | `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-r05` | later：下一子目标抬升阶段 | 奶油奶酪盒在篮子内的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 19 | `libero-10-06-cheese-butter-basket-rollback-s1-early-p1` | early：第一子目标刚完成，延迟 10 步 | 奶油奶酪盒在篮子内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |
| 20 | `libero-10-06-cheese-butter-basket-rollback-s1-mid-p1` | mid：开始接近下一子目标 | 奶油奶酪盒在篮子内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |
| 21 | `libero-10-06-cheese-butter-basket-rollback-s1-later-p1` | later：下一子目标抬升阶段 | 奶油奶酪盒在篮子内的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |

## libero_10/07 — Put the white mug on the left plate and the yellow and white mug on the right plate

**把白杯放到左盘、黄白马克杯放到右盘**

- **任务 baseline 视频**：[LIBERO_10_T193__baseline_seed0.mp4](../runs/catalog-native-preflight-20261014-v12/libero-10-07-white-mug-left-plate-rollback-s1-mid-ref-moved/pi05_20261014_122518/videos/LIBERO_10_T193__baseline_seed0.mp4)（v12 补充基线；Pi05 / seed 0 / 600 步预算，241 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/07 初始第一帧](assets/rollback-cases/task-07-baseline-first-frame.png)

- **回滚目标**：白杯在左盘上的关系
- **用例数**：29 条 rollback（任务定义共 42 条，其中 progress 13 条不计入）

| 序号 | 用例 ID | 时机 | 目标 | 状态/位置 | 评测语义 | 补充 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `libero-10-07-white-rollback-s1-early-offset-n3` | early：第一子目标刚完成 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 2 | `libero-10-07-white-rollback-s1-early-offset-p3` | early：第一子目标刚完成 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 3 | `libero-10-07-white-rollback-s1-early-offset-n5` | early：第一子目标刚完成 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 4 | `libero-10-07-white-rollback-s1-early-offset-p5` | early：第一子目标刚完成 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 5 | `libero-10-07-white-rollback-s1-early-offset-n8` | early：第一子目标刚完成 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 6 | `libero-10-07-white-rollback-s1-early-offset-p10` | early：第一子目标刚完成 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 7 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-offset-n3` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 8 | `libero-10-07-white-rollback-s1-mid-offset-n3` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 9 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-offset-p3` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 10 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-offset-n5` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 11 | `libero-10-07-white-rollback-s1-mid-offset-n5` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 12 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-offset-p5` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 13 | `libero-10-07-white-rollback-s1-later-offset-n3` | later：下一子目标抬升阶段 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 14 | `libero-10-07-white-mug-left-plate-rollback-s1-later-offset-n8` | later：下一子目标抬升阶段 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 15 | `libero-10-07-white-mug-left-plate-rollback-s1-later-offset-p8` | later：下一子目标抬升阶段 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 16 | `libero-10-07-white-mug-left-plate-rollback-s1-later-offset-p10` | later：下一子目标抬升阶段 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 17 | `libero-10-07-white-mug-left-plate-rollback-s1-later-offset-r05` | later：下一子目标抬升阶段 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 18 | `libero-10-07-white-rollback-s1-all_done-offset-n3` | all_done：全部子目标完成后 | 白杯在左盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 19 | `libero-10-07-white-mug-left-plate-place-early-t0` | early：第一子目标刚完成 | 白杯在左盘上的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；落点须在支撑面上、无碰撞、在工作区内且朝向保持 |
| 20 | `libero-10-07-white-rollback-s1-early-initial-pose` | early：第一子目标刚完成 | 白杯在左盘上的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 21 | `libero-10-07-white-rollback-s1-mid-initial-pose` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 22 | `libero-10-07-white-rollback-s1-later-initial-pose` | later：下一子目标抬升阶段 | 白杯在左盘上的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变；目标按实际执行顺序解析 |
| 23 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll15` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 姿态探针：平面位置不变，仅绕水平轴小幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 24 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll30` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 姿态探针：平面位置不变，仅绕水平轴中幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 25 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll45` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 姿态探针：平面位置不变，仅绕水平轴较大幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 26 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll60` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 姿态探针：平面位置不变，仅绕水平轴大幅倾转 | 要求失效→需恢复 | 其他不变；只读注入前后原生真值判定，倾转角度本身不构成失效证明 |
| 27 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-spin180` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 姿态探针：平面位置不变，仅绕竖直轴旋转半圈 | 关系保持对照 | 其他不变；预期保持为真，不进恢复率分母；翻假即说明物体并非关于竖直轴对称 |
| 28 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-ref-moved` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 参照物移动：只把可移动参照物（平面盘）移开，被撤销物体保持原位不动 | 要求失效→需恢复 | 其他不变；参照物须为非固定物体，且移动不得扰动当前正在处理的对象 |
| 29 | `libero-10-07-white-mug-left-plate-rollback-s1-mid-pair-moved` | mid：开始接近下一子目标 | 白杯在左盘上的关系 | 成对平移对照：被撤销物体与参照物一起平移同一向量，两者相对关系不变 | 关系保持对照 | 其他不变；关系应保持，不进恢复率分母 |

## libero_10/08 — Put the white mug on the plate and the chocolate pudding to the right of the plate

**把白杯放到盘上、巧克力布丁放到盘子右侧**

- **任务 baseline 视频**：[LIBERO_10_T237__baseline_seed0.mp4](../runs/catalog-native-preflight-20261014-v11/libero-10-08-progress-both-goals-all-done/pi05_20261014_114506/videos/LIBERO_10_T237__baseline_seed0.mp4)（v11 基线预检（保留）；Pi05 / seed 0 / 600 步预算，272 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/08 初始第一帧](assets/rollback-cases/task-08-baseline-first-frame.png)

- **回滚目标**：白杯在盘上的关系
- **用例数**：21 条 rollback（任务定义共 37 条，其中 progress 16 条不计入）

| 序号 | 用例 ID | 时机 | 目标 | 状态/位置 | 评测语义 | 补充 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `libero-10-08-mug-pudding-placement-rollback-s1-early-p2` | early：第一子目标刚完成，延迟 10 步 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 2 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-offset-n3` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 3 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-p2` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 4 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-offset-p3` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 5 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-offset-n5` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 6 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-offset-p5` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 7 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-offset-n8` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 8 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-offset-p8` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 9 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-offset-p10` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 10 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-offset-r05` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 11 | `libero-10-08-mug-pudding-placement-rollback-s1-later-p2` | later：下一子目标抬升阶段 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 12 | `libero-10-08-mug-pudding-placement-rollback-s1-later-offset-p3` | later：下一子目标抬升阶段 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向小幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 13 | `libero-10-08-mug-pudding-placement-rollback-s1-later-offset-n5` | later：下一子目标抬升阶段 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 14 | `libero-10-08-mug-pudding-placement-rollback-s1-later-offset-p5` | later：下一子目标抬升阶段 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向中幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 15 | `libero-10-08-mug-pudding-placement-rollback-s1-later-offset-n8` | later：下一子目标抬升阶段 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上朝机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 16 | `libero-10-08-mug-pudding-placement-rollback-s1-later-offset-p8` | later：下一子目标抬升阶段 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 17 | `libero-10-08-mug-pudding-placement-rollback-s1-later-offset-p10` | later：下一子目标抬升阶段 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上远离机械手方向大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 18 | `libero-10-08-mug-pudding-placement-rollback-s1-later-offset-r05` | later：下一子目标抬升阶段 | 白杯在盘上的关系 | 带符号水平平移：在初始落点基础上斜向（朝机械手方向、侧偏最大）大幅平移，贴支撑面、朝向不变 | 要求失效→需恢复 | 其他不变 |
| 19 | `libero-10-08-mug-pudding-placement-rollback-s1-early-p1` | early：第一子目标刚完成，延迟 10 步 | 白杯在盘上的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |
| 20 | `libero-10-08-mug-pudding-placement-rollback-s1-mid-p1` | mid：开始接近下一子目标 | 白杯在盘上的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |
| 21 | `libero-10-08-mug-pudding-placement-rollback-s1-later-p1` | later：下一子目标抬升阶段 | 白杯在盘上的关系 | 初始位姿复位：回到该物体在本回合的初始落点与初始朝向 | 要求失效→需恢复 | 其他不变 |

## libero_10/09 — Pick up the book and place it in the back compartment of the caddy

**拿起书并放进收纳架后格**

- **任务 baseline 视频**：[LIBERO_10_T276__baseline_seed0.mp4](../runs/progress-live-20261014-v12/libero-10-09-progress-initial-pose-all-done/pi05_20261014_121534/videos/LIBERO_10_T276__baseline_seed0.mp4)（v12 live 批次基线预检；Pi05 / seed 0 / 600 步预算，219 步成功）
- **初始第一帧**（episode 初始状态，取自该 baseline 视频）

![libero_10/09 初始第一帧](assets/rollback-cases/task-09-baseline-first-frame.png)

- **回滚目标**：唯一原生目标（书在收纳架后格）
- **用例数**：0 条 rollback（任务定义共 1 条，其唯一定义 `libero-10-09-progress-initial-pose-all-done` 来源为 progress-failure 候选，按本次口径不计入）

该任务只有一个原生目标，矩阵没有为它构造双关系（放置＋关节／两个放置）用例，因此本轮 rollback 清单中它为空；baseline 与首帧仍然列出，供与任务 00–08 的初始场景对照。

## 与矩阵的对账

- 矩阵 327 条 = rollback 205 条 ＋ progress 122 条；逐任务 rollback 数：00 3、01 32、02 27、03 23、04 28、05 21、06 21、07 29、08 21。
- 205 条中有 190 条可在当前 catalog（`dataset/current/manifest.yaml` 与 `coverage.yaml`，各 312 条）找到定义文件；其余 15 条为 pose-control 1.7.0（`matrix-p2-pose-20261013`），当前快照未收录其定义，只有矩阵行与 `runs/pose-control-pi05`、`runs/final-report` 的运行证据。
- 矩阵把 15 条 pose-control 计入 327，manifest 的 `case_count` 为 312；两者差异即上述 15 条，本文按矩阵收录并在各任务表中单列。

