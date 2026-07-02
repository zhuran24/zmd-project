# Agent 记忆系统重构会话整理

日期：2026-06-26  
整理范围：本会话中围绕「Agent 记忆系统」的调研、审查、反思、重构方向、已生成产物与后续计划。  
说明：本文是结构化整理，不是逐字聊天记录。重点保留设计判断、问题定位、方案演进、最终结论和后续执行路径。

\---

## 1\. 起点：为什么旧式条目记忆不够

最初讨论的问题是：很多 Agent 记忆系统只是一条一条地存「记忆条目」。例如条目 A、B、C 分别记录不同内容，但它们背后可能共同依赖同一个事实 F1；条目 B、C 又可能共同依赖另一个事实 F2。

如果只存条目，会出现一个根本问题：

```text
一个事实变化后，所有依赖这个事实的条目都应该更新，
但系统不知道哪些条目依赖它。
```

旧式系统只能靠使用者或 Agent 自己全库扫描、自己联想、自己 grep。这会让更新成本很高，而且会随着记忆数量增长越来越不可靠。

真正需要的是：

```text
条目 entry 和事实 fact 是多对多关系。
事实变了，系统能反查受影响条目。
条目变了，系统能知道它依赖哪些事实。
新增记忆时，系统能主动找候选相关项。
```

核心诉求不是“把记忆连成图”这么简单，而是让系统承担关系维护的工作，降低对当前使用者或当前 Agent 能力的依赖。

\---

## 2\. 初步调研：已有方向和相近系统

围绕这个想法，调研过几类相近方向。

### 2.1 Temporal / Knowledge Graph Agent Memory

相近产品和研究方向包括：

```text
Graphiti / Zep
Mem0
Cognee
Letta
LangMem
GraphRAG
```

这些系统大多已经意识到长期记忆不能只是向量库，需要：

```text
实体
事实
关系
时间
来源
检索增强
```

其中 Graphiti / Zep 一类的 temporal knowledge graph 最接近：它们强调时间化事实、来源追溯、增量构图，以及把会话数据转成图结构。

### 2.2 Truth Maintenance / Provenance / Incremental View Maintenance

从更老的系统设计角度看，这个问题和几个经典概念相关：

```text
truth maintenance / reason maintenance
provenance
incremental view maintenance
```

它们共同关心的是：

```text
一个结论依赖哪些前提？
前提变化后，哪些结论需要重算？
数据从哪里来？
能不能只更新受影响部分，而不是全量重算？
```

这正好对应记忆系统里的：

```text
facts -> entries
facts -> derived facts
events -> facts
change -> affected nodes
```

\---

## 3\. 第一版理想架构：事实、条目、事件、边

早期提出过一个比较完整的模型：

```text
原始事件层 events
实体层 entities
事实层 facts / fact versions
条目层 entries
依赖边层 typed edges
变更事务 changes
```

### 3.1 原始事件层

原始事件是来源：用户说过的话、工具返回结果、文件内容、外部材料、Agent 操作记录等。它应该尽量只追加，不重写。

作用：回答“这条事实到底从哪里来”。

### 3.2 事实层

事实不应该只是自然语言句子，而应该至少带有：

```text
subject
predicate
value
status
valid\_from / valid\_to
confidence
source event
version / supersedes
```

例如：

```text
subject: user
predicate: prefers\_drink
value: tea
status: active
source: event\_xxx
```

旧事实不是直接删除，而是变成 superseded / inactive / disputed。

### 3.3 条目层

条目是给 Agent 读的自然语言视图。它依赖事实，但不应该自己成为唯一真相。

例如：

```text
用户现在偏好喝茶；过去曾说过喜欢咖啡，但该偏好已过期。
```

这个条目应该显式依赖：

```text
DEPENDS\_ON fact\_current\_drink\_preference
MENTIONS fact\_old\_drink\_preference
```

### 3.4 类型化边

边不能只有 `\[\[wikilink]]`。需要区分：

```text
DEPENDS\_ON      硬依赖，目标变了来源必须重审
DERIVED\_FROM    推导关系
SUPERSEDES      替代关系
CONTRADICTS     冲突关系
SUPPORTS        支持关系
MENTIONS        提到但不硬依赖
RELATED\_TO      弱相关，只用于检索
```

