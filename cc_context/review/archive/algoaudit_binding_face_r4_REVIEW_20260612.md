# IndustrialPlanner binding 建模忠实度面 r4 审查报告

审查对象：`zmd_audit_snapshot_6867b7ce.zip`

开工校验：快照 sha256 已校验为 `6867b7ce75b5aa61efe9864572cc1b2781ea68d07bcf7efeca28a3ec8ee3487b`，与任务给定值一致。只解包并审查该快照；仓库根为 zip 内 `project/`。

## 总结

本轮发现 **1 个 HIGH soundness finding**，属于 r3 “单解析/单快照”修复的同型残留：generic I/O 需求快照已经从 master 注入 binding，但无线消费槽数 `wireless_sink.generic_input_slots` 仍可由 binding 在建模时重新从 `rules/preprocess_plan.json` 读盘。该缝会让 master optional lower bound 与 binding capacity 在同一 certified session 内看到两个时间点的槽数快照。

已给出补丁与回归测试。补丁后，未再发现第二个 proof 输入链 soundness finding。

## Finding F-BIND-R4-01

Severity: HIGH

修前位置：

- `src/models/binding_subproblem.py:300-313`：`PortBindingModel.__init__` 不接受 `wireless_sink_generic_input_slots` 显式快照，只把 `_wireless_sink_generic_input_slots` 初始化为 `None`。
- `src/models/binding_subproblem.py:732-737`：`_wireless_sink_input_slot_count()` 在首次构造 generic input domains 时，从 `self.project_root / rules / preprocess_plan.json` 重新装载槽数。
- `src/search/benders_loop.py:4892-4915`：r3 新增的 `_binding_generic_requirements_kwargs()` 只注入 `required_generic_outputs` / `required_generic_inputs`，未注入同一 master 持有的 wireless slot 快照。
- `src/search/benders_loop.py:4946-4952` 与 `src/search/benders_loop.py:5851-5856`：主 binding 与 overload retry 都调用同一 helper，因此二者都缺槽数快照。

### 影响

`ExactSearchSession.create()` 已在 session 构造期从 project-root plan 读取 `wireless_sink_generic_input_slots`，并传给 `MasterPlacementModel.build_exact_core()`；master 的 certified optional lower bound 使用这个值。若之后磁盘上的 `preprocess_plan.json` 被篡改或替换，binding 仍会在建模时重新读取新值。于是可能出现：master 用旧槽数判定 `protocol_storage_box` 下界足够，binding 用新槽数判定同一 placement 容量不足并返回 `INFEASIBLE`，从而产生 false nogood / false prune。

这不是 r1/r2/r3 finding 本体的重复，而是 r3 wireless-slot 参数化在 binding 建模消费点遗漏的第五个 hard consumer。

### 复现 probe

在未打补丁的原始快照上运行以下最小 probe：

```bash
cd /mnt/data/zmd_audit_r4/original/project
/mnt/data/zmd_audit_r4/venv/bin/python - <<'PY'
import json, tempfile
from pathlib import Path
from src.models.binding_subproblem import PortBindingModel
from src.models.master_model import infer_certified_optional_lower_bounds

rules = {"facility_templates": {"protocol_storage_box": {"dimensions": {"w": 3, "h": 3}}}}
reqs = {"required_generic_outputs": {}, "required_generic_inputs": {"valley_battery": 3}}
print('master_lb_with_slot_snapshot_3=', infer_certified_optional_lower_bounds(
    rules,
    reqs,
    wireless_sink_generic_input_slots=3,
))

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    (root / 'rules').mkdir(parents=True)
    (root / 'rules' / 'preprocess_plan.json').write_text(json.dumps({
        "utility_operations": {"wireless_sink": {"generic_input_slots": 1}}
    }), encoding='utf-8')
    pose = {
        "pose_id": "box_pose",
        "anchor": {"x": 0, "y": 0},
        "cells": [{"x": 0, "y": 0}],
        "ports": [],
        "operation_type": "wireless_sink",
    }
    model = PortBindingModel(
        {"box_001": {"pose_idx": 0, "pose_id": "box_pose", "anchor": {"x": 0, "y": 0}, "facility_type": "protocol_storage_box"}},
        {"protocol_storage_box": [pose]},
        [{"instance_id": "box_001", "facility_type": "protocol_storage_box", "operation_type": "wireless_sink", "is_mandatory": True}],
        required_generic_outputs={},
        required_generic_inputs={"valley_battery": 3},
        project_root=root,
    )
    model.build()
    print('binding_status_with_late_disk_slot_1=', model.solve(time_limit_seconds=2.0))
    print('binding_input_slots_seen=', len(model.generic_input_slots))
PY
```

