---
id: memory-db-feature-branch-stale-do-ops-on-main
kind: pitfall
title: feature 分支的 memory.db 可能早于 main → 记忆读写要在 main 权威库做
summary: 在 feature 分支上 search/read cc_memory 可能【假 no-match】,因为该分支的 cc_memory/memory.db 比 main 旧、缺 main 上新建的条目;cc_memory 读写应切到 main 权威库做。
error_regex:
  - "\\A(?:# cwd: [^\\n]*\\n)?\\$ [^\\n]*\\.claude/worktrees/[^\\n]*mem\\.py +(?:boot|search|read|find|impact|suggest|prune|relations|review-relation|add-event|set-fact|add-entry|link|supersede|archive|unarchive|propose|rebuild-embeddings|check|export|finalize|init)\\b"
  - "\\A# cwd: [^\\n]*\\.claude/worktrees/[^\\n]*\\n\\$ [^\\n]*\\scc_memory/mem\\.py +(?:boot|search|read|find|impact|suggest|prune|relations|review-relation|add-event|set-fact|add-entry|link|supersede|archive|unarchive|propose|rebuild-embeddings|check|export|finalize|init)\\b"
scope:
  domains: [cc-memory-branch]
  paths: [cc_memory/memory.db]
  symbols: []
status: active
priority: P1
triggers:
  intents: [memory-write, memory-read, memory-search, branch-switch]
  keywords: [memory.db, cc_memory, search no matches, 假 no-match, feature 分支, 权威库, main, 跨分支, 分叉, 搜不到刚建的条目]
  negative_keywords: []
  paths: [cc_memory/memory.db]
  symbols: []
  # 2026-08-03 二次收窄(审查打回):第一版用 `.claude/worktrees/|git -C |git checkout |git switch`
  # 做工作副本语境,实测两头都错——`git -C <repo> stash -- cc_memory/mem.py` 里的 mem.py
  # 只是 pathspec、不是记忆操作(假阳性),而真正在 worktree 里跑相对路径
  # `python cc_memory/mem.py search ...` 反而漏报(命令行里根本没有 worktree 字样)。
  # 现在两支:① 命令里的 mem.py 路径本身在 .claude/worktrees/ 下;② 由 hook 拼进
  # blob 的 `# cwd:` 行显示当前工作副本在 .claude/worktrees/ 下、且命令跑的是相对
  # 路径 cc_memory/mem.py。两支都要求 mem.py 后面紧跟一个真实子命令,git pathspec
  # (mem.py 后面没有子命令)因此不再命中。
  # 两支都用 \A 锚到 blob 开头(= hook 拼的 `# cwd:`/`$ 命令` 头两行),所以
  # 【读到一段引用了该命令的日志/文件】不会命中——只有真的跑了它才会。
  error_regex:
    - "\\A(?:# cwd: [^\\n]*\\n)?\\$ [^\\n]*\\.claude/worktrees/[^\\n]*mem\\.py +(?:boot|search|read|find|impact|suggest|prune|relations|review-relation|add-event|set-fact|add-entry|link|supersede|archive|unarchive|propose|rebuild-embeddings|check|export|finalize|init)\\b"
    - "\\A# cwd: [^\\n]*\\.claude/worktrees/[^\\n]*\\n\\$ [^\\n]*\\scc_memory/mem\\.py +(?:boot|search|read|find|impact|suggest|prune|relations|review-relation|add-event|set-fact|add-entry|link|supersede|archive|unarchive|propose|rebuild-embeddings|check|export|finalize|init)\\b"
  examples:
    - 在 feature/PR 分支上 mem.py search 自己之前建的条目却 no matches
    - 当前分支的 cc_memory/memory.db 比 main 旧、缺最近建的条目
    - 想在 feature 分支上更新记忆但条目都在 main 上
activation:
  layer_hint: L1
  must_know: false
  reason: cc_memory 的真相库在 main;feature 分支 memory.db 可能 stale,直接在其上读写会假 no-match 或写进分叉副本。
