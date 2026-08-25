#!/usr/bin/env python3
"""E009: one outer-loop linearization of selected-pose binding viability.

Research-only. Scores are computed in the frozen E006 occupancy and optimized in
a radius-20 trust region. They are not globally valid constraints or a production
objective.
"""

from __future__ import annotations

from collections import Counter
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
E002_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E002_component_commodity_core/run_component_core.py"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
)
E006_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E006_free_adjacency_master/run-003/RESULT.json"
)
E006_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E006_free_adjacency_master/run-003/PERMEABILITY_ASSIGNMENT.json"
)
E006_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E006_free_adjacency_master/run-003/PERMEABILITY_LAYOUT.json"
)
E007_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E007_permeability_interface/run-001/RESULT.json"
)
E008_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E008_permeability_mismatch_delta/run-001/RESULT.json"
)
OUT = ROOT / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ASSIGNMENT_PATH = OUT / "PATTERN_EXPOSED_ASSIGNMENT.json"
LAYOUT_PATH = OUT / "PATTERN_EXPOSED_LAYOUT.json"
LOG_PATH = OUT / "SOLVER.log"

EXPECTED_HASHES: dict[Path, str] = {
    E006_RUNNER: "84634cb920fe19a0d724af5e2927ede228b2383fd7c0babf10403b1324bdf20d",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E006_RESULT: "e3ce1ad7f557c1ee52c45588f9bc4ede701939fa444f9c7653157be71551d7d5",
    E006_ASSIGNMENT: "29692d8465374498100e6f58069c92eabb69460d8fc742912ec0984877218b43",
    E006_LAYOUT: "dd228aa137651251f63e8b473579d371d78b28781de4fd76518681eec830edd8",
    E007_RESULT: "51b0ed0c8b10e1454b5fb7c1785e7b9c9a9db56501c5d420e300daaec511bdee",
    E008_RESULT: "07cb000e85ba1795d851f1b79e3e4d82af9974cc4b68369932e50fb2205d67d9",
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
    "EXACT_MASTER_RANDOM_SEED": "260829",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
TRUST_RADIUS = 20
MAX_POWER_POLES = 54
SOLVE_CAP_SECONDS = 60.0
BINDING_CAP_SECONDS = 30.0
GRID_W = 70
GRID_H = 70
EXACT_PATTERN_WEIGHT = 10_000
GENERIC_CLEAR_WEIGHT = 100
POWER_POLE_PENALTY = 1


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
    if load_json(E007_RESULT).get("verdict") != "PERMEABILITY_COMPONENT_BINDING_INFEASIBLE":
        raise RuntimeError("E007 trigger drift")
    if load_json(E008_RESULT).get("verdict") != "PERMEABILITY_PROXY_PARTIAL_INTERFACE_IMPROVEMENT":
        raise RuntimeError("E008 trigger drift")
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


def selected_sets(
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
                raise RuntimeError(f"mandatory hint has no group: {instance_id}")
            mandatory.add((str(group_id), pose_idx))
            continue
        facility_type = str(row.get("facility_type", ""))
        if facility_type == "power_pole":
            poles.add(pose_idx)
        else:
            optional.add((facility_type, pose_idx))
    return mandatory, optional, poles


def all_ports_free(
    ports: Sequence[Mapping[str, Any]],
    occupied: set[tuple[int, int]],
) -> bool:
    return all(
        0 <= int(port["x"]) < GRID_W
        and 0 <= int(port["y"]) < GRID_H
        and (int(port["x"]), int(port["y"])) not in occupied
        for port in ports
    )


def build_linearized_objective(
    *,
    master: Any,
    inputs: Mapping[str, Any],
    reference_solution: Mapping[str, Mapping[str, Any]],
    base_module: Any,
) -> dict[str, Any]:
    from src.preprocess.operation_profiles import get_operation_port_profile
    from src.models.port_binding import (
        enumerate_pose_level_port_bindings_with_cache_info,
        is_routing_visible_output_commodity,
        routing_free_sink_commodities_from_generic_inputs,
        supports_exact_pose_level_binding,
    )

    delegate = master._coordinate_delegate
    occupied = base_module.occupancy_from_solution(
        solution=reference_solution,
        pools=inputs["pools"],
    )
    mandatory_selected, optional_selected, pole_selected = selected_sets(
        delegate=delegate,
        solution=reference_solution,
    )
    routing_free = routing_free_sink_commodities_from_generic_inputs(
        inputs["generic"].get("required_generic_inputs", {})
    )

    score_cache: dict[tuple[str, str, int], dict[str, int]] = {}
    objective_terms: list[Any] = []
    coefficient_records: list[dict[str, Any]] = []
    reference_exact_patterns = 0
    reference_generic_clear = 0
    reference_poles = len(pole_selected)
    selected_variables: list[Any] = []

    def pose_score(
        *,
        operation_type: str,
        facility_type: str,
        pose_idx: int,
    ) -> dict[str, int]:
        key = (operation_type, facility_type, int(pose_idx))
        cached = score_cache.get(key)
        if cached is not None:
            return cached
        pose = inputs["pools"][facility_type][int(pose_idx)]
        exact_survivors = 0
        generic_clear = 0
        if supports_exact_pose_level_binding(operation_type):
            patterns, _cache_hit = enumerate_pose_level_port_bindings_with_cache_info(
                operation_type,
                pose,
            )
            for pattern in patterns:
                visible_outputs = [
                    port
                    for port in pattern.get("output_ports", [])
                    if is_routing_visible_output_commodity(
                        port["commodity"],
                        routing_free,
                    )
                ]
                active = list(pattern.get("input_ports", [])) + visible_outputs
                if active and all_ports_free(active, occupied):
                    exact_survivors += 1
        else:
            profile = get_operation_port_profile(operation_type)
            if int(profile.generic_input_slots) > 0:
                generic_clear += sum(
                    (int(port["x"]), int(port["y"])) not in occupied
                    for port in pose.get("input_port_cells", []) or []
                )
            if int(profile.generic_output_slots) > 0:
                generic_clear += sum(
                    (int(port["x"]), int(port["y"])) not in occupied
                    for port in pose.get("output_port_cells", []) or []
                )
        record = {
            "exact_pattern_survivors": int(exact_survivors),
            "generic_clear_ports": int(generic_clear),
        }
        score_cache[key] = record
        return record

    for (group_id, pose_idx), variable in sorted(delegate.x_vars.items()):
        operation_type = str(delegate._mandatory_operation_by_group[group_id])
        facility_type = str(delegate._mandatory_template_by_group[group_id])
        score = pose_score(
            operation_type=operation_type,
            facility_type=facility_type,
            pose_idx=int(pose_idx),
        )
        coefficient = (
            EXACT_PATTERN_WEIGHT * score["exact_pattern_survivors"]
            + GENERIC_CLEAR_WEIGHT * score["generic_clear_ports"]
        )
        if coefficient:
            objective_terms.append(int(coefficient) * variable)
        selected = (str(group_id), int(pose_idx)) in mandatory_selected
        if selected:
            selected_variables.append(variable)
            reference_exact_patterns += score["exact_pattern_survivors"]
            reference_generic_clear += score["generic_clear_ports"]
        coefficient_records.append(
            {
                "kind": "mandatory",
                "group_id": str(group_id),
                "operation_type": operation_type,
                "facility_type": facility_type,
                "pose_idx": int(pose_idx),
                "selected_in_reference": selected,
                **score,
                "objective_coefficient": int(coefficient),
            }
        )

    for (facility_type, pose_idx), variable in sorted(delegate.ro_vars.items()):
        operation_type = str(master.utility_operation_by_template.get(facility_type, ""))
        score = (
            pose_score(
                operation_type=operation_type,
                facility_type=str(facility_type),
                pose_idx=int(pose_idx),
            )
            if operation_type
            else {"exact_pattern_survivors": 0, "generic_clear_ports": 0}
        )
        coefficient = (
            EXACT_PATTERN_WEIGHT * score["exact_pattern_survivors"]
            + GENERIC_CLEAR_WEIGHT * score["generic_clear_ports"]
        )
        if coefficient:
            objective_terms.append(int(coefficient) * variable)
        selected = (str(facility_type), int(pose_idx)) in optional_selected
        if selected:
            selected_variables.append(variable)
            reference_exact_patterns += score["exact_pattern_survivors"]
            reference_generic_clear += score["generic_clear_ports"]
        coefficient_records.append(
            {
                "kind": "required_optional",
                "operation_type": operation_type,
                "facility_type": str(facility_type),
                "pose_idx": int(pose_idx),
                "selected_in_reference": selected,
                **score,
                "objective_coefficient": int(coefficient),
            }
        )

    for pose_idx, variable in sorted(delegate.pole_vars.items()):
        objective_terms.append(-POWER_POLE_PENALTY * variable)
        selected = int(pose_idx) in pole_selected
        if selected:
            selected_variables.append(variable)
        coefficient_records.append(
            {
                "kind": "power_pole",
                "facility_type": "power_pole",
                "pose_idx": int(pose_idx),
                "selected_in_reference": selected,
                "exact_pattern_survivors": 0,
                "generic_clear_ports": 0,
                "objective_coefficient": -POWER_POLE_PENALTY,
            }
        )

    if len(selected_variables) != len(reference_solution):
        raise RuntimeError(
            f"selected variable mapping drift: {len(selected_variables)} != "
            f"{len(reference_solution)}"
        )
    master.model.Add(
        sum(selected_variables) >= len(selected_variables) - TRUST_RADIUS
    )
    master.model.Add(sum(delegate.pole_vars.values()) <= MAX_POWER_POLES)
    master.model.Maximize(sum(objective_terms))
    reference_objective = (
        EXACT_PATTERN_WEIGHT * reference_exact_patterns
        + GENERIC_CLEAR_WEIGHT * reference_generic_clear
        - POWER_POLE_PENALTY * reference_poles
    )
    return {
        "schema": "zmd_e009_selected_pattern_linearization_v1",
        "reference_occupied_cell_count": len(occupied),
        "trust_radius": TRUST_RADIUS,
        "selected_variable_count": len(selected_variables),
        "max_power_poles": MAX_POWER_POLES,
        "weights": {
            "exact_pattern": EXACT_PATTERN_WEIGHT,
            "generic_clear": GENERIC_CLEAR_WEIGHT,
            "power_pole_penalty": POWER_POLE_PENALTY,
        },
        "reference_exact_pattern_survivors": reference_exact_patterns,
        "reference_generic_clear_ports": reference_generic_clear,
        "reference_power_poles": reference_poles,
        "reference_objective": reference_objective,
        "coefficient_nonzero_count": sum(
            int(record["objective_coefficient"] != 0)
            for record in coefficient_records
        ),
        "coefficient_record_count": len(coefficient_records),
        "coefficient_digest": stable_digest(coefficient_records),
        "coefficient_distribution": dict(
            sorted(
                Counter(
                    int(record["objective_coefficient"])
                    for record in coefficient_records
                ).items()
            )
        ),
    }


def add_complete_hint(
    *,
    master: Any,
    inputs: Mapping[str, Any],
    reference_solution: Mapping[str, Mapping[str, Any]],
    base_module: Any,
) -> dict[str, Any]:
    delegate = master._coordinate_delegate
    occupied = base_module.occupancy_from_solution(
        solution=reference_solution,
        pools=inputs["pools"],
    )
    mandatory, optional, poles = selected_sets(
        delegate=delegate,
        solution=reference_solution,
    )
    selected_count = 0
    for key, variable in delegate.x_vars.items():
        value = int((str(key[0]), int(key[1])) in mandatory)
        master.model.AddHint(variable, value)
        selected_count += value
    for key, variable in delegate.ro_vars.items():
        value = int((str(key[0]), int(key[1])) in optional)
        master.model.AddHint(variable, value)
        selected_count += value
    for pose_idx, variable in delegate.pole_vars.items():
        value = int(int(pose_idx) in poles)
        master.model.AddHint(variable, value)
        selected_count += value
    for key, variable in delegate._front_clear.items():
        master.model.AddHint(variable, int((int(key[0]), int(key[1])) not in occupied))
    hint_count = len(master.model.Proto().solution_hint.vars)
    variable_count = len(master.model.Proto().variables)
    if hint_count != variable_count:
        raise RuntimeError(f"incomplete hint: {hint_count} != {variable_count}")
    return {
        "hint_count": hint_count,
        "variable_count": variable_count,
        "selected_pose_count": selected_count,
        "reference_free_cell_digest": stable_digest(
            sorted(
                {(x, y) for x in range(GRID_W) for y in range(GRID_H)} - occupied
            )
        ),
    }


def direct_solve(master: Any) -> tuple[int, Any, dict[str, Any]]:
    from src.models.cp_sat_worker_config import (
        apply_master_cp_sat_subsolver_filter,
        apply_subproblem_memory_cap,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_CAP_SECONDS
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = 260829
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
            float(solver.ObjectiveValue())
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
    meaningful_patterns = 0
    for instance_id, domain in model.binding_domains.items():
        if str(solution[instance_id].get("facility_type", "")) == "power_pole":
            continue
        if any(pattern.get("active_ports") for pattern in domain):
            meaningful_patterns += len(domain)
    for guard in internal["guards"].values():
        model.model.Add(guard == 1)
    build_seconds = time.monotonic() - build_started
    solve_started = time.monotonic()
    status = model.solve(time_limit_seconds=BINDING_CAP_SECONDS)
    solve_seconds = time.monotonic() - solve_started
    sizes = sorted(
        (len(cells) for cells in context.cells_by_component.values()),
        reverse=True,
    )
    return {
        "status": status,
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "fixed_occupancy": {
            "occupied_cell_count": len(context.occupied_cells),
            "free_cell_count": GRID_W * GRID_H - len(context.occupied_cells),
            "free_component_count": len(sizes),
            "largest_free_component": sizes[0] if sizes else 0,
            "component_sizes": sizes,
        },
        "compiled_interface": compiled,
        "meaningful_filtered_pattern_count": meaningful_patterns,
        "conflict_summary": json_safe(model.extract_conflict_summary()),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    environment = verify_environment()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    base = import_module("zmd_e006_base", E006_RUNNER)
    e001 = base.import_e001_module()
    e002 = import_module("zmd_e002_helper", E002_RUNNER)
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent_a1 = e001.load_parent_solution()
    reference_solution = base.reconstruct_solution(E006_ASSIGNMENT)
    e006_baseline = load_json(E007_RESULT)

    started = time.monotonic()
    build_started = time.monotonic()
    master = e001.construct_master(stack, inputs)
    master.build()
    build_seconds = time.monotonic() - build_started
    lowering = e001.audit_and_attach_lowering(
        master=master,
        inputs=inputs,
        parent_solution=parent_a1,
    )
    linearization = build_linearized_objective(
        master=master,
        inputs=inputs,
        reference_solution=reference_solution,
        base_module=base,
    )
    hint = add_complete_hint(
        master=master,
        inputs=inputs,
        reference_solution=reference_solution,
        base_module=base,
    )
    status, solver, solve = direct_solve(master)

    result: dict[str, Any] = {
        "schema": "zmd_zero_condition_e009_selected_pattern_linearization_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "environment": environment,
        "build_seconds": build_seconds,
        "pocket_cut_lowering": lowering,
        "linearization": linearization,
        "hint": hint,
        "solve": solve,
        "ledger_effect": "none",
        "routing_solver_run": False,
        "elapsed_seconds": time.monotonic() - started,
    }
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        result["verdict"] = "PATTERN_LINEARIZATION_UNKNOWN"
        result["truth_boundary"] = "No new master candidate was registered."
        return result

    objective = int(round(float(solver.ObjectiveValue())))
    if objective <= int(linearization["reference_objective"]):
        result["verdict"] = "PATTERN_LINEARIZATION_NO_PREDICTED_GAIN"
        result["truth_boundary"] = (
            "The E006 hint remained the best registered incumbent under the local "
            "linearized objective."
        )
        return result

    master._solver = solver
    master._status = status
    master._last_solution = None
    solution = master.extract_solution()
    morphology = base.morphology(solution=solution, pools=inputs["pools"])
    interface = evaluate_interface(solution=solution, inputs=inputs, e002=e002)

    selected_cut_literals: dict[str, int] = {}
    for row in lowering["resolved_literals"]:
        variable = master.model.GetBoolVarFromProtoIndex(int(row["consumer_var_index"]))
        selected_cut_literals[str(row["source_instance_id"])] = int(solver.Value(variable))
    if sum(selected_cut_literals.values()) > 3:
        raise RuntimeError(f"candidate violates E001 cut: {selected_cut_literals}")

    assignment = {
        "schema": "zmd_e009_pattern_exposed_assignment_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": solver.StatusName(status),
        "linearized_objective": objective,
        "solution": json_safe(solution),
    }
    layout = base.solution_layout(solution)
    dump_exclusive(ASSIGNMENT_PATH, assignment)
    dump_exclusive(LAYOUT_PATH, layout)

    baseline_compiled = e006_baseline["binding"]["compiled_interface"]
    baseline_solution = load_json(E006_ASSIGNMENT)["solution"]
    baseline_power_poles = sum(
        str(record.get("facility_type", "")) == "power_pole"
        for record in baseline_solution.values()
        if isinstance(record, Mapping)
    )
    baseline_meaningful = (
        int(baseline_compiled["filtered_binding_option_count"])
        - int(baseline_power_poles)
    )
    actual_pattern_delta = (
        int(interface["meaningful_filtered_pattern_count"]) - baseline_meaningful
    )
    pattern_total_delta = (
        int(interface["compiled_interface"]["filtered_binding_option_count"])
        - int(baseline_compiled["filtered_binding_option_count"])
    )
    front_pruned_delta = (
        int(
            interface["compiled_interface"]["routing_aware_filter_stats"][
                "front_blocked_patterns_pruned"
            ]
        )
        - int(
            baseline_compiled["routing_aware_filter_stats"][
                "front_blocked_patterns_pruned"
            ]
        )
    )

    if actual_pattern_delta > 0:
        verdict = (
            "PATTERN_EXPOSED_COMPONENT_BINDING_FEASIBLE"
            if interface["status"] == "FEASIBLE"
            else "PATTERN_EXPOSED_CANDIDATE"
        )
    else:
        verdict = "PATTERN_LINEARIZATION_UNFAITHFUL"
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
                "linearized_objective": objective,
                "linearized_objective_gain": objective
                - int(linearization["reference_objective"]),
                "baseline_meaningful_filtered_patterns": baseline_meaningful,
                "meaningful_filtered_pattern_delta": actual_pattern_delta,
                "total_filtered_pattern_delta": pattern_total_delta,
                "front_pruned_pattern_delta": front_pruned_delta,
            },
            "truth_boundary": (
                "One radius-20 local linearization around E006. Coefficients are "
                "contextual and have no validity outside this construction step."
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
        raise FileExistsError(f"refusing to overwrite E009 outputs under {OUT}")
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
                            key: value
                            for key, value in result.get("candidate", {}).items()
                            if key
                            in {
                                "linearized_objective_gain",
                                "meaningful_filtered_pattern_delta",
                                "total_filtered_pattern_delta",
                                "front_pruned_pattern_delta",
                                "morphology",
                            }
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
            "schema": "zmd_zero_condition_e009_failure_v1",
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
