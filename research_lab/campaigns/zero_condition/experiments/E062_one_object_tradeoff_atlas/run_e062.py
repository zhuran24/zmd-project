#!/usr/bin/env python3
"""E062: exact one-object qiaoyu-hard fine-mismatch atlas."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E062_one_object_tradeoff_atlas/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
NON6_PATH = OUT / "NON6_ATLAS.json"
SIX4_PATH = OUT / "SIX4_ATLAS.json"

E060_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E060_generic_qiaoyu_sink_correction/run-001/RESULT.json"
)
E061_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E061_all_one_object_signature_frontier/run-001/RESULT.json"
)
E061_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E061_all_one_object_signature_frontier/run_e061.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "289000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E060_RESULT: "feb697f506cb2ca2422c1d0e96a02250cb33afcaa21fc86fda939f6ce79409b8",
    E061_RESULT: "0559401660d99c69127c7f65f287900a6ca205b9f6bfce64b9e607d1dda785b2",
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
}

BASELINE_OBJECTIVE = 2
SOLVE_SECONDS = 1.0
SOLVE_WORKERS = 8


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def dump_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
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


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    mismatches = {
        key: {"expected": value, "actual": os.environ.get(key)}
        for key, value in EXPECTED_ENV.items()
        if os.environ.get(key) != value
    }
    unexpected_exact = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected_exact:
        raise RuntimeError(
            f"environment mismatch: mismatches={mismatches}, "
            f"unexpected_exact={unexpected_exact}"
        )
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(
                f"frozen identity drift for {path}: {actual} != {expected}"
            )
    e061_result = load_json(E061_RESULT)
    if e061_result.get("verdict") != (
        "ALL_ONE_OBJECT_TWO_ZERO_SIGNATURE_CHANGES_INFEASIBLE"
    ):
        raise RuntimeError("E062 E061 trigger verdict drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def add_exact_or(
    model: cp_model.CpModel,
    *,
    name: str,
    contributors: Sequence[Any],
) -> Any:
    variable = model.NewBoolVar(name)
    if not contributors:
        model.Add(variable == 0)
        return variable
    for contributor in contributors:
        model.Add(variable >= contributor)
    model.Add(variable <= cp_model.LinearExpr.Sum(list(contributors)))
    return variable


def solve_qiaoyu_hard(
    *,
    options: Mapping[int, Sequence[tuple[Any, ...]]],
    sink_space: Mapping[str, Any],
    random_seed: int,
) -> dict[str, Any]:
    if not sink_space["slots"] or any(not rows for rows in options.values()):
        return {
            "status": "STRUCTURAL_EMPTY",
            "objective": None,
            "elapsed_seconds": 0.0,
            "branches": 0,
            "conflicts": 0,
            "presence": None,
        }
    e061 = import_module("zmd_e062_e061_constants", E061_RUNNER)
    model = cp_model.CpModel()
    x_vars: dict[tuple[int, int], Any] = {}
    for destination, rows in options.items():
        variables: list[Any] = []
        for option_index, _option in enumerate(rows):
            variable = model.NewBoolVar(f"e062_x_{destination}_{option_index}")
            x_vars[(destination, option_index)] = variable
            variables.append(variable)
        model.AddExactlyOne(variables)
    for operation, expected in e061.OPERATION_COUNTS.items():
        model.Add(
            cp_model.LinearExpr.Sum(
                [
                    x_vars[(destination, option_index)]
                    for destination, rows in options.items()
                    for option_index, option in enumerate(rows)
                    if str(option[0]) == operation
                ]
            )
            == int(expected)
        )
    components = sorted(
        {
            int(component)
            for rows in options.values()
            for _operation, _pose_idx, signature in rows
            for part in signature
            for component in part
        }
        | set(int(value) for value in sink_space["components"])
    )
    fine_sources: dict[int, Any] = {}
    fine_sinks: dict[int, Any] = {}
    qiaoyu_sources: dict[int, Any] = {}
    for component in components:
        fine_sources[component] = add_exact_or(
            model,
            name=f"e062_fine_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option[2][1])
            ],
        )
        fine_sinks[component] = add_exact_or(
            model,
            name=f"e062_fine_sink_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option[2][0])
            ],
        )
        qiaoyu_sources[component] = add_exact_or(
            model,
            name=f"e062_qiaoyu_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option[2][2])
            ],
        )
    sink_component_vars = {
        component: model.NewBoolVar(f"e062_sink_component_{component}")
        for component in sink_space["components"]
    }
    model.AddExactlyOne(list(sink_component_vars.values()))
    fine_mismatch: dict[int, Any] = {}
    for component in components:
        model.Add(
            qiaoyu_sources[component]
            == (
                sink_component_vars[component]
                if component in sink_component_vars
                else 0
            )
        )
        mismatch = model.NewBoolVar(f"e062_fine_mismatch_{component}")
        source = fine_sources[component]
        sink = fine_sinks[component]
        model.Add(mismatch >= source - sink)
        model.Add(mismatch >= sink - source)
        model.Add(mismatch <= source + sink)
        model.Add(mismatch <= 2 - source - sink)
        fine_mismatch[component] = mismatch
    model.Add(cp_model.LinearExpr.Sum(list(fine_sources.values())) >= 1)
    model.Add(cp_model.LinearExpr.Sum(list(fine_sinks.values())) >= 1)
    model.Minimize(cp_model.LinearExpr.Sum(list(fine_mismatch.values())))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_SECONDS
    solver.parameters.num_search_workers = SOLVE_WORKERS
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(random_seed)
    started = time.monotonic()
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "status": status_name,
        "objective": None,
        "best_bound": float(solver.BestObjectiveBound()),
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "presence": None,
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        objective = int(round(solver.ObjectiveValue()))
        qiaoyu_sink = next(
            component
            for component, variable in sink_component_vars.items()
            if solver.Value(variable) == 1
        )
        source_set = {
            component
            for component, variable in fine_sources.items()
            if solver.Value(variable) == 1
        }
        sink_set = {
            component
            for component, variable in fine_sinks.items()
            if solver.Value(variable) == 1
        }
        mismatch_set = {
            component
            for component, variable in fine_mismatch.items()
            if solver.Value(variable) == 1
        }
        if objective != len(mismatch_set):
            raise RuntimeError("E062 objective/presence mismatch")
        result.update(
            {
                "objective": objective,
                "presence": {
                    "qiaoyu_sink_component": int(qiaoyu_sink),
                    "fine_source_components": sorted(source_set),
                    "fine_sink_components": sorted(sink_set),
                    "fine_mismatch_components": sorted(mismatch_set),
                    "source_only_components": sorted(source_set - sink_set),
                    "sink_only_components": sorted(sink_set - source_set),
                },
            }
        )
    return result


def candidate_record(
    *,
    instance_id: str,
    row: Mapping[str, Any],
    alternative: Mapping[str, Any],
    solve: Mapping[str, Any],
    alias_count: int,
) -> dict[str, Any]:
    return {
        "source_instance_id": str(instance_id),
        "facility_type": str(row["facility_type"]),
        "current_pose_idx": int(row["pose_idx"]),
        "replacement_pose_idx": int(alternative["pose_idx"]),
        "replacement_pose_id": str(alternative["pose_id"]),
        "alias_count": int(alias_count),
        "tradeoff": json_safe(solve),
    }


def scan_non6(
    *,
    e061: Any,
    base: Mapping[str, Any],
    descriptors: Mapping[int, Sequence[tuple[Any, ...]]],
    runner_sha256: str,
) -> dict[str, Any]:
    if NON6_PATH.exists():
        payload = load_json(NON6_PATH)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E062 non6 checkpoint")
        return payload
    seen: dict[tuple[Any, ...], int] = {}
    raw_body_count = 0
    status_counts: Counter[str] = Counter()
    objective_distribution: Counter[int] = Counter()
    improvements: list[dict[str, Any]] = []
    nonterminal: list[dict[str, Any]] = []
    same_mode_counts: Counter[str] = Counter()
    invariant_same_modes = 0
    explicit_same_modes = 0
    started = time.monotonic()
    for instance_id, row in sorted(base["solution"].items()):
        facility_type = str(row["facility_type"])
        if facility_type == e061.SIX4:
            continue
        for alternative in e061.enumerate_alternatives(
            base=base,
            instance_id=instance_id,
        ):
            if bool(alternative["same_footprint"]):
                same_mode_counts[facility_type] += 1
                operation = str(row.get("operation_type", ""))
                if facility_type != "protocol_core":
                    if int(
                        base["inputs"]["plan"][
                            "generic_input_slots_by_operation"
                        ].get(operation, 0)
                    ) != 0:
                        raise RuntimeError(
                            f"unhandled generic-input mode: {instance_id}"
                        )
                    invariant_same_modes += 1
                    objective_distribution[BASELINE_OBJECTIVE] += 1
                    continue
                explicit_same_modes += 1
                routing_context = base["build_routing_context"](
                    alternative["solution"],
                    base["inputs"]["pools"],
                    70,
                    70,
                )
                solve = solve_qiaoyu_hard(
                    options=e061.map_descriptors(
                        descriptors=descriptors,
                        routing_context=routing_context,
                    ),
                    sink_space=e061.generic_sink_space(
                        candidate=alternative["solution"],
                        routing_context=routing_context,
                        inputs=base["inputs"],
                        is_port_front_usable=base["is_port_front_usable"],
                    ),
                    random_seed=62100 + int(alternative["pose_idx"]),
                )
                status_counts[str(solve["status"])] += 1
                if solve.get("objective") is not None:
                    objective_distribution[int(solve["objective"])] += 1
                    if int(solve["objective"]) < BASELINE_OBJECTIVE:
                        improvements.append(
                            candidate_record(
                                instance_id=instance_id,
                                row=row,
                                alternative=alternative,
                                solve=solve,
                                alias_count=0,
                            )
                        )
                elif solve["status"] not in {"INFEASIBLE", "STRUCTURAL_EMPTY"}:
                    nonterminal.append(
                        candidate_record(
                            instance_id=instance_id,
                            row=row,
                            alternative=alternative,
                            solve=solve,
                            alias_count=0,
                        )
                    )
                continue
            raw_body_count += 1
            old_cells = tuple(
                sorted(
                    base["e014"].pose_cells(
                        base["inputs"]["pools"],
                        facility_type,
                        int(row["pose_idx"]),
                    )
                )
            )
            new_cells = tuple(
                sorted((int(x), int(y)) for x, y in alternative["occupied_cells"])
            )
            key = (facility_type, old_cells, new_cells)
            if key in seen:
                seen[key] += 1
                continue
            seen[key] = 0
            routing_context = base["build_routing_context"](
                alternative["solution"],
                base["inputs"]["pools"],
                70,
                70,
            )
            solve = solve_qiaoyu_hard(
                options=e061.map_descriptors(
                    descriptors=descriptors,
                    routing_context=routing_context,
                ),
                sink_space=e061.generic_sink_space(
                    candidate=alternative["solution"],
                    routing_context=routing_context,
                    inputs=base["inputs"],
                    is_port_front_usable=base["is_port_front_usable"],
                ),
                random_seed=62200 + len(seen),
            )
            status_counts[str(solve["status"])] += 1
            if solve.get("objective") is not None:
                objective_distribution[int(solve["objective"])] += 1
                if int(solve["objective"]) < BASELINE_OBJECTIVE:
                    improvements.append(
                        candidate_record(
                            instance_id=instance_id,
                            row=row,
                            alternative=alternative,
                            solve=solve,
                            alias_count=int(seen[key]),
                        )
                    )
            elif solve["status"] not in {"INFEASIBLE", "STRUCTURAL_EMPTY"}:
                nonterminal.append(
                    candidate_record(
                        instance_id=instance_id,
                        row=row,
                        alternative=alternative,
                        solve=solve,
                        alias_count=int(seen[key]),
                    )
                )
            if len(seen) % 500 == 0:
                print(
                    json.dumps(
                        {
                            "event": "E062_NON6_PROGRESS",
                            "unique": len(seen),
                            "raw": raw_body_count,
                            "improvements": len(improvements),
                            "nonterminal": len(nonterminal),
                            "at_utc": utc_now(),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
    payload = {
        "schema": "zmd_zero_condition_e062_non6_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "raw_body_changing_alternative_count": raw_body_count,
        "unique_body_geometry_count": len(seen),
        "same_mode_count_by_facility_type": dict(sorted(same_mode_counts.items())),
        "signature_invariant_same_mode_count": invariant_same_modes,
        "explicit_same_mode_solve_count": explicit_same_modes,
        "status_counts": dict(sorted(status_counts.items())),
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "strict_improvements": improvements,
        "nonterminal_candidates": nonterminal,
        "elapsed_seconds": time.monotonic() - started,
        "ledger_effect": "none",
    }
    dump_exclusive(NON6_PATH, payload)
    return payload


def scan_six4(
    *,
    e061: Any,
    base: Mapping[str, Any],
    mode_map: Mapping[tuple[tuple[int, int], ...], Sequence[int]],
    runner_sha256: str,
) -> dict[str, Any]:
    if SIX4_PATH.exists():
        payload = load_json(SIX4_PATH)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E062 6x4 checkpoint")
        return payload
    seen: dict[tuple[Any, ...], int] = {}
    raw_body_count = 0
    status_counts: Counter[str] = Counter()
    objective_distribution: Counter[int] = Counter()
    improvements: list[dict[str, Any]] = []
    nonterminal: list[dict[str, Any]] = []
    started = time.monotonic()
    for instance_id, row in sorted(base["solution"].items()):
        if str(row["facility_type"]) != e061.SIX4:
            continue
        for alternative in e061.enumerate_alternatives(
            base=base,
            instance_id=instance_id,
        ):
            if bool(alternative["same_footprint"]):
                continue
            raw_body_count += 1
            old_cells = tuple(
                sorted(
                    base["e014"].pose_cells(
                        base["inputs"]["pools"],
                        e061.SIX4,
                        int(row["pose_idx"]),
                    )
                )
            )
            new_cells = tuple(
                sorted((int(x), int(y)) for x, y in alternative["occupied_cells"])
            )
            key = (old_cells, new_cells)
            if key in seen:
                seen[key] += 1
                continue
            seen[key] = 0
            routing_context = base["build_routing_context"](
                alternative["solution"],
                base["inputs"]["pools"],
                70,
                70,
            )
            descriptors = e061.dynamic_descriptors(
                candidate=alternative["solution"],
                base=base,
                mode_map=mode_map,
            )
            solve = solve_qiaoyu_hard(
                options=e061.map_descriptors(
                    descriptors=descriptors,
                    routing_context=routing_context,
                ),
                sink_space=e061.generic_sink_space(
                    candidate=alternative["solution"],
                    routing_context=routing_context,
                    inputs=base["inputs"],
                    is_port_front_usable=base["is_port_front_usable"],
                ),
                random_seed=62300 + len(seen),
            )
            status_counts[str(solve["status"])] += 1
            if solve.get("objective") is not None:
                objective_distribution[int(solve["objective"])] += 1
                if int(solve["objective"]) < BASELINE_OBJECTIVE:
                    improvements.append(
                        candidate_record(
                            instance_id=instance_id,
                            row=row,
                            alternative=alternative,
                            solve=solve,
                            alias_count=int(seen[key]),
                        )
                    )
            elif solve["status"] not in {"INFEASIBLE", "STRUCTURAL_EMPTY"}:
                nonterminal.append(
                    candidate_record(
                        instance_id=instance_id,
                        row=row,
                        alternative=alternative,
                        solve=solve,
                        alias_count=int(seen[key]),
                    )
                )
            if len(seen) % 25 == 0:
                print(
                    json.dumps(
                        {
                            "event": "E062_SIX4_PROGRESS",
                            "unique": len(seen),
                            "raw": raw_body_count,
                            "improvements": len(improvements),
                            "nonterminal": len(nonterminal),
                            "at_utc": utc_now(),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
    payload = {
        "schema": "zmd_zero_condition_e062_six4_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "raw_body_changing_alternative_count": raw_body_count,
        "unique_body_geometry_count": len(seen),
        "same_mode_disposition": (
            "All 6x4 same-body modes are already simultaneous in the corrected "
            "E060 baseline tradeoff value two."
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "strict_improvements": improvements,
        "nonterminal_candidates": nonterminal,
        "elapsed_seconds": time.monotonic() - started,
        "ledger_effect": "none",
    }
    dump_exclusive(SIX4_PATH, payload)
    return payload


def run() -> dict[str, Any]:
    identity = verify_identity()
    e061 = import_module("zmd_e062_e061", E061_RUNNER)
    base = e061.reconstruct()
    bodies = e061.body_rows(
        base["solution"],
        base["inputs"]["pools"],
        base["e014"],
    )
    mode_map = e061.modes_by_footprint(base["inputs"]["pools"])
    descriptors = e061.raw_descriptors(
        bodies=bodies,
        mode_map=mode_map,
        pools=base["inputs"]["pools"],
        enumerate_patterns=base["enumerate_patterns"],
    )
    routing_context = base["build_routing_context"](
        base["solution"],
        base["inputs"]["pools"],
        70,
        70,
    )
    calibration = solve_qiaoyu_hard(
        options=e061.map_descriptors(
            descriptors=descriptors,
            routing_context=routing_context,
        ),
        sink_space=e061.generic_sink_space(
            candidate=base["solution"],
            routing_context=routing_context,
            inputs=base["inputs"],
            is_port_front_usable=base["is_port_front_usable"],
        ),
        random_seed=62001,
    )
    if calibration["status"] != "OPTIMAL" or int(
        calibration["objective"]
    ) != BASELINE_OBJECTIVE:
        raise RuntimeError(f"E062 baseline calibration drift: {calibration}")
    non6 = scan_non6(
        e061=e061,
        base=base,
        descriptors=descriptors,
        runner_sha256=str(identity["runner_sha256"]),
    )
    six4 = scan_six4(
        e061=e061,
        base=base,
        mode_map=mode_map,
        runner_sha256=str(identity["runner_sha256"]),
    )
    improvements = [
        *non6["strict_improvements"],
        *six4["strict_improvements"],
    ]
    nonterminal = [
        *non6["nonterminal_candidates"],
        *six4["nonterminal_candidates"],
    ]
    distribution: Counter[int] = Counter()
    for payload in (non6, six4):
        for key, value in payload["objective_distribution"].items():
            distribution[int(key)] += int(value)
    if nonterminal:
        verdict = "ONE_OBJECT_TRADEOFF_ATLAS_NONTERMINAL"
        decision = "CONTINUE_NONTERMINAL_TRADEOFF_SOLVES"
    elif improvements:
        verdict = "ONE_OBJECT_TRADEOFF_NEAR_MISSES_FOUND"
        decision = "BUILD_COMPLEMENTARY_TWO_OBJECT_RELATIONS"
    else:
        verdict = "NO_ONE_OBJECT_DIRECTIONAL_IMPROVEMENT"
        decision = "DERIVE_PAIR_FROM_COMPONENT_BOUNDARY_INTERACTION"
    return {
        "schema": "zmd_zero_condition_e062_one_object_tradeoff_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "baseline": calibration,
        "non6_atlas_path": str(NON6_PATH.relative_to(ROOT)),
        "non6_atlas_sha256": sha256_file(NON6_PATH),
        "non6_atlas": non6,
        "six4_atlas_path": str(SIX4_PATH.relative_to(ROOT)),
        "six4_atlas_sha256": sha256_file(SIX4_PATH),
        "six4_atlas": six4,
        "total_objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "strict_improvement_count": len(improvements),
        "strict_improvements": improvements,
        "nonterminal_count": len(nonterminal),
        "nonterminal_candidates": nonterminal,
        "decision": decision,
        "truth_boundary": (
            "E055 first-zero state with exactly one selected-object pose change; "
            "qiaoyu zero hard and fine mismatch minimized in the corrected target-"
            "signature relaxation."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E062 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "distribution": result["total_objective_distribution"],
                    "improvements": result["strict_improvement_count"],
                    "nonterminal": result["nonterminal_count"],
                    "decision": result["decision"],
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e062_one_object_tradeoff_atlas_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
