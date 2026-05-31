---
name: subagent-for-closed-loop-tasks
description: "独立闭环 + 不需用户中途决策 + done 可验证的中等粒度活 (≥3 step + read/edit/verify) 直接 spawn sub-agent, 不在主对话做. 不再问 user 该不该."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8ce2a10d-50a6-4d5c-82bf-3c4414cb623f
---

## 规则

当任务符合**三个条件全满足**时, 直接 spawn sub-agent (opus 默认),
**不在主对话里自己做, 也不问用户是否该 spawn**:

1. **独立闭环** — read + edit + verify 一个完整 loop, 不需主对话当前 context
2. **不需用户中途决策** — done 标准 + 边界已经清楚, 中途不会冒出 design 抉择
3. **done 可验证** — 有 grep / pytest / specific assertion / file diff 等
   objective check, agent 自己能判定完成

边界:
- **trivial 任务 (单 read / 单 edit / <3 step)** — 直接做, agent overhead 大
- **复杂决策任务 (含未定 trade-off)** — 主对话跟用户 align, 不 spawn
- **设计探索 (N 路 parallel)** — 走 [[design-phase-n-parallel-agents]] 不是此条

## Why

**节省主对话 context**: packaging 反复 build / memory audit fix 这种 read-多
edit-多 verify-多 的中等粒度活, 主对话执行会把每个 tool call 的输出/diff/grep
结果全堆进 context, 几轮就压几万 token. sub-agent 跑完只返一段 summary,
主对话 context 干净.

**主对话 default 倾向"自己做"是浪费**: 5-25 session 实测两个 case 都该
spawn 没 spawn:
- review pkg 反复 build 3 次 (audit-pkg-content + fix-README + rebuild +
  verify) — 完美闭环, 全可在 agent 内跑, 主对话只接 summary
- memory audit fix (7 HIGH 索引补 + 4 死 link 修 + verify) — 用户在另一
  session 让 Claude 接交接文档 +execute, 漂亮落地 — 本来主对话也能 spawn
  agent 做同样事

**用户偏好**: 用户原话 "额度用不完亏钱" (`[[design-phase-n-parallel-agents]]`),
spawn agent 不心疼算力. 主对话省的是用户 attention + context 不是 token.

## How to apply

每次准备开始一个 ≥3 step 的工作时, 先 check 三个条件:
- 闭环吗? (是否需要主对话当前 context 才能跑?)
- 决策清吗? (中途会冒出 user-facing 抉择吗?)
- done 可验? (能给 agent 一个 objective done 标准吗?)

三个全 yes → spawn agent (background, opus). 主对话给用户 1 句话说 spawn 了
什么 + 等 notification, 不轮询.

不再问 user "要不要 spawn agent" — 跟 [[lazy-mode]] 同 root: 心里有答案的
问句是无谓盖章.

## Refs

- [[design-phase-n-parallel-agents]] — N 路 parallel explore (kickoff /
  抉择), 跟此条互补: 那是 explore N 路, 这是 execute 单线闭环
- [[lazy-mode]] — 替用户想, sub-agent 同样减负
- [[long-op-background-mode]] — 长操作 background 模式, sub-agent 内置该模式
