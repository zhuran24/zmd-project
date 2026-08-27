#!/usr/bin/env python3
"""E051: audit positive-commodity count in the E050 joint context."""

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
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E051_positive_commodity_frontier/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
FIRST_ZERO_WITNESS_PATH = OUT / "FIRST_ZERO_JOINT_WITNESS.json"
FIRST_ZERO_ASSIGNMENT_PATH = OUT / "FIRST_ZERO_ASSIGNMENT.json"
FIRST_ZERO_LAYOUT_PATH = OUT / "FIRST_ZERO_LAYOUT.json"
FIRST_ZERO_UNCONSTRAINED_ENDPOINT_PATH = OUT / "FIRST_ZERO_UNCONSTRAINED_ENDPOINT.json"

E050_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E050_revalue_external_rescues/"
    "run-001/RESULT.json"
)
E050_BEST_ASSIGNMENT = E050_RESULT.with_name("SEED_C_BEST_ASSIGNMENT.json")
E050_BEST_ENDPOINT = E050_RESULT.with_name("SEED_C_BEST_ENDPOINT.json")
E049_SEED_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E049_external_rescue_graph/"
    "run-001/SEED_03_ASSIGNMENT.json"
)
E049_SEED_ENDPOINT = E049_SEED_ASSIGNMENT.with_name("SEED_03_ENDPOINT.json")

E050_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E050_revalue_external_rescues/run_e050.py"
)
E048_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E048_revalue_body_pair_geometries/run_e048.py"
)
E046_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E046_objective145_integrated_geometry_portfolio/run_e046.py"
)
E045_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E045_revalue_objective146_geometries/run_e045.py"
)
E043_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E043_geometry_conditioned_joint_middle/run_e043.py"
)
E041_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E041_joint_port_mode_assignment/run_e041.py"
)
E041_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E041_joint_port_mode_assignment/conditional_mode_owner_binding.py"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E001_pocket_cut_replay/run_experiment.py"
)
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E004_component_mismatch_atlas/run_e004.py"
)
E015_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E015_shared_binding_gradient/run_e015.py"
)
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E027_final_unary_discriminator/run_e027.py"
)
E031_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E031_bounded_assignment_neighborhood/run_e031.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "281000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E050_RESULT: "ece91ce0ebc74caa5a1e7791c64ebdf6a692926aa8f74e780384d6898a41944d",
    E050_BEST_ASSIGNMENT: "8964829329cc98d4ea58d691854d6d81a9723248a6467d9a159d010bbcdabe55",
    E050_BEST_ENDPOINT: "04999122509a580c501eb0458d9909abf65dbd5075fd3f06b5ca928355be9b86",
    E049_SEED_ASSIGNMENT: "17626085e2fe13ac452eeceb2b03db516668ea14d82c40f49076da9d199f1a3c",
    E049_SEED_ENDPOINT: "907fa3242501240ce8aa6caa480221d87b2caae213db6536196201bd4a1fb361",
    E050_RUNNER: "6e9a0a874c5d31fe6b63892b9aabb979c6c776204aaa12c7e2f043ebaf5a274e",
    E048_RUNNER: "97fae12907ce3a2ef3404c73cbb9dfa0e2fd8d60bfc3a7dffae72a09ccc4f7dd",
    E046_RUNNER: "b15363594654d497dc18f2a53eb12b75cc1ce0bedd3c2149acd9c40649d69648",
    E045_RUNNER: "8ba3886ef205e682e3e6e54d1905fecb9033ddc5e86fa0c3c252e61f0df1e02b",
    E043_RUNNER: "a81cd8a762f29fad5c1a9f1c587f3bc90c4abc099aa97ccadedee2235da34d26",
    E041_RUNNER: "5731b294e5c3070617d3a29e8912e4f859da207c6f183354ad9c7194f2d54b06",
    E041_HELPER: "98464fc5c9ee181a69392e582c2194edd0c213965b6c62672ece190fb1370dad",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
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

