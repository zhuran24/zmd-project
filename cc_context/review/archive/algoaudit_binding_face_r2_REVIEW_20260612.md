# 终末地 IndustrialPlanner exact binding fidelity round 2 review

审查对象：`zmd_fbind_r2_snapshot_6a9c241a.zip`

开工校验：`sha256sum /mnt/data/zmd_fbind_r2_snapshot_6a9c241a.zip` = `6a9c241a88a65ed4fca755c6df5e50c1cfe1d051375856e8a59ecde434e7eb46`，与任务声明一致。ZIP 已按 `project/` 仓库根解包。`data/preprocessed/candidate_placements.json` 复核 sha256 = `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，size = `45773799` bytes。

结论：F-BIND-R1-01 / F-BIND-R1-02 在 `src/models/binding_subproblem.py` 内的修复本身是 sound 的；本轮没有发现 r1 两条修复的残留破口。但在同类数据入口泛化审查中发现 2 个新的 proof-surface fail-open 缝，并已附补丁与回归测试。

补丁文件：`/mnt/data/fbind_r2_patch.diff`

补丁 sha256：`e0dcae1335f7924e9b2062082ab46c029008a2fa09d64782f765bdb61723e3fb`

补丁字节数：`9311`

## Finding F-BIND-R2-01 — HIGH — master 侧 generic_io artifact loader 仍 fail-open，且能在 binding 前改变 certified master 可行域

位置：原始快照 `src/models/master_model.py:1941-1961`，传播到 `src/search/benders_loop.py:1568-1577`、`src/models/master_model.py:1964-1989`、`src/models/master_model.py:2192-2206`、`src/models/master_model.py:5152-5169`、`src/search/benders_loop.py:1356-1371`、`src/search/benders_loop.py:6167-6173`。

问题：`load_generic_io_requirements_artifact()` 仍调用 master 本地 `_normalize_generic_io_requirements_payload()`，后者对两个 section 使用 `.get(...,{})`，对 count 使用 `int(v)`，不拒 bool / float / string / 负数，也不做 canonical role validation。虽然 binding loader 已 fail-closed，但 certified exact session 是先构造 master core，再进入 binding：`ExactSearchSession.create()` 先 `load_generic_io_requirements_artifact(project_root)`，再 `MasterPlacementModel.build_exact_core(... generic_io_requirements=...)`。因此坏 artifact 可在 binding 尚未触达前改变 master 硬约束和 area precheck。

可复现 probe，原始快照下会接受字符串需求并推导出错误的 optional 下界：

```python
import json, shutil, tempfile
from pathlib import Path
from src.models.master_model import load_generic_io_requirements_artifact, infer_certified_optional_lower_bounds

root = Path('.')
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    (tmp / 'data/preprocessed').mkdir(parents=True)
    (tmp / 'rules').mkdir()
    shutil.copy(root / 'rules/canonical_rules.json', tmp / 'rules/canonical_rules.json')
    bad = {
        'required_generic_outputs': {'source_ore': 0},
        'required_generic_inputs': {'valley_battery': '100'},
    }
    (tmp / 'data/preprocessed/generic_io_requirements.json').write_text(json.dumps(bad), encoding='utf-8')
    loaded = load_generic_io_requirements_artifact(tmp)
    rules = json.loads((root / 'rules/canonical_rules.json').read_text())
    print(loaded)
    print(infer_certified_optional_lower_bounds(rules, loaded))
```

原始输出：

```text
{'required_generic_outputs': {'source_ore': 0}, 'required_generic_inputs': {'valley_battery': 100}}
{'protocol_storage_box': 34}
```

真实当前需求只有 2 个 wireless final 槽，`protocol_storage_box` 下界应为 1；坏 artifact 的字符串 `"100"` 被 master 转成 100 后，会把 `sum(protocol_storage_box_pose_vars) >= 34` 注入 certified master。这不是只影响性能：它能让 master 过约束、让 static area lower bound 过大，进而形成 false-INFEASIBLE / 错误候选剪枝。反向的 section 缺失或被截断则会让 master 忽略 required optional lower bound，形成 proof surface 与 binding surface 的输入不一致。

修法：补丁让 `src/models/master_model.py:1986-1993` 的 on-disk artifact loader 委托 `src.models.binding_subproblem.load_generic_io_requirements(project_root=project_root)`，让 master 和 binding 共享同一个 fail-closed artifact 入口；同时将 master 的 in-memory normalizer 改成 strict int / 非负 / reserved sentinel 拒绝，防止测试或复用路径继续通过 `int()` 吞坏值。

回归：`src/tests/test_binding.py:842-891` 新增 master artifact loader 对 loose count 和 noncanonical role 的拒绝测试。

## Finding F-BIND-R2-02 — HIGH — binding 侧 JSON 解析仍接受 duplicate keys / NaN constants，可让坏需求或槽数 last-write-wins

位置：原始快照 `src/models/binding_subproblem.py:81`、`src/models/binding_subproblem.py:143`、`src/models/binding_subproblem.py:231`。

问题：r1 修复已经校验 section 存在、section 类型、strict int、reserved `__unused__`、canonical roles；但 JSON 入口仍用默认 `json.loads()`。Python 默认接受重复 key 且取最后一个值，也接受 `NaN` / `Infinity` 这类非标准 JSON 常量。对 binding proof 来说，重复 key 是实质 fail-open：例如 `generic_io_requirements.json` 内先写真实需求、后重复同名 section 为 `{}`，loader 会只看到最后的空需求；同理 `preprocess_plan.utility_operations.wireless_sink.generic_input_slots` 重复时最后值可把无线槽数悄悄改成 0。这样坏 artifact 不是 fail-closed，而是变成另一个模型。

可复现 probe，原始快照下会接受重复 key 并丢掉前一段需求：

```python
from pathlib import Path
from src.models.binding_subproblem import load_generic_io_requirements, load_wireless_sink_generic_input_slots

