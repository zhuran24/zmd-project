from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.models.master_model import MasterPlacementModel
from src.search.phase3b.pose_order.pose_order_validation_probe import (
    build_phase3b_pose_order_validation_probe,
    render_phase3b_pose_order_validation_probe_markdown,
    render_phase3b_pose_order_validation_probe_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_toy_exact_project(project_root: Path) -> Path:
    _write_json(
        project_root / "rules" / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 4, "height": 1}},
            "facility_templates": {
                "alpha": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "beta": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    _write_json(
        project_root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "alpha": [
                    {
                        "pose_id": "alpha_0",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    },
                    {
                        "pose_id": "alpha_1",
                        "anchor": {"x": 1, "y": 0},
                        "occupied_cells": [[1, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    },
                ],
                "beta": [
                    {
                        "pose_id": "beta_2",
                        "anchor": {"x": 2, "y": 0},
                        "occupied_cells": [[2, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    },
                    {
                        "pose_id": "beta_3",
                        "anchor": {"x": 3, "y": 0},
                        "occupied_cells": [[3, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    },
                ],
            }
        },
    )
    _write_json(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "alpha_001",
                "facility_type": "alpha",
                "operation_type": "alpha_op",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            },
            {
                "instance_id": "beta_001",
                "facility_type": "beta",
                "operation_type": "beta_op",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            },
        ],
    )
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def test_pose_order_validation_probe_finds_first_infeasible_prefix(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "project")

    def _fake_validation(
        self,
        *,
        solution_hint,
        ghost_anchor_hint_idx,
        time_limit_seconds,
        require_complete=True,
    ):
        rejected = len(dict(solution_hint)) >= 2
        return {
            "attempted": True,
            "status": "INFEASIBLE" if rejected else "OPTIMAL",
            "accepted": not rejected,
            "reason": "infeasible" if rejected else "feasible",
            "forced_slot_field_count": 3 * len(dict(solution_hint)),
            "forced_ghost_anchor": ghost_anchor_hint_idx is not None,
            "require_complete": bool(require_complete),
            "wall_time": 0.01,
            "branches": 0,
            "conflicts": 0,
        }

    monkeypatch.setattr(
        MasterPlacementModel,
        "_validate_coordinate_forced_hint",
        _fake_validation,
    )

    report = build_phase3b_pose_order_validation_probe(
        project_root,
        candidate="1x1",
        anchor_idx=3,
        ordering="y_then_x",
    )

    prefix = report["diagnostics"]["prefix_probe"]
    assert report["metadata"]["source"] == "phase3b_pose_order_validation_probe_v1"
    assert report["status"]["outcome"] == "prefix_infeasible"
    assert prefix["first_infeasible_prefix_group_count"] == 2
    assert prefix["first_infeasible_group"]["group_id"] == "group::beta::beta_op::1"
    assert prefix["prefix_results"][0]["validation"]["accepted"] is True
    assert prefix["prefix_results"][1]["validation"]["status"] == "INFEASIBLE"

    markdown = render_phase3b_pose_order_validation_probe_markdown(report)
    text = render_phase3b_pose_order_validation_probe_text(report)
    assert "Phase 3B Pose-Order Validation Probe" in markdown
    assert "group::beta::beta_op::1" in markdown
    assert "first_infeasible_prefix_group_count=2" in text
    assert "prefix_result=prefix=2" in text


def test_pose_order_validation_probe_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "project")
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "pose_order" / "build_pose_order_validation_probe.py"
    output_dir = tmp_path / "out"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--candidate",
            "1x1",
            "--anchor-index",
            "3",
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b pose-order validation probe" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--candidate",
            "1x1",
            "--anchor-index",
            "3",
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "pose_order_validation_probe_json=" in write.stdout
    payload = json.loads(
        (
            output_dir
            / "pose_order_validation_probe_1x1_anchor3_y_then_x.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["candidate"]["key"] == "1x1"
    assert payload["candidate"]["anchor_idx"] == 3
    assert (output_dir / "pose_order_validation_probe_1x1_anchor3_y_then_x.md").exists()
    assert (output_dir / "pose_order_validation_probe_1x1_anchor3_y_then_x.txt").exists()
