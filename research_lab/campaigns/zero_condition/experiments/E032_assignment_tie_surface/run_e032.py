#!/usr/bin/env python3
"""E032: compare residual assignment surfaces of the two E031 objective-161 states."""

from __future__ import annotations

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
OUT = ROOT / "research_lab/local/zero_condition/E032_assignment_tie_surface/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
SECOND_ASSIGNMENT_PATH = OUT / "SECOND_ASSIGNMENT.json"
SECOND_LAYOUT_PATH = OUT / "SECOND_LAYOUT.json"
SECOND_ENDPOINT_PATH = OUT / "SECOND_ENDPOINT.json"

E031_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/RESULT.json"
)
E031_ARM = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/ARM_3x3.json"
)
E031_BEST_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/BEST_ASSIGNMENT.json"
)
E031_BEST_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/BEST_ENDPOINT.json"
)
E030_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E030_operation_swap_portfolio/run-001/BEST_SWAP_ASSIGNMENT.json"
)
E030_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E030_operation_swap_portfolio/run-001/BEST_SWAP_ENDPOINT.json"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
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
E022_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E022_residual_action_surface/run_e022.py"
)
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E027_final_unary_discriminator/run_e027.py"
)
E029_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E029_operation_assignment_surface/run_e029.py"
)
E031_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E031_bounded_assignment_neighborhood/run_e031.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "263200",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E031_RESULT: "a6efad78e382133b0b5b2492bbb048e6e15726294ec3940c0a777bceecd791b2",
    E031_ARM: "e097a684e89dd1e70fcc2bdadcd64ef9aa3e02bfe14be6fdeeaf77f3f7c3defa",
    E031_BEST_ASSIGNMENT: "f34bcc394835730ac3a6925fcb7ac415d2cc57f79680af0372e4f4ab394b4dcf",
    E031_BEST_ENDPOINT: "f300d618089f92fad5b55044204c4946a911702db32334714f49a0a952703087",
    E030_ASSIGNMENT: "a6370b2d5fb51416ea9c0825e19c5a526c6b33fa50ccb3a4c52ed3e570d1cd7f",
    E030_ENDPOINT: "6f0bcec132a08159bffb5bb655f4378cb70b71f6398280941d835305022f1b23",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E022_RUNNER: "060440bd8b5ba2cba7647987fa30bed7b08e8d8ca155d9ddcaed6cd276e09507",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    E029_RUNNER: "08672e533d4d73e50a411703c41017b058521ff2a9d4e6f53c2235343cef46bf",
    E031_RUNNER: "ba35d569dc1a514da83b46721cb53c3f25386b2d776c70ac4cfae7f7c4d29b18",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
}

OBJECTIVE = 161
SECOND_CANDIDATE_INDEX = 8


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
        raise RuntimeError("E032 must run on research/main")
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
    result = load_json(E031_RESULT)
    if result.get("verdict") != "BOUNDED_ASSIGNMENT_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E031 trigger verdict drift")
    ties = [
        row
        for row in result["top_candidates"]
        if int(row["shared_binding"]["objective"]) == OBJECTIVE
    ]
    if len(ties) != 2:
        raise RuntimeError(f"E031 tie count drift: {len(ties)}")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def add_boundaries(
    *,
    endpoint: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Any],
    e004: Any,
) -> dict[str, Any]:
    shared = dict(endpoint)
    if "mismatch_boundaries" in shared:
        return shared
    from src.models.routing_binding_context import build_routing_binding_context

    routing_context = build_routing_binding_context(solution, pools, 70, 70)
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
    return shared


def build_surface(
    *,
    label: int,
    solution: Mapping[str, Mapping[str, Any]],
    endpoint: Mapping[str, Any],
    pools: Mapping[str, Any],
    group_by_instance: Mapping[str, str],
    e013: Any,
    e022: Any,
) -> dict[str, Any]:
    state = {
        "class_index": label,
        "retained_state": {
            "objective": OBJECTIVE,
            "placement_digest": stable_digest(solution),
            "binding_selection_digest": endpoint["selection_digest"],
            "free_cell_set_digest": endpoint["morphology"]["free_cell_set_digest"],
            "source": f"E031 objective-161 state {label}",
        },
        "solution": solution,
        "shared_binding": endpoint,
    }
    return e022.build_state_surface(
        state=state,
        group_by_instance=group_by_instance,
        facility_pools=pools,
        e013=e013,
    )


