# 终末地 IndustrialPlanner 几何 master round 8 审查报告

审查对象：`zmd_snapshot_37b84be0.zip`

快照校验：通过。

```text
37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd  zmd_snapshot_37b84be0.zip
```

候选工件校验：`data/preprocessed/candidate_placements.json` 与任务给定口径一致，sha256 为 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，大小为 `45,773,799` bytes。

本轮结论：**非零 soundness finding**。发现并修补 1 个几何 master soundness 问题，另修补 1 个 LOW 级 hint 健壮性问题。

## Findings

### F-GM-R8-SYM-01，HIGH，soundness：signature 单调对称破缺可删除整个等价类，导致 false-INFEASIBLE

位置：原始快照 `src/models/exact_coordinate_master.py` 的 `_add_coordinate_symmetry_breaking`，约 L3449-L3499；与 slot 级 `order_key` 单调约束组合，约 L2789-L2936、L3274-L3288。补丁后相关位置为 L2509-L2616、L3561-L3628。

问题形态：mandatory/required/residual 的同构 slot 已经按 `order_key = x * scale_x + y * scale_y + mode` 排序。随后代码又对相邻 slot 加 `signature_left <= signature_right`。这两条排序不是同一把标尺。只要存在 `order_key` 较小的 pose 落在较大的 signature bucket，而 `order_key` 较大的 pose 落在较小的 signature bucket，就会出现如下结构：

```text
slot0.order_key <= slot1.order_key 迫使代表为 [order_low, order_high]
slot0.signature <= slot1.signature 又要求 [sig_low, sig_high]
若实际唯一 order 代表是 [sig_high, sig_low]，则整个等价类被删空。
```

这是对称破缺的禁区：对称破缺必须“每个可行等价类至少留一个代表”，这里会把代表全剪掉，得到漏真矩形的 false-INFEASIBLE。

实数据并非理论边角。用当前全量 pool 检查 bucket 序与 `order_key` 序，多个 mandatory group 存在反向排列。例如：

```text
group::manufacturing_3x3::crusher_blue_iron::1
pose 254: tuple=(1,65,3), order_key=543, signature bucket=1
pose 257: tuple=(2,0,1),  order_key=561, signature bucket=0
```

最小复现已经固化为回归测试 `src/tests/test_master.py::test_coordinate_symmetry_breaking_skips_incompatible_signature_order_slots`。该 fixture 有 2 个同构 mandatory slot 和 2 个 pose：

```text
pose0: x=0, output E, order 低，signature 高
pose1: x=1, output W, order 高，signature 低
```

原始模型中，开启 symmetry 时求解为 `INFEASIBLE`，关闭 symmetry 时为 `OPTIMAL`。原因是 NoOverlap 要求两个 pose 都放，`order_key` 单调保留的唯一代表正好违反 `signature` 单调。

修法：补丁保留 `order_key` 单调这条安全排序；对 `signature` 单调增加同序门卫。只有当某个 slot 集合中所有候选 pose 的 `signature_int` 按 `order_key` 非降时，才加入 `signature_left <= signature_right`。此时 signature 单调是 `order_key` 单调的冗余后果，不会删解。若发现反向排列，则跳过该 signature 单调约束，并通过 telemetry 记录跳过数量：

```text
mandatory_signature_monotonic_skipped_incompatible_order
required_optional_signature_monotonic_skipped_incompatible_order
residual_optional_signature_monotonic_skipped_incompatible_order
```

补丁后用当前全量 artifact 构建几何 master，统计为：

```json
{
  "enabled": true,
  "mandatory_signature_monotonic_constraints": 45,
  "mandatory_signature_monotonic_skipped_incompatible_order": 202,
  "power_pole_family_order_constraints": 762,
  "required_optional_signature_monotonic_constraints": 0,
  "required_optional_signature_monotonic_skipped_incompatible_order": 0,
  "residual_optional_signature_monotonic_constraints": 543,
  "residual_optional_signature_monotonic_skipped_incompatible_order": 0,
  "slot_order_key_monotonic_constraints": 790
}
```

