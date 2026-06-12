# 终末地 IndustrialPlanner preprocess 链 round 9 审查报告

审查输入：`zmd_pre_r9_snapshot_ec504afe.zip`

开工校验：`sha256sum /mnt/data/zmd_pre_r9_snapshot_ec504afe.zip` = `ec504afe704b4a1cea6597a3956d7e68fd5adc195961cd4724e69cd354ffb50f`，与任务指定值一致。

结论：本轮发现 1 个 preprocess 再生成链可用性 / strictness finding；未发现当前冻结三件套导致 certified 求解 soundness 破坏。当前冻结工件在修复后 strict 读取干净，`candidate_placements.json` 再生成字节级 hash 不变。

## Finding F-PRE-R9-01：strict JSON 未拒绝 JSON 数字上溢，context/parity 写出点可再吐出 Infinity

Severity：Medium。影响面是 preprocess 再生成 / parity 工件的 fail-closed 可用性和 r8 strictness 承诺完整性；当前冻结工件自身干净，exact hash 闭包仍会挡住已登记工件静默漂移。

原始快照位置：

- `src/io/strict_json.py:31-35` 只设置 `object_pairs_hook` 与 `parse_constant`，能拒 `NaN`、`Infinity`、`-Infinity` 常量，但没有设置 `parse_float`。Python `json.loads` 会把合法 JSON 数字字面量 `1e309`、`-1e309` 解析成 `inf`、`-inf`。
- `scripts/build_current_preprocess_context.py:180,183` 复用 `src/search/exact_campaign.py:1304-1314` 的 `atomic_write_json`；该 writer 的 `json.dump(payload, handle, indent=2, ensure_ascii=False)` 没有 `allow_nan=False`。因此只要上游 strict loader 放入了 `inf`，context/parity 输出可写出非标准 JSON 常量 `Infinity`。

复现 probe（在原始快照副本上执行）：

```bash
cd /mnt/data/zmd_r9_orig_project
rm -rf /tmp/r9_overflow_orig && mkdir -p /tmp/r9_overflow_orig
python3.13 - <<'PY'
from pathlib import Path
text = Path('rules/canonical_rules.json').read_text(encoding='utf-8')
old = '''"power_pole": {\n      "dimensions": {\n        "w": 2,\n        "h": 2\n      },'''
new = '''"power_pole": {\n      "dimensions": {\n        "w": 1e309,\n        "h": 2\n      },'''
Path('/tmp/r9_overflow_orig/canonical_overflow.json').write_text(text.replace(old, new, 1), encoding='utf-8')
PY
PYTHONPATH=/mnt/data/zmd_r9_orig_project python3.13 - <<'PY'
from pathlib import Path
from src.io.strict_json import load_strict_json
payload = load_strict_json(Path('/tmp/r9_overflow_orig/canonical_overflow.json'))
print(payload['facility_templates']['power_pole']['dimensions'])
PY
PYTHONPATH=/mnt/data/zmd_r9_orig_project python3.13 scripts/build_current_preprocess_context.py \
  --rules /tmp/r9_overflow_orig/canonical_overflow.json \
  --plan rules/preprocess_plan.json \
  --output /tmp/r9_overflow_orig/current_context.json \
  --diff-json /tmp/r9_overflow_orig/diff.json \
  --diff-md /tmp/r9_overflow_orig/diff.md
python3.13 - <<'PY'
from pathlib import Path
text = Path('/tmp/r9_overflow_orig/current_context.json').read_text(encoding='utf-8')
idx = text.index('"power_pole"')
print(text[idx:idx+95].replace('\n','\\n'))
PY
```

观测输出：

```text
{'w': inf, 'h': 2}
preprocess context written: /tmp/r9_overflow_orig/current_context.json
...
"power_pole": {\n      "dimensions": {\n        "w": Infinity,\n        "h": 2\n      },
```

修复：

