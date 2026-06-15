---
name: memtree-restructure
index_summary: "记忆树工作 2026-06-16 大转向(GPT 外审 6a303556 点破): owner 真意图是 fact-entry 依赖图(改 fact 只反查依赖它的 entry 重写、不全扫),我/团队却做成 harvest-only「Markdown 治理」(同步/gate/索引)=做偏了、错的层; 真下一步=typed-graph MVP(frontmatter depends_on+edges.jsonl+impact query); 会话全文 inspect_6a303556/conversation_full.md; 全部未提交"
description: "记忆树重构(2026-06-15 起)。**2026-06-16 GPT Pro 外审(会话 6a303556)点破做偏了**: owner 第 1 轮原始意图是 fact-entry 依赖图记忆系统 —— 条目↔事实多对多,改一个 fact 系统只反查 DEPENDS_ON 它的 entry 去重写,不全库扫/不靠人 grep。我和团队却把任务框成「同步/投影」,做出 harvest-only 四层 + 一堆 gate/sync/索引生成 = 一个「Markdown 记忆树治理系统」,解决的是发布/同步/门禁、不是依赖传播,是错误的层(GPT:先别再堆同步脚本了)。根因=没回到 owner 真意图就开干。真正该做的=GPT 给的 typed-graph:事实当一等对象(版本+时效+状态)+ 带类型依赖边(DEPENDS_ON 硬线触发更新 vs RELATED_TO 软线只召回)+ change-txn + impact query;MVP 不用数据库:frontmatter depends_on/related_to → edges.jsonl → 图检查 → impact query。会话全文存 补丁包/gpt_deliveries/inspect_6a303556/conversation_full.md。下一步方向待 owner 拍板。全部未提交。"
metadata:
  node_type: memory
  type: project
---

# 记忆树工作 — 2026-06-16 大转向

## ⚠️ 重大转向(2026-06-16, GPT 外审点破): 做偏了
**owner 原始意图**(会话 `6a303556` 第 1 轮): 一个 **fact-entry 依赖图记忆系统** —— 条目和事实多对多,改一个事实,系统**只反查依赖它的条目去重写**,不全库扫、不靠人记得 grep。

**我/团队实际做的**(2C+2codex 讨论 + harvest-only + 这一晚的 gate/sync/索引生成): 一个 **「Markdown 记忆树治理系统」** —— 多副本同步、MEMORY.md 不超 24KB、索引生成、wikilink 不断、repo↔harness 对账。**= 错误的层**(发布/同步/门禁,不是依赖传播)。GPT 原话:「先别再往这个方向堆同步脚本了。」

**根因**: 团队一开始把任务框成「怎么重构记忆树(同步/投影)」就开干,**没回到 owner 第 1 轮那个真意图**(fact 依赖传播)。又一次 [[root-cause-over-symptom]] / [[fact-understand-before-output]]。

**GPT 给的正确架构**(全文存 `补丁包/gpt_deliveries/inspect_6a303556/conversation_full.md`,gitignored 本地): 五层 = 原始事件 / 实体 / **事实(槽位+版本+状态 active/superseded/disputed+时效+来源+置信度)** / 条目(给 agent 读的视图) / **带类型依赖边**。边分硬软: `DEPENDS_ON`/`DERIVED_FROM` 硬线(事实变→沿边找受影响条目重写)、`RELATED_TO` 软线(只召回不传播)、`SUPERSEDES`/`CONTRADICTS`/`SAME_AS`。写入走 change-txn(agent 只提 change proposal,死板 validator 盖章,不直接改正文)。已有最接近的=Graphiti/Zep temporal KG + 老 AI 的 truth-maintenance + DB 的 provenance / incremental-view-maintenance。一句话:**事实是骨架,条目是皮肤,事件是出生证明,依赖边是神经。**

**MVP(不用上数据库, 叠在现有 Markdown 上)**: frontmatter 显式 `depends_on`/`related_to`(不从正文 wikilink 猜)→ 生成 `edges.jsonl` → 图检查 → impact query(改 fact 反查依赖它的 entry)→ change-proposal 列受影响条目。通了才从「记忆目录管理器」变「活的记忆系统」。

**下一步方向待 owner 拍板**(直接搭 MVP / 先写计划再外审 / 别的走法)。

## 已建的「Markdown 治理层」(= 上面说的错的层, 留作历史)
harvest-only 四层(L1 live harness=写入口 / L2 repo harvest 账本永不自动反写 harness / L3 cc_context/memory+_cc_live / L4 MEMORY.md 从 index_summary 生成)。repo 侧 P0-P3 落地 5 工具(memory_harvest / sync_knowledge 总闸 / gen_memory_index / check_description_freshness / seed_index_summary),方案 A=把手写摘要回种 index_summary 当单源。完整讨论+落地见 `cc_context/review/memtree_landing_review_20260615.md`。**全部未提交。**

## 真 bug(GPT 验证过 + 我已独立复核为真; 若保留 Markdown 层要修)
- `check_description_freshness` 两个洞: ① 新节点 rc 仍 0(不阻断); ② 更深=一次 body+summary 同改后基线没更新,之后 body-only 改会拿当前 hash 比**最老** baseline(idx/desc 也都不同)→ 永不报=一次性门锁。正解: `body_sha != baseline` 一律 DIRTY(除非显式 accept),别用「idx 是否也变过」判断。
- `gen_memory_index` 默认模式仍 fail-soft(缺 index_summary 照写截断 description 旁路 + rc 0);`--check/--apply` 已修。
- `sync_memory_to_harness --apply` 还能写 live harness,与 harvest-only 文档自相矛盾(要么封存、要么改名 deploy_harness_cache 加 CAS 规则)。
- harness 路径 4-5 处硬编码 →「检查的不是同一棵树 / Linux 上优雅 skip」; 该建唯一 resolver(显式 override → 最近 jsonl 验 cwd → .claude.json → 弱 fallback)。
- `handoff_windows_ninth_review_pending.md` ~220KB = living 黑洞,该拆成 fact 槽位 + 生成视图。
- #1「验证修复」交付给了 patch(`zmd_memtree_repair_audit_patch_0fcea`),**未 apply**(GPT patch 有前科:上轮 benders 补丁误拒合法 type-1 被否)。

## 本会话工具变更(未提交)
- `dispatch_gpt_task.py` 加 `--message-attach`: sources 通道下额外把文件附到聊天消息(复用 upload_files,3 处增量改)。聊天框=md 附件 + 提示词(= round-2 模式,owner「附件记得带上、跟上次一样」)。
- `dump_conversation.py`(新): 复用后端 JSON 直读(`_BACKEND_CONV_JS`)导出**整条**会话全部消息(非只最后一条 `collect`);`inspect_conv.py` 已坏(依赖被移除的 SEL 字典)。

相关: [[zmd-project-entry]] [[memory-currency-protocol]] [[project-knowledge-tree-architecture]] [[root-cause-over-symptom]] [[fact-understand-before-output]] [[minimal-open-prompts]]
