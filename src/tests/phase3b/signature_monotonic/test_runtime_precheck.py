from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import src.models.master_model as master_model_module
from src.models.master_model import (
    EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK_ENV,
    MasterPlacementModel,
    evaluate_signature_monotonic_forced_label_conflict,
)


class _FakeOwner:
    _mandatory_groups = [
        {
            "group_id": "group::alpha::op::0",
            "facility_type": "alpha",
            "operation_type": "op",
            "count": 3,
            "instance_ids": ["alpha_001", "alpha_002", "alpha_003"],
        }
    ]
    _group_id_by_instance = {
        "alpha_001": "group::alpha::op::0",
        "alpha_002": "group::alpha::op::0",
        "alpha_003": "group::alpha::op::0",
    }

    def __init__(self) -> None:
        slot = SimpleNamespace(signature_id_to_bucket_id={0: "sig_000", 1: "sig_001", 2: "sig_002"})
        self._coordinate_delegate = SimpleNamespace(
            mandatory_slots={"group::alpha::op::0": [slot, slot, slot]},
            _mandatory_group_uses_signature_table={"group::alpha::op::0": False},
            _mandatory_group_bucket_pose_indices={
                "group::alpha::op::0": {
                    "sig_000": (10,),
                    "sig_001": (30,),
                    "sig_002": (20,),
                }
            },
            _template_pose_tuple_by_idx={
                "alpha": {
                    10: (0, 0, 0),
                    20: (2, 0, 0),
                    30: (1, 0, 0),
                }
            },
        )
        self._pose_order = {10: 0, 20: 1, 30: 2}

    def _pose_sort_key(self, tpl: str, pose_idx: int) -> int:
        del tpl
        return int(self._pose_order[int(pose_idx)])


class _ConjunctiveFakeOwner:
    _mandatory_groups = [
        {
            "group_id": "group::alpha::op::0",
            "facility_type": "alpha",
            "operation_type": "op",
            "count": 3,
            "instance_ids": ["alpha_001", "alpha_002", "alpha_003"],
        }
    ]
    _group_id_by_instance = {
        "alpha_001": "group::alpha::op::0",
        "alpha_002": "group::alpha::op::0",
        "alpha_003": "group::alpha::op::0",
    }

    def __init__(self) -> None:
        slot = SimpleNamespace(signature_id_to_bucket_id={0: "sig_000", 1: "sig_001", 2: "sig_002"})
        self._coordinate_delegate = SimpleNamespace(
            mandatory_slots={"group::alpha::op::0": [slot, slot, slot]},
            _mandatory_group_uses_signature_table={"group::alpha::op::0": False},
            _mandatory_group_bucket_pose_indices={
                "group::alpha::op::0": {
                    "sig_000": (10, 11),
                    "sig_001": (20,),
                    "sig_002": (30,),
                }
            },
            _template_pose_tuple_by_idx={
                "alpha": {
                    10: (0, 60, 1),
                    11: (0, 10, 0),
                    20: (1, 10, 1),
                    30: (2, 60, 0),
                }
            },
        )
        self._pose_order = {30: 0, 20: 1, 10: 2, 11: 3}

    def _pose_sort_key(self, tpl: str, pose_idx: int) -> int:
        del tpl
        return int(self._pose_order[int(pose_idx)])


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
        "globals": {"grid": {"width": 3, "height": 3}},
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


def test_signature_monotonic_evaluator_detects_forced_label_inversion() -> None:
    result = evaluate_signature_monotonic_forced_label_conflict(
        _FakeOwner(),
        solution_hint={"alpha_001": 10, "alpha_002": 20, "alpha_003": 30},
        force_fields=("x",),
    )

    assert result["evaluated"] is True
    assert result["conflict"] is True
    assert result["triggered"] is True
    assert result["reason"] == "signature_monotonic_forced_label_infeasible"
    assert result["failure"] == {
        "slot_index": 2,
        "previous_possible_signature_ids": [2],
        "current_allowed_signature_ids": [1],
    }


