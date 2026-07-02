# 主动记忆系统重构 — 八人议会最终方案

> 议会 `mem-redesign-council`(4 Claude + 4 Codex,2026-06-26)从两份提案(A=事件账本/Active Memory Kernel,B=card-deck/context-compiler)收敛而来。两个反方(ledger-arch 纯账本派、rewrite-skeptic 反重写派)经挑战轮均收敛。主席(Opus 主会话)终审通过。

## 三个分歧的收敛结论

- **F1 重写 vs 演进** → **只读 shadow 激活层 + 延后存储重写**。薄的新目录 `cc_memory_activation/` 只做只读索引/评分/报告,入口挂 `python cc_memory/mem.py activate ...` 子命令;不写回 memory.db、不改 mem.py 语义、不建取代 memory.db 的新真相源。铁律:shadow 产物禁止被当事实源。
- **F2 真相表示** → **混合 + 延后**。MVP 精选 15-20 张种子卡(写不出具体 trigger example 的条目不进 active、留 legacy);memory.db 当 legacy 读真相,种子卡=激活元数据层;"卡片是否最终取代 memory.db"延后到指标证明后再定。第一天起加最小 append-only 操作日志(ledger 派底线)。
- **F3 核心机制** → **activation-first MVP**:悖论不是被"更好的卡"打穿、是被"注入时机"打穿——先有注入,再优化卡质量。

---

## 1. MVP 范围(6 件,按依赖序)

| # | 件 | 独立验收 |
|---|---|---|
| M1 | 种子卡 15-20 张 + `zmem verify` gate | verify 通过;每卡 ≥2 trigger examples;高优卡有 evidence(否则 CI fail) |
| M2 | Domain Atlas(10 域,静态 .yaml) | SessionStart 注入 atlas 摘要;`verify --atlas` 每卡至少归属一域 |
| M3 | append-only 操作日志(卡片写 + 激活决策) | 每次 mutation 写 card_writes.jsonl;每次 activate 写 activation_decisions.jsonl;INSERT-only |
| M4 | `mem.py activate` 子命令(trigger+domain+lexical 三路→分层 packet) | 给 context JSON 输出 INTERRUPT/WORKING_SET/BACKGROUND/MAINTENANCE 四层;触发器手写 30-50,不自动生成 |
| M5 | Hook 强注入(SessionStart/UserPromptSubmit/PreToolUse) | 新 session 不靠手动 boot 拿到 packet;codex 子代理由 orchestrator 派发前塞同一 compiler 的 snapshot |
| M6 | Eval 回归集(20-30 条 query→expected_cards) | 来自 会话.txt 真实出错场景;`zmem eval` 跑出 Action Recall@L1 baseline |

**推到第二刀(不进 MVP)**:scorer 学习 / gardener 自动整理 / distiller(episode→card 自动提取)/ binary-vote 多视角 reranker / 存储真相源全量迁移 / 完整 projection 可重建。

## 2. 目录/入口形态

```
cc_memory_activation/          # shadow 激活层,只读 memory.db,不写回
  cards/ {rules,pitfalls,status,procedures,preferences}/   # 种子卡真相(.md+frontmatter)
  domains/  domain-*.yaml       # Domain Atlas(10 域)
  eval/ regression.jsonl        # 20-30 条 {query, expected_cards, source_session}
  logs/                         # append-only
    card_writes.jsonl           # {op,target_id,before_hash,after_hash,reason,actor,session,ts}  [git-tracked]
    activation_decisions.jsonl  # {ctx_hash,candidates[{id,hash,score,tier}],working_set,rejected_neighbors,corrections,ts}
  index/ triggers.sqlite        # gitignored,可删重建
  zmem.py / schema/{card_schema,domain_schema}.yaml
```
入口:`mem.py activate --context-json <p>`(薄 wrapper 调 zmem)、`zmem verify`(CI)、`zmem eval`、`zmem build-index`。铁律:激活层任何代码不得写 memory.db;packet 只传调用方、禁写持久存储当事实源。

## 3. 上线门槛(三档)

