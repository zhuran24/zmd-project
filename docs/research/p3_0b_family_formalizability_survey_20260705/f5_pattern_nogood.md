# F5 pattern_nogood —— literal-based no-good cut,基于 slot-indexed pose assignment 经 sub-problem oracle 验证 INFEASIBLE 后学习的禁止组合子句（属 lifecycle 里的 "literal" cut family，用 multiset evaluator）

## proposition
F5 `pattern_nogood` 是一个 literal-based no-good cut。spec 的核心形式是：一组具体 facility pose assignment 被 sub-problem oracle 验证为 `INFEASIBLE`，就学习禁止该组合的 cut，即禁止 `slot_1 = pose_1 ∧ ... ∧ slot_n = pose_n` 同时成立；spec 明写"specific assignment"经 oracle 验证 `INFEASIBLE` 后学 cut，形式见 05_pattern_nogood.md lines 11-17（docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md:11-17）。它被标为 `literal` family，并走 multiset evaluate，声称跨 group permutation sound，同文件 lines 3-6、19。

更严谨地说，当前实现中的命题应表述为：给定同一 replay scope 下的 `BState σ`、注册且版本匹配的 sub-problem oracle `O`、非空 finite core `C = [(g_i, s_i, p_i)]`。若每个 literal 满足 `g_i` 是真实 group、`0 ≤ s_i < demand(g_i)`、同一 `(g_i,s_i)` 不重复、`p_i ∈ pose_domain(g_i)`，并且 `O.query(C, σ)` 返回 `INFEASIBLE`，则 F5 cut 禁止任何当前 selected pose multiset 覆盖 `C` 的状态：对每个 `(g,p)`，若状态中 `selected_poses` 的计数至少为 `C` 中 `(g,p)` 的计数，则该状态触发 cut，应被视为不可行。slot index 在实际触发时不按命名 slot 一一匹配，而是被 group-anonymous multiset 语义折叠；代码的 evaluator 对 `(group_id, pose_id)` 做 Counter 计数并检查 `state_counts[k] >= demand_count`（src/cuts/lifecycle.py:1014-1070）。

这个命题包含一个"slot-indexed oracle core → group/pose multiset cut"的 lift。state-machine 文档说明 group 内 slot 是可置换匿名的，cut resolve 要检查所有 anonymous slot permutations / subset matches，而不是只看命名 slot；见 docs/research/p3_b_design_v2_20260521/state_machine_v2.md:291-307。PROJECT_LOCK 后来把 F5 slot 完整性写成硬 gate：每个 literal 必须是真实、唯一、在界内的匿名 slot，否则 slot-collision core 会被 oracle trivial UNSAT 但 multiset lift 过强导致 FP，PROJECT_LOCK.md:399-409。

## argument_type
F5 自身不是 Hall、max-flow/min-cut、LP dual/Farkas 或几何面积证明。F5 family 的核心是"外部 oracle 证明某个有限 literal core 不可行 → 学习一个 propositional no-good clause"（属计数/鸽笼类的组合命题范畴，而非几何或流论证），证据是 spec 把 family 定义成具体 pose 组合经 sub-problem oracle 验证 `INFEASIBLE` 后学习 `not(conjunction)`（docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md:11-25）。

它实际还叠加了有限 multiset/计数论证：literal-based evaluator 对 `(group, pose)` 计数，检查 cut demand counter 是否被 state selected counter 覆盖（src/cuts/lifecycle.py:1014-1070）。这个部分是有限集合/多重集包含关系（计数论证），不是几何重叠或图可达性。

第三个成分是 序/置换（group-orbit / 置换不变性）论证：state-machine 文档要求 anonymous slots 在 group 内可置换，resolve 必须检查所有 subset matches；PROJECT_LOCK 指出 slot-collision 会让 oracle-trivial core 被 lift 成更强 multiset cut，所以 validator 必须验证真实、唯一、在界 slot（docs/research/p3_b_design_v2_20260521/state_machine_v2.md:291-307；PROJECT_LOCK.md:403-409）。也就是说，F5 的 family-level soundness 是"oracle-soundness axiom（信任外部原语）+ finite multiset counting（计数）+ slot permutation/orbit quotient（序/置换）"的组合，不含 Hall 匹配、最大流最小割、LP 对偶/Farkas、区间/圆/线段几何、图可达性、集合覆盖这几类。

如果 sub-problem oracle 本身是 routing/binding/PCR-CUT，那么 oracle 内部可能涉及 CP-SAT、图连通性、min-cut、几何端口等（即上述被排除的类型可能出现在 oracle 内部），但当前 F5 validator 不读 witness、不验证 oracle 内部证明，只调用 `query()` 看 verdict（pattern_nogood.py:338-367）。因此这些不属于 F5 validator 自身的数学内容，而是外部原语的证明义务（见 dependencies 字段）。

