#!/usr/bin/env python3
"""E082: re-rank E080 connected partitions by historical bay-count alignment."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
from fractions import Fraction
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E082_bay_alignment_partition_frontier/run-001"
)

E080_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E080_dependency_partition_seam_frontier/run_e080.py"
)
E080_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E080_dependency_partition_seam_frontier/run-001"
)
E080_RESULT = E080_RUN / "RESULT.json"
E080_FRONTIER = E080_RUN / "PARTITION_FRONTIER.json"
E080_CONTRACT = E080_RUN / "SEAM_CONTRACT.json"

RECOVERY_ROOT = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/"
    "recovery_runs/restart-20260720T075344Z-kYNVbm"
)
BAY_PLAN = RECOVERY_ROOT / "count_closure_plan_20260720_v3.json"
ASSEMBLER = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/"
    "assemble_connected_bays.py"
)
COMPOSER = RECOVERY_ROOT / "compose_connected_bay_selection.py"

EXPECTED_HASHES = {
    E080_RUNNER: "c3eab72325aefd39ca3719bc836ef137f0f3901415079095d5e120bd435df265",
    E080_RESULT: "47f497a3f8ee26351bdc1616c8061f80d03646089c266be66f979f7393080077",
    E080_FRONTIER: "96e4e84fb88c666aee38c7be2c421a59ca4fbe7e59d570eacee5f4391fe867b7",
    E080_CONTRACT: "c44ee40995fcdd44a2ec9a8443245d1be75b51258ca9b347cd0fe1ae3563e6fc",
    BAY_PLAN: "1c9d42b00221436518f8e3635828bdad6261d0a5b005714f8817eca6194499e5",
    ASSEMBLER: "47927d4892b905a7b806a1e5916e58ecf4b1cfdf0cbc5a547fe065bc64fdedd5",
    COMPOSER: "90f54dc441aa25702ff05f283497806011ce7600dc12b572f043a5782885065e",
}

TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
EXPECTED_GLOBAL_TARGET = (132, 49, 38)
EXPECTED_BAY_COUNT = 17
EXPECTED_CONNECTED_PARTITIONS = 53
EXPECTED_CANONICAL_PARTITIONS = 65_535
BALANCE_LOW = Fraction(1, 3)
BALANCE_HIGH = Fraction(2, 3)
PRIMARY_SECONDS = 5.0
SECONDARY_SECONDS = 5.0


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def audit_module(module: Any, expected_path: Path) -> dict[str, Any]:
    expected = expected_path.resolve()
    foreign: list[dict[str, str]] = []
    functions = 0
    for name, value in sorted(vars(module).items()):
        if not inspect.isfunction(value) or value.__module__ != module.__name__:
            continue
        functions += 1
        actual = Path(value.__code__.co_filename).resolve()
        if actual != expected:
            foreign.append({"name": name, "code_filename": str(actual)})
    if foreign:
        raise RuntimeError(f"E082 foreign functions loaded: {foreign[:10]}")
    return {
        "module": module.__name__,
        "source": str(expected_path.relative_to(ROOT)),
        "source_sha256": sha256_file(expected_path),
        "function_count": functions,
        "foreign_function_count": 0,
    }


def verify_inputs() -> dict[str, Any]:
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"E082 input identity drift: {path}: {actual} != {expected}")

    result = load_json(E080_RESULT)
    frontier = load_json(E080_FRONTIER)
    contract = load_json(E080_CONTRACT)
    if (
        result.get("verdict")
        != "CONNECTED_BALANCED_TYPE_PARTITION_WITH_EXPLICIT_SEAM_FOUND"
        or int(result.get("canonical_partition_count", -1))
        != EXPECTED_CANONICAL_PARTITIONS
        or int(result.get("connected_partition_count", -1))
        != EXPECTED_CONNECTED_PARTITIONS
        or int(frontier.get("connected_partition_count", -1))
        != EXPECTED_CONNECTED_PARTITIONS
        or contract.get("selected_partition") != result.get("selected_partition")
    ):
        raise RuntimeError("E082 E080 result/frontier/contract drift")
    return {
        "checked_hashes": checked,
        "e080_result_digest": result.get("result_digest"),
        "e080_selected_partition_id": result["selected_partition"]["partition_id"],
    }


def parse_bay_plan(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    if (
        plan.get("schema_version") != "connected_bay_count_closure_plan.v3"
        or plan.get("status") != "SEARCH_PLAN_ONLY"
        or tuple(int(value) for value in plan.get("global_target", []))
        != EXPECTED_GLOBAL_TARGET
    ):
        raise RuntimeError("E082 historical bay plan identity/semantic drift")

    big = plan.get("big_bay_target")
    non_big = plan.get("non_big_component_targets")
    if not isinstance(big, Mapping) or not isinstance(non_big, Mapping):
        raise RuntimeError("E082 malformed historical bay plan")
    components = tuple(int(value) for value in big.get("components", []))
    if components != (0, 1, 2):
        raise RuntimeError(f"E082 big-bay component drift: {components}")
    rows = big.get("rows")
    if not isinstance(rows, Mapping):
        raise RuntimeError("E082 big-bay rows malformed")

    capacities: dict[int, tuple[int, int, int]] = {}
    for component, label in zip(components, ("F", "G", "H"), strict=True):
        raw = rows.get(label)
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) != 3:
            raise RuntimeError(f"E082 malformed big-bay row {label}: {raw}")
        capacities[component] = tuple(int(value) for value in raw)  # type: ignore[assignment]
    if set(non_big) != {str(value) for value in range(3, EXPECTED_BAY_COUNT)}:
        raise RuntimeError("E082 non-big bay ID set drift")
    for component in range(3, EXPECTED_BAY_COUNT):
        raw = non_big[str(component)]
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) != 3:
            raise RuntimeError(f"E082 malformed bay row {component}: {raw}")
        capacities[component] = tuple(int(value) for value in raw)  # type: ignore[assignment]

    total = tuple(
        sum(capacities[component][index] for component in range(EXPECTED_BAY_COUNT))
        for index in range(3)
    )
    if total != EXPECTED_GLOBAL_TARGET:
        raise RuntimeError(f"E082 bay capacity total drift: {total}")
    return [
        {
            "bay_id": component,
            "capacity": list(capacities[component]),
            "capacity_total": sum(capacities[component]),
        }
        for component in range(EXPECTED_BAY_COUNT)
    ]


def build_subset_table(
    bay_rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[int, int, int], dict[str, Any]]:
    capacities = [tuple(int(value) for value in row["capacity"]) for row in bay_rows]
    table: dict[tuple[int, int, int], dict[str, Any]] = {}
    for mask in range(1 << len(capacities)):
        target = tuple(
            sum(capacities[bay][index] for bay in range(len(capacities)) if mask & (1 << bay))
            for index in range(3)
        )
        row = table.setdefault(target, {"count": 0, "sample_masks": []})
        row["count"] = int(row["count"]) + 1
        if len(row["sample_masks"]) < 8:
            row["sample_masks"].append(mask)
    return table


def solve_min_mixed(
    target: tuple[int, int, int],
    bay_rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    model = cp_model.CpModel()
    allocations: list[list[Any]] = []
    full_a: list[Any] = []
    full_b: list[Any] = []
    mixed: list[Any] = []
    for bay, row in enumerate(bay_rows):
        capacity = tuple(int(value) for value in row["capacity"])
        variables = [
            model.NewIntVar(0, capacity[index], f"e082_a_{bay}_{index}")
            for index in range(3)
        ]
        allocations.append(variables)
        all_a = model.NewBoolVar(f"e082_full_a_{bay}")
        all_b = model.NewBoolVar(f"e082_full_b_{bay}")
        split = model.NewBoolVar(f"e082_mixed_{bay}")
        model.AddExactlyOne(all_a, all_b, split)
        for index, variable in enumerate(variables):
            model.Add(variable == capacity[index]).OnlyEnforceIf(all_a)
            model.Add(variable == 0).OnlyEnforceIf(all_b)
        model.Add(cp_model.LinearExpr.Sum(variables) >= 1).OnlyEnforceIf(split)
        model.Add(
            cp_model.LinearExpr.Sum(variables) <= sum(capacity) - 1
        ).OnlyEnforceIf(split)
        full_a.append(all_a)
        full_b.append(all_b)
        mixed.append(split)

    for index in range(3):
        model.Add(
            cp_model.LinearExpr.Sum(
                [allocations[bay][index] for bay in range(len(bay_rows))]
            )
            == target[index]
        )
    mixed_sum = cp_model.LinearExpr.Sum(mixed)
    model.Minimize(mixed_sum)

    primary = cp_model.CpSolver()
    primary.parameters.max_time_in_seconds = PRIMARY_SECONDS
    primary.parameters.num_search_workers = 1
    primary.parameters.random_seed = seed
    started = time.monotonic()
    status = primary.Solve(model)
    elapsed = time.monotonic() - started
    if status != cp_model.OPTIMAL:
        return {
            "status": primary.StatusName(status),
            "elapsed_seconds": elapsed,
            "best_bound": float(primary.BestObjectiveBound()),
            "minimum_mixed_bays": None,
        }
    optimum = int(round(primary.ObjectiveValue()))

    model.Add(mixed_sum == optimum)
    model.ClearObjective()
    # Deterministic materialization only; the allocation is not claimed unique.
    tie_terms: list[Any] = []
    for bay, variables in enumerate(allocations):
        for template_index, variable in enumerate(variables):
            tie_terms.append((1 + bay * 3 + template_index) * variable)
    model.Minimize(cp_model.LinearExpr.Sum(tie_terms))
    secondary = cp_model.CpSolver()
    secondary.parameters.max_time_in_seconds = SECONDARY_SECONDS
    secondary.parameters.num_search_workers = 1
    secondary.parameters.random_seed = seed + 1000
    secondary_status = secondary.Solve(model)
    if secondary_status != cp_model.OPTIMAL:
        return {
            "status": "PRIMARY_OPTIMAL_SECONDARY_" + secondary.StatusName(secondary_status),
            "elapsed_seconds": elapsed,
            "best_bound": float(primary.BestObjectiveBound()),
            "minimum_mixed_bays": optimum,
        }

    allocation_rows: list[dict[str, Any]] = []
    for bay, row in enumerate(bay_rows):
        capacity = tuple(int(value) for value in row["capacity"])
        assigned = tuple(int(secondary.Value(variable)) for variable in allocations[bay])
        if secondary.Value(full_a[bay]):
            classification = "FULL_A"
        elif secondary.Value(full_b[bay]):
            classification = "FULL_B"
        elif secondary.Value(mixed[bay]):
            classification = "MIXED"
        else:
            raise RuntimeError(f"E082 bay classification drift: {bay}")
        allocation_rows.append(
            {
                "bay_id": int(row["bay_id"]),
                "capacity": list(capacity),
                "module_a_template_counts": list(assigned),
                "module_b_template_counts": [
                    capacity[index] - assigned[index] for index in range(3)
                ],
                "classification": classification,
            }
        )
    if sum(row["classification"] == "MIXED" for row in allocation_rows) != optimum:
        raise RuntimeError("E082 mixed-bay extraction drift")

    return {
        "status": "OPTIMAL",
        "elapsed_seconds": elapsed,
        "best_bound": float(primary.BestObjectiveBound()),
        "minimum_mixed_bays": optimum,
        "secondary_status": "OPTIMAL",
        "secondary_objective": int(round(secondary.ObjectiveValue())),
        "allocation": allocation_rows,
        "full_a_bays": [
            row["bay_id"] for row in allocation_rows if row["classification"] == "FULL_A"
        ],
        "full_b_bays": [
            row["bay_id"] for row in allocation_rows if row["classification"] == "FULL_B"
        ],
        "mixed_bays": [
            row["bay_id"] for row in allocation_rows if row["classification"] == "MIXED"
        ],
        "allocation_digest": stable_digest(allocation_rows),
    }


def module_template_target(module: Mapping[str, Any]) -> tuple[int, int, int]:
    operations = module.get("operations")
    if not isinstance(operations, Sequence):
        raise RuntimeError("E082 module operations malformed")
    return tuple(
        sum(
            int(row["count"])
            for row in operations
            if isinstance(row, Mapping) and str(row["facility_type"]) == template
        )
        for template in TEMPLATES
    )  # type: ignore[return-value]


def direction_count(seam: Mapping[str, Any]) -> int:
    directions = {
        str(row["direction"])
        for row in seam.get("obligations", [])
        if isinstance(row, Mapping)
    }
    return len(directions)


def geometry_score(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    alignment = candidate["bay_alignment"]
    seam = candidate["seam"]
    return (
        int(alignment["minimum_mixed_bays"]),
        int(candidate["seam_direction_count"]),
        int(seam["commodity_count"]),
        int(seam["consumer_input_slot_incidence"]),
        int(seam["dependency_edge_count"]),
        int(candidate["area_imbalance"]),
        int(candidate["instance_imbalance"]),
        tuple(candidate["module_a"]["operation_types"]),
    )


def pareto_dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_metrics = (
        int(left["bay_alignment"]["minimum_mixed_bays"]),
        int(left["seam_direction_count"]),
        int(left["seam"]["commodity_count"]),
        int(left["seam"]["consumer_input_slot_incidence"]),
        int(left["area_imbalance"]),
    )
    right_metrics = (
        int(right["bay_alignment"]["minimum_mixed_bays"]),
        int(right["seam_direction_count"]),
        int(right["seam"]["commodity_count"]),
        int(right["seam"]["consumer_input_slot_incidence"]),
        int(right["area_imbalance"]),
    )
    return all(a <= b for a, b in zip(left_metrics, right_metrics, strict=True)) and any(
        a < b for a, b in zip(left_metrics, right_metrics, strict=True)
    )


def pareto_frontier(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    frontier: list[dict[str, Any]] = []
    for candidate in sorted((dict(row) for row in candidates), key=geometry_score):
        if any(pareto_dominates(existing, candidate) for existing in frontier):
            continue
        frontier = [
            existing
            for existing in frontier
            if not pareto_dominates(candidate, existing)
        ]
        frontier.append(candidate)
    return sorted(frontier, key=geometry_score)


def compact(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "partition_id": candidate["partition_id"],
        "module_a": candidate["module_a"],
        "module_b": candidate["module_b"],
        "seam": candidate["seam"],
        "seam_direction_count": candidate["seam_direction_count"],
        "external_source_inputs": candidate["external_source_inputs"],
        "final_sink_outputs": candidate["final_sink_outputs"],
        "area_imbalance": candidate["area_imbalance"],
        "instance_imbalance": candidate["instance_imbalance"],
        "total_body_area": candidate["total_body_area"],
        "module_a_template_target": candidate["module_a_template_target"],
        "bay_alignment": candidate["bay_alignment"],
        "geometry_score": list(geometry_score(candidate)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    if (run_dir / "RESULT.json").exists() or (run_dir / "FAILURE.json").exists():
        raise FileExistsError(f"E082 terminal output already exists: {run_dir}")

    identity = verify_inputs()
    e080 = import_module("zmd_e082_e080", E080_RUNNER)
    origin_audit = audit_module(e080, E080_RUNNER)
    e080_result = load_json(E080_RESULT)
    e080_frontier = load_json(E080_FRONTIER)
    plan = load_json(BAY_PLAN)
    bay_rows = parse_bay_plan(plan)
    subset_table = build_subset_table(bay_rows)

    operation_rows = {
        str(row["operation_type"]): dict(row)
        for row in e080_frontier["operation_rows"]
    }
    operation_types = tuple(sorted(operation_rows))
    if len(operation_types) != 17:
        raise RuntimeError(f"E082 operation type count drift: {operation_types}")

    producer_ops: dict[str, set[str]] = defaultdict(set)
    consumer_ops: dict[str, set[str]] = defaultdict(set)
    for operation, row in operation_rows.items():
        for commodity in row["output_commodities"]:
            producer_ops[str(commodity)].add(operation)
        for commodity in row["input_commodities"]:
            consumer_ops[str(commodity)].add(operation)
    intermediate = sorted(set(producer_ops) & set(consumer_ops))
    external_sources = sorted(set(consumer_ops) - set(producer_ops))
    final_sinks = sorted(set(producer_ops) - set(consumer_ops))
    adjacency: dict[str, set[str]] = {operation: set() for operation in operation_types}
    for commodity in intermediate:
        for producer in producer_ops[commodity]:
            for consumer in consumer_ops[commodity]:
                if producer == consumer:
                    continue
                adjacency[producer].add(consumer)
                adjacency[consumer].add(producer)

    anchor = operation_types[0]
    remaining = operation_types[1:]
    total_body_area = sum(int(row["body_area"]) for row in operation_rows.values())
    total_instances = sum(int(row["count"]) for row in operation_rows.values())
    alignment_cache: dict[tuple[int, int, int], dict[str, Any]] = {}
    connected: list[dict[str, Any]] = []
    canonical_count = 0
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
        canonical_count += 1
        if not e080.induced_connected(side_a, adjacency) or not e080.induced_connected(
            side_b, adjacency
        ):
            continue

        module_a = e080.module_payload(side_a, operation_rows)
        module_b = e080.module_payload(side_b, operation_rows)
        target = module_template_target(module_a)
        if target not in alignment_cache:
            alignment_cache[target] = solve_min_mixed(
                target,
                bay_rows,
                seed=81_000 + len(alignment_cache),
            )
        alignment = dict(alignment_cache[target])
        if alignment.get("status") != "OPTIMAL":
            raise RuntimeError(f"E082 alignment nonterminal for target {target}: {alignment}")
        subset = subset_table.get(target, {"count": 0, "sample_masks": []})
        alignment["whole_bay_subset_count"] = int(subset["count"])
        alignment["whole_bay_subset_samples"] = [
            [bay for bay in range(EXPECTED_BAY_COUNT) if mask_value & (1 << bay)]
            for mask_value in subset["sample_masks"]
        ]
        if (alignment["minimum_mixed_bays"] == 0) != (int(subset["count"]) > 0):
            raise RuntimeError(f"E082 zero-mixed subset cross-check drift for {target}")

        seam = e080.seam_payload(
            side_a,
            side_b,
            producer_ops,
            consumer_ops,
            operation_rows,
            intermediate,
        )
        external_inputs = (
            e080.external_interface_payload(
                side_a,
                operation_rows,
                external_sources,
                side="A",
                direction="input",
            )
            + e080.external_interface_payload(
                side_b,
                operation_rows,
                external_sources,
                side="B",
                direction="input",
            )
        )
        final_outputs = (
            e080.external_interface_payload(
                side_a,
                operation_rows,
                final_sinks,
                side="A",
                direction="output",
            )
            + e080.external_interface_payload(
                side_b,
                operation_rows,
                final_sinks,
                side="B",
                direction="output",
            )
        )
        connected.append(
            {
                "partition_id": f"partition_{canonical_count:05d}",
                "module_a": module_a,
                "module_b": module_b,
                "seam": seam,
                "seam_direction_count": direction_count(seam),
                "external_source_inputs": external_inputs,
                "final_sink_outputs": final_outputs,
                "area_imbalance": abs(
                    int(module_a["body_area"]) - int(module_b["body_area"])
                ),
                "instance_imbalance": abs(
                    int(module_a["mandatory_instance_count"])
                    - int(module_b["mandatory_instance_count"])
                ),
                "total_body_area": total_body_area,
                "total_instances": total_instances,
                "module_a_template_target": list(target),
                "bay_alignment": alignment,
            }
        )

    if canonical_count != EXPECTED_CANONICAL_PARTITIONS or len(connected) != EXPECTED_CONNECTED_PARTITIONS:
        raise RuntimeError(
            f"E082 partition reproduction drift: canonical={canonical_count} "
            f"connected={len(connected)}"
        )

    old_ops = tuple(e080_result["selected_partition"]["module_a"]["operation_types"])
    old_matches = [
        row for row in connected if tuple(row["module_a"]["operation_types"]) == old_ops
    ]
    if len(old_matches) != 1:
        raise RuntimeError(f"E082 old seed match drift: {len(old_matches)}")
    seam_first = old_matches[0]

    balanced = [
        row
        for row in connected
        if BALANCE_LOW * total_body_area
        <= int(row["module_a"]["body_area"])
        <= BALANCE_HIGH * total_body_area
    ]
    if not balanced:
        raise RuntimeError("E082 balanced connected set is empty")
    geometry_aware = min(balanced, key=geometry_score)
    exact_whole_bay = [
        row for row in connected if int(row["bay_alignment"]["minimum_mixed_bays"]) == 0
    ]
    if not exact_whole_bay:
        raise RuntimeError("E082 expected one whole-bay-aligned connected partition")

    old_mixed = int(seam_first["bay_alignment"]["minimum_mixed_bays"])
    new_mixed = int(geometry_aware["bay_alignment"]["minimum_mixed_bays"])
    old_commodities = int(seam_first["seam"]["commodity_count"])
    new_commodities = int(geometry_aware["seam"]["commodity_count"])
    reorder = (
        tuple(geometry_aware["module_a"]["operation_types"]) != old_ops
        and new_mixed < old_mixed
        and new_commodities <= old_commodities
    )
    if reorder:
        verdict = "BAY_ALIGNMENT_REORDERS_BALANCED_SEAM_FRONTIER"
        decision = (
            "BUILD_ONE_MIXED_BAY_GEOMETRY_AWARE_SEED_KEEP_E080_SEAM_FIRST_AS_CONTROL"
        )
    else:
        verdict = "E080_SEAM_FIRST_SEED_SURVIVES_BAY_ALIGNMENT"
        decision = "BUILD_E080_SEED_IN_BOUNDED_BAY_CONSTRUCTOR"

    mixed_histogram = Counter(
        int(row["bay_alignment"]["minimum_mixed_bays"]) for row in connected
    )
    balanced_mixed_histogram = Counter(
        int(row["bay_alignment"]["minimum_mixed_bays"]) for row in balanced
    )
    all_frontier = pareto_frontier(connected)
    balanced_frontier = pareto_frontier(balanced)

    comparison = {
        "seam_first_seed": compact(seam_first),
        "geometry_aware_seed": compact(geometry_aware),
        "whole_bay_aligned_control": compact(min(exact_whole_bay, key=geometry_score)),
        "delta_geometry_minus_seam_first": {
            "mixed_bays": new_mixed - old_mixed,
            "seam_directions": int(geometry_aware["seam_direction_count"])
            - int(seam_first["seam_direction_count"]),
            "seam_commodities": new_commodities - old_commodities,
            "seam_consumer_input_slots": int(
                geometry_aware["seam"]["consumer_input_slot_incidence"]
            )
            - int(seam_first["seam"]["consumer_input_slot_incidence"]),
            "area_imbalance": int(geometry_aware["area_imbalance"])
            - int(seam_first["area_imbalance"]),
            "instance_imbalance": int(geometry_aware["instance_imbalance"])
            - int(seam_first["instance_imbalance"]),
        },
    }

    frontier_payload = {
        "schema": "zmd_e082_bay_alignment_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "historical_plan_status": plan["status"],
        "historical_plan_claim_boundary": plan["claim_boundary"],
        "bay_rows": bay_rows,
        "canonical_partition_count": canonical_count,
        "connected_partition_count": len(connected),
        "balanced_connected_partition_count": len(balanced),
        "unique_template_targets": len(alignment_cache),
        "mixed_bay_histogram": {
            str(key): int(value) for key, value in sorted(mixed_histogram.items())
        },
        "balanced_mixed_bay_histogram": {
            str(key): int(value)
            for key, value in sorted(balanced_mixed_histogram.items())
        },
        "connected_partitions": [compact(row) for row in sorted(connected, key=geometry_score)],
        "all_connected_pareto_frontier": [compact(row) for row in all_frontier],
        "balanced_pareto_frontier": [compact(row) for row in balanced_frontier],
        "comparison": comparison,
        "selection_criterion": [
            "minimum_mixed_bays",
            "minimum_seam_directions",
            "minimum_seam_commodities",
            "minimum_consumer_input_slot_incidence",
            "minimum_dependency_edges",
            "minimum_area_imbalance",
            "minimum_instance_imbalance",
            "stable_operation_type_order",
        ],
        "truth_boundary": (
            "Bay alignment is exact only in a historical SEARCH_PLAN_ONLY template-count "
            "scaffold. It is an optimistic lower bound on mixed physical bays and proves no "
            "current bay selection, pose, dock, power, binding, route, or throughput."
        ),
    }
    frontier_path = run_dir / "BAY_ALIGNMENT_FRONTIER.json"
    atomic_json(frontier_path, frontier_payload)

    seed_payload = {
        "schema": "zmd_e082_geometry_aware_seed_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "geometry_aware_seed": compact(geometry_aware),
        "seam_first_control": compact(seam_first),
        "whole_bay_aligned_control": compact(min(exact_whole_bay, key=geometry_score)),
        "comparison": comparison["delta_geometry_minus_seam_first"],
        "next_discriminator": (
            "Materialize or refute the geometry-aware seed in the historical 17-bay geometry, "
            "with its one mixed count bay treated explicitly; compare against the E080 "
            "seam-first seed before building a new coordinate master."
        ),
        "truth_boundary": frontier_payload["truth_boundary"],
    }
    seed_path = run_dir / "GEOMETRY_AWARE_SEED.json"
    atomic_json(seed_path, seed_payload)

    result = {
        "schema": "zmd_e082_bay_alignment_partition_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "module_origin_audit": origin_audit,
        "historical_bay_plan": {
            "path": str(BAY_PLAN.relative_to(ROOT)),
            "sha256": sha256_file(BAY_PLAN),
            "schema": plan["schema_version"],
            "status": plan["status"],
            "claim_boundary": plan["claim_boundary"],
            "bay_count": len(bay_rows),
            "global_template_target": list(EXPECTED_GLOBAL_TARGET),
            "required_new_local_results": plan.get("required_new_local_results"),
        },
        "canonical_partition_count": canonical_count,
        "connected_partition_count": len(connected),
        "balanced_connected_partition_count": len(balanced),
        "unique_template_targets": len(alignment_cache),
        "mixed_bay_histogram": frontier_payload["mixed_bay_histogram"],
        "balanced_mixed_bay_histogram": frontier_payload[
            "balanced_mixed_bay_histogram"
        ],
        "geometry_aware_pareto_count": len(all_frontier),
        "balanced_geometry_aware_pareto_count": len(balanced_frontier),
        "comparison": comparison,
        "reorders_e080_seed": reorder,
        "frontier_path": str(frontier_path.relative_to(ROOT)),
        "frontier_sha256": sha256_file(frontier_path),
        "seed_path": str(seed_path.relative_to(ROOT)),
        "seed_sha256": sha256_file(seed_path),
        "runner": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "truth_boundary": frontier_payload["truth_boundary"],
    }
    result["result_digest"] = stable_digest(result)
    result_path = run_dir / "RESULT.json"
    atomic_json(result_path, result)
    receipt = {
        "schema": "zmd_e082_bay_alignment_partition_receipt_v1",
        "result_path": str(result_path.relative_to(ROOT)),
        "result_sha256": sha256_file(result_path),
        "frontier_sha256": sha256_file(frontier_path),
        "seed_sha256": sha256_file(seed_path),
        "verdict": verdict,
        "decision": decision,
    }
    atomic_json(run_dir / "RESULT_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
