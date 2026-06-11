# IndustrialPlanner preprocess F-01/F-02 soundness review

结论：本轮不是零 finding。审查发现 1 个 soundness finding，位于 Q1 routing-free 声明的完备性：虚拟 wireless sink 槽本身没有泄漏坐标，但无线最终商品仍能从上游生产设施的实体输出端口进入 routing/precheck。该路径违反“无线商品零 routing 需求”的修复目标，并能触发虚假的 `front_blocked`。

## 审查环境与工件核验

- 输入包 SHA256：`7f0433fa4258cb91970b9f266bbbc8f36f793c004687b64c09e2ad7625d8063a`。
- `data/preprocessed/candidate_placements.json`：
  - SHA256：`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`
  - size：`45,773,799` bytes
  - counts：`boundary_storage_port=134`, `manufacturing_3x3=17408`, `manufacturing_5x5=16368`, `manufacturing_6x4=16380`, `power_pole=4761`, `protocol_core=6728`, `protocol_storage_box=4624`, total `66403`
  - `protocol_storage_box`：4624 unique anchors, `(0,0)` through `(67,67)`, `orientation=[0]`, `port_mode=['omni']`, physical port pose count `0`。
- 重点测试与脚本：
  - 原始审查重点套件：`39 passed`。
  - 附带补丁后新增 regression：`40 passed`。
  - `python scripts/check_p1_2_proof_obligations.py`：pass。
  - `python scripts/check_external_artifacts.py --require candidate_placements`：pass。

## 审过的数据通道清单

已沿以下路径逐段追踪：

- `PortBindingModel._materialize_pose_optional_instances()`：`protocol_storage_box` 正确合成为 `wireless_sink`。
- `_build_generic_input_domains()`：每个 selected wireless sink 生成 3 个 virtual generic input 槽，槽 dict 只有 `slot_id/instance_id/type/operation_type/routing_free/virtual`，没有 `x/y/dir`。
- `_add_generic_input_requirements()`：`sum(commodity vars) == required`，`required == 0` 时固定 commodity vars 为 0。
- `extract_selection()`：virtual slots 以 `{instance_id}:in:{idx}` 形状进入 `generic_inputs`；不读坐标。
- `extract_port_specs()`：对 virtual/routing_free generic input slots 的跳过顺序正确，先 `slot.get("routing_free") or slot.get("virtual")`，不会触发 `slot["x"]`。
- `extract_routing_aware_certificates()`：只从实体 port binding pattern 的 front blockers 生成证据；virtual slots 不参与。
- `extract_conflict_summary()`：报告 generic slot 计数与 selection，不读 virtual slot 坐标。
- `add_nogood_cut()`：对 binding choices、generic inputs、generic outputs 使用 literal 形状切当前 selection；virtual slots 不导致下标坐标访问。
- `run_exact_routing_precheck()` / `RoutingGrid` / `RoutingSubproblem`：只消费 `extract_port_specs()` 输出；若 `port_specs == []`，precheck/routing 是 feasible/zero ports。
- `flow_subproblem` 与 D2 flow wrapper：直接坐标读取只来自 port specs/port dict；没有第二条 virtual slot 坐标通道。
- `benders_loop._run_exact_binding_and_routing()`：binding 后取 `selection` 与 `port_specs`，precheck 的 `front_blocked` / `relaxed_disconnected` 会触发 binding-level nogood 或后续 master cut/fail-closed 逻辑。

上述通道中，virtual slot 坐标侧没有发现泄漏；但实体 producer output 侧存在 wireless commodity 泄漏。

---

## Finding F-03 — P0：无线最终商品仍会通过生产端实体输出口进入 routing/precheck

**Severity**：P0 soundness / contract break。该问题会把 routing-free 的最终商品当成有 routing terminal 的商品处理，可能用虚假的端口 front 阻塞证据否定一个按 wireless 消费语义可行的 binding/layout。

**位置**：

- `src/models/binding_subproblem.py:816-831`：`extract_port_specs()` 对 pose-level `binding_choice` 的 `input_ports/output_ports` 无条件 append。这里会把上游生产设施的实体输出端口，例如 `filling_capsule -> qiaoyu_capsule`、`packaging_battery -> valley_battery`，加入 routing port specs。
- `src/models/binding_subproblem.py:833-839`：只跳过了 virtual/routing_free generic input slots，闸门范围太窄。
- `src/models/routing_subproblem.py:294-356`：precheck 对所有 port specs 直接建立 terminal front，并在 front 被占用时返回 `front_blocked`。
- `src/search/benders_loop.py:5162-5214`, `5251-5572`：precheck 的 `front_blocked` / `relaxed_disconnected` 可触发 binding nogood、layout cut 或 fail-closed 后续逻辑。

**复现 probe**：在原始树上构造一个 `filling_capsule` 生产 `qiaoyu_capsule`，同时放置一个 `protocol_storage_box` 作为 `wireless_sink`，并要求 `required_generic_inputs={"qiaoyu_capsule": 1}`。

