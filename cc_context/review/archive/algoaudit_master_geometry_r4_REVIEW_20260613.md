# 终末地 IndustrialPlanner 精确求解器 — 几何 master round 4 review

## 0. 开工校验

- 指定快照：`/mnt/data/zmd_snapshot_278e4d67.zip`
- sha256：`278e4d67f97a88cab7bba697ec96df2f04d43ce1475bc65aef4a22519d1885a0`，与任务给定值一致。
- 解包根：`/mnt/data/zmd_r4_work/project`
- Python：3.13.5
- 依赖：从 `zmd_py313_linux_x86_64.zip` 离线安装。
- `candidate_placements.json`：按要求运行 `python3.13 src/placement/placement_generator.py` 再生；sha256 为 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`。

## 1. Finding

### F-GM-Q3-01-R4-A — High / false-INFEASIBLE

**位置**

- `src/models/master_model.py:80`：`POSE_LEVEL_OPTIONAL_TEMPLATES = {"power_pole", "protocol_storage_box"}`，`power_pole` 是 pose-level optional 模板。
- `src/models/master_model.py:2269-2273`：`exact_required_pose_optional_counts` 接收任意正计数 key；没有排除 `power_pole`。
- `src/models/exact_coordinate_master.py:1662-1666`：原 `_power_pole_family_count_upper_bound()` 只用 `len(residual_optional_slots["power_pole"])` 作为 slot pool 上界。
- `src/models/exact_coordinate_master.py:3118-3233`：原 `_create_power_pole_slot_vars()` 只给 residual `power_pole` slot 建 active/family/family-membership channel；required optional `power_pole` slot 已经被创建，但没有接入 pole family。
- `src/models/exact_coordinate_master.py:4971-5021` 与 `src/models/exact_coordinate_master.py:5616-5654`：原 table/geometric power coverage witness 只枚举 residual `power_pole`，required fixed `power_pole` 不参与供电 witness。

**问题**

R3-A 修复确认时，`protocol_storage_box` 的 fixed+residual 混合语义已经闭合；但同一个 required optional API 对当前另一个 pose-level optional 模板 `power_pole` 暴露了新缝：当调用者显式传入 `exact_required_pose_optional_counts={"power_pole": 1}` 时，非 protocol 模板按“fixed 全代表”语义不会再创建 residual pole pool。这本身可以成立，但 fixed pole 仍必须作为真实电杆进入供电与 family capacity 约束。

原编码中 fixed `power_pole` 只作为 required optional 几何 slot 占格，不作为 power pole：

1. 不进入 `_power_pole_family_membership`，所以 family count 变量看不到它；
2. 不进入 `_add_geometric_power_coverage_constraints()` / `_add_table_power_coverage_constraints()` 的 `pole_slots`，所以 mandatory powered facility 没有 witness；
3. residual pole pool 又因为 fixed 全代表语义被跳过，于是合法的“固定 1 根杆供 1 台机器”配置被误判 INFEASIBLE。

**可复现 probe**

合法实例：2×1 网格，mandatory powered `machine` 固定在 `(0,0)`；required fixed `power_pole` 固定可放在 `(1,0)`；杆覆盖半径 1，`power_coverage_cells=[[0,0],[1,0]]`。物理上显然可行：`machine@0,0 + pole@1,0`。

在修复前，该配置结果为 `INFEASIBLE`，且 build stats 中 `required_optional_slots["power_pole"] == 1`、`residual_optional_slots["power_pole"] == 0`、`power_coverage["pole_slots"] == 0`。修复后同 probe 为 `OPTIMAL`，`power_coverage["pole_slots"] == 1`。

已加入回归：`src/tests/test_exact_coordinate_protocol_bounds.py::test_fixed_required_power_pole_slots_cover_powered_facilities`。

**修法**

补丁 `F-GM-Q3-01-R4-A.patch` 做了以下最小收敛：

- 新增 `_all_power_pole_slots()`，统一返回 required fixed + residual pole slots。
- 为 required fixed `power_pole` 添加 family tuple channel，并将其 membership literal 纳入 family count。
- `_power_pole_family_count_upper_bound()` 改用全部 materialized pole slots，而不是只看 residual pool。
- table/geometric power coverage witness 改用 `_all_power_pole_slots()`。
- 对 required pole 的 active lookup 使用常量 1；residual pole 仍使用原 active Bool。
- lazy power completion stats 的 `power_pole_slots_materialized` 也改为看全部 materialized pole slots。

该修法不改变 R3-A 的 protocol residual 判定：protocol 仍是 `lower > fixed` 才保留 residual pool；非 protocol 模板仍是 fixed 全代表语义，只是 fixed `power_pole` 现在也真正承担电杆语义。

## 2. Q1 — F-GM-Q3-01-R3-A 修复确认

### 2.1 `_needs_residual_optional_slots_after_fixed_required()` 调用点

静态扫描 `src/models/exact_coordinate_master.py` 与 `src/models/master_model.py`：该谓词直接调用点只有两处：

| 调用点 | 用途 | 结论 |
|---|---:|---|
| `exact_coordinate_master.py:1977` | residual protocol bucket 准备 | 使用 R3-A 谓词，未见旧 `fixed > 0` 直接跳过逻辑 |
| `exact_coordinate_master.py:2299` | residual optional slot 创建 | 使用 R3-A 谓词，未见旧 `fixed > 0` 直接跳过逻辑 |

跨文件第三处不是直接调用谓词，而是 `master_model.py:5222-5240` 的 `_residual_optional_powered_slot_upper_bounds()`。这段仍保留本地分支，但三段区间与 delegate 当前口径等价：

| 区间 | delegate residual 池 | delegate residual upper | master powered residual 统计 | 结论 |
|---|---:|---:|---:|---|
| `fixed = 0` | 保留 | `upper` | `upper` | 一致 |
| `0 < fixed < lower`，仅 protocol | 保留 | `max(0, upper - fixed)` | `max(0, upper - fixed)` | 一致 |
| `fixed >= lower`，protocol | 跳过 | 0 | 跳过 | 一致 |
| `fixed > 0`，非 protocol | 跳过 residual | 0 | 跳过 | 一致；本轮 finding 是 fixed `power_pole` 本身未接入 pole 语义，而非 residual 判定复发 |

### 2.2 `upper < fixed` 边界

`_residual_optional_slot_upper_bound()` 对 protocol 使用 `max(0, upper - fixed)`。若出现 `upper < fixed`，含义是显式 fixed count 已经超过 certified total upper bound。当前 upper 来源为 `min(candidate_pose_count, grid_area // template_area)`；对 solid rectangular optional 来说这是必要上界，不是估计。若同时 `lower > fixed`，则编码退化为 `0 >= shortfall`；这是“lower 超过 fixed + 可补 residual 上界”的真 INFEASIBLE，不是 false-INFEASIBLE。

审查结论：可以考虑以后增加更早的诊断型 ValueError，让 API 输入不一致更醒目；但当前 fail-closed UNSAT 对 soundness 是安全的。

### 2.3 required optional 模板枚举

| 模板 | 当前是否 pose-level optional | certified lower 来源 | certified total upper 来源 | fixed 语义 | 本轮结论 |
|---|---:|---|---|---|---|
| `protocol_storage_box` | 是 | `ceil(required_generic_input_slots / wireless_sink_generic_input_slots)` | `min(candidate_pose_count, grid_area / area)` | fixed 先计入 lower，再用 residual 补 shortfall | R3-A 口径闭合 |
| `power_pole` | 是 | 无 protocol-style lower | selected powered upper + family capacity bounds，不走 `_certified_optional_slot_upper_bound()` | fixed 全代表；不再创建 residual pool | 原 fixed pole 未接入供电/family，已作为 F-GM-Q3-01-R4-A 修复 |

当前没有第二个“有 lower bound 且会落入 protocol 同型 fixed+residual shortfall 缝”的模板。`power_pole` 的问题是另一类：fixed 代表全量时，fixed slot 必须进入 power-pole 专用通道。

## 3. Q2 — optional 基数有效不等式族双向保真

### 3.1 模板 × bound 方向 × 推导依据

| 模板/族 | bound 方向 | 编码位置 | 推导依据 | false-INFEASIBLE 结论 |
|---|---:|---|---|---|
| `protocol_storage_box` | upper | `master_model.py:5195-5220`，delegate residual 扣 fixed | `candidate_pose_count` 是候选位姿数量上界；`grid_area // template_area` 来自 solid rectangular footprint + NoOverlap2D 的面积必要条件 | 有效不等式；不是启发式 |
| `protocol_storage_box` | lower | `master_model.py:2030-2055`、delegate `:5985-6019` | generic input 总需求除以每个 wireless sink 的 generic input slots，向上取整 | 有效必要 lower；fixed 已扣 shortfall，不复发 R3-A |
| `power_pole` residual slots | selected upper | `exact_coordinate_master.py:6051-6069` | 每个 powered non-pole 只要求一个 pole witness；多出的 residual optional pole 可置 inactive，因此存在同等可行解满足 `selected_poles <= selected_powered_nonpoles` | 对 residual optional pole 有效；补丁后不限制显式 required fixed pole |
| `power_pole` family counts | upper | `exact_coordinate_master.py:_power_pole_family_count_upper_bound()` | family 可用 pose 数有限，materialized pole slot 数也有限，故 `count_family <= min(family_pose_count, pole_slot_count)` | 有效；补丁后 fixed pole 纳入 materialized slot 数 |
| `power_pole` family activation/order | canonical / symmetry | `exact_coordinate_master.py:3211-3223` | pole slots 匿名；active 前缀、family 非降、同 family order_key 非降可由重标号得到 | 不裁真实布局；只裁 slot 标签排列 |
| power capacity family lower | lower | `exact_coordinate_master.py:6081-6127` | 每个 family 对每类 powered template 有可覆盖容量系数；选中 family count 的容量和必须覆盖 demand | 必要条件；无 terms 且 demand > 0 时 UNSAT 为真不可行 |

### 3.2 lower bound 注入链

`wireless_sink_generic_input_slots` 链路一致：

1. `master_model.py:2016-2027` 归一化；`None` 时读取 `wireless_sink` operation profile 的 `generic_input_slots`，显式输入要求 strict int 且非负。
2. `master_model.py:2030-2055` 用该值推导 `_certified_optional_lower_bounds["protocol_storage_box"]`。
3. `build_exact_core()` 在 `ExactMasterCore` 中固化 `wireless_sink_generic_input_slots`。
4. `from_exact_core()` 用 core 内同一值重建模型。
5. delegate 在 `_add_global_valid_inequalities()` 消费 owner 的 `_required_protocol_storage_box_lower_bound()` 与 `wireless_sink_generic_input_slots`。

未发现第二个 optional lower bound 登记点。

### 3.3 power pole family 瀑布激活 / 高编号 family 可行性

family 间也是匿名槽重标号问题，而不是几何 family 的强制启用顺序。`family <= next.family` 只要求已选择 pole slots 的 family id 非降；如果只有高编号 family 可行，所有 active pole slots 可以都取该高编号 family，低编号 family count 为 0，不会被瀑布激活强迫使用。inactive slots 使用 sentinel family，active-prefix 把 inactive 放末尾。结论：不切掉“只有高编号 family 可行”的配置。

### 3.4 slot pool 为 0 的退化矩阵

| 家族 | pool=0 条件 | lower/demand | 编码退化 | soundness |
|---|---|---:|---|---|
| protocol residual | `upper - fixed <= 0` 或无候选 | `shortfall <= 0` | 不加 residual lower | 可行性不受 cardinality 误杀 |
| protocol residual | 同上 | `shortfall > 0` | `0 >= shortfall` | 真 INFEASIBLE：没有可补 residual box |
| protocol fixed | 无候选但 fixed > 0 | 任意 | required slot 空域已 fail-closed | 真 INFEASIBLE |
| residual power pole | demand=0 导致 upper=0 | 0 | 无 pole witness/family demand | 可行 |
| residual power pole | no pole slots | demand>0 | coverage 或 family lower 变 `0 >= demand` | 真 INFEASIBLE，除非显式 fixed pole；补丁后 fixed pole 已计入 witness/family |
| family count | materialized pole slots=0 | demand=0 | count var 0 或无 terms | 可行 |
| family count | materialized pole slots=0 | demand>0 | `0 >= demand` | 真 INFEASIBLE |

## 4. Q3 抽查维持 + 挂账复核

### 4.1 `enable_symmetry_breaking=False` 仍存在 order-key/active-prefix canonicalization

复核结论：这是配置语义问题，不是 soundness 问题。

`_add_coordinate_symmetry_breaking()` 只控制 signature monotonic 一类显式 symmetry-breaking stats；但 mandatory/required/residual/power-pole slot 的 active prefix 与 order-key canonicalization 在变量创建阶段无条件加入。由于这些 slots 是匿名槽，任意可行解都可以对 slot 标签重新排序，使 active slots 前缀化、同类 order_key 非降、同 family 非降，同时保持实际几何集合不变。因此它裁的是标签排列，不是真布局。未构造出裁真解 probe。

### 4.2 B-01 footprint bbox / mode-channel 抽查

- `_pose_mode_token()` 把 `_pose_footprint_key()` 纳入 mode token。
- `_build_mode_rect_domains_from_pose_indices()` 校验同 mode 内 footprint bounds 唯一；若 token 拆分后仍出现多 bounds，会 fail-closed。
- `_create_slot_footprint_intervals()` 用 footprint bounds 与 footprint width/height 建半开 footprint interval，并用 allowed assignment 绑定 mode、offset、尺寸。

结论：B-01 footprint bbox 派生修复仍在场，未发现本面新 soundness 缝。

### 4.3 ghost 半开锚点域抽查

`_add_ghost_constraints()` 对 ghost anchor 使用：

- `range(self.grid_w - ghost_w + 1)`
- `range(self.grid_h - ghost_h + 1)`

这正是半开矩形 anchor 完整域 `[0, grid_w - ghost_w] × [0, grid_h - ghost_h]`。若 ghost 尺寸超过 grid，则直接 `0 == 1` fail-closed。抽查未发现 off-by-one。

## 5. 验证记录

已执行：

```bash
sha256sum /mnt/data/zmd_snapshot_278e4d67.zip
python3.13 src/placement/placement_generator.py
sha256sum data/preprocessed/candidate_placements.json
python3.13 -m pytest -q src/tests/test_exact_coordinate_protocol_bounds.py -p no:randomly
python3.13 -m pytest -q src/tests/test_master.py -p no:randomly
python3.13 -m pytest -q src/tests -k 'coordinate_exact or power_pole or power_coverage or exact_power_capacity or protocol_lower_bound' -p no:randomly
python3.13 scripts/check_p1_2_proof_obligations.py
```

结果：

- snapshot sha256：匹配任务指定值。
- `candidate_placements.json` sha256：`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`。
- `test_exact_coordinate_protocol_bounds.py`：`3 passed`。
- `test_master.py`：`226 passed`。
- targeted coordinate/power/protocol selection：`100 passed, 2938 deselected`。
- proof obligation：`P1.2 proof obligation check passed: 8 obligations anchored`。

全量 `python3.13 -m pytest -q src/tests -p no:randomly` 也尝试运行，但在 300 秒超时；已观察到的前缀无失败。由于时间限制，本轮声明为“全量未跑完，专项与相关族通过”。

## 6. 结论

本轮不是零 finding：发现并修复 1 个 latent+API soundness 问题 `F-GM-Q3-01-R4-A`。R3-A 的 protocol fixed+residual 修复本身未发现复发；新问题来自 `power_pole` fixed required optional slot 没有进入 power-pole 专用 family/coverage 通道。
