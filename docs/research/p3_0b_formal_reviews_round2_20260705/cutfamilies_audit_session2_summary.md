审完了。结论是：**8 条忠实，7 条 CONCERN，2 条 BLOCK**。主要问题不是证明错，而是若干定理把“工程侧必须证明的绑定/分离/作用域条件”压缩成了太光滑的抽象前提，像把一条带钩子的绳子画成了直线。

我把完整审计报告和参考补丁打成了一个 7z 包：
[下载 CutFamilies_statement_audit_bundle.7z](sandbox:/mnt/data/CutFamilies_statement_audit_bundle.7z)

包内包含：

`CutFamilies_statement_audit_report.md`：完整表格、根因、最小反例、影响面。
`CutFamilies_statement_patches_uncompiled.lean`：每个 BLOCK/CONCERN 的 Lean 4 参考替换段。

补丁状态：**未经编译**。沙盒里没有 `lean` / `lake` 可执行文件；我只能做 Lean 4/mathlib 语法形态的参考补丁，不能本地跑内核。

### 17 条逐条裁定

|  # | theorem                          | 裁定        |
| -: | -------------------------------- | --------- |
|  1 | `f9_area_bound`                  | 忠实        |
|  2 | `f9_overflow_infeasible`         | 忠实        |
|  3 | `f1_occupancy_bound`             | CONCERN   |
|  4 | `f1_demand_overflow_infeasible`  | CONCERN   |
|  5 | `f7_cover_filter_monotone`       | CONCERN   |
|  6 | `f7_empty_cover_monotone`        | CONCERN   |
|  7 | `f4_closed_set_absorbs_reach`    | 忠实        |
|  8 | `f4_unreachable_outside_closed`  | 忠实        |
|  9 | `f4_subgraph_reach_mono`         | 忠实        |
| 10 | `f6_strip_capacity`              | 忠实        |
| 11 | `f6_packing_bound`               | CONCERN   |
| 12 | `f6_packing_overflow_infeasible` | CONCERN   |
| 13 | `f6_cross_side_lower_bound`      | 忠实        |
| 14 | `f2_cutset_bound`                | CONCERN   |
| 15 | `f2_demand_overflow_infeasible`  | **BLOCK** |
| 16 | `f3_blocked_port_infeasible`     | 忠实        |
| 17 | `f3_pair_literal_cut_sound`      | **BLOCK** |

### BLOCK 1：`f2_demand_overflow_infeasible`

根因：定理结论是 `¬ (每条路线命中 δ ∧ 路线边不相交)`，但 docstring 声称“需求路线数超过割边数 ⇒ 不存在边不相交的合法路由”。这两者不等价。survey 里的“每条合法 A-B 路必过割”来自 A/B partition、patch enclosure、commodity 两侧性这些图分离条件；Lean 定理没有形式化这些条件，只把命中割边作为被否定的 conjunct。

最小反例：令 `routes = {r}`，`δ = ∅`，`edges r = {e}`。有 `δ.card < routes.card`。如果某个图里 `e` 本来就是一条合法 source-sink route，但它不穿过这个伪造的空 `δ`，那么合法 edge-disjoint routing 存在。Lean 定理只能推出“不满足 hhit”，不是“不存在合法路由”。

影响面：这是 statement-fidelity block。工程侧若把这个 theorem 当 F2 cut soundness，就会把“分离性已证明”的义务悄悄吞掉，形成白证风险。

参考补丁：包内 `f2_cutset_infeasible_from_separator`。补丁把真实图路由谓词抽成 `Legal`，并显式要求 validator 的 A/B 分割和 enclosure 证明 `hseparator : Legal edges → 每条 legal route 命中 δ`。这样 overflow 才推出 `∀ edges, ¬ Legal edges`。

### BLOCK 2：`f3_pair_literal_cut_sound`

根因：docstring 声称这是 “literal 子多重集匹配语义”的数学核，但 theorem 使用 `selected : Finset ι` 和 `{A, B} ⊆ selected`。`Finset` 会折叠重复 literal；survey/lifecycle 明确是匿名 slot 的 literal **multiset** subset 语义。

最小反例：cut literal multiset 为 `[l, l]` 时，真实 evaluator 应要求当前 selected multiset 至少有两个 `l`。但在 `Finset` 中 `{l, l} = {l}`，一个 `l` 就满足子集条件。也就是说，定理形式化的是 set-nogood，不是 survey 说的 multiset-nogood。

影响面：如果重复 `(group, pose)` literal 能通过不同 slot 出现，这会直接证明一个更强、也更危险的 cut body。即便当前 F3 通常生成 distinct A/B，这个 docstring 仍然过度声称，后续扩展会踩雷。

参考补丁：包内 `PortExposureFreeMulti` 和 `f3_pair_literal_cut_sound_multi`。补丁把 selected 改成 `Multiset ι`，并用 `([A, B] : List ι).toMultiset ≤ selected` 保留 multiplicity。

### CONCERN：F1 两条

受影响：`f1_occupancy_bound`、`f1_demand_overflow_infeasible`。

根因：survey proposition 是 group-demand 形态：`Σ demand(g) * cells_per_pose(g) > cap_R`。Lean statement 已经把它压成了 instance-indexed `S` 和 `cells : ι → ℕ`。这可以作为内部引理，但 theorem/docstring 没把“`S` 确实展开了所有 demanded instances”这个绑定义务暴露出来。

最小反例：一个 group `g`，`demand(g)=2`，`cells_per_pose(g)=3`，`Free.card=5`。survey 触发，因为 `6 > 5`。如果工程绑定错误地把 `S` 实例化成一个 instance，Lean 只看到 `3 ≤ 5`，没有矛盾。 theorem 本身没错，错在它没有把 demand 展开义务放到陈述里。

