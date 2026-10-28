# 标准 LIBERO 40 任务与官方评测协议 —— 独立只读审计

- 审计角色：Team 审计员（独立核查，不复用其它成员的结论）
- 工作目录：`/home/tarowang/workspace/roboot/libero-rollback`
- 审计时间：2026-10-19（Asia/Singapore）
- 权威产物：同目录 [`spec.json`](spec.json)（机读 spec） + [`verify_std_libero.py`](verify_std_libero.py)（可复现审计脚本）
- 约束遵守：全程 **CPU-only、只读**；未加载 pi05/任何 model、未创建/未 reset/未 step 任何仿真 env、未占 GPU、未改 `~/.libero/config.yaml`、未改 `libero-plus`/`libero-rollback` 既有文件、未写 `runs/libero-std-baseline-20261019/`。所有临时文件在 `/tmp`，唯一写入区域是本目录。

---

## 0. 结论摘要（TL;DR）

1. **标准 4 套件各 10 个 base 任务、共 40 个任务全部齐备且可载入**：`n_tasks=10`（不是本机已安装 LIBERO-Plus 的 2402/2518/2591/2519），任务名与顺序来自上游 LIBERO 原版 task map；40/40 个 BDDL 文件存在且可被本机 `bddl` 库解析；40/40 个 `.pruned_init` 存在，**每个任务恰好 50 条初始状态**。
2. **标准 10 任务 benchmark 只存在于 `third_party/libero` 的 git HEAD 中**；live 文件已被 LIBERO-Plus 改写（`git status` 13 个 tracked 文件被修改，另有约 800 个 untracked 条目；活树，审计期间 792→795，见 R11）。原版代码可由 **`git show HEAD:<path>` 无损恢复**（8 个代码 `.bak` 与 HEAD 逐字节相同），**不需要、也不应修改 live 文件**。
3. **Shadow 包方案可行（已实测两种）**：
   - `shadow_full`：56 个 `.py` 全部取自 git HEAD → 原版 benchmark + 原版 env，import 成功；
   - `shadow_hybrid`：原版 benchmark（4 个文件）+ 已安装 LIBERO-Plus 的 `envs/utils/assets/*` 软链 → benchmark 与原版逐任务一致、env import 成功。**推荐 hybrid**：改动面最小，且现有 runtime 本来就是“包装原版 LIBERO BDDLBaseDomain”写的。
4. **评测协议以 openpi `examples/libero/main.py` 为准**：`max_steps = 220/280/300/520`（spatial/object/goal/libero_10）、`num_trials_per_task=50`、`num_steps_wait=10`、`replan_steps=5`、`seed=7`。其中 50 trials 正好等于每任务 50 条 init states → 每个初始状态跑 1 次。
5. **两个必须先处理的坑**：
   - 任何 harness 若不加 shadow，`get_benchmark("LIBERO_SPATIAL")()` 拿到的是 **2402** 个扰动任务而不是 10 个；
   - 原版 `get_task_init_states()` 在 torch 2.7.1 下会因 `weights_only=True` 抛 `UnpicklingError`。现有 runtime 已在 `libero-runtime/tools/run_benchmark.py:50-51` 全局 patch；自建 harness 必须同样 patch（或显式 `torch.load(..., weights_only=False)`）。
6. **资产有“同源但非同一”的风险**：LIBERO-Plus 资产树里的 40 个 base BDDL + 40 个 `.pruned_init` 与官方**逐字节相同**（80/80 sha256 一致），但**29 个纹理被降采样/重编码（原 225–2400px → 512×512）**、13 个 scene XML 增补了额外相机、缺 `textures/cream-plaster.png`。**标准 baseline 建议用临时 `LIBERO_CONFIG_PATH` 指向 third_party 原版资产**，不要直接用默认的 LIBERO-Plus 资产渲染。

---

## 1. 权威数字

| 套件（benchmark 类） | suite 目录 | n_tasks | max_steps | 每任务 init 数 | init_state 形状 |
|---|---|---:|---:|---:|---|
| `LIBERO_SPATIAL` | `libero_spatial` | **10** | **220** | 50 | `(50, 92)`（10 条全部相同） |
| `LIBERO_OBJECT` | `libero_object` | **10** | **280** | 50 | `(50, 110)`（10 条全部相同） |
| `LIBERO_GOAL` | `libero_goal` | **10** | **300** | 50 | `(50, 79)`（10 条全部相同） |
| `LIBERO_10` | `libero_10` | **10** | **520** | 50 | **随任务不同**：`(50,45)/(50,47)/(50,51)/(50,71)/(50,84)/(50,123)` |
| **合计** | | **40** | | **2000 条** | 不要硬编码 shape |

