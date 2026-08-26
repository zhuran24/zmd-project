#!/usr/bin/env python3
"""E025: rebuild the objective-168 residual surface and compare the live beam."""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E025_live_beam_residual_surface/run-004"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
)
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E004_component_mismatch_atlas/run_e004.py"
)
E015_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E015_shared_binding_gradient/run_e015.py"
)
E013_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E013_residual_boundary_coverage/run_e013.py"
)
E022_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E022_residual_action_surface/run_e022.py"
)
E022_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E022_residual_action_surface/run-003/RESULT.json"
)
E024_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/RESULT.json"
)
E024_ARM = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/ARM.json"
)
E024_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/BEST_BRANCH_CHILD_ASSIGNMENT.json"
)
E024_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/BEST_BRANCH_CHILD_LAYOUT.json"
)
E019_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E019_beam_common_action/run-002/RESULT.json"
)
E023_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E023_common_action_path_dependence/run-001/RESULT.json"
)

EXPECTED_HASHES: dict[Path, str] = {
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E022_RUNNER: "060440bd8b5ba2cba7647987fa30bed7b08e8d8ca155d9ddcaed6cd276e09507",
    E022_RESULT: "d43463034c81d1ce4185f76312a25173e880da9744bcc5bd2023e4610a1e6e83",
    E024_RESULT: "a0a69a8c0f9c7f59d8924f9f13e0e277fe5f254a35aeaeb34c6c721becd4d17f",
    E024_ARM: "570030b98191cf1f088484783404ce8ec32d026cf50b4ce467eac13e21c4ad76",
    E024_ASSIGNMENT: "4f49e6dc8aaaf8e677596cd631f0eb34fc735612a4ff5a3e09dbb50836633018",
    E024_LAYOUT: "c05ae6030d9ee8154cb3074b980ba34c438696ddf7aed2521ea1ba680ddb23ba",
    E019_RESULT: "89f37256e282a7f716092d477495d8e6ec715015d32632c97ca133b0ce40d3e7",
    E023_RESULT: "c064e9918b5e8d7cfe422868d1c4e46b9df64b7d0cf22ebab05fb022391caffc",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
}

