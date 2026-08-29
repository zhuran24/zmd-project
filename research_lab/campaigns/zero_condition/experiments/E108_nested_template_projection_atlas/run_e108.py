#!/usr/bin/env python3
"""E108: enumerate body, lower-front, and upper-front template projections."""

from __future__ import annotations

import argparse
from collections import defaultdict
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
    "E108_nested_template_projection_atlas/run-001"
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
E104_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E104_high_reserved_y60_constructor/run_e104.py"
)
E105_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E105_nested_allocation_handshake/run_e105.py"
)
E101_BODY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
)
E107_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E107_reverse_nested_allocation_handshake/run_e107.py"
)
E107_DURABLE = E107_RUNNER.with_name("RESULT.txt")
E107_SNAPSHOT = E107_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E107_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E107_reverse_nested_allocation_handshake/run-001/RESULT.json"
)
E107_CHECK = E107_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    E105_RUNNER: "7dbdf3be073dd77b6ef091b4302442aa5766882d2f384b285576b84c368588b9",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E107_RUNNER: "321e81f1751aa5293522f725643cb84a9249c603040fee98359ae413122166f6",
    E107_DURABLE: "b62ef25a4c503fdce8c8c0186e4871004207322fb6b42224f01e79f1c494298d",
    E107_SNAPSHOT: "2a5dc990fbb7aad8539401b1ae6c0e0977fd7dc1ea2674e99bd3dcde9fd20191",
    E107_RESULT: "ac3669812181c9659bb0e02ea45b291be6985f9ea90e3f849c42cbdd9c30348f",
    E107_CHECK: "9fc472de466d09e4d41d97ae221786fe19a72032294be82a576584c65b927235",
}

TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
TOTALS = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
RAW_VECTOR_COUNT = 11 * 7 * 11
EXPECTED_BODY_COUNT = 26
EXPECTED_SURVIVORS = 1010
EXPECTED_CLASS_COUNT = 8
KNOWN_UPPER_SPLIT_NOGOODS = (
    (3, 2, 2),
    (3, 1, 3),
    (7, 0, 3),
    (6, 1, 2),
    (5, 2, 1),
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
        raise RuntimeError("E108 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E108 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E108 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }
    e107 = load_json(E107_RESULT)
    if e107.get("verdict") != "OPEN_SPLIT_ALLOCATION_FACE_EXHAUSTED_PENDING_REPLAY":
        raise RuntimeError("E108 E107 producer verdict drift")
    check = load_json(E107_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "OPEN_SPLIT_CLOSED_BY_DIRECT_LOWER_INFEASIBILITY"
    ):
        raise RuntimeError("E108 E107 promotion check drift")
    promoted = check.get("promoted_template_split_nogood", {})
    if tuple(map(int, promoted.get("upper", []))) != KNOWN_UPPER_SPLIT_NOGOODS[-1]:
        raise RuntimeError("E108 fifth split identity drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def add_nonoverlap(
    model: cp_model.CpModel,
    rows: Sequence[Mapping[str, Any]],
    variables: Sequence[Any],
) -> dict[tuple[int, int], list[Any]]:
    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(variables[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)
    return by_cell


def add_power_and_stable(
    *,
    model: cp_model.CpModel,
    rows: Sequence[Mapping[str, Any]],
    variables: Sequence[Any],
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    coverage = set(prepared["context"]["fixed_coverage"])
    disabled = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & coverage:
            model.Add(variables[index] == 0)
            disabled += 1
    stable_indices: dict[str, int] = {}
    for instance_id, footprint in prepared["context"]["stable_footprints"].items():
        matches = [
            index for index, row in enumerate(rows) if tuple(row["body"]) == footprint
        ]
        if matches:
            if len(matches) != 1:
                raise RuntimeError(f"E108 stable remap drift: {instance_id}")
            stable_indices[instance_id] = matches[0]
            model.Add(variables[matches[0]] == 1)
    return {
        "disabled_unpowered_candidate_count": disabled,
        "stable_indices": stable_indices,
    }


def add_hints(
    *,
    model: cp_model.CpModel,
    rows: Sequence[Mapping[str, Any]],
    variables: Sequence[Any],
    hint_indices: set[int],
) -> int:
    matched = 0
    for index, row in enumerate(rows):
        hinted = int(row["global_row_index"]) in hint_indices
        model.AddHint(variables[index], int(hinted))
        matched += int(hinted)
    return matched


def build_body_projection(prepared: Mapping[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in prepared["survivors"]]
    if len(rows) != EXPECTED_SURVIVORS:
        raise RuntimeError("E108 body survivor count drift")
    model = cp_model.CpModel()
    variables = [model.NewBoolVar(f"body_projection_{index}") for index in range(len(rows))]
    add_nonoverlap(model, rows, variables)
    support = add_power_and_stable(
        model=model,
        rows=rows,
        variables=variables,
        prepared=prepared,
    )
    for template, required in sorted(TOTALS.items()):
        model.Add(
            sum(
                variables[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
            == int(required)
        )
    count_vars: dict[str, Any] = {}
    for template in TEMPLATES:
        variable = model.NewIntVar(0, int(TOTALS[template]), f"body_upper_{template}")
        count_vars[template] = variable
        model.Add(
            variable
            == sum(
                variables[index]
                for index, row in enumerate(rows)
                if str(row["nested_side"]) == "upper"
                and str(row["template"]) == template
            )
        )
    hints = set(map(int, load_json(E101_BODY)["selected_body_indices"]))
    matched = add_hints(
        model=model,
        rows=rows,
        variables=variables,
        hint_indices=hints,
    )
    if matched != 22:
        raise RuntimeError(f"E108 body hint drift: {matched}")
    error = model.Validate()
    if error:
        raise RuntimeError(f"E108 body projection invalid: {error}")
    return {
        "kind": "body_power",
        "model": model,
        "rows": rows,
        "body_vars": variables,
        "mode_rows": [],
        "count_vars": count_vars,
        "ordered_count_vars": [count_vars[template] for template in TEMPLATES],
        "disabled_unpowered_candidate_count": support[
            "disabled_unpowered_candidate_count"
        ],
        "stable_indices": support["stable_indices"],
        "matched_hint_count": matched,
    }


def build_side_projection(
    *,
    e095: types.ModuleType,
    prepared: Mapping[str, Any],
    nested_side: str,
) -> dict[str, Any]:
    rows = [
        dict(row)
        for row in prepared["survivors"]
        if str(row["nested_side"]) == nested_side
    ]
    model = cp_model.CpModel()
    body_vars = [model.NewBoolVar(f"{nested_side}_projection_body_{index}") for index in range(len(rows))]
    by_cell = add_nonoverlap(model, rows, body_vars)
    support = add_power_and_stable(
        model=model,
        rows=rows,
        variables=body_vars,
        prepared=prepared,
    )

    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(global_counts))
    if len(class_keys) != EXPECTED_CLASS_COUNT:
        raise RuntimeError("E108 side class count drift")
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
                    f"{nested_side}_projection_mc_{body_index}_{pose_index}_{need_in}_{need_out}"
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
            int(global_counts[class_key]),
            f"{nested_side}_projection_alloc_{index}",
        )
        allocation_vars[class_key] = variable
        model.Add(sum(vars_by_class[class_key]) == variable)

    count_vars: dict[str, Any] = {}
    for template in TEMPLATES:
        variable = model.NewIntVar(
            0,
            int(TOTALS[template]),
            f"{nested_side}_projection_count_{template}",
        )
        count_vars[template] = variable
        model.Add(
            variable
            == sum(
                body_vars[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
        )
        model.Add(
            variable
            == sum(
                allocation_vars[key]
                for key in class_keys
                if key[1] == template
            )
        )

    for mode_row in mode_rows:
        variable = mode_row["variable"]
        for field, need in (
            ("input_port_cells", int(mode_row["need_in"])),
            ("output_port_cells", int(mode_row["need_out"])),
        ):
            pose = pools[
                str(rows[int(mode_row["body_index"])]["template"])
            ][int(mode_row["pose_index"])]
            front_cells = tuple(e095.cell(value) for value in pose[field])
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

    hints = set(map(int, load_json(E101_BODY)["selected_body_indices"]))
    matched = add_hints(
        model=model,
        rows=rows,
        variables=body_vars,
        hint_indices=hints,
    )
    error = model.Validate()
    if error:
        raise RuntimeError(f"E108 {nested_side} projection invalid: {error}")
    return {
        "kind": f"{nested_side}_native_front",
        "nested_side": nested_side,
        "model": model,
        "rows": rows,
        "body_vars": body_vars,
        "mode_rows": mode_rows,
        "allocation_vars": allocation_vars,
        "count_vars": count_vars,
        "ordered_count_vars": [count_vars[template] for template in TEMPLATES],
        "class_keys": class_keys,
        "disabled_unpowered_candidate_count": support[
            "disabled_unpowered_candidate_count"
        ],
        "stable_indices": support["stable_indices"],
        "matched_hint_count": matched,
    }


def solver_for(seed: int, seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = int(seed)
    solver.parameters.stop_after_first_solution = True
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    return solver


def extract_witness(
    projection: Mapping[str, Any],
    solver: cp_model.CpSolver,
) -> dict[str, Any]:
    rows = projection["rows"]
    selected_indices = [
        index
        for index, variable in enumerate(projection["body_vars"])
        if solver.Value(variable)
    ]
    witness: dict[str, Any] = {
        "selected_body_count": len(selected_indices),
        "selected_global_indices": [
            int(rows[index]["global_row_index"]) for index in selected_indices
        ],
        "selected_body_digest": stable_digest(
            sorted(str(rows[index]["body_digest"]) for index in selected_indices)
        ),
    }
    if projection["mode_rows"]:
        selected_modes = [
            {
                "global_row_index": int(row["global_row_index"]),
                "body_digest": str(row["body_digest"]),
                "pose_index": int(row["pose_index"]),
                "class_key": list(row["class_key"]),
                "need_in": int(row["need_in"]),
                "need_out": int(row["need_out"]),
            }
            for row in projection["mode_rows"]
            if solver.Value(row["variable"])
        ]
        if len(selected_modes) != len(selected_indices):
            raise RuntimeError("E108 selected mode/body count drift")
        witness["selected_modes"] = selected_modes
        witness["allocation_tuple"] = [
            int(solver.Value(projection["allocation_vars"][key]))
            for key in projection["class_keys"]
        ]
    return witness


def enumerate_projection(
    *,
    projection: Mapping[str, Any],
    stage_seconds: float,
    per_solve_seconds: float,
    max_vectors: int,
    seed_base: int,
) -> dict[str, Any]:
    model = projection["model"]
    started = time.monotonic()
    before = process_snapshot()
    records: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int]] = set()
    terminal = "VECTOR_LIMIT"
    terminal_status = "NOT_RUN"
    terminal_solve_seconds = 0.0
    terminal_branches = 0
    terminal_conflicts = 0

    for iteration in range(max_vectors + 1):
        elapsed = time.monotonic() - started
        remaining = float(stage_seconds) - elapsed
        if remaining <= 0:
            terminal = "STAGE_BUDGET_EXHAUSTED"
            terminal_status = "NOT_RUN"
            break
        solver = solver_for(
            seed=seed_base + iteration,
            seconds=min(float(per_solve_seconds), remaining),
        )
        solve_started = time.monotonic()
        status_code = solver.Solve(model)
        solve_elapsed = time.monotonic() - solve_started
        status = solver.StatusName(status_code)
        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if len(records) >= max_vectors:
                terminal = "VECTOR_LIMIT"
                terminal_status = status
                terminal_solve_seconds = solve_elapsed
                terminal_branches = int(solver.NumBranches())
                terminal_conflicts = int(solver.NumConflicts())
                break
            vector = tuple(
                int(solver.Value(projection["count_vars"][template]))
                for template in TEMPLATES
            )
            if vector in seen:
                raise RuntimeError(f"E108 duplicate projection vector: {vector}")
            if any(
                value < 0 or value > int(TOTALS[TEMPLATES[index]])
                for index, value in enumerate(vector)
            ):
                raise RuntimeError(f"E108 projection vector out of bounds: {vector}")
            seen.add(vector)
            records.append(
                {
                    "iteration": iteration,
                    "vector": list(vector),
                    "status": status,
                    "elapsed_seconds": solve_elapsed,
                    "branches": int(solver.NumBranches()),
                    "conflicts": int(solver.NumConflicts()),
                    "witness": extract_witness(projection, solver),
                }
            )
            model.AddForbiddenAssignments(
                projection["ordered_count_vars"],
                [list(vector)],
            )
            continue
        terminal_status = status
        terminal_solve_seconds = solve_elapsed
        terminal_branches = int(solver.NumBranches())
        terminal_conflicts = int(solver.NumConflicts())
        if status == "INFEASIBLE":
            terminal = "COMPLETE"
        else:
            terminal = "CENSORED"
        break

    after = process_snapshot()
    total_elapsed = time.monotonic() - started
    return {
        "schema": "zmd_e108_projection_enumeration_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "kind": projection["kind"],
        "status": terminal,
        "complete": terminal == "COMPLETE",
        "vector_count": len(records),
        "vectors": records,
        "vector_digest": stable_digest(sorted(tuple(row["vector"]) for row in records)),
        "terminal_status": terminal_status,
        "terminal_solve_seconds": terminal_solve_seconds,
        "terminal_branches": terminal_branches,
        "terminal_conflicts": terminal_conflicts,
        "total_elapsed_seconds": total_elapsed,
        "stage_seconds": stage_seconds,
        "per_solve_seconds": per_solve_seconds,
        "max_vectors": max_vectors,
        "candidate_count": len(projection["rows"]),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "disabled_unpowered_candidate_count": projection[
            "disabled_unpowered_candidate_count"
        ],
        "matched_hint_count": projection["matched_hint_count"],
        "stable_body_count": len(projection["stable_indices"]),
        "process_before": before,
        "process_after": after,
        "truth_boundary": (
            "Distinct three-template count projection. Complete only when the "
            "post-blocking model returns exact INFEASIBLE."
        ),
    }


def vector_set(payload: Mapping[str, Any]) -> set[tuple[int, int, int]]:
    return {tuple(map(int, row["vector"])) for row in payload["vectors"]}


def complement(vector: Sequence[int]) -> tuple[int, int, int]:
    if len(vector) != len(TEMPLATES):
        raise RuntimeError("E108 complement width drift")
    return tuple(
        int(TOTALS[template]) - int(vector[index])
        for index, template in enumerate(TEMPLATES)
    )


def run(
    *,
    run_dir: Path,
    body_seconds: float,
    upper_seconds: float,
    lower_seconds: float,
    per_solve_seconds: float,
    max_vectors: int,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E108 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e108_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e108_source_e100")
    e104 = source_module(E104_RUNNER, "zmd_e108_source_e104")
    prepared = e104.reconstruct(e095=e095, e100=e100)

    body_model = build_body_projection(prepared)
    body = enumerate_projection(
        projection=body_model,
        stage_seconds=body_seconds,
        per_solve_seconds=per_solve_seconds,
        max_vectors=max_vectors,
        seed_base=108100,
    )
    body_path = run_dir / "BODY_TEMPLATE_PROJECTION.json"
    dump_exclusive(body_path, body)

    upper_model = build_side_projection(
        e095=e095,
        prepared=prepared,
        nested_side="upper",
    )
    upper = enumerate_projection(
        projection=upper_model,
        stage_seconds=upper_seconds,
        per_solve_seconds=per_solve_seconds,
        max_vectors=max_vectors,
        seed_base=108300,
    )
    upper_path = run_dir / "UPPER_FRONT_TEMPLATE_PROJECTION.json"
    dump_exclusive(upper_path, upper)

    lower_model = build_side_projection(
        e095=e095,
        prepared=prepared,
        nested_side="lower",
    )
    lower = enumerate_projection(
        projection=lower_model,
        stage_seconds=lower_seconds,
        per_solve_seconds=per_solve_seconds,
        max_vectors=max_vectors,
        seed_base=108500,
    )
    lower_path = run_dir / "LOWER_FRONT_TEMPLATE_PROJECTION.json"
    dump_exclusive(lower_path, lower)

    all_complete = bool(body["complete"] and upper["complete"] and lower["complete"])
    body_vectors = vector_set(body)
    upper_vectors = vector_set(upper)
    lower_complement_vectors = {complement(vector) for vector in vector_set(lower)}
    survivors = sorted(body_vectors & upper_vectors & lower_complement_vectors)
    known_status = {
        "/".join(map(str, vector)): {
            "body_feasible": vector in body_vectors,
            "upper_front_feasible": vector in upper_vectors,
            "lower_complement_front_feasible": vector in lower_complement_vectors,
        }
        for vector in KNOWN_UPPER_SPLIT_NOGOODS
    }
    if upper["complete"]:
        for vector in KNOWN_UPPER_SPLIT_NOGOODS[:4]:
            if vector in upper_vectors:
                raise RuntimeError(
                    f"E108 known upper-side split nogood reappeared: {vector}"
                )
    if lower["complete"] and KNOWN_UPPER_SPLIT_NOGOODS[-1] in lower_complement_vectors:
        raise RuntimeError("E108 E107 lower-projection nogood reappeared")

    intersection_path = run_dir / "TEMPLATE_PROJECTION_INTERSECTION.json"
    intersection = {
        "schema": "zmd_e108_template_projection_intersection_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "complete": all_complete,
        "raw_vector_count": RAW_VECTOR_COUNT,
        "body_projection_count": len(body_vectors),
        "upper_front_projection_count": len(upper_vectors),
        "lower_front_projection_count": len(vector_set(lower)),
        "lower_complement_projection_count": len(lower_complement_vectors),
        "survivor_count": len(survivors),
        "survivor_upper_vectors": [list(vector) for vector in survivors],
        "survivor_digest": stable_digest(survivors),
        "known_split_nogood_membership": known_status,
        "truth_boundary": (
            "Exact survivor atlas only if all three projections are complete. "
            "Template-level survival does not prove class-allocation compatibility."
        ),
    }
    dump_exclusive(intersection_path, intersection)

    if all_complete and not survivors:
        verdict = "RESERVED_Y60_TEMPLATE_PROJECTION_EMPTY"
        decision = "RESTORE_E103_EXPLICIT_Y59_SEPARATOR"
    elif all_complete:
        verdict = "FINITE_TEMPLATE_PROJECTION_SURVIVORS_FOUND"
        decision = "RUN_ALLOCATION_HANDSHAKE_ONLY_ON_SURVIVING_SPLITS"
    else:
        verdict = "TEMPLATE_PROJECTION_ATLAS_CENSORED"
        decision = "CONTINUE_ONLY_INCOMPLETE_PROJECTION_ENUMERATIONS"

    result = {
        "schema": "zmd_e108_nested_template_projection_atlas_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "raw_vector_count": RAW_VECTOR_COUNT,
            "max_vectors_per_projection": max_vectors,
            "per_solve_seconds": per_solve_seconds,
            "body_stage_seconds": body_seconds,
            "upper_stage_seconds": upper_seconds,
            "lower_stage_seconds": lower_seconds,
            "source_isolated_helpers": True,
        },
        "projections": {
            "body": {
                "path": display(body_path),
                "sha256": sha256_file(body_path),
                "status": body["status"],
                "complete": body["complete"],
                "vector_count": body["vector_count"],
                "total_elapsed_seconds": body["total_elapsed_seconds"],
                "terminal_status": body["terminal_status"],
            },
            "upper": {
                "path": display(upper_path),
                "sha256": sha256_file(upper_path),
                "status": upper["status"],
                "complete": upper["complete"],
                "vector_count": upper["vector_count"],
                "total_elapsed_seconds": upper["total_elapsed_seconds"],
                "terminal_status": upper["terminal_status"],
            },
            "lower": {
                "path": display(lower_path),
                "sha256": sha256_file(lower_path),
                "status": lower["status"],
                "complete": lower["complete"],
                "vector_count": lower["vector_count"],
                "total_elapsed_seconds": lower["total_elapsed_seconds"],
                "terminal_status": lower["terminal_status"],
            },
        },
        "intersection": {
            "path": display(intersection_path),
            "sha256": sha256_file(intersection_path),
            "complete": all_complete,
            "survivor_count": len(survivors),
            "survivor_upper_vectors": [list(vector) for vector in survivors],
            "survivor_digest": stable_digest(survivors),
        },
        "truth_boundary": (
            "Body/power and side native-front template projections only. Even a "
            "complete nonempty intersection requires a separate class-allocation "
            "handshake. Partial projections authorize no absence claim."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--body-seconds", type=float, default=45.0)
    parser.add_argument("--upper-seconds", type=float, default=90.0)
    parser.add_argument("--lower-seconds", type=float, default=120.0)
    parser.add_argument("--per-solve-seconds", type=float, default=12.0)
    parser.add_argument("--max-vectors", type=int, default=RAW_VECTOR_COUNT)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            body_seconds=float(args.body_seconds),
            upper_seconds=float(args.upper_seconds),
            lower_seconds=float(args.lower_seconds),
            per_solve_seconds=float(args.per_solve_seconds),
            max_vectors=int(args.max_vectors),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "body": result["projections"]["body"],
                    "upper": result["projections"]["upper"],
                    "lower": result["projections"]["lower"],
                    "intersection": result["intersection"],
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
            "schema": "zmd_e108_execution_failure_v1",
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
