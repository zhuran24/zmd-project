我判定这份 v1 **不是架构级推倒重写**，但当前不能直接作为 Q1 定义基准合入。核心思路可以保留：固定 theorem domain、把互斥 partition 改成优先 cover、把 F5 作为 W-完备 fallback、把强进展性移到 telemetry。问题在于它现在把几个很硬的桥接前提写成了“近乎结构性”，而 Lean 化恰好暴露出这些桥还没铺完。最短结论是：**修复所列 BLOCK 后，可作为“完整候选 + replay-verified reject”的 Q1a/W-完备定义基准；原 Q1 的 partial-assignment 全域与强进展性仍不能改判为已解决。**

## 逐节判定表

| 节                 |          判定 | 主要理由                                                                                                                                         |
| ----------------- | ----------: | -------------------------------------------------------------------------------------------------------------------------------------------- |
| §2 Theorem domain |   **BLOCK** | `D_cut := MasterFeasible ∧ ¬TrueFeasible` 是语义域，但后文把它当成 replay-verified 域；还缺 `MasterSound(M)`、`Complete/WF` 由 master 候选推出、以及 M 演进时 cut 持久化规则。 |
| §3 不可行类分类学        |   **BLOCK** | C6 的“整体 replay-verified”不由 `D_cut` 推出；C5 “空/不足”超出已列 F7 empty-cover lemma；分类学应声明为 priority cover，不是 causal partition。                         |
| §4 Owner lemma 模板 |   **BLOCK** | 缺 emitted master cut 的编码/refinement lemma；缺两状态 scope theorem；“7/9 已在 Lean”在包内未核实。                                                            |
| §5 完备性拆分          |   **BLOCK** | W 证明骨架在 prose 中缺 `hFC/hNoProperExt/hsWF` 等前提；S-完备“不可证、应改判实验命题”的裁定过强，且把 C6 残余误当成“无结构”的证明。                                                     |
| §6 F6/F9/F1 边界    | **CONCERN** | 若 F1 允许任意区域，F9 是 schema/generator 特化而非数学上更强；“严格早于/强于”应定义为工程生成器性质。                                                                            |
| §7 formal/ 接口     |   **BLOCK** | §7 写出的 `∀ s, ¬TrueFeasible s → ...` 与 Lean 文件中的完整性前提不一致；`FrameworkLemmas` 与 7/9 owner lemma 不在包内，相关声明未核实。                                    |
| §8 实施义务与红测        | **CONCERN** | 红测覆盖 generator/validator，但没覆盖 Lean 暴露的新前提、scope 两状态、encoding refinement、P-HOM 与 replay totality。                                             |
| §9 开放问题           | **CONCERN** | partial assignment 被放在开放问题里是诚实的，但原 Q1 权威文本量词就是 “master partial assignment”；必须把本文结论改名为 Q1a_complete，不能代表原 Q1 全域。                              |

---

## BLOCK-1：`D_cut` 语义不可行不推出 replay-verified witness

根因：§2 把 `D_cut` 定义为 `MasterFeasible(s) ∧ ¬TrueFeasible(s)`，这是语义不可行域；§3/§5 又使用 “s replay-verified 不可行” 作为 C6 witness 与 F5 cert 的输入。`¬TrueFeasible` 到 `ReplayReject` 中间缺一个 oracle totality/completeness 前提。设计稿 §5 只列 “replay verdict 正确”，这通常只表示 soundness，不表示所有语义不可行都能被 replay 证出。

最小场景：某完整候选 `s` master-feasible，真实路由不可行，但 routing oracle 返回 `UNKNOWN/TIMEOUT`，或 replay 只发现“无法构造 cert”而非 verified reject。则 `s ∈ D_cut^sem`，无 C1-C5 witness，也没有 C6 witness，F5 fallback validator 也不能 OK。此时 “C1-C6 对 D_cut 穷尽” 与 “W-完备结构性成立” 同时失效。

影响面：§3 C6 穷尽性、§5 W-完备、§8 R2/R4 telemetry 改判全部受影响。尤其是“未拦截 INFEASIBLE = F5 bug”的桥不成立；它也可能是 replay 非 total、oracle unknown、cert 不可构造或状态 scope 不足。

