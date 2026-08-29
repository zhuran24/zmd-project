#!/usr/bin/env python3
"""E105: nested lower/upper class-allocation handshake for reserved y60."""

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
    "E105_nested_allocation_handshake/run-001"
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
E100_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E100_source_stable_reserved_x42_hybrid/run_e100.py"
)
E101_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E101_x42_allocation_handshake/run_e101.py"
)
E101_BODY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
)
E104_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E104_high_reserved_y60_constructor/run_e104.py"
)
E104_DURABLE = E104_RUNNER.with_name("RESULT.txt")
E104_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E104_high_reserved_y60_constructor/run-002"
)
E104_RESULT = E104_RUN / "RESULT.json"
E104_CHECK = E104_RUN / "ARTIFACT_CHECK.json"
E104_AUDIT = E104_RUN / "RESERVED_ROW_AUDIT.json"
E104_HIGH = E104_RUN / "HIGH_RESULT.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    E104_DURABLE: "359ad5214e751853f97d0944cf47af27ad0b85f8f7b9f8fb2cbdaee6bde46098",
    E104_RESULT: "381c6547ed2b94773de4f1fadfe747459aaed307d6c3461f2875a2bdf4817b04",
    E104_CHECK: "7d2167688af5e8b49233d26df49bfaf764dd372e9c103d9437157db483457d86",
    E104_AUDIT: "9277248c332d1f132ae21e9121f08fe7009f69f7a432bd19a6e0a9797d62277c",
    E104_HIGH: "f76ce51a60aeaba6ef11e1ca117d0c9e5c9dec716767a2dec93758bc51fb5043",
}

