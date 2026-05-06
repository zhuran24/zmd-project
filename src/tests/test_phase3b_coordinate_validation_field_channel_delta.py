from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

import src.search.phase3b_coordinate_validation_field_channel_delta as field_module
from src.models.master_model import _normalize_coordinate_force_fields
from src.search.phase3b_coordinate_validation_field_channel_delta import (
    build_phase3b_coordinate_validation_field_channel_delta,
    render_phase3b_coordinate_validation_field_channel_delta_markdown,
    render_phase3b_coordinate_validation_field_channel_delta_text,
)


class _FakeModel:
    def __init__(self) -> None:
        self.validation_calls: list[dict[str, Any]] = []

    def _run_mandatory_greedy_pass(
        self,
        *,
        ordered_groups: Sequence[Mapping[str, Any]],
        candidates_by_group: Mapping[str, Sequence[int]],
        blocked_cells: set[tuple[int, int]],
        stop_on_first_failure: bool,
    ) -> dict[str, Any]:
        del candidates_by_group, blocked_cells, stop_on_first_failure
        solution_hint: dict[str, int] = {}
        for group in ordered_groups:
            pose_idx = 7 if str(group["facility_type"]) == "alpha" else 11
            for instance_id in list(group["instance_ids"]):
                solution_hint[str(instance_id)] = pose_idx
        return {
            "complete": True,
            "reason": None,
            "hinted_groups": len(list(ordered_groups)),
            "hinted_instances": len(solution_hint),
            "solution_hint": solution_hint,
            "first_failed_group_id": None,
            "first_failed_group_template": None,
            "first_failure_reason": None,
            "first_failed_group_position": None,
        }

    def _validate_coordinate_forced_hint(self, **kwargs: Any) -> dict[str, Any]:
        force_fields = tuple(kwargs["force_fields"])
        collect_labels = bool(kwargs.get("collect_force_equality_labels", False))
        self.validation_calls.append(
            {
                "solution_hint": dict(kwargs["solution_hint"]),
                "ghost_anchor_hint_idx": kwargs["ghost_anchor_hint_idx"],
                "require_complete": kwargs["require_complete"],
                "force_fields": force_fields,
                "collect_force_equality_labels": collect_labels,
            }
        )
        status = "INFEASIBLE" if force_fields == ("x", "y", "mode") else "OPTIMAL"
        return {
            "attempted": True,
            "status": status,
            "accepted": status == "OPTIMAL",
            "reason": status.lower(),
            "missing_hint_count": 0,
            "missing_pose_tuple_count": 0,
            "forced_slot_field_count": len(force_fields),
            "forced_ghost_anchor": kwargs["ghost_anchor_hint_idx"] is not None,
            "forced_fields": list(force_fields),
            "require_complete": bool(kwargs["require_complete"]),
            "wall_time": 0.05,
            "user_time": 0.04,
            "deterministic_time": 0.01,
            "branches": 0,
            "conflicts": 0,
            "binary_propagations": 0,
            "integer_propagations": 0,
            "force_equality_labels": [
                {
                    "stable_key": "mandatory|group::alpha::alpha_op::0|0|alpha_001|7|x",
                    "field": "x",
                }
            ]
            if collect_labels
            else [],
            "solver_parameters": {
                "profile_id": kwargs["solver_parameter_profile"]["profile_id"],
                "max_time_in_seconds": kwargs["time_limit_seconds"],
            },
        }


def _fake_groups() -> list[dict[str, Any]]:
    return [
        {
            "group_id": "group::alpha::alpha_op::0",
            "facility_type": "alpha",
            "operation_type": "alpha_op",
            "count": 1,
            "instance_ids": ["alpha_001"],
        },
        {
            "group_id": "group::beta::beta_op::1",
            "facility_type": "beta",
            "operation_type": "beta_op",
            "count": 1,
            "instance_ids": ["beta_001"],
        },
    ]


def test_coordinate_force_field_normalization_rejects_invalid_names() -> None:
    assert _normalize_coordinate_force_fields(("x", "y", "mode")) == (
        "x",
        "y",
        "mode",
    )
    assert _normalize_coordinate_force_fields(("mode", "x", "x")) == ("x", "mode")
    with pytest.raises(ValueError, match="Unsupported coordinate force field"):
        _normalize_coordinate_force_fields(("x", "angle"))
    with pytest.raises(ValueError, match="at least one"):
        _normalize_coordinate_force_fields(())


