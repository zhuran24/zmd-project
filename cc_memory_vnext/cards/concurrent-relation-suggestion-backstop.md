---
id: concurrent-relation-suggestion-backstop
kind: pitfall
title: cc_memory Stop backstop 报"N 条关系建议待审"——多半是并发别会话条目渗进来的,本地 reject 清掉、别提交 memory.db
summary: cc_memory 的 Stop backstop 报"N relation suggestion(s) await review"时,这些建议常【不是本会话的工作】——而是并发会话(如 PR2/分支线程)写的条目,经你 git pull 合并进 memory.db 后,关系引擎自动给【它们的条目】生成的建议。处置:先 `mem.py relations` 看 source 条目;若全属别会话,`review-relation <id> --reject` 整段 + `finalize --no-gpu` 本地解锁 backstop,【不要为此提交/push memory.db】(避免替别会话条目策展 + memory.db 二进制跨会话冲突)。
error_regex: ["relation suggestion\\(s\\) await review", "cc_memory backstop"]
scope:
  domains: [cc-memory-git, cc-memory-maintenance]
  paths: [cc_memory/memory.db]
  symbols: []
status: active
priority: P1
triggers:
  intents: [memory-backstop, relation-review, stop-hook-blocked]
  keywords: [relation suggestion, await review, backstop, 关系建议, 待审, finalize, review-relation, 并发会话, memory.db]
  negative_keywords: []
  paths: [cc_memory/memory.db]
  symbols: []
  error_regex: ["relation suggestion\\(s\\) await review", "cc_memory backstop"]
  examples:
    - Stop hook 报 cc_memory backstop 20 条关系建议待审,要不要 finalize
    - 回合末被 cc_memory 关系建议挡住,这些建议是我的吗
    - 并发会话往 memory.db 写了条目,关系建议堆进我的回合了
activation:
  layer_hint: L1
  must_know: false
  reason: 把别会话条目的自动关系建议当成自己的工作去 accept/提交,会替别会话策展并制造 memory.db 跨会话冲突。
provenance:
  op: record
  reason: 2026-06-28 本会话 Stop backstop 连报 20/40/20 条,逐条查 source 全是并发 PR2 分支线程的条目(pr2-b-codex / close-kernel / soundness / precompact-trigger 接线会话),非本会话工作。
  evidence:
    - "本会话:relations source 全是 entry:pr2-b-codex-.../close-kernel-.../soundness-opus-codex-... 等别会话条目"
    - "python cc_memory/mem.py read memory-db-cross-session-push-conflict --body(只覆盖 push 冲突,不覆盖这种 backstop 污染)"
updated_at: "2026-06-28"
---
本仓库常有并发会话(PR2/分支线程)往同一条 `cc_memory/memory.db` 写条目。你 `git pull --rebase` 自己的改动时会把它们的条目合并进本地 memory.db,关系引擎随即给【它们的条目】自动生成 `RELATED_TO`/`DEPENDS_ON` 建议。这些高分未审建议会触发 Stop backstop("N relation suggestion(s) await review"),挡住你的回合结束——但**它们不是你这回合的记忆工作**。

处置(确认来源 → 本地解锁,别策展别人的):
1. `python cc_memory/mem.py relations` 看每条的 source 条目(`entry:X --REL--> entry:Y` 里的 X)。
2. 若 source 全是别会话的条目(不是你这会话 add 的)→ `for id in <范围>: python cc_memory/mem.py review-relation <id> --reject --reason "..."` 整段 reject(declining 加边 = 不替别会话条目策展),再 `python cc_memory/mem.py finalize --no-gpu`。backstop 即解。
3. **关键:别为此 `git commit`/`push` memory.db**——① 你只是清队列、没产出值得持久化的记忆;② 并发会话正活跃写 memory.db,推你的 reject 大概率撞二进制非快进冲突(见 `memory-db-cross-session-push-conflict`);③ 你的本地 reject 下次 pull 可能被覆盖、得重做,这是过渡期的固有摩擦,认了即可。
4. 只有当**你自己** add 了值得持久化的条目、且 `git fetch` 确认 origin 没动(0/0 干净 FF)时,才 targeted commit memory.db。
