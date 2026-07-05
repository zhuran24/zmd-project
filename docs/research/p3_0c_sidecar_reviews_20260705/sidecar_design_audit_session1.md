行号均按解包后的文件计。§0/§8 我攻击失败：路线目标本身和背景材料一致，问题主要集中在 §1 到 §7 的 scope、输入契约、语义完整性与验收强度。

## [BLOCK] 1. §3.4 直接消费生产 dump，破坏“独立重建”的核心隔离

设计稿原文说两件事互相打架：一边要求“独立重建，不从生产代码导出、不 import 生产 builder”（`binding_pb_sidecar_design_v1.md:L16-L18`），另一边说“Phase 1 直接消费该 dump”（`binding_pb_sidecar_design_v1.md:L160-L167`）。

源码证据：dump 不是原始冻结输入的透明镜像，而是在 `PortBindingModel.__init__()` 已经跑完生产语义后才从对象内部吐出。构造函数先执行 `_materialize_pose_optional_instances()` 和 `_validate_placement_instance_metadata()`（`src_binding_subproblem.py:L580-L582`），dump 又写出 `instances=list(self.instances_by_id.values())`、已规范化后的 `required_generic_outputs/inputs` 和 `facility_pools_signature`（`src_binding_subproblem.py:L1258-L1267`）。这意味着 sidecar 如果把 dump 里的 `instances` 和需求映射当权威输入，就会继承生产侧的 pose_optional 合成、实例规范化、需求规范化错误。狼披着另一件羊毛衫，还是那头狼。

这会导致虚假安心感：生产 builder 若把某个 pose_optional 实例合成错了，dump 会把“合成错后的实例表”交给 sidecar；sidecar 即使完全不 import 生产代码，也是在复验生产加工后的世界，而不是冻结工件定义的世界。

修复文本，替换 §3.4：

> ### 3.4 输入采集边界：dump 只能做定位索引，不得做语义权威
>
> Phase 1 sidecar 的权威输入必须是 canonical input bundle：五个冻结工件的原始字节、其全长 sha256、原始 `placement_solution`、原始 `source_instances`、项目版本/工具版本、以及生产侧本次 solve 的 scope 标志。`EXACT_BINDING_DUMP_STATE` 产生的 `instances`、已规范化 generic requirements、`instances_by_id`、`synthesized_instances` 等字段一律只能作为审计对照，不得作为 emitter 的语义输入。
> emitter 必须从原始冻结字节独立执行：strict JSON 解析、generic I/O 校验、pose_optional 合成、facility_pools 重建、operation profile 推导、binding 域枚举和约束生成。若 dump 字段与 sidecar 独立重建结果不一致，样本判为 `INPUT_DIVERGENCE`，不得进入 `CONFIRMED`。在没有 canonical input bundle 的真实样本上，Phase 1 只允许输出 `NOT_REPLAYABLE`，不得输出 `CONFIRMED`。

## [BLOCK] 2. §1/§3.4 没有协议级 scope guard，PASS 仍可能被贴到错误形态上

设计稿原文说：“Phase 1 判 PASS 不得外推到形态②”（`binding_pb_sidecar_design_v1.md:L51-L54`），但同一节又打算用无 verdict 的 dump 关联生产判决：“dump 无 solver verdict 字段……从 conflict summary/checkpoint 侧关联”（`binding_pb_sidecar_design_v1.md:L163-L165`），并把关联键问题放进开放问题（`binding_pb_sidecar_design_v1.md:L224-L227`）。

源码证据：生产调用点在 build 前可启用 routing-aware binding filter：`EXACT_B1_ROUTING_AWARE_BINDING` 会构造 `routing_context` 并传给 `PortBindingModel`（`benders_callsite_excerpt.py:L19-L35`）。生产 build 默认还会读取 `EXACT_BINDING_USE_OVERLOAD_SEPARATION`，可能添加 hard nogood（`src_binding_subproblem.py:L787-L809`）。routing 侧拒绝后会调用 `add_nogood_cut(selection)`（`benders_callsite_excerpt.py:L49-L76`），overload fallback 还会重建模型并回放 rejected selections（`benders_callsite_excerpt.py:L84-L101`）。I1 的真正确认入口也不是“看到某个 layout hash 就确认”，而是显式接收 `binding_exhausted` / `routing_exhausted` 并在未满足条件时 fail closed（`src_independent_infeasibility_reverifier.py:L69-L80`、`L92-L133`）。

