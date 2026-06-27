"""Independent recomputation verifier for the material skeleton sidecar."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.interchange.preprocess_context import load_preprocess_context_from_paths
from src.io.strict_json import load_strict_json
from src.preprocess.material_skeleton import (
    DEFAULT_SKELETON_RELATIVE_PATH,
    canonicalize_skeleton,
    material_skeleton_digest,
)

SCHEMA_VERSION = 1
PRODUCTION_GROUP_PREFIX = "operation:"
WAREHOUSE_SOURCE_GROUP_ID = "warehouse:generic_output_pool"
WAREHOUSE_SINK_GROUP_ID = "warehouse:generic_input_pool"


class MaterialSkeletonVerificationError(RuntimeError):
    """Raised when the checked-in sidecar does not match a fresh derivation."""


@dataclass(frozen=True)
class MaterialSkeletonVerification:
    ok: bool
    expected_digest: str
    actual_digest: str
    reason: str | None = None


def verify_material_skeleton_file(
    skeleton_path: Path | str | None = None,
    *,
    project_root: Path | str | None = None,
    raise_on_mismatch: bool = True,
) -> MaterialSkeletonVerification:
    root = Path(project_root) if project_root is not None else _project_root()
    path = Path(skeleton_path) if skeleton_path is not None else root / DEFAULT_SKELETON_RELATIVE_PATH

    actual_payload = canonicalize_skeleton(load_strict_json(path))
    expected_payload = _recompute_expected_skeleton(root)
    actual_digest = material_skeleton_digest(actual_payload)
    expected_digest = material_skeleton_digest(expected_payload)
    if actual_payload == expected_payload:
        return MaterialSkeletonVerification(
            ok=True,
            expected_digest=expected_digest,
            actual_digest=actual_digest,
        )

    reason = (
        "material_connection_skeleton_mismatch:"
        f"expected={expected_digest}:actual={actual_digest}"
    )
    if raise_on_mismatch:
        raise MaterialSkeletonVerificationError(reason)
    return MaterialSkeletonVerification(
        ok=False,
        expected_digest=expected_digest,
        actual_digest=actual_digest,
        reason=reason,
    )


def _recompute_expected_skeleton(root: Path) -> dict[str, Any]:
    rules_path = root / "rules" / "canonical_rules.json"
    plan_path = root / "rules" / "preprocess_plan.json"
    data_dir = root / "data" / "preprocessed"

    context = load_preprocess_context_from_paths(
        rules_path=rules_path,
        plan_path=plan_path,
    )
    machine_counts = _load_strict_int_map(data_dir / "machine_counts.json", "machine_counts")
    mandatory_instances = _load_mandatory_instances(data_dir / "mandatory_exact_instances.json")
    generic_io_requirements = _load_generic_io_requirements(data_dir / "generic_io_requirements.json")
    commodity_demands = _load_optional_number_map(data_dir / "commodity_demands.json")
    operation_instances = _operation_instances_by_type(mandatory_instances)
    material_edges = _material_edges(
        context=context,
        machine_counts=machine_counts,
        generic_io_requirements=generic_io_requirements,
        commodity_demands=commodity_demands,
    )

    skeleton = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "material_connection_skeleton",
        "classification": "exploratory_diagnostic_sidecar",
        "generated_by": "src/preprocess/material_skeleton.py",
        "source_derivation": {
            "canonical_rules": "rules/canonical_rules.json",
            "preprocess_plan_read_only_cycle_and_utility_overlay": "rules/preprocess_plan.json",
            "machine_counts": "data/preprocessed/machine_counts.json",
            "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
            "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
            "commodity_demands": "data/preprocessed/commodity_demands.json",
            "source_hashes_recorded": False,
        },
        "certification_policy": {
            "may_feed_certified_gate": False,
            "may_feed_candidate_terminal_public_evidence": False,
            "may_feed_receipt_digest_reference": False,
            "may_generate_cut": False,
            "may_be_used_as_proof_input": False,
            "throughput_capacity_metrics_in_scope": False,
        },
        "totals": _totals(
            context=context,
            machine_counts=machine_counts,
            mandatory_instances=mandatory_instances,
            material_edges=material_edges,
        ),
        "node_groups": _recipe_groups(
            context=context,
            machine_counts=machine_counts,
            operation_instances=operation_instances,
        ),
        "warehouses": _warehouse_summary(
            mandatory_instances=mandatory_instances,
            generic_io_requirements=generic_io_requirements,
        ),
        "material_edges": material_edges,
        "equivalence_classes": _equivalence_classes(
            context=context,
            machine_counts=machine_counts,
            operation_instances=operation_instances,
            material_edges=material_edges,
        ),
        "cycle_material_groups": _cycle_material_groups(context),
        "consistency_checks": _consistency_checks(
            context=context,
            machine_counts=machine_counts,
            mandatory_instances=mandatory_instances,
            operation_instances=operation_instances,
            material_edges=material_edges,
        ),
    }
    return canonicalize_skeleton(skeleton)


def _strict_mapping(payload: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError(f"{label} must be a JSON object")
    return payload


def _load_strict_int_map(path: Path, label: str) -> dict[str, int]:
    payload = _strict_mapping(load_strict_json(path), label)
    result: dict[str, int] = {}
    for raw_key, raw_value in sorted(payload.items(), key=lambda item: str(item[0])):
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise TypeError(f"{label}.{raw_key} must be an integer")
        if raw_value < 0:
            raise ValueError(f"{label}.{raw_key} must be non-negative")
        result[str(raw_key)] = int(raw_value)
    return result


def _load_optional_number_map(path: Path) -> dict[str, int | float]:
    if not path.exists():
        return {}
    payload = _strict_mapping(load_strict_json(path), "commodity_demands")
    result: dict[str, int | float] = {}
    for raw_key, raw_value in sorted(payload.items(), key=lambda item: str(item[0])):
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise TypeError(f"commodity_demands.{raw_key} must be numeric")
        if not math.isfinite(float(raw_value)) or float(raw_value) < 0.0:
            raise ValueError(f"commodity_demands.{raw_key} must be finite and non-negative")
        result[str(raw_key)] = int(raw_value) if isinstance(raw_value, int) else float(raw_value)
    return result


def _load_generic_io_requirements(path: Path) -> dict[str, dict[str, int]]:
    payload = _strict_mapping(load_strict_json(path), "generic_io_requirements")
    result: dict[str, dict[str, int]] = {}
    for section in ("required_generic_outputs", "required_generic_inputs"):
        raw_section = _strict_mapping(payload.get(section), f"generic_io_requirements.{section}")
        section_result: dict[str, int] = {}
        for raw_key, raw_value in sorted(raw_section.items(), key=lambda item: str(item[0])):
            if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                raise TypeError(f"generic_io_requirements.{section}.{raw_key} must be an integer")
            if raw_value < 0:
                raise ValueError(f"generic_io_requirements.{section}.{raw_key} must be non-negative")
            section_result[str(raw_key)] = int(raw_value)
        result[section] = section_result
    return result


def _load_mandatory_instances(path: Path) -> list[dict[str, Any]]:
    payload = load_strict_json(path)
    if not isinstance(payload, list):
        raise TypeError("mandatory_exact_instances must be a JSON array")
    instances: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_instance in enumerate(payload):
        if not isinstance(raw_instance, Mapping):
            raise TypeError(f"mandatory_exact_instances[{index}] must be a JSON object")
        instance = dict(raw_instance)
        instance_id = str(instance.get("instance_id", "")).strip()
        if not instance_id:
            raise ValueError(f"mandatory_exact_instances[{index}].instance_id must be non-empty")
        if instance_id in seen_ids:
            raise ValueError(f"duplicate mandatory instance_id: {instance_id}")
        seen_ids.add(instance_id)
        instances.append(instance)
    return instances


def _operation_instances_by_type(instances: Iterable[Mapping[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for instance in instances:
        operation_type = str(instance.get("operation_type", "")).strip()
        instance_id = str(instance.get("instance_id", "")).strip()
        if operation_type and instance_id:
            grouped.setdefault(operation_type, []).append(instance_id)
    return {key: sorted(values) for key, values in sorted(grouped.items())}


def _recipe_groups(
    *,
    context: Any,
    machine_counts: Mapping[str, int],
    operation_instances: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for recipe_id, recipe in sorted(context.recipes.items()):
        groups.append(
            {
                "group_id": _operation_group_id(recipe_id),
                "kind": "production_operation_group",
                "operation_type": recipe_id,
                "facility_type": recipe.template,
                "machine_count": int(machine_counts.get(recipe_id, 0)),
                "instance_ids": list(operation_instances.get(recipe_id, ())),
                "input_commodities": sorted(recipe.inputs),
                "output_commodities": sorted(recipe.outputs),
                "port_profile": _recipe_port_profile(context, recipe_id),
            }
        )
    return groups


def _material_edges(
    *,
    context: Any,
    machine_counts: Mapping[str, int],
    generic_io_requirements: Mapping[str, Mapping[str, int]],
    commodity_demands: Mapping[str, int | float],
) -> list[dict[str, Any]]:
    all_commodities: set[str] = set(context.commodity_roles)
    all_commodities.update(commodity_demands)
    all_commodities.update(generic_io_requirements["required_generic_outputs"])
    all_commodities.update(generic_io_requirements["required_generic_inputs"])
    for recipe in context.recipes.values():
        all_commodities.update(recipe.inputs)
        all_commodities.update(recipe.outputs)

    edges: list[dict[str, Any]] = []
    for commodity_id in sorted(all_commodities):
        role = context.commodity_role(commodity_id)
        producers: list[dict[str, Any]] = []
        consumers: list[dict[str, Any]] = []
        if role.source_kind == "external_boundary":
            producers.append(
                {
                    "group_id": WAREHOUSE_SOURCE_GROUP_ID,
                    "kind": "warehouse_source",
                    "slot_count": int(
                        generic_io_requirements["required_generic_outputs"].get(commodity_id, 0)
                    ),
                }
            )
        if role.sink_kind == "generic_input":
            consumers.append(
                {
                    "group_id": WAREHOUSE_SINK_GROUP_ID,
                    "kind": "warehouse_sink",
                    "slot_count": int(
                        generic_io_requirements["required_generic_inputs"].get(commodity_id, 0)
                    ),
                }
            )
        for recipe_id, recipe in sorted(context.recipes.items()):
            if commodity_id in recipe.outputs:
                producers.append(_operation_endpoint(recipe_id, machine_counts))
            if commodity_id in recipe.inputs:
                consumers.append(_operation_endpoint(recipe_id, machine_counts))
        if producers or consumers:
            edges.append(
                {
                    "commodity_id": commodity_id,
                    "network_model": "pooled_multi_source_multi_sink",
                    "source_kind": role.source_kind,
                    "sink_kind": role.sink_kind,
                    "cycle_group": role.cycle_group,
                    "realized_demand_per_tick": commodity_demands.get(commodity_id, 0),
                    "producers": sorted(producers, key=lambda item: str(item["group_id"])),
                    "consumers": sorted(consumers, key=lambda item: str(item["group_id"])),
                    "pool_exchangeable": len(producers) > 1 or len(consumers) > 1,
                }
            )
    return edges


def _operation_endpoint(recipe_id: str, machine_counts: Mapping[str, int]) -> dict[str, Any]:
    return {
        "group_id": _operation_group_id(recipe_id),
        "kind": "operation_group",
        "operation_type": recipe_id,
        "machine_count": int(machine_counts.get(recipe_id, 0)),
    }


def _operation_group_id(recipe_id: str) -> str:
    return f"{PRODUCTION_GROUP_PREFIX}{recipe_id}"


def _recipe_port_profile(context: Any, recipe_id: str) -> dict[str, Any]:
    recipe = context.recipes[recipe_id]
    return {
        "inputs": {
            commodity_id: _port_rate_payload(
                amount=amount,
                ticks_per_cycle=recipe.ticks_per_cycle,
                belt_capacity_per_tick=context.belt_capacity_per_tick,
            )
            for commodity_id, amount in sorted(recipe.inputs.items())
        },
        "outputs": {
            commodity_id: _port_rate_payload(
                amount=amount,
                ticks_per_cycle=recipe.ticks_per_cycle,
                belt_capacity_per_tick=context.belt_capacity_per_tick,
            )
            for commodity_id, amount in sorted(recipe.outputs.items())
        },
    }


def _port_rate_payload(
    *,
    amount: Fraction,
    ticks_per_cycle: int,
    belt_capacity_per_tick: Fraction,
) -> dict[str, Any]:
    rate = amount / Fraction(ticks_per_cycle)
    return {
        "amount_per_cycle": _fraction_to_json(amount),
        "ticks_per_cycle": int(ticks_per_cycle),
        "rate_per_tick": _fraction_to_json(rate),
        "slots_per_machine": _ceil_fraction(rate / belt_capacity_per_tick),
    }


def _warehouse_summary(
    *,
    mandatory_instances: Sequence[Mapping[str, Any]],
    generic_io_requirements: Mapping[str, Mapping[str, int]],
) -> dict[str, Any]:
    boundary_ports = [
        instance
        for instance in mandatory_instances
        if str(instance.get("operation_type")) == "boundary_io"
    ]
    protocol_core = [
        instance
        for instance in mandatory_instances
        if str(instance.get("operation_type")) == "protocol_core"
    ]
    return {
        "physical_boundary_ports": {
            "group_id": "warehouse:physical_boundary_ports",
            "operation_type": "boundary_io",
            "facility_type": "boundary_storage_port",
            "instance_count": len(boundary_ports),
            "instance_builder_contract": "build_boundary_ports(46)",
        },
        "protocol_core_output_pool": {
            "group_id": "warehouse:protocol_core",
            "operation_type": "protocol_core",
            "facility_type": "protocol_core",
            "instance_count": len(protocol_core),
            "generic_output_slots_per_instance": 6,
        },
        "generic_output_requirements": dict(
            sorted(generic_io_requirements["required_generic_outputs"].items())
        ),
        "generic_input_requirements": dict(
            sorted(generic_io_requirements["required_generic_inputs"].items())
        ),
        "layering_note": {
            "physical_ports": "46 boundary-port instances come from mandatory_exact_instances.",
            "generic_io_demands": "Commodity slot requirements come from demand_solver expansion.",
        },
    }


def _equivalence_classes(
    *,
    context: Any,
    machine_counts: Mapping[str, int],
    operation_instances: Mapping[str, Sequence[str]],
    material_edges: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    same_operation_instances = []
    same_machine_material_ports = []
    for recipe_id, recipe in sorted(context.recipes.items()):
        same_operation_instances.append(
            {
                "class_id": f"same_operation_instances:{recipe_id}",
                "operation_type": recipe_id,
                "facility_type": recipe.template,
                "member_count": int(machine_counts.get(recipe_id, 0)),
                "member_instance_ids": list(operation_instances.get(recipe_id, ())),
            }
        )
        port_profile = _recipe_port_profile(context, recipe_id)
        for direction, commodities in (("input", recipe.inputs), ("output", recipe.outputs)):
            for commodity_id in sorted(commodities):
                port_payload = port_profile[f"{direction}s"][commodity_id]
                same_machine_material_ports.append(
                    {
                        "class_id": (
                            f"same_machine_material_ports:"
                            f"{recipe_id}:{direction}:{commodity_id}"
                        ),
                        "operation_type": recipe_id,
                        "commodity_id": commodity_id,
                        "direction": direction,
                        "machine_count": int(machine_counts.get(recipe_id, 0)),
                        "slots_per_machine": int(port_payload["slots_per_machine"]),
                    }
                )

    commodity_pool_classes = []
    for edge in material_edges:
        if not edge.get("pool_exchangeable"):
            continue
        commodity_pool_classes.append(
            {
                "class_id": f"commodity_pool_exchangeability:{edge['commodity_id']}",
                "commodity_id": str(edge["commodity_id"]),
                "producer_group_ids": [str(item["group_id"]) for item in edge["producers"]],
                "consumer_group_ids": [str(item["group_id"]) for item in edge["consumers"]],
            }
        )

    return {
        "same_operation_same_facility_machines": same_operation_instances,
        "same_machine_same_material_ports": same_machine_material_ports,
        "same_commodity_multi_source_or_sink_pools": commodity_pool_classes,
        "same_cycle_subchains": [
            {
                "class_id": f"cycle_subchain:{group_id}",
                "cycle_group": group_id,
                "operation_group_ids": [_operation_group_id(recipe_id) for recipe_id in group.recipes],
                "internal_commodities": list(group.internal_commodities),
            }
            for group_id, group in sorted(context.cycle_groups.items())
        ],
    }


def _cycle_material_groups(context: Any) -> list[dict[str, Any]]:
    return [
        {
            "cycle_group": group_id,
            "operation_group_ids": [_operation_group_id(recipe_id) for recipe_id in group.recipes],
            "recipes": list(group.recipes),
            "internal_commodities": list(group.internal_commodities),
            "net_export_commodities": list(group.net_export_commodities),
        }
        for group_id, group in sorted(context.cycle_groups.items())
    ]


def _totals(
    *,
    context: Any,
    machine_counts: Mapping[str, int],
    mandatory_instances: Sequence[Mapping[str, Any]],
    material_edges: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    manufacturing_count = sum(int(machine_counts.get(recipe_id, 0)) for recipe_id in context.recipes)
    boundary_count = sum(
        1 for instance in mandatory_instances if str(instance.get("operation_type")) == "boundary_io"
    )
    core_count = sum(
        1 for instance in mandatory_instances if str(instance.get("operation_type")) == "protocol_core"
    )
    return {
        "recipe_group_count": len(context.recipes),
        "manufacturing_instance_count": manufacturing_count,
        "boundary_port_instance_count": boundary_count,
        "protocol_core_instance_count": core_count,
        "mandatory_exact_instance_count": len(mandatory_instances),
        "material_edge_count": len(material_edges),
        "cycle_material_group_count": len(context.cycle_groups),
    }


def _consistency_checks(
    *,
    context: Any,
    machine_counts: Mapping[str, int],
    mandatory_instances: Sequence[Mapping[str, Any]],
    operation_instances: Mapping[str, Sequence[str]],
    material_edges: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    mismatches = []
    for recipe_id in sorted(context.recipes):
        expected = int(machine_counts.get(recipe_id, 0))
        actual = len(operation_instances.get(recipe_id, ()))
        if expected != actual:
            mismatches.append(
                {
                    "operation_type": recipe_id,
                    "machine_counts": expected,
                    "mandatory_instances": actual,
                }
            )
    totals = _totals(
        context=context,
        machine_counts=machine_counts,
        mandatory_instances=mandatory_instances,
        material_edges=material_edges,
    )
    return [
        {
            "name": "machine_counts_match_mandatory_manufacturing_instances",
            "passed": not mismatches,
            "mismatches": mismatches,
        },
        {
            "name": "current_default_contract_counts",
            "passed": (
                totals["recipe_group_count"] == 17
                and totals["manufacturing_instance_count"] == 219
                and totals["boundary_port_instance_count"] == 46
                and totals["protocol_core_instance_count"] == 1
                and totals["mandatory_exact_instance_count"] == 266
            ),
            "observed": totals,
        },
    ]


def _ceil_fraction(value: Fraction) -> int:
    if value <= 0:
        return 0
    return int((value.numerator + value.denominator - 1) // value.denominator)


def _fraction_to_json(value: Fraction) -> int | float:
    if value.denominator == 1:
        return int(value.numerator)
    rendered = round(float(value), 10)
    rounded = round(rendered)
    if abs(rendered - rounded) <= 1e-9:
        return int(rounded)
    return float(rendered)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify exploratory material skeleton sidecar")
    parser.add_argument(
        "--skeleton",
        type=Path,
        default=None,
        help="Skeleton path, default data/preprocessed/material_connection_skeleton.json",
    )
    args = parser.parse_args(argv)
    result = verify_material_skeleton_file(args.skeleton)
    print(f"material skeleton verifier passed: {result.actual_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