其中只有硬边触发更新传播。

\---

## 4\. 第一次项目审查：旧系统的真实问题

用户上传了旧项目快照 `zmd\_snapshot\_0fcea5e2.zip`。审查后发现，它不是一个真正的事实-条目依赖系统，而更像一个 Markdown 记忆树治理系统。

主要问题如下。

### 4.1 事实层只是概念标签

旧系统有 `fact\_\*.md`，但这些 fact 更像抽象原则或标签，不是结构化事实对象。它们缺少：

```text
subject / predicate / value
status / version
source events
valid\_from / valid\_to
confidence
```

### 4.2 wikilink 不是 typed edge

旧系统大量依赖 `\[\[...]]`，但 wikilink 不表达边类型。

系统不知道某条链接是：

```text
DEPENDS\_ON
MENTIONS
RELATED\_TO
BACKGROUND
```

因此不能安全地进行影响面传播。

### 4.3 多棵树同步导致系统臃肿

旧系统存在多个记忆面：

```text
cc\_context/memory/
\_cc\_live\_memory/
cc\_context/harness\_memory\_snapshot/
cc\_context/harness\_memory\_harvest/
cc\_context/knowledge/MEMORY.generated.md
```

这会把问题从“记忆关系维护”变成“多副本同步治理”。

### 4.4 freshness gate 有逻辑洞

旧 `check\_description\_freshness.py` 通过比较 body/summary hash 试图判断摘要是否过期，但会漏掉“第二次 stale edit”。

问题模式：

```text
baseline: body0, summary0
第一次修改: body1, summary1
第二次修改: body2, summary1
```

如果基线没有更新，它可能仍然认为 summary 已经变过，从而不报错。

正确逻辑应该是：

```text
只要 body hash 与 accepted baseline 不一致，就进入 DIRTY，直到显式 accept。
```

### 4.5 旧 generator 不是完整 lockfile

旧 `gen\_memory\_index.py` 只刷新摘要行，不锁完整索引结构。它不能证明：

```text
节点是否该出现
分组是否正确
顺序是否正确
标题是否同步
缺 index\_summary 是否被静默兜底
```

### 4.6 harness 写入路径危险

旧系统存在 repo -> active harness 的写入路径，且路径硬编码。问题是：

```text
repo 侧绿，不代表 live harness 侧健康。
旧工具可能写错 harness。
```

### 4.7 缺少事件层和变更事务层

旧系统只能说明“当前 Markdown 长这样”，很难回答：

```text
为什么改？
谁改的？
基于什么来源？
影响了哪些节点？
能否回滚？
```

\---

## 5\. Typed graph overlay 阶段：做了，但方向仍不对

随后尝试过 v2/v3/v4 类似 overlay 的方案：在旧系统旁边加：

```text
cc\_context/memory\_system/
cc\_context/memory\_graph/
memgraph.py
edges.jsonl
facts.jsonl
events.jsonl
changes.jsonl
bootstrap/onboard/doctor/read/impact
```

这解决了一些局部问题：

```text
有 typed edge 了
有 impact 查询了
有 bootstrap 入口了
有 freshness gate 了
有 generated MEMORY.md 了
```

但用户指出了关键问题：这不是重构，而是在旧系统上继续加外骨骼。

系统变成了三棵树：

```text
cc\_context/memory/          旧 Markdown 树
\_cc\_live\_memory/            live mirror
cc\_context/memory\_graph/    新图层
```

这违背了目标。真正想要的不是“旧系统更可治理”，而是“旧系统被替换”。

这个阶段的重要教训：

```text
图不应该是另一棵树。
图应该就是记忆系统本身。
```

\---

## 6\. Slim rewrite：单一真相 `memory.db`

在用户明确指出“不是我想要的效果”后，方案转向真正替换。

新的目标：

```text
一个真相源
一个工具入口
少量可重建视图
旧系统只归档，不参与运行
```

最终结构收敛为：

```text
cc\_memory/
  mem.py
  memory.db
  README.md
  schema.sql
  exports/
    MEMORY.md
  archive/
    old\_memory\_system/
```

唯一真相：

