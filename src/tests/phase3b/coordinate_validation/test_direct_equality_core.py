from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

import src.search.phase3b.coordinate_validation.direct_equality_core as core_module
from src.search.phase3b.coordinate_validation.direct_equality_core import (
    build_phase3b_coordinate_validation_direct_equality_core,
    render_phase3b_coordinate_validation_direct_equality_core_markdown,
    render_phase3b_coordinate_validation_direct_equality_core_text,
)


class _FakeModel:
    def __init__(self, *, full_status: str = "INFEASIBLE") -> None:
        self.full_status = full_status
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
        collect = bool(kwargs.get("collect_force_equality_labels", False))
        selected_keys = kwargs.get("force_equality_keys")
        labels = _labels()
        keys = {str(label["stable_key"]) for label in labels}
        active_keys = keys if selected_keys is None else {str(key) for key in selected_keys}
        self.validation_calls.append(
            {
                "collect": collect,
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
            "forced_ghost_anchor": False,
            "forced_fields": ["x"],
            "require_complete": False,
            "force_equality_filter_active": selected_keys is not None,
            "force_equality_labels": labels if collect else [],
            "wall_time": 0.01,
            "user_time": 0.01,
            "deterministic_time": 0.0,
            "branches": 0,
            "conflicts": 0,
            "binary_propagations": 0,
            "integer_propagations": 0,
            "solver_parameters": {"profile_id": "fake"},
        }


def _labels() -> list[dict[str, Any]]:
    return [
        {
            "stable_key": "k1",
            "group_id": "group::alpha::alpha_op::0",
            "solution_id": "alpha_001",
            "slot_key": "0",
            "slot_index": 0,
            "template": "alpha",
            "pose_index": 1,
            "field": "x",
            "forced_value": 3,
            "selected": True,
        },
        {
            "stable_key": "k2",
            "group_id": "group::alpha::alpha_op::0",
            "solution_id": "alpha_002",
            "slot_key": "1",
            "slot_index": 1,
            "template": "alpha",
            "pose_index": 2,
            "field": "x",
            "forced_value": 5,
            "selected": True,
        },
        {
            "stable_key": "k3",
            "group_id": "group::alpha::alpha_op::0",
            "solution_id": "alpha_003",
            "slot_key": "2",
            "slot_index": 2,
            "template": "alpha",
            "pose_index": 3,
            "field": "x",
            "forced_value": 8,
            "selected": True,
        },
    ]


def _fake_groups() -> list[dict[str, Any]]:
    return [
        {
            "group_id": "group::alpha::alpha_op::0",
            "facility_type": "alpha",
            "operation_type": "alpha_op",
            "count": 3,
            "instance_ids": ["alpha_001", "alpha_002", "alpha_003"],
        }
    ]


def _patch_context(monkeypatch: pytest.MonkeyPatch, fake_model: _FakeModel) -> None:
    groups = _fake_groups()
    monkeypatch.setattr(
        core_module,
        "_build_delta_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": groups,
            "candidates_by_group": {str(groups[0]["group_id"]): [1, 2, 3]},
            "blocked_cells": set(),
            "ghost_anchor_count": 1,
            "blocked_cell_count": 1,
            "ordered_group_count": len(groups),
        },
    )
    monkeypatch.setattr(
        core_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )


def test_direct_equality_core_collects_stable_labels_and_greedy_shrinks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_direct_equality_core(
        tmp_path / "project",
        group_id="group::alpha::alpha_op::0",
        field_variant="x",
        max_delete_tests=16,
    )

    core = report["direct_equality_core"]
    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_direct_equality_core_v1"
    )
    assert report["status"]["outcome"] == "direct_equality_core_approximated"
    assert core["full_validation"]["status"] == "INFEASIBLE"
    assert core["equality_label_count"] == 3
    assert [label["stable_key"] for label in core["equality_labels"]] == [
        "k1",
        "k2",
        "k3",
    ]
    assert core["first_single_delete_preserves_infeasible"]["removed_key"] == "k1"
    assert core["first_single_delete_changes_status"]["removed_key"] == "k2"
    assert core["final_keys"] == ["k2"]
    assert core["remaining_labels"][0]["forced_value"] == 5
    assert core["remaining_summary"]["field_counts"] == {"x": 1}

    subset_calls = [
        call for call in fake_model.validation_calls if call["selected_keys"] is not None
    ]
    assert subset_calls
    assert any(call["selected_keys"] == {"k2"} for call in subset_calls)

    markdown = render_phase3b_coordinate_validation_direct_equality_core_markdown(report)
    text = render_phase3b_coordinate_validation_direct_equality_core_text(report)
    assert "Remaining Approximate Core" in markdown
    assert "final_key_count=1" in text


def test_direct_equality_core_reports_when_full_set_not_infeasible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel(full_status="UNKNOWN")
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_direct_equality_core(
        tmp_path / "project",
        group_id="group::alpha::alpha_op::0",
        field_variant="x",
    )

    assert report["status"]["outcome"] == "full_set_not_infeasible"
    assert report["direct_equality_core"]["single_delete_results"] == []


def test_direct_equality_core_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "coordinate_validation" / "build_direct_equality_core.py"

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

    assert "phase3b coordinate validation direct equality core" in no_write.stdout
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
            "direct_core_smoke",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_validation_direct_equality_core_json=" in write.stdout
    payload = json.loads((output_dir / "direct_core_smoke.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_direct_equality_core_v1"
    )
    assert (output_dir / "direct_core_smoke.md").exists()
    assert (output_dir / "direct_core_smoke.txt").exists()
