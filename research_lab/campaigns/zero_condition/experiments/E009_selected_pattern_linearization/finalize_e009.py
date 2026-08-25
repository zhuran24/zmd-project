#!/usr/bin/env python3
"""Finalize E009 from its completed solver witness after a postprocess key error.

The LNS solve completed and wrote an assignment/layout before the original runner
looked up one wrong baseline JSON field. This script does not rerun search. It
pins the solver log and witness bytes, reconstructs the real interface metrics,
and writes the terminal research result.
"""

from __future__ import annotations

from collections import defaultdict
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
E009_RUNNER = Path(__file__).resolve().parent / "run_e009.py"
E006_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E006_free_adjacency_master/run_e006.py"
)
E002_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E002_component_commodity_core/run_component_core.py"
)
E006_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E006_free_adjacency_master/run-003/PERMEABILITY_ASSIGNMENT.json"
)
E007_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E007_permeability_interface/run-001/RESULT.json"
)
OUT = ROOT / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001"
ASSIGNMENT_PATH = OUT / "PATTERN_EXPOSED_ASSIGNMENT.json"
LAYOUT_PATH = OUT / "PATTERN_EXPOSED_LAYOUT.json"
LOG_PATH = OUT / "SOLVER.log"
ORIGINAL_FAILURE_PATH = OUT / "FAILURE.json"
RESULT_PATH = OUT / "RESULT.json"

EXECUTED_RUNNER_SHA256 = "c7706e386bd1719c12f3b1c2084c6a564348ab054a8cc174d6ad9bf98169129a"
EXPECTED_HASHES: dict[Path, str] = {
    E006_RUNNER: "84634cb920fe19a0d724af5e2927ede228b2383fd7c0babf10403b1324bdf20d",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E006_ASSIGNMENT: "29692d8465374498100e6f58069c92eabb69460d8fc742912ec0984877218b43",
    E007_RESULT: "51b0ed0c8b10e1454b5fb7c1785e7b9c9a9db56501c5d420e300daaec511bdee",
    ASSIGNMENT_PATH: "7a4a2a21cc13621e935fc6672bfa9f691e2d340ec120ec0947b3b62b3d648924",
    LAYOUT_PATH: "3b23f3f801d5b06f5cde90beb7ceb5074101d2be543b141e68ab432940e70d33",
    LOG_PATH: "b0854d3b1d8c3b8ad82b6506d7b5de71cdd94f835b0b97280a37d26dfd948c45",
}
EXPECTED_ENV: dict[str, str] = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "260829",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXACT_PATTERN_WEIGHT = 10_000
GENERIC_CLEAR_WEIGHT = 100
POWER_POLE_PENALTY = 1
REFERENCE_GENERIC_CLEAR = 59
REFERENCE_POWER_POLES = 54
REFERENCE_MEANINGFUL_PATTERNS = 12_289
REFERENCE_OBJECTIVE = (
    EXACT_PATTERN_WEIGHT * REFERENCE_MEANINGFUL_PATTERNS
    + GENERIC_CLEAR_WEIGHT * REFERENCE_GENERIC_CLEAR
    - POWER_POLE_PENALTY * REFERENCE_POWER_POLES
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


def verify_environment() -> dict[str, Any]:
    actual = {key: os.environ.get(key) for key in EXPECTED_ENV}
    mismatches = {
        key: {"expected": expected, "actual": actual[key]}
        for key, expected in EXPECTED_ENV.items()
        if actual[key] != expected
    }
    unexpected = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected:
        raise RuntimeError(
            f"environment mismatch: mismatches={mismatches}, unexpected={unexpected}"
        )
    return {"actual": actual, "unexpected_exact_variables": unexpected}


def verify_identity() -> dict[str, Any]:
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")
    failure = load_json(ORIGINAL_FAILURE_PATH)
    if failure.get("error") != "KeyError" or failure.get("detail") != "'total_selected_placement_count'":
        raise RuntimeError("original postprocess failure is not the expected incident")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "checked_hashes": checked,
        "executed_runner_sha256": EXECUTED_RUNNER_SHA256,
        "repaired_runner_sha256": sha256_file(E009_RUNNER),
        "finalizer_sha256": sha256_file(Path(__file__).resolve()),
        "original_failure_sha256": sha256_file(ORIGINAL_FAILURE_PATH),
    }


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_solver_log() -> dict[str, Any]:
    text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
    hint_match = re.search(r"#1\s+[^\n]*best:(\d+)", text)
    objective_match = re.search(r"\nobjective:\s*([-+0-9.eE]+)", text)
    bound_match = re.search(r"\nbest_bound:\s*([-+0-9.eE]+)", text)
    wall_match = re.search(r"\nwalltime:\s*([-+0-9.eE]+)", text)
    status_match = re.search(r"CpSolverResponse summary:\nstatus:\s*(\w+)", text)
    if not all((hint_match, objective_match, bound_match, wall_match, status_match)):
        raise RuntimeError("cannot parse terminal solver log")
    first_incumbent = int(hint_match.group(1))
    if first_incumbent != REFERENCE_OBJECTIVE:
        raise RuntimeError(
            f"repaired complete hint objective drift: {first_incumbent} != {REFERENCE_OBJECTIVE}"
        )
    return {
        "status": status_match.group(1),
        "first_registered_incumbent": first_incumbent,
        "objective": int(round(float(objective_match.group(1)))),
        "best_bound": float(bound_match.group(1)),
        "wall_time": float(wall_match.group(1)),
        "complete_hint_reported_infeasible_then_repaired": (
            "The solution hint is complete, but it is infeasible!" in text
        ),
        "solution_count": len(re.findall(r"^#\d+\s", text, flags=re.MULTILINE)),
    }