```text
cc\_memory/memory.db
```

生成视图：

```text
cc\_memory/exports/MEMORY.md
```

旧系统归档：

```text
cc\_memory/archive/old\_memory\_system/
```

不再作为 active runtime 的目录包括：

```text
cc\_context/memory/
\_cc\_live\_memory/
cc\_context/memory\_graph/
cc\_context/memory\_system/
cc\_context/harness\_memory\_harvest/
cc\_context/harness\_memory\_snapshot/
cc\_context/memory\_archive/
```

SQLite 表设计包括：

```text
meta
events
facts
entries
edges
aliases
changes
```

核心命令：

```bash
python cc\_memory/mem.py boot
python cc\_memory/mem.py search "query"
python cc\_memory/mem.py read <id>
python cc\_memory/mem.py impact <id>
python cc\_memory/mem.py add-event --text "raw evidence"
python cc\_memory/mem.py set-fact --subject ... --predicate ... --value ...
python cc\_memory/mem.py add-entry --title ... --body ... --depends-on <id>
python cc\_memory/mem.py link <source> <target> --type DEPENDS\_ON
python cc\_memory/mem.py propose --operation update\_fact --touches <id> --reason "..."
python cc\_memory/mem.py check
python cc\_memory/mem.py export
```

这一版产物：

```text
zmd\_slim\_memory\_rewrite\_full.zip
SLIM\_MEMORY\_REWRITE\_REPORT.md
slim\_memory\_validation.txt
```

验证摘要：

```text
memory check: OK
unit tests: OK
export\_bytes: 17297 / 24576
```

\---

## 7\. 第二个根问题：关系发现不能靠使用者能力

slim rewrite 虽然解决了“多棵树”和“单一真相”的问题，但用户继续指出更深的问题：

```text
新增条目时，谁来找所有相关条目？
如果还靠当前使用者或当前 Agent 自己想，系统质量仍然受使用者能力限制。
```

这很关键。因为记忆系统的目标不是要求使用者更强，而是帮助使用者发现连接。

所以关系发现不能是：

```text
使用者自己找边 -> 系统保存边
```

应该是：

```text
系统主动生成候选相关集合 -> 使用者/Agent 审阅 -> 系统形成边
```

这引入了 `relation\_suggestions`。

\---

## 8\. Relation discovery：系统主动生成候选边

在 `memory.db` 中增加：

```text
relation\_suggestions
```

新增流程：

```bash
python cc\_memory/mem.py suggest --title "..." --body "..."
python cc\_memory/mem.py add-entry --id <id> --title "..." --body "..."
python cc\_memory/mem.py relations
python cc\_memory/mem.py review-relation <suggestion-id> --accept
python cc\_memory/mem.py review-relation <suggestion-id> --reject
python cc\_memory/mem.py check
```

规则：

```text
新增 entry / fact 后，系统自动生成候选关系。
候选关系进入 pending review。
高置信 pending 未处理时，check 失败。
```

这让系统承担“发现候选相关项”的职责，使用者只做审阅。

新增核心事实：

```text
fact-relation-discovery-is-system-job
```

它记录：关系发现是系统职责，不应完全依赖使用者回忆。

这一版产物：

```text
zmd\_memory\_relation\_discovery\_full.zip
zmd\_memory\_relation\_discovery\_overlay.zip
MEMORY\_RELATION\_DISCOVERY\_REPORT.md
memory\_relation\_discovery\_validation.txt
```

\---

## 9\. Local compute relation discovery：零新增依赖增强

用户指出初版识别系统仍太弱，并要求如果需要依赖要先停下来确认。

于是先做了零新增依赖版本，只使用：

```text
Python standard library
SQLite
SQLite FTS5 如果当前 sqlite 支持
```

不引入：

```text
PyTorch
sentence-transformers
FAISS
llama.cpp
CUDA 包
```

新增本地索引表：

```text
node\_features
feature\_stats
node\_norms
memory\_fts
```

增强信号：

```text
SQLite FTS5 BM25
英文 / id token 加权重叠
中文 bigram / trigram / 4-gram
数字 token 命中
id / alias 精确命中
一跳图扩展
```

命令：

