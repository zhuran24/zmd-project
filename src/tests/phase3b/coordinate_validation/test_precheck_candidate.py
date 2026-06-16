from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.precheck_candidate import (
    build_phase3b_coordinate_validation_precheck_candidate_summary,
    render_phase3b_coordinate_validation_precheck_candidate_markdown,
    render_phase3b_coordinate_validation_precheck_candidate_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _start_compatibility_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_start_compatibility_diagnostics_v1"},
        "candidate": {"key": "67x13"},
        "status": {"outcome": "start_incompatible"},
        "diagnostics": {
            "warm_start": {
                "ghost_aware_coordinate_validation_rejected_count": 8,
                "ghost_aware_coordinate_validation_limit_reached": True,
                "ghost_aware_coordinate_validation_rejection_samples": [
                    {
                        "anchor_idx": 118,
                        "strategy": "ghost_aware_mandatory_rebuild",
                        "status": "INFEASIBLE",
                        "reason": "infeasible",
                        "forced_slot_field_count": 798,
                    }
                ],
            },
            "start_failure_summary": {
                "failed_anchor_count": 8,
                "failure_reason_counts": {
                    "coordinate_validation_infeasible": 8,
                    "coordinate_validation_attempt_limit_reached": 1,
                },
            },
        },
    }


def _solver_matrix_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_solver_matrix_v1"},
        "candidate": {"key": "67x13"},
        "status": {"outcome": "matrix_all_infeasible"},
        "matrix": {
            "status_counts": {"INFEASIBLE": 3},
            "entries": [
                {
                    "anchor_idx": 118,
                    "search_branching": "fixed",
                    "status": "INFEASIBLE",
                    "wall_time": 15.0,
                    "branches": 0,
                    "conflicts": 0,
                },
                {
                    "anchor_idx": 118,
                    "search_branching": "automatic",
                    "status": "INFEASIBLE",
                    "wall_time": 15.1,
                    "branches": 0,
                    "conflicts": 0,
                },
                {
                    "anchor_idx": 118,
                    "search_branching": "portfolio",
                    "status": "INFEASIBLE",
                    "wall_time": 15.2,
                    "branches": 0,
                    "conflicts": 0,
                },
            ],
        },
    }


def _b5a_summary_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_b5_anchor_sprint_summary_v1"},
        "status": {"anchor_found": False, "outcome": "triage_required"},
        "triage": {
            "top_blockers": [
                {
                    "candidate_key": "67x13",
                    "blocker_subtype": "master_start_incompatible_unknown",
                    "proof_summary": {
                        "master_last_solve": {
                            "branches": 12560,
                            "conflicts": 216,
                            "deterministic_time": 37.6539968117261,
                        },
                        "master_start_failure_attribution": {
                            "failure_reason_counts": {
                                "coordinate_validation_infeasible": 8,
                                "coordinate_validation_attempt_limit_reached": 1,
                            }
                        },
                    },
                }
            ]
        },
    }


def _joined_xy_profile_probe_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_coordinate_validation_profile_probe_v1"},
        "status": {
            "completed": True,
            "evaluated": True,
            "outcome": "coordinate_validation_infeasible",
            "status_counts": {"UNKNOWN": 1, "INFEASIBLE": 3},
        },
        "probe": {
            "best_terminal_entry": {
                "profile_id": "validation_fixed_presolve_on_30s",
                "status": "INFEASIBLE",
            }
        },
    }


def _joined_xy_delta_synthesis_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_joined_xy_coordinate_validation_delta_synthesis_v1"
        },
        "status": {
            "completed": True,
            "outcome": "joined_xy_coordinate_validation_shrunk_to_grinder_x_single_equality",
        },
        "evidence": {
            "anchor119_pair_x_core_synthesis": {
                "outcome": "anchor119_fixed_conflict_shrunk_to_protocol_planter_buckwheat_3_x_labels",
                "remaining_label_count": 3,
            },
            "anchor119_pair_x_no_ghost_space_synthesis": {
                "outcome": "three_x_labels_eliminate_entire_67x13_ghost_domain_in_full_model"
            },
        },
    }


def _anchor119_pair_x_core_synthesis_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_anchor119_pair_x_core_synthesis_v1"},
        "status": {
            "completed": True,
            "outcome": "anchor119_fixed_conflict_shrunk_to_protocol_planter_buckwheat_3_x_labels",
        },
        "evidence": {
            "minimality_10s": {
                "all3_infeasible": True,
                "proper_subsets_terminal_infeasible": 0,
            },
            "remaining_labels": [{}, {}, {}],
        },
    }


