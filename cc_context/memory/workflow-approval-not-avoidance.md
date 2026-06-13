---
name: workflow-approval-not-avoidance
description: Workflow 申请≠回避理由; 报备的本意是用前说一声不是别用; 当前 approval_required=false 该用就用
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

owner 2026-06-13 纠正: 我把"用 Workflow 前要申请"误读成了**回避理由** —— 逻辑变成"因为要申请所以干脆别用 wf", 导致 wf 使用频率大幅下降。owner 的本意是**报备**: "我要用 wf 了 → 用前打个招呼说一声 (跑什么 / 几个 agent / 预估 token)", 这是说明不是障碍。

**当前状态**: `C:\Users\22957\cc_watchdog\workflow_approval.json` 的 `approval_required = false` (owner 放开, 类比 owner_sleep 离线开关)。该用 Workflow 就直接用, 用前报备一句即可, 不阻塞不等同意。

**Why**: 申请/报备的设计目的是「让 owner 知道我要派多少 agent、烧多少 token」, 不是「给 wf 设门槛让我退回单代理」。把它当门槛 = 误读, 导致该用编排的场景退回低效手段 (单代理/手动)。

**How to apply**: 想用 wf 时查 workflow_approval.json — false → 报备一句直接调; true → 正式申请等同意。该不该用 wf 看**任务实质** (确定性多智能体编排 / 大范围 fan-out / 对抗式交叉验证 / 单上下文装不下), 不看"要不要申请"。仍不无脑每个任务都跑 wf (trivial/对话类直接做)。全局规则已同步全局 CLAUDE.md「Workflow 使用规则」段。相关: [[no-workflow-use-chrome-gpt-review]] (审查任务路由是另一回事: 审查/外审默认外发 GPT 不开本地审查 wf, owner 没改这条; 但别的可编排任务别因申请回避 wf)。
