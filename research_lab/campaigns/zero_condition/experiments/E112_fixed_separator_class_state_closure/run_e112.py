#!/usr/bin/env python3
"""E112: classify E111's 52 residual separator class states."""

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
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E112_fixed_separator_class_state_closure/run-001"
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
E110_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E110_explicit_separator_template_duty_atlas/run_e110.py"
)
E110_PROJECTION = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E110_explicit_separator_template_duty_atlas/run-001/"
    "SEPARATOR_TEMPLATE_PROJECTION.json"
)
E111_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E111_separator_native_front_class_atlas/run_e111.py"
)
E111_DURABLE = E111_RUNNER.with_name("RESULT.txt")
E111_SNAPSHOT = E111_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E111_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E111_separator_native_front_class_atlas/run-003"
)
E111_RESULT = E111_RUN / "RESULT.json"
E111_PROJECTION = E111_RUN / "SEPARATOR_CLASS_PROJECTION.json"
E111_CHECK = E111_RUN / "ARTIFACT_CHECK.json"
E111_RESIDUAL = E111_RUN / "RESIDUAL_CLASS_STATES.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E110_RUNNER: "30b2fc298ef56ba68053d47977ef139890e862568b53bba70bdf541f677a1fea",
    E110_PROJECTION: "73570c931c8e8c053ec5a17feaa821e4e69511443882eac01110b470a6537413",
    E111_RUNNER: "ea0ce5442c485b6c992b2ec27edb86b18bfc6354bb22e0295909ee5813b435e4",
    E111_DURABLE: "ed587b022b83a5eb6e19eaaa8c46745bcda6332e388d372870ac9ee7005a934a",
    E111_SNAPSHOT: "79f4feed000031a45890d0efc6fad3f1daaa9c709224cefa5b6351ca9d8330a8",
    E111_RESULT: "044863b79194b591156ee991e78519aecb101553b98d9aaa27bf8e2d81a6cbad",
    E111_PROJECTION: "58d8a27697ae03612ce770afece3d0bf395fb2dd8e7c6ad9a92163222ba5464c",
    E111_CHECK: "cc52d98fb0a5e0cdc715855174315e627dfd2de8d271dda317ee802779ade786",
    E111_RESIDUAL: "d5731a2260565d09eecc9f90e5eef761b63709622b09e6306ad3959efa50ccf0",
}

