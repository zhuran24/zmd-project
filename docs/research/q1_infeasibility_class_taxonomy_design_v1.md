# Q1 不可行类分类学与完备性命题设计稿 v2

**Status:** HISTORICAL_OR_PLAN（研究层设计稿，不改生产代码/锁面）
**Authored:** 2026-07-05（v1 同日送双会话对抗审；**v2 = 外审回收版**——
会话 A 判"架构级重写"、会话 B 判"修复后可作 Q1a 基准"，两份实质收敛；
v2 按两份修复文本融合重写 §2/§3/§4/§5/§7/§8/§9，原件归档
`docs/research/p3_0b_formal_reviews_round2_20260705/`（6/7 号文件））
**Scope authority:** 本稿不改变 `PROJECT_LOCK.md` 任何条款；Q1 在
`05_open_questions.md` 的 P0/defer 状态不因本稿改变。

**任务**：Q1（9 个 cut family 是否 cover 所有 INFEASIBLE 类）当前是经验性
覆盖框架。本稿补定义层。**v2 起最重要的自我限定（外审 BLOCK 共识）**：
本稿解决的命题命名为 **`Q1a_complete_candidate_W`**——只覆盖当前 LBBD
回路中 **replay-verified 的完整 master 候选**；Q1 原文的量词是"任何
master **partial assignment**"，partial 层保留为 open（§9 `Q1p`），
**本稿结论不得外推到原 Q1 全域**。

---

## 1. 事实基线（v2 修订两处）

- Q1 原文要求「形式化所有 INFEASIBLE 类的 partition + 对每类构造拦截
  family 或证明 ⊥」，量词域是 master partial assignment（`05_open_questions.md:17-32`）。
- F16 裁定「代数归 Master，几何归 Cut」（`PHASE_0_CLOSE.md:60-71`）。
  **条件化（v2）**：F16 类出域仅当 M_base 已含对应 master-native 行。
- 反例裁定（v2 修正引用）：**F13/F15 走 F5 fallback；F14 走 F9 降级 +
  F5 fallback**（v1 简写漏了 F14 的 F9 降级部分）。
- F5 full no-good 退化 = 132! 置换墙；orbit lift 解药有 v3 设计稿与
  Lean 层 `anon_lift_sound` 全链。
- 认证谓词 6 个：ghost 内无设施/两两不重叠/placement_rule/端口精确计数/
  路由连通/供电覆盖（`PROJECT_LOCK.md` §1A）。
- **Lean 状态声明（v2，外审"未核实"处理）**：本稿引用的 `formal/` 定理
  （CutFamilies 19 条 / DesignStatements 16 条 / FrameworkLemmas 14 条 /
  WCompleteness 4 条，公理审计 68/68）以 main `995373e` 为锚；送审时
  必须随包附全部 `.lean` 与 axiom audit 输出，未附即视为未核实断言。

## 2. Theorem domain（v2 重写：签名参数化 + 语义/观测分层）

**定义 Σ 与 M（定理签名）**：所有完备性命题显式参数化为
`(Σ, M_base, K, scope)`——Σ 固定变量语义、group/slot/pose 类型、
presence-key 投影、ghost/exterior 输入与 oracle 语义版本；`M_base` 是
**不含 learned cuts** 的 master-native hard constraints；`K` 是已过
scope-soundness 证明的 learned cuts（属搜索状态，不属 M_base）；`scope`
是 cut 可复用所需的冻结状态摘要。要求 `MasterSound(M_base)`：
`∀ s, TrueFeasible_Σ(s) → MasterFeasible_{M_base}(s)`。

**定义 D_full(Σ, M_base, K, scope)**：当前 LBBD 回路交给 replay 的完整
候选布局 s（`Complete_M(s) ∧ NoDuplicateNamedSlots(s)`，由 master 输出
合同 `CandidateWF(M)` 保证——这是义务不是假设，红测 R6）。

**定义 D_cut 分层（v2 关键修正——语义不可行 ≠ 可复验拒绝）**：
```
D_cut^sem := { s ∈ D_full | MasterFeasible(s) ∧ ¬TrueFeasible(s) }
D_cut^obs := { s ∈ D_full | MasterFeasible(s) ∧ VerifiedReject(s) }
```
`VerifiedReject(s)` = replay/oracle 在冻结语境下返回**可复验的**
INFEASIBLE 证书且 validator 接受。**W 定理只对 `D_cut^obs` 陈述**；
提升到 `D_cut^sem` 需另列 `ReplayExactOnD` 前提（replay totality——
UNKNOWN/TIMEOUT 存在时该前提为假，"replay verdict 正确"只给 soundness
不给 totality）。

