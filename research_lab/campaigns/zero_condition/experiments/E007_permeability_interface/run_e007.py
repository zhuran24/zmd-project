#!/usr/bin/env python3
"""E007: test E006 permeability candidate at binding and exact routing.

Research-only. All component rules are ordinary hard constraints in one fresh
model; no repeated assumption-core API is used.
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
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
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
OUT = ROOT / "research_lab/local/zero_condition/E007_permeability_interface/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
BINDING_PATH = OUT / "BINDING_WITNESS.json"
ROUTING_PATH = OUT / "ROUTING_WITNESS.json"

EXPECTED_HASHES: dict[Path, str] = {
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E006_RESULT: "e3ce1ad7f557c1ee52c45588f9bc4ede701939fa444f9c7653157be71551d7d5",
    E006_ASSIGNMENT: "29692d8465374498100e6f58069c92eabb69460d8fc742912ec0984877218b43",
    E006_LAYOUT: "dd228aa137651251f63e8b473579d371d78b28781de4fd76518681eec830edd8",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    HISTORY_ROOT / "rules/canonical_rules.json": "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0",
    HISTORY_ROOT / "rules/preprocess_plan.json": "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee",
    ROOT / "src/models/binding_subproblem.py": "b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba",
    ROOT / "src/models/port_binding.py": "9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53",
    ROOT / "src/models/routing_binding_context.py": "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2",
    ROOT / "src/models/routing_subproblem.py": "7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718",
    ROOT / "src/search/pr2_l0_fixed_witness_core.py": "eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1",
    ROOT / "src/search/exact_campaign.py": "d893e59a9f1bd573208a39905bdb7d677046f97367543958cc201a90b21d1a04",
}

EXPECTED_ENV: dict[str, str] = {
    "PYTHONHASHSEED": "0",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
    "EXACT_ROUTING_CP_SAT_WORKERS": "8",
}
BINDING_CAP_SECONDS = 60.0
ROUTING_CAP_SECONDS = 120.0
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

    consumed_tracked = {
        str(path.relative_to(ROOT))
        for path in EXPECTED_HASHES
        if path.is_relative_to(ROOT)
        and git_output("ls-files", "--", str(path.relative_to(ROOT)))
    }
    dirty_consumed: list[str] = []
    for line in git_output("status", "--porcelain=v1", "--untracked-files=no").splitlines():
        relative = line[3:].strip()
        if " -> " in relative:
            relative = relative.split(" -> ", 1)[1]
        if relative in consumed_tracked:
            dirty_consumed.append(relative)
    if dirty_consumed:
        raise RuntimeError(f"consumed tracked sources are dirty: {dirty_consumed}")

    e006 = load_json(E006_RESULT)
    if e006.get("verdict") != "RECOVERY_PERMEABILITY_CANDIDATE":
        raise RuntimeError("E006 input is not the expected permeability candidate")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reconstruct_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E006_ASSIGNMENT)
    layout = load_json(E006_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E006 assignment/layout structure is invalid")
    solution = {
        str(instance_id): dict(record)
        for instance_id, record in raw.items()
        if isinstance(record, Mapping) and str(instance_id) != "ghost_pick"
    }
    layout_solution = {
        str(record["instance_id"]): dict(record)
        for record in placements
        if isinstance(record, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E006 assignment and layout disagree")
    if sum(bool(row.get("is_mandatory")) for row in solution.values()) != 266:
        raise RuntimeError("E006 mandatory count drift")
    if layout.get("ghost_rect") is not None:
        raise RuntimeError("E006 unexpectedly contains a ghost")
    return solution


def fixed_occupancy_summary(context: Any) -> dict[str, Any]:
    component_sizes = sorted(
        (len(cells) for cells in context.cells_by_component.values()),
        reverse=True,
    )
    return {
        "occupied_cell_count": len(context.occupied_cells),
        "free_cell_count": GRID_W * GRID_H - len(context.occupied_cells),
        "free_component_count": len(component_sizes),
        "largest_free_component": component_sizes[0] if component_sizes else 0,
        "component_sizes": component_sizes,
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    environment = verify_environment()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    e002 = import_module("zmd_e002_component_helper", E002_RUNNER)
    e001 = import_module("zmd_e001_strict_helper", E001_RUNNER)

    from src.models.binding_subproblem import (
        PortBindingModel,
        load_binding_plan_semantics,
    )
    from src.models.master_model import (
        load_generic_io_requirements_artifact,
        load_project_data,
    )
    from src.models.routing_binding_context import build_routing_binding_context
    from src.models.routing_subproblem import (
        RoutingPlacementCore,
        RoutingSubproblem,
        run_exact_routing_precheck,
    )
    from src.search.pr2_l0_fixed_witness_core import (
        _normalize_port_specs,
        _routing_build_rejection,
    )

    solution = reconstruct_solution()
    instances, pools, rules = load_project_data(
        HISTORY_ROOT,
        solve_mode="certified_exact",
    )
    generic = load_generic_io_requirements_artifact(HISTORY_ROOT)
    plan = load_binding_plan_semantics(project_root=HISTORY_ROOT)
    routing_context = build_routing_binding_context(
        solution,
        pools,
        GRID_W,
        GRID_H,
    )
    placement_core = RoutingPlacementCore.from_occupied_cells(
        set(routing_context.occupied_cells),
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )

    started = time.monotonic()
    build_started = time.monotonic()
    binding_model = PortBindingModel(
        placement_solution=solution,
        facility_pools=pools,
        instances=instances,
        project_root=HISTORY_ROOT,
        required_generic_outputs=generic.get("required_generic_outputs", {}),
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
        generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
        utility_operation_by_template=plan["utility_operation_by_template"],
        canonical_rules_payload=rules,
        routing_context=routing_context,
    )
    binding_model.build()
    compiled, internal = e002.compile_guarded_interface(
        binding_model=binding_model,
        routing_context=routing_context,
        required_generic_inputs=generic.get("required_generic_inputs", {}),
    )
    guards = dict(internal["guards"])
    if len(guards) != 19:
        raise RuntimeError(f"component guard count drift: {len(guards)}")
    for commodity, guard in sorted(guards.items()):
        binding_model.model.Add(guard == 1)
    binding_build_seconds = time.monotonic() - build_started

    solve_started = time.monotonic()
    binding_status = binding_model.solve(time_limit_seconds=BINDING_CAP_SECONDS)
    binding_solve_seconds = time.monotonic() - solve_started
    solver = binding_model._solver
    result: dict[str, Any] = {
        "schema": "zmd_zero_condition_e007_permeability_interface_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "environment": environment,
        "fixed_occupancy": fixed_occupancy_summary(routing_context),
        "binding": {
            "status": binding_status,
            "build_seconds": binding_build_seconds,
            "solve_seconds": binding_solve_seconds,
            "cap_seconds": BINDING_CAP_SECONDS,
            "wall_time": float(solver.WallTime()) if solver is not None else None,
            "branches": int(solver.NumBranches()) if solver is not None else None,
            "conflicts": int(solver.NumConflicts()) if solver is not None else None,
            "compiled_interface": compiled,
            "component_guards_fixed_true": sorted(guards),
            "conflict_summary": json_safe(binding_model.extract_conflict_summary()),
        },
        "routing": {
            "reached": False,
            "status": "NOT_REACHED",
        },
        "strict_validator": {
            "reached": False,
            "status": "NOT_REACHED",
        },
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }

    if binding_status != "FEASIBLE":
        result["verdict"] = (
            "PERMEABILITY_COMPONENT_BINDING_INFEASIBLE"
            if binding_status == "INFEASIBLE"
            else "PERMEABILITY_COMPONENT_BINDING_UNKNOWN"
            if binding_status == "TIMEOUT"
            else "BINDING_EXECUTION_FAILURE"
        )
        result["truth_boundary"] = (
            "Fixed E006 placement under fresh front, duplicate-terminal, and all-"
            "commodity component-support binding semantics; exact routing unrun."
        )
        result["elapsed_seconds"] = time.monotonic() - started
        return result

    selection = binding_model.extract_selection()
    port_specs = binding_model.extract_port_specs()
    normalized_ports = _normalize_port_specs(port_specs)
    precheck_started = time.monotonic()
    precheck = run_exact_routing_precheck(
        placement_core=placement_core,
        port_specs=port_specs,
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    precheck_seconds = time.monotonic() - precheck_started
    public_precheck = {key: value for key, value in precheck.items() if key != "_analysis"}
    binding_witness = {
        "schema": "zmd_zero_condition_e007_binding_witness_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "placement_assignment_sha256": EXPECTED_HASHES[E006_ASSIGNMENT],
        "status": "FEASIBLE",
        "selection": json_safe(selection),
        "selection_digest": stable_digest(selection),
        "port_specs": json_safe(normalized_ports),
        "port_specs_digest": stable_digest(normalized_ports),
        "production_precheck": json_safe(public_precheck),
        "production_precheck_seconds": precheck_seconds,
    }
    dump_exclusive(BINDING_PATH, binding_witness)
    result["binding"].update(
        {
            "witness_path": str(BINDING_PATH.relative_to(ROOT)),
            "witness_sha256": sha256_file(BINDING_PATH),
            "selection_digest": binding_witness["selection_digest"],
            "port_specs_digest": binding_witness["port_specs_digest"],
            "port_count": len(port_specs),
            "production_precheck": json_safe(public_precheck),
            "production_precheck_seconds": precheck_seconds,
        }
    )
    if str(precheck.get("status")) != "feasible":
        result["verdict"] = "COMPONENT_COMPILER_PRODUCTION_PRECHECK_MISMATCH"
        result["truth_boundary"] = (
            "Compiled binding admitted a witness rejected by production precheck; "
            "interface semantics require repair before routing."
        )
        result["elapsed_seconds"] = time.monotonic() - started
        return result

    routing_build_started = time.monotonic()
    routing_model = RoutingSubproblem.from_placement_core(
        placement_core,
        port_specs,
        sorted({str(port["commodity"]) for port in port_specs}),
        domain_analysis=precheck.get("_analysis"),
    )
    routing_model.build()
    routing_build_seconds = time.monotonic() - routing_build_started
    build_rejection = _routing_build_rejection(routing_model.build_stats)
    result["routing"] = {
        "reached": True,
        "status": "BUILD_COMPLETE" if build_rejection is None else "BUILD_REJECTED",
        "build_seconds": routing_build_seconds,
        "build_stats": json_safe(routing_model.build_stats),
        "build_rejection": build_rejection,
    }
    if build_rejection is not None:
        result["verdict"] = "EXACT_ROUTING_BUILD_REJECTED"
        result["truth_boundary"] = "Binding passed, but routing build contract rejected."
        result["elapsed_seconds"] = time.monotonic() - started
        return result

    routing_solve_started = time.monotonic()
    routing_status = routing_model.solve(time_limit=ROUTING_CAP_SECONDS)
    routing_solve_seconds = time.monotonic() - routing_solve_started
    result["routing"].update(
        {
            "status": routing_status,
            "solve_seconds": routing_solve_seconds,
            "cap_seconds": ROUTING_CAP_SECONDS,
        }
    )
    if routing_status != "FEASIBLE":
        result["verdict"] = (
            "PERMEABILITY_EXACT_ROUTING_INFEASIBLE"
            if routing_status == "INFEASIBLE"
            else "PERMEABILITY_EXACT_ROUTING_UNKNOWN"
            if routing_status == "TIMEOUT"
            else "ROUTING_EXECUTION_FAILURE"
        )
        result["truth_boundary"] = (
            "Component-compatible binding found; exact routing did not produce a "
            "witness under the stated terminal status."
        )
        result["elapsed_seconds"] = time.monotonic() - started
        return result

    routes = routing_model.extract_routes()
    routing_witness = {
        "schema": "zmd_zero_condition_e007_routing_witness_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "placement_assignment_sha256": EXPECTED_HASHES[E006_ASSIGNMENT],
        "binding_witness_sha256": sha256_file(BINDING_PATH),
        "status": "FEASIBLE",
        "routes": json_safe(routes),
        "route_witness_digest": stable_digest(routes),
        "route_record_count": len(routes),
        "routing_build_stats": json_safe(routing_model.build_stats),
    }
    dump_exclusive(ROUTING_PATH, routing_witness)
    result["routing"].update(
        {
            "witness_path": str(ROUTING_PATH.relative_to(ROOT)),
            "witness_sha256": sha256_file(ROUTING_PATH),
            "route_witness_digest": routing_witness["route_witness_digest"],
            "route_record_count": len(routes),
        }
    )

    validator_started = time.monotonic()
    validator = e001.strict_non_ghost_terminal_validation(
        solution=solution,
        port_specs=port_specs,
        routes=routes,
        occupied_cells=set(routing_context.occupied_cells),
    )
    validator_seconds = time.monotonic() - validator_started
    result["strict_validator"] = {
        "reached": True,
        "status": str(validator.get("status", "MISSING")),
        "seconds": validator_seconds,
        "details": json_safe(validator),
    }
    result["verdict"] = (
        "ZERO_CONDITION_ROUTING_COMPLETE_RESEARCH_WITNESS"
        if validator.get("status") == "PASS"
        else "STRICT_VALIDATOR_REJECTED_ROUTING_WITNESS"
    )
    result["truth_boundary"] = (
        "Placement, power, component-aware binding, exact routing, and non-ghost "
        "strict terminal validation only; flow/startup/game/certification remain."
    )
    result["elapsed_seconds"] = time.monotonic() - started
    return result


def main() -> int:
    if any(
        path.exists()
        for path in (RESULT_PATH, FAILURE_PATH, BINDING_PATH, ROUTING_PATH)
    ):
        raise FileExistsError(f"refusing to overwrite E007 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "binding_status": result["binding"]["status"],
                    "routing_status": result["routing"]["status"],
                    "strict_validator_status": result["strict_validator"]["status"],
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
            "schema": "zmd_zero_condition_e007_failure_v1",
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
