读完并逐节对照后，我的结论是：这份 v1 不能直接进实现。它的大方向是对的，但当前文字会让实现者在三个位置拿到“假安心”：scope 识别不是机器闭合的，§2 对生产模型输入/异常语义漏项，§6 不能证明 emitter 没有过约束。下面按发现列出。

---

## [BLOCK] 1. §1 “两种形态”分类不成立：存在至少两个“非纯 binding、非累积 nogood”的初始 INFEASIBLE 形态

**设计稿原文引用**

§1.1 写道：“生产 `benders_loop._run_exact_binding_and_routing` 中 binding 判 INFEASIBLE 有两种状态”，随后列出形态①纯 binding 和形态②binding+累积 nogood，见 `binding_pb_sidecar_design_v1.md:23-33`。§1.2 又把 `EXACT_B1_ROUTING_AWARE_BINDING` 写成 out of scope，见 `binding_pb_sidecar_design_v1.md:56-59`。

**源码证据**

生产调用点会在 `EXACT_B1_ROUTING_AWARE_BINDING` 打开时构造 `routing_context`，并传给 `PortBindingModel`，不是纯 binding：`benders_callsite_excerpt.py:19-35`。模型内部在 `routing_context is not None` 时会过滤 binding pattern，并可能把 owner 记为 empty filtered owner：`src_binding_subproblem.py:1007-1027`；generic output slot 也会被 routing-front filter 跳过：`src_binding_subproblem.py:1063-1070`。此外，`EXACT_BINDING_USE_OVERLOAD_SEPARATION` 会在 `build()` 阶段加入硬 nogood，而不是“累积 rejected selection 后”的形态：`src_binding_subproblem.py:787-809`，具体 hard clauses 在 `src_binding_subproblem.py:831-885`。

**为什么会给虚假安心感**

如果 sidecar 只知道“生产报了 binding INFEASIBLE”，但不知道它来自纯模型、routing-aware 初始过滤、overload heuristic，还是 rejected selections 累积，那么一个纯 PB 模型的 CONFIRMED 可能被误贴到另一个命题上。尤其是 routing-aware 初始过滤导致的 empty domain，在外观上很像“首解即 INFEASIBLE”，但语义已经不是 §1.1 的形态①。

**修复文本，替换 §1.1 与 §1.2 开头**

```md
### 1.1 生产侧 binding INFEASIBLE 的机器可区分形态

生产侧不得只按“首解/重解”二分。进入 sidecar 前，必须先给每个 binding solve 记录一个 machine-readable `binding_scope_class`：

- `PURE_BINDING_INITIAL`：`routing_context is None`，`EXACT_BINDING_USE_OVERLOAD_SEPARATION` 未启用或本次 build 明确 `use_overload_separation=False`，`rejected_selection_count == 0`，且本次 INFEASIBLE 来自初始 `solve()`。这是 Phase 1 唯一可复验对象。
- `ROUTING_AWARE_INITIAL`：`routing_context is not None`，即使没有 rejected selections，也已经包含 routing-front 过滤；Phase 1 必须拒绝复验，输出 `OUT_OF_SCOPE`。
- `OVERLOAD_HEURISTIC_INITIAL`：`_add_storage_box_overload_nogoods()` 曾加入 hard nogoods；Phase 1 必须拒绝复验，输出 `OUT_OF_SCOPE`，除非生产已完成无 overload 的 fallback 且记录指向 fallback 模型。
- `REJECTED_SELECTIONS_ACCUMULATED`：至少一个 `add_nogood_cut(selection)` 已加入；这是 binding-routing 交互命题，Phase 1 必须拒绝复验，输出 `OUT_OF_SCOPE`。
- `INPUT_INVALID_OR_EXCEPTION`：生产 build/solve 未形成一个合法 CP-SAT feasibility verdict；sidecar 不得编码为 UNSAT。

### 1.2 Phase 1 的 scope 裁定

Phase 1 只接受 `binding_scope_class == PURE_BINDING_INITIAL` 的样本。任何缺少该字段、字段无法由采集证据复算、或字段与采集内容矛盾的样本，一律输出 `OUT_OF_SCOPE` 或 `INPUT_INVALID`，不得输出 `CONFIRMED`。Phase 1 的 PASS 只表示“同一纯 binding 初始模型在 PB/VeriPB 链上 UNSAT”，不得对 routing-aware、overload、或 rejected-selection 形态外推。
```

---

## [BLOCK] 2. §1.2 “与 I1 完全相同对象”是过度声称：I1 只强制关 overload，不在代码层强制 `routing_context=None`

**设计稿原文引用**

§1.2 写道：“I1 只在独立重建的纯 binding 模型（`use_overload_separation=False`、无 nogood、无 routing_context）INFEASIBLE 时出 `CONFIRMED_INFEASIBLE`”，见 `binding_pb_sidecar_design_v1.md:35-41`；又写“sidecar Phase 1 复验与 I1 完全相同的对象”，见 `binding_pb_sidecar_design_v1.md:43-49`。

**源码证据**

