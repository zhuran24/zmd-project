#!/usr/bin/env python3
"""E014: exhaust fixed-outside one-literal repairs from E013's budget-16 set.

The runner is research-only. It enumerates exact placement/power alternatives for
one current consumer literal at a time, then rebuilds the complete cheap binding
interface for every candidate. Raw output remains below research_lab/local.
"""

from __future__ import annotations

from collections import Counter
import datetime
import gc
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

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E014_fixed_outside_mobility/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

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
E013_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E013_residual_boundary_coverage/run-004/RESULT.json"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
)
E002_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E002_component_commodity_core/run_component_core.py"
)

EXPECTED_HASHES: dict[Path, str] = {
    E009_RESULT: "c0bce86fd9d2871621a28c883b57f51c3e3e7b5f5efbba9b96c23ea6c55dccec",
    E009_ASSIGNMENT: "7a4a2a21cc13621e935fc6672bfa9f691e2d340ec120ec0947b3b62b3d648924",
    E009_LAYOUT: "3b23f3f801d5b06f5cde90beb7ceb5074101d2be543b141e68ab432940e70d33",
    E013_RESULT: "99c029fe71c2835bd5d2f5cd16d00f324856d70ce305278e2bb3aa944cbf6fd1",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    ROOT / "research_lab/campaigns/zero_condition/experiments/E013_residual_boundary_coverage/run_e013.py": "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    ROOT / "src/models/master_model.py": "d1ada57bc6dcef1818341b26dfd482fb7c1623d106734b8f1a49061c2e7c1371",
    ROOT / "src/models/pose_bool_exact_master.py": "8991b7f98b95ee255c4967b13fc2d22bf6eed5ec54ad1f0e48377a44db0dbd90",
    ROOT / "src/models/binding_subproblem.py": "b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba",
    ROOT / "src/models/routing_binding_context.py": "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2",
    ROOT / "src/models/routing_subproblem.py": "7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718",
    ROOT / "src/models/port_binding.py": "9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53",
    ROOT / "src/search/pr2_l0_fixed_witness_core.py": "eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1",
    ROOT / "src/search/exact_campaign.py": "d893e59a9f1bd573208a39905bdb7d677046f97367543958cc201a90b21d1a04",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    HISTORY_ROOT / "rules/canonical_rules.json": "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0",
    HISTORY_ROOT / "rules/preprocess_plan.json": "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee",
}

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "260914",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

GRID_W = 70
GRID_H = 70
BINDING_CAP_SECONDS = 10.0
ROUTING_CAP_SECONDS = 180.0


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


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E014 must run on research/main")
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
            f"environment mismatch: mismatches={mismatches}, "
            f"unexpected_exact={unexpected_exact}"
        )

    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")
    e009 = load_json(E009_RESULT)
    e013 = load_json(E013_RESULT)
    if e009.get("verdict") != "PATTERN_EXPOSED_CANDIDATE":
        raise RuntimeError("E009 trigger drift")
    if e013.get("verdict") != "DISPERSED_GROUP_POSE_NEIGHBORHOOD_PLAUSIBLE":
        raise RuntimeError("E013 trigger drift")
    budget16 = next(
        row
        for row in e013["max_coverage_by_literal_budget"]
        if int(row["budget"]) == 16
    )
    if int(budget16["selected_literal_count"]) != 16:
        raise RuntimeError("E013 budget-16 portfolio count drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output("status", "--porcelain=v1", "--untracked-files=no"),
    }


