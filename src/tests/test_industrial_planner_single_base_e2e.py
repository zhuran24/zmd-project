"""Tests for the active IndustrialPlanner single-base end-to-end workflow."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_industrial_planner_full_demand_support_suite_inventory import (
    write_full_demand_support_suite_inventory_outputs,
)
from scripts.run_industrial_planner_single_base_e2e import run_single_base_e2e_workflow
from src.search.exact_campaign import atomic_write_json


_BLUEPRINT_RELATIVE_PATH = "data/examples/industrial_planner/full_demand_recipe_capacity_canonical_blueprint.json"


def _write_support_inventory(tmp_path: Path, output_dir: Path) -> Path:
    inventory_path = tmp_path / "full_demand_support_suite_inventory.json"
    atomic_write_json(
        inventory_path,
        {
            "inventory_version": 1,
            "entries": [
                {
                    "report_set_id": "default_full_demand_support_suite",
                    "blueprint_path": _BLUEPRINT_RELATIVE_PATH,
                    "output_dir": str(output_dir),
                }
            ],
        },
    )
    return inventory_path



def _write_family_inventory(tmp_path: Path, support_inventory_path: Path) -> Path:
    inventory_path = tmp_path / "checked_artifact_family_inventory.json"
    atomic_write_json(
        inventory_path,
        {
            "inventory_version": 1,
            "entries": [
                {
                    "family_id": "full_demand_support_suite",
                    "family_label": "IndustrialPlanner full-demand support report sets",
                    "inventory_path": str(support_inventory_path),
                    "result_builder": (
                        "scripts.audit_industrial_planner_full_demand_support_suite_inventory:"
                        "build_full_demand_support_suite_inventory_result"
                    ),
                    "scope_label_singular": "report set",
                    "checked_scope_count_attr": "checked_report_set_count",
                    "clean_scope_count_attr": "clean_report_set_count",
                }
            ],
        },
    )
    return inventory_path



def test_single_base_e2e_workflow_writes_successful_active_contract_bundle(tmp_path: Path) -> None:
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



def test_single_base_e2e_workflow_fails_closed_on_contract_ceiling_debug_base(tmp_path: Path) -> None:
    run_dir = tmp_path / "single_base_e2e"

    result = run_single_base_e2e_workflow(run_dir=run_dir, base_id="wuling_protocol_core")

    assert result.overall_status == "planning_failed"
    assert result.failure_stage == "planning"
    assert result.failure_classification == "unsupported_by_canonical_contract"
    assert result.deliverable_status == "not_ready"
    assert result.requested_base_is_active_contract is False
    assert result.planning_summary["status"] == "unsupported_by_canonical_contract"
    assert result.export_summary["status"] == "skipped"
    assert result.validation_summary["delivery_validation_status"] == "skipped"
    assert result.throughput_summary["status"] == "skipped"

    assert (run_dir / "canonical" / "full_demand_fixture_plan_report.json").exists()
    assert not (run_dir / "bundle" / "industrial_planner.blueprint.json").exists()
    assert (run_dir / "support_suite" / "full_demand_support_overview.json").exists()

    summary_payload = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary_payload["overall_status"] == "planning_failed"
    assert summary_payload["failure_classification"] == "unsupported_by_canonical_contract"



def test_single_base_e2e_workflow_surfaces_checked_in_support_drift(tmp_path: Path) -> None:
    checked_support_dir = tmp_path / "checked_support"
    support_inventory_path = _write_support_inventory(tmp_path, checked_support_dir)
    family_inventory_path = _write_family_inventory(tmp_path, support_inventory_path)

    write_full_demand_support_suite_inventory_outputs(inventory_path=support_inventory_path)
    (checked_support_dir / "full_demand_support_overview.md").write_text(
        "stale support overview",
        encoding="utf-8",
    )

    run_dir = tmp_path / "single_base_e2e"
    result = run_single_base_e2e_workflow(
        run_dir=run_dir,
        support_inventory_path=support_inventory_path,
        family_inventory_path=family_inventory_path,
    )

    assert result.overall_status == "checked_in_support_drift_detected"
    assert result.failure_stage == "checked_in_support_suite"
    assert result.failure_classification == "support_suite_inventory_drift"
    assert result.deliverable_status == "bundle_ready_repo_reports_drifting"
    assert result.checked_in_support_suite_summary["status"] == "drift_detected"
    assert result.checked_in_support_suite_summary["drift_entry_count"] == 1
    assert result.checked_artifact_suite_summary["status"] == "drift_detected"

    summary_payload = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary_payload["overall_status"] == "checked_in_support_drift_detected"
    assert summary_payload["checked_in_support_suite_inventory"]["status"] == "drift_detected"
    assert summary_payload["checked_artifact_suite"]["status"] == "drift_detected"
