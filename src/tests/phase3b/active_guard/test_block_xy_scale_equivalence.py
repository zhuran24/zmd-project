from __future__ import annotations

from pathlib import Path

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.active_guard.block_xy_scale_equivalence import (
    build_phase3b_active_guard_block_xy_scale_equivalence,
    render_phase3b_active_guard_block_xy_scale_equivalence_markdown,
    render_phase3b_active_guard_block_xy_scale_equivalence_text,
)


def test_active_guard_block_xy_scale_marks_direct_guarded_geometry_too_large(
    tmp_path: Path,
) -> None:
    proto_path = tmp_path / "proto.json"
    residual_path = tmp_path / "residual.json"
    atomic_write_json(
        proto_path,
        {
            "active_guard_shape": {
                "independent_expected": {
                    "block_size": 64,
                    "pole_slot_count": 10,
                    "powered_slot_count": 2,
                    "padded_pole_position_count": 16,
                    "powered_slot_counts": {"protocol_storage_box": 2},
                    "template_counts": {"protocol_storage_box": 32},
                }
            },
            "witness_stats": {
                "block_intermediate_target_channel_count": 8,
                "block_element_constraint_count": 8,
                "block_selected_geometry_constraint_count": 16,
                "block_active_guard_clause_count": 32,
                "local_selected_literal_count": 128,
                "block_selected_literal_count": 4,
            },
        },
    )
    atomic_write_json(
        residual_path,
        {
            "protocol_surface": {
                "block_xy_surface": {
                    "block_xy_constraint_count": 8,
                    "block_x_constraint_count": 4,
                    "block_y_constraint_count": 4,
                }
            }
        },
    )

    report = build_phase3b_active_guard_block_xy_scale_equivalence(
        tmp_path,
        proto_shape_audit_path=proto_path,
        residual_surface_path=residual_path,
    )

    direct = report["candidate_estimates"]["direct_guarded_geometry"]
    assert report["status"]["outcome"] == "active_guard_block_xy_scale_equivalence_estimated"
    assert report["metadata"]["solver_invoked"] is False
    assert report["baseline"]["relation_row_count"] == 32
    assert direct["constraints_added"] == 128
    assert direct["constraints_removed"] == 24
    assert direct["net_constraint_delta"] == 104
    assert direct["risk"] == "too_large"
    assert report["recommendation"]["classification"] == "direct_guarded_geometry_too_large"
    assert "padding_identity_preserved" in report["equivalence_gates"]
    assert "ActiveGuard Block XY" in render_phase3b_active_guard_block_xy_scale_equivalence_markdown(report)
    assert "direct_guarded_geometry_net_constraint_delta=104" in render_phase3b_active_guard_block_xy_scale_equivalence_text(report)


def test_active_guard_block_xy_scale_handles_missing_inputs(tmp_path: Path) -> None:
    report = build_phase3b_active_guard_block_xy_scale_equivalence(
        tmp_path,
        proto_shape_audit_path=tmp_path / "missing_proto.json",
        residual_surface_path=tmp_path / "missing_residual.json",
    )

    assert report["status"]["outcome"] == "active_guard_block_xy_scale_equivalence_incomplete"
    assert report["checks"][2]["status"] == "fail"


def test_active_guard_block_xy_scale_cli_surface_mentions_outputs() -> None:
    script = (
        Path(__file__).resolve().parents[4]
        / "scripts" / "phase3b" / "active_guard" / "build_block_xy_scale_equivalence.py"
    ).read_text(encoding="utf-8")

    assert "active_guard_block_xy_scale_equivalence.json" in script
    assert "--no-write" in script
