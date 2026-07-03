"""Tests for the active IndustrialPlanner single-base end-to-end workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.run_industrial_planner_single_base_e2e import (
    SingleBaseE2EAssemblyStageResults,
    assemble_single_base_e2e_result,
    run_single_base_e2e_workflow,
)


def _synthetic_stage_results(**overrides: Any) -> SingleBaseE2EAssemblyStageResults:
    fields: dict[str, Any] = {
        "planning_summary": {"status": "proven_equivalent", "synthetic_for_test": True},
        "export_summary": {"status": "written", "synthetic_for_test": True},
        "validation_summary": {
            "delivery_validation_status": "validator_acceptable_with_warnings",
            "is_import_compatible": True,
            "is_layout_healthy": True,
            "synthetic_for_test": True,
        },
        "throughput_summary": {"status": "proven_equivalent", "synthetic_for_test": True},
        "fresh_support_suite_summary": {"status": "written", "synthetic_for_test": True},
        "checked_in_support_suite_summary": {
            "status": "clean",
            "drift_entry_count": 0,
            "synthetic_for_test": True,
        },
        "checked_artifact_suite_summary": {
            "status": "clean",
            "drift_entry_count": 0,
            "synthetic_for_test": True,
        },
        "artifacts": (),
        "notes": ("synthetic assembly test input; no release artifacts written.",),
        "synthetic_for_test": True,
    }
    fields.update(overrides)
    return SingleBaseE2EAssemblyStageResults(**fields)


def test_single_base_e2e_workflow_writes_successful_active_contract_bundle(tmp_path: Path) -> None:
    # Sentinel: this is the only test in this file that runs the real full workflow.
    run_dir = tmp_path / "single_base_e2e"

    result = run_single_base_e2e_workflow(run_dir=run_dir)

    assert result.overall_status == "success"
    assert result.failure_stage is None
    assert result.failure_classification is None
    assert result.deliverable_status == "ready_for_single_base_delivery"
    assert result.requested_base_id == "valley4_protocol_core"
    assert result.requested_base_is_active_contract is True

    assert result.planning_summary["status"] == "proven_equivalent"
    assert result.export_summary["status"] == "written"
    assert result.validation_summary["delivery_validation_status"] == "validator_acceptable_with_warnings"
    assert result.validation_summary["is_import_compatible"] is True
    assert result.validation_summary["is_layout_healthy"] is True
    assert result.validation_summary["port_warning_count"] == 52
    assert result.throughput_summary["status"] == "proven_equivalent"
    assert result.throughput_summary["proven_recipe_count"] == 17
    assert result.throughput_summary["required_recipe_count"] == 17
    assert result.checked_in_support_suite_summary["status"] == "clean"
    assert result.checked_artifact_suite_summary["status"] == "clean"

    assert (run_dir / "canonical" / "full_demand_recipe_capacity_canonical_blueprint.json").exists()
    assert (run_dir / "bundle" / "industrial_planner.blueprint.json").exists()
    assert (run_dir / "bundle" / "industrial_planner.compatibility_manifest.json").exists()
    assert (run_dir / "bundle" / "validation_report.json").exists()
    assert (run_dir / "bundle" / "throughput_report.json").exists()
    assert (run_dir / "support_suite" / "full_demand_support_overview.md").exists()
    assert (run_dir / "checks" / "support_suite_inventory_summary.json").exists()
    assert (run_dir / "checks" / "checked_artifact_suite_summary.json").exists()
    assert (run_dir / "run_summary.md").exists()

    summary_payload = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary_payload["overall_status"] == "success"
    assert summary_payload["deliverable_status"] == "ready_for_single_base_delivery"
    assert summary_payload["exact_full_scale_certified"]["status"] == "open"
    assert summary_payload["validation"]["delivery_validation_status"] == "validator_acceptable_with_warnings"

    markdown = (run_dir / "run_summary.md").read_text(encoding="utf-8")
    assert "IndustrialPlanner Single-Base End-to-End Run Summary" in markdown
    assert "Validator interpretation" in markdown
    assert "Full-scale exact `CERTIFIED` status: `open`" in markdown


def test_single_base_e2e_assembly_fails_closed_on_contract_ceiling_debug_base(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "synthetic_single_base_e2e"
    stage_results = _synthetic_stage_results(
        planning_summary={
            "status": "unsupported_by_canonical_contract",
            "synthetic_for_test": True,
        },
        export_summary={"status": "skipped", "synthetic_for_test": True},
        validation_summary={
            "delivery_validation_status": "skipped",
            "synthetic_for_test": True,
        },
        throughput_summary={"status": "skipped", "synthetic_for_test": True},
    )

    result = assemble_single_base_e2e_result(
        run_dir=run_dir,
        requested_base_id="wuling_protocol_core",
        stage_results=stage_results,
    )

    assert result.overall_status == "planning_failed"
    assert result.failure_stage == "planning"
    assert result.failure_classification == "unsupported_by_canonical_contract"
    assert result.deliverable_status == "not_ready"
    assert result.requested_base_is_active_contract is False
    assert result.planning_summary["status"] == "unsupported_by_canonical_contract"
    assert result.export_summary["status"] == "skipped"
    assert result.validation_summary["delivery_validation_status"] == "skipped"
    assert result.throughput_summary["status"] == "skipped"
    assert stage_results.synthetic_for_test is True
    assert result.planning_summary["synthetic_for_test"] is True

    assert not run_dir.exists()
    summary_payload = result.to_dict()
    assert summary_payload["overall_status"] == "planning_failed"
    assert summary_payload["failure_classification"] == "unsupported_by_canonical_contract"


def test_single_base_e2e_assembly_surfaces_checked_in_support_drift(tmp_path: Path) -> None:
    run_dir = tmp_path / "synthetic_single_base_e2e"
    stage_results = _synthetic_stage_results(
        checked_in_support_suite_summary={
            "status": "drift_detected",
            "drift_entry_count": 1,
            "synthetic_for_test": True,
        },
        checked_artifact_suite_summary={
            "status": "drift_detected",
            "drift_entry_count": 1,
            "synthetic_for_test": True,
        },
    )

    result = assemble_single_base_e2e_result(
        run_dir=run_dir,
        requested_base_id="valley4_protocol_core",
        stage_results=stage_results,
    )

    assert result.overall_status == "checked_in_support_drift_detected"
    assert result.failure_stage == "checked_in_support_suite"
    assert result.failure_classification == "support_suite_inventory_drift"
    assert result.deliverable_status == "bundle_ready_repo_reports_drifting"
    assert result.checked_in_support_suite_summary["status"] == "drift_detected"
    assert result.checked_in_support_suite_summary["drift_entry_count"] == 1
    assert result.checked_artifact_suite_summary["status"] == "drift_detected"
    assert stage_results.synthetic_for_test is True
    assert result.checked_in_support_suite_summary["synthetic_for_test"] is True

    assert not run_dir.exists()
    summary_payload = result.to_dict()
    assert summary_payload["overall_status"] == "checked_in_support_drift_detected"
    assert summary_payload["checked_in_support_suite_inventory"]["status"] == "drift_detected"
    assert summary_payload["checked_artifact_suite"]["status"] == "drift_detected"