EXPECTED_FORMAL_STATE_COUNT = 353
EXPECTED_PRIOR_POSITIVE_COUNT = 301
EXPECTED_RESIDUAL_COUNT = 52
EXPECTED_CLASS_COUNT = 8
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
        raise RuntimeError("E112 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E112 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E112 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load_json(E111_RESULT)
    if result.get("verdict") != "SEPARATOR_NATIVE_FRONT_RELAXATION_ATLAS_CENSORED":
        raise RuntimeError("E112 E111 verdict drift")
    check = load_json(E111_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "THREE_HUNDRED_ONE_SEPARATOR_STATES_REPLAYED_FIFTY_TWO_UNRESOLVED"
    ):
        raise RuntimeError("E112 E111 check drift")
    residual = load_json(E111_RESIDUAL)
    if int(residual.get("residual_state_count", -1)) != EXPECTED_RESIDUAL_COUNT:
        raise RuntimeError("E112 residual state count drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def build_fixed_model(
    *,
    e095: types.ModuleType,
    e111: types.ModuleType,
    prepared: Mapping[str, Any],
    formal_states: Sequence[tuple[int, ...]],
    class_keys: Sequence[tuple[str, str, int, int]],
    class_caps: Mapping[tuple[str, str, int, int], int],
    state: Sequence[int],
) -> dict[str, Any]:
    side_model = e111.build_model(
        e095=e095,
        prepared=prepared,
        formal_states=formal_states,
        class_keys=class_keys,
        class_caps=class_caps,
    )
    if len(state) != len(side_model["ordered_allocation_vars"]):
        raise RuntimeError("E112 fixed-state width drift")
    for variable, value in zip(
        side_model["ordered_allocation_vars"],
        state,
        strict=True,
    ):
        side_model["model"].Add(variable == int(value))
    error = side_model["model"].Validate()
    if error:
        raise RuntimeError(f"E112 fixed model invalid: {error}")
    return side_model


def solver_for(
    *,
    seconds: float,
    seed: int,
    profile: str,
) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = int(seed)
    solver.parameters.stop_after_first_solution = True
    if profile == "pseudo_cost":
        solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
        solver.parameters.symmetry_level = 0
        solver.parameters.cp_model_probing_level = 0
    elif profile == "automatic":
        solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
        solver.parameters.symmetry_level = 3
        solver.parameters.cp_model_probing_level = 3
    else:
        raise ValueError(f"unknown E112 solver profile: {profile}")
    return solver


def solve_fixed(
    *,
    e095: types.ModuleType,
    e111: types.ModuleType,
    prepared: Mapping[str, Any],
    formal_states: Sequence[tuple[int, ...]],
    class_keys: Sequence[tuple[str, str, int, int]],
    class_caps: Mapping[tuple[str, str, int, int], int],
    state: tuple[int, ...],
    seconds: float,
    seed: int,
    profile: str,
) -> dict[str, Any]:
    side_model = build_fixed_model(
        e095=e095,
        e111=e111,
        prepared=prepared,
        formal_states=formal_states,
        class_keys=class_keys,
        class_caps=class_caps,
        state=state,
    )
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(seconds=seconds, seed=seed, profile=profile)
    status_code = solver.Solve(side_model["model"])
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)
    result: dict[str, Any] = {
        "status": status,
        "profile": profile,
        "seconds": seconds,
        "seed": seed,
        "elapsed_seconds": elapsed,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
        "model_variable_count": len(side_model["model"].Proto().variables),
        "model_constraint_count": len(side_model["model"].Proto().constraints),
    }
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result["witness"] = e111.extract_witness(
            e095=e095,
            side_model=side_model,
            solver=solver,
            allocation=state,
        )
    return result


def template_vector(
    *,
    e111: types.ModuleType,
    class_keys: Sequence[tuple[str, str, int, int]],
    state: Sequence[int],
) -> tuple[int, int, int]:
    return tuple(
        e111.template_vector_from_allocation(
            class_keys=class_keys,
            allocation=state,
        )
    )


def summarize_complete_atlas(
    *,
    e111: types.ModuleType,
    class_keys: Sequence[tuple[str, str, int, int]],
    prior_positive: set[tuple[int, ...]],
    new_positive: set[tuple[int, ...]],
    negative: set[tuple[int, ...]],
    unknown: set[tuple[int, ...]],
) -> dict[str, Any]:
    all_positive = prior_positive | new_positive
    state_counts = Counter(
        template_vector(e111=e111, class_keys=class_keys, state=state)
        for state in all_positive
    )
    negative_counts = Counter(
        template_vector(e111=e111, class_keys=class_keys, state=state)
        for state in negative
    )
    return {
        "complete": not unknown,
        "formal_state_count": EXPECTED_FORMAL_STATE_COUNT,
        "prior_positive_state_count": len(prior_positive),
        "new_positive_state_count": len(new_positive),
        "positive_state_count": len(all_positive),
        "negative_state_count": len(negative),
        "unknown_state_count": len(unknown),
        "positive_state_digest": stable_digest(sorted(all_positive)),
        "negative_state_digest": stable_digest(sorted(negative)),
        "unknown_state_digest": stable_digest(sorted(unknown)),
        "positive_count_by_template_vector": {
            "/".join(map(str, vector)): int(count)
            for vector, count in sorted(state_counts.items())
        },
        "negative_count_by_template_vector": {
            "/".join(map(str, vector)): int(count)
            for vector, count in sorted(negative_counts.items())
        },
    }


