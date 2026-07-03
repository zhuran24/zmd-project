# 记忆系统档案 — 来历 / 现状 / 路线 / 未解

> 这份档案存在的理由很反讽:这套主动记忆系统,本来记不住自己的故事。背景、重写过程、关键裁决、待做未做,过去只散在易丢的 download 文档 + 各次对话里。本文是**单一连贯入口**;一手设计语料在同目录 `design/`(已随仓库存活)。
> 最后更新:2026-07-04。

## 0. 一句话

记忆从「一条条存、靠人/Agent 自己 grep 关联」一路演进到「SQLite 单一真相 + 系统主动发现关系 + GPU 语义」,但仍卡在**被动数据库悖论**(得先知道有记忆才会查);v-next 把它改成「每回合 hook 确定性编译注入的**主动卡片系统**」。现状 = v-next MVP-0 上线;旧 cc_memory **仍现役可写**——2026-06-30 已裁定三层互补共存、整库迁移非目标,"冻结"=按条 archive-on-promotion(裁定见 `memory-three-layer-coexistence-decided` 卡;§4 里的口径打架已由该裁定收口,那段保留作史料)。

## 1. 完整演进链(背景 = 重写前)

> 一手详情:`design/evolution_summary_20260626.md`(slim/关系发现/GPU 那几章) + `design/proposal_A_*` `design/proposal_B_*`(v-next 两提案) + `design/council_*`(两议会)。

- **第0章 旧多树 Markdown 记忆**:`cc_context/memory/` + `_cc_live_memory/` + harness 快照/harvest 等**多棵树**。问题:fact 只是概念标签(无 subject/predicate/value/status/version)、`[[wikilink]]` 不是 typed edge(无法安全做影响面传播)、多副本同步、freshness gate 有"第二次 stale edit"逻辑洞、generator 不是完整 lockfile、repo→live harness 写入路径危险、缺事件层/变更事务层(答不了"为什么改/谁改/影响谁/能否回滚")。
- **第1章 typed-graph overlay(v2/v3/v4)**:在旧系统旁加 `memory_graph/`、typed edge、impact、bootstrap、freshness gate。**失败教训**:这不是重构,是给旧系统加外骨骼 → 变成**第三棵树**。owner 点破:"图不该是另一棵树,图应该就是记忆系统本身。"
- **第2章 slim rewrite → 单一真相 `cc_memory/memory.db`**:一个真相源 + 一个 CLI(`mem.py`)+ 少量可重建视图(`exports/MEMORY.md`)+ 旧系统归档。表:meta/events/facts/entries/edges/aliases/changes。**= 今天的 cc_memory 雏形。**
- **第3章 关系发现 + 本地计算 + GPU**:根问题"新增条目谁来找相关项?不能靠使用者能力" → `relation_suggestions`(系统产候选边、人审、高分未审则 `check` 失败)。先做**零新增依赖**版(FTS5 BM25 + token 重叠 + 中文 ngram + 一跳图扩展),再上 **GPU 语义**(原计划默认 bge-m3 → 选型后判 bge-m3 过时降级 → **实际部署 Harrier 嵌入(P1)+ Qwen3-Reranker(P2)**;GPU 只作可选检索后端、不做第四棵树。**实测低采用 → 暂停继续投入**)。沉淀原则:单一真相 / Markdown 是视图非源 / 图不是另一棵树 / 系统帮发现关系 / 候选≠真相 / check 阻断未审 / GPU 只增强 / 加依赖前先确认。
- **第4章 被动数据库悖论 → v-next(本会话)**:即便有了语义检索,仍犯**根病**——route-time 反射判断的当口不会主动 `search`,于是零召回(实证:owner 反复纠正同几件事记多次没用)。叠加几个硬坑(一手提案反复点):`search` 是整串 `LIKE` 子串、不走 FTS/语义,**多词查询常落空**;`--semantic` 是 opt-in、慢、**实测低采用**;`relation_suggestions` 主产软边 `RELATED_TO`、几乎不自动产 `SUPERSEDES/CONTRADICTS` → **旧认知 stale 不回填**(召回到也是旧的)。两个独立 8 人跨模型议会各自收敛到同一架构 → v-next:**每回合 hook 确定性编译注入的主动卡片系统**。

