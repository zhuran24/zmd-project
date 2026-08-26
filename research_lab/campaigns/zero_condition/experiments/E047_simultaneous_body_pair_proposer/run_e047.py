#!/usr/bin/env python3
"""E047: propose simultaneous body-pair geometries at objective 144."""

from __future__ import annotations

from collections import Counter, defaultdict
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
    / "research_lab/local/zero_condition/E047_simultaneous_body_pair_proposer/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
CENSUS_PATH = OUT / "BODY_MOBILITY_CENSUS.json"
ARM_MANIFEST_PATH = OUT / "ARM_MANIFEST.json"
DEAD_DIAGNOSTICS_PATH = OUT / "DEAD_DIAGNOSTICS.json"
PAIR_MANIFEST_PATH = OUT / "PAIR_MANIFEST.json"

PARENT_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E046_objective145_integrated_geometry_portfolio/"
    "run-001/RESULT.json"
)
PARENT_ASSIGNMENT = PARENT_RESULT.with_name("SEED_A_BEST_ASSIGNMENT.json")
PARENT_ENDPOINT = PARENT_RESULT.with_name("SEED_A_BEST_ENDPOINT.json")
PARENT_FACE = PARENT_RESULT.with_name("OPTIMUM_FACE_AUDITS.json")

E046_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E046_objective145_integrated_geometry_portfolio/run_e046.py"
)
E044_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E044_objective147_body_portfolio/run_e044.py"
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
E013_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E013_residual_boundary_coverage/run_e013.py"
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
E017_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E017_third_member_portfolio/run_e017.py"
)
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E027_final_unary_discriminator/run_e027.py"
)
E035_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E035_cross_block_joint_assignment/run_e035.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "277000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    PARENT_RESULT: "cd9c45fd0c57af15306329758ad80ecf14962ba27c680cda91b0c4e8cebf59c0",
    PARENT_ASSIGNMENT: "cb67a16cc022bed9cd332aebf65962cda1fdf819ecac4b8d768f7ae6738198f4",
    PARENT_ENDPOINT: "eabbd025a69e18e905604e47f72076af11317f99c5b03d6c0ca601f0190ad59e",
    PARENT_FACE: "f77a303d9a47bf41d8d24f332095352f34f1d9109478a943d55abaf55d6a9924",
    E046_RUNNER: "b15363594654d497dc18f2a53eb12b75cc1ce0bedd3c2149acd9c40649d69648",
    E044_RUNNER: "bd453033c5683d09b84d08dba9316fd5a2f0547f889aa21e47f60c9213cecd7a",
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
}

PARENT_OBJECTIVE = 144
BODY_BUDGET = 6
TOP_OPTIMAL_PER_TARGET = 4
TOP_DIRECT_RESCUE_PER_TARGET = 3
MAX_PAIR_CANDIDATES = 180
SEED_LIMIT = 3
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


def dump_or_validate(path: Path, payload: Mapping[str, Any]) -> None:
    if not path.exists():
        dump_exclusive(path, payload)
        return
    existing = load_json(path)
    left = {key: value for key, value in existing.items() if key != "created_at_utc"}
    right = {key: value for key, value in payload.items() if key != "created_at_utc"}
    if json_safe(left) != json_safe(right):
        raise RuntimeError(f"E047 resumable artifact drift: {path}")


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


def arm_path(index: int) -> Path:
    return OUT / f"ARM_{index:02d}.json"


def family_path(index: int) -> Path:
    return OUT / f"PAIR_FAMILY_{index:02d}.json"


def seed_paths(index: int) -> dict[str, Path]:
    prefix = OUT / f"SEED_{index:02d}"
    return {
        "assignment": prefix.with_name(prefix.name + "_ASSIGNMENT.json"),
        "layout": prefix.with_name(prefix.name + "_LAYOUT.json"),
        "endpoint": prefix.with_name(prefix.name + "_ENDPOINT.json"),
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E047 must run on research/main")
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
    result = load_json(PARENT_RESULT)
    endpoint = load_json(PARENT_ENDPOINT)
    if result.get("verdict") != "OBJECTIVE145_SINGLETON_GEOMETRY_SATURATION_SIGNAL":
        raise RuntimeError("E046 parent verdict drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E046 parent endpoint drift")
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
        "empty_filtered_domains": json_safe(
            shared.get("empty_filtered_domains", [])
        ),
    }


