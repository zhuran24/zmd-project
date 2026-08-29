#!/usr/bin/env python3
"""E114: send E110's 27 fixed high-side geometries to the real front consumer."""

from __future__ import annotations

import argparse
from collections import Counter
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
from typing import Any, Callable, Mapping

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E114_e110_fixed_geometry_direct_consumer/run-001"
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
E100_CHECK = E100_RESULT.with_name("ARTIFACT_CHECK.json")
E101_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E101_x42_allocation_handshake/run_e101.py"
)
E101_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E101_x42_allocation_handshake/run-001/RESULT.json"
)
E101_BODY = E101_RESULT.with_name("BODY_ONLY_RESULT.json")
E101_CHECK = E101_RESULT.with_name("ARTIFACT_CHECK.json")
E110_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E110_explicit_separator_template_duty_atlas/RESULT.txt"
)
E110_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E110_explicit_separator_template_duty_atlas/run-001"
)
E110_RESULT = E110_RUN / "RESULT.json"
E110_PROJECTION = E110_RUN / "SEPARATOR_TEMPLATE_PROJECTION.json"
E110_CHECK = E110_RUN / "ARTIFACT_CHECK.json"
E113_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E113_separator_side_interaction_compiler/RESULT.txt"
)
E113_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E113_separator_side_interaction_compiler/run-001/RESULT.json"
)
E113_CHECK = E113_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E100_RESULT: "d4de0239604cf4713164069fda553965275566c1840238ec4fa98446ba71b12c",
    E100_CHECK: "b2cc7e2aef54f5e0209a96b124319fa68b834bd0556db1d162732ac123fc5fc4",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_RESULT: "b6b088f214fcbb3be01b26180ce9d211b647ede4038e7542531077548bfd9e9d",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E101_CHECK: "35eb5580acf84a9b25e7569403ac5aa5814285fa29dd225c9bd5e9bd28eb0055",
    E110_DURABLE: "6f85129b3e621bc97c36ade2ae1fe3872ed8e2a565d4fcacdb9823862d3c49f0",
    E110_RESULT: "6b454d85725ac91ffdb7478231fb6b0900d077c701d1a2c81c6d75acff889664",
    E110_PROJECTION: "73570c931c8e8c053ec5a17feaa821e4e69511443882eac01110b470a6537413",
    E110_CHECK: "4b25595170b280f34951f563e61c5a17de46e1cc6b6afbfa97ee7e9421b17bf6",
    E113_DURABLE: "c4de948ed81d6c5a8125a1b4f416250d17a664cf4d1649be21f92388cc65d1f2",
    E113_RESULT: "511d5592142dcdce1832eca99e9d000ab439c2fee28d58b0f103aba96fb0108c",
    E113_CHECK: "07f220365a6a825b73cbf69423d847315b73fef66c5e7d36ecfe3b98c01e874f",
}