```python
from pathlib import Path
from src.models.binding_subproblem import PortBindingModel
from src.models.routing_subproblem import RoutingPlacementCore, run_exact_routing_precheck

PROJECT_ROOT = Path.cwd()

def make_pose(pose_id, x, y, w, h, in_ports=None, out_ports=None):
    return {
        "pose_id": pose_id,
        "anchor": {"x": x, "y": y},
        "pose_params": {"orientation": 0, "port_mode": "probe"},
        "occupied_cells": [[xx, yy] for yy in range(y, y + h) for xx in range(x, x + w)],
        "input_port_cells": list(in_ports or []),
        "output_port_cells": list(out_ports or []),
        "power_coverage_cells": None,
    }

producer = make_pose(
    "prod_x10_y10", 10, 10, 6, 4,
    in_ports=[{"x": 10 + i, "y": 14, "dir": "N"} for i in range(6)],
    out_ports=[{"x": 10 + i, "y": 9, "dir": "S"} for i in range(6)],
)
wireless = make_pose("box_x30_y30_omni", 30, 30, 3, 3)

solution = {
    "filling_capsule_001": {
        "facility_type": "manufacturing_6x4",
        "pose_idx": 0,
        "pose_id": producer["pose_id"],
        "anchor": dict(producer["anchor"]),
        "orientation": 0,
        "port_mode": "probe",
    },
    "pose_optional::protocol_storage_box::box_x30_y30_omni": {
        "facility_type": "protocol_storage_box",
        "pose_idx": 0,
        "pose_id": wireless["pose_id"],
        "anchor": dict(wireless["anchor"]),
        "orientation": 0,
        "port_mode": "omni",
        "bound_type": "exact_pose_optional",
        "solve_mode": "certified_exact",
    },
}
instances = [{
    "instance_id": "filling_capsule_001",
    "facility_type": "manufacturing_6x4",
    "operation_type": "filling_capsule",
    "is_mandatory": True,
}]

model = PortBindingModel(
    solution,
    {"manufacturing_6x4": [producer], "protocol_storage_box": [wireless]},
    instances,
    required_generic_outputs={},
    required_generic_inputs={"qiaoyu_capsule": 1},
    project_root=PROJECT_ROOT,
)
model.build()
assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
print(model.extract_selection()["generic_inputs"])
print(model.extract_port_specs())
```

原始输出要点：

```text
selected wireless slots {'pose_optional::protocol_storage_box::box_x30_y30_omni:in:0': 'qiaoyu_capsule'}
port spec commodities [
  ('in', 'fine_buckwheat_powder', 10, 14, 'N'),
  ('in', 'fine_buckwheat_powder', 11, 14, 'N'),
  ('in', 'steel_bottle', 12, 14, 'N'),
  ('in', 'steel_bottle', 13, 14, 'N'),
  ('out', 'qiaoyu_capsule', 10, 9, 'S')
]
qiaoyu in routing port specs? True
precheck metadata commodities ['fine_buckwheat_powder', 'qiaoyu_capsule', 'steel_bottle']
```

更强的阻塞 probe：把 wireless box 放到 `(10,7)`，其 body 占住 `qiaoyu_capsule` 输出口 `(10,9,S)` 的 routing front `(10,8)`。按 routing-free 语义，最终品无线消费不应要求这格可达；但原始实现返回：

```text
blocked qiaoyu specs [{'instance_id': 'filling_capsule_001', 'x': 10, 'y': 9, 'dir': 'S', 'type': 'out', 'commodity': 'qiaoyu_capsule'}]
blocked precheck status front_blocked
blocked ports [{'instance_id': 'filling_capsule_001', 'commodity': 'qiaoyu_capsule', 'front_cell': [10, 8], 'blocking_instance_ids': ['box_x10_y7_omni'], ...}]
```

**影响论证**：

这不是“虚拟槽没有 x/y/dir 导致崩溃”的问题；虚拟槽 gate 是正确的。问题是 wireless commodity 的生产端实体输出仍被导出成 routing terminal。于是 routing/precheck 看到一个不应存在的商品 terminal，并可以把本应 routing-free 的最终品输出 front 当作硬阻塞证据。由于 benders loop 会消费 precheck 的 `binding_selection_safe_reject` 并对当前 selection 加 nogood，或在后续阶段上升为 placement cut/fail-closed，这会造成对合法布局的虚假拒绝。该行为直接违背 `PROJECT_LOCK.md` 中“routing/flow 不应收到协议箱 sink fronts”的外部契约，并且没有被现有 wireless sink tests 覆盖，因为现有测试只验证了 sink-only 场景。

**建议修法**：

