from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest
from ortools.sat.python import cp_model

import src.search.phase3b.coordinate_validation.x_domain_order_audit as audit_module
from src.search.phase3b.coordinate_validation.x_domain_order_audit import (
    build_phase3b_coordinate_validation_x_domain_order_audit,
    render_phase3b_coordinate_validation_x_domain_order_audit_markdown,
    render_phase3b_coordinate_validation_x_domain_order_audit_text,
)


class _FakeSlot:
    def __init__(
        self,
        *,
        key: str,
        template: str,
        slot_index: int,
        x: cp_model.IntVar,
        y: cp_model.IntVar,
        mode: cp_model.IntVar,
        order_key: cp_model.IntVar,
    ) -> None:
        self.key = key
        self.template = template
        self.slot_kind = "mandatory"
        self.slot_index = slot_index
        self.dims = (2, 2)
        self.candidate_pose_count = 2
        self.tuple_to_pose_idx = {(0, 2, 0): 1, (0, 4, 0): 2}
        self.mode_rect_domains = {0: {"mode_id": 0, "x_min": 0, "x_max": 8, "y_min": 0, "y_max": 8}}
        self.allowed_tuples = ((0, 2, 0), (0, 4, 0))
        self.use_domain_table = True
        self.x = x
        self.y = y
        self.mode = mode
        self.order_key = order_key


class _FakeDelegate:
    def __init__(self, model: cp_model.CpModel) -> None:
        self.model = model
        self.grid_w = 10
        self.grid_h = 10
        self._template_mode_literals = {"alpha": 2}
        self._template_pose_tuple_by_idx = {"alpha": {1: (0, 2, 0), 2: (0, 4, 0)}}
        slots = []
        for slot_index in range(2):
            x = model.NewIntVar(0, 8, f"x__group::alpha::op::0::slot::{slot_index}")
            y = model.NewIntVar(0, 8, f"y__group::alpha::op::0::slot::{slot_index}")
            mode = model.NewIntVar(0, 1, f"mode__group::alpha::op::0::slot::{slot_index}")
            order = model.NewIntVar(0, 199, f"order_key__group::alpha::op::0::slot::{slot_index}")
            model.Add(order == x * 20 + y * 2 + mode)
            slots.append(
                _FakeSlot(
                    key=f"group::alpha::op::0::slot::{slot_index}",
                    template="alpha",
                    slot_index=slot_index,
                    x=x,
                    y=y,
                    mode=mode,
                    order_key=order,
                )
            )
        model.Add(slots[0].order_key <= slots[1].order_key)
        self.mandatory_slots = {"group::alpha::op::0": slots}

    def _slot_order_key_bounds(self, slot: _FakeSlot) -> tuple[int, int]:
        del slot
        return (20, 2)


class _FakeModel:
    def __init__(self) -> None:
        self.model = cp_model.CpModel()
        self._coordinate_delegate = _FakeDelegate(self.model)
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
            "alpha_001": 1,
            "alpha_002": 2,
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
        selected = {str(key) for key in kwargs.get("force_equality_keys", set())}
        self.validation_calls.append({"selected": selected})
        labels = [
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
                "selected": "k1" in selected,
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
                "selected": "k2" in selected,
            },
        ]
        return {
            "attempted": True,
            "status": "INFEASIBLE",
            "accepted": False,
            "reason": "infeasible",
            "missing_hint_count": 0,
            "missing_pose_tuple_count": 0,
            "forced_slot_field_count": len(selected),
            "forced_ghost_anchor": False,
            "forced_fields": ["x"],
            "require_complete": False,
            "force_equality_filter_active": True,
            "force_equality_labels": labels,
            "wall_time": 0.01,
            "user_time": 0.01,
            "deterministic_time": 0.0,
            "branches": 0,
            "conflicts": 0,
            "binary_propagations": 0,
            "integer_propagations": 0,
            "solver_parameters": {"profile_id": "fake"},
        }

    def _pose_sort_key(self, tpl: str, pose_idx: int) -> tuple[int, int]:
        del tpl
        return (pose_idx, 0)


def _fake_group() -> dict[str, Any]:
    return {
        "group_id": "group::alpha::op::0",
        "facility_type": "alpha",
        "operation_type": "op",
        "count": 2,
        "instance_ids": ["alpha_001", "alpha_002"],
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


def test_x_domain_order_audit_enriches_core_and_runs_standalone(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel()
    group = _fake_group()
    monkeypatch.setattr(
        audit_module,
        "_build_delta_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": [group],
            "candidates_by_group": {str(group["group_id"]): [1, 2]},
            "blocked_cells": set(),
            "ghost_anchor_count": 1,
            "blocked_cell_count": 0,
            "ordered_group_count": 1,
        },
    )
    monkeypatch.setattr(
        audit_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_x_domain_order_audit(
        tmp_path / "project",
        group_id="group::alpha::op::0",
        core_json=_core_json(tmp_path / "core.json"),
        time_limit_seconds=0.1,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_x_domain_order_audit_v1"
    )
    assert report["status"]["outcome"] == "subset_infeasible"
    assert report["subset_validation"]["status"] == "INFEASIBLE"
    assert report["audit"]["entry_count"] == 2
    assert report["audit"]["all_pose_tuples_allowed"] is True
    assert report["audit"]["all_forced_values_match_pose_tuple"] is True
    assert report["audit"]["monotonicity"]["core_order_keys_nondecreasing"] is True
    assert {entry["order_key_value"] for entry in report["audit"]["entries"]} == {4, 8}
    assert report["standalone_repro"]["attempted"] is True
    assert {
        variant["variant"]: variant["accepted"]
        for variant in report["standalone_repro"]["variants"]
    } == {
        "group_domain_order_only": True,
        "group_domain_order_no_overlap": True,
    }
    markdown = render_phase3b_coordinate_validation_x_domain_order_audit_markdown(report)
    text = render_phase3b_coordinate_validation_x_domain_order_audit_text(report)
    assert "Core Label Audit" in markdown
    assert "subset_status=INFEASIBLE" in text


def test_x_domain_order_audit_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "coordinate_validation" / "build_x_domain_order_audit.py"

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

    assert "phase3b coordinate validation x-domain/order audit" in no_write.stdout
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
            "x_domain_order_smoke",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_validation_x_domain_order_audit_json=" in write.stdout
    payload = json.loads((output_dir / "x_domain_order_smoke.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_x_domain_order_audit_v1"
    )
    assert (output_dir / "x_domain_order_smoke.md").exists()
    assert (output_dir / "x_domain_order_smoke.txt").exists()
