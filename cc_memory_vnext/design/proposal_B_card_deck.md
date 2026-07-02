# ZMD Memory v2: card-deck + context compiler design

本稿是重做版设计，不以现有 `cc_memory/mem.py` 的 facts/entries/edges/suggestions 体系为基础。它可以迁移旧数据，但不继承旧系统的核心抽象。

当前可见附件里，我实际读到的是项目快照与依赖包；没有单独散落的 MD 附件进入沙盒。因此本稿依据项目包内的 `cc_memory` 代码、`memory.db`、`exports/MEMORY.md` 与相关运行规则反推问题。

## 0. 一句话结论

旧系统失败的根不是“检索模型不够好”，而是“把记忆做成了一个被动数据库”。新系统必须把记忆改成主动的上下文编译器：数据库只做索引缓存，真正的记忆是可读、可合并、带激活条件的卡片集合；每个会话、每条用户消息、每次工具动作都会自动编译一个任务记忆包，而不是等模型想起自己要搜索。

核心原则：

1. 记忆不是搜索框，是任务启动器。
2. 每条记忆必须说明“什么时候应该自动出现”。
3. 检索召回率不是靠模型自觉，而是靠激活测试和 CI 闸门。
4. 二分 reranker 只能做投票/否决特征，不能做排序主轴。
5. 旧的 SQLite 可以存在，但只能是生成索引，不再是真相源。

## 1. 对现有系统的诊断

我看到的当前系统大致是：

- `cc_memory/memory.db` 是唯一活真相源。
- 表结构是 `events`、`facts`、`entries`、`edges`、`aliases`、`relation_suggestions`、`node_embeddings` 等。
- `search` 是 `LIKE %query%` 子串，不是 FTS，不走语义。
- `suggest/add-entry/set-fact` 可选 `--semantic` 与 `--rerank`，但这发生在写入候选边阶段，不是每次实际任务前的主动召回。
- `boot` 打印 pinned entries、维护状态、命令提示。它帮助开局，但不能解决任务中途“不知道要查什么”的问题。
- hook 主要做 finalize、rebuild embeddings、check/export、Stop 提醒，解决的是一致性与维护纪律，不是任务前主动上下文注入。
- 当前库内统计：约 25 events、22 facts、100 entries、402 edges、592 relation_suggestions、118 node embeddings。active 节点约 110 个，其中 17 个没有硬边。这个规模已经足以暴露结构问题。

### 1.1 最大结构病：被动数据库悖论

现在的模型必须先知道“这里可能有某类记忆”，才会 `search`。但它不知道有什么，便不会 `search`。这会导致零召回，尤其发生在这些场景：

- 用户问一个抽象问题，如“这个系统哪里不对”。
- 当前任务涉及旧裁决、旧坑、旧 owner 指令，但关键词没有原样出现。
- 子代理没有读 `CLAUDE.md` 或 `cc_memory boot`。
- 会话中途切换任务，boot 的初始上下文已经被冲淡。
- 某条记忆是“操作规则本身”，如 precompact、relay、codex 分工、rerank 脾气，这类自指知识很难被自然查询触发。

现有 pinned meta-index 是补丁，不是根治。它把“记忆系统本身怎么用”常驻化了，但项目内容记忆仍然是被动库。

### 1.2 第二病：记忆没有激活语义

当前 facts/entries 主要回答“这是什么”。它们没有把“何时必须加载”作为一等字段。结果是系统只能靠文本相似度找相关，而不是靠任务触发条件找相关。

一条真正可用的记忆至少需要这些激活语义：

- 触发意图：写代码、审查、发 relay、压缩、开会、迁移、提交、处理 P1.2 状态等。
- 触发实体：文件、目录、函数、phase 名、artifact 名、外部工具名、人员/模型角色。
- 触发风险：false-CERTIFIED、stale artifact、owner 决策、cross-model review、binary DB merge conflict。
- 触发动作：准备改文件、准备回答、准备调用子代理、准备提交、准备压缩上下文。

