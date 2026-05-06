from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

import src.search.phase3b_coordinate_validation_actual_path_equality_core as actual_module
from src.search.phase3b_coordinate_validation_actual_path_equality_core import (
    build_phase3b_coordinate_validation_actual_path_equality_core,
    render_phase3b_coordinate_validation_actual_path_equality_core_markdown,
    render_phase3b_coordinate_validation_actual_path_equality_core_text,
)


class _FakeModel:
    def __init__(self, *, complete: bool = True, full_status: str = "INFEASIBLE") -> None:
        self.complete = complete
        self.full_status = full_status
        self.greedy_calls: list[dict[str, Any]] = []
        self.validation_calls: list[dict[str, Any]] = []

    def _run_mandatory_greedy_pass(
        self,
        *,
        ordered_groups: Sequence[Mapping[str, Any]],
        candidates_by_group: Mapping[str, Sequence[int]],
        blocked_cells: set[tuple[int, int]],
        stop_on_first_failure: bool,
    ) -> dict[str, Any]:
        del candidates_by_group, stop_on_first_failure
        self.greedy_calls.append(
            {
                "ordered_group_count": len(list(ordered_groups)),
                "blocked_cells": set(blocked_cells),
            }
        )
        if not self.complete:
            return {
                "complete": False,
                "reason": "fake_incomplete",
                "hinted_groups": 0,
                "hinted_instances": 0,
                "solution_hint": {},
            }
        solution_hint = {
            str(instance_id): index
            for group in ordered_groups
            for index, instance_id in enumerate(list(group["instance_ids"]), start=1)
        }
        return {
            "complete": True,
            "hinted_groups": len(list(ordered_groups)),
            "hinted_instances": len(solution_hint),
            "solution_hint": solution_hint,
            "first_failed_group_id": None,
            "first_failed_group_template": None,
            "first_failure_reason": None,
            "first_failed_group_position": None,
        }

    def _validate_coordinate_forced_hint(self, **kwargs: Any) -> dict[str, Any]:
        selected_keys = kwargs.get("force_equality_keys")
        active_keys = (
            {str(label["stable_key"]) for label in _labels()}
            if selected_keys is None
            else {str(key) for key in selected_keys}
        )
        self.validation_calls.append(
            {
                "ghost_anchor_hint_idx": kwargs.get("ghost_anchor_hint_idx"),
                "require_complete": kwargs.get("require_complete"),
                "force_fields": kwargs.get("force_fields"),
                "selected_keys": None if selected_keys is None else set(active_keys),
            }
        )
        if selected_keys is None:
            status = self.full_status
        else:
            status = "INFEASIBLE" if "k2" in active_keys else "UNKNOWN"
        return {
            "attempted": True,
            "status": status,
            "accepted": False,
            "reason": status.lower(),
            "missing_hint_count": 0,
            "missing_pose_tuple_count": 0,
            "forced_slot_field_count": len(active_keys),
            "forced_ghost_anchor": True,
            "forced_fields": list(kwargs.get("force_fields", ())),
            "force_equality_filter_active": selected_keys is not None,
            "force_equality_labels": _labels()
            if bool(kwargs.get("collect_force_equality_labels", False))
            else [],
            "require_complete": bool(kwargs.get("require_complete", False)),
            "wall_time": 0.01,
            "user_time": 0.01,
            "deterministic_time": 0.0,
            "branches": 0,
            "conflicts": 0,
            "binary_propagations": 0,
            "integer_propagations": 0,
            "solver_parameters": {"profile_id": "fake"},
        }


def _groups() -> list[dict[str, Any]]:
    return [
        {
            "group_id": "group::alpha::op::0",
            "facility_type": "alpha",
            "operation_type": "op",
            "count": 3,
            "instance_ids": ["alpha_001", "alpha_002", "alpha_003"],
        }
    ]


def _labels() -> list[dict[str, Any]]:
    return [
        {
            "stable_key": "k1",
            "group_id": "group::alpha::op::0",
            "solution_id": "alpha_001",
            "slot_key": "0",
            "slot_index": 0,
            "template": "alpha",
            "pose_index": 11,
            "field": "x",
            "forced_value": 3,
        },
        {
            "stable_key": "k2",
            "group_id": "group::alpha::op::0",
            "solution_id": "alpha_002",
            "slot_key": "1",
            "slot_index": 1,
            "template": "alpha",
            "pose_index": 12,
            "field": "y",
            "forced_value": 7,
        },
        {
            "stable_key": "k3",
            "group_id": "group::alpha::op::0",
            "solution_id": "alpha_003",
            "slot_key": "2",
            "slot_index": 2,
            "template": "alpha",
            "pose_index": 13,
            "field": "mode",
            "forced_value": 1,
        },
    ]


