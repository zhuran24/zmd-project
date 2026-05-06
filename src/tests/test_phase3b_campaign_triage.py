from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.models.cut_manager import (
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNKNOWN,
    RUN_STATUS_UNPROVEN,
)
from src.search.campaign_telemetry import append_campaign_wave_summary, build_wave_summary
from src.search.campaign_triage import (
    build_phase3b_unknown_triage_inventory,
    render_phase3b_unknown_triage_markdown,
    render_phase3b_unknown_triage_text,
)
from src.search.exact_campaign import ExactCampaign
from src.search.phase3b_campaign_repair import (
    mark_running_exact_campaign_candidates_interrupted,
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
    mandatory_instances = [
        {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        mandatory_instances,
    )
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def _precheck_proof(precheck_reason: str = "boundary_port_all_anchors_infeasible") -> dict:
    return {
        "mode": "certified_exact",
        "master_status": "INFEASIBLE",
        "master_candidate_precheck": {
            "triggered": True,
            "precheck_reason": precheck_reason,
            "master_solve_skipped": True,
        },
        "precheck_lookahead": {
            "enabled": True,
            "slot_index": 1,
            "limit": 8,
            "is_selected_head": False,
        },
    }


def _master_unknown_proof(
    *,
    branches: int | None = None,
    conflicts: int | None = None,
    compatible_anchor_count: int | None = None,
    compatibility_skipped: bool = False,
    failed_anchor_count: int | None = None,
    mandatory_precheck_time_budgeted: bool = False,
) -> dict:
    proof: dict[str, object] = {
        "mode": "certified_exact",
        "master_status": "UNKNOWN",
    }
    if branches is not None or conflicts is not None:
        proof["master_last_solve"] = {
            "status": "UNKNOWN",
            "branches": int(branches or 0),
            "conflicts": int(conflicts or 0),
            "search_profile": "test_profile",
        }
    if compatible_anchor_count is not None:
        proof["master_start_feasibility"] = {
            "ghost_anchor_compatible_count": int(compatible_anchor_count),
            "ghost_anchor_hint_status": "skipped_anchor_limit"
            if compatibility_skipped
            else "applied",
            "warm_start_strategy": "precheck_anchor_limit_skipped"
            if compatibility_skipped
            else "ghost_aware_mandatory_rebuild",
        }
        if compatibility_skipped:
            proof["master_start_feasibility"]["ghost_anchor_compatibility_skipped"] = True
    if failed_anchor_count is not None:
        proof["master_start_failure_attribution"] = {
            "failed_anchor_count": int(failed_anchor_count),
            "failure_reason_counts": {
                "blocked_cells_exhausted": int(failed_anchor_count)
            },
            "first_failed_group_id": "tiny_group",
            "first_failed_group_template": "tiny_facility",
            "first_failed_group_position": 3,
            "first_failed_group_required_count": 2,
            "first_failed_group_candidate_count": 5,
            "first_failed_group_surviving_after_blocked_count": 4,
            "first_failed_group_surviving_at_failure_count": 1,
            "top_failed_group_failures": [
                {
                    "group_id": "tiny_group",
                    "facility_type": "tiny_facility",
                    "failure_reason": "blocked_cells_exhausted",
                    "count": int(failed_anchor_count),
                }
            ],
            "failed_anchor_samples": [
                {
                    "anchor_idx": 4,
                    "failure_reason": "blocked_cells_exhausted",
                    "first_failed_group_id": "tiny_group",
                    "first_failed_group_template": "tiny_facility",
                    "first_failed_group_position": 3,
                    "first_failed_group_required_count": 2,
                    "first_failed_group_candidate_count": 5,
                    "first_failed_group_surviving_after_blocked_count": 4,
                    "first_failed_group_surviving_at_failure_count": 1,
                    "blocked_cell_count": 9,
                    "blocked_bbox": {"min_x": 0, "min_y": 0, "max_x": 2, "max_y": 2},
                    "local_repair_attempted": True,
                    "local_repair_success": False,
                    "local_repair_attempt_count": 2,
                }
            ],
        }
    if mandatory_precheck_time_budgeted:
        proof["master_mandatory_group_prechecks"] = {
            "evaluated": True,
            "supported_group_count": 1,
            "groups": [
                {
                    "group_id": "group::manufacturing_6x4::filling_capsule::13",
                    "facility_type": "manufacturing_6x4",
                    "operation_type": "filling_capsule",
                    "required_count": 3,
                    "oracle_mode": "m6x4_mixed",
                    "partial_due_to_time_budget": True,
                }
            ],
            "interrupted_due_to_time_budget": True,
            "time_budget_seconds": 180.0,
            "elapsed_seconds": 186.0,
        }
    return proof


def _signature_monotonic_start_failure_proof() -> dict:
    proof = _master_unknown_proof(
        branches=0,
        conflicts=0,
        compatible_anchor_count=0,
    )
    proof["master_start_failure_attribution"] = {
        "attempted_anchor_count": 112,
        "failed_anchor_count": 112,
        "failure_reason_counts": {
            "coordinate_validation_infeasible": 8,
            "coordinate_validation_ghost_overlap_forced_domain_infeasible": 2,
            "coordinate_validation_signature_monotonic_forced_label_infeasible": 102,
            "coordinate_validation_attempt_limit_reached": 1,
        },
        "failed_anchor_samples": [
            {
                "anchor_idx": 118,
                "failure_reason": (
                    "coordinate_validation_ghost_overlap_forced_domain_infeasible"
                ),
                "blocked_cell_count": 871,
            },
            {
                "anchor_idx": 119,
                "failure_reason": (
                    "coordinate_validation_signature_monotonic_forced_label_infeasible"
                ),
                "coordinate_validation_status": "INFEASIBLE",
                "coordinate_validation_reason": (
                    "signature_monotonic_forced_label_infeasible"
                ),
                "coordinate_validation_solver_profile_id": (
                    "signature_monotonic_forced_label_precheck"
                ),
                "blocked_cell_count": 871,
            }
        ],
    }
    return proof


def _ghost_overlap_forced_domain_start_failure_proof() -> dict:
    proof = _master_unknown_proof(
        branches=0,
        conflicts=0,
        compatible_anchor_count=0,
    )
    proof["master_start_failure_attribution"] = {
        "attempted_anchor_count": 9,
        "failed_anchor_count": 8,
        "failure_reason_counts": {
            "coordinate_validation_ghost_overlap_forced_domain_infeasible": 7,
            "coordinate_validation_signature_monotonic_forced_label_infeasible": 1,
            "coordinate_validation_attempt_limit_reached": 1,
        },
        "failed_anchor_samples": [
            {
                "anchor_idx": 118,
                "failure_reason": (
                    "coordinate_validation_ghost_overlap_forced_domain_infeasible"
                ),
                "blocked_cell_count": 871,
            },
            {
                "anchor_idx": 119,
                "failure_reason": (
                    "coordinate_validation_signature_monotonic_forced_label_infeasible"
                ),
                "blocked_cell_count": 871,
            },
        ],
    }
    return proof


def _one_blocker(inventory: dict, candidate_key: str) -> dict:
    matches = [
        entry
        for entry in inventory["blockers"]
        if entry["candidate_key"] == candidate_key
    ]
    assert len(matches) == 1
    return matches[0]


def test_triage_missing_campaign_state_returns_empty_inventory(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")

    inventory = build_phase3b_unknown_triage_inventory(project_root)

    assert inventory["metadata"]["source"] == "phase3b_unknown_triage_inventory_v1"
    assert inventory["summary"]["campaign_present"] is False
    assert inventory["summary"]["telemetry_present"] is False
    assert inventory["summary"]["blocker_count"] == 0
    assert inventory["blockers"] == []


@pytest.mark.parametrize(
    ("proof_summary", "expected_classification", "expected_stage", "expected_reason"),
    [
        ({"master_status": "UNKNOWN"}, "master_unknown", "master", "master_status:UNKNOWN"),
        (
            {"master_status": "FEASIBLE", "binding_status": "TIMEOUT"},
            "binding_timeout",
            "binding",
            "binding_status:TIMEOUT",
        ),
        (
            {"master_status": "FEASIBLE", "binding_status": "EMPTY_DOMAIN"},
            "binding_empty_domain",
            "binding",
            "binding_status:EMPTY_DOMAIN",
        ),
        (
            {"master_status": "FEASIBLE", "routing_status": "TIMEOUT"},
            "routing_timeout",
            "routing",
            "routing_status:TIMEOUT",
        ),
        (
            {"master_status": "FEASIBLE", "routing_status": "PRECHECK_FRONT_BLOCKED"},
            "routing_precheck_reject",
            "routing",
            "routing_status:PRECHECK_FRONT_BLOCKED",
        ),
        (
            {"master_status": "FEASIBLE", "routing_status": "ALL_INFEASIBLE"},
            "routing_all_infeasible",
            "routing",
            "routing_status:ALL_INFEASIBLE",
        ),
    ],
)
def test_triage_classifies_unknown_stage_variants(
    tmp_path: Path,
    proof_summary: dict,
    expected_classification: str,
    expected_stage: str,
    expected_reason: str,
) -> None:
    project_root = _build_exact_project(tmp_path / expected_classification)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(3, 1)
    campaign.mark_candidate_result(
        3,
        1,
        RUN_STATUS_UNKNOWN,
        proof_summary=proof_summary,
    )
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    campaign.save()

    inventory = build_phase3b_unknown_triage_inventory(project_root)
    blocker = _one_blocker(inventory, "3x1")

    assert blocker["classification"] == expected_classification
    assert blocker["stop_stage"] == expected_stage
    assert blocker["stop_reason"] == expected_reason
    assert blocker["disposition"] == "open"
    assert inventory["summary"]["classification_counts"][expected_classification] == 1
    assert "evidence_refs" in blocker
    assert blocker["repro_command"] == blocker["repro"]["command"]
    assert blocker["repro"]["workspace_policy"].startswith("Run repro")


@pytest.mark.parametrize(
    ("proof_summary", "expected_subtype"),
    [
        (
            _master_unknown_proof(branches=0, conflicts=0),
            "master_zero_branch_unknown",
        ),
        (
            _master_unknown_proof(branches=5, conflicts=3),
            "master_conflictful_unknown",
        ),
        (
            _master_unknown_proof(branches=0, conflicts=0, compatible_anchor_count=0),
            "master_start_incompatible_unknown",
        ),
        (
            _signature_monotonic_start_failure_proof(),
            "master_start_signature_monotonic_incompatible_unknown",
        ),
        (
            _ghost_overlap_forced_domain_start_failure_proof(),
            "master_start_ghost_overlap_forced_domain_unknown",
        ),
        (
            _master_unknown_proof(
                branches=0,
                conflicts=0,
                compatible_anchor_count=0,
                mandatory_precheck_time_budgeted=True,
            ),
            "mandatory_rectangle_precheck_time_budget_unknown",
        ),
        (
            _master_unknown_proof(
                branches=0,
                conflicts=0,
                compatible_anchor_count=0,
                compatibility_skipped=True,
            ),
            "master_start_skipped_unknown",
        ),
        (
            _master_unknown_proof(branches=0, conflicts=0, compatible_anchor_count=2),
            "master_start_compatible_zero_branch_unknown",
        ),
        (
            _master_unknown_proof(
                branches=5,
                conflicts=0,
                compatible_anchor_count=2,
                failed_anchor_count=1,
            ),
            "ghost_aware_start_failure_unknown",
        ),
        (
            _master_unknown_proof(),
            "master_unknown_general",
        ),
    ],
)
def test_triage_classifies_master_unknown_subtypes(
    tmp_path: Path,
    proof_summary: dict,
    expected_subtype: str,
) -> None:
    project_root = _build_exact_project(tmp_path / expected_subtype)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(3, 1)
    campaign.mark_candidate_result(
        3,
        1,
        RUN_STATUS_UNKNOWN,
        proof_summary=proof_summary,
    )
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    campaign.save()

    inventory = build_phase3b_unknown_triage_inventory(project_root)
    blocker = _one_blocker(inventory, "3x1")

    assert blocker["classification"] == "master_unknown"
    assert blocker["blocker_subtype"] == expected_subtype
    assert inventory["summary"]["subtype_counts"] == {expected_subtype: 1}
    assert blocker["evidence_refs"]["proof_fields"]["master_status"] == "UNKNOWN"
    assert blocker["linked_test_name"].endswith(
        "::test_triage_classifies_master_unknown_subtypes"
    )
    if expected_subtype == "ghost_aware_start_failure_unknown":
        assert blocker["start_failure_summary"] == {
            "failed_anchor_count": 1,
            "failure_reason_counts": {"blocked_cells_exhausted": 1},
            "first_failed_group": {
                "group_id": "tiny_group",
                "facility_type": "tiny_facility",
                "position": 3,
                "required_count": 2,
                "candidate_count": 5,
                "surviving_after_blocked_count": 4,
                "surviving_at_failure_count": 1,
            },
            "top_failed_group_failures": [
                {
                    "group_id": "tiny_group",
                    "facility_type": "tiny_facility",
                    "failure_reason": "blocked_cells_exhausted",
                    "count": 1,
                }
            ],
            "failed_anchor_samples": [
                {
                    "anchor_idx": 4,
                    "failure_reason": "blocked_cells_exhausted",
                    "first_failed_group_id": "tiny_group",
                    "first_failed_group_template": "tiny_facility",
                    "first_failed_group_position": 3,
                    "first_failed_group_required_count": 2,
                    "first_failed_group_candidate_count": 5,
                    "first_failed_group_surviving_after_blocked_count": 4,
                    "first_failed_group_surviving_at_failure_count": 1,
                    "blocked_cell_count": 9,
                    "blocked_bbox": {"min_x": 0, "min_y": 0, "max_x": 2, "max_y": 2},
                    "local_repair_attempted": True,
                    "local_repair_success": False,
                    "local_repair_attempt_count": 2,
                }
            ],
        }
        assert (
            blocker["evidence_refs"]["proof_fields"][
                "master_start_failure_attribution"
            ]["failed_anchor_samples"][0]["anchor_idx"]
            == 4
        )

    markdown = render_phase3b_unknown_triage_markdown(inventory)
    text = render_phase3b_unknown_triage_text(inventory)
    assert expected_subtype in markdown
    assert "Repro" in markdown
    assert expected_subtype in text
    assert "EXACT_CP_SAT_WORKERS=1" in text
    if expected_subtype == "ghost_aware_start_failure_unknown":
        assert "sample_anchor=4:blocked_cells_exhausted" in markdown
        assert "sample_anchor=4:blocked_cells_exhausted" in text
    if expected_subtype == "master_start_signature_monotonic_incompatible_unknown":
        assert blocker["start_failure_summary"]["failure_reason_counts"] == {
            "coordinate_validation_infeasible": 8,
            "coordinate_validation_ghost_overlap_forced_domain_infeasible": 2,
            "coordinate_validation_signature_monotonic_forced_label_infeasible": 102,
            "coordinate_validation_attempt_limit_reached": 1,
        }
        assert (
            "sample_anchor=119:"
            "coordinate_validation_signature_monotonic_forced_label_infeasible"
            in markdown
        )
        assert blocker["start_failure_summary"]["failed_anchor_samples"][1][
            "coordinate_validation_reason"
        ] == "signature_monotonic_forced_label_infeasible"
        assert blocker["start_failure_summary"]["failed_anchor_samples"][1][
            "coordinate_validation_solver_profile_id"
        ] == "signature_monotonic_forced_label_precheck"
    if expected_subtype == "master_start_ghost_overlap_forced_domain_unknown":
        assert blocker["start_failure_summary"]["failure_reason_counts"] == {
            "coordinate_validation_ghost_overlap_forced_domain_infeasible": 7,
            "coordinate_validation_signature_monotonic_forced_label_infeasible": 1,
            "coordinate_validation_attempt_limit_reached": 1,
        }
        assert (
            "sample_anchor=118:"
            "coordinate_validation_ghost_overlap_forced_domain_infeasible"
            in markdown
        )


def test_triage_classifies_unproven_candidate(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "unproven")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(4, 1)
    campaign.mark_candidate_result(
        4,
        1,
        RUN_STATUS_UNPROVEN,
        proof_summary={"master_status": "FEASIBLE"},
    )
    campaign.mark_campaign_stopped("candidate_returned_unproven", status=RUN_STATUS_UNPROVEN)
    campaign.save()

    inventory = build_phase3b_unknown_triage_inventory(project_root)
    blocker = _one_blocker(inventory, "4x1")

    assert blocker["classification"] == "unproven"
    assert blocker["stop_stage"] == "proof"
    assert blocker["stop_reason"] == "candidate_returned_unproven"


def test_triage_classifies_precheck_eliminated_candidate(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "precheck")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_result(
        5,
        1,
        RUN_STATUS_INFEASIBLE,
        proof_summary=_precheck_proof("mandatory_group_empty_candidate_pool"),
    )
    campaign.save()

    inventory = build_phase3b_unknown_triage_inventory(project_root)
    blocker = _one_blocker(inventory, "5x1")

    assert blocker["classification"] == "pre_master_eliminated"
    assert blocker["stop_stage"] == "pre_master"
    assert blocker["stop_reason"] == "mandatory_group_empty_candidate_pool"
    assert blocker["disposition"] == "mitigated"
    assert blocker["proof_summary"]["precheck_lookahead"]["slot_index"] == 1


def test_triage_records_worker_failure_from_campaign_and_telemetry(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "worker_failure")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_campaign_stopped("worker_process_failed", status=RUN_STATUS_UNKNOWN)
    campaign.save()
    append_campaign_wave_summary(
        project_root=project_root,
        campaign_path=campaign.path,
        reset=True,
        wave_summary=build_wave_summary(
            wave_index=1,
            candidate_results=[],
            completed=False,
            failure_reason="worker_process_failed:pid=1:exitcode=1",
            dispatched_candidate_keys=["3x1"],
        ),
    )

    inventory = build_phase3b_unknown_triage_inventory(project_root)
    blocker = _one_blocker(inventory, "__campaign__")

    assert blocker["classification"] == "orchestration_failure"
    assert blocker["stop_stage"] == "orchestration"
    assert blocker["stop_reason"] == "worker_process_failed:pid=1:exitcode=1"
    assert inventory["summary"]["classification_counts"]["orchestration_failure"] == 1


def test_triage_records_operator_interruption_heartbeat_subtype(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "operator_heartbeat")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(28, 22)
    campaign.update_candidate_running_proof_summary(
        28,
        22,
        {
            "campaign_heartbeat": {
                "schema_version": 1,
                "candidate_key": "28x22",
                "stage": "routing_solve",
                "event": "start",
                "iteration": 1,
                "routing_attempts": 1,
                "enumerated_bindings": 1,
                "updated_at": "2026-04-17T00:00:00Z",
            }
        },
    )
    campaign.save()

    mark_running_exact_campaign_candidates_interrupted(
        project_root,
        reason="b5a_wall_timeout",
        detail="test timeout",
    )

    inventory = build_phase3b_unknown_triage_inventory(project_root)
    blocker = _one_blocker(inventory, "28x22")

    assert blocker["classification"] == "orchestration_failure"
    assert blocker["blocker_subtype"] == "routing_solve_interrupted"
    assert blocker["stop_reason"] == "b5a_wall_timeout"
    assert inventory["summary"]["subtype_counts"] == {"routing_solve_interrupted": 1}
    assert blocker["proof_summary"]["campaign_heartbeat"]["stage"] == "routing_solve"
    assert blocker["evidence_refs"]["proof_fields"]["campaign_heartbeat"]["routing_attempts"] == 1
    assert blocker["linked_test_name"].endswith(
        "::test_triage_records_operator_interruption_heartbeat_subtype"
    )


def test_triage_merges_mixed_telemetry_only_candidates(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "mixed_telemetry")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.save()
    append_campaign_wave_summary(
        project_root=project_root,
        campaign_path=campaign.path,
        reset=True,
        wave_summary=build_wave_summary(
            wave_index=1,
            candidate_results=[
                {
                    "candidate_key": "6x1",
                    "status": RUN_STATUS_UNKNOWN,
                    "proof_summary": {
                        "mode": "certified_exact",
                        "routing_status": "TIMEOUT",
                    },
                },
                {
                    "candidate_key": "5x1",
                    "status": RUN_STATUS_UNPROVEN,
                    "proof_summary": {
                        "mode": "certified_exact",
                        "master_status": "FEASIBLE",
                    },
                },
                {
                    "candidate_key": "4x1",
                    "status": RUN_STATUS_INFEASIBLE,
                    "proof_summary": _precheck_proof(),
                },
                {
                    "candidate_key": "3x1",
                    "status": RUN_STATUS_UNKNOWN,
                    "proof_summary": _master_unknown_proof(branches=0, conflicts=0),
                },
            ],
            completed=True,
            failure_reason=None,
            dispatched_candidate_keys=["6x1", "5x1", "4x1", "3x1"],
        ),
    )

    inventory = build_phase3b_unknown_triage_inventory(project_root)

    assert inventory["summary"]["telemetry_present"] is True
    assert inventory["summary"]["telemetry_wave_count"] == 1
    assert inventory["summary"]["blocker_count"] == 4
    assert _one_blocker(inventory, "6x1")["classification"] == "routing_timeout"
    assert _one_blocker(inventory, "5x1")["classification"] == "unproven"
    assert _one_blocker(inventory, "4x1")["classification"] == "pre_master_eliminated"
    assert _one_blocker(inventory, "3x1")["blocker_subtype"] == "master_zero_branch_unknown"
    assert inventory["summary"]["classification_counts"] == {
        "pre_master_eliminated": 1,
        "master_unknown": 1,
        "routing_timeout": 1,
        "unproven": 1,
    }
    assert inventory["summary"]["subtype_counts"] == {"master_zero_branch_unknown": 1}


def test_triage_cli_writes_json_markdown_text_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "cli")
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_phase3b_unknown_triage.py"
    output_dir = tmp_path / "triage_output"
    no_write_dir = tmp_path / "no_write"

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
    assert no_write_result.returncode == 0
    assert "phase3b unknown triage inventory" in no_write_result.stdout
    assert not no_write_dir.exists()

    write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write_result.returncode == 0
    assert (output_dir / "blocker_inventory.json").exists()
    assert (output_dir / "blocker_inventory.md").exists()
    assert (output_dir / "blocker_inventory.txt").exists()
    payload = json.loads((output_dir / "blocker_inventory.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_unknown_triage_inventory_v1"
