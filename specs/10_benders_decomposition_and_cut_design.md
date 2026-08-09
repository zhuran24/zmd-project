---
status: CURRENT_WITH_HISTORICAL_DESIGN_SECTIONS
source_of_truth: src/search/benders_loop.py + src/models/cut_manager.py + src/cuts/lifecycle.py
last_verified_against: 2026-07-18 working tree（实体 generic-input routing 与 provider map）
owner: cut-manager
---

# 10 逻辑型 Benders 循环与 cut 通信边界

> **当前实现边界（2026-07-18）。** `src/search/benders_loop.py` 的 certified 路径使用现役 master、binding、routing
> 和登记的 exact-safe cut ladder。`src/models/flow_subproblem.py` 只生成诊断状态，不能门控
> certified verdict，也不产生 Farkas ray 或 proof-bearing cut。当前 cut registry 为 F1-F7+F9，
> F8 已退役；`step_8_apply_to_master()` 已翻译 F1/F5/F6/F7，`benders_loop` 的 direct bridge 由
> `EXACT_CUT_FRAMEWORK_ATTACH` 门控。该 bridge 仍在 certified unsafe map 中且默认关闭，
> F2/F3/F4/F9 fail closed。Stage B B0/B1/B1.5 已落地，B2-B5、PIC C/D/E 与 B6 owner promotion 尚未完成。
> 面向人的阶段名为 P1.3；旧 `p1_3b_*` 仅是机器兼容字段。

## 10.1 当前 certified 路径

对一个固定 ghost candidate，当前调用链是：

1. master 求一个 placement；master `UNKNOWN`/timeout 必须 fail-closed；
2. 连续 flow LP 可以运行并写入 `diagnostic_flow_status`，但其 `FEASIBLE`、`INFEASIBLE` 或
   `TIMEOUT` 都不决定 certified acceptance；
3. binding 子问题枚举并校验端口绑定；generic-input 成品被绑定到 `box_sink` 或 `protocol_core` 的具体实体输入口，生产端输出与该 sink 都进入 routing terminal 集；
4. routing 子问题在已选 binding 上建立离散路由，`FEASIBLE` 才可返回内部
   `RUN_STATUS_CERTIFIED` candidate verdict；
5. routing/binding 的不可行结论只有经过对应 exact-safe proof ladder 才能形成 cut。whole-layout
   nogood 还必须先经 `independent_infeasibility_reverifier`；不确认、分歧、超时或异常返回
   `UNKNOWN`/no-cut；
6. 这个内部 candidate verdict 仍不是 durable/public `CERTIFIED`。outer producer 只能提交
   `CANDIDATE_PROPOSED`，之后还要经过 supervisor seal、fixed-witness 复验、owner publish gate 与
   canonical publisher。

代码证据：`benders_loop.py:5188-5369`、`:5694-5732`、`:5795+`、`:6973-6990`、
`:7538-7585`；终端发布链见 `outer_search.py:855-954`、`exact_campaign.py:3399-3593` 与
`certified_surface.py:563-680`。

## 10.2 exploratory 路径与历史 flow-loop

`_run_exploratory()` 仍保留 master → flow diagnostic → exploratory result/cut 的旧式循环。该路径
可以返回内部状态常量 `RUN_STATUS_CERTIFIED`，但它属于 exploratory/best-effort 语义，不能进入
certified campaign authority、supervisor seal 或公共认证发布面。文档、报告和 adapter 不得把这个
内部枚举值渲染成项目已认证。

## 10.3 现役 exact-safe cut ladder

现役 certified loop 的 cut 不是“LP Farkas ray 自动回灌”。它由具体 binding/routing 证据路径生成、
序列化、解析并在 master 上重放，且必须满足 `PROJECT_LOCK.md` 的 lifecycle、scope、condition 与
独立复验约束。关键原则是：

- 当前 binding selection 不可行，不自动证明 placement 对所有 binding 都不可行；
- routing precheck 的局部拒绝只有在量词和 scope 足够时才可提升为 master cut；
- persisted cut 的 conflict members、condition literals、artifact/source scope 必须完整解析，任何
  missing/unknown/aliasing 都 fail-closed；
- whole-layout `INFEASIBLE` 不能由原求解路径自证，必须经登记的 independent re-verifier；
- 预算耗尽、solver `UNKNOWN`、unsupported proof stage 或不完整冲突集不得被包装成
  `INFEASIBLE`。

## 10.4 Active cut-family framework 的真实进度

`src/cuts/families/`、validators/oracles 和 `src/cuts/lifecycle.py` 承载当前八族 registry（F1-F7+F9；
F8 retired）及其 proof lifecycle。canonicalize/generate/minimize/serialize/deserialize/validate/scope/
resolve/evaluate 已有实现与测试；production attach 处于“部分接通、尚未 certified promotion”状态：