RETIRED_UNARY_ACTIONS = {
    "mandatory::group::manufacturing_6x4::grinder_fine_buckwheat::16::7754": {
        "reason": "worsened every tested E019 and E023 parent by exactly two",
        "e019_result_sha256": EXPECTED_HASHES[E019_RESULT],
        "e023_result_sha256": EXPECTED_HASHES[E023_RESULT],
    }
}


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
        raise RuntimeError("E025 must run on research/main")
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual}")
    e022 = load_json(E022_RESULT)
    e024 = load_json(E024_RESULT)
    e019 = load_json(E019_RESULT)
    e023 = load_json(E023_RESULT)
    if e022.get("verdict") != "RESIDUAL_ACTION_SURFACE_SHARED_PORTFOLIO":
        raise RuntimeError("E022 verdict drift")
    if e024.get("verdict") != "BRANCH_SPECIFIC_LEADER_IMPROVES":
        raise RuntimeError("E024 verdict drift")
    if int(e024["best_child"]["objective"]) != 168:
        raise RuntimeError("E024 objective drift")
    if e019.get("verdict") != "COMMON_ACTION_BRANCH_INVARIANT":
        raise RuntimeError("E019 verdict drift")
    if e023.get("verdict") != "COMMON_COVERAGE_ACTION_RETIRED_SECOND_REJECTION":
        raise RuntimeError("E023 verdict drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def candidate_action(row: Mapping[str, Any]) -> bool:
    literal = str(row["literal_key"])
    if literal in RETIRED_UNARY_ACTIONS:
        return False
    if str(row.get("facility_type", "")) == "boundary_storage_port":
        return False
    return str(row.get("kind", "")) in {
        "mandatory_group_pose",
        "optional_pose",
    }


def build_objective_168_surface(
    *,
    e001: Any,
    e004: Any,
    e013: Any,
    e015: Any,
    e022: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = load_json(E024_RESULT)
    arm = load_json(E024_ARM)
    assignment = load_json(E024_ASSIGNMENT)
    solution = assignment.get("solution")
    if not isinstance(solution, Mapping) or len(solution) != 319:
        raise RuntimeError("E024 assignment solution drift")
    if e022.stable_digest(solution) != str(result["best_child"]["placement_digest"]):
        raise RuntimeError("E024 assignment placement digest drift")
    matching = [
        dict(record)
        for record in arm["candidate_records"]
        if str(record["candidate_solution_digest"])
        == str(result["best_child"]["placement_digest"])
    ]
    if len(matching) != 1:
        raise RuntimeError(f"E024 best child lookup drift: {len(matching)}")
    if int(matching[0]["shared_binding"]["objective"]) != 168:
        raise RuntimeError("E024 arm objective drift")

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    target_digest = str(result["best_child"]["binding_selection_digest"])
    replay_attempts: list[dict[str, Any]] = []
    shared: dict[str, Any] | None = None
    for attempt in range(1, 9):
        replay = e015.solve_shared_mismatch(
            solution=solution,
            inputs=inputs,
            e004=e004,
            random_seed=264001,
            include_boundaries=False,
        )
        digest = str(replay.get("selection_digest", ""))
        replay_attempts.append(
            {
                "attempt": attempt,
                "status": replay.get("status"),
                "objective": replay.get("objective"),
                "selection_digest": digest,
                "matches_frozen_digest": digest == target_digest,
                "per_commodity_digest": e022.stable_digest(
                    replay.get("per_commodity", {})
                ),
                "ore_pair": {
                    "blue_iron_ore": replay.get("per_commodity", {}).get(
                        "blue_iron_ore"
                    ),
                    "source_ore": replay.get("per_commodity", {}).get(
                        "source_ore"
                    ),
                },
            }
        )
        if replay.get("status") != "OPTIMAL" or int(replay["objective"]) != 168:
            raise RuntimeError("E024 detailed endpoint replay objective drift")
        if digest == target_digest:
            if json_safe(replay["per_commodity"]) != json_safe(
                result["best_child"]["per_commodity"]
            ):
                raise RuntimeError(
                    "E024 matching selection digest has per-commodity drift"
                )
            shared = dict(replay)
            break

    fallback_used = shared is None
    if shared is None:
        shared = dict(matching[0]["shared_binding"])
        if shared.get("status") != "OPTIMAL" or int(shared["objective"]) != 168:
            raise RuntimeError("E024 materialized arm endpoint drift")
        if json_safe(shared["per_commodity"]) != json_safe(
            result["best_child"]["per_commodity"]
        ):
            raise RuntimeError("E024 materialized arm endpoint vector drift")

    candidate_payload = load_json(
        HISTORY_ROOT / "data/preprocessed/candidate_placements.json"
    )
    facility_pools = candidate_payload.get("facility_pools")
    if not isinstance(facility_pools, Mapping):
        raise RuntimeError("candidate placement pool drift")
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(mandatory, list):
        raise RuntimeError("mandatory instances drift")
    group_by_instance = e013.group_mapping(mandatory)

    from src.models.routing_binding_context import build_routing_binding_context

    routing_context = build_routing_binding_context(
        solution,
        facility_pools,
        70,
        70,
    )
    shared["mismatch_boundaries"] = {
        commodity: [
            e004.boundary_profile(
                component=int(component),
                routing_context=routing_context,
                solution=solution,
            )
            for component in shared["selected_components"][commodity][
                "mismatch_components"
            ]
        ]
        for commodity in sorted(shared["selected_components"])
    }
    state = {
        "class_index": 168,
        "retained_state": {
            "objective": 168,
            "placement_digest": result["best_child"]["placement_digest"],
            "binding_selection_digest": result["best_child"][
                "binding_selection_digest"
            ],
            "free_cell_set_digest": result["best_child"]["morphology"][
                "free_cell_set_digest"
            ],
            "source": "E024 best branch-specific child",
        },
        "solution": solution,
        "shared_binding": shared,
    }
    surface = e022.build_state_surface(
        state=state,
        group_by_instance=group_by_instance,
        facility_pools=facility_pools,
        e013=e013,
    )
    endpoint_audit = {
        "frozen_summary_selection_digest": target_digest,
        "materialized_arm_selection_digest": str(
            matching[0]["shared_binding"]["selection_digest"]
        ),
        "replay_attempts": replay_attempts,
        "replay_distinct_selection_digest_count": len(
            {row["selection_digest"] for row in replay_attempts}
        ),
        "recovered_frozen_endpoint": not fallback_used,
        "fallback_to_materialized_arm_endpoint": fallback_used,
        "selected_endpoint_digest": str(shared["selection_digest"]),
        "statement": (
            "The E024 summary persisted only a selection digest. Parallel CP-SAT "
            "replay can return another optimum under the same seed, so E025 retries "
            "until the frozen digest is recovered; if unavailable, it explicitly "
            "adopts the fully materialized ARM endpoint instead."
        ),
    }
    return surface, endpoint_audit


def run() -> dict[str, Any]:
    identity = verify_identity()
    started = time.monotonic()
    e001 = import_module("zmd_e025_e001", E001_RUNNER)
    e004 = import_module("zmd_e025_e004", E004_RUNNER)
    e013 = import_module("zmd_e025_e013", E013_RUNNER)
    e015 = import_module("zmd_e025_e015", E015_RUNNER)
    e022 = import_module("zmd_e025_e022", E022_RUNNER)

    surface_168, endpoint_audit = build_objective_168_surface(
        e001=e001,
        e004=e004,
        e013=e013,
        e015=e015,
        e022=e022,
    )
    old = load_json(E022_RESULT)
    parents_173 = [
        dict(surface)
        for surface in old["state_surfaces"]
        if int(surface["class_index"]) in {1, 2, 3}
    ]
    if len(parents_173) != 3:
        raise RuntimeError("E025 live parent surface count drift")
    live_surfaces = [surface_168, *parents_173]
    comparison = e022.compare_surfaces(live_surfaces)

    robust_candidates = [
        dict(row)
        for row in comparison["robust_common_ranking"]
        if candidate_action(row)
    ]
    specific_candidates = [
        dict(row)
        for row in surface_168["top_literals"]
        if candidate_action(row)
    ]
    if not robust_candidates or not specific_candidates:
        verdict = "LIVE_BEAM_UNARY_PORTFOLIO_EXHAUSTED"
        selected_common = None
        selected_specific = None
    else:
        selected_common = robust_candidates[0]
        selected_specific = next(
            (
                row
                for row in specific_candidates
                if str(row["literal_key"])
                != str(selected_common["literal_key"])
            ),
            None,
        )
        verdict = "LIVE_BEAM_RESIDUAL_SURFACE_SHARED_PORTFOLIO"

    return {
        "schema": "zmd_zero_condition_e025_live_beam_residual_surface_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "live_beam": {
            "objectives": [168, 173, 173, 173],
            "surface_class_indices": [
                int(surface["class_index"]) for surface in live_surfaces
            ],
            "state_count": len(live_surfaces),
        },
        "objective_168_endpoint_audit": endpoint_audit,
        "objective_168_surface": surface_168,
        "comparison": comparison,
        "action_ledger": {
            "retired_unary_actions": RETIRED_UNARY_ACTIONS,
            "retired_action_still_raw_leader": (
                str(surface_168["top_literals"][0]["literal_key"])
                in RETIRED_UNARY_ACTIONS
            ),
            "eligible_robust_common_candidates": robust_candidates[:20],
            "eligible_objective_168_candidates": specific_candidates[:20],
        },
        "decision_reading": {
            "selected_common_action": selected_common,
            "selected_objective_168_specific_action": selected_specific,
            "next_test": (
                "cross-state exact replay of the selected common action"
                if selected_common is not None
                else "simultaneous two-pose or pose-binding neighborhood"
            ),
        },
        "truth_boundary": (
            "Residual mismatch-boundary coverage over one frozen objective-168 "
            "binding endpoint and three frozen objective-173 endpoints. Coverage "
            "selects experiments; it is not continuation value or a repair proof."
        ),
        "routing_solver_run": False,
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E025 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        decision = result["decision_reading"]
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "leader_by_class": result["comparison"]["leader_by_class"],
                    "common_top10_count": result["comparison"][
                        "common_top10_count"
                    ],
                    "selected_common_action": (
                        decision["selected_common_action"]["literal_key"]
                        if decision["selected_common_action"] is not None
                        else None
                    ),
                    "selected_objective_168_specific_action": (
                        decision["selected_objective_168_specific_action"][
                            "literal_key"
                        ]
                        if decision["selected_objective_168_specific_action"]
                        is not None
                        else None
                    ),
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
            "schema": "zmd_zero_condition_e025_failure_v1",
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
