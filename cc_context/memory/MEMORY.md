## 当前状态 / 交接

- [交接 Windows + 九审待外审 (单一 living 现状源)](handoff_windows_ninth_review_pending.md) — **当前 phase/状态权威源, 现状只信这条**；2026-06-06 已含文档树/记忆树 closeout 与 GitHub 上传准备。
- [P1.3A design phase (N=8 merger)](project_p1_3a_design_phase.md) — 设计记录: LBBD loop 已存在只缺 step_8 桥; F1-only; cut 强形式 vs nogood 头号决策; Step0 8/8 PASS; 等用户 phase-boundary 决策.
- [Windows 接手环境 (稳定 reference)](project_windows_handoff_env.md) — 路径/venv/能力边界、slug、prod-scale 回 Linux 主机；稳定环境细节只看该条。
- [Phase 1.2 spike close ✅ + F3 phase 完成](project_phase_1_2_progress.md) — 7/7 family close + F3 generator; 历史细节看该条, 当前现状看交接条。
- [记忆现状防过时协议](feedback_memory_currency_protocol.md) — 身份vs现状分离 + 单一 living 现状源 + phase 转换更新仪式 + transient 断言带日期 + 周期 staleness sweep + 仓库相对路径. 治本 3 个 HIGH 过时.
- [记忆树 publish-safety/currentness gate](project_memory_tree_publish_safety.md) — 2026-06-06 补强: 当前树 secret scan、repo-native INSTANCE check、memory graph/index/live-mirror gate 接入 preflight; 旧 key 需 owner 侧轮换。
- [项目知识树架构](project_knowledge_tree_architecture.md) — 逻辑单树/物理双树: docs=稳定项目表达, memory=协作连续性; living claim 走 subject/projection, evidence 节点保历史。
- [数字单一来源架构 (core-node+投影+强制函数)](project_authoritative_numbers_single_source.md) — 项目数字 + cut-family SoT 的主体/投影/强制函数经验；教训: 强制函数 > 规则。

## 打包 / 外部审查规范

- [打包簇 hub](index_packaging_cluster.md) — 外审打包规范入口: 何时打、prompt、内容、压缩、新窗口、reproduce、错估分类.
- [大节点结束打包 GPT pro 审查](feedback_big_milestone_gpt_pro_review.md) — 大节点 (Phase 完成/ramp/paradigm shift) 整 phase 打包送 GPT pro (≠ Gemini per-commit). **close 门禁=连续≥3 次独立审查零问题**.
- [External review prompt 7-section 模板](feedback_external_review_prompt_template.md) — 真瓶颈、死路 inventory、审查 axis、决策选项、优先方向、不可达 armor、deliverable.
- [GPT review prompt 加料 armor](feedback_gpt_review_prompt_armor.md) — 三段式: 真瓶颈 + 死路黑名单/白名单 + 不可达必须形式化证明 (cite literature, 不准 'I believe'). L14 实测起作用.
- [GPT review 新窗口零历史](feedback_gpt_review_no_history.md) — 新窗口 0 memory; 包/prompt 不准引用上次 GPT 输出; 要 ref 必须打包进 zip 或 inline 展开.
- [GPT prompt 不要催眠前缀](feedback_no_role_priming_for_reasoning_models.md) — "你是 X 专家" role-priming 对推理模型反作用; 直接讲任务 + format + 约束.
- [Review 包不放 prompt + 主动性内容](feedback_review_pkg_no_prompt_inside.md) — zip 只放事实素材; prompt/verdict/Close/审查指引放包外.
- [Review 包数据完整性 default](feedback_review_pkg_data_completeness.md) — 禁 priming 但 factual 要完整; code/archive/telemetry/reproducer 按需全入.
- [大 review pkg 用 7z + ship 7za](reference_review_pkg_7z_strategy.md) — 大包默认 7z; 必要时带解压工具、README、排除清单.
- [新窗口 review 包不带历史](feedback_review_package_for_new_window.md) — 新 GPT 窗口 review 包 README 不写 carry-forward (跟 v3/v4 不一样); standalone 极简点指引, 详细数据让 GPT 自查 zip.
- [Audit finding 必先 reproduce 才 archive](feedback_audit_verify_before_archive.md) — 反 GO 章 ritual 反向: NOT GO + finding 也必 specific reproduce (script/grep) 全 pass 才 archive. ~5-15 min/finding cheap.
- [外部审查报告 reproducibility 不足](feedback_external_review_reproducibility.md) — GPT 同 prompt 跑两次 finding 列表可能不同; sandbox 链接会过期立刻 cp 副本; 多次报告交叉信.
- [GPT 错估 4 种 taxonomy](feedback_gpt_error_types_taxonomy.md) — 算法错估 (攻错点) / 前提错估 (data 不满足 hidden assumption) / 数学能力上限 / L15 paradigm 层. 前 2 类 push GPT, 数学能力类承认 paradigm 限制.
- [Adversarial soundness audit (Gemini 漏, GPT pro catch)](feedback_adversarial_soundness_audit.md) — audit 分 2 层: Layer 1 spec↔src↔data (Gemini OK), Layer 2 adversarial "假 cert 能 pass?" (GPT pro 强).
- [GPT pro Phase 1.1 audit history (现 verdict GO)](project_gpt_pro_p11_audit_not_go.md) — 11 round audit 全 NOT GO → 15 commit close → 5 轮 deliverable 落地 Phase 1.1 GO. R5 reviewer 首次 "1.1 gate 正式通过".
- [GPT pro P1.2 in-progress review (9 verdict)](project_gpt_pro_p1_2_in_progress_review.md) — 2026-05-24 快照: 主线 ✅ 不换; 立刻 land sound≠converge 警句 + dark matter telemetry 硬闸 + cut store 评分淘汰.
- [v14 review verdict (历史)](project_v14_review_findings.md) — 2026-05-21 GPT pro + Gemini round 12/13: B GO + 4 必修. (详 linked file)

