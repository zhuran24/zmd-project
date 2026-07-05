# Q1 不可行类分类学与完备性命题设计稿 v1

**Status:** HISTORICAL_OR_PLAN（研究层设计稿，不改生产代码/锁面）
**Authored:** 2026-07-05（v1，待独立审查——本稿走「先想后做」审查链：外审 triage 后修订，落地前不作为任何实现依据）
**Scope authority:** 本稿不改变 `PROJECT_LOCK.md` 任何条款；Q1 在 `05_open_questions.md` 的 P0/defer 状态不因本稿改变。

**任务**：Q1（9 个 cut family 是否 cover 所有 INFEASIBLE 类，`05_open_questions.md:17-32`）当前是经验性覆盖框架——5 issue 映射 + red fixtures + F10-F16 反例裁定，无形式定义。survey（`docs/research/p3_0b_family_formalizability_survey_20260705/completeness.md`）列出八个定义层缺口。本稿补定义层：theorem domain、类分类学、owner lemma 模板、完备性命题的可证/可证伪形态。

---

## 1. 事实基线（全部有据，出处内联）

- Q1 原文要求「形式化所有 INFEASIBLE 类的 partition + 对每类构造拦截 family 或证明 ⊥」（`05_open_questions.md:30-32`）。
- F16 裁定：Global Algebraic Overload 不需 cut，归 master 一行线性约束——「代数归 Master，几何归 Cut」（`PHASE_0_CLOSE.md:60-71`）。
- F13/F14/F15 反例全部以「Family 5 fallback ✅」收口（同上）——F5 的兜底角色已是既成裁定。
- F5 full no-good 退化 = 132! 置换墙（`03_paradigm_death_baseline.md:171`）；其解药（orbit-aware lift）已有 v3 设计稿与 Lean 层 `anon_lift_sound` 全链（`formal/ZmdFormal/DesignStatements.lean`）。
- 认证谓词共 6 个：ghost 内无设施 / 两两不重叠 / placement_rule / 端口精确计数 / 路由连通 / 供电覆盖（`PROJECT_LOCK.md` §1A）。前三个 master 模型内表达；后三个由子问题（binding / routing / power）判定。
- Q3：cut 的 soundness scope 与 applicability scope 必须是同一回事（`05_open_questions.md:51-64`）。
- Q18：「好 cut」无非经验定义（`05_open_questions.md:438-446`）。
- `formal/` 现有 56 条机器检查定理，其中 9 个 family 中 7 个的 infeasible-fire 形态已在抽象层证明（`formal/ZmdFormal/CutFamilies.lean`），F5 lift 链完整（`DesignStatements.lean`）。

## 2. Theorem domain（缺口 1 的补法）

**定义 D（判定宇宙）**：固定 candidate（ghost_rect + 冻结输入）语境下，master 输出的完整赋值 s（selected poses per group + 派生 cell_owner）。

**定义 D_cut（cut framework 责任域）**：
```
D_cut := { s ∈ D | MasterFeasible(s) ∧ ¬TrueFeasible(s) }
```
其中 MasterFeasible = master 模型内已有约束（no-overlap、ghost 排空、placement_rule 域、F16 类代数总量）全满足；TrueFeasible = 6 谓词全满足（真可行）。

这个定义有三个立刻的推论：

1. **F16 裁定变成定义的一部分**而非例外条款：代数总量类不可行 ⇒ ¬MasterFeasible ⇒ 不在 D_cut ⇒ 定义上不是 cut framework 的责任。「代数归 Master、几何归 Cut」从格言变成量词域的边界。
2. **Q1 命题的量词域**：完备性只需对 D_cut 成员断言，master-native 违反自动出域。
3. **D_cut 正是 LBBD 分解的定义性结构**：master relaxation 与真可行集的差。cut framework 的任务 = 用 cut 逐步消灭这个差集在搜索路径上的成员。

**边界注意（写给审查者）**：MasterFeasible 依赖 master 模型版本——master 加一条约束（如 F16 后加的 power 总量行），D_cut 收缩。所以 D_cut 是**参数化定义**（以 master 约束集 M 为参数），完备性命题必须对固定 M 陈述；M 演进时命题需重验（这正是 Q3 scope 纪律在 theorem domain 层的镜像）。

## 3. 不可行类分类学（缺口 2 的补法）

**分类维度**：按「最小违反见证（violation witness）的证据类型」分类，不按 family 分（family 是解决方案侧的分类；分类学必须站在问题侧，否则完备性命题循环）。

