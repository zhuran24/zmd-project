from __future__ import annotations

from pathlib import Path

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_grouped_xy_probe_synthesis import (
    build_phase3b_grouped_xy_probe_synthesis,
    render_phase3b_grouped_xy_probe_synthesis_markdown,
    render_phase3b_grouped_xy_probe_synthesis_text,
)


def test_grouped_xy_probe_synthesis_records_anchor118_terminal_not_reproduced(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)

    report = build_phase3b_grouped_xy_probe_synthesis(
        tmp_path,
        profile_audit_path=paths["profile"],
        grouped_probe_paths=[paths["grouped"]],
        comparator_probe_paths=[paths["active"]],
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == (
        "grouped_xy_search_progress_but_anchor118_terminal_not_reproduced"
    )
    assert report["comparison"]["grouped_has_search_progress"] is True
    assert report["comparison"]["anchor118_terminal_not_reproduced"] is True
    assert "Grouped XY Probe Synthesis" in render_phase3b_grouped_xy_probe_synthesis_markdown(report)
    assert "anchor118_terminal_not_reproduced=True" in render_phase3b_grouped_xy_probe_synthesis_text(report)


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "profile": tmp_path / "profile.json",
        "grouped": tmp_path / "grouped.json",
        "active": tmp_path / "active.json",
    }
    atomic_write_json(
        paths["profile"],
        {
            "comparison": {
                "grouped_xy_profile_valid": True,
                "block_xy_target_delta": -4,
                "block_element_constraint_delta": -4,
                "selected_geometry_constraint_delta": -8,
                "no_pairwise_cover_literals": True,
            }
        },
    )
    atomic_write_json(
        paths["grouped"],
        {
            "reduction": {
                "entries": [
                    {
                        "anchor_idx": 118,
                        "status": "UNKNOWN",
                        "branches": 12,
                        "conflicts": 3,
                        "wall_time": 120.0,
                        "deterministic_time": 4.0,
                        "response_stats_parsed": {"booleans": 100},
                    }
                ]
            }
        },
    )
    atomic_write_json(
        paths["active"],
        {
            "reduction": {
                "entries": [
                    {
                        "anchor_idx": 118,
                        "status": "INFEASIBLE",
                        "branches": 2,
                        "conflicts": 1,
                        "wall_time": 30.0,
                        "deterministic_time": 2.0,
                        "response_stats_parsed": {"booleans": 50},
                    }
                ]
            }
        },
    )
    return paths