- 每个任务语言指令 = benchmark `get_task(i).language`；spatial/object/goal 为下划线任务名转空格，libero_10 为去掉 `SCENE` 前缀后的自然语言句。
- 任务顺序：`task_order_index=0` 时，原版 benchmark 使用 `task_orders[0] = [0,1,2,3,4,5,6,7,8,9]`（恒等置换），因此 **idx 0–9 就是 task map 文件中的书写顺序**（见 §2、§3）。
- 全量清单（idx / name / language / bddl / init 路径 / shape）见 `spec.json` 的 `suites`；下文 §3 亦列出 40 条。

## 2. 来源可信度（原版到底是不是干净原版？）

`third_party/libero` 是 openpi 的 git submodule：

- `.git` 指针：`gitdir: ../../.git/modules/third_party/libero`
- `HEAD = f78abd6 2023-12-24 "fixed the venv issue"`，`origin = https://github.com/Lifelong-Robot-Learning/LIBERO.git`（上游 LIBERO 官方仓库）
- `git status`：**13 个 tracked 文件被 LIBERO-Plus 修改**（未提交），另有约 800 个 untracked 条目（LIBERO-Plus 新增资产/备份；审计期间从 792 增至 795，说明该树正被并发进程触碰，见 R11）
- 修改文件里 8 个带 `.bak`：`benchmark/__init__.py`、`benchmark/libero_suite_task_map.py`、6 个 `envs/problems/libero_*.py`。**这 8 个 `.bak` 与 `git show HEAD:<同名文件>` 逐字节相同（实测 sha256 全等）** → `.bak` 就是干净原版备份；而全部原版代码都可由 git HEAD 恢复（不依赖 `.bak`，也不改 live 文件）。
- `git diff --numstat` 证明 LIBERO-Plus 的 env 改动基本是**纯新增**（见附录 A）：例如 `benchmark/__init__.py` +130/−43、`env_wrapper.py` +275/−3、6 个 problems 文件每个 +2 万~3.3 万行但只删 2~6 行、`style.py` +286/−0、`regions/__init__.py` +8746/−0。被删的 `env_wrapper` 3 行是 `step/reset` 的原始实现，被替换成带 `noise != 0` 分支的版本；无扰动（noise=0）时行为等同原实现。相机在 `view=0` 时走原坐标，但坐标被 **round 到 4 位小数**（量级 <1e-3 度，可忽略）。
- 结论：**`.bak`/git HEAD 是可信干净原版**；但 third_party 工作树本身不是“干净 checkout”（含 LIBERO-Plus 未跟踪残留），不要对它做 `git checkout/clean`。

## 3. 逐套件 40 个 base 任务清单

> `language` 即 openpi 评测里传给策略的 prompt（`task.language`）；路径均为绝对路径，完整值见 `spec.json`。

### 3.1 LIBERO_SPATIAL（max_steps=220）

| idx | task name | language | init_shape |
|---:|---|---|---|
| 0 | `pick_up_the_black_bowl_between_the_plate_and_the_ramekin_and_place_it_on_the_plate` | pick up the black bowl between the plate and the ramekin and place it on the plate | (50,92) |
| 1 | `pick_up_the_black_bowl_next_to_the_ramekin_and_place_it_on_the_plate` | pick up the black bowl next to the ramekin and place it on the plate | (50,92) |
| 2 | `pick_up_the_black_bowl_from_table_center_and_place_it_on_the_plate` | pick up the black bowl from table center and place it on the plate | (50,92) |
| 3 | `pick_up_the_black_bowl_on_the_cookie_box_and_place_it_on_the_plate` | pick up the black bowl on the cookie box and place it on the plate | (50,92) |
| 4 | `pick_up_the_black_bowl_in_the_top_drawer_of_the_wooden_cabinet_and_place_it_on_the_plate` | pick up the black bowl in the top drawer of the wooden cabinet and place it on the plate | (50,92) |
| 5 | `pick_up_the_black_bowl_on_the_ramekin_and_place_it_on_the_plate` | pick up the black bowl on the ramekin and place it on the plate | (50,92) |
| 6 | `pick_up_the_black_bowl_next_to_the_cookie_box_and_place_it_on_the_plate` | pick up the black bowl next to the cookie box and place it on the plate | (50,92) |
| 7 | `pick_up_the_black_bowl_on_the_stove_and_place_it_on_the_plate` | pick up the black bowl on the stove and place it on the plate | (50,92) |
| 8 | `pick_up_the_black_bowl_next_to_the_plate_and_place_it_on_the_plate` | pick up the black bowl next to the plate and place it on the plate | (50,92) |
| 9 | `pick_up_the_black_bowl_on_the_wooden_cabinet_and_place_it_on_the_plate` | pick up the black bowl on the wooden cabinet and place it on the plate | (50,92) |

