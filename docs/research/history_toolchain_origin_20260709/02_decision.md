## GPT v13 cut language 论题的原始主张

路径缩写：`M=/home/zhuran24/.claude/projects/-home-zhuran24-claude-pj-zmd/memory`；`R=/home/zhuran24/claude-pj/zmd/docs/research/paradigm_search_review_v12_with_code_20260520`；`B=/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521`。

| 结论 | 出处 + 短引 |
|---|---|
| GPT v13 的核心不是换 solver，而是换 master 能接收的 cut 语言。 | `M/project_gpt_v13_cut_language_thesis.md:10-18`："**换 cut 语言不是换 solver**"；"master 只听得懂…pose no-good"。 |
| 反对"换壳"：Choco/Gecode/Z3/clingo/Gurobi/SCIP、全量 routing 入 master、从零写通用 solver 都被排除。 | `M/project_gpt_v13_cut_language_thesis.md:19-24`："换壳不解决 cut 表达力"；"从零写通用 SAT/CP/MIP solver (无底洞)"。 |
| 自建的对象不是通用求解器，而是专用 cut/proof 工具链：PoseStore、SearchState、OracleRunner、CutFactory、ProofLog。 | `M/project_gpt_v13_cut_language_thesis.md:42-47`："推荐自研模块"；"validity checker 必须"。 |
| 目标 cut family 是 region/cutset/port/component/pattern/symmetry 级，而不是 instance-pose no-good。 | `M/project_gpt_v13_cut_language_thesis.md:26-32`："Region capacity cut"；"Separator / cutset cut"；"Port exposure cut"。 |
| cand C 没被立即否定；GPT v13 的定位是和 cand C 正交叠加。 | `M/project_gpt_v13_cut_language_thesis.md:77-84`："cand C 让 master 看 pattern, GPT 让 master 听 region capacity cut"。 |
| GPT v13 真正指出的风险是 cand C 到 routing 阶段仍可能把失败翻译回 pose ban。 | `M/project_gpt_v13_cut_language_thesis.md:67-75`："dual 仍在 cell + facility 级别"；"没有 cut language 升级的设计"。 |
| 直接行动是把 5 类 cut 框架纳入后续设计，并 schema-first 建 proof lifecycle。 | `M/project_gpt_v13_cut_language_thesis.md:86-92`："Phase 3/4 设计文档纳入 GPT 5 类 cut 框架"；"proof object lifecycle schema-first"。 |

## 当时台面上的全部选项(活候选清单+各自为什么没选)

| 选项 | 当时为什么在台面上 | 为什么没成为最终主线 |
|---|---|---|
| 旧 CP-SAT + LBBD / dead_paths 继续加 cut | `R/README.md:5`："4 个候选方向仍 alive, 其余 NO-GO"；`R/02_LEVER_HISTORY_24_DEAD.md:121-130`："6 paradigm…cut form 全退化 instance-pose"。 | pose-bool 只能表达 `x_i,p` no-good；`R/03_BOTTLENECK_UNDERSTANDING_EVOLUTION.md:46-59`："cut 翻译回 master 时只能写…instance, pose tuple"。 |
| B1 pose-bool master | 用户 2026-05-17 已拍过 B1；`R/02_LEVER_HISTORY_24_DEAD.md:147`："User decision 2026-05-17 走 B1…53.3s OPTIMAL"。 | B1 master 真 GO，但上层 cut 死；`R/dead_paths/B1_paradigm_pose_bool_master/README.md:38-40`："master 解开了, cut 端成了新瓶颈"。 |
| Lever 25 IHS | 5/20 alive；`R/alive_candidates/lever_25_ihs/README.md:23-25`："IHS 不在这个 dimension"；但 caveat 是 core 仍可能 pose-bool。 | 实测死：`M/project_lever25_ihs_dead.md:16-23`："core size p50 1.0"；"HS compression=1.0"；`M/...:27-31`："不解决 cut 本身 expressiveness"。 |
| Lever 26 Benders symmetry | 5/20 alive；`R/alive_candidates/lever_26_benders_symmetry/README.md:28-34`："aggregating symmetric cuts"；但可能只是增强。 | 实测死：`M/project_lever26_benders_symmetry_dead.md:16-31`："m5 effective multiplier 1.0"；"cut-relevant pose 无相关 orbit"；"194s 也超 budget"。 |
| Candidate A CDCL warm-start | 5/20 alive；`R/alive_candidates/candidate_a_cdcl_warmstart/README.md:12-13`："CDCL…feasibility hints…CP-SAT optimizer"。 | 证据层是低优先级而非见到 death verdict；`R/.../candidate_a_cdcl_warmstart/README.md:28-33`："不含 routing / port direction / power coverage"；"实质都是给 master 一个 valid placement"。 |
| Candidate C column generation | 5/20 alive且是"真换 master form"；`R/alive_candidates/candidate_c_column_generation/README.md:25-28`："真未试 paradigm shift"。 | Phase 0/1 先 GO：`M/project_cand_c_phase1_go.md:31-37`："4 ramp 全 GO"；但不能单独解决 cut language：`M/project_gpt_v13_cut_language_thesis.md:73-75`："撞回 24 lever 同墙"。后续 160/266 几何死结见 `B/paradigm_death_timeline.md:63-65`："Phase 2 v3 — 160/266 INFEASIBLE"。 |
| 直接换 solver / 写通用 solver | GPT v13 专门列为反路。 | `M/project_gpt_v13_cut_language_thesis.md:19-23`："直接换 Choco…换壳不解决"；"从零写通用…无底洞"。 |
| 自建 cut framework / B Design v2 | 由 GPT v13 cut language 论题转成 B Design v2。 | 成为主线：`M/project_v14_review_findings.md:13-17`："B direction: GO"；但 v14 spec 要重做。Phase 0 后 `B/PHASE_0_CLOSE.md:37-49` 已有"9 大 Cut Family"。 |

