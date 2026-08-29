#!/usr/bin/env python3
"""E104: high-side reserved-y60 native-front constructor."""

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
    "E104_high_reserved_y60_constructor/run-001"
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
E100_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E100_source_stable_reserved_x42_hybrid/run-001/RESULT.json"
)
E100_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E100_source_stable_reserved_x42_hybrid/run-001/ARTIFACT_CHECK.json"
)
E101_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E101_x42_allocation_handshake/run_e101.py"
)
E101_DURABLE = E101_RUNNER.with_name("RESULT.txt")
E101_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E101_x42_allocation_handshake/run-001/RESULT.json"
)
E101_BODY = E101_RESULT.with_name("BODY_ONLY_RESULT.json")
E101_CHECK = E101_RESULT.with_name("ARTIFACT_CHECK.json")
E102_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E102_high_side_solver_diverse_replay/RESULT.txt"
)
E103_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E103_high_side_interface_capacity_audit/run_e103.py"
)
E103_DURABLE = E103_RUNNER.with_name("RESULT.txt")
E103_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E103_high_side_interface_capacity_audit/run-003"
)
E103_RESULT = E103_RUN / "RESULT.json"
E103_CHECK = E103_RUN / "ARTIFACT_CHECK.json"
E103_LIVE = E103_RUN / "LIVE_HIGH_CANDIDATES.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E100_RESULT: "d4de0239604cf4713164069fda553965275566c1840238ec4fa98446ba71b12c",
    E100_CHECK: "b2cc7e2aef54f5e0209a96b124319fa68b834bd0556db1d162732ac123fc5fc4",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_DURABLE: "5395b9a852c9883b9662390740164ef2222710f83edd468985c3056030354f34",
    E101_RESULT: "b6b088f214fcbb3be01b26180ce9d211b647ede4038e7542531077548bfd9e9d",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E101_CHECK: "35eb5580acf84a9b25e7569403ac5aa5814285fa29dd225c9bd5e9bd28eb0055",
    E102_DURABLE: "1d24471e2c304c3f9b2276b1073befeb4ebd30d4268368a12b852e094219cca9",
    E103_RUNNER: "3185bc717e8c0438a47148972476d6176fee8643e23bcb7167a6b54f4be99f48",
    E103_DURABLE: "cee44b989deeea94355d31a69b41510dbe1a74531ec993da5ed9254f9694de6b",
    E103_RESULT: "6fefd59e3b8c5551501a2504e9c620bb6cc5468ac5847b92baa20a8ec6e6a32c",
    E103_CHECK: "63ba0d4085263d12c153db0f639bfd984f9bfd373de0b9828eeaf6e94f98850d",
    E103_LIVE: "ebf0c34b174df7036cf6c4bf2f3283dd4ea303998f62520cbd0c74d70aebfd08",
}