provenance:
  op: record
  reason: 记录 2026-06-30 在 pr2-5 分支上 search 本会话条目假 no-match 的实测坑。
  evidence:
    - "2026-06-30 实测：在 pr2-5-domain-frontier-gate 分支上 `python cc_memory/mem.py search` 找本会话在 main 建的 pr2-5 条目，返回 no matches；根因=pr2-5 的 memory.db 还是 d68bdc9 版、早于 main、缺那些条目"
    - "2026-08-03 普查 §3.5：旧 error_regex（`mem.py ... no match`）在 39 次唯一注入里占 8 次，8/8 是假警报——当时都在 main、工作树干净，卡片主张一次都不成立。跨 59 份转录、6260 条 Bash 结果复算：旧式 11 命中，改后 1 命中。"
    - "2026-08-03 审查复核：第一版收窄留下的那 1 条命中本身也是假阳性（命中源 `git -C /home/zhuran24/zmd-pj stash ... -- cc_memory/mem.py`，mem.py 是 git pathspec、不是记忆操作），且 worktree 内相对路径调用整类漏报。二次收窄改成「mem.py 后必须紧跟真实子命令」+ 用 hook 拼的 `# cwd:` 行覆盖相对路径调用。"
updated_at: "2026-08-03"
---
`cc_memory/memory.db` 是 SQLite 二进制,各分支各有一份、**不会自动跟 main 同步**。在一条 feature / PR 分支上做记忆操作时,该分支的 `memory.db` 可能是早先从 main 分出来的旧版本——比 main 落后好几个提交,**缺 main 上后来新建的条目**。

典型信号:在 feature 分支上 `python cc_memory/mem.py search`(或 `read <id>`)找一条你确定建过的条目,却返回 `no matches` / 找不到。别误以为条目没建成或丢了——大概率是**你站在 stale 分支的 memory.db 上**,而条目活在 main 的权威库里。

**撞错召回的触发形态已于 2026-08-03 收窄**(普查 §3.5):旧正则只认症状(`mem.py … no match`),而 cc_memory 现在基本是空库、搜不到才是常态——8 次触发 8 次假警报,当时都在 main、工作树干净。症状从工具输出里根本分不出真假;**能分出来的是「在哪个工作副本上做记忆操作」**,所以现在只认这两种形态:① 跑的 mem.py 本身在 `.claude/worktrees/` 下;② 当前 cwd 在 `.claude/worktrees/` 下、且跑的是相对路径 `cc_memory/mem.py`。两者都要求 `mem.py` 后面紧跟一个真实子命令(`search`/`read`/`set-fact`…),所以 `git … -- cc_memory/mem.py` 这种 pathspec 不再误弹。裸的 `mem.py … no matches` 不再强推——那条路留给关键词召回(卡还在,搜得到)。

第 ② 支依赖 `post_tool_error_recall.py` 把 `# cwd: <目录>` 拼进 blob 首行;**动那个拼法就要同步动这条正则**(否则 worktree 内相对路径调用整类漏报,那正是 08-03 审查抓到的漏)。已知残留:cwd 在 worktree 里、却用绝对路径跑 main 仓的 mem.py 时不弹——那本来就是正确做法,漏掉无害。

正确做法:**cc_memory 的真相库在 main,读写都去 main 做**。代码在 feature 分支时:① 先 `git checkout -- cc_memory/memory.db` 丢掉当前分支的水位印记,再 `git checkout main` 切过去做记忆(改完在 main 提交 memory.db + exports/MEMORY.md);② 若要边看 feature 分支代码边用 main 最新记忆,用 git archive/overlay 把代码与 main 记忆组合(见 [[git-archive-overlay-snapshot-no-branch-switch]]),别把 feature 分支的 stale memory.db 当真。与并发提交冲突坑 [[memory-db-cross-session-push-conflict]]、共享 index 坑 [[concurrent-session-shared-index-hazard]] 同属"共享/分叉 memory.db 的协作陷阱"族。
