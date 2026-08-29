#!/usr/bin/env python3
"""E100: source-stable reserved-x42 hybrid constructor for module B."""

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
from typing import Any, Mapping

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E100_source_stable_reserved_x42_hybrid/run-001"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition"
)
E095_RUNNER = E095_DIR / "run_e095.py"
E095_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/RESULT.json"
)
E095_CHECK = E095_RESULT.with_name("ARTIFACT_CHECK.json")
E095_MODULE_A = E095_RESULT.with_name("MODULE_A_RESULT.json")
E099_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E099_source_isolated_e096_revalidation"
)
E099_DURABLE = E099_DIR / "RESULT.txt"
E099_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E099_source_isolated_e096_revalidation/run-002/RESULT.json"
)
E099_CHECK = E099_RESULT.with_name("ARTIFACT_CHECK.json")
ANCHOR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001/"
    "state-00-partition_90abd29523f2a0dc/RESULT.json"
)

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_RESULT: "78de6850a02e66d1018a6f3f3ec545d624e16bdc0cf7e4ef1b455ea2eb25e609",
    E095_CHECK: "6d75894d7a79cb9611fc20d1121a832777f9cf4eeb8e67bb4fef85066d0ee43f",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E099_DURABLE: "ef3630b15b2b9b31555e9665b4ebf9bb7fd7f5d6d5cfb18da096b89632f8d138",
    E099_RESULT: "cb602a987cd47382b8dd64ed224f931029d7a41abf2a9d367e2e6df21b767f55",
    E099_CHECK: "ee7c22fac2795c20afbd568fdaf08062762556d5f9eba75c4ae09b20e825e9f8",
    ANCHOR: "7bc3cc6ccd48f919e08561c7b32262da56f9f3853d5fbca313413add4bd87a78",
}