def _anchor119_pair_x_no_ghost_space_synthesis_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_anchor119_pair_x_no_ghost_space_synthesis_v1"
        },
        "status": {
            "completed": True,
            "outcome": "three_x_labels_eliminate_entire_67x13_ghost_domain_in_full_model",
            "latest_followup_outcome": "residual_optional_signature_layer_primary_suspect",
        },
        "evidence": {
            "anchor_sweep_status_counts": {"INFEASIBLE": 232},
            "standalone_pair_status": "OPTIMAL",
            "minimality_10s": {
                "all3_infeasible": True,
                "proper_subsets_terminal_infeasible": 0,
            },
        },
    }


def _order_implied_capacity_explanation_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_order_implied_capacity_explanation_v1"
        },
        "geometry": {
            "free_ghost_infeasible_threshold_slots": 15,
            "anchor119_fixed_infeasible_threshold_slots": 14,
        },
    }


def _anchor119_row_domain_runtime_patch_status_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_v1"
        },
        "status": {
            "patch_status_ready": True,
            "runtime_patch_authored_in_code": True,
            "authored_but_not_enableable": True,
            "runtime_enablement_allowed": False,
        },
    }


def _anchor119_row_domain_review_state_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_review_state_v1",
            "spec_only": True,
            "review_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "review_state_ready": True,
            "repo_side_review_state_updated": True,
            "reviewed_runtime_patch_exists": True,
            "runtime_enablement_allowed": False,
            "production_acceptance_refresh_completed": False,
        },
    }