PRIMARY_OPTIMUM = 139
FIRST_ZERO_POSITIVE_CAP = 18
SOLVE_SECONDS = 180.0
SOLVE_WORKERS = 8


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
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(
                f"frozen identity drift for {path}: {actual} != {expected}"
            )
    result_50 = load_json(E050_RESULT)
    endpoint = load_json(E050_BEST_ENDPOINT)
    if result_50.get("verdict") != "EXTERNAL_RESCUE_JOINT_IMPROVEMENT":
        raise RuntimeError("E051 E050 trigger verdict drift")
    if result_50.get("best_seed_labels") != ["C"]:
        raise RuntimeError("E051 E050 best seed drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != PRIMARY_OPTIMUM:
        raise RuntimeError("E051 primary endpoint drift")
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


def attach_positive_variables(
    built: Mapping[str, Any],
    *,
    prefix: str,
) -> tuple[dict[str, Any], Any]:
    model = built["binding_model"].model
    positives: dict[str, Any] = {}
    all_mismatch: list[Any] = []
    for commodity in built["compiled"]["commodities"]:
        variables = list(built["compiled"]["mismatch_vars"][commodity].values())
        if not variables:
            raise RuntimeError(f"E051 commodity has no mismatch variables: {commodity}")
        all_mismatch.extend(variables)
        mismatch = cp_model.LinearExpr.Sum(variables)
        positive = model.NewBoolVar(f"{prefix}_positive_{commodity}")
        model.Add(mismatch >= 1).OnlyEnforceIf(positive)
        model.Add(mismatch == 0).OnlyEnforceIf(positive.Not())
        positives[str(commodity)] = positive
    return positives, cp_model.LinearExpr.Sum(all_mismatch)


def configure_solver(*, random_seed: int) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_SECONDS
    solver.parameters.num_search_workers = SOLVE_WORKERS
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(random_seed)
    return solver


def solve_primary_face_positive_count(
    built: Mapping[str, Any],
    *,
    random_seed: int,
) -> dict[str, Any]:
    positives, total = attach_positive_variables(built, prefix="e051_face")
    model = built["binding_model"].model
    model.Add(total == PRIMARY_OPTIMUM)
    model.Minimize(cp_model.LinearExpr.Sum(list(positives.values())))
    solver = configure_solver(random_seed=random_seed)
    started = time.monotonic()
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "status": status_name,
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "best_bound": float(solver.BestObjectiveBound()),
        "positive_commodity_count": None,
        "total_mismatch": None,
        "per_commodity": None,
        "zero_mismatch_commodities": None,
    }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result
    per_commodity = {
        str(commodity): sum(
            int(solver.Value(variable))
            for variable in built["compiled"]["mismatch_vars"][commodity].values()
        )
        for commodity in built["compiled"]["commodities"]
    }
    positive_count = sum(value > 0 for value in per_commodity.values())
    encoded_count = sum(int(solver.Value(variable)) for variable in positives.values())
    if positive_count != encoded_count:
        raise RuntimeError("E051 positive-variable/per-commodity mismatch")
    total_value = sum(per_commodity.values())
    if total_value != PRIMARY_OPTIMUM:
        raise RuntimeError("E051 primary-face total drift")
    for commodity in built["compiled"]["commodities"]:
        if int(solver.Value(built["compiled"]["source_global"][commodity])) != 1:
            raise RuntimeError(f"E051 primary face lacks source: {commodity}")
        if int(solver.Value(built["compiled"]["sink_global"][commodity])) != 1:
            raise RuntimeError(f"E051 primary face lacks sink: {commodity}")
    result.update(
        {
            "positive_commodity_count": positive_count,
            "total_mismatch": total_value,
            "per_commodity": per_commodity,
            "zero_mismatch_commodities": sorted(
                commodity for commodity, value in per_commodity.items() if value == 0
            ),
        }
    )
    return result


def add_first_zero_cap(built: Mapping[str, Any], *, prefix: str) -> dict[str, Any]:
    positives, total = attach_positive_variables(built, prefix=prefix)
    built["binding_model"].model.Add(
        cp_model.LinearExpr.Sum(list(positives.values())) <= FIRST_ZERO_POSITIVE_CAP
    )
    return {"positive_vars": positives, "total_expr": total}