I1 构造 `PortBindingModel` 时把 `binding_kwargs` 原样透传：`src_independent_infeasibility_reverifier.py:155-164`。它确实在 `build(use_overload_separation=False)` 里强制关 overload：`src_independent_infeasibility_reverifier.py:165`。但源码中没有断言或删除 `routing_context`；是否为 `None` 取决于 caller 给不给 `binding_kwargs`。I1 的 routing-exhausted 策略也只是“若 binding 独立不可行则 confirm routing exhaustion”，见 `src_independent_infeasibility_reverifier.py:106-132`。

**为什么会给虚假安心感**

设计稿把 I1 描述成已证明的 scope 锚点，但 I1 源码只证明了“overload 被关掉”，没有证明“routing_context 一定为 None”。如果实现者按这个叙述把 sidecar 的对象定义为“跟 I1 一样”而不采集/验证 scope 字段，就会继承一个未被源码保证的前提。

**修复文本，替换 §1.2 中 I1 对齐段**

```md
现有 I1 是 Phase 1 的保守性参照，但不是完整的 scope oracle。源码层面，I1 只在 `build(use_overload_separation=False)` 上强制关 overload；`binding_kwargs` 会透传给 `PortBindingModel`，因此“无 routing_context”必须由 caller 采集证据或显式断言保证，不能只从 I1 名义推出。

Phase 1 sidecar 定义比 I1 更严格：样本必须携带并通过校验 `routing_context_enabled == false`、`overload_separation_enabled == false`、`rejected_selection_count == 0`、`solve_ordinal == 0`。I1 的结论只能作为对账矩阵第三腿，不能替代 sidecar 自己的 scope gate。
```

---

## [BLOCK] 3. §3.4 输入采集口不足以把 sidecar verdict 绑定到生产 verdict；§7.2 不是开放问题，是 Phase 1 阻断项

**设计稿原文引用**

§3.4 写道：dump 包含 `placement_solution/instances/io requirements/facility_pools_signature`，无 solver verdict 字段，生产判决“从 conflict summary/checkpoint 侧关联”，见 `binding_pb_sidecar_design_v1.md:160-167`。§7.2 把“生产 verdict 与 dump 记录的关联键”列为开放问题，见 `binding_pb_sidecar_design_v1.md:226-227`。

**源码证据**

`_maybe_dump_state()` 只写 `schema_version`、`timestamp`、`placement_solution`、`instances`、`required_generic_outputs`、`required_generic_inputs`、`time_limit_seconds`、`facility_pools_signature`，没有 verdict、scope、solve ordinal、routing_context、overload、nogood 序列、artifact hashes：`src_binding_subproblem.py:1258-1267`。dump 在 `solve()` 入口发生，而不是判决之后：`src_binding_subproblem.py:1273-1275`。生产调用点在 build 后就先更新 summary，再进入后续 binding/routing 循环：`benders_callsite_excerpt.py:37-45`；后续 rejected selections 会继续 `add_nogood_cut()` 并重解：`benders_callsite_excerpt.py:49-75`。

**为什么会给虚假安心感**

没有强关联键时，sidecar 可以在一个 dump 上证明 UNSAT，却被人为或脚本错误关联到另一个生产 INFEASIBLE。更糟糕的是，dump 发生在 solve 入口，天然缺少“这次 solve 最终是什么 verdict、是第几次 solve、之前加过哪些 cut”的事实。

**修复文本，替换 §3.4，并把 §7.2 删除**

```md
### 3.4 输入采集：Phase 1 必须使用可对账的 canonical sample record

Phase 1 不直接把历史 `binding_dumps.jsonl` 当作可 CONFIRMED 的生产样本。进入 sidecar 的样本必须是 `binding_sidecar_sample_v1`，至少包含：

- `sample_id`：由 production run id、iteration、binding solve ordinal、placement hash、artifact hash bundle 组成；
- `production_solver_status`：本次 binding solve 的最终生产 verdict；
- `binding_scope_class`：见 §1.1，Phase 1 只接受 `PURE_BINDING_INITIAL`；
- `solve_ordinal == 0`，`rejected_selection_count == 0`；
- `routing_context_enabled == false`；
- `overload_separation_enabled == false`，以及 fallback 后模型的明确标记；
- `artifact_hashes`：canonical_rules、preprocess_plan、mandatory_exact_instances、generic_io_requirements、candidate_placements 的完整 hash；
- `facility_pools_sha256`：不是 16 hex 前缀，必须是完整 hash；sidecar 重建 pools 后必须复算相等；
- `placement_solution` 与 `instances` 的 canonical JSON hash；
- `producer_code_version` 与 dump schema version。

历史 `EXACT_BINDING_DUMP_STATE` 记录只能作为合成/调试 fixture。缺少上述字段时，sidecar 只能输出 `OUT_OF_SCOPE` 或 `UNKNOWN`，不得输出 `CONFIRMED`。
```

---

## [BLOCK] 4. §2 漏掉大量生产输入校验与“异常 vs INVALID_INPUT vs INFEASIBLE”的边界行为

**设计稿原文引用**

§2 声称列出 “`PortBindingModel` 在 I1 形态下的完整约束语义”，见 `binding_pb_sidecar_design_v1.md:61-64`。输入清单只列出 placement、facility pools、instances、generic requirements、wireless sink K、pose_optional 规则等，见 `binding_pb_sidecar_design_v1.md:65-77`。边界行为只显式写了“侧内槽数超过 port cells 数时 raise”，见 `binding_pb_sidecar_design_v1.md:90-92`。

