from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.exact_campaign import compute_exact_artifact_hashes
from src.search.phase3b_b5a_certified_anchor_promotion_review_packet import (
    build_phase3b_b5a_certified_anchor_promotion_review_packet,
)
from src.search.phase3b_b5a_gate_integration_marker import (
    B5A_GATE_INTEGRATION_MARKER_SOURCE,
    build_phase3b_b5a_gate_integration_marker,
)
from src.search.phase3b_b5a_certification_contracts import chain_fingerprint, sha256_file
from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator,
)
from src.search.phase3b_long_run_preflight import (
    EXPECTED_PRODUCTION_FRONTIER_CANDIDATES,
    build_phase3b_long_run_preflight_summary,
    render_phase3b_long_run_preflight_markdown,
    render_phase3b_long_run_preflight_text,
)
from src.tests.test_phase3b_b5a_certified_anchor_promotion_review_packet import (
    _valid_promotion_payload,
    _write_valid_chain,
)
from src.tests.test_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator import (
    _acceptance_execution_staging_json,
    _pre_run_acceptance_validation_json,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_exact_project(project_root: Path) -> Path:
    _write_json(
        project_root / "rules" / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 6, "height": 6}},
            "facility_templates": {
                "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
            },
        },
    )
    _write_json(
        project_root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "tiny_facility": [
                    {
                        "pose_id": "tiny_0",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    }
                ]
            }
        },
    )
    _write_json(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    _write_json(
        project_root / ".artifacts" / "phase3b_startline" / "startline_manifest.json",
        {
            "metadata": {"source": "phase3b_startline_manifest_v1"},
            "exact_source_of_truth_hashes": compute_exact_artifact_hashes(project_root),
        },
    )
    return project_root


def _write_b5a_summary(
    project_root: Path,
    *,
    anchor_found: bool,
    last_stop_reason: str | None = None,
) -> Path:
    path = project_root / ".artifacts" / "phase3b_b5_anchor_sprint" / "operator_summary.json"
    _write_json(
        path,
        {
            "metadata": {"source": "phase3b_b5_anchor_sprint_summary_v1"},
            "status": {
                "anchor_found": bool(anchor_found),
                "outcome": "anchor_found" if anchor_found else "triage_required",
                "recommendation": "Proceed"
                if anchor_found
                else "Return to B3 triage or B2 targeted shrink.",
            },
            "anchor": {"candidate_key": "4x1"} if anchor_found else None,
            "campaign": {
                "last_stop_reason": None
                if last_stop_reason is None
                else {"reason": last_stop_reason, "status": "UNKNOWN"}
            },
        },
    )
    return path


def _write_b5a_gate_integration_marker(
    project_root: Path,
    *,
    ready: bool,
    proof_source: bool = False,
) -> Path:
    if ready and proof_source is False:
        return _write_strict_b5a_gate_integration_marker(project_root)
    path = (
        project_root
        / ".artifacts"
        / "phase3b_b5a_gate_integration_marker_20260426"
        / "b5a_gate_integration_marker.json"
    )
    _write_json(
        path,
        {
            "metadata": {
                "source": B5A_GATE_INTEGRATION_MARKER_SOURCE,
                "proof_source": False,
                "runtime_semantics_changed": False,
                "checkpoint_written": False,
                "runtime_elimination_authorized": False,
                "final_168h_authorized": False,
                "checkpoint_write_or_import_back_authorized": False,
                "release_viewer_frontdoor_status_promoted": False,
                "preflight_gate_mutated": False,
            },
            "status": {
                "gate_integration_marker_ready": bool(ready),
                "repo_side_b5a_gate_state_updated": bool(ready),
                "b5a_anchor_found": bool(ready),
                "certified_anchor_found": bool(ready),
                "proof_source": bool(proof_source),
                "runtime_semantics_changed": False,
                "checkpoint_written": False,
                "runtime_elimination_authorized": False,
                "final_168h_authorized": False,
                "checkpoint_write_or_import_back_authorized": False,
                "release_viewer_frontdoor_status_promoted": False,
                "preflight_gate_mutated": False,
            },
            "gate_integration_marker": {
                "gate_integration_marker_ready": bool(ready),
                "b5a_anchor_found": bool(ready),
                "certified_anchor_found": bool(ready),
                "proof_source": bool(proof_source),
                "runtime_semantics_changed": False,
                "checkpoint_written": False,
                "runtime_elimination_authorized": False,
                "final_168h_authorized": False,
                "checkpoint_write_or_import_back_authorized": False,
                "release_viewer_frontdoor_status_promoted": False,
                "preflight_gate_mutated": False,
            },
        },
    )
    return path


def _write_forged_self_consistent_b5a_marker(project_root: Path) -> Path:
    fake_chain_input = project_root / ".artifacts" / "fake_chain_input.json"
    _write_json(fake_chain_input, {"fake": "but hash-consistent"})
    chain_records = [
        {
            "input_id": "fake_chain_input",
            "path": ".artifacts/fake_chain_input.json",
            "exists": True,
            "sha256": sha256_file(fake_chain_input),
        }
    ]
    path = (
        project_root
        / ".artifacts"
        / "phase3b_b5a_gate_integration_marker_20260426"
        / "forged_b5a_gate_integration_marker.json"
    )
    _write_json(
        path,
        {
            "metadata": {
                "source": B5A_GATE_INTEGRATION_MARKER_SOURCE,
                "solver_invoked": False,
                "checkpoint_written": False,
                "proof_source": False,
                "runtime_semantics_changed": False,
                "runtime_elimination_authorized": False,
                "final_168h_authorized": False,
                "checkpoint_write_or_import_back_authorized": False,
                "release_viewer_frontdoor_status_promoted": False,
                "preflight_gate_mutated": False,
                "candidate_elimination_claim": False,
                "certified_anchor_found": False,
                "b5a_anchor_found": False,
            },
            "paths": {"project_root": str(project_root)},
            "chain_input_hashes": chain_records,
            "chain_fingerprint": chain_fingerprint(chain_records),
            "candidate": {
                "candidate_key": "67x13",
                "covered_anchors": list(range(118, 126)),
                "scope": (
                    "candidate=67x13, anchors=118-125, "
                    "b5a_certified_anchor_promotion_review"
                ),
            },
            "status": {
                "gate_integration_marker_ready": True,
                "repo_side_b5a_gate_state_updated": True,
                "b5a_anchor_found": True,
                "certified_anchor_found": True,
                "proof_source": False,
                "runtime_semantics_changed": False,
                "checkpoint_written": False,
                "runtime_elimination_authorized": False,
                "final_168h_authorized": False,
                "checkpoint_write_or_import_back_authorized": False,
                "release_viewer_frontdoor_status_promoted": False,
                "preflight_gate_mutated": False,
                "candidate_elimination_claim": False,
            },
            "gate_integration_marker": {
                "gate_integration_marker_ready": True,
                "b5a_anchor_found": True,
                "certified_anchor_found": True,
                "proof_source": False,
                "runtime_semantics_changed": False,
                "checkpoint_written": False,
                "runtime_elimination_authorized": False,
                "final_168h_authorized": False,
                "checkpoint_write_or_import_back_authorized": False,
                "release_viewer_frontdoor_status_promoted": False,
                "preflight_gate_mutated": False,
                "candidate_elimination_claim": False,
            },
            "checks": [{"check_id": "fake_check", "status": "pass", "detail": "forged"}],
        },
    )
    return path


def _write_strict_b5a_gate_integration_marker(project_root: Path) -> Path:
    tmp_path = project_root.parent
    chain_project, paths = _write_valid_chain(tmp_path)
    assert chain_project == project_root
    payload_path = Path(".artifacts/promotion_payload.json")
    _write_json(project_root / payload_path, _valid_promotion_payload())
    packet = build_phase3b_b5a_certified_anchor_promotion_review_packet(
        project_root,
        review_state_path=paths["review_state"],
        localized_evidence_validator_path=paths["validator"],
        localized_evidence_readiness_path=paths["readiness"],
        reason_localization_path=paths["reason"],
        post_acceptance_blocker_summary_path=paths["post"],
        promotion_review_payload_path=payload_path,
    )
    assert packet["status"]["promotion_review_packet_ready"] is True
    assert packet["status"]["promotion_review_payload_validated"] is True
    packet_path = Path(
        ".artifacts/phase3b_b5a_certified_anchor_promotion_review_packet_20260425/"
        "b5a_certified_anchor_promotion_review_packet.json"
    )
    _write_json(project_root / packet_path, packet)
    marker = build_phase3b_b5a_gate_integration_marker(
        project_root,
        promotion_review_packet_path=packet_path,
    )
    assert marker["status"]["gate_integration_marker_ready"] is True
    marker_path = (
        project_root
        / ".artifacts"
        / "phase3b_b5a_gate_integration_marker_20260426"
        / "b5a_gate_integration_marker.json"
    )
    _write_json(marker_path, marker)
    return marker_path


def _write_production_acceptance(
    project_root: Path,
    *,
    record: dict | None,
) -> Path:
    path = (
        project_root
        / ".codex_test_logs"
        / "phase3b"
        / "production_acceptance_after_change.json"
    )
    run_records = [
        _production_acceptance_record(project_root, "prod_1x1", 1, 1),
        _production_acceptance_record(project_root, "prod_2x4", 2, 4),
        _production_acceptance_record(project_root, "prod_2x8", 2, 8),
    ]
    if record is not None:
        prod_4x4 = _production_acceptance_record(project_root, "prod_4x4", 4, 4)
        prod_4x4.update(record)
        run_records.insert(2, prod_4x4)
    _write_json(
        path,
        {
            "benchmark_inputs": {
                "grid_w": 70,
                "grid_h": 70,
                "safe_area_upper_bound": 1347,
                "selected_candidate": [1330, 70, 19],
                "frontier_candidates": EXPECTED_PRODUCTION_FRONTIER_CANDIDATES,
            },
            "logical_cpu_count": 24,
            "physical_cpu_count": 24,
            "generated_at_epoch": 1770000000.0,
            "suite_kind": "production-acceptance",
            "requested_master_search_profile": "exact_coordinate_guided_branching_v4",
            "process_priority_mode": "normal",
            "process_priority_source": "default",
            "process_priority_applied": False,
            "process_priority_error": None,
            "process_priority_platform": "win32",
            "run_records": run_records,
        },
    )
    return path


def _production_acceptance_record(
    project_root: Path,
    label: str,
    process_count: int,
    worker_count_per_process: int,
) -> dict:
    artifact_dir = project_root / ".codex_test_logs" / "parallelism_benchmark"
    output_json = artifact_dir / f"{label}__production-campaign-run__fixture.json"
    log_path = artifact_dir / f"{label}__production-campaign-run__fixture.log"
    campaign_state_path = (
        artifact_dir
        / "workspaces"
        / f"{label}__fixture"
        / "data"
        / "checkpoints"
        / "exact_campaign_state.json"
    )
    campaign_telemetry_path = (
        artifact_dir
        / "workspaces"
        / f"{label}__fixture"
        / "data"
        / "checkpoints"
        / "exact_campaign_telemetry.json"
    )
    child_payload = {
        "target": "production-campaign-run",
        "completed": True,
        "parallel_processes": process_count,
        "requested_master_search_profile": "exact_coordinate_guided_branching_v4",
        "campaign_valid_after_run": True,
        "duplicated_work": False,
    }
    _write_json(output_json, child_payload)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("fixture production acceptance log\n", encoding="utf-8")
    _write_json(campaign_state_path, {"fixture": True, "label": label})
    _write_json(campaign_telemetry_path, {"fixture": True, "label": label})
    return {
        "label": label,
        "process_count": process_count,
        "worker_count_per_process": worker_count_per_process,
        "target": "production-campaign-run",
        "completed": True,
        "parallel_processes": process_count,
        "requested_master_search_profile": "exact_coordinate_guided_branching_v4",
        "campaign_valid_after_run": True,
        "duplicated_work": False,
        "return_code": 0,
        "command": "python temp_scripts/benchmark_parallelism.py --suite-kind production-acceptance",
        "project_root": str(project_root),
        "output_json": str(output_json),
        "log_path": str(log_path),
        "campaign_state_path": str(campaign_state_path),
        "campaign_telemetry_path": str(campaign_telemetry_path),
        "wall_seconds": 1.0,
    }


def _write_production_acceptance_result_validator(
    project_root: Path,
    acceptance_path: Path,
) -> Path:
    staging_path = (
        project_root
        / ".artifacts"
        / "test_acceptance_execution_staging.json"
    )
    pre_run_path = (
        project_root
        / ".artifacts"
        / "test_pre_run_acceptance_validation.json"
    )
    _write_json(staging_path, _acceptance_execution_staging_json())
    _write_json(pre_run_path, _pre_run_acceptance_validation_json())
    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator(
            project_root,
            acceptance_execution_staging_path=staging_path,
            pre_run_acceptance_validation_path=pre_run_path,
            acceptance_result_path=acceptance_path,
        )
    )
    path = (
        project_root
        / ".artifacts"
        / "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_20260424"
        / "anchor119_row_domain_acceptance_result_validator.json"
    )
    _write_json(path, report)
    return path


