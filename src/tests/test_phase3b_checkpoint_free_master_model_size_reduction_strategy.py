from __future__ import annotations

import json
from pathlib import Path

from scripts.build_phase3b_checkpoint_free_master_model_size_reduction_strategy import (
    build_master_model_size_reduction_strategy,
    write_master_model_size_reduction_strategy,
)


def test_master_model_size_reduction_strategy_builds_no_solve_next_artifacts(
    tmp_path: Path,
) -> None:
    parameter_summary = tmp_path / "parameter_summary.json"
    run_plan = tmp_path / "run_plan.json"
    heartbeats = tmp_path / "stage_heartbeats.jsonl"
    _write_parameter_summary(parameter_summary)
    _write_run_plan(run_plan)
    _write_stage_heartbeats(heartbeats)

    strategy = build_master_model_size_reduction_strategy(
        parameter_summary_path=parameter_summary,
        baseline_run_plan_path=run_plan,
        baseline_stage_heartbeats_path=heartbeats,
    )

    assert strategy["schema"] == "phase3b-checkpoint-free-master-model-size-reduction-strategy/v0"
    assert strategy["target"]["candidate_key"] == "42x32"
    assert strategy["target"]["ghost_rect"] == {"w": 42, "h": 32, "area": 1344}
    assert strategy["interpretation"]["classification"] == (
        "master_model_size_reduction_required_before_more_42x32_runtime"
    )
    assert strategy["recommendation"]["action"] == "prepare_no_solve_master_proto_inventory"
    assert strategy["evidence"]["log_scale_metrics"]["max_clique_merged_constraints"] == 1_625_483
    assert strategy["evidence"]["log_scale_metrics"]["transform_exactly_one_num_amos"] == 1_617_179
    assert strategy["evidence"]["log_scale_metrics"]["hint_line_seen"] is True
    next_artifact = strategy["recommended_next_artifacts"][0]
    assert next_artifact["artifact_id"] == "24_master_proto_inventory"
    assert "CpSolver.Solve" in next_artifact["must_not_call"]
    assert strategy["safety"]["builder_executes_solver"] is False
    assert strategy["safety"]["checkpoint_written"] is False
    assert strategy["safety"]["proof_source"] is False


def test_master_model_size_reduction_strategy_holds_without_clean_parameter_gate(
    tmp_path: Path,
) -> None:
    parameter_summary = tmp_path / "parameter_summary.json"
    run_plan = tmp_path / "run_plan.json"
    heartbeats = tmp_path / "stage_heartbeats.jsonl"
    _write_parameter_summary(parameter_summary, clean=False)
    _write_run_plan(run_plan)
    _write_stage_heartbeats(heartbeats)

    strategy = build_master_model_size_reduction_strategy(
        parameter_summary_path=parameter_summary,
        baseline_run_plan_path=run_plan,
        baseline_stage_heartbeats_path=heartbeats,
    )

    assert strategy["interpretation"]["classification"] == "manual_review_required"
    assert strategy["recommendation"]["action"] == "hold_manual_review"
    assert strategy["recommended_next_artifacts"] == []


def test_master_model_size_reduction_strategy_write_mode(tmp_path: Path) -> None:
    parameter_summary = tmp_path / "parameter_summary.json"
    run_plan = tmp_path / "run_plan.json"
    heartbeats = tmp_path / "stage_heartbeats.jsonl"
    output_dir = tmp_path / "out"
    _write_parameter_summary(parameter_summary)
    _write_run_plan(run_plan)
    _write_stage_heartbeats(heartbeats)

    paths = write_master_model_size_reduction_strategy(
        build_master_model_size_reduction_strategy(
            parameter_summary_path=parameter_summary,
            baseline_run_plan_path=run_plan,
            baseline_stage_heartbeats_path=heartbeats,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "master_model_size_reduction_strategy.json"
    assert paths["md"] == output_dir / "master_model_size_reduction_strategy.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["recommendation"]["action"] == "prepare_no_solve_master_proto_inventory"
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_parameter_summary(path: Path, *, clean: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "baseline": {
                    "max_sat_presolve_vars": 1_151_270,
                    "max_symmetry_nodes": 7_218_285,
                },
                "interpretation": {
                    "classification": "parameter_micro_matrix_exhausted_without_search_start",
                    "sensitive_paths_clean": clean,
                    "checkpoints_clean": clean,
                    "symmetry_disabled_removed_symmetry_graph": True,
                    "any_search_started": False,
                },
                "recommendation": {
                    "action": "prepare_master_model_size_reduction_strategy",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_run_plan(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "run_id": "local_hotspot_b0_1x1_master_log_300s_42x32_eval_001",
                "duration_seconds": 300,
                "wave": {
                    "selection_kind": "explicit_frontier_candidate_key_v0",
                    "entries": [
                        {
                            "candidate": [1344, 42, 32],
                            "candidate_key": "42x32",
                        }
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_stage_heartbeats(path: Path) -> None:
    rows = [
        {
            "payload": {
                "stage": "master_solve_log",
                "event": "line",
                "text": "The solution hint is incomplete: 798 out of 58036 non fixed variables hinted.",
            }
        },
        {
            "payload": {
                "stage": "master_solve_log",
                "event": "line",
                "text": "1.25e+00s  3.27e+00d *[MaxClique] Merged 1'625'483 constraints with 3'250'966 literals into 1'614'513 constraints with 3'236'840 literals",
            }
        },
        {
            "payload": {
                "stage": "master_solve_log",
                "event": "line",
                "text": "1.57e+00s  1.00e+00d *[operations_research::sat::CpModelPresolver::TransformClausesToExactlyOne] #num_amos=1'617'179 #num_clauses=80'374 #num_checked=3'291",
            }
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