def action_payload(
    *,
    arm_index: int,
    target: Mapping[str, Any],
    target_coverage: int,
    record: Mapping[str, Any],
    category: str,
    empty_owners: Sequence[str] = (),
) -> dict[str, Any]:
    source_ids = [str(value) for value in target["source_instance_ids"]]
    if len(source_ids) != 1:
        raise RuntimeError("E047 target lacks one source instance")
    shared = record["shared_binding"]
    return {
        "arm": arm_index,
        "target_literal": str(target["literal_key"]),
        "target_coverage": int(target_coverage),
        "source_instance_id": source_ids[0],
        "facility_type": str(target["facility_type"]),
        "operation_type": str(target.get("operation_type", "")),
        "current_pose_idx": int(target["pose_idx"]),
        "replacement_pose_idx": int(record["pose_idx"]),
        "replacement_pose_id": str(record["pose_id"]),
        "same_footprint": bool(record["same_footprint"]),
        "single_status": str(shared["status"]),
        "single_objective": (
            int(shared["objective"])
            if shared.get("objective") is not None
            else None
        ),
        "single_filtered_binding_option_count": shared.get(
            "filtered_binding_option_count"
        ),
        "single_free_cell_set_digest": shared.get("morphology", {}).get(
            "free_cell_set_digest"
        ),
        "empty_owners": sorted(str(value) for value in empty_owners),
        "category": category,
    }


