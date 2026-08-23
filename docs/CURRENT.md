# ZMD 当前知识状态

> 本页由 `devtools/build_knowledge_docs.py` 自动生成，禁止手工修改。
> 机器状态从冻结规则、义务、gate 与 exact-status 文件直接读取；研究结论从稳定 ID 账本投影。
> 账本人工审阅日：`2026-08-18`；源摘要：`sha256:e60cead0a5729937f7a56b17d64f5e26530bde73944412cef43672c268ea959c`。

## 权威边界

本页只是查询入口，不会高于它引用的源。不同源各自管辖不同问题，发生冲突时回到对应源文件：

1. [PROJECT_LOCK.md](<../PROJECT_LOCK.md>)：certified exactness、命题 P、冻结身份与发布边界。
2. [docs/项目说明/01_overview.md](<项目说明/01_overview.md>)：六个 gating 谓词的外延与 CERTIFIED 命题。
3. [docs/项目说明/30_research_charter.md](<项目说明/30_research_charter.md>)：PROJECT_LOCK.md 之下的研究方向、立项基线、完成判据与当前押注唯一可写真源。
4. [rules/canonical_rules.json](<../rules/canonical_rules.json>)：当前 canonical 游戏规则、admissibility 与空矩形语义。
5. [data/proof_obligations/p1_2_proof_obligations.json](<../data/proof_obligations/p1_2_proof_obligations.json>)：P1.2 fail-closed 机器义务、proof-bearing sink 与 source/hash floor。
6. [data/review_gates/phase_1_2_spike_close.json](<../data/review_gates/phase_1_2_spike_close.json>)：当前 owner-only phase gate；测试、Markdown 与 receipt 均不能替代 owner 决定。
7. [data/solutions/exact_full_scale_status.json](<../data/solutions/exact_full_scale_status.json>)：checked-in full-scale exact 结果状态与阻断检查。
8. [data/knowledge/claims.jsonl](<../data/knowledge/claims.jsonl>)：具有稳定 ID、作用域、前提、后果和证据的 claim 账本。
9. [data/knowledge/decisions.jsonl](<../data/knowledge/decisions.jsonl>)：非授权、append-only 的 owner/governance 决定查询登记；每条记录必须指向外部权威真源，本文件不能授权。
10. [data/knowledge/backfill_triage.json](<../data/knowledge/backfill_triage.json>)：未获 current review 的 dossier 长尾分诊；只保证 inventory coverage，不授予语义结论。
11. [data/knowledge/topics.json](<../data/knowledge/topics.json>)：稳定主题到 claim、dossier topic 与术语的导航坐标。
12. [data/knowledge/terminology.json](<../data/knowledge/terminology.json>)：核心术语、别名与禁止混同边界。

## 认证问题面

| 项目 | 当前机器值 |
|---|---|
| canonical rules 版本 | `1.2.0` |
| 网格 | `70×70` |
| 目标 | `max_lex_area_min_side` |
| 候选最短边门槛 | `6` |
| 空矩形语义 | `no_occupant_of_any_kind` |
| mandatory 实例数 | `266` |
| 机器源 | [rules/canonical_rules.json](<../rules/canonical_rules.json>)；[data/preprocessed/mandatory_exact_instances.json](<../data/preprocessed/mandatory_exact_instances.json>) |

## 阶段门与证明义务

- **P1.2 gate：** `closed_manual_owner_decision`，机器更新时间 `2026-08-21`，review anchor `v99_p1_2_close_kernel_sealing`。
- **当前 owner 决定：** `owner-p1-2-reclose-20260806`，由 `zhuran24` 于 `2026-08-06` 作出。
- **下一阶段入口：** `P1.3 production master integration (machine compatibility id: p1_3b)`，`allowed=true`。
- **clean-review 计数：** `maintained_outside_repo`；仓库不从 receipt 推导计数，receipt 也不能打开下一阶段。
- **P1.2 义务集：** `active_fail_closed_contract`，更新时间 `2026-08-20`，共 `15` 条，anchor `v99_p1_2_close_kernel_sealing`。
- **机器源：** [data/review_gates/phase_1_2_spike_close.json](<../data/review_gates/phase_1_2_spike_close.json>)；[data/proof_obligations/p1_2_proof_obligations.json](<../data/proof_obligations/p1_2_proof_obligations.json>)。

## Checked-in durable exact 状态快照

本段逐字读取仓内 resolver 输出，不表示生成知识页时重新运行过 resolver；必须连同它自己的生成时间阅读。

- **状态：** `open`。
- **best_certified_result：** `null`。
- **当前 hash 可续跑：** `false`。
- **阻断检查：** `15` 项。
- **checked-in resolver 时间：** `2026-04-17T10:17:39Z`。
- **机器源：** [data/solutions/exact_full_scale_status.json](<../data/solutions/exact_full_scale_status.json>)。

## Certified 命题边界

### certified active scope 仅含单一 70×70 基地

- **Claim ID：** `CLAIM-ACTIVE-SCOPE-SINGLE-BASE`
- **状态：** `current`
- **权威层：** `machine`
- **权威依据：** `machine_verified`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-11`

当前 certified active scope 只有 70×70 的 valley4_protocol_core；其余已知 IndustrialPlanner 基地保持 future_scope，任何结论都不得自动外推。

- **适用范围：** certified_exact；valley4_protocol_core；70x70

- **成立前提：** PROJECT_LOCK.md 的 IndustrialPlanner Active Scope 未被后续 owner 决定改写

- **直接后果：** 当前 proof、witness、上界与发布叙述必须显式限制在该单基地范围内

- **明确不推出：** 其他六个基地具有相同可行性、最优值或性能特征

- **权威源：** PROJECT_LOCK.md
- **机器验收器：** `project_lock_active_scope`

- **证据：** [PROJECT_LOCK.md](<../PROJECT_LOCK.md>)〔scope authority〕

### CERTIFIED 的命题边界是六谓词与 lex 最优

- **Claim ID：** `CLAIM-CERTIFIED-THEOREM-SCOPE`
- **状态：** `current`
- **权威层：** `machine`
- **权威依据：** `machine_verified`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-11`

在冻结输入和已登记 admissibility 下，production CERTIFIED 只证明六个 gating 谓词成立，并证明 max_lex(area, min_side) 的 lex 最优性。吞吐、带宽、离散容量流与其他明确列入 OUT-OF-SCOPE 的性质不在该命题内。

- **适用范围：** certified_exact；proposition_p；max_lex_area_min_side

- **成立前提：** 使用当前冻结 canonical 输入、proof-bearing sink 与发布链；候选满足 min_side admissibility

- **直接后果：** 任何 CERTIFIED 叙述必须同时携带命题 P 的作用域；P2.0 吞吐结论必须另账书写

- **明确不推出：** 吞吐可行；稳态产量达标；游戏全部规则都被建模；P2.0 最优

- **依赖 claim：** CLAIM-ACTIVE-SCOPE-SINGLE-BASE

- **权威源：** PROJECT_LOCK.md
- **机器验收器：** `project_lock_certified_scope`

- **证据：** [PROJECT_LOCK.md](<../PROJECT_LOCK.md>)〔release and theorem authority〕；[docs/项目说明/01_overview.md](<项目说明/01_overview.md>)〔six-predicate definition〕

### 空矩形采用 no_occupant_of_any_kind 严格语义

- **Claim ID：** `CLAIM-EMPTY-RECTANGLE-STRICT`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `rules_semantics`
- **更新时间：** `2026-08-11`

目标空矩形内不得与任何占用物相交，包括设施机身、电杆、传送带、交叉/桥组件以及其他物流部件；早先允许 routing component 进入矩形的宽松解释已经作废。

- **适用范围：** canonical_rules；empty_rectangle；all_occupants

- **成立前提：** rules/canonical_rules.json 的 emptiness 字段与 owner adjudication 保持冻结身份

- **直接后果：** 候选生成、终端验证与相关研究引理必须使用完全空地语义

- **明确不推出：** 历史宽松语义下的运行结果仍然有效；仅机身为空即可满足空矩形谓词

- **取代 claim：** CLAIM-EMPTY-RECTANGLE-ROUTING-ALLOWED-SUPERSEDED

- **权威源：** rules/canonical_rules.json；docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md
- **关联决定：** DECISION-EMPTY-RECTANGLE-STRICT-20260805

- **推导角色：** `definition`
- **数学推导族：** empty_rectangle_geometry
- **验证方式：** authority_admission；machine_source_projection

- **有效性事件：** `semantic_replacement`
- **受影响层：** canonical_semantics；model_encoding；documentation
- **判定依据：** owner_adjudication；incident_replay
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** 规则定义已经写入 canonical source；依赖宽松语义的正向见证仍需单独重验。

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔frozen semantic authority〕；[docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md](<research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md>)〔owner adjudication record〕；[.artifacts/ghost_strict_fix_20260805](<../.artifacts/ghost_strict_fix_20260805>)〔local implementation repair, mutation and reseal receipts〕（工作区可选工件）

### 六个 model-stricter face 是完整性与认证作用域欠账

- **Claim ID：** `CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-11`

canonical rules 当前登记六个“认证模型比已裁决游戏语义更严格”的面。只要其余模型忠实，这些限制不会制造假阳性可行性；但它们不会自动保持全游戏 max_lex 最优。每个被排除面都必须成为显式 certification-scope restriction，或由独立的 WLOG / completeness proof 覆盖。

- **适用范围：** certified-model-domain；full-game-optimality；model-stricter-faces

- **成立前提：** rules/canonical_rules.json 的 model_stricter_faces 与 completeness 条款保持现行 authority；其余模型部分对声明作用域忠实

- **直接后果：** 全游戏最优性叙述必须逐面核销六项欠账；新发现的过严面必须先登记，再用于 certified solve 或最优性叙事

- **明确不推出：** 六个过严面都应立即解除；受限模型中的可行布局不满足游戏语义；登记表本身已经给出 completeness proof

- **依赖 claim：** CLAIM-CERTIFIED-THEOREM-SCOPE

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260807/RESEAL_MANIFEST.md；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `scope_shifted`
- **操作效果：** scope_boundary；constraint_selection
- **一般性：** `model_domain`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit；adversarial_review；owner_adjudication
- **分类注：** 这是一张模型域欠账总账，不是通用传播能力下界。

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔current model-stricter ledger authority〕；[docs/research/canonical_batch_20260807/RESEAL_MANIFEST.md](<research/canonical_batch_20260807/RESEAL_MANIFEST.md>)〔first sealed ledger batch〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔completeness scan and sixth-face correction〕

### 1×1 item admission port 的省略是显式认证作用域限制

- **Claim ID：** `CLAIM-ADMISSION-PORT-OMISSION-SCOPE-RESTRICTION`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-11`

游戏 v1.1 中存在带 item filtering 的 1×1 admission port，但 released model 故意不建模。几何等价与配额出界不足以证明所有混流布局都可无损去除过滤行为；在缺少 layout-preserving completeness transformation 时，该省略只是显式 certification-scope restriction。

- **适用范围：** routing-rules；item-admission-port；certification-scope

- **成立前提：** released candidate pool 与 predicate 当前尚未消费 admission-port filtering；没有独立 WLOG / completeness transformation；rate lemma 的分配前提并非由普通 certificate 自动履行

- **直接后果：** 若任何 predicate 落地后禁止了只有 filtering port 能实现的行为，当前豁免 authority 当场失效并须重裁；de-mix 禁令不得引用该省略作为无条件正当性

- **明确不推出：** 必须立即把 admission port 纳入模型；过滤行为在当前 frozen instance 必然改变最优值；rate lemma 在所有合法布局都成立

- **依赖 claim：** CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT；CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `scope_shifted`
- **操作效果：** pre_model_exclusion；scope_boundary
- **一般性：** `game_semantics`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit；adversarial_review；owner_adjudication

- **目标阶段：** `pre_model`
- **候选来源：** `declared_inventory`
- **选择方式：** manual_targeting
- **验证方式：** none
- **完备性：** `open`
- **消费方式：** model_omission
- **基线比较：** `formal`
- **分离注：** 这里记录的是显式 scope restriction，不是 proof-backed safe omission。

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔current omission scope authority〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔sixth-face adjudication and lapsed-authority trigger〕

### warehouse bridge 排除只由冻结产量目标下的条件式生产线论证支撑

- **Claim ID：** `CLAIM-WAREHOUSE-BRIDGE-EXCLUSION-TARGET-CONDITIONAL`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-11`

warehouse bridge 是真实游戏机制，但现行模型排除通过仓库重新发射中间品的 routing shortcut。当前正当性是绑定于 3.0/2.75-line 冻结生产目标的 production-line argument，不是 axiom-kernel 定理；在形式化 completeness proof 之前，full-game optimality 必须把它当显式 scope restriction。

- **适用范围：** routing-connectivity；warehouse-bridge；frozen-production-targets

