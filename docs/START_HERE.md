# 从问题出发阅读 ZMD

这个页面是一张稳定路标，刻意不写会变化的 gate 值、研究上下界、hash、测试数量或开关状态。需要“现在是什么”时只看 [CURRENT](CURRENT.md)；只看尚未关闭的稳定命题时进入 [OPEN_QUESTIONS](OPEN_QUESTIONS.md)；需要知道某条结论从哪里来时查 [CATALOG](CATALOG.md)；需要按推理类型、数学依赖、选择/验证/消费机制或历史回填覆盖查询时看 [REASONING_LEDGER](REASONING_LEDGER.md)；需要判断旧结论为何失效、由谁替代、修复是否重验以及还能怎样复用时看 [VALIDITY_LEDGER](VALIDITY_LEDGER.md)；需要区分哪些 dossier 真正做过语义审阅、哪些只核对了可用性、哪些仍在长尾分诊时看 [BACKFILL_LEDGER](BACKFILL_LEDGER.md)；按主题或规范术语进入时分别看 [TOPIC_INDEX](TOPIC_INDEX.md) 与 [TERMINOLOGY](TERMINOLOGY.md)；需要按稳定分区和局部前门进入时看 [SECTION_INDEX](SECTION_INDEX.md)；需要枚举当前仍承担维护职责的文档时看 [GUIDANCE_INDEX](GUIDANCE_INDEX.md)。

## 第一次进入仓库

先读 [CURRENT](CURRENT.md)，再读 [PROJECT_LOCK](../PROJECT_LOCK.md)。前者把当前机器状态与已登记结论汇总到一起，后者界定 certified exactness、命题 P、发布链和禁止改动。每次任务的耐久操作边界在 [AGENT_OPERATIONS](AGENT_OPERATIONS.md)；根 `CLAUDE.md` / `AGENTS.md` 只是在本机存在时提供的可选 workspace overlay，代码地图在 [NAV_MAP.md](../NAV_MAP.md)。

## 我正在找什么

| 问题 | 入口 |
|---|---|
| 当前 gate、proof obligations、canonical 语义和 durable exact 结果 | [CURRENT](CURRENT.md) |
| 当前六谓词研究账本、P2.0 独立账本、cut attach 边界 | [CURRENT](CURRENT.md) |
| 当前哪些稳定命题仍开放，它们不推出什么 | [OPEN_QUESTIONS](OPEN_QUESTIONS.md) |
| 某条不等式、负结果或研究方法的稳定 ID、前提、后果与证据 | [CATALOG](CATALOG.md) |
| 哪些结果属于预建模排除、候选筛选、条件式边界、反例或实验 cut；候选怎样发现、验证和消费；哪些 dossier 已完成语义回填 | [REASONING_LEDGER](REASONING_LEDGER.md) |
| 某条旧结论是被直接反驳、语义替代、实现/实验失效还是归因更正；successor 在哪里；是否已经重验；旧证据还能怎样引用 | [VALIDITY_LEDGER](VALIDITY_LEDGER.md) |
| 哪些 dossier 已做 semantic review、哪些只有 availability/provenance 核对、哪些仍是 inventory triage | [BACKFILL_LEDGER](BACKFILL_LEDGER.md) |
| 按稳定数学、求解、语义或治理主题浏览 claim、术语与开放问题 | [TOPIC_INDEX](TOPIC_INDEX.md) |
| canonical label、历史别名、概念区别和来源 | [TERMINOLOGY](TERMINOLOGY.md) |
| certified 到底证明什么、不证明什么 | [PROJECT_LOCK](../PROJECT_LOCK.md)、[项目概览](项目说明/01_overview.md)、[问题陈述](../specs/01_problem_statement.md) |
| 空矩形、网格、目标和 admissibility 的 canonical 定义 | [canonical rules](../rules/canonical_rules.json)、[规则手册](项目说明/26_rules_handbook.md) |
| 当前 owner phase gate 与机器义务 | [phase gate](../data/review_gates/phase_1_2_spike_close.json)、[proof obligations](../data/proof_obligations/p1_2_proof_obligations.json) |
| 如何运行、测试、reseal 或发布 | [AGENT_OPERATIONS](AGENT_OPERATIONS.md)、[测试工作流](项目说明/15_workflow_testing.md)、[坑册与 SOP](项目说明/28_pitfalls_and_sop.md) |
| 代码模块在哪里 | [NAV_MAP.md](../NAV_MAP.md) |
| 原始研究、外审和实验包在哪里 | [research 档案说明](research/README.md)、[CATALOG](CATALOG.md) |
| 接下来做什么、依赖什么、用什么证据退出 | [ROADMAP](项目说明/ROADMAP.md) |
| 项目的带日期编年史与旧迁移坐标 | [HISTORY](项目说明/HISTORY.md)、[历史快照总目录](history/README.md) |
| 科学推理、归属判据与管线设计方法 | [REASONING_METHOD](项目说明/REASONING_METHOD.md) |
| 文档层有哪些稳定分区、每个分区的局部前门和当前成员是什么 | [SECTION_INDEX](SECTION_INDEX.md) |
| 当前哪些文档仍承担 living、normative、generated 或 framework 职责 | [GUIDANCE_INDEX](GUIDANCE_INDEX.md) |
| 当前有哪些周期维护触发器、逾期项和 phase-close 待处置表面 | [MAINTENANCE_QUEUE](MAINTENANCE_QUEUE.md) |
| 旧入口和主题投影当时写了什么 | [历史快照总目录](history/README.md) |
| agent 应怎样修改某个文档，或怎样改变文档框架本身 | 先运行 `docctl context`；完整设计见 [文档系统架构](governance/document-system/ARCHITECTURE.md) 与 [维护指南](governance/document-system/MAINTAINING.md) |
| 阶段性重构完成后怎样日常维护、何时才重新开启框架 | [文档系统常态维护合同](governance/document-system/STEADY_STATE.md) |

