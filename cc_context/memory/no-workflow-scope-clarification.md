---
name: no-workflow-scope-clarification
index_summary: "2026-06-14 owner 纠正:no-workflow 只管「审查/判 soundness 动作本身」外发,不等于所有任务默认单 Agent;准备/调研/编排可 workflow 并行 fan-out;判据看任务实质"
description: "workflow vs no-workflow 厘清(2026-06-14 owner 纠正,别再误读):no-workflow 裁决只管「审查/判 soundness 这个动作本身」外发 GPT Pro、不开本地多代理审查 workflow;它不等于「所有任务都默认单 Agent」;准备/调研/编排(不跑 pytest 不判 soundness)完全可以 workflow 并行 fan-out;判据看任务实质不看是不是外审相关"
metadata:
  node_type: memory
  type: feedback
---

**workflow vs no-workflow 厘清 (2026-06-14 owner 纠正, 别再误读)**: 本 no-workflow 裁决**只管一件事**——「审查 / 判 soundness 这个动作本身」外发 GPT Pro 做、不开本地多代理**审查** workflow(实测教训: 审查 agent 并发跑 pytest 互删 .pytest_tmp + API 超时挂 critic)。它**不**等于「所有任务都默认单 Agent」。**准备工作**(调研代码、综合素材写审查 prompt 这类, 不跑 pytest 不判 soundness)完全可以用 workflow 并行 fan-out —— 实测用 Workflow 3 个 opus agent 并行调研 binding/campaign/scheduler 三面产出 prompt 素材, 高效且不违反 no-workflow。owner 06-14 抓到我又把 no-workflow 误读成「默认单 Agent」退回串行单代理, 纠正: workflow 已放开(approval_required=false, 见 [[workflow-approval-not-avoidance]]), 该用就用; no-workflow 的边界是「审查判定本身」不是「所有外审相关的活」。判据看**任务实质**(准备/调研/编排 → 可 workflow; soundness 审查判定 → 外发 GPT Pro), 不看「是不是外审相关」。
