#!/usr/bin/env python3
"""E038: merge the live and residual 3x3 subsets into one ten-footprint block."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback
import types
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E038_merged_3x3_assignment/run-003"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
JOINT_WITNESS_PATH = OUT / "JOINT_WITNESS.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_LAYOUT.json"
BEST_ENDPOINT_PATH = OUT / "BEST_ENDPOINT.json"

E037_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E037_merged_6x4_assignment/run-001/RESULT.json"
)
FIRST_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E037_merged_6x4_assignment/run-001/BEST_ASSIGNMENT.json"
)
FIRST_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E037_merged_6x4_assignment/run-001/BEST_ENDPOINT.json"
)
SECOND_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E036_three_block_joint_assignment/run-001/BEST_ASSIGNMENT.json"
)
SECOND_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E036_three_block_joint_assignment/run-001/BEST_ENDPOINT.json"
)
E037_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E037_merged_6x4_assignment/run_e037.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "268000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E037_RESULT: "450bd05565afc96cbd071d924405f85d4dc5bc7eee1af4e89cdb574566cfe56f",
    FIRST_ASSIGNMENT: "e06cb7e2078c398ee2eee4bdf61105bee3d9422a8fca355324f7296d04979640",
    FIRST_ENDPOINT: "4899d69713790483058945e1b568dd5a2fca12455dc8bfb844309ce18ad20383",
    SECOND_ASSIGNMENT: "a2b263a15a75d446154d7288c8fa499566d8bb565cd95e5c92c01cf782573116",
    SECOND_ENDPOINT: "24d675ea298254cba8ab34983f723d7b7e1663b06ed3957df014c0ef00c4a96e",
    E037_RUNNER: "0f6908e2735aba1c3ee7c8b9299fac212fd93ca29f32156af057c67af3d4edf5",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

PARENT_OBJECTIVE = 157
ADDITION_SIZE = 5
CALIBRATION_SECONDS = 45.0
FREE_SOLVE_SECONDS = 180.0


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
        raise RuntimeError("E038 must run on research/main")
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
    result = load_json(E037_RESULT)
    if result.get("verdict") != "MERGED_6X4_JOINT_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E037 trigger verdict drift")
    if int(result["best_child"]["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E037 objective drift")
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


def select_additional_3x3(
    *,
    live_blocks: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
) -> dict[str, Any]:
    current_pose_indices: dict[str, set[int]] = {}
    base_keys: list[str] = []
    for block in live_blocks:
        facility_type = str(block["facility_type"])
        poses = {
            int(payload["pose_idx"])
            for payload in block["selected_literal_payloads"]
        }
        current_pose_indices.setdefault(facility_type, set()).update(poses)
        keys = [
            key
            for key, payload in literals.items()
            if str(payload.get("facility_type")) == facility_type
            and int(payload.get("pose_idx", -1)) in poses
        ]
        if len(keys) != len(poses):
            raise RuntimeError(
                f"E038 current block literal count drift {block['block_id']}: "
                f"{len(keys)} != {len(poses)}"
            )
        base_keys.extend(keys)
    base_covered: set[int] = set()
    for key in base_keys:
        base_covered |= set(observation_ids_by_literal.get(key, set()))

    facility_type = "manufacturing_3x3"
    keys = sorted(
        key
        for key, payload in literals.items()
        if str(payload.get("kind")) == "mandatory_group_pose"
        and str(payload.get("facility_type")) == facility_type
        and len(payload.get("source_instance_ids", [])) == 1
        and int(payload.get("pose_idx", -1))
        not in current_pose_indices.get(facility_type, set())
    )
    if len(keys) < ADDITION_SIZE:
        raise RuntimeError("E038 insufficient residual 3x3 literals")
    operations = sorted({str(literals[key]["operation_type"]) for key in keys})

    def build_model() -> tuple[
        cp_model.CpModel,
        dict[str, cp_model.IntVar],
        list[cp_model.IntVar],
        dict[str, cp_model.IntVar],
    ]:
        model = cp_model.CpModel()
        select = {
            key: model.NewBoolVar(f"e038_select_{index}")
            for index, key in enumerate(keys)
        }
        cover: list[cp_model.IntVar] = []
        for observation_id in range(len(observations)):
            variable = model.NewBoolVar(f"e038_cover_{observation_id}")
            if observation_id in base_covered:
                model.Add(variable == 1)
            else:
                candidates = [
                    select[key]
                    for key in keys
                    if observation_id in observation_ids_by_literal.get(key, set())
                ]
                if candidates:
                    model.AddMaxEquality(variable, candidates)
                else:
                    model.Add(variable == 0)
            cover.append(variable)
        op_present: dict[str, cp_model.IntVar] = {}
        for operation_index, operation in enumerate(operations):
            candidates = [
                select[key]
                for key in keys
                if str(literals[key]["operation_type"]) == operation
            ]
            variable = model.NewBoolVar(f"e038_operation_{operation_index}")
            model.AddMaxEquality(variable, candidates)
            op_present[operation] = variable
        model.Add(sum(select.values()) == ADDITION_SIZE)
        return model, select, cover, op_present

    stage1, select1, cover1, _ops1 = build_model()
    stage1.Maximize(sum(cover1))
    solver1 = cp_model.CpSolver()
    solver1.parameters.max_time_in_seconds = 30
    solver1.parameters.num_search_workers = 1
    solver1.parameters.random_seed = 38001
    status1 = solver1.Solve(stage1)
    if status1 != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E038 3x3 marginal coverage not OPTIMAL: {solver1.StatusName(status1)}"
        )
    optimum_union = int(round(solver1.ObjectiveValue()))

    stage2, select2, cover2, op_present2 = build_model()
    stage2.Add(sum(cover2) == optimum_union)
    stage2.Maximize(sum(op_present2.values()))
    solver2 = cp_model.CpSolver()
    solver2.parameters.max_time_in_seconds = 30
    solver2.parameters.num_search_workers = 1
    solver2.parameters.random_seed = 38002
    status2 = solver2.Solve(stage2)
    if status2 != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E038 3x3 diversity not OPTIMAL: {solver2.StatusName(status2)}"
        )
    optimum_diversity = int(round(solver2.ObjectiveValue()))

    stage3, select3, cover3, op_present3 = build_model()
    stage3.Add(sum(cover3) == optimum_union)
    stage3.Add(sum(op_present3.values()) == optimum_diversity)
    stage3.Minimize(
        sum((index + 1) * select3[key] for index, key in enumerate(keys))
    )
    solver3 = cp_model.CpSolver()
    solver3.parameters.max_time_in_seconds = 30
    solver3.parameters.num_search_workers = 1
    solver3.parameters.random_seed = 38003
    status3 = solver3.Solve(stage3)
    if status3 != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E038 3x3 tie-break not OPTIMAL: {solver3.StatusName(status3)}"
        )
    selected = [key for key in keys if solver3.Value(select3[key]) == 1]
    payloads = [json_safe(literals[key]) for key in selected]
    return {
        "block_id": "3x3_addition",
        "facility_type": facility_type,
        "eligible_literal_count": len(keys),
        "selected_literal_count": len(selected),
        "base_covered_observation_count": len(base_covered),
        "covered_observation_count_with_base": optimum_union,
        "marginal_observation_count": optimum_union - len(base_covered),
        "coverage_fraction_with_base": optimum_union / len(observations),
        "operation_diversity": optimum_diversity,
        "selected_literals": selected,
        "selected_literal_payloads": payloads,
        "selection_digest": stable_digest(payloads),
    }


def actual_owner_by_pose(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    facility_type: str,
) -> dict[int, str]:
    owner_by_pose: dict[int, str] = {}
    for instance_id, row in solution.items():
        if str(row.get("facility_type")) != facility_type:
            continue
        pose_idx = int(row["pose_idx"])
        if pose_idx in owner_by_pose:
            raise RuntimeError(
                f"E038 duplicate {facility_type} owner at pose {pose_idx}: "
                f"{owner_by_pose[pose_idx]} and {instance_id}"
            )
        owner_by_pose[pose_idx] = str(instance_id)
    return owner_by_pose


def refresh_block_payloads(
    *,
    block_id: str,
    facility_type: str,
    pose_indices: Sequence[int],
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    group_by_instance: Mapping[str, str],
) -> dict[str, Any]:
    owner_by_pose = actual_owner_by_pose(
        solution=solution,
        facility_type=facility_type,
    )
    payloads: list[dict[str, Any]] = []
    for pose_idx in sorted(int(value) for value in pose_indices):
        instance_id = owner_by_pose.get(pose_idx)
        if instance_id is None:
            raise RuntimeError(
                f"E038 no current {facility_type} owner at pose {pose_idx}"
            )
        row = solution[instance_id]
        group_id = group_by_instance.get(instance_id)
        if group_id is None:
            raise RuntimeError(f"E038 mandatory owner lacks group: {instance_id}")
        pose = pools[facility_type][pose_idx]
        occupied = sorted(
            {(int(cell[0]), int(cell[1])) for cell in pose["occupied_cells"]}
        )
        payloads.append(
            {
                "literal_key": f"mandatory::{group_id}::{pose_idx}",
                "kind": "mandatory_group_pose",
                "consumer_id": group_id,
                "facility_type": facility_type,
                "operation_type": str(row["operation_type"]),
                "pose_idx": pose_idx,
                "pose_id": str(pose["pose_id"]),
                "occupied_cells": occupied,
                "source_instance_ids": [instance_id],
                "anchor": {
                    "x": int(pose["anchor"]["x"]),
                    "y": int(pose["anchor"]["y"]),
                },
            }
        )
    counts = Counter(str(row["operation_type"]) for row in payloads)
    semantic_permutations = math.factorial(len(payloads))
    for count in counts.values():
        semantic_permutations //= math.factorial(count)
    return {
        "block_id": block_id,
        "facility_type": facility_type,
        "selected_literal_count": len(payloads),
        "operation_multiset": dict(sorted(counts.items())),
        "operation_diversity": len(counts),
        "semantic_permutation_count_including_identity": semantic_permutations,
        "selected_literals": [str(row["literal_key"]) for row in payloads],
        "selected_literal_payloads": payloads,
        "selection_digest": stable_digest(payloads),
        "owner_refresh": "current_solution_pose_owner",
    }


def selected_ids_for_solution(
    *,
    blocks: Sequence[Mapping[str, Any]],
    solution: Mapping[str, Mapping[str, Any]],
) -> dict[str, set[str]]:
    selected: dict[str, set[str]] = {}
    for block in blocks:
        block_id = str(block["block_id"])
        facility_type = str(block["facility_type"])
        owner_by_pose = actual_owner_by_pose(
            solution=solution,
            facility_type=facility_type,
        )
        pose_indices = {
            int(row["pose_idx"])
            for row in block["selected_literal_payloads"]
        }
        ids = {owner_by_pose[pose_idx] for pose_idx in pose_indices}
        if len(ids) != len(pose_indices):
            raise RuntimeError(f"E038 {block_id} owner set alias")
        selected[block_id] = ids
    if len(set().union(*selected.values())) != sum(len(value) for value in selected.values()):
        raise RuntimeError("E038 cross-block selected instance overlap")
    return selected


def build_native_joint_model(
    *,
    full_solution: Mapping[str, Mapping[str, Any]],
    warm_endpoint: Mapping[str, Any],
    fixed_assignments: Mapping[str, Sequence[str]] | None,
    inputs: Mapping[str, Any],
    blocks: Sequence[Mapping[str, Any]],
    selected_ids_by_block: Mapping[str, set[str]],
    e004: Any,
    e015: Any,
    e035: Any,
) -> dict[str, Any]:
    """Build dynamic owners before native PortBindingModel constraint phases.

    Every potential (footprint, operation) owner is represented as one ordinary
    binding owner with an explicit inactive empty pattern.  The native builder
    therefore sees all conditional owners while constructing conservation,
    distinctness, local implication, and search-guidance constraints.  Assignment
    variables are derived from the non-empty pattern literals afterwards.
    """
    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_binding_context import build_routing_binding_context

    routing_context = build_routing_binding_context(
        full_solution,
        inputs["pools"],
        70,
        70,
    )
    all_selected_ids = set().union(*selected_ids_by_block.values())
    placement_solution = {
        instance_id: dict(row)
        for instance_id, row in full_solution.items()
        if instance_id not in all_selected_ids
    }
    virtual_instances: list[dict[str, Any]] = []
    virtual_meta: dict[str, dict[str, Any]] = {}
    block_metadata: list[dict[str, Any]] = []
    for block in blocks:
        block_id = str(block["block_id"])
        facility_type = str(block["facility_type"])
        payloads = [dict(row) for row in block["selected_literal_payloads"]]
        operations = sorted(str(value) for value in block["operation_multiset"])
        counts = {
            str(key): int(value)
            for key, value in block["operation_multiset"].items()
        }
        for destination, payload in enumerate(payloads):
            pose_idx = int(payload["pose_idx"])
            pose = inputs["pools"][facility_type][pose_idx]
            for operation in operations:
                virtual_owner = f"joint::{block_id}::{destination:02d}::{operation}"
                row = {
                    "instance_id": virtual_owner,
                    "facility_type": facility_type,
                    "operation_type": operation,
                    "pose_idx": pose_idx,
                    "pose_id": str(pose["pose_id"]),
                    "anchor": {
                        "x": int(pose["anchor"]["x"]),
                        "y": int(pose["anchor"]["y"]),
                    },
                    "is_mandatory": False,
                    "bound_type": "exact",
                    "solve_mode": "certified_exact",
                }
                placement_solution[virtual_owner] = row
                virtual_instances.append(
                    {
                        "instance_id": virtual_owner,
                        "facility_type": facility_type,
                        "operation_type": operation,
                        "is_mandatory": False,
                        "bound_type": "exact",
                        "solve_modes": ["certified_exact", "exploratory"],
                    }
                )
                virtual_meta[virtual_owner] = {
                    "block_id": block_id,
                    "destination": destination,
                    "operation": operation,
                    "pose_idx": pose_idx,
                }
        block_metadata.append(
            {
                "block_id": block_id,
                "facility_type": facility_type,
                "destination_count": len(payloads),
                "operations": operations,
                "operation_counts": counts,
            }
        )

    plan = inputs["plan"]
    generic = inputs["generic"]
    binding_model = PortBindingModel(
        placement_solution=placement_solution,
        facility_pools=inputs["pools"],
        instances=[*inputs["instances"], *virtual_instances],
        project_root=HISTORY_ROOT,
        required_generic_outputs=generic.get("required_generic_outputs", {}),
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
        generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
        utility_operation_by_template=plan["utility_operation_by_template"],
        canonical_rules_payload=inputs["rules"],
        routing_context=routing_context,
    )
    original_filter = binding_model._filter_pose_binding_domain

    def filter_with_inactive(
        self: Any,
        raw_patterns: list[dict[str, list[dict[str, Any]]]],
        owner_instance_id: str,
    ) -> list[dict[str, list[dict[str, Any]]]]:
        filtered = original_filter(raw_patterns, owner_instance_id)
        if owner_instance_id not in virtual_meta:
            return filtered
        return [
            {
                "input_ports": [],
                "output_ports": [],
                "joint_inactive": True,
            },
            *filtered,
        ]

    binding_model._filter_pose_binding_domain = types.MethodType(
        filter_with_inactive,
        binding_model,
    )
    binding_model.build(use_overload_separation=False)
    if binding_model.empty_binding_domain_instances:
        raise RuntimeError(
            "E038 native joint model has empty binding domains: "
            f"{binding_model.empty_binding_domain_instances}"
        )

    y_vars: dict[tuple[str, int, str], Any] = {}
    z_vars: dict[tuple[str, int, str, int], Any] = {}
    domain_stats: list[dict[str, Any]] = []
    for virtual_owner, metadata in sorted(virtual_meta.items()):
        domain = binding_model.binding_domains.get(virtual_owner)
        vars_by_idx = binding_model.binding_vars.get(virtual_owner)
        if not domain or vars_by_idx is None:
            raise RuntimeError(f"E038 virtual owner domain missing: {virtual_owner}")
        if not bool(domain[0].get("joint_inactive")):
            raise RuntimeError(f"E038 inactive pattern drift: {virtual_owner}")
        inactive = vars_by_idx.get(0)
        if inactive is None:
            raise RuntimeError(f"E038 inactive literal missing: {virtual_owner}")
        y = binding_model.model.NewBoolVar(f"e038_active_{virtual_owner}")
        binding_model.model.Add(y + inactive == 1)
        key = (
            str(metadata["block_id"]),
            int(metadata["destination"]),
            str(metadata["operation"]),
        )
        y_vars[key] = y
        for actual_index in range(1, len(domain)):
            variable = vars_by_idx.get(actual_index)
            if variable is None:
                raise RuntimeError(
                    f"E038 virtual pattern literal missing: {virtual_owner}/{actual_index}"
                )
            z_vars[(*key, actual_index - 1)] = variable
        domain_stats.append(
            {
                **metadata,
                "virtual_owner": virtual_owner,
                "domain_count_including_inactive": len(domain),
                "active_pattern_count": len(domain) - 1,
            }
        )

    for block in block_metadata:
        block_id = str(block["block_id"])
        operations = [str(value) for value in block["operations"]]
        for destination in range(int(block["destination_count"])):
            binding_model.model.Add(
                sum(
                    y_vars[(block_id, destination, operation)]
                    for operation in operations
                )
                == 1
            )
        for operation in operations:
            binding_model.model.Add(
                sum(
                    y_vars[(block_id, destination, operation)]
                    for destination in range(int(block["destination_count"]))
                )
                == int(block["operation_counts"][operation])
            )
        if fixed_assignments is not None:
            fixed = tuple(str(value) for value in fixed_assignments[block_id])
            if len(fixed) != int(block["destination_count"]):
                raise RuntimeError(f"E038 {block_id} fixed assignment width drift")
            for destination, selected_operation in enumerate(fixed):
                for operation in operations:
                    binding_model.model.Add(
                        y_vars[(block_id, destination, operation)]
                        == int(operation == selected_operation)
                    )

    compiled = e015.compile_shared_objective(
        binding_model=binding_model,
        routing_context=routing_context,
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        e004=e004,
    )
    hint_stats = e035.add_hints(
        binding_model=binding_model,
        y_vars=y_vars,
        z_vars=z_vars,
        warm_solution=full_solution,
        warm_endpoint=warm_endpoint,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
    )
    proto = binding_model.model.Proto()
    return {
        "binding_model": binding_model,
        "routing_context": routing_context,
        "compiled": compiled,
        "y_vars": y_vars,
        "z_vars": z_vars,
        "blocks": block_metadata,
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
                [
                    key
                    for key in binding_model.binding_domains
                    if key.startswith("joint::")
                ]
            ),
        },
        "native_constraint_path": True,
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e037 = import_module("zmd_e038_e037", E037_RUNNER)
    e036 = import_module("zmd_e038_e036", e037.E036_RUNNER)
    e035 = import_module("zmd_e038_e035", e036.E035_RUNNER)
    e001 = import_module("zmd_e038_e001", e035.E001_RUNNER)
    e002 = import_module("zmd_e038_e002", e035.E002_RUNNER)
    e004 = import_module("zmd_e038_e004", e035.E004_RUNNER)
    e013 = import_module("zmd_e038_e013", e035.E013_RUNNER)
    e014 = import_module("zmd_e038_e014", e035.E014_RUNNER)
    e015 = import_module("zmd_e038_e015", e035.E015_RUNNER)
    e027 = import_module("zmd_e038_e027", e035.E027_RUNNER)
    e031 = import_module("zmd_e038_e031", e035.E031_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    first_solution = e035.solution_from_assignment(FIRST_ASSIGNMENT)
    second_solution = e035.solution_from_assignment(SECOND_ASSIGNMENT)
    first_endpoint = load_json(FIRST_ENDPOINT)
    second_endpoint = load_json(SECOND_ENDPOINT)
    if first_endpoint.get("status") != "OPTIMAL" or int(first_endpoint["objective"]) != 157:
        raise RuntimeError("E038 first warm endpoint drift")
    if second_endpoint.get("status") != "OPTIMAL" or int(second_endpoint["objective"]) != 159:
        raise RuntimeError("E038 second regression endpoint drift")

    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(mandatory, list) or not isinstance(generic, Mapping):
        raise RuntimeError("E038 frozen instance/generic payload drift")

    observations, literals, observation_ids_by_literal = e035.build_incidence(
        solution=first_solution,
        endpoint=first_endpoint,
        pools=inputs["pools"],
        mandatory=mandatory,
        e013=e013,
    )
    e037_result = load_json(E037_RESULT)
    live_blocks = [dict(row) for row in e037_result["final_blocks"]]
    current_3x3 = next(
        block
        for block in live_blocks
        if str(block["facility_type"]) == "manufacturing_3x3"
    )
    addition = select_additional_3x3(
        live_blocks=live_blocks,
        observations=observations,
        literals=literals,
        observation_ids_by_literal=observation_ids_by_literal,
    )
    group_by_instance = e013.group_mapping(mandatory)
    merged_pose_indices = {
        int(row["pose_idx"])
        for row in current_3x3["selected_literal_payloads"]
    } | {
        int(row["pose_idx"])
        for row in addition["selected_literal_payloads"]
    }
    merged = refresh_block_payloads(
        block_id="3x3_merged",
        facility_type="manufacturing_3x3",
        pose_indices=sorted(merged_pose_indices),
        solution=first_solution,
        pools=inputs["pools"],
        group_by_instance=group_by_instance,
    )
    merged["component_blocks"] = {
        "current": current_3x3["selection_digest"],
        "addition": addition["selection_digest"],
    }
    current_5x5 = next(
        block
        for block in live_blocks
        if str(block["facility_type"]) == "manufacturing_5x5"
    )
    current_6x4 = next(
        block
        for block in live_blocks
        if str(block["facility_type"]) == "manufacturing_6x4"
    )
    refreshed_5x5 = refresh_block_payloads(
        block_id="5x5",
        facility_type="manufacturing_5x5",
        pose_indices=[
            int(row["pose_idx"])
            for row in current_5x5["selected_literal_payloads"]
        ],
        solution=first_solution,
        pools=inputs["pools"],
        group_by_instance=group_by_instance,
    )
    refreshed_6x4 = refresh_block_payloads(
        block_id="6x4_merged",
        facility_type="manufacturing_6x4",
        pose_indices=[
            int(row["pose_idx"])
            for row in current_6x4["selected_literal_payloads"]
        ],
        solution=first_solution,
        pools=inputs["pools"],
        group_by_instance=group_by_instance,
    )
    blocks = [merged, refreshed_5x5, refreshed_6x4]
    exchangeability = e031.exchangeability_audit(
        neighborhoods=blocks,
        mandatory=mandatory,
        generic=generic,
    )
    if exchangeability.get("status") != "PASS":
        raise RuntimeError("E038 exchangeability audit failed")

    selected_ids_by_block = selected_ids_for_solution(
        blocks=blocks,
        solution=first_solution,
    )

    calibrations: list[dict[str, Any]] = []
    for index, (label, solution, endpoint, expected) in enumerate(
        (
            ("first", first_solution, first_endpoint, 157),
            ("second_regression", second_solution, second_endpoint, 159),
        ),
        1,
    ):
        calibration_selected_ids = selected_ids_for_solution(
            blocks=blocks,
            solution=solution,
        )
        fixed = {
            str(block["block_id"]): e035.operation_assignment_for_solution(
                solution=solution,
                block=block,
                selected_ids=calibration_selected_ids[str(block["block_id"])],
            )
            for block in blocks
        }
        built = build_native_joint_model(
            full_solution=solution,
            warm_endpoint=endpoint,
            fixed_assignments=fixed,
            inputs=inputs,
            blocks=blocks,
            selected_ids_by_block=calibration_selected_ids,
            e004=e004,
            e015=e015,
            e035=e035,
        )
        solved = e035.solve_joint(
            built,
            time_limit_seconds=CALIBRATION_SECONDS,
            random_seed=38010 + index,
        )
        calibrations.append(
            {
                "label": label,
                "expected_objective": expected,
                "fixed_assignments": {
                    key: list(value) for key, value in fixed.items()
                },
                "solve": {
                    key: value
                    for key, value in solved.items()
                    if key not in {"joint_selection", "joint_port_specs"}
                },
                "model_size": built["model_size"],
                "hint_stats": built["hint_stats"],
            }
        )
        if solved["status"] != "OPTIMAL" or int(solved["objective"]) != expected:
            raise RuntimeError(
                f"E038 calibration failed {label}: {solved['status']} "
                f"objective={solved.get('objective')} expected={expected}"
            )

    free_built = build_native_joint_model(
        full_solution=first_solution,
        warm_endpoint=first_endpoint,
        fixed_assignments=None,
        inputs=inputs,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
        e004=e004,
        e015=e015,
        e035=e035,
    )
    free_solve = e035.solve_joint(
        free_built,
        time_limit_seconds=FREE_SOLVE_SECONDS,
        random_seed=38999,
    )
    common = {
        "schema": "zmd_zero_condition_e038_merged_3x3_assignment_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "parent_objective": PARENT_OBJECTIVE,
        "observation_count": len(observations),
        "live_blocks_before_merge": json_safe(live_blocks),
        "additional_3x3": json_safe(addition),
        "merged_3x3_block": json_safe(merged),
        "final_blocks": json_safe(blocks),
        "exchangeability_audit": exchangeability,
        "selected_instance_ids_by_block": {
            key: sorted(value) for key, value in selected_ids_by_block.items()
        },
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
            "One fixed occupied geometry; assignment and binding cohabit on one "
            "merged ten-footprint 3x3 block, five 5x5 footprints, and one merged "
            "ten-footprint 6x4 block."
        ),
        "ledger_effect": "none",
    }
    if free_solve["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return {
            **common,
            "verdict": "MERGED_3X3_JOINT_NONTERMINAL",
            "best_child": None,
            "routing": {"status": "NOT_REACHED_NO_FEASIBLE_JOINT_STATE"},
            "decision": "INSPECT_OR_REFORMULATE_MERGED_3X3_MODEL",
        }

    child = e035.realize_blocks(
        parent=first_solution,
        blocks=blocks,
        operation_by_block=free_solve["operation_by_block"],
        selected_ids_by_block=selected_ids_by_block,
        pools=inputs["pools"],
        e014=e014,
    )
    first_occupied, _ = e014.base_occupancy(first_solution, inputs["pools"])
    child_occupied, _ = e014.base_occupancy(child, inputs["pools"])
    if child_occupied != first_occupied:
        raise RuntimeError("E038 concrete realization changed occupied geometry")
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
        raise RuntimeError("E038 concrete realization broke power")

    endpoint = e027.materialize_shared_endpoint(
        solution=child,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=39001,
    )
    if int(endpoint["objective"]) != int(free_solve["objective"]):
        raise RuntimeError(
            "E038 joint/fixed materialization objective drift: "
            f"{free_solve['objective']} != {endpoint['objective']}"
        )

    joint_witness = {
        "schema": "zmd_zero_condition_e038_joint_witness_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": free_solve["status"],
        "objective": int(free_solve["objective"]),
        "operation_by_block": free_solve["operation_by_block"],
        "selected_pattern_by_block": free_solve["selected_pattern_by_block"],
        "joint_selection": free_solve["joint_selection"],
        "joint_port_specs": free_solve["joint_port_specs"],
        "per_commodity": free_solve["per_commodity"],
        "ledger_effect": "none",
    }
    dump_exclusive(JOINT_WITNESS_PATH, joint_witness)
    dump_exclusive(
        BEST_ASSIGNMENT_PATH,
        {
            "schema": "zmd_zero_condition_e038_best_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL"
            if free_solve["status"] == "OPTIMAL"
            else "FIXED_LAYOUT_SHARED_BINDING_FEASIBLE_NONTERMINAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "operation_by_block": free_solve["operation_by_block"],
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
        verdict = "MERGED_3X3_JOINT_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif free_solve["status"] == "OPTIMAL" and objective < PARENT_OBJECTIVE:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "MERGED_3X3_JOINT_MATERIAL_IMPROVEMENT"
        decision = "RECOMPUTE_RESIDUAL_FROM_MERGED_3X3_ENDPOINT"
    elif free_solve["status"] == "OPTIMAL":
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "FIXED_GEOMETRY_ASSIGNMENT_SATURATION_SIGNAL"
        decision = "RELEASE_PROBLEM_DERIVED_GEOMETRY_NEIGHBORHOOD"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "MERGED_3X3_JOINT_FEASIBLE_NONTERMINAL"
        decision = "CONTINUE_OR_REFORMULATE_MERGED_3X3_SOLVE"

    return {
        **common,
        "verdict": verdict,
        "best_child": {
            "objective": objective,
            "delta_from_parent": objective - PARENT_OBJECTIVE,
            "operation_by_block": free_solve["operation_by_block"],
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
        raise FileExistsError("refusing to overwrite E038 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "parent_objective": result["parent_objective"],
                    "additional_3x3": {
                        "marginal_observation_count": result["additional_3x3"][
                            "marginal_observation_count"
                        ],
                        "selected_literals": result["additional_3x3"][
                            "selected_literals"
                        ],
                    },
                    "merged_operation_multiset": result["merged_3x3_block"][
                        "operation_multiset"
                    ],
                    "calibrations": [
                        {
                            "label": row["label"],
                            "status": row["solve"]["status"],
                            "objective": row["solve"]["objective"],
                        }
                        for row in result["calibrations"]
                    ],
                    "free_status": result["free_solve"]["status"],
                    "free_objective": result["free_solve"]["objective"],
                    "model_size": result["model_size"],
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
            "schema": "zmd_zero_condition_e038_merged_3x3_assignment_failure_v1",
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
