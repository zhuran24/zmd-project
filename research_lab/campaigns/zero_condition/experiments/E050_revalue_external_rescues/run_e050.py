#!/usr/bin/env python3
"""E050: faithfully revalue three E049 external-rescue pose states."""

from __future__ import annotations

from collections import Counter
import copy
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
OUT = ROOT / "research_lab/local/zero_condition/E050_revalue_external_rescues/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E046_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E046_objective145_integrated_geometry_portfolio/"
    "run-001/RESULT.json"
)
PARENT_ASSIGNMENT = E046_RESULT.with_name("SEED_A_BEST_ASSIGNMENT.json")
PARENT_ENDPOINT = E046_RESULT.with_name("SEED_A_BEST_ENDPOINT.json")
E046_ORDINARY_ASSIGNMENT = E046_RESULT.with_name("SEED_01_ASSIGNMENT.json")
E046_SEED_A_CHECKPOINT = E046_RESULT.with_name("SEED_A.json")
E049_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E049_external_rescue_graph/run-001/RESULT.json"
)
SEED_ASSIGNMENTS = [
    E049_RESULT.with_name(f"SEED_{index:02d}_ASSIGNMENT.json")
    for index in range(1, 4)
]
SEED_ENDPOINTS = [
    E049_RESULT.with_name(f"SEED_{index:02d}_ENDPOINT.json")
    for index in range(1, 4)
]

E048_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E048_revalue_body_pair_geometries/run_e048.py"
)
E049_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E049_external_rescue_graph/run_e049.py"
)
E046_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E046_objective145_integrated_geometry_portfolio/run_e046.py"
)
E045_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E045_revalue_objective146_geometries/run_e045.py"
)
E043_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E043_geometry_conditioned_joint_middle/run_e043.py"
)
E041_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E041_joint_port_mode_assignment/run_e041.py"
)
E041_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E041_joint_port_mode_assignment/conditional_mode_owner_binding.py"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E001_pocket_cut_replay/run_experiment.py"
)
E002_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E002_component_commodity_core/run_component_core.py"
)
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E004_component_mismatch_atlas/run_e004.py"
)
E014_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E014_fixed_outside_mobility/run_e014.py"
)
E015_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E015_shared_binding_gradient/run_e015.py"
)
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E027_final_unary_discriminator/run_e027.py"
)
E031_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E031_bounded_assignment_neighborhood/run_e031.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "280000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E046_RESULT: "cd9c45fd0c57af15306329758ad80ecf14962ba27c680cda91b0c4e8cebf59c0",
    PARENT_ASSIGNMENT: "cb67a16cc022bed9cd332aebf65962cda1fdf819ecac4b8d768f7ae6738198f4",
    PARENT_ENDPOINT: "eabbd025a69e18e905604e47f72076af11317f99c5b03d6c0ca601f0190ad59e",
    E046_ORDINARY_ASSIGNMENT: "2004ef98fb8da184d938315ffac000ab0dd581faaa2a3c1a9a1e53d9ae9fedbd",
    E046_SEED_A_CHECKPOINT: "4df5e5686ac73001c88d24a5767b60aa05179983f5b4630fcbdefc64a214f88e",
    E049_RESULT: "23f6fb09bb81a24aaade376483059f6329e9dfd592409ad5391cc468fddee662",
    SEED_ASSIGNMENTS[0]: "46182a6e7a3585d091c60d399cf0b301960d5f1e913d49292a6a2b647cf8ead3",
    SEED_ASSIGNMENTS[1]: "e243e07fd3f471dd918b81cafa38b2f7d15bf9114538f185db2fc2aee8b9668f",
    SEED_ASSIGNMENTS[2]: "17626085e2fe13ac452eeceb2b03db516668ea14d82c40f49076da9d199f1a3c",
    SEED_ENDPOINTS[0]: "bdf813c969c8991c294a9b64b5befc9d8e08805532e59f5cf0f49966485e55c6",
    SEED_ENDPOINTS[1]: "9370569cac042911268f6404675ef21746201abe0b87e768cb5d2a6b4d05b414",
    SEED_ENDPOINTS[2]: "907fa3242501240ce8aa6caa480221d87b2caae213db6536196201bd4a1fb361",
    E048_RUNNER: "97fae12907ce3a2ef3404c73cbb9dfa0e2fd8d60bfc3a7dffae72a09ccc4f7dd",
    E049_RUNNER: "1f5d5fe11d21434d8d7a3e97d99958c04420e927698241eb437f8d39f225067a",
    E046_RUNNER: "b15363594654d497dc18f2a53eb12b75cc1ce0bedd3c2149acd9c40649d69648",
    E045_RUNNER: "8ba3886ef205e682e3e6e54d1905fecb9033ddc5e86fa0c3c252e61f0df1e02b",
    E043_RUNNER: "a81cd8a762f29fad5c1a9f1c587f3bc90c4abc099aa97ccadedee2235da34d26",
    E041_RUNNER: "5731b294e5c3070617d3a29e8912e4f859da207c6f183354ad9c7194f2d54b06",
    E041_HELPER: "98464fc5c9ee181a69392e582c2194edd0c213965b6c62672ece190fb1370dad",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    E031_RUNNER: "ba35d569dc1a514da83b46721cb53c3f25386b2d776c70ac4cfae7f7c4d29b18",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

