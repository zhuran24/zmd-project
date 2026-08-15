# 数字引用纪律

测试数、文件数、工件大小、hash、review anchor、gate 状态和研究 U/L 都是会漂移的事实。正文引用它们时至少同时给出来源和日期；需要表示“现在”时，不再手抄数字，而是链接 [`../CURRENT.md`](../CURRENT.md) 或对应机器源。

使用规则：

1. 规则版本、网格、目标和空矩形语义回到 `rules/canonical_rules.json`。
2. phase 状态只读 `data/review_gates/`，receipt 和测试绿灯不能替代 owner 决定。
3. frozen artifact 的 byte size 与 SHA 必须从当前 obligation/manifest 读取，不从旧报告转抄。
4. 研究 U/L 必须引用带稳定 ID 的 ledger claim，并保留它的前提和“明确不推出”。
5. 历史研究包中的数字可以保留，但引用时必须标明包名、日期和是否已被 supersede。

统一现态投影见 [`../CURRENT.md`](../CURRENT.md)，完整 claim 与证据见 [`../CATALOG.md`](../CATALOG.md)。
