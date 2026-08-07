# 文档树与权威边界

本目录同时包含现行说明、规格、运行手册和按日期保存的研究证据。阅读时先判断文件属于哪一层，不要把历史快照里的状态句直接当成当前工作树状态。

## 当前权威顺序

1. `PROJECT_LOCK.md`: exactness、命题 P、发布边界、Accepted Invariants 和 Forbidden Changes。
2. `data/proof_obligations/p1_2_proof_obligations.json`: P1.2 机器义务、proof-bearing sink inventory 和 source/hash floor。
3. `data/review_gates/phase_1_2_spike_close.json`: owner 手动 phase gate。当前为 `closed_manual_owner_decision`，P1.3 entry allowed；但不能由测试、receipt 或 Markdown 自动打开，2026-07-07 的关门动作只认显式 `owner_manual_decision`。
4. `docs/项目说明/06_current_status.md`: 当前人类可读状态。`docs/项目说明/soundness_gap_roadmap.md`
   只保存截至 2026-07-11 的 P1.2 soundness 历史快照，不是当前 authority。
5. 其它 `docs/`、`specs/` 和 runbook: 在上述边界内解释具体组件。

## 现行发布链

producer 只提交 `CANDIDATE_PROPOSED`。`ExactCampaign.supervisor_seal()` 从已提交 checkpoint
字节复验并铸造持久化终端 `CERTIFIED`；其生产入口是独立命令
`scripts/run_supervisor_seal.py`，普通 `main.py` 运行不会 seal。
`publish_verified_certified_delivery_surface()` 只能再从 supervisor-sealed、磁盘当前的
campaign authority 事务式发布 canonical solution、blueprint 和 manifest。owner 已于
2026-07-07 以显式 `owner_manual_decision` 关闭 P1.2、开启 P1.3。

截至 2026-07-27，Stage B B0-B5b 工程面已完成；typed lowering 仅 F1/F6/F7，F5 仍为
shadow-only，attach 仍 unsafe/default-off，B6 owner promotion 未关闭。研究账本为
`U=(1188,22)`、`L=absent`，`(1188,18)` 为 `FORMAL_AUTHORITY_INCOMPLETE`。
Rule/cut evolution 仍是 test/offline shadow，noncert cuts A/B 仍是有界、non-authorizing
研究；二者都不建立 production `CERTIFIED`、项目上下界、witness 或 optimality。
「仅防蓄意内鬼」的 PR2 L0/L1 受控 loader/read-once/TCB 深化项按 2026-07-06 令移至发布时点、
非 P1.2 闭合前提。

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

当前冻结 pin 为：`rules/canonical_rules.json` 40,371 bytes / SHA256 `b675fb6a1cdae7920f90abf63e59aa76ea8df37ae8a8c5d5d15b10b94218c4ca`；`rules/preprocess_plan.json` 1,383 bytes / SHA256 `5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`；`data/preprocessed/candidate_placements.json` 54,467,709 bytes / SHA256 `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`。其它轻量发行包可以省略 candidate 文件，但 certified exact 运行前必须恢复同一字节。45,774,305-byte `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`、45,773,799-byte `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`、53,594,995-byte `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` 和 53,595,501-byte `78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef` 只属 superseded、hash-incompatible 历史链。

当前 generic-input 合同使用物理端口与普通路由：`box_sink` 3 进/3 出，mandatory core 14 进/6 出，成品从 producer output 路由到 provider physical input。provider-aware、instance-aware box lower bound 因需求 2 已被真实 core 容量覆盖而为 0；exact session 原子绑定完整 `generic_input_slots_by_operation` map。

## 主要入口

- `docs/项目说明/README.md`: 项目说明书导航。
- `NAV_MAP.md` + `specs/11_pipeline_orchestration.md`: 当前认证发布链与 authority 调用链。
- `docs/certified_proof_chain_analysis.md`: 2026-06-19 的历史 write-point 审计，不能覆盖当前 PR1 链。
- `docs/exact_campaign_operations.md`: campaign 操作与恢复边界。
- `docs/PHASE_1_2_CLOSE_GATE.md`: phase gate 的机器/人工职责。
- `docs/specs_index.md`: `specs/` 索引。
- `docs/research/README.md`: 历史研究档案边界。
