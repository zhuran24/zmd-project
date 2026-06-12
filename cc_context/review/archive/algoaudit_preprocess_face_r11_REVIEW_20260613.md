# preprocess 链面 round 11 审查报告

快照入口：`/mnt/data/zmd_snapshot_3f4ceebb.zip`

sha256 校验：`3f4ceebb5606d2d2b054b5af82899202fc1dcdae8cee9c97626bbaf57b8e58b9`，与任务给定值一致后解包审查。仓库根为 zip 内 `project/`。

结论：本轮发现 3 个 soundness finding，均已附补丁与回归。未修改 `rules/canonical_rules.json`，Q3 只做投影保真审计。

## Finding F-PRE-R11-01: placement_generator 有第三个 canonical 文件入口，只 strict-load 不 schema validate

Severity: High

位置：

- 原代码：`src/placement/placement_generator.py:405-411`
- 修复后：`src/placement/placement_generator.py:468-481`
- 回归：`src/tests/test_placements.py:118-130`

问题：R10 对 `src/interchange/preprocess_context.py` 的两个入口已经在 strict JSON 后、defaults 前运行 schema 校验：`load_default_preprocess_context()` 与 `load_preprocess_context_from_paths()` 分别在 `src/interchange/preprocess_context.py:389-405` 进入 `_validate_preprocess_source_schemas()`。全仓 `src/` 与 `scripts/` 扫描后，未发现第三个 strict-load 规则 + 构造 `PreprocessContext` 的入口；`scripts/build_current_preprocess_context.py` 也经由 `load_preprocess_context_from_paths()`。但是 placement generator 自己的 `load_templates()` 是独立 canonical 文件入口，原来只调用 `load_strict_json(rules_path)` 后直接返回 `rules["facility_templates"]`。这意味着 schema-required 字段缺失可以绕过 schema 守卫进入候选摆位再生链。

可复现 probe：在未修复代码上，删除 `facility_templates.manufacturing_3x3.rotatable` 后写入临时 `canonical_rules.json`，调用 `load_templates(tmp_rules)`，函数会正常返回模板，且返回对象中确实缺失 `rotatable`；schema-required 字段被吞掉。

修复：`placement_generator.py` 新增 `_load_canonical_rules_schema()`，在 `load_templates()` strict-load 后立即使用 `canonical_rules.schema.json` 做 schema 校验，再返回 `facility_templates`。回归测试删除 `manufacturing_3x3.rotatable`，现在预期抛 `jsonschema.ValidationError`。

## Finding F-PRE-R11-02: template geometry contract 漏锁 rotatable 与 is_solid_z，schema-valid 漂移可让 canonical 与 pose 语义分叉

Severity: High

位置：

- 原代码：`src/placement/placement_generator.py:142-215`
- 修复后：`src/placement/placement_generator.py:135-276`
- 回归：`src/tests/test_preprocess_candidate_geometry_contract.py:25-81`

问题：R10 的 `_validate_template_geometry_contract()` 已锁 `dimensions`、`core_limits`、`power_coverage_radius`、`placement_rule` 等字段，但未覆盖 generator 实际消费或隐含假设的完整字段集。

实测 probe：在未修复代码上，把 schema-valid 的 `manufacturing_6x4.rotatable` 改为 `false`，然后调用 `generate_all_pools({"manufacturing_6x4": mutated})`。generator 仍会生成 `orientation` 为 `[0, 1]` 的候选，且 o=1 为 4x6 rotated footprint。类似地，`protocol_core.rotatable=false` 仍会生成 o=1 核心端口拓扑，`boundary_storage_port.rotatable=false` 仍会生成 bottom-base 横向 3x1 位姿。另一个漏项是 `is_solid_z`：所有 generator 都无条件输出 `occupied_cells`，因此隐含假设模板本体为 solid；若 schema-valid 地把 `is_solid_z=false`，候选域仍按 solid 阻塞体生成。

字段覆盖矩阵：

