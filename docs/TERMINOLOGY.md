# 核心术语与禁止混同边界

> 本页由 `data/knowledge/terminology.json` 自动生成；禁止手工修改。
> 账本审阅日：`2026-08-12`；源摘要：`sha256:d3a53eaf9c14ee35ae69308449341b740dd64914f466e3ae57dd83e3088e1baa`。

术语表统一名称和类推边界，但不覆盖 canonical rules、claim statement 或 owner decision。别名只帮助检索，不表示两个更细概念在所有上下文中等价。

## 快速索引

| Term ID | 规范名称 | 别名 | 一句话定义 |
|---|---|---|---|
| [`TERM-AUTHORITY`](#term-authority) | `authority` | 权威<br>authority source | 能够在声明管辖域内授予当前效力的 owner、规则或机器真源；文件存在、证明写完和测试通过本身都不是 authority。 |
| [`TERM-EVIDENCE`](#term-evidence) | `evidence` | 证据<br>evidence package | 支持 claim、decision 或历史判断的材料；它可以是 tracked 文档或 local-optional 工件，但不会自动升级权威层。 |
| [`TERM-CLAIM`](#term-claim) | `claim` | 知识声明<br>稳定结论 | 具有稳定 ID、statement、scope、premises、consequences、does-not-imply、evidence 与 authority effect 的可查询知识节点。 |
| [`TERM-DOSSIER`](#term-dossier) | `dossier` | 研究包<br>证据包 | 对一个一级研究、外审、实验或本地证据根的稳定登记单位；登记 dossier 只保证可发现，不表示内容已经语义审阅。 |
| [`TERM-CURRENT-REVIEW`](#term-current-review) | `current backfill review` | current review<br>语义审阅 | 某 dossier 当前有效的一次审阅记录，声明实际查看的路径、提炼 claim、未决项与重审触发器；后续审阅通过 supersedes 换代。 |
| [`TERM-BACKFILL-TRIAGE`](#term-backfill-triage) | `backfill triage` | 长尾分诊<br>inventory triage | 对尚无 current review 的 dossier 做显式、穷尽且可重开的队列分类，以保证没有材料从地图上消失。 |
| [`TERM-CURRENT`](#term-current) | `current` | 现役<br>当前有效 | 在其声明 scope 和 authority 内仍可作为当前知识引用的状态。 |
| [`TERM-HISTORICAL`](#term-historical) | `historical` | 历史有效<br>历史节点 | 保存当时成立、观察到或被采用的内容，但不再作为当前结论直接复用的状态。 |
| [`TERM-SUPERSEDED`](#term-superseded) | `superseded` | 被取代<br>换代 | 旧节点的含义或权威位置已由显式 successor 接替；旧节点仍保留以维持引用和历史链。 |
| [`TERM-CERTIFIED`](#term-certified) | `CERTIFIED` | 认证级<br>certified exact | 只在 PROJECT_LOCK 与 overview 声明的六谓词、身份、证据和 lex 最优边界内成立的发布级状态。 |
| [`TERM-RESEARCH-UPPER-LEDGER`](#term-research-upper-ledger) | `research upper ledger` | 研究上界账本<br>U 账本 | 按明确语义和前提登记的研究级上界坐标；六谓词与 P2.0 账本必须带标签并分开引用。 |
| [`TERM-NAMED-FRONTIER`](#term-named-frontier) | `具名前沿` | named frontier | 一条研究线明确承诺推动的具体边界或账本坐标，必须指出推进哪一侧、相对于哪个当前值。 |
| [`TERM-NAIVE-BASELINE`](#term-naive-baseline) | `朴素基线` | 同预算直接推进基线 | 在同一具名前沿与同一预算下，不增加新方法而直接推进该前沿的对照路线。 |
| [`TERM-STRICT-EMPTY-RECTANGLE`](#term-strict-empty-rectangle) | `strict empty rectangle` | 严格空地<br>no_occupant_of_any_kind | 空矩形内部不允许任何 occupant，包括设施、端口前格、物流组件与 ghost-reserved 占用。 |
| [`TERM-BODY-EMPTY-RECTANGLE`](#term-body-empty-rectangle) | `body-empty rectangle` | body-only 空矩形<br>设施体空地 | 只排除设施 body 的较宽松几何对象；它可用于中间计数，但不能直接替代现行 strict empty rectangle。 |
| [`TERM-PHYSICAL-PORT`](#term-physical-port) | `physical port cell` | port cell<br>端口格 | 由 canonical pose 给出的实体端口坐标。 |
| [`TERM-FRONT-CELL`](#term-front-cell) | `front/access cell` | front cell<br>access cell<br>准入口 | 与物理端口相邻、用于路由接入或容量账的外部格；其语义取决于 source/destination 与终端类别。 |
| [`TERM-CANDIDATE-DISCOVERY`](#term-candidate-discovery) | `candidate discovery` | 候选发现<br>发现器 | 从状态、结构或数据中提出可能有效的不等式、排除或 cut 候选的能力。 |
| [`TERM-CANDIDATE-VALIDATION`](#term-candidate-validation) | `candidate validation` | 候选验证<br>有效性验证 | 证明或独立检查候选在声明 scope 内 sound 的能力。 |
| [`TERM-SEPARATION`](#term-separation) | `separation` | 分离<br>separator | 针对当前候选解或状态主动找到被违反的有效不等式或排除条件的过程。 |
| [`TERM-SOLVER-CONSUMPTION`](#term-solver-consumption) | `solver consumption` | cut consumption<br>消费机制 | 把已经发现并验证的 cut、nogood 或预排除送入模型、搜索或缓存的机制。 |
| [`TERM-PREMODEL-EXCLUSION`](#term-premodel-exclusion) | `pre-model exclusion` | 模型前排除<br>预建模排除 | 在变量或候选进入主模型前，以已证明的必要条件删除不可能项。 |
| [`TERM-MODEL-OMISSION`](#term-model-omission) | `model omission` | 免建模<br>不建变量 | 因已建立等价或 sound 预排除而安全省略模型对象。 |
| [`TERM-UNKNOWN`](#term-unknown) | `UNKNOWN` | 未知<br>预算内未知 | 在给定预算、工具或证据下未能证明 FEASIBLE/INFEASIBLE 的终态。 |
| [`TERM-INFEASIBLE`](#term-infeasible) | `INFEASIBLE` | 不可行<br>无解证明 | 在声明模型、候选域和证明义务内已经闭合的不可行结论。 |
| [`TERM-FIXED-POINT`](#term-fixed-point) | `fixed point` | 闭包固定点<br>饱和点 | 在声明的推理规则集下继续应用规则不会产生新信息的状态。 |
| [`TERM-ROUTE-NO-GO`](#term-route-no-go) | `route NO-GO` | 路线撤回<br>方法 gate 失败 | 某个明示实现、参数、规模或 revision 未通过登记 gate 的历史负结果。 |
| [`TERM-SEMANTIC-REVIEW`](#term-semantic-review) | `semantic review` | 语义回填<br>knowledge backfill | 实际读取声明路径，判断可复用命题、scope、premises、authority 与失效边界，并写入 current review/claim 的过程。 |
| [`TERM-INVENTORY-COVERAGE`](#term-inventory-coverage) | `inventory coverage` | 目录覆盖<br>可发现性覆盖 | 保证每个登记 dossier 要么有 current review，要么进入唯一 triage group 的机械闭包。 |

<a id="term-authority"></a>
## authority

- **Term ID：** `TERM-AUTHORITY`
- **别名：** 权威；authority source
- **定义：** 能够在声明管辖域内授予当前效力的 owner、规则或机器真源；文件存在、证明写完和测试通过本身都不是 authority。
- **不要混同：** 不要与 evidence 混同。
- **相关 claim：** [`CLAIM-CERTIFIED-THEOREM-SCOPE`](<CATALOG.md#claim-certified-theorem-scope>)
- **解释来源：** [docs/START_HERE.md](<START_HERE.md>)；[docs/governance/document-system/ARCHITECTURE.md](<governance/document-system/ARCHITECTURE.md>)

<a id="term-evidence"></a>
## evidence

- **Term ID：** `TERM-EVIDENCE`
- **别名：** 证据；evidence package
- **定义：** 支持 claim、decision 或历史判断的材料；它可以是 tracked 文档或 local-optional 工件，但不会自动升级权威层。
- **不要混同：** 不要把 local artifact 或 PASS 直接读成 owner/production authority。
- **相关 claim：** —
- **解释来源：** [docs/START_HERE.md](<START_HERE.md>)；[data/knowledge/README.md](<../data/knowledge/README.md>)

<a id="term-claim"></a>
## claim

- **Term ID：** `TERM-CLAIM`
- **别名：** 知识声明；稳定结论
- **定义：** 具有稳定 ID、statement、scope、premises、consequences、does-not-imply、evidence 与 authority effect 的可查询知识节点。
- **不要混同：** statement 或 scope 实质变化时应新建 ID，而不是原地改义。
- **相关 claim：** —
- **解释来源：** [data/knowledge/README.md](<../data/knowledge/README.md>)；[data/knowledge/schemas/claim.schema.json](<../data/knowledge/schemas/claim.schema.json>)

<a id="term-dossier"></a>
## dossier

- **Term ID：** `TERM-DOSSIER`
- **别名：** 研究包；证据包
- **定义：** 对一个一级研究、外审、实验或本地证据根的稳定登记单位；登记 dossier 只保证可发现，不表示内容已经语义审阅。
- **不要混同：** 不要与 claim 或 current review 混同。
- **相关 claim：** —
- **解释来源：** [data/knowledge/README.md](<../data/knowledge/README.md>)；[docs/governance/document-system/ARCHITECTURE.md](<governance/document-system/ARCHITECTURE.md>)

<a id="term-current-review"></a>
## current backfill review

- **Term ID：** `TERM-CURRENT-REVIEW`
- **别名：** current review；语义审阅
- **定义：** 某 dossier 当前有效的一次审阅记录，声明实际查看的路径、提炼 claim、未决项与重审触发器；后续审阅通过 supersedes 换代。
- **不要混同：** availability_and_provenance 只检查缺失本地根的可用性与来源链，不等于 payload 语义审阅。
- **相关 claim：** —
- **解释来源：** [data/knowledge/README.md](<../data/knowledge/README.md>)；[data/knowledge/schemas/backfill_review.schema.json](<../data/knowledge/schemas/backfill_review.schema.json>)

<a id="term-backfill-triage"></a>
## backfill triage

- **Term ID：** `TERM-BACKFILL-TRIAGE`
- **别名：** 长尾分诊；inventory triage
- **定义：** 对尚无 current review 的 dossier 做显式、穷尽且可重开的队列分类，以保证没有材料从地图上消失。
- **不要混同：** triage 不是 semantic review，也不是 no_reusable_claim 判决。
- **相关 claim：** —
- **解释来源：** [data/knowledge/backfill_triage.json](<../data/knowledge/backfill_triage.json>)；[docs/governance/document-system/ARCHITECTURE.md](<governance/document-system/ARCHITECTURE.md>)

<a id="term-current"></a>
## current

- **Term ID：** `TERM-CURRENT`
- **别名：** 现役；当前有效
- **定义：** 在其声明 scope 和 authority 内仍可作为当前知识引用的状态。
- **不要混同：** current 不等于 production certified。
- **相关 claim：** —
- **解释来源：** [data/knowledge/schemas/claim.schema.json](<../data/knowledge/schemas/claim.schema.json>)；[docs/CURRENT.md](<CURRENT.md>)

<a id="term-historical"></a>
## historical

- **Term ID：** `TERM-HISTORICAL`
- **别名：** 历史有效；历史节点
- **定义：** 保存当时成立、观察到或被采用的内容，但不再作为当前结论直接复用的状态。
- **不要混同：** 历史材料不应追随现态静默改写。
- **相关 claim：** —
- **解释来源：** [docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)；[docs/governance/document-system/ARCHITECTURE.md](<governance/document-system/ARCHITECTURE.md>)

<a id="term-superseded"></a>
## superseded

- **Term ID：** `TERM-SUPERSEDED`
- **别名：** 被取代；换代
- **定义：** 旧节点的含义或权威位置已由显式 successor 接替；旧节点仍保留以维持引用和历史链。
- **不要混同：** supersedes 是换代边，不是 dependency 边。
- **相关 claim：** —
- **解释来源：** [docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)；[data/knowledge/schemas/claim.schema.json](<../data/knowledge/schemas/claim.schema.json>)

<a id="term-certified"></a>
## CERTIFIED

- **Term ID：** `TERM-CERTIFIED`
- **别名：** 认证级；certified exact
- **定义：** 只在 PROJECT_LOCK 与 overview 声明的六谓词、身份、证据和 lex 最优边界内成立的发布级状态。
- **不要混同：** 不要把 research authority、solver FEASIBLE 或局部 proof 当作 CERTIFIED。
- **相关 claim：** [`CLAIM-CERTIFIED-THEOREM-SCOPE`](<CATALOG.md#claim-certified-theorem-scope>)
- **解释来源：** [PROJECT_LOCK.md](<../PROJECT_LOCK.md>)；[docs/项目说明/01_overview.md](<项目说明/01_overview.md>)

<a id="term-research-upper-ledger"></a>
## research upper ledger

- **Term ID：** `TERM-RESEARCH-UPPER-LEDGER`
- **别名：** 研究上界账本；U 账本
- **定义：** 按明确语义和前提登记的研究级上界坐标；六谓词与 P2.0 账本必须带标签并分开引用。
- **不要混同：** 上界不推出可达性、下界或 production certification。
- **相关 claim：** [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](<CATALOG.md#claim-six-predicate-research-ledger>)；[`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](<CATALOG.md#claim-p2-throughput-research-ledger>)
- **解释来源：** [docs/CURRENT.md](<CURRENT.md>)；[data/knowledge/claims.jsonl](<../data/knowledge/claims.jsonl>)

<a id="term-named-frontier"></a>
## 具名前沿

- **Term ID：** `TERM-NAMED-FRONTIER`
- **别名：** named frontier
- **定义：** 一条研究线明确承诺推动的具体边界或账本坐标，必须指出推进哪一侧、相对于哪个当前值。
- **不要混同：** 不要把方法新颖度、文档完成或研究机器改良本身当成前沿移动。
- **相关 claim：** [`CLAIM-RESEARCH-LINE-FRONTIER-BASELINE-EXIT-DISCIPLINE`](<CATALOG.md#claim-research-line-frontier-baseline-exit-discipline>)
- **解释来源：** [docs/项目说明/30_research_charter.md](<项目说明/30_research_charter.md>)

<a id="term-naive-baseline"></a>
## 朴素基线

- **Term ID：** `TERM-NAIVE-BASELINE`
- **别名：** 同预算直接推进基线
- **定义：** 在同一具名前沿与同一预算下，不增加新方法而直接推进该前沿的对照路线。
- **不要混同：** 两条精巧路线彼此比较，不能替代与朴素基线的同场比较。
- **相关 claim：** [`CLAIM-RESEARCH-LINE-FRONTIER-BASELINE-EXIT-DISCIPLINE`](<CATALOG.md#claim-research-line-frontier-baseline-exit-discipline>)
- **解释来源：** [docs/项目说明/30_research_charter.md](<项目说明/30_research_charter.md>)

<a id="term-strict-empty-rectangle"></a>
## strict empty rectangle

- **Term ID：** `TERM-STRICT-EMPTY-RECTANGLE`
- **别名：** 严格空地；no_occupant_of_any_kind
- **定义：** 空矩形内部不允许任何 occupant，包括设施、端口前格、物流组件与 ghost-reserved 占用。
- **不要混同：** 不要与 body-empty rectangle 混同。
- **相关 claim：** [`CLAIM-EMPTY-RECTANGLE-STRICT`](<CATALOG.md#claim-empty-rectangle-strict>)
- **解释来源：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)；[docs/项目说明/01_overview.md](<项目说明/01_overview.md>)

<a id="term-body-empty-rectangle"></a>
## body-empty rectangle

- **Term ID：** `TERM-BODY-EMPTY-RECTANGLE`
- **别名：** body-only 空矩形；设施体空地
- **定义：** 只排除设施 body 的较宽松几何对象；它可用于中间计数，但不能直接替代现行 strict empty rectangle。
- **不要混同：** 中间 body/access 预算必须保留其作用域。
- **相关 claim：** [`CLAIM-BODY-ACCESS-BUDGET-1320`](<CATALOG.md#claim-body-access-budget-1320>)
- **解释来源：** [data/knowledge/claims.jsonl](<../data/knowledge/claims.jsonl>)

<a id="term-physical-port"></a>
## physical port cell

- **Term ID：** `TERM-PHYSICAL-PORT`
- **别名：** port cell；端口格
- **定义：** 由 canonical pose 给出的实体端口坐标。
- **不要混同：** 不要与 front/access cell 混同。
- **相关 claim：** [`CLAIM-MIXED-TERMINAL-TRIPARTITION`](<CATALOG.md#claim-mixed-terminal-tripartition>)
- **解释来源：** [rules/canonical_rules.json](<../rules/canonical_rules.json>)；[docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md](<research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md>)

<a id="term-front-cell"></a>
## front/access cell

- **Term ID：** `TERM-FRONT-CELL`
- **别名：** front cell；access cell；准入口
- **定义：** 与物理端口相邻、用于路由接入或容量账的外部格；其语义取决于 source/destination 与终端类别。
- **不要混同：** 不要再使用 stored port 后 double-step 的旧解释。
- **相关 claim：** [`CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED`](<CATALOG.md#claim-front-offset-double-step-semantics-superseded>)；[`CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE`](<CATALOG.md#claim-destination-front-exclusivity-terminal-sensitive>)
- **解释来源：** [docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)；[docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md](<research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md>)

<a id="term-candidate-discovery"></a>
## candidate discovery

- **Term ID：** `TERM-CANDIDATE-DISCOVERY`
- **别名：** 候选发现；发现器
- **定义：** 从状态、结构或数据中提出可能有效的不等式、排除或 cut 候选的能力。
- **不要混同：** 发现不等于有效性证明，也不等于 solver 已消费。
- **相关 claim：** [`CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS`](<CATALOG.md#claim-discovery-and-validation-separate-obligations>)
- **解释来源：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

<a id="term-candidate-validation"></a>
## candidate validation

- **Term ID：** `TERM-CANDIDATE-VALIDATION`
- **别名：** 候选验证；有效性验证
- **定义：** 证明或独立检查候选在声明 scope 内 sound 的能力。
- **不要混同：** validator 只检查输入候选时，不自动成为 separator。
- **相关 claim：** [`CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS`](<CATALOG.md#claim-discovery-and-validation-separate-obligations>)；[`CLAIM-SOLVER-RETHINK-G03-LACKS-SEPARATION-ORACLE`](<CATALOG.md#claim-solver-rethink-g03-lacks-separation-oracle>)
- **解释来源：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

<a id="term-separation"></a>
## separation

- **Term ID：** `TERM-SEPARATION`
- **别名：** 分离；separator
- **定义：** 针对当前候选解或状态主动找到被违反的有效不等式或排除条件的过程。
- **不要混同：** 不要把通用传播未触发、已知 cut 的 checker 或 accepted-cut 计数当作完整 separator。
- **相关 claim：** [`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](<CATALOG.md#claim-generic-cp-sat-separation-impossibility-open>)；[`CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`](<CATALOG.md#claim-raw-eligible-events-required-for-separation-evaluation>)
- **解释来源：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

<a id="term-solver-consumption"></a>
## solver consumption

- **Term ID：** `TERM-SOLVER-CONSUMPTION`
- **别名：** cut consumption；消费机制
- **定义：** 把已经发现并验证的 cut、nogood 或预排除送入模型、搜索或缓存的机制。
- **不要混同：** 消费已知规则不等于发现新规则。
- **相关 claim：** [`CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM`](<CATALOG.md#claim-typed-cut-pipeline-consumes-known-cuts-not-discovers-them>)
- **解释来源：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

<a id="term-premodel-exclusion"></a>
## pre-model exclusion

- **Term ID：** `TERM-PREMODEL-EXCLUSION`
- **别名：** 模型前排除；预建模排除
- **定义：** 在变量或候选进入主模型前，以已证明的必要条件删除不可能项。
- **不要混同：** 只有已证明 sound 的排除才支持后续 model omission。
- **相关 claim：** [`CLAIM-PROVED-PREMODEL-EXCLUSION-PERMITS-MODEL-OMISSION`](<CATALOG.md#claim-proved-premodel-exclusion-permits-model-omission>)
- **解释来源：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

<a id="term-model-omission"></a>
## model omission

- **Term ID：** `TERM-MODEL-OMISSION`
- **别名：** 免建模；不建变量
- **定义：** 因已建立等价或 sound 预排除而安全省略模型对象。
- **不要混同：** 启发式没发现候选、TIMEOUT 或通用传播没推出，均不足以支持免建模。
- **相关 claim：** [`CLAIM-PROVED-PREMODEL-EXCLUSION-PERMITS-MODEL-OMISSION`](<CATALOG.md#claim-proved-premodel-exclusion-permits-model-omission>)
- **解释来源：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

<a id="term-unknown"></a>
## UNKNOWN

- **Term ID：** `TERM-UNKNOWN`
- **别名：** 未知；预算内未知
- **定义：** 在给定预算、工具或证据下未能证明 FEASIBLE/INFEASIBLE 的终态。
- **不要混同：** UNKNOWN 不是 INFEASIBLE，也不是固定点或结构墙。
- **相关 claim：** [`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](<CATALOG.md#claim-budget-exhaustion-is-unknown-not-fixed-point>)；[`CLAIM-ROUND45-CORRECTED-PROFILE-UNKNOWN-NOT-STRUCTURAL-WALL`](<CATALOG.md#claim-round45-corrected-profile-unknown-not-structural-wall>)
- **解释来源：** [docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)；[docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

<a id="term-infeasible"></a>
## INFEASIBLE

- **Term ID：** `TERM-INFEASIBLE`
- **别名：** 不可行；无解证明
- **定义：** 在声明模型、候选域和证明义务内已经闭合的不可行结论。
- **不要混同：** 受限候选域 INFEASIBLE 不推出全域 INFEASIBLE。
- **相关 claim：** [`CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN`](<CATALOG.md#claim-witness-restricted-pole-domains-infeasible-full-domain-open>)
- **解释来源：** [data/knowledge/claims.jsonl](<../data/knowledge/claims.jsonl>)

<a id="term-fixed-point"></a>
## fixed point

- **Term ID：** `TERM-FIXED-POINT`
- **别名：** 闭包固定点；饱和点
- **定义：** 在声明的推理规则集下继续应用规则不会产生新信息的状态。
- **不要混同：** 预算耗尽、pairwise 无新项或 accepted cuts 为零都不能自动证明完整固定点。
- **相关 claim：** [`CLAIM-PAIRWISE-CLOSURE-INCOMPLETE`](<CATALOG.md#claim-pairwise-closure-incomplete>)；[`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](<CATALOG.md#claim-budget-exhaustion-is-unknown-not-fixed-point>)
- **解释来源：** [docs/REASONING_LEDGER.md](<REASONING_LEDGER.md>)

<a id="term-route-no-go"></a>
## route NO-GO

- **Term ID：** `TERM-ROUTE-NO-GO`
- **别名：** 路线撤回；方法 gate 失败
- **定义：** 某个明示实现、参数、规模或 revision 未通过登记 gate 的历史负结果。
- **不要混同：** 不能外推为整个算法家族或数学范式不可能。
- **相关 claim：** [`CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`](<CATALOG.md#claim-lever-verdicts-are-item-and-revision-bounded>)；[`CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO`](<CATALOG.md#claim-column-generation-phase2-scale-route-no-go>)
- **解释来源：** [docs/VALIDITY_LEDGER.md](<VALIDITY_LEDGER.md>)

<a id="term-semantic-review"></a>
## semantic review

- **Term ID：** `TERM-SEMANTIC-REVIEW`
- **别名：** 语义回填；knowledge backfill
- **定义：** 实际读取声明路径，判断可复用命题、scope、premises、authority 与失效边界，并写入 current review/claim 的过程。
- **不要混同：** 不要与 dossier inventory 或 triage coverage 混同。
- **相关 claim：** —
- **解释来源：** [data/knowledge/README.md](<../data/knowledge/README.md>)；[docs/BACKFILL_LEDGER.md](<BACKFILL_LEDGER.md>)

<a id="term-inventory-coverage"></a>
## inventory coverage

- **Term ID：** `TERM-INVENTORY-COVERAGE`
- **别名：** 目录覆盖；可发现性覆盖
- **定义：** 保证每个登记 dossier 要么有 current review，要么进入唯一 triage group 的机械闭包。
- **不要混同：** 100% inventory coverage 不等于 100% semantic review。
- **相关 claim：** —
- **解释来源：** [data/knowledge/backfill_triage.json](<../data/knowledge/backfill_triage.json>)；[docs/BACKFILL_LEDGER.md](<BACKFILL_LEDGER.md>)

按主题组合这些术语见 [TOPIC_INDEX](<TOPIC_INDEX.md>)；文档框架的完整原因与维护协议见 [ARCHITECTURE](<governance/document-system/ARCHITECTURE.md>) 和 [MAINTAINING](<governance/document-system/MAINTAINING.md>)。