def apply_action(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    action: Mapping[str, Any],
    inputs: Mapping[str, Any],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    child = {str(key): dict(value) for key, value in solution.items()}
    source_id = str(action["source_instance_id"])
    row = child.get(source_id)
    if row is None:
        raise RuntimeError(f"E047 action source absent: {source_id}")
    facility_type = str(row["facility_type"])
    if facility_type != str(action["facility_type"]):
        raise RuntimeError(f"E047 action facility drift: {source_id}")
    if int(row["pose_idx"]) != int(action["current_pose_idx"]):
        raise RuntimeError(f"E047 action current pose drift: {source_id}")
    pose_idx = int(action["replacement_pose_idx"])
    pose = inputs["pools"][facility_type][pose_idx]
    if facility_type == "power_pole":
        child.pop(source_id)
        new_id = f"pose_optional::power_pole::{pose['pose_id']}"
        if new_id in child:
            raise RuntimeError(f"E047 replacement pole already selected: {new_id}")
        source = dict(row)
        source["bound_type"] = "exact_pose_optional"
        child[new_id] = e014.replacement_row(
            source=source,
            pose=pose,
            pose_idx=pose_idx,
            instance_id=new_id,
        )
    else:
        child[source_id] = e014.replacement_row(
            source=row,
            pose=pose,
            pose_idx=pose_idx,
            instance_id=source_id,
        )
    return child


def build_pair_solution(
    *,
    parent: Mapping[str, Mapping[str, Any]],
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    inputs: Mapping[str, Any],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    if str(left["source_instance_id"]) == str(right["source_instance_id"]):
        raise RuntimeError("E047 pair aliases one source instance")
    child = apply_action(solution=parent, action=left, inputs=inputs, e014=e014)
    child = apply_action(solution=child, action=right, inputs=inputs, e014=e014)
    if sum(bool(row.get("is_mandatory")) for row in child.values()) != 266:
        raise RuntimeError("E047 pair mandatory count drift")
    if sum(str(row.get("facility_type")) == "power_pole" for row in child.values()) != 53:
        raise RuntimeError("E047 pair power-pole count drift")
    return child


def detailed_dead_diagnostics(
    *,
    arms: Sequence[Mapping[str, Any]],
    parent: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e001: Any,
    e002: Any,
    e014: Any,
    runner_sha256: str,
) -> dict[str, Any]:
    if DEAD_DIAGNOSTICS_PATH.exists():
        payload = load_json(DEAD_DIAGNOSTICS_PATH)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E047 dead diagnostics")
        return payload
    rows: list[dict[str, Any]] = []
    for arm in arms:
        target = arm["target"]
        for record in arm["candidate_records"]:
            if bool(record["same_footprint"]):
                continue
            if str(record["shared_binding"]["status"]) != "PORT_DOMAIN_EMPTY":
                continue
            action = action_payload(
                arm_index=int(arm["arm_index"]),
                target=target,
                target_coverage=int(arm["target_coverage"]),
                record=record,
                category="dead_unclassified",
            )
            child = apply_action(
                solution=parent,
                action=action,
                inputs=inputs,
                e014=e014,
            )
            diagnostic = e014.screen_component_interface(
                solution=child,
                inputs=inputs,
                e001=e001,
                e002=e002,
            )
            if diagnostic.get("status") != "PORT_DOMAIN_EMPTY":
                raise RuntimeError(
                    "E047 dead diagnostic did not reproduce PORT_DOMAIN_EMPTY: "
                    f"{action['target_literal']}->{action['replacement_pose_idx']} "
                    f"status={diagnostic.get('status')}"
                )
            rows.append(
                {
                    "action_key": (
                        f"{action['source_instance_id']}@"
                        f"{action['current_pose_idx']}->{action['replacement_pose_idx']}"
                    ),
                    "action": action,
                    "empty_filtered_domains": sorted(
                        str(value)
                        for value in diagnostic.get("empty_filtered_domains", [])
                    ),
                    "empty_filtered_domain_count": int(
                        diagnostic.get("empty_filtered_domain_count", 0)
                    ),
                    "morphology": diagnostic.get("morphology"),
                    "filtered_binding_option_count": diagnostic.get(
                        "filtered_binding_option_count"
                    ),
                }
            )
    payload = {
        "schema": "zmd_zero_condition_e047_dead_diagnostics_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "parent_objective": PARENT_OBJECTIVE,
        "row_count": len(rows),
        "rows": rows,
        "ledger_effect": "none",
    }
    dump_exclusive(DEAD_DIAGNOSTICS_PATH, payload)
    return payload


def build_action_pools(
    *,
    arms: Sequence[Mapping[str, Any]],
    dead_payload: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    selected_source_ids = {
        str(arm["target"]["source_instance_ids"][0]) for arm in arms
    }
    dead_by_key = {
        str(row["action_key"]): dict(row) for row in dead_payload["rows"]
    }
    pools: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, Any] = {}
    for arm in arms:
        target = arm["target"]
        source_id = str(target["source_instance_ids"][0])
        optimal_records = [
            record
            for record in arm["candidate_records"]
            if not bool(record["same_footprint"])
            and str(record["shared_binding"]["status"]) == "OPTIMAL"
        ]
        optimal_records.sort(
            key=lambda record: (
                int(record["shared_binding"]["objective"]),
                -int(record["shared_binding"].get("filtered_binding_option_count", 0)),
                int(record["pose_idx"]),
            )
        )
        chosen: list[dict[str, Any]] = []
        seen_free: set[str] = set()
        for record in optimal_records:
            free_digest = str(
                record["shared_binding"]["morphology"]["free_cell_set_digest"]
            )
            if free_digest in seen_free:
                continue
            seen_free.add(free_digest)
            chosen.append(
                action_payload(
                    arm_index=int(arm["arm_index"]),
                    target=target,
                    target_coverage=int(arm["target_coverage"]),
                    record=record,
                    category="ordinary_optimal",
                )
            )
            if len(chosen) >= TOP_OPTIMAL_PER_TARGET:
                break

        direct_rows: list[dict[str, Any]] = []
        for record in arm["candidate_records"]:
            if bool(record["same_footprint"]):
                continue
            if str(record["shared_binding"]["status"]) != "PORT_DOMAIN_EMPTY":
                continue
            action_key = f"{source_id}@{target['pose_idx']}->{record['pose_idx']}"
            diagnostic = dead_by_key.get(action_key)
            if diagnostic is None:
                raise RuntimeError(f"E047 missing dead diagnostic: {action_key}")
            direct = sorted(
                set(str(value) for value in diagnostic["empty_filtered_domains"])
                & (selected_source_ids - {source_id})
            )
            if not direct:
                continue
            direct_rows.append(
                action_payload(
                    arm_index=int(arm["arm_index"]),
                    target=target,
                    target_coverage=int(arm["target_coverage"]),
                    record=record,
                    category="direct_rescue_required",
                    empty_owners=direct,
                )
            )
        direct_rows.sort(
            key=lambda action: (
                -len(action["empty_owners"]),
                int(action["replacement_pose_idx"]),
            )
        )
        chosen.extend(direct_rows[:TOP_DIRECT_RESCUE_PER_TARGET])
        pools[source_id] = chosen
        summaries[source_id] = {
            "target_literal": str(target["literal_key"]),
            "target_coverage": int(arm["target_coverage"]),
            "ordinary_optimal_action_count": sum(
                action["category"] == "ordinary_optimal" for action in chosen
            ),
            "direct_rescue_action_count": sum(
                action["category"] == "direct_rescue_required" for action in chosen
            ),
            "pool_size": len(chosen),
        }
    return pools, summaries


def build_pair_specs(
    *,
    action_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_ids = sorted(action_pools)
    rows: list[dict[str, Any]] = []
    for left_index, left_source in enumerate(source_ids):
        for right_source in source_ids[left_index + 1 :]:
            left_pool = action_pools[left_source]
            right_pool = action_pools[right_source]
            for left in left_pool:
                for right in right_pool:
                    left_dead = left["category"] == "direct_rescue_required"
                    right_dead = right["category"] == "direct_rescue_required"
                    rescue_relation = (
                        right_source in set(left["empty_owners"])
                        or left_source in set(right["empty_owners"])
                    )
                    if (left_dead or right_dead) and not rescue_relation:
                        continue
                    predicted = None
                    if left["single_objective"] is not None and right["single_objective"] is not None:
                        predicted = (
                            int(left["single_objective"])
                            + int(right["single_objective"])
                            - PARENT_OBJECTIVE
                        )
                    category = "direct_rescue" if rescue_relation else "value_composition"
                    rows.append(
                        {
                            "pair_key": (
                                f"{left_source}@{left['replacement_pose_idx']} + "
                                f"{right_source}@{right['replacement_pose_idx']}"
                            ),
                            "target_pair": [left_source, right_source],
                            "left": json_safe(left),
                            "right": json_safe(right),
                            "category": category,
                            "rescue_relation": rescue_relation,
                            "union_target_coverage_upper": (
                                int(left["target_coverage"])
                                + int(right["target_coverage"])
                            ),
                            "predicted_additive_objective": predicted,
                        }
                    )
    rows.sort(
        key=lambda row: (
            0 if row["category"] == "direct_rescue" else 1,
            (
                int(row["predicted_additive_objective"])
                if row["predicted_additive_objective"] is not None
                else 10**9
            ),
            -int(row["union_target_coverage_upper"]),
            str(row["pair_key"]),
        )
    )
    selected = rows[:MAX_PAIR_CANDIDATES]
    return rows, selected


def evaluate_pair_family(
    *,
    family_index: int,
    target_pair: Sequence[str],
    specs: Sequence[Mapping[str, Any]],
    parent: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    power: Mapping[str, Any],
    e001: Any,
    e002: Any,
    e004: Any,
    e014: Any,
    e015: Any,
    runner_sha256: str,
) -> dict[str, Any]:
    path = family_path(family_index)
    spec_digest = stable_digest(specs)
    if path.exists():
        payload = load_json(path)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError(f"stale E047 pair family: {path}")
        if str(payload.get("pair_spec_digest")) != spec_digest:
            raise RuntimeError(f"E047 pair family spec drift: {path}")
        return payload

    records: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, 1):
        try:
            child = build_pair_solution(
                parent=parent,
                left=spec["left"],
                right=spec["right"],
                inputs=inputs,
                e014=e014,
            )
            e014.base_occupancy(child, inputs["pools"])
        except RuntimeError as exc:
            records.append(
                {
                    "pair_key": spec["pair_key"],
                    "pair_spec": json_safe(spec),
                    "status": "OVERLAP_OR_TRANSPORT_REJECTED",
                    "detail": str(exc),
                    "shared_binding": None,
                }
            )
            continue

        selected_poles = {
            int(row["pose_idx"])
            for row in child.values()
            if str(row["facility_type"]) == "power_pole"
        }
        if not e014.all_powered_facilities_covered(
            solution=child,
            selected_poles=selected_poles,
            powered_templates=power["powered_templates"],
            coverers=power["coverers"],
        ):
            records.append(
                {
                    "pair_key": spec["pair_key"],
                    "pair_spec": json_safe(spec),
                    "status": "POWER_REJECTED",
                    "detail": None,
                    "shared_binding": None,
                }
            )
            continue

        try:
            shared = e015.solve_shared_mismatch(
                solution=child,
                inputs=inputs,
                e004=e004,
                random_seed=470000 + family_index * 1000 + index,
                include_boundaries=False,
            )
        except RuntimeError as exc:
            if "empty binding domain" not in str(exc):
                raise
            diagnostic = e014.screen_component_interface(
                solution=child,
                inputs=inputs,
                e001=e001,
                e002=e002,
            )
            if diagnostic.get("status") != "PORT_DOMAIN_EMPTY":
                raise RuntimeError(
                    "E047 pair empty-domain exception did not reproduce: "
                    f"{diagnostic.get('status')}"
                )
            shared = {
                "status": "PORT_DOMAIN_EMPTY",
                "objective": None,
                "empty_filtered_domains": diagnostic.get(
                    "empty_filtered_domains", []
                ),
                "filtered_binding_option_count": diagnostic.get(
                    "filtered_binding_option_count"
                ),
                "morphology": diagnostic.get("morphology"),
            }
        compact = compact_shared(shared)
        record = {
            "pair_key": spec["pair_key"],
            "pair_spec": json_safe(spec),
            "status": str(compact["status"]),
            "candidate_solution_digest": stable_digest(child),
            "shared_binding": compact,
        }
        if compact.get("objective") is not None:
            predicted = spec.get("predicted_additive_objective")
            record["pair_synergy_vs_additive"] = (
                int(compact["objective"]) - int(predicted)
                if predicted is not None
                else None
            )
        records.append(record)
        if index % 20 == 0 or compact.get("objective") == 0:
            print(
                json.dumps(
                    {
                        "event": "E047_PAIR_PROGRESS",
                        "family": family_index,
                        "candidate": index,
                        "candidate_total": len(specs),
                        "status": compact.get("status"),
                        "objective": compact.get("objective"),
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    payload = {
        "schema": "zmd_zero_condition_e047_pair_family_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "parent_objective": PARENT_OBJECTIVE,
        "family_index": family_index,
        "target_pair": list(target_pair),
        "pair_spec_digest": spec_digest,
        "candidate_count": len(specs),
        "status_counts": dict(sorted(Counter(row["status"] for row in records).items())),
        "records": records,
        "ledger_effect": "none",
    }
    dump_exclusive(path, payload)
    return payload


def reconstruct_pair_from_record(
    *,
    record: Mapping[str, Any],
    parent: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    spec = record["pair_spec"]
    return build_pair_solution(
        parent=parent,
        left=spec["left"],
        right=spec["right"],
        inputs=inputs,
        e014=e014,
    )


def materialize_seed(
    *,
    seed_index: int,
    record: Mapping[str, Any],
    parent: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e001: Any,
    e004: Any,
    e014: Any,
    e015: Any,
    e027: Any,
) -> dict[str, Any]:
    paths = seed_paths(seed_index)
    child = reconstruct_pair_from_record(
        record=record,
        parent=parent,
        inputs=inputs,
        e014=e014,
    )
    endpoint = e027.materialize_shared_endpoint(
        solution=child,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=471000 + seed_index,
    )
    expected = int(record["shared_binding"]["objective"])
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != expected:
        raise RuntimeError(f"E047 seed {seed_index} materialization drift")
    dump_exclusive(
        paths["assignment"],
        {
            "schema": "zmd_zero_condition_e047_pair_seed_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "seed_index": seed_index,
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": expected,
            "pair_spec": record["pair_spec"],
            "solution": child,
        },
    )
    dump_exclusive(paths["layout"], e001.solution_layout(child))
    dump_exclusive(paths["endpoint"], endpoint)
    return {
        "seed_index": seed_index,
        "objective": expected,
        "delta_from_parent": expected - PARENT_OBJECTIVE,
        "target_pair": record["pair_spec"]["target_pair"],
        "pair_key": record["pair_key"],
        "category": record["pair_spec"]["category"],
        "pair_synergy_vs_additive": record.get("pair_synergy_vs_additive"),
        "placement_digest": stable_digest(child),
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
    e044 = import_module("zmd_e047_e044", E044_RUNNER)
    e001 = import_module("zmd_e047_e001", E001_RUNNER)
    e002 = import_module("zmd_e047_e002", E002_RUNNER)
    e004 = import_module("zmd_e047_e004", E004_RUNNER)
    e013 = import_module("zmd_e047_e013", E013_RUNNER)
    e014 = import_module("zmd_e047_e014", E014_RUNNER)
    e015 = import_module("zmd_e047_e015", E015_RUNNER)
    e017 = import_module("zmd_e047_e017", E017_RUNNER)
    e027 = import_module("zmd_e047_e027", E027_RUNNER)
    e035 = import_module("zmd_e047_e035", E035_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent = {
        str(key): dict(value)
        for key, value in load_json(PARENT_ASSIGNMENT)["solution"].items()
    }
    endpoint = load_json(PARENT_ENDPOINT)
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(mandatory, list):
        raise RuntimeError("E047 mandatory payload drift")
    observations, literals, observation_ids_by_literal = e035.build_incidence(
        solution=parent,
        endpoint=endpoint,
        pools=inputs["pools"],
        mandatory=mandatory,
        e013=e013,
    )
    if len(observations) != PARENT_OBJECTIVE:
        raise RuntimeError("E047 observation count drift")
    allowed = {
        key: dict(value)
        for key, value in literals.items()
        if str(value.get("kind")) in {"mandatory_group_pose", "optional_pose"}
        and str(value.get("facility_type")) not in EXCLUDED_FACILITY_TYPES
        and len(value.get("source_instance_ids", [])) == 1
    }

    old_out = e044.OUT
    old_census = e044.CENSUS_PATH
    old_objective = e044.PARENT_OBJECTIVE
    old_budget = e044.BODY_BUDGET
    try:
        e044.OUT = OUT
        e044.CENSUS_PATH = CENSUS_PATH
        e044.PARENT_OBJECTIVE = PARENT_OBJECTIVE
        e044.BODY_BUDGET = BODY_BUDGET
        census = e044.build_or_load_census(
            identity=identity,
            solution=parent,
            endpoint=endpoint,
            observations=observations,
            literals=literals,
            observation_ids_by_literal=observation_ids_by_literal,
            inputs=inputs,
            e013=e013,
            e014=e014,
            e001=e001,
        )
    finally:
        e044.OUT = old_out
        e044.CENSUS_PATH = old_census
        e044.PARENT_OBJECTIVE = old_objective
        e044.BODY_BUDGET = old_budget

    selected_keys = sorted(
        (str(value) for value in census["selected_literals"]),
        key=lambda key: (-len(observation_ids_by_literal[key]), key),
    )
    occupied, _ = e014.base_occupancy(parent, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in parent.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)

    arms: list[dict[str, Any]] = []
    arm_manifest: list[dict[str, Any]] = []
    for index, key in enumerate(selected_keys, 1):
        path = arm_path(index)
        if path.exists():
            arm = load_json(path)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E047 arm: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E047_ARM_START",
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
                target=allowed[key],
                pair_solution=parent,
                occupied=occupied,
                selected_poles=selected_poles,
                inputs=inputs,
                power=power,
                e004=e004,
                e014=e014,
                e015=e015,
                runner_sha256=runner_sha256,
            )
            arm["schema"] = "zmd_zero_condition_e047_single_body_arm_v1"
            arm["target_coverage"] = len(observation_ids_by_literal[key])
            dump_exclusive(path, arm)
        arms.append(arm)
        arm_manifest.append(
            {
                "arm": index,
                "target": key,
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
        )
    dump_or_validate(
        ARM_MANIFEST_PATH,
        {
            "schema": "zmd_zero_condition_e047_arm_manifest_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "runner_sha256": runner_sha256,
            "parent_objective": PARENT_OBJECTIVE,
            "selected_literals": selected_keys,
            "arms": arm_manifest,
            "ledger_effect": "none",
        },
    )

    dead_payload = detailed_dead_diagnostics(
        arms=arms,
        parent=parent,
        inputs=inputs,
        e001=e001,
        e002=e002,
        e014=e014,
        runner_sha256=runner_sha256,
    )
    action_pools, action_pool_summary = build_action_pools(
        arms=arms,
        dead_payload=dead_payload,
    )
    all_specs, selected_specs = build_pair_specs(action_pools=action_pools)

    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for spec in selected_specs:
        pair = tuple(str(value) for value in spec["target_pair"])
        by_pair[pair].append(spec)
    families: list[dict[str, Any]] = []
    pair_manifest: list[dict[str, Any]] = []
    all_records: list[dict[str, Any]] = []
    for family_index, pair in enumerate(sorted(by_pair), 1):
        family = evaluate_pair_family(
            family_index=family_index,
            target_pair=pair,
            specs=by_pair[pair],
            parent=parent,
            inputs=inputs,
            power=power,
            e001=e001,
            e002=e002,
            e004=e004,
            e014=e014,
            e015=e015,
            runner_sha256=runner_sha256,
        )
        families.append(family)
        all_records.extend(family["records"])
        path = family_path(family_index)
        pair_manifest.append(
            {
                "family": family_index,
                "target_pair": list(pair),
                "candidate_count": int(family["candidate_count"]),
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
        )
    dump_or_validate(
        PAIR_MANIFEST_PATH,
        {
            "schema": "zmd_zero_condition_e047_pair_manifest_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "runner_sha256": runner_sha256,
            "parent_objective": PARENT_OBJECTIVE,
            "all_pair_spec_count": len(all_specs),
            "selected_pair_spec_count": len(selected_specs),
            "families": pair_manifest,
            "ledger_effect": "none",
        },
    )

    optimal = [
        record
        for record in all_records
        if record.get("shared_binding") is not None
        and str(record["shared_binding"]["status"]) == "OPTIMAL"
    ]
    optimal.sort(
        key=lambda record: (
            int(record["shared_binding"]["objective"]),
            -int(record["shared_binding"].get("filtered_binding_option_count", 0)),
            (
                int(record["pair_synergy_vs_additive"])
                if record.get("pair_synergy_vs_additive") is not None
                else 10**9
            ),
            str(record["pair_key"]),
        )
    )
    parent_free = str(endpoint["morphology"]["free_cell_set_digest"])
    novel_optimal: list[dict[str, Any]] = []
    seen_free = {parent_free}
    for record in optimal:
        digest = str(record["shared_binding"]["morphology"]["free_cell_set_digest"])
        if digest in seen_free:
            continue
        seen_free.add(digest)
        novel_optimal.append(record)

    selected_seed_records: list[dict[str, Any]] = []
    used_pairs: set[tuple[str, str]] = set()
    for record in novel_optimal:
        target_pair = tuple(record["pair_spec"]["target_pair"])
        if target_pair in used_pairs and len(selected_seed_records) < 2:
            continue
        selected_seed_records.append(record)
        used_pairs.add(target_pair)
        if len(selected_seed_records) >= SEED_LIMIT:
            break
    if len(selected_seed_records) < SEED_LIMIT:
        for record in novel_optimal:
            if record in selected_seed_records:
                continue
            selected_seed_records.append(record)
            if len(selected_seed_records) >= SEED_LIMIT:
                break

    seeds = [
        materialize_seed(
            seed_index=index,
            record=record,
            parent=parent,
            inputs=inputs,
            e001=e001,
            e004=e004,
            e014=e014,
            e015=e015,
            e027=e027,
        )
        for index, record in enumerate(selected_seed_records, 1)
    ]

    zero_records = [record for record in optimal if int(record["shared_binding"]["objective"]) == 0]
    if zero_records:
        best_solution = reconstruct_pair_from_record(
            record=zero_records[0],
            parent=parent,
            inputs=inputs,
            e014=e014,
        )
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        verdict = "BODY_PAIR_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif seeds:
        routing = {"status": "NOT_REACHED_PAIR_PROPOSAL_ONLY"}
        verdict = "BODY_PAIR_GEOMETRY_SEEDS_PROPOSED"
        decision = "REVALUE_PAIR_GEOMETRIES_WITH_JOINT_MIDDLE"
    else:
        routing = {"status": "NOT_REACHED_NO_DOMAIN_VALID_PAIR"}
        verdict = "BODY_PAIR_PORTFOLIO_EMPTY"
        decision = "BROADEN_OR_NATIVE_SIMULTANEOUS_GEOMETRY_MODEL"

    status_counts = Counter(record["status"] for record in all_records)
    objective_distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal
    )
    rescue_optimal = sum(
        record["pair_spec"]["category"] == "direct_rescue" for record in optimal
    )
    negative_synergy = [
        record
        for record in optimal
        if record.get("pair_synergy_vs_additive") is not None
        and int(record["pair_synergy_vs_additive"]) < 0
    ]
    return {
        "schema": "zmd_zero_condition_e047_simultaneous_body_pair_proposer_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "parent_objective": PARENT_OBJECTIVE,
        "observation_count": len(observations),
        "literal_count": len(literals),
        "coverage": census["coverage"],
        "selected_literals": selected_keys,
        "arm_manifest_path": str(ARM_MANIFEST_PATH.relative_to(ROOT)),
        "arm_manifest_sha256": sha256_file(ARM_MANIFEST_PATH),
        "dead_diagnostics_path": str(DEAD_DIAGNOSTICS_PATH.relative_to(ROOT)),
        "dead_diagnostics_sha256": sha256_file(DEAD_DIAGNOSTICS_PATH),
        "dead_diagnostic_count": int(dead_payload["row_count"]),
        "action_pool_summary": action_pool_summary,
        "all_pair_spec_count": len(all_specs),
        "selected_pair_spec_count": len(selected_specs),
        "pair_manifest_path": str(PAIR_MANIFEST_PATH.relative_to(ROOT)),
        "pair_manifest_sha256": sha256_file(PAIR_MANIFEST_PATH),
        "pair_family_count": len(families),
        "pair_status_counts": dict(sorted(status_counts.items())),
        "ordinary_optimal_pair_count": len(optimal),
        "direct_rescue_optimal_pair_count": rescue_optimal,
        "negative_synergy_pair_count": len(negative_synergy),
        "ordinary_objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "top_pairs": optimal[:30],
        "novel_optimal_geometry_count": len(novel_optimal),
        "materialized_seeds": seeds,
        "routing": routing,
        "decision": decision,
        "truth_boundary": (
            "One exact budget-six body target set, a bounded pair action portfolio "
            "formed from up to four domain-valid and three direct-rescue actions per "
            "target, and ordinary shared-binding evaluation of at most 180 pairs."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E047 terminal output")
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
                    "selected_pair_spec_count": result["selected_pair_spec_count"],
                    "pair_status_counts": result["pair_status_counts"],
                    "ordinary_optimal_pair_count": result[
                        "ordinary_optimal_pair_count"
                    ],
                    "direct_rescue_optimal_pair_count": result[
                        "direct_rescue_optimal_pair_count"
                    ],
                    "negative_synergy_pair_count": result[
                        "negative_synergy_pair_count"
                    ],
                    "ordinary_objective_distribution": result[
                        "ordinary_objective_distribution"
                    ],
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
            "schema": "zmd_zero_condition_e047_simultaneous_body_pair_proposer_failure_v1",
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
