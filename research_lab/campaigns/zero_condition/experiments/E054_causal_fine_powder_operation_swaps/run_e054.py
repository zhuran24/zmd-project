#!/usr/bin/env python3
"""E054: seed the E053 context with nine causal capsule/grinder swaps."""

from __future__ import annotations

import copy
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

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / "research_lab/local/zero_condition/E054_causal_fine_powder_operation_swaps/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
PAIR_MANIFEST_PATH = OUT / "PAIR_MANIFEST.json"
BEST_WITNESS_PATH = OUT / "BEST_JOINT_WITNESS.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_LAYOUT.json"

E053_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E053_merged_6x4_first_zero_joint/run_e053.py"
)
E053_NONTERMINAL_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E053_merged_6x4_first_zero_joint/"
    "run-002/RESULT.json"
)
E051_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E051_positive_commodity_frontier/run_e051.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "283000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E053_HELPER: "4d7e19c30471ffcb9abe68e7b5324bf9703881d6159aa91a46f79ba61ad605ef",
    E053_NONTERMINAL_RESULT: "4637ba7a8314ab5ea70359d56b405f4cf1365253b87a161303443815d32bfe0b",
    E051_RUNNER: "e287c3c4323494b894792435b44fe2c23458345ca2f7409b06309170e9c4ca87",
}

TARGET_COMMODITY = "fine_buckwheat_powder"
RIGHT_SOURCE_IDS = (
    "grinder_fine_buckwheat_004",
    "grinder_fine_buckwheat_005",
    "grinder_fine_buckwheat_006",
)
CAPSULE_IDS = (
    "filling_capsule_001",
    "filling_capsule_002",
    "filling_capsule_003",
)
ALL_RELEVANT_IDS = set(RIGHT_SOURCE_IDS) | set(CAPSULE_IDS)
FEASIBILITY_SECONDS = 30.0
TOTAL_SECONDS = 180.0


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
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    mismatches = {
        key: {"expected": expected, "actual": os.environ.get(key)}
        for key, expected in EXPECTED_ENV.items()
        if os.environ.get(key) != expected
    }
    if mismatches:
        raise RuntimeError(f"environment mismatch: {mismatches}")
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual}")
    nonterminal = load_json(E053_NONTERMINAL_RESULT)
    if nonterminal.get("verdict") != "MERGED_6X4_TARGET_ZERO_NONTERMINAL":
        raise RuntimeError("E054 E053 trigger verdict drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def extend_relevant_modes(
    base: Mapping[str, Any],
    expanded: Mapping[str, Any],
) -> dict[str, Any]:
    inherited = {
        str(row["source_instance_id"])
        for row in expanded["mode_summary"]
        if bool(row["mode_enabled"])
    }
    mode_enabled = inherited | ALL_RELEVANT_IDS
    blocks, summary = base["e041"].enrich_blocks_with_modes(
        blocks=[copy.deepcopy(block) for block in expanded["blocks"]],
        solution=base["best_solution"],
        selected_ids_by_block=expanded["selected_ids_by_block"],
        mode_enabled_ids=mode_enabled,
        pools=base["inputs"]["pools"],
    )
    return {
        **expanded,
        "blocks": blocks,
        "mode_summary": summary,
        "mode_enabled_ids": sorted(mode_enabled),
        "context_digest": stable_digest(
            {
                "blocks": blocks,
                "selected_ids_by_block": {
                    key: sorted(values)
                    for key, values in expanded["selected_ids_by_block"].items()
                },
                "mode_summary": summary,
            }
        ),
    }


def current_state_maps(
    base: Mapping[str, Any],
    expanded: Mapping[str, Any],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[str, tuple[str, int]],
]:
    by_location: dict[tuple[str, int], dict[str, Any]] = {}
    by_instance: dict[str, tuple[str, int]] = {}
    for block in expanded["blocks"]:
        block_id = str(block["block_id"])
        states = base["e041"].destination_state_for_solution(
            solution=base["best_solution"],
            block=block,
            selected_ids=expanded["selected_ids_by_block"][block_id],
            pools=base["inputs"]["pools"],
        )
        for state in states:
            location = (block_id, int(state["destination"]))
            by_location[location] = dict(state)
            by_instance[str(state["instance_id"])] = location
    if not ALL_RELEVANT_IDS.issubset(by_instance):
        raise RuntimeError("E054 relevant instance missing from expanded context")
    return by_location, by_instance


def constrain_swap(
    built: Mapping[str, Any],
    *,
    state_by_location: Mapping[tuple[str, int], Mapping[str, Any]],
    source_location: tuple[str, int],
    capsule_location: tuple[str, int],
) -> None:
    block_by_id = {str(block["block_id"]): block for block in built["blocks"]}
    swapped = {source_location, capsule_location}
    for (block_id, destination, mode_index, operation), variable in built["y_vars"].items():
        location = (str(block_id), int(destination))
        current = state_by_location[location]
        if location == source_location:
            desired_operation = "filling_capsule"
        elif location == capsule_location:
            desired_operation = "grinder_fine_buckwheat"
        else:
            desired_operation = str(current["operation"])
        pose_idx = int(
            block_by_id[str(block_id)]["mode_pose_indices_by_destination"][
                int(destination)
            ][int(mode_index)]
        )
        if str(operation) != desired_operation:
            built["binding_model"].model.Add(variable == 0)
        elif location not in swapped and pose_idx != int(current["pose_idx"]):
            built["binding_model"].model.Add(variable == 0)
        elif location not in swapped:
            built["binding_model"].model.Add(variable == 1)


