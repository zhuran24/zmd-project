#!/usr/bin/env python3
"""E045: revalue the two E044 body seeds with the faithful joint middle layer."""

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
OUT = ROOT / "research_lab/local/zero_condition/E045_revalue_objective146_geometries/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E041_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E041_joint_port_mode_assignment/run-001/RESULT.json"
)
E041_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E041_joint_port_mode_assignment/run-001/BEST_ASSIGNMENT.json"
)
E042_BODY_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E042_mode_vs_body_discriminator/run-001/BEST_BODY_ASSIGNMENT.json"
)
E043_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/RESULT.json"
)
E043_SEED_A_CHECKPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/SEED_A.json"
)
E043_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/SEED_A_BEST_ASSIGNMENT.json"
)
E043_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E043_geometry_conditioned_joint_middle/run-001/SEED_A_BEST_ENDPOINT.json"
)
E044_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E044_objective147_body_portfolio/run-001/RESULT.json"
)
E044_SEED_1_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E044_objective147_body_portfolio/run-001/SEED_01_ASSIGNMENT.json"
)
E044_SEED_1_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E044_objective147_body_portfolio/run-001/SEED_01_ENDPOINT.json"
)
E044_SEED_2_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E044_objective147_body_portfolio/run-001/SEED_02_ASSIGNMENT.json"
)
E044_SEED_2_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E044_objective147_body_portfolio/run-001/SEED_02_ENDPOINT.json"
)
E041_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E041_joint_port_mode_assignment/run_e041.py"
)
E041_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E041_joint_port_mode_assignment/conditional_mode_owner_binding.py"
)
E043_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E043_geometry_conditioned_joint_middle/run_e043.py"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
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
    "EXACT_MASTER_RANDOM_SEED": "275000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E041_RESULT: "ba97d01cfe4a757daf102e514ab9984bd99abc679c16f8db6147f2269d40fada",
    E041_ASSIGNMENT: "020bfc79e47e61e2c6ccd68d10a7f292d22f381ab0747c3ea37e960f501ce642",
    E042_BODY_ASSIGNMENT: "b5dae2fadbcc5db51556aeb77f4b3bea26a929ed308ee76207ba19b38cb18d2f",
    E043_RESULT: "4ed1a66ef93e28e2e6521b1bd0458a0603db02a6a54731648f62df139dd4e335",
    E043_SEED_A_CHECKPOINT: "876289b47ce10af8963b59ca460f6615130858a8c462231c8afb23029a1d63b0",
    E043_ASSIGNMENT: "302c9ab02b839a9924ed9aecd7c2e23ba9c5c7a571052600c6514bf7292d846a",
    E043_ENDPOINT: "6ee527af5f84d652a351e7e00e22cddda990d121f2cdb25839af214f11c2051a",
    E044_RESULT: "d1329eb538618eaf42d4a90267dd336446ea33e458f29a47a5ab70d3c47ce9e1",
    E044_SEED_1_ASSIGNMENT: "cccd2fbe9f45e91e313fda56b283516e7c2f09097bb99dd0d24107cd4c537a3e",
    E044_SEED_1_ENDPOINT: "92436c89149d87e234e1d9168e9c0964a33b9c42f543290fb76a052ba2abe8d3",
    E044_SEED_2_ASSIGNMENT: "bf6aae0efaa0de4d29b5e87acc40c9761b5584e0061d8de045720ab118100e86",
    E044_SEED_2_ENDPOINT: "561e465f2dcb8126f411e5e0f2c686f907860efcbc24ef1cfa8c32e9665d28ff",
    E041_RUNNER: "5731b294e5c3070617d3a29e8912e4f859da207c6f183354ad9c7194f2d54b06",
    E041_HELPER: "98464fc5c9ee181a69392e582c2194edd0c213965b6c62672ece190fb1370dad",
    E043_RUNNER: "a81cd8a762f29fad5c1a9f1c587f3bc90c4abc099aa97ccadedee2235da34d26",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    E031_RUNNER: "ba35d569dc1a514da83b46721cb53c3f25386b2d776c70ac4cfae7f7c4d29b18",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

EXPECTED_FIXED_OBJECTIVE = 146


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
        raise RuntimeError("E045 must run on research/main")
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
    result_43 = load_json(E043_RESULT)
    result_44 = load_json(E044_RESULT)
    if int(result_43["best_objective"]) != 147:
        raise RuntimeError("E043 parent objective drift")
    seeds = result_44.get("materialized_seeds", [])
    if len(seeds) != 2 or any(
        int(seed["objective"]) != EXPECTED_FIXED_OBJECTIVE for seed in seeds
    ):
        raise RuntimeError("E044 seed objective drift")
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


