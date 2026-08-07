# canonical 公理 kernel + 四件套修正批（2026-08-07）

owner 2026-08-07 晨拍板：公理 kernel 提案与在案四件套（W-PENDING-01）合并、一次
freeze-ritual 走完。本目录 = 该批的定谳存档 + reseal 台账 + 验证记录。

## 落进 canonical 的内容（全部在 `semantics` 段内，纯 additive）

| 内容 | 落点 |
|---|---|
| 公理 kernel 章节（11 条公理 A1-A11 精缩 + scope 前提 + 裁决级输入 #14/#15 + 模型更严面登记） | `semantics.axiom_kernel`（新条目） |
| ①终端条款（口岸三分法：有线仓储口无限混吃 / 箱 6 槽有界 / 机器口配方槽污染；混流段须终止于结构上不拒收的终端） | `semantics.mixed_commodity_flow.terminal_clause` |
| ②速率引理适用范围（满产 + 最小车道分配双前件；10/17 勘误；21/22 输入侧标注；非谓词、认证叙事引用规则） | `semantics.rate_lemma_scope`（新条目） |
| ③限制口刻意不建模理由重述（结论保留；必要性=零：中间产物算术禁混 + 不拒收终端 + 分拣终端定理 #21） | `semantics.item_admission_port_exclusion.rationale_restated` |
| ④单口单商品范围声明（binding 槽位单商品制表达力缺口钉在胶囊+电池终端段 2-4 道；处置 (i) scope 声明） | `semantics.port_commodity_scope`（新条目） |
| 箱条款槽数口径（6 格占满即堵门、与类型数无关——owner P2 定谳，防再写宽） | `semantics.protocol_storage_box_wireless.slot_count_clause` |
| 现有条款推导注记（boundary_placement / routing_cross_junction / connectivity_quantifier / machine_min_clearance / warehouse_bridge_exclusion / power_source_note / power_coverage_stencil 各 +`axiom_derivation`） | 各条款子键 |

新 canonical：40,371 B / SHA256 `b675fb6a1cdae7920f90abf63e59aa76ea8df37ae8a8c5d5d15b10b94218c4ca`。

## 目录清单

| 文件 | 是什么 |
|---|---|
| `AXIOM_KERNEL_PROPOSAL_20260806.md` | 公理系终稿提案 v2 全文（11 公理 + 参数表 + 推导矩阵 #1-#21 + 四方一致性矩阵 + 残余清单），owner 08-06 终审全认可；canonical `axiom_kernel.source_doc` 指向本件 |
| `VERIFICATION_ANNEX_20260806.md` | 三席验证意见原文（反例席/完备性席/矛盾猎人） |
| `DOC_MEMORY_FIXLIST_20260806.md` | 文档-记忆修正清单 |
| `MFG_SLOT_PARAMS_20260806.md` | 制造机槽参数系统抽取（A7 换算方向安全的依据） |
| `PORT_SEMANTICS_REVERDICT_A_20260806.md` | 口岸语义终定谳（附录补遗一/二 + 批注）——四件套 ①③④ 与箱槽数口径的定谳原文 |
| `rate_lemma_recompute.py` / `rate_lemma_recompute.receipt.txt` | 速率引理机器复算脚本与 receipt（10/17 勘误、21/22 侧别、反例 0 对）——②的 receipt |
| `RESEAL_MANIFEST.md` | 全部 pin 面（文件:行号:旧→新）、连锁层次、史料门名单、提交 pathspec |
| `DEPENDENCY_VERIFICATION.md` | candidate_placements 不需重生成 + 派生工件字节不变的逐行验证 |
| `pin_audit_true_values.txt` | pin 面 python 真值审计输出（import + assert，非 grep） |
| `gate_full_20260807.log` / `gate_slow_20260807.log` | preflight `--full` 与 `--slow-tests` 完整输出 |

## 开放问题

无未决语义冲突。三处形状/边界决策的留痕见 `RESEAL_MANIFEST.md` §6
（additive 形状、U-02 归属 mixflow 线、source front 解锁排除在本批外）。
