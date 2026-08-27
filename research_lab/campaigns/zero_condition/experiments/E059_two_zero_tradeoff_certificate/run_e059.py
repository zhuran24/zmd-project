#!/usr/bin/env python3
"""E059: compress E058 infeasibility into a tradeoff and geometry signature target."""

from __future__ import annotations

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
    "E059_two_zero_tradeoff_certificate/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E058_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E058_all6x4_terminal_signature_frontier/run-004/RESULT.json"
)
E058_CENSUS = E058_RESULT.with_name("SIGNATURE_CENSUS.json")
E058_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E058_all6x4_terminal_signature_frontier/run_e058.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "286000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E058_RESULT: "d1295cd0988e751512968d1ad248f3e6da53ce912f52f6f28820f491c6fe27b4",
    E058_CENSUS: "2af0d107eaba7a638047b42b0aab58f83a52c37008221692bb4b8e8cadf27b5d",
    E058_RUNNER: "0d90380eace78a7831a91bebf3148fbbf301be61e3352a6de6002e8b831820a9",
}

FILLING = "filling_capsule"
FINE_GRINDER = "grinder_fine_buckwheat"
CORE_COMPONENT = 15
SOLVE_SECONDS = 60.0
SOLVE_WORKERS = 8
ENUMERATION_CAP = 300


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
    result = load_json(E058_RESULT)
    if result.get("verdict") != "FIXED_GEOMETRY_6X4_TWO_ZERO_SIGNATURE_CONFLICT":
        raise RuntimeError("E059 E058 trigger verdict drift")
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


def model_options(
    census: Mapping[str, Any],
    *,
    collapse_other: bool,
    synthetic: Mapping[str, Any] | None = None,
) -> tuple[dict[int, list[dict[str, Any]]], dict[str, int]]:
    if collapse_other:
        e058 = import_module("zmd_e059_e058_options", E058_RUNNER)
        options, counts = e058.relaxed_options(census)
    else:
        options = {
            int(key): [dict(row) for row in value]
            for key, value in census["options_by_body"].items()
        }
        counts = {
            str(key): int(value)
            for key, value in census["operation_counts"].items()
        }
    if synthetic is not None:
        if collapse_other:
            raise RuntimeError("synthetic scan uses exact operation counts")
        for destination in options:
            option = {
                "destination": destination,
                "body_digest": census["bodies"][destination]["body_digest"],
                "source_instance_id": census["bodies"][destination][
                    "source_instance_id"
                ],
                "mode_index": -1,
                "pose_idx": -1,
                "operation": str(synthetic["operation"]),
                "fine_input_components": list(
                    synthetic.get("fine_input_components", [])
                ),
                "fine_output_components": list(
                    synthetic.get("fine_output_components", [])
                ),
                "qiaoyu_output_components": list(
                    synthetic.get("qiaoyu_output_components", [])
                ),
                "active_pattern_count": 0,
                "active_pattern_indices": [],
                "signature_digest": "synthetic_geometry_target",
                "synthetic": True,
            }
            options[destination].append(option)
    return options, counts


