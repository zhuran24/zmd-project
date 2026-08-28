#!/usr/bin/env python3
"""E078 arm 1 and shared model helpers for target-26 transport stability."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
TARGET = 26
CORE_ROWS = (8, 9)
DESTINATION_COUNT = 38
MAX_NEIGHBOR_SUPPORTS = 64
SOLVE_SECONDS = 30.0

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E074_RUNNER = EXPERIMENT_ROOT / "E074_minimum_assignment_transport_core/run_e074.py"
SOURCE_PINS = {
    E074_RUNNER: "74e2720cf4b7aaa56fb004864f54c99710b004ae15bb77c5582a205558c67b25",
    EXPERIMENT_ROOT / "E061_all_one_object_signature_frontier/run_e061.py": "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    EXPERIMENT_ROOT / "E062_one_object_tradeoff_atlas/run_e062.py": "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    EXPERIMENT_ROOT / "E063_pole_conditioned_second_object_frontier/run_e063.py": "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    EXPERIMENT_ROOT / "E069_six4_near_miss_complete_face/run_e069.py": "2061d59f2f1e0bf28ad27bca1730a90323f6efca38a266675115717e8969b598",
}
TARGET_WITNESS = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E074_minimum_assignment_transport_core/run-001/"
    "TARGET_026_TRANSPORT.json"
)
TARGET_WITNESS_SHA256 = "609e0be6613f27531e9a24bc757b3dbeb7574d6422e9eb55615cf117d74658f4"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


for source_path, expected_sha in SOURCE_PINS.items():
    actual_sha = sha256_file(source_path)
    if actual_sha != expected_sha:
        raise RuntimeError(
            f"E078 source identity drift: {source_path}: {actual_sha} != {expected_sha}"
        )
if sha256_file(TARGET_WITNESS) != TARGET_WITNESS_SHA256:
    raise RuntimeError("E078 target-26 witness identity drift")

e074 = load_module("zmd_e078_e074", E074_RUNNER)
e061 = e074.import_module("zmd_e078_e061", e074.E061_RUNNER)
e062 = e074.import_module("zmd_e078_e062", e074.E062_RUNNER)
e063 = e074.import_module("zmd_e078_e063", e074.E063_RUNNER)
e069 = e074.import_module("zmd_e078_e069", e074.E069_RUNNER)

context = e069.reconstruct_parent(e061, e062, e063)
actual = e074.normalize_actual_options(context["options"])
bodies = e061.body_rows(
    context["solution"],
    context["base"]["inputs"]["pools"],
    context["base"]["e014"],
)
witness = json.loads(TARGET_WITNESS.read_text(encoding="utf-8"))
reference_assignment = list(witness["baseline_assignment"])
if [int(row["destination"]) for row in reference_assignment] != list(
    range(DESTINATION_COUNT)
):
    raise RuntimeError("E078 reference assignment destination order drift")
reference_by_destination = {
    int(row["destination"]): dict(row) for row in reference_assignment
}
reference_native_index = {
    destination: int(row["selected_option"]["native_option_index"])
    for destination, row in reference_by_destination.items()
}
body_by_destination = {
    destination: dict(row["body"])
    for destination, row in reference_by_destination.items()
}


def solver(seed: int, seconds: float = SOLVE_SECONDS) -> cp_model.CpSolver:
    value = cp_model.CpSolver()
    value.parameters.max_time_in_seconds = float(seconds)
    value.parameters.num_search_workers = 8
    value.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    value.parameters.symmetry_level = 3
    value.parameters.cp_model_probing_level = 3
    value.parameters.random_seed = int(seed)
    return value


def add_parent_face_constraints(
    model: cp_model.CpModel,
    built: Mapping[str, Any],
    target: int = TARGET,
) -> None:
    for component in built["components"]:
        source = built["fine_sources"][component]
        sink = built["fine_sinks"][component]
        if int(component) == int(target):
            model.Add(source == 1)
            model.Add(sink == 0)
        else:
            model.Add(source == sink)


def build_parent_model(
    *,
    prefix: str,
) -> tuple[cp_model.CpModel, dict[str, Any], dict[int, Any], Any]:
    model = cp_model.CpModel()
    built = e074.add_assignment_copy(
        model=model,
        prefix=prefix,
        rows_by_destination=actual,
        operation_counts=e061.OPERATION_COUNTS,
        sink_components=context["sink_space"]["components"],
    )
    add_parent_face_constraints(model, built)
    changed: dict[int, Any] = {}
    for destination in range(DESTINATION_COUNT):
        variable = model.NewBoolVar(f"{prefix}_changed_{destination}")
        reference = built["x_vars"][(destination, reference_native_index[destination])]
        model.Add(variable + reference == 1)
        changed[destination] = variable
    return model, built, changed, cp_model.LinearExpr.Sum(list(changed.values()))


def selected_assignment(
    solve: cp_model.CpSolver,
    rows: Mapping[int, Sequence[Mapping[str, Any]]],
    x_vars: Mapping[tuple[int, int], Any],
) -> list[dict[str, Any]]:
    return e074.selected_assignment(
        solver=solve,
        rows_by_destination=rows,
        x_vars=x_vars,
        bodies=bodies,
    )


def build_zero_model(
    baseline_assignment: Sequence[Mapping[str, Any]],
    *,
    prefix: str,
) -> tuple[
    cp_model.CpModel,
    dict[int, list[dict[str, Any]]],
    dict[str, Any],
    dict[int, Any],
    Any,
    dict[int, Any],
]:
    baseline_by_destination = {
        int(row["destination"]): row for row in baseline_assignment
    }
    if sorted(baseline_by_destination) != list(range(DESTINATION_COUNT)):
        raise RuntimeError("E078 fixed baseline destination domain drift")

    zero_rows = e074.tagged_zero_options(actual, target_component=TARGET)
    model = cp_model.CpModel()
    zero = e074.add_assignment_copy(
        model=model,
        prefix=prefix,
        rows_by_destination=zero_rows,
        operation_counts=e061.OPERATION_COUNTS,
        sink_components=context["sink_space"]["components"],
    )
    for component in zero["components"]:
        model.Add(zero["fine_sources"][component] == zero["fine_sinks"][component])

    synthetic_by_destination: dict[int, Any] = {}
    for destination, rows in zero_rows.items():
        variables = [
            zero["x_vars"][(destination, option_index)]
            for option_index, option in enumerate(rows)
            if bool(option["synthetic"])
        ]
        if len(variables) != 1:
            raise RuntimeError(
                f"E078 synthetic option count drift at destination {destination}: {len(variables)}"
            )
        synthetic_by_destination[int(destination)] = variables[0]
    model.Add(cp_model.LinearExpr.Sum(list(synthetic_by_destination.values())) == 1)

    changed: dict[int, Any] = {}
    for destination, baseline_row in sorted(baseline_by_destination.items()):
        native_index = baseline_row["selected_option"].get("native_option_index")
        if native_index is None:
            raise RuntimeError("E078 fixed baseline contains a synthetic option")
        variable = model.NewBoolVar(f"{prefix}_changed_{destination}")
        model.Add(
            variable + zero["x_vars"][(destination, int(native_index))] == 1
        )
        changed[destination] = variable
    changed_sum = cp_model.LinearExpr.Sum(list(changed.values()))
    return model, zero_rows, zero, changed, changed_sum, synthetic_by_destination


def solve_zero_from_fixed_baseline(
    baseline_assignment: Sequence[Mapping[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    model, zero_rows, zero, changed, changed_sum, synthetic = build_zero_model(
        baseline_assignment,
        prefix=f"e078_zero_{seed}",
    )
    model.Minimize(changed_sum)
    primary = solver(seed)
    started = time.monotonic()
    primary_status = primary.Solve(model)
    elapsed = time.monotonic() - started
    record: dict[str, Any] = {
        "primary_status": primary.StatusName(primary_status),
        "primary_best_bound": float(primary.BestObjectiveBound()),
        "primary_elapsed_seconds": elapsed,
        "minimum_changed_row_count": None,
        "reference_support_status": None,
        "alternate_support_status": None,
        "alternate_synthetic_destination_status": None,
        "selected_changed_destinations": [],
        "selected_synthetic_destination": None,
    }
    if primary_status != cp_model.OPTIMAL:
        return record
    minimum = int(round(primary.ObjectiveValue()))
    record["minimum_changed_row_count"] = minimum

    reference_model, _, _, reference_changed, reference_sum, reference_synthetic = (
        build_zero_model(
            baseline_assignment,
            prefix=f"e078_reference_{seed}",
        )
    )
    reference_model.Add(reference_sum == minimum)
    reference_model.Add(reference_changed[CORE_ROWS[0]] == 1)
    reference_model.Add(reference_changed[CORE_ROWS[1]] == 1)
    reference_model.Add(reference_synthetic[CORE_ROWS[1]] == 1)
    reference_solver = solver(seed + 1000)
    reference_status = reference_solver.Solve(reference_model)
    record["reference_support_status"] = reference_solver.StatusName(reference_status)

    alternate_model, _, _, alternate_changed, alternate_sum, _ = build_zero_model(
        baseline_assignment,
        prefix=f"e078_alternate_support_{seed}",
    )
    alternate_model.Add(alternate_sum == minimum)
    alternate_model.Add(
        cp_model.LinearExpr.Sum([alternate_changed[row] for row in CORE_ROWS]) <= 1
    )
    alternate_solver = solver(seed + 2000)
    alternate_status = alternate_solver.Solve(alternate_model)
    record["alternate_support_status"] = alternate_solver.StatusName(alternate_status)

    synthetic_model, _, _, _, synthetic_sum, synthetic_vars = build_zero_model(
        baseline_assignment,
        prefix=f"e078_alternate_synthetic_{seed}",
    )
    synthetic_model.Add(synthetic_sum == minimum)
    synthetic_model.Add(synthetic_vars[CORE_ROWS[1]] == 0)
    synthetic_solver = solver(seed + 3000)
    synthetic_status = synthetic_solver.Solve(synthetic_model)
    record["alternate_synthetic_destination_status"] = synthetic_solver.StatusName(
        synthetic_status
    )

    witness_model, witness_rows, witness_zero, witness_changed, witness_sum, witness_synthetic = (
        build_zero_model(
            baseline_assignment,
            prefix=f"e078_witness_{seed}",
        )
    )
    witness_model.Add(witness_sum == minimum)
    witness_model.Add(witness_changed[CORE_ROWS[0]] == 1)
    witness_model.Add(witness_changed[CORE_ROWS[1]] == 1)
    witness_model.Add(witness_synthetic[CORE_ROWS[1]] == 1)
    witness_solver = solver(seed + 4000)
    witness_status = witness_solver.Solve(witness_model)
    record["witness_status"] = witness_solver.StatusName(witness_status)
    if witness_status != cp_model.OPTIMAL:
        return record

    assignment = selected_assignment(
        witness_solver,
        witness_rows,
        witness_zero["x_vars"],
    )
    record["selected_changed_destinations"] = [
        destination
        for destination, variable in sorted(witness_changed.items())
        if witness_solver.Value(variable) == 1
    ]
    record["selected_synthetic_destination"] = next(
        destination
        for destination, variable in sorted(witness_synthetic.items())
        if witness_solver.Value(variable) == 1
    )
    record["selected_assignment_digest"] = e074.stable_digest(assignment)
    return record


def main() -> int:
    model, built, changed, changed_sum = build_parent_model(prefix="e078_support_parent")
    model.Add(changed_sum >= 1)
    model.Minimize(changed_sum)
    primary = solver(78001)
    primary_status = primary.Solve(model)
    if primary_status != cp_model.OPTIMAL:
        print(
            json.dumps(
                {
                    "status": primary.StatusName(primary_status),
                    "target": TARGET,
                    "enumeration_terminal": "PRIMARY_NONTERMINAL",
                },
                sort_keys=True,
            )
        )
        return 0

    distance = int(round(primary.ObjectiveValue()))
    model.Add(changed_sum == distance)
    model.ClearObjective()
    records: list[dict[str, Any]] = []
    supports: list[tuple[int, ...]] = []
    enumeration_terminal = "CAP_REACHED"
    for index in range(MAX_NEIGHBOR_SUPPORTS):
        current = solver(78100 + index)
        status = current.Solve(model)
        if status == cp_model.INFEASIBLE:
            enumeration_terminal = "EXHAUSTED"
            break
        if status != cp_model.OPTIMAL:
            enumeration_terminal = current.StatusName(status)
            break
        assignment = selected_assignment(current, actual, built["x_vars"])
        support = tuple(
            destination
            for destination in range(DESTINATION_COUNT)
            if current.Value(changed[destination]) == 1
        )
        if len(support) != distance or support in supports:
            raise RuntimeError(f"E078 support enumeration drift: {support}/{distance}")
        supports.append(support)
        transport = solve_zero_from_fixed_baseline(
            assignment,
            seed=79000 + index,
        )
        records.append(
            {
                "neighbor_index": index,
                "neighbor_changed_destinations": list(support),
                "neighbor_changed_stable_bodies": [
                    {
                        "destination_local": destination,
                        "source_instance_id": str(
                            body_by_destination[destination]["source_instance_id"]
                        ),
                        "body_digest": str(
                            body_by_destination[destination]["body_digest"]
                        ),
                    }
                    for destination in support
                ],
                "baseline_assignment_digest": e074.stable_digest(assignment),
                "transport": transport,
            }
        )
        model.Add(
            cp_model.LinearExpr.Sum([changed[destination] for destination in support])
            <= distance - 1
        )

    summary = {
        "status": "OPTIMAL" if enumeration_terminal == "EXHAUSTED" else enumeration_terminal,
        "target": TARGET,
        "reference_minimum_core_size": int(witness["minimum_changed_row_count"]),
        "nearest_baseline_distance": distance,
        "neighbor_support_count": len(supports),
        "enumeration_terminal": enumeration_terminal,
        "transport_primary_status_counts": dict(
            Counter(record["transport"]["primary_status"] for record in records)
        ),
        "transport_core_size_distribution": dict(
            Counter(
                record["transport"]["minimum_changed_row_count"]
                for record in records
                if record["transport"]["minimum_changed_row_count"] is not None
            )
        ),
        "reference_support_status_counts": dict(
            Counter(record["transport"]["reference_support_status"] for record in records)
        ),
        "alternate_support_status_counts": dict(
            Counter(record["transport"]["alternate_support_status"] for record in records)
        ),
        "alternate_synthetic_status_counts": dict(
            Counter(
                record["transport"]["alternate_synthetic_destination_status"]
                for record in records
            )
        ),
        "records": records,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
