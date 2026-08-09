#!/usr/bin/env python3
"""Verify a canonical mixed-commodity source-front hyperedge.

四轮修订（flowbound 补，2026-08-06）：原探针只验口存在性 / 机身互斥 / 容量；
"binding FEASIBLE" 当时由 refute 席另行独立复验。本耐久副本补上真实
PortBindingModel 调用（强制两实例各选一个含 (35,35) 目标产口的绑定并求解），
使脚本自证该声明。原始行为的输出见 canonical_mixed_source_hyperedge.log。
"""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path


ROOT = Path("/home/zhuran24/zmd-pj")
sys.path.insert(0, str(ROOT))

from src.models.binding_subproblem import PortBindingModel  # noqa: E402
from src.models.port_binding import enumerate_pose_level_port_bindings  # noqa: E402
from src.models.routing_binding_context import build_routing_binding_context  # noqa: E402


def occupied_cells(pose: dict[str, object]) -> set[tuple[int, int]]:
    return {tuple(cell) for cell in pose["occupied_cells"]}  # type: ignore[index]


def main() -> None:
    pools = json.loads(
        (ROOT / "data/preprocessed/candidate_placements.json").read_text()
    )["facility_pools"]
    rows = (
        (
            "grinder_fine_buckwheat",
            "manufacturing_6x4",
            3961,
            "fine_buckwheat_powder",
            Fraction(1, 2),
        ),
        (
            "molding_bottle",
            "manufacturing_3x3",
            8581,
            "steel_bottle",
            Fraction(1, 2),
        ),
    )
    bodies: list[set[tuple[int, int]]] = []
    receipt: list[dict[str, object]] = []
    aggregate_rate = Fraction()
    for operation, template, pose_index, commodity, output_rate in rows:
        pose = pools[template][pose_index]
        body = occupied_cells(pose)
        bodies.append(body)
        ports = [
            port
            for binding in enumerate_pose_level_port_bindings(operation, pose)
            for port in binding["output_ports"]
            if (int(port["x"]), int(port["y"]), str(port["commodity"]))
            == (35, 35, commodity)
        ]
        assert ports
        aggregate_rate += output_rate
        receipt.append(
            {
                "operation": operation,
                "pose_index": pose_index,
                "pose_id": pose["pose_id"],
                "bbox": [
                    min(x for x, _ in body),
                    min(y for _, y in body),
                    max(x for x, _ in body),
                    max(y for _, y in body),
                ],
                "front": [35, 35],
                "commodity": commodity,
                "direction": ports[0]["dir"],
                "residual_output_items_per_tick": str(output_rate),
            }
        )
    pairwise_disjoint = all(
        not bodies[left] & bodies[right]
        for left in range(len(bodies))
        for right in range(left + 1, len(bodies))
    )
    assert pairwise_disjoint
    assert aggregate_rate == 1

    # ---- 真实 PortBindingModel 自证（四轮补）：两实例强制含 (35,35) 目标产口的绑定 ----
    instances = json.loads(
        (ROOT / "data/preprocessed/mandatory_exact_instances.json").read_text()
    )
    instance_by_operation: dict[str, dict[str, object]] = {}
    for inst in instances:
        op = str(inst["operation_type"])
        if op in {r[0] for r in rows} and op not in instance_by_operation:
            instance_by_operation[op] = inst
    assert set(instance_by_operation) == {r[0] for r in rows}

    placement: dict[str, dict[str, object]] = {}
    selected_instances = []
    target_port_by_instance: dict[str, tuple[int, int, str]] = {}
    for operation, template, pose_index, commodity, _rate in rows:
        inst = instance_by_operation[operation]
        instance_id = str(inst["instance_id"])
        selected_instances.append(inst)
        placement[instance_id] = {"facility_type": template, "pose_idx": pose_index}
        target_port_by_instance[instance_id] = (35, 35, commodity)

    pool_subset = {
        "manufacturing_6x4": pools["manufacturing_6x4"],
        "manufacturing_3x3": pools["manufacturing_3x3"],
    }
    context = build_routing_binding_context(placement, pool_subset, 70, 70)
    binding_model = PortBindingModel(
        placement,
        pool_subset,
        selected_instances,
        required_generic_outputs={},
        required_generic_inputs={},
        routing_context=context,
    )
    binding_model.build(use_overload_separation=False)

    matched_binding_indices: dict[str, list[int]] = {}
    for instance_id, (px, py, pc) in target_port_by_instance.items():
        matching = [
            idx
            for idx, pattern in enumerate(binding_model.binding_domains[instance_id])
            if any(
                (int(port["x"]), int(port["y"]), str(port["commodity"])) == (px, py, pc)
                for port in pattern["output_ports"]
            )
        ]
        assert matching, (instance_id, "no binding pattern exposes target port")
        matched_binding_indices[instance_id] = matching
        if instance_id in binding_model.binding_vars:
            binding_model.model.Add(
                sum(binding_model.binding_vars[instance_id][idx] for idx in matching)
                == 1
            )
        else:
            assert binding_model.fixed_binding_choice[instance_id] in matching

    binding_status = binding_model.solve(time_limit_seconds=30.0)
    assert binding_status == "FEASIBLE", binding_model.extract_conflict_summary()
    out_specs_at_front = [
        spec
        for spec in binding_model.extract_port_specs()
        if str(spec["type"]) == "out" and (int(spec["x"]), int(spec["y"])) == (35, 35)
    ]
    front_commodities = sorted(str(spec["commodity"]) for spec in out_specs_at_front)
    assert front_commodities == ["fine_buckwheat_powder", "steel_bottle"], front_commodities

    print(
        json.dumps(
            {
                "front": [35, 35],
                "candidate_bindings": receipt,
                "pairwise_body_disjoint": pairwise_disjoint,
                "aggregate_items_per_tick": str(aggregate_rate),
                "one_tick_capacity": "1",
                "binding_activation": {
                    "status": binding_status,
                    "matched_binding_indices": matched_binding_indices,
                    "out_specs_at_front": out_specs_at_front,
                },
                "mixed_source_hyperedge_is_locally_feasible": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
