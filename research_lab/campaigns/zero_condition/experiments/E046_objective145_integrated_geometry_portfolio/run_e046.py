#!/usr/bin/env python3
"""E046: integrate objective-145 body proposals with joint middle revaluation."""

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
import traceback
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = (
    ROOT
    / "research_lab/local/zero_condition/E046_objective145_integrated_geometry_portfolio/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
CENSUS_PATH = OUT / "BODY_MOBILITY_CENSUS.json"
ARM_MANIFEST_PATH = OUT / "ARM_MANIFEST.json"

E041_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E041_joint_port_mode_assignment/run-001/RESULT.json"
)
E041_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E041_joint_port_mode_assignment/run-001/BEST_ASSIGNMENT.json"
)
E041_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E041_joint_port_mode_assignment/run-001/BEST_ENDPOINT.json"
)
E042_BODY_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E042_mode_vs_body_discriminator/run-001/BEST_BODY_ASSIGNMENT.json"
)
E043_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/RESULT.json"
)
E043_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/SEED_A_BEST_ASSIGNMENT.json"
)
E043_SEED_A_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/SEED_A_BEST_ENDPOINT.json"
)
E043_SEED_B_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/SEED_B_BEST_ENDPOINT.json"
)
E044_SEED_2_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E044_objective147_body_portfolio/run-001/SEED_02_ASSIGNMENT.json"
)
E045_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E045_revalue_objective146_geometries/run-001/RESULT.json"
)
E045_SEED_A_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E045_revalue_objective146_geometries/run-001/SEED_A_BEST_ENDPOINT.json"
)
E045_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E045_revalue_objective146_geometries/run-001/SEED_B_BEST_ASSIGNMENT.json"
)
E045_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E045_revalue_objective146_geometries/run-001/SEED_B_BEST_ENDPOINT.json"
)

E041_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E041_joint_port_mode_assignment/run_e041.py"
)
E041_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E041_joint_port_mode_assignment/conditional_mode_owner_binding.py"
)
E043_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E043_geometry_conditioned_joint_middle/run_e043.py"
)
E044_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E044_objective147_body_portfolio/run_e044.py"
)
E045_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E045_revalue_objective146_geometries/run_e045.py"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
)
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E004_component_mismatch_atlas/run_e004.py"
)
E013_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E013_residual_boundary_coverage/run_e013.py"
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
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E027_final_unary_discriminator/run_e027.py"
)
E031_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E031_bounded_assignment_neighborhood/run_e031.py"
)
E035_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E035_cross_block_joint_assignment/run_e035.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "276000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E041_RESULT: "ba97d01cfe4a757daf102e514ab9984bd99abc679c16f8db6147f2269d40fada",
    E041_ASSIGNMENT: "020bfc79e47e61e2c6ccd68d10a7f292d22f381ab0747c3ea37e960f501ce642",
    E041_ENDPOINT: "9c05925a3bb5e4f3d1d88c14e26e5473c7109fb5004e1110b8bd07fb8558f1b4",
    E042_BODY_ASSIGNMENT: "b5dae2fadbcc5db51556aeb77f4b3bea26a929ed308ee76207ba19b38cb18d2f",
    E043_RESULT: "4ed1a66ef93e28e2e6521b1bd0458a0603db02a6a54731648f62df139dd4e335",
    E043_ASSIGNMENT: "302c9ab02b839a9924ed9aecd7c2e23ba9c5c7a571052600c6514bf7292d846a",
    E043_SEED_A_ENDPOINT: "6ee527af5f84d652a351e7e00e22cddda990d121f2cdb25839af214f11c2051a",
    E043_SEED_B_ENDPOINT: "563bc5a5165b797444a1feeca955bfc7a045c6fea96a07f39a8104deed5df46e",
    E044_SEED_2_ASSIGNMENT: "bf6aae0efaa0de4d29b5e87acc40c9761b5584e0061d8de045720ab118100e86",
    E045_RESULT: "eae3662471f5b7d841effd9351351fdba67c329381ed5c65ddcf9dba839045df",
    E045_SEED_A_ENDPOINT: "ff394af513f81b82d3ff321979622cd642e30ff9e4bc46677197af0072aa5b30",
    E045_ASSIGNMENT: "216344c1ff593b228e2adf28cd67c04b33c9b7bc28a23c4c5a5793868669bd9f",
    E045_ENDPOINT: "ddcb3be7a67a86739c7ffc914f0e5bb722a5fe02ec593ce4bfb925b7b02eb67b",
    E041_RUNNER: "5731b294e5c3070617d3a29e8912e4f859da207c6f183354ad9c7194f2d54b06",
    E041_HELPER: "98464fc5c9ee181a69392e582c2194edd0c213965b6c62672ece190fb1370dad",
    E043_RUNNER: "a81cd8a762f29fad5c1a9f1c587f3bc90c4abc099aa97ccadedee2235da34d26",
    E044_RUNNER: "bd453033c5683d09b84d08dba9316fd5a2f0547f889aa21e47f60c9213cecd7a",
    E045_RUNNER: "8ba3886ef205e682e3e6e54d1905fecb9033ddc5e86fa0c3c252e61f0df1e02b",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E017_RUNNER: "106d7ee8830d3a45bf4115e064e65e059fdd86c4bd4b5c2acddaff55e203a2e0",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    E031_RUNNER: "ba35d569dc1a514da83b46721cb53c3f25386b2d776c70ac4cfae7f7c4d29b18",
    E035_RUNNER: "01bee53fb2e90e80a2cad6eaf363b865473bd9c92dfe5800b9475287af2b4bcf",
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

