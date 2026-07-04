# P2.0 throughput certification paradigm v2.1 final review

## Overall verdict

**修复所列问题后可作为 P2.0b 实现规格。** v2.1 对 v1 对抗审查的大部分修复已经闭合；local verification report 中原标 PARTIAL 的 BLOCK-4、CONCERN-1、NOTE-1 在当前 v2.1 文本中已实质闭合。仍需在发布前修正文档中的两处会影响 soundness/completeness 的规格缝合问题：

1. TP7-D path-phase 对多输入机器队首阻塞（CE4/A13）的验收义务仍未写入 §2.3 的 verifier 检查，可能造成 false-CERTIFIED。
2. §2.4 selected-solution nogood 对 route-use 只写“selected use-vars”，不是完整 0/1 离散选择键，可能把包含旧图的可行超集误剪成 false-INFEASIBLE/错误最优性。

另有两个规格精度 CONCERN：§4.1 envelope 缺 mandatory `scope/kind` 字段的硬要求；§4.3 Farkas normal form 需要列出与 T1-T6 精确对应的 row-family 清单与 `lp_digest` 绑定。

## Repair fidelity table

| 原审查项 | 终验 | 证据 |
|---|---:|---|
| BLOCK-1 源口漏 `protocol_core`、utility 误作 recipe | FIXED | v2.1 明确 source = boundary_io + protocol_core，utility 不进 T4: `docs/research/p2_0_throughput_certification_paradigm_design_v2.md:14,26,37-39,52-54`。源码：`rules/preprocess_plan.json:35-55`；`src/models/binding_subproblem.py:1047-1059,1095-1127,1147-1158`；需求：`data/preprocessed/generic_io_requirements.json:11-18`。 |
| BLOCK-2 `rate(p)` 未定义、未绑定 route graph | FIXED | `r[p]`、G+ terminal arcs、route-visible equality 已写入：`v2.md:41,45,49-56,117-119`。源码邻接只连 route-state，不含 terminal arcs：`src/models/routing_subproblem.py:1413-1432`。 |
| BLOCK-3 frontier/dominance 继承量词错误 | FIXED | 只继承 `¬P(x)`，旧 incumbent/dominance skip 失效，正向捷径量词成立：`v2.md:83-89`。 |
| BLOCK-4 witness 非自包含/digest 不足/closed-world 不明 | FIXED for original issue | 当前文本补 stable digests、`selected_route_states`、`throughput_inputs_digest`、`throughput_semantics_digest`、closed-world flows/ports 和 unknown commodity 拒绝：`v2.md:115-119,131-133,137-138`。新 scope/envelope 精度问题见 CONCERN-1。 |
| BLOCK-5 Farkas 规范形含糊 | FIXED for original issue | `Ax≤b`、等式拆行、bounds 入行、canonical constraint_id、exact rational λ 校验齐备：`v2.md:125-128`。新 row-family 明文化问题见 CONCERN-2。 |
| CONCERN-1 公理覆盖不足 | FIXED for coverage | A13 独立成条并解释 CE4；D6-D8 与 throughput_semantics 仍在缺口/消解路径中：`v2.md:91-111,137,150-152`。新 TP7-D verifier 义务问题见 BLOCK-1。 |
| CONCERN-2 满速线不能共享组件 | FIXED | 已改为组件级局部饱和，明确口满不推出组件满：`v2.md:146-148`。 |
| CONCERN-3 selected nogood 与 whole-layout replay | PARTIAL | whole-layout replay 已闭合：`v2.md:76-81,142-144`；但 route-use key 只写“全部 selected route use-vars”，不是完整 0/1 assignment：`v2.md:78`。源码现有 fallback 也只有 selected vars：`src/models/routing_subproblem.py:1804-1812`。 |
| NOTE-1 派生需求措辞 | FIXED | 已写成 T4 + K_route network balance + T6 routing-free sink balance 共同诱导，witness 可选多解：`v2.md:56`。 |
| NOTE-2 `through(φ,s)` 可执行定义 | FIXED | incoming incident arcs 跨商品总和，T1 下 outgoing 等价，cross-junction 容量交给 A9/D7：`v2.md:50,106,152`。 |

## New defects

### BLOCK-1: TP7-D path-phase does not yet consume A13/HOL semantics

