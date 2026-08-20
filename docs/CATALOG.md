# 项目知识目录

> 本页由 `devtools/build_knowledge_docs.py` 自动生成，禁止手工修改。
> 账本人工审阅日：`2026-08-18`；源摘要：`sha256:deb13488720d91ebb586d677fdce2123cf1a52db5580fcd7fd39b4163bd19ad7`。

这里登记稳定 ID。claim 回答“我们知道什么”，decision 回答“谁改变了什么规则或门”，
dossier 回答“原始证据包在哪里”，validity profile 回答“旧结论为何失效、怎样换代、能否复用”。目录不把历史材料自动升级为当前权威。

## 覆盖概览

- claim：`93` 条，其中当前 / 开放 `73` 条，带 validity profile `34` 条。
- decision：`8` 条。
- backfill review：`54` 条，其中 current `44` 条。
- dossier：`269` 个，其中 tracked `158` 个、local optional `111` 个、当前证据标记 `16` 个、人工精编 `89` 个。
- `docs/research/` 的一级目录和一级 Markdown 已全登记；`.artifacts/` 只登记一级目录，其路径允许在轻量 checkout 中缺失。

## Claim 索引

| Claim ID | 标题 | 状态 | 权威层 | 权威作用 |
|---|---|---|---|---|
| [`CLAIM-24-LEVER-FRAMEWORK-EXHAUSTED-SUPERSEDED`](#claim-24-lever-framework-exhausted-superseded) | “24 lever 全 dead、范式已穷尽”的全称判断已撤回 | `superseded` | `research_only` | `negative_research_result` |
| [`CLAIM-AB16-CAMPAIGN-CLOSEOUT-NO-ATTRIBUTABLE-CUT-RESULT`](#claim-ab16-campaign-closeout-no-attributable-cut-result) | AB16 完整收官未形成可归因的 cut 科学结论 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT`](#claim-ab16-no-scientific-cut-result) | AB16 当前只形成实验边界，未形成可归因的 cut 科学结论 | `superseded` | `research_authority` | `negative_research_result` |
| [`CLAIM-ACTIVE-SCOPE-SINGLE-BASE`](#claim-active-scope-single-base) | certified active scope 仅含单一 70×70 基地 | `current` | `machine` | `defines_certified_scope` |
| [`CLAIM-ADMISSION-PORT-OMISSION-SCOPE-RESTRICTION`](#claim-admission-port-omission-scope-restriction) | 1×1 item admission port 的省略是显式认证作用域限制 | `current` | `rules_authority` | `defines_certified_scope` |
| [`CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY`](#claim-attach-spikes-engineering-not-cut-efficacy) | attach spikes 只证明工程接线，不证明 cut 科学效力 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-B1-CEILING-EXACT-NINE-POLES`](#claim-b1-ceiling-exact-nine-poles) | B1 ceiling survivor 若存在则恰用九根电杆 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-B1-CONDITIONAL-HALO-CAPACITY-6650`](#claim-b1-conditional-halo-capacity-6650) | B1-CH 对全部已选电杆给出 clipped halo 容量下界 6650 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-B1-QMH-REFINED-MEMBRANE-INEQUALITY`](#claim-b1-qmh-refined-membrane-inequality) | B1-QMH 用边界 Q 交叠与端点项细化 ordinary membrane | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE`](#claim-band22-v0a-strict-hole-incompatible) | 交付版 band22 V0-A 骨架与 strict hole 不相容 | `current` | `research_only` | `conditional_model_exclusion` |
| [`CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE`](#claim-binding-slot-single-commodity-scope) | binding slot 单商品模型不能表达 wired warehouse 输入的多商品吸收 | `current` | `rules_authority` | `defines_certified_scope` |
| [`CLAIM-BODY-ACCESS-BUDGET-1320`](#claim-body-access-budget-1320) | body-empty rectangle 与外部 access cells 共用 1320 格预算 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED`](#claim-boundary-generic-output-slots-saturated) | generic output 槽账 52=52，46 个边界 raw 口全部被迫激活 | `current` | `research_only` | `conditional_model_exclusion` |
| [`CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE`](#claim-boundary-loader-excluded-frozen-instance) | 冻结实例中 storage-side boundary loader 被 141>139 格数账排除 | `current` | `rules_authority` | `conditional_model_exclusion` |
| [`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](#claim-budget-exhaustion-is-unknown-not-fixed-point) | 预算耗尽必须返回 UNKNOWN，不能冒充固定点 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](#claim-certified-existence-open) | 现行语义下 whole-layout 认证级存在性仍为 OPEN | `open` | `research_only` | `research_ledger_state` |
| [`CLAIM-CERTIFIED-THEOREM-SCOPE`](#claim-certified-theorem-scope) | CERTIFIED 的命题边界是六谓词与 lex 最优 | `current` | `machine` | `defines_certified_scope` |
| [`CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO`](#claim-column-generation-phase2-scale-route-no-go) | Column Generation Phase 2 的登记设计未跨过规模与重构门槛 | `historical` | `research_only` | `negative_research_result` |
| [`CLAIM-CONNECTIVITY-QUANTIFIER-PER-COMMODITY-SOURCE-SINK`](#claim-connectivity-quantifier-per-commodity-source-sink) | 游戏连通量词是逐 commodity 的双向 source/sink 可达 | `current` | `rules_authority` | `rules_semantics` |
| [`CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS`](#claim-cut-framework-production-status) | cut framework 仍未获 production attach 授权 | `current` | `machine` | `production_gate` |
| [`CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE`](#claim-destination-front-exclusivity-terminal-sensitive) | destination-front 单商品排他必须按接收终端类别解释 | `current` | `rules_authority` | `defines_certified_scope` |
| [`CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS`](#claim-discovery-and-validation-separate-obligations) | 候选发现与候选验证是两项独立能力 | `current` | `research_authority` | `descriptive_only` |
| [`CLAIM-DURABLE-CERTIFIED-RESULT-ABSENT`](#claim-durable-certified-result-absent) | checked-in durable CERTIFIED 结果当前不存在 | `current` | `machine` | `research_ledger_state` |
| [`CLAIM-EMPTY-RECTANGLE-MIN-SIDE-ADMISSIBILITY-SIX`](#claim-empty-rectangle-min-side-admissibility-six) | 空矩形 admissibility 的最小边长为 6 | `current` | `rules_authority` | `rules_semantics` |
| [`CLAIM-EMPTY-RECTANGLE-ROUTING-ALLOWED-SUPERSEDED`](#claim-empty-rectangle-routing-allowed-superseded) | 空矩形只禁设施、允许物流组件穿入的宽松解释已被替代 | `superseded` | `descriptive` | `descriptive_only` |
| [`CLAIM-EMPTY-RECTANGLE-STRICT`](#claim-empty-rectangle-strict) | 空矩形采用 no_occupant_of_any_kind 严格语义 | `current` | `rules_authority` | `rules_semantics` |
| [`CLAIM-F7-FACILITY-MASK-VALIDATOR-BUG-REPAIRED`](#claim-f7-facility-mask-validator-bug-repaired) | F7 validator 漏排 facility cells 的误杀缺陷已修复并复核 | `historical` | `research_only` | `descriptive_only` |
| [`CLAIM-FORWARD-COMPLETENESS-RELATIVE-TO-DECLARED-FRAGMENT`](#claim-forward-completeness-relative-to-declared-fragment) | 前向完备性只能相对于声明片段定义 | `current` | `research_only` | `descriptive_only` |
| [`CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED`](#claim-front-offset-double-step-semantics-superseded) | stored port 之后再沿方向前移一格的旧 front 解释已被替代 | `superseded` | `descriptive` | `descriptive_only` |
| [`CLAIM-FRONT-OFFSET-HISTORICAL-REJUDGMENT-40`](#claim-front-offset-historical-rejudgment-40) | front offset 事故的 40 条历史 finding 已分为 16 作废、12 需重验、12 不受影响 | `current` | `research_authority` | `research_ledger_state` |
| [`CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED`](#claim-front-offset-pre-0718-superseded) | 依赖旧 front offset 解释的 2026-07-18 前结果须视为已撤回或待复验 | `current` | `owner_decision` | `negative_research_result` |
| [`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](#claim-generic-cp-sat-separation-impossibility-open) | 通用 CP-SAT 传播不能替代领域分离的正式命题仍开放 | `open` | `research_only` | `none` |
| [`CLAIM-IHS-SINGLETON-CORE-COMPRESSION-PHASE0-NO-GO`](#claim-ihs-singleton-core-compression-phase0-no-go) | IHS Phase 0 的 singleton core 源没有产生跨迭代压缩 | `historical` | `research_only` | `negative_research_result` |
| [`CLAIM-LAZY-POWER-INSTANCE-POSE-CUT-ROUTE-NO-GO`](#claim-lazy-power-instance-pose-cut-route-no-go) | Lazy Power Completion 的 instance×pose cut 路线在登记锚点触发 NO-GO | `historical` | `research_only` | `negative_research_result` |
| [`CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`](#claim-lever-verdicts-are-item-and-revision-bounded) | lever verdict 只能按具体条目、修订和证据边界复用 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-M5-DEATHS-REQUIRE-RESOURCE-BUILD-AND-PARAMETER-SEPARATION`](#claim-m5-deaths-require-resource-build-and-parameter-separation) | M5 死亡归因必须分开资源尖峰、build 爆炸与 solve 参数 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-M5-DEFAULT-SOLVE-PARAMETERS-PATHOLOGICAL-REFUTED`](#claim-m5-default-solve-parameters-pathological-refuted) | M5“产品默认 solve 参数病态”归因已被受控 A/B 推翻 | `refuted` | `research_authority` | `negative_research_result` |
| [`CLAIM-MIXED-TERMINAL-TRIPARTITION`](#claim-mixed-terminal-tripartition) | 混流接收终端分为 core、storage box 与 machine input 三类 | `current` | `rules_authority` | `rules_semantics` |
| [`CLAIM-MIXFLOW-DEMIX-CONCLUSION-SURVIVES-FIXTURE-CORRECTION`](#claim-mixflow-demix-conclusion-survives-fixture-correction) | mixflow demix 主对照在忠实 fixture 修正后保持同向 | `historical` | `research_only` | `descriptive_only` |
| [`CLAIM-MIXFLOW-U01-GUARD-FORK-BENEFIT-REFUTED`](#claim-mixflow-u01-guard-fork-benefit-refuted) | U-01“守卫分叉带来可行性红利”的观测已由忠实 fixture 对照推翻 | `refuted` | `research_only` | `negative_research_result` |
| [`CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT`](#claim-model-stricter-faces-scope-debt) | 六个 model-stricter face 是完整性与认证作用域欠账 | `current` | `rules_authority` | `defines_certified_scope` |
| [`CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48`](#claim-ordinary-membrane-terminal-bound-s48) | ordinary membrane 给出 T_in≤w+h+48 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-P2-AREA-ACCOUNTING-1356`](#claim-p2-area-accounting-1356) | P2.0 格位分账给出 A≤1356−4P−R | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-P2-AREA-BOUND-1167`](#claim-p2-area-bound-1167) | P2.0 无条件容量计数面积上界为 A≤1167 | `current` | `research_authority` | `research_upper_update` |
| [`CLAIM-P2-BUCKWHEAT-SANDLEAF-MANDATORY-BRANCH`](#claim-p2-buckwheat-sandleaf-mandatory-branch) | P2.0 当前实例中荞麦与砂叶分支不可消除 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL`](#claim-p2-five-full-one-half-conditional) | 钢块免分流前提下，六台制瓶机被迫为 5 满 1 半 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-P2-MIN-SIDE-UPPER-OPEN`](#claim-p2-min-side-upper-open) | P2.0 的 min_side 上界仍未建立 | `open` | `research_authority` | `none` |
| [`CLAIM-P2-ROUTE-FOOTPRINT-LOWER-153`](#claim-p2-route-footprint-lower-153) | P2.0 route footprint 满足 R≥153 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305`](#claim-p2-route-state-lower-bound-305) | P2.0 route-state 数至少为 305 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-P2-ROUTED-FLOW-LOWER-9135`](#claim-p2-routed-flow-lower-9135) | P2.0 进入路由图的聚合流量至少为 9135 件/分钟 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015`](#claim-p2-single-layer-area-bound-1015) | P2.0 单层口径条件式面积上界为 A≤1015 | `current` | `research_authority` | `research_upper_update` |
| [`CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED`](#claim-p2-steel-block-17-lt-18-refuted) | “steel_block 17<18 因而必分流”已被反例推翻 | `refuted` | `research_authority` | `negative_research_result` |
| [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](#claim-p2-throughput-research-ledger) | P2.0 吞吐语义另有 A≤1167 / A≤1015 条件账本 | `superseded` | `research_authority` | `research_upper_update` |
| [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814`](#claim-p2-throughput-research-ledger-20260814) | P2.0 吞吐语义的独立条件账本 | `current` | `research_authority` | `research_upper_update` |
| [`CLAIM-PAIRWISE-CLOSURE-INCOMPLETE`](#claim-pairwise-closure-incomplete) | pairwise 固定点不能证明规则闭包已饱和 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE`](#claim-power-halo-pole-lower-bound-nine) | 当前冻结实例至少需要九根电杆 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-PROVED-PREMODEL-EXCLUSION-PERMITS-MODEL-OMISSION`](#claim-proved-premodel-exclusion-permits-model-omission) | 只有被证明的预建模排除才支持安全免建模 | `current` | `descriptive` | `descriptive_only` |
| [`CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED`](#claim-r1-1326-34-strict-upper-revalidated) | R1 strict `(1326,34)` 上界已由两段证明链重新验证 | `historical` | `research_authority` | `descriptive_only` |
| [`CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY`](#claim-r3-lex-band-2074-unsat-given-geometry) | 给定 R3 几何引理，2074 个 lex-better 尺寸的算术层为 UNSAT | `historical` | `research_authority` | `research_upper_update` |
| [`CLAIM-R4-BOUNDARY-23-23-FULL-SPAN-EXCLUSION`](#claim-r4-boundary-23-23-full-span-exclusion) | 46 个 boundary bodies 强制 23+23，并排除 70 格 full-span hole | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-R4-LEX-BAND-2084-UNSAT`](#claim-r4-lex-band-2084-unsat) | 给定 A004 几何引理，lex>(1188,22) 的 2084-orientation band 为 UNSAT | `current` | `research_authority` | `research_upper_update` |
| [`CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4`](#claim-r4-local-weighted-access-capacity-4) | R4 marked 账下每个外部 access cell 满足 t+m≤4 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-R4-MARKED-INCIDENCE-TOTAL-110`](#claim-r4-marked-incidence-total-110) | R4 marked-incidence census 的总数为 110 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-R4-MARKED-MEMBRANE-BOUND-S12`](#claim-r4-marked-membrane-bound-s12) | R4 marked membrane 对 normalized w≥9 给出 M_in≤S+12 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-R4-NECESSARY-DIMENSION-INEQUALITY`](#claim-r4-necessary-dimension-inequality) | R4 用 ordinary/marked 双账得到完整尺寸必要不等式 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN`](#claim-rab-fcl-front-dependent-performance-withdrawn) | 旧 RAB/FCL 的 front-dependent 性能与收敛归因已撤回，复用前须按修正语义重验 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE`](#claim-rate-lemma-conditional-profile) | intermediate pure-flow rate lemma 只覆盖等占空且最少车道的显式分配剖面 | `current` | `rules_authority` | `conditional_model_exclusion` |
| [`CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`](#claim-raw-eligible-events-required-for-separation-evaluation) | 分离实验必须记录 raw eligible events，不能只看 accepted cuts | `current` | `research_authority` | `descriptive_only` |
| [`CLAIM-ROUND45-CORRECTED-PROFILE-UNKNOWN-NOT-STRUCTURAL-WALL`](#claim-round45-corrected-profile-unknown-not-structural-wall) | 修正后的 Round 4/5 紧凑模型只支持预算内 UNKNOWN，不支持结构墙 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT`](#claim-routing-reverification-extra-strict) | routing reverification 的 no-orphan 与 selected-source-reaches-sink 超出游戏连通量词 | `superseded` | `rules_authority` | `defines_certified_scope` |
| [`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT-BOUNDARY`](#claim-routing-reverification-extra-strict-boundary) | routing reverification 的附加严格面不改写游戏连通量词 | `current` | `rules_authority` | `defines_certified_scope` |
| [`CLAIM-SHARED-ENCODING-AGREEMENT-NOT-INDEPENDENT-VALIDATION`](#claim-shared-encoding-agreement-not-independent-validation) | 共享坐标 helper 的 oracle 与 validator 一致不构成独立验证 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](#claim-six-predicate-research-ledger) | 六谓词 research ledger 为 U=(1188,18)、L=absent | `superseded` | `research_authority` | `research_upper_update` |
| [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818`](#claim-six-predicate-research-ledger-20260818) | 六谓词 research 条件上界收紧为 U=(1170,30) | `current` | `research_authority` | `research_upper_update` |
| [`CLAIM-SMM-209-EXCLUDES-22X54`](#claim-smm-209-excludes-22x54) | SMM-209 排除 22×54 与 54×22 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-SMM-COMBINED-CAP-209`](#claim-smm-combined-cap-209) | SMM-209 给出 T_in+M_in≤209 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-SMM-ENDPOINT-TOP-EIGHT-BUDGET-19`](#claim-smm-endpoint-top-eight-budget-19) | SMM entity-max 的八端点 top-eight budget 为 19 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-SMM-MARKED-MEMBRANE-BOUND-85`](#claim-smm-marked-membrane-bound-85) | SMM 对 22×54 给出 M_in≤85 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-SMM-OUTSIDE-ACCESS-LOWER-133`](#claim-smm-outside-access-lower-133) | SMM-209 推出至少 133 个外部 access cells | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-SMM4-LEX-BAND-COMPOSITION-2086`](#claim-smm4-lex-band-composition-2086) | SMM4 把旧 2084 band 与两个 SMM orientations 组合为完整 2086 band | `current` | `research_authority` | `research_upper_update` |
| [`CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER`](#claim-smt-mt-synthetic-go-not-transferable-to-real-inner) | SMT-MT synthetic GO 不能替代真实 inner fuel 的有效性验证 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-SOLVER-RETHINK-G03-LACKS-SEPARATION-ORACLE`](#claim-solver-rethink-g03-lacks-separation-oracle) | solver-rethink 的 G-03 只有 checker，缺自主 separator | `historical` | `research_only` | `negative_research_result` |
| [`CLAIM-SOLVER-RETHINK-PHASE1-OMITS-CONSTRUCTION-HALF`](#claim-solver-rethink-phase1-omits-construction-half) | solver-rethink 一期不覆盖 witness/下界构造半边 | `historical` | `research_only` | `descriptive_only` |
| [`CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT`](#claim-source-front-exclusivity-overstrict) | source-front 单商品排他是已确认的过严模型面 | `current` | `rules_authority` | `defines_certified_scope` |
| [`CLAIM-STORAGE-BOX-ACCEPTANCE-INVARIANT-FROZEN`](#claim-storage-box-acceptance-invariant-frozen) | frozen production line 单独履行了 protocol storage box 的逐次到达接受不变量 | `current` | `rules_authority` | `conditional_model_exclusion` |
| [`CLAIM-STRICT-HOLE-AVOIDS-X1-Y1`](#claim-strict-hole-avoids-x1-y1) | 严格空矩形不得触碰 x=1 列或 y=1 行 | `current` | `research_only` | `conditional_model_exclusion` |
| [`CLAIM-STRICTER-FEASIBLE-SET-PRESERVES-NEGATIVE-NOT-POSITIVE`](#claim-stricter-feasible-set-preserves-negative-not-positive) | 可行集收紧保留负结果与上界，但不保留旧正向见证 | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM`](#claim-typed-cut-pipeline-consumes-known-cuts-not-discovers-them) | typed cut 管道消费已知 cut，但不自动发现 cut | `current` | `machine` | `descriptive_only` |
| [`CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED`](#claim-w0-adjacent-4x4-power-impossibility-refuted) | W0 相邻 4+4 宏族供电不可行定理已被坐标反例推翻 | `refuted` | `research_authority` | `negative_research_result` |
| [`CLAIM-W0-POWER-OBSTRUCTION-REQUIRES-DECLARED-HEIGHT-PURITY`](#claim-w0-power-obstruction-requires-declared-height-purity) | W0 供电阻塞证明只能在明示的模板到带高纯装前提下复用 | `current` | `research_authority` | `conditional_model_exclusion` |
| [`CLAIM-WAREHOUSE-BRIDGE-EXCLUSION-TARGET-CONDITIONAL`](#claim-warehouse-bridge-exclusion-target-conditional) | warehouse bridge 排除只由冻结产量目标下的条件式生产线论证支撑 | `current` | `rules_authority` | `defines_certified_scope` |
| [`CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN`](#claim-witness-restricted-pole-domains-infeasible-full-domain-open) | witness 构造只排除了两个受限 pole 域，2,507 候选全域仍为 OPEN | `current` | `research_authority` | `negative_research_result` |
| [`CLAIM-ZERO-SLACK-AUDIT-METHOD`](#claim-zero-slack-audit-method) | 低余量审计可系统寻找被迫结构与领域不等式 | `current` | `descriptive` | `descriptive_only` |

## Decision 索引

| Decision ID | 标题 | 状态 | 日期 | 权威作用 |
|---|---|---|---|---|
| [`DECISION-B6-HOLD-20260803`](#decision-b6-hold-20260803) | B6 promotion 维持不动 | `current` | `2026-08-03` | `research_governance` |
| [`DECISION-EMPTY-RECTANGLE-STRICT-20260805`](#decision-empty-rectangle-strict-20260805) | 空矩形采用完全空地语义 | `current` | `2026-08-05` | `project_semantics` |
| [`DECISION-LEDGER-AUTHORITY-INTERFACES-20260813`](#decision-ledger-authority-interfaces-20260813) | 文档补丁链两接口点联合结论四条通过 | `current` | `2026-08-13` | `research_governance` |
| [`DECISION-OUTER-LOOP-REVIEW-REGISTRATION-20260815`](#decision-outer-loop-review-registration-20260815) | 推理外环评审归档与约束登记许可 | `current` | `2026-08-15` | `research_governance` |
| [`DECISION-P1-2-CLOSE-20260707`](#decision-p1-2-close-20260707) | P1.2 首次关闭并允许进入 P1.3 | `superseded` | `2026-07-07` | `phase_gate` |
| [`DECISION-P1-2-RECLOSE-20260806`](#decision-p1-2-reclose-20260806) | 严格语义修复后重新关闭 P1.2 | `current` | `2026-08-06` | `phase_gate` |
| [`DECISION-RULE-SYSTEM-REDESIGN-OPEN-20260813`](#decision-rule-system-redesign-open-20260813) | rule_system_redesign_20260807 线允许立项 | `current` | `2026-08-13` | `research_governance` |
| [`DECISION-SEMANTICS-SPLIT-EXPERIMENT-FIRST-20260813`](#decision-semantics-split-experiment-first-20260813) | semantics 拆分走先实验后拍板路线 | `current` | `2026-08-13` | `research_governance` |

## Topic 索引

- `p1_2-proof-chain`：72 个 dossier。
- `reasoning-system`：53 个 dossier。
- `solver-architecture`：52 个 dossier。
- `other`：50 个 dossier。
- `witness-lower-bound`：42 个 dossier。
- `upper-bound`：28 个 dossier。
- `solver-experiment`：26 个 dossier。
- `cut-framework`：19 个 dossier。
- `formal-verification`：16 个 dossier。
- `rules-semantics`：12 个 dossier。
- `industrial-delivery`：8 个 dossier。
- `p2-throughput`：8 个 dossier。
- `documentation-governance`：4 个 dossier。
- `separation-telemetry`：2 个 dossier。
- `solver-rethink`：2 个 dossier。
- `separation-method`：1 个 dossier。

## Dossier 反向索引

这里把证据包反向连回使用它的 claim 与 decision，避免目录只有单向指针。

| Dossier ID | 标题 / 入口 | Claims | Decisions | Backfill reviews |
|---|---|---|---|---|
| `DOSSIER-CFG-RELAXATION-CERTIFICATES-20260818-76C8EC34D8` | [配置松弛纯有理对偶证书与负控（2026-08-18）](<../.artifacts/cfg_relaxation_certificates_20260818/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818`](#claim-six-predicate-research-ledger-20260818) | — | — |
| `DOSSIER-CFG-RELAXATION-ENUM-CLOSURE-23X51-20260818-176509E438` | [23×51 配置松弛枚举完备性封口（2026-08-18）](<../.artifacts/cfg_relaxation_enum_closure_23x51_20260818/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818`](#claim-six-predicate-research-ledger-20260818) | — | — |
| `DOSSIER-CFG-RELAXATION-IMPL-B-20260817-77A5280EF9` | [配置松弛 support 独立实现 B（2026-08-17）](<../.artifacts/cfg_relaxation_impl_B_20260817/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818`](#claim-six-predicate-research-ledger-20260818) | — | — |
| `DOSSIER-CFG-RELAXATION-IMPL-A-20260817-BE414F298A` | [配置松弛 support 独立实现 A（2026-08-17）](<../.artifacts/cfg_relaxation_impl_A_20260817/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818`](#claim-six-predicate-research-ledger-20260818) | — | — |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-REVIEWS-20260815-D26B592E99` | [推理外环三轮外部评审归档（2026-08-15）](<research/solver_reasoning_outer_loop_reviews_20260815/README.md>)<br>三份外部评审正文逐字归档；同一 active dossier 继续承载 Phase -1 观测、W0 离线短证书、一元 lowering 金丝雀及 2026-08-16 席位算术／固定矩形终局排除实验。所有实验均保持 research-only／non-authorizing：定理与候选排除不自动构成立项、produ… | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818`](#claim-six-predicate-research-ledger-20260818) | [`DECISION-OUTER-LOOP-REVIEW-REGISTRATION-20260815`](#decision-outer-loop-review-registration-20260815) | [`REVIEW-20260815-SOLVER-REASONING-OUTER-LOOP-GPT-PRO`](#review-20260815-solver-reasoning-outer-loop-gpt-pro) |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-20260815-7FA2A0E225` | [推理外环 Phase -1 本机运行证据包（2026-08-15）](<../.artifacts/solver_reasoning_outer_loop_phase_minus1_20260815/phase-minus1-r1-20260815/BATCH_SUMMARY.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | — | — | [`REVIEW-20260815-PHASE-MINUS1-LOCAL-EVIDENCE-MECHANICAL-AUDIT`](#review-20260815-phase-minus1-local-evidence-mechanical-audit) |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-V2-20260815-96E16B17C8` | 推理外环 Phase -1 v2 高预算本机运行证据包（2026-08-15）<br><code>.artifacts/solver_reasoning_outer_loop_phase_minus1_v2_20260815</code><br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | — | — | [`REVIEW-20260815-PHASE-MINUS1-V2-LOCAL-EVIDENCE-REGISTRATION`](#review-20260815-phase-minus1-v2-local-evidence-registration) |
| `DOSSIER-SOLVER-RETHINK-20260808-47BE0A3C3A` | [推理外环 solver-rethink 设计与对抗收敛包](<../.artifacts/solver_rethink_20260808/DESIGN_DOC_v2.md>)<br>本机可选的推理外环、CP-SAT 内层、完备性口径、能力缺口与对抗收敛设计包；未立线、未获 production authority。 | [`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](#claim-budget-exhaustion-is-unknown-not-fixed-point)<br>[`CLAIM-FORWARD-COMPLETENESS-RELATIVE-TO-DECLARED-FRAGMENT`](#claim-forward-completeness-relative-to-declared-fragment)<br>[`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](#claim-generic-cp-sat-separation-impossibility-open)<br>[`CLAIM-SOLVER-RETHINK-G03-LACKS-SEPARATION-ORACLE`](#claim-solver-rethink-g03-lacks-separation-oracle)<br>[`CLAIM-SOLVER-RETHINK-PHASE1-OMITS-CONSTRUCTION-HALF`](#claim-solver-rethink-phase1-omits-construction-half) | — | [`REVIEW-20260811-SOLVER-RETHINK-BATCH3`](#review-20260811-solver-rethink-batch3) |
| `DOSSIER-CANONICAL-BATCH-20260808-B2462129DF` | [BLOCKERS / 待定点（canonical 08-08 改稿草案 · v3）](<research/canonical_batch_20260808/BLOCKERS.md>)<br>--- | [`CLAIM-ADMISSION-PORT-OMISSION-SCOPE-RESTRICTION`](#claim-admission-port-omission-scope-restriction)<br>[`CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE`](#claim-binding-slot-single-commodity-scope)<br>[`CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE`](#claim-boundary-loader-excluded-frozen-instance)<br>[`CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE`](#claim-destination-front-exclusivity-terminal-sensitive)<br>[`CLAIM-MIXED-TERMINAL-TRIPARTITION`](#claim-mixed-terminal-tripartition)<br>[`CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT`](#claim-model-stricter-faces-scope-debt)<br>[`CLAIM-PROVED-PREMODEL-EXCLUSION-PERMITS-MODEL-OMISSION`](#claim-proved-premodel-exclusion-permits-model-omission)<br>[`CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE`](#claim-rate-lemma-conditional-profile)<br>[`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT`](#claim-routing-reverification-extra-strict)<br>[`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT-BOUNDARY`](#claim-routing-reverification-extra-strict-boundary)<br>[`CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT`](#claim-source-front-exclusivity-overstrict)<br>[`CLAIM-STORAGE-BOX-ACCEPTANCE-INVARIANT-FROZEN`](#claim-storage-box-acceptance-invariant-frozen) | — | [`REVIEW-20260811-CANONICAL-BATCH-20260808`](#review-20260811-canonical-batch-20260808) |
| `DOSSIER-RULE-SYSTEM-REDESIGN-20260807-9B23FA19D2` | [规则形态与推理流程重设计](<research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md>)<br>低余量发现法、条件塌点、pairwise closure 反例、双向保真与 derived-rule 工作流的现行研究文书。 | [`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](#claim-budget-exhaustion-is-unknown-not-fixed-point)<br>[`CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS`](#claim-discovery-and-validation-separate-obligations)<br>[`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](#claim-generic-cp-sat-separation-impossibility-open)<br>[`CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL`](#claim-p2-five-full-one-half-conditional)<br>[`CLAIM-PAIRWISE-CLOSURE-INCOMPLETE`](#claim-pairwise-closure-incomplete)<br>[`CLAIM-PROVED-PREMODEL-EXCLUSION-PERMITS-MODEL-OMISSION`](#claim-proved-premodel-exclusion-permits-model-omission)<br>[`CLAIM-ZERO-SLACK-AUDIT-METHOD`](#claim-zero-slack-audit-method) | — | [`REVIEW-20260811-RULE-SYSTEM-REDESIGN`](#review-20260811-rule-system-redesign)<br>[`REVIEW-20260811-RULE-SYSTEM-REDESIGN-BATCH3`](#review-20260811-rule-system-redesign-batch3) |
| `DOSSIER-MIXFLOW-DEMIX-BAN-20260807-FFEA2B3CE4` | [更正：openyard8x8 探针装置端口朝向不忠实（2026-08-07，U-01 批发现并修）](<../.artifacts/mixflow_demix_ban_20260807/CORRECTION_open_yard_fixture_20260807.md>)<br>处置依据：team-lead 2026-08-07 拍板「openyard 装置在本批顺手修忠实（已有忠实变体， 替换 + 标注原装置缺陷即可）」。本文件是那次替换的记录。 | [`CLAIM-MIXFLOW-DEMIX-CONCLUSION-SURVIVES-FIXTURE-CORRECTION`](#claim-mixflow-demix-conclusion-survives-fixture-correction)<br>[`CLAIM-MIXFLOW-U01-GUARD-FORK-BENEFIT-REFUTED`](#claim-mixflow-u01-guard-fork-benefit-refuted) | — | [`REVIEW-20260811-MIXFLOW-FIXTURE-CORRECTION-BATCH4`](#review-20260811-mixflow-fixture-correction-batch4) |
| `DOSSIER-P2-0-SPECIALIZED-20260807-C40266E222` | [P2.0 特化推理与反例重判](<research/p2_0_specialized_20260807/README.md>)<br>台间占空自由度、作物必分支、steel_block 反例和阶梯见证的主 dossier。 | [`CLAIM-P2-BUCKWHEAT-SANDLEAF-MANDATORY-BRANCH`](#claim-p2-buckwheat-sandleaf-mandatory-branch)<br>[`CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL`](#claim-p2-five-full-one-half-conditional)<br>[`CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED`](#claim-p2-steel-block-17-lt-18-refuted)<br>[`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](#claim-p2-throughput-research-ledger)<br>[`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814`](#claim-p2-throughput-research-ledger-20260814) | — | [`REVIEW-20260811-P2-SPECIALIZED`](#review-20260811-p2-specialized)<br>[`REVIEW-20260811-P2-SPECIALIZED-BATCH4`](#review-20260811-p2-specialized-batch4) |
| `DOSSIER-CANONICAL-BATCH-20260807-B460BA9381` | [canonical 公理 kernel + 四件套修正批（2026-08-07）](<research/canonical_batch_20260807/README.md>)<br>owner 2026-08-07 晨拍板：公理 kernel 提案与在案四件套（W-PENDING-01）合并、一次 freeze-ritual 走完。本目录 = 该批的定谳存档 + reseal 台账 + 验证记录。 | [`CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE`](#claim-binding-slot-single-commodity-scope)<br>[`CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE`](#claim-boundary-loader-excluded-frozen-instance)<br>[`CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE`](#claim-destination-front-exclusivity-terminal-sensitive)<br>[`CLAIM-MIXED-TERMINAL-TRIPARTITION`](#claim-mixed-terminal-tripartition)<br>[`CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT`](#claim-model-stricter-faces-scope-debt)<br>[`CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE`](#claim-rate-lemma-conditional-profile)<br>[`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT`](#claim-routing-reverification-extra-strict)<br>[`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT-BOUNDARY`](#claim-routing-reverification-extra-strict-boundary)<br>[`CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT`](#claim-source-front-exclusivity-overstrict) | — | [`REVIEW-20260811-CANONICAL-BATCH-20260807`](#review-20260811-canonical-batch-20260807) |
| `DOSSIER-P2-0-AREA-BOUND-20260806-6016501B5F` | [P2.0 面积上界账本](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)<br>P2.0 吞吐语义下 A≤1167、条件界 A≤1015、共享前件与 min_side 次坐标开放义务的定理、复核和收据索引。 | [`CLAIM-P2-AREA-ACCOUNTING-1356`](#claim-p2-area-accounting-1356)<br>[`CLAIM-P2-AREA-BOUND-1167`](#claim-p2-area-bound-1167)<br>[`CLAIM-P2-MIN-SIDE-UPPER-OPEN`](#claim-p2-min-side-upper-open)<br>[`CLAIM-P2-ROUTE-FOOTPRINT-LOWER-153`](#claim-p2-route-footprint-lower-153)<br>[`CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305`](#claim-p2-route-state-lower-bound-305)<br>[`CLAIM-P2-ROUTED-FLOW-LOWER-9135`](#claim-p2-routed-flow-lower-9135)<br>[`CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015`](#claim-p2-single-layer-area-bound-1015)<br>[`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](#claim-p2-throughput-research-ledger)<br>[`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814`](#claim-p2-throughput-research-ledger-20260814)<br>[`CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE`](#claim-power-halo-pole-lower-bound-nine) | — | [`REVIEW-20260811-P2-AREA-BOUND`](#review-20260811-p2-area-bound)<br>[`REVIEW-20260811-P2-AREA-BOUND-BATCH2`](#review-20260811-p2-area-bound-batch2) |
| `DOSSIER-GHOST-STRICT-FIX-20260805-0FBA53DB19` | [strict ghost 修复与复审收据](<../.artifacts/ghost_strict_fix_20260805/mutation_manifests_20260806/SUMMARY.md>)<br>2026-08-05 至 08-06 strict-semantics 修复、外审与 seal batch 的本机可选证据。 | [`CLAIM-EMPTY-RECTANGLE-STRICT`](#claim-empty-rectangle-strict) | [`DECISION-P1-2-RECLOSE-20260806`](#decision-p1-2-reclose-20260806) | [`REVIEW-20260812-GHOST-STRICT-FIX-BATCH5`](#review-20260812-ghost-strict-fix-batch5) |
| `DOSSIER-P2-0-REFRESH-20260805-627C980F03` | [P2.0 refresh 本地收据](<../.artifacts/p2_0_refresh_20260805/AREA_BOUND_UPGRADE_PLAN.md>)<br>P2.0 面积界与复核脚本的本机可选收据根。 | [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](#claim-p2-throughput-research-ledger)<br>[`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814`](#claim-p2-throughput-research-ledger-20260814) | — | [`REVIEW-20260812-P2-REFRESH-BATCH5`](#review-20260812-p2-refresh-batch5) |
| `DOSSIER-BAND22-STRICT-HOLE-PROBE-20260805-B4EF0C65D3` | [band22 严格空地结构探针](<../.artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md>)<br>本机可选的 52=52 槽账、边界禁轨和孔位容量探针。 | [`CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE`](#claim-band22-v0a-strict-hole-incompatible)<br>[`CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED`](#claim-boundary-generic-output-slots-saturated)<br>[`CLAIM-STRICT-HOLE-AVOIDS-X1-Y1`](#claim-strict-hole-avoids-x1-y1) | — | [`REVIEW-20260811-BAND22-STRICT-HOLE-PROBE-BATCH2`](#review-20260811-band22-strict-hole-probe-batch2) |
| `DOSSIER-W0-FRONT-AWARE-20260803-425794297E` | [G1 两个 master run root 的仓内副本（字节原样）](<research/w0_front_aware_20260803/evidence/README.md>)<br>RESULT.md 的每个数字都来自这两个运行根。它们原本只存在于单机根盘的 .artifacts/（未跟踪、权限 700），所以这里放一份字节原样的副本进 git。 | [`CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED`](#claim-w0-adjacent-4x4-power-impossibility-refuted)<br>[`CLAIM-W0-POWER-OBSTRUCTION-REQUIRES-DECLARED-HEIGHT-PURITY`](#claim-w0-power-obstruction-requires-declared-height-purity) | — | [`REVIEW-20260811-W0-POWER-COUNTEREXAMPLE-BATCH4`](#review-20260811-w0-power-counterexample-batch4) |
| `DOSSIER-AB16-ARMS-20260802-DC229C4539` | [AB16 十六臂正式实验收据](<../.artifacts/ab16_arms_20260802/EVAL.md>)<br>本机可选的 16-arm frozen-run EVAL；16/16 budget-censored，generated/compiled/applied 均为 0/0/0。 | [`CLAIM-AB16-CAMPAIGN-CLOSEOUT-NO-ATTRIBUTABLE-CUT-RESULT`](#claim-ab16-campaign-closeout-no-attributable-cut-result)<br>[`CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT`](#claim-ab16-no-scientific-cut-result)<br>[`CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS`](#claim-cut-framework-production-status)<br>[`CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`](#claim-raw-eligible-events-required-for-separation-evaluation) | [`DECISION-B6-HOLD-20260803`](#decision-b6-hold-20260803) | [`REVIEW-20260811-AB16-ARMS-BATCH3`](#review-20260811-ab16-arms-batch3) |
| `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-20260727-EA260C6D6B` | [SMM4 fresh-authority 上界闭包](<research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md>)<br>把 SMM-209 与旧 band authority 合并为 U=(1188,18) 的 tracked authority 文书。 | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](#claim-six-predicate-research-ledger)<br>[`CLAIM-SMM-209-EXCLUDES-22X54`](#claim-smm-209-excludes-22x54)<br>[`CLAIM-SMM4-LEX-BAND-COMPOSITION-2086`](#claim-smm4-lex-band-composition-2086) | — | [`REVIEW-20260811-SMM-FRESH-AUTHORITY`](#review-20260811-smm-fresh-authority)<br>[`REVIEW-20260811-SMM-FRESH-AUTHORITY-BATCH2`](#review-20260811-smm-fresh-authority-batch2) |
| `DOSSIER-TRACK-B-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-2026-2C7C3FCD74` | SMM4 fresh-authority local artifact root<br><code>.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727</code><br>External authorization root named by the tracked authority report; intentionally optional and absent from some checkouts. | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](#claim-six-predicate-research-ledger) | — | [`REVIEW-20260812-SMM4-LOCAL-AUTHORITY-AVAILABILITY-BATCH5`](#review-20260812-smm4-local-authority-availability-batch5) |
| `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-STRICT-20260724-F275CFCFE2` | [SMM-209 严格膜不等式](<research/b1_sidewise_marked_membrane_strict_20260724/README.md>)<br>22×54 / 54×22 排除的纸面证明、翻译检查与对抗判读。 | [`CLAIM-SMM-209-EXCLUDES-22X54`](#claim-smm-209-excludes-22x54)<br>[`CLAIM-SMM-COMBINED-CAP-209`](#claim-smm-combined-cap-209)<br>[`CLAIM-SMM-ENDPOINT-TOP-EIGHT-BUDGET-19`](#claim-smm-endpoint-top-eight-budget-19)<br>[`CLAIM-SMM-MARKED-MEMBRANE-BOUND-85`](#claim-smm-marked-membrane-bound-85)<br>[`CLAIM-SMM-OUTSIDE-ACCESS-LOWER-133`](#claim-smm-outside-access-lower-133) | — | [`REVIEW-20260811-SMM-STRICT`](#review-20260811-smm-strict)<br>[`REVIEW-20260811-SMM-STRICT-BATCH2`](#review-20260811-smm-strict-batch2) |
| `DOSSIER-NONCERT-CUTS-AB16-20260724-826CF39625` | [AB16 非认证 cut 实验线](<research/noncert_cuts_ab16_20260724/README.md>)<br>cut 激活暴露、固定运行与 B6 promotion 证据边界。 | [`CLAIM-AB16-CAMPAIGN-CLOSEOUT-NO-ATTRIBUTABLE-CUT-RESULT`](#claim-ab16-campaign-closeout-no-attributable-cut-result)<br>[`CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT`](#claim-ab16-no-scientific-cut-result)<br>[`CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS`](#claim-cut-framework-production-status)<br>[`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](#claim-generic-cp-sat-separation-impossibility-open) | [`DECISION-B6-HOLD-20260803`](#decision-b6-hold-20260803) | [`REVIEW-20260811-NONCERT-CUTS-AB16`](#review-20260811-noncert-cuts-ab16) |
| `DOSSIER-B1-R4-1188-22-PB-20260723-FE5DFB853D` | [Track B/B1：R4 (1188,22) 候选的 proof-bearing 回归](<research/b1_r4_1188_22_pb_20260723/README.md>)<br>给定 A004 几何引理后，2084 个 lex-better orientations 的 OPB、RoundingSat proof、VeriPB 验证与 detached upper-update receipt。 | [`CLAIM-R4-LEX-BAND-2084-UNSAT`](#claim-r4-lex-band-2084-unsat) | — | [`REVIEW-20260811-B1-R4-PB-BATCH2`](#review-20260811-b1-r4-pb-batch2) |
| `DOSSIER-R4-RESPONSE-REVIEW-20260723-D8EBC0DB9D` | [R4 external-response review](<research/r4_response_review_20260723/README.md>)<br>R4 response 的 110-mark census、S+12 marked membrane、t+m≤4、23+23 full-span 排除与完整尺寸必要式。 | [`CLAIM-BODY-ACCESS-BUDGET-1320`](#claim-body-access-budget-1320)<br>[`CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48`](#claim-ordinary-membrane-terminal-bound-s48)<br>[`CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE`](#claim-power-halo-pole-lower-bound-nine)<br>[`CLAIM-R4-BOUNDARY-23-23-FULL-SPAN-EXCLUSION`](#claim-r4-boundary-23-23-full-span-exclusion)<br>[`CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4`](#claim-r4-local-weighted-access-capacity-4)<br>[`CLAIM-R4-MARKED-INCIDENCE-TOTAL-110`](#claim-r4-marked-incidence-total-110)<br>[`CLAIM-R4-MARKED-MEMBRANE-BOUND-S12`](#claim-r4-marked-membrane-bound-s12)<br>[`CLAIM-R4-NECESSARY-DIMENSION-INEQUALITY`](#claim-r4-necessary-dimension-inequality) | — | [`REVIEW-20260811-R4-RESPONSE-BATCH2`](#review-20260811-r4-response-batch2) |
| `DOSSIER-B1-CONDITIONAL-HALO-20260722-0D968A299D` | [Track B/B1 round 2: conditional halo](<research/b1_conditional_halo_20260722/README.md>)<br>All-selected-poles conditional-halo 必要式、actual-P ceiling 账与 512 对 control/treatment 零增量剪枝边界。 | [`CLAIM-B1-CEILING-EXACT-NINE-POLES`](#claim-b1-ceiling-exact-nine-poles)<br>[`CLAIM-B1-CONDITIONAL-HALO-CAPACITY-6650`](#claim-b1-conditional-halo-capacity-6650) | — | [`REVIEW-20260811-B1-CONDITIONAL-HALO-BATCH2`](#review-20260811-b1-conditional-halo-batch2) |
| `DOSSIER-B1-Q-MEMBRANE-HALO-20260722-D054906F9B` | [Track B/B1 round 1: Q/membrane/halo](<research/b1_q_membrane_halo_20260722/README.md>)<br>Boundary Q 交叠、ordinary membrane 与 tangential endpoint 修正形成的 B1-QMH 必要不等式及其双计数边界。 | [`CLAIM-B1-QMH-REFINED-MEMBRANE-INEQUALITY`](#claim-b1-qmh-refined-membrane-inequality) | — | [`REVIEW-20260811-B1-QMH-BATCH2`](#review-20260811-b1-qmh-batch2) |
| `DOSSIER-R3-UPPER-BOUND-PB-20260722-60ED8947CD` | [Track B/B0：R3 (1190,34) 算术层的 PB/VeriPB 链](<research/r3_upper_bound_pb_20260722/README.md>)<br>R3 shared body/access、ordinary membrane 与 power 前件，以及给定几何引理后的 2074-orientation PB/VeriPB 算术闭包。 | [`CLAIM-BODY-ACCESS-BUDGET-1320`](#claim-body-access-budget-1320)<br>[`CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48`](#claim-ordinary-membrane-terminal-bound-s48)<br>[`CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE`](#claim-power-halo-pole-lower-bound-nine)<br>[`CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY`](#claim-r3-lex-band-2074-unsat-given-geometry) | — | [`REVIEW-20260811-R3-UPPER-BOUND-PB-BATCH2`](#review-20260811-r3-upper-bound-pb-batch2) |
| `DOSSIER-RULES-AUDIT-20260718-A447D60E10` | [规则语义审计与 owner 裁决](<research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md>)<br>当前 strict empty-rectangle 语义与相关游戏规则裁决的 tracked 证据包。 | [`CLAIM-EMPTY-RECTANGLE-ROUTING-ALLOWED-SUPERSEDED`](#claim-empty-rectangle-routing-allowed-superseded)<br>[`CLAIM-EMPTY-RECTANGLE-STRICT`](#claim-empty-rectangle-strict)<br>[`CLAIM-STRICTER-FEASIBLE-SET-PRESERVES-NEGATIVE-NOT-POSITIVE`](#claim-stricter-feasible-set-preserves-negative-not-positive)<br>[`CLAIM-WAREHOUSE-BRIDGE-EXCLUSION-TARGET-CONDITIONAL`](#claim-warehouse-bridge-exclusion-target-conditional) | [`DECISION-EMPTY-RECTANGLE-STRICT-20260805`](#decision-empty-rectangle-strict-20260805) | [`REVIEW-20260811-RULES-AUDIT`](#review-20260811-rules-audit)<br>[`REVIEW-20260811-RULES-AUDIT-BATCH4`](#review-20260811-rules-audit-batch4) |
| `DOSSIER-CLEANROOM-REDERIVATION-20260718-41375BBFE3` | [R- 价签精算交付包](<research/cleanroom_rederivation_20260718/25_rstar_pricetag_delivery_20260804/README.md>)<br>本交付包按 00ASK.md 完成九条充分限制的价签、前提集、撤退线和判定实验设计；authority=false，不登记任何界，账本不变。【已证明】 | [`CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE`](#claim-band22-v0a-strict-hole-incompatible) | — | [`REVIEW-20260811-BAND22-CLEANROOM-V0A-BATCH2`](#review-20260811-band22-cleanroom-v0a-batch2) |
| `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-2B25E2B21B` | [front offset 本地复验收据](<../.artifacts/front_offset_incident_20260718/history.json>)<br>事故修复批的本机可选日志与结构化收据。 | [`CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED`](#claim-front-offset-pre-0718-superseded)<br>[`CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED`](#claim-r1-1326-34-strict-upper-revalidated) | — | [`REVIEW-20260811-FRONT-OFFSET-ARTIFACT-BATCH4`](#review-20260811-front-offset-artifact-batch4) |
| `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-7F16095D41` | [front offset 事故与历史重判](<research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md>)<br>旧 front 坐标重复偏移的根因、修复与历史结论有效性边界。 | [`CLAIM-24-LEVER-FRAMEWORK-EXHAUSTED-SUPERSEDED`](#claim-24-lever-framework-exhausted-superseded)<br>[`CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED`](#claim-front-offset-double-step-semantics-superseded)<br>[`CLAIM-FRONT-OFFSET-HISTORICAL-REJUDGMENT-40`](#claim-front-offset-historical-rejudgment-40)<br>[`CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED`](#claim-front-offset-pre-0718-superseded)<br>[`CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`](#claim-lever-verdicts-are-item-and-revision-bounded)<br>[`CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED`](#claim-r1-1326-34-strict-upper-revalidated)<br>[`CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN`](#claim-rab-fcl-front-dependent-performance-withdrawn)<br>[`CLAIM-ROUND45-CORRECTED-PROFILE-UNKNOWN-NOT-STRUCTURAL-WALL`](#claim-round45-corrected-profile-unknown-not-structural-wall)<br>[`CLAIM-SHARED-ENCODING-AGREEMENT-NOT-INDEPENDENT-VALIDATION`](#claim-shared-encoding-agreement-not-independent-validation) | — | [`REVIEW-20260811-FRONT-OFFSET-INCIDENT`](#review-20260811-front-offset-incident)<br>[`REVIEW-20260811-FRONT-OFFSET-INCIDENT-BATCH4`](#review-20260811-front-offset-incident-batch4) |
| `DOSSIER-WITNESS-CONSTRUCTOR-20260717-5F04E123B3` | [whole-layout witness constructor 线](<research/witness_constructor_20260717/07_routing_aware/README.md>)<br>当前 tracked witness 构造与 routing-aware 尝试入口；没有登记成功 lower witness。 | [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](#claim-certified-existence-open)<br>[`CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN`](#claim-witness-restricted-pole-domains-infeasible-full-domain-open) | — | [`REVIEW-20260811-WITNESS-CONSTRUCTOR`](#review-20260811-witness-constructor)<br>[`REVIEW-20260811-WITNESS-CONSTRUCTOR-BATCH4`](#review-20260811-witness-constructor-batch4) |
| `DOSSIER-RAB-SEP-PROMOTION-20260716-CF6D536C85` | [01 — ①′ 第一段：front-free 必要性 soundness 审查（v2 修订版，2026-07-16，对抗验证完成）](<research/rab_sep_promotion_20260716/01_front_free_necessity_soundness_review.md>)<br>RAB/front-clear separator 的 soundness、telemetry、promotion 与后续失效历史；batch3 只提炼 raw-event 评价原则。 | [`CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN`](#claim-rab-fcl-front-dependent-performance-withdrawn)<br>[`CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`](#claim-raw-eligible-events-required-for-separation-evaluation) | — | [`REVIEW-20260811-RAB-SEP-PROMOTION-BATCH3`](#review-20260811-rab-sep-promotion-batch3)<br>[`REVIEW-20260811-RAB-SEP-PROMOTION-BATCH4`](#review-20260811-rab-sep-promotion-batch4) |
| `DOSSIER-BATCH-CE-ATTACH-HOST-20260712-D4A08ECB0B` | [Batch C/E attach-host evidence line](<research/batch_ce_attach_host_20260712/01_batch_c_execution_plan_draft.md>)<br>Cut attach-host、prod-form mirror 和 fail-closed 修复证据；证明 consumer 接线边界，不授权 autonomous separation 或 production attach。 | [`CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM`](#claim-typed-cut-pipeline-consumes-known-cuts-not-discovers-them) | — | [`REVIEW-20260811-BATCH-CE-ATTACH-HOST`](#review-20260811-batch-ce-attach-host)<br>[`REVIEW-20260811-BATCH-CE-ATTACH-HOST-BATCH3`](#review-20260811-batch-ce-attach-host-batch3) |
| `DOSSIER-P1-3A-ATTACH-POWER-ON-SPIKE-20260710-25E1F679CB` | [P1.3A attach 通电 spike 规格书（主会话亲写定稿，2026-07-10 夜）](<research/p1_3a_attach_power_on_spike_20260710/02_spike_evidence.md>)<br>约 10K synthetic redundant F5 的真实 step-8 通电与 overhead 证据；只覆盖工程接线，不覆盖 cut 科学效力。 | [`CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY`](#claim-attach-spikes-engineering-not-cut-efficacy) | — | [`REVIEW-20260811-P1-3A-ATTACH-POWER-ON-BATCH3`](#review-20260811-p1-3a-attach-power-on-batch3) |
| `DOSSIER-HISTORY-TOOLCHAIN-ORIGIN-20260709-411160EC29` | [工具链起源考古：「自建 cut framework」决策的调研与最初设计（2026-07-09）](<research/history_toolchain_origin_20260709/README.md>)<br>cut-language thesis、专用 cut/proof 工具链、oracle/validator 分工与早期 lifecycle 的 tracked 起源考古。 | [`CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS`](#claim-discovery-and-validation-separate-obligations)<br>[`CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM`](#claim-typed-cut-pipeline-consumes-known-cuts-not-discovers-them) | — | [`REVIEW-20260811-HISTORY-TOOLCHAIN-ORIGIN-BATCH3`](#review-20260811-history-toolchain-origin-batch3) |
| `DOSSIER-P1-3A-ATTACH-SIZING-SPIKE-20260708-02F3C50E2F` | [P1.3A attach sizing spike — verdict（2026-07-08）](<research/p1_3a_attach_sizing_spike_20260708/verdict.md>)<br>增量 attach 形态与容量 sizing 的工程 GO；明确不证明收敛、P1.3 完成或 production promotion。 | [`CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY`](#claim-attach-spikes-engineering-not-cut-efficacy) | — | [`REVIEW-20260811-P1-3A-ATTACH-SIZING-BATCH3`](#review-20260811-p1-3a-attach-sizing-batch3) |
| `DOSSIER-P1-3-M5-CONVERGENCE-20260708-A96D060024` | [M5 A/B 首战:产品默认 solve 参数病态的单变量归因(2026-07-11 凌晨)](<research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md>)<br>M5 归因判决(m5c1memoryattribution20260710.md)与 attach spike E1 系列(../p13aattachpoweronspike20260710/01spikespec.md)两次把「产品默认 solve 参数(FIXEDSEARCH+probing3+symmetry3… | [`CLAIM-M5-DEATHS-REQUIRE-RESOURCE-BUILD-AND-PARAMETER-SEPARATION`](#claim-m5-deaths-require-resource-build-and-parameter-separation)<br>[`CLAIM-M5-DEFAULT-SOLVE-PARAMETERS-PATHOLOGICAL-REFUTED`](#claim-m5-default-solve-parameters-pathological-refuted) | — | [`REVIEW-20260811-M5-CONVERGENCE-BATCH4`](#review-20260811-m5-convergence-batch4) |
| `DOSSIER-P1-2B-F7-POWER-HITTING-SET-GEMINI-ROUND2-20260525-C4D8B4A483` | [p1 2b f7 power hitting set gemini round2 20260525](<research/p1_2b_f7_power_hitting_set_gemini_round2_20260525/gemini_response.md>)<br>NOTGO | [`CLAIM-F7-FACILITY-MASK-VALIDATOR-BUG-REPAIRED`](#claim-f7-facility-mask-validator-bug-repaired) | — | [`REVIEW-20260811-F7-ROUND2-BATCH4`](#review-20260811-f7-round2-batch4) |
| `DOSSIER-P1-2B-F7-POWER-HITTING-SET-GEMINI-ROUND1-20260525-DB49AFB525` | [p1 2b f7 power hitting set gemini round1 20260525](<research/p1_2b_f7_power_hitting_set_gemini_round1_20260525/gemini_response.md>)<br>NOTGO | [`CLAIM-F7-FACILITY-MASK-VALIDATOR-BUG-REPAIRED`](#claim-f7-facility-mask-validator-bug-repaired) | — | [`REVIEW-20260811-F7-ROUND1-BATCH4`](#review-20260811-f7-round1-batch4) |
| `DOSSIER-SMT-MT-OUTER-PRUNING-PHASE1-20260521-DF50598CC0` | [SMT-MT Outer Pruning Phase 1 (2026-05-21)](<research/smt_mt_outer_pruning_phase1_20260521/README.md>)<br>Phase 1 wires the SMT Modulo Monotonic Theories outer pruning engine into src/search/outersearch.py behind EXACTSMTMTOUTERPRUNING=1 env flag. Phase 0 cheap-gat… | [`CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER`](#claim-smt-mt-synthetic-go-not-transferable-to-real-inner) | — | [`REVIEW-20260811-SMT-MT-PHASE1-BATCH4`](#review-20260811-smt-mt-phase1-batch4) |
| `DOSSIER-SMT-MT-OUTER-PRUNING-PHASE0-20260521-042BF3000C` | [SMT-MT Outer Pruning Phase 0 (2026-05-21)](<research/smt_mt_outer_pruning_phase0_20260521/README.md>)<br>Phase 0 cheap-gate probe for SMT Modulo Monotonic Theories (Bayless et al., AAAI 2015) outer-search pruning. Mocks the inner solver with a Dummy threshold/rand… | [`CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER`](#claim-smt-mt-synthetic-go-not-transferable-to-real-inner) | — | [`REVIEW-20260811-SMT-MT-PHASE0-BATCH4`](#review-20260811-smt-mt-phase0-batch4) |
| `DOSSIER-CAND-C-COLUMN-GENERATION-PHASE2-20260521-9625F52BA3` | [Phase 2 — Column Generation: share cache + Ryan-Foster + 160/266 + routing-aware + boundary equality](<research/cand_c_column_generation_phase2_20260521/README.md>)<br>Date: 2026-05-21 Paradigm: cand C (column generation / branch-and-price) Predecessor: candccolumngenerationphase120260521/ — 4/4 ramp GO (5/20/40/80 inst, m10… | [`CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO`](#claim-column-generation-phase2-scale-route-no-go) | — | [`REVIEW-20260811-COLUMN-GENERATION-PHASE2-BATCH4`](#review-20260811-column-generation-phase2-batch4) |
| `DOSSIER-PARADIGM-SEARCH-REVIEW-V12-WITH-CODE-20260520-FC02CE09A5` | [v12 Paradigm Search Review (with code) — 2026-05-20](<research/paradigm_search_review_v12_with_code_20260520/README.md>)<br>项目在 CP-SAT + LBBD framework 内 24 lever 全 verdict 死之后, 调研了 32 个 paradigm 方向看是否有现成可调用的 algorithm 范式能 break. 4 个候选方向仍 alive, 其余 NO-GO. 包整理这些调研结果 + 24 lever 历史实施 +… | [`CLAIM-24-LEVER-FRAMEWORK-EXHAUSTED-SUPERSEDED`](#claim-24-lever-framework-exhausted-superseded)<br>[`CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`](#claim-lever-verdicts-are-item-and-revision-bounded) | — | [`REVIEW-20260811-PARADIGM-LEVER-HISTORY-BATCH4`](#review-20260811-paradigm-lever-history-batch4) |
| `DOSSIER-LEVER25-IHS-PHASE0-20260520-4194EBD09A` | [Lever 25 IHS (Implicit Hitting Set) — Phase 0 cheap gate](<research/lever25_ihs_phase0_20260520/README.md>)<br>Lever 25 explores the Implicit Hitting Set (IHS) paradigm as an alternative to standard LBBD cut accumulation. Instead of adding each oracle-extracted core dir… | [`CLAIM-IHS-SINGLETON-CORE-COMPRESSION-PHASE0-NO-GO`](#claim-ihs-singleton-core-compression-phase0-no-go) | — | [`REVIEW-20260811-IHS-PHASE0-BATCH4`](#review-20260811-ihs-phase0-batch4) |
| `DOSSIER-PHASE0-LAZY-POWER-COMPLETION-20260517-2DD76729CA` | [Phase 0 mini-PoC verdict — Lazy Power Completion v1](<research/phase0_lazy_power_completion_20260517/README.md>)<br>GPT v11 提的 Lazy Power Completion 架构 (master 跳 coverage 留 pole slot + completion subproblem 解电杆) 的 Phase 0 止损 gate 实测. | [`CLAIM-LAZY-POWER-INSTANCE-POSE-CUT-ROUTE-NO-GO`](#claim-lazy-power-instance-pose-cut-route-no-go) | — | [`REVIEW-20260811-LAZY-POWER-PHASE0-BATCH4`](#review-20260811-lazy-power-phase0-batch4) |
| `DOSSIER-P1-2-V99-CLOSE-KERNEL-SEALING-207F650E44` | [P1.2 V99 close-kernel sealing](<research/p1_2_v99_close_kernel_sealing.md>)<br>P1.2 proof-bearing sink 与 close-kernel 的 tracked review anchor。 | — | [`DECISION-P1-2-CLOSE-20260707`](#decision-p1-2-close-20260707)<br>[`DECISION-P1-2-RECLOSE-20260806`](#decision-p1-2-reclose-20260806) | [`REVIEW-20260811-P1-2-V99-CLOSE-KERNEL`](#review-20260811-p1-2-v99-close-kernel) |

## 人工精编 dossier

| Dossier ID | 日期 | 标题 / 入口 | topics | lifecycle | relevance |
|---|---|---|---|---|---|
| `DOSSIER-P-REINSERTION-AUDIT-20260820-8BB5417ED3` | `2026-08-20` | [PREINSERTIONGAP 异源验收报告](<../.artifacts/p_reinsertion_audit_20260820/AUDIT_REPORT.md>)<br>异源验收证据包；包内总判词/状态：PASS_WITH_SCOPED_ERRATA_LOCALIZATION_UNDER_DETERMINED。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-MUS-LANDSCAPE-20260820-CC6900A234` | `2026-08-20` | p mus landscape 20260820<br><code>.artifacts/p_mus_landscape_20260820</code><br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：在途、未封账。仅作为 active open workflow 进入 inventory，不进入 historical triage，… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-CPU-L3-PERF-MEASUREMENT-20260820-212859A058` | `2026-08-20` | [CPU 大三缓选购 perf 实测批 — REPORT](<../.artifacts/cpu_l3_perf_measurement_20260820/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE_RESEARCH_ONLY_NON_AUTHORIZING。验收状态：包内状态 COMPLETE_RESEARCH_ONLY_NON_AUTHORIZING；REVIEW_CHECKLIST 无对应异源验收节；出处：无对应 REVIEW_CHE… | `solver-experiment` | `active` | `unreviewed` |
| `DOSSIER-P-SIGNATURE-COOCCURRENCE-MATRIX-20260819-51366B1E18` | `2026-08-19` | [签名层逐事件成员集与共现矩阵](<../.artifacts/p_signature_cooccurrence_matrix_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS。验收状态：包内 checker/负测封账；REVIEW_CHECKLIST 未给出后续独立异源终结节；出处：REVIEW_CHECKLIST.md lines 155-173。 本登记不是 knowledge semantic review，不新增或升… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-NARROW-CORE-READMISSION-20260819-CD8FDB7CD0` | `2026-08-19` | [窄核重准入与几何证书对账](<../.artifacts/p_narrow_core_readmission_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE_RESEARCH_ONLY（最终判词见 REPORT.md §1）。验收状态：REVIEW_CHECKLIST 仍列待终检项，未见独立异源终结节；出处：REVIEW_CHECKLIST.md lines 257-297。 本登记不是 knowl… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-INTERIOR-BOUND-AUDIT-20260819-54D94C5C37` | `2026-08-19` | [异源验收：BINTERIOR 内部封锁精确下界包审计](<../.artifacts/p_interior_bound_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：CONFIRMED（定理本体）+ NEEDS_CORRECTION（语料观测与 3×3 护栏）。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 prod… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-REALIZABLE-AUDIT-20260819-9056A4CF0C` | `2026-08-19` | [异源验收：BDNFREALIZABLE 可实现 completeness 证据包审计](<../.artifacts/p_dnf_realizable_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：CONFIRMED（科学结论）+ NEEDS_CORRECTION（作用域叙述与独立性分层）。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 produ… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-ENUMERATION-AUDIT-20260819-AC4209EBC5` | `2026-08-19` | [异源验收：BDNFENUMERATE 可实现封锁构型完整枚举包审计](<../.artifacts/p_dnf_enumeration_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：CONFIRMED（全部数值）+ NEEDS_CORRECTION（作用域叙述）。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-UNIVERSAL-AUDIT-20260819-B7FD9D9756` | `2026-08-19` | [异源验收：BDNF 普适 soundness 证据包审计](<../.artifacts/p_dnf_universal_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：两条头条结论均确认；另有三条叙述/工程卫生修正。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production authority。 | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-COMPLETENESS-AUDIT-20260819-8A148379D6` | `2026-08-19` | [异源验收：BDNF 普适 completeness 证据包审计](<../.artifacts/p_dnf_completeness_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：三条头条结论在各自声明域内均正确；证据选择与若干解释项 NEEDS_CORRECTION。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 product… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-INTERIOR-3X3-AUDIT-20260819-AB3571C590` | `2026-08-19` | [异源验收：.artifacts/pinterior3x3bound20260819](<../.artifacts/p_interior_3x3_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：NEEDS_CORRECTION；全部数值结论 CONFIRMED。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production authori… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-BRANCH-SOUNDNESS-MINIMAL-CORE-20260819-99AFD08610` | `2026-08-19` | [九支 DNF：分支级普适 soundness 与端点原子最小核](<../.artifacts/p_dnf_branch_soundness_minimal_core_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_ALL_NINE_UNIVERSALLY_SOUND_FULL_DROP_ONE_COMPLETE。验收状态：异源验收确认核心结论，声明层按勘误收窄；出处：REVIEW_CHECKLIST.md lines 270-286。 勘误后解释入口：.arti… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-ZEROPOLE-AUDIT-20260819-7D071A5EF4` | `2026-08-19` | [PZEROPOLE 异源验收报告](<../.artifacts/p_zeropole_audit_20260819/AUDIT_REPORT.md>)<br>异源验收证据包；包内总判词/状态：CONFIRMED_WITH_CORRECTIONS。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production authority。 | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-BRIDGE-LIVENESS-PROBE-20260819-799812E3E4` | `2026-08-19` | p bridge liveness probe 20260819<br><code>.artifacts/p_bridge_liveness_probe_20260819</code><br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-ZEROPOLE-DIAGNOSIS-20260819-442FFB6551` | `2026-08-19` | [GZEROPOLEDIAGNOSIS：30×39 重建布局的零 coverer target 归因](<../.artifacts/p_zeropole_diagnosis_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_ZERO_COVERER_CAUSE_DISTRIBUTION_GEOMETRY_DOMINANT_NO_SELECTION_OPEN。验收状态：异源验收 CONFIRMED_WITH_CORRECTIONS；承重数字零偏差；出处：REVIEW_CHE… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-INTERIOR-BLOCKADE-BOUND-20260819-7F5A5AA51B` | `2026-08-19` | [BINTERIOR：内部供电锚点封锁的完整容量定理与实例观测](<../.artifacts/p_interior_blockade_bound_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_EXACT_MINIMUM_SEVEN_AND_CORPUS_OBSERVED。验收状态：异源验收确认数值，语料解释、作用域和前提需勘误；出处：REVIEW_CHECKLIST.md lines 411-449。 勘误后解释入口：.artifacts/… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-REALIZABLE-COMPLETENESS-20260819-F79B0B2A8C` | `2026-08-19` | [BDNFREALIZABLE：可实现几何上的 completeness 与冻结模板代表性](<../.artifacts/p_dnf_realizable_completeness_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：REFUTED_REALIZABLE_COMPLETENESS_BOTH_ARITIES_EXACT_GEOMETRY_COUNTEREXAMPLES。验收状态：异源验收确认科学结论，作用域叙述与独立性需更正；出处：REVIEW_CHECKLIST.md lin… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-REALIZABLE-ENUMERATION-20260819-796C6E270A` | `2026-08-19` | [BDNFENUMERATE：可实现供电封锁构型的完整枚举](<../.artifacts/p_dnf_realizable_enumeration_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE_BOTH_ARITIES_EXACT_REALIZABLE_BLOCKADE_CATALOG。验收状态：异源验收确认作用域内枚举，shape scope 与共模边界需勘误；出处：REVIEW_CHECKLIST.md lines 379-407… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-UNIVERSAL-COMPLETENESS-20260819-26F6F7EF75` | `2026-08-19` | [BDNFCOMPLETE：九支 DNF 的普适 completeness 与冻结模板库隐式不变量](<../.artifacts/p_dnf_universal_completeness_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：REFUTED_UNIVERSAL_COMPLETENESS_BOTH_ARITIES_FINITE_PARTITION_AND_LIBRARY_INVARIANTS_PROVED。验收状态：异源验收完成；反例与数值存活，作用域/证据归属需勘误；出处：REVIE… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-BLOCKADE-CLIPMAP-20260819-5F53E26B00` | `2026-08-19` | [BCLIPMAP：全网格 ghost-free 最小封锁数图](<../.artifacts/p_blockade_clipmap_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_COMPLETE_GHOST_FREE_CLIPMAP_GHOST_OVERLAY_AND_CATALOG_RECONCILIATION。验收状态：异源验收总判词 NEEDS_CORRECTION；数值零分歧，声明层勘误；出处：REVIEW_CHECK… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-CLIPMAP-AUDIT-20260819-0CC22B0448` | `2026-08-19` | [BCLIPMAP 异源验收报告](<../.artifacts/p_clipmap_audit_20260819/AUDIT_REPORT.md>)<br>异源验收证据包；包内总判词/状态：NEEDS_CORRECTION；全部独立重算数值零分歧，修正限于声明层。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production auth… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-INTERIOR-3X3-BOUND-20260819-3503337709` | `2026-08-19` | [B3X3：内部 3×3 需电目标的精确封锁下界与 pole 统一语义](<../.artifacts/p_interior_3x3_bound_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_EXACT_MINIMUM_SIX_AND_POLE_ACCOUNTING_RESOLVED。验收状态：异源验收总判词 NEEDS_CORRECTION；数值由独立第三模型复现；出处：REVIEW_CHECKLIST.md lines 453-493。… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-REINSERTION-GAP-20260819-2C69D7570F` | `2026-08-19` | [AREINSERTIONGAP：13-event 走廊的重插入缺口机制](<../.artifacts/p_reinsertion_gap_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_JOINT_COUPLING_TWO_ATOM_SELF_POWER_MUS。验收状态：异源验收 PASS_WITH_SCOPED_ERRATA_LOCALIZATION_UNDER_DETERMINED；出处：REVIEW_CHECKLIST.md… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-TRUE-REPAIR-CONFLICT-EXTRACTION-20260819-DAB640A917` | `2026-08-19` | [A3：真重排无条件 conflict 提炼环](<../.artifacts/p_true_repair_conflict_extraction_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：REPORT_FINALIZED_NO_SEPARATE_TERMINAL_RECEIPT。验收状态：异源验收完成；科学结论成立，但招牌负面归因被包内库存推翻；出处：REVIEW_CHECKLIST.md lines 233-255。 本登记不是 knowled… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-CFG-RELAXATION-CERTIFICATES-20260818-76C8EC34D8` | `2026-08-18` | [配置松弛纯有理对偶证书与负控（2026-08-18）](<../.artifacts/cfg_relaxation_certificates_20260818/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `upper-bound`, `formal-verification` | `active` | `unreviewed` |
| `DOSSIER-P-TRUE-REPLACEMENT-REPAIR-20260818-3044681953` | `2026-08-18` | [真重排语义下的供电修复走廊](<../.artifacts/p_true_replacement_repair_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_TRUE_REPLACEMENT_INTERVALS_OPEN_WITH_TYPED_CENSORING。验收状态：异源结构与语义审计已完成，结论带六项链条缺口；出处：REVIEW_CHECKLIST.md lines 18-24。 本登记不是 kno… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-TRUE-REPAIR-CHAIN-HARDENING-20260818-AF82028E42` | `2026-08-18` | [真重排修复走廊证据链补链批](<../.artifacts/p_true_repair_chain_hardening_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_TRUE_REPAIR_EVIDENCE_CHAIN_HARDENED。验收状态：异源验收完成；科学区间存活，能力抬头与独立性需收窄；出处：REVIEW_CHECKLIST.md lines 48-90。 本登记不是 knowledge semanti… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-NOVELTY-STAGNATION-WINDOWS-20260818-570D7BA230` | `2026-08-18` | [死因谱新颖性停滞点与可压缩性梯度](<../.artifacts/p_novelty_stagnation_windows_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_OFFLINE_NOVELTY_STAGNATION_AND_COMPRESSIBILITY_GRADIENT_COMPLETE。验收状态：收割终稿已封账；REVIEW_CHECKLIST 的追溯终检项仍未显式勾销；出处：REVIEW_CHECKLIS… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-CSPACE-BLOCKADE-COMPILER-20260818-F304516884` | `2026-08-18` | [构型空间供电封锁编译器试点三](<../.artifacts/p_cspace_blockade_compiler_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_REUSABLE_CSPACE_BLOCKADE_COMPILER_RESEARCH_ONLY。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-GHOSTFRONT-FAMILY-JUDGMENT-20260818-2441DB4B52` | `2026-08-18` | [幽灵矩形前格封锁的四原子家族化 Judgment](<../.artifacts/p_ghostfront_family_judgment_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_FOUR_ATOM_PARAMETERIZED_FAMILY_JUDGMENT_RESEARCH_ONLY。验收状态：收割终稿已封账；REVIEW_CHECKLIST 的追溯终检项仍未显式勾销；出处：REVIEW_CHECKLIST.md lines… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-CANDIDATE-CONDITION-MATRIX-V1-20260818-780443B8C2` | `2026-08-18` | [常设候选×条件值矩阵 v1](<../.artifacts/candidate_condition_matrix_v1_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不新增或升格 claim。 | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-POSTMEM-BLIND-COLLISION-20260818-4DB4F7129F` | `2026-08-18` | [postmem 盲测 B 段对撞裁断](<../.artifacts/postmem_blind_collision_20260818/COLLISION_REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：ARTIFACT 7 / NEW 2 / REDISCOVERED 1 / CONTRADICTS 1。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 勘误后解释入口：.artifact… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P0-FRONTIER-RERUN-20260818-DDAC26E3F1` | `2026-08-18` | [P0：current claim 账本到 production 矩形前沿的保守投影](<../.artifacts/p0_frontier_rerun_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：MANIFEST_SEALED_NO_TOP_LEVEL_STATUS。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-EMITTER-PROVENANCE-RECONCILIATION-20260818-8050D1C018` | `2026-08-18` | p emitter provenance reconciliation 20260818<br><code>.artifacts/p_emitter_provenance_reconciliation_20260818</code><br>Inventory-only 登记。包内终态判词/状态：MANIFEST_SEALED_NO_TOP_LEVEL_STATUS。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-MIXED-ENDPOINT-CLOSED-FORM-20260818-2E5F56A8F8` | `2026-08-18` | [Mixed family 端点不等式显式闭式](<../.artifacts/p_mixed_endpoint_closed_form_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_NINE_BRANCH_CLOSED_FORM_AND_EXTENSION_PROBE_COMPLETE。验收状态：收割终稿已封账；REVIEW_CHECKLIST 未给出独立异源终结节；出处：REVIEW_CHECKLIST.md lines 5-2… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-LBBD-MINIMAL-CORE-TOOLKIT-20260818-8B00079DD2` | `2026-08-18` | [LBBD Layered Minimization Toolkit](<../.artifacts/p_lbbd_minimal_core_toolkit_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不新增或升格 claim。 | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-NOVELTY-L3-CONTRACT-HARDENING-20260818-304523520A` | `2026-08-18` | [L3 触发器证据契约补强](<../.artifacts/p_novelty_l3_contract_hardening_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不新增或升格 claim。 | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-CORE-SHELL-PROPOSITION-20260818-C3CC2E9F4F` | `2026-08-18` | [deep v2 事件固定核心 ⊕ 可变壳层命题](<../.artifacts/p_core_shell_proposition_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS。验收状态：异源勘误闭合；按包内 ERRATA 与边界声明图解释；出处：REVIEW_CHECKLIST.md lines 92-173。 勘误后解释入口：.artifacts/p_core_shell_proposition_20260818/ERRA… | `other` | `active` | `unreviewed` |
| `DOSSIER-GPT-HARVEST-20260818-85692BD024` | `2026-08-18` | [A1 真重排修复走廊补链批 —— GPT 终稿](<../.artifacts/gpt_harvest_20260818/A1_FINAL_MESSAGE.md>)<br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `documentation-governance`, `reasoning-system` | `active` | `unreviewed` |
| `DOSSIER-P-LBBD-30X39-MULTI-INCUMBENT-20260818-0C7F9B4622` | `2026-08-18` | [30×39 多 incumbent 三层死因谱稳定性研究](<../.artifacts/p_lbbd_30x39_multi_incumbent_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_WITH_TYPED_GEOMETRY_CENSORING。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不新… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-CFG-RELAXATION-ENUM-CLOSURE-23X51-20260818-176509E438` | `2026-08-18` | [23×51 配置松弛枚举完备性封口（2026-08-18）](<../.artifacts/cfg_relaxation_enum_closure_23x51_20260818/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `upper-bound`, `formal-verification` | `active` | `unreviewed` |
| `DOSSIER-CFG-RELAXATION-IMPL-B-20260817-77A5280EF9` | `2026-08-17` | [配置松弛 support 独立实现 B（2026-08-17）](<../.artifacts/cfg_relaxation_impl_B_20260817/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `upper-bound`, `formal-verification` | `active` | `unreviewed` |
| `DOSSIER-CFG-RELAXATION-IMPL-A-20260817-BE414F298A` | `2026-08-17` | [配置松弛 support 独立实现 A（2026-08-17）](<../.artifacts/cfg_relaxation_impl_A_20260817/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `upper-bound`, `formal-verification` | `active` | `unreviewed` |
| `DOSSIER-NP-THEOREM-CORRESPONDENCE-20260817-6ADFE32DF1` | `2026-08-17` | [自产结构定理与数学文献对应关系](<../.artifacts/np_theorem_correspondence_20260817/GPT_CORRESPONDENCE.md>)<br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-NP-LITERATURE-RECON-20260817-C6D0998D78` | `2026-08-17` | [数学文献侦察：六堵墙的同族成果与三条高价值外环模板](<../.artifacts/np_literature_recon_20260817/GPT_MATH_RECON.md>)<br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-OUTER-LOOP-RECON-20260817-A3301A1D74` | `2026-08-17` | [推理外环三实验对账裁断全文（2026-08-17）](<../.artifacts/outer_loop_recon_20260817/B_VERDICT_FULL_20260817.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-POSTMEM-BLIND-SAMPLING-20260817-2127AF445D` | `2026-08-17` | postmem blind sampling 20260817<br><code>.artifacts/postmem_blind_sampling_20260817</code><br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P5-HORIZONTAL-LOWERING-CANARY-20260817-3DBC7800A0` | `2026-08-17` | [P5 水平边界供电封锁 lowering 金丝雀（2026-08-17）](<research/p5_horizontal_lowering_canary_20260817/README.md>)<br>P5 已执行 HORIZONTAL-BOUNDARY-MIDDLE-TARGET-SHELL-V1 的 research-only pose-bool lowering canary：六个 group-pose 事件被精确编译为一条 sum<=5 约束，producer 外重建与 proto replay 逐字节通过… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P5-HORIZONTAL-CANARY-20260817-44EADE5C7E` | `2026-08-17` | [P5 水平边界供电封锁 lowering 金丝雀本地证据包（2026-08-17）](<../.artifacts/p5_horizontal_canary_20260817/REPORT.md>)<br>P5 本机证据包保存 owner 授权、消费点对账、三臂 body-generation run、六份 binary CpModel proto、producer 外独立 replay、编译义务闭合、typed endpoint 与终局报告。静态 lowering PASS；三臂均在首 incumbent 前删失，r… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P4-BLOCKADE-FAMILY-ABSTRACTION-20260817-284FD8D3B0` | `2026-08-17` | [P4 区域供电封锁 family 抽象与定理化（2026-08-17）](<research/p4_blockade_family_abstraction_20260817/README.md>)<br>P4 将 P1b/P3 的局部供电封锁机制拆为水平边界中间 target、双边界角 target 与 5×5/6×4/4×6 混合矩形三类 group-pose family。水平类通过 1,728 个正例与 6,708 个系统反例并具备 2 个自然 occurrence，技术义务已闭合到只剩 owner lower… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P4-BLOCKADE-FAMILY-ABSTRACTION-20260817-5B9F642CB4` | `2026-08-17` | [P4 区域供电封锁 family 抽象与定理化本地证据包（2026-08-17）](<../.artifacts/p4_blockade_family_abstraction_20260817/REPORT.md>)<br>P4 本机证据包保存三类 Judgment、三个独立标准库 checker、1,728／48／664 条正域证据、6,708／136／142 条 near-miss 结果、九布局 corpus 投影、编译义务、水平类 owner-gated canary 草案与 typed 终局。payload 可在轻量 check… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P3-POWER-BLOCKADE-VALIDATION-20260817-3DC75D9C7A` | `2026-08-17` | [P3 区域供电封锁 family 验证（2026-08-17）](<research/p3_power_blockade_validation_20260817/README.md>)<br>P3 对 P1b 底边六块供电封锁候选做小样本 incidence、37 个近失配、1098 个纵向／target 换位、双 master 只读 literal 审计与 5×5/6×4/4×6 混合模板探针。候选被收窄为网格边界壳机制并获得扩展正样本，但仍未晋升为 claim、cut、certified 或 prod… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P3-POWER-BLOCKADE-VALIDATION-20260817-DA81BA8459` | `2026-08-17` | [P3 区域供电封锁 family 验证本地证据包（2026-08-17）](<../.artifacts/p3_power_blockade_validation_20260817/REPORT.md>)<br>P3 本机证据包保存 42 文件样本盘点、37 个近失配、1098 个纵向／target 换位、7 个 mixed-template 正样本、两种 master 的只读 literal 审计与 typed 终局。payload 可缺失；其存在不授予 claim、cut、certified、下界或 production… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P1B-JOINT-POWER-REPAIR-20260817-C459AE609C` | `2026-08-17` | [P1b 九窗口联合修复与区域供电封锁候选（2026-08-17）](<research/p1b_joint_power_repair_20260817/README.md>)<br>P1b 在未取得完整 witness、完整 verifier 未到达且 canonical L 保持 absent 的边界下，将 P1 family A 的 266 实例供电 nogood 收缩为 6 姿态全局最小局部核，并提出经 56 个水平平移独立复算的底边 5×5 六块 Hall 型封锁候选。该对象仅为 P3/… | `reasoning-system`, `witness-lower-bound`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P1B-JOINT-POWER-REPAIR-20260817-8F6B7DFD94` | `2026-08-17` | [P1b 九窗口联合修复与区域供电封锁候选本地证据包（2026-08-17）](<../.artifacts/p1b_joint_power_repair_20260817/REPORT.md>)<br>P1b 本机证据包保存 33×35 top-right body incumbent、exact power 分析、266→6 最小核、56 平移结构 checker、九窗口受限修复收据与 typed 终局。payload 可在轻量 checkout 缺失；其存在不授予 claim、cut、certified、下界或… | `reasoning-system`, `witness-lower-bound`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P1-WITNESS-CONSTRUCTION-20260817-D06675346E` | `2026-08-17` | [P1 受限 witness 构造本地证据包（2026-08-17）](<../.artifacts/p1_witness_construction_20260817/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `witness-lower-bound`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P1-RESTRICTED-WITNESS-CONSTRUCTION-20260817-39AB02A7C6` | `2026-08-17` | [P1 受限 witness 构造与供电死因谱（2026-08-17）](<research/p1_restricted_witness_construction_20260817/README.md>)<br>Active research dossier opened through docctl; semantic outcome is pending closure review. | `reasoning-system`, `witness-lower-bound`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P0-FRONTIER-PROJECTION-20260817-1B1E6F4CB4` | `2026-08-17` | [P0：current claim 账本到 production 矩形前沿的保守投影](<../.artifacts/p0_frontier_projection_20260817/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：MANIFEST_SEALED_NO_TOP_LEVEL_STATUS。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-W0-UNARY-CANARY-20260816-40F7F16A22` | `2026-08-16` | W0 一元 lowering 金丝雀共享本机证据根（GPT-5.6 Pro lineage，2026-08-16）<br><code>.artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816</code><br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-REVIEWS-20260815-D26B592E99` | `2026-08-15` | [推理外环三轮外部评审归档（2026-08-15）](<research/solver_reasoning_outer_loop_reviews_20260815/README.md>)<br>三份外部评审正文逐字归档；同一 active dossier 继续承载 Phase -1 观测、W0 离线短证书、一元 lowering 金丝雀及 2026-08-16 席位算术／固定矩形终局排除实验。所有实验均保持 research-only／non-authorizing：定理与候选排除不自动构成立项、produ… | `reasoning-system`, `solver-architecture`, `solver-rethink` | `active` | `historical` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-20260815-7FA2A0E225` | `2026-08-15` | [推理外环 Phase -1 本机运行证据包（2026-08-15）](<../.artifacts/solver_reasoning_outer_loop_phase_minus1_20260815/phase-minus1-r1-20260815/BATCH_SUMMARY.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-V2-20260815-96E16B17C8` | `2026-08-15` | 推理外环 Phase -1 v2 高预算本机运行证据包（2026-08-15）<br><code>.artifacts/solver_reasoning_outer_loop_phase_minus1_v2_20260815</code><br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-SOLVER-RETHINK-20260808-47BE0A3C3A` | `2026-08-08` | [推理外环 solver-rethink 设计与对抗收敛包](<../.artifacts/solver_rethink_20260808/DESIGN_DOC_v2.md>)<br>本机可选的推理外环、CP-SAT 内层、完备性口径、能力缺口与对抗收敛设计包；未立线、未获 production authority。 | `reasoning-system`, `solver-architecture`, `solver-rethink` | `historical` | `historical` |
| `DOSSIER-RULE-SYSTEM-REDESIGN-20260807-9B23FA19D2` | `2026-08-07` | [规则形态与推理流程重设计](<research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md>)<br>低余量发现法、条件塌点、pairwise closure 反例、双向保真与 derived-rule 工作流的现行研究文书。 | `reasoning-system`, `rules-semantics`, `separation-method` | `active` | `current_evidence` |
| `DOSSIER-P2-0-SPECIALIZED-20260807-C40266E222` | `2026-08-07` | [P2.0 特化推理与反例重判](<research/p2_0_specialized_20260807/README.md>)<br>台间占空自由度、作物必分支、steel_block 反例和阶梯见证的主 dossier。 | `p2-throughput` | `active` | `current_evidence` |
| `DOSSIER-P2-0-AREA-BOUND-20260806-6016501B5F` | `2026-08-06` | [P2.0 面积上界账本](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)<br>P2.0 吞吐语义下 A≤1167、条件界 A≤1015、共享前件与 min_side 次坐标开放义务的定理、复核和收据索引。 | `p2-throughput` | `active` | `current_evidence` |
| `DOSSIER-GHOST-STRICT-FIX-20260805-0FBA53DB19` | `2026-08-05` | [strict ghost 修复与复审收据](<../.artifacts/ghost_strict_fix_20260805/mutation_manifests_20260806/SUMMARY.md>)<br>2026-08-05 至 08-06 strict-semantics 修复、外审与 seal batch 的本机可选证据。 | `p1_2-proof-chain` | `historical` | `current_evidence` |
| `DOSSIER-P2-0-REFRESH-20260805-627C980F03` | `2026-08-05` | [P2.0 refresh 本地收据](<../.artifacts/p2_0_refresh_20260805/AREA_BOUND_UPGRADE_PLAN.md>)<br>P2.0 面积界与复核脚本的本机可选收据根。 | `p2-throughput` | `historical` | `current_evidence` |
| `DOSSIER-BAND22-STRICT-HOLE-PROBE-20260805-B4EF0C65D3` | `2026-08-05` | [band22 严格空地结构探针](<../.artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md>)<br>本机可选的 52=52 槽账、边界禁轨和孔位容量探针。 | `upper-bound` | `historical` | `current_evidence` |
| `DOSSIER-AB16-ARMS-20260802-DC229C4539` | `2026-08-02` | [AB16 十六臂正式实验收据](<../.artifacts/ab16_arms_20260802/EVAL.md>)<br>本机可选的 16-arm frozen-run EVAL；16/16 budget-censored，generated/compiled/applied 均为 0/0/0。 | `cut-framework`, `separation-telemetry`, `solver-experiment` | `historical` | `current_evidence` |
| `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-20260727-EA260C6D6B` | `2026-07-27` | [SMM4 fresh-authority 上界闭包](<research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md>)<br>把 SMM-209 与旧 band authority 合并为 U=(1188,18) 的 tracked authority 文书。 | `upper-bound` | `active` | `current_evidence` |
| `DOSSIER-TRACK-B-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-2026-2C7C3FCD74` | `2026-07-27` | SMM4 fresh-authority local artifact root<br><code>.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727</code><br>External authorization root named by the tracked authority report; intentionally optional and absent from some checkouts. | `formal-verification`, `upper-bound` | `historical` | `current_evidence` |
| `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-STRICT-20260724-F275CFCFE2` | `2026-07-24` | [SMM-209 严格膜不等式](<research/b1_sidewise_marked_membrane_strict_20260724/README.md>)<br>22×54 / 54×22 排除的纸面证明、翻译检查与对抗判读。 | `upper-bound` | `active` | `current_evidence` |
| `DOSSIER-NONCERT-CUTS-AB16-20260724-826CF39625` | `2026-07-24` | [AB16 非认证 cut 实验线](<research/noncert_cuts_ab16_20260724/README.md>)<br>cut 激活暴露、固定运行与 B6 promotion 证据边界。 | `cut-framework` | `historical` | `current_evidence` |
| `DOSSIER-B1-R4-1188-22-PB-20260723-FE5DFB853D` | `2026-07-23` | [Track B/B1：R4 (1188,22) 候选的 proof-bearing 回归](<research/b1_r4_1188_22_pb_20260723/README.md>)<br>给定 A004 几何引理后，2084 个 lex-better orientations 的 OPB、RoundingSat proof、VeriPB 验证与 detached upper-update receipt。 | `upper-bound`, `formal-verification` | `historical` | `historical` |
| `DOSSIER-R4-RESPONSE-REVIEW-20260723-D8EBC0DB9D` | `2026-07-23` | [R4 external-response review](<research/r4_response_review_20260723/README.md>)<br>R4 response 的 110-mark census、S+12 marked membrane、t+m≤4、23+23 full-span 排除与完整尺寸必要式。 | `upper-bound` | `historical` | `historical` |
| `DOSSIER-B1-CONDITIONAL-HALO-20260722-0D968A299D` | `2026-07-22` | [Track B/B1 round 2: conditional halo](<research/b1_conditional_halo_20260722/README.md>)<br>All-selected-poles conditional-halo 必要式、actual-P ceiling 账与 512 对 control/treatment 零增量剪枝边界。 | `upper-bound`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-B1-Q-MEMBRANE-HALO-20260722-D054906F9B` | `2026-07-22` | [Track B/B1 round 1: Q/membrane/halo](<research/b1_q_membrane_halo_20260722/README.md>)<br>Boundary Q 交叠、ordinary membrane 与 tangential endpoint 修正形成的 B1-QMH 必要不等式及其双计数边界。 | `upper-bound` | `historical` | `historical` |
| `DOSSIER-R3-UPPER-BOUND-PB-20260722-60ED8947CD` | `2026-07-22` | [Track B/B0：R3 (1190,34) 算术层的 PB/VeriPB 链](<research/r3_upper_bound_pb_20260722/README.md>)<br>R3 shared body/access、ordinary membrane 与 power 前件，以及给定几何引理后的 2074-orientation PB/VeriPB 算术闭包。 | `upper-bound`, `formal-verification` | `historical` | `historical` |
| `DOSSIER-RULES-AUDIT-20260718-A447D60E10` | `2026-07-18` | [规则语义审计与 owner 裁决](<research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md>)<br>当前 strict empty-rectangle 语义与相关游戏规则裁决的 tracked 证据包。 | `rules-semantics` | `active` | `current_evidence` |
| `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-2B25E2B21B` | `2026-07-18` | [front offset 本地复验收据](<../.artifacts/front_offset_incident_20260718/history.json>)<br>事故修复批的本机可选日志与结构化收据。 | `rules-semantics` | `historical` | `historical` |
| `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-7F16095D41` | `2026-07-18` | [front offset 事故与历史重判](<research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md>)<br>旧 front 坐标重复偏移的根因、修复与历史结论有效性边界。 | `rules-semantics` | `historical` | `current_evidence` |
| `DOSSIER-WITNESS-CONSTRUCTOR-20260717-5F04E123B3` | `2026-07-17` | [whole-layout witness constructor 线](<research/witness_constructor_20260717/07_routing_aware/README.md>)<br>当前 tracked witness 构造与 routing-aware 尝试入口；没有登记成功 lower witness。 | `witness-lower-bound` | `active` | `current_evidence` |
| `DOSSIER-RAB-SEP-PROMOTION-20260716-CF6D536C85` | `2026-07-16` | [01 — ①′ 第一段：front-free 必要性 soundness 审查（v2 修订版，2026-07-16，对抗验证完成）](<research/rab_sep_promotion_20260716/01_front_free_necessity_soundness_review.md>)<br>RAB/front-clear separator 的 soundness、telemetry、promotion 与后续失效历史；batch3 只提炼 raw-event 评价原则。 | `cut-framework`, `separation-telemetry` | `historical` | `historical` |
| `DOSSIER-BATCH-CE-ATTACH-HOST-20260712-D4A08ECB0B` | `2026-07-12` | [Batch C/E attach-host evidence line](<research/batch_ce_attach_host_20260712/01_batch_c_execution_plan_draft.md>)<br>Cut attach-host、prod-form mirror 和 fail-closed 修复证据；证明 consumer 接线边界，不授权 autonomous separation 或 production attach。 | `cut-framework`, `solver-experiment` | `historical` | `current_evidence` |
| `DOSSIER-P1-3A-ATTACH-POWER-ON-SPIKE-20260710-25E1F679CB` | `2026-07-10` | [P1.3A attach 通电 spike 规格书（主会话亲写定稿，2026-07-10 夜）](<research/p1_3a_attach_power_on_spike_20260710/02_spike_evidence.md>)<br>约 10K synthetic redundant F5 的真实 step-8 通电与 overhead 证据；只覆盖工程接线，不覆盖 cut 科学效力。 | `cut-framework`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-HISTORY-TOOLCHAIN-ORIGIN-20260709-411160EC29` | `2026-07-09` | [工具链起源考古：「自建 cut framework」决策的调研与最初设计（2026-07-09）](<research/history_toolchain_origin_20260709/README.md>)<br>cut-language thesis、专用 cut/proof 工具链、oracle/validator 分工与早期 lifecycle 的 tracked 起源考古。 | `cut-framework`, `documentation-governance`, `solver-architecture` | `historical` | `historical` |
| `DOSSIER-P1-3A-ATTACH-SIZING-SPIKE-20260708-02F3C50E2F` | `2026-07-08` | [P1.3A attach sizing spike — verdict（2026-07-08）](<research/p1_3a_attach_sizing_spike_20260708/verdict.md>)<br>增量 attach 形态与容量 sizing 的工程 GO；明确不证明收敛、P1.3 完成或 production promotion。 | `cut-framework`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-P1-2-V99-CLOSE-KERNEL-SEALING-207F650E44` | `未标日期` | [P1.2 V99 close-kernel sealing](<research/p1_2_v99_close_kernel_sealing.md>)<br>P1.2 proof-bearing sink 与 close-kernel 的 tracked review anchor。 | `p1_2-proof-chain` | `active` | `current_evidence` |

## tracked research dossier 全表

| Dossier ID | 日期 | 标题 / 入口 | topics | lifecycle | relevance |
|---|---|---|---|---|---|
| `DOSSIER-P5-HORIZONTAL-LOWERING-CANARY-20260817-3DBC7800A0` | `2026-08-17` | [P5 水平边界供电封锁 lowering 金丝雀（2026-08-17）](<research/p5_horizontal_lowering_canary_20260817/README.md>)<br>P5 已执行 HORIZONTAL-BOUNDARY-MIDDLE-TARGET-SHELL-V1 的 research-only pose-bool lowering canary：六个 group-pose 事件被精确编译为一条 sum<=5 约束，producer 外重建与 proto replay 逐字节通过… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P4-BLOCKADE-FAMILY-ABSTRACTION-20260817-284FD8D3B0` | `2026-08-17` | [P4 区域供电封锁 family 抽象与定理化（2026-08-17）](<research/p4_blockade_family_abstraction_20260817/README.md>)<br>P4 将 P1b/P3 的局部供电封锁机制拆为水平边界中间 target、双边界角 target 与 5×5/6×4/4×6 混合矩形三类 group-pose family。水平类通过 1,728 个正例与 6,708 个系统反例并具备 2 个自然 occurrence，技术义务已闭合到只剩 owner lower… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P3-POWER-BLOCKADE-VALIDATION-20260817-3DC75D9C7A` | `2026-08-17` | [P3 区域供电封锁 family 验证（2026-08-17）](<research/p3_power_blockade_validation_20260817/README.md>)<br>P3 对 P1b 底边六块供电封锁候选做小样本 incidence、37 个近失配、1098 个纵向／target 换位、双 master 只读 literal 审计与 5×5/6×4/4×6 混合模板探针。候选被收窄为网格边界壳机制并获得扩展正样本，但仍未晋升为 claim、cut、certified 或 prod… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P1B-JOINT-POWER-REPAIR-20260817-C459AE609C` | `2026-08-17` | [P1b 九窗口联合修复与区域供电封锁候选（2026-08-17）](<research/p1b_joint_power_repair_20260817/README.md>)<br>P1b 在未取得完整 witness、完整 verifier 未到达且 canonical L 保持 absent 的边界下，将 P1 family A 的 266 实例供电 nogood 收缩为 6 姿态全局最小局部核，并提出经 56 个水平平移独立复算的底边 5×5 六块 Hall 型封锁候选。该对象仅为 P3/… | `reasoning-system`, `witness-lower-bound`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P1-RESTRICTED-WITNESS-CONSTRUCTION-20260817-39AB02A7C6` | `2026-08-17` | [P1 受限 witness 构造与供电死因谱（2026-08-17）](<research/p1_restricted_witness_construction_20260817/README.md>)<br>Active research dossier opened through docctl; semantic outcome is pending closure review. | `reasoning-system`, `witness-lower-bound`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-TRI-PLANE-MODEL-V2-20260816-71A3625ABB` | `2026-08-16` | [三面防污染模型 v2 dossier](<research/tri_plane_model_v2_20260816/README.md>)<br>v1 三面模型解决了一个根病：同一个“收紧”动作在数学面与发布面上符号相反，语言混面会把发布侧“保守安全”的直觉错误搬进求解证明面。研究侧开始产出机器验证 theorem 并准备 lowering 后，污染风险从节点措辞扩展到消费链：一条正确 theorem 仍可能被错误 consumer、错误 runtime li… | `other` | `active` | `historical` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-REVIEWS-20260815-D26B592E99` | `2026-08-15` | [推理外环三轮外部评审归档（2026-08-15）](<research/solver_reasoning_outer_loop_reviews_20260815/README.md>)<br>三份外部评审正文逐字归档；同一 active dossier 继续承载 Phase -1 观测、W0 离线短证书、一元 lowering 金丝雀及 2026-08-16 席位算术／固定矩形终局排除实验。所有实验均保持 research-only／non-authorizing：定理与候选排除不自动构成立项、produ… | `reasoning-system`, `solver-architecture`, `solver-rethink` | `active` | `historical` |
| `DOSSIER-METHODOLOGY-COMPILATION-20260814-BF49D11CCD` | `2026-08-14` | [附录 E · 管线与归属方法论（项目既有方法论权威）](<research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md>)<br>本附录是本项目科学面的方法论权威：一套关于「一条知识该住在计算管线的哪一层、管线本身该怎么切、 一个结构性预设该押在哪」的判据体系。 | `other` | `historical` | `historical` |
| `DOSSIER-PLANE-MIXING-AUDIT-20260813-176281B3F4` | `2026-08-13` | [三面防污染架构审计——发现与挂账登记（2026-08-13）](<research/plane_mixing_audit_20260813/FINDINGS.md>) | `other` | `historical` | `historical` |
| `DOSSIER-CANONICAL-BATCH-20260808-B2462129DF` | `2026-08-08` | [BLOCKERS / 待定点（canonical 08-08 改稿草案 · v3）](<research/canonical_batch_20260808/BLOCKERS.md>)<br>--- | `rules-semantics` | `historical` | `historical` |
| `DOSSIER-RULE-SYSTEM-REDESIGN-20260807-9B23FA19D2` | `2026-08-07` | [规则形态与推理流程重设计](<research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md>)<br>低余量发现法、条件塌点、pairwise closure 反例、双向保真与 derived-rule 工作流的现行研究文书。 | `reasoning-system`, `rules-semantics`, `separation-method` | `active` | `current_evidence` |
| `DOSSIER-P2-0-SPECIALIZED-20260807-C40266E222` | `2026-08-07` | [P2.0 特化推理与反例重判](<research/p2_0_specialized_20260807/README.md>)<br>台间占空自由度、作物必分支、steel_block 反例和阶梯见证的主 dossier。 | `p2-throughput` | `active` | `current_evidence` |
| `DOSSIER-CANONICAL-BATCH-20260807-B460BA9381` | `2026-08-07` | [canonical 公理 kernel + 四件套修正批（2026-08-07）](<research/canonical_batch_20260807/README.md>)<br>owner 2026-08-07 晨拍板：公理 kernel 提案与在案四件套（W-PENDING-01）合并、一次 freeze-ritual 走完。本目录 = 该批的定谳存档 + reseal 台账 + 验证记录。 | `rules-semantics` | `historical` | `historical` |
| `DOSSIER-P2-0-AREA-BOUND-20260806-6016501B5F` | `2026-08-06` | [P2.0 面积上界账本](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)<br>P2.0 吞吐语义下 A≤1167、条件界 A≤1015、共享前件与 min_side 次坐标开放义务的定理、复核和收据索引。 | `p2-throughput` | `active` | `current_evidence` |
| `DOSSIER-BAND22-SIM-EXPORT-20260805-9A43971884` | `2026-08-05` | [band22 见证布局 → IndustrialPlanner 蓝图导出](<research/band22_sim_export_20260805/README.md>)<br>状态：已完成（2026-08-05）。产物为 research-only 导出件，不是认证材料，不参与任何 release 边界判定。 | `upper-bound`, `industrial-delivery` | `historical` | `historical` |
| `DOSSIER-BAND22-REGISTRATION-20260805-C053405AC5` | `2026-08-05` | [band22 v2 witness → official binding/routing gates](<research/band22_registration_20260805/README.md>)<br>Status: CURRENT research-only adapter contract | `upper-bound`, `witness-lower-bound` | `historical` | `historical` |
| `DOSSIER-W0-FRONT-AWARE-20260803-425794297E` | `2026-08-03` | [G1 两个 master run root 的仓内副本（字节原样）](<research/w0_front_aware_20260803/evidence/README.md>)<br>RESULT.md 的每个数字都来自这两个运行根。它们原本只存在于单机根盘的 .artifacts/（未跟踪、权限 700），所以这里放一份字节原样的副本进 git。 | `witness-lower-bound` | `historical` | `historical` |
| `DOSSIER-W0-POWER-CYCLE-DOMINO-D6-20260728-40A9A51629` | `2026-07-28` | [W0 power-cycle domino：D6 局部联合 completion gate](<research/w0_power_cycle_domino_d6_20260728/README.md>)<br>状态： RESEARCHONLY / LOCALD6ONLY / TWOV2NEGATIVEROOTSACCEPTED / SWAPV3REPLAYACCEPTEDINFEASIBLE | `witness-lower-bound` | `historical` | `historical` |
| `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-20260727-EA260C6D6B` | `2026-07-27` | [SMM4 fresh-authority 上界闭包](<research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md>)<br>把 SMM-209 与旧 band authority 合并为 U=(1188,18) 的 tracked authority 文书。 | `upper-bound` | `active` | `current_evidence` |
| `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-20260724-684AF89404` | `2026-07-24` | [Track B/B1：22×54 分边 marked-membrane 最小证明轮](<research/b1_sidewise_marked_membrane_20260724/README.md>)<br>本目录是 cuts Gate 1 支线终止后返回 Track B 的下一项最小工作。研究目标是 核心计划候选 3 的 ceiling 特化：对四条边容量 22,22,54,54 分开记账，并把 ordinary terminals、marked terminals、端点 partial contact 与 proto… | `upper-bound` | `historical` | `historical` |
| `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-AUTHORITY-RECOVERY-20260724-9E688ADD0E` | `2026-07-24` | [SMM3 authority recovery 终态](<research/b1_sidewise_marked_membrane_authority_recovery_20260724/README.md>)<br>SMM3 已完成 privileged manager attestation、两阶段 synthetic 生命周期验证与 formal admission，但唯一 formal a002 在 payload 的 selection replay 处 失败关闭。该 attempt 已消费，不得重跑或补写。没有 Rou… | `upper-bound` | `historical` | `historical` |
| `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-STRICT-20260724-F275CFCFE2` | `2026-07-24` | [SMM-209 严格膜不等式](<research/b1_sidewise_marked_membrane_strict_20260724/README.md>)<br>22×54 / 54×22 排除的纸面证明、翻译检查与对抗判读。 | `upper-bound` | `active` | `current_evidence` |
| `DOSSIER-NONCERT-CUTS-AB-TRUST-GATE1-V4-20260724-CBD18919D9` | `2026-07-24` | [Non-certified cuts Gate 1 v4 authority completion](<research/noncert_cuts_ab_trust_gate1_v4_20260724/README.md>)<br>Document kind: research authority terminal summary Evidence cutoff date: 2026-07-24 (Asia/Tokyo) Status: CUTSGATE1V4AUTHORITYCOMPLETIONPASS / MECHANISMCREDIBLE… | `cut-framework` | `historical` | `historical` |
| `DOSSIER-NONCERT-CUTS-AB16-20260724-826CF39625` | `2026-07-24` | [AB16 非认证 cut 实验线](<research/noncert_cuts_ab16_20260724/README.md>)<br>cut 激活暴露、固定运行与 B6 promotion 证据边界。 | `cut-framework` | `historical` | `current_evidence` |
| `DOSSIER-B1-R4-1188-22-PB-20260723-FE5DFB853D` | `2026-07-23` | [Track B/B1：R4 (1188,22) 候选的 proof-bearing 回归](<research/b1_r4_1188_22_pb_20260723/README.md>)<br>给定 A004 几何引理后，2084 个 lex-better orientations 的 OPB、RoundingSat proof、VeriPB 验证与 detached upper-update receipt。 | `upper-bound`, `formal-verification` | `historical` | `historical` |
| `DOSSIER-R4-RESPONSE-REVIEW-20260723-D8EBC0DB9D` | `2026-07-23` | [R4 external-response review](<research/r4_response_review_20260723/README.md>)<br>R4 response 的 110-mark census、S+12 marked membrane、t+m≤4、23+23 full-span 排除与完整尺寸必要式。 | `upper-bound` | `historical` | `historical` |
| `DOSSIER-NONCERT-CUTS-AB-TRUST-20260723-92D0F8BDCA` | `2026-07-23` | [Non-certified cuts A/B credibility experiment](<research/noncert_cuts_ab_trust_20260723/README.md>)<br>Document kind: research terminal-status summary\ Cutoff date: 2026-07-23\ Status: CREDIBILITYINCOMPLETE — Gate 1 admits neither a positive nor a negative cuts… | `cut-framework` | `historical` | `historical` |
| `DOSSIER-NONCERT-CUTS-AB-TRUST-GATE1-V3-20260723-A086F47E85` | `2026-07-23` | [Gate 1 v3 authority closeout](<research/noncert_cuts_ab_trust_gate1_v3_20260723/README.md>)<br>Document kind: research authority-hardening terminal summary Evidence cutoff date (UTC): 2026-07-23 Status: HARDENINGINCOMPLETE / LEGACYA002CREDIBILITYINCOMPLE… | `cut-framework` | `historical` | `historical` |
| `DOSSIER-B1-CONDITIONAL-HALO-20260722-0D968A299D` | `2026-07-22` | [Track B/B1 round 2: conditional halo](<research/b1_conditional_halo_20260722/README.md>)<br>All-selected-poles conditional-halo 必要式、actual-P ceiling 账与 512 对 control/treatment 零增量剪枝边界。 | `upper-bound`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-B1-Q-MEMBRANE-HALO-20260722-D054906F9B` | `2026-07-22` | [Track B/B1 round 1: Q/membrane/halo](<research/b1_q_membrane_halo_20260722/README.md>)<br>Boundary Q 交叠、ordinary membrane 与 tangential endpoint 修正形成的 B1-QMH 必要不等式及其双计数边界。 | `upper-bound` | `historical` | `historical` |
| `DOSSIER-R3-UPPER-BOUND-PB-20260722-60ED8947CD` | `2026-07-22` | [Track B/B0：R3 (1190,34) 算术层的 PB/VeriPB 链](<research/r3_upper_bound_pb_20260722/README.md>)<br>R3 shared body/access、ordinary membrane 与 power 前件，以及给定几何引理后的 2074-orientation PB/VeriPB 算术闭包。 | `upper-bound`, `formal-verification` | `historical` | `historical` |
| `DOSSIER-R4-EXTERNAL-BRAIN-HANDOFF-20260722-4A5CA75F11` | `2026-07-22` | [R4 external-brain handoff package](<research/r4_external_brain_handoff_20260722/README.md>)<br>This directory prepares the local R4 handoff defined by Part 6 of /home/zhuran24/zmd-pj-codex/核心计划书.md. It does not submit anything to an external service. The… | `upper-bound` | `historical` | `historical` |
| `DOSSIER-RULES-AUDIT-20260718-A447D60E10` | `2026-07-18` | [规则语义审计与 owner 裁决](<research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md>)<br>当前 strict empty-rectangle 语义与相关游戏规则裁决的 tracked 证据包。 | `rules-semantics` | `active` | `current_evidence` |
| `DOSSIER-PROOF-LOGGING-SCOUT-20260718-2B4BF502F3` | `2026-07-18` | [牌 D 侦察日志：证明日志求解器工具链（2026-07-18）](<research/proof_logging_scout_20260718/01_scout_log_20260718.md>)<br>d4edbf7908a9，2026-03-03，源码编译 -Dsoplex=OFF）直接吃 OPB → --proof-log= 输出 PBP → VeriPB 3.0.2（cargo 安装，Rust 版）校验。 不经过 CNF 翻译——少一层编码信任缺口。 | `formal-verification` | `historical` | `historical` |
| `DOSSIER-CLEANROOM-REDERIVATION-20260718-41375BBFE3` | `2026-07-18` | [R- 价签精算交付包](<research/cleanroom_rederivation_20260718/25_rstar_pricetag_delivery_20260804/README.md>)<br>本交付包按 00ASK.md 完成九条充分限制的价签、前提集、撤退线和判定实验设计；authority=false，不登记任何界，账本不变。【已证明】 | `rules-semantics` | `historical` | `historical` |
| `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-7F16095D41` | `2026-07-18` | [front offset 事故与历史重判](<research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md>)<br>旧 front 坐标重复偏移的根因、修复与历史结论有效性边界。 | `rules-semantics` | `historical` | `current_evidence` |
| `DOSSIER-WITNESS-CONSTRUCTOR-20260717-5F04E123B3` | `2026-07-17` | [whole-layout witness constructor 线](<research/witness_constructor_20260717/07_routing_aware/README.md>)<br>当前 tracked witness 构造与 routing-aware 尝试入口；没有登记成功 lower witness。 | `witness-lower-bound` | `active` | `current_evidence` |
| `DOSSIER-RAB-SEP-PROMOTION-20260716-CF6D536C85` | `2026-07-16` | [01 — ①′ 第一段：front-free 必要性 soundness 审查（v2 修订版，2026-07-16，对抗验证完成）](<research/rab_sep_promotion_20260716/01_front_free_necessity_soundness_review.md>)<br>RAB/front-clear separator 的 soundness、telemetry、promotion 与后续失效历史；batch3 只提炼 raw-event 评价原则。 | `cut-framework`, `separation-telemetry` | `historical` | `historical` |
| `DOSSIER-BATCH-CE-ATTACH-HOST-20260712-D4A08ECB0B` | `2026-07-12` | [Batch C/E attach-host evidence line](<research/batch_ce_attach_host_20260712/01_batch_c_execution_plan_draft.md>)<br>Cut attach-host、prod-form mirror 和 fail-closed 修复证据；证明 consumer 接线边界，不授权 autonomous separation 或 production attach。 | `cut-framework`, `solver-experiment` | `historical` | `current_evidence` |
| `DOSSIER-FORMAL-VERIFICATION-LANGUAGES-ASSESSMENT-20260711-CCCFF888D8` | `2026-07-11` | [ATS / F\ 形式化验证语言对本项目的适用性评估](<research/formal_verification_languages_assessment_20260711/01_ats_fstar_assessment.md>)<br>这类语言的看家本领是把「程序本身正确」变成机器可查的定理——典型用法不是验证求解器,而是验证检查器(De Bruijn 准则:求解器大而不可信,检查器小而可信)。 | `formal-verification` | `historical` | `historical` |
| `DOSSIER-CUT-FRAMEWORK-REVIEW-GPT56PRO-20260710-C6C896B93B` | `2026-07-10` | [补丁顺序](<research/cut_framework_review_gpt56pro_20260710/patches/README.md>)<br>基线：项目包 committed tree。 | `cut-framework` | `historical` | `historical` |
| `DOSSIER-P1-3A-ATTACH-POWER-ON-SPIKE-20260710-25E1F679CB` | `2026-07-10` | [P1.3A attach 通电 spike 规格书（主会话亲写定稿，2026-07-10 夜）](<research/p1_3a_attach_power_on_spike_20260710/02_spike_evidence.md>)<br>约 10K synthetic redundant F5 的真实 step-8 通电与 overhead 证据；只覆盖工程接线，不覆盖 cut 科学效力。 | `cut-framework`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-P1-3-BATCH1-DESIGN-20260710-57F92742D0` | `2026-07-10` | [P1.3 批 1 C1 certified 化任务书草案（2026-07-10）](<research/p1_3_batch1_design_20260710/00_batch1_workplan.md>)<br>范围：只把批 0 已实测获胜的 C1 供电编码升格为 src/models/exactcoordinatemaster.py 的 certified 默认编码，并补齐解级 dominance 剪杆与 reseal 材料。本文件是主会话对抗复核前的任务书草案，不是实现提交。 | `other` | `historical` | `historical` |
| `DOSSIER-P1-3-M6-DIAGNOSIS-20260709-7C9DEFFA5D` | `2026-07-09` | [诊断侦察·ablationmap（Fable，2026-07-09）](<research/p1_3_m6_diagnosis_20260709/01_ablation_map.md>)<br>6×6 coordinate master 的约束族已全量盘点：真正的模型只有 8 族（slot 几何/签名桶/对称链/核心 nooverlap2d/ghost 族/供电 witness/供电容量族/全局有效不等式），其中「供电三层」和「ghost 4225-anchor 多重性」是仅有的两大可疑墙，且每族都找到了… | `other` | `historical` | `historical` |
| `DOSSIER-HISTORY-TOOLCHAIN-ORIGIN-20260709-411160EC29` | `2026-07-09` | [工具链起源考古：「自建 cut framework」决策的调研与最初设计（2026-07-09）](<research/history_toolchain_origin_20260709/README.md>)<br>cut-language thesis、专用 cut/proof 工具链、oracle/validator 分工与早期 lifecycle 的 tracked 起源考古。 | `cut-framework`, `documentation-governance`, `solver-architecture` | `historical` | `historical` |
| `DOSSIER-P1-3-A-BATCH0-20260709-25C725D5B0` | `2026-07-09` | [A 批 0：C6/C1 供电编码原型头对头（2026-07-09）](<research/p1_3_a_batch0_20260709/README.md>)<br>b04r（C1 v1 自由搜索 w6 1800s）：OPTIMAL @541.3s（495 万分支 / 1077 冲突）。 266 mandatory + storage box + 26 杆 + 6×6 ghost（anchor (55,50)）完整布局， 独立覆盖复验（G0.4 门，照终端验证器语义、不 impo… | `other` | `historical` | `historical` |
| `DOSSIER-P1-3A-ATTACH-SIZING-SPIKE-20260708-02F3C50E2F` | `2026-07-08` | [P1.3A attach sizing spike — verdict（2026-07-08）](<research/p1_3a_attach_sizing_spike_20260708/verdict.md>)<br>增量 attach 形态与容量 sizing 的工程 GO；明确不证明收敛、P1.3 完成或 production promotion。 | `cut-framework`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-P1-3-M4-RECON-20260708-3819BDF48B` | `2026-07-08` | [P1.3 M4 开工侦察材料（2026-07-08）](<research/p1_3_m4_recon_20260708/README.md>)<br>M4（F2-F7+F9 逐族阶梯 + 两横切件）开工前的九路侦察报告存档。七路 Fable + 一路 codex（f9，配额耗尽前完成）+ 一路 D2 追加侦察。全部带真实签名 + 行号级硬事实（行号以当日 HEAD 为准，后续 M4 各批 reseal 后会漂移——结论仍有效，行号仅当叙事线索）。 | `other` | `historical` | `historical` |
| `DOSSIER-P1-3-M5-CONVERGENCE-20260708-A96D060024` | `2026-07-08` | [M5 A/B 首战:产品默认 solve 参数病态的单变量归因(2026-07-11 凌晨)](<research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md>)<br>M5 归因判决(m5c1memoryattribution20260710.md)与 attach spike E1 系列(../p13aattachpoweronspike20260710/01spikespec.md)两次把「产品默认 solve 参数(FIXEDSEARCH+probing3+symmetry3… | `other` | `historical` | `historical` |
| `DOSSIER-P3-0C-SIDECAR-REVIEWS-20260705-728E34B496` | `2026-07-05` | [P3.0c binding PB sidecar 设计稿 v1 外审归档（2026-07-05）](<research/p3_0c_sidecar_reviews_20260705/README.md>)<br>轴 B 证书侧 Phase 0+1 设计稿 v1 的双会话独立对抗审原件。两份均判 REJECT （方向保留：PB/OPB 独立重建 + RoundingSat + VeriPB sidecar 路线双方都攻击失败； 但 v1 的 scope gate、输入契约、语义完整性、验收强度不能作实现基线）。 | `other` | `historical` | `historical` |
| `DOSSIER-P3-0B-FORMAL-REVIEWS-ROUND2-20260705-23A40FE2C2` | `2026-07-05` | [P3.0b 第二轮独立审查归档（2026-07-05）](<research/p3_0b_formal_reviews_round2_20260705/README.md>)<br>对象一：formal/ZmdFormal/CutFamilies.lean（17 条）+ FrameworkLemmas.lean （9 条）的陈述保真。三路：对抗审 CutFamilies（双会话）、对抗审 FrameworkLemmas（双会话）、盲形式化对拼（26 条独立陈述）。 对象二（后续回传）：Q1 不可… | `formal-verification` | `historical` | `historical` |
| `DOSSIER-P3-0B-FAMILY-FORMALIZABILITY-SURVEY-20260705-37E896037C` | `2026-07-05` | [F1-F9 与完备性的形式化可开工地图（2026-07-05 调查）](<research/p3_0b_family_formalizability_survey_20260705/README.md>)<br>性质：HISTORICALORPLAN。10 路并行只读调查（每 family 一读者：spec + validator 源码 + oracle/helper，全部断言带 file:line；另一读者查完备性 Q1 现状），为 「P3.0 形式化线下一步先啃哪块」提供事实底料与排序。原始逐 family 报告在本目录… | `formal-verification` | `historical` | `historical` |
| `DOSSIER-P3-0-FORMAL-REVIEWS-20260705-D6CB85EB2A` | `2026-07-05` | [2026-07-05 P3.0 形式化头启动首轮独立审查归档（三会话）](<research/p3_0_formal_reviews_20260705/README.md>)<br>性质：HISTORICALORPLAN 审计档案，formal/ 首批定理与 P3.0 设计稿 v1 的 三路独立审查产物，v2 修订的输入证据。补丁未盲 apply（lean 补丁经本地重编译 + 公理审计后采纳；一处 API 修复：Lean core 无 Function.Bijective，双射前提改双侧逆）。 | `formal-verification` | `historical` | `historical` |
| `DOSSIER-P2-DESIGN-EXTERNAL-REVIEWS-20260704-54F28681D7` | `2026-07-04` | [2026-07-04 设计稿预实现外审归档（GPT Pro 五会话）](<research/p2_design_external_reviews_20260704/README.md>)<br>性质：HISTORICALORPLAN 审计档案。这些是对三份「先想后做」设计稿 v1 的外部审查/对照产物， 是 v2 修订的输入证据。不是命令、不是当前状态权威；补丁一律未盲 apply（v2 由本方 triage 后重写）。 | `other` | `historical` | `historical` |
| `DOSSIER-PROJECT-BOTTLENECK-AUDIT-20260702-9E995CC2F0` | `2026-07-02` | [2026-07-02 全项目瓶颈审计归档（多代理工作流，37 agent）](<research/project_bottleneck_audit_20260702/README.md>)<br>性质：HISTORICALORPLAN 审计档案。另一会话于 2026-07-02 深夜运行的全项目「历史 + 最终目标瓶颈」 调查工作流产物：8 个维度 × fable/codex 双模型独立阅读（16 份维度报告，dims.md），继而合成 12 条 瓶颈、逐条由独立核查员回源码验证（bottlenecks.md… | `documentation-governance` | `historical` | `historical` |
| `DOSSIER-DOC-TREE-FULL-AUDIT-20260604-80C4D1938D` | `2026-06-04` | [文档树全量审查 findings (2026-06-04, WF wv9rnpdzd)](<research/doc_tree_full_audit_20260604/FINDINGS.md>)<br>8 单元 fresh-eyes 全审 (R1/R3 口径, 非 R2 查修) + 每条对抗式核验。65 raw → confirmed 60 / refuted 5。severity: high 13 / med 25 / low 22。kind: currency 4 / broken-ref 5 / incons… | `documentation-governance` | `historical` | `historical` |
| `DOSSIER-P1-2-SPIKE-SIZING-GATE-20260601-C56E677966` | `2026-06-01` | [P1.2 spike — 真 cut body sizing cheap gate 结果 (active v6 / v27)](<research/p1_2_spike_sizing_gate_20260601/RESULTS.md>)<br>本文件保留下面 v1-v5 的历史叙述用于审计。gate close / P1.3A cap 设计的当前有效口径是本节， 不是后面较早的 type-pool-only 表。 | `p1_2-proof-chain`, `cut-framework`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-P1-2B-F3-GEMINI-ROUND2-20260526-3304F1F0AA` | `2026-05-26` | [p1 2b f3 gemini round2 20260526](<research/p1_2b_f3_gemini_round2_20260526/gemini_response.md>)<br>OVERALL VERDICT: PASS. The Round 1 warning is fully closed, and the implementation mathematically guarantees deterministic state reconstruction upon failure wi… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F3-GEMINI-ROUND1-20260526-655B7B3DF6` | `2026-05-26` | [p1 2b f3 gemini round1 20260526](<research/p1_2b_f3_gemini_round1_20260526/gemini_response.md>)<br>Overall Verdict: PASS (with completeness warnings). The mathematical soundness strictly holds under the v1.0 spec assumption (all ports active), and the litera… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-PROD-SCALE-SPIKE-DESIGN-20260525-770C030C5E` | `2026-05-25` | [Prod-scale spike design — main merger (N=8 parallel slant)](<research/prod_scale_spike_design_20260525/MERGER.md>)<br>Build target: GPT pro audit Finding 5 close. mini Step 8 spike 50 BoolVar toy + synthetic cuts + INFEASIBLE 早停, 不能当 Phase 1.3A integration close gate. 此 merger… | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-PHASE1-2-GPT-PRO-AUDIT-20260525-84DB22A832` | `2026-05-25` | [Phase 1.2 audit artifact](<research/phase1_2_gpt_pro_audit_20260525/README.md>)<br>Contents: | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND5-20260525-9F2E264F77` | `2026-05-25` | [p1 2b f8 power grid reach gemini round5 20260525](<research/p1_2b_f8_power_grid_reach_gemini_round5_20260525/gemini_response.md>)<br>GO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND4-20260525-99108B2CDC` | `2026-05-25` | [p1 2b f8 power grid reach gemini round4 20260525](<research/p1_2b_f8_power_grid_reach_gemini_round4_20260525/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND3-20260525-975688FCEE` | `2026-05-25` | [p1 2b f8 power grid reach gemini round3 20260525](<research/p1_2b_f8_power_grid_reach_gemini_round3_20260525/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND2-20260525-111B62C30A` | `2026-05-25` | [p1 2b f8 power grid reach gemini round2 20260525](<research/p1_2b_f8_power_grid_reach_gemini_round2_20260525/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND1-20260525-DCCCF931FA` | `2026-05-25` | [p1 2b f8 power grid reach gemini round1 20260525](<research/p1_2b_f8_power_grid_reach_gemini_round1_20260525/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F7-POWER-HITTING-SET-GEMINI-ROUND2-20260525-C4D8B4A483` | `2026-05-25` | [p1 2b f7 power hitting set gemini round2 20260525](<research/p1_2b_f7_power_hitting_set_gemini_round2_20260525/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F7-POWER-HITTING-SET-GEMINI-ROUND1-20260525-DB49AFB525` | `2026-05-25` | [p1 2b f7 power hitting set gemini round1 20260525](<research/p1_2b_f7_power_hitting_set_gemini_round1_20260525/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F6-SHAPE-PACKING-HALL-GEMINI-ROUND3-20260525-7CFD3F9A5E` | `2026-05-25` | [p1 2b f6 shape packing hall gemini round3 20260525](<research/p1_2b_f6_shape_packing_hall_gemini_round3_20260525/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F6-SHAPE-PACKING-HALL-GEMINI-ROUND2-20260525-7550CF55CC` | `2026-05-25` | [p1 2b f6 shape packing hall gemini round2 20260525](<research/p1_2b_f6_shape_packing_hall_gemini_round2_20260525/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F6-SHAPE-PACKING-HALL-GEMINI-ROUND1-20260525-824FA5AE3B` | `2026-05-25` | [p1 2b f6 shape packing hall gemini round1 20260525](<research/p1_2b_f6_shape_packing_hall_gemini_round1_20260525/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-MINI-STEP-8-SPIKE-20260525-5D74B8309D` | `2026-05-25` | [Mini Step 8 Spike — Verdict](<research/p1_2b_mini_step_8_spike_20260525/verdict.md>)<br>Date: 2026-05-25 Scope: Phase 1.2 close gate (per GPT pro P1.2 in-progress review #6) Verdict: GO — all 6 family forms translate cleanly to CP-SAT API, rebuild… | `p1_2-proof-chain`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-P1-2B-F9-DENSITY-ENVELOPE-GEMINI-ROUND3-20260524-2F6134754D` | `2026-05-24` | [p1 2b f9 density envelope gemini round3 20260524](<research/p1_2b_f9_density_envelope_gemini_round3_20260524/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F9-DENSITY-ENVELOPE-GEMINI-ROUND2-20260524-C00FC1FF2B` | `2026-05-24` | [p1 2b f9 density envelope gemini round2 20260524](<research/p1_2b_f9_density_envelope_gemini_round2_20260524/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F9-DENSITY-ENVELOPE-GEMINI-ROUND1-20260524-069C3F5DE0` | `2026-05-24` | [p1 2b f9 density envelope gemini round1 20260524](<research/p1_2b_f9_density_envelope_gemini_round1_20260524/gemini_response.md>)<br>NOTGO | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F2-F4-GEMINI-ROUND3-20260524-A342B2A1F0` | `2026-05-24` | [p1 2b f2 f4 gemini round3 20260524](<research/p1_2b_f2_f4_gemini_round3_20260524/gemini_response.md>)<br>GOWITHMINOR | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F2-F4-GEMINI-ROUND2-20260524-016B519BD5` | `2026-05-24` | [p1 2b f2 f4 gemini round2 20260524](<research/p1_2b_f2_f4_gemini_round2_20260524/gemini_response.md>)<br>GOWITHMINOR | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2B-F2-F4-GEMINI-ROUND1-20260524-948D3BB9A8` | `2026-05-24` | [p1 2b f2 f4 gemini round1 20260524](<research/p1_2b_f2_f4_gemini_round1_20260524/gemini_response.md>)<br>CONCERN (Borderline NOTGO due to a hidden recursion crash in Dinic, but mathematically sound for Phase 1.2 edge-only mode). | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-LITERATURE-REVIEW-PAPERS-20260524-F002A45263` | `2026-05-24` | [Literature Review — 2026-05-24](<research/literature_review_papers_20260524/README.md>)<br>触发: 用户 /deep-research 目前还有哪些论文对我们项目有帮助和参考意义的 | `other` | `historical` | `historical` |
| `DOSSIER-GEMINI-CROSS-CHECK-PHASE1-2-F5-ROUND3-20260524-F197C69BC0` | `2026-05-24` | [gemini cross check phase1 2 f5 round3 20260524](<research/gemini_cross_check_phase1_2_f5_round3_20260524/verdict.md>)<br>GOWITHMINOR (Defer to Phase 1.5+) | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P3-B-DESIGN-REVIEW-V14-20260521-24BD84A607` | `2026-05-21` | [v14 — P3 Design B Architecture Stress Test (2026-05-21)](<research/p3_b_design_review_v14_20260521/README.md>)<br>--- | `other` | `historical` | `historical` |
| `DOSSIER-SMT-MT-OUTER-PRUNING-PHASE1-20260521-DF50598CC0` | `2026-05-21` | [SMT-MT Outer Pruning Phase 1 (2026-05-21)](<research/smt_mt_outer_pruning_phase1_20260521/README.md>)<br>Phase 1 wires the SMT Modulo Monotonic Theories outer pruning engine into src/search/outersearch.py behind EXACTSMTMTOUTERPRUNING=1 env flag. Phase 0 cheap-gat… | `p1_2-proof-chain`, `formal-verification` | `historical` | `historical` |
| `DOSSIER-SMT-MT-OUTER-PRUNING-PHASE0-20260521-042BF3000C` | `2026-05-21` | [SMT-MT Outer Pruning Phase 0 (2026-05-21)](<research/smt_mt_outer_pruning_phase0_20260521/README.md>)<br>Phase 0 cheap-gate probe for SMT Modulo Monotonic Theories (Bayless et al., AAAI 2015) outer-search pruning. Mocks the inner solver with a Dummy threshold/rand… | `formal-verification`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-CAND-C-COLUMN-GENERATION-PHASE2-20260521-9625F52BA3` | `2026-05-21` | [Phase 2 — Column Generation: share cache + Ryan-Foster + 160/266 + routing-aware + boundary equality](<research/cand_c_column_generation_phase2_20260521/README.md>)<br>Date: 2026-05-21 Paradigm: cand C (column generation / branch-and-price) Predecessor: candccolumngenerationphase120260521/ — 4/4 ramp GO (5/20/40/80 inst, m10… | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-CAND-C-COLUMN-GENERATION-PHASE1-20260521-4E809F3AB7` | `2026-05-21` | [Phase 1 — Column Generation + integer reconstruction validator](<research/cand_c_column_generation_phase1_20260521/README.md>)<br>Date: 2026-05-21 Paradigm: cand C (column generation / branch-and-price) Predecessor: candccolumngenerationphase020260521/ (8/8 GO on 20-inst) Status: probe wr… | `p1_2-proof-chain`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-CAND-C-COLUMN-GENERATION-PHASE0-20260521-6F6C808E65` | `2026-05-21` | [Phase 0 cheap gate — Column Generation / Branch-and-Price](<research/cand_c_column_generation_phase0_20260521/README.md>)<br>Date: 2026-05-21 Paradigm: cand C (column generation with intermediate-granularity patterns) Status: probe written, dry-run only — measurement queued. | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-P3-B-DESIGN-V2-20260521-F2C6312F04` | `2026-05-21` | [B core PoC — Day 16c-4 (补做 prep 项 3)](<research/p3_b_design_v2_20260521/poc/README.md>)<br>bcorelifecyclepoc.py 实现 cut object lifecycle 9 步 (per cutlifecyclev2 v3.1 §2) on Family 1 regioncapacity (per cutfamilyspecs/01 v1.1): | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-PARADIGM-SEARCH-REVIEW-V12-WITH-CODE-20260520-FC02CE09A5` | `2026-05-20` | [v12 Paradigm Search Review (with code) — 2026-05-20](<research/paradigm_search_review_v12_with_code_20260520/README.md>)<br>项目在 CP-SAT + LBBD framework 内 24 lever 全 verdict 死之后, 调研了 32 个 paradigm 方向看是否有现成可调用的 algorithm 范式能 break. 4 个候选方向仍 alive, 其余 NO-GO. 包整理这些调研结果 + 24 lever 历史实施 +… | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-BENDERS-SYMMETRY-PHASE0-20260520-D5A77E6403` | `2026-05-20` | [Phase 0 cheap gate — Benders symmetry / cut-orbit lifting](<research/benders_symmetry_phase0_20260520/README.md>)<br>Date: 2026-05-20 Scope: Phase 0 only (cheap gate, no src changes) Verdict so far: TBD (probe written, not yet executed) | `cut-framework`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-LAYOUT-INVARIANT-CERT-PHASE0-20260520-5DA45C1506` | `2026-05-20` | [LIC Phase 0 — Layout-Invariant Cert cheap-gate](<research/layout_invariant_cert_phase0_20260520/README.md>)<br>Date: 2026-05-20 Status: probe written + dry-run pass; measurement run pending Lever: candidate Path 18 (independent brainstorm, not from GPT review) | `witness-lower-bound`, `solver-experiment` | `historical` | `historical` |
| `DOSSIER-LEVER25-IHS-PHASE0-20260520-4194EBD09A` | `2026-05-20` | [Lever 25 IHS (Implicit Hitting Set) — Phase 0 cheap gate](<research/lever25_ihs_phase0_20260520/README.md>)<br>Lever 25 explores the Implicit Hitting Set (IHS) paradigm as an alternative to standard LBBD cut accumulation. Instead of adding each oracle-extracted core dir… | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-PCR-CUT-PATCH-ROUTING-CONFLICT-20260519-0F2552BB75` | `2026-05-19` | [PCR-CUT (Path 14) Phase 5 verdict — 2026-05-19](<research/pcr_cut_patch_routing_conflict_20260519/phase5_verdict.md>)<br>🟡 0/8 CERTIFIED, 7/8 UNPROVEN, 1/8 sound master-INFEASIBLE. | `cut-framework` | `historical` | `historical` |
| `DOSSIER-SAC-HULL-SEPARATOR-CAPACITY-20260518-671A7E1193` | `2026-05-18` | sac hull separator capacity 20260518<br><code>docs/research/sac_hull_separator_capacity_20260518</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `cut-framework` | `historical` | `historical` |
| `DOSSIER-B1-RABSEP-ROUTING-AWARE-BINDING-20260518-E08AD6BF23` | `2026-05-18` | b1 rabsep routing aware binding 20260518<br><code>docs/research/b1_rabsep_routing_aware_binding_20260518</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `historical` |
| `DOSSIER-SETPACKING-PROVER-POC-20260517-A6B0980958` | `2026-05-17` | [Set-packing prover PoC — 2026-05-17](<research/setpacking_prover_poc_20260517/README.md>)<br>GPT 在 L14 weighted-occupancy 死路后推荐升级到 set-packing branch-and-bound prover: 直接在 (x{g,p}) 整数变量上搜, weighted LP 当 dual bound. GPT 估 1-2 个月工作. | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-PHASE0-LAZY-POWER-COMPLETION-20260517-2DD76729CA` | `2026-05-17` | [Phase 0 mini-PoC verdict — Lazy Power Completion v1](<research/phase0_lazy_power_completion_20260517/README.md>)<br>GPT v11 提的 Lazy Power Completion 架构 (master 跳 coverage 留 pole slot + completion subproblem 解电杆) 的 Phase 0 止损 gate 实测. | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-B1-POSE-BOOL-PHASE0-20260517-DBAB7753FE` | `2026-05-17` | [B1 Phase 0 verdict — pose-bool master + powercoverage](<research/b1_pose_bool_phase0_20260517/README.md>)<br>Date: 2026-05-17 Lever: B1 (唯一未试的 paradigm lever, 在 L1-L16 14 条全死 + L11 用户拒绝后) Decision: 用户授权走 B1, ROI 自决 | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-V8-ANCHOR-SLICING-SMOKE-20260516-66643824CB` | `2026-05-16` | [v8 anchor slicing 实测归档 — 2026-05-16](<research/v8_anchor_slicing_smoke_20260516/README.md>)<br>GPT Pro 在 v7 review 包基础上, 针对 Path 8 (ghost-anchor disjunctive decomposition) 给出 v8 完整 patch + 交付包. 本目录归档该 patch + 我们本地实测数据 + verdict 数据点. | `other` | `historical` | `historical` |
| `DOSSIER-V10-WITNESS-PREFLIGHT-SMOKE-20260516-1FA7D0C7BB` | `2026-05-16` | [v10 witness preflight 实测归档 — 2026-05-16](<research/v10_witness_preflight_smoke_20260516/README.md>)<br>GPT Pro 在 v9 review 包基础上 (注: v9 已记录 v8 anchor slicing 失败), 提出 witness-only mandatory-placement preflight 方案. 本目录归档 patch + 实测数据 + verdict 数据点. | `witness-lower-bound` | `historical` | `historical` |
| `DOSSIER-L14-WEIGHTED-OCCUPANCY-POC-20260516-6AF12BD79C` | `2026-05-16` | [L14 weighted-occupancy blocker oracle PoC — 2026-05-16](<research/l14_weighted_occupancy_poc_20260516/README.md>)<br>GPT Pro 在收到 v10 死路 + 强化版 prompt (要求方案对准 upper-bound INFEASIBLE 排除, 不准 anecdotal "不可达") 后, 给出proof-carrying weighted-occupancy blocker oracle (Farkas-style 整数证书… | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-D-STEP2-HINT-TRIALS-20260516-8794B39D8A` | `2026-05-16` | [D step 2 Hint Trials — 2026-05-16](<research/d_step2_hint_trials_20260516/README.md>)<br>5 个 hint trial 的 campaign state + telemetry 归档. 验证 community blueprint hint 注入对 master FEASIBLE 率的影响. | `other` | `historical` | `historical` |
| `DOSSIER-TERMINAL-NO-SOLUTION-EVIDENCE-CONTRACT-DESIGN-V2-473B668ADD` | `未标日期` | [Terminal 全域无解证书合同设计稿 v2](<research/terminal_no_solution_evidence_contract_design_v2.md>)<br>Status: HISTORICALORPLAN（研究层设计稿，不改生产代码/锁面） Authored: 2026-07-04（v2，取代 v1；v2.1 = 本地核查回收；v3 = GPT Pro 终审回收——schema 分层 proposalcore/sealedpublic + 负向复验/seal diges… | `other` | `historical` | `historical` |
| `DOSSIER-TERMINAL-NO-SOLUTION-EVIDENCE-CONTRACT-DESIGN-V1-A9EA1B8AA3` | `未标日期` | [Terminal 全域无解证书合同设计稿 v1](<research/terminal_no_solution_evidence_contract_design_v1.md>)<br>Status: HISTORICALORPLAN（研究层设计稿，不改生产代码/锁面） Authored: 2026-07-04 填的洞： src/search/outersearch.py:1982-1989——候选域穷尽但无任何 certified 候选时，当前 terminal-frontier 证据 schem… | `other` | `historical` | `historical` |
| `DOSSIER-Q1-INFEASIBILITY-CLASS-TAXONOMY-DESIGN-V1-69B91DF7A9` | `未标日期` | [Q1 不可行类分类学与完备性命题设计稿 v2](<research/q1_infeasibility_class_taxonomy_design_v1.md>)<br>Status: HISTORICALORPLAN（研究层设计稿，不改生产代码/锁面） Authored: 2026-07-05（v1 同日送双会话对抗审；v2 = 外审回收版—— 会话 A 判"架构级重写"、会话 B 判"修复后可作 Q1a 基准"，两份实质收敛； v2 按两份修复文本融合重写 §2/§3/§4/§5… | `other` | `historical` | `historical` |
| `DOSSIER-P3-0-FORMAL-VERIFICATION-HEAD-START-DESIGN-V1-B01927D599` | `未标日期` | [P3.0 形式化证明头启动 — 双轴架构与首批机器检查定理（v2，2026-07-05）](<research/p3_0_formal_verification_head_start_design_v1.md>)<br>项目的"证明"信任面拆成两个正交的轴,形式化投资必须分开对待: | `formal-verification` | `historical` | `historical` |
| `DOSSIER-P2-0-THROUGHPUT-CERTIFICATION-PARADIGM-DESIGN-V2-AB7D01DE56` | `未标日期` | [P2.0 吞吐认证范式设计稿 v2](<research/p2_0_throughput_certification_paradigm_design_v2.md>)<br>Status: HISTORICALORPLAN（研究层设计稿，不改生产代码/锁面） Authored: 2026-07-04（v2，取代 v1；v2.1 = 本地三路核查回收；v3 = GPT Pro 终审回收——TP7-D 验证器补 A13/HOL 验收义务、selected-solution nogood 改完… | `solver-experiment`, `p2-throughput` | `historical` | `historical` |
| `DOSSIER-P2-0-THROUGHPUT-CERTIFICATION-PARADIGM-DESIGN-V1-1282665D68` | `未标日期` | [P2.0 吞吐认证范式设计稿 v1](<research/p2_0_throughput_certification_paradigm_design_v1.md>)<br>Status: HISTORICALORPLAN（研究层设计稿，不是生产实现，不改变任何锁边界） Authored: 2026-07-04 Scope authority: 在本稿全部落地并走完 freeze-ritual 之前，PROJECTLOCK.md §1A B 块（吞吐/带宽/离散容量流 OUT-OF-SC… | `solver-experiment`, `p2-throughput` | `historical` | `historical` |
| `DOSSIER-P1-2-V99-CLOSE-KERNEL-SEALING-207F650E44` | `未标日期` | [P1.2 V99 close-kernel sealing](<research/p1_2_v99_close_kernel_sealing.md>)<br>P1.2 proof-bearing sink 与 close-kernel 的 tracked review anchor。 | `p1_2-proof-chain` | `active` | `current_evidence` |
| `DOSSIER-P1-2-V98-B5A-SYMLINK-AUTHORITY-SEALING-E71458350B` | `未标日期` | [P1.2 V98 B5A symlink-authority sealing](<research/p1_2_v98_b5a_symlink_authority_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V97-CANONICAL-CHECKPOINT-AUTHORITY-SEALING-CE3B241BB4` | `未标日期` | [P1.2 V97 canonical-checkpoint authority sealing](<research/p1_2_v97_canonical_checkpoint_authority_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain`, `rules-semantics` | `historical` | `historical` |
| `DOSSIER-P1-2-V96-SYMLINK-ANCESTOR-BOUNDARY-SEALING-076F167DB3` | `未标日期` | [P1.2 V96 symlink-ancestor boundary sealing](<research/p1_2_v96_symlink_ancestor_boundary_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V95-OPTIONAL-METADATA-AND-STOP-REASON-SEALING-9738EDCE9C` | `未标日期` | [P1.2 V95 optional-metadata and stop-reason sealing](<research/p1_2_v95_optional_metadata_and_stop_reason_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V94-PROTOCOL-STORAGE-SURPLUS-SEALING-D2DDA99FE5` | `未标日期` | [P1.2 V94 protocol-storage surplus sealing](<research/p1_2_v94_protocol_storage_surplus_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V93-NOTE-AND-SOLUTION-ENTRY-SEALING-3ECFEAADAD` | `未标日期` | [P1.2 V93 note and solution-entry sealing](<research/p1_2_v93_note_and_solution_entry_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V92-RELEASE-STATUS-ALLOWLIST-SEALING-3C2335E2DC` | `未标日期` | [P1.2 V92 release-status allowlist sealing](<research/p1_2_v92_release_status_allowlist_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain`, `industrial-delivery` | `historical` | `historical` |
| `DOSSIER-P1-2-V91-NESTED-PUBLIC-FIELD-SEALING-4D91AABA1A` | `未标日期` | [P1.2 V91 nested public-field sealing](<research/p1_2_v91_nested_public_field_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V90-FINAL-RESULT-FIELD-ALLOWLIST-SEALING-81D82D7C67` | `未标日期` | [P1.2 V90 final-result field-allowlist sealing](<research/p1_2_v90_final_result_field_allowlist_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V89-GHOST-PICK-TERMINAL-BINDING-SEALING-C6B2882B47` | `未标日期` | [P1.2 V89 ghost-pick terminal binding sealing](<research/p1_2_v89_ghost_pick_terminal_binding_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V88-GHOST-ANCHOR-REQUIRED-SEALING-D1943B9A4D` | `未标日期` | [P1.2 V88 ghost-anchor required sealing](<research/p1_2_v88_ghost_anchor_required_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V87-ANCHOR-AND-POLE-IRREDUNDANCY-SEALING-252F310360` | `未标日期` | [P1.2 V87 ghost-anchor and pole-irredundancy terminal sealing](<research/p1_2_v87_anchor_and_pole_irredundancy_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V86-POWER-WITNESS-TERMINAL-SEALING-209B19CC9E` | `未标日期` | [P1.2 V86 power-witness terminal sealing](<research/p1_2_v86_power_witness_terminal_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain`, `witness-lower-bound` | `historical` | `historical` |
| `DOSSIER-P1-2-V85-REQUIRED-OPTIONAL-TERMINAL-SEALING-0C5E057996` | `未标日期` | [P1.2 V85 required-optional terminal sealing](<research/p1_2_v85_required_optional_terminal_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V84-LAYOUT-OPTIMALITY-AND-ARTIFACT-BOUNDARY-SEALING-2646648D75` | `未标日期` | [P1.2 V84 layout-optimality and artifact-boundary sealing](<research/p1_2_v84_layout_optimality_and_artifact_boundary_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V83-GEOMETRY-WITNESS-NOGOOD-SCOPE-AND-LOADER-SEALIN-428112A0D6` | `未标日期` | [P1.2 V83 geometry-witness, nogood-scope, and mandatory-loader sealing](<research/p1_2_v83_geometry_witness_nogood_scope_and_loader_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain`, `witness-lower-bound` | `historical` | `historical` |
| `DOSSIER-P1-2-V82-ORIENTED-DOMAIN-AND-CUT-REPLAY-SEALING-4A8EF4883C` | `未标日期` | [P1.2 V82 oriented candidate domain and persisted-cut replay sealing](<research/p1_2_v82_oriented_domain_and_cut_replay_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain`, `cut-framework` | `historical` | `historical` |
| `DOSSIER-P1-2-V81-PARTIAL-PRECHECK-AND-RELEASE-CLAIM-SEALING-4FA1510135` | `未标日期` | [P1.2 V81 partial-precheck and release-claim sealing](<research/p1_2_v81_partial_precheck_and_release_claim_sealing.md>)<br>Date: 2026-06-11 | `p1_2-proof-chain`, `industrial-delivery` | `historical` | `historical` |
| `DOSSIER-P1-2-V80-DENY-UNKNOWN-CERTIFIED-SURFACE-11A22CC93C` | `未标日期` | [P1.2 V80 deny-unknown certified-surface hardening](<research/p1_2_v80_deny_unknown_certified_surface.md>)<br>Date: 2026-06-10 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V79-TERMINAL-DOMAIN-AXIS-SEALING-CB3497A612` | `未标日期` | [P1.2 V79 terminal candidate-domain axis sealing](<research/p1_2_v79_terminal_domain_axis_sealing.md>)<br>Date: 2026-06-10 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V78-CERTIFIED-MANIFEST-WRITER-CANONICAL-SURFACE-14CBB05590` | `未标日期` | [P1.2 V78 certified manifest writer canonical-surface hardening](<research/p1_2_v78_certified_manifest_writer_canonical_surface.md>)<br>Date: 2026-06-10 | `p1_2-proof-chain`, `rules-semantics` | `historical` | `historical` |
| `DOSSIER-P1-2-V77-DELIVERY-MANIFEST-WRITER-AUTHORITY-9337E8274B` | `未标日期` | [P1.2 V77 delivery manifest writer authority review](<research/p1_2_v77_delivery_manifest_writer_authority.md>)<br>Date: 2026-06-10 | `p1_2-proof-chain`, `industrial-delivery` | `historical` | `historical` |
| `DOSSIER-P1-2-V76-PROJECT-BOUND-TERMINAL-EVIDENCE-43DCB88753` | `未标日期` | [P1.2 V76 project-bound terminal evidence review](<research/p1_2_v76_project_bound_terminal_evidence.md>)<br>Date: 2026-06-10 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V75-TERMINAL-FRONTIER-EVIDENCE-SEALING-C43D367D50` | `未标日期` | [P1.2 V75 Terminal Frontier Evidence Sealing](<research/p1_2_v75_terminal_frontier_evidence_sealing.md>)<br>V74 made the public CERTIFIED surface verifier authoritative over disk state, strict JSON, and exact-artifact hashes. The next review pass found that this oute… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V74-CERTIFIED-SURFACE-AUTHORITY-HARDENING-91A96BFE49` | `未标日期` | [P1.2 V74 Certified Surface Authority Hardening](<research/p1_2_v74_certified_surface_authority_hardening.md>)<br>V73 correctly moved public CERTIFIED publication into one verifier, but the review found one remaining architectural wrinkle: the verifier still accepted calle… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V73-CERTIFIED-SURFACE-VERIFIER-CONSOLIDATION-7AA51E1A9F` | `未标日期` | [P1.2 V73 Certified Surface Verifier Consolidation](<research/p1_2_v73_certified_surface_verifier_consolidation.md>)<br>V72 closed the known sibling bypasses, but the review pattern showed a deeper risk: multiple public read surfaces still had enough local predicate logic to inv… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V66-STALE-DELIVERY-ARTIFACT-GUARD-E897C29E8C` | `未标日期` | [P1.2 V66 stale delivery artifact guard](<research/p1_2_v66_stale_delivery_artifact_guard.md>)<br>V66 closes two certifiedexact fail-closed residue paths. First, blocker branches already cleared terminal finalresult / finalstatus in the campaign checkpoint,… | `p1_2-proof-chain`, `industrial-delivery` | `historical` | `historical` |
| `DOSSIER-P1-2-V66-CERTIFIED-LIFECYCLE-EVIDENCE-CONSOLIDATION-CAF85D6BDF` | `未标日期` | [P1.2 V66 certified lifecycle evidence consolidation](<research/p1_2_v66_certified_lifecycle_evidence_consolidation.md>)<br>Date: 2026-06-09 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V64-POWER-WITNESS-REPRESENTATION-ENV-GUARD-1E7C6CB745` | `未标日期` | [P1.2 V64 power-witness representation env guard](<research/p1_2_v64_power_witness_representation_env_guard.md>)<br>V64 extends the V63 certified exact terminal-evidence boundary to sibling master/witness representations exposed by environment/debug knobs. A certified exact… | `p1_2-proof-chain`, `witness-lower-bound` | `historical` | `historical` |
| `DOSSIER-P1-2-V63-TERMINAL-EVIDENCE-EXPORT-BOUNDARY-REVIEW-C1B9CAC680` | `未标日期` | [P1.2 V63 terminal evidence export boundary review](<research/p1_2_v63_terminal_evidence_export_boundary_review.md>)<br>This note records the V63 follow-up hardening for the V62 terminal frontier evidence contract. | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V62-FRONTIER-TERMINAL-EVIDENCE-AND-OUTER-MASTER-DOM-BDCFA7A310` | `未标日期` | [P1.2 V62 frontier terminal evidence and outer master-domain guard](<research/p1_2_v62_frontier_terminal_evidence_and_outer_master_domain_guard.md>)<br>Status: reset-grade algorithmic / proof-obligation consolidation input. | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V61-MASTER-DOMAIN-CANDIDATE-FRONTIER-CONTRACT-9A8B2351BE` | `未标日期` | [P1.2 V61 master-domain and candidate-frontier contract](<research/p1_2_v61_master_domain_candidate_frontier_contract.md>)<br>V61 is a reset-grade sibling of the V57-V60 certified cut replay/domain-contract family. It does not reopen the retired V47-V50 receipt/counter authority. The… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V60-MASTER-DOMAIN-CONTRACT-996F05F604` | `未标日期` | [P1.2 V60 master-domain contract hardening](<research/p1_2_v60_master_domain_contract.md>)<br>Certified exact campaign candidates are full ghost-anchor-domain claims. The runtime may expose experimental anchor-slicing controls for RAM probes, but a term… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V59-CONDITION-REQUIRED-CUT-DOMAIN-VALIDATION-FC7B10C2FC` | `未标日期` | [P1.2 V59 condition-required cut domain validation](<research/p1_2_v59_condition_required_cut_domain_validation.md>)<br>Status: patch evidence for a V59 certified lifecycle false-negative found in zmd36.7z. | `p1_2-proof-chain`, `cut-framework` | `historical` | `historical` |
| `DOSSIER-P1-2-V58-CONDITION-REQUIRED-CUT-ANCHOR-VALIDATION-3F6EB607C8` | `未标日期` | [P1.2 V58 condition-required cut anchor validation](<research/p1_2_v58_condition_required_cut_anchor_validation.md>)<br>Status: patch evidence for a V58 certified lifecycle false-negative found in zmd35.7z. | `p1_2-proof-chain`, `cut-framework` | `historical` | `historical` |
| `DOSSIER-P1-2-V56-CERTIFIED-CUT-REPLAY-CONSOLIDATION-D34374EFFA` | `未标日期` | [P1.2 V56 certified cut replay faithfulness consolidation](<research/p1_2_v56_certified_cut_replay_consolidation.md>)<br>Date: 2026-06-08 | `p1_2-proof-chain`, `cut-framework` | `historical` | `historical` |
| `DOSSIER-P1-2-V50-MANUAL-PHASE-GATE-SIMPLIFICATION-3D7469FFC5` | `未标日期` | [P1.2 V50 manual phase-gate simplification](<research/p1_2_v50_manual_phase_gate_simplification.md>)<br>Date: 2026-06-08 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V46-PHASE-GATE-GIT-AUTHORITY-AND-METADATA-RESET-33949AE9C9` | `未标日期` | [P1.2 V46 phase-gate Git authority and metadata reset](<research/p1_2_v46_phase_gate_git_authority_and_metadata_reset.md>)<br>Package: v46candidate Date: 2026-06-08 Baseline reviewed: zmd22.7z Baseline archive SHA256: 5AC8255BB93CF299FF96481806CE7C957CBA9E30590568182E5925624618FBA1 Ba… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V45-PHASE-GATE-MARKUP-AND-GIT-AUTHORITY-RESET-17F015AF60` | `未标日期` | [P1.2 V45 phase-gate markup and Git authority reset](<research/p1_2_v45_phase_gate_markup_and_git_authority_reset.md>)<br>Package: v45candidate | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V44-PHASE-GATE-SOURCE-AUTHORITY-AND-METADATA-RESET-7036E4E74D` | `未标日期` | [P1.2 V44 phase-gate source authority and metadata reset](<research/p1_2_v44_phase_gate_source_authority_and_metadata_reset.md>)<br>Package: v44candidate Review type: independentfullexternal Outcome: majorsoundnessfindingsfound Major or soundness findings: 2 Resets counter: true | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V38-PHASE-GATE-PACKAGE-IDENTITY-A4399F1D27` | `未标日期` | [P1.2 V38 Phase Gate Package Identity Hardening](<research/p1_2_v38_phase_gate_package_identity.md>)<br>The V38 clean-review pass found that phase-gate clean evidence could still be bound to a self-declared reviewhistory[].package string instead of the actual cur… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V37-PHASE-GATE-PROVENANCE-HARDENING-2F7734A113` | `未标日期` | [P1.2 V37 phase-gate provenance hardening](<research/p1_2_v37_phase_gate_provenance_hardening.md>)<br>This note records the machine-checkable provenance invariants added after the V37 clean-review candidate probe. A clean-review slot is not satisfied by the spe… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V31-V46-FINDING-TAXONOMY-8B3B767053` | `未标日期` | [P1.2 V31-V46 finding taxonomy and review-protocol reset](<research/p1_2_v31_v46_finding_taxonomy.md>)<br>Package: v46reviewprotocolredesign Algorithmic reset package: v32runtimecachesourcedigestconsolidation Date: 2026-06-08 Review type: internalreviewprotocolrede… | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V31-POSTMORTEM-PROOF-OBLIGATION-CONSOLIDATION-B8536C155B` | `未标日期` | [P1.2 v31 postmortem: proof-obligation consolidation](<research/p1_2_v31_postmortem_proof_obligation_consolidation.md>)<br>Date: 2026-06-07 | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V31-CANDIDATE-REVIEW-RESET-8EB314EEA9` | `未标日期` | [P1.2 v31 candidate review reset evidence](<research/p1_2_v31_candidate_review_reset.md>)<br>Status: NOT CLEAN. | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-P1-2-V30-CANDIDATE-REVIEW-RESET-D5557D4DD7` | `未标日期` | [P1.2 v30 candidate review reset evidence](<research/p1_2_v30_candidate_review_reset.md>)<br>Status: NOT CLEAN. | `p1_2-proof-chain` | `historical` | `historical` |
| `DOSSIER-PROFILES-A2B11892A9` | `未标日期` | [P1 #20 短跑性能分析（2026-05-10）](<research/profiles/p1_20_short_profile_20260510/README.md>)<br>CP-SAT 求解器一次约 10 分钟的 short profile，目的是用 py-spy --native 找到真实热点，给后续优化（编译器、缓存、CP-SAT 参数）打底。 | `solver-experiment` | `historical` | `historical` |
| `DOSSIER-P1-3-F5-ORBIT-LIFT-SOUNDNESS-DESIGN-V2-D1ACE22754` | `未标日期` | [F5 orbit-aware lifting soundness 论证与实施规格 v2](<research/p1_3_f5_orbit_lift_soundness_design_v2.md>)<br>Status: HISTORICALORPLAN（研究层设计稿；F5 生产接入属 P1.3） Authored: 2026-07-04（v2，取代 v1；v2.1 = 本地核查回收；v3 = GPT Pro 终审回收——immutablescope 白/黑名单明文化、presence-key alias 禁令、can… | `other` | `historical` | `historical` |
| `DOSSIER-P1-3-F5-ORBIT-LIFT-SOUNDNESS-DESIGN-V1-291502415A` | `未标日期` | [F5 orbit-aware lifting soundness 论证与实施规格 v1](<research/p1_3_f5_orbit_lift_soundness_design_v1.md>)<br>Status: HISTORICALORPLAN（研究层设计稿；F5 生产接入属 P1.3，本稿不改生产代码、不动锁面） Authored: 2026-07-04 先例定位： PROJECTLOCK.md §3A（2026-05-22）已强制 "state 必走 group-orbit 而非 per-instance… | `other` | `historical` | `historical` |
| `DOSSIER-P3-0C-BINDING-PB-SIDECAR-DESIGN-V1-985EA9D7F5` | `未标日期` | [binding 子问题 PB 独立重建 + VeriPB sidecar——设计稿 v2](<research/p3_0c_binding_pb_sidecar_design_v1.md>)<br>对生产链宣布的 binding INFEASIBLE 判决，用一条异构旁路复验：从冻结工件 独立重建同一子问题的伪布尔（PB/OPB）编码 → 用原生产证明日志的求解器 （RoundingSat）重解 → 用独立检查器（VeriPB 3.0）复核其 UNSAT 证明 → 与生产 判决对账。最危险的失败模式不是报 UN… | `formal-verification` | `historical` | `historical` |

## local optional artifact root 全表

这些目录是本机证据入口。缺失不使 checker 失败，但本机一旦出现新的一级目录，就必须登记。

| Dossier ID | 日期 | 标题 / 入口 | topics | lifecycle | relevance |
|---|---|---|---|---|---|
| `DOSSIER-P-REINSERTION-AUDIT-20260820-8BB5417ED3` | `2026-08-20` | [PREINSERTIONGAP 异源验收报告](<../.artifacts/p_reinsertion_audit_20260820/AUDIT_REPORT.md>)<br>异源验收证据包；包内总判词/状态：PASS_WITH_SCOPED_ERRATA_LOCALIZATION_UNDER_DETERMINED。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-MUS-LANDSCAPE-20260820-CC6900A234` | `2026-08-20` | p mus landscape 20260820<br><code>.artifacts/p_mus_landscape_20260820</code><br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：在途、未封账。仅作为 active open workflow 进入 inventory，不进入 historical triage，… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-CPU-L3-PERF-MEASUREMENT-20260820-212859A058` | `2026-08-20` | [CPU 大三缓选购 perf 实测批 — REPORT](<../.artifacts/cpu_l3_perf_measurement_20260820/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE_RESEARCH_ONLY_NON_AUTHORIZING。验收状态：包内状态 COMPLETE_RESEARCH_ONLY_NON_AUTHORIZING；REVIEW_CHECKLIST 无对应异源验收节；出处：无对应 REVIEW_CHE… | `solver-experiment` | `active` | `unreviewed` |
| `DOSSIER-P-SIGNATURE-COOCCURRENCE-MATRIX-20260819-51366B1E18` | `2026-08-19` | [签名层逐事件成员集与共现矩阵](<../.artifacts/p_signature_cooccurrence_matrix_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS。验收状态：包内 checker/负测封账；REVIEW_CHECKLIST 未给出后续独立异源终结节；出处：REVIEW_CHECKLIST.md lines 155-173。 本登记不是 knowledge semantic review，不新增或升… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-NARROW-CORE-READMISSION-20260819-CD8FDB7CD0` | `2026-08-19` | [窄核重准入与几何证书对账](<../.artifacts/p_narrow_core_readmission_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE_RESEARCH_ONLY（最终判词见 REPORT.md §1）。验收状态：REVIEW_CHECKLIST 仍列待终检项，未见独立异源终结节；出处：REVIEW_CHECKLIST.md lines 257-297。 本登记不是 knowl… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-INTERIOR-BOUND-AUDIT-20260819-54D94C5C37` | `2026-08-19` | [异源验收：BINTERIOR 内部封锁精确下界包审计](<../.artifacts/p_interior_bound_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：CONFIRMED（定理本体）+ NEEDS_CORRECTION（语料观测与 3×3 护栏）。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 prod… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-REALIZABLE-AUDIT-20260819-9056A4CF0C` | `2026-08-19` | [异源验收：BDNFREALIZABLE 可实现 completeness 证据包审计](<../.artifacts/p_dnf_realizable_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：CONFIRMED（科学结论）+ NEEDS_CORRECTION（作用域叙述与独立性分层）。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 produ… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-ENUMERATION-AUDIT-20260819-AC4209EBC5` | `2026-08-19` | [异源验收：BDNFENUMERATE 可实现封锁构型完整枚举包审计](<../.artifacts/p_dnf_enumeration_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：CONFIRMED（全部数值）+ NEEDS_CORRECTION（作用域叙述）。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-UNIVERSAL-AUDIT-20260819-B7FD9D9756` | `2026-08-19` | [异源验收：BDNF 普适 soundness 证据包审计](<../.artifacts/p_dnf_universal_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：两条头条结论均确认；另有三条叙述/工程卫生修正。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production authority。 | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-COMPLETENESS-AUDIT-20260819-8A148379D6` | `2026-08-19` | [异源验收：BDNF 普适 completeness 证据包审计](<../.artifacts/p_dnf_completeness_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：三条头条结论在各自声明域内均正确；证据选择与若干解释项 NEEDS_CORRECTION。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 product… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-INTERIOR-3X3-AUDIT-20260819-AB3571C590` | `2026-08-19` | [异源验收：.artifacts/pinterior3x3bound20260819](<../.artifacts/p_interior_3x3_audit_20260819/AUDIT.md>)<br>异源验收证据包；包内总判词/状态：NEEDS_CORRECTION；全部数值结论 CONFIRMED。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production authori… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-BRANCH-SOUNDNESS-MINIMAL-CORE-20260819-99AFD08610` | `2026-08-19` | [九支 DNF：分支级普适 soundness 与端点原子最小核](<../.artifacts/p_dnf_branch_soundness_minimal_core_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_ALL_NINE_UNIVERSALLY_SOUND_FULL_DROP_ONE_COMPLETE。验收状态：异源验收确认核心结论，声明层按勘误收窄；出处：REVIEW_CHECKLIST.md lines 270-286。 勘误后解释入口：.arti… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-ZEROPOLE-AUDIT-20260819-7D071A5EF4` | `2026-08-19` | [PZEROPOLE 异源验收报告](<../.artifacts/p_zeropole_audit_20260819/AUDIT_REPORT.md>)<br>异源验收证据包；包内总判词/状态：CONFIRMED_WITH_CORRECTIONS。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production authority。 | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-BRIDGE-LIVENESS-PROBE-20260819-799812E3E4` | `2026-08-19` | p bridge liveness probe 20260819<br><code>.artifacts/p_bridge_liveness_probe_20260819</code><br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-ZEROPOLE-DIAGNOSIS-20260819-442FFB6551` | `2026-08-19` | [GZEROPOLEDIAGNOSIS：30×39 重建布局的零 coverer target 归因](<../.artifacts/p_zeropole_diagnosis_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_ZERO_COVERER_CAUSE_DISTRIBUTION_GEOMETRY_DOMINANT_NO_SELECTION_OPEN。验收状态：异源验收 CONFIRMED_WITH_CORRECTIONS；承重数字零偏差；出处：REVIEW_CHE… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-INTERIOR-BLOCKADE-BOUND-20260819-7F5A5AA51B` | `2026-08-19` | [BINTERIOR：内部供电锚点封锁的完整容量定理与实例观测](<../.artifacts/p_interior_blockade_bound_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_EXACT_MINIMUM_SEVEN_AND_CORPUS_OBSERVED。验收状态：异源验收确认数值，语料解释、作用域和前提需勘误；出处：REVIEW_CHECKLIST.md lines 411-449。 勘误后解释入口：.artifacts/… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-REALIZABLE-COMPLETENESS-20260819-F79B0B2A8C` | `2026-08-19` | [BDNFREALIZABLE：可实现几何上的 completeness 与冻结模板代表性](<../.artifacts/p_dnf_realizable_completeness_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：REFUTED_REALIZABLE_COMPLETENESS_BOTH_ARITIES_EXACT_GEOMETRY_COUNTEREXAMPLES。验收状态：异源验收确认科学结论，作用域叙述与独立性需更正；出处：REVIEW_CHECKLIST.md lin… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-REALIZABLE-ENUMERATION-20260819-796C6E270A` | `2026-08-19` | [BDNFENUMERATE：可实现供电封锁构型的完整枚举](<../.artifacts/p_dnf_realizable_enumeration_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE_BOTH_ARITIES_EXACT_REALIZABLE_BLOCKADE_CATALOG。验收状态：异源验收确认作用域内枚举，shape scope 与共模边界需勘误；出处：REVIEW_CHECKLIST.md lines 379-407… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-DNF-UNIVERSAL-COMPLETENESS-20260819-26F6F7EF75` | `2026-08-19` | [BDNFCOMPLETE：九支 DNF 的普适 completeness 与冻结模板库隐式不变量](<../.artifacts/p_dnf_universal_completeness_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：REFUTED_UNIVERSAL_COMPLETENESS_BOTH_ARITIES_FINITE_PARTITION_AND_LIBRARY_INVARIANTS_PROVED。验收状态：异源验收完成；反例与数值存活，作用域/证据归属需勘误；出处：REVIE… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-BLOCKADE-CLIPMAP-20260819-5F53E26B00` | `2026-08-19` | [BCLIPMAP：全网格 ghost-free 最小封锁数图](<../.artifacts/p_blockade_clipmap_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_COMPLETE_GHOST_FREE_CLIPMAP_GHOST_OVERLAY_AND_CATALOG_RECONCILIATION。验收状态：异源验收总判词 NEEDS_CORRECTION；数值零分歧，声明层勘误；出处：REVIEW_CHECK… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-CLIPMAP-AUDIT-20260819-0CC22B0448` | `2026-08-19` | [BCLIPMAP 异源验收报告](<../.artifacts/p_clipmap_audit_20260819/AUDIT_REPORT.md>)<br>异源验收证据包；包内总判词/状态：NEEDS_CORRECTION；全部独立重算数值零分歧，修正限于声明层。本条仅登记验收材料的 inventory 与 provenance，不构成对验收包的二次 semantic review，也不提升 claim、owner、certified 或 production auth… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-INTERIOR-3X3-BOUND-20260819-3503337709` | `2026-08-19` | [B3X3：内部 3×3 需电目标的精确封锁下界与 pole 统一语义](<../.artifacts/p_interior_3x3_bound_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_EXACT_MINIMUM_SIX_AND_POLE_ACCOUNTING_RESOLVED。验收状态：异源验收总判词 NEEDS_CORRECTION；数值由独立第三模型复现；出处：REVIEW_CHECKLIST.md lines 453-493。… | `other` | `active` | `unreviewed` |
| `DOSSIER-P-REINSERTION-GAP-20260819-2C69D7570F` | `2026-08-19` | [AREINSERTIONGAP：13-event 走廊的重插入缺口机制](<../.artifacts/p_reinsertion_gap_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_JOINT_COUPLING_TWO_ATOM_SELF_POWER_MUS。验收状态：异源验收 PASS_WITH_SCOPED_ERRATA_LOCALIZATION_UNDER_DETERMINED；出处：REVIEW_CHECKLIST.md… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-TRUE-REPAIR-CONFLICT-EXTRACTION-20260819-DAB640A917` | `2026-08-19` | [A3：真重排无条件 conflict 提炼环](<../.artifacts/p_true_repair_conflict_extraction_20260819/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：REPORT_FINALIZED_NO_SEPARATE_TERMINAL_RECEIPT。验收状态：异源验收完成；科学结论成立，但招牌负面归因被包内库存推翻；出处：REVIEW_CHECKLIST.md lines 233-255。 本登记不是 knowled… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-CFG-RELAXATION-CERTIFICATES-20260818-76C8EC34D8` | `2026-08-18` | [配置松弛纯有理对偶证书与负控（2026-08-18）](<../.artifacts/cfg_relaxation_certificates_20260818/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `upper-bound`, `formal-verification` | `active` | `unreviewed` |
| `DOSSIER-P-TRUE-REPLACEMENT-REPAIR-20260818-3044681953` | `2026-08-18` | [真重排语义下的供电修复走廊](<../.artifacts/p_true_replacement_repair_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_TRUE_REPLACEMENT_INTERVALS_OPEN_WITH_TYPED_CENSORING。验收状态：异源结构与语义审计已完成，结论带六项链条缺口；出处：REVIEW_CHECKLIST.md lines 18-24。 本登记不是 kno… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-TRUE-REPAIR-CHAIN-HARDENING-20260818-AF82028E42` | `2026-08-18` | [真重排修复走廊证据链补链批](<../.artifacts/p_true_repair_chain_hardening_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_TRUE_REPAIR_EVIDENCE_CHAIN_HARDENED。验收状态：异源验收完成；科学区间存活，能力抬头与独立性需收窄；出处：REVIEW_CHECKLIST.md lines 48-90。 本登记不是 knowledge semanti… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-NOVELTY-STAGNATION-WINDOWS-20260818-570D7BA230` | `2026-08-18` | [死因谱新颖性停滞点与可压缩性梯度](<../.artifacts/p_novelty_stagnation_windows_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_OFFLINE_NOVELTY_STAGNATION_AND_COMPRESSIBILITY_GRADIENT_COMPLETE。验收状态：收割终稿已封账；REVIEW_CHECKLIST 的追溯终检项仍未显式勾销；出处：REVIEW_CHECKLIS… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-CSPACE-BLOCKADE-COMPILER-20260818-F304516884` | `2026-08-18` | [构型空间供电封锁编译器试点三](<../.artifacts/p_cspace_blockade_compiler_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_REUSABLE_CSPACE_BLOCKADE_COMPILER_RESEARCH_ONLY。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P-GHOSTFRONT-FAMILY-JUDGMENT-20260818-2441DB4B52` | `2026-08-18` | [幽灵矩形前格封锁的四原子家族化 Judgment](<../.artifacts/p_ghostfront_family_judgment_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_FOUR_ATOM_PARAMETERIZED_FAMILY_JUDGMENT_RESEARCH_ONLY。验收状态：收割终稿已封账；REVIEW_CHECKLIST 的追溯终检项仍未显式勾销；出处：REVIEW_CHECKLIST.md lines… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-CANDIDATE-CONDITION-MATRIX-V1-20260818-780443B8C2` | `2026-08-18` | [常设候选×条件值矩阵 v1](<../.artifacts/candidate_condition_matrix_v1_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不新增或升格 claim。 | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-POSTMEM-BLIND-COLLISION-20260818-4DB4F7129F` | `2026-08-18` | [postmem 盲测 B 段对撞裁断](<../.artifacts/postmem_blind_collision_20260818/COLLISION_REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：ARTIFACT 7 / NEW 2 / REDISCOVERED 1 / CONTRADICTS 1。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 勘误后解释入口：.artifact… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P0-FRONTIER-RERUN-20260818-DDAC26E3F1` | `2026-08-18` | [P0：current claim 账本到 production 矩形前沿的保守投影](<../.artifacts/p0_frontier_rerun_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：MANIFEST_SEALED_NO_TOP_LEVEL_STATUS。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-EMITTER-PROVENANCE-RECONCILIATION-20260818-8050D1C018` | `2026-08-18` | p emitter provenance reconciliation 20260818<br><code>.artifacts/p_emitter_provenance_reconciliation_20260818</code><br>Inventory-only 登记。包内终态判词/状态：MANIFEST_SEALED_NO_TOP_LEVEL_STATUS。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-MIXED-ENDPOINT-CLOSED-FORM-20260818-2E5F56A8F8` | `2026-08-18` | [Mixed family 端点不等式显式闭式](<../.artifacts/p_mixed_endpoint_closed_form_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_NINE_BRANCH_CLOSED_FORM_AND_EXTENSION_PROBE_COMPLETE。验收状态：收割终稿已封账；REVIEW_CHECKLIST 未给出独立异源终结节；出处：REVIEW_CHECKLIST.md lines 5-2… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-LBBD-MINIMAL-CORE-TOOLKIT-20260818-8B00079DD2` | `2026-08-18` | [LBBD Layered Minimization Toolkit](<../.artifacts/p_lbbd_minimal_core_toolkit_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不新增或升格 claim。 | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-NOVELTY-L3-CONTRACT-HARDENING-20260818-304523520A` | `2026-08-18` | [L3 触发器证据契约补强](<../.artifacts/p_novelty_l3_contract_hardening_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：COMPLETE。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不新增或升格 claim。 | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P-CORE-SHELL-PROPOSITION-20260818-C3CC2E9F4F` | `2026-08-18` | [deep v2 事件固定核心 ⊕ 可变壳层命题](<../.artifacts/p_core_shell_proposition_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS。验收状态：异源勘误闭合；按包内 ERRATA 与边界声明图解释；出处：REVIEW_CHECKLIST.md lines 92-173。 勘误后解释入口：.artifacts/p_core_shell_proposition_20260818/ERRA… | `other` | `active` | `unreviewed` |
| `DOSSIER-GPT-HARVEST-20260818-85692BD024` | `2026-08-18` | [A1 真重排修复走廊补链批 —— GPT 终稿](<../.artifacts/gpt_harvest_20260818/A1_FINAL_MESSAGE.md>)<br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `documentation-governance`, `reasoning-system` | `active` | `unreviewed` |
| `DOSSIER-P-LBBD-30X39-MULTI-INCUMBENT-20260818-0C7F9B4622` | `2026-08-18` | [30×39 多 incumbent 三层死因谱稳定性研究](<../.artifacts/p_lbbd_30x39_multi_incumbent_20260818/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：PASS_WITH_TYPED_GEOMETRY_CENSORING。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不新… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-CFG-RELAXATION-ENUM-CLOSURE-23X51-20260818-176509E438` | `2026-08-18` | [23×51 配置松弛枚举完备性封口（2026-08-18）](<../.artifacts/cfg_relaxation_enum_closure_23x51_20260818/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `upper-bound`, `formal-verification` | `active` | `unreviewed` |
| `DOSSIER-CFG-RELAXATION-IMPL-B-20260817-77A5280EF9` | `2026-08-17` | [配置松弛 support 独立实现 B（2026-08-17）](<../.artifacts/cfg_relaxation_impl_B_20260817/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `upper-bound`, `formal-verification` | `active` | `unreviewed` |
| `DOSSIER-CFG-RELAXATION-IMPL-A-20260817-BE414F298A` | `2026-08-17` | [配置松弛 support 独立实现 A（2026-08-17）](<../.artifacts/cfg_relaxation_impl_A_20260817/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `upper-bound`, `formal-verification` | `active` | `unreviewed` |
| `DOSSIER-NP-THEOREM-CORRESPONDENCE-20260817-6ADFE32DF1` | `2026-08-17` | [自产结构定理与数学文献对应关系](<../.artifacts/np_theorem_correspondence_20260817/GPT_CORRESPONDENCE.md>)<br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-NP-LITERATURE-RECON-20260817-C6D0998D78` | `2026-08-17` | [数学文献侦察：六堵墙的同族成果与三条高价值外环模板](<../.artifacts/np_literature_recon_20260817/GPT_MATH_RECON.md>)<br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-OUTER-LOOP-RECON-20260817-A3301A1D74` | `2026-08-17` | [推理外环三实验对账裁断全文（2026-08-17）](<../.artifacts/outer_loop_recon_20260817/B_VERDICT_FULL_20260817.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-POSTMEM-BLIND-SAMPLING-20260817-2127AF445D` | `2026-08-17` | postmem blind sampling 20260817<br><code>.artifacts/postmem_blind_sampling_20260817</code><br>本地 research/support evidence inventory；包内终态判词/状态：NO_EXPLICIT_TERMINAL_VERDICT_RECORDED；验收状态：未见集中台账中的独立异源终结节。仅作为 active open workflow 进入 inventory，不进入 historica… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P5-HORIZONTAL-CANARY-20260817-44EADE5C7E` | `2026-08-17` | [P5 水平边界供电封锁 lowering 金丝雀本地证据包（2026-08-17）](<../.artifacts/p5_horizontal_canary_20260817/REPORT.md>)<br>P5 本机证据包保存 owner 授权、消费点对账、三臂 body-generation run、六份 binary CpModel proto、producer 外独立 replay、编译义务闭合、typed endpoint 与终局报告。静态 lowering PASS；三臂均在首 incumbent 前删失，r… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P4-BLOCKADE-FAMILY-ABSTRACTION-20260817-5B9F642CB4` | `2026-08-17` | [P4 区域供电封锁 family 抽象与定理化本地证据包（2026-08-17）](<../.artifacts/p4_blockade_family_abstraction_20260817/REPORT.md>)<br>P4 本机证据包保存三类 Judgment、三个独立标准库 checker、1,728／48／664 条正域证据、6,708／136／142 条 near-miss 结果、九布局 corpus 投影、编译义务、水平类 owner-gated canary 草案与 typed 终局。payload 可在轻量 check… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P3-POWER-BLOCKADE-VALIDATION-20260817-DA81BA8459` | `2026-08-17` | [P3 区域供电封锁 family 验证本地证据包（2026-08-17）](<../.artifacts/p3_power_blockade_validation_20260817/REPORT.md>)<br>P3 本机证据包保存 42 文件样本盘点、37 个近失配、1098 个纵向／target 换位、7 个 mixed-template 正样本、两种 master 的只读 literal 审计与 typed 终局。payload 可缺失；其存在不授予 claim、cut、certified、下界或 production… | `reasoning-system`, `solver-architecture`, `witness-lower-bound` | `active` | `unreviewed` |
| `DOSSIER-P1B-JOINT-POWER-REPAIR-20260817-8F6B7DFD94` | `2026-08-17` | [P1b 九窗口联合修复与区域供电封锁候选本地证据包（2026-08-17）](<../.artifacts/p1b_joint_power_repair_20260817/REPORT.md>)<br>P1b 本机证据包保存 33×35 top-right body incumbent、exact power 分析、266→6 最小核、56 平移结构 checker、九窗口受限修复收据与 typed 终局。payload 可在轻量 checkout 缺失；其存在不授予 claim、cut、certified、下界或… | `reasoning-system`, `witness-lower-bound`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P1-WITNESS-CONSTRUCTION-20260817-D06675346E` | `2026-08-17` | [P1 受限 witness 构造本地证据包（2026-08-17）](<../.artifacts/p1_witness_construction_20260817/REPORT.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `witness-lower-bound`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-P0-FRONTIER-PROJECTION-20260817-1B1E6F4CB4` | `2026-08-17` | [P0：current claim 账本到 production 矩形前沿的保守投影](<../.artifacts/p0_frontier_projection_20260817/REPORT.md>)<br>Inventory-only 登记。包内终态判词/状态：MANIFEST_SEALED_NO_TOP_LEVEL_STATUS。验收状态：包内终态已封装；集中台账未给出可定位的独立异源终结节；出处：REVIEW_CHECKLIST.md 未显式记录。 本登记不是 knowledge semantic review，不… | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-W0-UNARY-CANARY-20260816-40F7F16A22` | `2026-08-16` | W0 一元 lowering 金丝雀共享本机证据根（GPT-5.6 Pro lineage，2026-08-16）<br><code>.artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816</code><br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-20260815-7FA2A0E225` | `2026-08-15` | [推理外环 Phase -1 本机运行证据包（2026-08-15）](<../.artifacts/solver_reasoning_outer_loop_phase_minus1_20260815/phase-minus1-r1-20260815/BATCH_SUMMARY.md>)<br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-V2-20260815-96E16B17C8` | `2026-08-15` | 推理外环 Phase -1 v2 高预算本机运行证据包（2026-08-15）<br><code>.artifacts/solver_reasoning_outer_loop_phase_minus1_v2_20260815</code><br>Local-optional evidence registered through docctl; semantic outcome is pending closure review. | `reasoning-system`, `solver-architecture` | `active` | `unreviewed` |
| `DOSSIER-APX-E-GATE-REVIEW-20260810-1E0BCC6818` | `2026-08-10` | [【过堂表】推理外环求解器 · 附录 E 七问过堂](<../.artifacts/apx_e_gate_review_20260810/PASSTHROUGH_TABLE.md>)<br>--- | `other` | `historical` | `unreviewed` |
| `DOSSIER-MEMSYS-MEETING-20260808-1BB4142581` | `2026-08-08` | [记忆系统全面复查会议 · 主持人终裁（2026-08-08）](<../.artifacts/memsys_meeting_20260808/FINAL_VERDICT.md>)<br>T1 判决：M-02「已越 25KB 字节上限」证伪。 六变体假 HOME 实验（决定性 F 臂：36,056 字节/12,360 JS 字符/150 行 → 零截断）钉死：eoe=25000 的单位是 JS 字符（UTF-16 code unit），展示时 ÷1024 印成 KB。真实 MEMORY.md = 15… | `other` | `historical` | `unreviewed` |
| `DOSSIER-GPT-PRO-REVIEW-BATCH-20260808-A687A90BB0` | `2026-08-08` | [本包是什么 · 怎么读](<../.artifacts/gpt_pro_review_batch_20260808/9_architecture_holistic_review/pkg/README.md>)<br>本包是一套尚未动工的求解器架构设计的全部在案材料，交付给你做架构级审查。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-SOLVER-RETHINK-20260808-47BE0A3C3A` | `2026-08-08` | [推理外环 solver-rethink 设计与对抗收敛包](<../.artifacts/solver_rethink_20260808/DESIGN_DOC_v2.md>)<br>本机可选的推理外环、CP-SAT 内层、完备性口径、能力缺口与对抗收敛设计包；未立线、未获 production authority。 | `reasoning-system`, `solver-architecture`, `solver-rethink` | `historical` | `historical` |
| `DOSSIER-CANONICAL-RESEAL-20260808-126986753E` | `2026-08-08` | canonical reseal 20260808<br><code>.artifacts/canonical_reseal_20260808</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `rules-semantics` | `historical` | `unreviewed` |
| `DOSSIER-MIXFLOW-DEMIX-BAN-20260807-FFEA2B3CE4` | `2026-08-07` | [更正：openyard8x8 探针装置端口朝向不忠实（2026-08-07，U-01 批发现并修）](<../.artifacts/mixflow_demix_ban_20260807/CORRECTION_open_yard_fixture_20260807.md>)<br>处置依据：team-lead 2026-08-07 拍板「openyard 装置在本批顺手修忠实（已有忠实变体， 替换 + 标注原装置缺陷即可）」。本文件是那次替换的记录。 | `p2-throughput` | `historical` | `unreviewed` |
| `DOSSIER-MIXFLOW-U01-20260807-0F66A1F37E` | `2026-08-07` | [U-01 施工席：完工待主线（2026-08-07）](<../.artifacts/mixflow_u01_20260807/AWAITING_MAINLINE.md>)<br>状态：DONE。本席没有还能自己推进的工作项了。 | `p2-throughput` | `historical` | `unreviewed` |
| `DOSSIER-GPT-PRO-REVIEW-BATCH-20260807-2DAE56A307` | `2026-08-07` | [P2.0 吞吐认证特化设计稿批（2026-08-07）](<../.artifacts/gpt_pro_review_batch_20260807/4_p2_0_specialized/README.md>)<br>性质：研究层设计稿批。不改生产代码、不改锁面、不改 canonical。落地立项待 owner 过目。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-AXIOM-ANALYSIS-20260806-A86B1853BB` | `2026-08-06` | [游戏语义最小公理系（终稿提案 v2，2026-08-06）](<../.artifacts/axiom_analysis_20260806/AXIOM_KERNEL_PROPOSAL.md>)<br>证据路标记：SIM-=模拟器源码路；OWN-=owner 定谳/记忆路；W-/M-/R-/P-/U-带词缀（如 W-MIX-02、M-AXIOM-01、R-LEMMA-01、P-BRIDGE-01、U-GAP-03）=成文规则/文书路；R-nn/B-nn/P-nn/RT-nn/A-nn/U-nn 纯数字（如 R-07… | `rules-semantics` | `historical` | `unreviewed` |
| `DOSSIER-MIXFLOW-REVIEW-PACK-20260806-8BC80DB22D` | `2026-08-06` | [外审任务书：routing 模型混流表达手术（soundness 审查）](<../.artifacts/mixflow_review_pack_20260806/staging/00_REVIEW_ASK.md>)<br>日期：2026-08-06。审查对象：对 certified-exact 求解器 routing 子问题模型的一次 可行域放宽手术（原型阶段，未合入 main、未接入认证路径）。 | `p2-throughput` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-R4-PREP-20260806-47C18A75BE` | `2026-08-06` | [band22 第四轮设计任务书](<../.artifacts/band22_r4_prep_20260806/00_TASK_BRIEF_DRAFT.md>)<br>--- | `upper-bound` | `historical` | `unreviewed` |
| `DOSSIER-GHOST-STRICT-FIX-PLAN-20260805-03154569FD` | `2026-08-05` | [认证链严格空地语义修复批 — 执行计划](<../.artifacts/ghost_strict_fix_plan_20260805/BATCH_PLAN.md>)<br>--- | `other` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-ADMISSION-SIM-20260805-81C82FE8AA` | `2026-08-05` | [准入口分拣实验 · 总判读（2026-08-05，主线代笔收口）](<../.artifacts/band22_admission_sim_20260805/FINAL_REPORT.md>)<br>不入证明链账（吞吐 OUT-OF-SCOPE）。 | `upper-bound` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-REGISTRATION-20260805-5D2448DDF7` | `2026-08-05` | [下载夹孤本抢救（20260807 晚整理时发现）](<../.artifacts/band22_registration_20260805/downloads_orphans_20260807/README.md>)<br>两件 band22 时代（08-05）交付物在全 .artifacts 无副本，原件躺 ~/下载。 band22 线已死（三见证真死），此为史料保全非现役工件。原件已移 ~/下载/旧批归档202608/。 | `upper-bound` | `historical` | `unreviewed` |
| `DOSSIER-IP-CD-SEMANTICS-20260805-7002030E2F` | `2026-08-05` | [【已取消】IndustrialPlanner 准入口限速改 CD 语义](<../.artifacts/ip_cd_semantics_20260805/PATCH_NOTES.md>)<br>状态：任务取消，代码零改动。模拟器现有的「10 秒固定窗配额」实现是对的，不需要修改。 | `industrial-delivery` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-STRICT-REDESIGN-REPLIES-20260805-2F5380CA05` | `2026-08-05` | [strict42 / band22 v2 交付说明](<../.artifacts/band22_strict_redesign_replies_20260805/r1_strict42/strict42_band22_v2_delivery/README.md>)<br>【已证明】本目录给出严格空地语义下的坐标级 (area, minside) = (42, 6) 见证。最终孔为 x=32..38, y=64..69，尺寸 7×6；孔与强制设施机身、电杆、路由的交集均为 0。 | `upper-bound` | `historical` | `unreviewed` |
| `DOSSIER-GHOST-STRICT-FIX-20260805-0FBA53DB19` | `2026-08-05` | [strict ghost 修复与复审收据](<../.artifacts/ghost_strict_fix_20260805/mutation_manifests_20260806/SUMMARY.md>)<br>2026-08-05 至 08-06 strict-semantics 修复、外审与 seal batch 的本机可选证据。 | `p1_2-proof-chain` | `historical` | `current_evidence` |
| `DOSSIER-P2-0-REFRESH-20260805-627C980F03` | `2026-08-05` | [P2.0 refresh 本地收据](<../.artifacts/p2_0_refresh_20260805/AREA_BOUND_UPGRADE_PLAN.md>)<br>P2.0 面积界与复核脚本的本机可选收据根。 | `p2-throughput` | `historical` | `current_evidence` |
| `DOSSIER-IP-ADAPTER-V3-20260805-463C50D116` | `2026-08-05` | [IP adapter v3 原生降级批 — 实施席改动说明](<../.artifacts/ip_adapter_v3_20260805/CHANGES.md>)<br>执行依据：IMPLEMENTATIONPLAN.md（原生降级批）。 范围：只改 src/adapters/industrialplanner/ 与 src/tests/ 里 industrialplanner 相关测试。 没做的（归落库席）：不重生成 data/examples/industrialplanner/… | `other` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-SIM-EXPORT-20260805-32DC974A11` | `2026-08-05` | [IndustrialPlanner Validation Report](<../.artifacts/band22_sim_export_20260805/validation_report.md>) | `upper-bound`, `industrial-delivery` | `historical` | `unreviewed` |
| `DOSSIER-EMPTINESS-RITUAL-20260805-7CDD6F4EA4` | `2026-08-05` | [canonical emptiness freeze-ritual（2026-08-05，提交 5f1b974）](<../.artifacts/emptiness_ritual_20260805/NOTES.md>)<br>02 号裁决文书挂账 5 落地：把 owner 2026-08-05「空地当时的定义就是什么都不能有」 写进 rules/canonicalrules.json。只写定义，不含挂账 1 的认证链实现修复。 | `rules-semantics` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-FLOW-ACCOUNT-20260805-9B415D409F` | `2026-08-05` | [band22 静态流量账（2026-08-05）](<../.artifacts/band22_flow_account_20260805/REPORT.md>)<br>logistics-constants.ts:11（2 秒/格）+ entity-definition.ts:1416-1423（1 槽×容量 1） + runtime-slot-access.ts:1075（每周期 1 件）。管道 = 120 件/分钟。 | `upper-bound` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-HEADLESS-SIM-20260805-B287B4FBCC` | `2026-08-05` | [band22 无头仿真 harness — 源码存档与复现方式](<../.artifacts/band22_headless_sim_20260805/harness/README.md>)<br>这四个文件是本次调查写的 harness 源码存档（只读副本）。运行副本在 /home/zhuran24/upstream/IndustrialPlanner-simrun（上游 IndustrialPlanner 的 v3 分支本地克隆， HEAD 7b946c16），路径一一对应： | `upper-bound` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-FAITHFUL-SIM-20260805-8A9863F99B` | `2026-08-05` | [band22 忠实化蓝图 · IndustrialPlanner v3 无头仿真判读](<../.artifacts/band22_faithful_sim_20260805/FAITHFUL_SIM_REPORT.md>)<br>日期：2026-08-05 · 上游工作副本：/home/zhuran24/upstream/IndustrialPlanner-simrun（v3 分支，HEAD 7b946c16） 前置：映射席 MAPPINGREPORT.md + faithfulmapping.json（同目录）· 首跑 .artifacts… | `upper-bound`, `industrial-delivery` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-STRICT-HOLE-PROBE-20260805-B4EF0C65D3` | `2026-08-05` | [band22 严格空地结构探针](<../.artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md>)<br>本机可选的 52=52 槽账、边界禁轨和孔位容量探针。 | `upper-bound` | `historical` | `current_evidence` |
| `DOSSIER-BAND22-REGISTRATION-V2-20260805-16522D6183` | `2026-08-05` | [band22 registration v2 20260805](<../.artifacts/band22_registration_v2_20260805/SURVEY_POINTER.md>)<br>调查报告三段已由 reg-driver-survey 席经消息交付主线（08-05 深夜），全文见主会话转录；本目录为 v2 适配实施批工作区。关键结论：研究面适配 GO、第一阶段零封印；四个 P0/P1 阻塞=loader 形状/11 未激活候选口假阴性/ghost 双索引/不消费已知 binding。 | `upper-bound` | `historical` | `unreviewed` |
| `DOSSIER-BAND22-STRICT-REDESIGN-PACK-20260805-F8A8392DAF` | `2026-08-05` | [00ASK — 严格空地语义下的 band22 家族见证重设计，目标 (42, 6)](<../.artifacts/band22_strict_redesign_pack_20260805/00_ASK.md>)<br>打包日期 2026-08-05（第二版，v2）。本包自包含：你只会看到本目录内的材料， 不需要访问任何外部仓库、链接或历史对话。凡本文引用的文件都在包内，路径均相对本目录给出。 | `upper-bound` | `historical` | `unreviewed` |
| `DOSSIER-W0-PROBE-HOLE-20260804-11D39E624B` | `2026-08-04` | [边界七族带孔探测终局（2026-08-04）](<../.artifacts/w0_probe_hole_20260804/SUMMARY.md>)<br>strict 读法只会 ≤101），而各自 packing 级上界读数为 129/134。措辞纪律（codex refute 二轮订正）：129/134 是上界非可行 witness——已证命题=「面积账对真实天花板至少虚高 28 格」，不是「真能装 129」。 | `witness-lower-bound` | `historical` | `unreviewed` |
| `DOSSIER-W0-FIXRERUN-20260804-7239554A2D` | `2026-08-04` | [Pricing-bound experiment deliverable](<../.artifacts/w0_fixrerun_20260804/pricing_exp_run/README.md>)<br>This directory is research-only. It does not write to a proof registry or claim a formal certificate. | `witness-lower-bound` | `historical` | `unreviewed` |
| `DOSSIER-W0-CONSULT-PACKS-20260804-D95CAAE8A6` | `2026-08-04` | [11runnable · 解包即可运行的探测闭包](<../.artifacts/w0_consult_packs_20260804/pricing_exp/11_runnable/README.md>)<br>08areaprobe.py（包根那份）是运行时字节的逐字副本，它顶部的 SNAP 常量指向发件机上的一个临时快照目录， 所以那一份复制出去是跑不起来的。本目录是同一份代码的可运行版：唯一的改动是把 SNAP 换成包内相对路径 （Path(file).resolve().parents[1]），其余逐字节相同（MAN… | `witness-lower-bound` | `historical` | `unreviewed` |
| `DOSSIER-PRUNE-V2-20260803-A4F09E4468` | `2026-08-03` | [剪枝 P4 设计稿 v0：定点大修 + 无时态层](<../.artifacts/prune_v2_20260803/design_p4_compaction_timeless_layer.md>)<br>剪枝 v2 只保事实正确（引用不死、结论不过时、承诺不落空），不管结构最优——增量订正的局部最优叠加成地层沉积（标本：M5 卡 = 07-12 正文 + 08-03 订正 + 08-05 终局，三层）。文档里满地日期本质是「没人会更新这句话」的保险；剪枝体检就位后这份保险可以撤，但撤保险的操作（压实+去时化）系统里还… | `other` | `historical` | `unreviewed` |
| `DOSSIER-W0-METHOD-RFP-20260803-1CBCC9501E` | `2026-08-03` | [任务：从零设计一套下界见证构造方法](<../.artifacts/w0_method_rfp_20260803/00_ASK.md>)<br>请从头设计：如何构造出规格书 §1 的那张完整合法布局（含 6×7 空矩形）并通过六谓词 checker。不要求你沿用或避开任何已有路线；死亡名单里的三条路除外——它们是被 证死的，除非你能指出判死论证本身的错误，或指出它被外推得比证据宽（两种都是 有效反驳，请直说是哪一种）。 | `witness-lower-bound` | `historical` | `unreviewed` |
| `DOSSIER-W0-FRONT-AWARE-20260803-1040F8BE76` | `2026-08-03` | [W0 G1 修复批（三席审查后主会话裁决；2026-08-03）](<../.artifacts/w0_front_aware_20260803/fix_batch_brief.md>)<br>背景：G1 批三席审查终局 = codex 对抗席 BLOCK（4 阻塞）、opus 章程席/质量席 PASSWITHNOTES。 完整审查原文：/tmp/claude-1000/-home-zhuran24-zmd-pj/8f5c01e7-682b-43f6-a633-2c4886554c21/tasks/waj0… | `witness-lower-bound` | `historical` | `unreviewed` |
| `DOSSIER-M5-REVALIDATION-20260803-40F267675F` | `2026-08-03` | [M5 存在性复验(现行池 f05b1291) — 2026-08-03 深夜](<../.artifacts/m5_revalidation_20260803/NOTES.md>)<br>一直跑，不设时限；停机条件 = 左线程真的需要机器资源时，届时停掉按「枚举 censored@N 小时」入账（三大发现已在案，无损科学结论）。此前我建议的 24h 复查点作废。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-H20-ROW-POWER-ORACLE-20260803-28FC39F69B` | `2026-08-03` | [H20 row-power 微型判定器结果](<../.artifacts/h20_row_power_oracle_20260803/RESULT.md>)<br>性质：research-only 执行记录 截止日期：2026-08-03 状态：H20ROWPOWERUNSATBOTHR1INTERPRETATIONS 冻结输入：Git 3b4e859a0ffe080edd88953e2ad24811b3ecdeb7；16 号文书 SHA-256 b3980eccdc62961… | `other` | `historical` | `unreviewed` |
| `DOSSIER-AB16-ARMS-20260802-DC229C4539` | `2026-08-02` | [AB16 十六臂正式实验收据](<../.artifacts/ab16_arms_20260802/EVAL.md>)<br>本机可选的 16-arm frozen-run EVAL；16/16 budget-censored，generated/compiled/applied 均为 0/0/0。 | `cut-framework`, `separation-telemetry`, `solver-experiment` | `historical` | `current_evidence` |
| `DOSSIER-MERGE-CODEX-20260801-E0761ADC63` | `2026-08-01` | merge codex 20260801<br><code>.artifacts/merge_codex_20260801</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-AB16-SLIMDOWN-20260801-DFA55C71DB` | `2026-08-01` | [AB16 减法批结果](<../.artifacts/ab16_slimdown_20260801/RESULT.md>)<br>日期：2026-08-01 | `other` | `historical` | `unreviewed` |
| `DOSSIER-TRACK-B-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-2026-2C7C3FCD74` | `2026-07-27` | SMM4 fresh-authority local artifact root<br><code>.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727</code><br>External authorization root named by the tracked authority report; intentionally optional and absent from some checkouts. | `formal-verification`, `upper-bound` | `historical` | `current_evidence` |
| `DOSSIER-PROOF-SCOUT-20260718-7C6AD03F03` | `2026-07-18` | proof scout 20260718<br><code>.artifacts/proof_scout_20260718</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-2B25E2B21B` | `2026-07-18` | [front offset 本地复验收据](<../.artifacts/front_offset_incident_20260718/history.json>)<br>事故修复批的本机可选日志与结构化收据。 | `rules-semantics` | `historical` | `historical` |
| `DOSSIER-BATCH4-20260718-37902EF1B5` | `2026-07-18` | batch4 20260718<br><code>.artifacts/batch4_20260718</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-WITNESS-20260717-1D5FD48183` | `2026-07-17` | witness 20260717<br><code>.artifacts/witness_20260717</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `witness-lower-bound` | `historical` | `unreviewed` |
| `DOSSIER-DOC-SWEEP-20260717-54167D9495` | `2026-07-17` | doc sweep 20260717<br><code>.artifacts/doc_sweep_20260717</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-RAB-DRILL-20260716-132E17F171` | `2026-07-16` | rab drill 20260716<br><code>.artifacts/rab_drill_20260716</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-FC-LIFT-AB-20260716-5FD5604614` | `2026-07-16` | fc lift ab 20260716<br><code>.artifacts/fc_lift_ab_20260716</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-BATCH-C-LEFTOVERS-20260714-EAC2289AC0` | `2026-07-14` | batch c leftovers 20260714<br><code>.artifacts/batch_c_leftovers_20260714</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-PHASE3B-AI-ACCEL-20260429-4CCE6170E3` | `2026-04-29` | phase3b ai accel 20260429<br><code>.artifacts/phase3b_ai_accel_20260429</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-V46-VALIDATION-100519A7C4` | `未标日期` | v46 validation<br><code>.artifacts/v46_validation</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-CLEANROOM-R3-ADVERSARIAL-A6B46333B2` | `未标日期` | [R3 certified 候选证书对抗审查 verdict](<../.artifacts/cleanroom_r3_adversarial/verdict.md>)<br>固定一根杆 q，令 Sq 是被分配给它的制造机集合。对每台 F∈Sq，840 条局部不等式给出 | `other` | `historical` | `unreviewed` |
| `DOSSIER-PHASE3B-ACCEL-TUNING-64039CA2F2` | `未标日期` | phase3b accel tuning<br><code>.artifacts/phase3b_accel_tuning</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-V28-GPT-REVIEW-93871F1F70` | `未标日期` | [Phase 1.2 spike close 严格闭关审查 — v28 外部审查结果](<../.artifacts/v28_gpt_review/b1/REVIEW.md>)<br>审查对象: phase12spikereviewv28.zip | `solver-experiment` | `historical` | `unreviewed` |
| `DOSSIER-LAYER2-GATES-EC926F69A7` | `未标日期` | layer2 gates<br><code>.artifacts/layer2_gates</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-CODEX-TAKEOVER-3784FD3D07` | `未标日期` | codex takeover<br><code>.artifacts/codex_takeover</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |
| `DOSSIER-ADAPT-BATCH-GATES-EC7F30EDA7` | `未标日期` | adapt batch gates<br><code>.artifacts/adapt_batch_gates</code><br>本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。 | `other` | `historical` | `unreviewed` |

## Claim 详情

<a id="claim-24-lever-framework-exhausted-superseded"></a>

### “24 lever 全 dead、范式已穷尽”的全称判断已撤回

- **Claim ID：** `CLAIM-24-LEVER-FRAMEWORK-EXHAUSTED-SUPERSEDED`
- **状态：** `superseded`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

历史 lever 汇总曾把多个阶段和 cut 路线的失败压缩成“24 lever 全 dead、范式调查已穷尽”；front offset 重判确认其中若干承重 verdict 依赖污染语义，因此该全称判断不再是可复用结论。

- **适用范围：** historical-paradigm-search；lever-inventory；pre-front-rejudgment

- **成立前提：** 旧汇总混合了 front-dependent 与 front-independent 证据

- **直接后果：** 不得把旧汇总作为停止所有相邻研究路线的 authority

- **明确不推出：** 每个 lever 都重新变为可行；所有局部失败 verdict 都被推翻

- **权威源：** docs/research/paradigm_search_review_v12_with_code_20260520/02_LEVER_HISTORY_24_DEAD.md；docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md

- **条件处置：** `scope_shifted`
- **操作效果：** scope_boundary；experiment_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** incident_review；adversarial_review

- **有效性事件：** `route_retirement`
- **受影响层：** experiment_design；proof_argument；research_strategy
- **判定依据：** incident_replay；evidence_gap
- **复用策略：** `historical_only`
- **修复状态：** `pending`
- **时间作用域：** `design_version`
- **有效性注：** 撤回的是跨 lever 的全称归纳；单项 verdict 需要按 revision 与证据逐条处理。

- **证据：** [docs/research/paradigm_search_review_v12_with_code_20260520/02_LEVER_HISTORY_24_DEAD.md](<research/paradigm_search_review_v12_with_code_20260520/02_LEVER_HISTORY_24_DEAD.md>)〔historical universal exhaustion statement〕；[docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md](<research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md>)〔withdrawal and itemized validity boundary〕

<a id="claim-ab16-campaign-closeout-no-attributable-cut-result"></a>

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

<a id="claim-ab16-no-scientific-cut-result"></a>

### AB16 当前只形成实验边界，未形成可归因的 cut 科学结论

- **Claim ID：** `CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT`
- **状态：** `superseded`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-14`

AB16 tracked 合同与当前运行记录只证明实验链和 authority 边界被建立；历史 38 roots、约 26.5 小时与 0/16 organic arms 的零激活不能归因于 cut 本身，也不授权 B6 promotion、production attach 或“这些 cuts 无效”的科学结论。

- **适用范围：** noncert-cuts；ab16；experimental-evidence

- **成立前提：** 按 AB16 authority contract 区分运行完整性、暴露与科学因果；organic arms 未取得可归因的有效激活证据

- **直接后果：** 后续实验必须先设计能区分 cap、候选暴露与 cut 效果的对照；当前材料只能登记为 inconclusive experiment boundary

- **明确不推出：** cut framework 没有价值；通用 CP-SAT 传播能够替代这些 cuts；B6 永久取消；零激活证明对应不等式无效

- **依赖 claim：** CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS

- **权威源：** docs/research/noncert_cuts_ab16_20260724/README.md；docs/research/noncert_cuts_ab16_20260724/03_execution_record.md
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

- **有效性事件：** `scope_correction`
- **受影响层：** experiment_design；documentation
- **判定依据：** controlled_experiment；evidence_gap
- **复用策略：** `historical_only`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** 该记录停在收官前的历史统计口径；2026-08-03 的完整 21-attempt / 16-credible closeout 由 successor 单独承载。

- **证据：** [docs/research/noncert_cuts_ab16_20260724/README.md](<research/noncert_cuts_ab16_20260724/README.md>)〔AB16 authority and experiment boundary〕；[docs/research/noncert_cuts_ab16_20260724/03_execution_record.md](<research/noncert_cuts_ab16_20260724/03_execution_record.md>)〔tracked execution record〕；[.artifacts/ab16_arms_20260802/EVAL.md](<../.artifacts/ab16_arms_20260802/EVAL.md>)〔frozen 16-arm generated/compiled/applied exposure evaluation〕（工作区可选工件）

<a id="claim-active-scope-single-base"></a>

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

<a id="claim-admission-port-omission-scope-restriction"></a>

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

<a id="claim-attach-spikes-engineering-not-cut-efficacy"></a>

### attach spikes 只证明工程接线，不证明 cut 科学效力

- **Claim ID：** `CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

P1.3A sizing 与 power-on spikes 证明增量 attach 形态、真实 step-8 约束写入和约 10K synthetic redundant F5 负载下的工程开销可接受；实验输入是合成且数学冗余的 cut，没有生产 pool 演化或有机分离。因此这些 GO 不能推出 cut 改善收敛、扩大科学分离能力、完成 P1.3 或授权 B6/production attach。

- **适用范围：** cut-framework；attach-spike；engineering-evidence

- **成立前提：** sizing 与 power-on 的验收对象是接线形态和 overhead；synthetic F5 在数学上冗余；production promotion 需要独立 owner decision 和真实 efficacy evidence

- **直接后果：** 工程可行性与科学效力分开登记；后续 efficacy 实验必须有有机触发与识别性 baseline；历史 GO 不得当成 production authority

- **明确不推出：** attach 一定没有性能价值；synthetic 测试无工程意义；cut framework 永远不能 promotion

- **权威源：** docs/research/p1_3a_attach_sizing_spike_20260708/verdict.md；docs/research/p1_3a_attach_power_on_spike_20260710/02_spike_evidence.md；docs/research/p1_3a_attach_power_on_spike_20260710/03_production_integration_checklist.md

- **条件处置：** `discharged`
- **操作效果：** experiment_boundary；scope_boundary
- **一般性：** `research_process`
- **solver 关系：** `experimental_cut`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review
- **分类注：** GO 只落在工程问题，科学与 authority 问题保持未决。

- **目标阶段：** `model_build`
- **候选来源：** `supplied_candidate`
- **选择方式：** cut_registry_replay
- **验证方式：** independent_validator；terminal_replay
- **完备性：** `not_applicable`
- **消费方式：** diagnostic_only
- **基线比较：** `controlled`
- **分离注：** attach-off 对照只识别工程 overhead，不识别 cut efficacy。

- **证据：** [docs/research/p1_3a_attach_sizing_spike_20260708/verdict.md](<research/p1_3a_attach_sizing_spike_20260708/verdict.md>)〔incremental attach engineering GO and explicit non-convergence boundary〕；[docs/research/p1_3a_attach_power_on_spike_20260710/02_spike_evidence.md](<research/p1_3a_attach_power_on_spike_20260710/02_spike_evidence.md>)〔10K synthetic redundant-F5 power-on evidence and validity boundary〕；[docs/research/p1_3a_attach_power_on_spike_20260710/03_production_integration_checklist.md](<research/p1_3a_attach_power_on_spike_20260710/03_production_integration_checklist.md>)〔owner promotion and production checklist boundary〕

<a id="claim-b1-ceiling-exact-nine-poles"></a>

### B1 ceiling survivor 若存在则恰用九根电杆

- **Claim ID：** `CLAIM-B1-CEILING-EXACT-NINE-POLES`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

对 34×35 或 35×34 ceiling rectangle，B1-QMH 的 actual-P 面积账左端至少为 1318+4(P−9)，而 body/access 总预算为 1320。结合 P≥9，可得任何可行 ceiling survivor 都满足 P=9；P≥10 时左端至少 1322，立即矛盾。

- **适用范围：** b1-conditional-halo；34x35；35x34；selected-poles

- **成立前提：** CLAIM-B1-QMH-REFINED-MEMBRANE-INEQUALITY 成立；实际电杆占地按 4P 计入且 P≥9；候选尺寸为 34×35 或其转置

- **直接后果：** ceiling diagnostic 可以把 actual pole count 固定为九；conditional-halo 的全选杆求和仍不能改成“任意九杆”求和

- **明确不推出：** 34×35 或 35×34 存在可行布局；九根电杆的位置或覆盖关系唯一；conditional halo 在已跑 512-case corpus 中产生增量 prune

- **依赖 claim：** CLAIM-B1-QMH-REFINED-MEMBRANE-INEQUALITY；CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE

- **权威源：** docs/research/b1_conditional_halo_20260722/01_necessity_proof.md；docs/research/b1_conditional_halo_20260722/README.md

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；constraint_strengthening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof；adversarial_review
- **分类注：** 这是 ceiling 尺寸上的派生诊断，不把九杆量词偷换进 B1-CH 本体。

- **推导角色：** `composite_theorem`
- **数学推导族：** area_accounting；conditional_halo；integer_rounding
- **验证方式：** paper_derivation；independent_recomputation；adversarial_review

- **证据：** [docs/research/b1_conditional_halo_20260722/01_necessity_proof.md](<research/b1_conditional_halo_20260722/01_necessity_proof.md>)〔actual-pole ledger and exact-nine ceiling derivation〕；[docs/research/b1_conditional_halo_20260722/README.md](<research/b1_conditional_halo_20260722/README.md>)〔independent diagnostic accounting and no-prune boundary〕

<a id="claim-b1-conditional-halo-capacity-6650"></a>

### B1-CH 对全部已选电杆给出 clipped halo 容量下界 6650

- **Claim ID：** `CLAIM-B1-CONDITIONAL-HALO-CAPACITY-6650`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

对任一 body-empty rectangle R，把 14-orbit doubled halo stencil 平移到每根已选电杆、先裁剪到 70×70 网格再删去 R，则全部已选电杆的 clipped capacity 满足 Σ_q C2_q(R)≥6650（等价于 undoubled Σ_q C_q(R)≥3325）。量词是全部已选电杆，不可替换为任意九根。

- **适用范围：** b1-conditional-halo；strict-empty-rectangle；selected-poles

- **成立前提：** 219 个 mandatory powered manufacturing bodies 的总面积为 3325；840 个 eligible body/pole relative placements 均满足 local halo inequality；每个 powered facility 指派给一根实际覆盖它的已选电杆

- **直接后果：** B1 encoder 可以加入 all-selected-poles conditional halo 必要条件；量词必须覆盖全部已选电杆；不能静默替换为任意九根电杆

- **明确不推出：** 任意挑选九根电杆也满足同一求和不等式；512 对 control/treatment corpus 中出现增量 prune；产生更小 research upper bound、witness 或 production CERTIFIED 结论

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT

- **权威源：** docs/research/b1_conditional_halo_20260722/01_necessity_proof.md；docs/research/b1_conditional_halo_20260722/02_adversarial_verdict.md；docs/research/b1_conditional_halo_20260722/README.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening
- **一般性：** `parameterized_family`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof
- **分类注：** 数学必要条件已通过；预声明 512-case diagnostic 没有观察到额外分离。

- **推导角色：** `atomic_lemma`
- **数学推导族：** conditional_halo；power_coverage
- **验证方式：** exact_enumeration；paper_derivation；independent_recomputation；adversarial_review

- **证据：** [docs/research/b1_conditional_halo_20260722/01_necessity_proof.md](<research/b1_conditional_halo_20260722/01_necessity_proof.md>)〔all-selected-poles necessity proof and actual-pole ledger〕；[docs/research/b1_conditional_halo_20260722/02_adversarial_verdict.md](<research/b1_conditional_halo_20260722/02_adversarial_verdict.md>)〔geometry-only adversarial admission〕；[docs/research/b1_conditional_halo_20260722/README.md](<research/b1_conditional_halo_20260722/README.md>)〔closed diagnostic boundary and zero incremental-prune record〕

<a id="claim-b1-qmh-refined-membrane-inequality"></a>

### B1-QMH 用边界 Q 交叠与端点项细化 ordinary membrane

- **Claim ID：** `CLAIM-B1-QMH-REFINED-MEMBRANE-INEQUALITY`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

对固定 47 种 boundary pattern δ 与 body-empty rectangle R，令 A=wh、S=w+h、q=|R∩Qδ|，e 为 tangential endpoint partial contacts 数，则所有可行布局必须满足 A+ceil((580-S+floor(q/2)+e)/4)≤1320。该式通过在膜账内部扣除 q/e 改进量避免重复计数。

- **适用范围：** b1-qmh；boundary-patterns；strict-empty-rectangle

- **成立前提：** 46 个 boundary raw ports 与六个 core raw outputs 的 52=52 provider identity 使全部 boundary Q ports active；manufacturing partial contacts 与 boundary partial contacts 共享八个 directed endpoint positions；CLAIM-BODY-ACCESS-BUDGET-1320 与每个外部 access cell 至多四个 incidences 成立

- **直接后果：** 对每个实际 boundary pattern 与 rectangle placement 提供一条必要条件；完整 pattern-placement 扫描相对 inherited membrane baseline 排除 138 个 assignments

- **明确不推出：** 把 (46-q) 作为与 membrane access-cell lower bound 不相交的额外格池相加；本轮改进 research upper ledger；surviving selector assignment 是真实布局

- **依赖 claim：** CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED；CLAIM-BODY-ACCESS-BUDGET-1320；CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48

- **权威源：** docs/research/b1_q_membrane_halo_20260722/01_necessity_proof.md；docs/research/b1_q_membrane_halo_20260722/02_adversarial_verdict.md；docs/research/b1_q_membrane_halo_20260722/README.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；candidate_pruning
- **一般性：** `parameterized_family`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** ordinary_membrane；endpoint_budget；slot_saturation
- **验证方式：** paper_derivation；exact_enumeration；adversarial_review

- **证据：** [docs/research/b1_q_membrane_halo_20260722/01_necessity_proof.md](<research/b1_q_membrane_halo_20260722/01_necessity_proof.md>)〔paper derivation and double-counting exclusion〕；[docs/research/b1_q_membrane_halo_20260722/02_adversarial_verdict.md](<research/b1_q_membrane_halo_20260722/02_adversarial_verdict.md>)〔adversarial admission of the necessary condition〕；[docs/research/b1_q_membrane_halo_20260722/README.md](<research/b1_q_membrane_halo_20260722/README.md>)〔complete scan and translation-gate outcome〕

<a id="claim-band22-v0a-strict-hole-incompatible"></a>

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

<a id="claim-binding-slot-single-commodity-scope"></a>

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

<a id="claim-body-access-budget-1320"></a>

### body-empty rectangle 与外部 access cells 共用 1320 格预算

- **Claim ID：** `CLAIM-BODY-ACCESS-BUDGET-1320`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

当前 70×70 冻结实例中，mandatory bodies 占 3544 格且至少九根 2×2 电杆占 36 格。对任一 body-cell-empty rectangle R 和位于 R 外的 distinct body-free access cells 集 Z，必要地有 |R|+|Z|≤4900-3544-36=1320；额外设施、电杆或空闲约束只会进一步收紧该预算。

- **适用范围：** strict-empty-rectangle；body-access-budget；current-frozen-instance

- **成立前提：** 70×70 单基地网格；mandatory body area 为 3544；CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE 成立；R 与 counted external access cells 均不占 mandatory/pole body cells

- **直接后果：** 所有 membrane/access-cell upper-bound 链可以使用 RHS 1320；若某尺寸与必要 external access cells 的和超过 1320，则该尺寸被排除

- **明确不推出：** 恰有九根电杆；全部剩余 1320 格都可被 routing 或空矩形使用；存在达到该预算等号的布局

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT；CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE

- **权威源：** docs/research/r3_upper_bound_pb_20260722/README.md；docs/research/r4_response_review_20260723/02_necessity_proof.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof

- **推导角色：** `atomic_lemma`
- **数学推导族：** area_accounting；empty_rectangle_geometry；power_coverage
- **验证方式：** paper_derivation；source_recomputation

- **证据：** [docs/research/r3_upper_bound_pb_20260722/README.md](<research/r3_upper_bound_pb_20260722/README.md>)〔R3 body, pole and access-cell budget derivation〕；[docs/research/r4_response_review_20260723/02_necessity_proof.md](<research/r4_response_review_20260723/02_necessity_proof.md>)〔R4 independent reuse of the 1320 ledger〕

<a id="claim-boundary-generic-output-slots-saturated"></a>

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

<a id="claim-boundary-loader-excluded-frozen-instance"></a>

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

<a id="claim-budget-exhaustion-is-unknown-not-fixed-point"></a>

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

<a id="claim-certified-existence-open"></a>

### 现行语义下 whole-layout 认证级存在性仍为 OPEN

- **Claim ID：** `CLAIM-CERTIFIED-EXISTENCE-OPEN`
- **状态：** `open`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_ledger_state`
- **更新时间：** `2026-08-11`

当前没有被账本接受的完整可行布局或 whole-layout witness。现行池上的 master incumbent 与被 owner 截停的 binding↔routing 枚举都不足以建立认证级存在性，因此 lower ledger 仍为空。

- **适用范围：** six-predicate；whole-layout-witness；current-candidate-pool

- **成立前提：** witness 必须经过当前 HEAD/input-pinned 验收链；UNKNOWN、超时与 owner 截停没有可行或不可行语义

- **直接后果：** 不得把 master feasible 写成整例 feasible；下界继续记为 L=absent

- **明确不推出：** 全问题不可行；不存在可行布局；上界 U 已可达

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT；CLAIM-SIX-PREDICATE-RESEARCH-LEDGER

- **权威源：** data/solutions/exact_full_scale_status.json；docs/research/witness_constructor_20260717/07_routing_aware/README.md

- **证据：** [data/solutions/exact_full_scale_status.json](<../data/solutions/exact_full_scale_status.json>)〔checked-in durable exact status〕；[docs/research/witness_constructor_20260717/07_routing_aware/README.md](<research/witness_constructor_20260717/07_routing_aware/README.md>)〔latest tracked witness-construction line〕

<a id="claim-certified-theorem-scope"></a>

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

<a id="claim-column-generation-phase2-scale-route-no-go"></a>

### Column Generation Phase 2 的登记设计未跨过规模与重构门槛

- **Claim ID：** `CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO`
- **状态：** `historical`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

Column Generation Phase 2 总判为 NO-GO：20 与 40 instance 的 Ryan–Foster 分支均无 speedup，80 instance 同时出现 integer reconstruction failure 与无 speedup；160 和 266 instance 在第 0 轮 RMP 即 INFEASIBLE，并伴随 sound check、integer reconstruction 与 singleton-column 退化，其中 266 instance 的 multi-facility columns 仅 24.43%、singleton columns 为 75.57%。5-instance mini ramp 的局部 GO 不足以恢复该生产规模设计。

- **适用范围：** column-generation；phase2-share-cache-rf-routing-boundary；5-to-266-instance-ramps

- **成立前提：** 使用登记的 Phase 2 pricing、bootstrap、RF branching 与 reconstruction 实现；route verdict 绑定该设计版本和 ramp gates

- **直接后果：** 该 Phase 2 设计不得作为 production-scale inner replacement 继续推进；后续重启必须先解决 RMP 初始可行性、sound reconstruction 与大规模 column composition

- **明确不推出：** column generation 作为一般优化范式无效；5-instance mini exactness 结果失效；任何重新设计的 pricing、bootstrap 或 branching 都会失败；现有 production solver 已因此被证明最优

- **权威源：** docs/research/cand_c_column_generation_phase2_20260521/README.md；docs/research/cand_c_column_generation_phase2_20260521/phase2_results.json

- **条件处置：** `scope_shifted`
- **操作效果：** experiment_boundary；discovery_method；scope_boundary
- **一般性：** `model_domain`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **有效性事件：** `route_retirement`
- **受影响层：** model_encoding；experiment_design；solver_runtime；research_strategy
- **判定依据：** controlled_experiment；independent_recomputation
- **复用策略：** `method_only`
- **修复状态：** `pending`
- **时间作用域：** `design_version`
- **有效性注：** 保留 ramp gate、reconstruction 与 column-composition 诊断方法，不保留该设计的规模可行性判断。

- **证据：** [docs/research/cand_c_column_generation_phase2_20260521/README.md](<research/cand_c_column_generation_phase2_20260521/README.md>)〔Phase 2 design and gate interpretation〕；[docs/research/cand_c_column_generation_phase2_20260521/phase2_results.json](<research/cand_c_column_generation_phase2_20260521/phase2_results.json>)〔ramp-by-ramp verdict failures and resource telemetry〕

<a id="claim-connectivity-quantifier-per-commodity-source-sink"></a>

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

<a id="claim-cut-framework-production-status"></a>

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

<a id="claim-destination-front-exclusivity-terminal-sensitive"></a>

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

<a id="claim-discovery-and-validation-separate-obligations"></a>

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

<a id="claim-durable-certified-result-absent"></a>

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

<a id="claim-empty-rectangle-min-side-admissibility-six"></a>

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

<a id="claim-empty-rectangle-routing-allowed-superseded"></a>

### 空矩形只禁设施、允许物流组件穿入的宽松解释已被替代

- **Claim ID：** `CLAIM-EMPTY-RECTANGLE-ROUTING-ALLOWED-SUPERSEDED`
- **状态：** `superseded`
- **权威层：** `descriptive`
- **权威依据：** `descriptive`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

裁决前书面规格没有定义“空”的 occupant 范围，代码静默采用只排除 facility、允许 routing component 进入 ghost rectangle 的宽松解释；owner 随后明确“空地就是什么都不能有”，因此旧解释不再有效。

- **适用范围：** empty-rectangle；historical-semantics；pre-2026-08-05

- **成立前提：** 描述的是裁决前实现选择而非规则 authority

- **直接后果：** 旧解释只能用于判断历史结果的方向安全性

- **明确不推出：** 宽松语义下所有负结果失效；旧正向见证在 strict 语义下仍成立

- **权威源：** docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md
- **关联决定：** DECISION-EMPTY-RECTANGLE-STRICT-20260805

- **条件处置：** `scope_shifted`
- **操作效果：** semantic_partition；scope_boundary
- **一般性：** `game_semantics`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** owner_adjudication；systematic_rules_audit

- **有效性事件：** `semantic_replacement`
- **受影响层：** canonical_semantics；model_encoding；documentation
- **判定依据：** owner_adjudication；incident_replay
- **复用策略：** `historical_only`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`

- **证据：** [docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md](<research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md>)〔owner adjudication and pre-adjudication source audit〕

<a id="claim-empty-rectangle-strict"></a>

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

<a id="claim-f7-facility-mask-validator-bug-repaired"></a>

### F7 validator 漏排 facility cells 的误杀缺陷已修复并复核

- **Claim ID：** `CLAIM-F7-FACILITY-MASK-VALIDATOR-BUG-REPAIRED`
- **状态：** `historical`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

F7 Round 1 发现 replay validator 构造 free_cells 时未显式扣除目标 facility cells，会在设施内部找到伪 pole anchor 并把合法 cut 误判为 unsound；Round 2 验证 validator 与 oracle 均采用 `grid - ghost - exterior - facility` 的修正 mask，并确认该修复跨 caller 一致。

- **适用范围：** f7；power-hitting-set；validator-replay

- **成立前提：** 结论只覆盖登记的 Round 1 blocker 与 Round 2 修复复核

- **直接后果：** replay validator 必须把目标 facility cells 纳入 blocked mask；单个 blocker 修复后仍需独立审查其余 finding

- **明确不推出：** F7 自动获得 production authority；外部复核提出的每个后续 finding 都正确；validator 修复证明 cut family 完备

- **权威源：** docs/research/p1_2b_f7_power_hitting_set_gemini_round1_20260525/gemini_response.md；docs/research/p1_2b_f7_power_hitting_set_gemini_round2_20260525/verdict.md

- **条件处置：** `method_only`
- **操作效果：** experiment_boundary；discovery_method
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** adversarial_review；incident_review

- **有效性事件：** `implementation_invalidation`
- **受影响层：** validator；model_encoding
- **判定依据：** incident_replay；differential_test
- **复用策略：** `historical_only`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** 这是局部 validator 修复记录，不是 cut family 的完整 soundness 或 completeness 证明。

- **证据：** [docs/research/p1_2b_f7_power_hitting_set_gemini_round1_20260525/gemini_response.md](<research/p1_2b_f7_power_hitting_set_gemini_round1_20260525/gemini_response.md>)〔Round 1 blocker report〕；[docs/research/p1_2b_f7_power_hitting_set_gemini_round2_20260525/verdict.md](<research/p1_2b_f7_power_hitting_set_gemini_round2_20260525/verdict.md>)〔local adjudication and repair verification〕

<a id="claim-forward-completeness-relative-to-declared-fragment"></a>

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

<a id="claim-front-offset-double-step-semantics-superseded"></a>

### stored port 之后再沿方向前移一格的旧 front 解释已被替代

- **Claim ID：** `CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED`
- **状态：** `superseded`
- **权威层：** `descriptive`
- **权威依据：** `descriptive`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

事故前实现把 stored port 坐标理解为设施物理口，并在多个 consumer 中再次沿方向前移一格寻找 front/access cell；取证确认 stored port 坐标本身已经是外部 front/access cell，因此这套 double-step 解释不是当前语义。

- **适用范围：** historical-results；port-front-semantics；pre-2026-07-18

- **成立前提：** 记录描述的是事故前代码路径，而不是当前 canonical 语义

- **直接后果：** 旧定义只能用于解释事故史，不能用于生成、验证或重放当前结论

- **明确不推出：** 所有事故前结果都必然错误；与 front 坐标无关的数学结果自动失效

- **权威源：** docs/research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md；docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md

- **条件处置：** `scope_shifted`
- **操作效果：** scope_boundary；counterexample
- **一般性：** `model_domain`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** incident_review；adversarial_review
- **分类注：** 这是被事故取证替代的历史解释，不是仍可消费的规则。

- **有效性事件：** `semantic_replacement`
- **受影响层：** canonical_semantics；model_encoding；validator
- **判定依据：** incident_replay；differential_test
- **复用策略：** `historical_only`
- **修复状态：** `revalidated`
- **时间作用域：** `pre_fix_history`

- **证据：** [docs/research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md](<research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md>)〔incident root-cause survey〕；[docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md](<research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md>)〔historical validity rejudgment〕

<a id="claim-front-offset-historical-rejudgment-40"></a>

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

<a id="claim-front-offset-pre-0718-superseded"></a>

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

<a id="claim-generic-cp-sat-separation-impossibility-open"></a>

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

<a id="claim-ihs-singleton-core-compression-phase0-no-go"></a>

### IHS Phase 0 的 singleton core 源没有产生跨迭代压缩

- **Claim ID：** `CLAIM-IHS-SINGLETON-CORE-COMPRESSION-PHASE0-NO-GO`
- **状态：** `historical`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

在 27×15、anchor=(22,28) 的 IHS Phase 0 中，十轮 routing core 全部大小为 1，p50=1、`pct_eq_1=1.0`；离线最小 hitting set 大小 10 与 union 大小 10 相同，compression=1.0。Stage 1 因而判为 NO-GO，Stage 2 不具备进入资格，LBBD 最终保持 UNPROVEN。该 core source 与设计版本没有提供预期的跨 core 共享结构。

- **适用范围：** ihs；27x15-anchor-22-28；routing-core-phase0

- **成立前提：** 只评价登记的十轮 core source、anchor 与 IHS Phase 0 gate；compression 指离线 hitting-set 对 core union 的压缩

- **直接后果：** 不得把该 singleton core 流继续包装成已产生组合压缩的 IHS 路线；若重启 IHS，必须先改变 core 语义、一般化粒度或事件来源

- **明确不推出：** 所有问题上的 IHS 都无效；后续不同 core family 必然仍为 singleton；LBBD 主问题已经被证明不可行；十个 singleton cut 本身不 sound

- **权威源：** docs/research/lever25_ihs_phase0_20260520/README.md；docs/research/lever25_ihs_phase0_20260520/phase0_results.json

- **条件处置：** `scope_shifted`
- **操作效果：** experiment_boundary；discovery_method；scope_boundary
- **一般性：** `frozen_instance`
- **solver 关系：** `experimental_cut`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **目标阶段：** `search_loop`
- **候选来源：** `solver_events`
- **选择方式：** raw_event_separation
- **验证方式：** direct_arithmetic；terminal_replay
- **完备性：** `heuristic`
- **消费方式：** diagnostic_only
- **基线比较：** `controlled`
- **分离注：** hitting-set 求解本身成功，但输入 core 彼此不共享 literal，故没有压缩信号。

- **有效性事件：** `route_retirement`
- **受影响层：** experiment_design；research_strategy
- **判定依据：** controlled_experiment；independent_recomputation
- **复用策略：** `method_only`
- **修复状态：** `pending`
- **时间作用域：** `design_version`

- **证据：** [docs/research/lever25_ihs_phase0_20260520/README.md](<research/lever25_ihs_phase0_20260520/README.md>)〔Phase 0 gate design and verdict interpretation〕；[docs/research/lever25_ihs_phase0_20260520/phase0_results.json](<research/lever25_ihs_phase0_20260520/phase0_results.json>)〔ten singleton cores and compression telemetry〕

<a id="claim-lazy-power-instance-pose-cut-route-no-go"></a>

### Lazy Power Completion 的 instance×pose cut 路线在登记锚点触发 NO-GO

- **Claim ID：** `CLAIM-LAZY-POWER-INSTANCE-POSE-CUT-ROUTE-NO-GO`
- **状态：** `historical`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

在 27×15、anchor=(22,28) 的登记 Phase 0 中，跳过显式 coverage 的 master 可在约 80–92 秒内反复得到 OPTIMAL，但首个 layout 的 power completion 为 INFEASIBLE；全布局 220-pose nogood 十轮只把 uncovered 134 降到 133 后停滞，deletion core 虽把 cut 缩到 6 个 instance×pose literals，六轮仍在 134、133、125、133、133、123 间振荡。因此该设计版本以 instance×pose 为粒度的 lazy cut loop 按预设 UNKNOWN_POWER_CUT_STALL 门槛退役。

- **适用范围：** lazy-power-completion；27x15-anchor-22-28；instance-pose-cut-design

- **成立前提：** 使用登记的 Phase 0 master、completion oracle、候选锚点与时间预算；route verdict 只覆盖 instance×pose cut language v1

- **直接后果：** 不得在没有新的几何位置级 cut 语言或传播机制时复活同一 cut loop；master 去除 coverage 后变快仍可作为瓶颈定位与方法设计信号

- **明确不推出：** 该锚点或全局问题 power 不可行；所有 lazy completion 或 Benders 路线都不可行；CP-SAT 原则上无法表达位置级分离；pose-bool master 或几何位置级 cut 也会失败

- **权威源：** docs/research/phase0_lazy_power_completion_20260517/README.md；docs/research/phase0_lazy_power_completion_20260517/probe_phase3_tight_cut_v2.json

- **条件处置：** `scope_shifted`
- **操作效果：** experiment_boundary；discovery_method；scope_boundary
- **一般性：** `frozen_instance`
- **solver 关系：** `experimental_cut`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **目标阶段：** `search_loop`
- **候选来源：** `solver_events`
- **选择方式：** raw_event_separation
- **验证方式：** terminal_replay
- **完备性：** `heuristic`
- **消费方式：** model_constraint；diagnostic_only
- **基线比较：** `controlled`
- **分离注：** completion oracle 能给出当前 layout 的失败事件，但 instance×pose cut 没有把失败一般化到几何位置层。

- **有效性事件：** `route_retirement`
- **受影响层：** model_encoding；experiment_design；research_strategy
- **判定依据：** controlled_experiment；independent_recomputation
- **复用策略：** `method_only`
- **修复状态：** `pending`
- **时间作用域：** `design_version`
- **有效性注：** 可复用的是 master/coverage 瓶颈定位与 cut 粒度教训，不是该路线对全问题的不可行结论。

- **证据：** [docs/research/phase0_lazy_power_completion_20260517/README.md](<research/phase0_lazy_power_completion_20260517/README.md>)〔Phase 0 verdict, cut-loop chronology and abort boundary〕；[docs/research/phase0_lazy_power_completion_20260517/probe_phase3_tight_cut_v2.json](<research/phase0_lazy_power_completion_20260517/probe_phase3_tight_cut_v2.json>)〔six-iteration minimized-core telemetry〕

<a id="claim-lever-verdicts-are-item-and-revision-bounded"></a>

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

<a id="claim-m5-deaths-require-resource-build-and-parameter-separation"></a>

### M5 死亡归因必须分开资源尖峰、build 爆炸与 solve 参数

- **Claim ID：** `CLAIM-M5-DEATHS-REQUIRE-RESOURCE-BUILD-AND-PARAMETER-SEPARATION`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

M5 复判把旧死亡拆成三类：42G 且禁 swap 的运行低于约 60G 出解尖峰，E1 系列由 exploratory port-clearance build 爆炸，默认 solve 参数只带来有限 wall 税。后续归因必须保持资源条款、build 路径和 solve 参数为独立变量。

- **适用范围：** m5；resource-attribution；solver-experiment

- **成立前提：** 使用修订资源条款和单变量比较；区分 build 与 solve 阶段 telemetry

- **直接后果：** 一次死亡不得直接归因给同时变化的参数；campaign 可行性与 wall 优化要分账

- **明确不推出：** 62G 是所有候选的普遍充分预算；build 爆炸已经被 production 修复

- **取代 claim：** CLAIM-M5-DEFAULT-SOLVE-PARAMETERS-PATHOLOGICAL-REFUTED

- **权威源：** docs/research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md

- **条件处置：** `scope_shifted`
- **操作效果：** experiment_boundary；discovery_method
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **有效性事件：** `attribution_correction`
- **受影响层：** solver_runtime；experiment_design；model_encoding
- **判定依据：** controlled_experiment；differential_test
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `run_family`

- **证据：** [docs/research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md](<research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md>)〔corrected attribution and campaign replay〕

<a id="claim-m5-default-solve-parameters-pathological-refuted"></a>

### M5“产品默认 solve 参数病态”归因已被受控 A/B 推翻

- **Claim ID：** `CLAIM-M5-DEFAULT-SOLVE-PARAMETERS-PATHOLOGICAL-REFUTED`
- **状态：** `refuted`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

在修订后的 62G 预算下，fixed search、probing3、symmetry3 的单变量与完整默认组合均达到 OPTIMAL；默认组合只增加约 26.4% wall，而没有复现“持续吃内存不出解”的病态，因此旧参数归因不成立。

- **适用范围：** m5；solver-parameters；c1-master

- **成立前提：** 比较使用相同 C1 master 与修订资源条款；每刀只改变声明的参数因素

- **直接后果：** 不得再用参数病态解释旧 smoke 死亡；参数调优属于性能机会而非正确性阻塞

- **明确不推出：** 默认参数在所有实例上最优；旧运行没有资源或 build 问题

- **权威源：** docs/research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md

- **条件处置：** `refuted`
- **操作效果：** counterexample；experiment_boundary
- **一般性：** `frozen_instance`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **有效性事件：** `refutation`
- **受影响层：** solver_runtime；experiment_design
- **判定依据：** controlled_experiment；differential_test
- **复用策略：** `do_not_reuse`
- **修复状态：** `not_applicable`
- **时间作用域：** `run_family`

- **证据：** [docs/research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md](<research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md>)〔controlled single-variable and combined A/B results〕

<a id="claim-mixed-terminal-tripartition"></a>

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

<a id="claim-mixflow-demix-conclusion-survives-fixture-correction"></a>

### mixflow demix 主对照在忠实 fixture 修正后保持同向

- **Claim ID：** `CLAIM-MIXFLOW-DEMIX-CONCLUSION-SURVIVES-FIXTURE-CORRECTION`
- **状态：** `historical`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

旧与忠实 open_yard fixture 的 ban=ON/ban=OFF 主对照保持同向：ban=ON 阻止混流，ban=OFF 允许混流；fixture 缺陷只推翻 U-01 守卫分叉红利，不能外推成整个 demix 批次失效。

- **适用范围：** mixflow；demix-ban；fixture-correction

- **成立前提：** 结论只覆盖更正文书中的两版 30 秒对照

- **直接后果：** 历史 demix 方向性观察可保留；U-01 红利与主对照必须分账

- **明确不推出：** demix ban 已获 production authority；忠实 fixture 的 TIMEOUT 可以解释为不可行

- **权威源：** .artifacts/mixflow_demix_ban_20260807/CORRECTION_open_yard_fixture_20260807.md

- **条件处置：** `scope_shifted`
- **操作效果：** experiment_boundary；scope_boundary
- **一般性：** `frozen_instance`
- **solver 关系：** `experimental_cut`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **有效性事件：** `experiment_invalidation`
- **受影响层：** model_encoding；experiment_design
- **判定依据：** controlled_experiment；differential_test
- **复用策略：** `historical_only`
- **修复状态：** `revalidated`
- **时间作用域：** `specific_artifact`
- **有效性注：** 修正保留主对照方向，但没有把实验观察提升为 production 结论。

- **证据：** [.artifacts/mixflow_demix_ban_20260807/CORRECTION_open_yard_fixture_20260807.md](<../.artifacts/mixflow_demix_ban_20260807/CORRECTION_open_yard_fixture_20260807.md>)〔two-fixture controlled comparison〕（工作区可选工件）

<a id="claim-mixflow-u01-guard-fork-benefit-refuted"></a>

### U-01“守卫分叉带来可行性红利”的观测已由忠实 fixture 对照推翻

- **Claim ID：** `CLAIM-MIXFLOW-U01-GUARD-FORK-BENEFIT-REFUTED`
- **状态：** `refuted`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

旧 open_yard_8x8 fixture 同时宣称 64 格全自由却把四个端口的设施机身放在院内，使非本商品错误消费端口边；U-01 在该 fixture 上看到的守卫分叉 FEASIBLE 红利，在忠实变体上变为 TIMEOUT，因此该红利观测是装置产物。

- **适用范围：** mixflow；u01；open-yard-fixture

- **成立前提：** 比较只针对该 fixture 与 U-01 红利观测

- **直接后果：** 旧红利不得进入路线选择或性能结论；实验 fixture 必须验证 body cells 与 free yard 一致

- **明确不推出：** demix ban 的主对照结论被推翻；忠实 fixture 已证明守卫分叉无效

- **权威源：** .artifacts/mixflow_demix_ban_20260807/CORRECTION_open_yard_fixture_20260807.md

- **条件处置：** `refuted`
- **操作效果：** counterexample；experiment_boundary
- **一般性：** `frozen_instance`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **有效性事件：** `experiment_invalidation`
- **受影响层：** model_encoding；experiment_design
- **判定依据：** incident_replay；controlled_experiment
- **复用策略：** `do_not_reuse`
- **修复状态：** `not_applicable`
- **时间作用域：** `specific_artifact`

- **证据：** [.artifacts/mixflow_demix_ban_20260807/CORRECTION_open_yard_fixture_20260807.md](<../.artifacts/mixflow_demix_ban_20260807/CORRECTION_open_yard_fixture_20260807.md>)〔fixture correction and controlled rerun〕（工作区可选工件）

<a id="claim-model-stricter-faces-scope-debt"></a>

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

<a id="claim-ordinary-membrane-terminal-bound-s48"></a>

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

<a id="claim-p2-area-accounting-1356"></a>

### P2.0 格位分账给出 A≤1356−4P−R

- **Claim ID：** `CLAIM-P2-AREA-ACCOUNTING-1356`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

70×70 网格的 4900 格可按 mandatory bodies 3544 格、电杆 4P 格、非强制机身 N≥0、路由足迹 R 格、严格空矩形 A 格与其余空闲 S≥0 分账；这些类别两两不交，因此 A≤1356−4P−R−N−S≤1356−4P−R。

- **适用范围：** p2_0；area-accounting；strict-empty-rectangle

- **成立前提：** mandatory bodies 总占地为 3544；每根电杆占 2×2 共四格；设施机身两层实心，route state 不压机身；严格空矩形与设施、电杆及所有物流部件均不相交

- **直接后果：** 任何 P2.0 面积上界只需再提供电杆数和 route footprint 下界即可闭合

- **明确不推出：** 非强制机身 N 或空闲 S 等于零；P≥9、R≥153 或 A≤1167 可在不引用其他引理时直接得到；六谓词研究账本发生变化

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof；adversarial_review

- **推导角色：** `atomic_lemma`
- **数学推导族：** area_accounting；empty_rectangle_geometry
- **验证方式：** paper_derivation；source_recomputation；adversarial_review

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔Theorem 1 step A cell-accounting derivation〕

<a id="claim-p2-area-bound-1167"></a>

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

<a id="claim-p2-buckwheat-sandleaf-mandatory-branch"></a>

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

<a id="claim-p2-five-full-one-half-conditional"></a>

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

<a id="claim-p2-min-side-upper-open"></a>

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

<a id="claim-p2-route-footprint-lower-153"></a>

### P2.0 route footprint 满足 R≥153

- **Claim ID：** `CLAIM-P2-ROUTE-FOOTPRINT-LOWER-153`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

每个网格格位在 ground/elevated 两层上各至多容纳一个 physical route state，因此每格至多两个 state。结合 L≥305，route footprint 满足 R≥ceil(L/2)≥153。该界允许合法垂直双流交叉，因而是无条件双层口径。

- **适用范围：** p2_0；route-footprint；two-layer-routing

- **成立前提：** 每个 (cell,layer) 至多一个 physical route state；当前 routing layer 只有 ground 与 elevated 两层；垂直双流交叉可在一格兑现两个 state，但平行双流不可叠放

- **直接后果：** P2.0 无条件面积链可使用 R≥153；若另行 discharge 单层条件 X=0，才可把该界收紧为 R≥L

- **明确不推出：** 每个 route footprint 格都实际承载两个 state；交叉格数 X 的布局无关上界已经建立；R≥L 是无条件结论

- **依赖 claim：** CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof；adversarial_review

- **推导角色：** `composite_theorem`
- **数学推导族：** route_footprint；crossing_counting；integer_rounding
- **验证方式：** paper_derivation；source_recomputation；authority_admission

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔Theorem 1 step D and OB6 two-layer accounting〕

<a id="claim-p2-route-state-lower-bound-305"></a>

### P2.0 route-state 数至少为 305

- **Claim ID：** `CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

P2.0 scope 内每件被计入的 routed throughput 至少占用一个 physical route state，而每个 state 的容量至多 30 件/分钟。由 routed flow lower bound 9135 得 L≥ceil(9135/30)=305。

- **适用范围：** p2_0；route-state-count；throughput-conservation

- **成立前提：** CLAIM-P2-ROUTED-FLOW-LOWER-9135 成立；每个 active route-required port front exact-one 绑定一个 route state；每个 physical state 的跨商品聚合容量为 30 件/分钟

- **直接后果：** 双层无条件口径下 route footprint R≥153；单层条件口径下 route footprint R≥305

- **明确不推出：** front occurrence 数可以直接逐口相加为 state lower bound；一个 state 只能服务一个 source 与一个 sink；平均路径长度大于一

- **依赖 claim：** CLAIM-P2-ROUTED-FLOW-LOWER-9135

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** throughput_capacity；integer_rounding
- **验证方式：** paper_derivation；source_recomputation；adversarial_review

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔capacity-counting route-state theorem and model-source audit〕

<a id="claim-p2-routed-flow-lower-9135"></a>

### P2.0 进入路由图的聚合流量至少为 9135 件/分钟

- **Claim ID：** `CLAIM-P2-ROUTED-FLOW-LOWER-9135`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

在 P2.0 production_targets、仓库桥排除、稳态无损耗与当前 17 个 operation group 的聚合平衡方程下，聚合活动向量与逐商品聚合吞吐唯一；采用扣除无线终品的钉死口径，进入 route graph 的流量至少为 F_route=9135 件/分钟。

- **适用范围：** p2_0；aggregate-flow；throughput-conservation

- **成立前提：** production_targets 使用当前 valley/qiaoyu 满速目标；中间品必须由路由网络从 producer port 到 consumer port，warehouse bridge 被排除；循环稳态无丢弃或湮灭，聚合商品平衡成立

- **直接后果：** 容量计数可把 9135 作为 route-state lower bound 的分子；P2.0 面积链不必依赖逐路径流唯一或配方图为 DAG

- **明确不推出：** 逐条 commodity path flow 唯一；配方图没有 buckwheat/sandleaf SCC；所有终品交付都被计入该 9135 口径

- **依赖 claim：** CLAIM-WAREHOUSE-BRIDGE-EXCLUSION-TARGET-CONDITIONAL

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** throughput_capacity
- **验证方式：** source_recomputation；independent_recomputation；adversarial_review

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔OB1 exact flow caliber and corrected aggregate-flow semantics〕

<a id="claim-p2-single-layer-area-bound-1015"></a>

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

<a id="claim-p2-steel-block-17-lt-18-refuted"></a>

### “steel_block 17<18 因而必分流”已被反例推翻

- **Claim ID：** `CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED`
- **状态：** `refuted`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

旧论证把六台制瓶机强制均摊为各 11/12 占空，得到耗侧 18 条道并以 17<18 宣称必分流。允许合法的台间非均摊后，5 满 1 半给出 11 条制瓶耗道，加六条零件耗道恰为 17，与 17 条钢块产道一一匹配，因此旧鸽巢结论不成立。

- **适用范围：** p2_0；steel-block；historical-refutation

- **成立前提：** 同一 operation 的台间占空是布局自由度而非固定均摊；5 满 1 半阶梯分配在已审语义下可用

- **直接后果：** 不得再把 steel_block 列入无条件必分流商品；任何依赖 17<18 的下游结论必须重验

- **明确不推出：** 完整 P2.0 网络可行；钢块一定存在几何免分流布局；其他商品的必分流结论也被推翻

- **依赖 claim：** CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL

- **权威源：** docs/research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md；docs/research/p2_0_specialized_20260807/P2_0_SPECIALIZED_DESIGN_V1.md

- **条件处置：** `refuted`
- **操作效果：** counterexample
- **一般性：** `frozen_instance`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **推导角色：** `counterexample`
- **数学推导族：** branch_counting
- **验证方式：** counterexample；independent_recomputation

- **有效性事件：** `refutation`
- **受影响层：** proof_argument
- **判定依据：** counterexample；independent_recomputation
- **复用策略：** `do_not_reuse`
- **修复状态：** `not_applicable`
- **时间作用域：** `universal_claim`
- **有效性注：** 旧鸽巢结论本身被合法的 5 满 1 半分配反例击穿。

- **证据：** [docs/research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md](<research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md>)〔refutation and 17-to-17 construction〕；[docs/research/p2_0_specialized_20260807/P2_0_SPECIALIZED_DESIGN_V1.md](<research/p2_0_specialized_20260807/P2_0_SPECIALIZED_DESIGN_V1.md>)〔corrected design projection〕

<a id="claim-p2-throughput-research-ledger"></a>

### P2.0 吞吐语义另有 A≤1167 / A≤1015 条件账本

- **Claim ID：** `CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`
- **状态：** `superseded`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-14`

在 P2.0 第七谓词语义下，无条件面积上界为 A≤1167；单层口径给出 A≤1015，但依赖待闭合的 OB6 条件；电杆下界 P≥9。max_lex 的 min_side 次坐标上界仍未建立。该账本与六谓词 U=(1188,18) 并存且禁止混写。

- **适用范围：** p2_0；throughput-conservation；research-upper-bound

- **成立前提：** production_targets、严格空地、吞吐守恒与循环稳态；A≤1015 额外依赖 OB6 单层/交叉密度条件

- **直接后果：** P2.0 语义下可使用 A≤1167；满足 OB6 时可使用条件界 A≤1015；电杆数满足 P≥9；完整 lex 闭合仍需在 area=U_A 层建立 min_side 上界

- **明确不推出：** 六谓词上界发生变化；第七谓词已经证明改变全局最优解；A≤1015 是无条件结论；P2.0 的 max_lex 两个坐标已经闭合

- **依赖 claim：** CLAIM-P2-AREA-BOUND-1167；CLAIM-P2-MIN-SIDE-UPPER-OPEN；CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md；docs/research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md

- **推导角色：** `ledger_projection`
- **数学推导族：** research_ledger；area_accounting；throughput_capacity
- **验证方式：** authority_admission；machine_source_projection

- **有效性事件：** `semantic_replacement`
- **受影响层：** proof_argument；documentation
- **判定依据：** evidence_gap；independent_recomputation
- **复用策略：** `historical_only`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** Phase 2 Batch 2 曾在原 ID 上保守改写语义；本迁移冻结该身份，并由新 ID 显式接续当前账本含义。

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔P2.0 area-bound authority〕；[docs/research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md](<research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md>)〔specialized-line owner-facing adjudication summary〕；[.artifacts/p2_0_refresh_20260805/area_bound_work](<../.artifacts/p2_0_refresh_20260805/area_bound_work>)〔local receipts and review root〕（工作区可选工件）

<a id="claim-p2-throughput-research-ledger-20260814"></a>

### P2.0 吞吐语义的独立条件账本

- **Claim ID：** `CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-14`

在 P2.0 第七谓词语义下，无条件面积上界为 A≤1167；单层口径给出 A≤1015，但依赖待闭合的 OB6 条件；电杆下界 P≥9。max_lex 的 min_side 次坐标上界仍未建立。该账本与六谓词 U=(1188,18) 并存且禁止混写。

- **适用范围：** p2_0；throughput-conservation；research-upper-bound

- **成立前提：** production_targets、严格空地、吞吐守恒与循环稳态；A≤1015 额外依赖 OB6 单层/交叉密度条件

- **直接后果：** P2.0 语义下可使用 A≤1167；满足 OB6 时可使用条件界 A≤1015；电杆数满足 P≥9；完整 lex 闭合仍需在 area=U_A 层建立 min_side 上界

- **明确不推出：** 六谓词上界发生变化；第七谓词已经证明改变全局最优解；A≤1015 是无条件结论；P2.0 的 max_lex 两个坐标已经闭合

- **依赖 claim：** CLAIM-P2-AREA-BOUND-1167；CLAIM-P2-MIN-SIDE-UPPER-OPEN；CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015

- **取代 claim：** CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER

- **权威源：** docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md；docs/research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md

- **推导角色：** `ledger_projection`
- **数学推导族：** research_ledger；area_accounting；throughput_capacity
- **验证方式：** authority_admission；machine_source_projection

- **有效性事件：** `semantic_replacement`
- **受影响层：** proof_argument；documentation
- **判定依据：** independent_recomputation；evidence_gap
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** 以新稳定 ID 承载 Phase 2 Batch 2 后的保守语义，补回显式换代链。

- **证据：** [docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md](<research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md>)〔P2.0 area-bound authority〕；[docs/research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md](<research/p2_0_specialized_20260807/OWNER_DECISION_SUMMARY.md>)〔specialized-line owner-facing adjudication summary〕；[.artifacts/p2_0_refresh_20260805/area_bound_work](<../.artifacts/p2_0_refresh_20260805/area_bound_work>)〔local receipts and review root〕（工作区可选工件）

<a id="claim-pairwise-closure-incomplete"></a>

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

<a id="claim-power-halo-pole-lower-bound-nine"></a>

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

<a id="claim-proved-premodel-exclusion-permits-model-omission"></a>

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

<a id="claim-r1-1326-34-strict-upper-revalidated"></a>

### R1 strict `(1326,34)` 上界已由两段证明链重新验证

- **Claim ID：** `CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED`
- **状态：** `historical`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

在 R1 strict 输入上，面积大于 1348 的 1763 个有向尺寸由自由格上限排除；剩余 22 个 lexicographically-better 有向尺寸由独立 translation gate、RoundingSat proof log 与 VeriPB 3.0.2 验证的 residual-band OPB 排除，因此历史 R1 研究上界 `(1326,34)` 得到修正语义下的闭环恢复。

- **适用范围：** r1；strict-empty-rectangle；historical-upper-bound

- **成立前提：** 只消费登记的 strict R1 输入闭包；面积带外论证与带内 PB 证书共同成立

- **直接后果：** R1 历史上界可在精确作用域内引用；PB 证书只承担 22 个 residual-band 尺寸

- **明确不推出：** 其他事故前 PB、RND 或 solver 结果恢复；当前 R4 研究账本被替代；production CERTIFIED

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT

- **权威源：** docs/research/front_offset_incident_20260718/07_pb03_r1_upper_bound_veripb_revalidation_20260720.md

- **条件处置：** `discharged`
- **操作效果：** bound_tightening；scope_boundary
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** formal_proof；incident_review

- **推导角色：** `composite_theorem`
- **数学推导族：** area_accounting；lex_band_enumeration；finite_pb_proof
- **验证方式：** paper_derivation；exact_enumeration；independent_recomputation；roundingsat_veripb
- **推导注：** 完整上界是带外初等排除与带内 PB UNSAT 证书的合取。

- **目标阶段：** `knowledge_only`
- **候选来源：** `explicit_finite`
- **选择方式：** finite_enumeration
- **验证方式：** independent_validator；proof_object
- **完备性：** `proved_for_declared_domain`
- **消费方式：** objective_bound；knowledge_only
- **基线比较：** `formal`
- **分离注：** 证书覆盖 residual band，不能把整个上界误写成单一 OPB 证明。

- **有效性事件：** `revalidation`
- **受影响层：** model_encoding；validator；proof_argument
- **判定依据：** proof_replay；independent_recomputation
- **复用策略：** `historical_only`
- **修复状态：** `revalidated`
- **时间作用域：** `run_family`

- **证据：** [docs/research/front_offset_incident_20260718/07_pb03_r1_upper_bound_veripb_revalidation_20260720.md](<research/front_offset_incident_20260718/07_pb03_r1_upper_bound_veripb_revalidation_20260720.md>)〔corrected-semantics PB revalidation record〕；[.artifacts/front_offset_incident_20260718](<../.artifacts/front_offset_incident_20260718>)〔local proof and verification receipts〕（工作区可选工件）

<a id="claim-r3-lex-band-2074-unsat-given-geometry"></a>

### 给定 R3 几何引理，2074 个 lex-better 尺寸的算术层为 UNSAT

- **Claim ID：** `CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY`
- **状态：** `historical`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-14`

给定 R3 ordinary membrane、power-halo 与 access-cell capacity 引理，全部 2074 个 oriented dimensions 满足 lex(area,min_side)>(1190,34) 的 selector formula 已由 RoundingSat proof 与 VeriPB 3.0.2 验证为 UNSAT；最小必要式左端为 1322，出现在 19×63 与 63×19。

- **适用范围：** historical-r3；lex-band；formal-arithmetic

- **成立前提：** CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48 成立；CLAIM-BODY-ACCESS-BUDGET-1320 成立；R3 translation gate 对完整 oriented band 与 OPB multiset 独立重建通过

- **直接后果：** 历史 research upper ledger 获得 (1190,34) 的 proof-bearing arithmetic closure；提供后续 R4/SMM 上界链的机器验证先例与信任分层模板

- **明确不推出：** (1190,34) 可达；当前 research upper 仍是 (1190,34)；R3 几何引理在 PB proof 内部被重新证明；production CERTIFIED 或全局最优性

- **依赖 claim：** CLAIM-BODY-ACCESS-BUDGET-1320；CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48

- **权威源：** docs/research/r3_upper_bound_pb_20260722/README.md

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** formal_proof；adversarial_review

- **推导角色：** `composite_theorem`
- **数学推导族：** lex_band_enumeration；finite_pb_proof；integer_rounding
- **验证方式：** exact_enumeration；roundingsat_veripb；independent_recomputation

- **证据：** [docs/research/r3_upper_bound_pb_20260722/README.md](<research/r3_upper_bound_pb_20260722/README.md>)〔proof-bearing R3 arithmetic report and detached evidence identities〕

<a id="claim-r4-boundary-23-23-full-span-exclusion"></a>

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

<a id="claim-r4-lex-band-2084-unsat"></a>

### 给定 A004 几何引理，lex>(1188,22) 的 2084-orientation band 为 UNSAT

- **Claim ID：** `CLAIM-R4-LEX-BAND-2084-UNSAT`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-14`

给定 R4 a004 已准入的 ordinary membrane、marked membrane、local access-cell、power-halo 与 full-span 引理，全部 2084 个 oriented dimensions 满足 lex(area,min_side)>(1188,22) 的 OPB 已由 RoundingSat proof 与 VeriPB 3.0.2 验证为 UNSAT；detached receipt 明确授权当时的 research upper update。

- **适用范围：** r4；lex-band；formal-verification

- **成立前提：** CLAIM-R4-NECESSARY-DIMENSION-INEQUALITY 成立；CLAIM-R4-BOUNDARY-23-23-FULL-SPAN-EXCLUSION 成立；independent translation gate 对 2084 variables、2192 constraints 与 107 full-span forbids 完整重建

- **直接后果：** 旧 research upper ledger 可从 (1190,34) 更新为 (1188,22)；该完整旧 band 可作为 SMM4 composition 的只读前件

- **明确不推出：** (1188,22) 可达；当前 research upper 停留在 (1188,22)；a004 几何引理在 PB proof 内部被重新证明；production CERTIFIED 或 whole-instance infeasibility

- **依赖 claim：** CLAIM-R4-BOUNDARY-23-23-FULL-SPAN-EXCLUSION；CLAIM-R4-NECESSARY-DIMENSION-INEQUALITY

- **权威源：** docs/research/b1_r4_1188_22_pb_20260723/README.md；docs/research/b1_r4_1188_22_pb_20260723/03_execution_record.md

- **条件处置：** `discharged`
- **操作效果：** candidate_pruning；bound_tightening
- **一般性：** `frozen_instance`
- **solver 关系：** `pre_model_reduction`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** formal_proof；adversarial_review
- **分类注：** 这是给定几何引理后的完整有限 band UNSAT，不是对通用 CP-SAT 传播能力的下界。

- **推导角色：** `composite_theorem`
- **数学推导族：** lex_band_enumeration；finite_pb_proof；integer_rounding
- **验证方式：** exact_enumeration；roundingsat_veripb；independent_recomputation；authority_admission

- **证据：** [docs/research/b1_r4_1188_22_pb_20260723/README.md](<research/b1_r4_1188_22_pb_20260723/README.md>)〔formal band definition, toolchain outcome and claim boundary〕；[docs/research/b1_r4_1188_22_pb_20260723/03_execution_record.md](<research/b1_r4_1188_22_pb_20260723/03_execution_record.md>)〔detached receipt replay and immutable execution record〕

<a id="claim-r4-local-weighted-access-capacity-4"></a>

### R4 marked 账下每个外部 access cell 满足 t+m≤4

- **Claim ID：** `CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

对当前 strict template vocabulary 的任一 body-free access cell，令 t 为使用该格的 active terminal incidences 数、m 为其中 marked incidences 数，则总有 t+m≤4。t≤2 时由 m≤t 直接得到；t=3/4 时，枚举所有方向互异且 bodies 不重叠的 local placements 分别给出 max m=1/0。

- **适用范围：** r4-marked-incidence；local-access-cell；current-frozen-instance

- **成立前提：** 每个 access cell 只有四个正交邻接 body positions；strict facility templates、port directions 与 body nonoverlap 保持不变；CLAIM-R4-MARKED-INCIDENCE-TOTAL-110 的 marked definition 不变

- **直接后果：** 外部 cells 数 N 满足 4N≥T_out+M_out；marked membrane 可以与 ordinary membrane 在同一 local-capacity 账中叠加

- **明确不推出：** 单格最多只有四个普通 incidences 的更强几何分类已穷尽 routing semantics；该局部不等式单独产生当前 upper update；通用 solver propagation 会自动发现同一 weighted inequality

- **依赖 claim：** CLAIM-R4-MARKED-INCIDENCE-TOTAL-110

- **权威源：** docs/research/r4_response_review_20260723/02_necessity_proof.md；docs/research/r4_response_review_20260723/03_independent_recomputation.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；formal_proof；adversarial_review

- **推导角色：** `atomic_lemma`
- **数学推导族：** local_access_capacity；marked_membrane
- **验证方式：** exact_enumeration；independent_recomputation；adversarial_review

- **证据：** [docs/research/r4_response_review_20260723/02_necessity_proof.md](<research/r4_response_review_20260723/02_necessity_proof.md>)〔local exhaustive enumeration and t+m bound〕；[docs/research/r4_response_review_20260723/03_independent_recomputation.md](<research/r4_response_review_20260723/03_independent_recomputation.md>)〔independent exact-match local geometry report〕

<a id="claim-r4-marked-incidence-total-110"></a>

### R4 marked-incidence census 的总数为 110

- **Claim ID：** `CLAIM-R4-MARKED-INCIDENCE-TOTAL-110`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

当前 strict instance 对每个 manufacturing face 标记 max(0,active_count-2) 个必然 active 的 noncorner incidences，共 58；52=52 raw-provider 槽账使 46 个 boundary raw outputs 与六个 protocol-core raw outputs 全部 active 且均为 noncorner。故 marked incidence 总数 M=58+52=110。

- **适用范围：** r4-marked-incidence；current-frozen-instance；raw-output-slots

- **成立前提：** strict manufacturing operation census 与 face active counts 不变；CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED 成立；两个 final inputs 不属于 marked set

- **直接后果：** marked membrane 可把外部 marked incidences 写作 M_out≥110-M_in；SMM entity-max refinement 沿用同一 110-mark 定义

- **明确不推出：** 110 个 marks 使用 110 个不同 access cells；所有 active terminal incidences 都被标记；marked count 单独排除任一 rectangle size

- **依赖 claim：** CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED

- **权威源：** docs/research/r4_response_review_20260723/02_necessity_proof.md；docs/research/r4_response_review_20260723/03_independent_recomputation.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** zero_slack_audit；targeted_derivation；formal_proof

- **推导角色：** `atomic_lemma`
- **数学推导族：** entity_census；slot_saturation
- **验证方式：** source_recomputation；independent_recomputation

- **证据：** [docs/research/r4_response_review_20260723/02_necessity_proof.md](<research/r4_response_review_20260723/02_necessity_proof.md>)〔58 manufacturing plus 52 raw-provider mark census〕；[docs/research/r4_response_review_20260723/03_independent_recomputation.md](<research/r4_response_review_20260723/03_independent_recomputation.md>)〔independent exact-match census〕

<a id="claim-r4-marked-membrane-bound-s12"></a>

### R4 marked membrane 对 normalized w≥9 给出 M_in≤S+12

- **Claim ID：** `CLAIM-R4-MARKED-MEMBRANE-BOUND-S12`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

对 normalized body-empty rectangle 9≤w≤h，令 S=w+h。当前 marked-side census 的每类均满足 2r≤s；full contacts 按半密度计，至多八个 directed endpoint partial contacts 各增加至多三个 doubled units，故 2M_in≤2S+24，即 M_in≤S+12。

- **适用范围：** r4-marked-membrane；normalized-w-ge-9；strict-empty-rectangle

- **成立前提：** CLAIM-R4-MARKED-INCIDENCE-TOTAL-110 的 marked-side census 成立；同一 directed rectangle side 上 contact intervals 两两不交；每个 directed endpoint 至多一个 body-nonoverlapping partial contact

- **直接后果：** 当 w≥9 时 M_out≥98-S；可与 ordinary membrane 共同给出 weighted external-incidence lower bound 678-2S

- **明确不推出：** w<9 时同一 marked bound 仍可直接使用；sidewise entity-max 的更强 S+9 bound 自动成立；marked terminals 之间具有 routing independence

- **依赖 claim：** CLAIM-R4-MARKED-INCIDENCE-TOTAL-110

- **权威源：** docs/research/r4_response_review_20260723/02_necessity_proof.md；docs/research/r4_response_review_20260723/03_independent_recomputation.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；candidate_pruning
- **一般性：** `parameterized_family`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；adversarial_review；formal_proof

- **推导角色：** `composite_theorem`
- **数学推导族：** marked_membrane；endpoint_budget
- **验证方式：** paper_derivation；independent_recomputation；adversarial_review

- **证据：** [docs/research/r4_response_review_20260723/02_necessity_proof.md](<research/r4_response_review_20260723/02_necessity_proof.md>)〔marked-side census and endpoint membrane proof〕；[docs/research/r4_response_review_20260723/03_independent_recomputation.md](<research/r4_response_review_20260723/03_independent_recomputation.md>)〔independent coordinate/census confirmation〕

<a id="claim-r4-necessary-dimension-inequality"></a>

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

<a id="claim-rab-fcl-front-dependent-performance-withdrawn"></a>

### 旧 RAB/FCL 的 front-dependent 性能与收敛归因已撤回，复用前须按修正语义重验

- **Claim ID：** `CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

RAB-SEP 与 front-clear lift 在 2026-07-18 前产生的 EMPTY_DOMAIN、cut/core 分布、blocker 命中、binding 绕行、长跑干涸和“时间杠杆已测穿/结构墙”归因均依赖错位 front 模型，已失去当前性能与证明效力。只有与 front 坐标无关的工程纪律、遥测方法和逐次运行的历史事实可以按其原作用域保留；任何效果或收敛判断都必须在 corrected-front、可比配置和独立规则 oracle 下重验。

- **适用范围：** rab-separation；front-clear-lift；pre-2026-07-18-performance

- **成立前提：** 被引用结果的 blocker、EMPTY_DOMAIN、front-clear 或相关模型约束实际消费了旧 front offset 语义；尚无 corrected-front、同配置且可独立复核的替代实验覆盖该具体性能或收敛结论

- **直接后果：** 旧 RAB/FCL 数值和收敛归因不得进入当前路线优先级、性能基线或证明陈述；可复用的证书结构纪律与 raw-event 遥测原则必须和已失效的效果数字分账；新实验必须显式记录 corrected-front 语义、可比配置、stage reachability 与独立 oracle

- **明确不推出：** RAB 或 front-clear lift 在修正语义下一定无效；旧运行从未真实发生或其资源日志没有历史价值；与 front 坐标无关的 fail-closed 证书纪律和 telemetry 方法被撤回；23 小时 UNKNOWN 构成数学上的不可行性或通用传播不可能性证明

- **依赖 claim：** CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED

- **权威源：** docs/research/rab_sep_promotion_20260716/03_stage3_prod_drill_verdict_20260716.md；docs/research/rab_sep_promotion_20260716/06_front_clear_lift_ab_verdict_20260716.md；docs/research/rab_sep_promotion_20260716/07_owner_decision_package_20260717.md；docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md

- **条件处置：** `scope_shifted`
- **操作效果：** experiment_boundary；scope_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** incident_review；adversarial_review
- **分类注：** 撤回的是旧语义下的效果与收敛归因，不是对 repaired implementation 的普遍否定。

- **有效性事件：** `experiment_invalidation`
- **受影响层：** canonical_semantics；model_encoding；solver_runtime；experiment_design；proof_argument；research_strategy
- **判定依据：** incident_replay；evidence_gap
- **复用策略：** `revalidate_before_use`
- **修复状态：** `pending`
- **时间作用域：** `pre_fix_history`
- **有效性注：** 方法性资产可按独立 claim 保留；任何 front-dependent 数字、效果或路线结论仍待 corrected-front 重验。

- **证据：** [docs/research/rab_sep_promotion_20260716/03_stage3_prod_drill_verdict_20260716.md](<research/rab_sep_promotion_20260716/03_stage3_prod_drill_verdict_20260716.md>)〔withdrawn RAB production-drill performance and convergence attribution〕；[docs/research/rab_sep_promotion_20260716/06_front_clear_lift_ab_verdict_20260716.md](<research/rab_sep_promotion_20260716/06_front_clear_lift_ab_verdict_20260716.md>)〔withdrawn front-clear A/B numbers and probe attribution〕；[docs/research/rab_sep_promotion_20260716/07_owner_decision_package_20260717.md](<research/rab_sep_promotion_20260716/07_owner_decision_package_20260717.md>)〔historical overnight UNKNOWN and route-ranking package under old semantics〕；[docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md](<research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md>)〔itemized RAB/FCL invalidation and revalidation requirements〕

<a id="claim-rate-lemma-conditional-profile"></a>

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

<a id="claim-raw-eligible-events-required-for-separation-evaluation"></a>

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

<a id="claim-round45-corrected-profile-unknown-not-structural-wall"></a>

### 修正后的 Round 4/5 紧凑模型只支持预算内 UNKNOWN，不支持结构墙

- **Claim ID：** `CLAIM-ROUND45-CORRECTED-PROFILE-UNKNOWN-NOT-STRUCTURAL-WALL`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

在 identity-front、82,829 新池和 628 个 routing-visible 实体口下，三个真锚点的 bespoke coordinate master 均为 10,816 variables、16,513 constraints；六条固定臂在 600 秒与 1,200 秒内全部 clean UNKNOWN，memory.events 与 swap 均为零。该重验恢复的窄结论只有“当前 strict-lean profile 在当前预算内不收敛”，不能恢复旧模型上的结构墙、不可行性或 solver 范式穷尽判断。

- **适用范围：** front-offset-revalidation；round4-round5；three-registered-anchors

- **成立前提：** 使用登记的 identity-front 输入、candidate pool、单 worker seeds 与 600/1200 秒预算；模型忘掉全局 belt connectivity，因此即使 FEASIBLE 也只是松弛 witness

- **直接后果：** 三锚点当前没有上界证书；后续可解性研究必须把 profile、预算和编码写入作用域；UNKNOWN 必须与 INFEASIBLE、OOM 和结构性不可解分开

- **明确不推出：** 三锚点可行或不可行；CP-SAT 结构性无法解决该模型；增加时间一定无效；旧 18–20 GiB 内存墙在当前模型上复现；全局面积上界成立

- **依赖 claim：** CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT；CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED

- **权威源：** docs/research/front_offset_incident_20260718/06_round45_bespoke_coordinate_master_revalidation_20260719.md

- **条件处置：** `inconclusive`
- **操作效果：** experiment_boundary；scope_boundary
- **一般性：** `frozen_instance`
- **solver 关系：** `model_constraint`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；incident_review

- **目标阶段：** `search_loop`
- **候选来源：** `declared_inventory`
- **选择方式：** manual_targeting
- **验证方式：** independent_validator；terminal_replay
- **完备性：** `open`
- **消费方式：** diagnostic_only；knowledge_only
- **基线比较：** `controlled`
- **分离注：** 六臂用于重验修正语义下的 solver profile，不产生 INFEASIBLE certificate。

- **有效性事件：** `revalidation`
- **受影响层：** model_encoding；solver_runtime；experiment_design；proof_argument
- **判定依据：** controlled_experiment；independent_recomputation
- **复用策略：** `current_after_repair`
- **修复状态：** `revalidated`
- **时间作用域：** `run_family`

- **证据：** [docs/research/front_offset_incident_20260718/06_round45_bespoke_coordinate_master_revalidation_20260719.md](<research/front_offset_incident_20260718/06_round45_bespoke_coordinate_master_revalidation_20260719.md>)〔corrected model identity, six runs and interpretation boundary〕

<a id="claim-routing-reverification-extra-strict"></a>

### routing reverification 的 no-orphan 与 selected-source-reaches-sink 超出游戏连通量词

- **Claim ID：** `CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT`
- **状态：** `superseded`
- **权威层：** `rules_authority`
- **权威依据：** `rules_source`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `defines_certified_scope`
- **更新时间：** `2026-08-14`

现行 routing reverification 除游戏层已裁决的 connectivity quantifier 外，还要求 no-orphan 与 selected-source-reaches-sink。二者被登记为模型更严格的附加条件，不能静默当成完整游戏语义。

- **适用范围：** routing-reverification；connectivity-quantifier；certified-model-domain

- **成立前提：** canonical model_stricter_faces 登记保持现行；released reverifier 仍施加这两个附加条件

- **直接后果：** 依赖附加连通条件的排除只对受限模型域成立，除非另有 completeness proof

- **明确不推出：** 附加条件在工程上没有价值；游戏允许孤立组件满足任何 certified predicate；已经存在解除该面后的完整重证书

- **依赖 claim：** CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT

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
- **复用策略：** `historical_only`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** 旧记录遗漏了“附加严格面不改变 adjudicated connectivity_quantifier 本身”的明确边界；新 ID 承载补全后的命题。

- **证据：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)〔connectivity and model-stricter authority〕；[docs/research/canonical_batch_20260807/DEPENDENCY_VERIFICATION.md](<research/canonical_batch_20260807/DEPENDENCY_VERIFICATION.md>)〔sealed dependency verification〕；[docs/research/canonical_batch_20260808/DRAFT_DIFF.md](<research/canonical_batch_20260808/DRAFT_DIFF.md>)〔completeness scan coverage〕

<a id="claim-routing-reverification-extra-strict-boundary"></a>

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

<a id="claim-shared-encoding-agreement-not-independent-validation"></a>

### 共享坐标 helper 的 oracle 与 validator 一致不构成独立验证

- **Claim ID：** `CLAIM-SHARED-ENCODING-AGREEMENT-NOT-INDEPENDENT-VALIDATION`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

front offset 事故中，构造器、oracle 与 validator 共享同一坐标解释而产生共模假绿；因此两个 consumer 输出一致，只有在它们不共享承重编码路径且能对差异样例给出预期分歧时，才可作为独立语义复核。

- **适用范围：** validation-method；coordinate-semantics；common-mode-failure

- **成立前提：** 被比较的实现可能共享承重 helper、坐标转换或 fixture

- **直接后果：** 复验计划必须标出独立实现边界；共享 helper 的一致结果只能算重复执行而非异构复核

- **明确不推出：** 共享代码的测试没有任何价值；所有双实现一致结果都是错误的

- **依赖 claim：** CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED

- **权威源：** docs/research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md；docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md

- **条件处置：** `method_only`
- **操作效果：** discovery_method；experiment_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** incident_review；adversarial_review

- **有效性事件：** `implementation_invalidation`
- **受影响层：** model_encoding；validator；experiment_design
- **判定依据：** incident_replay；differential_test
- **复用策略：** `method_only`
- **修复状态：** `revalidated`
- **时间作用域：** `pre_fix_history`
- **有效性注：** 可复用的是独立性纪律，不是事故前任何具体数值。

- **证据：** [docs/research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md](<research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md>)〔common-mode incident evidence〕；[docs/research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md](<research/front_offset_incident_20260718/01_historical_rejudgment_addendum.md>)〔common-oracle historical rejudgment〕

<a id="claim-six-predicate-research-ledger"></a>

### 六谓词 research ledger 为 U=(1188,18)、L=absent

- **Claim ID：** `CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`
- **状态：** `superseded`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `research_upper_update`
- **更新时间：** `2026-08-18`

当前六谓词研究账本为条件性上界 U=(1188,18)，下界 L=absent；production_certified=false。账本更新授权来自 SMM4 的 detached receipt 与 immutable closeout，而不是内部 formal receipt 本身。

- **适用范围：** six-predicate；research-upper-ledger；strict-empty-rectangle

- **成立前提：** SMM4 fresh-authority root、A004/SMM-209 几何链与旧 band authority 均保持其冻结身份；引用时保留条件性标签

- **直接后果：** lex>(1188,18) 的已登记研究 band 被关闭；当前研究上界可写作 U=(1188,18)

- **明确不推出：** 存在 (1188,18) 布局；U 可达；全局 production CERTIFIED；任何下界；吞吐语义下的最优值

- **依赖 claim：** CLAIM-CERTIFIED-THEOREM-SCOPE；CLAIM-SMM4-LEX-BAND-COMPOSITION-2086

- **权威源：** docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md；docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/03_execution_record.md

- **推导角色：** `ledger_projection`
- **数学推导族：** research_ledger；lex_band_enumeration
- **验证方式：** authority_admission；machine_source_projection

- **有效性事件：** `semantic_replacement`
- **受影响层：** proof_argument；documentation
- **判定依据：** independent_recomputation；proof_replay
- **复用策略：** `historical_only`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`
- **有效性注：** 该 ID 保留 U=(1188,18) 的 canonical before-state；同一 slot 的当前 research 条件上界由 CLAIM-SIX-PREDICATE-RESEARCH-LEDGER-20260818 严格收紧为 U=(1170,30)。

- **证据：** [docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md](<research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md>)〔research upper-ledger authority〕；[docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/03_execution_record.md](<research/b1_sidewise_marked_membrane_fresh_authority_20260727/03_execution_record.md>)〔tracked execution and detached-receipt hashes〕；[.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/run-20260726T211018Z-SMM4-14a491b](<../.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/run-20260726T211018Z-SMM4-14a491b>)〔external authorization root named by the tracked authority report〕（工作区可选工件）

<a id="claim-six-predicate-research-ledger-20260818"></a>

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

<a id="claim-smm-209-excludes-22x54"></a>

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

<a id="claim-smm-combined-cap-209"></a>

### SMM-209 给出 T_in+M_in≤209

- **Claim ID：** `CLAIM-SMM-COMBINED-CAP-209`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

对 body-cell-empty 的 22×54（或转置）矩形，ordinary membrane 给出 T_in≤124，strict entity-max marked membrane 给出 M_in≤85，因此矩形内部的普通与 marked incidence 联合容量满足 T_in+M_in≤209。

- **适用范围：** smm-209；22x54；54x22

- **成立前提：** ordinary membrane 的 T_in≤S+48 在 S=76 时给出 124；entity-max endpoint budget 19 给出 M_in≤85

- **直接后果：** 738 个 total weighted incidences 中至少 529 个必须落在矩形外

- **明确不推出：** T_in=124 与 M_in=85 可以同时达到；209 对其他周长或不同 mark definition 自动成立；该联合上界单独排除 22×54

- **依赖 claim：** CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48；CLAIM-SMM-MARKED-MEMBRANE-BOUND-85

- **权威源：** docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md；docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；candidate_pruning
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof；adversarial_review

- **推导角色：** `composite_theorem`
- **数学推导族：** ordinary_membrane；marked_membrane；budget_composition
- **验证方式：** paper_derivation；independent_recomputation；adversarial_review

- **证据：** [docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md](<research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md>)〔SMM-209 combination step〕；[docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md](<research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md>)〔independent/adversarial admission〕

<a id="claim-smm-endpoint-top-eight-budget-19"></a>

### SMM entity-max 的八端点 top-eight budget 为 19

- **Claim ID：** `CLAIM-SMM-ENDPOINT-TOP-EIGHT-BUDGET-19`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

在 current strict 110-mark census 下，以每个实体所有可接触 marked faces 的最大 r 为 entity weight，实体分布为 r=3 有4个、r=2 有3个、r=1 有89个、r=0 有170个。body-empty rectangle 的八个 directed endpoints 至多接触八个不同实体，故 endpoint entity-max 总预算至多 3+3+3+3+2+2+2+1=19。

- **适用范围：** smm；entity-max；strict-empty-rectangle

- **成立前提：** CLAIM-R4-MARKED-INCIDENCE-TOTAL-110 的 marked definition 成立；同一 solid axis-aligned facility 不可能接触 body-empty rectangle 的两个不同 sides；每个 directed endpoint 至多一个 partial contact

- **直接后果：** partial-contact 预算不再把 protocol core 的两个 marked faces 错当成两个实体；对 22×54 可把 marked membrane 从 S+12 收紧到 S+9

- **明确不推出：** 八个最高权实体能在同一 rectangle 上同时实现；该 19 对不同 mandatory instance 或 mark definition 自动不变；top-eight census 单独授权 upper-ledger update

- **依赖 claim：** CLAIM-R4-MARKED-INCIDENCE-TOTAL-110

- **权威源：** docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md；docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening
- **一般性：** `parameterized_family`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof；adversarial_review

- **推导角色：** `atomic_lemma`
- **数学推导族：** endpoint_budget；entity_census
- **验证方式：** source_recomputation；paper_derivation；adversarial_review

- **证据：** [docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md](<research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md>)〔strict entity census and top-eight proof〕；[docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md](<research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md>)〔independent/adversarial geometry judgment〕

<a id="claim-smm-marked-membrane-bound-85"></a>

### SMM 对 22×54 给出 M_in≤85

- **Claim ID：** `CLAIM-SMM-MARKED-MEMBRANE-BOUND-85`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

对 body-cell-empty 22×54 rectangle，perimeter 为 152。full contacts 满足 2r≤s，partial contacts 的额外 entity-max 预算至多 19，因此 2M_in≤152+19=171，故 M_in≤85=S+9。

- **适用范围：** smm-209；22x54；54x22

- **成立前提：** CLAIM-SMM-ENDPOINT-TOP-EIGHT-BUDGET-19 成立；同一 rectangle side 上 full-contact intervals 两两不交；current strict marked-side classes 均满足 2r≤s

- **直接后果：** 与 ordinary T_in≤124 合并得到 T_in+M_in≤209；把 22×54 的 weighted external incidences lower bound 提高到 529

- **明确不推出：** M_in=85 可实现；同一数值 85 对其他 perimeter 自动成立；纸面 marked bound 单独排除 22×54

- **依赖 claim：** CLAIM-SMM-ENDPOINT-TOP-EIGHT-BUDGET-19

- **权威源：** docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md；docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；candidate_pruning
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof；adversarial_review

- **推导角色：** `composite_theorem`
- **数学推导族：** marked_membrane；endpoint_budget
- **验证方式：** paper_derivation；independent_recomputation；adversarial_review

- **证据：** [docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md](<research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md>)〔22x54 sidewise marked-membrane derivation〕；[docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md](<research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md>)〔adversarial admission of the 85 bound〕

<a id="claim-smm-outside-access-lower-133"></a>

### SMM-209 推出至少 133 个外部 access cells

- **Claim ID：** `CLAIM-SMM-OUTSIDE-ACCESS-LOWER-133`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

当前 strict instance 有 628 个 active terminal incidences 和 110 个 marked incidences，共 738 个 weighted incidences。由 T_in+M_in≤209，矩形外至少承担 529；每个 body-free access cell 的局部容量 t+m≤4，因此 distinct outside access cells 数 N≥ceil(529/4)=133。

- **适用范围：** smm-209；22x54；54x22；outside-access-cells

- **成立前提：** strict instance 的 active terminal incidence 总数为 628；marked incidence 总数为 110；每个外部 body-free access cell 满足 t+m≤4

- **直接后果：** 22×54 或 54×22 strict rectangle 需要至少 133 个矩形外 access cells

- **明确不推出：** 133 个 access cells 的几何布局可实现；每个外部 access cell 都达到容量 4；相同下界对其他尺寸或模板词汇自动成立

- **依赖 claim：** CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4；CLAIM-R4-MARKED-INCIDENCE-TOTAL-110；CLAIM-SMM-COMBINED-CAP-209

- **权威源：** docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md；docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md

- **条件处置：** `discharged`
- **操作效果：** constraint_strengthening；candidate_pruning
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** targeted_derivation；formal_proof；adversarial_review

- **推导角色：** `composite_theorem`
- **数学推导族：** local_access_capacity；budget_composition；integer_rounding
- **验证方式：** paper_derivation；independent_recomputation；adversarial_review

- **证据：** [docs/research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md](<research/b1_sidewise_marked_membrane_strict_20260724/01_necessity_proof.md>)〔weighted outside-incidence and ceiling division step〕；[docs/research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md](<research/b1_sidewise_marked_membrane_strict_20260724/02_adversarial_verdict.md>)〔adversarial admission〕

<a id="claim-smm4-lex-band-composition-2086"></a>

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

<a id="claim-smt-mt-synthetic-go-not-transferable-to-real-inner"></a>

### SMT-MT synthetic GO 不能替代真实 inner fuel 的有效性验证

- **Claim ID：** `CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

SMT-MT Phase 0 在 Dummy inner 上得到 76.67% monotone prune ratio、p95 约 293 ms 和 GO；接入真实 B1 LBBD 后，Phase 1 只收到 9 次 INFEASIBLE 通知，在 1,196 个候选中仅剪 9 个，real prune ratio 为 0.7525%，outer 终态 UNPROVEN。前一阶段证明数据结构与单调传播机制可运行，但不能作为真实 inner 能持续提供可传播 INFEASIBLE fuel 的证据。

- **适用范围：** smt-mt-outer-pruning；phase0-to-phase1-transfer；real-inner-fuel

- **成立前提：** 比较使用登记的 Phase 0 Dummy probe 与 Phase 1 real-inner trial；只评价候选剪枝燃料与 transfer validity

- **直接后果：** synthetic cheap-gate 的 GO 必须在真实 inner 上单独验证效果量；outer-pruning 研究必须同时记录 notification rate、unique prune 和 UNPROVEN 比例

- **明确不推出：** SMT modulo monotonic theories 本身不 sound；九个实际 prune 不合法；所有真实 inner 都只能给出 0.7525%；更强的 proof-producing inner 不会改善 fuel

- **权威源：** docs/research/smt_mt_outer_pruning_phase0_20260521/phase0_metrics.json；docs/research/smt_mt_outer_pruning_phase1_20260521/phase1_trial_summary.json

- **条件处置：** `scope_shifted`
- **操作效果：** candidate_pruning；experiment_boundary；scope_boundary
- **一般性：** `model_domain`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **目标阶段：** `search_loop`
- **候选来源：** `solver_events`
- **选择方式：** raw_event_separation
- **验证方式：** direct_arithmetic；terminal_replay
- **完备性：** `heuristic`
- **消费方式：** candidate_filter；diagnostic_only
- **基线比较：** `controlled`
- **分离注：** Phase 0 验的是 synthetic notification stream；Phase 1 才测真实 inner 对传播器的供给率。

- **有效性事件：** `scope_correction`
- **受影响层：** solver_runtime；experiment_design；research_strategy
- **判定依据：** controlled_experiment；differential_test
- **复用策略：** `unaffected_under_premises`
- **修复状态：** `revalidated`
- **时间作用域：** `run_family`

- **证据：** [docs/research/smt_mt_outer_pruning_phase0_20260521/phase0_metrics.json](<research/smt_mt_outer_pruning_phase0_20260521/phase0_metrics.json>)〔synthetic Dummy-inner GO metrics〕；[docs/research/smt_mt_outer_pruning_phase1_20260521/phase1_trial_summary.json](<research/smt_mt_outer_pruning_phase1_20260521/phase1_trial_summary.json>)〔real-inner prune ratio and UNPROVEN terminal result〕

<a id="claim-solver-rethink-g03-lacks-separation-oracle"></a>

### solver-rethink 的 G-03 只有 checker，缺自主 separator

- **Claim ID：** `CLAIM-SOLVER-RETHINK-G03-LACKS-SEPARATION-ORACLE`
- **状态：** `historical`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

solver-rethink 一期草案中的 G-03 能检查一个给定 (S,R) 是否违反 Hall 条件，却没有规定如何在海量 S、R 中自主找到有用违反。成本重标定后该能力缺口仍被保留，收敛稿要求另配非可信 HallSeparator，并以隐藏 trace 上自主产出非硬编码 judgment 作为验收。

- **适用范围：** solver-rethink；hall-separation；candidate-generation

- **成立前提：** 评价对象限定为 2026-08-08 solver-rethink 一期草案；G-03 checker 与候选 producer 分离；该设计未进入 production 实现

- **直接后果：** 该草案不能凭 checker 存在声称具备自主 Hall separation；后续实现必须独立交付 separator 并做隐藏输入验收；该缺口进入设计风险而非被成本折扣抹掉

- **明确不推出：** 所有 Hall separator 都不可实现；当前 production solver 缺少所有候选生成能力；solver-rethink 整体已被 owner 永久否决

- **依赖 claim：** CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS

- **权威源：** .artifacts/solver_rethink_20260808/VELOCITY_RECALIBRATION_20260808.md；.artifacts/solver_rethink_20260808/CONVERGENCE_9_9F_92.md

- **条件处置：** `inconclusive`
- **操作效果：** experiment_boundary；scope_boundary
- **一般性：** `research_process`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** adversarial_review
- **分类注：** 历史设计缺的是 producer，不是 supplied-candidate validity checker。

- **推导角色：** `open_obligation`
- **数学推导族：** closure_search
- **验证方式：** adversarial_review

- **目标阶段：** `candidate_generation`
- **候选来源：** `implicit_combinatorial`
- **选择方式：** not_applicable
- **验证方式：** independent_validator
- **完备性：** `open`
- **消费方式：** knowledge_only
- **基线比较：** `formal`
- **分离注：** 对设计能力的静态审查已闭合；separator 本体仍未实现。

- **证据：** [.artifacts/solver_rethink_20260808/VELOCITY_RECALIBRATION_20260808.md](<../.artifacts/solver_rethink_20260808/VELOCITY_RECALIBRATION_20260808.md>)〔C-12 capability gap survives cost recalibration〕（工作区可选工件）；[.artifacts/solver_rethink_20260808/CONVERGENCE_9_9F_92.md](<../.artifacts/solver_rethink_20260808/CONVERGENCE_9_9F_92.md>)〔required HallSeparator and hidden-trace autonomous discovery gate〕（工作区可选工件）

<a id="claim-solver-rethink-phase1-omits-construction-half"></a>

### solver-rethink 一期不覆盖 witness/下界构造半边

- **Claim ID：** `CLAIM-SOLVER-RETHINK-PHASE1-OMITS-CONSTRUCTION-HALF`
- **状态：** `historical`
- **权威层：** `research_only`
- **权威依据：** `research_only`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `descriptive_only`
- **更新时间：** `2026-08-11`

solver-rethink 一期草案主要提供必要条件、排除与上界裁剪；充分限制、ConstructorRule、candidate 到六谓词 terminal receipt 的见证链在原计划中缺位。收敛稿因此要求至少一个真实 construction vertical slice，并规定若一期仍不做下界充分限制，就只能评价上界裁剪管线，不能评价上下界钳口闭合架构。

- **适用范围：** solver-rethink；witness-construction；scope-boundary

- **成立前提：** 评价对象限定为未立线的一期设计；现行 certified 存在性仍为 open；必要条件不能代替充分构造

- **直接后果：** 一期验收结论必须显式限定为 upper-bound pruning；完整架构评估需要 constructor、terminal receipt 与 score recomputation；下界/见证义务单独保留

- **明确不推出：** 当前 production witness 链已由该草案改变；上界研究没有价值；存在性已被证明不可能

- **依赖 claim：** CLAIM-CERTIFIED-EXISTENCE-OPEN

- **权威源：** .artifacts/solver_rethink_20260808/VELOCITY_RECALIBRATION_20260808.md；.artifacts/solver_rethink_20260808/CONVERGENCE_9_9F_92.md

- **条件处置：** `scope_shifted`
- **操作效果：** scope_boundary；experiment_boundary
- **一般性：** `research_process`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** adversarial_review
- **分类注：** 该 claim 约束历史设计能声称回答的问题。

- **推导角色：** `open_obligation`
- **数学推导族：** research_ledger
- **验证方式：** adversarial_review

- **目标阶段：** `post_solve`
- **候选来源：** `not_applicable`
- **选择方式：** not_applicable
- **验证方式：** terminal_replay
- **完备性：** `open`
- **消费方式：** knowledge_only
- **基线比较：** `formal`
- **分离注：** 没有 constructor vertical slice 时不能把 pruning pipeline 评价扩写为钳口闭合。

- **证据：** [.artifacts/solver_rethink_20260808/VELOCITY_RECALIBRATION_20260808.md](<../.artifacts/solver_rethink_20260808/VELOCITY_RECALIBRATION_20260808.md>)〔B-07 missing sufficient/construction half〕（工作区可选工件）；[.artifacts/solver_rethink_20260808/CONVERGENCE_9_9F_92.md](<../.artifacts/solver_rethink_20260808/CONVERGENCE_9_9F_92.md>)〔constructor vertical slice and scope-limited evaluation requirement〕（工作区可选工件）

<a id="claim-source-front-exclusivity-overstrict"></a>

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

<a id="claim-storage-box-acceptance-invariant-frozen"></a>

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

<a id="claim-strict-hole-avoids-x1-y1"></a>

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

<a id="claim-stricter-feasible-set-preserves-negative-not-positive"></a>

### 可行集收紧保留负结果与上界，但不保留旧正向见证

- **Claim ID：** `CLAIM-STRICTER-FEASIBLE-SET-PRESERVES-NEGATIVE-NOT-POSITIVE`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

当 strict empty-rectangle 可行集是旧 loose 可行集的子集时，在 loose 集上证明的 INFEASIBLE 结论和目标上界对 strict 集方向安全；在 loose 集上找到的可行见证则不能据此迁移，必须重新验证全部 strict occupant 条件。

- **适用范围：** feasible-set-monotonicity；empty-rectangle；historical-validity

- **成立前提：** strict 可行集确为 loose 可行集的子集；比较使用同一目标定义

- **直接后果：** 历史负结果可按方向安全保留；历史正向 witness 必须逐件重验

- **明确不推出：** 宽松负结果的原始 proof artifact 已采用当前语义；所有数值和证书都能无条件恢复

- **依赖 claim：** CLAIM-EMPTY-RECTANGLE-STRICT

- **权威源：** docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md

- **条件处置：** `discharged`
- **操作效果：** scope_boundary；semantic_partition；bound_tightening
- **一般性：** `model_domain`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** owner_adjudication；targeted_derivation

- **推导角色：** `atomic_lemma`
- **数学推导族：** feasible_set_monotonicity
- **验证方式：** paper_derivation；authority_admission

- **有效性事件：** `scope_correction`
- **受影响层：** canonical_semantics；proof_argument
- **判定依据：** owner_adjudication；independent_recomputation
- **复用策略：** `unaffected_under_premises`
- **修复状态：** `revalidated`
- **时间作用域：** `design_version`

- **证据：** [docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md](<research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md>)〔set-inclusion direction adjudication〕

<a id="claim-typed-cut-pipeline-consumes-known-cuts-not-discovers-them"></a>

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

<a id="claim-w0-adjacent-4x4-power-impossibility-refuted"></a>

### W0 相邻 4+4 宏族供电不可行定理已被坐标反例推翻

- **Claim ID：** `CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED`
- **状态：** `refuted`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

28 号答卷声称其声明范围内不存在用 25 根电杆覆盖 219 台设施的相邻 4+4 宏族布局；27 号坐标见证落在该声明范围内，独立复算其 25 根杆覆盖 219/219，因此旧不可行结论本身被直接反例推翻。

- **适用范围：** w0；power-coverage；adjacent-4x4-macro-family

- **成立前提：** 反例只使用机身、电杆和供电覆盖层；27 号布局满足旧定理明示的范围条件

- **直接后果：** 旧定理不得用于砍掉该宏族或停止枚举

- **明确不推出：** 27 号完整 routing/port witness 已获认证；全局必要不等式 R<=3Q 被推翻；完整见证不存在这一更大命题已被反证

- **权威源：** docs/research/w0_front_aware_20260803/CONSULT_VERDICT_TRIPLE_20260804.md

- **条件处置：** `refuted`
- **操作效果：** counterexample；scope_boundary
- **一般性：** `parameterized_family`
- **solver 关系：** `not_applicable`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** adversarial_review；solver_experiment

- **推导角色：** `counterexample`
- **数学推导族：** power_coverage；boundary_packing
- **验证方式：** counterexample；independent_recomputation；adversarial_review

- **有效性事件：** `refutation`
- **受影响层：** proof_argument；research_strategy
- **判定依据：** counterexample；independent_recomputation
- **复用策略：** `do_not_reuse`
- **修复状态：** `not_applicable`
- **时间作用域：** `universal_claim`
- **有效性注：** 被反驳的是不可行结论；旧报告中的 R<=3Q 全局必要式在该见证上仍成立。

- **证据：** [docs/research/w0_front_aware_20260803/CONSULT_VERDICT_TRIPLE_20260804.md](<research/w0_front_aware_20260803/CONSULT_VERDICT_TRIPLE_20260804.md>)〔direct coordinate counterexample and collision review〕

<a id="claim-w0-power-obstruction-requires-declared-height-purity"></a>

### W0 供电阻塞证明只能在明示的模板到带高纯装前提下复用

- **Claim ID：** `CLAIM-W0-POWER-OBSTRUCTION-REQUIRES-DECLARED-HEIGHT-PURITY`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `conditional_model_exclusion`
- **更新时间：** `2026-08-11`

旧 W0 证明把 3x3 设施全部装入 3 高带并每带恰装 22 台当成推论，实际上这是未申报的模板到带高纯装前提；最小可复用修法必须把范围收窄到纯装家族，或重新定义能看见复合宏余隙的 q_i 并重证。

- **适用范围：** w0；power-obstruction；pure-placement-family

- **成立前提：** 每台设施只进入与其高度相等的带，或另有新定义与完整重证

- **直接后果：** 不满足纯装前提的 mixed-height band 布局不能被旧证明排除；证明范围行必须显式列出模板纯度

- **明确不推出：** 纯装家族不可行已经在本 claim 中重新证明；R<=3Q 已经失效；存在完整 W0 witness

- **取代 claim：** CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED

- **权威源：** docs/research/w0_front_aware_20260803/CONSULT_VERDICT_TRIPLE_20260804.md

- **条件处置：** `conditional`
- **操作效果：** scope_boundary；constraint_strengthening
- **一般性：** `parameterized_family`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** adversarial_review；targeted_derivation

- **有效性事件：** `scope_correction`
- **受影响层：** proof_argument；research_strategy
- **判定依据：** counterexample；independent_recomputation
- **复用策略：** `unaffected_under_premises`
- **修复状态：** `revalidated`
- **时间作用域：** `universal_claim`

- **证据：** [docs/research/w0_front_aware_20260803/CONSULT_VERDICT_TRIPLE_20260804.md](<research/w0_front_aware_20260803/CONSULT_VERDICT_TRIPLE_20260804.md>)〔hidden-premise analysis and minimal repair boundary〕

<a id="claim-warehouse-bridge-exclusion-target-conditional"></a>

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

<a id="claim-witness-restricted-pole-domains-infeasible-full-domain-open"></a>

### witness 构造只排除了两个受限 pole 域，2,507 候选全域仍为 OPEN

- **Claim ID：** `CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN`
- **状态：** `current`
- **权威层：** `research_authority`
- **权威依据：** `research_authority`
- **表示角色：** `AUTHORITATIVE_CURRENT`
- **权威作用：** `negative_research_result`
- **更新时间：** `2026-08-11`

routing-aware witness 构造中，`primary_even_rows` 的 247 个 pole candidates 在 3.42 秒内 INFEASIBLE，`fallback_rows` 的 498 个 candidates 在 102.43 秒内 INFEASIBLE；首次开放当前 topology 全部 2,507 个合法 pole candidates 的 attempt 在 600 秒后为 UNKNOWN。三个 attempt 都没有 `geometry_ready` 输出，因此只排除两个启发式受限域，全域可行性和 whole-layout witness 仍未解决。

- **适用范围：** witness-construction；routing-aware-shelf-power；registered-pole-domains

- **成立前提：** INFEASIBLE 只作用于各 attempt 明示的 pole candidate domain；UNKNOWN 不提供可行或不可行结论；没有 geometry_ready 就不能进入独立 witness campaign

- **直接后果：** 247 与 498 域可以从同一 topology 的候选队列中排除；2,507 全域及其他 shelf topology 继续保持开放；后续 agent 必须在结果中写明 candidate-domain size

- **明确不推出：** 当前 topology 全域不可行；存在完整 routing/port witness；其他 pole 候选策略不可行；600 秒后继续搜索一定无效

- **依赖 claim：** CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT；CLAIM-CERTIFIED-EXISTENCE-OPEN

- **权威源：** docs/research/witness_constructor_20260717/07_routing_aware/07_construction_log_20260720.md

- **条件处置：** `conditional`
- **操作效果：** candidate_pruning；scope_boundary；experiment_boundary
- **一般性：** `frozen_instance`
- **solver 关系：** `candidate_filter`
- **通用传播不能完成分离的证据：** `none`
- **发现方式：** solver_experiment；adversarial_review

- **目标阶段：** `candidate_generation`
- **候选来源：** `explicit_finite`
- **选择方式：** manual_targeting；finite_enumeration
- **验证方式：** terminal_replay
- **完备性：** `relative_to_declared_fragment`
- **消费方式：** candidate_filter；diagnostic_only
- **基线比较：** `controlled`
- **分离注：** INFEASIBLE 结果只覆盖两个显式受限 candidate fragments；全 2,507 域的 terminal result 是 UNKNOWN。

- **有效性事件：** `scope_correction`
- **受影响层：** candidate_inventory；solver_runtime；experiment_design
- **判定依据：** controlled_experiment；independent_recomputation
- **复用策略：** `unaffected_under_premises`
- **修复状态：** `revalidated`
- **时间作用域：** `run_family`

- **证据：** [docs/research/witness_constructor_20260717/07_routing_aware/07_construction_log_20260720.md](<research/witness_constructor_20260717/07_routing_aware/07_construction_log_20260720.md>)〔restricted-domain INFEASIBLE and full-domain UNKNOWN attempt log〕

<a id="claim-zero-slack-audit-method"></a>

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


## Decision 详情

<a id="decision-b6-hold-20260803"></a>

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

<a id="decision-empty-rectangle-strict-20260805"></a>

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

<a id="decision-ledger-authority-interfaces-20260813"></a>

### 文档补丁链两接口点联合结论四条通过

- **Decision ID：** `DECISION-LEDGER-AUTHORITY-INTERFACES-20260813`
- **状态：** `current`
- **登记角色：** `non_authorizing=true`
- **权威作用：** `research_governance`
- **决定人：** `zhuran24`
- **决定日期：** `2026-08-13`
- **外部决定 ID：** `owner-ledger-authority-interfaces-20260813`
- **外部权威源：** `docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md`

owner 拍板通过三面防污染架构审计线与文档评审线的联合结论四条：①decisions.jsonl 为显式非权威 append-only（non_authorizing 声明＋指针必填＋checker 校验指针真源＋预留 ruling_event_id；档案面落地后翻转 GENERATED_PROJECTION 或退役，生成式镜像定为目标形态非现在）；②claims authority 准入＝knowledge checker 能且确实对当前树 tracked 机器真源核验承重字段，authority_basis 必填，历史执行收据封顶 research_authority，3 条超标条目降级；③表示标签字段名 representation_class（四类值，与 authority 正交，与 document_class 建映射），enum 扩类权留 redesign 档案面批；④四条全并进已交回 GPT Pro 的落地适配批不单开。操作文本＝交接文档附录（文档评审线持有，owner 点头后并入）。绿灯≠关门，不产生任何 release closure。

- **适用范围：** knowledge_ledger；authority_interfaces；document_governance

- **直接后果：** decisions.jsonl 显式非权威化并带指针校验；claims 增加 authority_basis 与 representation_class；R3/R4/SMM4 三条 machine 条目降级 research_authority

- **明确不推出：** decisions.jsonl 可独立承载 owner authority；任何数学结论的 authority 等级被本决定改变；任何 release closure

- **证据：** [docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md](<history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md>)〔owner 拍板的落地时字节保真归档（roadmap 文末；sha256 38a5a752342d96e29542f466f3099a9668d4a6b60b04c792265cb539e04f8415）〕；[docs/项目说明/HISTORY.md](<项目说明/HISTORY.md>)〔编年史事件登记〕

<a id="decision-outer-loop-review-registration-20260815"></a>

### 推理外环评审归档与约束登记许可

- **Decision ID：** `DECISION-OUTER-LOOP-REVIEW-REGISTRATION-20260815`
- **状态：** `current`
- **登记角色：** `non_authorizing=true`
- **权威作用：** `research_governance`
- **决定人：** `zhuran24`
- **决定日期：** `2026-08-15`
- **外部决定 ID：** `owner-outer-loop-review-registration-20260815`
- **外部权威源：** `docs/research/solver_reasoning_outer_loop_reviews_20260815/OWNER_INSTRUCTION_20260815.md`

owner 允许归档三轮外部评审并以 non_authorizing 形态登记设计约束。

- **适用范围：** solver-reasoning-outer-loop；external-review-archive；design-constraint-registration

- **直接后果：** 允许三轮外部评审进入 tracked 逐字归档；允许以 non_authorizing 形态登记条件式设计约束

- **明确不推出：** 原登记八条内容及本次评审修复新增的指针型登记项获得批准；推理外环获得立项；对现行树新增义务

- **证据：** [docs/research/solver_reasoning_outer_loop_reviews_20260815/OWNER_INSTRUCTION_20260815.md](<research/solver_reasoning_outer_loop_reviews_20260815/OWNER_INSTRUCTION_20260815.md>)〔owner 登记许可的窄逐字存录与 authority source〕；[/home/zhuran24/.claude/projects/-home-zhuran24-zmd-pj/3aff26c7-fc81-4e12-8561-b144140f6db2.jsonl](<../../.claude/projects/-home-zhuran24-zmd-pj/3aff26c7-fc81-4e12-8561-b144140f6db2.jsonl>)〔owner 口述指令的仓外原始会话转录〕（仓外可选证据）；[docs/项目说明/HISTORY.md](<项目说明/HISTORY.md>)〔登记许可的 append-only 编年史投影〕；[docs/research/solver_reasoning_outer_loop_reviews_20260815/README.md](<research/solver_reasoning_outer_loop_reviews_20260815/README.md>)〔登记许可所覆盖的 tracked dossier 入口〕

<a id="decision-p1-2-close-20260707"></a>

### P1.2 首次关闭并允许进入 P1.3

- **Decision ID：** `DECISION-P1-2-CLOSE-20260707`
- **状态：** `superseded`
- **登记角色：** `non_authorizing=true`
- **权威作用：** `phase_gate`
- **决定人：** `zhuran24`
- **决定日期：** `2026-07-07`
- **外部决定 ID：** `owner-p1-2-close-p1-3-open-20260707`
- **外部权威源：** `data/review_gates/phase_1_2_spike_close.json`

owner 首次手动关闭 P1.2 并允许 P1.3 entry。该决定后来因严格空地语义与 source identity 变化而失去当前效力，并被 2026-08-06 的 re-close 决定 supersede。

- **适用范围：** phase-gate；p1_2；p1_3-entry

- **直接后果：** P1.2 当时被 owner 手动关闭并允许进入 P1.3；该节点只作为 superseded 历史保留

- **明确不推出：** 该 2026-07-07 决定仍是当前 gate authority

- **证据：** [data/review_gates/phase_1_2_spike_close.json](<../data/review_gates/phase_1_2_spike_close.json>)〔informational history and supersede target〕；[docs/research/p1_2_v99_close_kernel_sealing.md](<research/p1_2_v99_close_kernel_sealing.md>)〔tracked close-kernel anchor〕

<a id="decision-p1-2-reclose-20260806"></a>

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

<a id="decision-rule-system-redesign-open-20260813"></a>

### rule_system_redesign_20260807 线允许立项

- **Decision ID：** `DECISION-RULE-SYSTEM-REDESIGN-OPEN-20260813`
- **状态：** `current`
- **登记角色：** `non_authorizing=true`
- **权威作用：** `research_governance`
- **决定人：** `zhuran24`
- **决定日期：** `2026-08-13`
- **外部决定 ID：** `owner-rule-system-redesign-open-20260813`
- **外部权威源：** `docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md`

owner 口头拍板（主线程 2026-08-13 当日登记）：rule_system_redesign_20260807 线获准开工。入批口径未指定（缺省候选＝FINAL_DESIGN 批序，批 0 零 freeze 流程批先行）；OWNER_DECISION_SUMMARY.md 八项送审决定未逐项裁定，仍逐项上桌。绿灯≠关门，不产生任何 release closure。

- **适用范围：** rule_system_redesign；research_line_opening

- **直接后果：** rule_system_redesign_20260807 线获准开工；入批口径与八项送审决定仍待 owner 逐项裁定

- **明确不推出：** 任何批次已获准执行的具体口径；OWNER_DECISION_SUMMARY 八项中的任何一项已被裁定；任何 release closure

- **证据：** [docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md](<history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md>)〔owner 口头拍板的落地时字节保真归档（roadmap 文末；sha256 38a5a752342d96e29542f466f3099a9668d4a6b60b04c792265cb539e04f8415）〕；[docs/项目说明/HISTORY.md](<项目说明/HISTORY.md>)〔编年史事件登记〕

<a id="decision-semantics-split-experiment-first-20260813"></a>

### semantics 拆分走先实验后拍板路线

- **Decision ID：** `DECISION-SEMANTICS-SPLIT-EXPERIMENT-FIRST-20260813`
- **状态：** `current`
- **登记角色：** `non_authorizing=true`
- **权威作用：** `research_governance`
- **决定人：** `zhuran24`
- **决定日期：** `2026-08-13`
- **外部决定 ID：** `owner-semantics-split-experiment-first-20260813`
- **外部权威源：** `docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md`

owner 拍板认可 semantics 拆分「先实验后拍板」路线（按 fen5 核签 §11 缺省推荐）：先落传递依赖根、实测一个 canonical 批的成本，再由 owner 决定拆/不拆/整文件 SHA 进依赖根；实验属已立项 rule_system_redesign 线批 C 范围。绿灯≠关门，不产生任何 release closure。

- **适用范围：** rule_system_redesign；semantics_split

- **直接后果：** semantics 拆分决定推迟到实验数据之后；实验归属 redesign 线批 C

- **明确不推出：** semantics 拆分方案已被选定；canonical 批成本已有实测；任何 release closure

- **证据：** [docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md](<history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/00_master_roadmap.md>)〔owner 拍板的落地时字节保真归档（roadmap 文末；sha256 38a5a752342d96e29542f466f3099a9668d4a6b60b04c792265cb539e04f8415）〕；[docs/项目说明/HISTORY.md](<项目说明/HISTORY.md>)〔编年史事件登记〕


## Backfill review 详情

<a id="review-20260811-ab16-arms-batch3"></a>

### REVIEW-20260811-AB16-ARMS-BATCH3

- **Dossier：** `DOSSIER-AB16-ARMS-20260802-DC229C4539`
- **状态 / 结果：** `current` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS；CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT；CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION
- **未决项：** 需要有机触发、预注册 baseline 和完整 reachability funnel 的新实验。

复核 16/16 budget-censored 与 generated/compiled/applied 0/0/0 funnel；材料支持非识别性边界和 telemetry 需求，不支持 cut 无效或 generic propagation 优越性。

<a id="review-20260811-b1-conditional-halo-batch2"></a>

### REVIEW-20260811-B1-CONDITIONAL-HALO-BATCH2

- **Dossier：** `DOSSIER-B1-CONDITIONAL-HALO-20260722-0D968A299D`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-B1-CEILING-EXACT-NINE-POLES；CLAIM-B1-CONDITIONAL-HALO-CAPACITY-6650
- **未决项：** 该不等式在已跑 512-case corpus 中没有分离 control/treatment；其在其他候选族中的实际剪枝价值仍未量化。

提炼 all-selected-poles clipped halo 不等式，并把 actual-P ceiling 的“恰九杆”单独登记为派生 claim；同时保留 512 对 diagnostic 零增量 prune 的证据边界。

<a id="review-20260811-b1-qmh-batch2"></a>

### REVIEW-20260811-B1-QMH-BATCH2

- **Dossier：** `DOSSIER-B1-Q-MEMBRANE-HALO-20260722-D054906F9B`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-B1-QMH-REFINED-MEMBRANE-INEQUALITY
- **未决项：** 该必要式只排除 138 个 pattern-placement assignments，未改变当时 upper frontier。

提炼 Qδ 交叠、tangential endpoint 项与 membrane 账的安全合并公式，并把 direct Q-out 加法的 double-counting 边界写入 claim。

<a id="review-20260811-b1-r4-pb-batch2"></a>

### REVIEW-20260811-B1-R4-PB-BATCH2

- **Dossier：** `DOSSIER-B1-R4-1188-22-PB-20260723-FE5DFB853D`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-R4-LEX-BAND-2084-UNSAT
- **未决项：** —

把旧 (1188,22) research upper 的完整 2084-orientation proof-bearing closure 提升为可复用机器 claim。

<a id="review-20260811-band22-cleanroom-v0a-batch2"></a>

### REVIEW-20260811-BAND22-CLEANROOM-V0A-BATCH2

- **Dossier：** `DOSSIER-CLEANROOM-REDERIVATION-20260718-41375BBFE3`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE
- **未决项：** cleanroom_rederivation 其余子包未在本 review 中全量语义回填。

只审阅 cleanroom 巨型 dossier 中的 27 号 V0-A 交付件，并把后续 strict-hole disqualification 固定为 skeleton-level claim。

<a id="review-20260811-band22-strict-hole-probe-batch2"></a>

### REVIEW-20260811-BAND22-STRICT-HOLE-PROBE-BATCH2

- **Dossier：** `DOSSIER-BAND22-STRICT-HOLE-PROBE-20260805-B4EF0C65D3`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE；CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED；CLAIM-STRICT-HOLE-AVOIDS-X1-Y1
- **未决项：** k=1 单列活口只有必要账本，没有完整 placement/routing/power witness 或 strict checker 结果。

提炼 52=52 槽账、x=1/y=1 禁轨与固定 V0-A 的唯一孔位死亡；明确不把局部 48<49 子模型扩成 band 范式一般不可行。

<a id="review-20260811-batch-ce-attach-host"></a>

### REVIEW-20260811-BATCH-CE-ATTACH-HOST

- **Dossier：** `DOSSIER-BATCH-CE-ATTACH-HOST-20260712-D4A08ECB0B`
- **状态 / 结果：** `superseded` / `deferred`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** —
- **未决项：** 尚未逐轮提炼 attach-host 实验的可归因性能结论，也未确认该 dossier 是否应成为现有 production-status claim 的直接证据。

该包是 attach-host 历史证据线，但本批没有完成足以建立新领域推理 claim 的逐轮因果复核；production attach 的当前边界仍由独立 claim 与 authority 源承担。

<a id="review-20260811-batch-ce-attach-host-batch3"></a>

### REVIEW-20260811-BATCH-CE-ATTACH-HOST-BATCH3

- **Dossier：** `DOSSIER-BATCH-CE-ATTACH-HOST-20260712-D4A08ECB0B`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM
- **未决项：** 该 dossier 其余批 C/E 轮次尚未做完整性能因果回填。

把 prod-form fail-closed bug 与镜像修复提炼为 consumer-pipeline 边界：typed attach 能忠实消费已给 cut，但该包不证明 autonomous separation、效力或 production promotion。

<a id="review-20260811-canonical-batch-20260807"></a>

### REVIEW-20260811-CANONICAL-BATCH-20260807

- **Dossier：** `DOSSIER-CANONICAL-BATCH-20260807-B460BA9381`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT；CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE；CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT；CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT；CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE；CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE；CLAIM-MIXED-TERMINAL-TRIPARTITION；CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE
- **未决项：** 该 dossier 仍含其他规则条款，尚未做全量逐条 claim 化。

提炼 canonical freeze 中与领域约束选择、terminal semantics、model-stricter scope 和 rate lemma 直接相关的稳定 claim。

<a id="review-20260811-canonical-batch-20260808"></a>

### REVIEW-20260811-CANONICAL-BATCH-20260808

- **Dossier：** `DOSSIER-CANONICAL-BATCH-20260808-B2462129DF`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT；CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE；CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT；CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT；CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE；CLAIM-ADMISSION-PORT-OMISSION-SCOPE-RESTRICTION；CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE；CLAIM-MIXED-TERMINAL-TRIPARTITION；CLAIM-STORAGE-BOX-ACCEPTANCE-INVARIANT-FROZEN；CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE
- **未决项：** BLOCKERS 与 provenance 文档中的非承重细节尚未单独建 claim。

提炼 v3 精度修订、完整性扫描、admission-port 第六欠账、storage-box instance discharge 与 loader 前提集。

<a id="review-20260811-column-generation-phase2-batch4"></a>

### REVIEW-20260811-COLUMN-GENERATION-PHASE2-BATCH4

- **Dossier：** `DOSSIER-CAND-C-COLUMN-GENERATION-PHASE2-20260521-9625F52BA3`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO
- **未决项：** 不同 bootstrap、pricing、branching 或 reconstruction 设计仍未被该 verdict 排除。

把 Phase 2 从 5 到 266 instance 的 ramp verdict 压缩为设计版本级 NO-GO，同时保留 mini-ramp 与一般 column-generation 范式的边界。

<a id="review-20260811-f7-round1-batch4"></a>

### REVIEW-20260811-F7-ROUND1-BATCH4

- **Dossier：** `DOSSIER-P1-2B-F7-POWER-HITTING-SET-GEMINI-ROUND1-20260525-DB49AFB525`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-F7-FACILITY-MASK-VALIDATOR-BUG-REPAIRED
- **未决项：** 其他 defer 项仍属于当时 Phase 1.5+ 路线，不由本 claim 关闭。

登记 Round 1 的 facility-mask replay 误杀 blocker，保留外审发现与后续本地裁决之间的边界。

<a id="review-20260811-f7-round2-batch4"></a>

### REVIEW-20260811-F7-ROUND2-BATCH4

- **Dossier：** `DOSSIER-P1-2B-F7-POWER-HITTING-SET-GEMINI-ROUND2-20260525-C4D8B4A483`
- **状态 / 结果：** `current` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-F7-FACILITY-MASK-VALIDATOR-BUG-REPAIRED
- **未决项：** active_assumptions 等 defer 项未由本历史 repair claim 处理。

确认 R1 mask 修复跨 validator/oracle 一致，并记录 Round 2 其他 finding 仍需本地语义裁决而不能自动采信。

<a id="review-20260811-front-offset-artifact-batch4"></a>

### REVIEW-20260811-FRONT-OFFSET-ARTIFACT-BATCH4

- **Dossier：** `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-2B25E2B21B`
- **状态 / 结果：** `current` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED；CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED
- **未决项：** artifact payload 需在具备本地证据卷的环境中做逐文件 hash 重放。

本地 incident receipts 作为历史重判与 R1 proof replay 的可选证据根登记；轻量 checkout 缺失时不冒充可本机复验。

<a id="review-20260811-front-offset-incident"></a>

### REVIEW-20260811-FRONT-OFFSET-INCIDENT

- **Dossier：** `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-7F16095D41`
- **状态 / 结果：** `superseded` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED
- **未决项：** 逐项复验结果仍保留在历史 dossier，不在本批展开为独立 claim。

确认语义事故、历史重判边界和后续复验要求已由一个稳定 validity claim 覆盖。

<a id="review-20260811-front-offset-incident-batch4"></a>

### REVIEW-20260811-FRONT-OFFSET-INCIDENT-BATCH4

- **Dossier：** `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-7F16095D41`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED；CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED；CLAIM-FRONT-OFFSET-HISTORICAL-REJUDGMENT-40；CLAIM-SHARED-ENCODING-AGREEMENT-NOT-INDEPENDENT-VALIDATION；CLAIM-ROUND45-CORRECTED-PROFILE-UNKNOWN-NOT-STRUCTURAL-WALL；CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED
- **未决项：** 其余需重验 finding 尚未全部提升为稳定 claim；RAB/FCL 与 witness 的新 revision 仍应按各自作用域登记。

把 front 事故拆成旧语义、40 条逐项三态 ledger、共模验证教训、修正模型下的预算内 UNKNOWN 边界与一条恢复的 R1 上界；局部 revalidation 不再被用来追认事故前全称结论。

<a id="review-20260811-history-toolchain-origin-batch3"></a>

### REVIEW-20260811-HISTORY-TOOLCHAIN-ORIGIN-BATCH3

- **Dossier：** `DOSSIER-HISTORY-TOOLCHAIN-ORIGIN-20260709-411160EC29`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS；CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM
- **未决项：** 考古包中的外部 memory 引用并非全部 vendored，不能独立承担当前 authority。

把“换 cut 语言而非换 solver”、oracle/validator 分工和专用 cut consumer 的起源边界接入当前知识账本。

<a id="review-20260811-ihs-phase0-batch4"></a>

### REVIEW-20260811-IHS-PHASE0-BATCH4

- **Dossier：** `DOSSIER-LEVER25-IHS-PHASE0-20260520-4194EBD09A`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-IHS-SINGLETON-CORE-COMPRESSION-PHASE0-NO-GO
- **未决项：** 能产生共享 literals 的 generalized core source 尚未设计或验证。

登记十个 singleton routing cores 与 compression=1.0 的 Phase 0 NO-GO，不把该 core source 的失败外推成 IHS 一般不可能。

<a id="review-20260811-lazy-power-phase0-batch4"></a>

### REVIEW-20260811-LAZY-POWER-PHASE0-BATCH4

- **Dossier：** `DOSSIER-PHASE0-LAZY-POWER-COMPLETION-20260517-2DD76729CA`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-LAZY-POWER-INSTANCE-POSE-CUT-ROUTE-NO-GO
- **未决项：** 几何位置级 cut、pose-bool master 与其他 lazy-completion 语言仍是未验证的新设计。

提炼 master 去 coverage 后变快、completion 失败、220-pose cut 停滞以及 6-literal core 仍不收敛的完整 Phase 0 路线边界。

<a id="review-20260811-m5-convergence-batch4"></a>

### REVIEW-20260811-M5-CONVERGENCE-BATCH4

- **Dossier：** `DOSSIER-P1-3-M5-CONVERGENCE-20260708-A96D060024`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-M5-DEFAULT-SOLVE-PARAMETERS-PATHOLOGICAL-REFUTED；CLAIM-M5-DEATHS-REQUIRE-RESOURCE-BUILD-AND-PARAMETER-SEPARATION
- **未决项：** wall 税的 production wrapper 优化优先级仍属 owner roadmap。

将旧参数病态归因与修正后的资源/build/参数三分法接成显式反驳和归因更正链。

<a id="review-20260811-mixflow-fixture-correction-batch4"></a>

### REVIEW-20260811-MIXFLOW-FIXTURE-CORRECTION-BATCH4

- **Dossier：** `DOSSIER-MIXFLOW-DEMIX-BAN-20260807-FFEA2B3CE4`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-MIXFLOW-U01-GUARD-FORK-BENEFIT-REFUTED；CLAIM-MIXFLOW-DEMIX-CONCLUSION-SURVIVES-FIXTURE-CORRECTION
- **未决项：** 忠实 fixture 的 TIMEOUT 仍是非识别性结果。

把不忠实 fixture 导致的假红利与仍然同向的 demix 主对照拆开，保留更正边界而不静默覆盖旧证据。

<a id="review-20260811-noncert-cuts-ab16"></a>

### REVIEW-20260811-NONCERT-CUTS-AB16

- **Dossier：** `DOSSIER-NONCERT-CUTS-AB16-20260724-826CF39625`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS；CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT
- **未决项：** 需要新实验合同才能区分候选暴露、cap 口径与 cut 本体效果。

把 production authority 边界与“当前实验没有可归因科学结论”分成两条 claim，避免零激活被误写成 cut 无效或 generic propagation 足够。

<a id="review-20260811-p1-2-v99-close-kernel"></a>

### REVIEW-20260811-P1-2-V99-CLOSE-KERNEL

- **Dossier：** `DOSSIER-P1-2-V99-CLOSE-KERNEL-SEALING-207F650E44`
- **状态 / 结果：** `current` / `deferred`
- **审阅日 / 范围：** `2026-08-11` / `full_dossier`
- **提炼 claim：** —
- **未决项：** 需在 production proof-chain 专题中评估是否还应提炼非 decision 型 claim。

该文件是 production close-kernel 与 phase-gate 承重证据，不属于本批领域推理回填；现有 decision ledger 已保留其 gate 作用。

<a id="review-20260811-p1-3a-attach-power-on-batch3"></a>

### REVIEW-20260811-P1-3A-ATTACH-POWER-ON-BATCH3

- **Dossier：** `DOSSIER-P1-3A-ATTACH-POWER-ON-SPIKE-20260710-25E1F679CB`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY
- **未决项：** —

确认约 10K synthetic redundant F5 的通电 GO 只覆盖 master 写入与 overhead，真实 pool evolution、科学效力和 owner promotion 仍在边界外。

<a id="review-20260811-p1-3a-attach-sizing-batch3"></a>

### REVIEW-20260811-P1-3A-ATTACH-SIZING-BATCH3

- **Dossier：** `DOSSIER-P1-3A-ATTACH-SIZING-SPIKE-20260708-02F3C50E2F`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY
- **未决项：** —

提炼 sizing GO 的窄边界：增量 attach 形态和 active-cut 预算可工程化，不等于 P1.3 完成、收敛或 authority。

<a id="review-20260811-p2-area-bound"></a>

### REVIEW-20260811-P2-AREA-BOUND

- **Dossier：** `DOSSIER-P2-0-AREA-BOUND-20260806-6016501B5F`
- **状态 / 结果：** `superseded` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `full_dossier`
- **提炼 claim：** CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER
- **未决项：** 报告内分项不等式尚未全部拆成单独 claim。

确认 A≤1167 与条件界 A≤1015 已被独立 P2.0 research ledger 覆盖，且不会越界进入 six-predicate certified claim。

<a id="review-20260811-p2-area-bound-batch2"></a>

### REVIEW-20260811-P2-AREA-BOUND-BATCH2

- **Dossier：** `DOSSIER-P2-0-AREA-BOUND-20260806-6016501B5F`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `full_dossier`
- **提炼 claim：** CLAIM-P2-AREA-ACCOUNTING-1356；CLAIM-P2-AREA-BOUND-1167；CLAIM-P2-MIN-SIDE-UPPER-OPEN；CLAIM-P2-ROUTE-FOOTPRINT-LOWER-153；CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305；CLAIM-P2-ROUTED-FLOW-LOWER-9135；CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015；CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER；CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE
- **未决项：** OB6 的布局无关交叉格上界仍开放；被反例推翻的 L≥308 front-state 路线留待负结果专题系统回填。

把 P2.0 的格位分账、聚合流量、route-state、双层 footprint、无条件 1167、条件 1015、共享 P≥9，以及 max_lex 的 min_side 次坐标开放义务拆成可下钻 proof graph；聚合 ledger 只保留总览。

<a id="review-20260811-p2-specialized"></a>

### REVIEW-20260811-P2-SPECIALIZED

- **Dossier：** `DOSSIER-P2-0-SPECIALIZED-20260807-C40266E222`
- **状态 / 结果：** `superseded` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER；CLAIM-P2-BUCKWHEAT-SANDLEAF-MANDATORY-BRANCH；CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL；CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED
- **未决项：** 阶梯 allocation 与更多商品分流结果尚未逐条结构化。

确认特化推理、条件结论与反例已经分开登记；错误均摊占空不会继续伪装成无条件规律。

<a id="review-20260811-p2-specialized-batch4"></a>

### REVIEW-20260811-P2-SPECIALIZED-BATCH4

- **Dossier：** `DOSSIER-P2-0-SPECIALIZED-20260807-C40266E222`
- **状态 / 结果：** `current` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER；CLAIM-P2-BUCKWHEAT-SANDLEAF-MANDATORY-BRANCH；CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL；CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED
- **未决项：** 阶梯 allocation 与更多商品分流结果仍待逐条结构化。

将 steel-block 17<18 旧结论与 5 满 1 半条件修正版接成显式 supersede 链，避免“反例”和“替代命题”只靠标题暗示。

<a id="review-20260811-paradigm-lever-history-batch4"></a>

### REVIEW-20260811-PARADIGM-LEVER-HISTORY-BATCH4

- **Dossier：** `DOSSIER-PARADIGM-SEARCH-REVIEW-V12-WITH-CODE-20260520-FC02CE09A5`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-24-LEVER-FRAMEWORK-EXHAUSTED-SUPERSEDED；CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED
- **未决项：** 24 项 lever 的逐条有效性尚未全部映射为独立 claim。

把被污染的“范式已穷尽”全称结论降为历史，并保留可复用的 item/revision-bound 路线淘汰纪律。

<a id="review-20260811-r3-upper-bound-pb-batch2"></a>

### REVIEW-20260811-R3-UPPER-BOUND-PB-BATCH2

- **Dossier：** `DOSSIER-R3-UPPER-BOUND-PB-20260722-60ED8947CD`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-BODY-ACCESS-BUDGET-1320；CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48；CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE；CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY
- **未决项：** R3 PB 只机器验证给定几何引理后的算术层，几何 proof roots 仍在其他 dossier。

提炼 R3 的 shared membrane/power/budget 前件与历史 2074-orientation proof-bearing arithmetic closure。

<a id="review-20260811-r4-response-batch2"></a>

### REVIEW-20260811-R4-RESPONSE-BATCH2

- **Dossier：** `DOSSIER-R4-RESPONSE-REVIEW-20260723-D8EBC0DB9D`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-BODY-ACCESS-BUDGET-1320；CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48；CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE；CLAIM-R4-BOUNDARY-23-23-FULL-SPAN-EXCLUSION；CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4；CLAIM-R4-MARKED-INCIDENCE-TOTAL-110；CLAIM-R4-MARKED-MEMBRANE-BOUND-S12；CLAIM-R4-NECESSARY-DIMENSION-INEQUALITY
- **未决项：** 该 dossier 的 authority 只到 admitted-for-encoder-design；正式 2084-band UNSAT 由后续 B1 PB dossier 单独承担。

把 R4 response 中的普通膜、110 marks、S+12 marked membrane、t+m≤4、23+23 full-span 与尺寸必要式拆成可复用结构引理。

<a id="review-20260811-rab-sep-promotion-batch3"></a>

### REVIEW-20260811-RAB-SEP-PROMOTION-BATCH3

- **Dossier：** `DOSSIER-RAB-SEP-PROMOTION-20260716-CF6D536C85`
- **状态 / 结果：** `superseded` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION
- **未决项：** RAB 其余 soundness、promotion 与 incident 子文档留给 batch4 历史负结果专题。

只保留可复用的 telemetry 原则：raw eligible events 与 stage reachability 必须先于 accepted-cut 结论；旧 RAB 效果数字继续受 front-offset 事故失效标记约束。

<a id="review-20260811-rab-sep-promotion-batch4"></a>

### REVIEW-20260811-RAB-SEP-PROMOTION-BATCH4

- **Dossier：** `DOSSIER-RAB-SEP-PROMOTION-20260716-CF6D536C85`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION；CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN
- **未决项：** corrected-front 下同配置 RAB OFF/ON 与 front-clear lift 对照尚未形成可复核替代账本。；旧 package 中其余与 front 无关的工程事实若要晋升为独立 claim，仍需逐项证据审阅。

完成 RAB/FCL 历史负结果专题：保留 raw-event 与 reachability 的方法资产，同时把旧 front 语义下的 cut 数、blocker/core 分布、收敛效果、长跑归因和路线排序显式撤回，禁止由历史 UNKNOWN 推出结构墙或传播不可能性。

<a id="review-20260811-rule-system-redesign"></a>

### REVIEW-20260811-RULE-SYSTEM-REDESIGN

- **Dossier：** `DOSSIER-RULE-SYSTEM-REDESIGN-20260807-9B23FA19D2`
- **状态 / 结果：** `superseded` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-ZERO-SLACK-AUDIT-METHOD；CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL
- **未决项：** 失败分类与 claim 形态设计仍可在文档治理专题中进一步提炼。

确认低余量发现法与条件式 5-full-1-half 结论已有稳定身份；设计稿本身不自动升级其他候选规则。

<a id="review-20260811-rule-system-redesign-batch3"></a>

### REVIEW-20260811-RULE-SYSTEM-REDESIGN-BATCH3

- **Dossier：** `DOSSIER-RULE-SYSTEM-REDESIGN-20260807-9B23FA19D2`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-ZERO-SLACK-AUDIT-METHOD；CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL；CLAIM-PAIRWISE-CLOSURE-INCOMPLETE；CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS；CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN；CLAIM-PROVED-PREMODEL-EXCLUSION-PERMITS-MODEL-OMISSION；CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT
- **未决项：** FINAL_DESIGN 的治理落地批次和 derived-rule registry 仍未实施。

在 batch1 的两条稳定结论上继续提炼 pairwise closure 反例、发现/验证边界、proof-backed model omission 与预算删失语义；不把设计稿未落地部分升级为生产架构。

<a id="review-20260811-rules-audit"></a>

### REVIEW-20260811-RULES-AUDIT

- **Dossier：** `DOSSIER-RULES-AUDIT-20260718-A447D60E10`
- **状态 / 结果：** `superseded` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-EMPTY-RECTANGLE-STRICT；CLAIM-WAREHOUSE-BRIDGE-EXCLUSION-TARGET-CONDITIONAL
- **未决项：** 其余 owner adjudication 尚未全量拆分为 claim。

保留 strict empty-rectangle authority，并把 warehouse bridge 从隐含模型选择提升为显式 target-conditional scope claim。

<a id="review-20260811-rules-audit-batch4"></a>

### REVIEW-20260811-RULES-AUDIT-BATCH4

- **Dossier：** `DOSSIER-RULES-AUDIT-20260718-A447D60E10`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-EMPTY-RECTANGLE-ROUTING-ALLOWED-SUPERSEDED；CLAIM-EMPTY-RECTANGLE-STRICT；CLAIM-STRICTER-FEASIBLE-SET-PRESERVES-NEGATIVE-NOT-POSITIVE；CLAIM-WAREHOUSE-BRIDGE-EXCLUSION-TARGET-CONDITIONAL
- **未决项：** 其余 owner adjudication 尚未全量拆分为 validity chain。

显式登记 loose 到 strict 的语义换代，并把“负结果方向安全、正向见证不安全”的可行集单调性从叙述提升为可查询 claim。

<a id="review-20260811-smm-fresh-authority"></a>

### REVIEW-20260811-SMM-FRESH-AUTHORITY

- **Dossier：** `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-20260727-EA260C6D6B`
- **状态 / 结果：** `superseded` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-SIX-PREDICATE-RESEARCH-LEDGER；CLAIM-SMM-209-EXCLUDES-22X54
- **未决项：** —

确认 fresh-authority 包已由现有 research upper ledger 与 SMM-209 claim 覆盖。

<a id="review-20260811-smm-fresh-authority-batch2"></a>

### REVIEW-20260811-SMM-FRESH-AUTHORITY-BATCH2

- **Dossier：** `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-20260727-EA260C6D6B`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-SIX-PREDICATE-RESEARCH-LEDGER；CLAIM-SMM-209-EXCLUDES-22X54；CLAIM-SMM4-LEX-BAND-COMPOSITION-2086
- **未决项：** —

把 old-2084 ⊔ delta-2 = candidate-2086 的组合闭包从 ledger 总览中拆出，并保留 detached receipt/closeout 才能授权更新的边界。

<a id="review-20260811-smm-strict"></a>

### REVIEW-20260811-SMM-STRICT

- **Dossier：** `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-STRICT-20260724-F275CFCFE2`
- **状态 / 结果：** `superseded` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-SMM-209-EXCLUDES-22X54
- **未决项：** 同目录其他辅助证明部件尚未拆为更细粒度方法 claim。

确认 22×54 / 54×22 排除的纸面证明、翻译检查与对抗判读已由稳定 claim 覆盖。

<a id="review-20260811-smm-strict-batch2"></a>

### REVIEW-20260811-SMM-STRICT-BATCH2

- **Dossier：** `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-STRICT-20260724-F275CFCFE2`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-SMM-209-EXCLUDES-22X54；CLAIM-SMM-COMBINED-CAP-209；CLAIM-SMM-ENDPOINT-TOP-EIGHT-BUDGET-19；CLAIM-SMM-MARKED-MEMBRANE-BOUND-85；CLAIM-SMM-OUTSIDE-ACCESS-LOWER-133
- **未决项：** —

把 SMM-209 拆成 endpoint top-eight=19、M_in≤85、T_in+M_in≤209、outside access≥133 与最终面积矛盾，避免结论继续作为不可下钻黑箱。

<a id="review-20260811-smt-mt-phase0-batch4"></a>

### REVIEW-20260811-SMT-MT-PHASE0-BATCH4

- **Dossier：** `DOSSIER-SMT-MT-OUTER-PRUNING-PHASE0-20260521-042BF3000C`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER
- **未决项：** 不同真实 proof-producing inner 能否提供更高 INFEASIBLE fuel 仍开放。

保留 Dummy-inner cheap gate 对数据结构性能的 GO，但把它的外推范围限制在 synthetic notification stream。

<a id="review-20260811-smt-mt-phase1-batch4"></a>

### REVIEW-20260811-SMT-MT-PHASE1-BATCH4

- **Dossier：** `DOSSIER-SMT-MT-OUTER-PRUNING-PHASE1-20260521-DF50598CC0`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER
- **未决项：** outer pruning 是否在更高 INFEASIBLE 产率的 inner 上达到有效比例仍未验证。

用真实 B1 inner 的 9/1,196 unique prune 与 outer UNPROVEN 关闭 synthetic GO 的 production-effect 外推。

<a id="review-20260811-solver-rethink-batch3"></a>

### REVIEW-20260811-SOLVER-RETHINK-BATCH3

- **Dossier：** `DOSSIER-SOLVER-RETHINK-20260808-47BE0A3C3A`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-FORWARD-COMPLETENESS-RELATIVE-TO-DECLARED-FRAGMENT；CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN；CLAIM-SOLVER-RETHINK-G03-LACKS-SEPARATION-ORACLE；CLAIM-SOLVER-RETHINK-PHASE1-OMITS-CONSTRUCTION-HALF；CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT
- **未决项：** 该 local-optional 包的 DECISION_PACKAGE、内部 refute 与成本估计未在本 review 全量逐项回填。

提炼未立线设计中可复用的完备性口径与两项能力边界：G-03 缺 separator、一期缺 construction half；所有 claim 都明确保留 proposal/historical scope。

<a id="review-20260811-w0-power-counterexample-batch4"></a>

### REVIEW-20260811-W0-POWER-COUNTEREXAMPLE-BATCH4

- **Dossier：** `DOSSIER-W0-FRONT-AWARE-20260803-425794297E`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `targeted_files`
- **提炼 claim：** CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED；CLAIM-W0-POWER-OBSTRUCTION-REQUIRES-DECLARED-HEIGHT-PURITY
- **未决项：** 纯装家族的收窄版不可行定理尚未在账本中重新证明。

把直接坐标反例、未被打穿的 R<=3Q、隐藏的模板纯度前提和最小修法分开登记，防止“证明错了”被过度外推。

<a id="review-20260811-witness-constructor"></a>

### REVIEW-20260811-WITNESS-CONSTRUCTOR

- **Dossier：** `DOSSIER-WITNESS-CONSTRUCTOR-20260717-5F04E123B3`
- **状态 / 结果：** `superseded` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-CERTIFIED-EXISTENCE-OPEN
- **未决项：** 候选构造启发式的可复用负结果尚未单独提炼。

确认当前 witness 线仍未登记成功 lower witness；UNKNOWN、截停与 master incumbent 不会被解释为 whole-layout existence。

<a id="review-20260811-witness-constructor-batch4"></a>

### REVIEW-20260811-WITNESS-CONSTRUCTOR-BATCH4

- **Dossier：** `DOSSIER-WITNESS-CONSTRUCTOR-20260717-5F04E123B3`
- **状态 / 结果：** `current` / `claims_promoted`
- **审阅日 / 范围：** `2026-08-11` / `entry_and_references`
- **提炼 claim：** CLAIM-CERTIFIED-EXISTENCE-OPEN；CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN
- **未决项：** 全 pole domain 与其他 shelf topology 尚无 geometry_ready 结果，routing-aware whole-layout witness 仍缺失。

把 247/498 pole fragments 的 INFEASIBLE 与 2,507 全域 UNKNOWN 分开登记，并继续保持 whole-layout existence OPEN。

<a id="review-20260812-ghost-strict-fix-batch5"></a>

### REVIEW-20260812-GHOST-STRICT-FIX-BATCH5

- **Dossier：** `DOSSIER-GHOST-STRICT-FIX-20260805-0FBA53DB19`
- **状态 / 结果：** `current` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-12` / `targeted_files`
- **提炼 claim：** CLAIM-EMPTY-RECTANGLE-STRICT
- **未决项：** M11 的第二次 occupancy digest 比较与 M12 的 owner 身份增量语义在该 mutation batch 中仍是预期 MISSED。；本 review 未把本地测试绿灯提升为新的 owner 或 production authority。

把 strict ghost 修复、逐通道 cut 抑制与 15 个 mutant 收据定位为严格空地语义的实现/重验证据；它们不替代 canonical 语义源或 owner re-close。

<a id="review-20260812-p2-refresh-batch5"></a>

### REVIEW-20260812-P2-REFRESH-BATCH5

- **Dossier：** `DOSSIER-P2-0-REFRESH-20260805-627C980F03`
- **状态 / 结果：** `current` / `existing_claims_confirmed`
- **审阅日 / 范围：** `2026-08-12` / `targeted_files`
- **提炼 claim：** CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER
- **未决项：** 本 review 没有逐份复跑本地脚本、receipt 与外部求解器交叉验证。；AREA_BOUND_UPGRADE_PLAN 是升格前计划，不得覆盖后续 tracked theorem report 的修订口径。

确认该 local-optional 根保存了 P2.0 面积界从目标义务到反例修正的本地收据；当前可引用结论仍以 tracked area-bound/specialized authority 与稳定 P2 ledger 为准。

<a id="review-20260812-smm4-local-authority-availability-batch5"></a>

### REVIEW-20260812-SMM4-LOCAL-AUTHORITY-AVAILABILITY-BATCH5

- **Dossier：** `DOSSIER-TRACK-B-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-2026-2C7C3FCD74`
- **状态 / 结果：** `current` / `deferred`
- **审阅日 / 范围：** `2026-08-12` / `availability_and_provenance`
- **提炼 claim：** CLAIM-SIX-PREDICATE-RESEARCH-LEDGER
- **未决项：** 需在拥有外部 root 的 checkout 中按 tracked hash/manifest 复核 payload 完整性。

轻量快照缺少该 external authority root；本轮只核对 registry、tracked authority report 与稳定 claim 的 provenance 连接，不声称读取或语义审阅了缺失 payload。

<a id="review-20260815-phase-minus1-local-evidence-mechanical-audit"></a>

### REVIEW-20260815-PHASE-MINUS1-LOCAL-EVIDENCE-MECHANICAL-AUDIT

- **Dossier：** `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-20260815-7FA2A0E225`
- **状态 / 结果：** `current` / `deferred`
- **审阅日 / 范围：** `2026-08-15` / `availability_and_provenance`
- **提炼 claim：** —
- **未决项：** 原始运行 payload 保持 local_optional；轻量 checkout 可以缺失，恢复或重跑须依照 tracked README 与 manifest。

事后机械审计核对了本机 evidence package 的内部 manifest、r1/r3 终止标记、r2 observer-effect 终止收据、r3 九份 layout receipt，以及三组 append-only journal 的路径、SHA-256 与完整行计数；本 review 不评估科学结论，也不提升 verdict 或 authority。

<a id="review-20260815-phase-minus1-v2-local-evidence-registration"></a>

### REVIEW-20260815-PHASE-MINUS1-V2-LOCAL-EVIDENCE-REGISTRATION

- **Dossier：** `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-V2-20260815-96E16B17C8`
- **状态 / 结果：** `current` / `deferred`
- **审阅日 / 范围：** `2026-08-15` / `availability_and_provenance`
- **提炼 claim：** —
- **未决项：** 高预算 v2 运行仍处于 active 状态；当前 portability anchor 是启动时 CORPUS_ADMISSION 收据，不是终态 evidence manifest。；原始 journals、logs 与 slice/deep receipts 保持 local_optional；轻量 checkout 可缺失。

登记审计核对了 Phase -1 v2 本机证据包的启动 admission 收据、RUN_ID 与两份有限域 P1 slice receipt；tracked 协议、corpus 与恢复入口只作为 portability 坐标。本 review 不评估运行中的科学结论，也不提升判词或 authority。

<a id="review-20260815-solver-reasoning-outer-loop-gpt-pro"></a>

### REVIEW-20260815-SOLVER-REASONING-OUTER-LOOP-GPT-PRO

- **Dossier：** `DOSSIER-SOLVER-REASONING-OUTER-LOOP-REVIEWS-20260815-D26B592E99`
- **状态 / 结果：** `current` / `deferred`
- **审阅日 / 范围：** `2026-08-15` / `targeted_files`
- **提炼 claim：** —
- **未决项：** 逐字归档与条件式约束登记是否在 typed closure 时拆成两个 dossier 尚未裁决。；语义可压缩性、接口可压缩性与构造可分解性仍是待实验的可证伪假设。

GPT Pro 浏览器只读审查复核了逐字归档身份、dossier intake、条件式约束转述、authority 指针与路线图衔接；本 review 不把评审内容提升为 claim。

## 维护命令

```bash
.venv/bin/python devtools/build_knowledge_docs.py --refresh-dossiers --write
.venv/bin/python devtools/check_knowledge_docs.py
```

refresh 只自动补目录和更新 `auto_indexed` 元数据，不会删除缺失的 local artifact 记录，
也不会覆盖 `curated` 条目的人工字段。
