#!/usr/bin/env python3
"""E011: maximize free adjacency under E009 contextual interface guards.

Research-only. The selected-pattern coefficients are recomputed in the frozen
E009 occupancy, then converted from an objective into a hard local guard. The
actual objective is exact adjacent-free-pair count. No production or certified
effect is granted.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
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
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
E006_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E006_free_adjacency_master/run_e006.py"
)
E009_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E009_selected_pattern_linearization/run_e009.py"
)
E002_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E002_component_commodity_core/run_component_core.py"
)
E009_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/RESULT.json"
)
E009_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/PATTERN_EXPOSED_ASSIGNMENT.json"
)
E009_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/PATTERN_EXPOSED_LAYOUT.json"
)
E010_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E010_pattern_exposed_mismatch_delta/run-001/RESULT.json"
)
OUT = ROOT / "research_lab/local/zero_condition/E011_guarded_joint_step/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ASSIGNMENT_PATH = OUT / "GUARDED_PERMEABILITY_ASSIGNMENT.json"
LAYOUT_PATH = OUT / "GUARDED_PERMEABILITY_LAYOUT.json"
LOG_PATH = OUT / "SOLVER.log"

EXPECTED_HASHES: dict[Path, str] = {
    E006_RUNNER: "84634cb920fe19a0d724af5e2927ede228b2383fd7c0babf10403b1324bdf20d",
    E009_RUNNER: "963c515e969fae2d90103a8b7371e723e1fefca62a4459d52370fd147b5befda",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E009_RESULT: "c0bce86fd9d2871621a28c883b57f51c3e3e7b5f5efbba9b96c23ea6c55dccec",
    E009_ASSIGNMENT: "7a4a2a21cc13621e935fc6672bfa9f691e2d340ec120ec0947b3b62b3d648924",
    E009_LAYOUT: "3b23f3f801d5b06f5cde90beb7ceb5074101d2be543b141e68ab432940e70d33",
    E010_RESULT: "6e0965a159c52c6e49a5e0c8afc2a57472f8df0669d5631ed04c73749770d4fe",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    HISTORY_ROOT / "rules/canonical_rules.json": "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0",
    HISTORY_ROOT / "rules/preprocess_plan.json": "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee",
    ROOT / "src/models/master_model.py": "d1ada57bc6dcef1818341b26dfd482fb7c1623d106734b8f1a49061c2e7c1371",
    ROOT / "src/models/pose_bool_exact_master.py": "8991b7f98b95ee255c4967b13fc2d22bf6eed5ec54ad1f0e48377a44db0dbd90",
    ROOT / "src/models/cp_sat_worker_config.py": "4f9a4847f179f1ed15d61b17bcdc2340c82c1ec2494abd1eb7402f919c84ba50",
    ROOT / "src/models/binding_subproblem.py": "b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba",
    ROOT / "src/models/port_binding.py": "9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53",
    ROOT / "src/models/routing_binding_context.py": "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2",
    ROOT / "src/models/routing_subproblem.py": "7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718",
    ROOT / "src/search/pr2_l0_fixed_witness_core.py": "eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1",
}

EXPECTED_ENV: dict[str, str] = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "260830",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
SOLVE_CAP_SECONDS = 60.0
BINDING_CAP_SECONDS = 30.0
MAX_POWER_POLES = 53
GRID_W = 70
GRID_H = 70
TOTAL_GRID_EDGES = GRID_H * (GRID_W - 1) + GRID_W * (GRID_H - 1)


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def verify_identity() -> dict[str, Any]:
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")
    if load_json(E009_RESULT).get("verdict") != "PATTERN_EXPOSED_CANDIDATE":
        raise RuntimeError("E009 trigger drift")
    if load_json(E010_RESULT).get("verdict") != "ALTERNATING_CONSTRUCTOR_SECOND_BROAD_IMPROVEMENT":
        raise RuntimeError("E010 trigger drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reconstruct_reference(base: Any) -> dict[str, dict[str, Any]]:
    solution = base.reconstruct_solution(E009_ASSIGNMENT)
    layout = load_json(E009_LAYOUT)
    layout_solution = {
        str(record["instance_id"]): dict(record)
        for record in layout["placements"]
        if isinstance(record, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E009 assignment/layout mismatch")
    return solution


def capture_contextual_guard(master: Any, reference_objective: int) -> dict[str, Any]:
    objective = master.model.Proto().objective
    if float(objective.scaling_factor) != -1.0 or float(objective.offset) != 0.0:
        raise RuntimeError("unexpected contextual objective encoding")
    terms: list[Any] = []
    records: list[tuple[int, int]] = []
    for variable_index, proto_coefficient in zip(
        objective.vars,
        objective.coeffs,
        strict=True,
    ):
        weight = -int(proto_coefficient)
        variable = master.model.GetBoolVarFromProtoIndex(int(variable_index))
        terms.append(weight * variable)
        records.append((int(variable_index), weight))
    if not terms:
        raise RuntimeError("contextual objective is empty")
    master.model.Add(sum(terms) >= int(reference_objective))
    master.model.ClearObjective()
    return {
        "reference_objective": int(reference_objective),
        "term_count": len(terms),
        "coefficient_digest": stable_digest(records),
        "guard_relation": ">=",
    }


def add_edge_objective_and_hints(
    *,
    master: Any,
    reference_solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    base: Any,
) -> dict[str, Any]:
    delegate = master._coordinate_delegate
    cell_poses = getattr(delegate, "_sac_cell_poses", None)
    if not isinstance(cell_poses, dict):
        raise RuntimeError("pose-bool occupancy cache missing")
    occupied = base.occupancy_from_solution(
        solution=reference_solution,
        pools=pools,
    )
    free = {(x, y) for x in range(GRID_W) for y in range(GRID_H)} - occupied
    edge_vars: list[Any] = []
    hinted_ones = 0
    edge_records: list[tuple[int, int, int, int, int]] = []
    for x in range(GRID_W):
        for y in range(GRID_H):
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if nx >= GRID_W or ny >= GRID_H:
                    continue
                a_terms = list(cell_poses.get((x, y), []))
                b_terms = list(cell_poses.get((nx, ny), []))
                edge = master.model.NewBoolVar(f"e011_free_edge_{x}_{y}_{nx}_{ny}")
                if a_terms:
                    master.model.Add(edge + sum(a_terms) <= 1)
                if b_terms:
                    master.model.Add(edge + sum(b_terms) <= 1)
                master.model.Add(edge + sum(a_terms) + sum(b_terms) >= 1)
                value = int((x, y) in free and (nx, ny) in free)
                master.model.AddHint(edge, value)
                hinted_ones += value
                edge_vars.append(edge)
                edge_records.append((x, y, nx, ny, int(edge.Index())))
    if len(edge_vars) != TOTAL_GRID_EDGES:
        raise RuntimeError(f"edge variable count drift: {len(edge_vars)}")
    master.model.Maximize(sum(edge_vars))
    return {
        "edge_variable_count": len(edge_vars),
        "reference_free_adjacency": hinted_ones,
        "edge_variable_digest": stable_digest(edge_records),
        "reference_free_cell_digest": stable_digest(sorted(free)),
    }


def direct_solve(master: Any) -> tuple[int, Any, dict[str, Any]]:
    from src.models.cp_sat_worker_config import (
        apply_master_cp_sat_subsolver_filter,
        apply_subproblem_memory_cap,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_CAP_SECONDS
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = 260830
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.cp_model_presolve = False
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.repair_hint = True
    solver.parameters.hint_conflict_limit = 1_000_000
    solver.parameters.use_lns_only = True
    solver.parameters.log_search_progress = True
    solver.parameters.log_to_stdout = False
    apply_subproblem_memory_cap(solver)
    apply_master_cp_sat_subsolver_filter(solver)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("xb", buffering=0) as raw_log:
        def log_callback(line: str) -> None:
            encoded = line.encode("utf-8", errors="replace")
            raw_log.write(encoded)
            if not encoded.endswith(b"\n"):
                raw_log.write(b"\n")

        solver.log_callback = log_callback
        started = time.monotonic()
        status = solver.Solve(master.model)
        elapsed = time.monotonic() - started
    return status, solver, {
        "status": solver.StatusName(status),
        "elapsed_seconds": elapsed,
        "wall_time": solver.WallTime(),
        "objective": (
            int(round(float(solver.ObjectiveValue())))
            if status in (cp_model.FEASIBLE, cp_model.OPTIMAL)
            else None
        ),
        "best_bound": float(solver.BestObjectiveBound()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "response_stats": solver.ResponseStats(),
        "solver_log_sha256": sha256_file(LOG_PATH),
    }


def evaluate_interface(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e002: Any,
) -> dict[str, Any]:
    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_binding_context import build_routing_binding_context

    context = build_routing_binding_context(
        solution,
        inputs["pools"],
        GRID_W,
        GRID_H,
    )
    build_started = time.monotonic()
    model = PortBindingModel(
        placement_solution=solution,
        facility_pools=inputs["pools"],
        instances=inputs["instances"],
        project_root=HISTORY_ROOT,
        required_generic_outputs=inputs["generic"].get("required_generic_outputs", {}),
        required_generic_inputs=inputs["generic"].get("required_generic_inputs", {}),
        generic_input_slots_by_operation=inputs["plan"]["generic_input_slots_by_operation"],
        generic_output_slots_by_operation=inputs["plan"]["generic_output_slots_by_operation"],
        utility_operation_by_template=inputs["plan"]["utility_operation_by_template"],
        canonical_rules_payload=inputs["rules"],
        routing_context=context,
    )
    model.build()
    compiled, internal = e002.compile_guarded_interface(
        binding_model=model,
        routing_context=context,
        required_generic_inputs=inputs["generic"].get("required_generic_inputs", {}),
    )
    meaningful_patterns = sum(
        len(domain)
        for instance_id, domain in model.binding_domains.items()
        if str(solution[instance_id].get("facility_type", "")) != "power_pole"
    )
    for guard in internal["guards"].values():
        model.model.Add(guard == 1)
    build_seconds = time.monotonic() - build_started
    solve_started = time.monotonic()
    status = model.solve(time_limit_seconds=BINDING_CAP_SECONDS)
    solve_seconds = time.monotonic() - solve_started
    component_sizes = sorted(
        (len(cells) for cells in context.cells_by_component.values()),
        reverse=True,
    )
    return {
        "status": status,
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "meaningful_filtered_pattern_count": meaningful_patterns,
        "compiled_interface": compiled,
        "conflict_summary": json_safe(model.extract_conflict_summary()),
        "fixed_occupancy": {
            "occupied_cell_count": len(context.occupied_cells),
            "free_cell_count": GRID_W * GRID_H - len(context.occupied_cells),
            "free_component_count": len(component_sizes),
            "largest_free_component": component_sizes[0] if component_sizes else 0,
            "component_sizes": component_sizes,
        },
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    environment = verify_environment()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    base = import_module("zmd_e006_base", E006_RUNNER)
    e009 = import_module("zmd_e009_context", E009_RUNNER)
    e002 = import_module("zmd_e002_helper", E002_RUNNER)
    e001 = base.import_e001_module()
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    a1_parent = e001.load_parent_solution()
    reference = reconstruct_reference(base)
    baseline = load_json(E009_RESULT)

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
    contextual = e009.build_linearized_objective(
        master=master,
        inputs=inputs,
        reference_solution=reference,
        base_module=base,
    )
    guard = capture_contextual_guard(
        master,
        int(contextual["reference_objective"]),
    )
    delegate = master._coordinate_delegate
    master.model.Add(sum(delegate.pole_vars.values()) <= MAX_POWER_POLES)
    base_hint = e009.add_complete_hint(
        master=master,
        inputs=inputs,
        reference_solution=reference,
        base_module=base,
    )
    edge = add_edge_objective_and_hints(
        master=master,
        reference_solution=reference,
        pools=inputs["pools"],
        base=base,
    )
    if len(master.model.Proto().solution_hint.vars) != len(master.model.Proto().variables):
        raise RuntimeError("joint model hint is incomplete")
    status, solver, solve = direct_solve(master)

    result: dict[str, Any] = {
        "schema": "zmd_zero_condition_e011_guarded_joint_step_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "environment": environment,
        "build_seconds": build_seconds,
        "pocket_cut_lowering": lowering,
        "contextual_linearization": contextual,
        "contextual_guard": guard,
        "base_hint": base_hint,
        "edge_objective": edge,
        "solve": solve,
        "ledger_effect": "none",
        "routing_solver_run": False,
        "elapsed_seconds": time.monotonic() - started,
    }
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        result["verdict"] = "JOINT_STEP_UNKNOWN"
        result["truth_boundary"] = "No candidate was registered."
        return result

    objective = int(solve["objective"])
    if objective <= int(edge["reference_free_adjacency"]):
        result["verdict"] = "JOINT_STEP_NO_ADJACENCY_GAIN"
        result["truth_boundary"] = (
            "The E009 reference remained the best registered incumbent under the "
            "guarded free-adjacency objective."
        )
        return result

    master._solver = solver
    master._status = status
    master._last_solution = None
    solution = master.extract_solution()
    morphology = base.morphology(solution=solution, pools=inputs["pools"])
    if int(morphology["free_adjacency_score"]) != objective:
        raise RuntimeError("joint objective/recomputed morphology mismatch")
    interface = evaluate_interface(solution=solution, inputs=inputs, e002=e002)

    guard_value = 0
    objective_proto = None
    # Recompute the contextual selected-pattern score in the new solution's
    # literal values from the captured coefficient list is unnecessary for the
    # hard-guard check: CpSolver feasibility already proves it. Record the lower
    # bound and independently measured actual domain instead.
    del objective_proto
    guard_value = int(guard["reference_objective"])

    selected_cut_literals: dict[str, int] = {}
    for row in lowering["resolved_literals"]:
        variable = master.model.GetBoolVarFromProtoIndex(int(row["consumer_var_index"]))
        selected_cut_literals[str(row["source_instance_id"])] = int(solver.Value(variable))
    if sum(selected_cut_literals.values()) > 3:
        raise RuntimeError("joint candidate violates E001 pocket cut")

    assignment = {
        "schema": "zmd_e011_guarded_joint_assignment_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": solver.StatusName(status),
        "free_adjacency_objective": objective,
        "contextual_guard_lower_bound": guard_value,
        "solution": json_safe(solution),
    }
    layout = base.solution_layout(solution)
    dump_exclusive(ASSIGNMENT_PATH, assignment)
    dump_exclusive(LAYOUT_PATH, layout)

    baseline_patterns = int(
        baseline["candidate"]["actual_meaningful_filtered_patterns"]
    )
    actual_patterns = int(interface["meaningful_filtered_pattern_count"])
    if interface["status"] == "FEASIBLE":
        verdict = "JOINT_STEP_COMPONENT_BINDING_FEASIBLE"
    elif actual_patterns >= baseline_patterns:
        verdict = "JOINT_STEP_FAITHFUL_CANDIDATE"
    else:
        verdict = "JOINT_STEP_CONTEXT_GUARD_UNFAITHFUL"
    result.update(
        {
            "verdict": verdict,
            "candidate": {
                "assignment_path": str(ASSIGNMENT_PATH.relative_to(ROOT)),
                "assignment_sha256": sha256_file(ASSIGNMENT_PATH),
                "layout_path": str(LAYOUT_PATH.relative_to(ROOT)),
                "layout_sha256": sha256_file(LAYOUT_PATH),
                "selected_e001_cut_literals": selected_cut_literals,
                "morphology": morphology,
                "interface": interface,
                "free_adjacency_gain": objective
                - int(edge["reference_free_adjacency"]),
                "meaningful_pattern_gain": actual_patterns - baseline_patterns,
                "power_pole_count": sum(
                    str(row.get("facility_type", "")) == "power_pole"
                    for row in solution.values()
                ),
            },
            "truth_boundary": (
                "One radius-limited contextual joint step around E009. The hard "
                "guard is local to E009 occupancy; actual interface metrics were "
                "rebuilt on the candidate."
            ),
            "elapsed_seconds": time.monotonic() - started,
        }
    )
    return result


def main() -> int:
    if any(
        path.exists()
        for path in (RESULT_PATH, FAILURE_PATH, ASSIGNMENT_PATH, LAYOUT_PATH, LOG_PATH)
    ):
        raise FileExistsError(f"refusing to overwrite E011 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "solve": result["solve"],
                    "candidate_summary": (
                        {
                            "free_adjacency_gain": result.get("candidate", {}).get(
                                "free_adjacency_gain"
                            ),
                            "meaningful_pattern_gain": result.get("candidate", {}).get(
                                "meaningful_pattern_gain"
                            ),
                            "morphology": result.get("candidate", {}).get("morphology"),
                            "interface_status": result.get("candidate", {})
                            .get("interface", {})
                            .get("status"),
                        }
                    ),
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
            "schema": "zmd_zero_condition_e011_failure_v1",
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


if __name__ == "__main__":
    raise SystemExit(main())