## 2. v-next 设计的关键裁决(重写过程)

> 一手:`design/MASTER_PLAN.md`(合成版/开工权威)+ `design/council_A_branch_final_draft.md`(更硬,基线)+ `design/council_B_session_final_plan.md`(交叉印证)。

- **真相源 = 人读卡片 `cards/*.md` + git 审计轨**;SQLite/embedding 降为可重建缓存。
- **召回 = 确定性激活为核心**(trigger/scope 集合匹配,0 模型);reranker 降级为弱特征、不当裁判。
- **三类 must-know 强制入选**(constraint/status/open_obligation,不进评分池);其余按 kind 配额进 L1。
- **hook 强注入**(SessionStart/UserPromptSubmit + 子代理 splice),不靠模型自觉 boot。
- **召回可测 + red-line A**:金标准取自真实事故/owner 纠正的原始信号,由非触发规则作者构造、**禁照 scope 反填**(防"规则考自己")。
- **分歧裁决**:append-only 行为日志**砍出 MVP**(git 已是 byte 级审计;埋而不消费=负债 + 反压真相源)。"卡片是否最终取代 memory.db"延后到指标证明。
- **协作分工**:大工作量实现交 codex、小活/审/对抗交 claude;跨模型审(谁做的活另一模型审)。本会话即按此:codex 写卡 → claude 盲写金标准 → 主控 eval/codex 跨模型审。

## 3. 现状(2026-06-27)— 三层并存

| 层 | 是什么 | 状态 |
|---|---|---|
| **旧 cc_memory**(SQLite,~106 条) | 协作库,`mem.py` 驱动;全量低摩擦历史库+写入收件箱 | **现役可写**(2026-06-30 裁定三层互补共存;"冻结"=按条 archive-on-promotion,整库迁移非目标——见 `memory-three-layer-coexistence-decided` 卡) |
| **新 v-next**(`cc_memory_vnext/`,卡数以 `zmem verify` 为准) | 主动注入层,叠在旧库之上 | **MVP-0 上线**(见下) |
| **harness 记忆**(`~/.claude/.../memory/*.md`) | 跨项目、本地、不进仓库 | 活(MiMo/precompact 等 route-time 反射规则) |

**MVP-0 已落地实况**(均 push main;卡/金标准/eval 数实时以 `zmem verify`/`eval` 为准,本文不钉具体数字防漂移)/ **三硬类 StrictHitRate=100%(纯脚本基线)** / 编译器 flood 收口(L1 准入要 trigger 或 scope>0,codex 跨模型审 CLEAN)/ 2 hook 实时注入(已接 `.claude/settings.local.json`)/ **最小遥测**(`zmem context --log` → `logs/activation_decisions.jsonl`;**本地、gitignored、非真相源、≠被 MASTER 砍掉的 append-only 行为 ledger**——只记每回合注入了哪些卡,可删重建)/ **自喂养纪律 institutionalize**(CLAUDE.md + `vnext-maintenance-discipline` 卡:被纠正/踩坑→补金标准+卡)。判官机制已实证可行(blind 模型四条全中)。

