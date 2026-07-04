# completeness

## current_state
结论：现在有"分类学/论证草稿"的雏形，但没有形式化的不可行类 partition，也没有"F1-F9 覆盖所有不可行类"的数学证明。

Q1 已经把待证明命题写出来了：cut framework 9 family 是否数学上充分，即"任何 master partial assignment 若 INFEASIBLE, 必存在 F1-F9 之一可产 sound cut 排除该 assignment"（docs/项目说明/05_open_questions.md:17-19）。但同一段马上降级为当前理解：F1-F9 只是"各自针对一类 INFEASIBLE pattern"，跨 family 覆盖度是从 timeline §3 的 5 issue 推出来的，而且文档明确说"timeline 只列 5 issue, 没数学完整性证明"（docs/项目说明/05_open_questions.md:21-24）。

所以当前状态不是"已证明 cover"，而是"以 5 个已知 issue + red fixtures + telemetry 作为经验性覆盖框架"。Q1 的 verification trigger 也是经验式：168h 真生产 trial 后若仍有 INFEASIBLE candidate 不被 F1-F9 拦，则暗示 cover 不完整；长跑 telemetry 若出现反复 trigger 但无 cut 拦，则数学上需 F10+（docs/项目说明/05_open_questions.md:26-28）。文档把数学难度定为 paradigm-level，并明确列出现在缺的核心步骤："形式化'所有 INFEASIBLE 类'的 partition"和"对每类构造拦截 family 或证明 ⊥"（docs/项目说明/05_open_questions.md:30-32）。

Q14 进一步确认 completeness 仍 open：Soundness 只是"per-family validator 重算 cert"的工程证明，且"非形式化 proof system"；Completeness 直接回指"§5.1 Q1 open"；形式化 proof 需要 Coq / Lean / Isabelle，项目当前不投资（docs/项目说明/05_open_questions.md:392-401）。汇总表也把 Q1 标成 "9 family completeness | P0 | Phase 2+ telemetry 反推"，把 Q14 标成 "形式 proof completeness | P3 | Phase 2+"（docs/项目说明/05_open_questions.md:493,523），P0 critical 清单仍列 Q1（docs/项目说明/05_open_questions.md:530-531）。

## what_exists
1. 有四根因约束到 cut framework 的设计约束映射。03 文档列出 Root cause 1 是 pose-bool master 表达力限制，master 不知 port direction / pole selection / belt routing（docs/项目说明/03_paradigm_death_baseline.md:121-126）；Root cause 2 是 96% utilization 几何死结和 boundary/perimeter trap（docs/项目说明/03_paradigm_death_baseline.md:128-132）；Root cause 3 是 cell-front pattern 已 break symmetry，禁止跨 instance lifting（docs/项目说明/03_paradigm_death_baseline.md:134-139）；Root cause 4 是 single-machine RAM 不可扩（docs/项目说明/03_paradigm_death_baseline.md:141-144）。这些被翻译成四条 paradigm 要求：不重写 master、表达几何+物流 INFEASIBLE 各类、限 within-instance scope、不挤 master scale（docs/项目说明/03_paradigm_death_baseline.md:198-202）。

2. 有 5 个 known issue 到 family 的映射，但这不是完整 partition。03 文档说 cut framework "explicit 处理"衍生的 5 issue（docs/项目说明/03_paradigm_death_baseline.md:159-161）：96% utilization 几何死结由 F1 region_capacity + F6 shape_packing_hall 处理；boundary/perimeter 容量由 F1 boundary regions 处理；manufacturing cluster trap 由 F5 + F3 处理但评估不足；routing 反馈由 F2 + F4 处理；m10 sound 跨 scale 由每 family validator 独立重算 cert 处理（docs/项目说明/03_paradigm_death_baseline.md:163-169）。Issue 3 被明确标为当前最弱点：F5 pattern_nogood 可能退化成 full no-good，132! permutation 撞墙，需要 orbit-aware pattern lift（docs/项目说明/03_paradigm_death_baseline.md:171）。

3. 有 9-family 矩阵。Phase 0 close 文档列出 final state：F1 region_capacity、F2 cutset、F3 port_exposure、F4 component_reach、F5 pattern_nogood、F6 shape_packing_hall、F7 power_hitting_set、F8 power_grid_reach、F9 density_envelope，并给出 mode / version / 来源 / 处理（docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md:37-49）。这是一张 family taxonomy / owner matrix，但它只说明每个 family 处理什么，不证明这些 family 构成所有不可行类的 exhaustive partition。

4. 有盲点/反例清单和处理记录。red_fixtures README 明说它是 doc-only spec，fixture 是 schema-level 反例 + 期待拦截路径（docs/research/p3_b_design_v2_20260521/red_fixtures/README.md:3-5），Day 10-12 只验"反例 ↔ cut 表达"的接口契合，不验 oracle generation、scope-aware replay、validator 重算 cert（docs/research/p3_b_design_v2_20260521/red_fixtures/README.md:9-20）。该 README 列出 F1-F4 反例及 owner family（docs/research/p3_b_design_v2_20260521/red_fixtures/README.md:24-29），并承认 F2 shape packing Hall + F3 power hitting-set 当时需要新 cut family（docs/research/p3_b_design_v2_20260521/red_fixtures/README.md:48-51）。Phase 0 close 后又记录 F10/F13/F14/F15/F16 反例 verdict：F10 走 F4 kinematic upgrade，F13/F15 走 F5 fallback，F14 走 F9 降级 + F5 fallback，F16 归 Master CP-SAT 不需 cut（docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md:60-71）。

