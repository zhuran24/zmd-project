#!/usr/bin/env python3
"""E016: exhaust the first evidence-derived two-literal placement neighborhood."""

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
OUT = ROOT / "research_lab/local/zero_condition/E016_coupled_pair_search/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E013_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E013_residual_boundary_coverage/run-004/RESULT.json"
)
E015_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E015_shared_binding_gradient/run-001/RESULT.json"
)
E015_BEST_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E015_shared_binding_gradient/run-001/BEST_ASSIGNMENT.json"
)
E015_BEST_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E015_shared_binding_gradient/run-001/BEST_LAYOUT.json"
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
E014_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E014_fixed_outside_mobility/run_e014.py"
)
E015_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E015_shared_binding_gradient/run_e015.py"
)

EXPECTED_HASHES: dict[Path, str] = {
    E013_RESULT: "99c029fe71c2835bd5d2f5cd16d00f324856d70ce305278e2bb3aa944cbf6fd1",
    E015_RESULT: "d3a4a054a62ab4731a2b6f67b609b1101d4595eb097a031ec5edec11b4b95f9c",
    E015_BEST_ASSIGNMENT: "b1923ddcdb7fb1045a5cbb4abd829701325ef0b2a15ed968c9960b81a385a669",
    E015_BEST_LAYOUT: "e2fa7e97c74bf2e335936c38696080e33a234aa6fa41f4502b7ae8a2c42e3cb9",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
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
    "EXACT_MASTER_RANDOM_SEED": "261600",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

FIRST_LITERAL = "mandatory::group::manufacturing_3x3::crusher_sandleaf::3::2186"
FIRST_REPLACEMENT_POSE = 15830
SECOND_LITERAL = "mandatory::group::manufacturing_3x3::crusher_source::4::6191"
BASELINE_OBJECTIVE = 186


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
        raise RuntimeError("E016 must run on research/main")
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
    result = load_json(E015_RESULT)
    if int(result["best_objective"]) != BASELINE_OBJECTIVE:
        raise RuntimeError("E015 best objective drift")
    pair = result["suggested_pair"]
    if (
        str(pair["first_literal"]) != FIRST_LITERAL
        or int(pair["first_replacement_pose_idx"]) != FIRST_REPLACEMENT_POSE
        or str(pair["second_literal"]) != SECOND_LITERAL
    ):
        raise RuntimeError(f"E015 suggested pair drift: {pair}")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output("status", "--porcelain=v1", "--untracked-files=no"),
    }


