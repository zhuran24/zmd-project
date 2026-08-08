---
id: agent-role-division-and-codex-collaboration
kind: decision
title: 多代理分工——Fable5=数学面负责人(定方向)、Opus leader=发布面负责人+半队长(协调+发布面直做)、实现优先派 codex 省额度;codex 一次性执行任务书 / 矛盾指令按序执行 / 冲突停下澄清 / 改动真实落盘
summary: owner 2026-07-03 定的多代理分工模型 + 同日亲历的 codex 协作特性。**分工**:①**Fable5=数学面负责人**——数学面(routing/CP-SAT/canonical/生成器/loader 这类非对抗)的方向、计划、技术选择由它定,leader 不指挥不干预,最多给"当前情况说明"(leader 去指挥数学面反而拖累负责人);②**Opus leader(我)=发布面负责人+半个队长**——发布面(checker/reseal/close-kernel/外审 triage)直接做,队长那半=协调/派活/跨面编排,但对数学面只协调不指挥;③**具体实现优先派 codex 省额度**,不让负责人亲自写;方向已定的纯实现活直接 codex,只有需要定数学面方向/计划时才请 Fable5 出场、leader 只给情况不插手方向。判据:数学面任务"方向已拍板、纯执行"→ 直接 codex;"要定方向/计划"→ Fable5 定、codex 实现。**codex 协作特性**(2026-07-03 亲历):codex 子代理按**原始任务书一次性执行**,能收中途 SendMessage 但**按到达顺序执行**——发了自相矛盾两条(先"撤 X"后"别撤 X"),它先执行先到的、遇后到冲突时**停下来讲清楚、不默默处理**(很负责);铁律=**派 codex 指令一次写全、别指望中途改**。codex 改动**真实落盘**(别误判成 sandbox 隔离不同步——2026-07-03 我误判过,实为它忠实执行我"撤 T1"指令)。 **[订正 2026-08-08(跨层对账 G-2/3/4/10)：本卡「分工」段路由已整体过时——现行=主线程(Fable 本尊)不亲自实施、实施一律派 opus/wf;codex 额度随用量波动(08-08 刷新后 owner 恢复原始分工:codex 实施主力、opus 审查席,以文件层路由卡现值为准);派 Fable 子代理需 owner 允许(08-07 硬规矩)。权威=文件层 codex-default-delegation-routing / ultracode-fable-spawn-discipline。本卡仍有效部分=codex 协作特性段(任务书一次写全/冲突不默默处理/改动真实落盘)。]**
scope:
  domains:
    - multi-agent
    - orchestration
    - collaboration
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - divide-agent-roles
    - delegate-implementation
    - spawn-codex-subagent
    - assign-math-vs-publish-work
  keywords:
    - 分工
    - 数学面负责人
    - 发布面负责人
    - 半队长
    - Fable5
    - codex
    - 实现优先
    - 省额度
    - 派活
    - 方向
    - 矛盾指令
    - 一次性执行
    - 落盘
    - sandbox
    - 指挥
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 这个数学面小任务派谁做
    - codex 收到我中途改的指令吗
    - 数学面方向该我定还是 Fable5 定
    - 为什么 codex 的改动不见了
activation:
  layer_hint: L1
  must_know: false
  reason: 派数学面/实现活、或派 codex 时该想起——分工搞错(leader 越权指挥数学面方向、或让负责人做纯实现浪费额度)、或对 codex 指令中途改导致矛盾,都是自然会犯的;2026-07-03 当天多次实犯并被 owner 纠正。
provenance:
  op: record
  reason: owner 2026-07-03 明确的多代理分工模型(Fable5=数学面负责人 / 我=发布面负责人+半队长 / 实现优先 codex),及同日 codex 协作特性(矛盾指令按序执行+冲突停下澄清+改动真实落盘)的亲历。
  evidence:
    - "2026-07-03 批次3:owner 纠正'别给 Fable5 当数学面指挥''实现优先 codex 省额度''Fable5 是数学面负责人、你是发布面负责人兼半队长';据此停 Fable5、批次3 纯实现改派 codex。"
    - "2026-07-03 codex-batch3:我先发'撤出 T1'又发'别撤 T1 我要 reseal',codex 按序先撤 T1+提交 T2+T3、遇第二条冲突停下澄清;我一度把 T1 丢失误判为 codex sandbox 不落盘,实为 codex 忠实执行我矛盾指令。"
  updated_at: "2026-07-03"
---
多代理分工模型 + codex 协作特性(owner 2026-07-03 定 + 当天亲历)。

