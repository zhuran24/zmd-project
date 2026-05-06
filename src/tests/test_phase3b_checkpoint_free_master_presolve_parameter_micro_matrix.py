from __future__ import annotations

import json
from pathlib import Path

from scripts.build_phase3b_checkpoint_free_master_presolve_parameter_micro_matrix import (
    build_master_presolve_parameter_micro_matrix,
    write_master_presolve_parameter_micro_matrix,
)


def test_master_presolve_parameter_matrix_builds_expected_variants(tmp_path: Path) -> None:
    review_path = tmp_path / "master_solve_log_review.json"
    readiness_path = tmp_path / "master_solve_micro_augmented_readiness_packet.json"
    _write_log_review(review_path)
    _write_readiness(readiness_path)
    _write_source_markers(tmp_path)

    matrix = build_master_presolve_parameter_micro_matrix(
        project_root=tmp_path,
        log_review_path=review_path,
        master_readiness_path=readiness_path,
    )

    assert matrix["schema"] == "phase3b-checkpoint-free-master-presolve-parameter-micro-matrix/v0"
    assert matrix["recommendation"]["action"] == "ready_for_single_sym0_micro_probe"
    assert matrix["recommendation"]["first_candidate_id"] == (
        "local_hotspot_b0_1x1_master_log_sym0_global_normal"
    )
    variants = {variant["variant_id"]: variant for variant in matrix["variants"]}
    assert set(variants) == {"sym0", "probe0", "sym0_probe0"}
    assert variants["sym0"]["env"]["EXACT_MASTER_SYMMETRY_LEVEL"] == "0"
    assert "EXACT_MASTER_CP_MODEL_PROBING_LEVEL" not in variants["sym0"]["env"]
    assert variants["probe0"]["env"]["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] == "0"
    assert "EXACT_MASTER_SYMMETRY_LEVEL" not in variants["probe0"]["env"]
    assert variants["sym0_probe0"]["env"]["EXACT_MASTER_SYMMETRY_LEVEL"] == "0"
    assert variants["sym0_probe0"]["env"]["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] == "0"
    for variant in variants.values():
        assert variant["process_count"] == 1
        assert variant["duration_seconds"] == 300
        assert variant["candidate_key"] == "42x32"
        assert variant["proof_source"] is False
        assert variant["checkpoint_written"] is False
        assert "planned_future_commands" not in variant
    commands = matrix["command_matrix"]["commands"]
    assert len(commands) == 3
    assert commands[0]["execute_command_after_review"]
    assert "--duration-seconds" in commands[0]["execute_command_after_review"]
    assert "300" in commands[0]["execute_command_after_review"]
    assert "168h" not in " ".join(commands[0]["execute_command_after_review"])
    assert "--resume-campaign" not in commands[0]["execute_command_after_review"]
    assert matrix["safety"]["builder_executes_solver"] is False
    assert matrix["safety"]["checkpoint_written"] is False
    assert matrix["safety"]["proof_source"] is False


def test_master_presolve_parameter_matrix_holds_without_review_gate(tmp_path: Path) -> None:
    review_path = tmp_path / "master_solve_log_review.json"
    readiness_path = tmp_path / "master_solve_micro_augmented_readiness_packet.json"
    _write_log_review(review_path, action="hold_manual_master_log_review")
    _write_readiness(readiness_path)
    _write_source_markers(tmp_path)

    matrix = build_master_presolve_parameter_micro_matrix(
        project_root=tmp_path,
        log_review_path=review_path,
        master_readiness_path=readiness_path,
    )

    assert matrix["recommendation"]["action"] == "hold_manual_review"
    assert matrix["recommendation"]["first_candidate_id"] is None
    assert all(
        not command["execute_command_after_review"]
        for command in matrix["command_matrix"]["commands"]
    )


def test_master_presolve_parameter_matrix_write_mode(tmp_path: Path) -> None:
    review_path = tmp_path / "master_solve_log_review.json"
    readiness_path = tmp_path / "master_solve_micro_augmented_readiness_packet.json"
    output_dir = tmp_path / "out"
    _write_log_review(review_path)
    _write_readiness(readiness_path)
    _write_source_markers(tmp_path)

    paths = write_master_presolve_parameter_micro_matrix(
        build_master_presolve_parameter_micro_matrix(
            project_root=tmp_path,
            log_review_path=review_path,
            master_readiness_path=readiness_path,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "master_presolve_parameter_micro_matrix.json"
    assert paths["md"] == output_dir / "master_presolve_parameter_micro_matrix.md"
    assert paths["augmented_readiness"] == output_dir / "master_presolve_parameter_augmented_readiness_packet.json"
    assert paths["command_matrix"] == output_dir / "master_presolve_parameter_command_matrix.json"
    readiness = json.loads(paths["augmented_readiness"].read_text(encoding="utf-8"))
    assert "local_hotspot_b0_1x1_master_log_sym0_global_normal" in readiness[
        "master_presolve_parameter_variant_candidate_ids"
    ]
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_log_review(
    path: Path,
    *,
    action: str = "prepare_master_presolve_parameter_micro_matrix",
) -> None:
    path.write_text(
        json.dumps(
            {
                "run": {"run_id": "local_hotspot_b0_1x1_master_log_300s_42x32_eval_001"},
                "interpretation": {
                    "classification": "presolve_symmetry_scale_bottleneck_before_search",
                },
                "extracted_metrics": {
                    "max_symmetry_nodes": 7_218_285,
                    "max_symmetry_arcs": 16_969_922,
                    "max_sat_presolve_vars": 1_151_270,
                },
                "recommendation": {"action": action},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_readiness(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "packet_kind": "checkpoint_free_master_solve_micro_diagnostics_readiness_local_only",
                "augmented_candidate_ids": ["local_hotspot_b0_1x1_master_log_global_normal"],
                "candidates": [
                    {
                        "candidate_id": "local_hotspot_b0_1x1_master_log_global_normal",
                        "source_kind": "local_master_solve_micro_diagnostic",
                        "source_profile_id": "local_hotspot_b0_1x1_master_log_global_normal",
                        "process_count": 1,
                        "env": {
                            "EXACT_CP_SAT_WORKERS": "1",
                            "EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES": "80",
                            "EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_MAX_CHARS": "1000",
                        },
                        "risk": {"level": "low"},
                        "frontier_probe_mode": "auto",
                        "proof_source": False,
                        "checkpoint_written": False,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_source_markers(root: Path) -> None:
    path = root / "src" / "models" / "master_model.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "EXACT_MASTER_SYMMETRY_LEVEL_ENV\n"
        "EXACT_MASTER_CP_MODEL_PROBING_LEVEL_ENV\n"
        "EXACT_MASTER_CP_MODEL_PRESOLVE_ENV\n",
        encoding="utf-8",
    )
