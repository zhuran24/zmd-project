---
id: memory-db-cross-session-push-conflict
kind: pitfall
title: 多会话提交共享 memory.db 会触发非快进二进制冲突
summary: 多个会话或 checkout 同时把 cc_memory/memory.db 提交到同一 main 时，第二个 push 容易遇到 non-fast-forward，且 SQLite 二进制文件无法被 git 自动合并。
error_regex: ["\\$ [^\\n]*git[\\s\\S]{0,800}non-fast-forward", "\\$ [^\\n]*git[\\s\\S]{0,800}CONFLICT[^\\n]{0,160}memory\\.db"]
scope:
  domains: [cc-memory-git]
  paths: [cc_memory/memory.db]
  symbols: []
status: active
priority: P1
triggers:
  intents: [memory-write, git-push, conflict-resolution]
  keywords: [memory.db, cc_memory, non-fast-forward, SQLite, 二进制冲突, 多会话, 多 checkout, push main]
  negative_keywords: []
  paths: [cc_memory/memory.db]
  symbols: []
  error_regex: ["\\$ [^\\n]*git[\\s\\S]{0,800}non-fast-forward", "\\$ [^\\n]*git[\\s\\S]{0,800}CONFLICT[^\\n]{0,160}memory\\.db"]
  examples:
    - 多个 Codex 会话都改了 cc_memory/memory.db 后准备 push 到 main
    - push 失败提示 non-fast-forward，并且变更里包含 cc_memory/memory.db
    - 合并 main 时看到 memory.db 冲突，想知道能不能让 git 自动合并
activation:
  layer_hint: L1
  must_know: false
  reason: 共享 SQLite 记忆库的并发提交冲突不能按普通文本冲突处理。
provenance:
  op: record
  reason: 记录 2026-06-19 并发会话提交同一 memory.db 到 main 的实测失败模式。
  evidence: ["2026-06-19 实测：并发会话各自 commit 同一 cc_memory/memory.db 到 main，第二个 push 报 non-fast-forward，SQLite 二进制无法自动合并"]
updated_at: "2026-06-26"
---
当多个会话或多个 checkout 都修改并提交同一个 `cc_memory/memory.db` 到同一条 `main` 时，第二个推送者很容易遇到 `non-fast-forward`。即使随后拉取或合并，`memory.db` 是 SQLite 二进制文件，git 不能像文本一样自动三方合并，冲突会落到人工选择版本或重新生成变更的问题上。

遇到这个信号时，不要把它当成普通代码冲突来手工拼接，也不要随意用某一边覆盖共享记忆库。正确用法是先停止 push/merge 流程，确认哪一个 memory 写入是权威变更，再通过项目规定的 `python cc_memory/mem.py ...` 流程重新落库、检查并导出，最后只提交经过验证的一份 `cc_memory/memory.db`。
