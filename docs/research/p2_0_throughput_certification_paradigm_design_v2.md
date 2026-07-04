# P2.0 吞吐认证范式设计稿 v2

**Status:** HISTORICAL_OR_PLAN（研究层设计稿，不改生产代码/锁面）
**Authored:** 2026-07-04（v2，取代 `p2_0_throughput_certification_paradigm_design_v1.md`；同日 v2.1 修订——本地三路独立核查回收：CE4 独立成公理 A13、"消解公理"表述收敛、若干 PARTIAL 补齐）
**Scope authority:** 在本稿落地并走完 freeze-ritual 之前，`PROJECT_LOCK.md` §1A B 块与 `rules/canonical_rules.json:415-417` 的 out-of-scope 声明**继续有效**。

**v2 修订输入**（原件归档于 `p2_design_external_reviews_20260704/`）：
① GPT Pro 盲设计（独立设计对照，两层 TP7-S/TP7-D 结构采纳为 v2 主结构）；
② GPT Pro 对抗审查（5 BLOCK + 3 CONCERN + 2 NOTE，全部核实为真并吸收）；
③ GPT Pro 沙箱反例（tick 仿真器实证 CE1–CE4，验证公理组必要性并暴露一个未覆盖机制）。

**v1→v2 关键变更**：
- 【结构】单层 fluid+公理 → **两层**：TP7-S 静态平均层（必要条件 + Farkas 不可行证书）+ TP7-D 离散周期调度层（**发布级可行证书**）。TP7-D 用逐 tick 整数日历自证调度存在性，把 v1 里 merger 仲裁/splitter 比例/占空比可实现类公理从"假设"变成"证书内容"。
- 【BLOCK-1】外部源口修正：= `boundary_io`(46×1) **+ `protocol_core`(1×6)** = 52 slot，恰等于需求 34+18；utility 实例（boundary_io/protocol_core/power/wireless_sink）无 recipe、不进机器耦合约束。
- 【BLOCK-2】端口速率 `r[p]` 显式定义并经 terminal arcs 与路由流 φ 绑定（扩展图 G⁺），封死"机器吞吐与路由流脱钩"的 false-CERTIFIED 洞。
- 【BLOCK-3】迁移规则收紧：只有结论形如 ¬P(x) 的旧证据可继承；旧 CERTIFIED incumbent 及**依赖它的 frontier dominance skip 全部失效**。
- 【BLOCK-4】witness 升为自包含 closed-world 证书，digest 集扩到与 terminal fixed-witness stable fields 全对齐。
- 【BLOCK-5】Farkas 侧给出完整规范形（Ax≤b、等式拆行、bounds 入行、canonical constraint_id 由 verifier 重建）。
- 【CONCERN-1+CE4】公理组扩为 A1–A12（含端口 handoff、组件速率同质、cross-junction 通道独立、多输入同步、全局混流可分）；CE4（多输入队首阻塞）实证为 fluid 层不可消解、由 TP7-D+A8 或 FIFO trace 承担。
- 【CONCERN-2】§8 满带论断软化为组件级局部结论。

---

## 1. 事实基线（v1 §1 全部继承，此处只列修正与补充）

- **外部源口**（v1 错，实测核验）：`rules/preprocess_plan.json::utility_operations` 给 `boundary_io.generic_output_slots=1`、`protocol_core.generic_output_slots=6`；binding 的 generic output domain 同时接受两者（`binding_subproblem.py:1047-1063`）。46 boundary_io + 1 protocol_core ⇒ 52 个源 slot = `required_generic_outputs` 的 34+18。**只认 boundary_io 会把当前实例族错判 P7-不可行。**
- **当前目标速率**（盲设计核算，与 `demand_solver.py:261-272` 语义一致）：`valley_battery = 3×(1/5) = 3/5` item/tick；`qiaoyu_capsule = (11/4)×(1/5) = 11/20` item/tick；分母 lcm=20（周期证书天然候选周期，但 verifier 不得硬编码）。
- **routing 与 ghost**：`routing_subproblem.py` 全文零 ghost 引用——belts 可穿过空矩形，ghost 只排设施。
- 其余（速率数据齐备、route state 结构、混商品共享、认证链模式、flow 诊断退化）同 v1 §1。

