#!/usr/bin/env python3
"""E013: exact set/window coverage of E009 residual mismatch boundaries.

Research-only. Coverage identifies which current pose literals touch observed
mismatch-component boundaries. It does not prove that moving a covered literal
repairs the mismatch.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
import traceback
from typing import Any, Iterable, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
E009_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/RESULT.json"
)
E009_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/PATTERN_EXPOSED_ASSIGNMENT.json"
)
E009_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/PATTERN_EXPOSED_LAYOUT.json"
)
E010_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E010_pattern_exposed_mismatch_delta/run-001/RESULT.json"
)
OUT = ROOT / "research_lab/local/zero_condition/E013_residual_boundary_coverage/run-004"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

EXPECTED_HASHES: dict[Path, str] = {
    E009_RESULT: "c0bce86fd9d2871621a28c883b57f51c3e3e7b5f5efbba9b96c23ea6c55dccec",
    E009_ASSIGNMENT: "7a4a2a21cc13621e935fc6672bfa9f691e2d340ec120ec0947b3b62b3d648924",
    E009_LAYOUT: "3b23f3f801d5b06f5cde90beb7ceb5074101d2be543b141e68ab432940e70d33",
    E010_RESULT: "6e0965a159c52c6e49a5e0c8afc2a57472f8df0669d5631ed04c73749770d4fe",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "rules/canonical_rules.json": "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0",
    ROOT / "src/models/master_model.py": "d1ada57bc6dcef1818341b26dfd482fb7c1623d106734b8f1a49061c2e7c1371",
    ROOT / "src/models/pose_bool_exact_master.py": "8991b7f98b95ee255c4967b13fc2d22bf6eed5ec54ad1f0e48377a44db0dbd90",
}

LITERAL_BUDGETS = (1, 2, 4, 8, 16, 32, 64)
TARGET_FRACTIONS = (0.50, 0.75, 0.90, 1.00)
WINDOW_SIZES = (8, 12, 16, 20, 24, 28, 32, 40)
GRID_W = 70
GRID_H = 70
SOLVE_CAP_SECONDS = 30.0


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


def verify_identity() -> dict[str, Any]:
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")
    if load_json(E009_RESULT).get("verdict") != "PATTERN_EXPOSED_CANDIDATE":
        raise RuntimeError("E009 trigger drift")
    if load_json(E010_RESULT).get("verdict") != "ALTERNATING_CONSTRUCTOR_SECOND_BROAD_IMPROVEMENT":
        raise RuntimeError("E010 trigger drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def reconstruct_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E009_ASSIGNMENT)
    layout = load_json(E009_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E009 assignment/layout structure is invalid")
    solution = {
        str(instance_id): dict(record)
        for instance_id, record in raw.items()
        if isinstance(record, Mapping)
    }
    layout_solution = {
        str(record["instance_id"]): dict(record)
        for record in placements
        if isinstance(record, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E009 assignment and layout disagree")
    if sum(bool(row.get("is_mandatory")) for row in solution.values()) != 266:
        raise RuntimeError("E009 mandatory count drift")
    return solution


def group_mapping(
    mandatory_instances: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for instance in mandatory_instances:
        grouped[
            (
                str(instance.get("facility_type", "")),
                str(instance.get("operation_type", "")),
            )
        ].append(str(instance["instance_id"]))
    mapping: dict[str, str] = {}
    for group_index, ((facility_type, operation_type), members) in enumerate(
        sorted(grouped.items())
    ):
        group_id = f"group::{facility_type}::{operation_type}::{group_index}"
        for instance_id in sorted(members):
            mapping[instance_id] = group_id
    if len(mapping) != 266:
        raise RuntimeError(f"group mapping count drift: {len(mapping)}")
    return mapping


def literal_identity(
    *,
    owner: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
    group_by_instance: Mapping[str, str],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[str, dict[str, Any]]:
    instance_id = str(owner["instance_id"])
    row = solution.get(instance_id)
    if row is None:
        raise RuntimeError(f"boundary owner absent from E009 solution: {instance_id}")
    for field in ("facility_type", "operation_type", "pose_idx"):
        if str(owner.get(field, "")) != str(row.get(field, "")):
            raise RuntimeError(
                f"boundary owner/solution drift for {instance_id} field {field}"
            )
    facility_type = str(row["facility_type"])
    operation_type = str(row.get("operation_type", ""))
    pose_idx = int(row["pose_idx"])
    if bool(row.get("is_mandatory")):
        group_id = group_by_instance.get(instance_id)
        if group_id is None:
            raise RuntimeError(f"mandatory owner lacks group: {instance_id}")
        key = f"mandatory::{group_id}::{pose_idx}"
        kind = "mandatory_group_pose"
        consumer_id = group_id
    else:
        key = f"optional::{facility_type}::{pose_idx}"
        kind = "optional_pose"
        consumer_id = facility_type
    pool = facility_pools.get(facility_type)
    if not isinstance(pool, list) or not (0 <= pose_idx < len(pool)):
        raise RuntimeError(
            f"boundary owner pose is absent from the frozen pool: "
            f"{instance_id} {facility_type}@{pose_idx}"
        )
    pose = pool[pose_idx]
    if str(row.get("pose_id", "")) != str(pose.get("pose_id", "")):
        raise RuntimeError(f"boundary owner pose identity drift: {instance_id}")
    raw_cells = pose.get("occupied_cells")
    if not isinstance(raw_cells, list) or not raw_cells:
        raise RuntimeError(f"frozen pose has no occupied cells: {instance_id}")
    cells = sorted({(int(cell[0]), int(cell[1])) for cell in raw_cells})
    observed_cells = owner.get("occupied_cells")
    if isinstance(observed_cells, list) and observed_cells:
        observed = sorted({(int(cell[0]), int(cell[1])) for cell in observed_cells})
        if observed != cells:
            raise RuntimeError(f"boundary owner/frozen pose cell drift: {instance_id}")
    payload = {
        "literal_key": key,
        "kind": kind,
        "consumer_id": consumer_id,
        "facility_type": facility_type,
        "operation_type": operation_type,
        "pose_idx": pose_idx,
        "pose_id": str(row.get("pose_id", "")),
        "occupied_cells": cells,
        "source_instance_ids": [instance_id],
        "anchor": {
            "x": int(dict(row.get("anchor", {})).get("x", 0)),
            "y": int(dict(row.get("anchor", {})).get("y", 0)),
        },
    }
    return key, payload


def build_observations() -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, set[int]],
]:
    solution = reconstruct_solution()
    mandatory_instances = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(mandatory_instances, list):
        raise RuntimeError("mandatory instances are not a list")
    group_by_instance = group_mapping(mandatory_instances)
    atlas = load_json(E010_RESULT)
    candidate_payload = load_json(
        HISTORY_ROOT / "data/preprocessed/candidate_placements.json"
    )
    facility_pools = candidate_payload.get("facility_pools")
    if not isinstance(facility_pools, Mapping):
        raise RuntimeError("candidate placement artifact lacks facility_pools")

    observations: list[dict[str, Any]] = []
    literals: dict[str, dict[str, Any]] = {}
    observation_ids_by_literal: dict[str, set[int]] = defaultdict(set)
    for commodity_row in atlas["commodity_results"]:
        commodity = str(commodity_row["commodity"])
        selected_components = commodity_row.get("selected_components")
        if not isinstance(selected_components, Mapping):
            raise RuntimeError(f"commodity row lacks selected_components: {commodity}")
        source_only = {
            int(value) for value in selected_components.get("source_only_components", [])
        }
        sink_only = {
            int(value) for value in selected_components.get("sink_only_components", [])
        }
        if source_only & sink_only:
            raise RuntimeError(f"mismatch role sets overlap for {commodity}")
        for boundary in commodity_row["mismatch_boundaries"]:
            component_id = int(boundary["component_id"])
            if component_id in source_only:
                role = "source_only"
            elif component_id in sink_only:
                role = "sink_only"
            else:
                raise RuntimeError(
                    f"mismatch boundary lacks XOR role for {commodity}:{component_id}"
                )
            observation_id = len(observations)
            literal_keys: set[str] = set()
            for owner in boundary["boundary_owners"]:
                key, payload = literal_identity(
                    owner=owner,
                    solution=solution,
                    group_by_instance=group_by_instance,
                    facility_pools=facility_pools,
                )
                existing = literals.get(key)
                if existing is None:
                    literals[key] = payload
                else:
                    existing["source_instance_ids"] = sorted(
                        set(existing["source_instance_ids"])
                        | set(payload["source_instance_ids"])
                    )
                    if existing["occupied_cells"] != payload["occupied_cells"]:
                        raise RuntimeError(f"consumer literal cell drift for {key}")
                literal_keys.add(key)
            observations.append(
                {
                    "observation_id": observation_id,
                    "commodity": commodity,
                    "component": component_id,
                    "component_size": int(boundary["component_size"]),
                    "role": role,
                    "literal_keys": sorted(literal_keys),
                    "boundary_owner_count": int(boundary["boundary_owner_count"]),
                }
            )
            for key in literal_keys:
                observation_ids_by_literal[key].add(observation_id)
    if len(observations) != int(atlas["aggregate"]["e009_total"]):
        raise RuntimeError(
            f"observation count drift: {len(observations)} != "
            f"{atlas['aggregate']['e009_total']}"
        )
    return observations, literals, observation_ids_by_literal


def build_coverage_classes(
    *,
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
) -> list[dict[str, Any]]:
    """Quotient literals that touch exactly the same observed boundaries.

    The quotient is exact for this set-cover question only. It does not claim
    that two member literals are interchangeable in placement or power.
    """

    members_by_observations: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for key in sorted(literals):
        observation_ids = tuple(sorted(observation_ids_by_literal.get(key, set())))
        if not observation_ids:
            raise RuntimeError(f"literal has no observed boundary incidence: {key}")
        members_by_observations[observation_ids].append(key)

    classes: list[dict[str, Any]] = []
    for observation_ids, members in sorted(
        members_by_observations.items(), key=lambda item: (item[0], item[1])
    ):
        member_literals = sorted(members)
        pole_members = [
            key
            for key in member_literals
            if str(literals[key]["facility_type"]) == "power_pole"
        ]
        representative = pole_members[0] if pole_members else member_literals[0]
        classes.append(
            {
                "class_id": stable_digest(
                    {
                        "observation_ids": observation_ids,
                        "member_literals": member_literals,
                    }
                ),
                "observation_ids": list(observation_ids),
                "member_literals": member_literals,
                "member_count": len(member_literals),
                "has_power_pole_member": bool(pole_members),
                "power_pole_members": pole_members,
                "representative_literal": representative,
            }
        )
    return classes


def build_coverage_model(
    *,
    observation_count: int,
    coverage_classes: Sequence[Mapping[str, Any]],
) -> tuple[cp_model.CpModel, list[Any], list[Any]]:
    model = cp_model.CpModel()
    select = [
        model.NewBoolVar(f"select_class_{index}")
        for index in range(len(coverage_classes))
    ]
    cover: list[Any] = []
    for observation_id in range(observation_count):
        covering = [
            select[index]
            for index, row in enumerate(coverage_classes)
            if observation_id in row["observation_ids"]
        ]
        variable = model.NewBoolVar(f"cover_{observation_id}")
        if covering:
            model.AddMaxEquality(variable, covering)
        else:
            model.Add(variable == 0)
        cover.append(variable)
    return model, select, cover


def selected_class_projection(
    *,
    selected_indices: Sequence[int],
    coverage_classes: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], int]:
    representatives: list[str] = []
    details: list[dict[str, Any]] = []
    non_power_pole_count = 0
    for index in selected_indices:
        row = coverage_classes[index]
        representative = str(row["representative_literal"])
        representatives.append(representative)
        non_power_pole_count += int(not bool(row["has_power_pole_member"]))
        details.append(json_safe(row))
    return representatives, details, non_power_pole_count


def exact_max_coverage(
    *,
    observations: Sequence[Mapping[str, Any]],
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
    budget: int,
) -> dict[str, Any]:
    coverage_classes = build_coverage_classes(
        literals=literals,
        observation_ids_by_literal=observation_ids_by_literal,
    )
    model, select, cover = build_coverage_model(
        observation_count=len(observations),
        coverage_classes=coverage_classes,
    )
    model.Add(sum(select) <= int(budget))
    model.Maximize(sum(cover))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_CAP_SECONDS
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = 260831 + int(budget)
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    if status != cp_model.OPTIMAL:
        raise RuntimeError(f"max coverage k={budget} not OPTIMAL: {status_name}")
    optimum_coverage = int(round(solver.ObjectiveValue()))

    # Among all maximum-coverage solutions, first minimize classes that cannot
    # be represented by a power pole, then minimize the selected class count.
    secondary, secondary_select, secondary_cover = build_coverage_model(
        observation_count=len(observations),
        coverage_classes=coverage_classes,
    )
    secondary.Add(sum(secondary_select) <= int(budget))
    secondary.Add(sum(secondary_cover) == optimum_coverage)
    non_pole_terms = [
        secondary_select[index]
        for index, row in enumerate(coverage_classes)
        if not bool(row["has_power_pole_member"])
    ]
    secondary.Minimize(
        (len(coverage_classes) + 1) * sum(non_pole_terms)
        + sum(secondary_select)
    )
    secondary_solver = cp_model.CpSolver()
    secondary_solver.parameters.max_time_in_seconds = SOLVE_CAP_SECONDS
    secondary_solver.parameters.num_search_workers = 8
    secondary_solver.parameters.random_seed = 261831 + int(budget)
    secondary_status = secondary_solver.Solve(secondary)
    if secondary_status != cp_model.OPTIMAL:
        raise RuntimeError(
            f"max coverage k={budget} secondary optimization not OPTIMAL: "
            f"{secondary_solver.StatusName(secondary_status)}"
        )
    selected_indices = [
        index
        for index, variable in enumerate(secondary_select)
        if secondary_solver.Value(variable) == 1
    ]
    chosen, class_details, non_power_pole_count = selected_class_projection(
        selected_indices=selected_indices,
        coverage_classes=coverage_classes,
    )
    covered = [
        index
        for index, variable in enumerate(secondary_cover)
        if secondary_solver.Value(variable) == 1
    ]
    return {
        "budget": int(budget),
        "covered_count": len(covered),
        "coverage_fraction": len(covered) / len(observations),
        "selected_literal_count": len(chosen),
        "selected_literals": chosen,
        "selected_coverage_classes": class_details,
        "minimum_non_power_pole_class_count_at_optimum": non_power_pole_count,
        "all_power_pole_optimum_exists": non_power_pole_count == 0,
        "coverage_class_count": len(coverage_classes),
        "covered_observation_ids_digest": stable_digest(covered),
    }


def exact_min_literals_for_target(
    *,
    observations: Sequence[Mapping[str, Any]],
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
    target_count: int,
) -> dict[str, Any]:
    coverage_classes = build_coverage_classes(
        literals=literals,
        observation_ids_by_literal=observation_ids_by_literal,
    )
    model, select, cover = build_coverage_model(
        observation_count=len(observations),
        coverage_classes=coverage_classes,
    )
    model.Add(sum(cover) >= int(target_count))
    model.Minimize(sum(select))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_CAP_SECONDS
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = 260900 + int(target_count)
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    if status == cp_model.INFEASIBLE:
        return {
            "target_count": int(target_count),
            "status": "INFEASIBLE",
            "minimum_literal_count": None,
            "selected_literals": [],
            "selected_coverage_classes": [],
        }
    if status != cp_model.OPTIMAL:
        raise RuntimeError(
            f"min cover target={target_count} not OPTIMAL: {status_name}"
        )
    minimum_count = int(round(solver.ObjectiveValue()))

    secondary, secondary_select, secondary_cover = build_coverage_model(
        observation_count=len(observations),
        coverage_classes=coverage_classes,
    )
    secondary.Add(sum(secondary_cover) >= int(target_count))
    secondary.Add(sum(secondary_select) == minimum_count)
    non_pole_terms = [
        secondary_select[index]
        for index, row in enumerate(coverage_classes)
        if not bool(row["has_power_pole_member"])
    ]
    secondary.Minimize(sum(non_pole_terms))
    secondary_solver = cp_model.CpSolver()
    secondary_solver.parameters.max_time_in_seconds = SOLVE_CAP_SECONDS
    secondary_solver.parameters.num_search_workers = 8
    secondary_solver.parameters.random_seed = 261900 + int(target_count)
    secondary_status = secondary_solver.Solve(secondary)
    if secondary_status != cp_model.OPTIMAL:
        raise RuntimeError(
            f"min cover target={target_count} secondary optimization not OPTIMAL: "
            f"{secondary_solver.StatusName(secondary_status)}"
        )
    selected_indices = [
        index
        for index, variable in enumerate(secondary_select)
        if secondary_solver.Value(variable) == 1
    ]
    chosen, class_details, non_power_pole_count = selected_class_projection(
        selected_indices=selected_indices,
        coverage_classes=coverage_classes,
    )
    covered_count = sum(
        int(secondary_solver.Value(variable)) for variable in secondary_cover
    )
    return {
        "target_count": int(target_count),
        "status": "OPTIMAL",
        "minimum_literal_count": minimum_count,
        "selected_literals": chosen,
        "selected_coverage_classes": class_details,
        "minimum_non_power_pole_class_count": non_power_pole_count,
        "covered_count": covered_count,
    }


def literal_bbox(literal: Mapping[str, Any]) -> tuple[int, int, int, int]:
    cells = [(int(cell[0]), int(cell[1])) for cell in literal["occupied_cells"]]
    return (
        min(x for x, _y in cells),
        min(y for _x, y in cells),
        max(x for x, _y in cells),
        max(y for _x, y in cells),
    )


def best_window_coverage(
    *,
    observations: Sequence[Mapping[str, Any]],
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
    size: int,
) -> dict[str, Any]:
    bboxes = {key: literal_bbox(payload) for key, payload in literals.items()}
    best: dict[str, Any] | None = None
    for x0 in range(GRID_W - size + 1):
        x1 = x0 + size - 1
        for y0 in range(GRID_H - size + 1):
            y1 = y0 + size - 1
            contained = [
                key
                for key, (min_x, min_y, max_x, max_y) in bboxes.items()
                if x0 <= min_x and max_x <= x1 and y0 <= min_y and max_y <= y1
            ]
            covered: set[int] = set()
            for key in contained:
                covered.update(observation_ids_by_literal.get(key, set()))
            candidate = {
                "size": int(size),
                "anchor": {"x": x0, "y": y0},
                "contained_literal_count": len(contained),
                "covered_count": len(covered),
                "coverage_fraction": len(covered) / len(observations),
                "contained_literals": sorted(contained),
                "covered_observation_ids_digest": stable_digest(sorted(covered)),
            }
            if best is None or (
                candidate["covered_count"],
                -candidate["contained_literal_count"],
                -y0,
                -x0,
            ) > (
                best["covered_count"],
                -best["contained_literal_count"],
                -int(best["anchor"]["y"]),
                -int(best["anchor"]["x"]),
            ):
                best = candidate
    if best is None:
        raise RuntimeError(f"no windows enumerated for size {size}")
    return best


def selected_literal_details(
    keys: Iterable[str],
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
) -> list[dict[str, Any]]:
    return [
        {
            **json_safe(literals[key]),
            "observation_count": len(observation_ids_by_literal.get(key, set())),
        }
        for key in keys
    ]


def run() -> dict[str, Any]:
    identity = verify_identity()
    started = time.monotonic()
    observations, literals, observation_ids_by_literal = build_observations()
    unowned = [
        observation["observation_id"]
        for observation in observations
        if not observation["literal_keys"]
    ]

    max_coverage = [
        exact_max_coverage(
            observations=observations,
            literals=literals,
            observation_ids_by_literal=observation_ids_by_literal,
            budget=budget,
        )
        for budget in LITERAL_BUDGETS
    ]
    max_by_budget = {int(row["budget"]): row for row in max_coverage}

    min_targets: list[dict[str, Any]] = []
    for fraction in TARGET_FRACTIONS:
        target_count = math.ceil(fraction * len(observations))
        result = exact_min_literals_for_target(
            observations=observations,
            literals=literals,
            observation_ids_by_literal=observation_ids_by_literal,
            target_count=target_count,
        )
        result["target_fraction"] = fraction
        min_targets.append(result)

    windows = [
        best_window_coverage(
            observations=observations,
            literals=literals,
            observation_ids_by_literal=observation_ids_by_literal,
            size=size,
        )
        for size in WINDOW_SIZES
    ]

    occurrence_counts = Counter(
        key
        for observation in observations
        for key in observation["literal_keys"]
    )
    facility_occurrences: Counter[str] = Counter()
    operation_occurrences: Counter[str] = Counter()
    kind_occurrences: Counter[str] = Counter()
    pole_observations = 0
    for observation in observations:
        has_pole = False
        for key in observation["literal_keys"]:
            literal = literals[key]
            facility_occurrences[str(literal["facility_type"])] += 1
            operation_occurrences[str(literal["operation_type"])] += 1
            kind_occurrences[str(literal["kind"])] += 1
            if str(literal["facility_type"]) == "power_pole":
                has_pole = True
        pole_observations += int(has_pole)

    k16 = max_by_budget[16]["coverage_fraction"]
    window24 = next(row for row in windows if int(row["size"]) == 24)
    if k16 >= 0.75 and window24["coverage_fraction"] >= 0.50:
        verdict = "SINGLE_LOCAL_JOINT_NEIGHBORHOOD_PLAUSIBLE"
    elif k16 >= 0.75:
        verdict = "DISPERSED_GROUP_POSE_NEIGHBORHOOD_PLAUSIBLE"
    else:
        verdict = "RESIDUAL_CAUSAL_SURFACE_DISTRIBUTED"

    for row in max_coverage:
        row["selected_literal_details"] = selected_literal_details(
            row["selected_literals"],
            literals,
            observation_ids_by_literal,
        )
    for row in min_targets:
        row["selected_literal_details"] = selected_literal_details(
            row["selected_literals"],
            literals,
            observation_ids_by_literal,
        )

    return {
        "schema": "zmd_zero_condition_e013_residual_boundary_coverage_v2",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "observation_count": len(observations),
        "literal_count": len(literals),
        "coverage_class_count": len(
            build_coverage_classes(
                literals=literals,
                observation_ids_by_literal=observation_ids_by_literal,
            )
        ),
        "unowned_observation_count": len(unowned),
        "unowned_observation_ids": unowned,
        "transport": {
            "named_owner_to_consumer_literal": (
                "mandatory instance -> operation-group pose; optional instance -> "
                "template pose"
            ),
            "literal_manifest_digest": stable_digest(literals),
            "observation_manifest_digest": stable_digest(observations),
        },
        "max_coverage_by_literal_budget": max_coverage,
        "minimum_literals_by_target": min_targets,
        "best_single_windows": windows,
        "participation": {
            "observations_touching_power_pole": pole_observations,
            "power_pole_observation_fraction": pole_observations / len(observations),
            "top_literals": [
                {
                    **json_safe(literals[key]),
                    "observation_count": count,
                }
                for key, count in occurrence_counts.most_common(40)
            ],
            "facility_occurrences": dict(facility_occurrences.most_common()),
            "operation_occurrences": dict(operation_occurrences.most_common()),
            "literal_kind_occurrences": dict(kind_occurrences.most_common()),
        },
        "decision_reading": {
            "k16_coverage": k16,
            "best_24x24_window_coverage": window24["coverage_fraction"],
            "selected_next_representation": (
                "single spatial local joint model"
                if verdict == "SINGLE_LOCAL_JOINT_NEIGHBORHOOD_PLAUSIBLE"
                else "dispersed group-pose neighborhood / multi-region joint model"
                if verdict == "DISPERSED_GROUP_POSE_NEIGHBORHOOD_PLAUSIBLE"
                else "global backbone or multi-region representation"
            ),
        },
        "truth_boundary": (
            "Exact touch coverage of currently observed E009 mismatch boundaries. "
            "Coverage is an optimistic neighborhood selector, not a repair proof."
        ),
        "routing_solver_run": False,
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E013 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "observation_count": result["observation_count"],
                    "literal_count": result["literal_count"],
                    "max_coverage": [
                        {
                            key: row[key]
                            for key in (
                                "budget",
                                "covered_count",
                                "coverage_fraction",
                            )
                        }
                        for row in result["max_coverage_by_literal_budget"]
                    ],
                    "windows": [
                        {
                            key: row[key]
                            for key in ("size", "covered_count", "coverage_fraction")
                        }
                        for row in result["best_single_windows"]
                    ],
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e013_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