**源码证据**

generic I/O requirements 有严格规范化：`__unused__` 保留、count 必须是非 bool 的 int、非负，见 `src_binding_subproblem.py:305-329`。还要对 canonical commodity metadata 做角色校验：generic output 必须 `source_kind=external_boundary`，generic input 必须 `sink_kind=generic_input`，见 `src_binding_subproblem.py:332-399`。一旦 generic I/O 非空，所有 canonical `sink_kind=generic_input` commodity 必须以正槽数出现，见 `src_binding_subproblem.py:400-435`。wireless sink K 必须是非 bool 的 int 且非负，见 `src_binding_subproblem.py:78-94`。实例元数据还会检查 missing instance、facility type、pose_idx、operation type、profile/facility mismatch 等，见 `src_binding_subproblem.py:650-755`。`solve()` 遇到 invalid summary 会返回 `INVALID_INPUT` 而不是求解，见 `src_binding_subproblem.py:1273-1288`。但 build 发生在 solve 前，且 `_resolve_pose()` 可直接 raise `IndexError`，见 `src_binding_subproblem.py:977-983`；build 中直接访问 `sol["facility_type"]` 和 `int(sol["pose_idx"])`，见 `src_binding_subproblem.py:995-996`。生产调用点确实先 `build()` 再 solve，见 `benders_callsite_excerpt.py:29-37`。

**为什么会给虚假安心感**

如果 sidecar 把生产会拒绝或 raise 的输入编码成 PB UNSAT，就会把“输入坏了”伪装成“模型不可行”。这正是 INFEASIBLE 证明链最危险的假阳性。

**修复文本，追加到 §2 输入清单后，并替换 §5 的 INPUT_INVALID 定义**

```md
**输入校验与边界行为也是被复验语义的一部分**：

sidecar 在发 OPB 前必须独立执行生产等价的输入校验，并把失败分为 `INPUT_INVALID` 或 `PRODUCTION_EXCEPTION`，不得编码为 UNSAT。

1. `required_generic_outputs` / `required_generic_inputs`：
   - commodity `"__unused__"` 保留，禁止出现在需求工件中；
   - slot count 必须是非 bool 的整数，且非负；
   - generic output commodity 必须存在于 canonical `commodity_metadata` 且 `source_kind=external_boundary`；
   - generic input commodity 必须存在于 canonical `commodity_metadata` 且 `sink_kind=generic_input`；
   - 只要 generic I/O 工件非双空，所有 canonical `sink_kind=generic_input` commodity 必须以正槽数出现在 `required_generic_inputs`。
2. `wireless_sink_generic_input_slots` 必须是非 bool 的整数，且非负。
3. placement/instance metadata：
   - missing instance、非法 pose_idx、pose_idx 越界、facility_type 缺失或不一致、canonical facility 的 operation_type 缺失/未知/与 facility profile 不一致，都必须按生产语义分类；
   - 生产 build 可能在 solve 前 raise。sidecar 不得把这类样本编码成 `EMPTY` 或 generic 计数 UNSAT。
4. 只有通过以上校验并且 scope 为 `PURE_BINDING_INITIAL` 的样本，才能进入 OPB emission。

`INPUT_INVALID` 定义：emitter 或生产采集证据显示输入不满足上述校验；此类样本不是 INFEASIBLE 复验证据。  
`PRODUCTION_EXCEPTION` 定义：生产 build/solve 未形成合法 solver verdict；sidecar 输出 fail-closed 诊断，不生成 UNSAT 证明。
```

---

## [BLOCK] 5. §2 的 pose_optional 规则转述不完整：漏了 `pose_optional::...` 从 instance_id 反推模板的行为

**设计稿原文引用**

§2 输入清单写道：“pose_optional 合成实例规则：`POSE_OPTIONAL_OPERATION_BY_TEMPLATE` = {protocol_storage_box→wireless_sink, power_pole→power_supply}；`ghost_pick` 是非设施 marker，跳过”，见 `binding_pb_sidecar_design_v1.md:75-77`。

**源码证据**

生产逻辑不是只看 `sol["facility_type"]`。如果 placement 中的 instance_id 不在 instances 内，且不是 `ghost_pick`，源码先按 `facility_type` 查映射；若查不到且 `instance_id.startswith("pose_optional::")`，会从 id 中的第二段反推模板，再查 `POSE_OPTIONAL_OPERATION_BY_TEMPLATE`，见 `src_binding_subproblem.py:583-604`。成功后会合成 instance，字段包括 `instance_id`、`facility_type`、`operation_type`、`is_mandatory=False`、`bound_type`、`solve_mode`，见 `src_binding_subproblem.py:605-613`。

**为什么会给虚假安心感**

sidecar 若只按 `facility_type` 合成，会在 `pose_optional::protocol_storage_box::...` 这类 id 上漏掉 wireless_sink，进而漏掉 generic input virtual slots。对某些本来可行/不可行的样本，它可能用另一个模型给出 UNSAT，成为“错题但 proof 很漂亮”的糖衣炮弹。

**修复文本，替换 §2 中 pose_optional 子弹**