def load_first_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E015_BEST_ASSIGNMENT)
    layout = load_json(E015_BEST_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E015 best assignment/layout structure is invalid")
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
        raise RuntimeError("E015 best assignment and layout disagree")
    moved = solution.get("crusher_sandleaf_005")
    if moved is None or int(moved["pose_idx"]) != FIRST_REPLACEMENT_POSE:
        raise RuntimeError("E015 first move is absent from the best assignment")
    return solution


def target_details() -> dict[str, Any]:
    e013 = load_json(E013_RESULT)
    portfolio = next(
        row
        for row in e013["max_coverage_by_literal_budget"]
        if int(row["budget"]) == 16
    )["selected_literal_details"]
    target = next(
        row for row in portfolio if str(row["literal_key"]) == SECOND_LITERAL
    )
    if int(target["pose_idx"]) != 6191:
        raise RuntimeError("E016 second target pose drift")
    return dict(target)


def residual_third_partner(
    *,
    analysis: Mapping[str, Any],
) -> dict[str, Any]:
    ranking = [
        row
        for row in analysis["partner_ranking"]
        if str(row["literal_key"]) not in {FIRST_LITERAL, SECOND_LITERAL}
    ]
    return {
        "partner_ranking_excluding_pair": ranking,
        "suggested_third_literal": ranking[0] if ranking else None,
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e001 = import_module("zmd_e016_e001", E001_RUNNER)
    e002 = import_module("zmd_e016_e002", E002_RUNNER)
    e004 = import_module("zmd_e016_e004", E004_RUNNER)
    e014 = import_module("zmd_e016_e014", E014_RUNNER)
    e015 = import_module("zmd_e016_e015", E015_RUNNER)
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    first_solution = load_first_solution()
    occupied, _owner_by_cell = e014.base_occupancy(
        first_solution,
        inputs["pools"],
    )
    selected_poles = {
        int(row["pose_idx"])
        for row in first_solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)
    if not e014.all_powered_facilities_covered(
        solution=first_solution,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    ):
        raise RuntimeError("E015 best solution fails reconstructed power semantics")

    target = target_details()
    alternatives = e014.enumerate_alternatives(
        target=target,
        base_solution=first_solution,
        pools=inputs["pools"],
        occupied=occupied,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    )
    records: list[dict[str, Any]] = []
    for index, candidate in enumerate(alternatives, 1):
        solution = candidate["solution"]
        try:
            shared = e015.solve_shared_mismatch(
                solution=solution,
                inputs=inputs,
                e004=e004,
                random_seed=266000 + index,
                include_boundaries=False,
            )
        except RuntimeError as exc:
            if "empty binding domain" not in str(exc):
                raise
            shared = {
                "status": "PORT_DOMAIN_EMPTY",
                "detail": str(exc),
                "objective": None,
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
        if index % 20 == 0:
            print(
                json.dumps(
                    {
                        "event": "E016_PROGRESS",
                        "candidate": index,
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

    optimal = [row for row in records if row["shared_binding"]["status"] == "OPTIMAL"]
    ranked = sorted(
        optimal,
        key=lambda row: (
            int(row["shared_binding"]["objective"]),
            -len(row["shared_binding"]["zero_mismatch_commodities"]),
            -int(row["shared_binding"]["filtered_binding_option_count"]),
            int(row["shared_binding"]["morphology"]["free_component_count"]),
            int(row["pose_idx"]),
        ),
    )
    if not ranked:
        raise RuntimeError("E016 has no base-binding-feasible pair candidate")
    best = ranked[0]
    best_candidate = next(
        candidate
        for candidate in alternatives
        if int(candidate["pose_idx"]) == int(best["pose_idx"])
        and stable_digest(candidate["solution"])
        == str(best["candidate_solution_digest"])
    )
    best_solution = best_candidate["solution"]
    best_detailed = e015.solve_shared_mismatch(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        random_seed=267999,
        include_boundaries=True,
    )
    if (
        best_detailed["status"] != "OPTIMAL"
        or int(best_detailed["objective"])
        != int(best["shared_binding"]["objective"])
    ):
        raise RuntimeError("E016 best pair detailed replay drift")

    residual = e015.residual_partner_ranking(
        best_solution=best_solution,
        best_record=best_detailed,
        moved_literal=FIRST_LITERAL,
        inputs=inputs,
        e013=import_module(
            "zmd_e016_e013",
            ROOT
            / "research_lab/campaigns/zero_condition/experiments/E013_residual_boundary_coverage/run_e013.py",
        ),
    )
    third = residual_third_partner(analysis=residual)

    best_assignment_path = OUT / "BEST_PAIR_ASSIGNMENT.json"
    best_layout_path = OUT / "BEST_PAIR_LAYOUT.json"
    dump_exclusive(
        best_assignment_path,
        {
            "schema": "zmd_zero_condition_e016_best_pair_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "shared_mismatch_objective": int(best_detailed["objective"]),
            "first_literal": FIRST_LITERAL,
            "first_replacement_pose_idx": FIRST_REPLACEMENT_POSE,
            "second_literal": SECOND_LITERAL,
            "second_replacement_pose_idx": int(best["pose_idx"]),
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

    objective_distribution = Counter(
        int(row["shared_binding"]["objective"]) for row in optimal
    )
    best_objective = int(best_detailed["objective"])
    if best_objective == 0:
        verdict = "PAIR_COMPONENT_FEASIBLE_CANDIDATE"
    elif best_objective < BASELINE_OBJECTIVE:
        verdict = "PAIR_SHARED_MISMATCH_IMPROVEMENT"
    else:
        verdict = "PAIR_NO_IMPROVEMENT"
    return {
        "schema": "zmd_zero_condition_e016_coupled_pair_search_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "power_semantics": power["summary"],
        "first_move": {
            "literal": FIRST_LITERAL,
            "replacement_pose_idx": FIRST_REPLACEMENT_POSE,
            "baseline_shared_objective": BASELINE_OBJECTIVE,
            "solution_digest": stable_digest(first_solution),
        },
        "second_target": target,
        "alternative_count": len(alternatives),
        "status_counts": dict(
            sorted(Counter(row["shared_binding"]["status"] for row in records).items())
        ),
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "optimal_candidate_count": len(optimal),
        "best_objective": best_objective,
        "best_delta_from_first_move": best_objective - BASELINE_OBJECTIVE,
        "best_second_pose": {
            "pose_idx": int(best["pose_idx"]),
            "pose_id": str(best["pose_id"]),
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
        "third_partner_analysis": third,
        "routing": routing,
        "candidate_records": records,
        "top_candidates": ranked[:25],
        "truth_boundary": (
            "Exhaustive second-pose alternatives after one frozen first move and "
            "fixed outside geometry. A positive shared mismatch is not routing "
            "infeasibility or a global no-ghost theorem."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E016 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "alternative_count": result["alternative_count"],
                    "status_counts": result["status_counts"],
                    "baseline_objective": BASELINE_OBJECTIVE,
                    "best_objective": result["best_objective"],
                    "best_delta": result["best_delta_from_first_move"],
                    "best_second_pose": result["best_second_pose"],
                    "suggested_third": result["third_partner_analysis"][
                        "suggested_third_literal"
                    ],
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
            "schema": "zmd_zero_condition_e016_failure_v1",
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
