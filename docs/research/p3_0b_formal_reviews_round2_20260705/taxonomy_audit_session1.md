结论：**当前 v1 不宜作为 Q1 形式化定义基准**。核心想法里有可保留的部分，尤其是把 theorem domain 参数化、把 F5 residual fallback 当作 W 侧单点见证，以及把强 cut 进展性单独抽出来。但 v1 把几个原本应进入定理前提的东西留在了叙述层，又把 C6 和 telemetry 改判推得太快。总裁定：**架构级重写**，不是推倒 9-family，而是重写 §2、§3、§4、§5、§7、§8 的定义边界和证明合同。

我按最坏情况审，以下 BLOCK/CONCERN 都给了根因、反例场景、影响面和可直接替换的修复段落。

## 逐节判定表

| 节                 |          判定 | 主要原因                                                                                                                                      |
| ----------------- | ----------: | ----------------------------------------------------------------------------------------------------------------------------------------- |
| §2 Theorem domain |   **BLOCK** | D 只覆盖完整赋值，原 Q1 是 master partial assignment；`MasterFeasible` 没有完整参数化到 problem signature、master 版本、cut store、scope 语义。                      |
| §3 不可行类分类学        |   **BLOCK** | C6 用 replay-verified infeasible 兜底，等价于 D_cut residual，本身可作 fallback 域，但不能同时声称是非循环的 witness taxonomy。                                      |
| §4 Owner lemma 模板 |   **BLOCK** | 三段模板缺少 cut body 可表达性、scope-applicability 等价定理、generator 全称可构造性；R1 红测不足以替代 owner lemma。                                                    |
| §5 完备性拆分          |   **BLOCK** | W 证明骨架在设计稿中不成立，Lean 显式化后仍未封闭到工程 cut；S “不可证/不应作为 Q1 验收目标”裁定过早，telemetry 改判依赖未封闭条件。                                                         |
| §6 F6/F9/F1 边界    | **CONCERN** | 把 F1/F9/F6 说成 C1 精化谱系是合理方向，但没有真正收口 survey 中 F9 独立性、F6 length-k 边界与 F1/F9 cap 公式问题。                                                        |
| §7 与 formal/ 接口   |   **BLOCK** | `WCompleteness.lean` 证明的是 count-aware anonymous multiset nogood 的数学核，不是 `availableCuts` 中实际 F5 cert/cut；还依赖包外 `FrameworkLemmas`，复合安全链未核实。 |
| §8 实施义务与红测        |   **BLOCK** | “各 ≥1 例红测”只能防回归，不能机器锚定全称 owner lemma、F5 任意完整赋值构造性、scope soundness。                                                                        |
| §9 开放问题           | **CONCERN** | §9 承认 partial assignment 不覆盖，但这正是 Q1 原文量词域；作为开放问题登记可以，作为本稿 Q1 结论边界则不够醒目。                                                                  |

## BLOCK-1：§2 的 theorem domain 与原 Q1 量词不忠实，且 M 参数化不封闭

根因：设计稿把 D 定义成“master 输出的完整赋值”（`q1...md:24`），但权威 Q1 原文量词是“任何 master partial assignment 若 INFEASIBLE”（`authoritative_excerpts.md:7-24`）。§9 才承认 partial assignment 分类学不外推（`q1...md:118`），这意味着 §2 到 §7 实际解决的是 **Q1-full-candidate**，不是 Q1 原文。另一个洞是 `MasterFeasible` 只说“依赖 master 模型版本 M，固定 M 陈述”（`q1...md:38`），但没有区分 base master hard constraints、已累积 cuts、变量语义版本、candidate scope digest。Q3 原文恰恰说 cert sound 但 scope 错会 over-prune（`authoritative_excerpts.md:30-45`）。

