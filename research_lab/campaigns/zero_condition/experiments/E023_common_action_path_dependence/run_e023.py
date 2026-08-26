#!/usr/bin/env python3
"""E023: replay the common grinder action across four objective-173 states."""

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
OUT = ROOT / "research_lab/local/zero_condition/E023_common_action_path_dependence/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E022_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E022_residual_action_surface/run-003/RESULT.json"
)
E019_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E019_beam_common_action/run-002/RESULT.json"
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
    E019_RESULT: "89f37256e282a7f716092d477495d8e6ec715015d32632c97ca133b0ce40d3e7",
    E022_RUNNER: "060440bd8b5ba2cba7647987fa30bed7b08e8d8ca155d9ddcaed6cd276e09507",
}

PARENT_OBJECTIVE = 173
COMMON_TARGET_LITERAL = (
    "mandatory::group::manufacturing_6x4::grinder_fine_buckwheat::16::7754"
)
CLASS_COUNT = 4


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


def checkpoint_path(class_index: int) -> Path:
    return OUT / f"CLASS_{class_index:02d}.json"


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E023 must run on research/main")
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
    e022 = load_json(E022_RESULT)
    selected = e022["decision_reading"]["selected_next_common_action"]
    if str(selected) != COMMON_TARGET_LITERAL:
        raise RuntimeError(f"E023 target drift: {selected}")
    e019 = load_json(E019_RESULT)
    if e019.get("verdict") != "COMMON_ACTION_BRANCH_INVARIANT":
        raise RuntimeError("E019 control verdict drift")
    if int(e019["branch_response"]["best_child_objective"]) != 178:
        raise RuntimeError("E019 control objective drift")
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
    e022 = import_module("zmd_e023_e022", E022_RUNNER)
    e022_identity = e022.verify_identity()
    e021 = import_module("zmd_e023_e021", e022.E021_RUNNER)
    e001 = import_module("zmd_e023_e001", e021.E001_RUNNER)
    e004 = import_module("zmd_e023_e004", e021.E004_RUNNER)
    e014 = import_module("zmd_e023_e014", e021.E014_RUNNER)
    e015 = import_module("zmd_e023_e015", e021.E015_RUNNER)
    e017 = import_module("zmd_e023_e017", e021.E017_RUNNER)
    e019 = import_module("zmd_e023_e019", e021.E019_RUNNER)

    inputs, states = e022.reconstruct_retained_states(
        e001=e001,
        e004=e004,
        e014=e014,
        e017=e017,
        e019=e019,
        e021=e021,
    )
    if len(states) != CLASS_COUNT:
        raise RuntimeError(f"E023 state count drift: {len(states)}")
    e022_result = load_json(E022_RESULT)
    target = dict(e022_result["comparison"]["selected_common_action"])
    if str(target["literal_key"]) != COMMON_TARGET_LITERAL:
        raise RuntimeError("E023 target payload drift")

    stack = e001.import_stack()
    power = e014.build_power_semantics(e001, stack, inputs)
    class_runs: list[dict[str, Any]] = []
    class_results: list[dict[str, Any]] = []
    child_lookup: dict[
        tuple[int, str], tuple[dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = {}

    for state in states:
        class_index = int(state["class_index"])
        parent_solution = state["solution"]
        source_id = str(target["source_instance_ids"][0])
        if int(parent_solution[source_id]["pose_idx"]) != int(target["pose_idx"]):
            raise RuntimeError(f"E023 target already moved in class {class_index}")
        occupied, _owner_by_cell = e014.base_occupancy(
            parent_solution,
            inputs["pools"],
        )
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
            raise RuntimeError(f"E023 class {class_index} fails power semantics")

        path = checkpoint_path(class_index)
        if path.exists():
            arm = load_json(path)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E023 checkpoint: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E023_CLASS_START",
                        "class_index": class_index,
                        "parent_placement_digest": state["retained_state"][
                            "placement_digest"
                        ],
                        "target": COMMON_TARGET_LITERAL,
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            arm = e017.evaluate_arm(
                index=class_index,
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
            arm["schema"] = "zmd_zero_condition_e023_class_expansion_v1"
            arm["parent_state"] = json_safe(state["retained_state"])
            dump_exclusive(path, arm)
        class_runs.append(arm)

        optimal = [
            record
            for record in arm["candidate_records"]
            if str(record["shared_binding"]["status"]) == "OPTIMAL"
        ]
        ranked = sorted(
            optimal,
            key=lambda record: (
                int(record["shared_binding"]["objective"]),
                -int(record["shared_binding"]["filtered_binding_option_count"]),
                int(record["shared_binding"]["morphology"]["free_component_count"]),
                int(record["pose_idx"]),
            ),
        )
        best = ranked[0] if ranked else None
        best_objective = (
            int(best["shared_binding"]["objective"])
            if best is not None
            else None
        )
        class_results.append(
            {
                "class_index": class_index,
                "parent_objective": PARENT_OBJECTIVE,
                "alternative_count": int(arm["alternative_count"]),
                "status_counts": json_safe(arm["status_counts"]),
                "best_child_objective": best_objective,
                "delta_from_parent": (
                    best_objective - PARENT_OBJECTIVE
                    if best_objective is not None
                    else None
                ),
                "best_replacement_pose_idx": (
                    int(best["pose_idx"]) if best is not None else None
                ),
                "best_replacement_pose_id": (
                    str(best["pose_id"]) if best is not None else None
                ),
                "best_child_placement_digest": (
                    str(best["candidate_solution_digest"])
                    if best is not None
                    else None
                ),
                "best_child_binding_selection_digest": (
                    str(best["shared_binding"]["selection_digest"])
                    if best is not None
                    else None
                ),
            }
        )
        for record in arm["candidate_records"]:
            if str(record["shared_binding"]["status"]) != "OPTIMAL":
                continue
            child_lookup[(class_index, str(record["candidate_solution_digest"]))] = (
                state,
                arm,
                record,
            )

    all_records = [
        {**dict(record), "class_index": int(arm["arm_index"])}
        for arm in class_runs
        for record in arm["candidate_records"]
    ]
    optimal_records = [
        record
        for record in all_records
        if str(record["shared_binding"]["status"]) == "OPTIMAL"
    ]
    if not optimal_records:
        raise RuntimeError("E023 produced no OPTIMAL child")
    ranked_global = sorted(
        optimal_records,
        key=lambda record: (
            int(record["shared_binding"]["objective"]),
            -int(record["shared_binding"]["filtered_binding_option_count"]),
            int(record["shared_binding"]["morphology"]["free_component_count"]),
            int(record["class_index"]),
            int(record["pose_idx"]),
        ),
    )
    best = ranked_global[0]
    class_index = int(best["class_index"])
    parent_state, best_arm, best_record = child_lookup[
        (class_index, str(best["candidate_solution_digest"]))
    ]
    best_solution = e017.reconstruct_candidate(
        arm=best_arm,
        record=best_record,
        pair_solution=parent_state["solution"],
        inputs=inputs,
        e014=e014,
    )
    best_detailed = e015.solve_shared_mismatch(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        random_seed=263999,
        include_boundaries=True,
    )
    if (
        best_detailed["status"] != "OPTIMAL"
        or int(best_detailed["objective"])
        != int(best_record["shared_binding"]["objective"])
    ):
        raise RuntimeError("E023 best detailed replay drift")

    assignment_path = OUT / "BEST_GRINDER_CHILD_ASSIGNMENT.json"
    layout_path = OUT / "BEST_GRINDER_CHILD_LAYOUT.json"
    dump_exclusive(
        assignment_path,
        {
            "schema": "zmd_zero_condition_e023_best_grinder_child_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "shared_mismatch_objective": int(best_detailed["objective"]),
            "parent_class_index": class_index,
            "target_literal": COMMON_TARGET_LITERAL,
            "replacement_pose_idx": int(best_record["pose_idx"]),
            "solution": best_solution,
        },
    )
    dump_exclusive(layout_path, e001.solution_layout(best_solution))

    if int(best_detailed["objective"]) == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=import_module("zmd_e023_e002", e021.E002_RUNNER),
        )
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}

    child_objectives = [
        int(row["best_child_objective"])
        for row in class_results
        if row["best_child_objective"] is not None
    ]
    improved = sum(value < PARENT_OBJECTIVE for value in child_objectives)
    equal = sum(value == PARENT_OBJECTIVE for value in child_objectives)
    worsened = sum(value > PARENT_OBJECTIVE for value in child_objectives)
    if int(best_detailed["objective"]) == 0:
        verdict = "PATH_DEPENDENT_COMMON_ACTION_COMPONENT_CANDIDATE"
    elif improved == CLASS_COUNT:
        verdict = "PATH_DEPENDENT_COMMON_ACTION_IMPROVEMENT"
    elif worsened == CLASS_COUNT:
        verdict = "COMMON_COVERAGE_ACTION_RETIRED_SECOND_REJECTION"
    else:
        verdict = "COMMON_ACTION_RESPONSE_DIVERGED"

    e019 = load_json(E019_RESULT)
    objective_distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal_records
    )
    retain_children = improved > 0 or equal > 0
    return {
        "schema": "zmd_zero_condition_e023_common_action_path_dependence_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "e022_dependency_identity": e022_identity,
        "power_semantics": power["summary"],
        "parent_objective": PARENT_OBJECTIVE,
        "target_literal": COMMON_TARGET_LITERAL,
        "historical_control": {
            "experiment": "E019",
            "parent_objective": 176,
            "best_child_objective": int(
                e019["branch_response"]["best_child_objective"]
            ),
            "worsened_seed_count": int(
                e019["branch_response"]["worsened_seed_count"]
            ),
            "result_sha256": EXPECTED_HASHES[E019_RESULT],
        },
        "class_count": CLASS_COUNT,
        "class_checkpoint_paths": [
            str(checkpoint_path(index).relative_to(ROOT))
            for index in range(1, CLASS_COUNT + 1)
        ],
        "class_results": class_results,
        "total_alternative_count": len(all_records),
        "status_counts": dict(
            sorted(
                Counter(
                    str(record["shared_binding"]["status"])
                    for record in all_records
                ).items()
            )
        ),
        "optimal_candidate_count": len(optimal_records),
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "branch_response": {
            "improved_class_count": improved,
            "equal_class_count": equal,
            "worsened_class_count": worsened,
            "best_child_objective": min(child_objectives),
            "worst_child_objective": max(child_objectives),
            "objective_range": max(child_objectives) - min(child_objectives),
        },
        "best_child": {
            "parent_class_index": class_index,
            "objective": int(best_detailed["objective"]),
            "delta_from_parent": int(best_detailed["objective"]) - PARENT_OBJECTIVE,
            "replacement_pose_idx": int(best_record["pose_idx"]),
            "replacement_pose_id": str(best_record["pose_id"]),
            "placement_digest": stable_digest(best_solution),
            "binding_selection_digest": str(best_detailed["selection_digest"]),
            "per_commodity": json_safe(best_detailed["per_commodity"]),
            "positive_commodity_count": int(
                best_detailed["positive_commodity_count"]
            ),
            "zero_mismatch_commodities": json_safe(
                best_detailed["zero_mismatch_commodities"]
            ),
            "morphology": json_safe(best_detailed["morphology"]),
            "filtered_binding_option_count": int(
                best_detailed["filtered_binding_option_count"]
            ),
            "assignment_path": str(assignment_path.relative_to(ROOT)),
            "assignment_sha256": sha256_file(assignment_path),
            "layout_path": str(layout_path.relative_to(ROOT)),
            "layout_sha256": sha256_file(layout_path),
        },
        "beam_decision": {
            "retain_common_action_children": retain_children,
            "retire_target_from_current_unary_ledger": (
                verdict == "COMMON_COVERAGE_ACTION_RETIRED_SECOND_REJECTION"
            ),
            "next_representation": (
                "retain improved/equal children with parent context"
                if retain_children
                else "branch-specific action or simultaneous two-pose/pose-binding neighborhood"
            ),
        },
        "routing": routing,
        "truth_boundary": (
            "Exhaustive fixed-outside alternatives for one common current literal "
            "across four retained objective-173 states. Other actions and joint "
            "moves remain open."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E023 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "class_results": result["class_results"],
                    "branch_response": result["branch_response"],
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
            "schema": "zmd_zero_condition_e023_common_action_path_dependence_failure_v1",
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