## 2. 第七谓词：两层结构

### 2.1 建模对象（BLOCK-1 修正版）

给定已过六谓词的候选终态 (R\*, π\*, B\*, S\*)：

- **M\*** = 已放置且 `operation_type ∈ canonical_rules.recipes` 的 recipe-backed 机器实例。只有 M\* 有 `ticks_per_cycle`、输入/输出量和利用率变量 `u[i]`。utility 实例（schema key：`boundary_io`/`protocol_core`/`power_supply`/`wireless_sink`）无 recipe、不进机器耦合。
- **U_src(B\*)** = binding 选出的 generic output source slots（来自 `utility_operations.*.generic_output_slots > 0` 的 utility 实例；当前 = boundary_io + protocol_core）。
- **U_sink(B\*)** = routing-free 的 wireless sink virtual generic input slots（终产品，不进路由图，仍有 per-slot 容量）。
- **K_route / K_rf_sink**：进路由图的商品 / routing-free 终产品（`commodity_metadata` 的 sink_kind 判别）。
- **G⁺(B\*, S\*)** = 扩展路由图：selected route states 的邻接重建（同 connectivity guard 语义，`routing_subproblem.py:1413-1432`）**加 terminal arcs**——route-visible 输出/源口 `terminal(p) → 首 route state`、输入/汇口 `末 route state → terminal(p)`。同一 front cell 多物理端口时保留多个 terminal 节点，不得沿用 guard 的 front 去重（容量建模需要逐口）。注：当前 accepted routing 对重复 `(front, dir, commodity, type)` 本就 fail-closed（`routing_subproblem.py:151-160, 413-427`）——逐口保留主要是对未来语义扩展与恶意 witness 的防护，不是当前常态修正。

### 2.2 TP7-S：静态平均带宽层（必要条件层）

变量（全有理）：`φ[e,k]`（G⁺ 边流量）、`r[p]`（端口/slot 吞吐）、`u[i]∈[0,1]`（i∈M\*）。

| # | 约束 | 备注 |
|---|---|---|
| T1 | 每 k∈K_route、每非终端节点：Σin φ = Σout φ | splitter 不复制、merger 不丢由守恒直接给出 |
| T2 | 每 selected physical state s：`through(φ,s) ≤ belt_capacity_per_tick`（跨商品聚合）。`through(φ,s)` := s 上全部 incoming incident arcs 的跨商品总和（由 T1 等价于 outgoing 和）。cross-junction 的 L0/L1 两通道是两个 physical state、默认各自限容——**通道是否真独立是公理 A9/缺口 D7**，若实测否定则本行改为 per-cell 聚合容量 | NOTE-2 修正 |
| T3 | 每端口/slot p：`0 ≤ r[p] ≤ port_max_throughput_per_tick`；route-visible p 的 `r[p]` **必须等于其 incident terminal arc 的 φ**；未知端口、重复端口、无 incident selected state 的正吞吐拒绝 | BLOCK-2 核心 |
| T4 | 每 i∈M\*、商品 k：`Σ_{p∈in_ports(i,k)} r[p] = u[i]·inputs_i[k]/tpc_i`；输出侧同理 | utility 实例不进 T4 |
| T5 | 每 production target t：`Σ_{p∈target 输出承载} r[p] = target_rate(t)`（**精确等式**——避免未声明的溢出/void sink；若游戏允许过产丢弃需另立公理，见开放问题） | 盲设计裁定采纳 |
| T6 | routing-free sink 平衡：k∈K_rf_sink 的 `Σ_{生产口} r[p] = Σ_{virtual sink slots} r[p]`，右侧逐 slot 过 T3；外部注入只可来自 source_kind=external_boundary 的 U_src slot | 防无限黑洞 |

