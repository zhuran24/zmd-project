---
name: verification-independent-backstop
description: "长上下文下 LLM 注意力会漏看 → 验证/确认/核对类任务不能只信 main 自己回忆或自审, 必须派独立 backstop (workflow/子代理); 且 backstop 主体必须是「被验证对象本身」不能换 proxy; 子代理报告的根因/数字 main 要自己核实。"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

2026-06-01 用户原话: "llm 的注意力机制现在在长上下文下很容易出现漏看的问题, 至少让 workflow 或者多个子代理去作为补充和托底"; 紧接着纠正 "你让它确认的主体是记忆树, 但我想让它检查的主体却是当前的这个 session …… 你把检查的主体弄错了"。

## 规则

1. **长上下文下 LLM 注意力会漏看**。**验证 / 确认 / 核对 / "是否完整 / 是否全做了 / 有没有遗漏" 类任务, 不能只信 main 自己的回忆或自审** —— 必须派 workflow / 独立子代理作补充托底。(U37)
2. **backstop 的主体 (被检查对象) 必须是「要验证的东西本身」, 不能换成 proxy。** 例: 验"本 session 内容是否全落盘 memory" → 主体 = **session 对话本身**(抽用户消息), **不是** 记忆树内部一致性 / git log / repo。proxy 只看得见文件改动, 漏掉**只存在于对话里**的偏好/决策/口头反馈。(U39/U40)
3. 子代理跑完报告的**根因 / 数字, main 要自己核实**, 不能直接转述未验证的 (U17 同源)。

## Why

本 session 自证: main 第一次派 backstop 就把主体弄错成"记忆树"(proxy), 报"落盘完整"实为假 —— 恰恰漏了**本条 working-preference 自己**; 用户两次纠正(U39 完整重发为 U40)才扳回"主体 = 当前 session 内容"。换对主体后独立 agent 立刻确认这条缺失。**这正是本规则要防的失误, 当时却没进 memory, 不记下次必复发。** 口头反馈无文件副产物, 任何 git/repo/记忆树-proxy 检查都抓不到 —— 只有以"对话本身"为主体的独立检查能抓。

## How to apply

- 遇 "确认 / 核实 / 查全 / 是否遗漏 / 是否都做了" 类任务 → **先问"主体是什么"**, 把**那个东西本身**喂给独立 agent, 别用代理信号代替。
- 验 "session 内容全落盘 memory" → 抽 transcript 用户消息 (`cc_context/tools/extract_user_turns.py` 抽 role=user 文本) 当主体, 独立 agent 逐条查 memory 覆盖。
- 别因"内容在我 context 里 / 我刚做的我知道"就自审了事 —— 长 context 下我会漏。
- 子代理报告的 verdict/数字, 落 memory/commit 前 main 自己 grep/跑一遍核。
- 关联: [[external-review-reproducibility]] (外部模型单次有 variance; 本条是 "Claude 自己" 在长 context 不可信, 互补) / [[subagent-for-closed-loop-tasks]] / [[audit-verify-before-archive]] / [[memory-currency-protocol]]。