== 分工模型 ==
- **Fable5 = 数学面负责人**:数学面(routing/CP-SAT 建模、canonical 语义、生成器、loader 这类不含对抗性语料的活)的**方向、计划、技术选择**由它定;leader 不指挥、不干预,最多给它"当前情况说明"。理由:leader 去当数学面指挥反而拖累负责人自主发挥。
- **Opus leader(我)= 发布面负责人 + 半个队长**:发布面(checker 硬化、reseal、close-kernel 登记面、外审 triage)直接做(Opus 不被分类器降级);"半队长" = 协调、派活、跨面编排,但**对数学面只协调不指挥**。
- **具体实现优先派 codex 省额度**:不让负责人(Fable5)亲自写实现。方向已定的纯实现活 → 直接 codex;只有需要定数学面方向/计划时才请 Fable5 出场、且 leader 只给情况不插手方向。

== 判据 ==
数学面任务:**方向已拍板、纯执行** → 直接派 codex(省额度);**要定方向/计划** → Fable5 定、codex 实现。凡碰 checker/reseal/对抗性 = 发布面 = leader 自己做(leader=Opus 口径见 [[guardrail-delegate-adversarial-reads]])。

== codex 子代理协作特性(2026-07-03 亲历)==
- **一次性执行任务书**:codex 按你派它时的原始任务书跑;它**能收到**中途 SendMessage,但按**到达顺序执行**。
- **矛盾指令按序执行 + 冲突停下澄清**:我先发"撤出 T1"、后发"别撤 T1 我要基于它 reseal",codex 先执行先到的(撤 T1、提交 T2+T3),遇到后到的冲突时**停下来把冲突讲清楚、不默默处理**(很负责)。→ 铁律:**派 codex 指令一次写全,别指望中途改**;真要改就明确标"以此条为最终"。
- **改动真实落盘**:codex 的文件改动是真的(不是 sandbox 隔离不同步)。2026-07-03 我一度把"T1 改动不见了"误判成 codex sandbox bug,实际是 codex 忠实执行了我"撤 T1"的指令——**别把自己指令的后果甩锅给工具**。

与 [[guardrail-delegate-adversarial-reads]](隔离/降级)、[[agent-longrun-wait-wake-protocol]](teammate 唤醒)同族,一起构成多代理协作基建。

== 更新 2026-07-10（owner 拍板）：审查类活也默认 codex ==
diff 语义审查、修复批独立审查、preflight「改核心文件建议 AI 语义审查」WARN 的响应审查——**以后默认派 codex，不再用 opus**（owner 原话「审查以后也交给codex来」）。战绩背书：2026-07-09 codex 独立审查 C1 patch 在生产 cell 点火前抓出 clone 杆裸奔致命 bug；同日 GPT Pro bug 审的 dedup 段错误雷也是外部模型抓的。opus 审查（如 2026-07-10 硬化批 SEMANTICS_PRESERVED 那次）是该拍板前的最后一次。通道：codex MCP（会话启动时验 `ToolSearch "+codex"`）或 CLI `codex exec --sandbox read-only`（回退，见 cachy 环境卡）。审查提示词纪律照旧走 [[review-prompt-audience-purity]]。

== 更新 2026-07-10 深夜（owner 拍板）：计划书/任务书主会话自己写 ==
三类活的分工判据定稿（owner 推理原话大意：计划书需要先了解背景、且是流程大头，跟审查「必须派另一个模型」、实现「大头在具体工作」都不同）：**①计划书/任务书 = 主会话自己写**——背景理解与方向判断是大头，全在主会话上下文里零成本；外包 codex 则「喂背景的派单提示词本身≈半份计划书」，且它只知道被告知的（2026-07-10 批 1 任务书实例：codex 草稿质量高但四条关键修订全是主会话背景型判断补的）。**②审查 = 必须另一个模型**（codex/GPT Pro，独立性是本质）。**③实现 = codex**（工作量大头，省额度）。

== 更新 2026-07-10（owner 补充）：审查环节按 CC 额度弹性调度 ==
修订上一条「审查一律 codex」：**看当时 CC 额度**——额度多 → **opus 与 codex 双审并行**（暂行观察：若两者耗时差距过大——大概率 codex 更慢——则退为单走 opus）；额度少 → 单走 codex。owner 理由：主会话最后总会复核一遍，此环节「说重要也重要说不重要也不重要」，适合灵活变化。计划书=亲写、实现=codex 两条不变。


### 审查阵容暂时升级 fable+codex(owner 2026-07-10 凌晨,CC 额度刷新期)
owner:「现在wf可以随便派fable了(暂时),那审查就暂时换成fable+codex」——弹性制的「额度多」档从 opus+codex 升级为 **fable+codex**,自 1C 起生效;额度紧张时回落按原弹性制。同期实测背书:gpt-5.6(codex 侧新模型)双 effort 考试大胜——xhigh 抓到 opus/5.5/主会话三方全漏的交叉场景 BUG,ultra 再多抓跨文件交互 bug(nogood 断链)+边角输入(重复 pose_id),零误判;codex 侧默认 xhigh、手术核心批可上 ultra("max 推理+自动任务委托")。

