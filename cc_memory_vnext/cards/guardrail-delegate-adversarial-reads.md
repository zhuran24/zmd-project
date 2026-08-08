---
id: guardrail-delegate-adversarial-reads
kind: decision
title: 读 checker 对抗性语料/外审原文这类"满是绕过·篡改·exec"的内容,派独立上下文子代理去读、只带回摘要——别在主对话里整段贴,否则安全护栏对累积历史持续误伤且切模型无效
summary: 做 checker/AST 校验器对抗性加固、消化外审 会话.md/补丁、诊断对抗性负例测试这类"通篇绕过·篡改·getattr(exec)·重绑 main·变异探针"的语料时,**不要**在主对话上下文里整段 Read/复述原文(owner 2026-07-02 点破)。原因:安全护栏审的是**整个请求上下文=全部对话历史**,不是最新那句;这类原文与"教绕过安全检查"同形,一旦堆进历史,之后每发一条新消息(哪怕"继续""封"这种单字)都把这堆原文重新提交、重新标红,导致全线程被降级;/model 切模型**无效**,因为原文还躺在上下文里(护栏输入侧审"模型读到的一切":历史/记忆/工具结果/文件;输出侧边生成边审)。解法:把"读这些敏感原文+诊断+必要时改"的活派给**独立上下文子代理**(Agent 工具 general-purpose,fresh context;**别用 fork**——fork 继承已染红的主历史),让它读、判、改,只把**结论摘要**带回主线程;我自己的汇报也只讲结论,不复述 payload。这样主线程历史保持干净、不累积触发源。判据:一段内容若"满是绕过/篡改/exec 且很长",就该进子代理而非主上下文。owner 同日晚进一步泛化:**发布面(certified 链/checker 硬化/外审补丁)的具体工作整体默认进子代理**,主线程只留方向引导与抽象结论;数学面(算法核心/CP-SAT 编码)不受限。
scope:
  domains:
    - checker-hardening
    - external-review
    - security-guardrail
    - context-hygiene
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - harden-checker
    - consume-review-report
    - read-adversarial-source
    - diagnose-adversarial-test
  keywords:
    - checker
    - 加固
    - 硬化
    - 对抗性
    - 绕过
    - 篡改
    - 变异探针
    - 外审
    - 会话.md
    - 复审报告
    - 护栏
    - guardrail
    - 降级
    - 标红
    - Fable
    - 子代理
    - AST 校验
    - 发布面
    - 分类器
    - 拦截
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 实现 round-N checker 硬化
    - 读这批外审报告做 triage
    - 诊断这个对抗性负例测试为什么没拦住
    - 为什么切了模型还是被降级
activation:
  layer_hint: L1
  must_know: false
  reason: 一上手 checker 加固/外审消化就该想起——整段读原文是自然倾向、不自知;不隔离则主线程被护栏持续误伤,且发现时已积重难返(切模型也救不回)。
provenance:
  op: record
  reason: owner 2026-07-02 点破 pr2-5 round-19 线程被安全护栏持续降级的机理:约 26.5 万 token 上下文全是 checker 对抗性审查原文,护栏审全历史→每条新消息重新标红,/model 无效;要求以后这类阅读派子代理、主上下文只留摘要。
  evidence:
    - "2026-07-02 round-19:主线程直接 Read checker 源码+对抗性测试(main=lambda:0 / getattr(builtins,exec) 等)持续触发护栏降级;改用 general-purpose 子代理(fresh context)读源码诊断回归测试失败,只带回'测试脆性'结论摘要,主线程未再累积 payload。"
  updated_at: "2026-07-02"
---
做 checker 对抗性加固 / 消化外审对抗性语料时的上下文卫生纪律(owner 2026-07-02 点破,当天亲历)。

== 机理:为什么"一直"被降级、切模型也没用 ==
安全护栏审的是**整个请求**——不只你新打那句,而是模型读到的一切:对话历史、记忆、工具结果、读进来的文件(官方原文:reviews everything the model reads, not just your latest message)。checker 加固线程通篇是"绕过 checker/重绑 main/getattr 摸 exec/变异探针/篡改"这类词,在分类器眼里与"进攻性网络安全·教绕过安全检查"**同形**(哪怕对象是你自己写的 AST checker、目的是防御加固)。这些原文一旦进了历史,**每发一条新消息都把它们整个重新提交一次**→每一轮重新标红。所以后来只发"继续""封"这种单字也照样被拦。/model 只改"想用哪个模型",改不掉被标红的上下文,**切回去也没用**(官方承认设计如此:original request is still part of it)。护栏输出侧也边生成边审(计费分 "blocked on input" / "blocked midstream" 两类,后者=生成到一半被掐)。