- **成立前提：** 3.0 valley_battery / 2.75 qiaoyu_capsule 生产目标保持不变；现行 production-line capacity argument 未被新的 owner adjudication supersede

- **直接后果：** 生产目标变化时必须重新裁决 warehouse bridge 排除；完整游戏最优性不能只靠当前 target-conditional argument

- **明确不推出：** warehouse bridge 在游戏中不存在；该桥在当前目标下一定能改善解；排除该桥会制造假阳性可行性

- **依赖 claim：** CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT

- **权威源：** rules/canonical_rules.json；docs/research/rules_audit_20260718/00_owner_adjudications_and_rule_corrections.md

- **条件处置：** `scope_shifted`
- **操作效果：** pre_model_exclusion；scope_boundary
- **一般性：** `frozen_instance`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** owner_adjudication；targeted_derivation

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔current warehouse bridge exclusion authority〕；[docs/research/rules_audit_20260718/00_owner_adjudications_and_rule_corrections.md](<research/rules_audit_20260718/00_owner_adjudications_and_rule_corrections.md>)〔owner production-line argument〕

### binding slot 单商品模型不能表达 wired warehouse 输入的多商品吸收

- **Claim ID：** `CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-11`

binding 层把每个 port slot 绑定为恰好一种商品；游戏语义允许 wired warehouse-line 的 protocol-core 输入同时吸收多种已登记商品。因此 certified scope 当前显式限制为“每个 wired warehouse-line input port 只携带一种商品”，除非补出独立 completeness proof。

- **适用范围：** binding-layer；port-slot-typing；wired-warehouse-input

- **成立前提：** 现行 binding generic-input contract 保持 slot-single-commodity；protocol core 仍是唯一 wired warehouse input side

- **直接后果：** 不能把一个 core port 吃两种终品的布局自动纳入完整模型域；任何 2-4 lanes 等缺口量化只能在 rate lemma 前提全部单独履行时使用

- **明确不推出：** protocol core 游戏语义只允许单商品输入；该表达缺口必然改变当前冻结实例最优值

- **依赖 claim：** CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT；CLAIM-MIXED-TERMINAL-TRIPARTITION；CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `scope_shifted`
- **操作效果：** constraint_selection；scope_boundary
- **一般性：** `model_domain`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit；owner_adjudication

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔port commodity scope authority〕；[docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md](<research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md>)〔binding expressiveness adjudication〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔conditional gap wording〕

### 空矩形 admissibility 的最小边长为 6

- **Claim ID：** `CLAIM-EMPTY-RECTANGLE-MIN-SIDE-ADMISSIBILITY-SIX`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `rules_semantics`
- **更新时间：** `2026-08-14`

canonical empty-rectangle admissibility 要求 min_side >= 6；任何边长小于 6 的矩形不属于当前 certified objective 的 admissible domain。

- **适用范围：** canonical_rules；empty_rectangle；min_side_admissibility

- **成立前提：** rules/canonical_rules.json 的 globals.empty_rectangle.min_side_admissibility 保持为整数 6

- **直接后果：** 候选生成、upper/lower ledger 和发布叙述必须使用相同 admissibility floor

- **明确不推出：** 边长 6 的矩形必然可行；min_side=6 已达到全局最优；该阈值适用于未来未裁定的规则版本

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT

- **权威源：** rules/canonical_rules.json；PROJECT_LOCK.md

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔frozen min-side admissibility source〕；[PROJECT_LOCK.md](<../PROJECT_LOCK.md>)〔certified publication boundary for min_side〕

### 游戏连通量词是逐 commodity 的双向 source/sink 可达

- **Claim ID：** `CLAIM-CONNECTIVITY-QUANTIFIER-PER-COMMODITY-SOURCE-SINK`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `rules_semantics`
- **更新时间：** `2026-08-14`

Predicate 5 的 connectivity_quantifier 是：逐 commodity，每个 SINK front 从某个 source front 可达，并且每个 SOURCE front 能到达某个 sink front；同 commodity 允许多个独立连通岛。

- **适用范围：** canonical_rules；routing_connectivity；per_commodity

- **成立前提：** rules/canonical_rules.json 的 semantics.connectivity_quantifier 保持当前 owner-adjudicated statement

- **直接后果：** 模型或证明若增加 no-orphan、single-spanning 或 selected-source 条件，必须作为更严格作用域单独登记

- **明确不推出：** 同 commodity 必须形成单一 spanning component；任意连通岛满足吞吐需求；routing connectivity 本身证明带宽或稳态产量；附加 no-orphan 条件属于游戏量词本身

- **权威源：** rules/canonical_rules.json；PROJECT_LOCK.md

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔frozen connectivity quantifier source〕；[PROJECT_LOCK.md](<../PROJECT_LOCK.md>)〔certified routing proposition boundary〕

## Checked-in 求解结果

### 现行语义下 whole-layout 认证级存在性仍为 OPEN

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

### checked-in durable CERTIFIED 结果当前不存在

- **Claim ID：** `CLAIM-DURABLE-CERTIFIED-RESULT-ABSENT`
- **状态：** `current`
- **权威层：** `machine`
- **权威依据：** `machine_verified`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_ledger_state`
- **更新时间：** `2026-08-14`

当前 tracked exact_full_scale_status 为 OPEN，best_certified_result 为 null，且列出未闭合 blocking checks；仓库中没有可由该 checked-in machine source 支持的 durable CERTIFIED end state。当前 tracked tree 未包含 data/blueprints/；这是该 OPEN 形态下的正常状态。

- **适用范围：** checked-in-status；durable-certified；current-git-tree

- **成立前提：** data/solutions/exact_full_scale_status.json 是当前 checked-in exact status machine source；best_certified_result=null 且 blocking_check_ids 非空

- **直接后果：** 不得把研究 receipt、master incumbent 或局部 witness 写成 durable CERTIFIED；当前状态页必须显式保持 OPEN

- **明确不推出：** 不存在完整可行布局；认证级存在性已经被证明为不可行；research lower ledger 必然为空；未来不能产生 CERTIFIED

- **依赖 claim：** CLAIM-CERTIFIED-THEOREM-SCOPE

- **权威源：** data/solutions/exact_full_scale_status.json
- **机器验收器：** `exact_full_scale_durable_certified_absent`

- **证据：** [data/solutions/exact_full_scale_status.json](<../data/solutions/exact_full_scale_status.json>)〔tracked durable exact-status source〕；[PROJECT_LOCK.md](<../PROJECT_LOCK.md>)〔sole durable CERTIFIED mint and publication boundary〕

## 六谓词研究账本

### 六谓词 research 条件上界收紧为 U=(1170,30)

- **Claim ID：** `CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-18`

在 current 六谓词、70×70 冻结实例与 research-only 口径下，按 lexicographic maximize (empty_rectangle_area,min_side) 比较，所有得分严格大于 (1170,30) 的 admissible strict empty rectangle 均被排除，因此当前条件性 research upper 为 U=(1170,30)，L=absent，production_certified=false。配置 set-packing 安全松弛与纯有理对偶证书关闭 18 个归一化 minimal roots 中的 17 个；剩余 17×69 root 及其转置依赖 CLAIM-STRICT-HOLE-AVOIDS-X1-Y1 关闭。

- **适用范围：** six-predicate；research-upper-ledger；strict-empty-rectangle；current-frozen-instance；lexicographic-area-min-side

- **成立前提：** 目标顺序为先最大化 empty_rectangle_area、再最大化 min_side 的 lexicographic order；current strict instance 的 weighted incidence 总量 738、单个外部 body-free access cell 容量上界 4、body/access 共享预算 1320 与 final-input allowance +2 保持既有命题口径；配置松弛只保留真实二维 body nonoverlap 与 multiplicity，并舍弃地图边界、placement、供电、routing、storage_box、protocol-core inputs 及其他全局冲突，因此 contact support 是安全上界；lex>(1170,30) 的 18 个归一化 minimal roots 完整；其中 17 根满足 wh+ceil((738-U)/4)>1320；长度 69 的区间在 70 轴上必含坐标 1，且 CLAIM-STRICT-HOLE-AVOIDS-X1-Y1 对 17×69 及转置适用

- **直接后果：** 同一六谓词 research ledger 的条件性上界由 U=(1188,18) 严格收紧为 U=(1170,30)；所有 lex>(1170,30) 的 strict-hole 尺寸可在声明口径内作为 research-only pre-model exclusion 使用；CLAIM-SIX-PREDICATE-RESEARCH-LEDGER 退为 superseded 历史 before-state

- **明确不推出：** 存在或可达到得分 (1170,30) 的布局；任何 lower bound、global optimum 或完整 witness；production、certified、release、supervisor 或 publisher authority；P2.0 第七谓词吞吐语义下的上界发生变化；storage_box 或 protocol-core inputs 已进入配置域；任何 superset 扩域必须重新证明；P0 前沿图顶部已经按新上界重建

- **依赖 claim：** CLAIM-BODY-ACCESS-BUDGET-1320；CLAIM-CERTIFIED-THEOREM-SCOPE；CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4；CLAIM-R4-MARKED-INCIDENCE-TOTAL-110；CLAIM-STRICT-HOLE-AVOIDS-X1-Y1

- **取代 claim：** CLAIM-SIX-PREDICATE-RESEARCH-LEDGER

- **权威源：** docs/research/solver_reasoning_outer_loop_reviews_20260815/LEDGER_RECONCILIATION_RECEIPT_CFG_RELAXATION_UPPER_20260818.json

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** zero_slack_audit；formal_proof；adversarial_review
- **分类注：** ①"≤"方向的枚举层由 46,278 配置封口于 23×51,其余 16 根余量 9-115 由清单级对偶证书覆盖(清单有双实现对拍但无逐根物理封口);②规格常数(738/÷4/1320/+2)按既有命题消费未独立重审;③扩域禁令:storage_box 与 protocol-core inputs 不属当前命题,任何扩域须按 superset 重证。 下游待办：P0 前沿投影的顶部改写由独立后继批处理，本批不重跑前沿图。

- **推导角色：** `ledger_projection`
- **数学推导族：** research_ledger；lex_band_enumeration；boundary_packing；local_access_capacity；budget_composition；integer_rounding；empty_rectangle_geometry
- **验证方式：** exact_enumeration；optimization_certificate；independent_recomputation；adversarial_review；authority_admission

- **目标阶段：** `pre_model`
- **候选来源：** `explicit_finite`
- **选择方式：** finite_enumeration
- **验证方式：** direct_arithmetic；exact_enumeration；independent_validator；proof_object
- **完备性：** `proved_for_declared_domain`
- **消费方式：** pre_model_filter；objective_bound
- **基线比较：** `formal`
- **分离注：** The 18 normalized lex-band roots are closed only for the declared current six-predicate configuration domain; storage_box and protocol-core input supersets are excluded.

- **有效性事件：** `semantic_replacement`
- **受影响层：** proof_argument；documentation
- **判定依据：** independent_recomputation；proof_replay
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** 该 ID 以五层验证后的严格 strengthening 接续同一六谓词 research ledger slot；旧 U=(1188,18) 只保留为 canonical before-state。

- **证据：** [.artifacts/cfg_relaxation_impl_A_20260817/REPORT.md](<../.artifacts/cfg_relaxation_impl_A_20260817/REPORT.md>)〔evidence layer 1A: independent implementation A, 54/54 OPTIMAL with all frozen targets MATCH〕（工作区可选工件）；[.artifacts/cfg_relaxation_impl_B_20260817/REPORT.md](<../.artifacts/cfg_relaxation_impl_B_20260817/REPORT.md>)〔evidence layer 1B: independent implementation B, 61/61 OPTIMAL with all acceptance targets MATCH; joint raw support is insensitive to the free/noncorner mark diagnostic difference〕（工作区可选工件）；[.artifacts/cfg_relaxation_certificates_20260818/REPORT.md](<../.artifacts/cfg_relaxation_certificates_20260818/REPORT.md>)〔evidence layers 2 and 3: 34 pure-Fraction dual certificates over both A/B families plus NEGATIVE_CONTROLS{,_B}.json with 204/204 rejected mutations, including rehashed-forger variants〕（工作区可选工件）；[.artifacts/cfg_relaxation_enum_closure_23x51_20260818/REPORT.md](<../.artifacts/cfg_relaxation_enum_closure_23x51_20260818/REPORT.md>)〔evidence layers 4 and 5: 46,278-configuration physical enumeration closure at 23×51, A/B violations 0, 5/5 negative controls PASS, 81/81 SHA receipt, and heterogeneous final review PASS with no blocking finding at frozen verifier SHA 87adec142d4bdad7240714c94d1c74a5e60de85169c7b52595dc04d47ca716aa〕（工作区可选工件）；[docs/research/solver_reasoning_outer_loop_reviews_20260815/LEDGER_RECONCILIATION_RECEIPT_CFG_RELAXATION_UPPER_20260818.json](<research/solver_reasoning_outer_loop_reviews_20260815/LEDGER_RECONCILIATION_RECEIPT_CFG_RELAXATION_UPPER_20260818.json>)〔tracked consumption-point reconciliation receipt: canonical before-state U=(1188,18), relation WEAKER_CURRENT, five-layer file hashes, four-root dossier mapping, allowed effects and non-implications〕

### SMM4 把旧 2084 band 与两个 SMM orientations 组合为完整 2086 band

- **Claim ID：** `CLAIM-SMM4-LEX-BAND-COMPOSITION-2086`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-14`