EXPECTED_TOTAL_BODIES = 26
EXPECTED_TEMPLATES = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
EXPECTED_CLASS_COUNT = 8
MAX_PROPOSER_ALLOCATIONS = 3


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
        raise RuntimeError("E105 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E105 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E105 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load_json(E104_RESULT)
    if result.get("verdict") != "RESERVED_Y60_HIGH_CONSTRUCTOR_CENSORED":
        raise RuntimeError("E105 E104 verdict drift")
    if result.get("decision") != "EXTERNALIZE_LOWER_UPPER_CLASS_ALLOCATIONS":
        raise RuntimeError("E105 E104 decision drift")
    if load_json(E104_CHECK).get("classification") != "CENSORED_HIGH_NO_ALLOCATION":
        raise RuntimeError("E105 E104 check drift")
    if load_json(E104_AUDIT).get("status") != "PASS":
        raise RuntimeError("E105 E104 audit drift")
    if load_json(E104_HIGH).get("status") != "UNKNOWN":
        raise RuntimeError("E105 E104 high status drift")
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
    solver.parameters.stop_after_first_solution = True
    return solver


def body_only(
    *, prepared: Mapping[str, Any], seconds: float, seed: int
) -> dict[str, Any]:
    rows = [dict(row) for row in prepared["survivors"]]
    context = prepared["context"]
    model = cp_model.CpModel()
    variables = [model.NewBoolVar(f"nested_body_{index}") for index in range(len(rows))]
    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(variables[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)
    for template, required in sorted(EXPECTED_TEMPLATES.items()):
        model.Add(
            sum(
                variables[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
            == required
        )
    fixed_coverage = set(context["fixed_coverage"])
    disabled = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & fixed_coverage:
            model.Add(variables[index] == 0)
            disabled += 1
    stable_indices: dict[str, int] = {}
    for instance_id, footprint in context["stable_footprints"].items():
        matches = [
            index for index, row in enumerate(rows) if tuple(row["body"]) == footprint
        ]
        if len(matches) != 1:
            raise RuntimeError(f"E105 stable body remap drift: {instance_id}")
        stable_indices[instance_id] = matches[0]
        model.Add(variables[matches[0]] == 1)
    matched_hints = 0
    for index, row in enumerate(rows):
        hinted = int(row["global_row_index"]) in prepared["body_hint_indices"]
        model.AddHint(variables[index], int(hinted))
        matched_hints += int(hinted)
    if matched_hints != 22:
        raise RuntimeError(f"E105 body hint drift: {matched_hints}")
    error = model.Validate()
    if error:
        raise RuntimeError(f"E105 body model invalid: {error}")
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(seed, seconds)
    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)
    result: dict[str, Any] = {
        "schema": "zmd_e105_nested_body_only_result_v1",
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
        "disabled_unpowered_candidate_count": disabled,
        "matched_hint_count": matched_hints,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
        "stable_local_indices": stable_indices,
    }
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected = [index for index, var in enumerate(variables) if solver.Value(var)]
        if len(selected) != EXPECTED_TOTAL_BODIES:
            raise RuntimeError("E105 body-only selected count drift")
        side_templates = Counter(
            (str(rows[index]["nested_side"]), str(rows[index]["template"]))
            for index in selected
        )
        side_counts = Counter(str(rows[index]["nested_side"]) for index in selected)
        result.update(
            {
                "selected_body_count": len(selected),
                "selected_local_indices": selected,
                "selected_global_indices": [
                    int(rows[index]["global_row_index"]) for index in selected
                ],
                "selected_body_digest": stable_digest(
                    sorted(str(rows[index]["body_digest"]) for index in selected)
                ),
                "nested_side_body_counts": dict(sorted(side_counts.items())),
                "nested_side_template_counts": {
                    f"{side}:{template}": int(count)
                    for (side, template), count in sorted(side_templates.items())
                },
            }
        )
    return result


def build_nested_model(
    *,
    e095: types.ModuleType,
    prepared: Mapping[str, Any],
    nested_side: str,
    template_counts: Mapping[str, int],
    body_hint_indices: set[int],
    allocation_caps: Mapping[tuple[str, str, int, int], int],
) -> dict[str, Any]:
    context = prepared["context"]
    rows = [
        dict(row)
        for row in prepared["survivors"]
        if str(row["nested_side"]) == nested_side
    ]
    model = cp_model.CpModel()
    body_vars = [model.NewBoolVar(f"{nested_side}_body_{index}") for index in range(len(rows))]
    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(body_vars[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    class_keys = tuple(sorted(allocation_caps))
    if len(class_keys) != EXPECTED_CLASS_COUNT:
        raise RuntimeError("E105 class dimension drift")
    mode_rows: list[dict[str, Any]] = []
    vars_by_body: dict[int, list[Any]] = defaultdict(list)
    vars_by_class: dict[tuple[str, str, int, int], list[Any]] = defaultdict(list)
    pools = context["pools"]
    fixed_solid = set(context["fixed_solid"])
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
                    f"{nested_side}_mc_{body_index}_{pose_index}_{need_in}_{need_out}"
                )
                vars_by_body[body_index].append(variable)
                vars_by_class[class_key].append(variable)
                mode_rows.append(
                    {
                        "body_index": body_index,
                        "global_row_index": int(row["global_row_index"]),
                        "body_digest": str(row["body_digest"]),
                        "side": "high",
                        "nested_side": nested_side,
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
        cap = int(allocation_caps[class_key])
        variable = model.NewIntVar(0, cap, f"{nested_side}_alloc_{index}")
        allocation_vars[class_key] = variable
        model.Add(sum(vars_by_class[class_key]) == variable)
    for template, required in sorted(template_counts.items()):
        model.Add(
            sum(
                body_vars[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
            == int(required)
        )
        model.Add(
            sum(variable for key, variable in allocation_vars.items() if key[1] == template)
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
    disabled = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & fixed_coverage:
            model.Add(body_vars[index] == 0)
            disabled += 1
    stable_local: dict[str, int] = {}
    for instance_id, footprint in context["stable_footprints"].items():
        matches = [
            index for index, row in enumerate(rows) if tuple(row["body"]) == footprint
        ]
        if matches:
            if len(matches) != 1:
                raise RuntimeError(f"E105 stable nested remap drift: {instance_id}")
            stable_local[instance_id] = matches[0]
            model.Add(body_vars[matches[0]] == 1)
    matched_hints = 0
    for index, row in enumerate(rows):
        hinted = int(row["global_row_index"]) in body_hint_indices
        model.AddHint(body_vars[index], int(hinted))
        matched_hints += int(hinted)
    error = model.Validate()
    if error:
        raise RuntimeError(f"E105 {nested_side} model invalid: {error}")
    return {
        "model": model,
        "side": nested_side,
        "rows": rows,
        "body_vars": body_vars,
        "mode_rows": mode_rows,
        "allocation_vars": allocation_vars,
        "class_keys": class_keys,
        "template_counts": dict(template_counts),
        "disabled_unpowered_candidate_count": disabled,
        "matched_hint_count": matched_hints,
        "stable_local_indices": stable_local,
    }


def solve_nested(
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
        "schema": "zmd_e105_nested_side_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "nested_side": side_model["side"],
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
        selected_indices = [
            index
            for index, variable in enumerate(side_model["body_vars"])
            if solver.Value(variable)
        ]
        selected_modes = [
            {
                "body_index": int(row["body_index"]),
                "global_row_index": int(row["global_row_index"]),
                "body_digest": str(row["body_digest"]),
                "side": "high",
                "nested_side": str(row["nested_side"]),
                "pose_index": int(row["pose_index"]),
                "class_key": list(row["class_key"]),
                "need_in": int(row["need_in"]),
                "need_out": int(row["need_out"]),
            }
            for row in side_model["mode_rows"]
            if solver.Value(row["variable"])
        ]
        required = sum(int(value) for value in side_model["template_counts"].values())
        if len(selected_indices) != required or len(selected_modes) != required:
            raise RuntimeError("E105 nested selected count drift")
        rows = side_model["rows"]
        values = {
            key: int(solver.Value(variable))
            for key, variable in side_model["allocation_vars"].items()
        }
        result.update(
            {
                "selected_body_count": len(selected_indices),
                "selected_bodies": [
                    {
                        "local_body_index": index,
                        "global_row_index": int(rows[index]["global_row_index"]),
                        "template": str(rows[index]["template"]),
                        "body": [list(value) for value in rows[index]["body"]],
                        "body_digest": str(rows[index]["body_digest"]),
                        "is_current": bool(rows[index]["is_current"]),
                        "current_owner": rows[index]["current_owner"],
                        "side": "high",
                        "nested_side": str(rows[index]["nested_side"]),
                    }
                    for index in selected_indices
                ],
                "selected_modes": selected_modes,
                "allocation": {
                    f"{key[1]}:{key[2]}:{key[3]}": int(value)
                    for key, value in sorted(values.items())
                },
                "allocation_tuple": [int(values[key]) for key in side_model["class_keys"]],
            }
        )
    return result


def merge_high(
    *, class_keys: Sequence[tuple[str, str, int, int]], left: Mapping[str, Any], right: Mapping[str, Any]
) -> dict[str, Any]:
    allocation_tuple = [
        int(left["allocation_tuple"][index]) + int(right["allocation_tuple"][index])
        for index in range(len(class_keys))
    ]
    selected_bodies = [
        *[dict(row) for row in left["selected_bodies"]],
        *[dict(row) for row in right["selected_bodies"]],
    ]
    selected_modes = [
        *[dict(row) for row in left["selected_modes"]],
        *[dict(row) for row in right["selected_modes"]],
    ]
    if len(selected_bodies) != EXPECTED_TOTAL_BODIES or len(selected_modes) != EXPECTED_TOTAL_BODIES:
        raise RuntimeError("E105 merged high count drift")
    return {
        "schema": "zmd_e105_merged_high_side_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "side": "high",
        "status": "FEASIBLE",
        "selected_body_count": len(selected_bodies),
        "selected_bodies": selected_bodies,
        "selected_modes": selected_modes,
        "allocation_tuple": allocation_tuple,
        "allocation": {
            f"{key[1]}:{key[2]}:{key[3]}": int(value)
            for key, value in zip(class_keys, allocation_tuple, strict=True)
        },
        "selected_assignment_digest": stable_digest(
            {
                "bodies": selected_bodies,
                "modes": selected_modes,
                "allocation": allocation_tuple,
            }
        ),
    }


def run(
    *,
    run_dir: Path,
    body_seconds: float,
    proposer_seconds: float,
    consumer_seconds: float,
    outer_low_seconds: float,
    max_allocations: int,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E105 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(OPERATION_PROFILES, "src.preprocess.operation_profiles", package="src.preprocess")
    e095 = source_module(E095_RUNNER, "zmd_e105_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e105_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e105_source_e101")
    e104 = source_module(E104_RUNNER, "zmd_e105_source_e104")
    prepared = e104.reconstruct(e095=e095, e100=e100)

    body = body_only(prepared=prepared, seconds=body_seconds, seed=105100)
    body_path = run_dir / "BODY_ONLY_RESULT.json"
    dump_exclusive(body_path, body)
    if body["status"] not in {"OPTIMAL", "FEASIBLE"}:
        if body["status"] == "INFEASIBLE":
            verdict = "RESERVED_Y60_BODY_TEMPLATE_SPLIT_INFEASIBLE"
            decision = "RESTORE_E103_EXPLICIT_Y59_SEPARATOR"
        else:
            verdict = "RESERVED_Y60_BODY_TEMPLATE_SPLIT_CENSORED"
            decision = "REPLAY_ONLY_NESTED_BODY_POWER_MODEL_WITH_SOLVER_DIVERSITY"
        result = {
            "schema": "zmd_e105_nested_allocation_handshake_result_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "verdict": verdict,
            "decision": decision,
            "identity": identity,
            "body_only": {"path": display(body_path), "sha256": sha256_file(body_path), **body},
            "proposer_side": None,
            "records": [],
            "module_b_witness": None,
            "combined_witness": None,
            "truth_boundary": "Body-only branch only; no native-front allocation or witness follows.",
        }
        dump_exclusive(run_dir / "RESULT.json", result)
        return result

    nested_templates: dict[str, dict[str, int]] = {"lower": {}, "upper": {}}
    for side in ("lower", "upper"):
        for template in EXPECTED_TEMPLATES:
            nested_templates[side][template] = int(
                body["nested_side_template_counts"].get(f"{side}:{template}", 0)
            )
    nested_body_counts = {
        side: sum(counts.values()) for side, counts in nested_templates.items()
    }
    proposer_side = min(
        ("lower", "upper"),
        key=lambda side: (
            nested_body_counts[side],
            812 if side == "lower" else 198,
            side,
        ),
    )
    consumer_side = "upper" if proposer_side == "lower" else "lower"
    selected_hint_indices = set(map(int, body["selected_global_indices"]))
    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(global_counts))
    proposer_model = build_nested_model(
        e095=e095,
        prepared=prepared,
        nested_side=proposer_side,
        template_counts=nested_templates[proposer_side],
        body_hint_indices=selected_hint_indices,
        allocation_caps=global_counts,
    )

    records: list[dict[str, Any]] = []
    final_module_b: dict[str, Any] | None = None
    final_combined: dict[str, Any] | None = None
    total_high_nogood: list[int] | None = None
    terminal = "ALLOCATION_LIMIT"
    for iteration in range(max_allocations):
        proposer = solve_nested(
            proposer_model,
            seconds=proposer_seconds,
            seed=105200 + iteration,
        )
        proposer_path = run_dir / f"PROPOSER_RESULT_{iteration:02d}.json"
        dump_exclusive(proposer_path, proposer)
        record: dict[str, Any] = {
            "iteration": iteration,
            "proposer_side": proposer_side,
            "proposer_path": display(proposer_path),
            "proposer_sha256": sha256_file(proposer_path),
            "proposer_status": proposer["status"],
        }
        if proposer["status"] not in {"OPTIMAL", "FEASIBLE"}:
            terminal = f"PROPOSER_{proposer['status']}"
            records.append(record)
            break

        proposer_tuple = list(map(int, proposer["allocation_tuple"]))
        caps = {
            key: int(global_counts[key]) - proposer_tuple[index]
            for index, key in enumerate(class_keys)
        }
        consumer_model = build_nested_model(
            e095=e095,
            prepared=prepared,
            nested_side=consumer_side,
            template_counts=nested_templates[consumer_side],
            body_hint_indices=selected_hint_indices,
            allocation_caps=caps,
        )
        consumer = solve_nested(
            consumer_model,
            seconds=consumer_seconds,
            seed=105300 + iteration,
        )
        consumer_path = run_dir / f"CONSUMER_RESULT_{iteration:02d}.json"
        dump_exclusive(consumer_path, consumer)
        record.update(
            {
                "proposer_allocation_tuple": proposer_tuple,
                "consumer_side": consumer_side,
                "consumer_path": display(consumer_path),
                "consumer_sha256": sha256_file(consumer_path),
                "consumer_status": consumer["status"],
            }
        )
        if consumer["status"] == "INFEASIBLE":
            proposer_model["model"].AddForbiddenAssignments(
                [proposer_model["allocation_vars"][key] for key in class_keys],
                [proposer_tuple],
            )
            record["effect"] = "EXACT_PROPOSER_ALLOCATION_NOGOOD"
            records.append(record)
            continue
        if consumer["status"] not in {"OPTIMAL", "FEASIBLE"}:
            terminal = f"CONSUMER_{consumer['status']}"
            records.append(record)
            break

        high = merge_high(
            class_keys=class_keys,
            left=proposer,
            right=consumer,
        )
        high_path = run_dir / f"HIGH_WITNESS_{iteration:02d}.json"
        dump_exclusive(high_path, high)
        high_tuple = list(map(int, high["allocation_tuple"]))
        outer_low_allocation = e101.complement_allocation(
            class_keys,
            global_counts,
            high_tuple,
        )
        outer_low_model = e101.build_side_model(
            e095=e095,
            restricted=prepared["restricted"],
            side="low",
            template_counts={
                "manufacturing_3x3": 43,
                "manufacturing_5x5": 11,
                "manufacturing_6x4": 11,
            },
            body_hint_indices=set(map(int, load_json(E101_BODY)["selected_body_indices"])),
            fixed_allocation=outer_low_allocation,
        )
        outer_low = e101.solve_side(
            outer_low_model,
            seconds=outer_low_seconds,
            seed=105400 + iteration,
        )
        outer_low_path = run_dir / f"OUTER_LOW_RESULT_{iteration:02d}.json"
        dump_exclusive(outer_low_path, outer_low)
        record.update(
            {
                "high_path": display(high_path),
                "high_sha256": sha256_file(high_path),
                "total_high_allocation_tuple": high_tuple,
                "outer_low_path": display(outer_low_path),
                "outer_low_sha256": sha256_file(outer_low_path),
                "outer_low_status": outer_low["status"],
            }
        )
        if outer_low["status"] in {"OPTIMAL", "FEASIBLE"}:
            combined = e101.combine_side_witnesses(
                e095=e095,
                restricted=prepared["restricted"],
                low=outer_low,
                high=high,
            )
            final_module_b = combined["module_b"]
            final_combined = combined["combined"]
            module_b_path = run_dir / "MODULE_B_WITNESS.json"
            combined_path = run_dir / "COMBINED_WITNESS.json"
            dump_exclusive(module_b_path, final_module_b)
            dump_exclusive(combined_path, final_combined)
            record["effect"] = "PAIRED_219_BODY_NATIVE_FRONT_WITNESS"
            records.append(record)
            terminal = "FULL_POSITIVE"
            break
        if outer_low["status"] == "INFEASIBLE":
            total_high_nogood = high_tuple
            record["effect"] = "EXACT_TOTAL_HIGH_ALLOCATION_NOGOOD"
            records.append(record)
            terminal = "OUTER_LOW_INFEASIBLE"
            break
        record["effect"] = "OUTER_LOW_CENSORED"
        records.append(record)
        terminal = f"OUTER_LOW_{outer_low['status']}"
        break

    if terminal == "FULL_POSITIVE":
        verdict = "NESTED_ALLOCATION_HANDSHAKE_WITNESS_FOUND"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif terminal == "OUTER_LOW_INFEASIBLE":
        verdict = "NESTED_HANDSHAKE_TOTAL_HIGH_ALLOCATION_REJECTED"
        decision = "RECORD_TOTAL_HIGH_ALLOCATION_NOGOOD_AND_CONTINUE_NESTED_HANDSHAKE"
    elif terminal.startswith("OUTER_LOW_"):
        verdict = "NESTED_HANDSHAKE_OUTER_LOW_CENSORED"
        decision = "REPLAY_ONLY_PINNED_OUTER_LOW_COMPLEMENT"
    elif terminal.startswith("CONSUMER_"):
        verdict = "NESTED_ALLOCATION_CONSUMER_CENSORED"
        decision = "REPLAY_ONLY_PINNED_NESTED_CONSUMER"
    elif terminal.startswith("PROPOSER_INFEASIBLE"):
        verdict = "NESTED_TEMPLATE_SPLIT_NATIVE_FRONT_INFEASIBLE"
        decision = "ADD_EXACT_BODY_TEMPLATE_SPLIT_NOGOOD"
    elif terminal.startswith("PROPOSER_"):
        verdict = "NESTED_ALLOCATION_PROPOSER_CENSORED"
        decision = "CHANGE_ONLY_PROPOSER_SOLVER_OR_DERIVE_SIDE_CAPACITY"
    else:
        verdict = "NESTED_ALLOCATION_HANDSHAKE_LIMIT_REACHED"
        decision = "CONTINUE_FROM_REJECTED_PROPOSER_ALLOCATION_SET"

    result = {
        "schema": "zmd_e105_nested_allocation_handshake_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "body_seconds": body_seconds,
            "proposer_seconds": proposer_seconds,
            "consumer_seconds": consumer_seconds,
            "outer_low_seconds": outer_low_seconds,
            "max_proposer_allocations": max_allocations,
            "source_isolated_helpers": True,
        },
        "body_only": {
            "path": display(body_path),
            "sha256": sha256_file(body_path),
            "status": body["status"],
            "elapsed_seconds": body["elapsed_seconds"],
            "nested_side_body_counts": body.get("nested_side_body_counts"),
            "nested_side_template_counts": body.get("nested_side_template_counts"),
        },
        "proposer_side": proposer_side,
        "consumer_side": consumer_side,
        "records": records,
        "rejected_proposer_allocation_count": sum(
            record.get("effect") == "EXACT_PROPOSER_ALLOCATION_NOGOOD"
            for record in records
        ),
        "total_high_allocation_nogood": total_high_nogood,
        "module_b_witness": (
            {
                "path": "research_lab/local/zero_condition/E105_nested_allocation_handshake/run-001/MODULE_B_WITNESS.json",
                "sha256": sha256_file(run_dir / "MODULE_B_WITNESS.json"),
                "selected_body_count": final_module_b["selected_body_count"],
                "selected_assignment_digest": final_module_b["selected_assignment_digest"],
            }
            if final_module_b is not None
            else None
        ),
        "combined_witness": (
            {
                "path": "research_lab/local/zero_condition/E105_nested_allocation_handshake/run-001/COMBINED_WITNESS.json",
                "sha256": sha256_file(run_dir / "COMBINED_WITNESS.json"),
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
            "Body-only chooses one exact nested template split. Nested negatives "
            "and nogoods are allocation-contextual. Only the replayed paired positive "
            "transfers to the fixed-skeleton parent; UNKNOWN remains censored."
        ),
    }
    dump_exclusive(run_dir / "RESULT.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--body-seconds", type=float, default=20.0)
    parser.add_argument("--proposer-seconds", type=float, default=60.0)
    parser.add_argument("--consumer-seconds", type=float, default=60.0)
    parser.add_argument("--outer-low-seconds", type=float, default=90.0)
    parser.add_argument("--max-allocations", type=int, default=MAX_PROPOSER_ALLOCATIONS)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            body_seconds=float(args.body_seconds),
            proposer_seconds=float(args.proposer_seconds),
            consumer_seconds=float(args.consumer_seconds),
            outer_low_seconds=float(args.outer_low_seconds),
            max_allocations=int(args.max_allocations),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "body_status": result["body_only"]["status"],
                    "proposer_side": result["proposer_side"],
                    "record_count": len(result["records"]),
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
            "schema": "zmd_e105_execution_failure_v1",
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
