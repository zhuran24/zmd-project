# 终末地 IndustrialPlanner preprocess 面 round 6 审查报告

日期：2026-06-12  
范围：preprocess 面非 wireless 主线，覆盖 Q1 demand/IO 推导、Q2 非 wireless candidate 池、Q3 operation profile/canonical 投影、Q4 冻结与 hash 纪律、Q5 三件预处理工件一致性。P1.3B、exploratory、adapter/render/export 未审。

## 0. 开工校验

`/mnt/data/zmd_v80_impl_full_20260612_single.zip` sha256 已先验校验通过：

```text
e676c94dcc8477d087c916299486bea08c0d5a23dfd31d20b2c4c5842684fa52  /mnt/data/zmd_v80_impl_full_20260612_single.zip
```

依赖包使用 `/mnt/data/zmd_py313_linux_x86_64.zip` 解包后的本地 wheels 离线安装，Python 版本为 3.13。

## 1. Finding

### R6-F-01 — High — `preprocess_plan.json` 可改变运行时 profile，却未纳入 exact artifact hash；同时 plan 可静默覆盖 canonical recipe/target/commodity 元数据

受影响位置（原始快照行号）：

- `src/interchange/preprocess_context.py:172-183`：`build_preprocess_context_from_rules_and_plan()` 使用 `_merge_overlay()` 把 `preprocess_plan.json` 中的 `recipes` / `production_targets` / `commodity_roles` 覆盖到 canonical 上。
- `src/preprocess/operation_profiles.py:17,59-96`：运行时 `OPERATION_PORT_PROFILES` 由 `load_default_preprocess_context()` 派生，因此会消费上述 plan overlay。
- `src/models/binding_subproblem.py:57-91,568-595`：binding 侧也会在运行时直接读取 `rules/preprocess_plan.json` 中的 utility slot 配置。
- `src/search/exact_campaign.py:192-197,267-271`：`EXACT_HASH_FILES` 只覆盖 `mandatory_exact_instances`、`candidate_placements`、`canonical_rules`、`generic_io_requirements`，未覆盖 `rules/preprocess_plan.json`。

风险：certified runtime 的端口 profile/utility slot 语义会随 `preprocess_plan.json` 改变，但 campaign resume / certified surface stale-artifact 检查看不到该变化。更糟的是 schema 允许 plan 携带 recipe/target/commodity 覆盖，preprocess context 会静默偏向 plan。这样可以在 canonical hash、candidate hash、mandatory hash、generic IO hash 全部不变的情况下改变 recipe 的端口槽需求。例如把 `packaging_battery` 的 `dense_source_powder` 输入量从 canonical 的 15 改为 5，会让运行时 `input_slots['dense_source_powder']` 从 3 变成 1，形成相对 canonical 的欠约束，存在 false-CERTIFIED 风险。

复现 probe（补丁前）：

```text
profile_before {'dense_source_powder': 3, 'steel_part': 2} {'valley_battery': 1}
profile_after_overlay {'dense_source_powder': 1, 'steel_part': 2} {'valley_battery': 1}
hash_keys ['candidate_placements', 'canonical_rules', 'generic_io_requirements', 'mandatory_exact_instances']
preprocess_plan_hashed False
hashes_equal_after_plan_mutation True
```

修复：

1. `src/interchange/preprocess_context.py` 改为 fail-closed：`preprocess_plan.json` 只允许作为 cycle groups 与 utility operations 的 additive plan。出现 `recipes`、`production_targets`、`commodity_roles` 任一键即拒绝，recipe/target/commodity 三类事实只从 `canonical_rules.json` 派生。
2. `rules/preprocess_plan.schema.json` 同步收紧，移除 canonical 元数据 override 字段，保持 schema 与代码契约一致。
3. `src/search/exact_campaign.py` 在 `compute_exact_artifact_hashes()` 中将 `rules/preprocess_plan.json` 纳入 hash 集合；对没有该文件的极小 synthetic test project 记录 missing sentinel，避免打破旧测试桩，同时真实项目中的 plan 修改会触发 hash mismatch。
4. 新增回归：`src/tests/test_preprocess_plan_exact_hash.py` 验证 plan 修改会改变 exact hashes；`src/tests/test_preprocess_context.py` 增加 canonical metadata override 拒绝测试。

