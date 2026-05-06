from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import src.models.master_model as master_model_module
from src.models.master_model import (
    EXACT_GHOST_Y_OVERLAP_FORCED_LABEL_PRECHECK_ENV,
    MasterPlacementModel,
    evaluate_ghost_y_overlap_forced_label_conflict,
)


class _FakeGhostOwner:
    grid_w = 70
    grid_h = 70
    ghost_rect = (67, 13)
    _ghost_domains = [{"anchor": {"x": 2, "y": 17}}]
    _mandatory_groups = [
        {
            "group_id": "group::m5x5::planter::0",
            "facility_type": "m5x5",
            "operation_type": "planter",
            "count": 1,
            "instance_ids": ["planter_001"],
        }
    ]
    _group_id_by_instance = {"planter_001": "group::m5x5::planter::0"}

    def __init__(self, *, pose_y: int = 25, slot_w: int = 5) -> None:
        self._coordinate_delegate = SimpleNamespace(
            mandatory_slots={
                "group::m5x5::planter::0": [
                    SimpleNamespace(dims=(slot_w, 5)),
                ],
            },
            _template_pose_tuple_by_idx={
                "m5x5": {
                    101: (0, int(pose_y), 0),
                },
            },
        )


def _build_minimal_validation_model() -> tuple[MasterPlacementModel, dict[str, int]]:
    instances = [
        {
            "instance_id": "target_001",
            "facility_type": "target",
            "operation_type": "op",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "target": [
            {
                "pose_id": "pose_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 4}},
        "facility_templates": {
            "target": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
            },
        },
    }
    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )
    model.build()
    return model, {"target_001": 0}


def test_ghost_y_overlap_evaluator_detects_single_label_conflict() -> None:
    result = evaluate_ghost_y_overlap_forced_label_conflict(
        _FakeGhostOwner(pose_y=25),
        solution_hint={"planter_001": 101},
        ghost_anchor_hint_idx=0,
        force_fields=("y",),
    )

    assert result["evaluated"] is True
    assert result["conflict"] is True
    assert result["triggered"] is True
    assert result["reason"] == "ghost_y_overlap_forced_label_infeasible"
    assert result["first_conflict"]["slot_index"] == 0
    assert result["first_conflict"]["y_interval"] == {"start": 25, "end": 30}
    assert result["first_conflict"]["ghost_y_interval"] == {"start": 17, "end": 30}
    assert result["first_conflict"]["max_horizontal_strip_width"] == 2


def test_ghost_y_overlap_evaluator_ignores_non_overlapping_y() -> None:
    result = evaluate_ghost_y_overlap_forced_label_conflict(
        _FakeGhostOwner(pose_y=35),
        solution_hint={"planter_001": 101},
        ghost_anchor_hint_idx=0,
        force_fields=("y",),
    )

    assert result["evaluated"] is True
    assert result["conflict"] is False
    assert result["triggered"] is False
    assert result["reason"] == "no_ghost_y_overlap_forced_label_conflict"


def test_ghost_y_overlap_evaluator_respects_force_equality_filter() -> None:
    selected_key = "mandatory|group::m5x5::planter::0|0|planter_001|101|x"

    result = evaluate_ghost_y_overlap_forced_label_conflict(
        _FakeGhostOwner(pose_y=25),
        solution_hint={"planter_001": 101},
        ghost_anchor_hint_idx=0,
        force_fields=("y",),
        force_equality_keys={selected_key},
    )

    assert result["evaluated"] is True
    assert result["conflict"] is False
    assert result["forced_label_count"] == 0


def test_ghost_y_overlap_runtime_precheck_is_default_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, solution_hint = _build_minimal_validation_model()

    def _unexpected(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("ghost-y overlap precheck should be default-off")

    monkeypatch.delenv(EXACT_GHOST_Y_OVERLAP_FORCED_LABEL_PRECHECK_ENV, raising=False)
    monkeypatch.setattr(
        master_model_module,
        "evaluate_ghost_y_overlap_forced_label_conflict",
        _unexpected,
    )

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=0,
        time_limit_seconds=0.2,
        require_complete=True,
        force_fields=("y",),
    )

    assert validation["attempted"] is True
    assert validation["reason"] != "ghost_y_overlap_forced_label_infeasible"


def test_ghost_y_overlap_runtime_precheck_short_circuits_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, solution_hint = _build_minimal_validation_model()

    monkeypatch.setenv(EXACT_GHOST_Y_OVERLAP_FORCED_LABEL_PRECHECK_ENV, "true")
    monkeypatch.setattr(
        master_model_module,
        "evaluate_ghost_y_overlap_forced_label_conflict",
        lambda *args, **kwargs: {
            "evaluated": True,
            "conflict": True,
            "triggered": True,
            "reason": "ghost_y_overlap_forced_label_infeasible",
            "conflict_count": 1,
            "first_conflict": {"slot_index": 0, "field": "y"},
        },
    )

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=0,
        time_limit_seconds=0.2,
        require_complete=True,
        force_fields=("y",),
        collect_force_equality_labels=True,
    )

    assert validation["attempted"] is False
    assert validation["attempted_solver"] is False
    assert validation["status"] == "INFEASIBLE"
    assert validation["reason"] == "ghost_y_overlap_forced_label_infeasible"
    assert validation["forced_slot_field_count"] == 1
    assert validation["ghost_y_overlap_precheck"]["triggered"] is True
    assert validation["force_equality_labels"] == [{"slot_index": 0, "field": "y"}]


def test_ghost_y_overlap_runtime_precheck_non_conflict_continues_solver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, solution_hint = _build_minimal_validation_model()

    monkeypatch.setenv(EXACT_GHOST_Y_OVERLAP_FORCED_LABEL_PRECHECK_ENV, "true")
    monkeypatch.setattr(
        master_model_module,
        "evaluate_ghost_y_overlap_forced_label_conflict",
        lambda *args, **kwargs: {
            "evaluated": True,
            "conflict": False,
            "triggered": False,
            "reason": "no_ghost_y_overlap_forced_label_conflict",
        },
    )

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=0,
        time_limit_seconds=0.2,
        require_complete=True,
        force_fields=("y",),
    )

    assert validation["attempted"] is True
    assert validation["attempted_solver"] is True
    assert validation["reason"] != "ghost_y_overlap_forced_label_infeasible"
    assert validation["ghost_y_overlap_precheck"]["triggered"] is False
