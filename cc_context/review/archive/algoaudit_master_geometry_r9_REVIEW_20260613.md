# 终末地 IndustrialPlanner 几何 master round 9 审查报告

快照确认：`/mnt/data/zmd_snapshot_095a0b6d.zip` 的 sha256 已校验为 `095a0b6d5f7d4496f3ef99fb71f2c6873555b10324c045b5b78ef91cc85f5eda`，与任务指定值一致后才解包审查。

结论：**本轮零 soundness finding**。F-GM-R8-SYM-01 的同序门卫在本轮审查中确认 sound；`order_key` 单标尺保代表性成立；`protocol_storage_box` 的 543 条 residual signature 单调约束确认来自全集同序而非误判。另发现并修复 1 个 **LOW / non-soundness** 的 HINT-02 strictness 残留：部分 hint ingress 在 coordinate delegate 之前仍使用裸 `int()`，会把 float/bool/string 截断或转成整数后进入 hint。

## Finding

### LOW: HINT strict-int parser 未覆盖 community / legacy / pose-bool hint 入口

位置：pre-patch `src/search/benders_loop.py:4174-4185`、`src/models/master_model.py:11314-11323`、`src/models/pose_bool_exact_master.py:979-981`、`src/tests/test_community_hint_env_injection.py:132-143`。

问题：`CoordinateExactMasterDelegate.apply_solution_hint()` 已经用 `type(value) is int` 口径拒绝 bool、float、numeric string；但 certified exact 的 community blueprint hint 合并在进入 master 前仍执行 `int(pose_idx)`，legacy `MasterPlacementModel.solve()` fallback 也执行 `int(pose_idx)`，pose-bool exact delegate 的 hint 入口也直接 `int(pose_idx)`。因此 `3.14 -> 3`、`True -> 1`、`"0" -> 0` 这类值可以绕过 downstream strict parser。现有 community hint 单测还在断言这个错误行为：`d == 3`、`e == 1`。

影响：这是 hint-only 路径，`AddHint` 只影响 CP-SAT 搜索引导，不添加约束，不改变可行域、最优性或 proof；因此不是 soundness finding。但它违反 F-GM-R8-HINT-02 的“全链 strict-int parser / bool 显式拒绝 / 无二次裸 int()”修复确认目标，并会污染 hinted literal telemetry。

修法：新增共享 helper `src/models/solution_hint_parser.py:14-19`，只接受 `type(value) is int`；`src/models/exact_coordinate_master.py:40,6781-6783` 改为复用同一 parser；`src/search/benders_loop.py:87,4175-4185,4196-4199,4447-4452`、`src/models/master_model.py:77,11315-11322`、`src/models/pose_bool_exact_master.py:26,980-986` 全部改走共享 parser。回归更新 `src/tests/test_community_hint_env_injection.py:15,53-63,133-144`，并扩展 `src/tests/test_solution_hint_malformed_defense.py:121-145` 覆盖 legacy float/bool/string 和 parser 本体。

补丁：见 `r9_hint_strict_parser.patch`。

## Q1: F-GM-R8-SYM-01 修复确认

### 同序门卫量化范围

`_add_signature_monotonic_constraints_if_compatible()` 在 `src/models/exact_coordinate_master.py:2579-2613` 中构造 `pose_signature_int_by_idx`，再对同一 slot family 的每个 slot 调 `_signature_order_is_compatible_with_slot_order()`。比较器使用的 pose 集来自 `_slot_signature_order_pose_indices()`，该函数在 `src/models/exact_coordinate_master.py:2522-2534` 中优先遍历 `slot.allowed_tuples`，再用同一个 `tuple_to_pose_idx` 反查 pose index；因此门卫检查的是 slot 实际域，而不是随意的子集。signature int 来自 `_pose_signature_int_by_bucket_defs()`，位于 `src/models/exact_coordinate_master.py:2536-2551`，和后续 signature 变量使用同一组 bucket_defs。

Mandatory group：slot 的 `allowed_tuples` 在 `src/models/exact_coordinate_master.py:2251-2269` 由 `owner._candidate_pose_indices_for_group(group)` 构造；signature map 在 `src/models/exact_coordinate_master.py:1920-1938` 用同一个 candidate set 构造并过滤；门卫在 `src/models/exact_coordinate_master.py:3563-3578` 传入的也是 `owner._candidate_pose_indices_for_group(group)`。约束作用域是同一个 `mandatory_slots[group_id]`，slot 之间只有 key / slot_index 标签差异，没有 slot-index 特化域。数据 probe 未发现 mandatory set mismatch；真实数据中 1 个 mandatory group 同序并加 45 条 signature 单调，17 个 mandatory group 不同序并安全跳过 202 条 signature 单调。