def build_model(
    census: Mapping[str, Any],
    *,
    collapse_other: bool,
    synthetic: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    options, operation_counts = model_options(
        census,
        collapse_other=collapse_other,
        synthetic=synthetic,
    )
    model = cp_model.CpModel()
    x_vars: dict[tuple[int, int], Any] = {}
    synthetic_vars: list[Any] = []
    for destination, rows in options.items():
        variables: list[Any] = []
        for option_index, option in enumerate(rows):
            variable = model.NewBoolVar(f"e059_x_{destination}_{option_index}")
            x_vars[(destination, option_index)] = variable
            variables.append(variable)
            if bool(option.get("synthetic")):
                synthetic_vars.append(variable)
        model.AddExactlyOne(variables)
    for operation, expected in sorted(operation_counts.items()):
        model.Add(
            cp_model.LinearExpr.Sum(
                [
                    x_vars[(destination, option_index)]
                    for destination, rows in options.items()
                    for option_index, option in enumerate(rows)
                    if str(option["operation"]) == operation
                ]
            )
            == int(expected)
        )
    if synthetic is not None:
        model.Add(cp_model.LinearExpr.Sum(synthetic_vars) == 1)

    components = sorted(
        {
            int(component)
            for rows in options.values()
            for option in rows
            for field in (
                "fine_input_components",
                "fine_output_components",
                "qiaoyu_output_components",
            )
            for component in option[field]
        }
        | {CORE_COMPONENT}
    )
    fine_sources: dict[int, Any] = {}
    fine_sinks: dict[int, Any] = {}
    qiaoyu_sources: dict[int, Any] = {}
    for component in components:
        fine_sources[component] = add_exact_or(
            model,
            name=f"e059_fine_src_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option["fine_output_components"])
            ],
        )
        fine_sinks[component] = add_exact_or(
            model,
            name=f"e059_fine_sink_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option["fine_input_components"])
            ],
        )
        qiaoyu_sources[component] = add_exact_or(
            model,
            name=f"e059_qiaoyu_src_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option["qiaoyu_output_components"])
            ],
        )
    fine_mismatch: dict[int, Any] = {}
    for component in components:
        variable = model.NewBoolVar(f"e059_fine_mismatch_{component}")
        source = fine_sources[component]
        sink = fine_sinks[component]
        model.Add(variable >= source - sink)
        model.Add(variable >= sink - source)
        model.Add(variable <= source + sink)
        model.Add(variable <= 2 - source - sink)
        fine_mismatch[component] = variable
    qiaoyu_mismatch: dict[int, Any] = {}
    for component in components:
        if component == CORE_COMPONENT:
            variable = model.NewBoolVar("e059_qiaoyu_missing_core")
            model.Add(variable + qiaoyu_sources[component] == 1)
        else:
            variable = qiaoyu_sources[component]
        qiaoyu_mismatch[component] = variable
    model.Add(cp_model.LinearExpr.Sum(list(fine_sources.values())) >= 1)
    model.Add(cp_model.LinearExpr.Sum(list(fine_sinks.values())) >= 1)
    return {
        "model": model,
        "options": options,
        "operation_counts": operation_counts,
        "x_vars": x_vars,
        "synthetic_vars": synthetic_vars,
        "components": components,
        "fine_sources": fine_sources,
        "fine_sinks": fine_sinks,
        "qiaoyu_sources": qiaoyu_sources,
        "fine_mismatch": fine_mismatch,
        "qiaoyu_mismatch": qiaoyu_mismatch,
    }


def configure_solver(*, seed: int, seconds: float = SOLVE_SECONDS) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = SOLVE_WORKERS
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(seed)
    return solver


def presence_payload(built: Mapping[str, Any], solver: cp_model.CpSolver) -> dict[str, Any]:
    return {
        "fine_source_components": [
            component
            for component, variable in built["fine_sources"].items()
            if solver.Value(variable) == 1
        ],
        "fine_sink_components": [
            component
            for component, variable in built["fine_sinks"].items()
            if solver.Value(variable) == 1
        ],
        "fine_mismatch_components": [
            component
            for component, variable in built["fine_mismatch"].items()
            if solver.Value(variable) == 1
        ],
        "qiaoyu_source_components": [
            component
            for component, variable in built["qiaoyu_sources"].items()
            if solver.Value(variable) == 1
        ],
        "qiaoyu_mismatch_count": sum(
            int(solver.Value(variable))
            for variable in built["qiaoyu_mismatch"].values()
        ),
    }


def solve_tradeoff(
    census: Mapping[str, Any],
    *,
    direction: str,
    collapse_other: bool,
    seed: int,
) -> dict[str, Any]:
    built = build_model(census, collapse_other=collapse_other)
    model = built["model"]
    if direction == "qiaoyu_hard_fine_min":
        for component, variable in built["qiaoyu_sources"].items():
            model.Add(variable == int(component == CORE_COMPONENT))
        objective = cp_model.LinearExpr.Sum(list(built["fine_mismatch"].values()))
    elif direction == "fine_hard_qiaoyu_min":
        for component in built["components"]:
            model.Add(
                built["fine_sources"][component]
                == built["fine_sinks"][component]
            )
        objective = cp_model.LinearExpr.Sum(
            list(built["qiaoyu_mismatch"].values())
        )
    else:
        raise ValueError(direction)
    model.Minimize(objective)
    solver = configure_solver(seed=seed)
    started = time.monotonic()
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "direction": direction,
        "collapse_other": collapse_other,
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
        result["objective"] = int(round(solver.ObjectiveValue()))
        result["presence"] = presence_payload(built, solver)
    return result


