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

## 2026-08-13：owner 三笔拍板

原始登记文本见下节落地归档的 `00_master_roadmap.md` 文末；此处为编年史事件，机器登记在 `data/knowledge/decisions.jsonl`（显式非权威 append-only）。

- **`rule_system_redesign_20260807` 线允许立项**（口头拍板，主线程当日登记；入批口径未指定，`OWNER_DECISION_SUMMARY.md` 八项送审决定未逐项裁定、仍逐项上桌）→ `DECISION-RULE-SYSTEM-REDESIGN-OPEN-20260813`。
- **文档补丁链两接口点联合结论四条通过**（三面防污染架构审计线 × 文档评审线双线收敛、双方过目后呈批）：`decisions.jsonl` 显式非权威 append-only（non_authorizing 声明＋指针必填＋checker 校验指针真源＋预留 ruling_event_id，档案面落地后翻转 GENERATED_PROJECTION 或退役）；claims authority 准入＝「knowledge checker 能且确实对当前树 tracked 机器真源核验承重字段」＋authority_basis 必填，历史执行收据封顶 research_authority，3 条超标条目降级；表示标签字段名 representation_class（四类值，与 authority 正交，与 document_class 建映射），enum 扩类权留 redesign 档案面批；四条全并进已交回 GPT Pro 的落地适配批不单开；操作文本＝交接文档附录（文档评审线持有，`~/下载/zmd_文档补丁链落地评审交接_20260813.md`，owner 点头后并入）→ `DECISION-LEDGER-AUTHORITY-INTERFACES-20260813`。
- **semantics 拆分「先实验后拍板」路线认可**：先落传递依赖根、实测一个 canonical 批的成本，再由 owner 决定拆/不拆/整文件 SHA 进依赖根；实验属已立项 redesign 线批 C 范围 → `DECISION-SEMANTICS-SPLIT-EXPERIMENT-FIRST-20260813`。

三笔均为绿灯≠关门，不产生任何 release closure。

## 2026-08-15：全量文档系统落地与落地时漂移迁移

- 16 批正式补丁（phase1 → phase4 batch5）以合并包经 landing planner（状态 READY，动态漂移恰 3 个）落地于分支 `document-system-consolidated-landing`，base commit `31b4ce4`（230 路径）。
- 漂移源的落地时字节保真归档：

| 原路径 | 落地归档（仓库根相对） | SHA-256 |
|---|---|---|
| `CLAUDE.md` | [`docs/history/status/landing/2026-08-15/document-system-consolidated-landing/CLAUDE.md`](../history/status/landing/2026-08-15/document-system-consolidated-landing/CLAUDE.md) | `0d3888e5c7a293abe9b5058d874f5fbe8739a052183b3d7ef10667fa6df69474` |
| `docs/项目说明/00_master_roadmap.md` | [`docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md`](../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md) | `38a5a752342d96e29542f466f3099a9668d4a6b60b04c792265cb539e04f8415` |
| `docs/项目说明/27_status_dashboard.md` | [`docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/27_status_dashboard.md`](../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/27_status_dashboard.md) | `2f6df966769372a7f412cbf2ba14ccb2c1f6caae841b1f5366d7d0691d5cce40` |

- 语义迁移：roadmap 文末 owner 拍板进入上节与 `data/knowledge/decisions.jsonl`；仪表盘 §9 的开放残余进入 [ROADMAP.md](ROADMAP.md)；`CLAUDE.md` 经 manual overlay 调和（补文档系统自举段）后保留，不入 commit；耐久操作知识吸收进 [AGENT_OPERATIONS](../AGENT_OPERATIONS.md)。
- 仪表盘 §9 的已解叙事与完整原文只保留在上述落地归档；未来路线图只列开放残余。
- owner 于 2026-08-15 解除与「三面防污染架构审计」线的落地协调义务；该线文档层前置工作已结束。
- owner 的 GPT Pro 项目对话三轮外部评审以逐字正文归档进入 tracked 研究面，并登记推理外环设计约束；该登记为 `non_authorizing`，推理外环仍处于未立项／概念收敛状态。
- owner 允许归档三轮外部评审并以 non_authorizing 形态登记设计约束；这是 2026-08-15 主线程口头许可经落地会话形成的 authority source，只允许归档与登记动作，不批准约束内容、不立项，也不对现行树新增义务。

## 2026-08-20：I1 异源化触发 P1.2 close claim 机械重开

- **批次身份**：I1（`independent_infeasibility_reverifier`）异源化批改变了 P1.2 close-kernel 的 sealed bytes。
- **触发背景**：owner 对本批采用“不豁免治理、外审后再由 owner re-close”的边界，并于 2026-08-20 裁定范围 A：re-close 前补齐三组新 checker 守卫的 mutation 测试，使 required-test anchor 全部对应实存测试并进入强制层。
- **认证承重面变化**：I1 从复用生产 `PortBindingModel` 求解，重写为纯标准库、闭式算术、artifact-bound 的独立 binding 复验包；本批使 73 个登记 close-kernel sink 的封印字节发生漂移。每个 sink 都声明 `mutation_policy: source_sha256_drift_reopens_p1_2_close_claim`，因此 source SHA-256 漂移按机器契约自动重开 P1.2 close claim。
- **验证状态**：五轮外部异源审计已经完成，第五轮终判 `CLEAN_FOR_REOPEN`。范围 A 已执行完毕：新增 5 个 mutation 测试并取得 60/60 通过，`required_tests` 从 48 扩至 56，reseal 已完成，P1.2 proof gate 从 29 条 issue 收敛到 1 条；两条 sealed-authority parity 测试仍按 owner 边界保持 `2 failed`。
- **显式状态转移**：P1.2 从既有 owner 手动关闭状态，因 sealed source SHA-256 漂移机械转为 **reopened**。该转移是 mutation policy 的自动后果，不是 owner decision，也不建立 `DECISION-P1-2-REOPEN-*` 记录。
- **未完成的 owner 动作与边界**：本事件不表示 re-close 已发生；review gate、owner re-close decision 与 re-close authority floor 仍待后续 owner 动作。任何测试、receipt 或外审判词（包括 `CLEAN_FOR_REOPEN`）都不能替代该动作。
- **证据坐标**：机器因果与 73 个 sink 见 `data/proof_obligations/p1_2_proof_obligations.json`；I1 终态见 `src/search/independent_infeasibility_reverifier.py` 与 `src/search/independent_binding_reverify/`；范围 A 与 reseal 执行见 `docs/research/common_mode_binding_reverify_20260820/ACLOSE_PROGRESS.md`；第五轮外审见 `/home/zhuran24/zmd-pj/.artifacts/gpt_harvest_20260818/EXTERNAL_AUDIT_I1_ROUND5_20260820.md`。
