---
name: no-gpt-pro-outsource-core
description: "用户裁决(2026-06-10):非必要不用 Workflow 多代理编排;审查/外审/委托实现类任务用 Claude in Chrome 插件发到 chatgpt.com 让 GPT Pro 做;GPT Pro 沙盒能解包/装离线 wheels/跑 pytest 自验"
metadata:
  node_type: memory
  type: feedback
---

用户裁决:**非必要不用 Workflow 多代理编排**(即使 Ultracode 开着)。审查、外审、委托实现类任务用 Claude in Chrome 插件发到 chatgpt.com 让 GPT Pro 做。zmd 项目 v22-v79 全是 GPT 外审的,GPT Pro 沙盒(Python 3.13)能解包、装离线 wheels、跑 pytest 自验,实现任务也能整包委托。

**Why:** 本地审查 workflow 实测 38 分钟 + API stream 超时挂 critic + 审查 agent 并发跑 pytest 互删 `.pytest_tmp` 污染全量测试;GPT Pro 外发更稳更省额度。老审查规范是几十轮外审循环时代的产物,用户裁决"现在不用这么麻烦了"。

**How to apply:** 默认自己干或单个 Agent 子代理;"必要" = 用户明确点名要 workflow,或任务确实离不开本地多路编排且无法外发。委托实现的交付物拿回来后:本地 apply → check 脚本 + 目标测试 → 独占全量复验 → **`python scripts/preflight_gate.py --ci --base-ref HEAD~1` 全 gate(必跑!pytest 盖不到 frozen hash/行尾/记忆树三类检查,漏跑 = push 即 CI 红 + 邮件轰炸,V80 实测教训)** → 推锚易漏点复核 → commit,不盲信关键论证。外发 prompt 的锚定清单要含:若改 frozen artifact,`preflight_gate.py::FROZEN_ARTIFACTS` sha256 同批推进;要求 GPT 产物 LF 行尾。

相关:[[zmd-project-entry]]
