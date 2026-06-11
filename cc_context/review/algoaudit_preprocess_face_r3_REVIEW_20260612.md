# F-03 修复实现审查报告

审查对象：`zmd_v80_impl_full_20260612_single.zip`

输入包 SHA256：`764ef038b5df45a196ff597fb02a1b6e803fb4d2b8cd802113bb5446d8177614`

结论：**本轮不是零 soundness finding**。原包的 F-03 主修复在普通 `extract_port_specs()` 导出路径上是正确的，但仍有一个同类 producer-output 泄漏残留在 routing-aware binding domain filter 中。该泄漏会在 `EXACT_B1_ROUTING_AWARE_BINDING` 打开时，把 routing-free 无线终品生产端输出 front 当作必须空出的 routing terminal，导致虚假 empty binding domain，并可进一步进入 RAB certificate / Benders nogood。

我随附了补丁：`/mnt/data/f03_r3_residual_fix.patch`。补丁包含两个部分：

1. 修复 `_filter_pose_binding_domain()`，让它与 `extract_port_specs()` 同构，只检查 routing-visible ports，过滤掉 routing-free final commodity 的 producer output ports。
2. 增加 fail-closed semantic guard，禁止未来 canonical 把 `sink_kind = "generic_input"` 商品同时作为 recipe input，避免 F-03 的排除集合未来过宽后静默错。

补丁后针对性回归、规则测试、关键 preprocess/binding 测试与 proof-obligation check 均通过。未声称全量 `src/tests/` 完成，因为完整 `test_preprocess_golden.py` 的候选位再生路径在 300s 限时内未跑完。

---

## Finding F03-R3-01：routing-aware binding filter 仍把无线终品 producer output 当实体 routing port

Severity：**P0，当 `EXACT_B1_ROUTING_AWARE_BINDING=1` 启用时；默认关闭时为潜伏残留。**

位置，原包：

- `src/models/binding_subproblem.py:382-414`
- 特别是 `src/models/binding_subproblem.py:403`：`for port in pattern.get("input_ports", []) + pattern.get("output_ports", []):`
- 下游证书入口：`src/models/binding_subproblem.py:416-436`
- Benders loop 环境门与证书使用：`src/search/benders_loop.py:4888-4904`, `src/search/benders_loop.py:4920-4984`

### 问题

F-03 已在 `extract_port_specs()` 中正确跳过 routing-free wireless final commodity 的 producer output ports：

- `routing_free_sink_commodities` 由 positive `required_generic_inputs` 构成：`src/models/binding_subproblem.py:188-192`。
- `extract_port_specs()` 对实体 output ports 过滤这些 commodity：`src/models/binding_subproblem.py:826-843`。
- `extract_port_specs()` 对 generic-output slots 也过滤这些 commodity：`src/models/binding_subproblem.py:863-879`。

但 `_filter_pose_binding_domain()` 发生在 binding build 阶段，早于 solve 与 `extract_port_specs()`。原代码检查所有 active input + output ports 的 front 是否 in-grid/free。于是 `filling_capsule` 的 `qiaoyu_capsule` output front 只要被任意设施占住，就会把所有 binding patterns 剪掉，形成 empty domain。这个 front 本来不应该进入 routing，也不应该作为 routing-aware 过滤条件。

这条路径不是普通 precheck 的重复，而是独立侧门：

- `binding_model.build()` 期间直接清空 domain。
- `extract_empty_binding_domain_instances()` 可返回虚假空域。
- `extract_routing_aware_certificates()` 会把占据 wireless producer output front 的 blocker 记录进 certificate。
- Benders loop 在 `EXACT_B1_ROUTING_AWARE_BINDING` 打开时优先使用该 certificate / nogood，可能学习到错误冲突，或者在某些布局上反复拒绝合法解。

### Repro probe

构造：

- 一个 `filling_capsule_001`，pose 为 6x4，输入口在北侧，输出口在南侧。
- `required_generic_inputs = {"qiaoyu_capsule": 1}`。
- 两个 `protocol_storage_box` 仅用于占住该 producer 南侧所有 output front cells。
- producer 原料输入口不被占；按 F-03 语义，这个布局在 binding/routing 交互上应可行，因为 `qiaoyu_capsule` 是无线终品，不需要实体输出 front 可达。