```md
- pose_optional / marker 语义：
  - placement 中已有 `instances_by_id` 的 id，不重复合成；
  - `ghost_pick` 是非设施 marker，完全跳过；
  - 对 placement 中缺失 instance metadata 的 id，先用 `sol["facility_type"]` 查 `POSE_OPTIONAL_OPERATION_BY_TEMPLATE`；
  - 若未命中且 `instance_id.startswith("pose_optional::")`，则从 `instance_id.split("::")[1]` 反推 template，再查映射；
  - 当前映射为 `{protocol_storage_box: wireless_sink, power_pole: power_supply}`；
  - 若仍未命中，生产记 `missing_instance_ids`，最终进入 `INPUT_INVALID` / build exception 边界，而不是 UNSAT。
```

---

## [CONCERN] 6. §2 把“域空”当作纯 binding INFEASIBLE 主来源，但当前纯枚举下这个分支几乎是死分支；§6 的“域空类红/正样本”会很假

**设计稿原文引用**

§2 写“域空 → 生产在 `build()` 加 `0 == 1`”，见 `binding_pb_sidecar_design_v1.md:88-89`；又写纯 binding INFEASIBLE 来源穷尽为“(a) 某 instance 域空；(b) generic 计数等式系统不可满足”，见 `binding_pb_sidecar_design_v1.md:107-110`。§6 正向样本要求“域空类/计数鸽笼类各若干”，见 `binding_pb_sidecar_design_v1.md:211-212`。

**源码证据**

`_enumerate_side_binding_patterns()` 在槽数超过 cell 数时直接 raise `ValueError`，不是返回空域：`src_port_binding.py:143-153`。无 required slot 时返回一个空 pattern，而不是空域：`src_port_binding.py:154-155`。左右两侧 pattern 用 `product()` 合成，只要两侧非空就非空：`src_port_binding.py:58-69`。实际 empty domain 分支在 `PortBindingModel` 中存在，但 routing-aware filter 会把原始 domain 过滤到空，见 `src_binding_subproblem.py:1007-1027`；这恰恰是 Phase 1 out of scope。

**为什么会有风险**

如果验收里大量“域空类”是手搓假 fixture，而不是 production 在 `routing_context=None` 下真实可达的样本，就会让 emitter 的 `EMPTY` 约束看起来被覆盖，实际没有覆盖当前 Phase 1 的真实生产路径。这里不是说 `EMPTY` 不能保留，而是不能把它当作当前纯模型的主要 INFEASIBLE 来源。

**修复文本，替换 §2 的结构推论与 §6 的正向样本描述**

```md
**结构推论（当前 2026-07-05 源码）**：在 `routing_context=None` 且 `use_overload_separation=False` 的 Phase 1 纯模型中，binding 域枚举通常不会因“槽数超过物理 cell 数”返回空域；该边界生产会 raise。`EMPTY(i)` 只覆盖生产枚举器实际返回空列表的情况，或未来枚举器语义改变后的保守分支。当前可预期的真实纯 binding UNSAT 主要来自 generic input/output exact-count 系统不可满足。routing-aware filter 导致的 empty filtered domain 不属于 Phase 1。

§6 正向样本改为：≥20 个样本必须按“真实生产可达路径”标注来源；`EMPTY(i)` 样本只有在 production 在 `routing_context=None` 下实际生成 empty domain 时才计入 Phase 1 覆盖。否则只能作为 emitter 单元测试，不计入 production-aligned acceptance。
```

---

## [BLOCK] 7. §3.3 “独立重建”清单里混入了硬编码生产语义；这会让两边共错

**设计稿原文引用**

§3.3 写“重实现（不 import 生产代码）：域枚举组合数学、rate→slots 上取整、pose_optional 合成规则、槽物化规则、上述全部约束生成”，见 `binding_pb_sidecar_design_v1.md:136-142`。§3.3 的“已知对齐风险点”列出 `_rate_to_slots`、`supports_exact_pose_level_binding`、wireless_sink K、pose_optional、generic output 只来自 boundary_io/protocol_core 等，见 `binding_pb_sidecar_design_v1.md:148-156`。

**源码证据**

生产中若干关键语义不是从冻结数据自然读出来，而是硬编码或通过生产模块导出：`POSE_OPTIONAL_OPERATION_BY_TEMPLATE` 与 `NON_FACILITY_PLACEMENT_MARKER_IDS` 是源码常量，见 `src_binding_subproblem.py:56-60`。`CANONICAL_PROFILE_FACILITY_TYPES` 来自 `OPERATION_PORT_PROFILES`，见 `src_binding_subproblem.py:61-63`。`supports_exact_pose_level_binding()` 依赖 `get_operation_port_profile()` 的 generic slot 字段，见 `src_port_binding.py:31-33`。generic output slot 的 operation_type 集合硬编码为 `{boundary_io, protocol_core}`，见 `src_binding_subproblem.py:1057-1059`；generic input 只看 `operation_type == "wireless_sink"`，见 `src_binding_subproblem.py:1101-1107`。

**为什么会给虚假安心感**

“不 import 生产代码”不等于独立。如果 sidecar 手抄这些生产硬编码，生产 builder 在这些常量上的语义 bug 会被 sidecar 复制，最终两边一起给出同一个错误的 UNSAT。这个问题会直击 CONTEXT 里说的“双生稻草人”。

**修复文本，替换 §3.3**

