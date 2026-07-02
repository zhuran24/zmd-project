# zmd 全新记忆系统设计案：从“被查询的数据库”改成“主动运行的记忆内核”

日期：2026-06-26  
范围：基于当前项目快照 `zmd_full_snapshot_0bc36db_pr1wip_20260626_202358.7z`、随会话 MD 总结、以及当前 `cc_memory` 实装状态的重新设计。  
定位：这是设计案，不是对现有 `cc_memory/mem.py` 的补丁。现有系统可以作为迁移来源和 shadow baseline，但不再作为新架构的骨架。

---

## 0. 一句话结论

现有系统失败的根因不是“检索模型不够好”，而是：

```text
记忆被做成了一个等待查询的库；
但 Agent 的失败点恰恰是它不知道什么时候该查、该用什么词查、该查到什么才算够。
```

全新系统应当从“数据库 + 查询命令”改成“事件驱动的主动记忆内核”：

```text
每个用户输入、工具命令、文件改动、测试失败、git 状态、任务阶段，都会被转成 cue frame；
记忆系统根据 cue frame 自动激活相关记忆、发出阻断级提醒、生成工作集和候选维护任务；
Agent 不再先知道有某条记忆才查询，而是被当前情境自动拉到该看的记忆面前。
```

换句话说，新系统的中心不是 `search`，而是 `admit`: 当前情境下哪些记忆必须进入工作区。

---

## 1. 对当前系统的诊断

### 1.1 已经做对的部分

当前 `cc_memory` 已经比最初 Markdown 树好很多：

- 旧多树系统已退役，当前活真相在 `cc_memory/memory.db`。
- 有事实、条目、边、候选关系、审阅队列。
- GPU 语义层和 reranker 已经落地，嵌入表和 `node_embeddings` 已存在。
- hooks / finalize / WAL checkpoint / pre-commit / CI consistency check 已经覆盖一部分工程一致性问题。
- 元记忆 pinned 层、SessionStart read-first、domain map 等补强已经尝试解决“记忆不可见”的问题。

这些是重要资产，但它们是“一个更可维护的库”，还不是“会主动工作的记忆”。

### 1.2 当前系统没有解决的根问题

#### A. 召回悖论仍存在

当前系统的主要入口仍是：

```text
boot -> read pinned -> search/suggest/read/impact
```

这要求 Agent 先意识到“这里可能有记忆”，再选择查询词，再判断是否查够。实际上，真正会出错的场景往往是：

```text
Agent 根本没意识到这个任务落在已有记忆覆盖域；
或知道要查，但不知道正确锚点；
或查了一句多词 LIKE 落空后误以为没有；
或 semantic/rerank 是 opt-in，忙的时候没开；
或子代理没有读到 SessionStart 注入。
```

所以当前补强只能提高“愿意查时”的质量，不能保证“该查时一定查”。

#### B. GPU 层解决的是候选质量，不是记忆触发

当前 GPU 落地后，结构大概是：

```text
relation_suggestions / suggest / add-entry / set-fact
  lexical + dense semantic + optional rerank
```

它对“写入时找候选边”有帮助，但对“行动前该自动想起哪条旧记忆”帮助有限。更重要的是，当前 `search` 仍是 LIKE 子串；`--semantic` 挂在 suggest/add/set，而不是普通行动前的强制上下文入口。

#### C. reranker 二分化，不应再被当作排序器

当前 Qwen3-Reranker 类模型在项目实测中表现为：

```text
具体、有锚点查询：真目标接近 1，噪声接近 0；
泛化、抽象、缺锚点查询：真相关也接近 0，甚至全剪空。
```

这不是阈值问题，也不是简单换模型能稳定解决的连续排序问题。新设计应承认它是“二值判别器/强 veto/强确认器”，不要把它放在系统核心打分位置。

#### D. 关系系统容易软边膨胀，硬依赖仍靠人

当前库内数据已经显示这个倾向：

```text
edges: RELATED_TO 283, DEPENDS_ON 88, DERIVED_FROM 11, SUPERSEDES 5, CONTRADICTS 1
relation_suggestions accepted: RELATED_TO 177, MENTIONS 9, DEPENDS_ON 9
active nodes: 110，其中 17 个 active 节点零 hard edge，约 15.5%
```

这说明系统产出的候选大量是“看起来相关”的软边，而维护真正需要的是“变更时会传播影响”的硬边。软边越多，不等于记忆系统越懂自己；很多时候只是把蛛网织厚，真正承重的梁还没架。

