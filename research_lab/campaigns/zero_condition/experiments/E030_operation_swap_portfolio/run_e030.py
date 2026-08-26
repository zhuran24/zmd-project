#!/usr/bin/env python3
"""E030: exact shared-binding replay of the E029 operation-swap portfolio."""

from __future__ import annotations

from collections import Counter, defaultdict
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
OUT = ROOT / "research_lab/local/zero_condition/E030_operation_swap_portfolio/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
RECORDS_PATH = OUT / "SWAP_RECORDS.json"

E028_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E028_static_coupling_pair/run-001/RESULT.json"
)
E028_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E028_static_coupling_pair/run-001/BEST_PAIR_ASSIGNMENT.json"
)
E028_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E028_static_coupling_pair/run-001/BEST_PAIR_ENDPOINT.json"
)
E029_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E029_operation_assignment_surface/run-001/RESULT.json"
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
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E027_final_unary_discriminator/run_e027.py"
)
E029_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E029_operation_assignment_surface/run_e029.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "263000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E028_RESULT: "38901057591ffe6f3e3d8e0b00045e7facc86abc4f307dd46a9604c38c4a7c41",
    E028_ASSIGNMENT: "02383c24dfc4528714cb371c6d07b38481dabcfaa6868cdbe65002a9a30b8b95",
    E028_ENDPOINT: "5c0089cfd1cb4376ebfe1da361142705a352b1f7507b0ce390248f6facd54a97",
    E029_RESULT: "25ded5d381d3972bb753b4593c3f1b791303027696212fd40bd44a8612d7b6fe",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    E029_RUNNER: "08672e533d4d73e50a411703c41017b058521ff2a9d4e6f53c2235343cef46bf",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
    HISTORY_ROOT / "rules/canonical_rules.json": (
        "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0"
    ),
    HISTORY_ROOT / "rules/preprocess_plan.json": (
        "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee"
    ),
}

PARENT_OBJECTIVE = 166
EXPECTED_PORTFOLIO_SIZE = 12
MATERIAL_IMPROVEMENT = 2


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
        raise RuntimeError("E030 must run on research/main")
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
    e028 = load_json(E028_RESULT)
    if int(e028["best_child"]["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E028 parent objective drift")
    e029 = load_json(E029_RESULT)
    if e029.get("verdict") != "OPERATION_ASSIGNMENT_SWAP_PORTFOLIO_PLAUSIBLE":
        raise RuntimeError("E029 trigger verdict drift")
    portfolio = e029["operation_swap_surface"]["selected_portfolio"]
    if len(portfolio) != EXPECTED_PORTFOLIO_SIZE:
        raise RuntimeError("E029 portfolio size drift")
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


def load_parent_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E028_ASSIGNMENT)
    raw = assignment.get("solution")
    if not isinstance(raw, Mapping):
        raise RuntimeError("E028 parent assignment drift")
    solution = {
        str(instance_id): dict(row)
        for instance_id, row in raw.items()
        if isinstance(row, Mapping)
    }
    result = load_json(E028_RESULT)
    if stable_digest(solution) != str(result["best_child"]["placement_digest"]):
        raise RuntimeError("E028 parent placement digest drift")
    endpoint = load_json(E028_ENDPOINT)
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != 166:
        raise RuntimeError("E028 parent endpoint drift")
    return solution


