#!/usr/bin/env python3
"""E101: externalize E100's x42 class bridge as a low/high handshake."""

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
    "E101_x42_allocation_handshake/run-001"
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
E100_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E100_source_stable_reserved_x42_hybrid"
)
E100_RUNNER = E100_DIR / "run_e100.py"
E100_DURABLE = E100_DIR / "RESULT.txt"
E100_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E100_source_stable_reserved_x42_hybrid/run-001/RESULT.json"
)
E100_CHECK = E100_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E100_DURABLE: "6b230d36277982409309d843f75dcec1e74fd886022fc08cb08444784d443a1b",
    E100_RESULT: "d4de0239604cf4713164069fda553965275566c1840238ec4fa98446ba71b12c",
    E100_CHECK: "b2cc7e2aef54f5e0209a96b124319fa68b834bd0556db1d162732ac123fc5fc4",
}

BODY_SECONDS = 20.0
HIGH_SECONDS = 25.0
LOW_SECONDS = 40.0
MAX_ALLOCATIONS = 3
EXPECTED_BODY_COUNT = 91
EXPECTED_CLASS_DIMENSIONS = 8
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)


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
    code = compile(
        raw,
        f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>",
        "exec",
        dont_inherit=True,
    )
    exec(code, module.__dict__)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E101 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E101 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"E101 input drift: {path}: {observed} != {expected}")
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    e100 = load_json(E100_RESULT)
    if e100.get("verdict") != "SOURCE_STABLE_RESERVED_X42_CONSTRUCTOR_CENSORED":
        raise RuntimeError("E101 E100 verdict drift")
    if e100.get("decision") != "SOLVE_X42_LOW_HIGH_SIDES_CONDITIONED_ON_ALLOCATIONS":
        raise RuntimeError("E101 E100 decision drift")
    check = load_json(E100_CHECK)
    if check.get("status") != "PASS" or check.get("branch", {}).get(
        "classification"
    ) != "CENSORED_NO_INCUMBENT":
        raise RuntimeError("E101 E100 check drift")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def solver_for(seed: int, seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = int(seed)
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.randomize_search = True
    solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    solver.parameters.repair_hint = True
    solver.parameters.hint_conflict_limit = 4000
    solver.parameters.stop_after_first_solution = True
    return solver


def body_only_witness(
    *,
    e095: types.ModuleType,
    restricted: Mapping[str, Any],
    seconds: float,
    seed: int,
) -> dict[str, Any]:
    context = restricted["base"]
    rows = [dict(row) for row in restricted["rows"]]
    model = cp_model.CpModel()
    variables = [model.NewBoolVar(f"body_{index}") for index in range(len(rows))]

    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(variables[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    class_counts = {
        key: int(count)
        for key, count in context["class_counts"].items()
        if key[0] == "B"
    }
    template_counts: Counter[str] = Counter()
    for (_module, template, _need_in, _need_out), count in class_counts.items():
        template_counts[template] += int(count)
    for template, required in sorted(template_counts.items()):
        model.Add(
            sum(
                variables[index]
                for index, row in enumerate(rows)
                if row["template"] == template
            )
            == required
        )

    fixed_coverage = set(context["fixed_coverage"])
    disabled_unpowered = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & fixed_coverage:
            model.Add(variables[index] == 0)
            disabled_unpowered += 1

    stable_indices: dict[str, int] = {}
    for instance_id, footprint in context["stable_footprints"].items():
        matches = [
            index for index, row in enumerate(rows) if tuple(row["body"]) == footprint
        ]
        if len(matches) != 1:
            raise RuntimeError(f"E101 body-only stable remap drift: {instance_id}")
        stable_indices[instance_id] = matches[0]
        model.Add(variables[matches[0]] == 1)

    anchor = set(context["hint_bodies"]["B"])
    matched_hints = 0
    for index, row in enumerate(rows):
        hinted = tuple(row["body"]) in anchor
        model.AddHint(variables[index], int(hinted))
        matched_hints += int(hinted)
    if matched_hints != 87:
        raise RuntimeError(f"E101 body-only hint drift: {matched_hints}")

    error = model.Validate()
    if error:
        raise RuntimeError(f"E101 body-only model invalid: {error}")
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(seed, seconds)
    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)
    result: dict[str, Any] = {
        "schema": "zmd_e101_body_only_allocation_witness_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": status,
        "elapsed_seconds": elapsed,
        "seed": seed,
        "solve_seconds": seconds,
        "candidate_count": len(rows),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "disabled_unpowered_candidate_count": disabled_unpowered,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
        "stable_indices": stable_indices,
    }
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected = [index for index, variable in enumerate(variables) if solver.Value(variable)]
        if len(selected) != EXPECTED_BODY_COUNT:
            raise RuntimeError("E101 body-only selected count drift")
        side_template_counts = Counter(
            (str(rows[index]["side"]), str(rows[index]["template"]))
            for index in selected
        )
        result.update(
            {
                "selected_body_count": len(selected),
                "selected_body_indices": selected,
                "selected_body_digest": stable_digest(
                    sorted(str(rows[index]["body_digest"]) for index in selected)
                ),
                "side_body_counts": dict(
                    sorted(Counter(str(rows[index]["side"]) for index in selected).items())
                ),
                "side_template_counts": {
                    f"{side}:{template}": int(count)
                    for (side, template), count in sorted(side_template_counts.items())
                },
                "retained_anchor_count": sum(
                    tuple(rows[index]["body"]) in anchor for index in selected
                ),
            }
        )
    return result


def build_side_model(
    *,
    e095: types.ModuleType,
    restricted: Mapping[str, Any],
    side: str,
    template_counts: Mapping[str, int],
    body_hint_indices: set[int],
    fixed_allocation: Mapping[tuple[str, str, int, int], int] | None,
) -> dict[str, Any]:
    context = restricted["base"]
    source_rows = [dict(row) for row in restricted["rows"]]
    global_indices = [
        index for index, row in enumerate(source_rows) if str(row["side"]) == side
    ]
    rows = [{**source_rows[index], "global_row_index": index} for index in global_indices]
    model = cp_model.CpModel()
    body_vars = [model.NewBoolVar(f"{side}_body_{index}") for index in range(len(rows))]

    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(body_vars[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    global_class_counts = {
        key: int(count)
        for key, count in context["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(global_class_counts))
    if len(class_keys) != EXPECTED_CLASS_DIMENSIONS:
        raise RuntimeError("E101 side class dimension drift")

    mode_rows: list[dict[str, Any]] = []
    vars_by_body: dict[int, list[Any]] = defaultdict(list)
    vars_by_class: dict[tuple[str, str, int, int], list[Any]] = defaultdict(list)
    fixed_solid = set(context["fixed_solid"])
    pools = context["pools"]
    for body_index, row in enumerate(rows):
        template = str(row["template"])
        relevant = [key for key in class_keys if key[1] == template]
        forced = e095.STABLE_CLASS_BY_BODY.get(str(row["body_digest"]))
        for pose_index in row["mode_pose_indices"]:
            pose = pools[template][int(pose_index)]
            input_cells = tuple(e095.cell(value) for value in pose["input_port_cells"])
            output_cells = tuple(e095.cell(value) for value in pose["output_port_cells"])
            for class_key in relevant:
                _module, _template, need_in, need_out = class_key
                if forced is not None and (need_in, need_out) != forced:
                    continue
                if need_in > len(input_cells) or need_out > len(output_cells):
                    continue
                variable = model.NewBoolVar(
                    f"{side}_mc_{body_index}_{pose_index}_{need_in}_{need_out}"
                )
                vars_by_body[body_index].append(variable)
                vars_by_class[class_key].append(variable)
                mode_rows.append(
                    {
                        "body_index": body_index,
                        "global_row_index": int(row["global_row_index"]),
                        "body_digest": str(row["body_digest"]),
                        "side": side,
                        "pose_index": int(pose_index),
                        "class_key": class_key,
                        "need_in": int(need_in),
                        "need_out": int(need_out),
                        "input_cells": input_cells,
                        "output_cells": output_cells,
                        "variable": variable,
                    }
                )
        if vars_by_body[body_index]:
            model.Add(sum(vars_by_body[body_index]) == body_vars[body_index])
        else:
            model.Add(body_vars[body_index] == 0)

    allocation_vars: dict[tuple[str, str, int, int], Any] = {}
    for class_index, class_key in enumerate(class_keys):
        global_count = global_class_counts[class_key]
        if fixed_allocation is None:
            allocation = model.NewIntVar(0, global_count, f"{side}_alloc_{class_index}")
            allocation_vars[class_key] = allocation
            model.Add(sum(vars_by_class[class_key]) == allocation)
        else:
            required = int(fixed_allocation[class_key])
            if not 0 <= required <= global_count:
                raise RuntimeError(f"E101 invalid fixed allocation {class_key}: {required}")
            model.Add(sum(vars_by_class[class_key]) == required)

    for template, required in sorted(template_counts.items()):
        model.Add(
            sum(
                body_vars[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
            == int(required)
        )
    if fixed_allocation is None:
        for template, required in sorted(template_counts.items()):
            model.Add(
                sum(
                    allocation_vars[key]
                    for key in class_keys
                    if key[1] == template
                )
                == int(required)
            )

    for mode_row in mode_rows:
        variable = mode_row["variable"]
        for front_cells, need in (
            (mode_row["input_cells"], int(mode_row["need_in"])),
            (mode_row["output_cells"], int(mode_row["need_out"])),
        ):
            fixed_blocked = sum(
                (not e095.in_grid(value)) or value in fixed_solid
                for value in front_cells
            )
            dynamic_terms = [
                body_var
                for value in front_cells
                if e095.in_grid(value) and value not in fixed_solid
                for body_var in by_cell.get(value, [])
            ]
            model.Add(
                fixed_blocked + sum(dynamic_terms)
                <= len(front_cells) - need + len(front_cells) * (1 - variable)
            )

    fixed_coverage = set(context["fixed_coverage"])
    disabled_unpowered = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & fixed_coverage:
            model.Add(body_vars[index] == 0)
            disabled_unpowered += 1

    stable_local_indices: dict[str, int] = {}
    for instance_id, footprint in context["stable_footprints"].items():
        matches = [
            index for index, row in enumerate(rows) if tuple(row["body"]) == footprint
        ]
        if matches:
            if len(matches) != 1:
                raise RuntimeError(f"E101 side stable remap drift: {instance_id}")
            stable_local_indices[instance_id] = matches[0]
            model.Add(body_vars[matches[0]] == 1)
        elif side == "high":
            raise RuntimeError(f"E101 stable body missing from high side: {instance_id}")

    matched_hints = 0
    for local_index, row in enumerate(rows):
        hinted = int(row["global_row_index"]) in body_hint_indices
        model.AddHint(body_vars[local_index], int(hinted))
        matched_hints += int(hinted)

    error = model.Validate()
    if error:
        raise RuntimeError(f"E101 {side} model invalid: {error}")
    return {
        "side": side,
        "model": model,
        "rows": rows,
        "body_vars": body_vars,
        "mode_rows": mode_rows,
        "allocation_vars": allocation_vars,
        "class_keys": class_keys,
        "global_class_counts": global_class_counts,
        "template_counts": dict(template_counts),
        "stable_local_indices": stable_local_indices,
        "disabled_unpowered_candidate_count": disabled_unpowered,
        "matched_hint_count": matched_hints,
    }


def solve_side(
    side_model: Mapping[str, Any], *, seconds: float, seed: int
) -> dict[str, Any]:
    model = side_model["model"]
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(seed, seconds)
    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)
    result: dict[str, Any] = {
        "schema": "zmd_e101_side_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "side": side_model["side"],
        "status": status,
        "elapsed_seconds": elapsed,
        "seed": seed,
        "solve_seconds": seconds,
        "candidate_count": len(side_model["rows"]),
        "mode_class_variable_count": len(side_model["mode_rows"]),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "disabled_unpowered_candidate_count": side_model[
            "disabled_unpowered_candidate_count"
        ],
        "matched_hint_count": side_model["matched_hint_count"],
        "template_counts": side_model["template_counts"],
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
    }
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_body_indices = [
            index
            for index, variable in enumerate(side_model["body_vars"])
            if solver.Value(variable)
        ]
        selected_modes = [
            {
                "body_index": int(row["body_index"]),
                "global_row_index": int(row["global_row_index"]),
                "body_digest": str(row["body_digest"]),
                "side": str(row["side"]),
                "pose_index": int(row["pose_index"]),
                "class_key": list(row["class_key"]),
                "need_in": int(row["need_in"]),
                "need_out": int(row["need_out"]),
            }
            for row in side_model["mode_rows"]
            if solver.Value(row["variable"])
        ]
        expected = sum(int(value) for value in side_model["template_counts"].values())
        if len(selected_body_indices) != expected or len(selected_modes) != expected:
            raise RuntimeError(f"E101 {side_model['side']} selected count drift")
        allocation = (
            {
                key: int(solver.Value(variable))
                for key, variable in side_model["allocation_vars"].items()
            }
            if side_model["allocation_vars"]
            else Counter(tuple(row["class_key"]) for row in selected_modes)
        )
        rows = side_model["rows"]
        result.update(
            {
                "selected_body_count": len(selected_body_indices),
                "selected_body_indices": selected_body_indices,
                "selected_modes": selected_modes,
                "allocation": {
                    f"{key[1]}:{key[2]}:{key[3]}": int(value)
                    for key, value in sorted(allocation.items())
                },
                "allocation_tuple": [
                    int(allocation[key]) for key in side_model["class_keys"]
                ],
                "selected_bodies": [
                    {
                        "local_body_index": index,
                        "global_row_index": int(rows[index]["global_row_index"]),
                        "template": str(rows[index]["template"]),
                        "body": [list(value) for value in rows[index]["body"]],
                        "body_digest": str(rows[index]["body_digest"]),
                        "is_current": bool(rows[index]["is_current"]),
                        "current_owner": rows[index]["current_owner"],
                        "side": str(rows[index]["side"]),
                    }
                    for index in selected_body_indices
                ],
            }
        )
    return result


def complement_allocation(
    class_keys: Sequence[tuple[str, str, int, int]],
    global_counts: Mapping[tuple[str, str, int, int], int],
    high_tuple: Sequence[int],
) -> dict[tuple[str, str, int, int], int]:
    if len(class_keys) != len(high_tuple):
        raise RuntimeError("E101 allocation tuple width drift")
    return {
        key: int(global_counts[key]) - int(value)
        for key, value in zip(class_keys, high_tuple, strict=True)
    }


def combine_side_witnesses(
    *,
    e095: types.ModuleType,
    restricted: Mapping[str, Any],
    low: Mapping[str, Any],
    high: Mapping[str, Any],
) -> dict[str, Any]:
    context = restricted["base"]
    all_rows = [dict(row) for row in restricted["rows"]]
    selected_side_rows: list[dict[str, Any]] = []
    selected_modes: list[dict[str, Any]] = []
    for side_result in (low, high):
        mode_by_global = {
            int(row["global_row_index"]): dict(row)
            for row in side_result["selected_modes"]
        }
        for body in side_result["selected_bodies"]:
            global_row_index = int(body["global_row_index"])
            selected_side_rows.append(
                {
                    **all_rows[global_row_index],
                    "global_row_index": global_row_index,
                    "side": str(body["side"]),
                }
            )
            selected_modes.append(
                {
                    **mode_by_global[global_row_index],
                    "global_row_index": global_row_index,
                }
            )
    if len(selected_side_rows) != EXPECTED_BODY_COUNT:
        raise RuntimeError("E101 combined B body count drift")

    selected_side_rows.sort(
        key=lambda row: (str(row["body_digest"]), int(row["global_row_index"]))
    )
    global_index_by_source = {
        int(row["global_row_index"]): index
        for index, row in enumerate(selected_side_rows)
    }
    materialization_rows = [
        {
            "body_index": global_index_by_source[int(row["global_row_index"])],
            "body_digest": str(row["body_digest"]),
            "class_key": list(row["class_key"]),
        }
        for row in selected_modes
    ]
    stable_indices: dict[str, int] = {}
    for instance_id, footprint in context["stable_footprints"].items():
        matches = [
            index
            for index, row in enumerate(selected_side_rows)
            if tuple(row["body"]) == footprint
        ]
        if len(matches) != 1:
            raise RuntimeError(f"E101 final stable remap drift: {instance_id}")
        stable_indices[instance_id] = matches[0]

    operation_by_body = e095.materialize_named_operations(
        module="B",
        selected_mode_rows=materialization_rows,
        stable_indices=stable_indices,
        operation_counts=context["operation_counts"],
        class_operations=context["class_operations"],
    )
    mode_by_source = {
        int(row["global_row_index"]): dict(row) for row in selected_modes
    }
    selected: list[dict[str, Any]] = []
    pools = context["pools"]
    for body_index, row in enumerate(selected_side_rows):
        source_index = int(row["global_row_index"])
        mode = mode_by_source[source_index]
        template = str(row["template"])
        pose_index = int(mode["pose_index"])
        selected.append(
            {
                "module": "B",
                "side": str(row["side"]),
                "body_index": body_index,
                "source_b_index": int(row["source_b_index"]),
                "template": template,
                "body": [list(value) for value in row["body"]],
                "body_digest": str(row["body_digest"]),
                "is_current": bool(row["is_current"]),
                "current_owner": row["current_owner"],
                "operation": operation_by_body[body_index],
                "pose_index": pose_index,
                "pose_id": str(pools[template][pose_index]["pose_id"]),
                "need_in": int(mode["need_in"]),
                "need_out": int(mode["need_out"]),
                "class_key": list(mode["class_key"]),
            }
        )
    module_b = {
        "status": "OPTIMAL",
        "selected_body_count": len(selected),
        "selected_manufacturing": selected,
        "selected_assignment_digest": stable_digest(selected),
    }
    combined = e095.replay_combined(
        context,
        load_json(E095_MODULE_A),
        module_b,
    )
    return {"module_b": module_b, "combined": combined}


def run(
    *,
    run_dir: Path,
    body_seconds: float,
    high_seconds: float,
    low_seconds: float,
    max_allocations: int,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E101 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e101_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e101_source_e100")
    restricted = e100.build_restricted_context(e095)

    body = body_only_witness(
        e095=e095,
        restricted=restricted,
        seconds=body_seconds,
        seed=101001,
    )
    body_path = run_dir / "BODY_ONLY_RESULT.json"
    dump_exclusive(body_path, body)
    body_status = str(body["status"])

    records: list[dict[str, Any]] = []
    final_module_b: dict[str, Any] | None = None
    final_combined: dict[str, Any] | None = None
    rejected_allocations: list[list[int]] = []

    if body_status not in {"OPTIMAL", "FEASIBLE"}:
        if body_status == "INFEASIBLE":
            verdict = "RESERVED_X42_BODY_POWER_INFEASIBLE"
            decision = "RESTORE_X41_SEPARATOR_BEFORE_FRONT_ALLOCATION_WORK"
        else:
            verdict = "X42_BODY_POWER_ALLOCATION_PROPOSER_CENSORED"
            decision = "CHANGE_BODY_POWER_SOLVER_BEFORE_FRONT_HANDSHAKE"
    else:
        selected_indices = set(map(int, body["selected_body_indices"]))
        high_templates = {
            template: int(body["side_template_counts"].get(f"high:{template}", 0))
            for template in TEMPLATES
        }
        low_templates = {
            template: int(body["side_template_counts"].get(f"low:{template}", 0))
            for template in TEMPLATES
        }
        high_model = build_side_model(
            e095=e095,
            restricted=restricted,
            side="high",
            template_counts=high_templates,
            body_hint_indices=selected_indices,
            fixed_allocation=None,
        )
        class_keys = high_model["class_keys"]
        global_counts = high_model["global_class_counts"]
        terminal = "ITERATION_LIMIT"
        for iteration in range(max_allocations):
            high = solve_side(
                high_model,
                seconds=high_seconds,
                seed=101100 + iteration,
            )
            high_path = run_dir / f"HIGH_RESULT_{iteration:02d}.json"
            dump_exclusive(high_path, high)
            record: dict[str, Any] = {
                "iteration": iteration,
                "high_status": high["status"],
                "high_path": display(high_path),
                "high_sha256": sha256_file(high_path),
                "high_elapsed_seconds": high["elapsed_seconds"],
                "high_branches": high["branches"],
                "high_conflicts": high["conflicts"],
            }
            if high["status"] == "INFEASIBLE":
                terminal = "HIGH_ALLOCATION_SPACE_INFEASIBLE"
                records.append(record)
                break
            if high["status"] not in {"OPTIMAL", "FEASIBLE"}:
                terminal = "HIGH_SIDE_CENSORED"
                records.append(record)
                break

            high_tuple = list(map(int, high["allocation_tuple"]))
            low_allocation = complement_allocation(
                class_keys, global_counts, high_tuple
            )
            low_model = build_side_model(
                e095=e095,
                restricted=restricted,
                side="low",
                template_counts=low_templates,
                body_hint_indices=selected_indices,
                fixed_allocation=low_allocation,
            )
            low = solve_side(
                low_model,
                seconds=low_seconds,
                seed=101200 + iteration,
            )
            low_path = run_dir / f"LOW_RESULT_{iteration:02d}.json"
            dump_exclusive(low_path, low)
            record.update(
                {
                    "high_allocation_tuple": high_tuple,
                    "high_allocation": high["allocation"],
                    "low_complement": {
                        f"{key[1]}:{key[2]}:{key[3]}": int(value)
                        for key, value in sorted(low_allocation.items())
                    },
                    "low_status": low["status"],
                    "low_path": display(low_path),
                    "low_sha256": sha256_file(low_path),
                    "low_elapsed_seconds": low["elapsed_seconds"],
                    "low_branches": low["branches"],
                    "low_conflicts": low["conflicts"],
                }
            )
            records.append(record)
            if low["status"] in {"OPTIMAL", "FEASIBLE"}:
                terminal = "PAIRED_SIDE_WITNESS_FOUND"
                combined = combine_side_witnesses(
                    e095=e095,
                    restricted=restricted,
                    low=low,
                    high=high,
                )
                final_module_b = combined["module_b"]
                final_combined = combined["combined"]
                break
            if low["status"] == "INFEASIBLE":
                high_model["model"].AddForbiddenAssignments(
                    [high_model["allocation_vars"][key] for key in class_keys],
                    [high_tuple],
                )
                rejected_allocations.append(high_tuple)
                terminal = "ALLOCATION_NOGOODS_LEARNED"
                continue
            terminal = "LOW_SIDE_COMPLEMENT_CENSORED"
            break

        if terminal == "PAIRED_SIDE_WITNESS_FOUND":
            verdict = "X42_PAIRED_NATIVE_FRONT_WITNESS_FOUND"
            decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
        elif terminal == "HIGH_ALLOCATION_SPACE_INFEASIBLE":
            verdict = "X42_BODY_TEMPLATE_ALLOCATION_REJECTED_BY_HIGH_SIDE"
            decision = "PROPOSE_NEW_BODY_ONLY_TEMPLATE_ALLOCATION"
        elif terminal == "ALLOCATION_NOGOODS_LEARNED":
            verdict = "X42_ALLOCATION_HANDSHAKE_LEARNED_NOGOODS"
            decision = "CONTINUE_FROM_ALLOCATION_NOGOODS"
        elif terminal == "HIGH_SIDE_CENSORED":
            verdict = "X42_HIGH_SIDE_ALLOCATION_PROPOSER_CENSORED"
            decision = "CHANGE_HIGH_SIDE_SOLVER_OR_DERIVE_ALLOCATION_BOUNDS"
        elif terminal == "LOW_SIDE_COMPLEMENT_CENSORED":
            verdict = "X42_LOW_SIDE_COMPLEMENT_CENSORED"
            decision = "REPLAY_CENSORED_ALLOCATION_WITH_SOLVER_DIVERSITY"
        else:
            verdict = "X42_ALLOCATION_HANDSHAKE_CENSORED"
            decision = "CONTINUE_CONDITIONED_SIDE_DECOMPOSITION"

    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"
    if final_module_b is not None:
        dump_exclusive(module_b_path, final_module_b)
    if final_combined is not None:
        dump_exclusive(combined_path, final_combined)

    result = {
        "schema": "zmd_e101_x42_allocation_handshake_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "body_seconds": body_seconds,
            "high_seconds_per_allocation": high_seconds,
            "low_seconds_per_allocation": low_seconds,
            "max_allocations": max_allocations,
            "reserved_column_x": 42,
            "source_isolated_helpers": True,
        },
        "body_only": {
            "path": display(body_path),
            "sha256": sha256_file(body_path),
            "status": body_status,
            "elapsed_seconds": body["elapsed_seconds"],
            "branches": body["branches"],
            "conflicts": body["conflicts"],
            "side_body_counts": body.get("side_body_counts"),
            "side_template_counts": body.get("side_template_counts"),
            "retained_anchor_count": body.get("retained_anchor_count"),
        },
        "handshake_records": records,
        "tested_allocation_count": sum(
            1 for row in records if row.get("high_allocation_tuple") is not None
        ),
        "rejected_allocation_tuples": rejected_allocations,
        "module_b_witness": (
            {
                "path": display(module_b_path),
                "sha256": sha256_file(module_b_path),
                "selected_body_count": final_module_b["selected_body_count"],
                "selected_assignment_digest": final_module_b[
                    "selected_assignment_digest"
                ],
            }
            if final_module_b is not None
            else None
        ),
        "combined_witness": (
            {
                "path": display(combined_path),
                "sha256": sha256_file(combined_path),
                "status": final_combined["status"],
                "selected_manufacturing_count": final_combined[
                    "selected_manufacturing_count"
                ],
                "selected_assignment_digest": final_combined[
                    "selected_assignment_digest"
                ],
            }
            if final_combined is not None
            else None
        ),
        "truth_boundary": (
            "The body-only template allocation is one exact proposal. High-side "
            "INFEASIBLE rejects that proposal; low-side INFEASIBLE rejects one "
            "class allocation. UNKNOWN remains censored. Only a paired replayed "
            "positive transfers to unrestricted module B."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--body-seconds", type=float, default=BODY_SECONDS)
    parser.add_argument("--high-seconds", type=float, default=HIGH_SECONDS)
    parser.add_argument("--low-seconds", type=float, default=LOW_SECONDS)
    parser.add_argument("--max-allocations", type=int, default=MAX_ALLOCATIONS)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            body_seconds=float(args.body_seconds),
            high_seconds=float(args.high_seconds),
            low_seconds=float(args.low_seconds),
            max_allocations=int(args.max_allocations),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "body_status": result["body_only"]["status"],
                    "tested_allocation_count": result["tested_allocation_count"],
                    "rejected_allocation_count": len(
                        result["rejected_allocation_tuples"]
                    ),
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
            "schema": "zmd_e101_execution_failure_v1",
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
