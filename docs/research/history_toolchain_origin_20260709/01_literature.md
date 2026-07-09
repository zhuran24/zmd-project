## 调研问题清单与各自答案

| 调研问题 | 答案 |
|---|---|
| 现成 production solver 能不能替代 CP-SAT？ | 基本否。调研覆盖 Choco/Gecode/Chuffed/Z3/Picat/clingo/SCIP/LCG 后结论是"同 family 或代际落后"，换 solver"不解决 paradigm-level 死锁"。出处：`paradigm_search_review.../investigated_paradigm_groups/group_a_solver_families.md:66-70`，短引："换 production solver 不解决 paradigm-level 死锁"。 |
| PBO / SCIP-PB / RoundingSat 是不是最大外部缺口？ | 先被 Agent 4 推为高 ROI，但 DA 复核后降为"KILL 或硬 gate"。原因是 HiGHS 死因诊断错、dense coupling 与 propagation state 仍同款。出处：`literature_review.../agent_4_paradigm_shift.md:132-172`，短引："PB solver paradigm…未被项目尝试过的最大算法层缺口"；反证出处：`literature_review.../da_review_checkpoint2.md:24-34`，短引："RAM scaling root cause 同款"。 |
| Column generation 能否成为换 master form 的路？ | 理论上是"不同 dimension"，但 column 粒度无 principled method，且 forced-unique-instance 结构会退化成 whole-layout 或 single-pose。出处：`paradigm_search_review.../alive_candidates/candidate_c_column_generation/README.md:27-42`，短引："master 不见 pose-bool 个体…但前提失败风险"。 |
| 更强 LBBD cuts 有没有文献支持？ | 有。Karlsson/Rönnberg 支持 cut strengthening；QuickXplain/deletion filter 有理论和经验依据；但"learned cut 必须真 solver replay"没有现成 paper，反而成为项目自研点。出处：`literature_review.../agent_2_lbbd_cuts.md:12-20`，短引："irreducible cut + deletion filter"；`agent_2_lbbd_cuts.md:125-133`，短引："必须真 solver replay"。 |
| CP-SAT internals 能不能直接给解法？ | 主要是诊断工具，不是 paradigm 输入。Perron 2023 能解释 RAM/linearization；Bofill PB+AMO 可能针对 dense PB 做 Phase 0，但不直接改变 master/cut 结构。出处：`literature_review.../README.md:20-24`，短引："用作诊断工具，不是 paradigm 输入"；`agent_3_cpsat_internals.md:94-109`，短引："唯一可能打到 latency-bound 痛点"。 |
| 2D packing / geometry / VLSI exact 方法能否移植？ | 不能直接移植。经典 MER 只解决 fixed obstacles，VLSI exact scale 远小于 266 facilities，2D BPP 假设与项目 side constraints 不匹配。出处：`paradigm_search_review.../investigated_paradigm_groups/group_d_layout_geometry.md:5-23`，短引："exact 只能局部"；`group_d_layout_geometry.md:25-34`，短引："obstacles 固定"。 |
| MaxSAT / DD / SDP / Lagrangian 等理论工具能否兜底？ | 大多 NO-GO：MaxSAT 编码爆，DD 需要自然 DP，SDP/Lasserre 规模物理不可达，Lagrangian 只给 bound 且不对齐 certified path。出处：`group_c_cut_bound.md:5-35`，短引："单机 48 GB 内连 build 都不起来"；`group_b_decomposition.md:14-42`，短引："非自然 DP"。 |
| 24 个死杠杆给出的共同教训是什么？ | 两类死法：cut/subproblem framework 的表达力被 pose-bool 维度锁死；augmented master 想升表达力又撞资源墙。出处：`paradigm_search_review.../02_LEVER_HISTORY_24_DEAD.md:119-130`，短引："cut 表达力被 master pose-bool 维度锁死"。 |
| 当时还剩哪些 alive 候选？ | IHS、Benders symmetry、CDCL warm-start、CG 都只是待 gate：IHS 可能仍退化到 pose-bool core；symmetry 是 orthogonal 加速；CDCL 只是 hint source；CG 成本 3-6 月且粒度未解。出处：`alive_candidates/lever_25_ihs/README.md:23-26`，短引："core 仍是 pose-bool conjunction"；`candidate_c_column_generation/README.md:43-84`，短引："priority 最低"。 |
| 结论是否是"继续找现成工具"？ | 否。5/20 复盘结论已是 production CP-SAT+LBBD 内调穷尽，真 break 需要 research 级投资，不在 import 现成工具范围。出处：`02_LEVER_HISTORY_24_DEAD.md:149-154`，短引："不是 production tooling 内调"；`03_BOTTLENECK_UNDERSTANDING_EVOLUTION.md:98-102`，短引："不在现成 import 范畴"。 |