#### E. 写入不是 reconciliation，而是 append + review

当前新增节点后，会生成候选关系，但不会系统性地问：

```text
这条新记忆是否推翻旧记忆？
旧节点是否需要补正文？
是否有旧事实应该 valid_to 关闭？
是否应该生成 SUPERSEDES / CONTRADICTS？
是否有旧 summary / trigger / domain map 需要更新？
```

所以“新节点记了正确事实，旧节点仍然误导”仍会发生。边不能修内容漂移，必须有写入时调和。

#### F. SQLite 作为 git-tracked 真相源带来协作冲突

SQLite 适合作为投影和本地索引，不适合作为多人/多会话 git 协作下的唯一可合并真相。当前已经有 WAL、checkpoint、pathspec 提交等补丁，但这些是绕着二进制不可 merge 的事实打补丁。新系统应把 SQLite 降级为可重建 projection/cache。

---

## 2. 新系统目标

### 2.1 不再追求“更好的 search”，而追求“自动 admission”

新系统的核心问题改写为：

```text
给定当前情境，哪些记忆必须主动进入工作区？
哪些记忆需要作为背景？
哪些记忆不该进来，避免污染？
哪些旧记忆应该被维护、合并、废止？
```

### 2.2 设计目标

1. **无查询召回**：即使 Agent 没主动 search，系统也能根据当前输入、文件、命令、错误、任务阶段自动激活记忆。
2. **连续评分不依赖 reranker**：连续相关度由系统特征模型产生；二分 reranker 只是一个特征或 veto，不是排序核心。
3. **写入即调和**：禁止“裸 append 后算完”；每次新增/修改必须跑 duplicate / supersede / contradict / hard-edge / trigger 回填。
4. **记忆类型分层**：事实、事件、流程、策略、危险、任务状态、文件锚点不能混成同一种 entry。
5. **触发优先于检索**：程序性记忆和危险记忆必须靠 trigger/watchpoint 进入，不靠语义相似。
6. **可合并真相源**：git-tracked 真相源用 append-only ledger；SQLite、向量索引、Markdown 都是 projection。
7. **可观测与可训练**：每次候选生成、展示、采纳、忽略、事后发现漏召回，都要成为训练样本。

---

## 3. 新架构：Active Memory Kernel

建议目录：

```text
cc_mem2/
  memctl.py                         # CLI：人/Agent 入口
  memd.py                           # 可选 daemon：长驻加速，不是唯一真相
  ledger/                           # 唯一 git-tracked 真相：append-only 事件账本
    2026/
      06/
        2026-06-26.jsonl
  objects/                          # 大正文 / 证据快照，content-addressed
    sha256/
      ab/cd/<hash>.json
  ontology/
    node_types.yaml
    edge_types.yaml
    trigger_types.yaml
  policies/
    admission.yaml                  # 工作区 admission 规则
    review.yaml                     # 审阅闸规则
    lifecycle.yaml                  # hot/warm/cold/archive 规则
  projections/                      # 全部可删除重建
    memory.db                       # SQLite 查询投影
    vectors.sqlite                  # 或 FAISS / hnswlib cache
    MEMORY.md                       # 人读视图
    READFIRST.md                    # SessionStart 视图
    DOMAIN_MAP.md                   # 覆盖域图
  runtime/
    cue_extractor.py
    activator.py
    scorer.py
    reconciler.py
    exporter.py
  eval/
    labels.jsonl
    retrieval_runs.jsonl
    benchmarks/
```

核心转变：

```text
ledger 是真相；
SQLite 是 projection；
向量是 cache；
Markdown 是 view；
hooks 是触发器；
admission 是记忆使用面的中心。
```

多文件不等于多真相。ledger 是唯一事实来源，projection 全部可重建。

---

## 4. 数据模型

### 4.1 事件账本 Event Ledger

所有变化都写成事件，禁止直接改 current state。

事件通用字段：

```json
{
  "event_id": "evt_20260626_xxx",
  "ts": "2026-06-26T12:00:00Z",
  "actor": "claude|codex|owner|hook|ci",
  "session_id": "...",
  "event_type": "remember.assert",
  "body_hash": "sha256:...",
  "prev_event_hash": "sha256:...",
  "payload": {},
  "evidence": [],
  "labels": [],
  "schema_version": 1
}
```

