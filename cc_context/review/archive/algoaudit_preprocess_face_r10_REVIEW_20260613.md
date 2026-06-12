# 终末地 IndustrialPlanner preprocess 链 round 10 审查报告

审查对象只使用 `zmd_snapshot_70457b5e.zip`。开工前校验 sha256 为 `70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a`，与任务给定值一致。

本轮结论：原始快照存在 2 个 Medium 级 fail-closed/soundness guard finding，另有 1 个 Low 级 postprocess audit artifact freshness finding。已给出补丁并补 regression。当前 canonical 与 frozen candidate 本体未发现几何方向、端口极性或枚举等价类 soundness 错误；`candidate_placements.json` 再生成后 sha256 与字节数保持不变。

## Finding F-PRE-R10-01: preprocess path loader 未在消费前执行 schema 校验，schema-required 字段可被默认值吞掉

Severity: Medium

位置：原始 `src/interchange/preprocess_context.py:158-162` 使用 `_mapping_or_empty(...).get(..., default)` 读取 `globals.time.tick_interval_seconds` 与 `globals.logistics.belt_capacity_per_tick`；原始 `src/interchange/preprocess_context.py:365-372` 的 `load_preprocess_context_from_paths()` 只 strict-load JSON 后直接构造 context，没有先跑 `canonical_rules.schema.json` 与 `preprocess_plan.schema.json`。

问题：schema 明确要求若干字段存在，例如 `canonical_rules.schema.json:53-58` 要求 `tick_interval_seconds`，`preprocess_plan.schema.json:80-84` 要求 utility slot 字段。但实际文件入口未调用 schema 校验，导致 schema-invalid 源文件在 path loader 上仍可进入 context 构建，并由默认值伪装成合法数据。这是典型“schema 锁了，消费侧绕过了”的 fail-open 方向。

复现 probe，使用原始 loader：

```text
original_path_loader_missing_tick: PASS defaults_to 2.0
```

修法：在 `src/interchange/preprocess_context.py:359-397` 增加 schema 缓存加载与 `_validate_preprocess_source_schemas()`，并在 `load_default_preprocess_context()` 和 `load_preprocess_context_from_paths()` strict-load 后、context defaults 前执行 jsonschema 校验。新增 regression 位于 `src/tests/test_preprocess_context.py:114-137`，覆盖 canonical required 字段缺失和 preprocess_plan required 字段缺失。

修复后 probe：

```text
direct_builder_missing_tick: PASS defaults_to 2.0
path_loader_missing_tick: ERR ValidationError 'tick_interval_seconds' is a required property
```

说明：`build_preprocess_context_from_rules_and_plan()` 仍是低层纯构造函数，保留现有测试中直接喂变体 dict 做语义验证的能力；实际文件入口和生成脚本走 path loader，已 fail-closed。

## Finding F-PRE-R10-02: placement 生成器对 schema-visible 几何字段存在硬编码/消费滞后，schema-valid 模板漂移可生成与 canonical 不一致的 pose

Severity: Medium

位置：原始 `rules/canonical_rules.schema.json:181-263` 对 `facility_templates` 只要求 `dimensions.w/h >= 1`、`port_rule` enum、若干 optional 字段形状；原始 `src/placement/placement_generator.py:321-358` 根据 `port_rule` 分派，但 `core_specific`、`omni_wireless`、`none`、`inward_facing` 生成器分别硬编码 9x9、3x3、2x2、1x3，并未核对 canonical dimensions。`long_sides` 使用 dimensions，但数学假设是未旋转形态 `w > h`，schema 和 semantic validator 没有锁住该不变量。

复现 probe，所有 case 都通过 schema 与 semantic，但原始 generator 继续按旧几何发 pose：

```text
CASE protocol_core w=10
schema=PASS, semantic=PASS
generator=PASS first_area,bbox,ports,cov= (81, (9, 9), 20, None)
CASE storage_box w=4
schema=PASS, semantic=PASS
generator=PASS first_area,bbox,ports,cov= (9, (3, 3), 0, None)
CASE power_pole w=3
schema=PASS, semantic=PASS
generator=PASS first_area,bbox,ports,cov= (4, (2, 2), 0, 49)
CASE boundary_port w=2
schema=PASS, semantic=PASS
generator=PASS first_area,bbox,ports,cov= (3, (1, 3), 1, None)
CASE manufacturing_6x4 flipped long_sides
schema=PASS, semantic=PASS
generator=PASS first_area,bbox,ports,cov= (24, (4, 6), 8, None)
CASE power_pole radius=99
schema=PASS, semantic=PASS
generator=PASS first_area,bbox,ports,cov= (4, (2, 2), 0, 49)
```