def test_coordinate_validation_precheck_candidate_gate_passes_design_but_blocks_runtime(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    start_path = project_root / "start.json"
    matrix_path = project_root / "matrix.json"
    _write_json(start_path, _start_compatibility_payload())
    _write_json(matrix_path, _solver_matrix_payload())

    summary = build_phase3b_coordinate_validation_precheck_candidate_summary(
        project_root,
        start_compatibility_path=start_path,
        forced_anchor_solver_matrix_path=matrix_path,
        min_rejected_anchor_count=3,
        min_matrix_infeasible_count=3,
    )

    assert summary["metadata"]["source"] == "phase3b_coordinate_validation_precheck_candidate_v2"
    assert summary["candidate"]["key"] == "67x13"
    assert summary["gate"]["design_gate_passed"] is True
    assert summary["gate"]["runtime_promotion_ready"] is False
    assert summary["coordinate_validation"]["rejected_count"] == 8
    assert summary["forced_anchor_solver_matrix"]["matrix_all_infeasible"] is True
    assert [
        check["check_id"]
        for check in summary["checks"]
        if check["status"] == "fail"
    ] == ["runtime_promotion_guard"]

    markdown = render_phase3b_coordinate_validation_precheck_candidate_markdown(summary)
    text = render_phase3b_coordinate_validation_precheck_candidate_text(summary)
    assert "Coordinate-Validation Precheck Candidate Gate" in markdown
    assert "anchor" in markdown.lower()
    assert "design_gate_passed=True" in text
    assert "solver_matrix_entry=anchor=118" in text


def test_coordinate_validation_precheck_candidate_surfaces_joined_xy_current_blocker(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    start_path = project_root / "start.json"
    matrix_path = project_root / "matrix.json"
    b5a_path = project_root / "b5a.json"
    probe_path = project_root / "probe.json"
    delta_path = project_root / "delta.json"
    _write_json(start_path, _start_compatibility_payload())
    _write_json(matrix_path, _solver_matrix_payload())
    _write_json(b5a_path, _b5a_summary_payload())
    _write_json(probe_path, _joined_xy_profile_probe_payload())
    _write_json(delta_path, _joined_xy_delta_synthesis_payload())

    summary = build_phase3b_coordinate_validation_precheck_candidate_summary(
        project_root,
        start_compatibility_path=start_path,
        forced_anchor_solver_matrix_path=matrix_path,
        b5a_summary_path=b5a_path,
        joined_xy_profile_probe_path=probe_path,
        joined_xy_delta_synthesis_path=delta_path,
        min_rejected_anchor_count=3,
        min_matrix_infeasible_count=3,
    )

    blocker = summary["joined_xy_current_blocker"]
    assert blocker["active"] is True
    assert blocker["blocker_subtype"] == "master_start_incompatible_unknown"
    assert blocker["profile_probe_terminal_infeasible"] is True
    assert blocker["delta_shrink_present"] is True
    assert blocker["shrunk_core_label_count"] == 3
    assert "joined-XY coordinate-validation / ghost-aware start gate" in summary["gate"][
        "recommendation"
    ]
    failed = {
        check["check_id"] for check in summary["checks"] if check["status"] == "fail"
    }
    assert failed == {"runtime_promotion_guard"}


def test_coordinate_validation_precheck_candidate_surfaces_joined_xy_proof_candidate(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    start_path = project_root / "start.json"
    matrix_path = project_root / "matrix.json"
    b5a_path = project_root / "b5a.json"
    probe_path = project_root / "probe.json"
    delta_path = project_root / "delta.json"
    core_path = project_root / "pair_core.json"
    no_ghost_path = project_root / "no_ghost.json"
    order_capacity_path = project_root / "order_capacity.json"
    _write_json(start_path, _start_compatibility_payload())
    _write_json(matrix_path, _solver_matrix_payload())
    _write_json(b5a_path, _b5a_summary_payload())
    _write_json(probe_path, _joined_xy_profile_probe_payload())
    _write_json(delta_path, _joined_xy_delta_synthesis_payload())
    _write_json(core_path, _anchor119_pair_x_core_synthesis_payload())
    _write_json(no_ghost_path, _anchor119_pair_x_no_ghost_space_synthesis_payload())
    _write_json(order_capacity_path, _order_implied_capacity_explanation_payload())

    summary = build_phase3b_coordinate_validation_precheck_candidate_summary(
        project_root,
        start_compatibility_path=start_path,
        forced_anchor_solver_matrix_path=matrix_path,
        b5a_summary_path=b5a_path,
        joined_xy_profile_probe_path=probe_path,
        joined_xy_delta_synthesis_path=delta_path,
        anchor119_pair_x_core_synthesis_path=core_path,
        anchor119_pair_x_no_ghost_space_synthesis_path=no_ghost_path,
        order_implied_capacity_explanation_path=order_capacity_path,
        min_rejected_anchor_count=3,
        min_matrix_infeasible_count=3,
    )

    proof_candidate = summary["joined_xy_proof_preserving_candidate"]
    assert proof_candidate["design_ready"] is True
    assert proof_candidate["proof_preserving_precheck_ready"] is False
    assert proof_candidate["core_label_count"] == 3
    assert proof_candidate["anchor_sweep_all_infeasible"] is True
    assert proof_candidate["standalone_pair_optimal"] is True
    assert proof_candidate["order_capacity_present"] is True
    assert "proof-preserving extraction" in proof_candidate["recommendation"]


def test_coordinate_validation_precheck_candidate_surfaces_review_gate_after_runtime_patch(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    start_path = project_root / "start.json"
    matrix_path = project_root / "matrix.json"
    b5a_path = project_root / "b5a.json"
    probe_path = project_root / "probe.json"
    delta_path = project_root / "delta.json"
    core_path = project_root / "pair_core.json"
    no_ghost_path = project_root / "no_ghost.json"
    order_capacity_path = project_root / "order_capacity.json"
    runtime_patch_status_path = project_root / "runtime_patch_status.json"
    _write_json(start_path, _start_compatibility_payload())
    _write_json(matrix_path, _solver_matrix_payload())
    _write_json(b5a_path, _b5a_summary_payload())
    _write_json(probe_path, _joined_xy_profile_probe_payload())
    _write_json(delta_path, _joined_xy_delta_synthesis_payload())
    _write_json(core_path, _anchor119_pair_x_core_synthesis_payload())
    _write_json(no_ghost_path, _anchor119_pair_x_no_ghost_space_synthesis_payload())
    _write_json(order_capacity_path, _order_implied_capacity_explanation_payload())
    _write_json(
        runtime_patch_status_path,
        _anchor119_row_domain_runtime_patch_status_payload(),
    )

    summary = build_phase3b_coordinate_validation_precheck_candidate_summary(
        project_root,
        start_compatibility_path=start_path,
        forced_anchor_solver_matrix_path=matrix_path,
        b5a_summary_path=b5a_path,
        joined_xy_profile_probe_path=probe_path,
        joined_xy_delta_synthesis_path=delta_path,
        anchor119_pair_x_core_synthesis_path=core_path,
        anchor119_pair_x_no_ghost_space_synthesis_path=no_ghost_path,
        order_implied_capacity_explanation_path=order_capacity_path,
        anchor119_row_domain_runtime_patch_status_path=runtime_patch_status_path,
        min_rejected_anchor_count=3,
        min_matrix_infeasible_count=3,
    )

    proof_candidate = summary["joined_xy_proof_preserving_candidate"]
    assert proof_candidate["design_ready"] is True
    assert proof_candidate["proof_preserving_precheck_ready"] is True
    assert proof_candidate["row_domain_runtime_patch_ready"] is True
    assert proof_candidate["runtime_patch_authored_in_code"] is True
    assert proof_candidate["authored_but_not_enableable"] is True
    assert proof_candidate["runtime_enablement_allowed"] is False
    assert "reviewed_runtime_patch_exists=false" in proof_candidate["recommendation"]
    assert "not another B5A workspace rerun" in proof_candidate["recommendation"]
    assert "reviewed_runtime_patch_exists=false" in summary["gate"]["recommendation"]


def test_coordinate_validation_precheck_candidate_moves_to_acceptance_after_review_state(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    start_path = project_root / "start.json"
    matrix_path = project_root / "matrix.json"
    b5a_path = project_root / "b5a.json"
    probe_path = project_root / "probe.json"
    delta_path = project_root / "delta.json"
    core_path = project_root / "pair_core.json"
    no_ghost_path = project_root / "no_ghost.json"
    order_capacity_path = project_root / "order_capacity.json"
    runtime_patch_status_path = project_root / "runtime_patch_status.json"
    review_state_path = project_root / "review_state.json"
    _write_json(start_path, _start_compatibility_payload())
    _write_json(matrix_path, _solver_matrix_payload())
    _write_json(b5a_path, _b5a_summary_payload())
    _write_json(probe_path, _joined_xy_profile_probe_payload())
    _write_json(delta_path, _joined_xy_delta_synthesis_payload())
    _write_json(core_path, _anchor119_pair_x_core_synthesis_payload())
    _write_json(no_ghost_path, _anchor119_pair_x_no_ghost_space_synthesis_payload())
    _write_json(order_capacity_path, _order_implied_capacity_explanation_payload())
    _write_json(
        runtime_patch_status_path,
        _anchor119_row_domain_runtime_patch_status_payload(),
    )
    _write_json(review_state_path, _anchor119_row_domain_review_state_payload())

    summary = build_phase3b_coordinate_validation_precheck_candidate_summary(
        project_root,
        start_compatibility_path=start_path,
        forced_anchor_solver_matrix_path=matrix_path,
        b5a_summary_path=b5a_path,
        joined_xy_profile_probe_path=probe_path,
        joined_xy_delta_synthesis_path=delta_path,
        anchor119_pair_x_core_synthesis_path=core_path,
        anchor119_pair_x_no_ghost_space_synthesis_path=no_ghost_path,
        order_implied_capacity_explanation_path=order_capacity_path,
        anchor119_row_domain_runtime_patch_status_path=runtime_patch_status_path,
        anchor119_row_domain_review_state_path=review_state_path,
        min_rejected_anchor_count=3,
        min_matrix_infeasible_count=3,
    )

    proof_candidate = summary["joined_xy_proof_preserving_candidate"]
    assert proof_candidate["row_domain_runtime_patch_ready"] is True
    assert proof_candidate["row_domain_review_state_ready"] is True
    assert proof_candidate["reviewed_runtime_patch_exists"] is True
    assert "production_acceptance_refresh_completed" in proof_candidate["recommendation"]
    assert "prod_4x4_normal" in proof_candidate["recommendation"]
    assert summary["gate"]["recommendation"] == proof_candidate["recommendation"]


def test_coordinate_validation_precheck_candidate_fails_missing_matrix(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    start_path = project_root / "start.json"
    _write_json(start_path, _start_compatibility_payload())

    summary = build_phase3b_coordinate_validation_precheck_candidate_summary(
        project_root,
        start_compatibility_path=start_path,
        forced_anchor_solver_matrix_path=project_root / "missing.json",
    )

    assert summary["gate"]["design_gate_passed"] is False
    failed = {check["check_id"] for check in summary["checks"] if check["status"] == "fail"}
    assert "forced_anchor_solver_matrix_present" in failed
    assert "matrix_all_infeasible" in failed


def test_coordinate_validation_precheck_candidate_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    start_path = project_root / "start.json"
    matrix_path = project_root / "matrix.json"
    output_dir = tmp_path / "out"
    _write_json(start_path, _start_compatibility_payload())
    _write_json(matrix_path, _solver_matrix_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "coordinate_validation" / "build_precheck_candidate.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--start-compatibility",
            str(start_path),
            "--forced-anchor-solver-matrix",
            str(matrix_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate-validation precheck candidate gate" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--start-compatibility",
            str(start_path),
            "--forced-anchor-solver-matrix",
            str(matrix_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_precheck_candidate_json=" in write.stdout
    payload = json.loads((output_dir / "precheck_candidate.json").read_text(encoding="utf-8"))
    assert payload["gate"]["design_gate_passed"] is True
    assert (output_dir / "precheck_candidate.md").exists()
    assert (output_dir / "precheck_candidate.txt").exists()