**2026-07-03 衍生操作召回批**(owner 重提「vnext 只认提示词、回合中途衍生操作不触发注入」= ③ 已知缺口;按 recall-trigger 四层方案 + commitment-gate 地基落第一批):
- **UPS frame 富化**(Layer 0):`zmem context --enrich-frame` 确定性抽 prompt 里的路径 token / 索引已知 symbols / 风险动词 intents(零 LLM、additive-only),UPS hook 已启用;eval 支持逐 case `"enrich": true`,两条真实事故 frame 当富化回归护栏。
- **error_regex 通道通电**(「遇到什么」召回,recall-trigger §4.1):frame 新增 `errors` 字段,任何卡的 triggers/顶层 error_regex 命中 → force L0(reason=`error_regex_hit`);`hooks/post_tool_error_recall.py`(PostToolUse sync)撞错当场注 additionalContext,会话级账本同卡只弹一次(账本只活在建议通道、绝不参与 deny)。
- **L0 常驻**(Layer 1):`concurrent-session-shared-index-hazard` 升 `session_start_l0`(resident-design 席「最该常驻」裁决;session-start 常驻批已入 eval)。
- **PreToolUse 高危窄门**(= MVP-1a,Layer 2):`hooks/pre_tool_risk_gate.py` — git add -A/./-u、commit -a/-am → deny;push --force、rm -rf、Remove-Item -Recurse -Force、冻结工件 Write/Edit → ask;只认结构信号(先剥引号防 echo 误伤)、fail-open、`ALLOW_RISK_GATE` 逃生门。
- **ZMEM_PROOF 第一版**(commitment-gate 键石):`zmem search "<query>"` 打包激活结果 + 吐 `ZMEM_PROOF` 行(留 transcript 审计)+ 落 `logs/proofs.jsonl`;窄门对 ask 类动作先查本会话 45min 内 domain 相交的 proof,有则放行 = 「没查不准提交」最小闭环。**未做**:Stop 输出闸、`memory.skip` 显式留痕、`observable_from` 卡契约 / `verify --coverage`(仍在 §5 路线)。
- **影子测量**(measurement 席「先测后建」):`hooks/post_tool_shadow.py`(PostToolUse async,全工具)把 tool_input/response 确定性投影成 frame(prompt="" → bm25 恒 0),只记「本会注哪些卡」到 `logs/shadow_activations.jsonl`、一张不真注——「prompt 没注、动作会注」的真实载荷从此有数据。enrich 正向金标准按 red-line A 等影子挖出真实事故再补、不反填。
- 每回合看守(第四档)维持不买:先拿影子数据量残余缝。eval 19→24 全绿;三 hook 共 20 条决策路径实测通过(deny/ask/allow 边界、proof 解锁闭环、账本去重、影子落盘)。
- **同日四视角 codex 对抗审查(16 findings)后加固**:窄门重写为 quote-aware tokenize(修 `git -C <dir> add -A`、`git add "."` 两个 deny 绕过 blocker;rm 递归/强制标志分开解析,`--force` 不再误判);ALLOW_RISK_GATE 只降 ask、对 deny 无效且 deny 文案不再教绕过;proof 规则收紧(身份不明不认署名 proof;未署名 proof 只给 10min 短窗;proof domain 只来自 query 真实命中卡的 scope——自报 `--domains` 参数整个移除,实测它会进 frame 制造 scope 命中把解锁变成自助声明;proof 落盘失败显式报错不吐假 proof);无 pathspec 裸 commit 补 ask(worktree 私有 index 豁免);冻结工件按目录限定路径匹配(root 级要求同目录 PROJECT_LOCK.md,fixtures 同名不再误拦);error_recall 账本文件名白名单清洗防路径穿越;两张卡过宽 error_regex 收窄(non-fast-forward 归 push-conflict 专属;裸 no matches 要求 mem.py/cc_memory 语境),hook 给 errors 文本加命令前缀供正则锚定;RISK_VERB_INTENTS 去掉裸「提交/推送」防非 git prompt 误映射。eval 24→27(3 条新增负向/语境金标准均源自审查实测假阳性 + 真实 2026-06-30 事故投影形状)。**已知债(minor,记录不修)**:proofs/shadow 日志无轮转(gate 已 tail-read 64KB 缓解);同步 hook 冷启 ~170-195ms/次;未加引号的 echo 字面量危险串会误 ask;路径抽取正则按空白切 token,带空格路径(`C:\claude pj\...`)被截断成两段——尾段仍含 repo 相对结构、`*/pat` glob 照常命中,只丢前缀精度(2026-07-03 接线当日真实影子日志坐实);~~error_regex 分不出「真撞上」和「文本提到」~~——**同日已修(2026-07-03 晚)**:实测 PostToolUse payload 无退出码(只有 stdout/stderr/interrupted,shadow 日志新增 response_keys 字段坐实),且设计要保住 stdout 结果类召回(mem.py "no matches"),所以解法不是砍通道而是**锚定约定:error_regex 必须以 `\\$ [^\\n]*<命令特征>` 开头**(投影 blob=「$ 命令行\n输出」;git 报错要求命令行含 git,mem.py 结果要求命令行含 mem.py;文件工具响应无 $ 前缀天然免疫,Edit 响应里整份 originalFile 文本也不再是噪声源)。四张卡正则已全部改锚定式,crud-gotchas 从「输出含 --force/relation 就弹」改为「正在跑 mem.py 写命令才弹」。5 条区分路径实测全对,eval 27→28(当日真实误触发转负向金标准)。**残余小缝**:读「正文同时含命令特征+输出特征」的文档(如 read stale 卡自身正文)仍可误触发,每会话账本兜底,不再追。
- **接线当日首条真实测量(2026-07-03 18:06)**:并发会话跑 `package_review_snapshot.py` 时影子记到 `relay-review-clipboard-staging` would_inject——「prompt 没注、动作时刻该注」的活标本第一次被量到;同期 risk_gate 决策日志零误拦。
- **同日晚 owner 裁决:高危类去人工审核框,改「默认阻止 + 限时重发确认」**。起因=窄门首拦真实案例(并发会话删 mixflow 残留目录)弹了人工 Yes/No 框,owner 裁:审核压力不该压到人身上——第一次一律 deny + 把自查问题抛回发起方(「你确定这不是别的会话的产物吗?」),同一会话 **120s 内原样重发同一命令 = 确认,放行**(逃生门模式同 es_reminder hook)。实现=pending 令牌(sha256(session|shape|规整命令),`logs/risk_gate_pending/<session>.json`,过期即清);绝对 deny(git add -A/commit -a)仍无任何放行通道;ZMEM_PROOF/ALLOW_RISK_GATE 直接放行不变;冻结工件只认重发确认(ritual 须有意识)。18 条决策矩阵实测全过(首发阻止/重发放行/跨会话不共享/过期不放行/绝对 deny 重发仍拒)。
- **接线状态**:hook 脚本在库里 ≠ 已生效;实际注册在 `.claude/settings.local.json`(不入 git),主 checkout 接线与本批同日完成,核对以 settings 为准。