SMM4 composition gate 独立枚举确认 lex>(1188,18) 的完整 oriented band 有 2086 个 selectors，并且恰分解为旧 lex>(1188,22) 的 2084-orientation UNSAT band 与差集 {(22,54),(54,22)} 的 2-selector SMM-209 UNSAT。detached verifier 与 immutable closeout 才授权 research upper 更新。

- **适用范围：** smm4；lex-band-composition；research-upper

- **成立前提：** CLAIM-R4-LEX-BAND-2084-UNSAT 成立且其快照/receipt identity 闭合；CLAIM-SMM-209-EXCLUDES-22X54 成立；composition gate 对旧 band、candidate band 与差集做独立完整枚举

- **直接后果：** 完整 lex>(1188,18) research band 被覆盖；经 detached receipt 与 closeout 授权，六谓词 research upper ledger 可写为 U=(1188,18)

- **明确不推出：** (1188,18) 可达；global optimality、whole-instance infeasibility 或任何 lower bound；内部 formal receipt、composition gate 或旧 adapter 单独具有 upper update authority；production CERTIFIED

- **依赖 claim：** CLAIM-R4-LEX-BAND-2084-UNSAT；CLAIM-SMM-209-EXCLUDES-22X54

- **权威源：** docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md；docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/01_authority_contract.md；docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/03_execution_record.md

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** formal_proof；adversarial_review

- **推导角色：** `composite_theorem`
- **数学推导族：** lex_band_enumeration；finite_pb_proof；research_ledger
- **验证方式：** exact_enumeration；roundingsat_veripb；independent_recomputation；authority_admission

- **证据：** [docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md](<research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md>)〔current SMM4 composition and authority boundary〕；[docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/01_authority_contract.md](<research/b1_sidewise_marked_membrane_fresh_authority_20260727/01_authority_contract.md>)〔2084 plus two equals 2086 composition contract〕；[docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/03_execution_record.md](<research/b1_sidewise_marked_membrane_fresh_authority_20260727/03_execution_record.md>)〔detached verification and immutable closeout record〕

### SMM-209 排除 22×54 与 54×22

- **Claim ID：** `CLAIM-SMM-209-EXCLUDES-22X54`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-07-27`

对 body-cell-empty 的 22×54 矩形，ordinary membrane 与 entity-max marked membrane 给出 T_in+M_in≤209。由外部 weighted incidences 与每格容量账可推出至少 133 个外部 access cells，而 22×54+133=1321>1320，因此两个 orientation 均被排除。

- **适用范围：** strict-empty-rectangle；22x54；54x22；smm-209

- **成立前提：** T_in≤124 的旧 ordinary membrane authority；八个 directed endpoints 的 entity-max top-eight budget 为 19；外部 access cell 的局部权重上限为 4；required bodies 与至少九根电杆占用 3580 格

- **直接后果：** lex>(1188,18) 相对旧 lex>(1188,22) 新增的两个 orientation 被关闭；经 fresh authority 闭包后支持 U=(1188,18)

- **明确不推出：** 纸面证明单独授权上界更新；存在 1188×18 witness；整例不可行；production CERTIFIED

- **依赖 claim：** CLAIM-BODY-ACCESS-BUDGET-1320；CLAIM-SMM-OUTSIDE-ACCESS-LOWER-133

- **权威源：** docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md；docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md；docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；bound_tightening
- **一般性：** `parameterized_family`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof；adversarial_review
- **分类注：** 纸面不等式排除目标尺寸；未证明某个指定通用传播闭包无法得到同样结论。

- **推导角色：** `composite_theorem`
- **数学推导族：** empty_rectangle_geometry；budget_composition；integer_rounding
- **验证方式：** paper_derivation；independent_recomputation；adversarial_review

- **目标阶段：** `candidate_generation`
- **候选来源：** `explicit_finite`
- **选择方式：** manual_targeting；goal_backward_search
- **验证方式：** direct_arithmetic
- **完备性：** `proved_for_declared_domain`
- **消费方式：** candidate_filter；objective_bound
- **基线比较：** `formal`
- **分离注：** 对指定两 orientation 完成领域证明，但没有 generic propagation 对照定理。

- **证据：** [docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md](<research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md>)〔paper necessity proof〕；[docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md](<research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md>)〔adversarial review〕；[docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md](<research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md>)〔fresh authority closeout〕

## P2.0 独立研究账本

### P2.0 吞吐语义的当前独立条件账本

- **Claim ID：** `CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260822`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-22`

在 P2.0 第七谓词语义下，无条件面积上界为 A≤1167；单层口径给出 A≤1015，但依赖待闭合的 OB6 条件；电杆下界 P≥9。max_lex 的 min_side 次坐标上界仍未建立。该账本与当前六谓词 U=(1170,30) 并存且禁止混写；U=(1188,18) 只作为六谓词账本收紧前的 superseded before-state 保留。

- **适用范围：** p2_0；throughput-conservation；research-upper-bound

- **成立前提：** production_targets、严格空地、吞吐守恒与循环稳态；A≤1015 额外依赖 OB6 单层/交叉密度条件

- **直接后果：** P2.0 语义下可使用 A≤1167；满足 OB6 时可使用条件界 A≤1015；电杆数满足 P≥9；完整 lex 闭合仍需在 area=U_A 层建立 min_side 上界

- **明确不推出：** 六谓词上界发生变化；第七谓词已经证明改变全局最优解；A≤1015 是无条件结论；P2.0 的 max_lex 两个坐标已经闭合

- **依赖 claim：** CLAIM-P2-AREA-BOUND-1167；CLAIM-P2-MIN-SIDE-UPPER-OPEN；CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015；CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818

- **取代 claim：** CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md；docs/research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md

- **推导角色：** `ledger_projection`
- **数学推导族：** research_ledger；area_accounting；throughput_capacity
- **验证方式：** authority_admission；machine_source_projection

- **有效性事件：** `semantic_replacement`
- **受影响层：** proof_argument；documentation
- **判定依据：** independent_recomputation；proof_replay
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** 该 ID 接续 CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814，将独立 P2.0 条件账本与当前六谓词 research upper U=(1170,30) 对账；旧 U=(1188,18) 仅保留为 historical before-state。

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔P2.0 area-bound authority〕；[docs/research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md](<research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md>)〔specialized-line owner-facing adjudication summary〕；[.artifacts/p2_0_refresh_20260805/area_bound_work](<../.artifacts/p2_0_refresh_20260805/area_bound_work>)〔local receipts and review root〕（工作区可选工件）；[docs/research/solver_reasoning_outer_loop_reviews_20260815/LEDGER_RECONCILIATION_RECEIPT_CFG_RELAXATION_UPPER_20260818.json](<research/solver_reasoning_outer_loop_reviews_20260815/LEDGER_RECONCILIATION_RECEIPT_CFG_RELAXATION_UPPER_20260818.json>)〔tracked six-predicate ledger reconciliation with canonical after-state U=(1170,30)〕

### P2.0 无条件容量计数面积上界为 A≤1167

- **Claim ID：** `CLAIM-P2-AREA-BOUND-1167`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-11`

在 P2.0 第七谓词的列明前提下，网格分账给出 A≤1356-4P-R；route-state lower bound L≥305 与每格最多两层 state 给出 R≥ceil(L/2)≥153，电杆下界给出 P≥9。因此任何 P2.0-feasible layout 满足 A≤1356-36-153=1167。

- **适用范围：** p2_0；throughput-conservation；unconditional-area-bound

- **成立前提：** strict empty rectangle 与 mandatory-body partition 采用报告前提栏的 current semantics；CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305 成立；CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE 成立；每个网格 cell 最多承载 ground/elevated 两个 physical route states

- **直接后果：** P2.0 research upper ledger 可无条件使用 A≤1167；任何超过 1167 的 strict-hole candidate 在 P2.0 scope 内被排除

- **明确不推出：** 六谓词 research upper ledger 发生变化；P2.0 optimum 等于 1167；A=1167 可达或存在完整 routing witness；单层条件界 A≤1015 已无条件成立

- **依赖 claim：** CLAIM-P2-AREA-ACCOUNTING-1356；CLAIM-P2-ROUTE-FOOTPRINT-LOWER-153；CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** area_accounting；route_footprint；power_coverage；integer_rounding
- **验证方式：** paper_derivation；independent_recomputation；adversarial_review

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔P2.0 theorem 1, premise ledger and five-round adversarial correction〕

### P2.0 的 min_side 上界仍未建立

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

### P2.0 单层口径条件式面积上界为 A≤1015

- **Claim ID：** `CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-11`

若额外满足 OB6 的单层条件 X=0，使 route footprint R≥L，而非仅 R≥ceil(L/2)，则由 L≥305、P≥9 与 A≤1356-4P-R 得 A≤1356-36-305=1015。该结论必须始终携带【条件·待 OB6】标签。

- **适用范围：** p2_0；single-layer；conditional-area-bound

- **成立前提：** CLAIM-P2-AREA-BOUND-1167 的共同分账前提成立；交叉格数 X=0，等价于单层 route footprint R≥L；OB6 尚未被无条件证明

- **直接后果：** 在明确验证单层条件的候选族中可使用 A≤1015；相对无条件 1167 具有 152 格的潜在压降

- **明确不推出：** 所有可行 P2.0 布局都是单层；无条件 research upper ledger 已降到 1015；双层垂直交叉机制不可用

- **依赖 claim：** CLAIM-P2-AREA-ACCOUNTING-1356；CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305；CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md

- **条件处置：** `conditional`
- **操作效果：** candidate_pruning；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof
- **分类注：** 必须先 discharge X=0/OB6；不能作为全局无条件上界引用。

- **推导角色：** `composite_theorem`
- **数学推导族：** area_accounting；route_footprint；power_coverage
- **验证方式：** paper_derivation；independent_recomputation；adversarial_review
- **推导注：** 该节点携带 X=0/OB6 条件，不能进入无条件 ledger。

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔conditional single-layer branch and OB6 boundary〕

### P2.0 当前实例中荞麦与砂叶分支不可消除

- **Claim ID：** `CLAIM-P2-BUCKWHEAT-SANDLEAF-MANDATORY-BRANCH`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-07`

在当前 mandatory 台数、每个运行机器经当前运输网取货、仓库桥排除、端口容量与精确计数语义下，荞麦与砂叶两类循环都必须发生分支；该结论不依赖把同一 operation 的占空错误地均摊到每台机器。

- **适用范围：** p2_0；buckwheat-cycle；sandleaf-cycle；current-instance

- **成立前提：** 当前 mandatory 台数不变；所有运行机器从建模运输网获得输入；仓库桥不在模型中；端口容量和精确槽计数语义不变

- **直接后果：** 无分支路由对这两类作物不可行；两类循环至少各产生一段不超过半条带的细流

- **明确不推出：** 必然违反物理纯流谓词 P1；两种商品必然在同一组件共址；这是游戏的一般定理

- **权威源：** docs/research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md；docs/research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；constraint_strengthening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** branch_counting；throughput_capacity
- **验证方式：** paper_derivation；adversarial_review；source_recomputation

- **证据：** [docs/research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md](<research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md>)〔owner-facing corrected result〕；[docs/research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md](<research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md>)〔adversarial rejudgment and staircase witnesses〕

### 钢块免分流前提下，六台制瓶机被迫为 5 满 1 半

