from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

import src.search.phase3b_coordinate_validation_group_delta as delta_module
from src.search.phase3b_coordinate_validation_group_delta import (
    build_phase3b_coordinate_validation_group_delta,
    render_phase3b_coordinate_validation_group_delta_markdown,
    render_phase3b_coordinate_validation_group_delta_text,
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
        solution_hint = dict(kwargs["solution_hint"])
        ghost_anchor = kwargs["ghost_anchor_hint_idx"]
        profile = dict(kwargs["solver_parameter_profile"])
        self.validation_calls.append(
            {
                "solution_hint": solution_hint,
                "ghost_anchor_hint_idx": ghost_anchor,
                "require_complete": kwargs["require_complete"],
            }
        )
        status = (
            "INFEASIBLE"
            if ghost_anchor == 119 and solution_hint == {"alpha_001": 7}
            else "OPTIMAL"
        )
        return {
            "attempted": True,
            "status": status,
            "accepted": status == "OPTIMAL",
            "reason": status.lower(),
            "missing_hint_count": 0,
            "missing_pose_tuple_count": 0,
            "forced_slot_field_count": 3 * len(solution_hint),
            "forced_ghost_anchor": ghost_anchor is not None,
            "require_complete": bool(kwargs["require_complete"]),
            "wall_time": 0.05,
            "user_time": 0.04,
            "deterministic_time": 0.01,
            "branches": 0,
            "conflicts": 0,
            "binary_propagations": 0,
            "integer_propagations": 0,
            "solver_parameters": {
                "profile_id": profile["profile_id"],
                "max_time_in_seconds": kwargs["time_limit_seconds"],
                "num_search_workers": profile["worker_count"],
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


def test_group_delta_expands_group_variants_and_classifies_narrow_infeasible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    groups = _fake_groups()
    monkeypatch.setattr(
        delta_module,
        "_build_delta_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": groups,
            "candidates_by_group": {str(group["group_id"]): [7, 11] for group in groups},
            "blocked_cells": {(1, 2)},
            "ghost_anchor_count": 120,
            "blocked_cell_count": 871,
            "ordered_group_count": len(groups),
            "family_count": 2,
        },
    )
    monkeypatch.setattr(
        delta_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_group_delta(
        tmp_path / "project",
        variants=[
            "ghost_plus_all",
            "mandatory_only",
            "ghost_only",
            "ghost_plus_each_group",
            "ghost_plus_all_except_group",
        ],
        max_groups=1,
        time_limit_seconds=0.5,
    )

    assert report["metadata"]["source"] == "phase3b_coordinate_validation_group_delta_v1"
    assert report["status"]["outcome"] == "coordinate_validation_delta_infeasible_found"
    assert report["delta"]["status_counts"] == {"OPTIMAL": 4, "INFEASIBLE": 1}
    assert len(report["delta"]["entries"]) == 5

    first = report["delta"]["first_infeasible_entry"]
    assert first["variant"] == "ghost_plus_each_group"
    assert first["included_group_ids"] == ["group::alpha::alpha_op::0"]
    assert first["validation"]["require_complete"] is False
    assert report["delta"]["first_narrower_infeasible_entry"]["case_id"] == (
        "ghost_plus_each_group:group::alpha::alpha_op::0"
    )

    mandatory_call = fake_model.validation_calls[1]
    assert mandatory_call["ghost_anchor_hint_idx"] is None
    assert mandatory_call["require_complete"] is True

    markdown = render_phase3b_coordinate_validation_group_delta_markdown(report)
    text = render_phase3b_coordinate_validation_group_delta_text(report)
    assert "Coordinate Validation Group Delta" in markdown
    assert "group::alpha::alpha_op::0" in markdown
    assert "variant=ghost_plus_each_group" in text


def test_group_delta_rejects_unknown_variant(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported group delta variant"):
        build_phase3b_coordinate_validation_group_delta(
            tmp_path / "project",
            variants=["ghost_plus_all", "not_a_variant"],
        )


def test_group_delta_expands_mandatory_no_ghost_variants(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    groups = _fake_groups()
    monkeypatch.setattr(
        delta_module,
        "_build_delta_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": groups,
            "candidates_by_group": {
                str(group["group_id"]): [7, 11] for group in groups
            },
            "blocked_cells": {(1, 2)},
            "ghost_anchor_count": 120,
            "blocked_cell_count": 871,
            "ordered_group_count": len(groups),
            "family_count": 2,
        },
    )
    monkeypatch.setattr(
        delta_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_group_delta(
        tmp_path / "project",
        variants=[
            "mandatory_each_group",
            "mandatory_all_except_group",
            "mandatory_each_family",
            "mandatory_all_except_family",
            "ghost_plus_each_group",
        ],
        max_groups=1,
        max_families=1,
        time_limit_seconds=0.5,
    )

    entries = report["delta"]["entries"]
    by_case = {entry["case_id"]: entry for entry in entries}
    assert len(entries) == 5
    assert "mandatory_each_group:group::alpha::alpha_op::0" in by_case
    assert "mandatory_all_except_group:group::alpha::alpha_op::0" in by_case
    assert "mandatory_each_family:alpha" in by_case
    assert "mandatory_all_except_family:alpha" in by_case
    assert "ghost_plus_each_group:group::alpha::alpha_op::0" in by_case

    each_group = by_case["mandatory_each_group:group::alpha::alpha_op::0"]
    assert each_group["include_ghost"] is False
    assert each_group["require_complete"] is False
    assert each_group["included_group_count"] == 1
    assert each_group["excluded_group_count"] == 0

    except_group = by_case["mandatory_all_except_group:group::alpha::alpha_op::0"]
    assert except_group["include_ghost"] is False
    assert except_group["included_group_count"] == 1
    assert except_group["excluded_group_count"] == 1
    assert except_group["excluded_group_ids"] == ["group::alpha::alpha_op::0"]

    each_family = by_case["mandatory_each_family:alpha"]
    assert each_family["include_ghost"] is False
    assert each_family["family_key"] == "alpha"
    assert each_family["included_group_count"] == 1

    except_family = by_case["mandatory_all_except_family:alpha"]
    assert except_family["include_ghost"] is False
    assert except_family["family_key"] == "alpha"
    assert except_family["included_group_count"] == 1
    assert except_family["excluded_group_count"] == 1

    ghost_entry = by_case["ghost_plus_each_group:group::alpha::alpha_op::0"]
    assert ghost_entry["include_ghost"] is True

    mandatory_calls = [
        call
        for call in fake_model.validation_calls
        if call["solution_hint"] and call["ghost_anchor_hint_idx"] is None
    ]
    assert mandatory_calls
    assert all(call["require_complete"] is False for call in mandatory_calls)


def test_group_delta_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_coordinate_validation_group_delta.py"

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

    assert "phase3b coordinate validation group delta" in no_write.stdout
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
            "delta_smoke",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_validation_group_delta_json=" in write.stdout
    payload = json.loads((output_dir / "delta_smoke.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_coordinate_validation_group_delta_v1"
    assert (output_dir / "delta_smoke.md").exists()
    assert (output_dir / "delta_smoke.txt").exists()
