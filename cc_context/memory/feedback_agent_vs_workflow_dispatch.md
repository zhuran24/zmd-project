---
name: agent-vs-workflow-dispatch
description: "派遣方式选型: 非必要不用 Workflow; 外发 GPT Pro 首选 gpt_dispatch 自动化脚本 (2026-06-11 验收, 零 token), 插件通道 (Edge) 托底; 旧的形状二选一/三选一指导仅在'确实必要'时参考。"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> **2026-06-10 用户裁决 (优先于下面全部旧指导; 当晚二次裁决又精简了规则集)**: **非必要不要用 Workflow,特别是审查类任务**。审查/外审/委托实现类活外发给 GPT Pro (chatgpt.com) 完成。**发送设置: ① 模型选 Pro·进阶 (= GPT Pro 扩展模式, 中文 UI 叫「进阶专业」); ② 请求发在 ChatGPT 的「终末地」Project 里面; ③ 非必要不用老窗口 — 每个新任务默认开新会话, 只有同一任务的连续追问才留在原会话**。
> **外发通道 (2026-06-11 起首选自动化脚本, 完整验收通过)**: `python cc_context\review\gpt_dispatch\dispatch_gpt_task.py --pack --prompt-file <md>` — 打包→上传→发送→双信号等完成→收附件全自动, 本地跑零 token; 挂了 `--resume <会话URL>` 续; 附件 404 自动救援 (追问让 GPT 重新生成); 退出码/降级阶梯见 CLAUDE.md runbook + gpt_dispatch/README.md。**托底通道 = Claude in Chrome 插件** (插件浏览器实际是 Edge 且已登录, 与脚本的专用自动化 Chrome 是两条独立通道): 脚本 exit 5 (疑似 Pro 静默降级, 判据 = 真实任务完整生成 <1min, 无任何明面标注) 时 CC 改走插件手动发收。
> **打包规则 (唯一存留的打包规则)**: **除缓存文件外全项目打进去** (排除 .git/__pycache__/.pytest_*/.ruff_cache/.venv/.upstream_clones/*.pyc/输出 zip/prompt 文件)。build 脚本 `cc_context/review/build_v80_single_win.py` (单包自包含, gpt_dispatch --pack 调用; 分卷版已归档 review/archive/)。**老的审查打包规范 (no-priming/7-section prompt 模板/armor/7z 策略/数据完整性细则等) 已全部废除**, 原文备份在 `cc_context/memory_archive/` 与 `cc_context/review/archive/`。
> **Why (当日实测教训)**: 对抗审查 workflow 跑了 38 分钟还撞 API stream 超时; 审查 agent 并发跑 pytest 互删仓库根 `.pytest_tmp` 污染全量测试; token 成本高。外部 GPT Pro 沙盒能解包跑 pytest 自验, 更稳更省; 自动化脚本再把"CC 手动操作浏览器"这截 token 也省掉。
> **How to apply**: 默认单干或 Agent 子代理; "必要"= 用户明确点名要 workflow, 或任务确实离不开本地多路编排且无法外发。给 GPT 的 prompt 直接讲任务+约束+交付物即可, 不再套旧模板。

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
- **机械活 (批量改/跑测试/格式化) → 子代理** (可降模型省额度)。

**压缩上下文前**把本线程发生的事更新进记忆树是常规仪式 —— 这属"线性已知内容", main 自己落, 别派。

**Why**: 选错 dispatch 方式要么浪费 (该自己干的派出去丢细节), 要么漏看 (该派独立托底的自己回忆)。
**How to apply**: 先判任务形状再选工具; Ultracode 开着时默认编排 + 穷尽。关联 [[subagent-for-closed-loop-tasks]] [[design-phase-n-parallel-agents]] [[verification-independent-backstop]] [[long-op-background-mode]]。

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[main-merger-scope-creep-bias]] — N 并行 merge 步的 scope bias
