# 终末地 IndustrialPlanner binding 建模忠实度审查 round 1

审查对象：`zmd_f78r2_snapshot_13dc4e59.zip` 内 `project/` 仓库根，聚焦 `src/models/binding_subproblem.py` 的数学建模、解提取、loader 契约，以及 `src/search/benders_loop.py` 中 binding 状态消费。

## 开工校验

- 指定快照：`/mnt/data/zmd_f78r2_snapshot_13dc4e59.zip`
- 实测 sha256：`13dc4e596b5327a8fc888a39d89405553bffb7fb4c993538755580b3accd22af`
- 结果：与任务给定值一致，继续审查。

依赖从 `/mnt/data/zmd_py313_linux_x86_64.zip` 离线解出并用 Python 3.13 venv 安装。快照 zip 展开后无 `.git` 元数据；`data/preprocessed/candidate_placements.json` 不在快照内，测试前按锁文件命令再生。

## Findings

### F-BIND-R1-01 — HIGH — generic output 槽缺少合法“未使用”pattern，导致 false-INFEASIBLE

**位置（原始快照）：** `src/models/binding_subproblem.py:528-566`，`_build_generic_output_domains()`；提取端相关位置 `src/models/binding_subproblem.py:873-889`。

**规则真相：** `specs/03_rule_canonicalization.md` 明确协议核心出口允许部分或全部空置（§3.4.1、§3.5.5），制造单位/端口基本原则允许只使用部分端口、其余空置（§3.5.1），出货口属于全局池化资源而不是预先绑定到每个槽（§3.9.1、§3.9.2）。因此通用输出域应是“每个可见输出槽选择一个外部源商品或 unused”，再由全局精确计数约束决定被征用的槽数。

**问题：** 原模型对每个 `boundary_io` / `protocol_core` 输出槽只创建 `required_generic_outputs.keys()` 中的商品变量，并对这些商品变量 `AddExactlyOne`。如果合法需求少于可用通用输出槽数，模型必须给多余槽也选一个真实商品；随后 `_add_generic_output_requirements()` 又要求每个商品出现次数精确等于需求量，二者组合会把合法“空置输出口”判成 INFEASIBLE。

**最小复现（原始快照）：** 一个协议核心 pose 有两个输出口，但只需要一个 `source_ore` 通用输出口。规则允许一个口出货、一个口空置；原模型返回 INFEASIBLE。

```python
from pathlib import Path
from src.models.binding_subproblem import PortBindingModel

pose = {
    "pose_id": "core_pose_two_outputs",
    "anchor": {"x": 10, "y": 10},
    "occupied_cells": [],
    "input_port_cells": [],
    "output_port_cells": [
        {"x": 10, "y": 9, "dir": "N"},
        {"x": 11, "y": 9, "dir": "N"},
    ],
}
instances = [{
    "instance_id": "core_001",
    "facility_type": "protocol_core",
    "operation_type": "protocol_core",
    "is_mandatory": True,
}]
placement = {"core_001": {
    "pose_idx": 0,
    "pose_id": pose["pose_id"],
    "anchor": pose["anchor"],
    "facility_type": "protocol_core",
}}
model = PortBindingModel(
    placement,
    {"protocol_core": [pose]},
    instances,
    required_generic_outputs={"source_ore": 1},
    required_generic_inputs={},
)
model.build()
print(model.solve(time_limit_seconds=2))
```

原始输出：`INFEASIBLE`。

**soundness 影响：** 这是 binding 过严。Benders 中 `binding_status == "INFEASIBLE"` 会进入 `binding_infeasible_nogood`，对当前 master layout 加 whole-layout nogood 并继续搜索（`src/search/benders_loop.py:5030-5122`）。在 `max_lex(area, min_side)` 认证链里，这类 false-INFEASIBLE 会误杀合法候选布局，进而可能产生 objective 级 false-CERTIFIED。当前冻结工件恰好把需求数配成 52 个通用输出槽满额使用，掩盖了该缺陷；但规则允许未满额，模型不能依赖这个偶然平衡。

