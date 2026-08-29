#!/usr/bin/env python3
"""Independent replay closing E109's final two template splits."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time
import types
from typing import Any

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e109.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E109_last_two_template_split_discriminator/run-001"
)
RESULT = RUN / "RESULT.json"
UPPER_304 = RUN / "upper_3_0_4_UPPER_RESULT.json"
UPPER_603 = RUN / "upper_6_0_3_UPPER_RESULT.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition/run_e095.py"
)
E100_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E100_source_stable_reserved_x42_hybrid/run_e100.py"
)
E104_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E104_high_reserved_y60_constructor/run_e104.py"
)
E105_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E105_nested_allocation_handshake/run_e105.py"
)
E108_BODY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E108_nested_template_projection_atlas/run-001/BODY_TEMPLATE_PROJECTION.json"
)
E108_CHECK = E108_BODY.with_name("ARTIFACT_CHECK.json")

EXPECTED = {
    RUNNER: "a8e6ec35332db5ea7fa789f9f04a4081a8ed98d000d41620e0ea039c4d174889",
    RESULT: "32a76ec37e5a51158fc19aabfd02da606e0337d8903a677f6a064ac25bb69875",
    UPPER_304: "a22666a508e5c7d3a42f5c807a70d136f9e9b7e51ce6dcc6952744a25ab119b0",
    UPPER_603: "3b6bd33b8b6dba936a194d29feac5366f0b3bd78bf75528fe315b954382a7c10",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    E105_RUNNER: "7dbdf3be073dd77b6ef091b4302442aa5766882d2f384b285576b84c368588b9",
    E108_BODY: "24fdc3943a341321a44ddf99197dc4daea82d71ff4bfd16d1f5469269ebdae80",
    E108_CHECK: "17095258691adafc54c29bf48dbc901a65cfa2d694293c044782262c306bb9c1",
}
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
TARGETS = (
    {
        "target_id": "upper_3_0_4",
        "upper": (3, 0, 4),
        "lower": (7, 6, 6),
        "producer_path": UPPER_304,
    },
    {
        "target_id": "upper_6_0_3",
        "upper": (6, 0, 3),
        "lower": (4, 6, 7),
        "producer_path": UPPER_603,
    },
)
EXPECTED_BODY_VECTORS = {
    (3, 0, 4),
    (3, 1, 3),
    (3, 2, 2),
    (5, 2, 1),
    (6, 0, 3),
    (6, 1, 2),
    (7, 0, 3),
}
PRIOR_NOGOODS = {
    (3, 1, 3),
    (3, 2, 2),
    (5, 2, 1),
    (6, 1, 2),
    (7, 0, 3),
}
NEW_NOGOODS = {(3, 0, 4), (6, 0, 3)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def source_module(path: Path, name: str, package: str | None = None) -> types.ModuleType:
    raw = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = package if package is not None else name.rpartition(".")[0]
    module.__loader__ = None
    sys.modules[name] = module
    exec(
        compile(
            raw,
            f"<source-isolated-check:{path}:{hashlib.sha256(raw).hexdigest()}>",
            "exec",
            dont_inherit=True,
        ),
        module.__dict__,
    )
    return module


def count_map(values: tuple[int, int, int]) -> dict[str, int]:
    return {
        template: int(values[index])
        for index, template in enumerate(TEMPLATES)
    }


def body_hint_for_vector(body_atlas: dict[str, Any], vector: tuple[int, int, int]) -> set[int]:
    matches = [
        row
        for row in body_atlas["vectors"]
        if tuple(map(int, row["vector"])) == vector
    ]
    require(len(matches) == 1, f"body witness remap drift: {vector}")
    indices = set(map(int, matches[0]["witness"]["selected_global_indices"]))
    require(len(indices) == 26, f"body witness size drift: {vector}")
    return indices


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E109 check: {OUTPUT}")
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E109 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E109 artifact identity drift: {path}")
        artifact_records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    body_atlas = load(E108_BODY)
    e108_check = load(E108_CHECK)
    require(result["verdict"] == "RESERVED_Y60_TEMPLATE_PROJECTION_CLOSED", "verdict drift")
    require(result["decision"] == "RESTORE_E103_EXPLICIT_Y59_SEPARATOR", "decision drift")
    require(int(result["closed_split_count"]) == 2, "closed count drift")
    require(result["survivors"] == [] and result["censored"] == [], "unexpected survivor/censor")
    body_vectors = {tuple(map(int, row["vector"])) for row in body_atlas["vectors"]}
    require(body_atlas["complete"] is True, "E108 body atlas not complete")
    require(body_vectors == EXPECTED_BODY_VECTORS, "E108 body vector set drift")
    require(
        {tuple(map(int, value)) for value in e108_check["known_split_nogoods"]}
        == PRIOR_NOGOODS,
        "prior split store drift",
    )
    require(
        {tuple(map(int, value)) for value in e108_check["remaining_body_feasible_vectors"]}
        == NEW_NOGOODS,
        "remaining vector drift",
    )
    require(PRIOR_NOGOODS | NEW_NOGOODS == EXPECTED_BODY_VECTORS, "seven-state cover drift")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e109_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e109_check_e100")
    e104 = source_module(E104_RUNNER, "zmd_e109_check_e104")
    e105 = source_module(E105_RUNNER, "zmd_e109_check_e105")
    prepared = e104.reconstruct(e095=e095, e100=e100)
    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    require(len(global_counts) == 8, "class count drift")

    replays: list[dict[str, Any]] = []
    for index, target in enumerate(TARGETS):
        producer = load(target["producer_path"])
        require(producer["status"] == "INFEASIBLE", "producer negative drift")
        require(int(producer["candidate_count"]) == 198, "upper candidate count drift")
        hints = body_hint_for_vector(body_atlas, target["upper"])
        model = e105.build_nested_model(
            e095=e095,
            prepared=prepared,
            nested_side="upper",
            template_counts=count_map(target["upper"]),
            body_hint_indices=hints,
            allocation_caps=global_counts,
        )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 90.0
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 109900 + index
        solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
        solver.parameters.symmetry_level = 0
        solver.parameters.cp_model_probing_level = 0
        started = time.monotonic()
        status_code = solver.Solve(model["model"])
        elapsed = time.monotonic() - started
        status = solver.StatusName(status_code)
        require(status == "INFEASIBLE", f"solver-diverse replay censored: {target['target_id']} {status}")
        replays.append(
            {
                "target_id": target["target_id"],
                "upper": list(target["upper"]),
                "lower": list(target["lower"]),
                "producer_status": producer["status"],
                "producer_elapsed_seconds": producer["elapsed_seconds"],
                "producer_branches": producer["branches"],
                "producer_conflicts": producer["conflicts"],
                "replay_status": status,
                "replay_elapsed_seconds": elapsed,
                "replay_branches": int(solver.NumBranches()),
                "replay_conflicts": int(solver.NumConflicts()),
                "workers": 1,
                "search_branching": "PSEUDO_COST_SEARCH",
                "symmetry_level": 0,
                "probing_level": 0,
            }
        )

    payload = {
        "schema": "zmd_e109_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "SEVEN_STATE_BODY_ATLAS_FULLY_COVERED_BY_EXACT_SPLIT_NOGOODS",
        "artifact_records": artifact_records,
        "body_projection_complete": True,
        "body_projection_vector_count": 7,
        "prior_exact_split_nogood_count": 5,
        "new_exact_split_nogood_count": 2,
        "new_split_replays": replays,
        "covered_upper_vectors": [list(value) for value in sorted(EXPECTED_BODY_VECTORS)],
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "E108 proves the body/power split basis contains exactly seven vectors. "
            "Five prior exact split negatives plus the two independently replayed "
            "E109 upper-side negatives cover all seven. Therefore no native-front "
            "witness exists in the manufacturing-free-y60 sufficient language."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "new_split_nogood_count": 2,
                "covered_vector_count": 7,
                "decision": payload["decision"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