def build_pair_model(
    helper: Any,
    e051: Any,
    base: Mapping[str, Any],
    expanded: Mapping[str, Any],
    *,
    state_by_location: Mapping[tuple[str, int], Mapping[str, Any]],
    source_location: tuple[str, int],
    capsule_location: tuple[str, int],
    objective: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    built = helper.build_joint(
        base,
        expanded,
        fixed_state=None,
        warm_solution=base["best_solution"],
        warm_endpoint=base["best_endpoint"],
    )
    positive_vars, total_expr = e051.attach_positive_variables(
        built,
        prefix=f"e054_{source_location[1]}_{capsule_location[1]}_{objective}",
    )
    constrain_swap(
        built,
        state_by_location=state_by_location,
        source_location=source_location,
        capsule_location=capsule_location,
    )
    built["binding_model"].model.Add(
        cp_model.LinearExpr.Sum(
            list(built["compiled"]["mismatch_vars"][TARGET_COMMODITY].values())
        )
        == 0
    )
    if objective == "feasibility":
        built["binding_model"].model.Minimize(0)
    elif objective == "total_mismatch":
        built["binding_model"].model.Minimize(total_expr)
    else:
        raise ValueError(objective)
    return built, positive_vars


def run() -> dict[str, Any]:
    identity = verify_identity()
    helper = import_module("zmd_e054_e053", E053_HELPER)
    e051 = import_module("zmd_e054_e051", E051_RUNNER)
    base = e051.reconstruct_context()
    base["e051"] = e051
    expanded = extend_relevant_modes(base, helper.expanded_context(base))
    state_by_location, location_by_instance = current_state_maps(base, expanded)

    calibration_state = base["e041"].fixed_state_for_solution(
        solution=base["best_solution"],
        blocks=expanded["blocks"],
        selected_ids_by_block=expanded["selected_ids_by_block"],
        pools=base["inputs"]["pools"],
    )
    calibration_built = helper.build_joint(
        base,
        expanded,
        fixed_state=calibration_state,
        warm_solution=base["best_solution"],
        warm_endpoint=base["best_endpoint"],
    )
    with helper.heartbeat("e054_calibration"):
        calibration = base["e041"].solve_mode_joint(
            calibration_built,
            time_limit_seconds=45.0,
            random_seed=54001,
        )
    if calibration["status"] != "OPTIMAL" or int(calibration["objective"]) != 139:
        return {
            "schema": "zmd_zero_condition_e054_causal_operation_swaps_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "E054_CONTEXT_CALIBRATION_REJECTED",
            "identity": identity,
            "calibration": helper.compact(calibration),
            "decision": "REPAIR_RELEVANT_MODE_CONTEXT",
            "ledger_effect": "none",
        }

    pair_records: list[dict[str, Any]] = []
    for source_id in RIGHT_SOURCE_IDS:
        for capsule_id in CAPSULE_IDS:
            source_location = location_by_instance[source_id]
            capsule_location = location_by_instance[capsule_id]
            built, positive_vars = build_pair_model(
                helper,
                e051,
                base,
                expanded,
                state_by_location=state_by_location,
                source_location=source_location,
                capsule_location=capsule_location,
                objective="feasibility",
            )
            result = helper.solve_variant(
                built,
                positive_vars=positive_vars,
                random_seed=54100 + len(pair_records),
                objective_kind="feasibility",
                seconds=FEASIBILITY_SECONDS,
            )
            pair_records.append(
                {
                    "pair_key": f"{source_id}<->{capsule_id}",
                    "source_instance_id": source_id,
                    "capsule_instance_id": capsule_id,
                    "source_location": list(source_location),
                    "capsule_location": list(capsule_location),
                    "solve": helper.compact(result),
                }
            )
            print(
                json.dumps(
                    {
                        "event": "E054_PAIR_DONE",
                        "pair": pair_records[-1]["pair_key"],
                        "status": result["status"],
                        "total": result.get("total_mismatch"),
                        "positive": result.get("positive_commodity_count"),
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    dump_exclusive(
        PAIR_MANIFEST_PATH,
        {
            "schema": "zmd_zero_condition_e054_pair_manifest_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "context_digest": expanded["context_digest"],
            "pairs": pair_records,
            "ledger_effect": "none",
        },
    )
    feasible = [
        row
        for row in pair_records
        if row["solve"]["status"] in {"OPTIMAL", "FEASIBLE"}
    ]
    if not feasible:
        statuses = {row["solve"]["status"] for row in pair_records}
        verdict = (
            "CAUSAL_OPERATION_SWAPS_INFEASIBLE"
            if statuses == {"INFEASIBLE"}
            else "CAUSAL_OPERATION_SWAPS_NONTERMINAL"
        )
        decision = (
            "BUILD_NATIVE_MULTI_OPERATION_OR_BODY_CONTEXT"
            if verdict.endswith("INFEASIBLE")
            else "CONTINUE_NONTERMINAL_SWAP_SOLVES"
        )
        return {
            "schema": "zmd_zero_condition_e054_causal_operation_swaps_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": verdict,
            "identity": identity,
            "calibration": helper.compact(calibration),
            "expanded_context": {
                "context_digest": expanded["context_digest"],
                "mode_enabled_destination_count": sum(
                    bool(row["mode_enabled"]) for row in expanded["mode_summary"]
                ),
            },
            "pair_manifest_path": str(PAIR_MANIFEST_PATH.relative_to(ROOT)),
            "pair_manifest_sha256": sha256_file(PAIR_MANIFEST_PATH),
            "pair_records": pair_records,
            "best_pair": None,
            "decision": decision,
            "ledger_effect": "none",
        }

    feasible.sort(
        key=lambda row: (
            int(row["solve"]["positive_commodity_count"]),
            int(row["solve"]["total_mismatch"]),
            str(row["pair_key"]),
        )
    )
    selected = feasible[0]
    source_location = tuple(selected["source_location"])
    capsule_location = tuple(selected["capsule_location"])
    total_built, total_positive = build_pair_model(
        helper,
        e051,
        base,
        expanded,
        state_by_location=state_by_location,
        source_location=(str(source_location[0]), int(source_location[1])),
        capsule_location=(str(capsule_location[0]), int(capsule_location[1])),
        objective="total_mismatch",
    )
    total_result = helper.solve_variant(
        total_built,
        positive_vars=total_positive,
        random_seed=54999,
        objective_kind="total_mismatch",
        seconds=TOTAL_SECONDS,
    )

    materialized = None
    if total_result["status"] == "OPTIMAL":
        old_paths = (
            helper.BEST_WITNESS_PATH,
            helper.BEST_ASSIGNMENT_PATH,
            helper.BEST_LAYOUT_PATH,
        )
        helper.BEST_WITNESS_PATH = BEST_WITNESS_PATH
        helper.BEST_ASSIGNMENT_PATH = BEST_ASSIGNMENT_PATH
        helper.BEST_LAYOUT_PATH = BEST_LAYOUT_PATH
        try:
            materialized = helper.materialize_and_replay(
                base,
                expanded,
                total_result,
                optimum_positive_count=int(total_result["positive_commodity_count"]),
                required_zero_commodities=[TARGET_COMMODITY],
            )
        finally:
            (
                helper.BEST_WITNESS_PATH,
                helper.BEST_ASSIGNMENT_PATH,
                helper.BEST_LAYOUT_PATH,
            ) = old_paths

    if total_result["status"] == "OPTIMAL":
        verdict = "CAUSAL_OPERATION_SWAP_FIRST_ZERO_OPTIMAL"
        decision = "RECOMPUTE_RESIDUAL_WITH_POSITIVE_COUNT_PRIORITY"
    elif total_result["status"] == "FEASIBLE":
        verdict = "CAUSAL_OPERATION_SWAP_FIRST_ZERO_FEASIBLE_NONTERMINAL"
        decision = "RETAIN_WITNESS_AND_CONTINUE_TOTAL_SOLVE"
    else:
        verdict = "CAUSAL_OPERATION_SWAP_TOTAL_NONTERMINAL"
        decision = "RETAIN_FEASIBLE_PAIR_AND_CONTINUE_TOTAL_SOLVE"

    return {
        "schema": "zmd_zero_condition_e054_causal_operation_swaps_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "calibration": helper.compact(calibration),
        "expanded_context": {
            "context_digest": expanded["context_digest"],
            "mode_enabled_destination_count": sum(
                bool(row["mode_enabled"]) for row in expanded["mode_summary"]
            ),
        },
        "pair_manifest_path": str(PAIR_MANIFEST_PATH.relative_to(ROOT)),
        "pair_manifest_sha256": sha256_file(PAIR_MANIFEST_PATH),
        "pair_records": pair_records,
        "feasible_pair_count": len(feasible),
        "selected_pair": selected,
        "total_optimization": helper.compact(total_result),
        "materialized": materialized,
        "decision": decision,
        "truth_boundary": (
            "Nine capsule/right-edge-grinder operation swaps under E053's frozen "
            "occupied geometry and expanded relevant-mode context only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists() or PAIR_MANIFEST_PATH.exists():
        raise FileExistsError("refusing to overwrite E054 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        total = result.get("total_optimization", {})
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "feasible_pairs": result.get("feasible_pair_count", 0),
                    "selected_pair": (
                        result.get("selected_pair", {}).get("pair_key")
                    ),
                    "total_status": total.get("status"),
                    "total_mismatch": total.get("total_mismatch"),
                    "positive_count": total.get("positive_commodity_count"),
                    "zero_commodities": total.get("zero_mismatch_commodities"),
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
            "schema": "zmd_zero_condition_e054_causal_operation_swaps_failure_v1",
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
