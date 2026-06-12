# 终末地 IndustrialPlanner 精确求解器 — F-BIND-R3 binding 建模忠实度面审查

审查对象：`zmd_fbind_r3_snapshot_50360c1d.zip`

开工校验：`sha256sum /mnt/data/zmd_fbind_r3_snapshot_50360c1d.zip` = `50360c1d82504d4de5b5af026c00d8d235db8ded32304b293a3d0d8a7c550893`，与任务指定值一致。只解包并审查该快照，`project/` 作为仓库根。

结论：本轮不是零 finding。R2 的两个定向修复本身基本 sound，但在“proof 输入单一解析/单一快照”泛化穷举中发现 5 个可达 soundness 风险，均已给出补丁与回归测试。冻结工件未改动，无需再生 `candidate_placements.json` 或推进登记 hash。

## Findings

### F-BIND-R3-01 — HIGH — certified binding 仍可重读磁盘需求，master/binding 非同源快照

位置：`src/search/benders_loop.py:4892-4952`, `src/search/benders_loop.py:5851-5857`；原始触发点为主 binding `PortBindingModel(... project_root=...)` 和 overload retry binding 构造后由 binding 子问题自行从磁盘读取 `generic_io_requirements.json`。

R2-01 把 master 侧 loader 委托给 binding loader 后，certified session 在 `ExactSearchSession` 构造时先把 strict/canonical 校验后的 requirements 喂入 `build_exact_core`。但实际 binding 构造仍只传 `project_root`，`PortBindingModel` 会再次从磁盘加载同一工件。若同一 certified 进程中 master core 已建立、随后磁盘工件被替换，master 硬约束/optional 下界和 binding 实际绑定需求可以分裂。这不是“两个 schema 宽松度不同”的旧缝，而是“同一 proof 工件两个时间点、两个快照”的新缝。

修复：新增 `LBBDController._binding_generic_requirements_kwargs()`，certified 模式下把 `self.master.generic_io_requirements` 的 normalized snapshot 显式传入 `PortBindingModel`，主 binding 与 overload retry 统一使用；非 certified/legacy stub 返回空 kwargs 保持旧测试与非证明路径兼容。

回归：`src/tests/test_exact_contract.py:154-221` 覆盖主 binding 与 retry binding 都接收 master snapshot，而不是重读 `project_root`。

### F-BIND-R3-02 — HIGH — master proof 工件 `_load_json` 仍用默认 JSON，可吞重复 key / NaN

位置：`src/models/master_model.py:1949-1958`, `src/models/master_model.py:2161`；原始触发点为 `_load_json()` 默认 `json.load()`，被 `load_project_data()` 用于 `mandatory_exact_instances.json`、`candidate_placements.json`、`canonical_rules.json`。

R2-02 为 binding 需求、无线槽数、canonical commodity metadata 加了 strict JSON，但 certified master 的核心 proof 输入仍通过普通 JSON 解析。重复 key 会 last-write-wins；`NaN`、`Infinity`、`-Infinity` 会被 CPython JSON 接受。对 `mandatory_exact_instances.json` 这类强制实例输入，重复 key 可以静默改写字段；对候选/规则输入也会制造 proof surface 与人工审查可见文本的语义分叉。

修复：在 `master_model.py` 加入同 binding 等价的 strict JSON helper，`_load_json()` 改为 `read_text(encoding="utf-8")` + strict `json.loads(object_pairs_hook=..., parse_constant=...)`。`object_pairs_hook` 覆盖嵌套对象重复 key；`parse_constant` 拒 `NaN`、`Infinity`、`-Infinity`。

回归：`src/tests/test_exact_contract.py:118-151` 覆盖 mandatory artifact 嵌套重复 key 与 candidate artifact 非标准 JSON constant 均 fail-closed。另以审查 probe 验证 binding/master/preprocess 三个 strict helper 都拒绝嵌套重复 key与三类非标准 constant。