**TP7-S(B\*,S\*) :≡ ∃ 有理 (φ,r,u) 满足 T1–T6。** 设计要点保留 v1：只约束原始 targets，不把 `commodity_demands.json` 当 demand 等式（它多约束终品、漏 seed 循环商品）；中间/循环商品速率**由 T4 机器耦合 + K_route 网络平衡 + T6 routing-free sink 平衡共同诱导**，存在多个可行循环流时 witness 任选其一、verifier 只查 T1–T6 与目标。

**TP7-S 的地位**：任何离散周期运行按周期平均必满足 T1–T6 ⇒ **TP7-S 不可行是固定 (B\*,S\*) 吞吐不可行的 sound 证据**（Farkas 证书，§4.3）；TP7-S 可行**不是**发布依据（CE1–CE4 实证了 fluid-可行 ≠ 离散可达）。

### 2.3 TP7-D：离散周期调度层（发布级可行证书）

证书 = 周期 P∈Z₊ 的 **path-phase schedule**（盲设计首选格式采纳）：

- 列出路径 `path_j = (commodity, source port, 组件序列 p_1..p_L, sink port)` 与注入相位集 `Φ_j ⊆ {0..P-1}`；相位 φ 的 item 在 tick `(φ+h) mod P` 占用第 h+1 个组件。
- verifier 逐 tick 重算整数日历：每组件每 tick 占用 ≤ belt 容量（当前=1）、每端口每 tick ≤1、每机器周期内输入/输出计数与 recipe 精确平衡、目标商品周期计数 = P×target_rate（须为整数）、in-flight 集合周期闭合（tick 0 = tick P）。
- 备选格式：**FIFO trace**（显式逐 tick 队列模拟，用于机制争议场景——CE4 类多输入同步问题的最终裁决格式）；**static-flow-with-lift**（TP7-S 解 + 路径分解 + 相位着色，便于求解器输出）。

**发布判定**：publishable CERTIFIED′ 要求 TP7-D 证书被复验接受。TP7-S 可行而无 TP7-D ⇒ `UNKNOWN`（fail-closed）。

**TP7-D 改变了公理的分工（表述精确版）**：调度**存在性**由证书显式证明（不再假设"存在某种公平仲裁使流量可达"）；但"游戏能**执行**证书指定的确定性调度"仍是公理（A7/A8 的可实现性半边），由 `throughput_semantics` 机器化与 FIFO trace 终裁共同承担——TP7-D 不是单独消解，是把公理从"存在性+可实现性"缩到只剩"可实现性"。

### 2.4 量词、scope 与回退语义

证书 scope 层级（盲设计采纳）：`selected_route_graph`（v1 唯一启用）→ `binding` → `placement` → `candidate_frontier`（后三者需 all-alternatives cover 证书，v1 不实现、不假装有）。

固定候选的回退循环（CONCERN-3 收紧版）：

1. TP7-D 找不到 → 试 TP7-S；TP7-S INFEASIBLE（规范形 Farkas 在手）→ 对**完整离散选择键**落 selected-solution nogood——键必须含 recipe port binding choice、generic I/O slot assignment、全部 selected route use-vars 与 graph 语法版本（漏任一维度，solver 会换个等价 slot 赋值原样撞回来）；
2. 泛化 cut（如容量割集）必须自带独立 exact-rational 证明，heuristic bottleneck 不是 exact-safe cut；
3. 候选级 P7-INFEASIBLE 只在 CP-SAT 加入全部已复验 nogood 后返回 INFEASIBLE、且 whole-layout replay 能重建同一模型+cut 序列+结论时才成立；否则 UNKNOWN fail-closed。
4. TP7-S 可行但 TP7-D 反复找不到 → UNKNOWN（不落 cut；bounded-period 分支证书只作解释性材料，不剪候选）。

### 2.5 与最优性：迁移规则（BLOCK-3 修正版）

