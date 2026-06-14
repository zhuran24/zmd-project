---
name: design-creative-use-team
description: 设计类/创造性/开放式任务用 Agents Team 讨论收敛, 不是单干也不是纯确定性 Workflow; deterministic fan-out/对抗验证才用 Workflow。
metadata:
  node_type: memory
  type: feedback
---

> 事实依据: [[fact-decision-boundary-is-ability]]

设计类、创造性、开放式探索的任务 → 开 **Agents Team** 让多个 agent 互相通信、辩论、在彼此想法上叠加来收敛方案; 不要单干, 也不要用纯确定性 Workflow 顶替。

**Why**: 创造性/设计的解空间宽, 多视角来回讨论能碰出"单一作者"或"各自独立产出再合并"都碰不出的方案。Workflow 擅长的是机械分解 / 大范围并行独立子任务 / 对抗式交叉验证, 它把 agent 隔开各干各的, 不擅长"讨论"。

**How to apply**: 任务实质 = 设计/创造/开放式想法 → Team; 任务实质 = 确定性分解 / 大范围并行查改 / 对抗式交叉验证 → Workflow; 轻量单点 → 单 Agent 或自己干。判据看任务实质, 跟 [[no-workflow-use-chrome-gpt-review]]、[[workflow-approval-not-avoidance]]、[[no-workflow-scope-clarification]] 一起读。(2026-06-14 owner 裁决)
