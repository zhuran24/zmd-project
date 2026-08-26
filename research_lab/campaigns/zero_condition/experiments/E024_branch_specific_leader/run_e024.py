#!/usr/bin/env python3
"""E024: exhaust the class-4-specific crusher-blue-iron leader."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E022_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E022_residual_action_surface/run-003/RESULT.json"
)
E023_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E023_common_action_path_dependence/run-001/RESULT.json"
)
E022_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E022_residual_action_surface/run_e022.py"
)
EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "262100",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E022_RESULT: "d43463034c81d1ce4185f76312a25173e880da9744bcc5bd2023e4610a1e6e83",
    E023_RESULT: "c064e9918b5e8d7cfe422868d1c4e46b9df64b7d0cf22ebab05fb022391caffc",
    E022_RUNNER: "060440bd8b5ba2cba7647987fa30bed7b08e8d8ca155d9ddcaed6cd276e09507",
}
PARENT_OBJECTIVE = 173
CLASS_INDEX = 4
TARGET_LITERAL = (
    "mandatory::group::manufacturing_3x3::crusher_blue_iron::1::2053"
)


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        ).encode("utf-8")
    ).hexdigest()


def dump_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E024 must run on research/main")
    mismatches = {
        key: {"expected": expected, "actual": os.environ.get(key)}
        for key, expected in EXPECTED_ENV.items()
        if os.environ.get(key) != expected
    }
    unexpected_exact = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected_exact:
        raise RuntimeError(
            f"environment mismatch: mismatches={mismatches}, "
            f"unexpected_exact={unexpected_exact}"
        )
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(
                f"frozen identity drift for {path}: {actual} != {expected}"
            )
    e023 = load_json(E023_RESULT)
    if e023.get("verdict") != "COMMON_COVERAGE_ACTION_RETIRED_SECOND_REJECTION":
        raise RuntimeError("E023 stop-rule verdict drift")
    e022 = load_json(E022_RESULT)
    class4 = next(
        row for row in e022["state_surfaces"] if int(row["class_index"]) == CLASS_INDEX
    )
    if str(class4["top_literals"][0]["literal_key"]) != TARGET_LITERAL:
        raise RuntimeError("E024 class-4 leader drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output("status", "--porcelain=v1", "--untracked-files=no"),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e022 = import_module("zmd_e024_e022", E022_RUNNER)
    e022_identity = e022.verify_identity()
    e021 = import_module("zmd_e024_e021", e022.E021_RUNNER)
    e001 = import_module("zmd_e024_e001", e021.E001_RUNNER)
    e004 = import_module("zmd_e024_e004", e021.E004_RUNNER)
    e014 = import_module("zmd_e024_e014", e021.E014_RUNNER)
    e015 = import_module("zmd_e024_e015", e021.E015_RUNNER)
    e017 = import_module("zmd_e024_e017", e021.E017_RUNNER)
    e019 = import_module("zmd_e024_e019", e021.E019_RUNNER)

    inputs, states = e022.reconstruct_retained_states(
        e001=e001,
        e004=e004,
        e014=e014,
        e017=e017,
        e019=e019,
        e021=e021,
    )
    state = next(row for row in states if int(row["class_index"]) == CLASS_INDEX)
    parent_solution = state["solution"]
    e022_result = load_json(E022_RESULT)
    class4 = next(
        row
        for row in e022_result["state_surfaces"]
        if int(row["class_index"]) == CLASS_INDEX
    )
    target = dict(class4["top_literals"][0])
    if str(target["literal_key"]) != TARGET_LITERAL:
        raise RuntimeError("E024 target payload drift")
    source_id = str(target["source_instance_ids"][0])
    if int(parent_solution[source_id]["pose_idx"]) != int(target["pose_idx"]):
        raise RuntimeError("E024 target already moved")

    stack = e001.import_stack()
    power = e014.build_power_semantics(e001, stack, inputs)
    occupied, _owner_by_cell = e014.base_occupancy(parent_solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in parent_solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    if not e014.all_powered_facilities_covered(
        solution=parent_solution,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    ):
        raise RuntimeError("E024 parent fails power semantics")

    arm_path = OUT / "ARM.json"
    arm = e017.evaluate_arm(
        index=CLASS_INDEX,
        target=target,
        pair_solution=parent_solution,
        occupied=occupied,
        selected_poles=selected_poles,
        inputs=inputs,
        power=power,
        e004=e004,
        e014=e014,
        e015=e015,
        runner_sha256=runner_sha256,
    )
    arm["schema"] = "zmd_zero_condition_e024_branch_specific_arm_v1"
    arm["parent_state"] = json_safe(state["retained_state"])
    dump_exclusive(arm_path, arm)

    optimal = [
        record
        for record in arm["candidate_records"]
        if str(record["shared_binding"]["status"]) == "OPTIMAL"
    ]
    if not optimal:
        verdict = "BRANCH_SPECIFIC_LEADER_NO_BASE_FEASIBLE_CHILD"
        return {
            "schema": "zmd_zero_condition_e024_branch_specific_leader_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": verdict,
            "identity": identity,
            "e022_dependency_identity": e022_identity,
            "parent_objective": PARENT_OBJECTIVE,
            "parent_class_index": CLASS_INDEX,
            "target": target,
            "alternative_count": int(arm["alternative_count"]),
            "status_counts": json_safe(arm["status_counts"]),
            "arm_path": str(arm_path.relative_to(ROOT)),
            "routing": {"status": "NOT_REACHED_NO_OPTIMAL_CHILD"},
            "truth_boundary": "One fixed parent and one current literal only.",
            "ledger_effect": "none",
        }

    ranked = sorted(
        optimal,
        key=lambda record: (
            int(record["shared_binding"]["objective"]),
            -int(record["shared_binding"]["filtered_binding_option_count"]),
            int(record["shared_binding"]["morphology"]["free_component_count"]),
            int(record["pose_idx"]),
        ),
    )
    best = ranked[0]
    best_solution = e017.reconstruct_candidate(
        arm=arm,
        record=best,
        pair_solution=parent_solution,
        inputs=inputs,
        e014=e014,
    )
    detailed = e015.solve_shared_mismatch(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        random_seed=264001,
        include_boundaries=True,
    )
    if (
        detailed["status"] != "OPTIMAL"
        or int(detailed["objective"]) != int(best["shared_binding"]["objective"])
    ):
        raise RuntimeError("E024 detailed replay drift")

    assignment_path = OUT / "BEST_BRANCH_CHILD_ASSIGNMENT.json"
    layout_path = OUT / "BEST_BRANCH_CHILD_LAYOUT.json"
    dump_exclusive(
        assignment_path,
        {
            "schema": "zmd_zero_condition_e024_best_branch_child_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "shared_mismatch_objective": int(detailed["objective"]),
            "parent_class_index": CLASS_INDEX,
            "target_literal": TARGET_LITERAL,
            "replacement_pose_idx": int(best["pose_idx"]),
            "solution": best_solution,
        },
    )
    dump_exclusive(layout_path, e001.solution_layout(best_solution))

    objective = int(detailed["objective"])
    if objective == 0:
        verdict = "BRANCH_SPECIFIC_LEADER_COMPONENT_CANDIDATE"
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=import_module("zmd_e024_e002", e021.E002_RUNNER),
        )
    elif objective < PARENT_OBJECTIVE:
        verdict = "BRANCH_SPECIFIC_LEADER_IMPROVES"
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
    elif objective == PARENT_OBJECTIVE:
        verdict = "BRANCH_SPECIFIC_LEADER_EQUAL"
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
    else:
        verdict = "BRANCH_SPECIFIC_LEADER_REJECTED_UNARY_STOP"
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}

    distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal
    )
    return {
        "schema": "zmd_zero_condition_e024_branch_specific_leader_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "e022_dependency_identity": e022_identity,
        "power_semantics": power["summary"],
        "parent_objective": PARENT_OBJECTIVE,
        "parent_class_index": CLASS_INDEX,
        "target": target,
        "alternative_count": int(arm["alternative_count"]),
        "status_counts": json_safe(arm["status_counts"]),
        "optimal_candidate_count": len(optimal),
        "objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "best_child": {
            "objective": objective,
            "delta_from_parent": objective - PARENT_OBJECTIVE,
            "replacement_pose_idx": int(best["pose_idx"]),
            "replacement_pose_id": str(best["pose_id"]),
            "placement_digest": stable_digest(best_solution),
            "binding_selection_digest": str(detailed["selection_digest"]),
            "per_commodity": json_safe(detailed["per_commodity"]),
            "positive_commodity_count": int(detailed["positive_commodity_count"]),
            "zero_mismatch_commodities": json_safe(
                detailed["zero_mismatch_commodities"]
            ),
            "morphology": json_safe(detailed["morphology"]),
            "filtered_binding_option_count": int(
                detailed["filtered_binding_option_count"]
            ),
            "assignment_path": str(assignment_path.relative_to(ROOT)),
            "assignment_sha256": sha256_file(assignment_path),
            "layout_path": str(layout_path.relative_to(ROOT)),
            "layout_sha256": sha256_file(layout_path),
        },
        "arm_path": str(arm_path.relative_to(ROOT)),
        "routing": routing,
        "next_representation": (
            "retain branch-specific child"
            if objective < PARENT_OBJECTIVE
            else "simultaneous two-pose or pose-binding neighborhood"
        ),
        "truth_boundary": (
            "Exhaustive fixed-outside alternatives for one branch-specific current "
            "literal under one retained objective-173 parent."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E024 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "alternative_count": result["alternative_count"],
                    "status_counts": result["status_counts"],
                    "best_child": result.get("best_child"),
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e024_branch_specific_leader_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
