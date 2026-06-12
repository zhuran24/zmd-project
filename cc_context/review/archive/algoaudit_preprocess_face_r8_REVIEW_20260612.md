# IndustrialPlanner preprocess 链 round 8 审查报告

审查对象：`zmd_fbind_r3_snapshot_50360c1d.zip`。开工前已校验 sha256 为 `50360c1d82504d4de5b5af026c00d8d235db8ded32304b293a3d0d8a7c550893`，与任务给定值一致。

结论：本轮发现 1 个 preprocess 侧 soundness finding，已给出补丁与回归测试。除该 JSON 解析纵深问题外，Q1 候选枚举完备性、Q3 demand→instance ceil 展开、Q4 generic I/O 生成契约未发现新的 soundness finding。

## Finding F-PRE-R8-01：preprocess 再生成链默认 JSON 装载接受重复 key / NaN，首次构建可静默改写语义

Severity：High / soundness。

影响位置（baseline 行号）：

- `src/interchange/preprocess_context.py:358-370`：`canonical_rules.json` 与 `preprocess_plan.json` 通过默认 `json.loads` 装载。
- `src/placement/placement_generator.py:304-310`：`canonical_rules.json` 的 `facility_templates` 通过默认 `json.load` 装载。
- `src/preprocess/instance_builder.py:160`：`machine_counts.json` 通过默认 `json.loads` 装载后生成 `mandatory_exact_instances.json`。
- `scripts/build_current_preprocess_context.py:45-46`：冻结工件 parity 消费侧通过默认 `json.loads` 装载。

问题说明：Python 标准 `json.loads/json.load` 对重复对象 key 采用 last-write-wins，并接受 `NaN/Infinity/-Infinity`。hash 闭包能挡 resume 漂移，但不能阻止首次构建时把坏 canonical / plan / machine_counts / frozen parity 输入按被静默改写后的语义生成工件。对 Q1 来说，重复 `port_rule` 或尺寸字段可让 placement generator 走错枚举分支；对 Q3 来说，重复 target value 或 machine count 可改变 ceil 台数和强制实例数。

可复现 probe（在未修 baseline 上运行）：

```bash
cd /mnt/data/zmd_r8_orig/project
python3.13 - <<'PY'
from pathlib import Path
import tempfile
from src.interchange.preprocess_context import load_preprocess_context_from_paths
root = Path('.')
rules_text = (root / 'rules/canonical_rules.json').read_text(encoding='utf-8').replace(
    '"value": 3.0,\n      "final_recipe_id": "packaging_battery"',
    '"value": 3.0,\n      "value": 999.0,\n      "final_recipe_id": "packaging_battery"',
    1,
)
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    rules = td / 'canonical_rules.json'
    plan = td / 'preprocess_plan.json'
    rules.write_text(rules_text, encoding='utf-8')
    plan.write_text((root / 'rules/preprocess_plan.json').read_text(encoding='utf-8'), encoding='utf-8')
    ctx = load_preprocess_context_from_paths(rules_path=rules, plan_path=plan)
    print('duplicate-key accepted')
    print('valley_battery target value =', ctx.targets['valley_battery'].value)
PY
```

baseline 输出：

```text
duplicate-key accepted
valley_battery target value = 999
```

修复：

- 新增 `src/io/strict_json.py`，统一用 `object_pairs_hook` 拒绝重复 key，用 `parse_constant` 拒绝 `NaN/Infinity/-Infinity`。
- `src/interchange/preprocess_context.py` 的 canonical / preprocess_plan 装载改为 strict JSON；原先用于 deep copy 的 JSON roundtrip 改为 `copy.deepcopy`，避免重新引入默认 JSON 解码语义。
- `src/placement/placement_generator.py` 的 canonical 装载改为 strict JSON，并保留 `python src/placement/placement_generator.py` 直接执行能力。
- `src/preprocess/instance_builder.py` 新增 `load_machine_counts()`，strict 装载并校验 top-level object、非 bool 整数、非负。
- `scripts/build_current_preprocess_context.py` 的 frozen parity 装载改为 strict JSON。
- preprocess 生成侧 JSON dump 增加 `allow_nan=False`，包括 demand artifacts、instance artifacts、candidate placements。
- 新增回归测试覆盖 canonical duplicate key、canonical NaN、placement duplicate `port_rule`、placement NaN dimension、machine_counts duplicate key、machine_counts NaN。

