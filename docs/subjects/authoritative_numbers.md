# 数字引用纪律

测试数、文件数、工件大小、hash、review anchor 和 gate 状态都必须带来源和日期，不能把历史数字写成无时间边界的“当前值”。

测试 inventory（2026-07-11）：

- `pytest --collect-only -q src/tests` 收集 4182 tests；工作树含 450 个 `test*.py` 文件。`pytest --collect-only -q src/tests/cuts` 收集 594 tests。
- 这只是 inventory，不表示完整测试套件在本次审计中通过。
- phase gate anchor 为 `v99_p1_2_close_kernel_sealing`，机器状态为 `closed_manual_owner_decision`；`next_phase_entry.allowed=true`。

冻结工件与当前语义（2026-07-18 实测）：

- `canonical_rules.json`：18,137 bytes，SHA256 `c3666d78d5dd1329514c7813be9f91f09cb3ce7b94907ef5b6ce746c9bcbbbd5`。
- `preprocess_plan.json`：1,383 bytes，SHA256 `5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`。
- `candidate_placements.json`：54,467,709 bytes，SHA256 `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`。`a914…` 45,774,305 bytes、`adcc…` 45,773,799 bytes、`d5e3…` 53,594,995 bytes 与 `78e2…` 53,595,501 bytes 仅属 superseded、hash-incompatible 历史链。
- `box_sink` 为 3 个物理输入/3 个物理输出，mandatory core 为 14 个物理输入/6 个物理输出；generic-input 成品必须路由到 provider physical input。当前需求 2 已被真实 mandatory core 覆盖，所以 provider-aware、instance-aware box lower bound 为 0。
- exact session 原子绑定同一 plan snapshot 的完整 `generic_input_slots_by_operation` map；不能退回 box-only scalar 或中途重读。

旧研究包中的测试计数和性能数字继续作为历史证据保留，引用时必须注明包名或日期。
