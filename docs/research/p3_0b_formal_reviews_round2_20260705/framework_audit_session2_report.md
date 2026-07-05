# FrameworkLemmas 陈述保真对抗审报告

审计对象：`FrameworkLemmas.lean` 中 9 条 theorem 及相关 docstring/module header。

本报告按“前提过强 = 白证、前提缺失 = 虚假安全感、证了相邻命题 = 走样”的标准审查。补丁片段见同包内 `FrameworkLemmas.fidelity_patch_snippets.lean`。由于沙盒没有 lean/lake，补丁状态均为“未经编译”。

## 总结判定表

| # | theorem | 判定 | 根因一句话 | 最小反例/边界 | 影响面 |
|---|---|---|---|---|---|
| 1 | `f5_compound_safety` | BLOCK | 设计稿说“G-等价类代表选择 × G-不变 cut 删整类”，定理只要求裸关系、P-HOM、逐点 cut sound，完全不表达 cut 删整类 | 三元素模型：可行单例类 `{a}`，不可行类 `{b,c}`，`Cut b` 但不 `Cut c`。现定理可通过，却违反“轨道 cut 删整类” | 可让非 G-不变 cut 通过框架审计，只要它在当前抽象里逐点 sound；模块头“轨道 cut 删整类”被白证 |
| 2 | `f5_compound_needs_phom` | BLOCK | 原文红测是“非 G-不变、读 slot 身份的 cut”，现反例是“可行性读标签、Cut 全真且 G-不变”，证了相邻陷阱 | 现构造 `Cut := True`，不是 label-sensitive cut；且 `Cut true` 与 `Feasible true` 同时成立，保留不了主安全定理的 cut sound 前提 | 红测不能覆盖设计稿点名事故，未来 slot-sensitive cut 仍可能漏审 |
| 3 | `frontier_prune_dominates` | CONCERN | 严格幸存谓词 `<` 与“≤ 被剪”边界正确，但没有 `Feasible/CERTIFIED` 和“同一谓词”绑定 | 旧谓词下 A=100 certified 支配 B=90；新谓词下 A 失败、B 可行。当前 statement 无法表达这个迁移禁令 | 可作为纯 value dominance 小引理，但不能单独支撑 frontier skip soundness |
| 4 | `frontier_prune_preserves_max` | BLOCK | `sup'` 保的是全候选 raw value，不是“固定谓词下 certified 可行解的最优值”，且不产出 argmax witness | `F={A,B}`，A 旧 certified value=100，B value=90；收紧谓词后 A 不可行、B 可行。继承旧 skip 会丢新最优。另有等值 tie 时保值会丢一个 argmax witness | “剪枝不改变搜索问题答案”过宽；会被误用到谓词迁移、schema 升级或需要 witness 的路径 |
| 5 | `frontier_prune_preserves_max_lex` | BLOCK | 只是 #4 的 `toLex(area,minSide)` 特例；lex 顺序本身正确，但继承了 #4 的缺口 | 同 #4；`toLex (100,0)` 支配 `toLex (90,0)` 的旧 skip 不能迁移到新谓词 | max_lex 目标形式化对，frontier sound 声称不够 |
| 6 | `eq_key_violated_iff` | 忠实 | 带 `S ⊆ U` 与 `A ⊆ U` 时，PB 等式键违反条件确实等价于 `A = S` | 若去掉 `A ⊆ U`，只能得到 `A ∩ U = S`，不是裸 `A = S` | 当前 theorem 安全；建议补一个投影边界 lemma 防误用 |
| 7 | `tp7s_eq_key_sound` | 忠实 | 量化 `∀ A ⊆ U`，正好对应 Finset 表示下的完整 0/1 赋值空间；Farkas 证据抽象为 `¬ Feasible S` | `A⊆U` 是关键护栏，已在 statement 中 | 可支撑“等式键只禁固定赋值 S”的 sound 性，前提是 `U` 已含 graph syntax version 等全部键字段 |
| 8 | `tp7s_eq_key_no_overcut` | CONCERN | theorem 有 `A ⊆ U`，数学上安全；docstring “真超集不触发”等自然语言少了“U 内”限定 | `U={false}, S={false}, A={false,true}`：`S ⊂ A` 且 `EqKeyViolated U S A` 成立，因为 `true` 在 U 外被 key 忽略 | 未来若把全局 Finset 超集当成 U 内赋值超集，会误报“不过切” |
| 9 | `tp7s_selected_set_nogood_overcuts` | CONCERN | 抽象形状对，但没有形式化 TP7-S 半容量路、并行路、selected-set nogood 违反谓词；docstring “机器版”略过强 | 现证据只是 `Feasible X := 2 ≤ X.card`，`S={false}`，`A={false,true}` | 足以证明“存在超集可行，selected-set nogood 会过切”的集合论边界；不足以声称已机器化原文吞吐玩具结构 |

