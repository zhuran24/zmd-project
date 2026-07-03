# 数字引用纪律

测试数、文件数、工件大小、hash、review anchor 和 gate 状态都必须带来源和日期，不能把历史数字写成无时间边界的“当前值”。

截至 2026-06-26：

- `pytest --collect-only -q src/tests` 收集 425 个测试文件、3450 个测试。
- 这只是 inventory，不表示完整测试套件在本次审计中通过。
- `candidate_placements.json` 为 `45,774,305` bytes，SHA256 `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`；拐角修复前的 `45,773,799` bytes / SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` 版本已 superseded，且 hash-incompatible。
- phase gate anchor 为 `v99_p1_2_close_kernel_sealing`，状态仍 blocked。

旧研究包中的测试计数和性能数字继续作为历史证据保留，引用时必须注明包名或日期。
