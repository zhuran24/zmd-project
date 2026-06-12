# 终末地 IndustrialPlanner preprocess 链 round 12 审查报告

审查对象：`zmd_snapshot_37b84be0.zip`，sha256 已校验为 `37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd`，与题面一致。只解包并审查该快照，仓库根为 zip 内 `project/`。

冻结大件基线也先验过：`data/preprocessed/candidate_placements.json` 为 45,773,799 bytes，sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，与题面一致。

本轮结论：发现 1 个新的 preprocess soundness finding，编号建议 `F-PRE-R12-01`。它不是 R11 已修项重复，而是 R11-03 的 RHS/元数据闭包边界仍有一个 fail-open 漏洞。已给出补丁与回归。当前冻结 canonical 数据本身未触发该漏洞；补丁不要求再生冻结工件。

## Finding: F-PRE-R12-01 — cycle solver 接受非 net-export / 非 internal 的正外部需求，可能静默漏造循环机器

Severity: HIGH

位置：原始快照 `src/interchange/preprocess_context.py:288-295` 只校验 `cycle_internal` commodity 声明了已存在的 `cycle_group`，没有反向要求该 commodity 必须列入对应 group 的 `internal_commodities`。原始快照 `src/interchange/preprocess_context.py:436-445` 构造 RHS 时只遍历 `group.internal_commodities`，因此 `external_demands` 中不在 internal 列表里的正需求会被静默忽略；同时不在 `net_export_commodities` 中的 internal commodity 正需求也可被直接求解。

可复现 probe，在未打补丁的原始快照上执行：

```python
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import json
from src.interchange.preprocess_context import (
    build_preprocess_context_from_rules_and_plan,
    load_default_preprocess_context,
    solve_cycle_group_exact,
)
from src.preprocess.demand_solver import solve_demands_exact

root = Path('.')
rules = json.loads((root / 'rules/canonical_rules.json').read_text())
plan = json.loads((root / 'rules/preprocess_plan.json').read_text())
ctx = load_default_preprocess_context()

print('positive non-export internal:', solve_cycle_group_exact(
    ctx, 'buckwheat_cycle', {'buckwheat_seed': Fraction(1)}
))

mut = deepcopy(rules)
mut['commodity_metadata']['ghost_spore'] = {
    'source_kind': 'cycle_internal',
    'sink_kind': 'none',
    'cycle_group': 'buckwheat_cycle',
}
ctx2 = build_preprocess_context_from_rules_and_plan(mut, plan)
print('omitted cycle_internal accepted:', ctx2.commodity_roles['ghost_spore'])

mut2 = deepcopy(rules)
mut2['commodity_metadata']['ghost_spore'] = {
    'source_kind': 'cycle_internal',
    'sink_kind': 'none',
    'cycle_group': 'buckwheat_cycle',
}
mut2['recipes']['packaging_battery']['inputs']['ghost_spore'] = 1
ctx3 = build_preprocess_context_from_rules_and_plan(mut2, plan)
flows, machines = solve_demands_exact(ctx3)
print('ghost flow:', flows.get('ghost_spore'))
print('ghost-backed machines:', [key for key in machines if 'ghost' in key])
print('packaging_battery runs:', machines.get('packaging_battery'))
```

原始快照输出：

```text
positive non-export internal: {'planter_buckwheat': Fraction(1, 1), 'seed_collector_buckwheat': Fraction(1, 1)}
omitted cycle_internal accepted: CommodityRole(commodity_id='ghost_spore', source_kind='cycle_internal', sink_kind='none', cycle_group='buckwheat_cycle')
ghost flow: 3/5
ghost-backed machines: []
packaging_battery runs: 3
```

影响：R11-03 已证明每个 `net_export_commodities` 单位方向的非负基解，但求解入口仍允许正 RHS 不是 net-export 基向量的非负组合。更糟的是，若 canonical 增加一个 `cycle_internal` commodity 却漏列进 group `internal_commodities`，下游需求聚合可以产生正 flow，而 `_solve_cycle_group_exact()` 会因为只按 internal 列表取 RHS 而把该需求丢掉，生成缺少支撑机器的冻结需求/实例工件。这是 fail-open 方向。当前冻结 canonical 没有 `ghost_spore` 这类条目，所以现有冻结工件数值未受影响。

