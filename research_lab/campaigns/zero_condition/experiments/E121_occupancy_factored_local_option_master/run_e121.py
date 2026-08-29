#!/usr/bin/env python3
"""E121: exact occupancy-factored local-option master."""

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
import traceback
import types
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E121_occupancy_factored_local_option_master/run-001"
)
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
E115_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E115_separator_template_state_full_consumer/run_e115.py"
)
E117_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E117_high_geometry_local_front_benders/run_e117.py"
)
E118_CUTS = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E118_solver_diverse_local_front_benders/run-001/"
    "MERGED_LOCAL_FRONT_BLOCKER_CUTS.json"
)
E118_CHECK = E118_CUTS.with_name("ARTIFACT_CHECK.json")
E120_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E120_integrated_local_option_master/run_e120.py"
)
E120_DURABLE = E120_RUNNER.with_name("RESULT.txt")
E120_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E120_integrated_local_option_master/run-002/RESULT.json"
)
E120_ENCODING = E120_RESULT.with_name("ENCODING_AUDIT.json")
E120_CHECK = E120_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E114_RUNNER: "e893bdc7df70ce93f66c3976a06e3fd15e2d81b492fd2463b9d17cec4cd16e5d",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E117_RUNNER: "ff51200bdec11733a27f3a82ffd63dc49a193e36fb1573f7c33d8a8b57d2f3f2",
    E118_CUTS: "93b4a05a9a19c2876cd9146f86ce6cbd11ee6a1923a6fed87f22b29ca5710375",
    E118_CHECK: "891d8ec1b41ac1ce178fb8345e748f51833d0279a8681993638e9db6fcbc813b",
    E120_RUNNER: "92b9c0a01b1076e47965e6f4d32a3e1d323b64fdf4c75666db1f3730bb7901b0",
    E120_DURABLE: "c4ada544d70b0b5050e55cc51a4c3dba33aab9244059b59eb337743877802a0f",
    E120_RESULT: "f9218f63300dd6f24bdb10668c6944a3fbd1edf7d9ba30d421660f12c2e0eb60",
    E120_ENCODING: "102e0e9b5f80548d3f013ec6a67bce774b8753bf9f4ee78f29ae4c3fb3a060ed",
    E120_CHECK: "1569314f562f769771a92a91e370e937a5d14507fc0bedc3903605d92b858e55",
}

