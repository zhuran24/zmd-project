#!/usr/bin/env python3
"""Independent no-solver replay of E089's temporal-holdout decision."""

from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
RUN1 = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E089_module_b_spatial_hazard_holdout/run-001"
)
RUN2 = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E089_module_b_spatial_hazard_holdout/run-002"
)
FAILURE = RUN1 / "FAILURE.json"
RESULT = RUN2 / "RESULT.json"
ATLAS = RUN2 / "SPATIAL_ATLAS.json"
SELECTED = RUN2 / "SELECTED_HAZARD_REGIONS.json"
OUTPUT = RUN2 / "ARTIFACT_CHECK.json"

EXPECTED = {
    RESULT: "0a4b17f12a74edd644d53d31c6a445faba04b12544888b5ffcff10bfa077d7ef",
    ATLAS: "9d555d2c87cf7ea119db48015c9707c0148ba2e6ec1524343002d4e17e9f769f",
    SELECTED: "b281e62f305913feabe9573ced7ae168a02e97b51410f6caca541b50a4697a64",
}
EXPECTED_UNIVERSE = 4353
EXPECTED_TRAIN = 95
EXPECTED_HOLDOUT = 83
EXPECTED_FINAL = 178
MAX_REGIONS = 4
UNIVERSE_CAP = 2176
TRAIN_TARGET = 76
HOLDOUT_TARGET = 67
DISTANCE_BINS = {
    "0": (0, 0),
    "1_2": (1, 2),
    "3_5": (3, 5),
    "6_9": (6, 9),
    "10_plus": (10, None),
}
OPTION_BINS = {
    "0": (0, 0),
    "1": (1, 1),
    "2": (2, 2),
    "3_4": (3, 4),
    "5_8": (5, 8),
    "9_plus": (9, None),
}


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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def in_bin(value: int, label: str, bins: Mapping[str, tuple[int, int | None]]) -> bool:
    low, high = bins[label]
    return value >= low and (high is None or value <= high)


def quartile_match(value: int, label: str, thresholds: Sequence[int]) -> bool:
    first, second, third = (int(item) for item in thresholds)
    if label == "q1":
        return value <= first
    if label == "q2":
        return first < value <= second
    if label == "q3":
        return second < value <= third
    if label == "q4":
        return value > third
    raise RuntimeError(f"unknown quartile label: {label}")


def role_members(
    candidates: Sequence[Mapping[str, Any]],
    role: Mapping[str, Any],
    pressure_thresholds: Mapping[str, Sequence[int]],
) -> set[int]:
    definition = role["definition"]
    feature = str(definition["feature"])
    label = str(definition["bin"])
    kind = str(definition["kind"])
    members: set[int] = set()
    for position, row in enumerate(candidates):
        value = int(row[feature])
        if kind == "fixed_distance_band":
            matched = in_bin(value, label, DISTANCE_BINS)
        elif kind == "fixed_option_band":
            matched = in_bin(value, label, OPTION_BINS)
        elif kind == "universe_quartile":
            matched = quartile_match(value, label, pressure_thresholds[feature])
        else:
            raise RuntimeError(f"unknown E089 role kind: {kind}")
        if matched:
            members.add(position)
    return members