**修复：** 给 generic output 槽加入与 generic input 对称的 `"__unused__"` sentinel。`AddExactlyOne` 仍保留，但槽可以合法空置；`_add_generic_output_requirements()` 只对真实商品做精确计数；`extract_port_specs()` 跳过 `None` 和 `"__unused__"`，避免把哨兵传给 routing。

**补丁位置（修复后）：** `src/models/binding_subproblem.py:661-697`、`src/models/binding_subproblem.py:1001-1008`。

**回归：** `src/tests/test_binding.py:672-721`，`test_binding_model_allows_unused_generic_output_slots()`。

---

### F-BIND-R1-02 — HIGH — generic IO / wireless sink loader fail-open，可能放行非 canonical 商品语义或吞掉需求

**位置（原始快照）：** `src/models/binding_subproblem.py:81-91`，`load_wireless_sink_generic_input_slots()`；`src/models/binding_subproblem.py:98-131`，`load_generic_io_requirements()`；构造器二次归一化原位于 `src/models/binding_subproblem.py:151-166` 附近。

**问题：** 原 `load_generic_io_requirements()` 使用 `payload.get(..., {})`，缺少 `required_generic_outputs` 或 `required_generic_inputs` 时静默当空需求处理；同时对值直接 `int(v)`，接受字符串、布尔值、浮点截断、负数等非 schema 数据。它也不校验商品是否与 canonical `commodity_metadata` 的角色一致：generic output 应只能是 `source_kind=external_boundary` 的外部源，generic input 应只能是 `sink_kind=generic_input` 的最终收货商品。原 `load_wireless_sink_generic_input_slots()` 同样 `int()` 截断槽数，`3.5` 会变成 `3`，`true` 会变成 `1`。

**最小复现 A（原始快照缺键静默）：**

```python
import json, tempfile
from pathlib import Path
from src.models.binding_subproblem import load_generic_io_requirements

with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "generic_io_requirements.json"
    path.write_text(json.dumps({"required_generic_inputs": {"steel_block": 1}}), encoding="utf-8")
    print(load_generic_io_requirements(path=path))
```

原始输出：`{'required_generic_outputs': {}, 'required_generic_inputs': {'steel_block': 1}}`。缺失的外部源需求被静默吃掉。

**最小复现 B（原始快照非 canonical sink 被无线吞掉）：**

```python
from src.models.binding_subproblem import PortBindingModel

pose = {
    "pose_id": "box_pose",
    "anchor": {"x": 1, "y": 1},
    "occupied_cells": [],
    "input_port_cells": [],
    "output_port_cells": [],
}
instances = [{
    "instance_id": "box_001",
    "facility_type": "protocol_storage_box",
    "operation_type": "wireless_sink",
    "is_mandatory": True,
}]
placement = {"box_001": {
    "pose_idx": 0,
    "pose_id": "box_pose",
    "anchor": {"x": 1, "y": 1},
    "facility_type": "protocol_storage_box",
}}
model = PortBindingModel(
    placement,
    {"protocol_storage_box": [pose]},
    instances,
    required_generic_outputs={},
    required_generic_inputs={"steel_block": 1},
)
model.build()
print(model.solve(time_limit_seconds=2))
print(model.extract_selection())
print(model.extract_port_specs())
```

原始输出：`FEASIBLE`，selection 中 `box_001:in:0` 被赋为 `steel_block`，而 `extract_port_specs()` 返回 `[]`。这等价于让内部中间品无线离场，routing 只看 port specs，不会重验 canonical sink 语义。

**soundness 影响：** 这是双向风险。缺键或截断可让真实需求消失，导致 false-FEASIBLE；错误商品角色可把内部品当外部源或最终无线 sink，routing 不会兜底。负数还会让精确计数约束形同不可满足或语义漂移，具体表现取决于字段。

**修复：**

