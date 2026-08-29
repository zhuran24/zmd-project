#!/usr/bin/env python3
"""Independent replay of E106 split and allocation nogood stores."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import types
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e106.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E106_nested_template_split_frontier/run-001"
)
RESULT = RUN / "RESULT.json"
SPLIT_STORE = RUN / "TEMPLATE_SPLIT_NOGOODS.json"
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
E105_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E105_nested_allocation_handshake/run-003/RESULT.json"
)
E105_CHECK = E105_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED = {
    RUNNER: "485698087b044f99fa5ca6146c16421e7600c8780474691e60939ede944d66ab",
    RESULT: "026fe686944616305ff5056a574152a5c8d57fac44b15a797563b555c33316ae",
    SPLIT_STORE: "48cac90a3e704b82b0e50c22644a604214156d8dcfbbaa90c78a5ae5f74ecb96",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    E105_RUNNER: "7dbdf3be073dd77b6ef091b4302442aa5766882d2f384b285576b84c368588b9",
    E105_RESULT: "95ae95cc649097aae4010cb5ebe96f6027fefdfac2ee469d877cb8940a009ecb",
    E105_CHECK: "38e1d0f1fde3e689f04a17101805cf3e3c874b5f7941324b552945bab473a346",
}
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
TOTALS = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
EXPECTED_SPLITS = [
    (3, 2, 2),
    (3, 1, 3),
    (7, 0, 3),
    (6, 1, 2),
]
OPEN_SPLIT = (5, 2, 1)
EXPECTED_ALLOCATIONS = [
    (3, 1, 1, 2, 0, 1, 0, 0),
    (0, 1, 4, 0, 2, 0, 1, 0),
    (0, 0, 5, 0, 2, 0, 0, 1),
]


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


def one_worker_solver(seconds: float, seed: int) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = int(seed)
    solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    return solver


def replay_body_proposal(
    *,
    prepared: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    rows = prepared["survivors"]
    selected_global = set(map(int, proposal["selected_global_indices"]))
    selected = [
        row for row in rows if int(row["global_row_index"]) in selected_global
    ]
    require(len(selected) == 26, "body proposal selected count drift")
    require(len(selected_global) == 26, "body proposal global identity collision")
    occupied: set[tuple[int, int]] = set()
    unpowered = 0
    observed: Counter[tuple[str, str]] = Counter()
    coverage = set(prepared["context"]["fixed_coverage"])
    for row in selected:
        body = set(row["body"])
        require(not occupied & body, "body proposal overlap")
        occupied |= body
        unpowered += int(not bool(body & coverage))
        observed[(str(row["nested_side"]), str(row["template"]))] += 1
    require(unpowered == 0, "body proposal has unpowered body")
    stable = {
        instance_id
        for instance_id, footprint in prepared["context"]["stable_footprints"].items()
        if any(tuple(row["body"]) == footprint for row in selected)
    }
    require(
        stable == set(prepared["context"]["stable_footprints"]),
        "body proposal loses stable E078 body",
    )
    split = proposal["split"]
    expected: Counter[tuple[str, str]] = Counter()
    for template, count in split["lower_counts"].items():
        expected[("lower", str(template))] = int(count)
    for template, count in split["upper_counts"].items():
        expected[("upper", str(template))] = int(count)
    require(observed == expected, "body proposal split replay drift")
    return {
        "selected_body_count": len(selected),
        "occupied_cell_count": len(occupied),
        "unpowered_count": unpowered,
        "stable_body_count": len(stable),
        "observed_template_counts": {
            f"{side}:{template}": int(count)
            for (side, template), count in sorted(observed.items())
        },
    }


def template_counts_from_split(
    split: Mapping[str, Any], side: str
) -> dict[str, int]:
    return {
        template: int(split[f"{side}_counts"][template])
        for template in TEMPLATES
    }


def replay_direct_split_negative(
    *,
    e095: types.ModuleType,
    e105: types.ModuleType,
    prepared: Mapping[str, Any],
    body_proposal: Mapping[str, Any],
    proposer_record: Mapping[str, Any],
    seed: int,
) -> dict[str, Any]:
    split = body_proposal["split"]
    proposer_side = str(proposer_record["proposer_side"])
    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    model = e105.build_nested_model(
        e095=e095,
        prepared=prepared,
        nested_side=proposer_side,
        template_counts=template_counts_from_split(split, proposer_side),
        body_hint_indices=set(map(int, body_proposal["selected_global_indices"])),
        allocation_caps=global_counts,
    )
    solver = one_worker_solver(45.0, seed)
    started = time.monotonic()
    status_code = solver.Solve(model["model"])
    elapsed = time.monotonic() - started
    status = solver.StatusName(status_code)
    require(status == "INFEASIBLE", f"split replay not INFEASIBLE: {status}")
    return {
        "status": status,
        "elapsed_seconds": elapsed,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "workers": 1,
        "search_branching": "PSEUDO_COST_SEARCH",
        "symmetry_level": 0,
        "probing_level": 0,
    }


def replay_allocation_nogood(
    *,
    e095: types.ModuleType,
    e105: types.ModuleType,
    prepared: Mapping[str, Any],
    body_proposal: Mapping[str, Any],
    allocation: Sequence[int],
    seed: int,
) -> dict[str, Any]:
    split = body_proposal["split"]
    selected_global = set(map(int, body_proposal["selected_global_indices"]))
    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(global_counts))
    require(len(class_keys) == len(allocation) == 8, "allocation width drift")

    proposer_model = e105.build_nested_model(
        e095=e095,
        prepared=prepared,
        nested_side="upper",
        template_counts=template_counts_from_split(split, "upper"),
        body_hint_indices=selected_global,
        allocation_caps=global_counts,
    )
    for index, key in enumerate(class_keys):
        proposer_model["model"].Add(
            proposer_model["allocation_vars"][key] == int(allocation[index])
        )
    proposer_solver = one_worker_solver(45.0, seed)
    proposer_started = time.monotonic()
    proposer_code = proposer_solver.Solve(proposer_model["model"])
    proposer_elapsed = time.monotonic() - proposer_started
    proposer_status = proposer_solver.StatusName(proposer_code)
    require(
        proposer_status in {"OPTIMAL", "FEASIBLE"},
        f"allocation proposer replay not feasible: {proposer_status}",
    )

    caps = {
        key: int(global_counts[key]) - int(allocation[index])
        for index, key in enumerate(class_keys)
    }
    require(all(value >= 0 for value in caps.values()), "negative consumer cap")
    consumer_model = e105.build_nested_model(
        e095=e095,
        prepared=prepared,
        nested_side="lower",
        template_counts=template_counts_from_split(split, "lower"),
        body_hint_indices=selected_global,
        allocation_caps=caps,
    )
    consumer_solver = one_worker_solver(75.0, seed + 100)
    consumer_started = time.monotonic()
    consumer_code = consumer_solver.Solve(consumer_model["model"])
    consumer_elapsed = time.monotonic() - consumer_started
    consumer_status = consumer_solver.StatusName(consumer_code)
    require(
        consumer_status == "INFEASIBLE",
        f"allocation consumer replay not INFEASIBLE: {consumer_status}",
    )
    return {
        "allocation_tuple": list(map(int, allocation)),
        "proposer": {
            "status": proposer_status,
            "elapsed_seconds": proposer_elapsed,
            "branches": int(proposer_solver.NumBranches()),
            "conflicts": int(proposer_solver.NumConflicts()),
        },
        "consumer": {
            "status": consumer_status,
            "elapsed_seconds": consumer_elapsed,
            "branches": int(consumer_solver.NumBranches()),
            "conflicts": int(consumer_solver.NumConflicts()),
        },
        "workers": 1,
        "search_branching": "PSEUDO_COST_SEARCH",
        "symmetry_level": 0,
        "probing_level": 0,
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E106 check: {OUTPUT}")
    records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E106 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E106 artifact identity drift: {path}")
        records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    split_store = load(SPLIT_STORE)
    require(result["verdict"] == "NESTED_ALLOCATION_VECTOR_LIMIT_REACHED", "verdict drift")
    require(
        result["decision"] == "CONTINUE_FROM_SPLIT_AND_ALLOCATION_NOGOOD_STORE",
        "decision drift",
    )
    require(result["terminal"] == "ALLOCATION_LIMIT", "terminal drift")
    require(result["combined_witness"] is None, "censored branch leaks combined witness")
    require(result["module_b_witness"] is None, "censored branch leaks module-B witness")
    require(int(split_store["nogood_count"]) == 4, "split store count drift")
    store_vectors = [tuple(map(int, row["upper"])) for row in split_store["nogoods"]]
    require(store_vectors == EXPECTED_SPLITS, f"split store vector drift: {store_vectors}")
    require(
        [tuple(map(int, row["proposer_allocation_tuple"])) for row in result["allocation_nogoods"]]
        == EXPECTED_ALLOCATIONS,
        "allocation nogood vector drift",
    )

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e106_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e106_check_e100")
    e104 = source_module(E104_RUNNER, "zmd_e106_check_e104")
    e105 = source_module(E105_RUNNER, "zmd_e106_check_e105")
    prepared = e104.reconstruct(e095=e095, e100=e100)

    body_replays: list[dict[str, Any]] = []
    body_payloads: list[Mapping[str, Any]] = []
    for index, record in enumerate(result["body_records"]):
        path = ROOT / str(record["path"])
        require(path.is_file(), f"missing body proposal {index}")
        require(sha256(path) == record["sha256"], f"body proposal hash drift {index}")
        body = load(path)
        require(body["status"] == "OPTIMAL", f"body proposal status drift {index}")
        body_payloads.append(body)
        body_replays.append(
            {
                "proposal_index": index,
                "split": body["split"],
                **replay_body_proposal(prepared=prepared, proposal=body),
            }
        )
    require(
        [tuple(map(int, body["split"]["upper"])) for body in body_payloads]
        == [EXPECTED_SPLITS[1], EXPECTED_SPLITS[2], EXPECTED_SPLITS[3], OPEN_SPLIT],
        "body proposal split order drift",
    )

    direct_records = [
        row
        for row in result["handshake_records"]
        if row.get("effect") == "EXACT_TEMPLATE_SPLIT_NOGOOD"
    ]
    require(len(direct_records) == 3, "direct split negative count drift")
    split_replays = [
        {
            "proposal_index": index,
            "upper_split": list(map(int, body_payloads[index]["split"]["upper"])),
            **replay_direct_split_negative(
                e095=e095,
                e105=e105,
                prepared=prepared,
                body_proposal=body_payloads[index],
                proposer_record=direct_records[index],
                seed=106900 + index,
            ),
        }
        for index in range(3)
    ]

    allocation_replays = [
        replay_allocation_nogood(
            e095=e095,
            e105=e105,
            prepared=prepared,
            body_proposal=body_payloads[3],
            allocation=allocation,
            seed=106950 + index,
        )
        for index, allocation in enumerate(EXPECTED_ALLOCATIONS)
    ]

    payload = {
        "schema": "zmd_e106_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "THREE_NEW_SPLIT_NOGOODS_AND_THREE_ALLOCATION_NOGOODS_REPLAYED",
        "artifact_records": records,
        "body_replays": body_replays,
        "split_negative_replays": split_replays,
        "allocation_nogood_replays": allocation_replays,
        "template_split_nogood_count": 4,
        "new_template_split_nogood_count": 3,
        "allocation_nogood_count": 3,
        "open_split_upper": list(OPEN_SPLIT),
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Independent body replay plus solver-diverse side-model replay. Only "
            "the four exact template splits and three exact upper allocation vectors "
            "listed here are rejected. The open 5/2/1 split remains unresolved."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "template_split_nogood_count": payload[
                    "template_split_nogood_count"
                ],
                "allocation_nogood_count": payload["allocation_nogood_count"],
                "open_split_upper": payload["open_split_upper"],
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