PARENT_OBJECTIVE = 145
BODY_BUDGET = 6
SEED_LIMIT = 2
MATERIAL_GAIN = 2
PRE_RESUME_RUNNER_SHA256 = (
    "11be18751ce88dae029f1af1004ab0f7c10702f297a4f3b605cc42b54b0e414d"
)
EXCLUDED_FACILITY_TYPES = {"boundary_storage_port", "protocol_core"}


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


def checkpoint_path(index: int) -> Path:
    return OUT / f"ARM_{index:02d}.json"


def ordinary_seed_paths(index: int) -> dict[str, Path]:
    prefix = OUT / f"SEED_{index:02d}"
    return {
        "assignment": prefix.with_name(prefix.name + "_ASSIGNMENT.json"),
        "layout": prefix.with_name(prefix.name + "_LAYOUT.json"),
        "endpoint": prefix.with_name(prefix.name + "_ENDPOINT.json"),
    }


def dump_or_validate_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    if not path.exists():
        dump_exclusive(path, payload)
        return
    existing = load_json(path)
    existing_stable = {
        key: value for key, value in existing.items() if key != "created_at_utc"
    }
    payload_stable = {
        key: value for key, value in payload.items() if key != "created_at_utc"
    }
    if json_safe(existing_stable) != json_safe(payload_stable):
        raise RuntimeError(f"E046 resumable manifest drift: {path}")