```md
### 3.3 独立重建边界与语义 TCB

sidecar 不 import `src/` 只是最低要求；还必须区分“冻结数据语义”“独立规范语义”和“生产源码硬编码语义”。

Phase 1 前必须建立 `binding_canonical_semantics_v1`，列明以下语义的来源：

- operation profile、rate→slots、generic hub slot 判定：必须来自冻结 canonical/preprocess 数据的可复算规范，或来自单独冻结的 `operation_profiles.json`，不得只手抄 `src.preprocess.operation_profiles` 的当前行为。
- pose_optional 映射、non-facility marker、generic output provider operation set、generic input receiver operation set：若它们是业务规范，必须进入 canonical schema 或独立 spec；若只是生产源码常量，则列入 sidecar TCB，不能声称可防这类 builder 语义错误。
- strict JSON、metadata validation、role validation、slot materialization：必须独立实现，并用 golden fixtures 与边界红测覆盖。

对所有列入 TCB 的硬编码语义，sidecar 报告必须显式写出：`not independently checked by Phase 1`。不得把这些项列为“sidecar 存在的意义”。
```

---

## [BLOCK] 8. §1/§3 把形态② nogood 编码说成“平凡扩展”是错的；生产 `add_nogood_cut()` 只切已有 BoolVar，固定选择和未知项会被忽略

**设计稿原文引用**

§1.2 写形态②的 PB 编码是“平凡扩展（nogood = `Σ lits ≤ n-1` 直接是 PB 不等式）”，见 `binding_pb_sidecar_design_v1.md:51-54`。§3.2 表中也写 `NOGOOD(j) | Σ lits ≤ n_j − 1 | 形态② rejected selection`，见 `binding_pb_sidecar_design_v1.md:131`。

**源码证据**

生产的 `add_nogood_cut()` 只把 selection 中能找到对应 BoolVar 的项加入 literals：domain=1 的 fixed binding choice 没有 BoolVar，因此会被忽略；不存在的 slot/commodity 也会被忽略；只有 `literals` 非空才添加约束，见 `src_binding_subproblem.py:1447-1463`。固定 binding choice 的确是单独存在于 `fixed_binding_choice`，无 BoolVar，见 `src_binding_subproblem.py:1031-1040` 与 `src_binding_subproblem.py:1335-1342`。

**为什么会导致方向性返工**

如果 Phase 2 按设计稿的“全 selection literals”去编码，会比生产模型更强，尤其在大量 fixed choices 时会切掉生产没有切掉的组合，造成 sidecar 证明一个更强模型 UNSAT。那是典型的漂亮假证。

**修复文本，替换 §1.2 形态②段落与 §3.2 的 NOGOOD 行**

```md
形态②不是 Phase 1 的平凡扩展。生产 `add_nogood_cut(selection)` 的语义是：只收集当前模型中真实存在的 BoolVar literals，包括 `binding_vars[instance_id][binding_idx]`、`generic_input_vars[slot_id][commodity]`、`generic_output_vars[slot_id][commodity]`；domain=1 的 fixed binding choice 没有 BoolVar，不进入 cut；selection 中不存在的 slot/commodity 被忽略；若最终 literal 列表为空，则生产不添加任何 nogood。

因此 Phase 2/1.5 若要支持 rejected selections，采集记录必须保存每次 cut 的“生产实际 literal 列表”或足以独立复算该列表的 var-existence 证据。PB 行应为：

`NOGOOD(j)`：对生产实际加入的 literals `L_j` 添加 `Σ_{l∈L_j} l ≤ |L_j|-1`；若 `L_j` 为空，则无约束。任何无法复算 `L_j` 的样本为 `OUT_OF_SCOPE`。
```

---

## [CONCERN] 9. §3.1 varmap/slot id 描述有解析歧义：instance_id 本身可能含 `::`

**设计稿原文引用**

§3.1 定义 `s(slot,c)`，并说 slot id 类似 `{i}:out:{idx}`，变量编号按 `slot_id 字典序, c 字典序`，见 `binding_pb_sidecar_design_v1.md:116-119`；§2 又涉及 `pose_optional` 合成实例，见 `binding_pb_sidecar_design_v1.md:75-77`。

**源码证据**

生产会处理 `instance_id.startswith("pose_optional::")` 的 id，见 `src_binding_subproblem.py:595-599`。generic output slot id 用 `f"{instance_id}:out:{local_idx}"`，见 `src_binding_subproblem.py:1071`；generic input slot id 用 `f"{instance_id}:in:{local_idx}"`，见 `src_binding_subproblem.py:1117`。

**为什么有风险**

如果 varmap 或 witness checker 通过 split `:` 解析 slot id，`pose_optional::protocol_storage_box::...:in:0` 这类字符串会产生歧义。即便 OPB 只用 `xN`，调试、witness、conmap 一旦解析错，就会把 DIVERGED/CONFIRMED 定位到错误语义上。

**修复文本，替换 §3.1 varmap 描述**

```md
`varmap.json` 不得把语义压成需要 split 的字符串。每个变量必须是结构化对象：

- binding var：`{"kind":"binding_choice","instance_id": "...", "binding_idx": k}`
- generic slot var：`{"kind":"generic_input"|"generic_output","slot":{"slot_id":"...","instance_id":"...","direction":"in"|"out","local_idx": n},"commodity":"..."}`

`slot_id` 可作为生产兼容字段保留，但 checker 与对账器只能读结构化字段，不得解析 `slot_id` 字符串。OPB 文件内仍只使用 `x1..xN`。
```

