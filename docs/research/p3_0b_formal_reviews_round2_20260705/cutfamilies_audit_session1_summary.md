审完了。结论：**10 条忠实，5 条 CONCERN，2 条 BLOCK**。BLOCK 集中在 **F6 当前 fire 条件没有被组合成定理**、**F3 literal multiset 被 Finset 偷换** 这两处；这两处属于“机器绿了但陈述没接住 validator 命题”的硬风险。

我把完整审计报告和修复 theorem snippet 打成了一个 7z 包，里面包含：

`CutFamilies_statement_fidelity_audit.md`
`CutFamilies_statement_fidelity_patches.lean.snippets`

补丁段均标注为 **未经编译**，因为当前沙盒没有 Lean 工具链，`lean` / `lake` 均不可用。

[下载 7z 审计包](sandbox:/mnt/data/cutfamilies_statement_fidelity_audit.7z)

## 17 条汇总表

|  # | theorem                          | family | 结论      | 核心判断                                                            |     |   |     |    |
| -: | -------------------------------- | ------ | ------- | --------------------------------------------------------------- | --- | - | --- | -- |
|  1 | `f9_area_bound`                  | F9     | 忠实      | 正是 `A∩W ⊆ W\B ⇒                                                 | A∩W | ≤ | W\B | `。 |
|  2 | `f9_overflow_infeasible`         | F9     | 忠实      | 是 F9 bound 的逆否形态。                                               |     |   |     |    |
|  3 | `f1_occupancy_bound`             | F1     | CONCERN | survey 是 group-level `Σ demand·cells`，当前 theorem 只对已展开 slot 求和。 |     |   |     |    |
|  4 | `f1_demand_overflow_infeasible`  | F1     | CONCERN | 同上，缺少 demand-slot expansion 的显式桥。                               |     |   |     |    |
|  5 | `f7_cover_filter_monotone`       | F7     | 忠实      | 纯集合单调性 lemma 忠实。                                                |     |   |     |    |
|  6 | `f7_empty_cover_monotone`        | F7     | CONCERN | 只证明空覆盖单调，没钉住 ghost-only replay scope。                           |     |   |     |    |
|  7 | `f4_closed_set_absorbs_reach`    | F4     | 忠实      | 可达闭包 lemma 忠实。                                                  |     |   |     |    |
|  8 | `f4_unreachable_outside_closed`  | F4     | 忠实      | 封闭集外不可达，忠实。                                                     |     |   |     |    |
|  9 | `f4_subgraph_reach_mono`         | F4     | 忠实      | 子图可达不新增，忠实。                                                     |     |   |     |    |
| 10 | `f6_strip_capacity`              | F6     | 忠实      | 比 contiguous interval 更一般，但不失真。                                 |     |   |     |    |
| 11 | `f6_packing_bound`               | F6     | CONCERN | “不跨阻挡”被写成外部固定 `bucket`，量词偏硬。                                    |     |   |     |    |
| 12 | `f6_packing_overflow_infeasible` | F6     | BLOCK   | 没表达当前实现的 `C_R < d_R ≤ max(0,D−C_R')` fire。                      |     |   |     |    |
| 13 | `f6_cross_side_lower_bound`      | F6     | 忠实      | Nat 截断减法就是 `max(0,D−C')`。                                       |     |   |     |    |
| 14 | `f2_cutset_bound`                | F2     | 忠实      | `hhit + edge-disjoint ⇒ routes ≤ δ` 忠实。                         |     |   |     |    |
| 15 | `f2_demand_overflow_infeasible`  | F2     | CONCERN | 把 separator hit 性质放进被否定的 legal predicate 里。                     |     |   |     |    |
| 16 | `f3_blocked_port_infeasible`     | F3     | 忠实      | all-ports-active、cell_owner blocker 分支忠实。                       |     |   |     |    |
| 17 | `f3_pair_literal_cut_sound`      | F3     | BLOCK   | docstring 声称 multiset，theorem 实际用 Finset，会折叠重复 literal。         |     |   |     |    |

## 非忠实项摘要

### F1 两条：CONCERN

根因：survey proposition 是对 contributor group 求 `Σ demand(g)·cells_per_pose(g)`。当前 theorem 的 `S` 可以被解释成“已经展开的 demand slots”，但这个展开没有写进陈述。

最小反例：一个 group `g`，`demand(g)=2`，`cells_per_pose(g)=1`，`Free.card=1`。survey 会 fire，因为 `1 < 2*1`。当前若自然令 `S={g}`、`cells g=1`，fire 变成 `1 < 1`，推不出不可行。

影响面：证明本身没错，但 theorem 不是直接的 survey 命题。工程侧必须另有 slot expansion lemma，否则 F1 soundness 入口会卡住。

修复补丁：7z 内 patch snippets 的 **F1 repair** 段，把 theorem 改成 group-level `demand * cellsPerPose` 版本。