没有这些字段，检索系统只能拿着一把小手电在仓库里照，照到哪算哪。

### 1.3 第三病：当前边系统维护不动

现有硬边用于 impact，软边用于检索和阅读。问题是自动 suggester 倾向产生廉价 `RELATED_TO`，人又容易橡皮图章接受软边，真正影响传播需要的 `DEPENDS_ON/SUPERSEDES/CONTRADICTS` 很难自动补全。

这导致：

- 旧事实被新事实推翻，但旧节点仍 active。
- impact 只能沿硬边传播，孤儿节点被漏掉。
- relation_suggestions 数量堆积，accepted/rejected/pending 本身成为维护债。
- 维护动作从“系统维护自己”退化成“系统制造一堆候选让人清”。

### 1.4 第四病：二分 reranker 被放错了位置

用户已经实测：GPU reranker 近似二分，相关给 1，不相关给 0，不能稳定输出连续评分。现有设计还把它放在“剪候选/排序”的位置，于是必然出问题：

- 对具体锚定查询很好。
- 对抽象、自指、短口语查询会把真相关打成 0。
- 降 floor、换 instruction、换模型都救不了“无梯度”的根因。

二分模型不是不能用，但不能把它当 ranker。它应该被降级为“多视角投票器”或“高置信 veto”，连续评分由可解释特征与多视角覆盖率产生。

### 1.5 第五病：真相源是二进制 DB，不利于协作

SQLite 作为唯一真相源有几个问题：

- Git 无法语义合并，多会话容易二进制冲突。
- 人类不可直接审查 diff。
- 删除、归档、supersede 的语义不自然。
- 索引与内容混在一起，容易把“检索缓存”当成“知识本体”。

新系统应把 SQLite 降为可重建索引。真相源必须是文本化、可 diff、可 merge 的卡片与事件日志。

## 2. 新系统目标

新系统叫 `zmd_memory_v2`。它不是“更好的 search”，而是“任务上下文编译器”。

硬目标：

1. 零查询召回：模型即使没有主动搜索，系统也要在任务入口自动给出相关记忆包。
2. 可解释激活：每条加载进上下文的记忆都必须说明为什么被加载。
3. 可测召回：每张卡自带 trigger examples，CI 检查这些例子是否能召回本卡。
4. 可合并真相源：人读文本，Git 合并文本，SQLite 只做缓存。
5. 生命周期闭合：新卡若改变旧认知，必须更新、supersede 或标冲突，不能只添不改。
6. 二分模型不做主 ranker：它只能产生投票特征，不能负责连续排序。
7. 子代理同等受控：Claude、Codex、workflow/team agent 都拿到同一份任务记忆包，不靠它们自觉 boot。

## 3. 总体架构

```
zmd_memory/
  cards/                  # 真相源：一张卡一个 .md，可 diff/merge
    rules/
    decisions/
    pitfalls/
    status/
    procedures/
    artifacts/
    preferences/
  domains/                # 域图：告诉系统“这里有什么记忆”
  episodes/               # 原始事件日志，append-only JSONL/MD
  eval/                   # activation tests 与历史 miss 回归集
  views/                  # 生成视图，可删可重建
    BOOT_CONTEXT.md
    DOMAIN_ATLAS.md
    CURRENT_STATE.md
  index/                  # 生成索引，gitignored
    memory.sqlite
    embeddings/
    fts/
```

真相源是 `cards/`、`domains/`、`episodes/`、`eval/`。`index/` 是可重建缓存，不能提交为唯一证据。

新系统分五层：

1. Card Deck：带元数据、激活条件、生命周期的记忆卡。
2. Domain Atlas：常驻目录图，解决“不知道库里有什么”。
3. Context Compiler：根据当前任务自动编译记忆包。
4. Retrieval Engine：高召回候选池 + 可解释排序 + 二分投票器。
5. Gardener：写入、冲突、剪枝、回归测试、迁移维护。