---

## [CONCERN] 10. `facility_pools_signature` 只有 16 hex 前缀且 §5 不要求强校验，不能支撑“同一模型”对账

**设计稿原文引用**

§3.4 写 dump 只有 `facility_pools_signature`，emitter 从冻结工件自行重建 pools，signature 只“用作交叉审计”，见 `binding_pb_sidecar_design_v1.md:160-167`。

**源码证据**

生产模型直接使用 caller 传入的 `facility_pools`，见 `benders_callsite_excerpt.py:29-35` 与 `src_binding_subproblem.py:477-482`。dump 中的 signature 是对 `facility_pools` canonical JSON 的 sha256 前 16 chars，见 `src_binding_subproblem.py:1250-1257`，写入字段见 `src_binding_subproblem.py:1258-1267`。

**为什么有风险**

sidecar 的可复验对象是“生产实际吃到的 facility_pools”，不是“我从冻结文件猜出来的 pools”。16 hex 前缀适合作审计提示，不适合作 CONFIRMED 的 equality guard。§5 也没有要求 signature mismatch 时 fail-closed。

**修复文本，追加到 §3.4 / §5**

```md
facility pools 等价性是 CONFIRMED 前置条件。Phase 1 sample 必须携带完整 `facility_pools_sha256` 与生成该 hash 的 canonicalization 版本。sidecar 从冻结工件重建 pools 后必须复算完整 hash；不相等或缺失时输出 `INPUT_MISMATCH`，不得求解或 CONFIRMED。历史 16-hex `facility_pools_signature` 只能用于调试，不满足 Phase 1 acceptance。
```

---

## [CONCERN] 11. §5 fail-closed 还不够硬：RoundingSat UNSAT exit code=1、VeriPB 失败 exit code=0、proof-consumed 条件没有完整落到协议

**设计稿原文引用**

§5 的 CONFIRMED 条件是：RoundingSat stdout 含 `s UNSATISFIABLE`、proof 文件非空、VeriPB stdout 含 `s VERIFIED UNSATISFIABLE`、stderr 无 `Error:`，见 `binding_pb_sidecar_design_v1.md:193-195`。§4 只提了 “veripb 检查失败时 exit code 仍为 0”，见 `binding_pb_sidecar_design_v1.md:185-187`。

**工具链证据**

`toolchain_notes.md` 明确记录：VeriPB 检查失败时 exit code 仍为 0，必须解析 stdout 结论行，见 `toolchain_notes.md:21-23`。同一文件还说 RoundingSat UNSAT 时进程退出码为 1，同样要解析 `s UNSATISFIABLE`，见 `toolchain_notes.md:34-35`。判 PASS 草案还要求“proof 文件非空且 veripb 实际消费了它”，见 `toolchain_notes.md:48-53`。

**为什么有风险**

这类坑通常不是数学错，而是 wrapper 错：`subprocess.run(check=True)` 会把正确 UNSAT 当异常；只看 exit code 会把 VeriPB 拒绝当成功；不确认 proof digest/mtime/路径，可能检查了旧 proof。它们会造成 UNKNOWN 泛滥或更糟的假 PASS。

**修复文本，替换 §5 的 CONFIRMED 条件**

```md
CONFIRMED 需要全部满足：

1. RoundingSat 进程完成；runner 不得用 exit code 单独判失败，因为 UNSAT 可返回非零。必须解析 stdout 中唯一、完整行 `s UNSATISFIABLE`；若同时出现 SAT/UNKNOWN/多个互斥 status 行，输出 `TOOL_PROTOCOL_ERROR`。
2. proof 文件存在、非空、mtime 晚于 solver 启动时间，且 sha256 被记录。
3. 调用 VeriPB 时必须显式传入同一 OPB path 与同一 proof path；记录 argv、OPB sha256、proof sha256。
4. VeriPB stdout 必须包含唯一、完整行 `s VERIFIED UNSATISFIABLE`；缺失即 `PROOF_REJECTED`，不能用 exit code 兜底。
5. VeriPB stderr 不得包含 error-class 文本；若有 warning-class 文本，记录但不自动 PASS，除非白名单化。
6. checker output 必须能与本次 OPB/proof sha256 对上；否则 `PROOF_NOT_CONSUMED_OR_STALE`。

任一条件不满足，输出 `UNKNOWN` 子码或 `PROOF_REJECTED`，不得 CONFIRMED。
```

---

## [CONCERN] 12. §5 的 DIVERGED 路径依赖“独立 witness checker”，但 §7 又承认 checker 正确性未解决；当前信任地位不自洽

**设计稿原文引用**

§5 写 DIVERGED 条件是 RoundingSat 出 SAT witness，sidecar 用“独立 witness checker”确认后报 DIVERGED，见 `binding_pb_sidecar_design_v1.md:196-198`。§7 又把“witness checker 自身的正确性靠什么背书”列为开放问题，见 `binding_pb_sidecar_design_v1.md:238-239`。

**源材料证据**