### 3.2 LIBERO_OBJECT（max_steps=280）

| idx | task name | language | init_shape |
|---:|---|---|---|
| 0 | `pick_up_the_alphabet_soup_and_place_it_in_the_basket` | pick up the alphabet soup and place it in the basket | (50,110) |
| 1 | `pick_up_the_cream_cheese_and_place_it_in_the_basket` | pick up the cream cheese and place it in the basket | (50,110) |
| 2 | `pick_up_the_salad_dressing_and_place_it_in_the_basket` | pick up the salad dressing and place it in the basket | (50,110) |
| 3 | `pick_up_the_bbq_sauce_and_place_it_in_the_basket` | pick up the bbq sauce and place it in the basket | (50,110) |
| 4 | `pick_up_the_ketchup_and_place_it_in_the_basket` | pick up the ketchup and place it in the basket | (50,110) |
| 5 | `pick_up_the_tomato_sauce_and_place_it_in_the_basket` | pick up the tomato sauce and place it in the basket | (50,110) |
| 6 | `pick_up_the_butter_and_place_it_in_the_basket` | pick up the butter and place it in the basket | (50,110) |
| 7 | `pick_up_the_milk_and_place_it_in_the_basket` | pick up the milk and place it in the basket | (50,110) |
| 8 | `pick_up_the_chocolate_pudding_and_place_it_in_the_basket` | pick up the chocolate pudding and place it in the basket | (50,110) |
| 9 | `pick_up_the_orange_juice_and_place_it_in_the_basket` | pick up the orange juice and place it in the basket | (50,110) |

### 3.3 LIBERO_GOAL（max_steps=300）

| idx | task name | language | init_shape |
|---:|---|---|---|
| 0 | `open_the_middle_drawer_of_the_cabinet` | open the middle drawer of the cabinet | (50,79) |
| 1 | `put_the_bowl_on_the_stove` | put the bowl on the stove | (50,79) |
| 2 | `put_the_wine_bottle_on_top_of_the_cabinet` | put the wine bottle on top of the cabinet | (50,79) |
| 3 | `open_the_top_drawer_and_put_the_bowl_inside` | open the top drawer and put the bowl inside | (50,79) |
| 4 | `put_the_bowl_on_top_of_the_cabinet` | put the bowl on top of the cabinet | (50,79) |
| 5 | `push_the_plate_to_the_front_of_the_stove` | push the plate to the front of the stove | (50,79) |
| 6 | `put_the_cream_cheese_in_the_bowl` | put the cream cheese in the bowl | (50,79) |
| 7 | `turn_on_the_stove` | turn on the stove | (50,79) |
| 8 | `put_the_bowl_on_the_plate` | put the bowl on the plate | (50,79) |
| 9 | `put_the_wine_bottle_on_the_rack` | put the wine bottle on the rack | (50,79) |

### 3.4 LIBERO_10（max_steps=520）

| idx | task name | language | init_shape |
|---:|---|---|---|
| 0 | `LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket` | put both the alphabet soup and the tomato sauce in the basket | (50,123) |
| 1 | `LIVING_ROOM_SCENE2_put_both_the_cream_cheese_box_and_the_butter_in_the_basket` | put both the cream cheese box and the butter in the basket | (50,123) |
| 2 | `KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it` | turn on the stove and put the moka pot on it | (50,47) |
| 3 | `KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_of_the_cabinet_and_close_it` | put the black bowl in the bottom drawer of the cabinet and close it | (50,51) |
| 4 | `LIVING_ROOM_SCENE5_put_the_white_mug_on_the_left_plate_and_put_the_yellow_and_white_mug_on_the_right_plate` | put the white mug on the left plate and put the yellow and white mug on the right plate | (50,84) |
| 5 | `STUDY_SCENE1_pick_up_the_book_and_place_it_in_the_back_compartment_of_the_caddy` | pick up the book and place it in the back compartment of the caddy | (50,45) |
| 6 | `LIVING_ROOM_SCENE6_put_the_white_mug_on_the_plate_and_put_the_chocolate_pudding_to_the_right_of_the_plate` | put the white mug on the plate and put the chocolate pudding to the right of the plate | (50,71) |
| 7 | `LIVING_ROOM_SCENE1_put_both_the_alphabet_soup_and_the_cream_cheese_box_in_the_basket` | put both the alphabet soup and the cream cheese box in the basket | (50,84) |
| 8 | `KITCHEN_SCENE8_put_both_moka_pots_on_the_stove` | put both moka pots on the stove | (50,47) |
| 9 | `KITCHEN_SCENE6_put_the_yellow_and_white_mug_in_the_microwave_and_close_it` | put the yellow and white mug in the microwave and close it | (50,47) |