### F-BIND-R3-03 — HIGH — `preprocess_plan.json` 仍有宽松解析分叉，utility 槽数可被 `int()` 吞类型

位置：`src/interchange/preprocess_context.py:40-48`, `src/interchange/preprocess_context.py:380-395`, `src/interchange/preprocess_context.py:529-553`；原始触发点为 `load_default_preprocess_context()` / `load_preprocess_context_from_paths()` 默认 JSON，加 `_parse_utility_operation()` 对 `generic_input_slots` / `generic_output_slots` 直接 `int()`。

`preprocess_plan.json` 同时是 operation profile 与 binding 无线槽数的规则源。R2-02 只把 binding 的无线槽数读取切到 strict JSON，但 `preprocess_context` 仍允许重复 key/NaN，并允许字符串、float、bool 经 `int()` 变成槽数。这会造成同一规则源在 binding 与 operation profile 端 schema 不一致；对于无线槽数这类会进入 optional lower bound 的值，属于 proof 输入分叉。

修复：`preprocess_context` 增加 strict JSON helper；默认/显式 path loader 都使用 strict JSON；utility profile 槽数改为 `_strict_nonnegative_int()`，拒 bool、float、str、负数。

回归：`src/tests/test_preprocess_context.py:81-105` 覆盖 path loader 拒嵌套重复 key，并拒字符串/float/bool/负数槽数。

### F-BIND-R3-04 — HIGH — wireless sink generic-input slots 未进入 master core 快照，optional 下界可与 project-root 规则漂移

位置：`src/models/master_model.py:2016-2055`, `src/models/master_model.py:2194`, `src/models/master_model.py:2220-2280`, `src/models/master_model.py:2531-2598`, `src/search/benders_loop.py:1361-1368`, `src/search/benders_loop.py:1571-1588`, `src/search/outer_search.py:1698-1715`, `src/search/exact_campaign.py:1139-1196`, `src/models/exact_coordinate_master.py:5971`。

`infer_certified_optional_lower_bounds()` 原先用 import-time `get_operation_port_profile("wireless_sink").generic_input_slots`。而 R2 的 strict wireless loader 只保障 binding 自己读 `project_root/rules/preprocess_plan.json`。因此 master optional lower bound、outer safe area upper bound、campaign proof helpers、coordinate stats 仍可能用默认仓库 profile，而不是正在验证的 project-root proof 输入。若 synthetic/test project 或未来冻结工件的无线槽数不同，master 下界与 binding capacity 会不一致，构成 false-INFEASIBLE 或 false proof-bound 风险。

修复：`infer_certified_optional_lower_bounds()` 增加 `wireless_sink_generic_input_slots` 参数；`MasterPlacementModel` / `ExactMasterCore` 持有 strict normalized 槽数；certified session 在 generic inputs 非空时从 binding 的 `load_wireless_sink_generic_input_slots(project_root=...)` 读取同一 project-root snapshot，并传给 master core、outer safe-area 计算、campaign helpers、coordinate stats。

回归：`src/tests/test_exact_contract.py:225-253` 证明同一 rules + generic requirements 在 `wireless_sink_generic_input_slots=4` 时 optional area 下界为 9，在 `=2` 时为 18，且 certified 静态下界显式使用该 snapshot。

### F-BIND-R3-05 — HIGH — exact_campaign proof helpers 直接解析 generic IO，绕过 R2 canonical 校验

位置：`src/search/exact_campaign.py:1139-1159`, `src/search/exact_campaign.py:1166-1196`；原始触发点为 `_load_exact_required_optional_lower_bounds()` / `_load_exact_safe_area_upper_bound()` 直接 `_loads_strict_json_object(generic_io_requirements.json)` 后喂入 `infer_certified_optional_lower_bounds()`。