def enumerate_qiaoyu_hard_optimum(
    census: Mapping[str, Any],
    *,
    collapse_other: bool,
    optimum: int,
    seed: int,
) -> dict[str, Any]:
    built = build_model(census, collapse_other=collapse_other)
    model = built["model"]
    for component, variable in built["qiaoyu_sources"].items():
        model.Add(variable == int(component == CORE_COMPONENT))
    model.Add(
        cp_model.LinearExpr.Sum(list(built["fine_mismatch"].values()))
        == int(optimum)
    )
    solver = configure_solver(seed=seed, seconds=30.0)
    patterns: list[dict[str, Any]] = []
    for _index in range(ENUMERATION_CAP):
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {
                "status": solver.StatusName(status),
                "complete": status == cp_model.INFEASIBLE,
                "pattern_count": len(patterns),
                "patterns": patterns,
            }
        payload = presence_payload(built, solver)
        pattern = {
            "fine_source_components": payload["fine_source_components"],
            "fine_sink_components": payload["fine_sink_components"],
            "source_only_components": sorted(
                set(payload["fine_source_components"])
                - set(payload["fine_sink_components"])
            ),
            "sink_only_components": sorted(
                set(payload["fine_sink_components"])
                - set(payload["fine_source_components"])
            ),
        }
        patterns.append(pattern)
        literals: list[Any] = []
        source_set = set(payload["fine_source_components"])
        sink_set = set(payload["fine_sink_components"])
        for component in built["components"]:
            source = built["fine_sources"][component]
            sink = built["fine_sinks"][component]
            literals.append(source.Not() if component in source_set else source)
            literals.append(sink.Not() if component in sink_set else sink)
        model.AddBoolOr(literals)
    return {
        "status": "ENUMERATION_CAP",
        "complete": False,
        "pattern_count": len(patterns),
        "patterns": patterns,
    }


def solve_synthetic_repair(
    census: Mapping[str, Any],
    *,
    kind: str,
    component: int,
    seed: int,
) -> dict[str, Any]:
    if kind == "filling":
        synthetic = {
            "operation": FILLING,
            "fine_input_components": [component],
            "qiaoyu_output_components": [CORE_COMPONENT],
        }
    elif kind == "grinder":
        synthetic = {
            "operation": FINE_GRINDER,
            "fine_output_components": [component],
        }
    else:
        raise ValueError(kind)
    built = build_model(
        census,
        collapse_other=False,
        synthetic=synthetic,
    )
    model = built["model"]
    for component_id in built["components"]:
        model.Add(
            built["fine_sources"][component_id]
            == built["fine_sinks"][component_id]
        )
        model.Add(
            built["qiaoyu_sources"][component_id]
            == int(component_id == CORE_COMPONENT)
        )
    model.Minimize(
        cp_model.LinearExpr.Sum(
            [
                (destination + 1) * built["x_vars"][(destination, option_index)]
                for destination, rows in built["options"].items()
                for option_index, option in enumerate(rows)
                if bool(option.get("synthetic"))
            ]
        )
    )
    solver = configure_solver(seed=seed, seconds=30.0)
    started = time.monotonic()
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "kind": kind,
        "component": int(component),
        "status": status_name,
        "elapsed_seconds": elapsed,
        "best_bound": float(solver.BestObjectiveBound()),
        "selected_body": None,
        "presence": None,
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected = [
            destination
            for destination, rows in built["options"].items()
            for option_index, option in enumerate(rows)
            if bool(option.get("synthetic"))
            and solver.Value(built["x_vars"][(destination, option_index)]) == 1
        ]
        if len(selected) != 1:
            raise RuntimeError(f"synthetic repair extraction drift: {selected}")
        result["selected_body"] = int(selected[0])
        result["presence"] = presence_payload(built, solver)
    return result


