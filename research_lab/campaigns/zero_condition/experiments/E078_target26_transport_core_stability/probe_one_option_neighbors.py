#!/usr/bin/env python3
"""E078 arm 2: exhaust every one-option target-26 parent-face neighbor."""

from __future__ import annotations

from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

from ortools.sat.python import cp_model

HERE = Path(__file__).resolve().parent
SUPPORT = HERE / "probe_support_neighbors.py"


def load_support() -> Any:
    spec = importlib.util.spec_from_file_location("zmd_e078_support_for_options", SUPPORT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SUPPORT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module.__name__] = module
    spec.loader.exec_module(module)
    return module


base = load_support()


def fixed_neighbor(
    destination: int,
    option_index: int,
    *,
    seed: int,
) -> list[dict[str, Any]] | None:
    model = cp_model.CpModel()
    built = base.e074.add_assignment_copy(
        model=model,
        prefix=f"e078_option_parent_{destination}_{option_index}",
        rows_by_destination=base.actual,
        operation_counts=base.e061.OPERATION_COUNTS,
        sink_components=base.context["sink_space"]["components"],
    )
    base.add_parent_face_constraints(model, built)
    for row_destination in range(base.DESTINATION_COUNT):
        chosen = (
            option_index
            if row_destination == destination
            else base.reference_native_index[row_destination]
        )
        model.Add(built["x_vars"][(row_destination, chosen)] == 1)
    run = base.solver(seed, 10.0)
    status = run.Solve(model)
    if status == cp_model.INFEASIBLE:
        return None
    if status != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E078 one-option parent nonterminal at {destination}/{option_index}: "
            f"{run.StatusName(status)}"
        )
    return base.selected_assignment(run, base.actual, built["x_vars"])


def main() -> int:
    raw_alternatives = 0
    valid_alternatives = 0
    valid_by_destination: Counter[int] = Counter()
    primary_statuses: Counter[str] = Counter()
    core_sizes: Counter[int] = Counter()
    reference_support_statuses: Counter[str] = Counter()
    alternate_support_statuses: Counter[str] = Counter()
    alternate_synthetic_statuses: Counter[str] = Counter()
    selected_supports: Counter[tuple[int, ...]] = Counter()
    selected_synthetic_destinations: Counter[int] = Counter()
    anomalies: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for destination in range(base.DESTINATION_COUNT):
        for option_index, option in enumerate(base.actual[destination]):
            if option_index == base.reference_native_index[destination]:
                continue
            raw_alternatives += 1
            baseline = fixed_neighbor(
                destination,
                option_index,
                seed=81000 + destination * 16 + option_index,
            )
            if baseline is None:
                continue
            valid_alternatives += 1
            valid_by_destination[destination] += 1
            transport = base.solve_zero_from_fixed_baseline(
                baseline,
                seed=82000 + destination * 16 + option_index,
            )
            primary = str(transport["primary_status"])
            primary_statuses[primary] += 1
            minimum = transport.get("minimum_changed_row_count")
            if minimum is not None:
                core_sizes[int(minimum)] += 1
            reference_support_statuses[str(transport["reference_support_status"])] += 1
            alternate_support_statuses[str(transport["alternate_support_status"])] += 1
            alternate_synthetic_statuses[
                str(transport["alternate_synthetic_destination_status"])
            ] += 1
            support = tuple(
                int(value) for value in transport.get("selected_changed_destinations", [])
            )
            if support:
                selected_supports[support] += 1
            synthetic = transport.get("selected_synthetic_destination")
            if synthetic is not None:
                selected_synthetic_destinations[int(synthetic)] += 1

            record = {
                "changed_destination_local": destination,
                "changed_stable_body": {
                    "source_instance_id": str(
                        base.body_by_destination[destination]["source_instance_id"]
                    ),
                    "body_digest": str(
                        base.body_by_destination[destination]["body_digest"]
                    ),
                },
                "reference_native_option_index": base.reference_native_index[destination],
                "neighbor_native_option_index": option_index,
                "neighbor_option": base.e074.option_payload(
                    option,
                    option_index=option_index,
                ),
                "baseline_assignment_digest": base.e074.stable_digest(baseline),
                "transport": transport,
            }
            records.append(record)
            if (
                primary != "OPTIMAL"
                or minimum != 2
                or str(transport["reference_support_status"]) != "OPTIMAL"
                or support != base.CORE_ROWS
                or synthetic != base.CORE_ROWS[1]
            ):
                anomalies.append(record)

    summary = {
        "status": "OPTIMAL" if not anomalies else "COUNTEREXAMPLE_FOUND",
        "target": base.TARGET,
        "raw_one_option_alternative_count": raw_alternatives,
        "valid_one_option_neighbor_count": valid_alternatives,
        "valid_destination_support_count": len(valid_by_destination),
        "valid_alternatives_by_destination": {
            str(destination): count
            for destination, count in sorted(valid_by_destination.items())
        },
        "transport_primary_status_counts": dict(sorted(primary_statuses.items())),
        "transport_core_size_distribution": {
            str(size): count for size, count in sorted(core_sizes.items())
        },
        "reference_support_status_counts": dict(
            sorted(reference_support_statuses.items())
        ),
        "alternate_support_status_counts": dict(
            sorted(alternate_support_statuses.items())
        ),
        "alternate_synthetic_status_counts": dict(
            sorted(alternate_synthetic_statuses.items())
        ),
        "selected_support_counts": {
            ",".join(str(value) for value in support): count
            for support, count in sorted(selected_supports.items())
        },
        "selected_synthetic_destination_counts": {
            str(destination): count
            for destination, count in sorted(selected_synthetic_destinations.items())
        },
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "records": records,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
