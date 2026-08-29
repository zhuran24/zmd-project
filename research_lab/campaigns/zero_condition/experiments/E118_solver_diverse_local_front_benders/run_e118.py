#!/usr/bin/env python3
"""E118: solver-diverse continuation of E117 local-front Benders."""

from __future__ import annotations

import argparse
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
from typing import Any, Mapping

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E118_solver_diverse_local_front_benders/run-001"
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
E117_DURABLE = E117_RUNNER.with_name("RESULT.txt")
E117_SNAPSHOT = E117_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E117_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E117_high_geometry_local_front_benders/run-001"
)
E117_RESULT = E117_RUN / "RESULT.json"
E117_CUTS = E117_RUN / "LOCAL_FRONT_BLOCKER_CUTS.json"
E117_CHECK = E117_RUN / "ARTIFACT_CHECK.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E114_RUNNER: "e893bdc7df70ce93f66c3976a06e3fd15e2d81b492fd2463b9d17cec4cd16e5d",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E117_RUNNER: "ff51200bdec11733a27f3a82ffd63dc49a193e36fb1573f7c33d8a8b57d2f3f2",
    E117_DURABLE: "7d5634572f1de5c7b581edff2baba5808f21f5c6e8c9087eff1de65079ba0050",
    E117_SNAPSHOT: "b3a0fe9cc661b63d44b762cf5f9ca32226b5ffd46eebf29f0307543b2d00edbc",
    E117_RESULT: "1efe295bd816c0844cc550850c6c8d12c09b77a08b942bec9ca25aad8153054d",
    E117_CUTS: "6b671d1b97cb308fd109c75ced4d6521ffa2003deb386c0ad484406d1101e5fd",
    E117_CHECK: "c4529c108fe73ac6c871c3c5133d9592ad8d6091ceb543b58160cd553cd88d9d",
}

EXPECTED_IMPORTED_CUTS = 504
E117_BEST_EMPTY = 6
EXPECTED_BODY_COUNT = 26
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
        raise RuntimeError("E118 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E118 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E118 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }
    result = load_json(E117_RESULT)
    if result.get("verdict") != "HIGH_GEOMETRY_LOCAL_FRONT_BENDERS_CENSORED":
        raise RuntimeError("E118 E117 verdict drift")
    if result.get("decision") != "CONTINUE_FROM_PERSISTED_BLOCKER_CUTS":
        raise RuntimeError("E118 E117 decision drift")
    check = load_json(E117_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "FIVE_HUNDRED_FOUR_LOCAL_FRONT_CONTAINMENT_CUTS_REPLAYED"
    ):
        raise RuntimeError("E118 E117 check drift")
    if int(check.get("cut_count", -1)) != EXPECTED_IMPORTED_CUTS:
        raise RuntimeError("E118 imported cut count drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def solve_master(
    model: cp_model.CpModel,
    *,
    seconds: float,
    seed: int,
    profile: str,
) -> dict[str, Any]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.random_seed = int(seed)
    solver.parameters.stop_after_first_solution = True
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
        raise RuntimeError(f"unknown E118 master profile: {profile}")
    before = process_snapshot()
    started = time.monotonic()
    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started
    after = process_snapshot()
    return {
        "profile": profile,
        "status": solver.StatusName(status_code),
        "status_code": int(status_code),
        "elapsed_seconds": elapsed,
        "solve_seconds": float(seconds),
        "seed": int(seed),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
        "solver": solver,
    }


def public_solve_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"solver", "status_code"}
    }


