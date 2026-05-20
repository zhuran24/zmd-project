"""Tests for the IndustrialPlanner full-demand base support matrix."""

from __future__ import annotations

from scripts.audit_industrial_planner_full_demand_base_matrix import (
    build_full_demand_base_support_matrix,
)


def test_full_demand_base_support_matrix_defaults_to_single_active_contract_base() -> None:
    report = build_full_demand_base_support_matrix()
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
    assert report.summary["proven_equivalent_base_count"] == 1
    assert report.summary["proven_equivalent_base_ids"] == ["valley4_protocol_core"]
    assert report.summary["infeasible_base_count"] == 0
    assert report.summary["infeasible_base_ids"] == []
    assert report.summary["unsupported_by_canonical_contract_base_count"] == 0
    assert report.summary["unsupported_by_canonical_contract_base_ids"] == []
    assert report.summary["blocking_classification_counts"] == {}

    default_base = entries["valley4_protocol_core"]
    assert default_base.planner_status == "proven_equivalent"
    assert default_base.size_relation_to_canonical == "equal_to_canonical_contract"
    assert default_base.throughput_status == "proven_equivalent"
    assert default_base.validator_import_compatible is True
    assert default_base.validator_layout_healthy is True
    assert dict(default_base.selected_output_edge_counts) == {
        "top": 18,
        "left": 20,
        "bottom": 12,
        "right": 2,
    }

    assert report.scope["scope_mode"] == "default_contract_scope"
    assert report.scope["active_contract_base_ids"] == ["valley4_protocol_core"]
    assert any(
        "intentionally narrowed to the active 70×70 single-base contract" in signal
        for signal in report.decision_signals
    )

    markdown = report.to_markdown()
    assert "IndustrialPlanner Full-Demand Base Support Matrix" in markdown
    assert "Audited bases: `valley4_protocol_core`" in markdown
    assert "Preserved future-scope bases (not audited here): 5" in markdown
    assert "valley4 40×40 sub-bases (3)" in markdown
    assert "The detailed future-scope base inventory remains available in the JSON sidecar" in markdown


def test_full_demand_base_support_matrix_subset_renders_markdown() -> None:
    report = build_full_demand_base_support_matrix(
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
    assert report.summary["proven_equivalent_base_count"] == 1
    assert report.summary["proven_equivalent_base_ids"] == ["valley4_protocol_core"]
    assert report.summary["unsupported_by_canonical_contract_base_count"] == 1
    assert report.summary["unsupported_by_canonical_contract_base_ids"] == ["wuling_protocol_core"]

    markdown = report.to_markdown()
    assert "IndustrialPlanner Full-Demand Base Support Matrix" in markdown
    assert "Audited bases: `valley4_protocol_core`, `wuling_protocol_core`" in markdown
    assert "`valley4_protocol_core`" in markdown
    assert "`wuling_protocol_core`" in markdown
    assert "only audited base blocked purely by the canonical 70×70 edge contract" in markdown