def _write_group_packing_promotion_spec(project_root: Path) -> Path:
    path = (
        project_root
        / ".artifacts"
        / "phase3b_group_packing_precheck_promotion_spec"
        / "promotion_spec.json"
    )
    _write_json(
        path,
        {
            "metadata": {
                "source": "phase3b_group_packing_precheck_promotion_spec_v1"
            },
            "candidate": {"key": "69x19"},
            "promotion_status": {
                "spec_ready_for_runtime_slice": True,
                "runtime_slice_implemented": True,
                "runtime_promotion_ready": False,
                "runtime_promotion_guarded": True,
                "promotion_blocked_by": ["runtime_promotion_guard"],
            },
        },
    )
    return path


def _write_group_packing_proof_promotion(
    project_root: Path,
    *,
    ready: bool = False,
    blockers: list[str] | None = None,
) -> Path:
    blocked_by = [] if ready else (
        blockers
        or [
            "prefix_conditioned_evidence_not_terminal_safe",
            "terminal_safe_coverage_incomplete",
        ]
    )
    path = (
        project_root
        / ".artifacts"
        / "phase3b_group_packing_proof_promotion"
        / "proof_promotion_blockers.json"
    )
    _write_json(
        path,
        {
            "metadata": {
                "source": "phase3b_group_packing_proof_promotion_blockers_v1"
            },
            "candidate": {"key": "69x19"},
            "promotion_readiness": {
                "diagnostic_evidence_ready": True,
                "proof_promotion_ready": bool(ready),
                "blocked_by": blocked_by,
            },
            "checks": [
                {
                    "check_id": "soundness_gate_terminal_safe",
                    "status": "pass" if ready else "fail",
                    "detail": "test fixture",
                }
            ],
        },
    )
    return path


