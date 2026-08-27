#!/usr/bin/env python3
"""E053 target-first executor over the merged fourteen-body 6x4 context."""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HELPER = ROOT / "research_lab/campaigns/zero_condition/experiments/E053_merged_6x4_first_zero_joint/run_e053.py"
EXPECTED_HELPER_SHA256 = "4d7e19c30471ffcb9abe68e7b5324bf9703881d6159aa91a46f79ba61ad605ef"
TARGET_COMMODITY = "fine_buckwheat_powder"


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


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def compact(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"joint_selection", "joint_port_specs", "selected_pattern_by_block"}
    }


def run() -> dict[str, Any]:
    actual_helper = sha256_file(HELPER)
    if actual_helper != EXPECTED_HELPER_SHA256:
        raise RuntimeError(
            f"E053 helper drift: {actual_helper} != {EXPECTED_HELPER_SHA256}"
        )
    helper = import_module("zmd_e053_target_helper", HELPER)
    identity = helper.verify_identity()
    identity["helper_sha256"] = actual_helper
    identity["executor_sha256"] = sha256_file(Path(__file__).resolve())

    e051 = import_module("zmd_e053_target_e051", helper.E051_RUNNER)
    base = e051.reconstruct_context()
    expanded = helper.expanded_context(base)
    e041 = base["e041"]

    fixed_state = e041.fixed_state_for_solution(
        solution=base["best_solution"],
        blocks=expanded["blocks"],
        selected_ids_by_block=expanded["selected_ids_by_block"],
        pools=base["inputs"]["pools"],
    )
    calibration_built = helper.build_joint(
        base,
        expanded,
        fixed_state=fixed_state,
        warm_solution=base["best_solution"],
        warm_endpoint=base["best_endpoint"],
    )
    with helper.heartbeat("target_executor_calibration"):
        calibration = e041.solve_mode_joint(
            calibration_built,
            time_limit_seconds=45.0,
            random_seed=53101,
        )
    if calibration["status"] != "OPTIMAL" or int(calibration["objective"]) != 139:
        return {
            "schema": "zmd_zero_condition_e053_target_first_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "MERGED_6X4_CALIBRATION_REJECTED",
            "identity": identity,
            "calibration": compact(calibration),
            "decision": "REPAIR_MERGED_6X4_CONTEXT",
            "ledger_effect": "none",
        }

    built = helper.build_joint(
        base,
        expanded,
        fixed_state=None,
        warm_solution=base["best_solution"],
        warm_endpoint=base["best_endpoint"],
    )
    positive_vars, total_expr = e051.attach_positive_variables(
        built,
        prefix="e053_target_first",
    )
    built["binding_model"].model.Add(
        cp_model.LinearExpr.Sum(
            list(built["compiled"]["mismatch_vars"][TARGET_COMMODITY].values())
        )
        == 0
    )
    built["binding_model"].model.Minimize(total_expr)
    target = helper.solve_variant(
        built,
        positive_vars=positive_vars,
        random_seed=53102,
        objective_kind="total_mismatch",
        seconds=180.0,
    )
    common = {
        "schema": "zmd_zero_condition_e053_target_first_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "parent_objective": 139,
        "expanded_context": {
            "context_digest": expanded["context_digest"],
            "block_count": len(expanded["blocks"]),
            "selected_instance_count": sum(
                len(values) for values in expanded["selected_ids_by_block"].values()
            ),
            "merged_6x4_size": len(
                expanded["selected_ids_by_block"]["6x4_merged"]
            ),
            "added_instance_ids": expanded["added_instance_ids"],
            "mode_enabled_destination_count": sum(
                bool(row["mode_enabled"]) for row in expanded["mode_summary"]
            ),
            "exchangeability_audit": expanded["exchangeability"],
        },
        "calibration": compact(calibration),
        "target_commodity": TARGET_COMMODITY,
        "target_zero_solve": compact(target),
        "truth_boundary": (
            "E050 Seed C occupied geometry with the fourteen-body merged 6x4 "
            "assignment block and inherited bounded conditional contexts only."
        ),
        "ledger_effect": "none",
    }
    if target["status"] == "INFEASIBLE":
        return {
            **common,
            "verdict": "MERGED_6X4_TARGET_ZERO_INFEASIBLE",
            "materialized": None,
            "routing": {"status": "NOT_REACHED_NO_FIRST_ZERO"},
            "decision": "BUILD_NATIVE_SIMULTANEOUS_BODY_CONTEXT",
        }
    if target["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return {
            **common,
            "verdict": "MERGED_6X4_TARGET_ZERO_NONTERMINAL",
            "materialized": None,
            "routing": {"status": "NOT_REACHED_TARGET_SOLVE_NONTERMINAL"},
            "decision": "CONTINUE_TARGET_ZERO_SOLVE",
        }
    if int(target["per_commodity"][TARGET_COMMODITY]) != 0:
        raise RuntimeError("E053 target solve lost required zero")

    materialized = helper.materialize_and_replay(
        base,
        expanded,
        target,
        optimum_positive_count=int(target["positive_commodity_count"]),
        required_zero_commodities=[TARGET_COMMODITY],
    )
    if int(target["positive_commodity_count"]) == 0:
        verdict = "MERGED_6X4_COMPONENT_COMPATIBLE_BINDING"
        decision = "ENTER_EXACT_ROUTING"
        routing_status = "READY_COMPONENT_COMPATIBLE_BINDING"
    elif target["status"] == "OPTIMAL":
        verdict = "MERGED_6X4_TARGET_FIRST_ZERO_OPTIMAL"
        decision = "RECOMPUTE_RESIDUAL_WITH_POSITIVE_COUNT_PRIORITY"
        routing_status = "NOT_REACHED_POSITIVE_SHARED_MISMATCH"
    else:
        verdict = "MERGED_6X4_TARGET_FIRST_ZERO_FEASIBLE_NONTERMINAL"
        decision = "RETAIN_FIRST_ZERO_AND_CONTINUE_TARGET_TOTAL_SOLVE"
        routing_status = "NOT_REACHED_POSITIVE_SHARED_MISMATCH"
    return {
        **common,
        "verdict": verdict,
        "materialized": materialized,
        "routing": {"status": routing_status},
        "decision": decision,
    }


def main() -> int:
    helper = import_module("zmd_e053_target_paths", HELPER)
    if helper.RESULT_PATH.exists():
        raise FileExistsError("refusing to overwrite E053 run-002 result")
    try:
        result = run()
        dump_exclusive(helper.RESULT_PATH, result)
        target = result.get("target_zero_solve", {})
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "calibration": {
                        "status": result["calibration"]["status"],
                        "objective": result["calibration"].get("objective"),
                    },
                    "target_status": target.get("status"),
                    "target_total": target.get("total_mismatch"),
                    "target_positive": target.get("positive_commodity_count"),
                    "target_zeros": target.get("zero_mismatch_commodities"),
                    "decision": result["decision"],
                    "result_path": str(helper.RESULT_PATH),
                    "result_sha256": sha256_file(helper.RESULT_PATH),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e053_target_first_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not helper.FAILURE_PATH.exists():
            dump_exclusive(helper.FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