def swap_solution(
    *,
    parent: Mapping[str, Mapping[str, Any]],
    action: Mapping[str, Any],
    inputs: Mapping[str, Any],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    left = action["left"]
    right = action["right"]
    left_ids = [str(value) for value in left["source_instance_ids"]]
    right_ids = [str(value) for value in right["source_instance_ids"]]
    if len(left_ids) != 1 or len(right_ids) != 1:
        raise RuntimeError("E030 action lacks one concrete source per side")
    left_id = left_ids[0]
    right_id = right_ids[0]
    if left_id == right_id:
        raise RuntimeError("E030 action aliases one instance")
    left_row = parent[left_id]
    right_row = parent[right_id]
    facility_type = str(left_row["facility_type"])
    if facility_type != str(right_row["facility_type"]):
        raise RuntimeError("E030 action facility-type mismatch")
    if facility_type != str(left["facility_type"]) or facility_type != str(
        right["facility_type"]
    ):
        raise RuntimeError("E030 action payload facility drift")
    if int(left_row["pose_idx"]) != int(left["pose_idx"]):
        raise RuntimeError("E030 left current pose drift")
    if int(right_row["pose_idx"]) != int(right["pose_idx"]):
        raise RuntimeError("E030 right current pose drift")
    if str(left_row["operation_type"]) == str(right_row["operation_type"]):
        raise RuntimeError("E030 action does not cross operations")

    left_pose_idx = int(right_row["pose_idx"])
    right_pose_idx = int(left_row["pose_idx"])
    left_pose = inputs["pools"][facility_type][left_pose_idx]
    right_pose = inputs["pools"][facility_type][right_pose_idx]
    child = {str(key): dict(value) for key, value in parent.items()}
    child[left_id] = e014.replacement_row(
        source=left_row,
        pose=left_pose,
        pose_idx=left_pose_idx,
        instance_id=left_id,
    )
    child[right_id] = e014.replacement_row(
        source=right_row,
        pose=right_pose,
        pose_idx=right_pose_idx,
        instance_id=right_id,
    )
    return child


def compact_shared(shared: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": shared.get("status"),
        "objective": shared.get("objective"),
        "selection_digest": shared.get("selection_digest"),
        "port_specs_digest": shared.get("port_specs_digest"),
        "per_commodity": json_safe(shared.get("per_commodity", {})),
        "selected_components": json_safe(shared.get("selected_components", {})),
        "positive_commodity_count": shared.get("positive_commodity_count"),
        "zero_mismatch_commodities": json_safe(
            shared.get("zero_mismatch_commodities", [])
        ),
        "morphology": json_safe(shared.get("morphology", {})),
        "filtered_binding_option_count": shared.get(
            "filtered_binding_option_count"
        ),
        "empty_filtered_domains": json_safe(
            shared.get("empty_filtered_domains", [])
        ),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e001 = import_module("zmd_e030_e001", E001_RUNNER)
    e002 = import_module("zmd_e030_e002", E002_RUNNER)
    e004 = import_module("zmd_e030_e004", E004_RUNNER)
    e014 = import_module("zmd_e030_e014", E014_RUNNER)
    e015 = import_module("zmd_e030_e015", E015_RUNNER)
    e027 = import_module("zmd_e030_e027", E027_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent = load_parent_solution()
    parent_occupied, _ = e014.base_occupancy(parent, inputs["pools"])
    parent_free_digest = load_json(E028_ENDPOINT)["morphology"][
        "free_cell_set_digest"
    ]
    selected_poles = {
        int(row["pose_idx"])
        for row in parent.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)

    portfolio = [
        dict(row)
        for row in load_json(E029_RESULT)["operation_swap_surface"][
            "selected_portfolio"
        ]
    ]
    action_records: list[dict[str, Any]] = []
    unique_children: dict[str, dict[str, Any]] = {}
    provenance_by_digest: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for action in portfolio:
        child = swap_solution(
            parent=parent,
            action=action,
            inputs=inputs,
            e014=e014,
        )
        occupied, _owner_by_cell = e014.base_occupancy(child, inputs["pools"])
        if occupied != parent_occupied:
            raise RuntimeError(
                f"E030 swap changed occupancy: {action['pair_key']}"
            )
        if not e014.all_powered_facilities_covered(
            solution=child,
            selected_poles=selected_poles,
            powered_templates=power["powered_templates"],
            coverers=power["coverers"],
        ):
            raise RuntimeError(f"E030 swap broke power: {action['pair_key']}")
        digest = stable_digest(child)
        unique_children.setdefault(digest, child)
        provenance_by_digest[digest].append(action)

    evaluated_by_digest: dict[str, dict[str, Any]] = {}
    for index, (digest, child) in enumerate(sorted(unique_children.items()), 1):
        try:
            shared = e015.solve_shared_mismatch(
                solution=child,
                inputs=inputs,
                e004=e004,
                random_seed=270000 + index,
                include_boundaries=False,
            )
        except RuntimeError as exc:
            if "empty binding domain" not in str(exc):
                raise
            diagnostic = e014.screen_component_interface(
                solution=child,
                inputs=inputs,
                e001=e001,
                e002=e002,
            )
            if diagnostic.get("status") != "PORT_DOMAIN_EMPTY":
                raise RuntimeError(
                    "E030 empty-domain exception was not reproduced: "
                    f"{diagnostic.get('status')}"
                )
            shared = {
                "status": "PORT_DOMAIN_EMPTY",
                "objective": None,
                "detail": str(exc),
                "empty_filtered_domains": diagnostic.get(
                    "empty_filtered_domains", []
                ),
                "filtered_binding_option_count": diagnostic.get(
                    "filtered_binding_option_count"
                ),
                "front_blocked_patterns_pruned": diagnostic.get(
                    "front_blocked_patterns_pruned"
                ),
                "morphology": diagnostic.get("morphology"),
            }
        evaluated_by_digest[digest] = compact_shared(shared)
        print(
            json.dumps(
                {
                    "event": "E030_SWAP_COMPLETE",
                    "candidate": index,
                    "candidate_total": len(unique_children),
                    "placement_digest": digest,
                    "action_count": len(provenance_by_digest[digest]),
                    "status": shared.get("status"),
                    "objective": shared.get("objective"),
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    for action in portfolio:
        child = swap_solution(
            parent=parent,
            action=action,
            inputs=inputs,
            e014=e014,
        )
        digest = stable_digest(child)
        action_records.append(
            {
                "portfolio_rank": int(action["portfolio_rank"]),
                "pair_key": str(action["pair_key"]),
                "union_coverage": int(action["union_coverage"]),
                "coverage_fraction": float(action["coverage_fraction"]),
                "left_literal": str(action["left_literal"]),
                "right_literal": str(action["right_literal"]),
                "candidate_solution_digest": digest,
                "duplicate_action_count_for_state": len(
                    provenance_by_digest[digest]
                ),
                "shared_binding": evaluated_by_digest[digest],
            }
        )

    records_payload = {
        "schema": "zmd_zero_condition_e030_swap_records_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "parent_objective": PARENT_OBJECTIVE,
        "parent_free_cell_set_digest": parent_free_digest,
        "input_action_count": len(portfolio),
        "unique_child_count": len(unique_children),
        "records": action_records,
        "ledger_effect": "none",
    }
    dump_exclusive(RECORDS_PATH, records_payload)

    status_counts = Counter(
        str(record["shared_binding"]["status"]) for record in action_records
    )
    optimal = [
        record
        for record in action_records
        if record["shared_binding"]["status"] == "OPTIMAL"
    ]
    common = {
        "schema": "zmd_zero_condition_e030_operation_swap_portfolio_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "power_semantics": power["summary"],
        "parent_objective": PARENT_OBJECTIVE,
        "parent_free_cell_set_digest": parent_free_digest,
        "portfolio_digest": load_json(E029_RESULT)["operation_swap_surface"][
            "portfolio_digest"
        ],
        "input_action_count": len(portfolio),
        "unique_child_count": len(unique_children),
        "status_counts": dict(sorted(status_counts.items())),
        "swap_records_path": str(RECORDS_PATH.relative_to(ROOT)),
        "swap_records_sha256": sha256_file(RECORDS_PATH),
        "truth_boundary": (
            "Exact replay of twelve occupancy-preserving operation swaps under "
            "one fixed objective-166 parent endpoint."
        ),
        "ledger_effect": "none",
    }
    if not optimal:
        empty_frequency = Counter(
            f"{row.get('instance_id')}@{row.get('pose_idx')}"
            for record in action_records
            for row in record["shared_binding"].get(
                "empty_filtered_domains", []
            )
        )
        return {
            **common,
            "verdict": "OPERATION_SWAP_PORTFOLIO_STATIC_REJECTED",
            "optimal_candidate_count": 0,
            "objective_distribution": {},
            "empty_domain_frequency": dict(sorted(empty_frequency.items())),
            "best_child": None,
            "routing": {"status": "NOT_REACHED_NO_OPTIMAL_CHILD"},
            "decision": "MOVE_OPERATION_ASSIGNMENT_AND_BINDING_INTO_ONE_MODEL",
        }

    ranked = sorted(
        optimal,
        key=lambda row: (
            int(row["shared_binding"]["objective"]),
            -int(row["shared_binding"]["filtered_binding_option_count"]),
            int(row["portfolio_rank"]),
        ),
    )
    best = ranked[0]
    best_solution = unique_children[str(best["candidate_solution_digest"])]
    endpoint = e027.materialize_shared_endpoint(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=270999,
    )
    if int(endpoint["objective"]) != int(best["shared_binding"]["objective"]):
        raise RuntimeError("E030 materialized endpoint objective drift")
    if str(endpoint["morphology"]["free_cell_set_digest"]) != str(
        parent_free_digest
    ):
        raise RuntimeError("E030 materialized child changed free-cell set")

    assignment_path = OUT / "BEST_SWAP_ASSIGNMENT.json"
    layout_path = OUT / "BEST_SWAP_LAYOUT.json"
    endpoint_path = OUT / "BEST_SWAP_ENDPOINT.json"
    dump_exclusive(
        assignment_path,
        {
            "schema": "zmd_zero_condition_e030_best_swap_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "pair_key": best["pair_key"],
            "solution": best_solution,
        },
    )
    dump_exclusive(layout_path, e001.solution_layout(best_solution))
    dump_exclusive(endpoint_path, endpoint)

    objective = int(endpoint["objective"])
    delta = objective - PARENT_OBJECTIVE
    if objective == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        verdict = "OPERATION_SWAP_PORTFOLIO_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif delta <= -MATERIAL_IMPROVEMENT:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "OPERATION_SWAP_PORTFOLIO_MATERIAL_IMPROVEMENT"
        decision = "RETAIN_SWAP_CHILD_AND_RECOMPUTE_ASSIGNMENT_SURFACE"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "OPERATION_SWAP_PORTFOLIO_WEAK_OR_EQUAL"
        decision = "MOVE_OPERATION_ASSIGNMENT_AND_BINDING_INTO_ONE_MODEL"

    distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal
    )
    return {
        **common,
        "verdict": verdict,
        "optimal_candidate_count": len(optimal),
        "objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "top_candidates": ranked[:20],
        "best_child": {
            "objective": objective,
            "delta_from_parent": delta,
            "portfolio_rank": int(best["portfolio_rank"]),
            "pair_key": str(best["pair_key"]),
            "union_coverage": int(best["union_coverage"]),
            "placement_digest": stable_digest(best_solution),
            "binding_selection_digest": endpoint["selection_digest"],
            "per_commodity": endpoint["per_commodity"],
            "positive_commodity_count": endpoint["positive_commodity_count"],
            "zero_mismatch_commodities": endpoint["zero_mismatch_commodities"],
            "morphology": endpoint["morphology"],
            "filtered_binding_option_count": endpoint[
                "filtered_binding_option_count"
            ],
            "assignment_path": str(assignment_path.relative_to(ROOT)),
            "assignment_sha256": sha256_file(assignment_path),
            "layout_path": str(layout_path.relative_to(ROOT)),
            "layout_sha256": sha256_file(layout_path),
            "endpoint_path": str(endpoint_path.relative_to(ROOT)),
            "endpoint_sha256": sha256_file(endpoint_path),
        },
        "routing": routing,
        "decision": decision,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists() or RECORDS_PATH.exists():
        raise FileExistsError("refusing to overwrite E030 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "parent_objective": result["parent_objective"],
                    "input_action_count": result["input_action_count"],
                    "unique_child_count": result["unique_child_count"],
                    "status_counts": result["status_counts"],
                    "best_child": result.get("best_child"),
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
            "schema": "zmd_zero_condition_e030_operation_swap_portfolio_failure_v1",
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
