# FILE_STATUS.md

**Status**: CURRENT_INVENTORY
**Updated**: 2026-06-06
**Purpose**: Inventory of runtime roles and trust status for the current repository.
**History**: Engineering history moved to [CHANGELOG.md](CHANGELOG.md).

<!-- DOC-SUBJECT:current_project_state FIELD:file_status_notice START sha256:ee2eef17f991a3f0c58e6c895874d1880ef696522dd12e3e373a561e963967c0 -->
This file is an inventory projection, not the living status authority. Current phase and cut-family status are governed by `docs/subjects/current_project_state.md`, `CLAUDE.md`, and `PROJECT_LOCK.md`. Older `CURRENT_CODE_ALIGNED` labels should be read with their recorded dates instead of as fresh audit claims.
<!-- DOC-SUBJECT:current_project_state FIELD:file_status_notice END -->


## Status Legend

- `CURRENT_CODE_ALIGNED`: active and trusted to match current runtime behavior
- `ACCEPTED_DRAFT`: usable design/spec support, but not the final truth source
- `HISTORICAL_OR_EXPLORATORY`: retained for context, experiments, or legacy compatibility
- `POSTPROCESS_ONLY`: additive output or visualization layer, not part of core proof semantics
- `FUTURE_SCOPE`: preserved for later reactivation, but intentionally excluded from the active checked-in audit / CI surface
- `EXTERNAL_ARTIFACT_REQUIRED`: required by the certified contract but intentionally absent from current lightweight GitHub `main`; restore before certified runs
- `MIXED`: wildcard path containing files with different trust levels; inspect per-file metadata

## Cut-family LBBD Path (当前范式, 2026-06-04 补)

> 9 个 cut family F1–F9 当 Benders cut 收紧 master（见 `PROJECT_LOCK.md` §2B + `specs/10_benders_decomposition_and_cut_design.md` + `CLAUDE.md`）。validator soundness（FP=0 信任边界）由 `src/tests/cuts/` 守，测试计数权威 = 核心节点 `authoritative_numbers.json` 的 `cuts_tests_total`。

| Path | Status | Runtime Role | Source-of-Truth Note |
|---|---|---|---|
| `src/cuts/lifecycle.py` | CURRENT_CODE_ALIGNED | cut proof lifecycle (generate→serialize→validate→resolve→replay) | `step_8_apply_to_master` 仍 `NotImplementedError`（P1.3B 真 master 集成待接） |
| `src/cuts/families/` (F1–F9) | CURRENT_CODE_ALIGNED | 9 cut-family generator + validator | region_capacity / cutset / port_exposure / component_reach / pattern_nogood / shape_packing_hall / power_hitting_set / power_grid_reach / density_envelope；validator 是 FP=0 信任边界 |
| `src/cuts/helpers/canonical_sot.py` | CURRENT_CODE_ALIGNED | 共享 canonical SoT 校验 helper | F7/F8 委托它（消私有副本）；fail-closed dims / radius 核对 |
| `src/cuts/oracles/` | CURRENT_CODE_ALIGNED | generator 侧 oracle（读 canonical 产 cert） | 产证非验证，不在 validator private-lookup scan 范围 |
| `src/cuts/assumptions/verifiers.py` | CURRENT_CODE_ALIGNED | attach-scope assumption verifiers | canonical pole-radius 等委托 `canonical_sot`（v28 fresh-pass 消第 4 个副本） |
| `src/models/pose_bool_exact_master.py` | CURRENT_CODE_ALIGNED | pose-bool exact master (B1) | `EXACT_USE_POSE_BOOL_MASTER` env 切换；residual/required-optional 建模（无 50/10 hard cap） |
| `src/tests/cuts/` | CURRENT_CODE_ALIGNED | cut-family validator 回归 + soundness 测试 | 计数权威见核心节点；含 forged-cert adversarial 回归 |
| `docs/research/p1_2_spike_sizing_gate_20260601/authoritative_numbers.json` | CURRENT_CODE_ALIGNED | 评审/文档权威数字单一来源（核心节点） | drift-test `src/tests/test_authoritative_numbers_currency.py` 焊 `cuts_tests_total` |

## Certified Exact Active Path