def semantic_selection(
    solution: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[tuple[str, str], set[int]], set[int], set[tuple[str, int]]]:
    groups: dict[tuple[str, str], set[int]] = defaultdict(set)
    poles: set[int] = set()
    optionals: set[tuple[str, int]] = set()
    for row in solution.values():
        pose_idx = int(row["pose_idx"])
        if bool(row.get("is_mandatory")):
            groups[
                (str(row.get("facility_type", "")), str(row.get("operation_type", "")))
            ].add(pose_idx)
        elif str(row.get("facility_type", "")) == "power_pole":
            poles.add(pose_idx)
        else:
            optionals.add((str(row.get("facility_type", "")), pose_idx))
    return groups, poles, optionals


def trust_distance(
    reference: Mapping[str, Mapping[str, Any]],
    candidate: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    ref_groups, ref_poles, ref_optionals = semantic_selection(reference)
    new_groups, new_poles, new_optionals = semantic_selection(candidate)
    old_off = sum(
        len(poses - new_groups.get(group, set()))
        for group, poses in ref_groups.items()
    ) + len(ref_poles - new_poles) + len(ref_optionals - new_optionals)
    new_on = sum(
        len(poses - ref_groups.get(group, set()))
        for group, poses in new_groups.items()
    ) + len(new_poles - ref_poles) + len(new_optionals - ref_optionals)
    return {"reference_literals_left": old_off, "new_literals_entered": new_on}


def cut_literal_membership(candidate: Mapping[str, Mapping[str, Any]]) -> dict[str, bool]:
    blue_poses = {
        int(row["pose_idx"])
        for row in candidate.values()
        if bool(row.get("is_mandatory"))
        and str(row.get("operation_type", "")) == "refinery_blue_iron"
    }
    steel_poses = {
        int(row["pose_idx"])
        for row in candidate.values()
        if bool(row.get("is_mandatory"))
        and str(row.get("operation_type", "")) == "refinery_steel"
    }
    pole_poses = {
        int(row["pose_idx"])
        for row in candidate.values()
        if str(row.get("facility_type", "")) == "power_pole"
    }
    membership = {
        "power_pole_pose_1635": 1635 in pole_poses,
        "blue_iron_pose_5422": 5422 in blue_poses,
        "blue_iron_pose_5702": 5702 in blue_poses,
        "steel_pose_6494": 6494 in steel_poses,
    }
    if all(membership.values()):
        raise RuntimeError("candidate violates E001 four-literal cut")
    return membership


def run() -> dict[str, Any]:
    identity = verify_identity()
    environment = verify_environment()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    e009 = import_module("zmd_e009_repaired", E009_RUNNER)
    base = import_module("zmd_e006_base", E006_RUNNER)
    e001 = base.import_e001_module()
    e002 = import_module("zmd_e002_helper", E002_RUNNER)
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)

    reference = base.reconstruct_solution(E006_ASSIGNMENT)
    candidate_payload = load_json(ASSIGNMENT_PATH)
    candidate = {
        str(instance_id): dict(record)
        for instance_id, record in candidate_payload["solution"].items()
        if isinstance(record, Mapping)
    }
    if json_safe(candidate) != json_safe(
        {
            str(row["instance_id"]): dict(row)
            for row in load_json(LAYOUT_PATH)["placements"]
        }
    ):
        raise RuntimeError("candidate assignment/layout mismatch")

    started = time.monotonic()
    interface = e009.evaluate_interface(solution=candidate, inputs=inputs, e002=e002)
    morphology = base.morphology(solution=candidate, pools=inputs["pools"])
    solver = parse_solver_log()
    candidate_objective = int(candidate_payload["linearized_objective"])
    if candidate_objective != solver["objective"]:
        raise RuntimeError("assignment/log objective mismatch")

    candidate_poles = sum(
        str(row.get("facility_type", "")) == "power_pole"
        for row in candidate.values()
    )
    candidate_generic_clear = (
        int(interface["compiled_interface"]["generic_input_slot_count"])
        + int(interface["compiled_interface"]["generic_output_slot_count"])
    )
    numerator = (
        candidate_objective
        + POWER_POLE_PENALTY * candidate_poles
        - GENERIC_CLEAR_WEIGHT * candidate_generic_clear
    )
    if numerator % EXACT_PATTERN_WEIGHT:
        raise RuntimeError("candidate objective cannot be decoded into integer pattern score")
    predicted_patterns = numerator // EXACT_PATTERN_WEIGHT

    baseline = load_json(E007_RESULT)
    baseline_domains = baseline["binding"]["conflict_summary"]["binding_domains"]
    baseline_meaningful = sum(
        int(count)
        for instance_id, count in baseline_domains.items()
        if str(reference[instance_id].get("facility_type", "")) != "power_pole"
    )
    if baseline_meaningful != REFERENCE_MEANINGFUL_PATTERNS:
        raise RuntimeError("baseline meaningful pattern count drift")

    actual_patterns = int(interface["meaningful_filtered_pattern_count"])
    baseline_compiled = baseline["binding"]["compiled_interface"]
    actual_total = int(interface["compiled_interface"]["filtered_binding_option_count"])
    baseline_total = int(baseline_compiled["filtered_binding_option_count"])
    actual_pruned = int(
        interface["compiled_interface"]["routing_aware_filter_stats"][
            "front_blocked_patterns_pruned"
        ]
    )
    baseline_pruned = int(
        baseline_compiled["routing_aware_filter_stats"][
            "front_blocked_patterns_pruned"
        ]
    )

    verdict = (
        "PATTERN_EXPOSED_COMPONENT_BINDING_FEASIBLE"
        if interface["status"] == "FEASIBLE"
        else "PATTERN_EXPOSED_CANDIDATE"
        if actual_patterns > baseline_meaningful
        else "PATTERN_LINEARIZATION_UNFAITHFUL"
    )
    return {
        "schema": "zmd_zero_condition_e009_selected_pattern_linearization_final_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "environment": environment,
        "recovery": {
            "search_rerun": False,
            "reason": (
                "The original solver completed and wrote the witness; only a "
                "postprocess lookup used a nonexistent E006 result field."
            ),
            "original_failure": json_safe(load_json(ORIGINAL_FAILURE_PATH)),
        },
        "linearization": {
            "trust_radius": 20,
            "max_power_poles": 54,
            "weights": {
                "exact_pattern": EXACT_PATTERN_WEIGHT,
                "generic_clear": GENERIC_CLEAR_WEIGHT,
                "power_pole_penalty": POWER_POLE_PENALTY,
            },
            "reference_exact_patterns": REFERENCE_MEANINGFUL_PATTERNS,
            "reference_generic_clear": REFERENCE_GENERIC_CLEAR,
            "reference_power_poles": REFERENCE_POWER_POLES,
            "reference_objective": REFERENCE_OBJECTIVE,
            "candidate_predicted_exact_patterns": predicted_patterns,
            "candidate_generic_clear": candidate_generic_clear,
            "candidate_power_poles": candidate_poles,
            "candidate_objective": candidate_objective,
            "predicted_pattern_gain": predicted_patterns
            - REFERENCE_MEANINGFUL_PATTERNS,
            "objective_gain": candidate_objective - REFERENCE_OBJECTIVE,
            "trust_distance": trust_distance(reference, candidate),
        },
        "solve": solver,
        "candidate": {
            "assignment_path": str(ASSIGNMENT_PATH.relative_to(ROOT)),
            "assignment_sha256": sha256_file(ASSIGNMENT_PATH),
            "layout_path": str(LAYOUT_PATH.relative_to(ROOT)),
            "layout_sha256": sha256_file(LAYOUT_PATH),
            "selected_placement_count": len(candidate),
            "mandatory_count": sum(
                bool(row.get("is_mandatory")) for row in candidate.values()
            ),
            "power_pole_count": candidate_poles,
            "cut_literal_membership": cut_literal_membership(candidate),
            "morphology": morphology,
            "interface": interface,
            "actual_meaningful_filtered_patterns": actual_patterns,
            "actual_meaningful_pattern_gain": actual_patterns
            - baseline_meaningful,
            "actual_total_filtered_patterns": actual_total,
            "actual_total_pattern_gain": actual_total - baseline_total,
            "actual_front_pruned_patterns": actual_pruned,
            "front_pruned_change": actual_pruned - baseline_pruned,
            "prediction_error_actual_minus_predicted": actual_patterns
            - predicted_patterns,
        },
        "routing_solver_run": False,
        "truth_boundary": (
            "One radius-20 local linearization around E006. The candidate is a "
            "placement-plus-power intermediate and remains component-binding "
            f"{interface['status']}."
        ),
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> int:
    if RESULT_PATH.exists():
        raise FileExistsError(f"refusing to overwrite {RESULT_PATH}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "linearization": result["linearization"],
                    "morphology": result["candidate"]["morphology"],
                    "interface_status": result["candidate"]["interface"]["status"],
                    "actual_meaningful_pattern_gain": result["candidate"][
                        "actual_meaningful_pattern_gain"
                    ],
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FINALIZATION_FAILURE",
                    "error": type(exc).__name__,
                    "detail": str(exc),
                    "traceback": traceback.format_exc(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