补丁后验证 probe：

```text
overlay_rejected True preprocess_plan.json must be additive-only; canonical recipe/target/commodity metadata overrides are not allowed: recipes
preprocess_plan_hashed True
preprocess_plan_hash_changed True
```

## 2. 其余复核结论

除 R6-F-01 外，本轮未发现新的 soundness finding。

### Q1 demand / IO 推导数学

复核链路：`src/preprocess/demand_solver.py`、`src/interchange/preprocess_context.py`、`data/preprocessed/commodity_demands.json`、`machine_counts.json`、`port_budget.json`、`generic_io_requirements.json`、`mandatory_exact_instances.json`。

实测再生结果与 frozen artifact 逐字/语义一致。`solve_demands_exact()` 使用 `Fraction`，`equivalent_full_speed_lines` 先转成目标 recipe 输出速率，再反推上游；cycle group 用精确线性方程解。当前强制制造实例数为 219，叠加 1 个 protocol core 与 46 个 boundary storage port 后正好 266。

关键数值：

```text
ceil_machine_instances 219
mandatory_instances 266
required_generic_outputs {'blue_iron_ore': 34, 'source_ore': 18}
required_generic_inputs {'qiaoyu_capsule': 1, 'valley_battery': 1}
generic_output_slots_available_required 52
```

`required_generic_outputs` 与 binding 侧的强制 generic output 槽数一致：46 个 boundary port 槽 + protocol core 6 个 output 槽 = 52，刚好覆盖 `blue_iron_ore 34 + source_ore 18`。`required_generic_inputs` 的计数语义为每种 final commodity 一个 generic sink 槽，当前 `qiaoyu_capsule` 与 `valley_battery` 各 1；binding 侧允许 sink capacity surplus 通过 `__unused__` 吸收，不构成过约束。

取整位置复核：machine count 与 external generic output count 均使用向上取整，方向为保守；当前关键流量均为整数，未触发 fractional 边界缝。

### Q2 candidate 池生成，非 wireless/辅助设施

复核链路：`src/placement/placement_generator.py`、`rules/canonical_rules.json` facility templates、`data/preprocessed/candidate_placements.json`。

再生命令：

```text
python3.13 src/placement/placement_generator.py
sha256sum data/preprocessed/candidate_placements.json
```

结果：

```text
adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0  data/preprocessed/candidate_placements.json
45773799 bytes
```

候选池规模与公式枚举一致：

```text
manufacturing_3x3       17408
manufacturing_5x5       16368
manufacturing_6x4       16380
protocol_core            6728
protocol_storage_box     4624
power_pole               4761
boundary_storage_port     134
total                   66403
```

probe 覆盖项：每个 pose 的 `occupied_cells` 在 70×70 内且面积等于模板尺寸；manufacturing/core 的 port cell 不落在自身 body；所有 input/output port 的 `front = port + dir` 均在网格内；port cell 无重复；power pole coverage cell 全部在网格内；每个 exact recipe 的 input/output slot 总数均不超过其 facility template 任一 pose 的端口容量。`is_edge_starved` 过滤只剔除了 front 全部越界的边，未观察到错杀合法 pose 的证据。

### Q3 operation profiles 与 canonical 投影

复核链路：`src/preprocess/operation_profiles.py`、`src/interchange/preprocess_context.py`、`rules/canonical_rules.json` 17 个 recipe、`rules/preprocess_plan.json` utility operations。

对 17 个 recipe 逐项检查：`OperationPortProfile.input_rates/output_rates == amount / ticks_per_cycle`；slot 数为 `ceil(rate / belt_capacity_per_tick)`，当前 belt capacity 为 1。所有 mandatory instance 的 `operation_type` 均可在 profile 表中解析；所有 profile 的 `facility_type` 均存在于 candidate pool。

本轮 finding 已把 plan 对 canonical recipe/target/commodity 的覆盖关掉，并把 plan hash 纳入 checkpoint，因此 profile 投影不再有静默冲突入口。

### Q4 确定性与冻结纪律

`candidate_placements.json` 再生 hash 与登记前缀和完整值一致，未发现 set/dict 非确定性导致的输出漂移。生成器主要使用排序后的模板/recipe key 或 JSON 插入序，当前 frozen artifact 可 bit 级再生。