- `src/io/strict_json.py` 新增 `parse_float`，保持正常 JSON float 解析行为，但若 `float(value)` 非有限数则抛 `ValueError("non-finite JSON number: ...")`。
- `scripts/build_current_preprocess_context.py` 改用本地 `_atomic_write_json_strict`，继续 atomic replace + file fsync + directory fsync，但 `json.dump(..., allow_nan=False)`。
- 新增回归：
  - `src/tests/test_preprocess_context.py::test_preprocess_context_path_loader_rejects_overflow_json_numbers`
  - `src/tests/test_preprocess_context.py::test_preprocess_context_report_writer_rejects_nonfinite_numbers`
  - `src/tests/test_placements.py::test_placement_template_loader_rejects_overflow_json_numbers`
  - `src/tests/test_demand.py::test_load_machine_counts_rejects_overflow_json_numbers`

修复后 probe：

```text
nested_duplicate ValueError duplicate JSON key: a
array_duplicate ValueError duplicate JSON key: a
nan ValueError invalid JSON constant: NaN
infinity ValueError invalid JSON constant: Infinity
negative_infinity ValueError invalid JSON constant: -Infinity
overflow_positive ValueError non-finite JSON number: 1e309
overflow_negative ValueError non-finite JSON number: -1e309
```

同一上溢 canonical 输入现在在 `load_preprocess_context_from_paths()` 入口 fail-closed，报 `ValueError: non-finite JSON number: 1e309`，不会再生成 `Infinity` context 工件。

## Q1：r8 strict JSON 修复确认与装载点穷举

`object_pairs_hook` 对嵌套对象和数组内对象均生效，probe 覆盖 `{ "outer": {"a":1,"a":2} }` 与 `{ "items": [{"a":1,"a":2}] }`，均抛 `duplicate JSON key: a`。`parse_constant` 覆盖 `NaN`、`Infinity`、`-Infinity`。本轮补丁补上了 `1e309` / `-1e309` 这类 JSON 数字上溢。

preprocess 再生成链内装载点清单：

| 装载点 | 工件 / 入口 | r9 结论 |
|---|---|---|
| `src/interchange/preprocess_context.py:360-361` | 默认 `rules/canonical_rules.json`、`rules/preprocess_plan.json` | strict loader |
| `src/interchange/preprocess_context.py:371-372` | 自定义 `rules_path`、`plan_path` | strict loader |
| `src/placement/placement_generator.py:312-318` | candidate 生成器读取 `facility_templates` | strict loader |
| `src/preprocess/instance_builder.py:128-129` | `machine_counts.json` | strict loader |
| `scripts/build_current_preprocess_context.py:47-48` | parity / frozen 工件 `_load_json()` | strict loader |
| `src/preprocess/operation_profiles.py:14-17` | profile 构建的默认 context 间接读取 | 走 `load_default_preprocess_context()`，strict loader |

未发现 regeneration 链上的第 5 个默认 `json.loads` 装载口。仓内仍有 tests、adapter throughput audit、release builder、campaign/checkpoint 等其它 `json.loads`，不属于本轮 preprocess regeneration 链；binding/master/campaign/checkpoint 按任务边界未重报。

preprocess 写出点：

| 写出点 | 工件 | r9 结论 |
|---|---|---|
| `src/placement/placement_generator.py:388-389` | `candidate_placements.json` | `allow_nan=False` 已有 |
| `src/preprocess/demand_solver.py:226-229` | `commodity_demands.json`、`machine_counts.json`、`port_budget.json`、`generic_io_requirements.json` | `allow_nan=False` 已有 |
| `src/preprocess/instance_builder.py:146-150` | `mandatory_exact_instances.json`、`exploratory_optional_caps.json`、`all_facility_instances.json` | `allow_nan=False` 已有 |
| `scripts/build_current_preprocess_context.py:201,204` | `current_preprocess_context.json`、`preprocess_context_diff_report.json` | 本轮补丁改为 strict atomic writer + `allow_nan=False` |