5. 有 schema 层分类，但不是不可行类分类。schema_update_v3 有"互斥分类 (per family)"：F1/F2/F4/F6 是 geometric，F3/F5/F7 是 literal，并给出 rationale（docs/research/p3_b_design_v2_20260521/schema_update_v3.md:51-61）。state_machine_v2 也说明自己不定义 cut lifecycle / cut family taxonomy / search heuristic，这些在 cut_lifecycle_v2 和 cut family docs（docs/research/p3_b_design_v2_20260521/state_machine_v2.md:6）。这说明 taxonomy 是工程 schema / family mode 维度，不是 proof-system 的 INFEASIBLE-class partition。

## gap
1. 缺"不可行类宇宙"的形式定义。Q1 的量词是"任何 master partial assignment 若 INFEASIBLE"（docs/项目说明/05_open_questions.md:17-19），但现在没有定义哪些 INFEASIBLE 属于 cut framework 责任、哪些应由 master 自身表达。F16 verdict 明说 Global Algebraic Overload "不需 Cut"，归 Master CP-SAT 线性约束，且"代数归 Master, 几何归 Cut"（docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md:66-71）。因此形式命题必须先定义 theorem domain：是所有 master partial assignment，还是扣除 master-native algebraic infeasibility 后的 geometry/routing/power/binding 子域。

2. 缺 exhaustive partition。当前文档自己说覆盖度来自 timeline §3 的 5 issue，但"没数学完整性证明"（docs/项目说明/05_open_questions.md:21-24）；也自己列出必须形式化"所有 INFEASIBLE 类"的 partition（docs/项目说明/05_open_questions.md:30-32）。5 issue mapping、red fixtures、F10-F16 verdict 都是反例驱动清单，不是互斥且穷尽的 proof-system partition。

3. 缺每个 partition cell 的 owner lemma。Q1 要求"对每类构造拦截 family 或证明 ⊥"（docs/项目说明/05_open_questions.md:30-32），但 family matrix 只列 family 与处理对象（docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md:37-49）。要形式化，必须把每个 family 写成定理：若 assignment 落入 class C_i，则存在该 family 可生成的 cut，且 cut 排除该 assignment，并且 cut body 可表达到 master。

4. F5 仍有定义层缺口。F5 manufacturing cluster trap 当前被明确标为 P0：literal full assignment no-good 退化，132! permutation 撞墙（docs/项目说明/05_open_questions.md:196-205）。5.8 又给出三种 proposed solution：orbit-aware pattern lift、F5+F6/F3 复合 cut、instance-level partition，并说明当前推荐 orbit-aware，但仍需 land，否则 P1.2B-F5 incomplete（docs/项目说明/05_open_questions.md:459-481）。这意味着 F5 的 class definition、orbit quotient、复合 cut 语义或 partition 层都还没进入可证明定理形态。

5. F6/F9 仍有边界定义缺口。F6 的 length-k 反例边界只列了一个 length-3 例子，其他 length=2/4/5 的 ghost-cut 反例分布未列，defer 到 Phase 1.2 枚举（docs/项目说明/05_open_questions.md:207-216）。F9 则有 baseline 和独立性问题：必须有 envelope < trivial 的反例，否则退化 F1（docs/项目说明/05_open_questions.md:273-282）；F9 与 F1 的数学边界公式仍是问号，例如 F9.cap 是否等于 F1.cap 减 cell_owner 项（docs/项目说明/05_open_questions.md:284-293）。这些都阻止把 family scopes 写成清晰互斥/覆盖的数学类。

6. 缺 soundness scope = applicability scope 的形式化。Q3 指出 validator(cert,state)=OK 不足以排除 over-prune；cert sound 但 cut.scope 错会在更广 scope 误剪 feasible（docs/项目说明/05_open_questions.md:51-58）。文档明确说数学难点是 formalize "cut sound 范围"和"cut 适用范围"是同一回事（docs/项目说明/05_open_questions.md:60-64）。没有这个，completeness 命题即使找到 family，也无法保证 cut 可安全复用到目标 partial assignment 的 scope。

7. 缺从 telemetry 到数学 completeness 的桥。现在 Q1 的验证触发是 168h trial、cut_count_by_family 分布、发现 unexplained infeasible 就考虑 F10+（docs/项目说明/05_open_questions.md:26-28）；telemetry 文档也把"unexplained infeasible 连续出现 → 人工复盘提炼 F10"列为报警阈值（docs/项目说明/17_workflow_telemetry.md:71-75）。但 Q18 又说"好 cut"定义模糊，sound 只是必要不充分，"cut 排除多 assignment"直接量化困难（docs/项目说明/05_open_questions.md:438-446）。形式化命题需要一个非经验的 completeness metric，而不是 active_rate / attached_count / trial absence-of-counterexample。

8. 缺正式 proof system / mechanization 选择。Q14 明确说当前 soundness 是工程证明，不是形式化 proof system；形式 proof 需 Coq / Lean / Isabelle，当前不投资（docs/项目说明/05_open_questions.md:396-401）。所以要变成可证明/证伪命题，至少要先落：状态空间定义、assignment 语义、subproblem oracle 语义、cut schema 语义、family generator/validator soundness lemma、family coverage lemma，以及 counterexample 的反模型格式。
