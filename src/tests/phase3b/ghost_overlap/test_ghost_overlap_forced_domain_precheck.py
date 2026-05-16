from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import src.models.master_model as master_model_module
from src.models.master_model import (
    EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK_ENV,
    MasterPlacementModel,
    evaluate_ghost_overlap_forced_domain_conflict,
)


class _FakeDomainOwner:
    grid_w = 70
    grid_h = 70
    ghost_rect = (67, 13)
    _ghost_domains = [{"anchor": {"x": 2, "y": 2}}]
    _mandatory_groups = [
        {
            "group_id": "group::boundary_storage_port::boundary_io::0",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "count": 1,
            "instance_ids": ["boundary_port_046"],
        }
    ]
    _group_id_by_instance = {
        "boundary_port_046": "group::boundary_storage_port::boundary_io::0"
    }

    def __init__(self, *, allowed_tuples: list[tuple[int, int, int]]) -> None:
        self._coordinate_delegate = SimpleNamespace(
            mandatory_slots={
                "group::boundary_storage_port::boundary_io::0": [
                    SimpleNamespace(dims=(1, 3), allowed_tuples=list(allowed_tuples)),
                ],
            },
            _template_pose_tuple_by_idx={
                "boundary_storage_port": {
                    133: (67, 0, 1),
                },
            },
        )

    def _pose_sort_key(self, tpl: str, pose_idx: int) -> int:
        del tpl
        return int(pose_idx)


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


def test_forced_domain_evaluator_detects_x_label_implied_ghost_overlap() -> None:
    result = evaluate_ghost_overlap_forced_domain_conflict(
        _FakeDomainOwner(allowed_tuples=[(67, 0, 1)]),
        solution_hint={"boundary_port_046": 133},
        ghost_anchor_hint_idx=0,
        force_fields=("x",),
    )

    assert result["evaluated"] is True
    assert result["conflict"] is True
    assert result["triggered"] is True
    assert result["reason"] == "ghost_overlap_forced_domain_infeasible"
    first = result["first_conflict"]
    assert first["slot_index"] == 0
    assert first["forced_fields"] == {"x": 67}
    assert first["compatible_tuple_count"] == 1
    assert first["compatible_rows"] == [{"x": 67, "y": 0, "mode": 1}]


def test_forced_domain_evaluator_requires_all_compatible_rows_to_overlap() -> None:
    result = evaluate_ghost_overlap_forced_domain_conflict(
        _FakeDomainOwner(allowed_tuples=[(67, 0, 1), (67, 20, 1)]),
        solution_hint={"boundary_port_046": 133},
        ghost_anchor_hint_idx=0,
        force_fields=("x",),
    )

    assert result["evaluated"] is True
    assert result["conflict"] is False
    assert result["triggered"] is False
    assert result["reason"] == "no_ghost_overlap_forced_domain_conflict"


def test_forced_domain_evaluator_respects_force_equality_filter() -> None:
    selected_key = (
        "mandatory|group::boundary_storage_port::boundary_io::0|0|"
        "boundary_port_046|133|y"
    )

    result = evaluate_ghost_overlap_forced_domain_conflict(
        _FakeDomainOwner(allowed_tuples=[(67, 0, 1)]),
        solution_hint={"boundary_port_046": 133},
        ghost_anchor_hint_idx=0,
        force_fields=("x",),
        force_equality_keys={selected_key},
    )

    assert result["evaluated"] is True
    assert result["conflict"] is False
    assert result["forced_label_count"] == 0


def test_forced_domain_runtime_precheck_is_default_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, solution_hint = _build_minimal_validation_model()

    def _unexpected(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("forced-domain overlap precheck should be default-off")

    monkeypatch.delenv(EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK_ENV, raising=False)
    monkeypatch.setattr(
        master_model_module,
        "evaluate_ghost_overlap_forced_domain_conflict",
        _unexpected,
    )

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=0,
        time_limit_seconds=0.2,
        require_complete=True,
        force_fields=("x",),
    )

    assert validation["attempted"] is True
    assert validation["reason"] != "ghost_overlap_forced_domain_infeasible"


def test_forced_domain_runtime_precheck_short_circuits_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, solution_hint = _build_minimal_validation_model()

    monkeypatch.setenv(EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK_ENV, "true")
    monkeypatch.setattr(
        master_model_module,
        "evaluate_ghost_overlap_forced_domain_conflict",
        lambda *args, **kwargs: {
            "evaluated": True,
            "conflict": True,
            "triggered": True,
            "reason": "ghost_overlap_forced_domain_infeasible",
            "forced_label_count": 1,
            "first_conflict": {
                "slot_index": 0,
                "selected_labels": [{"slot_index": 0, "field": "x"}],
            },
        },
    )

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=0,
        time_limit_seconds=0.2,
        require_complete=True,
        force_fields=("x",),
        collect_force_equality_labels=True,
    )

    assert validation["attempted"] is False
    assert validation["attempted_solver"] is False
    assert validation["status"] == "INFEASIBLE"
    assert validation["reason"] == "ghost_overlap_forced_domain_infeasible"
    assert validation["forced_slot_field_count"] == 1
    assert validation["ghost_overlap_forced_domain_precheck"]["triggered"] is True
    assert validation["force_equality_labels"] == [{"slot_index": 0, "field": "x"}]
