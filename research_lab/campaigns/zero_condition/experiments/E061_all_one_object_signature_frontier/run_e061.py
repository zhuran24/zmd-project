#!/usr/bin/env python3
"""E061: exhaust all one-object pose changes in the corrected two-zero relaxation."""

from __future__ import annotations

from collections import Counter, defaultdict
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
    "E061_all_one_object_signature_frontier/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
NON6_PATH = OUT / "NON6_SCAN.json"
SIX4_PATH = OUT / "SIX4_SCAN.json"

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
E014_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E014_fixed_outside_mobility/run_e014.py"
)
E058_CENSUS = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E058_all6x4_terminal_signature_frontier/run-004/SIGNATURE_CENSUS.json"
)
E060_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E060_generic_qiaoyu_sink_correction/run-001/RESULT.json"
)
E060_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E060_generic_qiaoyu_sink_correction/run_e060.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "288000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E055_RESULT: "5a81cd6c58151643b345a888f8bd782ba9c5bbdfe00c21e5ac2beccc90576efa",
    E055_ASSIGNMENT: "bf6d1cfcd4c6aaf649a16b9513044b2023b5a9a1a5b39267ebcaad15ffe2c46b",
    E055_WITNESS: "3b36ad647149af238567b3746e165fc60fbd107d47b10d8ba92bf15e4e2ab559",
    E056_RUNNER: "840a30a26e25c485e71b4891dbc68dc9e2c18d8608ffcc0404eda512d17d9e34",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E058_CENSUS: "2af0d107eaba7a638047b42b0aab58f83a52c37008221692bb4b8e8cadf27b5d",
    E060_RESULT: "feb697f506cb2ca2422c1d0e96a02250cb33afcaa21fc86fda939f6ce79409b8",
    E060_RUNNER: "05395a59d594eab9dc54eccf4a4c0d1164dd2addf4e7604648e6d866ecd0e143",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

SIX4 = "manufacturing_6x4"
FILLING = "filling_capsule"
FINE_GRINDER = "grinder_fine_buckwheat"
TARGET_OPERATIONS = (FILLING, FINE_GRINDER)
OTHER_OPERATIONS = (
    "grinder_dense_blue_iron",
    "grinder_dense_source",
    "packaging_battery",
)
ALL_SIX4_OPERATIONS = (*TARGET_OPERATIONS, *OTHER_OPERATIONS)
OPERATION_COUNTS = {FILLING: 3, FINE_GRINDER: 6, "other": 29}
FINE = "fine_buckwheat_powder"
QIAOYU = "qiaoyu_capsule"
EXPECTED_SIX4_BODY_COUNT = 38
CANDIDATE_SOLVE_SECONDS = 1.0
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


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


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
    corrected = load_json(E060_RESULT)
    if corrected.get("verdict") != (
        "GENERIC_QIAOYU_SINK_FREEDOM_REVALIDATES_TWO_ZERO_TARGET"
    ):
        raise RuntimeError("E061 E060 trigger verdict drift")
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


