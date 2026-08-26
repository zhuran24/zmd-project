#!/usr/bin/env python3
"""E043: carry the faithful joint middle layer across two body geometries."""

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
OUT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

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
E042_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E042_mode_vs_body_discriminator/run-001/RESULT.json"
)
E042_ARM_02 = (
    ROOT
    / "research_lab/local/zero_condition/E042_mode_vs_body_discriminator/run-001/ARM_02.json"
)
E042_BODY_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E042_mode_vs_body_discriminator/run-001/BEST_BODY_ASSIGNMENT.json"
)
E042_BODY_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E042_mode_vs_body_discriminator/run-001/BEST_BODY_ENDPOINT.json"
)
E041_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E041_joint_port_mode_assignment/run_e041.py"
)
E041_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E041_joint_port_mode_assignment/conditional_mode_owner_binding.py"
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
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E027_final_unary_discriminator/run_e027.py"
)
E031_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E031_bounded_assignment_neighborhood/run_e031.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "273000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E041_RESULT: "ba97d01cfe4a757daf102e514ab9984bd99abc679c16f8db6147f2269d40fada",
    E041_ASSIGNMENT: "020bfc79e47e61e2c6ccd68d10a7f292d22f381ab0747c3ea37e960f501ce642",
    E041_ENDPOINT: "9c05925a3bb5e4f3d1d88c14e26e5473c7109fb5004e1110b8bd07fb8558f1b4",
    E042_RESULT: "81e641860cde0e3a99f55b964a25c68630c66360d8e3127152d164bcf517636a",
    E042_ARM_02: "4910d0e1cc405e6b1ada95b2b8332b8c5cecfe38f353a78a52c58811819151c4",
    E042_BODY_ASSIGNMENT: "b5dae2fadbcc5db51556aeb77f4b3bea26a929ed308ee76207ba19b38cb18d2f",
    E042_BODY_ENDPOINT: "25f13ba25f51568f9131ef7e4dcfe5b21444948e83200949b3b3645d8c029d6c",
    E041_RUNNER: "5731b294e5c3070617d3a29e8912e4f859da207c6f183354ad9c7194f2d54b06",
    E041_HELPER: "98464fc5c9ee181a69392e582c2194edd0c213965b6c62672ece190fb1370dad",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E017_RUNNER: "106d7ee8830d3a45bf4115e064e65e059fdd86c4bd4b5c2acddaff55e203a2e0",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    E031_RUNNER: "ba35d569dc1a514da83b46721cb53c3f25386b2d776c70ac4cfae7f7c4d29b18",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

SEED_A_EXPECTED = 150
SEED_B_EXPECTED = 151
SEED_B_TARGET = "mandatory::group::manufacturing_3x3::crusher_sandleaf::3::2155"
SEED_B_POSE_IDX = 5342
CALIBRATION_SECONDS = 60.0
FREE_SOLVE_SECONDS = 150.0


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


