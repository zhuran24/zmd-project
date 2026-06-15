---
name: record-tool-entry-points
index_summary: "refresh/sync 脚本写完立刻在 CLAUDE.md 加 runbook 段."
description: 自己写的运维脚本要在 CLAUDE.md 加 runbook 段，不然下次会忘
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---
每次写完一个**非一次性的运维脚本**（refresh/sync/migrate 等会反复用的），**立刻在项目根 CLAUDE.md 加一段 "Maintenance scripts" 或 "Runbook" 索引**。脚本本身的存在不等于未来能找到——上下文压缩后只有 CLAUDE.md 还会自动加载。

**Why:** 用户在 2026-05-08 直接指出："Codex 自己写的脚本自己都会忘"。Codex 在 4 月份写了大量 `scripts/build_phase3b_*.py`、`scripts/snapshot_endfield_calc.py` 等工具，但因为没有顶层索引文档，后续 session 看到旧脚本经常不知道是干嘛的、要不要再用。同样的事情我刚才差点重演——写了 `refresh_endfield_calc_snapshot.py` 和 `refresh_industrial_planner_bases.py`，如果没有 CLAUDE.md 入口，下次上游更新时新的 Claude session 大概率又会手动复制文件。

**How to apply:**
- 写完脚本（≥30 行带 argparse 的）→ 在 CLAUDE.md 的 `## Commands` 之后或 `## Maintenance scripts (runbook)` 段加一条
- 一条条目格式：脚本路径 + 一行用途 + 关键参数 + 重要边界（如"不会动 X / 不会自动改 Y"）
- 一次性脚本（debug 用、跑一次就丢）不需要进 CLAUDE.md
- 同时写测试（如果脚本读外部数据），并让测试**用 metadata 而不是 hardcode 数字**——这样脚本下次跑完不会破坏测试
- 反过来，看到 CLAUDE.md 缺索引但 scripts/ 里堆了一堆运维工具时，主动补一段——这是给未来自己/同行清扫战场

## 链 (补连 2026-06-01)
- [[archive-research-transcripts]] — 过程记录
