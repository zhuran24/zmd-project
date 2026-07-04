# ZMD 两份设计稿承重定理的 Lean 4 形式化陈述说明

交付文件：`ZmdDesignStatements.lean`。

说明：当前沙盒内没有 `lean` / `lake` 可执行文件，因此我没有声称本地编译通过；文件按 Lean 4 + mathlib 写成，定理主体按需求主要使用 `by sorry`，其中“presence 去重会把 cut 变强”的 toy 反例给了具体构造与 `native_decide` 风格证明。

## 1. 抽象选择

### Terminal no-solution 设计稿

我把候选尺寸抽象为 `Dim := Nat × Nat`，并定义了有方向的逐维序 `Dim.le`。这保留了设计稿 §2.2 的 oriented 纪律：`6x7` 与 `7x6` 不会被 canonicalize 成同一个键，也不会用面积或集合支配替代逐维支配。

候选域抽象为 `Finset Dim`。这样“极小元集合覆盖一般域”的有限性是 Lean 类型层面的，不需要额外假设无限下降不可能。工程里的 authoritative domain、schema、digest、sink projection、negative reverification 都没有展开成 JSON 字段；它们在数学定理里被压缩为语义假设：

- `DimwiseAntitoneInfeasible D Feasible`：设计稿 §2.1 的逐维反单调引理；
- `InfeasibleOn Feasible C`：覆盖集中每个候选已经被 replay-verified INFEASIBLE；
- `CoversDimwise D C`：覆盖集按 oriented dimwise-ge 覆盖全域；
- `CoverCertificate` 额外带 `D.Nonempty`，对应设计稿 §2.3 “空域拒绝”的合同选择。

一般域的核心定理是 `dimwise_antitone_minimal_antichain_soundness`。它不硬编码 `(6,6)`，而是通过 `MinimalDims D` 表示真实极小反链。标准域坍缩写成两个层次：`domain_with_bottom_minimalDims_singleton` 抽象说明只要 `(6,6)` 是域内 bottom 且所有候选都在其右上方，极小元就是单点；`standard_domain_minimalDims_singleton` 和 `standard_domain_single_point_collapse_soundness` 是矩形标准域 `[6,maxW] × [6,maxH]` 的直接版本。

### F5 orbit lifting 设计稿

我把带标签布局抽象为有限集合：

```lean
NamedAtom GroupId Slot Pose := Σ g, Slot g × Pose g
Layout GroupId Slot Pose := Finset (NamedAtom GroupId Slot Pose)
```

这里 `GroupId` 是组，`Slot g` 是该组实例/匿名 slot，`Pose g` 是该组 pose。组内置换群写成乘积形态：

```lean
SlotPerm GroupId Slot := (g : GroupId) → Equiv.Perm (Slot g)
```

P-HOM 被抽成 `P_HOM Feasible`：对所有组内置换，`Feasible (permuteLayout σ A) ↔ Feasible A`。设计稿 §2.2 还要求目标值相同，所以文件里也给了 `P_HOM_with_objective`，但 nogood soundness 实际只需要 feasibility invariant。

oracle 的 “liftable reject” 被定义为：

```lean
LiftableReject Feasible P := ∀ A, Feasible A → P ⊆ A → False
```

也就是设计稿 §2.3 第 3 个前提的数学核心：“任何完整解，只要扩展该 named core，就不可行”。`immutable_scope` 的白/黑名单没有在 Lean 中建模为 digest 或 parser，而是作为这个语义前提成立的工程条件。

匿名语义用了真正带重数的 multiset：

```lean
anonMultiset A : Multiset (Σ g, Pose g)
AnonMultisetExtends P A := ∀ x, count x (anon P) ≤ count x (anon A)
```

这让“两个相同 `(group,pose)` 的 pattern”仍然能表达成 count ≥ 2。对应定理 `anon_multiset_lift_soundness_from_named_representative` 明确列出从单个 named representative 推到匿名 multiset nogood 所需前提：P-HOM、liftable reject、feasible layout 与代表 pattern 都没有重复 `(group,slot)`，以及每组有限部分单射能延拓成完整组内置换。

部分单射延拓被单独抽成：

```lean
PartialSlotPermExtends Slot
```

并给出 `partialSlotPermExtends_of_fintype` 作为有限 slot 池推出该原则的定理陈述。换句话说，有限性只用于把“layout 中承载 pattern 多重集的那些 slot”到“代表 pattern 指名 slot”的有限一一对应补全为 `S_{n_g}` 中的全排列；P-HOM 和 liftable reject 本身不需要枚举有限性。

boolean master presence 另写为 `presenceSet` / `BooleanPresenceExtends`。它不是 multiset，故需要额外条件：`NoPresenceKeyAlias presenceKey P` 和 `PresenceKeyFaithfulForPattern presenceKey Feasible P`。前者覆盖 cert 内重复 projected key，包括 `(group,pose)` 重复和 attach-key alias；后者覆盖运行时 feasible layout 中“某个 atom 的 key 与 pattern key 相等但真实 `(group,pose)` 不同”的 alias 漏洞。

## 2. 文件中主要 theorem 对照

