# 记忆系统 v-next · 最终方案草案（对抗复核靶稿）

> 这是 8 人评审会三轮 + 定点对质的收敛结论 + 主持裁决。本稿供 contrarian 做最后对抗复核、owner 代言人做红线复核。**攻它。**

## 0. 一句话
把记忆从「等查询的被动数据库」改成「每回合由控制流确定性编译注入的主动卡片系统」；本地 LLM 只在异步补尾部。真相源是人类可读卡片，召回可测进 CI。

## 1. 真相源（D1 已裁：卡片完胜，席2 认输）
- **卡片 `cards/*.md`（YAML frontmatter + 正文）= 唯一真相源 + 当前态直读**。
- **git history = 免费的 byte 级内容审计轨**（`git log -p` 重建任一卡因果史）。
- **一条很窄的 append-only 行为日志**：三约束焊死——只写不读不回放、非真相源、不参与当前态判定。MVP 埋但不消费。唯一合法消费=V2 离线只读两用途：①漏召回事故→回归样本（只读当时 task_frame）②评分器离线校准（读 features→产独立权重文件，不碰卡片）。
- SQLite/embeddings/索引 = 可重建缓存，全部 gitignored。

## 2. 卡片 schema（席3 定稿）
必填公共字段：id/kind/title/scope{domains[]必填,paths[],symbols[]}/status/priority(P0-P3)/triggers/activation。kind∈{constraint,decision,status,pitfall,open_obligation,file_local,reference}。各 kind 必填差异：constraint→severity+scope.paths/symbols；status→validity+同domain唯一active；pitfall→error_regex；open_obligation→validity.until/invalidated_by；decision→provenance。
triggers{intents[],keywords[],negative_keywords[],paths[glob],symbols[],error_regex[],examples[]}，examples≥1 强制（即 activation 夹具）。
provenance{op,supersedes,reason,evidence} 在 supersede/contradict/merge 时必填。

## 3. 召回机制（核心）
### 3a 三类「绝不能漏」确定性触发（0 模型，集合匹配，强制入选不进评分池）（席1）
- 约束型：glob_overlap(scope.paths,frame.paths) or scope.symbols∩frame.symbols or scope.claim_guards∩frame.claims
- 当前状态型：active 且 scope.phases∩frame.phase or claim_guards∩frame.claims；superseded 永不注入
- 开放义务型：status=open 且 (always_on or arming 命中)
### 3b 7 特征可解释评分器（连续分唯一来源，全同步0模型<50ms）（席4）
score = 0.35·trigger_hit + 0.20·bm25 + 0.20·dense_cosine + 0.15·scope_match + 0.05·freshness + 0.05·type_priority [+0.10·graph_prox V1.5]。trigger 全命中直升 L0。
- 二分 reranker 只做可选第8弱特征，V1 不加，不 veto 不主裁。
### 3c 本地 LLM necessity judge（D3 已裁：纯异步，席4 认输同步）
- 纯异步（PostToolUse asyncRewake + 写入时 batch），绝不进每回合同步路径。
- 只判 scorer∈[0.3,0.7] 的边界候选；输入 task_frame+候选，输出 necessary/confidence/reason/miss_consequence。
- per-task_frame_hash 缓存（非 per-session）；超时 conservative-include 降级；缺 GPU 整层静默关闭。
- 副产品=把 necessary 判定回写卡片 trigger.examples，让确定性层越用越准。
- 可选模型 server（ollama 级，单用途无状态）允许存在但是可选加速器；admission 控制逻辑无 daemon（hook one-shot）。
### 3d 分层入选 L0/L1/L2/L3，L1 按 kind 配额、不 top-k（席1）
- L1_QUOTA={三类 must-know: 不封顶; decision:3, pitfall:3, local:2}。两池物理隔离=硬约束不被高频背景挤掉。
- 溢出：先降可选类到 L2 指针→仍超抬 INTERRUPT（绝不静默丢 must-know）。

## 4. 写入即调和（reconcile 前置闸，席7）
- 三态：committed / rejected / pending_nonactive（失败态，非候选队列：不能注入/不能被依赖/不能算完成，无人工清）。
- 同步确定性：schema 校验+同(domain,scope,type)查询+显式字段比较+旧ID映射+缓存近邻+硬边完整性。异步：仅本地 LLM 做语义解释和不确定分类。
- 查 supersede 关系用卡片 relations 硬边图（真相源内），不需独立语义日志。
- RELATED_TO 软边不算调和完成。

## 5. 主动注入（5 hook，席6）
- 薄 wrapper，真逻辑在 `zmem` CLI。读路径只碰离线预建文件索引（trigger 倒排/dense memmap/cards_meta/预编 L0）。
- SessionStart→注 L0(无LLM,<300ms)；UserPromptSubmit→编译 L0+L1 packet(sub-2s,无LLM)；PreToolUse(matcher限Write/Edit/高危Bash/Task/codex)→约束冲突 deny+reason 或 exit2(唯一类INTERRUPT硬阻断)；PostToolUse→async finalize+异步 necessity 精修回写trigger(fire-and-forget绝不阻塞)；Stop→轻量闭合检查。
- 子代理/codex：编排层 spawn 前调 `zmem context --for-subagent` splice packet 进 prompt；PreToolUse 匹配 Task/codex 兜底（无 sentinel→deny 逼父模型重做）。