修法：

1. `validate_preprocess_context()` 建立 `cycle_group -> internal_commodities` 反向索引；每个 `source_kind == "cycle_internal"` 的 commodity 必须声明存在的 group，并且自身必须列入该 group 的 `internal_commodities`。非 cycle commodity 不允许携带 `cycle_group`。
2. `_solve_cycle_group_exact()` 先规范化 RHS：正需求 key 必须同时属于 `internal_commodities` 与 `net_export_commodities`；负需求直接 fail-closed；零需求 key 允许保留兼容既有测试里的显式零 RHS。
3. 保留原有解向量逐项负值 fail-closed，作为矩阵漂移的最后保险。

补丁后同类探针翻转为：

```text
positive non-export internal REJECTED: ValueError ... is not declared in net_export_commodities
positive unknown internal REJECTED: ValueError ... is not listed in internal_commodities
negative export REJECTED: ValueError ... must be non-negative
ghost role REJECTED: ValueError ... is not listed in that group's internal_commodities
zero non-export remains accepted: {'planter_buckwheat': Fraction(0, 1), 'seed_collector_buckwheat': Fraction(0, 1)}
```

回归：新增 `src/tests/test_preprocess_context.py:232-244`，覆盖 `cycle_internal` 元数据不在 group internal 列表时拒绝；新增 `src/tests/test_preprocess_cycle_solver.py:34-38`，覆盖正需求打到非 net-export internal commodity 时拒绝。

冻结工件条款：该修复只改代码与测试，不改 canonical rules、plan 或 `data/preprocessed/*`。无需再生冻结工件，无需登记新工件 hash。已重新确认 `candidate_placements.json` 仍为题面 hash/bytes。

## Q1: R11-01/02/03 修复确认

### R11-01: `load_templates()` schema 加载路径

确认结果：R11-01 的主修复成立。`src/placement/placement_generator.py:468-481` 的 `_load_canonical_rules_schema()` 用 strict JSON 读取 `rules/canonical_rules.schema.json`，`load_templates()` 在 strict-load canonical 后立刻 `validate_json_schema(instance=rules, schema=...)`，再返回 `rules["facility_templates"]`。

schema 自身缺失/损坏方向已实测 fail-closed：临时移走 schema 后 `load_templates()` 抛 `FileNotFoundError`；写入坏 JSON 后抛 `JSONDecodeError`。恢复后 schema sha256 为 `6dbf3926c0649a339a2dc46feb38c99dead2247c14f9f949b529da1147a5ba1f`。

全仓 `src/`/`scripts/` 扫描：候选摆位再生本体只在 `src/placement/placement_generator.py:526` 通过 `load_templates()` 取模板后 `generate_all_pools()`。`src/tests/test_preprocess_golden.py:86` 也是同一路径。存在若干 runtime/adaptor/cut/test 直接读 `rules['facility_templates']` 或 `.get('facility_templates')` 的点，但它们不是 placement generator 的 canonical 文件入口；certified master 的 proof 输入由自己的 strict loader 与 hash 闭包封住。未发现新的 candidate regeneration 绕过 `load_templates()` 的生产调用点。

### R11-02: `rotatable` / `is_solid_z` 几何 contract

独立对照 canonical 当前真值与 generator contract：

| template | canonical dims / rule | canonical rotatable | canonical is_solid_z | generator contract |
|---|---:|---:|---:|---|
| `manufacturing_3x3` | 3×3 / `opposite_parallel_sides` | True | True | square manufacturing，正交边对模式，要求 rotatable=True |
| `manufacturing_5x5` | 5×5 / `opposite_parallel_sides` | True | True | 同上，要求 rotatable=True |
| `manufacturing_6x4` | 6×4 / `long_sides` | True | True | 长边上下/旋转矩形，要求 w>h 且 rotatable=True |
| `protocol_core` | 9×9 / `core_specific` | True | True | emits o=0/o=1，要求 9×9、6 outputs/14 inputs、rotatable=True |
| `protocol_storage_box` | 3×3 / `omni_wireless` | True | True | 方形无线箱，pool 去重为 orientation 0，但 canonical 仍为 rotatable=True |
| `power_pole` | 2×2 / `none` | False | True | 单固定朝向，radius=5，要求 rotatable=False |
| `boundary_storage_port` | 1×3 / `inward_facing` | True | True | 左/下边界双族位姿，要求 placement_rule=`left_or_bottom_boundary` 且 rotatable=True |

