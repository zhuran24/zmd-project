---
name: fact-conversation-state-is-window-local
description: "抽象事实: GPT/LLM 会话状态只活在当前窗口/线程/项目材料与显式附件里; 跨新会话不携带隐式记忆,所以新任务隔离和 opsec 威胁面都必须按窗口局部状态推导。"
metadata:
  node_type: memory
  type: fact
---

## 抽象事实

外发 GPT/LLM 的可用状态是窗口局部的：当前会话上下文、Project 来源区/附件、显式 prompt、该工具实际可见的文件。新会话不会继承旧窗口的隐式记忆或口头背景；跨窗口能共享的只有被明确放进 Project/附件/文件系统/记忆树的东西。

这个事实同时推出两个方向：新任务默认开新会话可以减少旧上下文污染；opsec 的真实威胁面也应按「哪些材料被显式放进这个窗口/Project」来算，不能凭空假设模型跨窗口记得或不记得某个仓库外信息。

## 首批投影

- [[no-gpt-send-settings]] — 新任务默认新会话,Project 来源区显式给材料。
- [[no-workflow-use-chrome-gpt-review]] — 审查外发 GPT Pro 时靠包/prompt 明示上下文。
- [[agent-vs-workflow-dispatch]] — 外发任务的窗口/Project/包是显式状态边界。
