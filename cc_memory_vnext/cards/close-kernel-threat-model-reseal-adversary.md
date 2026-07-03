---
id: close-kernel-threat-model-reseal-adversary
kind: decision
title: close-kernel 结构门的威胁模型【纳入】"能跑 reseal 仪式的半可信/内部对手"——这些 AST 结构锚只在"改被钉字节+忠实重算所有 hash"之后才可利用,故 round-19 三块新门覆盖不对称/缺兜底的缺口判 must-fix(走 round-20)、不归入既有 import-time·反射·checker-self 三类残余
summary: owner 2026-07-03 拍板:close-kernel 结构门的防护目标**明确纳入**"能执行 reseal 仪式的半可信/内部对手"(能改任一被字节 sha 钉死的源文件、并重算重钉所有 hash 的提交者)。依据:这些控制流/绑定/顶层封闭世界 AST 锚对**纯外部对手本就无意义**(外部对手改不动被钉字节)——它们唯一的用武之地就是"忠实 reseal 之后"这一层,即字节 sha 只让改动**可见**、锚才让改动**无害**;历轮 close-kernel 硬化一贯隐含此对手,故这次显式纳入是**一致选择、非扩围**。据此裁定:round-19 三块新结构门(父门↔checker 镜像判定、共享绑定 walker 的顶层语法覆盖、witness 承载文件的顶层封闭世界兜底)存在**覆盖不对称/缺兜底**的缺口,性质是"新块覆盖不完整/边界画错"、属 **must-fix**,**不**归入已显式登记的三类"语言本身不可闭合"残余(F import-time / A4 反射 / checker-self)。修复走 round-20,范围有界:对齐两侧镜像枚举、补齐 walker 顶层绑定语法、给承载文件加针对性顶层重绑兜底、加一条强制镜像等价测试、补一条此前遗漏的登记断言。规模中小。(2026-07-04 注:round-20 已完成 `2413cc2` 并随 pr2-5 `6e06922` 合入 main;owner 已在 round-20 画线停止 close-kernel 外审循环,见 [[review-convergence-tcb-line-not-zero-findings]]。)
scope:
  domains:
    - checker-hardening
    - external-review
    - threat-model
    - close-kernel
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - harden-checker
    - decide-threat-model
    - triage-review-finding
    - scope-round
  keywords:
    - close-kernel
    - 威胁模型
    - reseal
    - round-20
    - 残余边界
    - 半可信对手
    - 内部对手
    - 镜像
    - 结构门
    - must-fix
    - 已接受残余
    - import-time
    - 反射
    - checker-self
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 这条 close-kernel 缺口该修还是算已接受残余
    - round-20 该不该做、依据是什么
    - checker 结构锚防的是谁
    - 外审报的镜像不对称是不是 must-fix
activation:
  layer_hint: L1
  must_know: false
  reason: 决定 close-kernel 结构门"防谁"——这决定了每个外审发现是 must-fix 还是可归入残余;不知道这条会把"新块覆盖不对称"误判成"已接受残余"而放行。
provenance:
  op: record
  reason: owner 2026-07-03 拍板把 reseal 级半可信对手纳入 close-kernel 防护目标;两份独立终裁(triage)都据此推荐 NOT CLEAN → round-20。
  evidence:
    - "2026-07-03:pr2-5 round-19 外审 triage 终裁 NOT CLEAN;owner 拍板'防'(纳入半可信 reseal 对手),三块新门覆盖不对称缺口判 must-fix、走 round-20。"
  updated_at: "2026-07-04"
---
close-kernel 结构门"防谁"的定性决定(owner 2026-07-03 拍板)。判某个外审发现是 must-fix 还是可归入残余时,先看这条。

== 决定 ==
close-kernel 结构门(父门运行时闸 + 结构 checker + 两者互为镜像的顶层判定)的**防护目标明确纳入**"能执行 reseal 仪式的半可信/内部对手":即一个有提交权、能改动任一被字节 sha 钉死的源文件、并按既定 reseal 连锁**忠实重算、重钉所有 hash** 的对手。它**不是**纯外部对手(外部对手改不动被钉字节)。

