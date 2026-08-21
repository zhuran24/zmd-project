"""Parity sentinels for the independent binding sidecar projection.

These tests do not use production as the sidecar's oracle for a verdict.  They
pin one boundary where the two encodings must describe the same input contract:
the frozen per-operation generic-input count equals, rather than merely fits
within, the selected pose's physical input-port count.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from src.models.binding_subproblem import PortBindingModel


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EMITTER_PATH = PROJECT_ROOT / "certside" / "sidecar" / "emitter.py"
CANONICAL_CHECKER_PATH = (
    PROJECT_ROOT / "certside" / "sidecar" / "canonical_witness_checker.py"
)


def _load_sidecar_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load independent sidecar module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_sidecar_emitter() -> ModuleType:
    return _load_sidecar_module(
        EMITTER_PATH,
        "binding_sidecar_emitter_projection_parity",
    )


def _load_canonical_checker() -> ModuleType:
    return _load_sidecar_module(
        CANONICAL_CHECKER_PATH,
        "binding_sidecar_canonical_checker_projection_parity",
    )


def _port_cells(count: int) -> list[dict[str, Any]]:
    return [
        {"x": index, "y": 7, "dir": "N"}
        for index in range(count)
    ]


def _sidecar_payload(physical_port_count: int) -> dict[str, Any]:
    return {
        "schema": "binding_sidecar_model_input_v1",
        "placement_solution": {
            "box_0": {
                "facility_type": "protocol_storage_box",
                "pose_idx": 0,
            }
        },
        "facility_pools": {
            "protocol_storage_box": [
                {
                    "pose_id": "box_pose",
                    "input_port_cells": _port_cells(physical_port_count),
                    "output_port_cells": [],
                }
            ]
        },
        "instances": [
            {
                "instance_id": "box_0",
                "facility_type": "protocol_storage_box",
                "operation_type": "box_sink",
            }
        ],
        "required_generic_outputs": {},
        "required_generic_inputs": {"product": 1},
        "generic_input_slots_by_operation": {"box_sink": 3},
        "plan_utility_operation_by_template": {
            "protocol_storage_box": "box_sink",
        },
        "commodity_metadata": {
            "product": {"sink_kind": "generic_input"},
        },
        "operation_profiles": {
            "box_sink": {
                "facility_type": "protocol_storage_box",
                "input_slot_counts": {},
                "output_slot_counts": {},
                "generic_input_slots": 3,
                "generic_output_slots": 0,
            }
        },
    }


def _production_model(physical_port_count: int) -> PortBindingModel:
    return PortBindingModel(
        placement_solution={
            "box_0": {
                "facility_type": "protocol_storage_box",
                "pose_idx": 0,
            }
        },
        facility_pools={
            "protocol_storage_box": [
                {
                    "pose_id": "box_pose",
                    "input_port_cells": _port_cells(physical_port_count),
                    "output_port_cells": [],
                }
            ]
        },
        instances=[
            {
                "instance_id": "box_0",
                "facility_type": "protocol_storage_box",
                "operation_type": "box_sink",
            }
        ],
        required_generic_outputs={},
        required_generic_inputs={"product": 1},
        generic_input_slots_by_operation={"box_sink": 3},
        utility_operation_by_template={
            "protocol_storage_box": "box_sink"
        },
        canonical_commodity_metadata={
            "product": {"sink_kind": "generic_input"},
        },
    )


def test_generic_input_exact_physical_count_is_accepted_by_both_encodings() -> None:
    sidecar = _load_sidecar_emitter()

    emitted = sidecar.emit(_sidecar_payload(physical_port_count=3))
    production = _production_model(physical_port_count=3)
    production.build(use_overload_separation=False)

    assert emitted["report"]["generic_input_slots"] == 3
    assert len(production.generic_input_slots) == 3


@pytest.mark.parametrize("physical_port_count", [2, 4])
def test_generic_input_count_drift_is_rejected_by_both_encodings(
    physical_port_count: int,
) -> None:
    sidecar = _load_sidecar_emitter()

    with pytest.raises(
        sidecar.EmitterReject,
        match="GENERIC_INPUT_PORT_CAPACITY_DRIFT",
    ):
        sidecar.emit(_sidecar_payload(physical_port_count))

    production = _production_model(physical_port_count)
    with pytest.raises(ValueError, match="generic input capacity drift"):
        production.build(use_overload_separation=False)


def _satisfying_witness(emitted: dict[str, Any]) -> dict[int, int]:
    witness: dict[int, int] = {}
    product_used = False
    for number, semantic in enumerate(emitted["varmap"]["variables"], start=1):
        if semantic["kind"] != "generic_input":
            witness[number] = 0
            continue
        commodity = str(semantic["commodity"])
        if commodity == "product" and not product_used:
            witness[number] = 1
            product_used = True
        elif commodity == "__unused__":
            slot_id = str(semantic["slot"]["slot_id"])
            has_product = any(
                other["kind"] == "generic_input"
                and str(other["slot"]["slot_id"]) == slot_id
                and str(other["commodity"]) == "product"
                and witness.get(index, 0) == 1
                for index, other in enumerate(
                    emitted["varmap"]["variables"], start=1
                )
            )
            witness[number] = 0 if has_product else 1
        else:
            witness[number] = 0
    return witness


def test_canonical_checker_accepts_exact_generic_input_physical_count() -> None:
    emitter = _load_sidecar_emitter()
    checker = _load_canonical_checker()
    payload = _sidecar_payload(physical_port_count=3)
    emitted = emitter.emit(payload)

    verdict = checker.check_canonical_witness(
        payload,
        emitted["varmap"],
        emitted["patterns"],
        _satisfying_witness(emitted),
    )

    assert verdict["ok"] is True, verdict["failures"]


@pytest.mark.parametrize("physical_port_count", [2, 4])
def test_canonical_checker_rejects_generic_input_shortfall_and_surplus(
    physical_port_count: int,
) -> None:
    checker = _load_canonical_checker()
    payload = _sidecar_payload(physical_port_count=physical_port_count)

    verdict = checker.check_canonical_witness(
        payload,
        {"schema": "binding_sidecar_varmap_v1", "variables": []},
        {
            "schema": "binding_sidecar_patterns_v1",
            "fixed_choices": {},
            "by_instance": {},
        },
        {},
    )

    assert verdict["ok"] is False
    assert any(
        f"declares 3 generic input slots but pose has {physical_port_count}" in failure
        for failure in verdict["failures"]
    )