## 4. 官方评测协议（出处与逐项核对）

唯一权威出处：`/home/tarowang/workspace/roboot/libero-plus/openpi/examples/libero/main.py`（openpi 的 `pi05_libero` 官方结果表就是由此脚本产生，见 `examples/libero/README.md` 的 results 表）。

| 参数 | 值 | 出处（main.py 行号） |
|---|---:|---|
| `max_steps`（spatial / object / goal / libero_10） | **220 / 280 / 300 / 520** | 61 / 63 / 65 / 67（注释：最长训练 demo 分别 193/254/270/505 步） |
| `num_trials_per_task` | **50** | 38 |
| `num_steps_wait` | **10**（前 10 步用 dummy action 等物体稳定，**不计入** max_steps 预算：`while t < max_steps + num_steps_wait` 第 104 行） | 37 |
| `replan_steps` | **5**（模型每次 infer 的 action chunk 取前 5 步执行） | 29 |
| `seed` | **7** | 45 |
| env 分辨率 | **256×256** | 18 |
| dummy action | `[0.0]*6 + [-1.0]`（7 维：6 关节增量 + 夹爪） | 17 |
| 评测循环 | `task_suite = benchmark_dict[suite]()`（默认 `task_order_index=0`）→ `env.reset()` → `obs = env.set_init_state(initial_states[episode_idx])` → 每 `replan_steps` 重新 infer；`done` 即成功 | 54 / 93 / 97 / 127-158 |
| 观测预处理 | `agentview_image` / `robot0_eye_in_hand_image` 先 180° 翻转，再 `resize_with_pad(..., 224)`；state = `eef_pos + quat2axisangle(eef_quat) + gripper_qpos` | 113-141 |
| seed 语义 | `np.random.seed(seed)`（50 行）+ 构 env 后 `env.seed(seed)`（195 行，注释：固定 init state 时 seed 仍会影响物体位置） | 50 / 195 |

补充说明：

- `num_trials_per_task=50` 与每任务 50 条 `.pruned_init` 一一对应 → **每个初始状态只跑 1 次**；官方复现表（98.8/98.2/98.0/92.4）即此口径。
- 仓库现行的 rollback 实验协议是 `max_steps=600 / replan_steps=10`（见 `docs/libero-90-baseline-pi05-seed3.md`、`scripts/run_full_coverage.py` 的默认值），**与官方标准 baseline 不同**；跑标准 baseline 时请在 run 元数据里写清“220/280/300/520 · 50 trials · wait 10 · replan 5 · seed 7，出处 openpi examples/libero/main.py”，避免与 rollback 口径混用。
- `LIBERO_90` 的官方 max_steps=400 也一并记录在 `spec.json` 的 `evidence.protocol.max_steps.LIBERO_90`，本审计不展开 90 套件。

## 5. Shadow 方案（结论：可行；推荐 hybrid）

本机 `libero` pip 包实际是 `site-packages/libero/libero -> .../LIBERO-plus/libero/libero` 的软链；`site-packages/libero` 本身是 namespace 包（无 `__init__.py`）。因此 **`PYTHONPATH=<shadow root>` 会先于 site-packages 命中**，实测 shadow 进程里 `libero.libero.__file__` 指向 shadow，而不是 LIBERO-plus。

两种已验证 shadow（均由审计脚本在 `/tmp` 构建，不改仓库）：