可直接参考的修复文本，替换 §2 `D_cut` 定义后半与 §3 C6 前置说明：

> **定义 D_cut 分层**：固定 master 约束集 `M`、candidate context `κ` 与 frozen input 后，区分两个域：
> `D_cut^sem(M,κ) := { s ∈ D_M,κ | MasterFeasible_M(s) ∧ ¬TrueFeasible_κ(s) }`；
> `D_cut^obs(M,κ) := { s ∈ D_M,κ | MasterFeasible_M(s) ∧ VerifiedReject_κ(s) }`。
> 其中 `VerifiedReject_κ(s)` 表示 replay/oracle 在冻结语境 `κ` 下返回可复验的 INFEASIBLE certificate，且 validator 接受。
> W-完备定理先只对 `D_cut^obs` 陈述。若要把结论提升到 `D_cut^sem`，必须另列前提 `ReplayExactOnD(M,κ)`：对所有完整、well-formed master 候选 `s`，`VerifiedReject_κ(s) ↔ ¬TrueFeasible_κ(s)`。仅有 “replay verdict 正确” 不足以完成该提升。

---

## BLOCK-2：Lean 暴露的 `hFC/hNoProperExt` 还没有接回设计稿正文

根因：`WCompleteness.lean` 已把 “完整赋值无真扩展” 拆成两个显式前提：`hFC : Feasible A → Complete A` 与 `hNoProperExt : Complete s → Complete A → s ⊆ A → s = A`。但设计稿 §5 仍写成“对完整赋值，任何扩展 = 自身”，§7 甚至写出 `∀ s, ¬TrueFeasible s → ...`，没有把 `Complete(s)`、`NoDuplicateNamedSlots(s)`、`Feasible ⊆ Complete` 和 “完整布局间无真包含” 放入 theorem domain。

最小场景：`s` 放置了所有 mandatory machines，但未包含可选电杆、belt 节点或某类 subproblem 可补充对象；存在 `A = s ∪ {extra_power_pole}`，`A` 真可行且 `s ⊂ A`。若 F5 full nogood 以 `s` 为 pattern，则会排除一个有真扩展的可行布局，`LiftableReject` 不成立。`WCompleteness.lean` 中的 `incomplete_assignment_fallback_unsound` 正是在抽象层形式化了这类失败模式。

影响面：§5 W-完备证明骨架、§7 Lean 路径、§8 R2 全链红测。只证明 “完整候选” 可 full-nogood，不等于证明任意 `¬TrueFeasible` layout 可 full-nogood。

可直接参考的修复文本，替换 §5 W-完备证明骨架与工程条件清单：

> **W-完备的显式前提版**：令 `Complete_M(s)` 表示 `s` 覆盖当前 master 变量宇宙内所有必须决策的 group/slot，且每个 slot 恰一 pose、无重复 named slot、无 scope 外可追加 atom。W-完备只对满足 `Complete_M(s)` 与 `NoDuplicateNamedSlots(s)` 的完整候选陈述。证明使用以下结构前提：
>
> 1. `FeasibleComplete(M,κ)`：`TrueFeasible_κ(A) → Complete_M(A)`；
> 2. `NoProperCompleteExt(M)`：若 `Complete_M(s)`、`Complete_M(A)` 且 `s ⊆ A`，则 `s = A`；
> 3. `CandidateWF(M)`：`MasterFeasible_M(s)` 的候选输出满足 `Complete_M(s)` 与 `NoDuplicateNamedSlots(s)`；
> 4. `P_HOM(κ)` 与 finite slot-extension 结构门成立；
> 5. `VerifiedReject_κ(s)` 或语义版 `¬TrueFeasible_κ(s)` 加 `ReplayExactOnD`。
>    在这些前提下，F5 full pattern 的 `LiftableReject` 才能由 “完整布局无真扩展” discharge。

---

## BLOCK-3：数学 `AnonMultisetNogood` 与实际 master cut 之间缺 encoding/refinement lemma

