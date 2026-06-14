---
name: no-gpt-send-settings
description: "外发 GPT 的四条发送设置:模型选 Pro·进阶(进阶专业)、发在「终末地」Project、新任务默认开新会话、包走 Project 文件页(来源区)不随消息发附件(2026-06-12 owner 裁决,删旧快照保留依赖包,prompt 指认文件名+sha256)"
metadata:
  node_type: memory
  type: feedback
---

> 事实依据: [[fact-conversation-state-is-window-local]]

**发送设置(用户指定):**
1. 模型选 **Pro·进阶**(= GPT Pro 扩展模式;中文 UI「进阶专业」就是它,不用另找开关)
2. 发在 ChatGPT 的**「终末地」Project** 里面
3. **非必要不用老窗口**——新任务默认开新会话,只有同一任务的连续追问才留原会话
4. **包走 Project 文件页(来源区), 不随消息发附件 (2026-06-12 owner 裁决)**: 新项目快照包上传文件页后**删掉老的快照包**; 但依赖包 `zmd_py313_linux_x86_64.zip` (wheels) **永远不删**。prompt 里指认文件区的包文件名 + sha256 让 GPT 开工前校验, 并写明"本会话不带消息附件,一切从 Project 文件区取"。**Why**: Codex 时代包一直放文件页、从未触发过风控; 这轮风控全发生在会话内反复传大附件模式下——疑似诱因, 切回文件页模式。⚠️ **踩坑教训**: 探删除时把 owner 手动传的好快照包误删了 (删除 UI 无确认框、点即生效) → **别在生产数据上"试探"不可逆 UI**。