对应守卫在 `src/placement/placement_generator.py:135-139` 强制 JSON boolean，`src/placement/placement_generator.py:161-277` 按 port_rule family 锁尺寸、rotatable、solid 与特殊字段。实测 `rotatable=1`、`rotatable="true"`、`is_solid_z=1`、`is_solid_z="true"` 都抛 `ValueError ... must be a boolean`，truthy 非 bool 没有被吞。

### R11-03: cycle 数学与本轮新增补强

当前 canonical 两个农业循环矩阵相同，行是 internal commodities，列是 recipes：

```text
A = [[ 1, -1],
     [-1,  2]]
```

`buckwheat_cycle` 的 internal 为 `('buckwheat', 'buckwheat_seed')`，net export 为 `('buckwheat',)`；`sandleaf_cycle` 同构。单位 net-export 解分别为：

```text
buckwheat=1  -> planter_buckwheat=2, seed_collector_buckwheat=1
sandleaf=1   -> planter_sandleaf=2, seed_collector_sandleaf=1
```

实际需求解为：

```text
buckwheat=11/2 -> planter_buckwheat=11, seed_collector_buckwheat=11/2
sandleaf=21/2 -> planter_sandleaf=21, seed_collector_sandleaf=21/2
```

线性论证在多 net-export 同组时成立：实现里的 `_solve_square_linear_system()` 使用 `Fraction` 做固定矩阵的 Gauss-Jordan 精确线性求解，没有 ceil、过滤或状态化分支；若 group 有多个 net-export，任意非负实际 RHS 都是各单位 RHS 的非负线性组合，解也就是单位解的同系数组合。R11 的单位基解证明足够覆盖“RHS 只来自 net-export 且非负”的前提。

本轮 finding 正是这个前提没有在 solver 入口强制。补丁后 `_solve_cycle_group_exact()` 在 `src/interchange/preprocess_context.py:450-475` 明确锁住：正 RHS key 必须是 internal 且 net-export；负 RHS 先拒绝；然后才在 `src/interchange/preprocess_context.py:477-488` 组矩阵 RHS。组合 RHS 若因 canonical drift 产生负 run rate，`src/interchange/preprocess_context.py:489-494` 的逐项负值检查仍兜底。singular 路径在 `src/interchange/preprocess_context.py:501-518` 先找 pivot，找不到直接抛 `cycle group matrix is singular...`，不会被误报成负解。

## Q2: 实例展开器本体审查

生成路径：`src/preprocess/instance_builder.py:48-70` 对 `machine_counts` 的 key 排序后生成制造实例，id 为 `{operation_type}_{index:03d}`；`src/preprocess/instance_builder.py:74-85` 固定一个 `protocol_core_001`；`src/preprocess/instance_builder.py:89-101` 固定 46 个 `boundary_port_001..046`。`power_pole` 与 `protocol_storage_box` 在 `EXPLORATORY_OPTIONAL_CAPS` 中是探索/pose-level optional，不在 `mandatory_exact_instances.json` 的 266 强制实例里。

数量保真重算：

