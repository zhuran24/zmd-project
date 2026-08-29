#!/usr/bin/env python3
"""Audit E116 and execute its one budget-unattempted tuple in a fresh model."""

from __future__ import annotations

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
RUNNER = HERE / "run_e116.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E116_low_cardinality_separator_tuple_discriminator/run-001"
)
RESULT = RUN / "RESULT.json"
TUPLES = RUN / "FIXED_TUPLE_RESULTS.json"
LOW = RUN / "LOW_COMPLEMENT_RESULTS.json"
SUPPLEMENT = RUN / "UNTESTED_TUPLE_RESULT.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"
E101_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E101_x42_allocation_handshake/run_e101.py"
E114_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E114_e110_fixed_geometry_direct_consumer/run_e114.py"
E115_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E115_separator_template_state_full_consumer/run_e115.py"
E115_UNKNOWN = ROOT / "research_lab/local/zero_condition/E115_separator_template_state_full_consumer/run-001/UNKNOWN_TEMPLATE_STATES.json"
E115_CHECK = ROOT / "research_lab/local/zero_condition/E115_separator_template_state_full_consumer/run-001/ARTIFACT_CHECK.json"

EXPECTED = {
    RUNNER: "e9f76eea9ebb61b4ed2d7ed6b832e1794e5d6410aae967058b33086ec18f701e",
    RESULT: "2b7b93d9a4d1235a7284d9f11eb6512fbc13a3ceb4eda42928cdf7e7c15e378d",
    TUPLES: "fbcd83d392427d3598ef60e51e057c86721560dd5eea76eaa43c7dbb2127e5d0",
    LOW: "7dbf83c8bf70f4a07157577d3f99ca06ed5d74600cccf29e10ec50837785defe",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E114_RUNNER: "e893bdc7df70ce93f66c3976a06e3fd15e2d81b492fd2463b9d17cec4cd16e5d",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E115_UNKNOWN: "0cc243e76134ed53958d22c68a04a6067685b17620b6c1a7676e5ad7b12f0731",
    E115_CHECK: "7e76312570612dc299f73e7dec192fdaa19fc13dee28b958055146571955d76a",
}
EXPECTED_TUPLE_COUNT = 12
EXPECTED_PRODUCER_TESTED = 11
EXPECTED_PRODUCER_UNKNOWN = 11


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
            default=str,
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