R2-01 的 proof-surface 约束是“单一装载入口，禁止第二解析分叉”。`exact_campaign` 已有 strict JSON，但仍没有使用 `master_model.load_generic_io_requirements_artifact()`，因此缺少 binding loader 的 canonical commodity role 校验、required sections 校验、reserved sentinel 校验。它可能先于或独立于 LBBD session 计算 required optional lower bounds / safe area upper bound，使 public proof-surface helper 对坏 artifact fail-open 到“只要 section 是 mapping 就参与计算”的状态。

修复：`exact_campaign` 导入并使用 `load_generic_io_requirements_artifact(project_root)`，与 master/binding 共用单一 artifact loader；同时接入 project-root wireless slot snapshot，避免 F-BIND-R3-04 的同类漂移。

回归：`src/tests/test_exact_contract.py:324-337` 构造未登记 generic input commodity，`_load_exact_required_optional_lower_bounds()` 现在经 delegated loader fail-closed。

## Q1：R2 修复本身复核

R2-01 定向修复“master loader 委托 binding loader”是 sound 的：`src/models/master_model.py:2006-2014` 仍只委托 `src.models.binding_subproblem.load_generic_io_requirements(project_root=...)`，因此 on-disk artifact 的 strict JSON、required section、strict int、sentinel、canonical role 校验保持同源。`_normalize_generic_io_requirements_payload()` 的生产调用点仅处理已加载 snapshot 或显式传入的 in-memory maps；补丁后 binding 调用也使用 master normalized snapshot，不再依赖第二次磁盘读取。合法 synthetic/test 工程若直接传 in-memory requirements 仍不强迫 canonical artifact 存在；只在 on-disk proof artifact loader 入口 fail-closed。

R2-02 strict JSON helper 的实现语义是 sound 的：`object_pairs_hook` 在 Python JSON decoder 的每个对象层级调用，覆盖嵌套重复 key；`parse_constant` 覆盖 CPython JSON 接受的 `NaN`、`Infinity`、`-Infinity` 三个非标准常量。审查 probe 已验证 binding/master/preprocess 三处 helper 对嵌套重复 key 与三类 constant 均拒绝。

## Q2：proof 工件 × loader 矩阵

| 工件 / 规则源 | certified 消费点 | 审查结果 |
| --- | --- | --- |
| `generic_io_requirements.json` | binding `load_generic_io_requirements`; master `load_generic_io_requirements_artifact`; LBBD certified binding; outer safe-area; exact_campaign proof helpers | 补丁后 on-disk artifact 单一入口为 binding loader；master/session/campaign/outer 共用 normalized snapshot 或 delegated loader。主 binding 与 retry binding 不再重读磁盘。 |
| `rules/preprocess_plan.json` | binding `load_wireless_sink_generic_input_slots`; `preprocess_context`; operation profiles; master optional lower bounds; outer safe-area; exact_campaign helpers | 补丁后 JSON 解析 strict，utility slot schema strict，wireless slot snapshot 显式进入 master core/outer/campaign。 |
| `data/mandatory_exact_instances.json` | master `load_project_data`; exact_campaign `_load_validated_mandatory_exact_instances`; public validators/tests | 补丁后 master 侧 strict JSON + schema；exact_campaign 侧已有 strict object/schema。未发现 certified 链上 A strict/B `.get(default)` 改写强制实例语义的分叉。 |
| `data/candidate_placements.json` | master `load_project_data`; exact_campaign candidate/resume helpers; serializer/hash tooling | 补丁后 master 侧 strict JSON；campaign 侧 strict object parser已存在。深层候选字段仍在 coerce/use 点 fail-closed；未发现 binding/master proof 链的宽松第二解析器。 |
| `rules/canonical_rules.json` | master `load_project_data`; binding canonical commodity role check; `preprocess_context`; exact_campaign helpers | 补丁后 master/preprocess strict；binding role check strict；campaign strict。未发现能让 canonical role 与 master rules 分裂的 certified proof-surface 分叉。 |