**M 演进纪律（v2）**：learned cut 的 soundness 不因 M 增强自动保留。
仅新增由 TrueFeasible 蕴含且不改变量语义的 row 时旧 cut 可保留；
presence key / slot registry / scope 字段 / candidate context / master
ABI 任一变化 ⇒ 旧 cut 必须因 version/scope hash 不匹配而废弃或重验。

## 3. 不可行类 priority cover（v2：partition 措辞全部移除）

**本稿定义的是 priority cover，不是 partition**：`HasWitness_i(s)` 可
同时成立；数学命题用 `∨_i HasWitness_i` 与逐 witness 的 owner lemma，
不用唯一归因。工程 triage 取首个成功 owner，但 telemetry 必须
multi-label（`all_witnesses_detected` 与 `owner_cut_emitted` 分开记录，
防 priority 遮蔽真实类分布——外审 CONCERN 场景：C1 抢占 C2 导致
routing 覆盖被误判良好）。

| 类 | witness 形态 | owner | Lean 锚（main 995373e） |
|---|---|---|---|
| C0 代数总量 | master 线性/布尔约束违反 | master-native（M_base 含该行时出域） | 不适用 |
| C1 容量类 | ∃ 区域/窗口 R：需求格数 > 可用格数 | F1/F9/F6 候选谱系（边界假设，见 §6） | `f1_*`/`f9_*`/`f6_*` |
| C2 连通类 | ∃ 必需连接：可用图上不可达 | F4、F8（F8 等 reconcile） | `f4_unreachable_outside_closed` |
| C3 割容量类 | ∃ 割 δ：需求路线数 > \|δ\|（分离性为工程义务） | F2 | `f2_demand_overflow_infeasible` |
| C4 局部暴露类 | ∃ literal 对：port-front 冲突 | F3 | `f3_pair_literal_cut_sound`（multiset 版） |
| C5a 空覆盖类 | ∃ 待覆盖对象：合法 CoverSet = ∅ | F7 | `f7_empty_cover_monotone` |
| C5b 覆盖容量不足类（v2 新拆） | CoverSet 非空但容量/匹配条件失败 | **暂无 owner lemma**——落 C6，不得标已覆盖 | 待补（Hall/hitting-set 容量层） |
| C6 residual（v2 降格） | `s ∈ D_cut^obs ∧ ¬HasC1..C5`——**operational residual bucket，fallback evidence class，不是 causal 结构类** | F5 fallback | `w_completeness_f5_fallback` |

**穷尽性声明（v2 降格）**：C6 定义给出的是 **operational exhaustive
cover**（每个 `s ∈ D_cut^obs` 要么有结构 witness 要么进 residual），
**不是**"所有不可行类已分类"。C6 占比升高有两种解释：真实组合残余多，
或 **C1-C5 recognizer 漏证**（外审场景：单向 belt 约束漏建模使 routing
类反例假性入 C6）——telemetry 必须记录 recognizer miss reason 以区分。

## 4. Owner lemma 五段合同（v2 重写，原三段模板不足）

对每个结构类 `C_i` 与 owner `F_j`：

- **(a) recognizer soundness**：`Recognize_i(state,s) = some w → HasC_i(state,s,w)`；
- **(b) generator totality on witness domain**：`HasC_i(...,w) → ∃ cert,
  generate_j(...) = some cert ∧ validator_j(cert,state) = OK`。generator
  只支持 witness 子类时必须把 `HasC_i` 收窄到该子类或声明 coverage gap
  （外审场景：C1 允许任意区域而 F1 generator 只枚举矩形 ⇒ witness 存在
  不推 cert 可构造）；
- **(c) emitted-cut refinement（v2 新增）**：实际发给 master 的
  `cut.body` 不得强于数学层已证 sound 的排除谓词——
  `ExcludedByEmittedCut(cert,A) → ExcludedByMathPredicate(cert,A)`。
  对 F5：count-aware body 须证与 `AnonMultisetExtends` 一致；降为
  boolean presence 则必须另证 `NoPresenceKeyAlias` +
  `PresenceKeyFaithfulForPattern`，否则 validator 拒绝（Lean 层
  `presence_dedup_strengthens_cut_counterexample` 正是违反本条的反例）；
- **(d) 两状态 scope soundness（v2 新增，Q3 的真接入点）**：
  `validator_j(cert,state₀)=OK → ScopeApplies(cert.scope,state₀,state₁) →
  ExcludedByCut(cert,A,state₁) → ¬TrueFeasible(state₁,A)`。`ScopeApplies`
  必须精确覆盖 soundness 证明读取的全部状态成分（ghost/exterior hash、
  blocked-cells digest、presence-key schema、group homogeneity registry、
  candidate context、master ABI）；**证明读取但 scope 未钉死的字段 =
  BLOCK**（这正是 L14/anchor-slicing 死法与 GHOST_AGNOSTIC 误标场景）；
