> 2026-06-10 记忆树瘦身:73 条老记忆(老进度快照 / 死路单条 verdict / 已废除的打包审查规则)备份在 `cc_context/memory_archive/`(单份,不双镜像)。需要历史细节去那里翻;本索引只留活记忆。

## 当前状态 / 交接

- [交接 Windows + V80 外发进行中 (单一 living 现状源)](handoff_windows_ninth_review_pending.md) — **当前 phase/状态权威源, 现状只信这条**;2026-06-10 深夜: V80 范式翻转三件套已委托 GPT Pro 实现 (终末地 Project 跑着), 等交付后本地 apply+复验+推锚;当前审查锚 v79;V50 手动 owner-count gate 不变。
- [zmd 项目入口指针 (新会话先读顺序)](zmd-project-entry.md) — 项目记忆体系在哪/接手读文件顺序/双写规矩;指向 _cc_live_memory/handoff 为单一现状源
- [zmd Windows checkout 环境事实](zmd-checkout-env.md) — 无 venv 用全局 Python 3.13.13;commit 即 auto-push 且 CI preflight gate;candidate_placements 外置
- [P1.3A design phase (N=8 merger)](project_p1_3a_design_phase.md) — 设计记录: LBBD loop 已存在只缺 step_8 桥; F1-only; cut 强形式 vs nogood 头号决策; 等 owner phase-boundary 决策.
- [Windows 接手环境 (稳定 reference)](project_windows_handoff_env.md) — 路径/venv/能力边界、slug、prod-scale 回 Linux 主机;稳定环境细节只看该条。
- [记忆现状防过时协议](feedback_memory_currency_protocol.md) — 身份vs现状分离 + 单一 living 现状源 + phase 转换更新仪式 + transient 断言带日期 + 仓库相对路径.
- [记忆树 publish-safety/currentness gate](project_memory_tree_publish_safety.md) — secret scan、repo-native INSTANCE check、memory graph/index/live-mirror gate; 旧 key 需 owner 侧轮换。
- [项目知识树架构](project_knowledge_tree_architecture.md) — 逻辑单树/物理双树: docs=稳定项目表达, memory=协作连续性; living claim 走 subject/projection。
- [数字单一来源架构 (core-node+投影+强制函数)](project_authoritative_numbers_single_source.md) — 项目数字 + cut-family SoT 的主体/投影/强制函数经验;教训: 强制函数 > 规则。

## 外发 GPT Pro (2026-06-10 起的轻量规则, 老审查/打包规范已废除并归档)

- [任务外发 GPT Pro 通道 (权威条目)](feedback_agent_vs_workflow_dispatch.md) — **非必要不用 Workflow**; 审查/实现类任务经 Chrome 插件发 chatgpt.com「终末地」Project, 模型 Pro·进阶 (=GPT Pro 扩展模式); **非必要不用老窗口** (默认新会话); **打包 = 除缓存文件外全项目打** (build 脚本 cc_context/review/build_v80_*.py); 上传走剪贴板。
- [非必要不用 Workflow (GPT 外审裁决)](no-workflow-use-chrome-gpt-review.md) — 发送三条设置+打包规则+首选自动化脚本(gpt_dispatch)+Pro 降级判据+插件托底上传姿势;老审查规范已废除
- [GPT prompt 不要催眠前缀](feedback_no_role_priming_for_reasoning_models.md) — "你是 X 专家" role-priming 对推理模型反作用; 直接讲任务 + format + 约束.
- [Gemini 3.1 pro 数学 consultant](reference_gemini_math_consultant.md) — 数学 second opinion;key 不进 repo/memory, 只读 `GEMINI_API_KEY`。
- [Gemini 自然口吻写作更靠谱](feedback_gemini_better_at_natural_tone.md) — 给外部 reader 的长 narrative 默认 Gemini fat-context 写, Claude review 细节修.

## 工作流 / 协作偏好