根因：§4 owner lemma 只有 witness→cert、soundness、有效性三段；但 survey 的 owner lemma 缺口还要求 “cut body 可表达到 master”。包内 `DesignStatements.lean` 明确区分 count-aware `AnonMultisetNogood` 与 boolean presence cut，并给出 boolean presence 去重会强化 cut 的反例。设计稿 §5 证明的是匿名 multiset nogood sound，不等于实际 CP-SAT emitted cut 的 body 与该谓词一致或更弱。

最小场景：pattern 中同一 `(group, pose)` 需要两个 occurrence；数学 multiset cut 只排除包含两个 occurrence 的布局。若 master attach 时把它降成 boolean presence，只要出现一个 occurrence 就触发 cut，于是一个只含一个 occurrence 的可行布局被误剪。包内 `presence_dedup_strengthens_cut_counterexample` 正是这个风险的形式化版本。

影响面：§4 owner lemma、§5 F5 fallback、§7 formal interface、§8 R2。没有 encoding/refinement，Lean 的 `anon_multiset_lift_soundness_from_named_representative` 只能证明抽象谓词，不能证明实际 cut lifecycle 不 over-prune。

可直接参考的修复文本，插入 §4 owner lemma 模板为新增 (d)：

> * **(d) emitted-cut refinement / attachability**：generator 实际发给 master 的 `cut.body` 必须被证明不强于数学层已证 sound 的排除谓词。形式为：对任意候选 `A`，若 `ExcludedByEmittedCut(cert, A)`，则 `ExcludedByMathPredicate(cert, A)`；再由 (b) 推出 `¬TrueFeasible(A)`。
>   对 F5，若 emitted cut 使用 count-aware linear multiset 语义，则需证明其与 `AnonMultisetExtends` 等价；若 emitted cut 降为 boolean presence，则必须额外证明 `NoPresenceKeyAlias` 与 `PresenceKeyFaithfulForPattern`，否则 validator 必须拒绝该 cert。

---

## BLOCK-4：Q3 scope 只被口头接入，没有形成两状态 soundness theorem

根因：§4 的 scope 条款说 “(b) 的论证只允许引用 cut.scope 字段钉死的状态成分”，但这仍是一状态陈述。Q3 权威原文的风险是：cert 在生成状态 sound，但应用到更广或已变化的 state 时 over-prune。要解决 Q3，owner lemma 必须显式量化 `state0/state1` 与 applicability relation。

最小场景：F1 cert 在 `ghost_rect = G0` 时计算出区域容量不足，cut.scope 却错误标成 `GHOST_AGNOSTIC`。之后 `ghost_rect = G1` 让可用区域变大，旧 cut 仍被复用并排除一个真可行布局。validator 在 `G0` 下 OK 不足以证明在 `G1` 下 OK。

影响面：§4 owner lemma、§2 M/version 参数化、§5 telemetry 改判、§8 红测。没有两状态定理，“soundness scope = applicability scope”还只是口号。

可直接参考的修复文本，替换 §4 scope 条款：

> * **(scope 两状态条款，Q3 接入点)**：owner lemma 的 soundness 必须量化生成状态与应用状态：
>   `validator_j(cert, state0)=OK → ScopeApplies_j(cert.scope, state0, state1) → ExcludedByCut_j(cert, A, state1) → ¬TrueFeasible(state1, A)`。
>   `ScopeApplies` 必须精确包含该 family soundness proof 读取的全部 state 成分，包括 ghost/exterior hash、blocked-cells digest、presence-key schema、group homogeneity registry、candidate context 与相关 master ABI/version。任何 proof 读取但 scope 未钉死的字段都是 BLOCK。

---

## BLOCK-5：S-完备的“不可证/实验命题”裁定过强，且把残余类定义当成无结构证明

根因：§5 说 C6 “定义上没有”结构 witness，因此 S-完备等价于 “C6 在真实实例分布下测度足够小”。这一步不成立。C6 只表示“没有登记的 C1-C5 单证据型 witness”，并不证明不存在其他结构性 witness，也不证明现有 family 的泛化 owner lemma 不能给出强 cut。把 “当前 taxonomy 未捕获” 改写成 “数学上只能实验” 是过度裁定。

最小场景：所有 C6 实例共享一个未登记的 parity/coloring obstruction，或一个 multi-commodity cut obstruction。它不落 C1-C5 的单证据表述，但可以被某个新增 witness 定义或 F2/F4 泛化定理一次排除大量 orbit。按 v1 文本，这类可证强 cut 会被 C6 名义遮蔽，只被当成 telemetry 分布问题。