HIGH_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
LOW_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 43,
    "manufacturing_5x5": 11,
    "manufacturing_6x4": 11,
}
EXPECTED_GEOMETRY_COUNT = 27
EXPECTED_HIGH_BODY_COUNT = 26
EXPECTED_LOW_BODY_COUNT = 65
EXPECTED_CLASS_COUNT = 8


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
        raise RuntimeError("E114 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E114 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E114 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    if load_json(E100_CHECK).get("status") != "PASS":
        raise RuntimeError("E114 E100 check is not PASS")
    if load_json(E101_CHECK).get("status") != "PASS":
        raise RuntimeError("E114 E101 check is not PASS")
    body = load_json(E101_BODY)
    if body.get("status") != "OPTIMAL" or int(body.get("selected_body_count", -1)) != 91:
        raise RuntimeError("E114 E101 body witness drift")
    module_a = load_json(E095_MODULE_A)
    if module_a.get("status") != "OPTIMAL" or int(module_a.get("selected_body_count", -1)) != 128:
        raise RuntimeError("E114 frozen module-A witness drift")

    e110 = load_json(E110_RESULT)
    projection = load_json(E110_PROJECTION)
    if e110.get("verdict") != "EXPLICIT_SEPARATOR_TEMPLATE_DUTY_ATLAS_COMPLETE":
        raise RuntimeError("E114 E110 verdict drift")
    if projection.get("complete") is not True or int(projection.get("vector_count", -1)) != EXPECTED_GEOMETRY_COUNT:
        raise RuntimeError("E114 E110 projection drift")
    if load_json(E110_CHECK).get("status") != "PASS":
        raise RuntimeError("E114 E110 check is not PASS")

    e113 = load_json(E113_RESULT)
    if e113.get("verdict") != "LOW_VS_SEPARATOR_HIGH_CAP_INTERFACE_SELECTED":
        raise RuntimeError("E114 E113 verdict drift")
    if load_json(E113_CHECK).get("status") != "PASS":
        raise RuntimeError("E114 E113 check is not PASS")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def class_counts(context: Mapping[str, Any]) -> tuple[
    tuple[tuple[str, str, int, int], ...],
    dict[tuple[str, str, int, int], int],
]:
    counts = {
        key: int(value)
        for key, value in context["class_counts"].items()
        if key[0] == "B"
    }
    keys = tuple(sorted(counts))
    if len(keys) != EXPECTED_CLASS_COUNT:
        raise RuntimeError("E114 class dimension drift")
    return keys, counts


def validate_geometry(
    *,
    record: Mapping[str, Any],
    restricted: Mapping[str, Any],
) -> dict[str, Any]:
    rows = [dict(row) for row in restricted["rows"]]
    witness = record["witness"]
    selected_indices = list(map(int, witness["selected_global_indices"]))
    if len(selected_indices) != len(set(selected_indices)):
        raise RuntimeError("E114 geometry index identity drift")
    if len(selected_indices) != EXPECTED_HIGH_BODY_COUNT:
        raise RuntimeError("E114 geometry body count drift")
    selected: list[dict[str, Any]] = []
    for index in selected_indices:
        if not 0 <= index < len(rows):
            raise RuntimeError(f"E114 geometry row out of range: {index}")
        row = rows[index]
        if str(row["side"]) != "high":
            raise RuntimeError(f"E114 geometry row is not x42-high: {index}")
        selected.append(row)

    template_counts = Counter(str(row["template"]) for row in selected)
    if template_counts != Counter(HIGH_TEMPLATE_COUNTS):
        raise RuntimeError(f"E114 geometry template drift: {template_counts}")
    digest = stable_digest(sorted(str(row["body_digest"]) for row in selected))
    if digest != str(witness["selected_body_digest"]):
        raise RuntimeError("E114 E110 body digest drift")

    occupied = set(restricted["base"]["fixed_solid"])
    for row in selected:
        body = set(row["body"])
        if occupied & body:
            raise RuntimeError("E114 E110 geometry overlap drift")
        occupied |= body
    coverage = set(restricted["base"]["fixed_coverage"])
    if any(not set(row["body"]) & coverage for row in selected):
        raise RuntimeError("E114 E110 geometry power drift")
    for instance_id, footprint in restricted["base"]["stable_footprints"].items():
        matches = [row for row in selected if tuple(row["body"]) == footprint]
        if len(matches) != 1:
            raise RuntimeError(f"E114 stable body drift: {instance_id}")

    return {
        "iteration": int(record["iteration"]),
        "separator_template_vector": list(map(int, record["vector"])),
        "separator_body_count": int(record["separator_body_count"]),
        "selected_global_indices": selected_indices,
        "selected_body_digest": digest,
        "group_template_counts": dict(witness["group_template_counts"]),
        "selected_body_count": len(selected_indices),
    }


def fix_geometry(
    *,
    e095: types.ModuleType,
    e101: types.ModuleType,
    restricted: Mapping[str, Any],
    selected_indices: set[int],
) -> dict[str, Any]:
    bundle = e101.build_side_model(
        e095=e095,
        restricted=restricted,
        side="high",
        template_counts=HIGH_TEMPLATE_COUNTS,
        body_hint_indices=set(selected_indices),
        fixed_allocation=None,
    )
    rows = bundle["rows"]
    observed = {
        int(row["global_row_index"])
        for row in rows
        if int(row["global_row_index"]) in selected_indices
    }
    if observed != selected_indices:
        raise RuntimeError("E114 fixed geometry remap drift")
    for local_index, row in enumerate(rows):
        bundle["model"].Add(
            bundle["body_vars"][local_index]
            == int(int(row["global_row_index"]) in selected_indices)
        )
    error = bundle["model"].Validate()
    if error:
        raise RuntimeError(f"E114 fixed high model invalid: {error}")
    bundle["fixed_selected_global_indices"] = sorted(selected_indices)
    return bundle


def solver_for(*, profile: str, seconds: float, seed: int) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.random_seed = int(seed)
    solver.parameters.stop_after_first_solution = True
    if profile == "one_worker_pseudo_cost":
        solver.parameters.num_search_workers = 1
        solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
        solver.parameters.symmetry_level = 0
        solver.parameters.cp_model_probing_level = 0
        solver.parameters.randomize_search = False
    elif profile == "multiworker_automatic":
        solver.parameters.num_search_workers = 8
        solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
        solver.parameters.symmetry_level = 3
        solver.parameters.cp_model_probing_level = 3
        solver.parameters.randomize_search = True
    else:
        raise RuntimeError(f"E114 unknown solver profile: {profile}")
    return solver


def replay_side_positive(
    *,
    e095: types.ModuleType,
    bundle: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    rows = bundle["rows"]
    context = bundle["context"] if "context" in bundle else None
    if context is None:
        raise RuntimeError("E114 replay bundle lacks context")
    selected_indices = list(map(int, result["selected_body_indices"]))
    selected_modes = list(result["selected_modes"])
    if len(selected_indices) != len(selected_modes):
        raise RuntimeError("E114 replay body/mode count drift")
    selected_rows = [rows[index] for index in selected_indices]

    occupied = set(context["fixed_solid"])
    for row in selected_rows:
        body = set(row["body"])
        if occupied & body:
            raise RuntimeError("E114 replay body overlap")
        occupied |= body
    if any(not set(row["body"]) & set(context["fixed_coverage"]) for row in selected_rows):
        raise RuntimeError("E114 replay unpowered body")
    if Counter(str(row["template"]) for row in selected_rows) != Counter(bundle["template_counts"]):
        raise RuntimeError("E114 replay template-count drift")

    mode_by_body = {int(row["body_index"]): row for row in selected_modes}
    if set(mode_by_body) != set(selected_indices):
        raise RuntimeError("E114 replay mode identity drift")
    observed_classes: Counter[tuple[str, str, int, int]] = Counter()
    front_failures: list[dict[str, Any]] = []
    pools = context["pools"]
    for body_index in selected_indices:
        row = rows[body_index]
        mode = mode_by_body[body_index]
        class_key = tuple(mode["class_key"])
        if class_key not in bundle["class_keys"]:
            raise RuntimeError("E114 replay class identity drift")
        if class_key[1] != str(row["template"]):
            raise RuntimeError("E114 replay class/template drift")
        forced = e095.STABLE_CLASS_BY_BODY.get(str(row["body_digest"]))
        if forced is not None and tuple(class_key[2:]) != tuple(forced):
            raise RuntimeError("E114 replay stable class drift")
        pose_index = int(mode["pose_index"])
        if pose_index not in row["mode_pose_indices"]:
            raise RuntimeError("E114 replay pose/body drift")
        pose = pools[str(row["template"])][pose_index]
        inputs = [e095.cell(value) for value in pose["input_port_cells"]]
        outputs = [e095.cell(value) for value in pose["output_port_cells"]]
        free_inputs = [value for value in inputs if e095.in_grid(value) and value not in occupied]
        free_outputs = [value for value in outputs if e095.in_grid(value) and value not in occupied]
        if len(free_inputs) < int(mode["need_in"]) or len(free_outputs) < int(mode["need_out"]):
            front_failures.append(
                {
                    "body_index": body_index,
                    "body_digest": str(row["body_digest"]),
                    "free_inputs": len(free_inputs),
                    "need_in": int(mode["need_in"]),
                    "free_outputs": len(free_outputs),
                    "need_out": int(mode["need_out"]),
                }
            )
        observed_classes[class_key] += 1
    if front_failures:
        raise RuntimeError(f"E114 replay front failures: {front_failures[:3]}")
    expected_tuple = [observed_classes[key] for key in bundle["class_keys"]]
    if expected_tuple != list(map(int, result["allocation_tuple"])):
        raise RuntimeError("E114 replay allocation drift")
    return {
        "status": "PASS",
        "selected_body_count": len(selected_indices),
        "allocation_tuple": expected_tuple,
        "occupied_cell_count": len(occupied),
        "front_failure_count": 0,
    }


def solve_bundle(
    *,
    e095: types.ModuleType,
    bundle: dict[str, Any],
    seconds: float,
    seed: int,
    profile: str,
) -> dict[str, Any]:
    bundle["context"] = bundle.get("context") or bundle["base_context"]
    solver = solver_for(profile=profile, seconds=seconds, seed=seed)
    before = process_snapshot()
    started = time.monotonic()
    status_code = solver.Solve(bundle["model"])
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)
    result: dict[str, Any] = {
        "schema": "zmd_e114_side_solve_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "side": str(bundle["side"]),
        "status": status,
        "profile": profile,
        "elapsed_seconds": elapsed,
        "solve_seconds": seconds,
        "seed": seed,
        "candidate_count": len(bundle["rows"]),
        "mode_class_variable_count": len(bundle["mode_rows"]),
        "model_variable_count": len(bundle["model"].Proto().variables),
        "model_constraint_count": len(bundle["model"].Proto().constraints),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
        "template_counts": dict(bundle["template_counts"]),
    }
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_body_indices = [
            index
            for index, variable in enumerate(bundle["body_vars"])
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
            for row in bundle["mode_rows"]
            if solver.Value(row["variable"])
        ]
        expected = sum(int(value) for value in bundle["template_counts"].values())
        if len(selected_body_indices) != expected or len(selected_modes) != expected:
            raise RuntimeError("E114 positive selected count drift")
        allocation = (
            {
                key: int(solver.Value(variable))
                for key, variable in bundle["allocation_vars"].items()
            }
            if bundle["allocation_vars"]
            else Counter(tuple(row["class_key"]) for row in selected_modes)
        )
        rows = bundle["rows"]
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
                    int(allocation[key]) for key in bundle["class_keys"]
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
        result["semantic_replay"] = replay_side_positive(
            e095=e095,
            bundle=bundle,
            result=result,
        )
    return result


def solve_with_fallback(
    *,
    builder: Callable[[], dict[str, Any]],
    e095: types.ModuleType,
    primary_seconds: float,
    fallback_seconds: float,
    seed: int,
) -> dict[str, Any]:
    primary_bundle = builder()
    primary = solve_bundle(
        e095=e095,
        bundle=primary_bundle,
        seconds=primary_seconds,
        seed=seed,
        profile="one_worker_pseudo_cost",
    )
    fallback: dict[str, Any] | None = None
    terminal = primary
    if primary["status"] == "UNKNOWN" and fallback_seconds > 0:
        fallback_bundle = builder()
        fallback = solve_bundle(
            e095=e095,
            bundle=fallback_bundle,
            seconds=fallback_seconds,
            seed=seed + 100000,
            profile="multiworker_automatic",
        )
        terminal = fallback
    return {
        "primary": primary,
        "fallback": fallback,
        "terminal": terminal,
    }


def run(
    *,
    run_dir: Path,
    high_primary_seconds: float,
    high_fallback_seconds: float,
    low_primary_seconds: float,
    low_fallback_seconds: float,
    total_seconds: float,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E114 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e114_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e114_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e114_source_e101")
    restricted = e100.build_restricted_context(e095)
    projection = load_json(E110_PROJECTION)
    vectors = sorted(projection["vectors"], key=lambda row: int(row["iteration"]))
    if len(vectors) != EXPECTED_GEOMETRY_COUNT:
        raise RuntimeError("E114 geometry count drift")
    keys, global_counts = class_counts(restricted["base"])

    started = time.monotonic()
    high_records: list[dict[str, Any]] = []
    positive_by_allocation: dict[tuple[int, ...], dict[str, Any]] = {}
    untested_geometry_ids: list[str] = []

    for rank, vector_record in enumerate(vectors):
        remaining = float(total_seconds) - (time.monotonic() - started)
        geometry = validate_geometry(record=vector_record, restricted=restricted)
        geometry_id = (
            f"geometry_{int(geometry['iteration']):02d}_"
            f"{str(geometry['selected_body_digest'])[:12]}"
        )
        if remaining <= 1.0:
            untested_geometry_ids.append(geometry_id)
            continue
        selected_set = set(map(int, geometry["selected_global_indices"]))

        def high_builder(selected: set[int] = selected_set) -> dict[str, Any]:
            bundle = fix_geometry(
                e095=e095,
                e101=e101,
                restricted=restricted,
                selected_indices=selected,
            )
            bundle["base_context"] = restricted["base"]
            return bundle

        primary_seconds = min(float(high_primary_seconds), max(0.5, remaining - 0.25))
        fallback_seconds = min(
            float(high_fallback_seconds),
            max(0.0, remaining - primary_seconds - 0.25),
        )
        solve = solve_with_fallback(
            builder=high_builder,
            e095=e095,
            primary_seconds=primary_seconds,
            fallback_seconds=fallback_seconds,
            seed=114100 + rank,
        )
        terminal = solve["terminal"]
        record = {
            "geometry_id": geometry_id,
            "geometry": geometry,
            "primary": solve["primary"],
            "fallback": solve["fallback"],
            "terminal_status": terminal["status"],
            "classification": (
                "FIXED_GEOMETRY_FRONT_FEASIBLE"
                if terminal["status"] in {"OPTIMAL", "FEASIBLE"}
                else "FIXED_GEOMETRY_FRONT_INFEASIBLE"
                if terminal["status"] == "INFEASIBLE"
                else "FIXED_GEOMETRY_FRONT_CENSORED"
            ),
        }
        high_records.append(record)
        if terminal["status"] in {"OPTIMAL", "FEASIBLE"}:
            allocation = tuple(map(int, terminal["allocation_tuple"]))
            positive_by_allocation.setdefault(
                allocation,
                {
                    "geometry_id": geometry_id,
                    "high_result": terminal,
                    "geometry": geometry,
                },
            )

    high_path = run_dir / "HIGH_FIXED_GEOMETRY_RESULTS.json"
    dump_exclusive(
        high_path,
        {
            "schema": "zmd_e114_high_fixed_geometry_results_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "formal_geometry_count": EXPECTED_GEOMETRY_COUNT,
            "tested_geometry_count": len(high_records),
            "untested_geometry_ids": untested_geometry_ids,
            "positive_geometry_count": sum(
                row["terminal_status"] in {"OPTIMAL", "FEASIBLE"}
                for row in high_records
            ),
            "negative_geometry_count": sum(
                row["terminal_status"] == "INFEASIBLE" for row in high_records
            ),
            "unknown_geometry_count": sum(
                row["terminal_status"] == "UNKNOWN" for row in high_records
            ),
            "distinct_positive_allocation_count": len(positive_by_allocation),
            "records": high_records,
            "truth_boundary": (
                "Each negative applies only to one fixed E110 geometry. Positive "
                "allocations are full x42-high native-front witnesses."
            ),
        },
    )

    low_hint_indices = set(map(int, load_json(E101_BODY)["selected_body_indices"]))
    low_records: list[dict[str, Any]] = []
    module_b: dict[str, Any] | None = None
    combined: dict[str, Any] | None = None
    paired_allocation: tuple[int, ...] | None = None
    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"

    for allocation_rank, (allocation, source) in enumerate(positive_by_allocation.items()):
        if combined is not None:
            break
        remaining = float(total_seconds) - (time.monotonic() - started)
        if remaining <= 1.0:
            break
        complement = e101.complement_allocation(keys, global_counts, allocation)

        def low_builder(required: Mapping[tuple[str, str, int, int], int] = complement) -> dict[str, Any]:
            bundle = e101.build_side_model(
                e095=e095,
                restricted=restricted,
                side="low",
                template_counts=LOW_TEMPLATE_COUNTS,
                body_hint_indices=low_hint_indices,
                fixed_allocation=required,
            )
            bundle["base_context"] = restricted["base"]
            return bundle

        primary_seconds = min(float(low_primary_seconds), max(0.5, remaining - 0.25))
        fallback_seconds = min(
            float(low_fallback_seconds),
            max(0.0, remaining - primary_seconds - 0.25),
        )
        solve = solve_with_fallback(
            builder=low_builder,
            e095=e095,
            primary_seconds=primary_seconds,
            fallback_seconds=fallback_seconds,
            seed=114500 + allocation_rank,
        )
        terminal = solve["terminal"]
        low_record = {
            "allocation_rank": allocation_rank,
            "source_geometry_id": source["geometry_id"],
            "high_allocation_tuple": list(allocation),
            "low_complement_tuple": [int(complement[key]) for key in keys],
            "primary": solve["primary"],
            "fallback": solve["fallback"],
            "terminal_status": terminal["status"],
            "classification": (
                "ALLOCATION_PAIRED"
                if terminal["status"] in {"OPTIMAL", "FEASIBLE"}
                else "ALLOCATION_REJECTED_BY_LOW"
                if terminal["status"] == "INFEASIBLE"
                else "LOW_COMPLEMENT_CENSORED"
            ),
        }
        low_records.append(low_record)
        if terminal["status"] in {"OPTIMAL", "FEASIBLE"}:
            pair = e101.combine_side_witnesses(
                e095=e095,
                restricted=restricted,
                low=terminal,
                high=source["high_result"],
            )
            module_b = pair["module_b"]
            combined = pair["combined"]
            paired_allocation = allocation
            dump_exclusive(module_b_path, module_b)
            dump_exclusive(combined_path, combined)

    low_path = run_dir / "LOW_ALLOCATION_RESULTS.json"
    dump_exclusive(
        low_path,
        {
            "schema": "zmd_e114_low_allocation_results_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "distinct_high_allocation_count": len(positive_by_allocation),
            "tested_low_complement_count": len(low_records),
            "paired_allocation_tuple": (
                list(paired_allocation) if paired_allocation is not None else None
            ),
            "records": low_records,
            "truth_boundary": (
                "Low INFEASIBLE rejects only the exact high allocation tuple. "
                "UNKNOWN creates no rule."
            ),
        },
    )

    positive_count = sum(
        row["terminal_status"] in {"OPTIMAL", "FEASIBLE"} for row in high_records
    )
    negative_count = sum(
        row["terminal_status"] == "INFEASIBLE" for row in high_records
    )
    unknown_count = sum(row["terminal_status"] == "UNKNOWN" for row in high_records)
    if combined is not None:
        verdict = "E110_REPRESENTATIVE_GEOMETRY_REACHES_219_BODY_NATIVE_FRONT_WITNESS"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif positive_count > 0:
        verdict = "E110_FIXED_GEOMETRIES_HAVE_HIGH_FRONT_WITNESSES_WITHOUT_PAIRED_LOW_YET"
        decision = "CONTINUE_ONLY_FIXED_GEOMETRY_ALLOCATION_HANDSHAKE"
    elif negative_count == EXPECTED_GEOMETRY_COUNT:
        verdict = "ALL_E110_REPRESENTATIVE_GEOMETRIES_FAIL_FULL_HIGH_NATIVE_FRONT"
        decision = "USE_FULL_CONSUMER_DEATHS_TO_REDESIGN_GEOMETRY_OR_JOINT_COLLAR"
    else:
        verdict = "E110_FIXED_GEOMETRY_DIRECT_CONSUMER_CENSORED"
        decision = "REPLAY_ONLY_NAMED_UNKNOWN_GEOMETRIES"

    result = {
        "schema": "zmd_e114_e110_fixed_geometry_direct_consumer_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "high_primary_seconds": high_primary_seconds,
            "high_fallback_seconds": high_fallback_seconds,
            "low_primary_seconds": low_primary_seconds,
            "low_fallback_seconds": low_fallback_seconds,
            "total_seconds": total_seconds,
            "high_primary_profile": "one_worker_pseudo_cost",
            "fallback_profile": "multiworker_automatic",
            "source_isolated_helpers": True,
        },
        "high_geometries": {
            "path": display(high_path),
            "sha256": sha256_file(high_path),
            "formal_count": EXPECTED_GEOMETRY_COUNT,
            "tested_count": len(high_records),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "unknown_count": unknown_count,
            "untested_count": len(untested_geometry_ids),
            "distinct_positive_allocation_count": len(positive_by_allocation),
        },
        "low_allocations": {
            "path": display(low_path),
            "sha256": sha256_file(low_path),
            "tested_count": len(low_records),
            "positive_count": sum(
                row["terminal_status"] in {"OPTIMAL", "FEASIBLE"}
                for row in low_records
            ),
            "negative_count": sum(
                row["terminal_status"] == "INFEASIBLE" for row in low_records
            ),
            "unknown_count": sum(
                row["terminal_status"] == "UNKNOWN" for row in low_records
            ),
        },
        "module_b_witness": (
            {
                "path": display(module_b_path),
                "sha256": sha256_file(module_b_path),
                "selected_body_count": module_b["selected_body_count"],
                "selected_assignment_digest": module_b["selected_assignment_digest"],
            }
            if module_b is not None
            else None
        ),
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
        "total_elapsed_seconds": time.monotonic() - started,
        "truth_boundary": (
            "The 27 geometries are representatives, not a complete geometry basis. "
            "Each fixed-geometry negative is local. Any paired replay is a valid "
            "complete fixed-skeleton native-front witness but still lacks terminal "
            "uniqueness, binding, routing and throughput."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--high-primary-seconds", type=float, default=4.0)
    parser.add_argument("--high-fallback-seconds", type=float, default=8.0)
    parser.add_argument("--low-primary-seconds", type=float, default=20.0)
    parser.add_argument("--low-fallback-seconds", type=float, default=30.0)
    parser.add_argument("--total-seconds", type=float, default=240.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            high_primary_seconds=float(args.high_primary_seconds),
            high_fallback_seconds=float(args.high_fallback_seconds),
            low_primary_seconds=float(args.low_primary_seconds),
            low_fallback_seconds=float(args.low_fallback_seconds),
            total_seconds=float(args.total_seconds),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "high_geometries": result["high_geometries"],
                    "low_allocations": result["low_allocations"],
                    "combined_witness": result["combined_witness"] is not None,
                    "total_elapsed_seconds": result["total_elapsed_seconds"],
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
            "schema": "zmd_e114_execution_failure_v1",
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