EXPECTED_CANDIDATE_COUNT = 1205
EXPECTED_OPTION_COUNT = 9808
EXPECTED_OPEN_VECTOR_COUNT = 25
EXPECTED_EXPANDED_DYNAMIC_TERMS = 4_548_696


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            default=str,
        )
    )


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
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
            f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>",
            "exec",
            dont_inherit=True,
        ),
        module.__dict__,
    )
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E121 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E121 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E121 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }
    e120 = load_json(E120_RESULT)
    if e120.get("verdict") != "INTEGRATED_LOCAL_OPTION_MASTER_CENSORED":
        raise RuntimeError("E121 E120 verdict drift")
    if e120.get("decision") != "CHANGE_GEOMETRY_REPRESENTATION_OR_SKELETON":
        raise RuntimeError("E121 E120 decision drift")
    encoding = load_json(E120_ENCODING)
    if int(encoding.get("dynamic_term_count", -1)) != EXPECTED_EXPANDED_DYNAMIC_TERMS:
        raise RuntimeError("E121 E120 dynamic-term count drift")
    check = load_json(E120_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "EXACT_LOCAL_OPTION_ENCODING_REPLAYED_BOTH_SOLVER_ARMS_CENSORED"
    ):
        raise RuntimeError("E121 E120 check drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def build_factored_model(
    *,
    e095: types.ModuleType,
    e117: types.ModuleType,
    language: Mapping[str, Any],
    options_by_global: Mapping[int, Sequence[Mapping[str, Any]]],
    add_redundant_cuts: bool,
) -> dict[str, Any]:
    master = e117.build_master(language)
    model = master["model"]
    rows = master["rows"]
    local_by_global = master["local_by_global"]
    fixed_solid = set(language["context"]["fixed_solid"])

    body_vars_by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for local_index, row in enumerate(rows):
        for value in row["body"]:
            body_vars_by_cell[value].append(master["body_vars"][local_index])

    relevant_cells = {
        value
        for options in options_by_global.values()
        for option in options
        for field in ("input_cells", "output_cells")
        for value in option[field]
        if e095.in_grid(value)
        and value not in fixed_solid
        and value in body_vars_by_cell
    }
    occupancy_vars: dict[tuple[int, int], Any] = {}
    occupancy_channel_term_count = 0
    maximum_occupancy_channel_support = 0
    for value in sorted(relevant_cells):
        coverers = body_vars_by_cell[value]
        variable = model.NewBoolVar(f"occupied_{value[0]}_{value[1]}")
        model.Add(variable == sum(coverers))
        occupancy_vars[value] = variable
        occupancy_channel_term_count += len(coverers)
        maximum_occupancy_channel_support = max(
            maximum_occupancy_channel_support, len(coverers)
        )

    option_vars_by_global: dict[int, list[Any]] = defaultdict(list)
    option_records: list[dict[str, Any]] = []
    front_constraint_count = 0
    front_occupancy_term_count = 0
    fixed_blocked_total = 0
    maximum_front_occupancy_terms = 0
    duplicate_front_cell_occurrence_count = 0
    grouped_class_key_distribution: Counter[int] = Counter()

    for global_index in sorted(options_by_global):
        local_index = local_by_global[global_index]
        body_var = master["body_vars"][local_index]
        for option_index, option in enumerate(options_by_global[global_index]):
            variable = model.NewBoolVar(f"local_option_{global_index}_{option_index}")
            option_vars_by_global[global_index].append(variable)
            grouped_class_key_distribution[len(option["class_keys"])] += 1
            record = {
                "global_row_index": int(global_index),
                "local_body_index": int(local_index),
                "option_index": int(option_index),
                "pose_index": int(option["pose_index"]),
                "need_in": int(option["need_in"]),
                "need_out": int(option["need_out"]),
                "input_cells": tuple(option["input_cells"]),
                "output_cells": tuple(option["output_cells"]),
                "class_keys": tuple(option["class_keys"]),
                "variable": variable,
            }
            option_records.append(record)
            for front_cells, required in (
                (record["input_cells"], int(record["need_in"])),
                (record["output_cells"], int(record["need_out"])),
            ):
                fixed_blocked = sum(
                    (not e095.in_grid(value)) or value in fixed_solid
                    for value in front_cells
                )
                dynamic_terms = [
                    occupancy_vars[value]
                    for value in front_cells
                    if value in occupancy_vars
                ]
                duplicate_front_cell_occurrence_count += len(front_cells) - len(
                    set(front_cells)
                )
                model.Add(
                    fixed_blocked + sum(dynamic_terms)
                    <= len(front_cells)
                    - int(required)
                    + len(front_cells) * (1 - variable)
                )
                front_constraint_count += 1
                front_occupancy_term_count += len(dynamic_terms)
                fixed_blocked_total += int(fixed_blocked)
                maximum_front_occupancy_terms = max(
                    maximum_front_occupancy_terms, len(dynamic_terms)
                )
        model.Add(sum(option_vars_by_global[global_index]) == body_var)

    if len(option_records) != EXPECTED_OPTION_COUNT:
        raise RuntimeError("E121 option count drift")
    if len(option_vars_by_global) != EXPECTED_CANDIDATE_COUNT:
        raise RuntimeError("E121 body-option link count drift")

    imported_cut_count = 0
    if add_redundant_cuts:
        packet = load_json(E118_CUTS)
        imported = e117.add_death_cuts(master=master, deaths=list(packet["cuts"]))
        imported_cut_count = len(imported)
        if imported_cut_count != int(packet["cut_count"]) or imported_cut_count != 587:
            raise RuntimeError("E121 redundant cut import drift")

    error = model.Validate()
    if error:
        raise RuntimeError(f"E121 factored model invalid: {error}")
    factored_terms = occupancy_channel_term_count + front_occupancy_term_count
    if factored_terms <= 0:
        raise RuntimeError("E121 factored term count is empty")
    return {
        **master,
        "occupancy_vars": occupancy_vars,
        "option_vars_by_global": dict(option_vars_by_global),
        "option_records": option_records,
        "encoding_audit": {
            "candidate_count": len(rows),
            "body_variable_count": len(master["body_vars"]),
            "occupancy_variable_count": len(occupancy_vars),
            "option_variable_count": len(option_records),
            "body_option_link_constraint_count": len(option_vars_by_global),
            "occupancy_channel_constraint_count": len(occupancy_vars),
            "occupancy_channel_term_count": occupancy_channel_term_count,
            "maximum_occupancy_channel_support": maximum_occupancy_channel_support,
            "front_constraint_count": front_constraint_count,
            "front_occupancy_term_count": front_occupancy_term_count,
            "maximum_front_occupancy_terms": maximum_front_occupancy_terms,
            "fixed_blocked_term_total": fixed_blocked_total,
            "duplicate_front_cell_occurrence_count": (
                duplicate_front_cell_occurrence_count
            ),
            "grouped_class_key_count_distribution": {
                str(key): int(value)
                for key, value in sorted(grouped_class_key_distribution.items())
            },
            "expanded_dynamic_term_count": EXPECTED_EXPANDED_DYNAMIC_TERMS,
            "factored_dynamic_term_count": factored_terms,
            "dynamic_term_reduction_ratio": (
                EXPECTED_EXPANDED_DYNAMIC_TERMS / factored_terms
            ),
            "redundant_cut_count": imported_cut_count,
            "model_variable_count": len(model.Proto().variables),
            "model_constraint_count": len(model.Proto().constraints),
            "truth_boundary": (
                "For every relevant cell, occupancy equals the at-most-one sum of "
                "body selections covering that cell. Option rows use the same cell "
                "occurrence multiplicity as E120's expanded coefficients."
            ),
        },
    }


