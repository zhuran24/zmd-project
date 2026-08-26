#!/usr/bin/env python3
"""E027: final fixed-outside unary discriminator on the objective-168 state."""

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
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E027_final_unary_discriminator/run-002"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E024_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/RESULT.json"
)
E024_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/BEST_BRANCH_CHILD_ASSIGNMENT.json"
)
E024_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/BEST_BRANCH_CHILD_LAYOUT.json"
)
E025_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E025_live_beam_residual_surface/run-004/RESULT.json"
)
E026_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E026_common_packaging_action/run-003/RESULT.json"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
)
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E004_component_mismatch_atlas/run_e004.py"
)
E014_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E014_fixed_outside_mobility/run_e014.py"
)
E015_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E015_shared_binding_gradient/run_e015.py"
)
E017_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E017_third_member_portfolio/run_e017.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "262700",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E024_RESULT: "a0a69a8c0f9c7f59d8924f9f13e0e277fe5f254a35aeaeb34c6c721becd4d17f",
    E024_ASSIGNMENT: "4f49e6dc8aaaf8e677596cd631f0eb34fc735612a4ff5a3e09dbb50836633018",
    E024_LAYOUT: "c05ae6030d9ee8154cb3074b980ba34c438696ddf7aed2521ea1ba680ddb23ba",
    E025_RESULT: "3a2d076ba283ccfaf946c772cbbc25a530b14849bcd433516965edc3b7670c5a",
    E026_RESULT: "7dbb42b6c255fbc89a6a904364b861a7ef28eb8487ccabbfc305dbc291c8456e",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E017_RUNNER: "106d7ee8830d3a45bf4115e064e65e059fdd86c4bd4b5c2acddaff55e203a2e0",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
    HISTORY_ROOT / "rules/canonical_rules.json": (
        "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0"
    ),
    HISTORY_ROOT / "rules/preprocess_plan.json": (
        "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee"
    ),
}