- `load_generic_io_requirements()` 顶层必须是对象，必须同时含 `required_generic_outputs` 与 `required_generic_inputs`。
- 每个 section 必须是对象，槽数必须是非布尔、非负、精确 `int`；拒绝保留哨兵商品名 `"__unused__"`。
- 默认 artifact 装载时校验 canonical 角色：generic output 商品必须存在于 `commodity_metadata` 且 `source_kind == "external_boundary"`；generic input 商品必须 `sink_kind == "generic_input"`。空 toy 项目保持可用：当两个 section 都为空时不要求 toy canonical 带 `commodity_metadata`。
- 构造器对显式传入的 generic IO maps 也复用同一非负整数/哨兵校验，但不强制 toy 商品做 canonical 角色校验，以保留已有最小测试 fixture 能力。
- `load_wireless_sink_generic_input_slots()` 改为严格对象/section/整数/non-negative schema 校验，拒绝浮点截断和 bool。

**补丁位置（修复后）：** `src/models/binding_subproblem.py:82-118`、`src/models/binding_subproblem.py:120-260`、`src/models/binding_subproblem.py:291-317`。

**回归：**

- `src/tests/test_binding.py:724-735`：缺 section 必须 fail-closed。
- `src/tests/test_binding.py:738-757`：非整数槽数拒绝。
- `src/tests/test_binding.py:760-792`：`steel_block` 作为 generic output/input 均按 canonical 角色拒绝。
- `src/tests/test_binding.py:795-817`：wireless sink slot count 浮点拒绝。
- `src/tests/test_binding.py:820-839`：保留哨兵 `"__unused__"` 不能作为真实商品。

## Q1-Q5 审查清单与结论

### Q1 domain 构建

核过 `PortBindingModel.__init__()`、`_materialize_pose_optional_instances()`、`_build_fixed_operation_domains()`、`_build_generic_output_domains()`、`_wireless_sink_input_slot_count()`、`_build_generic_input_domains()`，并交叉核对 `src/models/port_binding.py` 的 `enumerate_pose_level_port_bindings_with_cache_info()` 与 `src/preprocess/operation_profiles.py` 的 recipe/profile 派生。

结论：fixed operation 由 recipe/profile 的正槽数与 pose 输入/输出端口集合枚举，unused 物理口通过不出现在 pattern 中表示，方向由候选 pose 的 `input_port_cells` / `output_port_cells` 决定；未发现额外 domain soundness finding。generic input 已有 `__unused__`；generic output 缺 `__unused__` 是 F-BIND-R1-01。pose-optional 的 `protocol_storage_box -> wireless_sink`、`power_pole -> power_supply` 与锁文件语义一致。

### Q2 约束编码

核过 `_add_generic_input_requirements()`、`_add_generic_output_requirements()`、`_ordered_generic_slot_commodities()`、`_add_storage_box_overload_nogoods()`、`build()` 主体，以及 `_add_search_guidance()`。

结论：generic input/output 的真实商品计数语义应是精确 `sum == required`，这一点保留；`required == 0` 强制该商品变量为 0。加入 `__unused__` 后，槽的 ExactlyOne 不再误迫真实商品。`_ordered_generic_slot_commodities()` 仅控制搜索顺序，未删合法解。`_add_search_guidance()` 只调用 `AddDecisionStrategy()`，没有 `Add()` 硬约束，符合 hint-only 合同。

`_add_storage_box_overload_nogoods()` 是硬 nogood，代码注释也承认它是启发式、可能砍可行解；不过 `EXACT_BINDING_USE_OVERLOAD_SEPARATION` 默认关闭，并且 certified env guard 把它列为 known 但非 operational allowlist 变量，非 false 值会被 `_collect_forbidden_certified_master_domain_env_overrides()` 阻断（`src/search/benders_loop.py:511-542`、`758-875`、`1555-1566`）。因此不作为默认 certified soundness finding 报告；direct/exploratory 若手动启用仍不得当 proof object 使用。

### Q3 解提取与 nogood 形状

核过 `extract_selection()`、`extract_port_specs()`、`extract_empty_binding_domain_instances()`、`add_nogood_cut()`。

结论：`extract_selection()` 直接读取 solver 赋值，固定 singleton choice 只作为常量投影加入 selection，未见提取时重写 solver 解。`extract_port_specs()` 对 fixed operation 输出端已排除 routing-free final sink 商品；补丁后 generic output 也排除 `"__unused__"`。`add_nogood_cut()` 对当前 selection 中所有被选 Boolean literal 加 `sum(lits) <= len(lits)-1`，恰好否定当前变量投影；singleton 固定选择无变量，本来就无可替代，不参与 cut 是正确的。

