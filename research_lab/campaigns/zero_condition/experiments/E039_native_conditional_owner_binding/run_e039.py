#!/usr/bin/env python3
"""E039: repair the native conditional-owner seam and rerun frozen E038."""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
EXPERIMENT_DIR = Path(__file__).resolve().parent
OUT = ROOT / "research_lab/local/zero_condition/E039_native_conditional_owner_binding/run-002"
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
E036_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E036_three_block_joint_assignment/run-001/RESULT.json"
)
SECOND_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E036_three_block_joint_assignment/run-001/BEST_ASSIGNMENT.json"
)
SECOND_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E036_three_block_joint_assignment/run-001/BEST_ENDPOINT.json"
)
E038_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E038_merged_3x3_assignment/run_e038.py"
)
CONDITIONAL_OWNER_MODULE = EXPERIMENT_DIR / "conditional_owner_binding.py"
BINDING_SOURCE = ROOT / "src/models/binding_subproblem.py"
PORT_BINDING_SOURCE = ROOT / "src/models/port_binding.py"

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "269000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E037_RESULT: "450bd05565afc96cbd071d924405f85d4dc5bc7eee1af4e89cdb574566cfe56f",
    FIRST_ASSIGNMENT: "e06cb7e2078c398ee2eee4bdf61105bee3d9422a8fca355324f7296d04979640",
    FIRST_ENDPOINT: "4899d69713790483058945e1b568dd5a2fca12455dc8bfb844309ce18ad20383",
    E036_RESULT: "e000e1dba3eb3eea208bbc75a8a41eb9faf6001e51eade2308ef43ba6eaff27c",
    SECOND_ASSIGNMENT: "a2b263a15a75d446154d7288c8fa499566d8bb565cd95e5c92c01cf782573116",
    SECOND_ENDPOINT: "24d675ea298254cba8ab34983f723d7b7e1663b06ed3957df014c0ef00c4a96e",
    E038_RUNNER: "0bd0e7d9f5453aeba0846311a27363cb5a838d31f80d7f4824cf0c07d8b66deb",
    BINDING_SOURCE: "b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba",
    PORT_BINDING_SOURCE: "9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53",
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
EXPECTED_HELPER_SHA256 = "3f86dbc5f339c80566e7d95e02d75009cdd8f377db2d1364615c3f23058caa11"

PARENT_OBJECTIVE = 157
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
        raise RuntimeError("E039 must run on research/main")
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
    helper_sha = sha256_file(CONDITIONAL_OWNER_MODULE)
    if helper_sha != EXPECTED_HELPER_SHA256:
        raise RuntimeError(
            "conditional-owner helper drift: "
            f"{helper_sha} != {EXPECTED_HELPER_SHA256}"
        )
    checked[str(CONDITIONAL_OWNER_MODULE)] = helper_sha
    first = load_json(E037_RESULT)
    second = load_json(E036_RESULT)
    if first.get("verdict") != "MERGED_6X4_JOINT_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E037 trigger verdict drift")
    if int(first["best_child"]["objective"]) != 157:
        raise RuntimeError("E037 objective drift")
    if int(second["best_child"]["objective"]) != 159:
        raise RuntimeError("E036 regression objective drift")
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