上游 Phase 0 要求 canonical 中间格式、constraint ID、canonical evaluator，小规模 exhaustive enumeration 对比 CP-SAT 与 canonical evaluator，见 `upstream_certside_route_research.md:125-133`。当前设计稿没有把这个 Phase 0 evaluator 作为 DIVERGED 的前置条件。

**为什么有风险**

DIVERGED 不是认证证据，但它会触发最高价值告警。如果 witness checker 与 emitter 共用同一套高层语义函数，或者只是按不完整的 §3.2 表验约束，那么它可能把“sidecar 自己错出来的 SAT witness”标成生产 bug。假阳性虽然不是假安心，但会制造方向性返工。

**修复文本，替换 §5 的 DIVERGED 条件**

```md
DIVERGED 是 diagnostic，不是 proof。进入 DIVERGED 必须满足：

1. RoundingSat 给出完整 assignment；
2. witness checker 只读取 `instance.opb`、`varmap.json`、`conmap.json` 与 assignment，逐行检查 OPB 约束，不调用 emitter 的约束生成函数；
3. witness checker 对 `binding_canonical_semantics_v1` 再做一次高层语义检查；该 checker 的测试集必须包含 SAT/UNSAT/invalid/exhaustive 小实例；
4. 若 OPB-level checker 通过但 canonical-level checker 未实现或未通过，状态为 `DIVERGED_OPB_ONLY`，不得写成“生产 bug”；
5. DIVERGED 报告必须同时输出“可能为 production bug / emitter underconstraint / witness checker bug”的 triage 分类。
```

---

## [BLOCK] 13. §6 验收只能抓 underconstraint，不足以抓 overconstraint；20 个 INFEASIBLE 样本没有统计意义

**设计稿原文引用**

§6 正向要求“≥20 个 binding INFEASIBLE 样本 sidecar 全部 CONFIRMED”，红测包括漏 EXO-SLOT、REQ±1、映射串位、漏 pose_optional，见 `binding_pb_sidecar_design_v1.md:211-216`。

**源材料证据**

上游 Phase 0 明确说要 canonical 子问题、独立 emitter、constraint ID，并用“小规模实例 exhaustive enumeration，对比 CP-SAT 与 canonical evaluator；历史 bug 重新注入”，见 `upstream_certside_route_research.md:125-133`。上游 Phase 1 的样本建议是 20 到 50 个历史/合成样本，并且 seeded bugs 示例包括漏互斥、容量符号反转、蕴含方向反转，见 `upstream_certside_route_research.md:135-143`。生产源码中当前纯模型的真实 UNSAT 主要是 generic exact-count；过约束 emitter 在 INFEASIBLE 样本上很容易仍然 UNSAT，例如漏槽、K 过小、错误跳过 provider operation，都不会被“全 CONFIRMED”发现，相关槽生成代码见 `src_binding_subproblem.py:1047-1132`。

**为什么会给虚假安心感**

只拿生产 INFEASIBLE 样本做正向验收，最容易放过“sidecar 比生产更强”的 bug。一个过约束 emitter 可以在所有 INFEASIBLE 样本上漂亮 CONFIRMED，然后在真实生产 FEASIBLE 上也证明 UNSAT，只是你没测。

**修复文本，替换 §6**

```md
## 6. 验收判据

Phase 1 acceptance 不以“20 个 INFEASIBLE 全 CONFIRMED”为充分条件。必须满足以下覆盖矩阵：

1. **Scope gate 样本**：
   - `PURE_BINDING_INITIAL` 可进入 sidecar；
   - routing-aware、overload、rejected-selection、缺 verdict 关联键、facility_pools hash mismatch 均必须 `OUT_OF_SCOPE` / `INPUT_MISMATCH`，不得 CONFIRMED。

2. **正向 UNSAT 样本**：
   - ≥20 个 production-aligned `PURE_BINDING_INITIAL` INFEASIBLE 样本；
   - 每个样本记录 UNSAT 来源分类：generic output count、generic input count、真实 empty domain、其他；
   - `EMPTY` 类只有 production 在 Phase 1 scope 下实际可达时才计入。

3. **正向 SAT/FEASIBLE 样本**：
   - ≥20 个 production FEASIBLE binding 样本，sidecar 必须得到 SAT，并由 witness checker 通过；
   - 包含 fixed binding domain、multi binding domain、generic input/output、pose_optional、zero requirements、empty generic requirements。

4. **Exhaustive 小模型**：
   - 对缩小版 canonical fixtures 穷举所有 placement/requirements 组合，比较 production CP-SAT、canonical evaluator、OPB solver 的 SAT/UNSAT/INPUT_INVALID 三值结果。

5. **红测必须覆盖 underconstraint 与 overconstraint**：
   - underconstraint：漏 EXO-SLOT、REQ 放宽、漏 NOGOOD literal、漏 provider/receiver 过滤；
   - overconstraint：漏 slot、K 减小、把 fixed choice 错编码成 hard literal、把 raise 错编码成 EMPTY、错误加入 routing-aware/overload 约束；
   - mapping：slot/commodity/instance id 串位，特别是 `pose_optional::...`；
   - input-boundary：`__unused__`、bool count、负 count、canonical role mismatch、missing generic input completeness、invalid pose_idx；
   - toolchain：proof 篡改、实例/证明错配、旧 proof、错误 `#equal`、VeriPB exit-code 0 失败、RoundingSat UNSAT exit-code 非零。