def load_or_materialize_seed(
    *,
    seed_index: int,
    row: Mapping[str, Any],
    parent_solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e001: Any,
    e004: Any,
    e014: Any,
    e015: Any,
    e017: Any,
    e027: Any,
    e044: Any,
) -> dict[str, Any]:
    paths = ordinary_seed_paths(seed_index)
    present = {key: path.exists() for key, path in paths.items()}
    if not any(present.values()):
        return e044.materialize_seed(
            seed_index=seed_index,
            row=row,
            parent_solution=parent_solution,
            inputs=inputs,
            e001=e001,
            e004=e004,
            e014=e014,
            e015=e015,
            e017=e017,
            e027=e027,
        )
    if not all(present.values()):
        raise RuntimeError(f"E046 partial materialized seed {seed_index}: {present}")

    assignment = load_json(paths["assignment"])
    endpoint = load_json(paths["endpoint"])
    solution = assignment.get("solution")
    record = row["record"]
    if not isinstance(solution, Mapping):
        raise RuntimeError(f"E046 seed {seed_index} assignment payload drift")
    if int(assignment.get("seed_index", -1)) != seed_index:
        raise RuntimeError(f"E046 seed {seed_index} index drift")
    if int(assignment.get("parent_objective", -1)) != PARENT_OBJECTIVE:
        raise RuntimeError(f"E046 seed {seed_index} parent objective drift")
    if json_safe(assignment.get("target")) != json_safe(row["target"]):
        raise RuntimeError(f"E046 seed {seed_index} target drift")
    if int(assignment.get("replacement_pose_idx", -1)) != int(record["pose_idx"]):
        raise RuntimeError(f"E046 seed {seed_index} replacement drift")
    expected_objective = int(record["shared_binding"]["objective"])
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != expected_objective:
        raise RuntimeError(f"E046 seed {seed_index} endpoint drift")
    stored_layout = load_json(paths["layout"])
    rebuilt_layout = e001.solution_layout(solution)
    stored_layout.pop("created_at_utc", None)
    rebuilt_layout.pop("created_at_utc", None)
    if json_safe(stored_layout) != json_safe(rebuilt_layout):
        raise RuntimeError(f"E046 seed {seed_index} layout drift")

    return {
        "seed_index": seed_index,
        "objective": expected_objective,
        "delta_from_parent": expected_objective - PARENT_OBJECTIVE,
        "target": row["target"],
        "target_coverage": int(row["target_coverage"]),
        "replacement_pose_idx": int(record["pose_idx"]),
        "replacement_pose_id": str(record["pose_id"]),
        "placement_digest": stable_digest(solution),
        "binding_selection_digest": endpoint["selection_digest"],
        "free_cell_set_digest": endpoint["morphology"]["free_cell_set_digest"],
        "per_commodity": endpoint["per_commodity"],
        "positive_commodity_count": endpoint["positive_commodity_count"],
        "zero_mismatch_commodities": endpoint["zero_mismatch_commodities"],
        "morphology": endpoint["morphology"],
        "filtered_binding_option_count": endpoint["filtered_binding_option_count"],
        "assignment_path": str(paths["assignment"].relative_to(ROOT)),
        "assignment_sha256": sha256_file(paths["assignment"]),
        "layout_path": str(paths["layout"].relative_to(ROOT)),
        "layout_sha256": sha256_file(paths["layout"]),
        "endpoint_path": str(paths["endpoint"].relative_to(ROOT)),
        "endpoint_sha256": sha256_file(paths["endpoint"]),
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E046 must run on research/main")
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
    result = load_json(E045_RESULT)
    endpoint = load_json(E045_ENDPOINT)
    if result.get("verdict") != "OBJECTIVE146_GEOMETRY_JOINT_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E045 trigger verdict drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E045 endpoint objective drift")
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


