#!/usr/bin/env python3
"""E102: solver-diverse replay of E101's unchanged high-side model."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import types
from typing import Any

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E102_high_side_solver_diverse_replay/run-001"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"
E101_DIR = ROOT / "research_lab/campaigns/zero_condition/experiments/E101_x42_allocation_handshake"
E101_RUNNER = E101_DIR / "run_e101.py"
E101_DURABLE = E101_DIR / "RESULT.txt"
E101_RESULT = ROOT / "research_lab/local/zero_condition/E101_x42_allocation_handshake/run-001/RESULT.json"
E101_CHECK = E101_RESULT.with_name("ARTIFACT_CHECK.json")
E101_BODY = E101_RESULT.with_name("BODY_ONLY_RESULT.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_DURABLE: "5395b9a852c9883b9662390740164ef2222710f83edd468985c3056030354f34",
    E101_RESULT: "b6b088f214fcbb3be01b26180ce9d211b647ede4038e7542531077548bfd9e9d",
    E101_CHECK: "35eb5580acf84a9b25e7569403ac5aa5814285fa29dd225c9bd5e9bd28eb0055",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
}
HIGH_SECONDS = 90.0
LOW_SECONDS = 120.0


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str)
    )


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(json_safe(value), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def source_module(path: Path, name: str, package: str | None = None) -> types.ModuleType:
    raw = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = package if package is not None else name.rpartition(".")[0]
    module.__loader__ = None
    sys.modules[name] = module
    exec(
        compile(raw, f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>", "exec", dont_inherit=True),
        module.__dict__,
    )
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E102 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E102 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E102 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}
    e101 = load_json(E101_RESULT)
    if e101.get("verdict") != "X42_HIGH_SIDE_ALLOCATION_PROPOSER_CENSORED":
        raise RuntimeError("E102 E101 verdict drift")
    if e101.get("decision") != "CHANGE_HIGH_SIDE_SOLVER_OR_DERIVE_ALLOCATION_BOUNDS":
        raise RuntimeError("E102 E101 decision drift")
    check = load_json(E101_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != "BODY_WITNESS_VALID_HIGH_SIDE_CENSORED":
        raise RuntimeError("E102 E101 check drift")
    body = load_json(E101_BODY)
    if body.get("status") != "OPTIMAL" or body.get("side_body_counts") != {"high": 26, "low": 65}:
        raise RuntimeError("E102 body allocation drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def pseudo_cost_solver(seed: int, seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = int(seed)
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.randomize_search = False
    solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
    solver.parameters.repair_hint = True
    solver.parameters.hint_conflict_limit = 4000
    solver.parameters.stop_after_first_solution = True
    return solver


def run(*, run_dir: Path, high_seconds: float, low_seconds: float) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E102 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(OPERATION_PROFILES, "src.preprocess.operation_profiles", package="src.preprocess")
    e095 = source_module(E095_RUNNER, "zmd_e102_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e102_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e102_source_e101")
    restricted = e100.build_restricted_context(e095)
    body = load_json(E101_BODY)
    selected_indices = set(map(int, body["selected_body_indices"]))
    high_templates = {
        template: int(body["side_template_counts"].get(f"high:{template}", 0))
        for template in e101.TEMPLATES
    }
    low_templates = {
        template: int(body["side_template_counts"].get(f"low:{template}", 0))
        for template in e101.TEMPLATES
    }

    high_model = e101.build_side_model(
        e095=e095,
        restricted=restricted,
        side="high",
        template_counts=high_templates,
        body_hint_indices=selected_indices,
        fixed_allocation=None,
    )
    original_solver_for = e101.solver_for
    e101.solver_for = pseudo_cost_solver
    try:
        high = e101.solve_side(high_model, seconds=high_seconds, seed=102001)
    finally:
        e101.solver_for = original_solver_for
    high_path = run_dir / "HIGH_RESULT.json"
    dump_exclusive(high_path, high)

    high_status = str(high["status"])
    low: dict[str, Any] | None = None
    low_path = run_dir / "LOW_RESULT.json"
    module_b: dict[str, Any] | None = None
    combined: dict[str, Any] | None = None
    allocation_tuple: list[int] | None = None

    if high_status in {"OPTIMAL", "FEASIBLE"}:
        allocation_tuple = list(map(int, high["allocation_tuple"]))
        low_allocation = e101.complement_allocation(
            high_model["class_keys"], high_model["global_class_counts"], allocation_tuple
        )
        low_model = e101.build_side_model(
            e095=e095,
            restricted=restricted,
            side="low",
            template_counts=low_templates,
            body_hint_indices=selected_indices,
            fixed_allocation=low_allocation,
        )
        low = e101.solve_side(low_model, seconds=low_seconds, seed=102101)
        dump_exclusive(low_path, low)
        low_status = str(low["status"])
        if low_status in {"OPTIMAL", "FEASIBLE"}:
            paired = e101.combine_side_witnesses(
                e095=e095, restricted=restricted, low=low, high=high
            )
            module_b = paired["module_b"]
            combined = paired["combined"]
            verdict = "SOLVER_DIVERSE_X42_PAIRED_FRONT_WITNESS_FOUND"
            decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
        elif low_status == "INFEASIBLE":
            verdict = "SOLVER_DIVERSE_HIGH_ALLOCATION_REJECTED_BY_LOW"
            decision = "CONTINUE_HANDSHAKE_WITH_ALLOCATION_NOGOOD"
        else:
            verdict = "SOLVER_DIVERSE_LOW_COMPLEMENT_CENSORED"
            decision = "REPLAY_EXACT_LOW_COMPLEMENT_WITH_SOLVER_DIVERSITY"
    elif high_status == "INFEASIBLE":
        verdict = "SOLVER_DIVERSE_HIGH_TEMPLATE_ALLOCATION_INFEASIBLE"
        decision = "PROPOSE_NEW_BODY_ONLY_TEMPLATE_ALLOCATION"
    else:
        verdict = "SOLVER_DIVERSE_HIGH_SIDE_STILL_CENSORED"
        decision = "BUILD_HIGH_SIDE_TEMPLATE_SPATIAL_CAPACITY_AUDIT"

    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"
    if module_b is not None:
        dump_exclusive(module_b_path, module_b)
    if combined is not None:
        dump_exclusive(combined_path, combined)

    result = {
        "schema": "zmd_e102_solver_diverse_high_replay_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "high": {
                "workers": 1,
                "search_branching": "PSEUDO_COST_SEARCH",
                "symmetry_level": 0,
                "probing_level": 0,
                "randomize_search": False,
                "seed": 102001,
                "seconds": high_seconds,
            },
            "low_if_triggered": {
                "solver": "E101_QUICK_RESTART_PORTFOLIO",
                "seed": 102101,
                "seconds": low_seconds,
            },
            "feasible_set_changed": False,
        },
        "body_template_allocation": {
            "source_path": display(E101_BODY),
            "source_sha256": sha256_file(E101_BODY),
            "high": high_templates,
            "low": low_templates,
        },
        "high": {
            "path": display(high_path),
            "sha256": sha256_file(high_path),
            "status": high_status,
            "elapsed_seconds": high["elapsed_seconds"],
            "branches": high["branches"],
            "conflicts": high["conflicts"],
            "allocation": high.get("allocation"),
            "allocation_tuple": allocation_tuple,
            "selected_body_count": high.get("selected_body_count", 0),
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
            }
            if low is not None
            else None
        ),
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
                "selected_manufacturing_count": combined["selected_manufacturing_count"],
                "selected_assignment_digest": combined["selected_assignment_digest"],
            }
            if combined is not None
            else None
        ),
        "truth_boundary": (
            "The high feasible set is identical to E101. A high negative is scoped "
            "to one 10/6/10 template allocation; a low negative is one class-vector "
            "nogood. UNKNOWN remains censored."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--high-seconds", type=float, default=HIGH_SECONDS)
    parser.add_argument("--low-seconds", type=float, default=LOW_SECONDS)
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
        print(json.dumps({
            "verdict": result["verdict"],
            "decision": result["decision"],
            "high_status": result["high"]["status"],
            "high_allocation": result["high"]["allocation"],
            "low_status": None if result["low"] is None else result["low"]["status"],
            "combined_witness": result["combined_witness"] is not None,
            "result_path": display(result_path),
            "result_sha256": sha256_file(result_path),
        }, ensure_ascii=False, sort_keys=True), flush=True)
        return 0
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e102_execution_failure_v1",
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