def test_field_channel_helper_emits_group_field_matrix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    groups = _fake_groups()
    monkeypatch.setattr(
        field_module,
        "_build_delta_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": groups,
            "candidates_by_group": {str(group["group_id"]): [7, 11] for group in groups},
            "blocked_cells": {(1, 2)},
            "ghost_anchor_count": 120,
            "blocked_cell_count": 871,
            "ordered_group_count": len(groups),
        },
    )
    monkeypatch.setattr(
        field_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_field_channel_delta(
        tmp_path / "project",
        group_ids=["group::alpha::alpha_op::0", "group::beta::beta_op::1"],
        field_variants=["x", "x_y_mode"],
        time_limit_seconds=0.5,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_field_channel_delta_v1"
    )
    assert report["status"]["outcome"] == "field_channel_infeasible_found"
    assert report["field_channel_delta"]["status_counts"] == {
        "OPTIMAL": 2,
        "INFEASIBLE": 2,
    }
    assert len(report["field_channel_delta"]["entries"]) == 4

    for entry in report["field_channel_delta"]["entries"]:
        assert entry["include_ghost"] is False
        assert entry["require_complete"] is False
        if entry["field_variant"] == "x":
            assert entry["force_fields"] == ["x"]
            assert entry["validation"]["forced_slot_field_count"] == 1
        if entry["field_variant"] == "x_y_mode":
            assert entry["force_fields"] == ["x", "y", "mode"]
            assert entry["validation"]["status"] == "INFEASIBLE"

    assert {call["ghost_anchor_hint_idx"] for call in fake_model.validation_calls} == {None}
    assert {call["require_complete"] for call in fake_model.validation_calls} == {False}
    assert ("x", "y", "mode") in {call["force_fields"] for call in fake_model.validation_calls}

    markdown = render_phase3b_coordinate_validation_field_channel_delta_markdown(report)
    text = render_phase3b_coordinate_validation_field_channel_delta_text(report)
    assert "Coordinate Validation Field-Channel Delta" in markdown
    assert "field_variant=x_y_mode" in text


def test_field_channel_helper_rejects_unknown_group_or_field(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    groups = _fake_groups()
    monkeypatch.setattr(
        field_module,
        "_build_delta_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": groups,
            "candidates_by_group": {str(group["group_id"]): [7, 11] for group in groups},
            "blocked_cells": set(),
            "ghost_anchor_count": 120,
            "blocked_cell_count": 871,
            "ordered_group_count": len(groups),
        },
    )

    with pytest.raises(ValueError, match="Unsupported field-channel variant"):
        build_phase3b_coordinate_validation_field_channel_delta(
            tmp_path / "project",
            field_variants=["x", "bad"],
        )

    report = build_phase3b_coordinate_validation_field_channel_delta(
        tmp_path / "project",
        group_ids=["missing"],
        field_variants=["x"],
    )
    assert report["status"]["outcome"] == "diagnostic_error"
    assert "Unknown field-channel group id" in report["model_error"]


def test_field_channel_helper_can_include_ghost_anchor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    groups = _fake_groups()
    monkeypatch.setattr(
        field_module,
        "_build_delta_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": groups,
            "candidates_by_group": {str(group["group_id"]): [7, 11] for group in groups},
            "blocked_cells": {(1, 2)},
            "ghost_anchor_count": 120,
            "blocked_cell_count": 871,
            "ordered_group_count": len(groups),
        },
    )
    monkeypatch.setattr(
        field_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_field_channel_delta(
        tmp_path / "project",
        anchor_idx=159,
        group_ids=["group::alpha::alpha_op::0"],
        field_variants=["x_y_mode"],
        include_ghost=True,
        collect_force_equality_labels=True,
        time_limit_seconds=0.5,
    )

    entry = report["field_channel_delta"]["entries"][0]
    assert report["profile"]["include_ghost"] is True
    assert entry["include_ghost"] is True
    assert entry["validation"]["forced_ghost_anchor"] is True
    assert report["profile"]["collect_force_equality_labels"] is True
    assert entry["validation"]["force_equality_labels"][0]["field"] == "x"
    assert fake_model.validation_calls[0]["ghost_anchor_hint_idx"] == 159
    assert fake_model.validation_calls[0]["collect_force_equality_labels"] is True
    assert "ghost=True" in render_phase3b_coordinate_validation_field_channel_delta_text(report)


def test_field_channel_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_coordinate_validation_field_channel_delta.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--fields",
            "x",
            "--include-ghost",
            "--collect-force-equality-labels",
            "--time-limit-seconds",
            "0",
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate validation field-channel delta" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--fields",
            "x",
            "--include-ghost",
            "--collect-force-equality-labels",
            "--time-limit-seconds",
            "0",
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "field_delta_smoke",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_validation_field_channel_delta_json=" in write.stdout
    payload = json.loads(
        (output_dir / "field_delta_smoke.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_field_channel_delta_v1"
    )
    assert payload["profile"]["include_ghost"] is True
    assert payload["profile"]["collect_force_equality_labels"] is True
    assert (output_dir / "field_delta_smoke.md").exists()
    assert (output_dir / "field_delta_smoke.txt").exists()