最小场景：当前完整候选 s 被 replay 判 infeasible，F5 full nogood 可排除 s，这只证明 full-candidate LBBD 回路可拦。若 master 在搜索节点上已有 partial assignment p，且所有 p 的完成都不可行，Q1 原文要求存在 F1-F9 cut 排除 p 或其不可行域。v1 没有定义 partial extension、partial cut body，也没有从“每个完成 s 可被 full nogood 拦”推出“p 可被一个有限、可表达 cut 拦”。这不是小缝，是量词层错位。

另一个 M 演进场景：旧 F5 anonymous lift cut 在 slot 集合、presence key、scope digest、ghost/exterior hash 语义为 Σ₀ 时生成；后来 master M₁ 增加了 symmetry-breaking、slot profile 约束或 presence-key 投影变化。即使 TrueFeasible 没变，cut body 在 master 中的解释可能变宽，旧 cut 会在新语义下误剪。v1 只说“命题需重验”，没有说旧 cut 必须冻结语义、重验或失效。

影响面：§2 的 D_cut 定义、§5 W 完备量词、§7 Lean 化路径和 §8 telemetry 改判全部只对“固定签名下完整候选”成立。若不修，v1 会把一个 scoped theorem 冒充成 Q1 原文的 theorem domain。

可替换修复文本（替换 §2 的 D/D_cut 段落）：

> **定义 Σ 与 M（定理签名）**：所有完备性命题必须显式参数化为 `(Σ, M_base, K, scope)`。Σ 固定变量语义、group/slot/pose 类型、presence key 投影、ghost/exterior 输入和 oracle 语义版本；`M_base` 是不含 learned cuts 的 master-native hard constraints；`K` 是已经通过 scope-soundness 证明的 learned cuts；`scope` 是 cut 可复用所需的冻结状态摘要。
>
> **定义 D_full(Σ, M_base, K, scope)**：当前 LBBD 回路中交给 replay 的完整候选布局 s，满足 `MasterFeasible_Σ,M_base,K(s)`，并且 s 的所有派生字段由 Σ 决定。
>
> **定义 D_cut_full**：`{s ∈ D_full | ¬ TrueFeasible_Σ(s)}`。本稿只证明 `Q1-full-candidate`：每个 replay-verified 完整候选若不可行，则存在 F1-F9 中某 family 产生 scope-sound cut 排除该候选。
>
> **与 Q1 原文的关系**：原 Q1 的 partial-assignment 版本暂不由本稿解决。若要覆盖原 Q1，需另给 partial theorem：对任意 partial p，若不存在 `s ∈ D_full` 扩展 p 且 `TrueFeasible(s)`，则存在可表达 cut 排除 p 的所有完成，或给出从所有完成的 full-candidate cuts 合成 partial cut 的有限化定理。
>
> **M 演进纪律**：learned cut 的 soundness 不因 M 增强自动保留。每条 cut 必须携带 Σ 语义版本与 scope digest；当 Σ、presence key、slot profile、ghost/exterior、或 oracle 语义版本变化时，旧 cut 必须重新验证或失效。仅当 `TrueFeasible_Σ ⊆ MasterFeasible_Σ,M_base,K` 且每条 `k ∈ K` 已证明 scope-sound 时，D_cut_full 才是合法 theorem domain。

## BLOCK-2：§5/§7 的 W 完备证明，Lean 显式化后仍没有封闭到实际 cut framework

根因：设计稿 §5 的证明骨架写“完整赋值任何扩展等于自身”（`q1...md:77-79`）。`WCompleteness.lean` 已经发现两个隐含前提：`Feasible ⊆ Complete` 和 `Complete` 布局间无真包含（`WCompleteness.lean:11-18`）。但形式化后的主定理还额外依赖 `PartialSlotPermExtends`、`P_HOM Feasible`、`NoDuplicateNamedSlots`、`NoDuplicateNamedSlots s`（`WCompleteness.lean:48-58`），而 `anon_multiset_lift_soundness_from_named_representative` 的完整前提还包括 feasible 布局 well-formed、pattern well-formed 和 partial permutation 可延拓（`DesignStatements.lean:628-642`）。这些在设计稿 §5 的“剩余工程条件”里没有完整列出（`q1...md:79`）。

