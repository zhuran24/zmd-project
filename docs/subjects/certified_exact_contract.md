# Certified exact contract

`certified_exact` 与 `exploratory` 是分离路径。exact 目标为 `max_lex(area, min_side)`，`min_side >= 6` 是候选 admissibility。flow 子问题只提供诊断，不是 certified gate。

冻结 source-of-truth 输入包括：

- `rules/canonical_rules.json`
- `rules/preprocess_plan.json`
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

当前 pin：`canonical_rules.json` 为 40,371 bytes / SHA256 `b675fb6a1cdae7920f90abf63e59aa76ea8df37ae8a8c5d5d15b10b94218c4ca`；`preprocess_plan.json` 为 1,383 bytes / SHA256 `5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`；`candidate_placements.json` 为 54,467,709 bytes / SHA256 `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`。其它发行包省略 candidate 文件时，必须在运行前恢复相同字节。45,774,305-byte `a914…`、45,773,799-byte `adcc…`、53,594,995-byte `d5e3…` 和 53,595,501-byte `78e2…` candidate 仅构成 superseded、hash-incompatible 历史链。

当前 generic-input 合同要求成品从 producer output 路由到 provider physical input。`box_sink` 有 3 个物理输入/3 个物理输出，mandatory core 有 14 个物理输入/6 个物理输出。下界同时识别 provider operation 与实际 instance；当前需求 2 已由 mandatory core 的 14 个真实输入覆盖，因此 box lower bound 为 0，未实例化模板不得记容量。exact session 只使用同一 hash-bound plan snapshot 中完整的 `generic_input_slots_by_operation` map。

候选级 strong status、terminal result 和公开 artifacts 的完整 authority 规则见 `PROJECT_LOCK.md`。特别是 producer 的 in-memory 返回值、generic writer、viewer 或 adapter 都不能单独授予 proof-bearing `CERTIFIED`。
