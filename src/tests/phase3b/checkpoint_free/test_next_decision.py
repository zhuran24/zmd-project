from __future__ import annotations

import json
from pathlib import Path

from scripts.phase3b.checkpoint_free.build_next_decision import (
    build_checkpoint_free_next_decision,
    write_checkpoint_free_next_decision,
)


def test_next_decision_advances_safe_completed_candidates_and_blocks_stage_risk(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    _write_readiness(readiness_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run("B0_prod_4x4", score=1.0, peak_private=14.0),
            _run("experimental_13900ks_htoff_2x10_global_normal", score=1.02, peak_private=8.0),
            _run("experimental_13900ks_htoff_4x5_global_normal", score=1.01, peak_private=14.0),
            _run(
                "W1_prod_4x4_stage_6_4_2_4",
                status="stopped_resource_limit",
                score=0.25,
                peak_private=45.0,
                resource_stop=True,
            ),
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
    )

    assert decision["recommendation"]["next_candidate_ids"] == [
        "B0_prod_4x4",
        "experimental_13900ks_htoff_4x5_global_normal",
        "experimental_13900ks_htoff_2x10_global_normal",
    ]
    by_id = {item["candidate_id"]: item for item in decision["candidate_decisions"]}
    assert by_id["W1_prod_4x4_stage_6_4_2_4"]["decision"] == "hold"
    assert by_id["W3_prod_4x4_stage_6_6_2_6"]["decision"] == "blocked"
    assert by_id["W6_prod_3x_stage_8_6_2_6"]["reason"] == "blocked_after_w1_resource_stop"
    assert decision["safety"]["proof_source"] is False


def test_next_decision_holds_timeout_high_memory_candidate(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    _write_readiness(readiness_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run("B0_prod_4x4", score=1.0, peak_private=14.0),
            _run(
                "experimental_13900ks_htoff_3x8_global_normal",
                status="timeout",
                score=0.2,
                peak_private=41.0,
                timed_out=True,
            ),
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
    )

    by_id = {item["candidate_id"]: item for item in decision["candidate_decisions"]}
    assert by_id["experimental_13900ks_htoff_3x8_global_normal"]["decision"] == "hold"
    assert by_id["experimental_13900ks_htoff_3x8_global_normal"]["reason"] == (
        "timeout_or_high_memory_with_low_relative_throughput"
    )


def test_next_decision_blocks_experiments_after_baseline_600s_resource_stop(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    _write_readiness(readiness_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            ),
            _run("experimental_13900ks_htoff_2x10_global_normal", score=4.2, peak_private=8.0),
            _run("experimental_13900ks_htoff_4x5_global_normal", score=4.1, peak_private=14.0),
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
    )

    assert decision["recommendation"]["action"] == "hold_for_baseline_600s_full_wave_resource_stop"
    assert decision["recommendation"]["next_candidate_ids"] == []
    by_id = {item["candidate_id"]: item for item in decision["candidate_decisions"]}
    assert by_id["B0_prod_4x4"]["decision"] == "hold"
    assert by_id["B0_prod_4x4"]["reason"] == "resource_stop_triggered"
    assert by_id["experimental_13900ks_htoff_4x5_global_normal"]["decision"] == "hold"
    assert by_id["experimental_13900ks_htoff_4x5_global_normal"]["reason"] == (
        "blocked_by_baseline_600s_full_wave_resource_stop"
    )


def test_next_decision_uses_stage_heartbeat_gate_when_present(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    stage_review_path = tmp_path / "stage_heartbeat_review.json"
    _write_readiness(readiness_path)
    _write_stage_review(stage_review_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            ),
            _run("experimental_13900ks_htoff_2x10_global_normal", score=4.2, peak_private=8.0),
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        stage_heartbeat_review_path=stage_review_path,
    )

    assert decision["recommendation"]["action"] == "hold_for_master_solve_micro_diagnostics"
    assert decision["recommendation"]["global_block_reason"] == (
        "master_solve_hotspot_diagnostic_required"
    )
    assert decision["recommendation"]["next_candidate_ids"] == []
    stage_gate = decision["recommendation"]["stage_heartbeat_review"]
    assert stage_gate["active"] is True
    assert stage_gate["stalled_stage"] == "master_solve"


def test_next_decision_uses_master_log_gate_when_matrix_is_missing(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    master_log_review_path = tmp_path / "master_solve_log_review.json"
    _write_readiness(readiness_path)
    _write_master_log_review(master_log_review_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        master_solve_log_review_path=master_log_review_path,
    )

    assert decision["recommendation"]["action"] == "hold_for_master_presolve_parameter_micro_matrix"
    assert decision["recommendation"]["global_block_reason"] == (
        "master_presolve_parameter_matrix_required"
    )
    assert decision["recommendation"]["next_candidate_ids"] == []
    master_gate = decision["recommendation"]["master_solve_log_review"]
    assert master_gate["active"] is True
    assert master_gate["classification"] == "presolve_symmetry_scale_bottleneck_before_search"


def test_next_decision_uses_parameter_matrix_gate_as_newest_hotspot_step(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    stage_review_path = tmp_path / "stage_heartbeat_review.json"
    master_log_review_path = tmp_path / "master_solve_log_review.json"
    parameter_matrix_path = tmp_path / "master_presolve_parameter_micro_matrix.json"
    _write_readiness(readiness_path)
    _write_stage_review(stage_review_path)
    _write_master_log_review(master_log_review_path)
    _write_parameter_matrix(parameter_matrix_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        stage_heartbeat_review_path=stage_review_path,
        master_solve_log_review_path=master_log_review_path,
        master_presolve_parameter_matrix_path=parameter_matrix_path,
    )

    assert decision["recommendation"]["action"] == "run_single_master_presolve_parameter_micro_probe"
    assert decision["recommendation"]["duration_seconds"] == 300
    assert decision["recommendation"]["global_block_reason"] is None
    assert decision["recommendation"]["next_candidate_ids"] == [
        "local_hotspot_b0_1x1_master_log_sym0_global_normal"
    ]
    matrix_gate = decision["recommendation"]["master_presolve_parameter_matrix"]
    assert matrix_gate["active"] is True
    assert matrix_gate["run_id"] == "local_hotspot_b0_1x1_master_log_sym0_300s_42x32_eval_001"


def test_next_decision_holds_after_parameter_result_summary_exhausts_matrix(
    tmp_path: Path,
) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    parameter_matrix_path = tmp_path / "master_presolve_parameter_micro_matrix.json"
    parameter_result_summary_path = tmp_path / "master_presolve_parameter_result_summary.json"
    _write_readiness(readiness_path)
    _write_parameter_matrix(parameter_matrix_path)
    _write_parameter_result_summary(parameter_result_summary_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        master_presolve_parameter_matrix_path=parameter_matrix_path,
        master_presolve_parameter_result_summary_path=parameter_result_summary_path,
    )

    assert decision["recommendation"]["action"] == "hold_for_master_model_size_reduction_strategy"
    assert decision["recommendation"]["global_block_reason"] == (
        "master_model_size_reduction_strategy_required"
    )
    assert decision["recommendation"]["next_candidate_ids"] == []
    result_gate = decision["recommendation"]["master_presolve_parameter_result_summary"]
    assert result_gate["active"] is True
    assert result_gate["classification"] == "parameter_micro_matrix_exhausted_without_search_start"


def test_next_decision_holds_for_no_solve_inventory_after_size_strategy(
    tmp_path: Path,
) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    parameter_result_summary_path = tmp_path / "master_presolve_parameter_result_summary.json"
    size_strategy_path = tmp_path / "master_model_size_reduction_strategy.json"
    _write_readiness(readiness_path)
    _write_parameter_result_summary(parameter_result_summary_path)
    _write_model_size_strategy(size_strategy_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        master_presolve_parameter_result_summary_path=parameter_result_summary_path,
        master_model_size_reduction_strategy_path=size_strategy_path,
    )

    assert decision["recommendation"]["action"] == "hold_for_no_solve_master_proto_inventory"
    assert decision["recommendation"]["global_block_reason"] == (
        "no_solve_master_proto_inventory_required"
    )
    assert decision["recommendation"]["next_candidate_ids"] == []
    strategy_gate = decision["recommendation"]["master_model_size_reduction_strategy"]
    assert strategy_gate["active"] is True
    assert strategy_gate["classification"] == (
        "master_model_size_reduction_required_before_more_42x32_runtime"
    )


def test_next_decision_holds_for_ghost_overlay_strategy_after_proto_review(
    tmp_path: Path,
) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    parameter_result_summary_path = tmp_path / "master_presolve_parameter_result_summary.json"
    size_strategy_path = tmp_path / "master_model_size_reduction_strategy.json"
    proto_review_path = tmp_path / "master_proto_inventory_review.json"
    _write_readiness(readiness_path)
    _write_parameter_result_summary(parameter_result_summary_path)
    _write_model_size_strategy(size_strategy_path)
    _write_proto_inventory_review(proto_review_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        master_presolve_parameter_result_summary_path=parameter_result_summary_path,
        master_model_size_reduction_strategy_path=size_strategy_path,
        master_proto_inventory_review_path=proto_review_path,
    )

    assert decision["recommendation"]["action"] == (
        "hold_for_ghost_overlay_constraint_reduction_strategy"
    )
    assert decision["recommendation"]["global_block_reason"] == (
        "ghost_overlay_constraint_reduction_strategy_required"
    )
    assert decision["recommendation"]["next_candidate_ids"] == []
    proto_gate = decision["recommendation"]["master_proto_inventory_review"]
    assert proto_gate["active"] is True
    assert proto_gate["classification"] == "ghost_overlay_constraint_build_dominates"


def test_next_decision_runs_no_solve_enforced_probe_after_ghost_strategy(
    tmp_path: Path,
) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    parameter_result_summary_path = tmp_path / "master_presolve_parameter_result_summary.json"
    size_strategy_path = tmp_path / "master_model_size_reduction_strategy.json"
    proto_review_path = tmp_path / "master_proto_inventory_review.json"
    ghost_strategy_path = tmp_path / "ghost_overlay_constraint_reduction_strategy.json"
    _write_readiness(readiness_path)
    _write_parameter_result_summary(parameter_result_summary_path)
    _write_model_size_strategy(size_strategy_path)
    _write_proto_inventory_review(proto_review_path)
    _write_ghost_overlay_strategy(ghost_strategy_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        master_presolve_parameter_result_summary_path=parameter_result_summary_path,
        master_model_size_reduction_strategy_path=size_strategy_path,
        master_proto_inventory_review_path=proto_review_path,
        ghost_overlay_constraint_reduction_strategy_path=ghost_strategy_path,
    )

    assert decision["recommendation"]["action"] == (
        "run_no_solve_enforced_family_bound_formulation_probe"
    )
    assert decision["recommendation"]["global_block_reason"] is None
    gate = decision["recommendation"]["ghost_overlay_constraint_reduction_strategy"]
    assert gate["active"] is True
    assert gate["env"] == {"EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION": "enforced"}
    assert "build_proto_inventory.py" in gate["command_template"]


def test_next_decision_prepares_shape_inventory_after_patch_spec(
    tmp_path: Path,
) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    ghost_strategy_path = tmp_path / "ghost_overlay_constraint_reduction_strategy.json"
    patch_spec_path = tmp_path / "family_bound_ablation_patch_spec.json"
    _write_readiness(readiness_path)
    _write_ghost_overlay_strategy(ghost_strategy_path)
    _write_family_bound_patch_spec(patch_spec_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        ghost_overlay_constraint_reduction_strategy_path=ghost_strategy_path,
        family_bound_ablation_patch_spec_path=patch_spec_path,
    )

    assert decision["recommendation"]["action"] == (
        "prepare_no_source_candidate_shape_inventory_comparison"
    )
    assert decision["recommendation"]["global_block_reason"] is None
    gate = decision["recommendation"]["family_bound_ablation_patch_spec"]
    assert gate["active"] is True
    assert gate["source_mutation_performed"] is False


def test_next_decision_reviews_shape_scaling_after_inventory_comparison(
    tmp_path: Path,
) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    patch_spec_path = tmp_path / "family_bound_ablation_patch_spec.json"
    shape_comparison_path = tmp_path / "candidate_shape_inventory_comparison.json"
    _write_readiness(readiness_path)
    _write_family_bound_patch_spec(patch_spec_path)
    _write_candidate_shape_inventory_comparison(shape_comparison_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        family_bound_ablation_patch_spec_path=patch_spec_path,
        candidate_shape_inventory_comparison_path=shape_comparison_path,
    )

    assert decision["recommendation"]["action"] == "review_no_source_shape_scaling_before_runtime"
    assert decision["recommendation"]["global_block_reason"] is None
    gate = decision["recommendation"]["candidate_shape_inventory_comparison"]
    assert gate["active"] is True
    assert gate["classification"] == "candidate_shape_inventory_comparison_ready"
    assert gate["non_baseline_completed_shape_count"] == 2


def test_next_decision_prepares_via_pole_instrumentation_spec_after_shape_review(
    tmp_path: Path,
) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    shape_comparison_path = tmp_path / "candidate_shape_inventory_comparison.json"
    shape_review_path = tmp_path / "candidate_shape_scaling_review.json"
    _write_readiness(readiness_path)
    _write_candidate_shape_inventory_comparison(shape_comparison_path)
    _write_candidate_shape_scaling_review(shape_review_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        candidate_shape_inventory_comparison_path=shape_comparison_path,
        candidate_shape_scaling_review_path=shape_review_path,
    )

    assert decision["recommendation"]["action"] == (
        "prepare_default_off_via_pole_shape_instrumentation_patch_spec"
    )
    assert decision["recommendation"]["global_block_reason"] is None
    gate = decision["recommendation"]["candidate_shape_scaling_review"]
    assert gate["active"] is True
    assert gate["source_mutation_performed"] is False


def test_next_decision_holds_after_via_pole_instrumentation_spec(
    tmp_path: Path,
) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    shape_review_path = tmp_path / "candidate_shape_scaling_review.json"
    via_pole_spec_path = tmp_path / "via_pole_shape_instrumentation_patch_spec.json"
    _write_readiness(readiness_path)
    _write_candidate_shape_scaling_review(shape_review_path)
    _write_via_pole_shape_instrumentation_patch_spec(via_pole_spec_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            )
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        candidate_shape_scaling_review_path=shape_review_path,
        via_pole_shape_instrumentation_patch_spec_path=via_pole_spec_path,
    )

    assert decision["recommendation"]["action"] == (
        "hold_for_default_off_via_pole_shape_instrumentation_source_authorization"
    )
    assert decision["recommendation"]["global_block_reason"] == (
        "source_mutation_authorization_required"
    )
    gate = decision["recommendation"]["via_pole_shape_instrumentation_patch_spec"]
    assert gate["active"] is True
    assert gate["implementation_allowed_now"] is False


def test_next_decision_keeps_full_wave_block_after_reduced_wave_baseline_succeeds(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    _write_readiness(readiness_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            ),
            _run(
                "B0_prod_4x4",
                score=1.0,
                peak_private=14.0,
                requested_duration=600,
                wave_max=1,
                run_suffix="wave1",
            ),
            _run("experimental_13900ks_htoff_2x10_global_normal", score=4.2, peak_private=8.0),
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
    )

    assert decision["recommendation"]["action"] == "hold_for_baseline_600s_full_wave_resource_stop"
    assert decision["recommendation"]["next_candidate_ids"] == []


def test_next_decision_allows_reduced_frontier_no_hotspots_path_under_full_wave_hold(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    resource_strategy_path = tmp_path / "resource_strategy.json"
    _write_readiness(readiness_path)
    _write_resource_strategy(resource_strategy_path)
    _write_scoreboard(
        scoreboard_path,
        [
            _run(
                "B0_prod_4x4",
                status="stopped_resource_limit",
                score=1.0,
                peak_private=45.0,
                resource_stop=True,
                requested_duration=600,
                wave_max=4,
            ),
            _run(
                "B0_prod_4x4",
                score=1.0,
                peak_private=14.3,
                requested_duration=600,
                wave_max=2,
                run_suffix="reduced_frontier_no_hotspots",
                selection_kind="deterministic_frontier_bounded_wave_excluding_keys_v0",
                excluded_candidate_keys=["42x32", "67x20"],
            ),
            _run(
                "experimental_13900ks_htoff_2x10_global_normal",
                score=1.02,
                peak_private=7.7,
                requested_duration=600,
                wave_max=2,
                run_suffix="reduced_frontier_no_hotspots",
                selection_kind="deterministic_frontier_bounded_wave_excluding_keys_v0",
                excluded_candidate_keys=["42x32", "67x20"],
            ),
            _run(
                "experimental_13900ks_htoff_4x5_global_normal",
                score=1.01,
                peak_private=14.0,
                requested_duration=600,
                wave_max=1,
                run_suffix="wave1",
            ),
            _run(
                "experimental_13900ks_htoff_3x8_global_normal",
                status="timeout",
                score=0.2,
                peak_private=41.0,
                timed_out=True,
            ),
            _run(
                "W1_prod_4x4_stage_6_4_2_4",
                status="stopped_resource_limit",
                score=0.2,
                peak_private=45.0,
                resource_stop=True,
            ),
        ],
    )

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
        resource_strategy_path=resource_strategy_path,
    )

    assert decision["recommendation"]["action"] == "hold_for_baseline_600s_full_wave_resource_stop"
    reduced = decision["recommendation"]["reduced_frontier_no_hotspots"]
    assert reduced["action"] == "continue_reduced_frontier_no_hotspots_only"
    assert reduced["avoid_candidate_keys"] == ["42x32", "67x20"]
    assert reduced["completed_candidate_ids"] == [
        "B0_prod_4x4",
        "experimental_13900ks_htoff_2x10_global_normal",
    ]
    assert reduced["next_candidate_ids"] == ["experimental_13900ks_htoff_4x5_global_normal"]
    assert reduced["blocked_reasons"]["experimental_13900ks_htoff_3x8_global_normal"] == (
        "no_safe_low_memory_prior_signal"
    )


def test_next_decision_write_mode(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    output_dir = tmp_path / "out"
    _write_readiness(readiness_path)
    _write_scoreboard(scoreboard_path, [_run("B0_prod_4x4", score=1.0, peak_private=14.0)])

    decision = build_checkpoint_free_next_decision(
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
    )
    paths = write_checkpoint_free_next_decision(decision, output_dir)

    assert json.loads(paths["json"].read_text(encoding="utf-8"))["schema"] == (
        "phase3b-checkpoint-free-next-decision/v0"
    )
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_readiness(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "selected_candidate_ids": [
                    "B0_prod_4x4",
                    "experimental_13900ks_htoff_3x8_global_normal",
                    "experimental_13900ks_htoff_4x5_global_normal",
                    "experimental_13900ks_htoff_2x10_global_normal",
                    "W1_prod_4x4_stage_6_4_2_4",
                    "W3_prod_4x4_stage_6_6_2_6",
                    "W6_prod_3x_stage_8_6_2_6",
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_scoreboard(path: Path, runs: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "runs": runs,
                "safety": {
                    "sensitive_path_mutation_detected": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_resource_strategy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "recommendation": {
                    "avoid_candidate_keys_for_wave_expansion": ["42x32", "67x20"],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_stage_review(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "run": {"run_id": "stage_probe"},
                "interpretation": {
                    "stalled_stage": "master_solve",
                    "stalled_reason": "last_stage_start_without_complete_before_timeout",
                },
                "recommendation": {
                    "action": "prepare_master_solve_micro_diagnostics",
                    "next_engineering_step": "add master-solve focused diagnostics",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_master_log_review(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "run": {"run_id": "local_hotspot_b0_1x1_master_log_300s_42x32_eval_001"},
                "interpretation": {
                    "classification": "presolve_symmetry_scale_bottleneck_before_search",
                },
                "recommendation": {
                    "action": "prepare_master_presolve_parameter_micro_matrix",
                    "next_engineering_step": "build a manifest-only parameter matrix",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_parameter_matrix(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "recommendation": {
                    "action": "ready_for_single_sym0_micro_probe",
                    "first_candidate_id": "local_hotspot_b0_1x1_master_log_sym0_global_normal",
                    "first_run_id": "local_hotspot_b0_1x1_master_log_sym0_300s_42x32_eval_001",
                    "next_engineering_step": "run at most one 300s checkpoint-free variant",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_parameter_result_summary(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "interpretation": {
                    "classification": "parameter_micro_matrix_exhausted_without_search_start",
                    "sensitive_paths_clean": True,
                    "checkpoints_clean": True,
                },
                "recommendation": {
                    "action": "prepare_master_model_size_reduction_strategy",
                    "next_engineering_step": "prepare model/candidate structure reduction",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_model_size_strategy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "interpretation": {
                    "classification": "master_model_size_reduction_required_before_more_42x32_runtime",
                },
                "recommendation": {
                    "action": "prepare_no_solve_master_proto_inventory",
                    "next_engineering_step": "build no-solve proto inventory",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_proto_inventory_review(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "interpretation": {
                    "classification": "ghost_overlay_constraint_build_dominates",
                },
                "recommendation": {
                    "action": "prepare_ghost_overlay_constraint_reduction_strategy",
                    "next_engineering_step": "inspect ghost overlay constraint generation",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_ghost_overlay_strategy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "interpretation": {
                    "classification": "family_bound_overlay_dominates",
                },
                "recommendation": {
                    "action": "run_no_solve_enforced_family_bound_formulation_probe",
                    "next_engineering_step": "run one no-solve enforced variant",
                },
                "candidate_actions": [
                    {
                        "id": "no_solve_enforced_family_bound_formulation_probe",
                        "allowed": True,
                        "env": {
                            "EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION": "enforced"
                        },
                        "command_template": (
                            "python scripts/phase3b/checkpoint_free/master/build_proto_inventory.py "
                            "--execute-no-solve --run-id local_hotspot_42x32_master_proto_inventory_enforced_001"
                        ),
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_family_bound_patch_spec(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "patch_spec_ready_source_mutation_still_blocked",
                },
                "recommendation": {
                    "action": "prepare_no_source_candidate_shape_inventory_comparison",
                    "next_engineering_step": "continue with no-source shape inventory",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_candidate_shape_inventory_comparison(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "execute_no_solve": True,
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
                "source_mutation_performed": False,
                "proof_source": False,
                "interpretation": {
                    "classification": "candidate_shape_inventory_comparison_ready",
                    "completed_shape_count": 3,
                    "non_baseline_completed_shape_count": 2,
                },
                "recommendation": {
                    "action": "review_no_source_shape_scaling_before_runtime",
                    "next_engineering_step": "review shape scaling before any runtime change",
                },
                "sensitive_path_comparison": {
                    "changed": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_candidate_shape_scaling_review(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
                "source_mutation_performed": False,
                "proof_source": False,
                "interpretation": {
                    "classification": "shape_specific_via_pole_anchor_explosion",
                },
                "recommendation": {
                    "action": "prepare_default_off_via_pole_shape_instrumentation_patch_spec",
                    "next_engineering_step": "prepare spec-only instrumentation patch",
                },
                "sensitive_path_comparison": {
                    "changed": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_via_pole_shape_instrumentation_patch_spec(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "patch_spec_ready_source_mutation_still_blocked",
                    "implementation_allowed_now": False,
                    "source_mutation_authorized_by_this_artifact": False,
                },
                "recommendation": {
                    "action": "hold_for_default_off_via_pole_shape_instrumentation_source_authorization",
                    "next_engineering_step": "wait for explicit source authorization",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _run(
    candidate_id: str,
    *,
    status: str = "completed",
    score: float,
    peak_private: float,
    timed_out: bool = False,
    resource_stop: bool = False,
    requested_duration: int = 300,
    wave_max: int = 1,
    run_suffix: str = "",
    selection_kind: str = "deterministic_frontier_bounded_wave_v0",
    excluded_candidate_keys: list[str] | None = None,
) -> dict[str, object]:
    suffix = f"_{run_suffix}" if run_suffix else ""
    return {
        "candidate_id": candidate_id,
        "run_id": f"{candidate_id}_{requested_duration}s{suffix}_single_eval_001",
        "status": status,
        "requested_duration_seconds": requested_duration,
        "wave_max_candidates": wave_max,
        "wave_selected_count": wave_max,
        "wave_selection_kind": selection_kind,
        "wave_excluded_candidate_keys": list(excluded_candidate_keys or []),
        "wave_candidate_keys": [f"candidate_{idx}" for idx in range(wave_max)],
        "result_count": 1 if status == "completed" else 0,
        "baseline_normalized_throughput": score,
        "peak_private_gib": peak_private,
        "peak_rss_gib": peak_private * 0.75,
        "timed_out": timed_out,
        "resource_stop_triggered": resource_stop,
        "sensitive_path_changed": False,
    }