关键事件类型：

```text
observe.user_message
observe.tool_call
observe.tool_result
observe.file_read
observe.file_diff
observe.git_status
observe.test_failure
observe.ci_result
remember.assert
remember.revise
remember.supersede
remember.contradict
remember.link
remember.unlink
remember.review
remember.archive
memory.admit
memory.dismiss
memory.missed
task.open
task.close
policy.set_trigger
```

这样可以回答：这条记忆为什么存在、谁写的、来自哪个会话、由哪个证据支持、后来如何演变。

### 4.2 节点 Node

不要再只有 `fact` 和 `entry`。至少需要：

```text
episode       原始经历 / 会话片段 / 工具结果
claim         可真可假的命题，带有效期、置信、证据
policy        操作纪律，例如“做 X 前必须查 Y”
procedure     可执行流程，例如“改记忆的标准步骤”
hazard        坑 / 危险 / 失败模式，必须有触发条件和严重度
artifact      文件、目录、模块、测试、脚本、外部工件
state         当前项目状态、阶段门、未闭任务
decision      owner/会议/外审裁决
summary       由其他节点生成的人读摘要，不作真相
```

每个节点必须有：

```text
id
kind
status: active | superseded | contradicted | archived | disputed
body_ref / body
summary
valid_from / valid_to
confidence
priority
severity
owner_domain
source_events
applicability
negative_scope
created_at / updated_at
```

`applicability` 是当前系统最缺的字段。它回答“什么时候该想起这条记忆”。

示例：

```json
{
  "id": "hazard_cc_memory_rerank_anchorless",
  "kind": "hazard",
  "severity": "high",
  "applicability": {
    "text_terms": ["rerank", "语义", "召回", "元记忆", "抽象查询"],
    "commands": ["cc_memory/mem.py suggest", "cc_memory/mem.py add-entry"],
    "negative_scope": ["具体实体点名查询"]
  },
  "body": "reranker 对无锚点抽象查询会全剪，不能当连续评分器。"
}
```

### 4.3 边 Edge

边不只是标签。边类型要有行为。

```text
EVIDENCED_BY       claim/decision 由 episode 支持
DERIVED_FROM       由另一节点推导
DEPENDS_ON         源节点改变时本节点必须重审
SUPERSEDES         新节点取代旧节点，旧节点关闭有效期
CONTRADICTS        两节点冲突，查询时必须同时提示
APPLIES_TO         policy/hazard/procedure 适用某 artifact/domain/trigger
TRIGGERS_ON        记忆绑定到 cue，例如文件 glob、命令、错误 regex
OWNS_DOMAIN        节点声明一个覆盖域
MENTIONS           提及但无传播
RELATED_TO         弱相关，只用于扩展阅读
DUPLICATES         候选合并关系
```

写边时触发 handler：

```text
SUPERSEDES.on_insert -> old.status=superseded; old.valid_to=now; active index 移除 old
CONTRADICTS.on_insert -> 两侧查询时互相提示；禁止单独注入一侧作为确定事实
DEPENDS_ON.on_insert -> 加入 impact graph；变更 target 时 source 进入 stale_review
TRIGGERS_ON.on_insert -> 更新触发器索引；命中 cue 时直接 admission
APPLIES_TO.on_insert -> 加入 domain map / artifact map
```

这可以避免“边只是看上去专业的 wikilink”。

---

## 5. 主动召回：Cue Frame -> Activation -> Admission

### 5.1 Cue Frame

每个回合、每个工具调用、每次文件改动都生成 cue frame。

来源：

```text
用户当前消息
系统/开发者指令摘要
当前任务标题 / open task
最近 N 条工具命令
最近读/写文件路径
git diff 文件
测试失败名 / traceback / error regex
当前分支 / commit / CI 状态
会话角色：主会话 / 子代理 / codex / reviewer
时间：是否压缩前、提交前、结束前
```

Cue frame 示例：

```json
{
  "cue_id": "cue_20260626_abc",
  "text": "重新设计记忆系统，GPU reranker 二分，召回率 0",
  "paths": ["cc_memory/mem.py", "cc_memory/hooks/cc_mem_hook.py"],
  "commands": ["python cc_memory/mem.py search rerank"],
  "symbols": ["relation_suggestions", "rerank_helper", "node_embeddings"],
  "phase": "design_review",
  "actor": "assistant_main"
}
```

