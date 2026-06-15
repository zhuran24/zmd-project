---
name: memtree-restructure
index_summary: "记忆树重构(2026-06-15起,进行中): harvest-only 四层模型; repo 侧 P0-P3 已落地(5 工具+index_summary 单源+lockfile/freshness 双 gate); harness 侧 recall 待做; 未提交; 详见 cc_context/review/memtree_landing_review_20260615.md"
description: "记忆树重构(2026-06-15 起, owner 发起, 进行中): 旧痛点=读写分家(AI 召回读 harness、owner 维护 repo cc_context/memory, 单向手动 sync 漏跑 AI 就读不到)+ MEMORY.md 24KB 红线 + 同步无总闸 + 失效链全 fail-soft + 现状值无强制函数。2C+2codex 团队讨论 + GPT Pro 外审收敛到 **harvest-only 四层模型**, repo 侧 P0-P3 已落地但**全部未提交**, harness 侧(recall 真受益那半)待做。新增 5 工具在 cc_context/tools/。完整讨论+落地审计见 cc_context/review/memtree_landing_review_20260615.md。"
metadata:
  node_type: memory
  type: project
---

# 记忆树重构 — harvest-only(2026-06-15 起, 进行中)

## 起因 / 痛点
一棵逻辑树多物理投影。**读写分家**最核心: AI auto-memory 召回真正读 harness 树(`~/.claude/projects/<slug>/memory/`, 按节点 frontmatter `description` 语义注入、不读 wikilink、MEMORY.md ~24576B 上限), owner 维护 repo `cc_context/memory/`(+ `_cc_live_memory/` 字节镜像), 单向手动 `sync_memory_to_harness.py` 漏跑→AI 读不到。另: MEMORY.md 顶 24KB 红线、同步工具碎片化无总闸、失效链全 fail-soft、现状值无强制函数。

## 收敛模型 = harvest-only 四层(团队 + GPT Pro 外审)
- **L1 live harness** = 运行时工作副本 + AI 写入口(它有原生写入, 是并列写入源不是部署目标)。
- **L2 repo harvest ledger** = 可审计账本(CI 可见)。**铁律: repo 永不自动反写 active harness**(harvest-only) —— 红队证明对一个别进程正读写的目录自动写=天生 race, 红队不出来, 只能 harvest(只读 live→repo)。
- **L3 curated memory** = cc_context/memory + _cc_live(发布/索引/长期整理)。
- **L4 generated index** = MEMORY.md 从单源生成。
落地顺序: P0 冻结观测 → P1 无副作用总闸 → P2 harvest → P3 generated MEMORY → P4 schema/命名。

## owner 三裁决(已确认)
① 写入入口收敛(常态 harness/会话, 冲突检测兜底)② MEMORY.md 自动生成(渐进, owner 看 diff 再切)③ 采纳 harvest-only。**scope=极简**(effort-matches-stakes: 个人 KB 不上搜索引擎级 5 字段系统; 树涨大/预算长期溢出/recall-miss 反复才升级)。

## 已落地(repo 侧, 5 个新工具, 全绿但未提交)
`cc_context/tools/`:
- `memory_harvest.py` —— P0 对账(按 name 比 repo↔harness, **语义** body+desc hash 抓同名 drift, 区分有意 stub)+ P2 `--harvest`(只读收割 live→repo ledger `cc_context/harness_memory_harvest/{new,updates,quarantine}`, **实证不写 harness**)。
- `sync_knowledge.py --check` —— P1 单入口总闸, 串 9 检查, 两级 BLOCK/warn, 不写任何文件。
- `gen_memory_index.py` —— P3: 从节点 `index_summary` 生成 MEMORY.md(`--check`=lockfile gate, `--apply`=写正本+_cc_live 镜像); 硬 24KB cap 不静默裁。**边界(GPT 指出)**: 只重写摘要、不重建标题/结构(取自现有 MEMORY.md 模板)→ 改标题不被抓, 是"摘要刷新器"非完整 lockfile。
- `check_description_freshness.py` —— body-sha gate: 节点正文变了但 index_summary/description 没跟上→报红(基线 `cc_context/knowledge/description_review.json`)。
- `seed_index_summary.py` —— 一次性回种(已跑)。

**方案 A(P3 实际做法)**: 实测"截断 description 当索引行"质量倒退(丢 actionable 尾巴+加冗余前缀), 改为**把现有好的手写摘要回种进各节点 frontmatter `index_summary` 当单一来源**, gen 从它生成 MEMORY.md(零质量损失, 逐字节==现状)+ lockfile/freshness 两 gate 设 **BLOCK**(repo P3)。

## GPT 审计落地(2026-06-16, 已收回)
框架符合; 3 偏离已修: ①钦点 stale 样本 zmd-round2 没真修(我把 stale 摘要原样种进 index_summary+--seed 接受为基线)→已对齐(另一会话也同步更新了该节点)②两 gate 降 warn→改 BLOCK ③gen 非真 lockfile+静默回退→加 validate 硬失败+文档改正。审计原文+讨论全程在 `cc_context/review/memtree_landing_review_20260615.md`。

## 待办(下阶段)
- **harness 侧 A**(recall 真受益的另一半): 传 index_summary 到 harness 节点 + harness MEMORY.md 也从 index_summary 单源生成(要处理 harness 153 节点 24KB 预算 + 双通道: MEMORY.md=无条件注入小集 / 每节点 description=按 query 召回)。**当前只做了 repo 侧, recall 侧未解。**
- P1/P2 风险项: check_description_freshness 新节点不 fail、memory_harvest 同名静默覆盖、slug resolver 4 处硬编码不统一、gen 完整 lockfile(skeleton-hash)。
- **全部未提交**(owner 说先不提交)。当前 repo 节点有 index_summary、harness 没有 → check_memory_tree 报 71 投影+32 共维护 drift warn(半迁移态预期, 非问题)。

## 关键教训
- 截断完整 description 当通道① 索引行 = 质量倒退(description 为通道② 召回写、长+带分类前缀)→ 索引行需专门精炼短文本(=index_summary 单源, 不是第三副本)。
- gate 接进总闸但设 warn = 复刻原问题(工具 exit 1 被吃成 WARN), repo P3 gate 必须 BLOCK。
- 并发会话碰撞活在同一节点(zmd-round2): 两会话同时编辑, block gate 正确拦下; 确认对方停了再干净收尾(见 concurrent-claude-sessions-repo-collision 记忆)。

相关: [[zmd-project-entry]] [[memory-currency-protocol]] [[project-knowledge-tree-architecture]]
