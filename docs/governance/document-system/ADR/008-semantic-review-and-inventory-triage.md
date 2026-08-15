# DOC-ADR-008：语义审阅、目录分诊与主题术语投影

状态：Accepted
日期：2026-08-12

## 背景

`dossiers.json` 能证明一个一级研究包或 artifact 根已经被发现，却不能证明其内容已经被理解。反过来，要求在第二阶段一次性逐字审完全部历史包，会诱使维护者用空 claim、宽泛 summary 或“已登记”冒充语义完成度。

此前 `backfill_reviews.jsonl` 已经能表达语义审阅，但没有一个穷尽的结构说明未审 dossier 去了哪里。于是“未审”“低优先级”“同族上下文”“本机工件缺席”容易混成同一种空白。主题和术语也仍主要依赖读者记忆，稳定 claim 虽可查询，却缺少跨目录入口。

## 决定

1. 将三种状态严格分开：
   - dossier inventory 只表示材料可发现；
   - backfill triage 只表示未审材料已被唯一分流；
   - current review 才表示声明范围内做过语义整理。
2. 每个 dossier 必须恰好满足其一：拥有一条 current review，或恰好属于一个 current triage 组。两者不能同时存在，也不能同时缺失。
3. `review_scope=availability_and_provenance` 只核对本机可用性、路径与 provenance，不计作 semantic review。它必须保持 `outcome=deferred`，并写明缺失内容和重审触发条件。
4. `backfill_triage.json` 按组记录 disposition、优先级、理由、相关 claim、代表性 review 与 reopen trigger。triage 不得产生 `no_reusable_claim` 结论，也不得提升 authority。
5. dossier 从 triage 晋升为 semantic review 时，必须在同一事务中新增 current review、从 triage 组移除，并重建投影。空 triage 组应删除。
6. 新增 `terminology.json`，为 canonical label、alias、定义、区别、claim 与来源提供稳定 `TERM-*` 坐标；别名不能在不同 term 间碰撞。
7. 新增 `topics.json`，用稳定 `TOPIC-*` 坐标把 claim、dossier topic label、term、入口和开放问题连接起来。所有 claim、dossier topic label 与 term 必须至少被一个 topic 覆盖。
8. 新增三份生成页：
   - `BACKFILL_LEDGER.md` 分开显示 semantic review、availability-only review 和 inventory triage；
   - `TOPIC_INDEX.md` 提供跨目录主题入口；
   - `TERMINOLOGY.md` 提供 canonical vocabulary 与区别。
9. `docctl context` 对 dossier 路径投影其 current review 或 triage 状态，并给出相关 topic 坐标；`docctl explain` 可按 REVIEW、TRIAGE、TOPIC 或 TERM ID 下钻。
10. 将“语义审阅与目录覆盖分离”登记为 `DOC-INV-011`。

## 后果

- 第二阶段可以对全部 dossier 建立可机检闭包，又不会把 100% inventory coverage 写成 100% semantic review。
- 未审长尾不会消失，而是拥有理由、优先级和重新打开条件。
- agent 操作某个 dossier 时能立刻知道它是否真正审过，不必先扫描全局账本。
- 主题与术语从手写索引变成结构化投影，但不会复制 claim 正文或取代原始证据。

## 未采用的方案

- **把所有 dossier 都生成一条 review**：会把没有阅读过的材料伪装成语义审阅。
- **只保留一个“待审列表”**：无法解释同族上下文、本机缺席、优先级和 reopen 条件，也无法保证唯一覆盖。
- **把 triage 写进 dossier lifecycle**：lifecycle 描述证据包状态，不描述知识整理深度。
- **继续人工维护主题页和 glossary**：会重新引入重复真相与术语漂移。