```bash
python cc\_memory/mem.py rebuild-index
python cc\_memory/mem.py suggest --title "..." --body "..."
python cc\_memory/mem.py suggest --node <id> --store
python cc\_memory/mem.py relations
python cc\_memory/mem.py review-relation <id> --accept
python cc\_memory/mem.py review-relation <id> --reject
```

这一版产物：

```text
zmd\_relation\_discovery\_local\_compute\_full.zip
zmd\_relation\_discovery\_local\_compute\_overlay.zip
RELATION\_DISCOVERY\_LOCAL\_COMPUTE\_REPORT.md
relation\_discovery\_local\_compute\_validation.txt
```

验证摘要：

```text
python3 cc\_memory/mem.py check: OK
python3 -m unittest -v cc\_memory.tests.test\_slim\_memory: OK, 8 tests
python3 -m py\_compile: OK
```

\---

## 10\. GPU 检索增强调研与计划

用户随后要求先详细调研，再给 GPU 检索增强计划书。明确要求：如果需要依赖，先停下来说明。

本轮只做计划，不改代码、不安装依赖。

硬件背景：

```text
CPU: i9-13900KS
GPU: RTX 4070 Ti 12GB
```

结论：GPU 增强不应该变成第四棵树。GPU 只能作为 `cc\_memory/mem.py` 的可选检索后端，唯一真相仍然是：

```text
cc\_memory/memory.db
```

### 10.1 推荐模型

默认推荐：

```text
BAAI/bge-m3
```

原因：中英混合稳、模型不大、支持 dense/sparse/multi-vector、长文本能力够。

对照候选：

```text
Qwen3-Embedding-0.6B
Qwen3-Embedding-4B
```

不建议默认：

```text
Qwen3-Embedding-8B
```

因为 4070 Ti 12GB 不适合常驻 8B fp16。

Reranker 候选：

```text
BAAI/bge-reranker-v2-m3
Qwen3-Reranker-0.6B
```

### 10.2 推荐流水线

```text
Stage 1: SQLite FTS / token / ngram / alias / graph expansion
Stage 2: GPU dense embedding recall
Stage 3: candidate union + graph expansion
Stage 4: cross-encoder rerank
Stage 5: relation\_suggestions pending review
```

### 10.3 数据库扩展计划

新增表建议：

```text
embedding\_models
node\_embeddings
retrieval\_runs
```

向量库原则：

```text
小规模：SQLite BLOB + NumPy exact cosine
中规模：FAISS CPU / hnswlib
大规模：FAISS GPU / cuVS
```

不要一上来做 FAISS GPU，因为当前记忆量远不到需要 GPU ANN 的规模。

### 10.4 依赖边界

真正实现 GPU 版前必须确认依赖。

最小 GPU 版依赖：

```text
torch CUDA build
sentence-transformers
transformers
numpy
```

加 rerank：

```text
FlagEmbedding
```

大规模 ANN 可选：

```text
faiss-gpu / FAISS GPU
cuVS / RAPIDS
```

本会话最后生成的计划书：

```text
GPU\_RETRIEVAL\_ENHANCEMENT\_PLAN.md
```

\---

## 11\. 设计原则沉淀

本会话逐步收敛出这些原则。

### 11.1 单一真相源

运行时只能有一个真相：

```text
cc\_memory/memory.db
```

其他文件都是生成视图、缓存、归档。

### 11.2 Markdown 是视图，不是源数据

`exports/MEMORY.md` 可以给 Agent 读，但不能手改为真相。删掉后必须能从数据库重建。

### 11.3 图不是另一棵树

typed graph 不能做成 `memory\_graph/` 这种第二套 active 目录。边、事实、条目都应该在数据库里。

### 11.4 系统要帮助使用者发现关系

新增/修改记忆时，系统必须主动召回候选相关项，而不是要求使用者自己想全。

### 11.5 候选不等于真相

系统可以自动生成 relation suggestions，但不能自动写硬边。硬边需要 review。

### 11.6 check 必须能阻断未审候选

高置信 pending relation suggestion 未处理时，`mem.py check` 应失败，防止关系发现流程被跳过。

### 11.7 GPU 只增强检索，不改变主系统

