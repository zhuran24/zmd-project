# 终末地 IndustrialPlanner 精确求解器 — binding 建模忠实度 round 6 审查报告

审查对象：`zmd_bind_r6_snapshot_ec504afe.zip`

快照 sha256：`ec504afe704b4a1cea6597a3956d7e68fd5adc195961cd4724e69cd354ffb50f`，已在开工前校验匹配。仅解包并审查该快照；文件区其它快照未用于结论。

结论：**本轮零 soundness finding**。

本轮未修改代码，未生成补丁包。以下是 R5 修复确认、单快照族终验清单、binding 枚举/对称数学审查和修复交互抽查。

---

## 1. Q1：F-BIND-R5-01 修复确认

### 1.1 outer domain snapshot 的 proof 输入覆盖面

R5 外层候选域封印在 `src/search/outer_search.py:1756-1782` 创建。它先用 certified loader 读取 mandatory/candidate/canonical 工件，再读取 `generic_io_requirements`，在需要 generic input 时读取 `wireless_sink.generic_input_slots`，并把三类值封入 `certified_outer_domain_snapshot`：

- `artifact_hashes`：来自 `ExactCampaign.artifact_hashes`，其哈希集合在 `src/search/exact_campaign.py:194-205` 和 `src/search/exact_campaign.py:276-286` 定义，覆盖 `mandatory_exact_instances`、`candidate_placements`、`canonical_rules`、`generic_io_requirements` 和可选 `preprocess_plan`。
- `generic_io_requirements`：直接封存 outer 候选域使用的 normalized mapping，见 `src/search/outer_search.py:1757` 和 `src/search/outer_search.py:1771`。
- `wireless_sink_generic_input_slots`：当 `required_generic_inputs` 非空时，从 `rules/preprocess_plan.json` strict 读取，见 `src/search/outer_search.py:1758-1764` 和 `src/search/outer_search.py:1772`。

我从“第四类 proof 输入”角度复核了候选域形状和候选证明语义的来源：

- grid 尺寸、facility template 面积、`min_side_admissibility`、canonical objective 口径来自 `canonical_rules.json`。这些由 `artifact_hashes[canonical_rules]` 封住；`min_side_admissibility` 的实际读取点是 `src/search/outer_search.py:1787`，底层 strict loader 在 `src/search/exact_campaign.py:517-538`。
- mandatory instance 集影响固定占用面积和 master 证明语义，已经由 `artifact_hashes[mandatory_exact_instances]` 封住。
- candidate placement pool 影响 master pose 域和绑定端口几何，已经由 `artifact_hashes[candidate_placements]` 封住。
- optional lower bound 中的 protocol storage box 数量由 `generic_io_requirements` 与 wireless 槽数共同决定，outer 与 session 都使用同一组 snapshot：`src/search/outer_search.py:1777-1782`、`src/search/benders_loop.py:6267-6273`。
- admissibility 参数目前来自 canonical rules；未发现另一个未哈希、会改变 certified frontier 形状的 binding/proof 输入。

判定：R5 snapshot 字段集没有遗漏会改变候选域形状或候选证明语义的第四类 proof 输入。

### 1.2 session 创建/ensure 路径覆盖

生产路径里没有绕过校验的 `ExactSearchSession` 直接构造：全仓非测试搜索 `ExactSearchSession(` 仅命中 `docs/research/...` 的 PoC 和历史 patch 文本；生产代码通过 `create_exact_search_session` 或 `ExactSearchSession.create`。

覆盖点：