当前协议没有要求样本携带“首解 / 无 nogood / 无 routing_context / overload off / solver_status=INFEASIBLE”的不可伪造标志。用 placement hash 去关联 conflict summary 是不够的：同一个布局可以经历首解、加 cut 后重解、fallback 重解、routing-aware 过滤重解。没有 solve ordinal 和 scope 标志，PASS 的标签会粘错瓶子。

修复文本，替换 §1.2 末尾和 §3.4 中 verdict 关联描述：

> Phase 1 样本进入 sidecar 前必须通过 scope gate。只有同时满足以下字段时才允许判 `CONFIRMED`：`binding_solve_ordinal == 0`、`production_binding_status == "INFEASIBLE"`、`routing_context_enabled == false`、`overload_separation_enabled == false`、`nogood_count_before_solve == 0`、`binding_rejected_selection_count == 0`、`use_overload_separation == false`、`routing_exhausted == false` 或者 `routing_exhausted == true` 但本次确认声明为“由纯 binding infeasible 推出 whole-layout infeasible”。
> 任一字段缺失或不满足，样本判 `OUT_OF_SCOPE`，不得输出 `CONFIRMED`。placement hash 只可作为辅助索引，不可作为 verdict 关联的唯一键；真实样本的关联键必须至少包含 `sample_id`、`iteration`、`binding_solve_ordinal`、生产 solver verdict、scope flags、artifact hashes 和 model-build config。若当前生产 dump schema 无法提供这些字段，Phase 1 对真实 dump 只能做 replayability 审计，不得做生产 verdict 对账。

## [BLOCK] 3. §2 漏掉 generic I/O 的 canonical role 与完备性校验

设计稿原文只把 generic I/O 描述成两个需求映射：“`required_generic_outputs` / `required_generic_inputs`：commodity → 精确槽数”（`binding_pb_sidecar_design_v1.md:L71-L74`），约束语义也只写了槽 ExactlyOne 与计数等式（`binding_pb_sidecar_design_v1.md:L94-L103`）。

源码证据：生产模型不只是读两个 mapping。它先拒绝 `__unused__`、bool、非整数、负数（`src_binding_subproblem.py:L305-L329`），然后用 canonical_rules 校验 output commodity 必须存在且 `source_kind=external_boundary`（`src_binding_subproblem.py:L370-L383`），input commodity 必须存在且 `sink_kind=generic_input`（`src_binding_subproblem.py:L385-L398`）。更重的是，非空 generic I/O 工件必须以正槽数覆盖所有 canonical `sink_kind=generic_input` commodity；漏声明或零槽数会抛 `ValueError`（`src_binding_subproblem.py:L400-L435`）。构造函数无论 requirements 是从文件加载还是调用方传入，都会执行这套校验（`src_binding_subproblem.py:L487-L523`）。

这个遗漏会把生产侧应当拒绝的输入编码成 PB 可满足/不可满足问题，甚至可能给出 `CONFIRMED`，而生产根本不会给出可复验的纯 binding INFEASIBLE。属于 BLOCK。

修复文本，追加到 §2 “输入”后：

> **输入有效性校验也是被复验语义的一部分。** sidecar 在生成 PB 前必须独立复现 generic I/O 校验：`__unused__` 是保留 sentinel，禁止出现在 requirements；槽数必须是非 bool 的整数且非负；每个 required generic output 必须在 `canonical_rules.commodity_metadata` 中存在且 `source_kind == "external_boundary"`；每个 required generic input 必须存在且 `sink_kind == "generic_input"`；只要 generic I/O requirements 非双空，就必须以正槽数覆盖 canonical 中所有 `sink_kind == "generic_input"` 的 commodity。任一校验失败时输出 `INPUT_INVALID`，不得发 OPB，不得把错误编码成 UNSAT。

## [BLOCK] 4. §2 对 placement / instance 元数据边界漏转述，异常、INVALID_INPUT、空域被混在一起

设计稿原文只提到“`ghost_pick` 是非设施 marker，跳过”和 pose_optional 的两条映射规则（`binding_pb_sidecar_design_v1.md:L75-L77`），以及一个边界：“侧内槽数超过 port cells 数时……raise，不是空域”（`binding_pb_sidecar_design_v1.md:L90-L92`）。

