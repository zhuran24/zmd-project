#!/usr/bin/env python3
"""Independent replay and branch audit for E115's 27 template states."""

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
RUNNER = HERE / "run_e115.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E115_separator_template_state_full_consumer/run-001"
)
RESULT = RUN / "RESULT.json"
STATE_RESULTS = RUN / "STATE_CONSUMER_RESULTS.json"
LOW_RESULTS = RUN / "LOW_COMPLEMENT_RESULTS.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
UNKNOWN_PACKET = RUN / "UNKNOWN_TEMPLATE_STATES.json"
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
E101_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E101_x42_allocation_handshake/run_e101.py"
)
E114_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E114_e110_fixed_geometry_direct_consumer/run_e114.py"
)
E112_MANIFEST = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E112_fixed_separator_class_state_closure/run-001/"
    "SEPARATOR_CLASS_ATLAS_MANIFEST.json"
)

EXPECTED = {
    RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    RESULT: "f6b1e3e4ef29aadd7d865a97424c4379b828608a857a3893172c03c3b9497ef2",
    STATE_RESULTS: "41f0560f5170d127fc7cbaeea379d47f70dd712f9eeb123e9b42a83148ae7a06",
    LOW_RESULTS: "84db25c7710a55c9aee9a42f49d1ce07d8c625b6c2ce8583e0ac0e4aade7f087",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E114_RUNNER: "e893bdc7df70ce93f66c3976a06e3fd15e2d81b492fd2463b9d17cec4cd16e5d",
    E112_MANIFEST: "45767f5f1a00d051701e1bd6787a77a813e23d1958652c632dbfea336113db2a",
}

EXPECTED_NEGATIVE_VECTORS = {(0, 3, 0), (5, 0, 0)}
EXPECTED_FORMAL_STATE_COUNT = 27
EXPECTED_UNKNOWN_STATE_COUNT = 25
EXPECTED_SEPARATOR_POSITIVE_COUNT = 350
LOW_CARDINALITY_THRESHOLD = 3


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def source_module(
    path: Path,
    name: str,
    package: str | None = None,
) -> types.ModuleType:
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