## 文献调研四路的关键结论（逐路）

1. **Agent 1：Column generation / branch-and-price**
   结论：CG 是少数真正可能换 master 维度的方向，但项目的 forced-unique-instance 结构让 column 粒度成为核心未解问题；可吸收的是 CP pricing、limited-memory cuts、branch-price-cut 架构经验，不是直接套工具。出处：`literature_review.../agent_1_column_generation.md:50-55`，短引："CP-as-pricing-engine"；`agent_1_column_generation.md:66-69`，短引："limited memory trick"；`candidate_c_column_generation/paper.md:53-70`，短引："0 paper 显式讨论 column 粒度怎么定"。

2. **Agent 2：LBBD cut strengthening / MUS / placement-routing**
   结论：这一路最直接导向自建 cut framework。文献支持 cut strengthening、MUS/QuickXplain、multicut、packing cut families；同时确认项目需要"真实 solver replay + fail-closed acceptance"，这是现有文献没有完整覆盖的自研点。出处：`literature_review.../agent_2_lbbd_cuts.md:12-20`，短引："feasibility cut strengthening"；`agent_2_lbbd_cuts.md:81-84`，短引："coordinate-window cut / interval clique cut"；`agent_2_lbbd_cuts.md:125-133`，短引："PCR-CUT 的 paradigm 创新点"。

3. **Agent 3：CP-SAT internals**
   结论：CP-SAT 论文能解释为什么 RAM/linearization/worker trail sharing 会出问题，但不能给出新的 paradigm；Bofill PB+AMO 只适合作为 dense constraint encoding 的 gated spike。出处：`literature_review.../agent_3_cpsat_internals.md:12-21`，短引："linearization_level…RAM 涨"；`agent_3_cpsat_internals.md:94-97`，短引："dense linear + AMO 混合"；`da_review_checkpoint2.md:51-57`，短引："diagnostic value 高、prescriptive value 低"。

4. **Agent 4：Paradigm shift 候选**
   结论：PB/SCIP/RoundingSat 是最像"换现成工具"的候选，但复核后发现它没有绕开项目真正的 RAM scaling / latency / dense coupling 根因；MaxSAT、DD、2D packing、SDP、presolve 也各自因编码、scale、结构或 exactness 不匹配而降级。出处：`literature_review.../agent_4_paradigm_shift.md:10-24`，短引："PB 是天然 fit"；`da_review_checkpoint2.md:18-34`，短引："paradigm transfer claim 根本不成立"；`literature_review.../README.md:39-49`，短引："KILL 或硬 gate"。

## 瓶颈理解的演化线

1. **误解 1：RAM 是核心瓶颈。**
   后来发现 workers 从 8 降到 1 只把 RAM 压下去，14h trial 仍全 UNKNOWN。出处：`03_BOTTLENECK_UNDERSTANDING_EVOLUTION.md:5-17`，短引："真瓶颈非 RAM"。

2. **误解 2：wall/search 是 NP-hard 本质。**
   B1 pose-bool master 后 30min UNKNOWN 变 53s OPTIMAL，说明 wall 不是问题本体，而是 master form 错。出处：`03_BOTTLENECK_UNDERSTANDING_EVOLUTION.md:18-30`，短引："wall 不是 fundamental, 是 master form 选择问题"。

3. **阶段性正解：master form 决定第一层成败。**
   B1 是唯一真 GO，pose-bool 解锁 master；但 master 解锁后 routing/binding cut 变成新瓶颈。出处：`dead_paths/B1_paradigm_pose_bool_master/README.md:24-40`，短引："唯一 paradigm-level 真 GO"；`03_BOTTLENECK_UNDERSTANDING_EVOLUTION.md:31-42`，短引："cut 框架成为新瓶颈"。