| 模板族 | generator | 实际读/隐含假设 | 修复后 contract |
|---|---|---|---|
| `long_sides` / `manufacturing_6x4` | `gen_rect_manufacturing()` | `dimensions.w > dimensions.h`，`port_rule`，`rotatable=True`，`is_solid_z=True` | 全部锁定 |
| `opposite_parallel_sides` / `manufacturing_3x3, manufacturing_5x5` | `gen_square_manufacturing()` | `dimensions.w == dimensions.h`，`port_rule`，四向 side-pair modes 需要 canonical rotatable，`is_solid_z=True` | 全部锁定 |
| `core_specific` / `protocol_core` | `gen_protocol_core()` | 9x9、`core_limits=6/14`、`rotatable=True`、`is_solid_z=True` | 全部锁定 |
| `omni_wireless` / `protocol_storage_box` | `gen_protocol_storage_box()` | 3x3、canonical rotatable square body 被 orientation-dedup，`is_solid_z=True` | 全部锁定 |
| `none` / `power_pole` | `gen_power_pole()` | 2x2、`power_coverage_radius=5`、`rotatable=False`、`is_solid_z=True` | 全部锁定 |
| `inward_facing` / `boundary_storage_port` | `gen_boundary_ports()` | 1x3、`placement_rule=left_or_bottom_boundary`、`rotatable=True`、`is_solid_z=True` | 全部锁定 |

`needs_power` 未纳入 placement contract：placement_generator 不根据它决定候选 pose、端口或占格；电力需求由 master/power 子链读取 canonical 模板字段处理。它是 schema-required 字段，但不是本 generator 的硬编码几何假设。

修复：新增 bool 类型守卫，进入分派前统一校验 `rotatable` 与 `is_solid_z`；各 `port_rule` 分支按 generator 实际 orientation family 锁定期望值。回归覆盖 `manufacturing_6x4.rotatable=false`、`protocol_core.rotatable=false`、`boundary_storage_port.rotatable=false`、`manufacturing_3x3.is_solid_z=false`。

## Finding F-PRE-R11-03: cycle group 只验证 square/singular，不验证非负解，负机器率会被静默吞掉

Severity: High

位置：

- 原代码：`src/interchange/preprocess_context.py:305-323` 与 `src/interchange/preprocess_context.py:418-442`
- 修复后：`src/interchange/preprocess_context.py:305-332` 与 `src/interchange/preprocess_context.py:427-457`
- 负值被吞的下游位置：`src/preprocess/demand_solver.py:117-129` 累加 cycle 解后进入 `_sort_fraction_mapping()`，而 `_sort_fraction_mapping()` 在 `src/preprocess/demand_solver.py:335-340` 过滤 `<=0` 项
- 回归：`src/tests/test_preprocess_context.py:224-229`

问题：`validate_preprocess_context()` 原来只检查 cycle group 是 square，并用零 RHS 解一次来捕获 singular；`_solve_square_linear_system()` 可捕获奇异矩阵，但 `_solve_cycle_group_exact()` 对求得的负 run rate 没有任何检查。若 canonical/schema-valid 漂移让农业闭环经济性倒置，solver 会返回负机器率，随后 demand solver 的排序/过滤步骤会把非正项静默丢弃，最终冻结需求工件可能缺失机器。

可复现 probe：在未修复代码上将 `seed_collector_buckwheat.outputs.buckwheat_seed` 从 `2` 改成 `0.5`。此时 buckwheat cycle 对正向 `buckwheat` 需求的方程仍唯一可解，但解为负：`planter_buckwheat = -D`，`seed_collector_buckwheat = -2D`；`build_preprocess_context_from_rules_and_plan()` 原来能成功构造 context。

修复：

1. `validate_preprocess_context()` 现在验证每个 `net_export_commodity` 必须属于 `internal_commodities`。
2. 构造 context 时，除零 RHS 外，对每个 net export commodity 的单位需求求解一次，强制证明该 cycle group 的导出方向存在非负基解。
3. `_solve_cycle_group_exact()` 对任意实际 RHS 的求解结果逐项检查，若 run rate 为负立即 fail-closed。

