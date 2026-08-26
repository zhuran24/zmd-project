#!/usr/bin/env python3
"""E017: evaluate four possible third members after the successful E016 pair."""

from __future__ import annotations

from collections import Counter
import datetime
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E017_third_member_portfolio/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E013_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E013_residual_boundary_coverage/run-004/RESULT.json"
)
E016_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E016_coupled_pair_search/run-001/RESULT.json"
)
E016_PAIR_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E016_coupled_pair_search/run-001/BEST_PAIR_ASSIGNMENT.json"
)
E016_PAIR_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E016_coupled_pair_search/run-001/BEST_PAIR_LAYOUT.json"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
)
E002_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E002_component_commodity_core/run_component_core.py"
)
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E004_component_mismatch_atlas/run_e004.py"
)
E013_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E013_residual_boundary_coverage/run_e013.py"
)
E014_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E014_fixed_outside_mobility/run_e014.py"
)
E015_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E015_shared_binding_gradient/run_e015.py"
)
E016_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E016_coupled_pair_search/run_e016.py"
)

EXPECTED_HASHES: dict[Path, str] = {
    E013_RESULT: "99c029fe71c2835bd5d2f5cd16d00f324856d70ce305278e2bb3aa944cbf6fd1",
    E016_RESULT: "1a6c85a6db935237c5d0df8666d47b1df36dce59ddaec5ab585883d5e13ca161",
    E016_PAIR_ASSIGNMENT: "aa92cf0328df49c3c2d058b96c0fd941ceba2436859823e15d85b0792d4c5403",
    E016_PAIR_LAYOUT: "41ff2502a5beaf0baf112eb05a4a10f186000527a5f2bf49a410461485caf6cf",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E016_RUNNER: "596a06da87fb710bd34483b9f40da8548de9edc9c7d0abc6415ae2683c8f4571",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    HISTORY_ROOT / "rules/canonical_rules.json": "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0",
    HISTORY_ROOT / "rules/preprocess_plan.json": "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee",
}

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "261700",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