## Q2：三件套与 canonical 交叉一致性矩阵

实际核验对象：`candidate_placements.json` / `mandatory_exact_instances.json` / `generic_io_requirements.json` / `canonical_rules.json` / `preprocess_plan.json` / `machine_counts.json`，均通过修复后的 strict loader 读取。

| 矩阵项 | 实测结果 | 保障来源 / 备注 |
|---|---:|---|
| candidate pool 模板集 vs canonical `facility_templates` | 7/7 完全相等 | `placement_generator.generate_all_pools()` 从 canonical templates 派生 pool key |
| candidate pool 总数 | 66,403 | `manufacturing_3x3=17,408`，`manufacturing_5x5=16,368`，`manufacturing_6x4=16,380`，`protocol_core=6,728`，`protocol_storage_box=4,624`，`power_pole=4,761`，`boundary_storage_port=134` |
| mandatory instance facility_type 是否全在 canonical | 0 unknown | 266 个强制实例：`manufacturing_3x3=132`，`manufacturing_5x5=49`，`manufacturing_6x4=38`，`protocol_core=1`，`boundary_storage_port=46` |
| mandatory operation_type 是否全有 profile | 0 unknown | 17 个制造 recipe + `protocol_core` + `boundary_io` 均在 `OPERATION_PORT_PROFILES` |
| operation profile facility_type vs instance facility_type | 0 mismatch | profile 由 context recipe / utility operation 派生；当前工件一致 |
| mandatory 模板无 candidate pool | 0 | 无 “必选但无坑位池” |
| candidate pool 无 mandatory instance | `power_pole`、`protocol_storage_box` | 预期 optional pose-level 模板；对应 `EXPLORATORY_OPTIONAL_CAPS` 与 master `POSE_LEVEL_OPTIONAL_TEMPLATES`，不是死候选 |
| `machine_counts.json` vs mandatory manufacturing instances | match | 219 个制造实例，外加 1 core + 46 boundary = 266 |
| generic output commodities vs commodity metadata | 0 missing / 0 role issue | `blue_iron_ore=34`、`source_ore=18`，均为 `source_kind=external_boundary`、`sink_kind=none` |
| generic input commodities vs commodity metadata | 0 missing / 0 role issue | `qiaoyu_capsule=1`、`valley_battery=1`，均为 `source_kind=internal_only`、`sink_kind=generic_input` |
| physical/wireless port profile consistency | no unexpected mismatch | manufacturing/core/boundary physical port capacities满足 profile；`protocol_storage_box` 是 `omni_wireless`，3 generic input slots 不对应 physical port cells，按既定口径不作为问题 |
| regenerated parity report | `all_match=true`，6/6 | `commodity_demands`、`machine_counts`、`port_budget`、`generic_io_requirements`、`mandatory_exact_instances`、`all_facility_instances` 全匹配 frozen |

我没有找到“能通过 preprocess 生成但被消费侧静默吞掉”的三件套交叉一致性构造。`validate_preprocess_context()` 会拒 unknown recipe template、unknown final recipe、unknown utility facility_type、非法 commodity role；`build_manufacturing_instances()` 会拒 unknown `operation_type` in `machine_counts`。`operation_profiles.aggregate_*()` 对任意外来 unknown operation 有 silent-skip 形态，但 preprocess 生成路径不会产生这种 operation；若手改 frozen artifact，则属于 hash-closed frozen artifact 篡改，而不是“通过生成”。

## Q3：再生确定性

`python3.13 src/placement/placement_generator.py` 在本轮补丁后重新生成：

```text
sha256  adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
bytes   45773799
```

确定性观察：

