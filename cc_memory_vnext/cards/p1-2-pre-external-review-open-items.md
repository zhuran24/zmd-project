---
id: p1-2-pre-external-review-open-items
kind: reference
title: P1.2 外审前真实未闭项只两件(归档策略 PARTIAL + 冻结仪式)+ P1.2/P1.3 边界辨析(生产 seal 跑通=P1.3 算力墙、canonical→geometry 骑墙)——2026-07-06 两次 codex 审计厘清
summary: 2026-07-06 owner 问"计划中 P1.2 外审前所有闭合条件都满足了吗",两路 codex 审计(workflow wkmq9z3r8 逐条核 go_criteria/PROJECT_LOCK/roadmap/review_gate 的 close 条件 + wqxdms1hu 核 P1.2/P1.3 边界)后厘清。答案:【不是全满足】。去掉"蓄意内鬼延期桶"([[deliberate-insider-hardening-deferred-to-release]])后,真正还开的**只两件**——**(甲)归档策略完整性 archive policy = PARTIAL,主缺口 2026-07-06 已收窄(`28d9d2c`)**(roadmap:19;非内鬼类、今天延期令明确"照旧"没动它;go_criteria #9/PROJECT_LOCK §C5 要求送审快照满足归档策略——曾是唯一现能推进的真活,已实做主缺口:把两个协作记忆子系统 `cc_memory/`+`cc_memory_vnext/`〔含 owner 私下裁定/内部 gap 地图〕补入打包器排除表+回归、真树 77 路径全 excluded;残余 `paths/`/`.githooks` 去留、secret-scan、obligation-anchor 留冻结那轮);**(乙)"冻结那一轮"仪式**(fresh reseal + 冻结树上重跑 full/slow 留命令/exit/日志证据 + 从冻结树物化不可变送审包;go_criteria #7/#8/#9;现工作树还脏〔并发会话未提交文件〕、HEAD commit 自己写"不触 frozen/reseal"、无绑当前 HEAD 的 full/slow 证据→现在必不满足,等真要外审时走)。**我之前列糙、其实不算 P1.2 外审前项的两个(更正)**:①"无真实生产 campaign→seal 跑通记录"(06_current_status:68)=**P1.3/算力墙**——P1.2 只证"如果有证明就别说谎、不是吞吐定理"(PROJECT_LOCK:164、08_phase_1_2_plan:33 排除纯 UNKNOWN/解不出来),而全尺度求解撞算力硬墙、从未产出过 FEASIBLE("物理上不可达",bottlenecks:1/4;baseline 14h 0 FEASIBLE)、没真 CANDIDATE_PROPOSED 可封;seal **入口存在**=已满足的 P1.2 机器条件,真**产出**全尺度 CERTIFIED 才是 P1.3;②canonical→geometry **骑墙**——字节半(candidate_placements)已由 16495f4 落=P1.2,语义半(F1-F9 cut helper 几何统一)在 step_8 接入前不可测=**P1.3-before-F1-F9**,非 P1.2 外审前 blocker。**P1.2/P1.3 边界一句话**:P1.2=认证管线 soundness(有证明就别说谎、别把 UNKNOWN 当 CERTIFIED),P1.3=master/cut 集成+算力(能不能真解出来)。owner 手动 review 门+close-scope 拍板是外审/关门本身、不算"编码前提"。
scope:
  domains:
    - release-engineering
    - certified-exact
    - pr2
  paths:
    - docs/项目说明/12_go_criteria.md
    - docs/项目说明/soundness_gap_roadmap.md
    - docs/项目说明/06_current_status.md
    - PROJECT_LOCK.md
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - check-p1-2-pre-review-conditions
    - judge-if-item-is-p1-2-pre-review-prereq
    - distinguish-p1-2-vs-p1-3
    - assess-production-seal-run-status
  keywords:
    - P1.2 外审前条件
    - 归档策略 archive policy
    - 冻结仪式 fresh reseal
    - 生产 seal 跑通记录
    - 算力硬墙
    - P1.2 vs P1.3 边界
    - canonical→geometry 骑墙
    - 不是吞吐定理
  negative_keywords: []
  paths:
    - docs/项目说明/12_go_criteria.md
  symbols: []
  error_regex: []
  examples:
    - P1.2 外审前条件都满足了吗 / 还差什么
    - 为什么没有生产 seal 跑通记录 / 它是 P1.2 还是 P1.3
    - canonical→geometry 是 P1.2 还是 P1.3 项
    - P1.2 和 P1.3 到底各管什么
activation:
  layer_hint: L1
  must_know: false
  reason: 问"P1.2 外审前条件满足没/还差什么"、或判某项属 P1.2 还是 P1.3 时该读——记了两次审计厘清的结果:外审前真实只剩归档策略+冻结仪式两件,以及"生产 seal 跑通"(算力墙 P1.3)、"canonical→geometry 语义半"(F1-F9 前置 P1.3)不算 P1.2 外审前项,和 P1.2/P1.3 边界。不读易把 P1.3/算力墙项误当 P1.2 外审前 blocker、或反过来漏掉归档策略这块真活。
provenance:
  op: record
  reason: 2026-07-06 owner 追问"外审前条件是否全满足"+"生产 seal 跑通为何是 P1.3"+"canonical→geometry 定位是否尴尬",两次 codex 审计厘清后固化结果与边界,并更正我此前把两个 P1.3 项列进外审前清单的糙处。
  evidence:
    - "2026-07-06:workflow wkmq9z3r8(2 路:逐条核 close 条件 + 唱反调)总判 overall_can_claim_satisfied=no,树 not-frozen/dirty;真开项=archive policy PARTIAL + 冻结仪式。workflow wqxdms1hu(2 路:P1.2/P1.3 边界 + canonical→geometry 定位)判 seal-run=P1.3 算力墙(P1.2 非吞吐定理,PROJECT_LOCK:164、08_phase_1_2_plan:33;bottlenecks:1/4 物理不可达)、canonical→geometry where_it_sits=straddles(字节半 16495f4=P1.2、语义半 F1-F9=P1.3,step_8 仍 NotImplementedError)。roadmap:21 已按骑墙重标。"
    - "2026-07-06:甲(archive policy)主缺口已实做——`28d9d2c` 把 `cc_memory/`+`cc_memory_vnext/` 补入 `package_review_snapshot.py:PACKAGE_EXCLUDED_PATH_PREFIXES`+扩现有锚定测试断言;目标测试 9 passed、`check_p1_2_proof_obligations` PASS(14 obl/64 sink,子集语义未破)、真树 77 路径全 excluded 零泄漏;二文件无字节 sha 钉→零 reseal。roadmap:19 已更 PARTIAL(主缺口已收窄)。"
  updated_at: "2026-07-06"
---
2026-07-06 owner 追问"计划中 P1.2 外审前所有闭合条件都满足了吗",两路 codex 审计后厘清。**答案:不是全满足。** 记结果 + P1.2/P1.3 边界,并更正我此前把两个 P1.3 项列进外审前清单的糙处。

== P1.2 外审前真实还开的只两件(去掉蓄意内鬼延期桶后)==
- **甲 · 归档策略完整性(archive policy)= PARTIAL,主缺口已收窄**(`soundness_gap_roadmap.md:19`;`go_criteria #9`;`PROJECT_LOCK §C5`)。管的是送审快照里敏感/非审查面覆盖 + 回归。**不是内鬼硬化**,今天那条延期令明确写了"snapshot immutability/archive policy 等常开项照旧"、没延期它。→ 曾是唯一现在就能实做推进的真缺口。**2026-07-06 已实做主缺口(`28d9d2c`)**:审计 `package_review_snapshot.py` 排除表,发现两个持久化协作记忆子系统 `cc_memory/`(pull 型 SQLite 全史,含 owner 私下裁定/内部推理)+ `cc_memory_vnext/`(push 型卡片,含"哪些防御没做"的内部 gap 地图)未被覆盖、会被默认物化进外审包——与已排除的 `.claude/`/`.codex/`/`_cc_live_memory/`/`cc_context/` 同类,漏进排除表;已补入 `PACKAGE_EXCLUDED_PATH_PREFIXES` + 把断言加进**已锚定测试**体(不新增 obligation 名→零 close-kernel reseal;二文件均无字节 sha 钉)。验证:目标测试 9 passed、checker PASS、真树 77 路径全 excluded 零泄漏。**残余(留冻结那轮 owner 拍板,非现在阻塞)**:`paths/` 探索 probe 与 `.githooks/pre-commit` 去留(倾向保留、非敏感)、secret-scan 类内容面(现机制只按路径+prompt 内容嗅探、不扫密钥;**2026-07-06 已只读扫描 tracked 树:无私钥/AWS/token/赋值型密钥→当前无暴露,加扫描器属纵深防御、非现洞**)、把这次新覆盖再 obligation-anchor。
- **乙 · "冻结那一轮"仪式** —— **2026-07-06 owner 说"准备外审了",已完整执行**(`go_criteria #7/#8/#9`;`PROJECT_LOCK §C5`)。冻结树 = `c9b41b3`(工作树干净)。**无需 fresh reseal**:本轮改的两文件(打包器+测试)无字节 sha 钉、B2 那次 `16495f4` 已把树封成一致态,双结构 checker 复跑即证封印完好(proof-obligations 14/64、strong-status 65/83)。在冻结树上跑齐门禁留证据:`--full` 18/18 PASS(fast-pytest **3822 passed** 5:13)、`--slow-tests` **30 passed** 18:33、日志留 `scratchpad/freeze_20260706/`。从冻结树物化不可变送审包:`C:\Users\22957\pr2_pkg\zmd_p1_2_closeout_c9b41b3.7z`(**SHA256 `1296f981…ccab2cd`**,2167 文件、内嵌 selftest+归档完整性+解包复验全过、inventory 0 条 cc_memory/agent 基建=archive 硬化真包生效)。**收口外审提示词**:按 P1.2 soundness 攻击面从零推 **7 切面**(mint 分权/L0 seal/terminal witness/publisher gate/close-kernel+frozen/snapshot 忠实/横切兜漏),workflow `wf_d8decfea-03b`(codex 14 agents 起草+核验)产出,已 QA(entry_5 verify 元评注泄漏已剥、entry_1 补标题)、写 `pr2_pkg\p1_2_closeout_20260706\entry_1..7.md`+`CONTEXT.md`。已按 relay 规程 staged 进剪贴板(Win+V 顶→底=包路径, CONTEXT, entry_1..7,9 条逐条回读验证)。**剩 owner 手动动作**:上传 .7z 到 GPT Pro + 逐会话贴 CONTEXT+entry_i;回传后按 [[review-convergence-tcb-line-not-zero-findings]] 收敛判据(TCB 线上必修/线下算受信/owner 判定合适为止)。

== 我之前列糙、其实不算 P1.2 外审前项的两个(更正)==
- **① "无真实生产 campaign→seal 跑通记录"(`06_current_status:68`)= P1.3/算力墙,不是 P1.2。**
  - P1.2 只证"**如果**手上有合法证明,链会正确封/发、并拒绝不合法的"= soundness;**PROJECT_LOCK:164 明写"不是吞吐定理"**;`08_phase_1_2_plan:33` 把纯 UNKNOWN/TIMEOUT/解不出来排除在 P1.2 外。
  - 全尺度求解**撞算力硬墙**:求解器**从未在全尺度产出过 FEASIBLE**(`bottlenecks:1` 原话"物理上不可达";baseline 14h 0 FEASIBLE)→ **没真 CANDIDATE_PROPOSED 可封**;"链后面 seal/publish/门再完美也没东西可 seal"(`bottlenecks:4`)。
  - seal **入口存在** = 已满足的 P1.2 机器条件;真**产出**一个全尺度 sealed CERTIFIED = P1.3/算力墙(而那墙"唯一没有已知工程路径",可能比 P1.3 待办更深)。
- **② canonical→geometry shared primitives = 骑墙,非 P1.2 外审前 blocker。**
  - 字节半(candidate_placements 字节须等于 canonical 重推)= **P1.2 相关,今天 `16495f4` 已落**。
  - 语义半(把 canonical→几何在 F1-F9 cut helper 间统一;它们各用旧欧氏覆盖模型)= 在 F1-F9 真接进 certified master(`step_8` 仍 NotImplementedError = **P1.3 主体**)之前**不可测/不可做** = **P1.3-before-F1-F9 前置**。`roadmap:21` 已按此重标。

== P1.2 / P1.3 边界(一句话记牢)==
- **P1.2 = 认证管线 soundness**:有证明就别说谎、别把 UNKNOWN 当 CERTIFIED、发布链单入口、owner 手动门。**不要求真把 70×70 解出来。**
- **P1.3 = master/cut 集成 + 算力/吞吐**:step_8 把 F1-F9 接进 master、以及"能不能在全尺度真解出来"。
- owner 手动 review 门 + close-scope 拍板 = 外审/关门本身,不算"编码前提"。

关联:蓄意内鬼延期桶 [[deliberate-insider-hardening-deferred-to-release]];算力墙审计 [[project-bottleneck-audit-20260702-map]];主线收口序 [[p1-2-closeout-then-tcb-backlog-order]];B2 字节 gate [[pr2-5-b2-candidate-geometry-rederivation-landed]]。
