#!/usr/bin/env python3
"""E074: minimum row-wise assignment transport core for E070 targets."""

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
    "E074_minimum_assignment_transport_core/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ATLAS_PATH = OUT / "TRANSPORT_CORE_ATLAS.json"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E061_RUNNER = (
    EXPERIMENT_ROOT / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = EXPERIMENT_ROOT / "E062_one_object_tradeoff_atlas/run_e062.py"
E063_RUNNER = (
    EXPERIMENT_ROOT / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E069_RUNNER = EXPERIMENT_ROOT / "E069_six4_near_miss_complete_face/run_e069.py"
E070_RUNNER = EXPERIMENT_ROOT / "E070_dual_filling_signature_targets/run_e070.py"

E069_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001"
)
E069_RESULT = E069_RUN / "RESULT.json"
E069_PARENT = E069_RUN / "PARENT_SOLUTION.json"
E069_FACE = E069_RUN / "FACE_CONTEXT.json"
E070_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E070_dual_filling_signature_targets/run-004"
)
E070_RESULT = E070_RUN / "RESULT.json"
E070_ATLAS = E070_RUN / "TARGET_ATLAS.json"

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e074_source_cache_v1",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "297000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E069_RUNNER: "2061d59f2f1e0bf28ad27bca1730a90323f6efca38a266675115717e8969b598",
    E070_RUNNER: "1e3e8cffd629938a5b429aea369ba686e10fef2255fb349fa9732e22730455c8",
    E069_RESULT: "cc16d6f308856201cfe06d85617290481ecde85815e5c83f1d9a4acbeb4efcaa",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E069_FACE: "c05a4e94ea370e8b674e44cd7206a9189ddd2102b824d36acd65975395c46c3e",
    E070_RESULT: "e15599c5c967cdc5ab74fb755b41d32cb476d68544a1f09b0b4c8be57a1829ed",
    E070_ATLAS: "e3fb175c713c98ff7556b91fb237336fa3f1f47255a8d8af62396b074b8474c2",
}