## Q1 R10 修复确认

`load_default_preprocess_context()` 与 `load_preprocess_context_from_paths()` 已在 strict JSON 后、context defaults 前运行 canonical/plan 双 schema 校验。全仓搜索 `build_preprocess_context_from_rules_and_plan(` 与 preprocess context loader 调用后，生产代码中没有绕过这两个 loader 直接 strict-load + 构造 context 的第三入口；测试中直接调用 builder 属于单元测试注入面。

`load_default_preprocess_context()` 上的 `lru_cache(maxsize=1)` 语义可接受：异常不会被缓存，首次 schema 校验失败后再调用会重新执行；首次成功后返回的缓存对象已经通过 strict JSON + schema + context validation。若同一进程内手动改磁盘默认文件，缓存不会重读，这与默认规则文件作为进程内 immutable source 的假设一致，不构成新的 fail-open。

R10 geometry contract 的原始字段覆盖不足已由 F-PRE-R11-02 修复。placement_generator 的独立 canonical 入口未跑 schema 的交互问题已由 F-PRE-R11-01 修复。

## Q2 demand solver 数学本体审计

`src/preprocess/demand_solver.py` 的非 cycle 展开使用 exact `Fraction`。`PreprocessRecipe.input_rate()` / `output_rate()` 在 `src/interchange/preprocess_context.py:39-43` 以 `amount / ticks_per_cycle` 定义 per-tick 速率；`solve_demands_exact()` 先完整回推 theoretical machine runs，再由 `generate_ceil_machine_counts()` 在 `src/preprocess/demand_solver.py:133-137` 对最终每个 operation 取 `ceil`。这与 `specs/04_recipe_and_demand_expansion.md:137-140` “基于理论台数、按单一工序向上取整”的规定一致，没有链式过早 ceil。

手算完整 demand 链如下，和冻结 `machine_counts.json`、`generic_io_requirements.json` 对齐：

| operation | 理论 run rate | ceil | 冻结 count |
|---|---:|---:|---:|
| `packaging_battery` | 3 | 3 | 3 |
| `filling_capsule` | 11/4 = 2.75 | 3 | 3 |
| `parts_maker` | 6 | 6 | 6 |
| `molding_bottle` | 11/2 = 5.5 | 6 | 6 |
| `grinder_dense_source` | 9 | 9 | 9 |
| `grinder_fine_buckwheat` | 11/2 = 5.5 | 6 | 6 |
| `grinder_dense_blue_iron` | 17 | 17 | 17 |
| `refinery_steel` | 17 | 17 | 17 |
| `refinery_blue_iron` | 34 | 34 | 34 |
| `crusher_source` | 18 | 18 | 18 |
| `crusher_blue_iron` | 34 | 34 | 34 |
| `crusher_buckwheat` | 11/2 = 5.5 | 6 | 6 |
| `crusher_sandleaf` | 21/2 = 10.5 | 11 | 11 |
| `planter_buckwheat` | 11 | 11 | 11 |
| `seed_collector_buckwheat` | 11/2 = 5.5 | 6 | 6 |
| `planter_sandleaf` | 21 | 21 | 21 |
| `seed_collector_sandleaf` | 21/2 = 10.5 | 11 | 11 |

关键中间链：

- targets: `valley_battery = 3 * 1/5 = 3/5` per tick；`qiaoyu_capsule = 11/4 * 1/5 = 11/20` per tick。
- final assembly consumes `dense_source_powder=9`，`steel_part=6`，`fine_buckwheat_powder=11/2`，`steel_bottle=11/2`。
- steel chain: `steel_block = 6 + 11 = 17`，因此 `dense_blue_iron_powder=17`。
- powder/base chain: `source_powder=18`，`blue_iron_powder=34`，`sandleaf_powder=9 + 11/2 + 17 = 63/2`。
- external ore: `source_ore=18`，`blue_iron_ore=34`，generic output port total `18 + 34 = 52`。
- agriculture cycles: 对任意作物净需求 D，矩阵为 `[[1, -1], [-1, 2]] * [P, C]^T = [D, 0]^T`，det=1，解 `P=2D, C=D`。buckwheat D=`11/2` 得 `P=11, C=11/2`；sandleaf D=`21/2` 得 `P=21, C=21/2`。