- [验证类任务必派独立 backstop](feedback_verification_independent_backstop.md) — 验证/核对/查全类不只信 main 自审; 独立子代理直接查被验对象本身, re-audit 不降 scope.
- [N=1 别当因果 (先排随机)](feedback_no_causal_claim_from_n1.md) — 单次观察编干净因果当事实=反复犯的病; 要定因须对照重复.
- [改 memory 前先过方案](feedback_memory_edit_confirmation.md) — 机械安全小改直接做; 结构性大改先给用户确认.
- [记忆树结构健康](feedback_memory_tree_structural_health.md) — wikilink 命名统一才解析 + MEMORY.md ~24576B 超了尾部静默截断 + harness 重写 frontmatter 保 name.
- [设计阶段 N 路并行子代理](feedback_design_phase_n_parallel_agents.md) — 代码设计阶段 N 路子代理各带不同 slant, main 当 merger; 补 RLHF bias. (Workflow 裁决后仅"确实必要"时用)
- [闭环任务直接 spawn sub-agent](feedback_subagent_for_closed_loop_tasks.md) — 独立闭环 + 不需中途决策 + 可验证的中等粒度活直接 spawn opus background, 不问 user.
- [Phase boundary 两镜像偏见](feedback_main_merger_scope_creep_bias.md) — 会往大扩或往小缩; **User 是唯一可信 phase boundary auditor**.
- [paradigm Phase 0 cheap gate workflow](feedback_paradigm_phase0_cheap_gate.md) — 新 paradigm 实施前必走 Phase 0 (≤1h cheap gate) 验前提, GO 后再投 Phase 1.
- [plan doc 不是 TODO list, 必含战略层](feedback_plan_doc_strategic_layers.md) — plan doc 必含战略/数学原理/paradigm/历史/GO 标准/依赖图/风险/回滚.
- [proof object 必须 6 步 lifecycle 闭环](feedback_proof_object_lifecycle.md) — generate→…→replay→regression; schema landed ≠ runtime correct.
- [不回复 = 默认同意我的倾向](feedback_no_reply_means_agree.md) — 提了 stated preference 的问题 user 不回 → 默认同意直接推进. 不可逆/高 stakes 例外.
- [懒狗模式 — 替用户想](feedback_lazy_mode.md) — 认同"无谓盖章=浪费用户"; 想替他省事自然不问.
- [直接讲核心 finding](feedback_directly_state_core_finding.md) — 第一句给结论+真问题定位. 不准先列 A/B/C 选项让用户选.
- [清晰 > 简短 (沟通)](feedback_clarity_over_brevity.md) — 用人话 = 展开术语+场景+why+代价, 不是缩短.
- [别把我的项目全局视野投射到用户](feedback_dont_project_project_visibility.md) — 讲理由前先从零搭共同词汇.
- [不准列放弃选项](feedback_no_giveup_options.md) — 除非 formal proof 证明不行.
- [不要给暂停/休息建议](feedback_no_rest_suggestions.md) — 用户自己知道何时该休息.
- [代码注释别切到工程化语气](feedback_code_comments_plain.md) — 只在 why 非显然处留一句人话.
- [优化必须 stack 所有方案](feedback_optimization_strategy.md) — 不按 ROI 单选, 全上是唯一选择.
- [不要进 micro-optimization 螺旋](feedback_avoid_micro_optimization_spiral.md) — 占比 <5% 就停手换方向.
- [工时按 Claude 节奏估](feedback_work_time_estimates.md) — 不按人类工程师"安全 buffer"打底, 多数任务分钟级.
- [运维脚本写完存入口](feedback_record_tool_entry_points.md) — refresh/sync 脚本写完立刻在 CLAUDE.md 加 runbook 段.
- [调研后立刻归档 transcripts](feedback_archive_research_transcripts.md) — ≥3 agent 跑完立刻 cp Temp→docs/research/ + 同步 INDEX.md.
- [调研价值用 ROI 算](feedback_research_roi_metric.md) — 节约时间÷调研时间.
- [solver 参数金矿必须核实源码](feedback_verify_solver_param_claims.md) — 进 P0/P1 前读 .cc/.proto/paper 否则负 ROI (11/11 翻盘).
- [vendor refresh 后跑全 pytest](feedback_full_pytest_after_vendor_refresh.md) — pre-commit 子集不算数, 全套才抓 vendor 漏改.
- [放开手脚但是要记得审查](feedback_autopilot_with_review_gate.md) — autopilot 升级到 src 改动+commit 级别; 每次必须走审查闭环 (preflight + pytest + 自审).
- [大表+1min心跳+自删工作流 (部分废弃)](feedback_autonomous_loop_workflow.md) — 心跳 hook 已移除; 仅用户明确再下"设 1min 心跳"才适用.
- [长任务一律 background 模式](feedback_long_op_background_mode.md) — 长跑默认 run_in_background:true.
- [/goal 不要 sleep loop 阻 hook](feedback_no_sleep_loop_for_goal_hook.md) — 每 turn 做一件 real action 或 honest status.
- [多进程 hang 必须全 worker py-spy](feedback_multiprocess_hang_inspect_all.md) — 只看 main 不看 worker 会误判.
- [shell wait wrapper pgrep 自匹配 bug](feedback_shell_wrapper_pgrep_self_match.md) — 用 wait $PID / pgrep -x / grep -v $$ 防.
- [项目整理: 不丢东西 + 清晰](feedback_cleanup_preserve_clarify.md) — 重组/加文档/加索引 OK, **删任何文件不 OK** (归档=移动不是删). 每动一个 commit 一次.