## 4. 记忆卡格式

每条记忆是一张 Markdown 卡，frontmatter 是结构字段，正文是人读内容。

示例：

```md
---
id: pref-creative-tasks-use-team-discussion
kind: preference
status: active
priority: high
confidence: owner_explicit
owner_asserted: true
summary: 创造性/开放判断题优先用 Agents Team 开会，而不是 workflow fan-out。
created_at: 2026-06-20T00:00:00Z
updated_at: 2026-06-26T00:00:00Z
validity:
  from: 2026-06-20
  until: null
scope:
  domains: [collaboration_workflow, agent_orchestration]
  phases: [all]
  files: []
  symbols: []
triggers:
  intents: [design, open_judgment, architecture_review, tradeoff_discussion]
  keywords: [开会, 讨论, team, workflow, fan-out, 创造性, 开放判断]
  negative_keywords: [纯枚举, 批量核对]
  examples:
    - 用户让我重新设计记忆系统
    - 需要多个 agent 互相挑战来收敛方案
activation:
  default_tier: task
  load_when:
    - intent in [design, open_judgment, architecture_review]
    - user_mentions_any [开会, 讨论, team]
relations:
  supersedes: []
  depends_on: []
  contradicts: []
  related: [terminology-meeting-equals-team]
evidence:
  - type: owner_instruction
    ref: cc_memory legacy import
review:
  next_review: null
  stale_if_not_retrieved_days: 180
---

## Claim

创造性、开放判断、方案权衡类任务优先用 Agents Team 形式开会讨论。

## Rationale

...正文...
```

关键变化：`triggers`、`activation`、`scope`、`validity` 是一等字段。没有触发条件的卡就是不可召回垃圾，CI 应该拒绝。

## 5. 记忆类型

旧系统只有 fact/entry，太粗。新系统至少需要这些 kind：

- `rule`：必须遵守的操作规则。
- `preference`：owner 偏好。
- `decision`：已裁决事项，含边界与例外。
- `procedure`：怎么做某类任务。
- `pitfall`：踩过的坑与避免方式。
- `status`：某阶段当前状态，必须有 freshness 与 supersession。
- `artifact`：外部包、relay、文件、证据链状态。
- `code_fact`：路径、符号、调用链相关知识。
- `review_finding`：外审/对抗审查发现。
- `open_obligation`：未闭事项，必须能进入任务包。
- `tombstone`：被删除或废弃的记忆，防止误复活。

每种类型有不同必填字段。例如 `status` 必须有 `validity` 与 `supersedes` 检查；`rule/preference` 必须有 owner/evidence；`code_fact` 必须有 files/symbols；`open_obligation` 必须有 owner、blocking 状态和 close condition。

## 6. Domain Atlas：解决数据库悖论的第一根柱子

Domain Atlas 是常驻域图，不是检索结果。它回答“库里有什么领域的记忆”。每个 domain 也是一张卡，但更短、更稳定。

示例：

```yaml
id: domain-cc-memory-system
name: cc_memory / memory system
summary: 记忆系统自身的读写纪律、检索脾气、hook、压缩、迁移、rerank 限制。
load_when:
  - user_mentions_any: [记忆, memory, cc_memory, 检索, 召回, rerank, semantic]
  - intent_any: [memory_write, memory_design, context_compression]
key_cards:
  - memory-runtime-protocol
  - cc-memory-search-is-substring-like
  - reranker-conservative-needs-specific-query
  - cc-memory-crud-gotchas
current_state_card: cc-memory-current-state
```

每个会话启动时，系统注入一个紧凑版 `DOMAIN_ATLAS.md`，例如：

