#!/usr/bin/env python3
"""E042: discriminate unadmitted same-body modes from body relocations."""

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
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E042_mode_vs_body_discriminator/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
CENSUS_PATH = OUT / "MOBILITY_CENSUS.json"
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
E041_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E041_joint_port_mode_assignment/run_e041.py"
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
    "EXACT_MASTER_RANDOM_SEED": "272000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E041_RESULT: "ba97d01cfe4a757daf102e514ab9984bd99abc679c16f8db6147f2269d40fada",
    E041_ASSIGNMENT: "020bfc79e47e61e2c6ccd68d10a7f292d22f381ab0747c3ea37e960f501ce642",
    E041_ENDPOINT: "9c05925a3bb5e4f3d1d88c14e26e5473c7109fb5004e1110b8bd07fb8558f1b4",
    E041_RUNNER: "5731b294e5c3070617d3a29e8912e4f859da207c6f183354ad9c7194f2d54b06",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E017_RUNNER: "106d7ee8830d3a45bf4115e064e65e059fdd86c4bd4b5c2acddaff55e203a2e0",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
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
    HISTORY_ROOT / "rules/canonical_rules.json": (
        "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0"
    ),
    HISTORY_ROOT / "rules/preprocess_plan.json": (
        "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee"
    ),
}

PARENT_OBJECTIVE = 152
MODE_BUDGET = 6
BODY_BUDGET = 6
MATERIAL_IMPROVEMENT = 2
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


