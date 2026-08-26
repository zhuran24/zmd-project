#!/usr/bin/env python3
"""E041: joint same-footprint port mode, operation assignment, and binding."""

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
EXPERIMENT_DIR = Path(__file__).resolve().parent
OUT = ROOT / "research_lab/local/zero_condition/E041_joint_port_mode_assignment/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
JOINT_WITNESS_PATH = OUT / "JOINT_WITNESS.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_LAYOUT.json"
BEST_ENDPOINT_PATH = OUT / "BEST_ENDPOINT.json"

E039_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E039_native_conditional_owner_binding/run-002/RESULT.json"
)
E039_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E039_native_conditional_owner_binding/run-002/BEST_ASSIGNMENT.json"
)
E039_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E039_native_conditional_owner_binding/run-002/BEST_ENDPOINT.json"
)
E040_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E040_geometry_mobility_discriminator/run-002/RESULT.json"
)
E040_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E040_geometry_mobility_discriminator/run-002/BEST_ASSIGNMENT.json"
)
E040_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E040_geometry_mobility_discriminator/run-002/BEST_ENDPOINT.json"
)
E039_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E039_native_conditional_owner_binding/run_e039.py"
)
E039_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E039_native_conditional_owner_binding/conditional_owner_binding.py"
)
E040_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E040_geometry_mobility_discriminator/run_e040.py"
)
MODE_HELPER = EXPERIMENT_DIR / "conditional_mode_owner_binding.py"

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "271000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E039_RESULT: "662c2a420fd84a7c9fbbde6c0392d1ce7d726b8c3dcd83e430d299a8a3c93389",
    E039_ASSIGNMENT: "aeded115ef1a1983e0fdf9f3decee3d34983d8b53de0f02af5bcb3670cd8cf7b",
    E039_ENDPOINT: "f24f39d1fdf317a9bd2cd9c3559c46ef449a9d67e8e5c671b1523b3d2c0ef85e",
    E040_RESULT: "d6031ef825363173b1ec51aebbcd69eb46a0d00cf76aef3dd7a1d69e6c5c9b3e",
    E040_ASSIGNMENT: "f4d2a3a90ffa40fd937776702344fa513a49bcb496d86732cf04407c556f247f",
    E040_ENDPOINT: "d700a6bdcf62e1f611d421ad6e71a1e99e46eff0f0d5958ac8657e3dbc71ea42",
    E039_RUNNER: "ebb471a0bba3e3cd2d2e141190c2e128fefcacfff620d7e6fdf6aee71b1741b9",
    E039_HELPER: "3f86dbc5f339c80566e7d95e02d75009cdd8f377db2d1364615c3f23058caa11",
    E040_RUNNER: "31acc6d399b1e2e9f8b80504570e276681692fd082afd2e561470f0fddff827e",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}
EXPECTED_MODE_HELPER_SHA256 = "98464fc5c9ee181a69392e582c2194edd0c213965b6c62672ece190fb1370dad"

E039_OBJECTIVE = 157
E040_OBJECTIVE = 154
CALIBRATION_SECONDS = 60.0
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
        raise RuntimeError("E041 must run on research/main")
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
    helper_sha = sha256_file(MODE_HELPER)
    if helper_sha != EXPECTED_MODE_HELPER_SHA256:
        raise RuntimeError(
            f"conditional mode helper drift: {helper_sha} != "
            f"{EXPECTED_MODE_HELPER_SHA256}"
        )
    checked[str(MODE_HELPER)] = helper_sha
    r39 = load_json(E039_RESULT)
    r40 = load_json(E040_RESULT)
    if r39.get("verdict") != "NATIVE_CONDITIONAL_OWNER_CONTEXT_SATURATED":
        raise RuntimeError("E039 trigger verdict drift")
    if int(r39["best_child"]["objective"]) != E039_OBJECTIVE:
        raise RuntimeError("E039 objective drift")
    if r40.get("verdict") != "CAUSAL_GEOMETRY_MATERIAL_SIGNAL":
        raise RuntimeError("E040 trigger verdict drift")
    if int(r40["best_child"]["objective"]) != E040_OBJECTIVE:
        raise RuntimeError("E040 objective drift")
    if not bool(r40["best_child"]["same_footprint"]):
        raise RuntimeError("E040 best child is no longer same-footprint")
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
    raw = load_json(path).get("solution")
    if not isinstance(raw, Mapping):
        raise RuntimeError(f"assignment solution missing: {path}")
    return {
        str(instance_id): dict(row)
        for instance_id, row in raw.items()
        if isinstance(row, Mapping)
    }