```
本项目记忆覆盖这些域：
1. cc_memory/记忆系统：检索、压缩、rerank、hook、迁移。
2. P1.2/P1.3 publication/soundness：当前 gate、certified 边界、supervisor。
3. Codex/Claude 协作：谁实现、谁审、子代理提示词纪律。
4. relay/GPT Pro 外审：包、提示词、剪贴板、等待回复状态。
5. precompact/上下文压缩：专门记忆更新回合规则。
6. git/并发工作区：共享 index、memory DB 冲突、提交 pathspec。
```

模型看到域图，才知道该查什么。这样“我不知道库里有什么，所以不会查”的悖论被结构性切断。

## 7. Context Compiler：第二根柱子

每次任务入口，系统不等模型主动 search，而是自动生成 Task Frame，再编译 Memory Packet。

Task Frame：

```json
{
  "user_text": "重新设计记忆系统",
  "intent": ["architecture_design", "memory_system_review"],
  "entities": ["cc_memory", "rerank", "GPU", "database", "recall"],
  "files_in_scope": ["cc_memory/mem.py", "cc_memory/memory.db"],
  "risk_tags": ["self_reference", "retrieval_failure", "stale_memory"],
  "action": "answer_design",
  "session_context": {
    "agent": "assistant",
    "repo": "zmd"
  }
}
```

Memory Packet 分层：

- L0 Kernel：永远加载，500 到 800 token。包括 owner 高优规则、当前仓库安全边界、记忆系统域图摘要。
- L1 Task：本任务必须读，1500 到 4000 token。由 Context Compiler 选卡。
- L2 Pointers：相关但不塞全文，只给 id、摘要、读取命令。
- L3 Archive：原始事件、旧审查、长材料，只在需要时展开。

输出形态：

```md
# Memory Packet

## Why loaded
- user intent = memory_system_review
- matched domain = cc_memory / memory system
- matched risks = retrieval_failure, binary_reranker_limit

## Must-use cards
1. cc-memory-crud-gotchas: 当前系统静默坑。
2. cc-memory-search-is-substring-like: search 是 LIKE，不是 FTS/semantic。
3. reranker-conservative-needs-specific-query: reranker 对抽象查询误剪。
4. cc-memory-semantic-low-adoption-verdict: 语义层低采用。

## Watch-outs
- 不要把二分 reranker 当排序主轴。
- 不要继续用 SQLite 作为唯一人类真相源。
```

模型处理任务时拿到的是“已经编译好的上下文”，不是一个空搜索框。

## 8. Retrieval Engine

新检索分五阶段。

### 8.1 Stage A：硬触发召回

从 Task Frame 直接用结构字段召回：

- domain match
- intent match
- file/symbol/path match
- phase/status match
- tool/action match
- owner/risk tag match
- open obligation match

这一步不靠模型相似度。例如用户说“要压缩了”，就必出 `precompact` 规则；用户说“重新设计记忆系统”，就必出 `domain-cc-memory-system` 与相关卡。

### 8.2 Stage B：高召回文本召回

并行召回候选：

- FTS5/BM25，支持多词，不再用单个 LIKE 字面串。
- CJK ngram token table，保证中文词组与子串可检索。
- alias/entity index。
- dense embedding cosine。
- recent/current/open status。
- graph closure：depends/supersedes/contradicts/open_obligation。

候选池目标不是精确，而是宽。宁可拿 200 个候选，也不要在这里漏。

### 8.3 Stage C：可解释基础分

连续分数由可解释特征给出，不由二分 reranker 给出。

建议公式：

```
base_score =
  0.25 * trigger_match_score      # intent/path/domain/action 是否命中
+ 0.20 * lexical_score            # BM25/ngram/token
+ 0.15 * dense_score              # cosine normalized
+ 0.15 * scope_score              # 文件/phase/status/domain 精确度
+ 0.10 * graph_score              # 与已命中卡的硬关系距离
+ 0.10 * priority_score           # owner rule/current status/open obligation
+ 0.05 * freshness_score          # status 类 freshness
```