- **(e) effectiveness**：`cut_excludes(cert,state,s)`。

数学半边（cut 排除集 ⊆ 不可行集的抽象层）7/9 在 Lean；(a)(b)(c)(d) 是
工程验证义务。**红测只能作 regression suite，单例不能锚全称**——(b)(c)(d)
需要机器检查、小域穷举或 proof-carrying validator 合同之一支撑。

## 5. 完备性命题（v2 重写：Q1a 定名 + 前提全列 + S 三层拆分）

**Q1a_complete_candidate_W（对 D_cut^obs，固定 (Σ,M_base,K,scope)）**：
```
∀ s ∈ D_cut^obs，∃ F ∈ {F1..F9}：F 产生 cert，validator OK，
cut body 可表达且 refine 数学谓词，scope-sound，且排除 s。
```
**F5 fallback 见证的完整前提清单（v2，Lean 显式化 + 外审补全）**：
1. `Feasible` 语义 = "存在满足 6 谓词的完整布局"，**不是某一次
   routing/binding 分支失败**（replay verdict 必须是对全部 completion
   的可复验拒绝）；
2. `FeasibleComplete`：TrueFeasible ⊆ Complete；
3. `NoProperCompleteExt`：完整布局间无真包含（optional 对象——电杆、
   belt 节点——必须明确在 layout universe 内或 scope 外，红测 R7）；
4. `CandidateWF`：master 输出满足 Complete ∧ NoDuplicateNamedSlots；
5. `P_HOM` 按 **slot_profile 等价类**成立（v2 硬化：置换群不得默认取
   "同 group 全 slot"；须先按 slot_profile 分类并证同 profile 保
   TrueFeasible/presence key/scope 前提。**P-HOM 失败 = validator 必须
   拒绝的 soundness 前提失败，不是 telemetry 事件**）；
6. 有限 slot 池的部分单射延拓（`partialSlotPermExtends_of_fintype`）；
7. attach 层 refinement（§4(c)）。
**降级纪律**：第 5/7 条失败 ⇒ 禁 anonymous lift，退 named full nogood
或拒 cert 报 implementation gap。

**裁定（v2 收窄）**：在前提 1-7 全部机器锚定后，Q1a 由
`w_completeness_f5_fallback` + `anon_lift_sound` 的组装给出。**当前
Lean 定理是数学核 lemma，不是工程 W 定理**——缺的语义桥（obs 域、
Complete 闭包、encoding refinement、两状态 scope、ABI 固定）就是
§4/§8 的义务清单。

**S-侧（v2：撤回"不可证"整体裁定，改三层）**：
- `S_i-progress`（**逐类可证/可证伪命题，是定理义务不是直觉**）：对
  C1-C5 的每个结构 witness，owner cut 的排除集严格强于当前赋值轨道；
- `S_residual`：C6 占比与轨道商 telemetry——**注意 C6 占比升高不证明
  "无结构"**，可能是未登记的结构 obstruction（parity/多商品割），是
  发现新 witness 类的信号；
- `S_global(B)`：给定实例族与资源界下 cut 累积有限步收敛——带分布
  参数的实验/后续定理，本稿不承诺。

**telemetry 改判（v2 conditional 化）**：只有 Q1a 全部 gates（replay
totality 分层、F5 generator totality、encoding refinement、P-HOM gate、
两状态 scope、ABI 锚）落地后，`VerifiedReject ∧ no_emitted_cut` 才默认
判 implementation defect。此前告警保持四分：`implementation_bug` /
`oracle_totality_gap`（UNKNOWN/TIMEOUT）/ `gate_failure`（P-HOM、alias、
scope hash 拒绝）/ `new_structural_class_candidate`。

## 6. F1/F9/F6 边界（v2 降格为 boundary hypothesis）

三者是 C1 容量型 witness 的**候选 owner 谱系**，边界未收口。若 F1
schema 允许任意 region，则 F9 在 proof-system 表达力上被 F1 包含，
其独立价值是**工程性质**（受限枚举预算/scope 粒度/cert size 下更早
发现）而非数学更强；主张数学分离须先限制 F1 region universe 并给
separation theorem。待补三条关系：① F9_witness ⇒ C1_capacity_witness；
② F9 严格早于/强于 F1 的实例（或正式降 F9 为 F1 实现特例）；③ F6
shape witness 与 F1 cell-count witness 的蕴含关系。survey 点名的
F6 length-k 边界、F9 baseline 问题保持 open。

