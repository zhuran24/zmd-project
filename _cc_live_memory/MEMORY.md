> 2026-06-10 记忆树瘦身:73 条老记忆(老进度快照 / 死路单条 verdict / 已废除的打包审查规则)备份在 `cc_context/memory_archive/`(单份,不双镜像)。需要历史细节去那里翻;本索引只留活记忆。

## 抽象事实层 (normalize: fact → projection)

> 投影节点只回指这里的事实,不要把抽象事实再复刻成新原子。每个 fact 在 MEMORY.md 直接覆盖,避免父索引传递覆盖失效。
- [决策边界=能力](fact_decision_boundary_is_ability.md) — 能不能问 owner 看我能不能自己做/定; 目标/先例/放开开关=授权
- [先理解再产出](fact_understand_before_output.md) — 默认病是抢可见反应,正确顺序是先读懂意图+根因
- [证据先于叙事](fact_evidence_before_story.md) — N=1/终态/重试不定因; 明确数字/规则优先
- [自报不算证据](fact_self_report_is_not_evidence.md) — 自验摘要/metadata/单次结果不裸信,靠独立复现和端到端验收
- [零 finding 不是 proof](fact_zero_finding_is_not_proof.md) — 审查只能证有问题; 闭合靠独立对拍/fuzz/proof/多轮计数
- [强制函数优先](fact_forcing_function_required.md) — 复发行为/漂移靠 hook/test/gate/stamp,规则只做 fallback
- [会话状态局部](fact_conversation_state_is_window_local.md) — 新会话不带隐式记忆; 新任务隔离与 opsec 都按显式材料算

## 当前状态 / 交接

