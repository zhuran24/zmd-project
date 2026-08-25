#!/usr/bin/env python3
"""E006 recovery: bypass full presolve and seed permeability-derived variables.

The original E006 run spent its budget in presolve and never registered the
known-feasible hint. This research-only recovery keeps the same model and
objective, but invokes CpSolver directly with presolve disabled and hints for the
selected pose literals, front-clear variables, and all free-edge variables.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
BASE_RUNNER = HERE / "run_e006.py"
BASE_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E006_free_adjacency_master/run-001/RESULT.json"
)
OUT = ROOT / "research_lab/local/zero_condition/E006_free_adjacency_master/run-003"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ASSIGNMENT_PATH = OUT / "PERMEABILITY_ASSIGNMENT.json"
LAYOUT_PATH = OUT / "PERMEABILITY_LAYOUT.json"
LOG_PATH = OUT / "SOLVER.log"

EXPECTED_BASE_RUNNER_SHA256 = "84634cb920fe19a0d724af5e2927ede228b2383fd7c0babf10403b1324bdf20d"
EXPECTED_BASE_RESULT_SHA256 = "a84339d8ee5b768ad63e5c2eaa641aa34af17d3251108d67eff7992b7b246355"
EXPECTED_ENV: dict[str, str] = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "260826",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
}
SOLVE_CAP_SECONDS = 60.0
GRID_W = 70
GRID_H = 70


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


def dump_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def verify_environment() -> dict[str, Any]:
    actual = {key: os.environ.get(key) for key in EXPECTED_ENV}
    mismatches = {
        key: {"expected": expected, "actual": actual[key]}
        for key, expected in EXPECTED_ENV.items()
        if actual[key] != expected
    }
    unexpected = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected:
        raise RuntimeError(
            f"environment mismatch: mismatches={mismatches}, unexpected={unexpected}"
        )
    return {"actual": actual, "unexpected_exact_variables": unexpected}


def load_base_module() -> Any:
    if sha256_file(BASE_RUNNER) != EXPECTED_BASE_RUNNER_SHA256:
        raise RuntimeError("base E006 runner drifted")
    if sha256_file(BASE_RESULT) != EXPECTED_BASE_RESULT_SHA256:
        raise RuntimeError("base E006 result drifted")
    spec = importlib.util.spec_from_file_location("zmd_e006_base_runner", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load E006 base runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selected_pose_sets(
    *,
    delegate: Any,
    solution: Mapping[str, Mapping[str, Any]],
) -> tuple[set[tuple[str, int]], set[tuple[str, int]], set[int]]:
    mandatory: set[tuple[str, int]] = set()
    optional: set[tuple[str, int]] = set()
    poles: set[int] = set()
    for instance_id, row in solution.items():
        pose_idx = int(row["pose_idx"])
        if bool(row.get("is_mandatory")):
            group_id = delegate._group_id_by_instance.get(str(instance_id))
            if group_id is None:
                raise RuntimeError(f"hint mandatory has no group: {instance_id}")
            mandatory.add((str(group_id), pose_idx))
            continue
        facility_type = str(row.get("facility_type", ""))
        if facility_type == "power_pole":
            poles.add(pose_idx)
        else:
            optional.add((facility_type, pose_idx))
    return mandatory, optional, poles


def add_objective_and_hints(
    *,
    master: Any,
    hint_solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    delegate = master._coordinate_delegate
    if getattr(delegate, "master_representation", None) != "pose_bool_exact_v1":
        raise RuntimeError("recovery requires pose_bool_exact_v1")
    cell_poses = getattr(delegate, "_sac_cell_poses", None)
    if not isinstance(cell_poses, dict):
        raise RuntimeError("pose-bool cell occupancy cache missing")

    occupied = master_module.occupancy_from_solution(
        solution=hint_solution,
        pools=pools,
    )
    free = {(x, y) for x in range(GRID_W) for y in range(GRID_H)} - occupied
    mandatory, optional, poles = selected_pose_sets(
        delegate=delegate,
        solution=hint_solution,
    )

    pose_hint_count = 0
    selected_pose_hint_count = 0
    for key, variable in delegate.x_vars.items():
        value = int((str(key[0]), int(key[1])) in mandatory)
        master.model.AddHint(variable, value)
        pose_hint_count += 1
        selected_pose_hint_count += value
    for key, variable in delegate.ro_vars.items():
        value = int((str(key[0]), int(key[1])) in optional)
        master.model.AddHint(variable, value)
        pose_hint_count += 1
        selected_pose_hint_count += value
    for pose_idx, variable in delegate.pole_vars.items():
        value = int(int(pose_idx) in poles)
        master.model.AddHint(variable, value)
        pose_hint_count += 1
        selected_pose_hint_count += value

    front_hint_count = 0
    for key, variable in getattr(delegate, "_front_clear", {}).items():
        cell = (int(key[0]), int(key[1]))
        master.model.AddHint(variable, int(cell in free))
        front_hint_count += 1

    edge_vars: list[Any] = []
    edge_hint_count = 0
    edge_hint_ones = 0
    for x in range(GRID_W):
        for y in range(GRID_H):
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if nx >= GRID_W or ny >= GRID_H:
                    continue
                a_terms = list(cell_poses.get((x, y), []))
                b_terms = list(cell_poses.get((nx, ny), []))
                edge = master.model.NewBoolVar(
                    f"e006r_free_edge_{x}_{y}_{nx}_{ny}"
                )
                if a_terms:
                    master.model.Add(edge + sum(a_terms) <= 1)
                if b_terms:
                    master.model.Add(edge + sum(b_terms) <= 1)
                master.model.Add(edge + sum(a_terms) + sum(b_terms) >= 1)
                value = int((x, y) in free and (nx, ny) in free)
                master.model.AddHint(edge, value)
                edge_hint_count += 1
                edge_hint_ones += value
                edge_vars.append(edge)
    master.model.Maximize(sum(edge_vars))
    if edge_hint_ones != 1081:
        raise RuntimeError(f"E001 edge hint score drift: {edge_hint_ones}")
    return {
        "pose_hint_count": pose_hint_count,
        "selected_pose_hint_count": selected_pose_hint_count,
        "front_clear_hint_count": front_hint_count,
        "edge_hint_count": edge_hint_count,
        "edge_hint_ones": edge_hint_ones,
        "total_hint_count": len(master.model.Proto().solution_hint.vars),
        "edge_variable_count": len(edge_vars),
        "hint_free_cell_digest": stable_digest(sorted(free)),
    }


def direct_solve(master: Any) -> tuple[int, Any, dict[str, Any]]:
    from src.models.cp_sat_worker_config import (
        apply_master_cp_sat_subsolver_filter,
        apply_subproblem_memory_cap,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_CAP_SECONDS
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = 260826
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.cp_model_presolve = False
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.repair_hint = True
    solver.parameters.hint_conflict_limit = 1_000_000
    solver.parameters.log_search_progress = True
    solver.parameters.log_to_stdout = False
    solver.parameters.use_lns_only = True
    apply_subproblem_memory_cap(solver)
    apply_master_cp_sat_subsolver_filter(solver)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("xb", buffering=0) as raw_log:
        def log_callback(line: str) -> None:
            data = line.encode("utf-8", errors="replace")
            raw_log.write(data)
            if not data.endswith(b"\n"):
                raw_log.write(b"\n")

        solver.log_callback = log_callback
        started = time.monotonic()
        status = solver.Solve(master.model)
        elapsed = time.monotonic() - started
    return status, solver, {
        "elapsed_seconds": elapsed,
        "status": solver.StatusName(status),
        "wall_time": solver.WallTime(),
        "objective": (
            float(solver.ObjectiveValue())
            if status in (cp_model.FEASIBLE, cp_model.OPTIMAL)
            else None
        ),
        "best_bound": float(solver.BestObjectiveBound()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "response_stats": solver.ResponseStats(),
        "solver_log_sha256": sha256_file(LOG_PATH),
        "parameters": {
            "cp_model_presolve": False,
            "symmetry_level": 0,
            "cp_model_probing_level": 0,
            "repair_hint": True,
            "hint_conflict_limit": 1_000_000,
            "num_search_workers": 8,
            "use_lns_only": True,
        },
    }


def run() -> dict[str, Any]:
    global master_module
    environment = verify_environment()
    master_module = load_base_module()
    identity = master_module.verify_identity()
    e001 = master_module.import_e001_module()
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    a1_parent = e001.load_parent_solution()
    hint_solution = master_module.reconstruct_solution(
        master_module.E001_REPLACEMENT_ASSIGNMENT
    )

    started = time.monotonic()
    build_started = time.monotonic()
    master = e001.construct_master(stack, inputs)
    master.build()
    build_seconds = time.monotonic() - build_started
    lowering = e001.audit_and_attach_lowering(
        master=master,
        inputs=inputs,
        parent_solution=a1_parent,
    )
    hints = add_objective_and_hints(
        master=master,
        hint_solution=hint_solution,
        pools=inputs["pools"],
    )
    status, solver, solve = direct_solve(master)

    result: dict[str, Any] = {
        "schema": "zmd_zero_condition_e006_recovery_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": {
            **identity,
            "base_runner_sha256": EXPECTED_BASE_RUNNER_SHA256,
            "base_result_sha256": EXPECTED_BASE_RESULT_SHA256,
            "recovery_runner_sha256": sha256_file(Path(__file__).resolve()),
        },
        "environment": environment,
        "build_seconds": build_seconds,
        "pocket_cut_lowering": lowering,
        "hint_surface": hints,
        "solve": solve,
        "ledger_effect": "none",
        "binding_routing_terminal_validator_run": False,
        "elapsed_seconds": time.monotonic() - started,
    }
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        result["verdict"] = "RECOVERY_UNKNOWN"
        result["truth_boundary"] = "No candidate was registered by the recovery path."
        return result

    objective = int(round(float(solver.ObjectiveValue())))
    if objective <= 1081:
        result.update(
            {
                "verdict": "RECOVERY_FEASIBLE_NO_OBJECTIVE_GAIN",
                "candidate": None,
                "registered_incumbent_objective": objective,
                "truth_boundary": (
                    "The complete E001 hint was registered as feasible under the "
                    "objective encoding, but the bounded LNS found no better incumbent."
                ),
                "elapsed_seconds": time.monotonic() - started,
            }
        )
        return result

    master._solver = solver
    master._status = status
    master._last_solution = None
    solution = master.extract_solution()
    morphology = master_module.morphology(
        solution=solution,
        pools=inputs["pools"],
    )
    if morphology["free_adjacency_score"] != objective:
        raise RuntimeError(
            f"recovery objective mismatch: {objective} != "
            f"{morphology['free_adjacency_score']}"
        )

    selected_cut_literals: dict[str, int] = {}
    for row in lowering["resolved_literals"]:
        variable = master.model.GetBoolVarFromProtoIndex(int(row["consumer_var_index"]))
        selected_cut_literals[str(row["source_instance_id"])] = int(solver.Value(variable))
    if sum(selected_cut_literals.values()) > 3:
        raise RuntimeError(f"recovery candidate violates E001 cut: {selected_cut_literals}")

    assignment = {
        "schema": "zmd_e006_recovery_assignment_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": solver.StatusName(status),
        "objective_value": objective,
        "solution": json_safe(solution),
    }
    layout = master_module.solution_layout(solution)
    dump_exclusive(ASSIGNMENT_PATH, assignment)
    dump_exclusive(LAYOUT_PATH, layout)
    gain = objective - 1081
    reduction = 97 - int(morphology["free_component_count"])
    result.update(
        {
            "verdict": (
                "RECOVERY_PERMEABILITY_CANDIDATE"
                if gain > 0 and reduction > 0
                else "RECOVERY_FEASIBLE_NO_COMPONENT_GAIN"
            ),
            "candidate": {
                "assignment_path": str(ASSIGNMENT_PATH.relative_to(ROOT)),
                "assignment_sha256": sha256_file(ASSIGNMENT_PATH),
                "layout_path": str(LAYOUT_PATH.relative_to(ROOT)),
                "layout_sha256": sha256_file(LAYOUT_PATH),
                "objective_gain_over_e001": gain,
                "component_reduction_over_e001": reduction,
                "morphology": morphology,
                "selected_e001_cut_literals": selected_cut_literals,
            },
            "truth_boundary": (
                "Placement-plus-power candidate under the E001 cut and positive "
                "free-adjacency objective; binding and routing remain unrun."
            ),
            "elapsed_seconds": time.monotonic() - started,
        }
    )
    return result


def main() -> int:
    if any(path.exists() for path in (RESULT_PATH, FAILURE_PATH, ASSIGNMENT_PATH, LAYOUT_PATH, LOG_PATH)):
        raise FileExistsError(f"refusing to overwrite E006 recovery outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "solve": result["solve"],
                    "candidate": result.get("candidate"),
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e006_recovery_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


master_module: Any

if __name__ == "__main__":
    raise SystemExit(main())