## 7. 与 formal/ 的接口（v2 重写目标陈述）

**当前已有**（main `995373e`）：F5 fallback 数学核
（`complete_infeasible_liftable_reject` / `w_completeness_f5_fallback` /
`incomplete_assignment_fallback_unsound` 反例 /
`oracle_nogood_compound_search_safety` 组合）。

**W 定理的正确 Lean 目标形态（v2，替换 v1 的过强形态）**：
```
∀ s, CandidateComplete_M(s) → MasterFeasible_M(s) → VerifiedReject(s) →
  ∃ cut ∈ availableCuts(M,κ), SoundAtScope(cut,κ) ∧ Excludes(cut,s)
```
**不得写成 `∀ s, ¬TrueFeasible s → …`**（v1 §7 原文即此错——比已形式化
定理强；`incomplete_assignment_fallback_unsound` 正是其反例）。从数学核
到该目标缺的是 §4(b)(c)(d) 的工程桥，`availableCuts` 成员性与
`SoundAtScope` 是新的形式化对象，不是"无新数学"。

## 8. 实施义务与红测（v2 扩到 R10）

- R1：逐类合成 witness 红测（C1-C5a 各 ≥1 正例全链）——回归锚，
  **不替代** owner lemma (b)(c)(d)；
- R2：F5 fallback 全链红测；
- R3：C6 telemetry 拆分（`F5_named_full_nogood` / `F5_anon_lift_ok` /
  `F5_residual_after_C1_C5_miss` + recognizer miss reason）；
- R4：告警四分语义（§5）；
- R5：F9 独立价值红测（§6 关系②）；
- R6（v2）：candidate domain gate——master 输出必须 Complete ∧
  NoDuplicateNamedSlots，负测 incomplete/duplicate 不得进 F5 fallback；
- R7（v2）：NoProperCompleteExt 结构测试（optional 对象归属显式化）；
- R8（v2）：P-HOM slot-profile registry 测试（非同质 group 负测必须拒）；
- R9（v2）：F5 emitted-cut refinement 测试（count-aware 一致性；boolean
  presence 的 duplicate/alias 反例必须拒）；
- R10（v2）：两状态 scope 红测（ghost/exterior/schema/registry 变化下
  旧 cut 复用负例，断言 scope mismatch 失效而非继续应用）。

## 9. 开放问题（v2 重排）

1. **Q1p_partial_coverage（原 Q1 的 partial 层，本稿不解）**：
   `∀ p, MasterPartialFeasible(p) ∧ NoTrueCompleteExtension(p) → ∃ family
   cut soundly excluding p or all its extensions`。在给出 partial→complete
   bridge 或 partial owner lemma 前，Q1a 结论不得外推。
2. C5b 的 owner lemma（覆盖容量不足层，Hall/hitting-set）。
3. C2/C3 退化边界的 triage 约定。
4. Q18：`orbit_quotient_pruning_ratio` 只是**候选指标之一**（v2 降格），
   与 active-after-replay rate、contribution-to-master-INFEASIBLE 并列，
   本稿不裁定全序。
5. `ReplayExactOnD`（replay totality）是否值得作为独立形式化对象。

## 10. v1→v2 修订记录（外审回收）

双会话对抗审（归档 round2/6、7 号），实质收敛。v2 吸收的 BLOCK：
① 量词层错位 → 定名 Q1a_complete_candidate_W + Q1p 显式登记；
② D_cut 语义/观测分层（¬TrueFeasible ≠ VerifiedReject）；
③ (Σ,M_base,K,scope) 签名参数化 + M 演进 ABI 纪律；
④ C6 降格 operational residual（不再兼任结构类）+ 穷尽性声明降格；
⑤ owner lemma 三段 → 五段（补 emitted-cut refinement + 两状态 scope）；
⑥ W 前提清单补全（Lean 的 hFC/hNoProperExt/P_HOM/WF 接回正文 +
replay 语义前提）；⑦ S"不可证"裁定撤回 → 三层拆分（S_i 是定理义务）；
⑧ telemetry 改判 conditional 四分。CONCERN：C5 拆 a/b、F14 引用修正、
F9/F1 边界降格假设、P-HOM slot_profile 硬门、attribution 分离、
Q18 降格、Lean 引用附锚纪律、红测 R6-R10。
两份审查对"主路线可保留"一致：theorem domain 参数化、priority cover、
F5 residual fallback 作 W 见证、强进展分离——v2 保留该骨架。