这说明补丁不是粗暴关闭 symmetry，而是仅跳过不保代表的 signature 排序。

### F-GM-R8-HINT-02，LOW，非 soundness：ghost anchor malformed hint 在 telemetry 返回阶段仍可抛 `ValueError`，pose hint 还会接受 float/bool 截断

位置：原始快照 `src/models/exact_coordinate_master.py::apply_solution_hint`，约 L6654-L6744。补丁后为 L6780-L6874。回归在 `src/tests/test_solution_hint_malformed_defense.py` L86-L117。

问题形态：r7 的修复已经在 ghost anchor hint 应用前捕获 `int()` 失败，但 return payload 又执行了一次 `int(ghost_anchor_hint_idx)`：

```python
"ghost_anchor_hint_idx": None if ghost_anchor_hint_idx is None else int(ghost_anchor_hint_idx)
```

因此 `ghost_anchor_hint_idx="not_an_int"` 或 `"2.0"` 不会写 hint，但会在返回 telemetry 时抛异常。它不改变 CP-SAT 可行域，属于可用性和诊断问题，不是 soundness。

同一段代码还用宽松 `int(pose_idx)` 解析 pose hint，因此 `0.9`、`0.0`、`True`、`False` 等会被截断或布尔化后穿过。hint 仍只调用 `model.AddHint`，不会约束模型，但这不符合“malformed hint 统一 skip”的 r7 语义。

修法：新增 `_strict_int_hint_value`，只接受真实 `int`，显式拒绝 `bool`、`float`、数字字符串和普通字符串。ghost anchor telemetry 改为返回解析后的整数或 `None`，不再在 return 阶段二次 `int()`。

补丁后 probe 输出摘要：

```text
ghost 'not_an_int' OPTIMAL applied=False idx=None hinted=0
ghost '0'          OPTIMAL applied=False idx=None hinted=0
ghost '2.0'        OPTIMAL applied=False idx=None hinted=0
ghost 0.0          OPTIMAL applied=False idx=None hinted=0
ghost True         OPTIMAL applied=False idx=None hinted=0
ghost 999          OPTIMAL applied=False idx=999  hinted=0
ghost 0            OPTIMAL applied=True  idx=0    hinted=2
pose '0'           OPTIMAL hinted=0
pose 0.9           OPTIMAL hinted=0
pose True          OPTIMAL hinted=0
pose 0             OPTIMAL hinted=3
```

## Q1：R7-HINT 修复确认

`grouped_hints` 的 skip 与 `zip` 截断不会派生约束。`apply_solution_hint` 先把合法 pose index 按 group 收集，排序后与同构 slot `zip`，并只调用 `model.AddHint` 写入 `x/y/mode` 初值。跳过某个 malformed pose 会让列表缩短，但不会写约束，不会进入 Benders/cut/binding contract，也不会改变 feasible set。mandatory group 本身是计数语义，slot 与 instance 身份后续也是排序回填，不依赖 hint 的原始 instance 顺序。

malformed 覆盖在补丁后闭合：非真实 int、float、bool、数字字符串、普通字符串全部 skip；负数和越界 int 可以被记录到 telemetry，但只有命中 `u_vars` 或 template pose tuple 时才写 hint。不存在 anchor 的 ghost idx 不写 one-hot hint；不存在 pose idx 不写 slot hint。

`ghost_anchor_hint_applied` 补丁后只在真正遍历 `_ordered_ghost_anchor_indices()` 并写入 one-hot hint 后置 true。skip 路径不会误标 applied。

## Q2：对称破缺、mandatory 装配本体、optional/residual 语义

### 对称破缺逐条审查

`mandatory` 和 `required_optional` 的 `order_key` 单调是安全的。slot 是同构 slot，任意可行多重集都可以按 `(x,y,mode)` 的 total key 排序，排序后仍代表同一个几何多重集。代码位置为 `src/models/exact_coordinate_master.py` L2894-L2898、L2935-L2939。