谓词添加 = 收紧（P′-可行 ⇒ P-可行）。**只允许继承结论形如 ¬P(x) 的旧证据**：结构性不可行证明（binding/routing/power 穷尽）、已复验 whole-layout nogood、与旧 incumbent 无关的 exact-safe cut。

**不得继承**：旧 CERTIFIED incumbent；依赖旧 incumbent 的 frontier dominance skip / search stop / terminal frontier evidence；一切"无需探索因为已有更优 P-可行解"型记录。反例：旧 A(area=100) CERTIFIED 支配剪掉 B(area=90)；P′ 下 A 吞吐失败而 B 可行——继承 skip 就丢了 P′ 最优解。

迁移程序：旧 CERTIFIED 全部降级 `P7_PENDING`；被 dominance 跳过且无结构性不可行证明的候选恢复 `UNRESOLVED_UNDER_P7`；粒度不可区分时保守只继承可独立复验的 exact-safe cut。**正向捷径**（盲设计 §6.2）：若旧 lex 最优候选补到 TP7-D 证书，则"无 lex 更优新可行解"自动成立（新可行集 ⊆ 旧可行集），无需重跑 frontier——只需 schema 升版重 seal。

## 3. 离散语义鸿沟：公理组 A1–A12 与反例实证

TP7-D 承担调度存在性后，残余公理收敛为「参数真实性 + 调度可实现性 + 语义完整性」三类（编号沿盲设计，内容并入对抗审 A6-A9）：

| 公理 | 断言 | 实证/缺口 |
|---|---|---|
| A1 tick | 游戏物流与配方时间可统一到 tick 域，tick 内更新序由 `throughput_semantics.update_order` 完整描述 | D-order 实测 |
| A2 离散计数 | 周期整数事件代表稳态平均产率 | 沙箱控制实验：0.55/tick 占空比收敛 ✓ |
| A3 belt 聚合容量 | 组件瓶颈容量 = canonical 值、跨商品共享 | D7：转弯/交接是否折损 |
| A4 port 容量 | `port_max_throughput_per_tick` 真实且含 handoff/buffer 语义（不丢件、回压停机） | D6 |
| A5 混货 | 共享组件除聚合容量与 FIFO 序外无额外禁忌 | D8 |
| A6 FIFO | path-phase 的"每组件每 tick ≤1 in-flight"是游戏可容纳的保守模型 | D6 |
| A7 splitter | 证书指定的输出选择游戏可实现（若强制轮转比例，`throughput_semantics.splitter_policy` 加约束） | CE2 实证 type-blind 分流失败属此类；D3 |
| A8 merger/注入调度 | 证书指定的输入选择/注入相位游戏可实现 | CE1（优先级饿死）实证属此 |
| **A13 多输入同步可调度性**（v2.1 独立成条，原误折入 A8） | 对任何需要 ≥2 种输入商品的机器：witness 中进入该机器的平均输入流，必须存在有限周期离散序列使有限 FIFO、输入槽容量与启动规则**不产生队首阻塞（head-of-line blocking）**。静态充分条件：多输入机器前最后一段 FIFO 不混商品，或存在过滤/分商品队列/覆盖最大突发的输入缓存 | **CE4 实证：最宽容语义下仍失败——这是 fluid 层不可消解、也非普通仲裁问题的独立机制**；path-phase 证书证明交错调度存在（A13 前半），游戏能否实现该交错是 A8/A13 的可实现性半边；争议场景 FIFO trace 终裁 |
| A9 cross-junction | 两垂直通道同格不互相阻塞、不共享容量 | D7 实测；若否定 T2 改 per-cell 聚合 |
| A10 machine | 聚合模式下机器可实现平均速率；cycle_trace 模式下 timing 与游戏一致 | D5 |
| A11 wireless sink | 终品接收容量由 virtual slots 给出、不占路由图 | 规则已定（preprocess_plan） |
| A12 warm-up | 稳态命题接受周期初态；若要求空网启动，另给 finite startup trace（种子循环 bootstrap 属此）| CE3 实证：空启动死锁、补 WIP 后达标 |