更严重的是，Lean 主定理结论只是：

`AnonMultisetNogood Feasible s ∧ AnonMultisetExtends s s`

也就是 count-aware anonymous multiset nogood 的数学 soundness 与自排除（`WCompleteness.lean:48-63`）。它还不是工程上的 `F5 generator 产 cert`、`validator OK`、`cut body 可表达在 master 中`、`cut ∈ availableCuts`。如果实际 attach 使用 boolean presence，而不是 multiset 计数，包内 `DesignStatements.lean` 明确给了额外 theorem，需要 `NoPresenceKeyAlias` 与 `PresenceKeyFaithfulForPattern`（`DesignStatements.lean:736-753`），并给了 boolean dedup 会误剪的反例（`DesignStatements.lean:806-833`）。v1 没有把这层纳入 W 完备条件。

最小反例 1：有一个 partial/incomplete pattern p 当前 replay 分支不可行，但存在可行完整扩展 A。`incomplete_assignment_fallback_unsound` 正是这个反例形状：`¬ Feasible s` 但 `¬ LiftableReject Feasible s`（`WCompleteness.lean:65-80`）。设计稿虽然说 D 是完整赋值，但没有把“replay verdict 是对 placement 的所有 binding/routing/power completion 不存在”写成 `Feasible` 的定义。如果 replay 只证明某一次 routing/binding 选择失败，full nogood 会误剪另一个可行 completion。

最小反例 2：两个同组 slot 选择同一 anonymous `(group,pose)` key 的 multiplicity-2 pattern，实际 master attach 去重成 boolean presence。包内 toy theorem 已证明：boolean presence 会被一个 one-copy feasible layout 触发，而 count-aware multiset 不会（`DesignStatements.lean:813-833`）。所以 “anon multiset sound” 不能自动推出 “实际 F5 cut sound”。

最小反例 3：`P_HOM` 不成立。若同一 group 的两个 slot 有不同 port profile、不同 recipe role、不同外部 anchor，slot permutation 不保持 TrueFeasible。此时 anonymous orbit lift 可能把只对 slot0 不可行的 pattern lift 到 slot1，误剪可行布局。v1 把 `P-HOM` 称为结构门，但没有定义失败时的降级路径。

影响面：§5 的 W 完备裁定、§7 的“无新数学”、§8 的 F5 fallback 红测、§5 telemetry 改判都依赖此链。现在 Lean 证明可以作为 “数学核 lemma”，不能作为 W 完备 theorem。

可替换修复文本（替换 §5 W 完备证明骨架与 §7 Lean 化路径）：

> **W-完备（full-candidate scoped 版本）**：对固定 `(Σ, M_base, K, scope)`，若 `s ∈ D_cut_full`，则存在 F1-F9 中某 family 生成的 cert，使 `validator_Σ(cert, state)=OK`，cut body 在当前 master 语言中可表达，cut 对 scope 内所有适用 state sound，且 cut 排除 s。
>
> **F5 fallback 见证的完整前提**：F5 anonymous lift 只能在以下前提全部机器锚定后使用：
>
> 1. `Feasible_Σ` 表示“存在满足 6 谓词的完整布局”，不是某一次 replay 分支失败；
> 2. `Feasible_Σ(A) → Complete_Σ(A)`；
> 3. 完整布局间无真包含：`Complete(s) ∧ Complete(A) ∧ s ⊆ A → s=A`；
> 4. `P_HOM Feasible_Σ` 对当前 slot equivalence class 成立；
> 5. 每个 feasible layout 与 pattern 本身满足 `NoDuplicateNamedSlots`；
> 6. 每组 partial injective slot map 可延拓为总置换，通常由有限 slot pool 证明；
> 7. 实际 cut attach 若使用 count-aware multiset，则 master body 保留 multiplicity；若使用 boolean presence，则还需 `NoPresenceKeyAlias` 与 `PresenceKeyFaithfulForPattern`。
>
> **降级纪律**：若第 4 或第 7 条失败，F5 不得使用 anonymous orbit lift；只能退化为 named full nogood，或者拒绝 cert 并报告 family implementation gap。
>
> **Lean 接口声明**：`WCompleteness.lean` 当前只证明 F5 fallback 的数学核：`AnonMultisetNogood` 与自排除。它不是完整 W theorem。完整 theorem 还必须连接 generator、validator、cut-body expression、scope applicability 和 availableCuts membership。

