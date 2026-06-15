# Memory agent guide

这份文件给新会话里的 agent 用。不要先读完整系统设计，先按这里跑。

## 一条命令启动

```bash
python cc_context/tools/memgraph.py bootstrap
```

它会告诉你：当前记忆系统是否健康、入口文件读哪些、改记忆时该用哪些命令、哪些规则不能碰。

## 日常读取

先读 `cc_context/memory/MEMORY.md`。它是机器生成索引，只负责告诉你有哪些节点和每个节点的短摘要。需要细节时再打开对应 Markdown 节点。

不要只靠肉眼把 `[[link]]` 当成最终依赖结论。当前系统会从 frontmatter、overlay 和正文 wikilink 推断 typed edge：entry 指向 fact 默认是硬依赖，只有纯 `相关/参见/see also` 列表会降成软引用。真正要信的是 `memgraph check/impact` 跑出来的图。

## 改记忆时

先保存来源，再提变更，再看影响面：

```bash
python cc_context/tools/memgraph.py add-event --source-type user_message --summary "一句话来源" --text "原始材料"
python cc_context/tools/memgraph.py propose-change --operation update_fact --touches fact-or-entry-id --reason "为什么要改"
python cc_context/tools/memgraph.py impact fact-or-entry-id
```

只改 `impact` 返回的受影响节点，加上必要的新事实和显式边。改完后：

```bash
python cc_context/tools/memgraph.py freshness --accept changed-node-id
python cc_context/tools/memgraph.py index --apply
python cc_context/tools/sync_knowledge.py --check
```

## 什么时候不能自己猜

如果出现下面任一情况，先停在变更提案，不要直接写：

- 不知道一条边是硬依赖还是弱相关。
- 事实像是时间变化，而不是同一时间冲突。
- 一个改动影响面突然很大。
- 需要写 active harness。
- 新节点没有清楚的 description、index_summary 和来源。

## 一句话心智模型

原始事件是证据，事实是骨架，条目是给 agent 读的视图，typed edge 是神经。改骨架前先看神经连到了哪里。
