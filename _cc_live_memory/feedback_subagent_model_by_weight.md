---
name: subagent-model-by-weight
index_summary: "wf/子代理默认 codex(owner 2026-06-16 裁决, 为质量多开 wf + codex 独立额度池); 非 wf 按难度派 sonnet 轻/opus 重/fable 关键, 不按类别. 额度纠正见正文(我之前在此写的 opus 额度那套是臆想、已删)."
description: "子代理模型选择。2026-06-16 owner 裁决: workflow 子代理默认用 codex(原话『wf 都用 codex 子代理』『以后就先一直用 codex』), 动机=为质量多开 wf(对抗验证/多视角)+ codex 走独立订阅额度池。其余(Agent 工具单发/codex 不胜任时)按 2026-06-11 规则按任务具体难度派: 轻活 sonnet/重活 opus/特别重要 fable, 按难度不按类别。⚠️ 我 2026-06-16 曾在本节写进一堆没核实的额度臆想(opus 额度紧/sonnet-opus 分池/5h opus 窗口/周五刷新/主会话省 opus), 被 owner 逐条否定、已删, 教训见 [[assumption-as-fact-then-backfill]]。"
metadata: 
  node_type: memory
  type: feedback
---

## 2026-06-16 修订 (owner): wf/子代理默认 codex

owner 裁决 **workflow 子代理(`agent()`/`agentType`)默认用 codex**, 续『以后就先一直用 codex』—— 不限 wf, 子代理一律优先 codex。原话『wf 都用 codex 子代理』。动机: **为质量多开 wf**(Workflow 多智能体对抗验证/多视角)+ codex 走独立订阅额度池、不占 Claude。codex 可信度已被双模型对照校准证实(见 [[memtree-restructure]]: codex 审查核心 finding 被 Claude opus 独立印证、且有独有发现)。

**额度事实(2026-06-16 owner 逐条纠正; 我之前在本节写的 opus 额度那套全是臆想、已删)**:
- **codex** 走 ChatGPT 订阅、独立额度池, 但**有 5 小时滚动额度**、会耗尽会恢复、周额度没问题(实测一连开几个 codex wf 后撞 codex `usage limit`、约数小时重置)。所以『一直用 codex』≠ 无限, 别一次性堆太多并发 codex wf、排着用。
- **Claude** 订阅额度是**整体一个池、所有模型共用**(不分 opus/sonnet 池)。owner 那句『这周额度剩 20%』是 Claude 这周整体额度紧(背景: 我起了个 opus 对照 wf 烧了 Claude)。
- **wf 里 codex agent 外层有一个 Claude sonnet 中介壳**(实测 `model=claude-sonnet-4-6`, 调 `mcp__codex__codex` 转发), 它烧 Claude 额度(token 小但非零); 重活(codex/gpt-5 读改审)那部分走 ChatGPT 订阅、不烧 Claude。
- **⚠️ 我删掉的臆想**(全是没核实当事实写进来的): 『opus 额度紧 / sonnet 和 opus 分额度池 / 5h opus 窗口 / 周五刷新 / 主会话 opus 要省』—— owner 明确否定『opus 额度我从没说有问题、你怎么转到 opus 上去』。教训 = [[assumption-as-fact-then-backfill]] / [[fact-self-report-is-not-evidence]]。

- **适用面**: 子代理一律优先 codex; 拿不准就 codex(除非 codex 不胜任该活)。
- **与下面 by-weight 的关系**: by-weight(sonnet/opus/fable) 是"用 Claude 子代理时按重量选档"; 默认换 codex 后, by-weight 退为 **codex 不适用时的回退**(codex 跑不动/需 Claude 特定能力/明确要 Claude 对照)。
- **Why**: codex = 独立模型(gpt-5.x)+ 走独立额度池 + 给对抗审查天然的模型多样性。机制见 harness 记忆「codex-cli-as-subagent」(repo 无此镜像)。

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