- [交接 Windows + 过夜审查循环 ACTIVE (单一 living 现状源)](handoff_windows_ninth_review_pending.md) — **当前 phase/状态权威源, 现状只信这条** (读法: 正文 stamp 编号最大的块 = 最新现状; 逐面轮次史以台账 cc_context/review/p1_2_closure_evidence.md 为准, 本行不手抄易漂数值);V50 手动 owner-count gate 不变。
- [zmd 项目入口指针 (新会话先读顺序)](zmd-project-entry.md) — 项目记忆体系在哪/接手读文件顺序/双写规矩;指向 _cc_live_memory/handoff 为单一现状源
- [zmd Windows checkout 环境事实索引](zmd-checkout-env.md) — 当前 Windows checkout 环境事实索引;无 venv/Python/auto-push/pytest/CI/记忆同步等子主题见各子节点
- [zmd-env 工作区路径](zmd-env-checkout-location.md) — C:\claude pj\zmd_pj 是轻量 GitHub checkout(zhuran24/zmd,分支 project-foundation);旧 D:\追光\zmd 已不存在,记忆里 D 盘路径全失效
- [zmd-env 用哪个 Python](zmd-env-python.md) — 无 .venv;主环境=C:\Program Files\Python313\ 的 python.org 3.13.14(`python`);依赖 --no-deps 克隆(litellm 钉 jsonschema 必须 --no-deps);商店版 python3.13 备份
- [zmd-env 商店 Python alias 坑](zmd-env-store-python-alias-pitfall.md) — 商店 Store Python 半夜自动升级弄坏 `python` alias(静默失败 exit 49/9009 会话中途挂),python3.13.exe 是好的;alias 坏时 pre-commit 误报 STALE 先用 python3.13 复核
- [zmd-env exit code 假通过坑](zmd-env-exit-code-falsepass.md) — PowerShell `& venv\python xxx; Write-Host exit:$LASTEXITCODE` venv 不存在时 & 失败但 Write-Host 把整条洗成 exit 0;判断脚本通过必须看脚本自身输出不能只看 exit code
- [zmd-env post-commit 自动 push](zmd-env-auto-push.md) — post-commit hook 自动 push GitHub(commit ≈ 发布到远程),提交前想清楚;推送历史在 .git/auto-push.log
- [zmd-env 记忆 sync 现状](zmd-env-memory-sync.md) — pre-commit memory sync 只 auto-stamp handoff INSTANCE 槽,整目录镜像覆盖块已移除别加回(会用 harness 十几条覆盖 cc_context 几十条=删数据);共维护文件改动靠手动双写三处
- [zmd-env candidate_placements](zmd-env-candidate-placements.md) — certified exact 必需输入已就位且随时可再生(本地 45,773,799B sha adcc2a6e,.gitignore 防误推);丢了用 placement_generator.py 现场再生 ~3s;旧版/zmd.7z 老归档带病不可作恢复源
- [zmd-env 补丁包/ 目录](zmd-env-patch-dir.md) — 仓库根 补丁包/ = Codex 接手期 v29→v78 外审包/补丁存放处,zip/7z 被 gitignore;最近补丁审查情况.txt 是 0 字节空文件
- [zmd-env pytest 独占跑](zmd-env-pytest-isolation.md) — 全量 pytest 必须独占(pytest.ini --basetemp=.pytest_tmp 在仓库根,多进程并发互删→Windows 随机 FileExistsError);加速跑法 xdist 8 worker -n8+独立 basetemp ~85s
- [zmd-env 测试基线全绿](zmd-env-test-baseline.md) — 全量测试基线=全绿(2026-06-12 wireless 修复 fbb0466 起项目史上首次)0 failed/74 skipped;passed 数以台账 p1_2_closure_evidence.md+handoff stamp 为准;旧 20 个环境失败清单作废,今后任何 failed 都是真问题无豁免
- [zmd-env CI gate](zmd-env-ci-gate.md) — CI=GitHub Actions project-foundation gate,每次 push 跑 preflight_gate.py --ci(17 项)失败给 owner 发邮件;落地前必本地跑同款全绿;pytest 盖不到三类:frozen-artifact hash/LF 行尾政策/记忆树死链
- [zmd-env 邮件轰炸根因](zmd-env-email-bomb.md) — 归档 GPT 审查 probe 带 ruff error 入库→连续 push 连红每红一封;三层教训:gate ruff 扫全仓含 cc_context 入库前必 ruff check、纯文档/归档 commit 不豁免 preflight、push 后 gh run list -L 1 回看
- [zmd-env pre-push 机械门禁](zmd-env-prepush-gate.md) — .git/hooks/pre-push(机器专属不入库)强制跑 preflight_gate.py --hook(20 项 ≈20s)BLOCK 就物理挡 push,逃生口 ZMD_SKIP_PUSH_GATE=1;装机坑 PYTEST_ADDOPTS 反斜杠被 shlex 吃掉必 tr 转正斜杠
- [P1.3A design phase (N=8 merger)](project_p1_3a_design_phase.md) — 设计记录: LBBD loop 已存在只缺 step_8 桥; F1-only; cut 强形式 vs nogood 头号决策; 等 owner phase-boundary 决策.
- [Windows 接手环境 (历史快照, 已 superseded)](project_windows_handoff_env.md) — 2026-05-30 初次 Linux→Windows 接手记录;路径/venv/slug 均失效, **当前 Windows 环境现状看 zmd-checkout-env**;仅"prod-scale 回 Linux 主机"能力边界仍有效。
- [记忆现状防过时协议](feedback_memory_currency_protocol.md) — 身份vs现状分离 + 单一 living 现状源 + phase 转换更新仪式 + transient 断言带日期 + 仓库相对路径.
- [记忆树 publish-safety/currentness gate](project_memory_tree_publish_safety.md) — secret scan、repo-native INSTANCE check、memory graph/index/live-mirror gate; 旧 key 需 owner 侧轮换。
- [项目知识树架构](project_knowledge_tree_architecture.md) — 逻辑单树/物理双树: docs=稳定项目表达, memory=协作连续性; living claim 走 subject/projection。
- [数字单一来源架构 (core-node+投影+强制函数)](project_authoritative_numbers_single_source.md) — 项目数字 + cut-family SoT 的主体/投影/强制函数经验;教训: 强制函数 > 规则。

## 外发 GPT Pro (2026-06-10 起的轻量规则, 老审查/打包规范已废除并归档)