## 4. 未解 / 待澄清(诚实标注)

- **冻结时机:三处口径打架——【已于 2026-06-30 裁定收口,本条转史料】**三层互补共存、整库迁移非目标、冻结=按条 archive-on-promotion(`memory-three-layer-coexistence-decided` 卡,三处文档口径已对齐);以下为裁定前的原始记录。`MASTER_PLAN` 写"旧 cc_memory **上线即冻只读**绝不双活";`council_B` 写"memory.db 当 legacy 读真相、**迁移延后无时间表**";`CLAUDE.md` 又仍称 cc_memory 为 "authoritative collaboration memory"(=活)。**而实际操作仍在写旧库**(本会话 + 分支线程都写过)。可行的**按条解读**(防漂移):某条知识做成卡后,别再更新它旧库副本——但这≠整库已冻。"整库迁移成只读"是 V2 里程碑、未到、且上面三处得先对齐。(`entry:v-next` 里"冻只读不动"的措辞偏笼统,待校准。)
- claim_guards 是关键词子串匹配,金标准外的改写措辞可能漏(泛化属 V2 dense)。
- 残留话题邻近 flood(共享关键词的卡偶尔同现)未全清。
- **捕获≠召回(2026-06-28 元层血泪,被动悖论咬到系统自己)**:本会话开了两场六代理大会重推「召回触发(③)」「老系统整合(①)」,而那套"判官/看守"结论 + 分档门槛(Action Recall@L1≥80% 等)+ 冻结/迁移路线,**早就写在本档 §5 + `design/council_B` + `MASTER_PLAN`**。为什么还重推:① 24115 那次压缩的【摘要有损】,把整个 V2 路线图/判官/遥测洞见摘没了,只留 precompact-B;② 写下来的那几份在 `HISTORY`/`design` = **"拉"层、无人推**,我开 ③ 时没被推到;③ 那次的记忆更新回合 + 判官回合**没失职**(判官 GAP=0 是对的——确实没"漏记")——**因为这是召回缺口、不是捕获缺口**。教训:记忆更新回合 + 判官修的是捕获,修不了召回;"重推已记过的"只有 ③ 那个"读输出 cross-check 全量记忆"的看守逮得住。**已止血**:把 `vnext-self-history` 卡触发拓宽到"设计/重推记忆系统功能"那一刻(原只在"问历史"时弹)+ 加金标准 frame,让"先读 HISTORY/design"进【推】通道(否则只写本档 = 重蹈这条覆辙)。

