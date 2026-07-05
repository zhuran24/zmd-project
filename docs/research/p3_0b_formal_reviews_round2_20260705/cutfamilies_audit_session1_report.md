# CutFamilies.lean 陈述保真对抗审

审计对象：`/mnt/data/cut_audit/CutFamilies.lean`，对照包内 `CONTEXT.md` 与 `survey_*.md` 的 proposition / formalization_needs / latent_issues。

编译状态：未能本地编译修复片段。当前沙盒没有 Lean 工具链，`lean --version` 和 `lake --version` 均返回 command not found；因此所有 patch snippet 标注为“未经编译”。原始包声称已编译，本审计只攻击陈述保真，不攻击内核证明。

## 17 条逐条结论

| # | theorem / def 附近 | family | 结论 | 核心判断 |
|---:|---|---|---|---|
| 1 | `f9_area_bound` | F9 | 忠实 | 正好是 `A∩W ⊆ W\B ⇒ |A∩W|≤|W\B|` 的面积计数核心。|
| 2 | `f9_overflow_infeasible` | F9 | 忠实 | 是上述 bound 的逆否形态；`cell_owner` well-formed 的“无 ghost/exterior owner”被抽成子集前提。|
| 3 | `f1_occupancy_bound` | F1 | CONCERN | survey proposition 是 group-level `Σ demand(g)·cells(g)`；当前 theorem 只对已展开的 per-instance `S` 求和，展开步骤未入陈述。|
| 4 | `f1_demand_overflow_infeasible` | F1 | CONCERN | 同上；若 `S` 被理解为 contributor group 而非 demand slots，会证明一个弱得多的命题。|
| 5 | `f7_cover_filter_monotone` | F7 | 忠实 | 纯集合单调性 lemma 与 survey 的 monotonicity core 一致。|
| 6 | `f7_empty_cover_monotone` | F7 | CONCERN | 只证明“某个 Free 的空覆盖保持”，没有把 replay-safe 的 ghost-only scope 和“无 cover anchor”结论写进陈述。|
| 7 | `f4_closed_set_absorbs_reach` | F4 | 忠实 | 可达闭包 lemma 与 BFS reachable component 的抽象核心一致。|
| 8 | `f4_unreachable_outside_closed` | F4 | 忠实 | sink 在封闭 reachable set 外 ⇒ 无路径，忠实。|
| 9 | `f4_subgraph_reach_mono` | F4 | 忠实 | 子图可达蕴含原图可达，忠实于阻挡增加不新增 reachability。|
| 10 | `f6_strip_capacity` | F6 | 忠实 | 容量上界只需 L-card、互斥、subset；比 contiguous interval 更一般但不失真。|
| 11 | `f6_packing_bound` | F6 | CONCERN | survey 的“不跨阻挡”是每个 pose 存在某 interval；当前陈述要求外部给固定 `bucket : ι→κ`，量词/工程义务偏硬。|
| 12 | `f6_packing_overflow_infeasible` | F6 | BLOCK | 只排除“给定 bucket 且全部 S 在本区域”的直接 overflow；没有表达当前实现的 `C_R < d_R ≤ max(0,D−C_R')` fire 条件。|
| 13 | `f6_cross_side_lower_bound` | F6 | 忠实 | Nat 截断减法就是 `max(0,D−C')`；该算术 lemma 本身忠实。|
| 14 | `f2_cutset_bound` | F2 | 忠实 | 在 `hhit` 与 edge-disjoint 前提下的鸽笼计数完全正确。|
| 15 | `f2_demand_overflow_infeasible` | F2 | CONCERN | 把“每条路必过 δ”放进被否定的 legal predicate 里，导致它只证明 `¬(hhit∧disjoint)`，不是 separator 已证后 `¬disjoint route family`。|
| 16 | `f3_blocked_port_infeasible` | F3 | 忠实 | 对 all-ports-active、cell_owner blocker 分支，正好是否定 `PortExposureFree`。|
| 17 | `f3_pair_literal_cut_sound` | F3 | BLOCK | docstring 声称 lifecycle 的 literal 子多重集语义，但 theorem 用 `Finset {A,B}⊆selected`，会把重复 literal 折叠。|