源码证据：生产侧的输入边界远不止这一条。缺失 instance 会进入 `missing_instance_ids`（`src_binding_subproblem.py:L625-L629`、`L888-L899`）。metadata 校验包括 solution facility_type 缺失、pose_idx 缺失/布尔/不可转 int、pose_idx 越界、instance facility_type 缺失或不匹配、operation_type 缺失/未知、operation profile facility_type 不匹配（`src_binding_subproblem.py:L650-L759`）。`solve()` 在发现 invalid binding input 时直接返回 `INVALID_INPUT`，不调用 CP-SAT（`src_binding_subproblem.py:L1273-L1288`）。但 build 阶段本身还可能先因为 `sol["facility_type"]`、`int(sol["pose_idx"])`、`_resolve_pose()` 越界而抛异常（`src_binding_subproblem.py:L985-L997`、`L977-L982`）。

所以“raise vs 空域 vs INFEASIBLE”的分界在设计稿里严重缩小了。sidecar 若只实现 port-cell insufficient 这一种 raise，会把大量生产 INVALID_INPUT / exception 场景错误编码为 PB。

修复文本，替换 §2-A 末尾的边界说明：

> **边界行为：输入无效优先于 PB 编码。** sidecar 必须在发 OPB 前独立执行 placement/instance 校验：忽略 `ghost_pick`；对缺失实例，仅当 facility_type 或 `pose_optional::<template>::...` 可映射到 `POSE_OPTIONAL_OPERATION_BY_TEMPLATE` 时才合成，否则 `INPUT_INVALID`；校验 solution facility_type、pose_idx 类型与范围、instance facility_type、operation_type 存在性、operation profile 存在性与 facility_type 一致性。`pose_idx` 缺失、bool、不可转 int、越界，未知 canonical operation，facility mismatch，缺失 canonical instance metadata 等均不得编码成 UNSAT。
> `enumerate_pose_level_port_bindings` 中“侧内所需槽数 > physical port cell 数”是 build-time exception，sidecar 同样归为 `INPUT_INVALID`。只有生产模型确实会构造 `empty_binding_domain_instances` 并添加 `0 == 1` 的场景，才允许编码 `EMPTY(i)`。

## [BLOCK] 5. §2/§3 声称完整转述，但关键语义委托给未纳入核对源的模块

设计稿原文说 §2 是“第一手源码语义，sidecar 必须独立重达”，并声称 profile 槽数由 `_rate_to_slots` 推导（`binding_pb_sidecar_design_v1.md:L61-L88`），§3 又把 `rate→slots` 和 strict JSON 作为重实现项（`binding_pb_sidecar_design_v1.md:L136-L142`）。

源码证据：`src_port_binding.py` 并没有给出 operation profile 生成语义，它直接 import `get_operation_port_profile`（`src_port_binding.py:L16-L17`），`supports_exact_pose_level_binding()` 完全依赖 profile 的 `generic_input_slots/generic_output_slots`（`src_port_binding.py:L31-L33`），域枚举依赖 `profile.input_slots` 和 `profile.output_slots`（`src_port_binding.py:L44-L68`）。`src_binding_subproblem.py` 也 import `OPERATION_PORT_PROFILES` 和 `get_operation_port_profile`（`src_binding_subproblem.py:L35-L38`），用 profile 集合定义 canonical facility types（`src_binding_subproblem.py:L61-L63`），并在 metadata 校验中再次取 profile（`src_binding_subproblem.py:L731-L753`）。strict JSON 同样只是 import 进来，实际行为不在包内：`load_strict_json` / `loads_strict_json` 来自 `src.io.strict_json`（`src_binding_subproblem.py:L24-L25`、`L70-L75`）。

也就是说，给定本包材料无法逐行验证 `_rate_to_slots` 的 Fraction/EPSILON 语义，也无法验证 strict JSON 的重复 key / NaN / Infinity 行为。设计稿把这些当成已知规格，会让实现期靠猜，猜错就是方向性返工；更坏的是 sidecar 和生产可能共享同一个“口头理解”错误。

修复文本，追加为 §2.0 前置条件：

