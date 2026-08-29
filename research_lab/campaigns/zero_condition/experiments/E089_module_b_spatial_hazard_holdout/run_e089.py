#!/usr/bin/env python3
"""E089: temporal-holdout spatial hazard atlas for module B."""

from __future__ import annotations

from collections import defaultdict
import datetime as dt
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import traceback
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E089_module_b_spatial_hazard_holdout/run-002"
)
RESULT_PATH = OUT / "RESULT.json"
ATLAS_PATH = OUT / "SPATIAL_ATLAS.json"
SELECTED_PATH = OUT / "SELECTED_HAZARD_REGIONS.json"
FAILURE_PATH = OUT / "FAILURE.json"

E086_CHECKPOINT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E086_feasibility_first_front_proposer/run-001/CHECKPOINT.json"
)
E087_CHECKPOINT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E087_feasibility_first_front_continuation/run-001/CHECKPOINT.json"
)
E088_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E088_module_b_front_rule_signature_atlas/run-002/RESULT.json"
)
E088_CANDIDATES = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E088_module_b_front_rule_signature_atlas/run-002/CANDIDATE_SIGNATURES.json"
)
E088_ATLAS = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E088_module_b_front_rule_signature_atlas/run-002/SIGNATURE_ATLAS.json"
)
E088_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E088_module_b_front_rule_signature_atlas/RESULT.txt"
)
E081_FRONTIER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E081_axis_seam_recolor_frontier/run-001/AXIS_SEAM_FRONTIER.json"
)
E069_PARENT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json"
)
CANDIDATE_POOL = HISTORY / "data/preprocessed/candidate_placements.json"

EXPECTED_HASHES = {
    E086_CHECKPOINT: "06cadbed6f61cb04c8c5445b778378bca336ddc2fa1f2f0804962c1ceb70933d",
    E087_CHECKPOINT: "09c0c31d5874fe9689ecea7295be48edb3a765f0a605a475e44e5ef1a107d4e9",
    E088_RESULT: "ba1ecfa3772f7b0a7837818f4945a303e12ab15b61853aaf5fb773cc142bd2c8",
    E088_CANDIDATES: "3037fe5f2539fc4b155cde387481d60681cd34a0302656e58a73870bfff64798",
    E088_ATLAS: "06cebb6ef75aa3584f9779b768698b2bf89041b7f0f18c1a81c198f734df15c6",
    E088_DURABLE: "e1259d86d81def32e686ecee66e527d15d1bbb1454f3c7bee62a45a89af2a29d",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    CANDIDATE_POOL: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
}

