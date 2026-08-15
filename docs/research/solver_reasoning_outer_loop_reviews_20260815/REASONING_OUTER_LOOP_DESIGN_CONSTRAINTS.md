# 推理外环设计约束登记

> **分层效力：** A1–A6、A8–A9 只在推理外环获得 owner 立项裁决后约束该线设计；A7 的 Phase -1 证据协议建议可在立项前由实验设计消费，但始终为 `non_authorizing`，只约束证据可采纳性，不产生立项，也不强制任何人开跑实验。
> **现行义务边界：** 本登记对现行树零新增义务；“架构假设”一节不是约束。
> **登记依据：** 归档与 `non_authorizing` 登记动作的许可及其非蕴含边界，只以 [`DECISION-OUTER-LOOP-REVIEW-REGISTRATION-20260815`](../../../data/knowledge/decisions.jsonl) 为准。
> **升格纪律：** 任何一条要从 `non_authorizing` 升为权威，升格动作必须是 owner 显式逐项拍板并留下 ruling；“用了很久没人反对”不构成升格。

## A1　三账本命题身份统一

| 栏 | 登记 |
|---|---|
| **出处** | [`round1_project_architecture_and_failure_compiler_review.md`](round1_project_architecture_and_failure_compiler_review.md) 第一轮，§6。 |
| **效力** | `non_authorizing / research_governance`。 |
| **效力边界** | 约束对象＝推理外环若立线后的命题身份与证据存储；生效条件＝该线获得 owner 立项裁决。文档 claim、规则 theorem 与 solver `Judgment` 必须共享同一规范化命题身份和单一 evidence root，各自只作为只读投影；禁止建立三套 ledger 再相互同步。 |
| **已有本体指针** | [`DECISION-LEDGER-AUTHORITY-INTERFACES-20260813`](../../../data/knowledge/decisions.jsonl) 同一记录同时承载 decisions register 的非权威／指针校验形态与 claims authority 准入结论。**现行树的对应运动=档案面批（`decisions.jsonl` 已落显式非权威+指针校验形态，`GENERATED_PROJECTION` 翻转是档案面批义务），本条不对现行树新增义务。** |

## A2　上下文采用结构化假设代数

| 栏 | 登记 |
|---|---|
| **出处** | [`round1_project_architecture_and_failure_compiler_review.md`](round1_project_architecture_and_failure_compiler_review.md) 第一轮，“context 可能爆炸”。 |
| **效力** | `non_authorizing / research_governance`。 |
| **效力边界** | 约束对象＝推理外环若立线后的上下文身份、复用与迁移；生效条件＝该线获得 owner 立项裁决。上下文必须表达假设集合的子集关系、单调提升、可行域包含、已证等价与 `context transport`；hash 只确认字节身份，不得代替假设代数。 |
| **相邻实验指针** | [`DECISION-SEMANTICS-SPLIT-EXPERIMENT-FIRST-20260813`](../../../data/knowledge/decisions.jsonl) 与 [`OWNER_DECISION_SUMMARY.md`](../rule_system_redesign_20260807/OWNER_DECISION_SUMMARY.md) 管的是文件拆分、传递依赖根、epoch 与 pin 成本实验，属于相邻依赖根实验，不是本条假设代数的同题本体。未来若两线均获立项且确需共享 context 机制，由 owner 另行决定是否共用。 |

## A3　每种可执行判断具有独立 lowering 正确性契约

| 栏 | 登记 |
|---|---|
| **出处** | [`round1_project_architecture_and_failure_compiler_review.md`](round1_project_architecture_and_failure_compiler_review.md) 第一轮，“抽象定理到实际约束之间还有三道翻译缝”。 |
| **效力** | `non_authorizing / research_governance`。 |
| **效力边界** | 约束对象＝推理外环若立线后任何会改变可行域的可执行判断；生效条件＝该线获得 owner 立项裁决。游戏语义→形式命题→runtime checker→master／binding 具体约束的三道翻译缝必须逐道设防，每种可执行判断必须有独立 lowering correctness contract。 |
| **已有本体指针** | 现行树只有局部先例而无统一的全判断本体：[`PROJECT_LOCK.md`](../../../PROJECT_LOCK.md) 登记 F1／F6／F7 typed lowering 单入口，F5 无 lowering 不得改 master；[`FINAL_DESIGN.md`](../rule_system_redesign_20260807/FINAL_DESIGN.md) 登记 `implementation_anchors`、形式化 condition 与独立 checker。二者不能被外推成推理外环已具备通用 lowering 正确性契约。 |