6. **样本数解释**：
   - 20 个样本只是 smoke baseline，不给统计保证；
   - acceptance 以覆盖矩阵、mutation kill rate、exhaustive fixture 一致性为准。
```

---

## [CONCERN] 14. §4 与 §7.3 对 `intsize/#equal` 的状态互相矛盾，会误导实现

**设计稿原文引用**

§4 写 `intsize` 语义待钉死，并指向开放问题 §7.3，见 `binding_pb_sidecar_design_v1.md:182-184`。但 §7.3 又写 `intsize` 已钉死：值被 RoundingSat 忽略，`#equal=` 才关键，见 `binding_pb_sidecar_design_v1.md:228-233`。

**工具链证据**

`toolchain_notes.md` 明确记录扩展 OPB 头要求、`#equal` 语义、写错会 solver 出 proof 但 VeriPB 拒绝、`intsize` 被忽略，见 `toolchain_notes.md:24-30`。

**为什么有风险**

这不是数学 scope 问题，但会直接影响 emitter header 和 proof checker 对齐。§4 是实现者最先读到的链路规格，不能保留“待钉死”。

**修复文本，替换 §4 对 OPB 头的 bullet**

```md
- RoundingSat 开 proof-log 时要求扩展 OPB 头：
  `* #variable= N #constraint= M #equal= K intsize= B`。
  2026-07-05 源码+实验已钉死：`intsize` 的值被 parser 吞掉但不参与语义，写 `0` 即可；`#equal=K` 必须精确等于 OPB 中等式行数，因为 proof logger 的约束 ID 初始化会把等式按两个 ID 计。`#equal` 写错属于 fail-detect：solver 可能仍出 proof，但 VeriPB 必须拒绝。
```

---

## [CONCERN] 15. §3.2 约束表没有明确“零变量等式/不等式”的 OPB 表达与 checker 语义

**设计稿原文引用**

§3.2 把 `REQ-OUT(c)` / `REQ-IN(c)` 写成 `Σ_slot s(slot,c) = required_c`，`EMPTY(i)` 写成 `0 ≥ 1`，见 `binding_pb_sidecar_design_v1.md:123-131`。

**源码证据**

生产在没有任何 generic vars 时仍可能调用 `self.model.Add(sum(vars_for_commodity) == required)`，其中 `vars_for_commodity` 可以为空，见 `src_binding_subproblem.py:1134-1145` 与 `src_binding_subproblem.py:1147-1158`。empty binding domain 则添加 `self.model.Add(0 == 1)`，见 `src_binding_subproblem.py:775-784`。OPB 工具链又对 header 等式行数敏感，见 `toolchain_notes.md:24-30`。

**为什么有风险**

零项行在不同 OPB parser 中容易踩语法边角。若 emitter 用一种写法、witness checker 用另一种语义，可能出现 solver/checker 分歧或错误 `#equal` 计数。

**修复文本，追加到 §3.2**

```md
零项约束必须规范化：

- `EMPTY(i)` 用固定的 OPB false row 表达，并在 conmap 标注 `constant_false`；该 row 是否计入 `#equal` 按实际 OPB 形式确定。
- `Σ_empty = 0` 不输出约束，或输出 canonical true row；二者必须在 emitter spec 中固定一种。
- `Σ_empty = k>0` 输出 canonical false row，conmap 标注 `empty_sum_required_positive`。
- emitter、witness checker、`#equal` 计数必须共享同一 OPB-row-level 规范，但不得共享高层业务约束生成代码。
```

---

## [NIT] 16. 文档引用名不一致：§4 写 `NOTES.md`，包内文件叫 `toolchain_notes.md`

**设计稿原文引用**

§4 写“详见 `NOTES.md`”，见 `binding_pb_sidecar_design_v1.md:178`。背景材料列出的文件名是 `toolchain_notes.md`，见 `CONTEXT.md:31-32`。

**建议替换**

把 `NOTES.md` 改为 `toolchain_notes.md`。

---

## [NIT] 17. §6 写“红测 ≥3 类”，但实际列了 4 类

**设计稿原文引用**

§6 写“红测（seeded encoding bug，≥3 类）”，随后列出 (a)-(d) 四类，见 `binding_pb_sidecar_design_v1.md:213-216`。

**建议替换**

改成“≥4 类，且必须覆盖 underconstraint / overconstraint / mapping / input-boundary”。

---

## 我攻击失败的部分

§0 的大方向，也就是“PB/OPB 独立重建 + RoundingSat + VeriPB sidecar”这条路线，我没有找到路线级反证；它与上游报告的 Phase 1 方向一致，见 `upstream_certside_route_research.md:135-143`。§8 的防线关系图在完成上述 scope、采集、验收修正后也基本成立；我没有找到单独的新问题。

---

## 总判定：REJECT

不是因为 PB/VeriPB sidecar 方向错，而是 v1 的 scope gate、生产 verdict 关联、输入校验语义、Phase② nogood 语义、验收矩阵都还没闭合。按当前稿实现，最危险的失败模式不是报 UNKNOWN，而是“证明了另一个模型 UNSAT，然后被人当成生产 binding INFEASIBLE 的证据”。需要先补 Phase 0 canonical sample/schema 与机器可验证 scope，再重写 §1/§2/§3.4/§5/§6 后再进实现。
