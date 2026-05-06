from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from src.search.phase3b_direct_equality_core_geometry import (
    build_phase3b_direct_equality_core_geometry_report,
    render_phase3b_direct_equality_core_geometry_markdown,
    render_phase3b_direct_equality_core_geometry_text,
)


def _write_fixture_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "project"
    placements = project / "data" / "preprocessed" / "candidate_placements.json"
    placements.parent.mkdir(parents=True)
    facility_pools = {
        "manufacturing_5x5": [
            {
                "pose_id": "p_x00_y61_o0_m_BT",
                "anchor": {"x": 0, "y": 61},
                "pose_params": {"orientation": 0, "port_mode": "BT"},
                "occupied_cells": [[0, 61], [4, 65]],
                "input_port_cells": [{"x": 0, "y": 60}],
                "output_port_cells": [{"x": 0, "y": 66}],
            },
            {
                "pose_id": "p_x05_y00_o0_m_LR",
                "anchor": {"x": 5, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "LR"},
                "occupied_cells": [[5, 0], [5, 3]],
                "input_port_cells": [{"x": 4, "y": 0}],
                "output_port_cells": [{"x": 10, "y": 0}],
            },
        ]
    }
    placements.write_text(json.dumps({"facility_pools": facility_pools}), encoding="utf-8")

    core = project / ".artifacts" / "core.json"
    core.parent.mkdir(parents=True)
    core.write_text(
        json.dumps(
            {
                "candidate": {
                    "key": "67x13",
                    "anchor_idx": 119,
                    "ghost_rect": {"w": 67, "h": 13, "area": 871},
                },
                "profile": {"group_id": "group::manufacturing_5x5::planter_sandleaf::10"},
                "direct_equality_core": {
                    "remaining_labels": [
                        {
                            "group_id": "group::manufacturing_5x5::planter_sandleaf::10",
                            "solution_id": "planter_sandleaf_013",
                            "slot_index": 12,
                            "template": "manufacturing_5x5",
                            "pose_index": 0,
                            "field": "y",
                            "forced_value": 61,
                            "stable_key": "k0",
                        },
                        {
                            "group_id": "group::manufacturing_5x5::planter_sandleaf::10",
                            "solution_id": "planter_sandleaf_014",
                            "slot_index": 13,
                            "template": "manufacturing_5x5",
                            "pose_index": 1,
                            "field": "mode",
                            "forced_value": 1,
                            "stable_key": "k1",
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    return project, placements, core


def test_direct_equality_core_geometry_marks_partial_field_semantics(tmp_path: Path) -> None:
    project, placements, core = _write_fixture_project(tmp_path)

    report = build_phase3b_direct_equality_core_geometry_report(
        project,
        core_paths=[core],
        candidate_placements_path=placements,
    )

    assert report["metadata"]["source"] == "phase3b_direct_equality_core_geometry_v1"
    assert report["metadata"]["solver_invoked"] is False
    assert report["summary"]["final_key_count"] == 2
    assert report["summary"]["complete_pose_equality_key_count"] == 0
    labels = report["entries"][0]["labels"]
    assert labels[0]["forced_semantics"] == "forces y coordinate only"
    assert labels[1]["forced_semantics"] == "forces orientation/port-mode id only"
    assert labels[1]["source_pose_overlaps_ghost"] is True
    assert labels[1]["stable_key_pose_index_is_provenance_only"] is True
    markdown = render_phase3b_direct_equality_core_geometry_markdown(report)
    text = render_phase3b_direct_equality_core_geometry_text(report)
    assert "Solver invoked: false" in markdown
    assert "semantics=forces orientation/port-mode id only" in text


def test_direct_equality_core_geometry_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project, placements, core = _write_fixture_project(tmp_path)
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_direct_equality_core_geometry.py"
    spec = importlib.util.spec_from_file_location("direct_equality_core_geometry_cli", script)
    assert spec is not None and spec.loader is not None
    cli_module = importlib.util.module_from_spec(spec)
    sys.modules["direct_equality_core_geometry_cli"] = cli_module
    spec.loader.exec_module(cli_module)

    output_dir = tmp_path / "out"
    sys.argv = [
        str(script),
        "--project-root",
        str(project),
        "--candidate-placements",
        str(placements),
        "--core-json",
        str(core),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        "geometry",
        "--no-write",
    ]
    assert cli_module.main() == 0
    assert not output_dir.exists()

    sys.argv = [
        str(script),
        "--project-root",
        str(project),
        "--candidate-placements",
        str(placements),
        "--core-json",
        str(core),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        "geometry",
    ]
    assert cli_module.main() == 0
    assert (output_dir / "geometry.json").exists()
    assert (output_dir / "geometry.md").exists()
    assert (output_dir / "geometry.txt").exists()