GPU embedding / rerank 是可选检索后端，不能成为新记忆系统。

### 11.8 加依赖前必须确认

用户明确要求：如果实现需要依赖，必须先停下来说明，不得偷偷引入。

\---

## 12\. 当前推荐基线

当前推荐基线不是早期 overlay，而是 slim memory + local relation discovery：

```text
cc\_memory/mem.py
cc\_memory/memory.db
cc\_memory/exports/MEMORY.md
relation\_suggestions
node\_features / feature\_stats / node\_norms / memory\_fts
```

推荐日常流程：

```bash
python cc\_memory/mem.py boot
python cc\_memory/mem.py search "query"
python cc\_memory/mem.py read <id>
python cc\_memory/mem.py impact <id>
python cc\_memory/mem.py suggest --title "..." --body "..."
python cc\_memory/mem.py add-entry --title "..." --body "..."
python cc\_memory/mem.py relations
python cc\_memory/mem.py review-relation <id> --accept
python cc\_memory/mem.py review-relation <id> --reject
python cc\_memory/mem.py check
python cc\_memory/mem.py export
```

当前不建议继续使用：

```text
cc\_context/memory/ 作为 active source
\_cc\_live\_memory/ 作为 mirror source
cc\_context/memory\_graph/ 作为 active graph source
旧 harness 写入工具
```

\---

## 13\. 已生成产物列表

本会话中生成或讨论过的主要产物如下。

### 13.1 Slim rewrite

```text
zmd\_slim\_memory\_rewrite\_full.zip
SLIM\_MEMORY\_REWRITE\_REPORT.md
slim\_memory\_validation.txt
```

### 13.2 Relation discovery

```text
zmd\_memory\_relation\_discovery\_full.zip
zmd\_memory\_relation\_discovery\_overlay.zip
MEMORY\_RELATION\_DISCOVERY\_REPORT.md
memory\_relation\_discovery\_validation.txt
```

### 13.3 Local compute relation discovery

```text
zmd\_relation\_discovery\_local\_compute\_full.zip
zmd\_relation\_discovery\_local\_compute\_overlay.zip
RELATION\_DISCOVERY\_LOCAL\_COMPUTE\_REPORT.md
relation\_discovery\_local\_compute\_validation.txt
```

### 13.4 GPU plan

```text
GPU\_RETRIEVAL\_ENHANCEMENT\_PLAN.md
```

### 13.5 本文档

```text
memory\_system\_session\_summary\_20260626.md
```

\---

## 14\. 后续建议

### 14.1 短期

先不要上 GPU。先把 local relation discovery 的效果跑扎实：

```text
新增条目时 pending suggestion 数量是否合理
check 是否能阻断未审高分候选
review-relation 是否足够顺手
误报/漏报样例是否可收集
```

### 14.2 中期

构建一个小 benchmark：

```text
positive = 已接受 edges
negative = 随机不相关 pair
query = title + body / fact value
```

指标：

```text
Recall@20
MRR@20
Precision@10
pending suggestions per new node
suggest p95 latency
```

先证明增强确实比现在好，再实现 GPU。

### 14.3 GPU 实现前必须确认依赖

如果进入 GPU 版，需要先确认：

```text
torch CUDA build
sentence-transformers
transformers
numpy
FlagEmbedding
```

如果用户不同意依赖，不能继续实现。

### 14.4 实现 GPU 时保持瘦架构

必须坚持：

```text
memory.db 是唯一真相
embedding 是缓存/派生数据
FAISS/cuVS 索引如有，只能放 cache，可删除重建
relation\_suggestions 是审阅队列，不是自动写边
```

\---

## 15\. 一句话总结

本会话从“条目记忆为什么不够”开始，经历了“typed graph overlay 失败教训”，最终收敛到一个更干净的方向：

```text
SQLite 单一真相 + 生成视图 + 系统主动关系发现 + 强制审阅 + 可选 GPU 语义检索后端。
```

关键转折是：记忆系统不能只保存使用者已经想到的边，它必须主动帮助使用者发现候选连接；否则系统质量仍然被当前使用者或当前 Agent 的能力上限锁死。




这条这段话是我作为用户留下来的。

现在 GPU 加速已经落地了
