---
id: ship-then-sweep-docs-for-stale-narrative
kind: constraint
title: 做完「改变既成事实」的工程后主动扫文档层过时叙述 — 代码/运行时变了,PROJECT_LOCK/README/CLAUDE 常没跟上,权威文档变「撒谎」(2026-07 两次同类遗漏)
summary: 反复出现的坑:实现完一个改变既成事实的工程(重生成/重 pin frozen artifact、建生产入口、补一个此前记为 OPEN 的机器条件、改 producer/seal/publish 行为),代码与运行时更新了,但**叙事文档层**(PROJECT_LOCK、README、CLAUDE.md、NAV_MAP、FILE_STATUS、CHANGELOG)没跟上、继续陈述旧状态,权威文档就在「撒谎」。2026-07 两次亲历:①candidate_placements 拐角修复重生成 → 17 个文档还写旧字节 `adcc/45,773,799`(运行时已 `a914/45,774,305`);②PR2 #7 通电建了 `scripts/run_supervisor_seal.py` → 大量文档(README 十几处 + CLAUDE/FILE_STATUS/CHANGELOG/PROJECT_LOCK/NAV_MAP)还说「生产入口不存在 / 无生产 caller / 操作链缺口」。两次都是 **owner 主动发现**(问「README/CLAUDE 更新了吗」)。**纪律:凡做完「改变既成事实」的工程,收尾必须 grep 一遍文档层有没有过时叙述并对齐,别等被问。** 改 `PROJECT_LOCK` 这类 release 契约的 done-condition 状态时,红线一字不松、甚至强化;历史叙事保留 + 加时点;描述性文档可派 codex 批量 + 逐处验收,最高权威(PROJECT_LOCK/NAV_MAP)leader 亲改守红线。
scope:
  domains:
    - release-engineering
    - documentation
    - workflow-discipline
  paths:
    - PROJECT_LOCK.md
    - README.md
    - CLAUDE.md
    - NAV_MAP.md
    - FILE_STATUS.md
    - CHANGELOG.md
  symbols: []
status: active
priority: P1
severity: high
triggers:
  intents:
    - finish-shipping-a-fact-changing-change
    - update-docs-after-code-change
    - sweep-stale-docs
  keywords:
    - 文档过时
    - 文档没跟上
    - README 更新
    - PROJECT_LOCK 更新
    - stale narrative
    - 收尾扫文档
    - frozen artifact 重生成
    - 生产入口
    - done-condition 状态
    - 既成事实
  negative_keywords: []
  paths:
    - PROJECT_LOCK.md
    - README.md
    - CLAUDE.md
  symbols: []
  error_regex: []
  examples:
    - 建了生产入口 / 重生成 artifact 后要不要更新文档
    - PROJECT_LOCK 里说的状态跟代码对不上
    - owner 问 README 更新了吗
activation:
  layer_hint: L1
  must_know: false
  reason: 做完改变既成事实的工程(建入口 / 重 pin / 补机器条件 / 改 seal/publish 行为)、准备收尾时该想起——文档跟不上代码是反复犯的遗漏,收尾主动扫一遍才不会让权威文档撒谎、不用等 owner 问。
provenance:
  op: record
  reason: 2026-07-04 PR2 #7 通电后 owner 再次问「README/CLAUDE 更新了吗」,坐实这是第二次同类遗漏,固化收尾纪律。
  evidence:
    - "2026-07-04 两次同类遗漏坐实:candidate_placements 重生成后 17 文档写旧字节(commit b9043f6 才对齐)、PR2 #7 通电(349c56c)后 README/CLAUDE/FILE_STATUS/CHANGELOG/PROJECT_LOCK/NAV_MAP 还说入口不存在(commit ae6646e 才对齐);两次都是 owner 主动问才补。文档更新守红线:P1.2 OPEN、main.py 止于 CANDIDATE_PROPOSED、通电≠closed≠发布 全程未削弱,preflight --full 19 passed。"
  updated_at: "2026-07-04"
---
做完「改变既成事实」的工程后,主动扫文档层有没有过时叙述(2026-07 两次同类遗漏后固化)。

== 坑(反复犯)==
实现完一个**改变既成事实**的工程,代码/运行时更新了,但叙事文档层没跟上、继续陈述旧状态,权威文档就在撒谎——误导将来的审查者/会话(以为缺口还在、重复做;或反过来以为已 closed)。2026-07 两次亲历,**都是 owner 主动问「更新了吗」才补**:
1. candidate_placements 拐角修复重生成 → 17 个文档还写旧字节 `adcc/45,773,799`(运行时已 `a914/45,774,305`);commit `b9043f6` 才对齐。
2. PR2 #7 通电建 `scripts/run_supervisor_seal.py` → README 十几处 + CLAUDE/FILE_STATUS/CHANGELOG/PROJECT_LOCK/NAV_MAP 还说「生产入口不存在 / 无生产 caller / 操作链缺口」;commit `ae6646e` 才对齐。

**Why**:文档跟不上代码 = 权威文档撒谎。PROJECT_LOCK/README/CLAUDE 是新会话/审查者的第一信息源,它撒谎 → 有人以为缺口还在去重复做,或以为条件满足了去误推 closed。而且 owner 会主动查(两次都问了),被问才补显得没收尾干净。

== How to apply(收尾 checklist 加一条)==
凡做完这类「改变既成事实」的工程 —— **建入口 / 重生成或重 pin frozen artifact / 补一个此前记为 OPEN 的机器条件 / 改 producer·seal·publish 行为** —— 收尾时 grep 一遍文档层:
- `PROJECT_LOCK.md`、`README.md`、`CLAUDE.md`、`NAV_MAP.md`、`FILE_STATUS.md`、`CHANGELOG.md`
- 搜该事实的**旧状态叙述**(如「不存在 / 无 caller / OPEN / 旧字节 / DOES NOT EXIST / 尚无」),逐处对齐现状。

== 改 release 契约(PROJECT_LOCK)时的红线纪律 ==
- 状态从「缺口存在」→「已补」只是**补一条机器条件**,不是 closure。红线**一字不松、甚至强化**:P1.2 仍 OPEN/BLOCKED、`main.py` 普通完成仍止于 `CANDIDATE_PROPOSED`、通电/入口存在 **≠** closed **≠** 发布、反绕过守卫、producer/mint 分权、OPEN-GATE、internal seal necessary-but-not-sufficient。
- **历史叙事保留 + 加时点**(改过去时 + 补「后续已于 <date> 落地」),别删历史。
- 分工:描述性文档(README/CLAUDE/FILE_STATUS/CHANGELOG)可派 codex 批量 + leader 逐处验收红线;**最高权威(PROJECT_LOCK/NAV_MAP)leader 亲改**守红线。

关联:PR2 #7 通电本身见 [[pr2-7-supervisor-seal-entrypoint-design]];reseal/frozen 对齐见 [[close-kernel-reseal-execution-sop]];分工见 [[agent-role-division-and-codex-collaboration]]。