| operation | fractional runs | ceil machines |
|---|---:|---:|
| `crusher_blue_iron` | 34 | 34 |
| `crusher_buckwheat` | 11/2 | 6 |
| `crusher_sandleaf` | 21/2 | 11 |
| `crusher_source` | 18 | 18 |
| `filling_capsule` | 11/4 | 3 |
| `grinder_dense_blue_iron` | 17 | 17 |
| `grinder_dense_source` | 9 | 9 |
| `grinder_fine_buckwheat` | 11/2 | 6 |
| `molding_bottle` | 11/2 | 6 |
| `packaging_battery` | 3 | 3 |
| `parts_maker` | 6 | 6 |
| `planter_buckwheat` | 11 | 11 |
| `planter_sandleaf` | 21 | 21 |
| `refinery_blue_iron` | 34 | 34 |
| `refinery_steel` | 17 | 17 |
| `seed_collector_buckwheat` | 11/2 | 6 |
| `seed_collector_sandleaf` | 21/2 | 11 |

制造实例合计 219；加 `protocol_core=1` 与 `boundary_io=46` 得 266。冻结 `machine_counts.json` 与重算完全一致；冻结 `mandatory_exact_instances.json` 中 operation count 也与 `machine_counts` 逐项一致。设施类型分布为 `manufacturing_3x3=132`、`manufacturing_5x5=49`、`manufacturing_6x4=38`、`protocol_core=1`、`boundary_storage_port=46`。

抽 5 个 operation profile，对照 canonical recipe 与 derived port profile：

| operation | facility_type | canonical recipe | derived rates / slots |
|---|---|---|---|
| `packaging_battery` | `manufacturing_6x4` | 5 ticks, in `dense_source_powder=15`, `steel_part=10`, out `valley_battery=1` | rates 3,2 -> input slots 3,2; output rate 1/5 -> output slot 1 |
| `filling_capsule` | `manufacturing_6x4` | 5 ticks, in `fine_buckwheat_powder=10`, `steel_bottle=10`, out `qiaoyu_capsule=1` | rates 2,2 -> input slots 2,2; output slot 1 |
| `parts_maker` | `manufacturing_3x3` | 1 tick, in `steel_block=1`, out `steel_part=1` | rate 1 -> one input slot and one output slot |
| `grinder_dense_source` | `manufacturing_6x4` | 1 tick, in `source_powder=2`, `sandleaf_powder=1`, out `dense_source_powder=1` | input slots 2,1; output slot 1 |
| `planter_buckwheat` | `manufacturing_5x5` | 1 tick, in `buckwheat_seed=1`, out `buckwheat=1` | one input slot and one output slot |

profile 来源没有第二张手写表：`src/preprocess/operation_profiles.py:59-78` 从 `PreprocessContext` recipes 派生 facility_type、input/output rates，再由 `_rate_to_slots()` 做 ceil slot。utility operation 则在 `src/preprocess/operation_profiles.py:80-89` 从 preprocess_plan 派生 generic slot。

实例 id 稳定性：`build_manufacturing_instances()` 对 `counts.items()` 排序，id 使用三位序号；固定 core 和 boundary port 也固定序号。用同一输入重生 mandatory list 与冻结文件语义完全一致。样例首尾：首批 `crusher_blue_iron_001..010`；最后制造类为 `seed_collector_sandleaf_009..011`；尾部固定 `boundary_port_042..046`。因此同输入 id 集合稳定，不会因 dict insertion order 漂移。

wireless/generic I/O 标注：`mandatory_exact_instances.json` 自身不携带 `routing_free` 字段，也没有 mandatory `wireless_sink`。generic output capacity 来自 46 个 boundary port 加 protocol core 6 个 output slot，`aggregate_port_slots(... mandatory_only=True)` 得 `generic_output_slots=52`，与 `generic_io_requirements.required_generic_outputs={"blue_iron_ore":34,"source_ore":18}` 相合。generic input requirement 为 `{"qiaoyu_capsule":1,"valley_battery":1}`；master 由 `src/models/master_model.py:2030-2055` 推出 `protocol_storage_box` lower bound：2 个 required slots / 每盒 3 slots => 1 个盒。binding 在 `src/models/binding_subproblem.py:757-795` 只为 `operation_type == "wireless_sink"` materialize `routing_free=True, virtual=True` 的 generic input slots；routing-free commodity 集来自 `required_generic_inputs` 的正需求，见 `src/models/binding_subproblem.py:369-373`。

## Q3: 冻结工件交叉一致性

### 交叉断言矩阵

