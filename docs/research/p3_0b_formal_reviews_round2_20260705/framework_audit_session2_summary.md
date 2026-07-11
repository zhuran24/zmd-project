审完了。结论偏硬：**4 个 BLOCK，3 个 CONCERN，2 个忠实**。我把完整报告和 Lean 补丁片段打进了一个 7z 包，补丁均标注为**未经编译**，因为当前沙盒没有 `lean/lake` 环境。

下载包： frameworklemmas_fidelity_audit_bundle.7z（原会话沙盒附件未随仓库快照归档）

包内有：

`adversarial_fidelity_audit_report.md`：完整审计报告
`FrameworkLemmas.fidelity_patch_snippets.lean`：可参考的 Lean 4 替换段和补强定理片段

## 汇总表

| # | theorem                             | 判定          | 根因                                                                                      | 最小反例 / 边界                                                                                               | 影响面                                                                      |
| - | ----------------------------------- | ----------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 1 | `f5_compound_safety`                | **BLOCK**   | 设计稿说“G-等价类代表选择 × G-不变 cut 删整类”，但 theorem 只要求裸二元关系、P-HOM、逐点 `Cut → ¬Feasible`，没有表达“删整类”。 | 三元素模型：可行单例类 `{a}`，不可行类 `{b,c}`，`Cut b` 但不 `Cut c`。当前 theorem 仍可通过，因为 cut 逐点 sound，但它不是轨道 cut。           | 会让“非 G-不变 cut”通过框架层陈述审计，模块头“轨道 cut 删整类”属于白证。                             |
| 2 | `f5_compound_needs_phom`            | **BLOCK**   | 原文红测是“非 G-不变、读 slot 身份的 cut”，当前反例是“可行性读标签 + Cut 全真且 G-不变”，证的是相邻陷阱。                      | 当前构造 `Cut := True`，不是 label-sensitive cut；且 `true` 可行但被 cut，连主定理的 cut sound 也没有保留。                      | 红测无法覆盖设计稿点名事故，未来 slot-sensitive cut 仍可能漏审。                               |
| 3 | `frontier_prune_dominates`          | **CONCERN** | `<` 幸存、`≤` 被剪的边界是对的，但没有建模 `CERTIFIED witness`，也没有绑定“同一个 Feasible 谓词/schema”。            | 旧谓词下 A=100 certified 支配 B=90；新谓词下 A 失败、B 可行。当前 theorem 无法表达禁止迁移继承。                                      | 可作为纯 value dominance 小引理，不能单独支撑 frontier skip soundness。                 |
| 4 | `frontier_prune_preserves_max`      | **BLOCK**   | `sup'` 保的是全候选 raw value，不是固定谓词下 certified feasible 解的最优值；也不产出 argmax witness。           | `F={A,B}`，旧 A certified value=100，B value=90；新谓词下 A 不可行、B 可行。继承旧 skip 会丢新最优。                            | “剪枝不改变搜索问题答案”过宽，易被误用到谓词迁移、schema 升级、terminal frontier evidence。          |
| 5 | `frontier_prune_preserves_max_lex`  | **BLOCK**   | lex 方向本身正确，但只是 #4 的 `toLex(area,minSide)` 特例，继承同样缺口。                                    | 同 #4。`toLex (100,0)` 支配 `toLex (90,0)` 的旧 skip 不能迁移到新谓词。                                                | max_lex 目标形式化对，但 frontier sound 声称不够。                                    |
| 6 | `eq_key_violated_iff`               | **忠实**      | 有 `S ⊆ U` 与 `A ⊆ U` 护栏时，PB 等式键违反条件确实等价于 `A = S`。                                        | 若去掉 `A ⊆ U`，只能推出 `A ∩ U = S`，不是裸 `A = S`。当前 theorem 没漏。                                                 | 当前 theorem 安全，建议补投影边界 lemma 防误用。                                         |
| 7 | `tp7s_eq_key_sound`                 | **忠实**      | 量化 `∀ A ⊆ U`，匹配 Finset 表示下的完整 0/1 赋值空间。                                                 | `A⊆U` 已在 statement 中。                                                                                   | 可支撑“等式键只禁固定赋值 S”的 sound 性，前提是调用方保证 `U` 含完整 key 字段和 graph syntax version。 |
| 8 | `tp7s_eq_key_no_overcut`            | **CONCERN** | theorem 有 `A ⊆ U`，数学上安全；docstring “真超集不触发”等自然语言少了“U 内”限定。                               | `U={false}`，`S={false}`，`A={false,true}`：`S ⊂ A` 且 `EqKeyViolated U S A` 成立，因为 `true` 在 U 外，PB key 忽略它。 | 若未来把全局 Finset 超集当成 U 内赋值超集，会误读“不过切”。                                     |
| 9 | `tp7s_selected_set_nogood_overcuts` | **CONCERN** | 抽象形状对，但没有形式化 TP7-S 半容量路、并行路、selected-set nogood 违反谓词；docstring “机器版”过强。                 | 当前只是 `Feasible X := 2 ≤ X.card`，`S={false}`，`A={false,true}`。                                           | 足以证明集合论过切边界，不足以声称已机器化原文吞吐 toy。                                           |

## 我给出的补丁方向

F5 主安全定理补丁：显式加入 `Equivalence equiv`、`hCutInv : equiv s t → (Cut s ↔ Cut t)`，并把结论加强为：存在 selected representative，它可行、未被 cut，且其整个等价类内都未被 cut。这样才把“未被 cut 删的类，其序代表仍存活”落到类级语义。

F5 红测补丁：替换为 `f5_compound_non_invariant_cut_overcuts`。构造保留 P-HOM，保留代表选择，但让 cut 读标签且非 G-不变，刚好删掉 master 唯一代表，直接对应设计稿“标签敏感 cut + 序 = 删光合法类”。

frontier 补丁：给 dominance 和 max-preservation 定理加入 `Feasible` 谓词与 `hfw₀ : Feasible w₀`，把 theorem 限定为“同一谓词/schema 下”的 certified witness 剪枝。另补 `frontier_prune_preserves_argmax_witness` 和一个迁移红测 `frontier_dominance_skip_not_migratable`。

TP7-S 补丁：补 `eq_key_violated_iff_inter`，说明没有 `A⊆U` 时只能得到投影等于 `S`；把 no-overcut docstring 改成“U 内真超集”；给 selected-set overcut 反例补显式 `SelectedSetNogoodViolated S A := S ⊆ A`、`S ⊂ A`、`A ⊆ U`，并把 docstring 降格为“抽象玩具版”。

## 设计稿歧义单列

frontier 的 `F` 若在项目内部约定为“固定谓词下已知可行候选集”，则 `frontier_prune_preserves_max` 和 `_lex` 可以从 BLOCK 降到 CONCERN；但当前 docstring 写的是“全候选集”，所以我按 BLOCK 处理。

“最优解 witness 也不能丢”有两种读法。若只需返回任一最优 witness，等值候选被剪通常没问题，因为 `w₀` 留下；若 terminal evidence、可复现 seal 或枚举全部 optima 需要特定 witness，则当前 theorem 明显不足。补丁证明的是“仍存在一个剪后可行 argmax witness”，不是保留所有 argmax。

TP7-S 半容量路 toy 没有在节选中给出可直接形式化的小网络，所以当前 theorem 可判为抽象过切证据，但不能判为忠实机器化吞吐 toy。