> **核对源完整性前置条件。** Phase 1 设计不得进入实现，除非本设计包同时纳入并逐行规格化 `src/preprocess/operation_profiles.py`、`src/io/strict_json.py`，以及 facility_pools 从 canonical/preprocess/candidate 工件重建的源码或规范。`get_operation_port_profile`、`OPERATION_PORT_PROFILES`、`_rate_to_slots`、Fraction/EPSILON 处理、canonical profile facility type 集合、strict JSON duplicate-key/NaN/Infinity 拒绝规则，均属于 sidecar 语义 TCB，不能只在正文中口头描述。缺少这些核对源时，相关样本只能输出 `SPEC_INCOMPLETE`，不得输出 `CONFIRMED`。

## [CONCERN] 6. §1 把 I1 简化成“纯 binding INFEASIBLE 复验”，但 I1 实际入口是 whole-layout cut 的保守复验

设计稿原文：“I1 只在独立重建的纯 binding 模型……INFEASIBLE 时出 `CONFIRMED_INFEASIBLE`”（`binding_pb_sidecar_design_v1.md:L35-L41`），并说 sidecar Phase 1 “与 I1 完全相同的对象”（`binding_pb_sidecar_design_v1.md:L43-L49`）。

源码证据：I1 函数名和 docstring 都是 whole-layout infeasibility reverifier（`src_independent_infeasibility_reverifier.py:L1-L13`）。入口参数明确包含 `binding_exhausted` 和 `routing_exhausted`（`src_independent_infeasibility_reverifier.py:L69-L80`）。若 `binding_exhausted` 为 false，它直接 UNKNOWN（`src_independent_infeasibility_reverifier.py:L92-L97`）；若 routing exhausted 且 binding 独立 infeasible，它返回 “routing_exhaustion_reverified_by_binding_infeasible”（`src_independent_infeasibility_reverifier.py:L106-L121`）；若 routing exhausted 但 binding 未确认，它 UNKNOWN，并写入 “no routing ALL-INFEASIBLE cut without an independent full exhaustion proof”（`src_independent_infeasibility_reverifier.py:L122-L132`）。

所以 I1 的“对象”不是裸模型样本，而是带 proof_stage 和 exhaustion flags 的 whole-layout cut 候选。sidecar 可以只证明纯 binding 子命题，但不能说对象完全相同，除非也继承这些 flags 和 authority 边界。

修复文本，替换 §1.2 第一段：

> I1 的 authority 对象是 whole-layout INFEASIBLE cut 候选；Phase 1 策略是在该候选上只接受一个充分条件：独立重建的无 routing_context、无 nogood、`use_overload_separation=False` 的纯 binding 模型不可行。routing exhaustion 只有在这个更强的 binding 不可行命题成立时才被保守确认，否则 UNKNOWN。sidecar Phase 1 复验的是同一个充分条件，而不是生产过程中所有 binding/routing exhaustion 形态本身；sidecar 报告必须保留 `proof_stage`、`binding_exhausted`、`routing_exhausted` 和 scope flags。

## [CONCERN] 7. §3.2 把 Phase 2 的 NOGOOD 说成“平凡扩展”，但生产语义不是 selection 全量取反

设计稿原文：“形态②……PB 编码是平凡扩展（nogood = `Σ lits ≤ n-1`）”（`binding_pb_sidecar_design_v1.md:L51-L53`），表里也写 `NOGOOD(j) | Σ lits ≤ n_j − 1 | 形态② rejected selection`（`binding_pb_sidecar_design_v1.md:L131-L131`）。

源码证据：生产 `add_nogood_cut()` 只收集“实际存在的 BoolVar”：binding 只有 `len(domain)>1` 的实例才有变量，fixed binding choice 没有变量；generic input/output 也只有 slot 和 commodity 都存在时才加入 literal；如果最后 `literals` 为空，就不加任何 cut（`src_binding_subproblem.py:L1447-L1463`）。这和“selection 里所有选择项的 n”不是一回事。

这虽在 Phase 1 外，但正文已经下了“平凡扩展”的判断，会误导 Phase 1.5 设计。尤其 fixed choices 很多时，生产 nogood 约束的维度会小于 rejected selection 的语义维度；sidecar 若照 selection 全量编码，会和生产模型不等价。

修复文本，替换 §1.2 中形态②段落及 §3.2 的 NOGOOD 行：