## BLOCK-3：§3 的 C6 是合法 residual 域，但不能同时充当非循环分类学

根因：C6 定义为“无以上单证据型 witness，但 s 整体 replay-verified 不可行”（`q1...md:52`）。而 D_cut 本身就是 `MasterFeasible ∧ ¬TrueFeasible`（`q1...md:26-30`）。因此 C6 的 witness 在逻辑上就是 “s 是 D_cut residual”。这可以作为 fallback 触发条件，但它不是和 C1-C5 同类的“证据类型”。设计稿说“穷尽性由兜底类定义直接给出，无需逐类枚举论证”（`q1...md:56`），这会把 taxonomy 的负担从“解释不可行结构”变成“只要不可行就归 C6”。这正是 survey 中“缺 exhaustive partition”的难点，不能靠残余类本身解决（`survey_completeness.md:23-28`）。

最小场景：某个 s 没有被当前 C1-C5 witness recognizer 识别，但原因不是组合残余，而是 recognizer 不完备。例如一个 routing 反例本应落 C2/C3，但可用图模型漏了单向 belt 或 turn 约束，导致 `HasC2(s)=False`、`HasC3(s)=False`，最后进 C6。W 侧 F5 full nogood 仍能拦，但 taxonomy 会误把一个结构性 routing 类吞进 residual，telemetry 也会显示 F5 占比上升，却无法区分“真实残余多”还是“C2/C3 recognizer 漏证”。

影响面：§3 的“分类学补缺口 2”、§4 owner lemma 表、§5 S-完备“C6 在真实分布测度小”的实验命题、§8 C6 telemetry 都会失真。

可替换修复文本（替换 §3 的 C6 与穷尽性段落）：

> **C6 residual，不作为结构类 witness**：C6 定义为 `Residual(s) := s ∈ D_cut_full ∧ ¬HasC1(s) ∧ ... ∧ ¬HasC5(s)`。其 witness 是 replay-verified infeasibility 加上 C1-C5 recognizer 均未产出结构 witness 的日志，而不是新的不可行结构。C6 只承担 W 侧 fallback 责任，不得用来声称 C1-C6 已给出结构性 partition。
>
> **穷尽性声明降格**：C1-C5 是结构 witness taxonomy，C6 是 operational residual bucket。由 C6 定义可得到 operational exhaustive cover：每个 `s ∈ D_cut_full` 要么有 C1-C5 witness，要么进入 C6。但这不等于“所有不可行类已分类”。C6 占比升高必须解释为两种可能：真实残余复杂，或 C1-C5 recognizer/定义漏掉结构 witness。
>
> **telemetry 口径**：F5 fallback 计数必须拆成 `F5_named_full_nogood`、`F5_anon_lift_ok`、`F5_residual_after_C1_C5_miss`，并记录 C1-C5 recognizer miss reason，防止 residual bucket 吞掉新结构类。

## BLOCK-4：§4 owner lemma 模板没有覆盖 cut framework 真正需要的全链

根因：模板只有 witness→cert、cut soundness、有效性和一句 scope 条款（`q1...md:60-67`）。但 Q3 的问题不是“只要写 scope 字段”，而是要 formalize “cut sound 范围”和“cut 适用范围”是同一回事（`authoritative_excerpts.md:30-45`）。此外 owner lemma 缺少两个关键项：cut body 可表达性，以及 generator 的全称可构造性。§8 用“每类 ≥1 合成 witness 红测”锚 owner lemma (a)+(c)（`q1...md:107`），这只能证明一个例子能跑通，不能证明“若任意 s 有 C_i witness，则 owner family generator 必可产 validator OK cert 且排除 s”。

