#!/usr/bin/env python3
"""E070: test one hypothetical dual filling signature on the E069 face."""

from __future__ import annotations

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
    "E070_dual_filling_signature_targets/run-002"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
TARGET_ATLAS_PATH = OUT / "TARGET_ATLAS.json"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E061_RUNNER = (
    EXPERIMENT_ROOT / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = EXPERIMENT_ROOT / "E062_one_object_tradeoff_atlas/run_e062.py"
E063_RUNNER = (
    EXPERIMENT_ROOT / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E069_RUNNER = EXPERIMENT_ROOT / "E069_six4_near_miss_complete_face/run_e069.py"
E069_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/RESULT.json"
)
E069_PARENT = E069_RESULT.parent / "PARENT_SOLUTION.json"
E069_FACE = E069_RESULT.parent / "FACE_CONTEXT.json"

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e070_source_cache_v2",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "296000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E069_RUNNER: "e71e8bd00d5238fc86dfbfb5eab36e9acf9561e87e626b57ba5ab2e0982a2367",
    E069_RESULT: "38cd4ec548bd18ad70b3549e04d225a4e4a226489bd8ed111c9f72554640769f",
    E069_PARENT: "6eb5b4708fb616ab5d03c126eb8603626fd50180d78fa10be64a2688538b4137",
    E069_FACE: "9265a64a4caaddbf67ff0925e5b984bb789ab39ff7a455acfb1ae7ee3fcdf584",
}

