#!/usr/bin/env python3
"""E044: derive new body-geometry seeds from the objective-147 endpoint."""

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
OUT = ROOT / "research_lab/local/zero_condition/E044_objective147_body_portfolio/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
CENSUS_PATH = OUT / "BODY_MOBILITY_CENSUS.json"
ARM_MANIFEST_PATH = OUT / "ARM_MANIFEST.json"

E043_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/RESULT.json"
)
E043_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/SEED_A_BEST_ASSIGNMENT.json"
)
E043_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/SEED_A_BEST_ENDPOINT.json"
)
E043_SEED_B_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/SEED_B_BEST_ENDPOINT.json"
)
E041_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E041_joint_port_mode_assignment/run-001/BEST_ENDPOINT.json"
)
E043_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E043_geometry_conditioned_joint_middle/run_e043.py"
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
    "EXACT_MASTER_RANDOM_SEED": "274000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E043_RESULT: "4ed1a66ef93e28e2e6521b1bd0458a0603db02a6a54731648f62df139dd4e335",
    E043_ASSIGNMENT: "302c9ab02b839a9924ed9aecd7c2e23ba9c5c7a571052600c6514bf7292d846a",
    E043_ENDPOINT: "6ee527af5f84d652a351e7e00e22cddda990d121f2cdb25839af214f11c2051a",
    E043_SEED_B_ENDPOINT: "563bc5a5165b797444a1feeca955bfc7a045c6fea96a07f39a8104deed5df46e",
    E041_ENDPOINT: "9c05925a3bb5e4f3d1d88c14e26e5473c7109fb5004e1110b8bd07fb8558f1b4",
    E043_RUNNER: "a81cd8a762f29fad5c1a9f1c587f3bc90c4abc099aa97ccadedee2235da34d26",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
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

PARENT_OBJECTIVE = 147
BODY_BUDGET = 6
SEED_LIMIT = 2
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


def seed_paths(index: int) -> dict[str, Path]:
    return {
        "assignment": OUT / f"SEED_{index:02d}_ASSIGNMENT.json",
        "layout": OUT / f"SEED_{index:02d}_LAYOUT.json",
        "endpoint": OUT / f"SEED_{index:02d}_ENDPOINT.json",
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E044 must run on research/main")
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
    result = load_json(E043_RESULT)
    endpoint = load_json(E043_ENDPOINT)
    if result.get("verdict") != "GEOMETRY_CONDITIONED_JOINT_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E043 trigger verdict drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E043 endpoint objective drift")
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
    runner_sha256 = str(identity["runner_sha256"])
    parent_placement_digest = stable_digest(solution)
    parent_selection_digest = str(endpoint["selection_digest"])
    if CENSUS_PATH.exists():
        payload = load_json(CENSUS_PATH)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E044 census runner")
        if str(payload.get("parent_placement_digest")) != parent_placement_digest:
            raise RuntimeError("stale E044 census placement")
        if str(payload.get("parent_selection_digest")) != parent_selection_digest:
            raise RuntimeError("stale E044 census endpoint")
        return payload

    allowed = {
        key: dict(value)
        for key, value in literals.items()
        if str(value.get("kind")) in {"mandatory_group_pose", "optional_pose"}
        and str(value.get("facility_type")) not in EXCLUDED_FACILITY_TYPES
        and len(value.get("source_instance_ids", [])) == 1
    }
    occupied, _ = e014.base_occupancy(solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, e001.import_stack(), inputs)
    rows: list[dict[str, Any]] = []
    body_literals: dict[str, dict[str, Any]] = {}
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
        body_count = sum(not bool(row["same_footprint"]) for row in alternatives)
        row = {
            "literal_key": key,
            "coverage": len(observation_ids_by_literal[key]),
            "facility_type": str(target["facility_type"]),
            "operation_type": str(target.get("operation_type", "")),
            "pose_idx": int(target["pose_idx"]),
            "pose_id": str(target.get("pose_id", "")),
            "source_instance_id": str(target["source_instance_ids"][0]),
            "same_footprint_alternative_count": sum(
                bool(value["same_footprint"]) for value in alternatives
            ),
            "body_relocation_alternative_count": body_count,
            "total_alternative_count": len(alternatives),
        }
        rows.append(row)
        if body_count:
            body_literals[key] = target
    coverage = e013.exact_max_coverage(
        observations=observations,
        literals=body_literals,
        observation_ids_by_literal={
            key: observation_ids_by_literal[key] for key in body_literals
        },
        budget=BODY_BUDGET,
    )
    selected = sorted(str(value) for value in coverage["selected_literals"])
    if len(selected) != BODY_BUDGET:
        raise RuntimeError(f"E044 target count drift: {len(selected)}")
    payload = {
        "schema": "zmd_zero_condition_e044_body_mobility_census_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "parent_objective": PARENT_OBJECTIVE,
        "parent_placement_digest": parent_placement_digest,
        "parent_selection_digest": parent_selection_digest,
        "observation_count": len(observations),
        "literal_count": len(literals),
        "allowed_target_count": len(allowed),
        "body_relocation_target_count": len(body_literals),
        "rows": rows,
        "coverage": json_safe(coverage),
        "selected_literals": selected,
        "mobility_digest": stable_digest(rows),
        "ledger_effect": "none",
    }
    dump_exclusive(CENSUS_PATH, payload)
    return payload


