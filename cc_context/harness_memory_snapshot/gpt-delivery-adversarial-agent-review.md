---
name: gpt-delivery-adversarial-agent-review
description: "ultracode 开时,HIGH soundness finding 的 GPT patch 落地前起独立对抗 subagent 做静态验证(finding 真不真/patch 完不完备有没有同型残留/是否引入反向缺陷[误弃合法 wave、新 false-CERTIFIED]/ruff-mypy 雷/独立判严重度),只读不跑测试(不抢 .pytest_tmp),主线同时机械 probe 红→绿;LOW finding 可省此步,机械全量+preflight 已兜(2026-06-14 face 6/8 实证有用)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

**对抗 agent 验收 GPT patch (ultracode 开时, 2026-06-14 face 6/8 实证有用)**: HIGH soundness finding 的 patch 落地前, 起独立对抗 subagent 做**静态**验证 (finding 真不真 / patch 完不完备有没有同型残留 / 是否引入反向缺陷[误弃合法 wave、新 false-CERTIFIED] / ruff-mypy 雷 / 独立判严重度), **只读不跑测试**(不抢 .pytest_tmp), 我同时在主线做机械 probe 红→绿。

实证: face8 agent 比 GPT 挖更深, 确认 false-CERTIFIED 会持久化进 campaign record、resume 后被 _compute_exact_frontier_state 当真证据 prune 候选 (放大严重度坐实 HIGH); face6 agent 穷尽扫全仓 output-only 工件构造零误拒 (清回归疑虑)。

LOW finding 可省此步, 机械全量+preflight 已兜。

母节点 [[gpt-delivery-no-blind-trust]]。
