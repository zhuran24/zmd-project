---
id: memory-payload-at-injection-point-not-circular
kind: decision
title: 记忆该记住的 payload 放在【注入即见】处(summary / L0),别写成"先去读/搜 X"埋进 X 正文(循环依赖、拦不住它要拦的失败)
summary: 一条提醒 / must-do 必须放在【读者还没做它要求的事时也会看见】的地方——vnext 卡的 **summary**(L1 自动注入给我看的就是它)或 L0 must_know。**绝不**写成"写提示词前先 search / 重读本卡"埋在卡正文里:那是循环依赖,真会漏的人(没读正文)永远撞不上这句,读了正文的人已经看见真规则、不需要它;失败模式是"没读",提醒却只在"读了"才可见 = 废话。修法 = 把 must-do 的【实际内容】直接上提到 summary,让注入在 point-of-need 把 payload 送到面前,别用"去 fetch X"的指路替代 payload。
scope:
  domains:
    - memory-system
    - memory-authoring
  paths:
    - cc_memory_vnext/cards
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - memory-write
    - memory-authoring
    - place-reminder
    - card-design
  keywords:
    - 记忆
    - 卡
    - card
    - summary
    - 正文
    - 注入
    - 提醒
    - must-do
    - 循环依赖
    - 先读
    - 先 search
    - 重读本卡
    - 凭印象
    - 别凭印象
    - 漏掉
    - 提醒自己
    - 放对吗
    - 正文里加
    - point-of-need
    - payload
    - vnext
    - 废话
  negative_keywords: []
  paths:
    - cc_memory_vnext/cards
  symbols: []
  error_regex: []
  examples:
    - 我想在这张卡正文里加一句"写之前先 search/重读本卡"提醒自己别忘
    - 这条 must-do 放卡的正文还是 summary?
    - 怎么保证写提示词时真的看见这条规则、而不是凭印象漏掉
activation:
  layer_hint: L1
  must_know: false
  reason: 写 / 放记忆时该想起这条,否则会把 must-do 埋进没人读的正文、再靠"先读 X"的循环提醒兜底(review-routing 卡实证失败 5 次)。
provenance:
  op: record
  reason: owner 2026-06-30 点出 review-routing 卡里"写提示词前先 search / 重读本卡"是循环废话,提炼成普适记忆设计原则。
  evidence:
    - "review-routing-gptpro-relay 卡曾把 must-do(具体补丁 / lean)埋正文 + 循环'先读本卡'提醒;r5 relay 凭压缩后印象漏掉(已五次);修法=must-do 上提 summary。"
updated_at: "2026-06-30"
---
普适记忆设计原则:**一条提醒 / must-do 必须放在「读者还没做它要求的那件事时、也会看见」的地方**。

== 循环依赖反模式(要避免)==
把"写 X 前先 search / 先重读本卡 / 先查某条记忆"这种**指路型元指令**埋在卡 / 条目的【正文】里——它从设计上就拦不住它声称要拦的失败:
- 真会漏的人 = 没读正文、凭印象写的人 → **永远撞不上这句提醒**(它在正文里)。
- 读了正文的人 → 已经看见真正的规则了 → 这句"先读本卡"**纯属多余**。
- 失败模式是「没读」,而提醒只在「读了」时才可见 = 对它要拦的失败完全无效 = 废话。

== 正确做法 ==
把该记住的 must-do 的【实际内容(payload)】直接放到**注入即见**的位置:
- vnext 卡:放进 **summary**(L1 自动注入给主模型看的就是 summary、不是正文),让"正要做这件事"的时刻 payload 自动送到面前;真正必须每次都见的升 L0 `must_know`。
- 别用"去读 / 去 search X"的**指路**替代 payload——指路要求读者先主动做一步(而那一步恰恰是失败点)。

判据:写一条记忆 / 放一条提醒时自问——**「如果读者正处于会漏掉它的那种状态(凭印象、没主动查),这句话还能被看见吗?」** 答否 → 它放错地方了,把 payload 上提到注入层。

实例:`review-routing-gptpro-relay` 卡曾把"每个 BLOCK 要具体补丁 / lean 不剧透"埋正文、再加一句"写提示词前先 search / 重读本卡",r5 外审 relay 凭压缩后印象写、把"具体补丁"漂成"补丁方向"(同型失败已五次);修法 = 把那 4 条 must-do 上提到卡 summary、删掉循环的"先读本卡"句。与 [[memory-write-for-future-reader-not-present]](为未来无上下文的读者写)、[[cc-memory-meta-index]](元记忆导航)同属"怎样写 / 放记忆才真生效"族;典型受害卡 [[review-routing-gptpro-relay]]。
