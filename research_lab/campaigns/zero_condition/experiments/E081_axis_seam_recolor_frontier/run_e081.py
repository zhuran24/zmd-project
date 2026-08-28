#!/usr/bin/env python3
"""E081: geometry-conditioned straight-seam continuation for E080 partitions."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import datetime as dt
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path("/home/zhuran24/zmd-research")
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/E081_axis_seam_recolor_frontier/run-001"
)
HISTORY_CANDIDATES = Path(
    "/home/zhuran24/zmd-pj/data/preprocessed/candidate_placements.json"
)
E069_PARENT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json"
)
E074_TARGET = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E074_minimum_assignment_transport_core/run-001/TARGET_026_TRANSPORT.json"
)
E078_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E078_target26_transport_core_stability/run-003/RESULT.json"
)
E080_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E080_dependency_partition_seam_frontier/run-001/RESULT.json"
)
E080_FRONTIER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E080_dependency_partition_seam_frontier/run-001/PARTITION_FRONTIER.json"
)
EXPECTED_HASHES = {
    HISTORY_CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E074_TARGET: "609e0be6613f27531e9a24bc757b3dbeb7574d6422e9eb55615cf117d74658f4",
    E078_RESULT: "b1309e4684513743a5613bbffd51f4d3d8f4147df9d5f353cc61f6e8f6612886",
    E080_RESULT: "47f497a3f8ee26351bdc1616c8061f80d03646089c266be66f979f7393080077",
    E080_FRONTIER: "96e4e84fb88c666aee38c7be2c421a59ca4fbe7e59d570eacee5f4391fe867b7",
}
EXPECTED_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 132,
    "manufacturing_5x5": 49,
    "manufacturing_6x4": 38,
}
EXPECTED_MANUFACTURING_COUNT = 219
EXPECTED_OPERATION_COUNT = 17
EXPECTED_CANONICAL_PARTITION_COUNT = 65_535
EXPECTED_CONNECTED_PARTITION_COUNT = 53
EXPECTED_BALANCED_CONNECTED_COUNT = 16
CORRIDOR_WIDTHS = (1, 2, 3)
INTERIOR_MIN = 1
INTERIOR_MAX = 68
BALANCE_LOW = Fraction(1, 3)
BALANCE_HIGH = Fraction(2, 3)


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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()


def cell_xy(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def body_record(
    *,
    instance_id: str,
    solution_row: Mapping[str, Any],
    pose: Mapping[str, Any],
) -> dict[str, Any]:
    cells = tuple(sorted(cell_xy(value) for value in pose["occupied_cells"]))
    if not cells:
        raise RuntimeError(f"E081 empty body: {instance_id}")
    if str(pose["pose_id"]) != str(solution_row["pose_id"]):
        raise RuntimeError(
            f"E081 pose identity drift for {instance_id}: "
            f"{pose['pose_id']} != {solution_row['pose_id']}"
        )
    return {
        "instance_id": str(instance_id),
        "facility_type": str(solution_row["facility_type"]),
        "source_operation_label": str(solution_row["operation_type"]),
        "pose_idx": int(solution_row["pose_idx"]),
        "pose_id": str(solution_row["pose_id"]),
        "occupied_cells": cells,
        "body_digest": stable_digest(cells),
        "body_area": len(cells),
        "min_x": min(x for x, _y in cells),
        "max_x": max(x for x, _y in cells),
        "min_y": min(y for _x, y in cells),
        "max_y": max(y for _x, y in cells),
    }


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
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor in nodes and neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen == set(nodes)


def partition_seam(
    side_a: frozenset[str],
    side_b: frozenset[str],
    *,
    operation_rows: Mapping[str, Mapping[str, Any]],
    producers: Mapping[str, set[str]],
    consumers: Mapping[str, set[str]],
    intermediate: Iterable[str],
) -> dict[str, Any]:
    commodities: set[str] = set()
    edges: set[tuple[str, str, str]] = set()
    directional = Counter()
    obligations: list[dict[str, Any]] = []
    for commodity in sorted(intermediate):
        for source_name, source_side, sink_name, sink_side in (
            ("A", side_a, "B", side_b),
            ("B", side_b, "A", side_a),
        ):
            source_ops = sorted(producers[commodity] & source_side)
            sink_ops = sorted(consumers[commodity] & sink_side)
            if not source_ops or not sink_ops:
                continue
            commodities.add(commodity)
            output_slots = sum(
                int(operation_rows[operation]["output_slots"].get(commodity, 0))
                * int(operation_rows[operation]["count"])
                for operation in source_ops
            )
            input_slots = sum(
                int(operation_rows[operation]["input_slots"].get(commodity, 0))
                * int(operation_rows[operation]["count"])
                for operation in sink_ops
            )
            for producer in source_ops:
                for consumer in sink_ops:
                    edges.add((producer, consumer, commodity))
            direction = f"{source_name}_to_{sink_name}"
            directional[f"{direction}_producer_slots"] += output_slots
            directional[f"{direction}_consumer_slots"] += input_slots
            obligations.append(
                {
                    "commodity": commodity,
                    "direction": direction,
                    "producer_operations": source_ops,
                    "consumer_operations": sink_ops,
                    "producer_output_slot_incidence": output_slots,
                    "consumer_input_slot_incidence": input_slots,
                }
            )
    obligations.sort(key=lambda row: (row["direction"], row["commodity"]))
    return {
        "commodity_count": len(commodities),
        "commodities": sorted(commodities),
        "dependency_edge_count": len(edges),
        "crossing_edges": [
            {"producer": producer, "consumer": consumer, "commodity": commodity}
            for producer, consumer, commodity in sorted(edges)
        ],
        "obligations": obligations,
        "directional_slot_incidence": dict(sorted(directional.items())),
        "producer_output_slot_incidence": sum(
            int(row["producer_output_slot_incidence"]) for row in obligations
        ),
        "consumer_input_slot_incidence": sum(
            int(row["consumer_input_slot_incidence"]) for row in obligations
        ),
    }


def partition_payload(
    side_a: frozenset[str],
    side_b: frozenset[str],
    *,
    operation_rows: Mapping[str, Mapping[str, Any]],
    producers: Mapping[str, set[str]],
    consumers: Mapping[str, set[str]],
    intermediate: Iterable[str],
) -> dict[str, Any]:
    template_counts: dict[str, Counter[str]] = {"A": Counter(), "B": Counter()}
    for operation in side_a:
        row = operation_rows[operation]
        template_counts["A"][str(row["facility_type"])] += int(row["count"])
    for operation in side_b:
        row = operation_rows[operation]
        template_counts["B"][str(row["facility_type"])] += int(row["count"])
    area_a = sum(int(operation_rows[operation]["body_area"]) for operation in side_a)
    area_b = sum(int(operation_rows[operation]["body_area"]) for operation in side_b)
    instances_a = sum(int(operation_rows[operation]["count"]) for operation in side_a)
    instances_b = sum(int(operation_rows[operation]["count"]) for operation in side_b)
    seam = partition_seam(
        side_a,
        side_b,
        operation_rows=operation_rows,
        producers=producers,
        consumers=consumers,
        intermediate=intermediate,
    )
    identity = {
        "module_a_operations": sorted(side_a),
        "module_b_operations": sorted(side_b),
    }
    return {
        "partition_id": "partition_" + stable_digest(identity)[:16],
        **identity,
        "module_a_template_counts": dict(sorted(template_counts["A"].items())),
        "module_b_template_counts": dict(sorted(template_counts["B"].items())),
        "module_a_instance_count": instances_a,
        "module_b_instance_count": instances_b,
        "module_a_body_area": area_a,
        "module_b_body_area": area_b,
        "area_imbalance": abs(area_a - area_b),
        "instance_imbalance": abs(instances_a - instances_b),
        "seam": seam,
    }


def corridor_cells(axis: str, start: int, width: int) -> frozenset[tuple[int, int]]:
    end = start + width - 1
    if axis == "x":
        return frozenset(
            (x, y)
            for x in range(start, end + 1)
            for y in range(INTERIOR_MIN, INTERIOR_MAX + 1)
        )
    return frozenset(
        (x, y)
        for y in range(start, end + 1)
        for x in range(INTERIOR_MIN, INTERIOR_MAX + 1)
    )


def body_side(body: Mapping[str, Any], *, axis: str, start: int, end: int) -> str:
    lower = int(body["min_x"] if axis == "x" else body["min_y"])
    upper = int(body["max_x"] if axis == "x" else body["max_y"])
    if upper < start:
        return "low"
    if lower > end:
        return "high"
    return "corridor"


def distance_from_corridor(
    body: Mapping[str, Any], *, axis: str, side: str, start: int, end: int
) -> int:
    if axis == "x":
        return (
            start - 1 - int(body["max_x"])
            if side == "low"
            else int(body["min_x"]) - end - 1
        )
    return (
        start - 1 - int(body["max_y"])
        if side == "low"
        else int(body["min_y"]) - end - 1
    )


def compact_body(body: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "instance_id": str(body["instance_id"]),
        "facility_type": str(body["facility_type"]),
        "pose_idx": int(body["pose_idx"]),
        "pose_id": str(body["pose_id"]),
        "body_digest": str(body["body_digest"]),
        "body_area": int(body["body_area"]),
        "occupied_cells": [list(cell) for cell in body["occupied_cells"]],
    }


def evaluate_corridor(
    *,
    partition: Mapping[str, Any],
    manufacturing: Sequence[Mapping[str, Any]],
    fixed: Sequence[Mapping[str, Any]],
    reference_targets: Mapping[str, str],
    axis: str,
    start: int,
    width: int,
    module_a_on_low: bool,
    preserve_reference: bool,
) -> dict[str, Any] | None:
    end = start + width - 1
    cells = corridor_cells(axis, start, width)
    fixed_intersections = [
        row for row in fixed if cells & set(row["occupied_cells"])
    ]
    if any(str(row["facility_type"]) in {"protocol_core", "boundary_storage_port"} for row in fixed_intersections):
        return None
    pole_rows = [
        row for row in fixed_intersections if str(row["facility_type"]) == "power_pole"
    ]

    side_by_id = {
        str(body["instance_id"]): body_side(body, axis=axis, start=start, end=end)
        for body in manufacturing
    }
    bodies_by_side_template: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for body in manufacturing:
        side = side_by_id[str(body["instance_id"])]
        if side != "corridor":
            bodies_by_side_template[(side, str(body["facility_type"]))].append(body)

    module_side = {
        "A": "low" if module_a_on_low else "high",
        "B": "high" if module_a_on_low else "low",
    }
    operation_module = {
        operation: "A" for operation in partition["module_a_operations"]
    } | {
        operation: "B" for operation in partition["module_b_operations"]
    }
    forced_by_module_template: dict[tuple[str, str], list[str]] = defaultdict(list)
    reference_rows: list[dict[str, Any]] = []
    if preserve_reference:
        for instance_id, target_operation in sorted(reference_targets.items()):
            module = operation_module[target_operation]
            body = next(
                row for row in manufacturing if str(row["instance_id"]) == instance_id
            )
            observed_side = side_by_id[instance_id]
            expected_side = module_side[module]
            if observed_side != expected_side:
                return None
            key = (module, str(body["facility_type"]))
            forced_by_module_template[key].append(instance_id)
            reference_rows.append(
                {
                    "instance_id": instance_id,
                    "body_digest": str(body["body_digest"]),
                    "target_operation": target_operation,
                    "target_module": module,
                    "side": observed_side,
                }
            )

    retained_ids: set[str] = set()
    retained_assignment: dict[str, str] = {}
    deficits: dict[str, dict[str, int]] = {"A": {}, "B": {}}
    for module in ("A", "B"):
        side = module_side[module]
        requirements = partition[
            "module_a_template_counts" if module == "A" else "module_b_template_counts"
        ]
        for template, raw_need in sorted(requirements.items()):
            need = int(raw_need)
            available = list(bodies_by_side_template[(side, template)])
            forced_ids = set(forced_by_module_template[(module, template)])
            available.sort(
                key=lambda body: (
                    0 if str(body["instance_id"]) in forced_ids else 1,
                    -distance_from_corridor(
                        body,
                        axis=axis,
                        side=side,
                        start=start,
                        end=end,
                    ),
                    str(body["instance_id"]),
                )
            )
            keep_count = min(need, len(available))
            kept = available[:keep_count]
            kept_ids = {str(body["instance_id"]) for body in kept}
            if not forced_ids <= kept_ids:
                return None
            for body in kept:
                instance_id = str(body["instance_id"])
                retained_ids.add(instance_id)
                retained_assignment[instance_id] = module
            deficits[module][template] = need - keep_count

    all_ids = {str(body["instance_id"]) for body in manufacturing}
    moved_ids = sorted(all_ids - retained_ids)
    moved_rows = [
        next(row for row in manufacturing if str(row["instance_id"]) == instance_id)
        for instance_id in moved_ids
    ]
    moved_by_template = Counter(str(row["facility_type"]) for row in moved_rows)
    corridor_body_ids = sorted(
        instance_id for instance_id, side in side_by_id.items() if side == "corridor"
    )
    return {
        "corridor": {
            "axis": axis,
            "start": start,
            "end": end,
            "width": width,
            "module_low": "A" if module_a_on_low else "B",
            "module_high": "B" if module_a_on_low else "A",
            "interior_cell_count": len(cells),
            "interior_cells_digest": stable_digest(sorted(cells)),
        },
        "preserve_reference_rewrite": preserve_reference,
        "reference_rewrite_rows": reference_rows,
        "retained_manufacturing_count": len(retained_ids),
        "moved_manufacturing_count": len(moved_ids),
        "moved_body_area": sum(int(row["body_area"]) for row in moved_rows),
        "moved_by_template": dict(sorted(moved_by_template.items())),
        "corridor_intersecting_body_count": len(corridor_body_ids),
        "corridor_intersecting_body_ids": corridor_body_ids,
        "pole_move_count": len(pole_rows),
        "pole_move_ids": sorted(str(row["instance_id"]) for row in pole_rows),
        "module_template_deficits": deficits,
        "retained_assignment_digest": stable_digest(
            sorted(retained_assignment.items())
        ),
        "moved_body_ids": moved_ids,
        "moved_bodies": [compact_body(row) for row in moved_rows],
        "retained_module_by_instance": dict(sorted(retained_assignment.items())),
    }


def evaluation_score(
    partition: Mapping[str, Any], evaluation: Mapping[str, Any]
) -> tuple[Any, ...]:
    corridor = evaluation["corridor"]
    seam = partition["seam"]
    return (
        int(evaluation["moved_manufacturing_count"]),
        int(seam["commodity_count"]),
        int(seam["consumer_input_slot_incidence"]),
        int(evaluation["pole_move_count"]),
        int(partition["area_imbalance"]),
        -int(corridor["width"]),
        str(corridor["axis"]),
        int(corridor["start"]),
        str(corridor["module_low"]),
        tuple(partition["module_a_operations"]),
    )


def compact_evaluation(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in evaluation.items()
        if key
        not in {
            "moved_bodies",
            "retained_module_by_instance",
        }
    }


def dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_metrics = (
        int(left["best_reference_preserving"]["moved_manufacturing_count"]),
        int(left["partition"]["seam"]["commodity_count"]),
        int(left["partition"]["seam"]["consumer_input_slot_incidence"]),
        int(left["best_reference_preserving"]["pole_move_count"]),
        int(left["partition"]["area_imbalance"]),
    )
    right_metrics = (
        int(right["best_reference_preserving"]["moved_manufacturing_count"]),
        int(right["partition"]["seam"]["commodity_count"]),
        int(right["partition"]["seam"]["consumer_input_slot_incidence"]),
        int(right["best_reference_preserving"]["pole_move_count"]),
        int(right["partition"]["area_imbalance"]),
    )
    return all(a <= b for a, b in zip(left_metrics, right_metrics, strict=True)) and any(
        a < b for a, b in zip(left_metrics, right_metrics, strict=True)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"E081 refuses nonempty run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    observed_hashes: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        observed_hashes[str(path)] = actual
        if actual != expected:
            raise RuntimeError(
                f"E081 frozen identity drift: {path}: {actual} != {expected}"
            )

    candidate_payload = read_json(HISTORY_CANDIDATES)
    pools = candidate_payload["facility_pools"]
    parent_payload = read_json(E069_PARENT)
    solution = parent_payload["solution"]
    manufacturing: list[dict[str, Any]] = []
    fixed: list[dict[str, Any]] = []
    for instance_id, solution_row in sorted(solution.items()):
        template = str(solution_row["facility_type"])
        pose_idx = int(solution_row["pose_idx"])
        pose = pools[template][pose_idx]
        row = body_record(
            instance_id=str(instance_id),
            solution_row=solution_row,
            pose=pose,
        )
        (manufacturing if template.startswith("manufacturing_") else fixed).append(row)
    if len(manufacturing) != EXPECTED_MANUFACTURING_COUNT:
        raise RuntimeError(
            f"E081 manufacturing body count drift: {len(manufacturing)}"
        )
    observed_template_counts = Counter(
        str(row["facility_type"]) for row in manufacturing
    )
    if dict(observed_template_counts) != EXPECTED_TEMPLATE_COUNTS:
        raise RuntimeError(
            f"E081 manufacturing template count drift: {observed_template_counts}"
        )

    e078 = read_json(E078_RESULT)
    if (
        e078.get("verdict")
        != "TARGET26_REFERENCE_TWO_ROW_REWRITE_STABLE_ON_FULL_FROZEN_PARENT_FACE_BUT_MINIMUM_CORES_NONUNIQUE"
        or e078["classification"].get("reference_rewrite_stable_on_full_parent_face")
        is not True
    ):
        raise RuntimeError("E081 E078 stability verdict drift")
    e074 = read_json(E074_TARGET)
    reference_targets: dict[str, str] = {}
    reference_digest_by_id: dict[str, str] = {}
    for row in e074["changed_rows"]:
        instance_id = str(row["body"]["source_instance_id"])
        reference_targets[instance_id] = str(row["zero_option"]["operation"])
        reference_digest_by_id[instance_id] = str(row["body"]["body_digest"])
    e078_witnesses = {
        str(row["source_instance_id"]): str(row["body_digest"])
        for row in e078["reference_rewrite"]["stable_body_witnesses"]
    }
    if reference_digest_by_id != e078_witnesses or len(reference_targets) != 2:
        raise RuntimeError("E081 stable reference rewrite identity drift")
    manufacturing_by_id = {
        str(row["instance_id"]): row for row in manufacturing
    }
    for instance_id, expected_digest in e078_witnesses.items():
        if manufacturing_by_id[instance_id]["body_digest"] != expected_digest:
            raise RuntimeError(
                f"E081 reference body remap drift: {instance_id}"
            )

    e080_result = read_json(E080_RESULT)
    frontier = read_json(E080_FRONTIER)
    if (
        e080_result.get("verdict")
        != "CONNECTED_BALANCED_TYPE_PARTITION_WITH_EXPLICIT_SEAM_FOUND"
        or int(frontier.get("operation_type_count", -1))
        != EXPECTED_OPERATION_COUNT
        or int(frontier.get("canonical_partition_count", -1))
        != EXPECTED_CANONICAL_PARTITION_COUNT
        or int(frontier.get("connected_partition_count", -1))
        != EXPECTED_CONNECTED_PARTITION_COUNT
    ):
        raise RuntimeError("E081 E080 frontier identity or verdict drift")
    operation_rows = {
        str(row["operation_type"]): dict(row)
        for row in frontier["operation_rows"]
    }
    operation_types = tuple(sorted(operation_rows))
    if len(operation_types) != EXPECTED_OPERATION_COUNT:
        raise RuntimeError("E081 operation row count drift")

    producers: dict[str, set[str]] = defaultdict(set)
    consumers: dict[str, set[str]] = defaultdict(set)
    for operation, row in operation_rows.items():
        for commodity in row["output_commodities"]:
            producers[str(commodity)].add(operation)
        for commodity in row["input_commodities"]:
            consumers[str(commodity)].add(operation)
    intermediate = sorted(set(producers) & set(consumers))
    adjacency: dict[str, set[str]] = {operation: set() for operation in operation_types}
    for commodity in intermediate:
        for producer in producers[commodity]:
            for consumer in consumers[commodity]:
                if producer == consumer:
                    continue
                adjacency[producer].add(consumer)
                adjacency[consumer].add(producer)

    total_area = sum(int(row["body_area"]) for row in operation_rows.values())
    anchor = operation_types[0]
    remaining = operation_types[1:]
    balanced_partitions: list[dict[str, Any]] = []
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
        if not induced_connected(side_a, adjacency) or not induced_connected(side_b, adjacency):
            continue
        connected_count += 1
        area_a = sum(int(operation_rows[operation]["body_area"]) for operation in side_a)
        if not BALANCE_LOW * total_area <= area_a <= BALANCE_HIGH * total_area:
            continue
        balanced_partitions.append(
            partition_payload(
                side_a,
                side_b,
                operation_rows=operation_rows,
                producers=producers,
                consumers=consumers,
                intermediate=intermediate,
            )
        )
    if connected_count != EXPECTED_CONNECTED_PARTITION_COUNT:
        raise RuntimeError(f"E081 connected partition drift: {connected_count}")
    if len(balanced_partitions) != EXPECTED_BALANCED_CONNECTED_COUNT:
        raise RuntimeError(
            f"E081 balanced connected partition drift: {len(balanced_partitions)}"
        )

    selected_a = tuple(
        e080_result["selected_partition"]["module_a"]["operation_types"]
    )
    selected_partition_id: str | None = None
    partition_records: list[dict[str, Any]] = []
    corridor_count = 0
    for partition in balanced_partitions:
        if tuple(partition["module_a_operations"]) == selected_a:
            selected_partition_id = str(partition["partition_id"])
        best_unconstrained: dict[str, Any] | None = None
        best_reference: dict[str, Any] | None = None
        best_by_width: dict[str, dict[str, Any]] = {}
        for axis in ("x", "y"):
            for width in CORRIDOR_WIDTHS:
                for start in range(
                    INTERIOR_MIN,
                    INTERIOR_MAX - width + 2,
                ):
                    for module_a_on_low in (True, False):
                        corridor_count += 1
                        unconstrained = evaluate_corridor(
                            partition=partition,
                            manufacturing=manufacturing,
                            fixed=fixed,
                            reference_targets=reference_targets,
                            axis=axis,
                            start=start,
                            width=width,
                            module_a_on_low=module_a_on_low,
                            preserve_reference=False,
                        )
                        if unconstrained is not None and (
                            best_unconstrained is None
                            or evaluation_score(partition, unconstrained)
                            < evaluation_score(partition, best_unconstrained)
                        ):
                            best_unconstrained = unconstrained
                        reference = evaluate_corridor(
                            partition=partition,
                            manufacturing=manufacturing,
                            fixed=fixed,
                            reference_targets=reference_targets,
                            axis=axis,
                            start=start,
                            width=width,
                            module_a_on_low=module_a_on_low,
                            preserve_reference=True,
                        )
                        if reference is None:
                            continue
                        width_key = str(width)
                        prior = best_by_width.get(width_key)
                        if prior is None or evaluation_score(partition, reference) < evaluation_score(partition, prior):
                            best_by_width[width_key] = reference
                        if best_reference is None or evaluation_score(partition, reference) < evaluation_score(partition, best_reference):
                            best_reference = reference
        if best_unconstrained is None or best_reference is None:
            raise RuntimeError(
                f"E081 partition lacks a valid corridor: {partition['partition_id']}"
            )
        partition_records.append(
            {
                "partition": partition,
                "best_unconstrained": compact_evaluation(best_unconstrained),
                "best_reference_preserving": compact_evaluation(best_reference),
                "best_reference_preserving_by_width": {
                    key: compact_evaluation(value)
                    for key, value in sorted(best_by_width.items(), key=lambda item: int(item[0]))
                },
                "reference_penalty_moved_bodies": (
                    int(best_reference["moved_manufacturing_count"])
                    - int(best_unconstrained["moved_manufacturing_count"])
                ),
                "geometry_score": list(evaluation_score(partition, best_reference)),
            }
        )
    if selected_partition_id is None:
        raise RuntimeError("E081 cannot identify E080 selected partition")

    ranked = sorted(
        partition_records,
        key=lambda row: tuple(row["geometry_score"]),
    )
    for rank, row in enumerate(ranked, 1):
        row["geometry_rank"] = rank
        row["is_e080_selected_partition"] = (
            row["partition"]["partition_id"] == selected_partition_id
        )
    selected_record = next(
        row for row in ranked if row["is_e080_selected_partition"]
    )
    geometry_winner = ranked[0]
    pareto = [
        row
        for row in ranked
        if not any(dominates(other, row) for other in ranked if other is not row)
    ]
    selected_dominated_by = [
        row["partition"]["partition_id"]
        for row in ranked
        if row is not selected_record and dominates(row, selected_record)
    ]
    selected_on_pareto = not selected_dominated_by

    if selected_record["geometry_rank"] == 1:
        verdict = "E080_SELECTED_PARTITION_SURVIVES_GEOMETRY_CONTINUATION"
        decision = "BUILD_SELECTED_REFERENCE_PRESERVING_AXIS_SEAM_REPAIR_CONTEXT"
    elif selected_on_pareto:
        verdict = "E080_SELECTED_PARTITION_REORDERED_BUT_REMAINS_GEOMETRY_PARETO"
        decision = "KEEP_GEOMETRY_PARETO_BEAM_AND_BUILD_REFERENCE_PRESERVING_REPAIR_CONTEXTS"
    else:
        verdict = "E080_SELECTED_PARTITION_GEOMETRY_DOMINATED"
        decision = "REPLACE_SINGLE_E080_SEED_WITH_DOMINATING_GEOMETRY_BEAM"

    detailed_ids = {
        str(geometry_winner["partition"]["partition_id"]),
        str(selected_record["partition"]["partition_id"]),
        *(str(row["partition"]["partition_id"]) for row in pareto),
    }
    detailed_candidates: list[dict[str, Any]] = []
    for row in ranked:
        if str(row["partition"]["partition_id"]) not in detailed_ids:
            continue
        detailed = dict(row)
        detailed_candidates.append(detailed)

    atlas = {
        "schema": "zmd_e081_axis_seam_recolor_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "input_hashes": observed_hashes,
        "manufacturing_body_count": len(manufacturing),
        "manufacturing_template_counts": dict(sorted(observed_template_counts.items())),
        "connected_partition_count": connected_count,
        "balanced_connected_partition_count": len(balanced_partitions),
        "corridor_state_evaluation_count": corridor_count,
        "corridor_widths": list(CORRIDOR_WIDTHS),
        "reference_target_operations": dict(sorted(reference_targets.items())),
        "ranked_partitions": ranked,
        "pareto_partition_ids": [
            str(row["partition"]["partition_id"]) for row in pareto
        ],
        "selected_partition_id": selected_partition_id,
        "selected_partition_geometry_rank": int(selected_record["geometry_rank"]),
        "selected_partition_on_geometry_pareto": selected_on_pareto,
        "selected_partition_dominated_by": selected_dominated_by,
        "geometry_winner_partition_id": str(
            geometry_winner["partition"]["partition_id"]
        ),
        "detailed_candidates": detailed_candidates,
        "truth_boundary": (
            "Each moved-body count is exact only in the E069 current-footprint, "
            "straight-axis-corridor, same-template operation-reassignment quotient. "
            "Moved bodies are not re-embedded and no power reclosure, front, binding, "
            "routing, throughput, or whole-layout feasibility is proved."
        ),
    }
    atlas_path = run_dir / "AXIS_SEAM_FRONTIER.json"
    write_exclusive(atlas_path, atlas)

    result = {
        "schema": "zmd_e081_axis_seam_recolor_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "connected_partition_count": connected_count,
        "balanced_connected_partition_count": len(balanced_partitions),
        "corridor_state_evaluation_count": corridor_count,
        "geometry_winner": geometry_winner,
        "e080_selected_partition": selected_record,
        "geometry_pareto_partition_count": len(pareto),
        "geometry_pareto_partition_ids": [
            str(row["partition"]["partition_id"]) for row in pareto
        ],
        "selected_partition_on_geometry_pareto": selected_on_pareto,
        "selected_partition_dominated_by": selected_dominated_by,
        "reference_target_operations": dict(sorted(reference_targets.items())),
        "frontier_path": str(atlas_path.relative_to(ROOT)),
        "frontier_sha256": sha256_file(atlas_path),
        "runner": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "truth_boundary": atlas["truth_boundary"],
    }
    result["result_digest"] = stable_digest(result)
    result_path = run_dir / "RESULT.json"
    write_exclusive(result_path, result)
    receipt = {
        "schema": "zmd_e081_axis_seam_recolor_receipt_v1",
        "result_path": str(result_path.relative_to(ROOT)),
        "result_sha256": sha256_file(result_path),
        "frontier_sha256": sha256_file(atlas_path),
        "verdict": verdict,
        "decision": decision,
    }
    write_exclusive(run_dir / "RESULT_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