## 工作流 / 协作偏好

- [验证类任务必派独立 backstop](feedback_verification_independent_backstop.md) — 验证/核对/查全类不只信 main 自审; 独立 workflow/子代理直接查被验对象本身, re-audit 不降 scope.
- [N=1 别当因果 (先排随机)](feedback_no_causal_claim_from_n1.md) — 单次观察编干净因果当事实=反复犯的病; "改 X 就好了"≠"X 致因", 要定因须对照重复. 实例: review 质量归 README / 无下载按钮归大小, 均被戳穿. 同根 [[external-review-reproducibility]].
- [Agent vs Workflow 派遣选型 + Ultracode](feedback_agent_vs_workflow_dispatch.md) — 形状二选一 (单闭环→Agent / 扇出·流水线·对抗核→Workflow, 后者有 resume); dispatch 三选一 (线性→自己/散落→wf/机械→子代理); Ultracode=穷尽不计 token.
- [改 memory 前先过方案](feedback_memory_edit_confirmation.md) — 机械安全小改直接做; 结构性大改 (新增/删条目/重组/slim MEMORY.md) 先给用户确认.
- [记忆树结构健康](feedback_memory_tree_structural_health.md) — wikilink 命名统一才解析 + MEMORY.md ~24576B 超了尾部静默截断 (加索引前先 slim) + harness 重写 frontmatter 保 name. 区别于现状过时轴 [[memory-currency-protocol]].
- [Gemini 3.1 pro 数学 consultant](reference_gemini_math_consultant.md) — 数学 second opinion；key 不进 repo/memory, 只读 `GEMINI_API_KEY`。
- [Gemini 自然口吻写作更靠谱](feedback_gemini_better_at_natural_tone.md) — Claude 默认 register 偏端着/工程化; 给外部 reader 的长 narrative 默认 Gemini fat-context 写, Claude review 细节修.
- [算法/数学层必经 Gemini cross-check (v2 加严)](feedback_gemini_review_algorithm_math.md) — "先 check 再继续". 每 commit 后立刻 cross-check 不堆 (堆到 round 14 找出 3 致命 bug). 纯 refactor/rename/IO 不算数学层.
- [Gemini prompt audit 模式 — 不要 GO 章 ritual](feedback_gemini_prompt_audit_mode.md) — "Gemini 用来找问题不要被夸傻". 真数据进 paths + armor 强制 3 死法 + 反 vague hyperbole + 不重写 prompt 别调.
- [设计阶段 N 路并行子代理](feedback_design_phase_n_parallel_agents.md) — 代码设计阶段启 N=8 opus 子代理各带不同 slant, main 当 merger; 补 RLHF bias. 紧时 N=2-3, 假设稳才 fire.
- [闭环任务直接 spawn sub-agent](feedback_subagent_for_closed_loop_tasks.md) — 独立闭环 + 不需中途决策 + 可验证的中等粒度活 (≥3 step) 直接 spawn opus background, 不问 user. (explore N 路 vs execute 单线)
- [Phase boundary 两镜像偏见](feedback_main_merger_scope_creep_bias.md) — 会往大扩或往小缩; **User 是唯一可信 phase boundary auditor**.
- [Sub-problem vs augmented master 默认偏见](feedback_subproblem_vs_augmented_master_default.md) — 默认会偏 LBBD sub-problem; 实施前先明确 vars 是否进 master、loop、cut form、同质死法.
- [paradigm Phase 0 cheap gate workflow](feedback_paradigm_phase0_cheap_gate.md) — 新 paradigm 实施前必走 Phase 0 (≤1h cheap gate) 验前提, GO 后再投 Phase 1. 反例 Path 08 直接 Phase 1 浪费 4 form.
- [plan doc 不是 TODO list, 必含战略层](feedback_plan_doc_strategic_layers.md) — plan doc 必含战略/数学原理/paradigm/历史/GO 标准/依赖图/风险/mitigation/回滚, 不只 commit-level TODO.
- [proof object 必须 6 步 lifecycle 闭环](feedback_proof_object_lifecycle.md) — generate→serialize→deserialize→validate→resolve→replay→regression; schema landed ≠ runtime correct; v4 replay bug 根因.
- [不回复 = 默认同意我的倾向](feedback_no_reply_means_agree.md) — main 提了 stated preference 的问题 user 不回 → 默认同意直接推进. 不可逆/高 stakes 例外. 同 [[lazy-mode]] root.
- [懒狗模式 — 替用户想](feedback_lazy_mode.md) — 不是禁词清单, 是认同"无谓盖章=浪费用户"; 想替他省事自然不问; 改 generation 内在倾向比改 surface 深.
- [直接讲核心 finding](feedback_directly_state_core_finding.md) — 第一句给结论+真问题定位. 不准先列 A/B/C 选项让用户选, 不准堆数据回避结论. 不确定就说"倾向 Z".
- [清晰 > 简短 (沟通)](feedback_clarity_over_brevity.md) — 用人话 = 展开术语+场景+why+代价, 不是缩短. 不准只给代号 A/B/C. "清晰在我们这个项目里最重要".
- [别把我的项目全局视野投射到用户](feedback_dont_project_project_visibility.md) — 讲理由前先从零搭共同词汇; 用户只见重型项目极小一片, 我常默认共享术语省地基→理由成黑话. 区别 [[clarity-over-brevity]] (HOW): 本条讲 WHY 我会漏 (没察觉在假设共享背景).
- [不准列放弃选项](feedback_no_giveup_options.md) — 除非 formal proof 证明不行; "接受 verdict/改方向/停在这里" 不准当 option 列.
- [不要给暂停/休息建议](feedback_no_rest_suggestions.md) — 列方案时不准把"暂停/休息/睡"当选项. 用户自己知道何时该休息.
- [代码注释别切到工程化语气](feedback_code_comments_plain.md) — 写注释不切"严谨技术文档"模式; 大段年代戳/学术段碍眼; 只在 why 非显然处留一句人话.
- [优化必须 stack 所有方案](feedback_optimization_strategy.md) — 不按 ROI 单选, 全上是唯一选择 (游戏内容持续膨胀).
- [不要进 micro-optimization 螺旋](feedback_avoid_micro_optimization_spiral.md) — 占比 <5% 就停手换方向 (前车之鉴 Codex).
- [终末地项目流程要轻](feedback_keep_review_process_light.md) — preflight + 自主审查够用, 不必每 patch 套外审.
- [工时按 Claude 节奏估](feedback_work_time_estimates.md) — 不按人类工程师"安全 buffer"打底, 多数任务分钟级.
- [运维脚本写完存入口](feedback_record_tool_entry_points.md) — refresh/sync 脚本写完立刻在 CLAUDE.md 加 runbook 段, 不然下次 session 会忘.
- [调研后立刻归档 transcripts](feedback_archive_research_transcripts.md) — ≥3 agent 跑完立刻 cp Temp→docs/research/ + 同步 INDEX.md 按 Round 分段 + 保原名, 别等会丢.
- [调研价值用 ROI 算](feedback_research_roi_metric.md) — 节约时间÷调研时间, 金矿计数器易被门槛漂移操纵.
- [solver 参数金矿必须核实源码](feedback_verify_solver_param_claims.md) — 进 P0/P1 前读 .cc/.proto/paper 否则负 ROI (11/11 翻盘). 新增填 ROI provenance; "X 件套" claim 自动 audit.
- [vendor refresh 后跑全 pytest](feedback_full_pytest_after_vendor_refresh.md) — pre-commit 只测 86 子集不算数, 全套 2086 才抓 vendor 漏改. 同适用依赖升级/canonical 改/fixture 重构.
- [放开手脚但是要记得审查](feedback_autopilot_with_review_gate.md) — autopilot 升级到 src 改动+commit 级别; 每次必须走审查闭环 (preflight + pytest + 自审).
- [大表+1min心跳+自删工作流 (部分废弃)](feedback_autonomous_loop_workflow.md) — 用户离开前指令模板. **心跳 hook 已移除 (959b6de), settings.json hooks 空**; 仅用户明确再下"设 1min 心跳"才适用.
- [长任务一律 background 模式](feedback_long_op_background_mode.md) — spawn Agent/Bash 长跑默认 run_in_background:true, 保 prompt cache TTL.
- [/goal 不要 sleep loop 阻 hook](feedback_no_sleep_loop_for_goal_hook.md) — 烧 5h CPU 拖时间用户嫌烦; 接受 hook fires, 每 turn 做一件 real action 或 honest status.
- [多进程 hang 必须全 worker py-spy](feedback_multiprocess_hang_inspect_all.md) — 之前 168h "IPC bug" hypothesis 是只 py-spy main 没看 worker 的误判.
- [shell wait wrapper pgrep 自匹配 bug](feedback_shell_wrapper_pgrep_self_match.md) — wait wrapper cmdline 含搜索 pattern 会永远 pgrep 到自己; 用 wait $PID / pgrep -x / grep -v $$ 防.
- [项目整理: 不丢东西 + 清晰](feedback_cleanup_preserve_clarify.md) — 重组/加文档/加索引 OK, **删任何文件不 OK** (HiGHS PoC/Codex archive/phase3b 全留). 每动一个 commit 一次.
- [审查策略树](project_review_strategy.md) — 3 层审查: preflight gate → 自主语义审查 → 每日 ultrareview.