FILLING = "filling_capsule"
TARGET_QIAOYU_COMPONENT = 29
EXPECTED_TARGETS = (1, 4, 8, 12, 14, 22, 26, 32, 37, 38, 40, 41)
EXPECTED_FEASIBLE_TARGETS = (1, 4, 8, 12, 22, 26)
EXPECTED_INFEASIBLE_TARGETS = (14, 32, 37, 38, 40, 41)
EXPECTED_DESTINATION_COUNT = 38
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded(value))
        handle.flush()
        os.fsync(handle.fileno())


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
        raise RuntimeError(f"run E074 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E074 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"E074 requires a clean tracked worktree: {tracked_status}")
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
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift: {path}: {actual} != {expected}")

    e069 = load_json(E069_RESULT)
    if (
        e069.get("verdict") != "SIX4_PARENT_COMPLETE_FACE_BROAD"
        or tuple(e069["face"]["unmatched_components"]) != EXPECTED_TARGETS
        or tuple(e069["face"]["qiaoyu_sink_components"])
        != (TARGET_QIAOYU_COMPONENT,)
    ):
        raise RuntimeError("E074 E069 face drift")
    e070 = load_json(E070_RESULT)
    feasible = tuple(int(value) for value in e070["feasible_target_components"])
    if (
        e070.get("verdict") != "DUAL_FILLING_SIGNATURE_TARGETS_SUFFICIENT"
        or feasible != EXPECTED_FEASIBLE_TARGETS
        or int(e070.get("nonterminal_count", -1)) != 0
        or int(e070["existing_signature_audit"]["exact_dual_target_count"]) != 0
    ):
        raise RuntimeError(f"E074 E070 result drift: {e070}")
    statuses = {
        int(row["target_component"]): str(row["status"])
        for row in e070["target_results"]
    }
    expected_statuses = {
        target: ("OPTIMAL" if target in EXPECTED_FEASIBLE_TARGETS else "INFEASIBLE")
        for target in EXPECTED_TARGETS
    }
    if statuses != expected_statuses:
        raise RuntimeError(f"E074 E070 target-status drift: {statuses}")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def add_exact_or(
    model: cp_model.CpModel,
    *,
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


def normalize_actual_options(
    options: Mapping[int, Sequence[tuple[Any, ...]]],
) -> dict[int, list[dict[str, Any]]]:
    output: dict[int, list[dict[str, Any]]] = {}
    for destination, rows in sorted(options.items()):
        normalized: list[dict[str, Any]] = []
        for option_index, (operation, pose_idx, signature) in enumerate(rows):
            normalized.append(
                {
                    "operation": str(operation),
                    "pose_idx": int(pose_idx),
                    "signature": tuple(
                        tuple(int(value) for value in part) for part in signature
                    ),
                    "synthetic": False,
                    "native_option_index": int(option_index),
                }
            )
        if not normalized:
            raise RuntimeError(f"E074 destination {destination} has no native options")
        output[int(destination)] = normalized
    if sorted(output) != list(range(EXPECTED_DESTINATION_COUNT)):
        raise RuntimeError(f"E074 destination identity drift: {sorted(output)}")
    return output


def tagged_zero_options(
    actual: Mapping[int, Sequence[Mapping[str, Any]]],
    *,
    target_component: int,
) -> dict[int, list[dict[str, Any]]]:
    synthetic_pose = -740000 - int(target_component)
    output: dict[int, list[dict[str, Any]]] = {}
    for destination, rows in actual.items():
        values = [dict(row) for row in rows]
        values.append(
            {
                "operation": FILLING,
                "pose_idx": synthetic_pose,
                "signature": (
                    (int(target_component),),
                    (),
                    (TARGET_QIAOYU_COMPONENT,),
                ),
                "synthetic": True,
                "native_option_index": None,
            }
        )
        output[int(destination)] = values
    return output


def add_assignment_copy(
    *,
    model: cp_model.CpModel,
    prefix: str,
    rows_by_destination: Mapping[int, Sequence[Mapping[str, Any]]],
    operation_counts: Mapping[str, int],
    sink_components: Sequence[int],
) -> dict[str, Any]:
    x_vars: dict[tuple[int, int], Any] = {}
    for destination, rows in rows_by_destination.items():
        variables: list[Any] = []
        for option_index, _option in enumerate(rows):
            variable = model.NewBoolVar(f"{prefix}_x_{destination}_{option_index}")
            x_vars[(destination, option_index)] = variable
            variables.append(variable)
        model.AddExactlyOne(variables)
    for operation, expected in operation_counts.items():
        model.Add(
            cp_model.LinearExpr.Sum(
                [
                    x_vars[(destination, option_index)]
                    for destination, rows in rows_by_destination.items()
                    for option_index, option in enumerate(rows)
                    if str(option["operation"]) == str(operation)
                ]
            )
            == int(expected)
        )

    components = sorted(
        {
            int(component)
            for rows in rows_by_destination.values()
            for option in rows
            for part in option["signature"]
            for component in part
        }
        | {int(value) for value in sink_components}
    )
    fine_sources: dict[int, Any] = {}
    fine_sinks: dict[int, Any] = {}
    qiaoyu_sources: dict[int, Any] = {}
    for component in components:
        fine_sources[component] = add_exact_or(
            model,
            name=f"{prefix}_fine_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in rows_by_destination.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][1])
            ],
        )
        fine_sinks[component] = add_exact_or(
            model,
            name=f"{prefix}_fine_sink_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in rows_by_destination.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][0])
            ],
        )
        qiaoyu_sources[component] = add_exact_or(
            model,
            name=f"{prefix}_qiaoyu_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in rows_by_destination.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][2])
            ],
        )
    qiaoyu_sink_vars = {
        int(component): model.NewBoolVar(f"{prefix}_qiaoyu_sink_{component}")
        for component in sorted(set(int(value) for value in sink_components))
    }
    model.AddExactlyOne(list(qiaoyu_sink_vars.values()))
    for component in components:
        model.Add(
            qiaoyu_sources[component]
            == qiaoyu_sink_vars.get(component, 0)
        )
    if TARGET_QIAOYU_COMPONENT not in qiaoyu_sink_vars:
        raise RuntimeError("E074 qiaoyu sink component 29 is absent")
    model.Add(qiaoyu_sink_vars[TARGET_QIAOYU_COMPONENT] == 1)
    model.Add(cp_model.LinearExpr.Sum(list(fine_sources.values())) >= 1)
    model.Add(cp_model.LinearExpr.Sum(list(fine_sinks.values())) >= 1)
    return {
        "x_vars": x_vars,
        "components": components,
        "fine_sources": fine_sources,
        "fine_sinks": fine_sinks,
        "qiaoyu_sources": qiaoyu_sources,
        "qiaoyu_sink_vars": qiaoyu_sink_vars,
    }