## "自建工具链"的论证链(谁提出/什么证据/owner 怎么拍的板)

| 环节 | 结论 | 出处 + 短引 |
|---|---|---|
| 提出者 | 直接提案源是 2026-05-21 用户 ad-hoc 问 GPT 后的三份 GPT v13 共同 thesis。 | `M/project_gpt_v13_cut_language_thesis.md:10-12`："用户 ad-hoc 问"；"三份独立答复共同 thesis"。 |
| 技术核心 | 自建的是 cut/cert/replay/validator 工具链，不是替换 CP-SAT 或写通用 solver。 | `M/project_gpt_v13_cut_language_thesis.md:17-23`："不要 abort CP-SAT"；"不要重写通用 SAT/CP/MIP"。 |
| 负证据 | 27 lever 归档把死法归成 cut amplification、accumulation、family abstraction、master scale、几何死结。 | `M/project_paradigm_death_timeline_27_lever.md:14-21`："5 类死法分类"。 |
| 根因证据 | pose-bool master 表达力、96% utilization、symmetry 被打碎、48GB 单机上界共同约束。 | `M/project_paradigm_death_timeline_27_lever.md:23-28`："4 共同 root cause"。 |
| 正向设计 | B Design 必须显式处理 routing feedback 强 cut、validator soundness、几何死结等 issue。 | `B/paradigm_death_timeline.md:111-146`："Routing 反馈翻译成强 cut…不是 pose-level no-good"；"Validator 每 family 独立重算"。 |
| 外部背书 1 | GPT pro + Gemini 对方向给 GO，但否掉 v14 原 spec。 | `M/project_v14_review_findings.md:10-17`："B direction: GO"；"v14 cut set/state/lifecycle NO-GO"。 |
| 外部背书 2 | review 要求补 boundary、3-4 类新 cut、state schema、10 步 lifecycle/scope-aware replay。 | `M/project_v14_review_findings.md:35-51`："必加 4 类新 cut"；`M/...:77-91`："Cut lifecycle 扩到 ~10 步"。 |
| owner/process 拍板 | 文件中未见一句"用户说自建工具链"的直引；可见拍板形式是 phase gate：Phase 0 close 后进入 Phase 1 编码由用户决定走法。 | `B/PHASE_0_CLOSE.md:121-125`："用户授权检查"；"用户决定走法"；"你已经准备好进入 Phase 1"。 |
| owner 质量要求 | 用户随后要求计划书必须包含 why、paradigm 决策、历史、GO 标准，不能只是 TODO。 | `M/feedback_plan_doc_strategic_layers.md:10-13`："全部东西放进计划书里面"；`M/...:27-43`："paradigm 决策 + 死路分析"。 |
| 最终落地 | 2026-05-22 Phase 1.0 framework 已实现 lifecycle/store/replay/assumptions/helpers，90/90 tests pass。 | `M/project_phase0_b_prep_progress.md:10-27`："Phase 1.0 framework 全 land"；"90/90 test PASS"。 |
| 继续背书 | Gemini round 26/28 给 Phase 1 编码与 Phase 1.0 framework GO。 | `B/cross_check/gemini_round_26_phase1_go.md:41-45`："Phase 1 编码 GO"；`B/cross_check/gemini_round_28_phase1_0_framework_go.md:45-47`："Phase 1.0 GO"。 |