def reconstruct() -> dict[str, Any]:
    e056 = import_module("zmd_e061_e056", E056_RUNNER)
    e014 = import_module("zmd_e061_e014", E014_RUNNER)
    from src.models.port_binding import (
        enumerate_pose_level_port_bindings_with_cache_info,
    )
    from src.models.routing_binding_context import (
        build_routing_binding_context,
        is_port_front_usable,
    )

    context = e056.reconstruct()
    solution = context["warm_solution"]
    inputs = context["base"]["inputs"]
    stack = context["base"]["e001"].import_stack()
    power = e014.build_power_semantics(
        context["base"]["e001"],
        stack,
        inputs,
    )
    occupied, _owners = e014.base_occupancy(solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    return {
        "context": context,
        "solution": solution,
        "inputs": inputs,
        "power": power,
        "occupied": occupied,
        "selected_poles": selected_poles,
        "e014": e014,
        "enumerate_patterns": enumerate_pose_level_port_bindings_with_cache_info,
        "build_routing_context": build_routing_binding_context,
        "is_port_front_usable": is_port_front_usable,
    }


def body_rows(
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    e014: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[tuple[int, int], ...]] = set()
    for instance_id, row in solution.items():
        if str(row["facility_type"]) != SIX4:
            continue
        cells = tuple(
            sorted(
                e014.pose_cells(
                    pools,
                    SIX4,
                    int(row["pose_idx"]),
                )
            )
        )
        if cells in seen:
            raise RuntimeError("duplicate current 6x4 body")
        seen.add(cells)
        rows.append(
            {
                "source_instance_id": str(instance_id),
                "current_pose_idx": int(row["pose_idx"]),
                "current_operation": str(row["operation_type"]),
                "occupied_cells": cells,
                "body_digest": stable_digest(cells),
            }
        )
    rows.sort(key=lambda row: (row["occupied_cells"][0], row["body_digest"]))
    if len(rows) != EXPECTED_SIX4_BODY_COUNT:
        raise RuntimeError(f"current 6x4 body count drift: {len(rows)}")
    return rows


def modes_by_footprint(
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[tuple[tuple[int, int], ...], list[int]]:
    output: dict[tuple[tuple[int, int], ...], list[int]] = defaultdict(list)
    for pose_idx, pose in enumerate(pools[SIX4]):
        cells = tuple(sorted((int(x), int(y)) for x, y in pose["occupied_cells"]))
        output[cells].append(int(pose_idx))
    return dict(output)


def raw_descriptors(
    *,
    bodies: Sequence[Mapping[str, Any]],
    mode_map: Mapping[tuple[tuple[int, int], ...], Sequence[int]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    enumerate_patterns: Any,
) -> dict[int, list[tuple[Any, ...]]]:
    output: dict[int, list[tuple[Any, ...]]] = {}
    for destination, body in enumerate(bodies):
        descriptors: set[tuple[Any, ...]] = set()
        cells = tuple(body["occupied_cells"])
        for pose_idx in mode_map[cells]:
            pose = pools[SIX4][pose_idx]
            for operation in ALL_SIX4_OPERATIONS:
                raw_patterns, _cache = enumerate_patterns(operation, pose)
                for pattern in raw_patterns:
                    active = tuple(
                        sorted(
                            (int(port["x"]), int(port["y"]))
                            for port in pattern["active_ports"]
                        )
                    )
                    fine_input = tuple(
                        sorted(
                            (int(port["x"]), int(port["y"]))
                            for port in pattern["input_ports"]
                            if str(port["commodity"]) == FINE
                        )
                    )
                    fine_output = tuple(
                        sorted(
                            (int(port["x"]), int(port["y"]))
                            for port in pattern["output_ports"]
                            if str(port["commodity"]) == FINE
                        )
                    )
                    qiaoyu_output = tuple(
                        sorted(
                            (int(port["x"]), int(port["y"]))
                            for port in pattern["output_ports"]
                            if str(port["commodity"]) == QIAOYU
                        )
                    )
                    descriptors.add(
                        (
                            int(pose_idx),
                            str(operation),
                            active,
                            fine_input,
                            fine_output,
                            qiaoyu_output,
                        )
                    )
        output[destination] = sorted(descriptors)
    return output


def generic_sink_space(
    *,
    candidate: Mapping[str, Mapping[str, Any]],
    routing_context: Any,
    inputs: Mapping[str, Any],
    is_port_front_usable: Any,
) -> dict[str, Any]:
    capacity_map = inputs["plan"]["generic_input_slots_by_operation"]
    slots: list[dict[str, Any]] = []
    for instance_id, row in sorted(candidate.items()):
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
                f"generic input capacity drift: {instance_id}/{len(ports)}/{declared}"
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
                    "component": int(component),
                    "x": cell[0],
                    "y": cell[1],
                }
            )
    return {
        "slots": slots,
        "components": sorted({int(row["component"]) for row in slots}),
    }


def map_descriptors(
    *,
    descriptors: Mapping[int, Sequence[tuple[Any, ...]]],
    routing_context: Any,
) -> dict[int, list[tuple[Any, ...]]]:
    free_cells = set(routing_context.component_by_cell)
    output: dict[int, list[tuple[Any, ...]]] = {}
    for destination, rows in descriptors.items():
        options: set[tuple[Any, ...]] = set()
        for (
            pose_idx,
            operation,
            active,
            fine_input,
            fine_output,
            qiaoyu_output,
        ) in rows:
            if any(cell not in free_cells for cell in active):
                continue
            operation_class = (
                operation if operation in TARGET_OPERATIONS else "other"
            )
            signature = (
                tuple(
                    sorted(
                        {
                            int(routing_context.component_by_cell[cell])
                            for cell in fine_input
                        }
                    )
                ),
                tuple(
                    sorted(
                        {
                            int(routing_context.component_by_cell[cell])
                            for cell in fine_output
                        }
                    )
                ),
                tuple(
                    sorted(
                        {
                            int(routing_context.component_by_cell[cell])
                            for cell in qiaoyu_output
                        }
                    )
                ),
            )
            options.add((operation_class, int(pose_idx), signature))
        output[destination] = sorted(options)
    return output


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


def solve_signature(
    *,
    options: Mapping[int, Sequence[tuple[Any, ...]]],
    sink_space: Mapping[str, Any],
    random_seed: int,
) -> dict[str, Any]:
    if not sink_space["slots"] or any(not rows for rows in options.values()):
        return {
            "status": "STRUCTURAL_EMPTY",
            "elapsed_seconds": 0.0,
            "branches": 0,
            "conflicts": 0,
            "sink_components": sink_space["components"],
        }
    model = cp_model.CpModel()
    x_vars: dict[tuple[int, int], Any] = {}
    for destination, rows in options.items():
        variables: list[Any] = []
        for option_index, _option in enumerate(rows):
            variable = model.NewBoolVar(f"e061_x_{destination}_{option_index}")
            x_vars[(destination, option_index)] = variable
            variables.append(variable)
        model.AddExactlyOne(variables)
    for operation, expected in OPERATION_COUNTS.items():
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
            name=f"e061_fine_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option[2][1])
            ],
        )
        fine_sinks[component] = add_exact_or(
            model,
            name=f"e061_fine_sink_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option[2][0])
            ],
        )
        qiaoyu_sources[component] = add_exact_or(
            model,
            name=f"e061_qiaoyu_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option[2][2])
            ],
        )
    sink_component_vars = {
        component: model.NewBoolVar(f"e061_sink_component_{component}")
        for component in sink_space["components"]
    }
    model.AddExactlyOne(list(sink_component_vars.values()))
    for component in components:
        model.Add(fine_sources[component] == fine_sinks[component])
        model.Add(
            qiaoyu_sources[component]
            == (
                sink_component_vars[component]
                if component in sink_component_vars
                else 0
            )
        )
    model.Add(cp_model.LinearExpr.Sum(list(fine_sources.values())) >= 1)
    model.Minimize(0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = CANDIDATE_SOLVE_SECONDS
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
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "sink_components": sink_space["components"],
        "selected_sink_component": None,
        "fine_components": None,
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result["selected_sink_component"] = next(
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


def enumerate_alternatives(
    *,
    base: Mapping[str, Any],
    instance_id: str,
) -> list[dict[str, Any]]:
    solution = base["solution"]
    row = solution[instance_id]
    return base["e014"].enumerate_alternatives(
        target={
            "literal_key": instance_id,
            "source_instance_ids": [instance_id],
            "facility_type": str(row["facility_type"]),
            "pose_idx": int(row["pose_idx"]),
        },
        base_solution=solution,
        pools=base["inputs"]["pools"],
        occupied=base["occupied"],
        selected_poles=base["selected_poles"],
        powered_templates=base["power"]["powered_templates"],
        coverers=base["power"]["coverers"],
    )


def compact_candidate(
    *,
    instance_id: str,
    row: Mapping[str, Any],
    alternative: Mapping[str, Any],
    result: Mapping[str, Any],
    alias_count: int,
) -> dict[str, Any]:
    return {
        "source_instance_id": str(instance_id),
        "facility_type": str(row["facility_type"]),
        "current_pose_idx": int(row["pose_idx"]),
        "replacement_pose_idx": int(alternative["pose_idx"]),
        "replacement_pose_id": str(alternative["pose_id"]),
        "alias_count": int(alias_count),
        "signature_solve": json_safe(result),
    }


def scan_non6(
    *,
    base: Mapping[str, Any],
    fixed_descriptors: Mapping[int, Sequence[tuple[Any, ...]]],
    runner_sha256: str,
) -> dict[str, Any]:
    if NON6_PATH.exists():
        payload = load_json(NON6_PATH)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E061 non6 checkpoint")
        return payload
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    raw_body_count = 0
    raw_same_mode_count = 0
    invariant_same_mode_count = 0
    same_mode_counts: Counter[str] = Counter()
    body_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    feasible: list[dict[str, Any]] = []
    nonterminal: list[dict[str, Any]] = []
    started = time.monotonic()
    for instance_id, row in sorted(base["solution"].items()):
        facility_type = str(row["facility_type"])
        if facility_type == SIX4:
            continue
        alternatives = enumerate_alternatives(base=base, instance_id=instance_id)
        for alternative in alternatives:
            if bool(alternative["same_footprint"]):
                raw_same_mode_count += 1
                same_mode_counts[facility_type] += 1
                operation = str(row.get("operation_type", ""))
                if facility_type != "protocol_core":
                    if int(
                        base["inputs"]["plan"][
                            "generic_input_slots_by_operation"
                        ].get(operation, 0)
                    ) != 0:
                        raise RuntimeError(
                            f"unhandled generic-input same mode: {instance_id}"
                        )
                    invariant_same_mode_count += 1
                    continue
                routing_context = base["build_routing_context"](
                    alternative["solution"],
                    base["inputs"]["pools"],
                    70,
                    70,
                )
                sink_space = generic_sink_space(
                    candidate=alternative["solution"],
                    routing_context=routing_context,
                    inputs=base["inputs"],
                    is_port_front_usable=base["is_port_front_usable"],
                )
                options = map_descriptors(
                    descriptors=fixed_descriptors,
                    routing_context=routing_context,
                )
                result = solve_signature(
                    options=options,
                    sink_space=sink_space,
                    random_seed=61100 + int(alternative["pose_idx"]),
                )
                status_counts[str(result["status"])] += 1
                if result["status"] in {"OPTIMAL", "FEASIBLE"}:
                    feasible.append(
                        compact_candidate(
                            instance_id=instance_id,
                            row=row,
                            alternative=alternative,
                            result=result,
                            alias_count=0,
                        )
                    )
                elif result["status"] not in {"INFEASIBLE", "STRUCTURAL_EMPTY"}:
                    nonterminal.append(
                        compact_candidate(
                            instance_id=instance_id,
                            row=row,
                            alternative=alternative,
                            result=result,
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
                seen[key]["aliases"] += 1
                continue
            seen[key] = {
                "instance_id": instance_id,
                "row": row,
                "alternative": alternative,
                "aliases": 0,
            }
            body_counts[facility_type] += 1
            routing_context = base["build_routing_context"](
                alternative["solution"],
                base["inputs"]["pools"],
                70,
                70,
            )
            sink_space = generic_sink_space(
                candidate=alternative["solution"],
                routing_context=routing_context,
                inputs=base["inputs"],
                is_port_front_usable=base["is_port_front_usable"],
            )
            options = map_descriptors(
                descriptors=fixed_descriptors,
                routing_context=routing_context,
            )
            result = solve_signature(
                options=options,
                sink_space=sink_space,
                random_seed=61200 + len(seen),
            )
            status_counts[str(result["status"])] += 1
            if result["status"] in {"OPTIMAL", "FEASIBLE"}:
                feasible.append(
                    compact_candidate(
                        instance_id=instance_id,
                        row=row,
                        alternative=alternative,
                        result=result,
                        alias_count=int(seen[key]["aliases"]),
                    )
                )
            elif result["status"] not in {"INFEASIBLE", "STRUCTURAL_EMPTY"}:
                nonterminal.append(
                    compact_candidate(
                        instance_id=instance_id,
                        row=row,
                        alternative=alternative,
                        result=result,
                        alias_count=int(seen[key]["aliases"]),
                    )
                )
            if len(seen) % 500 == 0:
                print(
                    json.dumps(
                        {
                            "event": "E061_NON6_PROGRESS",
                            "unique": len(seen),
                            "raw": raw_body_count,
                            "feasible": len(feasible),
                            "nonterminal": len(nonterminal),
                            "at_utc": utc_now(),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
    payload = {
        "schema": "zmd_zero_condition_e061_non6_scan_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "raw_body_changing_alternative_count": raw_body_count,
        "unique_body_geometry_count": len(seen),
        "unique_body_geometry_count_by_facility_type": dict(
            sorted(body_counts.items())
        ),
        "raw_same_footprint_mode_count": raw_same_mode_count,
        "same_footprint_mode_count_by_facility_type": dict(
            sorted(same_mode_counts.items())
        ),
        "signature_invariant_same_mode_count": invariant_same_mode_count,
        "explicit_same_mode_solve_count": raw_same_mode_count
        - invariant_same_mode_count,
        "status_counts": dict(sorted(status_counts.items())),
        "feasible_candidates": feasible,
        "nonterminal_candidates": nonterminal,
        "elapsed_seconds": time.monotonic() - started,
        "ledger_effect": "none",
    }
    dump_exclusive(NON6_PATH, payload)
    return payload


def dynamic_descriptors(
    *,
    candidate: Mapping[str, Mapping[str, Any]],
    base: Mapping[str, Any],
    mode_map: Mapping[tuple[tuple[int, int], ...], Sequence[int]],
) -> dict[int, list[tuple[Any, ...]]]:
    bodies = body_rows(
        candidate,
        base["inputs"]["pools"],
        base["e014"],
    )
    return raw_descriptors(
        bodies=bodies,
        mode_map=mode_map,
        pools=base["inputs"]["pools"],
        enumerate_patterns=base["enumerate_patterns"],
    )


def scan_six4(
    *,
    base: Mapping[str, Any],
    mode_map: Mapping[tuple[tuple[int, int], ...], Sequence[int]],
    runner_sha256: str,
) -> dict[str, Any]:
    if SIX4_PATH.exists():
        payload = load_json(SIX4_PATH)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E061 6x4 checkpoint")
        return payload
    seen: dict[tuple[Any, ...], int] = {}
    raw_body_count = 0
    raw_same_mode_count = 0
    status_counts: Counter[str] = Counter()
    feasible: list[dict[str, Any]] = []
    nonterminal: list[dict[str, Any]] = []
    started = time.monotonic()
    for instance_id, row in sorted(base["solution"].items()):
        if str(row["facility_type"]) != SIX4:
            continue
        alternatives = enumerate_alternatives(base=base, instance_id=instance_id)
        for alternative in alternatives:
            if bool(alternative["same_footprint"]):
                raw_same_mode_count += 1
                continue
            raw_body_count += 1
            old_cells = tuple(
                sorted(
                    base["e014"].pose_cells(
                        base["inputs"]["pools"],
                        SIX4,
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
            sink_space = generic_sink_space(
                candidate=alternative["solution"],
                routing_context=routing_context,
                inputs=base["inputs"],
                is_port_front_usable=base["is_port_front_usable"],
            )
            descriptors = dynamic_descriptors(
                candidate=alternative["solution"],
                base=base,
                mode_map=mode_map,
            )
            options = map_descriptors(
                descriptors=descriptors,
                routing_context=routing_context,
            )
            result = solve_signature(
                options=options,
                sink_space=sink_space,
                random_seed=61300 + len(seen),
            )
            status_counts[str(result["status"])] += 1
            if result["status"] in {"OPTIMAL", "FEASIBLE"}:
                feasible.append(
                    compact_candidate(
                        instance_id=instance_id,
                        row=row,
                        alternative=alternative,
                        result=result,
                        alias_count=int(seen[key]),
                    )
                )
            elif result["status"] not in {"INFEASIBLE", "STRUCTURAL_EMPTY"}:
                nonterminal.append(
                    compact_candidate(
                        instance_id=instance_id,
                        row=row,
                        alternative=alternative,
                        result=result,
                        alias_count=int(seen[key]),
                    )
                )
            if len(seen) % 25 == 0:
                print(
                    json.dumps(
                        {
                            "event": "E061_SIX4_PROGRESS",
                            "unique": len(seen),
                            "raw": raw_body_count,
                            "feasible": len(feasible),
                            "nonterminal": len(nonterminal),
                            "at_utc": utc_now(),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
    payload = {
        "schema": "zmd_zero_condition_e061_six4_scan_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "raw_body_changing_alternative_count": raw_body_count,
        "unique_body_geometry_count": len(seen),
        "raw_same_footprint_mode_count": raw_same_mode_count,
        "same_footprint_mode_disposition": (
            "Already jointly represented in the corrected E060 all-6x4 signature "
            "model; not re-enumerated as one-object states."
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "feasible_candidates": feasible,
        "nonterminal_candidates": nonterminal,
        "elapsed_seconds": time.monotonic() - started,
        "ledger_effect": "none",
    }
    dump_exclusive(SIX4_PATH, payload)
    return payload


def run() -> dict[str, Any]:
    identity = verify_identity()
    base = reconstruct()
    bodies = body_rows(
        base["solution"],
        base["inputs"]["pools"],
        base["e014"],
    )
    mode_map = modes_by_footprint(base["inputs"]["pools"])
    fixed_descriptors = raw_descriptors(
        bodies=bodies,
        mode_map=mode_map,
        pools=base["inputs"]["pools"],
        enumerate_patterns=base["enumerate_patterns"],
    )
    current_context = base["build_routing_context"](
        base["solution"],
        base["inputs"]["pools"],
        70,
        70,
    )
    current_signature = solve_signature(
        options=map_descriptors(
            descriptors=fixed_descriptors,
            routing_context=current_context,
        ),
        sink_space=generic_sink_space(
            candidate=base["solution"],
            routing_context=current_context,
            inputs=base["inputs"],
            is_port_front_usable=base["is_port_front_usable"],
        ),
        random_seed=61001,
    )
    if current_signature["status"] != "INFEASIBLE":
        raise RuntimeError(
            f"E061 current corrected signature calibration drift: {current_signature}"
        )
    non6 = scan_non6(
        base=base,
        fixed_descriptors=fixed_descriptors,
        runner_sha256=str(identity["runner_sha256"]),
    )
    six4 = scan_six4(
        base=base,
        mode_map=mode_map,
        runner_sha256=str(identity["runner_sha256"]),
    )
    feasible_count = len(non6["feasible_candidates"]) + len(
        six4["feasible_candidates"]
    )
    nonterminal_count = len(non6["nonterminal_candidates"]) + len(
        six4["nonterminal_candidates"]
    )
    if feasible_count:
        verdict = "ONE_OBJECT_TWO_ZERO_SIGNATURE_CANDIDATES_FOUND"
        decision = "VALIDATE_SIGNATURE_CANDIDATES_IN_FULL_JOINT_CONSUMER"
    elif nonterminal_count:
        verdict = "ONE_OBJECT_TWO_ZERO_SIGNATURE_FRONTIER_NONTERMINAL"
        decision = "CONTINUE_NONTERMINAL_CANDIDATE_SOLVES"
    else:
        verdict = "ALL_ONE_OBJECT_TWO_ZERO_SIGNATURE_CHANGES_INFEASIBLE"
        decision = "BUILD_SIMULTANEOUS_TWO_OBJECT_OR_ALTERNATE_FIRST_ZERO_CONTEXT"
    return {
        "schema": "zmd_zero_condition_e061_all_one_object_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "current_signature_calibration": current_signature,
        "raw_descriptor_count": sum(
            len(rows) for rows in fixed_descriptors.values()
        ),
        "non6_scan_path": str(NON6_PATH.relative_to(ROOT)),
        "non6_scan_sha256": sha256_file(NON6_PATH),
        "non6_scan": non6,
        "six4_scan_path": str(SIX4_PATH.relative_to(ROOT)),
        "six4_scan_sha256": sha256_file(SIX4_PATH),
        "six4_scan": six4,
        "total_raw_body_changing_alternative_count": int(
            non6["raw_body_changing_alternative_count"]
        )
        + int(six4["raw_body_changing_alternative_count"]),
        "total_unique_body_geometry_count": int(
            non6["unique_body_geometry_count"]
        )
        + int(six4["unique_body_geometry_count"]),
        "total_non6_same_footprint_mode_count": int(
            non6["raw_same_footprint_mode_count"]
        ),
        "total_feasible_candidate_count": feasible_count,
        "total_nonterminal_candidate_count": nonterminal_count,
        "decision": decision,
        "truth_boundary": (
            "E055 first-zero state with exactly one placement-/power-valid pose "
            "change. The corrected model restores candidate-specific generic sink "
            "components and relaxes unrelated 6x4 operations into `other`."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E061 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "raw_body_changes": result[
                        "total_raw_body_changing_alternative_count"
                    ],
                    "unique_geometries": result[
                        "total_unique_body_geometry_count"
                    ],
                    "non6_same_modes": result[
                        "total_non6_same_footprint_mode_count"
                    ],
                    "feasible": result["total_feasible_candidate_count"],
                    "nonterminal": result["total_nonterminal_candidate_count"],
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
            "schema": "zmd_zero_condition_e061_all_one_object_frontier_failure_v1",
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
