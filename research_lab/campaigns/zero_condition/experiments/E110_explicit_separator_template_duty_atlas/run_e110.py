#!/usr/bin/env python3
"""E110: exact body/power projection of E103 separator template duties."""

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
    "E110_explicit_separator_template_duty_atlas/run-001"
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
E101_BODY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
)
E103_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E103_high_side_interface_capacity_audit/run_e103.py"
)
E103_DURABLE = E103_RUNNER.with_name("RESULT.txt")
E103_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E103_high_side_interface_capacity_audit/run-003/RESULT.json"
)
E103_CHECK = E103_RESULT.with_name("ARTIFACT_CHECK.json")
E103_LIVE = E103_RESULT.with_name("LIVE_HIGH_CANDIDATES.json")
E109_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E109_last_two_template_split_discriminator/run_e109.py"
)
E109_DURABLE = E109_RUNNER.with_name("RESULT.txt")
E109_SNAPSHOT = E109_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E109_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E109_last_two_template_split_discriminator/run-001/RESULT.json"
)
E109_CHECK = E109_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E103_RUNNER: "3185bc717e8c0438a47148972476d6176fee8643e23bcb7167a6b54f4be99f48",
    E103_DURABLE: "cee44b989deeea94355d31a69b41510dbe1a74531ec993da5ed9254f9694de6b",
    E103_RESULT: "6fefd59e3b8c5551501a2504e9c620bb6cc5468ac5847b92baa20a8ec6e6a32c",
    E103_CHECK: "63ba0d4085263d12c153db0f639bfd984f9bfd373de0b9828eeaf6e94f98850d",
    E103_LIVE: "ebf0c34b174df7036cf6c4bf2f3283dd4ea303998f62520cbd0c74d70aebfd08",
    E109_RUNNER: "a8e6ec35332db5ea7fa789f9f04a4081a8ed98d000d41620e0ea039c4d174889",
    E109_DURABLE: "cc815e7d63d2546b446ae122d43f2a1d9c85474941f64d864328950de2b2745f",
    E109_SNAPSHOT: "7ee5ae3d5a4fdffb2dc7b1d7920c05f5e64567267c0fbc26a5a5c93551f8370d",
    E109_RESULT: "32a76ec37e5a51158fc19aabfd02da606e0337d8903a677f6a064ac25bb69875",
    E109_CHECK: "a065ff1730e445bea7ae6825413b27a7bee641b63c4f20c084050229a9a511a0",
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
EXPECTED_LIVE = 1205
EXPECTED_GROUP_COUNTS = {"low": 812, "separator": 154, "high": 239}
EXPECTED_BODY_COUNT = 26
EXPECTED_HINTS = 25
RAW_SEPARATOR_VECTOR_COUNT = 11 * 7 * 11


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
        raise RuntimeError("E110 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E110 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E110 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    e103 = load_json(E103_RESULT)
    if e103.get("verdict") != "HIGH_SIDE_SPATIAL_TEMPLATE_HYBRID_SELECTED":
        raise RuntimeError("E110 E103 verdict drift")
    selected = e103.get("selected_spatial_cut", {})
    if selected.get("cut_id") != "y_after_59":
        raise RuntimeError("E110 E103 selected cut drift")
    if selected.get("group_candidate_counts") != EXPECTED_GROUP_COUNTS:
        raise RuntimeError("E110 E103 group-count drift")
    if load_json(E103_CHECK).get("status") != "PASS":
        raise RuntimeError("E110 E103 check is not PASS")

    e109 = load_json(E109_RESULT)
    if e109.get("verdict") != "RESERVED_Y60_TEMPLATE_PROJECTION_CLOSED":
        raise RuntimeError("E110 E109 verdict drift")
    if e109.get("decision") != "RESTORE_E103_EXPLICIT_Y59_SEPARATOR":
        raise RuntimeError("E110 E109 decision drift")
    check = load_json(E109_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "SEVEN_STATE_BODY_ATLAS_FULLY_COVERED_BY_EXACT_SPLIT_NOGOODS"
    ):
        raise RuntimeError("E110 E109 check drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def restore_three_groups(
    *,
    e095: types.ModuleType,
    e100: types.ModuleType,
) -> dict[str, Any]:
    restricted = e100.build_restricted_context(e095)
    rows = [dict(row) for row in restricted["rows"]]
    live_payload = load_json(E103_LIVE)
    records = list(live_payload["candidates"])
    if int(live_payload.get("candidate_count", -1)) != EXPECTED_LIVE:
        raise RuntimeError("E110 live candidate count drift")

    live_rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for record in records:
        global_index = int(record["global_row_index"])
        if global_index in seen:
            raise RuntimeError(f"E110 duplicate global row: {global_index}")
        seen.add(global_index)
        if not 0 <= global_index < len(rows):
            raise RuntimeError(f"E110 global row out of range: {global_index}")
        source = rows[global_index]
        if str(source["side"]) != "high":
            raise RuntimeError(f"E110 live row not x42-high: {global_index}")
        body = tuple(tuple(map(int, value)) for value in record["body"])
        if tuple(source["body"]) != body:
            raise RuntimeError(f"E110 body transport drift: {global_index}")
        if str(source["body_digest"]) != str(record["body_digest"]):
            raise RuntimeError(f"E110 body digest drift: {global_index}")
        if str(source["template"]) != str(record["template"]):
            raise RuntimeError(f"E110 template drift: {global_index}")
        if record.get("fixed_powered") is not True or record.get("static_mode_live") is not True:
            raise RuntimeError(f"E110 non-live record entered atlas: {global_index}")
        bbox = record["bbox"]
        if int(bbox["max_y"]) <= 59:
            group = "low"
        elif int(bbox["min_y"]) > 59:
            group = "high"
        else:
            group = "separator"
        live_rows.append(
            {
                **source,
                "global_row_index": global_index,
                "separator_group": group,
                "e103_is_anchor": bool(record["is_anchor"]),
            }
        )

    counts = Counter(str(row["separator_group"]) for row in live_rows)
    if dict(counts) != EXPECTED_GROUP_COUNTS:
        raise RuntimeError(f"E110 restored group-count drift: {counts}")
    anchor_counts = Counter(
        str(row["separator_group"])
        for row in live_rows
        if bool(row["e103_is_anchor"])
    )
    if dict(anchor_counts) != {"low": 19, "separator": 1, "high": 5}:
        raise RuntimeError(f"E110 live anchor group drift: {anchor_counts}")
    return {
        "restricted": restricted,
        "context": restricted["base"],
        "rows": live_rows,
        "group_counts": dict(sorted(counts.items())),
        "anchor_group_counts": dict(sorted(anchor_counts.items())),
    }


def build_model(prepared: Mapping[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in prepared["rows"]]
    model = cp_model.CpModel()
    variables = [model.NewBoolVar(f"separator_body_{index}") for index in range(len(rows))]
    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(variables[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    for template, required in sorted(TOTALS.items()):
        model.Add(
            sum(
                variables[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
            == int(required)
        )

    coverage = set(prepared["context"]["fixed_coverage"])
    disabled = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & coverage:
            model.Add(variables[index] == 0)
            disabled += 1
    if disabled != 0:
        raise RuntimeError(f"E110 unary-live power drift: {disabled}")

    stable_indices: dict[str, int] = {}
    for instance_id, footprint in prepared["context"]["stable_footprints"].items():
        matches = [
            index for index, row in enumerate(rows) if tuple(row["body"]) == footprint
        ]
        if len(matches) != 1:
            raise RuntimeError(f"E110 stable remap drift: {instance_id}")
        stable_indices[instance_id] = matches[0]
        model.Add(variables[matches[0]] == 1)

    body_hint_indices = set(map(int, load_json(E101_BODY)["selected_body_indices"]))
    matched_hints = 0
    for index, row in enumerate(rows):
        hinted = int(row["global_row_index"]) in body_hint_indices
        model.AddHint(variables[index], int(hinted))
        matched_hints += int(hinted)
    if matched_hints != EXPECTED_HINTS:
        raise RuntimeError(f"E110 hint count drift: {matched_hints}")

    separator_count_vars: dict[str, Any] = {}
    for template in TEMPLATES:
        variable = model.NewIntVar(
            0,
            int(TOTALS[template]),
            f"separator_count_{template}",
        )
        separator_count_vars[template] = variable
        model.Add(
            variable
            == sum(
                variables[index]
                for index, row in enumerate(rows)
                if str(row["separator_group"]) == "separator"
                and str(row["template"]) == template
            )
        )

    error = model.Validate()
    if error:
        raise RuntimeError(f"E110 model invalid: {error}")
    return {
        "model": model,
        "rows": rows,
        "variables": variables,
        "separator_count_vars": separator_count_vars,
        "ordered_separator_vars": [
            separator_count_vars[template] for template in TEMPLATES
        ],
        "stable_indices": stable_indices,
        "matched_hint_count": matched_hints,
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


def enumerate_vectors(
    *,
    body_model: Mapping[str, Any],
    stage_seconds: float,
    per_solve_seconds: float,
    max_vectors: int,
) -> dict[str, Any]:
    model = body_model["model"]
    rows = body_model["rows"]
    started = time.monotonic()
    before = process_snapshot()
    vectors: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int]] = set()
    terminal = "VECTOR_LIMIT"
    terminal_status = "NOT_RUN"
    terminal_elapsed = 0.0
    terminal_branches = 0
    terminal_conflicts = 0

    for iteration in range(max_vectors + 1):
        remaining = float(stage_seconds) - (time.monotonic() - started)
        if remaining <= 0:
            terminal = "STAGE_BUDGET_EXHAUSTED"
            terminal_status = "NOT_RUN"
            break
        solver = solver_for(
            seed=110100 + iteration,
            seconds=min(float(per_solve_seconds), remaining),
        )
        solve_started = time.monotonic()
        status_code = solver.Solve(model)
        solve_elapsed = time.monotonic() - solve_started
        status = solver.StatusName(status_code)
        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if len(vectors) >= max_vectors:
                terminal = "VECTOR_LIMIT"
                terminal_status = status
                terminal_elapsed = solve_elapsed
                terminal_branches = int(solver.NumBranches())
                terminal_conflicts = int(solver.NumConflicts())
                break
            vector = tuple(
                int(solver.Value(body_model["separator_count_vars"][template]))
                for template in TEMPLATES
            )
            if vector in seen:
                raise RuntimeError(f"E110 duplicate separator vector: {vector}")
            seen.add(vector)
            selected = [
                index
                for index, variable in enumerate(body_model["variables"])
                if solver.Value(variable)
            ]
            if len(selected) != EXPECTED_BODY_COUNT:
                raise RuntimeError("E110 selected body count drift")
            group_templates = Counter(
                (
                    str(rows[index]["separator_group"]),
                    str(rows[index]["template"]),
                )
                for index in selected
            )
            observed_separator = tuple(
                int(group_templates[("separator", template)])
                for template in TEMPLATES
            )
            if observed_separator != vector:
                raise RuntimeError("E110 separator vector replay drift")
            vectors.append(
                {
                    "iteration": iteration,
                    "vector": list(vector),
                    "separator_body_count": sum(vector),
                    "status": status,
                    "elapsed_seconds": solve_elapsed,
                    "branches": int(solver.NumBranches()),
                    "conflicts": int(solver.NumConflicts()),
                    "witness": {
                        "selected_body_count": len(selected),
                        "selected_global_indices": [
                            int(rows[index]["global_row_index"]) for index in selected
                        ],
                        "selected_body_digest": stable_digest(
                            sorted(str(rows[index]["body_digest"]) for index in selected)
                        ),
                        "group_template_counts": {
                            f"{group}:{template}": int(count)
                            for (group, template), count in sorted(group_templates.items())
                        },
                    },
                }
            )
            model.AddForbiddenAssignments(
                body_model["ordered_separator_vars"],
                [list(vector)],
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
        "schema": "zmd_e110_separator_template_projection_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": terminal,
        "complete": terminal == "COMPLETE",
        "vector_count": len(vectors),
        "vectors": vectors,
        "vector_digest": stable_digest(sorted(tuple(row["vector"]) for row in vectors)),
        "terminal_status": terminal_status,
        "terminal_elapsed_seconds": terminal_elapsed,
        "terminal_branches": terminal_branches,
        "terminal_conflicts": terminal_conflicts,
        "total_elapsed_seconds": time.monotonic() - started,
        "stage_seconds": stage_seconds,
        "per_solve_seconds": per_solve_seconds,
        "max_vectors": max_vectors,
        "candidate_count": len(rows),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "matched_hint_count": body_model["matched_hint_count"],
        "stable_body_count": len(body_model["stable_indices"]),
        "process_before": before,
        "process_after": after,
        "truth_boundary": (
            "Exact separator template-count projection only if post-blocking "
            "model returns INFEASIBLE. Stored side template counts are witnesses, "
            "not unique duties for their separator vector."
        ),
    }


def derive_summary(projection: Mapping[str, Any]) -> dict[str, Any]:
    vectors = [tuple(map(int, row["vector"])) for row in projection["vectors"]]
    if not vectors:
        return {
            "separator_body_count_min": None,
            "separator_body_count_max": None,
            "per_template_min": {},
            "per_template_max": {},
            "body_count_distribution": {},
            "zero_separator_vector_present": False,
        }
    return {
        "separator_body_count_min": min(sum(vector) for vector in vectors),
        "separator_body_count_max": max(sum(vector) for vector in vectors),
        "per_template_min": {
            template: min(vector[index] for vector in vectors)
            for index, template in enumerate(TEMPLATES)
        },
        "per_template_max": {
            template: max(vector[index] for vector in vectors)
            for index, template in enumerate(TEMPLATES)
        },
        "body_count_distribution": {
            str(count): sum(sum(vector) == count for vector in vectors)
            for count in sorted({sum(vector) for vector in vectors})
        },
        "zero_separator_vector_present": (0, 0, 0) in set(vectors),
    }


def run(
    *,
    run_dir: Path,
    stage_seconds: float,
    per_solve_seconds: float,
    max_vectors: int,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E110 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e110_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e110_source_e100")
    prepared = restore_three_groups(e095=e095, e100=e100)
    body_model = build_model(prepared)
    projection = enumerate_vectors(
        body_model=body_model,
        stage_seconds=stage_seconds,
        per_solve_seconds=per_solve_seconds,
        max_vectors=max_vectors,
    )
    projection_path = run_dir / "SEPARATOR_TEMPLATE_PROJECTION.json"
    dump_exclusive(projection_path, projection)
    summary = derive_summary(projection)

    if projection["complete"] and projection["vector_count"] > 0:
        verdict = "EXPLICIT_SEPARATOR_TEMPLATE_DUTY_ATLAS_COMPLETE"
        decision = "ATTACH_CLASS_COORDINATES_TO_SEPARATOR_VECTORS"
    elif projection["complete"]:
        verdict = "EXPLICIT_SEPARATOR_BODY_PROJECTION_EMPTY_APPARATUS_CONTRADICTION"
        decision = "AUDIT_SEPARATOR_RECONSTRUCTION"
    else:
        verdict = "EXPLICIT_SEPARATOR_TEMPLATE_DUTY_ATLAS_CENSORED"
        decision = "CONTINUE_SEPARATOR_VECTOR_ENUMERATION"

    result = {
        "schema": "zmd_e110_explicit_separator_template_duty_atlas_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "raw_separator_vector_count": RAW_SEPARATOR_VECTOR_COUNT,
            "stage_seconds": stage_seconds,
            "per_solve_seconds": per_solve_seconds,
            "max_vectors": max_vectors,
            "source_isolated_helpers": True,
        },
        "restored_language": {
            "candidate_count": len(prepared["rows"]),
            "group_candidate_counts": prepared["group_counts"],
            "anchor_group_counts": prepared["anchor_group_counts"],
        },
        "projection": {
            "path": display(projection_path),
            "sha256": sha256_file(projection_path),
            "status": projection["status"],
            "complete": projection["complete"],
            "vector_count": projection["vector_count"],
            "vector_digest": projection["vector_digest"],
            "total_elapsed_seconds": projection["total_elapsed_seconds"],
            "terminal_status": projection["terminal_status"],
        },
        "summary": summary,
        "truth_boundary": (
            "Body/power-only separator template projection. A positive vector "
            "requires a separate low/separator/high native-front and class handshake."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--stage-seconds", type=float, default=90.0)
    parser.add_argument("--per-solve-seconds", type=float, default=3.0)
    parser.add_argument("--max-vectors", type=int, default=RAW_SEPARATOR_VECTOR_COUNT)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            stage_seconds=float(args.stage_seconds),
            per_solve_seconds=float(args.per_solve_seconds),
            max_vectors=int(args.max_vectors),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "projection": result["projection"],
                    "summary": result["summary"],
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
            "schema": "zmd_e110_execution_failure_v1",
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
