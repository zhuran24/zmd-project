#!/usr/bin/env python3
"""E080: exhaust the type-level dependency bipartition / seam frontier."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import datetime as dt
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path("/home/zhuran24/zmd-research")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.preprocess.operation_profiles import get_operation_port_profile  # noqa: E402

DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/E080_dependency_partition_seam_frontier/run-001"
)
EXPECTED_FULL_POOL_SHA256 = "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
EXPECTED_RECIPE_OPERATION_COUNT = 17
EXPECTED_CANONICAL_PARTITION_COUNT = (1 << (EXPECTED_RECIPE_OPERATION_COUNT - 1)) - 1
BOUNDARY_MACRO_PATH = (
    ROOT / "research_lab/local/zero_condition/E079_k47_boundary_macro/run-001/BOUNDARY_MACRO_V1.json"
)
BOUNDARY_RESULT_PATH = (
    ROOT / "research_lab/local/zero_condition/E079_k47_boundary_macro/run-001/RESULT.json"
)
BOUNDARY_RECEIPT_PATH = (
    ROOT / "research_lab/local/zero_condition/E079_k47_boundary_macro/run-001/RESULT_RECEIPT.json"
)
CANDIDATE_PATHS = (
    ROOT / "data/preprocessed/candidate_placements.json",
    Path("/home/zhuran24/zmd-pj/data/preprocessed/candidate_placements.json"),
    Path("/home/zhuran24/zmd-certification/data/preprocessed/candidate_placements.json"),
)
MANDATORY_PATHS = (
    ROOT / "data/preprocessed/mandatory_exact_instances.json",
    Path("/home/zhuran24/zmd-pj/data/preprocessed/mandatory_exact_instances.json"),
    Path("/home/zhuran24/zmd-certification/data/preprocessed/mandatory_exact_instances.json"),
)
BALANCE_BANDS = {
    "one_quarter_three_quarters": (Fraction(1, 4), Fraction(3, 4)),
    "one_third_two_thirds": (Fraction(1, 3), Fraction(2, 3)),
    "two_fifths_three_fifths": (Fraction(2, 5), Fraction(3, 5)),
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def first_existing(paths: Sequence[Path], *, label: str) -> Path:
    found = [path.resolve() for path in paths if path.is_file()]
    if not found:
        raise FileNotFoundError(f"E080 missing {label}: {list(map(str, paths))}")
    return found[0]


def collect_instances(value: Any) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    if isinstance(value, Mapping):
        if "instance_id" in value and "facility_type" in value:
            output[str(value["instance_id"])] = dict(value)
        for child in value.values():
            output.update(collect_instances(child))
    elif isinstance(value, list):
        for child in value:
            output.update(collect_instances(child))
    return output


def find_key_lists(value: Any, key: str) -> list[list[Any]]:
    output: list[list[Any]] = []
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            if str(child_key) == key and isinstance(child, list):
                output.append(child)
            output.extend(find_key_lists(child, key))
    elif isinstance(value, list):
        for child in value:
            output.extend(find_key_lists(child, key))
    return output


def cell_count(pose: Mapping[str, Any]) -> int:
    cells = pose.get("occupied_cells", []) or []
    return len({tuple(cell.values()) if isinstance(cell, Mapping) else tuple(cell) for cell in cells})


def facility_area(
    facility_type: str,
    candidate_payload: Any,
) -> int:
    candidates = [
        rows
        for rows in find_key_lists(candidate_payload, facility_type)
        if rows and all(isinstance(row, Mapping) for row in rows)
    ]
    area_sets = {
        tuple(sorted({cell_count(dict(pose)) for pose in rows}))
        for rows in candidates
    }
    valid = [areas for areas in area_sets if len(areas) == 1 and areas[0] > 0]
    unique = sorted(set(valid))
    if len(unique) != 1:
        raise RuntimeError(
            f"E080 facility-area lookup drift for {facility_type}: "
            f"candidate_lists={len(candidates)} area_sets={sorted(area_sets)}"
        )
    return int(unique[0][0])


def induced_connected(
    nodes: frozenset[str],
    adjacency: Mapping[str, set[str]],
) -> bool:
    if not nodes:
        return False
    start = min(nodes)
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in adjacency.get(node, set()):
            if neighbor in nodes and neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen == set(nodes)


def module_payload(
    operations: Iterable[str],
    operation_rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    ops = tuple(sorted(operations))
    return {
        "operation_types": list(ops),
        "operation_type_count": len(ops),
        "mandatory_instance_count": sum(int(operation_rows[op]["count"]) for op in ops),
        "body_area": sum(int(operation_rows[op]["body_area"]) for op in ops),
        "operations": [dict(operation_rows[op]) for op in ops],
    }


def seam_payload(
    side_a: frozenset[str],
    side_b: frozenset[str],
    producer_ops: Mapping[str, set[str]],
    consumer_ops: Mapping[str, set[str]],
    operation_rows: Mapping[str, Mapping[str, Any]],
    intermediate: Iterable[str],
) -> dict[str, Any]:
    obligations: list[dict[str, Any]] = []
    directional = Counter()
    seam_commodities: set[str] = set()
    crossing_edges: set[tuple[str, str, str]] = set()
    for commodity in sorted(intermediate):
        producers = producer_ops.get(commodity, set())
        consumers = consumer_ops.get(commodity, set())
        for source_side_name, source_side, sink_side_name, sink_side in (
            ("A", side_a, "B", side_b),
            ("B", side_b, "A", side_a),
        ):
            source_ops = sorted(producers & source_side)
            sink_ops = sorted(consumers & sink_side)
            if not source_ops or not sink_ops:
                continue
            seam_commodities.add(commodity)
            source_slots = sum(
                int(operation_rows[op]["output_slots"].get(commodity, 0))
                * int(operation_rows[op]["count"])
                for op in source_ops
            )
            sink_slots = sum(
                int(operation_rows[op]["input_slots"].get(commodity, 0))
                * int(operation_rows[op]["count"])
                for op in sink_ops
            )
            for producer in source_ops:
                for consumer in sink_ops:
                    crossing_edges.add((producer, consumer, commodity))
            obligations.append(
                {
                    "commodity": commodity,
                    "direction": f"{source_side_name}_to_{sink_side_name}",
                    "producer_operations": source_ops,
                    "consumer_operations": sink_ops,
                    "producer_output_slot_incidence": source_slots,
                    "consumer_input_slot_incidence": sink_slots,
                    "mixed_producer_sides": bool(producers & side_a and producers & side_b),
                    "mixed_consumer_sides": bool(consumers & side_a and consumers & side_b),
                    "semantic_note": (
                        "construction-interface incidence only; not a fixed duty, rate, "
                        "lane count, or proof that this amount must cross"
                    ),
                }
            )
            directional[f"{source_side_name}_to_{sink_side_name}_producer_slots"] += source_slots
            directional[f"{source_side_name}_to_{sink_side_name}_consumer_slots"] += sink_slots
    obligations.sort(key=lambda row: (row["direction"], row["commodity"]))
    return {
        "commodity_count": len(seam_commodities),
        "commodities": sorted(seam_commodities),
        "dependency_edge_count": len(crossing_edges),
        "crossing_edges": [
            {"producer": producer, "consumer": consumer, "commodity": commodity}
            for producer, consumer, commodity in sorted(crossing_edges)
        ],
        "obligations": obligations,
        "directional_slot_incidence": dict(sorted(directional.items())),
        "consumer_input_slot_incidence": sum(
            int(row["consumer_input_slot_incidence"]) for row in obligations
        ),
        "producer_output_slot_incidence": sum(
            int(row["producer_output_slot_incidence"]) for row in obligations
        ),
    }


def external_interface_payload(
    operations: frozenset[str],
    operation_rows: Mapping[str, Mapping[str, Any]],
    commodities: Iterable[str],
    *,
    side: str,
    direction: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for commodity in sorted(commodities):
        if direction == "input":
            incidences = [
                {
                    "operation": op,
                    "slots": int(operation_rows[op]["input_slots"].get(commodity, 0))
                    * int(operation_rows[op]["count"]),
                }
                for op in sorted(operations)
                if int(operation_rows[op]["input_slots"].get(commodity, 0)) > 0
            ]
        else:
            incidences = [
                {
                    "operation": op,
                    "slots": int(operation_rows[op]["output_slots"].get(commodity, 0))
                    * int(operation_rows[op]["count"]),
                }
                for op in sorted(operations)
                if int(operation_rows[op]["output_slots"].get(commodity, 0)) > 0
            ]
        if incidences:
            rows.append(
                {
                    "side": side,
                    "commodity": commodity,
                    "slot_incidence": sum(row["slots"] for row in incidences),
                    "operation_incidences": incidences,
                    "binding_note": (
                        "named commodity obligation; assignment to generic provider/sink "
                        "slots remains existential until binding"
                    ),
                }
            )
    return rows


def dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_metrics = (
        int(left["seam"]["commodity_count"]),
        int(left["seam"]["consumer_input_slot_incidence"]),
        int(left["area_imbalance"]),
    )
    right_metrics = (
        int(right["seam"]["commodity_count"]),
        int(right["seam"]["consumer_input_slot_incidence"]),
        int(right["area_imbalance"]),
    )
    return all(a <= b for a, b in zip(left_metrics, right_metrics, strict=True)) and any(
        a < b for a, b in zip(left_metrics, right_metrics, strict=True)
    )


def pareto_frontier(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    frontier: list[dict[str, Any]] = []
    ordered = sorted(
        (dict(row) for row in candidates),
        key=lambda row: (
            int(row["seam"]["commodity_count"]),
            int(row["seam"]["consumer_input_slot_incidence"]),
            int(row["area_imbalance"]),
            tuple(row["module_a"]["operation_types"]),
        ),
    )
    for candidate in ordered:
        if any(dominates(existing, candidate) for existing in frontier):
            continue
        frontier = [existing for existing in frontier if not dominates(candidate, existing)]
        frontier.append(candidate)
    return sorted(
        frontier,
        key=lambda row: (
            int(row["seam"]["commodity_count"]),
            int(row["seam"]["consumer_input_slot_incidence"]),
            int(row["area_imbalance"]),
            tuple(row["module_a"]["operation_types"]),
        ),
    )


def in_balance_band(candidate: Mapping[str, Any], band: tuple[Fraction, Fraction]) -> bool:
    low, high = band
    total = int(candidate["total_body_area"])
    area_a = int(candidate["module_a"]["body_area"])
    return low * total <= area_a <= high * total


def candidate_score(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(candidate["seam"]["commodity_count"]),
        int(candidate["seam"]["consumer_input_slot_incidence"]),
        int(candidate["seam"]["dependency_edge_count"]),
        int(candidate["area_imbalance"]),
        int(candidate["instance_imbalance"]),
        tuple(candidate["module_a"]["operation_types"]),
    )


def compact_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "partition_id": candidate["partition_id"],
        "module_a": candidate["module_a"],
        "module_b": candidate["module_b"],
        "connected_a": candidate["connected_a"],
        "connected_b": candidate["connected_b"],
        "seam": candidate["seam"],
        "external_source_inputs": candidate["external_source_inputs"],
        "final_sink_outputs": candidate["final_sink_outputs"],
        "area_imbalance": candidate["area_imbalance"],
        "instance_imbalance": candidate["instance_imbalance"],
        "total_body_area": candidate["total_body_area"],
        "score": list(candidate_score(candidate)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate_path = first_existing(CANDIDATE_PATHS, label="candidate placements")
    mandatory_path = first_existing(MANDATORY_PATHS, label="mandatory instances")
    if sha256_file(candidate_path) != EXPECTED_FULL_POOL_SHA256:
        raise RuntimeError("E080 candidate-placement identity drift")
    candidate_payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    mandatory_payload = json.loads(mandatory_path.read_text(encoding="utf-8"))
    instances = collect_instances(mandatory_payload)

    operation_instances: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in instances.values():
        operation = str(row.get("operation_type", ""))
        if not operation:
            continue
        try:
            profile = get_operation_port_profile(operation)
        except KeyError:
            continue
        if not profile.input_rates and not profile.output_rates:
            continue
        operation_instances[operation].append(row)
    operation_types = tuple(sorted(operation_instances))
    if len(operation_types) != EXPECTED_RECIPE_OPERATION_COUNT:
        raise RuntimeError(
            f"E080 recipe-operation count drift: {len(operation_types)} {operation_types}"
        )

    operation_rows: dict[str, dict[str, Any]] = {}
    for operation in operation_types:
        profile = get_operation_port_profile(operation)
        facility_type = str(profile.facility_type)
        count = len(operation_instances[operation])
        body_area_each = facility_area(facility_type, candidate_payload)
        operation_rows[operation] = {
            "operation_type": operation,
            "facility_type": facility_type,
            "count": count,
            "body_area_each": body_area_each,
            "body_area": body_area_each * count,
            "input_slots": dict(sorted(profile.input_slots.items())),
            "output_slots": dict(sorted(profile.output_slots.items())),
            "input_commodities": sorted(profile.input_rates),
            "output_commodities": sorted(profile.output_rates),
        }

    producer_ops: dict[str, set[str]] = defaultdict(set)
    consumer_ops: dict[str, set[str]] = defaultdict(set)
    for operation, row in operation_rows.items():
        for commodity in row["output_commodities"]:
            producer_ops[str(commodity)].add(operation)
        for commodity in row["input_commodities"]:
            consumer_ops[str(commodity)].add(operation)
    produced = set(producer_ops)
    consumed = set(consumer_ops)
    intermediate = sorted(produced & consumed)
    external_sources = sorted(consumed - produced)
    final_sinks = sorted(produced - consumed)

    adjacency: dict[str, set[str]] = {operation: set() for operation in operation_types}
    dependency_edges: list[dict[str, str]] = []
    for commodity in intermediate:
        for producer in sorted(producer_ops[commodity]):
            for consumer in sorted(consumer_ops[commodity]):
                if producer == consumer:
                    continue
                adjacency[producer].add(consumer)
                adjacency[consumer].add(producer)
                dependency_edges.append(
                    {"producer": producer, "consumer": consumer, "commodity": commodity}
                )

    anchor = operation_types[0]
    remaining = operation_types[1:]
    total_body_area = sum(int(row["body_area"]) for row in operation_rows.values())
    total_instances = sum(int(row["count"]) for row in operation_rows.values())
    partitions: list[dict[str, Any]] = []
    histogram = Counter()
    connected_count = 0
    for mask in range(1 << len(remaining)):
        side_a = frozenset(
            {anchor}
            | {
                operation
                for bit, operation in enumerate(remaining)
                if mask & (1 << bit)
            }
        )
        side_b = frozenset(set(operation_types) - set(side_a))
        if not side_b:
            continue
        module_a = module_payload(side_a, operation_rows)
        module_b = module_payload(side_b, operation_rows)
        connected_a = induced_connected(side_a, adjacency)
        connected_b = induced_connected(side_b, adjacency)
        if connected_a and connected_b:
            connected_count += 1
        seam = seam_payload(
            side_a,
            side_b,
            producer_ops,
            consumer_ops,
            operation_rows,
            intermediate,
        )
        external_inputs = (
            external_interface_payload(
                side_a,
                operation_rows,
                external_sources,
                side="A",
                direction="input",
            )
            + external_interface_payload(
                side_b,
                operation_rows,
                external_sources,
                side="B",
                direction="input",
            )
        )
        final_outputs = (
            external_interface_payload(
                side_a,
                operation_rows,
                final_sinks,
                side="A",
                direction="output",
            )
            + external_interface_payload(
                side_b,
                operation_rows,
                final_sinks,
                side="B",
                direction="output",
            )
        )
        area_imbalance = abs(int(module_a["body_area"]) - int(module_b["body_area"]))
        instance_imbalance = abs(
            int(module_a["mandatory_instance_count"])
            - int(module_b["mandatory_instance_count"])
        )
        partition = {
            "partition_id": f"partition_{len(partitions)+1:05d}",
            "module_a": module_a,
            "module_b": module_b,
            "connected_a": connected_a,
            "connected_b": connected_b,
            "seam": seam,
            "external_source_inputs": external_inputs,
            "final_sink_outputs": final_outputs,
            "area_imbalance": area_imbalance,
            "instance_imbalance": instance_imbalance,
            "total_body_area": total_body_area,
            "total_instances": total_instances,
        }
        partitions.append(partition)
        histogram[
            (
                seam["commodity_count"],
                seam["consumer_input_slot_incidence"],
                connected_a,
                connected_b,
            )
        ] += 1

    if len(partitions) != EXPECTED_CANONICAL_PARTITION_COUNT:
        raise RuntimeError(
            f"E080 canonical partition count drift: {len(partitions)}"
        )

    connected = [
        row for row in partitions if bool(row["connected_a"]) and bool(row["connected_b"])
    ]
    frontier = pareto_frontier(connected)
    if not frontier:
        raise RuntimeError("E080 connected Pareto frontier is empty")

    band_winners: dict[str, Any] = {}
    for name, band in BALANCE_BANDS.items():
        eligible = [row for row in connected if in_balance_band(row, band)]
        winner = min(eligible, key=candidate_score) if eligible else None
        band_winners[name] = {
            "lower": str(band[0]),
            "upper": str(band[1]),
            "eligible_count": len(eligible),
            "winner": None if winner is None else compact_candidate(winner),
        }

    selected = band_winners["one_third_two_thirds"]["winner"]
    if selected is None:
        verdict = "NO_CONNECTED_ONE_THIRD_BALANCED_TYPE_BIPARTITION"
        decision = "REFINE_TO_INSTANCE_LEVEL_OR_MORE_THAN_TWO_MODULES"
    else:
        verdict = "CONNECTED_BALANCED_TYPE_PARTITION_WITH_EXPLICIT_SEAM_FOUND"
        decision = "BUILD_GEOMETRIC_BAY_AND_SEAM_CONSTRUCTOR_AROUND_SELECTED_CONTRACT"

    if not BOUNDARY_MACRO_PATH.is_file() or not BOUNDARY_RESULT_PATH.is_file():
        raise FileNotFoundError("E080 requires completed E079 boundary macro")
    boundary_macro = json.loads(BOUNDARY_MACRO_PATH.read_text(encoding="utf-8"))
    boundary_result = json.loads(BOUNDARY_RESULT_PATH.read_text(encoding="utf-8"))
    boundary_receipt = json.loads(BOUNDARY_RECEIPT_PATH.read_text(encoding="utf-8"))
    if (
        int(boundary_macro.get("state_count", -1)) != 47
        or boundary_result.get("verdict")
        != "K47_BOUNDARY_PACKING_EXACTLY_COMPILED_TO_47_STATE_MACRO"
        or boundary_receipt.get("macro_sha256") != sha256_file(BOUNDARY_MACRO_PATH)
    ):
        raise RuntimeError("E080 boundary macro identity or verdict drift")

    frontier_payload = {
        "schema": "zmd_e080_dependency_partition_frontier_v1",
        "created_at_utc": utc_now(),
        "operation_type_count": len(operation_types),
        "canonical_partition_count": len(partitions),
        "connected_partition_count": connected_count,
        "producer_consumer_dependency_edges": dependency_edges,
        "intermediate_commodities": intermediate,
        "external_source_commodities": external_sources,
        "final_sink_commodities": final_sinks,
        "histogram": [
            {
                "seam_commodity_count": key[0],
                "seam_consumer_input_slots": key[1],
                "connected_a": key[2],
                "connected_b": key[3],
                "count": count,
            }
            for key, count in sorted(histogram.items())
        ],
        "pareto_frontier": [compact_candidate(row) for row in frontier],
        "balance_band_winners": band_winners,
        "selected_partition": selected,
        "operation_rows": [operation_rows[op] for op in operation_types],
        "semantic_guards": [
            "slot incidence is not a fixed duty, rate, or throughput proof",
            "generic provider/sink commodity binding remains existential",
            "all copies of one operation type are fixed to one module in this prototype",
            "mixed-commodity physical lanes are not assigned by this abstraction",
        ],
    }
    frontier_path = run_dir / "PARTITION_FRONTIER.json"
    atomic_json(frontier_path, frontier_payload)

    interface_contract = {
        "schema": "zmd_e080_partition_seam_contract_v1",
        "created_at_utc": utc_now(),
        "selected_partition": selected,
        "boundary_module": {
            "macro_path": str(BOUNDARY_MACRO_PATH.relative_to(ROOT)),
            "macro_sha256": sha256_file(BOUNDARY_MACRO_PATH),
            "state_count": 47,
            "complete_disjunction_required": True,
            "rank1_is_wlog": False,
            "license": boundary_macro["license"],
        },
        "constructor_obligations": [
            "choose one of all 47 boundary macro states",
            "place each interior module without reopening the raw boundary pose family",
            "materialize every named seam commodity incidence at stable docks",
            "defer generic source/sink commodity assignment to an admitted binding model",
            "check front clearance, power, non-overlap, terminal uniqueness, component compatibility, and exact routing",
            "treat slot incidence as interface cardinality only; throughput requires the future duty-polytope route LP",
        ],
        "truth_boundary": (
            "This contract is a type-level sufficient construction proposal. It is not a "
            "necessary partition, not a physical embedding, and not a routing or throughput witness."
        ),
    }
    contract_path = run_dir / "SEAM_CONTRACT.json"
    atomic_json(contract_path, interface_contract)

    result = {
        "schema": "zmd_e080_dependency_partition_seam_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "operation_type_count": len(operation_types),
        "canonical_partition_count": len(partitions),
        "connected_partition_count": connected_count,
        "pareto_frontier_count": len(frontier),
        "balance_band_winners": band_winners,
        "selected_partition": selected,
        "frontier_path": str(frontier_path.relative_to(ROOT)),
        "frontier_sha256": sha256_file(frontier_path),
        "seam_contract_path": str(contract_path.relative_to(ROOT)),
        "seam_contract_sha256": sha256_file(contract_path),
        "boundary_macro_identity": {
            "path": str(BOUNDARY_MACRO_PATH.relative_to(ROOT)),
            "sha256": sha256_file(BOUNDARY_MACRO_PATH),
            "state_count": 47,
        },
        "input_identity": {
            "candidate_path": str(candidate_path),
            "candidate_sha256": sha256_file(candidate_path),
            "mandatory_path": str(mandatory_path),
            "mandatory_sha256": sha256_file(mandatory_path),
        },
        "runner": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "truth_boundary": (
            "E080 exhausts canonical type-level bipartitions only. The selected partition "
            "is a deterministic sufficient-construction seed, never WLOG; it freezes no "
            "duty/rate and proves no physical seam, binding, routing, or full layout."
        ),
    }
    result["result_digest"] = stable_digest(result)
    result_path = run_dir / "RESULT.json"
    atomic_json(result_path, result)
    receipt = {
        "schema": "zmd_e080_dependency_partition_seam_receipt_v1",
        "result_path": str(result_path.relative_to(ROOT)),
        "result_sha256": sha256_file(result_path),
        "frontier_sha256": sha256_file(frontier_path),
        "seam_contract_sha256": sha256_file(contract_path),
        "verdict": verdict,
        "decision": decision,
    }
    atomic_json(run_dir / "RESULT_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
