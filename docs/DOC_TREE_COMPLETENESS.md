# 文档树完整性说明

`docs/DOC_TREE_COMPLETENESS.json` 是信息性文件清单，用于帮助审计者发现新增、移动或删除的文档面。它不是 proof gate，也没有配套 checker。

截至 2026-06-26，仓库中没有 `scripts/check_doc_tree_completeness.py`，preflight 不检查 subject/projection 同步或文档树清单完整性。因此：

- 清单中的 `present` 只表示生成清单时文件存在。
- 清单不证明文档内容与代码一致。
- 清单不影响 P1.2 close、`CERTIFIED` mint、公开发布或 P1.3 entry。
- 新增或删除文档时应更新清单，但漏更属于文档维护债，不得被写成机器 gate 已通过或失败。

当前状态由 `PROJECT_LOCK.md`、`data/proof_obligations/p1_2_proof_obligations.json`、`data/review_gates/phase_1_2_spike_close.json` 和 `docs/项目说明/06_current_status.md` 共同约束。
