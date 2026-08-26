#!/usr/bin/env python3
"""E040: exact fixed-outside geometry mobility over a causal target portfolio."""

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
OUT = ROOT / "research_lab/local/zero_condition/E040_geometry_mobility_discriminator/run-002"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ARM_MANIFEST_PATH = OUT / "ARM_MANIFEST.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_LAYOUT.json"
BEST_ENDPOINT_PATH = OUT / "BEST_ENDPOINT.json"

E039_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E039_native_conditional_owner_binding/run-002/RESULT.json"
)
E039_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E039_native_conditional_owner_binding/run-002/BEST_ASSIGNMENT.json"
)
E039_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E039_native_conditional_owner_binding/run-002/BEST_ENDPOINT.json"
)
E039_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E039_native_conditional_owner_binding/run_e039.py"
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

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "270000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E039_RESULT: "662c2a420fd84a7c9fbbde6c0392d1ce7d726b8c3dcd83e430d299a8a3c93389",
    E039_ASSIGNMENT: "aeded115ef1a1983e0fdf9f3decee3d34983d8b53de0f02af5bcb3670cd8cf7b",
    E039_ENDPOINT: "f24f39d1fdf317a9bd2cd9c3559c46ef449a9d67e8e5c671b1523b3d2c0ef85e",
    E039_RUNNER: "ebb471a0bba3e3cd2d2e141190c2e128fefcacfff620d7e6fdf6aee71b1741b9",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E017_RUNNER: "106d7ee8830d3a45bf4115e064e65e059fdd86c4bd4b5c2acddaff55e203a2e0",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
}

PARENT_OBJECTIVE = 157
TARGET_BUDGET = 16
MATERIAL_IMPROVEMENT = 2
EXCLUDED_FACILITY_TYPES = {"boundary_storage_port", "protocol_core"}


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


