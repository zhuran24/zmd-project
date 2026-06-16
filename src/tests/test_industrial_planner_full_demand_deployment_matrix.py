"""Tests for the IndustrialPlanner full-demand deployment-path matrix."""

from __future__ import annotations

from scripts.audit_industrial_planner_full_demand_deployment_matrix import (
    build_full_demand_deployment_path_matrix,
)



def test_full_demand_deployment_path_matrix_defaults_to_canonical_only_active_scope() -> None:
    report = build_full_demand_deployment_path_matrix()
    entries = {entry.base_id: entry for entry in report.entries}

    assert report.summary["total_base_count"] == 1
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
    assert report.summary["best_available_canonical_contract_ceiling_base_count"] == 0
    assert report.summary["best_available_canonical_contract_ceiling_base_ids"] == []
    assert report.summary["future_scope_outer_path_base_count"] == 1
    assert report.summary["best_available_path_counts"] == {"canonical_contract": 1}
    assert report.summary["best_available_blocking_classification_counts"] == {}

    default_base = entries["valley4_protocol_core"]
    assert default_base.canonical_path.planner_status == "proven_equivalent"
    assert default_base.outer_path.applicable is False
    assert default_base.outer_path.path_status == "future_scope"
    assert default_base.outer_path.applicability_reason == "outer_deployment_deactivated_from_active_contract"
    assert default_base.best_available_path_id == "canonical_contract"
    assert default_base.best_available_status == "proven_equivalent"
    assert default_base.unlocked_by_outer_path is False

    assert any(
        "preserved as `future_scope`" in signal
        for signal in report.decision_signals
    )

    markdown = report.to_markdown()
    assert "IndustrialPlanner Full-Demand Deployment Path Matrix" in markdown
    assert "Audited bases: `valley4_protocol_core`" in markdown
    assert "Outer-path rows preserved as future-scope (not evaluated): 1" in markdown
    assert "`future_scope`" in markdown
    assert "valley4 40×40 sub-bases (3)" in markdown



def test_full_demand_deployment_path_matrix_subset_renders_markdown() -> None:
    report = build_full_demand_deployment_path_matrix(
        base_ids=("valley4_protocol_core", "wuling_protocol_core"),
    )

    assert [entry.base_id for entry in report.entries] == [
        "valley4_protocol_core",
        "wuling_protocol_core",
    ]
    assert report.summary["total_base_count"] == 2
    assert report.summary["audited_base_ids"] == [
        "valley4_protocol_core",
        "wuling_protocol_core",
    ]
    assert report.summary["future_scope_base_count"] == 0
    assert report.summary["future_scope_base_ids"] == []
    assert report.summary["canonical_path_proven_equivalent_base_count"] == 1
    assert report.summary["canonical_path_proven_equivalent_base_ids"] == ["valley4_protocol_core"]
    assert report.summary["best_available_proven_equivalent_base_count"] == 1
    assert report.summary["best_available_proven_equivalent_base_ids"] == ["valley4_protocol_core"]
    assert report.summary["additional_bases_unlocked_by_outer_path_base_count"] == 0
    assert report.summary["additional_bases_unlocked_by_outer_path_base_ids"] == []
    assert report.summary["future_scope_outer_path_base_count"] == 2

    markdown = report.to_markdown()
    assert "IndustrialPlanner Full-Demand Deployment Path Matrix" in markdown
    assert "Audited bases: `valley4_protocol_core`, `wuling_protocol_core`" in markdown
    assert "`valley4_protocol_core`" in markdown
    assert "`wuling_protocol_core`" in markdown
    assert "Outer-path rows preserved as future-scope (not evaluated): 2" in markdown
    assert "`unsupported_by_canonical_contract`" in markdown
    assert "`future_scope`" in markdown