## 非“忠实”项详情

### F1 `f1_occupancy_bound` / `f1_demand_overflow_infeasible` — CONCERN

根因：survey 的命题是对 contributor groups 求 `Σ demand(g)·cells_per_pose(g)`。当前 theorem 的 `S` 可以被解释成 demand 展开的 slot 集，此时可救；但陈述和 docstring 没有记录这个 reindexing/slot expansion。若调用方自然地令 `S = C` 为 group 集，`cells g = cells_per_pose g`，则 theorem 不再是 survey proposition。

最小反例：一个 group `g`，`demand(g)=2`，`cells_per_pose(g)=1`，`Free.card=1`。survey 的 fire 是 `1 < 2*1`，不可行。当前 theorem 若 `S={g}` 且 `cells g=1`，fire 变成 `1 < 1`，无法推出任何东西。要用当前 theorem，必须额外构造两个 slot `g#0,g#1`，这个桥没有在陈述里。

影响面：不是内核 false proof，但会把 F1 的 Lean 定理从“validator proposition”降格为“需要未声明编码约定的 lemma”。工程侧若没有 slot expansion lemma，cut soundness 入口会卡住。

修复：把 bound/infeasible 改成 group-level demand 版本，或另加明确的 slot expansion theorem。参考 `CutFamilies_statement_fidelity_patches.lean.snippets` 中 F1 段。

### F7 `f7_empty_cover_monotone` — CONCERN

根因：survey 特别强调当前实现必须用 ghost-only mask 排除 `cell_owner` 回溯导致的 false positive：`free = grid-(G∪E∪O∪F)` 空还不够，还要 `free_ghost = grid-(G∪E∪F)` 空。当前 theorem 只有任意 `Free'⊆Free` 的 monotone 空集保持，未把 `Free` 必须是 replay-stable scope 写进名字/陈述，也没有给出“无 cover anchor”的否定存在结论。

最小反例：当前 full free 因某个临时 `cell_owner` blocker 为空，故 `Free.filter CanCover=∅`；但移走 blocker 后 future free 不再是 current full free 的子集，且存在可覆盖 pole anchor。当前 theorem 若被误用在 full free 上，只能证明一个无关的子状态性质，不能支撑 single-literal cut soundness。survey 中 ghost-only empty 正是防这个坑。

影响面：theorem 本身是对的；风险在 docstring/接口过于短，容易把已知 unsound 的 full-mask empty 当成已形式化安全。

修复：加 replay-stable `FreeScope`/`FutureFree` 版本，并将 `FreeScope` 文档钉为 ghost-only mask。参考 patch snippets 的 F7 段。

### F6 `f6_packing_bound` — CONCERN

根因：survey 的“不跨阻挡”语义是：每个合法 1×L pose 整体落入某个 unblocked interval。当前陈述要求外部提供 `bucket : ι→κ`，并在 infeasible theorem 中固定该 bucket。存在性 bucket 与固定 bucket 在数学上可转化，但这是应由 theorem 内部消化的量词，不应变成工程侧额外字段。

最小反例：假设 hypothetical layout 只满足 `∀ i, ∃ j∈J, seg i⊆interval j`。这就是 survey 的 no-crossing 语义；当前 theorem 不能直接套用，必须先构造一个全局 `bucket` 函数。若工程 proof boundary 没有 choice/selection lemma，该前提就是白证接口。

影响面：bound lemma 可救，但当前接口把抽象数学和证书/工程 witness 混在一起，容易让 validator 无法 discharge Lean 前提。

修复：保留 bucketed theorem 为 helper，公开 theorem 改为接受 `∃ bucket, ...` 或 `∀ i, ∃ j, ...`。参考 patch snippets 的 F6 段。

### F6 `f6_packing_overflow_infeasible` — BLOCK

根因：survey 当前实现的 fire 不是“本区域实际有 `S.card` 个 pose 且 `capacity < S.card`”，而是 `C_R < d_R ≤ max(0,D−C_R')`：对侧最多放 `C_R'`，总需求为 `D`，所以本侧至少需要 `d_R`。当前 infeasible theorem 没有把这个下界和本侧 capacity 组合成 cut soundness，只能排除“全部给定 S 都已经在本区域且超过本区 capacity”的直接 overflow。

