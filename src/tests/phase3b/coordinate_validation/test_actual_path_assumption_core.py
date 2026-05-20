from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

import src.search.phase3b.coordinate_validation.actual_path_assumption_core as actual_module
from src.search.phase3b.coordinate_validation.actual_path_assumption_core import (
    build_phase3b_coordinate_validation_actual_path_assumption_core,
    render_phase3b_coordinate_validation_actual_path_assumption_core_markdown,
    render_phase3b_coordinate_validation_actual_path_assumption_core_text,
)


class _FakeModel:
    def __init__(self, *, complete: bool = True, status: str = "INFEASIBLE") -> None:
        self.complete = complete
        self.status = status
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
        self.validation_calls.append(dict(kwargs))
        core = _core_labels() if self.status == "INFEASIBLE" else []
        return {
            "attempted": True,
            "status": self.status,
            "accepted": False,
            "reason": self.status.lower(),
            "missing_hint_count": 0,
            "missing_pose_tuple_count": 0,
            "forced_slot_field_count": 6,
            "forced_ghost_anchor": True,
            "forced_fields": list(kwargs.get("force_fields", ())),
            "use_assumptions": bool(kwargs.get("use_assumptions", False)),
            "assumption_core_supported": True,
            "assumption_count": 6,
            "assumption_labels": _core_labels(),
            "infeasible_assumption_core": core,
            "infeasible_assumption_core_status": "extracted" if core else "empty",
            "force_equality_filter_active": False,
            "force_equality_labels": _core_labels()
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
            "count": 2,
            "instance_ids": ["alpha_001", "alpha_002"],
        }
    ]


def _core_labels() -> list[dict[str, Any]]:
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
    ]


def _patch_context(monkeypatch: pytest.MonkeyPatch, fake_model: _FakeModel) -> None:
    groups = _groups()
    monkeypatch.setattr(
        actual_module,
        "_build_delta_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": groups,
            "candidates_by_group": {str(groups[0]["group_id"]): [11, 12]},
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


def test_actual_path_assumption_core_uses_full_anchor_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_actual_path_assumption_core(
        tmp_path / "project",
        anchor_idx=133,
        field_variant="x_y",
        collect_force_equality_labels=True,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_actual_path_assumption_core_v1"
    )
    assert report["status"]["outcome"] == "actual_path_assumption_core_extracted"
    assert fake_model.greedy_calls[0]["blocked_cells"] == {(1, 2), (3, 4)}
    call = fake_model.validation_calls[0]
    assert call["ghost_anchor_hint_idx"] == 133
    assert call["require_complete"] is True
    assert call["use_assumptions"] is True
    assert call["force_fields"] == ("x", "y")
    assert call["collect_force_equality_labels"] is True
    assert report["actual_path"]["core_size"] == 2
    assert report["actual_path"]["collected_force_equality_label_count"] == 2
    assert report["actual_path"]["core_summary"]["field_counts"] == {"x": 1, "y": 1}

    markdown = render_phase3b_coordinate_validation_actual_path_assumption_core_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_actual_path_assumption_core_text(report)
    assert "Actual-Path" in markdown
    assert "core_size=2" in text


def test_actual_path_assumption_core_reports_greedy_incomplete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel(complete=False)
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_actual_path_assumption_core(
        tmp_path / "project",
        anchor_idx=118,
    )

    assert report["status"]["outcome"] == "actual_path_greedy_incomplete"
    assert fake_model.validation_calls == []
    assert report["actual_path"]["validation"]["status"] == "SKIPPED"


def test_actual_path_assumption_core_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "build_actual_path_assumption_core.py"
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

    assert "phase3b actual-path coordinate validation assumption core" in no_write.stdout
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
            "actual_path_test",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "actual_path_assumption_core_json=" in write.stdout
    assert (output_dir / "actual_path_test.json").exists()
    assert (output_dir / "actual_path_test.md").exists()
    assert (output_dir / "actual_path_test.txt").exists()