风险：当前 canonical 内容是干净的，因此没有当前 frozen candidate 污染。但未来 owner-gated canonical 变更若只依赖 schema/semantic 通过，可能得到“canonical 说一套，candidate pose 发另一套”的候选域，属于 certified-exact 前置域生成的 fail-open 缝。

修法：在 `src/placement/placement_generator.py:125-215` 增加 `_validate_template_geometry_contract()`，在 `generate_all_pools()` 分派前校验：

- `long_sides` 必须 `w > h`。
- `opposite_parallel_sides` 必须 `w == h`。
- `core_specific` 必须 9x9 且 `core_limits == 6/14`。
- `omni_wireless` 必须 3x3。
- `none` 必须 2x2 且 `power_coverage_radius == 5`。
- `inward_facing` 必须 1x3 且 `placement_rule == left_or_bottom_boundary`。

新增 regression 位于 `src/tests/test_preprocess_candidate_geometry_contract.py:18-61`。

修复后 probe：

```text
CASE protocol_core w=10 ERR ValueError protocol_core uses port_rule='core_specific', whose generator emits 9x9 poses; canonical dimensions are 10x9
CASE storage_box w=4 ERR ValueError protocol_storage_box uses port_rule='omni_wireless', whose generator emits 3x3 poses; canonical dimensions are 4x3
CASE power_pole w=3 ERR ValueError power_pole uses port_rule='none', whose generator emits 2x2 poses; canonical dimensions are 3x2
CASE boundary_port w=2 ERR ValueError boundary_storage_port uses port_rule='inward_facing', whose generator emits 1x3 poses; canonical dimensions are 2x3
CASE manufacturing_6x4 flipped long_sides ERR ValueError manufacturing_6x4 uses port_rule='long_sides' but dimensions are 4x6; the manufacturing generator expects the unrotated long side on top/bottom (w > h)
CASE power_pole radius=99 ERR ValueError power_pole.power_coverage_radius is 99; the power-pole generator emits the frozen radius-5 coverage stencil
```

## Finding F-PRE-R10-03: `current_preprocess_context.json` 为 r6 后旧 metadata，postprocess audit artifact 未字节级同步

Severity: Low

位置：原始 `data/solutions/current_preprocess_context.json:7-9` 仍写 `canonical_rules_plus_overlay`，而当前 `src/interchange/preprocess_context.py:221-223` 构造出的 source metadata 已是 `canonical_rules`。`FILE_STATUS.md:153-156` 标记该文件及 diff report 为 `POSTPROCESS_ONLY` audit artifact，不是 certified exact runtime 输入，因此不升级为当前求解 soundness finding。

复核：运行 `scripts/build_current_preprocess_context.py` 后，diff report 仍为 6/6 parity match，但 context payload hash 从原始 `b335d115efec05b2b4a755051a96cdf5f9d3b64689ffa5b4bd6de0c7327e8def` 变为 `4e62542ce6031d2bcadac09fa048bc3bfd387c8ae437ee2f852ced6a87d25592`，差异仅 3 个 metadata 字段。

修法：重新生成并提交 `data/solutions/current_preprocess_context.json`。`data/solutions/preprocess_context_diff_report.json` sha256 仍为 `ef2a2d31ba140acbd08d3ff08d9c798f50e94a7a4008a2479db3578c9263df56`，字节数 893，未变化。

## Q1: F-PRE-R9-01 修复确认

结论：r9 strict JSON 修复确认通过，未发现新的非有限数值绕过。

`src/io/strict_json.py:29-33` 的 `parse_float` 只接管 JSON float/exponent 字面量，拒绝 `math.isfinite(parsed) == False`。`parse_int` 未自定义，Python int 任意精度路径保持标准 `json.loads` 行为，没有被 `parse_float` 误接管。

边界 probe 结果：

```text
plain_float: OK same_as_std=True value=[1.25, -2.5, 0.0]
scientific: OK same_as_std=True value=[1000.0, -0.00025, 6.022e+23]
negative_zero: OK same_as_std=True neg_zero_ok=True value=[-0.0]
tiny_subnormal: OK same_as_std=True value=[5e-324]
long_precision: OK same_as_std=True value=[0.12345678901234568]
plain_int: OK same_as_std=True value=[123, -456]
huge_int: OK same_as_std=True value=[1234567890123456789012345678901234567890]
positive_overflow: ERR ValueError: non-finite JSON number: 1e309
negative_overflow: ERR ValueError: non-finite JSON number: -1e309
nested_overflow: ERR ValueError: non-finite JSON number: 1e309
string_overflow: OK same_as_std=True value={'a': '1e309'}
```

