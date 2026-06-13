# PROJECT_LOCK.md

**Status**: CURRENT_LOCK
**Updated**: 2026-06-12 (wireless routing-free chain F-01..F04-R4: geometry repair + omni_wireless binding semantics + every-consumer / every-loading-path exclusion contract)
**Purpose**: Freeze exactness boundaries, source-of-truth rules, accepted invariants, and forbidden changes for the current repository state.
**History**: Date-stamped engineering history lives in [CHANGELOG.md](CHANGELOG.md). If this file conflicts with older notes, this file wins.

## 1. Exactness Constitution

- `certified_exact` and `exploratory` are separate paths. Exploratory outputs must not be promoted as certified evidence.
- The exact empty-rectangle objective is `max_lex(area, min_side)`.
- `min_side >= 6` is a candidate admissibility rule, not an objective tie-break.
- `rules/canonical_rules.json::globals.empty_rectangle.min_side_admissibility` is the project-level authority for that admissibility floor; the production project value is `6`, while toy projects may use smaller explicit floors.
- `Phi(w, h)` is not the exact source of truth.
- `(area, width, height)` is not the exact source-of-truth comparator.
- Exact mode has no hard `50 power poles + 10 protocol storage boxes` cap. If that number appears anywhere, it is exploratory-only guidance.
  - (2026-06-04) specs 02 §2.6.1 / 06 §6.1 / 07 §7.2·§7.4.1 早先把 `I_opt=60 (50桩+10箱)` / 总集 326 当 exact 固定枚举, 已对齐为: 供电桩 residual-optional (激活数为决策变量、coverage 下界、候选池上界)、协议箱 required-optional (demand 驱动); 60/326 仅标 exploratory illustrative 参考。真实 master (`pose_bool_exact_master` / `exact_coordinate_master`) 实证无此 cap (源码 residual/required-optional 建模, 非固定 60)。

## 2. Certified Source of Truth

The certified path is grounded in:

- `rules/canonical_rules.json` (now also carries consolidated preprocess recipe / target / commodity truth and empty-rectangle admissibility)
- `data/preprocessed/candidate_placements.json` (required external large artifact in the current lightweight GitHub checkout)
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`
- artifact-hash-compatible campaign state
- provenance-complete exact-safe cuts

The current GitHub `main` branch intentionally omits the large
`data/preprocessed/candidate_placements.json` working-tree file after the
2026-06-06 backup cleanup. This does **not** remove it from the certified
contract: certified exact runs must restore or regenerate the artifact first.
Expected facts after the 2026-06-12 preprocess F-01/F-02 repair: size
`45,773,799` bytes, SHA256
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`. The
former artifact (size `53,594,995` bytes, SHA256
`d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f`) is
superseded and must be treated as hash-incompatible evidence; campaign
resume must fail closed with `artifact_hash_mismatch`. Regeneration source:
`python src/placement/placement_generator.py`.
Older archives such as `C:\22957\download\zmd.7z` may still contain the
superseded bytes and are not valid restore sources for the current lock.

The following remain additive postprocess artifacts and must not redefine internal solve schemas:

- `data/solutions/final_solution.json`
- `data/blueprints/optimal_blueprint.json`
- `data/solutions/certified_delivery_manifest.json`
- generated viewer/report sidecars such as `viewer_report.json`
- compatibility export bundles such as `data/exports/industrial_planner/*`
- adapter-side outer deployment sidecars / validator probes for IndustrialPlanner larger-base experiments
- neutral interchange contracts under `src/interchange/*`
- build-time / export-time adapters under `src/adapters/*`
- build-time preprocess plan `rules/preprocess_plan.json` and `src/interchange/preprocess_context.py` — **additive-only** (cycle groups / utility operations). The plan must never carry `recipes` / `production_targets` / `commodity_roles`: recipe/target/commodity truth derives exclusively from `rules/canonical_rules.json`, and the context builder fails closed on any such key (R6-F-01: a same-key plan overlay could silently rewrite runtime operation profiles). Because the plan feeds runtime operation profiles and binding utility slots, it is bound into the exact campaign hash closure (`exact_campaign.OPTIONAL_EXACT_HASH_FILES`) and the preflight frozen-artifact registry; editing it is a freeze-ritual change, not a free overlay edit.

## 2B. B Design v2 Cut Object Boundary (2026-05-22)

Phase 0 close (`docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md`) 后,
**cut object 升级为持久化一等公民**. New source-of-truth additions:

- `docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md` v3.2.2 — cut
  object schema + 10 步 lifecycle + 6 步 replay verify + 6 维 watcher
- `docs/research/p3_b_design_v2_20260521/cut_family_specs/{01-09}` — 9 cut
  family 完整 spec (region_capacity / cutset / port_exposure / component_reach /
  pattern_nogood / shape_packing_hall / power_hitting_set / power_grid_reach /
  density_envelope) 全 final version
- `docs/research/p3_b_design_v2_20260521/state_machine_v2.md` — group-orbit
  state + AnonymousSlotRef (替代 v14 per-instance state, 消 10^134 label
  symmetry)
- Phase 1 起 `data/cuts/*.json` (persisted active cuts) + `data/cuts/
  quarantine/*.json` (quarantined cuts) 加进 certified path source-of-truth
  (currently 空, 等 Phase 1 cut store 落地后启用)

**postprocess/adapter boundary** unchanged: cut object 仅在 certified core 内
循环, 不进 `src/adapters/*` / `data/exports/*`.

## 2A. IndustrialPlanner Active Scope

- The current certified IndustrialPlanner support contract targets `valley4_protocol_core` (70×70) exclusively.
- The other known IndustrialPlanner bases (`valley4_infra_outpost`, `valley4_rebuilt_command`, `valley4_refugee_shelter`, `wuling_tianwangping_aid`, `wuling_heart_repair_station`, and `wuling_protocol_core`) are preserved as `future_scope` and are not part of the active checked-in audit / CI contract.
- The checked-in full-demand base matrix, deployment-path matrix, umbrella overview, support-suite inventory, and checked-artifact gate must default to that single active 70×70 base.
- The outer-deployment subsystem for larger-base translation remains adapter-side `future_scope`: it may stay in the repository, but it must not be treated as active certified evidence or as part of the default CI-critical path until explicitly reactivated.