def _patch_context(monkeypatch: pytest.MonkeyPatch, fake_model: _FakeModel) -> None:
    groups = _groups()
    monkeypatch.setattr(
        actual_module,
        "_build_delta_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": groups,
            "candidates_by_group": {str(groups[0]["group_id"]): [11, 12, 13]},
            "blocked_cells": {(1, 2), (3, 4)},
            "ghost_anchor_count": 232,
            "blocked_cell_count": 2,
            "ordered_group_count": len(groups),
        },
    )
    monkeypatch.setattr(
        actual_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )


def test_actual_path_equality_core_uses_anchor_path_and_shrinks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_actual_path_equality_core(
        tmp_path / "project",
        anchor_idx=133,
        field_variant="x_y_mode",
        max_delete_tests=16,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_actual_path_equality_core_v1"
    )
    assert report["status"]["outcome"] == "actual_path_equality_core_approximated"
    assert fake_model.greedy_calls[0]["blocked_cells"] == {(1, 2), (3, 4)}
    first_call = fake_model.validation_calls[0]
    assert first_call["ghost_anchor_hint_idx"] == 133
    assert first_call["require_complete"] is True
    assert first_call["force_fields"] == ("x", "y", "mode")
    assert report["actual_path"]["equality_label_count"] == 3
    assert report["actual_path"]["first_single_delete_preserves_infeasible"]["removed_key"] == "k1"
    assert report["actual_path"]["first_single_delete_changes_status"]["removed_key"] == "k2"
    assert report["actual_path"]["final_keys"] == ["k2"]
    assert report["actual_path"]["remaining_summary"]["field_counts"] == {"y": 1}

    markdown = render_phase3b_coordinate_validation_actual_path_equality_core_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_actual_path_equality_core_text(report)
    assert "Actual-Path" in markdown
    assert "final_key_count=1" in text


def test_actual_path_equality_core_reports_full_not_infeasible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel(full_status="UNKNOWN")
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_actual_path_equality_core(
        tmp_path / "project",
        anchor_idx=118,
        max_delete_tests=16,
    )

    assert report["status"]["outcome"] == "full_actual_path_not_infeasible"
    assert report["actual_path"]["single_delete_results"] == []


def test_actual_path_equality_core_can_skip_single_delete_scan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_actual_path_equality_core(
        tmp_path / "project",
        anchor_idx=133,
        field_variant="x_y_mode",
        max_delete_tests=16,
        skip_single_delete=True,
    )

    assert report["profile"]["skip_single_delete"] is True
    assert report["actual_path"]["single_delete_results"] == []
    assert report["actual_path"]["greedy_steps"]
    assert report["actual_path"]["final_keys"] == ["k2"]


def test_actual_path_equality_core_can_continue_from_initial_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_actual_path_equality_core(
        tmp_path / "project",
        anchor_idx=133,
        field_variant="x_y_mode",
        max_delete_tests=16,
        skip_single_delete=True,
        initial_keys=["k1", "k2", "missing"],
    )

    assert report["profile"]["initial_keys_supplied"] is True
    assert report["actual_path"]["initial_key_count"] == 2
    assert report["actual_path"]["unknown_initial_key_count"] == 1
    assert report["actual_path"]["unknown_initial_keys"] == ["missing"]
    assert report["actual_path"]["initial_subset_validation"]["status"] == "INFEASIBLE"
    assert report["actual_path"]["final_keys"] == ["k2"]


def test_actual_path_equality_core_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_actual_path_equality_core.py"
    )

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

    assert "phase3b actual-path coordinate validation equality core" in no_write.stdout
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
            "actual_path_equality_test",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "actual_path_equality_core_json=" in write.stdout
    assert (output_dir / "actual_path_equality_test.json").exists()
    assert (output_dir / "actual_path_equality_test.md").exists()
    assert (output_dir / "actual_path_equality_test.txt").exists()
