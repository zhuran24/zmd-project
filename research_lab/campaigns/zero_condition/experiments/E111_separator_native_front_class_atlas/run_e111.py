#!/usr/bin/env python3
"""E111: enumerate separator-internal native-front class states."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import itertools
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
    "E111_separator_native_front_class_atlas/run-002"
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
E103_LIVE = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E103_high_side_interface_capacity_audit/run-003/LIVE_HIGH_CANDIDATES.json"
)
E110_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E110_explicit_separator_template_duty_atlas/run_e110.py"
)
E110_DURABLE = E110_RUNNER.with_name("RESULT.txt")
E110_SNAPSHOT = E110_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E110_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E110_explicit_separator_template_duty_atlas/run-001"
)
E110_RESULT = E110_RUN / "RESULT.json"
E110_PROJECTION = E110_RUN / "SEPARATOR_TEMPLATE_PROJECTION.json"
E110_CHECK = E110_RUN / "ARTIFACT_CHECK.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E103_LIVE: "ebf0c34b174df7036cf6c4bf2f3283dd4ea303998f62520cbd0c74d70aebfd08",
    E110_RUNNER: "30b2fc298ef56ba68053d47977ef139890e862568b53bba70bdf541f677a1fea",
    E110_DURABLE: "6f85129b3e621bc97c36ade2ae1fe3872ed8e2a565d4fcacdb9823862d3c49f0",
    E110_SNAPSHOT: "d4b38cb0a6b8977b027b3676534d5f0f7426f4e8bcea1c54df937f2d81c02aba",
    E110_RESULT: "6b454d85725ac91ffdb7478231fb6b0900d077c701d1a2c81c6d75acff889664",
    E110_PROJECTION: "73570c931c8e8c053ec5a17feaa821e4e69511443882eac01110b470a6537413",
    E110_CHECK: "4b25595170b280f34951f563e61c5a17de46e1cc6b6afbfa97ee7e9421b17bf6",
}

TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
EXPECTED_GROUP_COUNTS = {"low": 812, "separator": 154, "high": 239}
EXPECTED_TEMPLATE_VECTOR_COUNT = 27
EXPECTED_CLASS_COUNT = 8
EXPECTED_FORMAL_CLASS_STATE_COUNT = 353
EXPECTED_SEPARATOR_CANDIDATES = 154


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
        raise RuntimeError("E111 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E111 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E111 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load_json(E110_RESULT)
    if result.get("verdict") != "EXPLICIT_SEPARATOR_TEMPLATE_DUTY_ATLAS_COMPLETE":
        raise RuntimeError("E111 E110 verdict drift")
    if result.get("decision") != "ATTACH_CLASS_COORDINATES_TO_SEPARATOR_VECTORS":
        raise RuntimeError("E111 E110 decision drift")
    projection = load_json(E110_PROJECTION)
    if projection.get("complete") is not True:
        raise RuntimeError("E111 E110 projection is not complete")
    if int(projection.get("vector_count", -1)) != EXPECTED_TEMPLATE_VECTOR_COUNT:
        raise RuntimeError("E111 E110 template vector count drift")
    check = load_json(E110_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "TWENTY_SEVEN_SEPARATOR_TEMPLATE_VECTORS_EXACTLY_ENUMERATED"
    ):
        raise RuntimeError("E111 E110 check drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def bounded_compositions(total: int, caps: Sequence[int]) -> list[tuple[int, ...]]:
    if not caps:
        return [tuple()] if total == 0 else []
    if len(caps) == 1:
        return [(total,)] if 0 <= total <= int(caps[0]) else []
    output: list[tuple[int, ...]] = []
    first_cap = min(int(caps[0]), int(total))
    for value in range(first_cap + 1):
        for tail in bounded_compositions(int(total) - value, caps[1:]):
            output.append((value, *tail))
    return output


def formal_class_states(
    *,
    class_keys: Sequence[tuple[str, str, int, int]],
    class_caps: Mapping[tuple[str, str, int, int], int],
    template_vectors: Sequence[tuple[int, int, int]],
) -> list[tuple[int, ...]]:
    indices_by_template = {
        template: [index for index, key in enumerate(class_keys) if key[1] == template]
        for template in TEMPLATES
    }
    states: set[tuple[int, ...]] = set()
    for vector in template_vectors:
        per_template: list[list[tuple[int, ...]]] = []
        for template_index, template in enumerate(TEMPLATES):
            indices = indices_by_template[template]
            caps = [int(class_caps[class_keys[index]]) for index in indices]
            per_template.append(
                bounded_compositions(int(vector[template_index]), caps)
            )
        for pieces in itertools.product(*per_template):
            values = [0] * len(class_keys)
            for template_index, template in enumerate(TEMPLATES):
                indices = indices_by_template[template]
                for local_index, class_index in enumerate(indices):
                    values[class_index] = int(pieces[template_index][local_index])
            states.add(tuple(values))
    return sorted(states)


def template_vector_from_allocation(
    *,
    class_keys: Sequence[tuple[str, str, int, int]],
    allocation: Sequence[int],
) -> tuple[int, int, int]:
    totals = Counter()
    for index, key in enumerate(class_keys):
        totals[str(key[1])] += int(allocation[index])
    return tuple(int(totals[template]) for template in TEMPLATES)


def body_union(rows: Sequence[Mapping[str, Any]]) -> set[tuple[int, int]]:
    return {value for row in rows for value in row["body"]}


def front_union(
    *,
    e095: types.ModuleType,
    context: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> set[tuple[int, int]]:
    output: set[tuple[int, int]] = set()
    for row in rows:
        template = str(row["template"])
        for pose_index in row["mode_pose_indices"]:
            pose = context["pools"][template][int(pose_index)]
            for field in ("input_port_cells", "output_port_cells"):
                for raw in pose[field]:
                    value = e095.cell(raw)
                    if e095.in_grid(value):
                        output.add(value)
    return output


def coupling_audit(
    *,
    e095: types.ModuleType,
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    groups = {
        group: [
            row
            for row in prepared["rows"]
            if str(row["separator_group"]) == group
        ]
        for group in ("low", "separator", "high")
    }
    bodies = {group: body_union(rows) for group, rows in groups.items()}
    fronts = {
        group: front_union(
            e095=e095,
            context=prepared["context"],
            rows=rows,
        )
        for group, rows in groups.items()
    }
    return {
        "schema": "zmd_e111_separator_side_coupling_audit_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "candidate_counts": {group: len(rows) for group, rows in groups.items()},
        "body_union_cell_counts": {
            group: len(values) for group, values in bodies.items()
        },
        "front_union_cell_counts": {
            group: len(values) for group, values in fronts.items()
        },
        "body_body_intersections": {
            "low_separator": len(bodies["low"] & bodies["separator"]),
            "separator_high": len(bodies["separator"] & bodies["high"]),
            "low_high": len(bodies["low"] & bodies["high"]),
        },
        "front_body_intersections": {
            "separator_front_low_body": len(fronts["separator"] & bodies["low"]),
            "separator_front_high_body": len(fronts["separator"] & bodies["high"]),
            "low_front_separator_body": len(fronts["low"] & bodies["separator"]),
            "high_front_separator_body": len(fronts["high"] & bodies["separator"]),
            "low_front_high_body": len(fronts["low"] & bodies["high"]),
            "high_front_low_body": len(fronts["high"] & bodies["low"]),
        },
        "front_front_intersections": {
            "low_separator": len(fronts["low"] & fronts["separator"]),
            "separator_high": len(fronts["separator"] & fronts["high"]),
            "low_high": len(fronts["low"] & fronts["high"]),
        },
        "truth_boundary": (
            "Candidate-union coupling census. Nonzero separator/side intersections "
            "make separator-only positives optimistic; removing side bodies can only "
            "relax separator front feasibility."
        ),
    }


def build_model(
    *,
    e095: types.ModuleType,
    prepared: Mapping[str, Any],
    formal_states: Sequence[tuple[int, ...]],
    class_keys: Sequence[tuple[str, str, int, int]],
    class_caps: Mapping[tuple[str, str, int, int], int],
) -> dict[str, Any]:
    rows = [
        dict(row)
        for row in prepared["rows"]
        if str(row["separator_group"]) == "separator"
    ]
    if len(rows) != EXPECTED_SEPARATOR_CANDIDATES:
        raise RuntimeError(f"E111 separator candidate count drift: {len(rows)}")

    model = cp_model.CpModel()
    body_vars = [
        model.NewBoolVar(f"separator_body_{index}") for index in range(len(rows))
    ]
    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(body_vars[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    mode_rows: list[dict[str, Any]] = []
    vars_by_body: dict[int, list[Any]] = defaultdict(list)
    vars_by_class: dict[tuple[str, str, int, int], list[Any]] = defaultdict(list)
    pools = prepared["context"]["pools"]
    fixed_solid = set(prepared["context"]["fixed_solid"])
    for body_index, row in enumerate(rows):
        template = str(row["template"])
        relevant = [key for key in class_keys if key[1] == template]
        forced = e095.STABLE_CLASS_BY_BODY.get(str(row["body_digest"]))
        for pose_index in row["mode_pose_indices"]:
            pose = pools[template][int(pose_index)]
            inputs = tuple(e095.cell(value) for value in pose["input_port_cells"])
            outputs = tuple(e095.cell(value) for value in pose["output_port_cells"])
            for class_key in relevant:
                _module, _template, need_in, need_out = class_key
                if forced is not None and (need_in, need_out) != forced:
                    continue
                if need_in > len(inputs) or need_out > len(outputs):
                    continue
                variable = model.NewBoolVar(
                    f"separator_mc_{body_index}_{pose_index}_{need_in}_{need_out}"
                )
                vars_by_body[body_index].append(variable)
                vars_by_class[class_key].append(variable)
                mode_rows.append(
                    {
                        "body_index": body_index,
                        "global_row_index": int(row["global_row_index"]),
                        "body_digest": str(row["body_digest"]),
                        "pose_index": int(pose_index),
                        "class_key": class_key,
                        "need_in": int(need_in),
                        "need_out": int(need_out),
                        "input_cells": inputs,
                        "output_cells": outputs,
                        "variable": variable,
                    }
                )
        if vars_by_body[body_index]:
            model.Add(sum(vars_by_body[body_index]) == body_vars[body_index])
        else:
            model.Add(body_vars[body_index] == 0)

    allocation_vars: dict[tuple[str, str, int, int], Any] = {}
    for index, class_key in enumerate(class_keys):
        variable = model.NewIntVar(
            0,
            int(class_caps[class_key]),
            f"separator_alloc_{index}",
        )
        allocation_vars[class_key] = variable
        model.Add(sum(vars_by_class[class_key]) == variable)

    for template in TEMPLATES:
        model.Add(
            sum(
                body_vars[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
            == sum(
                allocation_vars[key] for key in class_keys if key[1] == template
            )
        )

    ordered_allocation_vars = [allocation_vars[key] for key in class_keys]
    model.AddAllowedAssignments(
        ordered_allocation_vars,
        [list(state) for state in formal_states],
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

    fixed_coverage = set(prepared["context"]["fixed_coverage"])
    disabled_unpowered = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & fixed_coverage:
            model.Add(body_vars[index] == 0)
            disabled_unpowered += 1
    if disabled_unpowered != 0:
        raise RuntimeError(
            f"E111 unary-live power drift: {disabled_unpowered} separator rows"
        )

    stable_separator_indices: dict[str, int] = {}
    for instance_id, footprint in prepared["context"]["stable_footprints"].items():
        matches = [
            index for index, row in enumerate(rows) if tuple(row["body"]) == footprint
        ]
        if matches:
            if len(matches) != 1:
                raise RuntimeError(f"E111 stable separator remap drift: {instance_id}")
            stable_separator_indices[instance_id] = matches[0]
            model.Add(body_vars[matches[0]] == 1)

    anchor_hint_count = 0
    for index, row in enumerate(rows):
        hinted = bool(row["e103_is_anchor"])
        model.AddHint(body_vars[index], int(hinted))
        anchor_hint_count += int(hinted)
    if anchor_hint_count != 1:
        raise RuntimeError(f"E111 separator anchor hint drift: {anchor_hint_count}")

    error = model.Validate()
    if error:
        raise RuntimeError(f"E111 separator model invalid: {error}")
    return {
        "model": model,
        "rows": rows,
        "body_vars": body_vars,
        "mode_rows": mode_rows,
        "allocation_vars": allocation_vars,
        "ordered_allocation_vars": ordered_allocation_vars,
        "class_keys": tuple(class_keys),
        "formal_state_count": len(formal_states),
        "disabled_unpowered_candidate_count": disabled_unpowered,
        "stable_separator_indices": stable_separator_indices,
        "anchor_hint_count": anchor_hint_count,
    }


def solver_for(seed: int, seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = int(seed)
    solver.parameters.stop_after_first_solution = True
    solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    return solver


def extract_witness(
    *,
    e095: types.ModuleType,
    side_model: Mapping[str, Any],
    solver: cp_model.CpSolver,
    allocation: Sequence[int],
) -> dict[str, Any]:
    selected_indices = [
        index
        for index, variable in enumerate(side_model["body_vars"])
        if solver.Value(variable)
    ]
    selected_mode_rows = [
        row for row in side_model["mode_rows"] if solver.Value(row["variable"])
    ]
    if len(selected_indices) != sum(map(int, allocation)):
        raise RuntimeError("E111 selected body/allocation count drift")
    if len(selected_mode_rows) != len(selected_indices):
        raise RuntimeError("E111 selected mode/body count drift")

    mode_by_body = {int(row["body_index"]): row for row in selected_mode_rows}
    if set(mode_by_body) != set(selected_indices):
        raise RuntimeError("E111 selected mode/body identity drift")
    rows = side_model["rows"]
    assignments: list[dict[str, Any]] = []
    for body_index in selected_indices:
        row = rows[body_index]
        mode = mode_by_body[body_index]
        assignments.append(
            {
                "local_body_index": int(body_index),
                "global_row_index": int(row["global_row_index"]),
                "template": str(row["template"]),
                "body": [list(value) for value in row["body"]],
                "body_digest": str(row["body_digest"]),
                "pose_index": int(mode["pose_index"]),
                "class_key": list(mode["class_key"]),
                "need_in": int(mode["need_in"]),
                "need_out": int(mode["need_out"]),
            }
        )

    template_vector = template_vector_from_allocation(
        class_keys=side_model["class_keys"],
        allocation=allocation,
    )
    observed_templates = Counter(str(row["template"]) for row in assignments)
    if tuple(observed_templates[template] for template in TEMPLATES) != template_vector:
        raise RuntimeError("E111 witness template vector drift")

    return {
        "selected_body_count": len(assignments),
        "template_vector": list(template_vector),
        "selected_assignments": assignments,
        "selected_assignment_digest": stable_digest(assignments),
        "semantic_replay": {
            "fixed_obstacle_and_separator_body_front_capacity": True,
            "low_high_bodies_removed": True,
            "in_grid_function": str(e095.in_grid.__name__),
        },
    }


def enumerate_states(
    *,
    e095: types.ModuleType,
    side_model: Mapping[str, Any],
    stage_seconds: float,
    per_solve_seconds: float,
    max_states: int,
) -> dict[str, Any]:
    model = side_model["model"]
    started = time.monotonic()
    before = process_snapshot()
    records: list[dict[str, Any]] = []
    seen: set[tuple[int, ...]] = set()
    terminal = "STATE_LIMIT"
    terminal_status = "NOT_RUN"
    terminal_elapsed = 0.0
    terminal_branches = 0
    terminal_conflicts = 0

    for iteration in range(max_states + 1):
        remaining = float(stage_seconds) - (time.monotonic() - started)
        if remaining <= 0:
            terminal = "STAGE_BUDGET_EXHAUSTED"
            terminal_status = "NOT_RUN"
            break
        solver = solver_for(
            seed=111100 + iteration,
            seconds=min(float(per_solve_seconds), remaining),
        )
        solve_started = time.monotonic()
        status_code = solver.Solve(model)
        solve_elapsed = time.monotonic() - solve_started
        status = solver.StatusName(status_code)
        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if len(records) >= max_states:
                terminal = "STATE_LIMIT"
                terminal_status = status
                terminal_elapsed = solve_elapsed
                terminal_branches = int(solver.NumBranches())
                terminal_conflicts = int(solver.NumConflicts())
                break
            allocation = tuple(
                int(solver.Value(variable))
                for variable in side_model["ordered_allocation_vars"]
            )
            if allocation in seen:
                raise RuntimeError(f"E111 duplicate allocation state: {allocation}")
            seen.add(allocation)
            witness = extract_witness(
                e095=e095,
                side_model=side_model,
                solver=solver,
                allocation=allocation,
            )
            records.append(
                {
                    "iteration": iteration,
                    "allocation_tuple": list(allocation),
                    "allocation": {
                        f"{key[1]}:{key[2]}:{key[3]}": int(allocation[index])
                        for index, key in enumerate(side_model["class_keys"])
                    },
                    "template_vector": witness["template_vector"],
                    "separator_body_count": int(witness["selected_body_count"]),
                    "status": status,
                    "elapsed_seconds": solve_elapsed,
                    "branches": int(solver.NumBranches()),
                    "conflicts": int(solver.NumConflicts()),
                    "witness": witness,
                }
            )
            model.AddForbiddenAssignments(
                side_model["ordered_allocation_vars"],
                [list(allocation)],
            )
            continue
        terminal_status = status
        terminal_elapsed = solve_elapsed
        terminal_branches = int(solver.NumBranches())
        terminal_conflicts = int(solver.NumConflicts())
        terminal = "COMPLETE" if status == "INFEASIBLE" else "CENSORED"
        break

    after = process_snapshot()
    return {
        "schema": "zmd_e111_separator_native_front_class_projection_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": terminal,
        "complete": terminal == "COMPLETE",
        "formal_state_count": side_model["formal_state_count"],
        "feasible_state_count": len(records),
        "records": records,
        "state_digest": stable_digest(
            sorted(tuple(row["allocation_tuple"]) for row in records)
        ),
        "terminal_status": terminal_status,
        "terminal_elapsed_seconds": terminal_elapsed,
        "terminal_branches": terminal_branches,
        "terminal_conflicts": terminal_conflicts,
        "total_elapsed_seconds": time.monotonic() - started,
        "stage_seconds": stage_seconds,
        "per_solve_seconds": per_solve_seconds,
        "max_states": max_states,
        "candidate_count": len(side_model["rows"]),
        "mode_class_variable_count": len(side_model["mode_rows"]),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "disabled_unpowered_candidate_count": side_model[
            "disabled_unpowered_candidate_count"
        ],
        "stable_separator_body_count": len(side_model["stable_separator_indices"]),
        "anchor_hint_count": side_model["anchor_hint_count"],
        "process_before": before,
        "process_after": after,
        "truth_boundary": (
            "Complete only when the post-blocking separator-only relaxation is exact "
            "INFEASIBLE. Positive records omit low/high bodies and are necessary-only "
            "candidates for the full three-module model."
        ),
    }


def summarize(
    *,
    projection: Mapping[str, Any],
    template_vectors: Sequence[tuple[int, int, int]],
    class_keys: Sequence[tuple[str, str, int, int]],
) -> dict[str, Any]:
    records = list(projection["records"])
    state_counts = Counter(
        tuple(map(int, row["template_vector"])) for row in records
    )
    surviving = sorted(state_counts)
    rejected = sorted(set(template_vectors) - set(surviving))
    coordinate_values = [
        [int(row["allocation_tuple"][index]) for row in records]
        for index in range(len(class_keys))
    ]
    return {
        "surviving_template_vector_count": len(surviving),
        "surviving_template_vectors": [list(value) for value in surviving],
        "rejected_template_vector_count": len(rejected),
        "rejected_template_vectors": [list(value) for value in rejected],
        "state_count_by_template_vector": {
            "/".join(map(str, vector)): int(state_counts[vector])
            for vector in surviving
        },
        "separator_body_count_distribution": dict(
            sorted(
                Counter(
                    int(row["separator_body_count"]) for row in records
                ).items()
            )
        ),
        "class_coordinate_ranges": {
            f"{key[1]}:{key[2]}:{key[3]}": {
                "min": min(coordinate_values[index]) if records else None,
                "max": max(coordinate_values[index]) if records else None,
            }
            for index, key in enumerate(class_keys)
        },
        "zero_allocation_present": any(
            all(int(value) == 0 for value in row["allocation_tuple"])
            for row in records
        ),
    }


def run(
    *,
    run_dir: Path,
    stage_seconds: float,
    per_solve_seconds: float,
    max_states: int,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E111 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e111_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e111_source_e100")
    e110 = source_module(E110_RUNNER, "zmd_e111_source_e110")
    prepared = e110.restore_three_groups(e095=e095, e100=e100)
    if prepared["group_counts"] != dict(sorted(EXPECTED_GROUP_COUNTS.items())):
        raise RuntimeError("E111 restored group count drift")

    class_caps = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(class_caps))
    if len(class_keys) != EXPECTED_CLASS_COUNT:
        raise RuntimeError("E111 class dimension drift")

    e110_projection = load_json(E110_PROJECTION)
    template_vectors = sorted(
        {tuple(map(int, row["vector"])) for row in e110_projection["vectors"]}
    )
    if len(template_vectors) != EXPECTED_TEMPLATE_VECTOR_COUNT:
        raise RuntimeError("E111 template vector identity drift")
    formal_states = formal_class_states(
        class_keys=class_keys,
        class_caps=class_caps,
        template_vectors=template_vectors,
    )
    if len(formal_states) != EXPECTED_FORMAL_CLASS_STATE_COUNT:
        raise RuntimeError(
            f"E111 formal state count drift: {len(formal_states)}"
        )

    audit = coupling_audit(e095=e095, prepared=prepared)
    audit_path = run_dir / "COUPLING_AUDIT.json"
    dump_exclusive(audit_path, audit)

    side_model = build_model(
        e095=e095,
        prepared=prepared,
        formal_states=formal_states,
        class_keys=class_keys,
        class_caps=class_caps,
    )
    projection = enumerate_states(
        e095=e095,
        side_model=side_model,
        stage_seconds=stage_seconds,
        per_solve_seconds=per_solve_seconds,
        max_states=max_states,
    )
    projection_path = run_dir / "SEPARATOR_CLASS_PROJECTION.json"
    dump_exclusive(projection_path, projection)
    summary = summarize(
        projection=projection,
        template_vectors=template_vectors,
        class_keys=class_keys,
    )

    if projection["complete"] and projection["feasible_state_count"] > 0:
        verdict = "SEPARATOR_NATIVE_FRONT_RELAXATION_ATLAS_COMPLETE"
        decision = "CONDITION_SIDE_MODELS_ON_SEPARATOR_CLASS_ATLAS"
    elif projection["complete"]:
        verdict = "SEPARATOR_RELAXATION_EMPTY_APPARATUS_CONTRADICTION"
        decision = "AUDIT_ZERO_SEPARATOR_STATE"
    else:
        verdict = "SEPARATOR_NATIVE_FRONT_RELAXATION_ATLAS_CENSORED"
        decision = "CONTINUE_ONLY_FINITE_SEPARATOR_CLASS_ENUMERATION"

    result = {
        "schema": "zmd_e111_separator_native_front_class_atlas_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "formal_class_state_count": len(formal_states),
            "stage_seconds": stage_seconds,
            "per_solve_seconds": per_solve_seconds,
            "max_states": max_states,
            "source_isolated_helpers": True,
            "positive_semantics": "optimistic_separator_only_relaxation",
        },
        "restored_language": {
            "candidate_count": len(prepared["rows"]),
            "group_candidate_counts": prepared["group_counts"],
            "anchor_group_counts": prepared["anchor_group_counts"],
        },
        "coupling_audit": {
            "path": display(audit_path),
            "sha256": sha256_file(audit_path),
            "body_body_intersections": audit["body_body_intersections"],
            "front_body_intersections": audit["front_body_intersections"],
        },
        "projection": {
            "path": display(projection_path),
            "sha256": sha256_file(projection_path),
            "status": projection["status"],
            "complete": projection["complete"],
            "formal_state_count": projection["formal_state_count"],
            "feasible_state_count": projection["feasible_state_count"],
            "state_digest": projection["state_digest"],
            "total_elapsed_seconds": projection["total_elapsed_seconds"],
            "terminal_status": projection["terminal_status"],
        },
        "summary": summary,
        "truth_boundary": (
            "Separator-only native-front relaxation. Exact absent states are safe "
            "necessary rejections. Positive states can be invalidated by low/high "
            "body and front interactions and require conditioned side consumers."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--stage-seconds", type=float, default=150.0)
    parser.add_argument("--per-solve-seconds", type=float, default=5.0)
    parser.add_argument(
        "--max-states",
        type=int,
        default=EXPECTED_FORMAL_CLASS_STATE_COUNT,
    )
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            stage_seconds=float(args.stage_seconds),
            per_solve_seconds=float(args.per_solve_seconds),
            max_states=int(args.max_states),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "projection": result["projection"],
                    "summary": {
                        "surviving_template_vector_count": result["summary"][
                            "surviving_template_vector_count"
                        ],
                        "rejected_template_vector_count": result["summary"][
                            "rejected_template_vector_count"
                        ],
                        "zero_allocation_present": result["summary"][
                            "zero_allocation_present"
                        ],
                    },
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
            "schema": "zmd_e111_execution_failure_v1",
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