普通 `residual_optional` 的 active 排序是安全的。`left.active >= right.active` 把 active slot 前置，`order_key <=` 只在 `right.active` 时启用，所以只对 active 前缀排序；inactive slot 使用默认坐标并且 optional interval 不参与 NoOverlap。代码位置为 L3034-L3041。

`power_pole` residual 的 family 排序是安全的。`active` 前置后，`family <=` 按 family 排序；同 family 时再按 `order_key` 排序。inactive family 为 sentinel，排在 active family 后面。由于 power_pole residual slot 本身同构，按 `(active, family, order_key)` 选代表不会删除整个等价类。代码位置为 L3379-L3391。

原始 `signature` 单调不安全，见 F-GM-R8-SYM-01。补丁后它只在 signature 与 `order_key` 同序时加入；否则跳过。因此补丁后的 signature 单调为冗余剪枝，不再承担不保代表的第二排序。

### mandatory 装配计数对照

装配链代码：`MasterPlacementModel._build_mandatory_groups` 按 `(facility_type, operation_type)` 分组并记录 `count` 与排序后的 `instance_ids`，位置为 `src/models/master_model.py` L2969-L2995。`CoordinateExactMasterDelegate._prepare_slot_specs` 对每个 group materialize `range(group["count"])` 个 slot，位置为 `src/models/exact_coordinate_master.py` L2242-L2272。

对 `data/preprocessed/mandatory_exact_instances.json` 的 266 个实例逐 group 对照如下：

| facility_type | operation_type | instances | master slots |
|---|---:|---:|---:|
| boundary_storage_port | boundary_io | 46 | 46 |
| manufacturing_3x3 | crusher_blue_iron | 34 | 34 |
| manufacturing_3x3 | crusher_buckwheat | 6 | 6 |
| manufacturing_3x3 | crusher_sandleaf | 11 | 11 |
| manufacturing_3x3 | crusher_source | 18 | 18 |
| manufacturing_3x3 | molding_bottle | 6 | 6 |
| manufacturing_3x3 | parts_maker | 6 | 6 |
| manufacturing_3x3 | refinery_blue_iron | 34 | 34 |
| manufacturing_3x3 | refinery_steel | 17 | 17 |
| manufacturing_5x5 | planter_buckwheat | 11 | 11 |
| manufacturing_5x5 | planter_sandleaf | 21 | 21 |
| manufacturing_5x5 | seed_collector_buckwheat | 6 | 6 |
| manufacturing_5x5 | seed_collector_sandleaf | 11 | 11 |
| manufacturing_6x4 | filling_capsule | 3 | 3 |
| manufacturing_6x4 | grinder_dense_blue_iron | 17 | 17 |
| manufacturing_6x4 | grinder_dense_source | 9 | 9 |
| manufacturing_6x4 | grinder_fine_buckwheat | 6 | 6 |
| manufacturing_6x4 | packaging_battery | 3 | 3 |
| protocol_core | protocol_core | 1 | 1 |
| **total** |  | **266** | **266** |

master 侧 contract 是计数/多重集语义，不是强身份语义。`extract_solution` 将 group 内选中的 pose index 排序，再与排序后的 `instance_ids` zip 回填，位置为 `src/models/exact_coordinate_master.py` L6722-L6742。对于同一 `(facility_type, operation_type)` 的 mandatory 实例，master 不承诺某个物理 slot 对应某个原始 instance 身份，只承诺该 group 的 count 和 pose 多重集。

当前 artifact 下 `exact_required_pose_optional_counts` 为空，因此 required optional slot 数为 0。residual optional slot 为：

```text
protocol_storage_box: 544
power_pole: 763
```

### optional/residual active 语义

signature optional path：`_create_optional_signature_slot_vars` 创建 `active`，用 optional interval 承载 NoOverlap，inactive 时 `signature == inactive_signature_value`，并用 `sum(bucket_lits) == active` 绑定 bucket。active 为 1 时恰有一个 bucket lit 和一个 region lit 生效；active 为 0 时所有 bucket/region lit 为 0，不会施加占地 region。代码位置为 L2783-L2858。

