#!/usr/bin/env python3
"""E034: cohabit bounded operation assignment and exact binding variables."""

from __future__ import annotations

from collections import defaultdict
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
OUT = ROOT / "research_lab/local/zero_condition/E034_joint_assignment_binding/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
JOINT_WITNESS_PATH = OUT / "JOINT_WITNESS.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_LAYOUT.json"
BEST_ENDPOINT_PATH = OUT / "BEST_ENDPOINT.json"

E031_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/RESULT.json"
)
E033_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E033_tied_state_action_replay/run-001/RESULT.json"
)
FIRST_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E033_tied_state_action_replay/run-001/FIRST_COMMON_ASSIGNMENT.json"
)
FIRST_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E033_tied_state_action_replay/run-001/FIRST_COMMON_ENDPOINT.json"
)
SECOND_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E033_tied_state_action_replay/run-001/SECOND_COMMON_ASSIGNMENT.json"
)
SECOND_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E033_tied_state_action_replay/run-001/SECOND_COMMON_ENDPOINT.json"
)

E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
)
E002_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E002_component_commodity_core/run_component_core.py"
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
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E027_final_unary_discriminator/run_e027.py"
)
E031_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E031_bounded_assignment_neighborhood/run_e031.py"
)
E033_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E033_tied_state_action_replay/run_e033.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "264000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E031_RESULT: "a6efad78e382133b0b5b2492bbb048e6e15726294ec3940c0a777bceecd791b2",
    E033_RESULT: "0928591c006dc70fe4fe2250e2161d8e3261bc121c0f196822aa390b583b8932",
    FIRST_ASSIGNMENT: "b64c0ba2e2372d2d0b7cf0d2c73a53bb98cd5002e8ac703d4a3e85255ba0035f",
    FIRST_ENDPOINT: "80669d65d1039aa896a6cb8d35c59593d1ac57b285a100058d967c46c72974b3",
    SECOND_ASSIGNMENT: "aaa21b02f772a955921e0e8e7fefa467ae5a84c9cb834d2b31de9278320cbeaa",
    SECOND_ENDPOINT: "ab184e28e69326b40f1e5d973d64096ec3436b83fe890390b1804a22ee0f7e30",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    E031_RUNNER: "ba35d569dc1a514da83b46721cb53c3f25386b2d776c70ac4cfae7f7c4d29b18",
    E033_RUNNER: "8b17f6678a313ccf009d02f624dcb702c6cc26def2b99b6a3082a2f146fffedf",
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

PARENT_OBJECTIVE = 160
TARGET_FACILITY_TYPE = "manufacturing_3x3"
CALIBRATION_SECONDS = 45.0
FREE_SOLVE_SECONDS = 180.0
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
        raise RuntimeError("E034 must run on research/main")
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
    e031 = load_json(E031_RESULT)
    if e031.get("verdict") != "BOUNDED_ASSIGNMENT_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E031 trigger verdict drift")
    if e031.get("exchangeability_audit", {}).get("status") != "PASS":
        raise RuntimeError("E031 exchangeability audit drift")
    e033 = load_json(E033_RESULT)
    if e033.get("verdict") != "TIED_STATE_ACTION_FAMILY_SATURATION_SIGNAL":
        raise RuntimeError("E033 stop verdict drift")
    if e033.get("decision") != "COHABIT_OPERATION_ASSIGNMENT_AND_BINDING":
        raise RuntimeError("E033 decision drift")
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