def run(
    *,
    run_dir: Path,
    primary_seconds: float,
    fallback_seconds: float,
    high_primary_seconds: float,
    high_fallback_seconds: float,
    low_seconds: float,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E121 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e121_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e121_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e121_source_e101")
    e114 = source_module(E114_RUNNER, "zmd_e121_source_e114")
    e115 = source_module(E115_RUNNER, "zmd_e121_source_e115")
    e117 = source_module(E117_RUNNER, "zmd_e121_source_e117")
    e120 = source_module(E120_RUNNER, "zmd_e121_source_e120")

    language = e117.build_language(e095=e095, e100=e100, e115=e115)
    options_by_global = e117.precompute_options(e095=e095, language=language)
    if len(language["rows"]) != EXPECTED_CANDIDATE_COUNT:
        raise RuntimeError("E121 candidate count drift")
    if len(language["open_vectors"]) != EXPECTED_OPEN_VECTOR_COUNT:
        raise RuntimeError("E121 open-vector count drift")
    if sum(len(values) for values in options_by_global.values()) != EXPECTED_OPTION_COUNT:
        raise RuntimeError("E121 option count drift")

    primary_model = build_factored_model(
        e095=e095,
        e117=e117,
        language=language,
        options_by_global=options_by_global,
        add_redundant_cuts=False,
    )
    encoding_path = run_dir / "ENCODING_AUDIT.json"
    dump_exclusive(
        encoding_path,
        {
            "schema": "zmd_e121_occupancy_factored_encoding_audit_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            **primary_model["encoding_audit"],
        },
    )
    primary = e120.solve_integrated(
        integrated=primary_model,
        profile="one_worker_pseudo_cost",
        seconds=primary_seconds,
        seed=121100,
    )
    primary_path = run_dir / "PRIMARY_RESULT.json"
    dump_exclusive(primary_path, primary)

    terminal = primary
    terminal_path = primary_path
    fallback = None
    fallback_path = run_dir / "FALLBACK_RESULT.json"
    if primary["status"] == "UNKNOWN":
        fallback_model = build_factored_model(
            e095=e095,
            e117=e117,
            language=language,
            options_by_global=options_by_global,
            add_redundant_cuts=True,
        )
        fallback = e120.solve_integrated(
            integrated=fallback_model,
            profile="multiworker_automatic",
            seconds=fallback_seconds,
            seed=121300,
        )
        dump_exclusive(fallback_path, fallback)
        terminal = fallback
        terminal_path = fallback_path

    consumer = None
    if terminal["status"] in {"OPTIMAL", "FEASIBLE"}:
        consumer = e120.consume_geometry(
            run_dir=run_dir,
            e095=e095,
            e101=e101,
            e114=e114,
            e117=e117,
            language=language,
            options_by_global=options_by_global,
            selected_globals=set(map(int, terminal["selected_global_row_indices"])),
            high_primary_seconds=high_primary_seconds,
            high_fallback_seconds=high_fallback_seconds,
            low_seconds=low_seconds,
        )

    combined = consumer["combined"] if consumer is not None else None
    high = consumer["high"] if consumer is not None else None
    if combined is not None:
        verdict = "OCCUPANCY_FACTORED_MASTER_REACHES_219_BODY_NATIVE_FRONT_WITNESS"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif high is not None and high["status"] in {"OPTIMAL", "FEASIBLE"}:
        verdict = "OCCUPANCY_FACTORED_GEOMETRY_HAS_FULL_HIGH_WITNESS"
        decision = "CONTINUE_ONLY_X42_LOW_ALLOCATION_HANDSHAKE"
    elif consumer is not None:
        verdict = "OCCUPANCY_FACTORED_GEOMETRY_FOUND_FULL_CLASS_NOT_PAIRED"
        decision = "FREEZE_GEOMETRY_AND_DECOMPOSE_GLOBAL_CLASS_ASSIGNMENT"
    elif terminal["status"] == "INFEASIBLE":
        verdict = "OPEN_X42_LOCAL_OPTION_LANGUAGE_INFEASIBLE"
        decision = "RETIRE_SOURCE_STABLE_X42_SUFFICIENT_CONSTRUCTOR"
    else:
        verdict = "OCCUPANCY_FACTORED_LOCAL_OPTION_MASTER_CENSORED"
        decision = "RUN_SPATIAL_COLLAR_AUDIT_OR_SWITCH_SKELETON"

    result = {
        "schema": "zmd_e121_occupancy_factored_local_option_master_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "primary_profile": "one_worker_pseudo_cost",
            "primary_seconds": primary_seconds,
            "fallback_profile": "multiworker_automatic_with_587_redundant_cuts",
            "fallback_seconds": fallback_seconds,
            "high_primary_seconds": high_primary_seconds,
            "high_fallback_seconds": high_fallback_seconds,
            "low_seconds": low_seconds,
            "source_isolated_helpers": True,
        },
        "encoding": {
            "path": display(encoding_path),
            "sha256": sha256_file(encoding_path),
            **primary_model["encoding_audit"],
        },
        "primary": {
            "path": display(primary_path),
            "sha256": sha256_file(primary_path),
            "status": primary["status"],
            "elapsed_seconds": primary["elapsed_seconds"],
            "branches": primary["branches"],
            "conflicts": primary["conflicts"],
            "selected_body_count": primary.get("selected_body_count", 0),
        },
        "fallback": (
            {
                "path": display(fallback_path),
                "sha256": sha256_file(fallback_path),
                "status": fallback["status"],
                "elapsed_seconds": fallback["elapsed_seconds"],
                "branches": fallback["branches"],
                "conflicts": fallback["conflicts"],
                "selected_body_count": fallback.get("selected_body_count", 0),
                "redundant_cut_count": fallback["encoding_audit"][
                    "redundant_cut_count"
                ],
            }
            if fallback is not None
            else None
        ),
        "terminal": {
            "path": display(terminal_path),
            "sha256": sha256_file(terminal_path),
            "status": terminal["status"],
            "profile": terminal["profile"],
            "selected_body_count": terminal.get("selected_body_count", 0),
            "selected_body_digest": terminal.get("selected_body_digest"),
            "separator_template_vector": terminal.get("separator_template_vector"),
        },
        "consumer": consumer,
        "truth_boundary": (
            "Cell occupancy channeling is algebraically equivalent to E120's expanded "
            "body coefficients under the existing body nonoverlap constraints. Local "
            "option existence still omits global class totals; UNKNOWN proves no absence."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--primary-seconds", type=float, default=90.0)
    parser.add_argument("--fallback-seconds", type=float, default=90.0)
    parser.add_argument("--high-primary-seconds", type=float, default=25.0)
    parser.add_argument("--high-fallback-seconds", type=float, default=25.0)
    parser.add_argument("--low-seconds", type=float, default=30.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            primary_seconds=float(args.primary_seconds),
            fallback_seconds=float(args.fallback_seconds),
            high_primary_seconds=float(args.high_primary_seconds),
            high_fallback_seconds=float(args.high_fallback_seconds),
            low_seconds=float(args.low_seconds),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "encoding": {
                        "occupancy_variable_count": result["encoding"][
                            "occupancy_variable_count"
                        ],
                        "expanded_dynamic_term_count": result["encoding"][
                            "expanded_dynamic_term_count"
                        ],
                        "factored_dynamic_term_count": result["encoding"][
                            "factored_dynamic_term_count"
                        ],
                        "dynamic_term_reduction_ratio": result["encoding"][
                            "dynamic_term_reduction_ratio"
                        ],
                    },
                    "primary": result["primary"],
                    "fallback": result["fallback"],
                    "terminal": result["terminal"],
                    "consumer": result["consumer"],
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
            "schema": "zmd_e121_execution_failure_v1",
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