## 逐条说明

### 1. `f5_compound_safety`: BLOCK

原文要素有三个：G-等价类、代表元选择、G-不变 cut 删整类。现 theorem 的 `equiv` 是任意二元关系，没有 `Equivalence equiv`；`hSel` 只是每个点能找一个 `equiv` 后继被 `Sel` 保留；cut 只由 `hcut_sound : ∀ s, Cut s → ¬ Feasible s` 约束。证明也没有使用任何 cut invariant。

这不是单纯“发现了更弱前提”。它使模块头和 docstring 中“轨道 cut 删整类”的审计声称失真。一个模型可以满足当前 theorem，同时违反设计稿的 cut 形态：设等价类 `{a}` 可行，等价类 `{b,c}` 不可行，selector 保留每类代表，cut 只删 `b` 不删 `c`。逐点 sound 成立，主定理仍可证，但 cut 明显不是删整类。

建议补丁：把 `Equivalence equiv`、`hCutInv : equiv s t → (Cut s ↔ Cut t)` 放入 theorem，并把结论加强为存在代表 `r`，`r` 可行且其整个等价类均未 cut。见补丁文件 `CompoundSafetyPatch/f5_compound_safety`。

### 2. `f5_compound_needs_phom`: BLOCK

docstring 声称它是设计稿点名的“标签敏感 cut + 序 = 删光合法类”。实际构造是：`Feasible s := s = true`，`Sel s := s = true`，`Cut _ := True`。这不是非 G-不变 cut；相反它是全关系下最 G-不变的 cut。陷阱根因变成了“没有 P-HOM 时从一个不可行标签过度 lift 到整个轨道”，不是原文“非 G-不变、读 slot 身份”的事故。

更要命的是，它也没有保留主安全 theorem 的 `hcut_sound`：`true` 可行但被 cut。因此“其余前提全保留”的 docstring 是假的。

建议补丁：替换为 `f5_compound_non_invariant_cut_overcuts`：`equiv` 为全关系，`Feasible := True` 保持 P-HOM，selector 只保留 `true`，cut 也只删 `true`，于是 cut 非 G-不变，原问题有可行解但剪后无可行代表。见补丁文件。

### 3. `frontier_prune_dominates`: CONCERN

边界 `<` 是对的：幸存者是严格优于 incumbent 的候选，等值和更差候选由 `w₀` 支配，正好对应“lex 不优于 witness 的候选被跳过”。

问题是 theorem 没有建模 witness 的 certified 可行性，也没有把 dominance 绑定到同一个谓词/schema。作为纯序引理可接受；作为 “frontier 剪枝 sound” 的一环则欠前提。迁移规则原文明确禁止继承依赖旧 incumbent 的 skip，当前 statement/docstring 没有把这条护栏写进类型。

建议补丁：给 theorem 加 `Feasible : ι → Prop` 与 `hfw₀ : Feasible w₀`，只对 `Feasible c` 的候选给出可行支配者。见补丁文件 `FrontierPrunePatch/frontier_prune_dominates`。

### 4. `frontier_prune_preserves_max`: BLOCK

这个 theorem 保的是 `F.sup' value`，也就是全候选 raw value。设计稿的“搜索问题答案”是 certified feasible layout 的 max_lex，不是任意候选的 raw 最大值。若 `F` 中有高 value 但不可行的候选，当前 theorem 保留的值不是搜索答案。若谓词收紧，旧 incumbent 可能失效，继承旧 skip 会丢新最优，这正是设计稿 §2.5 的反例。

它还只保 value，不保 witness。对只需返回任一最优解的搜索来说，等值候选被剪通常没问题，因为 `w₀` 留下；但 docstring “搜索问题答案”若被理解为 argmax witness 或 terminal evidence，则 theorem 不足。

建议补丁：替换为 `frontier_prune_preserves_max` 的可行版本，比较 `(F.filter Feasible).sup'` 与剪后可行幸存集的 `sup'`；另加 `frontier_prune_preserves_argmax_witness` 证明至少存在一个剪后可行 argmax witness。见补丁文件。

### 5. `frontier_prune_preserves_max_lex`: BLOCK

`toLex (area,minSide)` 的方向与设计稿一致：面积优先，面积相等时最短边更大者胜。问题完全继承自 #4：它没有 `Feasible`/`CERTIFIED`/同谓词条件，只是 raw max 的 lex 特例。

建议补丁：给 lex theorem 加 `Feasible` 和 `hfw₀`，调用可行版本的 `frontier_prune_preserves_max`。见补丁文件。