def seed_paths(label: str) -> dict[str, Path]:
    prefix = f"SEED_{label}"
    return {
        "checkpoint": OUT / f"{prefix}.json",
        "fixed_assignment": OUT / f"{prefix}_FIXED_ASSIGNMENT.json",
        "fixed_layout": OUT / f"{prefix}_FIXED_LAYOUT.json",
        "fixed_endpoint": OUT / f"{prefix}_FIXED_ENDPOINT.json",
        "best_assignment": OUT / f"{prefix}_BEST_ASSIGNMENT.json",
        "best_layout": OUT / f"{prefix}_BEST_LAYOUT.json",
        "best_endpoint": OUT / f"{prefix}_BEST_ENDPOINT.json",
        "joint_witness": OUT / f"{prefix}_JOINT_WITNESS.json",
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E043 must run on research/main")
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
    e041_result = load_json(E041_RESULT)
    e042_result = load_json(E042_RESULT)
    if int(e041_result["best_child"]["objective"]) != 152:
        raise RuntimeError("E041 objective drift")
    if int(e042_result["best_body_child"]["objective"]) != SEED_A_EXPECTED:
        raise RuntimeError("E042 seed A drift")
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


def pose_payload(
    *,
    instance_id: str,
    row: Mapping[str, Any],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    facility_type = str(row["facility_type"])
    pose_idx = int(row["pose_idx"])
    pose = pools[facility_type][pose_idx]
    return {
        "anchor": {
            "x": int(pose["anchor"]["x"]),
            "y": int(pose["anchor"]["y"]),
        },
        "consumer_id": f"geometry_body::{instance_id}",
        "facility_type": facility_type,
        "kind": "mandatory_group_pose",
        "literal_key": f"geometry_body::{instance_id}::{pose_idx}",
        "occupied_cells": [
            [int(cell[0]), int(cell[1])] for cell in pose["occupied_cells"]
        ],
        "operation_type": str(row["operation_type"]),
        "pose_id": str(pose["pose_id"]),
        "pose_idx": pose_idx,
        "source_instance_ids": [instance_id],
    }


def prepare_blocks_for_seed(
    *,
    base_solution: Mapping[str, Mapping[str, Any]],
    seed_solution: Mapping[str, Mapping[str, Any]],
    result_41: Mapping[str, Any],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    e041: Any,
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
    moved = [
        instance_id
        for instance_id in sorted(seed_solution)
        if int(seed_solution[instance_id]["pose_idx"])
        != int(base_solution[instance_id]["pose_idx"])
    ]
    if len(moved) != 1:
        raise RuntimeError(f"E043 seed move count drift: {moved}")
    moved_instance = moved[0]
    moved_location: tuple[str, int] | None = None

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
                pose_payload(
                    instance_id=instance_id,
                    row=seed_solution[instance_id],
                    pools=pools,
                )
            )
            source_ids.append(instance_id)
            if instance_id == moved_instance:
                moved_location = (block_id, destination)
        block["selected_literal_payloads"] = payloads
        block["selected_literals"] = [
            str(payload["literal_key"]) for payload in payloads
        ]
        block["source_instance_ids_by_destination"] = source_ids
        block["selected_literal_count"] = len(payloads)
        block["selection_digest"] = stable_digest(payloads)

    if moved_location is None:
        row = seed_solution[moved_instance]
        block_id = f"geometry_singleton::{moved_instance}"
        payload = pose_payload(
            instance_id=moved_instance,
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
            "source_instance_ids_by_destination": [moved_instance],
            "selection_digest": stable_digest([payload]),
            "semantic_permutation_count_including_identity": 1,
            "owner_refresh": "geometry_singleton",
        }
        blocks.append(singleton)
        selected_ids_by_block[block_id] = {moved_instance}
        moved_location = (block_id, 0)

    enabled = set(base_enabled)
    enabled.add(moved_location)
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
                    f"E043 current pose missing from modes: {block_id}/{destination}"
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
        raise RuntimeError("E043 selected instance overlap")
    return (
        blocks,
        selected_ids_by_block,
        mode_summary,
        {
            "moved_instance_id": moved_instance,
            "moved_location": {
                "block_id": moved_location[0],
                "destination": moved_location[1],
            },
            "inside_original_assignment_context": moved_instance
            in {
                value
                for values in result_41["selected_instance_ids_by_block"].values()
                for value in values
            },
        },
    )


def load_or_build_seed_b(
    *,
    base_solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e001: Any,
    e004: Any,
    e014: Any,
    e015: Any,
    e017: Any,
    e027: Any,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    paths = seed_paths("B")
    if paths["fixed_assignment"].exists() and paths["fixed_endpoint"].exists():
        solution = load_json(paths["fixed_assignment"])["solution"]
        endpoint = load_json(paths["fixed_endpoint"])
        if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != SEED_B_EXPECTED:
            raise RuntimeError("E043 cached seed B endpoint drift")
        return {str(key): dict(value) for key, value in solution.items()}, endpoint

    arm = load_json(E042_ARM_02)
    if str(arm["target"]["literal_key"]) != SEED_B_TARGET:
        raise RuntimeError("E043 seed B target drift")
    matches = [
        dict(record)
        for record in arm["candidate_records"]
        if int(record["pose_idx"]) == SEED_B_POSE_IDX
        and str(record["shared_binding"]["status"]) == "OPTIMAL"
        and int(record["shared_binding"]["objective"]) == SEED_B_EXPECTED
    ]
    if len(matches) != 1:
        raise RuntimeError(f"E043 seed B record drift: {len(matches)}")
    solution = e017.reconstruct_candidate(
        arm=arm,
        record=matches[0],
        pair_solution=base_solution,
        inputs=inputs,
        e014=e014,
    )
    endpoint = e027.materialize_shared_endpoint(
        solution=solution,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=44002,
    )
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != SEED_B_EXPECTED:
        raise RuntimeError("E043 seed B materialization drift")
    dump_exclusive(
        paths["fixed_assignment"],
        {
            "schema": "zmd_zero_condition_e043_seed_b_fixed_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "objective": SEED_B_EXPECTED,
            "target_literal": SEED_B_TARGET,
            "replacement_pose_idx": SEED_B_POSE_IDX,
            "solution": solution,
        },
    )
    dump_exclusive(paths["fixed_layout"], e001.solution_layout(solution))
    dump_exclusive(paths["fixed_endpoint"], endpoint)
    return solution, endpoint


def run_seed(
    *,
    label: str,
    seed_solution: Mapping[str, Mapping[str, Any]],
    seed_endpoint: Mapping[str, Any],
    expected_objective: int,
    base_solution: Mapping[str, Mapping[str, Any]],
    result_41: Mapping[str, Any],
    inputs: Mapping[str, Any],
    mandatory: Sequence[Mapping[str, Any]],
    generic: Mapping[str, Any],
    e001: Any,
    e004: Any,
    e014: Any,
    e015: Any,
    e027: Any,
    e031: Any,
    e041: Any,
    conditional_mode_module: Any,
    runner_sha256: str,
) -> dict[str, Any]:
    paths = seed_paths(label)
    if paths["checkpoint"].exists():
        checkpoint = load_json(paths["checkpoint"])
        if str(checkpoint.get("runner_sha256")) != runner_sha256:
            raise RuntimeError(f"stale E043 seed checkpoint: {label}")
        return checkpoint

    blocks, selected_ids_by_block, mode_summary, move = prepare_blocks_for_seed(
        base_solution=base_solution,
        seed_solution=seed_solution,
        result_41=result_41,
        pools=inputs["pools"],
        e041=e041,
    )
    exchangeability = e031.exchangeability_audit(
        neighborhoods=blocks,
        mandatory=mandatory,
        generic=generic,
    )
    if exchangeability.get("status") != "PASS":
        raise RuntimeError(f"E043 seed {label} exchangeability failed")
    fixed = e041.fixed_state_for_solution(
        solution=seed_solution,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
        pools=inputs["pools"],
    )
    calibration_built = e041.build_mode_joint_model(
        full_solution=seed_solution,
        warm_endpoint=seed_endpoint,
        fixed_state=fixed,
        inputs=inputs,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
        e004=e004,
        e015=e015,
        conditional_mode_module=conditional_mode_module,
    )
    calibration = e041.solve_mode_joint(
        calibration_built,
        time_limit_seconds=CALIBRATION_SECONDS,
        random_seed=44010 + (1 if label == "A" else 2),
    )
    calibration_public = {
        key: value
        for key, value in calibration.items()
        if key
        not in {
            "joint_selection",
            "joint_port_specs",
            "selected_pattern_by_block",
        }
    }
    if calibration["status"] != "OPTIMAL" or int(calibration["objective"]) != expected_objective:
        checkpoint = {
            "schema": "zmd_zero_condition_e043_seed_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "runner_sha256": runner_sha256,
            "seed_label": label,
            "fixed_objective": expected_objective,
            "verdict": "GEOMETRY_SEED_CALIBRATION_REJECTED",
            "move": move,
            "mode_summary": mode_summary,
            "exchangeability_audit": exchangeability,
            "calibration": calibration_public,
            "free_solve": None,
            "best_child": None,
            "ledger_effect": "none",
        }
        dump_exclusive(paths["checkpoint"], checkpoint)
        return checkpoint

    free_built = e041.build_mode_joint_model(
        full_solution=seed_solution,
        warm_endpoint=seed_endpoint,
        fixed_state=None,
        inputs=inputs,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
        e004=e004,
        e015=e015,
        conditional_mode_module=conditional_mode_module,
    )
    free = e041.solve_mode_joint(
        free_built,
        time_limit_seconds=FREE_SOLVE_SECONDS,
        random_seed=44990 + (1 if label == "A" else 2),
    )
    free_public = {
        key: value
        for key, value in free.items()
        if key
        not in {
            "joint_selection",
            "joint_port_specs",
            "selected_pattern_by_block",
        }
    }
    if free["status"] not in {"OPTIMAL", "FEASIBLE"}:
        checkpoint = {
            "schema": "zmd_zero_condition_e043_seed_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "runner_sha256": runner_sha256,
            "seed_label": label,
            "fixed_objective": expected_objective,
            "verdict": "GEOMETRY_SEED_JOINT_NONTERMINAL",
            "move": move,
            "mode_summary": mode_summary,
            "exchangeability_audit": exchangeability,
            "calibration": calibration_public,
            "free_solve": free_public,
            "best_child": None,
            "ledger_effect": "none",
        }
        dump_exclusive(paths["checkpoint"], checkpoint)
        return checkpoint

    child = e041.realize_mode_blocks(
        parent=seed_solution,
        blocks=blocks,
        operation_by_block=free["operation_by_block"],
        pose_idx_by_block=free["pose_idx_by_block"],
        selected_ids_by_block=selected_ids_by_block,
        pools=inputs["pools"],
        e014=e014,
    )
    seed_occupied, _ = e014.base_occupancy(seed_solution, inputs["pools"])
    child_occupied, _ = e014.base_occupancy(child, inputs["pools"])
    if child_occupied != seed_occupied:
        raise RuntimeError(f"E043 seed {label} joint realization changed geometry")
    stack = e001.import_stack()
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
        raise RuntimeError(f"E043 seed {label} realization broke power")
    endpoint = e027.materialize_shared_endpoint(
        solution=child,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=45000 + (1 if label == "A" else 2),
    )
    if int(endpoint["objective"]) != int(free["objective"]):
        raise RuntimeError(f"E043 seed {label} joint/fixed objective drift")

    dump_exclusive(
        paths["joint_witness"],
        {
            "schema": "zmd_zero_condition_e043_seed_joint_witness_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "seed_label": label,
            "status": free["status"],
            "objective": int(free["objective"]),
            "operation_by_block": free["operation_by_block"],
            "pose_idx_by_block": free["pose_idx_by_block"],
            "selected_pattern_by_block": free["selected_pattern_by_block"],
            "joint_selection": free["joint_selection"],
            "joint_port_specs": free["joint_port_specs"],
            "per_commodity": free["per_commodity"],
            "ledger_effect": "none",
        },
    )
    dump_exclusive(
        paths["best_assignment"],
        {
            "schema": "zmd_zero_condition_e043_seed_best_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "seed_label": label,
            "status": "GEOMETRY_CONDITIONED_SHARED_BINDING_OPTIMAL"
            if free["status"] == "OPTIMAL"
            else "GEOMETRY_CONDITIONED_SHARED_BINDING_FEASIBLE_NONTERMINAL",
            "fixed_objective": expected_objective,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "operation_by_block": free["operation_by_block"],
            "pose_idx_by_block": free["pose_idx_by_block"],
            "solution": child,
        },
    )
    dump_exclusive(paths["best_layout"], e001.solution_layout(child))
    dump_exclusive(paths["best_endpoint"], endpoint)

    objective = int(endpoint["objective"])
    checkpoint = {
        "schema": "zmd_zero_condition_e043_seed_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "seed_label": label,
        "fixed_objective": expected_objective,
        "verdict": (
            "GEOMETRY_SEED_JOINT_COMPONENT_CANDIDATE"
            if objective == 0
            else "GEOMETRY_SEED_JOINT_OPTIMAL"
            if free["status"] == "OPTIMAL"
            else "GEOMETRY_SEED_JOINT_FEASIBLE_NONTERMINAL"
        ),
        "move": move,
        "mode_summary": mode_summary,
        "mode_enabled_destination_count": sum(
            bool(row["mode_enabled"]) for row in mode_summary
        ),
        "exchangeability_audit": exchangeability,
        "calibration": calibration_public,
        "free_solve": free_public,
        "model_size": free_built["model_size"],
        "best_child": {
            "objective": objective,
            "delta_from_fixed": objective - expected_objective,
            "operation_by_block": free["operation_by_block"],
            "pose_idx_by_block": free["pose_idx_by_block"],
            "placement_digest": stable_digest(child),
            "binding_selection_digest": endpoint["selection_digest"],
            "per_commodity": endpoint["per_commodity"],
            "positive_commodity_count": endpoint["positive_commodity_count"],
            "zero_mismatch_commodities": endpoint["zero_mismatch_commodities"],
            "morphology": endpoint["morphology"],
            "filtered_binding_option_count": endpoint[
                "filtered_binding_option_count"
            ],
            "joint_witness_path": str(paths["joint_witness"].relative_to(ROOT)),
            "joint_witness_sha256": sha256_file(paths["joint_witness"]),
            "assignment_path": str(paths["best_assignment"].relative_to(ROOT)),
            "assignment_sha256": sha256_file(paths["best_assignment"]),
            "layout_path": str(paths["best_layout"].relative_to(ROOT)),
            "layout_sha256": sha256_file(paths["best_layout"]),
            "endpoint_path": str(paths["best_endpoint"].relative_to(ROOT)),
            "endpoint_sha256": sha256_file(paths["best_endpoint"]),
        },
        "ledger_effect": "none",
    }
    dump_exclusive(paths["checkpoint"], checkpoint)
    return checkpoint


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e041 = import_module("zmd_e043_e041", E041_RUNNER)
    e001 = import_module("zmd_e043_e001", E001_RUNNER)
    e004 = import_module("zmd_e043_e004", E004_RUNNER)
    e014 = import_module("zmd_e043_e014", E014_RUNNER)
    e015 = import_module("zmd_e043_e015", E015_RUNNER)
    e017 = import_module("zmd_e043_e017", E017_RUNNER)
    e027 = import_module("zmd_e043_e027", E027_RUNNER)
    e031 = import_module("zmd_e043_e031", E031_RUNNER)
    conditional_mode_module = import_module(
        "zmd_e043_conditional_mode",
        E041_HELPER,
    )

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    base_solution = e041.solution_from_assignment(E041_ASSIGNMENT)
    result_41 = load_json(E041_RESULT)
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(mandatory, list) or not isinstance(generic, Mapping):
        raise RuntimeError("E043 frozen instance/generic payload drift")

    seed_a_solution = e041.solution_from_assignment(E042_BODY_ASSIGNMENT)
    seed_a_endpoint = load_json(E042_BODY_ENDPOINT)
    if seed_a_endpoint.get("status") != "OPTIMAL" or int(seed_a_endpoint["objective"]) != SEED_A_EXPECTED:
        raise RuntimeError("E043 seed A endpoint drift")
    seed_b_solution, seed_b_endpoint = load_or_build_seed_b(
        base_solution=base_solution,
        inputs=inputs,
        e001=e001,
        e004=e004,
        e014=e014,
        e015=e015,
        e017=e017,
        e027=e027,
    )

    seed_results = [
        run_seed(
            label="A",
            seed_solution=seed_a_solution,
            seed_endpoint=seed_a_endpoint,
            expected_objective=SEED_A_EXPECTED,
            base_solution=base_solution,
            result_41=result_41,
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
        ),
        run_seed(
            label="B",
            seed_solution=seed_b_solution,
            seed_endpoint=seed_b_endpoint,
            expected_objective=SEED_B_EXPECTED,
            base_solution=base_solution,
            result_41=result_41,
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
        ),
    ]
    if any(result["verdict"] == "GEOMETRY_SEED_CALIBRATION_REJECTED" for result in seed_results):
        return {
            "schema": "zmd_zero_condition_e043_geometry_conditioned_joint_middle_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "GEOMETRY_PORTFOLIO_CALIBRATION_REJECTED",
            "identity": identity,
            "seed_results": seed_results,
            "best_seed": None,
            "routing": {"status": "NOT_REACHED_CALIBRATION_REJECTED"},
            "decision": "REFINE_GEOMETRY_CONDITIONED_JOINT_MODEL",
            "truth_boundary": "Fidelity calibrations only.",
            "ledger_effect": "none",
        }

    feasible = [
        result
        for result in seed_results
        if result.get("best_child") is not None
    ]
    if not feasible:
        return {
            "schema": "zmd_zero_condition_e043_geometry_conditioned_joint_middle_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "GEOMETRY_PORTFOLIO_JOINT_NONTERMINAL",
            "identity": identity,
            "seed_results": seed_results,
            "best_seed": None,
            "routing": {"status": "NOT_REACHED_NO_FEASIBLE_JOINT_STATE"},
            "decision": "CONTINUE_OR_REFORMULATE_GEOMETRY_JOINT_SOLVES",
            "truth_boundary": "Two frozen single-body geometry seeds only.",
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
        # The concrete endpoint is already materialized; exact routing is the next
        # stage, but E043 leaves the actual invocation to the selected seed report.
        verdict = "GEOMETRY_CONDITIONED_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
        routing = {"status": "READY_SELECTED_ZERO_ENDPOINT"}
    elif len(best) > 1:
        verdict = "GEOMETRY_CONDITIONED_JOINT_TIE"
        decision = "RETAIN_GEOMETRY_BEAM_AND_COMPARE_BODY_RESPONSE_DOMAINS"
    else:
        selected = best[0]
        if int(selected["best_child"]["objective"]) < int(selected["fixed_objective"]):
            verdict = "GEOMETRY_CONDITIONED_JOINT_MATERIAL_IMPROVEMENT"
            decision = "RECOMPUTE_RESIDUAL_FROM_SELECTED_GEOMETRY"
        else:
            verdict = "GEOMETRY_CONDITIONED_JOINT_SATURATION_SIGNAL"
            decision = "BUILD_SIMULTANEOUS_BODY_PAIR_NEIGHBORHOOD"

    return {
        "schema": "zmd_zero_condition_e043_geometry_conditioned_joint_middle_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "seed_results": seed_results,
        "joint_objective_distribution": dict(
            sorted(
                Counter(
                    int(result["best_child"]["objective"])
                    for result in feasible
                ).items()
            )
        ),
        "best_objective": best_objective,
        "best_seed_labels": [str(result["seed_label"]) for result in best],
        "best_seed": best[0] if len(best) == 1 else None,
        "routing": routing,
        "decision": decision,
        "truth_boundary": (
            "Two frozen single-body geometry states, each with exact fixed-state "
            "calibration and one free bounded port-mode/assignment/binding solve."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E043 terminal output")
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
            "schema": "zmd_zero_condition_e043_geometry_conditioned_joint_middle_failure_v1",
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
