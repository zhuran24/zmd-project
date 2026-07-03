---
id: review-convergence-tcb-line-not-zero-findings
kind: decision
title: 外审"审到零发现"永远做不到、不是收敛判据——真收敛=画冻一条 TCB 线、修线以上全部、线下新发现算受信假设→owner 拍板可停;2026-07-03 owner 判 round-20 close-kernel 强度够、在此画线收口、停外审循环
summary: 项目头号硬教训(README §3/§7、cc_memory `p1-2-review-converged-tcb-start-p1-3`):对抗式外审**永远能再剥一层"信任洋葱"**(witness→发布闸/artifact 载入→验证器执行的字节码→解释器→OS→硬件),逐个打补丁总能被推到下一层,所以**"审到零发现"不可能、更不是收敛判据**。真正的收敛是三步:①显式画+冻一条 **TCB 线**(声明"这些选择信任、不再证":解释器/stdlib/OR-Tools native/OS 隔离/冻结几何字节等)②把线**以上**的洞全修掉 ③之后新发现要么落在线**以下**(=已声明的受信假设,不算数)、要么是已知 done 实例 → **可停审**。判断"该不该继续外审"的唯一尺子:**再剥出的东西还在不在 TCB 线以上**——线上的 soundness 洞(能盖假章)必审,线下的"对更强假想对手能否更严"是强度选择、无限可加、不该追。**结束靠 owner 主动画线+拍板(P1.2 是手动门、clean-streak 故意存仓库外),不是等外审次数自然归零。** 防混淆:TCB 架构(L0/L1 隔离子进程 micro-verifier)落地**之前**(PR1/capsule 时期)外审剥出的是**真能盖假章的洞**(verdict 可同进程伪造 `TerminalFixedWitnessVerdict(publishable=True)`、guard 按函数名认可绕、hash 可自 reseal),owner 拍板上隔离验证器才从"逐个补丁"升级为"架构上不可伪造"——那才是真危险;而 2026-07-03 这次 close-kernel(round-14→20)剥出的是"门能否对更强内部对手更严",危险等级低得多,但"审不完"机理同源。**本次拍板(owner 2026-07-03)**:判 round-20 close-kernel 作为"防半可信内部对手"的门强度**够了**,在此画 TCB 线;**停止 close-kernel 外审循环**(round-19/round-20 外审都不发)、进入 P1.2 owner 手动门收口。数学面同轮已收敛(8 份报告真 BLOCK 只剩拐角、已修,余为假阳性/降级/表达债;canonical 四语义已机器化在 mixflow 分支),数学面收口=写 canonical(已做),不靠外审。**适用范围澄清(owner 2026-07-04)**:画线只管"外审循环停不停",**不等于**把 PR2 深化项(#1/#2/#3/#5 独立枚举/#8/#9)标成已完成或从账上划掉——owner 原话意思是"#7 可以填上了,其他部分还没做、没做自然不能填上";它们仍是真实 backlog、将来要做几轮才能填,只是不挡当前收口、现在不排期。
scope:
  domains:
    - external-review
    - certification-philosophy
    - close-kernel
    - project-governance
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - decide-whether-to-external-review
    - assess-review-convergence
    - plan-close-kernel-hardening-round
    - close-out-p1-2
  keywords:
    - 外审
    - 收敛
    - 零发现
    - 审到零
    - 信任洋葱
    - TCB
    - TCB 线
    - 画线
    - 收口
    - round
    - close-kernel
    - 还要审多久
    - 什么时候结束
    - 何时停审
    - 强度
    - 半可信对手
    - 手动门
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 这个 PR 外审都第 15 次了到底什么时候结束
    - 要不要再发一轮 close-kernel 外审
    - round-N 硬化是不是又变成无底洞了
    - 审到没问题了才能收吗
activation:
  layer_hint: L1
  must_know: false
  reason: 每逢"要不要再外审 / 硬化到 round-N 够不够 / 什么时候能收"该想起——不然自然倾向是"再审一轮更保险",而项目铁律是那永远审不完、且不是判据;画线收口是 owner 决定,代理别自作主张起新 round、也别拿"还能审出东西"当"没结束"。
provenance:
  op: record
  reason: owner 2026-07-03 深度反问"外审第 15 次了到底何时结束、是不是重蹈那次(TCB 落地前反复外审出假 CERTIFIED 大问题)的坑",并拍板"够了,就这样吧"——在 round-20 close-kernel 强度上画 TCB 线、停外审循环、进收口。把收敛判据(项目老教训)+ 本次画线决定一并固化。
  evidence:
    - "2026-07-03:数学面 8 份外审终裁真 BLOCK 仅剩拐角(已修 d1845dc),余为假阳性(被 PROJECT_LOCK 否)/降级 guarded/canonical 表达债/witness 卫生——收敛信号;发布面 close-kernel round-20(2413cc2)双 checker 绿、owner 判强度足、画线收口。"
    - "史料:README:506/604/757-765 '对抗审查总能再剥一层信任洋葱,审到零发现不是收敛判据';收敛=画冻 TCB 线+修线上+线下算受信假设(cc_memory `p1-2-review-converged-tcb-start-p1-3`)。TCB 落地前假 CERTIFIED 大问题见 README §3/§5(可伪造 verdict / name-based guard / self-reseal hash)。"
    - "2026-07-04:两个代理(主线线程+状态调查会话)先后把画线读过头成'PR2 深化项被取消/违背拍板',owner 被搞懵后当面澄清:画线≠划掉 backlog,#7 已填、#1/#2/#3/#5独立枚举/#8/#9 还没做、以后仍要做;据此补适用范围段。"
  updated_at: "2026-07-04"
---
外审何时结束的收敛判据 + 2026-07-03 owner 画线收口拍板(本轮方向性最大的一个决定)。

== 头号硬教训:"审到零发现"是个陷阱 ==
对抗式外审**永远能再剥一层"信任洋葱"**:你堵掉 witness 层,对手退到发布闸;堵掉发布闸,退到验证器执行的字节码;再往下是解释器、OS、硬件。**逐个打补丁总能被推到下一层**(reviewer 当年明说过这句)。所以"一直审到某轮零发现"这件事**不可能发生**,拿它当"结束标志"就是掉进无底洞——这正是 owner 记忆里"审了很多很多轮还出大问题"那段的机理(精确的"70 次"史料里没有单一节点,实际是 PR1 三轮 + capsule 五六轮反复推翻 + close-kernel 这条自己跑了 18 轮……累加,数字不重要,模式对)。

== 真收敛 = 画线,不是审干净 ==
项目定义的结束条件是三步(README §3/§7、cc_memory `p1-2-review-converged-tcb-start-p1-3`):
1. **显式画+冻一条 TCB 线**——声明"这些东西选择信任、不再证"(解释器 / stdlib / OR-Tools native `.so` / OS 进程·文件隔离 / 父 relay / 冻结的几何字节 …)。
2. **修掉线以上的全部洞**。
3. **之后新发现**:落在线**以下** = 已声明的受信假设(不算数)、或是已知 done 实例 → **可停审**。
唯一的尺子:**再剥出的东西在不在 TCB 线以上**。线上 = 能盖假章的 soundness 洞,必审;线下 = "对更强假想对手能否更严",是强度选择、可无限加、**不该无限追**。"当前 TCB 线画对没有"本身是留给新审查者的活问题,但"审到零发现"绝不是判据。**结束靠 owner 主动拍板画线**(P1.2 是手动门、clean-streak 故意存仓库外),外审替不了这一拍。

== 防混淆:TCB 落地前 vs 落地后,危险等级天差地别 ==
- **落地前(PR1/capsule 时期)= 真危险**:剥出的是**信任根自己是空的**——verdict 是普通内存对象,`TerminalFixedWitnessVerdict(publishable=True)` 同进程一构造就自带通行证、不跑 binding/routing 直接 mint CERTIFIED;guard 按函数名认、换别名就绕;hash 能自己给自己重盖。3 个 reviewer 独立剥到同一层。owner 拍板不再打补丁、改**架构级根治**:验证器进隔离子进程(`python -I -S -B`)执行 + 结论带不可伪造 nonce + 认不出的锚点 fail-closed = PR2 的 L0/L1 最小 TCB micro-verifier。这才是"那个三字母信任系统"。
- **落地后(本次 close-kernel round-14→20)= 低危**:TCB 架构已在,这条是"第二道门"(结构门/lint 性质,证登记结构没漂移、**不证求解数学**)。剥出的是"门能否对更强内部对手更严",**不会让你盖出假 CERTIFIED**。危险低,但"审不完"机理同源——所以照样必须 owner 画线,否则 round-21/22… 无限。

== 本次拍板(owner 2026-07-03)==
- **发布面**:round-20 close-kernel(`2413cc2`,双 checker 绿)作为"防半可信内部对手"的门,**强度够了 → 在此画 TCB 线**。**停止 close-kernel 外审循环**:round-19、round-20 外审**都不发**(不是没审出东西,是再剥就落 TCB 线下了);进入 **P1.2 owner 手动门**收口。
- **数学面**:同轮 8 份外审**已收敛**——真 BLOCK 只剩拐角(已修 `d1845dc`),其余假阳性/降级 guarded/表达债/witness 卫生。收口 = 把四条游戏语义写进 canonical(**已机器化在 mixflow 分支**),**不靠外审**。
- **收口后残余**(非外审):① mixflow 合入 main 的时机(owner 定,前置=pr2-5 那条大分支近期合不合 main,两分支有 4 个 close-kernel 文件交集会冲突);② 批次 3 三个数学面小尾巴(loader parity / I1 文档降级 / 方向常量 anti-drift,派 Fable5,不碰敏感面)。

== 防重蹈 ==
未来任何会话:**别再无脑起 round-21**、别拿"还能审出东西"当"没结束"的信号(永远能)。要判该不该再审,只问"再剥出的在不在 TCB 线以上"。外审的历史使命(挖净能盖假章的 soundness 洞、逼出 TCB 架构)已完成;剩下的是画线决定,归 owner。

== 适用范围澄清:画线 ≠ 取消 PR2 深化 backlog(owner 2026-07-04)==
2026-07-04 两个代理先后把这张卡的"画线收口"读过头:主线线程说 PR2 #1/#2/#3/#5 深化"跟画线精神有张力",状态调查会话更直接说"重开这些等于违背收敛拍板"——owner 被搞懵后当面澄清,两个问题别搅在一起:
- **"做没做?"**——没做完。#7(supervisor seal 生产入口)已填上(349c56c);#1/#2/#3 是 partial、#5 独立枚举/#8/#9 基本没动。**没有任何一项被画线标成"已完成",也没有被划掉。**
- **"现在排不排?"**——不排。画线管的只有一件事:**外审循环停**,收口不等这些空格填满。
owner 原话意思:"第 7 部分是可以填上了,但其他部分还没做,还没做自然不能填上"——这些深化项仍是**真实 backlog**,预期将来要"做上一段时间/做上几轮"才能填;何时排期归 owner,届时明说重开即可,**不需要**推翻画线拍板(两者不矛盾,是先后与优先级)。代理别把"线下的活现在不做"外推成"这批活永久取消/碰它就是违背拍板"。

四条游戏语义拍板见 [[routing-game-semantics-rulings]];close-kernel 防谁(半可信内部对手)见 [[close-kernel-threat-model-reseal-adversary]];#7 入口通电的设计边界见 [[pr2-7-supervisor-seal-entrypoint-design]];外审对抗性语料的上下文卫生见 [[guardrail-delegate-adversarial-reads]];外审 relay 剪贴板规程(本次收口后暂不触发)见 [[relay-review-clipboard-staging]]。
