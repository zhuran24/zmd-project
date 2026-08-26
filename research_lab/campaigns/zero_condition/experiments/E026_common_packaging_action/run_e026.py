#!/usr/bin/env python3
"""E026: replay packaging_battery pose 6189 across the live 168/173 beam."""

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
OUT = ROOT / "research_lab/local/zero_condition/E026_common_packaging_action/run-003"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E025_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E025_live_beam_residual_surface/run-004/RESULT.json"
)
E025_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E025_live_beam_residual_surface/run_e025.py"
)
E024_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/RESULT.json"
)
E024_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/BEST_BRANCH_CHILD_ASSIGNMENT.json"
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
    "EXACT_MASTER_RANDOM_SEED": "262600",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

EXPECTED_HASHES: dict[Path, str] = {
    E025_RESULT: "3a2d076ba283ccfaf946c772cbbc25a530b14849bcd433516965edc3b7670c5a",
    E025_RUNNER: "bd97fc5669943e7ae2b93bfd8a04dd725e20032116f42d433af2d7da88173002",
    E024_RESULT: "a0a69a8c0f9c7f59d8924f9f13e0e277fe5f254a35aeaeb34c6c721becd4d17f",
    E024_ASSIGNMENT: "4f49e6dc8aaaf8e677596cd631f0eb34fc735612a4ff5a3e09dbb50836633018",
    E022_RUNNER: "060440bd8b5ba2cba7647987fa30bed7b08e8d8ca155d9ddcaed6cd276e09507",
}

COMMON_TARGET_LITERAL = (
    "mandatory::group::manufacturing_6x4::packaging_battery::17::6189"
)
PARENT_OBJECTIVES = {1: 173, 2: 173, 3: 173, 168: 168}


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
    return OUT / f"CLASS_{class_index}.json"


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E026 must run on research/main")
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
            raise RuntimeError(f"frozen identity drift for {path}: {actual}")
    e025 = load_json(E025_RESULT)
    selected = e025["decision_reading"]["selected_common_action"]
    if str(selected["literal_key"]) != COMMON_TARGET_LITERAL:
        raise RuntimeError("E026 target drift")
    e024 = load_json(E024_RESULT)
    if int(e024["best_child"]["objective"]) != 168:
        raise RuntimeError("E026 E024 objective drift")
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