原包输出：

```text
empty domains [{'instance_id': 'filling_capsule_001', 'facility_type': 'manufacturing_6x4', 'operation_type': 'filling_capsule', 'pose_idx': 0, 'pose_id': 'prod_10_10'}]
domain count {}
stats {'enabled': True, 'raw_patterns_total': 540, 'filtered_patterns_total': 0, 'front_blocked_patterns_pruned': 540, 'empty_filtered_owners': ['filling_capsule_001'], ...}
status INFEASIBLE
```

补丁后输出：

```text
empty domains []
domain count {'filling_capsule_001': 540}
stats {'enabled': True, 'raw_patterns_total': 540, 'filtered_patterns_total': 540, 'front_blocked_patterns_pruned': 0, 'empty_filtered_owners': [], ...}
status FEASIBLE
```

### 修法

在 `_filter_pose_binding_domain()` 中构造 `routing_visible_ports`：

- 保留所有 input ports，因为生产设施的原料输入仍需 routing。
- 仅保留不属于 `self.routing_free_sink_commodities` 的 output ports。
- blocker collection 也只对 routing-visible ports 发生，避免 false RAB certificate。

补丁位置：

- `src/models/binding_subproblem.py:407-413`，补丁后。

新增回归：

- `src/tests/test_wireless_sink_binding_semantics.py:254-321`
- 断言 blocked wireless producer output fronts 不会导致 empty domain。
- 断言 540 个原始 binding patterns 全保留。
- 断言 `front_blocked_patterns_pruned == 0`。
- 断言 `extract_routing_aware_certificates() == []`。
- 断言 solve 可行，并且 `qiaoyu_capsule` 仍不出现在 `extract_port_specs()`。

---

## Hardening H03-R3-02：未来 dual-role generic_input 商品目前不会 fail-closed

Severity：**P1 fail-closed hardening，不是当前 canonical soundness failure。**

### 当前 canonical 穷举结果

独立从 `rules/canonical_rules.json` 和 `data/preprocessed/generic_io_requirements.json` 穷举：

```text
recipes 17
routing_free_sink_commodities ['qiaoyu_capsule', 'valley_battery']
positive_required_generic_inputs {'qiaoyu_capsule': 1, 'valley_battery': 1}
qiaoyu_capsule recipe_inputs 0 recipe_outputs 1 sink_kind generic_input production_target True
valley_battery recipe_inputs 0 recipe_outputs 1 sink_kind generic_input production_target True
input_overlap []
generic_input_metadata ['qiaoyu_capsule', 'valley_battery']
production_targets ['qiaoyu_capsule', 'valley_battery']
```

对应源码/工件位置：

- `data/preprocessed/generic_io_requirements.json:15-18`：positive `required_generic_inputs` 仅为 `qiaoyu_capsule` 和 `valley_battery`。
- `rules/canonical_rules.json:117-127`：`packaging_battery` 输出 `valley_battery`。
- `rules/canonical_rules.json:128-137`：`filling_capsule` 输出 `qiaoyu_capsule`。
- `rules/canonical_rules.json:293-303`：production targets 仅为这两个商品。
- `rules/canonical_rules.json:305-315`：二者 `sink_kind = "generic_input"`。

因此当前 17-recipe 投影下，F-03 的排除集合没有过宽：两者均为纯终品，不作任何 recipe input。

### 未来风险

原包的 semantic validator 只检查：

- `generic_input` 商品必须对应 production target。
- production target 必须声明 `sink_kind = "generic_input"`。

它没有禁止 `generic_input` 商品同时作为 recipe input。实测将 `steel_part` 改为 `sink_kind = "generic_input"` 并加入 production target 后，原包 validator 输出：

```text
mutated_dual_role_generic_input_validator=PASS
```

这意味着未来若 canonical 扩展出现“既是无线终品 generic_input，又是中间品 recipe input”的商品，当前 F-03 机制会静默跳过其 producer output routing port，但下游实体消费者仍需要该商品，binding/routing 可能各自局部可行却断料。