## A4　推理外环四能力

| 栏 | 登记 |
|---|---|
| **出处** | [`round2_mathematical_shape_and_proof_complexity_review.md`](round2_mathematical_shape_and_proof_complexity_review.md) 第二轮，结尾四能力清单。 |
| **效力** | `non_authorizing / research_governance`。 |
| **效力边界** | 约束对象＝推理外环若立线后的能力边界与架构验收；生效条件＝该线获得 owner 立项裁决。四项缺一不可：瓶颈驱动查询而非盲目饱和；概念发明是架构组件而非体系外残余；创造不可信而检查可信；必要条件与充分构造双向生长。 |
| **已有本体指针** | [`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) 的问题观、预设、诚实记账与上桌纪律，以及 [`REASONING_METHOD.md`](../../项目说明/REASONING_METHOD.md) 的双 ledger、主动挖对偶、榫眼／被迫性与构造判例，分别覆盖相关方法；现行 tracked 方法论载体未把四项合并为一个推理外环能力本体。 |

## A5　等式挖矿

| 栏 | 登记 |
|---|---|
| **稳定概念名** | 等式挖矿。 |
| **作用域标签** | 推理外环双向生产接口；标签不承载本体内容。 |
| **canonical 本体指针** | [落地时 `00_master_roadmap.md` 归档](../../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md) §0b“等式挖矿”；当前说明坐标＝[`REASONING_METHOD.md`](../../项目说明/REASONING_METHOD.md)“干净房间外部收编”第 5 项与 [`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) §四。具体含义一律回正典读取。 |
| **独立重发现** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) 第三轮独立重发现。 |
| **效力边界** | `non_authorizing / research_governance`；本条只登记稳定概念名、指针、作用域标签与独立重发现关系，不授权、不复制、不修改本体。 |

## A6　残余自由为一阶验收量

| 栏 | 登记 |
|---|---|
| **稳定概念名** | 残余自由为一阶验收量。 |
| **作用域标签** | 推理外环架构与实验验收；标签不承载本体内容。 |
| **canonical 本体指针** | [落地时 `00_master_roadmap.md` 归档](../../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md) §0b“自由两源／用计算购买被迫性”；当前说明坐标＝[`REASONING_METHOD.md`](../../项目说明/REASONING_METHOD.md)“理论根基”与 [`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) §一。具体含义一律回正典读取。 |
| **独立重发现** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) 第三轮独立重发现。 |
| **效力边界** | `non_authorizing / research_governance`；本条只登记稳定概念名、指针、作用域标签与独立重发现关系，不授权、不复制、不修改本体。 |

## A7　接口可压缩性与 Phase -1 证据协议

| 栏 | 登记 |
|---|---|
| **稳定概念名** | 接口可压缩性。 |
| **作用域标签** | Phase -1 证据协议建议／立线后设计约束壳；标签不承载本体内容。 |
| **canonical 本体指针** | [落地时 `00_master_roadmap.md` 归档](../../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md) §0b“补记⑧／补记⑧续”；当前说明坐标＝[`REASONING_METHOD.md`](../../项目说明/REASONING_METHOD.md) 同名两节与 [`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) §六。具体含义一律回正典读取。 |
| **Phase -1 证据协议建议** | `non_authorizing`；可在实验设计时、立项裁决前消费，只约束证据可采纳性，不产生立项，不强制任何人开跑实验。接口可压缩性维度归入该协议建议；本登记不替未来编写协议。 |
| **立线后设计约束壳** | 若推理外环获得 owner 立项裁决，保留该概念的设计约束入口；具体内容仍从 canonical 本体读取。 |
| **独立重发现** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) 第三轮独立重发现。 |
| **效力边界** | `non_authorizing / research_governance`；本条只登记稳定概念名、指针、作用域标签、分层消费边界与独立重发现关系，不授权、不复制、不修改本体。 |

