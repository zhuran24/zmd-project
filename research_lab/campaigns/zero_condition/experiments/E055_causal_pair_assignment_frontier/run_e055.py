#!/usr/bin/env python3
"""E055: minimize positive commodity count with one causal pair relation retained."""

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
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / "research_lab/local/zero_condition/E055_causal_pair_assignment_frontier/run-002"
POSITIVE_PATH = OUT / "POSITIVE_RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E054_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E054_causal_fine_powder_operation_swaps/"
    "run-001/RESULT.json"
)
E054_ASSIGNMENT = E054_RESULT.with_name("BEST_ASSIGNMENT.json")
E054_WITNESS = E054_RESULT.with_name("BEST_JOINT_WITNESS.json")
E054_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E054_causal_fine_powder_operation_swaps/run_e054.py"
)
E053_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E053_merged_6x4_first_zero_joint/run_e053.py"
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
    "EXACT_MASTER_RANDOM_SEED": "285000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E054_RESULT: "c2055940969cd97e7e2d454fc9e859acd06d154e710bb362af34a97238d38412",
    E054_ASSIGNMENT: "c32d7516e52b0d84b10520b998c3ac7d65bdb4d18ab5763ad09a717fc71be131",
    E054_WITNESS: "16102d76fd94694cd99d7ac554c78bb4af03f76af82b69962e906352f6d8eeb5",
    E054_RUNNER: "5b92368f3219b4e5f4d62c58e9a9f8cae4bc6f2d9f4d07932fdcfac4e60e5ad2",
    E053_HELPER: "4d7e19c30471ffcb9abe68e7b5324bf9703881d6159aa91a46f79ba61ad605ef",
    E051_RUNNER: "e287c3c4323494b894792435b44fe2c23458345ca2f7409b06309170e9c4ca87",
}

