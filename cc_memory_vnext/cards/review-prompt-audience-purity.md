---
id: review-prompt-audience-purity
kind: decision
title: 外审提示词只放 reviewer 干活需要的东西——别塞元信息,跨份引用自包含,份数从对象切面推,且必须要求 reviewer 对每个发现附修复补丁
summary: 给外部 reviewer(GPT Pro/codex)写审计提示词的四条纪律(①②③为 owner 2026-07-02 两次点破的实犯,④为 owner 2026-07-03 明示):①受众纯净——别塞外审元信息("首次审计"/"以往 N 轮审过什么"),那是说给 owner 听的,reviewer 拿它干不了事;②跨份引用禁止——reviewer 单会话只看一份,"见 entry 5"必须改自包含;③份数从被审对象自然切面从零推,别被上轮格式锚死;④**审查纪律段必须要求 reviewer 对每个 BLOCK/CONCERN 附可参考的修复补丁**(unified diff 或完整替换段,基于包内源码)——我方实现时不盲 apply,但有补丁作参考能省大量工作量(数学面/发布面通用;2026-07-02 数学面 3 个自发补丁全部被证明有用,而提示词只写了"修复方向"没要求补丁,是运气不是设计)。判据:每写一段先问"reviewer 拿这段能干什么"。**保留**的合法内容:范围界定(OUT-OF-SCOPE/已裁定残余勿重报)、"别信某某 gate"类审计要点、指向包内真实文件的历史缺陷线索。
scope:
  domains:
    - external-review
    - prompt-authoring
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - external-review-relay
    - write-review-prompt
  keywords:
    - 外审
    - 提示词
    - review prompt
    - relay
    - entry
    - 角度
    - GPT Pro
    - 分角度
    - 共享头
    - 几份
    - 写提示词
    - reviewer
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 给 round-19 写外审提示词
    - 这轮审计切几个角度
    - 帮我起草 GPT Pro 的审计 prompt
activation:
  layer_hint: L1
  must_know: false
  reason: 起草外审提示词的时刻该想起——元叙述是自然倾向、格式锚定是自然倾向,都不自知;owner 2026-07-02 同一天点破两次。
provenance:
  op: record
  reason: owner 2026-07-02 算法核心审计 relay 备制中两次纠正:一问"怎么正好 6 个角度"暴露格式锚定+漏角度;二指出提示词里的外审元信息对 reviewer 没必要。
  evidence:
    - "2026-07-02 算法核心外审:6 份锚定 round-18 格式→重推后补 entry_7(数据生成链);7 份共享头全删'首次/以往 12 轮'叙述,跨份引用改自包含,X/6 标题错误一并修正。"
updated_at: "2026-07-02"
---
给外部 reviewer 写审计提示词的四条纪律(①②③=2026-07-02 实犯;④=owner 2026-07-03 明示):

== ① 受众纯净:删外审元信息 ==
"这是首次 XX 审计"/"以往 N 轮外审都在审 YY"/"本轮价值所在"/"与以往外审不同"——这些是**说给 owner 听的项目史**,reviewer 拿它干不了任何事,反而占注意力。判据:逐段问"reviewer 拿这段能干什么?"——干不了什么就删。
**合法保留**(不是元信息、是审计输入):范围界定(OUT-OF-SCOPE、已裁定残余勿重报清单)、审计要点("别信 I1 的 confirmed"这类)、指向包内真实文件的历史缺陷线索(如 V84 → test_v84_*.py)。

== ② 每份自包含:禁跨份引用 ==
reviewer 每份提示词开一个独立会话,看不到其他份。"见 entry 5"/"与 entry 2 同族"必须改成自包含:直接写 file:line("与 exact_coordinate_master.py:3944 的 XX 同族")或中性描述("由另一份并行审计覆盖")。份数变动时记得改所有标题的 X/N。

== ③ 份数从零推:别被上轮格式锚死 ==
round-18 是"1 全面+5 分角度"=6 份 → 下一轮审计想都没想也切 6 份 = 格式锚定。正确做法:从被审对象的**自然切面**推(实体模型各一份 + 横切关注点各一份 + 一份全面综合兜漏),再检查"如果不是这个数该是几"——2026-07-02 这一问直接暴露漏了整个上游(数据生成链:frozen hash 只防篡改不防生成错误,pose/实例生成器错了下游全白审)。
份数的真实约束:每份窄到能逐行深审(上下文过宽必然审浅——与 codex auto-compact 教训同源)×份数=owner 手动开会话的成本。

== ④ 必须要求 reviewer 附修复补丁(owner 2026-07-03 明示)==
审查纪律段除"根因+最小反例+影响面+修复方向"外,**必须加一条:每个 BLOCK/CONCERN 请附可直接参考的修复补丁**(unified diff 或完整替换段,基于包内真实源码可应用)。定位:我方后续实现修复时**不盲 apply**(reviewer 环境/基线可能偏差,补丁自带的 sha 一律重算),但作参考实现能省大量工作量。数学面/发布面提示词通用。教训:2026-07-02 数学面 7 份提示词只写了"修复方向",3 个补丁是 reviewer 自发给的、事后全部被证明有用——靠运气不如写进纪律。

与 [[memory-write-for-future-reader-not-present]] 同族(都是"为读者写,不写只对当下有意义的元叙述"),这张是它在外审提示词场景的具体化。剪贴板 staging 操作规程见 [[relay-review-clipboard-staging]]。
