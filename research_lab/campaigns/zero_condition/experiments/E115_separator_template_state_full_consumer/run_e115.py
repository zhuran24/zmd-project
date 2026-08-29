#!/usr/bin/env python3
"""E115: full x42-high consumer conditioned on 27 separator template states."""

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
    "E115_separator_template_state_full_consumer/run-001"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"
E101_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E101_x42_allocation_handshake/run_e101.py"
E101_BODY = ROOT / "research_lab/local/zero_condition/E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
E103_RUN = ROOT / "research_lab/local/zero_condition/E103_high_side_interface_capacity_audit/run-003"
E103_RESULT = E103_RUN / "RESULT.json"
E103_CHECK = E103_RUN / "ARTIFACT_CHECK.json"
E103_LIVE = E103_RUN / "LIVE_HIGH_CANDIDATES.json"
E110_RUN = ROOT / "research_lab/local/zero_condition/E110_explicit_separator_template_duty_atlas/run-001"
E110_PROJECTION = E110_RUN / "SEPARATOR_TEMPLATE_PROJECTION.json"
E110_CHECK = E110_RUN / "ARTIFACT_CHECK.json"
E112_RUN = ROOT / "research_lab/local/zero_condition/E112_fixed_separator_class_state_closure/run-001"
E112_RESULT = E112_RUN / "RESULT.json"
E112_MANIFEST = E112_RUN / "SEPARATOR_CLASS_ATLAS_MANIFEST.json"
E112_CHECK = E112_RUN / "ARTIFACT_CHECK.json"
E114_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E114_e110_fixed_geometry_direct_consumer/run_e114.py"
E114_DURABLE = E114_RUNNER.with_name("RESULT.txt")
E114_RUN = ROOT / "research_lab/local/zero_condition/E114_e110_fixed_geometry_direct_consumer/run-001"
E114_RESULT = E114_RUN / "RESULT.json"
E114_CHECK = E114_RUN / "ARTIFACT_CHECK.json"
E114_DIAGNOSTICS = E114_RUN / "FIXED_GEOMETRY_DEATH_DIAGNOSTICS.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E103_RESULT: "6fefd59e3b8c5551501a2504e9c620bb6cc5468ac5847b92baa20a8ec6e6a32c",
    E103_CHECK: "63ba0d4085263d12c153db0f639bfd984f9bfd373de0b9828eeaf6e94f98850d",
    E103_LIVE: "ebf0c34b174df7036cf6c4bf2f3283dd4ea303998f62520cbd0c74d70aebfd08",
    E110_PROJECTION: "73570c931c8e8c053ec5a17feaa821e4e69511443882eac01110b470a6537413",
    E110_CHECK: "4b25595170b280f34951f563e61c5a17de46e1cc6b6afbfa97ee7e9421b17bf6",
    E112_RESULT: "da64e4a66ff0826c1b9aa56b69fda4fe7855739acc60e853522241dc5bd9fa0e",
    E112_MANIFEST: "45767f5f1a00d051701e1bd6787a77a813e23d1958652c632dbfea336113db2a",
    E112_CHECK: "cdbae6428ba1514646e12836de069b26104e1872f7356b63fb1bdeb4c34e5e03",
    E114_RUNNER: "e893bdc7df70ce93f66c3976a06e3fd15e2d81b492fd2463b9d17cec4cd16e5d",
    E114_DURABLE: "03482af4eabbd4cc395807791e43817aab4f9f19ed7365433ef537ceba6583f1",
    E114_RESULT: "58348a482fb4936aca55d06d161e49804ee7e3c032544a64d97a5b5ceee46d22",
    E114_CHECK: "36b224f752e05e92e58a0d161e8d59e3dd59595c290abb55f896a2a29d471aef",
    E114_DIAGNOSTICS: "a8e0f73fd99efb63e5220a2b4137700255d95e30a27c3a2060d71e06df99ed12",
}

TEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")
HIGH_TEMPLATE_COUNTS = {"manufacturing_3x3": 10, "manufacturing_5x5": 6, "manufacturing_6x4": 10}
LOW_TEMPLATE_COUNTS = {"manufacturing_3x3": 43, "manufacturing_5x5": 11, "manufacturing_6x4": 11}
EXPECTED_CLASS_ORDER = (
    ("B", "manufacturing_3x3", 1, 1),
    ("B", "manufacturing_3x3", 1, 2),
    ("B", "manufacturing_3x3", 2, 1),
    ("B", "manufacturing_5x5", 1, 1),
    ("B", "manufacturing_5x5", 1, 2),
    ("B", "manufacturing_6x4", 3, 1),
    ("B", "manufacturing_6x4", 4, 1),
    ("B", "manufacturing_6x4", 5, 1),
)
EXPECTED_STATE_COUNT = 27
EXPECTED_POSITIVE_SEPARATOR_STATES = 350
EXPECTED_LIVE_COUNT = 1205
EXPECTED_GROUP_COUNTS = {"low": 812, "separator": 154, "high": 239}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False, default=str) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return completed.stdout.strip()


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def source_module(path: Path, name: str, package: str | None = None) -> types.ModuleType:
    raw = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = package if package is not None else name.rpartition(".")[0]
    module.__loader__ = None
    sys.modules[name] = module
    exec(compile(raw, f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>", "exec", dont_inherit=True), module.__dict__)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E115 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E115 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E115 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}
    if load_json(E103_CHECK).get("status") != "PASS":
        raise RuntimeError("E115 E103 check is not PASS")
    if load_json(E110_CHECK).get("status") != "PASS":
        raise RuntimeError("E115 E110 check is not PASS")
    manifest = load_json(E112_MANIFEST)
    if manifest.get("complete") is not True or int(manifest.get("summary", {}).get("positive_state_count", -1)) != EXPECTED_POSITIVE_SEPARATOR_STATES:
        raise RuntimeError("E115 E112 manifest drift")
    if load_json(E112_CHECK).get("status") != "PASS":
        raise RuntimeError("E115 E112 check is not PASS")
    if load_json(E114_CHECK).get("status") != "PASS":
        raise RuntimeError("E115 E114 check is not PASS")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def template_vector_for_state(state: tuple[int, ...], class_keys: tuple[tuple[str, str, int, int], ...]) -> tuple[int, int, int]:
    return tuple(sum(int(state[index]) for index, key in enumerate(class_keys) if key[1] == template) for template in TEMPLATES)


def load_language(restricted: Mapping[str, Any]) -> dict[str, Any]:
    context = restricted["base"]
    class_keys = tuple(sorted(key for key in context["class_counts"] if key[0] == "B"))
    if class_keys != EXPECTED_CLASS_ORDER:
        raise RuntimeError(f"E115 class order drift: {class_keys}")
    live_payload = load_json(E103_LIVE)
    if int(live_payload.get("candidate_count", -1)) != EXPECTED_LIVE_COUNT:
        raise RuntimeError("E115 E103 live count drift")
    group_by_global: dict[int, str] = {}
    for record in live_payload["candidates"]:
        global_index = int(record["global_row_index"])
        bbox = record["bbox"]
        if int(bbox["max_y"]) <= 59:
            group = "low"
        elif int(bbox["min_y"]) > 59:
            group = "high"
        else:
            group = "separator"
        if global_index in group_by_global:
            raise RuntimeError("E115 live global-row collision")
        group_by_global[global_index] = group
    if dict(Counter(group_by_global.values())) != EXPECTED_GROUP_COUNTS:
        raise RuntimeError("E115 E103 group count drift")

    projection = load_json(E110_PROJECTION)
    vector_records = list(projection["vectors"])
    if len(vector_records) != EXPECTED_STATE_COUNT:
        raise RuntimeError("E115 E110 vector count drift")
    vectors = {tuple(map(int, row["vector"])) for row in vector_records}
    if len(vectors) != EXPECTED_STATE_COUNT:
        raise RuntimeError("E115 E110 vector identity drift")

    manifest = load_json(E112_MANIFEST)
    positive_states = [tuple(map(int, state)) for state in manifest["positive_states"]]
    if len(positive_states) != EXPECTED_POSITIVE_SEPARATOR_STATES or len(set(positive_states)) != len(positive_states):
        raise RuntimeError("E115 E112 positive-state identity drift")
    allowed_by_vector: dict[tuple[int, int, int], list[tuple[int, ...]]] = defaultdict(list)
    for state in positive_states:
        if len(state) != len(class_keys):
            raise RuntimeError("E115 separator state width drift")
        allowed_by_vector[template_vector_for_state(state, class_keys)].append(state)
    if set(allowed_by_vector) != vectors:
        raise RuntimeError("E115 separator class/template coverage drift")
    expected_counts = manifest["summary"]["positive_count_by_template_vector"]
    for vector, states in allowed_by_vector.items():
        key = "/".join(map(str, vector))
        if len(states) != int(expected_counts[key]):
            raise RuntimeError(f"E115 positive-state count drift: {key}")

    death = load_json(E114_DIAGNOSTICS)
    zero_count_by_vector = {
        tuple(map(int, row["separator_template_vector"])): int(row["zero_domain_body_count"])
        for row in death["records"]
    }
    if set(zero_count_by_vector) != vectors:
        raise RuntimeError("E115 E114 ordering vector drift")
    representative_by_vector = {
        tuple(map(int, row["vector"])): set(map(int, row["witness"]["selected_global_indices"]))
        for row in vector_records
    }
    ordered_vectors = sorted(vectors, key=lambda vector: (zero_count_by_vector[vector], vector))
    return {
        "class_keys": class_keys,
        "global_class_counts": {key: int(context["class_counts"][key]) for key in class_keys},
        "group_by_global": group_by_global,
        "live_global_indices": set(group_by_global),
        "allowed_by_vector": allowed_by_vector,
        "representative_by_vector": representative_by_vector,
        "zero_count_by_vector": zero_count_by_vector,
        "ordered_vectors": ordered_vectors,
    }


def build_state_model(
    *,
    e095: types.ModuleType,
    e101: types.ModuleType,
    restricted: Mapping[str, Any],
    language: Mapping[str, Any],
    vector: tuple[int, int, int],
) -> dict[str, Any]:
    hints = set(language["representative_by_vector"][vector])
    bundle = e101.build_side_model(
        e095=e095,
        restricted=restricted,
        side="high",
        template_counts=HIGH_TEMPLATE_COUNTS,
        body_hint_indices=hints,
        fixed_allocation=None,
    )
    bundle["base_context"] = restricted["base"]
    live = language["live_global_indices"]
    group_by_global = language["group_by_global"]
    rows = bundle["rows"]
    for local_index, row in enumerate(rows):
        if int(row["global_row_index"]) not in live:
            bundle["model"].Add(bundle["body_vars"][local_index] == 0)

    for template_index, template in enumerate(TEMPLATES):
        bundle["model"].Add(
            sum(
                bundle["body_vars"][local_index]
                for local_index, row in enumerate(rows)
                if group_by_global.get(int(row["global_row_index"])) == "separator"
                and str(row["template"]) == template
            )
            == int(vector[template_index])
        )

    sep_class_vars: list[Any] = []
    for class_index, class_key in enumerate(language["class_keys"]):
        variable = bundle["model"].NewIntVar(
            0,
            int(language["global_class_counts"][class_key]),
            f"separator_class_{class_index}",
        )
        sep_class_vars.append(variable)
        bundle["model"].Add(
            variable
            == sum(
                mode["variable"]
                for mode in bundle["mode_rows"]
                if tuple(mode["class_key"]) == class_key
                and group_by_global.get(int(mode["global_row_index"])) == "separator"
            )
        )
    allowed = [list(state) for state in language["allowed_by_vector"][vector]]
    bundle["model"].AddAllowedAssignments(sep_class_vars, allowed)
    error = bundle["model"].Validate()
    if error:
        raise RuntimeError(f"E115 state model invalid {vector}: {error}")
    bundle["separator_template_vector"] = vector
    bundle["separator_class_vars"] = sep_class_vars
    bundle["allowed_separator_state_count"] = len(allowed)
    bundle["live_body_variable_count"] = sum(int(row["global_row_index"]) in live for row in rows)
    return bundle


def solve_state(
    *,
    e095: types.ModuleType,
    e114: types.ModuleType,
    bundle: dict[str, Any],
    seconds: float,
    seed: int,
) -> dict[str, Any]:
    result = e114.solve_bundle(
        e095=e095,
        bundle=bundle,
        seconds=seconds,
        seed=seed,
        profile="multiworker_automatic",
    )
    result["separator_template_vector"] = list(bundle["separator_template_vector"])
    result["allowed_separator_state_count"] = int(bundle["allowed_separator_state_count"])
    result["live_body_variable_count"] = int(bundle["live_body_variable_count"])
    if result["status"] in {"OPTIMAL", "FEASIBLE"}:
        group_by_global = load_language_cache["group_by_global"]
        sep_tuple = [0] * len(bundle["class_keys"])
        for mode in result["selected_modes"]:
            if group_by_global.get(int(mode["global_row_index"])) == "separator":
                sep_tuple[bundle["class_keys"].index(tuple(mode["class_key"]))] += 1
        result["separator_class_tuple"] = sep_tuple
        if tuple(sep_tuple) not in set(load_language_cache["allowed_by_vector"][tuple(bundle["separator_template_vector"])]):
            raise RuntimeError("E115 positive separator class tuple escaped allowed atlas")
    return result


load_language_cache: dict[str, Any] = {}


def run(*, run_dir: Path, state_seconds: float, low_seconds: float, total_seconds: float) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E115 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(OPERATION_PROFILES, "src.preprocess.operation_profiles", package="src.preprocess")
    e095 = source_module(E095_RUNNER, "zmd_e115_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e115_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e115_source_e101")
    e114 = source_module(E114_RUNNER, "zmd_e115_source_e114")
    restricted = e100.build_restricted_context(e095)
    language = load_language(restricted)
    load_language_cache.clear()
    load_language_cache.update(language)

    started = time.monotonic()
    state_records: list[dict[str, Any]] = []
    low_records: list[dict[str, Any]] = []
    module_b: dict[str, Any] | None = None
    combined: dict[str, Any] | None = None
    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"
    low_hints = set(map(int, load_json(E101_BODY)["selected_body_indices"]))

    for rank, vector in enumerate(language["ordered_vectors"]):
        remaining = float(total_seconds) - (time.monotonic() - started)
        if remaining <= 1.0 or combined is not None:
            break
        bundle = build_state_model(
            e095=e095,
            e101=e101,
            restricted=restricted,
            language=language,
            vector=vector,
        )
        seconds = min(float(state_seconds), max(0.5, remaining - 0.25))
        high = solve_state(
            e095=e095,
            e114=e114,
            bundle=bundle,
            seconds=seconds,
            seed=115100 + rank,
        )
        state_record: dict[str, Any] = {
            "rank": rank,
            "separator_template_vector": list(vector),
            "representative_zero_domain_count": int(language["zero_count_by_vector"][vector]),
            "allowed_separator_state_count": int(bundle["allowed_separator_state_count"]),
            "high": high,
            "classification": (
                "STATE_FRONT_FEASIBLE"
                if high["status"] in {"OPTIMAL", "FEASIBLE"}
                else "STATE_FRONT_INFEASIBLE"
                if high["status"] == "INFEASIBLE"
                else "STATE_FRONT_CENSORED"
            ),
        }
        state_records.append(state_record)

        if high["status"] not in {"OPTIMAL", "FEASIBLE"}:
            continue
        remaining = float(total_seconds) - (time.monotonic() - started)
        if remaining <= 1.0:
            continue
        complement = e101.complement_allocation(
            language["class_keys"],
            language["global_class_counts"],
            list(map(int, high["allocation_tuple"])),
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
            seed=115500 + rank,
            profile="multiworker_automatic",
        )
        low_record = {
            "separator_template_vector": list(vector),
            "source_high_allocation_tuple": list(map(int, high["allocation_tuple"])),
            "low_complement_tuple": [int(complement[key]) for key in language["class_keys"]],
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
                high=high,
            )
            module_b = pair["module_b"]
            combined = pair["combined"]
            dump_exclusive(module_b_path, module_b)
            dump_exclusive(combined_path, combined)
            break

    state_path = run_dir / "STATE_CONSUMER_RESULTS.json"
    tested_vectors = {tuple(record["separator_template_vector"]) for record in state_records}
    untested_vectors = [list(vector) for vector in language["ordered_vectors"] if vector not in tested_vectors]
    dump_exclusive(
        state_path,
        {
            "schema": "zmd_e115_state_consumer_results_v1",
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "formal_state_count": EXPECTED_STATE_COUNT,
            "tested_state_count": len(state_records),
            "untested_state_vectors": untested_vectors,
            "positive_state_count": sum(record["high"]["status"] in {"OPTIMAL", "FEASIBLE"} for record in state_records),
            "negative_state_count": sum(record["high"]["status"] == "INFEASIBLE" for record in state_records),
            "unknown_state_count": sum(record["high"]["status"] == "UNKNOWN" for record in state_records),
            "records": state_records,
            "truth_boundary": "Exact negatives reject only named separator template states. UNKNOWN creates no rule.",
        },
    )
    low_path = run_dir / "LOW_COMPLEMENT_RESULTS.json"
    dump_exclusive(
        low_path,
        {
            "schema": "zmd_e115_low_complement_results_v1",
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "record_count": len(low_records),
            "records": low_records,
        },
    )

    positive_count = sum(record["high"]["status"] in {"OPTIMAL", "FEASIBLE"} for record in state_records)
    negative_count = sum(record["high"]["status"] == "INFEASIBLE" for record in state_records)
    unknown_count = sum(record["high"]["status"] == "UNKNOWN" for record in state_records)
    if combined is not None:
        verdict = "STATE_CONDITIONED_X42_REACHES_219_BODY_NATIVE_FRONT_WITNESS"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif positive_count > 0:
        verdict = "SEPARATOR_TEMPLATE_STATES_HAVE_HIGH_FRONT_WITNESSES_WITHOUT_PAIRED_LOW_YET"
        decision = "CONTINUE_ONLY_POSITIVE_STATE_ALLOCATION_HANDSHAKES"
    elif negative_count == EXPECTED_STATE_COUNT:
        verdict = "ALL_SEPARATOR_TEMPLATE_STATES_INFEASIBLE_IN_X42_HIGH_CONSUMER"
        decision = "RETIRE_SOURCE_STABLE_X42_SUFFICIENT_CONSTRUCTOR"
    else:
        verdict = "SEPARATOR_TEMPLATE_STATE_FULL_CONSUMER_CENSORED"
        decision = "REPLAY_ONLY_NAMED_UNKNOWN_STATES"

    result = {
        "schema": "zmd_e115_separator_template_state_full_consumer_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "state_seconds": state_seconds,
            "low_seconds": low_seconds,
            "total_seconds": total_seconds,
            "solver_profile": "multiworker_automatic",
            "state_order": "ascending_E114_representative_zero_domain_count_then_vector",
            "source_isolated_helpers": True,
        },
        "state_results": {
            "path": display(state_path),
            "sha256": sha256_file(state_path),
            "formal_count": EXPECTED_STATE_COUNT,
            "tested_count": len(state_records),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "unknown_count": unknown_count,
            "untested_count": len(untested_vectors),
        },
        "low_results": {
            "path": display(low_path),
            "sha256": sha256_file(low_path),
            "record_count": len(low_records),
            "positive_count": sum(record["low"]["status"] in {"OPTIMAL", "FEASIBLE"} for record in low_records),
            "negative_count": sum(record["low"]["status"] == "INFEASIBLE" for record in low_records),
            "unknown_count": sum(record["low"]["status"] == "UNKNOWN" for record in low_records),
        },
        "module_b_witness": ({"path": display(module_b_path), "sha256": sha256_file(module_b_path), "selected_body_count": module_b["selected_body_count"], "selected_assignment_digest": module_b["selected_assignment_digest"]} if module_b is not None else None),
        "combined_witness": ({"path": display(combined_path), "sha256": sha256_file(combined_path), "status": combined["status"], "selected_manufacturing_count": combined["selected_manufacturing_count"], "selected_assignment_digest": combined["selected_assignment_digest"]} if combined is not None else None),
        "total_elapsed_seconds": time.monotonic() - started,
        "truth_boundary": "State negatives are contextual to source-stable manufacturing-free x42, E103's exact live filter and fixed E092 skeleton. A state positive still requires an x42-low complement.",
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--state-seconds", type=float, default=7.0)
    parser.add_argument("--low-seconds", type=float, default=20.0)
    parser.add_argument("--total-seconds", type=float, default=270.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(run_dir=run_dir, state_seconds=float(args.state_seconds), low_seconds=float(args.low_seconds), total_seconds=float(args.total_seconds))
        result_path = run_dir / "RESULT.json"
        print(json.dumps({"verdict": result["verdict"], "decision": result["decision"], "state_results": result["state_results"], "low_results": result["low_results"], "combined_witness": result["combined_witness"] is not None, "total_elapsed_seconds": result["total_elapsed_seconds"], "result_path": display(result_path), "result_sha256": sha256_file(result_path)}, ensure_ascii=False, sort_keys=True), flush=True)
        return 0
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {"schema": "zmd_e115_execution_failure_v1", "created_at_utc": utc_now(), "status": "EXECUTION_FAILURE", "error": type(exc).__name__, "detail": str(exc), "traceback": traceback.format_exc(), "ledger_effect": "none"}
        if not failure_path.exists():
            dump_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