影响面：若 group-to-instance expansion 或 demand lower-bound binding 漏了，机器会证明一个过小需求版本。

参考补丁：包内 `f1_region_capacity_bound` 和 `f1_region_capacity_overflow_infeasible`。补丁新增 `requiredCells` 以及 `hdemand : requiredCells ≤ ∑ i∈S, cells i`，其中 `requiredCells` 对应 survey 的 `Σ demand·cells_per_pose`。

### CONCERN：F7 两条

受影响：`f7_cover_filter_monotone`、`f7_empty_cover_monotone`。

根因：Lean 定理只是 `Free.filter CanCover` 的集合单调性，其中 `CanCover` 与 `Free` 无关。survey 的当前实现更具体：pole anchor 的 2×2 footprint 必须完全落在 free cells 中，而且 single-literal soundness 需要 owner-insensitive 的 ghost/exterior scope empty-cover，而不只是当前 full-free empty-cover。

最小反例：当前 `cell_owner` 把所有 pole anchor 挤掉，所以 full-free cover set 为空；但如果该 owner 被回溯移走，某个 pole anchor 又可用了。survey 说这正是为什么还要检查 ghost-only cover set 为空。Lean 定理只有在 replay free set 是旧 `Free` 的子集时才可用，却没有告诉工程侧这个稳定的 `Free` 必须是 ghost scope，而不是 current full-free scope。

影响面：作为“小单调性骨架”可以，但作为 F7 当前 cut soundness 的陈述边界太薄。错误实例化会把 cell_owner-caused empty-cover 当成 ghost-scope empty-cover。

参考补丁：包内 `F7CoverSet`、`f7_cover_set_monotone_with_footprint`、`f7_empty_cover_ghost_scope`。补丁把 footprint subset-free 条件和 ghost-scope replay 条件放进 theorem。

### CONCERN：F6 两条

受影响：`f6_packing_bound`、`f6_packing_overflow_infeasible`。

`f6_packing_bound` 的问题是 `bucket : ι → κ` 被直接作为前提。survey 的自然语言是“pose 不跨阻挡，所以整体落入某个 maximal unblocked interval”。Lean 现在跳过了“从不跨阻挡/partition 几何推出存在 bucket”的证明义务。

最小反例：两个 interval `{a}` 和 `{b}`，`L=2`，抽象 segment `{a,b}` 有两个 free cells，但不属于任何单个 interval。当前 theorem 通过没有 bucket 把它排除；这没错，但说明几何层必须证明这种 segment 非法，而 theorem 没把该义务显式化。

影响面：如果 validator 没证明 interval membership，只把 bucket 当作黑箱，F6 bound 会变成白证。

参考补丁：包内 `f6_packing_bound_exists_bucket`，把预选 total function 改为 `∀ i∈S, ∃ j∈J, seg i ⊆ interval j`。

`f6_packing_overflow_infeasible` 的问题是没有组合当前 validator 的真实 fire 形态：`C_R < d_R ≤ max(0, D−C_R')`。Lean 有直接 side-capacity overflow，也有 `f6_cross_side_lower_bound`，但没有把 certified `d_R` 合成到 infeasible theorem。

最小反例：`D=10`，对侧容量 `C'=6`，证书下界 `d_R=4`，本侧容量 `C_R=3`。survey 从 `3 < 4 ≤ 10−6` 触发。现有 theorem 需要 `3 < S.card`，也就是实际本侧放了几个；这个量正是要由 cross-side 下界推出，而不是证书直接给出。

影响面：不 unsound，但它没有陈述 validator 当前真正检查的命题，集成证明容易漏掉组合步骤。

参考补丁：包内 `f6_region_demand_overflow_infeasible`，把 side capacity、`dR`、`D−Cother` 下界一次性合成。

### CONCERN：`f2_cutset_bound`

根因：这是正确的鸽笼计数引理：每条 route 命中 δ，且 route 间 edge-disjoint，则 route 数不超过 `|δ|`。但 survey proposition 的重点还包括 A/B 分割、patch 无 escape、commodity 两侧性，这些图事实用来推出“每条合法 route 命中 δ”。Lean 定理只保留了结果前提 `hhit`。

最小反例：`δ = ∅`，存在一条合法 route 走 δ 外的边。计数 lemma 没错，因为 hhit 不成立；但它不是 graph cutset proposition 本身。

影响面：作为 helper 忠实，作为 F2 soundness statement 不够。需要在 theorem 名称/docstring 里承认它只是 hit-cut counting lemma，或者加 wrapper theorem 要求 separator lemma。

参考补丁：同 BLOCK 1，使用 `f2_cutset_infeasible_from_separator`。

### 明确未标的问题

F9 我没有标。`A ∩ W ⊆ W \ B` 正是面积不等式需要的 set-level well-formed consequence。survey 提到的 “cell_owner 不含 ghost/exterior、每 cell 至多一 owner” 比这个定理实际需要更强；“每 cell 至多一 owner”在这里已经被 `A` 是 group-owned cell set 吸收了，不参与 card bound。

F4 三条没有标。它们分别覆盖 closed reachable set、outside closed unreachable、subgraph reach monotonicity；70×70、free-cell、commodity registry 是工程绑定层，抽象边界合理。

`f6_cross_side_lower_bound` 没标。Lean 的 Nat 截断减法 `D - C'` 正是 report 的 `max(0, D−C')`。

`f3_blocked_port_infeasible` 没标。它忠实捕捉当前实现的 `cell_owner` blocker 分支；all-ports-active 通过 `ports A` 全量化显式进入，`frontCell` 抽象为工程侧方向原语义务。