def axis_paths(axis: str) -> dict[str, Path]:
    prefix = axis.upper()
    return {
        "assignment": OUT / f"BEST_{prefix}_ASSIGNMENT.json",
        "layout": OUT / f"BEST_{prefix}_LAYOUT.json",
        "endpoint": OUT / f"BEST_{prefix}_ENDPOINT.json",
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E042 must run on research/main")
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
    result = load_json(E041_RESULT)
    endpoint = load_json(E041_ENDPOINT)
    if result.get("verdict") != "PORT_MODE_JOINT_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E041 trigger verdict drift")
    if int(result["best_child"]["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E041 result objective drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E041 endpoint objective drift")
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


def build_or_load_census(
    *,
    identity: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
    endpoint: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
    inputs: Mapping[str, Any],
    e013: Any,
    e014: Any,
    e001: Any,
) -> dict[str, Any]:
    parent_placement_digest = stable_digest(solution)
    parent_selection_digest = str(endpoint["selection_digest"])
    runner_sha256 = str(identity["runner_sha256"])
    if CENSUS_PATH.exists():
        payload = load_json(CENSUS_PATH)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E042 mobility census runner")
        if str(payload.get("parent_placement_digest")) != parent_placement_digest:
            raise RuntimeError("stale E042 mobility census placement")
        if str(payload.get("parent_selection_digest")) != parent_selection_digest:
            raise RuntimeError("stale E042 mobility census endpoint")
        return payload

    allowed = {
        key: dict(value)
        for key, value in literals.items()
        if str(value.get("kind")) in {"mandatory_group_pose", "optional_pose"}
        and str(value.get("facility_type")) not in EXCLUDED_FACILITY_TYPES
        and len(value.get("source_instance_ids", [])) == 1
    }
    result_41 = load_json(E041_RESULT)
    admitted_mode_body_digests = {
        str(row["body_digest"])
        for row in result_41["mode_summary"]
        if bool(row["mode_enabled"])
    }
    selected_ids = {
        str(value)
        for values in result_41["selected_instance_ids_by_block"].values()
        for value in values
    }
    occupied, _ = e014.base_occupancy(solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    stack = e001.import_stack()
    power = e014.build_power_semantics(e001, stack, inputs)

    rows: list[dict[str, Any]] = []
    mobility_by_key: dict[str, dict[str, Any]] = {}
    for key in sorted(allowed):
        target = allowed[key]
        alternatives = e014.enumerate_alternatives(
            target=target,
            base_solution=solution,
            pools=inputs["pools"],
            occupied=occupied,
            selected_poles=selected_poles,
            powered_templates=power["powered_templates"],
            coverers=power["coverers"],
        )
        body_digest = stable_digest(
            sorted(tuple(int(value) for value in cell) for cell in target["occupied_cells"])
        )
        source_instance = str(target["source_instance_ids"][0])
        same_count = sum(bool(row["same_footprint"]) for row in alternatives)
        body_count = len(alternatives) - same_count
        row = {
            "literal_key": key,
            "coverage": len(observation_ids_by_literal[key]),
            "facility_type": str(target["facility_type"]),
            "operation_type": str(target.get("operation_type", "")),
            "pose_idx": int(target["pose_idx"]),
            "pose_id": str(target.get("pose_id", "")),
            "source_instance_id": source_instance,
            "inside_assignment_context": source_instance in selected_ids,
            "body_mode_already_admitted": body_digest in admitted_mode_body_digests,
            "same_footprint_alternative_count": same_count,
            "body_relocation_alternative_count": body_count,
            "total_alternative_count": len(alternatives),
            "body_digest": body_digest,
        }
        rows.append(row)
        mobility_by_key[key] = row

    mode_literals = {
        key: allowed[key]
        for key, row in mobility_by_key.items()
        if int(row["same_footprint_alternative_count"]) > 0
        and not bool(row["body_mode_already_admitted"])
    }
    body_literals = {
        key: allowed[key]
        for key, row in mobility_by_key.items()
        if int(row["body_relocation_alternative_count"]) > 0
    }
    mode_coverage = e013.exact_max_coverage(
        observations=observations,
        literals=mode_literals,
        observation_ids_by_literal={
            key: observation_ids_by_literal[key] for key in mode_literals
        },
        budget=MODE_BUDGET,
    )
    body_coverage = e013.exact_max_coverage(
        observations=observations,
        literals=body_literals,
        observation_ids_by_literal={
            key: observation_ids_by_literal[key] for key in body_literals
        },
        budget=BODY_BUDGET,
    )
    mode_keys = sorted(str(value) for value in mode_coverage["selected_literals"])
    body_keys = sorted(str(value) for value in body_coverage["selected_literals"])
    if len(mode_keys) != MODE_BUDGET or len(body_keys) != BODY_BUDGET:
        raise RuntimeError(
            f"E042 portfolio width drift: mode={len(mode_keys)} body={len(body_keys)}"
        )
    payload = {
        "schema": "zmd_zero_condition_e042_mobility_census_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "parent_objective": PARENT_OBJECTIVE,
        "parent_placement_digest": parent_placement_digest,
        "parent_selection_digest": parent_selection_digest,
        "observation_count": len(observations),
        "literal_count": len(literals),
        "allowed_target_count": len(allowed),
        "unadmitted_mode_target_count": len(mode_literals),
        "body_relocation_target_count": len(body_literals),
        "rows": rows,
        "mode_coverage": json_safe(mode_coverage),
        "body_coverage": json_safe(body_coverage),
        "mode_selected_literals": mode_keys,
        "body_selected_literals": body_keys,
        "selected_union_literals": sorted(set(mode_keys) | set(body_keys)),
        "mobility_digest": stable_digest(rows),
        "ledger_effect": "none",
    }
    dump_exclusive(CENSUS_PATH, payload)
    return payload


def compact_shared(shared: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": shared.get("status"),
        "objective": shared.get("objective"),
        "selection_digest": shared.get("selection_digest"),
        "port_specs_digest": shared.get("port_specs_digest"),
        "per_commodity": json_safe(shared.get("per_commodity", {})),
        "positive_commodity_count": shared.get("positive_commodity_count"),
        "zero_mismatch_commodities": json_safe(
            shared.get("zero_mismatch_commodities", [])
        ),
        "morphology": json_safe(shared.get("morphology", {})),
        "filtered_binding_option_count": shared.get(
            "filtered_binding_option_count"
        ),
    }


def materialize_axis(
    *,
    axis: str,
    best: Mapping[str, Any],
    parent_solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e001: Any,
    e004: Any,
    e014: Any,
    e015: Any,
    e017: Any,
    e027: Any,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    arm = load_json(ROOT / str(best["checkpoint_path"]))
    record = dict(best["record"])
    solution = e017.reconstruct_candidate(
        arm=arm,
        record=record,
        pair_solution=parent_solution,
        inputs=inputs,
        e014=e014,
    )
    endpoint = e027.materialize_shared_endpoint(
        solution=solution,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=43000 + (1 if axis == "mode" else 2),
    )
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != int(
        record["shared_binding"]["objective"]
    ):
        raise RuntimeError(f"E042 {axis} endpoint materialization drift")
    paths = axis_paths(axis)
    dump_exclusive(
        paths["assignment"],
        {
            "schema": f"zmd_zero_condition_e042_best_{axis}_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_OUTSIDE_SHARED_BINDING_OPTIMAL",
            "axis": axis,
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "target": best["target"],
            "replacement_pose_idx": int(record["pose_idx"]),
            "solution": solution,
        },
    )
    dump_exclusive(paths["layout"], e001.solution_layout(solution))
    dump_exclusive(paths["endpoint"], endpoint)
    summary = {
        "objective": int(endpoint["objective"]),
        "delta_from_parent": int(endpoint["objective"]) - PARENT_OBJECTIVE,
        "target": best["target"],
        "target_coverage": int(best["target_coverage"]),
        "replacement_pose_idx": int(record["pose_idx"]),
        "replacement_pose_id": str(record["pose_id"]),
        "same_footprint": bool(record["same_footprint"]),
        "inside_assignment_context": bool(best["mobility"]["inside_assignment_context"]),
        "body_mode_already_admitted": bool(
            best["mobility"]["body_mode_already_admitted"]
        ),
        "placement_digest": stable_digest(solution),
        "binding_selection_digest": endpoint["selection_digest"],
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
    return summary, solution


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e041 = import_module("zmd_e042_e041", E041_RUNNER)
    e001 = import_module("zmd_e042_e001", E001_RUNNER)
    e002 = import_module("zmd_e042_e002", E002_RUNNER)
    e004 = import_module("zmd_e042_e004", E004_RUNNER)
    e013 = import_module("zmd_e042_e013", E013_RUNNER)
    e014 = import_module("zmd_e042_e014", E014_RUNNER)
    e015 = import_module("zmd_e042_e015", E015_RUNNER)
    e017 = import_module("zmd_e042_e017", E017_RUNNER)
    e027 = import_module("zmd_e042_e027", E027_RUNNER)
    e035 = import_module("zmd_e042_e035", E035_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    solution = e041.solution_from_assignment(E041_ASSIGNMENT)
    endpoint = load_json(E041_ENDPOINT)
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(mandatory, list):
        raise RuntimeError("E042 mandatory instance payload drift")
    observations, literals, observation_ids_by_literal = e035.build_incidence(
        solution=solution,
        endpoint=endpoint,
        pools=inputs["pools"],
        mandatory=mandatory,
        e013=e013,
    )
    if len(observations) != PARENT_OBJECTIVE:
        raise RuntimeError("E042 observation count drift")
    allowed = {
        key: dict(value)
        for key, value in literals.items()
        if str(value.get("kind")) in {"mandatory_group_pose", "optional_pose"}
        and str(value.get("facility_type")) not in EXCLUDED_FACILITY_TYPES
        and len(value.get("source_instance_ids", [])) == 1
    }
    census = build_or_load_census(
        identity=identity,
        solution=solution,
        endpoint=endpoint,
        observations=observations,
        literals=literals,
        observation_ids_by_literal=observation_ids_by_literal,
        inputs=inputs,
        e013=e013,
        e014=e014,
        e001=e001,
    )
    mobility_by_key = {
        str(row["literal_key"]): dict(row) for row in census["rows"]
    }
    mode_keys = {str(value) for value in census["mode_selected_literals"]}
    body_keys = {str(value) for value in census["body_selected_literals"]}
    selected_keys = sorted(
        mode_keys | body_keys,
        key=lambda key: (-len(observation_ids_by_literal[key]), key),
    )

    occupied, _ = e014.base_occupancy(solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)

    arm_manifest: list[dict[str, Any]] = []
    arm_summaries: list[dict[str, Any]] = []
    mode_records: list[dict[str, Any]] = []
    body_records: list[dict[str, Any]] = []
    for index, key in enumerate(selected_keys, 1):
        target = allowed[key]
        path = checkpoint_path(index)
        if path.exists():
            arm = load_json(path)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E042 checkpoint: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E042_ARM_START",
                        "arm": index,
                        "target": key,
                        "coverage": len(observation_ids_by_literal[key]),
                        "mode_portfolio": key in mode_keys,
                        "body_portfolio": key in body_keys,
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            arm = e017.evaluate_arm(
                index=index,
                target=target,
                pair_solution=solution,
                occupied=occupied,
                selected_poles=selected_poles,
                inputs=inputs,
                power=power,
                e004=e004,
                e014=e014,
                e015=e015,
                runner_sha256=runner_sha256,
            )
            arm["schema"] = "zmd_zero_condition_e042_axis_arm_v1"
            arm["target_coverage"] = len(observation_ids_by_literal[key])
            arm["mode_portfolio"] = key in mode_keys
            arm["body_portfolio"] = key in body_keys
            arm["mobility"] = mobility_by_key[key]
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
        mode_optimal = [
            dict(record)
            for record in arm["candidate_records"]
            if key in mode_keys
            and bool(record["same_footprint"])
            and str(record["shared_binding"]["status"]) == "OPTIMAL"
        ]
        body_optimal = [
            dict(record)
            for record in arm["candidate_records"]
            if key in body_keys
            and not bool(record["same_footprint"])
            and str(record["shared_binding"]["status"]) == "OPTIMAL"
        ]
        for record in mode_optimal:
            mode_records.append(
                {
                    "arm": index,
                    "target": json_safe(target),
                    "target_coverage": len(observation_ids_by_literal[key]),
                    "checkpoint_path": str(path.relative_to(ROOT)),
                    "mobility": mobility_by_key[key],
                    "record": record,
                }
            )
        for record in body_optimal:
            body_records.append(
                {
                    "arm": index,
                    "target": json_safe(target),
                    "target_coverage": len(observation_ids_by_literal[key]),
                    "checkpoint_path": str(path.relative_to(ROOT)),
                    "mobility": mobility_by_key[key],
                    "record": record,
                }
            )
        arm_summaries.append(
            {
                "arm": index,
                "target": json_safe(target),
                "target_coverage": len(observation_ids_by_literal[key]),
                "mode_portfolio": key in mode_keys,
                "body_portfolio": key in body_keys,
                "mobility": mobility_by_key[key],
                "alternative_count": int(arm["alternative_count"]),
                "status_counts": dict(sorted(status_counts.items())),
                "best_mode_objective": (
                    min(int(row["shared_binding"]["objective"]) for row in mode_optimal)
                    if mode_optimal
                    else None
                ),
                "best_body_objective": (
                    min(int(row["shared_binding"]["objective"]) for row in body_optimal)
                    if body_optimal
                    else None
                ),
                "checkpoint_path": str(path.relative_to(ROOT)),
                "checkpoint_sha256": arm_hash,
            }
        )

    dump_exclusive(
        ARM_MANIFEST_PATH,
        {
            "schema": "zmd_zero_condition_e042_arm_manifest_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "parent_objective": PARENT_OBJECTIVE,
            "mode_portfolio": sorted(mode_keys),
            "body_portfolio": sorted(body_keys),
            "arms": arm_manifest,
            "ledger_effect": "none",
        },
    )

    def rank(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            (dict(row) for row in rows),
            key=lambda row: (
                int(row["record"]["shared_binding"]["objective"]),
                -int(row["record"]["shared_binding"]["filtered_binding_option_count"]),
                -int(row["target_coverage"]),
                int(row["arm"]),
                int(row["record"]["pose_idx"]),
            ),
        )

    ranked_mode = rank(mode_records)
    ranked_body = rank(body_records)
    best_mode_summary: dict[str, Any] | None = None
    best_body_summary: dict[str, Any] | None = None
    mode_solution: dict[str, dict[str, Any]] | None = None
    body_solution: dict[str, dict[str, Any]] | None = None
    if ranked_mode:
        best_mode_summary, mode_solution = materialize_axis(
            axis="mode",
            best=ranked_mode[0],
            parent_solution=solution,
            inputs=inputs,
            e001=e001,
            e004=e004,
            e014=e014,
            e015=e015,
            e017=e017,
            e027=e027,
        )
    if ranked_body:
        best_body_summary, body_solution = materialize_axis(
            axis="body",
            best=ranked_body[0],
            parent_solution=solution,
            inputs=inputs,
            e001=e001,
            e004=e004,
            e014=e014,
            e015=e015,
            e017=e017,
            e027=e027,
        )

    mode_objective = (
        int(best_mode_summary["objective"]) if best_mode_summary is not None else None
    )
    body_objective = (
        int(best_body_summary["objective"]) if best_body_summary is not None else None
    )
    mode_material = (
        mode_objective is not None
        and mode_objective <= PARENT_OBJECTIVE - MATERIAL_IMPROVEMENT
    )
    body_material = (
        body_objective is not None
        and body_objective <= PARENT_OBJECTIVE - MATERIAL_IMPROVEMENT
    )

    routing: dict[str, Any] = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
    if mode_objective == 0 or body_objective == 0:
        axis = "mode" if mode_objective == 0 else "body"
        selected_solution = mode_solution if axis == "mode" else body_solution
        if selected_solution is None:
            raise RuntimeError("E042 zero axis lacks materialized solution")
        routing = e014.screen_component_interface(
            solution=selected_solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        verdict = "MODE_OR_BODY_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif mode_material and body_material and mode_objective == body_objective:
        verdict = "MODE_AND_BODY_EQUAL_MATERIAL_SIGNALS"
        decision = "BUILD_HYBRID_MODE_BODY_NEIGHBORHOOD"
    elif mode_material and (not body_material or int(mode_objective) < int(body_objective)):
        verdict = "UNADMITTED_MODE_MATERIAL_SIGNAL"
        decision = "EXPAND_JOINT_MODE_CONTEXT"
    elif body_material and (not mode_material or int(body_objective) < int(mode_objective)):
        verdict = "BODY_RELOCATION_MATERIAL_SIGNAL"
        decision = "BUILD_SIMULTANEOUS_BODY_GEOMETRY_NEIGHBORHOOD"
    else:
        verdict = "FIXED_OUTSIDE_MOBILITY_SATURATION_SIGNAL"
        decision = "BUILD_SIMULTANEOUS_BODY_GEOMETRY_NEIGHBORHOOD"

    mode_distribution = Counter(
        int(row["record"]["shared_binding"]["objective"]) for row in mode_records
    )
    body_distribution = Counter(
        int(row["record"]["shared_binding"]["objective"]) for row in body_records
    )
    return {
        "schema": "zmd_zero_condition_e042_mode_vs_body_discriminator_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "parent_objective": PARENT_OBJECTIVE,
        "observation_count": len(observations),
        "literal_count": len(literals),
        "mobility_census_path": str(CENSUS_PATH.relative_to(ROOT)),
        "mobility_census_sha256": sha256_file(CENSUS_PATH),
        "mode_coverage": census["mode_coverage"],
        "body_coverage": census["body_coverage"],
        "mode_selected_literals": sorted(mode_keys),
        "body_selected_literals": sorted(body_keys),
        "selected_union_count": len(selected_keys),
        "arm_summaries": arm_summaries,
        "arm_manifest_path": str(ARM_MANIFEST_PATH.relative_to(ROOT)),
        "arm_manifest_sha256": sha256_file(ARM_MANIFEST_PATH),
        "mode_optimal_candidate_count": len(mode_records),
        "body_optimal_candidate_count": len(body_records),
        "mode_objective_distribution": {
            str(key): value for key, value in sorted(mode_distribution.items())
        },
        "body_objective_distribution": {
            str(key): value for key, value in sorted(body_distribution.items())
        },
        "top_mode_candidates": [
            {
                "arm": row["arm"],
                "target": row["target"],
                "target_coverage": row["target_coverage"],
                "mobility": row["mobility"],
                "pose_idx": int(row["record"]["pose_idx"]),
                "pose_id": str(row["record"]["pose_id"]),
                "objective": int(row["record"]["shared_binding"]["objective"]),
                "filtered_binding_option_count": int(
                    row["record"]["shared_binding"]["filtered_binding_option_count"]
                ),
            }
            for row in ranked_mode[:30]
        ],
        "top_body_candidates": [
            {
                "arm": row["arm"],
                "target": row["target"],
                "target_coverage": row["target_coverage"],
                "mobility": row["mobility"],
                "pose_idx": int(row["record"]["pose_idx"]),
                "pose_id": str(row["record"]["pose_id"]),
                "objective": int(row["record"]["shared_binding"]["objective"]),
                "filtered_binding_option_count": int(
                    row["record"]["shared_binding"]["filtered_binding_option_count"]
                ),
            }
            for row in ranked_body[:30]
        ],
        "best_mode_child": best_mode_summary,
        "best_body_child": best_body_summary,
        "routing": routing,
        "decision": decision,
        "truth_boundary": (
            "Two exact residual-selected six-target portfolios under one frozen "
            "objective-152 parent; same-footprint and body-relocation responses "
            "are separated after exhaustive fixed-outside evaluation."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E042 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "parent_objective": result["parent_objective"],
                    "selected_union_count": result["selected_union_count"],
                    "mode_coverage": {
                        "covered_count": result["mode_coverage"]["covered_count"],
                        "coverage_fraction": result["mode_coverage"][
                            "coverage_fraction"
                        ],
                    },
                    "body_coverage": {
                        "covered_count": result["body_coverage"]["covered_count"],
                        "coverage_fraction": result["body_coverage"][
                            "coverage_fraction"
                        ],
                    },
                    "best_mode_child": result.get("best_mode_child"),
                    "best_body_child": result.get("best_body_child"),
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
            "schema": "zmd_zero_condition_e042_mode_vs_body_discriminator_failure_v1",
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