stale artifact hash 方面，原有 `sha256_file()` 已拒绝缺失、symlink component、非 regular file；resume 校验使用完整 `artifact_hashes` dict 等值比较。R6-F-01 修复后，`preprocess_plan.json` 也进入该 dict，plan 改动会触发 `artifact_hash_mismatch`。

### Q5 三件预处理工件一致性

复核链路：`candidate_placements.json`、`mandatory_exact_instances.json`、`generic_io_requirements.json`、`binding_subproblem` 池化绑定数学。

probe 检查：266 个 mandatory instance 的 `facility_type` 均在 placement pool 中；`operation_type` 均在 operation profiles 中；制造 operation 计数与 `machine_counts.json` 一致；46 个 `boundary_io` 与 1 个 `protocol_core` 提供的 generic output slot 总数正好等于 `generic_io_requirements.required_generic_outputs` 总数 52；generic input commodity 均来自 canonical final target/role 定义。

## 3. 自验记录

通过：

```text
PYTHONPATH=. python3.13 /tmp/r6_audit_probe.py
# R6_AUDIT_PROBE_OK

PYTHONPATH=. python3.13 /tmp/r6_plan_hash_probe_fixed.py
# overlay_rejected True
# preprocess_plan_hashed True
# preprocess_plan_hash_changed True

python3.13 scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

python3.13 -m pytest -q -p no:randomly src/tests/test_preprocess_context.py src/tests/test_preprocess_plan_schema.py src/tests/test_preprocess_plan_exact_hash.py
# 11 passed

python3.13 -m pytest -q -p no:randomly \
  src/tests/test_exact_campaign_inspector.py::test_v74_certified_surface_recomputes_exact_hashes_even_when_caller_claims_resume_ok \
  src/tests/test_wireless_sink_binding_semantics.py::test_campaign_resume_rejects_stale_candidate_placement_hash \
  src/tests/test_v84_terminal_layout_max_empty_rect.py \
  src/tests/test_v85_terminal_required_optionals.py \
  src/tests/test_v88_terminal_ghost_anchor_required.py
# 11 passed

python3.13 -m pytest -q -p no:randomly \
  src/tests/test_preprocess_golden.py::test_regenerated_instance_distribution_matches_machine_counts \
  src/tests/test_preprocess_golden.py::test_regenerated_preprocess_invariants_match_current_frozen_contract \
  src/tests/test_preprocess_golden.py::test_frozen_preprocess_artifacts_are_cleanly_serialized_without_binary_noise \
  src/tests/test_binding.py \
  src/tests/test_wireless_front_consumers_r4.py
# 21 passed

python3.13 -m pytest -q -p no:randomly src/tests/test_cut_provenance.py
# 35 passed

python3.13 -m pytest -q -p no:randomly \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/test_v83_certified_surface_soundness.py \
  src/tests/test_v84_terminal_layout_max_empty_rect.py \
  src/tests/test_v85_terminal_required_optionals.py \
  src/tests/test_v86_terminal_power_witness_validation.py \
  src/tests/test_v87_terminal_power_pole_irredundancy.py \
  src/tests/test_v88_terminal_ghost_anchor_required.py \
  src/tests/test_v94_terminal_protocol_storage_surplus_validation.py \
  src/tests/test_v95_terminal_optional_metadata_validation.py
# 44 passed
```

说明：直接运行 pytest 时，环境中的 `pytest-randomly`/numpy seed hook 在一个用例 setup/teardown 触发 `ValueError: Seed must be between 0 and 2**32 - 1`，因此自验命令使用 `-p no:randomly`。未宣称完成 `python3.13 -m pytest -q src/tests` 全量；一次包含 `test_preprocess_golden.py::test_preprocess_chain_regenerates_frozen_artifacts_from_source_code` 的组合跑法在 45MB candidate artifact 语义 diff 阶段超时，故用直接再生 hash 与专项 probe 覆盖 candidate determinism。

## 4. 补丁

补丁文件：`zmd_preprocess_r6_plan_hash_overlay_fix.patch`  
patch dry-run：在原始快照重新解包目录中执行 `patch --dry-run -p1 < zmd_preprocess_r6_plan_hash_overlay_fix.patch` 通过。