| 类 | 定义（witness 形态） | owner family | witness 的 Lean 抽象层（已证） |
|---|---|---|---|
| C0 代数总量 | master 线性/布尔约束违反 | **master-native**（F16） | 不适用（出域） |
| C1 容量类 | ∃ 区域/窗口 R：需求格数 > 可用格数 | F1（粗容量）→ F9（window 密度）→ F6（形状感知）精化谱系 | `f1_demand_overflow_infeasible` / `f9_overflow_infeasible` / `f6_packing_overflow_infeasible` |
| C2 连通类 | ∃ 必需连接 (a,b)：可用图上 b 不可达 | F4（belt 可达）、F8（电网可达） | `f4_unreachable_outside_closed`（F8 等几何 reconcile） |
| C3 割容量类 | 连通但 ∃ 割 δ：需求路线数 > \|δ\| | F2 | `f2_demand_overflow_infeasible` |
| C4 局部暴露类 | ∃ literal 对 {A,B}：port-front 几何冲突 | F3 | `f3_pair_literal_cut_sound` |
| C5 覆盖类 | ∃ 待覆盖集 F：可用覆盖点集空/不足 | F7（局部 CoverSet 空）、F8 | `f7_empty_cover_monotone` |
| C6 组合残余 | 无以上单证据型 witness，但 s 整体 replay-verified 不可行 | **F5（定义为兜底）** | `anon_lift_sound` 全链 |

**放弃互斥、保留穷尽 + 优先序**（对 Q1 原文「partition」措辞的一个修正）：一个 s 可以同时有容量 witness 和连通 witness——类间互斥既不成立也不必要。完备性要件是**穷尽 + 每类有 owner**；工程上 generator 按 C1→C5 优先尝试强 cut、C6 兜底，这是 triage 顺序不是数学分划。审查者请特别攻击这一步：如果有互斥才能成立的下游论证被本稿隐含使用了，属于 BLOCK。

**穷尽性是结构性的**：C6 的定义（「整体 replay-verified 不可行」）使 C1-C6 对 D_cut 穷尽——任何 s ∈ D_cut 若无 C1-C5 witness，其自身连同 replay verdict 就是 C6 witness。穷尽性由兜底类定义直接给出，无需逐类枚举论证。这不是把问题定义没了：代价全部转移到「强完备性」（§5）。

## 4. Owner lemma 模板（缺口 3 的补法）

对每类 C_i 与 owner F_j，owner lemma 的标准形态分三段：

- **(a) witness→cert 可构造性**（工程层）：若 s 有 C_i witness w，则 F_j 的 generator 从 w 可构造 cert，且 validator(cert, state) = OK。
- **(b) cut soundness**（数学层，**7/9 已在 Lean**）：cert 通过 ⇒ cut 排除集 ⊆ ¬TrueFeasible 集。C1-C5 各行的 Lean 定理见 §3 表；C6 = F5 lift 链。
- **(c) 有效性**：s ∈ cut 排除集（cut 确实排除引发它的 assignment）。
- **(scope 条款，Q3 的接入点)**：(b) 的论证只允许引用 cut.scope 字段钉死的状态成分（ghost/exterior hash 等）；scope 外状态变化不得影响 (b) 的任何前提。这把 Q3 的「soundness scope = applicability scope」变成 owner lemma 的良构条件，而非独立难题。

现状盘点：(b) 抽象层 7/9 已完成；(a) 与 (c) 是逐 family 工程验证义务（红测形态：对每类构造合成 witness → 走 generator→validator 全链 → 断言 cut 排除该 assignment），P1.3 接入时逐 family 落。

## 5. 完备性命题的拆分（本稿核心裁定）

Q1 原文的「充分性」一问拆成两个语义截然不同的命题：

**W-完备（弱完备性——每个不可行至少被拦）**：
```
∀ s ∈ D_cut，∃ F ∈ {F1..F9}：F 可产 sound cut 排除 s。
```
**裁定：W-完备在 C6 兜底定义下近乎结构性成立，且 Lean 可及。**
证明骨架：s ∈ D_cut ⇒ s replay-verified 不可行 ⇒ 以 s 的完整 literal 集为 pattern 的 F5 full nogood 满足 liftable-reject 前提（对完整赋值，「任何扩展」= 自身）⇒ 由 `anon_lift_sound`，其匿名 multiset nogood sound 且排除 s 及其整个轨道。∎
剩余工程条件（诚实清单）：① replay verdict 正确（I1/复验链义务，不是本稿范围）；② F5 generator 对任意完整赋值可构造 cert（现状 fallback 路径存在，`PHASE_0_CLOSE.md` F13-F15 裁定依赖它）；③ P-HOM 结构门成立（F5 稿实施义务）。
**推论（telemetry 桥，缺口 7）**：一旦 W-完备落为定理，「出现无 family 可拦的 INFEASIBLE」就从「数学缺口的暗示」（Q1 原文的 verification trigger 措辞）改判为「F5 fallback 实现 bug」——告警语义从研究信号变成缺陷信号。