def reconstruct_context() -> dict[str, Any]:
    e050 = import_module("zmd_e051_e050", E050_RUNNER)
    e048 = import_module("zmd_e051_e048", E048_RUNNER)
    e046 = import_module("zmd_e051_e046", E046_RUNNER)
    e045 = import_module("zmd_e051_e045", E045_RUNNER)
    e043 = import_module("zmd_e051_e043", E043_RUNNER)
    e041 = import_module("zmd_e051_e041", E041_RUNNER)
    e001 = import_module("zmd_e051_e001", E001_RUNNER)
    e004 = import_module("zmd_e051_e004", E004_RUNNER)
    e015 = import_module("zmd_e051_e015", E015_RUNNER)
    e027 = import_module("zmd_e051_e027", E027_RUNNER)
    e031 = import_module("zmd_e051_e031", E031_RUNNER)
    conditional_mode_module = import_module(
        "zmd_e051_conditional_mode",
        E041_HELPER,
    )

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent_solution = e041.solution_from_assignment(e050.PARENT_ASSIGNMENT)
    context_144 = e048.reconstruct_objective144_context(
        e041=e041,
        e043=e043,
        e045=e045,
        e046=e046,
        inputs=inputs,
    )
    seed_solution = e041.solution_from_assignment(E049_SEED_ASSIGNMENT)
    seed_endpoint = load_json(E049_SEED_ENDPOINT)
    best_solution = e041.solution_from_assignment(E050_BEST_ASSIGNMENT)
    best_endpoint = load_json(E050_BEST_ENDPOINT)
    blocks, selected_ids_by_block, mode_summary, move = (
        e050.prepare_blocks_for_pose_pair(
            base_solution=parent_solution,
            seed_solution=seed_solution,
            result_41=context_144,
            pools=inputs["pools"],
            e041=e041,
            e043=e043,
        )
    )
    result_50 = load_json(E050_RESULT)
    seed_c = next(
        row for row in result_50["seed_results"] if str(row["seed_label"]) == "C"
    )
    if json_safe(mode_summary) != json_safe(seed_c["mode_summary"]):
        raise RuntimeError("E051 E050 mode context drift")
    if json_safe(move) != json_safe(seed_c["move"]):
        raise RuntimeError("E051 E050 move context drift")
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(mandatory, list) or not isinstance(generic, Mapping):
        raise RuntimeError("E051 frozen instance/generic payload drift")
    exchangeability = e031.exchangeability_audit(
        neighborhoods=blocks,
        mandatory=mandatory,
        generic=generic,
    )
    if exchangeability.get("status") != "PASS":
        raise RuntimeError("E051 exchangeability audit failed")
    return {
        "e050": e050,
        "e048": e048,
        "e046": e046,
        "e045": e045,
        "e043": e043,
        "e041": e041,
        "e001": e001,
        "e004": e004,
        "e015": e015,
        "e027": e027,
        "e031": e031,
        "conditional_mode_module": conditional_mode_module,
        "stack": stack,
        "inputs": inputs,
        "parent_solution": parent_solution,
        "seed_solution": seed_solution,
        "seed_endpoint": seed_endpoint,
        "best_solution": best_solution,
        "best_endpoint": best_endpoint,
        "blocks": blocks,
        "selected_ids_by_block": selected_ids_by_block,
        "mode_summary": mode_summary,
        "move": move,
        "mandatory": mandatory,
        "generic": generic,
        "exchangeability": exchangeability,
    }


def build_joint(
    context: Mapping[str, Any],
    *,
    fixed_state: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    warm_solution: Mapping[str, Mapping[str, Any]],
    warm_endpoint: Mapping[str, Any],
) -> dict[str, Any]:
    return context["e041"].build_mode_joint_model(
        full_solution=warm_solution,
        warm_endpoint=warm_endpoint,
        fixed_state=fixed_state,
        inputs=context["inputs"],
        blocks=context["blocks"],
        selected_ids_by_block=context["selected_ids_by_block"],
        e004=context["e004"],
        e015=context["e015"],
        conditional_mode_module=context["conditional_mode_module"],
    )


