# 文档树与权威边界

本目录同时包含现行说明、规格、运行手册和按日期保存的研究证据。阅读时先判断文件属于哪一层，不要把历史快照里的状态句直接当成当前工作树状态。

## 当前权威顺序

1. `PROJECT_LOCK.md`: exactness、命题 P、发布边界、Accepted Invariants 和 Forbidden Changes。
2. `data/proof_obligations/p1_2_proof_obligations.json`: P1.2 机器义务、proof-bearing sink inventory 和 source/hash floor。
3. `data/review_gates/phase_1_2_spike_close.json`: owner 手动 phase gate。当前仍为 blocked，不能由测试、receipt 或 Markdown 自动打开。
4. `docs/项目说明/06_current_status.md` 与 `docs/项目说明/soundness_gap_roadmap.md`: 当前实现状态和未闭边界。
5. 其它 `docs/`、`specs/` 和 runbook: 在上述边界内解释具体组件。

## 现行发布链

producer 只提交 `CANDIDATE_PROPOSED`。`ExactCampaign.supervisor_seal()` 从已提交 checkpoint 字节复验并铸造持久化终端 `CERTIFIED`；其生产入口是独立命令 `scripts/run_supervisor_seal.py`（从 proposal-ready marker 驱动，`349c56c`），普通 `main.py` 运行不会 seal。`publish_verified_certified_delivery_surface()` 只能再从 supervisor-sealed、磁盘当前的 campaign authority 事务式发布 canonical solution、blueprint 和 manifest。fixed-witness verifier、P1.2 open gate 与 supervisor 调度入口均已落地;owner 已于 2026-07-07 以显式 owner_manual_decision 关闭 P1.2、开启 P1.3B（三轮收口外审 0 上-TCB 洞、gate=`closed_manual_owner_decision`）。「仅防蓄意内鬼」的 PR2 L0/L1 受控 loader/read-once/TCB 深化项按 2026-07-06 令移至发布时点、非 P1.2 闭合前提。

## 历史 subject/projection 文本

`docs/subjects/` 和各文件中的 `<!-- DOC-SUBJECT:... -->` 注释是历史遗留的人工维护文本，不是自动同步系统。当前仓库中不存在：

- `scripts/sync_doc_subjects.py`
- `scripts/check_doc_tree_completeness.py`
- `cc_context/knowledge/PROJECT_SUBJECT_PROJECTIONS.json`
- `cc_context/memory/`

preflight 也没有执行上述工具。修改现行文本时直接编辑目标文件，并用代码、测试和机器 gate 交叉核对。`docs/DOC_TREE_COMPLETENESS.json` 只是信息性 inventory，不是 executable gate。

## 历史研究档案

`docs/research/` 下的目录名通常带日期或版本。其内容保存当时的观察、外审输入输出、实验结果和已被后续修复替代的计划。历史文件可以保留当时的“当前”“已闭”“待办”措辞，但这些措辞只对文件记录的时间点成立。当前状态必须回到本页上方的权威链确认。

## 冻结输入提示

当前工作树包含 `data/preprocessed/candidate_placements.json`，大小 `45,774,305` bytes，SHA256 `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`。其它轻量发行包可以省略它，但 certified exact 运行前必须恢复同一字节。拐角修复前的 `45,773,799` bytes / SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` 旧 hash 工件已 superseded、hash-incompatible，不能作为当前 campaign authority。

## 主要入口

- `docs/项目说明/README.md`: 项目说明书导航。
- `docs/certified_proof_chain_analysis.md`: 当前认证发布链审计。
- `docs/exact_campaign_operations.md`: campaign 操作与恢复边界。
- `docs/PHASE_1_2_CLOSE_GATE.md`: phase gate 的机器/人工职责。
- `docs/specs_index.md`: `specs/` 索引。
- `docs/research/README.md`: 历史研究档案边界。