### 5.2 Candidate Generators

候选不再只来自 search。必须多路高召回生成：

```text
1. Watchpoint / trigger 命中
   path glob、symbol、command、error regex、phase、actor。
   这是最高优先级，解决“我不知道该搜什么”。

2. Domain map 命中
   当前 cue 落入某个 domain，自动拉 domain owner / protocol / hazards。

3. Lexical / BM25 / ngram
   用 cue frame 全量文本，而不是用户手写 query。

4. Dense semantic
   用 cue frame embedding 查近邻，作为召回通道，不作唯一分数。

5. Graph spreading activation
   从已命中节点沿 APPLIES_TO / DEPENDS_ON / DERIVED_FROM / CONTRADICTS / SUPERSEDES 扩散。

6. Temporal / task state
   未闭任务、最近变更、dirty/stale/pending、高严重度 hazard。

7. Artifact ownership
   如果要改某文件，直接召回绑定到该文件/模块/测试的记忆。
```

### 5.3 Admission Tiers

候选不要只排一个 top-k。要分层进入上下文：

```text
INTERRUPT
  不读会犯错；例如 owner policy、危险、阶段门、文件写入禁忌。
  允许阻断行动。

WORKING_SET
  当前任务大概率需要；注入摘要 + id + why。

BACKGROUND
  相关但不一定要读；列出 id，可按需 read。

MAINTENANCE
  这次写入/行动可能需要修旧记忆、补边、归档、重嵌。

SUPPRESSED
  相似但被 negative_scope / 过期 / 冲突规则压下；可审计但不注入。
```

输出给 Agent 的不是搜索结果，而是：

```text
Memory admission packet
- 为什么这些记忆被激活
- 哪些是硬阻断
- 哪些是背景
- 哪些动作前必须 read 全文
- 哪些旧记忆需要维护
```

这才真正绕开“数据库悖论”。

---

## 6. 连续评分：不要向二分 reranker 乞讨连续分

### 6.1 基本原则

连续分应由系统自己产生，而不是要求某个 yes/no reranker 输出细腻排序。

二分模型的位置：

```text
可作为一个特征；
可作为高精度确认器；
可作为噪声 veto；
不可作为唯一 rank score；
不可决定“有没有相关记忆”。
```

### 6.2 Feature-based Scorer

每个候选生成特征向量：

```text
trigger_exact              触发器精确命中
trigger_specificity        glob/regex/symbol 的具体度
path_overlap               文件路径重合
symbol_overlap             函数/类/测试名重合
lex_bm25                   词法分
cjk_ngram                  中文 ngram 分
embedding_cosine           dense 相似度
same_domain                是否同覆盖域
graph_distance             图距离
graph_edge_strength        经过硬边还是软边
recency                    最近更新 / 最近使用
priority                   owner/pinned/severity
validity                   active / confirmed / disputed
contradiction_penalty       有无冲突未解决
staleness_penalty           是否过期/被 superseded
usage_success              历史 admission 后是否被 read / accepted
usage_dismiss              历史被 dismiss / rejected
binary_rerank_yes           reranker yes/no 或 sigmoid 极值
```

初始线性分：

```text
score = Σ weight_i * feature_i
```

随后用本项目自己的标签在线校准：

```text
accepted edge / read after admission / human kept    => positive
rejected suggestion / dismissed / false interrupt    => negative
missed memory postmortem                             => hard positive with penalty
```

不用新大依赖也能做：SQLite + Python 标准库实现 logistic update 或 pairwise perceptron 即可。未来需要更强再换成 LightGBM / learning-to-rank，但不是第一步。

### 6.3 为什么这能解决“二分模型”

因为系统最终连续分来自多源证据：

```text
路径命中 0.9
符号命中 0.7
embedding 0.46
hard graph 距离 1
severity high
历史 3 次被采纳
reranker yes/no = no
```

reranker no 只是一个负特征，不会把强触发、高严重度、路径命中的程序性记忆剪成 0。

---

## 7. 写入流程：从 append 改成 reconcile transaction

当前系统最大维护洞之一是“新记忆写进来了，旧记忆没被修”。新系统禁止裸 append。

### 7.1 写入标准流程

```text
memctl remember --draft <file>
```

内部事务：