| pair / invariant | 代码或测试检查点 | 状态 |
|---|---|---|
| canonical_rules ↔ preprocess_plan | `load_default_preprocess_context()` / `load_preprocess_context_from_paths()` schema validate；plan 对 recipes/targets/commodity_roles additive-only；`src/interchange/preprocess_context.py:240-348` 语义校验 | 有运行时/生成时检查 |
| context demand solve ↔ `commodity_demands` / `machine_counts` / `port_budget` / `generic_io` | `src/tests/test_preprocess_context.py:247-256` 重算并对比冻结；`src/tests/test_preprocess_golden.py:56-102` 全链语义再生对比 | 有测试检查，非 certified runtime 现场重算 |
| `machine_counts` ↔ `mandatory_exact_instances` | `src/preprocess/instance_builder.py:48-70` 展开；`src/tests/test_preprocess_golden.py:105-129` 逐 operation count 与 facility_type 对照 | 有生成/测试检查；runtime 不读 `machine_counts` |
| mandatory instance operation ↔ canonical recipe facility_type/profile | `build_template_mapping()` + `operation_profiles.py:59-78` 从 context 派生；`test_preprocess_golden.py:124` 检查 facility_type | 有测试检查 |
| `generic_io_requirements` ↔ canonical commodity roles | `src/models/binding_subproblem.py:249-305` 校验 generic outputs 必须 `source_kind=external_boundary`、generic inputs 必须 `sink_kind=generic_input`；master 在 `src/models/master_model.py:2006-2013` 委托同一 loader | 有 runtime 检查 |
| `generic_io_requirements` ↔ mandatory/core/boundary slot capacity | `src/tests/test_preprocess_golden.py:142-149` 锁 52 output slots、34/18 outputs、1/1 final inputs；binding output domain 在 `src/models/binding_subproblem.py:709-748` 从 boundary/core pose ports 建 slot | 有测试与 runtime容量建模；runtime 不从 flows 重推 generic_io |
| `mandatory_exact_instances` / `candidate_placements` / `canonical_rules` / `generic_io` / `preprocess_plan` ↔ exact campaign resume | hash closure 在 `src/search/exact_campaign.py:194-205` 覆盖 mandatory、candidate、canonical、generic_io、preprocess_plan | 有 hash closure |
| `candidate_placements` ↔ canonical geometry | `load_templates()` schema + `_validate_template_geometry_contract()`；placement tests 锁 pool keys/nonempty/边界基本性质；golden test 可重生候选语义对比但耗时 | 有生成时/测试检查 |
| `commodity_demands` ↔ certified exact runtime | 不在 `EXACT_HASH_FILES`；`load_project_data()` 只读 mandatory/candidate/canonical，见 `src/models/master_model.py:2174-2182` | 无 certified runtime 消费缝；仅 legacy/heuristic/flow diagnostic 读它 |

### 没有 runtime 交叉检查、主要依赖生成时序/测试的 pair

`machine_counts` 不在 exact hash closure，也不被 certified runtime 读取；它到 mandatory 的一致性靠生成器和测试锁。`port_budget` 不在 hash closure，且 `generate_generic_io_requirements()` 目前保留参数但在 `src/preprocess/demand_solver.py:179-180` 明确 `del port_budget`，因此 runtime 不消费它。`commodity_demands` 不在 hash closure；`src/search/benders_loop.py:2675-2680` 和 `src/search/heuristic_feasible_finder.py:229-256` 会读它，但这些是 legacy/heuristic/flow diagnostic 侧，不是当前 certified exact proof 输入。`all_facility_instances.json` 与 `exploratory_optional_caps.json` 不在 certified_exact 读取面；`load_project_data()` 在 `solve_mode == "certified_exact"` 时只读 mandatory。

mandatory ↔ generic_io 的推导一致性没有在 runtime 从 canonical flows 现场重算；runtime 校验的是 generic_io artifact 的结构、commodity role、hash 和 capacity建模。若人为只改 generic_io 并启动新 campaign，hash closure 会记录这组新 bytes，但不会证明它是由 demand solver 推导而来；这项由 preprocess parity tests / proof-obligation preflight 承担。当前这是设计边界，不构成本轮新 finding。