影响面：§5 Q1 状态改写、§8 telemetry、§9 开放问题。它会过早把一个可能可形式化的强进展子问题降级成实验指标。

可直接参考的修复文本，替换 §5 S-完备裁定段：

> **S-完备（强进展性）状态**：本稿不裁定 S-完备不可证，只把它拆成两层：
> `S_i`：对已登记 witness 类 `C_i`，owner family 是否产生严格强于 full-orbit nogood 的 cut；这是逐类可证/可证伪命题。
> `S_global(B)`：在给定实例族与资源界 `B` 下，cut 累积是否在可接受步数内收敛；这是带分布与成本参数的工程/实验命题。
> C6 仅表示 “当前 C1-C5 witness registry 未解释的 verified reject”，不表示 “无结构” 或 “不存在强 cut”。C6 占比 telemetry 是发现新 witness 或 generator 缺口的信号，不能作为不可证性的证明。

---

## BLOCK-6：§7 的 Lean 目标陈述比已形式化 theorem 强，且实际导入不封闭

根因：§7 写 “`∀ s, ¬TrueFeasible s → ∃ cut ...`”，但包内 `w_completeness_f5_fallback` 需要 `Complete s`、`NoDuplicateNamedSlots s`、`hFC`、`hNoProperExt`、`hPHOM`、`hExtend` 和 feasible well-formed。`WCompleteness.lean` 反而包含 `incomplete_assignment_fallback_unsound`，证明去掉完整性语义时 full fallback 会崩。另一个组合 theorem 还 import `ZmdFormal.FrameworkLemmas`，该文件不在包内，无法核实。

最小场景：任意 incomplete assignment `s` 已语义不可行，但有可行真扩展；§7 目标会声称 F5 可排除 `s`，而 Lean 反例说明这不成立。

影响面：§7 formal/ 接口、§5 “Lean 可及”表述、§8 落地任务拆分。

可直接参考的修复文本，替换 §7 三步 Lean 化路径：

> W-完备 Lean 目标应陈述为：
> `∀ s, CandidateComplete_M(s) → MasterFeasible_M(s) → VerifiedReject_κ(s) → ∃ cut, cut ∈ availableCuts(M,κ) ∧ SoundAtScope(cut,κ) ∧ Excludes(cut,s)`。
> 其中 `CandidateComplete_M` 展开为 `Complete_M ∧ NoDuplicateNamedSlots`，并显式导入 `FeasibleComplete`、`NoProperCompleteExt`、`P_HOM`、`PartialSlotPermExtends`、`EncodingRefinesMathPredicate` 与 `ScopeApplies`。
> 不得写成 `∀ s, ¬TrueFeasible s → ...`，除非另有 partial/incomplete 层的 liftable-reject 定理。

---

## CONCERN-1：`MasterFeasible_M` 参数化缺 “master soundness” 与 cut 持久化 ABI

根因：§2 只说 M 演进时 D_cut 收缩、命题需重验，但没有区分 static master constraints、learned cuts、schema/variable ABI，也没要求每条 master-native 约束由 `TrueFeasible → MasterFeasible_M` 支撑。若 M 变化改变变量含义、presence key 或 group homogeneity，旧 cut 的应用语义可能变化。

具体场景：`M_old` 下 F5 cut 使用某个 group/slot registry，`M_new` 将同一 group 拆成非同质子组或改 presence key；旧 cut 被加载到新 master，body 仍可解析但语义不再等于原证明对象。即使旧 cut 对 `TrueFeasible_old` sound，也不自动对新语义 sound。

影响面：§2 theorem domain、§4 scope、§8 replay/cut lifecycle。严格来说，单纯“加一条由 TrueFeasible 蕴含的 master 行且变量语义不变”不会让旧 sound cut 变 unsound；但 schema/ABI 或 scope 变化会。

可直接参考的修复文本，补入 §2 边界注意：