最小场景：F1 region capacity cert 在 state₀ 中重算 cap_R sound，但 cut.scope 漏掉 exterior_blocks_hash。state₁ 中 exterior blocks 改变后，cut 仍 applicable，body 排除了一个在 state₁ 中可行的布局。validator 在 state₀ OK，数学 soundness 对 state₀ 成立，但 applicability 过宽导致 over-prune。这正是 Q3 原文的 L14/v3 anchor slicing 死法类型。

另一个场景：C1 witness 定义允许“任意区域 R 需求格数 > 可用格数”，但 F1 generator 只支持矩形或少数预定义 region。则 witness 存在不推出 cert 可构造。红测测一个 rectangle 不覆盖任意 R。

影响面：§4 是所有 C1-C6 owner 的证明骨架，§8 是落地义务。该洞会让“每类有 owner”从定理降成测试愿望。

可替换修复文本（替换 §4 owner lemma 模板）：

> 对每个结构类 `C_i` 与 owner family `F_j`，owner lemma 必须采用五段合同：
>
> **(a) recognizer soundness**：`Recognize_i(state,s)=some w → HasC_i(state,s,w)`。
> **(b) generator totality on witness domain**：`HasC_i(state,s,w) → ∃ cert, generate_j(state,s,w)=some cert ∧ validator_j(cert,state)=OK`。若 generator 只支持 witness 子类，必须把 `HasC_i` 收窄到该子类，或声明 coverage gap。
> **(c) cut body expressibility**：validator OK 的 cert 可翻译为当前 master 语言中的 cut body，且 body 的 literal/key projection 保留 multiplicity 与 alias 语义。
> **(d) scope-applicability soundness**：`validator_j(cert,state₀)=OK ∧ applicable(cert,state₁) → ∀ s', cut_excludes(cert,state₁,s') → ¬ TrueFeasible_Σ(state₁,s')`。这里 `applicable` 必须等价于所有 soundness 前提在 state₁ 中仍成立，不得只是字段哈希存在。
> **(e) effectiveness**：`cut_excludes(cert,state,s)`。
>
> 红测只能作为 regression suite；owner lemma 的 (b)(c)(d)(e) 需要机器检查、穷举小域验证、或 proof-carrying validator 合同之一支撑，不能由单例红测替代。

## BLOCK-5：§5 的 W/S 拆分有洞察，但“改判 S 非数学命题、telemetry 变缺陷信号”过早

根因：权威 Q1 的字面定义确实接近 W：不可行 assignment 必存在 F1-F9 sound cut 排除它（`authoritative_excerpts.md:7-24`）。但同一段也把 F5 full no-good 退化和 132! permutation 墙列为当前 spec 不足（`authoritative_excerpts.md:11-15`），说明项目语义下的“充分”不只是任意 named full nogood 的逻辑存在性。Q18 又说好 cut 的非经验 metric 尚未定义（`authoritative_excerpts.md:50-59`）。v1 直接裁定 S-完备“不是当前可证的数学命题，且不应该被当成 Q1 验收目标”（`q1...md:87-91`），这一步过强。更稳妥的是把 S 拆成若干可证弱化命题和实验命题，而不是整体改判不可证。

最小场景：对 C1 容量类可以证明严格强于 orbit(s) 的 region cut；对 C2/C3 routing 类可以证明 cutset/component cut 排除指数多个 routing-equivalent placements；对 C5 cover 类也可能证明 hitting-set cut 的 domination。也就是说 “S 全域完备”可能不可证或不实用，但 “S_i per witness class progress lemma” 是可证的。v1 把 C1-C5 “天然有强 cut”写成直觉（`q1...md:88`），却没有把它转成定理义务。

telemetry 改判也过早。v1 说一旦 W 完备落定，“无 family 可拦的 INFEASIBLE”就从研究信号变成 F5 fallback bug（`q1...md:80`）。但 W 完备落定需要 replay 正确、F5 任意完整赋值 cert total、P-HOM、Complete 语义、attach semantics、scope applicability 全成立。只要其中任一项未机器锚定，未拦截仍可能是 theorem domain 缝隙或 taxonomy residual 漏定义，不应直接判 bug。