## formalization_needs
若只形式化 F5 family 的核心数学命题，而不形式化 oracle 内部，则主要需要有限类型、有限 map、multiset/Counter、自然数计数、subset/≤ 关系、以及 group 内 slot permutation/orbit quotient 的基础工具。依据是 evaluator 明确把 cut literals 聚合成 `(group_id, pose_id)` Counter 并检查 state Counter 覆盖（src/cuts/lifecycle.py:1045-1070）；state-machine 明确 slot 匿名和 permutation/subset match 语义（docs/research/p3_b_design_v2_20260521/state_machine_v2.md:291-307）。

形式化时可抽象证明的部分：给定 finite groups、pose domains、demand、slot-complete core、oracle-soundness predicate，证明 multiset no-good cut 对所有覆盖该 core 的 group-anonymous assignments sound。这个证明不需要 Hall、max-flow/min-cut、LP dual/Farkas、计算几何库；这些只在外部 oracle 的正确性被展开时才进入。F5 当前 validator 对外部 oracle 只 re-query verdict，不验证 witness 或 proof object（pattern_nogood.py:338-367）。

绑死具体系统的部分：`PoseId` 来自 candidate_placements，`BState` source_digest 覆盖 canonical_rules/candidate_placements/mandatory instances 等具体项目 artifact（lifecycle.py:46-50、504-520）；scope replay 还绑定 ghost、blocked/exterior hash、artifact hashes 和 oracle version（lifecycle.py:941-984）。若只证明抽象 F5 no-good lemma，这些可以被参数化成 finite domains 和 scope equality 假设；若证明"当前项目的某个 cert 真 sound"，就必须把这些 artifact 解析、pose_domain 构造、oracle semantics 一起纳入证明或作为外部可信原语（trusted oracle axiom，未在代码里被独立证明，仅运行时假设）。

字节级 validator 形式化不是 family 数学核心，但如果要覆盖实现一致性，还需要 JSON AST/schema、strict duplicate-key rejection、UTF-8、SHA256 bookkeeping 等模型；这些来自 `validate_cert_payload` / `loads_strict_json` / `validate_cut_integrity`（src/cuts/cert_schema.py:131-174、src/io/strict_json.py:51-67、src/cuts/lifecycle.py:544-563）。数学核心可以先把 decoded cert 当 record，避免把 parser/SHA256 作为第一阶段证明负担。

## latent_issues
- Class C 退化风险：spec 顶部明写 132 个 `mfg_3x3` cluster 时退化 full no-good，Family 9 density_envelope 是真正解（docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md:7）；展开说明 full no-good 不能跨 translation lift（同文件 lines 30-40）。
- accumulation 监控仍被列为 Phase 1 必加，ratio > 50% 是 telemetry alarm（同文件 lines 158-164）。
- Open questions：Translation lift、oracle abstraction version / compat matrix、与 F7 cell_owner causation 重复（同文件 lines 166-174）。
- spec 旧 cert schema 与当前代码不一致：spec 仍列 `oracle_cert_hash`、`sub_oracle_witness_blob_b64`，并在 validator 示例中检查 witness hash（同文件 lines 42-57、131-145）；当前代码则明确 witness bytes 不进 cert、witness hash validation removed（src/cuts/families/pattern_nogood.py:20-24、133-135）；cert schema 当前允许字段也只有 `cert_kind/sub_problem_oracle_name/sub_problem_oracle_version/forbidden_pose_pattern/core_minimization`（src/cuts/cert_schema.py:69-75）。
- validator docstring 里仍写第 4 步是 `sub_problem_witness_hash hex sha256 schema`，但实现没有该字段检查；同一文件前文又说 witness hash removed（pattern_nogood.py:133-135 与 pattern_nogood.py:377-386 自相矛盾）。
- real adapters 未落地到 F5 registry：oracle 模块注释说 Phase 1.2 无真实实现，tests inject fakes（src/cuts/oracles/pattern_nogood_oracle.py:65-67）。
- reverify deadline 后续可能调参：validator 注释说 15s 是 1.5× generator default，Phase 1.5+ 可按真实 adapter latency telemetry 调整（pattern_nogood.py:54-60）。
- lifecycle 层 `step_8_apply_to_master` 仍是 `NotImplementedError`，不是 F5 validator theorem 本身，但说明 cut-to-master apply 集成仍有未实现边界（src/cuts/lifecycle.py:1121-1126）。
