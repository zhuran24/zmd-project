#!/usr/bin/env python3
"""E116: fix twelve low-cardinality separator class tuples in the full high consumer."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import types
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E116_low_cardinality_separator_tuple_discriminator/run-001"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"
E101_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E101_x42_allocation_handshake/run_e101.py"
E101_BODY = ROOT / "research_lab/local/zero_condition/E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
E114_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E114_e110_fixed_geometry_direct_consumer/run_e114.py"
E115_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E115_separator_template_state_full_consumer/run_e115.py"
E115_DURABLE = E115_RUNNER.with_name("RESULT.txt")
E115_SNAPSHOT = E115_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E115_RUN = ROOT / "research_lab/local/zero_condition/E115_separator_template_state_full_consumer/run-001"
E115_RESULT = E115_RUN / "RESULT.json"
E115_STATE_RESULTS = E115_RUN / "STATE_CONSUMER_RESULTS.json"
E115_UNKNOWN = E115_RUN / "UNKNOWN_TEMPLATE_STATES.json"
E115_CHECK = E115_RUN / "ARTIFACT_CHECK.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E114_RUNNER: "e893bdc7df70ce93f66c3976a06e3fd15e2d81b492fd2463b9d17cec4cd16e5d",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E115_DURABLE: "f00ce3db40e122baa8d491043033bc6bca2e0d797a89a367775275bc303a2588",
    E115_SNAPSHOT: "f80ea6d3f4c7f3facc2ee73051651447903eb518f7930fa0f4bcbd28ca348674",
    E115_RESULT: "f6b1e3e4ef29aadd7d865a97424c4379b828608a857a3893172c03c3b9497ef2",
    E115_STATE_RESULTS: "41f0560f5170d127fc7cbaeea379d47f70dd712f9eeb123e9b42a83148ae7a06",
    E115_UNKNOWN: "0cc243e76134ed53958d22c68a04a6067685b17620b6c1a7676e5ad7b12f0731",
    E115_CHECK: "7e76312570612dc299f73e7dec192fdaa19fc13dee28b958055146571955d76a",
}

EXPECTED_PARENT_STATE_COUNT = 5
EXPECTED_TUPLE_COUNT = 12
EXPECTED_CLASS_COUNT = 8
LOW_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 43,
    "manufacturing_5x5": 11,
    "manufacturing_6x4": 11,
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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
            f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>",
            "exec",
            dont_inherit=True,
        ),
        module.__dict__,
    )
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E116 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E116 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E116 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }
    result = load_json(E115_RESULT)
    check = load_json(E115_CHECK)
    packet = load_json(E115_UNKNOWN)
    if result.get("verdict") != "SEPARATOR_TEMPLATE_STATE_FULL_CONSUMER_CENSORED":
        raise RuntimeError("E116 E115 verdict drift")
    if check.get("status") != "PASS" or check.get("decision") != (
        "FIX_LOW_CARDINALITY_SEPARATOR_CLASS_TUPLES_FIRST"
    ):
        raise RuntimeError("E116 E115 checker drift")
    if int(packet.get("low_cardinality_state_count", -1)) != EXPECTED_PARENT_STATE_COUNT:
        raise RuntimeError("E116 parent-state count drift")
    if int(packet.get("low_cardinality_tuple_count", -1)) != EXPECTED_TUPLE_COUNT:
        raise RuntimeError("E116 tuple count drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def load_targets(language: Mapping[str, Any]) -> list[dict[str, Any]]:
    packet = load_json(E115_UNKNOWN)
    class_order = tuple(tuple(value) for value in packet["class_order"])
    if class_order != tuple(language["class_keys"]):
        raise RuntimeError("E116 class-order drift")
    targets: list[dict[str, Any]] = []
    for parent in packet["low_cardinality_states"]:
        vector = tuple(map(int, parent["separator_template_vector"]))
        source_states = {
            tuple(map(int, state))
            for state in parent["allowed_separator_class_states"]
        }
        expected_states = set(language["allowed_by_vector"][vector])
        if source_states != expected_states:
            raise RuntimeError(f"E116 allowed-state drift: {vector}")
        for tuple_rank, state in enumerate(sorted(source_states)):
            if len(state) != EXPECTED_CLASS_COUNT:
                raise RuntimeError("E116 tuple width drift")
            targets.append(
                {
                    "parent_template_vector": vector,
                    "separator_class_tuple": state,
                    "parent_allowed_tuple_count": len(source_states),
                    "representative_zero_domain_count": int(
                        parent["representative_zero_domain_count"]
                    ),
                    "tuple_rank_within_parent": tuple_rank,
                }
            )
    if len(targets) != EXPECTED_TUPLE_COUNT:
        raise RuntimeError("E116 flattened target count drift")
    targets.sort(
        key=lambda row: (
            int(row["parent_allowed_tuple_count"]),
            int(row["representative_zero_domain_count"]),
            row["parent_template_vector"],
            row["separator_class_tuple"],
        )
    )
    return targets


def build_tuple_model(
    *,
    e095: types.ModuleType,
    e101: types.ModuleType,
    e115: types.ModuleType,
    restricted: Mapping[str, Any],
    language: Mapping[str, Any],
    vector: tuple[int, int, int],
    class_tuple: tuple[int, ...],
) -> dict[str, Any]:
    bundle = e115.build_state_model(
        e095=e095,
        e101=e101,
        restricted=restricted,
        language=language,
        vector=vector,
    )
    if len(bundle["separator_class_vars"]) != len(class_tuple):
        raise RuntimeError("E116 separator tuple width drift")
    for variable, value in zip(
        bundle["separator_class_vars"],
        class_tuple,
        strict=True,
    ):
        bundle["model"].Add(variable == int(value))
    error = bundle["model"].Validate()
    if error:
        raise RuntimeError(f"E116 tuple model invalid {vector}/{class_tuple}: {error}")
    bundle["fixed_separator_class_tuple"] = class_tuple
    return bundle


def terminal_status(solve: Mapping[str, Any]) -> str:
    fallback = solve.get("fallback")
    if isinstance(fallback, Mapping):
        return str(fallback["status"])
    return str(solve["primary"]["status"])


def terminal_result(solve: Mapping[str, Any]) -> Mapping[str, Any]:
    fallback = solve.get("fallback")
    if isinstance(fallback, Mapping):
        return fallback
    return solve["primary"]


def solve_target(
    *,
    e095: types.ModuleType,
    e114: types.ModuleType,
    builder: Any,
    primary_seconds: float,
    fallback_seconds: float,
    seed: int,
) -> dict[str, Any]:
    return e114.solve_with_fallback(
        builder=builder,
        e095=e095,
        primary_seconds=primary_seconds,
        fallback_seconds=fallback_seconds,
        seed=seed,
    )


def run(
    *,
    run_dir: Path,
    primary_seconds: float,
    fallback_seconds: float,
    low_seconds: float,
    total_seconds: float,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E116 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e116_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e116_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e116_source_e101")
    e114 = source_module(E114_RUNNER, "zmd_e116_source_e114")
    e115 = source_module(E115_RUNNER, "zmd_e116_source_e115")
    restricted = e100.build_restricted_context(e095)
    language = e115.load_language(restricted)
    targets = load_targets(language)
    low_hints = set(map(int, load_json(E101_BODY)["selected_body_indices"]))

    started = time.monotonic()
    records: list[dict[str, Any]] = []
    low_records: list[dict[str, Any]] = []
    module_b: dict[str, Any] | None = None
    combined: dict[str, Any] | None = None
    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"

    for target_index, target in enumerate(targets):
        if combined is not None:
            break
        remaining = float(total_seconds) - (time.monotonic() - started)
        if remaining <= 1.0:
            break
        vector = tuple(target["parent_template_vector"])
        class_tuple = tuple(target["separator_class_tuple"])

        def builder(
            parent_vector: tuple[int, int, int] = vector,
            fixed_tuple: tuple[int, ...] = class_tuple,
        ) -> dict[str, Any]:
            return build_tuple_model(
                e095=e095,
                e101=e101,
                e115=e115,
                restricted=restricted,
                language=language,
                vector=parent_vector,
                class_tuple=fixed_tuple,
            )

        primary_budget = min(float(primary_seconds), max(0.5, remaining - 0.25))
        fallback_budget = min(
            float(fallback_seconds),
            max(0.0, remaining - primary_budget - 0.25),
        )
        solve = solve_target(
            e095=e095,
            e114=e114,
            builder=builder,
            primary_seconds=primary_budget,
            fallback_seconds=fallback_budget,
            seed=116100 + target_index,
        )
        terminal = terminal_result(solve)
        status = terminal_status(solve)
        if status in {"OPTIMAL", "FEASIBLE"}:
            selected_tuple = [0] * len(language["class_keys"])
            group_by_global = language["group_by_global"]
            for mode in terminal["selected_modes"]:
                if group_by_global.get(int(mode["global_row_index"])) != "separator":
                    continue
                class_index = language["class_keys"].index(tuple(mode["class_key"]))
                selected_tuple[class_index] += 1
            if selected_tuple != list(class_tuple):
                raise RuntimeError("E116 positive separator tuple replay drift")
            terminal["separator_class_tuple"] = selected_tuple

        record = {
            "target_index": target_index,
            "parent_template_vector": list(vector),
            "separator_class_tuple": list(class_tuple),
            "parent_allowed_tuple_count": int(target["parent_allowed_tuple_count"]),
            "representative_zero_domain_count": int(
                target["representative_zero_domain_count"]
            ),
            "primary": solve["primary"],
            "fallback": solve["fallback"],
            "terminal_status": status,
            "classification": (
                "TUPLE_FRONT_FEASIBLE"
                if status in {"OPTIMAL", "FEASIBLE"}
                else "TUPLE_FRONT_INFEASIBLE"
                if status == "INFEASIBLE"
                else "TUPLE_FRONT_CENSORED"
            ),
        }
        records.append(record)

        if status not in {"OPTIMAL", "FEASIBLE"}:
            continue
        remaining = float(total_seconds) - (time.monotonic() - started)
        if remaining <= 1.0:
            continue
        complement = e101.complement_allocation(
            language["class_keys"],
            language["global_class_counts"],
            list(map(int, terminal["allocation_tuple"])),
        )
        low_bundle = e101.build_side_model(
            e095=e095,
            restricted=restricted,
            side="low",
            template_counts=LOW_TEMPLATE_COUNTS,
            body_hint_indices=low_hints,
            fixed_allocation=complement,
        )
        low_bundle["base_context"] = restricted["base"]
        low = e114.solve_bundle(
            e095=e095,
            bundle=low_bundle,
            seconds=min(float(low_seconds), max(0.5, remaining - 0.25)),
            seed=116500 + target_index,
            profile="multiworker_automatic",
        )
        low_record = {
            "target_index": target_index,
            "parent_template_vector": list(vector),
            "separator_class_tuple": list(class_tuple),
            "high_allocation_tuple": list(map(int, terminal["allocation_tuple"])),
            "low_complement_tuple": [
                int(complement[key]) for key in language["class_keys"]
            ],
            "low": low,
            "classification": (
                "PAIRED_ALLOCATION"
                if low["status"] in {"OPTIMAL", "FEASIBLE"}
                else "ALLOCATION_REJECTED_BY_LOW"
                if low["status"] == "INFEASIBLE"
                else "LOW_COMPLEMENT_CENSORED"
            ),
        }
        low_records.append(low_record)
        if low["status"] in {"OPTIMAL", "FEASIBLE"}:
            pair = e101.combine_side_witnesses(
                e095=e095,
                restricted=restricted,
                low=low,
                high=terminal,
            )
            module_b = pair["module_b"]
            combined = pair["combined"]
            dump_exclusive(module_b_path, module_b)
            dump_exclusive(combined_path, combined)
            break

    tested_keys = {
        (
            tuple(record["parent_template_vector"]),
            tuple(record["separator_class_tuple"]),
        )
        for record in records
    }
    untested = [
        {
            "parent_template_vector": list(target["parent_template_vector"]),
            "separator_class_tuple": list(target["separator_class_tuple"]),
        }
        for target in targets
        if (
            tuple(target["parent_template_vector"]),
            tuple(target["separator_class_tuple"]),
        )
        not in tested_keys
    ]

    parent_records: list[dict[str, Any]] = []
    by_parent: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_parent[tuple(record["parent_template_vector"])].append(record)
    expected_by_parent = Counter(
        tuple(target["parent_template_vector"]) for target in targets
    )
    closed_parents: list[list[int]] = []
    positive_parents: list[list[int]] = []
    for parent in sorted(expected_by_parent):
        rows = by_parent.get(parent, [])
        statuses = [str(row["terminal_status"]) for row in rows]
        complete = len(rows) == int(expected_by_parent[parent])
        closed = complete and statuses and all(status == "INFEASIBLE" for status in statuses)
        positive = any(status in {"OPTIMAL", "FEASIBLE"} for status in statuses)
        if closed:
            closed_parents.append(list(parent))
        if positive:
            positive_parents.append(list(parent))
        parent_records.append(
            {
                "parent_template_vector": list(parent),
                "formal_tuple_count": int(expected_by_parent[parent]),
                "tested_tuple_count": len(rows),
                "positive_tuple_count": sum(
                    status in {"OPTIMAL", "FEASIBLE"} for status in statuses
                ),
                "negative_tuple_count": sum(
                    status == "INFEASIBLE" for status in statuses
                ),
                "unknown_tuple_count": sum(status == "UNKNOWN" for status in statuses),
                "complete": complete,
                "closed": closed,
            }
        )

    tuple_path = run_dir / "FIXED_TUPLE_RESULTS.json"
    dump_exclusive(
        tuple_path,
        {
            "schema": "zmd_e116_fixed_tuple_results_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "formal_tuple_count": EXPECTED_TUPLE_COUNT,
            "tested_tuple_count": len(records),
            "untested_tuples": untested,
            "positive_tuple_count": sum(
                record["terminal_status"] in {"OPTIMAL", "FEASIBLE"}
                for record in records
            ),
            "negative_tuple_count": sum(
                record["terminal_status"] == "INFEASIBLE" for record in records
            ),
            "unknown_tuple_count": sum(
                record["terminal_status"] == "UNKNOWN" for record in records
            ),
            "records": records,
            "parent_records": parent_records,
            "closed_parent_template_vectors": closed_parents,
            "positive_parent_template_vectors": positive_parents,
            "tuple_digest": stable_digest(
                [
                    (
                        record["parent_template_vector"],
                        record["separator_class_tuple"],
                        record["terminal_status"],
                    )
                    for record in records
                ]
            ),
            "truth_boundary": (
                "Each exact negative rejects only one separator class tuple. A parent "
                "state closes only if every one of its exact E112-positive tuples is negative."
            ),
        },
    )
    low_path = run_dir / "LOW_COMPLEMENT_RESULTS.json"
    dump_exclusive(
        low_path,
        {
            "schema": "zmd_e116_low_complement_results_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "record_count": len(low_records),
            "records": low_records,
        },
    )

    positive_count = sum(
        record["terminal_status"] in {"OPTIMAL", "FEASIBLE"} for record in records
    )
    negative_count = sum(
        record["terminal_status"] == "INFEASIBLE" for record in records
    )
    unknown_count = sum(record["terminal_status"] == "UNKNOWN" for record in records)
    if combined is not None:
        verdict = "FIXED_SEPARATOR_TUPLE_REACHES_219_BODY_NATIVE_FRONT_WITNESS"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif positive_count > 0:
        verdict = "LOW_CARDINALITY_SEPARATOR_TUPLES_HAVE_HIGH_FRONT_WITNESSES"
        decision = "CONTINUE_ONLY_POSITIVE_TUPLE_ALLOCATION_HANDSHAKES"
    elif negative_count == EXPECTED_TUPLE_COUNT:
        verdict = "FIVE_LOW_CARDINALITY_TEMPLATE_STATES_CLOSED"
        decision = "CONTINUE_NEXT_LOWEST_CARDINALITY_UNKNOWN_TEMPLATE_STATES"
    else:
        verdict = "LOW_CARDINALITY_SEPARATOR_TUPLE_DISCRIMINATOR_CENSORED"
        decision = "REPLAY_ONLY_NAMED_UNKNOWN_TUPLES"

    result = {
        "schema": "zmd_e116_low_cardinality_separator_tuple_discriminator_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "primary_seconds": primary_seconds,
            "fallback_seconds": fallback_seconds,
            "low_seconds": low_seconds,
            "total_seconds": total_seconds,
            "primary_profile": "one_worker_pseudo_cost",
            "fallback_profile": "multiworker_automatic",
            "source_isolated_helpers": True,
        },
        "tuple_results": {
            "path": display(tuple_path),
            "sha256": sha256_file(tuple_path),
            "formal_count": EXPECTED_TUPLE_COUNT,
            "tested_count": len(records),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "unknown_count": unknown_count,
            "untested_count": len(untested),
            "closed_parent_count": len(closed_parents),
            "closed_parent_template_vectors": closed_parents,
            "positive_parent_template_vectors": positive_parents,
        },
        "low_results": {
            "path": display(low_path),
            "sha256": sha256_file(low_path),
            "record_count": len(low_records),
            "positive_count": sum(
                record["low"]["status"] in {"OPTIMAL", "FEASIBLE"}
                for record in low_records
            ),
            "negative_count": sum(
                record["low"]["status"] == "INFEASIBLE" for record in low_records
            ),
            "unknown_count": sum(
                record["low"]["status"] == "UNKNOWN" for record in low_records
            ),
        },
        "module_b_witness": (
            {
                "path": display(module_b_path),
                "sha256": sha256_file(module_b_path),
                "selected_body_count": module_b["selected_body_count"],
                "selected_assignment_digest": module_b["selected_assignment_digest"],
            }
            if module_b is not None
            else None
        ),
        "combined_witness": (
            {
                "path": display(combined_path),
                "sha256": sha256_file(combined_path),
                "status": combined["status"],
                "selected_manufacturing_count": combined[
                    "selected_manufacturing_count"
                ],
                "selected_assignment_digest": combined[
                    "selected_assignment_digest"
                ],
            }
            if combined is not None
            else None
        ),
        "total_elapsed_seconds": time.monotonic() - started,
        "truth_boundary": (
            "The twelve tuples cover only five E115 UNKNOWN template states. Tuple "
            "negatives are contextual to source-stable x42, E103 live rows and fixed E092."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--primary-seconds", type=float, default=10.0)
    parser.add_argument("--fallback-seconds", type=float, default=10.0)
    parser.add_argument("--low-seconds", type=float, default=20.0)
    parser.add_argument("--total-seconds", type=float, default=260.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            primary_seconds=float(args.primary_seconds),
            fallback_seconds=float(args.fallback_seconds),
            low_seconds=float(args.low_seconds),
            total_seconds=float(args.total_seconds),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "tuple_results": result["tuple_results"],
                    "low_results": result["low_results"],
                    "combined_witness": result["combined_witness"] is not None,
                    "total_elapsed_seconds": result["total_elapsed_seconds"],
                    "result_path": display(result_path),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e116_execution_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not failure_path.exists():
            dump_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