这解决“reranker 没连续分”的问题：排序主轴不依赖它。

### 8.4 Stage D：二分模型变投票器

如果二分 reranker 只能输出 0/1，就把它用于多视角投票，而不是单次评分。

对每个候选卡，问多个二分问题：

1. 这张卡是否直接约束当前任务意图？
2. 是否涉及当前实体？
3. 是否涉及当前文件/phase？
4. 忽略这张卡是否可能导致错误？
5. 是否应进入 L1，而不只是 L2 pointer？
6. 是否与当前用户问题的核心名词有关？
7. 是否是被当前任务触发的高优 rule/status/open obligation？

再加上多 query variant、多 chunk、多字段视图：

```
binary_vote_score = weighted_positive_votes / total_weight
```

单个模型仍是二分，但多视角投票会产生 0 到 1 的连续覆盖率。它不是“相关概率”，而是“多激活条件覆盖率”。这比硬把 sigmoid 当连续相关度可靠。

使用规则：

- binary_vote_score 只能上调/下调，不得独自从候选池删除 high-priority/triggered/open-obligation 卡。
- 对抽象自指任务，binary model 默认不做 veto，只做弱特征。
- 对具体锚定任务，binary model 可剪掉 L2 噪声，但必须保留硬触发卡。

### 8.5 Stage E：多样性与闭包

最终不是简单 top-k。Context Compiler 要做闭包：

- 如果加载 status，则加载它 supersedes 的旧状态摘要，避免旧新冲突。
- 如果加载 decision，则加载 evidence 或 owner instruction 摘要。
- 如果加载 rule，则加载 exception/negative examples。
- 如果加载 code_fact，则加载 file/symbol pointer。
- 相似卡只取最新/最高优，其他进 L2 pointer。

## 9. 写入与维护

新写入流程叫 `distill`，不是 `add-entry`。

### 9.1 事件先行

所有新信息先进入 append-only episode：

```jsonl
{"id":"evt-...","source":"user_message","text":"...","created_at":"...","session":"..."}
```

episode 是原始证据，不是最终记忆。之后 distiller 从 episode 生成 card patch。

### 9.2 Distiller 产出 changeset

Distiller 不直接改卡，而是输出 changeset：

```yaml
changeset_id: cs-20260626-memory-v2
source_events: [evt-...]
proposals:
  - op: create_card
    card: ...
  - op: update_card
    id: cc-memory-current-state
    patch: ...
  - op: supersede_card
    new: memory-v2-design
    old: cc-memory-gpu-retrieval-upgrade-plan
```

### 9.3 Commit 前强制检查

`zmem verify` 必须检查：

- 每张 active 卡至少有一个 domain。
- 每张 active 卡至少有 trigger examples。
- status 卡必须有 validity/currentness。
- priority high/critical 卡必须能进 L0/L1 或 domain atlas。
- 新卡若同 scope 里已有 active 卡，必须声明 merge/update/supersede/related。
- 任何 `contradicts` 必须有人类可读解释。
- 每个 open_obligation 必须有 close condition。
- 每张卡的 trigger examples 必须在 activation test 中召回本卡。
- 生成 index 与 views 必须与 cards 同步。

这是系统维护自己的关键。不是“给人一堆建议”，而是“没有激活路径就不让入库”。

## 10. Activation Tests：把召回率变成可测指标

每张卡都带 `triggers.examples`。CI 跑：

```
zmem eval activation
```

对每个 example：

1. 构造 Task Frame。
2. 跑 Context Compiler。
3. 检查该卡是否进入 L1 或 L2。
4. 若卡 priority high/critical，必须进入 L1。
5. 若没进入，CI fail。

此外保存历史 miss：

```yaml
- query: "这个记忆系统为什么召回率很差"
  expected_cards:
    - cc-memory-search-is-substring-like
    - cc-memory-semantic-low-adoption-verdict
    - reranker-conservative-needs-specific-query
    - cc-memory-crud-gotchas
```