`src/interchange/preprocess_context.py` path loader、`src/placement/placement_generator.py` template loader、`src/preprocess/instance_builder.py` loader 等 preprocess 入口均走 strict loader。`scripts/build_current_preprocess_context.py:66-83` 的 strict atomic writer 使用 same-dir tmp、`json.dump(... allow_nan=False)`、file fsync、`os.replace()`、directory fsync。probe 证实 finite payload 正常写出，`float('inf')` 被 `allow_nan=False` 拒绝且目标文件未出现。

冻结/审计 JSON 均可 strict-load，包括：`rules/canonical_rules.json`、`rules/preprocess_plan.json`、`candidate_placements.json`、`commodity_demands.json`、`machine_counts.json`、`port_budget.json`、`generic_io_requirements.json`、`mandatory_exact_instances.json`、`all_facility_instances.json`、`current_preprocess_context.json`、`preprocess_context_diff_report.json`。

## Q2: pose 几何变换数学本体复核

结论：当前 canonical 下未发现 rotation/orientation 坐标变换、端口 dir 极性、等价类折叠或 port_mode 语义漂移错误。

独立重推的本体规则：occupied bbox 为锚点左下角 `(x,y)` 到 `(x+w-1,y+h-1)`；端口坐标是设施外一格连接点，`top=(x+i,y+h,N)`、`bottom=(x+i,y-1,S)`、`left=(x-1,y+i,W)`、`right=(x+w,y+i,E)`；routing front 为 `port + DIR_DELTA[dir]`。因此 90° 顺时针旋转时边与方向极性对应为 `top/N -> right/E`，`bottom/S -> left/W`，`left/W -> top/N`，`right/E -> bottom/S`。实测所有物理端口满足“在 bbox 外侧一格且 front cell 在 70x70 grid 内”，`bad_physical_ports=0`。

手算对照清单：

| 模板/pose | 手算期望 | 实测摘要 |
|---|---|---|
| `manufacturing_6x4`, `(10,10,o=0,TB)` | bbox 6x4；输入 top N 6 个；输出 bottom S 6 个 | bbox `(10,10,15,13)`；inputs `(10..15,14,N)`；outputs `(10..15,9,S)` |
| `manufacturing_6x4`, `(10,10,o=0,BT)` | TB 反向 | inputs `(10..15,9,S)`；outputs `(10..15,14,N)` |
| `manufacturing_6x4`, `(10,10,o=1,RL)` | 90° 后 bbox 4x6；top/N 输入变 right/E；bottom/S 输出变 left/W | bbox `(10,10,13,15)`；inputs `(14,10..15,E)`；outputs `(9,10..15,W)` |
| `manufacturing_6x4`, `(10,10,o=1,LR)` | RL 反向 | inputs `(9,10..15,W)`；outputs `(14,10..15,E)` |
| `protocol_core`, `(20,20,o=0,core_LR_out)` | 9x9；左右 sparse outputs index 1,4,7；上下 dense inputs index 1..7 | outputs `(19,21/24/27,W)` 与 `(29,21/24/27,E)`；inputs bottom/top x=21..27, y=19/29 |
| `protocol_core`, `(20,20,o=1,core_TB_out)` | 90° 后上下 sparse outputs，左右 dense inputs；口数 6/14 保持 | outputs top/bottom x=21/24/27；inputs left/right y=21..27 |
| `manufacturing_3x3`, `manufacturing_5x5` | 方形 body 旋转等价，但端口侧别仍需 4 个 port_mode | orientation `{0}`；modes `{TB,BT,RL,LR}` |
| `protocol_storage_box`, `power_pole` | 无物理端口，body 对称，orientation 折叠安全 | orientation `{0}`；mode `{omni}`；ports 0 |
| `boundary_storage_port` | left/bottom boundary 两类基础姿态，不走自由旋转 | orientation `{0,1}`；modes `{left_base,bottom_base}`；每 pose 1 个 inward-facing storage port |

枚举复核：`manufacturing_3x3=17408`、`manufacturing_5x5=16368`、`manufacturing_6x4=16380`、`protocol_core=6728`、`protocol_storage_box=4624`、`power_pole=4761`、`boundary_storage_port=134`，总数 `66403`。

## Q3: schema vs 实际消费字段对齐矩阵