def run(
    *,
    run_dir: Path,
    primary_seconds: float,
    fallback_seconds: float,
    total_seconds: float,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E112 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e112_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e112_source_e100")
    e110 = source_module(E110_RUNNER, "zmd_e112_source_e110")
    e111 = source_module(E111_RUNNER, "zmd_e112_source_e111")
    prepared = e110.restore_three_groups(e095=e095, e100=e100)

    class_caps = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(class_caps))
    if len(class_keys) != EXPECTED_CLASS_COUNT:
        raise RuntimeError("E112 class dimension drift")
    template_vectors = sorted(
        {
            tuple(map(int, record["vector"]))
            for record in load_json(E110_PROJECTION)["vectors"]
        }
    )
    formal_states = e111.formal_class_states(
        class_keys=class_keys,
        class_caps=class_caps,
        template_vectors=template_vectors,
    )
    if len(formal_states) != EXPECTED_FORMAL_STATE_COUNT:
        raise RuntimeError("E112 formal state count drift")

    prior_projection = load_json(E111_PROJECTION)
    prior_positive = {
        tuple(map(int, record["allocation_tuple"]))
        for record in prior_projection["records"]
    }
    if len(prior_positive) != EXPECTED_PRIOR_POSITIVE_COUNT:
        raise RuntimeError("E112 prior positive count drift")
    residual_payload = load_json(E111_RESIDUAL)
    if [list(key) for key in class_keys] != residual_payload["class_order"]:
        raise RuntimeError("E112 residual class order drift")
    residual_states = [
        tuple(map(int, record["allocation_tuple"]))
        for record in residual_payload["residual_states"]
    ]
    if len(residual_states) != EXPECTED_RESIDUAL_COUNT:
        raise RuntimeError("E112 residual width/count drift")
    if set(residual_states) & prior_positive:
        raise RuntimeError("E112 residual/positive state overlap")
    if set(residual_states) | prior_positive != set(formal_states):
        raise RuntimeError("E112 formal partition drift")

    started = time.monotonic()
    records: list[dict[str, Any]] = []
    new_positive: set[tuple[int, ...]] = set()
    negative: set[tuple[int, ...]] = set()
    unknown: set[tuple[int, ...]] = set()

    for index, state in enumerate(residual_states):
        remaining = float(total_seconds) - (time.monotonic() - started)
        if remaining <= 0:
            unknown.update(residual_states[index:])
            break
        primary = solve_fixed(
            e095=e095,
            e111=e111,
            prepared=prepared,
            formal_states=formal_states,
            class_keys=class_keys,
            class_caps=class_caps,
            state=state,
            seconds=min(float(primary_seconds), remaining),
            seed=112100 + index,
            profile="pseudo_cost",
        )
        record: dict[str, Any] = {
            "state_index": index,
            "allocation_tuple": list(state),
            "template_vector": list(
                template_vector(e111=e111, class_keys=class_keys, state=state)
            ),
            "primary": primary,
            "fallback": None,
        }
        status = str(primary["status"])
        if status in {"OPTIMAL", "FEASIBLE"}:
            record["classification"] = "FIXED_STATE_FEASIBLE"
            record["witness"] = primary["witness"]
            new_positive.add(state)
            records.append(record)
            continue
        if status == "INFEASIBLE":
            record["classification"] = "FIXED_STATE_INFEASIBLE"
            negative.add(state)
            records.append(record)
            continue

        remaining = float(total_seconds) - (time.monotonic() - started)
        if remaining <= 0:
            record["classification"] = "FIXED_STATE_UNKNOWN"
            unknown.add(state)
            records.append(record)
            unknown.update(residual_states[index + 1 :])
            break
        fallback = solve_fixed(
            e095=e095,
            e111=e111,
            prepared=prepared,
            formal_states=formal_states,
            class_keys=class_keys,
            class_caps=class_caps,
            state=state,
            seconds=min(float(fallback_seconds), remaining),
            seed=112600 + index,
            profile="automatic",
        )
        record["fallback"] = fallback
        fallback_status = str(fallback["status"])
        if fallback_status in {"OPTIMAL", "FEASIBLE"}:
            record["classification"] = "FIXED_STATE_FEASIBLE"
            record["witness"] = fallback["witness"]
            new_positive.add(state)
        elif fallback_status == "INFEASIBLE":
            record["classification"] = "FIXED_STATE_INFEASIBLE"
            negative.add(state)
        else:
            record["classification"] = "FIXED_STATE_UNKNOWN"
            unknown.add(state)
        records.append(record)

    classified = new_positive | negative | unknown
    unattempted = set(residual_states) - classified
    unknown |= unattempted
    summary = summarize_complete_atlas(
        e111=e111,
        class_keys=class_keys,
        prior_positive=prior_positive,
        new_positive=new_positive,
        negative=negative,
        unknown=unknown,
    )
    if (
        summary["positive_state_count"]
        + summary["negative_state_count"]
        + summary["unknown_state_count"]
        != EXPECTED_FORMAL_STATE_COUNT
    ):
        raise RuntimeError("E112 complete atlas accounting drift")

    residual_results = {
        "schema": "zmd_e112_fixed_separator_state_results_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "class_order": [list(key) for key in class_keys],
        "source_residual_state_count": len(residual_states),
        "records": records,
        "new_positive_states": [list(value) for value in sorted(new_positive)],
        "negative_states": [list(value) for value in sorted(negative)],
        "unknown_states": [list(value) for value in sorted(unknown)],
        "summary": summary,
        "truth_boundary": (
            "Each terminal result applies only to one fixed separator-only class "
            "state. Positive states still omit low/high body coupling."
        ),
    }
    residual_results_path = run_dir / "FIXED_STATE_RESULTS.json"
    dump_exclusive(residual_results_path, residual_results)

    atlas = {
        "schema": "zmd_e112_separator_class_atlas_manifest_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "complete": bool(summary["complete"]),
        "summary": summary,
        "prior_positive_projection": {
            "path": display(E111_PROJECTION),
            "sha256": sha256_file(E111_PROJECTION),
            "positive_state_count": len(prior_positive),
        },
        "fixed_state_results": {
            "path": display(residual_results_path),
            "sha256": sha256_file(residual_results_path),
            "new_positive_state_count": len(new_positive),
            "negative_state_count": len(negative),
            "unknown_state_count": len(unknown),
        },
        "positive_states": [
            list(value) for value in sorted(prior_positive | new_positive)
        ],
        "negative_states": [list(value) for value in sorted(negative)],
        "unknown_states": [list(value) for value in sorted(unknown)],
        "truth_boundary": (
            "Complete exact partition only when unknown_state_count is zero. "
            "The feasible partition remains an optimistic separator-only atlas."
        ),
    }
    atlas_path = run_dir / "SEPARATOR_CLASS_ATLAS_MANIFEST.json"
    dump_exclusive(atlas_path, atlas)

    if summary["complete"]:
        verdict = "SEPARATOR_NATIVE_FRONT_RELAXATION_ATLAS_COMPLETE"
        decision = "BUILD_SIDE_CONDITIONED_SEPARATOR_INTERFACE"
    else:
        verdict = "FIXED_SEPARATOR_CLASS_STATE_CLOSURE_CENSORED"
        decision = "REPLAY_ONLY_UNKNOWN_FIXED_STATES"

    result = {
        "schema": "zmd_e112_fixed_separator_class_state_closure_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "primary_seconds": primary_seconds,
            "fallback_seconds": fallback_seconds,
            "total_seconds": total_seconds,
            "primary_profile": "one_worker_pseudo_cost",
            "fallback_profile": "one_worker_automatic",
            "source_isolated_helpers": True,
        },
        "fixed_state_results": {
            "path": display(residual_results_path),
            "sha256": sha256_file(residual_results_path),
        },
        "atlas_manifest": {
            "path": display(atlas_path),
            "sha256": sha256_file(atlas_path),
            **summary,
        },
        "truth_boundary": (
            "Fixed-state closure of the E111 separator-only relaxation. Negative "
            "states are exact necessary nogoods. Positive states require side-"
            "conditioned body/front consumers before transfer."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--primary-seconds", type=float, default=12.0)
    parser.add_argument("--fallback-seconds", type=float, default=25.0)
    parser.add_argument("--total-seconds", type=float, default=260.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            primary_seconds=float(args.primary_seconds),
            fallback_seconds=float(args.fallback_seconds),
            total_seconds=float(args.total_seconds),
        )
        result_path = run_dir / "RESULT.json"
        atlas = result["atlas_manifest"]
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "positive_state_count": atlas["positive_state_count"],
                    "negative_state_count": atlas["negative_state_count"],
                    "unknown_state_count": atlas["unknown_state_count"],
                    "complete": atlas["complete"],
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
            "schema": "zmd_e112_execution_failure_v1",
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