### Q4 状态判读与 Benders 接口

核过 `PortBindingModel.solve()` 与 `BendersController._run_exact_binding_and_routing()` 的 binding 调用点。

结论：`solve()` 将 CP-SAT `OPTIMAL/FEASIBLE` 映射为 `FEASIBLE`，`INFEASIBLE` 映射为 `INFEASIBLE`，其他状态映射为 `TIMEOUT`（`src/models/binding_subproblem.py:890-925`）。Benders 对 `TIMEOUT` 返回 `RUN_STATUS_UNKNOWN`，不会当 INFEASIBLE 消费（`src/search/benders_loop.py:5030-5045`、`5731-5749`）。Benders 对 binding INFEASIBLE 会加当前 whole-layout nogood 并继续 master（`src/search/benders_loop.py:5092-5122`），这正是 F-BIND-R1-01 的放大器，但状态契约本身未见 TIMEOUT/UNKNOWN false-INFEASIBLE。

RAB `extract_routing_aware_certificates()` 的证书是 owner pose 加 blocker pose 的 conflict set；它对 blocker 取 union，可能不最小，但在“empty filtered owner”前提下是保守禁用 owner+所有 blockers 的组合，不比实际更宽。RAB env `EXACT_B1_ROUTING_AWARE_BINDING` 同样不在 certified operational allowlist，默认关闭；本轮未把 RAB 非最小性作为 finding。

### Q5 装载器与数据契约

核过 `load_generic_io_requirements()` 与 `load_wireless_sink_generic_input_slots()`。原始 fail-open 是 F-BIND-R1-02。补丁后 binding 自己的 loader 与构造器 normalize 都改为 fail-closed；默认 artifact 装载会校验 canonical commodity 角色。

范围提示：`src/models/master_model.py` 仍有自己的 `load_generic_io_requirements_artifact()` / `_normalize_generic_io_requirements_payload()`，它不在本轮主要审查对象内。由于 Benders 实际 binding 模型会再次读取并校验 binding artifact，默认 certified 链不会靠 master loader 的宽松行为完成 binding 放行；但若 owner 希望全仓库 loader 风格一致，建议另开 master/preprocess 数据契约面统一收紧。

## 补丁

已生成 unified diff：`/mnt/data/zmd_binding_review_round1.patch`

补丁 sha256：`82cfa51452ef59f52246f4da64ecb373193ff385c88a6ce4300d172fbf2fa0b4`

改动文件：

- `src/models/binding_subproblem.py`
- `src/tests/test_binding.py`

未修改 canonical、mandatory instances、generic_io_requirements、candidate_placements 等冻结工件。

## 冻结工件条款

补丁不涉及冻结工件登记变更。为运行既有测试，本地再生了快照缺失的 `data/preprocessed/candidate_placements.json`：

```bash
python src/placement/placement_generator.py
```

再生结果：

- sha256：`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`
- 字节数：`45,773,799`

与 `PROJECT_LOCK.md` 登记一致；该文件未纳入补丁。

## 自验结果

通过：

```bash
python src/placement/placement_generator.py
sha256sum data/preprocessed/candidate_placements.json
wc -c data/preprocessed/candidate_placements.json
# adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
# 45773799

python -m py_compile src/models/binding_subproblem.py src/tests/test_binding.py
python -m pytest -q -p no:randomly src/tests/test_binding.py src/tests/test_wireless_sink_binding_semantics.py src/tests/test_exact_contract.py
# 107 passed in 7.70s

python -m pytest -q -p no:randomly src/tests/test_master.py
# 226 passed in 9.26s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

尝试但未完成：

```bash
python -m pytest -q -p no:randomly src/tests
```

全量 `src/tests` 在沙盒 300s 命令上限内超时；超时前 pytest 进度已到约 7%，终端未显示 failure。另试 `src/tests/test_master.py src/tests/test_regression.py` 在约 86% 处超时，单独 `src/tests/test_regression.py` 也超时；这些超时看起来是重型回归耗时问题，不是本补丁触发的即时断言失败。已用 binding/wireless/exact_contract/master 专项覆盖本轮改动面。
