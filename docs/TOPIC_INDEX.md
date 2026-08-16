# 稳定主题索引

> 本页由 `data/knowledge/topics.json` 自动生成；禁止手工修改。
> 账本审阅日：`2026-08-14`；源摘要：`sha256:a908dba4370e8a96fd7058f3a13cecbee70b8ce19acc9ea5930d5ba6f6715502`。

主题是读取路径，不是新的 authority。一个 claim 可以出现在多个主题中；topic membership 只表示相关性，不改变 statement、scope 或 status。

## 总览

| Topic | 摘要 | Claims | Dossier labels | Open |
|---|---|---:|---|---:|
| [`TOPIC-AUTHORITY-AND-CURRENT-STATE`](#topic-authority-and-current-state) | 从 machine/owner authority、current ledger 与 OPEN 边界进入项目，不把证据存在误读为现态。 | 9 | p1_2-proof-chain | 1 |
| [`TOPIC-CERTIFIED-SCOPE-AND-SEMANTICS`](#topic-certified-scope-and-semantics) | 六谓词、严格空地、model-stricter face 与 terminal/routing 作用域的当前边界。 | 13 | rules-semantics | 0 |
| [`TOPIC-SIX-PREDICATE-UPPER-BOUND`](#topic-six-predicate-upper-bound) | R3/R4、membrane、zero-slack、SMM 与 SMM4 的结构引理、有限 band 与研究账本。 | 21 | upper-bound | 0 |
| [`TOPIC-P2-THROUGHPUT`](#topic-p2-throughput) | P2.0 第七谓词下的流量、route-state、面积界、条件界、反例与未闭 min_side。 | 11 | p2-throughput | 1 |
| [`TOPIC-SELECTION-SEPARATION-AND-CUTS`](#topic-selection-separation-and-cuts) | 区分候选发现、soundness 验证、主动 separation、模型前排除和 solver 消费，并保留 generic CP-SAT 不可能性仍 OPEN 的边界。 | 10 | cut-framework；separation-method；separation-telemetry；solver-architecture；solver-rethink | 1 |
| [`TOPIC-ROUTING-TERMINALS-AND-MIXFLOW`](#topic-routing-terminals-and-mixflow) | 物理 port、front/access、source/destination 排他、storage box、mixflow 与 front-offset 历史修正。 | 16 | rules-semantics；p2-throughput | 0 |
| [`TOPIC-WITNESS-AND-LOWER-BOUND`](#topic-witness-and-lower-bound) | whole-layout existence、受限候选域、W0 反例与局部构造证据的可复用边界。 | 5 | witness-lower-bound | 1 |
| [`TOPIC-SOLVER-EXPERIMENTS-AND-NO-GO`](#topic-solver-experiments-and-no-go) | 保留 cheap gate、fixture、资源/参数归因和路线撤回的具体 scope，避免方法家族级过度外推。 | 13 | solver-experiment | 0 |
| [`TOPIC-FORMAL-VERIFICATION`](#topic-formal-verification) | PB/VeriPB band、共享编码 common-mode 风险与 proof-producing sidecar 的证据坐标。 | 5 | formal-verification | 0 |
| [`TOPIC-DISCOVERY-METHODS`](#topic-discovery-methods) | zero-slack、pairwise closure 反例、独立验证与发现/验证拆分等可复用方法层。 | 5 | other；reasoning-system | 0 |
| [`TOPIC-HISTORICAL-VALIDITY`](#topic-historical-validity) | 统一查询 refutation、semantic replacement、scope correction、implementation/experiment invalidation、route retirement 与 revalid… | 32 | other | 0 |
| [`TOPIC-DOCUMENTATION-GOVERNANCE`](#topic-documentation-governance) | 文档类型、继承 policy、current review、长尾 triage、生成页和 framework-core 自维护入口。 | 0 | documentation-governance | 0 |
| [`TOPIC-INDUSTRIAL-DELIVERY`](#topic-industrial-delivery) | 把蓝图导出、manifest、local artifact 与 release authority 分开，供追溯而不抬升语义。 | 0 | industrial-delivery | 0 |

<a id="topic-authority-and-current-state"></a>
## 权威与当前状态

- **Topic ID：** `TOPIC-AUTHORITY-AND-CURRENT-STATE`
- **摘要：** 从 machine/owner authority、current ledger 与 OPEN 边界进入项目，不把证据存在误读为现态。
- **Dossier topic labels：** p1_2-proof-chain
- **术语坐标：** [`TERM-AUTHORITY`](<TERMINOLOGY.md#term-authority>)；[`TERM-EVIDENCE`](<TERMINOLOGY.md#term-evidence>)；[`TERM-CURRENT`](<TERMINOLOGY.md#term-current>)；[`TERM-CERTIFIED`](<TERMINOLOGY.md#term-certified>)；[`TERM-RESEARCH-UPPER-LEDGER`](<TERMINOLOGY.md#term-research-upper-ledger>)
- **入口：** [docs/CURRENT.md](<CURRENT.md>)；[docs/START_HERE.md](<START_HERE.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE`](<CATALOG.md#claim-band22-v0a-strict-hole-incompatible>) | `current` | 交付版 band22 V0-A 骨架与 strict hole 不相容 |
| [`CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE`](<CATALOG.md#claim-boundary-loader-excluded-frozen-instance>) | `current` | 冻结实例中 storage-side boundary loader 被 141>139 格数账排除 |
| [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](<CATALOG.md#claim-certified-existence-open>) | `open` | 现行语义下 whole-layout 认证级存在性仍为 OPEN |
| [`CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS`](<CATALOG.md#claim-cut-framework-production-status>) | `current` | cut framework 仍未获 production attach 授权 |
| [`CLAIM-DURABLE-CERTIFIED-RESULT-ABSENT`](<CATALOG.md#claim-durable-certified-result-absent>) | `current` | checked-in durable CERTIFIED 结果当前不存在 |
| [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814`](<CATALOG.md#claim-p2-throughput-research-ledger-20260814>) | `current` | P2.0 吞吐语义的独立条件账本 |
| [`CLAIM-R4-BOUNDARY-23-23-FULL-SPAN-EXCLUSION`](<CATALOG.md#claim-r4-boundary-23-23-full-span-exclusion>) | `current` | 46 个 boundary bodies 强制 23+23，并排除 70 格 full-span hole |
| [`CLAIM-R4-MARKED-INCIDENCE-TOTAL-110`](<CATALOG.md#claim-r4-marked-incidence-total-110>) | `current` | R4 marked-incidence census 的总数为 110 |
| [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](<CATALOG.md#claim-six-predicate-research-ledger>) | `current` | 六谓词 research ledger 为 U=(1188,18)、L=absent |

### Open questions

- [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](<CATALOG.md#claim-certified-existence-open>)

<a id="topic-certified-scope-and-semantics"></a>
## 认证作用域与规则语义

- **Topic ID：** `TOPIC-CERTIFIED-SCOPE-AND-SEMANTICS`
- **摘要：** 六谓词、严格空地、model-stricter face 与 terminal/routing 作用域的当前边界。
- **Dossier topic labels：** rules-semantics
- **术语坐标：** [`TERM-CERTIFIED`](<TERMINOLOGY.md#term-certified>)；[`TERM-STRICT-EMPTY-RECTANGLE`](<TERMINOLOGY.md#term-strict-empty-rectangle>)；[`TERM-BODY-EMPTY-RECTANGLE`](<TERMINOLOGY.md#term-body-empty-rectangle>)；[`TERM-PHYSICAL-PORT`](<TERMINOLOGY.md#term-physical-port>)；[`TERM-FRONT-CELL`](<TERMINOLOGY.md#term-front-cell>)
- **入口：** [PROJECT_LOCK.md](<../PROJECT_LOCK.md>)；[docs/项目说明/01_overview.md](<项目说明/01_overview.md>)；[rules/canonical_rules.json](<../rules/canonical_rules.json>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-ACTIVE-SCOPE-SINGLE-BASE`](<CATALOG.md#claim-active-scope-single-base>) | `current` | certified active scope 仅含单一 70×70 基地 |
| [`CLAIM-ADMISSION-PORT-OMISSION-SCOPE-RESTRICTION`](<CATALOG.md#claim-admission-port-omission-scope-restriction>) | `current` | 1×1 item admission port 的省略是显式认证作用域限制 |
| [`CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE`](<CATALOG.md#claim-binding-slot-single-commodity-scope>) | `current` | binding slot 单商品模型不能表达 wired warehouse 输入的多商品吸收 |
| [`CLAIM-CERTIFIED-THEOREM-SCOPE`](<CATALOG.md#claim-certified-theorem-scope>) | `current` | CERTIFIED 的命题边界是六谓词与 lex 最优 |
| [`CLAIM-CONNECTIVITY-QUANTIFIER-PER-COMMODITY-SOURCE-SINK`](<CATALOG.md#claim-connectivity-quantifier-per-commodity-source-sink>) | `current` | 游戏连通量词是逐 commodity 的双向 source/sink 可达 |
| [`CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE`](<CATALOG.md#claim-destination-front-exclusivity-terminal-sensitive>) | `current` | destination-front 单商品排他必须按接收终端类别解释 |
| [`CLAIM-EMPTY-RECTANGLE-MIN-SIDE-ADMISSIBILITY-SIX`](<CATALOG.md#claim-empty-rectangle-min-side-admissibility-six>) | `current` | 空矩形 admissibility 的最小边长为 6 |
| [`CLAIM-EMPTY-RECTANGLE-STRICT`](<CATALOG.md#claim-empty-rectangle-strict>) | `current` | 空矩形采用 no_occupant_of_any_kind 严格语义 |
| [`CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT`](<CATALOG.md#claim-model-stricter-faces-scope-debt>) | `current` | 六个 model-stricter face 是完整性与认证作用域欠账 |
| [`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT-BOUNDARY`](<CATALOG.md#claim-routing-reverification-extra-strict-boundary>) | `current` | routing reverification 的附加严格面不改写游戏连通量词 |
| [`CLAIM-SOLVER-RETHINK-PHASE1-OMITS-CONSTRUCTION-HALF`](<CATALOG.md#claim-solver-rethink-phase1-omits-construction-half>) | `historical` | solver-rethink 一期不覆盖 witness/下界构造半边 |
| [`CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT`](<CATALOG.md#claim-source-front-exclusivity-overstrict>) | `current` | source-front 单商品排他是已确认的过严模型面 |
| [`CLAIM-WAREHOUSE-BRIDGE-EXCLUSION-TARGET-CONDITIONAL`](<CATALOG.md#claim-warehouse-bridge-exclusion-target-conditional>) | `current` | warehouse bridge 排除只由冻结产量目标下的条件式生产线论证支撑 |

<a id="topic-six-predicate-upper-bound"></a>
## 六谓词上界与领域不等式

- **Topic ID：** `TOPIC-SIX-PREDICATE-UPPER-BOUND`
- **摘要：** R3/R4、membrane、zero-slack、SMM 与 SMM4 的结构引理、有限 band 与研究账本。
- **Dossier topic labels：** upper-bound
- **术语坐标：** [`TERM-RESEARCH-UPPER-LEDGER`](<TERMINOLOGY.md#term-research-upper-ledger>)；[`TERM-STRICT-EMPTY-RECTANGLE`](<TERMINOLOGY.md#term-strict-empty-rectangle>)；[`TERM-BODY-EMPTY-RECTANGLE`](<TERMINOLOGY.md#term-body-empty-rectangle>)
- **入口：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)；[docs/CURRENT.md](<CURRENT.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-B1-CEILING-EXACT-NINE-POLES`](<CATALOG.md#claim-b1-ceiling-exact-nine-poles>) | `current` | B1 ceiling survivor 若存在则恰用九根电杆 |
| [`CLAIM-B1-CONDITIONAL-HALO-CAPACITY-6650`](<CATALOG.md#claim-b1-conditional-halo-capacity-6650>) | `current` | B1-CH 对全部已选电杆给出 clipped halo 容量下界 6650 |
| [`CLAIM-B1-QMH-REFINED-MEMBRANE-INEQUALITY`](<CATALOG.md#claim-b1-qmh-refined-membrane-inequality>) | `current` | B1-QMH 用边界 Q 交叠与端点项细化 ordinary membrane |
| [`CLAIM-BODY-ACCESS-BUDGET-1320`](<CATALOG.md#claim-body-access-budget-1320>) | `current` | body-empty rectangle 与外部 access cells 共用 1320 格预算 |
| [`CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED`](<CATALOG.md#claim-boundary-generic-output-slots-saturated>) | `current` | generic output 槽账 52=52，46 个边界 raw 口全部被迫激活 |
| [`CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48`](<CATALOG.md#claim-ordinary-membrane-terminal-bound-s48>) | `current` | ordinary membrane 给出 T_in≤w+h+48 |
| [`CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE`](<CATALOG.md#claim-power-halo-pole-lower-bound-nine>) | `current` | 当前冻结实例至少需要九根电杆 |
| [`CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY`](<CATALOG.md#claim-r3-lex-band-2074-unsat-given-geometry>) | `historical` | 给定 R3 几何引理，2074 个 lex-better 尺寸的算术层为 UNSAT |
| [`CLAIM-R4-LEX-BAND-2084-UNSAT`](<CATALOG.md#claim-r4-lex-band-2084-unsat>) | `current` | 给定 A004 几何引理，lex>(1188,22) 的 2084-orientation band 为 UNSAT |
| [`CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4`](<CATALOG.md#claim-r4-local-weighted-access-capacity-4>) | `current` | R4 marked 账下每个外部 access cell 满足 t+m≤4 |
| [`CLAIM-R4-MARKED-MEMBRANE-BOUND-S12`](<CATALOG.md#claim-r4-marked-membrane-bound-s12>) | `current` | R4 marked membrane 对 normalized w≥9 给出 M_in≤S+12 |
| [`CLAIM-R4-NECESSARY-DIMENSION-INEQUALITY`](<CATALOG.md#claim-r4-necessary-dimension-inequality>) | `current` | R4 用 ordinary/marked 双账得到完整尺寸必要不等式 |
| [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](<CATALOG.md#claim-six-predicate-research-ledger>) | `current` | 六谓词 research ledger 为 U=(1188,18)、L=absent |
| [`CLAIM-SMM-209-EXCLUDES-22X54`](<CATALOG.md#claim-smm-209-excludes-22x54>) | `current` | SMM-209 排除 22×54 与 54×22 |
| [`CLAIM-SMM-COMBINED-CAP-209`](<CATALOG.md#claim-smm-combined-cap-209>) | `current` | SMM-209 给出 T_in+M_in≤209 |
| [`CLAIM-SMM-ENDPOINT-TOP-EIGHT-BUDGET-19`](<CATALOG.md#claim-smm-endpoint-top-eight-budget-19>) | `current` | SMM entity-max 的八端点 top-eight budget 为 19 |
| [`CLAIM-SMM-MARKED-MEMBRANE-BOUND-85`](<CATALOG.md#claim-smm-marked-membrane-bound-85>) | `current` | SMM 对 22×54 给出 M_in≤85 |
| [`CLAIM-SMM-OUTSIDE-ACCESS-LOWER-133`](<CATALOG.md#claim-smm-outside-access-lower-133>) | `current` | SMM-209 推出至少 133 个外部 access cells |
| [`CLAIM-SMM4-LEX-BAND-COMPOSITION-2086`](<CATALOG.md#claim-smm4-lex-band-composition-2086>) | `current` | SMM4 把旧 2084 band 与两个 SMM orientations 组合为完整 2086 band |
| [`CLAIM-STRICT-HOLE-AVOIDS-X1-Y1`](<CATALOG.md#claim-strict-hole-avoids-x1-y1>) | `current` | 严格空矩形不得触碰 x=1 列或 y=1 行 |
| [`CLAIM-ZERO-SLACK-AUDIT-METHOD`](<CATALOG.md#claim-zero-slack-audit-method>) | `current` | 低余量审计可系统寻找被迫结构与领域不等式 |

<a id="topic-p2-throughput"></a>
## P2.0 吞吐与面积账本

- **Topic ID：** `TOPIC-P2-THROUGHPUT`
- **摘要：** P2.0 第七谓词下的流量、route-state、面积界、条件界、反例与未闭 min_side。
- **Dossier topic labels：** p2-throughput
- **术语坐标：** [`TERM-RESEARCH-UPPER-LEDGER`](<TERMINOLOGY.md#term-research-upper-ledger>)；[`TERM-UNKNOWN`](<TERMINOLOGY.md#term-unknown>)；[`TERM-INFEASIBLE`](<TERMINOLOGY.md#term-infeasible>)
- **入口：** [docs/CURRENT.md](<CURRENT.md>)；[docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-P2-AREA-ACCOUNTING-1356`](<CATALOG.md#claim-p2-area-accounting-1356>) | `current` | P2.0 格位分账给出 A≤1356−4P−R |
| [`CLAIM-P2-AREA-BOUND-1167`](<CATALOG.md#claim-p2-area-bound-1167>) | `current` | P2.0 无条件容量计数面积上界为 A≤1167 |
| [`CLAIM-P2-BUCKWHEAT-SANDLEAF-MANDATORY-BRANCH`](<CATALOG.md#claim-p2-buckwheat-sandleaf-mandatory-branch>) | `current` | P2.0 当前实例中荞麦与砂叶分支不可消除 |
| [`CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL`](<CATALOG.md#claim-p2-five-full-one-half-conditional>) | `current` | 钢块免分流前提下，六台制瓶机被迫为 5 满 1 半 |
| [`CLAIM-P2-MIN-SIDE-UPPER-OPEN`](<CATALOG.md#claim-p2-min-side-upper-open>) | `open` | P2.0 的 min_side 上界仍未建立 |
| [`CLAIM-P2-ROUTE-FOOTPRINT-LOWER-153`](<CATALOG.md#claim-p2-route-footprint-lower-153>) | `current` | P2.0 route footprint 满足 R≥153 |
| [`CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305`](<CATALOG.md#claim-p2-route-state-lower-bound-305>) | `current` | P2.0 route-state 数至少为 305 |
| [`CLAIM-P2-ROUTED-FLOW-LOWER-9135`](<CATALOG.md#claim-p2-routed-flow-lower-9135>) | `current` | P2.0 进入路由图的聚合流量至少为 9135 件/分钟 |
| [`CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015`](<CATALOG.md#claim-p2-single-layer-area-bound-1015>) | `current` | P2.0 单层口径条件式面积上界为 A≤1015 |
| [`CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED`](<CATALOG.md#claim-p2-steel-block-17-lt-18-refuted>) | `refuted` | “steel_block 17<18 因而必分流”已被反例推翻 |
| [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814`](<CATALOG.md#claim-p2-throughput-research-ledger-20260814>) | `current` | P2.0 吞吐语义的独立条件账本 |

### Open questions

- [`CLAIM-P2-MIN-SIDE-UPPER-OPEN`](<CATALOG.md#claim-p2-min-side-upper-open>)

<a id="topic-selection-separation-and-cuts"></a>
## 选择、分离、验证与 cut 消费

- **Topic ID：** `TOPIC-SELECTION-SEPARATION-AND-CUTS`
- **摘要：** 区分候选发现、soundness 验证、主动 separation、模型前排除和 solver 消费，并保留 generic CP-SAT 不可能性仍 OPEN 的边界。
- **Dossier topic labels：** cut-framework；separation-method；separation-telemetry；solver-architecture；solver-rethink
- **术语坐标：** [`TERM-CANDIDATE-DISCOVERY`](<TERMINOLOGY.md#term-candidate-discovery>)；[`TERM-CANDIDATE-VALIDATION`](<TERMINOLOGY.md#term-candidate-validation>)；[`TERM-SEPARATION`](<TERMINOLOGY.md#term-separation>)；[`TERM-SOLVER-CONSUMPTION`](<TERMINOLOGY.md#term-solver-consumption>)；[`TERM-PREMODEL-EXCLUSION`](<TERMINOLOGY.md#term-premodel-exclusion>)；[`TERM-MODEL-OMISSION`](<TERMINOLOGY.md#term-model-omission>)；[`TERM-FIXED-POINT`](<TERMINOLOGY.md#term-fixed-point>)
- **入口：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-AB16-CAMPAIGN-CLOSEOUT-NO-ATTRIBUTABLE-CUT-RESULT`](<CATALOG.md#claim-ab16-campaign-closeout-no-attributable-cut-result>) | `current` | AB16 完整收官未形成可归因的 cut 科学结论 |
| [`CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY`](<CATALOG.md#claim-attach-spikes-engineering-not-cut-efficacy>) | `current` | attach spikes 只证明工程接线，不证明 cut 科学效力 |
| [`CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS`](<CATALOG.md#claim-cut-framework-production-status>) | `current` | cut framework 仍未获 production attach 授权 |
| [`CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS`](<CATALOG.md#claim-discovery-and-validation-separate-obligations>) | `current` | 候选发现与候选验证是两项独立能力 |
| [`CLAIM-FORWARD-COMPLETENESS-RELATIVE-TO-DECLARED-FRAGMENT`](<CATALOG.md#claim-forward-completeness-relative-to-declared-fragment>) | `current` | 前向完备性只能相对于声明片段定义 |
| [`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](<CATALOG.md#claim-generic-cp-sat-separation-impossibility-open>) | `open` | 通用 CP-SAT 传播不能替代领域分离的正式命题仍开放 |
| [`CLAIM-PAIRWISE-CLOSURE-INCOMPLETE`](<CATALOG.md#claim-pairwise-closure-incomplete>) | `current` | pairwise 固定点不能证明规则闭包已饱和 |
| [`CLAIM-PROVED-PREMODEL-EXCLUSION-PERMITS-MODEL-OMISSION`](<CATALOG.md#claim-proved-premodel-exclusion-permits-model-omission>) | `current` | 只有被证明的预建模排除才支持安全免建模 |
| [`CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`](<CATALOG.md#claim-raw-eligible-events-required-for-separation-evaluation>) | `current` | 分离实验必须记录 raw eligible events，不能只看 accepted cuts |
| [`CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM`](<CATALOG.md#claim-typed-cut-pipeline-consumes-known-cuts-not-discovers-them>) | `current` | typed cut 管道消费已知 cut，但不自动发现 cut |

### Open questions

- [`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](<CATALOG.md#claim-generic-cp-sat-separation-impossibility-open>)

<a id="topic-routing-terminals-and-mixflow"></a>
## 路由终端、front 与混流语义

- **Topic ID：** `TOPIC-ROUTING-TERMINALS-AND-MIXFLOW`
- **摘要：** 物理 port、front/access、source/destination 排他、storage box、mixflow 与 front-offset 历史修正。
- **Dossier topic labels：** rules-semantics；p2-throughput
- **术语坐标：** [`TERM-PHYSICAL-PORT`](<TERMINOLOGY.md#term-physical-port>)；[`TERM-FRONT-CELL`](<TERMINOLOGY.md#term-front-cell>)；[`TERM-HISTORICAL`](<TERMINOLOGY.md#term-historical>)；[`TERM-SUPERSEDED`](<TERMINOLOGY.md#term-superseded>)
- **入口：** [docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)；[docs/CURRENT.md](<CURRENT.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-ADMISSION-PORT-OMISSION-SCOPE-RESTRICTION`](<CATALOG.md#claim-admission-port-omission-scope-restriction>) | `current` | 1×1 item admission port 的省略是显式认证作用域限制 |
| [`CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE`](<CATALOG.md#claim-binding-slot-single-commodity-scope>) | `current` | binding slot 单商品模型不能表达 wired warehouse 输入的多商品吸收 |
| [`CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE`](<CATALOG.md#claim-destination-front-exclusivity-terminal-sensitive>) | `current` | destination-front 单商品排他必须按接收终端类别解释 |
| [`CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED`](<CATALOG.md#claim-front-offset-double-step-semantics-superseded>) | `superseded` | stored port 之后再沿方向前移一格的旧 front 解释已被替代 |
| [`CLAIM-FRONT-OFFSET-HISTORICAL-REJUDGMENT-40`](<CATALOG.md#claim-front-offset-historical-rejudgment-40>) | `current` | front offset 事故的 40 条历史 finding 已分为 16 作废、12 需重验、12 不受影响 |
| [`CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED`](<CATALOG.md#claim-front-offset-pre-0718-superseded>) | `current` | 依赖旧 front offset 解释的 2026-07-18 前结果须视为已撤回或待复验 |
| [`CLAIM-MIXED-TERMINAL-TRIPARTITION`](<CATALOG.md#claim-mixed-terminal-tripartition>) | `current` | 混流接收终端分为 core、storage box 与 machine input 三类 |
| [`CLAIM-MIXFLOW-DEMIX-CONCLUSION-SURVIVES-FIXTURE-CORRECTION`](<CATALOG.md#claim-mixflow-demix-conclusion-survives-fixture-correction>) | `historical` | mixflow demix 主对照在忠实 fixture 修正后保持同向 |
| [`CLAIM-MIXFLOW-U01-GUARD-FORK-BENEFIT-REFUTED`](<CATALOG.md#claim-mixflow-u01-guard-fork-benefit-refuted>) | `refuted` | U-01“守卫分叉带来可行性红利”的观测已由忠实 fixture 对照推翻 |
| [`CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN`](<CATALOG.md#claim-rab-fcl-front-dependent-performance-withdrawn>) | `current` | 旧 RAB/FCL 的 front-dependent 性能与收敛归因已撤回，复用前须按修正语义重验 |
| [`CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE`](<CATALOG.md#claim-rate-lemma-conditional-profile>) | `current` | intermediate pure-flow rate lemma 只覆盖等占空且最少车道的显式分配剖面 |
| [`CLAIM-ROUND45-CORRECTED-PROFILE-UNKNOWN-NOT-STRUCTURAL-WALL`](<CATALOG.md#claim-round45-corrected-profile-unknown-not-structural-wall>) | `current` | 修正后的 Round 4/5 紧凑模型只支持预算内 UNKNOWN，不支持结构墙 |
| [`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT-BOUNDARY`](<CATALOG.md#claim-routing-reverification-extra-strict-boundary>) | `current` | routing reverification 的附加严格面不改写游戏连通量词 |
| [`CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT`](<CATALOG.md#claim-source-front-exclusivity-overstrict>) | `current` | source-front 单商品排他是已确认的过严模型面 |
| [`CLAIM-STORAGE-BOX-ACCEPTANCE-INVARIANT-FROZEN`](<CATALOG.md#claim-storage-box-acceptance-invariant-frozen>) | `current` | frozen production line 单独履行了 protocol storage box 的逐次到达接受不变量 |
| [`CLAIM-WAREHOUSE-BRIDGE-EXCLUSION-TARGET-CONDITIONAL`](<CATALOG.md#claim-warehouse-bridge-exclusion-target-conditional>) | `current` | warehouse bridge 排除只由冻结产量目标下的条件式生产线论证支撑 |

<a id="topic-witness-and-lower-bound"></a>
## 见证构造与下界开放边界

- **Topic ID：** `TOPIC-WITNESS-AND-LOWER-BOUND`
- **摘要：** whole-layout existence、受限候选域、W0 反例与局部构造证据的可复用边界。
- **Dossier topic labels：** witness-lower-bound
- **术语坐标：** [`TERM-CERTIFIED`](<TERMINOLOGY.md#term-certified>)；[`TERM-UNKNOWN`](<TERMINOLOGY.md#term-unknown>)；[`TERM-INFEASIBLE`](<TERMINOLOGY.md#term-infeasible>)；[`TERM-ROUTE-NO-GO`](<TERMINOLOGY.md#term-route-no-go>)
- **入口：** [docs/CURRENT.md](<CURRENT.md>)；[docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](<CATALOG.md#claim-certified-existence-open>) | `open` | 现行语义下 whole-layout 认证级存在性仍为 OPEN |
| [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](<CATALOG.md#claim-six-predicate-research-ledger>) | `current` | 六谓词 research ledger 为 U=(1188,18)、L=absent |
| [`CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED`](<CATALOG.md#claim-w0-adjacent-4x4-power-impossibility-refuted>) | `refuted` | W0 相邻 4+4 宏族供电不可行定理已被坐标反例推翻 |
| [`CLAIM-W0-POWER-OBSTRUCTION-REQUIRES-DECLARED-HEIGHT-PURITY`](<CATALOG.md#claim-w0-power-obstruction-requires-declared-height-purity>) | `current` | W0 供电阻塞证明只能在明示的模板到带高纯装前提下复用 |
| [`CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN`](<CATALOG.md#claim-witness-restricted-pole-domains-infeasible-full-domain-open>) | `current` | witness 构造只排除了两个受限 pole 域，2,507 候选全域仍为 OPEN |

### Open questions

- [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](<CATALOG.md#claim-certified-existence-open>)

<a id="topic-solver-experiments-and-no-go"></a>
## 求解器实验、预算与路线 NO-GO

- **Topic ID：** `TOPIC-SOLVER-EXPERIMENTS-AND-NO-GO`
- **摘要：** 保留 cheap gate、fixture、资源/参数归因和路线撤回的具体 scope，避免方法家族级过度外推。
- **Dossier topic labels：** solver-experiment
- **术语坐标：** [`TERM-UNKNOWN`](<TERMINOLOGY.md#term-unknown>)；[`TERM-INFEASIBLE`](<TERMINOLOGY.md#term-infeasible>)；[`TERM-FIXED-POINT`](<TERMINOLOGY.md#term-fixed-point>)；[`TERM-ROUTE-NO-GO`](<TERMINOLOGY.md#term-route-no-go>)
- **入口：** [docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)；[docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-AB16-CAMPAIGN-CLOSEOUT-NO-ATTRIBUTABLE-CUT-RESULT`](<CATALOG.md#claim-ab16-campaign-closeout-no-attributable-cut-result>) | `current` | AB16 完整收官未形成可归因的 cut 科学结论 |
| [`CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY`](<CATALOG.md#claim-attach-spikes-engineering-not-cut-efficacy>) | `current` | attach spikes 只证明工程接线，不证明 cut 科学效力 |
| [`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](<CATALOG.md#claim-budget-exhaustion-is-unknown-not-fixed-point>) | `current` | 预算耗尽必须返回 UNKNOWN，不能冒充固定点 |
| [`CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO`](<CATALOG.md#claim-column-generation-phase2-scale-route-no-go>) | `historical` | Column Generation Phase 2 的登记设计未跨过规模与重构门槛 |
| [`CLAIM-FORWARD-COMPLETENESS-RELATIVE-TO-DECLARED-FRAGMENT`](<CATALOG.md#claim-forward-completeness-relative-to-declared-fragment>) | `current` | 前向完备性只能相对于声明片段定义 |
| [`CLAIM-IHS-SINGLETON-CORE-COMPRESSION-PHASE0-NO-GO`](<CATALOG.md#claim-ihs-singleton-core-compression-phase0-no-go>) | `historical` | IHS Phase 0 的 singleton core 源没有产生跨迭代压缩 |
| [`CLAIM-LAZY-POWER-INSTANCE-POSE-CUT-ROUTE-NO-GO`](<CATALOG.md#claim-lazy-power-instance-pose-cut-route-no-go>) | `historical` | Lazy Power Completion 的 instance×pose cut 路线在登记锚点触发 NO-GO |
| [`CLAIM-M5-DEATHS-REQUIRE-RESOURCE-BUILD-AND-PARAMETER-SEPARATION`](<CATALOG.md#claim-m5-deaths-require-resource-build-and-parameter-separation>) | `current` | M5 死亡归因必须分开资源尖峰、build 爆炸与 solve 参数 |
| [`CLAIM-M5-DEFAULT-SOLVE-PARAMETERS-PATHOLOGICAL-REFUTED`](<CATALOG.md#claim-m5-default-solve-parameters-pathological-refuted>) | `refuted` | M5“产品默认 solve 参数病态”归因已被受控 A/B 推翻 |
| [`CLAIM-MIXFLOW-DEMIX-CONCLUSION-SURVIVES-FIXTURE-CORRECTION`](<CATALOG.md#claim-mixflow-demix-conclusion-survives-fixture-correction>) | `historical` | mixflow demix 主对照在忠实 fixture 修正后保持同向 |
| [`CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER`](<CATALOG.md#claim-smt-mt-synthetic-go-not-transferable-to-real-inner>) | `current` | SMT-MT synthetic GO 不能替代真实 inner fuel 的有效性验证 |
| [`CLAIM-SOLVER-RETHINK-G03-LACKS-SEPARATION-ORACLE`](<CATALOG.md#claim-solver-rethink-g03-lacks-separation-oracle>) | `historical` | solver-rethink 的 G-03 只有 checker，缺自主 separator |
| [`CLAIM-SOLVER-RETHINK-PHASE1-OMITS-CONSTRUCTION-HALF`](<CATALOG.md#claim-solver-rethink-phase1-omits-construction-half>) | `historical` | solver-rethink 一期不覆盖 witness/下界构造半边 |

<a id="topic-formal-verification"></a>
## 形式化验证与独立复核

- **Topic ID：** `TOPIC-FORMAL-VERIFICATION`
- **摘要：** PB/VeriPB band、共享编码 common-mode 风险与 proof-producing sidecar 的证据坐标。
- **Dossier topic labels：** formal-verification
- **术语坐标：** [`TERM-EVIDENCE`](<TERMINOLOGY.md#term-evidence>)；[`TERM-CANDIDATE-VALIDATION`](<TERMINOLOGY.md#term-candidate-validation>)
- **入口：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)；[docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED`](<CATALOG.md#claim-r1-1326-34-strict-upper-revalidated>) | `historical` | R1 strict `(1326,34)` 上界已由两段证明链重新验证 |
| [`CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY`](<CATALOG.md#claim-r3-lex-band-2074-unsat-given-geometry>) | `historical` | 给定 R3 几何引理，2074 个 lex-better 尺寸的算术层为 UNSAT |
| [`CLAIM-R4-LEX-BAND-2084-UNSAT`](<CATALOG.md#claim-r4-lex-band-2084-unsat>) | `current` | 给定 A004 几何引理，lex>(1188,22) 的 2084-orientation band 为 UNSAT |
| [`CLAIM-SHARED-ENCODING-AGREEMENT-NOT-INDEPENDENT-VALIDATION`](<CATALOG.md#claim-shared-encoding-agreement-not-independent-validation>) | `current` | 共享坐标 helper 的 oracle 与 validator 一致不构成独立验证 |
| [`CLAIM-SMM4-LEX-BAND-COMPOSITION-2086`](<CATALOG.md#claim-smm4-lex-band-composition-2086>) | `current` | SMM4 把旧 2084 band 与两个 SMM orientations 组合为完整 2086 band |

<a id="topic-discovery-methods"></a>
## 系统发现与审计方法

- **Topic ID：** `TOPIC-DISCOVERY-METHODS`
- **摘要：** zero-slack、pairwise closure 反例、独立验证与发现/验证拆分等可复用方法层。
- **Dossier topic labels：** other；reasoning-system
- **术语坐标：** [`TERM-CANDIDATE-DISCOVERY`](<TERMINOLOGY.md#term-candidate-discovery>)；[`TERM-CANDIDATE-VALIDATION`](<TERMINOLOGY.md#term-candidate-validation>)；[`TERM-SEPARATION`](<TERMINOLOGY.md#term-separation>)；[`TERM-FIXED-POINT`](<TERMINOLOGY.md#term-fixed-point>)
- **入口：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-FORWARD-COMPLETENESS-RELATIVE-TO-DECLARED-FRAGMENT`](<CATALOG.md#claim-forward-completeness-relative-to-declared-fragment>) | `current` | 前向完备性只能相对于声明片段定义 |
| [`CLAIM-PAIRWISE-CLOSURE-INCOMPLETE`](<CATALOG.md#claim-pairwise-closure-incomplete>) | `current` | pairwise 固定点不能证明规则闭包已饱和 |
| [`CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`](<CATALOG.md#claim-raw-eligible-events-required-for-separation-evaluation>) | `current` | 分离实验必须记录 raw eligible events，不能只看 accepted cuts |
| [`CLAIM-SHARED-ENCODING-AGREEMENT-NOT-INDEPENDENT-VALIDATION`](<CATALOG.md#claim-shared-encoding-agreement-not-independent-validation>) | `current` | 共享坐标 helper 的 oracle 与 validator 一致不构成独立验证 |
| [`CLAIM-ZERO-SLACK-AUDIT-METHOD`](<CATALOG.md#claim-zero-slack-audit-method>) | `current` | 低余量审计可系统寻找被迫结构与领域不等式 |

<a id="topic-historical-validity"></a>
## 历史有效性、反例与换代

- **Topic ID：** `TOPIC-HISTORICAL-VALIDITY`
- **摘要：** 统一查询 refutation、semantic replacement、scope correction、implementation/experiment invalidation、route retirement 与 revalidation。
- **Dossier topic labels：** other
- **术语坐标：** [`TERM-HISTORICAL`](<TERMINOLOGY.md#term-historical>)；[`TERM-SUPERSEDED`](<TERMINOLOGY.md#term-superseded>)；[`TERM-ROUTE-NO-GO`](<TERMINOLOGY.md#term-route-no-go>)；[`TERM-UNKNOWN`](<TERMINOLOGY.md#term-unknown>)
- **入口：** [docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)

### Claims

| Claim | 状态 | 标题 |
|---|---|---|
| [`CLAIM-24-LEVER-FRAMEWORK-EXHAUSTED-SUPERSEDED`](<CATALOG.md#claim-24-lever-framework-exhausted-superseded>) | `superseded` | “24 lever 全 dead、范式已穷尽”的全称判断已撤回 |
| [`CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT`](<CATALOG.md#claim-ab16-no-scientific-cut-result>) | `superseded` | AB16 当前只形成实验边界，未形成可归因的 cut 科学结论 |
| [`CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO`](<CATALOG.md#claim-column-generation-phase2-scale-route-no-go>) | `historical` | Column Generation Phase 2 的登记设计未跨过规模与重构门槛 |
| [`CLAIM-EMPTY-RECTANGLE-ROUTING-ALLOWED-SUPERSEDED`](<CATALOG.md#claim-empty-rectangle-routing-allowed-superseded>) | `superseded` | 空矩形只禁设施、允许物流组件穿入的宽松解释已被替代 |
| [`CLAIM-EMPTY-RECTANGLE-STRICT`](<CATALOG.md#claim-empty-rectangle-strict>) | `current` | 空矩形采用 no_occupant_of_any_kind 严格语义 |
| [`CLAIM-F7-FACILITY-MASK-VALIDATOR-BUG-REPAIRED`](<CATALOG.md#claim-f7-facility-mask-validator-bug-repaired>) | `historical` | F7 validator 漏排 facility cells 的误杀缺陷已修复并复核 |
| [`CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED`](<CATALOG.md#claim-front-offset-double-step-semantics-superseded>) | `superseded` | stored port 之后再沿方向前移一格的旧 front 解释已被替代 |
| [`CLAIM-FRONT-OFFSET-HISTORICAL-REJUDGMENT-40`](<CATALOG.md#claim-front-offset-historical-rejudgment-40>) | `current` | front offset 事故的 40 条历史 finding 已分为 16 作废、12 需重验、12 不受影响 |
| [`CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED`](<CATALOG.md#claim-front-offset-pre-0718-superseded>) | `current` | 依赖旧 front offset 解释的 2026-07-18 前结果须视为已撤回或待复验 |
| [`CLAIM-IHS-SINGLETON-CORE-COMPRESSION-PHASE0-NO-GO`](<CATALOG.md#claim-ihs-singleton-core-compression-phase0-no-go>) | `historical` | IHS Phase 0 的 singleton core 源没有产生跨迭代压缩 |
| [`CLAIM-LAZY-POWER-INSTANCE-POSE-CUT-ROUTE-NO-GO`](<CATALOG.md#claim-lazy-power-instance-pose-cut-route-no-go>) | `historical` | Lazy Power Completion 的 instance×pose cut 路线在登记锚点触发 NO-GO |
| [`CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`](<CATALOG.md#claim-lever-verdicts-are-item-and-revision-bounded>) | `current` | lever verdict 只能按具体条目、修订和证据边界复用 |
| [`CLAIM-M5-DEATHS-REQUIRE-RESOURCE-BUILD-AND-PARAMETER-SEPARATION`](<CATALOG.md#claim-m5-deaths-require-resource-build-and-parameter-separation>) | `current` | M5 死亡归因必须分开资源尖峰、build 爆炸与 solve 参数 |
| [`CLAIM-M5-DEFAULT-SOLVE-PARAMETERS-PATHOLOGICAL-REFUTED`](<CATALOG.md#claim-m5-default-solve-parameters-pathological-refuted>) | `refuted` | M5“产品默认 solve 参数病态”归因已被受控 A/B 推翻 |
| [`CLAIM-MIXFLOW-DEMIX-CONCLUSION-SURVIVES-FIXTURE-CORRECTION`](<CATALOG.md#claim-mixflow-demix-conclusion-survives-fixture-correction>) | `historical` | mixflow demix 主对照在忠实 fixture 修正后保持同向 |
| [`CLAIM-MIXFLOW-U01-GUARD-FORK-BENEFIT-REFUTED`](<CATALOG.md#claim-mixflow-u01-guard-fork-benefit-refuted>) | `refuted` | U-01“守卫分叉带来可行性红利”的观测已由忠实 fixture 对照推翻 |
| [`CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL`](<CATALOG.md#claim-p2-five-full-one-half-conditional>) | `current` | 钢块免分流前提下，六台制瓶机被迫为 5 满 1 半 |
| [`CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED`](<CATALOG.md#claim-p2-steel-block-17-lt-18-refuted>) | `refuted` | “steel_block 17<18 因而必分流”已被反例推翻 |
| [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](<CATALOG.md#claim-p2-throughput-research-ledger>) | `superseded` | P2.0 吞吐语义另有 A≤1167 / A≤1015 条件账本 |
| [`CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED`](<CATALOG.md#claim-r1-1326-34-strict-upper-revalidated>) | `historical` | R1 strict `(1326,34)` 上界已由两段证明链重新验证 |
| [`CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY`](<CATALOG.md#claim-r3-lex-band-2074-unsat-given-geometry>) | `historical` | 给定 R3 几何引理，2074 个 lex-better 尺寸的算术层为 UNSAT |
| [`CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN`](<CATALOG.md#claim-rab-fcl-front-dependent-performance-withdrawn>) | `current` | 旧 RAB/FCL 的 front-dependent 性能与收敛归因已撤回，复用前须按修正语义重验 |
| [`CLAIM-ROUND45-CORRECTED-PROFILE-UNKNOWN-NOT-STRUCTURAL-WALL`](<CATALOG.md#claim-round45-corrected-profile-unknown-not-structural-wall>) | `current` | 修正后的 Round 4/5 紧凑模型只支持预算内 UNKNOWN，不支持结构墙 |
| [`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT`](<CATALOG.md#claim-routing-reverification-extra-strict>) | `superseded` | routing reverification 的 no-orphan 与 selected-source-reaches-sink 超出游戏连通量词 |
| [`CLAIM-SHARED-ENCODING-AGREEMENT-NOT-INDEPENDENT-VALIDATION`](<CATALOG.md#claim-shared-encoding-agreement-not-independent-validation>) | `current` | 共享坐标 helper 的 oracle 与 validator 一致不构成独立验证 |
| [`CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER`](<CATALOG.md#claim-smt-mt-synthetic-go-not-transferable-to-real-inner>) | `current` | SMT-MT synthetic GO 不能替代真实 inner fuel 的有效性验证 |
| [`CLAIM-SOLVER-RETHINK-G03-LACKS-SEPARATION-ORACLE`](<CATALOG.md#claim-solver-rethink-g03-lacks-separation-oracle>) | `historical` | solver-rethink 的 G-03 只有 checker，缺自主 separator |
| [`CLAIM-SOLVER-RETHINK-PHASE1-OMITS-CONSTRUCTION-HALF`](<CATALOG.md#claim-solver-rethink-phase1-omits-construction-half>) | `historical` | solver-rethink 一期不覆盖 witness/下界构造半边 |
| [`CLAIM-STRICTER-FEASIBLE-SET-PRESERVES-NEGATIVE-NOT-POSITIVE`](<CATALOG.md#claim-stricter-feasible-set-preserves-negative-not-positive>) | `current` | 可行集收紧保留负结果与上界，但不保留旧正向见证 |
| [`CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED`](<CATALOG.md#claim-w0-adjacent-4x4-power-impossibility-refuted>) | `refuted` | W0 相邻 4+4 宏族供电不可行定理已被坐标反例推翻 |
| [`CLAIM-W0-POWER-OBSTRUCTION-REQUIRES-DECLARED-HEIGHT-PURITY`](<CATALOG.md#claim-w0-power-obstruction-requires-declared-height-purity>) | `current` | W0 供电阻塞证明只能在明示的模板到带高纯装前提下复用 |
| [`CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN`](<CATALOG.md#claim-witness-restricted-pole-domains-infeasible-full-domain-open>) | `current` | witness 构造只排除了两个受限 pole 域，2,507 候选全域仍为 OPEN |

<a id="topic-documentation-governance"></a>
## 文档系统与知识维护

- **Topic ID：** `TOPIC-DOCUMENTATION-GOVERNANCE`
- **摘要：** 文档类型、继承 policy、current review、长尾 triage、生成页和 framework-core 自维护入口。
- **Dossier topic labels：** documentation-governance
- **术语坐标：** [`TERM-CLAIM`](<TERMINOLOGY.md#term-claim>)；[`TERM-DOSSIER`](<TERMINOLOGY.md#term-dossier>)；[`TERM-CURRENT-REVIEW`](<TERMINOLOGY.md#term-current-review>)；[`TERM-BACKFILL-TRIAGE`](<TERMINOLOGY.md#term-backfill-triage>)；[`TERM-SEMANTIC-REVIEW`](<TERMINOLOGY.md#term-semantic-review>)；[`TERM-INVENTORY-COVERAGE`](<TERMINOLOGY.md#term-inventory-coverage>)
- **入口：** [docs/governance/document-system/ARCHITECTURE.md](<governance/document-system/ARCHITECTURE.md>)；[docs/governance/document-system/MAINTAINING.md](<governance/document-system/MAINTAINING.md>)；[docs/BACKFILL_LEDGER.md](<BACKFILL_LEDGER.md>)

### Claims

该主题当前只提供文档/dossier 导航，没有单独登记 claim。

<a id="topic-industrial-delivery"></a>
## 交付、导出与工件边界

- **Topic ID：** `TOPIC-INDUSTRIAL-DELIVERY`
- **摘要：** 把蓝图导出、manifest、local artifact 与 release authority 分开，供追溯而不抬升语义。
- **Dossier topic labels：** industrial-delivery
- **术语坐标：** [`TERM-AUTHORITY`](<TERMINOLOGY.md#term-authority>)；[`TERM-EVIDENCE`](<TERMINOLOGY.md#term-evidence>)；[`TERM-DOSSIER`](<TERMINOLOGY.md#term-dossier>)
- **入口：** [.artifacts/README.md](<../.artifacts/README.md>)；[docs/CATALOG.md](<CATALOG.md>)

### Claims

该主题当前只提供文档/dossier 导航，没有单独登记 claim。

完整 claim 详情见 [CATALOG](<CATALOG.md>)；历史有效性见 [VALIDITY_LEDGER](<VALIDITY_LEDGER.md>)；长尾覆盖见 [BACKFILL_LEDGER](<BACKFILL_LEDGER.md>)。
