from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

import src.search.phase3b.coordinate_validation.assumption_core as core_module
from src.search.phase3b.coordinate_validation.assumption_core import (
    build_phase3b_coordinate_validation_assumption_core,
    render_phase3b_coordinate_validation_assumption_core_markdown,
    render_phase3b_coordinate_validation_assumption_core_text,
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
        use_assumptions = bool(kwargs.get("use_assumptions", False))
        solution_hint = dict(kwargs["solution_hint"])
        self.validation_calls.append(
            {
                "solution_hint": solution_hint,
                "ghost_anchor_hint_idx": kwargs["ghost_anchor_hint_idx"],
                "require_complete": kwargs["require_complete"],
                "force_fields": force_fields,
                "use_assumptions": use_assumptions,
            }
        )
        labels = [
            {
                "assumption_index": index,
                "group_id": "group::alpha::alpha_op::0",
                "solution_id": solution_id,
                "slot_key": str(index),
                "slot_index": index,
                "template": "alpha",
                "pose_index": pose_idx,
                "field": field,
                "forced_value": index + 1,
            }
            for index, (solution_id, pose_idx) in enumerate(solution_hint.items())
            for field in force_fields
        ]
        status = "INFEASIBLE" if use_assumptions else "OPTIMAL"
        core = labels[:1] if status == "INFEASIBLE" else []
        return {
            "attempted": True,
            "status": status,
            "accepted": status == "OPTIMAL",
            "reason": status.lower(),
            "missing_hint_count": 0,
            "missing_pose_tuple_count": 0,
            "forced_slot_field_count": len(labels),
            "forced_ghost_anchor": kwargs["ghost_anchor_hint_idx"] is not None,
            "forced_fields": list(force_fields),
            "use_assumptions": use_assumptions,
            "assumption_core_supported": use_assumptions,
            "assumption_count": len(labels) if use_assumptions else 0,
            "assumption_labels": labels if use_assumptions else [],
            "infeasible_assumption_core": core,
            "infeasible_assumption_core_status": (
                "extracted" if core else ("not_requested" if not use_assumptions else "empty")
            ),
            "require_complete": bool(kwargs["require_complete"]),
            "wall_time": 0.05,
            "user_time": 0.04,
            "deterministic_time": 0.01,
            "branches": 0,
            "conflicts": 0,
            "binary_propagations": 0,
            "integer_propagations": 0,
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


def _patch_context(monkeypatch: pytest.MonkeyPatch, fake_model: _FakeModel) -> None:
    groups = _fake_groups()
    monkeypatch.setattr(
        core_module,
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
        core_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )


def test_assumption_core_helper_maps_extracted_core_labels(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_assumption_core(
        tmp_path / "project",
        cases=["group::alpha::alpha_op::0:x_y"],
        time_limit_seconds=0.5,
    )

    assert report["metadata"]["source"] == "phase3b_coordinate_validation_assumption_core_v1"
    assert report["status"]["outcome"] == "assumption_core_extracted"
    entry = report["assumption_core"]["entries"][0]
    validation = entry["validation"]
    assert validation["use_assumptions"] is True
    assert validation["assumption_core_supported"] is True
    assert validation["infeasible_assumption_core_status"] == "extracted"
    assert validation["assumption_count"] == 2
    assert validation["infeasible_assumption_core"][0]["slot_key"] == "0"
    assert validation["infeasible_assumption_core"][0]["field"] == "x"
    assert validation["infeasible_assumption_core"][0]["forced_value"] == 1

    assert fake_model.validation_calls[0]["use_assumptions"] is True
    assert fake_model.validation_calls[0]["ghost_anchor_hint_idx"] is None
    assert fake_model.validation_calls[0]["require_complete"] is False
    assert fake_model.validation_calls[0]["force_fields"] == ("x", "y")

    markdown = render_phase3b_coordinate_validation_assumption_core_markdown(report)
    text = render_phase3b_coordinate_validation_assumption_core_text(report)
    assert "First Extracted Core" in markdown
    assert "core_status=extracted" in text


def test_fake_validation_default_does_not_use_assumptions() -> None:
    fake_model = _FakeModel()
    payload = fake_model._validate_coordinate_forced_hint(
        solution_hint={"alpha_001": 7},
        ghost_anchor_hint_idx=None,
        time_limit_seconds=0.5,
        require_complete=False,
        solver_parameter_profile={"profile_id": "p0"},
        force_fields=("x",),
    )

    assert payload["use_assumptions"] is False
    assert payload["assumption_count"] == 0
    assert payload["infeasible_assumption_core_status"] == "not_requested"
    assert fake_model.validation_calls[0]["use_assumptions"] is False


def test_assumption_core_reports_diagnostic_error_for_unknown_group(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    _patch_context(monkeypatch, fake_model)

    report = build_phase3b_coordinate_validation_assumption_core(
        tmp_path / "project",
        cases=["missing:x"],
    )

    assert report["status"]["outcome"] == "diagnostic_error"
    assert "Unknown assumption-core group id" in report["model_error"]


def test_assumption_core_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "coordinate_validation" / "build_assumption_core.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--case",
            "group::manufacturing_5x5::planter_sandleaf::10:x",
            "--time-limit-seconds",
            "0",
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate validation assumption core" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--case",
            "group::manufacturing_5x5::planter_sandleaf::10:x",
            "--time-limit-seconds",
            "0",
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "assumption_core_smoke",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_validation_assumption_core_json=" in write.stdout
    payload = json.loads(
        (output_dir / "assumption_core_smoke.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_assumption_core_v1"
    )
    assert (output_dir / "assumption_core_smoke.md").exists()
    assert (output_dir / "assumption_core_smoke.txt").exists()