def reconstruct_current_context(
    *,
    e041: Any,
    e043: Any,
    e045: Any,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    context_43 = e045.reconstruct_e043_context(
        e041=e041,
        e043=e043,
        inputs=inputs,
    )
    parent_43 = e041.solution_from_assignment(E043_ASSIGNMENT)
    ordinary_seed_b = e041.solution_from_assignment(E044_SEED_2_ASSIGNMENT)
    blocks, selected_ids, mode_summary, move = e043.prepare_blocks_for_seed(
        base_solution=parent_43,
        seed_solution=ordinary_seed_b,
        result_41=context_43,
        pools=inputs["pools"],
        e041=e041,
    )
    result_45 = load_json(E045_RESULT)
    seed_b = next(
        row for row in result_45["seed_results"] if str(row["seed_label"]) == "B"
    )
    if json_safe(mode_summary) != json_safe(seed_b["mode_summary"]):
        raise RuntimeError("E046 reconstructed E045 mode context drift")
    if json_safe(move) != json_safe(seed_b["move"]):
        raise RuntimeError("E046 reconstructed E045 move context drift")
    return {
        "final_blocks": blocks,
        "selected_instance_ids_by_block": {
            key: sorted(value) for key, value in selected_ids.items()
        },
        "mode_summary": mode_summary,
        "source": "reconstructed E045 Seed B geometry-conditioned context",
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    current_runner_sha256 = str(identity["runner_sha256"])
    continued_from_existing = any(
        checkpoint_path(index).exists() for index in range(1, BODY_BUDGET + 1)
    ) or (OUT / "SEED_A.json").exists()
    runner_sha256 = (
        PRE_RESUME_RUNNER_SHA256
        if continued_from_existing
        else current_runner_sha256
    )
    checkpoint_identity = {**identity, "runner_sha256": runner_sha256}
    e041 = import_module("zmd_e046_e041", E041_RUNNER)
    e043 = import_module("zmd_e046_e043", E043_RUNNER)
    e044 = import_module("zmd_e046_e044", E044_RUNNER)
    e045 = import_module("zmd_e046_e045", E045_RUNNER)
    e001 = import_module("zmd_e046_e001", E001_RUNNER)
    e004 = import_module("zmd_e046_e004", E004_RUNNER)
    e013 = import_module("zmd_e046_e013", E013_RUNNER)
    e014 = import_module("zmd_e046_e014", E014_RUNNER)
    e015 = import_module("zmd_e046_e015", E015_RUNNER)
    e017 = import_module("zmd_e046_e017", E017_RUNNER)
    e027 = import_module("zmd_e046_e027", E027_RUNNER)
    e031 = import_module("zmd_e046_e031", E031_RUNNER)
    e035 = import_module("zmd_e046_e035", E035_RUNNER)
    conditional_mode_module = import_module(
        "zmd_e046_conditional_mode",
        E041_HELPER,
    )

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent_solution = e041.solution_from_assignment(E045_ASSIGNMENT)
    parent_endpoint = load_json(E045_ENDPOINT)
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(mandatory, list) or not isinstance(generic, Mapping):
        raise RuntimeError("E046 frozen instance/generic payload drift")
    observations, literals, observation_ids_by_literal = e035.build_incidence(
        solution=parent_solution,
        endpoint=parent_endpoint,
        pools=inputs["pools"],
        mandatory=mandatory,
        e013=e013,
    )
    if len(observations) != PARENT_OBJECTIVE:
        raise RuntimeError("E046 observation count drift")
    allowed = {
        key: dict(value)
        for key, value in literals.items()
        if str(value.get("kind")) in {"mandatory_group_pose", "optional_pose"}
        and str(value.get("facility_type")) not in EXCLUDED_FACILITY_TYPES
        and len(value.get("source_instance_ids", [])) == 1
    }

    old_e044_out = e044.OUT
    old_e044_census = e044.CENSUS_PATH
    old_e044_manifest = e044.ARM_MANIFEST_PATH
    old_e044_objective = e044.PARENT_OBJECTIVE
    old_e044_budget = e044.BODY_BUDGET
    try:
        e044.OUT = OUT
        e044.CENSUS_PATH = CENSUS_PATH
        e044.ARM_MANIFEST_PATH = ARM_MANIFEST_PATH
        e044.PARENT_OBJECTIVE = PARENT_OBJECTIVE
        e044.BODY_BUDGET = BODY_BUDGET
        census = e044.build_or_load_census(
            identity=checkpoint_identity,
            solution=parent_solution,
            endpoint=parent_endpoint,
            observations=observations,
            literals=literals,
            observation_ids_by_literal=observation_ids_by_literal,
            inputs=inputs,
            e013=e013,
            e014=e014,
            e001=e001,
        )
    finally:
        e044.OUT = old_e044_out
        e044.CENSUS_PATH = old_e044_census
        e044.ARM_MANIFEST_PATH = old_e044_manifest
        e044.PARENT_OBJECTIVE = old_e044_objective
        e044.BODY_BUDGET = old_e044_budget

    selected_keys = sorted(
        (str(value) for value in census["selected_literals"]),
        key=lambda key: (-len(observation_ids_by_literal[key]), key),
    )
    occupied, _ = e014.base_occupancy(parent_solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in parent_solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)

    arm_manifest: list[dict[str, Any]] = []
    arm_summaries: list[dict[str, Any]] = []
    body_records: list[dict[str, Any]] = []
    for index, key in enumerate(selected_keys, 1):
        target = allowed[key]
        path = checkpoint_path(index)
        if path.exists():
            arm = load_json(path)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E046 checkpoint: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E046_ARM_START",
                        "arm": index,
                        "target": key,
                        "coverage": len(observation_ids_by_literal[key]),
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            arm = e017.evaluate_arm(
                index=index,
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
            arm["schema"] = "zmd_zero_condition_e046_body_arm_v1"
            arm["target_coverage"] = len(observation_ids_by_literal[key])
            dump_exclusive(path, arm)
        arm_hash = sha256_file(path)
        arm_manifest.append(
            {
                "arm": index,
                "target": key,
                "path": str(path.relative_to(ROOT)),
                "sha256": arm_hash,
            }
        )
        status_counts = Counter(
            str(record["shared_binding"]["status"])
            for record in arm["candidate_records"]
        )
        optimal = [
            dict(record)
            for record in arm["candidate_records"]
            if not bool(record["same_footprint"])
            and str(record["shared_binding"]["status"]) == "OPTIMAL"
        ]
        for record in optimal:
            body_records.append(
                {
                    "arm": index,
                    "target": json_safe(target),
                    "target_coverage": len(observation_ids_by_literal[key]),
                    "checkpoint_path": str(path.relative_to(ROOT)),
                    "record": record,
                }
            )
        arm_summaries.append(
            {
                "arm": index,
                "target": json_safe(target),
                "target_coverage": len(observation_ids_by_literal[key]),
                "alternative_count": int(arm["alternative_count"]),
                "status_counts": dict(sorted(status_counts.items())),
                "best_body_objective": (
                    min(int(row["shared_binding"]["objective"]) for row in optimal)
                    if optimal
                    else None
                ),
                "checkpoint_path": str(path.relative_to(ROOT)),
                "checkpoint_sha256": arm_hash,
            }
        )

    dump_or_validate_manifest(
        ARM_MANIFEST_PATH,
        {
            "schema": "zmd_zero_condition_e046_arm_manifest_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "parent_objective": PARENT_OBJECTIVE,
            "selected_literals": selected_keys,
            "arms": arm_manifest,
            "ledger_effect": "none",
        },
    )

    known_geometry_values = {
        str(load_json(E041_ENDPOINT)["morphology"]["free_cell_set_digest"]): 152,
        str(load_json(E043_SEED_A_ENDPOINT)["morphology"]["free_cell_set_digest"]): 147,
        str(load_json(E043_SEED_B_ENDPOINT)["morphology"]["free_cell_set_digest"]): 150,
        str(load_json(E045_SEED_A_ENDPOINT)["morphology"]["free_cell_set_digest"]): 146,
        str(parent_endpoint["morphology"]["free_cell_set_digest"]): 145,
    }
    ranked_all = sorted(
        body_records,
        key=lambda row: (
            int(row["record"]["shared_binding"]["objective"]),
            -int(row["record"]["shared_binding"]["filtered_binding_option_count"]),
            -int(row["target_coverage"]),
            int(row["arm"]),
            int(row["record"]["pose_idx"]),
        ),
    )
    novel: list[dict[str, Any]] = []
    known_responses: list[dict[str, Any]] = []
    seen_free: set[str] = set()
    for row in ranked_all:
        digest = str(row["record"]["shared_binding"]["morphology"]["free_cell_set_digest"])
        if digest in known_geometry_values:
            known_responses.append(
                {
                    "free_cell_set_digest": digest,
                    "known_joint_value": known_geometry_values[digest],
                    "ordinary_objective": int(
                        row["record"]["shared_binding"]["objective"]
                    ),
                    "target": row["target"],
                    "pose_idx": int(row["record"]["pose_idx"]),
                }
            )
            continue
        if digest in seen_free:
            continue
        seen_free.add(digest)
        novel.append(row)

    old_e044_out = e044.OUT
    old_e044_objective = e044.PARENT_OBJECTIVE
    try:
        e044.OUT = OUT
        e044.PARENT_OBJECTIVE = PARENT_OBJECTIVE
        ordinary_seeds = [
            load_or_materialize_seed(
                seed_index=index,
                row=row,
                parent_solution=parent_solution,
                inputs=inputs,
                e001=e001,
                e004=e004,
                e014=e014,
                e015=e015,
                e017=e017,
                e027=e027,
                e044=e044,
            )
            for index, row in enumerate(novel[:SEED_LIMIT], 1)
        ]
    finally:
        e044.OUT = old_e044_out
        e044.PARENT_OBJECTIVE = old_e044_objective

    if not ordinary_seeds:
        return {
            "schema": "zmd_zero_condition_e046_integrated_geometry_portfolio_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "OBJECTIVE145_SINGLETON_GEOMETRY_EMPTY",
            "identity": identity,
            "parent_objective": PARENT_OBJECTIVE,
            "coverage": census["coverage"],
            "arm_summaries": arm_summaries,
            "known_geometry_responses": known_responses,
            "ordinary_seeds": [],
            "joint_seed_results": [],
            "best_joint_objective": None,
            "routing": {"status": "NOT_REACHED_NO_NEW_GEOMETRY"},
            "decision": "BUILD_SIMULTANEOUS_BODY_PAIR_NEIGHBORHOOD",
            "truth_boundary": "One exact budget-six singleton-body portfolio.",
            "ledger_effect": "none",
        }

    context_current = reconstruct_current_context(
        e041=e041,
        e043=e043,
        e045=e045,
        inputs=inputs,
    )
    seed_inputs: list[tuple[str, dict[str, dict[str, Any]], dict[str, Any], int]] = []
    for index, seed in enumerate(ordinary_seeds, 1):
        assignment = load_json(ROOT / str(seed["assignment_path"]))
        endpoint = load_json(ROOT / str(seed["endpoint_path"]))
        solution = {
            str(key): dict(value) for key, value in assignment["solution"].items()
        }
        moved = [
            instance_id
            for instance_id in sorted(solution)
            if int(solution[instance_id]["pose_idx"])
            != int(parent_solution[instance_id]["pose_idx"])
        ]
        if len(moved) != 1:
            raise RuntimeError(f"E046 seed {index} move count drift: {moved}")
        seed_inputs.append(
            (chr(64 + index), solution, endpoint, int(seed["objective"]))
        )

    old_e043_out = e043.OUT
    old_calibration_seconds = e043.CALIBRATION_SECONDS
    old_free_seconds = e043.FREE_SOLVE_SECONDS
    e043.OUT = OUT
    e043.CALIBRATION_SECONDS = 45.0
    e043.FREE_SOLVE_SECONDS = 120.0
    try:
        joint_seed_results = [
            e043.run_seed(
                label=label,
                seed_solution=solution,
                seed_endpoint=endpoint,
                expected_objective=expected,
                base_solution=parent_solution,
                result_41=context_current,
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
        e043.OUT = old_e043_out
        e043.CALIBRATION_SECONDS = old_calibration_seconds
        e043.FREE_SOLVE_SECONDS = old_free_seconds

    if any(
        result["verdict"] == "GEOMETRY_SEED_CALIBRATION_REJECTED"
        for result in joint_seed_results
    ):
        verdict = "OBJECTIVE145_GEOMETRY_CALIBRATION_REJECTED"
        decision = "REFINE_OBJECTIVE145_GEOMETRY_CONTEXT"
        best_joint_objective = None
        best_labels: list[str] = []
        best_seed = None
    else:
        feasible = [
            result
            for result in joint_seed_results
            if result.get("best_child") is not None
        ]
        if feasible:
            feasible.sort(
                key=lambda result: (
                    int(result["best_child"]["objective"]),
                    -int(result["best_child"]["filtered_binding_option_count"]),
                    str(result["seed_label"]),
                )
            )
            best_joint_objective = int(feasible[0]["best_child"]["objective"])
            best = [
                result
                for result in feasible
                if int(result["best_child"]["objective"])
                == best_joint_objective
            ]
            best_labels = [str(result["seed_label"]) for result in best]
            best_seed = best[0] if len(best) == 1 else None
            if best_joint_objective == 0:
                verdict = "OBJECTIVE145_GEOMETRY_COMPONENT_CANDIDATE"
                decision = "ENTER_EXACT_ROUTING"
            elif best_joint_objective <= PARENT_OBJECTIVE - MATERIAL_GAIN:
                verdict = (
                    "OBJECTIVE145_GEOMETRY_MATERIAL_TIE"
                    if len(best) > 1
                    else "OBJECTIVE145_GEOMETRY_MATERIAL_IMPROVEMENT"
                )
                decision = (
                    "RETAIN_GEOMETRY_BEAM_AND_RECOMPUTE_RESIDUAL"
                    if len(best) > 1
                    else "RECOMPUTE_RESIDUAL_FROM_SELECTED_GEOMETRY"
                )
            else:
                verdict = "OBJECTIVE145_SINGLETON_GEOMETRY_SATURATION_SIGNAL"
                decision = "BUILD_SIMULTANEOUS_BODY_PAIR_NEIGHBORHOOD"
        else:
            best_joint_objective = None
            best_labels = []
            best_seed = None
            verdict = "OBJECTIVE145_GEOMETRY_JOINT_NONTERMINAL"
            decision = "CONTINUE_OR_REFORMULATE_GEOMETRY_JOINT_SOLVES"

    distribution = Counter(
        int(row["record"]["shared_binding"]["objective"])
        for row in body_records
    )
    joint_distribution = Counter(
        int(result["best_child"]["objective"])
        for result in joint_seed_results
        if result.get("best_child") is not None
    )
    return {
        "schema": "zmd_zero_condition_e046_integrated_geometry_portfolio_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "resume": {
            "continued_from_existing": continued_from_existing,
            "checkpoint_runner_sha256": runner_sha256,
            "current_runner_sha256": current_runner_sha256,
            "pre_resume_runner_sha256": PRE_RESUME_RUNNER_SHA256,
        },
        "parent_objective": PARENT_OBJECTIVE,
        "observation_count": len(observations),
        "literal_count": len(literals),
        "mobility_census_path": str(CENSUS_PATH.relative_to(ROOT)),
        "mobility_census_sha256": sha256_file(CENSUS_PATH),
        "coverage": census["coverage"],
        "selected_literals": selected_keys,
        "arm_summaries": arm_summaries,
        "arm_manifest_path": str(ARM_MANIFEST_PATH.relative_to(ROOT)),
        "arm_manifest_sha256": sha256_file(ARM_MANIFEST_PATH),
        "body_optimal_candidate_count": len(body_records),
        "ordinary_objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "known_geometry_values": known_geometry_values,
        "known_geometry_responses": known_responses,
        "novel_geometry_count": len(novel),
        "top_novel_candidates": [
            {
                "objective": int(row["record"]["shared_binding"]["objective"]),
                "target": row["target"],
                "target_coverage": int(row["target_coverage"]),
                "pose_idx": int(row["record"]["pose_idx"]),
                "pose_id": str(row["record"]["pose_id"]),
                "free_cell_set_digest": str(
                    row["record"]["shared_binding"]["morphology"][
                        "free_cell_set_digest"
                    ]
                ),
            }
            for row in novel[:30]
        ],
        "ordinary_seeds": ordinary_seeds,
        "context_reconstruction": {
            "block_count": len(context_current["final_blocks"]),
            "selected_instance_count": sum(
                len(values)
                for values in context_current[
                    "selected_instance_ids_by_block"
                ].values()
            ),
            "mode_enabled_destination_count": sum(
                bool(row["mode_enabled"])
                for row in context_current["mode_summary"]
            ),
            "context_digest": stable_digest(context_current),
        },
        "joint_seed_results": joint_seed_results,
        "joint_objective_distribution": {
            str(key): value for key, value in sorted(joint_distribution.items())
        },
        "best_joint_objective": best_joint_objective,
        "best_seed_labels": best_labels,
        "best_seed": best_seed,
        "routing": {
            "status": (
                "READY_SELECTED_ZERO_ENDPOINT"
                if best_joint_objective == 0
                else "NOT_REACHED_POSITIVE_SHARED_MISMATCH"
            )
        },
        "decision": decision,
        "truth_boundary": (
            "One exact budget-six singleton-body portfolio under the objective-145 "
            "parent, with at most two distinct new geometries receiving exact "
            "fixed-state calibration and free joint middle-layer revaluation."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists():
        raise FileExistsError("refusing to overwrite E046 terminal result")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "coverage": {
                        "covered_count": result["coverage"]["covered_count"],
                        "coverage_fraction": result["coverage"]["coverage_fraction"],
                    },
                    "ordinary_seeds": result["ordinary_seeds"],
                    "joint_seed_results": [
                        {
                            "seed": row["seed_label"],
                            "fixed": row["fixed_objective"],
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
                        for row in result["joint_seed_results"]
                    ],
                    "best_joint_objective": result["best_joint_objective"],
                    "best_seed_labels": result["best_seed_labels"],
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
            "schema": "zmd_zero_condition_e046_integrated_geometry_portfolio_failure_v1",
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