def body_cells(
    *,
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    facility_type: str,
    pose_idx: int,
) -> frozenset[tuple[int, int]]:
    pool = pools.get(facility_type)
    if not isinstance(pool, list) or not (0 <= pose_idx < len(pool)):
        raise RuntimeError(f"pose missing from pool: {facility_type}@{pose_idx}")
    raw = pool[pose_idx].get("occupied_cells")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"pose body missing: {facility_type}@{pose_idx}")
    return frozenset((int(cell[0]), int(cell[1])) for cell in raw)


def destination_state_for_solution(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    block: Mapping[str, Any],
    selected_ids: set[str],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    facility_type = str(block["facility_type"])
    destinations = [
        body_cells(
            pools=pools,
            facility_type=facility_type,
            pose_idx=int(payload["pose_idx"]),
        )
        for payload in block["selected_literal_payloads"]
    ]
    if len(destinations) != len(set(destinations)):
        raise RuntimeError(f"duplicate body destination in {block['block_id']}")
    rows: list[dict[str, Any] | None] = [None] * len(destinations)
    for instance_id in selected_ids:
        row = solution.get(instance_id)
        if row is None:
            raise RuntimeError(f"selected instance absent: {instance_id}")
        if str(row["facility_type"]) != facility_type:
            raise RuntimeError(f"selected facility type drift: {instance_id}")
        cells = body_cells(
            pools=pools,
            facility_type=facility_type,
            pose_idx=int(row["pose_idx"]),
        )
        matches = [index for index, body in enumerate(destinations) if body == cells]
        if len(matches) != 1:
            raise RuntimeError(
                f"body destination lookup drift {block['block_id']}/{instance_id}: "
                f"{matches}"
            )
        destination = matches[0]
        if rows[destination] is not None:
            raise RuntimeError(
                f"multiple instances occupy one body destination: {block['block_id']}/"
                f"{destination}"
            )
        rows[destination] = {
            "destination": destination,
            "instance_id": instance_id,
            "operation": str(row["operation_type"]),
            "pose_idx": int(row["pose_idx"]),
        }
    if any(row is None for row in rows):
        raise RuntimeError(f"incomplete destination state: {block['block_id']}")
    return [dict(row) for row in rows if row is not None]


def enrich_blocks_with_modes(
    *,
    blocks: Sequence[Mapping[str, Any]],
    solution: Mapping[str, Mapping[str, Any]],
    selected_ids_by_block: Mapping[str, set[str]],
    mode_enabled_ids: set[str],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    enriched: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for raw_block in blocks:
        block = dict(raw_block)
        block_id = str(block["block_id"])
        facility_type = str(block["facility_type"])
        current_state = destination_state_for_solution(
            solution=solution,
            block=block,
            selected_ids=selected_ids_by_block[block_id],
            pools=pools,
        )
        pool = pools.get(facility_type)
        if not isinstance(pool, list):
            raise RuntimeError(f"facility pool missing: {facility_type}")
        modes_by_destination: list[list[int]] = []
        source_ids_by_destination: list[str] = []
        for destination, state in enumerate(current_state):
            current_pose_idx = int(state["pose_idx"])
            current_body = body_cells(
                pools=pools,
                facility_type=facility_type,
                pose_idx=current_pose_idx,
            )
            instance_id = str(state["instance_id"])
            if instance_id in mode_enabled_ids:
                modes = [
                    pose_idx
                    for pose_idx in range(len(pool))
                    if body_cells(
                        pools=pools,
                        facility_type=facility_type,
                        pose_idx=pose_idx,
                    )
                    == current_body
                ]
            else:
                modes = [current_pose_idx]
            modes = sorted(set(int(value) for value in modes))
            if current_pose_idx not in modes:
                raise RuntimeError(
                    f"current pose absent from mode set: {block_id}/{destination}"
                )
            modes_by_destination.append(modes)
            source_ids_by_destination.append(instance_id)
            summary.append(
                {
                    "block_id": block_id,
                    "destination": destination,
                    "source_instance_id": instance_id,
                    "facility_type": facility_type,
                    "current_operation": str(state["operation"]),
                    "current_pose_idx": current_pose_idx,
                    "mode_enabled": instance_id in mode_enabled_ids,
                    "mode_pose_indices": modes,
                    "mode_count": len(modes),
                    "body_digest": stable_digest(sorted(current_body)),
                }
            )
        block["mode_pose_indices_by_destination"] = modes_by_destination
        block["source_instance_ids_by_destination"] = source_ids_by_destination
        enriched.append(block)
    return enriched, summary


def fixed_state_for_solution(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    blocks: Sequence[Mapping[str, Any]],
    selected_ids_by_block: Mapping[str, set[str]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for block in blocks:
        block_id = str(block["block_id"])
        rows = destination_state_for_solution(
            solution=solution,
            block=block,
            selected_ids=selected_ids_by_block[block_id],
            pools=pools,
        )
        admitted_modes = [
            {int(value) for value in values}
            for values in block["mode_pose_indices_by_destination"]
        ]
        for row in rows:
            destination = int(row["destination"])
            if int(row["pose_idx"]) not in admitted_modes[destination]:
                raise RuntimeError(
                    f"fixed pose outside admitted mode set: {block_id}/{destination}/"
                    f"{row['pose_idx']}"
                )
        output[block_id] = rows
    return output


def conditional_mode_owner_registration(
    *,
    full_solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    blocks: Sequence[Mapping[str, Any]],
    selected_ids_by_block: Mapping[str, set[str]],
) -> tuple[
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
]:
    all_selected_ids = set().union(*selected_ids_by_block.values())
    placement_solution = {
        instance_id: dict(row)
        for instance_id, row in full_solution.items()
        if instance_id not in all_selected_ids
    }
    virtual_instances: list[dict[str, Any]] = []
    virtual_metadata: dict[str, dict[str, Any]] = {}
    block_metadata: list[dict[str, Any]] = []
    plan = inputs["plan"]
    for block in blocks:
        block_id = str(block["block_id"])
        facility_type = str(block["facility_type"])
        modes_by_destination = [
            [int(value) for value in values]
            for values in block["mode_pose_indices_by_destination"]
        ]
        operations = sorted(str(value) for value in block["operation_multiset"])
        counts = {
            str(key): int(value)
            for key, value in block["operation_multiset"].items()
        }
        for operation in operations:
            generic_inputs = int(
                plan["generic_input_slots_by_operation"].get(operation, 0)
            )
            generic_outputs = int(
                plan["generic_output_slots_by_operation"].get(operation, 0)
            )
            if generic_inputs or generic_outputs:
                raise RuntimeError(
                    "E041 conditional generic slots are outside admitted scope: "
                    f"operation={operation} in={generic_inputs} out={generic_outputs}"
                )
        for destination, pose_indices in enumerate(modes_by_destination):
            for mode_index, pose_idx in enumerate(pose_indices):
                pose = inputs["pools"][facility_type][pose_idx]
                for operation in operations:
                    virtual_owner = (
                        f"jointmode::{block_id}::{destination:02d}::"
                        f"{mode_index:02d}::{operation}"
                    )
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
                    virtual_metadata[virtual_owner] = {
                        "block_id": block_id,
                        "destination": destination,
                        "mode_index": mode_index,
                        "pose_idx": pose_idx,
                        "operation": operation,
                        "facility_type": facility_type,
                    }
        block_metadata.append(
            {
                "block_id": block_id,
                "facility_type": facility_type,
                "destination_count": len(modes_by_destination),
                "operations": operations,
                "operation_counts": counts,
                "mode_pose_indices_by_destination": modes_by_destination,
            }
        )
    return placement_solution, virtual_instances, virtual_metadata, block_metadata


def add_mode_hints(
    *,
    binding_model: Any,
    y_vars: Mapping[tuple[str, int, int, str], Any],
    z_vars: Mapping[tuple[str, int, int, str, int], Any],
    warm_solution: Mapping[str, Mapping[str, Any]],
    warm_endpoint: Mapping[str, Any],
    blocks: Sequence[Mapping[str, Any]],
    selected_ids_by_block: Mapping[str, set[str]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    fixed = fixed_state_for_solution(
        solution=warm_solution,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
        pools=pools,
    )
    state_by_destination = {
        (block_id, int(row["destination"])): dict(row)
        for block_id, rows in fixed.items()
        for row in rows
    }
    block_by_id = {str(block["block_id"]): block for block in blocks}
    hinted = 0
    for (block_id, destination, mode_index, operation), variable in y_vars.items():
        state = state_by_destination[(block_id, destination)]
        pose_idx = int(
            block_by_id[block_id]["mode_pose_indices_by_destination"][destination][
                mode_index
            ]
        )
        selected = (
            str(state["operation"]) == operation
            and int(state["pose_idx"]) == pose_idx
        )
        binding_model.model.AddHint(variable, int(selected))
        hinted += 1

    selection = warm_endpoint.get("selection", {})
    binding_choice = dict(selection.get("binding_choice", {}))
    for (
        block_id,
        destination,
        mode_index,
        operation,
        pattern_index,
    ), variable in z_vars.items():
        state = state_by_destination[(block_id, destination)]
        pose_idx = int(
            block_by_id[block_id]["mode_pose_indices_by_destination"][destination][
                mode_index
            ]
        )
        selected_pattern = binding_choice.get(str(state["instance_id"]))
        selected = (
            str(state["operation"]) == operation
            and int(state["pose_idx"]) == pose_idx
            and selected_pattern is not None
            and int(selected_pattern) == int(pattern_index)
        )
        binding_model.model.AddHint(variable, int(selected))
        hinted += 1

    for instance_id, vars_by_idx in binding_model.binding_vars.items():
        if instance_id.startswith("jointmode::"):
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
        "hinted_variable_count": hinted,
        "warm_binding_choice_count": len(binding_choice),
        "warm_state_digest": stable_digest(fixed),
    }


def build_mode_joint_model(
    *,
    full_solution: Mapping[str, Mapping[str, Any]],
    warm_endpoint: Mapping[str, Any],
    fixed_state: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    inputs: Mapping[str, Any],
    blocks: Sequence[Mapping[str, Any]],
    selected_ids_by_block: Mapping[str, set[str]],
    e004: Any,
    e015: Any,
    conditional_mode_module: Any,
) -> dict[str, Any]:
    from src.models.routing_binding_context import build_routing_binding_context

    routing_context = build_routing_binding_context(
        full_solution,
        inputs["pools"],
        70,
        70,
    )
    (
        placement_solution,
        virtual_instances,
        virtual_metadata,
        block_metadata,
    ) = conditional_mode_owner_registration(
        full_solution=full_solution,
        inputs=inputs,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
    )
    plan = inputs["plan"]
    generic = inputs["generic"]
    binding_model = conditional_mode_module.ConditionalModeOwnerPortBindingModel(
        conditional_owner_metadata=virtual_metadata,
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
    binding_model.build(use_overload_separation=False)
    if binding_model.empty_binding_domain_instances:
        raise RuntimeError(
            "E041 outside native model has empty binding domains: "
            f"{binding_model.empty_binding_domain_instances}"
        )
    y_vars, z_vars, activation_stats = (
        binding_model.attach_mode_activation_variables(prefix="e041")
    )
    for block in block_metadata:
        block_id = str(block["block_id"])
        operations = [str(value) for value in block["operations"]]
        modes_by_destination = block["mode_pose_indices_by_destination"]
        for destination, pose_indices in enumerate(modes_by_destination):
            binding_model.model.Add(
                sum(
                    y_vars[(block_id, destination, mode_index, operation)]
                    for mode_index in range(len(pose_indices))
                    for operation in operations
                )
                == 1
            )
        for operation in operations:
            binding_model.model.Add(
                sum(
                    y_vars[(block_id, destination, mode_index, operation)]
                    for destination, pose_indices in enumerate(modes_by_destination)
                    for mode_index in range(len(pose_indices))
                )
                == int(block["operation_counts"][operation])
            )
        if fixed_state is not None:
            fixed_rows = [dict(row) for row in fixed_state[block_id]]
            if len(fixed_rows) != int(block["destination_count"]):
                raise RuntimeError(f"E041 {block_id} fixed-state width drift")
            for destination, selected in enumerate(fixed_rows):
                for mode_index, pose_idx in enumerate(modes_by_destination[destination]):
                    for operation in operations:
                        binding_model.model.Add(
                            y_vars[(block_id, destination, mode_index, operation)]
                            == int(
                                str(selected["operation"]) == operation
                                and int(selected["pose_idx"]) == int(pose_idx)
                            )
                        )

    compiled = e015.compile_shared_objective(
        binding_model=binding_model,
        routing_context=routing_context,
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        e004=e004,
    )
    hint_stats = add_mode_hints(
        binding_model=binding_model,
        y_vars=y_vars,
        z_vars=z_vars,
        warm_solution=full_solution,
        warm_endpoint=warm_endpoint,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
        pools=inputs["pools"],
    )
    proto = binding_model.model.Proto()
    return {
        "binding_model": binding_model,
        "routing_context": routing_context,
        "compiled": compiled,
        "y_vars": y_vars,
        "z_vars": z_vars,
        "blocks": block_metadata,
        "domain_stats": activation_stats,
        "native_domain_stats": binding_model.conditional_owner_domain_stats,
        "hint_stats": hint_stats,
        "model_size": {
            "variables": len(proto.variables),
            "constraints": len(proto.constraints),
            "mode_operation_variables": len(y_vars),
            "conditional_pattern_variables": len(z_vars),
            "outside_binding_owner_count": sum(
                not key.startswith("jointmode::")
                for key in binding_model.binding_domains
            ),
            "joint_binding_owner_count": sum(
                key.startswith("jointmode::")
                for key in binding_model.binding_domains
            ),
            "inactive_only_owner_count": sum(
                bool(row["inactive_only"]) for row in activation_stats
            ),
        },
        "conditional_owner_path": "prebuild_native_domain_with_mode_and_inactive",
    }


def solve_mode_joint(
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

    operation_by_block: dict[str, list[str]] = {}
    pose_idx_by_block: dict[str, list[int]] = {}
    selected_pattern_by_block: dict[str, list[dict[str, Any]]] = {}
    for block in built["blocks"]:
        block_id = str(block["block_id"])
        operations = [str(value) for value in block["operations"]]
        modes_by_destination = block["mode_pose_indices_by_destination"]
        operations_out: list[str] = []
        poses_out: list[int] = []
        patterns_out: list[dict[str, Any]] = []
        for destination, pose_indices in enumerate(modes_by_destination):
            selected = [
                (mode_index, operation)
                for mode_index in range(len(pose_indices))
                for operation in operations
                if solver.Value(
                    built["y_vars"][(
                        block_id,
                        destination,
                        mode_index,
                        operation,
                    )]
                )
                == 1
            ]
            if len(selected) != 1:
                raise RuntimeError(
                    f"E041 assignment extraction drift {block_id}/{destination}: "
                    f"{selected}"
                )
            mode_index, operation = selected[0]
            pose_idx = int(pose_indices[mode_index])
            operations_out.append(operation)
            poses_out.append(pose_idx)
            patterns = [
                pattern_index
                for (
                    row_block,
                    row_destination,
                    row_mode,
                    row_operation,
                    pattern_index,
                ), variable in built["z_vars"].items()
                if row_block == block_id
                and row_destination == destination
                and row_mode == mode_index
                and row_operation == operation
                and solver.Value(variable) == 1
            ]
            if len(patterns) != 1:
                raise RuntimeError(
                    f"E041 pattern extraction drift {block_id}/{destination}: "
                    f"{patterns}"
                )
            patterns_out.append(
                {
                    "destination": destination,
                    "mode_index": mode_index,
                    "pose_idx": pose_idx,
                    "operation": operation,
                    "pattern_index": int(patterns[0]),
                }
            )
        operation_by_block[block_id] = operations_out
        pose_idx_by_block[block_id] = poses_out
        selected_pattern_by_block[block_id] = patterns_out

    per_commodity: dict[str, int] = {}
    for commodity in built["compiled"]["commodities"]:
        value = sum(
            int(solver.Value(variable))
            for variable in built["compiled"]["mismatch_vars"][commodity].values()
        )
        per_commodity[commodity] = value
        if int(solver.Value(built["compiled"]["source_global"][commodity])) != 1:
            raise RuntimeError(f"E041 missing global source: {commodity}")
        if int(solver.Value(built["compiled"]["sink_global"][commodity])) != 1:
            raise RuntimeError(f"E041 missing global sink: {commodity}")
    if sum(per_commodity.values()) != int(result["objective"]):
        raise RuntimeError("E041 objective/per-commodity mismatch")

    binding_model = built["binding_model"]
    binding_model._solver = solver
    binding_model._status = status
    selection = binding_model.extract_selection()
    port_specs = binding_model.extract_port_specs()
    result.update(
        {
            "operation_by_block": operation_by_block,
            "pose_idx_by_block": pose_idx_by_block,
            "selected_pattern_by_block": selected_pattern_by_block,
            "per_commodity": per_commodity,
            "positive_commodity_count": sum(
                value > 0 for value in per_commodity.values()
            ),
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


def realize_mode_blocks(
    *,
    parent: Mapping[str, Mapping[str, Any]],
    blocks: Sequence[Mapping[str, Any]],
    operation_by_block: Mapping[str, Sequence[str]],
    pose_idx_by_block: Mapping[str, Sequence[int]],
    selected_ids_by_block: Mapping[str, set[str]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    child = {str(key): dict(value) for key, value in parent.items()}
    assigned_all: set[str] = set()
    for block in blocks:
        block_id = str(block["block_id"])
        operations = [str(value) for value in operation_by_block[block_id]]
        pose_indices = [int(value) for value in pose_idx_by_block[block_id]]
        if len(operations) != len(pose_indices):
            raise RuntimeError(f"E041 {block_id} realization width drift")
        selected_ids = selected_ids_by_block[block_id]
        source_ids_by_operation: dict[str, list[str]] = defaultdict(list)
        for instance_id in selected_ids:
            source_ids_by_operation[str(parent[instance_id]["operation_type"])].append(
                instance_id
            )
        destinations_by_operation: dict[str, list[int]] = defaultdict(list)
        for destination, operation in enumerate(operations):
            destinations_by_operation[operation].append(destination)
        if {
            key: len(value) for key, value in source_ids_by_operation.items()
        } != {
            key: len(value) for key, value in destinations_by_operation.items()
        }:
            raise RuntimeError(f"E041 {block_id} operation multiset drift")
        facility_type = str(block["facility_type"])
        assigned: set[str] = set()
        for operation in sorted(source_ids_by_operation):
            source_ids = sorted(source_ids_by_operation[operation])
            destinations = sorted(destinations_by_operation[operation])
            for source_id, destination in zip(source_ids, destinations, strict=True):
                pose_idx = pose_indices[destination]
                admitted = {
                    int(value)
                    for value in block["mode_pose_indices_by_destination"][destination]
                }
                if pose_idx not in admitted:
                    raise RuntimeError(
                        f"E041 selected pose outside admitted mode set: "
                        f"{block_id}/{destination}/{pose_idx}"
                    )
                pose = pools[facility_type][pose_idx]
                child[source_id] = e014.replacement_row(
                    source=parent[source_id],
                    pose=pose,
                    pose_idx=pose_idx,
                    instance_id=source_id,
                )
                assigned.add(source_id)
        if assigned != selected_ids:
            raise RuntimeError(f"E041 {block_id} realization coverage drift")
        assigned_all |= assigned
    expected = set().union(*selected_ids_by_block.values())
    if assigned_all != expected:
        raise RuntimeError("E041 cross-block realization coverage drift")
    return child


def run() -> dict[str, Any]:
    identity = verify_identity()
    e039 = import_module("zmd_e041_e039", E039_RUNNER)
    e038 = import_module("zmd_e041_e038", e039.E038_RUNNER)
    e037 = import_module("zmd_e041_e037", e038.E037_RUNNER)
    e036 = import_module("zmd_e041_e036", e037.E036_RUNNER)
    e035 = import_module("zmd_e041_e035", e036.E035_RUNNER)
    e001 = import_module("zmd_e041_e001", e035.E001_RUNNER)
    e002 = import_module("zmd_e041_e002", e035.E002_RUNNER)
    e004 = import_module("zmd_e041_e004", e035.E004_RUNNER)
    e014 = import_module("zmd_e041_e014", e035.E014_RUNNER)
    e015 = import_module("zmd_e041_e015", e035.E015_RUNNER)
    e027 = import_module("zmd_e041_e027", e035.E027_RUNNER)
    e031 = import_module("zmd_e041_e031", e035.E031_RUNNER)
    conditional_mode_module = import_module(
        "zmd_e041_conditional_mode",
        MODE_HELPER,
    )

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    solution_39 = solution_from_assignment(E039_ASSIGNMENT)
    solution_40 = solution_from_assignment(E040_ASSIGNMENT)
    endpoint_39 = load_json(E039_ENDPOINT)
    endpoint_40 = load_json(E040_ENDPOINT)
    if endpoint_39.get("status") != "OPTIMAL" or int(endpoint_39["objective"]) != 157:
        raise RuntimeError("E041 E039 endpoint drift")
    if endpoint_40.get("status") != "OPTIMAL" or int(endpoint_40["objective"]) != 154:
        raise RuntimeError("E041 E040 endpoint drift")

    occupied_39, _ = e014.base_occupancy(solution_39, inputs["pools"])
    occupied_40, _ = e014.base_occupancy(solution_40, inputs["pools"])
    if occupied_39 != occupied_40:
        raise RuntimeError("E041 calibration states do not share occupied bodies")

    result_39 = load_json(E039_RESULT)
    result_40 = load_json(E040_RESULT)
    blocks = [dict(row) for row in result_39["final_blocks"]]
    selected_ids_by_block = {
        str(block_id): {str(value) for value in values}
        for block_id, values in result_39["selected_instance_ids_by_block"].items()
    }
    all_selected_ids = set().union(*selected_ids_by_block.values())
    mode_enabled_ids = {
        str(target["source_instance_ids"][0])
        for target in result_40["selected_targets"]
        if target.get("source_instance_ids")
        and str(target["source_instance_ids"][0]) in all_selected_ids
        and str(target.get("facility_type", ""))
        not in {"power_pole", "boundary_storage_port", "protocol_core"}
    }
    blocks, mode_summary = enrich_blocks_with_modes(
        blocks=blocks,
        solution=solution_39,
        selected_ids_by_block=selected_ids_by_block,
        mode_enabled_ids=mode_enabled_ids,
        pools=inputs["pools"],
    )
    enabled_rows = [row for row in mode_summary if row["mode_enabled"]]
    if len(enabled_rows) != 9:
        raise RuntimeError(f"E041 mode-enabled destination drift: {len(enabled_rows)}")
    if sum(int(row["mode_count"]) > 1 for row in enabled_rows) != 9:
        raise RuntimeError("E041 selected destination lacks same-footprint alternatives")

    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(mandatory, list) or not isinstance(generic, Mapping):
        raise RuntimeError("E041 frozen instance/generic payload drift")
    exchangeability = e031.exchangeability_audit(
        neighborhoods=blocks,
        mandatory=mandatory,
        generic=generic,
    )
    if exchangeability.get("status") != "PASS":
        raise RuntimeError("E041 exchangeability audit failed")

    calibrations: list[dict[str, Any]] = []
    for index, (label, solution, endpoint, expected) in enumerate(
        (
            ("e039_frozen_pose", solution_39, endpoint_39, E039_OBJECTIVE),
            ("e040_same_body_mode", solution_40, endpoint_40, E040_OBJECTIVE),
        ),
        1,
    ):
        fixed = fixed_state_for_solution(
            solution=solution,
            blocks=blocks,
            selected_ids_by_block=selected_ids_by_block,
            pools=inputs["pools"],
        )
        built = build_mode_joint_model(
            full_solution=solution,
            warm_endpoint=endpoint,
            fixed_state=fixed,
            inputs=inputs,
            blocks=blocks,
            selected_ids_by_block=selected_ids_by_block,
            e004=e004,
            e015=e015,
            conditional_mode_module=conditional_mode_module,
        )
        solved = solve_mode_joint(
            built,
            time_limit_seconds=CALIBRATION_SECONDS,
            random_seed=41010 + index,
        )
        calibration = {
            "label": label,
            "expected_objective": expected,
            "fixed_state": json_safe(fixed),
            "solve": {
                key: value
                for key, value in solved.items()
                if key
                not in {
                    "joint_selection",
                    "joint_port_specs",
                    "selected_pattern_by_block",
                }
            },
            "model_size": built["model_size"],
            "hint_stats": built["hint_stats"],
        }
        calibrations.append(calibration)
        if solved["status"] != "OPTIMAL" or int(solved["objective"]) != expected:
            return {
                "schema": "zmd_zero_condition_e041_joint_port_mode_assignment_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "verdict": "PORT_MODE_JOINT_CALIBRATION_REJECTED",
                "identity": identity,
                "mode_summary": mode_summary,
                "exchangeability_audit": exchangeability,
                "calibrations": calibrations,
                "failed_calibration": label,
                "best_child": None,
                "routing": {"status": "NOT_REACHED_CALIBRATION_REJECTED"},
                "decision": "REFINE_PORT_MODE_CONDITIONAL_OWNER_MODEL",
                "truth_boundary": (
                    "Fidelity calibration only; no free scientific solve admitted."
                ),
                "ledger_effect": "none",
            }

    free_built = build_mode_joint_model(
        full_solution=solution_40,
        warm_endpoint=endpoint_40,
        fixed_state=None,
        inputs=inputs,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
        e004=e004,
        e015=e015,
        conditional_mode_module=conditional_mode_module,
    )
    free_solve = solve_mode_joint(
        free_built,
        time_limit_seconds=FREE_SOLVE_SECONDS,
        random_seed=41999,
    )
    common = {
        "schema": "zmd_zero_condition_e041_joint_port_mode_assignment_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "parent_objective": E040_OBJECTIVE,
        "fixed_body_digest": stable_digest(sorted(occupied_39)),
        "mode_enabled_destination_count": len(enabled_rows),
        "mode_summary": mode_summary,
        "final_blocks": json_safe(blocks),
        "selected_instance_ids_by_block": {
            key: sorted(value) for key, value in selected_ids_by_block.items()
        },
        "exchangeability_audit": exchangeability,
        "calibrations": calibrations,
        "model_size": free_built["model_size"],
        "domain_stats": free_built["domain_stats"],
        "native_domain_stats": free_built["native_domain_stats"],
        "hint_stats": free_built["hint_stats"],
        "conditional_owner_path": free_built["conditional_owner_path"],
        "free_solve": {
            key: value
            for key, value in free_solve.items()
            if key
            not in {
                "joint_selection",
                "joint_port_specs",
                "selected_pattern_by_block",
            }
        },
        "truth_boundary": (
            "One fixed occupied body geometry; same-footprint modes are admitted "
            "for nine E040-selected destinations inside the E039 25-footprint "
            "operation-assignment context."
        ),
        "ledger_effect": "none",
    }
    if free_solve["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return {
            **common,
            "verdict": "PORT_MODE_JOINT_NONTERMINAL",
            "best_child": None,
            "routing": {"status": "NOT_REACHED_NO_FEASIBLE_JOINT_STATE"},
            "decision": "CONTINUE_OR_REFORMULATE_PORT_MODE_JOINT_SOLVE",
        }

    child = realize_mode_blocks(
        parent=solution_40,
        blocks=blocks,
        operation_by_block=free_solve["operation_by_block"],
        pose_idx_by_block=free_solve["pose_idx_by_block"],
        selected_ids_by_block=selected_ids_by_block,
        pools=inputs["pools"],
        e014=e014,
    )
    child_occupied, _ = e014.base_occupancy(child, inputs["pools"])
    if child_occupied != occupied_39:
        raise RuntimeError("E041 concrete realization changed occupied bodies")
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
        raise RuntimeError("E041 concrete realization broke power")

    endpoint = e027.materialize_shared_endpoint(
        solution=child,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=42001,
    )
    if int(endpoint["objective"]) != int(free_solve["objective"]):
        raise RuntimeError(
            "E041 joint/fixed materialization objective drift: "
            f"{free_solve['objective']} != {endpoint['objective']}"
        )

    reference_state = fixed_state_for_solution(
        solution=solution_39,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
        pools=inputs["pools"],
    )
    selected_state = {
        block_id: [
            {
                "destination": destination,
                "operation": str(operation),
                "pose_idx": int(free_solve["pose_idx_by_block"][block_id][destination]),
            }
            for destination, operation in enumerate(operations)
        ]
        for block_id, operations in free_solve["operation_by_block"].items()
    }
    changes: list[dict[str, Any]] = []
    for block_id, rows in selected_state.items():
        for row in rows:
            destination = int(row["destination"])
            old = reference_state[block_id][destination]
            if (
                str(old["operation"]) != str(row["operation"])
                or int(old["pose_idx"]) != int(row["pose_idx"])
            ):
                changes.append(
                    {
                        "block_id": block_id,
                        "destination": destination,
                        "old_operation": str(old["operation"]),
                        "new_operation": str(row["operation"]),
                        "old_pose_idx": int(old["pose_idx"]),
                        "new_pose_idx": int(row["pose_idx"]),
                    }
                )

    joint_witness = {
        "schema": "zmd_zero_condition_e041_joint_witness_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": free_solve["status"],
        "objective": int(free_solve["objective"]),
        "operation_by_block": free_solve["operation_by_block"],
        "pose_idx_by_block": free_solve["pose_idx_by_block"],
        "selected_pattern_by_block": free_solve["selected_pattern_by_block"],
        "joint_selection": free_solve["joint_selection"],
        "joint_port_specs": free_solve["joint_port_specs"],
        "per_commodity": free_solve["per_commodity"],
        "conditional_owner_path": free_built["conditional_owner_path"],
        "ledger_effect": "none",
    }
    dump_exclusive(JOINT_WITNESS_PATH, joint_witness)
    dump_exclusive(
        BEST_ASSIGNMENT_PATH,
        {
            "schema": "zmd_zero_condition_e041_best_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_BODY_SHARED_BINDING_OPTIMAL"
            if free_solve["status"] == "OPTIMAL"
            else "FIXED_BODY_SHARED_BINDING_FEASIBLE_NONTERMINAL",
            "parent_objective": E040_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "operation_by_block": free_solve["operation_by_block"],
            "pose_idx_by_block": free_solve["pose_idx_by_block"],
            "changes_from_e039": changes,
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
        verdict = "PORT_MODE_JOINT_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif free_solve["status"] == "OPTIMAL" and objective < E040_OBJECTIVE:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "PORT_MODE_JOINT_MATERIAL_IMPROVEMENT"
        decision = "RECOMPUTE_RESIDUAL_FOR_MODE_OR_BODY_EXPANSION"
    elif free_solve["status"] == "OPTIMAL":
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "PORT_MODE_JOINT_CONTEXT_SATURATED"
        decision = "BUILD_SIMULTANEOUS_BODY_GEOMETRY_NEIGHBORHOOD"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "PORT_MODE_JOINT_FEASIBLE_NONTERMINAL"
        decision = "CONTINUE_OR_REFORMULATE_PORT_MODE_JOINT_SOLVE"

    return {
        **common,
        "verdict": verdict,
        "best_child": {
            "objective": objective,
            "delta_from_parent": objective - E040_OBJECTIVE,
            "operation_by_block": free_solve["operation_by_block"],
            "pose_idx_by_block": free_solve["pose_idx_by_block"],
            "changes_from_e039": changes,
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
        raise FileExistsError("refusing to overwrite E041 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "calibrations": [
                        {
                            "label": row["label"],
                            "expected": row["expected_objective"],
                            "status": row["solve"]["status"],
                            "objective": row["solve"].get("objective"),
                        }
                        for row in result["calibrations"]
                    ],
                    "mode_enabled_destination_count": result[
                        "mode_enabled_destination_count"
                    ],
                    "free_status": result.get("free_solve", {}).get("status"),
                    "free_objective": result.get("free_solve", {}).get("objective"),
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
            "schema": "zmd_zero_condition_e041_joint_port_mode_assignment_failure_v1",
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