因此 Q2 中除 F-PRE-R11-03 的负解验证缺口外，当前 canonical demand 数字、52/34/18 口预算、ceil 位置均 sound。

## Q3 canonical 17-recipe 投影 vs vendored 上游抽样

抽样覆盖原料、底层冶炼、中间品、终品、cycle group 成员。单位换算规则：上游 `craftingTime` 为秒，canonical `ticks_per_cycle = craftingTime / 2`，与 `globals.time.tick_interval_seconds=2` 一致。

| canonical recipe | canonical 字段 | upstream source | upstream 字段 | 判定 |
|---|---|---|---|---|
| `packaging_battery` | `manufacturing_6x4`, ticks 5, `dense_source_powder 15 + steel_part 10 -> valley_battery 1`，见 `rules/canonical_rules.json:117-127` | `tools_proc_battery_3_1`，见 `third_party_snapshots/endfield_calc/upstream_materialized_snapshot/recipes.json:3041-3059` | `item_originium_enr_powder 15 + item_iron_enr_cmpt 10 -> item_proc_battery_3 1`, `facilityId=item_port_tools_asm_mc_1`, `craftingTime=10` | 忠实，10s/2s=5 ticks |
| `filling_capsule` | `manufacturing_6x4`, ticks 5, `fine_buckwheat_powder 10 + steel_bottle 10 -> qiaoyu_capsule 1`，见 `rules/canonical_rules.json:128-138` | `filling_bottled_rec_hp_3_1`，见 `recipes.json:1663-1681` | `item_plant_moss_enr_powder_1 10 + item_iron_enr_bottle 10 -> item_bottled_rec_hp_3 1`, `facilityId=item_port_filling_pd_mc_1`, `craftingTime=10` | 忠实；moss_1/rec_hp 选择有注释记录 |
| `crusher_source` | `manufacturing_3x3`, ticks 1, `source_ore 1 -> source_powder 1`，见 `rules/canonical_rules.json:212-220` | `grinder_originium_powder_1`，见 `recipes.json:2238-2252` | `item_originium_ore 1 -> item_originium_powder 1`, `facilityId=item_port_grinder_1`, `craftingTime=2` | 忠实 |
| `refinery_blue_iron` | `manufacturing_3x3`, ticks 1, `blue_iron_ore 1 -> blue_iron_block 1`，见 `rules/canonical_rules.json:202-210` | `furnance_iron_nugget_1`，见 `recipes.json:2085-2099` | `item_iron_ore 1 -> item_iron_nugget 1`, `facilityId=item_port_furnance_1`, `craftingTime=2` | 忠实 |
| `grinder_dense_source` | `manufacturing_6x4`, ticks 1, `source_powder 2 + sandleaf_powder 1 -> dense_source_powder 1`，见 `rules/canonical_rules.json:159-168` | `thickener_originium_enr_powder_1`，见 `recipes.json:2915-2933` | `item_originium_powder 2 + item_plant_moss_powder_3 1 -> item_originium_enr_powder 1`, `facilityId=item_port_thickener_1`, `craftingTime=2` | 忠实 |
| `planter_buckwheat` / `seed_collector_buckwheat` | ticks 1, `buckwheat_seed 1 -> buckwheat 1` 与 `buckwheat 1 -> buckwheat_seed 2`，见 `rules/canonical_rules.json:252-280` | `planter_plant_moss_1_1` / `seedcollector_plant_moss_1_1`，见 `recipes.json:2433-2447` 与 `recipes.json:2648-2662` | seed/crop loop 数量 `1 -> 1` 与 `1 -> 2`, `craftingTime=2` | 忠实，cycle group 成员无 off-by-one |