def solution_from_assignment(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    raw = payload.get("solution")
    if not isinstance(raw, Mapping) or len(raw) != 319:
        raise RuntimeError(f"assignment solution drift: {path}")
    return {
        str(instance_id): dict(row)
        for instance_id, row in raw.items()
        if isinstance(row, Mapping)
    }


def selected_neighborhood() -> dict[str, Any]:
    result = load_json(E031_RESULT)
    matches = [
        dict(row)
        for row in result["neighborhoods"]
        if str(row["facility_type"]) == TARGET_FACILITY_TYPE
    ]
    if len(matches) != 1:
        raise RuntimeError(f"E034 3x3 neighborhood count drift: {len(matches)}")
    neighborhood = matches[0]
    if int(neighborhood["selected_literal_count"]) != 5:
        raise RuntimeError("E034 neighborhood width drift")
    if int(neighborhood["semantic_permutation_count_including_identity"]) != 60:
        raise RuntimeError("E034 semantic permutation count drift")
    return neighborhood


def selected_instance_ids(neighborhood: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for payload in neighborhood["selected_literal_payloads"]:
        source_ids = [str(value) for value in payload["source_instance_ids"]]
        if len(source_ids) != 1:
            raise RuntimeError("E034 footprint lacks one concrete source")
        ids.append(source_ids[0])
    if len(ids) != len(set(ids)):
        raise RuntimeError("E034 selected instance alias")
    return ids


def operation_assignment_for_solution(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    neighborhood: Mapping[str, Any],
    selected_ids: set[str],
) -> tuple[str, ...]:
    operation_by_pose: dict[int, str] = {}
    seen_ids: set[str] = set()
    pose_set = {
        int(payload["pose_idx"])
        for payload in neighborhood["selected_literal_payloads"]
    }
    for instance_id in selected_ids:
        row = solution.get(instance_id)
        if row is None:
            raise RuntimeError(f"E034 selected instance absent: {instance_id}")
        pose_idx = int(row["pose_idx"])
        if pose_idx not in pose_set:
            raise RuntimeError(
                f"E034 selected instance left bounded footprints: {instance_id}@{pose_idx}"
            )
        if pose_idx in operation_by_pose:
            raise RuntimeError(f"E034 duplicate selected footprint: {pose_idx}")
        operation_by_pose[pose_idx] = str(row["operation_type"])
        seen_ids.add(instance_id)
    if seen_ids != selected_ids or set(operation_by_pose) != pose_set:
        raise RuntimeError("E034 bounded footprint coverage drift")
    return tuple(
        operation_by_pose[int(payload["pose_idx"])]
        for payload in neighborhood["selected_literal_payloads"]
    )


def realize_assignment(
    *,
    parent: Mapping[str, Mapping[str, Any]],
    neighborhood: Mapping[str, Any],
    operation_by_destination: Sequence[str],
    selected_ids: set[str],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    payloads = [dict(row) for row in neighborhood["selected_literal_payloads"]]
    if len(payloads) != len(operation_by_destination):
        raise RuntimeError("E034 assignment width drift")
    source_ids_by_operation: dict[str, list[str]] = defaultdict(list)
    for instance_id in selected_ids:
        source_ids_by_operation[str(parent[instance_id]["operation_type"])].append(
            instance_id
        )
    destinations_by_operation: dict[str, list[int]] = defaultdict(list)
    for index, operation in enumerate(operation_by_destination):
        destinations_by_operation[str(operation)].append(index)
    if {
        operation: len(ids)
        for operation, ids in source_ids_by_operation.items()
    } != {
        operation: len(indices)
        for operation, indices in destinations_by_operation.items()
    }:
        raise RuntimeError("E034 operation multiset drift during realization")

    child = {str(key): dict(value) for key, value in parent.items()}
    assigned: set[str] = set()
    for operation in sorted(source_ids_by_operation):
        source_ids = sorted(source_ids_by_operation[operation])
        destinations = sorted(destinations_by_operation[operation])
        for source_id, destination_index in zip(source_ids, destinations, strict=True):
            payload = payloads[destination_index]
            pose_idx = int(payload["pose_idx"])
            pose = pools[TARGET_FACILITY_TYPE][pose_idx]
            child[source_id] = e014.replacement_row(
                source=parent[source_id],
                pose=pose,
                pose_idx=pose_idx,
                instance_id=source_id,
            )
            assigned.add(source_id)
    if assigned != selected_ids:
        raise RuntimeError("E034 concrete assignment coverage drift")
    return child


def add_hints(
    *,
    binding_model: Any,
    y_vars: Mapping[tuple[int, str], Any],
    z_vars: Mapping[tuple[int, str, int], Any],
    warm_solution: Mapping[str, Mapping[str, Any]],
    warm_endpoint: Mapping[str, Any],
    neighborhood: Mapping[str, Any],
    selected_ids: set[str],
) -> dict[str, Any]:
    operation_by_destination = operation_assignment_for_solution(
        solution=warm_solution,
        neighborhood=neighborhood,
        selected_ids=selected_ids,
    )
    selection = warm_endpoint.get("selection", {})
    binding_choice = dict(selection.get("binding_choice", {}))
    hinted = 0

    for (destination, operation), variable in y_vars.items():
        binding_model.model.AddHint(
            variable,
            int(operation_by_destination[destination] == operation),
        )
        hinted += 1

    selected_by_pose = {
        int(warm_solution[instance_id]["pose_idx"]): instance_id
        for instance_id in selected_ids
    }
    for destination, payload in enumerate(neighborhood["selected_literal_payloads"]):
        pose_idx = int(payload["pose_idx"])
        instance_id = selected_by_pose[pose_idx]
        operation = str(warm_solution[instance_id]["operation_type"])
        selected_pattern = binding_choice.get(instance_id)
        if selected_pattern is None:
            continue
        for (row_destination, row_operation, pattern_index), variable in z_vars.items():
            if row_destination == destination and row_operation == operation:
                binding_model.model.AddHint(
                    variable,
                    int(pattern_index == int(selected_pattern)),
                )
                hinted += 1

    for instance_id, vars_by_idx in binding_model.binding_vars.items():
        if instance_id.startswith("joint::"):
            continue
        selected_pattern = binding_choice.get(instance_id)
        if selected_pattern is None:
            continue
        for pattern_index, variable in vars_by_idx.items():
            binding_model.model.AddHint(
                variable,
                int(int(pattern_index) == int(selected_pattern)),
            )
            hinted += 1
    for slot_id, vars_by_commodity in binding_model.generic_input_vars.items():
        selected = selection.get("generic_inputs", {}).get(slot_id)
        if selected is None:
            continue
        for commodity, variable in vars_by_commodity.items():
            binding_model.model.AddHint(variable, int(commodity == selected))
            hinted += 1
    for slot_id, vars_by_commodity in binding_model.generic_output_vars.items():
        selected = selection.get("generic_outputs", {}).get(slot_id)
        if selected is None:
            continue
        for commodity, variable in vars_by_commodity.items():
            binding_model.model.AddHint(variable, int(commodity == selected))
            hinted += 1
    return {
        "hint_literal_count": hinted,
        "operation_by_destination": list(operation_by_destination),
        "warm_selection_digest": warm_endpoint.get("selection_digest"),
    }


def build_joint_model(
    *,
    full_solution: Mapping[str, Mapping[str, Any]],
    warm_endpoint: Mapping[str, Any],
    fixed_assignment: Sequence[str] | None,
    inputs: Mapping[str, Any],
    neighborhood: Mapping[str, Any],
    selected_ids: set[str],
    e004: Any,
    e015: Any,
) -> dict[str, Any]:
    from src.models.binding_subproblem import PortBindingModel
    from src.models.port_binding import (
        enumerate_pose_level_port_bindings_with_cache_info,
        supports_exact_pose_level_binding,
    )
    from src.models.routing_binding_context import build_routing_binding_context

    routing_context = build_routing_binding_context(
        full_solution,
        inputs["pools"],
        70,
        70,
    )
    outside_solution = {
        instance_id: dict(row)
        for instance_id, row in full_solution.items()
        if instance_id not in selected_ids
    }
    plan = inputs["plan"]
    generic = inputs["generic"]
    binding_model = PortBindingModel(
        placement_solution=outside_solution,
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
    binding_model.build(use_overload_separation=False)
    if binding_model.empty_binding_domain_instances:
        raise RuntimeError(
            "E034 outside fixed model has an empty binding domain: "
            f"{binding_model.empty_binding_domain_instances}"
        )

    operations = sorted(str(key) for key in neighborhood["operation_multiset"])
    counts = {
        str(key): int(value)
        for key, value in neighborhood["operation_multiset"].items()
    }
    for operation in operations:
        if not supports_exact_pose_level_binding(operation):
            raise RuntimeError(f"E034 operation lacks exact pose binding: {operation}")
        if int(plan["generic_input_slots_by_operation"].get(operation, 0)) != 0:
            raise RuntimeError(f"E034 moving operation has generic inputs: {operation}")
        if int(plan["generic_output_slots_by_operation"].get(operation, 0)) != 0:
            raise RuntimeError(f"E034 moving operation has generic outputs: {operation}")

    y_vars: dict[tuple[int, str], Any] = {}
    z_vars: dict[tuple[int, str, int], Any] = {}
    domain_stats: list[dict[str, Any]] = []
    payloads = [dict(row) for row in neighborhood["selected_literal_payloads"]]
    for destination, payload in enumerate(payloads):
        pose_idx = int(payload["pose_idx"])
        pose = inputs["pools"][TARGET_FACILITY_TYPE][pose_idx]
        for operation in operations:
            y = binding_model.model.NewBoolVar(
                f"e034_assign_{destination}_{operation}"
            )
            y_vars[(destination, operation)] = y
            raw_domains, _cache_hit = enumerate_pose_level_port_bindings_with_cache_info(
                operation,
                pose,
            )
            virtual_owner = f"joint::{destination:02d}::{operation}"
            domains = binding_model._filter_pose_binding_domain(
                list(raw_domains),
                virtual_owner,
            )
            row = {
                "destination": destination,
                "pose_idx": pose_idx,
                "pose_id": str(pose.get("pose_id", "")),
                "operation": operation,
                "raw_pattern_count": len(raw_domains),
                "filtered_pattern_count": len(domains),
                "virtual_owner": virtual_owner,
            }
            domain_stats.append(row)
            if not domains:
                binding_model.model.Add(y == 0)
                continue
            binding_model.binding_domains[virtual_owner] = domains
            vars_by_idx: dict[int, Any] = {}
            for pattern_index in range(len(domains)):
                variable = binding_model.model.NewBoolVar(
                    f"e034_bind_{destination}_{operation}_{pattern_index}"
                )
                vars_by_idx[pattern_index] = variable
                z_vars[(destination, operation, pattern_index)] = variable
            binding_model.binding_vars[virtual_owner] = vars_by_idx
            binding_model.model.Add(sum(vars_by_idx.values()) == y)

    for destination in range(len(payloads)):
        binding_model.model.Add(
            sum(y_vars[(destination, operation)] for operation in operations) == 1
        )
    for operation in operations:
        binding_model.model.Add(
            sum(y_vars[(destination, operation)] for destination in range(len(payloads)))
            == counts[operation]
        )
    if fixed_assignment is not None:
        if len(fixed_assignment) != len(payloads):
            raise RuntimeError("E034 fixed assignment width drift")
        for destination, selected_operation in enumerate(fixed_assignment):
            for operation in operations:
                binding_model.model.Add(
                    y_vars[(destination, operation)]
                    == int(operation == str(selected_operation))
                )

    compiled = e015.compile_shared_objective(
        binding_model=binding_model,
        routing_context=routing_context,
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        e004=e004,
    )
    hint_stats = add_hints(
        binding_model=binding_model,
        y_vars=y_vars,
        z_vars=z_vars,
        warm_solution=full_solution,
        warm_endpoint=warm_endpoint,
        neighborhood=neighborhood,
        selected_ids=selected_ids,
    )
    proto = binding_model.model.Proto()
    return {
        "binding_model": binding_model,
        "routing_context": routing_context,
        "compiled": compiled,
        "y_vars": y_vars,
        "z_vars": z_vars,
        "operations": operations,
        "operation_counts": counts,
        "domain_stats": domain_stats,
        "hint_stats": hint_stats,
        "model_size": {
            "variables": len(proto.variables),
            "constraints": len(proto.constraints),
            "assignment_variables": len(y_vars),
            "conditional_pattern_variables": len(z_vars),
            "outside_binding_owner_count": len(
                [
                    key
                    for key in binding_model.binding_domains
                    if not key.startswith("joint::")
                ]
            ),
            "joint_binding_owner_count": len(
                [key for key in binding_model.binding_domains if key.startswith("joint::")]
            ),
        },
    }


def solve_joint(
    built: Mapping[str, Any],
    *,
    time_limit_seconds: float,
    random_seed: int,
) -> dict[str, Any]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = SOLVE_WORKERS
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(random_seed)
    started = time.monotonic()
    status = solver.Solve(built["binding_model"].model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "status": status_name,
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "objective": None,
        "best_bound": float(solver.BestObjectiveBound()),
    }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result

    result["objective"] = int(round(solver.ObjectiveValue()))
    operation_by_destination: list[str] = []
    selected_pattern_by_destination: list[dict[str, Any]] = []
    for destination in range(len(built["y_vars"]) // len(built["operations"])):
        selected_operations = [
            operation
            for operation in built["operations"]
            if solver.Value(built["y_vars"][(destination, operation)]) == 1
        ]
        if len(selected_operations) != 1:
            raise RuntimeError(
                f"E034 assignment extraction drift destination={destination}: "
                f"{selected_operations}"
            )
        operation = selected_operations[0]
        operation_by_destination.append(operation)
        patterns = [
            pattern_index
            for (row_destination, row_operation, pattern_index), variable in built[
                "z_vars"
            ].items()
            if row_destination == destination
            and row_operation == operation
            and solver.Value(variable) == 1
        ]
        if len(patterns) != 1:
            raise RuntimeError(
                f"E034 pattern extraction drift destination={destination}: {patterns}"
            )
        selected_pattern_by_destination.append(
            {
                "destination": destination,
                "operation": operation,
                "pattern_index": int(patterns[0]),
            }
        )

    per_commodity: dict[str, int] = {}
    for commodity in built["compiled"]["commodities"]:
        value = sum(
            int(solver.Value(variable))
            for variable in built["compiled"]["mismatch_vars"][commodity].values()
        )
        per_commodity[commodity] = value
        if int(solver.Value(built["compiled"]["source_global"][commodity])) != 1:
            raise RuntimeError(f"E034 missing global source: {commodity}")
        if int(solver.Value(built["compiled"]["sink_global"][commodity])) != 1:
            raise RuntimeError(f"E034 missing global sink: {commodity}")
    if sum(per_commodity.values()) != int(result["objective"]):
        raise RuntimeError("E034 objective/per-commodity mismatch")

    binding_model = built["binding_model"]
    binding_model._solver = solver
    binding_model._status = status
    selection = binding_model.extract_selection()
    port_specs = binding_model.extract_port_specs()
    result.update(
        {
            "operation_by_destination": operation_by_destination,
            "selected_pattern_by_destination": selected_pattern_by_destination,
            "per_commodity": per_commodity,
            "positive_commodity_count": sum(value > 0 for value in per_commodity.values()),
            "zero_mismatch_commodities": sorted(
                commodity for commodity, value in per_commodity.items() if value == 0
            ),
            "joint_selection": selection,
            "joint_selection_digest": stable_digest(selection),
            "joint_port_specs": port_specs,
            "joint_port_specs_digest": stable_digest(port_specs),
        }
    )
    return result


def run() -> dict[str, Any]:
    identity = verify_identity()
    e001 = import_module("zmd_e034_e001", E001_RUNNER)
    e002 = import_module("zmd_e034_e002", E002_RUNNER)
    e004 = import_module("zmd_e034_e004", E004_RUNNER)
    e014 = import_module("zmd_e034_e014", E014_RUNNER)
    e015 = import_module("zmd_e034_e015", E015_RUNNER)
    e027 = import_module("zmd_e034_e027", E027_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    neighborhood = selected_neighborhood()
    selected_ids = set(selected_instance_ids(neighborhood))
    first_solution = solution_from_assignment(FIRST_ASSIGNMENT)
    second_solution = solution_from_assignment(SECOND_ASSIGNMENT)
    first_endpoint = load_json(FIRST_ENDPOINT)
    second_endpoint = load_json(SECOND_ENDPOINT)
    for label, endpoint in (("first", first_endpoint), ("second", second_endpoint)):
        if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != 160:
            raise RuntimeError(f"E034 {label} warm endpoint drift")

    first_assignment = operation_assignment_for_solution(
        solution=first_solution,
        neighborhood=neighborhood,
        selected_ids=selected_ids,
    )
    second_assignment = operation_assignment_for_solution(
        solution=second_solution,
        neighborhood=neighborhood,
        selected_ids=selected_ids,
    )
    if first_assignment == second_assignment:
        raise RuntimeError("E034 warm assignments unexpectedly coincide")

    calibrations: list[dict[str, Any]] = []
    for index, (label, solution, endpoint, fixed_assignment) in enumerate(
        (
            ("first", first_solution, first_endpoint, first_assignment),
            ("second", second_solution, second_endpoint, second_assignment),
        ),
        1,
    ):
        built = build_joint_model(
            full_solution=solution,
            warm_endpoint=endpoint,
            fixed_assignment=fixed_assignment,
            inputs=inputs,
            neighborhood=neighborhood,
            selected_ids=selected_ids,
            e004=e004,
            e015=e015,
        )
        solved = solve_joint(
            built,
            time_limit_seconds=CALIBRATION_SECONDS,
            random_seed=34000 + index,
        )
        calibration = {
            "label": label,
            "fixed_assignment": list(fixed_assignment),
            "solve": {
                key: value
                for key, value in solved.items()
                if key
                not in {
                    "joint_selection",
                    "joint_port_specs",
                }
            },
            "model_size": built["model_size"],
            "hint_stats": built["hint_stats"],
        }
        calibrations.append(calibration)
        if solved["status"] != "OPTIMAL" or int(solved["objective"]) != 160:
            raise RuntimeError(
                f"E034 calibration failed for {label}: "
                f"{solved['status']} objective={solved.get('objective')}"
            )

    free_built = build_joint_model(
        full_solution=first_solution,
        warm_endpoint=first_endpoint,
        fixed_assignment=None,
        inputs=inputs,
        neighborhood=neighborhood,
        selected_ids=selected_ids,
        e004=e004,
        e015=e015,
    )
    free_solve = solve_joint(
        free_built,
        time_limit_seconds=FREE_SOLVE_SECONDS,
        random_seed=34999,
    )
    common = {
        "schema": "zmd_zero_condition_e034_joint_assignment_binding_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "parent_objective": PARENT_OBJECTIVE,
        "neighborhood": json_safe(neighborhood),
        "selected_instance_ids": sorted(selected_ids),
        "first_warm_assignment": list(first_assignment),
        "second_warm_assignment": list(second_assignment),
        "calibrations": calibrations,
        "model_size": free_built["model_size"],
        "domain_stats": free_built["domain_stats"],
        "hint_stats": free_built["hint_stats"],
        "free_solve": {
            key: value
            for key, value in free_solve.items()
            if key not in {"joint_selection", "joint_port_specs"}
        },
        "truth_boundary": (
            "One fixed occupied geometry; operation assignment and exact binding "
            "cohabit only on five selected 3x3 footprints."
        ),
        "ledger_effect": "none",
    }
    if free_solve["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return {
            **common,
            "verdict": "JOINT_ASSIGNMENT_BINDING_NONTERMINAL",
            "best_child": None,
            "routing": {"status": "NOT_REACHED_NO_FEASIBLE_JOINT_STATE"},
            "decision": "INSPECT_JOINT_MODEL_RESIDUE",
        }

    operation_by_destination = tuple(free_solve["operation_by_destination"])
    child = realize_assignment(
        parent=first_solution,
        neighborhood=neighborhood,
        operation_by_destination=operation_by_destination,
        selected_ids=selected_ids,
        pools=inputs["pools"],
        e014=e014,
    )
    first_occupied, _ = e014.base_occupancy(first_solution, inputs["pools"])
    child_occupied, _ = e014.base_occupancy(child, inputs["pools"])
    if child_occupied != first_occupied:
        raise RuntimeError("E034 concrete realization changed occupied geometry")
    selected_poles = {
        int(row["pose_idx"])
        for row in child.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)
    if not e014.all_powered_facilities_covered(
        solution=child,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    ):
        raise RuntimeError("E034 concrete realization broke power")

    endpoint = e027.materialize_shared_endpoint(
        solution=child,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=35001,
    )
    if int(endpoint["objective"]) != int(free_solve["objective"]):
        raise RuntimeError(
            "E034 joint/fixed materialization objective drift: "
            f"{free_solve['objective']} != {endpoint['objective']}"
        )

    joint_witness = {
        "schema": "zmd_zero_condition_e034_joint_witness_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": free_solve["status"],
        "objective": int(free_solve["objective"]),
        "operation_by_destination": list(operation_by_destination),
        "selected_pattern_by_destination": free_solve[
            "selected_pattern_by_destination"
        ],
        "joint_selection": free_solve["joint_selection"],
        "joint_port_specs": free_solve["joint_port_specs"],
        "per_commodity": free_solve["per_commodity"],
        "ledger_effect": "none",
    }
    dump_exclusive(JOINT_WITNESS_PATH, joint_witness)
    dump_exclusive(
        BEST_ASSIGNMENT_PATH,
        {
            "schema": "zmd_zero_condition_e034_best_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL"
            if free_solve["status"] == "OPTIMAL"
            else "FIXED_LAYOUT_SHARED_BINDING_FEASIBLE_NONTERMINAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "operation_by_destination": list(operation_by_destination),
            "solution": child,
        },
    )
    dump_exclusive(BEST_LAYOUT_PATH, e001.solution_layout(child))
    dump_exclusive(BEST_ENDPOINT_PATH, endpoint)

    objective = int(endpoint["objective"])
    if objective == 0:
        routing = e014.screen_component_interface(
            solution=child,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        verdict = "JOINT_ASSIGNMENT_BINDING_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif free_solve["status"] == "OPTIMAL" and objective < PARENT_OBJECTIVE:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "JOINT_ASSIGNMENT_BINDING_IMPROVEMENT"
        decision = "RECOMPUTE_JOINT_RESIDUAL_AND_SELECT_CONTEXT_EXPANSION"
    elif free_solve["status"] == "OPTIMAL":
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "BOUNDED_JOINT_ASSIGNMENT_BINDING_SATURATED"
        decision = "EXPAND_JOINT_CONTEXT_FROM_RESIDUAL_CAUSES"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "JOINT_ASSIGNMENT_BINDING_FEASIBLE_NONTERMINAL"
        decision = "CONTINUE_OR_REFORMULATE_JOINT_SOLVE"

    return {
        **common,
        "verdict": verdict,
        "best_child": {
            "objective": objective,
            "delta_from_parent": objective - PARENT_OBJECTIVE,
            "operation_by_destination": list(operation_by_destination),
            "placement_digest": stable_digest(child),
            "binding_selection_digest": endpoint["selection_digest"],
            "per_commodity": endpoint["per_commodity"],
            "positive_commodity_count": endpoint["positive_commodity_count"],
            "zero_mismatch_commodities": endpoint["zero_mismatch_commodities"],
            "morphology": endpoint["morphology"],
            "filtered_binding_option_count": endpoint[
                "filtered_binding_option_count"
            ],
            "joint_witness_path": str(JOINT_WITNESS_PATH.relative_to(ROOT)),
            "joint_witness_sha256": sha256_file(JOINT_WITNESS_PATH),
            "assignment_path": str(BEST_ASSIGNMENT_PATH.relative_to(ROOT)),
            "assignment_sha256": sha256_file(BEST_ASSIGNMENT_PATH),
            "layout_path": str(BEST_LAYOUT_PATH.relative_to(ROOT)),
            "layout_sha256": sha256_file(BEST_LAYOUT_PATH),
            "endpoint_path": str(BEST_ENDPOINT_PATH.relative_to(ROOT)),
            "endpoint_sha256": sha256_file(BEST_ENDPOINT_PATH),
        },
        "power_semantics": power["summary"],
        "routing": routing,
        "decision": decision,
    }


def main() -> int:
    outputs = (
        RESULT_PATH,
        FAILURE_PATH,
        JOINT_WITNESS_PATH,
        BEST_ASSIGNMENT_PATH,
        BEST_LAYOUT_PATH,
        BEST_ENDPOINT_PATH,
    )
    if any(path.exists() for path in outputs):
        raise FileExistsError("refusing to overwrite E034 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "parent_objective": result["parent_objective"],
                    "calibrations": [
                        {
                            "label": row["label"],
                            "status": row["solve"]["status"],
                            "objective": row["solve"]["objective"],
                        }
                        for row in result["calibrations"]
                    ],
                    "model_size": result["model_size"],
                    "free_status": result["free_solve"]["status"],
                    "free_objective": result["free_solve"]["objective"],
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
            "schema": "zmd_zero_condition_e034_joint_assignment_binding_failure_v1",
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
