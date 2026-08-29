#!/usr/bin/env python3
"""Independent replay promoting E107's open split after direct lower infeasibility."""

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
RUNNER = HERE / "run_e107.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E107_reverse_nested_allocation_handshake/run-001"
)
RESULT = RUN / "RESULT.json"
LOWER = RUN / "LOWER_PROPOSER_00.json"
STORE = RUN / "BIDIRECTIONAL_ALLOCATION_STORE.json"
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
E106_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E106_nested_template_split_frontier/run-001/RESULT.json"
)
E106_CHECK = E106_RESULT.with_name("ARTIFACT_CHECK.json")
E106_BODY = E106_RESULT.with_name("BODY_PROPOSAL_03.json")

EXPECTED = {
    RUNNER: "321e81f1751aa5293522f725643cb84a9249c603040fee98359ae413122166f6",
    RESULT: "ac3669812181c9659bb0e02ea45b291be6985f9ea90e3f849c42cbdd9c30348f",
    LOWER: "7246918cdca6043462d71072d1dc201b43e4ccb8615d37107b7a86cd891a2ab2",
    STORE: "e01257f3d129cf6398bfe14f500224ca9ef21af86509e9a90257b1bf38d9d8f2",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    E105_RUNNER: "7dbdf3be073dd77b6ef091b4302442aa5766882d2f384b285576b84c368588b9",
    E106_RESULT: "026fe686944616305ff5056a574152a5c8d57fac44b15a797563b555c33316ae",
    E106_CHECK: "acad46fdf658475d2dcc801a624514dde4213e0c890424debb7e2d5fb4ba9cfc",
    E106_BODY: "8293d53a8985b1631e7211e562e7422e783a36741f6e20b8945431db6d032f0a",
}
LOWER_TEMPLATES = {
    "manufacturing_3x3": 5,
    "manufacturing_5x5": 4,
    "manufacturing_6x4": 9,
}
OPEN_UPPER = [5, 2, 1]
OPEN_LOWER = [5, 4, 9]


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


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E107 check: {OUTPUT}")
    records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E107 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E107 artifact identity drift: {path}")
        records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    lower = load(LOWER)
    store = load(STORE)
    e106 = load(E106_RESULT)
    e106_check = load(E106_CHECK)
    body = load(E106_BODY)

    require(
        result["verdict"] == "OPEN_SPLIT_ALLOCATION_FACE_EXHAUSTED_PENDING_REPLAY",
        "E107 verdict drift",
    )
    require(
        result["decision"] == "REPLAY_COMPLETE_NOGOOD_CHAIN_BEFORE_SPLIT_PROMOTION",
        "E107 decision drift",
    )
    require(result["terminal"] == "LOWER_DIRECT_INFEASIBLE", "E107 terminal drift")
    require(result["split"]["upper"] == OPEN_UPPER, "E107 upper split drift")
    require(result["split"]["lower"] == OPEN_LOWER, "E107 lower split drift")
    require(lower["status"] == "INFEASIBLE", "E107 lower producer status drift")
    require(int(lower["candidate_count"]) == 812, "E107 lower candidate count drift")
    require(lower["template_counts"] == LOWER_TEMPLATES, "E107 lower totals drift")
    require(result["new_lower_allocation_nogoods"] == [], "direct negative has nogoods")
    require(result["combined_witness"] is None, "negative leaks combined witness")
    require(result["module_b_witness"] is None, "negative leaks module-B witness")
    require(not list(RUN.glob("UPPER_CONSUMER_*.json")), "upper consumer unexpectedly ran")
    require(not list(RUN.glob("OUTER_LOW_*.json")), "outer low unexpectedly ran")

    require(e106["verdict"] == "NESTED_ALLOCATION_VECTOR_LIMIT_REACHED", "E106 drift")
    require(e106_check["status"] == "PASS", "E106 check not PASS")
    require(body["split"]["upper"] == OPEN_UPPER, "E106 body upper split drift")
    require(body["split"]["lower"] == OPEN_LOWER, "E106 body lower split drift")
    require(store["split"]["upper"] == OPEN_UPPER, "store upper split drift")
    require(store["split"]["lower"] == OPEN_LOWER, "store lower split drift")
    require(
        len(store["e106_upper_vectors_rejected_by_lower"]) == 3,
        "store prior upper nogood count drift",
    )
    require(store["e107_lower_vectors_rejected_by_upper"] == [], "store new vector drift")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e107_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e107_check_e100")
    e104 = source_module(E104_RUNNER, "zmd_e107_check_e104")
    e105 = source_module(E105_RUNNER, "zmd_e107_check_e105")
    prepared = e104.reconstruct(e095=e095, e100=e100)
    body_hint_indices = set(map(int, body["selected_global_indices"]))
    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    replay_model = e105.build_nested_model(
        e095=e095,
        prepared=prepared,
        nested_side="lower",
        template_counts=LOWER_TEMPLATES,
        body_hint_indices=body_hint_indices,
        allocation_caps=global_counts,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 107901
    solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    started = time.monotonic()
    status_code = solver.Solve(replay_model["model"])
    elapsed = time.monotonic() - started
    status = solver.StatusName(status_code)
    require(status == "INFEASIBLE", f"lower replay not INFEASIBLE: {status}")

    payload = {
        "schema": "zmd_e107_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "OPEN_SPLIT_CLOSED_BY_DIRECT_LOWER_INFEASIBILITY",
        "artifact_records": records,
        "split": {
            "upper": OPEN_UPPER,
            "lower": OPEN_LOWER,
            "split_digest": result["split"]["split_digest"],
        },
        "producer": {
            "status": lower["status"],
            "elapsed_seconds": lower["elapsed_seconds"],
            "branches": lower["branches"],
            "conflicts": lower["conflicts"],
            "candidate_count": lower["candidate_count"],
        },
        "solver_diverse_lower_replay": {
            "status": status,
            "elapsed_seconds": elapsed,
            "branches": int(solver.NumBranches()),
            "conflicts": int(solver.NumConflicts()),
            "workers": 1,
            "search_branching": "PSEUDO_COST_SEARCH",
            "symmetry_level": 0,
            "probing_level": 0,
        },
        "promoted_template_split_nogood": {
            "upper": OPEN_UPPER,
            "lower": OPEN_LOWER,
            "reason": "complete_lower_native_front_projection_empty",
        },
        "verdict": "OPEN_SPLIT_TEMPLATE_VECTOR_INFEASIBLE",
        "decision": "RETURN_TO_BODY_FRONTIER_WITH_FIFTH_SPLIT_NOGOOD",
        "truth_boundary": (
            "The full lower side is exact INFEASIBLE with free class allocation at "
            "template totals 5/4/9. Therefore split upper 5/2/1 plus lower 5/4/9 "
            "is rejected. No other split, y60 parent or module-B parent is rejected."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "replay_status": status,
                "promoted_upper_split": OPEN_UPPER,
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