实测输出：

```text
master_lb_with_slot_snapshot_3= {'protocol_storage_box': 1}
binding_status_with_late_disk_slot_1= INFEASIBLE
binding_input_slots_seen= 1
```

同一 certified 语义下，master 已按 3 槽/箱证明 1 个协议箱足够；binding 却按后读磁盘的 1 槽/箱构造域并拒绝该 placement。这个反例直接击中单 session 双时间点快照。

### 修法

补丁要点：

1. 在 `src/models/binding_subproblem.py` 增加 `_normalize_wireless_sink_generic_input_slots()`，并让 `load_wireless_sink_generic_input_slots()` 与 `PortBindingModel` 显式入参共用同一 strict 非负整数规范化逻辑。
2. `PortBindingModel.__init__` 新增可选关键字参数 `wireless_sink_generic_input_slots`。传入时使用该快照；未传入时保留旧 loader fallback，供非 certified / legacy fixture 路径使用。
3. `LBBDController._binding_generic_requirements_kwargs()` 在 `solve_mode == "certified_exact"` 且 `required_generic_inputs` 非空时，必须从 `self.master.wireless_sink_generic_input_slots` 取得 strict 非负整数快照并注入 binding kwargs；缺失、bool、非 int、负数均 fail-closed。
4. 主 binding 与 overload retry 已共用该 helper，因此二者一起获得同一 master 快照。
5. 更新 `PROJECT_LOCK.md` 与 `specs/05_facility_instance_definition.md`，把 F-BIND-R4-01 写入单快照条款。

回归：

- `src/tests/test_binding.py::test_binding_uses_injected_wireless_slot_snapshot_over_project_root_plan`：磁盘 plan 写 1 槽，但向 binding 注入 3 槽快照，3 个 input demand 应 FEASIBLE 且生成 3 个虚拟槽。
- `src/tests/test_exact_contract.py::test_certified_binding_kwargs_use_master_generic_io_snapshot`：主路径 kwargs 必须带 `wireless_sink_generic_input_slots`。
- `src/tests/test_exact_contract.py::test_certified_retry_binding_receives_master_generic_io_snapshot`：overload retry kwargs 也必须带同一槽数快照。
- `src/tests/test_exact_contract.py::test_certified_binding_kwargs_require_wireless_slot_snapshot_for_generic_inputs`：certified master 有 generic inputs 但缺槽数快照时 fail-closed。

## Q1：r3 修复本身复核

### R3-01：显式 generic maps 跳过 canonical 角色校验的等价性

结论：generic I/O 需求快照这一部分 sound；无线槽数部分修前有 F-BIND-R4-01，补丁后 sound。

核查链路：

- `ExactSearchSession.create()` 通过 `load_generic_io_requirements_artifact(project_root)` 取得 generic I/O；该函数委托 binding loader，因此默认路径执行双 section、strict JSON、`__unused__` 保留名、canonical commodity role 校验。
- `MasterPlacementModel.__init__` 在 `src/models/master_model.py:2263` 对 `generic_io_requirements` 再规范化并持有 model-owned dict；`build_exact_core()` 再把该快照打包入 `ExactMasterCore`。
- `from_exact_core`/outer master 构造继续传 core 内快照，未发现回磁盘重读 generic I/O 的生产分叉。
- AST mutation scan 结果：生产代码里对 `self.generic_io_requirements` 的赋值只有 `src/models/master_model.py:2263`；未发现 `.update/.clear/.pop/.setdefault` 等 mutation 调用。测试 mock 赋值不算生产路径。
- `_binding_generic_requirements_kwargs()` 注入给 binding 的是 `dict(...)` copy；`PortBindingModel` 即使显式传参，也仍调用 `_normalize_generic_io_requirement_mapping()`，因此 `__unused__` 哨兵保留名与 strict 非负整数约束仍生效。显式路径跳过的 canonical role 校验由 master snapshot 来源承担，且该来源已验证。
- 主 binding 与 overload retry 都调用同一个 helper。补丁后，这个 helper 同时注入 generic maps 与 wireless slot 快照。

### R3-04：wireless 槽数参数化消费点穷举

`get_operation_port_profile("wireless_sink")` 与 `generic_input_slots` 的非测试引用重扫后，hard proof consumers 如下：