RESERVED_Y = 60
EXPECTED_LIVE_HIGH = 1205
EXPECTED_REMOVED = 195
EXPECTED_LOWER = 812
EXPECTED_UPPER = 198
EXPECTED_SURVIVORS = EXPECTED_LOWER + EXPECTED_UPPER
EXPECTED_HIGH_BODY_COUNT = 26
EXPECTED_CLASS_COUNT = 8
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
EXPECTED_HIGH_TEMPLATES = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
EXPECTED_LOW_TEMPLATES = {
    "manufacturing_3x3": 43,
    "manufacturing_5x5": 11,
    "manufacturing_6x4": 11,
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
        raise RuntimeError("E104 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E104 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"E104 input drift: {path}: {observed} != {expected}")
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    e100 = load_json(E100_RESULT)
    if e100.get("verdict") != "SOURCE_STABLE_RESERVED_X42_CONSTRUCTOR_CENSORED":
        raise RuntimeError("E104 E100 verdict drift")
    if load_json(E100_CHECK).get("status") != "PASS":
        raise RuntimeError("E104 E100 check is not PASS")
    e101 = load_json(E101_RESULT)
    if e101.get("verdict") != "X42_HIGH_SIDE_ALLOCATION_PROPOSER_CENSORED":
        raise RuntimeError("E104 E101 verdict drift")
    if load_json(E101_CHECK).get("status") != "PASS":
        raise RuntimeError("E104 E101 check is not PASS")
    body = load_json(E101_BODY)
    if body.get("status") != "OPTIMAL" or int(body.get("selected_body_count", -1)) != 91:
        raise RuntimeError("E104 E101 body witness drift")
    e103 = load_json(E103_RESULT)
    if e103.get("verdict") != "HIGH_SIDE_SPATIAL_TEMPLATE_HYBRID_SELECTED":
        raise RuntimeError("E104 E103 verdict drift")
    if e103.get("decision") != "RESERVE_SELECTED_SPATIAL_ROW_WITH_TEMPLATE_CLASS_BRIDGE":
        raise RuntimeError("E104 E103 decision drift")
    if e103.get("selected_spatial_cut", {}).get("cut_id") != "y_after_59":
        raise RuntimeError("E104 E103 selected cut drift")
    if e103.get("high_template_counts") != EXPECTED_HIGH_TEMPLATES:
        raise RuntimeError("E104 E103 high template counts drift")
    if load_json(E103_CHECK).get("status") != "PASS":
        raise RuntimeError("E104 E103 check is not PASS")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def reconstruct(
    *,
    e095: types.ModuleType,
    e100: types.ModuleType,
) -> dict[str, Any]:
    restricted = e100.build_restricted_context(e095)
    context = restricted["base"]
    rows = [dict(row) for row in restricted["rows"]]
    live_payload = load_json(E103_LIVE)
    live_raw = list(live_payload["candidates"])
    if int(live_payload.get("candidate_count", -1)) != EXPECTED_LIVE_HIGH:
        raise RuntimeError("E104 live high candidate count drift")

    seen_global: set[int] = set()
    survivors: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for record in live_raw:
        global_index = int(record["global_row_index"])
        if global_index in seen_global:
            raise RuntimeError(f"E104 duplicate global row: {global_index}")
        seen_global.add(global_index)
        if not 0 <= global_index < len(rows):
            raise RuntimeError(f"E104 global row out of range: {global_index}")
        source = rows[global_index]
        if str(source["side"]) != "high":
            raise RuntimeError(f"E104 live row not outer-high: {global_index}")
        expected_body = tuple(tuple(map(int, value)) for value in record["body"])
        if tuple(source["body"]) != expected_body:
            raise RuntimeError(f"E104 body transport drift: {global_index}")
        if str(source["body_digest"]) != str(record["body_digest"]):
            raise RuntimeError(f"E104 body digest drift: {global_index}")
        if str(source["template"]) != str(record["template"]):
            raise RuntimeError(f"E104 template drift: {global_index}")
        if record.get("fixed_powered") is not True or record.get("static_mode_live") is not True:
            raise RuntimeError(f"E104 non-live row entered atlas: {global_index}")
        body = tuple(source["body"])
        if any(y == RESERVED_Y for _x, y in body):
            removed.append({**source, "global_row_index": global_index})
            continue
        max_y = max(y for _x, y in body)
        min_y = min(y for _x, y in body)
        if max_y <= RESERVED_Y - 1:
            nested_side = "lower"
        elif min_y >= RESERVED_Y + 1:
            nested_side = "upper"
        else:
            raise RuntimeError(f"E104 survivor crosses reserved row: {body}")
        survivors.append(
            {
                **source,
                "global_row_index": global_index,
                "nested_side": nested_side,
                "e103_is_anchor": bool(record["is_anchor"]),
                "e103_supported_classes": tuple(
                    tuple(value) for value in record["supported_classes"]
                ),
            }
        )

    side_counts = Counter(str(row["nested_side"]) for row in survivors)
    if len(removed) != EXPECTED_REMOVED:
        raise RuntimeError(f"E104 removed count drift: {len(removed)}")
    if len(survivors) != EXPECTED_SURVIVORS:
        raise RuntimeError(f"E104 survivor count drift: {len(survivors)}")
    if side_counts != Counter({"lower": EXPECTED_LOWER, "upper": EXPECTED_UPPER}):
        raise RuntimeError(f"E104 side count drift: {side_counts}")

    body_hint_indices = set(map(int, load_json(E101_BODY)["selected_body_indices"]))
    surviving_hint_count = sum(
        int(row["global_row_index"]) in body_hint_indices for row in survivors
    )
    removed_hint_count = sum(
        int(row["global_row_index"]) in body_hint_indices for row in removed
    )
    fixed_solid = set(context["fixed_solid"])
    reserved_cells = {(x, RESERVED_Y) for x in range(43, 69)}
    fixed_hits = reserved_cells & fixed_solid

    def front_union(side: str) -> set[tuple[int, int]]:
        output: set[tuple[int, int]] = set()
        for row in survivors:
            if row["nested_side"] != side:
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

    lower_body = {
        value
        for row in survivors
        if row["nested_side"] == "lower"
        for value in row["body"]
    }
    upper_body = {
        value
        for row in survivors
        if row["nested_side"] == "upper"
        for value in row["body"]
    }
    lower_front = front_union("lower")
    upper_front = front_union("upper")
    stable_rows = {
        instance_id: [
            row
            for row in survivors
            if tuple(row["body"]) == footprint
        ]
        for instance_id, footprint in context["stable_footprints"].items()
    }
    if any(len(matches) != 1 for matches in stable_rows.values()):
        raise RuntimeError(f"E104 stable body survivor drift: {stable_rows}")

    audit = {
        "schema": "zmd_e104_reserved_y60_product_audit_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "reserved_row_y": RESERVED_Y,
        "reserved_row_x_range": [43, 68],
        "live_high_candidate_count": len(live_raw),
        "removed_candidate_count": len(removed),
        "survivor_candidate_count": len(survivors),
        "nested_side_candidate_counts": dict(sorted(side_counts.items())),
        "survivor_template_candidate_counts": dict(
            sorted(Counter(str(row["template"]) for row in survivors).items())
        ),
        "removed_template_candidate_counts": dict(
            sorted(Counter(str(row["template"]) for row in removed).items())
        ),
        "surviving_hint_count": surviving_hint_count,
        "removed_hint_count": removed_hint_count,
        "stable_body_sides": {
            instance_id: str(matches[0]["nested_side"])
            for instance_id, matches in sorted(stable_rows.items())
        },
        "reserved_row_fixed_solid_count": len(fixed_hits),
        "reserved_row_fixed_solid_cells": [list(value) for value in sorted(fixed_hits)],
        "cross_body_cell_count": len(lower_body & upper_body),
        "lower_front_upper_body_intersection_count": len(lower_front & upper_body),
        "upper_front_lower_body_intersection_count": len(upper_front & lower_body),
        "cross_front_front_intersection_count": len(lower_front & upper_front),
        "cross_front_front_cells": [list(value) for value in sorted(lower_front & upper_front)],
        "truth_boundary": (
            "Exact product audit after removing E103-live high manufacturing bodies "
            "that occupy y=60. Fixed solids on y=60 remain constant blockers; "
            "front/front coincidence remains outside native-front semantics."
        ),
    }
    if (
        audit["cross_body_cell_count"]
        or audit["lower_front_upper_body_intersection_count"]
        or audit["upper_front_lower_body_intersection_count"]
    ):
        raise RuntimeError(f"E104 reserved-row product audit failed: {audit}")
    return {
        "restricted": restricted,
        "context": context,
        "survivors": survivors,
        "removed": removed,
        "body_hint_indices": body_hint_indices,
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


def build_high_model(
    *,
    e095: types.ModuleType,
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    context = prepared["context"]
    rows = [dict(row) for row in prepared["survivors"]]
    model = cp_model.CpModel()
    body_vars = [model.NewBoolVar(f"high_body_{index}") for index in range(len(rows))]
    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(body_vars[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    global_counts = {
        key: int(count)
        for key, count in context["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(global_counts))
    if len(class_keys) != EXPECTED_CLASS_COUNT:
        raise RuntimeError("E104 class dimension drift")

    mode_rows: list[dict[str, Any]] = []
    vars_by_body: dict[int, list[Any]] = defaultdict(list)
    vars_by_nested_class: dict[
        tuple[str, tuple[str, str, int, int]], list[Any]
    ] = defaultdict(list)
    fixed_solid = set(context["fixed_solid"])
    pools = context["pools"]
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
                    f"high_mc_{body_index}_{pose_index}_{need_in}_{need_out}"
                )
                vars_by_body[body_index].append(variable)
                vars_by_nested_class[(str(row["nested_side"]), class_key)].append(
                    variable
                )
                mode_rows.append(
                    {
                        "body_index": body_index,
                        "global_row_index": int(row["global_row_index"]),
                        "body_digest": str(row["body_digest"]),
                        "side": "high",
                        "nested_side": str(row["nested_side"]),
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

    high_allocation: dict[tuple[str, str, int, int], Any] = {}
    nested_allocation: dict[tuple[str, tuple[str, str, int, int]], Any] = {}
    for class_index, class_key in enumerate(class_keys):
        cap = int(global_counts[class_key])
        high_value = model.NewIntVar(0, cap, f"high_alloc_{class_index}")
        lower_value = model.NewIntVar(0, cap, f"lower_alloc_{class_index}")
        upper_value = model.NewIntVar(0, cap, f"upper_alloc_{class_index}")
        high_allocation[class_key] = high_value
        nested_allocation[("lower", class_key)] = lower_value
        nested_allocation[("upper", class_key)] = upper_value
        model.Add(lower_value + upper_value == high_value)
        model.Add(
            sum(vars_by_nested_class[("lower", class_key)]) == lower_value
        )
        model.Add(
            sum(vars_by_nested_class[("upper", class_key)]) == upper_value
        )

    for template, required in sorted(EXPECTED_HIGH_TEMPLATES.items()):
        model.Add(
            sum(
                body_vars[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
            == int(required)
        )
        model.Add(
            sum(
                high_allocation[key]
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
        if len(matches) != 1:
            raise RuntimeError(f"E104 stable remap drift: {instance_id}")
        stable_local_indices[instance_id] = matches[0]
        model.Add(body_vars[matches[0]] == 1)

    matched_hints = 0
    for index, row in enumerate(rows):
        hinted = int(row["global_row_index"]) in prepared["body_hint_indices"]
        model.AddHint(body_vars[index], int(hinted))
        matched_hints += int(hinted)
    if matched_hints != int(prepared["audit"]["surviving_hint_count"]):
        raise RuntimeError("E104 hint count drift")

    validation = model.Validate()
    if validation:
        raise RuntimeError(f"E104 high model invalid: {validation}")
    return {
        "model": model,
        "rows": rows,
        "body_vars": body_vars,
        "mode_rows": mode_rows,
        "class_keys": class_keys,
        "global_counts": global_counts,
        "high_allocation": high_allocation,
        "nested_allocation": nested_allocation,
        "stable_local_indices": stable_local_indices,
        "disabled_unpowered_candidate_count": disabled_unpowered,
        "matched_hint_count": matched_hints,
    }


def solve_high(
    high_model: Mapping[str, Any], *, seconds: float, seed: int
) -> dict[str, Any]:
    model = high_model["model"]
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(seed, seconds)
    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)
    result: dict[str, Any] = {
        "schema": "zmd_e104_reserved_y60_high_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": status,
        "elapsed_seconds": elapsed,
        "seed": seed,
        "solve_seconds": seconds,
        "candidate_count": len(high_model["rows"]),
        "mode_class_variable_count": len(high_model["mode_rows"]),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "disabled_unpowered_candidate_count": high_model[
            "disabled_unpowered_candidate_count"
        ],
        "matched_hint_count": high_model["matched_hint_count"],
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
    }
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_indices = [
            index
            for index, variable in enumerate(high_model["body_vars"])
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
            for row in high_model["mode_rows"]
            if solver.Value(row["variable"])
        ]
        if len(selected_indices) != EXPECTED_HIGH_BODY_COUNT:
            raise RuntimeError("E104 selected high body count drift")
        if len(selected_modes) != EXPECTED_HIGH_BODY_COUNT:
            raise RuntimeError("E104 selected high mode count drift")
        rows = high_model["rows"]
        high_values = {
            key: int(solver.Value(variable))
            for key, variable in high_model["high_allocation"].items()
        }
        nested_values = {
            (side, key): int(solver.Value(variable))
            for (side, key), variable in high_model["nested_allocation"].items()
        }
        result.update(
            {
                "selected_body_count": len(selected_indices),
                "selected_body_indices": selected_indices,
                "selected_modes": selected_modes,
                "allocation": {
                    f"{key[1]}:{key[2]}:{key[3]}": int(value)
                    for key, value in sorted(high_values.items())
                },
                "allocation_tuple": [
                    int(high_values[key]) for key in high_model["class_keys"]
                ],
                "nested_allocations": {
                    f"{side}:{key[1]}:{key[2]}:{key[3]}": int(value)
                    for (side, key), value in sorted(
                        nested_values.items(), key=lambda item: (item[0][0], item[0][1])
                    )
                },
                "nested_side_body_counts": dict(
                    sorted(
                        Counter(
                            str(rows[index]["nested_side"])
                            for index in selected_indices
                        ).items()
                    )
                ),
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
            }
        )
    return result


def run(
    *,
    run_dir: Path,
    high_seconds: float,
    low_seconds: float,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E104 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e104_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e104_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e104_source_e101")
    prepared = reconstruct(e095=e095, e100=e100)
    audit_path = run_dir / "RESERVED_ROW_AUDIT.json"
    dump_exclusive(audit_path, prepared["audit"])

    high_model = build_high_model(e095=e095, prepared=prepared)
    high = solve_high(high_model, seconds=high_seconds, seed=104100)
    high_path = run_dir / "HIGH_RESULT.json"
    dump_exclusive(high_path, high)

    low: dict[str, Any] | None = None
    final_module_b: dict[str, Any] | None = None
    final_combined: dict[str, Any] | None = None
    low_path = run_dir / "LOW_RESULT.json"
    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"
    high_status = str(high["status"])

    if high_status in {"OPTIMAL", "FEASIBLE"}:
        class_keys = high_model["class_keys"]
        low_allocation = e101.complement_allocation(
            class_keys,
            high_model["global_counts"],
            list(map(int, high["allocation_tuple"])),
        )
        low_model = e101.build_side_model(
            e095=e095,
            restricted=prepared["restricted"],
            side="low",
            template_counts=EXPECTED_LOW_TEMPLATES,
            body_hint_indices=prepared["body_hint_indices"],
            fixed_allocation=low_allocation,
        )
        low = e101.solve_side(low_model, seconds=low_seconds, seed=104200)
        dump_exclusive(low_path, low)
        if low["status"] in {"OPTIMAL", "FEASIBLE"}:
            combined = e101.combine_side_witnesses(
                e095=e095,
                restricted=prepared["restricted"],
                low=low,
                high=high,
            )
            final_module_b = combined["module_b"]
            final_combined = combined["combined"]
            dump_exclusive(module_b_path, final_module_b)
            dump_exclusive(combined_path, final_combined)
            verdict = "RESERVED_Y60_PAIRED_NATIVE_FRONT_WITNESS_FOUND"
            decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
        elif low["status"] == "INFEASIBLE":
            verdict = "RESERVED_Y60_HIGH_ALLOCATION_REJECTED_BY_X42_LOW"
            decision = "ADD_EXACT_HIGH_ALLOCATION_NOGOOD_AND_CONTINUE_HANDSHAKE"
        else:
            verdict = "RESERVED_Y60_LOW_COMPLEMENT_CENSORED"
            decision = "REPLAY_ONLY_THE_PINNED_LOW_COMPLEMENT_WITH_SOLVER_DIVERSITY"
    elif high_status == "INFEASIBLE":
        verdict = "RESERVED_Y60_HIGH_CONSTRUCTOR_INFEASIBLE"
        decision = "RESTORE_E103_EXPLICIT_Y59_SEPARATOR"
    else:
        verdict = "RESERVED_Y60_HIGH_CONSTRUCTOR_CENSORED"
        decision = "EXTERNALIZE_LOWER_UPPER_CLASS_ALLOCATIONS"

    result = {
        "schema": "zmd_e104_high_reserved_y60_constructor_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "reserved_row_y": RESERVED_Y,
            "high_seconds": high_seconds,
            "low_seconds": low_seconds,
            "high_seed": 104100,
            "low_seed": 104200,
            "source_isolated_helpers": True,
            "pure_feasibility": True,
        },
        "reserved_row_audit": {
            "path": display(audit_path),
            "sha256": sha256_file(audit_path),
            **{
                key: prepared["audit"][key]
                for key in (
                    "live_high_candidate_count",
                    "removed_candidate_count",
                    "survivor_candidate_count",
                    "nested_side_candidate_counts",
                    "surviving_hint_count",
                    "removed_hint_count",
                    "cross_body_cell_count",
                    "lower_front_upper_body_intersection_count",
                    "upper_front_lower_body_intersection_count",
                    "cross_front_front_intersection_count",
                )
            },
        },
        "high": {
            "path": display(high_path),
            "sha256": sha256_file(high_path),
            "status": high_status,
            "elapsed_seconds": high["elapsed_seconds"],
            "branches": high["branches"],
            "conflicts": high["conflicts"],
            "selected_body_count": high.get("selected_body_count", 0),
            "allocation": high.get("allocation"),
            "allocation_tuple": high.get("allocation_tuple"),
            "nested_allocations": high.get("nested_allocations"),
            "nested_side_body_counts": high.get("nested_side_body_counts"),
        },
        "low": (
            {
                "path": display(low_path),
                "sha256": sha256_file(low_path),
                "status": low["status"],
                "elapsed_seconds": low["elapsed_seconds"],
                "branches": low["branches"],
                "conflicts": low["conflicts"],
                "selected_body_count": low.get("selected_body_count", 0),
                "allocation": low.get("allocation"),
            }
            if low is not None
            else None
        ),
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
            "A paired positive transfers to the fixed-skeleton module-B parent. "
            "High INFEASIBLE applies only after removing y60 manufacturing bodies; "
            "low INFEASIBLE applies only to one exact high allocation. UNKNOWN is censored."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--high-seconds", type=float, default=120.0)
    parser.add_argument("--low-seconds", type=float, default=120.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            high_seconds=float(args.high_seconds),
            low_seconds=float(args.low_seconds),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "high_status": result["high"]["status"],
                    "low_status": result["low"]["status"] if result["low"] else None,
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
            "schema": "zmd_e104_execution_failure_v1",
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