### 修法

补丁在 `src/rules/semantic_validator.py:125-147` 添加 consumers map，并对 `meta.sink_kind == "generic_input" and commodity_id in consumers` fail-closed。

新增回归：

- `src/tests/test_rules.py:186-197`
- 构造 `steel_part` dual-role generic_input，要求 semantic validator 抛出 `SemanticValidationError`。

补丁后同一 mutation 输出：

```text
mutated_dual_role_generic_input_validator=FAIL SemanticValidationError
  - 商品元数据冲突：generic_input 商品 'steel_part' 是 routing-free 无线终品，不能同时作为配方输入；否则生产端输出口会被 routing 排除但下游仍需要实体供料。消费者 recipes: packaging_battery。
```

---

## Q1：排除集合两个方向审查

### 过宽方向

当前工件：没有过宽。`routing_free_sink_commodities = {c | required_generic_inputs[c] > 0}` 恰为 `{qiaoyu_capsule, valley_battery}`，二者均是 recipe output，均是 production target，均 `sink_kind = "generic_input"`，且 recipe input 出现次数均为 0。

未来扩展：原包不会显式报错，会静默接受 dual-role generic_input。补丁已加 fail-closed guard 与回归，把这个未来风险钉死。

### 过窄方向

未发现当前过窄。`required == 0` 时，wireless sink slot 会绑定 `__unused__`，不会导出 port spec；这类商品没有真实 routing-free demand。当前 `commodity_metadata.sink_kind = "generic_input"` 与 production target 集合也只含这两个 positive required entries，没有其他 routing-free 消费形态被漏掉。

`__unused__` 路径也未泄漏：generic input slots 的 `__unused__` 在 `extract_port_specs()` 中被跳过，wireless virtual slots 因 `routing_free` 或 `virtual` 也被跳过。

### 端口读端复查

- `extract_port_specs()` 的实体 binding-choice 端口循环：已过滤 routing-free output ports，保留 input ports。
- `extract_port_specs()` 的 generic-output 槽循环：已过滤同集合 commodity。
- fixed binding choice：`extract_selection()` 会先写入 `fixed_binding_choice`，随后 `extract_port_specs()` 对同一 `binding_choice` 结果应用过滤，因此该路径无额外泄漏。
- `extract_empty_binding_domain_instances()`：自身只是返回 build 阶段结果。原包问题来自 RAB 过滤阶段，补丁后不再因 wireless producer output front 产生虚假空域。
- `extract_routing_aware_certificates()`：原包会消费虚假 blockers；补丁后 blocker collection 只看 routing-visible ports，测试断言该 probe 下 certs 为空。

---

## Q2：binding 数学与下游交互

F-03 只改变 port specs 导出面，不改变 binding 内部端口绑定数学。producer 的 output ports 仍参与 binding pattern 枚举与 CP-SAT 选择；区别只是 routing-free wireless final commodity 的 output ports 不再成为 routing terminal。

这不是反向漏洞，而是 F-03 文档语义要求。根据 PROJECT_LOCK 与 specs，`qiaoyu_capsule` / `valley_battery` 被协议箱无线消费，不要求通向协议箱的 sink front，也不把生产端实体输出口计入 flow/routing 端口集合。没有审到 canonical/specs 中存在“无线终品 producer output front 被占会 back-pressure 停机”这一约束；按当前宪法，要求该 front 可达反而会重新制造 F-03 false-INFEASIBLE。

下游行为：

- 普通 `front_blocked` precheck 只消费 `extract_port_specs()`。F-03 后无线终品 output 不在 port_specs，原料 input ports 仍在，因此 precheck 不会对无线终品输出 front 误报。
- `binding_selection_safe_reject` / binding empty-domain nogood：原包的 RAB 侧门可能提前空域；补丁后不会因 routing-free output front 触发。
- RAB certificate / Benders nogood：原包可把 blocker 记入 false certificate；补丁后只对 routing-visible ports 记录 blockers。

---

## Q3：回归与文档一致性

