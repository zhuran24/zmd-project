#!/usr/bin/env python3
"""Verify a canonical mixed-commodity source-front hyperedge."""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path


ROOT = Path("/home/zhuran24/zmd-pj")
sys.path.insert(0, str(ROOT))

from src.models.port_binding import enumerate_pose_level_port_bindings  # noqa: E402


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
    print(
        json.dumps(
            {
                "front": [35, 35],
                "candidate_bindings": receipt,
                "pairwise_body_disjoint": pairwise_disjoint,
                "aggregate_items_per_tick": str(aggregate_rate),
                "one_tick_capacity": "1",
                "mixed_source_hyperedge_is_locally_feasible": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
