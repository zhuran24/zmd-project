---
id: memory-db-feature-branch-stale-do-ops-on-main
# kind 归位记录(2026-08-03,P2 主批)。P2.2 曾把它从 pitfall 改成 decision——
# 不是重新定性,是被 schema 逼的:当时 zmem verify 规定「pitfall 卡必须有非空
# error_regex」,而本卡这一批正好退出了 error_regex 定向召回(见下方 triggers
# 注释)。那条规则编码的正是普查 §3.5 否掉的假设「坑=靠报错文本认出来」,于是
# 本批把规则放宽(zmem.py:kind == "pitfall" 分支不再有要求),这张卡随之改回它
# 语义上本来的类型。**不需要再借 kind 绕行。**
kind: pitfall
title: feature 分支的 memory.db 可能早于 main → 记忆读写要在 main 权威库做
summary: 在 feature 分支上 search/read cc_memory 可能【假 no-match】,因为该分支的 cc_memory/memory.db 比 main 旧、缺 main 上新建的条目;cc_memory 读写应切到 main 权威库做。
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
  # 2026-08-03 终局:本卡退出 error_regex 定向召回,空表是刻意的、别再填。
  # 三轮收窄的账:裸「mem.py … no match」→ 8 次触发 8 次假警报;第一版收窄后仅剩
  # 的 1 条命中还是假阳性(mem.py 只是 git pathspec);二次收窄靠 hook 往 blob 里
  # 拼 `# cwd:` 才把 worktree 内相对路径捞回来,代价是 12 张活 error-regex 卡里
  # 10 张能被一行普通 cwd 文本假触发。历史真阳=0。普查 §3.5 的总账(39 次唯一注入
  # 里 30.8% 自触发、53.8% 良性输出、真阳 3 次、唯一一次被采纳的触发本身还是假阳性)
  # 说明这是个高假阳机制,正确处置是退出赛道、不是继续雕正则。
  # 本卡其余触发面(keywords / intents / paths / examples)全部保留——卡有价值,
  # 只是不该靠错误文本定向召回;真要它就用关键词/意图召回,或 mem.py find。
  error_regex: []
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
    - "2026-08-03 收尾（本卡 error_regex 归零）：二次收窄依赖的 `# cwd:` 拼接经实测让 12 张活 error-regex 卡里 10 张能被一行普通 cwd 文本假触发（cwd=/tmp/MODEL_INVALID/repo + command=true + response=ok 就误弹了一张无关卡），而假命中会消费 seen-once 账本、把随后真正的 MODEL_INVALID 报错静默压掉。三轮收窄下来本卡历史真阳仍是 0，遂退出 error_regex 通道、拼接一并撤销。"
updated_at: "2026-08-03"
---
`cc_memory/memory.db` 是 SQLite 二进制,各分支各有一份、**不会自动跟 main 同步**。在一条 feature / PR 分支上做记忆操作时,该分支的 `memory.db` 可能是早先从 main 分出来的旧版本——比 main 落后好几个提交,**缺 main 上后来新建的条目**。

典型信号:在 feature 分支上 `python cc_memory/mem.py search`(或 `read <id>`)找一条你确定建过的条目,却返回 `no matches` / 找不到。别误以为条目没建成或丢了——大概率是**你站在 stale 分支的 memory.db 上**,而条目活在 main 的权威库里。

**本卡 2026-08-03 起不再靠撞错召回弹出**(`triggers.error_regex` 是空表,普查 §3.5 判定)。三轮收窄的结局值得记下来,免得下次有人又想"再收窄一次就好了":

1. 裸「`mem.py …  no match`」——8 次触发 8 次假警报(当时都在 main、工作树干净)。cc_memory 现在基本是空库,**搜不到才是常态**,症状从工具输出里根本分不出真假。
2. 收窄成"命令自带 worktree 语境"——仅剩的 1 条命中还是假阳性(`git … -- cc_memory/mem.py`,mem.py 只是 pathspec),同时 worktree 内跑相对路径的整类漏报。
3. 再收窄成"hook 把 `# cwd:` 拼进 blob 首行 + mem.py 后紧跟真实子命令"——捞回了漏报,代价是 12 张活 error-regex 卡里 10 张能被一行普通 cwd 文本假触发,而每次假触发都会吃掉那张卡本会话唯一一次提醒额度。

**历史真阳 0 次。** 结论不是"正则还不够准",是**这张卡的触发条件根本不在错误文本里**——错误文本只说"没搜到",说不了"你站在哪个副本上"。要它就走关键词/意图召回(下面的 keywords 全在),或者直接 `python cc_memory/mem.py find <id>` 看这个 id 到底在哪层。别再往 `error_regex` 里填东西。

正确做法:**cc_memory 的真相库在 main,读写都去 main 做**。代码在 feature 分支时:① 先 `git checkout -- cc_memory/memory.db` 丢掉当前分支的水位印记,再 `git checkout main` 切过去做记忆(改完在 main 提交 memory.db + exports/MEMORY.md);② 若要边看 feature 分支代码边用 main 最新记忆,用 git archive/overlay 把代码与 main 记忆组合(见 [[git-archive-overlay-snapshot-no-branch-switch]]),别把 feature 分支的 stale memory.db 当真。与并发提交冲突坑 [[memory-db-cross-session-push-conflict]]、共享 index 坑 [[concurrent-session-shared-index-hazard]] 同属"共享/分叉 memory.db 的协作陷阱"族。