def live_states(*, e022: Any, e001: Any, e004: Any, e014: Any, e017: Any, e019: Any, e021: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs, old_states = e022.reconstruct_retained_states(
        e001=e001,
        e004=e004,
        e014=e014,
        e017=e017,
        e019=e019,
        e021=e021,
    )
    states = [dict(state) for state in old_states if int(state["class_index"]) in {1, 2, 3}]
    if len(states) != 3:
        raise RuntimeError("E026 retained 173 state count drift")
    e024_result = load_json(E024_RESULT)
    assignment = load_json(E024_ASSIGNMENT)
    solution = assignment.get("solution")
    if not isinstance(solution, Mapping) or len(solution) != 319:
        raise RuntimeError("E026 E024 assignment drift")
    if stable_digest(solution) != str(e024_result["best_child"]["placement_digest"]):
        raise RuntimeError("E026 E024 placement digest drift")
    states.append(
        {
            "class_index": 168,
            "retained_state": {
                "objective": 168,
                "placement_digest": e024_result["best_child"]["placement_digest"],
                "binding_selection_digest": e024_result["best_child"][
                    "binding_selection_digest"
                ],
                "free_cell_set_digest": e024_result["best_child"]["morphology"][
                    "free_cell_set_digest"
                ],
                "source": "E024 branch leader",
            },
            "solution": dict(solution),
        }
    )
    return inputs, states


def compact_endpoint(shared: Mapping[str, Any]) -> dict[str, Any]:
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
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e022 = import_module("zmd_e026_e022", E022_RUNNER)
    e021 = import_module("zmd_e026_e021", e022.E021_RUNNER)
    e001 = import_module("zmd_e026_e001", e021.E001_RUNNER)
    e002 = import_module("zmd_e026_e002", e021.E002_RUNNER)
    e004 = import_module("zmd_e026_e004", e021.E004_RUNNER)
    e014 = import_module("zmd_e026_e014", e021.E014_RUNNER)
    e015 = import_module("zmd_e026_e015", e021.E015_RUNNER)
    e017 = import_module("zmd_e026_e017", e021.E017_RUNNER)
    e019 = import_module("zmd_e026_e019", e021.E019_RUNNER)

    inputs, states = live_states(
        e022=e022,
        e001=e001,
        e004=e004,
        e014=e014,
        e017=e017,
        e019=e019,
        e021=e021,
    )
    e025 = load_json(E025_RESULT)
    target = dict(e025["decision_reading"]["selected_common_action"])
    if str(target["literal_key"]) != COMMON_TARGET_LITERAL:
        raise RuntimeError("E026 target payload drift")

    stack = e001.import_stack()
    power = e014.build_power_semantics(e001, stack, inputs)
    class_results: list[dict[str, Any]] = []
    all_records: list[dict[str, Any]] = []
    child_solutions: dict[tuple[int, str], dict[str, Any]] = {}

    for state in states:
        class_index = int(state["class_index"])
        parent_objective = PARENT_OBJECTIVES[class_index]
        parent_solution = state["solution"]
        source_id = str(target["source_instance_ids"][0])
        if int(parent_solution[source_id]["pose_idx"]) != int(target["pose_idx"]):
            raise RuntimeError(f"E026 target already moved in class {class_index}")
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
            raise RuntimeError(f"E026 class {class_index} fails power semantics")

        path = checkpoint_path(class_index)
        alternatives = e014.enumerate_alternatives(
            target=target,
            base_solution=parent_solution,
            pools=inputs["pools"],
            occupied=occupied,
            selected_poles=selected_poles,
            powered_templates=power["powered_templates"],
            coverers=power["coverers"],
        )
        if len(alternatives) != 3:
            raise RuntimeError(
                f"E026 class {class_index} action-domain drift: {len(alternatives)}"
            )
        records: list[dict[str, Any]] = []
        for candidate_index, candidate in enumerate(alternatives, 1):
            solution = candidate["solution"]
            try:
                shared = e015.solve_shared_mismatch(
                    solution=solution,
                    inputs=inputs,
                    e004=e004,
                    random_seed=266000 + class_index + candidate_index,
                    include_boundaries=False,
                )
            except RuntimeError as exc:
                if "empty binding domain" not in str(exc):
                    raise
                diagnostic = e014.screen_component_interface(
                    solution=solution,
                    inputs=inputs,
                    e001=e001,
                    e002=e002,
                )
                if diagnostic.get("status") != "PORT_DOMAIN_EMPTY":
                    raise RuntimeError(
                        "E026 empty-domain exception was not reproduced by the "
                        f"ordered interface screen: {diagnostic.get('status')}"
                    )
                shared = {
                    "status": "PORT_DOMAIN_EMPTY",
                    "objective": None,
                    "detail": str(exc),
                    "empty_filtered_domain_count": diagnostic.get(
                        "empty_filtered_domain_count"
                    ),
                    "empty_filtered_domains": diagnostic.get(
                        "empty_filtered_domains"
                    ),
                    "filtered_binding_option_count": diagnostic.get(
                        "filtered_binding_option_count"
                    ),
                    "front_blocked_patterns_pruned": diagnostic.get(
                        "front_blocked_patterns_pruned"
                    ),
                    "morphology": diagnostic.get("morphology"),
                }
            digest = stable_digest(solution)
            record = {
                "pose_idx": int(candidate["pose_idx"]),
                "pose_id": str(candidate["pose_id"]),
                "anchor": json_safe(candidate["anchor"]),
                "same_footprint": bool(candidate["same_footprint"]),
                "candidate_solution_digest": digest,
                "shared_binding": json_safe(shared),
            }
            records.append(record)
            child_solutions[(class_index, digest)] = dict(solution)
        checkpoint = {
            "schema": "zmd_zero_condition_e026_class_expansion_v1",
            "created_at_utc": utc_now(),
            "runner_sha256": runner_sha256,
            "class_index": class_index,
            "parent_objective": parent_objective,
            "parent_state": json_safe(state["retained_state"]),
            "target": json_safe(target),
            "alternative_count": len(records),
            "candidate_records": records,
            "status_counts": dict(
                sorted(Counter(row["shared_binding"]["status"] for row in records).items())
            ),
        }
        dump_exclusive(path, checkpoint)

        optimal = [
            row for row in records if row["shared_binding"]["status"] == "OPTIMAL"
        ]
        ranked = sorted(
            optimal,
            key=lambda row: (
                int(row["shared_binding"]["objective"]),
                -int(row["shared_binding"]["filtered_binding_option_count"]),
                int(row["shared_binding"]["morphology"]["free_component_count"]),
                int(row["pose_idx"]),
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
                "parent_objective": parent_objective,
                "alternative_count": len(records),
                "status_counts": checkpoint["status_counts"],
                "best_child_objective": best_objective,
                "delta_from_parent": (
                    best_objective - parent_objective
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
                "best_child_endpoint": (
                    compact_endpoint(best["shared_binding"])
                    if best is not None
                    else None
                ),
            }
        )
        all_records.extend(
            {**dict(record), "class_index": class_index} for record in records
        )

    optimal_records = [
        row for row in all_records if row["shared_binding"]["status"] == "OPTIMAL"
    ]
    if not optimal_records:
        empty_domain_counts = Counter(
            (
                f"{domain.get('instance_id')}@{domain.get('pose_idx')}"
            )
            for record in all_records
            for domain in record["shared_binding"].get(
                "empty_filtered_domains", []
            )
        )
        return {
            "schema": "zmd_zero_condition_e026_common_packaging_action_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "COMMON_PACKAGING_ACTION_STATIC_DOMAIN_REJECTED",
            "identity": identity,
            "power_semantics": power["summary"],
            "target": json_safe(target),
            "parent_objectives": {
                str(k): v for k, v in PARENT_OBJECTIVES.items()
            },
            "class_results": class_results,
            "class_checkpoint_paths": [
                str(checkpoint_path(index).relative_to(ROOT))
                for index in (1, 2, 3, 168)
            ],
            "total_alternative_count": len(all_records),
            "status_counts": dict(
                sorted(
                    Counter(
                        row["shared_binding"]["status"] for row in all_records
                    ).items()
                )
            ),
            "optimal_candidate_count": 0,
            "objective_distribution": {},
            "empty_domain_frequency": dict(sorted(empty_domain_counts.items())),
            "branch_response": {
                "base_feasible_class_count": 0,
                "static_domain_rejected_class_count": len(class_results),
                "statement": (
                    "Every placement/power-valid alternative empties at least one "
                    "front-filtered binding owner domain before component support."
                ),
            },
            "best_child": None,
            "beam_decision": {
                "retain_improved_children": False,
                "retire_target_from_current_unary_ledger": True,
                "next_action": (
                    "mandatory::group::manufacturing_3x3::crusher_sandleaf::3::2155"
                ),
                "next_representation_if_unary_saturates": (
                    "simultaneous two-pose or pose-binding neighborhood"
                ),
            },
            "routing": {"status": "NOT_REACHED_PORT_DOMAIN_EMPTY"},
            "truth_boundary": (
                "Exhaustive fixed-outside alternatives for packaging_battery pose "
                "6189 under four live parent placements."
            ),
            "ledger_effect": "none",
        }
    ranked_global = sorted(
        optimal_records,
        key=lambda row: (
            int(row["shared_binding"]["objective"]),
            int(row["class_index"]),
            -int(row["shared_binding"]["filtered_binding_option_count"]),
            int(row["pose_idx"]),
        ),
    )
    best = ranked_global[0]
    best_class = int(best["class_index"])
    best_solution = child_solutions[
        (best_class, str(best["candidate_solution_digest"]))
    ]

    assignment_path = OUT / "BEST_PACKAGING_CHILD_ASSIGNMENT.json"
    layout_path = OUT / "BEST_PACKAGING_CHILD_LAYOUT.json"
    endpoint_path = OUT / "BEST_PACKAGING_ENDPOINT.json"
    dump_exclusive(
        assignment_path,
        {
            "schema": "zmd_zero_condition_e026_best_packaging_child_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "parent_class_index": best_class,
            "parent_objective": PARENT_OBJECTIVES[best_class],
            "target_literal": COMMON_TARGET_LITERAL,
            "replacement_pose_idx": int(best["pose_idx"]),
            "shared_mismatch_objective": int(best["shared_binding"]["objective"]),
            "solution": best_solution,
        },
    )
    dump_exclusive(layout_path, e001.solution_layout(best_solution))
    dump_exclusive(
        endpoint_path,
        {
            "schema": "zmd_zero_condition_e026_materialized_binding_endpoint_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "placement_digest": stable_digest(best_solution),
            "parent_class_index": best_class,
            "parent_objective": PARENT_OBJECTIVES[best_class],
            "target_literal": COMMON_TARGET_LITERAL,
            "replacement_pose_idx": int(best["pose_idx"]),
            **compact_endpoint(best["shared_binding"]),
        },
    )

    if int(best["shared_binding"]["objective"]) == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=import_module("zmd_e026_e002", e021.E002_RUNNER),
        )
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}

    deltas = [
        int(row["delta_from_parent"])
        for row in class_results
        if row["delta_from_parent"] is not None
    ]
    improved = sum(delta < 0 for delta in deltas)
    equal = sum(delta == 0 for delta in deltas)
    worsened = sum(delta > 0 for delta in deltas)
    if int(best["shared_binding"]["objective"]) == 0:
        verdict = "COMMON_PACKAGING_ACTION_COMPONENT_CANDIDATE"
    elif improved == len(class_results):
        verdict = "COMMON_PACKAGING_ACTION_IMPROVES_ALL"
    elif worsened == len(class_results):
        verdict = "COMMON_PACKAGING_ACTION_RETIRED"
    elif improved or worsened:
        verdict = "COMMON_PACKAGING_ACTION_BRANCH_DEPENDENT"
    else:
        verdict = "COMMON_PACKAGING_ACTION_EQUAL"

    objective_distribution = Counter(
        int(row["shared_binding"]["objective"]) for row in optimal_records
    )
    return {
        "schema": "zmd_zero_condition_e026_common_packaging_action_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "power_semantics": power["summary"],
        "target": json_safe(target),
        "parent_objectives": {str(k): v for k, v in PARENT_OBJECTIVES.items()},
        "class_results": class_results,
        "class_checkpoint_paths": [
            str(checkpoint_path(index).relative_to(ROOT))
            for index in (1, 2, 3, 168)
        ],
        "total_alternative_count": len(all_records),
        "status_counts": dict(
            sorted(Counter(row["shared_binding"]["status"] for row in all_records).items())
        ),
        "optimal_candidate_count": len(optimal_records),
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "branch_response": {
            "improved_class_count": improved,
            "equal_class_count": equal,
            "worsened_class_count": worsened,
            "delta_range": max(deltas) - min(deltas),
            "best_delta": min(deltas),
            "worst_delta": max(deltas),
        },
        "best_child": {
            "parent_class_index": best_class,
            "parent_objective": PARENT_OBJECTIVES[best_class],
            "objective": int(best["shared_binding"]["objective"]),
            "delta_from_parent": (
                int(best["shared_binding"]["objective"])
                - PARENT_OBJECTIVES[best_class]
            ),
            "replacement_pose_idx": int(best["pose_idx"]),
            "replacement_pose_id": str(best["pose_id"]),
            "placement_digest": stable_digest(best_solution),
            "endpoint": compact_endpoint(best["shared_binding"]),
            "assignment_path": str(assignment_path.relative_to(ROOT)),
            "assignment_sha256": sha256_file(assignment_path),
            "layout_path": str(layout_path.relative_to(ROOT)),
            "layout_sha256": sha256_file(layout_path),
            "endpoint_path": str(endpoint_path.relative_to(ROOT)),
            "endpoint_sha256": sha256_file(endpoint_path),
        },
        "beam_decision": {
            "retain_improved_children": improved > 0,
            "retire_target_from_current_unary_ledger": worsened == len(class_results),
            "next_action_if_weak": (
                "mandatory::group::manufacturing_3x3::crusher_sandleaf::3::2155"
            ),
            "next_representation_if_unary_saturates": (
                "simultaneous two-pose or pose-binding neighborhood"
            ),
        },
        "routing": routing,
        "truth_boundary": (
            "Exhaustive fixed-outside alternatives for packaging_battery pose 6189 "
            "under four live parent placements."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E026 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "class_results": result["class_results"],
                    "branch_response": result["branch_response"],
                    "best_child": (
                        {
                            key: result["best_child"][key]
                            for key in (
                                "parent_class_index",
                                "parent_objective",
                                "objective",
                                "delta_from_parent",
                                "replacement_pose_idx",
                            )
                        }
                        if result["best_child"] is not None
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
            "schema": "zmd_zero_condition_e026_failure_v1",
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