- **第一档 Shadow(日志观察、不阻断)**:M1-M6 验收通过即进,采真实数据。
- **第二档 L1/L2 主动推荐(注入 WORKING_SET/BACKGROUND、不阻断)**:Action Recall@L1(高优卡)≥80%;trigger/domain/lexical 三路各 ≥5 unique contribution;连续 5 天无"注入完全无关内容"投诉。
- **第三档 INTERRUPT 阻断**:false-interrupt rate <15%(人工标注);Action Recall@L1 ≥85%;INTERRUPT 仅限最严重 hazard(≤10 张卡有资格)。

存储真相源迁移不设时间表,第二档达标后再评估。

## 4. 风险→缓解表

| 来源 | 风险 | 机制 |
|---|---|---|
| ledger-arch | 激活决策不可溯源;card mutation 可覆盖 | 两个 .jsonl INSERT-only;verify 查追加模式;禁 OR REPLACE |
| card-arch 三闸 | 新卡推翻旧卡仍 active;evidence 无引;scope 重叠静默 | verify:高优空 evidence→fail;同 scope collision 未声明 supersede/contradict→fail;supersede 由命令写 status+valid_to,禁手改 |
| eval-lead | activation tests 无对照自圆;INTERRUPT 误报未知 | regression 来自真实出错场景(不自造);false-interrupt<15% 作第三档硬门 |
| retrieval-eng | 触发器自动生成质量差;多路名义并存实单路撑 | 触发器全手写、miss-postmortem 扩;`eval --channel-stats` 每路 hit-rate+unique,各自门槛 |
| write-recon | 新节点 active 但旧节点未 touched;高 severity 被误降温 | verify:同 scope 旧 active 未在 changeset→fail(回填正文非只加边);温度衰减豁免 severity=high hazard(除非显式 tombstone) |
| integ-storage | 子代理拿不到 packet;codex 仍靠自觉 boot | hook 调 mem activate(只读);codex 子代理 orchestrator 塞 compiler snapshot |
| Atlas 单点失效 | atlas 过时则整个领域凭空消失 | `verify --atlas` 每卡有归属域;域文件变更查 key_cards 仍 active;gardener(二刀)定期 diff cards vs atlas |

## 5. 第一周最小路径(Day4 末前第一个真实 session 收到真 packet)

- **Day1(4h)地基**:card_schema + verify 骨架;5 张最高优种子卡(rerank二分限制/crud gotchas/precompact纪律/codex分工/P1.2 gate);两个 .jsonl 追加写封装。验收:5 卡 verify 过、日志可追加。
- **Day2(4h)注入骨架**:10 域 atlas;`zmem activate`=trigger 精确+domain 匹配→packet(BM25/dense 先不接);5 卡手写触发器;wire SessionStart。验收:敲"重新设计记忆系统",atlas+rerank限制卡进 WORKING_SET。
- **Day3(3h)可测**:regression.jsonl 20 条;`zmem eval` 跑通出 Recall@L1+per-channel;修明显 trigger miss。验收:Recall@L1≥60%(基准非门槛)。
- **Day4-5 补全**:种子卡补到 15-20;接 UserPromptSubmit/PreToolUse;codex orchestrator 注入;verify 接 preflight(只 warn);shadow 期 5 天观察。
- **关键约束**:Day3 末 activate 还出不了 packet → 立刻砍 BM25/dense 候选路、只做触发器精确匹配,保 Day4 注入。**宁可 recall 低,不要没有 packet。**

---

## 主席终审补充(2 条实现收紧)

1. **种子卡 vs memory.db 真相边界**:15-20 张卡对自身内容是真相,对应 memory.db 源条目标 migrated/legacy,避免同一记忆出现卡和 db 两份会漂移的真相。
2. **日志 git 跟踪钉死**:`card_writes.jsonl`(=provenance、未来 ledger 种子)**git-tracked**(随 clone 存活);`activation_decisions.jsonl`(遥测)可本地或为 eval 跟踪。

**一句话**:`cc_memory_activation/` 建只读激活层,15-20 手写种子卡 + 10 域图 + hook 强注入打穿召回悖论;memory.db 不动,指标达标前不迁存储真相源;scorer/gardener/distiller 是第二刀。
