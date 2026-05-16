from __future__ import annotations

from typing import Any, Mapping

from src.models.master_model import (
    MasterPlacementModel,
    evaluate_same_x_strip_fixed_ghost_capacity_conflict,
)


def _build_same_x_model(
    *,
    slot_count: int,
    pose_x: int = 0,
    pose_ys: list[int] | None = None,
    ghost_rect: tuple[int, int] = (67, 13),
    grid_w: int = 70,
    grid_h: int = 70,
    template_w: int = 5,
    template_h: int = 5,
) -> tuple[MasterPlacementModel, dict[str, int]]:
    pose_ys = list(pose_ys or [0, *[16 + 5 * idx for idx in range(max(0, slot_count - 1))]])
    instances = [
        {
            "instance_id": f"target_{idx + 1:03d}",
            "facility_type": "target",
            "operation_type": "op",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for idx in range(slot_count)
    ]
    pools = {
        "target": [
            {
                "pose_id": f"pose_{idx}",
                "anchor": {"x": int(pose_x), "y": int(y)},
                "occupied_cells": [
                    [int(pose_x) + dx, int(y) + dy]
                    for dx in range(template_w)
                    for dy in range(template_h)
                ],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for idx, y in enumerate(pose_ys[:slot_count])
        ]
    }
    rules = {
        "globals": {"grid": {"width": int(grid_w), "height": int(grid_h)}},
        "facility_templates": {
            "target": {
                "dimensions": {"w": int(template_w), "h": int(template_h)},
                "needs_power": False,
            },
        },
    }
    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
    )
    model.build()
    solution_hint = {f"target_{idx + 1:03d}": idx for idx in range(slot_count)}
    return model, solution_hint


def _anchor_idx(*, x: int, y: int, grid_h: int = 70, ghost_h: int = 13) -> int:
    return int(x) * (int(grid_h) - int(ghost_h) + 1) + int(y)


def test_same_x_strip_runtime_precheck_defaults_to_off() -> None:
    model, solution_hint = _build_same_x_model(slot_count=11)

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=_anchor_idx(x=2, y=3),
        time_limit_seconds=1.0,
        require_complete=True,
        force_fields=("x",),
    )

    assert validation["reason"] != "same_x_strip_fixed_ghost_capacity_conflict"
    assert validation["attempted"] is True
    assert validation.get("attempted_solver", True) is True


def test_anchor119_11_same_x_slots_rejected_before_solver(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_SAME_X_STRIP_FIXED_GHOST_CAPACITY_PRECHECK", "1")
    model, solution_hint = _build_same_x_model(slot_count=11)

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=_anchor_idx(x=2, y=3),
        time_limit_seconds=1.0,
        require_complete=True,
        force_fields=("x",),
    )

    assert validation["status"] == "INFEASIBLE"
    assert validation["accepted"] is False
    assert validation["attempted"] is False
    assert validation["attempted_solver"] is False
    assert validation["reason"] == "same_x_strip_fixed_ghost_capacity_conflict"
    detail = validation["capacity_conflict"]
    assert detail["forced_count"] == 11
    assert detail["capacity"] == 10
    assert detail["lower_capacity"] == 0
    assert detail["upper_capacity"] == 10
    assert detail["ghost_rect"] == {"x": 2, "y": 3, "w": 67, "h": 13}
    assert detail["x_interval"] == {"start": 0, "end": 5}


def test_10_same_x_slots_fall_through_to_solver() -> None:
    model, solution_hint = _build_same_x_model(
        slot_count=10,
        pose_ys=[16 + 5 * idx for idx in range(10)],
    )

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=_anchor_idx(x=2, y=3),
        time_limit_seconds=1.0,
        require_complete=True,
        force_fields=("x",),
    )

    assert validation["reason"] != "same_x_strip_fixed_ghost_capacity_conflict"
    assert validation["attempted"] is True
    assert validation.get("attempted_solver", True) is True
    assert validation["status"] in {"OPTIMAL", "FEASIBLE"}


def test_no_x_overlap_does_not_reject() -> None:
    model, solution_hint = _build_same_x_model(
        slot_count=11,
        ghost_rect=(5, 13),
    )

    result = evaluate_same_x_strip_fixed_ghost_capacity_conflict(
        model,
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=_anchor_idx(x=6, y=3),
        force_fields=("x",),
    )

    assert result["conflict"] is False
    assert result["reason"] == "no_conflicting_same_x_bucket"
    assert result["bucket_count"] == 0


def test_mixed_slot_heights_skip_without_rejection() -> None:
    owner = _FakeOwner(
        slot_specs=[
            _FakeSlot(dims=(5, 5)),
            _FakeSlot(dims=(5, 6)),
        ],
        pose_tuples={0: (0, 0, 0), 1: (0, 16, 0)},
    )

    result = evaluate_same_x_strip_fixed_ghost_capacity_conflict(
        owner,
        solution_hint={"target_001": 0, "target_002": 1},
        ghost_anchor_hint_idx=0,
        force_fields=("x",),
    )

    assert result["conflict"] is False
    assert result["reason"] == "no_conflicting_same_x_bucket"
    assert result["skipped_buckets"][0]["reason"] == "mixed_slot_heights"


def test_missing_ghost_anchor_skips_without_rejection() -> None:
    model, solution_hint = _build_same_x_model(slot_count=11)

    result = evaluate_same_x_strip_fixed_ghost_capacity_conflict(
        model,
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=None,
        force_fields=("x",),
    )

    assert result == {
        "evaluated": False,
        "conflict": False,
        "reason": "ghost_anchor_hint_unavailable",
    }


class _FakeSlot:
    def __init__(self, *, dims: tuple[int, int]) -> None:
        self.dims = dims


class _FakeDelegate:
    def __init__(
        self,
        *,
        slot_specs: list[_FakeSlot],
        pose_tuples: Mapping[int, tuple[int, int, int]],
    ) -> None:
        self.mandatory_slots = {"group::target::op::0": list(slot_specs)}
        self.required_optional_slots: dict[str, list[Any]] = {}
        self._template_pose_tuple_by_idx = {"target": dict(pose_tuples)}


class _FakeOwner:
    grid_w = 70
    grid_h = 70
    ghost_rect = (67, 13)
    _ghost_domains = [{"anchor": {"x": 2, "y": 3}, "cells": []}]
    _mandatory_groups = [
        {
            "group_id": "group::target::op::0",
            "facility_type": "target",
            "operation_type": "op",
            "count": 2,
            "instance_ids": ["target_001", "target_002"],
        }
    ]
    _group_id_by_instance = {
        "target_001": "group::target::op::0",
        "target_002": "group::target::op::0",
    }

    def __init__(
        self,
        *,
        slot_specs: list[_FakeSlot],
        pose_tuples: Mapping[int, tuple[int, int, int]],
    ) -> None:
        self._coordinate_delegate = _FakeDelegate(
            slot_specs=slot_specs,
            pose_tuples=pose_tuples,
        )

    def _pose_sort_key(self, tpl: str, pose_idx: int) -> int:
        del tpl
        return int(pose_idx)

    def _infer_optional_template_from_solution_id(self, solution_id: str) -> None:
        del solution_id
        return None