def run() -> dict[str, Any]:
    identity = verify_identity()
    census = load_json(E058_CENSUS)
    tradeoffs = {
        "exact_qiaoyu_hard_fine_min": solve_tradeoff(
            census,
            direction="qiaoyu_hard_fine_min",
            collapse_other=False,
            seed=59001,
        ),
        "relaxed_qiaoyu_hard_fine_min": solve_tradeoff(
            census,
            direction="qiaoyu_hard_fine_min",
            collapse_other=True,
            seed=59002,
        ),
        "exact_fine_hard_qiaoyu_min": solve_tradeoff(
            census,
            direction="fine_hard_qiaoyu_min",
            collapse_other=False,
            seed=59003,
        ),
        "relaxed_fine_hard_qiaoyu_min": solve_tradeoff(
            census,
            direction="fine_hard_qiaoyu_min",
            collapse_other=True,
            seed=59004,
        ),
    }
    exact_q = tradeoffs["exact_qiaoyu_hard_fine_min"]
    relaxed_q = tradeoffs["relaxed_qiaoyu_hard_fine_min"]
    if exact_q["status"] != "OPTIMAL" or relaxed_q["status"] != "OPTIMAL":
        raise RuntimeError("E059 qiaoyu-hard tradeoff did not close")
    exact_face = enumerate_qiaoyu_hard_optimum(
        census,
        collapse_other=False,
        optimum=int(exact_q["objective"]),
        seed=59011,
    )
    relaxed_face = enumerate_qiaoyu_hard_optimum(
        census,
        collapse_other=True,
        optimum=int(relaxed_q["objective"]),
        seed=59012,
    )
    if not exact_face["complete"] or not relaxed_face["complete"]:
        raise RuntimeError("E059 qiaoyu-hard optimum-face enumeration nonterminal")
    exact_patterns = {
        (
            tuple(row["fine_source_components"]),
            tuple(row["fine_sink_components"]),
        )
        for row in exact_face["patterns"]
    }
    relaxed_patterns = {
        (
            tuple(row["fine_source_components"]),
            tuple(row["fine_sink_components"]),
        )
        for row in relaxed_face["patterns"]
    }
    source_only_class = sorted(
        {
            int(component)
            for row in exact_face["patterns"]
            for component in row["source_only_components"]
        }
    )
    sink_only_class = sorted(
        {
            int(component)
            for row in exact_face["patterns"]
            for component in row["sink_only_components"]
        }
    )
    common_source_components = sorted(
        set.intersection(
            *(
                set(row["fine_source_components"])
                for row in exact_face["patterns"]
            )
        )
    )
    common_sink_components = sorted(
        set.intersection(
            *(
                set(row["fine_sink_components"])
                for row in exact_face["patterns"]
            )
        )
    )
    filling_repairs = [
        solve_synthetic_repair(
            census,
            kind="filling",
            component=component,
            seed=59100 + component,
        )
        for component in source_only_class
    ]
    grinder_repairs = [
        solve_synthetic_repair(
            census,
            kind="grinder",
            component=component,
            seed=59200 + component,
        )
        for component in sink_only_class
    ]
    filling_feasible = [
        row for row in filling_repairs if row["status"] in {"OPTIMAL", "FEASIBLE"}
    ]
    grinder_feasible = [
        row for row in grinder_repairs if row["status"] in {"OPTIMAL", "FEASIBLE"}
    ]
    expected_tradeoff = (
        int(exact_q["objective"]) == 2
        and int(relaxed_q["objective"]) == 2
        and int(tradeoffs["exact_fine_hard_qiaoyu_min"]["objective"]) == 1
        and int(tradeoffs["relaxed_fine_hard_qiaoyu_min"]["objective"]) == 1
    )
    if (
        expected_tradeoff
        and exact_patterns == relaxed_patterns
        and filling_feasible
        and not grinder_feasible
    ):
        verdict = "TWO_ZERO_TRADEOFF_AND_FILLING_SIGNATURE_TARGET_EXACT"
        decision = "SEARCH_GEOMETRY_FOR_Q15_FILLING_INPUT_IN_SOURCE_CLASS"
    elif filling_feasible or grinder_feasible:
        verdict = "TWO_ZERO_SINGLE_SIGNATURE_TARGET_FOUND"
        decision = "SEARCH_GEOMETRY_FOR_FEASIBLE_SIGNATURE_CLASS"
    else:
        verdict = "TWO_ZERO_REQUIRES_MULTI_SIGNATURE_OR_COMPONENT_CHANGE"
        decision = "BUILD_TWO_BODY_OR_COMPONENT_PARTITION_PROPOSER"
    return {
        "schema": "zmd_zero_condition_e059_tradeoff_certificate_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "tradeoffs": tradeoffs,
        "qiaoyu_hard_optimum_face": {
            "exact": exact_face,
            "relaxed": relaxed_face,
            "exact_relaxed_pattern_sets_equal": exact_patterns == relaxed_patterns,
            "common_source_components": common_source_components,
            "common_sink_components": common_sink_components,
            "source_only_component_class": source_only_class,
            "sink_only_component_class": sink_only_class,
        },
        "single_signature_repairs": {
            "filling_capsule": filling_repairs,
            "grinder_fine_buckwheat": grinder_repairs,
            "feasible_filling_components": [
                int(row["component"]) for row in filling_feasible
            ],
            "feasible_grinder_components": [
                int(row["component"]) for row in grinder_feasible
            ],
        },
        "decision": decision,
        "truth_boundary": (
            "E058 fixed component partition and terminal-signature relaxation. "
            "Synthetic repair options are proposal-only and do not assert that a "
            "legal body relocation realizes the requested signature."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E059 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "qiaoyu_hard_fine_min": result["tradeoffs"][
                        "exact_qiaoyu_hard_fine_min"
                    ]["objective"],
                    "fine_hard_qiaoyu_min": result["tradeoffs"][
                        "exact_fine_hard_qiaoyu_min"
                    ]["objective"],
                    "pattern_count": result["qiaoyu_hard_optimum_face"][
                        "exact"
                    ]["pattern_count"],
                    "source_only_class": result["qiaoyu_hard_optimum_face"][
                        "source_only_component_class"
                    ],
                    "sink_only_class": result["qiaoyu_hard_optimum_face"][
                        "sink_only_component_class"
                    ],
                    "filling_targets": result["single_signature_repairs"][
                        "feasible_filling_components"
                    ],
                    "grinder_targets": result["single_signature_repairs"][
                        "feasible_grinder_components"
                    ],
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
            "schema": "zmd_zero_condition_e059_tradeoff_certificate_failure_v1",
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