### 6. `eq_key_violated_iff`: 忠实

在 theorem 自带的 `hSU : S ⊆ U` 与 `hAU : A ⊆ U` 下，`EqKeyViolated U S A` 等价于 PB key 左侧全为 0：所有 `S1` 变量为 1，所有 `S0=U\S` 变量为 0。Finset 表示中 `A` 是置 1 的变量集合，因此完整赋值空间就是 `A ⊆ U`。结论 `A = S` 忠实。

建议补强而非修正：加一个投影边界 lemma，说明若允许 `A` 含 U 外变量，只能推出 `U ∩ A = S`。见补丁文件 `eq_key_violated_iff_inter`。

### 7. `tp7s_eq_key_sound`: 忠实

该 theorem 量化 `∀ A ⊆ U`，没有遗漏 `A⊆U`。在 `eq_key_violated_iff` 的护栏下，等式键排除的所有赋值都等于 `S`，所以 `¬ Feasible S` 足以推出 `¬ Feasible A`。这正是“Farkas 只证明固定图 S 不可行，因此 equality key 只禁 S”的抽象。

唯一需要实现层保证的是：`U` 必须真是设计稿里的完整键全集，包含 binding choice、generic slot assignment、route use-vars 全集和 graph syntax version。这个保证不在 theorem 内，但属于调用方建模义务。

### 8. `tp7s_eq_key_no_overcut`: CONCERN

statement 有 `hAU : A ⊆ U`，所以数学结论安全。但 docstring 写“真超集不触发等式键”，缺少“U 内真超集”限定。若未来有人把它当作裸 Finset 超集定理，结论是假的。

最小边界例：`U={false}`，`S={false}`，`A={false,true}`。此时 `S ⊂ A`，但 `EqKeyViolated U S A` 成立，因为 `true` 不在 U 内，PB key 根本不看它。

建议补丁：docstring 改成“U 内真超集”；补红测 `tp7s_eq_key_no_overcut_needs_assignment_subset` 明确说明 `A⊆U` 不能删。见补丁文件。

### 9. `tp7s_selected_set_nogood_overcuts`: CONCERN

它正确证明了一个集合论边界：存在 `S ⊆ A`，`S` 不可行但 `A` 可行，所以 selected-set nogood 会过切。这个抽象足以支持“只禁选中集不 sound”的大方向。

但 docstring 说是“一条半容量路不够、加一条并行路就够”的机器版，当前 theorem 没有 TP7-S 结构、容量、路径、Farkas、也没有显式 selected-set nogood 违反谓词。`Feasible X := 2 ≤ X.card` 只能算形状相似的容量抽象。

建议补丁：至少显式加入 `SelectedSetNogoodViolated S A := S ⊆ A`、`S ⊂ A`、`A ⊆ U`，并把 docstring 降格为“抽象玩具版”。若要声称忠实机器化原文 toy，还需要定义两个 route 变量、需求 2、每条路容量 1 的 TP7-S 小模型。见补丁文件。

## 横切 docstring/module header 问题

1. 模块头对 F5 的描述写“序保代表元 × 轨道 cut 删整类”，但主 theorem 没有 `hCutInv`。这是 #1 的 BLOCK。
2. 模块头说 F5 反例是“v1 点名的反方向陷阱”，实际 theorem 是 P-HOM 破缺且 G-不变 cut。该 header 与 theorem 一起 BLOCK。
3. frontier header 说“已有 in-hand witness 时剪掉 lex 不优于它的候选不损失最优值”，没有写“witness 必须在同一谓词/schema 下 certified”。这与迁移规则相冲突。
4. TP7-S header 的“完整 0/1 等式键排除集恰为 {S}”需要读作“在 `A⊆U` 的完整赋值空间内”。theorem 做到了，header/docstring 建议补这句话。

## 设计稿原文歧义

1. frontier 的 `F` 到底是“所有候选”还是“固定谓词下已知可行候选集”，节选没有给形式化约定。如果项目内部约定 `F` 已经只含 fixed-P feasible candidates，则 #4/#5 可从 BLOCK 降为 CONCERN；但当前 theorem/docstring 写“全候选集”，所以本报告按 BLOCK 处理。
2. “最优解 witness 也不能丢”有两种读法：若只需返回任一最优 witness，等值候选被剪不一定 unsound；若 terminal evidence、可复现 seal 或枚举所有 optima 需要特定 witness，则现 theorem 明显不足。补丁给了存在性 argmax witness，而非保留所有 argmax。
3. TP7-S 半容量路 toy 的具体网络结构未在节选中形式化。现 theorem 可判为抽象过切证据，但无法判为忠实机器化吞吐 toy。