### fable+codex 首战战绩 + GPT-5.6 Pro 复审代差实证(2026-07-10 深夜)
**1C 双审首战(fable+codex)**:两家结论冲突(fable PASS_WITH_NOTES/codex BLOCK),终审裁决 codex 两 BLOCK 全实锤(缺杆模板 fail-closed 漏洞+调用链异常屏障,均附最小复现);fable 零 BLOCK 但侦察极扎实(5 NOTE 全带实验数据:中间层 stub 真剪实验/pinned 工件 4761 pose 统计/checker 静默退 1 定位),其一次性实验被固化为 T14 回归。**互补形态定型:codex 管"往死里挑",fable 管"把现场摸透"**。
**GPT-5.6 Pro vs 5.5 Pro 复审对比(cut framework 同题材同快照)**:5.6 抓到 5.5 的同一 P0(integrity bypass,已被 c7cd6a0 拦)+**两个 5.5 漏掉的可复现问题**(ghost 轴反置 BLOCKER/scope 自删,当前 HEAD 仍复现,修复批规格书 ce6f703 已备)+3 份 RFC+4 补丁,交付形态=完整工程包(SHA256/evidence/repro 脚本/patched 测试日志)。结论:5.6 系对 5.5 系是审查代差,强项=测试盲区型 bug(square 掩盖非方形/组合负例失真),与本地 codex 5.6 在 1B/1C 的表现同向。

### 1D 双审战绩(2026-07-10 上午,fable+codex 第二战)
互补形态再验证:**codex BLOCK=pre-1A checkpoint 恢复路径混搭旧 witness proto**(504 绿测试全没覆盖的恢复×表示交叉场景,第四次「规格盲区靠审查抓」实证;修复=方案 A direct rebuild);**fable=checker needle 连锁 handoff 级预警**(21 项 witness env needle 硬编码会被 S2 打断+旧测试名双 pin——把主会话终审必撞的墙提前拆了)。终审自身又挖出第五/六次盲区(v62 文件族+慢 lane witness 真实工件回归,全量扫描+slow 直跑抓出 16+1 失败,含一个源码级边界缺陷=C1 空 powered 义务撞非矩形挡板)。教训沉淀:**规格书 §2 验收清单必须包含「全量 fast lane+全量 slow 直跑」两条,不能只列受影响文件**——四批下来盲区全出在"不在清单里的测试"。

### 1F 双审战绩(2026-07-10 中午,fable+codex 第三战)
互补形态三连验证:**codex BLOCK×6 全实锤**(systemd-run $VAR 二次展开改写 argv/CAMPAIGN_MEMORY_MAX=infinity 静默脱帽/user manager 不可连无回退——前 3 项本批引入,终审抽验坐实;另 3 项既有 fail-open 顺手封死);**fable=PASS_WITH_NOTES 现场极扎实**(退出码三值实测透传/degraded user systemd 下 scope 仍工作实证/双 checker 绿),其 NOTE 2 前提(env 不在 allowlist)被实现者用契约测试反转——教训:**审计 allowlist 成员必须 python print 集合或跑契约测试,grep 字面量会被拼接字符串骗过**(benders_loop:1248 的 "EX" "ACT_" 拼接条目,auto-memory 卡 zmd-allowlist-split-string-grep-trap)。终审自身贡献=allowlist 事实定案+两复现亲手抽验。B 段 smoke 五连实验主会话直做(实验设计/二分归因=发布面侦察,归因修复=数学面 M5)。

### 更新 2026-07-10 下午（owner 拍板）：fan-out 用 Workflow 编排 + 侦察也默认 codex
①**多 agent fan-out（双审/多路并行）直接用 Workflow 工具编排**，不手动 Agent×2 逐个派（owner 原话「这里你直接派wf不就好了」，针对 1F 双审手动双派场景）；②**侦察/调查类工作也默认派 codex**（此前审查=codex、实现=codex，现在侦察也归 codex；owner 原话「另外侦察的工作也交给codex」——当时我把 C1 差异面侦察派了 sonnet Explore）。计划书/任务书主会话亲写、终审 reseal 主会话直做不变。

### 更新 2026-07-10 下午（owner 拍板）：审查阵容回落 opus+codex
额度回到常态，「fable+codex」临时档结束（该档三战战绩：1C 首战/1D 第二战/1F 第三战，互补形态已定型入卡）。**审查回弹性制正常档=opus+codex 双审**；额度紧张时按原弹性制单走 codex。Fable 回归「单点难题」定位（ultracode-fable-spawn-discipline）。