| 方案 | 组成 | 验证结果 |
|---|---|---|
| `shadow_hybrid`（**推荐**） | 原版 `__init__.py` + `benchmark/{__init__,libero_suite_task_map,mu_creation}.py`（取自 git HEAD）；`envs/ utils/ assets/ bddl_files/ init_files/` 软链到已安装 LIBERO-Plus | 4 套件 `n_tasks=10`；任务名/顺序与 `shadow_full` 完全一致；`from libero.libero.envs import OffScreenRenderEnv` import OK |
| `shadow_full`（最忠实） | 56 个 `.py` 全部取自 git HEAD（完整原版包；资产由临时 config 指向 third_party） | 同上；import OK；40/40 BDDL 用本机 `bddl` 解析 OK |

两种方案都必须解决 **init states 的 torch 兼容问题**：

```
原版代码：torch.load(init_states_path)            # 无 weights_only 参数
本机 torch 2.7.1 默认 weights_only=True
→ UnpicklingError: Weights only load failed ... Unsupported global: numpy.core.multiarray._reconstruct
```

现有 runtime 已内置同一行 shim：`libero-runtime/tools/run_benchmark.py:50-51`

```python
_orig_load = _torch.load
_torch.load = lambda p, *a, **kw: _orig_load(p, *a, **{**{"weights_only": False}, **kw})
```

→ **用现有 runtime 跑 shadow 时无需额外改动**；自建评测脚本必须自己加这行（或按任务显式 `torch.load(path, weights_only=False)`）。审计实测：patch 前抛 `UnpicklingError`，patch 后 `get_task_init_states(0)` 返回 `ndarray, shape=(50,92)`。

最小可复现用法（hybrid；示例，供 Lead 集成）：

```bash
PY=/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python
TP=/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero
LP=/home/tarowang/workspace/roboot/libero-plus/LIBERO-plus/libero/libero
W=/tmp/std-libero-shadow; CFG=/tmp/std-libero-config
rm -rf $W $CFG; mkdir -p $W/libero/libero/benchmark $CFG $W/datasets
git -C $TP show HEAD:libero/libero/__init__.py > $W/libero/libero/__init__.py
for f in __init__.py libero_suite_task_map.py mu_creation.py; do
  git -C $TP show HEAD:libero/libero/benchmark/$f > $W/libero/libero/benchmark/$f; done
for d in envs utils assets bddl_files init_files; do ln -s $LP/$d $W/libero/libero/$d; done
cat > $CFG/config.yaml <<EOF
benchmark_root: $TP/libero/libero
bddl_files: $TP/libero/libero/bddl_files
init_states: $TP/libero/libero/init_files
datasets: $W/datasets
assets: $TP/libero/libero/assets
EOF
# 在评测进程（含 runtime）里：
export PYTHONPATH=$W
export LIBERO_CONFIG_PATH=$CFG
# 启动后立刻自检（必须在跑任何 episode 前）：
$PY - <<'PY'
import torch
_l = torch.load; torch.load = lambda p, *a, **k: _l(p, *a, **{**{"weights_only": False}, **k})
from libero.libero import benchmark
for cls in ["LIBERO_SPATIAL","LIBERO_OBJECT","LIBERO_GOAL","LIBERO_10"]:
    b = benchmark.get_benchmark(cls)()
    assert b.n_tasks == 10, (cls, b.n_tasks)      # 关键门禁
    s = b.get_task_init_states(0)
print("shadow OK:", b.__class__.__name__, "n_tasks=10, init", s.shape)
PY
```

> 注意：`LIBERO_CONFIG_PATH` 必须 export 给**真正跑评测的那个进程**（runtime 自身不设置它）；`~/.libero/config.yaml` 不要改。若改用 `shadow_full`，用同样的 `git show` 循环恢复 `libero/libero/**` 下全部 56 个 `.py` 即可，config 不变（指向 third_party 原版资产）。

与现有 runtime 的兼容性：`libero-runtime/libero_runtime/env_wrapper.py` 文件头明确写着 “Wraps the original LIBERO BDDLBaseDomain subclasses directly … Depends ONLY on: original LIBERO benchmark package (libero.libero.envs)”，并使用 `TASK_MAPPING`；hybrid/full 两种 shadow 都能提供该 API（实测 import OK）。runtime 中 `get_benchmark(suite)(task_order_index=0)` 与 `bm.get_task_init_states(...)` 的调用点（`tools/run_benchmark.py:55, 1014, 4623`）在 shadow 下会拿到 10 任务 benchmark。

## 6. 资产完整性（40/40 齐备；镜像“同源但视觉不完全相同”）

third_party 原版包（`$TP/libero/libero`）：

