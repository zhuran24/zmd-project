# 推理外环设计约束登记

> **生效条件：** 推理外环若立线，则约束其设计。
> **现行义务边界：** 本登记对现行树零新增义务。
> **owner 拍板边界：** owner 点头的是登记动作，内容未逐项拍板。
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
| **效力边界** | 约束对象＝推理外环若立线后的上下文身份、复用与迁移；生效条件＝该线获得 owner 立项裁决。上下文必须表达假设集合的子集关系、单调提升与迁移；hash 只确认字节身份，不得代替假设代数。 |
| **已有本体指针** | redesign 线对同一“假设／上下文同一性”问题已采用 semantics 拆分“先实验后拍板”：[`OWNER_DECISION_SUMMARY.md`](../rule_system_redesign_20260807/OWNER_DECISION_SUMMARY.md) 头部 2026-08-13 状态追记，以及 [`DECISION-SEMANTICS-SPLIT-EXPERIMENT-FIRST-20260813`](../../../data/knowledge/decisions.jsonl)。两线不得分头各自重设计假设代数。 |

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
| **出处** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) 第三轮。 |
| **效力** | `non_authorizing / research_governance`。 |
| **效力边界** | 约束对象＝推理外环若立线后的上界／必要条件生产器；生效条件＝该线获得 owner 立项裁决。本条只登记既有本体指针，不复制本体。 |
| **已有本体指针** | 权威本体＝[落地时 `00_master_roadmap.md` 归档](../../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md) §0b“等式挖矿”；当前说明坐标＝[`REASONING_METHOD.md`](../../项目说明/REASONING_METHOD.md)“干净房间外部收编”第 5 项；[`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) §四提供同义入口并回指该权威本体。**注记：外部评审第三轮独立重发现。** |

## A6　残余自由为一阶验收量

| 栏 | 登记 |
|---|---|
| **出处** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) 第三轮。 |
| **效力** | `non_authorizing / research_governance`。 |
| **效力边界** | 约束对象＝推理外环若立线后的实验与架构验收；生效条件＝该线获得 owner 立项裁决。被迫性收益为一阶，运行时间为二阶；本条只登记既有本体指针，不复制本体。 |
| **已有本体指针** | 权威本体＝[落地时 `00_master_roadmap.md` 归档](../../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md) §0b“自由两源／用计算购买被迫性”；当前说明坐标＝[`REASONING_METHOD.md`](../../项目说明/REASONING_METHOD.md) v2.7“理论根基”；[`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) §一提供同义入口并回指该权威本体。**注记：外部评审第三轮独立重发现。** |

## A7　接口可压缩性进入死因谱分析

| 栏 | 登记 |
|---|---|
| **出处** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) 第三轮。 |
| **效力** | `non_authorizing / research_governance`。 |
| **效力边界** | 约束对象＝推理外环若立线后的 Phase -1 死因谱实验；生效条件＝该线获得 owner 立项裁决。分析必须纳入接口可压缩性，即下游一次失败能向上游传回多少候选空间信息的通信复杂度框架；本条只登记本体指针与独立重发现关系。 |
| **已有本体指针** | 权威本体＝[落地时 `00_master_roadmap.md` 归档](../../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md) §0b“补记⑧／补记⑧续”；当前说明坐标＝[`REASONING_METHOD.md`](../../项目说明/REASONING_METHOD.md) 同名两节与 [`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) §六。Phase -1 的 untracked 收束来源＝`.artifacts/solver_rethink_20260808/CONVERGENCE_9_9F_92.md` §5.3。**注记：外部评审第三轮独立重发现。** |

## A8　残余核引擎去中心化

| 栏 | 登记 |
|---|---|
| **出处** | [`round3_semantic_compression_dual_loop_and_residual_freedom_review.md`](round3_semantic_compression_dual_loop_and_residual_freedom_review.md) 第三轮，§十；[`round2_mathematical_shape_and_proof_complexity_review.md`](round2_mathematical_shape_and_proof_complexity_review.md) 第二轮提供“CP-SAT 处理残余核”的前置判断。 |
| **效力** | `non_authorizing / research_governance`。 |
| **效力边界** | 约束对象＝推理外环若立线后的残余核引擎选择；生效条件＝该线获得 owner 立项裁决。CP-SAT 只能是收尾引擎之一，不得被规定为唯一内层；引擎按残余问题的证明语言与结构选择。 |
| **已有本体指针** | [`22_project_journey_plain_language.md`](../../项目说明/22_project_journey_plain_language.md)“五轮攻坚”第 4 轮：front-clear 数学规约经对抗审查站住，紧凑模型仍令三个负锚点全部 `UNKNOWN`，原文判词即“数学赢了，求解器输了”。此处只把该 tracked 案例提升为未来推理外环的引擎去中心化约束，不改变现行 solver。 |
