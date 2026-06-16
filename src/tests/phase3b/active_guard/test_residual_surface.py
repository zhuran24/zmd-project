from __future__ import annotations

import json
from pathlib import Path

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.active_guard.residual_surface import (
    build_phase3b_active_guard_residual_surface,
    render_phase3b_active_guard_residual_surface_markdown,
    render_phase3b_active_guard_residual_surface_text,
)


def test_active_guard_residual_surface_classifies_stable_search_with_family_bound(
    tmp_path: Path,
) -> None:
    protocol_path = tmp_path / "protocol.json"
    family_path = tmp_path / "family.json"
    probe_path = tmp_path / "probe.json"
    atomic_write_json(
        protocol_path,
        {
            "metadata": {"solver_invoked": False},
            "summary": {
                "evaluated": True,
                "diagnostic_signal": "no_new_divergence_detected",
                "next_probe_hint": "inspect family-bound deltas",
                "mapped_protocol_slot_count": 544,
                "mapping_matches_artifact_counts": False,
                "family_bounds_present": True,
            },
            "target_channel_map": {
                "by_target_token": {
                    "active_x": {"constraint_count": 6528, "unique_slot_count": 544},
                    "active_y": {"constraint_count": 6528, "unique_slot_count": 544},
                    "active_xy": {"constraint_count": 13056, "unique_slot_count": 544},
                }
            },
            "family_bounds": {
                "125": {
                    "family_009": {
                        "family_name": "family_009",
                        "implied_upper_when_anchor_active": 547,
                        "family_domain_upper": 612,
                        "upper_reduction_when_anchor_active": 65,
                    }
                }
            },
            "comparison": {"mapping_matches_artifact_counts": False},
        },
    )
    atomic_write_json(
        family_path,
        {
            "summary": {"all_bounds_consistent": True},
            "status": {"outcome": "family_bound_derivation_consistent"},
            "audits": [
                {
                    "anchor_idx": 119,
                    "target_power_family": "family_009",
                    "present": True,
                    "derivation": {
                        "global_upper_bound": 612,
                        "derived_conditioned_upper_bound": 526,
                        "domain_conditioned_upper_bound": 526,
                        "blocked_family_pose_count": 86,
                        "available_family_pose_count": 526,
                    },
                    "proto_constraint": {
                        "matching_constraint_count": 1,
                        "implied_conditioned_upper_bound": 526,
                    },
                    "bounds_consistent": True,
                    "finding": "target_family_bound_derivation_consistent",
                }
            ],
        },
    )
    atomic_write_json(
        probe_path,
        {
            "campaign_state_unchanged": True,
            "reduction": {
                "entries": [
                    {
                        "anchor_idx": 119,
                        "status": "UNKNOWN",
                        "branches": 84,
                        "conflicts": 22,
                        "deterministic_time": 51.3,
                        "solver_parameter_profile": {"random_seed": 2},
                    }
                ]
            },
        },
    )

    report = build_phase3b_active_guard_residual_surface(
        tmp_path,
        protocol_audit_path=protocol_path,
        family_bound_audit_path=family_path,
        active_guard_probe_paths=[probe_path],
    )

    assert report["status"]["outcome"] == "active_guard_residual_surface_synthesized"
    assert report["metadata"]["solver_invoked"] is False
    assert report["active_guard_probe_summary"]["all_unknown_with_search_progress"] is True
    assert report["active_guard_probe_summary"]["zero_branch_unknown_count"] == 0
    assert report["protocol_surface"]["family_bound_source"] == "family_bound_audit"
    assert report["protocol_surface"]["family_bound_audit_all_bounds_consistent"] is True
    assert report["protocol_surface"]["family_bound_focus"]["119"]["upper_reduction_when_anchor_active"] == 86
    assert report["relationship"]["classification"] == (
        "stable_search_progress_with_family009_bound_and_surviving_block_xy_surface"
    )
    assert report["relationship"]["direct_proto_edge"] is False
    assert report["relationship"]["shared_power_pole_slot_surface"] is True
    assert report["relationship"]["missing_family_bound_anchors"] == []
    assert "family009" in report["relationship"]["recommended_next_action"]
    assert "ActiveGuard Residual Surface" in render_phase3b_active_guard_residual_surface_markdown(report)
    assert "block_xy_constraint_count=13056" in render_phase3b_active_guard_residual_surface_text(report)
    assert "direct_proto_edge=False" in render_phase3b_active_guard_residual_surface_text(report)


def test_active_guard_residual_surface_handles_missing_inputs(tmp_path: Path) -> None:
    report = build_phase3b_active_guard_residual_surface(
        tmp_path,
        protocol_audit_path=tmp_path / "missing_protocol.json",
        family_bound_audit_path=tmp_path / "missing_family.json",
        active_guard_probe_paths=[tmp_path / "missing_probe.json"],
    )

    assert report["status"]["outcome"] == "active_guard_residual_surface_incomplete"
    assert report["checks"][2]["status"] == "fail"


def test_active_guard_residual_surface_cli_surface_mentions_output() -> None:
    script = (
        Path(__file__).resolve().parents[4]
        / "scripts" / "phase3b" / "active_guard" / "build_residual_surface.py"
    ).read_text(encoding="utf-8")

    assert "active_guard_residual_surface.json" in script
    assert "--no-write" in script
    assert "--family-bound-audit" in script