## 决策时间线(带日期)

| 日期 | 事件 | 出处 + 短引 |
|---|---|---|
| 2026-05-17 | 用户决策走 B1 pose-bool master；这是第一次真正 master-form GO。 | `R/02_LEVER_HISTORY_24_DEAD.md:147`："User decision 2026-05-17 走 B1"；"53.3s OPTIMAL"。 |
| 2026-05-18 | B1 Phase 6 path-1/path-2 死：master 持 port-selection 解不动，lazy demand cut 不收敛。 | `R/02_LEVER_HISTORY_24_DEAD.md:56-73`："4 个 form 实测全 verdict 死"；"10 iter 不收敛"。 |
| 2026-05-20 | v12 review 包形成：24 lever dead，台面剩 4 个 alive candidates。 | `R/README.md:5`："24 lever 全 verdict 死"；`R/01_PROJECT_STATE.md:117-120`："IHS / Benders symmetry / CDCL warm-start / Column generation"。 |
| 2026-05-20 | Augmented master Candidate D 实测撞 scale 墙，证明 routing/flow channel 进 master 不现实。 | `R/02_LEVER_HISTORY_24_DEAD.md:105-112`："2.68M cstr"；"RSS 32 GB"；"multi-commodity 推算 24M cstr 必死"。 |
| 2026-05-20 | Lever 26 Benders symmetry cheap gate 死。 | `M/project_lever26_benders_symmetry_dead.md:27-31`："cut-relevant pose 无相关 orbit"；"194s 也超 budget"。 |
| 2026-05-20 | Lever 25 IHS cheap gate 死。 | `M/project_lever25_ihs_dead.md:23-31`："compression=1.0"；"IHS 跟 LBBD 完全等价"。 |
| 2026-05-21 | GPT v13 cut language thesis 出现：转向自建 cut/proof 工具链。 | `M/project_gpt_v13_cut_language_thesis.md:10-18`："换 cut 语言不是换 solver"。 |
| 2026-05-21 | cand C Phase 0/1 GO，但被定位为与 cut language 正交，不能单独覆盖 routing feedback。 | `M/project_cand_c_phase1_go.md:31-37`："4 ramp 全 GO"；`M/project_gpt_v13_cut_language_thesis.md:84`："正交不冲突可 stack"。 |
| 2026-05-21 | GPT pro + Gemini v14 review：B direction GO，v14 spec NO-GO，Phase 0 扩成约 3 周准备。 | `M/project_v14_review_findings.md:10-19`："high robustness 共识 verdict"；"必修 4 件事"。 |
| 2026-05-21 至 2026-05-22 | B Design v2 Phase 0 形成 9 family、lifecycle、state schema、red fixtures、PoC，并经 Gemini 多轮 cross-check。 | `M/project_phase0_b_prep_progress.md:156-170`："9 family spec + 7 轮 Gemini"；"Phase 1 编码 GO"。 |
| 2026-05-22 | Phase 0 close：Gemini round 22/26 背书进入 Phase 1。 | `B/PHASE_0_CLOSE.md:3-5`："Phase 0 ABSOLUTE FINAL CLOSE"；`B/cross_check/gemini_round_26_phase1_go.md:45`："Phase 1 编码 GO"。 |
| 2026-05-22 | P1.x 最早雏形落成：Phase 1.0 framework 进入源码。 | `M/project_phase0_b_prep_progress.md:10-27`："src/cuts/…~2600 LOC"；"90/90 test PASS"。 |