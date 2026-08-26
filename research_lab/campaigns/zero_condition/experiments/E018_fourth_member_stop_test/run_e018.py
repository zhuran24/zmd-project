#!/usr/bin/env python3
"""E018: one final fourth-member portfolio before a multi-state beam."""

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
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E018_fourth_member_stop_test/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E013_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E013_residual_boundary_coverage/run-004/RESULT.json"
)
E017_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E017_third_member_portfolio/run-001/RESULT.json"
)
E017_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E017_third_member_portfolio/run-001/BEST_TRIPLE_ASSIGNMENT.json"
)
E017_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E017_third_member_portfolio/run-001/BEST_TRIPLE_LAYOUT.json"
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
E017_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E017_third_member_portfolio/run_e017.py"
)

EXPECTED_HASHES: dict[Path, str] = {
    E013_RESULT: "99c029fe71c2835bd5d2f5cd16d00f324856d70ce305278e2bb3aa944cbf6fd1",
    E017_RESULT: "08626489854032d7a25097b6b2f1cfacb95444a14c680cee6e7886134f45588d",
    E017_ASSIGNMENT: "d3c8aed026ddefefdf8da43a3096fac26e89703330dea0d047bc3f9172fd5768",
    E017_LAYOUT: "1631b107bfd481cba6fcbfeb59779fe729840d6adf31ecd1c994dc0741976926",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E017_RUNNER: "106d7ee8830d3a45bf4115e064e65e059fdd86c4bd4b5c2acddaff55e203a2e0",
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
    "EXACT_MASTER_RANDOM_SEED": "261800",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

BASELINE_OBJECTIVE = 176
USED_LITERALS = {
    "mandatory::group::manufacturing_3x3::crusher_sandleaf::3::2186",
    "mandatory::group::manufacturing_3x3::crusher_source::4::6191",
    "mandatory::group::manufacturing_3x3::crusher_source::4::6073",
}
TARGET_LITERALS = (
    "mandatory::group::manufacturing_6x4::grinder_fine_buckwheat::16::7754",
    "mandatory::group::manufacturing_3x3::refinery_blue_iron::7::5279",
    "mandatory::group::manufacturing_3x3::refinery_blue_iron::7::5343",
    "mandatory::group::manufacturing_3x3::crusher_source::4::6125",
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
        raise RuntimeError("E018 must run on research/main")
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
    if int(load_json(E017_RESULT)["best_objective"]) != BASELINE_OBJECTIVE:
        raise RuntimeError("E017 best objective drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output("status", "--porcelain=v1", "--untracked-files=no"),
    }


def load_triple_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E017_ASSIGNMENT)
    layout = load_json(E017_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E017 triple assignment/layout structure is invalid")
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
        raise RuntimeError("E017 triple assignment and layout disagree")
    expected = {
        "crusher_sandleaf_005": 15830,
        "crusher_source_015": 6102,
        "crusher_source_012": 6179,
    }
    for instance_id, pose_idx in expected.items():
        if int(solution[instance_id]["pose_idx"]) != pose_idx:
            raise RuntimeError(f"E017 frozen move drift: {instance_id}")
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
        raise RuntimeError(f"E018 targets absent from E013: {missing}")
    return [by_key[key] for key in TARGET_LITERALS]


def arm_path(index: int) -> Path:
    return OUT / f"ARM_{index:02d}.json"


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e001 = import_module("zmd_e018_e001", E001_RUNNER)
    e002 = import_module("zmd_e018_e002", E002_RUNNER)
    e004 = import_module("zmd_e018_e004", E004_RUNNER)
    e013 = import_module("zmd_e018_e013", E013_RUNNER)
    e014 = import_module("zmd_e018_e014", E014_RUNNER)
    e015 = import_module("zmd_e018_e015", E015_RUNNER)
    e017 = import_module("zmd_e018_e017", E017_RUNNER)
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    triple_solution = load_triple_solution()
    occupied, _owner_by_cell = e014.base_occupancy(
        triple_solution,
        inputs["pools"],
    )
    selected_poles = {
        int(row["pose_idx"])
        for row in triple_solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)
    if not e014.all_powered_facilities_covered(
        solution=triple_solution,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    ):
        raise RuntimeError("E017 triple fails reconstructed power semantics")

    targets = target_manifest()
    arms: list[dict[str, Any]] = []
    for index, target in enumerate(targets, 1):
        path = arm_path(index)
        if path.exists():
            arm = load_json(path)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E018 arm checkpoint: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E018_ARM_START",
                        "arm": index,
                        "literal": target["literal_key"],
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            arm = e017.evaluate_arm(
                index=index,
                target=target,
                pair_solution=triple_solution,
                occupied=occupied,
                selected_poles=selected_poles,
                inputs=inputs,
                power=power,
                e004=e004,
                e014=e014,
                e015=e015,
                runner_sha256=runner_sha256,
            )
            arm["schema"] = "zmd_zero_condition_e018_arm_v1"
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
                    "event": "E018_ARM_DONE",
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
        raise RuntimeError("E018 has no base-binding-feasible candidate")
    best = ranked[0]
    best_arm = next(
        arm for arm in arms if int(arm["arm_index"]) == int(best["arm_index"])
    )
    best_solution = e017.reconstruct_candidate(
        arm=best_arm,
        record=best,
        pair_solution=triple_solution,
        inputs=inputs,
        e014=e014,
    )
    best_detailed = e015.solve_shared_mismatch(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        random_seed=271999,
        include_boundaries=True,
    )
    if (
        best_detailed["status"] != "OPTIMAL"
        or int(best_detailed["objective"])
        != int(best["shared_binding"]["objective"])
    ):
        raise RuntimeError("E018 best detailed replay drift")

    residual = e015.residual_partner_ranking(
        best_solution=best_solution,
        best_record=best_detailed,
        moved_literal=str(best["target"]["literal_key"]),
        inputs=inputs,
        e013=e013,
    )
    used = set(USED_LITERALS) | {str(best["target"]["literal_key"])}
    next_ranking = [
        row
        for row in residual["partner_ranking"]
        if str(row["literal_key"]) not in used
    ]

    best_assignment_path = OUT / "BEST_FOURTH_ASSIGNMENT.json"
    best_layout_path = OUT / "BEST_FOURTH_LAYOUT.json"
    dump_exclusive(
        best_assignment_path,
        {
            "schema": "zmd_zero_condition_e018_best_fourth_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "shared_mismatch_objective": int(best_detailed["objective"]),
            "fourth_literal": str(best["target"]["literal_key"]),
            "fourth_replacement_pose_idx": int(best["pose_idx"]),
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
        verdict = "FOURTH_COMPONENT_FEASIBLE_CANDIDATE"
    elif best_objective < BASELINE_OBJECTIVE:
        verdict = "FOURTH_SHARED_MISMATCH_IMPROVEMENT_BEAM_NEXT"
    else:
        verdict = "SEQUENTIAL_LINEAGE_SATURATED_BEAM_NEXT"
    objective_distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal
    )
    e017_result = load_json(E017_RESULT)
    beam_seed_descriptors = [
        {
            "arm_index": int(record["arm_index"]),
            "literal": str(record["target"]["literal_key"]),
            "replacement_pose_idx": int(record["pose_idx"]),
            "objective": int(record["shared_binding"]["objective"]),
            "free_cell_set_digest": str(
                record["shared_binding"]["morphology"]["free_cell_set_digest"]
            ),
            "selection_digest": str(record["shared_binding"]["selection_digest"]),
        }
        for record in e017_result["top_candidates"]
        if int(record["shared_binding"]["objective"]) == BASELINE_OBJECTIVE
    ][:12]
    return {
        "schema": "zmd_zero_condition_e018_fourth_member_stop_test_v1",
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
        "best_delta_from_triple": best_objective - BASELINE_OBJECTIVE,
        "best_fourth_move": {
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
        "next_partner_ranking": next_ranking,
        "routing": routing,
        "beam_transition": {
            "decision": (
                "ROUTING_NEXT"
                if best_objective == 0
                else "TRANSITION_TO_MULTI_STATE_BEAM"
            ),
            "reason": (
                "The controlled fourth round is the predeclared stop point for "
                "single-line sequential assembly; E017 already produced twelve "
                "equal-score triples across distinct families."
            ),
            "seed_descriptors": beam_seed_descriptors,
            "seed_count": len(beam_seed_descriptors),
        },
        "top_candidates": ranked[:30],
        "arm_checkpoint_paths": [
            str(arm_path(int(arm["arm_index"])).relative_to(ROOT)) for arm in arms
        ],
        "truth_boundary": (
            "Exhaustive alternatives for four selected fourth literals after one "
            "representative fixed triple. Other tied triples remain live beam states."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E018 outputs under {OUT}")
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
                    "best_delta": result["best_delta_from_triple"],
                    "best_fourth_move": result["best_fourth_move"],
                    "beam_transition": result["beam_transition"],
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
            "schema": "zmd_zero_condition_e018_failure_v1",
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