def test_signature_monotonic_evaluator_conjoins_same_slot_fields() -> None:
    selected_keys = {
        "mandatory|group::alpha::op::0|0|alpha_001|30|y",
        "mandatory|group::alpha::op::0|0|alpha_001|30|mode",
        "mandatory|group::alpha::op::0|1|alpha_002|20|mode",
    }

    result = evaluate_signature_monotonic_forced_label_conflict(
        _ConjunctiveFakeOwner(),
        solution_hint={"alpha_001": 30, "alpha_002": 20, "alpha_003": 10},
        force_fields=("y", "mode"),
        force_equality_keys=selected_keys,
    )

    assert result["evaluated"] is True
    assert result["conflict"] is True
    assert result["reason"] == "signature_monotonic_forced_label_infeasible"
    assert result["constrained_slots"][:2] == [
        {"slot_index": 0, "allowed_signature_ids": [2]},
        {"slot_index": 1, "allowed_signature_ids": [0, 1]},
    ]
    assert result["failure"] == {
        "slot_index": 1,
        "previous_possible_signature_ids": [2],
        "current_allowed_signature_ids": [0, 1],
    }


def test_signature_monotonic_evaluator_respects_force_equality_filter() -> None:
    owner = _FakeOwner()
    selected_key = (
        "mandatory|group::alpha::op::0|2|alpha_003|30|x"
    )

    result = evaluate_signature_monotonic_forced_label_conflict(
        owner,
        solution_hint={"alpha_001": 10, "alpha_002": 20, "alpha_003": 30},
        force_fields=("x",),
        force_equality_keys={selected_key},
    )

    assert result["evaluated"] is True
    assert result["conflict"] is False
    assert result["triggered"] is False
    assert result["reason"] == "no_signature_monotonic_conflict"


def test_signature_monotonic_runtime_precheck_is_default_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, solution_hint = _build_minimal_validation_model()

    def _unexpected(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("signature monotonic precheck should be default-off")

    monkeypatch.delenv(EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK_ENV, raising=False)
    monkeypatch.setattr(
        master_model_module,
        "evaluate_signature_monotonic_forced_label_conflict",
        _unexpected,
    )

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=None,
        time_limit_seconds=0.2,
        require_complete=True,
    )

    assert validation["attempted"] is True
    assert validation["reason"] != "signature_monotonic_forced_label_infeasible"


def test_signature_monotonic_runtime_precheck_short_circuits_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, solution_hint = _build_minimal_validation_model()

    monkeypatch.setenv(EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK_ENV, "true")
    monkeypatch.setattr(
        master_model_module,
        "evaluate_signature_monotonic_forced_label_conflict",
        lambda *args, **kwargs: {
            "evaluated": True,
            "conflict": True,
            "reason": "signature_monotonic_forced_label_infeasible",
            "group_id": "group::target::op::0",
            "forced_label_count": 2,
            "failure": {"slot_index": 1},
        },
    )

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=None,
        time_limit_seconds=0.2,
        require_complete=True,
    )

    assert validation["attempted"] is False
    assert validation["attempted_solver"] is False
    assert validation["status"] == "INFEASIBLE"
    assert validation["reason"] == "signature_monotonic_forced_label_infeasible"
    assert validation["forced_slot_field_count"] == 2
    assert validation["signature_monotonic_precheck"]["triggered"] is True
    assert validation["signature_monotonic_precheck"]["failure"] == {"slot_index": 1}


def test_signature_monotonic_runtime_precheck_non_conflict_continues_solver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, solution_hint = _build_minimal_validation_model()

    monkeypatch.setenv(EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK_ENV, "true")
    monkeypatch.setattr(
        master_model_module,
        "evaluate_signature_monotonic_forced_label_conflict",
        lambda *args, **kwargs: {
            "evaluated": True,
            "conflict": False,
            "reason": "no_signature_monotonic_conflict",
        },
    )

    validation = model._validate_coordinate_forced_hint(
        solution_hint=solution_hint,
        ghost_anchor_hint_idx=None,
        time_limit_seconds=0.2,
        require_complete=True,
    )

    assert validation["attempted"] is True
    assert validation["attempted_solver"] is True
    assert validation["reason"] != "signature_monotonic_forced_label_infeasible"
    assert validation["signature_monotonic_precheck"]["triggered"] is False