**实证小结**（仿真器与实例见归档 patch）：CE1→A8、CE2→A7、CE3→A12、**CE4→A13（新机制，独立成条）**；对照实验证明 belt 迟延只影响 warmup（G1 数学消解成立）、分数速率无节拍锁死（A2 成立）。公理组由"纸面清单"升级为"经反例狩猎校准的清单"。

## 4. 证书格式（要点；完整字段表实施期出 schema JSON）

### 4.1 公共 envelope（BLOCK-4 修正版）

自包含、closed-world、layout-bound。digest 集与 terminal fixed-witness stable fields 全对齐：`candidate_key / solution_digest / ghost_rect_digest / ghost_cells_digest / binding_assignment_digest / port_specs_digest / routing_occupancy_digest`，加 `selected_route_states`（**闭世界列表，verifier 由此独立重建 G⁺ 并重算 selected_graph_digest，不信 witness 边表**）与 `throughput_inputs_digest`（覆盖 canonical_rules 速率投影 + `commodity_metadata` 角色 + `preprocess_plan.utility_operations` + `generic_io_requirements` + mandatory instance→operation 映射——v1 只盖 canonical_rules 是漏洞）与 `throughput_semantics_digest`（§6 新 frozen artifact）。

数值规范：有理数 `{num,den}`，den>0、既约、零=`{0,1}`；float/NaN/未知字段/重复 key 一律拒。`flows`/`port_rates` closed-world：缺省=0，重复/未知边/**未知商品**/未知口拒绝；route-visible 口的 `r[p]` 必须等于 terminal arc 流量。（完整字段级 schema JSON 属实施期交付——这是本稿已声明的未闭合面，不是遗漏。）

### 4.2 可行侧

`feasible_periodic_path_phase_v1`（主力，§2.3）；`feasible_fifo_trace_v1`（机制争议终裁）；`feasible_static_flow_with_lift_v1`（TP7-S 解+分解+相位着色）。verifier 均为确定性重算，不解优化问题；targets_per_period 从 canonical rules 重算，不信 payload。

### 4.3 不可行侧（BLOCK-5 修正版）

`infeasible_static_farkas_v1`：verifier 先把 TP7-S 全约束**独立规范化**为 `A x ≤ b`——等式拆两行、`≥` 取负、变量下界 `-x≤0` 入行、全部上界（u≤1、r≤port_max、组件容量）入行、每行 canonical `constraint_id` 由 verifier 重建（不信 producer 自报），产出 `lp_digest`。证书 = `{constraint_id: λ}` 非负有理乘子；检查 `λ≥0 ∧ Σλ·A=0（逐列）∧ Σλ·b<0`。未知/重复 constraint_id、未引用行乘子非零歧义、非既约有理数全部 fail-closed。**由 §2.2 平均化引理，该证书同时否定 TP7-D。**

`infeasible_periodic_branch_farkas_v1`（bounded-period 分支树）：只证"无周期 P 的调度"，无 period bound 定理时不得用于剪候选。

## 5. 独立复验器

四步：① strict JSON + 数值规范；② 从 locked artifacts 重算全部速率输入并对 digest；③ 消费 terminal verifier 已重算的 binding/routing 结果，从 closed-world selected states 独立重建 G⁺ 并对 digest（terminal verifier 需新增输出 `selected_route_graph_digest`——现有 `extract_routes()` 有数据、verdict 未纳入，这是接入点）；④ 按证书类型做纯算术验证（§4）。复杂度：path-phase O(L_total)；Farkas O(nnz(A))。

## 6. 管线接入与工程影响面（v1 §6 基础上增补）