FILLING = "filling_capsule"
TARGET_QIAOYU_COMPONENT = 29
EXPECTED_TARGETS = (1, 4, 8, 12, 17, 21, 25, 29, 35, 36, 39, 60)
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
        raise RuntimeError(f"run E070 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E070 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"E070 requires a clean tracked worktree: {tracked_status}")
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
    face = load_json(E069_FACE)["face"]
    if tuple(face["unmatched_components"]) != EXPECTED_TARGETS:
        raise RuntimeError(f"E070 target face drift: {face['unmatched_components']}")
    if tuple(face["qiaoyu_sink_components"]) != (TARGET_QIAOYU_COMPONENT,):
        raise RuntimeError(f"E070 qiaoyu sink drift: {face['qiaoyu_sink_components']}")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
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


def solve_target(
    *,
    e061: Any,
    options: Mapping[int, Sequence[tuple[Any, ...]]],
    sink_space: Mapping[str, Any],
    target_component: int,
    random_seed: int,
) -> dict[str, Any]:
    tagged: dict[int, list[dict[str, Any]]] = {}
    synthetic_pose = -700000 - int(target_component)
    for destination, rows in options.items():
        values = [
            {
                "operation": str(operation),
                "pose_idx": int(pose_idx),
                "signature": tuple(tuple(int(x) for x in part) for part in signature),
                "synthetic": False,
            }
            for operation, pose_idx, signature in rows
        ]
        values.append(
            {
                "operation": FILLING,
                "pose_idx": synthetic_pose,
                "signature": ((int(target_component),), (), (TARGET_QIAOYU_COMPONENT,)),
                "synthetic": True,
            }
        )
        tagged[int(destination)] = values
    if not sink_space["slots"] or any(not rows for rows in tagged.values()):
        return {
            "status": "STRUCTURAL_EMPTY",
            "target_component": int(target_component),
            "elapsed_seconds": 0.0,
            "branches": 0,
            "conflicts": 0,
        }

    model = cp_model.CpModel()
    x_vars: dict[tuple[int, int], Any] = {}
    synthetic_vars: list[Any] = []
    for destination, rows in tagged.items():
        variables: list[Any] = []
        for option_index, option in enumerate(rows):
            variable = model.NewBoolVar(f"e070_x_{destination}_{option_index}")
            x_vars[(destination, option_index)] = variable
            variables.append(variable)
            if bool(option["synthetic"]):
                synthetic_vars.append(variable)
        model.AddExactlyOne(variables)
    model.Add(cp_model.LinearExpr.Sum(synthetic_vars) == 1)
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
            name=f"e070_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in tagged.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][1])
            ],
        )
        fine_sinks[component] = add_exact_or(
            model,
            name=f"e070_sink_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in tagged.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][0])
            ],
        )
        qiaoyu_sources[component] = add_exact_or(
            model,
            name=f"e070_qiaoyu_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in tagged.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][2])
            ],
        )
    sink_component_vars = {
        int(component): model.NewBoolVar(f"e070_qsink_{component}")
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
    model.Minimize(
        cp_model.LinearExpr.Sum(
            [
                (destination + 1) * x_vars[(destination, option_index)]
                for destination, rows in tagged.items()
                for option_index, option in enumerate(rows)
                if bool(option["synthetic"])
            ]
        )
    )
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
        "target_component": int(target_component),
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "selected_destination": None,
        "selected_qiaoyu_sink_component": None,
        "fine_components": None,
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result["selected_destination"] = next(
            destination
            for destination, rows in tagged.items()
            for option_index, option in enumerate(rows)
            if bool(option["synthetic"])
            and solver.Value(x_vars[(destination, option_index)]) == 1
        )
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


def existing_signature_audit(
    *,
    e061: Any,
    context: Mapping[str, Any],
    targets: Sequence[int],
) -> dict[str, Any]:
    bodies = e061.body_rows(
        context["solution"],
        context["base"]["inputs"]["pools"],
        context["base"]["e014"],
    )
    rows: list[dict[str, Any]] = []
    exact_dual_by_target: dict[str, list[dict[str, Any]]] = {
        str(target): [] for target in targets
    }
    fine_input_by_target: dict[str, list[dict[str, Any]]] = {
        str(target): [] for target in targets
    }
    qiaoyu_29: list[dict[str, Any]] = []
    for destination, options in sorted(context["options"].items()):
        body = bodies[int(destination)]
        for option_index, (operation, pose_idx, signature) in enumerate(options):
            if str(operation) != FILLING:
                continue
            fine_input = tuple(int(value) for value in signature[0])
            qiaoyu_output = tuple(int(value) for value in signature[2])
            record = {
                "destination": int(destination),
                "option_index": int(option_index),
                "source_instance_id": str(body["source_instance_id"]),
                "current_operation": str(body["current_operation"]),
                "pose_idx": int(pose_idx),
                "fine_input_components": list(fine_input),
                "qiaoyu_output_components": list(qiaoyu_output),
            }
            rows.append(record)
            if TARGET_QIAOYU_COMPONENT in qiaoyu_output:
                qiaoyu_29.append(record)
            for target in targets:
                if int(target) in fine_input:
                    fine_input_by_target[str(target)].append(record)
                    if TARGET_QIAOYU_COMPONENT in qiaoyu_output:
                        exact_dual_by_target[str(target)].append(record)
    recomputed_exact_dual: dict[str, list[dict[str, Any]]] = {}
    for target in targets:
        key = str(target)
        recomputed_exact_dual[key] = [
            row
            for row in qiaoyu_29
            if int(target) in set(row["fine_input_components"])
        ]
        if stable_digest(recomputed_exact_dual[key]) != stable_digest(
            exact_dual_by_target[key]
        ):
            raise RuntimeError(f"E070 exact-dual audit mismatch for target {target}")
    exact_dual_targets = [
        int(target)
        for target, values in recomputed_exact_dual.items()
        if values
    ]
    return {
        "filling_option_count": len(rows),
        "qiaoyu_29_option_count": len(qiaoyu_29),
        "qiaoyu_29_options": qiaoyu_29,
        "fine_input_options_by_target": fine_input_by_target,
        "exact_dual_options_by_target": recomputed_exact_dual,
        "exact_dual_option_count": sum(
            len(values) for values in recomputed_exact_dual.values()
        ),
        "exact_dual_targets": exact_dual_targets,
        "exact_dual_target_count": len(exact_dual_targets),
        "actual_parent_joint_minimum": 1,
        "actual_parent_joint_zero_feasible": False,
        "audit_digest": stable_digest(rows),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e061 = import_module("zmd_e070_e061", E061_RUNNER)
    e062 = import_module("zmd_e070_e062", E062_RUNNER)
    e063 = import_module("zmd_e070_e063", E063_RUNNER)
    e069 = import_module("zmd_e070_e069", E069_RUNNER)
    direct_origins = [
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
        audit_module(e063, E063_RUNNER),
        audit_module(e069, E069_RUNNER),
    ]
    context = e069.reconstruct_parent(e061, e062, e063)
    nested_origins = audit_nested_modules(
        (
            "zmd_e070_",
            "zmd_e061_",
            "zmd_e062_",
            "zmd_e063_",
            "zmd_e069_",
        )
    )
    summary = e069.face_summary(context["face"])
    targets = [int(value) for value in summary["unmatched_components"]]
    if tuple(targets) != EXPECTED_TARGETS:
        raise RuntimeError(f"E070 reconstructed target drift: {targets}")
    target_results = [
        solve_target(
            e061=e061,
            options=context["options"],
            sink_space=context["sink_space"],
            target_component=target,
            random_seed=70000 + target,
        )
        for target in targets
    ]
    signature_audit = existing_signature_audit(
        e061=e061,
        context=context,
        targets=targets,
    )
    atlas = {
        "schema": "zmd_zero_condition_e070_dual_signature_target_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "parent_face_digest": str(summary["face_digest"]),
        "target_qiaoyu_component": TARGET_QIAOYU_COMPONENT,
        "target_results": target_results,
        "existing_signature_audit": signature_audit,
        "ledger_effect": "none",
    }
    dump_exclusive(TARGET_ATLAS_PATH, atlas)

    feasible = [
        row for row in target_results if row["status"] in {"OPTIMAL", "FEASIBLE"}
    ]
    nonterminal = [
        row
        for row in target_results
        if row["status"] not in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "STRUCTURAL_EMPTY"}
    ]
    if nonterminal:
        verdict = "DUAL_FILLING_SIGNATURE_TARGETS_NONTERMINAL"
        decision = "CONTINUE_ONLY_NONTERMINAL_SIGNATURE_TARGETS"
    elif feasible:
        verdict = "DUAL_FILLING_SIGNATURE_TARGETS_SUFFICIENT"
        decision = "SEARCH_PHYSICAL_DUAL_SIGNATURE_RELATIONS"
    else:
        verdict = "DUAL_FILLING_SIGNATURE_HYPOTHESIS_REFUTED"
        decision = "DERIVE_HIGHER_ORDER_TERMINAL_RELATION"
    return {
        "schema": "zmd_zero_condition_e070_dual_filling_signature_targets_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "module_origin_audit": {
            "direct": direct_origins,
            "nested": nested_origins,
        },
        "parent_face": summary,
        "target_atlas_path": str(TARGET_ATLAS_PATH.relative_to(ROOT)),
        "target_atlas_sha256": sha256_file(TARGET_ATLAS_PATH),
        "target_count": len(target_results),
        "feasible_target_count": len(feasible),
        "feasible_target_components": [
            int(row["target_component"]) for row in feasible
        ],
        "nonterminal_count": len(nonterminal),
        "target_results": target_results,
        "existing_signature_audit": signature_audit,
        "decision": decision,
        "truth_boundary": (
            "E069 fixed occupied geometry with exactly one hypothetical tagged "
            "filling-capsule signature, exact 38-body operation counts, actual "
            "generic qiaoyu sink choice, and terminal-signature equality only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E070 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "targets": result["target_count"],
                    "feasible": result["feasible_target_count"],
                    "feasible_components": result["feasible_target_components"],
                    "existing_dual_targets": result["existing_signature_audit"][
                        "exact_dual_target_count"
                    ],
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
            "schema": "zmd_zero_condition_e070_dual_filling_signature_targets_failure_v1",
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
