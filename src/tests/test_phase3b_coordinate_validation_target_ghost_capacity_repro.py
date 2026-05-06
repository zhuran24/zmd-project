from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest
from ortools.sat.python import cp_model

import src.search.phase3b_coordinate_validation_target_ghost_capacity_repro as repro_module
from src.search.phase3b_coordinate_validation_target_ghost_capacity_repro import (
    build_phase3b_coordinate_validation_target_ghost_capacity_repro,
    render_phase3b_coordinate_validation_target_ghost_capacity_repro_markdown,
    render_phase3b_coordinate_validation_target_ghost_capacity_repro_text,
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


def test_target_ghost_capacity_repro_aggregates_variants(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        repro_module,
        "_build_delta_context",
        lambda *args, **kwargs: _fake_context(),
    )
    monkeypatch.setattr(
        repro_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_target_ghost_capacity_repro(
        tmp_path / "project",
        group_id="group::alpha::op::0",
        anchor_idx=0,
        core_json=_core_json(tmp_path / "core.json"),
        variants=(
            "target_group_only_no_overlap",
            "target_slots_12_core_only_without_ghost",
            "target_slots_12_core_only_plus_anchor119_ghost",
            "unsupported_variant",
        ),
        time_limit_seconds=0.2,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_target_ghost_capacity_repro_v1"
    )
    assert report["geometry"]["target_group"]["slot_count"] == 2
    assert report["repro"]["entries"][0]["target_slot_count"] == 2
    assert report["repro"]["entries"][-1]["status"] == "SKIPPED"
    assert report["repro"]["status_counts"]["SKIPPED"] == 1
    markdown = render_phase3b_coordinate_validation_target_ghost_capacity_repro_markdown(report)
    text = render_phase3b_coordinate_validation_target_ghost_capacity_repro_text(report)
    assert "Variant Matrix" in markdown
    assert "status_counts=" in text


def test_target_ghost_capacity_repro_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_coordinate_validation_target_ghost_capacity_repro.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--time-limit-seconds",
            "0",
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate validation target+ghost capacity repro" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--time-limit-seconds",
            "0",
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "target_ghost_smoke",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_validation_target_ghost_capacity_repro_json=" in write.stdout
    payload = json.loads((output_dir / "target_ghost_smoke.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_target_ghost_capacity_repro_v1"
    )
    assert (output_dir / "target_ghost_smoke.md").exists()
    assert (output_dir / "target_ghost_smoke.txt").exists()
