---
name: agent-vs-workflow-dispatch
description: "派遣方式选型: 非必要不用 Workflow; 外发 GPT Pro 首选 gpt_dispatch 自动化脚本 (2026-06-11 验收, 零 token), 插件通道 (Edge) 托底; 旧的形状二选一/三选一指导仅在'确实必要'时参考。"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> **GPT Pro 外发审查/委托的完整规则(核心裁决 / 四条发送设置 / 打包 `build_v80_single_win.py` / dispatch 通道 + 两层托底链 / 降级判据 / 并发 / scope 厘清)见 [[no-workflow-use-chrome-gpt-review]] 子树,本节不复述以防双处漂移**(议会 redundancy 收口 2026-06-14:同话题别抄副本、用 wikilink)。
> **不变的要点(读全规则去子树)**: ① 非必要不用 Workflow 做 **soundness 审查这个动作**、审查/外审/委托实现外发 GPT Pro;② 但 Workflow 本身**已放开**(`approval_required=false`,见 [[workflow-approval-not-avoidance]]),别把"非必要不用 Workflow"误读成"默认单 Agent";③ 本裁决**只管「判 soundness 的动作」**,准备/调研/编排可 workflow fan-out(判据看任务实质,见 [[no-workflow-scope-clarification]])。

2026-06-01 用户开了 Ultracode 并指明"这个复杂任务派 workflow 比较好"。沉淀派遣方式选型的偏好。(2026-06-10 起按上方裁决收紧。)

## Ultracode 默认偏好

用户开 Ultracode = 让我**优化最穷尽、最正确的答案, 不是最快最省**: 实质任务优先用多代理编排, token 成本不是约束。它**不碰工具 schema, 只改 main 的默认倾向**。开着时实质活默认走 Workflow / 多代理 + 对抗核验; 只有对话/琐碎 turn 才单干。关了就回到"显式 opt-in 才用 workflow"。

## Agent vs Workflow 按任务形状二选一

- **单条闭环、不需中途决策、可验证** → 直接 `Agent` 工具 spawn (轻, 见 [[subagent-for-closed-loop-tasks]])。
- **要扇出 N 路 / 流水线 / 循环 / 对抗核 (find→verify→synthesize)** → `Workflow` (确定性编排 + 结构)。
- **Workflow 有 `resumeFromRunId` 断点续跑** (已完成 agent 缓存秒回), **后台 Agent 无 resume, 线程重启得整个重派** —— 长/贵的多步活优先 Workflow (见 [[windows-powershell-harness-pitfalls]] 后台代理不稳)。两者都怕线程重启丢进程内状态。

## dispatch 方式三选一 (派给谁)

- **线性已知内容 (如"把本线程发生的事落盘 memory") → main 自己最合适**: 没有散落信息可并行发现, 子代理还没有本线程 context, 派出去反而费 + 丢细节。
- **发现散落信息 (查全/审计/跨多文件核对) → workflow / 多代理**: 正是注意力会漏看、需独立托底的场景 (见 [[verification-independent-backstop]])。
- **机械活 (批量改/跑测试/格式化) → 子代理** (模型按 [[subagent-model-by-weight]] 重量降档)。

**压缩上下文前**把本线程发生的事更新进记忆树是常规仪式 —— 这属"线性已知内容", main 自己落, 别派。

**Why**: 选错 dispatch 方式要么浪费 (该自己干的派出去丢细节), 要么漏看 (该派独立托底的自己回忆)。
**How to apply**: 先判任务形状再选工具; Ultracode 开着时默认编排 + 穷尽。关联 [[subagent-for-closed-loop-tasks]] [[design-phase-n-parallel-agents]] [[verification-independent-backstop]] [[long-op-background-mode]]。

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[main-merger-scope-creep-bias]] — N 并行 merge 步的 scope bias