RESERVED_X = 42
SEAM_Y = 41
EXPECTED_B_CANDIDATES = 4378
EXPECTED_REMOVED_CANDIDATES = 249
EXPECTED_SURVIVORS = 4129
EXPECTED_SIDE_CANDIDATES = {"low": 2805, "high": 1324}
EXPECTED_ANCHOR_REMOVED = 4
EXPECTED_ANCHOR_HINTS = 87
EXPECTED_B_BODY_COUNT = 91
EXPECTED_CLASS_DIMENSIONS = 8
EXPECTED_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 53,
    "manufacturing_5x5": 17,
    "manufacturing_6x4": 21,
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
        raise RuntimeError("E100 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E100 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"E100 input drift: {path}: {observed} != {expected}")
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    e095_result = load_json(E095_RESULT)
    if e095_result.get("verdict") != "MODULE_B_FRONT_SUBMODEL_CENSORED":
        raise RuntimeError("E100 E095 verdict drift")
    if e095_result.get("decision") != "DECOMPOSE_MODULE_B_BY_TEMPLATE_OR_BAY":
        raise RuntimeError("E100 E095 decision drift")
    if load_json(E095_CHECK).get("status") != "PASS":
        raise RuntimeError("E100 E095 check is not PASS")
    module_a = load_json(E095_MODULE_A)
    if module_a.get("status") != "OPTIMAL" or int(
        module_a.get("selected_body_count", -1)
    ) != 128:
        raise RuntimeError("E100 frozen module-A witness drift")

    e099 = load_json(E099_RESULT)
    if e099.get("verdict") != (
        "SOURCE_ISOLATED_REPLAY_INVALIDATES_COMMITTED_E096_SELECTION"
    ):
        raise RuntimeError("E100 E099 verdict drift")
    if e099.get("decision") != (
        "RETRACT_E096_E097_AND_BUILD_HYBRID_INTERFACE_FROM_E095"
    ):
        raise RuntimeError("E100 E099 decision drift")
    stable = e099.get("source_stable_interface", {})
    if stable.get("verdict") != "TEMPLATE_AND_SPATIAL_INTERFACES_ARE_INCOMPARABLE":
        raise RuntimeError("E100 source-stable E096 verdict drift")
    if stable.get("selected", {}).get("cut_id") != "x_after_41":
        raise RuntimeError("E100 source-stable cut drift")
    if int(stable.get("selected", {}).get("class_allocation_dimension_count", -1)) != 8:
        raise RuntimeError("E100 source-stable allocation dimension drift")
    if load_json(E099_CHECK).get("status") != "PASS":
        raise RuntimeError("E100 E099 check is not PASS")

    anchor = load_json(ANCHOR)
    if anchor.get("status") != "BODY_POWER_FEASIBLE":
        raise RuntimeError("E100 anchor status drift")
    if len(anchor.get("selected_manufacturing", [])) != 219:
        raise RuntimeError("E100 anchor manufacturing count drift")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def build_restricted_context(e095: types.ModuleType) -> dict[str, Any]:
    context = e095.build_context()
    if e095.decomposition_audit(context).get("status") != "PASS":
        raise RuntimeError("E100 imported E095 product audit is not PASS")

    all_b = [dict(row) for row in context["body_rows"] if row["module"] == "B"]
    if len(all_b) != EXPECTED_B_CANDIDATES:
        raise RuntimeError(f"E100 B candidate count drift: {len(all_b)}")

    rows: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for source_index, row in enumerate(all_b):
        body = tuple(row["body"])
        xs = [x for x, _y in body]
        if RESERVED_X in xs:
            removed.append({**row, "source_b_index": source_index})
            continue
        if max(xs) <= RESERVED_X - 1:
            side = "low"
        elif min(xs) >= RESERVED_X + 1:
            side = "high"
        else:
            raise RuntimeError(f"E100 nonreserved side classification drift: {body}")
        rows.append({**row, "source_b_index": source_index, "side": side})

    side_counts = Counter(str(row["side"]) for row in rows)
    if len(removed) != EXPECTED_REMOVED_CANDIDATES:
        raise RuntimeError(f"E100 removed-candidate drift: {len(removed)}")
    if len(rows) != EXPECTED_SURVIVORS:
        raise RuntimeError(f"E100 survivor-count drift: {len(rows)}")
    if dict(side_counts) != EXPECTED_SIDE_CANDIDATES:
        raise RuntimeError(f"E100 side-count drift: {side_counts}")

    anchor_bodies = set(context["hint_bodies"]["B"])
    anchor_removed = sum(tuple(row["body"]) in anchor_bodies for row in removed)
    anchor_hints = sum(tuple(row["body"]) in anchor_bodies for row in rows)
    if anchor_removed != EXPECTED_ANCHOR_REMOVED or anchor_hints != EXPECTED_ANCHOR_HINTS:
        raise RuntimeError(
            f"E100 anchor partition drift: removed={anchor_removed} hints={anchor_hints}"
        )

    reserved_column = {(RESERVED_X, y) for y in range(SEAM_Y + 1, 70)}
    fixed_hits = reserved_column & set(context["fixed_solid"])
    if fixed_hits:
        raise RuntimeError(f"E100 reserved column hits fixed solid: {fixed_hits}")

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
    template_survivors = Counter(
        (str(row["side"]), str(row["template"])) for row in rows
    )
    template_removed = Counter(str(row["template"]) for row in removed)
    audit = {
        "schema": "zmd_e100_reserved_x42_product_audit_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "reserved_column_x": RESERVED_X,
        "reserved_column_y_range": [SEAM_Y + 1, 69],
        "all_b_candidate_count": len(all_b),
        "removed_candidate_count": len(removed),
        "survivor_candidate_count": len(rows),
        "side_candidate_counts": dict(sorted(side_counts.items())),
        "side_template_candidate_counts": {
            f"{side}:{template}": int(count)
            for (side, template), count in sorted(template_survivors.items())
        },
        "removed_template_candidate_counts": dict(sorted(template_removed.items())),
        "anchor_removed_count": anchor_removed,
        "anchor_hint_count": anchor_hints,
        "reserved_column_fixed_solid_count": len(fixed_hits),
        "cross_body_cell_count": len(low_body & high_body),
        "low_front_high_body_intersection_count": len(low_front & high_body),
        "high_front_low_body_intersection_count": len(high_front & low_body),
        "cross_front_front_intersection_count": len(low_front & high_front),
        "cross_front_front_cells": [list(value) for value in sorted(low_front & high_front)],
        "truth_boundary": (
            "Exact low/high product audit after excluding module-B manufacturing "
            "bodies on x=42. Front/front coincidence is outside native-front semantics."
        ),
    }
    if (
        audit["cross_body_cell_count"]
        or audit["low_front_high_body_intersection_count"]
        or audit["high_front_low_body_intersection_count"]
    ):
        raise RuntimeError(f"E100 reserved-column product audit failed: {audit}")
    return {
        "base": context,
        "rows": rows,
        "removed": removed,
        "audit": audit,
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


def solve_restricted(
    *,
    e095: types.ModuleType,
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
        raise RuntimeError(f"E100 class dimension drift: {class_counts}")

    mode_rows: list[dict[str, Any]] = []
    vars_by_body: dict[int, list[Any]] = defaultdict(list)
    vars_by_side_class: dict[
        tuple[str, tuple[str, str, int, int]], list[Any]
    ] = defaultdict(list)
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
    if dict(template_counts) != EXPECTED_TEMPLATE_COUNTS:
        raise RuntimeError(f"E100 template-count drift: {template_counts}")
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
            raise RuntimeError(f"E100 stable body remap drift {instance_id}: {matches}")
        stable_indices[instance_id] = matches[0]
        model.Add(body_vars[matches[0]] == 1)

    anchor_bodies = set(context["hint_bodies"]["B"])
    compatible_anchor_count = 0
    for index, row in enumerate(rows):
        selected = tuple(row["body"]) in anchor_bodies
        model.AddHint(body_vars[index], int(selected))
        compatible_anchor_count += int(selected)
    if compatible_anchor_count != EXPECTED_ANCHOR_HINTS:
        raise RuntimeError(
            f"E100 compatible anchor drift: {compatible_anchor_count}"
        )

    validation = model.Validate()
    if validation:
        raise RuntimeError(f"E100 model invalid: {validation}")
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(seed, seconds)
    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)

    result: dict[str, Any] = {
        "schema": "zmd_e100_reserved_x42_module_b_result_v1",
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
            "Exact fixed-skeleton module-B native-front model under the additional "
            "sufficient restriction that no manufacturing body occupies x=42."
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
            raise RuntimeError("E100 selected body count drift")
        if len(selected_modes) != EXPECTED_B_BODY_COUNT:
            raise RuntimeError("E100 selected mode count drift")

        operation_by_body = e095.materialize_named_operations(
            module="B",
            selected_mode_rows=selected_modes,
            stable_indices=stable_indices,
            operation_counts=context["operation_counts"],
            class_operations=context["class_operations"],
        )
        mode_by_body = {int(row["body_index"]): row for row in selected_modes}
        selected: list[dict[str, Any]] = []
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
        raise FileExistsError(f"refusing to reuse E100 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e100_source_e095")
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
        verdict = "SOURCE_STABLE_RESERVED_X42_FRONT_WITNESS_FOUND"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif status == "INFEASIBLE":
        verdict = "SOURCE_STABLE_RESERVED_X42_CONSTRUCTOR_INFEASIBLE"
        decision = "RESTORE_X41_SEPARATOR_AND_SOLVE_HYBRID_ALLOCATIONS"
    else:
        verdict = "SOURCE_STABLE_RESERVED_X42_CONSTRUCTOR_CENSORED"
        decision = "SOLVE_X42_LOW_HIGH_SIDES_CONDITIONED_ON_ALLOCATIONS"

    result = {
        "schema": "zmd_e100_source_stable_reserved_x42_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "imported_e095_identity": e095_identity,
        "source_execution": {
            "operation_profiles_source_sha256": sha256_file(OPERATION_PROFILES),
            "e095_source_sha256": sha256_file(E095_RUNNER),
            "bytecode_cache_consumed_for_these_modules": False,
        },
        "controls": {
            "reserved_column_x": RESERVED_X,
            "reserved_column_y_range": [SEAM_Y + 1, 69],
            "solve_seconds": float(seconds),
            "seed": int(seed),
            "pure_feasibility": True,
            "stop_after_first_solution": True,
        },
        "reserved_column_audit": {
            "path": display(audit_path),
            "sha256": sha256_file(audit_path),
            **{
                key: restricted["audit"][key]
                for key in (
                    "all_b_candidate_count",
                    "removed_candidate_count",
                    "survivor_candidate_count",
                    "side_candidate_counts",
                    "anchor_removed_count",
                    "anchor_hint_count",
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
            "INFEASIBLE or UNKNOWN applies only to reserved x=42. Terminal "
            "uniqueness and commodity semantics remain outside."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--seconds", type=float, default=240.0)
    parser.add_argument("--seed", type=int, default=100001)
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
            "schema": "zmd_e100_execution_failure_v1",
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