### F7 `f7_empty_cover_monotone`：CONCERN

根因：survey 强调当前实现要用 ghost-only mask，避免 `cell_owner` 回溯导致 false positive。当前 theorem 只是任意 `Free'⊆Free` 的空覆盖保持，没有把 `Free` 必须是 replay-stable scope 写入陈述。

最小反例：当前 full free 因临时 `cell_owner` blocker 而 empty，但 blocker 被移走后 future free 出现可覆盖 pole anchor。此时 future free 不是 current full free 的子集，单 literal cut 不 sound。survey 的 ghost-only empty 正是防这个坑。

影响面：theorem 是真 lemma，但 docstring/interface 过短，容易把已知 unsound 的 full-mask empty 当成已形式化安全。

修复补丁：7z 内 patch snippets 的 **F7 repair** 段，加入 `FreeScope`/`FutureFree` 和 `F7NoCover` 版本，并要求 `FreeScope` 是 ghost-only scope。

### F6 `f6_packing_bound`：CONCERN

根因：survey 的“不跨阻挡”是每个 pose **存在**某个 unblocked interval 容纳它。当前 theorem 要求外部给固定 `bucket : ι → κ`。数学上可用 choice 转换，但作为 validator-facing theorem，这个 bucket 不应成为额外工程字段。

最小反例：hypothetical legal layout 只给出 `∀ i, ∃ j∈J, seg i⊆interval j`。这是 survey 语义；当前 theorem 不能直接套用，必须先构造全局 bucket。

影响面：bound lemma 可救，但前提接口偏硬，容易形成白证义务。

修复补丁：7z 内 patch snippets 的 **F6 repair** 段，将原 bucket 版降级为 helper，公开 theorem 改为接受 `∃ bucket, ...`。

### F6 `f6_packing_overflow_infeasible`：BLOCK

根因：当前实现的 fire 是 `C_R < d_R ≤ max(0,D−C_R')`。Lean theorem 只证明“若本区域已有 `S.card` 个 pose 且 `capacity < S.card`，则不可能”。它没有组合对侧容量下界，所以没有证明 validator 当前实际 fire 的 soundness。

最小反例：`D=3`，本侧容量 `C_R=1`，对侧容量 `C_R'=1`，证书 `d_R=2`。survey fire：`1 < 2 ≤ 3-1`，不可行。当前 theorem 若令 `S` 为全部 3 个需求，无法证明全都在本侧；若令 `S` 为本侧实际 placements，`S.card=x` 是未知数，恰恰需要 cross-side lower bound 推出来。

影响面：这漏掉了 F6 2026-06-04 amendment 修补的核心 soundness 条件。属于 BLOCK。

修复补丁：7z 内 patch snippets 的 **F6 repair** 段，加入 `f6_cross_side_capacity_overflow_infeasible`，直接表达 `C < d ≤ D-C'` 与 split capacity 的矛盾。

### F2 `f2_demand_overflow_infeasible`：CONCERN

根因：survey 结构是：separator/enclosure 先证明每条合法 A-B 路必过 δ，然后 `demand > |δ|` 推出不存在 edge-disjoint routing。当前 theorem 的结论是否定 `(hhit ∧ hdisj)`，把 `hhit` 放进被否定的“合法性”里了。

最小反例：`δ=∅`，有一条 route 完全绕过 δ，route family edge-disjoint。`hfire : 0 < 1` 成立。当前 theorem 只推出 `¬(hhit∧hdisj)`，这当然真，因为 hhit 假；但它没有排除这条 route。真正 soundness 需要 separator proof 作为前提，再否定 disjoint routes。

影响面：计数 lemma 本身没错，但 infeasible theorem 的 docstring “不存在合法路由”偏强。若 F2/F4 separator lemma 没接上，会产生虚假安全感。

修复补丁：7z 内 patch snippets 的 **F2 repair** 段，把 `hhit` 移到 theorem 前提，结论只否定 edge-disjoint route family。

### F3 `f3_pair_literal_cut_sound`：BLOCK

根因：survey 明确说 lifecycle evaluator 用 group/pose 多重集 subset 语义，slot index 匿名。当前 theorem 用 `Finset` 的 `{A,B}⊆selected`，重复 literal 会被折叠。docstring 还声称“literal 子多重集匹配语义”，这是注释与定理实际不符。

最小反例：cut literals 是 `[A,A]`，需要 state 至少选择两份 `A` 才 violated。当前 Finset `{A,A}` 等于 `{A}`，一份 `A` 就满足 subset。这个 theorem 不能证明 lifecycle 的 multiset evaluator。

影响面：literal family 的 multiplicity 语义被抹掉。F3/F5/F7 这类 literal cut 都不能用 Finset 偷换 multiset。

修复补丁：7z 内 patch snippets 的 **F3 repair** 段，给出 `Multiset` 版 `PortExposureFreeMS` 与 `f3_pair_literal_cut_sound`。