在 `PortBindingModel` 内显式记录 positive `required_generic_inputs` 对应的 routing-free sink commodities，并在 `extract_port_specs()` 中跳过这些 commodity 的实体输出端口和 generic output 端口。这样保留上游生产设施的输入口 routing 需求，例如 `fine_buckwheat_powder`、`steel_bottle`，但不再把无线最终品输出当成需要 routing 的商品 terminal。

已附 unified diff：`fix_wireless_routing_free_leak.patch`。

补丁后同一 probe 的结果：

```text
box_x30_y30_omni qiaoyu specs [] precheck feasible blocked []
box_x10_y7_omni  qiaoyu specs [] precheck feasible blocked []
```

新增 regression：`test_wireless_sink_commodity_does_not_reenter_routing_from_producer_output()`，验证：

- `qiaoyu_capsule` 仍被 virtual generic input slot 消费；
- `extract_port_specs()` 不再含 `qiaoyu_capsule`；
- 非无线上游输入商品仍保留实体 routing ports；
- `run_exact_routing_precheck()` 的 metadata 不再含 `qiaoyu_capsule`。

---

## Q2 binding 容量数学审查

未发现容量数学问题。

实测结论：

```text
over_capacity INFEASIBLE slots 3 selected None
exact_capacity FEASIBLE slots 3 selected all 'a'
zero_explicit FEASIBLE slots 3 selected all '__unused__'
multi_box_sum FEASIBLE slots 6 selected five 'a' + one '__unused__'
missing_file FileNotFoundError
missing_key KeyError
negative ValueError
```

对应代码依据：

- `load_wireless_sink_generic_input_slots()` 对缺文件、缺键、负数 fail-closed。
- `_build_generic_input_domains()` 每槽 `AddExactlyOne(commodities + "__unused__")`。
- `_add_generic_input_requirements()` 对 positive required 使用 `sum(vars_for_commodity) == required`，对 zero required 固定 commodity vars 为 0。
- 多 wireless 实例自然叠加 slots。

## Q3 生成器与池契约审查

未发现 generator / pool contract 新缺陷。

- `is_edge_starved()` 现在是“非空 port 集合且所有 front 越界才剪”，空集合不剪；该语义与 specs/06 的“整组 front 全越界才绝对面壁”一致。
- `gen_protocol_storage_box()` 只枚举 3x3 no-port omni，全 anchor `0..67`，计数 `68 * 68 = 4624`。
- `candidate_placements.json` 实测 hash/size/count 与 PROJECT_LOCK/specs06/docs 登记一致。
- stale artifact hash resume rejection 已由 `test_campaign_resume_rejects_stale_candidate_placement_hash` 覆盖，且该测试不是恒真：它先保存旧 hash，再改写 artifact，并断言 resume 被 `artifact_hash_mismatch` reset。

## Q4 测试判别力与文档一致性审查

发现 1 个测试缺口，即 Finding F-03 的 producer-output 回流路径未覆盖。其余 F-01/F-02 核心文档与测试观察一致：

- `PROJECT_LOCK.md`、`specs/05_facility_instance_definition.md`、`specs/06_candidate_placement_enumeration.md`、`docs/exact_campaign_operations.md` 均登记了 4624 no-port omni 与新 artifact hash/size。
- 上轮 review 文档中旧 17,952/TB/BT/RL/LR 内容作为历史 finding 保留在 `cc_context/review/algoaudit_preprocess_face_r1_REVIEW_20260612.md`，不是当前 contract 陈述。
- `specs/08_topological_flow_subproblem.md` 仍描述一般物理 port flow；它未显式提到 wireless sink 例外，但与 specs/05 的 wireless sink routing-free 专条并不直接冲突。若 owner 希望更强文档闭环，可在 specs/08 加一句“wireless_sink virtual generic input slots are excluded from physical port set”。

## 附带补丁验证

补丁文件：`fix_wireless_routing_free_leak.patch`。

验证命令：

```bash
python -m py_compile src/models/binding_subproblem.py src/tests/test_wireless_sink_binding_semantics.py
python -m pytest -q -p no:randomly src/tests/test_wireless_sink_binding_semantics.py --tb=short
python -m pytest -q -p no:randomly \
  src/tests/test_preprocess_candidate_geometry_contract.py \
  src/tests/test_wireless_sink_binding_semantics.py \
  src/tests/test_placements.py \
  src/tests/test_binding.py::test_binding_model_assigns_generic_wireless_sink_inputs \
  src/tests/test_exact_contract.py::test_binding_recognizes_pose_optional_protocol_storage_box \
  src/tests/test_blueprint_to_master_hint.py \
  --tb=short
python scripts/check_p1_2_proof_obligations.py
python scripts/check_external_artifacts.py --require candidate_placements
```

结果：

```text
6 passed in 0.43s
40 passed in 22.64s
P1.2 proof obligation check passed: 8 obligations anchored
external artifact check passed: data/preprocessed/candidate_placements.json verified
```

`python -m ruff check ...` 未执行成功，因为当前离线环境未安装 `ruff`。
