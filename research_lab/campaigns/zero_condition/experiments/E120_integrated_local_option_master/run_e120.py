#!/usr/bin/env python3
"""E120: exact geometry + local-option existence master."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
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
    "E120_integrated_local_option_master/run-001"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition/run_e095.py"
)
E095_MODULE_A = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/MODULE_A_RESULT.json"
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
E101_BODY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
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
E119_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E119_local_front_cut_family_saturation_audit/RESULT.txt"
)
E119_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E119_local_front_cut_family_saturation_audit/run-001/RESULT.json"
)
E119_CHECK = E119_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
}
EXPECTED_HASHES.update(
    {
        E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
        E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
        E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
        E114_RUNNER: "e893bdc7df70ce93f66c3976a06e3fd15e2d81b492fd2463b9d17cec4cd16e5d",
        E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
        E117_RUNNER: "ff51200bdec11733a27f3a82ffd63dc49a193e36fb1573f7c33d8a8b57d2f3f2",
        E118_CUTS: "93b4a05a9a19c2876cd9146f86ce6cbd11ee6a1923a6fed87f22b29ca5710375",
        E118_CHECK: "891d8ec1b41ac1ce178fb8345e748f51833d0279a8681993638e9db6fcbc813b",
        E119_DURABLE: "a0dae6e343a381c1b87166aa6686c8245d82dd572fe716f7633a3570ea0b0c49",
        E119_RESULT: "1e587146d34e1e42dfe5261ed5d179f772e594fb6b455154cf5666576b57b8e4",
        E119_CHECK: "07c106647606ebc8faf5fee06bb826d3db6f4420d257d51bca6ee4a64680af7e",
    }
)

EXPECTED_BODY_COUNT = 26
EXPECTED_CANDIDATE_COUNT = 1205
EXPECTED_OPTION_COUNT = 9808
EXPECTED_OPEN_VECTOR_COUNT = 25
HIGH_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
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


def process_snapshot() -> dict[str, int]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "ru_maxrss_kib": int(usage.ru_maxrss),
        "minor_page_faults": int(usage.ru_minflt),
        "major_page_faults": int(usage.ru_majflt),
        "voluntary_context_switches": int(usage.ru_nvcsw),
        "involuntary_context_switches": int(usage.ru_nivcsw),
    }


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
        raise RuntimeError("E120 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E120 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E120 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }
    result = load_json(E119_RESULT)
    if result.get("verdict") != "INCONCLUSIVE_MIXED_SATURATION":
        raise RuntimeError("E120 E119 verdict drift")
    if result.get("decision") != (
        "DO_NOT_BLINDLY_CONTINUE_SELECT_ONE_MEASURED_DISCRIMINATOR"
    ):
        raise RuntimeError("E120 E119 decision drift")
    check = load_json(E119_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "HIGH_STRUCTURAL_NOVELTY_LOW_SUBJECT_NOVELTY_ZERO_CROSS_GEOMETRY_REUSE"
    ):
        raise RuntimeError("E120 E119 check drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def build_integrated_model(
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

    body_vars_by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for local_index, row in enumerate(rows):
        for value in row["body"]:
            body_vars_by_cell[value].append(master["body_vars"][local_index])

    fixed_solid = set(language["context"]["fixed_solid"])
    option_vars_by_global: dict[int, list[Any]] = defaultdict(list)
    option_records: list[dict[str, Any]] = []
    front_constraint_count = 0
    dynamic_term_count = 0
    fixed_blocked_total = 0
    maximum_dynamic_terms = 0
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
                    body_variable
                    for value in front_cells
                    if e095.in_grid(value) and value not in fixed_solid
                    for body_variable in body_vars_by_cell.get(value, [])
                ]
                model.Add(
                    fixed_blocked + sum(dynamic_terms)
                    <= len(front_cells)
                    - int(required)
                    + len(front_cells) * (1 - variable)
                )
                front_constraint_count += 1
                dynamic_term_count += len(dynamic_terms)
                fixed_blocked_total += int(fixed_blocked)
                maximum_dynamic_terms = max(
                    maximum_dynamic_terms, len(dynamic_terms)
                )
        model.Add(sum(option_vars_by_global[global_index]) == body_var)

    if len(option_records) != EXPECTED_OPTION_COUNT:
        raise RuntimeError(
            f"E120 option count drift: {len(option_records)} != {EXPECTED_OPTION_COUNT}"
        )
    if len(option_vars_by_global) != EXPECTED_CANDIDATE_COUNT:
        raise RuntimeError("E120 body option-link count drift")

    imported_cut_count = 0
    if add_redundant_cuts:
        packet = load_json(E118_CUTS)
        cuts = list(packet["cuts"])
        imported = e117.add_death_cuts(master=master, deaths=cuts)
        imported_cut_count = len(imported)
        if imported_cut_count != int(packet["cut_count"]) or imported_cut_count != 587:
            raise RuntimeError("E120 redundant cut import drift")

    error = model.Validate()
    if error:
        raise RuntimeError(f"E120 integrated model invalid: {error}")
    return {
        **master,
        "option_vars_by_global": dict(option_vars_by_global),
        "option_records": option_records,
        "encoding_audit": {
            "candidate_count": len(rows),
            "body_variable_count": len(master["body_vars"]),
            "option_variable_count": len(option_records),
            "body_option_link_constraint_count": len(option_vars_by_global),
            "front_constraint_count": front_constraint_count,
            "dynamic_term_count": dynamic_term_count,
            "fixed_blocked_term_total": fixed_blocked_total,
            "maximum_dynamic_term_count_per_front_constraint": maximum_dynamic_terms,
            "grouped_class_key_count_distribution": dict(
                sorted(grouped_class_key_distribution.items())
            ),
            "redundant_cut_count": imported_cut_count,
            "model_variable_count": len(model.Proto().variables),
            "model_constraint_count": len(model.Proto().constraints),
            "truth_boundary": (
                "Each selected body chooses exactly one local existential witness. "
                "Grouped class keys share identical pose, fronts and required counts; "
                "no global class total is imposed."
            ),
        },
    }


def solver_for(*, profile: str, seconds: float, seed: int) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.random_seed = int(seed)
    solver.parameters.stop_after_first_solution = True
    solver.parameters.repair_hint = True
    solver.parameters.hint_conflict_limit = 4000
    if profile == "one_worker_pseudo_cost":
        solver.parameters.num_search_workers = 1
        solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
        solver.parameters.symmetry_level = 0
        solver.parameters.cp_model_probing_level = 0
        solver.parameters.randomize_search = False
    elif profile == "multiworker_automatic":
        solver.parameters.num_search_workers = 8
        solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
        solver.parameters.symmetry_level = 3
        solver.parameters.cp_model_probing_level = 3
        solver.parameters.randomize_search = True
    else:
        raise ValueError(f"unknown E120 solver profile: {profile}")
    return solver


def solve_integrated(
    *,
    integrated: Mapping[str, Any],
    profile: str,
    seconds: float,
    seed: int,
) -> dict[str, Any]:
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(profile=profile, seconds=seconds, seed=seed)
    status_code = solver.Solve(integrated["model"])
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)
    result: dict[str, Any] = {
        "schema": "zmd_e120_integrated_local_option_solve_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "profile": profile,
        "status": status,
        "elapsed_seconds": elapsed,
        "seconds": seconds,
        "seed": seed,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
        "encoding_audit": integrated["encoding_audit"],
    }
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_locals = [
            index
            for index, variable in enumerate(integrated["body_vars"])
            if solver.Value(variable)
        ]
        selected_globals = [
            int(integrated["rows"][index]["global_row_index"])
            for index in selected_locals
        ]
        if len(selected_globals) != EXPECTED_BODY_COUNT:
            raise RuntimeError("E120 selected body count drift")
        selected_option_records = [
            {
                "global_row_index": int(record["global_row_index"]),
                "option_index": int(record["option_index"]),
                "pose_index": int(record["pose_index"]),
                "need_in": int(record["need_in"]),
                "need_out": int(record["need_out"]),
                "class_keys": [list(key) for key in record["class_keys"]],
            }
            for record in integrated["option_records"]
            if solver.Value(record["variable"])
        ]
        if len(selected_option_records) != EXPECTED_BODY_COUNT:
            raise RuntimeError("E120 selected option count drift")
        option_globals = {
            int(record["global_row_index"]) for record in selected_option_records
        }
        if option_globals != set(selected_globals):
            raise RuntimeError("E120 selected option/body identity drift")
        separator_vector = [
            int(solver.Value(variable))
            for variable in integrated["separator_count_vars"]
        ]
        result.update(
            {
                "selected_body_count": len(selected_globals),
                "selected_global_row_indices": sorted(selected_globals),
                "selected_body_digest": stable_digest(
                    sorted(
                        str(integrated["rows"][index]["body_digest"])
                        for index in selected_locals
                    )
                ),
                "separator_template_vector": separator_vector,
                "selected_local_options": sorted(
                    selected_option_records,
                    key=lambda row: int(row["global_row_index"]),
                ),
                "selected_local_option_digest": stable_digest(
                    sorted(
                        selected_option_records,
                        key=lambda row: int(row["global_row_index"]),
                    )
                ),
            }
        )
    return result


def consume_geometry(
    *,
    run_dir: Path,
    e095: types.ModuleType,
    e101: types.ModuleType,
    e114: types.ModuleType,
    e117: types.ModuleType,
    language: Mapping[str, Any],
    options_by_global: Mapping[int, Sequence[Mapping[str, Any]]],
    selected_globals: set[int],
    high_primary_seconds: float,
    high_fallback_seconds: float,
    low_seconds: float,
) -> dict[str, Any]:
    rows_by_global = {
        int(row["global_row_index"]): row for row in language["rows"]
    }
    local_check = e117.local_front_check(
        e095=e095,
        selected_globals=selected_globals,
        options_by_global=options_by_global,
        rows_by_global=rows_by_global,
        fixed_solid=set(language["context"]["fixed_solid"]),
    )
    if not local_check["locally_live"]:
        raise RuntimeError("E120 integrated positive failed E117 local replay")
    geometry = {
        "schema": "zmd_e120_locally_live_geometry_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "selected_global_row_indices": sorted(selected_globals),
        "selected_body_digest": stable_digest(
            sorted(str(rows_by_global[index]["body_digest"]) for index in selected_globals)
        ),
        "local_front_replay": local_check,
    }
    geometry_path = run_dir / "LOCALLY_LIVE_GEOMETRY.json"
    dump_exclusive(geometry_path, geometry)

    def high_builder() -> dict[str, Any]:
        bundle = e114.fix_geometry(
            e095=e095,
            e101=e101,
            restricted=language["restricted"],
            selected_indices=selected_globals,
        )
        bundle["base_context"] = language["context"]
        return bundle

    high_solve = e114.solve_with_fallback(
        builder=high_builder,
        e095=e095,
        primary_seconds=high_primary_seconds,
        fallback_seconds=high_fallback_seconds,
        seed=120500,
    )
    high_terminal = (
        high_solve["fallback"]
        if high_solve["fallback"] is not None
        else high_solve["primary"]
    )
    high_path = run_dir / "HIGH_FIXED_GEOMETRY_RESULT.json"
    dump_exclusive(
        high_path,
        {
            "primary": high_solve["primary"],
            "fallback": high_solve["fallback"],
            "terminal": high_terminal,
        },
    )

    hall = None
    low_result = None
    module_b = None
    combined = None
    low_path = run_dir / "LOW_COMPLEMENT_RESULT.json"
    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"
    if high_terminal["status"] == "INFEASIBLE":
        hall = e117.class_hall_diagnosis(
            e095=e095,
            selected_globals=selected_globals,
            options_by_global=options_by_global,
            rows_by_global=rows_by_global,
            fixed_solid=set(language["context"]["fixed_solid"]),
            class_keys=language["class_keys"],
            class_caps=language["global_class_counts"],
        )
    elif high_terminal["status"] in {"OPTIMAL", "FEASIBLE"}:
        complement = e101.complement_allocation(
            language["class_keys"],
            language["global_class_counts"],
            list(map(int, high_terminal["allocation_tuple"])),
        )
        low_hints = set(map(int, load_json(E101_BODY)["selected_body_indices"]))
        low_bundle = e101.build_side_model(
            e095=e095,
            restricted=language["restricted"],
            side="low",
            template_counts=LOW_TEMPLATE_COUNTS,
            body_hint_indices=low_hints,
            fixed_allocation=complement,
        )
        low_bundle["base_context"] = language["context"]
        low_result = e114.solve_bundle(
            e095=e095,
            bundle=low_bundle,
            seconds=low_seconds,
            seed=120700,
            profile="multiworker_automatic",
        )
        dump_exclusive(low_path, low_result)
        if low_result["status"] in {"OPTIMAL", "FEASIBLE"}:
            pair = e101.combine_side_witnesses(
                e095=e095,
                restricted=language["restricted"],
                low=low_result,
                high=high_terminal,
            )
            module_b = pair["module_b"]
            combined = pair["combined"]
            dump_exclusive(module_b_path, module_b)
            dump_exclusive(combined_path, combined)

    return {
        "geometry": {
            "path": display(geometry_path),
            "sha256": sha256_file(geometry_path),
            "selected_body_digest": geometry["selected_body_digest"],
        },
        "high": {
            "path": display(high_path),
            "sha256": sha256_file(high_path),
            "status": high_terminal["status"],
            "elapsed_seconds": high_terminal["elapsed_seconds"],
            "branches": high_terminal["branches"],
            "conflicts": high_terminal["conflicts"],
            "hall_diagnosis": hall,
        },
        "low": (
            {
                "path": display(low_path),
                "sha256": sha256_file(low_path),
                "status": low_result["status"],
                "elapsed_seconds": low_result["elapsed_seconds"],
                "branches": low_result["branches"],
                "conflicts": low_result["conflicts"],
            }
            if low_result is not None
            else None
        ),
        "module_b": (
            {
                "path": display(module_b_path),
                "sha256": sha256_file(module_b_path),
                "selected_body_count": module_b["selected_body_count"],
                "selected_assignment_digest": module_b["selected_assignment_digest"],
            }
            if module_b is not None
            else None
        ),
        "combined": (
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
        raise FileExistsError(f"refusing to reuse E120 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e120_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e120_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e120_source_e101")
    e114 = source_module(E114_RUNNER, "zmd_e120_source_e114")
    e115 = source_module(E115_RUNNER, "zmd_e120_source_e115")
    e117 = source_module(E117_RUNNER, "zmd_e120_source_e117")

    language = e117.build_language(e095=e095, e100=e100, e115=e115)
    options_by_global = e117.precompute_options(e095=e095, language=language)
    if len(language["rows"]) != EXPECTED_CANDIDATE_COUNT:
        raise RuntimeError("E120 candidate count drift")
    if len(language["open_vectors"]) != EXPECTED_OPEN_VECTOR_COUNT:
        raise RuntimeError("E120 open separator-vector count drift")
    if sum(len(values) for values in options_by_global.values()) != EXPECTED_OPTION_COUNT:
        raise RuntimeError("E120 syntactic option count drift")

    primary_model = build_integrated_model(
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
            "schema": "zmd_e120_integrated_encoding_audit_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            **primary_model["encoding_audit"],
        },
    )
    primary = solve_integrated(
        integrated=primary_model,
        profile="one_worker_pseudo_cost",
        seconds=primary_seconds,
        seed=120100,
    )
    primary_path = run_dir / "PRIMARY_RESULT.json"
    dump_exclusive(primary_path, primary)

    terminal = primary
    terminal_path = primary_path
    fallback = None
    fallback_path = run_dir / "FALLBACK_RESULT.json"
    if primary["status"] == "UNKNOWN":
        fallback_model = build_integrated_model(
            e095=e095,
            e117=e117,
            language=language,
            options_by_global=options_by_global,
            add_redundant_cuts=True,
        )
        fallback = solve_integrated(
            integrated=fallback_model,
            profile="multiworker_automatic",
            seconds=fallback_seconds,
            seed=120300,
        )
        dump_exclusive(fallback_path, fallback)
        terminal = fallback
        terminal_path = fallback_path

    consumer = None
    if terminal["status"] in {"OPTIMAL", "FEASIBLE"}:
        selected_globals = set(map(int, terminal["selected_global_row_indices"]))
        consumer = consume_geometry(
            run_dir=run_dir,
            e095=e095,
            e101=e101,
            e114=e114,
            e117=e117,
            language=language,
            options_by_global=options_by_global,
            selected_globals=selected_globals,
            high_primary_seconds=high_primary_seconds,
            high_fallback_seconds=high_fallback_seconds,
            low_seconds=low_seconds,
        )

    combined = consumer["combined"] if consumer is not None else None
    high = consumer["high"] if consumer is not None else None
    if combined is not None:
        verdict = "INTEGRATED_LOCAL_OPTION_MASTER_REACHES_219_BODY_NATIVE_FRONT_WITNESS"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif high is not None and high["status"] in {"OPTIMAL", "FEASIBLE"}:
        verdict = "INTEGRATED_LOCAL_OPTION_GEOMETRY_HAS_FULL_HIGH_WITNESS"
        decision = "CONTINUE_ONLY_X42_LOW_ALLOCATION_HANDSHAKE"
    elif consumer is not None:
        verdict = "INTEGRATED_LOCAL_OPTION_GEOMETRY_FOUND_FULL_CLASS_NOT_PAIRED"
        decision = "FREEZE_GEOMETRY_AND_DECOMPOSE_GLOBAL_CLASS_ASSIGNMENT"
    elif terminal["status"] == "INFEASIBLE":
        verdict = "OPEN_X42_LOCAL_OPTION_LANGUAGE_INFEASIBLE"
        decision = "RETIRE_SOURCE_STABLE_X42_SUFFICIENT_CONSTRUCTOR"
    else:
        verdict = "INTEGRATED_LOCAL_OPTION_MASTER_CENSORED"
        decision = "CHANGE_GEOMETRY_REPRESENTATION_OR_SKELETON"

    result = {
        "schema": "zmd_e120_integrated_local_option_master_result_v1",
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
        "language": {
            "candidate_count": len(language["rows"]),
            "syntactic_option_count": sum(
                len(values) for values in options_by_global.values()
            ),
            "open_separator_template_vector_count": len(language["open_vectors"]),
            "encoding_audit_path": display(encoding_path),
            "encoding_audit_sha256": sha256_file(encoding_path),
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
            "The integrated model is exactly E117 local-option existence plus the "
            "body/power master, without global class totals. A positive requires the "
            "unchanged full high consumer; UNKNOWN proves no absence."
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
            "schema": "zmd_e120_execution_failure_v1",
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