def _write_coordinate_validation_precheck_candidate(
    project_root: Path,
    *,
    reviewed_runtime_patch_exists: bool = False,
) -> Path:
    path = (
        project_root
        / ".artifacts"
        / "phase3b_coordinate_validation_precheck_candidate"
        / "precheck_candidate.json"
    )
    payload = {
        "metadata": {
            "source": "phase3b_coordinate_validation_precheck_candidate_v2"
        },
        "candidate": {"key": "67x13"},
        "gate": {
            "design_gate_passed": True,
            "runtime_promotion_ready": False,
            "recommendation": "Coordinate validation design candidate.",
        },
        "coordinate_validation": {"rejected_count": 8},
        "forced_anchor_solver_matrix": {"matrix_all_infeasible": True},
    }
    if reviewed_runtime_patch_exists:
        payload["gate"]["recommendation"] = (
            "Reviewed runtime patch state is now marked in a repo-side artifact. "
            "The next gate is production_acceptance_refresh_completed via the "
            "locked prod_4x4_normal production acceptance refresh; "
            "runtime_enablement_allowed remains false and this is not final "
            "168h authorization."
        )
        payload["joined_xy_proof_preserving_candidate"] = {
            "proof_preserving_precheck_ready": True,
            "row_domain_runtime_patch_ready": True,
            "row_domain_review_state_ready": True,
            "reviewed_runtime_patch_exists": True,
            "runtime_enablement_allowed": False,
            "recommendation": payload["gate"]["recommendation"],
        }
    _write_json(path, payload)
    return path


def _write_coordinate_validation_promotion_spec(
    project_root: Path,
    *,
    joined_xy_proof_candidate_design_ready: bool = False,
    joined_xy_proof_candidate_ready: bool = False,
    recommendation: str | None = None,
) -> Path:
    path = (
        project_root
        / ".artifacts"
        / "phase3b_coordinate_validation_precheck_promotion_spec"
        / "promotion_spec.json"
    )
    _write_json(
        path,
        {
            "metadata": {
                "source": "phase3b_coordinate_validation_precheck_promotion_spec_v1"
            },
            "candidate": {"key": "67x13"},
            "promotion_status": {
                "spec_ready_for_runtime_slice": True,
                "runtime_slice_implemented": True,
                "runtime_promotion_ready": False,
                "runtime_promotion_guarded": True,
                "promotion_blocked_by": ["runtime_promotion_guard"],
                **({"recommendation": recommendation} if recommendation else {}),
            },
            "evidence_summary": {
                "joined_xy_proof_candidate_design_ready": bool(
                    joined_xy_proof_candidate_design_ready
                ),
                "joined_xy_proof_candidate_ready": bool(
                    joined_xy_proof_candidate_ready
                ),
                "joined_xy_proof_candidate_core_label_count": 3
                if joined_xy_proof_candidate_design_ready
                else 0,
            },
        },
    )
    return path