- 生成器无随机数、无并行、无 OR-Tools 调用；`time.time()` 只进入 stdout，不进入 JSON。
- 坐标、方向、模式的枚举顺序由固定嵌套循环决定。
- `json.dump(..., separators=(',', ':'), allow_nan=False)` 已固定紧凑分隔符并拒非有限数；candidate 工件不含浮点格式化问题。
- pool 顶层 key 顺序跟 canonical JSON 中 `facility_templates` 的插入顺序一致；这是 Python 3.7+ 语言层 dict 顺序保证。没有 `sort_keys=True`，所以“语义相同但 key 顺序变了”的 canonical 会造成字节 hash 变化，但 exact hash 闭包会 fail-closed，而不是静默回退。
- Python 3.13.x → 3.14 / json encoder 未来变化不是项目内可数学证明的字节级兼容承诺；当前安全性依赖冻结 hash 校验失败即阻断。`PROJECT_LOCK.md` 登记 expected candidate hash/size，`compute_exact_artifact_hashes()` 绑定 candidate/canonical/mandatory/generic，并在存在时绑定 `preprocess_plan`。

## Q4：r8 修复与 hash 闭包交互

当前合法工件上，strict loader 与 `allow_nan=False` 零行为差异：

- 当前 `canonical_rules.json`、`preprocess_plan.json`、`candidate_placements.json`、`mandatory_exact_instances.json`、`generic_io_requirements.json`、`machine_counts.json` 均可通过修复后的 strict loader。
- `candidate_placements.json` 再生成 hash/bytes 与冻结登记完全一致：`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` / `45,773,799`。
- `scripts/build_current_preprocess_context.py` parity report：`summary.all_match=true`，`matched_count=6`，`total_count=6`。
- 未发现当前冻结工件含重复 key 或非有限数；r8 前静默接受、r9 后当前再生报错的情况不存在。

冻结工件条款：本补丁不修改 canonical 内容，不要求 owner gate；不修改 `candidate_placements.json` 内容；不需要推进冻结工件 hash 登记。若重新生成 candidate，步骤为：

```bash
python3.13 src/placement/placement_generator.py
sha256sum data/preprocessed/candidate_placements.json
stat -c '%s' data/preprocessed/candidate_placements.json
```

期望仍为：

```text
adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0  data/preprocessed/candidate_placements.json
45773799
```

登记位置清单（本补丁无需改）：

- `PROJECT_LOCK.md:34-41`：candidate expected bytes/hash 与 regeneration command。
- `src/search/exact_campaign.py:194-205`：exact hash closure 文件列表，含 candidate/canonical/mandatory/generic，存在时含 preprocess_plan。
- `src/tests/test_preprocess_plan_exact_hash.py:25-40`：preprocess_plan 被 hash closure 绑定的回归。

## 验证命令

已通过：

```bash
python3.13 -m pytest -q src/tests/test_preprocess_context.py src/tests/test_placements.py src/tests/test_demand.py -p no:randomly
# 44 passed

python3.13 -m pytest -q src/tests/test_preprocess_plan_exact_hash.py src/tests/test_preprocess_plan_schema.py src/tests/test_operation_profiles.py -p no:randomly
# 8 passed

python3.13 scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

python3.13 src/placement/placement_generator.py
sha256sum data/preprocessed/candidate_placements.json
stat -c '%s' data/preprocessed/candidate_placements.json
# adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0 / 45773799

python3.13 scripts/build_current_preprocess_context.py --output /tmp/r9_current_context_after.json --diff-json /tmp/r9_diff_after.json --diff-md /tmp/r9_diff_after.md
# all_match True, matched 6 / total 6
```

尝试但未完成：

```bash
python3.13 -m pytest -q src/tests -p no:randomly
```

该全量命令在 300 秒沙盒 timeout 前未完成；可见输出均为通过进度点，未出现 failure。`src/tests/test_preprocess_golden.py` 单独运行也在 180 秒 timeout 前未完成，因此本报告以专项回归 + proof obligation + 再生 hash/parity 为实测基线。