TARGET_COMMODITY = "fine_buckwheat_powder"
SOURCE_INSTANCE = "grinder_fine_buckwheat_004"
CAPSULE_INSTANCE = "filling_capsule_003"
MERGED_BLOCK = "6x4_merged"
EXPECTED_TOTAL = 139
EXPECTED_POSITIVE = 18
CALIBRATION_SECONDS = 45.0
POSITIVE_SECONDS = 180.0


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
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
    ).strip()


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
        key: {"expected": value, "actual": os.environ.get(key)}
        for key, value in EXPECTED_ENV.items()
        if os.environ.get(key) != value
    }
    unexpected_exact = sorted(
        key for key in os.environ if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected_exact:
        raise RuntimeError(
            f"environment mismatch: mismatches={mismatches} "
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
    result = load_json(E054_RESULT)
    if result.get("verdict") != "CAUSAL_OPERATION_SWAP_FIRST_ZERO_OPTIMAL":
        raise RuntimeError("E055 E054 trigger verdict drift")
    total = result.get("total_optimization", {})
    if (
        total.get("status") != "OPTIMAL"
        or int(total.get("total_mismatch", -1)) != EXPECTED_TOTAL
        or int(total.get("positive_commodity_count", -1)) != EXPECTED_POSITIVE
    ):
        raise RuntimeError("E055 E054 selected state drift")
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


def state_maps(
    base: Mapping[str, Any],
    expanded: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, tuple[str, int]]]:
    by_location: dict[tuple[str, int], dict[str, Any]] = {}
    by_instance: dict[str, tuple[str, int]] = {}
    for block in expanded["blocks"]:
        block_id = str(block["block_id"])
        states = base["e041"].destination_state_for_solution(
            solution=solution,
            block=block,
            selected_ids=expanded["selected_ids_by_block"][block_id],
            pools=base["inputs"]["pools"],
        )
        for state in states:
            location = (block_id, int(state["destination"]))
            row = dict(state)
            by_location[location] = row
            by_instance[str(row["instance_id"])] = location
    return by_location, by_instance


def reconstruct() -> dict[str, Any]:
    e054 = import_module("zmd_e055_e054", E054_RUNNER)
    helper = import_module("zmd_e055_e053", E053_HELPER)
    e051 = import_module("zmd_e055_e051", E051_RUNNER)
    base = e051.reconstruct_context()
    base["e051"] = e051
    expanded = e054.extend_relevant_modes(base, helper.expanded_context(base))
    warm_solution = base["e041"].solution_from_assignment(E054_ASSIGNMENT)
    warm_witness = load_json(E054_WITNESS)
    state_by_location, _location_by_instance = state_maps(
        base,
        expanded,
        warm_solution,
    )
    selected_pair = load_json(E054_RESULT)["selected_pair"]
    if (
        str(selected_pair["source_instance_id"]) != SOURCE_INSTANCE
        or str(selected_pair["capsule_instance_id"]) != CAPSULE_INSTANCE
    ):
        raise RuntimeError("E055 selected causal pair identity drift")
    source_location = (
        str(selected_pair["source_location"][0]),
        int(selected_pair["source_location"][1]),
    )
    capsule_location = (
        str(selected_pair["capsule_location"][0]),
        int(selected_pair["capsule_location"][1]),
    )
    if source_location not in state_by_location or capsule_location not in state_by_location:
        raise RuntimeError("E055 selected causal locations missing from expanded context")
    if source_location[0] != MERGED_BLOCK or capsule_location[0] != MERGED_BLOCK:
        raise RuntimeError("E055 selected causal pair left merged 6x4 block")
    if str(state_by_location[source_location]["operation"]) != "filling_capsule":
        raise RuntimeError("E055 source body does not carry capsule operation")
    if str(state_by_location[capsule_location]["operation"]) != "grinder_fine_buckwheat":
        raise RuntimeError("E055 capsule body does not carry grinder operation")
    return {
        "e054": e054,
        "helper": helper,
        "e051": e051,
        "base": base,
        "expanded": expanded,
        "warm_solution": warm_solution,
        "warm_witness": warm_witness,
        "state_by_location": state_by_location,
        "source_location": source_location,
        "capsule_location": capsule_location,
    }


def constrain_assignment_frontier(
    built: Mapping[str, Any],
    context: Mapping[str, Any],
) -> None:
    block_by_id = {str(row["block_id"]): row for row in built["blocks"]}
    state_by_location = context["state_by_location"]
    source_location = context["source_location"]
    capsule_location = context["capsule_location"]
    for (block_id, destination, mode_index, operation), variable in built["y_vars"].items():
        location = (str(block_id), int(destination))
        current = state_by_location[location]
        pose_idx = int(
            block_by_id[str(block_id)]["mode_pose_indices_by_destination"][
                int(destination)
            ][int(mode_index)]
        )
        current_pose = int(current["pose_idx"])
        if pose_idx != current_pose:
            built["binding_model"].model.Add(variable == 0)
            continue
        if location == source_location:
            if str(operation) != "filling_capsule":
                built["binding_model"].model.Add(variable == 0)
            continue
        if location == capsule_location:
            if str(operation) != "grinder_fine_buckwheat":
                built["binding_model"].model.Add(variable == 0)
            continue
        if str(block_id) != MERGED_BLOCK:
            built["binding_model"].model.Add(
                variable == int(str(operation) == str(current["operation"]))
            )


def build_variant(
    context: Mapping[str, Any],
    *,
    fixed_state: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    objective_kind: str,
    positive_target: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = context["base"]
    expanded = context["expanded"]
    helper = context["helper"]
    built = helper.build_joint(
        base,
        expanded,
        fixed_state=fixed_state,
        warm_solution=context["warm_solution"],
        warm_endpoint={"selection": context["warm_witness"]["joint_selection"]},
    )
    positive_vars, total_expr = context["e051"].attach_positive_variables(
        built,
        prefix=f"e055_{objective_kind}",
    )
    constrain_assignment_frontier(built, context)
    built["binding_model"].model.Add(
        cp_model.LinearExpr.Sum(
            list(built["compiled"]["mismatch_vars"][TARGET_COMMODITY].values())
        )
        == 0
    )
    positive_expr = cp_model.LinearExpr.Sum(list(positive_vars.values()))
    if positive_target is not None:
        built["binding_model"].model.Add(positive_expr == int(positive_target))
    if objective_kind == "positive_count":
        built["binding_model"].model.Minimize(positive_expr)
    elif objective_kind == "total_mismatch":
        built["binding_model"].model.Minimize(total_expr)
    else:
        raise ValueError(objective_kind)
    return built, positive_vars


def run() -> dict[str, Any]:
    identity = verify_identity()
    context = reconstruct()
    base = context["base"]
    expanded = context["expanded"]
    fixed_state = base["e041"].fixed_state_for_solution(
        solution=context["warm_solution"],
        blocks=expanded["blocks"],
        selected_ids_by_block=expanded["selected_ids_by_block"],
        pools=base["inputs"]["pools"],
    )
    calibration_built, calibration_positive = build_variant(
        context,
        fixed_state=fixed_state,
        objective_kind="total_mismatch",
        positive_target=EXPECTED_POSITIVE,
    )
    with context["helper"].heartbeat("e055_calibration"):
        calibration = context["helper"].solve_variant(
            calibration_built,
            positive_vars=calibration_positive,
            random_seed=55001,
            objective_kind="total_mismatch",
            seconds=CALIBRATION_SECONDS,
        )
    if (
        calibration["status"] != "OPTIMAL"
        or int(calibration["total_mismatch"]) != EXPECTED_TOTAL
        or int(calibration["positive_commodity_count"]) != EXPECTED_POSITIVE
        or TARGET_COMMODITY not in calibration["zero_mismatch_commodities"]
    ):
        return {
            "schema": "zmd_zero_condition_e055_assignment_frontier_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "E055_CALIBRATION_REJECTED",
            "identity": identity,
            "calibration": context["helper"].compact(calibration),
            "positive_solve": None,
            "decision": "REPAIR_E054_CONTEXT_REPLAY",
            "ledger_effect": "none",
        }

    positive_built, positive_vars = build_variant(
        context,
        fixed_state=None,
        objective_kind="positive_count",
    )
    positive = context["helper"].solve_variant(
        positive_built,
        positive_vars=positive_vars,
        random_seed=55101,
        objective_kind="positive_count",
        seconds=POSITIVE_SECONDS,
    )
    if positive["status"] == "OPTIMAL":
        count = int(positive["positive_commodity_count"])
        verdict = (
            "ASSIGNMENT_FRONTIER_SECOND_ZERO_OPTIMAL"
            if count <= 17
            else "ASSIGNMENT_FRONTIER_ONE_ZERO_OPTIMAL"
        )
        decision = "MINIMIZE_TOTAL_ON_POSITIVE_FACE"
    elif positive["status"] == "FEASIBLE":
        verdict = "ASSIGNMENT_FRONTIER_FEASIBLE_NONTERMINAL"
        decision = "RETAIN_WITNESS_AND_CONTINUE_POSITIVE_SOLVE"
    elif positive["status"] == "INFEASIBLE":
        verdict = "ASSIGNMENT_FRONTIER_INFEASIBLE"
        decision = "AUDIT_CONSTRAINT_TRANSPORT"
    else:
        verdict = "ASSIGNMENT_FRONTIER_NONTERMINAL"
        decision = "REFINE_ASSIGNMENT_SYMMETRY_OR_CONTINUE_SOLVE"

    payload = {
        "schema": "zmd_zero_condition_e055_assignment_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "context": {
            "context_digest": expanded["context_digest"],
            "merged_block_destination_count": next(
                int(row["destination_count"])
                for row in positive_built["blocks"]
                if str(row["block_id"]) == MERGED_BLOCK
            ),
            "source_location": list(context["source_location"]),
            "capsule_location": list(context["capsule_location"]),
            "fixed_port_modes": True,
            "released_operation_block": MERGED_BLOCK,
        },
        "calibration": context["helper"].compact(calibration),
        "positive_solve": context["helper"].compact(positive),
        "decision": decision,
        "truth_boundary": (
            "E054 occupied geometry and selected causal relation; all port modes "
            "and non-6x4 operations fixed, remaining fourteen-body 6x4 operation "
            "assignment and binding free."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(POSITIVE_PATH, payload)
    return payload


def main() -> int:
    if POSITIVE_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E055 positive result")
    try:
        result = run()
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "calibration": result["calibration"],
                    "positive_solve": result["positive_solve"],
                    "decision": result["decision"],
                    "result_path": str(POSITIVE_PATH),
                    "result_sha256": sha256_file(POSITIVE_PATH),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e055_assignment_frontier_failure_v1",
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