- **Claim ID：** `CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

条件于钢块物流免分流、六台制瓶机全开、钢瓶总占空 11/2、带容量 1 件每 tick 且配方每次消耗 2 件钢块，每台占空只能落在 {1/2,1}，总量唯一确定为五台满速、一台半速。

- **适用范围：** p2_0；steel-block；molding-bottle；split-free

- **成立前提：** 钢块物流免分流；六台制瓶机全开；总占空为 11/2；每台输入道容量与 2:1 配方把可用占空压到 1/2 或 1

- **直接后果：** 免分流布局中恰有一台制瓶机只使用一个钢块输入口；钢块耗侧可以形成 11 条满速输入道

- **明确不推出：** 无条件下台间占空唯一；所有 operation 都具有两档占空；该结构已经构造出完整 P2.0 布局

- **取代 claim：** CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED

- **权威源：** docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md；docs/research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md

- **条件处置：** `conditional`
- **操作效果：** candidate_pruning；constraint_strengthening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof
- **分类注：** 只有在钢块免分流等列明前提同时成立时才可使用。

- **推导角色：** `composite_theorem`
- **数学推导族：** branch_counting；integer_rounding
- **验证方式：** paper_derivation；source_recomputation

- **目标阶段：** `candidate_generation`
- **候选来源：** `implicit_combinatorial`
- **选择方式：** manual_targeting
- **验证方式：** direct_arithmetic
- **完备性：** `proved_for_declared_domain`
- **消费方式：** candidate_filter
- **基线比较：** `formal`
- **分离注：** 只有完整条件集同时成立时，档位塌点才可消费。

- **有效性事件：** `scope_correction`
- **受影响层：** proof_argument
- **判定依据：** counterexample；independent_recomputation
- **复用策略：** `unaffected_under_premises`
- **修复状态：** `revalidated`
- **时间作用域：** `universal_claim`
- **有效性注：** 替代关系只修正 steel-block 分流推理；条件定理不能外推成无条件台间占空规律。

- **证据：** [docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md](<research/rule_system_redesign_20260807/FINAL_DESIGN.md>)〔registered five-premise collapse theorem〕；[docs/research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md](<research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md>)〔machine-checked staircase witness〕

## 当前结构性推理与发现方法

### generic output 槽账 52=52，46 个边界 raw 口全部被迫激活

- **Claim ID：** `CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED`
- **状态：** `current`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-05`

当前冻结实例的 generic output 需求为 52 个离散槽；可供给槽恰为 46 个 boundary raw output 加 protocol core 的 6 个 raw output，共 52。零余量使 46 个边界 raw 口全部必须激活。

- **适用范围：** strict-empty-rectangle；boundary-ports；generic-output-slots

- **成立前提：** 冻结 mandatory 实例和 generic I/O 需求保持不变；每个 boundary raw provider 只有一个物理 output slot；protocol core 提供六个 raw output slots

- **直接后果：** 任何让一个边界 raw 口失活的候选都会立即破坏槽数等式；边界 front 不能被空矩形吞掉后再靠闲置该端口规避

- **明确不推出：** 已经构造出全局 routing witness；所有 52 个槽具有唯一绑定；该局部账本单独证明整例不可行

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT

- **权威源：** data/preprocessed/generic_io_requirements.json；data/preprocessed/mandatory_exact_instances.json；rules/canonical_rules.json；src/placement/placement_generator.py

- **条件处置：** `discharged`
- **操作效果：** pre_model_exclusion；candidate_pruning
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** zero_slack_audit；targeted_derivation
- **分类注：** 零余量槽账给出直接的实例级排除；未提交通用 CP-SAT 传播不可替代证明。

- **推导角色：** `atomic_lemma`
- **数学推导族：** slot_saturation
- **验证方式：** source_recomputation；exact_enumeration

- **证据：** [data/preprocessed/generic_io_requirements.json](<../data/preprocessed/generic_io_requirements.json>)〔frozen generic-output demand ledger〕；[data/preprocessed/mandatory_exact_instances.json](<../data/preprocessed/mandatory_exact_instances.json>)〔mandatory boundary-provider census〕；[rules/canonical_rules.json](<../rules/canonical_rules.json>)〔protocol-core output cap and boundary template authority〕；[src/placement/placement_generator.py](<../src/placement/placement_generator.py>)〔one-slot boundary candidate generation〕；[.artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md](<../.artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md>)〔strict-hole probe §8.2 slot-ledger derivation〕（工作区可选工件）

### 严格空矩形不得触碰 x=1 列或 y=1 行

- **Claim ID：** `CLAIM-STRICT-HOLE-AVOIDS-X1-Y1`
- **状态：** `current`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-05`

在当前冻结边界口几何和 52=52 零余量槽账下，x=1 列与 y=1 行分别钉有 23 个被迫激活的 front；全部边界铺法上最长无 front 连续段仅 3 格。由于 admissible 空矩形短边至少 6，任何触碰 x=1 或 y=1 的严格空矩形都会吞掉被迫 front。

- **适用范围：** strict-empty-rectangle；boundary-front-rails；current-frozen-instance

- **成立前提：** CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED 成立；min_side admissibility 为 6；边界 port/front 几何保持冻结

- **直接后果：** 候选生成和结构推理可把 x=1 与 y=1 作为禁碰轨道；band22 孔位分析不能复用这两条轨道

- **明确不推出：** x=2 或 y=2 也必然禁碰；所有远离边界轨道的孔位都可行；该结论对其他基地或不同边界口数量自动成立

- **依赖 claim：** CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED；CLAIM-EMPTY-RECTANGLE-STRICT

- **权威源：** src/placement/placement_generator.py；rules/canonical_rules.json

- **条件处置：** `discharged`
- **操作效果：** pre_model_exclusion；candidate_pruning
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** zero_slack_audit；solver_experiment；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** slot_saturation；boundary_packing；empty_rectangle_geometry
- **验证方式：** exact_enumeration；paper_derivation

- **证据：** [src/placement/placement_generator.py](<../src/placement/placement_generator.py>)〔boundary front-coordinate implementation〕；[rules/canonical_rules.json](<../rules/canonical_rules.json>)〔boundary template and empty-rectangle authority〕；[.artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md](<../.artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md>)〔Theorem A and exhaustive boundary-lane probe〕（工作区可选工件）

### 交付版 band22 V0-A 骨架与 strict hole 不相容

- **Claim ID：** `CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE`
- **状态：** `current`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

交付版 V0-A 固定布局中，逐格穷举得到的唯一 body/pole-free 6×7 或 7×6 孔位是 [1,6]×[51,57]；该孔触碰 x=1，而当前冻结边界口与 52=52 槽账已证明任何 admissible strict hole 都不能触碰 x=1 或 y=1。因此该固定 V0-A skeleton 不能满足 strict empty-rectangle 语义。

- **适用范围：** band22；v0-a-fixed-skeleton；strict-empty-rectangle

- **成立前提：** V0-A 的设施、电杆与路由坐标保持交付版本不变；CLAIM-STRICT-HOLE-AVOIDS-X1-Y1 成立；孔短边至少为 6，且 strict hole 内不得含 body、pole 或 transport component

- **直接后果：** 不得把该固定 V0-A skeleton 登记为 strict-hole witness；继续沿 band22 路线时必须改变布局或拓扑，而不能只在原骨架内平移孔位

- **明确不推出：** band22 范式一般层不可行；不存在改变带序或单列拓扑后的 strict witness；48<49 的 5×5 子模型账可以无条件推广到所有 band 变体

- **依赖 claim：** CLAIM-STRICT-HOLE-AVOIDS-X1-Y1

- **权威源：** docs/research/cleanroom_rederivation_20260718/27_band22_witness_delivery_20260804/band22_three_holes_repair_report.md

- **条件处置：** `discharged`
- **操作效果：** pre_model_exclusion；candidate_pruning
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** zero_slack_audit；solver_experiment；formal_proof
- **分类注：** 只排除交付版固定 skeleton；探针同时保留 band 范式一般层未死的边界。

- **推导角色：** `composite_theorem`
- **数学推导族：** empty_rectangle_geometry；boundary_packing
- **验证方式：** exact_enumeration；source_recomputation

- **目标阶段：** `pre_model`
- **候选来源：** `explicit_finite`
- **选择方式：** zero_slack_ranking；finite_enumeration
- **验证方式：** exact_enumeration；direct_arithmetic
- **完备性：** `proved_for_declared_domain`
- **消费方式：** pre_model_filter；candidate_filter
- **基线比较：** `formal`
- **分离注：** 穷尽的是固定 V0-A skeleton 内的孔位，不是整个 band22 范式。

- **证据：** [docs/research/cleanroom_rederivation_20260718/27_band22_witness_delivery_20260804/band22_three_holes_repair_report.md](<research/cleanroom_rederivation_20260718/27_band22_witness_delivery_20260804/band22_three_holes_repair_report.md>)〔tracked V0-A delivery plus strict-hole disqualification banner〕；[.artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md](<../.artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md>)〔coordinate reconstruction, unique-hole enumeration and Theorem A application〕（工作区可选工件）

### 当前冻结实例至少需要九根电杆

- **Claim ID：** `CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

当前 mandatory powered manufacturing bodies 的总面积为 3325。14-orbit nonnegative halo certificate 与独立装填复算给出单杆在该 charging argument 中最多承担 K=396 个 powered-body cells，因此任何可行布局满足 P≥ceil(3325/396)=9。

- **适用范围：** power-coverage；current-frozen-instance；single-base

- **成立前提：** current mandatory powered-body census 为 3325 格；power coverage 采用当前 12×12 intersection 语义；单杆容量 K=396 的 840-placement certificate/optimization 保持有效

- **直接后果：** 至少 36 个网格 cell 被 pole bodies 占用；R3/R4/SMM 与 P2.0 面积链可使用 P≥9

- **明确不推出：** 九根电杆足以覆盖某个完整布局；电杆位置或覆盖指派唯一；供电路由与其他设施几何已经可行

- **权威源：** docs/research/r3_upper_bound_pb_20260722/README.md；docs/research/r4_response_review_20260723/02_necessity_proof.md；docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；formal_proof；adversarial_review

- **推导角色：** `composite_theorem`
- **数学推导族：** power_coverage；integer_rounding
- **验证方式：** optimization_certificate；independent_recomputation；adversarial_review

