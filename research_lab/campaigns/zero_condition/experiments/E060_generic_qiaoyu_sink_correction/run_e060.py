#!/usr/bin/env python3
"""E060: restore generic qiaoyu sink choice in the E058/E059 signature model."""

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
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E060_generic_qiaoyu_sink_correction/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E055_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E055_causal_pair_assignment_frontier/run-002/RESULT.json"
)
E055_ASSIGNMENT = E055_RESULT.with_name("BEST_ASSIGNMENT.json")
E055_WITNESS = E055_RESULT.with_name("BEST_JOINT_WITNESS.json")
E056_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E056_causal_pair_mode_frontier/run_e056.py"
)
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
E059_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E059_two_zero_tradeoff_certificate/run-001/RESULT.json"
)
E059_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E059_two_zero_tradeoff_certificate/run_e059.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "287000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E055_RESULT: "5a81cd6c58151643b345a888f8bd782ba9c5bbdfe00c21e5ac2beccc90576efa",
    E055_ASSIGNMENT: "bf6d1cfcd4c6aaf649a16b9513044b2023b5a9a1a5b39267ebcaad15ffe2c46b",
    E055_WITNESS: "3b36ad647149af238567b3746e165fc60fbd107d47b10d8ba92bf15e4e2ab559",
    E056_RUNNER: "840a30a26e25c485e71b4891dbc68dc9e2c18d8608ffcc0404eda512d17d9e34",
    E058_RESULT: "d1295cd0988e751512968d1ad248f3e6da53ce912f52f6f28820f491c6fe27b4",
    E058_CENSUS: "2af0d107eaba7a638047b42b0aab58f83a52c37008221692bb4b8e8cadf27b5d",
    E058_RUNNER: "0d90380eace78a7831a91bebf3148fbbf301be61e3352a6de6002e8b831820a9",
    E059_RESULT: "c1404d1b41b5b6dd3069b9692387d35ab5962bfee0d0b3dfcc0d970915c7daff",
    E059_RUNNER: "f93eedfc989e81184593be94c310a730b4e53f6daa8518c87ae517b1e6ce1504",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

QIAOYU = "qiaoyu_capsule"
FILLING = "filling_capsule"
FINE_GRINDER = "grinder_fine_buckwheat"
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


