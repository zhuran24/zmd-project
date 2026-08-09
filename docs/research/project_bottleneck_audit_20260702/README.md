# 2026-07-02 全项目瓶颈审计归档（多代理工作流，37 agent）

> **[时点标注]** 本文为收口前快照；文中「P1.2 仍 blocked / blocked_manual_review_count」等现状描述已过时——P1.2 已于 2026-07-07 由 owner_manual_decision 正式 CLOSED（P1.3 已开启），现状以 data/review_gates/phase_1_2_spike_close.json 为准。

**性质**：HISTORICAL_OR_PLAN 审计档案。另一会话于 2026-07-02 深夜运行的全项目「历史 + 最终目标瓶颈」
调查工作流产物：8 个维度 × fable/codex 双模型独立阅读（16 份维度报告，`dims.md`），继而合成 12 条
瓶颈、逐条由独立核查员回源码验证（`bottlenecks.md`，每条带 VERDICT: CONFIRMED/PARTLY、
severity 独立复核与 file:line 核实记录）。**不是**当前状态权威；快照后仓库已发生重大变化（见下表）。

| 文件 | 内容 |
|---|---|
| `bottlenecks.md` | 12 条瓶颈（severity + votes + lenses + evidence + why + fix）+ 逐条核查记录 |
| `dims.md` | 16 份维度报告全文：history / cert-chain / solver-math / gates / branches / release / tests / ops × 双模型 |

完整产物集（raw workflow JSON 308KB、37-agent journal、工作流脚本、衍生摘要 dim-summaries/dim-facts、
dossier HTML）不入仓库，另存两份：`C:\Users\22957\zmd_bottleneck_audit_20260702\` 与
`E:\zmd_backups\zmd_bottleneck_audit_20260702\`。

## ⚠ 时效对照（快照 = 2026-07-02 23:2x，早于 07-03 画线与 07-04 合并/通电批次）

按 2026-07-05 对 main 的实测，12 条中以下条目的现状已改变：

| 审计条目 | 快照后现状 |
|---|---|
| main seal 三项校验被跳过 + pr2-5 未合入（votes=4） | **已解决**：pr2-5 于 `6e06922` 合入 main（round-19/20 全吸收、分支指针已删）；child 的 declare_mode/last_stop_reason 修复已在 main（`pr2_l0_true_verifier_child.py:449` 实测） |
| PR2 #7 通电缺口（votes=4） | **主体已解决**：`349c56c` 通电，生产入口 `scripts/run_supervisor_seal.py` 存在。其中「不打桩 seal→publish 端到端测试缺失」半点是否已补未核实 |
| owner 单人单机零冗余（votes=3，核查降 major） | **部分解决**：pr2-5 硬化已进 main 历史；2026-07-05 已做全分支 git bundle（`C:\Users\22957\zmd_git_backup_2026-07-05\`）并连同 06-16 的 920-commit 原史料 bundle 一起拷入 `E:\zmd_backups\`（第二块物理盘）。**残留**：GitHub 私有远端 zmd_pj 的 main 停在 07-01 推送、不含合并后工作；本仓库无 remote；是否推送由 owner 决定 |
| clean-review 关门循环无终止保证（votes=2） | **前提已变**：owner 2026-07-03 在 round-20 close-kernel 强度上画 TCB 线、停外审循环（画线 ≠ 取消 backlog）；收口路径改为「PR2 #1 深化完成后走收口外审 + 三连 clean 计数 + owner 手动门」，不再是开放循环 |
| CP-SAT 编码忠实性单点——其中一处出入 | `a731764` 已强制 I1 独立复验 binding 关闭 overload separation（深度防御补齐）。**核心单点仍成立**：复验与生产共用同一构造器 + 同一 CP-SAT 库，无异构第二编码 |
| 文档-代码-分支漂移（PARTLY） | **大幅缓解**：`efd3de4`/`5151859`/`a5985da` 三提交做了全量文档/记忆清扫。**残留**：PROJECT_LOCK §1A 的 binding 锚（`:930/:976/:1022`）2026-07-05 实测仍是漂移前旧值（实际 +117 行） |

**仍完全成立的条目**（2026-07-05 实测口径）：算力硬墙（第一多米诺）、P1.2 owner 手动门
（设计如此）、CP-SAT 编码忠实性单点、F1-F9 未接入生产（`step_8_apply_to_master` 实测仍
NotImplementedError）、dependency floor manifest 占位（deploy_pending_placeholder）、
168h 执行层工程债、冻结输入只证「没变」不证「正确」。

> **[superseded]** 其中「P1.2 owner 手动门」作为 2026-07-05 现状条目已过时：P1.2 已于 2026-07-07 由 owner_manual_decision 正式 CLOSED（P1.3 已开启），现状以 data/review_gates/phase_1_2_spike_close.json 为准；手动门纪律本身仍有效，仍不得从测试/receipt/seal/checker 绿灯自动推导 closed/released。

## 与「先想后做」三设计稿的关系

算力硬墙的 fix ①（F1-F9 接入，含 F5 置换墙）与编码忠实性的异构复验方向，其最难的数学部分已被
`p1_3_f5_orbit_lift_soundness_design_v2.md`（v3）与 `terminal_no_solution_evidence_contract_design_v2.md`（v3）
的设计（禁共享 parser、独立复验 TCB 纪律）预先覆盖；吞吐稿（P2.0）覆盖圈外巨兽中最大的一头。
三稿均过三轮独立审查、以 v3 为实现基准（见 `p2_design_external_reviews_20260704/`）。