| Path | Status | Runtime Role | Source-of-Truth Note |
|---|---|---|---|
| `main.py` | CURRENT_CODE_ALIGNED | top-level certified/exploratory entry | runtime CLI and startup profile logging |
| `src/search/outer_search.py` | CURRENT_CODE_ALIGNED | production outer search | certified objective, frontier, campaign wiring, optional exact-safe probe scheduling |
| `src/search/campaign_telemetry.py` | CURRENT_CODE_ALIGNED | campaign telemetry aggregation | additive runtime diagnostics including probe activity |
| `src/search/benders_loop.py` | CURRENT_CODE_ALIGNED | certified candidate evaluation | exact master/binding/routing loop |
| `src/search/exact_campaign.py` | CURRENT_CODE_ALIGNED | campaign persistence | best certified result monotonicity and resume |
| `src/search/exact_parallel_scheduler.py` | CURRENT_CODE_ALIGNED | production parallel scheduling | coordinator-only writer, worker execution |
| `src/models/master_model.py` | CURRENT_CODE_ALIGNED | exact master placement model | coordinate exact mainline |
| `src/models/binding_subproblem.py` | CURRENT_CODE_ALIGNED | exact binding subproblem | certified subsolver path |
| `src/models/_cpsat_compat.py` | CURRENT_CODE_ALIGNED | CP-SAT compatibility shim | stabilizes enum/proto surfaces across OR-Tools versions |
| `src/models/routing_subproblem.py` | CURRENT_CODE_ALIGNED | exact routing subproblem | certified routing proof path |
| `rules/canonical_rules.json` | CURRENT_CODE_ALIGNED | frozen rules artifact | preprocess/runtime certified input; now carries consolidated recipes / production targets / commodity metadata / empty-rectangle admissibility |
| `data/preprocessed/candidate_placements.json` | EXTERNAL_ARTIFACT_REQUIRED | frozen placement domain | certified pose domain; omitted from current lightweight GitHub tree, expected SHA256 `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` |
| `data/preprocessed/mandatory_exact_instances.json` | CURRENT_CODE_ALIGNED | frozen exact instances | certified mandatory instance source |
| `data/preprocessed/generic_io_requirements.json` | CURRENT_CODE_ALIGNED | frozen generic IO artifact | binding/runtime certified input |

## Preprocess and Artifact Generation

| Path | Status | Runtime Role | Source-of-Truth Note |
|---|---|---|---|
| `src/preprocess/demand_solver.py` | CURRENT_CODE_ALIGNED | preprocess-only | demand, machine-count, port-budget, generic-IO generation |
| `src/preprocess/instance_builder.py` | CURRENT_CODE_ALIGNED | preprocess-only | exact/exploratory instance artifact generation |
| `src/preprocess/operation_profiles.py` | CURRENT_CODE_ALIGNED | preprocess-only | port-slot aggregation and operation summaries |
| `rules/preprocess_plan.json` | CURRENT_CODE_ALIGNED | build-time preprocess overlay | additive cycle-group / utility-operation overlay plus optional future overrides for PreprocessContext |
| `rules/preprocess_plan.schema.json` | CURRENT_CODE_ALIGNED | build-time preprocess schema | validates preprocess plan payloads |
| `src/interchange/preprocess_context.py` | CURRENT_CODE_ALIGNED | build-time preprocess contract | assembles canonical rules + preprocess plan without changing runtime truth |
| `src/placement/placement_generator.py` | CURRENT_CODE_ALIGNED | preprocess-only | candidate placement enumeration |
| `data/preprocessed/commodity_demands.json` | CURRENT_CODE_ALIGNED | frozen preprocess artifact | generated from demand solver |
| `data/preprocessed/machine_counts.json` | CURRENT_CODE_ALIGNED | frozen preprocess artifact | generated from demand solver |
| `data/preprocessed/port_budget.json` | CURRENT_CODE_ALIGNED | frozen preprocess artifact | generated from demand solver |
| `data/preprocessed/all_facility_instances.json` | HISTORICAL_OR_EXPLORATORY | exploratory/support artifact | not the certified mandatory instance source |
| `data/preprocessed/exploratory_optional_caps.json` | HISTORICAL_OR_EXPLORATORY | exploratory-only artifact | optional caps are not exact-mode bounds |

## Exploratory and Diagnostic Layers

| Path | Status | Runtime Role | Source-of-Truth Note |
|---|---|---|---|
| `src/models/flow_subproblem.py` | HISTORICAL_OR_EXPLORATORY | diagnostic/exploratory | not a certified proof source |
| `data/solutions/cuts_*.json` | HISTORICAL_OR_EXPLORATORY | legacy artifacts | not implicitly exact-safe |
| `temp_scripts/` (运行时/临时, 当前 repo 不含) | HISTORICAL_OR_EXPLORATORY | benchmark/dev utilities | runtime/ad-hoc 生成, not production source of truth |
| `logs/` / `temp_*.log` / `diag_log.txt` (运行时生成, 当前 repo 不含) | HISTORICAL_OR_EXPLORATORY | archive/debug output | runtime-generated, 运行时才出现 (`*.log` 受 .gitignore 挡) |

## Postprocess and Delivery

| Path | Status | Runtime Role | Source-of-Truth Note |
|---|---|---|---|
| `src/io/output_schema.py` | POSTPROCESS_ONLY | canonical blueprint schema | additive delivery contract |
| `src/io/serializer.py` | POSTPROCESS_ONLY | canonical output serialization | blueprint and render recovery helpers |
| `src/io/delivery_manifest.py` | POSTPROCESS_ONLY | delivery summary export | additive manifest writer with compatibility export discovery |
| `src/render/blueprint_exporter.py` | POSTPROCESS_ONLY | blueprint export wrapper | consumes canonical serializer and target export registry |
| `src/render/grid_visualizer.py` | POSTPROCESS_ONLY | optional visualization | supports blueprint-first + legacy fallback |
| `src/render/ascii_renderer.py` | POSTPROCESS_ONLY | optional visualization | synthetic/smoke rendering only |
| `src/render/image_renderer.py` | POSTPROCESS_ONLY | optional visualization wrapper | thin wrapper over current visualization path |
| `src/render/serve.py` | POSTPROCESS_ONLY | optional viewer launcher | copies canonical artifacts and best-effort viewer reports only |
| `src/render/report_builder.py` | POSTPROCESS_ONLY | viewer-side summary builder | additive report/view-model sidecar generation |
| `src/render/web_viewer/` | POSTPROCESS_ONLY | static browser viewer | blueprint-first viewer with local persistence/debug overlays plus optional current-release cards and grouped download links when release viewer metadata is present |
| `data/solutions/final_solution.json` | POSTPROCESS_ONLY | internal certified result export | additive output, not schema replacement |
| `data/blueprints/optimal_blueprint.json` | POSTPROCESS_ONLY | canonical delivery blueprint | derived from best certified result |
| `data/solutions/certified_delivery_manifest.json` | POSTPROCESS_ONLY | delivery summary artifact | additive, repo-relative artifact map |
| `data/exports/industrial_planner/*` | POSTPROCESS_ONLY | target export bundle | one-way compatibility output derived from the canonical blueprint |

