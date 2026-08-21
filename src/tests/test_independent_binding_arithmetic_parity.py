"""Differential parity matrix for the independent binding arithmetic theorem.

The verifier itself remains free of production imports.  This regression places
the isolated capsule beside production CP-SAT on small capacity cases so a
future constraint-family or constructor-surface change cannot silently keep
using an obsolete closed-form theorem.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

from src.models.binding_subproblem import PortBindingModel
from src.search.independent_infeasibility_reverifier import (
    reverify_whole_layout_infeasibility,
)


_ARTIFACT_RELPATHS = {
    "canonical_rules": "rules/canonical_rules.json",
    "preprocess_plan": "rules/preprocess_plan.json",
    "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
    "candidate_placements": "data/preprocessed/candidate_placements.json",
    "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _port_cells(count: int, *, y: int, direction: str) -> list[dict[str, Any]]:
    return [{"x": index, "y": y, "dir": direction} for index in range(count)]


def _artifact_hashes(root: Path) -> dict[str, str]:
    return {
        key: hashlib.sha256((root / relpath).read_bytes()).hexdigest()
        for key, relpath in _ARTIFACT_RELPATHS.items()
    }


def test_independent_binding_arithmetic_matches_production_capacity_matrix(
    tmp_path: Path,
) -> None:
    rules = {
        "globals": {"logistics": {"belt_capacity_per_tick": 1}},
        "recipes": {},
        "commodity_metadata": {
            "ore": {"source_kind": "external_boundary", "sink_kind": "none"},
            "product": {
                "source_kind": "internal_only",
                "sink_kind": "generic_input",
            },
        },
    }
    plan = {
        "utility_operations": {
            "boundary_io": {
                "facility_type": "boundary_storage_port",
                "generic_input_slots": 0,
                "generic_output_slots": 1,
            },
            "protocol_core": {
                "facility_type": "protocol_core",
                "generic_input_slots": 14,
                "generic_output_slots": 6,
            },
            "box_sink": {
                "facility_type": "protocol_storage_box",
                "generic_input_slots": 3,
                "generic_output_slots": 0,
            },
            "power_supply": {
                "facility_type": "power_pole",
                "generic_input_slots": 0,
                "generic_output_slots": 0,
            },
        }
    }
    facility_pools = {
        "boundary_storage_port": [
            {
                "pose_id": "source_pose",
                "input_port_cells": [],
                "output_port_cells": _port_cells(1, y=4, direction="N"),
            }
        ],
        "protocol_storage_box": [
            {
                "pose_id": "box_pose",
                "input_port_cells": _port_cells(3, y=8, direction="S"),
                "output_port_cells": [],
            }
        ],
    }
    _write_json(tmp_path / "rules/canonical_rules.json", rules)
    _write_json(tmp_path / "rules/preprocess_plan.json", plan)
    _write_json(
        tmp_path / "data/preprocessed/candidate_placements.json",
        {"facility_pools": facility_pools},
    )
    input_map = {"box_sink": 3, "protocol_core": 14}
    output_map = {"boundary_io": 1, "protocol_core": 6}
    utility_operation_map = {
        "boundary_storage_port": "boundary_io",
        "power_pole": "power_supply",
        "protocol_core": "protocol_core",
        "protocol_storage_box": "box_sink",
    }
    semantics_contract = {
        "schema": "binding_semantics_contract_v1",
        "constructor_parameters": sorted(
            name
            for name in inspect.signature(PortBindingModel.__init__).parameters
            if name != "self"
        ),
        "build_parameters": sorted(
            name
            for name in inspect.signature(PortBindingModel.build).parameters
            if name != "self"
        ),
        "constraint_families": [
            "fixed_pose_side_injection",
            "generic_input_exact_cardinality",
            "generic_output_exact_cardinality",
        ],
        "routing_context_enabled": False,
        "overload_separation_enabled": False,
        "reverification_selection_nogood_count": 0,
        "source_rejected_selection_count": 0,
        "generic_input_slot_policy": "plan_derived_physical_exact_count",
        "generic_output_slot_policy": "plan_derived_physical_exact_count",
        "plan_generic_input_slots_by_operation": input_map,
        "plan_generic_output_slots_by_operation": output_map,
        "plan_utility_operation_by_template": utility_operation_map,
    }

    cases = (
        (0, 0, 0, 0),
        (0, 1, 1, 1),
        (1, 0, 1, 1),
        (1, 1, 1, 1),
        (1, 1, 2, 1),
        (1, 1, 1, 4),
        (2, 1, 2, 3),
        (2, 1, 3, 3),
        (2, 2, 2, 6),
        (3, 2, 3, 7),
    )
    for source_count, box_count, required_outputs, required_inputs in cases:
        instances = [
            *[
                {
                    "instance_id": f"source_{index}",
                    "facility_type": "boundary_storage_port",
                    "operation_type": "boundary_io",
                    "is_mandatory": True,
                }
                for index in range(source_count)
            ],
            *[
                {
                    "instance_id": f"box_{index}",
                    "facility_type": "protocol_storage_box",
                    "operation_type": "box_sink",
                    "is_mandatory": True,
                }
                for index in range(box_count)
            ],
        ]
        solution = {
            str(instance["instance_id"]): {
                "facility_type": str(instance["facility_type"]),
                "pose_idx": 0,
            }
            for instance in instances
        }
        requirements = {
            "required_generic_outputs": (
                {} if required_outputs == 0 else {"ore": required_outputs}
            ),
            "required_generic_inputs": (
                {} if required_inputs == 0 else {"product": required_inputs}
            ),
        }
        _write_json(
            tmp_path / "data/preprocessed/generic_io_requirements.json",
            requirements,
        )
        _write_json(
            tmp_path / "data/preprocessed/mandatory_exact_instances.json",
            instances,
        )
        binding_kwargs = {
            "required_generic_outputs": requirements["required_generic_outputs"],
            "required_generic_inputs": requirements["required_generic_inputs"],
            "generic_input_slots_by_operation": input_map,
            "generic_output_slots_by_operation": output_map,
            "utility_operation_by_template": utility_operation_map,
            "canonical_rules_payload": rules,
        }

        production = PortBindingModel(
            placement_solution=solution,
            facility_pools=facility_pools,
            instances=instances,
            project_root=tmp_path,
            **binding_kwargs,
        )
        production.build(use_overload_separation=False)
        production_status = production.solve(time_limit_seconds=2.0)
        independent = reverify_whole_layout_infeasibility(
            solution=solution,
            facility_pools=facility_pools,
            instances=instances,
            project_root=tmp_path,
            proof_stage="binding",
            binding_exhausted=True,
            routing_exhausted=False,
            binding_kwargs=binding_kwargs,
            artifact_hashes=_artifact_hashes(tmp_path),
            binding_semantics_contract=semantics_contract,
            time_limit_seconds=2.0,
        )

        expected_infeasible = (
            required_outputs > source_count or required_inputs > 3 * box_count
        )
        assert production_status == (
            "INFEASIBLE" if expected_infeasible else "FEASIBLE"
        )
        assert independent.confirmed is expected_infeasible
        assert independent.independent_status == (
            "ARITHMETIC_INFEASIBLE"
            if expected_infeasible
            else "CONSTRUCTIVE_FEASIBLE"
        )
        assert independent.details["certificate_check"]["ok"] is True