Required optional：slot 的 `allowed_tuples` 在 `src/models/exact_coordinate_master.py:2275-2295` 取模板全部 pose tuple；signature map 在 `src/models/exact_coordinate_master.py:1948-1967` 用 `range(len(facility_pools[tpl]))`；门卫在 `src/models/exact_coordinate_master.py:3581-3597` 同样传入全 pool range。当前快照 `_exact_required_pose_optional_counts == {}`，因此实数据没有 required_optional slot family；代码路径由专项回归 `test_coordinate_symmetry_breaking_orders_required_optional_signature_slots` 覆盖。

Residual `protocol_storage_box`：residual signature buckets 在 `src/models/exact_coordinate_master.py:1977-2019` 对模板全 pool 构造；slot 的 `allowed_tuples` 在 `src/models/exact_coordinate_master.py:2299-2335` 取模板全部 pose tuple；signature slot 创建在 `src/models/exact_coordinate_master.py:2964-2980`；门卫在 `src/models/exact_coordinate_master.py:3606-3624` 传入 `range(len(facility_pools[tpl]))`。probe 结果：`slots=544`、`poses=4624`、`buckets=1`、`compatible=True`、`drops=0`，因此 543 条 signature 单调约束等于 `544 - 1`，是全集同序的直接结果。

覆盖完整性：`_build_bucket_regions()` 在 `src/models/exact_coordinate_master.py:1705-1764` 对 allowed pose 集检查 bucket 覆盖，漏 pose 会 `ValueError` fail-closed；所以 `_signature_order_is_compatible_with_slot_order()` 中对缺 signature 的防御性 skip 在正常 build 路径下不会把“缺一块的子集”误判为同序。

### `order_key` 单标尺保代表性

`order_key` 定义在 `src/models/exact_coordinate_master.py:2501-2520`：`scale_x = grid_h * mode_count`、`scale_y = mode_count`，因此 key 为 `x * grid_h * mode_count + y * mode_count + mode`。在合法域 `0 <= y < grid_h`、`0 <= mode < mode_count` 上可唯一反解：`mode = key % mode_count`，`y = (key // mode_count) % grid_h`，`x = key // (grid_h * mode_count)`。所以它是 `(x, y, mode)` 的注入式 total order；即使 CP-SAT 的 `<=` 本身能容忍碰撞，真实候选集 probe 也确认 `order_key_collision_count = 0`、`order_key_out_of_bounds_count = 0`。

保代表性论证：mandatory / required_optional 同族 slots 在创建时共享同一 `allowed_tuples`、同一 domains、同一 bucket/signature 语义；其它约束按 slot 集合求和、NoOverlap 或覆盖计数，不给“第一个 slot”额外语义。因此任何可行多重集都能按 `order_key` 排序后重新分配给同构 slots，保持可行性和目标不变。residual optional 另有 `active` 前缀约束，`src/models/exact_coordinate_master.py:3035-3039` 保证活跃 slot 在前；把活跃 pose 按 `order_key` 排序、非活跃 slot 放在后面仍保持同一多重集。非活跃 residual signature 值设为 sentinel `len(bucket_defs)`，见 `src/models/exact_coordinate_master.py:2784-2812`，并由 `sum(bucket_lits) == slot.active` channel，见 `src/models/exact_coordinate_master.py:2855-2858`；所以未 guard 的 `left.signature <= right.signature` 不会因为 inactive slot 删除代表解。

### 同序门卫比较器与约束值同源

比较器调用 `_slot_order_key_for_pose_tuple()`，与建模时 `slot.order_key == slot.x * scale_x + slot.y * scale_y + slot.mode` 的公式同源；signature int 来自同一 `bucket_defs` 枚举顺序。空族或单 slot family 在 `_add_signature_monotonic_constraints_if_compatible()` 早退，不加约束也不记跳过。门卫若发现任一 slot 的 signature 不是按 order_key 非降，就整族跳过 signature 单调，只保留 order_key 单标尺；telemetry 计数增加 `len(slots)-1`，不参与 proof。

### `protocol_storage_box` 543 条 signature 单调独立抽查

数据级 probe：

```text
required_counts {}
order_key_collision_count 0
order_key_out_of_bounds_count 0
candidate_set_mismatches []
compat_counter {('mandatory', True): 1, ('mandatory', False): 17, ('residual_optional', True): 1}
residual_protocol_storage_box {'slots': 544, 'poses': 4624, 'buckets': 1, 'compatible': True, 'drops': 0, 'constraints_expected': 543}
coordinate_symmetry {'enabled': True, 'mandatory_signature_monotonic_constraints': 45, 'required_optional_signature_monotonic_constraints': 0, 'residual_optional_signature_monotonic_constraints': 543, 'mandatory_signature_monotonic_skipped_incompatible_order': 202, 'required_optional_signature_monotonic_skipped_incompatible_order': 0, 'residual_optional_signature_monotonic_skipped_incompatible_order': 0, 'slot_order_key_monotonic_constraints': 790, 'power_pole_family_order_constraints': 762}
```

