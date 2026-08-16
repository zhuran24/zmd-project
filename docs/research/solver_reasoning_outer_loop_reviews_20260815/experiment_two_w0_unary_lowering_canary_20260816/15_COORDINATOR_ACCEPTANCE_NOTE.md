# W0 一元 lowering 金丝雀批尾验收与审计对账

> **性质与截止：** 本文件为批尾验收/审计对账存档，截至 2026-08-16。
> **效力边界：** 本文件记录协调席对执行批、机械审计与科学复核的对账结论；不把 research-only 结果提升为认证、发布或通用 D3/D4 权限。

## 1. 机械审计对账

Sol 机械审计总判定为 `DEFECTS_FOUND`；四项缺陷及状态如下。

1. **GPT-5.6 Pro tracked 收据契约缺口——已关闭。** [`13_GPT56PRO_RUN_RECEIPT.json`](13_GPT56PRO_RUN_RECEIPT.json) 的 `contract_identity` 已具备 [`03B_RECEIPT_ENVELOPE_SCHEMA_V1.json`](03B_RECEIPT_ENVELOPE_SCHEMA_V1.json) 强制要求的 `manifest_path` 与 `receipt_schema_path`，并通过冻结收据 schema 的实际校验。
2. **`988d1b7` 提交表面披露不全——内容合规，形式瑕疵存档。** 提交 `988d1b787778c211f5e8b930b7f6cf093581aed8` 对 [`../REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`](../REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md) §6.7 增加“过缓不自曝 ↔ 过严不自曝”互指，属于协调席带内增量第 8 条明令授权的同批小编辑，内容与授权相符；该提交信息未披露此文件，构成提交表面形式瑕疵，不影响内容合规性与科学判词。
3. **执行席提交链计数——已对平。** 执行席收尾自报的八笔 lineage 提交链漏列 `0ad7af7e3ba6d3fac465b5c2de1a77fb07711571`（金丝雀入口登记）；完整计数为九笔。
4. **旧 `w0-unary-canary-r1-20260816/` 证据——降格为 `raw-only`。** `lowering_contract_receipt.json`、`endpoint_sensitivity.json` 与 `AGGREGATE_SUMMARY.json` 不满足 [`03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md`](03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md) §1 的八字段收据超集，因而不可采纳为 contract、sensitivity、aggregate 或 final-verdict 收据；`A_BASELINE/summary.json`、`B_OBSERVER_NOOP/summary.json` 与 `C_UNARY_LOWERING/summary.json` 同为 `raw-only`。GPT-5.6 Pro lineage manifest 显式排除该 run 目录，冻结科学判词未受其污染。

## 2. 科学面复核

科学面复核全绿：数字 12 项复算吻合，mutation canary `4/4`，敏感性控制 `11/11`，装置事故记录保持只追加，判词纪律零残留。

## 3. 活树三检归因

活树三检的 `BLOCK` 唯一归因于并行线 `docs/research/tri_plane_model_v2_20260816/` 的在途登记事务，不由本批引入；该线落库批完成登记后解除。本批不登记、移动或删除该并行目录。
