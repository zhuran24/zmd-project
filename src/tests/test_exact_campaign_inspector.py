from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.models.cut_manager import (
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_UNKNOWN,
    RUN_STATUS_UNPROVEN,
)
from src.search.campaign_telemetry import (
    append_campaign_wave_summary,
    build_wave_summary,
)
from src.search.exact_campaign import ExactCampaign
from src.search.exact_campaign_inspector import build_exact_campaign_inspection


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_exact_project(project_root: Path) -> Path:
    _write_json(
        project_root / "rules" / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 3, "height": 3}},
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


def _certified_solution() -> dict[str, object]:
    return {"tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}}


def test_inspector_reports_missing_campaign_state(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["present"] is False
    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is False
    assert inspection["campaign"]["resume_validation_reason"] == "campaign_state_missing"
    assert inspection["telemetry"]["present"] is False
    assert inspection["delivery_manifest"]["present"] is False
    failed_checks = {
        check["check_id"]
        for check in inspection["checks"]
        if check["status"] == "fail"
    }
    assert "campaign_state_present" in failed_checks
    assert "campaign_telemetry_present" in failed_checks
    assert "delivery_manifest_present" in failed_checks


def test_inspector_summarizes_valid_resume_state(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED", "selection_reason": "objective_head"},
    )
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "INFEASIBLE",
        proof_summary={"master_status": "INFEASIBLE"},
    )
    campaign.save()

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["present"] is True
    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is True
    assert inspection["campaign"]["resume_validation_reason"] is None
    assert inspection["campaign"]["candidate_count"] == 2
    assert inspection["campaign"]["candidate_status_counts"] == {
        "CERTIFIED": 1,
        "INFEASIBLE": 1,
    }
    assert inspection["campaign"]["best_certified_result"]["ghost_rect"] == {
        "w": 2,
        "h": 1,
        "area": 2,
    }
    assert inspection["campaign"]["best_certified_result"]["objective"] == {
        "area": 2,
        "min_side": 1,
    }


def test_inspector_reports_artifact_mismatch_without_mutating_state(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED"},
    )
    campaign.save()
    before = campaign.path.read_text(encoding="utf-8")

    rules_path = project_root / "rules" / "canonical_rules.json"
    rules_payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules_payload["globals"]["grid"]["width"] = 4
    _write_json(rules_path, rules_payload)

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is False
    assert inspection["campaign"]["resume_validation_reason"] == "artifact_hash_mismatch"
    assert campaign.path.read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    ("stop_reason", "status"),
    [
        ("candidate_returned_unknown", RUN_STATUS_UNKNOWN),
        ("candidate_returned_unproven", RUN_STATUS_UNPROVEN),
        ("worker_process_failed", RUN_STATUS_UNKNOWN),
    ],
)
def test_inspector_keeps_stop_reason_and_best_certified_result_visible(
    tmp_path: Path,
    stop_reason: str,
    status: str,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED"},
    )
    campaign.mark_campaign_stopped(stop_reason, status=status)
    campaign.save()

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["last_stop_reason"]["reason"] == stop_reason
    assert inspection["campaign"]["final_status"] == RUN_STATUS_CERTIFIED
    assert inspection["campaign"]["best_certified_result"]["ghost_rect"]["area"] == 2


def test_inspector_summarizes_telemetry(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
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
                    "candidate_key": "2x1",
                    "status": RUN_STATUS_UNKNOWN,
                    "proof_summary": {"master_status": "UNKNOWN"},
                }
            ],
            completed=True,
            failure_reason=None,
            dispatched_candidate_keys=["2x1"],
        ),
    )

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["telemetry"]["present"] is True
    assert inspection["telemetry"]["wave_count"] == 1
    assert inspection["telemetry"]["last_wave"]["wave_index"] == 1
    assert inspection["telemetry"]["aggregate"]["status_counts"] == {RUN_STATUS_UNKNOWN: 1}


def test_inspector_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "inspect_exact_campaign_state.py"
    output_path = tmp_path / "inspection.json"
    no_write_path = tmp_path / "no_write.json"

    no_write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output",
            str(no_write_path),
            "--no-write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_write_result.returncode == 0
    assert "exact campaign inspection" in no_write_result.stdout
    assert not no_write_path.exists()

    write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write_result.returncode == 0
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_exact_campaign_inspector_v1"