plain residual path：每个 slot 创建 `active` 和 optional interval，inactive 时 `mode/x/y` 归到 default domain；若存在 sparse domain table，`AddAllowedAssignments([x,y,mode], rows)` 只在 active 时 enforce。代码位置为 L3005-L3033 和 `_create_base_slot_geometry` L2675-L2692。

power_pole residual path：每个 power pole slot 创建 `active`、optional interval 和 `family`。family lookup 表只在 active 时 enforce；inactive 时 `x/y` 为默认值，`family` 为 sentinel。代码位置为 L3298-L3365。inactive slot 因 optional interval 不进入 NoOverlap，不形成幽灵占地。

未发现 optional/residual active 挂接遗漏。保留的 inactive 约束都是默认值或 sentinel，属于可满足的解码约束，不是几何占地约束。

## Q3：自由攻击角

我选了两个缝隙深挖。

第一，稀疏 `AddAllowedAssignments` 域表生成。攻击点是 `allowed_tuples` 是否可能少于 candidate pose，或者 optional inactive 是否仍被 sparse table 约束。mandatory 的 candidate tuples 来自 `_candidate_pose_indices_for_group(group)`，再由 `_template_pose_tuple_by_idx` 转成 `(x,y,mode)`，位置为 L2250-L2268。`_create_base_slot_geometry` 只在 `slot.use_domain_table and slot.allowed_tuples` 时加入 table；optional path 对 table 加 `OnlyEnforceIf(slot.active)`。若 domain 完全空，代码创建 0 域变量后立刻 `Add(0 == 1)` fail-closed。结论：未发现 soundness 问题。

第二，build 顺序依赖。攻击点是 symmetry 约束是否可能在 `signature/order_key/active/family` 变量建好前读取 `None`，从而漏约束或半挂约束。`build()` 的顺序是 `_create_mandatory_slot_vars()`、`_create_required_optional_slot_vars()`、`_create_residual_optional_slot_vars()`、`_create_power_pole_slot_vars()`，最后才 `_add_coordinate_symmetry_breaking()`，位置为 L3421-L3425。所有 slot 的 `order_key` 在 `_create_base_slot_geometry` 中创建；signature path 在 slot var 创建阶段创建；power family 在 `_create_power_pole_slot_vars` 中创建。结论：除 F-GM-R8-SYM-01 的“不保代表”问题外，未发现 build 顺序导致的额外 soundness 问题。

## Patch 摘要

修改文件：

```text
src/models/exact_coordinate_master.py
src/tests/test_master.py
src/tests/test_solution_hint_malformed_defense.py
```

核心变更：

```text
1. 新增 signature/order_key 同序检测，只在保代表时添加 signature 单调对称破缺。
2. 新增 symmetry skipped telemetry，便于诊断哪些 signature 单调因不保代表被跳过。
3. hint index 改为 strict int parser，malformed hint 统一 skip，不再因 telemetry 二次 int() 抛异常。
4. 增加 regression：不兼容 signature/order 排序的 2-slot 模型必须可解；malformed pose/ghost hint 必须 skip。
```

补丁文件：`/mnt/data/zmd_gm_r8.patch`。

## 验证记录

环境：Python 3.13 venv，离线安装 `zmd_py313_linux_x86_64.zip` 中的 wheels。

通过：

```text
/mnt/data/zmd_r8_venv/bin/python -m pytest -q -p no:randomly src/tests/test_solution_hint_malformed_defense.py src/tests/test_master.py::test_coordinate_symmetry_breaking_skips_incompatible_signature_order_slots
17 passed in 1.44s
```

通过：

```text
/mnt/data/zmd_r8_venv/bin/python -m pytest -q -p no:randomly src/tests/test_master.py src/tests/test_solution_hint_malformed_defense.py
243 passed in 11.36s
```

通过：

```text
/mnt/data/zmd_r8_venv/bin/python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored
```

全量 `src/tests` 尝试运行过一次，但沙盒时间墙在约 14% 处中断；中断前未打印 failure。最终声明以以上专项和影响面测试为准，未声称全量 2988 测试完成。