## 3. Accepted Invariants

- Best certified result is monotonic across campaign persistence and resume.
- `final_solution.json`, `optimal_blueprint.json`, and `certified_delivery_manifest.json` must be derived from the same best certified result when one exists.
- Optional compatibility exports must be derived from the canonical blueprint and must not become the source of truth for solver/runtime consumers.
- Postprocess manifest/export mappings used to bridge translated larger-base exports remain adapter-side evidence only and must not be promoted into certified proof.
- Production parallel scheduling uses a coordinator-only writer with disjoint candidate waves.
- Candidate-record solution hygiene (F78-F-01): a persisted candidate `solution` may exist only on a `CERTIFIED` record; every incoming `CERTIFIED` result must carry its own fresh solution mapping (no inheritance across `mark_candidate_started`/`mark_candidate_result` rewrites); resume validation rejects any non-`CERTIFIED` record carrying a solution. Strong statuses (`CERTIFIED`/`INFEASIBLE`) are monotone under the same artifact hashes: rerun preambles must not downgrade them to `RUNNING`, weak results must not overwrite them (audited block), and contradictory strong statuses fail loudly.
- Parallel wave results are identity-bound (F78-F-02): a worker result is accepted only when its `dispatch_seq`, `attempt_index`, `candidate`, and `candidate_key` all match the dispatched task, validated independently on both the scheduler side and the consumer side before any campaign write; duplicate sequences, mismatched identities, and errored results never become proof-bearing outputs, and a malformed wave stops the campaign as `worker_process_failed`/`UNKNOWN`.
- Optional frontier probe mode is an exact-safe scheduling hint only and must not replace completeness requirements.
- Global pooling semantics for shared boundary/core resources must remain commodity-aggregated.
- `protocol_storage_box` follows canonical `omni_wireless`: candidate poses have no physical input/output port cells, use `orientation = 0` and `port_mode = "omni"`, and binding materializes the plan-defined virtual generic input slots (`rules/preprocess_plan.json::utility_operations.wireless_sink.generic_input_slots = 3`). These slots are commodity binding capacity only; they must not emit routing port specs or routing/flow sink fronts.
- Symmetrically (producer side, preprocess F-03): a routing-free wireless **final** commodity — canonical `commodity_metadata[*].sink_kind == "generic_input"`, i.e. a positive `required_generic_inputs` entry such as `qiaoyu_capsule` or `valley_battery` — is consumed wirelessly and has no routing sink. Its producer facility's physical **output** ports (and any generic-output port for the same commodity) must be excluded from `extract_port_specs()`; the producer's **input** ports for raw materials stay routed. Re-exporting such an output as a routing terminal creates an orphan routing source with no sink, yielding spurious `front_blocked` / false-INFEASIBLE rejection of otherwise valid layouts. The exclusion must hold at **every** consumer of port-front routability — `extract_port_specs()` (the feed into routing/precheck), the routing-aware build-time domain filter `_filter_pose_binding_domain()` and RAB blocker certificates (F03-R3-01: the build-time filter is an independent side channel, not derived from port specs), the routing deletion-core minimizer oracle (must consume routing-visible port keys built from the current binding's port specs, F04-R4-02), the pose-bool exact master's env-gated port-active output demand / hard-clearance and blocking-cell port caches / lazy-demand cuts (output-side demand and caches must exclude routing-free final outputs; a mixed visible+routing-free output side must not be generalized from raw output ports, F04-R4-03), and separator-capacity / L2 abstract-routing / dynamic-separator commodity-side classification (a routing-free final commodity must never be classified as a routed source, F04-R4-04). Additionally, the semantic guard fails closed if a `sink_kind == "generic_input"` commodity ever also appears as a recipe input (dual-role would make this exclusion starve a real downstream consumer silently) — and this guard must hold on **every loading path**: both `validate_canonical_document()` and direct rules+plan `validate_preprocess_context()` construction (F04-R4-01: overlay/direct loads bypassed the canonical-only guard).
- Generic output slot domains must include an explicit unused sentinel (F-BIND-R1-01): full boundary/core output-port occupancy in the current base is a numeric consequence of the exact-count constraints over real commodities (R=S=52, specs/04 §4.5), not a structural domain assumption. Encoding fullness structurally (dropping the `__unused__` choice) turns any requirement-below-slot-count configuration into false-INFEASIBLE. The sentinel is binding-internal only: it must never reach `extract_port_specs()` or any routing/flow surface, and it is a reserved name that may not appear as a commodity in any requirements artifact.
- Generic I/O requirement and wireless-sink slot-count loading is fail-closed (F-BIND-R1-02): both requirement sections must be present (a missing section is an error, not an empty default), slot counts must be strict non-negative integers (bool/float/string coercion rejected), and on the default artifact loading path every generic output commodity must have canonical `source_kind == "external_boundary"` and every generic input commodity canonical `sink_kind == "generic_input"`. All production `PortBindingModel` constructions load requirements through this validated path; explicitly passed toy maps are test-fixture-only and must not appear in solver/runtime code.
- The fail-closed generic I/O entry point is proof-surface-wide, not binding-local (F-BIND-R2-01): the certified master core consumes generic I/O requirements **before** binding ever runs (hard constraints and certified optional lower bounds derived at `ExactSearchSession` construction), so `master_model.load_generic_io_requirements_artifact()` must delegate to the same fail-closed binding loader — a second, looser parser of the same artifact is a forbidden proof-surface fork.
- Proof-relevant JSON artifact parsing is strict (F-BIND-R2-02): duplicate object keys (Python `json.loads` silently keeps the last value, letting a tampered artifact replace real demand with an empty section or rewrite the wireless slot count) and non-standard JSON constants (`NaN`/`Infinity`) must be rejected at every loader feeding binding/master proof inputs (generic I/O requirements, wireless sink slot count, canonical commodity-role reads).
- Proof inputs are single-parse, single-snapshot (F-BIND-R3-01..05, F-BIND-R4-01): within one certified session, every consumer of a proof artifact must consume the same in-memory snapshot or the same validated loader — the certified binding receives the master's normalized `generic_io_requirements` snapshot instead of re-reading disk (no two-points-in-time fork); `load_project_data`'s JSON reads (mandatory instances, candidate placements, canonical rules) are strict-parsed; utility slot counts in `preprocess_context` are strict non-negative ints; the wireless-sink slot count flows from the project-root plan into master optional lower bounds, outer safe-area, campaign proof helpers, coordinate stats, and certified binding construction (never from an import-time default profile or a later binding-time disk reread); and campaign proof helpers load generic I/O through the shared validated artifact loader, never a private parse.
- The single-snapshot seal extends across the outer search and worker processes (F-BIND-R5-01): the certified frontier candidate domain and every solver session proving candidates from it must be sealed to the same artifact snapshot — `run_outer_search` records its domain snapshot (artifact hashes, generic I/O requirements, wireless slot count) and every `ExactSearchSession` created or ensured afterwards must match it exactly (mismatch is a `RuntimeError`, not a silent re-read); parallel workers receive the coordinator's expected artifact hashes and fail startup (`STARTUP_ERROR`) when their self-built session disagrees, so no worker can produce candidate proofs in a different artifact universe than the frontier domain they feed.
- Strict parsing extends to the preprocess (re)generation chain (F-PRE-R8-01): the hash closure pins artifact bytes but cannot disambiguate parsing of those bytes, so first-build inputs are a layer below it. Canonical/plan loading in `preprocess_context`, the placement generator's canonical read, `machine_counts` loading in the instance builder, and frozen-parity consumption must all use the shared strict JSON entry (`src/io/strict_json.py`); preprocess artifact writers must emit `allow_nan=False`. A duplicate key in a generation input must fail loudly, never rewrite a target value, a port rule, or a machine count silently. Strictness includes numeric overflow (F-PRE-R9-01): a JSON number literal parsing to a non-finite float (`1e309` → `inf`) must be rejected at the shared strict entry via `parse_float` (`parse_constant` only catches spelled-out `NaN`/`Infinity`), and every preprocess/parity writer — including the context/diff report writer — must write with `allow_nan=False`, so non-finite values can neither enter through a literal nor exit as a non-standard constant.
- Schema validation must run at the file-loading boundary, not exist only as a bystander (F-PRE-R10-01): the preprocess context path loaders (`load_default_preprocess_context`, `load_preprocess_context_from_paths`) must validate strict-loaded canonical/plan payloads against `canonical_rules.schema.json` / `preprocess_plan.schema.json` before context construction applies defaults — a schema-required field silently absorbed by a code-level default is fail-open. The low-level dict-to-context builder stays a pure constructor for test variants; file entrances are the enforcement boundary.
- Closed-form pose generators must verify the canonical geometry they hard-code (F-PRE-R10-02): the placement generator families that emit frozen geometry (core 9x9 with 6/14 limits, omni 3x3, pole 2x2 with the radius-5 stencil, boundary 1x3 left/bottom, long-sides w>h, square w==h) must fail closed when the canonical template's schema-visible fields (`dimensions`, `core_limits`, `power_coverage_radius`, `placement_rule`) drift from those assumptions. A schema-valid canonical edit must never let canonical claim one geometry while generated candidate poses carry another (owner-gated canonical extensions inherit this contract).
- Every canonical file entrance validates schema, not just the context loaders (F-PRE-R11-01): the placement generator's `load_templates()` is an independent canonical file entrance feeding candidate regeneration; like the context path loaders it must run `canonical_rules.schema.json` validation immediately after strict JSON loading. Any future reader that strict-loads canonical bytes from disk inherits this obligation — a schema-required field absorbed by downstream defaults through any entrance is fail-open.
- The geometry contract locks every field the generators consume or implicitly assume (F-PRE-R11-02): beyond the R10 field set, `rotatable` and `is_solid_z` are generator-semantic fields — emitting rotated orientations for a non-rotatable template, or emitting solid `occupied_cells` for a non-solid one, lets schema-valid canonical drift fork canonical semantics from generated poses. `_validate_template_geometry_contract()` must pin the per-family expected values (and type-check them as booleans) before dispatch.
- Cycle-group solutions must be proven non-negative, not just unique (F-PRE-R11-03): a square non-singular cycle system can still yield negative run rates under canonical drift, and downstream demand aggregation filters non-positive entries — silently deleting machines from the frozen demand artifacts. Context validation must prove each net-export commodity admits a non-negative basis solution, every net-export commodity must be an internal commodity of its group, and `_solve_cycle_group_exact()` must fail closed on any negative run rate at solve time.
- Cycle-group demand keys are a closed set, membership-checked at both ends (F-PRE-R12-01): the RHS is assembled by iterating `internal_commodities`, so a positive external demand keyed by a commodity outside that list would be silently dropped — producing frozen demand/instance artifacts that are missing the supporting machines (fail-open). Context validation must require every `cycle_internal` commodity to be listed in its declared group's `internal_commodities` (reverse-index check, not just group existence), and `_solve_cycle_group_exact()` must reject positive demand keys that are not both internal and net-export (preserving the R11-03 proof premise that RHS lies in the non-negative span of proven net-export unit directions) and reject negative demands outright; explicit zero entries stay accepted.
- Cycle groups must be a recipe I/O closure, checked at both ends (F-PRE-R13-01): the cycle solver builds its matrix and downstream machine-run aggregation only over `internal_commodities`, so any cycle recipe input/output referencing a commodity outside that list is silently dropped from demand propagation — under canonical drift a cycle recipe consuming an external commodity (e.g. an ore) would leave the frozen `commodity_demands`/`port_budget`/`generic_io_requirements` artifacts missing that supply requirement while still claiming the 52-port budget feasible (fail-open, the F-PRE-R12-01 membership-closure class extended from demand keys to recipe I/O). Context validation must require every cycle-group recipe's `inputs ∪ outputs` to lie entirely within the group's `internal_commodities`, and `_solve_cycle_group_exact()` must repeat the check at its entry to cover direct solver calls on unvalidated contexts.
- A fully enclosed legal empty rectangle remains allowed; exterior connectivity is not part of the exact contract.
- Terminal certified frontier evidence is a closed, project-bound contract: unknown `candidate_generation` keys, non-authoritative domain values, stale evidence schema versions, and sub-admissible terminal best results must fail closed before any public CERTIFIED surface.
- In `certified_exact`, `EXACT_*` environment knobs are deny-unknown by default: only documented operational allowlist entries may be present, known proof-semantics knobs must stay at canonical false/default values, and future/unclassified names must block the run.
- Terminal front polarity is toward the connector (F-RT-R2-01): a port stores the outward normal `dir` and its routing front is `port + dir`; the source front receives with `flow_in = Opp(dir)` and the sink front sends back with `flow_out = Opp(dir)`. Encoding the sink front in the outward direction rejects legal straight corridors (false-INFEASIBLE) and lets roomy layouts satisfy a phantom outward state without feeding the connector. The solver's port indexing/adherence and every independent verifier must derive this polarity from the rule, not from each other — a verifier that copies the solver's key orientation is blind to exactly this class (the diff-fuzz oracle shared the same inverted key for its first 900 instances).
- Per-edge channel conservation holds across layer overlap (F-RT-R2-02): legal L0-straight/L1-bridge overlap on one 2D cell must not let a single directed edge feed both layers or merge two layers into one edge — for every commodity and every non-terminal cell-to-cell directed edge, the number of selected sending states equals the number of selected receiving states. Local "at least one supporter" continuity alone licenses hidden splitters/mergers at overlap cells that the connectivity guard cannot see.
- Physical port connector cells are terminal nodes, never belt cells (F-RT-R3-01): the routing domain must exclude every in-grid port connector cell `(port.x, port.y)` from free/active routing cells — at domain resolution, at any externally supplied `domain_analysis` binding (fail-closed re-subtraction), and with placement-core reuse recomputing connectivity components after the subtraction. Leaving connector cells routable lets any commodity cross another port's connector as an ordinary belt cell and lets a normal belt reuse a terminal side, bypassing both the CP-SAT encoding and the reachability guard (false-FEASIBLE). Ordinary route states must also not send into a source front's connector side nor receive from a sink front's connector side (belt-and-suspenders over the domain exclusion). Independent verifiers must check connector-cell occupancy as their own rule-derived predicate.
- Same-commodity terminal fronts may live in multiple disconnected components (F-RT-R4-01): the routing-domain precheck must not require all terminal fronts of a commodity to share one connected component — the rule semantics (each source front reaches some sink front, each sink front is reached by some source front; specs/08 pool model) admit multiple physically disconnected islands each closing its own supply/demand. When a commodity has both sources and sinks, every terminal-bearing component must contain at least one source front and one sink front, the active domain is the union of the satisfying components, and per-component core peeling applies; collapsing this to a single-component requirement rejects legal layouts (false-INFEASIBLE through the binding-local safe-reject consumption of `relaxed_disconnected`).
- Terminal front keys must be unique per physical port (F-RT-R4-02): two port specs folding onto the same `(front, terminal_dir, commodity, type)` key would collapse two exact-one adherence obligations into one (multiplicity lost). Canonically unreachable (shared front+dir implies a shared connector cell, which master no-overlap forbids across facilities and the generator never emits within a pose), but externally supplied `port_specs`/`domain_analysis` can construct it — the precheck and the solver build must both fail closed (`front_blocked`/reject) on duplicate terminal front keys rather than silently folding.
- Externally supplied routing domains must be clipped to the real free grid (F-RT-R5-01): binding a caller-supplied `domain_analysis` must intersect every commodity's active/component cell set with `grid.free_cells - port_connector_cells`, not merely subtract connector cells. The CP-SAT obstacle exclusion is implemented as "route states are only created on active domain cells", so a stale or hostile external analysis containing an occupied solid cell would otherwise materialize route states on solid cells and produce an accepted `FEASIBLE` through a wall (false-FEASIBLE; specs/09 solid obstacle exclusion). Connector cells, occupied cells, and out-of-grid cells must all be rejected by the same intersection; a port front clipped out of the active domain stays fail-closed through the `0 == 1` adherence guard.
- Routing CP-SAT `FEASIBLE` is not a certification boundary by itself: certified acceptance must rebuild the selected per-commodity route-state graph and prove every source front reaches a sink front and every sink front is reachable from a source. A locally closed but globally disconnected incumbent must be rejected and re-solved; if the budget is exhausted before a connected incumbent is found, the certified path returns `UNKNOWN`/`TIMEOUT`, never `CERTIFIED`.
- P0-1 lazy routing connectivity cuts are acceleration-only proof obligations: every source-side component cut must independently revalidate its `W`/`X` certificate (source fronts in `W`, sink fronts outside `W`; removing `X` disconnects all source fronts from sink fronts in the full potential state graph; incumbent selected states are disjoint from `X`) before attachment, otherwise it must fall back to the selected-positive nogood.
- Certified optional lower bounds must count every slot form that satisfies them (F-GM-Q3-01): when the coordinate master enforces a required-optional cardinality lower bound (e.g. `ceil(generic input demand / wireless slots)` for `protocol_storage_box`), fixed required optional slots count toward the bound as constant contributions; only the remaining shortfall may be demanded from the residual optional pool. Encoding the bound over the residual pool alone turns a configuration whose fixed slots already satisfy it into false-INFEASIBLE. The dual obligation (F-GM-Q3-01-R3-A): when fixed required slots exist but do not satisfy the lower bound (`0 < fixed < lower`), the residual optional pool must still be constructed so the shortfall has literals to draw from — skipping residual slot construction whenever any fixed slot exists encodes `0 >= shortfall` and turns legal fixed+residual mixes into false-INFEASIBLE. Residual pool sizing and powered residual upper-bound statistics must both subtract the fixed count from the template upper bound (no double-spending the same capacity) and must use the same residual-needed predicate as slot construction (no one-sided fixes splitting bucket preparation from slot creation). Fixed required optional slots must carry the template's full role semantics (F-GM-Q3-01-R4-A): a fixed `power_pole` slot is a real pole, not just a geometric footprint — it must enter pole family membership/count channels and the table/geometric power-coverage witness enumeration; under "fixed fully represents the template" semantics the residual pole pool is skipped, so a fixed pole left out of the power channels turns legal fixed-pole-powered configurations into false-INFEASIBLE. The degenerate boundary (F-GM-Q3-01-R5-A): attaching fixed poles to the capacity-family channel is only meaningful when the family mapping exists — when power coverage is skipped or the model has no powered demand at all, the family table is legitimately empty and the attach must be skipped entirely rather than emitting an empty-table `0 == 1` (which rejects legal geometry-only fixed-pole configurations). With a non-empty family mapping, an unexpectedly empty tuple table keeps the fail-closed rejection.
- Applying a cut must invalidate the previous solver witness, not just the solution cache (F-GM-R6-01): a successfully added Benders cut changes the model, so the pre-cut `CpSolver` assignment is no longer a witness for the current model. Clearing only `_last_solution` leaves `extract_solution()` / `extract_bound_state()` free to rebuild the just-forbidden placement (or its objective bound) from the stale solver until the next solve. Cut application must clear the solver and status on both the exact-coordinate and legacy paths so post-cut, pre-resolve extraction returns empty/no-incumbent instead of a stale witness. The LBBD main loop re-solves immediately after cutting, so this is an API-surface fail-closed obligation; it binds any future consumer that extracts between cut and re-solve.
- Solution hints are search guidance only and malformed entries degrade to skip (F-GM-R7-HINT-01): the hint path (greedy, community blueprint merge, ghost anchor) may only write the CP-SAT `solution_hint` proto via `AddHint` — never constraints — so a wrong hint can cost time but can never change the feasible set or the conclusion. Malformed hint entries (non-int pose index, out-of-range pose, unknown ghost anchor index) must be skipped instead of raising pre-solve: a performance suggestion must not be able to interrupt a certified solve. Each solve clears the previous hint proto before applying the current one. Hint index parsing is strict-int end to end — bools, floats, and numeric strings are skipped, and no later stage (telemetry included) may re-coerce a rejected raw value (F-GM-R8-HINT-02).
- Symmetry breaking may impose at most one total order per interchangeable slot family (F-GM-R8-SYM-01): every symmetry constraint must preserve at least one representative of each feasible equivalence class. Two simultaneous monotonic orders over different keys (slot `order_key` and `signature_int`) are NOT jointly representative-preserving — a pose pair ascending in one key and descending in the other leaves no arrangement satisfying both, deleting the entire class (false-INFEASIBLE; under `max_lex` this silently drops true maximal rectangles, and real candidate pools contain such reversed pairs). A secondary monotonic order may only be added when it is provably a consequence of the primary order over the family's full candidate set (same-order gate), and skipped families must be visible in telemetry.
- Coordinate exact master geometry must be keyed by each candidate pose's `occupied_cells` footprint, not by template default dimensions alone. No-overlap, ghost interaction, and power-coverage witness spans must use a mode-channelled footprint bounding box derived from the selected pose; non-rectangular footprints may be conservatively over-approximated by that box but must not under-approximate.
- `binding_selection_safe_reject=True` routing precheck evidence is binding-local. `front_blocked` and `relaxed_disconnected` must first add a binding-level nogood and enumerate alternative port bindings while any remain. A master placement-level nogood is allowed only after binding alternatives are exhausted or an independent placement-level proof exists; otherwise the certified path fails closed as `UNKNOWN`.
- Budget exhaustion is never an exhaustion proof (F-BL-R3-01): hitting an enumeration cap (e.g. `EXACT_B1_BINDING_ALT_CAP`) while binding alternatives remain must return `UNKNOWN` without minting any binding-level or whole-layout nogood — only a binding CP-SAT `INFEASIBLE` re-solve proves the alternatives are exhausted. Likewise the main loop consumes subproblem statuses through an explicit contract (F-BL-R3-02): any routing status other than `FEASIBLE`/`INFEASIBLE`/`TIMEOUT` fails closed as `UNKNOWN` with no cut, never down the infeasible branch. The same contract binds every binding solve and re-solve site (F-BL-R4-01): any binding status other than `FEASIBLE`/`INFEASIBLE`/`TIMEOUT` — at the initial solve, overload-fallback retry, precheck safe-reject re-solve, relaxed-disconnected re-solve, or post-routing-INFEASIBLE re-enumeration — fails closed as `UNKNOWN` (`subproblem_status_contract_violation="unexpected_binding_status"`) without entering the exhaustion chain; only a contract-valid binding `INFEASIBLE` re-solve may feed the binding/routing-exhausted whole-layout nogood.
- Master-level cell-pattern cuts may only quantify over necessarily-active ports (F-CUT-R2-01): the env-gated pose-bool cell cut `sum(poses with a port at (cell,dir)) + sum(poses occupying the front cell) <= 1` is exact only when every enumerated port candidate is necessarily active and routing-visible whenever its pose is selected — the side's visible demand must cover all physical ports on that side (input: concrete routing-visible `input_demand >= physical_port_count`; output: visible output non-zero, equal to total output, and `>= physical_port_count`). Generic utility slots are binding capacity, not mandatory per-port demand (CUT-R3-H1): generic-input slots are virtual wireless capacity and never count as physical front demand; generic-output slots may count as visible output demand only when the required generic-output total globally saturates the mandatory generic-output capacity (saturation forces every physical slot away from `__unused__`), and the capacity total must be computed fail-closed — any generic-output-providing group whose instance count is unknowable makes the capacity unknowable and the side is not registered (an undercounted capacity could fake saturation and over-cut). A blocked port that binding may leave inactive does not make pose+blocker infeasible (binding can select another slot), so registering optional binding slots — or residual-optional poses without operation binding identity — in the routing-visible per-cell port index over-cuts feasible placements; mixed visible+routing-free output sides stay with the weaker-but-exact lazy-demand/count cut. Candidate pose data is global-coordinate: port/cell lookup caches must not re-apply the anchor offset (double-anchoring aliases candidates to phantom cells, silently missing or mis-targeting cuts). The hook is blocked on the public certified path by the `pose_bool_master_not_certified` env guard; this clause binds any future promotion of pose-bool/cell cuts into certified.
  CUT-R4-H1 addendum: generic-output saturation proves only that slots are non-`__unused__`; it does not prove routing visibility for commodities that are also routing-free generic-input sinks. Pose-bool visible demand may therefore count saturated generic-output slots only when every positive required generic-output commodity is disjoint from the routing-free sink set. If the generic-output requirement set mixes routed and routing-free commodities, raw per-pose generic-output fronts remain unregistered until a binding-aware/global count proof exists.
- The PCR-CUT patch model must be a relaxation (over-approximation) of full routing, end to end (PCR-R5): the entire proof value of `patch INFEASIBLE ⇒ layout INFEASIBLE` rests on the patch CP-SAT accepting every continuation the full model accepts. Four obligations bind this (each was violated once): boundary relaxation must exist for **every** routing layer, not just ground (an elevated bridge crossing the artificial patch border must remain feasible, PCR-R5-H1); patch port-front polarity must match `RoutingSubproblem` exactly — input/sink fronts send toward the connector via `Opp(dir)` (PCR-R5-H2, the F-RT-R2-01 polarity class recurring in a re-implementation); constant-occupancy support must be carried into the conflict core and master terms — patch cells plus their cardinal boundary neighbors whose occupancy shaped the infeasibility must appear as assumptions/terms, otherwise the cut blames the victim pose unconditionally while the real blocker walks (PCR-R5-H3); and signature lifting must fail closed when lifted master var sets overlap — a duplicated BoolVar in the linear nogood strengthens `co-occurrence forbidden` into `single pose forbidden` (PCR-R5-H4). Replay validation (presolve=false, workers=1) re-proves the patch model's own UNSAT; it cannot substitute for these encoding-level relaxation obligations. QuickXplain cap hits may return a non-minimum core (weaker cut) — never treat the result as a global minimum.
- Patch port membership is decided by terminal-front intersection, not connector membership (PCR-CUT-R6-H1, fifth relaxation obligation): a port whose connector cell lies outside the patch but whose terminal front cell lies inside still injects/absorbs flow inside the patch in the full model — dropping it makes the patch stricter than full routing, and boundary relaxation cannot compensate because the connector cell is occupied and never receives boundary variables. Port indexing, port adherence, separator patch-port collection, and local pose signatures must all include a port when its connector **or** its front cell intersects the patch (front-in-patch external connectors enter the signature so lifting cannot merge poses whose terminals do and do not touch the patch).
- A separator's master cut may not be narrower than the layout context compiled into its model (CUT-R8-H1, the PCR-R5-H3 constant-support obligation restated for every separator channel): a CP-SAT assumption core only covers assumption literals, while any layout state baked into the model as constants (occupancy grid from selected footprints, helper terminal positions) is unguarded proof context. A cut over the raw core alone upgrades "this terminal subset is infeasible under the current obstacles" into "these poses are infeasible in any layout" — over-cut. The master conflict tuple must include every selected pose that contributed compiled constants (all occupancy contributors and all current port owners, ghost excluded) alongside the raw core; augmenting only weakens the cut, keeping its forbidden set within the proof obligation. The env-gated D2 commodity-flow rung violated this once (`EXACT_B1_D2_COMMODITY_FLOW`, raw-terminal-core cut while the entire layout footprint was a model constant).

### 3A. B Design v2 invariant additions (2026-05-22)

Phase 0 23 round Gemini cross-check 后 frozen invariants. **Phase 1 实施
不可破**:

- **Exactness FP = 0**: 任何 cut 都不能误剪合法解 (False Positive = 0).
  False Negative (cut 漏发, 性能退化) 可接受, FP 致命. Gemini round 19 原则
  "宁可 FN 不可 FP" 写进 lock.
- **Group/orbit-count symmetry**: state 必走 group-orbit 而非 per-instance,
  消 10^134 label symmetry. AnonymousSlotRef multiset 包含语义跨 candidate
  enumeration order 必 sound (slot_index 仅 debug/serialization 用, 不参与
  soundness 推理).
- **Cut family ↔ mode 一致性**: `_FAMILY_MODE_MAP` (cut_lifecycle_v2 v3 §3)
  契约 — literal-based family (3/5/7) 走 multiset evaluate, geometric family
  (1/2/4/6/8/9) 走 evaluate_geometric. `__post_init__` enforce literals
  XOR geometric_payload 互斥.
- **Scope-aware HOLD vs Quarantine**: 6 步 verify (cut_lifecycle v3.2.2 §4)
  失败的处理必须严格区分 — HOLD 不删 cut 等下次 candidate matching;
  QUARANTINE 不删 cut 留 audit trail 不进 active resolve; 两者不能混. ghost-
  agnostic cut (`GHOST_AGNOSTIC` sentinel) 跳 ghost_rect_id 校验**但**仍走
  exterior_blocks_hash 校验 (v3.2.2 dispatch).
- **F9 paradigm 降级 lock**: density_envelope 只 trigger
  `area_capacity_overflow` 凭证. binding/routing/PCR-CUT INFEASIBLE 必 fallback
  Family 5 pattern_nogood (Gemini round 19 verdict). 不允许 silent generalize
  topological deadlock → density cut.
- **F9 area-based counting lock** (Gemini round 24 B2 — round 20 finding 焊死):
  F9 evaluator + validator 必走 area-based `sum(|pose_cells ∩ W|)` 计数,
  **不可退化** instance-based counting (v1.0 over-count / v1.2 origin-in-W
  / v1.3 all-in-W 全 unsound — v1.0 FP, v1.2 FP, v1.3 FN). v1.4+ 全
  area paradigm 是唯一 sound 路径, 任何 refactor 退回 instance-counting 算
  Forbidden Change.
- **(2026-06-04 v28 GPT pro 外审) Cut-family validator 数值/字面量 source-of-truth
  gate**: 任何 accepted cut 里 validator **无法独立便宜重算**的 scalar/literal
  payload, 必须对 canonical_rules / source-of-truth fail-closed 交叉核对 (镜像 v28
  F7 `pole_radius` 修复)。逐 family 焊死:
  - **F5 pattern_nogood slot 完整性**: `forbidden_pose_pattern` 每个 literal 必须绑
    一个真实、唯一、在界内的匿名 slot — `slot_index < group.demand` + `(group, slot)`
    唯一 + per-group literal 数 ≤ demand。Why: generic evaluator
    (`evaluate_literal_multiset`) 刻意丢 slot 身份按 `(group, pose)` multiset 评估,
    一个 slot-collision 核 `[(g,0,pA),(g,0,pB)]` 虽被 oracle 正确判 INFEASIBLE (单
    slot 不能两 pose), lift 成 multiset cut 后却比 oracle 实际证明的更强 → 错剪合法
    布局 slot0→pA/slot1→pB (FP)。
  - **F6 shape_packing_hall region_demand 下界**: `region_demand ≤ max(0, group_demand
    − 对侧 baseline 容量)`, 且仅接受 `left_or_bottom_boundary` 模板。Why: 单边 Hall
    cut 只对 "被 pigeonhole 强制到该侧" 的数量 sound; 容量上界 ≠ 强制下界, 伪
    `region_demand` 会错剪合法 split (全放另一边)。
  - **F7/F8 footprint SoT**: power_pole footprint 2×2、protocol_core footprint 9×9
    必须对 `canonical_rules.facility_templates.{power_pole,protocol_core}.dimensions`
    fail-closed 核对 (与既有 `pole_radius` gate 同款)。当前 canonical 下无 live FP,
    防 footprint drift 退化成 F7 radius 同类洞。
  共享实现集中在 `src/cuts/helpers/canonical_sot.py` (canonical lookup + fail-closed
  dims 校验), F7/F8 委托它 (不再各持私有副本); `src/tests/cuts/test_canonical_sot_coverage.py`
  meta-test 强制 (登记契约 + 私有 lookup 不复活)。**新增信任 canonical 标量的 family 必须
  走 canonical_sot + 进登记表 + 加 behavioral red-test** (meta-test 抓回归, 但发现"全新未守
  标量"仍靠人/审查 —— 诚实边界)。**已知 grandfathered**: F6 (shape_packing_hall) 有一份
  family-local canonical-dims SoT 核对 (pose_length vs template dims, 经 state.facility_templates
  alias, sound fail-closed) 未走 canonical_sot、未进登记表 —— 它**非 fail-open 洞** (v28 合并只
  针对 fail-open), 是预存未 consolidate 项; meta-test 的 dimensions 私有扫描刻意不覆盖它。
  **(2026-06-04 fresh-pass 补)**: `src/cuts/assumptions/verifiers.py` 的 `verify_power_pole_jump_radius`
  曾藏 canonical pole-radius lookup 的**第 4 个逐字副本** (在 certified attach-scope 路径, 前 3
  轮 + v28 外审全漏), 已委托 canonical_sot; meta-test 的私有-radius 扫描已扩到 validator-side
  (families + assumptions)。**待办 (本轮未做)**: `verifiers.py` `verify_protocol_core_position`
  是 F8 `_validate_pc_anchor_sot` 的**近似**副本 (非逐字), 未 consolidate; `src/cuts/oracles/power_cover_oracle.py` 是 generator 侧读 canonical (产 cert 非验, 不在 scan 范围)。
  **澄清: F1 region_capacity 的 `cells_per_pose` 不是未守 SoT** —— 是 Gemini round-14 #5 **刻意
  信任 cert** (防 canonical pose-shape 微调时全 cut quarantine), 同 F9 tight-K 的 deferral 性质,
  **勿 consolidate** (改了会反转刻意决定)。
- **(2026-06-04 v28) F9 tight-K quarantine (supersedes Gemini round-4 oracle-trust
  deferral)**: density_envelope validator 对 `max_allowed_area = K < safe_ub` fail-
  closed 拒 (Phase 1.2 cert 不携带 replayable tight-bound proof)。净效果: F9 只剩
  K==safe_ub 的平凡 cut (`_validate_witness_overflow` 的 strict `>` 在 K==safe_ub
  不可满足 → F9 实质停用)。**这反转 Gemini round 4 "信任 oracle K、tight-K 重验
  defer P1.5+" 的判断**: replay 实证 validator 是信任边界且不重跑 oracle
  (`replay.py` 对 deserialized cert re-validate), 信任无法重算的 cert 标量 = replay
  时真 FP 暴露; 与上方 validator SoT gate 原则一致。恢复 tight F9 须在 Phase 1.5+
  给 cert 加 area-capacity proof-carrying 字段 + replay 校验 (与 F5 v1.0 信任
  INFEASIBLE 同类升级)。**解封时同步恢复**
  `test_generator_witness_canonical_order_independent_cert_hash` 的 cert_hash 不变量
  覆盖 (quarantine 期间该测试改为 assert 空)。与 "F9 area-based counting lock" 正交
  (不改计数 paradigm, 只加 K fail-closed gate)。
- **RAM 测量必走 psutil RSS** (Gemini round 25 B2 — Phase 1 OOM 防虚假 PASS):
  168h campaign cut store RAM 监测 (`exit_criteria` #6 + ramp report
  `cut_store_peak_mb_per_worker`) **必须** 用
  `psutil.Process(pid).memory_info().rss` 读 OS 级真物理内存. **禁** 用
  逻辑大小计算 (`sys.getsizeof(cut)` / JSON string len 累加 / `dict` len ×
  estimate). Why: Python 对象头 + dict/tuple/dataclass 小对象内存碎片化导致
  逻辑 3 GB → RSS 8 GB. 若 #6 PASS based on 逻辑大小但 RSS 已超 5 GB, 168h
  campaign 仍触发 OS OOM kill. Phase 1 ramp report 必 emit
  `rss_peak_mb_per_worker` field, exit_criteria 优先验该字段.
- **代数 vs 几何分工**: 全局代数约束 (e.g. power supply cap, total worker
  count) 必走 Master CP-SAT 线性约束, 不进 cut framework (Gemini round 22
  F16 verdict — "代数归 Master, 几何归 Cut").

## 4. Forbidden Changes

- Reintroducing exploratory caps as exact-mode bounds.
- Treating exploratory artifacts, legacy cuts, or diagnostic flow checks as certified proof.
- Changing campaign, artifact, or proof schemas without explicitly updating the lock/spec/test boundary together.
- Publishing a terminal `CERTIFIED` final result whose empty-rectangle `min_side` is below the canonical project `min_side_admissibility`, even if it was found in a superdomain run.
- Adding a new `candidate_generation` or `EXACT_*` certified-surface axis without first classifying it in the closed contract and adding fail-closed red tests.
- Rebinding globally pooled resources into per-line or per-instance hard bindings without a new exact proof basis.
- Adding any exterior-path requirement for the ghost rectangle.
- Enabling `EXACT_POWER_PLACEMENT_SUBPROBLEM=1` in any certified / production campaign path. The power-pole subproblem feature flag is exploratory only. Status of the three known exactness gaps (originally characterized in the GPT v4 review follow-up; 三项 status 至 v28 外审未变, gate 仍强制):
  - **Live ghost-conditioned infeasible cut**: implemented (`condition_lits` 走 master.add_benders_cut, `OnlyEnforceIf`).
  - **Persisted cut replay**: `BendersCut.condition_set` 在 `run_benders_for_ghost_rect` 现已通过 `_resolve_condition_lits_from_condition_set` 反解析回 master `u_var`, certified mode 下未知 condition fail-closed skip cut (不退化成无条件).
  - **Feasible-path pole alternatives**: 未实现 witness-complete cut. 现 stop-gap: `_add_exact_whole_layout_nogood` 在 flag on 且 solution 含 synthetic power_pole entry 时 fail-closed skip cut, caller 升 `UNKNOWN`. 真正解锁 feature 需要 enumeration / 多 witness 增量排除.
  
  The production readiness gate and `scripts/run_campaign_linux.sh` both still block when the env var is set; do not bypass them until pole alternatives is implemented and re-audited.

- Bypassing **exact-safe proof object lifecycle**. Any persisted artifact carrying solver-side semantics (e.g. `BendersCut.condition_set`, `BendersCut.metadata`) must have all six steps wired before being trusted in certified mode: generate → serialize → deserialize → validate → resolve runtime literals → replay → behavioral regression test. Landing a new schema field without the runtime resolver + regression coverage is treated as a Forbidden Change, regardless of how harmless the "feature gate currently off" feels.
- **(2026-05-22) Bypassing B Design v2 cut lifecycle**: new B Design v2
  cut object (Phase 1 起在 `src/cuts/` 落地) 必须 wire 全部 lifecycle 步骤
  （**canonicalize = Step 0 共用哈希/序列化基础、非业务步；业务链 9 步**，
  与 docs/项目说明/04 §2.2 / 06 / cut_lifecycle_v2 口径一致）:
  canonicalize → generate → minimize/normalize → serialize → deserialize →
  validate → attach-scope check → resolve → activation index → replay/regression.
  (Step 10 dominance/expiry/demotion defer to Phase 2 per Gemini round 13.)
  跳过任一步骤 (例如 Phase 1 implementation 没写 scope-aware replay 直接进
  168h campaign) 算 Forbidden Change. PoC `docs/research/p3_b_design_v2_20260521/
  poc/b_core_lifecycle_poc.py` 14/14 PASS 必跨 src/ boundary 真验.

  **Capacity-based Eviction 豁免** (Gemini round 24 B1 — A2 §4 vs A3 R2 冲突解):
  Step 10 dominance/expiry/demotion 严禁的是**语义级 expiry** (基于 cut
  hit-count / age / subsumption 主动 demote/expire). **不禁** capacity-based
  eviction — 当 cut store 达 RAM/disk 上限 (e.g. 5 GB/worker per criterion #6)
  时, 走 LRU/FIFO 驱逐**最近最不命中的 cut** (cut 仍 sound 只是工程上不存)
  防 OOM. 这是工程兜底, 不属于 Step 10. Phase 1 实施时驱逐 cut 必走
  `data/cuts/quarantine/evicted/` 子目录留 audit trail (不删, 168h close 后
  归档), 跟 Step 10 semantic expiry 不混.
- **(2026-05-22) Silent recovery 禁止**: B Design v2 9 family cut + replay
  全 fail-closed. cut.scope.source_digest 跟当前 source-of-truth hash 不一致
  → quarantine, **不可 auto-migrate**. 即使重算 cert 在新 source 下 sound,
  仍要手动 audit override (PROJECT_LOCK 一致 — certified exact 不允许 silent
  fix). Validator `ASSUMPTION_VERIFIERS` 未知 key → fail-closed return False
  (HOLD), 不可 silent return True. (Gemini round 14-22 共识 invariant.)

## 5. Allowed Changes

- Exact-safe lower bounds, dominance rules, reuse, caching, and scheduling improvements.
- Optional frontier probes that evaluate legitimate potential-domain candidates without weakening proof semantics.
- Additive postprocess exports, viewer/report sidecars, and delivery summaries.
- Additive neutral contract layers in `src/interchange/*` and build-time/export-time adapters in `src/adapters/*`.
- Adapter-side outer deployment planning/probing for larger IndustrialPlanner bases, plus optional exporter/throughput-manifest bridge metadata for those translated exports, may remain preserved as future-scope tooling provided those artifacts stay postprocess-only and are not promoted as certified evidence.
- Documentation, governance, provenance, and regression coverage improvements.
- Runtime discoverability improvements that do not alter solver semantics.

## 6. Update Rule

If a change affects exact boundaries, runtime roles, or certified output meaning, update:

1. `PROJECT_LOCK.md`
2. `FILE_STATUS.md`
3. the relevant spec(s)
4. the relevant regression tests