def swap_surface(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    endpoint: Mapping[str, Any],
    pools: Mapping[str, Any],
    group_by_instance: Mapping[str, str],
    e013: Any,
    e029: Any,
) -> dict[str, Any]:
    e029.OBJECTIVE = OBJECTIVE
    observations, literals, observation_ids_by_literal = e029.build_incidence(
        solution=solution,
        endpoint=endpoint,
        pools=pools,
        group_by_instance=group_by_instance,
        e013=e013,
    )
    all_swaps, portfolio = e029.swap_candidates(
        literals=literals,
        observation_ids_by_literal=observation_ids_by_literal,
    )
    return {
        "candidate_pair_count": len(all_swaps),
        "eligible_literal_count": len(
            {row["left_literal"] for row in all_swaps}
            | {row["right_literal"] for row in all_swaps}
        ),
        "top_raw_pairs": json_safe(all_swaps[:40]),
        "selected_portfolio": json_safe(portfolio),
        "portfolio_digest": stable_digest(portfolio),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e001 = import_module("zmd_e032_e001", E001_RUNNER)
    e004 = import_module("zmd_e032_e004", E004_RUNNER)
    e013 = import_module("zmd_e032_e013", E013_RUNNER)
    e014 = import_module("zmd_e032_e014", E014_RUNNER)
    e015 = import_module("zmd_e032_e015", E015_RUNNER)
    e022 = import_module("zmd_e032_e022", E022_RUNNER)
    e027 = import_module("zmd_e032_e027", E027_RUNNER)
    e029 = import_module("zmd_e032_e029", E029_RUNNER)
    e031 = import_module("zmd_e032_e031", E031_RUNNER)

    parent, _parent_endpoint, pools, mandatory, _generic = e031.load_parent()
    result = load_json(E031_RESULT)
    neighborhood = next(
        row
        for row in result["neighborhoods"]
        if str(row["facility_type"]) == "manufacturing_3x3"
    )
    arm = load_json(E031_ARM)
    second_record = next(
        row
        for row in arm["records"]
        if int(row["candidate_index"]) == SECOND_CANDIDATE_INDEX
    )
    if int(second_record["shared_binding"]["objective"]) != OBJECTIVE:
        raise RuntimeError("E032 second candidate objective drift")
    second_solution = e031.realize_assignment(
        parent=parent,
        neighborhood=neighborhood,
        operation_by_destination=second_record["operation_by_destination"],
        pools=pools,
        e014=e014,
    )
    if stable_digest(second_solution) != str(
        second_record["candidate_solution_digest"]
    ):
        raise RuntimeError("E032 second candidate placement reconstruction drift")

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    target_digest = str(second_record["shared_binding"]["selection_digest"])
    attempts: list[dict[str, Any]] = []
    second_endpoint: dict[str, Any] | None = None
    for attempt in range(1, 9):
        endpoint = e027.materialize_shared_endpoint(
            solution=second_solution,
            inputs=inputs,
            e004=e004,
            e015=e015,
            random_seed=272008,
        )
        digest = str(endpoint["selection_digest"])
        attempts.append(
            {
                "attempt": attempt,
                "selection_digest": digest,
                "matches_frozen_digest": digest == target_digest,
                "objective": endpoint["objective"],
            }
        )
        if int(endpoint["objective"]) != OBJECTIVE:
            raise RuntimeError("E032 second endpoint objective drift")
        if digest == target_digest:
            second_endpoint = endpoint
            break
    fully_materialized = second_endpoint is not None
    if second_endpoint is None:
        second_endpoint = add_boundaries(
            endpoint=second_record["shared_binding"],
            solution=second_solution,
            pools=pools,
            e004=e004,
        )
        second_endpoint["materialization_status"] = (
            "COMPACT_FROZEN_ENDPOINT_SELECTION_NOT_REPRODUCED"
        )
    else:
        second_endpoint["materialization_status"] = "FULL_ENDPOINT_REPRODUCED"

    dump_exclusive(
        SECOND_ASSIGNMENT_PATH,
        {
            "schema": "zmd_zero_condition_e032_second_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "objective": OBJECTIVE,
            "candidate_index": SECOND_CANDIDATE_INDEX,
            "operation_by_destination": second_record["operation_by_destination"],
            "solution": second_solution,
        },
    )
    dump_exclusive(SECOND_LAYOUT_PATH, e001.solution_layout(second_solution))
    dump_exclusive(SECOND_ENDPOINT_PATH, second_endpoint)

    best_solution = load_json(E031_BEST_ASSIGNMENT)["solution"]
    best_endpoint = load_json(E031_BEST_ENDPOINT)
    best_endpoint = add_boundaries(
        endpoint=best_endpoint,
        solution=best_solution,
        pools=pools,
        e004=e004,
    )
    second_endpoint = add_boundaries(
        endpoint=second_endpoint,
        solution=second_solution,
        pools=pools,
        e004=e004,
    )
    group_by_instance = e013.group_mapping(mandatory)
    best_surface = build_surface(
        label=16101,
        solution=best_solution,
        endpoint=best_endpoint,
        pools=pools,
        group_by_instance=group_by_instance,
        e013=e013,
        e022=e022,
    )
    second_surface = build_surface(
        label=16102,
        solution=second_solution,
        endpoint=second_endpoint,
        pools=pools,
        group_by_instance=group_by_instance,
        e013=e013,
        e022=e022,
    )
    residual_comparison = e022.compare_surfaces([best_surface, second_surface])
    best_swaps = swap_surface(
        solution=best_solution,
        endpoint=best_endpoint,
        pools=pools,
        group_by_instance=group_by_instance,
        e013=e013,
        e029=e029,
    )
    second_swaps = swap_surface(
        solution=second_solution,
        endpoint=second_endpoint,
        pools=pools,
        group_by_instance=group_by_instance,
        e013=e013,
        e029=e029,
    )

    best_top10 = {
        str(row["pair_key"]) for row in best_swaps["top_raw_pairs"][:10]
    }
    second_top10 = {
        str(row["pair_key"]) for row in second_swaps["top_raw_pairs"][:10]
    }
    best_portfolio = {
        str(row["pair_key"]) for row in best_swaps["selected_portfolio"]
    }
    second_portfolio = {
        str(row["pair_key"]) for row in second_swaps["selected_portfolio"]
    }
    best_leader = str(best_swaps["top_raw_pairs"][0]["pair_key"])
    second_leader = str(second_swaps["top_raw_pairs"][0]["pair_key"])
    if (
        str(best_surface["ranking_digest"]) == str(second_surface["ranking_digest"])
        and best_portfolio == second_portfolio
    ):
        verdict = "OBJECTIVE_161_ASSIGNMENT_SURFACES_EQUIVALENT"
        decision = "QUOTIENT_STATES_FOR_SHARED_NEXT_ACTION"
    elif best_leader == second_leader:
        verdict = "OBJECTIVE_161_SHARED_LEADER_DISTINCT_SURFACES"
        decision = "REPLAY_COMMON_AND_BRANCH_SPECIFIC_ACTIONS"
    else:
        verdict = "OBJECTIVE_161_ASSIGNMENT_SURFACES_DIVERGENT"
        decision = "RETAIN_TWO_STATE_ASSIGNMENT_BEAM"

    return {
        "schema": "zmd_zero_condition_e032_assignment_tie_surface_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "second_endpoint_materialization": {
            "fully_materialized": fully_materialized,
            "target_selection_digest": target_digest,
            "selected_endpoint_digest": second_endpoint["selection_digest"],
            "attempts": attempts,
            "assignment_path": str(SECOND_ASSIGNMENT_PATH.relative_to(ROOT)),
            "assignment_sha256": sha256_file(SECOND_ASSIGNMENT_PATH),
            "layout_path": str(SECOND_LAYOUT_PATH.relative_to(ROOT)),
            "layout_sha256": sha256_file(SECOND_LAYOUT_PATH),
            "endpoint_path": str(SECOND_ENDPOINT_PATH.relative_to(ROOT)),
            "endpoint_sha256": sha256_file(SECOND_ENDPOINT_PATH),
        },
        "state_surfaces": [best_surface, second_surface],
        "residual_comparison": residual_comparison,
        "swap_surfaces": {
            "best_materialized_state": best_swaps,
            "second_tied_state": second_swaps,
            "leader_by_state": {
                "best": best_leader,
                "second": second_leader,
            },
            "top10_intersection_count": len(best_top10 & second_top10),
            "top10_jaccard": (
                len(best_top10 & second_top10) / len(best_top10 | second_top10)
            ),
            "portfolio_intersection_count": len(
                best_portfolio & second_portfolio
            ),
            "portfolio_jaccard": (
                len(best_portfolio & second_portfolio)
                / len(best_portfolio | second_portfolio)
            ),
        },
        "decision": decision,
        "routing_solver_run": False,
        "truth_boundary": (
            "Residual boundary and operation-swap proposal surfaces for two frozen "
            "objective-161 assignment/binding states under one occupied geometry."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if (
        RESULT_PATH.exists()
        or FAILURE_PATH.exists()
        or SECOND_ASSIGNMENT_PATH.exists()
        or SECOND_LAYOUT_PATH.exists()
        or SECOND_ENDPOINT_PATH.exists()
    ):
        raise FileExistsError("refusing to overwrite E032 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "fully_materialized_second_endpoint": result[
                        "second_endpoint_materialization"
                    ]["fully_materialized"],
                    "residual_leaders": result["residual_comparison"][
                        "leader_by_class"
                    ],
                    "swap_leaders": result["swap_surfaces"]["leader_by_state"],
                    "top10_intersection_count": result["swap_surfaces"][
                        "top10_intersection_count"
                    ],
                    "portfolio_intersection_count": result["swap_surfaces"][
                        "portfolio_intersection_count"
                    ],
                    "decision": result["decision"],
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
            "schema": "zmd_zero_condition_e032_assignment_tie_surface_failure_v1",
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
