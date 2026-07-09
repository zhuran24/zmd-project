# 交付内容

* `REVIEW.md`：完整架构、实现、领域对照与通电前建议。
* `patches/0001...0004.patch`：可独立审阅和 `git apply` 的补丁序列。
* `design/RFC-001...003.md`：所有 Q1/Q2 CONCERN 的替换设计。
* `evidence/`：源码一致性、规模、基线测试、三条反例、补丁后测试与静态检查日志。
* `evidence/repro_scripts/`：三个未改源码反例脚本。

推荐阅读顺序：`REVIEW.md`，然后 patch 0001 至 0003，最后按需要阅读三个 RFC。patch 0004 仅是类型注解卫生修复。