EXPECTED_UNIVERSE = 4353
EXPECTED_TRAIN_B = 95
EXPECTED_HOLDOUT_B = 83
EXPECTED_FINAL_B = 178
MAX_REGIONS = 4
UNIVERSE_CAP_FRACTION = 0.50
SUCCESS_FRACTION = 0.80
DISTANCE_BINS = (
    ("0", 0, 0),
    ("1_2", 1, 2),
    ("3_5", 3, 5),
    ("6_9", 6, 9),
    ("10_plus", 10, None),
)
OPTION_BINS = (
    ("0", 0, 0),
    ("1", 1, 1),
    ("2", 2, 2),
    ("3_4", 3, 4),
    ("5_8", 5, 8),
    ("9_plus", 9, None),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, payload: Any) -> None:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def cell(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def rect_cells(row: Mapping[str, Any]) -> set[tuple[int, int]]:
    min_x, min_y = (int(value) for value in row["body_min"])
    max_x, max_y = (int(value) for value in row["body_max"])
    return {
        (x, y)
        for x in range(min_x, max_x + 1)
        for y in range(min_y, max_y + 1)
    }


def manhattan_gap(
    body: Iterable[tuple[int, int]],
    obstacle: Iterable[tuple[int, int]],
) -> int:
    obstacle_values = tuple(obstacle)
    require(bool(obstacle_values), "empty spatial obstacle")
    return min(
        abs(x - ox) + abs(y - oy)
        for x, y in body
        for ox, oy in obstacle_values
    )


def fixed_bin(value: int, bins: Sequence[tuple[str, int, int | None]]) -> str:
    for label, low, high in bins:
        if value >= low and (high is None or value <= high):
            return label
    raise RuntimeError(f"value outside fixed bins: {value}")


def quartile_thresholds(values: Sequence[int]) -> tuple[int, int, int]:
    ordered = sorted(int(value) for value in values)
    require(bool(ordered), "empty quartile values")
    last = len(ordered) - 1
    return (
        ordered[last // 4],
        ordered[last // 2],
        ordered[(3 * last) // 4],
    )


def quartile_label(value: int, thresholds: Sequence[int]) -> str:
    first, second, third = (int(item) for item in thresholds)
    if value <= first:
        return "q1"
    if value <= second:
        return "q2"
    if value <= third:
        return "q3"
    return "q4"


def checkpoint_b_indices(payload: Mapping[str, Any]) -> set[int]:
    return {
        int(raw_index)
        for raw_index, row in payload["front_rule_stats"].items()
        if str(row["module"]) == "B"
    }


def demand_label(row: Mapping[str, Any]) -> str:
    values = sorted(
        (
            str(item["template"]),
            int(item["input_need"]),
            int(item["output_need"]),
        )
        for item in row["demand_classes"]
    )
    return "+".join(f"{template}:{need_in}i{need_out}o" for template, need_in, need_out in values)


def support_pressure(payload: Mapping[str, Any]) -> tuple[int, int, int]:
    manufacturing = 0
    pole = 0
    boundary = 0
    for mode in payload["modes"]:
        for side in ("input_cells", "output_cells"):
            for row in mode[side]:
                manufacturing = max(manufacturing, int(row["manufacturing_coverers"]))
                pole = max(pole, int(row["pole_coverers"]))
                boundary = max(boundary, int(row["boundary_state_coverers"]))
    return manufacturing, pole, boundary


def role_mask(indices: Sequence[int]) -> int:
    mask = 0
    for index in indices:
        mask |= 1 << int(index)
    return mask


def verify_identity() -> dict[str, Any]:
    require(git_output("branch", "--show-current") == "research/main", "branch drift")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    require(not tracked, f"tracked worktree is dirty: {tracked}")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        require(path.is_file(), f"missing E089 input: {path}")
        observed = sha256_file(path)
        require(observed == expected, f"E089 input identity drift: {path}")
        try:
            display = str(path.relative_to(ROOT))
        except ValueError:
            display = str(path)
        checked[display] = {"sha256": observed, "size_bytes": path.stat().st_size}
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def fixed_geometry() -> dict[str, Any]:
    frontier = load_json(E081_FRONTIER)
    detailed = {
        row["partition"]["partition_id"]: row
        for row in frontier["detailed_candidates"]
    }
    winner = detailed[frontier["geometry_winner_partition_id"]]
    evaluation = winner["best_reference_preserving"]
    corridor = evaluation["corridor"]
    require(
        corridor["axis"] == "y"
        and int(corridor["start"]) == 41
        and int(corridor["end"]) == 41,
        "E089 corridor drift",
    )
    removed_ids = set(map(str, evaluation["pole_move_ids"]))
    require(len(removed_ids) == 1, "E089 removed-pole identity drift")

    parent = load_json(E069_PARENT)["solution"]
    pools = load_json(CANDIDATE_POOL)["facility_pools"]
    fixed_poles: set[tuple[int, int]] = set()
    removed_pole: set[tuple[int, int]] = set()
    core_reserved: set[tuple[int, int]] = set()
    for instance_id, row in parent.items():
        template = str(row["facility_type"])
        pose = pools[template][int(row["pose_idx"])]
        body = {cell(value) for value in pose["occupied_cells"]}
        if template == "power_pole":
            if str(instance_id) in removed_ids:
                removed_pole |= body
            else:
                fixed_poles |= body
        elif template == "protocol_core":
            core_reserved |= body
            core_reserved |= {cell(value) for value in pose["input_port_cells"]}
            core_reserved |= {cell(value) for value in pose["output_port_cells"]}
    require(len(fixed_poles) == 52 * 4, "E089 fixed-pole body count drift")
    require(len(removed_pole) == 4, "E089 removed-pole body count drift")
    require(bool(core_reserved), "E089 core reserved set missing")
    return {
        "fixed_poles": fixed_poles,
        "removed_pole": removed_pole,
        "core_reserved": core_reserved,
        "removed_pole_ids": sorted(removed_ids),
    }


def select_regions(
    roles: Sequence[Mapping[str, Any]],
    *,
    train_mask: int,
    universe_cap: int,
) -> dict[str, Any]:
    eligible = [row for row in roles if int(row["training_count"]) > 0]
    best: tuple[int, int, int, tuple[str, ...], int] | None = None
    for size in range(1, MAX_REGIONS + 1):
        for combo in itertools.combinations(eligible, size):
            union = 0
            names: list[str] = []
            for row in combo:
                union |= int(row["mask"])
                names.append(str(row["role_id"]))
            universe_count = union.bit_count()
            if universe_count > universe_cap:
                continue
            train_count = (union & train_mask).bit_count()
            key = (
                train_count,
                -universe_count,
                -size,
                tuple(sorted(names)),
                union,
            )
            if best is None or key[:3] > best[:3] or (
                key[:3] == best[:3] and key[3] < best[3]
            ):
                best = key
    require(best is not None, "E089 no region combination satisfies universe cap")
    return {
        "training_count": best[0],
        "universe_count": -best[1],
        "region_count": -best[2],
        "role_ids": list(best[3]),
        "mask": best[4],
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e088_result = load_json(E088_RESULT)
    require(
        e088_result["verdict"]
        == "REGISTERED_B_FAILURES_ARE_TOO_DIFFUSE_FOR_BOUNDED_BULK_COMPILATION",
        "E089 trigger verdict drift",
    )
    candidate_payload = load_json(E088_CANDIDATES)
    atlas = load_json(E088_ATLAS)
    candidates = [dict(row) for row in candidate_payload["candidates"]]
    require(len(candidates) == EXPECTED_UNIVERSE, "E089 universe count drift")
    by_index = {int(row["candidate_index"]): row for row in candidates}
    require(len(by_index) == len(candidates), "E089 duplicate candidate indices")

    train = checkpoint_b_indices(load_json(E086_CHECKPOINT))
    final = checkpoint_b_indices(load_json(E087_CHECKPOINT))
    holdout = final - train
    require(train <= final, "E089 training labels are not a subset of final labels")
    require(len(train) == EXPECTED_TRAIN_B, "E089 training B count drift")
    require(len(holdout) == EXPECTED_HOLDOUT_B, "E089 holdout B count drift")
    require(len(final) == EXPECTED_FINAL_B, "E089 final B count drift")
    require(train.isdisjoint(holdout), "E089 train/holdout overlap")
    require(all(index in by_index for index in final), "E089 label index missing")
    require(all(bool(by_index[index]["registered"]) for index in final), "E089 registered flag drift")

    spatial = fixed_geometry()
    payloads = atlas["signature_payloads"]
    pressure_by_signature: dict[str, tuple[int, int, int]] = {}
    for row in candidates:
        signature = str(row["support_signature"])
        if signature not in pressure_by_signature:
            pressure_by_signature[signature] = support_pressure(
                payloads[f"support:{signature}"]
            )

    candidate_features: list[dict[str, Any]] = []
    manufacturing_values: list[int] = []
    pole_values: list[int] = []
    boundary_values: list[int] = []
    for row in candidates:
        body = rect_cells(row)
        min_x, min_y = (int(value) for value in row["body_min"])
        max_x, max_y = (int(value) for value in row["body_max"])
        pressure = pressure_by_signature[str(row["support_signature"])]
        features = {
            "candidate_index": int(row["candidate_index"]),
            "template": str(row["template"]),
            "demand_stratum": demand_label(row),
            "seam_gap": min_y - 42,
            "outer_gap": min(min_x, 69 - max_x, 69 - max_y),
            "core_gap": manhattan_gap(body, spatial["core_reserved"]),
            "fixed_pole_gap": manhattan_gap(body, spatial["fixed_poles"]),
            "removed_pole_gap": manhattan_gap(body, spatial["removed_pole"]),
            "option_count": int(row["option_count"]),
            "manufacturing_pressure": int(pressure[0]),
            "pole_pressure": int(pressure[1]),
            "boundary_pressure": int(pressure[2]),
            "is_current_footprint": bool(row["is_current_footprint"]),
            "training_label": int(row["candidate_index"]) in train,
            "holdout_label": int(row["candidate_index"]) in holdout,
            "final_registered": int(row["candidate_index"]) in final,
        }
        require(features["seam_gap"] >= 0, "candidate crosses y=41 seam")
        require(features["outer_gap"] >= 0, "candidate leaves grid")
        candidate_features.append(features)
        manufacturing_values.append(features["manufacturing_pressure"])
        pole_values.append(features["pole_pressure"])
        boundary_values.append(features["boundary_pressure"])

    pressure_thresholds = {
        "manufacturing_pressure": quartile_thresholds(manufacturing_values),
        "pole_pressure": quartile_thresholds(pole_values),
        "boundary_pressure": quartile_thresholds(boundary_values),
    }

    membership: dict[str, list[int]] = defaultdict(list)
    role_definition: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(candidate_features):
        for feature in (
            "seam_gap",
            "outer_gap",
            "core_gap",
            "fixed_pole_gap",
            "removed_pole_gap",
        ):
            label = fixed_bin(int(row[feature]), DISTANCE_BINS)
            role_id = f"{feature}:{label}"
            membership[role_id].append(position)
            role_definition[role_id] = {
                "feature": feature,
                "bin": label,
                "kind": "fixed_distance_band",
            }
        option_label = fixed_bin(int(row["option_count"]), OPTION_BINS)
        option_role = f"option_count:{option_label}"
        membership[option_role].append(position)
        role_definition[option_role] = {
            "feature": "option_count",
            "bin": option_label,
            "kind": "fixed_option_band",
        }
        for feature, thresholds in pressure_thresholds.items():
            label = quartile_label(int(row[feature]), thresholds)
            role_id = f"{feature}:{label}"
            membership[role_id].append(position)
            role_definition[role_id] = {
                "feature": feature,
                "bin": label,
                "kind": "universe_quartile",
                "thresholds": list(thresholds),
            }

    train_positions = {
        position
        for position, row in enumerate(candidate_features)
        if bool(row["training_label"])
    }
    holdout_positions = {
        position
        for position, row in enumerate(candidate_features)
        if bool(row["holdout_label"])
    }
    final_positions = train_positions | holdout_positions
    train_mask = role_mask(sorted(train_positions))
    holdout_mask = role_mask(sorted(holdout_positions))
    final_mask = role_mask(sorted(final_positions))

    roles: list[dict[str, Any]] = []
    for role_id in sorted(membership):
        mask = role_mask(membership[role_id])
        universe_count = mask.bit_count()
        train_count = (mask & train_mask).bit_count()
        holdout_count = (mask & holdout_mask).bit_count()
        final_count = (mask & final_mask).bit_count()
        roles.append(
            {
                "role_id": role_id,
                "definition": role_definition[role_id],
                "mask": mask,
                "universe_count": universe_count,
                "universe_fraction": universe_count / EXPECTED_UNIVERSE,
                "training_count": train_count,
                "training_fraction": train_count / EXPECTED_TRAIN_B,
                "training_rate_within_role": train_count / universe_count,
                "holdout_count": holdout_count,
                "holdout_fraction": holdout_count / EXPECTED_HOLDOUT_B,
                "holdout_rate_within_role": holdout_count / universe_count,
                "final_registered_count": final_count,
            }
        )

    universe_cap = int(math.floor(EXPECTED_UNIVERSE * UNIVERSE_CAP_FRACTION))
    selected = select_regions(roles, train_mask=train_mask, universe_cap=universe_cap)
    selected_mask = int(selected.pop("mask"))
    selected["holdout_count"] = (selected_mask & holdout_mask).bit_count()
    selected["final_registered_count"] = (selected_mask & final_mask).bit_count()
    selected["training_fraction"] = selected["training_count"] / EXPECTED_TRAIN_B
    selected["holdout_fraction"] = selected["holdout_count"] / EXPECTED_HOLDOUT_B
    selected["final_registered_fraction"] = (
        selected["final_registered_count"] / EXPECTED_FINAL_B
    )
    selected["universe_fraction"] = selected["universe_count"] / EXPECTED_UNIVERSE
    selected["training_target_count"] = int(math.ceil(EXPECTED_TRAIN_B * SUCCESS_FRACTION))
    selected["holdout_target_count"] = int(math.ceil(EXPECTED_HOLDOUT_B * SUCCESS_FRACTION))

    training_pass = selected["training_count"] >= selected["training_target_count"]
    holdout_pass = selected["holdout_count"] >= selected["holdout_target_count"]
    if training_pass and holdout_pass:
        verdict = "STABLE_SPATIAL_HAZARD_REGIONS"
        decision = "BUILD_BOUNDED_B_BAY_OR_FRONT_HALO_FROM_SELECTED_ROLES"
    elif training_pass:
        verdict = "TRAINING_HAZARD_DOES_NOT_GENERALIZE"
        decision = "DO_NOT_PROMOTE_FITTED_REGIONS_WIDEN_GEOMETRY_LANGUAGE"
    else:
        verdict = "SPATIAL_ROLES_TOO_DIFFUSE"
        decision = "RETIRE_FIXED_52_PLUS_ONE_B_GEOMETRY_WIDEN_POLES_OR_PARTITION"

    strata: dict[str, Any] = {}
    for key_fn, label in (
        (lambda row: str(row["template"]), "template"),
        (lambda row: str(row["demand_stratum"]), "demand"),
    ):
        grouped: dict[str, list[int]] = defaultdict(list)
        for position, row in enumerate(candidate_features):
            grouped[key_fn(row)].append(position)
        strata[label] = {
            key: {
                "universe_count": len(positions),
                "training_count": sum(position in train_positions for position in positions),
                "holdout_count": sum(position in holdout_positions for position in positions),
                "selected_universe_count": sum(
                    bool(selected_mask & (1 << position)) for position in positions
                ),
                "selected_training_count": sum(
                    position in train_positions and bool(selected_mask & (1 << position))
                    for position in positions
                ),
                "selected_holdout_count": sum(
                    position in holdout_positions and bool(selected_mask & (1 << position))
                    for position in positions
                ),
            }
            for key, positions in sorted(grouped.items())
        }

    role_output = [
        {key: value for key, value in row.items() if key != "mask"}
        for row in sorted(
            roles,
            key=lambda row: (
                -int(row["training_count"]),
                int(row["universe_count"]),
                str(row["role_id"]),
            ),
        )
    ]
    candidate_output = [
        {
            **row,
            "selected_region_union": bool(selected_mask & (1 << position)),
        }
        for position, row in enumerate(candidate_features)
    ]
    atlas_output = {
        "schema": "zmd_e089_module_b_spatial_hazard_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "candidate_count": EXPECTED_UNIVERSE,
        "training_count": EXPECTED_TRAIN_B,
        "holdout_count": EXPECTED_HOLDOUT_B,
        "pressure_quartile_thresholds": {
            key: list(value) for key, value in pressure_thresholds.items()
        },
        "roles": role_output,
        "selected": selected,
        "strata": strata,
        "candidates": candidate_output,
        "truth_boundary": (
            "No-solver spatial-role atlas with a temporal holdout. Region selection "
            "uses training labels only; holdout labels are revealed afterward."
        ),
    }
    selected_output = {
        "schema": "zmd_e089_selected_hazard_regions_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "selection_rule": {
            "max_regions": MAX_REGIONS,
            "universe_cap_fraction": UNIVERSE_CAP_FRACTION,
            "success_fraction": SUCCESS_FRACTION,
            "objective": [
                "maximize_training_coverage",
                "minimize_universe_coverage",
                "minimize_region_count",
                "deterministic_role_identity",
            ],
        },
        "selected": selected,
        "selected_role_details": [
            next(row for row in role_output if row["role_id"] == role_id)
            for role_id in selected["role_ids"]
        ],
        "strata": strata,
        "truth_boundary": (
            "Selected roles are constructor proposers only. They are not cuts or "
            "candidate feasibility labels."
        ),
    }
    dump_exclusive(ATLAS_PATH, atlas_output)
    dump_exclusive(SELECTED_PATH, selected_output)

    result = {
        "schema": "zmd_e089_module_b_spatial_hazard_holdout_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "split": {
            "training_checkpoint": str(E086_CHECKPOINT.relative_to(ROOT)),
            "training_b_count": len(train),
            "holdout_checkpoint": str(E087_CHECKPOINT.relative_to(ROOT)),
            "holdout_b_count": len(holdout),
            "final_b_count": len(final),
            "train_holdout_disjoint": train.isdisjoint(holdout),
        },
        "candidate_count": EXPECTED_UNIVERSE,
        "role_count": len(roles),
        "pressure_quartile_thresholds": {
            key: list(value) for key, value in pressure_thresholds.items()
        },
        "selected": selected,
        "selected_role_details": selected_output["selected_role_details"],
        "strata": strata,
        "atlas_path": str(ATLAS_PATH.relative_to(ROOT)),
        "atlas_sha256": sha256_file(ATLAS_PATH),
        "selected_path": str(SELECTED_PATH.relative_to(ROOT)),
        "selected_sha256": sha256_file(SELECTED_PATH),
        "truth_boundary": (
            "Temporal-holdout no-solver predictive atlas on the frozen E088 module-B "
            "candidate language. It provides no feasibility, cut, binding or routing "
            "claim."
        ),
    }
    return result


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite E089 run directory: {OUT}")
    OUT.mkdir(parents=True, exist_ok=False)
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "role_count": result["role_count"],
                    "selected": result["selected"],
                    "result_path": str(RESULT_PATH.relative_to(ROOT)),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_e089_module_b_spatial_hazard_holdout_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