def replay_negative(
    *,
    e095: types.ModuleType,
    e101: types.ModuleType,
    e115: types.ModuleType,
    restricted: dict[str, Any],
    language: dict[str, Any],
    vector: tuple[int, int, int],
    seed: int,
) -> dict[str, Any]:
    bundle = e115.build_state_model(
        e095=e095,
        e101=e101,
        restricted=restricted,
        language=language,
        vector=vector,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 90.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = int(seed)
    solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.randomize_search = False
    solver.parameters.stop_after_first_solution = True
    started = time.monotonic()
    status_code = solver.Solve(bundle["model"])
    elapsed = time.monotonic() - started
    status = solver.StatusName(status_code)
    require(status == "INFEASIBLE", f"E115 negative replay censored: {vector}: {status}")
    return {
        "separator_template_vector": list(vector),
        "status": status,
        "elapsed_seconds": elapsed,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "workers": 1,
        "search_branching": "PSEUDO_COST_SEARCH",
        "symmetry_level": 0,
        "probing_level": 0,
        "allowed_separator_state_count": int(bundle["allowed_separator_state_count"]),
        "live_body_variable_count": int(bundle["live_body_variable_count"]),
    }


def main() -> int:
    if OUTPUT.exists() or UNKNOWN_PACKET.exists():
        raise FileExistsError("refusing to overwrite E115 checker outputs")

    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E115 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E115 artifact identity drift: {path}")
        artifact_records[str(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    states = load(STATE_RESULTS)
    low = load(LOW_RESULTS)
    manifest = load(E112_MANIFEST)
    require(
        result["verdict"] == "SEPARATOR_TEMPLATE_STATE_FULL_CONSUMER_CENSORED",
        "E115 verdict drift",
    )
    require(
        result["decision"] == "REPLAY_ONLY_NAMED_UNKNOWN_STATES",
        "E115 decision drift",
    )
    require(int(states["formal_state_count"]) == EXPECTED_FORMAL_STATE_COUNT, "formal count drift")
    require(int(states["tested_state_count"]) == EXPECTED_FORMAL_STATE_COUNT, "tested count drift")
    require(int(states["positive_state_count"]) == 0, "unexpected positive state")
    require(int(states["negative_state_count"]) == len(EXPECTED_NEGATIVE_VECTORS), "negative count drift")
    require(int(states["unknown_state_count"]) == EXPECTED_UNKNOWN_STATE_COUNT, "unknown count drift")
    require(states["untested_state_vectors"] == [], "untested state leakage")
    require(low["records"] == [], "unexpected low complement record")
    require(
        manifest.get("complete") is True
        and int(manifest.get("summary", {}).get("positive_state_count", -1))
        == EXPECTED_SEPARATOR_POSITIVE_COUNT,
        "E112 manifest identity drift",
    )

    records_by_vector: dict[tuple[int, int, int], dict[str, Any]] = {}
    for record in states["records"]:
        vector = tuple(map(int, record["separator_template_vector"]))
        require(vector not in records_by_vector, f"duplicate E115 vector: {vector}")
        records_by_vector[vector] = record
        high = record["high"]
        status = str(high["status"])
        require(
            status in {"INFEASIBLE", "UNKNOWN"},
            f"unexpected E115 terminal status: {vector}: {status}",
        )
        if status == "UNKNOWN":
            for key in (
                "selected_body_indices",
                "selected_modes",
                "allocation_tuple",
                "separator_class_tuple",
            ):
                require(key not in high, f"censored state leaked {key}: {vector}")
        else:
            require(vector in EXPECTED_NEGATIVE_VECTORS, f"unexpected negative vector: {vector}")
    require(len(records_by_vector) == EXPECTED_FORMAL_STATE_COUNT, "record vector count drift")
    observed_negative = {
        vector
        for vector, record in records_by_vector.items()
        if record["high"]["status"] == "INFEASIBLE"
    }
    require(observed_negative == EXPECTED_NEGATIVE_VECTORS, "negative vector set drift")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e115_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e115_check_e100")
    e101 = source_module(E101_RUNNER, "zmd_e115_check_e101")
    e114 = source_module(E114_RUNNER, "zmd_e115_check_e114")
    e115 = source_module(RUNNER, "zmd_e115_check_runner")
    del e114  # imported to validate exact helper identity; E115 rebuilds through source calls.
    restricted = e100.build_restricted_context(e095)
    language = e115.load_language(restricted)

    replays = [
        replay_negative(
            e095=e095,
            e101=e101,
            e115=e115,
            restricted=restricted,
            language=language,
            vector=vector,
            seed=115900 + index,
        )
        for index, vector in enumerate(sorted(EXPECTED_NEGATIVE_VECTORS))
    ]

    unknown_records: list[dict[str, Any]] = []
    low_cardinality_records: list[dict[str, Any]] = []
    for vector, record in sorted(records_by_vector.items()):
        if record["high"]["status"] != "UNKNOWN":
            continue
        allowed_states = [
            list(state) for state in language["allowed_by_vector"][vector]
        ]
        packet_record = {
            "separator_template_vector": list(vector),
            "allowed_separator_state_count": len(allowed_states),
            "allowed_separator_class_states": allowed_states,
            "representative_zero_domain_count": int(
                record["representative_zero_domain_count"]
            ),
            "producer_elapsed_seconds": float(record["high"]["elapsed_seconds"]),
            "producer_branches": int(record["high"]["branches"]),
            "producer_conflicts": int(record["high"]["conflicts"]),
            "model_variable_count": int(record["high"]["model_variable_count"]),
            "model_constraint_count": int(record["high"]["model_constraint_count"]),
        }
        unknown_records.append(packet_record)
        if len(allowed_states) <= LOW_CARDINALITY_THRESHOLD:
            low_cardinality_records.append(packet_record)
    require(len(unknown_records) == EXPECTED_UNKNOWN_STATE_COUNT, "unknown packet count drift")

    unknown_packet = {
        "schema": "zmd_e115_unknown_template_states_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "class_order": [list(key) for key in language["class_keys"]],
        "unknown_state_count": len(unknown_records),
        "unknown_states": unknown_records,
        "low_cardinality_threshold": LOW_CARDINALITY_THRESHOLD,
        "low_cardinality_state_count": len(low_cardinality_records),
        "low_cardinality_tuple_count": sum(
            int(record["allowed_separator_state_count"])
            for record in low_cardinality_records
        ),
        "low_cardinality_states": low_cardinality_records,
        "unknown_state_digest": stable_digest(
            [
                (
                    record["separator_template_vector"],
                    record["allowed_separator_class_states"],
                )
                for record in unknown_records
            ]
        ),
        "truth_boundary": (
            "Every listed template state is UNKNOWN in E115. Allowed class tuples "
            "are exact necessary separator-only positives, not full-high witnesses."
        ),
    }
    dump_exclusive(UNKNOWN_PACKET, unknown_packet)

    payload = {
        "schema": "zmd_e115_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "TWO_TEMPLATE_STATES_EXACT_NEGATIVE_TWENTY_FIVE_NAMED_UNKNOWN",
        "artifact_records": artifact_records,
        "negative_state_replays": replays,
        "negative_state_count": len(replays),
        "unknown_state_count": len(unknown_records),
        "unknown_packet": {
            "path": str(UNKNOWN_PACKET.relative_to(ROOT)),
            "sha256": sha256(UNKNOWN_PACKET),
            "unknown_state_count": len(unknown_records),
            "low_cardinality_state_count": len(low_cardinality_records),
            "low_cardinality_tuple_count": unknown_packet[
                "low_cardinality_tuple_count"
            ],
        },
        "verdict": result["verdict"],
        "decision": "FIX_LOW_CARDINALITY_SEPARATOR_CLASS_TUPLES_FIRST",
        "truth_boundary": (
            "Vectors 0/3/0 and 5/0/0 are independently replayed exact contextual "
            "negatives. The other 25 vectors remain UNKNOWN; no absence is inferred."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "negative_vectors": [
                    record["separator_template_vector"] for record in replays
                ],
                "unknown_state_count": len(unknown_records),
                "low_cardinality_state_count": len(low_cardinality_records),
                "low_cardinality_tuple_count": unknown_packet[
                    "low_cardinality_tuple_count"
                ],
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
