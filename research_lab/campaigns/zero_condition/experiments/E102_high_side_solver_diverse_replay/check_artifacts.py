#!/usr/bin/env python3
"""Independent branch and feasible-set joins for E102."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e102.py"
RUN = ROOT / "research_lab/local/zero_condition/E102_high_side_solver_diverse_replay/run-001"
RESULT = RUN / "RESULT.json"
HIGH = RUN / "HIGH_RESULT.json"
LOW = RUN / "LOW_RESULT.json"
MODULE_B = RUN / "MODULE_B_WITNESS.json"
COMBINED = RUN / "COMBINED_WITNESS.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
E101_HIGH = ROOT / "research_lab/local/zero_condition/E101_x42_allocation_handshake/run-001/HIGH_RESULT_00.json"
E101_BODY = ROOT / "research_lab/local/zero_condition/E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"

EXPECTED = {
    RUNNER: "a7415535a105199d3745a322d4ff9e6cd2fe443961fb2108e6b5126bdf777af5",
    RESULT: "853dfba41a1cd017cb010a1255b07f077d24fb2e6221c1fdc9130d2ac6f30d90",
    HIGH: "eae72ad0237d0b7d6d68490a1580d7f13e84e859c10d15803bb34def6a72a67e",
    E101_HIGH: "19354cf83b3e0463c2d5fd24aa8880dda4b55ab5dbf5a69d4f496ec6b1b40d02",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
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


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E102 check: {OUTPUT}")
    records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E102 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E102 artifact identity drift: {path}")
        records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    high = load(HIGH)
    prior = load(E101_HIGH)
    body = load(E101_BODY)
    require(
        result["verdict"] == "SOLVER_DIVERSE_HIGH_SIDE_STILL_CENSORED",
        "E102 verdict drift",
    )
    require(
        result["decision"] == "BUILD_HIGH_SIDE_TEMPLATE_SPATIAL_CAPACITY_AUDIT",
        "E102 decision drift",
    )
    require(result["controls"]["feasible_set_changed"] is False, "feasible-set marker drift")
    require(result["high"]["sha256"] == sha256(HIGH), "high join drift")
    require(high["status"] == "UNKNOWN", "high status drift")
    require(result["high"]["status"] == "UNKNOWN", "wrapper high status drift")
    require(result["high"]["allocation"] is None, "censored allocation leakage")
    require(result["high"]["allocation_tuple"] is None, "censored tuple leakage")
    require(int(result["high"]["selected_body_count"]) == 0, "censored body leakage")
    require(result["low"] is None, "low ran without a high allocation")
    require(result["module_b_witness"] is None, "module-B witness leakage")
    require(result["combined_witness"] is None, "combined witness leakage")
    require(not LOW.exists(), "unexpected low artifact")
    require(not MODULE_B.exists(), "unexpected module-B witness artifact")
    require(not COMBINED.exists(), "unexpected combined witness artifact")

    invariant_fields = (
        "candidate_count",
        "mode_class_variable_count",
        "model_variable_count",
        "model_constraint_count",
        "disabled_unpowered_candidate_count",
        "matched_hint_count",
        "template_counts",
    )
    for field in invariant_fields:
        require(high[field] == prior[field], f"high feasible-set projection drift: {field}")
    require(
        result["body_template_allocation"]["source_sha256"] == sha256(E101_BODY),
        "body allocation join drift",
    )
    require(body["side_template_counts"] == {
        "high:manufacturing_3x3": 10,
        "high:manufacturing_5x5": 6,
        "high:manufacturing_6x4": 10,
        "low:manufacturing_3x3": 43,
        "low:manufacturing_5x5": 11,
        "low:manufacturing_6x4": 11,
    }, "body template allocation drift")
    controls = result["controls"]["high"]
    require(controls == {
        "workers": 1,
        "search_branching": "PSEUDO_COST_SEARCH",
        "symmetry_level": 0,
        "probing_level": 0,
        "randomize_search": False,
        "seed": 102001,
        "seconds": 90.0,
    }, "solver controls drift")

    payload = {
        "schema": "zmd_e102_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "IDENTICAL_HIGH_FEASIBLE_SET_SECOND_SOLVER_CENSORED",
        "artifact_records": records,
        "invariant_projection": {field: high[field] for field in invariant_fields},
        "high_status": "UNKNOWN",
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Confirms identical structural high model and no witness leakage. "
            "UNKNOWN remains censored and is not an allocation or negative."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(json.dumps({
        "status": "PASS",
        "classification": payload["classification"],
        "verdict": payload["verdict"],
        "decision": payload["decision"],
        "output_path": str(OUTPUT.relative_to(ROOT)),
        "output_sha256": sha256(OUTPUT),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