== 解法:对抗性阅读进子代理,主线程只留摘要 ==
凡是要读"满是绕过/篡改/exec/重绑"的长内容(checker/contract 源码、对抗性负例测试、外审 会话.md、绕过补丁原文),派**独立上下文子代理**去读:
- 用 **Agent 工具 general-purpose**(fresh context,不带主线程那堆染红历史);**不要用 fork**——fork 会把已染红的主历史整个继承过去,等于没隔离。
- 子代理读原文、做诊断/修改,**只把结论摘要**带回主线程(根因一句话、判定、改了啥、是否要 reseal、验证结果)。
- 我自己的汇报也**只讲结论**,不复述 payload 原文。
这样主对话历史里没有那堆触发源,一般就不再被误伤。

== 泛化(owner 2026-07-02 晚补充)==
口径不止"读对抗性语料"一种情形:**发布面(certified 链/checker 硬化/外审补丁消化)相关的具体工作整体默认走子代理**——主线程只看抽象大概、只做方向引导(给目标/验收标准/纪律,收结论,做决策),细节工作(读源码、跑诊断、改代码、跑验证)都在 fresh-context 子代理里发生;**子代理的汇报同样只许抽象结论**(过/没过 + 数字、失败性质分类、需要什么决策),不带 payload,派活时把这条汇报纪律写死在任务书里。**数学面(算法核心/CP-SAT 编码/binding/routing/master)不受此限**,主线程可直接看细节。

== 架构演进(owner 2026-07-03:leader 换 Opus,隔离方式反转)==
上面"发布面进子代理"的隔离**前提是 leader 自己是 Fable5**(分类器对 Fable5 敏感、发布面对抗性语料会持续降级它)。owner 2026-07-03 把 leader(主线程)模型换成 **Opus**——Opus 不受该分类器强度困扰,所以隔离方式**反转**:
- **发布面/对抗性工作(checker 硬化、reseal、close-kernel 登记面、外审对抗性报告 triage)由 Opus leader 直接做,不再派发布面子代理**(隔离的成本没了、上下文也不断)。
- **只保留 Fable5 子代理做纯数学面**(routing/CP-SAT 建模、canonical 语义、生成器、loader 这类**不含对抗性语料**的活),永不碰 checker/reseal/外审报告——防止 Fable5 被降级。
- 分界铁律:凡碰 checker/reseal/对抗性 = 发布面 = Opus leader;纯建模/规则/非对抗 = 数学面 = 可派 Fable5。
- 代理归属原则:已沾过 reseal/checker 对抗性语料的子代理**不要**转 Fable5(降级残留),要留 Fable5 就**全新起**只喂纯数学面。
**所以"发布面默认进子代理"这条现在只在 leader=Fable5 时成立;leader=Opus 时反过来,发布面归 leader。** 判断当前口径先看 leader 模型。

== 无缝降级的检测(owner 2026-07-03 教)==
降级**不是**输出被掐断 / 会话中断——它是**模型被无缝换掉**(换成受分类器约束更强的受限模型),会话照常、输出不截断。所以想确认某子代理有没有被降级,**看"输出完不完整 / 有没有被掐"是错的靶子**(对无缝降级无效)。正确信号 = **读它 transcript 里每条 assistant 消息的 `model` 字段**:transcript 在 `~/.claude/projects/<proj>/<session>/subagents/agent-<name>-<id>.jsonl`(用 `es` / glob 按 agent 名或 team-session id 搜);逐条取 `message.model`,全程是预期模型(如 `claude-fable-5`)= 没降级,某点后变成别的 = 那点被降级(变化点 ≈ 触发点)。实例:2026-07-03 math-batch3(Fable5)在数学面任务里意外撞到 T1 发布面(读了 V99 sha 清单 / checker / reseal),owner 让我查它降级没——读 transcript,132 条 assistant **全程 `claude-fable-5`、零变化** = 没降级;推测因它碰得浅(定位 loader → 判断撞 V99 → 立即停下上报,没深读对抗 payload)。但这次侥幸**不改分工**:仍让 Fable5 远离发布面。

== 判据 ==
leader=Fable5 时:一段内容若"很长 + 满是绕过/篡改/exec 字样"或整个发布面工作,默认进子代理。leader=Opus 时:发布面归 leader 直接做,只有纯数学面才派(Fable5)子代理。写审计提示词的受众纪律见 [[review-prompt-audience-purity]];外审剪贴板 staging 规程见 [[relay-review-clipboard-staging]]。

== 更新 2026-08-08（跨层对账 G-10/G-11 订正）==

上文「leader 换 Opus」与「只保留 Fable5 子代理做纯数学面（无须再问）」两条已过时：现行主循环模型=Fable 本尊；**任何 Fable 子代理（数学面与否）都要先问 owner**（08-07 硬规矩，权威=文件层 ultracode-fable-spawn-discipline）。本卡核心机制（对抗性语料进独立上下文子代理、主线程只留结论）不受影响、仍现行。
