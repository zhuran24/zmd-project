# 04. Proof-bearing sink inventory audit

review_anchor: `v99_p1_2_close_kernel_sealing`
sink_count: `50`

## Scan contract

scan_roots: `['src', 'scripts/check_p1_2_proof_obligations.py', 'scripts/build_industrial_planner_single_base_delivery_release.py']`
excluded_subpaths: `['src/tests', 'src/search/phase3b', 'src/ai_accel', 'src/runtime', 'src/preprocess', '.artifacts', '.pytest_tmp', 'cc_memory']`
proof_bearing_tokens: `['CERTIFIED', 'INFEASIBLE', 'RUN_STATUS_CERTIFIED', 'RUN_STATUS_INFEASIBLE', 'terminal_frontier_evidence', 'best_certified_result', 'certified_surface', 'proof_source', 'certified_delivery_manifest.json', 'final_solution.json', 'optimal_blueprint.json', 'proof-bearing', 'proof_bearing']`

Excluded paths are limited to test/non-authority or out-of-scope trees. Core source directories such as `src/search`, `src/io`, `src/models`, and `src/cuts` remain scanned.

## Classification counts

| classification | count |
|---|---|
| diagnostic_or_telemetry_non_authority | 2 |
| exploratory_or_heuristic_non_authority | 1 |
| non_authoritative_projection | 11 |
| p1_2_certified_path | 29 |
| p1_2_close_kernel | 1 |
| p1_2_public_surface | 6 |

## Obligation counts

| obligation | count |
|---|---|
| PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | 20 |
| PO-CERTIFIED-EXPORT-SURFACE | 17 |
| PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE | 4 |
| PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS | 4 |
| PO-P1-2-CLOSE-KERNEL-SEALING | 4 |
| PO-STEP7-ATTACH-MIRROR | 1 |

## Registered sinks