PARENT_OBJECTIVE = 144
EXPECTED_FIXED_OBJECTIVES = [143, 143, 144]


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
        raise RuntimeError("E050 must run on research/main")
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
    parent = load_json(PARENT_ENDPOINT)
    e049 = load_json(E049_RESULT)
    if parent.get("status") != "OPTIMAL" or int(parent["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E050 parent endpoint drift")
    if e049.get("verdict") != "EXTERNAL_RESCUE_RELATIONS_CONFIRMED":
        raise RuntimeError("E050 E049 trigger verdict drift")
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


def prepare_blocks_for_pose_pair(
    *,
    base_solution: Mapping[str, Mapping[str, Any]],
    seed_solution: Mapping[str, Mapping[str, Any]],
    result_41: Mapping[str, Any],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    e041: Any,
    e043: Any,
) -> tuple[
    list[dict[str, Any]],
    dict[str, set[str]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    blocks = [copy.deepcopy(row) for row in result_41["final_blocks"]]
    selected_ids_by_block = {
        str(block_id): {str(value) for value in values}
        for block_id, values in result_41["selected_instance_ids_by_block"].items()
    }
    base_enabled = {
        (str(row["block_id"]), int(row["destination"]))
        for row in result_41["mode_summary"]
        if bool(row["mode_enabled"])
    }
    pose_changed = [
        instance_id
        for instance_id in sorted(seed_solution)
        if int(seed_solution[instance_id]["pose_idx"])
        != int(base_solution[instance_id]["pose_idx"])
    ]
    if len(pose_changed) != 2:
        raise RuntimeError(f"E050 pose change count drift: {pose_changed}")
    body_changed = {
        instance_id: (
            e041.body_cells(
                pools=pools,
                facility_type=str(seed_solution[instance_id]["facility_type"]),
                pose_idx=int(seed_solution[instance_id]["pose_idx"]),
            )
            != e041.body_cells(
                pools=pools,
                facility_type=str(base_solution[instance_id]["facility_type"]),
                pose_idx=int(base_solution[instance_id]["pose_idx"]),
            )
        )
        for instance_id in pose_changed
    }
    if not any(body_changed.values()):
        raise RuntimeError("E050 rescue seed changes no occupied body")
    changed_set = set(pose_changed)
    changed_locations: dict[str, tuple[str, int]] = {}

    for block in blocks:
        block_id = str(block["block_id"])
        base_states = e041.destination_state_for_solution(
            solution=base_solution,
            block=block,
            selected_ids=selected_ids_by_block[block_id],
            pools=pools,
        )
        payloads: list[dict[str, Any]] = []
        source_ids: list[str] = []
        for destination, state in enumerate(base_states):
            instance_id = str(state["instance_id"])
            payloads.append(
                e043.pose_payload(
                    instance_id=instance_id,
                    row=seed_solution[instance_id],
                    pools=pools,
                )
            )
            source_ids.append(instance_id)
            if instance_id in changed_set:
                changed_locations[instance_id] = (block_id, destination)
        block["selected_literal_payloads"] = payloads
        block["selected_literals"] = [
            str(payload["literal_key"]) for payload in payloads
        ]
        block["source_instance_ids_by_destination"] = source_ids
        block["selected_literal_count"] = len(payloads)
        block["selection_digest"] = stable_digest(payloads)

    for instance_id in pose_changed:
        if instance_id in changed_locations:
            continue
        row = seed_solution[instance_id]
        block_id = f"rescue_singleton::{instance_id}"
        if block_id in selected_ids_by_block:
            raise RuntimeError(f"E050 duplicate rescue singleton: {block_id}")
        payload = e043.pose_payload(
            instance_id=instance_id,
            row=row,
            pools=pools,
        )
        singleton = {
            "block_id": block_id,
            "facility_type": str(row["facility_type"]),
            "operation_multiset": {str(row["operation_type"]): 1},
            "operation_diversity": 1,
            "selected_literal_count": 1,
            "selected_literal_payloads": [payload],
            "selected_literals": [str(payload["literal_key"])],
            "source_instance_ids_by_destination": [instance_id],
            "selection_digest": stable_digest([payload]),
            "semantic_permutation_count_including_identity": 1,
            "owner_refresh": "external_rescue_pose_pair",
        }
        blocks.append(singleton)
        selected_ids_by_block[block_id] = {instance_id}
        changed_locations[instance_id] = (block_id, 0)

    if set(changed_locations) != changed_set:
        raise RuntimeError("E050 changed-location coverage drift")
    enabled = set(base_enabled)
    enabled.update(changed_locations.values())
    mode_summary: list[dict[str, Any]] = []
    for block in blocks:
        block_id = str(block["block_id"])
        facility_type = str(block["facility_type"])
        pool = pools[facility_type]
        modes_by_destination: list[list[int]] = []
        for destination, payload in enumerate(block["selected_literal_payloads"]):
            current_pose_idx = int(payload["pose_idx"])
            current_body = e041.body_cells(
                pools=pools,
                facility_type=facility_type,
                pose_idx=current_pose_idx,
            )
            if (block_id, destination) in enabled:
                modes = [
                    pose_idx
                    for pose_idx in range(len(pool))
                    if e041.body_cells(
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
                    f"E050 current pose missing from modes: {block_id}/{destination}"
                )
            modes_by_destination.append(modes)
            mode_summary.append(
                {
                    "block_id": block_id,
                    "destination": destination,
                    "source_instance_id": str(
                        block["source_instance_ids_by_destination"][destination]
                    ),
                    "facility_type": facility_type,
                    "current_pose_idx": current_pose_idx,
                    "mode_enabled": (block_id, destination) in enabled,
                    "mode_pose_indices": modes,
                    "mode_count": len(modes),
                    "body_digest": stable_digest(sorted(current_body)),
                }
            )
        block["mode_pose_indices_by_destination"] = modes_by_destination

    all_sets = list(selected_ids_by_block.values())
    if len(set().union(*all_sets)) != sum(len(values) for values in all_sets):
        raise RuntimeError("E050 selected instance overlap")
    original_context_ids = {
        value
        for values in result_41["selected_instance_ids_by_block"].values()
        for value in values
    }
    return (
        blocks,
        selected_ids_by_block,
        mode_summary,
        {
            "pose_changed_instance_ids": pose_changed,
            "body_changed": body_changed,
            "changed_locations": {
                instance_id: {
                    "block_id": changed_locations[instance_id][0],
                    "destination": changed_locations[instance_id][1],
                }
                for instance_id in pose_changed
            },
            "inside_original_assignment_context": {
                instance_id: instance_id in original_context_ids
                for instance_id in pose_changed
            },
        },
    )


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e048 = import_module("zmd_e050_e048", E048_RUNNER)
    e046 = import_module("zmd_e050_e046", E046_RUNNER)
    e045 = import_module("zmd_e050_e045", E045_RUNNER)
    e043 = import_module("zmd_e050_e043", E043_RUNNER)
    e041 = import_module("zmd_e050_e041", E041_RUNNER)
    e001 = import_module("zmd_e050_e001", E001_RUNNER)
    e002 = import_module("zmd_e050_e002", E002_RUNNER)
    e004 = import_module("zmd_e050_e004", E004_RUNNER)
    e014 = import_module("zmd_e050_e014", E014_RUNNER)
    e015 = import_module("zmd_e050_e015", E015_RUNNER)
    e027 = import_module("zmd_e050_e027", E027_RUNNER)
    e031 = import_module("zmd_e050_e031", E031_RUNNER)
    conditional_mode_module = import_module(
        "zmd_e050_conditional_mode",
        E041_HELPER,
    )

    for path, expected in e048.EXPECTED_HASHES.items():
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(
                f"E050 inherited E048 input drift for {path}: {actual} != {expected}"
            )

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent_solution = e041.solution_from_assignment(PARENT_ASSIGNMENT)
    context_144 = e048.reconstruct_objective144_context(
        e041=e041,
        e043=e043,
        e045=e045,
        e046=e046,
        inputs=inputs,
    )
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(mandatory, list) or not isinstance(generic, Mapping):
        raise RuntimeError("E050 frozen instance/generic payload drift")

    seed_inputs: list[tuple[str, dict[str, dict[str, Any]], dict[str, Any], int]] = []
    for index, (assignment_path, endpoint_path, expected) in enumerate(
        zip(SEED_ASSIGNMENTS, SEED_ENDPOINTS, EXPECTED_FIXED_OBJECTIVES, strict=True),
        1,
    ):
        solution = e041.solution_from_assignment(assignment_path)
        endpoint = load_json(endpoint_path)
        if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != expected:
            raise RuntimeError(f"E050 seed {index} endpoint drift")
        pose_changed = [
            instance_id
            for instance_id in sorted(solution)
            if int(solution[instance_id]["pose_idx"])
            != int(parent_solution[instance_id]["pose_idx"])
        ]
        if len(pose_changed) != 2:
            raise RuntimeError(f"E050 seed {index} pose change count drift: {pose_changed}")
        seed_inputs.append((chr(64 + index), solution, endpoint, expected))

    original_prepare = e043.prepare_blocks_for_seed
    old_out = e043.OUT
    old_calibration_seconds = e043.CALIBRATION_SECONDS
    old_free_seconds = e043.FREE_SOLVE_SECONDS
    e043.prepare_blocks_for_seed = lambda **kwargs: prepare_blocks_for_pose_pair(
        **kwargs,
        e043=e043,
    )
    e043.OUT = OUT
    e043.CALIBRATION_SECONDS = 45.0
    e043.FREE_SOLVE_SECONDS = 120.0
    try:
        seed_results = [
            e043.run_seed(
                label=label,
                seed_solution=solution,
                seed_endpoint=endpoint,
                expected_objective=expected,
                base_solution=parent_solution,
                result_41=context_144,
                inputs=inputs,
                mandatory=mandatory,
                generic=generic,
                e001=e001,
                e004=e004,
                e014=e014,
                e015=e015,
                e027=e027,
                e031=e031,
                e041=e041,
                conditional_mode_module=conditional_mode_module,
                runner_sha256=runner_sha256,
            )
            for label, solution, endpoint, expected in seed_inputs
        ]
    finally:
        e043.prepare_blocks_for_seed = original_prepare
        e043.OUT = old_out
        e043.CALIBRATION_SECONDS = old_calibration_seconds
        e043.FREE_SOLVE_SECONDS = old_free_seconds

    if any(
        result["verdict"] == "GEOMETRY_SEED_CALIBRATION_REJECTED"
        for result in seed_results
    ):
        return {
            "schema": "zmd_zero_condition_e050_external_rescue_revaluation_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "EXTERNAL_RESCUE_CALIBRATION_REJECTED",
            "identity": identity,
            "seed_results": seed_results,
            "best_seed": None,
            "routing": {"status": "NOT_REACHED_CALIBRATION_REJECTED"},
            "decision": "REFINE_EXTERNAL_RESCUE_CONTEXT",
            "truth_boundary": "Fidelity calibrations only.",
            "ledger_effect": "none",
        }

    feasible = [
        result for result in seed_results if result.get("best_child") is not None
    ]
    if not feasible:
        return {
            "schema": "zmd_zero_condition_e050_external_rescue_revaluation_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "EXTERNAL_RESCUE_JOINT_NONTERMINAL",
            "identity": identity,
            "seed_results": seed_results,
            "best_seed": None,
            "routing": {"status": "NOT_REACHED_NO_FEASIBLE_JOINT_STATE"},
            "decision": "CONTINUE_OR_REFORMULATE_EXTERNAL_RESCUE_SOLVES",
            "truth_boundary": "Three E049 rescued pose states only.",
            "ledger_effect": "none",
        }

    ranked = sorted(
        feasible,
        key=lambda result: (
            int(result["best_child"]["objective"]),
            -int(result["best_child"]["filtered_binding_option_count"]),
            str(result["seed_label"]),
        ),
    )
    best_objective = int(ranked[0]["best_child"]["objective"])
    best = [
        result
        for result in ranked
        if int(result["best_child"]["objective"]) == best_objective
    ]
    routing: dict[str, Any] = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
    if best_objective == 0:
        verdict = "EXTERNAL_RESCUE_JOINT_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
        best_solution = e041.solution_from_assignment(
            ROOT / str(best[0]["best_child"]["assignment_path"])
        )
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
    elif best_objective < PARENT_OBJECTIVE:
        verdict = "EXTERNAL_RESCUE_JOINT_IMPROVEMENT"
        decision = "RECOMPUTE_RESIDUAL_FROM_RESCUED_GEOMETRY"
    else:
        verdict = "EXTERNAL_RESCUE_ADMISSION_ONLY"
        decision = "BUILD_BROADER_NATIVE_SIMULTANEOUS_GEOMETRY_CONTEXT"

    return {
        "schema": "zmd_zero_condition_e050_external_rescue_revaluation_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "parent_objective": PARENT_OBJECTIVE,
        "context_reconstruction": {
            "block_count": len(context_144["final_blocks"]),
            "selected_instance_count": sum(
                len(values)
                for values in context_144[
                    "selected_instance_ids_by_block"
                ].values()
            ),
            "mode_enabled_destination_count": sum(
                bool(row["mode_enabled"])
                for row in context_144["mode_summary"]
            ),
            "context_digest": stable_digest(context_144),
        },
        "seed_results": seed_results,
        "joint_objective_distribution": {
            str(key): value
            for key, value in sorted(
                Counter(
                    int(result["best_child"]["objective"])
                    for result in feasible
                ).items()
            )
        },
        "best_objective": best_objective,
        "best_seed_labels": [str(result["seed_label"]) for result in best],
        "best_seed": best[0] if len(best) == 1 else None,
        "routing": routing,
        "decision": decision,
        "truth_boundary": (
            "Three E049 external-rescue pose states under the reconstructed "
            "objective-144 context; each receives one exact calibration and one "
            "free bounded port-mode/assignment/binding solve."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists():
        raise FileExistsError("refusing to overwrite E050 terminal result")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "seed_results": [
                        {
                            "seed": row["seed_label"],
                            "fixed": row["fixed_objective"],
                            "move": row["move"],
                            "calibration_status": row["calibration"]["status"],
                            "calibration_objective": row["calibration"].get(
                                "objective"
                            ),
                            "free_status": (
                                row["free_solve"].get("status")
                                if row.get("free_solve")
                                else None
                            ),
                            "free_objective": (
                                row["free_solve"].get("objective")
                                if row.get("free_solve")
                                else None
                            ),
                        }
                        for row in result["seed_results"]
                    ],
                    "best_objective": result.get("best_objective"),
                    "best_seed_labels": result.get("best_seed_labels"),
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
            "schema": "zmd_zero_condition_e050_external_rescue_revaluation_failure_v1",
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