> `MasterFeasible_M` 只指 master-native static relaxation，不包括 learned cuts；learned cuts 属于搜索状态 `Cuts_k`。每个 master-native 约束集 `M` 必须满足 `MasterSound(M): ∀s, TrueFeasible_κ(s) → MasterFeasible_M(s)`。M 演进时，若仅新增由 `TrueFeasible` 蕴含且不改变变量语义的 row，旧 sound cut 可保留；若改变 presence key、slot registry、scope 字段、candidate context 或 master ABI，旧 cut 必须因 version/scope hash 不匹配而废弃或重新验证。

---

## CONCERN-2：放弃互斥可接受，但“partition”措辞必须彻底移除

根因：设计稿正确指出类间互斥不必要，但 §1 仍引用 Q1 的 partition，§3 又使用“分类学”“最小 witness”容易让下游继续按唯一类理解。若 owner lemma 或 telemetry 按单一归因汇总，会隐含使用互斥。

具体场景：一个 candidate 同时有容量 witness 与连通 witness。generator 按 C1 优先发 F1 cut，telemetry 只记 C1，后续评估误以为 C2 覆盖率低或该 C2 witness 不存在。数学 soundness 无碍，但覆盖统计与 owner 义务被污染。

影响面：§3 分类学、§8 cut_count_by_family、§9 C2/C3 边界。

可直接参考的修复文本，替换 §3 “放弃互斥”段首句：

> 本稿定义的是 **priority cover**，不是 partition。`HasWitness_i(s)` 可同时成立；数学命题使用 `∨_i HasWitness_i(s)` 与 owner lemma，不使用唯一类。工程 triage 可选择首个 owner cut，但 telemetry 必须允许 multi-label 记录：`all_witnesses_detected` 与 `owner_cut_emitted` 分开统计。

---

## CONCERN-3：C6 作为 fallback 证据类成立，但不是“不可行原因类”

根因：C6 的 witness 是整体 replay reject，本质是 proof artifact，不是 violation cause。它可以支撑 W-完备 fallback，但不能支撑“按 violation witness 类型”的 taxonomy 名义。

具体场景：某 residual candidate 的真实原因是三路交互 cutset，但当前 registry 无 C3 generalized witness，于是归 C6。C6 记录的是“没解释”，不是“组合残余原因”。

影响面：§3 分类学命名、§5 S-完备论证、§8 telemetry。若不澄清，C6 占比会被误读为“组合残余天然不可结构化”。

可直接参考的修复文本，替换 C6 行与穷尽性段：

> `C6_obs residual verified reject`：`s ∈ D_cut^obs` 且当前 registry 未发现 C1-C5 witness。C6 是 fallback evidence class，不是 causal infeasibility class。它保证 priority cover 的穷尽性：若没有已登记结构 witness，则 replay reject 本身可作为 F5 full fallback 的证据。C6 的 telemetry 含义是 “registry/generator 未解释比例”，不是 “数学上无强 cut 比例”。

---

## CONCERN-4：C5 “空/不足”超出当前 owner lemma 表

根因：§3 C5 写 “可用覆盖点集空/不足”，但 owner family 写 F7 “局部 CoverSet 空”，Lean 抽象也只列 `f7_empty_cover_monotone`。空 cover 与容量不足/Hall 不足不是同一个 lemma。

具体场景：两个消费者各需一个覆盖点，候选覆盖点集非空但只有一个点，且该点容量为 1。`CoverSet` 不空，但整体覆盖容量不足。F7 empty-cover lemma不能拦；若没有 Hall/hitting-set 容量 lemma，这个 C5 witness 没 owner。

影响面：§3 owner 表、§4 owner lemma (a)(b)、§8 R1 红测。

可直接参考的修复文本，替换 C5 行：

> `C5a 空覆盖类`：存在待覆盖对象 `f`，其合法 CoverSet 为空；owner = F7，Lean target = `f7_empty_cover_monotone`。
> `C5b 覆盖容量不足类`：存在覆盖需求集合 `F` 与可用覆盖点集合 `P`，满足容量/Hall 条件失败；owner 暂定 F7-capacity 或 F8，但必须新增 owner lemma。若暂无 lemma，C5b 不得标为已覆盖，只能落 C6 fallback。

---

## CONCERN-5：F9/F1 的“独立价值”混合了数学表达力与生成器策略