> 形态②暂不声称“平凡扩展”。生产 `add_nogood_cut(selection)` 的语义是：从 rejected selection 中抽取当前模型内实际存在的 BoolVar literal，包括非 fixed binding choice、generic input slot assignment、generic output slot assignment；fixed binding choice、缺失 slot、缺失 commodity 被忽略；若抽取结果为空，则生产不添加约束。Phase 1.5 若要编码 nogood，必须以“materialized literal set”而非原始 selection 全量为输入，约束为 `Σ materialized_lits ≤ len(materialized_lits)-1`，且 `len==0` 时不发约束并记录 `NO_EFFECT_NOGOOD`。在采集 materialized literal set 前，形态②不得进入 sidecar `CONFIRMED` 路径。

## [CONCERN] 8. §4/§7 对 OPB header 的规格自相矛盾，`#equal` 应从开放问题移到硬规格

设计稿 §4 说：RoundingSat header 中 `intsize` “语义待钉死，emitter 落地前必须从源码钉准”（`binding_pb_sidecar_design_v1.md:L182-L184`）。但 §7 又说这个问题“已钉死”，`intsize` 被忽略，`#equal=` 才关键，必须等于等式行数（`binding_pb_sidecar_design_v1.md:L228-L233`）。

核对材料证据：`toolchain_notes.md` 已明确实测：RoundingSat 要求扩展头（`toolchain_notes.md:L24-L26`），`#equal` 是 proof logger 约束 ID 初始计数，必须精确等于等式行数，写错 solver 仍可能出 proof 但 veripb 拒绝；`intsize` 被忽略（`toolchain_notes.md:L27-L30`）。

这不是开放问题。它是 emitter 的硬输出规范。正文冲突会造成实现返工，尤其 `ZERO(c)`、ExactlyOne、REQ 等等到底计入多少 equalities，必须有唯一算法。

修复文本，替换 §4 的 header bullet，并删除 §7.3 的开放问题措辞：

> RoundingSat proof-log 模式要求扩展 OPB 头：`* #variable= N #constraint= M #equal= K intsize= 0`。`N` 为 OPB 变量数，`M` 为约束行总数，`K` 必须精确等于 OPB 中使用等号的约束行数，包括 `EXO-BIND`、`EXO-SLOT`、positive `REQ-*` 等式以及 `ZERO` 的逐变量等式；`EMPTY` 和 `NOGOOD` 不计入 `K`。`intsize` 当前被 RoundingSat 解析但不使用，固定写 0。header 计数错误属于 fail-detect 类，样本判 `EMITTER_HEADER_INVALID` 或 `PROOF_REJECTED`，不得重试修正后仍把同一 artifact 标为首次 PASS。

## [CONCERN] 9. §5 的 fail-closed 判定还不够硬，容易被工具链怪癖和 runner 默认行为咬到

设计稿原文：`CONFIRMED` 要求 stdout “含” `s UNSATISFIABLE`、proof 非空、veripb stdout “含” `s VERIFIED UNSATISFIABLE`、stderr 无 `Error:`（`binding_pb_sidecar_design_v1.md:L193-L195`）。`UNKNOWN` 包括 timeout / proof 检查不过 / 异常（`binding_pb_sidecar_design_v1.md:L199-L201`）。

核对材料证据：veripb 检查失败时 exit code 仍为 0，不能用退出码（`toolchain_notes.md:L21-L23`）。RoundingSat UNSAT 时 exit code 为 1，也必须解析 stdout，不能让 `subprocess.run(check=True)` 把正常 UNSAT 变成异常（`toolchain_notes.md:L34-L34`）。toolchain notes 还要求“proof 文件非空且 veripb 实际消费了它”和严格模式 `--force-checked-deletion`（`toolchain_notes.md:L48-L53`），但设计稿 §5 没写“实际消费”的可检条件，也没写 anchored parse、冲突状态行处理、stdout/stderr 全量保存。

修复文本，替换 §5 `CONFIRMED` 条件：

> `CONFIRMED` 仅当以下全部满足：
>
> 1. RoundingSat 进程完成且未被 timeout/kill；runner 不得使用 `check=True`；允许 UNSAT exit code 为 1，但必须在 stdout 中解析到唯一一行完全匹配 `^s UNSATISFIABLE\\s*$`，且不得存在 `^s SATISFIABLE` 或其他冲突 status 行。
> 2. proof path 存在、regular file、size > 0，记录 sha256；RoundingSat 命令行、stdout、stderr、exit code、版本 hash 全量归档。
> 3. VeriPB 进程完成；stdout 中解析到唯一一行完全匹配 `^s VERIFIED UNSATISFIABLE\\s*$`；stdout/stderr 均不得包含 `Error:`, `Checking error`, `panic`, `failed`, `unsupported` 等拒绝/崩溃标志；不得仅依赖 exit code。
> 4. checker invocation 必须显式带入 instance path 和 proof path；严格模式使用 `--force-checked-deletion`。验收红测必须包含：空 proof、缺失 proof、错配 proof、损坏 proof、错误 header、SAT instance + UNSAT proof，均不得产生 `CONFIRMED`。
>    任一条件缺失或解析不唯一，判 `UNKNOWN`，子码按 `SOLVER_STATUS_UNPARSEABLE`、`PROOF_NOT_CONSUMED`、`PROOF_REJECTED`、`TOOL_CRASH` 分类。

