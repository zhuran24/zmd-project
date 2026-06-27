# 记忆系统档案 — 来历 / 现状 / 路线 / 未解

> 这份档案存在的理由很反讽:这套主动记忆系统,本来记不住自己的故事。背景、重写过程、关键裁决、待做未做,过去只散在易丢的 download 文档 + 各次对话里。本文是**单一连贯入口**;一手设计语料在同目录 `design/`(已随仓库存活)。
> 最后更新:2026-06-27。

## 0. 一句话

记忆从「一条条存、靠人/Agent 自己 grep 关联」一路演进到「SQLite 单一真相 + 系统主动发现关系 + GPU 语义」,但仍卡在**被动数据库悖论**(得先知道有记忆才会查);v-next 把它改成「每回合 hook 确定性编译注入的**主动卡片系统**」。现状 = v-next MVP-0 上线,旧 cc_memory 仍是现役主力(未真冻)。

## 1. 完整演进链(背景 = 重写前)

> 一手详情:`design/evolution_summary_20260626.md`(slim/关系发现/GPU 那几章) + `design/proposal_A_*` `design/proposal_B_*`(v-next 两提案) + `design/council_*`(两议会)。

- **第0章 旧多树 Markdown 记忆**:`cc_context/memory/` + `_cc_live_memory/` + harness 快照/harvest 等**多棵树**。问题:fact 只是概念标签(无 subject/predicate/value/status/version)、`[[wikilink]]` 不是 typed edge(无法安全做影响面传播)、多副本同步、freshness gate 有"第二次 stale edit"逻辑洞、generator 不是完整 lockfile、repo→live harness 写入路径危险、缺事件层/变更事务层(答不了"为什么改/谁改/影响谁/能否回滚")。
- **第1章 typed-graph overlay(v2/v3/v4)**:在旧系统旁加 `memory_graph/`、typed edge、impact、bootstrap、freshness gate。**失败教训**:这不是重构,是给旧系统加外骨骼 → 变成**第三棵树**。owner 点破:"图不该是另一棵树,图应该就是记忆系统本身。"
- **第2章 slim rewrite → 单一真相 `cc_memory/memory.db`**:一个真相源 + 一个 CLI(`mem.py`)+ 少量可重建视图(`exports/MEMORY.md`)+ 旧系统归档。表:meta/events/facts/entries/edges/aliases/changes。**= 今天的 cc_memory 雏形。**
- **第3章 关系发现 + 本地计算 + GPU**:根问题"新增条目谁来找相关项?不能靠使用者能力" → `relation_suggestions`(系统产候选边、人审、高分未审则 `check` 失败)。先做**零新增依赖**版(FTS5 BM25 + token 重叠 + 中文 ngram + 一跳图扩展),再上 **GPU 语义**(嵌入 harrier/bge-m3 + Qwen3-Reranker;GPU 只作可选检索后端,不做第四棵树)。沉淀原则:单一真相 / Markdown 是视图非源 / 图不是另一棵树 / 系统帮发现关系 / 候选≠真相 / check 阻断未审 / GPU 只增强 / 加依赖前先确认。
- **第4章 被动数据库悖论 → v-next(本会话)**:即便有了语义检索,仍犯**根病**——route-time 反射判断的当口不会主动 `search`,于是零召回(实证:owner 反复纠正同几件事记多次没用)。两个独立 8 人跨模型议会各自收敛到同一架构 → v-next:**每回合 hook 确定性编译注入的主动卡片系统**。

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
| **旧 cc_memory**(SQLite,~106 条) | 现役主力协作库,`mem.py` 驱动 | **仍活,未真冻**(v-next 只覆盖一小切片) |
| **新 v-next**(`cc_memory_vnext/`,16 卡) | 主动注入层,叠在旧库之上 | **MVP-0 上线**(见下) |
| **harness 记忆**(`~/.claude/.../memory/*.md`) | 跨项目、本地、不进仓库 | 活(MiMo/precompact 等 route-time 反射规则) |

**MVP-0 已落地实况**(均 push main):16 卡 / 27 金标准回归 / **eval 27/27** / **三硬类 StrictHitRate=100%(纯脚本基线)** / 编译器 flood 收口(L1 准入要 trigger 或 scope>0,codex 跨模型审 CLEAN)/ 2 hook 实时注入(已接 `.claude/settings.local.json`)/ **最小遥测**(`zmem context --log` → `logs/activation_decisions.jsonl`)/ **自喂养纪律 institutionalize**(CLAUDE.md + `vnext-maintenance-discipline` 卡:被纠正/踩坑→补金标准+卡)。判官机制已实证可行(blind 模型四条全中)。

## 4. 未解 / 待澄清(诚实标注)

- **冻结时机的计划矛盾**:`MASTER_PLAN` 写"旧 cc_memory **上线即冻只读**绝不双活";`council_B` 写"memory.db 当 legacy 读真相、**迁移延后无时间表**"。当前操作按后者(旧库仍现役)。**正确解读**:"冻只读/绝不双活"是**按条**的——某条做成卡后别再更新它旧库副本(防漂移);**不是整库冻**。"整库迁移成只读"是 V2 里程碑、未到。(`entry:v-next` 里"冻只读不动"的措辞偏笼统,待校准。)
- claim_guards 是关键词子串匹配,金标准外的改写措辞可能漏(泛化属 V2 dense)。
- 残留话题邻近 flood(共享关键词的卡偶尔同现)未全清。

## 5. 路线 / 待做未做(全凭指标解锁)

- **近(纯离线、随时推)**:持续把新踩的坑补进金标准(自喂养);卡 16→更多;扩金标准;三硬类保持 100%。
- **MVP-1a**:PreToolUse 高危只读阻断(不引日志/LLM)。
- **判官层(V2 测量)**:小模型/廉价 API 读 transcript,经**遥测预筛**只看可疑切片 → 抓漏召回/纠正 → **起草** frame/卡(过 verify/eval 闸 + 抽检才落,绝不自动改卡)。遥测=它的省钱阀门。
- **V2(凭指标)**:dense 语义召回;necessity-LLM(只产建议);行为日志 + 在线权重校准(明文 git 可回退);生命周期温度;**存储真相源整库迁移**(council_B:第二档达标后再评估、不设时间表)。
- **解锁关口**:MVP-0 三硬类 StrictHitRate 100%(含纯脚本基线)**已达成**;各 V2 件仍按各自指标门槛逐项推进。

## 6. 东西都在哪

- 本档案 = 唯一连贯入口;一手设计语料 = `cc_memory_vnext/design/`(8 份,143KB)。
- 系统本体 = `cc_memory_vnext/`(`zmem.py` / `cards/` / `eval/` / `hooks/` / `README.md`)。
- 项目状态记忆 = cc_memory `entry:v-next`。
- 跨项目 route-time 规则 = harness `MEMORY.md` + 各 `*.md`。