```text
1. ingest draft -> remember.assert event
2. extract nodes: claim / policy / hazard / decision / artifact refs
3. generate triggers/applicability
4. duplicate search
5. supersession / contradiction search
6. hard dependency search
7. old-node backfill candidates
8. review packet
9. human/agent review
10. commit accepted reconciliation events
11. rebuild projections
12. run eval smoke
```

### 7.2 Reconciliation Packet

写入后系统给的不是“候选相关边列表”，而是：

```text
A. 可能重复
B. 可能取代旧事实
C. 可能冲突
D. 应该补硬依赖
E. 应该绑定 trigger
F. 应该更新旧节点正文/summary
G. 应该归档/降温
H. 只作为软相关
```

示例：

```text
新节点: reranker 二分模型不能连续评分

必须审：
- CONTRADICTS/REFINES old: “reranker 可作连续 rerank score”
- SUPERSEDES old: “降 floor 可修”
- APPLIES_TO trigger: commands contains `--rerank`, text contains `元记忆|抽象查询`
- DEPENDS_ON fact: semantic low adoption verdict
- MAINTENANCE: update meta-index section C
```

这会把“修旧内容”变成流程强制项。

---

## 8. Review UX：不让 Agent 只盖软边

当前关系审阅容易变成：

```text
系统吐 RELATED_TO -> Agent accept -> 图变厚但不承重
```

新审阅要强迫回答关系语义：

```text
这条候选是：
[1] 硬依赖：目标变了源必须重审
[2] 取代旧认知
[3] 冲突并存
[4] 证据来源
[5] 适用触发器
[6] 只是背景相关
[7] 噪声
```

对于 `policy/hazard/decision` 类型，若没有 `APPLIES_TO/TRIGGERS_ON`，check 失败。对于 `claim`，若没有 `EVIDENCED_BY`，check 失败。对于高优先级节点，若零 hard edge 且无 trigger，check 失败。

---

## 9. Memory Lifecycle：剪枝不是删，而是温度和职责变化

节点生命周期：

```text
hot        最近常用 / 高风险 / pinned / open task
warm       普通 active
cold       很少触发，但仍可查
archived   不自动召回，只能手动查
superseded 不作为当前事实，但作为历史证据保留
contradicted 查询时必须和冲突方同时出现
deleted    仅在隐私/错误写入等极少数情况使用
```

温度由使用数据自动更新：

```text
admitted and read -> 升温
admitted and dismissed -> 降温
长期无触发 -> 降温
被 superseded -> 移出 active recall
高 severity hazard -> 保持 hot，除非明确关闭
```

剪枝系统不再靠“人想起来手动清”，而是周期性生成 maintenance packet：

```text
- 可能重复的节点
- 长期无触发的 RELATED_TO 簇
- active 但无 trigger 的 policy/hazard
- superseded 后仍被召回的旧节点
- summary 与正文 hash 不一致
- 高拒绝率 domain 的触发器需要收窄
```

---

## 10. Hooks：从提醒命令变成 memory admission 管线

需要的 hook 层：

```text
SessionStart
  输出 READFIRST + 当前 domain map + open interrupts。

UserPromptSubmit / 等价入口
  把用户消息转 cue frame，输出 admission packet。

PreToolUse
  如果要改文件 / git commit / 调测试 / 改 memory，先按 command/path 召回 watchpoints。

PostToolUse
  记录工具结果；若有错误/测试失败/文件 diff，生成新 cue 并可能追加 admission。

Stop
  轻量检查：未审 reconciliation、未提交 ledger、dirty projection、miss report。

PreCompact
  触发 summary + memory reconciliation packet，不能只靠人记得压缩前写记忆。
```

关键点：hook 不复制业务逻辑，只调用 `memctl admit` / `memctl finalize`。逻辑在内核，hook 是触角。

---

## 11. 与当前系统的迁移关系

### 11.1 不直接改 `cc_memory/mem.py`

这不是补丁式升级。建议新建 `cc_mem2/` 做 shadow mode。

### 11.2 迁移步骤

#### P0：冻结旧系统为输入源

```text
导出 memory.db: events/facts/entries/edges/relation_suggestions/embeddings metadata
转成 ledger events
保留原 id，写入 migrated_from_cc_memory 字段
```

#### P1：构建 projection

从 ledger 生成：

```text
projections/memory.db
projections/MEMORY.md
projections/READFIRST.md
projections/DOMAIN_MAP.md
```

要求：删掉 projection 能全量重建。

#### P2：Shadow admission

每次任务运行：

