#!/usr/bin/env python3
"""Independent artifact and body-witness replay for E101."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import types
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e101.py"
RUN = ROOT / "research_lab/local/zero_condition/E101_x42_allocation_handshake/run-001"
RESULT = RUN / "RESULT.json"
BODY = RUN / "BODY_ONLY_RESULT.json"
HIGH = RUN / "HIGH_RESULT_00.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"

EXPECTED = {
    RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    RESULT: "b6b088f214fcbb3be01b26180ce9d211b647ede4038e7542531077548bfd9e9d",
    BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    HIGH: "19354cf83b3e0463c2d5fd24aa8880dda4b55ab5dbf5a69d4f496ec6b1b40d02",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
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
    exec(compile(raw, f"<source-check:{path}>", "exec", dont_inherit=True), module.__dict__)
    return module


def replay_body_witness(e100: types.ModuleType, e095: types.ModuleType, body: dict[str, Any]) -> dict[str, Any]:
    restricted = e100.build_restricted_context(e095)
    rows = restricted["rows"]
    selected_indices = list(map(int, body["selected_body_indices"]))
    require(len(selected_indices) == 91, "E101 body selected count drift")
    require(len(set(selected_indices)) == 91, "E101 duplicate selected index")
    selected = [rows[index] for index in selected_indices]

    occupied: set[tuple[int, int]] = set(restricted["base"]["fixed_solid"])
    for row in selected:
        cells = set(row["body"])
        require(not cells & occupied, "E101 body witness overlap")
        require(all(x != 42 for x, _y in cells), "E101 body witness uses x42")
        occupied |= cells
        require(bool(cells & set(restricted["base"]["fixed_coverage"])), "E101 unpowered body")

    templates = Counter(str(row["template"]) for row in selected)
    require(templates == Counter({"manufacturing_3x3": 53, "manufacturing_5x5": 17, "manufacturing_6x4": 21}), "E101 template count drift")
    sides = Counter(str(row["side"]) for row in selected)
    require(dict(sides) == body["side_body_counts"], "E101 side count join drift")
    side_templates = Counter((str(row["side"]), str(row["template"])) for row in selected)
    observed_side_templates = {f"{side}:{template}": count for (side, template), count in sorted(side_templates.items())}
    require(observed_side_templates == body["side_template_counts"], "E101 side template join drift")

    for instance_id, footprint in restricted["base"]["stable_footprints"].items():
        require(sum(tuple(row["body"]) == footprint for row in selected) == 1, f"stable body missing: {instance_id}")
    anchor = set(restricted["base"]["hint_bodies"]["B"])
    retained = sum(tuple(row["body"]) in anchor for row in selected)
    require(retained == int(body["retained_anchor_count"]), "E101 retained anchor drift")
    return {
        "selected_body_count": 91,
        "side_body_counts": dict(sorted(sides.items())),
        "side_template_counts": observed_side_templates,
        "retained_anchor_count": retained,
        "occupied_cell_count": len(occupied),
        "stable_body_count": 2,
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E101 check: {OUTPUT}")
    records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E101 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E101 artifact drift: {path}")
        records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    body = load(BODY)
    high = load(HIGH)
    require(result["verdict"] == "X42_HIGH_SIDE_ALLOCATION_PROPOSER_CENSORED", "E101 verdict drift")
    require(result["decision"] == "CHANGE_HIGH_SIDE_SOLVER_OR_DERIVE_ALLOCATION_BOUNDS", "E101 decision drift")
    require(result["body_only"]["sha256"] == sha256(BODY), "E101 body join drift")
    require(result["handshake_records"][0]["high_sha256"] == sha256(HIGH), "E101 high join drift")
    require(body["status"] == "OPTIMAL", "E101 body status drift")
    require(high["status"] == "UNKNOWN", "E101 high status drift")
    require(not high.get("selected_bodies"), "E101 censored high carries bodies")
    require(not high.get("allocation_tuple"), "E101 censored high carries allocation")
    require(result["tested_allocation_count"] == 0, "E101 tested allocation drift")
    require(result["rejected_allocation_tuples"] == [], "E101 rejected allocation drift")
    require(result["combined_witness"] is None, "E101 censored result carries combined witness")

    source_module(OPERATION_PROFILES, "src.preprocess.operation_profiles", package="src.preprocess")
    e095 = source_module(E095_RUNNER, "zmd_e101_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e101_check_e100")
    body_replay = replay_body_witness(e100, e095, body)

    require(high["candidate_count"] == 1324, "E101 high candidate drift")
    require(high["template_counts"] == {"manufacturing_3x3": 10, "manufacturing_5x5": 6, "manufacturing_6x4": 10}, "E101 high template allocation drift")
    require(high["matched_hint_count"] == 26, "E101 high hint drift")

    payload = {
        "schema": "zmd_e101_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "BODY_WITNESS_VALID_HIGH_SIDE_CENSORED",
        "artifact_records": records,
        "body_replay": body_replay,
        "high_status": high["status"],
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": "The body/power witness is replayed; high-side UNKNOWN remains censored and supplies no allocation nogood.",
    }
    dump_exclusive(OUTPUT, payload)
    print(json.dumps({"status": "PASS", "classification": payload["classification"], "verdict": payload["verdict"], "decision": payload["decision"], "output_path": str(OUTPUT.relative_to(ROOT)), "output_sha256": sha256(OUTPUT)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
