---
name: subagent-model-by-weight
description: "子代理模型按任务具体难度/重量派 (2026-06-11 用户裁决): 轻活 sonnet / 重活 opus / 特别重要 fable; 不按任务类别套公式。取代旧'子代理默认 opus'规则。"
metadata: 
  node_type: memory
  type: feedback
---

2026-06-11 用户裁决, **取代** 旧的"子代理模型默认 opus"规则 (CLAUDE.md Conventions 同步已改)。

## 规则

派子代理 (Agent 工具 / Workflow 内 `agent()`) 时, 模型按任务的**具体难度和"重量"**定, 不按任务类别套公式:

- **轻活 → sonnet**: 小资料搜索、轻量代码查询、轻量/小功能代码编写这一档的重量
- **重活 → opus**: 调研、大范围多角度代码查询、重度/大模块代码编写这一档的重量
- **特别重要的任务 → fable** (claude-fable-5): 做错代价大、绝不能错的活

用户原话要点: "不要根据任务分类来派遣, 要根据任务的具体难度和'重量'来派遣, 意会就行不用照抄"。上面的例子是**示意刻度, 不是类别白名单** —— 同是"搜索", 轻的派 sonnet, 重的派 opus。

**Why**: 旧规则"默认 opus"是一刀切; 按重量派既不在轻活上烧大模型额度, 也不在重活/关键活上省错地方。

**How to apply**:
- 派遣前先掂这个活的真实重量 (步骤数 / 需要的判断深度 / 做错的代价), 再选档; 拿不准时往上取一档 (宁可 opus 跑轻活, 别 sonnet 跑重活)。
- 主会话当前模型是 fable, **"继承主会话模型"不再是默认正确做法** —— 轻活/重活要显式传 `model="sonnet"` / `model="opus"`; 只有特别重要的活才让它继承 (或显式 `model="fable"`)。
- Agent 工具无独立 effort/thinking-budget 旋钮, `model` 参数是控制力度的唯一硬杠杆 (软杠杆 = prompt 措辞)。
- **fable 子代理可能派不出 (2026-06-14 实测)**: 派 model=fable 的 subagent 报 `model claude-fable-5 may not exist or you may not have access` → 当场退 opus 重派, 别卡住。可能 transient/额度; 若持续派不出, 重活/关键活默认 opus 足够 (fable 是更优不是必须), 别因'特别重要必须 fable'而阻塞。

## 链
- [[agent-vs-workflow-dispatch]] — "派给谁"的选型框架; 本条管"派出去后用什么模型"
- [[subagent-for-closed-loop-tasks]] — 闭环活 spawn 时模型按本条定 (原"opus 默认"已被本条取代)
- [[design-phase-n-parallel-agents]] — 设计期 N 路并行属重活, opus 仍然对; paradigm 级特别重要可上 fable
