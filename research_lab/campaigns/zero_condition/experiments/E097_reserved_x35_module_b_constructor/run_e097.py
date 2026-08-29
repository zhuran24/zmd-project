#!/usr/bin/env python3
"""E097: sufficient module-B constructor with manufacturing-free column x=35."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback
from types import ModuleType
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E097_reserved_x35_module_b_constructor/run-001"
)
E095_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition/run_e095.py"
)
E095_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/RESULT.json"
)
E095_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/ARTIFACT_CHECK.json"
)
E095_MODULE_A = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/MODULE_A_RESULT.json"
)
E095_DURABLE = E095_RUNNER.with_name("RESULT.txt")
E096_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E096_module_b_interface_thickness/run-001/RESULT.json"
)
E096_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E096_module_b_interface_thickness/run-001/ARTIFACT_CHECK.json"
)
ANCHOR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001/"
    "state-00-partition_90abd29523f2a0dc/RESULT.json"
)

EXPECTED_HASHES = {
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_RESULT: "78de6850a02e66d1018a6f3f3ec545d624e16bdc0cf7e4ef1b455ea2eb25e609",
    E095_CHECK: "6d75894d7a79cb9611fc20d1121a832777f9cf4eeb8e67bb4fef85066d0ee43f",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E095_DURABLE: "6794d794cbd512c5bc01379a2f29ace4080127dc8c4d98bd706b9a792e536b14",
    E096_RESULT: "b16062ce71a9bf40943bd9adcb788249b68099906ab4bb360d48800230dc10f2",
    E096_CHECK: "695eae5cac25ac72c5f3f0fa4b76cd79c0c03042c8290bd746dcd960edcf8192",
    ANCHOR: "7bc3cc6ccd48f919e08561c7b32262da56f9f3853d5fbca313413add4bd87a78",
}

RESERVED_X = 35
SEAM_Y = 41
EXPECTED_B_CANDIDATES = 4378
EXPECTED_LOW_CANDIDATES = 1915
EXPECTED_SEPARATOR_CANDIDATES = 436
EXPECTED_HIGH_CANDIDATES = 2027
EXPECTED_SURVIVORS = EXPECTED_LOW_CANDIDATES + EXPECTED_HIGH_CANDIDATES
EXPECTED_B_BODY_COUNT = 91
EXPECTED_CLASS_DIMENSIONS = 8


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


def import_e095() -> ModuleType:
    name = "zmd_e097_pinned_e095"
    spec = importlib.util.spec_from_file_location(name, E095_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import E095 runner: {E095_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E097 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E097 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E097 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    e095 = load_json(E095_RESULT)
    if e095.get("verdict") != "MODULE_B_FRONT_SUBMODEL_CENSORED":
        raise RuntimeError("E097 E095 trigger verdict drift")
    if e095.get("decision") != "DECOMPOSE_MODULE_B_BY_TEMPLATE_OR_BAY":
        raise RuntimeError("E097 E095 trigger decision drift")
    if load_json(E095_CHECK).get("status") != "PASS":
        raise RuntimeError("E097 E095 artifact check is not PASS")
    module_a = load_json(E095_MODULE_A)
    if module_a.get("status") != "OPTIMAL" or int(
        module_a.get("selected_body_count", -1)
    ) != 128:
        raise RuntimeError("E097 frozen module-A witness drift")

    e096 = load_json(E096_RESULT)
    if e096.get("verdict") != (
        "SPATIAL_SEPARATOR_INTERFACE_DOMINATES_TEMPLATE_INTERFACE"
    ):
        raise RuntimeError("E097 E096 trigger verdict drift")
    if e096.get("decision") != "SELECT_SPATIAL_SEPARATOR_DECOMPOSITION":
        raise RuntimeError("E097 E096 trigger decision drift")
    selected = e096.get("selected_spatial_cut", {})
    if selected.get("cut_id") != "x_after_34":
        raise RuntimeError("E097 E096 selected cut drift")
    expected_groups = {
        "low": EXPECTED_LOW_CANDIDATES,
        "separator": EXPECTED_SEPARATOR_CANDIDATES,
        "high": EXPECTED_HIGH_CANDIDATES,
    }
    if selected.get("group_candidate_counts") != expected_groups:
        raise RuntimeError("E097 E096 group-count drift")
    if int(selected.get("class_allocation_dimension_count", -1)) != (
        EXPECTED_CLASS_DIMENSIONS
    ):
        raise RuntimeError("E097 E096 class-allocation dimension drift")
    if load_json(E096_CHECK).get("status") != "PASS":
        raise RuntimeError("E097 E096 artifact check is not PASS")

    anchor = load_json(ANCHOR)
    if anchor.get("status") != "BODY_POWER_FEASIBLE":
        raise RuntimeError("E097 anchor status drift")
    if len(anchor.get("selected_manufacturing", [])) != 219:
        raise RuntimeError("E097 anchor manufacturing count drift")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def build_restricted_context(e095: ModuleType) -> dict[str, Any]:
    context = e095.build_context()
    e095_audit = e095.decomposition_audit(context)
    if e095_audit.get("status") != "PASS":
        raise RuntimeError("E097 imported E095 product audit is not PASS")

    all_b = [dict(row) for row in context["body_rows"] if row["module"] == "B"]
    if len(all_b) != EXPECTED_B_CANDIDATES:
        raise RuntimeError(f"E097 B candidate count drift: {len(all_b)}")

    rows: list[dict[str, Any]] = []
    separator_count = 0
    for source_index, row in enumerate(all_b):
        body = tuple(row["body"])
        xs = [x for x, _y in body]
        if RESERVED_X in xs:
            separator_count += 1
            continue
        if max(xs) <= RESERVED_X - 1:
            side = "low"
        elif min(xs) >= RESERVED_X + 1:
            side = "high"
        else:
            raise RuntimeError(f"E097 nonseparator side classification drift: {body}")
        rows.append({**row, "source_b_index": source_index, "side": side})
    side_counts = Counter(str(row["side"]) for row in rows)
    if separator_count != EXPECTED_SEPARATOR_CANDIDATES:
        raise RuntimeError(f"E097 separator count drift: {separator_count}")
    if len(rows) != EXPECTED_SURVIVORS:
        raise RuntimeError(f"E097 survivor count drift: {len(rows)}")
    if side_counts != Counter(
        {"low": EXPECTED_LOW_CANDIDATES, "high": EXPECTED_HIGH_CANDIDATES}
    ):
        raise RuntimeError(f"E097 side count drift: {side_counts}")

    reserved_b_column = {(RESERVED_X, y) for y in range(SEAM_Y + 1, 70)}
    fixed_hits = reserved_b_column & set(context["fixed_solid"])
    if fixed_hits:
        raise RuntimeError(f"E097 reserved B column hits fixed solid: {fixed_hits}")

    def all_fronts(side: str) -> set[tuple[int, int]]:
        output: set[tuple[int, int]] = set()
        for row in rows:
            if row["side"] != side:
                continue
            template = str(row["template"])
            for pose_index in row["mode_pose_indices"]:
                pose = context["pools"][template][int(pose_index)]
                for field in ("input_port_cells", "output_port_cells"):
                    output.update(
                        value
                        for raw in pose[field]
                        for value in [e095.cell(raw)]
                        if e095.in_grid(value)
                    )
        return output

    low_body = {
        value for row in rows if row["side"] == "low" for value in row["body"]
    }
    high_body = {
        value for row in rows if row["side"] == "high" for value in row["body"]
    }
    low_front = all_fronts("low")
    high_front = all_fronts("high")
    audit = {
        "schema": "zmd_e097_reserved_x35_product_audit_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "reserved_column_x": RESERVED_X,
        "reserved_column_y_range": [SEAM_Y + 1, 69],
        "all_b_candidate_count": len(all_b),
        "separator_candidate_count": separator_count,
        "survivor_candidate_count": len(rows),
        "side_candidate_counts": dict(sorted(side_counts.items())),
        "reserved_column_fixed_solid_count": len(fixed_hits),
        "cross_body_cell_count": len(low_body & high_body),
        "low_front_high_body_intersection_count": len(low_front & high_body),
        "high_front_low_body_intersection_count": len(high_front & low_body),
        "cross_front_front_intersection_count": len(low_front & high_front),
        "cross_front_front_cells": [list(value) for value in sorted(low_front & high_front)],
        "truth_boundary": (
            "Exact low/high product audit after excluding manufacturing bodies on "
            "x=35. Front/front coincidence remains outside native-front semantics."
        ),
    }
    if (
        audit["cross_body_cell_count"]
        or audit["low_front_high_body_intersection_count"]
        or audit["high_front_low_body_intersection_count"]
    ):
        raise RuntimeError(f"E097 reserved-column product audit failed: {audit}")
    return {"base": context, "rows": rows, "audit": audit}


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


def solve_restricted(
    *,
    e095: ModuleType,
    restricted: Mapping[str, Any],
    seconds: float,
    seed: int,
) -> dict[str, Any]:
    context = restricted["base"]
    rows = [dict(row) for row in restricted["rows"]]
    model = cp_model.CpModel()
    body_vars = [model.NewBoolVar(f"b_body_{index}") for index in range(len(rows))]

    body_vars_by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            body_vars_by_cell[value].append(body_vars[index])
    for terms in body_vars_by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    class_counts = {
        key: int(count)
        for key, count in context["class_counts"].items()
        if key[0] == "B"
    }
    if len(class_counts) != EXPECTED_CLASS_DIMENSIONS:
        raise RuntimeError(f"E097 class dimension drift: {class_counts}")

    mode_rows: list[dict[str, Any]] = []
    vars_by_body: dict[int, list[Any]] = defaultdict(list)
    vars_by_side_class: dict[tuple[str, tuple[str, str, int, int]], list[Any]] = (
        defaultdict(list)
    )
    fixed_solid = set(context["fixed_solid"])
    pools = context["pools"]
    for body_index, row in enumerate(rows):
        template = str(row["template"])
        relevant = [key for key in class_counts if key[1] == template]
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
                    f"b_mc_{body_index}_{pose_index}_{need_in}_{need_out}"
                )
                vars_by_body[body_index].append(variable)
                vars_by_side_class[(str(row["side"]), class_key)].append(variable)
                mode_rows.append(
                    {
                        "body_index": body_index,
                        "body_digest": str(row["body_digest"]),
                        "side": str(row["side"]),
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

    allocation_vars: dict[tuple[str, tuple[str, str, int, int]], Any] = {}
    for class_index, (class_key, required) in enumerate(sorted(class_counts.items())):
        low = model.NewIntVar(0, required, f"alloc_low_{class_index}")
        high = model.NewIntVar(0, required, f"alloc_high_{class_index}")
        allocation_vars[("low", class_key)] = low
        allocation_vars[("high", class_key)] = high
        model.Add(low + high == required)
        model.Add(sum(vars_by_side_class[("low", class_key)]) == low)
        model.Add(sum(vars_by_side_class[("high", class_key)]) == high)

    template_counts: Counter[str] = Counter()
    for (_module, template, _need_in, _need_out), count in class_counts.items():
        template_counts[template] += int(count)
    for template, required in sorted(template_counts.items()):
        model.Add(
            sum(
                body_vars[index]
                for index, row in enumerate(rows)
                if row["template"] == template
            )
            == required
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
                for body_var in body_vars_by_cell.get(value, [])
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

    stable_indices: dict[str, int] = {}
    for instance_id, footprint in context["stable_footprints"].items():
        matches = [
            index
            for index, row in enumerate(rows)
            if tuple(row["body"]) == footprint
            and row["template"] == "manufacturing_6x4"
        ]
        if len(matches) != 1:
            raise RuntimeError(f"E097 stable body remap drift {instance_id}: {matches}")
        stable_indices[instance_id] = matches[0]
        model.Add(body_vars[matches[0]] == 1)

    anchor_bodies = context["hint_bodies"]["B"]
    compatible_anchor_count = 0
    for index, row in enumerate(rows):
        selected = tuple(row["body"]) in anchor_bodies
        model.AddHint(body_vars[index], int(selected))
        compatible_anchor_count += int(selected)
    if compatible_anchor_count != 86:
        raise RuntimeError(
            f"E097 compatible anchor count drift: {compatible_anchor_count} != 86"
        )

    validation = model.Validate()
    if validation:
        raise RuntimeError(f"E097 model invalid: {validation}")
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(seed, seconds)
    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)

    result: dict[str, Any] = {
        "schema": "zmd_e097_reserved_x35_module_b_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": status,
        "solver_status": status,
        "elapsed_seconds": elapsed,
        "seed": int(seed),
        "solve_seconds": float(seconds),
        "reserved_column_x": RESERVED_X,
        "candidate_count": len(rows),
        "side_candidate_counts": dict(
            sorted(Counter(str(row["side"]) for row in rows).items())
        ),
        "required_body_count": EXPECTED_B_BODY_COUNT,
        "class_allocation_dimension_count": len(class_counts),
        "body_variable_count": len(body_vars),
        "mode_class_variable_count": len(mode_rows),
        "allocation_variable_count": len(allocation_vars),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "disabled_unpowered_candidate_count": disabled_unpowered,
        "compatible_anchor_hint_count": compatible_anchor_count,
        "stable_body_candidate_indices": stable_indices,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
        "truth_boundary": (
            "Exact fixed-skeleton module-B native-front class model under the "
            "additional sufficient restriction that no manufacturing body occupies x=35."
        ),
    }

    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_body_indices = [
            index for index, variable in enumerate(body_vars) if solver.Value(variable)
        ]
        selected_modes = [
            {
                "body_index": int(row["body_index"]),
                "body_digest": str(row["body_digest"]),
                "side": str(row["side"]),
                "pose_index": int(row["pose_index"]),
                "class_key": list(row["class_key"]),
                "need_in": int(row["need_in"]),
                "need_out": int(row["need_out"]),
            }
            for row in mode_rows
            if solver.Value(row["variable"])
        ]
        if len(selected_body_indices) != EXPECTED_B_BODY_COUNT:
            raise RuntimeError("E097 selected body count drift")
        if len(selected_modes) != EXPECTED_B_BODY_COUNT:
            raise RuntimeError("E097 selected mode count drift")

        operation_by_body = e095.materialize_named_operations(
            module="B",
            selected_mode_rows=selected_modes,
            stable_indices=stable_indices,
            operation_counts=context["operation_counts"],
            class_operations=context["class_operations"],
        )
        mode_by_body = {int(row["body_index"]): row for row in selected_modes}
        selected = []
        for body_index in selected_body_indices:
            row = rows[body_index]
            mode = mode_by_body[body_index]
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
        allocations = {
            f"{side}:{class_key[1]}:{class_key[2]}:{class_key[3]}": int(
                solver.Value(variable)
            )
            for (side, class_key), variable in sorted(
                allocation_vars.items(), key=lambda item: (item[0][0], item[0][1])
            )
        }
        result.update(
            {
                "selected_body_count": len(selected),
                "retained_current_body_count": sum(
                    bool(row["is_current"]) for row in selected
                ),
                "selected_side_body_counts": dict(
                    sorted(Counter(str(row["side"]) for row in selected).items())
                ),
                "class_allocations": allocations,
                "selected_manufacturing": selected,
                "selected_assignment_digest": stable_digest(selected),
            }
        )
    return result


def run(*, run_dir: Path, seconds: float, seed: int) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E097 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    e095 = import_e095()
    e095_identity = e095.verify_identity()
    restricted = build_restricted_context(e095)
    audit_path = run_dir / "RESERVED_COLUMN_AUDIT.json"
    dump_exclusive(audit_path, restricted["audit"])

    module_b = solve_restricted(
        e095=e095,
        restricted=restricted,
        seconds=seconds,
        seed=seed,
    )
    module_b_path = run_dir / "MODULE_B_RESULT.json"
    dump_exclusive(module_b_path, module_b)

    status = str(module_b["status"])
    combined_path = run_dir / "COMBINED_WITNESS.json"
    combined: dict[str, Any] | None = None
    if status in {"OPTIMAL", "FEASIBLE"}:
        combined = e095.replay_combined(
            restricted["base"],
            load_json(E095_MODULE_A),
            module_b,
        )
        dump_exclusive(combined_path, combined)
        verdict = "RESERVED_X35_MODULE_B_FRONT_WITNESS_FOUND"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif status == "INFEASIBLE":
        verdict = "RESERVED_X35_SUFFICIENT_CONSTRUCTOR_INFEASIBLE"
        decision = "RESTORE_EXPLICIT_SEPARATOR_AND_SOLVE_CONDITIONED_ALLOCATIONS"
    else:
        verdict = "RESERVED_X35_MODULE_B_CONSTRUCTOR_CENSORED"
        decision = "SOLVE_LOW_HIGH_SIDES_CONDITIONED_ON_ALLOCATION_VECTORS"

    result = {
        "schema": "zmd_e097_reserved_x35_constructor_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "imported_e095_identity": e095_identity,
        "controls": {
            "reserved_column_x": RESERVED_X,
            "reserved_column_y_range": [SEAM_Y + 1, 69],
            "solve_seconds": float(seconds),
            "seed": int(seed),
            "stop_after_first_solution": True,
        },
        "reserved_column_audit": {
            "path": display(audit_path),
            "sha256": sha256_file(audit_path),
            **{
                key: restricted["audit"][key]
                for key in (
                    "all_b_candidate_count",
                    "separator_candidate_count",
                    "survivor_candidate_count",
                    "side_candidate_counts",
                    "cross_body_cell_count",
                    "low_front_high_body_intersection_count",
                    "high_front_low_body_intersection_count",
                    "cross_front_front_intersection_count",
                )
            },
        },
        "module_b": {
            "path": display(module_b_path),
            "sha256": sha256_file(module_b_path),
            "status": status,
            "elapsed_seconds": module_b["elapsed_seconds"],
            "candidate_count": module_b["candidate_count"],
            "model_variable_count": module_b["model_variable_count"],
            "model_constraint_count": module_b["model_constraint_count"],
            "branches": module_b["branches"],
            "conflicts": module_b["conflicts"],
            "selected_body_count": module_b.get("selected_body_count", 0),
            "class_allocations": module_b.get("class_allocations"),
        },
        "frozen_module_a": {
            "path": display(E095_MODULE_A),
            "sha256": sha256_file(E095_MODULE_A),
            "status": "OPTIMAL",
            "selected_body_count": 128,
        },
        "combined_witness": (
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
        "truth_boundary": (
            "A positive is a complete fixed-skeleton native-front class witness. "
            "INFEASIBLE or UNKNOWN applies only to the reserved-x35 sufficient "
            "restriction. Terminal uniqueness and commodity semantics remain outside."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--seconds", type=float, default=240.0)
    parser.add_argument("--seed", type=int, default=97001)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            seconds=float(args.seconds),
            seed=int(args.seed),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "module_b_status": result["module_b"]["status"],
                    "elapsed_seconds": result["module_b"]["elapsed_seconds"],
                    "branches": result["module_b"]["branches"],
                    "conflicts": result["module_b"]["conflicts"],
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
            "schema": "zmd_e097_execution_failure_v1",
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