## 项目主线进度

- [Endfield 求解器项目 (身份根)](project_endfield_solver.md) — 终末地 70×70 工业规划器精确求解器身份根 (稳定身份+PROJECT_LOCK+依赖). 现状不在本条见交接条. 范式已转 cut-family LBBD.
- [用户画像](user_profile.md) — 终末地玩家+开发者, 中文沟通, 偏好自动化.
- [Phase 0+A 集成层 CLOSE, Phase 1 GO](project_phase0_b_prep_progress.md) — 32 commit + 26 round Gemini cross-check 收尾. 9 family + cut_lifecycle v3.2.2 + 5 fixture + 8 invariant. Phase 1 GO.
- [Phase 1.1 GO blessed (5 轮 deliverable)](project_phase_1_1_go_blessed.md) — 5 轮 R1-R5 deliverable 落地, 172→189 cuts pass, radon A. R5 verdict: 1.1 gate 正式通过, 可进 P1.2B-F5.
- [Phase 3B 进度 (历史)](project_phase3b_progress.md) — S0-S18 阶段执行追踪 (早期 tuning paradigm, 已被 cut-family LBBD 取代).
- [Phase 3C 路线图 v1](project_phase3c_roadmap.md) — 22 个 P0/P1/P2 项 + 12 个 Excluded, 按 ROI 分级. roadmap 在 docs/phase3c_optimization_roadmap_v1.md.
- [Phase 3A IP delivery README 待清理](project_phase3a_ip_delivery_readme_cleanup.md) — r20260416 已冻结但 README 第一屏还推它; audit 工具 .artifacts baseline 漏洞; 核心完工后改 README.
- [SMT-MT outer pruning Phase 0 ✅ GO](project_smt_mt_outer_pruning_phase0_go.md) — R-tree monotone containment 剪枝 outer candidate. **项目第一个 GO**: prune 76.7% + RSS 0.43 GB. Dummy Inner mock.
- [SMT-MT Phase 1 ⚠️ marginal](project_smt_mt_phase1_marginal.md) — Phase 1 trial 比 mock 弱 100x: 真 inner UNPROVEN 不触发 sound prune 是 root cause. land env-gated default off, 等 B engine unlock.
- [Cand C Phase 0 ✅ GO (历史)](project_cand_c_column_generation_phase0_go.md) — cand C 20-inst 8/8 GO, 唯一真换 master basis. (详 paradigm-death-timeline)
- [Cand C Phase 1 ✅ 4-ramp GO (历史)](project_cand_c_phase1_go.md) — 5/20/40/80 inst 全 GO. **Phase 2 路线图已 superseded** (Phase 2 v3 160/266 INFEASIBLE Class E, 主线转 B-design). (详 linked file)
- [项目说明 docs/项目说明/ 21 sub-doc](reference_docs_project_spec_folder.md) — 拆顶层 21 sub-doc 中等粒度 + README 索引 + 受众分流. 旧 plan+math 留 redirect stub.