def generic_qiaoyu_sink_slots() -> dict[str, Any]:
    from src.models.routing_binding_context import (
        build_routing_binding_context,
        is_port_front_usable,
    )

    e056 = import_module("zmd_e060_e056", E056_RUNNER)
    context = e056.reconstruct()
    solution = context["warm_solution"]
    inputs = context["base"]["inputs"]
    routing_context = build_routing_binding_context(
        solution,
        inputs["pools"],
        70,
        70,
    )
    capacity_map = inputs["plan"]["generic_input_slots_by_operation"]
    slots: list[dict[str, Any]] = []
    for instance_id, row in sorted(solution.items()):
        operation = str(row.get("operation_type", ""))
        declared = int(capacity_map.get(operation, 0))
        if declared <= 0:
            continue
        facility_type = str(row["facility_type"])
        pose_idx = int(row["pose_idx"])
        pose = inputs["pools"][facility_type][pose_idx]
        ports = list(pose.get("input_port_cells", []) or [])
        if len(ports) != declared:
            raise RuntimeError(
                f"generic-input capacity drift: {instance_id}/{operation}/"
                f"{len(ports)} != {declared}"
            )
        for local_index, port in enumerate(ports):
            if not is_port_front_usable(port, routing_context, instance_id):
                continue
            cell = (int(port["x"]), int(port["y"]))
            component = routing_context.component_by_cell.get(cell)
            if component is None:
                raise RuntimeError(f"usable generic sink lacks component: {cell}")
            slots.append(
                {
                    "slot_id": f"{instance_id}:in:{local_index}",
                    "instance_id": str(instance_id),
                    "operation_type": operation,
                    "facility_type": facility_type,
                    "pose_idx": pose_idx,
                    "x": cell[0],
                    "y": cell[1],
                    "dir": str(port["dir"]),
                    "component": int(component),
                }
            )
    if len(slots) < 2:
        raise RuntimeError("insufficient generic-input slots for qiaoyu and valley battery")
    required = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )["required_generic_inputs"]
    if int(required.get(QIAOYU, 0)) != 1:
        raise RuntimeError("qiaoyu generic-input requirement drift")
    return {
        "slots": slots,
        "slot_count": len(slots),
        "components": sorted({int(row["component"]) for row in slots}),
        "component_slot_counts": {
            str(component): sum(
                int(row["component"]) == component for row in slots
            )
            for component in sorted({int(row["component"]) for row in slots})
        },
        "provider_instances": sorted({str(row["instance_id"]) for row in slots}),
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


def build_corrected(
    census: Mapping[str, Any],
    sink_payload: Mapping[str, Any],
    *,
    collapse_other: bool,
    synthetic: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    e059 = import_module("zmd_e060_e059_builder", E059_RUNNER)
    built = e059.build_model(
        census,
        collapse_other=collapse_other,
        synthetic=synthetic,
    )
    model = built["model"]
    sink_slot_vars: dict[str, Any] = {}
    for row in sink_payload["slots"]:
        slot_id = str(row["slot_id"])
        sink_slot_vars[slot_id] = model.NewBoolVar(
            f"e060_qiaoyu_sink_{slot_id.replace(':', '_')}"
        )
    model.AddExactlyOne(list(sink_slot_vars.values()))
    sink_presence: dict[int, Any] = {}
    all_components = sorted(
        set(int(value) for value in built["components"])
        | set(int(value) for value in sink_payload["components"])
    )
    for component in all_components:
        contributors = [
            sink_slot_vars[str(row["slot_id"])]
            for row in sink_payload["slots"]
            if int(row["component"]) == component
        ]
        sink_presence[component] = add_exact_or(
            model,
            name=f"e060_qiaoyu_sink_component_{component}",
            contributors=contributors,
        )
        if component not in built["qiaoyu_sources"]:
            source = model.NewBoolVar(f"e060_absent_qiaoyu_source_{component}")
            model.Add(source == 0)
            built["qiaoyu_sources"][component] = source
        if component not in built["fine_sources"]:
            source = model.NewBoolVar(f"e060_absent_fine_source_{component}")
            sink = model.NewBoolVar(f"e060_absent_fine_sink_{component}")
            mismatch = model.NewBoolVar(f"e060_absent_fine_mismatch_{component}")
            model.Add(source == 0)
            model.Add(sink == 0)
            model.Add(mismatch == 0)
            built["fine_sources"][component] = source
            built["fine_sinks"][component] = sink
            built["fine_mismatch"][component] = mismatch
    qiaoyu_mismatch: dict[int, Any] = {}
    for component in all_components:
        variable = model.NewBoolVar(f"e060_qiaoyu_mismatch_{component}")
        source = built["qiaoyu_sources"][component]
        sink = sink_presence[component]
        model.Add(variable >= source - sink)
        model.Add(variable >= sink - source)
        model.Add(variable <= source + sink)
        model.Add(variable <= 2 - source - sink)
        qiaoyu_mismatch[component] = variable
    built.update(
        {
            "components": all_components,
            "sink_slot_vars": sink_slot_vars,
            "sink_presence": sink_presence,
            "qiaoyu_mismatch_corrected": qiaoyu_mismatch,
        }
    )
    return built


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
    selected_slots = [
        slot_id
        for slot_id, variable in built["sink_slot_vars"].items()
        if solver.Value(variable) == 1
    ]
    if len(selected_slots) != 1:
        raise RuntimeError(f"qiaoyu sink-slot extraction drift: {selected_slots}")
    return {
        "fine_source_components": [
            component
            for component in built["components"]
            if solver.Value(built["fine_sources"][component]) == 1
        ],
        "fine_sink_components": [
            component
            for component in built["components"]
            if solver.Value(built["fine_sinks"][component]) == 1
        ],
        "fine_mismatch_components": [
            component
            for component in built["components"]
            if solver.Value(built["fine_mismatch"][component]) == 1
        ],
        "qiaoyu_source_components": [
            component
            for component in built["components"]
            if solver.Value(built["qiaoyu_sources"][component]) == 1
        ],
        "qiaoyu_sink_components": [
            component
            for component in built["components"]
            if solver.Value(built["sink_presence"][component]) == 1
        ],
        "selected_qiaoyu_sink_slot": selected_slots[0],
        "qiaoyu_mismatch_count": sum(
            int(solver.Value(variable))
            for variable in built["qiaoyu_mismatch_corrected"].values()
        ),
    }


def solve_arm(
    census: Mapping[str, Any],
    sink_payload: Mapping[str, Any],
    *,
    name: str,
    collapse_other: bool,
    fine_hard: bool,
    qiaoyu_hard: bool,
    objective: str,
    seed: int,
) -> dict[str, Any]:
    built = build_corrected(
        census,
        sink_payload,
        collapse_other=collapse_other,
    )
    model = built["model"]
    if fine_hard:
        for component in built["components"]:
            model.Add(
                built["fine_sources"][component]
                == built["fine_sinks"][component]
            )
    if qiaoyu_hard:
        for component in built["components"]:
            model.Add(
                built["qiaoyu_sources"][component]
                == built["sink_presence"][component]
            )
    if objective == "feasibility":
        model.Minimize(0)
    elif objective == "fine_mismatch":
        model.Minimize(
            cp_model.LinearExpr.Sum(list(built["fine_mismatch"].values()))
        )
    elif objective == "qiaoyu_mismatch":
        model.Minimize(
            cp_model.LinearExpr.Sum(
                list(built["qiaoyu_mismatch_corrected"].values())
            )
        )
    else:
        raise ValueError(objective)
    solver = configure_solver(seed=seed)
    started = time.monotonic()
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "name": name,
        "collapse_other": collapse_other,
        "fine_hard": fine_hard,
        "qiaoyu_hard": qiaoyu_hard,
        "objective_kind": objective,
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


def enumerate_qiaoyu_hard_face(
    census: Mapping[str, Any],
    sink_payload: Mapping[str, Any],
    *,
    collapse_other: bool,
    optimum: int,
    seed: int,
) -> dict[str, Any]:
    built = build_corrected(
        census,
        sink_payload,
        collapse_other=collapse_other,
    )
    model = built["model"]
    for component in built["components"]:
        model.Add(
            built["qiaoyu_sources"][component]
            == built["sink_presence"][component]
        )
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
        source_set = set(payload["fine_source_components"])
        sink_set = set(payload["fine_sink_components"])
        qiaoyu_sink = tuple(payload["qiaoyu_sink_components"])
        pattern = {
            "qiaoyu_sink_components": list(qiaoyu_sink),
            "fine_source_components": sorted(source_set),
            "fine_sink_components": sorted(sink_set),
            "source_only_components": sorted(source_set - sink_set),
            "sink_only_components": sorted(sink_set - source_set),
        }
        patterns.append(pattern)
        literals: list[Any] = []
        for component in built["components"]:
            source = built["fine_sources"][component]
            sink = built["fine_sinks"][component]
            q_sink = built["sink_presence"][component]
            literals.append(source.Not() if component in source_set else source)
            literals.append(sink.Not() if component in sink_set else sink)
            literals.append(q_sink.Not() if component in qiaoyu_sink else q_sink)
        model.AddBoolOr(literals)
    return {
        "status": "ENUMERATION_CAP",
        "complete": False,
        "pattern_count": len(patterns),
        "patterns": patterns,
    }


def solve_synthetic(
    census: Mapping[str, Any],
    sink_payload: Mapping[str, Any],
    *,
    kind: str,
    component: int,
    seed: int,
) -> dict[str, Any]:
    if kind == "filling":
        synthetic = {
            "operation": FILLING,
            "fine_input_components": [component],
            "qiaoyu_output_components": [15],
        }
    elif kind == "grinder":
        synthetic = {
            "operation": FINE_GRINDER,
            "fine_output_components": [component],
        }
    else:
        raise ValueError(kind)
    built = build_corrected(
        census,
        sink_payload,
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
            == built["sink_presence"][component_id]
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
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "kind": kind,
        "component": int(component),
        "status": status_name,
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
            raise RuntimeError(f"synthetic selection drift: {selected}")
        result["selected_body"] = int(selected[0])
        result["presence"] = presence_payload(built, solver)
    return result


def run() -> dict[str, Any]:
    identity = verify_identity()
    census = load_json(E058_CENSUS)
    sink_payload = generic_qiaoyu_sink_slots()
    arms = {
        "exact_joint": solve_arm(
            census,
            sink_payload,
            name="exact_joint",
            collapse_other=False,
            fine_hard=True,
            qiaoyu_hard=True,
            objective="feasibility",
            seed=60001,
        ),
        "relaxed_joint": solve_arm(
            census,
            sink_payload,
            name="relaxed_joint",
            collapse_other=True,
            fine_hard=True,
            qiaoyu_hard=True,
            objective="feasibility",
            seed=60002,
        ),
        "exact_qiaoyu_hard_fine_min": solve_arm(
            census,
            sink_payload,
            name="exact_qiaoyu_hard_fine_min",
            collapse_other=False,
            fine_hard=False,
            qiaoyu_hard=True,
            objective="fine_mismatch",
            seed=60003,
        ),
        "relaxed_qiaoyu_hard_fine_min": solve_arm(
            census,
            sink_payload,
            name="relaxed_qiaoyu_hard_fine_min",
            collapse_other=True,
            fine_hard=False,
            qiaoyu_hard=True,
            objective="fine_mismatch",
            seed=60004,
        ),
        "exact_fine_hard_qiaoyu_min": solve_arm(
            census,
            sink_payload,
            name="exact_fine_hard_qiaoyu_min",
            collapse_other=False,
            fine_hard=True,
            qiaoyu_hard=False,
            objective="qiaoyu_mismatch",
            seed=60005,
        ),
        "relaxed_fine_hard_qiaoyu_min": solve_arm(
            census,
            sink_payload,
            name="relaxed_fine_hard_qiaoyu_min",
            collapse_other=True,
            fine_hard=True,
            qiaoyu_hard=False,
            objective="qiaoyu_mismatch",
            seed=60006,
        ),
    }
    exact_q = arms["exact_qiaoyu_hard_fine_min"]
    relaxed_q = arms["relaxed_qiaoyu_hard_fine_min"]
    if exact_q["status"] != "OPTIMAL" or relaxed_q["status"] != "OPTIMAL":
        raise RuntimeError("corrected qiaoyu-hard tradeoff nonterminal")
    exact_face = enumerate_qiaoyu_hard_face(
        census,
        sink_payload,
        collapse_other=False,
        optimum=int(exact_q["objective"]),
        seed=60011,
    )
    relaxed_face = enumerate_qiaoyu_hard_face(
        census,
        sink_payload,
        collapse_other=True,
        optimum=int(relaxed_q["objective"]),
        seed=60012,
    )
    if not exact_face["complete"] or not relaxed_face["complete"]:
        raise RuntimeError("corrected qiaoyu-hard face enumeration nonterminal")
    exact_patterns = {
        (
            tuple(row["qiaoyu_sink_components"]),
            tuple(row["fine_source_components"]),
            tuple(row["fine_sink_components"]),
        )
        for row in exact_face["patterns"]
    }
    relaxed_patterns = {
        (
            tuple(row["qiaoyu_sink_components"]),
            tuple(row["fine_source_components"]),
            tuple(row["fine_sink_components"]),
        )
        for row in relaxed_face["patterns"]
    }
    source_class = sorted(
        {
            int(component)
            for row in exact_face["patterns"]
            for component in row["source_only_components"]
        }
    )
    sink_class = sorted(
        {
            int(component)
            for row in exact_face["patterns"]
            for component in row["sink_only_components"]
        }
    )
    filling_repairs = [
        solve_synthetic(
            census,
            sink_payload,
            kind="filling",
            component=component,
            seed=60100 + component,
        )
        for component in source_class
    ]
    grinder_repairs = [
        solve_synthetic(
            census,
            sink_payload,
            kind="grinder",
            component=component,
            seed=60200 + component,
        )
        for component in sink_class
    ]
    filling_targets = [
        int(row["component"])
        for row in filling_repairs
        if row["status"] in {"OPTIMAL", "FEASIBLE"}
    ]
    grinder_targets = [
        int(row["component"])
        for row in grinder_repairs
        if row["status"] in {"OPTIMAL", "FEASIBLE"}
    ]
    old = load_json(E059_RESULT)
    old_patterns = {
        (
            (15,),
            tuple(row["fine_source_components"]),
            tuple(row["fine_sink_components"]),
        )
        for row in old["qiaoyu_hard_optimum_face"]["exact"]["patterns"]
    }
    revalidated = (
        arms["exact_joint"]["status"] == "INFEASIBLE"
        and arms["relaxed_joint"]["status"] == "INFEASIBLE"
        and int(arms["exact_qiaoyu_hard_fine_min"]["objective"]) == 2
        and int(arms["relaxed_qiaoyu_hard_fine_min"]["objective"]) == 2
        and int(arms["exact_fine_hard_qiaoyu_min"]["objective"]) == 1
        and int(arms["relaxed_fine_hard_qiaoyu_min"]["objective"]) == 1
        and exact_patterns == relaxed_patterns == old_patterns
        and filling_targets
        == old["single_signature_repairs"]["feasible_filling_components"]
        and grinder_targets
        == old["single_signature_repairs"]["feasible_grinder_components"]
    )
    if revalidated:
        verdict = "GENERIC_QIAOYU_SINK_FREEDOM_REVALIDATES_TWO_ZERO_TARGET"
        decision = "CONTINUE_FILLING_SIGNATURE_GEOMETRY_SEARCH"
    elif arms["exact_joint"]["status"] in {"OPTIMAL", "FEASIBLE"}:
        verdict = "GENERIC_QIAOYU_SINK_FREEDOM_REOPENS_FIXED_GEOMETRY"
        decision = "VALIDATE_CORRECTED_SIGNATURE_ASSIGNMENT_IN_FULL_CONSUMER"
    else:
        verdict = "GENERIC_QIAOYU_SINK_CORRECTION_CHANGES_TARGET"
        decision = "SUPERSEDE_OLD_SIGNATURE_TARGET"
    return {
        "schema": "zmd_zero_condition_e060_generic_sink_correction_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "generic_qiaoyu_sink_space": sink_payload,
        "arms": arms,
        "qiaoyu_hard_optimum_face": {
            "exact": exact_face,
            "relaxed": relaxed_face,
            "exact_relaxed_pattern_sets_equal": exact_patterns == relaxed_patterns,
            "all_selected_sink_components": sorted(
                {
                    int(component)
                    for row in exact_face["patterns"]
                    for component in row["qiaoyu_sink_components"]
                }
            ),
            "source_only_component_class": source_class,
            "sink_only_component_class": sink_class,
        },
        "single_signature_repairs": {
            "filling_capsule": filling_repairs,
            "grinder_fine_buckwheat": grinder_repairs,
            "feasible_filling_components": filling_targets,
            "feasible_grinder_components": grinder_targets,
        },
        "prior_scope_defect": {
            "finding": (
                "E058 fixed qiaoyu sink presence to the materialized component 15, "
                "although production binding assigns required generic inputs to "
                "front-usable physical provider slots."
            ),
            "omitted_sink_components": sorted(
                set(int(value) for value in sink_payload["components"]) - {15}
            ),
            "scientific_disposition": (
                "Original proof surface rejected; conclusion and E059 target are "
                "carried only by this corrected successor revalidation."
            ),
        },
        "decision": decision,
        "truth_boundary": (
            "E055 occupied geometry and E058 all-6x4 terminal-signature relaxation, "
            "with exact qiaoyu generic sink-slot choice restored across every "
            "front-usable selected provider input."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E060 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "sink_components": result["generic_qiaoyu_sink_space"][
                        "components"
                    ],
                    "joint_status": result["arms"]["exact_joint"]["status"],
                    "qiaoyu_hard_fine_min": result["arms"][
                        "exact_qiaoyu_hard_fine_min"
                    ]["objective"],
                    "fine_hard_qiaoyu_min": result["arms"][
                        "exact_fine_hard_qiaoyu_min"
                    ]["objective"],
                    "pattern_count": result["qiaoyu_hard_optimum_face"][
                        "exact"
                    ]["pattern_count"],
                    "selected_sink_components": result[
                        "qiaoyu_hard_optimum_face"
                    ]["all_selected_sink_components"],
                    "filling_targets": result["single_signature_repairs"][
                        "feasible_filling_components"
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
            "schema": "zmd_zero_condition_e060_generic_sink_correction_failure_v1",
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