def _write_zero_branch_unknown_triage(project_root: Path) -> Path:
    path = (
        project_root
        / ".artifacts"
        / "phase3b_zero_branch_unknown_triage"
        / "zero_branch_unknown_triage.json"
    )
    _write_json(
        path,
        {
            "metadata": {"source": "phase3b_zero_branch_unknown_triage_v1"},
            "candidate": {"key": "67x13"},
            "matrix": {"zero_branch_unknown_count": 21},
            "findings": ["power_coverage_core_is_primary_suspect"],
            "recommendation": (
                "Zero-branch UNKNOWN is reproduced in the base forced-anchor model; "
                "model-slice findings point at power coverage core/residual optional interactions."
            ),
        },
    )
    return path


def _write_joined_xy_probe_synthesis(project_root: Path) -> Path:
    path = (
        project_root
        / ".artifacts"
        / "phase3b_joined_xy_probe_synthesis_20260423_r5"
        / "joined_xy_probe_synthesis.json"
    )
    _write_json(
        path,
        {
            "metadata": {
                "source": "phase3b_joined_xy_probe_synthesis_v2",
                "diagnostic_semantics": "joined_xy_probe_synthesis_not_proof",
                "proof_source": False,
            },
            "status": {
                "completed": True,
                "outcome": "joined_xy_targeted_anchor_set_completed",
                "recommendation": (
                    "Joined-XY now covers anchors 120-124 with search-progress UNKNOWN; "
                    "do not launch final 168h."
                ),
            },
            "aggregate": {
                "terminal_anchor_indices": [118],
                "search_progress_unknown_anchor_indices": [119, 120, 121, 122, 123, 124, 125],
                "zero_branch_unknown_count": 0,
            },
        },
    )
    return path


def _write_power_protocol_interaction(project_root: Path) -> Path:
    path = (
        project_root
        / ".artifacts"
        / "phase3b_power_protocol_interaction"
        / "power_protocol_interaction.json"
    )
    _write_json(
        path,
        {
            "metadata": {
                "source": "phase3b_power_protocol_interaction_diagnostic_v1"
            },
            "candidate": {"key": "67x13"},
            "analysis": {
                "primary_hypothesis": (
                    "conditioned_power_family_bounds_interact_with_protocol_residuals"
                ),
                "next_probe_family": "family_009",
                "next_probe_template": "protocol_storage_box",
            },
            "findings": ["protocol_storage_box_domain_tightens"],
            "recommendation": "Power/protocol interaction narrows the next probe.",
        },
    )
    return path


def _valid_prod_4x4_record() -> dict:
    return {
        "label": "prod_4x4",
        "process_count": 4,
        "worker_count_per_process": 4,
        "completed": True,
        "return_code": 0,
        "campaign_valid_after_run": True,
        "duplicated_work": False,
    }


def test_preflight_fails_when_b5a_summary_missing(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "b5a_summary_present") == "fail"
    assert _check_status(summary, "b5a_anchor_found") == "fail"


def test_preflight_fails_when_b5a_anchor_missing(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=False)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    _write_group_packing_promotion_spec(project_root)
    _write_group_packing_proof_promotion(project_root)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "b5a_anchor_found") == "fail"
    assert "B5A did not find a certified anchor" in summary["recommendation"]
    assert "diagnostic-only" in summary["recommendation"]
    assert "prefix_conditioned_evidence_not_terminal_safe" in summary["recommendation"]
    assert summary["b2_targeted_shrink"]["spec_ready_for_runtime_slice"] is True
    assert summary["b2_targeted_shrink"]["runtime_promotion_guarded"] is True
    assert summary["b2_targeted_shrink"]["proof_promotion_ready"] is False
    assert summary["b2_targeted_shrink"]["soundness_gate_terminal_safe"] is False


def test_preflight_rejects_legacy_b5a_summary_without_explicit_marker(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "explicit_b5a_gate_integration_marker_present") == "fail"
    assert _check_status(summary, "b5a_anchor_found") == "fail"
    detail = [
        check["detail"]
        for check in summary["checks"]
        if check["check_id"] == "b5a_anchor_found"
    ][0]
    assert "requires an explicit accepted B5A gate integration marker" in detail


def test_preflight_accepts_explicit_b5a_gate_integration_marker(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=False)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert _check_status(summary, "b5a_anchor_found") == "pass"
    assert summary["ready_for_final_long_run"] is True
    assert summary["b5a_gate_integration_marker"]["status"][
        "gate_integration_marker_ready"
    ] is True


def test_preflight_rejects_invalid_b5a_gate_integration_marker(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=False)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    marker_path = _write_b5a_gate_integration_marker(
        project_root,
        ready=True,
        proof_source=True,
    )

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "b5a_anchor_found") == "fail"
    detail = [
        check["detail"]
        for check in summary["checks"]
        if check["check_id"] == "b5a_anchor_found"
    ][0]
    assert "B5A gate integration marker not accepted" in detail


def test_preflight_rejects_forged_self_consistent_b5a_gate_integration_marker(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=False)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_forged_self_consistent_b5a_marker(project_root)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "b5a_anchor_found") == "fail"
    failed_rules = summary["b5a_gate_integration_marker"]["preflight_validation"][
        "failed_rule_ids"
    ]
    assert "required_chain_inputs_exact" in failed_rules
    assert "required_marker_check_ids_exact" in failed_rules


@pytest.mark.parametrize("mutation", ["exists_false", "exists_missing"])
def test_preflight_rejects_b5a_gate_integration_marker_with_tampered_chain_exists(
    tmp_path: Path,
    mutation: str,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=False)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if mutation == "exists_false":
        marker["chain_input_hashes"][0]["exists"] = False
    elif mutation == "exists_missing":
        marker["chain_input_hashes"][0].pop("exists")
    else:
        raise AssertionError(mutation)
    _write_json(marker_path, marker)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "b5a_anchor_found") == "fail"
    failed_rules = summary["b5a_gate_integration_marker"]["preflight_validation"][
        "failed_rule_ids"
    ]
    assert "chain_input_hashes_match" in failed_rules