def main() -> int:
    if OUTPUT.exists() or SUPPLEMENT.exists():
        raise FileExistsError("refusing to overwrite E116 checker outputs")

    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E116 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E116 artifact identity drift: {path}")
        artifact_records[str(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    tuples = load(TUPLES)
    low = load(LOW)
    require(
        result["verdict"] == "LOW_CARDINALITY_SEPARATOR_TUPLE_DISCRIMINATOR_CENSORED",
        "E116 verdict drift",
    )
    require(
        result["decision"] == "REPLAY_ONLY_NAMED_UNKNOWN_TUPLES",
        "E116 decision drift",
    )
    require(int(tuples["formal_tuple_count"]) == EXPECTED_TUPLE_COUNT, "formal count drift")
    require(int(tuples["tested_tuple_count"]) == EXPECTED_PRODUCER_TESTED, "tested count drift")
    require(int(tuples["positive_tuple_count"]) == 0, "unexpected producer positive")
    require(int(tuples["negative_tuple_count"]) == 0, "unexpected producer negative")
    require(int(tuples["unknown_tuple_count"]) == EXPECTED_PRODUCER_UNKNOWN, "unknown count drift")
    require(len(tuples["untested_tuples"]) == 1, "untested tuple count drift")
    require(low["records"] == [], "unexpected low consumer result")

    producer_keys: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for record in tuples["records"]:
        key = (
            tuple(map(int, record["parent_template_vector"])),
            tuple(map(int, record["separator_class_tuple"])),
        )
        require(key not in producer_keys, f"duplicate producer tuple: {key}")
        producer_keys.add(key)
        require(record["terminal_status"] == "UNKNOWN", f"producer status drift: {key}")
        for branch_name in ("primary", "fallback"):
            branch = record.get(branch_name)
            if not isinstance(branch, dict):
                continue
            require(branch["status"] == "UNKNOWN", f"branch status drift: {key}/{branch_name}")
            for field in (
                "selected_body_indices",
                "selected_modes",
                "allocation_tuple",
                "separator_class_tuple",
            ):
                require(field not in branch, f"censored branch leaked {field}: {key}")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e116_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e116_check_e100")
    e101 = source_module(E101_RUNNER, "zmd_e116_check_e101")
    e114 = source_module(E114_RUNNER, "zmd_e116_check_e114")
    e115 = source_module(E115_RUNNER, "zmd_e116_check_e115")
    e116 = source_module(RUNNER, "zmd_e116_check_runner")
    restricted = e100.build_restricted_context(e095)
    language = e115.load_language(restricted)
    targets = e116.load_targets(language)
    all_keys = {
        (
            tuple(target["parent_template_vector"]),
            tuple(target["separator_class_tuple"]),
        )
        for target in targets
    }
    require(len(all_keys) == EXPECTED_TUPLE_COUNT, "target-key count drift")
    untested_record = tuples["untested_tuples"][0]
    untested_key = (
        tuple(map(int, untested_record["parent_template_vector"])),
        tuple(map(int, untested_record["separator_class_tuple"])),
    )
    require(untested_key in all_keys - producer_keys, "untested tuple identity drift")
    require(len(all_keys - producer_keys) == 1, "producer omission set drift")

    bundle = e116.build_tuple_model(
        e095=e095,
        e101=e101,
        e115=e115,
        restricted=restricted,
        language=language,
        vector=untested_key[0],
        class_tuple=untested_key[1],
    )
    supplement = e114.solve_bundle(
        e095=e095,
        bundle=bundle,
        seconds=30.0,
        seed=116999,
        profile="one_worker_pseudo_cost",
    )
    supplement["parent_template_vector"] = list(untested_key[0])
    supplement["separator_class_tuple_fixed"] = list(untested_key[1])
    supplement["truth_boundary"] = (
        "Fresh execution of the one E116 tuple not attempted under the producer's "
        "total budget. UNKNOWN remains local; a terminal result applies only to this tuple."
    )
    dump_exclusive(SUPPLEMENT, supplement)

    status = str(supplement["status"])
    if status == "INFEASIBLE":
        classification = "ELEVEN_PRODUCER_UNKNOWNS_ONE_SUPPLEMENTAL_NEGATIVE"
        decision = "PRESERVE_ELEVEN_UNKNOWNS_AND_PROMOTE_ONE_TUPLE_NOGOOD"
    elif status in {"OPTIMAL", "FEASIBLE"}:
        classification = "ONE_SUPPLEMENTAL_HIGH_TUPLE_WITNESS_FOUND"
        decision = "SEND_SUPPLEMENTAL_HIGH_ALLOCATION_TO_X42_LOW"
    else:
        require(status == "UNKNOWN", f"unexpected supplemental status: {status}")
        classification = "ALL_TWELVE_LOW_CARDINALITY_TUPLES_CENSORED"
        decision = "RETIRE_SEPARATOR_CLASS_FIXATION_AS_PRIMARY_DISCRIMINATOR"

    combined_statuses = [
        {
            "parent_template_vector": list(key[0]),
            "separator_class_tuple": list(key[1]),
            "status": "UNKNOWN",
            "source": "producer",
        }
        for key in sorted(producer_keys)
    ]
    combined_statuses.append(
        {
            "parent_template_vector": list(untested_key[0]),
            "separator_class_tuple": list(untested_key[1]),
            "status": status,
            "source": "supplement",
        }
    )

    payload = {
        "schema": "zmd_e116_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": classification,
        "artifact_records": artifact_records,
        "producer_tested_tuple_count": EXPECTED_PRODUCER_TESTED,
        "producer_unknown_tuple_count": EXPECTED_PRODUCER_UNKNOWN,
        "supplemental_tuple": {
            "path": str(SUPPLEMENT.relative_to(ROOT)),
            "sha256": sha256(SUPPLEMENT),
            "parent_template_vector": list(untested_key[0]),
            "separator_class_tuple": list(untested_key[1]),
            "status": status,
            "elapsed_seconds": float(supplement["elapsed_seconds"]),
            "branches": int(supplement["branches"]),
            "conflicts": int(supplement["conflicts"]),
        },
        "all_target_statuses": combined_statuses,
        "decision": decision,
        "truth_boundary": (
            "Fixing separator class tuples did not alter body geometry freedom. "
            "Only terminal tuple results may become rules; UNKNOWN is non-evidence."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": classification,
                "supplemental_status": status,
                "supplemental_tuple": payload["supplemental_tuple"],
                "decision": decision,
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