def build_frozen_blocks(
    *,
    first_solution: Mapping[str, Mapping[str, Any]],
    first_endpoint: Mapping[str, Any],
    inputs: Mapping[str, Any],
    mandatory: Sequence[Mapping[str, Any]],
    e013: Any,
    e031: Any,
    e035: Any,
    e038: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
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
    addition = e038.select_additional_3x3(
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
    merged = e038.refresh_block_payloads(
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
    refreshed_5x5 = e038.refresh_block_payloads(
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
    refreshed_6x4 = e038.refresh_block_payloads(
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
    return blocks, addition, {
        "observation_count": len(observations),
        "literal_count": len(literals),
    }


def conditional_owner_registration(
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
        payloads = [dict(row) for row in block["selected_literal_payloads"]]
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
                    "E039 conditional generic slots are outside the admitted scope: "
                    f"operation={operation} in={generic_inputs} out={generic_outputs}"
                )
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
                virtual_metadata[virtual_owner] = {
                    "block_id": block_id,
                    "destination": destination,
                    "operation": operation,
                    "pose_idx": pose_idx,
                    "facility_type": facility_type,
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
    return placement_solution, virtual_instances, virtual_metadata, block_metadata


def build_faithful_joint_model(
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
    conditional_module: Any,
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
    ) = conditional_owner_registration(
        full_solution=full_solution,
        inputs=inputs,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
    )
    plan = inputs["plan"]
    generic = inputs["generic"]
    binding_model = conditional_module.ConditionalOwnerPortBindingModel(
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
            "E039 outside native model has empty binding domains: "
            f"{binding_model.empty_binding_domain_instances}"
        )
    y_vars, z_vars, activation_stats = binding_model.attach_activation_variables(
        prefix="e039"
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
                raise RuntimeError(f"E039 {block_id} fixed assignment width drift")
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
        "domain_stats": activation_stats,
        "native_domain_stats": binding_model.conditional_owner_domain_stats,
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
            "inactive_only_owner_count": sum(
                bool(row["inactive_only"]) for row in activation_stats
            ),
        },
        "conditional_owner_path": "prebuild_native_domain_with_inactive",
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e038 = import_module("zmd_e039_e038", E038_RUNNER)
    e037 = import_module("zmd_e039_e037", e038.E037_RUNNER)
    e036 = import_module("zmd_e039_e036", e037.E036_RUNNER)
    e035 = import_module("zmd_e039_e035", e036.E035_RUNNER)
    e001 = import_module("zmd_e039_e001", e035.E001_RUNNER)
    e002 = import_module("zmd_e039_e002", e035.E002_RUNNER)
    e004 = import_module("zmd_e039_e004", e035.E004_RUNNER)
    e013 = import_module("zmd_e039_e013", e035.E013_RUNNER)
    e014 = import_module("zmd_e039_e014", e035.E014_RUNNER)
    e015 = import_module("zmd_e039_e015", e035.E015_RUNNER)
    e027 = import_module("zmd_e039_e027", e035.E027_RUNNER)
    e031 = import_module("zmd_e039_e031", e035.E031_RUNNER)
    conditional_module = import_module(
        "zmd_e039_conditional_owner",
        CONDITIONAL_OWNER_MODULE,
    )

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    first_solution = e035.solution_from_assignment(FIRST_ASSIGNMENT)
    second_solution = e035.solution_from_assignment(SECOND_ASSIGNMENT)
    first_endpoint = load_json(FIRST_ENDPOINT)
    second_endpoint = load_json(SECOND_ENDPOINT)
    if first_endpoint.get("status") != "OPTIMAL" or int(first_endpoint["objective"]) != 157:
        raise RuntimeError("E039 first warm endpoint drift")
    if second_endpoint.get("status") != "OPTIMAL" or int(second_endpoint["objective"]) != 159:
        raise RuntimeError("E039 second warm endpoint drift")
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(mandatory, list) or not isinstance(generic, Mapping):
        raise RuntimeError("E039 frozen instance/generic payload drift")

    blocks, addition, surface_summary = build_frozen_blocks(
        first_solution=first_solution,
        first_endpoint=first_endpoint,
        inputs=inputs,
        mandatory=mandatory,
        e013=e013,
        e031=e031,
        e035=e035,
        e038=e038,
    )
    exchangeability = e031.exchangeability_audit(
        neighborhoods=blocks,
        mandatory=mandatory,
        generic=generic,
    )
    if exchangeability.get("status") != "PASS":
        raise RuntimeError("E039 exchangeability audit failed")

    first_selected_ids = e038.selected_ids_for_solution(
        blocks=blocks,
        solution=first_solution,
    )
    calibrations: list[dict[str, Any]] = []
    for index, (label, solution, endpoint, expected) in enumerate(
        (
            ("e037", first_solution, first_endpoint, 157),
            ("e036_regression", second_solution, second_endpoint, 159),
        ),
        1,
    ):
        selected_ids = e038.selected_ids_for_solution(
            blocks=blocks,
            solution=solution,
        )
        fixed = {
            str(block["block_id"]): e035.operation_assignment_for_solution(
                solution=solution,
                block=block,
                selected_ids=selected_ids[str(block["block_id"])],
            )
            for block in blocks
        }
        built = build_faithful_joint_model(
            full_solution=solution,
            warm_endpoint=endpoint,
            fixed_assignments=fixed,
            inputs=inputs,
            blocks=blocks,
            selected_ids_by_block=selected_ids,
            e004=e004,
            e015=e015,
            e035=e035,
            conditional_module=conditional_module,
        )
        solved = e035.solve_joint(
            built,
            time_limit_seconds=CALIBRATION_SECONDS,
            random_seed=39010 + index,
        )
        calibration = {
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
        calibrations.append(calibration)
        if solved["status"] != "OPTIMAL" or int(solved["objective"]) != expected:
            return {
                "schema": "zmd_zero_condition_e039_native_conditional_owner_binding_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "verdict": "CONDITIONAL_OWNER_CALIBRATION_REJECTED",
                "identity": identity,
                "surface_summary": surface_summary,
                "additional_3x3": json_safe(addition),
                "final_blocks": json_safe(blocks),
                "exchangeability_audit": exchangeability,
                "calibrations": calibrations,
                "failed_calibration": label,
                "best_child": None,
                "routing": {"status": "NOT_REACHED_CALIBRATION_REJECTED"},
                "decision": "REFINE_CONDITIONAL_OWNER_COMPILER",
                "truth_boundary": (
                    "Fidelity calibration only; no free scientific solve admitted."
                ),
                "ledger_effect": "none",
            }

    free_built = build_faithful_joint_model(
        full_solution=first_solution,
        warm_endpoint=first_endpoint,
        fixed_assignments=None,
        inputs=inputs,
        blocks=blocks,
        selected_ids_by_block=first_selected_ids,
        e004=e004,
        e015=e015,
        e035=e035,
        conditional_module=conditional_module,
    )
    free_solve = e035.solve_joint(
        free_built,
        time_limit_seconds=FREE_SOLVE_SECONDS,
        random_seed=39999,
    )
    common = {
        "schema": "zmd_zero_condition_e039_native_conditional_owner_binding_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "parent_objective": PARENT_OBJECTIVE,
        "surface_summary": surface_summary,
        "additional_3x3": json_safe(addition),
        "final_blocks": json_safe(blocks),
        "exchangeability_audit": exchangeability,
        "selected_instance_ids_by_block": {
            key: sorted(value) for key, value in first_selected_ids.items()
        },
        "calibrations": calibrations,
        "model_size": free_built["model_size"],
        "domain_stats": free_built["domain_stats"],
        "native_domain_stats": free_built["native_domain_stats"],
        "hint_stats": free_built["hint_stats"],
        "conditional_owner_path": free_built["conditional_owner_path"],
        "free_solve": {
            key: value
            for key, value in free_solve.items()
            if key not in {"joint_selection", "joint_port_specs"}
        },
        "truth_boundary": (
            "One fixed occupied geometry; native conditional-owner exact domains "
            "cover the frozen E038 merged 3x3, 5x5, and merged 6x4 blocks."
        ),
        "ledger_effect": "none",
    }
    if free_solve["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return {
            **common,
            "verdict": "NATIVE_CONDITIONAL_OWNER_JOINT_NONTERMINAL",
            "best_child": None,
            "routing": {"status": "NOT_REACHED_NO_FEASIBLE_JOINT_STATE"},
            "decision": "INSPECT_OR_REFORMULATE_NATIVE_EXTENSION",
        }

    child = e035.realize_blocks(
        parent=first_solution,
        blocks=blocks,
        operation_by_block=free_solve["operation_by_block"],
        selected_ids_by_block=first_selected_ids,
        pools=inputs["pools"],
        e014=e014,
    )
    first_occupied, _ = e014.base_occupancy(first_solution, inputs["pools"])
    child_occupied, _ = e014.base_occupancy(child, inputs["pools"])
    if child_occupied != first_occupied:
        raise RuntimeError("E039 concrete realization changed occupied geometry")
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
        raise RuntimeError("E039 concrete realization broke power")

    endpoint = e027.materialize_shared_endpoint(
        solution=child,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=40001,
    )
    if int(endpoint["objective"]) != int(free_solve["objective"]):
        raise RuntimeError(
            "E039 joint/fixed materialization objective drift: "
            f"{free_solve['objective']} != {endpoint['objective']}"
        )

    joint_witness = {
        "schema": "zmd_zero_condition_e039_joint_witness_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": free_solve["status"],
        "objective": int(free_solve["objective"]),
        "operation_by_block": free_solve["operation_by_block"],
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
            "schema": "zmd_zero_condition_e039_best_assignment_v1",
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
        verdict = "NATIVE_CONDITIONAL_OWNER_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif free_solve["status"] == "OPTIMAL" and objective < PARENT_OBJECTIVE:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "NATIVE_CONDITIONAL_OWNER_MATERIAL_IMPROVEMENT"
        decision = "RECOMPUTE_RESIDUAL_FROM_FAITHFUL_EXTENSION"
    elif free_solve["status"] == "OPTIMAL":
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "NATIVE_CONDITIONAL_OWNER_CONTEXT_SATURATED"
        decision = "RELEASE_PROBLEM_DERIVED_GEOMETRY_NEIGHBORHOOD"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "NATIVE_CONDITIONAL_OWNER_FEASIBLE_NONTERMINAL"
        decision = "CONTINUE_OR_REFORMULATE_NATIVE_SOLVE"

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
        raise FileExistsError("refusing to overwrite E039 outputs")
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
            "schema": "zmd_zero_condition_e039_native_conditional_owner_binding_failure_v1",
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