影响面：§5 的核心裁定、§8 R4、项目 Q1 状态建议都会被过度降级。后续 owner 可能把真正需要证明的 progress lemma 丢给 telemetry，形成盲区。

可替换修复文本（替换 §5 S 与 telemetry 段落）：

> **S-侧拆分**：本稿不裁定 S-完备不可证。改为三层：
>
> 1. `S_i-progress`：对 C1-C5 的每个结构 witness，证明 owner cut 的排除集严格强于当前 F5 full nogood 或至少强于当前 assignment 轨道；
> 2. `S_residual`：对 C6 residual，不声称强 cut 全域存在，只统计 residual rate 与 orbit quotient；
> 3. `S_global_convergence`：cut 累积有限步收敛到 master INFEASIBLE 或可行解，这是搜索过程命题，暂列实验/后续 theorem，不作为本稿完成项。
>
> **telemetry 改判条件**：只有当 `Q1-full-candidate W theorem`、F5 generator totality、validator proof、attach refinement、P-HOM gate、scope-applicability theorem 和 replay oracle correctness 全部落地后，“unintercepted INFEASIBLE” 才能默认判为 implementation defect。在此之前，telemetry 必须保持三分：`implementation_bug`、`definition_gap`、`new_structural_class_candidate`。

## CONCERN-1：放弃互斥本身可以接受，但 priority 与 owner attribution 需要形式化

根因：设计稿正确指出类间互斥不必要（`q1...md:54`）。但它同时使用 C1→C5→C6 的 priority 作为 generator triage，而没有定义“owner attribution”在多 witness 情况下的稳定语义。若 telemetry 用 family 分布判断覆盖不足，priority 会改变观测分布。

具体场景：某个 s 同时有 C1 容量 witness 和 C2 reachability witness。若 C1 generator 因 scope/hash 条件暂时不能产 cert，triage 继续 C2；若 C1 generator 能产但很弱，C2 会被遮蔽。长期统计中 C2 真实结构类可能被 C1 抢占，误判 routing 强 cut 覆盖良好。

影响面：§3 分类学、§8 R3 telemetry、§5 S 侧替身指标。

可替换修复文本：

> **非互斥 cover 与 attribution 分离**：数学定义使用 `HasC_i(s)` 的非互斥 cover；工程 triage 使用 `first_success_family(s)`；telemetry 同时记录 `all_detected_witness_classes` 与 `emitted_family`。完备性 theorem 只引用前者，性能/coverage 分析不得只看后者。若多个 witness 同时存在，owner lemma 对每个 witness 独立陈述，不因 priority 被跳过而失效。

## CONCERN-2：§6 对 F1/F9/F6 边界的“收口”太快

根因：survey 明确说 F6 length-k 分布、F9 baseline/独立性、F9 与 F1 的 cap 公式仍是定义层缺口（`survey_completeness.md:30-32`）。v1 §6 说它们是 C1 内精化谱系，并称 Lean 前提差异已精确刻画（`q1...md:93-95`）。但包内没有 `CutFamilies.lean`，C1 表里的 F1/F6/F9 theorem 名称也无法核实。

具体场景：若 F9 的 window density witness 实际等价于某个 F1 region capacity witness，则 F9 只是 generator heuristic，不是独立 owner。反过来，若 F9 依赖 cell_owner 或 group-specific window occupancy，而 F1 的 cap 定义没有这些参数，则 F1 不覆盖 F9 witness。二者都影响 C1 的 owner lemma 陈述。

影响面：§3 C1 owner chain、§6、§8 R5。不会推翻 W fallback，但会推翻“C1 结构类已精确分解”的说法。

可替换修复文本：