根因：§6 说 F1 是任意区域粗容量，F9 是矩形 window 特化。若 F1 真允许任意区域，则 F9 witness 在 proof-system 表达力上被 F1 包含；F9 的价值只能是更早发现、更低成本、更稳定 scope 或更好 generator，不是数学上更强。

具体场景：某 window density overflow 被 F9 发现。若 F1 generator 也允许选择同一个 window region 与同一 demand/cap 口径，则 F1 可生成同等 cut。所谓 “F9 严格强于 F1”只是在当前 F1 generator 不枚举该 window 时成立。

影响面：§6 边界、§8 R5 红测、Q18 quality metric。

可直接参考的修复文本，替换 §6 后半段：

> 若 F1 schema 允许任意 region，则 F9 不是新的不可行类，而是 F1 容量 schema 的 window-specialized generator/validator profile。F9 的独立价值应定义为工程性质：在受限枚举预算、scope 粒度或 cert size 下，F9 generator 能发现 F1 baseline generator 未发现或成本过高的 witness。若要主张数学分离，必须先限制 F1 的 region universe，并给出 F9 witness 不可由该受限 F1 表达的 separation theorem。

---

## CONCERN-6：telemetry 改判前提不可只写 “W-完备落地”

根因：§5/§8 把 “无 family 可拦的 INFEASIBLE” 改判为 F5 fallback bug，但真正需要的是完整工程链：`D_cut^obs` 域、replay totality 或明确 UNKNOWN、F5 generator total、validator encoding refinement、P-HOM gate、scope applicability、cut registry dispatch 全部成立。

具体场景：telemetry 看到 replay INFEASIBLE，但 F5 validator 拒绝，因为 pattern 含 presence-key alias，boolean attach 不安全。这不是数学 cover 不完整，也不一定是 F5 generator bug；它可能是 schema encoding 未满足，或应走 count-aware emitted cut。

影响面：§5 telemetry 桥、§8 R4 告警语义。

可直接参考的修复文本，替换 R4：

> R4 告警分层：W-完备所有 gates 通过后，`VerifiedReject ∧ no_emitted_cut` 才判为 implementation defect。若 replay 为 UNKNOWN/TIMEOUT，归 oracle-totality gap；若 validator 因 P-HOM、presence alias、scope hash、schema ABI 拒绝，归 gate failure；若 C6/F5 占比升高但 cut 正常生成，归 strong-cut coverage/quality signal。只有 gate-complete 情形下才允许把 “未拦截 INFEASIBLE” 改判为 F5 fallback bug。

---

## CONCERN-7：§8 红测缺少 Lean 新前提的机器锚

根因：R1/R2 只测 generator→validator→excludes，但不测 `FeasibleComplete`、`NoProperCompleteExt`、`CandidateWF`、`P_HOM`、`EncodingRefinesMathPredicate`、`ScopeApplies` 等真正支撑 W theorem 的前提。

具体场景：R2 随机拿一个 replay-verified 完整赋值，F5 cert OK；但另一个候选带重复 named slot 或 presence-key alias，数学 theorem 不适用，validator 仍误发 boolean cut。R2 不会发现。

影响面：§8 实施义务完整性、§5 “Lean + 红测”落地口径。

可直接参考的修复文本，追加到 §8：

> R6：Candidate domain gate 红测：master 输出必须满足 `Complete_M`、`NoDuplicateNamedSlots`，并负测 incomplete/duplicate 候选不得进入 F5 fallback。
> R7：NoProperCompleteExt 结构测试：对所有 selectable group/slot，完整候选不存在合法真扩展；optional/derived 对象必须明确在 layout universe 内或 scope 外。
> R8：P-HOM registry 测试：每个可被匿名 lift 的 group 必须通过 slot-homogeneity gate；非同质 group 负测必须拒绝。
> R9：F5 emitted-cut refinement 测试：count-aware body 与 `AnonMultisetExtends` 一致；boolean presence 模式必须测试 duplicate/alias 反例并拒绝。
> R10：两状态 scope 红测：对 ghost/exterior/schema/group registry 变化构造旧 cut 复用负例，断言 scope mismatch 导致 cut 失效而非继续应用。

---

## CONCERN-8：partial assignment 被标开放是诚实的，但不能同时声称解决 Q1 原文

