from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest
from ortools.sat.python import cp_model

import src.search.phase3b_coordinate_validation_no_overlap_subset_delta as delta_module
from src.models.master_model import _clone_model_proto
from src.search.phase3b_coordinate_validation_no_overlap_subset_delta import (
    _apply_no_overlap_subset_variant_selector,
    _no_overlap_inventory,
    build_phase3b_coordinate_validation_no_overlap_subset_delta,
    render_phase3b_coordinate_validation_no_overlap_subset_delta_markdown,
    render_phase3b_coordinate_validation_no_overlap_subset_delta_text,
)


class _Slot:
    def __init__(self, *, x: Any, y: Any, mode: Any) -> None:
        self.x = x
        self.y = y
        self.mode = mode


class _Delegate:
    def __init__(self, model: cp_model.CpModel) -> None:
        target_x = model.NewIntVar(0, 0, "x__group::alpha::op::0::slot::0")
        target_y = model.NewIntVar(0, 0, "y__group::alpha::op::0::slot::0")
        target_mode = model.NewIntVar(0, 0, "mode__group::alpha::op::0::slot::0")
        other_x = model.NewIntVar(0, 0, "x__group::beta::op::1::slot::0")
        other_y = model.NewIntVar(0, 0, "y__group::beta::op::1::slot::0")
        target_x_end = model.NewIntVar(1, 1, "x_end__group::alpha::op::0::slot::0")
        target_y_end = model.NewIntVar(1, 1, "y_end__group::alpha::op::0::slot::0")
        other_x_end = model.NewIntVar(1, 1, "x_end__group::beta::op::1::slot::0")
        other_y_end = model.NewIntVar(1, 1, "y_end__group::beta::op::1::slot::0")
        target_x_iv = model.NewIntervalVar(
            target_x,
            1,
            target_x_end,
            "x_iv__group::alpha::op::0::slot::0",
        )
        target_y_iv = model.NewIntervalVar(
            target_y,
            1,
            target_y_end,
            "y_iv__group::alpha::op::0::slot::0",
        )
        other_x_iv = model.NewIntervalVar(
            other_x,
            1,
            other_x_end,
            "x_iv__group::beta::op::1::slot::0",
        )
        other_y_iv = model.NewIntervalVar(
            other_y,
            1,
            other_y_end,
            "y_iv__group::beta::op::1::slot::0",
        )
        model.AddNoOverlap2D([target_x_iv, other_x_iv], [target_y_iv, other_y_iv])
        self.mandatory_slots = {"group::alpha::op::0": [_Slot(x=target_x, y=target_y, mode=target_mode)]}


class _Model:
    def __init__(self) -> None:
        self.model = cp_model.CpModel()
        self._coordinate_delegate = _Delegate(self.model)


def _fake_context() -> dict[str, Any]:
    group = {
        "group_id": "group::alpha::op::0",
        "facility_type": "alpha",
        "operation_type": "op",
        "count": 1,
        "instance_ids": ["alpha_001"],
    }
    return {
        "model": _Model(),
        "ordered_groups": [group],
        "candidates_by_group": {"group::alpha::op::0": [1]},
        "ghost_anchor_count": 1,
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
                }
            ]
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_no_overlap_inventory_classifies_owner_buckets() -> None:
    model = _Model()
    proto = _clone_model_proto(model.model.Proto())

    inventory = _no_overlap_inventory(proto, group_id="group::alpha::op::0")

    assert inventory["no_overlap_constraint_count"] == 1
    assert inventory["owner_bucket_counts"] == {
        "mandatory_target_group": 1,
        "other_mandatory": 1,
    }
    assert inventory["constraints"][0]["no_overlap_kind"] == "core_only"


def test_no_overlap_selector_removes_interval_subset_and_reports_skip() -> None:
    model = _Model()
    proto = _clone_model_proto(model.model.Proto())

    summary = _apply_no_overlap_subset_variant_selector(
        proto,
        variant="remove_target_group_intervals_from_no_overlap",
        group_id="group::alpha::op::0",
    )

    assert summary["skipped"] is False
    assert summary["modified_no_overlap_constraint_count"] == 1
    assert summary["removed_interval_pair_count"] == 1
    assert summary["removed_owner_bucket_counts"] == {"mandatory_target_group": 1}

    skipped = _apply_no_overlap_subset_variant_selector(
        proto,
        variant="remove_required_optional_intervals_from_no_overlap",
        group_id="group::alpha::op::0",
    )
    assert skipped["skipped"] is True
    assert skipped["skip_reason"] == "selector_matched_no_interval_pairs"


def test_no_overlap_delta_aggregates_first_status_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        delta_module,
        "_build_delta_context",
        lambda *args, **kwargs: _fake_context(),
    )
    monkeypatch.setattr(
        delta_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_no_overlap_subset_delta(
        tmp_path / "project",
        group_id="group::alpha::op::0",
        core_json=_core_json(tmp_path / "core.json"),
        variants=(
            "base_12_key_full_model",
            "remove_target_group_intervals_from_no_overlap",
        ),
        time_limit_seconds=0.2,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_no_overlap_subset_delta_v1"
    )
    assert report["status"]["base_status"] == "INFEASIBLE"
    assert report["delta"]["first_status_change"]["variant"] == (
        "remove_target_group_intervals_from_no_overlap"
    )
    markdown = render_phase3b_coordinate_validation_no_overlap_subset_delta_markdown(report)
    text = render_phase3b_coordinate_validation_no_overlap_subset_delta_text(report)
    assert "Variant Matrix" in markdown
    assert "base_status=INFEASIBLE" in text


def test_no_overlap_delta_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_coordinate_validation_no_overlap_subset_delta.py"

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

    assert "phase3b coordinate validation no-overlap subset delta" in no_write.stdout
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
            "no_overlap_delta_smoke",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_validation_no_overlap_subset_delta_json=" in write.stdout
    payload = json.loads((output_dir / "no_overlap_delta_smoke.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_no_overlap_subset_delta_v1"
    )
    assert (output_dir / "no_overlap_delta_smoke.md").exists()
    assert (output_dir / "no_overlap_delta_smoke.txt").exists()