- master optional lower bound：`src/models/master_model.py:2030-2055`，由 session/core 注入 `wireless_sink_generic_input_slots`。
- outer safe-area / session lower-bound packaging：`src/search/benders_loop.py:1359-1368`, `src/search/benders_loop.py:1572-1588`, `src/search/benders_loop.py:6231-6335`，使用 exact session core 的槽数快照。
- campaign proof helpers：`src/search/exact_campaign.py:1142-1159`, `src/search/exact_campaign.py:1172-1196`，在有 generic inputs 时从 project-root plan 读取并传给 `infer_certified_optional_lower_bounds()`。
- coordinate stats：`src/models/exact_coordinate_master.py:5971`，使用 owner/master 快照。
- certified binding capacity：修前遗漏，补丁后由 `src/search/benders_loop.py:4892-4936` 注入，并由 `src/models/binding_subproblem.py:319-330`, `src/models/binding_subproblem.py:750-755` 消费。

非 hard proof consumers / 不报项：

- `src/models/master_model.py:2016-2026` 的 import-time profile fallback 仅在 caller 未传槽数时使用；certified session 在有 generic inputs 时已传 project-root snapshot。空 `required_generic_inputs` 时，`None` 与显式槽数路径都返回 `{}` lower bound，probe 通过。
- `src/models/exact_coordinate_master.py:6144-6151` 用 profile 做 search-order demand sorting，不生成硬约束或 proof lower bound。
- `src/models/port_binding.py` 读取 operation profile 判断 pose-level binding support，不是 wireless input capacity consumer。
- `src/models/pose_bool_exact_master.py` 仍可读 profile，但 pose-bool exact master 在 certified gate 下被阻断，不是当前 certified proof surface。
- `src/preprocess/operation_profiles.py` 是 preprocess 生成/默认 profile 定义层，不是同一 certified session 的 proof lower bound 消费点。

空需求 probe：

```text
empty-required-generic-inputs-slot-equivalence-ok
```

### CC 连带测试意图复核

- delivery_manifest stale 测试仍有效：`test_v71_delivery_manifest_rejects_stale_exact_artifact_hash_before_best_result` 实跑通过，篡改物仍走 loader 但 bytes/hash 改变，保留 hash-staleness 防线意图。
- inspector duplicate/stale manifest 防线仍有效：`test_v74_inspector_rejects_duplicate_key_delivery_manifest` 与 `test_v74_certified_surface_rejects_memory_manifest_when_disk_manifest_stale` 实跑通过。
- mock master 增补快照属性没有遮蔽真实缺属性回归：本补丁新增 `test_certified_binding_kwargs_require_wireless_slot_snapshot_for_generic_inputs`，明确覆盖 certified master 有 generic inputs 但缺 `wireless_sink_generic_input_slots` 时必须 RuntimeError。

## Q2：proof 输入链终遍矩阵

| 输入 / 工件 | proof relevance | 当前 loader / snapshot | 审查结论 |
|---|---:|---|---|
| `data/preprocessed/generic_io_requirements.json` | hard binding + master optional lower bound | binding strict loader；master `load_generic_io_requirements_artifact()` 委托同一 loader；certified binding 接 master 快照 | sound |
| `rules/preprocess_plan.json` 中 `wireless_sink.generic_input_slots` | hard master lower bound + binding capacity | strict loader；master/session/project-root snapshot；补丁后 certified binding 接 master 快照 | 修前 F-BIND-R4-01；补丁后 sound |
| `data/preprocessed/mandatory_exact_instances.json` | hard master instance set | master `_load_json` strict parse + schema；campaign hash closure | sound 抽查通过 |
| `data/preprocessed/candidate_placements.json` | hard candidate enumeration | master `_load_json` strict parse；campaign state/hash closure | sound 抽查通过 |
| `rules/canonical_rules.json` | geometry, commodity roles, profiles | master strict parse；binding role validation strict parse；campaign helper strict object parse | sound |
| campaign checkpoint `data/checkpoints/exact_campaign_state.json` | resume proof state | `ExactCampaign.load_or_create()` strict object parse；`_validate_resume_state()` 比对 artifact hashes | sound |
| terminal evidence / final solution / optimal blueprint / delivery manifest | public CERTIFIED surface | delivery manifest strict mapping parse；current artifact hash validation；terminal replay/metadata checks | sound 抽查通过 |
| `commodity_demands.json` | flow diagnostic | `benders_loop.py` 默认 json.load | 不进入 CERTIFIED acceptance/proof hard constraint；不报 |
| `_load_overload_classification` | env-gated binding overload separation | default `json.loads` | `EXACT_BINDING_USE_OVERLOAD_SEPARATION` 不在 certified allowlist，certified 非 false env 被 blocker 拦截；不报 |
| `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH` | warm-start hint | default parse | 仅 hint，不作为 hard constraint/proof acceptance；不报 |