> **F1/F9/F6 边界状态**：本稿只把 F1/F9/F6 归为 C1 容量型 witness 的候选 owner 谱系，不声称边界已收口。需分别补三条关系：
>
> 1. `F9_witness ⇒ C1_capacity_witness`；
> 2. 存在实例使 F9 cut 严格早于或强于 F1，或正式把 F9 降为 F1 的实现特例；
> 3. F6 shape-packing witness 与 F1 cell-count witness 的蕴含/非蕴含关系。
>    在这些定理或红测族完成前，§6 只能标为 boundary hypothesis，不应写成缺口 5 的收口。

## CONCERN-3：P-HOM 是 F5 anonymous lift 的硬门，不应只列为“实施义务”

根因：`P_HOM` 是 `anon_multiset_lift_soundness_from_named_representative` 的核心数学前提（`DesignStatements.lean:628-642`）。v1 只把它列为“F5 稿实施义务”（`q1...md:79`）。但在 fallback 场景中，完整赋值往往包含所有 slot；只要 slot 身份承载任何非对称语义，P-HOM 就可能失败。

具体场景：两个同组 slot 表面上是同型号设施实例，但 slot0 已绑定某个 port direction 或外部 anchor，slot1 没有；交换 slot 会改变 routing/power feasibility。匿名 multiset cut 会把 “slot0 选 pose p 不可行” lift 成 “slot1 选 pose p 不可行”，可能误剪。

影响面：F5 fallback、C6 owner、W theorem。若 P-HOM 不成立，仍可使用 named full nogood，但不能使用 orbit-aware lift。

可替换修复文本：

> **P-HOM gate**：F5 anonymous lift 的 slot permutation group 不得默认取“同 group 全 slot”。必须先按 `slot_profile` 划分 equivalence class，并证明 `slot_profile(s₁)=slot_profile(s₂)` 足以保持 TrueFeasible、objective-free feasibility、presence key 和 scope premises。若无法证明，则该 class 禁止 anonymous lift，退回 named full nogood。P-HOM 失败不是 telemetry 事件，而是 cert validator 必须拒绝的 soundness 前提失败。

## CONCERN-4：事实基线有两处应降级为“未核实/不完整引用”

根因：v1 §1 声称 `formal/` 现有 56 条机器检查定理、9 个 family 中 7 个 infeasible-fire 已在抽象层证明（`q1...md:20`），§3 表也列出多条 theorem 名（`q1...md:44-52`）。但包内没有 `CutFamilies.lean`，按任务纪律只能标为**未核实**。另外 v1 §1 说 F13/F14/F15 “全部以 Family 5 fallback 收口”（`q1...md:15`），权威表中 F14 是 “F9 降级 + Family 5 fallback”（`authoritative_excerpts.md:127-134`），v1 的说法不算反向错误，但遗漏了 F9 降级这一裁定细节。

影响面：事实基线、owner lemma 表可信度。不是数学核心 BLOCK，但会影响审查者对既有裁定忠实性的判断。

可替换修复文本：

> **事实基线修订**：F13/F15 以 F5 fallback 收口；F14 的裁定是 “F9 降级 + F5 fallback”，不得简写成纯 F5 fallback。
>
> **Lean 状态声明**：`CutFamilies.lean` 不在本审查包内，故 “7/9 已在 Lean” 与 §3 表中 C1-C5 的 theorem 对应在本轮标为未核实；本稿只能依赖包内可见的 `DesignStatements.lean` 与 `WCompleteness.lean`。若 v2 保留该断言，应附 theorem 列表、commit/hash、axiom audit 输出和每条 theorem 对应 owner lemma 的映射表。

## CONCERN-5：§8 的 telemetry 口径与 Q18 的关系需要降格

根因：v1 §9 说 Q18 在本框架下等于“排除集大小/轨道商的比值排序”（`q1...md:117`）。权威 Q18 只说好 cut metric 模糊，可能 proxy 包括 active rate、attached count、contribution to master infeasible（`authoritative_excerpts.md:50-59`）。把 Q18 直接归约为轨道商比值是一个合理候选，但不是权威基线。