## [CONCERN] 10. §5 的 DIVERGED 路径把 witness checker 放在“半信任”位置，正文和开放问题不自洽

设计稿原文：RoundingSat 出 SAT witness 后，“sidecar 用独立 witness checker……确认后报 DIVERGED”（`binding_pb_sidecar_design_v1.md:L196-L198`）。但 §7 又把“witness checker 自身的正确性靠什么背书”列为开放问题（`binding_pb_sidecar_design_v1.md:L238-L239`）。

源码证据：I1 对可行 witness 的处理是 CP-SAT 自己找到 FEASIBLE 就报 `DIVERGED_FEASIBLE`，但它仍然清楚记录这是 independent solver status，而不是证明生产错（`src_independent_infeasibility_reverifier.py:L197-L207`）。sidecar 的 witness checker 若只“对照 §3.2 约束逐条验”，而 §3.2 本身可能漏生产语义，那么它只能证明 witness 满足 sidecar OPB，不能证明满足生产 binding 语义。

这会制造方向性返工：报告把“sidecar under-encoded”包装成“生产 bug 最高价值信号”。DIVERGED 很有用，但必须降级命名，直到 checker 的语义来源独立于 emitter。

修复文本，替换 §5 的 DIVERGED 条件，并移动 §7.6 到 §5：

> **SIDE_SAT / DIVERGED_CANDIDATE**：RoundingSat 输出 SAT 时，首先解析 witness 并用一个不读取 OPB/conmap 的 semantic witness checker 检查：原始 canonical bundle、placement、source_instances、operation profile 推导、slot materialization、requirements 校验、binding 域 membership、generic counts 均独立重算。checker 通过时输出 `DIVERGED_CANDIDATE`，说明“sidecar 找到满足独立语义规格的 witness，与生产 INFEASIBLE verdict 冲突”，仍不得自动归因生产 bug。checker 不通过或 checker 仅能检查 emitted OPB 时，输出 `SIDE_SAT_UNTRUSTED` 或 `UNKNOWN`，不得输出 `DIVERGED`。
> witness checker 的验收必须包含已知 feasible canaries、非法 witness 红测、slot/commodity 错配红测、fixed binding choice 红测、pose_optional 红测；在这些通过前，DIVERGED 路径不得作为结论性状态。

## [BLOCK] 11. §6 红测偏向“漏约束”，抓不住最危险的“多加约束 / 域缩小”假 PASS

设计稿原文的 seeded bugs 是：漏 EXO-SLOT、REQ required±1、变量映射串位、漏 pose_optional（`binding_pb_sidecar_design_v1.md:L211-L216`）。

问题是：sidecar 的最大安全风险不是“把 UNSAT 编成 SAT”，而是“把真实可行或生产 bug 场景也编成 UNSAT”，从而给生产 INFEASIBLE 虚假背书。现有四类红测主要偏 under-constraint 或局部扰动，不能系统捕捉 over-constraint。比如 emitter 错误地少枚举 binding patterns、错误跳过 output slots、错误把某 commodity ZERO、错误把 `supports_exact_pose_level_binding` gate 收窄、错误添加额外 nogood，都可能仍然产出可验证 UNSAT proof，四类红测不一定会炸。

源码证据：生产域大小取决于完整组合枚举（`src_port_binding.py:L143-L179`）以及 `supports_exact_pose_level_binding()` gate（`src_port_binding.py:L31-L33`）。generic output slots 只来自 boundary_io/protocol_core 的 output cells（`src_binding_subproblem.py:L1047-L1087`），generic input slots只来自 wireless_sink 的 K 个虚拟槽（`src_binding_subproblem.py:L1095-L1133`），requirements 还有 zero 特判（`src_binding_subproblem.py:L1134-L1158`）。这些地方任何“少发变量/少发槽/少发 pattern/多发 ZERO”的 bug 都会偏向 UNSAT，最容易形成假 PASS。