### 四类活判据总表（2026-07-10 下午定稿，此前三类判据漏了侦察类——owner 点破补上）
| 活类 | 派谁 | 依据 |
|---|---|---|
| 计划书/任务书 | 主会话亲写 | 背景理解是大头，外包≈半份计划书 |
| 侦察/调查/差异分析 | codex | owner 07-10「侦察的工作也交给codex」（此前判据表缺这类，曾误派 sonnet Explore） |
| 实现 | codex | 工作量大头省额度，指令一次写全 |
| 审查 | opus+codex 双审（额度紧=单 codex） | 独立性是本质；fable+codex 是已结束的临时档 |
| 终审 reseal/close-kernel | 主会话直做 | 发布面负责人不外包 |
多路 fan-out（双审/并行侦察）用 Workflow 编排，不手动 Agent 逐个派。

### 侦察=codex 的头对头实证（2026-07-10 M5 归因侦察，sonnet vs codex 同题）
codex 三个关键发现 sonnet 全漏：①harness 层 env 差异（b0_4r runner 自设 automatic/probing1/symmetry1，纠正了 sonnet「solve 参数逐字节相同」的误导性结论）②产品独有 family×ghost-anchor big-M 网络（4225×F 规模，比 sonnet 找到的 family 段大两个数量级）③跨面证据（翻会话 JSONL 确认 taskset、指出 OOM 跑无 snapshot 的工具盲区）。sonnet 头号发现正确但深度止步单文件比对。——owner「侦察交给 codex」拍板的当场验证。

### opus+codex 正常档首战（2026-07-10 晚，cut 修复批双审）
双 PASS_WITH_NOTES 零 BLOCK（四批以来首次无修复轮）。互补形态在回落阵容下保持：opus=注入旧 bug 验证红测真实性+运行时 monkeypatch 验证守卫 load-bearing+精确 reseal 清单（6 条 checker 错逐条定性全为 sha 漂移）；codex=发现 replay 诊断 subset 残留（生产不可达,记 TRIAGE）+真实求解 2×1 master 越过 seam 测试验证。Workflow 编排双审首战跑通（parallel 双 agent,14min 收齐）。

== 2026-07-10 深夜追加:spike 三轮协作战绩(侦察→实现→卡点拍板闭环) ==
P1.3A attach spike 的 codex 协作全链(同一 thread 三轮,threadId 复用零重复喂背景):①侦察六问全答(step_8 契约/cut 字段/自然空间只有 257 条/14 条风险清单,质量与 M5 头对头持平);②实现前**主动暂停上报规格硬冲突**(GHOST_AGNOSTIC F5 被 delegate 拒空条件,给三选一带证据链)——这是 codex 首次在动手前拦下规格错误,比实现后返工省一轮;③拍板(harness shim)后一次交付全绿(冒烟两组+断言套+ruff)。范式确认:**侦察和实现用同一 codex thread 是高杠杆形态**——实现方带着自己的侦察记忆,任务书只需写增量拍板。主会话职责=拍板卡点(三选一裁决)+终审+正式跑(单发铁律)。

== 2026-07-11 追加:规格书两轮双审范式(阶段 B 实现规格书首用) ==
主会话亲写的大规格书(10+ sealed 文件批总纲)过审形态:**一轮打事实,二轮打闭合性**。一轮双审(opus 7+codex 27,6 BLOCK)抓的全是初稿事实错误与依据失真(臆造字段/迁移面低估/「不可实现的校验」);按 fix 重写 v2 后,**二轮必须做**——v2 的新拍板一轮审查者没见过,二轮(opus 6+codex 13,4 BLOCK)恰好全打在 v2 新拍板的闭合缝上(同型病换字段名/类型冲突/批次依赖断头)。两轮 53 条全采纳无一驳回,codex 连续两轮 verdict=BLOCK 都是真 BLOCK(证据全实)。教训:大规格一轮过审=假收敛;v3 里自己新加的拍板要么取审查者 fix 方向、要么标注实现批首件验证。

== 更新 2026-08-08（跨层对账 G-2/3/4/10 订正）==

本卡「分工」段路由已整体过时——现行=主线程(Fable 本尊)不亲自实施、实施一律派 opus/wf;codex 额度随用量波动(08-08 刷新后 owner 恢复原始分工:codex 实施主力、opus 审查席,以文件层路由卡现值为准);派 Fable 子代理需 owner 允许(08-07 硬规矩)。权威=文件层 codex-default-delegation-routing / ultracode-fable-spawn-discipline。本卡仍有效部分=codex 协作特性段(任务书一次写全/冲突不默默处理/改动真实落盘)。