- `ExactSearchSession.create` 本身在 `src/search/benders_loop.py:1551-1605` 完成 certified-only 检查、unsafe env guard、strict project load、generic I/O load、wireless 槽数注入、artifact hash 计算和 exact core snapshot 构建。
- `create_exact_search_session` 在 `src/search/benders_loop.py:1608-1637` 先做同一套 unsafe env guard，再委托 `ExactSearchSession.create`。唯一 `except TypeError` 只兼容旧签名，非 `master_search_profile` 相关 TypeError 会重新抛出。
- `outer_search._ensure_exact_session` 在 `src/search/outer_search.py:1389-1402` 只复用既有 session 或调用上述工厂。三个生产 ensure 点都紧跟 `_validate_certified_outer_domain_snapshot_matches_session`：serial precheck `src/search/outer_search.py:1945-1954`，parallel coordinator precheck `src/search/outer_search.py:2108-2117`，serial candidate solve `src/search/outer_search.py:2504-2513`。
- `run_benders_for_ghost_rect` 直接带 session 时，会校验 `project_root/solve_mode/master_search_profile`，不匹配直接 `ValueError`，见 `src/search/benders_loop.py:6205-6219`。

判定：生产证明路径未发现 bypass 构造 session 且跳过 R5 校验的路径。

### 1.3 parallel worker STARTUP_ERROR 链

parallel coordinator 创建 worker pool 时显式传入 expected hashes，见 `src/search/outer_search.py:2226-2236`。expected hash 来源由 `src/search/outer_search.py:1449-1460` 规定：优先使用已建 `ExactSearchSession.artifact_hashes`，否则使用 outer snapshot 的 `artifact_hashes`。

worker 侧在 `src/search/exact_parallel_scheduler.py:193-252` 创建自己的 `ExactSearchSession` 后比较 `session.artifact_hashes` 和 `expected_artifact_hashes`。不一致会抛 `RuntimeError`，被同一函数转成 `STARTUP_ERROR` 消息；pool.start 在 `src/search/exact_parallel_scheduler.py:442-444` 收到 `STARTUP_ERROR` 后 terminate 并抛 `RuntimeError`。

我用直接 monkeypatch probe 验证 mismatch 不会降级继续：

```text
STARTUP_ERROR
RuntimeError: parallel worker ExactSearchSession artifact hashes do not match the coordinator certified frontier snapshot
```

`ExactParallelWorkerPool.__init__` 在 `src/search/exact_parallel_scheduler.py:344-355` 仍允许 `expected_artifact_hashes=None`，但 production certified outer path 会传入 expected hashes。唯一审到的生产样式 omission 是 `src/runtime/checkpoint_free_evaluator.py:479-484`，该 evaluator 明确标记 `proof_source=False`、`exact_campaign_used=False`、`checkpoint_free=True`，见 `src/runtime/checkpoint_free_evaluator.py:108-120` 和 `src/runtime/checkpoint_free_evaluator.py:372-385`，不是 certified proof source。

判定：parallel proof path 的 expected-hash 传递链 fail-closed；缺省只出现在非 proof checkpoint-free 调优器。

### 1.4 校验失败是否被吞

- outer/session snapshot mismatch 的 `RuntimeError` 不在 best-effort telemetry `except` 内；`run_outer_search` 外层只有 `finally` 关闭 worker pool，见 `src/search/outer_search.py:1836` 和 `src/search/outer_search.py:2750-2751`，不会把 RuntimeError 转成继续证明。
- worker `STARTUP_ERROR` 在 pool.start 中立即 raise，见 `src/search/exact_parallel_scheduler.py:442-444`；outer parallel path没有把该异常解释为可用 worker 结果。
- binding snapshot 缺失/格式错误在 `LBBDController._binding_generic_requirements_kwargs` 直接 `RuntimeError`，见 `src/search/benders_loop.py:4892-4936`；不是 `UNKNOWN` 后继续，也不是 silent fallback。
- strict loader 的 `ValueError/TypeError` 在 outer domain load 和 session create 阶段抛出；没有发现将其吞掉并继续 certified proof 的 catch。

判定：R5 seal 失败路径没有被上层误吞后继续。

---

## 2. Q2：单解析/单快照族终验穷举清单

搜索口径覆盖 `generic_io_requirements`、`load_wireless_sink_generic_input_slots`、`wireless_sink_generic_input_slots`、`generic_input_slots`、`artifact_hashes`、`compute_exact_artifact_hashes`，含 `scripts/`、`src/runtime/`、`src/adapters/`、`src/search/phase3b/`、`src/render/`。以下按消费点聚合；测试文件不作为生产消费点，但相关回归在第 5 节列出。