def consume_geometry(
    *,
    e095: types.ModuleType,
    e101: types.ModuleType,
    e114: types.ModuleType,
    e117: types.ModuleType,
    language: Mapping[str, Any],
    options_by_global: Mapping[int, Any],
    rows_by_global: Mapping[int, Mapping[str, Any]],
    fixed_solid: set[tuple[int, int]],
    selected_globals: set[int],
    high_primary_seconds: float,
    high_fallback_seconds: float,
    low_seconds: float,
    run_dir: Path,
) -> dict[str, Any]:
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
        primary_seconds=float(high_primary_seconds),
        fallback_seconds=float(high_fallback_seconds),
        seed=118500,
    )
    high = (
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
            "terminal": high,
        },
    )
    hall = None
    low = None
    module_b = None
    combined = None
    low_path = run_dir / "LOW_COMPLEMENT_RESULT.json"
    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"
    if high["status"] == "INFEASIBLE":
        hall = e117.class_hall_diagnosis(
            e095=e095,
            selected_globals=selected_globals,
            options_by_global=options_by_global,
            rows_by_global=rows_by_global,
            fixed_solid=fixed_solid,
            class_keys=language["class_keys"],
            class_caps=language["global_class_counts"],
        )
    elif high["status"] in {"OPTIMAL", "FEASIBLE"}:
        complement = e101.complement_allocation(
            language["class_keys"],
            language["global_class_counts"],
            list(map(int, high["allocation_tuple"])),
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
        low = e114.solve_bundle(
            e095=e095,
            bundle=low_bundle,
            seconds=float(low_seconds),
            seed=118700,
            profile="multiworker_automatic",
        )
        dump_exclusive(low_path, low)
        if low["status"] in {"OPTIMAL", "FEASIBLE"}:
            pair = e101.combine_side_witnesses(
                e095=e095,
                restricted=language["restricted"],
                low=low,
                high=high,
            )
            module_b = pair["module_b"]
            combined = pair["combined"]
            dump_exclusive(module_b_path, module_b)
            dump_exclusive(combined_path, combined)
    return {
        "high": high,
        "high_path": high_path,
        "hall": hall,
        "low": low,
        "low_path": low_path if low is not None else None,
        "module_b": module_b,
        "module_b_path": module_b_path if module_b is not None else None,
        "combined": combined,
        "combined_path": combined_path if combined is not None else None,
    }


def run(
    *,
    run_dir: Path,
    primary_seconds: float,
    fallback_seconds: float,
    high_primary_seconds: float,
    high_fallback_seconds: float,
    low_seconds: float,
    max_iterations: int,
    total_seconds: float,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E118 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e118_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e118_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e118_source_e101")
    e114 = source_module(E114_RUNNER, "zmd_e118_source_e114")
    e115 = source_module(E115_RUNNER, "zmd_e118_source_e115")
    e117 = source_module(E117_RUNNER, "zmd_e118_source_e117")

    language = e117.build_language(e095=e095, e100=e100, e115=e115)
    options_by_global = e117.precompute_options(e095=e095, language=language)
    master = e117.build_master(language)
    rows_by_global = {
        int(row["global_row_index"]): row for row in language["rows"]
    }
    fixed_solid = set(language["context"]["fixed_solid"])

    imported_packet = load_json(E117_CUTS)
    imported_records = [dict(record) for record in imported_packet["cuts"]]
    imported = e117.add_death_cuts(master=master, deaths=imported_records)
    if len(imported) != EXPECTED_IMPORTED_CUTS:
        raise RuntimeError(f"E118 imported cut drift: {len(imported)}")
    if len(master["cut_keys"]) != EXPECTED_IMPORTED_CUTS:
        raise RuntimeError("E118 imported cut key drift")
    if master["model"].Validate():
        raise RuntimeError("E118 imported master invalid")

    started = time.monotonic()
    iterations: list[dict[str, Any]] = []
    new_cuts: list[dict[str, Any]] = []
    locally_live: dict[str, Any] | None = None
    consumer: dict[str, Any] | None = None
    master_terminal_status = "NOT_RUN"
    best_empty: int | None = None

    for iteration in range(max_iterations):
        remaining = float(total_seconds) - (time.monotonic() - started)
        if remaining <= 1.0:
            master_terminal_status = "TOTAL_BUDGET_EXHAUSTED"
            break
        primary = solve_master(
            master["model"],
            seconds=min(float(primary_seconds), max(0.5, remaining - 0.25)),
            seed=118100 + iteration,
            profile="one_worker_pseudo_cost",
        )
        terminal = primary
        fallback = None
        if primary["status"] == "UNKNOWN":
            remaining = float(total_seconds) - (time.monotonic() - started)
            if remaining > 1.0 and fallback_seconds > 0:
                fallback = solve_master(
                    master["model"],
                    seconds=min(float(fallback_seconds), max(0.5, remaining - 0.25)),
                    seed=118300 + iteration,
                    profile="multiworker_automatic",
                )
                terminal = fallback
        status = str(terminal["status"])
        master_terminal_status = status
        record: dict[str, Any] = {
            "iteration": iteration,
            "cut_count_before": len(master["cut_keys"]),
            "primary": public_solve_record(primary),
            "fallback": public_solve_record(fallback) if fallback is not None else None,
            "terminal_profile": terminal["profile"],
            "terminal_status": status,
        }
        status_code = int(terminal["status_code"])
        if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            iterations.append(record)
            break

        solver = terminal["solver"]
        selected_locals = [
            index
            for index, variable in enumerate(master["body_vars"])
            if solver.Value(variable)
        ]
        if len(selected_locals) != EXPECTED_BODY_COUNT:
            raise RuntimeError("E118 selected body count drift")
        selected_globals = {
            int(master["rows"][index]["global_row_index"])
            for index in selected_locals
        }
        separator_vector = tuple(
            int(solver.Value(variable))
            for variable in master["separator_count_vars"]
        )
        check = e117.local_front_check(
            e095=e095,
            selected_globals=selected_globals,
            options_by_global=options_by_global,
            rows_by_global=rows_by_global,
            fixed_solid=fixed_solid,
        )
        empty_count = int(check["empty_body_count"])
        best_empty = empty_count if best_empty is None else min(best_empty, empty_count)
        record.update(
            {
                "selected_global_row_indices": sorted(selected_globals),
                "selected_body_digest": stable_digest(
                    sorted(
                        str(rows_by_global[value]["body_digest"])
                        for value in selected_globals
                    )
                ),
                "separator_template_vector": list(separator_vector),
                "local_front": check,
            }
        )
        if check["locally_live"]:
            locally_live = {
                "iteration": iteration,
                "selected_global_row_indices": sorted(selected_globals),
                "selected_body_digest": record["selected_body_digest"],
                "separator_template_vector": list(separator_vector),
                "viable_option_count_by_body": check[
                    "viable_option_count_by_body"
                ],
            }
            record["new_cut_count"] = 0
            iterations.append(record)
            consumer = consume_geometry(
                e095=e095,
                e101=e101,
                e114=e114,
                e117=e117,
                language=language,
                options_by_global=options_by_global,
                rows_by_global=rows_by_global,
                fixed_solid=fixed_solid,
                selected_globals=selected_globals,
                high_primary_seconds=high_primary_seconds,
                high_fallback_seconds=high_fallback_seconds,
                low_seconds=low_seconds,
                run_dir=run_dir,
            )
            break

        added = e117.add_death_cuts(master=master, deaths=check["deaths"])
        if not added:
            raise RuntimeError("E118 front-dead geometry produced no new cuts")
        new_cuts.extend(
            {**cut, "source_iteration": iteration} for cut in added
        )
        record["new_cut_count"] = len(added)
        record["cut_count_after"] = len(master["cut_keys"])
        iterations.append(record)

    merged_records = [*imported_records, *new_cuts]
    if len({str(record["cut_key"]) for record in merged_records}) != len(
        merged_records
    ):
        raise RuntimeError("E118 merged cut key collision")
    new_cuts_path = run_dir / "NEW_LOCAL_FRONT_BLOCKER_CUTS.json"
    dump_exclusive(
        new_cuts_path,
        {
            "schema": "zmd_e118_new_local_front_blocker_cuts_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "imported_cut_count": EXPECTED_IMPORTED_CUTS,
            "new_cut_count": len(new_cuts),
            "cuts": new_cuts,
        },
    )
    merged_path = run_dir / "MERGED_LOCAL_FRONT_BLOCKER_CUTS.json"
    dump_exclusive(
        merged_path,
        {
            "schema": "zmd_e118_merged_local_front_blocker_cuts_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "imported_cut_count": EXPECTED_IMPORTED_CUTS,
            "new_cut_count": len(new_cuts),
            "cut_count": len(merged_records),
            "cuts": merged_records,
            "truth_boundary": (
                "Imported E117 cuts plus E118 cuts; every record is a monotone "
                "local-front containment rule."
            ),
        },
    )
    iterations_path = run_dir / "CONTINUATION_ITERATIONS.json"
    dump_exclusive(
        iterations_path,
        {
            "schema": "zmd_e118_continuation_iterations_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "iteration_count": len(iterations),
            "master_terminal_status": master_terminal_status,
            "locally_live_geometry_found": locally_live is not None,
            "best_new_empty_body_count": best_empty,
            "records": iterations,
        },
    )
    geometry_path = run_dir / "LOCALLY_LIVE_GEOMETRY.json"
    if locally_live is not None:
        dump_exclusive(geometry_path, locally_live)

    combined = consumer["combined"] if consumer is not None else None
    high = consumer["high"] if consumer is not None else None
    low = consumer["low"] if consumer is not None else None
    if combined is not None:
        verdict = "SOLVER_DIVERSE_BENDERS_REACHES_219_BODY_NATIVE_FRONT_WITNESS"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif locally_live is not None:
        verdict = "SOLVER_DIVERSE_BENDERS_FINDS_LOCALLY_LIVE_GEOMETRY"
        decision = "FREEZE_GEOMETRY_AND_CONTINUE_ONLY_CLASS_CONSUMER"
    elif master_terminal_status == "INFEASIBLE":
        verdict = "CUT_AUGMENTED_X42_LOCAL_FRONT_MASTER_INFEASIBLE"
        decision = "RETIRE_SOURCE_STABLE_X42_SUFFICIENT_CONSTRUCTOR"
    elif best_empty is not None and best_empty < E117_BEST_EMPTY:
        verdict = "SOLVER_DIVERSE_LOCAL_FRONT_BENDERS_CENSORED_WITH_IMPROVEMENT"
        decision = "CONTINUE_FROM_MERGED_CUT_STORE"
    else:
        verdict = "SOLVER_DIVERSE_LOCAL_FRONT_BENDERS_CENSORED_NO_IMPROVEMENT"
        decision = "MEASURE_CUT_FAMILY_COVERAGE_AND_SATURATION"

    result = {
        "schema": "zmd_e118_solver_diverse_local_front_benders_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "primary_profile": "one_worker_pseudo_cost",
            "primary_seconds_per_iteration": primary_seconds,
            "fallback_profile": "multiworker_automatic",
            "fallback_seconds_per_iteration": fallback_seconds,
            "max_iterations": max_iterations,
            "total_seconds": total_seconds,
            "high_primary_seconds": high_primary_seconds,
            "high_fallback_seconds": high_fallback_seconds,
            "low_seconds": low_seconds,
            "source_isolated_helpers": True,
        },
        "import": {
            "cut_count": EXPECTED_IMPORTED_CUTS,
            "path": display(E117_CUTS),
            "sha256": sha256_file(E117_CUTS),
            "check_path": display(E117_CHECK),
            "check_sha256": sha256_file(E117_CHECK),
        },
        "continuation": {
            "iterations_path": display(iterations_path),
            "iterations_sha256": sha256_file(iterations_path),
            "iteration_count": len(iterations),
            "master_terminal_status": master_terminal_status,
            "new_cut_count": len(new_cuts),
            "new_cuts_path": display(new_cuts_path),
            "new_cuts_sha256": sha256_file(new_cuts_path),
            "merged_cut_count": len(merged_records),
            "merged_cuts_path": display(merged_path),
            "merged_cuts_sha256": sha256_file(merged_path),
            "best_prior_empty_body_count": E117_BEST_EMPTY,
            "best_new_empty_body_count": best_empty,
            "locally_live_geometry_found": locally_live is not None,
        },
        "locally_live_geometry": (
            {
                "path": display(geometry_path),
                "sha256": sha256_file(geometry_path),
                **locally_live,
            }
            if locally_live is not None
            else None
        ),
        "high_consumer": (
            {
                "path": display(consumer["high_path"]),
                "sha256": sha256_file(consumer["high_path"]),
                "status": high["status"],
                "elapsed_seconds": high["elapsed_seconds"],
                "branches": high["branches"],
                "conflicts": high["conflicts"],
                "hall_diagnosis": consumer["hall"],
            }
            if consumer is not None
            else None
        ),
        "low_consumer": (
            {
                "path": display(consumer["low_path"]),
                "sha256": sha256_file(consumer["low_path"]),
                "status": low["status"],
                "elapsed_seconds": low["elapsed_seconds"],
                "branches": low["branches"],
                "conflicts": low["conflicts"],
            }
            if consumer is not None and low is not None
            else None
        ),
        "combined_witness": (
            {
                "path": display(consumer["combined_path"]),
                "sha256": sha256_file(consumer["combined_path"]),
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
            "Solver profiles change only the search instrument. Imported and new "
            "cuts are local-front necessary conditions. UNKNOWN proves no absence."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--primary-seconds", type=float, default=30.0)
    parser.add_argument("--fallback-seconds", type=float, default=12.0)
    parser.add_argument("--high-primary-seconds", type=float, default=30.0)
    parser.add_argument("--high-fallback-seconds", type=float, default=30.0)
    parser.add_argument("--low-seconds", type=float, default=45.0)
    parser.add_argument("--max-iterations", type=int, default=60)
    parser.add_argument("--total-seconds", type=float, default=240.0)
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
            max_iterations=int(args.max_iterations),
            total_seconds=float(args.total_seconds),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "continuation": result["continuation"],
                    "high_consumer": result["high_consumer"],
                    "low_consumer": result["low_consumer"],
                    "combined_witness": result["combined_witness"] is not None,
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
            "schema": "zmd_e118_execution_failure_v1",
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
