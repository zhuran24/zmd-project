#!/usr/bin/env python3
"""Independent body replay and solver-diverse negative check for E105."""

from __future__ import annotations

from collections import Counter
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
RUNNER = HERE / "run_e105.py"
RUN = ROOT / "research_lab/local/zero_condition/E105_nested_allocation_handshake/run-003"
RESULT = RUN / "RESULT.json"
BODY = RUN / "BODY_ONLY_RESULT.json"
PROPOSER = RUN / "PROPOSER_RESULT_00.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
FAILURE_1 = ROOT / "research_lab/local/zero_condition/E105_nested_allocation_handshake/run-001/FAILURE.json"
FAILURE_2 = ROOT / "research_lab/local/zero_condition/E105_nested_allocation_handshake/run-002/FAILURE.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"
E104_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E104_high_reserved_y60_constructor/run_e104.py"

EXPECTED = {
    RUNNER: "7dbdf3be073dd77b6ef091b4302442aa5766882d2f384b285576b84c368588b9",
    RESULT: "95ae95cc649097aae4010cb5ebe96f6027fefdfac2ee469d877cb8940a009ecb",
    BODY: "8c4a4b0c72f2fed7bca59cde513d9a286b5c368c3d06f9ed0c9033a9b1d319ca",
    PROPOSER: "dfad7745d7aaf239d87a02d3e446d3dfe267c137df2762e24d2b1bd85aeeed55",
    FAILURE_1: "6478a18a556f6b6fc4d6c591e35b06bea51a8c46d7d198e5020c1df87f51de17",
    FAILURE_2: "691373a7030abc1dc192c7ca0a64d04dfb7989f36db151ff2380d833ee146ced",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
}


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
        compile(raw, f"<source-isolated-check:{path}:{hashlib.sha256(raw).hexdigest()}>", "exec", dont_inherit=True),
        module.__dict__,
    )
    return module


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E105 check: {OUTPUT}")
    records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E105 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E105 artifact identity drift: {path}")
        records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    body = load(BODY)
    proposer = load(PROPOSER)
    require(result["verdict"] == "NESTED_TEMPLATE_SPLIT_NATIVE_FRONT_INFEASIBLE", "verdict drift")
    require(result["decision"] == "ADD_EXACT_BODY_TEMPLATE_SPLIT_NOGOOD", "decision drift")
    require(body["status"] == "OPTIMAL" and body["selected_body_count"] == 26, "body witness drift")
    require(body["nested_side_body_counts"] == {"lower": 19, "upper": 7}, "side counts drift")
    require(
        body["nested_side_template_counts"]
        == {
            "lower:manufacturing_3x3": 7,
            "lower:manufacturing_5x5": 4,
            "lower:manufacturing_6x4": 8,
            "upper:manufacturing_3x3": 3,
            "upper:manufacturing_5x5": 2,
            "upper:manufacturing_6x4": 2,
        },
        "template split drift",
    )
    require(proposer["nested_side"] == "upper", "proposer side drift")
    require(proposer["status"] == "INFEASIBLE", "producer negative drift")
    require(proposer["template_counts"] == {"manufacturing_3x3": 3, "manufacturing_5x5": 2, "manufacturing_6x4": 2}, "upper template counts drift")
    require(not list(RUN.glob("CONSUMER_RESULT_*.json")), "consumer unexpectedly ran")
    require(not list(RUN.glob("OUTER_LOW_RESULT_*.json")), "outer low unexpectedly ran")
    require(not (RUN / "COMBINED_WITNESS.json").exists(), "negative branch leaks witness")

    source_module(OPERATION_PROFILES, "src.preprocess.operation_profiles", package="src.preprocess")
    e095 = source_module(E095_RUNNER, "zmd_e105_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e105_check_e100")
    e104 = source_module(E104_RUNNER, "zmd_e105_check_e104")
    e105 = source_module(RUNNER, "zmd_e105_check_runner")
    prepared = e104.reconstruct(e095=e095, e100=e100)
    rows = prepared["survivors"]
    selected_global = set(map(int, body["selected_global_indices"]))
    selected_rows = [row for row in rows if int(row["global_row_index"]) in selected_global]
    require(len(selected_rows) == 26, "body identity replay count drift")
    occupied: set[tuple[int, int]] = set()
    for row in selected_rows:
        for value in row["body"]:
            require(value not in occupied, f"body overlap at {value}")
            occupied.add(value)
        require(bool(set(row["body"]) & set(prepared["context"]["fixed_coverage"])), "unpowered body")
    stable = {
        instance_id
        for instance_id, footprint in prepared["context"]["stable_footprints"].items()
        if any(tuple(row["body"]) == footprint for row in selected_rows)
    }
    require(stable == set(prepared["context"]["stable_footprints"]), "stable bodies absent")
    observed_templates = Counter((str(row["nested_side"]), str(row["template"])) for row in selected_rows)
    expected_templates = Counter(
        {
            ("lower", "manufacturing_3x3"): 7,
            ("lower", "manufacturing_5x5"): 4,
            ("lower", "manufacturing_6x4"): 8,
            ("upper", "manufacturing_3x3"): 3,
            ("upper", "manufacturing_5x5"): 2,
            ("upper", "manufacturing_6x4"): 2,
        }
    )
    require(observed_templates == expected_templates, "body template replay drift")

    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    upper_model = e105.build_nested_model(
        e095=e095,
        prepared=prepared,
        nested_side="upper",
        template_counts={"manufacturing_3x3": 3, "manufacturing_5x5": 2, "manufacturing_6x4": 2},
        body_hint_indices=selected_global,
        allocation_caps=global_counts,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 105901
    solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    started = time.monotonic()
    status_code = solver.Solve(upper_model["model"])
    elapsed = time.monotonic() - started
    status = solver.StatusName(status_code)
    require(status == "INFEASIBLE", f"solver-diverse replay not INFEASIBLE: {status}")

    payload = {
        "schema": "zmd_e105_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "EXACT_NESTED_TEMPLATE_SPLIT_NOGOOD",
        "artifact_records": records,
        "body_replay": {
            "selected_body_count": len(selected_rows),
            "occupied_cell_count": len(occupied),
            "template_counts": {
                f"{side}:{template}": count
                for (side, template), count in sorted(observed_templates.items())
            },
            "stable_body_count": len(stable),
            "unpowered_count": 0,
        },
        "solver_diverse_upper_replay": {
            "status": status,
            "elapsed_seconds": elapsed,
            "branches": int(solver.NumBranches()),
            "conflicts": int(solver.NumConflicts()),
            "workers": 1,
            "search_branching": "PSEUDO_COST_SEARCH",
            "symmetry_level": 0,
            "probing_level": 0,
        },
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "The body witness is replayed independently and the upper native-front "
            "negative is solver-diverse. The nogood applies only to template split "
            "lower 7/4/8 and upper 3/2/2 under reserved y60."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "replay_status": status,
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