| 消费点 | proof / 非 proof 判读 | 判读依据 |
|---|---:|---|
| `src/models/binding_subproblem.py:101-151` `load_wireless_sink_generic_input_slots` | proof loader | strict JSON，缺失 `utility_operations.wireless_sink.generic_input_slots` fail-closed；certified binding 通过 master snapshot 注入，只有非 certified / 直接 toy path 会在 model 内 fallback 读取。 |
| `src/models/binding_subproblem.py:154-305` `load_generic_io_requirements` | proof loader | strict JSON，要求两个 section，拒绝 `__unused__`，校验 canonical role；master loader 复用它。 |
| `src/models/binding_subproblem.py:310-373` `PortBindingModel.__init__` | proof consumer | certified path 由 `LBBDController._binding_generic_requirements_kwargs` 注入 required maps 和 wireless slots；missing inputs 才走 loader fallback。 |
| `src/models/binding_subproblem.py:709-820` generic slot/domain/requirement constraints | proof consumer | generic input/output domains 使用注入的 required maps；slot count 经 `_wireless_sink_input_slot_count`，需求约束为 exact count。 |
| `src/models/binding_subproblem.py:972-1106` selection/nogood | proof consumer | selection 包含全部 generic slot 选择；nogood 按当前 variable/generic selection 加 `sum(lits) <= n-1`。 |
| `src/models/master_model.py:2006-2013` `load_generic_io_requirements_artifact` | proof loader bridge | 只委托 binding strict loader，不另开宽松解析分叉。 |
| `src/models/master_model.py:2016-2055` optional lower-bound inference | proof consumer | slot count 为显式参数；若 `None` 才用 profile 默认，proof callers 传 snapshot。 |
| `src/models/master_model.py:2219-2278` `MasterPlacementModel.__init__` | proof consumer | 存储 normalized `generic_io_requirements` 和 `wireless_sink_generic_input_slots`，用于 required optional lower bound。 |
| `src/models/master_model.py:2521-2596` `build_exact_core` | proof snapshot owner | exact core 包含 `generic_io_requirements` 与 `wireless_sink_generic_input_slots`。 |
| `src/models/master_model.py:2680-2692` `from_exact_core` | proof snapshot reuse | overlay master 复用 exact core snapshot，不重读文件。 |
| `src/models/master_model.py:5181-5243` protocol storage cardinality | proof consumer | `required_generic_inputs` 和 injected slot count 决定 storage box lower bound。 |
| `src/search/exact_campaign.py:194-205` / `276-286` artifact hash set | proof authority | hash 集合覆盖 mandatory/candidates/canonical/generic_io/preprocess_plan。 |
| `src/search/exact_campaign.py:517-538` min-side admissibility | proof consumer | strict canonical read；canonical file hash 已在 artifact hashes。 |
| `src/search/exact_campaign.py:1139-1200` static lower/upper bound helpers | proof consumer | 通过 shared loader 读 generic I/O，需要 input 时读 wireless slots，然后传入 master bound inference。 |
| `src/search/exact_campaign.py:1490-1504` resume validation | proof guard | campaign resume state artifact hash 必须等于 current hashes，否则 reset。 |
| `src/search/exact_campaign.py:1815-1881` campaign load/create and hashes property | proof authority | 当前 hash 进入 campaign state；outer snapshot 从这里取得 hashes。 |
| `src/search/benders_loop.py:1356-1374` static area lower bound | proof consumer | 接收 caller 注入的 generic I/O 与 wireless slot snapshot。 |
| `src/search/benders_loop.py:1551-1605` `ExactSearchSession.create` | proof snapshot owner | session 构建时读取 strict artifacts、generic I/O、wireless slots、artifact hashes，并生成 exact core。 |
| `src/search/benders_loop.py:1608-1637` `create_exact_search_session` | proof factory | 中央工厂；guard 后委托 session create；无宽松路径。 |
| `src/search/benders_loop.py:4892-4936` `_binding_generic_requirements_kwargs` | proof seal | binding 必须从 master snapshot 取 generic maps；存在 required generic inputs 时必须有 strict int wireless slot snapshot。 |
| `src/search/benders_loop.py:4967-4974` binding model construction | proof consumer | `PortBindingModel` 使用上面的 snapshot kwargs。 |
| `src/search/benders_loop.py:6205-6392` candidate run exact session/core reuse | proof consumer | direct candidate run 使用 session core 的 generic I/O 和 wireless slots；pose-bool fallback 分支也显式传 core snapshot。 |
| `src/search/benders_loop.py:6333-6337` / `6722` cut manager/controller artifact hashes | proof metadata | current hashes 进入 cut manager/controller；persisted exact_safe_cuts 在 certified path 被清空重算，见 `src/search/benders_loop.py:6441-6447`。 |
| `src/search/outer_search.py:1405-1447` outer/session snapshot validator | proof seal | 比较 artifact hashes、generic I/O、wireless slot snapshot；mismatch RuntimeError。 |
| `src/search/outer_search.py:1449-1460` parallel expected hashes | proof seal | worker expected hash 从 real session 或 outer snapshot 派生。 |
| `src/search/outer_search.py:1756-1782` outer domain snapshot | proof owner | frontier domain 使用的 canonical/mandatory/generic/slot 输入都在 hash/value seal 内。 |
| `src/search/outer_search.py:1945-1954` / `2108-2117` / `2504-2513` session ensure sites | proof seal | 每个 ensure 后立即调用 validator。 |
| `src/search/outer_search.py:2226-2236` worker pool construction | proof seal | production parallel certified path 传 `expected_artifact_hashes`。 |
| `src/search/exact_parallel_scheduler.py:193-252` worker startup | proof seal | worker 自建 session 后比较 expected hashes；不一致 STARTUP_ERROR。 |
| `src/search/exact_parallel_scheduler.py:344-355` pool expected hash field | mixed | API 允许 None；certified outer path不缺省，checkpoint-free evaluator 缺省但非 proof。 |
| `src/models/exact_coordinate_master.py:5967-5980` protocol box lower-bound stats | proof consumer | owner 已是 master snapshot；不读文件。 |
| `src/models/exact_coordinate_master.py:6144-6154` group port demand | proof-adjacent | 读取 operation profile 中 generic slot metadata，用于 search guidance/ordering；不是独立 artifact read。 |
| `src/models/pose_bool_exact_master.py:106-114` / `121-132` / `430-463` | proof-sensitive but blocked | 只读 owner snapshot；`EXACT_USE_POSE_BOOL_MASTER` 是 proof-semantics env，certified guard 会 block public certified path。 |
| `src/runtime/checkpoint_free_evaluator.py:108-120` / `230-239` / `479-484` | 非 proof | 明确 `proof_source=False`、`exact_campaign_used=False`；generic I/O 仅用于 local tuning wave，worker pool 未传 expected hashes不影响 certificate。 |
| `src/adapters/industrial_planner/throughput_audit.py:146-149` / `263-268` / `420-428` | 非 proof | throughput audit / adapter 生成或比较 generic I/O；直接 JSON load 不参与 certified exact proof。 |
| `src/preprocess/demand_solver.py:172-247` | artifact generator | 生成 `generic_io_requirements.json`，不是 proof 消费点。 |
| `src/interchange/preprocess_context.py:72` / `130` / `335` / `522-524`，`src/preprocess/operation_profiles.py:28-86` / `151-168` | artifact/profile generator | 读取/生成 preprocess context 和 operation profile；proof path 通过 hashes + strict loaders 使用产物。 |
| `src/cuts/lifecycle.py:322-325` / `955-958`，`src/cuts/replay.py:246-248` | proof metadata guard | cut scope hash schema/validation；certified replay不把 persisted exact_safe_cuts 当 proof source。 |
| `src/cuts/oracles/*` artifact_hashes stamping | proof metadata | `component_reach_oracle.py:176`、`density_envelope_oracle.py:195`、`power_cover_oracle.py:281`、`power_grid_reach_oracle.py:323`、`region_capacity_oracle.py:185`、`shape_packing_hall_oracle.py:260`、`cutset_oracle.py:212`、`port_exposure_oracle.py:309` 仅把 current hashes 写入 cut scope。 |
| `src/models/cut_manager.py:223` / `260` / `497` | checkpoint/cut metadata | stale hash cut 会被跳过；certified path当前不 replay persisted cuts作为 proof。 |
| `src/search/certified_surface.py:632-659` | proof surface/postprocess | public surface 重新计算 current artifact hashes，拒绝 stale provided hashes。 |
| `src/io/delivery_manifest.py:282-300` | delivery postprocess | 交付 manifest 校验 campaign resume state 与 current hashes；不是 solving proof 输入。 |
| `src/search/exact_campaign_inspector.py:185-192` / `220-267` | diagnostic/postprocess | inspector 展示 current hashes 与 resume compatibility；不参与证明。 |
| `src/search/phase3b/**`、`scripts/phase3b/**`、`paths/17_candidate_d_commodity_flow/**`、`scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py` | 非 proof/profiler | 多数使用 `create_exact_search_session` 共享 loader；phase3b/probe 产物不作为 certified proof。 |
| `scripts/phase0_lazy_power_completion_probe.py:177-190` | 非 proof probe | 用 shared loader build exact core 做 lazy power probe；不是 certified campaign。 |
| `scripts/build_current_preprocess_context.py`、`scripts/build_industrial_planner_full_demand_fixture.py` | artifact/fixture generator | 生成或 diff preprocess context/generic I/O；不消费 proof snapshot。 |
| `scripts/preflight_gate.py:53`、`scripts/check_p1_2_proof_obligations.py`、`scripts/gemini_*`、`scripts/build_*review*.py` | verification/static report | hash 常量、proof-obligation 检查或历史报告文本；非 runtime proof consumer。 |
| `src/render/**` | 无命中 | 未发现 `generic_io_requirements` / wireless slot / artifact hash 相关消费点。 |