| # | path | classification | obligation | terms | guard tokens | sha256 prefix |
|---:|---|---|---|---|---|---|
| 1 | `scripts/build_industrial_planner_single_base_delivery_release.py` | p1_2_public_surface | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED, certified_surface, final_solution.json, optimal_blueprint.json` | `normalize_non_authoritative_exact_status, normalize_non_authoritative_exact_note, may not claim` | `6cd8480f4b3c97b5` |
| 2 | `scripts/check_p1_2_proof_obligations.py` | p1_2_close_kernel | PO-P1-2-CLOSE-KERNEL-SEALING | `CERTIFIED, INFEASIBLE, terminal_frontier_evidence, best_certified_result, certified_surface, final_solution.json, proof-bearing, proof_bearing` | `close_kernel_contract, _check_close_kernel_contract, source_sha256_drift_reopens_p1_2_close_claim` | `c125eab7d1e5628f` |
| 3 | `src/adapters/industrial_planner/export_blueprint.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `optimal_blueprint.json` | `optimal_blueprint.json` | `9a5410b559a0e4c9` |
| 4 | `src/adapters/industrial_planner/mapping_registry.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `optimal_blueprint.json` | `optimal_blueprint.json` | `7e20051ff2a4eddc` |
| 5 | `src/cuts/families/pattern_nogood.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `c65eb8296c9c3706` |
| 6 | `src/cuts/helpers/bounded_core_minimizer.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `da3184e860ea49fa` |
| 7 | `src/cuts/lifecycle.py` | p1_2_certified_path | PO-STEP7-ATTACH-MIRROR | `proof-bearing` | `proof-bearing` | `3b63cb3d18d5d0ba` |
| 8 | `src/cuts/oracles/pattern_nogood_oracle.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `019d808d18619c9f` |
| 9 | `src/cuts/oracles/power_cover_oracle.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `161e513cde4fbfa0` |
| 10 | `src/cuts/oracles/region_capacity_oracle.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `95b65c40a02dea29` |
| 11 | `src/cuts/oracles/shape_packing_hall_oracle.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `44111273420eaf00` |
| 12 | `src/io/delivery_manifest.py` | p1_2_public_surface | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED, best_certified_result, certified_surface, certified_delivery_manifest.json, final_solution.json` | `validate_certified_delivery_manifest_matches_campaign, validate_delivery_artifacts_match_campaign, write_certified_delivery_manifest` | `dbaf33755a7e1d17` |
| 13 | `src/io/output_schema.py` | p1_2_public_surface | PO-CERTIFIED-EXPORT-SURFACE | `optimal_blueprint.json` | `optimal_blueprint.json` | `78900b3f252534e3` |
| 14 | `src/io/serializer.py` | p1_2_public_surface | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED, optimal_blueprint.json` | `CERTIFIED, optimal_blueprint.json` | `b0186ce5582e5695` |
| 15 | `src/models/abstract_routing_layer.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `1f1f71258a840d87` |
| 16 | `src/models/binding_subproblem.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `ea5e277879efea9b` |
| 17 | `src/models/cpsat_minimum_model.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `92d9e9eed88dbf66` |
| 18 | `src/models/cut_manager.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `CERTIFIED, INFEASIBLE, RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE` | `CERTIFIED, INFEASIBLE` | `ebf8663111571c45` |
| 19 | `src/models/d2_commodity_flow_core.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `55aee97d9162541e` |
| 20 | `src/models/exact_coordinate_master.py` | p1_2_certified_path | PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `8d4d9f1c09f8f2d2` |
| 21 | `src/models/flow_subproblem.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `1d3d0f174e23feb6` |
| 22 | `src/models/highs_candidate_evaluator.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `CERTIFIED, INFEASIBLE` | `CERTIFIED, INFEASIBLE` | `1709e1536a49f11e` |
| 23 | `src/models/highs_master_model.py` | p1_2_certified_path | PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `ab366573359ec1db` |
| 24 | `src/models/master_model.py` | p1_2_certified_path | PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `437dcf94703fff82` |
| 25 | `src/models/patch_routing_core.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `371cdf69c6d30a14` |
| 26 | `src/models/power_placement_subproblem.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `88573b3ebdf26a33` |
| 27 | `src/models/routing_subproblem.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `25c56e1f5f383f86` |
| 28 | `src/models/scip_master_model.py` | p1_2_certified_path | PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `d3590b07088e4e67` |
| 29 | `src/render/industrial_planner_exact_status.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED, certified_surface` | `normalize_non_authoritative_exact_status, _RESERVED_CERTIFIED_TOKEN, normalize_non_authoritative_exact_note` | `22875159909302a5` |
| 30 | `src/render/industrial_planner_single_base_delivery_entrypoints.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED` | `CERTIFIED` | `e80cc8d6c4badada` |
| 31 | `src/render/industrial_planner_single_base_delivery_frontdoor.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED` | `CERTIFIED` | `5e530baaa4e49e14` |
| 32 | `src/render/industrial_planner_single_base_delivery_landing.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED` | `CERTIFIED` | `085212ba166c2211` |
| 33 | `src/render/industrial_planner_single_base_delivery_surface_alignment.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED` | `CERTIFIED` | `f3bc8bec1160f97c` |
| 34 | `src/render/industrial_planner_single_base_delivery_surface_health.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED` | `CERTIFIED` | `788fd78ad6fcf6d9` |
| 35 | `src/render/industrial_planner_single_base_delivery_viewer.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `final_solution.json, optimal_blueprint.json` | `final_solution.json, optimal_blueprint.json` | `7999354932833774` |
| 36 | `src/render/report_builder.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `optimal_blueprint.json` | `optimal_blueprint.json` | `c92f43fc9e305f8e` |
| 37 | `src/render/serve.py` | non_authoritative_projection | PO-CERTIFIED-EXPORT-SURFACE | `final_solution.json, optimal_blueprint.json` | `final_solution.json, optimal_blueprint.json` | `038160a4155b2f7a` |
| 38 | `src/search/benders_loop.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `CERTIFIED, INFEASIBLE, RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE` | `partial_due_to_time_budget, _CERTIFIED_UNCLASSIFIED_ENV_BLOCKER_CODE, _CERTIFIED_PROOF_SEMANTICS_ENV_BLOCKER_CODE` | `0205ffe8e33674af` |
| 39 | `src/search/campaign_telemetry.py` | diagnostic_or_telemetry_non_authority | PO-P1-2-CLOSE-KERNEL-SEALING | `CERTIFIED, INFEASIBLE, RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE, proof_source` | `CERTIFIED, INFEASIBLE` | `b6582c452b39c444` |
| 40 | `src/search/campaign_triage.py` | diagnostic_or_telemetry_non_authority | PO-P1-2-CLOSE-KERNEL-SEALING | `INFEASIBLE, RUN_STATUS_INFEASIBLE` | `INFEASIBLE, RUN_STATUS_INFEASIBLE` | `0ce473249d0a78e4` |
| 41 | `src/search/certified_frontier.py` | p1_2_certified_path | PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE | `CERTIFIED, INFEASIBLE, RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE, terminal_frontier_evidence` | `build_terminal_frontier_evidence, terminal_frontier_evidence_violation, TERMINAL_FRONTIER_EVIDENCE_SOURCE` | `3ead765526029de3` |
| 42 | `src/search/certified_surface.py` | p1_2_public_surface | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED, best_certified_result, certified_surface, certified_delivery_manifest.json, final_solution.json, optimal_blueprint.json` | `verify_certified_delivery_surface, evaluate_certified_delivery_surface` | `ca66ebacf68791c0` |
| 43 | `src/search/d2_separator.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `0263f50142b72833` |
| 44 | `src/search/exact_campaign.py` | p1_2_certified_path | PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE | `CERTIFIED, INFEASIBLE, terminal_frontier_evidence, best_certified_result, certified_surface, final_solution.json, optimal_blueprint.json, proof-bearing` | `validate_exact_campaign_resume_state, terminal_frontier_evidence, best_certified_result` | `529c93b5dc49a6f5` |
| 45 | `src/search/exact_campaign_inspector.py` | p1_2_public_surface | PO-CERTIFIED-EXPORT-SURFACE | `CERTIFIED, INFEASIBLE, best_certified_result, certified_surface, final_solution.json, optimal_blueprint.json` | `CERTIFIED, INFEASIBLE` | `b50bf8675156ba4e` |
| 46 | `src/search/exact_parallel_scheduler.py` | p1_2_certified_path | PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE | `CERTIFIED, INFEASIBLE` | `worker` | `e07c926505e030ed` |
| 47 | `src/search/heuristic_feasible_finder.py` | exploratory_or_heuristic_non_authority | PO-P1-2-CLOSE-KERNEL-SEALING | `CERTIFIED, INFEASIBLE` | `CERTIFIED, INFEASIBLE` | `0f9723671ddee8dd` |
| 48 | `src/search/outer_search.py` | p1_2_certified_path | PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE | `CERTIFIED, INFEASIBLE, RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE, terminal_frontier_evidence, best_certified_result, certified_surface` | `build_terminal_frontier_evidence, _parallel_wave_result_identity_failure, _parallel_wave_failure_discards_results` | `bc996216f0dd9088` |
| 49 | `src/search/patch_conflict_separator.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `4c468f34bb620dbf` |
| 50 | `src/search/smt_mt_outer_pruning.py` | p1_2_certified_path | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | `INFEASIBLE` | `INFEASIBLE` | `004ce7151b8fc4dc` |

## Negative control result

A rogue source file `src/search/rogue_certified_sink.py` returning `{"status": "CERTIFIED"}` was added in a temporary copy. The proof-obligation gate failed with `unregistered proof-bearing close-kernel sink`, recorded as mutation M1 in `06_mutation_logs/M1.md`.

Result: current sinks are registered, no dangerous scan blind spot was found in the close-kernel roots, and the rogue sink negative control fails closed.