## 读研究材料时的三个检查

先找 claim ID，再看它的 `status`、`scope` 和 `authority_effect`。随后核对 `premises` 与 `does_not_imply`，最后才下钻 evidence。推理分类见 `reasoning_profile`，数学组合见 `derivation_profile`，候选来源、选择、验证、完备性与消费落点见 `separation_profile`，历史失效、换代、复用与重验边界见 `validity_profile`，但这些分类都不替代命题本身。尤其是 `experimental_only` 只表示存在相关实验观察，不等于已有“通用传播不可能完成分离”的正式证明。一个 paper proof、一次 solver PASS、一个本地 artifact 或一个 dated README 都不会仅凭存在就自动更新 production、owner gate 或研究总账。

[`.artifacts/` 证据根](../.artifacts/README.md) 的具体 payload 可以在轻量 checkout 中缺席；这不等于 claim 消失，但依赖本地工件的细节无法在该 checkout 独立复验。tracked 研究入口应能从 [CATALOG](CATALOG.md) 找到。

## 维护文档与知识层

任何文档操作先让路径解析出最小操作卡：

```bash
.venv/bin/python devtools/docctl.py context <path> --intent <edit|create|move|delete>
```

新增 `docs/research/` 一级包或本机 `.artifacts/` 一级包后，先刷新 dossier registry。完成一次 dossier 语义审阅时，同时写入 backfill review，并从 triage 中原子移除该 dossier；未审材料只进入 triage，不能冒充 semantic review。新增会被重复引用的结论、决定、主题或术语时，先写入结构化账本，再生成页面。以下命令从仓库根目录运行：

```bash
.venv/bin/python devtools/build_knowledge_docs.py --refresh-dossiers --write
.venv/bin/python devtools/check_knowledge_docs.py
.venv/bin/python devtools/docctl.py check --changed
.venv/bin/python devtools/docctl.py audit --profile weekly
```

知识 checker 会阻断 schema 错误、悬空 ID、循环依赖、证据路径错误、未登记 research 包和知识生成页漂移；`docctl doctor` 负责前门、兼容跳转、policy 与职责投影；`docctl audit` 只读发现长期欠账，并把修复送回同一写入管道。它们都不替代数学审查、owner decision、preflight 或 production certification。


认证、phase gate 与发布边界统一从 [CERTIFICATION](CERTIFICATION.md) 进入。