文档/注释痕迹：`src/adapters/endfield_calc/semantic_mapping.py:49-94` 记录 item 映射理由和 alternates；`src/adapters/endfield_calc/semantic_mapping.py:96-221` 记录 17 个 recipe 的 upstream id / facility id / canonical facility type；`specs/ecosystem_notes/endfield_calc_current_repository_semantic_alignment.md:18-60` 记录同一投影表，且说明这是 partial alignment。

facility 模板：canonical 的 3 个 manufacturing 模板与 adapter 中记录的上游 facility group 对齐：`manufacturing_3x3=(3,3, opposite_parallel_sides)`、`manufacturing_5x5=(5,5, opposite_parallel_sides)`、`manufacturing_6x4=(6,4, long_sides)`，见 `src/adapters/endfield_calc/semantic_mapping.py:223-257`。`src/adapters/industrial_planner/device_type_registry.json` 由 IP v2 `registry.ts` 派生，见 `src/adapters/README.md:25-26`；抽到的 grinder/furnance/cmpt/shaper 是 3x3，planter/seedcol 是 5x5，filling/thickener/tools 是 6x4，且 ports0 为一对相对边输入/输出。`third_party_snapshots/industrial_planner/bases/bases.json` 只投影 base，能确认 `valley4_protocol_core.placeableSize=70` 与 outerRing，见 `third_party_snapshots/industrial_planner/bases/bases.json:51-59`；该 vendored base 文件不包含 facility template 端口规则，因此 manufacturing port-rule 的直接来源是 IP device registry projection 与 semantic mapping，不是 base JSON。

Q3 抽样未发现无痕迹 canonical 漂移；未修改 canonical。

## 冻结工件条款

本补丁只增加输入校验与 cycle 非负性证明，当前 canonical 下生成结果不变。未修改或覆盖 `data/preprocessed/candidate_placements.json`。

复核命令：

```bash
python - <<'PY'
import hashlib, json, tempfile
from pathlib import Path
from src.placement.placement_generator import generate_all_pools, load_templates
with tempfile.TemporaryDirectory() as td:
    out = Path(td) / 'candidate_placements.json'
    pools = generate_all_pools(load_templates())
    out.write_text(json.dumps({'facility_pools': pools}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    data = out.read_bytes()
    print(len(data), hashlib.sha256(data).hexdigest())
PY
```

输出：`45773799 adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，与任务冻结期望一致。因此不需要同批推进任何登记 hash 位置。

## 回归与命令记录

依赖：已从 `/mnt/data/zmd_py313_linux_x86_64.zip` 离线安装 Python 3.13 wheels。

已通过：

```bash
python -m pytest -q \
  src/tests/test_preprocess_context.py \
  src/tests/test_preprocess_candidate_geometry_contract.py \
  src/tests/test_placements.py \
  src/tests/test_preprocess_cycle_solver.py \
  -p no:randomly
# 44 passed

python -m pytest -q \
  src/tests/test_demand.py \
  src/tests/test_preprocess_plan_schema.py \
  src/tests/test_preprocess_plan_exact_hash.py \
  src/tests/test_endfield_calc_semantic_mapping.py \
  src/tests/test_industrial_planner_precision_export.py \
  src/tests/test_preprocess_golden.py::test_regenerated_instance_distribution_matches_machine_counts \
  src/tests/test_preprocess_golden.py::test_regenerated_preprocess_invariants_match_current_frozen_contract \
  src/tests/test_preprocess_golden.py::test_frozen_preprocess_artifacts_are_cleanly_serialized_without_binary_noise \
  -p no:randomly
# 31 passed

python -m ruff check \
  src/placement/placement_generator.py \
  src/interchange/preprocess_context.py \
  src/tests/test_placements.py \
  src/tests/test_preprocess_candidate_geometry_contract.py \
  src/tests/test_preprocess_context.py
# All checks passed

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

未完成：全量 `python -m pytest -q src/tests` 未跑完；`src/tests/test_preprocess_golden.py::test_preprocess_chain_regenerates_frozen_artifacts_from_source_code` 在 sandbox 中超时。已用更直接的 candidate regeneration hash probe 覆盖本补丁涉及的冻结工件不变性。