修复后同一 probe 输出：

```text
ValueError duplicate JSON key: value
```

## Q1：candidate_placements 枚举完备性复核

复核方法：写了独立枚举 probe，不调用 `placement_generator.generate_all_pools()`，只从 canonical 模板维度 / port_rule 重新构造 expected pose signature，并与 `data/preprocessed/candidate_placements.json` 的实际 `(facility, x, y, orientation, port_mode, occupied_cells, input_ports, output_ports, coverage)` 集合逐项比对。

结果：7 个模板池全部 expected == actual；missing pose = 0，extra pose = 0。再生 artifact 后 sha256 与大小仍为任务给定值：

```text
sha256  adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
bytes   45773799
```

枚举矩阵如下。

| facility | orientation / port_mode | count | anchor x range | anchor y range |
| --- | ---: | ---: | ---: | ---: |
| manufacturing_3x3 | o=0 / BT | 4352 | 0..67 | 2..65 |
| manufacturing_3x3 | o=0 / LR | 4352 | 2..65 | 0..67 |
| manufacturing_3x3 | o=0 / RL | 4352 | 2..65 | 0..67 |
| manufacturing_3x3 | o=0 / TB | 4352 | 0..67 | 2..65 |
| manufacturing_5x5 | o=0 / BT | 4092 | 0..65 | 2..63 |
| manufacturing_5x5 | o=0 / LR | 4092 | 2..63 | 0..65 |
| manufacturing_5x5 | o=0 / RL | 4092 | 2..63 | 0..65 |
| manufacturing_5x5 | o=0 / TB | 4092 | 0..65 | 2..63 |
| manufacturing_6x4 | o=0 / BT | 4095 | 0..64 | 2..64 |
| manufacturing_6x4 | o=0 / TB | 4095 | 0..64 | 2..64 |
| manufacturing_6x4 | o=1 / LR | 4095 | 2..64 | 0..64 |
| manufacturing_6x4 | o=1 / RL | 4095 | 2..64 | 0..64 |
| protocol_core | o=0 / core_LR_out | 3364 | 2..59 | 2..59 |
| protocol_core | o=1 / core_TB_out | 3364 | 2..59 | 2..59 |
| protocol_storage_box | o=0 / omni | 4624 | 0..67 | 0..67 |
| power_pole | o=0 / omni | 4761 | 0..68 | 0..68 |
| boundary_storage_port | o=0 / left_base | 67 | 0..0 | 1..67 |
| boundary_storage_port | o=1 / bottom_base | 67 | 1..67 | 0..0 |

按 pool 汇总：

```text
manufacturing_3x3             expected 17408 actual 17408 missing 0 extra 0
manufacturing_5x5             expected 16368 actual 16368 missing 0 extra 0
manufacturing_6x4             expected 16380 actual 16380 missing 0 extra 0
protocol_core                 expected  6728 actual  6728 missing 0 extra 0
protocol_storage_box          expected  4624 actual  4624 missing 0 extra 0
power_pole                    expected  4761 actual  4761 missing 0 extra 0
boundary_storage_port         expected   134 actual   134 missing 0 extra 0
TOTAL                         expected 66403 actual 66403
```

审查结论：

- `generate_all_pools()` 遍历 canonical `facility_templates` 的全部 key，未知 `port_rule` 直接 `ValueError`，未发现 facility 静默跳过。
- 正方形制造设施固定 `o=0`，用 `BT/TB/LR/RL` 覆盖所有物理通流方向；`o=1/o=2/o=3` 对 footprint 与端口集合为旋转等价冗余，未发现非对称 pose 漏枚举。
- `manufacturing_6x4` 对 `long_sides` 枚举 `o=0` 的 top/bottom 两向与 `o=1` 的 left/right 两向，覆盖 90° 旋转和输入输出反向。
- `protocol_core` 两个非等价输出轴向 `core_LR_out/core_TB_out` 均枚举；左右 / 上下内部镜像由端口集合对称吸收。
- `protocol_storage_box` / `power_pole` 无物理端口，边界死锁剪枝不适用，anchor 为全 footprint in-grid 域。
- `boundary_storage_port` 只在左 / 下基线枚举，左下角交叠被 `1..67` 起止裁剪排除，未发现 off-by-one 剪掉贴边合法 pose。
- `occupied_cells` 与 port cell 推导按 orientation 复核；所有 occupied cells in-grid，port/front 裁剪与现行 artifact 一致。