具体场景：一个 cut 排除集很大，但永远不 active；另一个 cut 排除集较小，却直接导致 master INFEASIBLE。按轨道商比值前者更好，按 contribution 后者更好。Q18 仍未被定义层解决。

影响面：§5 S 替身指标、§8 R3/R4、§9 开放问题。

可替换修复文本：

> **Q18 接入方式**：本稿提出 `orbit_quotient_pruning_ratio` 作为 F5/S-side telemetry 候选指标之一，不把它定义为 Q18 的答案。Q18 至少保留三类指标并列：排除集或轨道商规模、active-after-replay rate、contribution-to-master-INFEASIBLE。S-side telemetry 可先记录这些指标，不在本稿中裁定全序。

## CONCERN-6：`FrameworkLemmas` 与复合安全 theorem 在包内不可审

根因：`WCompleteness.lean` 的第三个 theorem `oracle_nogood_compound_search_safety` 调用 `ZmdFormal.Framework.f5_compound_safety`（`WCompleteness.lean:82-113`），但审查包内没有 `FrameworkLemmas.lean`。因此“cut 不删光合法类”的复合安全链只能标为**未核实**，不能作为本轮支持 §5/§7 的证据。

具体场景：若 `f5_compound_safety` 的 `Sel` representative 选择只保证每个 equivalence class 有代表，但 equivalence relation 与 F5 anonymous multiset orbit 不一致，组合后可能保留的代表恰好被 cut 排除。包内无法检查其前提是否排除此类问题。

影响面：§7 formal 接口与 §5 “轨道”相关陈述。W 单点 soundness不依赖这个 theorem，但复合搜索安全依赖。

可替换修复文本：

> **复合安全链状态**：`oracle_nogood_compound_search_safety` 依赖包外 `FrameworkLemmas`，本轮不可核实。v2 不得把该 theorem 作为已审事实；应附 `FrameworkLemmas.lean`、`f5_compound_safety` 的 statement、axiom audit，以及 equivalence relation 与 F5 orbit/presence semantics 的一致性 lemma。

## 权威原文本身的歧义

Q1 的“充分”字面上是 W 命题：存在 sound cut 排除不可行 assignment。但同一 Q1 又把 F5 full no-good 的 132! 墙列为当前 spec 不足，所以项目语义里“cover”可能混有进展性期待。v1 可以提出 W/S 拆分，但不能单方面宣告 S 不属于 Q1 验收，需要 owner 对 Q1a/Q1b 重新裁定。

Q1 使用 “partition” 一词。数学上可以把 disjoint partition 放宽为 non-mutual exhaustive cover，但这应明确写成“对 Q1 原文的修订建议”，而不是直接替代。v1 已经意识到这一点，但 C6 residual 让“partition”问题被绕开得过猛。

F16 “不需 cut”在权威表中是以 Master CP-SAT 一行线性约束为裁定前提。若某个 master 版本尚未包含该行，F16 类不能自动出域；§2 应写成“在 M_base 已含 F16 master-native 行时出域”。

## 建议的 v2 重写骨架

v2 可以保留主路线，但要改成以下形状：

第一层定义 `Q1-full-candidate(Σ,M,K,scope)`，不要冒充 partial Q1。第二层把 C1-C5 定义为结构 witness cover，把 C6 定义为 operational residual。第三层把 F5 W 见证拆成两档：named full nogood 无需 P-HOM 但无进展；anonymous lift 需要 P-HOM、multiset/boolean attach refinement、slot-profile homogeneity 和 scope theorem。第四层把 S 拆为 `S_i-progress`、`S_residual telemetry`、`S_global convergence`，不要整体裁定不可证。第五层把 telemetry 改判写成 conditional，只有 W 全链落地后才把 unintercepted infeasible 默认判 bug。

最终裁定不变：**架构级重写**。修完上述 BLOCK 后，它有机会成为 “Q1-full-candidate 的形式化定义基准”；但按当前 v1，不能作为 Q1 原文的定义基准，也不能支撑 telemetry 语义改判。
