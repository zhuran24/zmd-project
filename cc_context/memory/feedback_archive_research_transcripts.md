---
name: archive-research-transcripts
description: 每轮 agent 调研完，原 JSONL 转录要从 Temp 复制到项目 docs/，否则会话结束就丢
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---
每完成一轮 Agent 调研（≥3 个 agent 跑完），**立刻把 Temp 目录里的 `.output` 文件复制到项目 `docs/research/agent_transcripts/`**，并维护 `docs/research/INDEX.md` 索引。**不能等"调研都做完再统一归档"**——会话压缩或意外退出会让 Temp 文件永久丢失。

**Why:** 用户 2026-05-08 直接问"搜到的东西有存下来吗，特别是子代理们的原消息"。检查发现 61 个 agent 输出全在 `C:\Users\22957\AppData\Local\Temp\claude\<session>\tasks\` 下——这是 session-scoped 临时目录，session 结束清理。每个 .output 是完整 JSONL 转录（prompt + thinking + tool uses + final report），是宝贵研究素材，但默认根本没保留路径。Codex 时代写的脚本都会忘（已在另一条 memory 里记录），调研产物更容易丢。

**How to apply:**
- 每轮 agent 全部完成（或任意时刻），跑：
  ```powershell
  robocopy "$env:LOCALAPPDATA\Temp\claude\D--claude-pj-zmd\<session-id>\tasks" `
           "docs\research\agent_transcripts" *.output
  ```
  或 bash 等价 `cp`
- 同步在 `docs/research/INDEX.md` 加新一行：`| <agent_id> | <topic> | <outcome 1 行> |`
- 命名规则：保留原 `<agent_id>.output` 文件名（不要重命名，方便交叉引用）
- 多轮调研项目：在 INDEX 里按 Round 分段
- 这是 cheap 操作（Temp 总大小通常 <1MB），不要犹豫
- session 结束前最后做一次 final sync 兜底

**Bonus**：transcript 里 agent 的 thinking 段经常含跟最终 report 不同的洞察（某些被丢弃的方向、不确定性表达等），归档后可以二次挖掘。

## 链 (补连 2026-06-01)
- [[research-roi-metric]] — 调研价值/归档