修复文本，替换 §6.2，并追加正向可行样本要求：

> 2. **红测必须覆盖 under-constraint 与 over-constraint 两个方向。** 每个约束族至少有一组“应 UNSAT 变 SAT/UNKNOWN”的漏约束突变，以及一组“应 SAT 变 UNSAT”的多约束/少域突变。最低矩阵：
>
> * EXO-SLOT 漏发、EXO-SLOT 多发互斥；
> * REQ required±1，且分别覆盖 required=0、required=slot_count、required>slot_count；
> * generic output 槽源过宽/过窄，boundary_io/protocol_core 漏含与误含；
> * wireless_sink K 少 1 / 多 1 / 读错来源；
> * pose_optional 漏合成、误合成、`pose_optional::<template>` fallback 误解析；
> * binding 域 under-enumeration、over-enumeration、port insufficient raise 被误当空域；
> * `supports_exact_pose_level_binding` gate 反向或收窄；
> * 额外 ZERO、额外 NOGOOD、漏 `__unused__` sentinel。
>
> 3. **必须加入 known-FEASIBLE canaries。** 至少 20 个独立构造的 feasible canonical binding 样本，sidecar 必须输出 SAT witness 且 semantic witness checker 通过。任何 feasible canary 被 sidecar 证明 UNSAT，均为 BLOCK。
> 4. 原第 2 条的 “DIVERGED 或对账 FAIL” 不够精确：对 over-constraint mutation，预期是 known-FEASIBLE canary 变成 false UNSAT，必须被 canary 捕获；不得只在 production-INFEASIBLE 样本上验红测。

## [CONCERN] 12. §6 “≥20 个 INFEASIBLE 样本”没有统计意义，也没有覆盖矩阵

设计稿原文：“≥20 个 binding INFEASIBLE 样本（合成为主……真实 dump 有则加）sidecar 全部 CONFIRMED”（`binding_pb_sidecar_design_v1.md:L211-L212`）。上游深研建议是 20 到 50 个历史/合成样本并抓 seeded encoding bug（`upstream_certside_route_research.md:L143-L143`），但设计稿把它压成“20 个 + 真实 dump 有则加”。

源码证据显示语义分支很多：pose_optional 合成与 missing instance（`src_binding_subproblem.py:L583-L615`）、metadata invalid（`src_binding_subproblem.py:L650-L759`）、三类约束族（`src_binding_subproblem.py:L985-L1158`）、zero requirements 特判（`src_binding_subproblem.py:L1141-L1145`、`L1154-L1158`）、nogood 外延（`src_binding_subproblem.py:L1447-L1463`）。20 个纯合成 UNSAT 不覆盖这些分支，不能说明 sidecar 对真实冻结工件安全。

修复文本，替换 §6.1：

> **正向验收不按样本数拍脑袋，而按覆盖矩阵。** Phase 1 最低要求：每个约束族、每个输入校验分支、每个边界行为至少一个样本；UNSAT 样本不少于 50 个，其中 generic output pigeonhole、generic input pigeonhole、zero requirement、empty/invalid distinction、pose_optional、missing/invalid metadata、operation profile gate、port insufficient raise 均必须覆盖。真实 dump 在 scope schema 修复后必须纳入，不再是“有则加”；若当前真实 dump 不可关联 verdict，则验收结论只能覆盖 synthetic harness，不能宣称覆盖生产对账。另需配套不少于 20 个 known-FEASIBLE canaries。

## [CONCERN] 13. §7.5 “组合爆炸防护”不应等实现期，应该进入判定协议

设计稿原文把“域枚举重实现的组合爆炸防护”列为开放问题：超大域是否需要上界护栏，超界报 UNKNOWN（`binding_pb_sidecar_design_v1.md:L236-L237`）。

源码证据：生产域枚举是组合乘积：每侧用 combinations 递归枚举，再对输入/输出侧 product（`src_port_binding.py:L58-L69`、`L143-L179`），且有全局 cache（`src_port_binding.py:L28-L29`、`L55-L69`）。sidecar 若“独立重建”但没有 cache/上界，某些合法输入会在 emitter 阶段炸内存或超时。炸掉本身 fail closed，但如果 runner 把半成品 artifact 留给 checker 或重试逻辑误判，会污染结果。