- 新增 frozen artifact：`throughput_semantics`（canonical semantics 块或独立 rules 文件）——update_order、splitter/merger policy、buffer 模型、machine timing、cross-junction 独立性全部 hash-pin；v1 保守默认（每组件每 tick 聚合 1、不复制不丢弃、cross-junction 两层独立）。机制实测结果落进它 = 公理消解的机器化通道。
- terminal fixed-witness verdict v2 新增：`selected_route_graph_digest / throughput_semantics_digest / throughput_certificate_digest / throughput_status / throughput_kind / throughput_scope`；publishable 判定加 `throughput_status==FEASIBLE ∧ scope==selected_route_graph`。
- 其余（新模块不改造 flow_subproblem、candidate_proof v2、manifest v2、PROJECT_LOCK B 块改写、canonical semantics 措辞 freeze-ritual、EXACT_* allowlist、reseal 连锁、P1.3 先行共享有理对偶基建）同 v1。
- **最小落地路线**（盲设计 §11 采纳）：TP7-S verifier + Farkas → terminal 输出 selected_route_graph_digest → path-phase verifier → throughput_semantics hash → terminal schema v2 → campaign 迁移（先试给旧最优补 TP7-D，成功则最优性直接转移）。

## 7. 复杂度（CONCERN-3 修正）

单次 TP7-S LP 与证书复验成本可忽略（选中图 ~10³ 组件、17 商品）；**但 LBBD 内环不可忽略**——selected-solution nogood 最坏枚举指数级 (B,S)，收敛性只有"有限空间理论终止"，可发布终止还要 cut transcript 可复验。P2.0b 不得承诺每候选新增成本可忽略；Farkas→容量割集泛化 cut 的强度是内环收敛的决定因素，列头号算法问题。

## 8. 对最优性的实质影响（CONCERN-2 软化版）

严格结论是**组件级局部**的：witness 中 `through(φ,s)=容量` 的组件无剩余容量，不能再共享正流。端口侧：当前 52 个源 slot 恰好 = 需求 52，源口预期全部打满；但**口满不推组件满**——满载源流出 splitter 后可分成半速分支与他流共享。故 P7 的实质影响 = 大量走廊/口前成为容量瓶颈、混商品共享的空间节省显著缩水、最优空矩形预期收缩；但"逐线不相交"**不是**可直接施加的硬约束，只有 Farkas/割集证明了具体组件集合饱和才可升格为 sound cut。

## 9. 数据/语义缺口（v1 D1-D5 + 审查 D6-D8）

D1 belt 移速（tick 层需要）；D2 merger 仲裁；D3 splitter 分配与混流可分；D4 循环组 bootstrap；D5 机器输出阻塞语义；**D6 端口 handoff/buffer/丢弃细节；D7 cross-junction 通道独立性与组件速率折损；D8 混流经 merge/split 网络的全局标签可分性**。全部经 `throughput_semantics` 机器化消解（先例：2026-07-02 routing 四裁定）。

## 10. 验收判据与分期

- **P2.0a（进行中）**：v1 过五路外审 ✓；反例集建立且逐个归因 ✓（CE1-3 归 A8/A7/A12，CE4 独立成 A13）；v2 本地三路独立核查 ✓（2026-07-04，发现项已并入本 v2.1）；**剩余（必须，非可选）**：GPT Pro 对 v2.1 的终审 + toy path-phase 证书 + 原型 checker 端到端。
- **P2.0b（P1.3 后）**：§6 全清单落地；红测含证书伪造全谱（脱钩 digest、伪 Farkas、重复边、多口去重漏洞、targets 篡改）。
- **P2.0c**：throughput_semantics 实测填充（D1-D8），公理逐条消解；FIFO trace 语义与游戏对齐验证。
- 开放问题（承 v1 + 盲设计）：①TP7-S→TP7-D 的 bounded-period lift 定理；②过产/溢出语义公理；③吞吐失败引导 routing 找低拥塞替代图的 cut 设计；④证书压缩（run-length/bitset）；⑤人类可读吞吐审计报告。

---

*v2 完。v1 保留为历史快照；外审原件见 `p2_design_external_reviews_20260704/`。*