BASELINE_OBJECTIVE = 178
USED_LITERALS = {
    "mandatory::group::manufacturing_3x3::crusher_sandleaf::3::2186",
    "mandatory::group::manufacturing_3x3::crusher_source::4::6191",
}
TARGET_LITERALS = (
    "mandatory::group::manufacturing_6x4::grinder_fine_buckwheat::16::7754",
    "mandatory::group::manufacturing_3x3::crusher_source::4::6073",
    "mandatory::group::manufacturing_3x3::refinery_blue_iron::7::5279",
    "mandatory::group::manufacturing_3x3::refinery_blue_iron::7::5343",
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
        raise RuntimeError("E017 must run on research/main")
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
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")
    e016 = load_json(E016_RESULT)
    if int(e016["best_objective"]) != BASELINE_OBJECTIVE:
        raise RuntimeError("E016 best objective drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output("status", "--porcelain=v1", "--untracked-files=no"),
    }


def load_pair_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E016_PAIR_ASSIGNMENT)
    layout = load_json(E016_PAIR_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E016 pair assignment/layout structure is invalid")
    solution = {
        str(instance_id): dict(record)
        for instance_id, record in raw.items()
        if isinstance(record, Mapping)
    }
    layout_solution = {
        str(record["instance_id"]): dict(record)
        for record in placements
        if isinstance(record, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E016 pair assignment and layout disagree")
    if int(solution["crusher_sandleaf_005"]["pose_idx"]) != 15830:
        raise RuntimeError("E016 first move drift")
    if int(solution["crusher_source_015"]["pose_idx"]) != 6102:
        raise RuntimeError("E016 second move drift")
    return solution


def target_manifest() -> list[dict[str, Any]]:
    e013 = load_json(E013_RESULT)
    portfolio = next(
        row
        for row in e013["max_coverage_by_literal_budget"]
        if int(row["budget"]) == 16
    )["selected_literal_details"]
    by_key = {str(row["literal_key"]): dict(row) for row in portfolio}
    missing = [key for key in TARGET_LITERALS if key not in by_key]
    if missing:
        raise RuntimeError(f"E017 target literals absent from E013: {missing}")
    return [by_key[key] for key in TARGET_LITERALS]


def arm_path(index: int) -> Path:
    return OUT / f"ARM_{index:02d}.json"


def evaluate_arm(
    *,
    index: int,
    target: Mapping[str, Any],
    pair_solution: Mapping[str, Mapping[str, Any]],
    occupied: frozenset[tuple[int, int]],
    selected_poles: set[int],
    inputs: Mapping[str, Any],
    power: Mapping[str, Any],
    e004: Any,
    e014: Any,
    e015: Any,
    runner_sha256: str,
) -> dict[str, Any]:
    alternatives = e014.enumerate_alternatives(
        target=target,
        base_solution=pair_solution,
        pools=inputs["pools"],
        occupied=occupied,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    )
    records: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(alternatives, 1):
        solution = candidate["solution"]
        try:
            shared = e015.solve_shared_mismatch(
                solution=solution,
                inputs=inputs,
                e004=e004,
                random_seed=268000 + 1000 * index + candidate_index,
                include_boundaries=False,
            )
        except RuntimeError as exc:
            if "empty binding domain" not in str(exc):
                raise
            shared = {
                "status": "PORT_DOMAIN_EMPTY",
                "objective": None,
                "detail": str(exc),
            }
        records.append(
            {
                "pose_idx": int(candidate["pose_idx"]),
                "pose_id": str(candidate["pose_id"]),
                "anchor": json_safe(candidate["anchor"]),
                "same_footprint": bool(candidate["same_footprint"]),
                "candidate_solution_digest": stable_digest(solution),
                "shared_binding": shared,
            }
        )
        if candidate_index % 20 == 0:
            print(
                json.dumps(
                    {
                        "event": "E017_ARM_PROGRESS",
                        "arm": index,
                        "candidate": candidate_index,
                        "candidate_total": len(alternatives),
                        "status": shared["status"],
                        "objective": shared.get("objective"),
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            gc.collect()
    return {
        "schema": "zmd_zero_condition_e017_arm_v1",
        "created_at_utc": utc_now(),
        "runner_sha256": runner_sha256,
        "arm_index": index,
        "target": json_safe(target),
        "alternative_count": len(alternatives),
        "candidate_records": records,
        "status_counts": dict(
            sorted(Counter(row["shared_binding"]["status"] for row in records).items())
        ),
    }


def reconstruct_candidate(
    *,
    arm: Mapping[str, Any],
    record: Mapping[str, Any],
    pair_solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    target = arm["target"]
    source_id = str(target["source_instance_ids"][0])
    source_row = pair_solution[source_id]
    facility_type = str(source_row["facility_type"])
    pose_idx = int(record["pose_idx"])
    pose = inputs["pools"][facility_type][pose_idx]
    solution = e014.make_candidate_solution(
        base_solution=pair_solution,
        target_instance_id=source_id,
        target_row=source_row,
        facility_type=facility_type,
        pose_idx=pose_idx,
        pose=pose,
    )
    if stable_digest(solution) != str(record["candidate_solution_digest"]):
        raise RuntimeError("E017 candidate reconstruction drift")
    return solution


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e001 = import_module("zmd_e017_e001", E001_RUNNER)
    e002 = import_module("zmd_e017_e002", E002_RUNNER)
    e004 = import_module("zmd_e017_e004", E004_RUNNER)
    e013 = import_module("zmd_e017_e013", E013_RUNNER)
    e014 = import_module("zmd_e017_e014", E014_RUNNER)
    e015 = import_module("zmd_e017_e015", E015_RUNNER)
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    pair_solution = load_pair_solution()
    occupied, _owner_by_cell = e014.base_occupancy(pair_solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in pair_solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)
    if not e014.all_powered_facilities_covered(
        solution=pair_solution,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    ):
        raise RuntimeError("E016 pair fails reconstructed power semantics")

    targets = target_manifest()
    arms: list[dict[str, Any]] = []
    for index, target in enumerate(targets, 1):
        path = arm_path(index)
        if path.exists():
            arm = load_json(path)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E017 arm checkpoint: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E017_ARM_START",
                        "arm": index,
                        "literal": target["literal_key"],
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            arm = evaluate_arm(
                index=index,
                target=target,
                pair_solution=pair_solution,
                occupied=occupied,
                selected_poles=selected_poles,
                inputs=inputs,
                power=power,
                e004=e004,
                e014=e014,
                e015=e015,
                runner_sha256=runner_sha256,
            )
            dump_exclusive(path, arm)
        arms.append(arm)
        objectives = [
            int(record["shared_binding"]["objective"])
            for record in arm["candidate_records"]
            if record["shared_binding"]["status"] == "OPTIMAL"
        ]
        print(
            json.dumps(
                {
                    "event": "E017_ARM_DONE",
                    "arm": index,
                    "literal": target["literal_key"],
                    "alternatives": arm["alternative_count"],
                    "best_objective": min(objectives) if objectives else None,
                    "status_counts": arm["status_counts"],
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    all_records = [
        {
            "arm_index": int(arm["arm_index"]),
            "target": arm["target"],
            **record,
        }
        for arm in arms
        for record in arm["candidate_records"]
    ]
    optimal = [
        record for record in all_records if record["shared_binding"]["status"] == "OPTIMAL"
    ]
    ranked = sorted(
        optimal,
        key=lambda record: (
            int(record["shared_binding"]["objective"]),
            -len(record["shared_binding"]["zero_mismatch_commodities"]),
            -int(record["shared_binding"]["filtered_binding_option_count"]),
            int(record["shared_binding"]["morphology"]["free_component_count"]),
            int(record["arm_index"]),
            int(record["pose_idx"]),
        ),
    )
    if not ranked:
        raise RuntimeError("E017 has no base-binding-feasible candidate")
    best = ranked[0]
    best_arm = next(
        arm for arm in arms if int(arm["arm_index"]) == int(best["arm_index"])
    )
    best_solution = reconstruct_candidate(
        arm=best_arm,
        record=best,
        pair_solution=pair_solution,
        inputs=inputs,
        e014=e014,
    )
    best_detailed = e015.solve_shared_mismatch(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        random_seed=269999,
        include_boundaries=True,
    )
    if (
        best_detailed["status"] != "OPTIMAL"
        or int(best_detailed["objective"])
        != int(best["shared_binding"]["objective"])
    ):
        raise RuntimeError("E017 best detailed replay drift")

    residual = e015.residual_partner_ranking(
        best_solution=best_solution,
        best_record=best_detailed,
        moved_literal=str(best["target"]["literal_key"]),
        inputs=inputs,
        e013=e013,
    )
    used = set(USED_LITERALS) | {str(best["target"]["literal_key"])}
    fourth_ranking = [
        row
        for row in residual["partner_ranking"]
        if str(row["literal_key"]) not in used
    ]

    best_assignment_path = OUT / "BEST_TRIPLE_ASSIGNMENT.json"
    best_layout_path = OUT / "BEST_TRIPLE_LAYOUT.json"
    dump_exclusive(
        best_assignment_path,
        {
            "schema": "zmd_zero_condition_e017_best_triple_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "shared_mismatch_objective": int(best_detailed["objective"]),
            "third_literal": str(best["target"]["literal_key"]),
            "third_replacement_pose_idx": int(best["pose_idx"]),
            "solution": best_solution,
        },
    )
    dump_exclusive(best_layout_path, e001.solution_layout(best_solution))

    if int(best_detailed["objective"]) == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}

    best_objective = int(best_detailed["objective"])
    if best_objective == 0:
        verdict = "TRIPLE_COMPONENT_FEASIBLE_CANDIDATE"
    elif best_objective < BASELINE_OBJECTIVE:
        verdict = "TRIPLE_SHARED_MISMATCH_IMPROVEMENT"
    else:
        verdict = "THIRD_MEMBER_PORTFOLIO_NO_IMPROVEMENT"
    objective_distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal
    )
    return {
        "schema": "zmd_zero_condition_e017_third_member_portfolio_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "power_semantics": power["summary"],
        "baseline_objective": BASELINE_OBJECTIVE,
        "target_literals": list(TARGET_LITERALS),
        "arm_count": len(arms),
        "total_alternative_count": len(all_records),
        "status_counts": dict(
            sorted(Counter(record["shared_binding"]["status"] for record in all_records).items())
        ),
        "optimal_candidate_count": len(optimal),
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "arm_summaries": [
            {
                "arm_index": int(arm["arm_index"]),
                "target": arm["target"],
                "alternative_count": int(arm["alternative_count"]),
                "status_counts": arm["status_counts"],
                "best_objective": min(
                    [
                        int(record["shared_binding"]["objective"])
                        for record in arm["candidate_records"]
                        if record["shared_binding"]["status"] == "OPTIMAL"
                    ],
                    default=None,
                ),
            }
            for arm in arms
        ],
        "best_objective": best_objective,
        "best_delta_from_pair": best_objective - BASELINE_OBJECTIVE,
        "best_third_move": {
            "literal": str(best["target"]["literal_key"]),
            "source_instance_id": str(best["target"]["source_instance_ids"][0]),
            "current_pose_idx": int(best["target"]["pose_idx"]),
            "replacement_pose_idx": int(best["pose_idx"]),
            "replacement_pose_id": str(best["pose_id"]),
            "anchor": json_safe(best["anchor"]),
            "same_footprint": bool(best["same_footprint"]),
            "candidate_solution_digest": str(best["candidate_solution_digest"]),
        },
        "best_shared_binding": best_detailed,
        "best_assignment_path": str(best_assignment_path.relative_to(ROOT)),
        "best_assignment_sha256": sha256_file(best_assignment_path),
        "best_layout_path": str(best_layout_path.relative_to(ROOT)),
        "best_layout_sha256": sha256_file(best_layout_path),
        "residual_partner_analysis": residual,
        "fourth_partner_ranking": fourth_ranking,
        "suggested_fourth_literal": fourth_ranking[0] if fourth_ranking else None,
        "routing": routing,
        "top_candidates": ranked[:30],
        "arm_checkpoint_paths": [
            str(arm_path(int(arm["arm_index"])).relative_to(ROOT)) for arm in arms
        ],
        "truth_boundary": (
            "Exhaustive alternatives for four selected third literals after a "
            "fixed successful pair and fixed outside geometry."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E017 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "total_alternative_count": result["total_alternative_count"],
                    "status_counts": result["status_counts"],
                    "baseline_objective": result["baseline_objective"],
                    "best_objective": result["best_objective"],
                    "best_delta": result["best_delta_from_pair"],
                    "best_third_move": result["best_third_move"],
                    "suggested_fourth": result["suggested_fourth_literal"],
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
            "schema": "zmd_zero_condition_e017_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        OUT.mkdir(parents=True, exist_ok=True)
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