def reconstruct_e043_context(
    *,
    e041: Any,
    e043: Any,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    result_41 = load_json(E041_RESULT)
    base_41 = e041.solution_from_assignment(E041_ASSIGNMENT)
    seed_a_42 = e041.solution_from_assignment(E042_BODY_ASSIGNMENT)
    blocks, selected_ids, mode_summary, move = e043.prepare_blocks_for_seed(
        base_solution=base_41,
        seed_solution=seed_a_42,
        result_41=result_41,
        pools=inputs["pools"],
        e041=e041,
    )
    checkpoint = load_json(E043_SEED_A_CHECKPOINT)
    if json_safe(mode_summary) != json_safe(checkpoint["mode_summary"]):
        raise RuntimeError("E045 reconstructed E043 mode context drift")
    if json_safe(move) != json_safe(checkpoint["move"]):
        raise RuntimeError("E045 reconstructed E043 move context drift")
    return {
        "final_blocks": blocks,
        "selected_instance_ids_by_block": {
            key: sorted(value) for key, value in selected_ids.items()
        },
        "mode_summary": mode_summary,
        "source": "reconstructed E043 Seed A geometry-conditioned context",
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e041 = import_module("zmd_e045_e041", E041_RUNNER)
    e043 = import_module("zmd_e045_e043", E043_RUNNER)
    e001 = import_module("zmd_e045_e001", E001_RUNNER)
    e004 = import_module("zmd_e045_e004", E004_RUNNER)
    e014 = import_module("zmd_e045_e014", E014_RUNNER)
    e015 = import_module("zmd_e045_e015", E015_RUNNER)
    e027 = import_module("zmd_e045_e027", E027_RUNNER)
    e031 = import_module("zmd_e045_e031", E031_RUNNER)
    conditional_mode_module = import_module(
        "zmd_e045_conditional_mode",
        E041_HELPER,
    )

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent_solution = e041.solution_from_assignment(E043_ASSIGNMENT)
    context_result = reconstruct_e043_context(
        e041=e041,
        e043=e043,
        inputs=inputs,
    )
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(mandatory, list) or not isinstance(generic, Mapping):
        raise RuntimeError("E045 frozen instance/generic payload drift")

    seed_inputs = [
        (
            "A",
            e041.solution_from_assignment(E044_SEED_1_ASSIGNMENT),
            load_json(E044_SEED_1_ENDPOINT),
        ),
        (
            "B",
            e041.solution_from_assignment(E044_SEED_2_ASSIGNMENT),
            load_json(E044_SEED_2_ENDPOINT),
        ),
    ]
    for label, solution, endpoint in seed_inputs:
        moved = [
            instance_id
            for instance_id in sorted(solution)
            if int(solution[instance_id]["pose_idx"])
            != int(parent_solution[instance_id]["pose_idx"])
        ]
        if len(moved) != 1:
            raise RuntimeError(f"E045 seed {label} move count drift: {moved}")
        if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != 146:
            raise RuntimeError(f"E045 seed {label} endpoint drift")

    old_out = e043.OUT
    e043.OUT = OUT
    try:
        seed_results = [
            e043.run_seed(
                label=label,
                seed_solution=solution,
                seed_endpoint=endpoint,
                expected_objective=EXPECTED_FIXED_OBJECTIVE,
                base_solution=parent_solution,
                result_41=context_result,
                inputs=inputs,
                mandatory=mandatory,
                generic=generic,
                e001=e001,
                e004=e004,
                e014=e014,
                e015=e015,
                e027=e027,
                e031=e031,
                e041=e041,
                conditional_mode_module=conditional_mode_module,
                runner_sha256=runner_sha256,
            )
            for label, solution, endpoint in seed_inputs
        ]
    finally:
        e043.OUT = old_out

    if any(
        result["verdict"] == "GEOMETRY_SEED_CALIBRATION_REJECTED"
        for result in seed_results
    ):
        return {
            "schema": "zmd_zero_condition_e045_revalue_objective146_geometries_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "OBJECTIVE146_GEOMETRY_CALIBRATION_REJECTED",
            "identity": identity,
            "context_reconstruction": context_result,
            "seed_results": seed_results,
            "best_seed": None,
            "routing": {"status": "NOT_REACHED_CALIBRATION_REJECTED"},
            "decision": "REFINE_OBJECTIVE146_GEOMETRY_CONTEXT",
            "truth_boundary": "Fidelity calibrations only.",
            "ledger_effect": "none",
        }

    feasible = [
        result for result in seed_results if result.get("best_child") is not None
    ]
    if not feasible:
        return {
            "schema": "zmd_zero_condition_e045_revalue_objective146_geometries_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "OBJECTIVE146_GEOMETRY_JOINT_NONTERMINAL",
            "identity": identity,
            "context_reconstruction": context_result,
            "seed_results": seed_results,
            "best_seed": None,
            "routing": {"status": "NOT_REACHED_NO_FEASIBLE_JOINT_STATE"},
            "decision": "CONTINUE_OR_REFORMULATE_OBJECTIVE146_JOINT_SOLVES",
            "truth_boundary": "Two frozen singleton body geometries only.",
            "ledger_effect": "none",
        }

    ranked = sorted(
        feasible,
        key=lambda result: (
            int(result["best_child"]["objective"]),
            -int(result["best_child"]["filtered_binding_option_count"]),
            str(result["seed_label"]),
        ),
    )
    best_objective = int(ranked[0]["best_child"]["objective"])
    best = [
        result
        for result in ranked
        if int(result["best_child"]["objective"]) == best_objective
    ]
    routing: dict[str, Any] = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
    if best_objective == 0:
        verdict = "OBJECTIVE146_GEOMETRY_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
        routing = {"status": "READY_SELECTED_ZERO_ENDPOINT"}
    elif len(best) > 1:
        verdict = "OBJECTIVE146_GEOMETRY_JOINT_TIE"
        decision = "RETAIN_GEOMETRY_BEAM_AND_COMPARE_BODY_RESPONSE_DOMAINS"
    else:
        if best_objective < EXPECTED_FIXED_OBJECTIVE:
            verdict = "OBJECTIVE146_GEOMETRY_JOINT_MATERIAL_IMPROVEMENT"
            decision = "RECOMPUTE_RESIDUAL_FROM_SELECTED_GEOMETRY"
        else:
            verdict = "OBJECTIVE146_GEOMETRY_JOINT_SATURATION_SIGNAL"
            decision = "BUILD_SIMULTANEOUS_BODY_PAIR_NEIGHBORHOOD"

    return {
        "schema": "zmd_zero_condition_e045_revalue_objective146_geometries_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "context_reconstruction": {
            "block_count": len(context_result["final_blocks"]),
            "selected_instance_count": sum(
                len(values)
                for values in context_result[
                    "selected_instance_ids_by_block"
                ].values()
            ),
            "mode_enabled_destination_count": sum(
                bool(row["mode_enabled"])
                for row in context_result["mode_summary"]
            ),
            "context_digest": hashlib.sha256(
                json.dumps(
                    json_safe(context_result),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        },
        "seed_results": seed_results,
        "joint_objective_distribution": dict(
            sorted(
                Counter(
                    int(result["best_child"]["objective"])
                    for result in feasible
                ).items()
            )
        ),
        "best_objective": best_objective,
        "best_seed_labels": [str(result["seed_label"]) for result in best],
        "best_seed": best[0] if len(best) == 1 else None,
        "routing": routing,
        "decision": decision,
        "truth_boundary": (
            "Two E044 singleton body geometries composed with the E043 Seed A "
            "parent; each receives one exact fixed-state calibration and one free "
            "bounded port-mode/assignment/binding solve."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E045 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "seed_results": [
                        {
                            "seed": row["seed_label"],
                            "fixed": row["fixed_objective"],
                            "calibration_status": row["calibration"]["status"],
                            "calibration_objective": row["calibration"].get(
                                "objective"
                            ),
                            "free_status": (
                                row["free_solve"].get("status")
                                if row.get("free_solve")
                                else None
                            ),
                            "free_objective": (
                                row["free_solve"].get("objective")
                                if row.get("free_solve")
                                else None
                            ),
                        }
                        for row in result["seed_results"]
                    ],
                    "best_objective": result.get("best_objective"),
                    "best_seed_labels": result.get("best_seed_labels"),
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
            "schema": "zmd_zero_condition_e045_revalue_objective146_geometries_failure_v1",
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