def test_preflight_b2_advisory_is_not_a_final_long_run_gate(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)
    _write_coordinate_validation_precheck_candidate(project_root)
    _write_coordinate_validation_promotion_spec(project_root)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is True
    assert summary["b2_targeted_shrink"]["present"] is False
    assert summary["coordinate_validation_precheck"]["present"] is True
    assert summary["coordinate_validation_precheck"]["design_gate_passed"] is True
    assert summary["coordinate_validation_precheck"]["runtime_promotion_ready"] is False
    assert summary["coordinate_validation_promotion_spec"]["present"] is True
    assert summary["coordinate_validation_promotion_spec"][
        "spec_ready_for_runtime_slice"
    ] is True
    assert summary["coordinate_validation_promotion_spec"][
        "runtime_slice_implemented"
    ] is True
    assert summary["coordinate_validation_promotion_spec"][
        "runtime_promotion_guarded"
    ] is True
    assert "B5A workspace rerun" in summary["coordinate_validation_promotion_spec"][
        "recommendation"
    ]
    assert summary["b2_targeted_shrink"]["promotion_blocked_by"] == [
        "promotion_spec_missing"
    ]
    text = render_phase3b_long_run_preflight_text(summary)
    assert "coordinate_validation_precheck=" in text
    assert "coordinate_validation_promotion_spec=" in text


def test_preflight_prioritizes_coordinate_validation_when_b5a_anchor_missing(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=False)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    _write_group_packing_promotion_spec(project_root)
    _write_group_packing_proof_promotion(project_root)
    _write_coordinate_validation_precheck_candidate(project_root)
    _write_coordinate_validation_promotion_spec(project_root)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert "coordinate-validation is the active B2 follow-up for 67x13" in summary[
        "recommendation"
    ]
    assert "group-packing remains diagnostic-only" in summary["recommendation"]
    assert "b5a_anchor_found" in [
        check["check_id"] for check in summary["checks"] if check["status"] == "fail"
    ]


def test_preflight_prioritizes_zero_branch_unknown_when_present(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=False)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    _write_group_packing_promotion_spec(project_root)
    _write_group_packing_proof_promotion(project_root)
    _write_coordinate_validation_precheck_candidate(project_root)
    _write_coordinate_validation_promotion_spec(project_root)
    _write_zero_branch_unknown_triage(project_root)
    _write_power_protocol_interaction(project_root)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert "zero-branch UNKNOWN triage for 67x13" in summary["recommendation"]
    assert "Power/protocol interaction diagnostic narrows" in summary["recommendation"]
    assert summary["power_protocol_interaction"]["next_probe_family"] == "family_009"
    assert summary["zero_branch_unknown_triage"]["zero_branch_unknown_count"] == 21
    text = render_phase3b_long_run_preflight_text(summary)
    assert "zero_branch_unknown_triage=" in text
    assert "power_protocol_interaction=" in text