这才是真召回治理。不是凭感觉说“应该能搜到”，而是每次改索引/改触发/改卡都跑回归。

指标：

- activation_recall@L1 for high-priority cards。
- activation_recall@L2 for normal cards。
- false_context_rate：加载后被模型/人标记无用的比例。
- stale_active_count：过期仍 active。
- orphan_activation_count：无触发卡数量，目标 0。
- unresolved_conflict_count。
- memory_packet_token_budget。

## 11. Gardener：系统自维护

Gardener 不是神秘自动整理，而是一组明确队列：

- stale：status 超过 review window。
- duplicate：相同 scope 和 claim 的多卡。
- conflict：同 scope 下 active 卡互相 contradict。
- activation_gap：卡存在但 trigger examples 召回失败。
- overlong：卡过长，需拆摘要与正文。
- ungrounded：缺 evidence。
- zombie：长时间从未被召回，也非 archive/tombstone。
- hot_noise：经常被召回但被标记无用。
- supersession_debt：新卡疑似推翻旧卡但未处理旧卡。

Gardener 输出 changeset，由规则决定是否可自动应用：

- 低风险：重建 index、刷新 views、补 generated summary、格式化 frontmatter。
- 中风险：补 triggers、补 domain、拆过长卡，需要 review。
- 高风险：改 claim、supersede、contradict、archive active rule/status，必须人工或高置信 owner evidence。

这样“系统自身维护”变成可审计流水线，而不是靠模型灵感修库。

## 12. 与 Claude/Codex/workflow 的集成

### 12.1 会话启动

SessionStart 不跑会写库的命令，只读生成：

```
zmem context --mode session-start
```

输出：

- L0 Kernel。
- Domain Atlas 摘要。
- 当前 open obligations。
- 当前 memory health。

### 12.2 每条用户消息前

主会话在回答或动手前调用：

```
zmem context --task-file .zmem/task_frame.json --budget 3000
```

这个动作可以由 wrapper/hook/agent orchestrator 强制，不靠模型自觉。

### 12.3 工具动作前后

- PreTool：根据将要读取/修改的路径加载 file/symbol 相关卡。
- PostTool：把 test failure、diff、artifact path 写入 episode，必要时触发 distill proposal。
- Stop：轻量提示未闭 changeset、activation failures、open obligations。

### 12.4 子代理

所有 agent prompt 由 orchestrator 注入 Memory Packet，不让子代理自己决定要不要 boot。

```
You must first read this Memory Packet. It was compiled for your task.
```

Codex 子代理的“不会主动读记忆”问题由父进程注入解决。

## 13. 迁移计划

### Phase 0：冻结旧系统为 legacy

- 禁止继续把旧 `memory.db` 当唯一真相源新增知识。
- 旧 `cc_memory` 保留只读导出与迁移输入。
- 生成 legacy snapshot，包括 facts/entries/edges/suggestions。

### Phase 1：建立 v2 骨架

新增目录：

```
zmd_memory/
  cards/
  domains/
  episodes/
  eval/
  views/
  index/
```

实现最小 CLI：

```
zmem build-index
zmem context --query/--task-json
zmem verify
zmem eval activation
zmem distill --episode
```

### Phase 2：迁移高价值记忆

不要全量机械搬运。按优先级迁移：

1. owner 明确偏好与硬规则。
2. 当前状态与 open obligations。
3. 会导致严重错误的 pitfalls。
4. 工作流/relay/precompact/codex 分工。
5. P1.2/P1.3 当前 gate 和 soundness 边界。
6. 其他历史材料进 archive 或 legacy pointer。

每张迁移卡必须补 triggers/examples/domain。没有触发条件的旧条目不迁入 active。

### Phase 3：替换启动与子代理入口