最小反例：`D=3`，本侧 `C_R=1`，对侧 `C_R'=1`，证书 `d_R=2`。survey fire：`1 < 2 ≤ 3-1`，因此不可行。当前 theorem 若令 `S` 为全部 3 个需求，不能证明 `seg i⊆本侧 interval`；若令 `S` 为本侧实际 placements，则 `S.card=x` 是 hypothetical layout 的未知数，fire `1 < x` 正是需要先从 cross-side 下界推出的结论。当前文件只有分离的 `f6_cross_side_lower_bound`，没有组合 theorem。

影响面：这会让 F6 当前 validator 的核心 amendment（2026-06-04 修的 soundness 缺口）没有被 Lean theorem 覆盖。属于陈述漏掉 soundness 必需前提/量词结构，BLOCK。

修复：加入 `C < d ≤ D-C'` 与 split capacity 的组合 infeasible theorem，并把 packing overflow 的 bucket 改成存在量词。参考 patch snippets 的 F6 段。

### F2 `f2_demand_overflow_infeasible` — CONCERN

根因：survey 的抽象结构是：validator/分离性先证明每条合法 A-B 路必过 δ，然后 demand 超过 `|δ|` 推出不存在 edge-disjoint routing。当前 theorem 的结论是否定 `(hhit ∧ hdisj)`，把 `hhit` 放进“合法路由”一起否掉了。这样即使存在一组完全绕过 δ 的 edge-disjoint routes，theorem 仍然为真，因为它只说明这组 routes 不满足 `hhit`。

最小反例：`δ=∅`，一条 route 的 edges 非空且不在 δ，route family trivially edge-disjoint。`hfire : 0 < 1` 成立。当前 theorem 只推出 `¬(hhit∧hdisj)`，但真正需要的是在 separator 已证 `hhit` 后推出 `¬hdisj`。没有 separator proof 时，route 绕过 δ 不应被该 theorem 说成“不存在合法路由”。

影响面：作为 pigeonhole lemma 没错；作为 cut soundness 入口，docstring “不存在边不相交的合法路由”偏强。若 F2/F4 的 separator lemma 没接上，会产生虚假安全感。

修复：把 `hhit` 移到 theorem 前提，结论只否定 edge-disjoint route family。参考 patch snippets 的 F2 段。

### F3 `f3_pair_literal_cut_sound` — BLOCK

根因：survey 明确说 lifecycle evaluator 使用 group/pose 多重集 subset 语义，slot index 匿名；当前 theorem 用 `Finset` 和 `{A,B}⊆selected`，这会把重复 literal 折叠。docstring 还直接声称“literal 子多重集匹配语义”，与 theorem 实际不符。

最小反例：cut literals 是同一个匿名 literal 的两份 `[A,A]`，需要当前 state 至少选择两份该 pose 才 violated。当前 Finset `{A,A}` 等于 `{A}`，所以只要一份 `A` 就满足 subset。即使当前生产路径常见 blocker 是 distinct literal，这个 theorem 的陈述仍不能证明 lifecycle 的 multiset evaluator。

影响面：literal cut soundness 的形式化会把 evaluator 的 multiplicity 语义抹掉。对 F3/F5/F7 这类 literal family，重复 literal/匿名 slot 是核心抽象边界，不能用 Finset 偷换。

修复：用 `Multiset` selected/cut literals，或显式加 `A≠B` 并把 docstring 降格为 distinct-literal set lemma。survey 要求的是 multiset，参考 patch snippets 的 F3 段。

## 总体裁定

本文件不是“证明错”，而是典型的 statement-interface 风险：F9/F4 的抽象最干净；F1/F2/F7 是可救的桥接/命名风险；F6 和 F3 有 BLOCK，因为它们分别漏掉当前 validator 的关键 fire 结构与 literal multiset 语义。建议先修 F6/F3，再补 F1/F2/F7 的接口定理或 docstring 降级。