| 字段区域 | schema 状态 | 消费侧 | 结论 |
|---|---|---|---|
| `canonical_rules.metadata.version` | schema required | context metadata source version | 通过 path loader schema 校验后对齐；metadata 不参与 pose 几何 |
| `globals.time.tick_interval_seconds`、`globals.logistics.belt_capacity_per_tick` | schema required 且 >0 | preprocess context tick/belt | F-PRE-R10-01 已修；文件入口先 schema 校验，防止默认值吞缺失 |
| `facility_templates.dimensions`、`port_rule` | schema 宽约束 | placement generator geometry dispatch | F-PRE-R10-02 已修；消费点锁住当前硬编码几何 contract |
| `facility_templates.core_limits` | schema optional object，值 minimum 0 | protocol core generator 实际发 6 outputs/14 inputs | F-PRE-R10-02 已修；`core_specific` 必须 6/14 |
| `facility_templates.power_coverage_radius` | schema optional int minimum 0 | power pole generator frozen radius-5 stencil | F-PRE-R10-02 已修；`none` 模板必须 radius 5 |
| `facility_templates.placement_rule` | schema optional enum | boundary port generator 只支持 `left_or_bottom_boundary` | F-PRE-R10-02 已修 |
| `facility_templates.rotatable/needs_power/is_solid_z` | schema required | preprocess placement generator不直接消费；下游 master/binding 面消费 | preprocess 本轮仅列维护噪声，不报 soundness finding |
| `routing_rules`、`globals.grid`、`empty_rectangle` | schema locks | 本轮 preprocess context/candidate generator 不直接消费，其他面消费 | 非本轮 finding |
| `recipes.template/ticks_per_cycle/inputs/outputs` | schema required，数值正约束 | preprocess context demand solver | 文件入口 schema + context semantic 双层校验；对齐 |
| `production_targets.mode/value/final_recipe_id` | schema required | preprocess context targets | 文件入口 schema + context semantic 校验 final recipe/output；对齐 |
| `commodity_metadata.source_kind/sink_kind/cycle_group` | schema required | preprocess context roles | 文件入口 schema + context semantic 校验 source/sink/cycle；对齐 |
| `preprocess_plan.metadata` | schema required | context metadata | 文件入口 schema 校验后对齐 |
| `preprocess_plan.cycle_groups` | schema required | cycle solver square-system validation | 对齐；context 额外校验 group square、recipe/commodity refs |
| `preprocess_plan.utility_operations` | schema required，slot int >=0 | generic IO/port budget derivation | F-PRE-R10-01 已修；文件入口 schema + `_strict_nonnegative_int` 对齐 |
| plan canonical override keys `recipes/production_targets/commodity_roles` | schema `additionalProperties:false` 禁止 | context additive-only guard | 双层防护，对齐 |

## 冻结工件条款

本补丁不扩展 canonical 内容，不改变 certified candidate 语义。执行：

```bash
PYTHONPATH=. python src/placement/placement_generator.py
sha256sum data/preprocessed/candidate_placements.json
wc -c data/preprocessed/candidate_placements.json
```

结果：

```text
sha256 adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
bytes 45773799
total poses 66403
```

无需推进 candidate hash 登记。`data/solutions/current_preprocess_context.json` 属 `POSTPROCESS_ONLY` audit artifact，本轮已同步为当前生成结果：

```text
sha256 4e62542ce6031d2bcadac09fa048bc3bfd387c8ae437ee2f852ced6a87d25592
bytes 9759
```

`data/solutions/preprocess_context_diff_report.json` 未变化：

```text
sha256 ef2a2d31ba140acbd08d3ff08d9c798f50e94a7a4008a2479db3578c9263df56
bytes 893
summary {'all_match': True, 'matched_count': 6, 'total_count': 6, 'mandatory_exact_instance_count': 266, 'all_instance_count': 326, 'generic_output_slots': 52, 'generic_input_slots': 0}
```

## 验证命令

通过：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python -m pytest -q -p no:randomly src/tests/test_placements.py
# 19 passed

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python -m pytest -vv -p no:randomly src/tests/test_preprocess_candidate_geometry_contract.py
# 5 passed

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python -m pytest -q -p no:randomly src/tests/test_preprocess_context.py
# 16 passed

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python -m pytest -q -p no:randomly src/tests/test_rules.py
# 18 passed

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python -m pytest -q -p no:randomly src/tests/test_preprocess_plan_schema.py src/tests/test_preprocess_plan_exact_hash.py
# 3 passed

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

全量 `src/tests` 尝试运行但在沙盒 wall-clock 内未完成，未拿到全量 2968 passed 结论；本轮与变更相关的专项、proof obligation、candidate 再生成、context 再生成均已完成。
