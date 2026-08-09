from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from ortools.sat.python import cp_model

import src.search.phase3b.coordinate_validation.capacity_cut_design as design_module
from src.search.phase3b.coordinate_validation.capacity_cut_design import (
    build_phase3b_coordinate_validation_capacity_cut_design,
    render_phase3b_coordinate_validation_capacity_cut_design_markdown,
    render_phase3b_coordinate_validation_capacity_cut_design_text,
)


class _Slot:
    def __init__(self, *, x: Any, y: Any, mode: Any, idx: int) -> None:
        self.x = x
        self.y = y
        self.mode = mode
        self.dims = (2, 2)
        self.template = "alpha"
        self.use_domain_table = False
        self.allowed_tuples = ()
        self.key = f"group::alpha::op::0::slot::{idx}"


class _Delegate:
    grid_w = 5
    grid_h = 5

    def __init__(self, model: cp_model.CpModel) -> None:
        slots = []
        for idx in range(2):
            x = model.NewIntVar(0, 3, f"x__group::alpha::op::0::slot::{idx}")
            y = model.NewIntVar(0, 3, f"y__group::alpha::op::0::slot::{idx}")
            mode = model.NewIntVar(0, 0, f"mode__group::alpha::op::0::slot::{idx}")
            slots.append(_Slot(x=x, y=y, mode=mode, idx=idx))
        self.mandatory_slots = {"group::alpha::op::0": slots}
        self._template_pose_tuple_by_idx = {"alpha": {1: (0, 0, 0), 2: (0, 2, 0)}}

    def _slot_order_key_bounds(self, slot: _Slot) -> tuple[int, int]:
        del slot
        return (5, 1)


class _Model:
    def __init__(self) -> None:
        self.model = cp_model.CpModel()
        self._coordinate_delegate = _Delegate(self.model)
        self.ghost_rect = (2, 2)
        self._ghost_domains = [
            {"anchor": {"x": 0, "y": 0}, "cells": []},
            {"anchor": {"x": 3, "y": 3}, "cells": []},
        ]


def _fake_context() -> dict[str, Any]:
    group = {
        "group_id": "group::alpha::op::0",
        "facility_type": "alpha",
        "operation_type": "op",
        "count": 2,
        "instance_ids": ["alpha_001", "alpha_002"],
    }
    return {
        "model": _Model(),
        "ordered_groups": [group],
        "candidates_by_group": {"group::alpha::op::0": [1, 2]},
        "ghost_anchor_count": 2,
        "blocked_cell_count": 0,
        "ordered_group_count": 1,
    }


def _core_json(path: Path) -> Path:
    payload = {
        "direct_equality_core": {
            "remaining_labels": [
                {
                    "stable_key": "k1",
                    "group_id": "group::alpha::op::0",
                    "solution_id": "alpha_001",
                    "slot_key": "0",
                    "slot_index": 0,
                    "template": "alpha",
                    "pose_index": 1,
                    "field": "x",
                    "forced_value": 0,
                },
                {
                    "stable_key": "k2",
                    "group_id": "group::alpha::op::0",
                    "solution_id": "alpha_002",
                    "slot_key": "1",
                    "slot_index": 1,
                    "template": "alpha",
                    "pose_index": 2,
                    "field": "x",
                    "forced_value": 0,
                },
            ]
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_capacity_cut_design_identifies_fixed_anchor_threshold(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        design_module,
        "_build_delta_context",
        lambda *args, **kwargs: _fake_context(),
    )
    monkeypatch.setattr(
        design_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_capacity_cut_design(
        tmp_path / "project",
        group_id="group::alpha::op::0",
        anchor_idx=0,
        core_json=_core_json(tmp_path / "core.json"),
        time_limit_seconds=0.2,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_capacity_cut_design_v1"
    )
    assert report["thresholds"]["pure_aggregate_height_threshold_k"] == 2
    assert report["thresholds"]["fixed_anchor_infeasible_threshold_k"] == 2
    assert report["subset_probe"]["minimal_infeasible_k"] == 2
    assert report["subset_probe"]["entries"][0]["status"] == "OPTIMAL"
    assert report["subset_probe"]["entries"][1]["status"] == "INFEASIBLE"
    markdown = render_phase3b_coordinate_validation_capacity_cut_design_markdown(report)
    text = render_phase3b_coordinate_validation_capacity_cut_design_text(report)
    assert "Cut Proposal" in markdown
    assert "minimal_infeasible_k=2" in text


def test_capacity_cut_design_cli_writes_and_no_write_skips_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "coordinate_validation" / "build_capacity_cut_design.py"
    spec = importlib.util.spec_from_file_location("capacity_cut_design_cli", script)
    assert spec is not None and spec.loader is not None
    cli_module = importlib.util.module_from_spec(spec)
    sys.modules["capacity_cut_design_cli"] = cli_module
    spec.loader.exec_module(cli_module)

    fake_report = {
        "metadata": {"source": "phase3b_coordinate_validation_capacity_cut_design_v1"},
        "status": {"outcome": "minimal_aggregate_subset_found", "recommendation": "ok"},
        "thresholds": {
            "pure_aggregate_height_threshold_k": 12,
            "fixed_anchor_infeasible_threshold_k": 11,
        },
        "subset_probe": {
            "minimal_infeasible_k": 11,
            "status_counts": {"OPTIMAL": 10, "INFEASIBLE": 2},
            "entries": [],
        },
        "geometry": {},
        "cut_design": {},
        "checks": [],
    }
    monkeypatch.setattr(
        cli_module,
        "build_phase3b_coordinate_validation_capacity_cut_design",
        lambda *args, **kwargs: fake_report,
    )

    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--project-root",
            str(tmp_path / "project"),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "design_smoke",
            "--no-write",
        ],
    )
    assert cli_module.main() == 0
    assert not output_dir.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--project-root",
            str(tmp_path / "project"),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "design_smoke",
        ],
    )
    assert cli_module.main() == 0
    payload = json.loads((output_dir / "design_smoke.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_capacity_cut_design_v1"
    )
    assert (output_dir / "design_smoke.md").exists()
    assert (output_dir / "design_smoke.txt").exists()