| 项 | 数量/大小 | 说明 |
|---|---|---|
| `bddl_files` | spatial/object/goal/libero_10 各 **10 个 `.bddl`**（+`tasks_info.txt`；spatial 另有 6 个 LIBERO-Plus 的 `*.bddl.M008_backup` 未跟踪残留） | 40/40 存在 |
| `init_files` | 各套件 **10 个 `.pruned_init`** | 40/40 存在，每任务 50 条 |
| `assets` | **16,286 个文件 / 3,288,549,581 B ≈ 3.1 GB** | 原版 tracked 资产完整（无 tracked 删除/修改） |
| 40 个 base 任务 | **40/40 齐备**（bddl+init 都命中） | 用 4 套件 task map 逐条核验 |
| 40/40 BDDL 可解析 | 用本机 `bddl 3.6.0` + 原版 `bddl_utils.robosuite_parse_problem` 解析：**40/40 OK** | 每个任务 `problem_name` 与 goal 项数已记录在 `spec.json` |

与 `LIBERO-plus` 资产树的交叉核对：

- **base BDDL / pruned_init：80/80 逐字节相同**（40 bddl + 40 init sha256 全等，0 缺失）→ 即使沿用默认 config（LIBERO-plus 资产），**任务数据本身**不会错。
- 但 **渲染资产不同**：共 42 个同名文件大小不同：13 个 scene XML 只“增补相机”（新增 34 条 `<camera>`，原有相机行未删；删改行数=0），29 个纹理被重编码/降采样（如 `gray_wall.png` 2400→512、`dark_green_plaster_wall.png` 1900→512；含物体纹理 `brown_ceramic_tile.png`、`ceramic.png`、`kona_gotham.png` 等），另有 1 个原版纹理 `textures/cream-plaster.png` 在 LIBERO-plus 树中缺失（原版 scene XML 未引用它，不影响加载）。
- 因此：**要点是“别用 LIBERO-Plus 资产渲染标准 baseline”**。用临时 `LIBERO_CONFIG_PATH` 指向 third_party 原版资产即可恢复官方视觉域；LIBERO-Plus env 代码本身不依赖新增资产（base 任务路径与原版一致，见 §2 的纯新增 diff 证据）。

## 7. 风险与建议（按严重度）