修复文本，追加到 §5 `UNKNOWN` 后：

> emitter 必须先做组合规模预估：对每个 exact binding instance 计算输入侧 pattern count、输出侧 pattern count 与乘积；对 generic slot groups 计算变量数与约束数。若任一计数超过配置上限，必须在发 OPB 前输出 `UNKNOWN`，子码 `EMITTER_DOMAIN_TOO_LARGE`，并保证不产生 partial OPB/proof artifact。上限、估算值和触发实例写入报告。生产侧 cache 行为不得作为 sidecar 正确性的依赖；sidecar 可实现自己的 cache，但 cache key 和命中结果必须审计输出。

## [CONCERN] 14. §3.2 的 `ZERO(c)` 与 `REQ-*(c)` 表述容易让实现发双份等式，影响 header/count/proof 定位

设计稿原文在表里同时写 `REQ-OUT(c) | Σ_slot s(slot,c) = required_c`、`REQ-IN(c) | ... = required_c`，又写 `ZERO(c) | 每槽 s(slot,c)=0 | required_c = 0 的显式禁用`（`binding_pb_sidecar_design_v1.md:L123-L131`）。

源码证据：生产对 required=0 不是同时发 `sum == 0` 和逐变量 `var == 0`，而是只逐变量置 0 后 `continue`（`src_binding_subproblem.py:L1134-L1145`、`L1147-L1158`）。双发在逻辑上等价，但会改变 OPB 行数、`#equal`、conmap 和 proof 定位。既然 §4/§7 已经要求 `#equal` 精确，约束族必须唯一。

修复文本，替换 §3.2 中 `REQ`/`ZERO` 行：

> `REQ-OUT(c)` / `REQ-IN(c)` 仅在 `required_c > 0` 时发一条 `Σ_slot s(slot,c) = required_c`。当 `required_c == 0` 时，不发 sum 等式，改发 `ZERO-OUT(slot,c)` / `ZERO-IN(slot,c)`：对每个已物化且含该 commodity 变量的 slot 发 `s(slot,c) = 0`；若没有变量则不发约束但记录零变量计数。`ZERO` 行计入 `#equal`，并在 conmap 中逐槽编号。

## [NIT] 15. `facility_pools_signature` 只用 sha256 前 16 位，不适合作为长期审计字段

设计稿原文说 `facility_pools` dump 只有 signature，sidecar 自行重建 pools，signature 用作交叉审计（`binding_pb_sidecar_design_v1.md:L160-L167`）。源码证据：signature 是 `json.dumps(... sort_keys=True, ensure_ascii=True, default=str)` 后 sha256 的前 16 个 hex 字符（`src_binding_subproblem.py:L1250-L1257`）。

这不是主要安全洞，因为 Phase 1 不应把 dump 当权威输入；但作为审计字段，截断到 64 bit 没必要，还混入 `default=str` 这种非严格序列化。建议 schema v3 改成全长 sha256，并同时记录 canonical bytes hash 与 facility_pools 重建算法版本。

## [NIT] 16. §3.1 变量排序说 commodity 字典序，但生产 search guidance 把 `__unused__` 放最后

设计稿原文：“变量编号确定性：按……slot_id 字典序, c 字典序”（`binding_pb_sidecar_design_v1.md:L116-L119`）。源码中 slot 变量创建时是 `sorted(required.keys()) + ["__unused__"]`（`src_binding_subproblem.py:L1047-L1052`、`L1095-L1100`），search guidance 也显式把 `__unused__` 排最后（`src_binding_subproblem.py:L1160-L1170`）。

这不影响可满足性，但会影响 varmap 可读性和 witness diff。建议写成“commodity 按生产槽顺序：真实 commodity 字典序，`__unused__` 最后”。

## 总判定：REJECT

这份设计的 PB sidecar 方向值得保留，但 v1 不能作为实现基线：独立输入边界被生产 dump 偷穿，真实 verdict 与 scope 关联没有协议级护栏，§2 还漏了多项会改变 INVALID_INPUT/exception/UNSAT 分界的源码语义。最危险的是它可能在“生产加工后的输入”上给出漂亮的 UNSAT proof，从而制造异构复验的幻觉。先重写 canonical input bundle、scope schema、完整语义规格和验收矩阵，再进入实现。
