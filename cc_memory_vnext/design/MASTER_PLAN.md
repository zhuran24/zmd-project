# 记忆系统 v-next · MASTER 方案(合成版 · 开工权威)

## 0. 状态与来源
- **两个独立 8 人跨模型议会**各自收敛到同一架构 → 方向高可信:
  - 分支线程 `c266318a`(arch/card/ledger/ml/runtime/datamodel/skeptic/owner-advocate,3 轮 + 双对抗复核 + 验收官红线签字)→ 终裁版 `C:\Users\22957\memory_redesign_council_final_draft.md`(**更硬,作基线**)
  - 本会话 `mem-redesign-council`(card/retrieval/eval/synthesizer + ledger/rewrite-skeptic/write-recon/integ-storage)→ `记忆系统-3\COUNCIL_FINAL_PLAN.md`(**独立交叉印证**)
- 本 MASTER = 分支终裁版骨架 + 交叉印证标注 + 分歧裁决,作开工权威。

## 1. 一句话
把记忆从「等查询的被动数据库」改成「每回合由 hook 确定性编译注入的主动卡片系统」;**纯确定性先证明召回非 0**,语义模型/行为日志/自动维护全部凭指标往后解锁。

## 2. 两个议会共同收敛的核心(= 高可信,直接做)
1. **真相源 = 人类可读卡片 `cards/*.md`**(YAML frontmatter + 正文,打开即当前态)+ **git history = byte 级审计轨**;SQLite/embedding/索引全是可重建缓存(gitignored)。彻底告别 SQLite 当真相源。
2. **旧 cc_memory 上线即冻只读,绝不双活**。
3. **召回 = 确定性激活为核心**(trigger/scope 集合匹配),reranker 降级为弱特征/投票、**不当裁判**(不逼二分模型出连续分)。
4. **hook 强注入**(SessionStart/UserPromptSubmit + 子代理 splice),不靠模型自觉 boot。
5. **15-20 张高杀伤种子卡**;判据 = 写不出具体 trigger example 的条目不进 active recall。
6. **召回可测**:金标准回归集来自真实事故/owner 纠正史;CI activation_gate fail-closed。
7. scorer 学习 / gardener / distiller / 语义模型 全凭指标推 **V2**。
8. **写入即调和**当提交闸(schema + 同 scope active 冲突 + supersedes/contradicts 必填)。

## 3. 分歧裁决(两议会唯一冲突点)
- **append-only 行为日志 → 砍出 MVP**(以分支裁决为准)。理由:① contrarian:埋而不消费 = 逻辑漏洞,MVP 不消费就不该进;埋点拖出 schema/轮转/并发/体积一整套非核心工程,还天然变成「为何没注入」的解释权来源、**反压卡片真相源 = 系统伺候自己** ② 真相源已是 cards + git,**git history 本身就是 byte 级审计轨**,MVP 阶段单独日志 provenance 价值与 git 大量重叠。
- 本会话 ledger 派的"未来上 ledger 缺历史返工"顾虑 → 留作 **V2 设计输入**(V2 上行为日志+在线校准时按 ledger 兼容设计,权重明文可回退),不进 MVP。