def materialize_seed(
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
) -> dict[str, Any]:
    arm = load_json(ROOT / str(row["checkpoint_path"]))
    record = dict(row["record"])
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
        random_seed=46000 + seed_index,
    )
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != int(
        record["shared_binding"]["objective"]
    ):
        raise RuntimeError(f"E044 seed {seed_index} materialization drift")
    paths = seed_paths(seed_index)
    dump_exclusive(
        paths["assignment"],
        {
            "schema": "zmd_zero_condition_e044_geometry_seed_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "seed_index": seed_index,
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "target": row["target"],
            "replacement_pose_idx": int(record["pose_idx"]),
            "solution": solution,
        },
    )
    dump_exclusive(paths["layout"], e001.solution_layout(solution))
    dump_exclusive(paths["endpoint"], endpoint)
    return {
        "seed_index": seed_index,
        "objective": int(endpoint["objective"]),
        "delta_from_parent": int(endpoint["objective"]) - PARENT_OBJECTIVE,
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


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e001 = import_module("zmd_e044_e001", E001_RUNNER)
    e004 = import_module("zmd_e044_e004", E004_RUNNER)
    e013 = import_module("zmd_e044_e013", E013_RUNNER)
    e014 = import_module("zmd_e044_e014", E014_RUNNER)
    e015 = import_module("zmd_e044_e015", E015_RUNNER)
    e017 = import_module("zmd_e044_e017", E017_RUNNER)
    e027 = import_module("zmd_e044_e027", E027_RUNNER)
    e035 = import_module("zmd_e044_e035", E035_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    solution = load_json(E043_ASSIGNMENT)["solution"]
    endpoint = load_json(E043_ENDPOINT)
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(solution, Mapping) or not isinstance(mandatory, list):
        raise RuntimeError("E044 parent payload drift")
    solution = {str(key): dict(value) for key, value in solution.items()}
    observations, literals, observation_ids_by_literal = e035.build_incidence(
        solution=solution,
        endpoint=endpoint,
        pools=inputs["pools"],
        mandatory=mandatory,
        e013=e013,
    )
    if len(observations) != PARENT_OBJECTIVE:
        raise RuntimeError("E044 observation count drift")
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
    selected_keys = sorted(
        (str(value) for value in census["selected_literals"]),
        key=lambda key: (-len(observation_ids_by_literal[key]), key),
    )
    mobility_by_key = {
        str(row["literal_key"]): dict(row) for row in census["rows"]
    }
    occupied, _ = e014.base_occupancy(solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
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
                raise RuntimeError(f"stale E044 checkpoint: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E044_ARM_START",
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
            arm["schema"] = "zmd_zero_condition_e044_body_arm_v1"
            arm["target_coverage"] = len(observation_ids_by_literal[key])
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
                "mobility": mobility_by_key[key],
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

    dump_exclusive(
        ARM_MANIFEST_PATH,
        {
            "schema": "zmd_zero_condition_e044_arm_manifest_v1",
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
        str(load_json(E043_SEED_B_ENDPOINT)["morphology"]["free_cell_set_digest"]): 150,
        str(endpoint["morphology"]["free_cell_set_digest"]): 147,
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

    seeds = [
        materialize_seed(
            seed_index=index,
            row=row,
            parent_solution=solution,
            inputs=inputs,
            e001=e001,
            e004=e004,
            e014=e014,
            e015=e015,
            e017=e017,
            e027=e027,
        )
        for index, row in enumerate(novel[:SEED_LIMIT], 1)
    ]
    if any(seed["objective"] == 0 for seed in seeds):
        verdict = "OBJECTIVE147_BODY_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif seeds:
        verdict = "OBJECTIVE147_BODY_SEEDS_PROPOSED"
        decision = "REVALUE_GEOMETRY_SEEDS_WITH_JOINT_MIDDLE"
    else:
        verdict = "OBJECTIVE147_SINGLETON_BODY_PORTFOLIO_EMPTY"
        decision = "BUILD_SIMULTANEOUS_BODY_PAIR_NEIGHBORHOOD"

    distribution = Counter(
        int(row["record"]["shared_binding"]["objective"])
        for row in body_records
    )
    return {
        "schema": "zmd_zero_condition_e044_objective147_body_portfolio_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
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
        "objective_distribution": {
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
                "filtered_binding_option_count": int(
                    row["record"]["shared_binding"]["filtered_binding_option_count"]
                ),
            }
            for row in novel[:30]
        ],
        "materialized_seeds": seeds,
        "routing": {
            "status": (
                "READY_ZERO_SEED" if any(seed["objective"] == 0 for seed in seeds)
                else "NOT_REACHED_POSITIVE_SHARED_MISMATCH"
            )
        },
        "decision": decision,
        "truth_boundary": (
            "One exact budget-six body target portfolio under the objective-147 "
            "parent; ordinary fixed-layout values only propose geometry seeds."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E044 terminal output")
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
                    "body_optimal_candidate_count": result[
                        "body_optimal_candidate_count"
                    ],
                    "objective_distribution": result["objective_distribution"],
                    "novel_geometry_count": result["novel_geometry_count"],
                    "materialized_seeds": result["materialized_seeds"],
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
            "schema": "zmd_zero_condition_e044_objective147_body_portfolio_failure_v1",
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