- **证据：** [docs/research/r3_upper_bound_pb_20260722/README.md](<research/r3_upper_bound_pb_20260722/README.md>)〔14-orbit halo certificate and P>=9 derivation〕；[docs/research/r4_response_review_20260723/02_necessity_proof.md](<research/r4_response_review_20260723/02_necessity_proof.md>)〔independent R4 reconstruction of the shared pole lower bound〕；[docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔P2.0 K=396 optimization and independent SCIP cross-check〕

### ordinary membrane 给出 T_in≤w+h+48

- **Claim ID：** `CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

对当前 strict instance 中任一 body-disjoint axis-aligned rectangle R，令 S=w+h，则 manufacturing 与 boundary-port contact 的八类 census、full-contact excess 63、八个 directed endpoints 的 partial-contact allowance 24，再加 protocol core 与两个 final inputs 的安全 +5，给出 active terminal incidences inside R 的上界 T_in≤S+48。

- **适用范围：** ordinary-membrane；strict-empty-rectangle；current-frozen-instance

- **成立前提：** 当前 strict template census 与 628 active terminal incidences 不变；body-disjoint rectangle 不能同时接触同一 solid rectangular facility 的不同 sides；每个 directed rectangle endpoint 至多承载一个 partial contact

- **直接后果：** 外部 terminal incidences 至少为 580-S；为 R3、R4、B1-QMH 与 SMM-209 提供共同的 ordinary membrane 前件

- **明确不推出：** R 内 terminals 可以同时路由；marked membrane 或 sidewise refinement 自动成立；该不等式单独关闭任何当前 upper band

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT

- **权威源：** docs/research/r3_upper_bound_pb_20260722/README.md；docs/research/r4_response_review_20260723/02_necessity_proof.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；candidate_pruning
- **一般性：** `parameterized_family`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** ordinary_membrane；endpoint_budget
- **验证方式：** paper_derivation；exact_enumeration；adversarial_review

- **证据：** [docs/research/r3_upper_bound_pb_20260722/README.md](<research/r3_upper_bound_pb_20260722/README.md>)〔ordinary membrane census and S+48 derivation〕；[docs/research/r4_response_review_20260723/02_necessity_proof.md](<research/r4_response_review_20260723/02_necessity_proof.md>)〔independent reconstruction inside the admitted R4 chain〕

### R4 用 ordinary/marked 双账得到完整尺寸必要不等式

- **Claim ID：** `CLAIM-R4-NECESSARY-DIMENSION-INEQUALITY`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

对 normalized body-empty rectangle R，令 S=w+h、N 为 distinct outside access cells。所有 w 都满足 N≥ceil((580-S)/4)；当 w≥9 时还满足 N≥ceil((678-2S)/4)。结合 |R|+N≤1320，得到 w≥9 时 wh+max(ceil((580-S)/4),ceil((678-2S)/4))≤1320，w<9 时保留 ordinary branch。

- **适用范围：** r4；dimension-filter；strict-empty-rectangle

- **成立前提：** CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48 成立；CLAIM-R4-MARKED-INCIDENCE-TOTAL-110 与 CLAIM-R4-MARKED-MEMBRANE-BOUND-S12 成立；CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4 成立；CLAIM-BODY-ACCESS-BUDGET-1320 成立

- **直接后果：** 34×35、29×41 等 lex-better candidates 在纸面 necessary scan 中被排除；22×54 以 1188+132=1320 留作该 relaxation 的边界 survivor；为完整 R4 formal band 提供固定系数算术前件

- **明确不推出：** 22×54 可行或可达；full-span candidates 无需另行排除；纸面 scan 本身授权 research upper update

- **依赖 claim：** CLAIM-BODY-ACCESS-BUDGET-1320；CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48；CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4；CLAIM-R4-MARKED-MEMBRANE-BOUND-S12

- **权威源：** docs/research/r4_response_review_20260723/02_necessity_proof.md；docs/research/r4_response_review_20260723/03_independent_recomputation.md；docs/research/r4_response_review_20260723/04_adversarial_verdict.md

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；bound_tightening
- **一般性：** `parameterized_family`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** ordinary_membrane；marked_membrane；area_accounting；integer_rounding
- **验证方式：** paper_derivation；independent_recomputation；adversarial_review

- **证据：** [docs/research/r4_response_review_20260723/02_necessity_proof.md](<research/r4_response_review_20260723/02_necessity_proof.md>)〔paper necessity proof and complete normalized scan〕；[docs/research/r4_response_review_20260723/03_independent_recomputation.md](<research/r4_response_review_20260723/03_independent_recomputation.md>)〔independent exact-match dimension ledger〕；[docs/research/r4_response_review_20260723/04_adversarial_verdict.md](<research/r4_response_review_20260723/04_adversarial_verdict.md>)〔admission boundary for B1 encoder design〕

### 46 个 boundary bodies 强制 23+23，并排除 70 格 full-span hole

- **Claim ID：** `CLAIM-R4-BOUNDARY-23-23-FULL-SPAN-EXCLUSION`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

每个 required boundary body 在 left 或 bottom supported boundary 占连续三格；70 格边界非重叠最多容纳 23 个。当前恰有 46 个 required boundary bodies，因此两边各恰放 23 个并覆盖 69/70 格。短边至少六的 body-free rectangle 若 w=70 或 h=70，必在对应 supported boundary 上碰到已占格，故 full-span selector 不可行。

- **适用范围：** boundary-packing；full-span；strict-empty-rectangle

- **成立前提：** current instance 恰有 46 个 required boundary bodies；每个 boundary body 沿 supported boundary 占三连格且 bodies 不重叠；strict-hole 最小短边为 6

- **直接后果：** 任何 w=70 或 h=70 的 empty-rectangle candidate 可在建模前排除；R4 formal band 中 107 个 full-span selectors 可被显式 forbid

- **明确不推出：** 边界铺法唯一；非 full-span 尺寸可行；边界 front 的 x=1/y=1 禁轨结论无需 52=52 槽账

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT

- **权威源：** docs/research/r4_response_review_20260723/02_necessity_proof.md；docs/research/r4_response_review_20260723/03_independent_recomputation.md

- **条件处置：** `discharged`
- **操作效果：** pre_model_exclusion；candidate_pruning
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** zero_slack_audit；targeted_derivation；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** boundary_packing；empty_rectangle_geometry；integer_rounding
- **验证方式：** paper_derivation；independent_recomputation

- **证据：** [docs/research/r4_response_review_20260723/02_necessity_proof.md](<research/r4_response_review_20260723/02_necessity_proof.md>)〔23+23 packing and full-span proof〕；[docs/research/r4_response_review_20260723/03_independent_recomputation.md](<research/r4_response_review_20260723/03_independent_recomputation.md>)〔independent exact-match reconstruction〕

### 低余量审计可系统寻找被迫结构与领域不等式

- **Claim ID：** `CLAIM-ZERO-SLACK-AUDIT-METHOD`
- **状态：** `current`
- **权威层：** `descriptive`
- **权威依据：** `descriptive`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-07`

把面积、边界、台数容纳、端口槽位、覆盖、源汇、整除与模数等资源账逐行计算“容量−需求=余量”，再按余量升序排列。趋近零的行优先暴露被迫结构、可判性好的候选以及可能由两本账相乘得到的领域不等式。

- **适用范围：** research-method；domain-specific-propagation；candidate-discovery

- **成立前提：** 容量和需求必须来自同一语义与同一冻结实例；任何候选结论仍需独立证明、对抗审查与 authority admission

- **直接后果：** 新研究线可先生成可排序的余量审计表，而不是依赖偶然灵感；零余量行同时进入锚点清单和危险清单

- **明确不推出：** 低余量自动构成有效不等式；CP-SAT 通用传播一定无法推出候选；所有候选都值得进入 production

- **权威源：** docs/history/status/00_master_roadmap_pre_phase3_20260812.md；docs/项目说明/REASONING_METHOD.md；docs/research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md

- **条件处置：** `method_only`
- **操作效果：** discovery_method
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** zero_slack_audit
- **分类注：** 它是候选结论的系统发现法，不会自动赋予候选有效性或 authority。

- **推导角色：** `method`
- **数学推导族：** slack_audit
- **验证方式：** authority_admission

- **目标阶段：** `candidate_generation`
- **候选来源：** `declared_inventory`
- **选择方式：** zero_slack_ranking
- **验证方式：** none
- **完备性：** `heuristic`
- **消费方式：** knowledge_only
- **基线比较：** `none`
- **分离注：** 它系统排序候选，不承担候选有效性、完备性或 authority。

- **证据：** [docs/history/status/00_master_roadmap_pre_phase3_20260812.md](<history/status/00_master_roadmap_pre_phase3_20260812.md>)〔owner-accepted methodology ledger before Phase 3 split〕；[docs/项目说明/REASONING_METHOD.md](<项目说明/REASONING_METHOD.md>)〔current extracted methodology contract〕；[docs/research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md](<research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md>)〔independent first-principles convergence〕

### 研究线立项与完成必须绑定具名前沿、朴素基线和后继变化

- **Claim ID：** `CLAIM-RESEARCH-LINE-FRONTIER-BASELINE-EXIT-DISCIPLINE`
- **状态：** `current`
- **权威层：** `owner_decision`
- **权威依据：** `owner_decision`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-23`

每条研究线开工前必须声明要移动的具名前沿、同预算朴素基线以及继续、降级或停止条件；产出只有实际改变后继问题或后继决策才算完成。方法、工具与研究机器改良本身不自动计入项目进展。

- **适用范围：** research-governance；line-opening；baseline-comparison；completion-criterion

- **成立前提：** PROJECT_LOCK.md 的精确性契约、命题 P 与认证边界保持更高权威；研究所得仍须经过既有证明链与发布闸门才能成为认证结论

- **直接后果：** 新研究线必须在开工前写明前沿、基线与退出条件；精巧路线必须与同预算下直接推进同一前沿的朴素基线比较；文档落库或研究机器改良只有在改变后继问题、后继决策或提供具名前沿杠杆时才计为完成

- **明确不推出：** 当前押注板中的候 owner 裁事项已经获准点火；研究机器改良没有价值；朴素基线必须优于所有精巧路线；本纲领能够授予 production、certified 或 release authority

- **权威源：** docs/项目说明/30_research_charter.md

- **条件处置：** `method_only`
- **操作效果：** constraint_selection；discovery_method；experiment_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** owner_adjudication
- **分类注：** 该 claim 约束研究线的立项、比较与完成口径，不替任何具体路线提供数学或认证结论。

- **证据：** [docs/项目说明/30_research_charter.md](<项目说明/30_research_charter.md>)〔owner-approved research-direction, line-opening and completion charter〕

### 冻结实例中 storage-side boundary loader 被 141>139 格数账排除

- **Claim ID：** `CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

70×70 左边界与下边界并集只有 139 格；46 个 mandatory boundary pickup port 各占 3 格，共占 138 格。若 storage-side loader 同样受 left_or_bottom_boundary 规则约束且机身为 3×1，再放一个需 141 格，因此任何容纳当前 266 mandatory instances 的布局都放不下它。

- **适用范围：** frozen-instance；boundary-strip；storage-side-loader

- **成立前提：** 冻结生产目标仍要求 46 个 pickup ports；storage-side loader 遵守与 pickup port 相同的 left_or_bottom_boundary 规则；loader 机身为 3x1；网格为 70x70

- **直接后果：** 在该前提集内，未建模 loader 不会移除一个几何上可实现的 frozen-instance 行为；生产目标或边界规则变化时必须重新推导

- **明确不推出：** loader 在一般游戏布局中不可放置；storage-side 边界规则已由 owner 游戏实测裁决；该格数账是无条件规则语义

- **依赖 claim：** CLAIM-ACTIVE-SCOPE-SINGLE-BASE

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `discharged`
- **操作效果：** pre_model_exclusion；semantic_partition
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** zero_slack_audit；targeted_derivation；owner_adjudication
- **分类注：** 结论对列明前提已闭合，但前提之一来自 simulator 外推，变化即重推。

- **目标阶段：** `pre_model`
- **候选来源：** `declared_inventory`
- **选择方式：** manual_targeting；zero_slack_ranking
- **验证方式：** direct_arithmetic
- **完备性：** `proved_for_declared_domain`
- **消费方式：** model_omission；pre_model_filter
- **基线比较：** `formal`
- **分离注：** 只在列明冻结实例和边界前提内支持免建模。

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔conditional terminal-universe derivation〕；[docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md](<research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md>)〔boundary loader closure record〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔premise-set correction and audit〕

### intermediate pure-flow rate lemma 只覆盖等占空且最少车道的显式分配剖面

- **Claim ID：** `CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

在冻结满产、同 operation 各 mandatory machine 等占空、且每股流只占 ceil(rate/C) 条车道的剖面下，中间品非满载余量集合使任意两股余量之和都大于一条车道容量，因此两种中间品不能共享一条 lane。普通六谓词 certificate 不记录占空分配、实际车道数或速率，不能自动履行后两个前提。

- **适用范围：** rate-allocation-profile；intermediate-pure-flow；frozen-production-targets

- **成立前提：** 满产于冻结 3.0/2.75 production targets；同 operation 的 mandatory machines 采用等占空；每股 per-machine commodity stream 使用最少的 ceil(rate/C) 条 occupied lanes

- **直接后果：** 只有对具体布局单独给出所有前提证据时，才可用该引理缩小混流域；不能凭普通 CERTIFIED 结果排除 unequal-duty 或 lane-dilution 布局

- **明确不推出：** 所有合法布局都中间纯流；admission-port filtering 一般不需要；证书已经验证 throughput、lane occupancy 或 duty allocation

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260807/rate_lemma_recompute.receipt.txt；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `conditional`
- **操作效果：** candidate_pruning；constraint_strengthening
- **一般性：** `model_domain`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof；adversarial_review
- **分类注：** certificate 不履行占空与 lane-count 前提；这是条件式领域推理，不是 solver 通用传播下界。

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔current conditional lemma authority〕；[docs/research/canonical_batch_20260807/rate_lemma_recompute.receipt.txt](<research/canonical_batch_20260807/rate_lemma_recompute.receipt.txt>)〔machine recomputation receipt〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔precondition and usage-rule correction〕

## 选择、分离与消费机制边界

### pairwise 固定点不能证明规则闭包已饱和

- **Claim ID：** `CLAIM-PAIRWISE-CLOSURE-INCOMPLETE`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

对扫描器只做 pairwise 合取并仅回灌新结晶的设定，x≥0、y≥0、x+y≤−1 的任意两条都有非空连续可行域，因此第一轮没有新结晶；三条合取却为空。项目自身的 5 满 1 半结论还需要五条跨层前提共同塌点。因此 pairwise 零产出只能记为 PAIRWISE_FIXED_POINT_INCOMPLETE，不能写成饱和、无更多定理或子空间已扫尽。

- **适用范围：** reasoning-closure；pairwise-scan；derived-rules

- **成立前提：** 扫描只枚举两两组合；只有新结晶才进入回灌池；承重结论需要区分启发式发现与完备闭包

- **直接后果：** pairwise 扫描只作为猜想生成和优先级启发；承重闭包应交给对相应理论完备的 solver 或 proof checker；预算或深度截断必须保留 UNKNOWN / NOT_EXHAUSTIVE

- **明确不推出：** pairwise 扫描没有研究价值；所有高阶组合都必须无差别暴力枚举；5 满 1 半条件定理失效

- **依赖 claim：** CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL

- **权威源：** docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md

- **条件处置：** `refuted`
- **操作效果：** counterexample；scope_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** adversarial_review；formal_proof
- **分类注：** 反例推翻的是“pairwise 固定点即饱和”的停机解释。

- **推导角色：** `counterexample`
- **数学推导族：** closure_search
- **验证方式：** paper_derivation；counterexample；adversarial_review

- **目标阶段：** `knowledge_only`
- **候选来源：** `implicit_combinatorial`
- **选择方式：** pairwise_closure
- **验证方式：** counterexample
- **完备性：** `disproved`
- **消费方式：** knowledge_only
- **基线比较：** `formal`
- **分离注：** 被否证的是完备性声称，不是 pairwise 作为启发式的效用。

- **证据：** [docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md](<research/rule_system_redesign_20260807/FINAL_DESIGN.md>)〔three-premise counterexample, five-premise flagship and corrected stop states〕

### 候选发现与候选验证是两项独立能力

- **Claim ID：** `CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

能够验证一个给定 cut、(S,R) 或算式是否成立，不等于能够从巨大候选空间中找到有用候选。把正确的资源账配对关系直接写进 detector，只是把缺失的领域发现预装进检测器；cut framework 的 oracle/candidate producer 与独立 validator 因而必须分别登记、分别验收。

- **适用范围：** candidate-discovery；cut-validation；separation-architecture

- **成立前提：** 候选空间不由 validator 自身穷尽；候选有效性仍需独立重算或 proof object；领域账户配对不能以规则名存在为由假定已知

- **直接后果：** 每个机制必须分别说明候选来源、选择方式和验证方式；只接通 typed validator 不得宣称已拥有 autonomous separator；验收必须包含自主发现而非仅回放硬编码候选

- **明确不推出：** 所有候选都必须由人手提出；独立 validator 不重要；领域选择策略不能系统化

- **权威源：** docs/research/rule_system_redesign_20260807/REFUTE_rule_form.md；docs/research/history_toolchain_origin_20260709/03_design.md

- **条件处置：** `method_only`
- **操作效果：** discovery_method；scope_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit；adversarial_review
- **分类注：** 该边界用于防止“checker 已有”被扩写为“separator 已有”。

- **推导角色：** `method`
- **数学推导族：** closure_search
- **验证方式：** adversarial_review；source_recomputation

- **目标阶段：** `knowledge_only`
- **候选来源：** `supplied_candidate`
- **选择方式：** not_applicable
- **验证方式：** independent_validator
- **完备性：** `not_applicable`
- **消费方式：** knowledge_only
- **基线比较：** `formal`
- **分离注：** supplied-candidate validation 本身没有候选空间覆盖保证。

- **证据：** [docs/research/rule_system_redesign_20260807/REFUTE_rule_form.md](<research/rule_system_redesign_20260807/REFUTE_rule_form.md>)〔capacity-vs-arrival detector assumes the missing domain pairing〕；[docs/research/history_toolchain_origin_20260709/03_design.md](<research/history_toolchain_origin_20260709/03_design.md>)〔oracle is untrusted while validator is an independent trust boundary〕

### 前向完备性只能相对于声明片段定义

- **Claim ID：** `CLAIM-FORWARD-COMPLETENESS-RELATIVE-TO-DECLARED-FRAGMENT`
- **状态：** `current`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

“把所有新规则都推出”只有在声明的语句片段、冗余序和义务清单三元组内才是良定义命题。有限可枚举片段可以证明相对饱和；新语句形状和片段外义务仍然开放。solver-rethink v2 因此把在线主引擎收束为 query-driven，并把有限饱和降为离线考卷与原语覆盖体检。

- **适用范围：** reasoning-engine；forward-completeness；declared-fragment

- **成立前提：** 片段语言和冗余序被显式冻结；有限实例空间可枚举且推导格单调有限；片段外义务与新语句形状单独挂账

- **直接后果：** 完备性声明必须同时命名片段、冗余序与义务清单；在线预算耗尽不能冒充片段饱和；离线有限饱和可以作为旧战果重发现考卷

- **明确不推出：** solver-rethink 架构已获 production 批准；原语集具有绝对完备性；片段外不会出现新领域洞察

- **权威源：** .artifacts/solver_rethink_20260808/DESIGN_SEED.md；.artifacts/solver_rethink_20260808/DESIGN_DOC_v2.md

- **条件处置：** `method_only`
- **操作效果：** discovery_method；scope_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit；targeted_derivation
- **分类注：** 这是可复用的完备性口径，不是对未立线架构的批准。

- **推导角色：** `definition`
- **数学推导族：** closure_search
- **验证方式：** paper_derivation；adversarial_review

- **目标阶段：** `candidate_generation`
- **候选来源：** `explicit_finite`
- **选择方式：** goal_backward_search；finite_enumeration
- **验证方式：** complete_theory_solver
- **完备性：** `relative_to_declared_fragment`
- **消费方式：** knowledge_only
- **基线比较：** `formal`
- **分离注：** 有限片段的闭包与片段外开放义务必须分开记账。

- **证据：** [.artifacts/solver_rethink_20260808/DESIGN_SEED.md](<../.artifacts/solver_rethink_20260808/DESIGN_SEED.md>)〔relative completeness model and three-layer boundary〕（工作区可选工件）；[.artifacts/solver_rethink_20260808/DESIGN_DOC_v2.md](<../.artifacts/solver_rethink_20260808/DESIGN_DOC_v2.md>)〔query-driven online engine and offline finite saturation compromise〕（工作区可选工件）

### 只有被证明的预建模排除才支持安全免建模

- **Claim ID：** `CLAIM-PROVED-PREMODEL-EXCLUSION-PERMITS-MODEL-OMISSION`
- **状态：** `current`
- **权威层：** `descriptive`
- **权威依据：** `descriptive`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

对已点名元素，若一个作用域明确、前提可追踪的排除定理证明它在目标域内放不下、无益或可等价归约，则该定理可被消费为 pre-model filter 或 model omission；若只是不建模而没有 completeness transformation，则只能登记为 certification scope restriction。安全免建模是证明的后果，不是静默省略的理由。

- **适用范围：** model-on-demand；pre-model-exclusion；model-completeness

- **成立前提：** 元素已进入 inventory；排除命题的 scope、premises 和重推触发器已登记；模型省略与规则真语义的关系可被审计

- **直接后果：** agent 在省略模型变量前必须找到对应排除 claim 或显式 scope debt；排除前提变化时触发重推；建模成本可以按“先排除、证不出再建模”排序

- **明确不推出：** 任何未建模元素都自动无关；scope restriction 等价于安全排除；一个冻结实例排除可推广到一般游戏

- **依赖 claim：** CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE；CLAIM-ADMISSION-PORT-OMISSION-SCOPE-RESTRICTION

- **权威源：** docs/research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `method_only`
- **操作效果：** pre_model_exclusion；scope_boundary
- **一般性：** `research_process`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit；zero_slack_audit
- **分类注：** 该 claim 管消费协议，不替代具体排除定理。

- **推导角色：** `method`
- **数学推导族：** closure_search
- **验证方式：** source_recomputation；adversarial_review

- **目标阶段：** `pre_model`
- **候选来源：** `declared_inventory`
- **选择方式：** manual_targeting；zero_slack_ranking
- **验证方式：** direct_arithmetic；proof_object
- **完备性：** `relative_to_declared_fragment`
- **消费方式：** model_omission；pre_model_filter
- **基线比较：** `formal`
- **分离注：** 必须由具体 scoped claim 提供证明。

- **证据：** [docs/research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md](<research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md>)〔exclusion and model-completeness workflow〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔contrast between conditional exclusion and certification-scope omission〕

### typed cut 管道消费已知 cut，但不自动发现 cut

- **Claim ID：** `CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM`
- **状态：** `current`
- **权威层：** `machine`
- **权威依据：** `machine_verified`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

当前 typed registry、validate/compile、scope resolver 与 step_8 typed apply 能把已提供且通过验证的 CompiledCut 绑定并下译到 master。该管道的职责是接收、验证、解析和消费 cut；它本身不从候选空间自主生成有用 cut，也不改变 certified default-off 与 B6 owner-promotion 边界。

- **适用范围：** src-cuts；typed-pipeline；candidate-discovery

- **成立前提：** 输入 cut 或 envelope 已由 producer 提供；family plugin、snapshot 和 live scope 通过 fail-closed validation；production attach authority 仍由 owner gate 单独决定

- **直接后果：** 可复用现有 typed pipeline 作为领域判断的消费端；separator/oracle 必须作为独立 producer 验收；consumer 成功不等于 candidate coverage

- **明确不推出：** typed apply 已经是完整 separation oracle；production attach 已获授权；已知 cut 的效力或收敛性已经证明

- **依赖 claim：** CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS；CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS

- **权威源：** src/cuts/typed_platform.py；src/cuts/lifecycle.py
- **机器验收器：** `typed_cut_pipeline_contract`

- **条件处置：** `discharged`
- **操作效果：** constraint_selection；scope_boundary
- **一般性：** `model_domain`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit
- **分类注：** 实现边界已由源码复核；candidate producer 能力不在该管道内。

- **目标阶段：** `search_loop`
- **候选来源：** `supplied_candidate`
- **选择方式：** cut_registry_replay
- **验证方式：** independent_validator；terminal_replay
- **完备性：** `open`
- **消费方式：** model_constraint；diagnostic_only
- **基线比较：** `none`
- **分离注：** consumer 的存在不提供候选发现完备性。

- **证据：** [src/cuts/typed_platform.py](<../src/cuts/typed_platform.py>)〔typed registry and validate/compile implementation〕；[src/cuts/lifecycle.py](<../src/cuts/lifecycle.py>)〔sole resolver and typed step-8 apply path〕；[docs/research/history_toolchain_origin_20260709/03_design.md](<research/history_toolchain_origin_20260709/03_design.md>)〔original oracle/validator split〕；[docs/research/batch_ce_attach_host_20260712/02_prod_form_adaptation_batch_spec.md](<research/batch_ce_attach_host_20260712/02_prod_form_adaptation_batch_spec.md>)〔prod-form fail-closed attach boundary and mirror repair〕

### 分离实验必须记录 raw eligible events，不能只看 accepted cuts

- **Claim ID：** `CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

accepted/applied cut 计数为零同时兼容“没有可分离事件”“producer 未到达”“候选被上游 cap 截断”“validator 全拒绝”和“确实无效”等多种机制。要评价 separator，必须按 eligible scope 记录 raw violation/event、producer/validator/consumer 各阶段到达状态，并区分 NOT_REACHED、NOT_EVALUATED、REACHED_NO_EFFECT 与 EFFECT_NO_TERMINAL；否则零计数不能成为绿色科学结论。

- **适用范围：** separation-telemetry；solver-experiment；cut-framework

- **成立前提：** 事件口径在实验前冻结；raw event 与 accepted cut 分层计数；预算删失和未到达状态不被删样本

- **直接后果：** separator 验收必须报告 reachability funnel；零 accepted 不再自动解释成无违规或无价值；AB16/RAB 类实验应使用可识别遥测

- **明确不推出：** raw event 自动是有效 cut；历史 RAB 性能数字重新有效；观测到事件就证明 production soundness

- **依赖 claim：** CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT

- **权威源：** docs/research/rab_sep_promotion_20260716/04_front_clear_lift_design_20260716.md；docs/research/rab_sep_promotion_20260716/05_front_clear_lift_batch_execution_20260716.md

- **条件处置：** `method_only`
- **操作效果：** discovery_method；experiment_boundary
- **一般性：** `research_process`
- **solver 关系：** `experimental_cut`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；incident_review
- **分类注：** 遥测方法可复用，但不复活已被 front-offset 事故作废的历史效果数据。

- **目标阶段：** `search_loop`
- **候选来源：** `solver_events`
- **选择方式：** raw_event_separation
- **验证方式：** independent_validator
- **完备性：** `not_applicable`
- **消费方式：** diagnostic_only
- **基线比较：** `controlled`
- **分离注：** 识别性来自完整 funnel 和预注册对照，不来自单个 accepted counter。

- **证据：** [docs/research/rab_sep_promotion_20260716/04_front_clear_lift_design_20260716.md](<research/rab_sep_promotion_20260716/04_front_clear_lift_design_20260716.md>)〔raw empty-domain event counters and NOT_EVALUATED semantics〕；[docs/research/rab_sep_promotion_20260716/05_front_clear_lift_batch_execution_20260716.md](<research/rab_sep_promotion_20260716/05_front_clear_lift_batch_execution_20260716.md>)〔historical telemetry design plus invalidation boundary〕；[.artifacts/ab16_arms_20260802/EVAL.md](<../.artifacts/ab16_arms_20260802/EVAL.md>)〔16-arm generated/compiled/applied funnel and budget censoring〕（工作区可选工件）

### 通用 CP-SAT 传播不能替代领域分离的正式命题仍开放

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

### 预算耗尽必须返回 UNKNOWN，不能冒充固定点

- **Claim ID：** `CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

无论是规则组合扫描、query-driven 推理还是 solver 实验，只要终止原因是预算、深度上限或 producer 未到达，就不能陈述“已饱和”“无更多规则”或“没有可分离事件”。对应结果必须保留 UNKNOWN、NOT_EXHAUSTIVE、NOT_REACHED 或 NOT_EVALUATED，并让无条件结论 fail closed。

- **适用范围：** budget-censoring；closure-search；experiment-semantics

- **成立前提：** 终止原因被机器记录；预算截断与逻辑固定点是不同事件；无条件结论要求完备停机判据或完整 proof object

- **直接后果：** 所有扫描和实验报告显式输出 terminated_by；预算删失样本留在统计中；不完整搜索只能产 conditional 或 open ledger

- **明确不推出：** 预算搜索永远没有价值；UNKNOWN 等价于不可行；达到时间上限证明候选不存在

- **依赖 claim：** CLAIM-PAIRWISE-CLOSURE-INCOMPLETE；CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT

- **权威源：** docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md

- **条件处置：** `discharged`
- **操作效果：** experiment_boundary；scope_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** adversarial_review；solver_experiment
- **分类注：** 结论是结果语义边界，不是对任何具体候选的否定。

- **推导角色：** `method`
- **数学推导族：** closure_search
- **验证方式：** adversarial_review；source_recomputation

- **目标阶段：** `candidate_generation`
- **候选来源：** `implicit_combinatorial`
- **选择方式：** pairwise_closure；goal_backward_search
- **验证方式：** none
- **完备性：** `open`
- **消费方式：** diagnostic_only；knowledge_only
- **基线比较：** `none`
- **分离注：** 没有完备终止证据时，搜索覆盖保持 open。

- **证据：** [docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md](<research/rule_system_redesign_20260807/FINAL_DESIGN.md>)〔PAIRWISE_FIXED_POINT_INCOMPLETE, NOT_EXHAUSTIVE and UNKNOWN stop semantics〕；[.artifacts/solver_rethink_20260808/DESIGN_DOC_v2.md](<../.artifacts/solver_rethink_20260808/DESIGN_DOC_v2.md>)〔budget exhaustion returns UNKNOWN and is not a fixed point〕（工作区可选工件）

## 接收终端语义与模型约束选择

### frozen production line 单独履行了 protocol storage box 的逐次到达接受不变量

- **Claim ID：** `CLAIM-STORAGE-BOX-ACCEPTANCE-INVARIANT-FROZEN`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

class (2) storage box 一般是有界、可能拒绝到达的混流吸收器；但 frozen production line 上，3 个输入口在 10 秒 flush 周期内最多 15 次到达，静态容量为 6×50，且能到 storage line 的只有两种终品。owner 因此裁决 6-slot occupied blocking state 在该实例不可达，box 可作为合法 mixed-flow terminal。

- **适用范围：** frozen-instance；protocol-storage-box；mixed-terminal

- **成立前提：** box 获得 power 且 default-on flush 行为有效；6 个独立 slot group 每组容量 50；10 秒 flush 与 2 秒到达头距保持有效；frozen storage line 只接收两种终品

- **直接后果：** 该 frozen instance 可把 storage box 作为 class (2) 合法混流终点；其他布局必须重新逐次履行接受不变量

- **明确不推出：** class (2) 在所有布局都无条件安全；仅看 commodity type 数就足以判定不堵塞；cache、timing 与 flush 已成为 certified predicate

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `discharged`
- **操作效果：** semantic_permission；constraint_selection
- **一般性：** `frozen_instance`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；owner_adjudication；systematic_rules_audit

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔slot invariant and frozen-instance discharge authority〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔occupied-vs-full correction and owner disposition〕

### 混流接收终端分为 core、storage box 与 machine input 三类

- **Claim ID：** `CLAIM-MIXED-TERMINAL-TRIPARTITION`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `rules_semantics`
- **更新时间：** `2026-08-11`

canonical receiving-terminal tri-partition 仅覆盖有实体输入口、且 belt segment 在其上终止的设施：class (1) protocol-core wired warehouse inputs 对已登记商品混流无条件吸收；class (2) protocol storage box 只有在逐次到达接受不变量被单独履行时安全；class (3) machine inputs 因 recipe-blind intake 与不可逆占槽而不安全。output-only boundary pickup port 不属于接收终端。

- **适用范围：** mixed-commodity-flow；receiving-terminals；routing-rules

- **成立前提：** 使用当前 canonical axiom kernel 与 facility parameters；class (2) 接受性不由终端类别本身自动推出

- **直接后果：** destination-front constraint 的合法含义必须按终端类别选择；任何 mixed terminal 论证都必须说明它终止于哪一类端口

- **明确不推出：** belt 层禁止商品交织；所有 storage-box 布局都安全；machine input 具有配方过滤能力

- **依赖 claim：** CLAIM-STORAGE-BOX-ACCEPTANCE-INVARIANT-FROZEN

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `discharged`
- **操作效果：** semantic_partition；constraint_selection
- **一般性：** `game_semantics`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit；owner_adjudication

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔current terminal tri-partition authority〕；[docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md](<research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md>)〔terminal-class adjudication〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔class (2) precision correction〕

### destination-front 单商品排他必须按接收终端类别解释

- **Claim ID：** `CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-11`

routing 模型施加在接收 front cell 上的单商品排他，对 class (3) 机器输入是污染安全的保守编码；对 class (1) protocol-core 输入，以及已经单独履行 class (2) 接受不变量的 storage-box 执行，则比游戏语义更严格。

- **适用范围：** routing-layer；destination-front；mixed-terminal-classes

- **成立前提：** 使用 canonical terminal tri-partition；class (2) 是否安全由逐次到达接受不变量单独判断

- **直接后果：** 不能把 sink-front 排他无差别解释为所有接收终端的游戏规则；若依赖它排除 core/安全 box 混流，结论必须标注受限模型作用域

- **明确不推出：** 机器输入可以安全接收混流；class (2) 仅凭类型数量就自动安全；该模型面已经被解除

- **依赖 claim：** CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT；CLAIM-MIXED-TERMINAL-TRIPARTITION

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `scope_shifted`
- **操作效果：** constraint_selection；scope_boundary
- **一般性：** `game_semantics`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit；owner_adjudication

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔terminal-sensitive destination-front authority〕；[docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md](<research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md>)〔port-semantics adjudication package〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔model-stricter split and final wording〕

### source-front 单商品排他是已确认的过严模型面

- **Claim ID：** `CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-11`

owner 已裁决 output-door transit 在游戏中安全，因此 routing 模型对 source-front 施加的同类单商品排他比已裁决游戏语义更严格。任何解锁必须作为独立 sealed-face batch，现行模型仍保留该限制。

- **适用范围：** routing-layer；source-front；output-door-transit

- **成立前提：** 2026-08-06 owner port-semantics adjudication保持有效；现行 released model 尚未完成独立 unlock batch

- **直接后果：** 依赖 source-front 排他的最优性结论只覆盖受限模型域；后续解锁需要单独迁移、验证与 reseal

- **明确不推出：** source-front 排他已从生产模型删除；输出端任意混流都满足其他 routing 条件

- **依赖 claim：** CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `scope_shifted`
- **操作效果：** scope_boundary；constraint_selection
- **一般性：** `model_domain`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** owner_adjudication；systematic_rules_audit

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔current registered face〕；[docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md](<research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md>)〔owner port-semantics adjudication〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔ledger-preserving rewrite〕

### routing reverification 的附加严格面不改写游戏连通量词

- **Claim ID：** `CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT-BOUNDARY`
- **状态：** `current`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-14`

现行 routing reverification 除游戏层已裁决的 connectivity_quantifier 外，还要求 no-orphan 与 selected-source-reaches-sink。二者是模型更严格的附加条件；它们限制当前模型域，但不改变 canonical connectivity_quantifier 本身。

- **适用范围：** routing-reverification；connectivity-quantifier；certified-model-domain

- **成立前提：** canonical model_stricter_faces 登记保持现行；released reverifier 仍施加这两个附加条件

- **直接后果：** 依赖附加连通条件的排除只对受限模型域成立，除非另有 completeness proof

- **明确不推出：** 附加条件在工程上没有价值；游戏允许孤立组件满足任何 certified predicate；已经存在解除该面后的完整重证书；附加严格面改变了 adjudicated connectivity_quantifier 本身

- **依赖 claim：** CLAIM-CONNECTIVITY-QUANTIFIER-PER-COMMODITY-SOURCE-SINK；CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT

- **取代 claim：** CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT

- **权威源：** rules/canonical_rules.json；docs/research/canonical_batch_20260807/DEPENDENCY_VERIFICATION.md；docs/research/canonical_batch_20260808/DRAFT_DIFF.md

- **条件处置：** `scope_shifted`
- **操作效果：** constraint_strengthening；scope_boundary
- **一般性：** `model_domain`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** systematic_rules_audit；adversarial_review

- **有效性事件：** `scope_correction`
- **受影响层：** canonical_semantics；model_encoding；documentation
- **判定依据：** independent_recomputation；evidence_gap
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** successor 明确分开 canonical quantifier 与 conservative model face。

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔connectivity and model-stricter authority〕；[docs/research/canonical_batch_20260807/DEPENDENCY_VERIFICATION.md](<research/canonical_batch_20260807/DEPENDENCY_VERIFICATION.md>)〔sealed dependency verification〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔completeness scan coverage〕

## 历史结果有效性边界

### 依赖旧 front offset 解释的 2026-07-18 前结果须视为已撤回或待复验

- **Claim ID：** `CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED`
- **状态：** `current`
- **权威层：** `owner_decision`
- **权威依据：** `owner_decision`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

front offset 事故确认 stored port 坐标本身就是 front/access cell，旧实现再次加方向偏移会同时制造假 INFEASIBLE 与假放行。因此所有依赖该旧语义的历史运行数字，除非在修正语义和现行候选池上重验，不得作为当前结论。

- **适用范围：** historical-results；port-front-semantics；pre-2026-07-18

- **成立前提：** 结论的计算路径实际消费了旧 front offset 解释；没有后续 corrected-semantics revalidation 覆盖

- **直接后果：** 引用旧实验时必须带前语义标签；当前状态页不得把旧数值直接当现行事实

- **明确不推出：** 所有 2026-07-18 前数学结论都失效；与 front 语义无关的证书被自动推翻

- **取代 claim：** CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED

- **权威源：** docs/research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md；docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md

- **条件处置：** `refuted`
- **操作效果：** counterexample；scope_boundary
- **一般性：** `model_domain`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** incident_review；adversarial_review
- **分类注：** 这是语义事故造成的历史有效性反判，不是 solver 分离器。

- **有效性事件：** `semantic_replacement`
- **受影响层：** canonical_semantics；model_encoding；validator；proof_argument
- **判定依据：** incident_replay；differential_test；independent_recomputation
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `pre_fix_history`
- **有效性注：** 当前可复用的是历史有效性边界；事故前数值仍须逐项在修正语义下重验。

- **证据：** [docs/research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md](<research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md>)〔incident root-cause record〕；[docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md](<research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md>)〔historical rejudgment〕；[.artifacts/front_offset_incident_20260718](<../.artifacts/front_offset_incident_20260718>)〔local incident revalidation receipts〕（工作区可选工件）

### front offset 事故的 40 条历史 finding 已分为 16 作废、12 需重验、12 不受影响

- **Claim ID：** `CLAIM-FRONT-OFFSET-HISTORICAL-REJUDGMENT-40`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_ledger_state`
- **更新时间：** `2026-08-11`

front offset 历史重判对八类共 40 条 finding 逐项落账：16 条作废，只能保留为事故史料；12 条需重验，继续撤回直到修复模型、可比配置和独立规则 oracle 下重跑；12 条不受影响，但只保留指定结构、方法或工具结论，不能外推为相关 front 数值、证书或全称判断仍有效。

- **适用范围：** front-offset-incident；pre-2026-07-18-history；itemized-rejudgment-ledger

- **成立前提：** 只覆盖附录列出的 40 条 finding 与三态定义；任何新实验相似数字都形成新 revision，而非追认旧证书

- **直接后果：** 引用事故前结论时必须先定位该 finding 的三态和动作；作废、需重验与不受影响不得合并成 dossier 级全有或全无判断

- **明确不推出：** 12 条不受影响可以恢复相关 front benchmark；12 条需重验已经由修复提交自动恢复；16 条作废的研究方法也都无价值；所有事故前负结果都失效

- **依赖 claim：** CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED

- **权威源：** docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md

- **条件处置：** `scope_shifted`
- **操作效果：** semantic_partition；scope_boundary；experiment_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** incident_review；adversarial_review

- **有效性事件：** `implementation_invalidation`
- **受影响层：** model_encoding；validator；experiment_design；proof_argument；documentation；research_strategy
- **判定依据：** incident_replay；independent_recomputation；evidence_gap
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `pre_fix_history`
- **有效性注：** 可复用的是逐项三态 ledger；每条 finding 的恢复仍由自己的 revalidation 证据决定。

- **证据：** [docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md](<research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md>)〔itemized 40-finding validity ledger〕

### lever verdict 只能按具体条目、修订和证据边界复用

- **Claim ID：** `CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

历史 lever 失败结论必须绑定具体实现修订、语义版本、资源条款和验证证据；front-independent 的 master、面积、power 或 cut 粒度结论可以逐项保留，front-dependent 的 Phase 4–6、RAB/FCL 与常数 benchmark 则维持撤回或待重验，不能再合并成“整个范式已穷尽”。

- **适用范围：** research-strategy；lever-inventory；historical-validity

- **成立前提：** 每个 lever 的输入语义与实现 revision 可被辨认

- **直接后果：** 路线淘汰记录必须声明 item、revision 和失效触发条件；未来相似路线可先查询局部 verdict 而不是继承全称禁令

- **明确不推出：** 被撤回路线自动值得重跑；旧 verdict 在新 revision 上仍然成立

- **依赖 claim：** CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED

- **取代 claim：** CLAIM-24-LEVER-FRAMEWORK-EXHAUSTED-SUPERSEDED

- **权威源：** docs/research/paradigm_search_review_v12_with_code_20260520/02_LEVER_HISTORY_24_DEAD.md；docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md

- **条件处置：** `scope_shifted`
- **操作效果：** scope_boundary；experiment_boundary；discovery_method
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** incident_review；systematic_rules_audit

- **有效性事件：** `scope_correction`
- **受影响层：** experiment_design；proof_argument；research_strategy
- **判定依据：** incident_replay；evidence_gap
- **复用策略：** `unaffected_under_premises`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`

- **证据：** [docs/research/paradigm_search_review_v12_with_code_20260520/02_LEVER_HISTORY_24_DEAD.md](<research/paradigm_search_review_v12_with_code_20260520/02_LEVER_HISTORY_24_DEAD.md>)〔lever-by-lever historical record and withdrawal banner〕；[docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md](<research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md>)〔itemized rejudgment boundary〕

## Production 开放边界

### cut framework 仍未获 production attach 授权

- **Claim ID：** `CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS`
- **状态：** `current`
- **权威层：** `machine`
- **权威依据：** `machine_verified`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `production_gate`
- **更新时间：** `2026-08-11`

F1/F6/F7 已走 typed lowering；F5 仍为 shadow-only 且没有 lowering；F2/F3/F4/F9 为 LEGACY_DIAGNOSTIC；F8 retired。EXACT_CUT_FRAMEWORK_ATTACH 在 certified unsafe map 内且 default-off，B6 owner promotion 未执行。

- **适用范围：** src/cuts；certified_exact；production_attach

- **成立前提：** PROJECT_LOCK.md 列出的 production integration 前置仍然有效；owner 尚未执行 B6 promotion

- **直接后果：** certified production path 不得开启 cut framework attach；F5 的 shadow 结果不能改写 master

- **明确不推出：** 已验证的 cut 数学结论无价值；B6 只需改一个默认值；F5 已可 production apply

- **依赖 claim：** CLAIM-CERTIFIED-THEOREM-SCOPE

- **权威源：** PROJECT_LOCK.md；src/cuts/typed_platform.py；src/cuts/lifecycle.py
- **机器验收器：** `project_lock_cut_framework_status`
- **关联决定：** DECISION-B6-HOLD-20260803

- **目标阶段：** `search_loop`
- **候选来源：** `supplied_candidate`
- **选择方式：** cut_registry_replay
- **验证方式：** independent_validator；terminal_replay
- **完备性：** `open`
- **消费方式：** diagnostic_only
- **基线比较：** `none`
- **分离注：** typed apply 能消费已知 cut；当前 claim 不声称已有 production 分离器或授权。

- **证据：** [PROJECT_LOCK.md](<../PROJECT_LOCK.md>)〔production promotion boundary〕；[src/cuts/typed_platform.py](<../src/cuts/typed_platform.py>)〔typed registry implementation〕；[docs/research/noncert_cuts_ab16_20260724/README.md](<research/noncert_cuts_ab16_20260724/README.md>)〔tracked AB16 research boundary〕；[.artifacts/ab16_arms_20260802/EVAL.md](<../.artifacts/ab16_arms_20260802/EVAL.md>)〔latest frozen-run exposure evaluation〕（工作区可选工件）；[src/cuts/lifecycle.py](<../src/cuts/lifecycle.py>)〔typed attach-scope and Step-8 apply lifecycle implementation〕

### AB16 完整收官未形成可归因的 cut 科学结论

- **Claim ID：** `CLAIM-AB16-CAMPAIGN-CLOSEOUT-NO-ATTRIBUTABLE-CUT-RESULT`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-14`

AB16 最终 campaign root run-20260802T221714Z-r6 共 21 attempts，其中 16 个 credible terminal arms 全部为 BUDGET_CENSORED_UNKNOWN 且 ORGANIC_NONACTIVATION（G/C/A=0/0/0）。该冻结实验没有任何 cut 配置展示可归因的有机 runtime 改善，因此只形成实验边界，不授权 B6 promotion、production attach、soundness、上下界或“这些 cuts 无效”的结论。

- **适用范围：** noncert-cuts；ab16；experimental-evidence

- **成立前提：** terminal classification v2 对 16 个固定顺序臂给出 credibility=PASS；16/16 credible arms 在相同删失里程碑前未到达 treatment cut 触发点

- **直接后果：** AB16 当前结论必须写成 non-identifying experiment boundary；B6 继续缺少有机暴露证据，owner hold 不被本实验翻转；未来实验必须重新设计可归因的 treatment exposure

- **明确不推出：** cut framework 没有价值；通用 CP-SAT 传播能够替代这些 cuts；B6 永久取消；零激活证明对应不等式无效；BUDGET_CENSORED_UNKNOWN 具有 SAT、UNSAT 或最优语义

- **依赖 claim：** CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS

- **取代 claim：** CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT

- **权威源：** docs/research/noncert_cuts_ab16_20260724/README.md；docs/history/status/00_master_roadmap_pre_phase3_20260812.md
- **关联决定：** DECISION-B6-HOLD-20260803

- **条件处置：** `inconclusive`
- **操作效果：** experiment_boundary
- **一般性：** `research_process`
- **solver 关系：** `experimental_cut`
- **通用传播不能完成分离的证据：** `experimental_only`
- **发现方式：** solver_experiment；adversarial_review
- **分类注：** 零激活是受实验合同限制的观测，不是 generic-propagation impossibility，也不是 cut 无效证明。

- **目标阶段：** `search_loop`
- **候选来源：** `solver_events`
- **选择方式：** raw_event_separation
- **验证方式：** independent_validator
- **完备性：** `open`
- **消费方式：** diagnostic_only
- **基线比较：** `non_identifying`
- **分离注：** 16 臂没有形成可归因的 treatment exposure，因此不能比较 cut 与 baseline 的分离能力。

- **有效性事件：** `revalidation`
- **受影响层：** experiment_design；documentation
- **判定依据：** controlled_experiment；independent_recomputation
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `run_family`
- **有效性注：** successor 使用完整 2026-08-03 closeout 口径，旧 38-root/0-of-16 叙述只保留为历史。

- **证据：** [docs/research/noncert_cuts_ab16_20260724/README.md](<research/noncert_cuts_ab16_20260724/README.md>)〔AB16 authority and experiment contract〕；[docs/history/status/00_master_roadmap_pre_phase3_20260812.md](<history/status/00_master_roadmap_pre_phase3_20260812.md>)〔tracked 2026-08-03 closeout ledger〕；[.artifacts/ab16_arms_20260802/EVAL.md](<../.artifacts/ab16_arms_20260802/EVAL.md>)〔complete 16-arm terminal evaluation〕（工作区可选工件）

## 当前 owner / 治理决定

### 严格语义修复后重新关闭 P1.2

- **Decision ID：** `DECISION-P1-2-RECLOSE-20260806`
- **状态：** `current`
- **登记角色：** `non_authorizing=true`
- **权威作用：** `phase_gate`
- **决定人：** `zhuran24`
- **决定日期：** `2026-08-06`
- **外部决定 ID：** `owner-p1-2-reclose-20260806`
- **外部权威源：** `data/review_gates/phase_1_2_spike_close.json`

owner 在严格空地语义修复、三轮外审与 seal batch 后重新关闭 P1.2；该决定 supersede 2026-07-07 的首次 close。clean-review 计数继续由 owner 在仓库外维护。

- **适用范围：** phase-gate；p1_2；p1_3-entry

- **直接后果：** P1.2 当前为 owner-closed；P1.3 entry 当前允许；clean-review 计数仍在仓库外维护

- **明确不推出：** P1.3 已完成；仓库可从 receipt 计算 clean-review streak

- **取代决定：** DECISION-P1-2-CLOSE-20260707

- **证据：** [data/review_gates/phase_1_2_spike_close.json](<../data/review_gates/phase_1_2_spike_close.json>)〔owner manual gate authority〕；[docs/research/p1_2_v99_close_kernel_sealing.md](<research/p1_2_v99_close_kernel_sealing.md>)〔tracked close-kernel anchor〕；[.artifacts/ghost_strict_fix_20260805/BLOCK_ADJUDICATION_20260806.md](<../.artifacts/ghost_strict_fix_20260805/BLOCK_ADJUDICATION_20260806.md>)〔strict-semantics repair adjudication〕（工作区可选工件）

### 空矩形采用完全空地语义

- **Decision ID：** `DECISION-EMPTY-RECTANGLE-STRICT-20260805`
- **状态：** `current`
- **登记角色：** `non_authorizing=true`
- **权威作用：** `project_semantics`
- **决定人：** `zhuran24`
- **决定日期：** `2026-08-05`
- **外部决定 ID：** `owner-empty-rectangle-strict-20260805`
- **外部权威源：** `docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md`

owner 选择严格解释：空矩形内不得出现任何 occupant。该决定已写入 canonical_rules.json，并使旧的宽松 routing-in-rectangle 解释失效。

- **适用范围：** canonical-rules；empty-rectangle；certified-semantics

- **直接后果：** 候选、验证器和研究证明必须按 no_occupant_of_any_kind 解释空矩形

- **明确不推出：** 所有旧结果无需复验即可迁移到严格语义

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔frozen decision projection〕；[docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md](<research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md>)〔owner adjudication record〕

### B6 promotion 维持不动

- **Decision ID：** `DECISION-B6-HOLD-20260803`
- **状态：** `current`
- **登记角色：** `non_authorizing=true`
- **权威作用：** `research_governance`
- **决定人：** `zhuran24`
- **决定日期：** `2026-08-03`
- **外部决定 ID：** `owner-b6-hold-20260803`
- **外部权威源：** `docs/history/status/00_master_roadmap_pre_phase3_20260812.md`

在没有有机暴露证据且现有零激活受 cap 口径结构影响的情况下，owner 决定不执行 B6 promotion；将来只有在新的实验设计取得可归因激活证据后再议。

- **适用范围：** cut-framework；b6；production-promotion

- **直接后果：** EXACT_CUT_FRAMEWORK_ATTACH 继续 certified unsafe/default-off；没有新可归因激活证据时不得执行 B6 promotion

- **明确不推出：** B6 永久取消；cut framework 的研究结果无效

- **证据：** [docs/history/status/00_master_roadmap_pre_phase3_20260812.md](<history/status/00_master_roadmap_pre_phase3_20260812.md>)〔owner decision ledger before Phase 3 split〕；[docs/history/status/27_status_dashboard_20260803.md](<history/status/27_status_dashboard_20260803.md>)〔pre-spine decision projection〕；[docs/research/noncert_cuts_ab16_20260724/README.md](<research/noncert_cuts_ab16_20260724/README.md>)〔tracked experiment and authority boundary〕；[.artifacts/ab16_arms_20260802/EVAL.md](<../.artifacts/ab16_arms_20260802/EVAL.md>)〔frozen 16-arm evaluation〕（工作区可选工件）

## 覆盖范围与欠账

- **dossier 目录覆盖：** 已登记 docs/research 一级目录与一级 Markdown，以及本机存在或被承重证据引用的 .artifacts 一级目录。轻量 checkout 可缺少 local artifact root。
- **claim 覆盖：** 当前共 95 条稳定 claim；CURRENT 按 claim_selection_policy 只投影当前承重子集，完整账本由 CATALOG、topic、reasoning 与 validity 页面查询。
- **历史 claim 回填：** 45 个 dossier 有 current review，其中 42 个为语义审阅、3 个为 availability/provenance review；另有 165 个 dossier 全部且仅进入一个显式 triage group，17 个 active workflow 等待 typed closure。100% inventory coverage 不等于 100% semantic review。

完整 claim、decision 与 evidence package 目录见 [CATALOG](<CATALOG.md>)；推理分类与历史回填进度见 [REASONING_LEDGER](<REASONING_LEDGER.md>)；历史反例、语义更正、实现失效与重验谱系见 [VALIDITY_LEDGER](<VALIDITY_LEDGER.md>)；语义审阅、可用性核对与长尾分诊闭包见 [BACKFILL_LEDGER](<BACKFILL_LEDGER.md>)；按稳定主题坐标查询见 [TOPIC_INDEX](<TOPIC_INDEX.md>)；规范术语与别名见 [TERMINOLOGY](<TERMINOLOGY.md>)；当前开放问题见 [OPEN_QUESTIONS](<OPEN_QUESTIONS.md>)；按问题进入项目见 [START_HERE](<START_HERE.md>)。