4. **误解 3：cut 不够强，只要换 subproblem/cut family。**
   Path 12-17 从 binding-side、corridor capacity、patch CP-SAT、positive witness、global core、D2 flow 全试过，最终同质失败。出处：`02_LEVER_HISTORY_24_DEAD.md:75-101`，短引："6 paradigm 撞同墙"；`path17_d2_subproblem/code/phase2_verdict.md:53-59`，短引："cut form 被 master pose-bool 限制"。

5. **当前正解：维度锁死 + scale 墙。**
   master 只认识 `x_{i,p}`，cut 不能表达 connectivity/flow 的原因；若把 routing/flow channel 进 master，又爆成 2.68M constraints / 32GB。出处：`03_BOTTLENECK_UNDERSTANDING_EVOLUTION.md:44-60`，短引："cut 表达力被 master form 锁死"；`L23_augmented_master_candidate_d/code/phase3_verdict.md:26-46`，短引："pose_count × ports_per_pose × commodity_count"。

## 这些调研如何直接导出"自建 cut framework"的决定

1. **先排除"换现成 solver/tool"的路线。**
   32 个 paradigm 调研里，绝大多数 NO-GO；production solver 同质或更弱，PBO/PB solver 没改 master/cut 维度，CG 虽不同维度但无 column 粒度方法。出处：`paradigm_search_review.../README.md:3-6`，短引："32 个 paradigm 方向"；`group_a_solver_families.md:66-70`，短引："ROI 全部为负"；`group_c_cut_bound.md:17-25`，短引："不改 master/cut 维度"。

2. **再确认"继续堆单个 cut"也不够。**
   RAB-SEP、SAC-Hull、PCR-CUT、D2 都能端到端 land，但 0/8 certified；问题不在某个 subproblem 算法，而在 cut 翻译层统一退化。出处：`path14_pcr_cut/code/phase5_verdict.md:26-37`，短引："70 PCR-CUT cuts added…但 paradigm 不 sufficient"；`path17_d2_subproblem/code/phase2_verdict.md:61-77`，短引："没法表达…connectivity/flow 信息"。

3. **因此需要的是"cut families + 生命周期 + validator"的自建工具链，而不是单一算法。**
   PCR-CUT 已经显出雏形：Phase 0 oracle、patch solver、replay validate、QuickXplain、signature lifting、master hook、multi-anchor verdict；项目规则要求 fail-closed 和 proof lifecycle。出处：`dead_paths/path14_pcr_cut/README.md:17-23`，短引："Phase 0-4 全 GO"；`shared_infra/CLAUDE.md:338-348`，短引："replay validate…QuickXplain…proof lifecycle"；`shared_infra/PROJECT_LOCK.md:72`，短引："generate → serialize → deserialize → validate → resolve → replay"。

4. **文献层给了框架部件，但没有给完整项目解。**
   LBBD 文献给 cut strengthening 家族；packing 文献给 interval/window cut family；LCG 文献解释外部 cut 等价手写 explanation；但"learned cut 必须真 solver replay"没有现成 paper。出处：`literature_review.../agent_2_lbbd_cuts.md:137-141`，短引："Top 3 推荐"；`agent_2_lbbd_cuts.md:101-109`，短引："手工补一种 LCG explanation"；`agent_2_lbbd_cuts.md:133`，短引："没有专门做…明确 paper"。

5. **最终转折点：从"找一个能救的 paradigm"改成"建一个能系统试错、验证、淘汰 cut family 的框架"。**
   5/20 的状态已经是：production CP-SAT+LBBD 内调穷尽，真 break 需要 1-3 月 research；5/24 文献复核又把外部 PB solver 降为 hard gate，并把 LBBD cut strengthening / CP-based CG / CP-SAT diagnostics 作为可吸收部件。出处：`02_LEVER_HISTORY_24_DEAD.md:151-154`，短引："paradigm investigation 现穷尽"；`literature_review.../README.md:111-119`，短引："按 ROI 排"；`da_review_checkpoint2.md:100-111`，短引："Revised Top 3"。