## paradigm 死路 verdict (历史)

> 详情各 linked file; 整合见 [[paradigm-death-timeline-27-lever]]。

- [Paradigm death timeline (27 lever)](project_paradigm_death_timeline_27_lever.md) — 27 lever 合并: 5 类死法 + 4 共同 root cause + B 5 unsolved. cross-check 前必带.
- [latency-bound 非 bandwidth-bound](project_workload_latency_bound_not_bandwidth.md) — BCP 指针追逐 + 280K pose L3 spill. **别再提带宽/多通道**.
- [硬件状态 (已扩展)](project_hardware_constraint_single_machine.md) — 2026-05-08 起主机+1远程 (WAN), 分布式仅 WAN-适配模式.
- [P2 #14 dumper 路径 已解锁](project_p2_14_dumper_path_blocked.md) — 真因是 master 嵌套 CP-SAT 无 timeout 无限 hang, 2915d6f 修.
- [P1 #24 4-parallel 撞 OOM](project_p1_24_oom_blocked.md) — 9 min OOM 退; 软优化全死; 硬件方向排除.
- [30GB 大头是 propagation buffer](project_30gb_real_culprit_power_coverage.md) — 8 worker × propagation; workers=1 plateau 12.78 GB.
- [HiGHS 重写硬瓶颈](project_highs_rewrite_blocker.md) — 加 power_coverage 后 42 GB > OR-Tools 30 GB; LP-MIP 不适 dense linear.
- [重写路径全穷尽](project_rewrite_path_exhausted.md) — 单机 48GB + 准确性必保, 决定性收益物理不可达.
- [换 Rust 不解决 (瓶颈非内存安全)](feedback_no_rust_rewrite_correctness_not_safety.md) — Rust 治内存安全, 但 30 轮 finding 全是校验逻辑/文档/数学类, 真热点在 CP-SAT C++ 核; 换 Rust 求解层零收益 + 清空 soundness 硬化. 真减审查轮数靠语言无关的单一来源+共享 SoT.
- [RAM 优化跑偏 (历史)](project_2026_05_15_ram_session_misdirected.md) — worker 8→1 让 master 30→12 GB 但 51 cand 全 UNKNOWN; 真瓶颈 master 解不动.
- [5-16 session 终态](project_2026_05_16_session_final_state.md) — GPT 三连死 (v8/v10/L14) + 12 lever. v9 SHA 79b5d1d7.
- [5-17 session 终态](project_2026_05_17_session_terminal_state.md) — L15+L16 ❌ + 用户走 B1. 14 lever.
- [v4 follow-up land](project_v4_followup_landed_next_main_line.md) — 8 commit + ruff/mypy; 接 P1#24/#12/#7.
- [v7 review 包 + final state](project_v7_review_package_landed.md) — 12 cleanup + v7 9.4MB. **superseded [[v8-anchor-slicing-dead]]**.
- [v8 anchor slicing 死路](project_v8_anchor_slicing_dead.md) — build -92% 真但单 anchor 5min UNKNOWN 同 quality. **L12 ❌**.
- [v10 witness preflight ❌](project_v10_witness_preflight_dead.md) — sound 但前提错 (blueprint 缺 41 mandatory). **L13 ❌**.
- [L14 weighted occupancy ❌](project_l14_weighted_occupancy_dead.md) — interior LP=1.000 永不可 cert. **L14 ❌**.
- [L15 set-packing prover 死路](project_l15_setpacking_prover_dead.md) — 核心 CP-SAT 几秒搞定, 真瓶颈 master 多余约束. **L15 ❌**.
- [L16 Lazy Power 死路](project_l16_lazy_power_completion_phase0.md) — master PASS 81.8s 但 cut 端不收敛. **L16 ❌**.
- [B1 pose-bool master 计划](project_b1_pose_bool_master_rewrite_plan.md) — 27×15 interior 7.2s FEASIBLE vs coord 30min UNKNOWN.
- [B1 Phase 0 GO](project_b1_phase0_go.md) — 5 anchor 49-53s OPTIMAL.
- [B1 Phase 1](project_b1_phase1_findings.md) — master 52.9s OPTIMAL + binding 0.0s 端到端 PASS.
- [B1 Phase 2 land](project_b1_phase2_production_land.md) — PoseBoolExactMasterDelegate + env EXACT_USE_POSE_BOOL_MASTER.
- [B1 Phase 3 LBBD wiring](project_b1_phase3_lbbd_land.md) — pose-bool master 接 outer search + LBBD 跑通.
- [B1 Phase 4 routing 🟡](project_b1_phase4_routing_convergence.md) — routing precheck front_blocked ~500-610 ports.
- [B1 Phase 5 cell cut](project_b1_phase5_cell_cut_findings.md) — 3 种 cell-cut 全 over-restrictive.
- [B1 Phase 6 plan](project_b1_phase6_plan_port_active.md) — path-1 master/binding port-selection 决策提升.
- [B1 Phase 6 audit](project_b1_phase6_audit_finding.md) — 否定 storage box 唯一 over-restriction.
- [B1 Phase 6 path-1 死路](project_b1_phase6_path1_dead.md) — master 持 port-selection 4 form 全死. 架构层不可解.
- [B1 Phase 6 path-2 死路](project_b1_phase6_path2_dead.md) — lazy demand cut UNPROVEN 778s 不收敛. B1 全死. 16 lever.
- [5-18→19 paradigm 终态](project_paradigm_session_2026_05_18_19.md) — 19 lever 死 + PCR-CUT Phase 0 GO. Path 12/13/14.
- [PCR-CUT Phase 1 pickup](project_pcr_cut_phase1_pickup.md) — Phase 0 commit 24ed7d8. superseded [[pcr-cut-phase5-verdict]].
- [PCR-CUT Phase 5 🟡](project_pcr_cut_phase5_verdict.md) — Phase 0-4 GO, Phase 5 multi-anchor 0/8 CERTIFIED.
- [PGW-UB Phase 0 ❌](project_pgw_phase0_verdict.md) — positive witness + UB closure, locality 不足.
- [GOC-C2 Phase 0 ❌](project_goc_phase0_verdict.md) — 全图 owner-optional, RSS 25 GB > 12 GB cap.
- [D2 Path 17 verdict](project_d2_path17_verdict.md) — commodity cell-flow + arc, Phase 2 multi 死.
- [Augmented master D pickup (superseded)](project_augmented_master_candidate_d_pickup.md) — superseded [[lever24-augmented-master-dead]].
- [Lever 24 augmented master ❌](project_lever24_augmented_master_dead.md) — 603.9s UNKNOWN + RSS 32 GB. pose-bool scale 死.
- [Path 18 layout-invariant cert ❌](project_path18_layout_invariant_cert_dead.md) — m1=2 ≪ ≥100 target, cut lift 不跨数量级. **25 lever**.
- [Lever 26 Benders symm ❌](project_lever26_benders_symmetry_dead.md) — m5=1.0 全 trivial orbit, symmetry 被 ghost/boundary 杀.
- [Lever 25 IHS ❌](project_lever25_ihs_dead.md) — IHS Phase 0 core size=1 全退化. **27 lever**.
- [GPT v13 cut language thesis](project_gpt_v13_cut_language_thesis.md) — 换 cut 语言不是换 solver. 已超 — 见 [[phase0-b-prep-progress]].
- [GPT anchor slicing 方案](project_gpt_anchor_slicing_proposal.md) — ghost-anchor disjunctive 拆 N anchor; sound 但 RAM 未验.
- [D 第 1 步交 GPT-5.5 Pro](project_d_step1_gpt_handoff.md) — wine input-sim fail, OCR 85% 不够, 69MB zip 交多模态.
- [D step 2 blueprint converter (superseded)](project_d_step2_blueprint_converter_state.md) — 用户手调验证版 blueprint.
- [D step 2 hint integration](project_d_step2_hint_landed.md) — blueprint hint A 路径死, master inherent 难解非 hint failure.
- [benders_loop.py mypy 8 错](project_benders_loop_mypy_followup.md) — G4 全清进 gate (fe83c41).

## reference (硬件 / config / spec)

- [待机功耗 100+W → host 调优全 revert](reference_idle_power_hwp_boost_toggle.md) — idle 100W 真凶 = cmdline `idle=poll + max_cstate=0 + isolcpus`. 全 revert 工序 + 正式前 re-enable 命令. cmdline 重启生效.
- [.claude.json 自动备份 (外盘 daily)](reference_claude_config_backup.md) — ⚠️ 不要 `echo '{}' > ~/.claude.json`; 外盘备份位置 + systemd timer + 恢复命令 + 防 ENOSPC 覆盖事故硬警告.
- [CachyOS 主机环境配置](reference_cachyos_paste_and_nm.md) — wl-clipboard 装了 (Ctrl+V 贴图); NM 探测换 qualcomm.cn; zhuran24 全局 NOPASSWD sudo.
- [CP-SAT 不支持 AddLazyConstraint](reference_cp_sat_no_add_lazy_constraint.md) — OR-Tools 9.15 Python 无此 API. 必走 LBBD 外循环 (solve → verify → cut → rebuild/resolve).
- [F9 area-only invariant (PROJECT_LOCK 锁)](reference_f9_area_only_not_density.md) — F9 generator 只接受 area_capacity_overflow, 拒 routing/binding/pcr. Evaluator 必 area-based. 严格 > 才 cut.
- [IP v2 蓝图 LP 建模规则](reference_ip_v2_blueprint_lp_modeling.md) — 外部源只有矿石 (硬白名单), unloader/storager 是内部 routing 不是源; 采种机 1→2 倍增. (annotate 脚本未进 git)
- [GitHub 实时备份](reference_github_backup.md) — 当前发布目标为 zhuran24/zmd；使用 GitHub 上传包或普通 git push 推分支，不再假设旧 post-commit auto-push。memory 改后必须保持 `cc_context/memory/` 与 `_cc_live_memory/` 镜像一致；不要随意翻 public。
- [Windows/PowerShell/harness 踩坑](reference_windows_powershell_harness_pitfalls.md) — Remove-Item -Recurse 被护栏 BLOCK / here-string 展开 $env 坏脚本 / 进程 cwd 锁目录 / 控制台中文乱码≠文件坏 / 后台 Agent 不稳要 Workflow resume.