def configure_solver(*, seed: int) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_SECONDS
    solver.parameters.num_search_workers = SOLVE_WORKERS
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(seed)
    return solver


def option_payload(option: Mapping[str, Any], *, option_index: int) -> dict[str, Any]:
    return {
        "option_index": int(option_index),
        "native_option_index": option.get("native_option_index"),
        "operation": str(option["operation"]),
        "pose_idx": int(option["pose_idx"]),
        "signature": [list(part) for part in option["signature"]],
        "synthetic": bool(option["synthetic"]),
        "option_digest": stable_digest(
            {
                "operation": str(option["operation"]),
                "pose_idx": int(option["pose_idx"]),
                "signature": option["signature"],
                "synthetic": bool(option["synthetic"]),
            }
        ),
    }


def selected_assignment(
    *,
    solver: cp_model.CpSolver,
    rows_by_destination: Mapping[int, Sequence[Mapping[str, Any]]],
    x_vars: Mapping[tuple[int, int], Any],
    bodies: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for destination, rows in sorted(rows_by_destination.items()):
        selected = [
            option_index
            for option_index, _option in enumerate(rows)
            if solver.Value(x_vars[(destination, option_index)]) == 1
        ]
        if len(selected) != 1:
            raise RuntimeError(
                f"E074 selected-option count drift at destination {destination}: {selected}"
            )
        body = bodies[destination]
        option_index = selected[0]
        output.append(
            {
                "destination": int(destination),
                "body": {
                    "body_digest": str(body["body_digest"]),
                    "source_instance_id": str(body["source_instance_id"]),
                    "current_pose_idx": int(body["current_pose_idx"]),
                    "current_operation": str(body["current_operation"]),
                    "occupied_cells": [list(cell) for cell in body["occupied_cells"]],
                },
                "selected_option": option_payload(
                    rows[option_index],
                    option_index=option_index,
                ),
            }
        )
    return output


def solve_target_transport(
    *,
    e061: Any,
    context: Mapping[str, Any],
    bodies: Sequence[Mapping[str, Any]],
    actual: Mapping[int, Sequence[Mapping[str, Any]]],
    target_component: int,
) -> dict[str, Any]:
    zero_rows = tagged_zero_options(actual, target_component=target_component)
    model = cp_model.CpModel()
    baseline = add_assignment_copy(
        model=model,
        prefix=f"e074_b_{target_component}",
        rows_by_destination=actual,
        operation_counts=e061.OPERATION_COUNTS,
        sink_components=context["sink_space"]["components"],
    )
    zero = add_assignment_copy(
        model=model,
        prefix=f"e074_z_{target_component}",
        rows_by_destination=zero_rows,
        operation_counts=e061.OPERATION_COUNTS,
        sink_components=context["sink_space"]["components"],
    )

    all_components = sorted(
        set(baseline["components"]) | set(zero["components"])
    )
    for component in all_components:
        b_source = baseline["fine_sources"].get(component)
        b_sink = baseline["fine_sinks"].get(component)
        z_source = zero["fine_sources"].get(component)
        z_sink = zero["fine_sinks"].get(component)
        if b_source is None or b_sink is None or z_source is None or z_sink is None:
            raise RuntimeError(f"E074 component-domain mismatch: {component}")
        if component == int(target_component):
            model.Add(b_source == 1)
            model.Add(b_sink == 0)
        else:
            model.Add(b_source == b_sink)
        model.Add(z_source == z_sink)

    synthetic_vars = [
        zero["x_vars"][(destination, option_index)]
        for destination, rows in zero_rows.items()
        for option_index, option in enumerate(rows)
        if bool(option["synthetic"])
    ]
    model.Add(cp_model.LinearExpr.Sum(synthetic_vars) == 1)

    changed_vars: dict[int, Any] = {}
    same_vars_by_destination: dict[int, list[Any]] = {}
    for destination, rows in actual.items():
        same_vars: list[Any] = []
        for option_index, _option in enumerate(rows):
            same = model.NewBoolVar(
                f"e074_same_{target_component}_{destination}_{option_index}"
            )
            b_var = baseline["x_vars"][(destination, option_index)]
            z_var = zero["x_vars"][(destination, option_index)]
            model.Add(same <= b_var)
            model.Add(same <= z_var)
            model.Add(same >= b_var + z_var - 1)
            same_vars.append(same)
        changed = model.NewBoolVar(f"e074_changed_{target_component}_{destination}")
        model.Add(changed + cp_model.LinearExpr.Sum(same_vars) == 1)
        changed_vars[destination] = changed
        same_vars_by_destination[destination] = same_vars

    changed_sum = cp_model.LinearExpr.Sum(list(changed_vars.values()))
    model.Minimize(changed_sum)
    primary_solver = configure_solver(seed=74000 + int(target_component))
    started = time.monotonic()
    primary_status = primary_solver.Solve(model)
    primary_elapsed = time.monotonic() - started
    primary_name = primary_solver.StatusName(primary_status)
    result: dict[str, Any] = {
        "target_component": int(target_component),
        "primary_status": primary_name,
        "primary_best_bound": float(primary_solver.BestObjectiveBound()),
        "primary_elapsed_seconds": primary_elapsed,
        "primary_wall_time": float(primary_solver.WallTime()),
        "primary_branches": int(primary_solver.NumBranches()),
        "primary_conflicts": int(primary_solver.NumConflicts()),
        "minimum_changed_row_count": None,
        "secondary_status": None,
        "secondary_elapsed_seconds": None,
        "changed_rows": [],
        "synthetic_destination": None,
        "operation_transition_counts": [],
        "materialized_witness": None,
    }
    if primary_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result
    if primary_status != cp_model.OPTIMAL:
        return result

    minimum = int(round(primary_solver.ObjectiveValue()))
    model.Add(changed_sum == minimum)
    secondary_terms: list[Any] = []
    for destination, rows in zero_rows.items():
        for option_index, option in enumerate(rows):
            variable = zero["x_vars"][(destination, option_index)]
            if bool(option["synthetic"]):
                secondary_terms.append((destination + 1) * 1_000_000 * variable)
            secondary_terms.append((option_index + 1) * variable)
    for destination, rows in actual.items():
        for option_index, _option in enumerate(rows):
            secondary_terms.append(
                (option_index + 1)
                * baseline["x_vars"][(destination, option_index)]
            )
    model.Minimize(cp_model.LinearExpr.Sum(secondary_terms))
    secondary_solver = configure_solver(seed=75000 + int(target_component))
    secondary_started = time.monotonic()
    secondary_status = secondary_solver.Solve(model)
    secondary_elapsed = time.monotonic() - secondary_started
    secondary_name = secondary_solver.StatusName(secondary_status)
    result.update(
        {
            "minimum_changed_row_count": minimum,
            "secondary_status": secondary_name,
            "secondary_elapsed_seconds": secondary_elapsed,
            "secondary_wall_time": float(secondary_solver.WallTime()),
            "secondary_branches": int(secondary_solver.NumBranches()),
            "secondary_conflicts": int(secondary_solver.NumConflicts()),
        }
    )
    if secondary_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result

    baseline_assignment = selected_assignment(
        solver=secondary_solver,
        rows_by_destination=actual,
        x_vars=baseline["x_vars"],
        bodies=bodies,
    )
    zero_assignment = selected_assignment(
        solver=secondary_solver,
        rows_by_destination=zero_rows,
        x_vars=zero["x_vars"],
        bodies=bodies,
    )
    changed_rows: list[dict[str, Any]] = []
    transitions: Counter[tuple[str, str]] = Counter()
    synthetic_rows: list[dict[str, Any]] = []
    for baseline_row, zero_row in zip(baseline_assignment, zero_assignment, strict=True):
        if int(baseline_row["destination"]) != int(zero_row["destination"]):
            raise RuntimeError("E074 assignment destination alignment drift")
        b_option = baseline_row["selected_option"]
        z_option = zero_row["selected_option"]
        if b_option["option_digest"] == z_option["option_digest"]:
            continue
        transition = (str(b_option["operation"]), str(z_option["operation"]))
        transitions[transition] += 1
        row = {
            "destination": int(baseline_row["destination"]),
            "body": baseline_row["body"],
            "baseline_option": b_option,
            "zero_option": z_option,
            "operation_changed": transition[0] != transition[1],
            "mode_or_signature_changed": (
                int(b_option["pose_idx"]) != int(z_option["pose_idx"])
                or b_option["signature"] != z_option["signature"]
            ),
        }
        changed_rows.append(row)
        if bool(z_option["synthetic"]):
            synthetic_rows.append(row)
    if len(changed_rows) != minimum:
        raise RuntimeError(
            f"E074 changed-row count drift: {len(changed_rows)} != {minimum}"
        )
    if len(synthetic_rows) != 1:
        raise RuntimeError(f"E074 synthetic-row count drift: {len(synthetic_rows)}")

    witness_path = OUT / f"TARGET_{int(target_component):03d}_TRANSPORT.json"
    witness_payload = {
        "schema": "zmd_zero_condition_e074_target_transport_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "target_component": int(target_component),
        "minimum_changed_row_count": minimum,
        "baseline_assignment": baseline_assignment,
        "zero_assignment": zero_assignment,
        "changed_rows": changed_rows,
        "synthetic_destination": {
            "destination": int(synthetic_rows[0]["destination"]),
            "body": synthetic_rows[0]["body"],
            "zero_option": synthetic_rows[0]["zero_option"],
        },
        "operation_transition_counts": [
            {
                "baseline_operation": key[0],
                "zero_operation": key[1],
                "count": int(count),
            }
            for key, count in sorted(transitions.items())
        ],
        "ledger_effect": "none",
    }
    dump_exclusive(witness_path, witness_payload)
    result.update(
        {
            "changed_rows": changed_rows,
            "changed_body_digests": sorted(
                str(row["body"]["body_digest"]) for row in changed_rows
            ),
            "synthetic_destination": witness_payload["synthetic_destination"],
            "operation_transition_counts": witness_payload[
                "operation_transition_counts"
            ],
            "materialized_witness": {
                "path": str(witness_path.relative_to(ROOT)),
                "sha256": sha256_file(witness_path),
            },
        }
    )
    return result


def run() -> dict[str, Any]:
    identity = verify_identity()
    e061 = import_module("zmd_e074_e061", E061_RUNNER)
    e062 = import_module("zmd_e074_e062", E062_RUNNER)
    e063 = import_module("zmd_e074_e063", E063_RUNNER)
    e069 = import_module("zmd_e074_e069", E069_RUNNER)
    e070 = import_module("zmd_e074_e070", E070_RUNNER)
    direct_origins = [
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
        audit_module(e063, E063_RUNNER),
        audit_module(e069, E069_RUNNER),
        audit_module(e070, E070_RUNNER),
    ]
    context = e069.reconstruct_parent(e061, e062, e063)
    nested_origins = audit_nested_modules(
        (
            "zmd_e074_",
            "zmd_e061_",
            "zmd_e062_",
            "zmd_e063_",
            "zmd_e069_",
            "zmd_e070_",
        )
    )
    summary = e069.face_summary(context["face"])
    if tuple(summary["unmatched_components"]) != EXPECTED_TARGETS:
        raise RuntimeError("E074 reconstructed E069 face drift")
    actual = normalize_actual_options(context["options"])
    bodies = e061.body_rows(
        context["solution"],
        context["base"]["inputs"]["pools"],
        context["base"]["e014"],
    )
    if len(bodies) != EXPECTED_DESTINATION_COUNT:
        raise RuntimeError(f"E074 body count drift: {len(bodies)}")

    target_records: list[dict[str, Any]] = []
    for index, target in enumerate(EXPECTED_TARGETS, 1):
        record = solve_target_transport(
            e061=e061,
            context=context,
            bodies=bodies,
            actual=actual,
            target_component=target,
        )
        target_records.append(record)
        print(
            json.dumps(
                {
                    "event": "E074_TARGET",
                    "target_index": index,
                    "target_count": len(EXPECTED_TARGETS),
                    "target_component": target,
                    "primary_status": record["primary_status"],
                    "minimum_changed_row_count": record[
                        "minimum_changed_row_count"
                    ],
                    "secondary_status": record["secondary_status"],
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    observed_feasible = tuple(
        int(row["target_component"])
        for row in target_records
        if row["primary_status"] in {"OPTIMAL", "FEASIBLE"}
    )
    observed_infeasible = tuple(
        int(row["target_component"])
        for row in target_records
        if row["primary_status"] == "INFEASIBLE"
    )
    nonterminal = [
        row
        for row in target_records
        if row["primary_status"] not in {"OPTIMAL", "INFEASIBLE"}
        or (
            row["primary_status"] == "OPTIMAL"
            and row["secondary_status"] != "OPTIMAL"
        )
    ]
    if observed_feasible != EXPECTED_FEASIBLE_TARGETS:
        raise RuntimeError(
            f"E074 feasible-target disagreement: {observed_feasible}"
        )
    if observed_infeasible != EXPECTED_INFEASIBLE_TARGETS:
        raise RuntimeError(
            f"E074 infeasible-target disagreement: {observed_infeasible}"
        )

    feasible_records = [
        row for row in target_records if row["primary_status"] == "OPTIMAL"
    ]
    core_sizes = [int(row["minimum_changed_row_count"]) for row in feasible_records]
    core_size_distribution = Counter(core_sizes)
    changed_sets = [set(row["changed_body_digests"]) for row in feasible_records]
    shared_changed = sorted(set.intersection(*changed_sets)) if changed_sets else []
    union_changed = sorted(set.union(*changed_sets)) if changed_sets else []
    atlas = {
        "schema": "zmd_zero_condition_e074_assignment_transport_core_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "parent_face_digest": str(summary["face_digest"]),
        "expected_feasible_targets": list(EXPECTED_FEASIBLE_TARGETS),
        "target_records": target_records,
        "core_size_distribution": {
            str(size): int(count) for size, count in sorted(core_size_distribution.items())
        },
        "shared_changed_body_digests": shared_changed,
        "union_changed_body_digests": union_changed,
        "ledger_effect": "none",
    }
    dump_exclusive(ATLAS_PATH, atlas)

    if nonterminal:
        verdict = "ASSIGNMENT_TRANSPORT_CORE_NONTERMINAL"
        decision = "CONTINUE_ONLY_NONTERMINAL_TARGETS"
    elif core_sizes and min(core_sizes) == 1:
        verdict = "SINGLE_ROW_ASSIGNMENT_TRANSPORT_FOUND"
        decision = "SYNTHESIZE_ONE_STABLE_BODY_MODE"
    elif core_sizes and max(core_sizes) <= 3:
        verdict = "SMALL_ASSIGNMENT_TRANSPORT_CORES_FOUND"
        decision = "BUILD_BOUNDED_STABLE_BODY_JOINT_CONSUMER"
    else:
        verdict = "ASSIGNMENT_TRANSPORT_CORES_ARE_NOT_SMALL"
        decision = "RETIRE_ASSIGNMENT_CORE_SHORTCUT"
    return {
        "schema": "zmd_zero_condition_e074_assignment_transport_core_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "module_origin_audit": {
            "direct": direct_origins,
            "nested": nested_origins,
        },
        "parent_face": summary,
        "target_count": len(target_records),
        "observed_feasible_targets": list(observed_feasible),
        "observed_infeasible_targets": list(observed_infeasible),
        "nonterminal_count": len(nonterminal),
        "core_size_distribution": atlas["core_size_distribution"],
        "minimum_core_size": min(core_sizes) if core_sizes else None,
        "maximum_core_size": max(core_sizes) if core_sizes else None,
        "shared_changed_body_digests": shared_changed,
        "union_changed_body_count": len(union_changed),
        "target_records": target_records,
        "atlas_path": str(ATLAS_PATH.relative_to(ROOT)),
        "atlas_sha256": sha256_file(ATLAS_PATH),
        "decision": decision,
        "truth_boundary": (
            "Paired baseline/zero operation-assignment models on E069 fixed occupied "
            "geometry and native terminal-signature domains, with one hypothetical "
            "dual filling option and row-wise Hamming minimization only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E074 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "feasible_targets": result["observed_feasible_targets"],
                    "core_sizes": result["core_size_distribution"],
                    "minimum_core_size": result["minimum_core_size"],
                    "maximum_core_size": result["maximum_core_size"],
                    "shared_changed_bodies": len(
                        result["shared_changed_body_digests"]
                    ),
                    "nonterminal": result["nonterminal_count"],
                    "decision": result["decision"],
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e074_assignment_transport_core_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