判定：R3→R4→R5 的单解析/单快照族已经收口。仍存在的直接 JSON 读取或缺省 expected-hash 入口均落在非 proof 诊断、adapter、checkpoint-free 调优、生成器或 postprocess 中；certified proof path 均通过 shared loader / exact session core snapshot / outer snapshot / artifact hash seal。

---

## 3. Q3：binding 枚举与对称数学审查

### 3.1 `add_nogood_cut(selection)` 不重不漏语义

`extract_selection` 在 `src/models/binding_subproblem.py:972-1005` 抽取：固定 binding choice、变量 binding choice、全部 generic input slots、全部 generic output slots，包括 `__unused__`。`add_nogood_cut` 在 `src/models/binding_subproblem.py:1090-1106` 对当前 selection 中有 BoolVar 表示的选择加入 literal，并添加：

```python
self.model.Add(sum(literals) <= len(literals) - 1)
```

这恰好排除“所有当前 variable/generic literal 同时为真”的那一个 CP assignment。固定 choice 没有 BoolVar 时不会进 nogood literal，但如果模型只有固定 choice 且无 generic vars，`LBBDController._binding_has_alternatives` 会返回 False，因为它只看 `binding_vars` / `generic_input_vars` / `generic_output_vars`，见 `src/search/benders_loop.py:5966-5971`。若固定 choice 与 generic vars 混合，固定部分对所有 alternatives 恒定，nogood 排除当前 generic/variable 部分即可。