- TNS §2.1–§2.2：`dimwise_antitone_cover_soundness`，`dimwise_antitone_cover_certificate_soundness`。
- TNS §2.2 一般域极小反链：`minimalDims_cover`，`minimalDims_antichain`，`dimwise_antitone_minimal_antichain_soundness`。
- TNS §2.2 标准域 `(6,6)` 坍缩：`domain_with_bottom_minimalDims_singleton`，`standard_domain_minimalDims_singleton`，`standard_domain_single_point_collapse_soundness`。
- F5 §2.3 具名 slot 轨道提升：`named_orbit_lift_soundness`。
- F5 §2.3 匿名 multiset 语义：`anonMultisetExtends_gives_matching`，`matching_extends_to_group_permutation`，`anon_multiset_lift_soundness_from_named_representative`。
- F5 §2.3 boolean presence attach 的安全版本：`boolean_presence_refines_multiset`，`boolean_presence_lift_soundness_from_named_representative`。
- F5 BLOCK-2 反例：`NoRepeatCounterexample.presence_dedup_strengthens_cut_counterexample`。

## 3. 我认为设计稿定理陈述仍有歧义或需补严的地方

1. **“标准域”缺少纯数学定义。** 设计稿写了 authoritative full domain、min_side、safe area_upper_bound、start_area/aspect 为空，但定理层最好加一句：标准域满足 `(6,6) ∈ D` 且 `∀ (w,h)∈D, 6≤w ∧ 6≤h`。若实现要用矩形盒，则直接写 `D = { (w,h) | 6≤w≤Wmax ∧ 6≤h≤Hmax }`。否则“标准域单点坍缩”的真正原因是 `(6,6)` 是 bottom，而不是候选生成器的其他字段。

2. **“极小元反链”依赖有限候选域。** 当前设计默认 `generate_candidate_sizes` 产有限域，但定理句子最好显式写“finite candidate domain”。如果未来 lazy/infinite domain 出现，就需要 well-foundedness 或可计算覆盖见证，不能直接沿用 `MinimalDims`。

3. **P-HOM 的目标值不影响 nogood soundness。** 设计稿 §2.2 同时说谓词满足性等价、目标值相同。若 F5 cut 只删除不可行 whole-layout，定理只需要 feasibility invariant；若未来把 orbit lifting 用到 objective pruning，应单独声明 objective invariance 被使用在哪里。

4. **liftable reject 应写成语义量词，而不是 oracle 标签。** 建议把“oracle 的 INFEASIBLE 必须证明……”改成精确定义：`LiftableReject(core, scope) := ∀ complete layout A, Extends(A, core) → ¬ Feasible_scope(A)`。随后再说 `query_liftable` 只能在 immutable_scope 白名单内产生这个语义命题的证据。这样能避免把 `INFEASIBLE` 字符串误当 theorem。

5. **“禁止重复 `(group,pose)`”应以 attach presence key 为准。** v3 已补充 alias 禁令，但定理句子仍容易被读成只检查 pose_id。建议把承重前提改成：“cert 内 `presenceKey(group, pose)` 两两不同；且若两个 pose_id 解析到同一 attach presence key，validator fail-closed”。Lean 文件里用 `NoPresenceKeyAlias presenceKey P` 表示这个更强前提。

6. **匿名 multiset 与 boolean presence 应分开命名。** 设计稿同时讨论 “pose 多重集” 和 master boolean presence。建议固定术语：`AnonMultisetExtends` 表示 count-aware inclusion；`BooleanPresenceExtends` 表示去重 set inclusion。所有从前者降到后者的地方必须引用 no-alias/no-repeat theorem。

7. **从 multiset containment 到 named representative 需要写出 matching。** 证明中“取 A 中承载 `[π₀]` 的 slot 集 `T_g`”这一步应补一句：multiset count containment gives an injective occurrence matching from pattern occurrences to selected layout atoms with the same `(group,pose)`。否则在重复 pose 或 alias 场景里读者容易把 set containment 偷换进来。

8. **部分单射补全为群置换需要单独 lemma。** 设计稿说明了“先定义 `T_g` 上的双射，再任意补全”，建议把前提写成：每个 `Slot g` 是有限类型，且 source/target partial maps are injective over the same finite index set。有限性只用于补全为 `Equiv.Perm (Slot g)`。

9. **Feasible layout 的 well-formedness 应是 theorem 前提或定义的一部分。** Lean 陈述要求 `Feasible A → NoDuplicateNamedSlots A`。如果“完整解”在项目中天然保证每个 slot 至多一个 pose，设计稿可以直接写入 complete layout 的定义；如果不是，轨道提升 proof 的 source-slot injection 会有洞。

10. **canonical_relabel 的 theorem 边界需要一句话。** 设计稿要求非规范 cert 直接拒绝，不允许重标后继续。定理层最好说所有 theorem 的 `P` 都是已经 canonical_relabel 且复验后的代表；canonicalization 不是 theorem 内部的 rewrite step，更不是 silent dedup。

11. **TNS 空域：数学真与合同真不同。** `∀ x∈∅, ¬Feasible x` 是真，但设计稿拒绝 empty-domain no-solution certificate。建议在合同定义中显式写 `valid_certificate := D.Nonempty ∧ ...`，并在验证器错误码上保持“domain empty is schema/contract rejection, not mathematical contradiction”。

12. **routing/ghost inventory 属于反单调前提，不是定理结论。** 设计稿已经强调 inventory digest，但定理句子里建议把“逐谓词 ghost-use inventory validates monotonicity hypothesis”与“monotonicity implies cover soundness”分开，避免读者以为 Lean 里的 `DimwiseAntitoneInfeasible` 自动证明了工程源码的 ghost 独立性。
