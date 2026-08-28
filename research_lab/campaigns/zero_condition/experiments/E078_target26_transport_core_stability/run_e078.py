#!/usr/bin/env python3
"""E078: fixed-face stability of E074's target-26 semantic transport core."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E078_target26_transport_core_stability/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ATLAS_PATH = OUT / "ONE_OPTION_NEIGHBOR_ATLAS.json"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E074_RUNNER = (
    EXPERIMENT_ROOT
    / "E074_minimum_assignment_transport_core/run_e074.py"
)
E074_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E074_minimum_assignment_transport_core/run-001"
)
E074_RESULT = E074_RUN / "RESULT.json"
E074_TARGET = E074_RUN / "TARGET_026_TRANSPORT.json"

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e078_source_cache_v1",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "297000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E074_RUNNER: "74e2720cf4b7aaa56fb004864f54c99710b004ae15bb77c5582a205558c67b25",
    E074_RESULT: "e3e59cc773b88f033d754a97ec16e28e9e18980c9f02b55ab8980851b95fa7c9",
    E074_TARGET: "609e0be6613f27531e9a24bc757b3dbeb7574d6422e9eb55615cf117d74658f4",
}

TARGET_COMPONENT = 26
TARGET_QIAOYU_COMPONENT = 29
CORE_ROWS = (8, 9)
EXPECTED_RAW_ONE_OPTION_ALTERNATIVES = 168
EXPECTED_VALID_ONE_OPTION_NEIGHBORS = 25
SOLVE_SECONDS = 45.0
SOLVE_WORKERS = 8


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            default=str,
        )
    )


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def encoded(value: Any) -> bytes:
    return (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def dump_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded(value))
        handle.flush()
        os.fsync(handle.fileno())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


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
    functions: list[dict[str, str]] = []
    foreign: list[dict[str, str]] = []
    for name, value in sorted(vars(module).items()):
        if not inspect.isfunction(value) or value.__module__ != module.__name__:
            continue
        actual = Path(value.__code__.co_filename).resolve()
        record = {"name": str(name), "code_filename": str(actual)}
        functions.append(record)
        if actual != expected:
            foreign.append(record)
    if foreign:
        raise RuntimeError(f"foreign functions loaded for {expected_path}: {foreign[:10]}")
    return {
        "module": str(module.__name__),
        "source": str(expected_path.relative_to(ROOT)),
        "source_sha256": sha256_file(expected_path),
        "function_count": len(functions),
        "foreign_function_count": 0,
    }


def audit_nested_modules(prefixes: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, module in sorted(sys.modules.items()):
        if module is None or not any(name.startswith(prefix) for prefix in prefixes):
            continue
        file_value = getattr(module, "__file__", None)
        if not isinstance(file_value, str):
            continue
        path = Path(file_value).resolve()
        source = (
            Path(importlib.util.source_from_cache(str(path))).resolve()
            if path.suffix == ".pyc"
            else path
        )
        rows.append(audit_module(module, source))
    return rows


def verify_identity() -> dict[str, Any]:
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError(f"run E078 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E078 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"E078 requires a clean tracked worktree: {tracked_status}")
    mismatches = {
        key: {"expected": expected, "actual": os.environ.get(key)}
        for key, expected in EXPECTED_ENV.items()
        if os.environ.get(key) != expected
    }
    unexpected_exact = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected_exact:
        raise RuntimeError(
            f"environment mismatch: {mismatches}; unexpected={unexpected_exact}"
        )
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path.relative_to(ROOT))] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift: {path}: {actual} != {expected}")
    result = load_json(E074_RESULT)
    target = load_json(E074_TARGET)
    target_record = next(
        row
        for row in result["target_records"]
        if int(row["target_component"]) == TARGET_COMPONENT
    )
    if (
        result.get("verdict") != "SMALL_ASSIGNMENT_TRANSPORT_CORES_FOUND"
        or int(target_record["minimum_changed_row_count"]) != 2
        or int(target["minimum_changed_row_count"]) != 2
        or tuple(int(value) for value in target["changed_destinations"])
        != CORE_ROWS
    ):
        raise RuntimeError("E078 E074 target-26 witness drift")
    return {
        "checked_sha256": checked,
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
    }


def configure_solver(*, seed: int, seconds: float = SOLVE_SECONDS) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = SOLVE_WORKERS
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(seed)
    return solver


def add_parent_face_constraints(
    *,
    model: cp_model.CpModel,
    built: Mapping[str, Any],
) -> None:
    for component in built["components"]:
        source = built["fine_sources"][component]
        sink = built["fine_sinks"][component]
        if int(component) == TARGET_COMPONENT:
            model.Add(source == 1)
            model.Add(sink == 0)
        else:
            model.Add(source == sink)


def build_parent_model(
    *,
    e074: Any,
    e061: Any,
    context: Mapping[str, Any],
    actual: Mapping[int, Sequence[Mapping[str, Any]]],
    prefix: str,
) -> tuple[cp_model.CpModel, dict[str, Any]]:
    model = cp_model.CpModel()
    built = e074.add_assignment_copy(
        model=model,
        prefix=prefix,
        rows_by_destination=actual,
        operation_counts=e061.OPERATION_COUNTS,
        sink_components=context["sink_space"]["components"],
    )
    add_parent_face_constraints(model=model, built=built)
    return model, built


def selected_assignment(
    *,
    e074: Any,
    solver: cp_model.CpSolver,
    rows: Mapping[int, Sequence[Mapping[str, Any]]],
    built: Mapping[str, Any],
    bodies: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return e074.selected_assignment(
        solver=solver,
        rows_by_destination=rows,
        x_vars=built["x_vars"],
        bodies=bodies,
    )


def build_zero_model(
    *,
    e074: Any,
    e061: Any,
    context: Mapping[str, Any],
    actual: Mapping[int, Sequence[Mapping[str, Any]]],
    baseline_assignment: Sequence[Mapping[str, Any]],
    prefix: str,
) -> tuple[
    cp_model.CpModel,
    dict[str, Any],
    dict[int, Any],
    Any,
    dict[int, Any],
]:
    zero_rows = e074.tagged_zero_options(
        actual,
        target_component=TARGET_COMPONENT,
    )
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
        synthetic = [
            zero["x_vars"][(destination, option_index)]
            for option_index, option in enumerate(rows)
            if bool(option["synthetic"])
        ]
        if len(synthetic) != 1:
            raise RuntimeError(f"E078 synthetic-option count drift: {destination}")
        synthetic_by_destination[int(destination)] = synthetic[0]
    model.Add(
        cp_model.LinearExpr.Sum(list(synthetic_by_destination.values())) == 1
    )
    changed: dict[int, Any] = {}
    for row in baseline_assignment:
        destination = int(row["destination"])
        native_index = row["selected_option"].get("native_option_index")
        if native_index is None:
            raise RuntimeError("E078 baseline contains a synthetic option")
        variable = model.NewBoolVar(f"{prefix}_changed_{destination}")
        model.Add(
            variable
            + zero["x_vars"][(destination, int(native_index))]
            == 1
        )
        changed[destination] = variable
    changed_sum = cp_model.LinearExpr.Sum(list(changed.values()))
    return model, zero, changed, changed_sum, synthetic_by_destination


def minimum_zero_transport(
    *,
    e074: Any,
    e061: Any,
    context: Mapping[str, Any],
    actual: Mapping[int, Sequence[Mapping[str, Any]]],
    bodies: Sequence[Mapping[str, Any]],
    baseline_assignment: Sequence[Mapping[str, Any]],
    seed: int,
) -> dict[str, Any]:
    model, zero, changed, changed_sum, synthetic = build_zero_model(
        e074=e074,
        e061=e061,
        context=context,
        actual=actual,
        baseline_assignment=baseline_assignment,
        prefix=f"e078_zero_{seed}",
    )
    model.Minimize(changed_sum)
    primary = configure_solver(seed=seed)
    started = time.monotonic()
    primary_status = primary.Solve(model)
    elapsed = time.monotonic() - started
    record: dict[str, Any] = {
        "primary_status": primary.StatusName(primary_status),
        "primary_best_bound": float(primary.BestObjectiveBound()),
        "primary_elapsed_seconds": elapsed,
        "minimum_changed_row_count": None,
        "alternate_optimum_support_status": None,
        "alternate_synthetic_destination_status": None,
        "selected_changed_destinations": [],
    }
    if primary_status != cp_model.OPTIMAL:
        return record
    minimum = int(round(primary.ObjectiveValue()))
    record["minimum_changed_row_count"] = minimum

    support_model, _support_zero, support_changed, support_sum, _support_synthetic = (
        build_zero_model(
            e074=e074,
            e061=e061,
            context=context,
            actual=actual,
            baseline_assignment=baseline_assignment,
            prefix=f"e078_support_{seed}",
        )
    )
    support_model.Add(support_sum == minimum)
    support_model.Add(
        cp_model.LinearExpr.Sum([support_changed[row] for row in CORE_ROWS]) <= 1
    )
    support_solver = configure_solver(seed=seed + 1000)
    support_status = support_solver.Solve(support_model)
    record["alternate_optimum_support_status"] = support_solver.StatusName(
        support_status
    )

    synthetic_model, _synthetic_zero, _synthetic_changed, synthetic_sum, synthetic_vars = (
        build_zero_model(
            e074=e074,
            e061=e061,
            context=context,
            actual=actual,
            baseline_assignment=baseline_assignment,
            prefix=f"e078_synthetic_{seed}",
        )
    )
    synthetic_model.Add(synthetic_sum == minimum)
    synthetic_model.Add(synthetic_vars[CORE_ROWS[1]] == 0)
    synthetic_solver = configure_solver(seed=seed + 2000)
    synthetic_status = synthetic_solver.Solve(synthetic_model)
    record["alternate_synthetic_destination_status"] = (
        synthetic_solver.StatusName(synthetic_status)
    )

    witness_model, witness_zero, witness_changed, witness_sum, witness_synthetic = (
        build_zero_model(
            e074=e074,
            e061=e061,
            context=context,
            actual=actual,
            baseline_assignment=baseline_assignment,
            prefix=f"e078_witness_{seed}",
        )
    )
    witness_model.Add(witness_sum == minimum)
    witness_model.Add(witness_changed[CORE_ROWS[0]] == 1)
    witness_model.Add(witness_changed[CORE_ROWS[1]] == 1)
    witness_model.Add(witness_synthetic[CORE_ROWS[1]] == 1)
    witness_solver = configure_solver(seed=seed + 3000)
    witness_status = witness_solver.Solve(witness_model)
    record["witness_status"] = witness_solver.StatusName(witness_status)
    if witness_status != cp_model.OPTIMAL:
        return record
    assignment = selected_assignment(
        e074=e074,
        solver=witness_solver,
        rows=e074.tagged_zero_options(actual, target_component=TARGET_COMPONENT),
        built=witness_zero,
        bodies=bodies,
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
    record["selected_assignment_digest"] = stable_digest(assignment)
    return record


def paired_global_minimum(
    *,
    e074: Any,
    e061: Any,
    context: Mapping[str, Any],
    actual: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    zero_rows = e074.tagged_zero_options(actual, target_component=TARGET_COMPONENT)
    model = cp_model.CpModel()
    baseline = e074.add_assignment_copy(
        model=model,
        prefix="e078_global_baseline",
        rows_by_destination=actual,
        operation_counts=e061.OPERATION_COUNTS,
        sink_components=context["sink_space"]["components"],
    )
    zero = e074.add_assignment_copy(
        model=model,
        prefix="e078_global_zero",
        rows_by_destination=zero_rows,
        operation_counts=e061.OPERATION_COUNTS,
        sink_components=context["sink_space"]["components"],
    )
    add_parent_face_constraints(model=model, built=baseline)
    for component in zero["components"]:
        model.Add(zero["fine_sources"][component] == zero["fine_sinks"][component])
    synthetic_vars = [
        zero["x_vars"][(destination, option_index)]
        for destination, rows in zero_rows.items()
        for option_index, option in enumerate(rows)
        if bool(option["synthetic"])
    ]
    model.Add(cp_model.LinearExpr.Sum(synthetic_vars) == 1)
    changed: dict[int, Any] = {}
    for destination in range(38):
        variable = model.NewBoolVar(f"e078_global_changed_{destination}")
        changed[destination] = variable
        same_terms: list[Any] = []
        for baseline_index, baseline_option in enumerate(actual[destination]):
            baseline_var = baseline["x_vars"][(destination, baseline_index)]
            for zero_index, zero_option in enumerate(zero_rows[destination]):
                if bool(zero_option["synthetic"]):
                    continue
                if (
                    str(baseline_option["operation"])
                    == str(zero_option["operation"])
                    and int(baseline_option["pose_idx"])
                    == int(zero_option["pose_idx"])
                    and tuple(baseline_option["signature"])
                    == tuple(zero_option["signature"])
                ):
                    pair = model.NewBoolVar(
                        f"e078_global_same_{destination}_{baseline_index}_{zero_index}"
                    )
                    model.Add(pair <= baseline_var)
                    model.Add(pair <= zero["x_vars"][(destination, zero_index)])
                    model.Add(
                        pair
                        >= baseline_var
                        + zero["x_vars"][(destination, zero_index)]
                        - 1
                    )
                    same_terms.append(pair)
        model.Add(variable + cp_model.LinearExpr.Sum(same_terms) == 1)
    changed_sum = cp_model.LinearExpr.Sum(list(changed.values()))
    model.Minimize(changed_sum)
    solver = configure_solver(seed=86001)
    started = time.monotonic()
    status = solver.Solve(model)
    return {
        "status": solver.StatusName(status),
        "best_bound": float(solver.BestObjectiveBound()),
        "objective": (
            int(round(solver.ObjectiveValue()))
            if status == cp_model.OPTIMAL
            else None
        ),
        "elapsed_seconds": time.monotonic() - started,
    }


def core_row_invariance(
    *,
    e074: Any,
    e061: Any,
    context: Mapping[str, Any],
    actual: Mapping[int, Sequence[Mapping[str, Any]]],
    reference_index: Mapping[int, int],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for offset, row in enumerate(CORE_ROWS):
        model, built = build_parent_model(
            e074=e074,
            e061=e061,
            context=context,
            actual=actual,
            prefix=f"e078_invariance_{row}",
        )
        model.Add(built["x_vars"][(row, int(reference_index[row]))] == 0)
        solver = configure_solver(seed=87001 + offset)
        status = solver.Solve(model)
        records.append(
            {
                "destination_local": row,
                "status": solver.StatusName(status),
                "branches": int(solver.NumBranches()),
                "conflicts": int(solver.NumConflicts()),
                "wall_time": float(solver.WallTime()),
            }
        )
    return {
        "records": records,
        "all_core_rows_invariant": all(
            record["status"] == "INFEASIBLE" for record in records
        ),
    }


def exact_or(
    *,
    model: cp_model.CpModel,
    name: str,
    contributors: Sequence[Any],
) -> Any:
    variable = model.NewBoolVar(name)
    if not contributors:
        model.Add(variable == 0)
        return variable
    for contributor in contributors:
        model.Add(variable >= contributor)
    model.Add(variable <= cp_model.LinearExpr.Sum(list(contributors)))
    return variable


def xor(
    *,
    model: cp_model.CpModel,
    name: str,
    left: Any,
    right: Any,
) -> Any:
    variable = model.NewBoolVar(name)
    model.Add(variable >= left - right)
    model.Add(variable >= right - left)
    model.Add(variable <= left + right)
    model.Add(variable <= 2 - left - right)
    return variable


def universal_rewrite_counterexample(
    *,
    e074: Any,
    e061: Any,
    context: Mapping[str, Any],
    actual: Mapping[int, Sequence[Mapping[str, Any]]],
    reference_index: Mapping[int, int],
    zero_reference: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    model, parent = build_parent_model(
        e074=e074,
        e061=e061,
        context=context,
        actual=actual,
        prefix="e078_universal_parent",
    )
    for row in CORE_ROWS:
        model.Add(parent["x_vars"][(row, int(reference_index[row]))] == 1)
    components = sorted(
        {
            int(component)
            for rows in actual.values()
            for option in rows
            for part in option["signature"]
            for component in part
        }
        | {
            int(component)
            for option in zero_reference.values()
            for part in option["signature"]
            for component in part
        }
    )
    mismatches: list[Any] = []
    qiaoyu_failures: list[Any] = []
    for component in components:
        source_terms: list[Any] = []
        sink_terms: list[Any] = []
        qiaoyu_terms: list[Any] = []
        for destination, rows in actual.items():
            if destination in CORE_ROWS:
                continue
            for option_index, option in enumerate(rows):
                variable = parent["x_vars"][(destination, option_index)]
                if component in set(option["signature"][1]):
                    source_terms.append(variable)
                if component in set(option["signature"][0]):
                    sink_terms.append(variable)
                if component in set(option["signature"][2]):
                    qiaoyu_terms.append(variable)
        for option in zero_reference.values():
            if component in set(int(value) for value in option["signature"][1]):
                source_terms.append(1)
            if component in set(int(value) for value in option["signature"][0]):
                sink_terms.append(1)
            if component in set(int(value) for value in option["signature"][2]):
                qiaoyu_terms.append(1)
        source = exact_or(
            model=model,
            name=f"e078_universal_source_{component}",
            contributors=source_terms,
        )
        sink = exact_or(
            model=model,
            name=f"e078_universal_sink_{component}",
            contributors=sink_terms,
        )
        qiaoyu = exact_or(
            model=model,
            name=f"e078_universal_qiaoyu_{component}",
            contributors=qiaoyu_terms,
        )
        mismatches.append(
            xor(
                model=model,
                name=f"e078_universal_mismatch_{component}",
                left=source,
                right=sink,
            )
        )
        failure = model.NewBoolVar(f"e078_universal_qiaoyu_failure_{component}")
        if component == TARGET_QIAOYU_COMPONENT:
            model.Add(failure + qiaoyu == 1)
        else:
            model.Add(failure == qiaoyu)
        qiaoyu_failures.append(failure)
    model.Add(cp_model.LinearExpr.Sum(mismatches + qiaoyu_failures) >= 1)
    solver = configure_solver(seed=88001)
    status = solver.Solve(model)
    return {
        "status": solver.StatusName(status),
        "counterexample_found": status in (cp_model.OPTIMAL, cp_model.FEASIBLE),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "wall_time": float(solver.WallTime()),
    }


def one_option_atlas(
    *,
    e074: Any,
    e061: Any,
    context: Mapping[str, Any],
    actual: Mapping[int, Sequence[Mapping[str, Any]]],
    bodies: Sequence[Mapping[str, Any]],
    reference_assignment: Sequence[Mapping[str, Any]],
    reference_index: Mapping[int, int],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    raw_count = 0
    for destination in range(38):
        for option_index, _option in enumerate(actual[destination]):
            if option_index == int(reference_index[destination]):
                continue
            raw_count += 1
            model, built = build_parent_model(
                e074=e074,
                e061=e061,
                context=context,
                actual=actual,
                prefix=f"e078_neighbor_{destination}_{option_index}",
            )
            for row in range(38):
                chosen = option_index if row == destination else int(reference_index[row])
                model.Add(built["x_vars"][(row, chosen)] == 1)
            solver = configure_solver(
                seed=89000 + destination * 16 + option_index,
                seconds=15.0,
            )
            status = solver.Solve(model)
            if status == cp_model.INFEASIBLE:
                continue
            if status != cp_model.OPTIMAL:
                raise RuntimeError(
                    "E078 one-option neighbor nonterminal: "
                    f"destination={destination} option={option_index} "
                    f"status={solver.StatusName(status)}"
                )
            baseline = selected_assignment(
                e074=e074,
                solver=solver,
                rows=actual,
                built=built,
                bodies=bodies,
            )
            transport = minimum_zero_transport(
                e074=e074,
                e061=e061,
                context=context,
                actual=actual,
                bodies=bodies,
                baseline_assignment=baseline,
                seed=90000 + destination * 16 + option_index,
            )
            body = baseline[destination]["body"]
            records.append(
                {
                    "changed_destination_local": destination,
                    "changed_stable_body": {
                        "source_instance_id": str(body["source_instance_id"]),
                        "body_digest": str(body["body_digest"]),
                    },
                    "reference_native_option_index": int(reference_index[destination]),
                    "neighbor_native_option_index": option_index,
                    "neighbor_option": baseline[destination]["selected_option"],
                    "baseline_assignment_digest": stable_digest(baseline),
                    "transport": transport,
                }
            )
    return {
        "raw_one_option_alternative_count": raw_count,
        "valid_one_option_neighbor_count": len(records),
        "valid_destination_support_count": len(
            {int(record["changed_destination_local"]) for record in records}
        ),
        "transport_primary_status_counts": dict(
            sorted(Counter(record["transport"]["primary_status"] for record in records).items())
        ),
        "transport_core_size_distribution": dict(
            sorted(
                Counter(
                    int(record["transport"]["minimum_changed_row_count"])
                    for record in records
                    if record["transport"]["minimum_changed_row_count"] is not None
                ).items()
            )
        ),
        "transport_support_counts": {
            ",".join(str(value) for value in support): count
            for support, count in sorted(
                Counter(
                    tuple(record["transport"]["selected_changed_destinations"])
                    for record in records
                ).items()
            )
        },
        "alternate_support_status_counts": dict(
            sorted(
                Counter(
                    record["transport"]["alternate_optimum_support_status"]
                    for record in records
                ).items()
            )
        ),
        "alternate_synthetic_status_counts": dict(
            sorted(
                Counter(
                    record["transport"]["alternate_synthetic_destination_status"]
                    for record in records
                ).items()
            )
        ),
        "records": records,
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e074 = import_module("e078_e074", E074_RUNNER)
    for path, expected in e074.EXPECTED_HASHES.items():
        actual_hash = sha256_file(path)
        if actual_hash != expected:
            raise RuntimeError(
                f"E078 inherited E074 identity drift: {path}: {actual_hash} != {expected}"
            )
    e061 = e074.import_module("e078_e061", e074.E061_RUNNER)
    e062 = e074.import_module("e078_e062", e074.E062_RUNNER)
    e063 = e074.import_module("e078_e063", e074.E063_RUNNER)
    e069 = e074.import_module("e078_e069", e074.E069_RUNNER)
    direct_audit = [
        audit_module(e074, E074_RUNNER),
        audit_module(e061, e074.E061_RUNNER),
        audit_module(e062, e074.E062_RUNNER),
        audit_module(e063, e074.E063_RUNNER),
        audit_module(e069, e074.E069_RUNNER),
    ]
    context = e069.reconstruct_parent(e061, e062, e063)
    actual = e074.normalize_actual_options(context["options"])
    bodies = e061.body_rows(
        context["solution"],
        context["base"]["inputs"]["pools"],
        context["base"]["e014"],
    )
    witness = load_json(E074_TARGET)
    reference_assignment = list(witness["baseline_assignment"])
    zero_assignment = list(witness["zero_assignment"])
    reference_by_destination = {
        int(row["destination"]): dict(row) for row in reference_assignment
    }
    zero_by_destination = {
        int(row["destination"]): dict(row) for row in zero_assignment
    }
    if sorted(reference_by_destination) != list(range(38)):
        raise RuntimeError("E078 reference destination drift")
    reference_index = {
        destination: int(row["selected_option"]["native_option_index"])
        for destination, row in reference_by_destination.items()
    }
    zero_reference = {
        row: dict(zero_by_destination[row]["selected_option"])
        for row in CORE_ROWS
    }
    body_by_destination = {
        int(destination): {
            "source_instance_id": str(body["source_instance_id"]),
            "body_digest": str(body["body_digest"]),
            "occupied_cells": [list(cell) for cell in body["occupied_cells"]],
        }
        for destination, body in enumerate(bodies)
    }
    for row in CORE_ROWS:
        if (
            body_by_destination[row]["source_instance_id"]
            != reference_by_destination[row]["body"]["source_instance_id"]
            or body_by_destination[row]["body_digest"]
            != reference_by_destination[row]["body"]["body_digest"]
        ):
            raise RuntimeError(f"E078 stable core-body remap drift at row {row}")

    calibration_model, calibration_built = build_parent_model(
        e074=e074,
        e061=e061,
        context=context,
        actual=actual,
        prefix="e078_calibration",
    )
    for row in range(38):
        calibration_model.Add(
            calibration_built["x_vars"][(row, int(reference_index[row]))] == 1
        )
    calibration_solver = configure_solver(seed=91001)
    calibration_status = calibration_solver.Solve(calibration_model)
    calibration = {
        "status": calibration_solver.StatusName(calibration_status),
        "branches": int(calibration_solver.NumBranches()),
        "conflicts": int(calibration_solver.NumConflicts()),
        "wall_time": float(calibration_solver.WallTime()),
    }
    if calibration_status != cp_model.OPTIMAL:
        raise RuntimeError(f"E078 calibration failed: {calibration}")

    global_minimum = paired_global_minimum(
        e074=e074,
        e061=e061,
        context=context,
        actual=actual,
    )
    invariance = core_row_invariance(
        e074=e074,
        e061=e061,
        context=context,
        actual=actual,
        reference_index=reference_index,
    )
    rewrite = universal_rewrite_counterexample(
        e074=e074,
        e061=e061,
        context=context,
        actual=actual,
        reference_index=reference_index,
        zero_reference=zero_reference,
    )
    atlas = one_option_atlas(
        e074=e074,
        e061=e061,
        context=context,
        actual=actual,
        bodies=bodies,
        reference_assignment=reference_assignment,
        reference_index=reference_index,
    )

    if global_minimum["status"] != "OPTIMAL" or global_minimum["objective"] != 2:
        raise RuntimeError(f"E078 global minimum drift: {global_minimum}")
    if not invariance["all_core_rows_invariant"]:
        raise RuntimeError(f"E078 core-row invariance failed: {invariance}")
    if rewrite["status"] != "INFEASIBLE" or rewrite["counterexample_found"]:
        raise RuntimeError(f"E078 universal rewrite counterexample: {rewrite}")
    if (
        atlas["raw_one_option_alternative_count"]
        != EXPECTED_RAW_ONE_OPTION_ALTERNATIVES
        or atlas["valid_one_option_neighbor_count"]
        != EXPECTED_VALID_ONE_OPTION_NEIGHBORS
        or atlas["valid_destination_support_count"]
        != EXPECTED_VALID_ONE_OPTION_NEIGHBORS
        or atlas["transport_primary_status_counts"] != {"OPTIMAL": 25}
        or atlas["transport_core_size_distribution"] != {2: 25}
        or atlas["transport_support_counts"] != {"8,9": 25}
        or atlas["alternate_support_status_counts"] != {"INFEASIBLE": 25}
        or atlas["alternate_synthetic_status_counts"] != {"INFEASIBLE": 25}
    ):
        raise RuntimeError(f"E078 one-option atlas drift: {atlas}")

    target_cells = sorted(
        [list(cell) for cell in context["routing_context"].cells_by_component[TARGET_COMPONENT]]
    )
    qiaoyu_slots = sorted(
        [
            {
                "slot_id": str(row["slot_id"]),
                "component_local": int(row["component"]),
                "x": int(row["x"]),
                "y": int(row["y"]),
            }
            for row in context["sink_space"]["slots"]
            if int(row["component"]) == TARGET_QIAOYU_COMPONENT
        ],
        key=lambda row: row["slot_id"],
    )
    if not qiaoyu_slots:
        raise RuntimeError("E078 stable qiaoyu sink witness is empty")

    atlas_payload = {
        "schema": "zmd_e078_one_option_neighbor_atlas_v1",
        "target_component_local": TARGET_COMPONENT,
        "target_free_cell_set_digest": stable_digest(target_cells),
        "target_free_cell_count": len(target_cells),
        "core_rows_local": list(CORE_ROWS),
        "core_stable_bodies": [body_by_destination[row] for row in CORE_ROWS],
        **atlas,
    }
    atlas_sha = stable_digest(atlas_payload)
    result = {
        "schema": "zmd_e078_target26_transport_core_stability_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "identity": {
            **identity,
            "runner_sha256": sha256_file(Path(__file__)),
            "inherited_e074_hashes": {
                str(path.relative_to(ROOT)): sha256_file(path)
                for path in sorted(e074.EXPECTED_HASHES, key=str)
            },
        },
        "module_origin_audit": {
            "direct": direct_audit,
            "nested": audit_nested_modules(
                (
                    "e078_",
                    "zmd_e061_",
                    "zmd_e062_",
                    "zmd_e063_",
                    "zmd_e069_",
                )
            ),
        },
        "context": {
            "geometry_scope": "fixed_E069_occupied_geometry",
            "target_component_local": TARGET_COMPONENT,
            "target_free_cells": target_cells,
            "target_free_cell_set_digest": stable_digest(target_cells),
            "qiaoyu_component_local": TARGET_QIAOYU_COMPONENT,
            "qiaoyu_sink_slot_witnesses": qiaoyu_slots,
            "core_rows_local": list(CORE_ROWS),
            "core_stable_bodies": [body_by_destination[row] for row in CORE_ROWS],
            "baseline_core_options": [
                reference_by_destination[row]["selected_option"] for row in CORE_ROWS
            ],
            "zero_core_options": [zero_reference[row] for row in CORE_ROWS],
        },
        "calibration": calibration,
        "paired_global_minimum": global_minimum,
        "core_row_invariance": invariance,
        "universal_rewrite_counterexample": rewrite,
        "one_option_atlas_path": str(ATLAS_PATH.relative_to(ROOT)),
        "one_option_atlas_digest": atlas_sha,
        "one_option_summary": {
            key: value for key, value in atlas.items() if key != "records"
        },
        "verdict": "TARGET26_SEMANTIC_CORE_STABLE_ON_FIXED_FACE",
        "decision": "TEST_STABLE_BODY_CORE_ACROSS_GEOMETRY_REMAP",
        "truth_boundary": (
            "The result is exact only on E069's fixed occupied geometry and target-26 "
            "terminal-signature abstraction. It proves a globally optimal, fixed-face "
            "two-row semantic rewrite on two stable bodies; it does not realize the "
            "synthetic filling option physically or prove binding, routing, throughput, "
            "a whole layout, certification, U/L, or cross-geometry stability."
        ),
    }
    dump_exclusive(ATLAS_PATH, atlas_payload)
    dump_exclusive(RESULT_PATH, result)
    return result


def main() -> int:
    try:
        result = run()
    except Exception as exc:
        failure = {
            "schema": "zmd_e078_target26_transport_core_stability_failure_v1",
            "created_at_utc": utc_now(),
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "runner_sha256": sha256_file(Path(__file__)),
        }
        if not RESULT_PATH.exists() and not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "decision": result["decision"],
                "paired_global_minimum": result["paired_global_minimum"],
                "core_row_invariance": result["core_row_invariance"],
                "universal_rewrite_counterexample": result[
                    "universal_rewrite_counterexample"
                ],
                "one_option_summary": result["one_option_summary"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