**S-完备（强完备性——拦得有进展，真正 open 的）**：
```
∀ s ∈ D_cut，∃ F 产 sound cut，其排除集 ⊋ orbit(s)（严格强于 full nogood），
且 cut 累积在有限步内使 master 变 INFEASIBLE 或找到可行解（进展性）。
```
**裁定：S-完备不是当前可证的数学命题，且它不应该被当成 Q1 的验收目标。**
理由：① 132! 置换墙正是 W-成立 S-失败的实例——full nogood sound 但每步只删一个轨道，指数空间下无进展；② 「严格更强」依赖 witness 结构（C1-C5 有结构 witness 的类天然有强 cut；C6 残余类**定义上**没有），所以 S-完备等价于「C6 在真实实例分布下测度足够小」——这是实验命题不是定理；③ 进展性与算力墙（27 条 lever 全死的第一多米诺）本质同源，形式化它等于形式化收敛性，Q1 的框架内装不下。
**S-侧的可操作替身**（代替不可证的定理）：telemetry 双指标——cut_count_by_family 分布（C6/F5 占比持续走高 = 强 cut 覆盖不足的实验证据）+ 轨道商计数（F5 稿 §5 的组合收益口径）。阈值沿用 F5 稿验收 telemetry（>10⁵ 撞墙 / <10³ 工作）。

**对 Q1 状态的建议改写**（供 owner 裁定，本稿不自行改 05 文档）：Q1 拆为 Q1a（W-完备，可在 P3.0b 内落为 Lean 定理 + 工程红测）与 Q1b（S-完备，改判实验命题、由 P1.3 后 telemetry 承载，不再是「数学证明缺失」型 open question）。

## 6. F6/F9/F1 边界（缺口 5 的顺带收口）

分类学下三者是 C1 容量类内的**精化谱系**而非独立类：F1 = 任意区域粗容量；F9 = window 密度（把区域特化为矩形 window、owned 集特化为单 group）；F6 = 形状感知容量（把「格数」精化为「可放形状数」）。「F9 是否退化为 F1」（`05_open_questions.md:273-293`）在此视角下不是缺陷而是谱系内包含关系；F9 的独立价值判据 = 存在实例使 window 密度 witness 严格早于/强于全区域容量 witness（可写成红测）。Lean 层三条 infeasible 定理的前提集差异已经精确刻画了这个谱系（F1 的 `cells` 下界函数 vs F6 的恰 L 等式 + 分桶）。

## 7. 与 formal/ 的接口（缺口 8 的落点）

W-完备定理的 Lean 化路径（下一批砖候选，依赖已全部在库）：
1. 抽象 D_cut：`Layout` 上两个谓词 MasterFeasible / TrueFeasible + hM : TrueFeasible ⊆ MasterFeasible；
2. full-assignment nogood soundness：完整赋值的 liftable-reject 前提由「replay verdict + 扩展=自身」直接 discharge——`anon_lift_sound` 的特例引理（`LiftableReject Feasible s` 当 s 为完整赋值时 ⟺ ¬Feasible s 的适配层）；
3. W-完备骨架定理：`∀ s, ¬TrueFeasible s → ∃ cut ∈ availableCuts, sound cut ∧ excludes s`，其中 availableCuts 含 F5 fallback 构造。
预估：一个短模块（~5 条定理），无新数学，全部是既有链的组装。

## 8. 实施义务与红测（落地时执行，本稿只登记）

- R1：逐类合成 witness 红测（C1-C5 各 ≥1 例：构造 witness → generator → validator OK → cut 排除该 assignment）——owner lemma (a)+(c) 的机器锚。
- R2：F5 fallback 全链红测（任意 replay-verified 不可行完整赋值 → full nogood cert → validator OK）——W-完备工程条件②的机器锚。
- R3：C6 占比 telemetry 落点（cut_count_by_family 中 F5-fallback 单列，与 F5 稿验收阈值联动）。
- R4：「未拦截 INFEASIBLE」告警语义改判（W-完备落地后：告警 = 缺陷，不是研究信号）。
- R5：F9 独立价值红测（window witness 严格早于全区域 witness 的构造实例）。

## 9. 开放问题（本稿不解，登记给后续）

1. C2/C3 的边界：连通性 witness 与割容量 witness 在退化情形（割为空集 vs 不连通）的归类约定——建议按「不连通 ⇒ C2 优先」的 triage 序处理，但需要一个两类 owner lemma 都适用的实例来验证无缝。
2. C6 测度：真实实例分布下残余类占比——只能 P1.3 接入后实测（S-完备替身指标）。
3. Q18（好 cut 的量化）在本稿框架下 = 排除集大小/轨道商的比值排序——是否值得进 telemetry 口径，挂起。
4. partial assignment 的分类学：本稿 D 定义在完整赋值上（与当前 LBBD 回路一致——子问题只判完整赋值）；若未来 master 中途 conflict 分析需要 partial 层分类学，D 与 witness 定义需重推，**本稿结论不自动外推**。