判定：nogood 不会回到同一个 selection；也不会排除未共享全部当前 literal 的邻近 selection。

### 3.2 binding 侧 cap / 早停语义

`PortBindingModel` 内部未发现 alternatives cap 或早停证明逻辑；`solve()` 只返回 `FEASIBLE`、`INFEASIBLE`、`TIMEOUT`，见 `src/models/binding_subproblem.py:935-970`。binding alternative cap 在外层 LBBD，见 `src/search/benders_loop.py:5786-5817`：当 `EXACT_B1_BINDING_ALT_CAP` 命中且仍有 alternatives 时，返回 `RUN_STATUS_UNKNOWN`，不会加 whole-layout cut。这与 F-BL-R3-01 的“cap 命中只能 UNKNOWN，穷尽证明唯一来源是重解 INFEASIBLE”一致。

已有回归 `src/tests/test_exact_contract.py:3342-3461` 覆盖 cap 命中不落 whole-layout cut。

### 3.3 槽-商品对称性

同 facility 等价 generic 槽的置换在当前模型中是“slot-indexed alternatives”，不是 quotient 后的逻辑等价类。selection 保留 slot id；nogood 排除一个具体置换，镜像置换仍然可行，之后会逐个枚举。该行为可能增加枚举成本，但不会破坏“穷尽”的正确性：穷尽只能来自所有 slot-indexed alternatives 都被 nogood 后 CP-SAT 返回 `INFEASIBLE`。