## 4. 架构(锤定)
### 4.1 真相源
卡片 schema 必填公共:`id/kind/title/scope{domains[]必填,paths[],symbols[]}/status/priority(P0-P3)/triggers/activation`。`kind∈{constraint,decision,status,pitfall,open_obligation,file_local,reference}`。各 kind 必填差异:constraint→severity+scope.paths/symbols;status→validity+同 domain 唯一 active;pitfall→error_regex;open_obligation→validity.until/invalidated_by;decision→provenance。`triggers{intents[],keywords[],negative_keywords[],paths[glob],symbols[],error_regex[],examples[]}`,**examples≥1 强制(= activation 夹具)**。`provenance{op,supersedes,reason,evidence}` 在 supersede/contradict/merge 时必填。
### 4.2 召回三层
- **3a 三类「绝不能漏」确定性触发(0 模型,集合匹配,强制入选不进评分池)**:约束型(glob/symbol/claim_guard 重叠)、当前状态型(active 且 phase/claim 命中;superseded 永不注入)、开放义务型(open 且 always_on/arming 命中)。
- **3b 7 特征可解释评分器**(连续分唯一来源,全同步 0 模型 <50ms):`score = 0.35·trigger_hit + 0.20·bm25 + 0.20·dense_cosine + 0.15·scope_match + 0.05·freshness + 0.05·type_priority`;trigger 全命中直升 L0。二分 reranker 只做可选第 8 弱特征,V1 不加。
- **3d 分层 L0/L1/L2/L3,L1 按 kind 配额不做 top-k**:`L1_QUOTA={三类 must-know 不封顶; decision:3, pitfall:3, local:2}`,**两池物理隔离 = 硬约束不被高频背景挤掉**;溢出先降可选类到 L2 指针→仍超抬 INTERRUPT,**绝不静默丢 must-know**。
### 4.3 写入即调和(前置闸)
三态 committed/rejected/**pending_nonactive**(失败态:不注入/不被依赖/不算完成/不落 cards,进 .quarantine 或带 TTL);同步确定性(schema+同(domain,scope,type)查询+字段比较+硬边完整性);supersede 关系查卡片 relations 硬边图 + git,**不需独立语义日志**;RELATED_TO 软边不算调和完成。
### 4.4 主动注入(hook,薄 wrapper,真逻辑在 `zmem` CLI)
读路径只碰离线预建索引(trigger 倒排/dense memmap/cards_meta/预编 L0)。SessionStart→注 L0(无 LLM <300ms);UserPromptSubmit→编 L0+L1 packet(sub-2s 无 LLM);PreToolUse(matcher 限 Write/Edit/高危 Bash/Task/codex)→约束冲突 deny+reason 或 exit2(唯一 INTERRUPT 硬阻断);PostToolUse→async finalize;Stop→轻量闭合检查。子代理/codex:编排层 spawn 前 `zmem context --for-subagent` splice 进 prompt。
### 4.5 召回可测
金标准 = 事故反推(owner 纠正史/项目硬约束红线/花大代价定位的根因),每 frame 必须是 hook 运行时真拿得到的信号,第一批 20-30 条。指标:**StrictHitRate@K**(场景级全中,主验收);三硬类 StrictHitRate **=100% 且纯脚本基线单独也 100%**(证明三硬类不靠模型从 0 顶满);软门 Recall@12≥0.85;FloodRate=0;StaleConflictRate=0。CI:preflight 内 `activation_gate` 子门 fail-closed。

## 5. MVP 分级(切两刀)
- **MVP-0(最小可证伪,先做)**:卡片 + 确定性编译器(path/symbol/keyword/scope,**dense 默认关**)+ reconcile 最小闸 + activation(防自证金标准)+ **2 hook**(SessionStart 注 L0 / UserPromptSubmit 编 L0+L1)+ **15-20 张高杀伤种子卡**。**无 LLM、无行为日志、无 PreTool/PostTool**。目标 = 三硬类召回 0→100%(纯脚本基线 100%)。
- **MVP-1a**:+ PreToolUse 高危只读阻断(不引入日志/LLM/回写)。
- **V2(凭指标解锁)**:dense 语义、necessity LLM(**只产建议、经 verify 闸或人确认,绝不自动改卡**)、行为日志 + 在线校准(权重明文 git commit 可回退,按 ledger 兼容)、生命周期温度。**解锁关口 = MVP-0 三硬类 StrictHitRate 100%(含纯脚本基线 100%)。**

## 6. 焊死的红线(验收官口子,必守)
- **A(必焊)**:金标准 frame **必须取自真实事故/owner 纠正的原始信号、由非触发规则作者构造复核、禁止照 scope.paths/symbols 反填**(否则三硬类纯脚本 100% = 规则匹配自己的自证循环)。
- **B**:dense 不进同步阻塞;三硬类纯集合匹配不依赖 dense;MVP-0 dense 默认关。
- **C**:V2 在线校准权重必须明文 + 每次改 git commit + 可一键回退静态权重。
- **D**:pending_nonactive 不落 cards/(进 .quarantine 或 TTL);写不进 = 写入失败当场逼调用方解决,不积死卡。
- **necessity LLM**:不进 MVP/MVP-1a;即便 V2 也只产建议、绝不自动改卡(= 已否决的 Gardener 换皮)。3 个杀手例改用 symbol ownership 表 + 风险动词(skip/bypass/fast/gate/preflight/hash/frozen)硬触发 + 首个文件读写前按路径二次注入。

## 7. 种子卡迁移清单(提炼非倾倒)
优先级:pinned 常驻层 > 改变控制流的红线/禁令 > exactness/certified 红线 > 已知 CRUD 坑 > 零硬边但被多依赖的当前态。首批具体:`cc-memory-meta-index`、`cc-memory-crud-gotchas`、`fact-p1-2-supervisor-operability`、`offline-mode-autonomy-criterion`、`concurrent-session-shared-index-hazard`、`codex-executes-claude-orchestrates`、`terminology-meeting-equals-team`、`use-codegraph-before-grep`… 每条补 trigger_examples(否则进不了 activation)。

## 8. 开工
**MVP-0 先做**,codex 实现 → claude 审 → 回环至 clean → 主控终审。建在 repo 新目录(如 `cc_memory_vnext/`,旧 cc_memory 只读不动)。Day1-2 地基(schema+verify+zmem 骨架+确定性编译器+2 hook+首批 5 张种子卡)起步,Day3 金标准回归集 + activation_gate,Day4-5 补满 15-20 卡 + 验收三硬类 100%。**铁律:宁可 recall 低也要先有 packet;别借异步/日志把可证伪的卡片编译器拖回多组件平台。**