## 项目主线

- [Endfield 求解器项目 (身份根)](project_endfield_solver.md) — 终末地 70×70 工业规划器精确求解器身份根 (稳定身份+PROJECT_LOCK+依赖). 现状见交接条. 范式 = cut-family LBBD.
- [用户画像](user_profile.md) — 终末地玩家+开发者, 中文沟通, 偏好自动化.
- [Phase 3C 路线图 v1](project_phase3c_roadmap.md) — 22 个 P0/P1/P2 项 + 12 个 Excluded, 按 ROI 分级.
- [项目说明 docs/项目说明/ 21 sub-doc](reference_docs_project_spec_folder.md) — 拆顶层 21 sub-doc + README 索引 + 受众分流.

## 死路总表 + 硬件边界 (单条细节在 memory_archive)

- [Paradigm death timeline (27 lever)](project_paradigm_death_timeline_27_lever.md) — 27 lever 合并: 5 类死法 + 4 共同 root cause. **新方案 cross-check 前必带**; 各 lever 单条已归档.
- [latency-bound 非 bandwidth-bound](project_workload_latency_bound_not_bandwidth.md) — BCP 指针追逐 + 280K pose L3 spill. **别再提带宽/多通道**.
- [硬件状态 (已扩展)](project_hardware_constraint_single_machine.md) — 主机+1远程 (WAN), 分布式仅 WAN-适配模式.
- [换 Rust 不解决 (瓶颈非内存安全)](feedback_no_rust_rewrite_correctness_not_safety.md) — 真热点在 CP-SAT C++ 核; 换语言零收益.

## reference (硬件 / config / spec)

- [待机功耗 100+W → host 调优全 revert](reference_idle_power_hwp_boost_toggle.md) — idle 100W 真凶 = cmdline; 全 revert 工序 + 正式前 re-enable 命令.
- [.claude.json 自动备份 (外盘 daily)](reference_claude_config_backup.md) — ⚠️ 不要 `echo '{}' > ~/.claude.json`; 外盘备份位置 + 恢复命令.
- [CachyOS 主机环境配置](reference_cachyos_paste_and_nm.md) — wl-clipboard; NM 探测换 qualcomm.cn; NOPASSWD sudo.
- [CP-SAT 不支持 AddLazyConstraint](reference_cp_sat_no_add_lazy_constraint.md) — OR-Tools 9.15 Python 无此 API. 必走 LBBD 外循环.
- [F9 area-only invariant (PROJECT_LOCK 锁)](reference_f9_area_only_not_density.md) — F9 generator 只接受 area_capacity_overflow. 严格 > 才 cut.
- [IP v2 蓝图 LP 建模规则](reference_ip_v2_blueprint_lp_modeling.md) — 外部源只有矿石 (硬白名单); 采种机 1→2 倍增.
- [GitHub 实时备份](reference_github_backup.md) — 发布目标 zhuran24/zmd;memory 改后必须保持 `cc_context/memory/` 与 `_cc_live_memory/` 镜像一致.
- [Windows/PowerShell/harness 踩坑](reference_windows_powershell_harness_pitfalls.md) — Remove-Item -Recurse 被护栏 BLOCK (批量删/移挪到 Bash 工具做) / here-string 展开 $env 坏脚本 / 控制台中文乱码≠文件坏.