我用 standalone probe 实证：

```text
output_status INFEASIBLE
output_count 3
output_unused_counts [2, 2, 2]
output_ore_slots [('proto_001:out:0',), ('proto_001:out:1',), ('proto_001:out:2',)]
output_two_status INFEASIBLE
output_two_count 6
output_two_unused_counts [1, 1, 1, 1, 1, 1]
input_status INFEASIBLE
input_count 3
input_unused_counts [2, 2, 2]
input_battery_slots [('box_001:in:0',), ('box_001:in:1',), ('box_001:in:2',)]
input_overdemand_status INFEASIBLE
```

解释：3 个等价 output slots、1 个真实 commodity 时枚举 3 个置换；3 个 slots、2 个真实 commodities 时枚举 6 个置换；3 个 wireless input slots、1 个真实 commodity 时枚举 3 个置换。每次穷尽后最终 `INFEASIBLE`，无重复同一 assignment。

### 3.4 `__unused__` 与非满额配置 R <= S

generic output 域在 `src/models/binding_subproblem.py:709-748` 为每个 slot 创建 `generic_commodities + ["__unused__"]`，并对每个 slot `AddExactlyOne`。wireless generic input 域在 `src/models/binding_subproblem.py:757-795` 同理。需求约束在 `src/models/binding_subproblem.py:796-820` 对每个真实 commodity 加 exact count：`sum(vars_for_commodity) == required`；required=0 时强制该 commodity 的所有 var 为 0。

由于每个 slot ExactlyOne，且真实 commodity 只来自 required map 的 key，`__unused__` 又被 loader 禁止出现在 artifact 需求里，见 `src/models/binding_subproblem.py:231-234`，所以任意总需求 R 与总 slot 数 S 满足 R <= S 时，模型恰好编码“R 个真实商品 + S-R 个空置”；R > S 时 infeasible。上面的 probe 覆盖了 R<S 和 R>S。

判定：不依赖当前 base 52=52 满额巧合；非满额配置语义成立。

---

## 4. Q4：r1-r5 修复交互抽查

### 4.1 strict loader × outer/session snapshot

若 `generic_io_requirements.json` 缺 section、含重复 key、含 `__unused__` 或角色不合法，binding shared loader 在 `src/models/binding_subproblem.py:154-305` 直接失败。outer domain load (`src/search/outer_search.py:1757`) 和 session create (`src/search/benders_loop.py:1572`) 都在候选证明前调用它；没有发现 catch 后降级继续的路径。

### 4.2 wireless slot snapshot drift × session ensure

outer domain 使用 `load_wireless_sink_generic_input_slots` 封存 slot count，session core 再封存一次。三个 session ensure 点均立即比较 snapshot。回归 `test_outer_search_rejects_wireless_slot_drift_between_frontier_and_session` 在 `src/tests/test_exact_contract.py:6212-6307` 构造 outer=3、session=1 的漂移，期望 `RuntimeError`，专项测试通过。

### 4.3 parallel worker hash mismatch × STARTUP_ERROR

