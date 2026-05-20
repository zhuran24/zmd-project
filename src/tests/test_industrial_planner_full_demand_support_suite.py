"""Tests for the IndustrialPlanner full-demand support-suite workflow."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from scripts.audit_industrial_planner_full_demand_support_suite import (
    build_full_demand_support_overview,
    check_full_demand_support_suite_outputs,
    main,
    write_full_demand_support_suite_outputs,
)


def test_full_demand_support_overview_defaults_to_single_active_base() -> None:
    report = build_full_demand_support_overview()
    entries = {entry.base_id: entry for entry in report.entries}

    assert report.summary["total_base_count"] == 1
    assert report.summary["scope_mode"] == "default_contract_scope"
    assert report.summary["audited_base_ids"] == ["valley4_protocol_core"]
    assert report.summary["future_scope_base_count"] == 5
    assert report.summary["future_scope_base_ids"] == [
        "valley4_infra_outpost",
        "valley4_rebuilt_command",
        "valley4_refugee_shelter",
        "wuling_protocol_core",
        "wuling_tianwangping_aid",
    ]
    assert report.summary["canonical_path_proven_equivalent_base_count"] == 1
    assert report.summary["canonical_path_proven_equivalent_base_ids"] == ["valley4_protocol_core"]
    assert report.summary["best_available_proven_equivalent_base_count"] == 1
    assert report.summary["best_available_proven_equivalent_base_ids"] == ["valley4_protocol_core"]
    assert report.summary["additional_bases_unlocked_by_outer_path_base_count"] == 0
    assert report.summary["additional_bases_unlocked_by_outer_path_base_ids"] == []
    assert report.summary["status_transition_base_count"] == 0
    assert report.summary["status_transition_base_ids"] == []
    assert report.summary["canonical_contract_ceiling_base_count"] == 0
    assert report.summary["best_available_canonical_contract_ceiling_base_count"] == 0
    assert report.summary["manufacturing_area_shortfall_base_count"] == 0
    assert report.summary["status_transition_counts"] == {}
    assert report.summary["best_available_path_counts"] == {
        "canonical_contract": 1,
    }
    assert report.summary["unlocked_base_ids"] == []
    assert report.summary["future_scope_outer_path_base_count"] == 1

    default_base = entries["valley4_protocol_core"]
    assert default_base.status_transition == "unchanged"
    assert default_base.outer_path_applicable is False
    assert default_base.outer_path_status == "future_scope"
    assert default_base.best_available_path_id == "canonical_contract"
    assert default_base.best_available_status == "proven_equivalent"
    assert default_base.unlocked_by_outer_path is False

    assert report.scope["scope_mode"] == "default_contract_scope"
    assert report.scope["active_contract_base_ids"] == ["valley4_protocol_core"]
    markdown = report.to_markdown()
    assert "IndustrialPlanner Full-Demand Support Overview" in markdown
    assert "Audited bases: `valley4_protocol_core`" in markdown
    assert "Outer-path rows preserved as future-scope (not evaluated): 1" in markdown
    assert "No active checked-in status transitions remain" in markdown
    assert "valley4 40×40 sub-bases (3)" in markdown



def test_full_demand_support_suite_writer_emits_all_companion_reports(tmp_path: Path) -> None:
    report = build_full_demand_support_overview()

    paths = write_full_demand_support_suite_outputs(
        output_dir=tmp_path / "industrial_planner_support_suite",
        report=report,
    )

    assert set(paths.keys()) == {
        "canonical_matrix_json",
        "canonical_matrix_markdown",
        "deployment_matrix_json",
        "deployment_matrix_markdown",
        "overview_json",
        "overview_markdown",
    }
    for output_path in paths.values():
        assert output_path.exists()

    canonical_payload = json.loads(paths["canonical_matrix_json"].read_text(encoding="utf-8"))
    deployment_payload = json.loads(paths["deployment_matrix_json"].read_text(encoding="utf-8"))
    overview_payload = json.loads(paths["overview_json"].read_text(encoding="utf-8"))

    assert canonical_payload["summary"]["total_base_count"] == 1
    assert canonical_payload["summary"]["audited_base_ids"] == ["valley4_protocol_core"]
    assert canonical_payload["summary"]["future_scope_base_count"] == 5
    assert deployment_payload["summary"]["best_available_proven_equivalent_base_count"] == 1
    assert deployment_payload["summary"]["best_available_proven_equivalent_base_ids"] == [
        "valley4_protocol_core"
    ]
    assert deployment_payload["summary"]["future_scope_outer_path_base_count"] == 1
    assert overview_payload["summary"]["status_transition_base_count"] == 0
    assert overview_payload["summary"]["status_transition_base_ids"] == []
    assert overview_payload["summary"]["unlocked_base_ids"] == []
    assert overview_payload["scope"]["scope_mode"] == "default_contract_scope"

    assert "IndustrialPlanner Full-Demand Base Support Matrix" in paths["canonical_matrix_markdown"].read_text(
        encoding="utf-8"
    )
    assert "IndustrialPlanner Full-Demand Deployment Path Matrix" in paths[
        "deployment_matrix_markdown"
    ].read_text(encoding="utf-8")
    assert "IndustrialPlanner Full-Demand Support Overview" in paths["overview_markdown"].read_text(
        encoding="utf-8"
    )



def test_full_demand_support_suite_check_detects_missing_and_stale_reports(tmp_path: Path) -> None:
    report = build_full_demand_support_overview()
    output_dir = tmp_path / "industrial_planner_support_suite"
    write_full_demand_support_suite_outputs(output_dir=output_dir, report=report)

    clean_result = check_full_demand_support_suite_outputs(
        output_dir=output_dir,
        report=report,
    )
    assert clean_result.is_clean is True
    assert clean_result.checked_file_count == 6
    assert clean_result.drift_entries == ()
    assert "is in sync" in clean_result.to_console_text()

    (output_dir / "full_demand_support_overview.md").write_text("stale overview", encoding="utf-8")
    (output_dir / "full_demand_base_support_matrix.json").unlink()

    drift_result = check_full_demand_support_suite_outputs(
        output_dir=output_dir,
        report=report,
    )
    assert drift_result.is_clean is False
    assert drift_result.checked_file_count == 6
    assert {(entry.filename, entry.drift_kind) for entry in drift_result.drift_entries} == {
        ("full_demand_base_support_matrix.json", "missing"),
        ("full_demand_support_overview.md", "content_mismatch"),
    }

    console_text = drift_result.to_console_text()
    assert "drift detected" in console_text
    assert "missing: full_demand_base_support_matrix.json" in console_text
    assert "content_mismatch: full_demand_support_overview.md" in console_text
    assert "audit_industrial_planner_full_demand_support_suite.py --output-dir" in console_text



def test_full_demand_support_suite_main_check_mode_exits_nonzero_on_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = build_full_demand_support_overview()
    output_dir = tmp_path / "industrial_planner_support_suite"
    write_full_demand_support_suite_outputs(output_dir=output_dir, report=report)
    (output_dir / "full_demand_support_overview.md").write_text("drift", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_industrial_planner_full_demand_support_suite.py",
            "--output-dir",
            str(output_dir),
            "--check",
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    assert "drift detected" in capsys.readouterr().out