| # | 严重度 | 风险 | 证据 | 缓解 |
|---|---|---|---|---|
| R1 | **高** | 不加 shadow 时 `get_benchmark(...)` 返回 LIBERO-Plus 的 2402/2518/2591/2519 个任务，`task_idx` 语义完全不同，可能“静默跑错套件” | `spec.json → evidence.shadow.n_tasks_installed_liberoplus`；live first_task 带 `_table_1` 后缀 | shadow + 启动门禁 `assert n_tasks==10`；run 元数据记录 benchmark 来源路径 |
| R2 | **高** | 原版 `get_task_init_states` 在 torch 2.7.1 抛 `UnpicklingError`（weights_only） | 实测 unpatched FAIL / patched OK；runtime shim 行号 50-51 | 沿用 runtime，或自建 harness 加同一行 shim；不要逐帧依赖错误处理 |
| R3 | **中高** | 用默认 LIBERO-Plus 资产渲染 → 纹理分辨率/内容与 pi05 训练数据不一致，成功率可能系统性偏移 | 29 纹理降采样 + 13 scene 增补相机（`spec.json → evidence.assets.libero_plus_assets_diff`） | 临时 config 指向 third_party 原版资产；在本目录以外不要改 `~/.libero/config.yaml` |
| R4 | **中** | hybrid 栈的 env 代码是 LIBERO-Plus 补丁版（+275/−3 等，主要是扰动新增），base 任务行为“理论不变”但**未做仿真验证**（本审计禁起 episode） | 附录 A diff numstat；env_wrapper 的 3 处删改仅在 noise 分支 | 正式全量前跑 1 条 smoke episode（如 spatial idx0，50 步），对比 obs/成功判定与官方栈一致；或直接选 shadow_full |
| R5 | **中** | shadow_full（全原版）虽 import/解析全绿，但 env 创建/rollout 未验证；原版代码与本机 robosuite 1.4.0 / bddl 3.6.0 的实际运行兼容性属“高概率可行但未证实” | 56/56 个 py 取自 HEAD、import OK；40/40 bddl 用本机 bddl 解析 OK；runtime wrapper 明示依赖原版 API | 若追求最忠实 baseline：先 1 条 smoke episode 验证，再全量；否则用 hybrid |
| R6 | **中** | `LIBERO_CONFIG_PATH` 只影响 libero 包的路径解析，runtime 不自动设置；漏设会退回 `~/.libero`（LIBERO-plus 资产） | `libero/libero/__init__.py:5-8,38-50` | 在 WSL 启动脚本里显式 `export LIBERO_CONFIG_PATH=$CFG`；启动后打印 `get_libero_path("assets")` 自检 |
| R7 | 低 | `LIBERO_10` 的 init shape 因任务而异（45/47/51/71/84/123 维），不能硬编码 `(50,92)` 之类 | §1、§3.4 | 从 benchmark 逐任务 `get_task_init_states(i)`，或读 `spec.json` |
| R8 | 低 | third_party 工作树含约 800 个 LIBERO-Plus 未跟踪残留（`*_backup`、`.bak`、`scenes/study250` 等）；误 `git clean` 会删掉 LIBERO-plus 的备份，误 `git checkout` 会覆盖 live 补丁 | `git status --porcelain` | 只读使用；需要原版时用 `git show HEAD:<path>`/`git archive` 到 /tmp，不动工作树 |
| R9 | 低 | LIBERO-Plus live benchmark 的 task 顺序/编号与官方不同（idx0 已被 `_table_1` 类任务占据） | live first_task 输出 | 永远以 shadow benchmark 的 idx 为准；`spec.json` 即 shadow 口径 |
| R10 | 低 | 仓库现行 rollback 协议是 600 步/10 replan，与官方 220–520/5 不同；混用会让 baseline 数字不可比 | `docs/libero-90-baseline-pi05-seed3.md`、`scripts/run_full_coverage.py` | 标准 baseline 明确使用 §4 参数并写入 run meta；不要沿用 600/10 |
| R11 | 低 | `third_party/libero` 是**活的工作树**：审计期间观察到 untracked 条目数在变化（792→795）、`bddl_files/libero_spatial` 目录 mtime 被并发进程刷新（17:05）。可能是其他 teammate/进程在读写该树 | 审计末尾复检：40/40 bddl + 40/40 init 仍与 LIBERO-plus 镜像逐字节一致，无内容漂移 | `spec.json → evidence.integrity` 记录了 80 个文件的 sha256；正式跑前跑一遍 §8 的漂移校验（或把原版 bddl/init 冻结复制到只读目录再跑） |

## 8. 复现命令

一键复跑审计（会重建 /tmp shadow、不触碰仓库/配置/GPU，最后覆盖写同目录 `spec.json`）：

```bash
cd /home/tarowang/workspace/roboot/libero-rollback/.tmp/std-baseline-audit
/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python verify_std_libero.py \
  --output-dir . --work-dir /tmp/std-libero-audit-run
# 期望：checks 17/17 passed，退出码 0；spec.json 生成
```

正式 baseline 开跑前的资产完整性门禁（防止 R11 漂移）：

```bash
PY=/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python
SPEC=/home/tarowang/workspace/roboot/libero-rollback/.tmp/std-baseline-audit/spec.json
$PY - "$SPEC" <<'PY'
import hashlib, json, sys
spec = json.load(open(sys.argv[1]))
integ = spec["evidence"]["integrity"]
bad = []
for kind in ("bddl_sha256", "init_states_sha256"):
    for path, want in integ[kind].items():
        got = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if got != want:
            bad.append((kind, path))
print("drift:", bad if bad else "none (40 bddl + 40 init OK)")
PY
```

脚本内部的关键证据命令（可单独复跑）：

```bash
TP=/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero
# 1) 原版来源
git -C $TP rev-parse HEAD                       # f78abd6...（上游 LIBERO）
git -C $TP remote -v                            # Lifelong-Robot-Learning/LIBERO.git
git -C $TP status --porcelain | grep -v '^??'   # 13 个 M = LIBERO-Plus patch
# 2) .bak 是否干净原版
git -C $TP diff --numstat                       # 纯新增为主
for f in benchmark/__init__.py benchmark/libero_suite_task_map.py \
         envs/problems/libero_{tabletop,study_tabletop,floor,coffee_table,living_room_tabletop,kitchen_tabletop}_manipulation.py; do
  git -C $TP show HEAD:libero/libero/$f | cmp - $TP/libero/libero/$f.bak && echo "OK $f.bak"
done
# 3) shadow 枚举（完整命令见 §5）
# 4) 资产对比：base bddl/init sha256、纹理尺寸、scene xml 增删行 → 见 verify_std_libero.py 的 asset_inventory()
```