coordinator 传 expected hashes，worker 自建 session 后比较；mismatch 变 `STARTUP_ERROR`，pool.start 直接 raise。直接 probe 已验证错误不会被转换成候选 UNKNOWN/INFEASIBLE 结果，也不会留下可消费的强结果。

### 4.4 proof-semantics env guard × binding overload separation

`EXACT_BINDING_USE_OVERLOAD_SEPARATION` 是 known proof-semantics env，但不在 certified operational allowlist；非 canonical true 值会被 `_collect_forbidden_certified_master_domain_env_overrides` block，见 `src/search/benders_loop.py:511-542`、`src/search/benders_loop.py:758-811`、`src/search/benders_loop.py:836-907`。`run_outer_search` 在 artifact/domain load 前 block 并标记 campaign，见 `src/search/outer_search.py:1717-1729`；direct session create 在 `src/search/benders_loop.py:1560-1569` / `1618-1627` fail-closed。该组合不会让 env-gated hard nogood 进入 public certified proof path。

---

## 5. 自验与回归

已执行：

```text
sha256sum /mnt/data/zmd_bind_r6_snapshot_ec504afe.zip
# ec504afe704b4a1cea6597a3956d7e68fd5adc195961cd4724e69cd354ffb50f  /mnt/data/zmd_bind_r6_snapshot_ec504afe.zip
```

```text
PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

专项 pytest：

```text
python -m pytest -q -p no:randomly \
  src/tests/test_exact_contract.py::test_certified_binding_kwargs_use_master_generic_io_snapshot \
  src/tests/test_exact_contract.py::test_certified_retry_binding_receives_master_generic_io_snapshot \
  src/tests/test_exact_contract.py::test_certified_binding_kwargs_require_wireless_slot_snapshot_for_generic_inputs \
  src/tests/test_exact_contract.py::test_certified_static_lower_bound_uses_project_wireless_slot_snapshot \
  src/tests/test_exact_contract.py::test_binding_alt_cap_returns_unknown_without_whole_layout_cut \
  src/tests/test_exact_contract.py::test_outer_search_rejects_wireless_slot_drift_between_frontier_and_session \
  src/tests/test_exact_contract.py::test_v80_certified_exact_env_guard_blocks_known_proof_knob \
  src/tests/test_wireless_sink_binding_semantics.py::test_wireless_sink_virtual_slots_bind_positive_required_inputs \
  src/tests/test_wireless_sink_binding_semantics.py::test_wireless_sink_required_zero_uses_unused_sentinel \
  src/tests/test_wireless_sink_binding_semantics.py::test_wireless_sink_commodity_does_not_reenter_routing_from_producer_output \
  src/tests/test_exact_coordinate_protocol_bounds.py \
  src/tests/test_v94_terminal_protocol_storage_surplus_validation.py
# 12 passed in 2.49s
```

```text
python -m pytest -q -p no:randomly src/tests/test_parallel_scheduler.py
# 13 passed in 2.68s
```

```text
python -m pytest -q -p no:randomly \
  src/tests/test_v84_terminal_layout_max_empty_rect.py::test_v84_exact_artifact_hashes_reject_symlinked_project_authority \
  src/tests/test_v84_terminal_layout_max_empty_rect.py::test_v96_exact_artifact_hashes_reject_symlinked_parent_project_authority \
  src/tests/test_exact_campaign_inspector.py::test_v70_inspector_and_b5a_reject_stale_terminal_after_artifact_hash_mismatch
# 3 passed in 1.94s
```

```text
python -m pytest -q -p no:randomly src/tests/test_binding.py
# 24 passed in 4.66s
```

额外 probe：binding 非满额 / 对称 alternatives / R>S infeasible probe 通过，输出见第 3.3 节；parallel worker expected-hash mismatch probe 输出见第 1.3 节。

全量测试尝试：

```text
python -m pytest -q -p no:randomly src/tests
# 沙盒超时中断；中断前 pytest 输出推进到约 14%，未打印 failure。
```

因此本轮结论基于全仓静态审查、专项回归、proof-obligation 检查和定制 probe；未宣称完成全量 2951 项 pytest。
