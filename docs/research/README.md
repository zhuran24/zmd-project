# docs/research/ 历史研究与外审档案

本目录保存按日期/版本冻结的实验、外审、prompt、原始响应和阶段性结论。文件中的“当前”“已闭”“LIVE”“GO”等词只描述其记录时间点，不能覆盖当前工作树。

当前状态必须从 `PROJECT_LOCK.md`、`data/proof_obligations/p1_2_proof_obligations.json`、`data/review_gates/phase_1_2_spike_close.json`、`docs/项目说明/06_current_status.md` 和 `docs/certified_proof_chain_analysis.md` 读取。2026-07-07 后口径：fixed-witness、P1.2 open gate、independent infeasibility reverify 和 PR1 producer/supervisor split 已在后续工作树落地；P1.2 已由 owner `owner_manual_decision` 正式 CLOSED，P1.3 已开启。PR2、review-package 剩余边界中仅防蓄意内鬼硬化桶延期到发布时点，#9a 是部署时点任务。

总注：本目录 `p1_2_v*` 系列报告中的 “P1.2 remains blocked” 等现状句均为各版本时点快照；P1.2 已于 2026-07-07 由 `owner_manual_decision` 正式 CLOSED。P1.3 的“开启”仅表示准许开工，不表示 `step_8_apply_to_master` 生产 master/cut 集成已经完成。

研究档案作为证据保留，不应为了迎合现态而改写当时观察。需要把历史结论用于现行 runbook 时，必须重新对照当前代码和测试，再在 living docs 中写入带日期的结论。

`docs/research/INDEX.md` 只索引 2026-05-07/08 Phase 3C agent transcript，不是本目录的完整 manifest。`docs/DOC_TREE_COMPLETENESS.json` 提供信息性 first-level inventory，但不参与 preflight 或认证。