- `step_8_apply_to_master()` 已翻译 F1/F5/F6/F7；F2/F3/F4/F9 对不支持路径抛 `NotImplementedError`；
- `_maybe_attach_framework_cuts()` 可在 `EXACT_CUT_FRAMEWORK_ATTACH` 门后调用 direct bridge，但 certified
  unsafe-map 禁止该开关，默认路径不会把这些 cut 当成认证前提；
- Stage B B0/B1 已提供 contract shell、`FrozenArtifactBundle`、`ValidatedStateSnapshot` 与 digest v1；
  B2-B5、PIC C/D/E、RFC-002/003 和 B6 owner promotion 仍未完成；
- family validator 或 lifecycle replay 通过不等于 cut 已获 certified authority。promotion 前仍必须复核
  theorem、constant support、scope、runtime literal resolution、master encoding、独立 verifier 与 red tests。

## 10.5 历史 Type-I/Type-II 设计

早期文档把 flow LP `INFEASIBLE` 描述为可经 Farkas ray 生成“宏观拓扑瓶颈 cut”，并把 routing
失败描述为可直接提取 MUC 后写 placement no-good。当前代码没有实现该 Farkas-ray 管线，也不能把
任一 routing 局部冲突无条件提升为 placement-level theorem。以下 2026-06-11 之后的 addenda 记录
已经落入代码或仍约束未来集成的具体 soundness 条件；更早的 Type-I/II 方程仅保留为设计历史，不是
当前行为说明。

## 10.7 [2026-06-11 P0 Soundness Addendum] Binding-local precheck evidence ladder

Routing precheck 的 `binding_selection_safe_reject=True` 只说明当前 binding selection 不可接受，不自动证明当前 placement pose combination 不可路由。尤其是 `front_blocked`：端口前格是否被占用取决于 `binding_idx` 选出的具体端口/方向；同一 pose 换另一个 binding 可能打开前格。

因此 LBBD loop 对 `front_blocked` 与 `relaxed_disconnected` 使用同一 proof ladder：只要 binding model 仍有可枚举替代，先写 binding-level nogood (`binding_model.add_nogood_cut(selection)`) 并重解 binding。只有所有 binding 替代已穷尽，或另有独立 exact proof 表明该 placement 下任意 binding 都必然失败，才允许投影为 master placement-level nogood。若无法建立 exact placement-level proof，certified path 必须返回 `UNKNOWN` 而不是误剪 placement。

## 10.8 [2026-06-12 cuts R2 Addendum] Cell-pattern cut 的必然激活端口前提 (F-CUT-R2-01)

env 门控的 pose-bool cell cut（`add_routing_port_blocking_cell_cut`，形状 `sum(在 (cell,dir) 有端口的 pose) + sum(占 front cell 的 pose) <= 1`）是 master 级 cut，对 pose 变量量化，构造时不知道未来 binding 子问题会选哪个 alternative。其隐含定理"port pose + blocker pose 同选必然 front_blocked"需要一个关键前提：**该物理端口在 pose 被选中时必然 active 且 routing-visible**。

因此 raw per-cell 端口只在该 side 的 visible demand 覆盖该 side 全部物理端口时才允许登记进 routing-visible 索引（`_mandatory_port_side_is_cell_pattern_exact()`——input 侧：concrete routing-visible `input_demand >= 物理端口数`；output 侧：visible output 非零、等于 total output、且 `>= 物理端口数`）。Generic-input provider 也有真实物理端口：`box_sink` 的选中 pose 为 3 个输入口/3 个输出口，`protocol_core` 为 14 个输入口/6 个输出口；plan capacity 必须与 pose 输入口数严格相等。Binding 选中的 generic-input 口必然 routing-visible，并由 `extract_port_specs()` 导出为 sink，但 master 仅看 pose 时不知道需求会分配到哪个 provider/slot，所以**未绑定的 raw provider 口仍不能当作 necessarily-active**。只有 binding-aware assignment、全局饱和或同等 exact proof 才能把具体 provider 口登记进 cell-pattern cut。

Generic-output 槽同样是容量而非逐端口必选需求：只有 required generic-output 数量等于已知 mandatory generic-output 总容量时，`__unused__` 才被精确计数压成 0，相关物理输出槽才能视为 necessarily-active。否则被挡的口可能只是 binding 可不选的 slot；换另一个槽后 placement 仍可行，raw cell-pattern cut 会误剪（最小反例：双输入口、demand=1 的机器 + 占第一口 front cell 的 blocker；对偶反例是双 generic-output 物理口、demand=1）。Residual-optional pose 若缺少 operation/binding identity，也不得登记 raw per-cell 索引。