## Q2：preprocess 链 JSON 装载点清单

本轮覆盖的 preprocess 链装载点如下。

| 位置 | 装载内容 | baseline 行为 | 补丁后行为 | 语义风险判定 |
| --- | --- | --- | --- | --- |
| `src/interchange/preprocess_context.py:357-373` | `canonical_rules.json`, `preprocess_plan.json` | 默认 `json.loads` | `load_strict_json` | 实际 soundness 路径，已修 |
| `src/preprocess/operation_profiles.py:17` | 默认 `PreprocessContext` | 间接依赖 default context | 间接 strict | 无独立 JSON 装载点 |
| `src/placement/placement_generator.py:312-318` | `canonical_rules.json/facility_templates` | 默认 `json.load` | `load_strict_json` | 实际 candidate 枚举语义路径，已修 |
| `src/preprocess/instance_builder.py:128-143,179` | `machine_counts.json` | 默认 `json.loads` | `load_machine_counts()` strict + 类型校验 | 实际 mandatory instance 生成路径，已修 |
| `scripts/build_current_preprocess_context.py:46-47` | frozen parity 工件：`commodity_demands`, `machine_counts`, `port_budget`, `generic_io_requirements`, `mandatory_exact_instances`, `all_facility_instances` | 默认 `json.loads` | `load_strict_json` | parity 消费侧语义路径，已修 |
| `src/preprocess/demand_solver.py:172-206` | `generic_io_requirements.json` 生成 | 不从 JSON 装载，派生自 context | context strict；dump `allow_nan=False` | 无重复 key 装载面 |
| `src/preprocess/demand_solver.py:209-229` | demand artifacts 写出 | 默认 `json.dump` 可写 NaN | `allow_nan=False` | 写出侧已 fail-closed |
| `src/preprocess/instance_builder.py:146-150` | instance artifacts 写出 | 默认 `json.dump` 可写 NaN | `allow_nan=False` | 写出侧已 fail-closed |
| `src/placement/placement_generator.py:386-389` | candidate artifact 写出 | 默认 `json.dump` 可写 NaN | `allow_nan=False` | 写出侧已 fail-closed |

binding/master 侧已有独立 strict loader，本报告不重报 face 6 的 F-BIND finding。

## Q3：demand→instance ceil 规则数学抽查

复核方法：用当前 `PreprocessContext` 重新跑 `solve_demands()` 与 `generate_ceil_machine_counts()`，逐 operation 比对理论台数、ceil 台数、冻结 `machine_counts.json`、冻结 `mandatory_exact_instances.json` 中的实例计数。

| operation_type | theory N_m | ceil | mandatory instances |
| --- | ---: | ---: | ---: |
| crusher_blue_iron | 34.0 | 34 | 34 |
| crusher_buckwheat | 5.5 | 6 | 6 |
| crusher_sandleaf | 10.5 | 11 | 11 |
| crusher_source | 18.0 | 18 | 18 |
| filling_capsule | 2.75 | 3 | 3 |
| grinder_dense_blue_iron | 17.0 | 17 | 17 |
| grinder_dense_source | 9.0 | 9 | 9 |
| grinder_fine_buckwheat | 5.5 | 6 | 6 |
| molding_bottle | 5.5 | 6 | 6 |
| packaging_battery | 3.0 | 3 | 3 |
| parts_maker | 6.0 | 6 | 6 |
| planter_buckwheat | 11.0 | 11 | 11 |
| planter_sandleaf | 21.0 | 21 | 21 |
| refinery_blue_iron | 34.0 | 34 | 34 |
| refinery_steel | 17.0 | 17 | 17 |
| seed_collector_buckwheat | 5.5 | 6 | 6 |
| seed_collector_sandleaf | 10.5 | 11 | 11 |

Probe 结果：

```text
sum_counts 219
machine_counts_match_frozen True
mandatory_manufacturing_match_counts True
mandatory_total 266 manufacturing 219 core 1 boundary 46
```