- [任务外发 GPT Pro 通道 (权威条目)](feedback_agent_vs_workflow_dispatch.md) — **非必要不用 Workflow**; 审查/实现类任务经 Chrome 插件发 chatgpt.com「终末地」Project, 模型 Pro·进阶 (=GPT Pro 扩展模式); **非必要不用老窗口** (默认新会话); **打包 = 除缓存文件外全项目打** (build 脚本 cc_context/review/build_v80_*.py); 包走 Project 文件页(来源区), 上传/发送已全脚本化 (详见 no-workflow 条目与 CLAUDE.md runbook)。
- [非必要不用 Workflow 外发 GPT 索引](no-workflow-use-chrome-gpt-review.md) — GPT Pro 外发审查/委托主题索引(原巨型节点已拆);具体设置/通道/风控/降级/并发见各子节点
- [核心裁决:外发 GPT Pro](no-gpt-pro-outsource-core.md) — 2026-06-10:非必要不用 Workflow 多代理;审查/外审/委托实现外发 GPT Pro;GPT Pro 沙盒能解包/装离线 wheels/跑 pytest 自验
- [四条发送设置](no-gpt-send-settings.md) — 模型 Pro·进阶 + 终末地 Project + 新会话默认 + 包走 Project 文件页(来源区)不随消息发附件;删旧快照保留依赖包,prompt 指认文件名+sha256
- [打包规则](no-gpt-packaging-rules.md) — 除缓存全打(build_v80_single_win.py);r7 纪律=git worktree 干净树打+复制成 sha 前缀唯一名防并发覆盖+交付前 Get-FileHash 核对;老审查打包规范已全废
- [发送分工+风控处置](no-gpt-dispatch-vs-manual-riskctrl.md) — 单发默认 dispatch 脚本,多路并行/额度紧改手动;疑似风控=无自动托底停一切落盘等 owner;手动发走 clip_send.ps1;dispatch 后台骤死(exit 58)用 --resume 重连
- [通道架构终态](no-gpt-channel-architecture.md) — 2026-06-12 全链路脚本化:dispatch 浏览器层重写 raw page 级 CDP(弃 Playwright fab40a7);upload 铁律只打网页端 Edge 9222 绝不对 App;App 9224 自动 fallback;跑法纪律 Start-Process detached+单后台 bash
- [dispatch 命令+降级判据](no-gpt-dispatch-command-and-downgrade.md) — 首选 dispatch_gpt_task.py --pack --prompt-file;前置 start 脚本 attach 日常 Edge(无端口温和重启 Edge,重启后端口丢需重跑 start);Pro 降级唯一判据=生成耗时(5min 内极大概率降级);托底两层=插件/App 9224
- [插件剪贴板上传姿势](no-gpt-plugin-clipboard-upload.md) — 插件 file_upload 10MB 上限且拒主机路径别用;改走 clip_send.ps1 -Files(必须 DataObject+SetDataObject copy:=true)聚焦输入框 Ctrl+V;长 prompt 同理;sandbox 附件几分钟 404 完成立即收
- [降级机理实证](no-gpt-downgrade-evidence.md) — 24 次交付数据:4 路并发触发 Sentinel 后脚本特征发送降到 40-70s,手动(Edge/App)仍真 Pro;唯一可靠信号=elapsed_s(model_slug/thinking_marker 全撒谎);找客服真证据=时长对比非 HAR sentinel 请求
- [并发上限已字段化](no-gpt-concurrency-field.md) — 2026-06-14 owner 放开:旧"最多 2 条在途"软上限去掉,改由 gpt_dispatch_concurrency.json 的 max_in_flight 控制(null=不限);仍成立护栏=在途未收完别清旧快照、每单一个后台 shell、包走文件区
- [dispatch 0614 大改](no-gpt-dispatch-rewrite-0614.md) — commit 51e5c47/9465731:复用页+不关页(--reuse-tab-id/--no-close)+模型自检自修(verify_model 真开『智能水平』菜单点 Pro 扩展,Radix 要 CDP click_xy)+接收侧 model 复核 exit 5;cargo-cult 铁律=改前理清因果链别凭猜加 workaround
- [workflow vs no-workflow 厘清](no-workflow-scope-clarification.md) — 2026-06-14 owner 纠正:no-workflow 只管「审查/判 soundness 动作本身」外发,不等于所有任务默认单 Agent;准备/调研/编排可 workflow 并行 fan-out;判据看任务实质
- [Workflow 申请≠回避理由](workflow-approval-not-avoidance.md) — 报备=用前说一声不是别用;approval_required=false 该用就用;别因"要申请"退回单代理/手动 (owner 06-13 纠正)
- [GPT prompt 不要催眠前缀](feedback_no_role_priming_for_reasoning_models.md) — "你是 X 专家" role-priming 对推理模型反作用; 直接讲任务 + format + 约束.
- [Gemini 3.1 pro 数学 consultant](reference_gemini_math_consultant.md) — 数学 second opinion;key 不进 repo/memory, 只读 `GEMINI_API_KEY`。
- [Gemini 自然口吻写作更靠谱](feedback_gemini_better_at_natural_tone.md) — 给外部 reader 的长 narrative 默认 Gemini fat-context 写, Claude review 细节修.