def select_regions(
    role_rows: Sequence[Mapping[str, Any]],
    role_sets: Mapping[str, set[int]],
    training: set[int],
) -> dict[str, Any]:
    eligible = [row for row in role_rows if int(row["training_count"]) > 0]
    best: tuple[int, int, int, tuple[str, ...], set[int]] | None = None
    for size in range(1, MAX_REGIONS + 1):
        for combo in itertools.combinations(eligible, size):
            names = tuple(sorted(str(row["role_id"]) for row in combo))
            union: set[int] = set()
            for name in names:
                union |= role_sets[name]
            if len(union) > UNIVERSE_CAP:
                continue
            key = (len(union & training), -len(union), -size, names, union)
            if best is None or key[:3] > best[:3] or (
                key[:3] == best[:3] and key[3] < best[3]
            ):
                best = key
    require(best is not None, "no admissible role combination")
    return {
        "training_count": best[0],
        "universe_count": -best[1],
        "region_count": -best[2],
        "role_ids": list(best[3]),
        "members": best[4],
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E089 artifact: {path}")
        require(sha256_file(path) == expected, f"E089 artifact drift: {path}")

    failure = load_json(FAILURE)
    result = load_json(RESULT)
    atlas = load_json(ATLAS)
    selected_artifact = load_json(SELECTED)
    candidates = list(atlas["candidates"])
    roles = list(atlas["roles"])
    pressure_thresholds = atlas["pressure_quartile_thresholds"]

    require(
        failure.get("status") == "EXECUTION_FAILURE"
        and str(failure.get("detail", "")) == "value outside fixed bins: 0",
        "E089 run-001 apparatus failure drift",
    )
    require(len(candidates) == EXPECTED_UNIVERSE, "E089 candidate count drift")
    training = {
        position for position, row in enumerate(candidates) if bool(row["training_label"])
    }
    holdout = {
        position for position, row in enumerate(candidates) if bool(row["holdout_label"])
    }
    final = {
        position for position, row in enumerate(candidates) if bool(row["final_registered"])
    }
    require(len(training) == EXPECTED_TRAIN, "training count drift")
    require(len(holdout) == EXPECTED_HOLDOUT, "holdout count drift")
    require(len(final) == EXPECTED_FINAL, "final count drift")
    require(training.isdisjoint(holdout), "train/holdout overlap")
    require(training | holdout == final, "final labels do not equal split union")

    role_sets: dict[str, set[int]] = {}
    for role in roles:
        role_id = str(role["role_id"])
        members = role_members(candidates, role, pressure_thresholds)
        role_sets[role_id] = members
        require(len(members) == int(role["universe_count"]), f"{role_id} universe drift")
        require(
            len(members & training) == int(role["training_count"]),
            f"{role_id} training drift",
        )
        require(
            len(members & holdout) == int(role["holdout_count"]),
            f"{role_id} holdout drift",
        )

    selected = select_regions(roles, role_sets, training)
    members = selected.pop("members")
    selected["holdout_count"] = len(members & holdout)
    selected["final_registered_count"] = len(members & final)
    selected["training_fraction"] = selected["training_count"] / EXPECTED_TRAIN
    selected["holdout_fraction"] = selected["holdout_count"] / EXPECTED_HOLDOUT
    selected["final_registered_fraction"] = (
        selected["final_registered_count"] / EXPECTED_FINAL
    )
    selected["universe_fraction"] = selected["universe_count"] / EXPECTED_UNIVERSE
    selected["training_target_count"] = TRAIN_TARGET
    selected["holdout_target_count"] = HOLDOUT_TARGET

    require(selected == result["selected"], "E089 selected region replay drift")
    require(selected == selected_artifact["selected"], "selected artifact drift")
    selected_flags = {
        position for position, row in enumerate(candidates) if bool(row["selected_region_union"])
    }
    require(selected_flags == members, "candidate selected-union flags drift")

    training_pass = selected["training_count"] >= TRAIN_TARGET
    holdout_pass = selected["holdout_count"] >= HOLDOUT_TARGET
    if training_pass and holdout_pass:
        expected_verdict = "STABLE_SPATIAL_HAZARD_REGIONS"
    elif training_pass:
        expected_verdict = "TRAINING_HAZARD_DOES_NOT_GENERALIZE"
    else:
        expected_verdict = "SPATIAL_ROLES_TOO_DIFFUSE"
    require(result["verdict"] == expected_verdict, "E089 verdict drift")
    require(
        result["decision"]
        == "RETIRE_FIXED_52_PLUS_ONE_B_GEOMETRY_WIDEN_POLES_OR_PARTITION",
        "E089 decision drift",
    )

    output = {
        "schema": "zmd_e089_module_b_spatial_hazard_artifact_check_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "artifact_sha256": {
            str(path.relative_to(ROOT)): expected for path, expected in EXPECTED.items()
        },
        "run_001_zero_option_apparatus_failure_preserved": True,
        "candidate_count": len(candidates),
        "training_count": len(training),
        "holdout_count": len(holdout),
        "role_count": len(roles),
        "selected": selected,
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Independent no-solver replay of the fixed role language, exact "
            "train-only selection and temporal holdout evaluation. It proves no "
            "candidate feasible or infeasible and authorizes no cut."
        ),
    }
    dump_exclusive(OUTPUT, output)
    print(
        json.dumps(
            {
                "status": output["status"],
                "verdict": output["verdict"],
                "decision": output["decision"],
                "selected": output["selected"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256_file(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