def reconstruct_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E009_ASSIGNMENT)
    layout = load_json(E009_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E009 assignment/layout structure is invalid")
    solution = {
        str(instance_id): dict(record)
        for instance_id, record in raw.items()
        if isinstance(record, Mapping)
    }
    layout_solution = {
        str(record["instance_id"]): dict(record)
        for record in placements
        if isinstance(record, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E009 assignment and layout disagree")
    if sum(bool(row.get("is_mandatory")) for row in solution.values()) != 266:
        raise RuntimeError("E009 mandatory count drift")
    if sum(str(row.get("facility_type")) == "power_pole" for row in solution.values()) != 53:
        raise RuntimeError("E009 power-pole count drift")
    return solution


def pose_cells(
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    facility_type: str,
    pose_idx: int,
) -> frozenset[tuple[int, int]]:
    pool = pools.get(facility_type)
    if not isinstance(pool, list) or not (0 <= pose_idx < len(pool)):
        raise RuntimeError(f"pose missing from pool: {facility_type}@{pose_idx}")
    raw = pool[pose_idx].get("occupied_cells")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"pose has no occupied cells: {facility_type}@{pose_idx}")
    cells = frozenset((int(cell[0]), int(cell[1])) for cell in raw)
    if any(not (0 <= x < GRID_W and 0 <= y < GRID_H) for x, y in cells):
        raise RuntimeError(f"pose is outside grid: {facility_type}@{pose_idx}")
    return cells


def base_occupancy(
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[frozenset[tuple[int, int]], dict[tuple[int, int], str]]:
    owner_by_cell: dict[tuple[int, int], str] = {}
    for instance_id, row in solution.items():
        cells = pose_cells(
            pools,
            str(row["facility_type"]),
            int(row["pose_idx"]),
        )
        for cell in cells:
            if cell in owner_by_cell:
                raise RuntimeError(
                    f"E009 occupancy overlap at {cell}: "
                    f"{owner_by_cell[cell]} and {instance_id}"
                )
            owner_by_cell[cell] = str(instance_id)
    return frozenset(owner_by_cell), owner_by_cell


def replacement_row(
    *,
    source: Mapping[str, Any],
    pose: Mapping[str, Any],
    pose_idx: int,
    instance_id: str,
) -> dict[str, Any]:
    row = dict(source)
    row["instance_id"] = instance_id
    row["pose_idx"] = int(pose_idx)
    row["pose_id"] = str(pose["pose_id"])
    row["anchor"] = {
        "x": int(dict(pose["anchor"])["x"]),
        "y": int(dict(pose["anchor"])["y"]),
    }
    return row


def all_powered_facilities_covered(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    selected_poles: set[int],
    powered_templates: set[str],
    coverers: Mapping[str, Mapping[int, Sequence[int]]],
) -> bool:
    for row in solution.values():
        facility_type = str(row["facility_type"])
        if facility_type == "power_pole" or facility_type not in powered_templates:
            continue
        pose_idx = int(row["pose_idx"])
        candidates = {
            int(value)
            for value in coverers.get(facility_type, {}).get(pose_idx, [])
        }
        if not candidates & selected_poles:
            return False
    return True


def build_power_semantics(e001: Any, stack: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    master = e001.construct_master(stack, inputs)
    master.build()
    coverers = {
        str(template): {
            int(pose_idx): tuple(int(value) for value in values)
            for pose_idx, values in by_pose.items()
        }
        for template, by_pose in master._power_coverers_by_template_pose.items()
    }
    powered_templates = {str(value) for value in master._powered_templates}
    payload = {
        "build_seconds": time.monotonic() - started,
        "powered_templates": sorted(powered_templates),
        "coverer_template_count": len(coverers),
        "coverer_pose_count": sum(len(value) for value in coverers.values()),
        "coverer_digest": stable_digest(coverers),
    }
    del master
    gc.collect()
    return {
        "summary": payload,
        "coverers": coverers,
        "powered_templates": powered_templates,
    }


def candidate_morphology(context: Any) -> dict[str, Any]:
    free_cells = set(context.component_by_cell)
    adjacency = 0
    for x, y in free_cells:
        if (x + 1, y) in free_cells:
            adjacency += 1
        if (x, y + 1) in free_cells:
            adjacency += 1
    sizes = sorted(
        (len(cells) for cells in context.cells_by_component.values()), reverse=True
    )
    return {
        "occupied_cell_count": len(context.occupied_cells),
        "free_cell_count": len(free_cells),
        "free_adjacency_score": adjacency,
        "free_component_count": len(sizes),
        "largest_free_component": sizes[0] if sizes else 0,
        "component_sizes": sizes,
        "free_cell_set_digest": stable_digest(sorted(free_cells)),
    }


def make_candidate_solution(
    *,
    base_solution: Mapping[str, Mapping[str, Any]],
    target_instance_id: str,
    target_row: Mapping[str, Any],
    facility_type: str,
    pose_idx: int,
    pose: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    solution = {str(key): dict(value) for key, value in base_solution.items()}
    if facility_type == "power_pole":
        solution.pop(target_instance_id)
        new_instance_id = f"pose_optional::power_pole::{pose['pose_id']}"
        if new_instance_id in solution:
            raise RuntimeError(f"replacement pole already selected: {new_instance_id}")
        source = dict(target_row)
        source["bound_type"] = "exact_pose_optional"
        solution[new_instance_id] = replacement_row(
            source=source,
            pose=pose,
            pose_idx=pose_idx,
            instance_id=new_instance_id,
        )
    else:
        solution[target_instance_id] = replacement_row(
            source=target_row,
            pose=pose,
            pose_idx=pose_idx,
            instance_id=target_instance_id,
        )
    if sum(bool(row.get("is_mandatory")) for row in solution.values()) != 266:
        raise RuntimeError("candidate mandatory count drift")
    if sum(str(row.get("facility_type")) == "power_pole" for row in solution.values()) != 53:
        raise RuntimeError("candidate pole count drift")
    return solution


def enumerate_alternatives(
    *,
    target: Mapping[str, Any],
    base_solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    occupied: frozenset[tuple[int, int]],
    selected_poles: set[int],
    powered_templates: set[str],
    coverers: Mapping[str, Mapping[int, Sequence[int]]],
) -> list[dict[str, Any]]:
    source_ids = [str(value) for value in target["source_instance_ids"]]
    if not source_ids:
        raise RuntimeError(f"target has no source instance: {target['literal_key']}")
    target_instance_id = source_ids[0]
    target_row = base_solution.get(target_instance_id)
    if target_row is None:
        raise RuntimeError(f"target source is absent from E009: {target_instance_id}")
    facility_type = str(target_row["facility_type"])
    current_pose_idx = int(target_row["pose_idx"])
    if facility_type != str(target["facility_type"]) or current_pose_idx != int(
        target["pose_idx"]
    ):
        raise RuntimeError(f"target transport drift: {target['literal_key']}")
    current_cells = pose_cells(pools, facility_type, current_pose_idx)
    fixed_occupied = set(occupied - current_cells)
    pool = pools.get(facility_type)
    if not isinstance(pool, list):
        raise RuntimeError(f"missing facility pool: {facility_type}")

    alternatives: list[dict[str, Any]] = []
    for pose_idx, pose in enumerate(pool):
        if pose_idx == current_pose_idx:
            continue
        cells = pose_cells(pools, facility_type, pose_idx)
        if cells & fixed_occupied:
            continue
        candidate = make_candidate_solution(
            base_solution=base_solution,
            target_instance_id=target_instance_id,
            target_row=target_row,
            facility_type=facility_type,
            pose_idx=pose_idx,
            pose=pose,
        )
        candidate_poles = {
            int(row["pose_idx"])
            for row in candidate.values()
            if str(row.get("facility_type")) == "power_pole"
        }
        if len(candidate_poles) != len(selected_poles):
            raise RuntimeError("candidate pole set cardinality drift")
        if not all_powered_facilities_covered(
            solution=candidate,
            selected_poles=candidate_poles,
            powered_templates=powered_templates,
            coverers=coverers,
        ):
            continue
        alternatives.append(
            {
                "pose_idx": int(pose_idx),
                "pose_id": str(pose["pose_id"]),
                "anchor": json_safe(pose["anchor"]),
                "same_footprint": cells == current_cells,
                "occupied_cells": [list(cell) for cell in sorted(cells)],
                "solution": candidate,
            }
        )
    return alternatives


def screen_component_interface(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e001: Any,
    e002: Any,
) -> dict[str, Any]:
    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_binding_context import build_routing_binding_context
    from src.models.routing_subproblem import (
        RoutingPlacementCore,
        RoutingSubproblem,
        run_exact_routing_precheck,
    )
    from src.search.pr2_l0_fixed_witness_core import _routing_build_rejection

    routing_context = build_routing_binding_context(
        solution,
        inputs["pools"],
        GRID_W,
        GRID_H,
    )
    morphology = candidate_morphology(routing_context)
    build_started = time.monotonic()
    plan = inputs["plan"]
    generic = inputs["generic"]
    binding_model = PortBindingModel(
        placement_solution=solution,
        facility_pools=inputs["pools"],
        instances=inputs["instances"],
        project_root=HISTORY_ROOT,
        required_generic_outputs=generic.get("required_generic_outputs", {}),
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
        generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
        utility_operation_by_template=plan["utility_operation_by_template"],
        canonical_rules_payload=inputs["rules"],
        routing_context=routing_context,
    )
    binding_model.build()
    compiled, internals = e002.compile_guarded_interface(
        binding_model=binding_model,
        routing_context=routing_context,
        required_generic_inputs=generic.get("required_generic_inputs", {}),
    )
    build_seconds = time.monotonic() - build_started
    common = {
        "morphology": morphology,
        "build_seconds": build_seconds,
        "empty_filtered_domain_count": int(compiled["empty_filtered_domain_count"]),
        "empty_filtered_domains": json_safe(
            binding_model.empty_binding_domain_instances
        ),
        "filtered_binding_option_count": int(
            compiled["filtered_binding_option_count"]
        ),
        "front_blocked_patterns_pruned": int(
            compiled["routing_aware_filter_stats"]["front_blocked_patterns_pruned"]
        ),
        "generic_input_slot_count": int(compiled["generic_input_slot_count"]),
        "generic_output_slot_count": int(compiled["generic_output_slot_count"]),
        "duplicate_constraint_count": int(compiled["duplicate_constraint_count"]),
        "duplicate_fixed_contradictions": int(
            compiled["duplicate_fixed_contradictions"]
        ),
        "component_constraint_count": int(compiled["component_constraint_count"]),
        "model_variable_count": int(compiled["model_variable_count"]),
        "model_constraint_count": int(compiled["model_constraint_count"]),
    }
    if common["empty_filtered_domain_count"]:
        return {"status": "PORT_DOMAIN_EMPTY", **common}
    if common["duplicate_fixed_contradictions"]:
        return {"status": "DUPLICATE_FIXED_CONTRADICTION", **common}

    for guard in internals["guards"].values():
        binding_model.model.Add(guard == 1)
    solve_started = time.monotonic()
    binding_status = binding_model.solve(time_limit_seconds=BINDING_CAP_SECONDS)
    solve_seconds = time.monotonic() - solve_started
    solver = binding_model._solver
    common.update(
        {
            "binding_status": binding_status,
            "binding_solve_seconds": solve_seconds,
            "binding_wall_time": (
                float(solver.WallTime()) if solver is not None else 0.0
            ),
            "binding_branches": (
                int(solver.NumBranches()) if solver is not None else None
            ),
            "binding_conflicts": (
                int(solver.NumConflicts()) if solver is not None else None
            ),
        }
    )
    if binding_status != "FEASIBLE":
        return {
            "status": (
                "COMPONENT_INFEASIBLE"
                if binding_status == "INFEASIBLE"
                else "COMPONENT_UNKNOWN"
            ),
            **common,
        }

    selection = binding_model.extract_selection()
    port_specs = binding_model.extract_port_specs()
    placement_core = RoutingPlacementCore.from_occupied_cells(
        set(routing_context.occupied_cells),
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    precheck = run_exact_routing_precheck(
        placement_core=placement_core,
        port_specs=port_specs,
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    precheck_public = {
        key: value for key, value in precheck.items() if key != "_analysis"
    }
    common.update(
        {
            "selection_digest": stable_digest(selection),
            "port_specs_digest": stable_digest(port_specs),
            "port_count": len(port_specs),
            "ordinary_precheck": json_safe(precheck_public),
        }
    )
    if str(precheck.get("status")) != "feasible":
        return {"status": "COMPILER_PRECHECK_MISMATCH", **common}

    routing_model = RoutingSubproblem.from_placement_core(
        placement_core,
        port_specs,
        sorted({str(port["commodity"]) for port in port_specs}),
        domain_analysis=precheck.get("_analysis"),
    )
    routing_build_started = time.monotonic()
    routing_model.build()
    routing_build_seconds = time.monotonic() - routing_build_started
    rejection = _routing_build_rejection(routing_model.build_stats)
    common.update(
        {
            "routing_build_seconds": routing_build_seconds,
            "routing_build_stats": json_safe(routing_model.build_stats),
        }
    )
    if rejection is not None:
        return {
            "status": "EXACT_ROUTING_BUILD_REJECTED",
            "routing_build_rejection": json_safe(rejection),
            **common,
        }
    routing_started = time.monotonic()
    routing_status = routing_model.solve(time_limit=ROUTING_CAP_SECONDS)
    routing_seconds = time.monotonic() - routing_started
    common.update(
        {
            "routing_status": routing_status,
            "routing_solve_seconds": routing_seconds,
        }
    )
    if routing_status != "FEASIBLE":
        return {
            "status": (
                "EXACT_ROUTING_INFEASIBLE"
                if routing_status == "INFEASIBLE"
                else "EXACT_ROUTING_UNKNOWN"
            ),
            **common,
        }
    routes = routing_model.extract_routes()
    strict = e001.strict_non_ghost_terminal_validation(
        solution=solution,
        port_specs=port_specs,
        routes=routes,
        occupied_cells=set(routing_context.occupied_cells),
    )
    return {
        "status": (
            "ZERO_CONDITION_ROUTING_COMPLETE_RESEARCH_WITNESS"
            if strict["status"] == "PASS"
            else "STRICT_VALIDATOR_REJECTED"
        ),
        "routes_digest": stable_digest(routes),
        "route_record_count": len(routes),
        "strict_validator": json_safe(strict),
        **common,
    }


def arm_result_path(index: int) -> Path:
    return OUT / f"ARM_{index:02d}.json"


def evaluate_arm(
    *,
    index: int,
    target: Mapping[str, Any],
    base_solution: Mapping[str, Mapping[str, Any]],
    occupied: frozenset[tuple[int, int]],
    selected_poles: set[int],
    inputs: Mapping[str, Any],
    power: Mapping[str, Any],
    e001: Any,
    e002: Any,
    runner_sha256: str,
) -> dict[str, Any]:
    alternatives = enumerate_alternatives(
        target=target,
        base_solution=base_solution,
        pools=inputs["pools"],
        occupied=occupied,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    )
    candidate_results: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(alternatives, 1):
        interface = screen_component_interface(
            solution=candidate["solution"],
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        candidate_results.append(
            {
                "pose_idx": candidate["pose_idx"],
                "pose_id": candidate["pose_id"],
                "anchor": candidate["anchor"],
                "same_footprint": candidate["same_footprint"],
                "occupied_cells": candidate["occupied_cells"],
                "candidate_solution_digest": stable_digest(candidate["solution"]),
                "interface": interface,
            }
        )
        if candidate_index % 25 == 0 or str(interface["status"]).startswith(
            "ZERO_CONDITION_"
        ):
            print(
                json.dumps(
                    {
                        "event": "E014_ARM_PROGRESS",
                        "arm": index,
                        "candidate": candidate_index,
                        "candidate_total": len(alternatives),
                        "status": interface["status"],
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        if interface["status"] == "ZERO_CONDITION_ROUTING_COMPLETE_RESEARCH_WITNESS":
            break
        del candidate["solution"]
        if candidate_index % 20 == 0:
            gc.collect()

    status_counts = Counter(
        str(candidate["interface"]["status"]) for candidate in candidate_results
    )
    ranked = sorted(
        candidate_results,
        key=lambda row: (
            0
            if row["interface"]["status"]
            == "ZERO_CONDITION_ROUTING_COMPLETE_RESEARCH_WITNESS"
            else 1
            if row["interface"]["status"] in {
                "EXACT_ROUTING_INFEASIBLE",
                "EXACT_ROUTING_UNKNOWN",
                "EXACT_ROUTING_BUILD_REJECTED",
            }
            else 2
            if row["interface"]["status"] == "COMPONENT_INFEASIBLE"
            else 3,
            int(row["interface"].get("empty_filtered_domain_count", 0)),
            -int(row["interface"].get("filtered_binding_option_count", 0)),
            int(row["interface"]["morphology"]["free_component_count"]),
            -int(row["interface"]["morphology"]["free_adjacency_score"]),
            int(row["pose_idx"]),
        ),
    )
    return {
        "schema": "zmd_zero_condition_e014_arm_v1",
        "created_at_utc": utc_now(),
        "runner_sha256": runner_sha256,
        "arm_index": index,
        "target": json_safe(target),
        "alternative_count": len(alternatives),
        "same_footprint_alternative_count": sum(
            bool(candidate["same_footprint"]) for candidate in alternatives
        ),
        "footprint_changing_alternative_count": sum(
            not bool(candidate["same_footprint"]) for candidate in alternatives
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "candidate_results": candidate_results,
        "ranked_candidate_pose_indices": [
            int(candidate["pose_idx"]) for candidate in ranked
        ],
        "top_candidates": ranked[:10],
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e001 = import_module("zmd_e014_e001", E001_RUNNER)
    e002 = import_module("zmd_e014_e002", E002_RUNNER)
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    base_solution = reconstruct_solution()
    occupied, _owner_by_cell = base_occupancy(base_solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in base_solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = build_power_semantics(e001, stack, inputs)
    if not all_powered_facilities_covered(
        solution=base_solution,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    ):
        raise RuntimeError("E009 base solution fails reconstructed power semantics")

    e013 = load_json(E013_RESULT)
    portfolio = next(
        row
        for row in e013["max_coverage_by_literal_budget"]
        if int(row["budget"]) == 16
    )["selected_literal_details"]
    if len(portfolio) != 16:
        raise RuntimeError("E013 budget-16 portfolio drift")

    OUT.mkdir(parents=True, exist_ok=True)
    arms: list[dict[str, Any]] = []
    for index, target in enumerate(portfolio, 1):
        path = arm_result_path(index)
        if path.exists():
            arm = load_json(path)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E014 arm checkpoint: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E014_ARM_START",
                        "arm": index,
                        "total": len(portfolio),
                        "literal": target["literal_key"],
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            arm = evaluate_arm(
                index=index,
                target=target,
                base_solution=base_solution,
                occupied=occupied,
                selected_poles=selected_poles,
                inputs=inputs,
                power=power,
                e001=e001,
                e002=e002,
                runner_sha256=runner_sha256,
            )
            dump_exclusive(path, arm)
        arms.append(arm)
        print(
            json.dumps(
                {
                    "event": "E014_ARM_DONE",
                    "arm": index,
                    "alternatives": arm["alternative_count"],
                    "status_counts": arm["status_counts"],
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if any(
            candidate["interface"]["status"]
            == "ZERO_CONDITION_ROUTING_COMPLETE_RESEARCH_WITNESS"
            for candidate in arm["candidate_results"]
        ):
            break

    all_candidates = [
        candidate
        for arm in arms
        for candidate in arm["candidate_results"]
    ]
    aggregate_status = Counter(
        str(candidate["interface"]["status"]) for candidate in all_candidates
    )
    witnesses = [
        {
            "arm_index": arm["arm_index"],
            "target_literal": arm["target"]["literal_key"],
            "candidate": candidate,
        }
        for arm in arms
        for candidate in arm["candidate_results"]
        if candidate["interface"]["status"]
        == "ZERO_CONDITION_ROUTING_COMPLETE_RESEARCH_WITNESS"
    ]
    component_feasible = [
        {
            "arm_index": arm["arm_index"],
            "target_literal": arm["target"]["literal_key"],
            "candidate": candidate,
        }
        for arm in arms
        for candidate in arm["candidate_results"]
        if candidate["interface"]["status"]
        in {
            "EXACT_ROUTING_INFEASIBLE",
            "EXACT_ROUTING_UNKNOWN",
            "EXACT_ROUTING_BUILD_REJECTED",
            "ZERO_CONDITION_ROUTING_COMPLETE_RESEARCH_WITNESS",
            "STRICT_VALIDATOR_REJECTED",
        }
    ]
    locked_arms = [
        int(arm["arm_index"]) for arm in arms if int(arm["alternative_count"]) == 0
    ]
    if witnesses:
        verdict = "ZERO_CONDITION_ROUTING_COMPLETE_RESEARCH_WITNESS"
    elif component_feasible:
        verdict = "ONE_LITERAL_COMPONENT_FEASIBLE_CANDIDATE"
    elif locked_arms:
        verdict = "PARTIAL_MOBILITY_COMPONENT_WALL_PERSISTS"
    else:
        verdict = "PORTFOLIO_MOBILE_COMPONENT_WALL_PERSISTS"

    return {
        "schema": "zmd_zero_condition_e014_fixed_outside_mobility_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "power_semantics": power["summary"],
        "base": {
            "selected_placement_count": len(base_solution),
            "mandatory_count": 266,
            "power_pole_count": len(selected_poles),
            "occupied_cell_count": len(occupied),
            "solution_digest": stable_digest(base_solution),
        },
        "portfolio_size": len(portfolio),
        "completed_arm_count": len(arms),
        "locked_arms": locked_arms,
        "total_alternative_count": sum(
            int(arm["alternative_count"]) for arm in arms
        ),
        "aggregate_status_counts": dict(sorted(aggregate_status.items())),
        "component_feasible_candidates": component_feasible,
        "routing_complete_witnesses": witnesses,
        "arms": [
            {
                key: value
                for key, value in arm.items()
                if key != "candidate_results"
            }
            for arm in arms
        ],
        "arm_checkpoint_paths": [
            str(arm_result_path(int(arm["arm_index"])).relative_to(ROOT))
            for arm in arms
        ],
        "truth_boundary": (
            "Exhaustive one-literal fixed-outside placement/power alternatives "
            "for completed E013 portfolio arms. Joint moves remain outside scope."
        ),
        "routing_solver_run": bool(component_feasible),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E014 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "completed_arm_count": result["completed_arm_count"],
                    "total_alternative_count": result["total_alternative_count"],
                    "aggregate_status_counts": result["aggregate_status_counts"],
                    "component_feasible_candidate_count": len(
                        result["component_feasible_candidates"]
                    ),
                    "routing_complete_witness_count": len(
                        result["routing_complete_witnesses"]
                    ),
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e014_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        OUT.mkdir(parents=True, exist_ok=True)
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