def test_preflight_prioritizes_joined_xy_when_synthesis_completed(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    b5a_path = _write_b5a_summary(project_root, anchor_found=False)
    payload = json.loads(b5a_path.read_text(encoding="utf-8"))
    payload["triage"] = {
        "top_blockers": [
            {
                "candidate_key": "67x13",
                "blocker_subtype": "master_start_incompatible_unknown",
                "proof_summary": {
                    "master_status": "UNKNOWN",
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
    }
    _write_json(b5a_path, payload)
    _write_production_acceptance(project_root, record=_valid_prod_4x4_record())
    _write_zero_branch_unknown_triage(project_root)
    _write_power_protocol_interaction(project_root)
    _write_joined_xy_probe_synthesis(project_root)
    _write_coordinate_validation_promotion_spec(
        project_root,
        joined_xy_proof_candidate_design_ready=True,
    )

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert "joined-XY workspace validation already reached conflictful master UNKNOWN" in summary[
        "recommendation"
    ]
    assert "coordinate_validation_infeasible currently rejects 8 sampled anchors" in summary[
        "recommendation"
    ]
    assert "preferred next move is to finish the joined-XY proof-preserving extraction" in summary[
        "recommendation"
    ]
    assert "protocol_planter_buckwheat_3_x_labels" in summary["recommendation"]
    assert summary["joined_xy_probe_synthesis"]["completed"] is True
    assert summary["joined_xy_probe_synthesis"]["zero_branch_unknown_count"] == 0
    text = render_phase3b_long_run_preflight_text(summary)
    assert "joined_xy_probe_synthesis=" in text


def test_preflight_uses_review_gate_recommendation_after_joined_xy_patch_authored(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    b5a_path = _write_b5a_summary(project_root, anchor_found=False)
    payload = json.loads(b5a_path.read_text(encoding="utf-8"))
    payload["triage"] = {
        "top_blockers": [
            {
                "candidate_key": "67x13",
                "blocker_subtype": "master_start_incompatible_unknown",
                "proof_summary": {
                    "master_status": "UNKNOWN",
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
    }
    _write_json(b5a_path, payload)
    _write_production_acceptance(project_root, record=_valid_prod_4x4_record())
    _write_zero_branch_unknown_triage(project_root)
    _write_power_protocol_interaction(project_root)
    _write_joined_xy_probe_synthesis(project_root)
    _write_coordinate_validation_promotion_spec(
        project_root,
        joined_xy_proof_candidate_design_ready=True,
        joined_xy_proof_candidate_ready=True,
        recommendation=(
            "Anchor119 row-domain runtime patch is authored; require "
            "reviewed_runtime_patch_exists before any B5A workspace rerun."
        ),
    )

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert "reviewed_runtime_patch_exists" in summary["recommendation"]
    assert "finish the joined-XY proof-preserving extraction" not in summary[
        "recommendation"
    ]
    assert "reviewed_runtime_patch_exists" in summary[
        "coordinate_validation_promotion_spec"
    ]["recommendation"]


def test_preflight_prefers_review_state_over_stale_review_gate_text(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    b5a_path = _write_b5a_summary(project_root, anchor_found=False)
    payload = json.loads(b5a_path.read_text(encoding="utf-8"))
    payload["triage"] = {
        "top_blockers": [
            {
                "candidate_key": "67x13",
                "blocker_subtype": "master_start_incompatible_unknown",
                "proof_summary": {
                    "master_status": "UNKNOWN",
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
    }
    _write_json(b5a_path, payload)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    _write_zero_branch_unknown_triage(project_root)
    _write_power_protocol_interaction(project_root)
    _write_joined_xy_probe_synthesis(project_root)
    _write_coordinate_validation_precheck_candidate(
        project_root,
        reviewed_runtime_patch_exists=True,
    )
    _write_coordinate_validation_promotion_spec(
        project_root,
        joined_xy_proof_candidate_design_ready=True,
        joined_xy_proof_candidate_ready=True,
        recommendation=(
            "Anchor119 row-domain runtime patch is authored; require "
            "reviewed_runtime_patch_exists before any B5A workspace rerun."
        ),
    )

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert summary["coordinate_validation_precheck"][
        "reviewed_runtime_patch_exists"
    ] is True
    assert summary["coordinate_validation_precheck"][
        "row_domain_review_state_ready"
    ] is True
    assert "prod_4x4_normal production acceptance are both validated" in summary[
        "recommendation"
    ]
    assert "remaining gate is B5A certified-anchor evidence" in summary[
        "recommendation"
    ]
    assert "production_acceptance_refresh_completed" not in summary["recommendation"]
    assert "require reviewed_runtime_patch_exists before" not in summary[
        "recommendation"
    ]


def test_preflight_prioritizes_latest_conflictful_b5a_over_stale_zero_branch(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    b5a_path = _write_b5a_summary(project_root, anchor_found=False)
    payload = json.loads(b5a_path.read_text(encoding="utf-8"))
    payload["triage"] = {
        "top_blockers": [
            {
                "candidate_key": "67x13",
                "blocker_subtype": "master_start_incompatible_unknown",
                "proof_summary": {
                    "master_status": "UNKNOWN",
                    "master_last_solve": {
                        "branches": 7439714,
                        "conflicts": 748173,
                        "deterministic_time": 1535.4,
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
    }
    _write_json(b5a_path, payload)
    _write_production_acceptance(project_root, record=_valid_prod_4x4_record())
    _write_zero_branch_unknown_triage(project_root)
    _write_power_protocol_interaction(project_root)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert "latest B5A reached conflictful master UNKNOWN for 67x13" in summary[
        "recommendation"
    ]
    assert "branches=7439714" in summary["recommendation"]
    assert "zero-branch UNKNOWN triage" not in summary["recommendation"]


def test_preflight_requires_proof_promotion_report_before_b2_shrink_advice(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=False)
    _write_production_acceptance(project_root, record=_valid_prod_4x4_record())
    _write_group_packing_promotion_spec(project_root)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert "proof-promotion/soundness evidence is missing" in summary["recommendation"]
    assert summary["b2_targeted_shrink"]["proof_promotion_present"] is False


def test_preflight_recommends_terminal_integration_when_proof_promotion_ready(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=False)
    _write_production_acceptance(project_root, record=_valid_prod_4x4_record())
    _write_group_packing_promotion_spec(project_root)
    _write_group_packing_proof_promotion(project_root, ready=True)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert "terminal proof integration" in summary["recommendation"]
    assert summary["b2_targeted_shrink"]["proof_promotion_ready"] is True


def test_preflight_prioritizes_b5a_timeout_over_b2_advisory(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(
        project_root,
        anchor_found=False,
        last_stop_reason="b5a_wall_timeout",
    )
    _write_production_acceptance(project_root, record=_valid_prod_4x4_record())
    _write_group_packing_promotion_spec(project_root)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert "b5a_wall_timeout" in summary["recommendation"]
    assert "production acceptance/final long run blocked" in summary["recommendation"]


def test_preflight_fails_when_production_acceptance_missing(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "explicit_production_acceptance_summary_present") == "fail"
    assert _check_status(summary, "production_acceptance_present") == "fail"


@pytest.mark.parametrize(
    "record",
    [
        None,
        {**_valid_prod_4x4_record(), "completed": False},
        {**_valid_prod_4x4_record(), "return_code": 1},
        {**_valid_prod_4x4_record(), "campaign_valid_after_run": False},
        {**_valid_prod_4x4_record(), "duplicated_work": True},
    ],
)
def test_preflight_fails_for_invalid_prod_4x4_acceptance_record(
    tmp_path: Path,
    record: dict | None,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(project_root, record=record)
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "production_acceptance_prod_4x4_valid") == "fail"


def test_preflight_rejects_minimal_fake_production_acceptance_summary(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)
    acceptance_path = (
        project_root
        / ".codex_test_logs"
        / "phase3b"
        / "production_acceptance_before_final_long_run.json"
    )
    _write_json(
        acceptance_path,
        {
            "run_records": [
                {
                    "completed": True,
                    "return_code": 0,
                    "campaign_valid_after_run": True,
                    "duplicated_work": False,
                }
            ]
        },
    )

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "production_acceptance_present") == "pass"
    assert _check_status(summary, "production_acceptance_prod_4x4_valid") == "fail"


def test_preflight_rejects_forged_production_acceptance_summary_and_validator(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)
    acceptance_path = (
        project_root
        / ".codex_test_logs"
        / "phase3b"
        / "production_acceptance_after_change.json"
    )
    _write_json(
        acceptance_path,
        {
            "suite_kind": "production-acceptance",
            "run_records": [_valid_prod_4x4_record()],
        },
    )
    expected_summary_path = str(acceptance_path.relative_to(project_root)).replace(
        "\\", "/"
    )
    validator_path = (
        project_root
        / ".artifacts"
        / "forged_acceptance_result_validator"
        / "anchor119_row_domain_acceptance_result_validator.json"
    )
    _write_json(
        validator_path,
        {
            "metadata": {
                "source": "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_v1"
            },
            "paths": {
                "project_root": str(project_root),
                "provided_acceptance_result": expected_summary_path,
            },
            "status": {
                "acceptance_result_validator_ready": True,
                "runtime_enablement_allowed": False,
                "acceptance_result_validation_performed": True,
                "acceptance_result_validation_passed": True,
            },
            "acceptance_result_validator": {
                "does_not_imply_enablement": True,
                "expected_result_path": expected_summary_path,
            },
            "result_validation": {
                "validation_performed": True,
                "validation_passed": True,
                "provided_acceptance_result_path": expected_summary_path,
                "provided_acceptance_result_sha256": sha256_file(acceptance_path),
                "result_path_matches_expected": True,
                "production_acceptance_suite_contract_passed": True,
                "production_acceptance_suite_contract_detail": "forged",
                "prod_4x4_record_found": True,
                "prod_4x4_record_selected_by": "label",
                "prod_4x4_record_valid_under_long_run_preflight": True,
                "supporting_artifacts_passed": True,
                "supporting_artifact_results": [],
            },
            "chain_input_hashes": [],
        },
    )

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "production_acceptance_prod_4x4_valid") == "fail"
    assert (
        _check_status(summary, "production_acceptance_result_validator_passed")
        == "fail"
    )
    failed_rules = summary["production_acceptance"]["result_validator"][
        "failed_rule_ids"
    ]
    assert "production_acceptance_result_validator_chain_inputs_exact" in failed_rules
    assert "production_acceptance_result_validator_canonical_rebuild" in failed_rules


@pytest.mark.parametrize(
    "mutation",
    ["missing_sha256", "all_zero_sha256", "path_mismatch", "duplicate_input_id"],
)
def test_preflight_rejects_tampered_production_acceptance_validator_chain_hashes(
    tmp_path: Path,
    mutation: str,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)
    payload = json.loads(validator_path.read_text(encoding="utf-8"))
    chain_records = payload["chain_input_hashes"]
    if mutation == "missing_sha256":
        chain_records[0].pop("sha256")
    elif mutation == "all_zero_sha256":
        chain_records[0]["sha256"] = "0" * 64
    elif mutation == "path_mismatch":
        chain_records[0]["path"] = ".artifacts/other.json"
    elif mutation == "duplicate_input_id":
        chain_records[0]["input_id"] = chain_records[1]["input_id"]
    else:
        raise AssertionError(mutation)
    _write_json(validator_path, payload)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert (
        _check_status(summary, "production_acceptance_result_validator_passed")
        == "fail"
    )
    failed_rules = summary["production_acceptance"]["result_validator"][
        "failed_rule_ids"
    ]
    assert "production_acceptance_result_validator_chain_hashes_match" in failed_rules


def test_preflight_rejects_shape_compatible_production_acceptance_validator_without_canonical_evidence(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)
    real_validator = json.loads(validator_path.read_text(encoding="utf-8"))
    fake_validator_path = tmp_path / "shape_compatible_fake_validator.json"
    fake_validator = {
        "metadata": {
            "source": real_validator["metadata"]["source"],
        },
        "paths": dict(real_validator["paths"]),
        "chain_input_hashes": list(real_validator["chain_input_hashes"]),
        "chain_fingerprint": real_validator["chain_fingerprint"],
        "status": {
            key: real_validator["status"].get(key)
            for key in [
                "acceptance_result_validator_ready",
                "runtime_enablement_allowed",
                "acceptance_result_validation_performed",
                "acceptance_result_validation_passed",
            ]
        },
        "acceptance_result_validator": dict(
            real_validator["acceptance_result_validator"]
        ),
        "result_validation": dict(real_validator["result_validation"]),
    }
    _write_json(fake_validator_path, fake_validator)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=fake_validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert (
        _check_status(summary, "production_acceptance_result_validator_passed")
        == "fail"
    )
    failed_rules = summary["production_acceptance"]["result_validator"][
        "failed_rule_ids"
    ]
    assert "production_acceptance_result_validator_canonical_match" in failed_rules


def test_preflight_rejects_tampered_selected_candidate_even_with_rebuilt_validator(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
    payload["benchmark_inputs"]["selected_candidate"] = [999, 999, 999]
    _write_json(acceptance_path, payload)
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "production_acceptance_prod_4x4_valid") == "fail"
    assert (
        _check_status(summary, "production_acceptance_result_validator_passed")
        == "fail"
    )
    failed_rules = summary["production_acceptance"]["result_validator"][
        "failed_rule_ids"
    ]
    assert "production_acceptance_result_suite_contract_passed" in failed_rules
    rule_details = {
        rule["rule_id"]: rule["detail"]
        for rule in summary["production_acceptance"]["result_validator"][
            "rule_results"
        ]
    }
    assert (
        rule_details["production_acceptance_result_suite_contract_passed"]
        == "benchmark_inputs.selected_candidate"
    )


def test_preflight_rejects_marker_rebuilt_from_blank_reason_candidate_key(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    chain_project, paths = _write_valid_chain(tmp_path)
    assert chain_project == project_root
    reason_path = project_root / paths["reason"]
    reason = json.loads(reason_path.read_text(encoding="utf-8"))
    reason["candidate"]["key"] = ""
    reason["candidate"]["matches_expected"] = False
    _write_json(reason_path, reason)
    payload_path = Path(".artifacts/promotion_payload.json")
    _write_json(project_root / payload_path, _valid_promotion_payload())
    packet = build_phase3b_b5a_certified_anchor_promotion_review_packet(
        project_root,
        review_state_path=paths["review_state"],
        localized_evidence_validator_path=paths["validator"],
        localized_evidence_readiness_path=paths["readiness"],
        reason_localization_path=paths["reason"],
        post_acceptance_blocker_summary_path=paths["post"],
        promotion_review_payload_path=payload_path,
    )
    packet_path = Path(
        ".artifacts/phase3b_b5a_certified_anchor_promotion_review_packet_20260425/"
        "b5a_certified_anchor_promotion_review_packet.json"
    )
    _write_json(project_root / packet_path, packet)
    marker = build_phase3b_b5a_gate_integration_marker(
        project_root,
        promotion_review_packet_path=packet_path,
    )
    marker_path = (
        project_root
        / ".artifacts"
        / "phase3b_b5a_gate_integration_marker_20260426"
        / "b5a_gate_integration_marker.json"
    )
    _write_json(marker_path, marker)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert packet["status"]["promotion_review_packet_ready"] is False
    assert marker["status"]["gate_integration_marker_ready"] is False
    assert summary["ready_for_final_long_run"] is False
    assert _check_status(summary, "b5a_anchor_found") == "fail"


def test_preflight_passes_when_all_gates_pass(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)

    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert summary["ready_for_final_long_run"] is True
    assert summary["preflight_gate_ready"] is True
    assert summary["ready_to_request_human_launch_authorization"] is True
    assert summary["human_launch_authorization_required"] is True
    assert summary["final_168h_authorized"] is False
    assert summary["execution_allowed"] is False
    assert summary["final_long_run"]["allowed"] is False
    assert summary["final_long_run"]["execution_allowed"] is False
    assert summary["final_long_run"]["final_168h_authorized"] is False
    assert summary["final_long_run"]["human_launch_authorization_required"] is True
    assert summary["final_long_run"]["preflight_gate_ready"] is True
    assert (
        summary["final_long_run"]["ready_to_request_human_launch_authorization"]
        is True
    )
    assert summary["final_long_run"]["command"] is None
    assert summary["final_long_run"]["non_dry_run_command"] is None
    assert all(check["status"] == "pass" for check in summary["checks"])
    assert "run_prod_4x4_normal.ps1" in summary["final_long_run"]["dry_run_command"]
    assert "-DryRun" in summary["final_long_run"]["dry_run_command"]

    markdown = render_phase3b_long_run_preflight_markdown(summary)
    text = render_phase3b_long_run_preflight_text(summary)
    assert "Ready to request human launch authorization: True" in markdown
    assert "Final 168h authorized: False" in markdown
    assert "Execution allowed: False" in markdown
    assert "ready_to_request_human_launch_authorization=True" in text
    assert "final_168h_authorized=False" in text
    assert "execution_allowed=False" in text
    assert "ready_for_final_long_run=True" in text
    assert "run_prod_4x4_normal.ps1 -ResumeCampaign\n" not in text


def test_preflight_builder_is_reentrant_in_one_interpreter(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)

    first = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )
    second = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        disk_free_gb_override=200.0,
    )

    assert first["ready_for_final_long_run"] is True
    assert second["ready_for_final_long_run"] is True
    assert first["final_long_run"] == second["final_long_run"]
    assert [check["check_id"] for check in first["checks"]] == [
        check["check_id"] for check in second["checks"]
    ]


def test_preflight_disk_threshold_can_block_and_be_overridden(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)

    blocked = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        min_free_gb=100.0,
        disk_free_gb_override=10.0,
    )
    allowed = build_phase3b_long_run_preflight_summary(
        project_root,
        production_acceptance_path=acceptance_path,
        production_acceptance_result_validator_path=validator_path,
        b5a_gate_integration_marker_path=marker_path,
        min_free_gb=5.0,
        disk_free_gb_override=10.0,
    )

    assert blocked["ready_for_final_long_run"] is False
    assert _check_status(blocked, "workspace_disk_free") == "fail"
    assert allowed["ready_for_final_long_run"] is True
    assert _check_status(allowed, "workspace_disk_free") == "pass"


def test_preflight_cli_does_not_emit_non_dry_run_command_when_ready(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _write_b5a_summary(project_root, anchor_found=True)
    acceptance_path = _write_production_acceptance(
        project_root, record=_valid_prod_4x4_record()
    )
    validator_path = _write_production_acceptance_result_validator(
        project_root, acceptance_path
    )
    marker_path = _write_b5a_gate_integration_marker(project_root, ready=True)
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "build_phase3b_long_run_preflight.py"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--production-acceptance-summary",
            str(acceptance_path),
            "--production-acceptance-result-validator",
            str(validator_path),
            "--b5a-gate-integration-marker",
            str(marker_path),
            "--min-free-gb",
            "0",
            "--no-write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "- ready: True" in result.stdout
    assert "- ready to request human launch authorization: True" in result.stdout
    assert "- final 168h authorized: False" in result.stdout
    assert "- execution allowed: False" in result.stdout
    assert "not emitted without human authorization" in result.stdout
    assert "run_prod_4x4_normal.ps1 -ResumeCampaign -DryRun" in result.stdout
    assert "run_prod_4x4_normal.ps1 -ResumeCampaign\n" not in result.stdout


def test_preflight_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_phase3b_long_run_preflight.py"
    output_dir = tmp_path / "preflight_output"
    no_write_dir = tmp_path / "preflight_no_write"

    no_write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(no_write_dir),
            "--no-write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_write_result.returncode == 2
    assert "phase3b final long-run preflight" in no_write_result.stdout
    assert not no_write_dir.exists()

    write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--min-free-gb",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write_result.returncode == 2
    assert (output_dir / "preflight_summary.json").exists()
    assert (output_dir / "preflight_summary.md").exists()
    assert (output_dir / "preflight_summary.txt").exists()
    payload = json.loads((output_dir / "preflight_summary.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_long_run_preflight_v1"


def _check_status(summary: dict, check_id: str) -> str:
    matches = [check for check in summary["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
