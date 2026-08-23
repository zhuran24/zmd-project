# 当前开放问题

> 本页由 claim ledger 与 `data/knowledge/topics.json` 自动生成；禁止手工修改。
> 账本审阅日：`2026-08-18`；源摘要：`sha256:e60cead0a5729937f7a56b17d64f5e26530bde73944412cef43672c268ea959c`。

本页只列 `status=open` 的稳定 claim。它不是全部未来工作，也不把“尚未证明”解释成“不可能”；阶段顺序见手工维护的 ROADMAP，当前事实仍以 CURRENT 和各自机器 authority 为准。

## 总览

| Claim | 标题 | Scope | 相关主题 |
|---|---|---|---|
| [`CLAIM-CERTIFIED-EXISTENCE-OPEN-20260823`](#claim-certified-existence-open-20260823) | 现行语义下 whole-layout 认证级存在性仍为 OPEN | six-predicate；whole-layout-witness；current-candidate-pool；three-arm-baseline | [`TOPIC-AUTHORITY-AND-CURRENT-STATE`](<TOPIC_INDEX.md#topic-authority-and-current-state>)<br>[`TOPIC-WITNESS-AND-LOWER-BOUND`](<TOPIC_INDEX.md#topic-witness-and-lower-bound>) |
| [`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](#claim-generic-cp-sat-separation-impossibility-open) | 通用 CP-SAT 传播不能替代领域分离的正式命题仍开放 | cp-sat；generic-propagation；domain-separation | [`TOPIC-SELECTION-SEPARATION-AND-CUTS`](<TOPIC_INDEX.md#topic-selection-separation-and-cuts>) |
| [`CLAIM-P2-MIN-SIDE-UPPER-OPEN`](#claim-p2-min-side-upper-open) | P2.0 的 min_side 上界仍未建立 | p2_0；max_lex-area-min_side；certification-gap | [`TOPIC-P2-THROUGHPUT`](<TOPIC_INDEX.md#topic-p2-throughput>) |

<a id="claim-certified-existence-open-20260823"></a>
## 现行语义下 whole-layout 认证级存在性仍为 OPEN

- **Claim ID：** `CLAIM-CERTIFIED-EXISTENCE-OPEN-20260823`
- **状态：** `open`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_ledger_state`
- **更新时间：** `2026-08-23`

当前没有被账本接受的完整可行布局或 whole-layout witness。binding↔routing 枚举截停已于 2026-08-23 解除，供三臂判别的基线臂使用；在新 witness 通过当前验收链前，lower ledger 仍为空。

- **适用范围：** six-predicate；whole-layout-witness；current-candidate-pool；three-arm-baseline

- **成立前提：** witness 必须经过当前 HEAD/input-pinned 验收链；UNKNOWN、超时以及解除截停本身都没有可行或不可行语义

- **直接后果：** 不得把 master feasible 写成整例 feasible；下界继续记为 L=absent；binding↔routing 枚举可供三臂判别的基线臂继续推进

- **明确不推出：** 全问题不可行；不存在可行布局；上界 U 已可达；解除截停已经产生完整 witness 或三臂判词

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT；CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818

- **取代 claim：** CLAIM-CERTIFIED-EXISTENCE-OPEN

- **权威源：** data/solutions/exact_full_scale_status.json；docs/research/witness_constructor_20260717/07_routing_aware/README.md；docs/research/witness_constructor_20260717/OWNER_AUTHORITY_COMPANION_20260823.md
- **关联决定：** DECISION-RESEARCH-THREE-ARM-ALL-APPROVED-20260823

- **有效性事件：** `semantic_replacement`
- **受影响层：** documentation；research_strategy
- **判定依据：** owner_adjudication
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** successor 保留 whole-layout existence OPEN，并将 binding↔routing 枚举截停更新为 2026-08-23 已解除。

- **证据：** [data/solutions/exact_full_scale_status.json](<../data/solutions/exact_full_scale_status.json>)〔checked-in durable exact status〕；[docs/research/witness_constructor_20260717/07_routing_aware/README.md](<research/witness_constructor_20260717/07_routing_aware/README.md>)〔latest tracked witness-construction line〕；[docs/research/witness_constructor_20260717/OWNER_AUTHORITY_COMPANION_20260823.md](<research/witness_constructor_20260717/OWNER_AUTHORITY_COMPANION_20260823.md>)〔owner ruling companion for the binding↔routing enumeration stop release〕

- **相关主题：** [`TOPIC-AUTHORITY-AND-CURRENT-STATE`](<TOPIC_INDEX.md#topic-authority-and-current-state>)；[`TOPIC-WITNESS-AND-LOWER-BOUND`](<TOPIC_INDEX.md#topic-witness-and-lower-bound>)


<a id="claim-generic-cp-sat-separation-impossibility-open"></a>
## 通用 CP-SAT 传播不能替代领域分离的正式命题仍开放

- **Claim ID：** `CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`
- **状态：** `open`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `none`
- **更新时间：** `2026-08-11`

当前已审材料没有一条 claim 同时明确指定通用 CP-SAT 传播系统、输入族、搜索/预算口径和目标分离，并正式证明该系统不能得到领域策略得到的分离。AB16 是非识别性实验，SMM、band22 与边界格数账证明领域结论本身，但都不构成 generic-propagation impossibility theorem。

- **适用范围：** cp-sat；generic-propagation；domain-separation

- **成立前提：** 正式不可能性必须指定传播闭包与允许的搜索动作；实验零激活和预算删失不能替代不可分离证明；领域证明与 solver 能力下界是不同命题

- **直接后果：** 知识账本继续把领域分离实例与 generic impossibility 分开计数；后续研究需建立 formal baseline 或受控可识别对照；当前 formal generic-propagation evidence 计数保持为零

- **明确不推出：** CP-SAT 一定能够得到相同结论；领域 cut 没有价值；AB16 已经证明某方更强

- **依赖 claim：** CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT；CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS

- **权威源：** docs/research/noncert_cuts_ab16_20260724/03_execution_record.md；docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md

- **条件处置：** `inconclusive`
- **操作效果：** experiment_boundary；scope_boundary
- **一般性：** `research_process`
- **solver 关系：** `experimental_cut`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review
- **分类注：** formal 证据仍为 none；该 claim 本身登记开放义务。

- **推导角色：** `open_obligation`
- **数学推导族：** closure_search
- **验证方式：** adversarial_review

- **目标阶段：** `knowledge_only`
- **候选来源：** `implicit_combinatorial`
- **选择方式：** not_applicable
- **验证方式：** none
- **完备性：** `open`
- **消费方式：** knowledge_only
- **基线比较：** `non_identifying`
- **分离注：** 尚无 formal baseline comparison。

- **证据：** [docs/research/noncert_cuts_ab16_20260724/03_execution_record.md](<research/noncert_cuts_ab16_20260724/03_execution_record.md>)〔budget-censored non-identifying execution record〕；[docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md](<research/rule_system_redesign_20260807/FINAL_DESIGN.md>)〔domain closure and pairwise incompleteness boundary〕；[.artifacts/solver_rethink_20260808/VELOCITY_RECALIBRATION_20260808.md](<../.artifacts/solver_rethink_20260808/VELOCITY_RECALIBRATION_20260808.md>)〔reviewed capability-gap and AB16 recalibration〕（工作区可选工件）

- **相关主题：** [`TOPIC-SELECTION-SEPARATION-AND-CUTS`](<TOPIC_INDEX.md#topic-selection-separation-and-cuts>)


<a id="claim-p2-min-side-upper-open"></a>
## P2.0 的 min_side 上界仍未建立

- **Claim ID：** `CLAIM-P2-MIN-SIDE-UPPER-OPEN`
- **状态：** `open`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `none`
- **更新时间：** `2026-08-11`

现役 P2.0 定理只闭合 max_lex(area,min_side) 的面积主坐标上界 A≤1167；在 area=U_A 层上用于闭合第二坐标的 min_side 上界 U_S 尚未建立。即使以后获得面积 1167 的完整 witness，也不能仅凭面积相等认证完整 lex 最优。

- **适用范围：** p2_0；max_lex-area-min_side；certification-gap

- **成立前提：** lex 认证必须在同一语义下分别闭合 area 主坐标与 min_side 次坐标；CLAIM-P2-AREA-BOUND-1167 只提供面积主坐标上界

- **直接后果：** P2.0 完整 lex 闭合需要新增阶段 S：在 area=U_A 条件下证明 min_side≤U_S；任何“面积上界等于见证面积即已全局 lex 最优”的表述都必须被阻断

- **明确不推出：** A≤1167 不成立；存在面积 1167 witness；六谓词与 P2.0 的上下界可以跨语义拼接；min_side 上界不存在，只是当前尚未建立

- **依赖 claim：** CLAIM-P2-AREA-BOUND-1167

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md

- **条件处置：** `inconclusive`
- **操作效果：** scope_boundary
- **一般性：** `model_domain`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** adversarial_review；owner_adjudication
- **分类注：** 这是显式开放义务，不是对面积上界的反驳。

- **推导角色：** `open_obligation`
- **数学推导族：** lex_band_enumeration；research_ledger
- **验证方式：** paper_derivation；adversarial_review

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔明确声明 min_side 维度未触碰，并禁止跨语义拼接上界〕

- **相关主题：** [`TOPIC-P2-THROUGHPUT`](<TOPIC_INDEX.md#topic-p2-throughput>)


完整 claim 结构见 [CATALOG](<CATALOG.md>)；按主题浏览见 [TOPIC_INDEX](<TOPIC_INDEX.md>)；阶段安排见 [ROADMAP](<项目说明/ROADMAP.md>)；唯一现态见 [CURRENT](<CURRENT.md>)。