### 部分再生撕裂风险

只再生 `candidate_placements.json`：旧 campaign/resume 会被 hash mismatch 拦住；新 campaign 会以新 candidate bytes 为 proof universe。若不是通过 generator 而是手写 candidate，runtime 主要依赖结构使用与几何可行性，不会重跑完整 generator 等价证明；冻结 hash/preflight 和 placement tests 是防线。

只再生 `mandatory_exact_instances.json`：旧 campaign hash mismatch；新 campaign 会接受结构合法的 mandatory 文件，不现场对 `machine_counts` 重算。由于 `machine_counts` 不在 certified runtime 输入里，撕裂会被 preprocess golden/context tests 抓，而不是 runtime 抓。

只再生 `generic_io_requirements.json`：旧 campaign hash mismatch；new campaign 的 runtime 会校验 section、strict int、canonical roles，并据此建 generic slot/optional lower bound，但不会从 flows/port_budget 重推 34/18/1/1。撕裂由 preprocess tests 抓。

只再生 `machine_counts.json`、`port_budget.json` 或 `commodity_demands.json`：certified exact hash closure 不感知；但 certified exact 当前也不消费这些文件。它们的撕裂主要影响后续再生步骤、报告或 diagnostic。

### hash 闭包覆盖面

闭包内：

```text
mandatory_exact_instances -> data/preprocessed/mandatory_exact_instances.json
candidate_placements     -> data/preprocessed/candidate_placements.json
canonical_rules          -> rules/canonical_rules.json
generic_io_requirements  -> data/preprocessed/generic_io_requirements.json
preprocess_plan          -> rules/preprocess_plan.json  (optional exact hash file, present here)
```

闭包外：`machine_counts.json`、`port_budget.json`、`commodity_demands.json`、`all_facility_instances.json`、`exploratory_optional_caps.json`、preprocess context diff/report artifacts。对 Q3③ 的缝隙确认：未发现 `commodity_demands.json` 被当前 certified exact `load_project_data()` / `ExactSearchSession` proof surface 消费；因此没有“在 hash 闭包外却进入 certified 证明路径”的新 finding。

## 执行过的验证

```text
python3.13 -m pytest -q src/tests/test_preprocess_context.py src/tests/test_preprocess_cycle_solver.py -p no:randomly
# 21 passed in 1.10s

python3.13 -m pytest -q \
  src/tests/test_preprocess_golden.py::test_regenerated_instance_distribution_matches_machine_counts \
  src/tests/test_preprocess_golden.py::test_regenerated_preprocess_invariants_match_current_frozen_contract \
  src/tests/test_preprocess_golden.py::test_frozen_preprocess_artifacts_are_cleanly_serialized_without_binary_noise \
  src/tests/test_placements.py::test_placement_template_loader_rejects_duplicate_json_keys \
  src/tests/test_placements.py::test_placement_template_loader_rejects_nonfinite_json_constants \
  src/tests/test_placements.py::test_placement_template_loader_rejects_overflow_json_numbers \
  src/tests/test_placements.py::test_placement_template_loader_rejects_schema_missing_required_template_field \
  src/tests/test_placements.py::test_pool_keys_match_canonical \
  src/tests/test_placements.py::test_all_pools_nonempty \
  -p no:randomly
# 9 passed in 2.86s

python3.13 scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

尝试跑包含 `test_preprocess_chain_regenerates_frozen_artifacts_from_source_code` 的更宽 preprocess/placement 组合时，candidate placement 再生相关测试未在 600 秒内完成；该次不能计为通过。未跑完全量 `src/tests`，因此全量约 2988 的绿灯我不声称。

## 补丁摘要

修改文件：

```text
src/interchange/preprocess_context.py
src/tests/test_preprocess_context.py
src/tests/test_preprocess_cycle_solver.py
```

补丁不触碰冻结 JSON 工件，不触碰登记 hash。候选文件仍为：

```text
data/preprocessed/candidate_placements.json
bytes  = 45773799
sha256 = adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
```