审查结论：

- `generate_ceil_machine_counts()` 对 `machines_fractional.items()` 按 operation 独立 ceil，没有发现把多个 operation 先合并再 ceil 的路径。
- `mandatory_exact_instances.json` 的 219 个制造实例逐 operation 等于 ceil 结果，再加 `protocol_core=1` 与 `boundary_io=46`，总数 266。
- 冗余机器没有在 preprocess 侧被折算成必须满载的 flow 需求。`commodity_demands.json` 保留 exact demand 侧数值，例如 `valley_battery=0.6`、`qiaoyu_capsule=0.55`、`source_ore=18`、`blue_iron_ore=34`；binding 的 generic I/O 只强制需要的 generic source/sink 槽数，flow diagnostic 的需求等式使用 `commodity_demands`，未看到按 ceil 后产能强制每台机器满载的 preprocess 路径。

## Q4：preprocess→binding generic I/O 新契约涟漪

`generate_generic_io_requirements()` 生成侧现在与 F-BIND-R1/R2 的消费契约一致：

- `required_generic_outputs` 仅来自 `role.source_kind == "external_boundary"` 且 flow > 0 的商品。
- `required_generic_inputs` 仅来自 `role.sink_kind == "generic_input"` 且 flow > 0 的商品。
- `validate_preprocess_context()` 先校验 `source_kind/sink_kind` 枚举，且要求所有 production target 必须声明 `sink_kind='generic_input'`；`generic_input` 商品必须是 target，且不能再作为 recipe input。

当前 artifact 与 canonical 角色对应关系：

| section | commodity | generated count | canonical source_kind | canonical sink_kind |
| --- | --- | ---: | --- | --- |
| required_generic_outputs | blue_iron_ore | 34 | external_boundary | none |
| required_generic_outputs | source_ore | 18 | external_boundary | none |
| required_generic_inputs | qiaoyu_capsule | 1 | internal_only | generic_input |
| required_generic_inputs | valley_battery | 1 | internal_only | generic_input |

结论：当前生成侧保证产出的商品满足消费侧角色约束。若未来 owner-gate 扩展新的商品角色，当前快照的 `_ALLOWED_SOURCE_KINDS/_ALLOWED_SINK_KINDS` 会先在 context validation 报错；不会在未更新代码的情况下静默生成消费侧会误解释的 generic I/O 工件。

## 冻结工件条款

本补丁未修改 canonical 内容，也未修改冻结工件内容。为确认写出侧变更不会改变 candidate artifact，已按任务指定命令再生：

```bash
python3.13 src/placement/placement_generator.py
sha256sum data/preprocessed/candidate_placements.json
stat -c '%s' data/preprocessed/candidate_placements.json
```

结果：

```text
adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0  data/preprocessed/candidate_placements.json
45773799
```

登记位置清单：无。`candidate_placements.json` 内容 hash / 字节数未变，不需要推进 frozen artifact hash registry。`scripts/build_current_preprocess_context.py` parity 报告显示 6 个 frozen preprocess 工件全部与再生结果一致。

## 验证记录

已运行并通过：

```text
python3.13 -m pytest -q src/tests/test_preprocess_context.py src/tests/test_placements.py src/tests/test_demand.py -p no:randomly
38 passed in 4.42s

python3.13 scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored

python3.13 scripts/build_current_preprocess_context.py --output /tmp/r8_build_current/context.json --diff-json /tmp/r8_build_current/diff.json --diff-md /tmp/r8_build_current/diff.md
summary.all_match = true, matched_count = 6, total_count = 6, mandatory_exact_instance_count = 266, all_instance_count = 326, generic_output_slots = 52

python3.13 -m compileall -q src/io/strict_json.py src/interchange/preprocess_context.py src/placement/placement_generator.py src/preprocess/instance_builder.py src/preprocess/demand_solver.py scripts/build_current_preprocess_context.py
passed
```

全量 `python3.13 -m pytest -q src/tests -p no:randomly` 已尝试运行；在沙盒中跑到约 14% 时超时，超时前未打印 failure。由于本轮改动集中在 preprocess JSON 装载、candidate 再生与 demand/instance 生成，以上专项与 proof-obligation/parity 检查覆盖了本补丁涉及路径。