def compact_joint(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"joint_selection", "joint_port_specs", "selected_pattern_by_block"}
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    context = reconstruct_context()
    e041 = context["e041"]
    e014 = import_module(
        "zmd_e051_e014",
        context["e050"].E014_RUNNER,
    )

    fixed_state = e041.fixed_state_for_solution(
        solution=context["best_solution"],
        blocks=context["blocks"],
        selected_ids_by_block=context["selected_ids_by_block"],
        pools=context["inputs"]["pools"],
    )
    calibration_built = build_joint(
        context,
        fixed_state=fixed_state,
        warm_solution=context["best_solution"],
        warm_endpoint=context["best_endpoint"],
    )
    calibration = e041.solve_mode_joint(
        calibration_built,
        time_limit_seconds=45.0,
        random_seed=51001,
    )
    if calibration["status"] != "OPTIMAL" or int(calibration["objective"]) != PRIMARY_OPTIMUM:
        return {
            "schema": "zmd_zero_condition_e051_positive_commodity_frontier_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "E050_FIXED_STATE_CALIBRATION_REJECTED",
            "identity": identity,
            "calibration": compact_joint(calibration),
            "decision": "REPAIR_E050_CONTEXT_RECONSTRUCTION",
            "ledger_effect": "none",
        }

    baseline_built = build_joint(
        context,
        fixed_state=None,
        warm_solution=context["best_solution"],
        warm_endpoint=context["best_endpoint"],
    )
    baseline = e041.solve_mode_joint(
        baseline_built,
        time_limit_seconds=SOLVE_SECONDS,
        random_seed=51002,
    )
    if baseline["status"] != "OPTIMAL" or int(baseline["objective"]) != PRIMARY_OPTIMUM:
        return {
            "schema": "zmd_zero_condition_e051_positive_commodity_frontier_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "E050_FREE_PRIMARY_REPLAY_REJECTED",
            "identity": identity,
            "calibration": compact_joint(calibration),
            "baseline": compact_joint(baseline),
            "decision": "REPAIR_OR_REESTABLISH_PRIMARY_OPTIMUM",
            "ledger_effect": "none",
        }

    face_built = build_joint(
        context,
        fixed_state=None,
        warm_solution=context["best_solution"],
        warm_endpoint=context["best_endpoint"],
    )
    primary_face = solve_primary_face_positive_count(
        face_built,
        random_seed=51003,
    )

    frontier_built = build_joint(
        context,
        fixed_state=None,
        warm_solution=context["best_solution"],
        warm_endpoint=context["best_endpoint"],
    )
    add_first_zero_cap(frontier_built, prefix="e051_frontier")
    frontier = e041.solve_mode_joint(
        frontier_built,
        time_limit_seconds=SOLVE_SECONDS,
        random_seed=51004,
    )
    frontier_public = compact_joint(frontier)
    first_zero: dict[str, Any] | None = None
    routing: dict[str, Any] = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}

    if frontier["status"] in {"OPTIMAL", "FEASIBLE"}:
        positive_count = int(frontier["positive_commodity_count"])
        if positive_count > FIRST_ZERO_POSITIVE_CAP:
            raise RuntimeError("E051 first-zero solver violated positive cap")
        child = e041.realize_mode_blocks(
            parent=context["best_solution"],
            blocks=context["blocks"],
            operation_by_block=frontier["operation_by_block"],
            pose_idx_by_block=frontier["pose_idx_by_block"],
            selected_ids_by_block=context["selected_ids_by_block"],
            pools=context["inputs"]["pools"],
            e014=e014,
        )
        parent_occupied, _ = e014.base_occupancy(
            context["best_solution"], context["inputs"]["pools"]
        )
        child_occupied, _ = e014.base_occupancy(child, context["inputs"]["pools"])
        if child_occupied != parent_occupied:
            raise RuntimeError("E051 first-zero realization changed occupied geometry")
        power = e014.build_power_semantics(
            context["e001"], context["stack"], context["inputs"]
        )
        selected_poles = {
            int(row["pose_idx"])
            for row in child.values()
            if str(row["facility_type"]) == "power_pole"
        }
        if not e014.all_powered_facilities_covered(
            solution=child,
            selected_poles=selected_poles,
            powered_templates=power["powered_templates"],
            coverers=power["coverers"],
        ):
            raise RuntimeError("E051 first-zero realization broke power")

        child_fixed_state = e041.fixed_state_for_solution(
            solution=child,
            blocks=context["blocks"],
            selected_ids_by_block=context["selected_ids_by_block"],
            pools=context["inputs"]["pools"],
        )
        replay_built = build_joint(
            context,
            fixed_state=child_fixed_state,
            warm_solution=child,
            warm_endpoint={"selection": frontier["joint_selection"]},
        )
        add_first_zero_cap(replay_built, prefix="e051_replay")
        fixed_replay = e041.solve_mode_joint(
            replay_built,
            time_limit_seconds=90.0,
            random_seed=51005,
        )
        if fixed_replay["status"] != "OPTIMAL":
            raise RuntimeError("E051 first-zero fixed replay is non-optimal")
        if int(fixed_replay["objective"]) != int(frontier["objective"]):
            raise RuntimeError("E051 first-zero fixed replay objective drift")
        if int(fixed_replay["positive_commodity_count"]) > FIRST_ZERO_POSITIVE_CAP:
            raise RuntimeError("E051 first-zero fixed replay lost zero commodity")

        unconstrained_endpoint = context["e027"].materialize_shared_endpoint(
            solution=child,
            inputs=context["inputs"],
            e004=context["e004"],
            e015=context["e015"],
            random_seed=51006,
        )
        dump_exclusive(FIRST_ZERO_UNCONSTRAINED_ENDPOINT_PATH, unconstrained_endpoint)
        dump_exclusive(
            FIRST_ZERO_WITNESS_PATH,
            {
                "schema": "zmd_zero_condition_e051_first_zero_joint_witness_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "status": frontier["status"],
                "total_mismatch": int(frontier["objective"]),
                "positive_commodity_count": positive_count,
                "zero_mismatch_commodities": frontier["zero_mismatch_commodities"],
                "per_commodity": frontier["per_commodity"],
                "operation_by_block": frontier["operation_by_block"],
                "pose_idx_by_block": frontier["pose_idx_by_block"],
                "selected_pattern_by_block": frontier["selected_pattern_by_block"],
                "joint_selection": frontier["joint_selection"],
                "joint_port_specs": frontier["joint_port_specs"],
                "ledger_effect": "none",
            },
        )
        dump_exclusive(
            FIRST_ZERO_ASSIGNMENT_PATH,
            {
                "schema": "zmd_zero_condition_e051_first_zero_assignment_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "status": "FIRST_ZERO_FRONTIER_OPTIMAL"
                if frontier["status"] == "OPTIMAL"
                else "FIRST_ZERO_FRONTIER_FEASIBLE_NONTERMINAL",
                "primary_optimum": PRIMARY_OPTIMUM,
                "total_mismatch": int(frontier["objective"]),
                "positive_commodity_count": positive_count,
                "zero_mismatch_commodities": frontier["zero_mismatch_commodities"],
                "operation_by_block": frontier["operation_by_block"],
                "pose_idx_by_block": frontier["pose_idx_by_block"],
                "solution": child,
            },
        )
        dump_exclusive(FIRST_ZERO_LAYOUT_PATH, context["e001"].solution_layout(child))
        first_zero = {
            "status": frontier["status"],
            "total_mismatch": int(frontier["objective"]),
            "delta_from_primary": int(frontier["objective"]) - PRIMARY_OPTIMUM,
            "positive_commodity_count": positive_count,
            "zero_mismatch_commodities": frontier["zero_mismatch_commodities"],
            "per_commodity": frontier["per_commodity"],
            "fixed_replay": compact_joint(fixed_replay),
            "unconstrained_fixed_endpoint": {
                "objective": unconstrained_endpoint["objective"],
                "positive_commodity_count": unconstrained_endpoint[
                    "positive_commodity_count"
                ],
                "zero_mismatch_commodities": unconstrained_endpoint[
                    "zero_mismatch_commodities"
                ],
                "selection_digest": unconstrained_endpoint["selection_digest"],
                "path": str(
                    FIRST_ZERO_UNCONSTRAINED_ENDPOINT_PATH.relative_to(ROOT)
                ),
                "sha256": sha256_file(FIRST_ZERO_UNCONSTRAINED_ENDPOINT_PATH),
            },
            "placement_digest": stable_digest(child),
            "witness_path": str(FIRST_ZERO_WITNESS_PATH.relative_to(ROOT)),
            "witness_sha256": sha256_file(FIRST_ZERO_WITNESS_PATH),
            "assignment_path": str(FIRST_ZERO_ASSIGNMENT_PATH.relative_to(ROOT)),
            "assignment_sha256": sha256_file(FIRST_ZERO_ASSIGNMENT_PATH),
            "layout_path": str(FIRST_ZERO_LAYOUT_PATH.relative_to(ROOT)),
            "layout_sha256": sha256_file(FIRST_ZERO_LAYOUT_PATH),
        }
        if int(frontier["objective"]) == 0:
            routing = e014.screen_component_interface(
                solution=child,
                inputs=context["inputs"],
                e001=context["e001"],
                e002=import_module(
                    "zmd_e051_e002",
                    context["e050"].E002_RUNNER,
                ),
            )

    if primary_face["status"] != "OPTIMAL":
        verdict = "PRIMARY_JOINT_FACE_POSITIVE_COUNT_NONTERMINAL"
        decision = "CONTINUE_PRIMARY_FACE_SOLVE_BEFORE_GEOMETRY_ACTION"
    elif int(primary_face["positive_commodity_count"]) < 19:
        verdict = "PRIMARY_JOINT_FACE_ALREADY_CONTAINS_ZERO"
        decision = "MATERIALIZE_POSITIVE_COUNT_REFINED_PRIMARY_STATE"
    elif frontier["status"] == "INFEASIBLE":
        verdict = "FIRST_ZERO_INFEASIBLE_IN_BOUNDED_JOINT_CONTEXT"
        decision = "EXPAND_GEOMETRY_OR_RESCUE_CONTEXT"
    elif frontier["status"] != "OPTIMAL":
        verdict = "FIRST_ZERO_FRONTIER_NONTERMINAL"
        decision = "CONTINUE_FIRST_ZERO_FRONTIER_SOLVE"
    elif int(frontier["objective"]) == 0:
        verdict = "FIRST_ZERO_FRONTIER_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif int(frontier["objective"]) <= PRIMARY_OPTIMUM + 2:
        verdict = "FIRST_ZERO_NEAR_PRIMARY_OPTIMUM"
        decision = "RETAIN_SUM_AND_POSITIVE_COUNT_BEAM"
    else:
        verdict = "FIRST_ZERO_HAS_MATERIAL_PRICE"
        decision = "TARGET_ZERO_OBSTRUCTION_IN_NEXT_GEOMETRY_CONTEXT"

    return {
        "schema": "zmd_zero_condition_e051_positive_commodity_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "primary_optimum": PRIMARY_OPTIMUM,
        "context": {
            "block_count": len(context["blocks"]),
            "selected_instance_count": sum(
                len(values) for values in context["selected_ids_by_block"].values()
            ),
            "mode_enabled_destination_count": sum(
                bool(row["mode_enabled"]) for row in context["mode_summary"]
            ),
            "context_digest": stable_digest(
                {
                    "blocks": context["blocks"],
                    "selected_ids_by_block": {
                        key: sorted(value)
                        for key, value in context["selected_ids_by_block"].items()
                    },
                    "mode_summary": context["mode_summary"],
                    "move": context["move"],
                }
            ),
            "exchangeability_audit": context["exchangeability"],
        },
        "calibration": compact_joint(calibration),
        "baseline": compact_joint(baseline),
        "primary_face_positive_count": primary_face,
        "first_zero_frontier": frontier_public,
        "first_zero": first_zero,
        "routing": routing,
        "decision": decision,
        "truth_boundary": (
            "E050 Seed C occupied geometry and bounded conditional port-mode, "
            "operation-assignment, and binding context only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    outputs = (
        RESULT_PATH,
        FAILURE_PATH,
        FIRST_ZERO_WITNESS_PATH,
        FIRST_ZERO_ASSIGNMENT_PATH,
        FIRST_ZERO_LAYOUT_PATH,
        FIRST_ZERO_UNCONSTRAINED_ENDPOINT_PATH,
    )
    if any(path.exists() for path in outputs):
        raise FileExistsError("refusing to overwrite E051 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "calibration": {
                        "status": result["calibration"]["status"],
                        "objective": result["calibration"].get("objective"),
                    },
                    "baseline": {
                        "status": result["baseline"]["status"],
                        "objective": result["baseline"].get("objective"),
                        "positive": result["baseline"].get(
                            "positive_commodity_count"
                        ),
                    },
                    "primary_face": result["primary_face_positive_count"],
                    "first_zero": result["first_zero"],
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
            "schema": "zmd_zero_condition_e051_positive_commodity_frontier_failure_v1",
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