根因：权威 Q1 文本量词是 “任何 master partial assignment 若 INFEASIBLE”。设计稿 §2/§9 把 domain 限到完整赋值，并说 partial 层未来重推。这可以成立为当前 LBBD complete-candidate theorem，但不能叫作原 Q1 全覆盖。

具体场景：CP-SAT 中途产生一个 assumption subset 或 partial placement `p`，所有完整扩展都不可行，但 `p` 本身不是完整 layout。F5 full-assignment nogood 不适用；C1-C5 witness 也可能需要 partial 版本。原 Q1 partial 命题仍 open。

影响面：§5 Q1a/Q1b 改写、§7 theorem 目标、§9 开放问题。

可直接参考的修复文本，替换 §9 第 4 点并回链 §5：

> 本稿结论命名为 `Q1a_complete_candidate_W`：只覆盖当前 LBBD 回路中 replay-verified 的完整 master candidate。原 Q1 的 partial-assignment 版本保留为 `Q1p_partial_coverage`：
> `∀ p, MasterPartialFeasible(p) ∧ NoTrueCompleteExtension(p) → ∃ family cut soundly excluding p or all its extensions`。
> 在给出 partial→complete bridge 或 partial owner lemmas 前，不得把 Q1a 结论外推到原 Q1 全域。

---

## 引用忠实性与未核实项

F16 引用基本忠实：权威摘录确实写 Global Algebraic Overload 不需 cut、归 Master CP-SAT 一行线性约束，且有“代数归 Master，几何归 Cut”的裁定。

F13/F15 引用忠实；F14 在权威摘录里是 “F9 降级 + Family 5 fallback ✅”。设计稿说 “F13/F14/F15 全部以 F5 fallback 收口”没有直接造假，但省略了 F14 的 F9 降级部分。建议在 §1 改成 “F13/F15 走 F5 fallback；F14 走 F9 降级 + F5 fallback”。

Q3 引用忠实，但设计稿没有真正完成 Q3，只把它纳入 owner lemma 纪律。应避免“变成良构条件而非独立难题”这种过强表述。

Q18 引用忠实地承认 “好 cut”无非经验定义，但 §9 说 “Q18 在本稿框架下 = 排除集大小/轨道商的比值排序”过早。更安全说法是 “一个候选 metric”。

“formal/ 现有 56 条机器检查定理、7/9 family infeasible-fire 已在 Lean、CutFamilies.lean”在包内无法核实；本审只能标注 **未核实**。`WCompleteness.lean` 与 `DesignStatements.lean` 包内可读，但没有 Lean 工具链与 `FrameworkLemmas` 文件，组合 theorem 的编译状态也无法独立核实。

---

## Lean 前提闭包结论

`WCompleteness.lean` 的核心 theorem 在抽象数学层是清楚的：给定 `Complete`、`Feasible ⊆ Complete`、完整布局无真包含、P-HOM、slot permutation extension、feasible well-formed、pattern well-formed，就能从完整不可行 layout 得到 count-aware F5 anonymous multiset nogood，并排除自身。

但这个前提集**没有封闭到设计稿声称的工程 W-完备**。缺的不是 Lean 证明步骤，而是语义桥：`s ∈ D_cut` 如何推出 `VerifiedReject`、`Complete`、`NoDuplicateNamedSlots`；actual emitted cut 如何 refine `AnonMultisetNogood`；scope 如何跨 state 保持；M/ABI 如何固定；partial assignment 如何排除在命题外。换句话说，Lean 文件把 “证明骨架洞”从一个洞变成了一组显式门禁，但设计稿正文还没把门禁接上线。

## 总裁定

**修复所列问题后可作为 Q1 形式化的定义基准**，但建议正式命名为 `Q1a_complete_candidate_W`，不要直接宣称解决原 Q1。当前 v1 的架构方向可保留；必须重写的是 §2/§5/§7 的 theorem statement 与 §4/§8 的工程桥接条款。只要把 replay 域、完整性闭包、encoding refinement、两状态 scope、P-HOM gate、M/version ABI 和 partial-scope 限定补齐，这份设计稿就能从“漂亮但漏风的纸桥”变成可机械化的定义底座。