PARENT_OBJECTIVE = 168
TARGET_LITERAL = (
    "mandatory::group::manufacturing_3x3::crusher_sandleaf::3::2155"
)
MATERIAL_IMPROVEMENT = 2


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
        raise RuntimeError("E027 must run on research/main")
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
            raise RuntimeError(
                f"frozen identity drift for {path}: {actual} != {expected}"
            )
    e024 = load_json(E024_RESULT)
    if e024.get("verdict") != "BRANCH_SPECIFIC_LEADER_IMPROVES":
        raise RuntimeError("E024 verdict drift")
    if int(e024["best_child"]["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E024 objective drift")
    e025 = load_json(E025_RESULT)
    target = e025["decision_reading"]["selected_objective_168_specific_action"]
    if str(target["literal_key"]) != TARGET_LITERAL:
        raise RuntimeError("E025 selected objective-168 action drift")
    e026 = load_json(E026_RESULT)
    if e026.get("verdict") != "COMMON_PACKAGING_ACTION_STATIC_DOMAIN_REJECTED":
        raise RuntimeError("E026 trigger verdict drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def load_parent_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E024_ASSIGNMENT)
    layout = load_json(E024_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E024 assignment/layout structure drift")
    solution = {
        str(instance_id): dict(row)
        for instance_id, row in raw.items()
        if isinstance(row, Mapping)
    }
    layout_solution = {
        str(row["instance_id"]): dict(row)
        for row in placements
        if isinstance(row, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E024 assignment/layout content drift")
    e024 = load_json(E024_RESULT)
    if stable_digest(solution) != str(e024["best_child"]["placement_digest"]):
        raise RuntimeError("E024 parent placement digest drift")
    if len(solution) != 319:
        raise RuntimeError(f"E024 parent placement count drift: {len(solution)}")
    return solution


def materialize_shared_endpoint(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e004: Any,
    e015: Any,
    random_seed: int,
) -> dict[str, Any]:
    from ortools.sat.python import cp_model
    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_binding_context import build_routing_binding_context
    from src.models.routing_subproblem import (
        RoutingPlacementCore,
        run_exact_routing_precheck,
    )

    routing_context = build_routing_binding_context(
        solution,
        inputs["pools"],
        70,
        70,
    )
    plan = inputs["plan"]
    generic = inputs["generic"]
    build_started = time.monotonic()
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
    if binding_model.empty_binding_domain_instances:
        raise RuntimeError("E027 best candidate unexpectedly has an empty binding domain")
    compiled = e015.compile_shared_objective(
        binding_model=binding_model,
        routing_context=routing_context,
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        e004=e004,
    )
    if compiled["duplicate_fixed_contradictions"]:
        raise RuntimeError("E027 best candidate has a fixed terminal contradiction")
    build_seconds = time.monotonic() - build_started

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 8
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(random_seed)
    solve_started = time.monotonic()
    status = solver.Solve(binding_model.model)
    solve_seconds = time.monotonic() - solve_started
    status_name = solver.StatusName(status)
    if status != cp_model.OPTIMAL:
        raise RuntimeError(f"E027 endpoint materialization not OPTIMAL: {status_name}")

    binding_model._solver = solver
    binding_model._status = status
    selection = binding_model.extract_selection()
    port_specs = binding_model.extract_port_specs()
    per_commodity: dict[str, int] = {}
    global_presence: dict[str, dict[str, int]] = {}
    selected_components: dict[str, Any] = {}
    mismatch_boundaries: dict[str, Any] = {}
    for commodity in compiled["commodities"]:
        per_commodity[commodity] = sum(
            int(solver.Value(variable))
            for variable in compiled["mismatch_vars"][commodity].values()
        )
        global_presence[commodity] = {
            "source": int(solver.Value(compiled["source_global"][commodity])),
            "sink": int(solver.Value(compiled["sink_global"][commodity])),
        }
        selected = e004.selected_component_sets(
            commodity=commodity,
            port_specs=port_specs,
            routing_context=routing_context,
        )
        if len(selected["mismatch_components"]) != per_commodity[commodity]:
            raise RuntimeError(f"E027 selected-component mismatch for {commodity}")
        selected_components[commodity] = selected
        mismatch_boundaries[commodity] = [
            e004.boundary_profile(
                component=int(component),
                routing_context=routing_context,
                solution=solution,
            )
            for component in selected["mismatch_components"]
        ]

    objective = int(round(solver.ObjectiveValue()))
    if objective != sum(per_commodity.values()):
        raise RuntimeError("E027 endpoint objective/per-commodity sum mismatch")
    if any(value != {"source": 1, "sink": 1} for value in global_presence.values()):
        raise RuntimeError("E027 endpoint lacks a required source or sink")

    placement_core = RoutingPlacementCore.from_occupied_cells(
        set(routing_context.occupied_cells),
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    precheck = run_exact_routing_precheck(
        placement_core=placement_core,
        port_specs=port_specs,
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    disconnected = {
        str(row.get("commodity", ""))
        for row in precheck.get("disconnected_commodities", [])
    }
    positive = {
        commodity for commodity, value in per_commodity.items() if int(value) > 0
    }
    if disconnected != positive:
        raise RuntimeError("E027 endpoint/precheck commodity mismatch")

    return {
        "schema": "zmd_zero_condition_e027_materialized_binding_endpoint_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": status_name,
        "objective": objective,
        "best_bound": float(solver.BestObjectiveBound()),
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "selection": json_safe(selection),
        "selection_digest": stable_digest(selection),
        "port_specs": json_safe(port_specs),
        "port_specs_digest": stable_digest(port_specs),
        "per_commodity": per_commodity,
        "global_presence": global_presence,
        "selected_components": json_safe(selected_components),
        "mismatch_boundaries": json_safe(mismatch_boundaries),
        "positive_commodity_count": len(positive),
        "zero_mismatch_commodities": sorted(set(per_commodity) - positive),
        "morphology": e015.fixed_occupancy_summary(routing_context),
        "filtered_binding_option_count": sum(
            len(domain) for domain in binding_model.binding_domains.values()
        ),
        "routing_aware_filter_stats": json_safe(
            binding_model.routing_aware_filter_stats
        ),
        "generic_input_slot_count": len(binding_model.generic_input_slots),
        "generic_output_slot_count": len(binding_model.generic_output_slots),
        "compile": {
            key: value
            for key, value in compiled.items()
            if key
            not in {
                "mismatch_vars",
                "source_presence",
                "sink_presence",
                "source_global",
                "sink_global",
                "support_summary",
            }
        },
        "ordinary_precheck": json_safe(
            {key: value for key, value in precheck.items() if key != "_analysis"}
        ),
        "truth_boundary": (
            "A fully materialized exact shared-binding endpoint for one fixed "
            "placement. It is not an exact-routing or whole-layout witness."
        ),
        "ledger_effect": "none",
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e001 = import_module("zmd_e027_e001", E001_RUNNER)
    e004 = import_module("zmd_e027_e004", E004_RUNNER)
    e014 = import_module("zmd_e027_e014", E014_RUNNER)
    e015 = import_module("zmd_e027_e015", E015_RUNNER)
    e017 = import_module("zmd_e027_e017", E017_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent_solution = load_parent_solution()
    target = dict(
        load_json(E025_RESULT)["decision_reading"][
            "selected_objective_168_specific_action"
        ]
    )
    if str(target["literal_key"]) != TARGET_LITERAL:
        raise RuntimeError("E027 target payload drift")
    source_id = str(target["source_instance_ids"][0])
    if int(parent_solution[source_id]["pose_idx"]) != int(target["pose_idx"]):
        raise RuntimeError("E027 target pose is not selected in the parent")

    power = e014.build_power_semantics(e001, stack, inputs)
    occupied, _owner_by_cell = e014.base_occupancy(parent_solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in parent_solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    if not e014.all_powered_facilities_covered(
        solution=parent_solution,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    ):
        raise RuntimeError("E027 parent fails exact power semantics")

    arm_path = OUT / "ARM.json"
    arm = e017.evaluate_arm(
        index=27,
        target=target,
        pair_solution=parent_solution,
        occupied=occupied,
        selected_poles=selected_poles,
        inputs=inputs,
        power=power,
        e004=e004,
        e014=e014,
        e015=e015,
        runner_sha256=runner_sha256,
    )
    arm["schema"] = "zmd_zero_condition_e027_final_unary_arm_v1"
    arm["parent_objective"] = PARENT_OBJECTIVE
    dump_exclusive(arm_path, arm)

    optimal = [
        record
        for record in arm["candidate_records"]
        if str(record["shared_binding"]["status"]) == "OPTIMAL"
    ]
    status_counts = dict(arm["status_counts"])
    if not optimal:
        return {
            "schema": "zmd_zero_condition_e027_final_unary_discriminator_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "FINAL_UNARY_NO_BASE_FEASIBLE_CHILD",
            "identity": identity,
            "power_semantics": power["summary"],
            "parent_objective": PARENT_OBJECTIVE,
            "target": target,
            "alternative_count": int(arm["alternative_count"]),
            "status_counts": status_counts,
            "arm_path": str(arm_path.relative_to(ROOT)),
            "routing": {"status": "NOT_REACHED_NO_OPTIMAL_CHILD"},
            "decision": "TRANSITION_TO_SIMULTANEOUS_NEIGHBORHOOD",
            "truth_boundary": "One target literal with all outside placements fixed.",
            "ledger_effect": "none",
        }

    ranked = sorted(
        optimal,
        key=lambda record: (
            int(record["shared_binding"]["objective"]),
            -int(record["shared_binding"]["filtered_binding_option_count"]),
            int(record["shared_binding"]["morphology"]["free_component_count"]),
            int(record["pose_idx"]),
        ),
    )
    best = ranked[0]
    best_solution = e017.reconstruct_candidate(
        arm=arm,
        record=best,
        pair_solution=parent_solution,
        inputs=inputs,
        e014=e014,
    )
    endpoint = materialize_shared_endpoint(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=267999,
    )
    if int(endpoint["objective"]) != int(best["shared_binding"]["objective"]):
        raise RuntimeError("E027 materialized endpoint objective drift")

    assignment_path = OUT / "BEST_CHILD_ASSIGNMENT.json"
    layout_path = OUT / "BEST_CHILD_LAYOUT.json"
    endpoint_path = OUT / "BEST_CHILD_ENDPOINT.json"
    dump_exclusive(
        assignment_path,
        {
            "schema": "zmd_zero_condition_e027_best_child_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "parent_objective": PARENT_OBJECTIVE,
            "target_literal": TARGET_LITERAL,
            "replacement_pose_idx": int(best["pose_idx"]),
            "shared_mismatch_objective": int(endpoint["objective"]),
            "solution": best_solution,
        },
    )
    dump_exclusive(layout_path, e001.solution_layout(best_solution))
    dump_exclusive(endpoint_path, endpoint)

    objective = int(endpoint["objective"])
    delta = objective - PARENT_OBJECTIVE
    if objective == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=import_module(
                "zmd_e027_e002",
                ROOT
                / "research_lab/campaigns/zero_condition/experiments/E002_component_commodity_core/run_component_core.py",
            ),
        )
        verdict = "FINAL_UNARY_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif delta <= -MATERIAL_IMPROVEMENT:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "FINAL_UNARY_MATERIAL_IMPROVEMENT"
        decision = "RETAIN_CHILD_AND_RECOMPUTE_RESIDUAL_SURFACE"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "SERIAL_UNARY_SATURATION_SIGNAL"
        decision = "TRANSITION_TO_SIMULTANEOUS_NEIGHBORHOOD"

    distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal
    )
    return {
        "schema": "zmd_zero_condition_e027_final_unary_discriminator_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "power_semantics": power["summary"],
        "parent_objective": PARENT_OBJECTIVE,
        "target": target,
        "alternative_count": int(arm["alternative_count"]),
        "status_counts": status_counts,
        "optimal_candidate_count": len(optimal),
        "objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "best_child": {
            "objective": objective,
            "delta_from_parent": delta,
            "replacement_pose_idx": int(best["pose_idx"]),
            "replacement_pose_id": str(best["pose_id"]),
            "placement_digest": stable_digest(best_solution),
            "binding_selection_digest": endpoint["selection_digest"],
            "per_commodity": endpoint["per_commodity"],
            "positive_commodity_count": endpoint["positive_commodity_count"],
            "zero_mismatch_commodities": endpoint["zero_mismatch_commodities"],
            "morphology": endpoint["morphology"],
            "filtered_binding_option_count": endpoint[
                "filtered_binding_option_count"
            ],
            "assignment_path": str(assignment_path.relative_to(ROOT)),
            "assignment_sha256": sha256_file(assignment_path),
            "layout_path": str(layout_path.relative_to(ROOT)),
            "layout_sha256": sha256_file(layout_path),
            "endpoint_path": str(endpoint_path.relative_to(ROOT)),
            "endpoint_sha256": sha256_file(endpoint_path),
        },
        "arm_path": str(arm_path.relative_to(ROOT)),
        "routing": routing,
        "decision": decision,
        "truth_boundary": (
            "Exhaustive fixed-outside alternatives for one objective-168 current "
            "literal. Positive mismatch remains only a necessary coarse-topology "
            "distance, not a routing or whole-layout result."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E027 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "parent_objective": result["parent_objective"],
                    "alternative_count": result["alternative_count"],
                    "status_counts": result["status_counts"],
                    "best_child": result.get("best_child"),
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
            "schema": "zmd_zero_condition_e027_final_unary_failure_v1",
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