## 9. 产物与检查项

- `spec.json`：`{suites: {SUITE: {max_steps, tasks: [{idx,name,language,bddl,init_states,init_shape,init_count}]}}, protocol: {num_trials_per_task,num_steps_wait,replan_steps,seed}, evidence}`；所有路径为 third_party 原版资产绝对路径。`evidence` 里包含完整证据链（git 来源、8 个 `.bak` 校验、shadow 两方案结果、torch shim、资产对比、40 任务 BDDL 解析、40 任务 bddl/init 的 sha256（`evidence.integrity`）、协议原始行号、17 项检查结果、LIBERO-Plus 当前 n_tasks）。
- `verify_std_libero.py`：只读审计脚本；`/tmp` 内构建 shadow（56 py / hybrid 软链）、临时 config、8 个子进程 probe（2×枚举 + 2×env import + 40 BDDL 解析 + live n_tasks + …），最终写 `spec.json`。
- 审计自检：**17/17 全绿**（shadow 文件来源、n_tasks=10、两 shadow 顺序一致、env import、40/40 bddl parse、live 包为 LIBERO-plus、`.bak == HEAD`、每套件 10 bddl/10 init、40 任务齐备、50 init/任务、镜像 80/80 字节一致、language 非空、integrity 哈希 80/80、init 数值全 finite）。

## 附录 A：LIBERO-Plus 对 third_party/libero 的 tracked 修改（`git diff --numstat`）

| 文件 | + | − |
|---|---:|---:|
| `libero/libero/benchmark/__init__.py` | 130 | 43 |
| `libero/libero/benchmark/libero_suite_task_map.py` | 10031 | 41 |
| `libero/libero/envs/arenas/style.py` | 286 | 0 |
| `libero/libero/envs/bddl_base_domain.py` | 1 | 0 |
| `libero/libero/envs/env_wrapper.py` | 275 | 3 |
| `libero/libero/envs/objects/__init__.py` | 1 | 0 |
| `libero/libero/envs/problems/libero_coffee_table_manipulation.py` | 205 | 2 |
| `libero/libero/envs/problems/libero_floor_manipulation.py` | 29209 | 6 |
| `libero/libero/envs/problems/libero_kitchen_tabletop_manipulation.py` | 33017 | 3 |
| `libero/libero/envs/problems/libero_living_room_tabletop_manipulation.py` | 32209 | 6 |
| `libero/libero/envs/problems/libero_study_tabletop_manipulation.py` | 31459 | 6 |
| `libero/libero/envs/problems/libero_tabletop_manipulation.py` | 31460 | 6 |
| `libero/libero/envs/regions/__init__.py` | 8746 | 0 |

解释：benchmark 两个文件被整体改写（扩展任务表/语言生成）；env 侧基本是扰动特性新增（多视角、噪声、新区域/新物体），原版逻辑保留度高，但**不是官方代码原样**——这正是推荐“最忠实 baseline 用 shadow_full、工程稳妥用 shadow_hybrid”的原因。

## 附录 B：审计检查项（17/17 passed）

1. `shadow_full_py_count>=50`（56 个原版 py）
2. `full_shadow_libero_libero_file` 指向 /tmp shadow
3. `hybrid_shadow_libero_libero_file` 指向 /tmp shadow
4. `n_tasks_all_10`：4 套件均 10
5. `full_vs_hybrid_task_order_equal`：两 shadow 任务名/顺序一致
6. `full_shadow_env_import` OK
7. `hybrid_shadow_env_import` OK
8. `all_40_bddl_parse`：40/40 OK（bddl 3.6.0）
9. `live_package_is_liberoplus`：live 包 realpath 指向 LIBERO-plus
10. `bak_files_are_clean_head`：8/8 `.bak` == `git show HEAD:`
11. `pristine_10_bddl_10_init_per_suite`
12. `all_40_tasks_complete`：bddl+init 均存在
13. `all_init_counts_50`
14. `base_bddl_init_byte_identical_in_liberoplus_mirror`：80/80
15. `language_non_empty`
16. `integrity_hashes_recorded`：40 bddl + 40 init sha256
17. `init_all_finite`：2000 条初始状态数值全部 finite

审计的临时工作目录：`/tmp/std-libero-audit-run/`（shadow 包、临时 config、子进程 JSON 证据），可随时删除；未写入任何受保护路径。
