# 推理外环四轮外部评审归档（2026-08-15）

> **性质：** 本 dossier 同时承担两种 research-only 角色：owner 的 GPT Pro 项目对话所产四轮外部评审的 tracked 逐字归档，以及从评审中提取的条件式设计约束与可证伪架构假设登记。
> **效力上限：** 本目录及其正文的效力封顶为 `research_authority`；沿用历史执行收据的封顶先例，不构成 owner ruling、项目立项、现行实现义务或发布授权。
> **史料边界：** 三份归档正文只保存评审时点原文，不追随仓库现状改写；条件式登记的当前边界见本目录约束文档。当前状态、未来工作与 owner 决定分别以现行状态页、路线图和 owner authority source 为准。
> **流程状态：** dossier 处于 `active` workflow；逐字归档与条件式登记是否在 typed closure 时拆成两个 dossier 尚待裁决。

## 四轮来源

| 轮次 | 归档正文 | 主题 | 评审输入 HEAD | 仓外原件 |
|---|---|---|---|---|
| 第一轮 | [`round1_project_architecture_and_failure_compiler_review.md`](round1_project_architecture_and_failure_compiler_review.md) | 全项目长处／短处、三个新架构的消歧、失败编译器建议 | `8c25aaf` | `/home/zhuran24/文档/Text File.txt` |
| 第二轮 | [`round2_mathematical_shape_and_proof_complexity_review.md`](round2_mathematical_shape_and_proof_complexity_review.md) | 从数学形态复核推理外环直觉与证明复杂度框架；沿用第一轮项目快照 | `8c25aaf` | `/home/zhuran24/文档/Text File (1).txt` |
| 第三轮 | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) | 重读方法论正典后的语义压缩、双环、等式挖矿、残余自由度量与三条数学假设 | `3362dc7` | `/home/zhuran24/文档/Text File (2).txt` |
| 第四轮 | [`round4_blind_observability_experiment_sequence_and_binding_routing_wall_review.md`](round4_blind_observability_experiment_sequence_and_binding_routing_wall_review.md) | 从弱到强的可观测现象阶梯、实验序列、最小决定性实验与 binding/routing 深墙关系 | 不读取仓库；对 Phase -1 实测盲态下产出 | 2026-08-15 当前 GPT-5.6 Pro 分支会话 |

四份归档正文均保存各自来源的逐字正文，不含修订或批注。前三轮是仓外原件的逐字节副本；第四轮由当前 GPT-5.6 Pro 分支会话在 owner 明示“全程不要调用工具、不要读仓库”后产出，完成后才接收 Phase -1 实测摘要。

## 字节身份

| 归档正文 | SHA-256 |
|---|---|
| `round1_project_architecture_and_failure_compiler_review.md` | `0e25f508ec00d9c6cc28499bc188e6d1d35212af8fb27a66a59cbe2d3ee2c0cf` |
| `round2_mathematical_shape_and_proof_complexity_review.md` | `80d15229cb1a4a591621271498d43cd482fa533315801de5862a305720a6a934` |
| `round3_semantic_compression_dual_loop_and_residual_freedom_review.md` | `755da5707a26ebfd0d10a2e0be8b74847728675f45d0e1c049f033d4e223938b` |
| `round4_blind_observability_experiment_sequence_and_binding_routing_wall_review.md` | `2bf8639eb54286b2769293e4fbd9cc5fb7a125d34bf2ce5770f57e03ab159f54` |

## 条件式登记

[`REASONING_OUTER_LOOP_DESIGN_CONSTRAINTS.md`](REASONING_OUTER_LOOP_DESIGN_CONSTRAINTS.md) 保存条件式设计约束和可证伪架构假设。归档与 `non_authorizing` 登记动作的许可及其非蕴含边界，只以 [`DECISION-OUTER-LOOP-REVIEW-REGISTRATION-20260815`](../../../data/knowledge/decisions.jsonl) 为准；证据链为该 decision → [`OWNER_INSTRUCTION_20260815.md`](OWNER_INSTRUCTION_20260815.md) 窄存录 → 存录内所列仓外会话转录。

## Phase -1 立项前实验闸

[`phase_minus1/`](phase_minus1/README.md) 保存 owner 已授权开展、但仍不产生立项的 Phase -1 证据线。该线先冻结协议和 corpus，再运行无 cap 死因谱、producer→consumer 触达与外部布局终验 canary；实验结果只能进入 owner 的第二道立项闸。

## 实验一：离线短证书

[`experiment_one_w0_ghost_front_offline_certificate_20260815/`](experiment_one_w0_ghost_front_offline_certificate_20260815/README.md) 保存第一号对象的完整研究包：以固定 W0 布局中的活动边界源口为单原子触发器，从 canonical 规则与 pinned 输入字节独立证明其前格和 strict-empty 矩形冲突，并在不把观测当证明的前提下测量冻结 1007 个 binding selection 的覆盖。该包不包含 solver integration、lowering、D3/D4、认证或发布动作。

## 已知字节保真 lint debt

**状态：** `ACCEPTED_KNOWN_LINT_DEBT`。

复现命令 `git diff --check 3362dc7..HEAD` 会报告第三轮归档第 502 行的 `=======` 为 leftover conflict marker。该行是原文数学分式横线；三份归档正文以逐字保真优先，因此接受这项累计区间 lint debt，不改写原文，也不增加豁免工程。工作树级检查不受这项历史区间债务影响。

## Provenance

执行席位＝GPT-5.6-Sol（CC harness），commit trailer 使用 harness 模板名义；评审席＝GPT Pro（浏览器接入）。