## 工作流 / 协作偏好

- [问题不是重点·原因才是重点 (根因优先, 严重级)](root-cause-over-symptom.md) — owner 铁律:遇事找产生问题的原因别停在症状;我反复会错意/请示/不长记性的根因=默认「收到消息就赶产出反应」跳过「先理解意图+根因」
- [任务推进根治系统·维护地图](task-progression-enforcement-system.md) — 注入hook+授权台账+fact层+forcing gate 取代靠自觉的规则;各件位置/设计留档见此 (2026-06-15 落地 35548cc)
- [验证类任务必派独立 backstop](feedback_verification_independent_backstop.md) — 验证/核对/查全类不只信 main 自审; 独立子代理直接查被验对象本身, re-audit 不降 scope.
- [N=1 别当因果 (先排随机)](feedback_no_causal_claim_from_n1.md) — 单次观察编干净因果当事实=反复犯的病; 要定因须对照重复.
- [改 memory 前先过方案](feedback_memory_edit_confirmation.md) — 机械安全小改直接做; 结构性大改先给用户确认.
- [记忆树结构健康](feedback_memory_tree_structural_health.md) — wikilink 命名统一才解析 + MEMORY.md ~24576B 超了尾部静默截断 + harness 重写 frontmatter 保 name.
- [记忆价值尺: 丢了能否重建](feedback_memory_value_yardstick.md) — 该不该记看"丢了能否重建"不是"重不重要"; 重要≠该常驻; 算法知识只存指针不是缺陷; 判断类错靠对抗/自反驳防、成文治不住 (本节点=对抗引信非 forcing 铁律).
- [设计阶段 N 路并行子代理](feedback_design_phase_n_parallel_agents.md) — 代码设计阶段 N 路子代理各带不同 slant, main 当 merger; 补 RLHF bias. (Workflow 裁决后仅"确实必要"时用)
- [设计/创造性开 Team](design-creative-use-team.md) — 设计/创造/开放式任务用 Agents Team 讨论收敛, 不单干也不用纯确定性 Workflow 顶替; 确定性 fan-out/对抗验证才用 Workflow (2026-06-14 owner)
- [闭环任务直接 spawn sub-agent](feedback_subagent_for_closed_loop_tasks.md) — 独立闭环 + 不需中途决策 + 可验证的中等粒度活直接 spawn background, 不问 user.
- [子代理模型按重量派](feedback_subagent_model_by_weight.md) — 轻活 sonnet / 重活 opus / 特别重要 fable; 按具体难度不按任务类别; 取代旧"默认 opus".
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
- [用力程度匹配任务 stakes (治用力过猛)](feedback_effort_matches_stakes.md) — 多代理/对抗/穷尽/backstop 的力度匹配「做错代价×不确定性×规模」不默认拉满; "能更彻底"≠"该更彻底"; 与"别过度保守"是一对(都=匹配实质); Ultracode 是工具非默认; 调节 optimization-stack/verification-backstop 别脱 scope 泛化.
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
- [certified 红线召回锚点 (PROJECT_LOCK §1+§3)](project_certified_redlines.md) — 要动 certified/proof/schema/cut 前先读 lock; 5 条 forbidden + 易撞 invariant + 3 真 P0 反面教材; 召回锚点非 proof 源, 不拓宽 proof 语义.
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
- [graphify 代码语义地图 (query before grep)](reference_graphify_codegraph.md) — src→确定性代码结构图 + Claude 补语义层, 新窗口先查图再 grep; .mcp.json 注册 mcp__graphify__*; graph.json gitignore 需刷新; 只读导航辅助不进 certified 证明路径.
