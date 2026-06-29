# cc_memory_vnext — 主动卡片记忆系统 (MVP-0)

> 状态:**MVP-0 已落地 + 多轮深化**(卡数 / 金标准数**以 `zmem verify`/`eval` 为准、不硬编码防漂移**;三硬类 StrictHitRate=100% 纯脚本基线)。
> 旧 `cc_memory/`(SQLite)与本层**互补共存**(非新旧替代、整库迁移非目标):cc_memory = 全量可查历史库 + 写入收件箱(仍现役、可写),本目录 = 主动推送精选层。**"冻结"=按条 archive-on-promotion**(某条做成卡 → archive cc_memory 源条目防漂移;图枢纽条目留薄"图锚/指针节点"保边)。2026-06-30 三处文档(MASTER_PLAN/COUNCIL_FINAL_PLAN/CLAUDE.md)已对齐定调(详 `cards/memory-three-layer-coexistence-decided.md`)。本目录是并存的主动推送层。

## 1. 为什么重做(根病)

旧 `cc_memory` 是**被动数据库**:得先知道有某条记忆、才会去 `search` 它。但很多该用记忆的当口是 **route-time 反射判断**(要不要主动压缩、用不用 codegraph、"开会"是起 team 还是 wf),那一刻根本不会去查 → **零召回**。证据就是 owner 反复纠正同几件事(precompact 纪律、codegraph、开会=team)记了多次都没用。

两个独立 8 人跨模型议会各自收敛到同一结论:把记忆从「等查询的被动库」改成「**每回合由 hook 确定性编译注入的主动卡片系统**」。

## 2. 架构(锤定)

- **真相源 = 人读卡片 `cards/*.md`**(YAML frontmatter + 正文)+ git history 当 byte 级审计轨。
- **索引/嵌入 = 可重建缓存**(`.index/`,gitignored,删了能重建)。彻底告别 SQLite 当真相源。
- **召回 = 确定性激活**(trigger / scope 集合匹配,**0 模型、无 LLM**),reranker 降级、不当裁判。
- **hook 强注入**(SessionStart 注 L0 / UserPromptSubmit 编 L0+L1),不靠模型自觉 boot。
- **召回可测**:金标准回归集来自真实事故 / owner 纠正史,`eval` 跑 StrictHitRate,CI 可 fail-closed。

### 分层
- **L0** = 三类「绝不能漏」**强制入选**(不进评分池):
  - `constraint`(约束):scope/triggers 的 path-glob 命中、symbol 交集,或 **`activation.claim_guards` 关键词命中 prompt**。
  - `status`(当前态):active 且 `activation.phase/claims/claim_guards` 命中;superseded 永不注入。
  - `open_obligation`(开放义务):`always_on` 或 `arming` 命中。
- **L1** = 可选类按 kind 配额(`decision:3, pitfall:3, file_local:2, reference:3`),**只有 trigger>0 或 scope>0 的强信号才占槽**;纯 bm25 子串噪声降 L2(防 flood)。
- **L2** = 溢出 / 弱信号指针。

## 3. CLI

```bash
python cc_memory_vnext/zmem.py verify          # 校验卡片 schema + 调和闸(同 scope 冲突/同 domain 双 active status)
python cc_memory_vnext/zmem.py build-index     # 卡片 → 确定性离线索引
python cc_memory_vnext/zmem.py context --require-index --layers L0,L1 --frame-json '{"prompt":"..."}'
python cc_memory_vnext/zmem.py eval            # 跑金标准回归(StrictHitRate)
```

## 4. 卡片 schema(verify 强制)

顶层必填:`id`(小写 slug) / `kind` / `title` / `scope{domains[]必填,paths[],symbols[]}` / `status` / `priority(P0-P3)` / `triggers` / `activation`。
`triggers` 必含 7 个列表:`intents/keywords/negative_keywords/paths/symbols/error_regex/examples`,其中 **`examples≥1`(=激活夹具)**。
逐 kind 额外强制:
- `constraint` → 顶层 `severity` + scope.paths/symbols 至少一个非空;**要被自然语言 prompt 命中需补 `activation.claim_guards`**。
- `status` → 顶层 `validity`;同 domain 唯一 active。
- `pitfall` → **顶层** `error_regex`(非空)。
- `open_obligation` → `validity.until` + `validity.invalidated_by`。
- `decision` → `provenance`。
- P0/P1 → `provenance.evidence` 非空。

## 5. 红线(MVP-0 焊死)

- **无 LLM、无行为日志、无 PreToolUse/PostToolUse**(MVP-0 只读编译 + 2 hook)。
- **dense 默认关**:三硬类纯集合匹配,不依赖 dense(`--enable-dense` 是 V2 预留)。
- **金标准防自证(red-line A)**:回归 frame 取自真实事故 / owner 纠正的**原始信号**,由**非触发规则作者**(codex 写卡 → claude 盲写 frame)构造,**禁照 scope.paths/symbols 反填** → 三硬类纯脚本 100% 不是"规则匹配自己"。
- 旧 `cc_memory/`:**与 vnext 互补共存**(全量可查库,仍现役可写);"冻结"=按条 archive-on-promotion、整库迁移非目标(2026-06-30 定调,详 `cards/memory-three-layer-coexistence-decided.md`)。

## 6. 现状指标(实时为准,不硬编码防漂移)

- **卡数**:`python cc_memory_vnext/zmem.py verify`(本会话已远超初始 15)。
- **金标准 / eval**:`python cc_memory_vnext/zmem.py eval`(StrictHitRate,含 `forbidden_cards` precision 锁)。
- **三硬类 StrictHitRate = 100%(纯脚本基线 dense-off 也 100%)** = 解锁 V2 的硬门槛已达成。
- ③ 召回触发的真地基已转到「可观测提交点记忆闸(ZMEM_PROOF)」,详 `design/observable-commitment-gate-20260628.md`。

## 7. 已知边界(诚实标注,非 bug)

- **claim_guards 是关键词子串匹配**:对金标准场景确定性命中;对**金标准之外的改写措辞**可能漏(关键词没覆盖到)。泛化是 **V2 dense 语义层**的事,MVP-0 不解决。
- 残留话题邻近 flood(共享关键词的卡偶尔同现)未全清,但纯 bm25 噪声已砍。

## 8. V2 路线(全部凭指标解锁,不在 MVP-0/1a)

解锁关口 = MVP-0 三硬类 StrictHitRate 100%(含纯脚本基线)**已达成**;以下仍按各自指标门槛逐项推进:
- **MVP-1a**:PreToolUse 高危只读阻断(不引日志/LLM)。
- **V2**:dense 语义召回;necessity-LLM(**只产建议、经 verify 闸或人确认,绝不自动改卡**);行为日志 + 在线校准(权重明文 git 可回退);生命周期温度。

权威设计:`记忆系统-3/MASTER_PLAN.md`(合成版)+ 分支终裁 `memory_redesign_council_final_draft.md`。