矩阵内抽查：generic I/O loader strict 行为、wireless slot strict/BOM 行为、delivery manifest stale/hash 行为均有实证。

## Q3：三批修复交互复核

- 哨兵逻辑 × 快照注入：`__unused__` 保留名校验位于 `_normalize_generic_io_requirement_mapping()`，显式 maps 与 loader maps 都经过该 normalize；补丁未绕过。
- strict JSON × 委托链：binding、master、shared strict loaders 均使用 duplicate-key rejection 与 non-standard constant rejection。schema 层可能抛 `KeyError`/`TypeError`/`ValueError`，但 proof callers 未见把某类异常吞成默认值的 catch 分叉；实际行为为 fail-closed。
- F-PRE-R8 shared strict_json × binding/master private helpers：未统一实现本身不报；语义 probe 覆盖 nested duplicate keys、`NaN`/`Infinity`、BOM，结果一致 fail-closed。

Strict JSON/BOM probe 输出：

```text
strict-json-probe-ok
```

## Q4：前轮“无 finding”薄点抽查

抽查 1：嵌套重复 key 与非标准 JSON 常量。

- binding `_loads_strict_json`
- master `_loads_strict_json`
- shared `src.io.strict_json.loads_strict_json`

三者均拒绝 `{"outer":{"x":1,"x":2}}` 与 `NaN`/`Infinity`/`-Infinity`。

抽查 2：BOM。

`load_wireless_sink_generic_input_slots()` 通过 `encoding="utf-8"` + strict json 读取；对 `\ufeff{"utility_operations":...}` 实测抛 `ValueError`，没有 utf-8-sig fail-open。

抽查 3：delivery manifest stale/hash 防线。

`test_v71_delivery_manifest_rejects_stale_exact_artifact_hash_before_best_result` 实跑通过；新 fixture 仍能通过 loader，但 bytes/hash 不同，触发 hash mismatch 具体防线。

## 测试记录

环境：Python 3.13 venv，离线 wheel 安装依赖包 `zmd_py313_linux_x86_64.zip`。

已通过：

```bash
python -m pytest -q -p no:randomly \
  src/tests/test_binding.py::test_binding_uses_injected_wireless_slot_snapshot_over_project_root_plan \
  src/tests/test_exact_contract.py::test_certified_binding_kwargs_use_master_generic_io_snapshot \
  src/tests/test_exact_contract.py::test_certified_retry_binding_receives_master_generic_io_snapshot \
  src/tests/test_exact_contract.py::test_certified_binding_kwargs_require_wireless_slot_snapshot_for_generic_inputs
# 4 passed in 3.02s
```

```bash
python -m pytest -q -p no:randomly src/tests/test_binding.py src/tests/test_exact_contract.py src/tests/test_master.py src/tests/test_preprocess_context.py
# 350 passed in 21.28s
```

```bash
python -m pytest -q -p no:randomly \
  src/tests/test_delivery_manifest.py::test_v71_delivery_manifest_rejects_stale_exact_artifact_hash_before_best_result \
  src/tests/test_exact_campaign_inspector.py::test_v74_inspector_rejects_duplicate_key_delivery_manifest \
  src/tests/test_exact_campaign_inspector.py::test_v74_certified_surface_rejects_memory_manifest_when_disk_manifest_stale
# 3 passed in 2.07s
```

```bash
python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

全量测试说明：尝试运行 `python -m pytest -q -p no:randomly src/tests`，15 分钟超时，在约 14% 进度前未出现失败输出；未宣称全量绿。

Patch dry-run：

```bash
cd /mnt/data/zmd_audit_r4/original/project
patch -p1 --dry-run < /mnt/data/F_BIND_R4_wireless_slot_snapshot.patch
# checking file PROJECT_LOCK.md
# checking file specs/05_facility_instance_definition.md
# checking file src/models/binding_subproblem.py
# checking file src/search/benders_loop.py
# checking file src/tests/test_binding.py
# checking file src/tests/test_exact_contract.py
```

## 冻结工件条款

本修复只修改代码、测试、`PROJECT_LOCK.md` 与 `specs/05_facility_instance_definition.md`。未修改任何登记 hash 的冻结工件，未改 `candidate_placements.json` / `canonical_rules.json` / delivery artifact bytes，因此无需再生冻结工件，也无新的 sha256/字节数登记位置。

## 交付补丁

Unified diff: `F_BIND_R4_wireless_slot_snapshot.patch`

Patch sha256: `bdc4e2cff7f1d4989f3cdf98ea44df3b5cb67302cc31d9bccb0888a19efef444`

Patch bytes: `18700`