def checkpoint_path(index: int) -> Path:
    return OUT / f"ARM_{index:02d}.json"


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E040 must run on research/main")
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
    result = load_json(E039_RESULT)
    if result.get("verdict") != "NATIVE_CONDITIONAL_OWNER_CONTEXT_SATURATED":
        raise RuntimeError("E039 trigger verdict drift")
    if int(result["best_child"]["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E039 objective drift")
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


def compact_shared(shared: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": shared.get("status"),
        "objective": shared.get("objective"),
        "selection_digest": shared.get("selection_digest"),
        "port_specs_digest": shared.get("port_specs_digest"),
        "per_commodity": json_safe(shared.get("per_commodity", {})),
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
    e039 = import_module("zmd_e040_e039", E039_RUNNER)
    e038 = import_module("zmd_e040_e038", e039.E038_RUNNER)
    e037 = import_module("zmd_e040_e037", e038.E037_RUNNER)
    e036 = import_module("zmd_e040_e036", e037.E036_RUNNER)
    e035 = import_module("zmd_e040_e035", e036.E035_RUNNER)
    e001 = import_module("zmd_e040_e001", e035.E001_RUNNER)
    e002 = import_module("zmd_e040_e002", e035.E002_RUNNER)
    e004 = import_module("zmd_e040_e004", e035.E004_RUNNER)
    e013 = import_module("zmd_e040_e013", E013_RUNNER)
    e014 = import_module("zmd_e040_e014", E014_RUNNER)
    e015 = import_module("zmd_e040_e015", E015_RUNNER)
    e017 = import_module("zmd_e040_e017", E017_RUNNER)
    e027 = import_module("zmd_e040_e027", e035.E027_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    solution = e035.solution_from_assignment(E039_ASSIGNMENT)
    endpoint = load_json(E039_ENDPOINT)
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != 157:
        raise RuntimeError("E040 parent endpoint drift")
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(mandatory, list):
        raise RuntimeError("E040 mandatory instance payload drift")
    observations, literals, observation_ids_by_literal = e035.build_incidence(
        solution=solution,
        endpoint=endpoint,
        pools=inputs["pools"],
        mandatory=mandatory,
        e013=e013,
    )
    allowed = {
        key: dict(payload)
        for key, payload in literals.items()
        if str(payload.get("kind"))
        in {"mandatory_group_pose", "optional_pose"}
        and str(payload.get("facility_type")) not in EXCLUDED_FACILITY_TYPES
        and len(payload.get("source_instance_ids", [])) == 1
    }
    coverage = e013.exact_max_coverage(
        observations=observations,
        literals=allowed,
        observation_ids_by_literal={key: observation_ids_by_literal[key] for key in allowed},
        budget=TARGET_BUDGET,
    )
    selected_keys = sorted(
        (str(key) for key in coverage["selected_literals"]),
        key=lambda key: (-len(observation_ids_by_literal[key]), key),
    )
    if len(selected_keys) != TARGET_BUDGET:
        raise RuntimeError("E040 selected target count drift")

    occupied, _owner_by_cell = e014.base_occupancy(solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)

    arm_summaries: list[dict[str, Any]] = []
    all_optimal: list[dict[str, Any]] = []
    aggregate_status = Counter()
    arm_manifest: list[dict[str, Any]] = []
    for index, key in enumerate(selected_keys, 1):
        target = allowed[key]
        path = checkpoint_path(index)
        if path.exists():
            arm = load_json(path)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E040 checkpoint: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E040_ARM_START",
                        "arm": index,
                        "target": key,
                        "coverage": len(observation_ids_by_literal[key]),
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            arm = e017.evaluate_arm(
                index=index,
                target=target,
                pair_solution=solution,
                occupied=occupied,
                selected_poles=selected_poles,
                inputs=inputs,
                power=power,
                e004=e004,
                e014=e014,
                e015=e015,
                runner_sha256=runner_sha256,
            )
            arm["schema"] = "zmd_zero_condition_e040_geometry_arm_v1"
            arm["target_coverage"] = len(observation_ids_by_literal[key])
            dump_exclusive(path, arm)
        arm_hash = sha256_file(path)
        arm_manifest.append(
            {
                "arm": index,
                "target": key,
                "path": str(path.relative_to(ROOT)),
                "sha256": arm_hash,
            }
        )
        aggregate_status.update(arm["status_counts"])
        optimal = [
            dict(record)
            for record in arm["candidate_records"]
            if str(record["shared_binding"]["status"]) == "OPTIMAL"
        ]
        for record in optimal:
            all_optimal.append(
                {
                    "arm": index,
                    "target": json_safe(target),
                    "target_coverage": len(observation_ids_by_literal[key]),
                    "checkpoint_path": str(path.relative_to(ROOT)),
                    "record": record,
                }
            )
        best_objective = (
            min(int(row["shared_binding"]["objective"]) for row in optimal)
            if optimal
            else None
        )
        arm_summaries.append(
            {
                "arm": index,
                "target": json_safe(target),
                "target_coverage": len(observation_ids_by_literal[key]),
                "alternative_count": int(arm["alternative_count"]),
                "geometry_change_count": sum(
                    not bool(row["same_footprint"])
                    for row in arm["candidate_records"]
                ),
                "same_footprint_count": sum(
                    bool(row["same_footprint"])
                    for row in arm["candidate_records"]
                ),
                "status_counts": json_safe(arm["status_counts"]),
                "best_objective": best_objective,
                "best_delta_from_parent": (
                    best_objective - PARENT_OBJECTIVE
                    if best_objective is not None
                    else None
                ),
                "checkpoint_path": str(path.relative_to(ROOT)),
                "checkpoint_sha256": arm_hash,
            }
        )

    dump_exclusive(
        ARM_MANIFEST_PATH,
        {
            "schema": "zmd_zero_condition_e040_arm_manifest_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "parent_objective": PARENT_OBJECTIVE,
            "selected_target_count": len(selected_keys),
            "arms": arm_manifest,
            "ledger_effect": "none",
        },
    )

    common = {
        "schema": "zmd_zero_condition_e040_geometry_mobility_discriminator_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "parent_objective": PARENT_OBJECTIVE,
        "observation_count": len(observations),
        "literal_count": len(literals),
        "allowed_target_count": len(allowed),
        "coverage_portfolio": json_safe(coverage),
        "selected_targets": [json_safe(allowed[key]) for key in selected_keys],
        "arm_summaries": arm_summaries,
        "status_counts": dict(sorted(aggregate_status.items())),
        "optimal_candidate_count": len(all_optimal),
        "arm_manifest_path": str(ARM_MANIFEST_PATH.relative_to(ROOT)),
        "arm_manifest_sha256": sha256_file(ARM_MANIFEST_PATH),
        "truth_boundary": (
            "Exhaustive fixed-outside pose alternatives for sixteen exact residual-"
            "coverage-selected current literals under one objective-157 parent."
        ),
        "ledger_effect": "none",
    }
    if not all_optimal:
        return {
            **common,
            "verdict": "CAUSAL_GEOMETRY_PORTFOLIO_NO_OPTIMAL_CHILD",
            "objective_distribution": {},
            "top_candidates": [],
            "best_child": None,
            "routing": {"status": "NOT_REACHED_NO_OPTIMAL_CHILD"},
            "decision": "CHANGE_OR_BROADEN_GEOMETRY_REPRESENTATION",
        }

    ranked = sorted(
        all_optimal,
        key=lambda row: (
            int(row["record"]["shared_binding"]["objective"]),
            -int(row["record"]["shared_binding"]["filtered_binding_option_count"]),
            -int(row["target_coverage"]),
            int(row["arm"]),
            int(row["record"]["pose_idx"]),
        ),
    )
    best = ranked[0]
    arm = load_json(ROOT / best["checkpoint_path"])
    record = best["record"]
    best_solution = e017.reconstruct_candidate(
        arm=arm,
        record=record,
        pair_solution=solution,
        inputs=inputs,
        e014=e014,
    )
    endpoint_best = e027.materialize_shared_endpoint(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=40999,
    )
    if int(endpoint_best["objective"]) != int(
        record["shared_binding"]["objective"]
    ):
        raise RuntimeError("E040 best endpoint materialization drift")
    dump_exclusive(
        BEST_ASSIGNMENT_PATH,
        {
            "schema": "zmd_zero_condition_e040_best_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint_best["objective"]),
            "target": best["target"],
            "replacement_pose_idx": int(record["pose_idx"]),
            "solution": best_solution,
        },
    )
    dump_exclusive(BEST_LAYOUT_PATH, e001.solution_layout(best_solution))
    dump_exclusive(BEST_ENDPOINT_PATH, endpoint_best)

    objective = int(endpoint_best["objective"])
    delta = objective - PARENT_OBJECTIVE
    if objective == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        verdict = "CAUSAL_GEOMETRY_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif delta <= -MATERIAL_IMPROVEMENT:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "CAUSAL_GEOMETRY_MATERIAL_SIGNAL"
        decision = "RETAIN_SEED_BUILD_SIMULTANEOUS_GEOMETRY_NEIGHBORHOOD"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "CAUSAL_GEOMETRY_UNARY_SATURATION_SIGNAL"
        decision = "BUILD_SIMULTANEOUS_GEOMETRY_NEIGHBORHOOD"
    distribution = Counter(
        int(row["record"]["shared_binding"]["objective"])
        for row in all_optimal
    )
    return {
        **common,
        "verdict": verdict,
        "objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "top_candidates": [
            {
                "arm": row["arm"],
                "target": row["target"],
                "target_coverage": row["target_coverage"],
                "pose_idx": int(row["record"]["pose_idx"]),
                "pose_id": str(row["record"]["pose_id"]),
                "same_footprint": bool(row["record"]["same_footprint"]),
                "objective": int(row["record"]["shared_binding"]["objective"]),
                "filtered_binding_option_count": int(
                    row["record"]["shared_binding"][
                        "filtered_binding_option_count"
                    ]
                ),
                "candidate_solution_digest": str(
                    row["record"]["candidate_solution_digest"]
                ),
            }
            for row in ranked[:30]
        ],
        "best_child": {
            "objective": objective,
            "delta_from_parent": delta,
            "target": best["target"],
            "target_coverage": int(best["target_coverage"]),
            "replacement_pose_idx": int(record["pose_idx"]),
            "replacement_pose_id": str(record["pose_id"]),
            "same_footprint": bool(record["same_footprint"]),
            "placement_digest": stable_digest(best_solution),
            "binding_selection_digest": endpoint_best["selection_digest"],
            "per_commodity": endpoint_best["per_commodity"],
            "positive_commodity_count": endpoint_best[
                "positive_commodity_count"
            ],
            "zero_mismatch_commodities": endpoint_best[
                "zero_mismatch_commodities"
            ],
            "morphology": endpoint_best["morphology"],
            "filtered_binding_option_count": endpoint_best[
                "filtered_binding_option_count"
            ],
            "assignment_path": str(BEST_ASSIGNMENT_PATH.relative_to(ROOT)),
            "assignment_sha256": sha256_file(BEST_ASSIGNMENT_PATH),
            "layout_path": str(BEST_LAYOUT_PATH.relative_to(ROOT)),
            "layout_sha256": sha256_file(BEST_LAYOUT_PATH),
            "endpoint_path": str(BEST_ENDPOINT_PATH.relative_to(ROOT)),
            "endpoint_sha256": sha256_file(BEST_ENDPOINT_PATH),
        },
        "power_semantics": power["summary"],
        "routing": routing,
        "decision": decision,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E040 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "selected_target_count": len(result["selected_targets"]),
                    "status_counts": result["status_counts"],
                    "optimal_candidate_count": result["optimal_candidate_count"],
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
            "schema": "zmd_zero_condition_e040_geometry_mobility_discriminator_failure_v1",
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
