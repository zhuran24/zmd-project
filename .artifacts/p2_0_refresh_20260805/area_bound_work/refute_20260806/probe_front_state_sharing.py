#!/usr/bin/env python3
"""Independent refutation probe for AREA_BOUND_THEOREM_REPORT theorem 2.

All repository inputs are read-only.  The only generated receipt is written next
to this script in the caller-authorized scratchpad.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path("/home/zhuran24/zmd-pj")
WORK = ROOT / ".artifacts/p2_0_refresh_20260805/area_bound_work"
OUT = Path(__file__).with_name("front_state_sharing_receipt.json")
CENTER = (35, 35)
COMMODITY = "buckwheat"
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}

sys.path.insert(0, str(ROOT))

from src.models.binding_subproblem import PortBindingModel  # noqa: E402
from src.models.port_binding import enumerate_pose_level_port_bindings  # noqa: E402
from src.models.routing_binding_context import build_routing_binding_context  # noqa: E402
from src.models.routing_subproblem import (  # noqa: E402
    RoutingGrid,
    RoutingSubproblem,
    _duplicate_terminal_front_keys,
    analyze_exact_routing_domain,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_fraction(value: Any) -> Fraction:
    text = str(value)
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return Fraction(int(numerator), int(denominator))
    return Fraction(text)


def cells(pose: dict[str, Any]) -> set[tuple[int, int]]:
    return {(int(cell[0]), int(cell[1])) for cell in pose["occupied_cells"]}


def bbox(pose: dict[str, Any]) -> list[int]:
    occupied = cells(pose)
    return [
        min(x for x, _ in occupied),
        min(y for _, y in occupied),
        max(x for x, _ in occupied),
        max(y for _, y in occupied),
    ]


@dataclass(frozen=True)
class Candidate:
    operation: str
    template: str
    pose_idx: int
    binding_idx: int
    pose: dict[str, Any]
    binding: dict[str, list[dict[str, Any]]]
    target_port: dict[str, Any]


def candidates_at_front(
    pools: dict[str, list[dict[str, Any]]],
    *,
    operation: str,
    template: str,
    side_key: str,
    raw_side_key: str,
) -> list[Candidate]:
    result: list[Candidate] = []
    for pose_idx, pose in enumerate(pools[template]):
        if not any(
            (int(port["x"]), int(port["y"])) == CENTER
            for port in pose.get(raw_side_key, [])
        ):
            continue
        for binding_idx, binding in enumerate(
            enumerate_pose_level_port_bindings(operation, pose)
        ):
            for port in binding[side_key]:
                if (
                    str(port["commodity"]) == COMMODITY
                    and (int(port["x"]), int(port["y"])) == CENTER
                ):
                    result.append(
                        Candidate(
                            operation=operation,
                            template=template,
                            pose_idx=pose_idx,
                            binding_idx=binding_idx,
                            pose=pose,
                            binding=binding,
                            target_port=port,
                        )
                    )
    return result


def find_canonical_splitter(
    pools: dict[str, list[dict[str, Any]]],
) -> tuple[Candidate, Candidate, Candidate]:
    producer_candidates = candidates_at_front(
        pools,
        operation="planter_buckwheat",
        template="manufacturing_5x5",
        side_key="output_ports",
        raw_side_key="output_port_cells",
    )
    crusher_candidates = candidates_at_front(
        pools,
        operation="crusher_buckwheat",
        template="manufacturing_3x3",
        side_key="input_ports",
        raw_side_key="input_port_cells",
    )
    collector_candidates = candidates_at_front(
        pools,
        operation="seed_collector_buckwheat",
        template="manufacturing_5x5",
        side_key="input_ports",
        raw_side_key="input_port_cells",
    )

    for producer, crusher, collector in itertools.product(
        producer_candidates,
        crusher_candidates,
        collector_candidates,
    ):
        route_in = OPP[str(producer.target_port["dir"])]
        route_out = (
            OPP[str(crusher.target_port["dir"])],
            OPP[str(collector.target_port["dir"])],
        )
        if route_in in route_out or len(set((route_in, *route_out))) != 3:
            continue

        chosen = (producer, crusher, collector)
        occupied = [cells(candidate.pose) for candidate in chosen]
        if any(
            occupied[left] & occupied[right]
            for left in range(3)
            for right in range(left + 1, 3)
        ):
            continue
        occupied_union = set().union(*occupied)
        if CENTER in occupied_union:
            continue
        active_ports = [
            port
            for candidate in chosen
            for port in candidate.binding["active_ports"]
        ]
        if any(
            not (0 <= int(port["x"]) < 70 and 0 <= int(port["y"]) < 70)
            or (int(port["x"]), int(port["y"])) in occupied_union
            for port in active_ports
        ):
            continue
        return chosen
    raise AssertionError("no canonical three-owner splitter geometry found")


def normalize_pattern(pattern: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        side: sorted(
            (
                str(port["commodity"]),
                int(port["x"]),
                int(port["y"]),
                str(port["dir"]),
                str(port["type"]),
            )
            for port in pattern[side]
        )
        for side in ("input_ports", "output_ports")
    }


def prove_binding_activation(
    pools: dict[str, list[dict[str, Any]]],
    all_instances: list[dict[str, Any]],
    chosen: tuple[Candidate, Candidate, Candidate],
) -> tuple[dict[str, Any], list[dict[str, Any]], set[tuple[int, int]]]:
    instance_by_operation: dict[str, dict[str, Any]] = {}
    for instance in all_instances:
        operation = str(instance["operation_type"])
        if operation in {candidate.operation for candidate in chosen}:
            instance_by_operation.setdefault(operation, instance)
    assert set(instance_by_operation) == {candidate.operation for candidate in chosen}

    placement: dict[str, dict[str, Any]] = {}
    selected_instances: list[dict[str, Any]] = []
    target_by_instance: dict[str, dict[str, Any]] = {}
    owner_by_cell: dict[tuple[int, int], str] = {}
    for candidate in chosen:
        instance = instance_by_operation[candidate.operation]
        instance_id = str(instance["instance_id"])
        selected_instances.append(instance)
        placement[instance_id] = {
            "facility_type": candidate.template,
            "pose_idx": candidate.pose_idx,
        }
        target_by_instance[instance_id] = normalize_pattern(candidate.binding)
        for cell in cells(candidate.pose):
            assert cell not in owner_by_cell
            owner_by_cell[cell] = instance_id

    pool_subset = {
        "manufacturing_3x3": pools["manufacturing_3x3"],
        "manufacturing_5x5": pools["manufacturing_5x5"],
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

    selected_domain_indices: dict[str, int] = {}
    for instance_id, target in target_by_instance.items():
        matching = [
            idx
            for idx, pattern in enumerate(binding_model.binding_domains[instance_id])
            if normalize_pattern(pattern) == target
        ]
        assert len(matching) == 1, (instance_id, matching)
        selected_idx = matching[0]
        selected_domain_indices[instance_id] = selected_idx
        if instance_id in binding_model.binding_vars:
            binding_model.model.Add(binding_model.binding_vars[instance_id][selected_idx] == 1)
        else:
            assert binding_model.fixed_binding_choice[instance_id] == selected_idx

    binding_status = binding_model.solve(time_limit_seconds=10.0)
    assert binding_status == "FEASIBLE", binding_model.extract_conflict_summary()
    port_specs = binding_model.extract_port_specs()
    selected_front_specs = [
        spec
        for spec in port_specs
        if str(spec["commodity"]) == COMMODITY
        and (int(spec["x"]), int(spec["y"])) == CENTER
    ]
    assert len(selected_front_specs) == 3, selected_front_specs
    assert sum(str(spec["type"]) == "out" for spec in selected_front_specs) == 1
    assert sum(str(spec["type"]) == "in" for spec in selected_front_specs) == 2

    receipt = {
        "status": binding_status,
        "selected_domain_indices_after_front_filter": selected_domain_indices,
        "routing_aware_filter_stats": binding_model.routing_aware_filter_stats,
        "placement": placement,
        "front_specs": selected_front_specs,
        "all_extracted_port_specs": port_specs,
    }
    return receipt, selected_front_specs, set(owner_by_cell)


def run_one_cell_gadget(
    name: str,
    port_specs: list[dict[str, Any]],
    *,
    expected_type: str,
    expected_flow_in: set[str],
    expected_flow_out: set[str],
) -> dict[str, Any]:
    # The exact local gadget: the terminal/front cell is the only free cell.
    # Every port's body-side neighbor is occupied and attributed to its owner;
    # all other cells are inert obstacles so no alternate route can be selected.
    all_cells = {(x, y) for x in range(70) for y in range(70)}
    occupied = all_cells - {CENTER}
    owner_by_cell: dict[tuple[int, int], str] = {}
    body_side_cells: dict[str, list[int]] = {}
    for spec in port_specs:
        direction = str(spec["dir"])
        dx, dy = DELTA[direction]
        body_cell = (CENTER[0] - dx, CENTER[1] - dy)
        assert body_cell in occupied
        owner_by_cell[body_cell] = str(spec["instance_id"])
        body_side_cells[str(spec["instance_id"])] = [body_cell[0], body_cell[1]]

    duplicates = _duplicate_terminal_front_keys(port_specs)
    assert not duplicates, duplicates
    grid = RoutingGrid(
        occupied,
        port_specs,
        occupied_owner_by_cell=owner_by_cell,
    )
    analysis = analyze_exact_routing_domain(grid)
    assert analysis["status"] == "feasible", analysis
    model = RoutingSubproblem(grid, [COMMODITY], domain_analysis=analysis)
    model.build()
    status = model.solve(time_limit=10.0)
    routes = model.extract_routes()
    assert status == "FEASIBLE", model.build_stats
    assert len(routes) == 1, routes
    route = routes[0]
    assert route["component_type"] == expected_type, route
    assert int(route["layer"]) == 0, route
    assert set(route["flow_in"]) == expected_flow_in, route
    assert set(route["flow_out"]) == expected_flow_out, route

    source_front_matches = []
    sink_front_matches = []
    for spec in port_specs:
        terminal_direction = OPP[str(spec["dir"])]
        record = {
            "instance_id": str(spec["instance_id"]),
            "front": [int(spec["x"]), int(spec["y"])],
            "port_dir": str(spec["dir"]),
            "terminal_direction": terminal_direction,
        }
        if str(spec["type"]) == "out":
            assert terminal_direction in route["flow_in"]
            source_front_matches.append(record)
        else:
            assert terminal_direction in route["flow_out"]
            sink_front_matches.append(record)

    connectivity = model.build_stats["last_solve"]["connectivity"]
    assert connectivity["failure_count"] == 0, connectivity
    assert connectivity["selected_route_states"] == 1, connectivity
    assert model.build_stats["port_adherence"] == {
        "exact_links": len(port_specs),
        "blocked_ports": 0,
        "ports": len(port_specs),
    }
    return {
        "name": name,
        "status": status,
        "domain_status": analysis["status"],
        "duplicate_terminal_front_keys": duplicates,
        "body_side_cells": body_side_cells,
        "port_specs": port_specs,
        "selected_physical_route_count": len(routes),
        "selected_route": route,
        "source_fronts_served_by_same_state": source_front_matches,
        "sink_fronts_served_by_same_state": sink_front_matches,
        "port_adherence": model.build_stats["port_adherence"],
        "connectivity": connectivity,
    }


def port(instance_id: str, direction: str, port_type: str) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "x": CENTER[0],
        "y": CENTER[1],
        "dir": direction,
        "type": port_type,
        "commodity": COMMODITY,
    }


def rate_and_bound_effect(
    canonical: dict[str, Any],
    ob1: dict[str, Any],
    theorem_receipt: dict[str, Any],
) -> dict[str, Any]:
    machine_equivalents = {
        operation: parse_fraction(value)
        for operation, value in ob1["pinned_target_solution"][
            "machine_equivalents_x"
        ].items()
    }
    recipes = canonical["recipes"]

    def per_tick(operation: str, side: str) -> Fraction:
        recipe = recipes[operation]
        quantity = Fraction(recipe[side][COMMODITY])
        ticks = Fraction(recipe["ticks_per_cycle"])
        return machine_equivalents[operation] * quantity / ticks

    producer_flow = per_tick("planter_buckwheat", "outputs")
    crusher_flow = per_tick("crusher_buckwheat", "inputs")
    collector_flow = per_tick("seed_collector_buckwheat", "inputs")
    assert producer_flow == crusher_flow + collector_flow == 11
    crusher_residual = crusher_flow - math.floor(crusher_flow)
    collector_residual = collector_flow - math.floor(collector_flow)
    assert crusher_residual == collector_residual == Fraction(1, 2)
    assert crusher_residual + collector_residual == 1

    pair_table = theorem_receipt["state_lower_bounds"]["matching_detail"][
        "per_commodity"
    ]
    aggregate_front_bound = 0
    corrected_by_commodity: dict[str, int] = {}
    for commodity, row in pair_table.items():
        corrected = min(
            int(row["states_min"]),
            int(max(row["out_ports_min"], row["in_ports_min"])),
        )
        # Only the two known split residual pairs are changed.  This is not a
        # claim that every other row is optimal; it computes the direct damage
        # to the report's own table from the explicit legal splitters.
        if commodity in {"buckwheat", "sandleaf"}:
            corrected -= 1
        corrected_by_commodity[commodity] = corrected
        aggregate_front_bound += corrected
    assert aggregate_front_bound == 306

    budget = 1356
    pole_cells = 4
    pole_min = 9
    area_unconditional = budget - pole_cells * pole_min - math.ceil(
        aggregate_front_bound / 2
    )
    area_single_layer = budget - pole_cells * pole_min - aggregate_front_bound
    assert area_unconditional == 1167
    assert area_single_layer == 1014
    return {
        "buckwheat_per_tick": {
            "producer_planter": str(producer_flow),
            "consumer_crusher": str(crusher_flow),
            "consumer_seed_collector": str(collector_flow),
            "consumer_residuals": [str(crusher_residual), str(collector_residual)],
            "shared_splitter_total": str(crusher_residual + collector_residual),
            "report_in_port_min": pair_table["buckwheat"]["in_ports_min"],
            "counterexample_sink_front_states": 11,
        },
        "same_defect_sandleaf": {
            "report_in_port_min": pair_table["sandleaf"]["in_ports_min"],
            "counterexample_sink_front_states": 21,
        },
        "report_L_front": theorem_receipt["state_lower_bounds"][
            "L_front_state_matching"
        ],
        "directly_corrected_front_count": aggregate_front_bound,
        "directly_corrected_by_commodity": corrected_by_commodity,
        "fallback_area_if_other_report_inputs_hold": {
            "unconditional": area_unconditional,
            "single_layer_conditional": area_single_layer,
        },
    }


def main() -> None:
    pools_payload = json.loads(
        (ROOT / "data/preprocessed/candidate_placements.json").read_text()
    )
    pools = pools_payload["facility_pools"]
    instances = json.loads(
        (ROOT / "data/preprocessed/mandatory_exact_instances.json").read_text()
    )
    canonical = json.loads((ROOT / "rules/canonical_rules.json").read_text())
    ob1 = json.loads((WORK / "ob1_flow_caliber_receipt.json").read_text())
    theorem_receipt = json.loads((WORK / "ob5_theorem_bound_receipt.json").read_text())

    chosen = find_canonical_splitter(pools)
    binding_receipt, canonical_front_specs, _canonical_bodies = prove_binding_activation(
        pools,
        instances,
        chosen,
    )
    canonical_route = run_one_cell_gadget(
        "canonical_buckwheat_one_source_two_opposite_sinks",
        canonical_front_specs,
        expected_type="splitter",
        expected_flow_in={"W"},
        expected_flow_out={"N", "S"},
    )

    opposite_sources = run_one_cell_gadget(
        "minimal_two_opposite_sources_one_sink",
        [
            port("producer_west", "E", "out"),
            port("producer_east", "W", "out"),
            port("consumer_north", "S", "in"),
        ],
        expected_type="merger",
        expected_flow_in={"E", "W"},
        expected_flow_out={"N"},
    )
    dense_four_owner = run_one_cell_gadget(
        "dense_three_sources_one_sink",
        [
            port("producer_west", "E", "out"),
            port("producer_east", "W", "out"),
            port("producer_south", "N", "out"),
            port("consumer_north", "S", "in"),
        ],
        expected_type="merger",
        expected_flow_in={"E", "S", "W"},
        expected_flow_out={"N"},
    )

    canonical_geometry = []
    for candidate in chosen:
        canonical_geometry.append(
            {
                "operation": candidate.operation,
                "template": candidate.template,
                "pose_idx": candidate.pose_idx,
                "binding_idx_before_front_filter": candidate.binding_idx,
                "pose_id": candidate.pose["pose_id"],
                "anchor": candidate.pose["anchor"],
                "occupied_bbox": bbox(candidate.pose),
                "target_port": candidate.target_port,
                "active_ports": candidate.binding["active_ports"],
            }
        )

    inputs = [
        ROOT / "src/models/routing_subproblem.py",
        ROOT / "src/models/binding_subproblem.py",
        ROOT / "src/models/port_binding.py",
        ROOT / "src/models/routing_binding_context.py",
        ROOT / "rules/canonical_rules.json",
        ROOT / "data/preprocessed/candidate_placements.json",
        WORK / "AREA_BOUND_THEOREM_REPORT.md",
        WORK / "ob5_slot_census.py",
        WORK / "ob5_theorem_bound.py",
        WORK / "ob1_flow_caliber_receipt.json",
        WORK / "ob5_theorem_bound_receipt.json",
    ]
    receipt = {
        "verdict": "REFUTED",
        "refuted_claim": (
            "one route state serves at most one producer front and at most one "
            "consumer front"
        ),
        "git_head": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
        "probe_sha256": sha256(Path(__file__)),
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "canonical_geometry": canonical_geometry,
        "binding_activation": binding_receipt,
        "routing_gadgets": [canonical_route, opposite_sources, dense_four_owner],
        "rate_and_bound_effect": rate_and_bound_effect(
            canonical,
            ob1,
            theorem_receipt,
        ),
    }
    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")

    print("=== front-state sharing refutation probe ===")
    print(f"HEAD={receipt['git_head']}")
    print("VERDICT=REFUTED")
    print("canonical geometry:")
    for row in canonical_geometry:
        print(
            f"  {row['operation']}: pose_idx={row['pose_idx']} "
            f"pose_id={row['pose_id']} bbox={row['occupied_bbox']} "
            f"target_port={row['target_port']}"
        )
    print(f"binding_status={binding_receipt['status']}")
    for gadget in receipt["routing_gadgets"]:
        route = gadget["selected_route"]
        print(
            f"gadget={gadget['name']} status={gadget['status']} "
            f"selected_states={gadget['connectivity']['selected_route_states']} "
            f"type={route['component_type']} flow_in={route['flow_in']} "
            f"flow_out={route['flow_out']} "
            f"sources={len(gadget['source_fronts_served_by_same_state'])} "
            f"sinks={len(gadget['sink_fronts_served_by_same_state'])} "
            f"connectivity_failures={gadget['connectivity']['failure_count']}"
        )
    effect = receipt["rate_and_bound_effect"]
    print(
        "buckwheat residual sink flows="
        f"{effect['buckwheat_per_tick']['consumer_residuals']} "
        f"sum={effect['buckwheat_per_tick']['shared_splitter_total']}"
    )
    print(
        f"front bound: report={effect['report_L_front']} "
        f"after explicit buckwheat+sandleaf splitters="
        f"{effect['directly_corrected_front_count']}"
    )
    print(
        "area fallback (holding other premises fixed): "
        f"unconditional={effect['fallback_area_if_other_report_inputs_hold']['unconditional']} "
        f"single_layer={effect['fallback_area_if_other_report_inputs_hold']['single_layer_conditional']}"
    )
    print(f"receipt={OUT}")


if __name__ == "__main__":
    main()