现有 F-03 回归 `test_wireless_sink_commodity_does_not_reenter_routing_from_producer_output` 是判别的：

- 断言 `qiaoyu_capsule` 已被 generic input 消费。
- 断言 `qiaoyu_capsule` 不在 `port_specs`。
- 断言 `fine_buckwheat_powder` 与 `steel_bottle` 仍在 `port_specs`，覆盖“原料 input 口保持 routing”。
- 断言 routing precheck 的 `commodity_front_metadata` 不含 `qiaoyu_capsule`。

新增 RAB 回归覆盖了原测试没有覆盖的 build 阶段 side channel。

文档一致性检查：

- `PROJECT_LOCK.md:94-95`：明确 consumer 端无线虚拟槽不 emit port specs，producer 端只排除无线终品 output ports，原料 input ports 保留。
- `specs/05_facility_instance_definition.md:101-107`：同样写明生产端对偶只排除实体输出口和同 commodity generic-output 口。
- `specs/08_topological_flow_subproblem.md:23-26`：`V_port` 例外明确不把无线终品生产端实体输出口计入端口集合，同时保留生产设施原料输入口。

未发现“排除全部口”这类措辞错位。

---

## 已执行验证

环境：Python 3.13 venv，依赖从 `zmd_py313_linux_x86_64.zip` 离线安装。

原包 probe：

```text
empty domains [{'instance_id': 'filling_capsule_001', ...}]
front_blocked_patterns_pruned: 540
status INFEASIBLE
```

补丁后 probe：

```text
empty domains []
domain count {'filling_capsule_001': 540}
front_blocked_patterns_pruned: 0
status FEASIBLE
```

补丁后测试：

```text
python -m py_compile src/models/binding_subproblem.py src/tests/test_wireless_sink_binding_semantics.py src/rules/semantic_validator.py src/tests/test_rules.py
# pass

python -m pytest -q -p no:randomly src/tests/test_rules.py src/tests/test_wireless_sink_binding_semantics.py --tb=short
# 25 passed in 1.36s

python -m pytest -q -p no:randomly \
  src/tests/test_preprocess_golden.py::test_regenerated_preprocess_invariants_match_current_frozen_contract \
  src/tests/test_regression.py::test_generic_io_requirements_are_generated_from_preprocess \
  src/tests/test_binding.py::test_binding_model_assigns_generic_wireless_sink_inputs \
  src/tests/test_binding.py::test_binding_model_keeps_generic_outputs_globally_pooled --tb=short
# 4 passed in 2.74s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

另外，补丁前已跑过原 F-03 专项文件：

```text
python -m pytest -q -p no:randomly src/tests/test_wireless_sink_binding_semantics.py --tb=short
# 6 passed in 1.51s
```

补丁后该文件：

```text
python -m pytest -q -p no:randomly src/tests/test_wireless_sink_binding_semantics.py --tb=short
# 7 passed in 1.20s
```

---

## 审查覆盖清单

实际审过的通道与攻击：

1. Canonical recipes / commodity metadata / production_targets / generic IO requirements 穷举，验证当前 `routing_free_sink_commodities` 集合。
2. 未来 dual-role generic_input mutation，验证原包不会 fail-closed，并给出 semantic guard。
3. `extract_port_specs()` 两个排除点：实体 output ports 与 generic-output slots。
4. fixed binding choice 通过 `extract_selection()` 进入同一导出过滤路径。
5. consumer 端 wireless virtual generic input slots 不导出 routing specs。
6. producer 原料 input ports 仍导出 routing specs。
7. ordinary routing precheck 的 `front_blocked` 路径。
8. RAB `_filter_pose_binding_domain()` build-time 过滤路径。
9. `extract_empty_binding_domain_instances()` 与 `extract_routing_aware_certificates()` 的 false-empty / false-cert 路径。
10. Benders loop 对 RAB certificates 的消费路径。

对原包结论：**存在 1 个当前 soundness finding，不能报零。**

对随附补丁后的工作树结论：针对本轮 F-03 审查面，未发现新的残留 soundness finding；建议先合入补丁后再将 preprocess 面收口。