## A8　残余核引擎去中心化

| 栏 | 登记 |
|---|---|
| **出处** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) 第三轮，§十；[`round2_mathematical_shape_and_proof_complexity_review.md`](round2_mathematical_shape_and_proof_complexity_review.md) 第二轮提供“CP-SAT 处理残余核”的前置判断。 |
| **效力** | `non_authorizing / research_governance`。 |
| **效力边界** | 约束对象＝推理外环若立线后的残余核引擎选择；生效条件＝该线获得 owner 立项裁决。CP-SAT 只能是收尾引擎之一，不得被规定为唯一内层；引擎按残余问题的证明语言与结构选择。 |
| **已有本体指针** | [`22_project_journey_plain_language.md`](../../项目说明/22_project_journey_plain_language.md)“五轮攻坚”第 4 轮：front-clear 数学规约经对抗审查站住，紧凑模型仍令三个负锚点全部 `UNKNOWN`，原文判词即“数学赢了，求解器输了”。此处只把该 tracked 案例提升为未来推理外环的引擎去中心化约束，不改变现行 solver。 |

## A9　双环与三极使用隔离

| 栏 | 登记 |
|---|---|
| **稳定概念名** | 双环与三极使用隔离。 |
| **作用域标签** | 推理外环双向集合逼近与证据消费权限；标签不承载三极本体。 |
| **canonical 本体指针** | [落地时 `00_master_roadmap.md` 归档](../../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md) §0b“三极性登记／双 ledger 汇报”；当前说明坐标＝[`REASONING_METHOD.md`](../../项目说明/REASONING_METHOD.md) 同名条目与 [`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) §五“三极性不可混极／双 ledger／终审归精确本体”。上述正典共同承载 construct-then-verify 的使用边界；具体含义一律回正典读取。 |
| **使用隔离登记** | 必要投影、充分限制与精确语义保持正交使用权限，不得跨极消费；尤其充分限制可比真规则更严，只能用于构造合法 witness，绝不能 lower 成上界侧必要条件。上下界两账只有在同一命题身份与同一前提根下相遇，才允许报告 optimal。 |
| **独立重发现** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) 第三轮“双向逼近真实可行域”段独立重发现。 |
| **效力边界** | `non_authorizing / research_governance`；本条只登记正典已有使用权限的未来线约束、指针、作用域标签与独立重发现关系，不复制三极本体，不改变现行 solver 或 checker。 |

## 架构假设（可证伪，非约束）

以下三项只登记推理外环的经验赌注与证伪路径，不属于 A1–A9 设计约束，不因登记获得 authority。

| 假设 | 第三轮出处 | 可测代理 | 证伪实验归属 | 失败时退线 |
|---|---|---|---|---|
| **语义可压缩性** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) §九“语义可压缩性”。 | 在冻结 corpus 与 holdout 上，少量不变量、规范形或计数定理对 pose、binding、route-state、interface signature 与未关闭目标区域的压缩比例，以及 holdout 复验率。 | Phase -1 之后的定理／规范形专项实验；Phase -1 不直接检验本项。 | 停止押注通用语义压缩，只保留局部已验规则与 exact search。 |
| **接口可压缩性** | 同文 §九“接口可压缩性”。 | 冻结抽样框中，下游失败被压缩为可复用族级理由而非点状 nogood 的比例、每次反馈消除的候选空间、holdout 复用率与三态触达分布。 | Phase -1 直接检验。 | 保留点状反馈与精确下游验证，不把接口压缩当作扩线依据。 |
| **构造可分解性** | 同文 §九“构造可分解性”。 | 冻结 corpus 中由充分安全模块或规范骨架拼出候选的覆盖率、拼装后残余自由与 exact checker 通过率。 | Phase -1 之后的构造专项实验；Phase -1 不直接检验本项。 | 不强推模块化构造器，退回 whole-layout 构造／搜索加精确终验。 |

Phase -1 只直接检验接口可压缩性；即使该项通过，也不得外推为语义可压缩性与构造可分解性同时通过。