这说明 residual `protocol_storage_box` 的门卫输入和 slot 域同为 4624 个 pose，signature 序列无下降，543 条约束不是误判漏集。

### power_pole family 排序

`power_pole` 不走 signature monotonic 门卫。family 由每个 pole pose 的 power capacity coefficient signature 分组，见 `src/models/exact_coordinate_master.py:2134-2154`；residual pole slots 在 `src/models/exact_coordinate_master.py:3379-3389` 约束 `left.active >= right.active`、`left.family <= right.family`，并且只在 `same_family` 时约束 `left.order_key <= right.order_key`。这不是 SYM-01 中的“双 total order”；它等价于对同构 residual pole slot 按一个复合 key 排序：active prefix，然后 family，再同 family 内的 order_key。inactive slot 使用 sentinel family，见 `src/models/exact_coordinate_master.py:3294-3309,3365`，因此 inactive 永远排在 active 之后，同 family inactive 的 order_key 也被固定在默认 anchor。任意 residual pole 多重集都可按 `(family, order_key)` 排序后赋给相同 slot 集，family count、coverage witness 和目标不变。专项回归 `test_exact_search_guidance_orders_residual_power_poles_by_family` 通过，实数据 build telemetry 为 `power_pole_family_order_constraints = 762`。

## Q2: F-GM-R8-HINT-02 修复确认

修补后，所有本轮审计到的 hint 值入口都走共享 strict parser：coordinate mandatory / optional / ghost anchor 入口复用 `parse_strict_int_hint_value()`；community blueprint merge、legacy solve fallback、pose-bool exact delegate 也改为同一 parser。bool 因为 `type(value) is int` 被拒绝；float 和 numeric string 不再截断。`benders_loop` 对 warm-start ghost anchor 和 last_solve ghost anchor 回写也不再二次裸 `int()`；telemetry 中对 count 字段的 `int()` 保留，因为它们不是 hint pose/anchor value。

## Q3: 自由攻击角

攻击角 A：signature domain payload cache 是否可能因 cache key 未包含 bucket_defs 而复用错桶。检查发现 bucket payload 本身由 `MasterPlacementModel._build_signature_bucket_payload()` 按 `(tpl, pose_indices)` 唯一生成，见 `src/models/master_model.py:4359-4402`；mandatory / required optional seed 在 `src/models/master_model.py:4414-4431` 也只依赖 template pose local signature。coordinate side 的 `_signature_domain_payload()` cache key 同样是 `(tpl, allowed_pose_indices)`，见 `src/models/exact_coordinate_master.py:1837-1897`。因此“同 tpl + 同 allowed set + 不同 bucket_defs”的攻击前提在当前代码中不存在；probe 的 `candidate_set_mismatches []` 也确认门卫域与 slot 域没有漂移。

攻击角 B：residual optional signature monotonic 是否因 inactive sentinel 或 telemetry skip 逻辑引入新缝。`_create_optional_signature_slot_vars()` 将 inactive signature 固定为最大 sentinel，并通过 `sum(bucket_lits) == slot.active` 保证 active slot 恰好落入一个真实 bucket；active prefix 约束禁止 inactive 出现在 active 前面。因此 signature 单调在 active-active 上是真实同序剪枝，在 active-inactive 上是 `real <= sentinel`，在 inactive-inactive 上是 `sentinel <= sentinel`。skip telemetry 只记录被跳过的 adjacent signature 约束数，不被其它 proof 使用。结论：无 finding。

## 自验

执行过的命令与结果：

```bash
sha256sum /mnt/data/zmd_snapshot_095a0b6d.zip
# 095a0b6d5f7d4496f3ef99fb71f2c6873555b10324c045b5b78ef91cc85f5eda

PYTHONPATH=. python3.13 /mnt/data/zmd_r9_review/geometry_master_r9_sym_probe.py
# 输出见上方 protocol_storage_box / coordinate_symmetry probe 摘要

python3.13 -m pytest -q -p no:randomly \
  src/tests/test_solution_hint_malformed_defense.py \
  src/tests/test_community_hint_env_injection.py
# 33 passed in 1.49s

python3.13 -m pytest -q -p no:randomly \
  src/tests/test_master.py::test_coordinate_symmetry_breaking_orders_mandatory_signature_slots \
  src/tests/test_master.py::test_coordinate_symmetry_breaking_skips_incompatible_signature_order_slots \
  src/tests/test_master.py::test_coordinate_symmetry_breaking_orders_required_optional_signature_slots \
  src/tests/test_master.py::test_coordinate_symmetry_breaking_orders_residual_optional_signature_slots \
  src/tests/test_master.py::test_exact_search_guidance_orders_residual_power_poles_by_family
# 5 passed in 2.24s

python3.13 scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

全量 `python3.13 -m pytest -q -p no:randomly src/tests` 曾尝试运行，但在 900 秒沙盒超时前只推进到约 13%，此前未见失败；因此本轮以 scoped regression + proof-obligation + 数据 probe 为准。