CUT-R4-H1 当前口径：正数 `required_generic_inputs` 商品是普通 routed commodity。生产设施输出口是 source，已绑定的 provider 输入口是 sink；generic-input 角色不再授予任何 routing 豁免。因此饱和 generic-output 的 visible 判定不再排除 generic-input 商品，但仍必须满足 commodity-role disjoint、slot assignment 与上述 necessarily-active 前提。

> [!NOTE]
> **Superseded historical premise（2026-07-18 前）**：旧 CUT-R4-H1 曾从 positive generic-input demand 推导 routing-free sink，并跳过对应输出与 provider front。该前提随 `omni_wireless`/虚拟槽解释一起废止；兼容命名若仍存在也必须返回空集合，不能重新激活旧 cut 量词。

另一同源前提：candidate pose data 是 global 坐标（同 `_build_global_pose_cache` 的注释），端口/格子 lookup cache 不得再叠加 anchor 偏移——double-anchor 会把 candidate alias 到幻影格，轻则漏 cut、重则把无关 pose 带进 cut。该 hook 在公开 certified 路径被 `pose_bool_master_not_certified` env guard 阻断；本前提约束任何未来把 pose-bool/cell cut 提升为 certified 的决定。

## 10.9 [2026-06-13 cuts R8 Addendum] Separator cut 不得窄于其模型编译进的 layout context (CUT-R8-H1)

任何 separator（D2 commodity-flow、未来同构通道）若把当前 layout 状态编译为模型**常量**（selected footprints 构成的 occupied grid、helper terminal 的当前端口位置），其 CP-SAT assumption core 只覆盖 assumption literals，常量部分是不受保护的 proof context。只按 raw core 写 master no-good，等于把"该 terminal 子集在当前障碍上下文下不可行"升级成"这些 pose 在任意 layout 下不可行"——over-cut（PCR-R5-H3 constant-support 义务在另一通道的复发；最小反例：单行走廊 + 墙挡中点，core 只含 source，移墙后同一对 source/sink pose 可行）。

义务：master conflict tuple 必须在 raw core 之外并入**所有贡献了编译常量的 selected pose**（全部 occupancy contributors + 全部当前 port owners，`ghost_pick` 除外）。并入只会弱化 cut，使被禁集合不超出 D2 实际证明范围。`EXACT_B1_D2_COMMODITY_FLOW` rung 曾违反一次（raw terminal core cut，而整个 layout footprint 都是模型常量），修复为 support-augmented conflict set（`_build_d2_supported_conflict_set`），回归 `src/tests/test_d2_separator_support_context.py` 固定 toy 反例。

## 10.10 [2026-06-13 cuts R9 Addendum] 非证明 relaxation 的 separator 模型不是 master-cut proof source (CUT-R9-H1)

CUT-R8-H1 修复 support 完备性之后还剩更底层的根前提：**D2 模型本身不是 production routing 的 relaxation**。至少两处编码比 production 更严——per-cell `AddAtMostOne` 是 2D 的，表达不了两条 commodity 在同一格跨层（bridge）通过；单位流守恒表达不了 splitter/merger 一源多汇拓扑。production 可行的 layout 因此可能 D2-INFEASIBLE（两个最小反例都有 probe 回归：两层 crossing 与 splitter，production precheck=feasible + RoutingSubproblem=FEASIBLE + raw D2=INFEASIBLE），即使 support 全并入，cut 仍会禁掉可行解——独立于 CUT-R8-H1 的第二种 over-cut。

义务：separator 模型未按 PCR-R5 义务族端到端证明为 relaxation 前，其 INFEASIBLE 只能用于 telemetry / core 收缩，**不能独立作为 master cut 的 proof source**。master cut 必须挂在一个独立的 production 侧不可行证明上：D2 rung 现要求 production routing precheck 对**同一** occupied grid + port specs 判 `front_blocked`/`relaxed_disconnected`（其余一切状态 deny-unknown 拒绝，返回 `MODEL_INVALID` 不建模不写 cut）。两个配套口径义务：① separator 侧 occupied 编译保持 ≤ production 口径（`ghost_pick` 显式跳过），使 blocked/disconnected 判定沿障碍单调方向安全（separator 障碍更少时仍判 blocked ⇒ production 上下文也 blocked）；② 该 gate 的 proof ladder 位置依赖 caller——benders_loop 的 front_blocked branch 只在 `binding_selection_safe_reject=False` 或 binding alternatives 穷尽后到达（§10.7 ladder），D2 cut 与 fallback selected nogood 同位置同保护，cut 范围（support tuple 全集）⊇ fallback tuple = 只弱化。