Evidence: §2.3 only requires component/port capacity, per-machine cycle counts, targets, in-flight closure: `v2.md:62-66`; A13 itself states CE4 is a separate HOL mechanism and FIFO trace is terminal裁决: `v2.md:105`; sandbox CE4 shows fluid feasible but discrete zero output under generous merger/splitter semantics: `p2_0_sandbox_counterexamples_gpt.patch:309-411,425-452`.

Risk: a path-phase certificate with balanced period counts can still feed `A,A,B,B` into a finite single FIFO before an A+B machine. Counts satisfy average recipe balance, but the second A blocks B behind it, producing false-CERTIFIED unless the verifier simulates machine input buffers or proves a HOL-free static precondition.

Patch: see `p2_v21_final_review_proposed.patch`, hunks for §2.3, §3 heading, summary line, A13 wording.

### BLOCK-2: selected-solution nogood is not an exact discrete-choice key for route-use variables

Evidence: §2.4 says the key includes “全部 selected route use-vars”: `v2.md:78`. Existing routing fallback no-good uses only selected vars: `src/models/routing_subproblem.py:1804-1812`. But a Farkas proof for selected graph S does not prove a strict superset S′ infeasible. Toy check: S with one 1/2-capacity path and demand 1 is infeasible; S′ adding another 1/2-capacity parallel path is feasible.

Risk: selected-only no-good `∨ ¬x_selected` forbids S′ that contains S plus additional route states. That is a false-INFEASIBLE / optimality-risk overcut.

Patch: see §2.4 and §7 hunks in `p2_v21_final_review_proposed.patch`; route-use no-good must be full equality: `Σ_{x∈S1}(1-x)+Σ_{x∈S0}x≥1`, unless an independent exact-rational proof justifies a superset/generalized cut.

### CONCERN-1: §4.1 certificate envelope leaves `scope/kind` implicit

Evidence: scope hierarchy is defined in §2.4: `v2.md:72-75`, and terminal verdict field list has `throughput_scope`: `v2.md:137-138`, but §4.1 envelope does not explicitly require certificate `scope` or `kind`: `v2.md:115-119`. Blind design included scope as an envelope field: `p2_0_blind_design_gpt.md:197-226`.

Risk: selected_route_graph certificates and future all-alternatives certificates can be projected with mismatched量词 unless scope is a schema field and P2.0b accepts only selected_route_graph.

Patch: see §4.1 hunk in `p2_v21_final_review_proposed.patch`.

### CONCERN-2: Farkas `lp_digest` should bind an explicit T1-T6 row-family manifest

Evidence: §4.3 says “TP7-S 全约束” and normalizes generally: `v2.md:125-128`; T1-T6 include terminal-arc equality, routing-free sink balance, target equality, and port capacities: `v2.md:47-56`. Without an enumerated row-family manifest, two implementations can disagree while both claim “Ax≤b”.

Risk: producer/verifier drift on T3 terminal equality or T6 routing-free sink rows can accept an invalid Farkas ray or reject a valid one.

Patch: see §4.3 hunk in `p2_v21_final_review_proposed.patch`.

## Per-source fact checks

`rules/preprocess_plan.json` has exactly the utility slot definitions v2.1 relies on: `protocol_core` has 6 generic output slots, `boundary_io` has 1 generic output slot, `power_supply` has zero generic slots, and `wireless_sink` has 3 generic input slots: `rules/preprocess_plan.json:35-55`. `data/preprocessed/generic_io_requirements.json` requires 34 + 18 external output slots and 1 + 1 generic input slots: `data/preprocessed/generic_io_requirements.json:11-18`. The arithmetic `46×1 + 1×6 = 52` matches v2.1’s stated capacity, but the uploaded review zip does not include `data/preprocessed/mandatory_exact_instances.json`, so I did not independently recount the 46/1 instance counts from this package.

`src/models/routing_subproblem.py` supports v2.1’s terminal-arc repair: `_route_state_adjacency` connects selected route states to neighboring route states and skips sink fronts; it does not create LP terminal arcs: `src/models/routing_subproblem.py:1413-1432`. Front metadata is set-like per `(front, dir, commodity)` for guard reachability: `src/models/routing_subproblem.py:1326-1338`. Duplicate physical-port terminal keys fail closed before routing: `src/models/routing_subproblem.py:151-160,413-427`. `extract_routes()` can expose selected physical states and commodity uses for a future `selected_route_graph_digest`: `src/models/routing_subproblem.py:1975-2024`.