## 6. 召回可测（席8，把"召回率0"变成可见非0数）
- 金标准集=事故反推法（owner纠正史/项目硬约束红线/花大代价定位的根因），每对 task_frame 必须是 hook 运行时真拿得到的信号。第一批20-30条。
- 指标：StrictHitRate@K（场景级全中，主验收）；三硬类(约束/状态/义务) StrictHitRate 必须=100% **且纯脚本基线单独也100%**（证明三硬类不靠模型从0顶满）；软门全集 Recall@12≥0.85；FloodRate=0；StaleConflictRate=0。
- CI：preflight_gate 内 `activation_gate` 子门 fail-closed；调生产同一份 admission 编译纯函数；漏召回事故→`zmem eval add-case` 固化成回归对。

## 7. MVP 边界（主持裁决：切两刀）
- **MVP-0（最小可证伪，先做）**：卡片+确定性编译器(硬触发+scope+lexical+dense可选不阻塞)+reconcile闸+activation+2hook(SessionStart/UserPromptSubmit)+15-20张高杀伤种子卡。**不含LLM/PreTool/PostTool**。目标=三硬类召回0→100%。
- **MVP-1（MVP-0验收100%后紧接）**：+PreToolUse(INTERRUPT)+PostToolUse(异步necessity LLM回写trigger,可选降级)+行为日志埋点。
- 解锁关口=MVP-0 三硬类 StrictHitRate 100%(含纯脚本基线100%)。
- V2：在线校准(行为日志解锁判据:日志≥500条+三硬类CI≥95%+静态权重Recall两周无提升+shadow ROI≥5pp 四条同时满足)、完整生命周期温度、多帧投票。

## 8. 迁移（席7，提炼非倾倒）
- 第一批15-20张种子卡，标准优先级：pinned常驻层>改变控制流的红线/禁令>exactness/certified红线>已知CRUD坑>零硬边但被多依赖的当前态。
- 具体：cc-memory-meta-index、cc-memory-crud-gotchas、fact-p1-2-supervisor-operability、offline-mode-autonomy-criterion、concurrent-session-shared-index-hazard…每条补 trigger_examples（否则进不了 activation）。
- 旧 cc_memory 上线即冻只读，绝不双活。

## 9. 对抗复核后 · 主持终裁（contrarian + owner 代言人双复核已锤）

**接受的修正（两轮对抗复核）：**
- **行为日志 → MVP 不埋**（contrarian：不消费就不该进 MVP；埋点会拖出 schema/轮转/并发/体积一整套非核心工程，且天然变成"为何没注入"的解释权来源、反压卡片真相源 = 系统伺候自己）。整体推 V2，与在线校准一起设计。
- **necessity LLM → 不进 MVP/MVP-1，降 V2 实验**（contrarian：异步回写 trigger.examples = 自动改真相源的维护代理 = 已否决的 Gardener 换皮；且席1+席5 已证三个杀手例子全部确定性 symbol/path/风险动词可解）。即便 V2 做，只能产建议、经 verify 闸或人确认，**绝不自动改卡**。三例改用：symbol ownership 表 + 风险动词（skip/bypass/fast/gate/preflight/hash/frozen）硬触发 + 首个文件读写前按路径二次注入。
- **金标准集防自证循环（口子A·必焊）**：金标准 frame **必须取自真实事故/owner 纠正的原始信号、由非触发规则作者构造并复核、禁止照 scope.paths/symbols 反填**。否则三硬类纯脚本 100% 是"规则匹配自己"的自证循环。
- **dense 不进同步阻塞（口子B）**：同步 query 编码限时降级或只用预建近邻；三硬类（纯集合匹配）不依赖 dense，基线不受影响；MVP-0 dense 默认关。
- **pending_nonactive 不落真相源（口子D）**：不得落 cards/，进 .quarantine 或带 TTL；写不进 = 写入失败、当场逼调用方解决，不积死卡。
- **V2 权重文件可审（口子C）**：在线校准产的权重必须明文 + 每次改权重 git commit + 可一键回退静态权重。
- **reconcile 最小化**：MVP-0 只做 schema + 同 scope active 冲突 + supersedes/contradicts 必填，不做缓存近邻/语义解释。reconcile 查 supersede 关系用卡片 relations 硬边图 + git（席1 已认输撤回独立日志）。

**最终 MVP 分级：**
- **MVP-0（最小可证伪，先做）**：卡片 + 确定性编译器（path/symbol/keyword/scope，dense 默认关）+ reconcile 最小闸 + activation（防自证金标准）+ 2 hook（SessionStart 注 L0 / UserPromptSubmit 编 L0+L1）+ 15-20 张高杀伤种子卡。**无 LLM、无行为日志、无 PreTool/PostTool**。目标 = 三硬类召回 0→100%（纯脚本基线单独 100%）。
- **MVP-1a**：+ PreToolUse 高危只读阻断（不引入日志/LLM/回写）。
- **V2（凭指标解锁）**：dense 语义、necessity LLM（产建议不自动改卡）、行为日志 + 在线校准（权重明文可回退）、生命周期温度。

**双复核签字**：contrarian —— MVP-0 已对齐最小可证伪、最大烂尾风险（MVP-1 平台化）已砍堵；owner 代言人 —— 口子A 已纳入必焊、B/C/D 边界已写明，红线维度签字。一句话最重预警（contrarian）：别借"异步补尾部/日志埋点"把一个已可证伪的卡片编译器拖回多组件平台。
