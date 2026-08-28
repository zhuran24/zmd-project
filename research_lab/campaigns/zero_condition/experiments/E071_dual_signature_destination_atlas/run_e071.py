#!/usr/bin/env python3
"""E071: destination-conditioned atlas for E070's target-36 dual signature."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import inspect
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
    "E071_dual_signature_destination_atlas/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ATLAS_PATH = OUT / "DESTINATION_ATLAS.json"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E061_RUNNER = (
    EXPERIMENT_ROOT / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = EXPERIMENT_ROOT / "E062_one_object_tradeoff_atlas/run_e062.py"
E063_RUNNER = (
    EXPERIMENT_ROOT / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E069_RUNNER = EXPERIMENT_ROOT / "E069_six4_near_miss_complete_face/run_e069.py"
E070_RUNNER = EXPERIMENT_ROOT / "E070_dual_filling_signature_targets/run_e070.py"

E069_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/RESULT.json"
)
E069_FACE = E069_RESULT.parent / "FACE_CONTEXT.json"
E070_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E070_dual_filling_signature_targets/run-003/RESULT.json"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e071_source_cache_v1",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "297000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E069_RESULT: "38cd4ec548bd18ad70b3549e04d225a4e4a226489bd8ed111c9f72554640769f",
    E069_FACE: "9265a64a4caaddbf67ff0925e5b984bb789ab39ff7a455acfb1ae7ee3fcdf584",
    E070_RESULT: "1fd35529e6f92eb1f55b2411b8ac0f5a650c2f576ef1e95c67056849e7e4df9c",
}

FILLING = "filling_capsule"
TARGET_FINE_COMPONENT = 36
TARGET_QIAOYU_COMPONENT = 29
EXPECTED_DESTINATION_COUNT = 38
EXPECTED_ACTUAL_DESTINATION = 24
EXPECTED_ACTUAL_POSE = 8064
EXPECTED_ACTUAL_OPTION_INDEX = 33
SOLVE_SECONDS = 30.0
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
        ).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def encoded(value: Any) -> bytes:
    return (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def dump_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded(value))
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


def audit_module(module: Any, expected_path: Path) -> dict[str, Any]:
    expected = expected_path.resolve()
    functions: list[dict[str, str]] = []
    foreign: list[dict[str, str]] = []
    for name, value in sorted(vars(module).items()):
        if not inspect.isfunction(value) or value.__module__ != module.__name__:
            continue
        actual = Path(value.__code__.co_filename).resolve()
        record = {"name": str(name), "code_filename": str(actual)}
        functions.append(record)
        if actual != expected:
            foreign.append(record)
    if foreign:
        raise RuntimeError(f"foreign functions loaded for {expected_path}: {foreign[:10]}")
    return {
        "module": str(module.__name__),
        "source": str(expected_path.relative_to(ROOT)),
        "source_sha256": sha256_file(expected_path),
        "function_count": len(functions),
        "foreign_function_count": 0,
    }


def audit_nested_modules(prefixes: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, module in sorted(sys.modules.items()):
        if module is None or not any(name.startswith(prefix) for prefix in prefixes):
            continue
        file_value = getattr(module, "__file__", None)
        if not isinstance(file_value, str):
            continue
        path = Path(file_value).resolve()
        source = (
            Path(importlib.util.source_from_cache(str(path))).resolve()
            if path.suffix == ".pyc"
            else path
        )
        rows.append(audit_module(module, source))
    return rows


def verify_identity() -> dict[str, Any]:
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError(f"run E071 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E071 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"E071 requires a clean tracked worktree: {tracked_status}")
    mismatches = {
        key: {"expected": expected, "actual": os.environ.get(key)}
        for key, expected in EXPECTED_ENV.items()
        if os.environ.get(key) != expected
    }
    unexpected_exact = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected_exact:
        raise RuntimeError(
            f"environment mismatch: {mismatches}; unexpected={unexpected_exact}"
        )
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift: {path}: {actual} != {expected}")
    e070 = load_json(E070_RESULT)
    if e070.get("verdict") != "DUAL_FILLING_SIGNATURE_TARGETS_SUFFICIENT":
        raise RuntimeError("E071 E070 verdict drift")
    audit = e070["existing_signature_audit"]
    if (
        audit.get("exact_dual_targets") != [TARGET_FINE_COMPONENT]
        or int(audit.get("exact_dual_target_count", -1)) != 1
        or bool(audit.get("actual_parent_joint_zero_feasible"))
    ):
        raise RuntimeError(f"E071 E070 dual-signature audit drift: {audit}")
    current_e070_hash = sha256_file(E070_RUNNER)
    if str(e070["identity"]["runner_sha256"]) != current_e070_hash:
        raise RuntimeError("E071 current E070 runner differs from frozen E070 execution")
    current_e069_hash = sha256_file(E069_RUNNER)
    if str(e070["identity"]["checked_hashes"].get(str(E069_RUNNER))) != current_e069_hash:
        raise RuntimeError("E071 current E069 runner differs from E070 frozen input")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "current_e069_runner_sha256": current_e069_hash,
        "current_e070_runner_sha256": current_e070_hash,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": tracked_status,
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


def solve_configuration(
    *,
    e061: Any,
    options: Mapping[int, Sequence[tuple[Any, ...]]],
    sink_space: Mapping[str, Any],
    synthetic_destination: int | None,
    forced_actual: tuple[int, int] | None,
    random_seed: int,
) -> dict[str, Any]:
    if (synthetic_destination is None) == (forced_actual is None):
        raise ValueError("select exactly one of synthetic_destination or forced_actual")
    tagged: dict[int, list[dict[str, Any]]] = {}
    synthetic_vars: list[Any] = []
    for destination, rows in sorted(options.items()):
        values = [
            {
                "operation": str(operation),
                "pose_idx": int(pose_idx),
                "signature": tuple(tuple(int(x) for x in part) for part in signature),
                "synthetic": False,
                "source_option_index": int(option_index),
            }
            for option_index, (operation, pose_idx, signature) in enumerate(rows)
        ]
        if synthetic_destination == int(destination):
            values.append(
                {
                    "operation": FILLING,
                    "pose_idx": -710036,
                    "signature": ((TARGET_FINE_COMPONENT,), (), (TARGET_QIAOYU_COMPONENT,)),
                    "synthetic": True,
                    "source_option_index": None,
                }
            )
        tagged[int(destination)] = values

    if not sink_space["slots"] or any(not rows for rows in tagged.values()):
        return {
            "status": "STRUCTURAL_EMPTY",
            "synthetic_destination": synthetic_destination,
            "forced_actual": list(forced_actual) if forced_actual else None,
            "elapsed_seconds": 0.0,
            "branches": 0,
            "conflicts": 0,
        }

    model = cp_model.CpModel()
    x_vars: dict[tuple[int, int], Any] = {}
    for destination, rows in tagged.items():
        variables: list[Any] = []
        for option_index, option in enumerate(rows):
            variable = model.NewBoolVar(f"e071_x_{destination}_{option_index}")
            x_vars[(destination, option_index)] = variable
            variables.append(variable)
            if bool(option["synthetic"]):
                synthetic_vars.append(variable)
        model.AddExactlyOne(variables)
    if synthetic_destination is not None:
        if len(synthetic_vars) != 1:
            raise RuntimeError(
                f"E071 synthetic option count drift: {len(synthetic_vars)}"
            )
        model.Add(synthetic_vars[0] == 1)
    else:
        destination, source_option_index = forced_actual
        matching = [
            (option_index, option)
            for option_index, option in enumerate(tagged[int(destination)])
            if option["source_option_index"] == int(source_option_index)
        ]
        if len(matching) != 1:
            raise RuntimeError(f"E071 forced actual option drift: {matching}")
        model.Add(x_vars[(int(destination), int(matching[0][0]))] == 1)

    for operation, expected in e061.OPERATION_COUNTS.items():
        model.Add(
            cp_model.LinearExpr.Sum(
                [
                    x_vars[(destination, option_index)]
                    for destination, rows in tagged.items()
                    for option_index, option in enumerate(rows)
                    if str(option["operation"]) == operation
                ]
            )
            == int(expected)
        )

    components = sorted(
        {
            int(component)
            for rows in tagged.values()
            for option in rows
            for part in option["signature"]
            for component in part
        }
        | {int(value) for value in sink_space["components"]}
    )
    fine_sources: dict[int, Any] = {}
    fine_sinks: dict[int, Any] = {}
    qiaoyu_sources: dict[int, Any] = {}
    for component in components:
        fine_sources[component] = add_exact_or(
            model,
            name=f"e071_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in tagged.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][1])
            ],
        )
        fine_sinks[component] = add_exact_or(
            model,
            name=f"e071_sink_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in tagged.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][0])
            ],
        )
        qiaoyu_sources[component] = add_exact_or(
            model,
            name=f"e071_qiaoyu_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in tagged.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][2])
            ],
        )
    sink_component_vars = {
        int(component): model.NewBoolVar(f"e071_qsink_{component}")
        for component in sink_space["components"]
    }
    model.AddExactlyOne(list(sink_component_vars.values()))
    for component in components:
        model.Add(fine_sources[component] == fine_sinks[component])
        model.Add(
            qiaoyu_sources[component]
            == sink_component_vars.get(component, 0)
        )
    model.Add(cp_model.LinearExpr.Sum(list(fine_sources.values())) >= 1)
    model.Minimize(0)

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
        "synthetic_destination": synthetic_destination,
        "forced_actual": list(forced_actual) if forced_actual else None,
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "selected_qiaoyu_sink_component": None,
        "fine_components": None,
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result["selected_qiaoyu_sink_component"] = next(
            component
            for component, variable in sink_component_vars.items()
            if solver.Value(variable) == 1
        )
        result["fine_components"] = [
            component
            for component, variable in fine_sources.items()
            if solver.Value(variable) == 1
        ]
    return result


def actual_dual_identity(
    *,
    options: Mapping[int, Sequence[tuple[Any, ...]]],
    e070_result: Mapping[str, Any],
) -> dict[str, Any]:
    audit_rows = e070_result["existing_signature_audit"][
        "exact_dual_options_by_target"
    ][str(TARGET_FINE_COMPONENT)]
    if len(audit_rows) != 1:
        raise RuntimeError(f"E071 exact dual audit count drift: {len(audit_rows)}")
    audit = dict(audit_rows[0])
    matches: list[dict[str, Any]] = []
    for destination, rows in sorted(options.items()):
        for option_index, (operation, pose_idx, signature) in enumerate(rows):
            normalized = tuple(tuple(int(x) for x in part) for part in signature)
            if (
                str(operation) == FILLING
                and int(pose_idx) == EXPECTED_ACTUAL_POSE
                and normalized
                == ((TARGET_FINE_COMPONENT,), (), (TARGET_QIAOYU_COMPONENT,))
            ):
                matches.append(
                    {
                        "destination": int(destination),
                        "option_index": int(option_index),
                        "operation": str(operation),
                        "pose_idx": int(pose_idx),
                        "signature": [list(part) for part in normalized],
                    }
                )
    if len(matches) != 1:
        raise RuntimeError(f"E071 actual dual option drift: {matches}")
    actual = matches[0]
    if (
        int(actual["destination"]) != EXPECTED_ACTUAL_DESTINATION
        or int(actual["option_index"]) != EXPECTED_ACTUAL_OPTION_INDEX
        or int(audit["destination"]) != EXPECTED_ACTUAL_DESTINATION
        or int(audit["option_index"]) != EXPECTED_ACTUAL_OPTION_INDEX
        or int(audit["pose_idx"]) != EXPECTED_ACTUAL_POSE
    ):
        raise RuntimeError(f"E071 actual dual identity mismatch: {actual}/{audit}")
    return {"model_option": actual, "e070_audit": audit}


def real_filling_inventory(
    *,
    e061: Any,
    context: Mapping[str, Any],
    feasible_destinations: Sequence[int],
) -> dict[str, Any]:
    bodies = e061.body_rows(
        context["solution"],
        context["base"]["inputs"]["pools"],
        context["base"]["e014"],
    )
    feasible = {int(value) for value in feasible_destinations}
    by_destination: dict[str, dict[str, Any]] = {}
    for destination in sorted(context["options"]):
        body = bodies[int(destination)]
        categories: dict[str, list[dict[str, Any]]] = {
            "exact_dual": [],
            "qiaoyu_29_half": [],
            "fine_36_half": [],
            "neither": [],
        }
        for option_index, (operation, pose_idx, signature) in enumerate(
            context["options"][destination]
        ):
            if str(operation) != FILLING:
                continue
            fine_input = tuple(int(value) for value in signature[0])
            qiaoyu_output = tuple(int(value) for value in signature[2])
            has_fine = TARGET_FINE_COMPONENT in fine_input
            has_qiaoyu = TARGET_QIAOYU_COMPONENT in qiaoyu_output
            if has_fine and has_qiaoyu:
                category = "exact_dual"
            elif has_qiaoyu:
                category = "qiaoyu_29_half"
            elif has_fine:
                category = "fine_36_half"
            else:
                category = "neither"
            categories[category].append(
                {
                    "option_index": int(option_index),
                    "pose_idx": int(pose_idx),
                    "fine_input_components": list(fine_input),
                    "qiaoyu_output_components": list(qiaoyu_output),
                }
            )
        by_destination[str(destination)] = {
            "destination": int(destination),
            "source_instance_id": str(body["source_instance_id"]),
            "current_operation": str(body["current_operation"]),
            "current_pose_idx": int(body["current_pose_idx"]),
            "synthetic_destination_feasible": int(destination) in feasible,
            "categories": categories,
        }
    feasible_half_destinations = [
        int(destination)
        for destination, row in by_destination.items()
        if bool(row["synthetic_destination_feasible"])
        and (
            row["categories"]["qiaoyu_29_half"]
            or row["categories"]["fine_36_half"]
            or row["categories"]["exact_dual"]
        )
    ]
    return {
        "destinations": by_destination,
        "feasible_half_signature_destinations": sorted(
            feasible_half_destinations
        ),
        "feasible_half_signature_destination_count": len(
            feasible_half_destinations
        ),
        "inventory_digest": stable_digest(by_destination),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e061 = import_module("zmd_e071_e061", E061_RUNNER)
    e062 = import_module("zmd_e071_e062", E062_RUNNER)
    e063 = import_module("zmd_e071_e063", E063_RUNNER)
    e069 = import_module("zmd_e071_e069", E069_RUNNER)
    e070 = import_module("zmd_e071_e070", E070_RUNNER)
    direct_origins = [
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
        audit_module(e063, E063_RUNNER),
        audit_module(e069, E069_RUNNER),
        audit_module(e070, E070_RUNNER),
    ]
    context = e069.reconstruct_parent(e061, e062, e063)
    nested_origins = audit_nested_modules(
        (
            "zmd_e071_",
            "zmd_e061_",
            "zmd_e062_",
            "zmd_e063_",
            "zmd_e069_",
            "zmd_e070_",
        )
    )
    destinations = sorted(int(value) for value in context["options"])
    if destinations != list(range(EXPECTED_DESTINATION_COUNT)):
        raise RuntimeError(f"E071 destination identity drift: {destinations}")
    e070_result = load_json(E070_RESULT)
    actual_identity = actual_dual_identity(
        options=context["options"],
        e070_result=e070_result,
    )
    destination_results = [
        solve_configuration(
            e061=e061,
            options=context["options"],
            sink_space=context["sink_space"],
            synthetic_destination=destination,
            forced_actual=None,
            random_seed=71000 + destination,
        )
        for destination in destinations
    ]
    forced_actual_result = solve_configuration(
        e061=e061,
        options=context["options"],
        sink_space=context["sink_space"],
        synthetic_destination=None,
        forced_actual=(
            int(actual_identity["model_option"]["destination"]),
            int(actual_identity["model_option"]["option_index"]),
        ),
        random_seed=71999,
    )
    feasible_destinations = [
        int(row["synthetic_destination"])
        for row in destination_results
        if row["status"] in {"OPTIMAL", "FEASIBLE"}
    ]
    nonterminal = [
        row
        for row in destination_results
        if row["status"] not in {
            "OPTIMAL",
            "FEASIBLE",
            "INFEASIBLE",
            "STRUCTURAL_EMPTY",
        }
    ]
    inventory = real_filling_inventory(
        e061=e061,
        context=context,
        feasible_destinations=feasible_destinations,
    )
    atlas = {
        "schema": "zmd_zero_condition_e071_dual_signature_destination_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "target": {
            "operation": FILLING,
            "fine_input_component": TARGET_FINE_COMPONENT,
            "qiaoyu_output_component": TARGET_QIAOYU_COMPONENT,
        },
        "actual_dual_identity": actual_identity,
        "destination_results": destination_results,
        "forced_actual_result": forced_actual_result,
        "real_filling_inventory": inventory,
        "ledger_effect": "none",
    }
    dump_exclusive(ATLAS_PATH, atlas)

    actual_destination_feasible = (
        EXPECTED_ACTUAL_DESTINATION in feasible_destinations
    )
    if nonterminal:
        verdict = "DUAL_SIGNATURE_DESTINATION_ATLAS_NONTERMINAL"
        decision = "CONTINUE_ONLY_NONTERMINAL_DESTINATIONS"
    elif not feasible_destinations:
        verdict = "E070_FREE_DESTINATION_RESULT_INCONSISTENT"
        decision = "QUARANTINE_E070_AND_REPAIR_SYNTHETIC_MODEL"
    elif actual_destination_feasible or forced_actual_result["status"] in {
        "OPTIMAL",
        "FEASIBLE",
    }:
        verdict = "ACTUAL_DUAL_DESTINATION_CONTRADICTS_PARENT_MINIMUM"
        decision = "REPAIR_OPTION_IDENTITY_OR_PARENT_MODEL"
    else:
        verdict = "DUAL_SIGNATURE_DESTINATION_COMPATIBILITY_IDENTIFIED"
        decision = "SEARCH_DUAL_SIGNATURE_TRANSPORT_TO_FEASIBLE_DESTINATION"
    status_counts = Counter(str(row["status"]) for row in destination_results)
    return {
        "schema": "zmd_zero_condition_e071_dual_signature_destination_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "module_origin_audit": {
            "direct": direct_origins,
            "nested": nested_origins,
        },
        "target": atlas["target"],
        "actual_dual_identity": actual_identity,
        "destination_count": len(destination_results),
        "destination_status_counts": dict(sorted(status_counts.items())),
        "feasible_destination_count": len(feasible_destinations),
        "feasible_destinations": feasible_destinations,
        "actual_destination_feasible": actual_destination_feasible,
        "forced_actual_result": forced_actual_result,
        "nonterminal_count": len(nonterminal),
        "nonterminal_destinations": nonterminal,
        "real_filling_inventory": inventory,
        "destination_atlas_path": str(ATLAS_PATH.relative_to(ROOT)),
        "destination_atlas_sha256": sha256_file(ATLAS_PATH),
        "decision": decision,
        "truth_boundary": (
            "E069 fixed occupied geometry and corrected terminal-signature model, "
            "with either one target-36 synthetic filling option fixed to a single "
            "destination or the unique real pose-8064 dual option forced."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E071 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "feasible_destinations": result["feasible_destinations"],
                    "actual_destination": EXPECTED_ACTUAL_DESTINATION,
                    "actual_destination_feasible": result[
                        "actual_destination_feasible"
                    ],
                    "forced_actual_status": result["forced_actual_result"][
                        "status"
                    ],
                    "feasible_half_destinations": result[
                        "real_filling_inventory"
                    ]["feasible_half_signature_destinations"],
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
            "schema": "zmd_zero_condition_e071_dual_signature_destination_atlas_failure_v1",
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
