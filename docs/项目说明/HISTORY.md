# ZMD 文档与项目历史索引

> 本页为 append-only 编年史，只追加已发生事件和历史坐标。它不追随当前状态重写，也不替代 claim validity、owner decision 或原始研究证据。

## 2026-08-12：旧手册职责收束

- 将混合现状、方法、排期与编年史的 `00_master_roadmap.md` 冻结为字节保真快照，并建立未来-only [ROADMAP](ROADMAP.md)、append-only HISTORY 与独立 [REASONING_METHOD](REASONING_METHOD.md)。
- 将手写开放问题页替换为 [OPEN_QUESTIONS](../OPEN_QUESTIONS.md) 的兼容入口。
- 将手写 glossary 替换为 [TERMINOLOGY](../TERMINOLOGY.md) 的兼容入口。
- 将带旧阶段现态的 GO criteria 改写为无时态判读契约，原文保留为历史快照。
- 当前职责由有效 policy 自动生成到 [GUIDANCE_INDEX](../GUIDANCE_INDEX.md)，历史材料不再因目录位置被默认为 living。

冻结快照：

| 原路径 | 历史快照 | SHA-256 |
|---|---|---|
| `docs/项目说明/00_master_roadmap.md` | [00_master_roadmap_pre_phase3_20260812.md](../history/status/00_master_roadmap_pre_phase3_20260812.md) | `68d7807f8eedc84edce4f693b12c07d6a58f0f69eae02091be3e667e0e0689ab` |
| `docs/项目说明/05_open_questions.md` | [05_open_questions_pre_phase3_20260812.md](../history/status/05_open_questions_pre_phase3_20260812.md) | `1031dfa3f264c6e3eb45cf71d828cd316c6168cf616806f1aea8d8bdc20e9cd2` |
| `docs/项目说明/12_go_criteria.md` | [12_go_criteria_pre_phase3_20260812.md](../history/status/12_go_criteria_pre_phase3_20260812.md) | `ae4de46646d5ed02301b8a856339f2b22cbc8c2bb037bf210b99b0b5fbad5115` |
| `docs/项目说明/21_glossary.md` | [21_glossary_pre_phase3_20260812.md](../history/status/21_glossary_pre_phase3_20260812.md) | `76af80247b3c4631d9265340a5d5eb1583a47e8a97571f59d4bd0dba50d4822e` |

## 更早历史的入口

- 项目主线人话编年史：[22_project_journey_plain_language.md](22_project_journey_plain_language.md)
- 被替换入口的快照总目录：[../history/README.md](../history/README.md)
- 研究、外审和实验包：[../CATALOG.md](../CATALOG.md)
- 反例、语义替代、修复与重验：[../VALIDITY_LEDGER.md](../VALIDITY_LEDGER.md)
- Git 级变更历史：仓库 `git log` / `git blame`

## 2026-08-13:owner 三笔口头拍板

原始登记文本见下节落地归档的 `00_master_roadmap.md` 文末;此处为编年史事件,机器登记在 `data/knowledge/decisions.jsonl`(显式非权威 append-only)。

- **`rule_system_redesign_20260807` 线允许立项**(口头拍板,主线程当日登记;入批口径未指定,`OWNER_DECISION_SUMMARY.md` 八项送审决定未逐项裁定、仍逐项上桌)→ `DECISION-RULE-SYSTEM-REDESIGN-OPEN-20260813`。
- **文档补丁链两接口点联合结论四条通过**(三面评估线 × 文档评审线双线收敛、双方过目后呈批):`decisions.jsonl` 显式非权威 append-only(non_authorizing 声明+指针必填+checker 校验指针真源+预留 ruling_event_id,档案面落地后翻转 GENERATED_PROJECTION 或退役);claims authority 准入=「knowledge checker 能且确实对当前树 tracked 机器真源核验承重字段」+ authority_basis 必填,历史执行收据封顶 research_authority,3 条超标条目降级;表示标签字段名 representation_class(四类值,与 authority 正交,与 document_class 建映射),enum 扩类权留 redesign 档案面批;四条全并进落地适配批不单开 → `DECISION-LEDGER-AUTHORITY-INTERFACES-20260813`。
- **semantics 拆分「先实验后拍板」路线认可**:先落传递依赖根、实测一个 canonical 批的成本,再由 owner 决定拆/不拆/整文件 SHA 进依赖根;实验属已立项 redesign 线批 C 范围 → `DECISION-SEMANTICS-SPLIT-EXPERIMENT-FIRST-20260813`。

三笔均为绿灯≠关门,不产生任何 release closure。

## 2026-08-15:全量文档系统落地与落地时漂移迁移

- 16 批正式补丁(phase1 → phase4 batch5)以合并包经 landing planner(状态 READY,动态漂移恰 3 个)落地于分支 `document-system-consolidated-landing`,base commit `31b4ce4`(230 路径)。
- 漂移源的落地时字节保真归档:

| 原路径 | 落地归档(仓库根相对) | SHA-256 |
|---|---|---|
| `CLAUDE.md` | [`docs/history/status/landing/2026-08-15/document-system-consolidated-landing/CLAUDE.md`](../history/status/landing/2026-08-15/document-system-consolidated-landing/CLAUDE.md) | `0d3888e5c7a293abe9b5058d874f5fbe8739a052183b3d7ef10667fa6df69474` |
| `docs/项目说明/00_master_roadmap.md` | [`docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md`](../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md) | `38a5a752342d96e29542f466f3099a9668d4a6b60b04c792265cb539e04f8415` |
| `docs/项目说明/27_status_dashboard.md` | [`docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/27_status_dashboard.md`](../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/27_status_dashboard.md) | `2f6df966769372a7f412cbf2ba14ccb2c1f6caae841b1f5366d7d0691d5cce40` |

- 语义迁移:roadmap 文末 owner 拍板 → 上节与 `data/knowledge/decisions.jsonl`;仪表盘 §9 挂账 A10–A14 五行 → [ROADMAP.md](ROADMAP.md) 登记欠账节;`CLAUDE.md` 按 workspace overlay 保留在场版本;耐久操作知识吸收进 [AGENT_OPERATIONS](../AGENT_OPERATIONS.md)。