```text
旧 cc_memory 正常使用；
新 cc_mem2 同时根据 cue frame 输出 admission packet；
不阻断，只记录“它会提醒什么”。
```

#### P3：用旧审阅数据训练初始 scorer

当前已有：

```text
relation_suggestions: accepted/rejected/pending
edges: hard/soft 类型
read/boot/mutations 历史
```

把 accepted/rejected 变成排序训练样本，先校准特征权重。

#### P4：把程序性/危险记忆迁成 trigger-first

优先迁移：

```text
cc_memory 自身操作纪律
codex/claude 分工纪律
git/db 并发危险
P1.2 阶段门/外审状态
precompact/压缩纪律
文件/脚本级坑
```

这些不该靠 search，必须靠 trigger。

#### P5：启用阻断级 admission

当 shadow mode 指标达标后：

```text
INTERRUPT 级记忆开始阻断行动；
WORKING_SET 自动注入；
旧 cc_memory 降为只读迁移源；
最终删除旧写入口。
```

---

## 12. 验收指标

不要用“感觉召回好了”验收。建议硬指标：

```text
Action Recall@K
  对一批历史任务，行动前 admission packet 是否包含后来证明必须看的记忆。

Missed-memory rate
  事后发现“如果早看某记忆就不会犯错”的次数 / 总任务数。

False interrupt rate
  INTERRUPT 级提醒中被人标为噪声的比例。

Hard-edge coverage
  active policy/hazard/decision/claim 中，有证据、有 trigger、有 hard edge 的比例。

Reconciliation coverage
  新写入中，被系统提出 duplicate/supersede/contradict/backfill 的比例与采纳率。

Stale latency
  旧记忆被新事实推翻后，到被 superseded/revised 的时间。

Manual search dependency
  完成任务所需关键记忆中，有多少是靠 Agent 主动 search 才出现；目标逐步趋近 0。

Projection reproducibility
  删除 projections 后全量重建，hash 一致。

Git merge conflict rate
  多会话 ledger 合并冲突率显著低于 SQLite 二进制提交。
```

---

## 13. 最小可行版本

MVP 不需要一上来做 daemon，也不需要新模型。

最小实现：

```text
1. ledger JSONL + projection SQLite
2. cue_extractor：从用户文本、命令、路径、git diff 产 cue frame
3. trigger index：path glob / command / regex / domain / term
4. activator：trigger + lexical + graph activation
5. scorer：手写连续特征分，不用 reranker 排名
6. admission packet：INTERRUPT / WORKING_SET / BACKGROUND / MAINTENANCE
7. reconciler：新增记忆时强制 duplicate/supersede/contradict/hard-edge/trigger 审查
8. retrieval_runs + labels：每次展示和审阅都记样本
```

GPU 可继续作为 dense feature provider，但不是核心依赖。

---

## 14. 明确不要做的事

1. 不要继续调 Qwen3-Reranker floor / instruction / 模型，希望它输出理想连续评分。
2. 不要再在 `cc_memory` 旁边加第四层 overlay。
3. 不要把 “boot 多打印一点” 当成解决召回悖论。
4. 不要把“关系候选 pending review”当成维护闭环；它只解决候选边，不解决旧内容调和。
5. 不要让 `RELATED_TO` 通过审阅就等于维护完成。
6. 不要让 SQLite 二进制继续承担多人 git 真相源职责。
7. 不要把 prompt 纪律当系统保证。prompt 是最后一层，不是内核。

---

## 15. 总结

新系统的心脏不是更聪明的检索模型，而是这条闭环：

```text
现实活动 -> cue frame -> 自动激活 -> admission packet -> 使用/忽略反馈 -> 写入调和 -> projection 重建 -> 指标评估
```

数据库仍然存在，但它只是索引和投影；真正的记忆系统是一个持续运行的注意力与维护机制。

这能同时回应三个问题：

```text
召回率 0：
  不再等待 Agent 主动查，而由 cue/trigger/watchpoint 自动召回。

reranker 二分：
  不再让它输出连续评分，连续分由多特征校准器产生。

没有达成原始目标：
  维护不再是 append + review，而是 write-time reconciliation + lifecycle + missed-memory 学习。
```

如果旧系统是一座整理得越来越好的图书馆，新系统应该是一名值班参谋：它不等你想起书名，而是在你伸手摸错开关前，把该看的操作票拍到桌上。