p = Path('/tmp/generic_io_requirements.json')
p.write_text('{"required_generic_outputs":{"source_ore":1},"required_generic_outputs":{},"required_generic_inputs":{}}', encoding='utf-8')
print(load_generic_io_requirements(path=p, validate_against_canonical=False))

q = Path('/tmp/preprocess_plan.json')
q.write_text('{"utility_operations":{"wireless_sink":{"generic_input_slots":3,"generic_input_slots":0}}}', encoding='utf-8')
print(load_wireless_sink_generic_input_slots(path=q))
```

原始行为：第一个 loader 返回空 `required_generic_outputs`；第二个 loader 返回 `0`。

修法：补丁在 `src/models/binding_subproblem.py:57-79` 增加 strict JSON helper，拒绝 duplicate keys 和 JSON constants；`load_wireless_sink_generic_input_slots()`、`load_generic_io_requirements()`、canonical role validation 三处改用 strict loader，见 `src/models/binding_subproblem.py:106`、`:168`、`:256`。

回归：`src/tests/test_binding.py:894-929` 新增两个 duplicate-key 拒绝测试。

## Q1：r1 修复本身复核

### F-BIND-R1-01 generic output `__unused__` 哨兵

修复正确。当前基地 generic output 真实需求为 `blue_iron_ore=34`、`source_ore=18`，总和 `R=52`。当前强制 utility 实例为 `boundary_io=46`、`protocol_core=1`；profile generic output slots 为 `46*1 + 1*6 = 52`，总槽数 `S=52`。

binding 模型对每个槽有 ExactlyOne，域为真实 commodity 加 `__unused__`，见 `src/models/binding_subproblem.py:664-703`；对每个真实 commodity 有精确计数 `sum(vars_for_commodity) == required`，见 `src/models/binding_subproblem.py:764-775`。把所有槽的 ExactlyOne 相加得到：

```text
sum(real commodity literals) + sum(__unused__ literals) = S
```

精确计数给出 `sum(real commodity literals) = R`。当前 `S=R=52`，所以 `sum(__unused__ literals)=0`。因此哨兵加入后当前基地满额语义不变，不存在 “哨兵非 0 但计数仍满足” 的解形态。

实证 toy probe 也符合：两个 generic output 槽、需求 2 时 selection 里没有 `__unused__`；需求 1 时正好一个 `__unused__`，且 `extract_port_specs()` 只输出真实 commodity 端口。

### `extract_selection()` / `add_nogood_cut()` 与哨兵

`extract_selection()` 会把 `__unused__` 写入 `selection["generic_outputs"]`，见 `src/models/binding_subproblem.py:927-960`。这是正确的，因为一个 routing 失败的 binding assignment 必须包含“哪个槽不用”这个选择；否则 nogood 会把不同的真实端口位置选择混在一起。

`add_nogood_cut()` 对 selection 中实际存在的 BoolVar 加 `sum(literals) <= len(literals)-1`，见 `src/models/binding_subproblem.py:1045-1061`。这恰好否定当前 assignment 投影，不会扩大成“禁掉同商品任意槽”，也不会缩小成“没有禁掉 unused 位置”。若 selection 只含固定 singleton binding 且没有任何 BoolVar，函数不加 cut，这是无替代域时的正确行为。

哨兵没有漏进 routing/flow：`extract_port_specs()` 对 generic input/output 都跳过 `None` 和 `__unused__`，见 `src/models/binding_subproblem.py:992-1014`；routing 主链只消费 `port_specs`，Benders 对 `selection` 的消费是 conflict summary 和 binding alt nogood，见 `src/search/benders_loop.py:5138-5141`、`:5587-5588`、`:5720-5721`。`heuristic_feasible_finder` 只把 selection 作为诊断/缓存材料，不把它当路由端口。

### F-BIND-R1-02 canonical role validation

角色判据当前恰好正确。当前 `canonical_rules.commodity_metadata` 中 `source_kind == "external_boundary"` 只有 `blue_iron_ore`、`source_ore`；`sink_kind == "generic_input"` 只有 `qiaoyu_capsule`、`valley_battery`。因此 generic output 的合法集正是 external boundary source；generic input 的合法集正是 wireless final sink。

生产 certified 调用点没有显式 map 后门：`src/search/benders_loop.py:4909-4915`、`:5813-5818` 和 `src/search/heuristic_feasible_finder.py:129` 均不传 `required_generic_outputs` / `required_generic_inputs`，所以走 loader + canonical validation。显式传参路径仍只做 normalize、不做 role validation，现阶段只用于测试和 `scripts/p2_14_evaluator/run_eval_v1_baseline.py` 的 dump/evaluator 复跑，不在 proof 主链。补丁还让 master artifact loader 也走同一个 binding loader，补上了 r1 已挂账的 proof-surface 入口。

## Q2：结构假设泛化穷举

实际扫过的结构假设如下。

1. 固定 operation pose-level binding：`supports_exact_pose_level_binding()` 只允许 `generic_input_slots == 0 and generic_output_slots == 0` 的 operation 进入固定端口枚举，见 `src/models/port_binding.py:31-33`；`enumerate_pose_level_port_bindings_with_cache_info()` 遇到 generic slot operation 会拒绝，见 `src/models/port_binding.py:40-49`；固定端口需求超过 pose 端口数时 `_enumerate_side_binding_patterns()` 抛 `ValueError`，见 `src/models/port_binding.py:143-153`。当前 17 类 fixed exact operation 的所有候选 pose 均满足端口数：3x3 机器 in/out 都是 3/3、5x5 是 5/5、6x4 是 6/6，最大 fixed recipe 需求是 input 5 / output 3，没有 current-base false assumption。

2. generic output utility roster：`_build_generic_output_domains()` 当前硬编码 `operation_type in {"boundary_io", "protocol_core"}`，见 `src/models/binding_subproblem.py:674-676`。当前 profile 中 generic output ops 也正好只有 `boundary_io`、`protocol_core`，所以当前数据 sound。扩展风险：如果 owner gate 未来新增 generic-output utility，binding 不会 profile-drive 自动接入，可能把合法扩展误判为 infeasible 或改变搜索域；建议未来加一个 guard，断言 `OPERATION_PORT_PROFILES` 中 `generic_output_slots > 0` 的 operation 集合等于模型支持集合，或者直接 profile-drive 构域。

3. generic input utility roster：`_build_generic_input_domains()` 当前只认 `wireless_sink`，见 `src/models/binding_subproblem.py:718-724`。当前 profile 中 generic input ops 也只有 `wireless_sink`，且槽数来自 strict `preprocess_plan` loader，见 `src/models/binding_subproblem.py:82-136`。扩展风险同上：新增 generic-input utility 需要先改模型或加 fail-closed guard。

4. wireless sink 槽数：没有继续硬编码 3。模型调用 `load_wireless_sink_generic_input_slots()`，且该 loader 现在要求顶层、`utility_operations`、`wireless_sink` section、`generic_input_slots` 全部存在并 strict non-negative int；本轮补丁又加了 strict JSON duplicate-key 拒绝。

5. pose_optional materialization：`POSE_OPTIONAL_OPERATION_BY_TEMPLATE = {"protocol_storage_box": "wireless_sink", "power_pole": "power_supply"}`，见 `src/models/binding_subproblem.py:51-54`。当前 optional roster 与其一致。扩展风险：未来新增 pose-optional template 若有 binding/routing 语义，不在 map 中会被 `_resolve_instance()` 记录 missing 后跳过，见 `src/models/binding_subproblem.py:511-516`，这需要 owner-gate 同步 guard。

6. `_ordered_generic_slot_commodities()`：只影响 search decision order，把 `__unused__` 排到真实 commodity 之后，见 `src/models/binding_subproblem.py:777-787`；它不添加 hard constraint，不影响可行域。

7. storage overload 分类：`EXACT_BINDING_USE_OVERLOAD_SEPARATION` 默认 off，见 `src/models/binding_subproblem.py:422-435`；开启时是 hard nogood，但 certified_exact 环境 guard 会把非默认 proof-semantics EXACT_* env 拦在 session 构造前，见 `src/search/benders_loop.py:836-879`、`:1557-1566`。当前不构成 certified proof 缝。

## Q3：数据入口泛化穷举

实际扫过的 binding 链入口如下。

- `generic_io_requirements.json`：r1 后已有 section/type/count/role/sentinel 校验；本轮补丁补上 strict JSON duplicate-key / NaN constant 拒绝。
- `rules/preprocess_plan.json` 中 `utility_operations.wireless_sink.generic_input_slots`：r1 后已有 fail-closed section/type/count 校验；本轮补丁补上 strict JSON duplicate-key / NaN constant 拒绝。
- `rules/canonical_rules.json` 的 `commodity_metadata`：r1 后用于 role 校验；本轮补丁让该读取也走 strict JSON，避免 role 表 duplicate-key last-wins。
- `master_model.load_generic_io_requirements_artifact()`：本轮确认它确实进入 certified proof surface，并已修复为委托 binding loader。
- `operation_profiles` / `preprocess_context`：`OperationPortProfile` 仍从默认 preprocess context 构建；这属于 preprocess 面入口。binding 当前 proof-critical 的 wireless 槽数不再信任该宽松解析，而是单独 strict 读取。generic op roster 仍有 Q2 里的扩展 guard 风险。
- `placement_solution`：由 master 内部生成；binding 侧使用 `sol["facility_type"]`、`int(sol["pose_idx"])`、pose pool 索引。生产路径不是外部 JSON 直接喂入，未发现本面可达 fail-open。
- `facility_pools` / `candidate_placements.json`：binding 通过 master/exact artifacts 获得。该 artifact 按任务边界不作为本轮 finding 重报；本次仅复核其冻结 hash 与期望一致。

## Q4：r1 “无 finding” 抽查

抽查 1：`_add_search_guidance()`。代码只调用 `AddDecisionStrategy()`，并记录 conflict summary；没有 `Add()`、`AddBoolOr()`、`OnlyEnforceIf()` 等硬约束写入，见 `src/models/binding_subproblem.py:789-849`。结论维持 r1：AI/search guidance 不改变可行域。

抽查 2：`solve()` TIMEOUT 消费链。binding `solve()` 对 OR-Tools OPTIMAL/FEASIBLE 返回 `FEASIBLE`，INFEASIBLE 返回 `INFEASIBLE`，其他状态返回 `TIMEOUT`，见 `src/models/binding_subproblem.py:890-925`。Benders 主链在 binding TIMEOUT 时返回 `RUN_STATUS_UNKNOWN`，而不是当作 infeasible cut，见 `src/search/benders_loop.py:5030-5045`；overload fallback TIMEOUT 同样返回 UNKNOWN，见 `src/search/benders_loop.py:5075-5090`；routing TIMEOUT 也返回 UNKNOWN，见 `src/search/benders_loop.py:5688-5705`。结论维持 r1。

抽查 3：RAB / overload env guard。`EXACT_B1_ROUTING_AWARE_BINDING` 和 `EXACT_BINDING_USE_OVERLOAD_SEPARATION` 在 known env 集合中，但不属于 certified operational allowlist；非 false/default 值会被 `_collect_forbidden_certified_master_domain_env_overrides()` 归类为 proof-semantics blocker，session 构造前抛错，见 `src/search/benders_loop.py:511-542`、`:760-811`、`:836-879`、`:1557-1566`。结论维持 r1。

## 自验

已执行：

```bash
sha256sum /mnt/data/zmd_fbind_r2_snapshot_6a9c241a.zip
# 6a9c241a88a65ed4fca755c6df5e50c1cfe1d051375856e8a59ecde434e7eb46

sha256sum data/preprocessed/candidate_placements.json
# adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0

PYTHONPATH=. python -m py_compile src/models/binding_subproblem.py src/models/master_model.py src/tests/test_binding.py src/tests/test_exact_contract.py
PYTHONPATH=. python -m pytest -q -p no:randomly src/tests/test_binding.py src/tests/test_exact_contract.py src/tests/test_master.py
# 330 passed in 18.25s

PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

全量 `src/tests` 在本沙盒尝试过一次，300s 超时，未拿到完整摘要；因此最终以 binding/exact_contract/master 专项和 proof-obligation gate 覆盖本面。

## 冻结工件条款

本补丁只修改代码与测试：

- `src/models/binding_subproblem.py`
- `src/models/master_model.py`
- `src/tests/test_binding.py`
- `src/tests/test_exact_contract.py`

未修改 `rules/`、`data/preprocessed/`、candidate placements 或任何登记 hash 的冻结工件；无需再生冻结工件，也无需推进 artifact registry/hash 登记。若未来 owner gate 扩展 canonical 内容或新增 generic utility/pose_optional template，应同步增加 Q2 中列出的 profile-driven guard 或显式 roster 断言。