== 依据(为何纳入是一致选择,而非扩围) ==
- 这些控制流锚、绑定唯一性判定、顶层封闭世界判定,都是**结构层 AST 断言**。对一个改不动被钉字节的纯外部对手,它们本就不产生任何额外保护——字节 sha 已经把外部篡改挡在外面。
- 它们唯一的用武之地,正是"**忠实 reseal 之后**"这一层:字节 sha 只保证一处源码改动**可见**(sha 变、需有人重钉),而结构锚才保证"即便被重钉,也不能悄悄把门的语义掏空"。所以这些锚**天然就是为 reseal 级对手设计的**。
- 历轮 close-kernel 硬化(逐轮补父门/checker/witness 的结构锚)一贯**隐含**这个对手模型;这次只是把它**显式写下来**,是对既有实践的一致确认,不是新增防护面。

== 它明确/推翻了什么 ==
- round-19 引入三块新结构门,但它们之间**覆盖不对称、且有一块缺顶层兜底**:①一侧镜像判定器比另一侧**更宽**(更宽的一侧是负责"要不要放行"的那一侧,方向危险);②共享的顶层绑定枚举**漏认若干顶层绑定语法**;③承载 witness 直呼的运行时文件一侧**没有**另一块已有的顶层封闭世界兜底,只靠绑定计数。
- 这些缺口的性质是"**新块覆盖不完整/边界画错**"——即某类顶层语法形态的重绑,能在镜像不对称处或无兜底处**漏判**、从而在忠实 reseal 之后仍让门放行。**不是**"语言本身不可闭合"的那种残余。
- 因此它们判 **must-fix**,**不**归入已显式登记的三类"接受残余"(见下)。据此第 13 轮外审 triage 定 **NOT CLEAN → round-20**。(round-20 已完成并合入 main `6e06922`;外审循环随后由 owner 画线停止。)

（受众纪律:本卡只做定性,**不记录任何具体的重绑/绕过/exec 构造**——那些是对抗性 payload,详见 [[guardrail-delegate-adversarial-reads]] 的上下文卫生纪律。)

== round-20 修复范围(抽象、有界) ==
- 把父门侧的"定义期节点枚举 + 绑定 walker"与 checker 侧对齐,消除镜像**不对称**(更宽的一侧收紧到与另一侧逐节点一致)。
- 给共享顶层绑定 walker **补齐**此前漏认的几类顶层绑定语法。
- 给 witness 承载文件一侧加一个**针对性的顶层动态重绑兜底**(按受保护名参数化的 denylist,而非承载文件套不了的白名单封闭世界),并对承载类的实例查找钩子做约束。
- 父门控制流锚补两项对称约束(被锚函数无装饰器 + 父模块顶层封闭世界)。
- 附:加一条**强制镜像等价测试**把两侧同名判定锁死防未来漂移;补一条此前遗漏未断言的登记 nodeid。
- 规模中小;涉及 close-kernel checker + 父门两个源文件的结构层,外加登记面/测试,连带一次统一 reseal。

== 已接受残余的边界(这次维持,不与上面混淆) ==
三类"语言本身不可完全闭合"的残余维持**显式登记、本轮不强求闭合**:import-time 求值面、反射/栈逃逸面、checker-self 在极端形态下的自完整性面。它们与上面的 must-fix 缺口的区别在于:must-fix 是"新块之间覆盖不对称/漏了一块本可加的兜底"(可闭合、边界画错),残余是"要闭合需追着语言特性打地鼠、成本发散"(有界接受)。判某发现归哪边,用这个区分。

关联:对抗性语料的上下文卫生 [[guardrail-delegate-adversarial-reads]];外审提示词受众纪律 [[review-prompt-audience-purity]];外审剪贴板 staging 规程 [[relay-review-clipboard-staging]]。
