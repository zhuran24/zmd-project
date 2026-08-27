#!/usr/bin/env python3
"""E056: minimize positive commodity count with 6x4 port modes released."""

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
OUT = ROOT / "research_lab/local/zero_condition/E056_causal_pair_mode_frontier/run-001"
POSITIVE_PATH = OUT / "POSITIVE_RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E055_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E055_causal_pair_assignment_frontier/"
    "run-002/RESULT.json"
)
E055_ASSIGNMENT = E055_RESULT.with_name("BEST_ASSIGNMENT.json")
E055_WITNESS = E055_RESULT.with_name("BEST_JOINT_WITNESS.json")
E055_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E055_causal_pair_assignment_frontier/run_e055.py"
)
E053_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E053_merged_6x4_first_zero_joint/run_e053.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "286000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E055_RESULT: "5a81cd6c58151643b345a888f8bd782ba9c5bbdfe00c21e5ac2beccc90576efa",
    E055_ASSIGNMENT: "bf6d1cfcd4c6aaf649a16b9513044b2023b5a9a1a5b39267ebcaad15ffe2c46b",
    E055_WITNESS: "3b36ad647149af238567b3746e165fc60fbd107d47b10d8ba92bf15e4e2ab559",
    E055_RUNNER: "5722d921d66f4bd4b7126c42a9be50d47ee4cb2c7c0873f2a3f161d402cabad6",
    E053_HELPER: "4d7e19c30471ffcb9abe68e7b5324bf9703881d6159aa91a46f79ba61ad605ef",
}

TARGET_COMMODITY = "fine_buckwheat_powder"
MERGED_BLOCK = "6x4_merged"
EXPECTED_TOTAL = 139
EXPECTED_POSITIVE = 18
CALIBRATION_SECONDS = 45.0
POSITIVE_SECONDS = 210.0


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
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


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
    result = load_json(E055_RESULT)
    if result.get("verdict") != "ASSIGNMENT_FRONTIER_LEX_SATURATED_AT_18_139":
        raise RuntimeError("E056 E055 trigger verdict drift")
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


def reconstruct() -> dict[str, Any]:
    e055 = import_module("zmd_e056_e055", E055_RUNNER)
    helper = import_module("zmd_e056_e053", E053_HELPER)
    context = e055.reconstruct()
    warm_solution = context["base"]["e041"].solution_from_assignment(E055_ASSIGNMENT)
    warm_witness = load_json(E055_WITNESS)
    state_by_location, _ = e055.state_maps(
        context["base"],
        context["expanded"],
        warm_solution,
    )
    context.update(
        {
            "e055": e055,
            "helper": helper,
            "warm_solution": warm_solution,
            "warm_witness": warm_witness,
            "state_by_location": state_by_location,
        }
    )
    source_location = context["source_location"]
    capsule_location = context["capsule_location"]
    if str(state_by_location[source_location]["operation"]) != "filling_capsule":
        raise RuntimeError("E056 source location lost capsule operation")
    if str(state_by_location[capsule_location]["operation"]) != "grinder_fine_buckwheat":
        raise RuntimeError("E056 capsule location lost grinder operation")
    return context


def constrain_mode_frontier(
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
                variable
                == int(
                    str(operation) == str(current["operation"])
                    and pose_idx == int(current["pose_idx"])
                )
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
    built = context["helper"].build_joint(
        base,
        expanded,
        fixed_state=fixed_state,
        warm_solution=context["warm_solution"],
        warm_endpoint={"selection": context["warm_witness"]["joint_selection"]},
    )
    positive_vars, total_expr = context["e051"].attach_positive_variables(
        built,
        prefix=f"e056_{objective_kind}",
    )
    constrain_mode_frontier(built, context)
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
    calibration = context["helper"].solve_variant(
        calibration_built,
        positive_vars=calibration_positive,
        random_seed=56001,
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
            "schema": "zmd_zero_condition_e056_mode_frontier_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "E056_CALIBRATION_REJECTED",
            "identity": identity,
            "calibration": context["helper"].compact(calibration),
            "positive_solve": None,
            "decision": "REPAIR_E055_CONTEXT_REPLAY",
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
        random_seed=56101,
        objective_kind="positive_count",
        seconds=POSITIVE_SECONDS,
    )
    if positive["status"] == "OPTIMAL":
        count = int(positive["positive_commodity_count"])
        verdict = (
            "MODE_FRONTIER_SECOND_ZERO_OPTIMAL"
            if count <= 17
            else "MODE_FRONTIER_ONE_ZERO_OPTIMAL"
        )
        decision = "MINIMIZE_TOTAL_ON_POSITIVE_FACE"
    elif positive["status"] == "FEASIBLE":
        verdict = "MODE_FRONTIER_FEASIBLE_NONTERMINAL"
        decision = "RETAIN_WITNESS_AND_CONTINUE_POSITIVE_SOLVE"
    elif positive["status"] == "INFEASIBLE":
        verdict = "MODE_FRONTIER_INFEASIBLE"
        decision = "AUDIT_MODE_CONSTRAINT_TRANSPORT"
    else:
        verdict = "MODE_FRONTIER_NONTERMINAL"
        decision = "REFINE_MODE_SYMMETRY_OR_CONTINUE_SOLVE"

    payload = {
        "schema": "zmd_zero_condition_e056_mode_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "context": {
            "context_digest": expanded["context_digest"],
            "source_location": list(context["source_location"]),
            "capsule_location": list(context["capsule_location"]),
            "mode_enabled_destination_count": sum(
                bool(row["mode_enabled"]) for row in expanded["mode_summary"]
            ),
            "released_operation_and_mode_block": MERGED_BLOCK,
        },
        "calibration": context["helper"].compact(calibration),
        "positive_solve": context["helper"].compact(positive),
        "decision": decision,
        "truth_boundary": (
            "E054/E055 occupied geometry and selected causal relation; non-6x4 "
            "operation/mode choices fixed, admitted 6x4 port modes, operation "
            "assignment, and binding free."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(POSITIVE_PATH, payload)
    return payload


def main() -> int:
    if POSITIVE_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E056 positive result")
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
            "schema": "zmd_zero_condition_e056_mode_frontier_failure_v1",
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