## Docs, Runtime Tuning, and Governance

| Path | Status | Runtime Role | Source-of-Truth Note |
|---|---|---|---|
| `src/interchange/*` | POSTPROCESS_ONLY | neutral interchange contracts | additive adapter/export boundary, not solver truth |
| `src/adapters/endfield_calc/*` | POSTPROCESS_ONLY | build-time snapshot ingest | normalizes third-party JSON/TypeScript snapshots without runtime dependency |
| `src/adapters/base_planner/*` | MIXED | report-shape + outer-deployment helpers | wildcard spans active report-shape helpers plus preserved future-scope outer-deployment files; inspect specific rows below |
| `src/adapters/base_planner/outer_deployment_plan.py` | FUTURE_SCOPE | outer deployment sidecar IR | preserved larger-base translation sidecar for later reactivation; excluded from the active single-base 70×70 CI gate and still not certified evidence |
| `src/adapters/dige/*` | POSTPROCESS_ONLY | product-layer view models | cards/warnings/defaults only |
| `src/adapters/industrial_planner/*` | MIXED | one-way target export compatibility | wildcard spans active single-base export/audit surfaces plus preserved future-scope outer-deployment helpers; inspect specific rows below |
| `src/adapters/industrial_planner/commodity_resolver.py` | POSTPROCESS_ONLY | commodity translation / precise recipe inference | fail-closed adapter-scoped translation only; not certified solver truth |
| `src/adapters/industrial_planner/mapping_registry.py` | POSTPROCESS_ONLY | facility/routing target mapping | additive target mapping, boundary-port derivation, and pure-input loader admission/bus-geometry helpers only |
| `src/adapters/industrial_planner/export_blueprint.py` | POSTPROCESS_ONLY | target bundle assembly | emits IndustrialPlanner bundle + sidecar manifest/report only, including optional outer-plan translated exports, postprocess export mappings, loader-admission witnesses, and base-aware grouped input/output boundary-bus witness packing |
| `src/adapters/industrial_planner/recipe_matcher.py` | POSTPROCESS_ONLY | exact target recipe matching helpers | adapter-side exact machine/cycle/I-O signature matching only; not certified solver truth |
| `src/adapters/industrial_planner/throughput_audit.py` | POSTPROCESS_ONLY | static recipe/capacity conformance audit | adapter-side sidecar only; not runtime simulation or exact proof; counts explicit loader-admission plus grouped input/output bus witnesses conservatively, and can bridge translated exports via postprocess manifest mappings |
| `src/adapters/industrial_planner/blueprint_validator.py` | POSTPROCESS_ONLY | offline import/layout-health validator | validator sidecar only; not throughput simulation or exact proof |
| `src/adapters/industrial_planner/outer_export_probe.py` | FUTURE_SCOPE | outer-deployment export probe | preserved validator-grounded larger-base probe path for later reactivation; excluded from the active single-base CI gate and not canonical truth |
| `src/adapters/industrial_planner/deployment_transform.py` | FUTURE_SCOPE | target-side outer-deployment materialization helpers | preserved larger-base translation helpers for later reactivation; excluded from the active single-base CI gate and still postprocess-only |
| `PROJECT_LOCK.md` | CURRENT_CODE_ALIGNED | normative lock file | exactness boundaries and forbidden changes |
| `FILE_STATUS.md` | CURRENT_CODE_ALIGNED | inventory/status doc | runtime role map |
| `README.md` | CURRENT_CODE_ALIGNED | repo entry guide | top-level quick path into the active IndustrialPlanner single-base delivery surfaces, now including the browse-first/download-first repo-front entry split, plus the current project boundary |
| `CHANGELOG.md` | CURRENT_CODE_ALIGNED | engineering history log | canonical home for dated history |
| `specs/01_problem_statement.md` | CURRENT_CODE_ALIGNED | problem statement | current exact objective, admissibility, and geometry legality boundary |
| `specs/09_exact_grid_routing_subproblem.md` | CURRENT_CODE_ALIGNED | routing spec | splitter/merger support already present |
| `specs/11_pipeline_orchestration.md` | CURRENT_CODE_ALIGNED | orchestration spec | current runtime worker/default behavior |
| `specs/12_output_blueprint_schema.md` | CURRENT_CODE_ALIGNED | output contract spec | blueprint delivery schema |
| `specs/13_ecosystem_borrowing_and_compatibility_plan.md` | ACCEPTED_DRAFT | ecosystem upgrade plan | additive roadmap, not runtime truth |
| `specs/14_normalized_catalog_contract.md` | ACCEPTED_DRAFT | neutral catalog contract | additive adapter boundary spec |
| `specs/15_target_export_and_compatibility_manifest.md` | ACCEPTED_DRAFT | export/manifest contract | additive compatibility sidecar spec |
| `specs/16_industrial_planner_export_contract.md` | CURRENT_CODE_ALIGNED | target export contract | implemented one-way target bundle |
| `specs/17_endfield_calc_ingest_contract.md` | CURRENT_CODE_ALIGNED | upstream ingest contract | implemented JSON/TypeScript snapshot ingest surface |
| `docs/compatibility_matrix.md` | CURRENT_CODE_ALIGNED | ecosystem compatibility summary | current implementation matrix |
| `docs/parallel_configuration.md` | CURRENT_CODE_ALIGNED | runtime tuning guidance | memory and worker guidance for production parallel runs |
| `docs/frontier_probe_strategy.md` | CURRENT_CODE_ALIGNED | operator guidance | manual and automatic exact-safe probe workflow |
| `specs/18_preprocess_context_contract.md` | CURRENT_CODE_ALIGNED | preprocess context contract | current build-time context boundary |
| `specs/19_phase3_frozen_compatible_preprocess_regeneration.md` | CURRENT_CODE_ALIGNED | preprocess regeneration rollout spec | frozen-compatible parity and audit path |
| `specs/20_canonical_rules_consolidation.md` | CURRENT_CODE_ALIGNED | consolidation spec | current canonical-rules + overlay truth split after consolidation |
| `specs/21_frontier_probe_and_campaign_telemetry.md` | CURRENT_CODE_ALIGNED | probe scheduling spec | exact-safe probe insertion and telemetry contract |
| `specs/22_industrial_planner_precision_export_and_validator_spec.md` | CURRENT_CODE_ALIGNED | IndustrialPlanner precision export + validator spec | current Spec 22 implementation and evidence boundary |
| `specs/23_industrial_planner_outer_base_planning_representation.md` | CURRENT_CODE_ALIGNED | outer deployment representation spec | adapter-side outer-deployment planning/probe boundary, including larger-base translated and equal-size identity cases only; not certified evidence |
| `docs/industrial_planner_recipe_capacity_audit.md` | CURRENT_CODE_ALIGNED | IndustrialPlanner throughput-audit doc | adapter-side static recipe/capacity audit boundary and usage |
| `docs/industrial_planner_single_base_runbook.md` | CURRENT_CODE_ALIGNED | active single-base end-to-end runbook | standard operator path for `valley4_protocol_core` 70×70 from regenerated canonical truth through export/support/gate verification, including artifact-role and failure-class interpretation |
| `docs/industrial_planner_single_base_delivery_release.md` | CURRENT_CODE_ALIGNED | active single-base delivery release guide | explains how a delivery-ready `valley4_protocol_core` 70×70 run is promoted into a versioned release bundle/pointer plus current viewer + stable current landing/current bundle ZIP alias + repo-front current entry while keeping full-scale exact `CERTIFIED` status honestly open |
| `docs/industrial_planner_single_base_delivery_landing.md` | CURRENT_CODE_ALIGNED | stable current landing guide | documents the direct current-entry landing/download layer that resolves the current-viewer pointer into one fixed `current_delivery/` bundle, now with repo-relative checked-in metadata plus a one-file current bundle ZIP alias under `downloads/`, without widening scope |
| `docs/industrial_planner_single_base_delivery_frontdoor.md` | CURRENT_CODE_ALIGNED | repo-front entry guide | documents the higher-level checked-in entry page that now separates browse-first and download-first paths while mirroring the stable current bundle under a shorter top-level latest alias and surfacing the current clean/drift audit summary without widening scope |
| `docs/industrial_planner_single_base_delivery_entrypoints.md` | CURRENT_CODE_ALIGNED | aggregate active-entrypoints guide | documents the checked-in manifest that summarizes the current release/viewer/landing/latest-bundle surface plus the latest consumer-surface audit summary for script consumers and fail-closes on cross-surface drift |
| `docs/industrial_planner_single_base_delivery_surface_alignment.md` | CURRENT_CODE_ALIGNED | repo-front/entrypoints no-drift audit guide | documents the lightweight audit that rechecks the checked-in frontdoor helper links, aggregate active-entrypoints manifest, and the surfaced `surface_alignment_summary.{json,md,txt}` visibility chain without repromoting a release |
| `docs/industrial_planner_single_base_delivery_surface_health.md` | CURRENT_CODE_ALIGNED | compact current-surface health guide | documents the tiny checked-in `current_surface_health.{json,md,txt}` snapshot derived from the converged surface-alignment audit for zero-parse CI/reviewer/script consumers |
| `docs/phase3b_exact_endgame_execution_plan.md` | ACCEPTED_DRAFT | Phase 3B execution plan | detailed current-to-finish plan for the remaining solver-side exact closeout, including startline freeze, exact-safe shrink/triage loops, terminal proof freeze, and the later propagation of exact-close status back into the checked-in single-base release/frontdoor surface; roadmap only, not runtime truth |
| `docs/benchmarks/industrial_planner_validator_70x70.md` | CURRENT_CODE_ALIGNED | validator benchmark evidence doc | checked-in AC-B12 benchmark summary for the offline validator |
| `scripts/build_current_preprocess_context.py` | POSTPROCESS_ONLY | additive audit/build script | emits current context payload and parity reports |
| `data/solutions/current_preprocess_context.json` | POSTPROCESS_ONLY | audit artifact | current context payload exported for review |
| `data/solutions/preprocess_context_diff_report.json` | POSTPROCESS_ONLY | audit artifact | parity report for context-driven preprocess regeneration |
| `data/solutions/preprocess_context_diff_report.md` | POSTPROCESS_ONLY | audit artifact | human-readable parity summary |
| `data/examples/industrial_planner/*` | MIXED | IndustrialPlanner example and benchmark fixtures | wildcard spans active single-base fixtures plus preserved future-scope support/outer directories; inspect specific rows below |
| `data/examples/industrial_planner/full_demand_base_support_matrix.{json,md}` | POSTPROCESS_ONLY | checked-in full-demand base support report | active single-base decision-support matrix for `valley4_protocol_core` only, with dormant bases preserved as grouped future-scope metadata; not a schema/proof change |
| `data/examples/industrial_planner/full_demand_deployment_path_matrix.{json,md}` | POSTPROCESS_ONLY | checked-in dual-path full-demand support report | active single-base companion matrix that keeps the strict canonical 70×70 view intact while preserving dormant outer-path rows as future-scope metadata only; not a schema/proof change |
| `data/examples/industrial_planner/full_demand_support_overview.{json,md}` | POSTPROCESS_ONLY | checked-in umbrella support summary | regenerates the active single-base canonical/deployment reports together and records future-scope preservation metadata without widening scope; not a schema/proof change |
| `data/examples/industrial_planner/active_single_base_delivery_release.{json,md}` | POSTPROCESS_ONLY | checked-in current-release pointer | points at the current versioned `valley4_protocol_core` 70×70 delivery release bundle without claiming the exact full-scale terminal artifact is already done |
| `data/examples/industrial_planner/active_single_base_delivery_viewer.{json,md}` | POSTPROCESS_ONLY | checked-in current-viewer pointer | points at the current static browser-consumable viewer bundle for the active `valley4_protocol_core` 70×70 delivery release without widening the support contract |
| `data/examples/industrial_planner/current_delivery/*` | POSTPROCESS_ONLY | stable current landing/download bundle | fixed consumer entry built from the checked-in current-viewer pointer, with one landing page plus a copied viewer bundle under `current_delivery/viewer/` and pointer sidecars (`.json`/`.md`) under `current_delivery/downloads/` so downstream users do not need to guess the active release id (注: 同名 `.zip` 别名被 `.gitignore *.zip` 挡, 是 gitignored regenerable build 产物、**非 checked-in**; downstream 沿 sidecar 的 `bundle_zip` 路径取) |
| `data/examples/industrial_planner/index.html` | POSTPROCESS_ONLY | repo-front current entry page | higher-level checked-in entry page that now splits into browse-first/download-first paths, uses a shorter top-level latest bundle ZIP alias as the download-first primary action, and surfaces the aggregate `active_single_base_delivery_entrypoints.{json,md}` pair plus both the detailed `surface_alignment_summary.{json,md,txt}` trio and the compact `current_surface_health.{json,md,txt}` trio so humans/scripts/reviewers share one current-entry surface |
| `data/examples/industrial_planner/frontdoor_manifest.json` | POSTPROCESS_ONLY | repo-front current entry manifest | machine-readable summary of the higher-level current entry page, including browse-first/download-first `entry_modes`, the shorter top-level latest bundle ZIP alias, forwarded download/viewer links, aggregate script-entrypoint links, converged surface-audit summary fields/paths, and the surfaced compact current-surface-health refs/summary fields that now re-close against the checked-in health snapshot itself |
| `data/examples/industrial_planner/industrial_planner_latest_single_base_delivery_bundle.zip` | POSTPROCESS_ONLY (gitignored, 非 checked-in) | repo-front latest bundle ZIP alias | shorter alias mirroring the current-delivery bundle ZIP. **⚠️ 被 `.gitignore *.zip` 挡 → 是本地 regenerate 的 build 产物、非 checked-in**; `index.html` download-first 指向它需先本地 regenerate (或给该 alias 加 `.gitignore !` 白名单真正提交)。checked-in 的只有同名 `.{json,md}` sidecar |
| `data/examples/industrial_planner/latest_single_base_delivery_bundle.{json,md}` | POSTPROCESS_ONLY | repo-front latest bundle pointer sidecars | machine/human pointer sidecars for the shorter top-level latest bundle alias, including the source current-delivery ZIP path and the honest exact-open note |
| `data/examples/industrial_planner/active_single_base_delivery_entrypoints.{json,md}` | POSTPROCESS_ONLY | aggregate current-entrypoints manifest | machine/human aggregate summary for script consumers that need one checked-in file describing the current release pointer, current viewer, stable landing bundle, top-level latest bundle alias, the latest consumer-surface clean/drift audit summary, and the compact current-surface-health snapshot, now with self-checked surfaced audit refs/counts and surfaced health refs/counts |
| `data/examples/industrial_planner/current_surface_health.{json,md,txt}` | POSTPROCESS_ONLY | compact current-surface health snapshot | tiny checked-in health artifact derived from the converged surface-alignment audit so CI, reviewer tooling, and scripts can read the active consumer-surface clean/drift verdict and top-line counts without parsing the full audit payload |
| `data/examples/industrial_planner/releases/*` | POSTPROCESS_ONLY | versioned single-base delivery bundles | promoted release bundles for the active `valley4_protocol_core` 70×70 line, including canonical/export/support/check artifacts plus release manifest and checksums; preserved as delivery references, not CI truth |
| `data/examples/industrial_planner/releases/release_index.{json,md}` | POSTPROCESS_ONLY | single-base delivery release index | machine/human index of versioned active-contract release bundles with one current-release marker |
| `data/examples/industrial_planner/viewers/*` | POSTPROCESS_ONLY | versioned single-base delivery viewer bundles | browser-consumable static viewer bundles keyed by promoted release id, derived from the active single-base delivery release and kept separate from the checksum-tracked core payload |
| `data/examples/industrial_planner/viewers/viewer_index.{json,md}` | POSTPROCESS_ONLY | single-base delivery viewer index | machine/human index of versioned active-contract viewer bundles with one current-viewer marker |
| `data/examples/industrial_planner/protocol_core_transition_support_suite/*` | FUTURE_SCOPE | focused checked-in support report set | preserved two-base valley4/wuling transition slice for later reactivation; excluded from the active single-base inventory and CI gate |
| `data/examples/industrial_planner/full_demand_support_suite_inventory.json` | POSTPROCESS_ONLY | checked-in support-suite inventory | repo-local inventory of checked-in strict/deployment decision-surface report sets with one active single-base report set plus explicit future-scope/deactivated entries; not canonical truth or certified evidence |
| `data/examples/industrial_planner/generated_outer_base_bundle/*` | FUTURE_SCOPE | outer deployment probe artifacts | preserved translated larger-base planning/probe outputs for later reactivation; excluded from the active single-base checked-artifact gate and not canonical truth or certified evidence |
| `data/examples/industrial_planner/generated_outer_base_bundle_valley4_protocol_core/*` | FUTURE_SCOPE | outer deployment probe artifacts | preserved degenerate identity outer-deployment outputs for later reactivation; excluded from the active single-base checked-artifact gate and not canonical truth or certified evidence |
| `data/examples/industrial_planner/outer_base_bundle_inventory.json` | FUTURE_SCOPE | checked-in outer bundle inventory | preserved inventory of outer-deployment example bundles for later reactivation; excluded from the active checked-artifact family inventory and CI gate |
| `data/examples/industrial_planner/checked_artifact_family_inventory.json` | POSTPROCESS_ONLY | checked-artifact family inventory | repo-local inventory-of-inventories for the repo-level IndustrialPlanner gate; the active entries now point only at the single support-suite family while dormant outer families remain preserved as future-scope metadata |
| `data/examples/industrial_planner/benchmark.full70x70.blueprint.json` | POSTPROCESS_ONLY | validator benchmark fixture | deterministic 70×70-scale benchmark input for the offline validator |
| `data/examples/industrial_planner/benchmark.full70x70.benchmark.json` | POSTPROCESS_ONLY | benchmark evidence artifact | raw benchmark stats captured from the checked-in harness |
| `specs/ecosystem_notes/*` | ACCEPTED_DRAFT | borrowing/provenance notes | source-analysis notes for adapter/product work |
| `BORROWED_COMPONENTS.md` | CURRENT_CODE_ALIGNED | provenance summary | records borrowed ideas and copy posture |
| `third_party_snapshots/*` | POSTPROCESS_ONLY | vendored fixture/snapshot inputs | build-time adapter fixtures only; vendored endfield-calc raw repository fixture refreshed 2026-05-08 to package `0.6.2` master commit `49be16e1` (178 items / 260 recipes / 16 facilities); IndustrialPlanner BASES field-subset vendored under `industrial_planner/bases/` from branch `v2` commit `c494c5ae` (7 bases). Refresh both via `scripts/refresh_endfield_calc_snapshot.py` and `scripts/refresh_industrial_planner_bases.py` — neither touches canonical_rules.json. |
| `scripts/build_*.py` / `scripts/snapshot_endfield_calc.py` / `scripts/export_industrial_planner_bundle.py` | POSTPROCESS_ONLY | additive tooling | optional build/report/export utilities, including deterministic IndustrialPlanner fixture regeneration and optional outer-plan translated bundle export |
| `scripts/build_industrial_planner_full_demand_fixture.py` | POSTPROCESS_ONLY | full-demand fixture planner/regenerator | derives explicit boundary-slot layout from current generic-I/O truth plus exporter/validator feedback, while failing closed outside the canonical 70×70 contract |
| `scripts/run_industrial_planner_single_base_e2e.py` | POSTPROCESS_ONLY | active single-base end-to-end workflow | regenerates the active canonical fixture, writes the IndustrialPlanner bundle, refreshes a fresh support-report set, rechecks the checked-in support/checked-artifact inventories, and emits a failure-classified run summary without widening the single-base contract |
| `scripts/build_industrial_planner_single_base_delivery_release.py` | POSTPROCESS_ONLY | versioned single-base delivery release builder | promotes a delivery-ready `valley4_protocol_core` 70×70 end-to-end run into a versioned release bundle with release manifest, checksums, current-release pointer, release index, versioned viewer bundle, current-viewer pointer/index, a stable current landing/download directory with a one-file ZIP alias, a repo-front current-entry page plus top-level latest bundle alias, an aggregate current-entrypoints manifest, a lightweight repo-front/entrypoints no-drift audit summary, and a compact `current_surface_health.{json,md,txt}` snapshot; it now refreshes that audit, emits the smaller health snapshot from the converged audit output, re-surfaces the audit back into the frontdoor/aggregate manifests, then re-runs the audit on the final checked-in surface and fail-closes on drift |
| `src/render/industrial_planner_single_base_delivery_viewer.py` | POSTPROCESS_ONLY | active-current-release viewer bundle builder | resolves the checked-in single-base delivery pointer into a compact static viewer bundle, regenerates viewer-side summary data, prunes geometry pools to the poses actually used by the release-associated canonical blueprint, and groups release/support/gate/meta downloads without widening scope |
| `scripts/build_industrial_planner_single_base_delivery_viewer.py` | POSTPROCESS_ONLY | active single-base delivery viewer bundle builder | materializes a static browser viewer bundle from the checked-in current-release pointer, with grouped downloads and active-contract scope messaging for the `valley4_protocol_core` 70×70 line |
| `src/render/industrial_planner_single_base_delivery_landing.py` | POSTPROCESS_ONLY | stable current landing bundle builder | resolves the checked-in current-viewer pointer into one fixed current-delivery directory with a copied viewer bundle under `viewer/`, grouped downloads, a one-file current bundle ZIP alias under `downloads/`, and an explicit active-contract/exact-open landing page |
| `scripts/build_industrial_planner_single_base_delivery_landing.py` | POSTPROCESS_ONLY | stable current landing bundle builder CLI | materializes the direct current-entry landing/download page plus current bundle ZIP alias from the checked-in current-viewer pointer without repromoting a release |
| `src/render/industrial_planner_single_base_delivery_frontdoor.py` | POSTPROCESS_ONLY | repo-front current-entry builder | resolves the checked-in current-delivery landing bundle into a higher-level repo-facing index/manifest pair with explicit browse-first/download-first paths, a ZIP-first download action, fail-closed action checks, and optional helper links/status cards for both the aggregate current-entrypoints manifest, the latest surface-alignment audit summary, and the compact `current_surface_health.{json,md,txt}` snapshot so human/script/reviewer entry surfaces stay aligned without widening scope |
| `scripts/build_industrial_planner_single_base_delivery_frontdoor.py` | POSTPROCESS_ONLY | repo-front current-entry builder CLI | materializes the higher-level checked-in current entry page from the stable current-delivery landing bundle, now with explicit browse-first/download-first paths, a ZIP-first primary download action, and optional/required helper links to the aggregate current-entrypoints manifest, the surface-alignment audit summary, and the compact current-surface-health snapshot, without repromoting a release |
| `src/render/industrial_planner_single_base_delivery_entrypoints.py` | POSTPROCESS_ONLY | aggregate current-entrypoints builder | resolves the checked-in current release/viewer/landing/frontdoor/latest-bundle surface into one fail-closed machine/human manifest pair for script consumers, now also surfacing both the latest consumer-surface audit summary and the compact current-surface-health snapshot when present |
| `scripts/build_industrial_planner_single_base_delivery_entrypoints.py` | POSTPROCESS_ONLY | aggregate current-entrypoints builder CLI | materializes the checked-in one-file current-entrypoint summary from already-promoted release/viewer/landing/frontdoor/latest-bundle outputs, optionally requiring both the surface-alignment audit summary and the compact current-surface-health snapshot, without repromoting a release |
| `src/render/industrial_planner_single_base_delivery_surface_alignment.py` | POSTPROCESS_ONLY | repo-front/entrypoints no-drift audit core | audits the checked-in repo-front frontdoor HTML/manifest and aggregate active-entrypoints manifest for consumer-surface drift without rebuilding them, now also fail-closing on both surfaced surface-audit refs/metadata drift and surfaced `current_surface_health.{json,md,txt}` refs/metadata drift |
| `scripts/audit_industrial_planner_single_base_delivery_surface_alignment.py` | POSTPROCESS_ONLY | repo-front/entrypoints no-drift audit CLI | emits JSON/Markdown/plain-text summaries for the lightweight checked-in consumer-surface audit, can explicitly require surfaced current-surface-health visibility, and exits non-zero on drift |
| `src/render/industrial_planner_single_base_delivery_surface_health.py` | POSTPROCESS_ONLY | compact current-surface health builder | compresses the converged checked-in surface-alignment audit down to `current_surface_health.{json,md,txt}` for zero-parse consumers while preserving the detailed audit as the source of truth |
| `scripts/build_industrial_planner_single_base_delivery_surface_health.py` | POSTPROCESS_ONLY | compact current-surface health builder CLI | materializes the checked-in `current_surface_health.{json,md,txt}` trio from the detailed surface-alignment audit without repromoting a release |
| `docs/industrial_planner_single_base_delivery_viewer.md` | CURRENT_CODE_ALIGNED | viewer-bundle runbook | documents both the checked-in promotion path and the ad hoc local build path for the active single-base delivery viewer bundle while keeping other bases as future-scope |
| `scripts/build_industrial_planner_outer_base_plan.py` | FUTURE_SCOPE | outer deployment sidecar generator | preserved helper for the dormant larger-base translation subsystem; excluded from the active single-base CI gate |
| `scripts/probe_industrial_planner_outer_base_export.py` | FUTURE_SCOPE | outer deployment validator probe CLI | preserved helper for the dormant larger-base translation subsystem; excluded from the active single-base CI gate |
| `scripts/audit_industrial_planner_outer_base_bundle.py` | FUTURE_SCOPE | outer-deployment bundle audit | preserved no-drift workflow for dormant outer-deployment bundles; excluded from the active single-base checked-artifact gate |
| `scripts/audit_industrial_planner_checked_artifact_suite.py` | POSTPROCESS_ONLY | repo-level IndustrialPlanner checked-artifact gate | consumes the checked-in checked-artifact family inventory, dispatches to each active family-specific inventory-driven no-drift workflow, and can emit JSON/Markdown/plain-text summaries so CI can fail closed on stale single-base decision reports without hard-coding family wiring in the top-level gate |
| `scripts/audit_industrial_planner_outer_base_bundle_suite.py` | FUTURE_SCOPE | inventory-driven outer-base bundle audit | preserved inventory-driven checker for dormant outer-deployment bundles; excluded from the active single-base checked-artifact gate |
| `.github/workflows/industrial_planner_checked_artifacts.yml` | POSTPROCESS_ONLY | repo automation / CI gate | installs the pinned Python toolchain, runs focused IndustrialPlanner regression coverage for the active single-base support surface, executes the repo-level family-inventory-driven gate on relevant active-scope changes, and uploads JSON/Markdown/plain-text summaries only |
| `.github/workflows/industrial_planner_single_base_delivery_surfaces.yml` | POSTPROCESS_ONLY | repo automation / consumer-surface gate | installs the pinned Python toolchain, runs focused viewer/landing/frontdoor/entrypoints/release regressions for the active single-base consumer surface, executes the lightweight repo-front/aggregate-entrypoints no-drift audit, and uploads JSON/Markdown/plain-text summaries |
| `scripts/industrial_planner_scope.py` | POSTPROCESS_ONLY | support-audit scope metadata helper | centralizes the active single-base contract plus grouped future-scope base metadata for the checked-in IndustrialPlanner reports only |
| `src/tests/test_outer_base_deployment_plan.py` | FUTURE_SCOPE | dormant outer-deployment regression | preserved for later reactivation of the larger-base translation subsystem; excluded from the active single-base CI gate |
| `src/tests/test_industrial_planner_outer_export.py` | FUTURE_SCOPE | dormant outer-export regression | preserved for later reactivation of the larger-base translation subsystem; excluded from the active single-base CI gate |
| `src/tests/test_industrial_planner_outer_throughput_audit.py` | FUTURE_SCOPE | dormant outer-throughput regression | preserved for later reactivation of the larger-base translation subsystem; excluded from the active single-base CI gate |
| `src/tests/test_industrial_planner_outer_base_bundle_audit.py` | FUTURE_SCOPE | dormant outer-bundle regression | preserved for later reactivation of the larger-base translation subsystem; excluded from the active single-base CI gate |
| `src/tests/test_industrial_planner_outer_base_bundle_suite.py` | FUTURE_SCOPE | dormant outer-bundle inventory regression | preserved for later reactivation of the larger-base translation subsystem; excluded from the active single-base CI gate |
| `scripts/audit_industrial_planner_full_demand_base_matrix.py` | POSTPROCESS_ONLY | single-base-first full-demand support audit | defaults to the active `valley4_protocol_core` 70×70 contract, records dormant bases as grouped future-scope metadata, and still supports explicit subsets when future work needs them |
| `scripts/audit_industrial_planner_full_demand_deployment_matrix.py` | POSTPROCESS_ONLY | single-base-first full-demand deployment audit | defaults to the active `valley4_protocol_core` 70×70 contract, preserves dormant outer-path rows as future-scope metadata, and only evaluates outer deployment when explicitly requested for future work |
| `scripts/audit_industrial_planner_full_demand_support_suite.py` | POSTPROCESS_ONLY | umbrella full-demand support workflow | regenerates the active single-base canonical matrix, the companion future-scope deployment matrix, and the cross-view overview together, and can fail closed in `--check` mode when that checked-in decision surface drifts |
| `scripts/audit_industrial_planner_full_demand_support_suite_inventory.py` | POSTPROCESS_ONLY | inventory-driven full-demand support audit | consumes the checked-in support-suite inventory, regenerates the active single-base report set plus any future explicit subsets, can fail closed in `--check` mode when listed decision-surface artifacts drift, and tracks future-scope preservation metadata |
| `scripts/audit_industrial_planner_throughput.py` | POSTPROCESS_ONLY | throughput-audit CLI | writes adapter-side throughput audit JSON/Markdown sidecars only |
| `scripts/benchmark_industrial_planner_validator.py` | POSTPROCESS_ONLY | validator benchmark harness | reproducible benchmark runner for AC-B12 evidence only |
| `specs/*.md` | MIXED | documentation | inspect per-file metadata for trust level |
| `scripts/*.ps1` | CURRENT_CODE_ALIGNED | launcher/benchmark wrappers | wrappers, not precedence truth source |