本轮仍保留的普通 `json.loads/json.load` 调用经 grep 分类后主要在 telemetry、render/ascii、campaign inspector/triage、phase3b exploratory/preflight、checkpoint-free evaluator、HiGHS evaluator、tests、cut telemetry/persisted payload。它们不位于本轮 OR-Tools LBBD certified binding proof 输入链；`binding_subproblem._load_overload_classification` 仍是普通 JSON，但 overload/RAB 已在任务边界中列为 certified guard 阻断或非本轮 finding，因此未报。

## Q3：strict JSON 之外解析层检查

重复 key：binding/master/preprocess 三个 proof loader helper 均覆盖嵌套对象，probe 通过。

非标准 constants：`NaN`、`Infinity`、`-Infinity` 全部由 `parse_constant` 拒绝，probe 通过。

整数精度：Python JSON 对整数为 arbitrary precision，不存在 JSON 大整数自动转 float 的精度损失；本轮把 generic IO requirements、preprocess utility slot、wireless slot 相关入口均收紧为 strict int，拒 bool/float/string/负数。其他 candidate 坐标/尺寸字段在 schema/coerce 使用点仍以 int 检查或会 fail-closed，未构造出可达语义改写。

Unicode 归一化：未发现 NFC/NFKC 自动归一化。commodity/facility id 是精确字符串匹配 canonical metadata；同形异码不会 alias，只会成为未登记 id 并 fail-closed。若 canonical 自身登记同形异码，那是冻结规则内容质量问题，不是解析层缝。

编码/BOM：proof loaders 使用 `read_text(encoding="utf-8")`。非法 UTF-8 fail-closed；UTF-8 BOM 没有用 `utf-8-sig` 吞掉，JSON parser 会拒绝，偏 fail-closed。未发现 proof 链上同时存在 `utf-8` 与 `utf-8-sig` 对同一冻结工件产生不同语义的可达路径。

## Q4：前轮“无 finding”抽查

抽查 1：fixed pattern / operation profile 端口充足性口径。当前 `preprocess_plan.json` 中 operation profile 总数 21，其中 recipe operation 17、utility operation 4。utility roster 为：`boundary_io -> boundary_storage_port` 槽 0/1，`power_supply -> power_pole` 槽 0/0，`protocol_core -> protocol_core` 槽 0/6，`wireless_sink -> protocol_storage_box` 槽 3/0。17 类 recipe operation 全在 profile 中；本轮未推翻 r2 “fixed pattern 枚举端口数充足”的结论。

抽查 2：`_ordered_generic_slot_commodities` 仅 hint。该符号只在 `src/models/binding_subproblem.py:804-864` 的 `AddDecisionStrategy` 顺序构造中使用，不进入约束、目标、容量或可行性判定。本轮未推翻 r2 结论。

## 回归与自验

已执行：

```text
sha256sum /mnt/data/zmd_fbind_r3_snapshot_50360c1d.zip
# 50360c1d82504d4de5b5af026c00d8d235db8ded32304b293a3d0d8a7c550893

python -m pytest -q -p no:randomly src/tests/test_preprocess_context.py src/tests/test_binding.py src/tests/test_exact_contract.py
# 120 passed in 5.47s

python -m pytest -q -p no:randomly src/tests/test_master.py
# 226 passed in 13.57s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

strict JSON probe
# strict-json-probe-ok
```

未跑完全量 `python -m pytest -q src/tests`；本轮按任务重点执行了 binding / exact_contract / master / preprocess_context 专项与 proof obligation 脚本。

## 冻结工件条款

本补丁只改 Python 源码与测试，未修改 `data/candidate_placements.json`、`data/mandatory_exact_instances.json`、`rules/canonical_rules.json`、`rules/preprocess_plan.json`、hash manifest 或 PROJECT_LOCK。无需冻结工件再生步骤、无需新增期望 sha256/字节数、无需推进登记位置。