## 5. 路线 / 待做未做(全凭指标解锁)

- **近(纯离线、随时推)**:持续把新踩的坑补进金标准(自喂养);卡 17→更多;扩金标准;三硬类保持 100%。
- **MVP-1a:已落地(2026-07-03)** — `pre_tool_risk_gate.py` 高危 deny/ask + ZMEM_PROOF 解锁(详 §3「2026-07-03 衍生操作召回批」)。
- **判官层(V2 测量)**:小模型/廉价 API 读 transcript,经**遥测预筛**只看可疑切片 → 抓漏召回/纠正 → **起草** frame/卡(过 verify/eval 闸 + 抽检才落,绝不自动改卡)。遥测=它的省钱阀门。
- **V2(凭指标)**:dense 语义召回;necessity-LLM(只产建议);行为日志 + 在线权重校准(明文 git 可回退);生命周期温度;~~存储真相源整库迁移~~(**2026-06-30 已裁定非目标**——三层互补共存,只做按条 archive-on-promotion;原 council_B 口径"第二档达标后再评估"作废)。
- **⭐ ③ 召回触发的【真地基】= 可观测提交点记忆闸(Observable-Commitment Gate,2026-06-28)**:owner 拿本会话 ③ 讨论喂 ChatGPT 后的 reframe,**取代/修正 ③ 的 framing**——真问题不是"自动推卡"(③ 的看守=push),是"**逼模型在提交点真去查**"(带门的 pull):`zmem search` 吐 `ZMEM_PROOF` token,PreToolUse/Stop 闸**查 transcript 有没有 proof**、没 proof 不准把想法变成动作/结论;`skip` 须显式留痕。地基层 = 每张卡声明 `observable_from`、`verify --coverage` 强制(没可观测触发面的卡不准算自动召回保证)。三目标别混:(a)念头那刻=无解,(b)没查不准提交=提交点闸=近期键石,(c)中途多查=改 agent loop=未来。**详 `design/observable-commitment-gate-20260628.md`(+ 源 `design/chatgpt-...source-20260628.md`)。** 它治"读了没连上"(逼判断那刻重查、记忆落当下)。③ 的看守降为第四档。**(2026-07-03 进展:`zmem search` + `ZMEM_PROOF` + PreToolUse proof 检查已落第一版;Stop 输出闸、skip 显式留痕、observable_from 契约/coverage 仍未做。)**
- **解锁关口**:MVP-0 三硬类 StrictHitRate 100%(含纯脚本基线)**已达成**;各 V2 件仍按各自指标门槛逐项推进。

## 6. 东西都在哪

- 本档案 = 唯一连贯入口;一手设计语料 = `cc_memory_vnext/design/`(8 份,143KB)。
- 系统本体 = `cc_memory_vnext/`(`zmem.py` / `cards/` / `eval/` / `hooks/` / `README.md`)。
- 项目状态记忆:本档 §3 即权威现状。~~cc_memory `entry:v-next`~~ = **死指针**(2026-07-03 实查 main 权威库 `unknown node`、exports 全文零命中——该条目从未建成或没进 main;别再引用)。
- 跨项目 route-time 规则 = harness `MEMORY.md` + 各 `*.md`。
- v-next 已入 git = 随 clone 存活、git 即 checkpoint;owner 早先"单独打 `.7z` 快照"的偏好是它**还未入库**时的过渡做法(入库后 git 已 cover)。

---
*本档案经独立 codex critic 跨模型核对(2026-06-27):订正 MVP-0 计数、GPU 选型实况(Harrier+Qwen3-Reranker)、冻结口径三方矛盾、补旧库搜索硬坑/软边失败/遥测边界。*