- `CLAUDE.md` / `AGENTS.md` 从 `python cc_memory/mem.py boot` 改为 `zmem context --mode session-start`。
- 子代理 prompt wrapper 自动注入 Memory Packet。
- old mem.py search/read 保留 read-only bridge。

### Phase 4：引入 activation CI

- `zmem verify` 接 preflight。
- `zmem eval activation` 接 CI。
- 每次新增/修改卡，必须同时更新 trigger examples。

### Phase 5：弃用旧 SQLite 真相源

- `cc_memory/memory.db` 标 legacy read-only。
- `zmd_memory/index/memory.sqlite` 可重建且 gitignored。
- 人类审查只看 card diff 与 changeset。

## 14. 第一批应该建的 domains

结合当前项目，我建议初始 domains：

1. `memory_system`：记忆系统、检索、rerank、semantic、压缩、迁移。
2. `agent_orchestration`：Claude/Codex 分工、workflow/team、子代理提示词。
3. `p1_2_publication_soundness`：P1.2 gate、supervisor、CERTIFIED 边界、外审 BLOCK。
4. `p1_3_transition`：P1.3/P1.3B 命名、后续集成边界。
5. `relay_external_review`：GPT Pro relay、包、提示词、剪贴板、等待状态。
6. `precompact_context`：记忆更新回合、compact 纪律。
7. `git_concurrency`：共享 index、多 checkout、SQLite 冲突、pathspec 提交。
8. `artifact_boundaries`：PROJECT_LOCK、FILE_STATUS、runtime role、archive only。
9. `industrial_planner_delivery`：viewer、release、single-base delivery surface。
10. `test_preflight`：preflight、slow tests、mock stale、reseal。

这些 domains 常驻显示，模型就知道“这里有这些记忆领域”。

## 15. 旧系统中应该删除的概念

彻底重做时，不建议保留这些核心概念：

- `facts` vs `entries` 二分：太粗，改为 typed cards。
- `relation_suggestions` 作为主维护入口：改为 changeset + verify + activation tests。
- SQLite as source of truth：降为 generated index。
- 手动 `search` 作为主要召回入口：改为 automatic context compiler。
- reranker raw score gate：改为 feature score + binary vote。
- `propose` 死表：改为 changeset 工作流。
- 只有 hard edge 的 impact：改为 scope/trigger/domain/supersession 多维影响分析。

## 16. 新系统的成功判据

不是“能搜到”，而是：

1. 用户问“重新设计记忆系统”时，不需要人工 search，Memory Packet 自动包含记忆系统、rerank 限制、CRUD 坑、低采用结论、旧系统当前结构。
2. 用户准备 `/compact` 时，precompact 规则自动进 L1。
3. 子代理做实现任务时，自动收到 CLAUDE/Codex 分工与当前项目 gate，不靠它自己 boot。
4. 新建一条推翻旧认知的卡时，verify 强制处理旧卡，否则不通过。
5. 每张高优卡都有 activation tests，改检索后召回回归会被 CI 抓住。
6. DB 删了可以重建，Git diff 能看懂记忆变化。
7. 二分 reranker 崩成全 0 时，系统仍靠 triggers/FTS/dense/priority 召回关键卡。

## 17. 最小可行实现建议

最小版本不要一开始做复杂 agent gardener。先做四个东西：

1. Card frontmatter schema + `zmem verify`。
2. Domain Atlas + session context packet。
3. FTS/ngram/dense index + task context compiler。
4. Activation tests。

只要这四个落地，召回悖论就已经被打穿。之后再做 distiller、gardener、binary vote、pairwise tournament。

## 18. 结语

旧系统像一座密室图书馆：书是真的多，但门口没有目录，馆员还得先猜哪本书存在。新系统应该像一副会自己翻面的牌组：每张牌背面写着何时该出现，任务一来，Context Compiler 自动洗牌、切牌、把该看的牌递到手上。SQLite 仍可做检索机器，但它不能再当记忆本体。真正的记忆必须可读、可测、可触发、可演化。
