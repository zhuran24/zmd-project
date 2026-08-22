# 历史知识回填与长尾覆盖

> 本页由 `data/knowledge/backfill_reviews.jsonl`、`backfill_triage.json` 与 dossier registry 自动生成；禁止手工修改。
> 账本审阅日：`2026-08-15`；源摘要：`sha256:2720224c8cc41d4abfd1a1a30adf5c380a40c4458918601ced4695350f0983a8`。

这里把两件经常被混写的事情分开：**semantic review** 表示实际读取了声明路径并提炼知识；**inventory triage** 只保证尚未审阅的 dossier 仍可发现、只落入一个队列，并带有重开条件。分诊从不等价于 `no_reusable_claim`。

## 收口概览

- dossier 总数：`277`。
- current review：`45`，其中语义审阅 `42`，availability/provenance-only `3`。
- 尚无 current review、但已进入唯一 triage group：`165`。
- 新写入流程中尚未关闭的 active dossier：`71`；其中已有 current review `4`；open workflow 不进入历史 triage。
- inventory coverage：`277/277`。
- semantic review coverage：`42/277`。这个比例不会被 triage 人为抬高。

## Current review

| Review | Dossier | 范围 | 结果 | Claim | 未决项 |
|---|---|---|---|---|---|
| [`REVIEW-20260811-AB16-ARMS-BATCH3`](<CATALOG.md#review-20260811-ab16-arms-batch3>) | `DOSSIER-AB16-ARMS-20260802-DC229C4539` | `targeted_files` | `existing_claims_confirmed` | [`CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS`](<CATALOG.md#claim-cut-framework-production-status>)<br>[`CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT`](<CATALOG.md#claim-ab16-no-scientific-cut-result>)<br>[`CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`](<CATALOG.md#claim-raw-eligible-events-required-for-separation-evaluation>) | 需要有机触发、预注册 baseline 和完整 reachability funnel 的新实验。 |
| [`REVIEW-20260811-B1-CONDITIONAL-HALO-BATCH2`](<CATALOG.md#review-20260811-b1-conditional-halo-batch2>) | `DOSSIER-B1-CONDITIONAL-HALO-20260722-0D968A299D` | `entry_and_references` | `claims_promoted` | [`CLAIM-B1-CEILING-EXACT-NINE-POLES`](<CATALOG.md#claim-b1-ceiling-exact-nine-poles>)<br>[`CLAIM-B1-CONDITIONAL-HALO-CAPACITY-6650`](<CATALOG.md#claim-b1-conditional-halo-capacity-6650>) | 该不等式在已跑 512-case corpus 中没有分离 control/treatment；其在其他候选族中的实际剪枝价值仍未量化。 |
| [`REVIEW-20260811-B1-QMH-BATCH2`](<CATALOG.md#review-20260811-b1-qmh-batch2>) | `DOSSIER-B1-Q-MEMBRANE-HALO-20260722-D054906F9B` | `entry_and_references` | `claims_promoted` | [`CLAIM-B1-QMH-REFINED-MEMBRANE-INEQUALITY`](<CATALOG.md#claim-b1-qmh-refined-membrane-inequality>) | 该必要式只排除 138 个 pattern-placement assignments，未改变当时 upper frontier。 |
| [`REVIEW-20260811-B1-R4-PB-BATCH2`](<CATALOG.md#review-20260811-b1-r4-pb-batch2>) | `DOSSIER-B1-R4-1188-22-PB-20260723-FE5DFB853D` | `entry_and_references` | `claims_promoted` | [`CLAIM-R4-LEX-BAND-2084-UNSAT`](<CATALOG.md#claim-r4-lex-band-2084-unsat>) | — |
| [`REVIEW-20260811-BAND22-CLEANROOM-V0A-BATCH2`](<CATALOG.md#review-20260811-band22-cleanroom-v0a-batch2>) | `DOSSIER-CLEANROOM-REDERIVATION-20260718-41375BBFE3` | `targeted_files` | `claims_promoted` | [`CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE`](<CATALOG.md#claim-band22-v0a-strict-hole-incompatible>) | cleanroom_rederivation 其余子包未在本 review 中全量语义回填。 |
| [`REVIEW-20260811-BAND22-STRICT-HOLE-PROBE-BATCH2`](<CATALOG.md#review-20260811-band22-strict-hole-probe-batch2>) | `DOSSIER-BAND22-STRICT-HOLE-PROBE-20260805-B4EF0C65D3` | `targeted_files` | `claims_promoted` | [`CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE`](<CATALOG.md#claim-band22-v0a-strict-hole-incompatible>)<br>[`CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED`](<CATALOG.md#claim-boundary-generic-output-slots-saturated>)<br>[`CLAIM-STRICT-HOLE-AVOIDS-X1-Y1`](<CATALOG.md#claim-strict-hole-avoids-x1-y1>) | k=1 单列活口只有必要账本，没有完整 placement/routing/power witness 或 strict checker 结果。 |
| [`REVIEW-20260811-BATCH-CE-ATTACH-HOST-BATCH3`](<CATALOG.md#review-20260811-batch-ce-attach-host-batch3>) | `DOSSIER-BATCH-CE-ATTACH-HOST-20260712-D4A08ECB0B` | `targeted_files` | `claims_promoted` | [`CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM`](<CATALOG.md#claim-typed-cut-pipeline-consumes-known-cuts-not-discovers-them>) | 该 dossier 其余批 C/E 轮次尚未做完整性能因果回填。 |
| [`REVIEW-20260811-CANONICAL-BATCH-20260807`](<CATALOG.md#review-20260811-canonical-batch-20260807>) | `DOSSIER-CANONICAL-BATCH-20260807-B460BA9381` | `entry_and_references` | `claims_promoted` | [`CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT`](<CATALOG.md#claim-model-stricter-faces-scope-debt>)<br>[`CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE`](<CATALOG.md#claim-destination-front-exclusivity-terminal-sensitive>)<br>[`CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT`](<CATALOG.md#claim-source-front-exclusivity-overstrict>)<br>[`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT`](<CATALOG.md#claim-routing-reverification-extra-strict>)<br>[`CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE`](<CATALOG.md#claim-binding-slot-single-commodity-scope>)<br>[`CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE`](<CATALOG.md#claim-boundary-loader-excluded-frozen-instance>)<br>[`CLAIM-MIXED-TERMINAL-TRIPARTITION`](<CATALOG.md#claim-mixed-terminal-tripartition>)<br>[`CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE`](<CATALOG.md#claim-rate-lemma-conditional-profile>) | 该 dossier 仍含其他规则条款，尚未做全量逐条 claim 化。 |
| [`REVIEW-20260811-CANONICAL-BATCH-20260808`](<CATALOG.md#review-20260811-canonical-batch-20260808>) | `DOSSIER-CANONICAL-BATCH-20260808-B2462129DF` | `targeted_files` | `claims_promoted` | [`CLAIM-MODEL-STRICTER-FACES-SCOPE-DEBT`](<CATALOG.md#claim-model-stricter-faces-scope-debt>)<br>[`CLAIM-DESTINATION-FRONT-EXCLUSIVITY-TERMINAL-SENSITIVE`](<CATALOG.md#claim-destination-front-exclusivity-terminal-sensitive>)<br>[`CLAIM-SOURCE-FRONT-EXCLUSIVITY-OVERSTRICT`](<CATALOG.md#claim-source-front-exclusivity-overstrict>)<br>[`CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT`](<CATALOG.md#claim-routing-reverification-extra-strict>)<br>[`CLAIM-BINDING-SLOT-SINGLE-COMMODITY-SCOPE`](<CATALOG.md#claim-binding-slot-single-commodity-scope>)<br>[`CLAIM-ADMISSION-PORT-OMISSION-SCOPE-RESTRICTION`](<CATALOG.md#claim-admission-port-omission-scope-restriction>)<br>[`CLAIM-BOUNDARY-LOADER-EXCLUDED-FROZEN-INSTANCE`](<CATALOG.md#claim-boundary-loader-excluded-frozen-instance>)<br>[`CLAIM-MIXED-TERMINAL-TRIPARTITION`](<CATALOG.md#claim-mixed-terminal-tripartition>)<br>[`CLAIM-STORAGE-BOX-ACCEPTANCE-INVARIANT-FROZEN`](<CATALOG.md#claim-storage-box-acceptance-invariant-frozen>)<br>[`CLAIM-RATE-LEMMA-CONDITIONAL-PROFILE`](<CATALOG.md#claim-rate-lemma-conditional-profile>) | BLOCKERS 与 provenance 文档中的非承重细节尚未单独建 claim。 |
| [`REVIEW-20260811-COLUMN-GENERATION-PHASE2-BATCH4`](<CATALOG.md#review-20260811-column-generation-phase2-batch4>) | `DOSSIER-CAND-C-COLUMN-GENERATION-PHASE2-20260521-9625F52BA3` | `entry_and_references` | `claims_promoted` | [`CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO`](<CATALOG.md#claim-column-generation-phase2-scale-route-no-go>) | 不同 bootstrap、pricing、branching 或 reconstruction 设计仍未被该 verdict 排除。 |
| [`REVIEW-20260811-F7-ROUND1-BATCH4`](<CATALOG.md#review-20260811-f7-round1-batch4>) | `DOSSIER-P1-2B-F7-POWER-HITTING-SET-GEMINI-ROUND1-20260525-DB49AFB525` | `targeted_files` | `claims_promoted` | [`CLAIM-F7-FACILITY-MASK-VALIDATOR-BUG-REPAIRED`](<CATALOG.md#claim-f7-facility-mask-validator-bug-repaired>) | 其他 defer 项仍属于当时 Phase 1.5+ 路线，不由本 claim 关闭。 |
| [`REVIEW-20260811-F7-ROUND2-BATCH4`](<CATALOG.md#review-20260811-f7-round2-batch4>) | `DOSSIER-P1-2B-F7-POWER-HITTING-SET-GEMINI-ROUND2-20260525-C4D8B4A483` | `targeted_files` | `existing_claims_confirmed` | [`CLAIM-F7-FACILITY-MASK-VALIDATOR-BUG-REPAIRED`](<CATALOG.md#claim-f7-facility-mask-validator-bug-repaired>) | active_assumptions 等 defer 项未由本历史 repair claim 处理。 |
| [`REVIEW-20260811-FRONT-OFFSET-ARTIFACT-BATCH4`](<CATALOG.md#review-20260811-front-offset-artifact-batch4>) | `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-2B25E2B21B` | `targeted_files` | `existing_claims_confirmed` | [`CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED`](<CATALOG.md#claim-front-offset-pre-0718-superseded>)<br>[`CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED`](<CATALOG.md#claim-r1-1326-34-strict-upper-revalidated>) | artifact payload 需在具备本地证据卷的环境中做逐文件 hash 重放。 |
| [`REVIEW-20260811-FRONT-OFFSET-INCIDENT-BATCH4`](<CATALOG.md#review-20260811-front-offset-incident-batch4>) | `DOSSIER-FRONT-OFFSET-INCIDENT-20260718-7F16095D41` | `entry_and_references` | `claims_promoted` | [`CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED`](<CATALOG.md#claim-front-offset-double-step-semantics-superseded>)<br>[`CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED`](<CATALOG.md#claim-front-offset-pre-0718-superseded>)<br>[`CLAIM-FRONT-OFFSET-HISTORICAL-REJUDGMENT-40`](<CATALOG.md#claim-front-offset-historical-rejudgment-40>)<br>[`CLAIM-SHARED-ENCODING-AGREEMENT-NOT-INDEPENDENT-VALIDATION`](<CATALOG.md#claim-shared-encoding-agreement-not-independent-validation>)<br>[`CLAIM-ROUND45-CORRECTED-PROFILE-UNKNOWN-NOT-STRUCTURAL-WALL`](<CATALOG.md#claim-round45-corrected-profile-unknown-not-structural-wall>)<br>[`CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED`](<CATALOG.md#claim-r1-1326-34-strict-upper-revalidated>) | 其余需重验 finding 尚未全部提升为稳定 claim；RAB/FCL 与 witness 的新 revision 仍应按各自作用域登记。 |
| [`REVIEW-20260811-HISTORY-TOOLCHAIN-ORIGIN-BATCH3`](<CATALOG.md#review-20260811-history-toolchain-origin-batch3>) | `DOSSIER-HISTORY-TOOLCHAIN-ORIGIN-20260709-411160EC29` | `entry_and_references` | `claims_promoted` | [`CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS`](<CATALOG.md#claim-discovery-and-validation-separate-obligations>)<br>[`CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM`](<CATALOG.md#claim-typed-cut-pipeline-consumes-known-cuts-not-discovers-them>) | 考古包中的外部 memory 引用并非全部 vendored，不能独立承担当前 authority。 |
| [`REVIEW-20260811-IHS-PHASE0-BATCH4`](<CATALOG.md#review-20260811-ihs-phase0-batch4>) | `DOSSIER-LEVER25-IHS-PHASE0-20260520-4194EBD09A` | `entry_and_references` | `claims_promoted` | [`CLAIM-IHS-SINGLETON-CORE-COMPRESSION-PHASE0-NO-GO`](<CATALOG.md#claim-ihs-singleton-core-compression-phase0-no-go>) | 能产生共享 literals 的 generalized core source 尚未设计或验证。 |
| [`REVIEW-20260811-LAZY-POWER-PHASE0-BATCH4`](<CATALOG.md#review-20260811-lazy-power-phase0-batch4>) | `DOSSIER-PHASE0-LAZY-POWER-COMPLETION-20260517-2DD76729CA` | `entry_and_references` | `claims_promoted` | [`CLAIM-LAZY-POWER-INSTANCE-POSE-CUT-ROUTE-NO-GO`](<CATALOG.md#claim-lazy-power-instance-pose-cut-route-no-go>) | 几何位置级 cut、pose-bool master 与其他 lazy-completion 语言仍是未验证的新设计。 |
| [`REVIEW-20260811-M5-CONVERGENCE-BATCH4`](<CATALOG.md#review-20260811-m5-convergence-batch4>) | `DOSSIER-P1-3-M5-CONVERGENCE-20260708-A96D060024` | `targeted_files` | `claims_promoted` | [`CLAIM-M5-DEFAULT-SOLVE-PARAMETERS-PATHOLOGICAL-REFUTED`](<CATALOG.md#claim-m5-default-solve-parameters-pathological-refuted>)<br>[`CLAIM-M5-DEATHS-REQUIRE-RESOURCE-BUILD-AND-PARAMETER-SEPARATION`](<CATALOG.md#claim-m5-deaths-require-resource-build-and-parameter-separation>) | wall 税的 production wrapper 优化优先级仍属 owner roadmap。 |
| [`REVIEW-20260811-MIXFLOW-FIXTURE-CORRECTION-BATCH4`](<CATALOG.md#review-20260811-mixflow-fixture-correction-batch4>) | `DOSSIER-MIXFLOW-DEMIX-BAN-20260807-FFEA2B3CE4` | `targeted_files` | `claims_promoted` | [`CLAIM-MIXFLOW-U01-GUARD-FORK-BENEFIT-REFUTED`](<CATALOG.md#claim-mixflow-u01-guard-fork-benefit-refuted>)<br>[`CLAIM-MIXFLOW-DEMIX-CONCLUSION-SURVIVES-FIXTURE-CORRECTION`](<CATALOG.md#claim-mixflow-demix-conclusion-survives-fixture-correction>) | 忠实 fixture 的 TIMEOUT 仍是非识别性结果。 |
| [`REVIEW-20260811-NONCERT-CUTS-AB16`](<CATALOG.md#review-20260811-noncert-cuts-ab16>) | `DOSSIER-NONCERT-CUTS-AB16-20260724-826CF39625` | `entry_and_references` | `claims_promoted` | [`CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS`](<CATALOG.md#claim-cut-framework-production-status>)<br>[`CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT`](<CATALOG.md#claim-ab16-no-scientific-cut-result>) | 需要新实验合同才能区分候选暴露、cap 口径与 cut 本体效果。 |
| [`REVIEW-20260811-P1-2-V99-CLOSE-KERNEL`](<CATALOG.md#review-20260811-p1-2-v99-close-kernel>) | `DOSSIER-P1-2-V99-CLOSE-KERNEL-SEALING-207F650E44` | `full_dossier` | `deferred` | — | 需在 production proof-chain 专题中评估是否还应提炼非 decision 型 claim。 |
| [`REVIEW-20260811-P1-3A-ATTACH-POWER-ON-BATCH3`](<CATALOG.md#review-20260811-p1-3a-attach-power-on-batch3>) | `DOSSIER-P1-3A-ATTACH-POWER-ON-SPIKE-20260710-25E1F679CB` | `targeted_files` | `claims_promoted` | [`CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY`](<CATALOG.md#claim-attach-spikes-engineering-not-cut-efficacy>) | — |
| [`REVIEW-20260811-P1-3A-ATTACH-SIZING-BATCH3`](<CATALOG.md#review-20260811-p1-3a-attach-sizing-batch3>) | `DOSSIER-P1-3A-ATTACH-SIZING-SPIKE-20260708-02F3C50E2F` | `targeted_files` | `claims_promoted` | [`CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY`](<CATALOG.md#claim-attach-spikes-engineering-not-cut-efficacy>) | — |
| [`REVIEW-20260811-P2-AREA-BOUND-BATCH2`](<CATALOG.md#review-20260811-p2-area-bound-batch2>) | `DOSSIER-P2-0-AREA-BOUND-20260806-6016501B5F` | `full_dossier` | `claims_promoted` | [`CLAIM-P2-AREA-ACCOUNTING-1356`](<CATALOG.md#claim-p2-area-accounting-1356>)<br>[`CLAIM-P2-AREA-BOUND-1167`](<CATALOG.md#claim-p2-area-bound-1167>)<br>[`CLAIM-P2-MIN-SIDE-UPPER-OPEN`](<CATALOG.md#claim-p2-min-side-upper-open>)<br>[`CLAIM-P2-ROUTE-FOOTPRINT-LOWER-153`](<CATALOG.md#claim-p2-route-footprint-lower-153>)<br>[`CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305`](<CATALOG.md#claim-p2-route-state-lower-bound-305>)<br>[`CLAIM-P2-ROUTED-FLOW-LOWER-9135`](<CATALOG.md#claim-p2-routed-flow-lower-9135>)<br>[`CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015`](<CATALOG.md#claim-p2-single-layer-area-bound-1015>)<br>[`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](<CATALOG.md#claim-p2-throughput-research-ledger>)<br>[`CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE`](<CATALOG.md#claim-power-halo-pole-lower-bound-nine>) | OB6 的布局无关交叉格上界仍开放；被反例推翻的 L≥308 front-state 路线留待负结果专题系统回填。 |
| [`REVIEW-20260811-P2-SPECIALIZED-BATCH4`](<CATALOG.md#review-20260811-p2-specialized-batch4>) | `DOSSIER-P2-0-SPECIALIZED-20260807-C40266E222` | `entry_and_references` | `existing_claims_confirmed` | [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](<CATALOG.md#claim-p2-throughput-research-ledger>)<br>[`CLAIM-P2-BUCKWHEAT-SANDLEAF-MANDATORY-BRANCH`](<CATALOG.md#claim-p2-buckwheat-sandleaf-mandatory-branch>)<br>[`CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL`](<CATALOG.md#claim-p2-five-full-one-half-conditional>)<br>[`CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED`](<CATALOG.md#claim-p2-steel-block-17-lt-18-refuted>) | 阶梯 allocation 与更多商品分流结果仍待逐条结构化。 |
| [`REVIEW-20260811-PARADIGM-LEVER-HISTORY-BATCH4`](<CATALOG.md#review-20260811-paradigm-lever-history-batch4>) | `DOSSIER-PARADIGM-SEARCH-REVIEW-V12-WITH-CODE-20260520-FC02CE09A5` | `targeted_files` | `claims_promoted` | [`CLAIM-24-LEVER-FRAMEWORK-EXHAUSTED-SUPERSEDED`](<CATALOG.md#claim-24-lever-framework-exhausted-superseded>)<br>[`CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`](<CATALOG.md#claim-lever-verdicts-are-item-and-revision-bounded>) | 24 项 lever 的逐条有效性尚未全部映射为独立 claim。 |
| [`REVIEW-20260811-R3-UPPER-BOUND-PB-BATCH2`](<CATALOG.md#review-20260811-r3-upper-bound-pb-batch2>) | `DOSSIER-R3-UPPER-BOUND-PB-20260722-60ED8947CD` | `entry_and_references` | `claims_promoted` | [`CLAIM-BODY-ACCESS-BUDGET-1320`](<CATALOG.md#claim-body-access-budget-1320>)<br>[`CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48`](<CATALOG.md#claim-ordinary-membrane-terminal-bound-s48>)<br>[`CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE`](<CATALOG.md#claim-power-halo-pole-lower-bound-nine>)<br>[`CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY`](<CATALOG.md#claim-r3-lex-band-2074-unsat-given-geometry>) | R3 PB 只机器验证给定几何引理后的算术层，几何 proof roots 仍在其他 dossier。 |
| [`REVIEW-20260811-R4-RESPONSE-BATCH2`](<CATALOG.md#review-20260811-r4-response-batch2>) | `DOSSIER-R4-RESPONSE-REVIEW-20260723-D8EBC0DB9D` | `entry_and_references` | `claims_promoted` | [`CLAIM-BODY-ACCESS-BUDGET-1320`](<CATALOG.md#claim-body-access-budget-1320>)<br>[`CLAIM-ORDINARY-MEMBRANE-TERMINAL-BOUND-S48`](<CATALOG.md#claim-ordinary-membrane-terminal-bound-s48>)<br>[`CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE`](<CATALOG.md#claim-power-halo-pole-lower-bound-nine>)<br>[`CLAIM-R4-BOUNDARY-23-23-FULL-SPAN-EXCLUSION`](<CATALOG.md#claim-r4-boundary-23-23-full-span-exclusion>)<br>[`CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4`](<CATALOG.md#claim-r4-local-weighted-access-capacity-4>)<br>[`CLAIM-R4-MARKED-INCIDENCE-TOTAL-110`](<CATALOG.md#claim-r4-marked-incidence-total-110>)<br>[`CLAIM-R4-MARKED-MEMBRANE-BOUND-S12`](<CATALOG.md#claim-r4-marked-membrane-bound-s12>)<br>[`CLAIM-R4-NECESSARY-DIMENSION-INEQUALITY`](<CATALOG.md#claim-r4-necessary-dimension-inequality>) | 该 dossier 的 authority 只到 admitted-for-encoder-design；正式 2084-band UNSAT 由后续 B1 PB dossier… |
| [`REVIEW-20260811-RAB-SEP-PROMOTION-BATCH4`](<CATALOG.md#review-20260811-rab-sep-promotion-batch4>) | `DOSSIER-RAB-SEP-PROMOTION-20260716-CF6D536C85` | `targeted_files` | `claims_promoted` | [`CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`](<CATALOG.md#claim-raw-eligible-events-required-for-separation-evaluation>)<br>[`CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN`](<CATALOG.md#claim-rab-fcl-front-dependent-performance-withdrawn>) | corrected-front 下同配置 RAB OFF/ON 与 front-clear lift 对照尚未形成可复核替代账本。<br>旧 package 中其余与 front 无关的工程事实若要晋升为独立 claim，仍需逐项证据审阅。 |
| [`REVIEW-20260811-RULE-SYSTEM-REDESIGN-BATCH3`](<CATALOG.md#review-20260811-rule-system-redesign-batch3>) | `DOSSIER-RULE-SYSTEM-REDESIGN-20260807-9B23FA19D2` | `entry_and_references` | `claims_promoted` | [`CLAIM-ZERO-SLACK-AUDIT-METHOD`](<CATALOG.md#claim-zero-slack-audit-method>)<br>[`CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL`](<CATALOG.md#claim-p2-five-full-one-half-conditional>)<br>[`CLAIM-PAIRWISE-CLOSURE-INCOMPLETE`](<CATALOG.md#claim-pairwise-closure-incomplete>)<br>[`CLAIM-DISCOVERY-AND-VALIDATION-SEPARATE-OBLIGATIONS`](<CATALOG.md#claim-discovery-and-validation-separate-obligations>)<br>[`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](<CATALOG.md#claim-generic-cp-sat-separation-impossibility-open>)<br>[`CLAIM-PROVED-PREMODEL-EXCLUSION-PERMITS-MODEL-OMISSION`](<CATALOG.md#claim-proved-premodel-exclusion-permits-model-omission>)<br>[`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](<CATALOG.md#claim-budget-exhaustion-is-unknown-not-fixed-point>) | FINAL_DESIGN 的治理落地批次和 derived-rule registry 仍未实施。 |
| [`REVIEW-20260811-RULES-AUDIT-BATCH4`](<CATALOG.md#review-20260811-rules-audit-batch4>) | `DOSSIER-RULES-AUDIT-20260718-A447D60E10` | `entry_and_references` | `claims_promoted` | [`CLAIM-EMPTY-RECTANGLE-ROUTING-ALLOWED-SUPERSEDED`](<CATALOG.md#claim-empty-rectangle-routing-allowed-superseded>)<br>[`CLAIM-EMPTY-RECTANGLE-STRICT`](<CATALOG.md#claim-empty-rectangle-strict>)<br>[`CLAIM-STRICTER-FEASIBLE-SET-PRESERVES-NEGATIVE-NOT-POSITIVE`](<CATALOG.md#claim-stricter-feasible-set-preserves-negative-not-positive>)<br>[`CLAIM-WAREHOUSE-BRIDGE-EXCLUSION-TARGET-CONDITIONAL`](<CATALOG.md#claim-warehouse-bridge-exclusion-target-conditional>) | 其余 owner adjudication 尚未全量拆分为 validity chain。 |
| [`REVIEW-20260811-SMM-FRESH-AUTHORITY-BATCH2`](<CATALOG.md#review-20260811-smm-fresh-authority-batch2>) | `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-20260727-EA260C6D6B` | `entry_and_references` | `claims_promoted` | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](<CATALOG.md#claim-six-predicate-research-ledger>)<br>[`CLAIM-SMM-209-EXCLUDES-22X54`](<CATALOG.md#claim-smm-209-excludes-22x54>)<br>[`CLAIM-SMM4-LEX-BAND-COMPOSITION-2086`](<CATALOG.md#claim-smm4-lex-band-composition-2086>) | — |
| [`REVIEW-20260811-SMM-STRICT-BATCH2`](<CATALOG.md#review-20260811-smm-strict-batch2>) | `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-STRICT-20260724-F275CFCFE2` | `entry_and_references` | `claims_promoted` | [`CLAIM-SMM-209-EXCLUDES-22X54`](<CATALOG.md#claim-smm-209-excludes-22x54>)<br>[`CLAIM-SMM-COMBINED-CAP-209`](<CATALOG.md#claim-smm-combined-cap-209>)<br>[`CLAIM-SMM-ENDPOINT-TOP-EIGHT-BUDGET-19`](<CATALOG.md#claim-smm-endpoint-top-eight-budget-19>)<br>[`CLAIM-SMM-MARKED-MEMBRANE-BOUND-85`](<CATALOG.md#claim-smm-marked-membrane-bound-85>)<br>[`CLAIM-SMM-OUTSIDE-ACCESS-LOWER-133`](<CATALOG.md#claim-smm-outside-access-lower-133>) | — |
| [`REVIEW-20260811-SMT-MT-PHASE0-BATCH4`](<CATALOG.md#review-20260811-smt-mt-phase0-batch4>) | `DOSSIER-SMT-MT-OUTER-PRUNING-PHASE0-20260521-042BF3000C` | `entry_and_references` | `claims_promoted` | [`CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER`](<CATALOG.md#claim-smt-mt-synthetic-go-not-transferable-to-real-inner>) | 不同真实 proof-producing inner 能否提供更高 INFEASIBLE fuel 仍开放。 |
| [`REVIEW-20260811-SMT-MT-PHASE1-BATCH4`](<CATALOG.md#review-20260811-smt-mt-phase1-batch4>) | `DOSSIER-SMT-MT-OUTER-PRUNING-PHASE1-20260521-DF50598CC0` | `entry_and_references` | `claims_promoted` | [`CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER`](<CATALOG.md#claim-smt-mt-synthetic-go-not-transferable-to-real-inner>) | outer pruning 是否在更高 INFEASIBLE 产率的 inner 上达到有效比例仍未验证。 |
| [`REVIEW-20260811-SOLVER-RETHINK-BATCH3`](<CATALOG.md#review-20260811-solver-rethink-batch3>) | `DOSSIER-SOLVER-RETHINK-20260808-47BE0A3C3A` | `targeted_files` | `claims_promoted` | [`CLAIM-FORWARD-COMPLETENESS-RELATIVE-TO-DECLARED-FRAGMENT`](<CATALOG.md#claim-forward-completeness-relative-to-declared-fragment>)<br>[`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](<CATALOG.md#claim-generic-cp-sat-separation-impossibility-open>)<br>[`CLAIM-SOLVER-RETHINK-G03-LACKS-SEPARATION-ORACLE`](<CATALOG.md#claim-solver-rethink-g03-lacks-separation-oracle>)<br>[`CLAIM-SOLVER-RETHINK-PHASE1-OMITS-CONSTRUCTION-HALF`](<CATALOG.md#claim-solver-rethink-phase1-omits-construction-half>)<br>[`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](<CATALOG.md#claim-budget-exhaustion-is-unknown-not-fixed-point>) | 该 local-optional 包的 DECISION_PACKAGE、内部 refute 与成本估计未在本 review 全量逐项回填。 |
| [`REVIEW-20260811-W0-POWER-COUNTEREXAMPLE-BATCH4`](<CATALOG.md#review-20260811-w0-power-counterexample-batch4>) | `DOSSIER-W0-FRONT-AWARE-20260803-425794297E` | `targeted_files` | `claims_promoted` | [`CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED`](<CATALOG.md#claim-w0-adjacent-4x4-power-impossibility-refuted>)<br>[`CLAIM-W0-POWER-OBSTRUCTION-REQUIRES-DECLARED-HEIGHT-PURITY`](<CATALOG.md#claim-w0-power-obstruction-requires-declared-height-purity>) | 纯装家族的收窄版不可行定理尚未在账本中重新证明。 |
| [`REVIEW-20260811-WITNESS-CONSTRUCTOR-BATCH4`](<CATALOG.md#review-20260811-witness-constructor-batch4>) | `DOSSIER-WITNESS-CONSTRUCTOR-20260717-5F04E123B3` | `entry_and_references` | `claims_promoted` | [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](<CATALOG.md#claim-certified-existence-open>)<br>[`CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN`](<CATALOG.md#claim-witness-restricted-pole-domains-infeasible-full-domain-open>) | 全 pole domain 与其他 shelf topology 尚无 geometry_ready 结果，routing-aware whole-layout witness… |
| [`REVIEW-20260812-GHOST-STRICT-FIX-BATCH5`](<CATALOG.md#review-20260812-ghost-strict-fix-batch5>) | `DOSSIER-GHOST-STRICT-FIX-20260805-0FBA53DB19` | `targeted_files` | `existing_claims_confirmed` | [`CLAIM-EMPTY-RECTANGLE-STRICT`](<CATALOG.md#claim-empty-rectangle-strict>) | M11 的第二次 occupancy digest 比较与 M12 的 owner 身份增量语义在该 mutation batch 中仍是预期 MISSED。<br>本 review 未把本地测试绿灯提升为新的 owner 或 production authority。 |
| [`REVIEW-20260812-P2-REFRESH-BATCH5`](<CATALOG.md#review-20260812-p2-refresh-batch5>) | `DOSSIER-P2-0-REFRESH-20260805-627C980F03` | `targeted_files` | `existing_claims_confirmed` | [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](<CATALOG.md#claim-p2-throughput-research-ledger>) | 本 review 没有逐份复跑本地脚本、receipt 与外部求解器交叉验证。<br>AREA_BOUND_UPGRADE_PLAN 是升格前计划，不得覆盖后续 tracked theorem report 的修订口径。 |
| [`REVIEW-20260812-SMM4-LOCAL-AUTHORITY-AVAILABILITY-BATCH5`](<CATALOG.md#review-20260812-smm4-local-authority-availability-batch5>) | `DOSSIER-TRACK-B-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-2026-2C7C3FCD74` | `availability_and_provenance` | `deferred` | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](<CATALOG.md#claim-six-predicate-research-ledger>) | 需在拥有外部 root 的 checkout 中按 tracked hash/manifest 复核 payload 完整性。 |
| [`REVIEW-20260815-PHASE-MINUS1-LOCAL-EVIDENCE-MECHANICAL-AUDIT`](<CATALOG.md#review-20260815-phase-minus1-local-evidence-mechanical-audit>) | `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-20260815-7FA2A0E225` | `availability_and_provenance` | `deferred` | — | 原始运行 payload 保持 local_optional；轻量 checkout 可以缺失，恢复或重跑须依照 tracked README 与 manifest。 |
| [`REVIEW-20260815-PHASE-MINUS1-V2-LOCAL-EVIDENCE-REGISTRATION`](<CATALOG.md#review-20260815-phase-minus1-v2-local-evidence-registration>) | `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-V2-20260815-96E16B17C8` | `availability_and_provenance` | `deferred` | — | 高预算 v2 运行仍处于 active 状态；当前 portability anchor 是启动时 CORPUS_ADMISSION 收据，不是终态 evidence manif…<br>原始 journals、logs 与 slice/deep receipts 保持 local_optional；轻量 checkout 可缺失。 |
| [`REVIEW-20260815-SOLVER-REASONING-OUTER-LOOP-GPT-PRO`](<CATALOG.md#review-20260815-solver-reasoning-outer-loop-gpt-pro>) | `DOSSIER-SOLVER-REASONING-OUTER-LOOP-REVIEWS-20260815-D26B592E99` | `targeted_files` | `deferred` | — | 逐字归档与条件式约束登记是否在 typed closure 时拆成两个 dossier 尚未裁决。<br>语义可压缩性、接口可压缩性与构造可分解性仍是待实验的可证伪假设。 |
| [`REVIEW-20260821-COMMON-MODE-BINDING-REVERIFY-RECLOSE`](<CATALOG.md#review-20260821-common-mode-binding-reverify-reclose>) | `DOSSIER-COMMON-MODE-BINDING-REVERIFY-20260820-0268E9394D` | `targeted_files` | `deferred` | — | 维护登记（已接受例外，不是待修项）：strong-status allowlist id 尾号 _295 不作坐标承诺；仅当下游开始把 id 尾号解释为坐标、或 SHA+size…<br>P1.2 proof gate 继续恰 1 issue：production 与 I1 的 pose-optional operation-map 过滤 parity 断言归后批…<br>checker 48 处零 mutation 覆盖、generic-output 重复守卫、token-lock 内鬼模型硬化、strict/closed-package typ… |

## Open intake workflow

| Dossier | 路径 | 打开日 | 生命周期 |
|---|---|---|---|
| `DOSSIER-CANDIDATE-CONDITION-MATRIX-V1-20260818-780443B8C2` | `.artifacts/candidate_condition_matrix_v1_20260818` | `2026-08-18` | `active` |
| `DOSSIER-CFG-RELAXATION-CERTIFICATES-20260818-76C8EC34D8` | `.artifacts/cfg_relaxation_certificates_20260818` | `2026-08-18` | `active` |
| `DOSSIER-CFG-RELAXATION-ENUM-CLOSURE-23X51-20260818-176509E438` | `.artifacts/cfg_relaxation_enum_closure_23x51_20260818` | `2026-08-18` | `active` |
| `DOSSIER-CFG-RELAXATION-IMPL-A-20260817-BE414F298A` | `.artifacts/cfg_relaxation_impl_A_20260817` | `2026-08-17` | `active` |
| `DOSSIER-CFG-RELAXATION-IMPL-B-20260817-77A5280EF9` | `.artifacts/cfg_relaxation_impl_B_20260817` | `2026-08-17` | `active` |
| `DOSSIER-COMMON-MODE-BINDING-REVERIFY-20260820-0268E9394D` | `docs/research/common_mode_binding_reverify_20260820` | `2026-08-20` | `active` |
| `DOSSIER-CPU-L3-PERF-MEASUREMENT-20260820-212859A058` | `.artifacts/cpu_l3_perf_measurement_20260820` | `2026-08-20` | `active` |
| `DOSSIER-GHOST-COND-DIVERGENCE-20260821-3D2338886C` | `.artifacts/ghost_cond_divergence_20260821` | `2026-08-21` | `active` |
| `DOSSIER-GPT-CUT-SHAPES-20260821-745509BF6B` | `.artifacts/gpt_cut_shapes_20260821` | `2026-08-21` | `active` |
| `DOSSIER-GPT-HARVEST-20260818-85692BD024` | `.artifacts/gpt_harvest_20260818` | `2026-08-18` | `active` |
| `DOSSIER-I1-ROUND4-SELF-CHECK-20260820-0CFC3F056C` | `.artifacts/i1_round4_self_check_20260820` | `2026-08-20` | `active` |
| `DOSSIER-NP-LITERATURE-RECON-20260817-C6D0998D78` | `.artifacts/np_literature_recon_20260817` | `2026-08-17` | `active` |
| `DOSSIER-NP-THEOREM-CORRESPONDENCE-20260817-6ADFE32DF1` | `.artifacts/np_theorem_correspondence_20260817` | `2026-08-17` | `active` |
| `DOSSIER-OUTER-LOOP-RECON-20260817-A3301A1D74` | `.artifacts/outer_loop_recon_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P-BLOCKADE-CLIPMAP-20260819-5F53E26B00` | `.artifacts/p_blockade_clipmap_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-BRIDGE-LIVENESS-PROBE-20260819-799812E3E4` | `.artifacts/p_bridge_liveness_probe_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-CLIPMAP-AUDIT-20260819-0CC22B0448` | `.artifacts/p_clipmap_audit_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-CORE-SHELL-PROPOSITION-20260818-C3CC2E9F4F` | `.artifacts/p_core_shell_proposition_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-CSPACE-BLOCKADE-COMPILER-20260818-F304516884` | `.artifacts/p_cspace_blockade_compiler_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-DNF-BRANCH-SOUNDNESS-MINIMAL-CORE-20260819-99AFD08610` | `.artifacts/p_dnf_branch_soundness_minimal_core_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-DNF-COMPLETENESS-AUDIT-20260819-8A148379D6` | `.artifacts/p_dnf_completeness_audit_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-DNF-ENUMERATION-AUDIT-20260819-AC4209EBC5` | `.artifacts/p_dnf_enumeration_audit_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-DNF-REALIZABLE-AUDIT-20260819-9056A4CF0C` | `.artifacts/p_dnf_realizable_audit_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-DNF-REALIZABLE-COMPLETENESS-20260819-F79B0B2A8C` | `.artifacts/p_dnf_realizable_completeness_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-DNF-REALIZABLE-ENUMERATION-20260819-796C6E270A` | `.artifacts/p_dnf_realizable_enumeration_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-DNF-UNIVERSAL-AUDIT-20260819-B7FD9D9756` | `.artifacts/p_dnf_universal_audit_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-DNF-UNIVERSAL-COMPLETENESS-20260819-26F6F7EF75` | `.artifacts/p_dnf_universal_completeness_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-EMITTER-PROVENANCE-RECONCILIATION-20260818-8050D1C018` | `.artifacts/p_emitter_provenance_reconciliation_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-GHOSTFRONT-FAMILY-JUDGMENT-20260818-2441DB4B52` | `.artifacts/p_ghostfront_family_judgment_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-INTERIOR-3X3-AUDIT-20260819-AB3571C590` | `.artifacts/p_interior_3x3_audit_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-INTERIOR-3X3-BOUND-20260819-3503337709` | `.artifacts/p_interior_3x3_bound_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-INTERIOR-BLOCKADE-BOUND-20260819-7F5A5AA51B` | `.artifacts/p_interior_blockade_bound_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-INTERIOR-BOUND-AUDIT-20260819-54D94C5C37` | `.artifacts/p_interior_bound_audit_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-LBBD-30X39-MULTI-INCUMBENT-20260818-0C7F9B4622` | `.artifacts/p_lbbd_30x39_multi_incumbent_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-LBBD-MINIMAL-CORE-TOOLKIT-20260818-8B00079DD2` | `.artifacts/p_lbbd_minimal_core_toolkit_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-MIXED-ENDPOINT-CLOSED-FORM-20260818-2E5F56A8F8` | `.artifacts/p_mixed_endpoint_closed_form_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-MUS-LANDSCAPE-20260820-CC6900A234` | `.artifacts/p_mus_landscape_20260820` | `2026-08-20` | `active` |
| `DOSSIER-P-MUS-LANDSCAPE-ERRATA-20260820-4FB752F398` | `.artifacts/p_mus_landscape_errata_20260820` | `2026-08-20` | `active` |
| `DOSSIER-P-NARROW-CORE-READMISSION-20260819-CD8FDB7CD0` | `.artifacts/p_narrow_core_readmission_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-NOVELTY-L3-CONTRACT-HARDENING-20260818-304523520A` | `.artifacts/p_novelty_l3_contract_hardening_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-NOVELTY-STAGNATION-WINDOWS-20260818-570D7BA230` | `.artifacts/p_novelty_stagnation_windows_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-REINSERTION-AUDIT-20260820-8BB5417ED3` | `.artifacts/p_reinsertion_audit_20260820` | `2026-08-20` | `active` |
| `DOSSIER-P-REINSERTION-GAP-20260819-2C69D7570F` | `.artifacts/p_reinsertion_gap_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-SIGNATURE-COOCCURRENCE-MATRIX-20260819-51366B1E18` | `.artifacts/p_signature_cooccurrence_matrix_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-TRUE-REPAIR-CHAIN-HARDENING-20260818-AF82028E42` | `.artifacts/p_true_repair_chain_hardening_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-TRUE-REPAIR-CONFLICT-EXTRACTION-20260819-DAB640A917` | `.artifacts/p_true_repair_conflict_extraction_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-TRUE-REPLACEMENT-REPAIR-20260818-3044681953` | `.artifacts/p_true_replacement_repair_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P-ZEROPOLE-AUDIT-20260819-7D071A5EF4` | `.artifacts/p_zeropole_audit_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P-ZEROPOLE-DIAGNOSIS-20260819-442FFB6551` | `.artifacts/p_zeropole_diagnosis_20260819` | `2026-08-19` | `active` |
| `DOSSIER-P0-FRONTIER-PROJECTION-20260817-1B1E6F4CB4` | `.artifacts/p0_frontier_projection_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P0-FRONTIER-RERUN-20260818-DDAC26E3F1` | `.artifacts/p0_frontier_rerun_20260818` | `2026-08-18` | `active` |
| `DOSSIER-P1-RESTRICTED-WITNESS-CONSTRUCTION-20260817-39AB02A7C6` | `docs/research/p1_restricted_witness_construction_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P1-WITNESS-CONSTRUCTION-20260817-D06675346E` | `.artifacts/p1_witness_construction_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P1B-JOINT-POWER-REPAIR-20260817-8F6B7DFD94` | `.artifacts/p1b_joint_power_repair_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P1B-JOINT-POWER-REPAIR-20260817-C459AE609C` | `docs/research/p1b_joint_power_repair_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P3-POWER-BLOCKADE-VALIDATION-20260817-3DC75D9C7A` | `docs/research/p3_power_blockade_validation_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P3-POWER-BLOCKADE-VALIDATION-20260817-DA81BA8459` | `.artifacts/p3_power_blockade_validation_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P4-BLOCKADE-FAMILY-ABSTRACTION-20260817-284FD8D3B0` | `docs/research/p4_blockade_family_abstraction_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P4-BLOCKADE-FAMILY-ABSTRACTION-20260817-5B9F642CB4` | `.artifacts/p4_blockade_family_abstraction_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P5-HORIZONTAL-CANARY-20260817-44EADE5C7E` | `.artifacts/p5_horizontal_canary_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P5-HORIZONTAL-LOWERING-CANARY-20260817-3DBC7800A0` | `docs/research/p5_horizontal_lowering_canary_20260817` | `2026-08-17` | `active` |
| `DOSSIER-P5-RETRIAL-20260821-428061A300` | `.artifacts/p5_retrial_20260821` | `2026-08-21` | `active` |
| `DOSSIER-POLE-GATE-CANARY-20260821-7F3338D139` | `.artifacts/pole_gate_canary_20260821` | `2026-08-21` | `active` |
| `DOSSIER-POSTMEM-BLIND-COLLISION-20260818-4DB4F7129F` | `.artifacts/postmem_blind_collision_20260818` | `2026-08-18` | `active` |
| `DOSSIER-POSTMEM-BLIND-SAMPLING-20260817-2127AF445D` | `.artifacts/postmem_blind_sampling_20260817` | `2026-08-17` | `active` |
| `DOSSIER-SIXPRED-UPPER-NEXT-BAND-20260821-CAA91F9B9A` | `.artifacts/sixpred_upper_next_band_20260821` | `2026-08-21` | `active` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-20260815-7FA2A0E225` | `.artifacts/solver_reasoning_outer_loop_phase_minus1_20260815` | `2026-08-15` | `active` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-PHASE-MINUS1-V2-20260815-96E16B17C8` | `.artifacts/solver_reasoning_outer_loop_phase_minus1_v2_20260815` | `2026-08-15` | `active` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-REVIEWS-20260815-D26B592E99` | `docs/research/solver_reasoning_outer_loop_reviews_20260815` | `2026-08-15` | `active` |
| `DOSSIER-SOLVER-REASONING-OUTER-LOOP-W0-UNARY-CANARY-20260816-40F7F16A22` | `.artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816` | `2026-08-16` | `active` |
| `DOSSIER-TRI-PLANE-MODEL-V2-20260816-71A3625ABB` | `docs/research/tri_plane_model_v2_20260816` | `2026-08-16` | `active` |

## Triage group

| Group | 处置 | 优先级 | Dossier 数 | 相关知识 |
|---|---|---:|---:|---|
| [`TRIAGE-CUT-SOLVER-TRACKED-LONGTAIL`](#triage-cut-solver-tracked-longtail) | `historical_semantic_queue` | `normal` | 14 | [`CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION`](<CATALOG.md#claim-raw-eligible-events-required-for-separation-evaluation>)<br>[`CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`](<CATALOG.md#claim-lever-verdicts-are-item-and-revision-bounded>)<br>[`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](<CATALOG.md#claim-generic-cp-sat-separation-impossibility-open>)<br>[`REVIEW-20260811-NONCERT-CUTS-AB16`](<CATALOG.md#review-20260811-noncert-cuts-ab16>)<br>[`REVIEW-20260811-RAB-SEP-PROMOTION-BATCH4`](<CATALOG.md#review-20260811-rab-sep-promotion-batch4>)<br>[`REVIEW-20260811-PARADIGM-LEVER-HISTORY-BATCH4`](<CATALOG.md#review-20260811-paradigm-lever-history-batch4>) |
| [`TRIAGE-DOCUMENTATION-GOVERNANCE-TRACKED-LONGTAIL`](#triage-documentation-governance-tracked-longtail) | `historical_semantic_queue` | `low` | 2 | — |
| [`TRIAGE-FORMAL-VERIFICATION-TRACKED-LONGTAIL`](#triage-formal-verification-tracked-longtail) | `historical_semantic_queue` | `normal` | 7 | [`CLAIM-R4-LEX-BAND-2084-UNSAT`](<CATALOG.md#claim-r4-lex-band-2084-unsat>)<br>[`CLAIM-SMM4-LEX-BAND-COMPOSITION-2086`](<CATALOG.md#claim-smm4-lex-band-composition-2086>)<br>[`REVIEW-20260811-B1-R4-PB-BATCH2`](<CATALOG.md#review-20260811-b1-r4-pb-batch2>) |
| [`TRIAGE-LOCAL-CUT-SOLVER-EXPERIMENTS`](#triage-local-cut-solver-experiments) | `local_optional_queue` | `low` | 1 | [`CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT`](<CATALOG.md#claim-ab16-no-scientific-cut-result>)<br>[`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](<CATALOG.md#claim-budget-exhaustion-is-unknown-not-fixed-point>)<br>[`REVIEW-20260811-AB16-ARMS-BATCH3`](<CATALOG.md#review-20260811-ab16-arms-batch3>)<br>[`REVIEW-20260811-SOLVER-RETHINK-BATCH3`](<CATALOG.md#review-20260811-solver-rethink-batch3>) |
| [`TRIAGE-LOCAL-DELIVERY`](#triage-local-delivery) | `local_optional_queue` | `low` | 1 | [`CLAIM-CERTIFIED-THEOREM-SCOPE`](<CATALOG.md#claim-certified-theorem-scope>) |
| [`TRIAGE-LOCAL-OPTIONAL-MISC`](#triage-local-optional-misc) | `local_optional_queue` | `low` | 24 | [`CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`](<CATALOG.md#claim-lever-verdicts-are-item-and-revision-bounded>) |
| [`TRIAGE-LOCAL-P2-THROUGHPUT`](#triage-local-p2-throughput) | `local_optional_queue` | `normal` | 2 | [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](<CATALOG.md#claim-p2-throughput-research-ledger>)<br>[`CLAIM-MIXFLOW-U01-GUARD-FORK-BENEFIT-REFUTED`](<CATALOG.md#claim-mixflow-u01-guard-fork-benefit-refuted>)<br>[`REVIEW-20260811-P2-SPECIALIZED-BATCH4`](<CATALOG.md#review-20260811-p2-specialized-batch4>)<br>[`REVIEW-20260811-MIXFLOW-FIXTURE-CORRECTION-BATCH4`](<CATALOG.md#review-20260811-mixflow-fixture-correction-batch4>) |
| [`TRIAGE-LOCAL-RULES-SEMANTICS`](#triage-local-rules-semantics) | `local_optional_queue` | `normal` | 3 | [`CLAIM-EMPTY-RECTANGLE-STRICT`](<CATALOG.md#claim-empty-rectangle-strict>)<br>[`CLAIM-MIXED-TERMINAL-TRIPARTITION`](<CATALOG.md#claim-mixed-terminal-tripartition>)<br>[`REVIEW-20260811-RULES-AUDIT-BATCH4`](<CATALOG.md#review-20260811-rules-audit-batch4>) |
| [`TRIAGE-LOCAL-UPPER-BOUND-AND-BAND22`](#triage-local-upper-bound-and-band22) | `local_optional_queue` | `normal` | 10 | [`CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE`](<CATALOG.md#claim-band22-v0a-strict-hole-incompatible>)<br>[`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](<CATALOG.md#claim-six-predicate-research-ledger>)<br>[`REVIEW-20260811-BAND22-STRICT-HOLE-PROBE-BATCH2`](<CATALOG.md#review-20260811-band22-strict-hole-probe-batch2>)<br>[`REVIEW-20260811-SMM-FRESH-AUTHORITY-BATCH2`](<CATALOG.md#review-20260811-smm-fresh-authority-batch2>) |
| [`TRIAGE-LOCAL-WITNESS`](#triage-local-witness) | `local_optional_queue` | `normal` | 6 | [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](<CATALOG.md#claim-certified-existence-open>)<br>[`CLAIM-W0-POWER-OBSTRUCTION-REQUIRES-DECLARED-HEIGHT-PURITY`](<CATALOG.md#claim-w0-power-obstruction-requires-declared-height-purity>)<br>[`REVIEW-20260811-WITNESS-CONSTRUCTOR-BATCH4`](<CATALOG.md#review-20260811-witness-constructor-batch4>)<br>[`REVIEW-20260811-W0-POWER-COUNTEREXAMPLE-BATCH4`](<CATALOG.md#review-20260811-w0-power-counterexample-batch4>) |
| [`TRIAGE-OTHER-TRACKED-LONGTAIL`](#triage-other-tracked-longtail) | `historical_semantic_queue` | `low` | 18 | [`CLAIM-LEVER-VERDICTS-ARE-ITEM-AND-REVISION-BOUNDED`](<CATALOG.md#claim-lever-verdicts-are-item-and-revision-bounded>) |
| [`TRIAGE-P1-2-PROOF-CHAIN-FAMILY`](#triage-p1-2-proof-chain-family) | `family_context_only` | `normal` | 67 | [`CLAIM-CERTIFIED-THEOREM-SCOPE`](<CATALOG.md#claim-certified-theorem-scope>)<br>[`CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS`](<CATALOG.md#claim-cut-framework-production-status>)<br>[`CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT`](<CATALOG.md#claim-budget-exhaustion-is-unknown-not-fixed-point>)<br>[`REVIEW-20260811-P1-2-V99-CLOSE-KERNEL`](<CATALOG.md#review-20260811-p1-2-v99-close-kernel>) |
| [`TRIAGE-P2-THROUGHPUT-TRACKED-LONGTAIL`](#triage-p2-throughput-tracked-longtail) | `historical_semantic_queue` | `normal` | 2 | [`CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER`](<CATALOG.md#claim-p2-throughput-research-ledger>)<br>[`CLAIM-P2-MIN-SIDE-UPPER-OPEN`](<CATALOG.md#claim-p2-min-side-upper-open>)<br>[`REVIEW-20260811-P2-AREA-BOUND-BATCH2`](<CATALOG.md#review-20260811-p2-area-bound-batch2>)<br>[`REVIEW-20260811-P2-SPECIALIZED-BATCH4`](<CATALOG.md#review-20260811-p2-specialized-batch4>) |
| [`TRIAGE-UPPER-BOUND-TRACKED-LONGTAIL`](#triage-upper-bound-tracked-longtail) | `family_context_only` | `normal` | 5 | [`CLAIM-SIX-PREDICATE-RESEARCH-LEDGER`](<CATALOG.md#claim-six-predicate-research-ledger>)<br>[`CLAIM-R4-NECESSARY-DIMENSION-INEQUALITY`](<CATALOG.md#claim-r4-necessary-dimension-inequality>)<br>[`CLAIM-SMM-209-EXCLUDES-22X54`](<CATALOG.md#claim-smm-209-excludes-22x54>)<br>[`REVIEW-20260811-R4-RESPONSE-BATCH2`](<CATALOG.md#review-20260811-r4-response-batch2>)<br>[`REVIEW-20260811-SMM-STRICT-BATCH2`](<CATALOG.md#review-20260811-smm-strict-batch2>)<br>[`REVIEW-20260811-SMM-FRESH-AUTHORITY-BATCH2`](<CATALOG.md#review-20260811-smm-fresh-authority-batch2>) |
| [`TRIAGE-WITNESS-TRACKED-LONGTAIL`](#triage-witness-tracked-longtail) | `historical_semantic_queue` | `normal` | 3 | [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](<CATALOG.md#claim-certified-existence-open>)<br>[`CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN`](<CATALOG.md#claim-witness-restricted-pole-domains-infeasible-full-domain-open>)<br>[`REVIEW-20260811-WITNESS-CONSTRUCTOR-BATCH4`](<CATALOG.md#review-20260811-witness-constructor-batch4>)<br>[`REVIEW-20260811-W0-POWER-COUNTEREXAMPLE-BATCH4`](<CATALOG.md#review-20260811-w0-power-counterexample-batch4>) |

<a id="triage-cut-solver-tracked-longtail"></a>
### TRIAGE-CUT-SOLVER-TRACKED-LONGTAIL

- **处置 / 优先级：** `historical_semantic_queue` / `normal`
- **理由：** 这些 solver/cut cheap gate、PoC 与旧实验未被逐份语义回填；已登记 NO-GO、实验边界和分离机制 claim 只覆盖其明示证据，不代表整组方法被判死。
- **重开触发：** 某条路线复活、使用新 inner/telemetry 重跑，或需要证明 generic propagation 与领域 separator 的能力差异时。
- **Dossier：** `DOSSIER-B1-POSE-BOOL-PHASE0-20260517-DBAB7753FE；DOSSIER-BENDERS-SYMMETRY-PHASE0-20260520-D5A77E6403；DOSSIER-CAND-C-COLUMN-GENERATION-PHASE0-20260521-6F6C808E65；DOSSIER-CUT-FRAMEWORK-REVIEW-GPT56PRO-20260710-C6C896B93B；DOSSIER-L14-WEIGHTED-OCCUPANCY-POC-20260516-6AF12BD79C；DOSSIER-NONCERT-CUTS-AB-TRUST-20260723-92D0F8BDCA；DOSSIER-NONCERT-CUTS-AB-TRUST-GATE1-V3-20260723-A086F47E85；DOSSIER-NONCERT-CUTS-AB-TRUST-GATE1-V4-20260724-CBD18919D9；DOSSIER-P3-B-DESIGN-V2-20260521-F2C6312F04；DOSSIER-PCR-CUT-PATCH-ROUTING-CONFLICT-20260519-0F2552BB75；DOSSIER-PROD-SCALE-SPIKE-DESIGN-20260525-770C030C5E；DOSSIER-PROFILES-A2B11892A9；DOSSIER-SAC-HULL-SEPARATOR-CAPACITY-20260518-671A7E1193；DOSSIER-SETPACKING-PROVER-POC-20260517-A6B0980958`

<a id="triage-documentation-governance-tracked-longtail"></a>
### TRIAGE-DOCUMENTATION-GOVERNANCE-TRACKED-LONGTAIL

- **处置 / 优先级：** `historical_semantic_queue` / `low`
- **理由：** 这些旧文档树/项目瓶颈审计是本次文档系统设计的历史证据，不作为当前框架定义；当前定义由 manifest、invariants、ARCHITECTURE、MAINTAINING 与 ADR 提供。
- **重开触发：** 需要追溯某项框架设计的原始 finding，或第三阶段清理旧入口时。
- **Dossier：** `DOSSIER-DOC-TREE-FULL-AUDIT-20260604-80C4D1938D；DOSSIER-PROJECT-BOTTLENECK-AUDIT-20260702-9E995CC2F0`

<a id="triage-formal-verification-tracked-longtail"></a>
### TRIAGE-FORMAL-VERIFICATION-TRACKED-LONGTAIL

- **处置 / 优先级：** `historical_semantic_queue` / `normal`
- **理由：** 这些形式化语言、sidecar、proof logging 与 family formalizability 材料尚未逐份提炼；现有 PB/VeriPB 上界 claim 只覆盖其登记证据。
- **重开触发：** 某一 formalization 设计进入实现，或新的 proof-producing authority 依赖这些材料时。
- **Dossier：** `DOSSIER-FORMAL-VERIFICATION-LANGUAGES-ASSESSMENT-20260711-CCCFF888D8；DOSSIER-P3-0-FORMAL-REVIEWS-20260705-D6CB85EB2A；DOSSIER-P3-0-FORMAL-VERIFICATION-HEAD-START-DESIGN-V1-B01927D599；DOSSIER-P3-0B-FAMILY-FORMALIZABILITY-SURVEY-20260705-37E896037C；DOSSIER-P3-0B-FORMAL-REVIEWS-ROUND2-20260705-23A40FE2C2；DOSSIER-P3-0C-BINDING-PB-SIDECAR-DESIGN-V1-985EA9D7F5；DOSSIER-PROOF-LOGGING-SCOUT-20260718-2B4BF502F3`

<a id="triage-local-cut-solver-experiments"></a>
### TRIAGE-LOCAL-CUT-SOLVER-EXPERIMENTS

- **处置 / 优先级：** `local_optional_queue` / `low`
- **理由：** 这些 local solver/cut review、tuning 与 validation 包未逐份提炼；TIMEOUT、零激活、工程接线或单次 gate 结果都不自动成为方法级结论。
- **重开触发：** 实验获得 faithful baseline、raw eligible telemetry、独立验证或进入现役路线时。
- **Dossier：** `DOSSIER-V28-GPT-REVIEW-93871F1F70`

<a id="triage-local-delivery"></a>
### TRIAGE-LOCAL-DELIVERY

- **处置 / 优先级：** `local_optional_queue` / `low`
- **理由：** 这些 local delivery/IP adapter 材料保存运行和交付上下文，不授予数学、owner 或 production authority。
- **重开触发：** 对应工具或交付包重新进入 release/复验路径时。
- **Dossier：** `DOSSIER-IP-CD-SEMANTICS-20260805-7002030E2F`

<a id="triage-local-optional-misc"></a>
### TRIAGE-LOCAL-OPTIONAL-MISC

- **处置 / 优先级：** `local_optional_queue` / `low`
- **理由：** 这些 local-only 会议、计划、接管、残件与实验包保持可发现，但尚未逐份语义回填；本地存在性和文件名不构成 authority。
- **重开触发：** 某个包被当前 claim/decision、实现变更或审计明确引用时。
- **Dossier：** `DOSSIER-AB16-SLIMDOWN-20260801-DFA55C71DB；DOSSIER-ADAPT-BATCH-GATES-EC7F30EDA7；DOSSIER-APX-E-GATE-REVIEW-20260810-1E0BCC6818；DOSSIER-BATCH-C-LEFTOVERS-20260714-EAC2289AC0；DOSSIER-BATCH4-20260718-37902EF1B5；DOSSIER-CLEANROOM-R3-ADVERSARIAL-A6B46333B2；DOSSIER-CODEX-TAKEOVER-3784FD3D07；DOSSIER-DOC-SWEEP-20260717-54167D9495；DOSSIER-FC-LIFT-AB-20260716-5FD5604614；DOSSIER-GHOST-STRICT-FIX-PLAN-20260805-03154569FD；DOSSIER-GPT-PRO-REVIEW-BATCH-20260807-2DAE56A307；DOSSIER-GPT-PRO-REVIEW-BATCH-20260808-A687A90BB0；DOSSIER-H20-ROW-POWER-ORACLE-20260803-28FC39F69B；DOSSIER-IP-ADAPTER-V3-20260805-463C50D116；DOSSIER-LAYER2-GATES-EC926F69A7；DOSSIER-M5-REVALIDATION-20260803-40F267675F；DOSSIER-MEMSYS-MEETING-20260808-1BB4142581；DOSSIER-MERGE-CODEX-20260801-E0761ADC63；DOSSIER-PHASE3B-ACCEL-TUNING-64039CA2F2；DOSSIER-PHASE3B-AI-ACCEL-20260429-4CCE6170E3；DOSSIER-PROOF-SCOUT-20260718-7C6AD03F03；DOSSIER-PRUNE-V2-20260803-A4F09E4468；DOSSIER-RAB-DRILL-20260716-132E17F171；DOSSIER-V46-VALIDATION-100519A7C4`

<a id="triage-local-p2-throughput"></a>
### TRIAGE-LOCAL-P2-THROUGHPUT

- **处置 / 优先级：** `local_optional_queue` / `normal`
- **理由：** 这些 local P2/mixflow 包是提案、施工或外审证据；当前 P2 ledger 与 mixflow validity claim 只在登记 scope 内复用。
- **重开触发：** mixflow 实现语义、P2 ledger 或相关 fixture/authority 变化时。
- **Dossier：** `DOSSIER-MIXFLOW-REVIEW-PACK-20260806-8BC80DB22D；DOSSIER-MIXFLOW-U01-20260807-0F66A1F37E`

<a id="triage-local-rules-semantics"></a>
### TRIAGE-LOCAL-RULES-SEMANTICS

- **处置 / 优先级：** `local_optional_queue` / `normal`
- **理由：** 这些 local-only 语义 freeze/reseal/axiom 包是可选证据或提案，不替代 canonical rules、owner decision 或 tracked adjudication。
- **重开触发：** canonical rules、语义裁决或 reseal provenance 需要逐包复核时。
- **Dossier：** `DOSSIER-AXIOM-ANALYSIS-20260806-A86B1853BB；DOSSIER-CANONICAL-RESEAL-20260808-126986753E；DOSSIER-EMPTINESS-RITUAL-20260805-7CDD6F4EA4`

<a id="triage-local-upper-bound-and-band22"></a>
### TRIAGE-LOCAL-UPPER-BOUND-AND-BAND22

- **处置 / 优先级：** `local_optional_queue` / `normal`
- **理由：** 这些 band22/strict redesign/simulation 本地包是候选、交付或复验材料；它们不能替代 strict-hole 排除、SMM4 authority 或 tracked theorem report。
- **重开触发：** band22 候选被重新用于 witness/lower bound，或 strict-hole/authority 语义变化时。
- **Dossier：** `DOSSIER-BAND22-ADMISSION-SIM-20260805-81C82FE8AA；DOSSIER-BAND22-FAITHFUL-SIM-20260805-8A9863F99B；DOSSIER-BAND22-FLOW-ACCOUNT-20260805-9B415D409F；DOSSIER-BAND22-HEADLESS-SIM-20260805-B287B4FBCC；DOSSIER-BAND22-R4-PREP-20260806-47C18A75BE；DOSSIER-BAND22-REGISTRATION-20260805-5D2448DDF7；DOSSIER-BAND22-REGISTRATION-V2-20260805-16522D6183；DOSSIER-BAND22-SIM-EXPORT-20260805-32DC974A11；DOSSIER-BAND22-STRICT-REDESIGN-PACK-20260805-F8A8392DAF；DOSSIER-BAND22-STRICT-REDESIGN-REPLIES-20260805-2F5380CA05`

<a id="triage-local-witness"></a>
### TRIAGE-LOCAL-WITNESS

- **处置 / 优先级：** `local_optional_queue` / `normal`
- **理由：** 这些 W0/witness 本地探针与交付包属于构造证据长尾；whole-layout existence 仍 OPEN，局部可行/不可行不能外推。
- **重开触发：** 本地探针产生可验收 witness、独立反例或被 tracked dossier 正式引用时。
- **Dossier：** `DOSSIER-W0-CONSULT-PACKS-20260804-D95CAAE8A6；DOSSIER-W0-FIXRERUN-20260804-7239554A2D；DOSSIER-W0-FRONT-AWARE-20260803-1040F8BE76；DOSSIER-W0-METHOD-RFP-20260803-1CBCC9501E；DOSSIER-W0-PROBE-HOLE-20260804-11D39E624B；DOSSIER-WITNESS-20260717-1D5FD48183`

<a id="triage-other-tracked-longtail"></a>
### TRIAGE-OTHER-TRACKED-LONGTAIL

- **处置 / 优先级：** `historical_semantic_queue` / `low`
- **理由：** 这些 tracked 历史设计、文献、smoke、审计、方法论汇编与评审材料尚未逐份语义提炼；保留在显式队列中，不能被“已登记”误读成“已审完”或“无结论”。
- **重开触发：** 它们被新的 claim、实现路线、外审问题或历史追溯重新引用时；落地迁移登记 A12/A13：来源归档 docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/27_status_dashboard.md，SHA-256 2f6df966769372a7f412cbf2ba14ccb2c1f6caae841b1f5366d7d0691d5cce40；A12 触发器为「Chain B/C 批顺走」与「挂 redesign 批 5/6」；A13 交接坐标为「zmd_文档补丁链落地评审交接_20260813」。
- **Dossier：** `DOSSIER-B1-RABSEP-ROUTING-AWARE-BINDING-20260518-E08AD6BF23；DOSSIER-D-STEP2-HINT-TRIALS-20260516-8794B39D8A；DOSSIER-LITERATURE-REVIEW-PAPERS-20260524-F002A45263；DOSSIER-METHODOLOGY-COMPILATION-20260814-BF49D11CCD；DOSSIER-P1-3-A-BATCH0-20260709-25C725D5B0；DOSSIER-P1-3-BATCH1-DESIGN-20260710-57F92742D0；DOSSIER-P1-3-F5-ORBIT-LIFT-SOUNDNESS-DESIGN-V1-291502415A；DOSSIER-P1-3-F5-ORBIT-LIFT-SOUNDNESS-DESIGN-V2-D1ACE22754；DOSSIER-P1-3-M4-RECON-20260708-3819BDF48B；DOSSIER-P1-3-M6-DIAGNOSIS-20260709-7C9DEFFA5D；DOSSIER-P2-DESIGN-EXTERNAL-REVIEWS-20260704-54F28681D7；DOSSIER-P3-0C-SIDECAR-REVIEWS-20260705-728E34B496；DOSSIER-P3-B-DESIGN-REVIEW-V14-20260521-24BD84A607；DOSSIER-PLANE-MIXING-AUDIT-20260813-176281B3F4；DOSSIER-Q1-INFEASIBILITY-CLASS-TAXONOMY-DESIGN-V1-69B91DF7A9；DOSSIER-TERMINAL-NO-SOLUTION-EVIDENCE-CONTRACT-DESIGN-V1-A9EA1B8AA3；DOSSIER-TERMINAL-NO-SOLUTION-EVIDENCE-CONTRACT-DESIGN-V2-473B668ADD；DOSSIER-V8-ANCHOR-SLICING-SMOKE-20260516-66643824CB`

<a id="triage-p1-2-proof-chain-family"></a>
### TRIAGE-P1-2-PROOF-CHAIN-FAMILY

- **处置 / 优先级：** `family_context_only` / `normal`
- **理由：** P1.2 的多轮 review/reset/sealing 文件构成历史治理与证据链上下文；当前 gate 与 proof obligations 由机器源和已审 close-kernel 节点表达。这里不把整族文件视为逐份语义审阅。
- **重开触发：** 某一历史 finding 再次影响当前 proof obligation、phase gate、certified surface 或 release claim 时。
- **Dossier：** `DOSSIER-CAND-C-COLUMN-GENERATION-PHASE1-20260521-4E809F3AB7；DOSSIER-GEMINI-CROSS-CHECK-PHASE1-2-F5-ROUND3-20260524-F197C69BC0；DOSSIER-P1-2-SPIKE-SIZING-GATE-20260601-C56E677966；DOSSIER-P1-2-V30-CANDIDATE-REVIEW-RESET-D5557D4DD7；DOSSIER-P1-2-V31-CANDIDATE-REVIEW-RESET-8EB314EEA9；DOSSIER-P1-2-V31-POSTMORTEM-PROOF-OBLIGATION-CONSOLIDATION-B8536C155B；DOSSIER-P1-2-V31-V46-FINDING-TAXONOMY-8B3B767053；DOSSIER-P1-2-V37-PHASE-GATE-PROVENANCE-HARDENING-2F7734A113；DOSSIER-P1-2-V38-PHASE-GATE-PACKAGE-IDENTITY-A4399F1D27；DOSSIER-P1-2-V44-PHASE-GATE-SOURCE-AUTHORITY-AND-METADATA-RESET-7036E4E74D；DOSSIER-P1-2-V45-PHASE-GATE-MARKUP-AND-GIT-AUTHORITY-RESET-17F015AF60；DOSSIER-P1-2-V46-PHASE-GATE-GIT-AUTHORITY-AND-METADATA-RESET-33949AE9C9；DOSSIER-P1-2-V50-MANUAL-PHASE-GATE-SIMPLIFICATION-3D7469FFC5；DOSSIER-P1-2-V56-CERTIFIED-CUT-REPLAY-CONSOLIDATION-D34374EFFA；DOSSIER-P1-2-V58-CONDITION-REQUIRED-CUT-ANCHOR-VALIDATION-3F6EB607C8；DOSSIER-P1-2-V59-CONDITION-REQUIRED-CUT-DOMAIN-VALIDATION-FC7B10C2FC；DOSSIER-P1-2-V60-MASTER-DOMAIN-CONTRACT-996F05F604；DOSSIER-P1-2-V61-MASTER-DOMAIN-CANDIDATE-FRONTIER-CONTRACT-9A8B2351BE；DOSSIER-P1-2-V62-FRONTIER-TERMINAL-EVIDENCE-AND-OUTER-MASTER-DOM-BDCFA7A310；DOSSIER-P1-2-V63-TERMINAL-EVIDENCE-EXPORT-BOUNDARY-REVIEW-C1B9CAC680；DOSSIER-P1-2-V64-POWER-WITNESS-REPRESENTATION-ENV-GUARD-1E7C6CB745；DOSSIER-P1-2-V66-CERTIFIED-LIFECYCLE-EVIDENCE-CONSOLIDATION-CAF85D6BDF；DOSSIER-P1-2-V66-STALE-DELIVERY-ARTIFACT-GUARD-E897C29E8C；DOSSIER-P1-2-V73-CERTIFIED-SURFACE-VERIFIER-CONSOLIDATION-7AA51E1A9F；DOSSIER-P1-2-V74-CERTIFIED-SURFACE-AUTHORITY-HARDENING-91A96BFE49；DOSSIER-P1-2-V75-TERMINAL-FRONTIER-EVIDENCE-SEALING-C43D367D50；DOSSIER-P1-2-V76-PROJECT-BOUND-TERMINAL-EVIDENCE-43DCB88753；DOSSIER-P1-2-V77-DELIVERY-MANIFEST-WRITER-AUTHORITY-9337E8274B；DOSSIER-P1-2-V78-CERTIFIED-MANIFEST-WRITER-CANONICAL-SURFACE-14CBB05590；DOSSIER-P1-2-V79-TERMINAL-DOMAIN-AXIS-SEALING-CB3497A612；DOSSIER-P1-2-V80-DENY-UNKNOWN-CERTIFIED-SURFACE-11A22CC93C；DOSSIER-P1-2-V81-PARTIAL-PRECHECK-AND-RELEASE-CLAIM-SEALING-4FA1510135；DOSSIER-P1-2-V82-ORIENTED-DOMAIN-AND-CUT-REPLAY-SEALING-4A8EF4883C；DOSSIER-P1-2-V83-GEOMETRY-WITNESS-NOGOOD-SCOPE-AND-LOADER-SEALIN-428112A0D6；DOSSIER-P1-2-V84-LAYOUT-OPTIMALITY-AND-ARTIFACT-BOUNDARY-SEALING-2646648D75；DOSSIER-P1-2-V85-REQUIRED-OPTIONAL-TERMINAL-SEALING-0C5E057996；DOSSIER-P1-2-V86-POWER-WITNESS-TERMINAL-SEALING-209B19CC9E；DOSSIER-P1-2-V87-ANCHOR-AND-POLE-IRREDUNDANCY-SEALING-252F310360；DOSSIER-P1-2-V88-GHOST-ANCHOR-REQUIRED-SEALING-D1943B9A4D；DOSSIER-P1-2-V89-GHOST-PICK-TERMINAL-BINDING-SEALING-C6B2882B47；DOSSIER-P1-2-V90-FINAL-RESULT-FIELD-ALLOWLIST-SEALING-81D82D7C67；DOSSIER-P1-2-V91-NESTED-PUBLIC-FIELD-SEALING-4D91AABA1A；DOSSIER-P1-2-V92-RELEASE-STATUS-ALLOWLIST-SEALING-3C2335E2DC；DOSSIER-P1-2-V93-NOTE-AND-SOLUTION-ENTRY-SEALING-3ECFEAADAD；DOSSIER-P1-2-V94-PROTOCOL-STORAGE-SURPLUS-SEALING-D2DDA99FE5；DOSSIER-P1-2-V95-OPTIONAL-METADATA-AND-STOP-REASON-SEALING-9738EDCE9C；DOSSIER-P1-2-V96-SYMLINK-ANCESTOR-BOUNDARY-SEALING-076F167DB3；DOSSIER-P1-2-V97-CANONICAL-CHECKPOINT-AUTHORITY-SEALING-CE3B241BB4；DOSSIER-P1-2-V98-B5A-SYMLINK-AUTHORITY-SEALING-E71458350B；DOSSIER-P1-2B-F2-F4-GEMINI-ROUND1-20260524-948D3BB9A8；DOSSIER-P1-2B-F2-F4-GEMINI-ROUND2-20260524-016B519BD5；DOSSIER-P1-2B-F2-F4-GEMINI-ROUND3-20260524-A342B2A1F0；DOSSIER-P1-2B-F3-GEMINI-ROUND1-20260526-655B7B3DF6；DOSSIER-P1-2B-F3-GEMINI-ROUND2-20260526-3304F1F0AA；DOSSIER-P1-2B-F6-SHAPE-PACKING-HALL-GEMINI-ROUND1-20260525-824FA5AE3B；DOSSIER-P1-2B-F6-SHAPE-PACKING-HALL-GEMINI-ROUND2-20260525-7550CF55CC；DOSSIER-P1-2B-F6-SHAPE-PACKING-HALL-GEMINI-ROUND3-20260525-7CFD3F9A5E；DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND1-20260525-DCCCF931FA；DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND2-20260525-111B62C30A；DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND3-20260525-975688FCEE；DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND4-20260525-99108B2CDC；DOSSIER-P1-2B-F8-POWER-GRID-REACH-GEMINI-ROUND5-20260525-9F2E264F77；DOSSIER-P1-2B-F9-DENSITY-ENVELOPE-GEMINI-ROUND1-20260524-069C3F5DE0；DOSSIER-P1-2B-F9-DENSITY-ENVELOPE-GEMINI-ROUND2-20260524-C00FC1FF2B；DOSSIER-P1-2B-F9-DENSITY-ENVELOPE-GEMINI-ROUND3-20260524-2F6134754D；DOSSIER-P1-2B-MINI-STEP-8-SPIKE-20260525-5D74B8309D；DOSSIER-PHASE1-2-GPT-PRO-AUDIT-20260525-84DB22A832`

<a id="triage-p2-throughput-tracked-longtail"></a>
### TRIAGE-P2-THROUGHPUT-TRACKED-LONGTAIL

- **处置 / 优先级：** `historical_semantic_queue` / `normal`
- **理由：** 这些 tracked 设计、评审与专项材料位于 P2.0 吞吐族，但未逐份提炼；当前可复用数学结论由 area-bound 与 specialized reviews 及 P2 ledger 承载。
- **重开触发：** P2.0 语义进入实现、min_side 获得上界，或这些设计稿重新成为现役路线时。
- **Dossier：** `DOSSIER-P2-0-THROUGHPUT-CERTIFICATION-PARADIGM-DESIGN-V1-1282665D68；DOSSIER-P2-0-THROUGHPUT-CERTIFICATION-PARADIGM-DESIGN-V2-AB7D01DE56`

<a id="triage-upper-bound-tracked-longtail"></a>
### TRIAGE-UPPER-BOUND-TRACKED-LONGTAIL

- **处置 / 优先级：** `family_context_only` / `normal`
- **理由：** 这些 tracked 文件属于 R4/SMM/band22 等上界家族的前身、交付或复核上下文；现役上界 claim 已由定点审阅拆解。单个 dossier 仍未自动获得“无新结论”判定。
- **重开触发：** 上界作用域、冻结实例、strict-hole 语义或 formal proof band 变化时。
- **Dossier：** `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-20260724-684AF89404；DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-AUTHORITY-RECOVERY-20260724-9E688ADD0E；DOSSIER-BAND22-REGISTRATION-20260805-C053405AC5；DOSSIER-BAND22-SIM-EXPORT-20260805-9A43971884；DOSSIER-R4-EXTERNAL-BRAIN-HANDOFF-20260722-4A5CA75F11`

<a id="triage-witness-tracked-longtail"></a>
### TRIAGE-WITNESS-TRACKED-LONGTAIL

- **处置 / 优先级：** `historical_semantic_queue` / `normal`
- **理由：** 这些 tracked 构造、smoke、W0 与证据合同材料属于下界/见证长尾；whole-layout existence 仍 OPEN，已审 witness constructor 只覆盖明确列出的候选域与结果。
- **重开触发：** 出现 geometry_ready/whole-layout witness、新的 W0 结构定理，或终局无解证书合同被采用时。
- **Dossier：** `DOSSIER-LAYOUT-INVARIANT-CERT-PHASE0-20260520-5DA45C1506；DOSSIER-V10-WITNESS-PREFLIGHT-SMOKE-20260516-1FA7D0C7BB；DOSSIER-W0-POWER-CYCLE-DOMINO-D6-20260728-40A9A51629`

## 维护纪律

- legacy dossier 获得真实语义审阅后，新增 current review，并把它从 triage group 中移除；两步必须在同一变更中完成。
- 新 dossier 以 open workflow 登记；open workflow 可以已经拥有 current review，但仍保持 active 且不进入 triage。关闭时必须在同一 Git-visible transaction 中新增或更新 current review，并写入 typed closure。
- `availability_and_provenance` 只允许用于缺失的 local-optional 根，结果必须保持 `deferred`，不得计入 semantic review coverage。
- 要断言一个 dossier 没有可复用结论，必须写 `outcome=no_reusable_claim` 的语义 review；不能从 triage disposition 推断。
- 完整 claim、review 与 evidence 详情见 [CATALOG](<CATALOG.md>)；按主题下钻见 [TOPIC_INDEX](<TOPIC_INDEX.md>)。
