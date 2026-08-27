#!/usr/bin/env python3
"""E053: merge four relevant 6x4 bodies and optimize first-zero progress."""

from __future__ import annotations

from collections import Counter
import copy
from contextlib import contextmanager
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E053_merged_6x4_first_zero_joint/run-002"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
BEST_WITNESS_PATH = OUT / "BEST_LEX_JOINT_WITNESS.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_LEX_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_LEX_LAYOUT.json"

E051_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E051_positive_commodity_frontier/"
    "run-001/RESULT.json"
)
E052_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E052_fine_powder_terminal_body_frontier/"
    "run-001/RESULT.json"
)
E052_PROPOSED_BLOCK = E052_RESULT.with_name("PROPOSED_6X4_BLOCK.json")
E050_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E050_revalue_external_rescues/"
    "run-001/SEED_C_BEST_ASSIGNMENT.json"
)
E050_ENDPOINT = E050_ASSIGNMENT.with_name("SEED_C_BEST_ENDPOINT.json")

E051_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E051_positive_commodity_frontier/run_e051.py"
)
E052_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E052_fine_powder_terminal_body_frontier/run_e052.py"
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
E014_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E014_fixed_outside_mobility/run_e014.py"
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
    "EXACT_MASTER_RANDOM_SEED": "283000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E051_RESULT: "7c0b50f8ce92e8e12e7be89a7e7e2f612facd650173abd823e4867ce9e984c04",
    E052_RESULT: "6f96f86d21d956f82edbb5995440676910691d5b30ada76cdb5e49cbb0049e8c",
    E052_PROPOSED_BLOCK: "faf0e48478218c15561230090f672717ec5d0c3b6f1a2be297b7300414842437",
    E050_ASSIGNMENT: "8964829329cc98d4ea58d691854d6d81a9723248a6467d9a159d010bbcdabe55",
    E050_ENDPOINT: "04999122509a580c501eb0458d9909abf65dbd5075fd3f06b5ca928355be9b86",
    E051_RUNNER: "e287c3c4323494b894792435b44fe2c23458345ca2f7409b06309170e9c4ca87",
    E052_RUNNER: "2539c2b4fce6ddeeb4a9520b7dfe947f9e1163f1cd212321fa483ad96245b658",
    E041_RUNNER: "5731b294e5c3070617d3a29e8912e4f859da207c6f183354ad9c7194f2d54b06",
    E041_HELPER: "98464fc5c9ee181a69392e582c2194edd0c213965b6c62672ece190fb1370dad",
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

PRIMARY_PARENT = 139
TARGET_COMMODITY = "fine_buckwheat_powder"
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
    result_51 = load_json(E051_RESULT)
    result_52 = load_json(E052_RESULT)
    endpoint = load_json(E050_ENDPOINT)
    if result_51.get("verdict") != "FIRST_ZERO_INFEASIBLE_IN_BOUNDED_JOINT_CONTEXT":
        raise RuntimeError("E053 E051 trigger verdict drift")
    if result_52.get("verdict") != "ONE_BODY_FIRST_ZERO_INFEASIBLE_ASSIGNMENT_BLOCK_INCOMPLETE":
        raise RuntimeError("E053 E052 trigger verdict drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != PRIMARY_PARENT:
        raise RuntimeError("E053 parent endpoint drift")
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


def expanded_context(base: Mapping[str, Any]) -> dict[str, Any]:
    e041 = base["e041"]
    e043 = base["e043"]
    solution = base["best_solution"]
    pools = base["inputs"]["pools"]
    proposed = load_json(E052_PROPOSED_BLOCK)

    blocks = [copy.deepcopy(block) for block in base["blocks"]]
    selected_ids_by_block = {
        str(block_id): set(values)
        for block_id, values in base["selected_ids_by_block"].items()
    }
    block = next(row for row in blocks if str(row["block_id"]) == "6x4_merged")
    proposed_ids = [str(value) for value in proposed["proposed_selected_instance_ids"]]
    current_ids = sorted(selected_ids_by_block["6x4_merged"])
    if current_ids != sorted(str(value) for value in proposed["current_selected_instance_ids"]):
        raise RuntimeError("E053 current 6x4 selected IDs drift")
    if len(proposed_ids) != 14 or len(set(proposed_ids)) != 14:
        raise RuntimeError("E053 proposed 6x4 block width drift")

    ordered_ids = sorted(
        proposed_ids,
        key=lambda instance_id: (
            int(solution[instance_id]["pose_idx"]),
            instance_id,
        ),
    )
    payloads = [
        e043.pose_payload(
            instance_id=instance_id,
            row=solution[instance_id],
            pools=pools,
        )
        for instance_id in ordered_ids
    ]
    operation_counts = Counter(
        str(solution[instance_id]["operation_type"])
        for instance_id in ordered_ids
    )
    if dict(sorted(operation_counts.items())) != dict(proposed["operation_multiset"]):
        raise RuntimeError("E053 proposed operation multiset drift")
    permutation_count = math.factorial(len(ordered_ids))
    for count in operation_counts.values():
        permutation_count //= math.factorial(int(count))

    block["operation_multiset"] = dict(sorted(operation_counts.items()))
    block["operation_diversity"] = len(operation_counts)
    block["selected_literal_count"] = len(payloads)
    block["selected_literal_payloads"] = payloads
    block["selected_literals"] = [str(payload["literal_key"]) for payload in payloads]
    block["source_instance_ids_by_destination"] = ordered_ids
    block["selection_digest"] = stable_digest(payloads)
    block["semantic_permutation_count_including_identity"] = permutation_count
    block["owner_refresh"] = "fine_powder_relevant_6x4_merge"
    block.pop("mode_pose_indices_by_destination", None)
    selected_ids_by_block["6x4_merged"] = set(ordered_ids)

    inherited_mode_ids = {
        str(row["source_instance_id"])
        for row in base["mode_summary"]
        if bool(row["mode_enabled"])
    }
    added_ids = set(str(value) for value in proposed["relevant_outside_instance_ids"])
    mode_enabled_ids = inherited_mode_ids | added_ids
    enriched_blocks, mode_summary = e041.enrich_blocks_with_modes(
        blocks=blocks,
        solution=solution,
        selected_ids_by_block=selected_ids_by_block,
        mode_enabled_ids=mode_enabled_ids,
        pools=pools,
    )
    all_sets = list(selected_ids_by_block.values())
    if len(set().union(*all_sets)) != sum(len(values) for values in all_sets):
        raise RuntimeError("E053 selected instance overlap")
    exchangeability = base["e031"].exchangeability_audit(
        neighborhoods=enriched_blocks,
        mandatory=base["mandatory"],
        generic=base["generic"],
    )
    if exchangeability.get("status") != "PASS":
        raise RuntimeError("E053 exchangeability audit failed")
    return {
        "blocks": enriched_blocks,
        "selected_ids_by_block": selected_ids_by_block,
        "mode_summary": mode_summary,
        "mode_enabled_ids": sorted(mode_enabled_ids),
        "added_instance_ids": sorted(added_ids),
        "exchangeability": exchangeability,
        "context_digest": stable_digest(
            {
                "blocks": enriched_blocks,
                "selected_ids_by_block": {
                    key: sorted(values)
                    for key, values in selected_ids_by_block.items()
                },
                "mode_summary": mode_summary,
            }
        ),
    }


def build_joint(
    base: Mapping[str, Any],
    expanded: Mapping[str, Any],
    *,
    fixed_state: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    warm_solution: Mapping[str, Mapping[str, Any]],
    warm_endpoint: Mapping[str, Any],
) -> dict[str, Any]:
    return base["e041"].build_mode_joint_model(
        full_solution=warm_solution,
        warm_endpoint=warm_endpoint,
        fixed_state=fixed_state,
        inputs=base["inputs"],
        blocks=expanded["blocks"],
        selected_ids_by_block=expanded["selected_ids_by_block"],
        e004=base["e004"],
        e015=base["e015"],
        conditional_mode_module=base["conditional_mode_module"],
    )


@contextmanager
def heartbeat(label: str):
    stop = threading.Event()

    def emit() -> None:
        while not stop.wait(10.0):
            print(
                json.dumps(
                    {
                        "event": "E053_HEARTBEAT",
                        "stage": label,
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    thread = threading.Thread(target=emit, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=2.0)


def configure_solver(*, random_seed: int, seconds: float = SOLVE_SECONDS) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = SOLVE_WORKERS
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(random_seed)
    return solver


def solve_variant(
    built: Mapping[str, Any],
    *,
    positive_vars: Mapping[str, Any],
    random_seed: int,
    objective_kind: str,
    seconds: float = SOLVE_SECONDS,
) -> dict[str, Any]:
    solver = configure_solver(random_seed=random_seed, seconds=seconds)
    started = time.monotonic()
    with heartbeat(objective_kind):
        status = solver.Solve(built["binding_model"].model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "status": status_name,
        "objective_kind": objective_kind,
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "optimizer_objective": None,
        "best_bound": float(solver.BestObjectiveBound()),
        "total_mismatch": None,
        "positive_commodity_count": None,
    }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result
    result["optimizer_objective"] = int(round(solver.ObjectiveValue()))

    operation_by_block: dict[str, list[str]] = {}
    pose_idx_by_block: dict[str, list[int]] = {}
    selected_pattern_by_block: dict[str, list[dict[str, Any]]] = {}
    for block in built["blocks"]:
        block_id = str(block["block_id"])
        operations = [str(value) for value in block["operations"]]
        modes_by_destination = block["mode_pose_indices_by_destination"]
        operations_out: list[str] = []
        poses_out: list[int] = []
        patterns_out: list[dict[str, Any]] = []
        for destination, pose_indices in enumerate(modes_by_destination):
            selected = [
                (mode_index, operation)
                for mode_index in range(len(pose_indices))
                for operation in operations
                if solver.Value(
                    built["y_vars"][(
                        block_id,
                        destination,
                        mode_index,
                        operation,
                    )]
                )
                == 1
            ]
            if len(selected) != 1:
                raise RuntimeError(
                    f"E053 assignment extraction drift {block_id}/{destination}: "
                    f"{selected}"
                )
            mode_index, operation = selected[0]
            pose_idx = int(pose_indices[mode_index])
            operations_out.append(operation)
            poses_out.append(pose_idx)
            pattern_indices = [
                pattern_index
                for (
                    row_block,
                    row_destination,
                    row_mode,
                    row_operation,
                    pattern_index,
                ), variable in built["z_vars"].items()
                if row_block == block_id
                and row_destination == destination
                and row_mode == mode_index
                and row_operation == operation
                and solver.Value(variable) == 1
            ]
            if len(pattern_indices) != 1:
                raise RuntimeError(
                    f"E053 pattern extraction drift {block_id}/{destination}: "
                    f"{pattern_indices}"
                )
            patterns_out.append(
                {
                    "destination": destination,
                    "mode_index": mode_index,
                    "pose_idx": pose_idx,
                    "operation": operation,
                    "pattern_index": int(pattern_indices[0]),
                }
            )
        operation_by_block[block_id] = operations_out
        pose_idx_by_block[block_id] = poses_out
        selected_pattern_by_block[block_id] = patterns_out

    per_commodity: dict[str, int] = {}
    for commodity in built["compiled"]["commodities"]:
        value = sum(
            int(solver.Value(variable))
            for variable in built["compiled"]["mismatch_vars"][commodity].values()
        )
        per_commodity[str(commodity)] = value
        if int(solver.Value(built["compiled"]["source_global"][commodity])) != 1:
            raise RuntimeError(f"E053 missing global source: {commodity}")
        if int(solver.Value(built["compiled"]["sink_global"][commodity])) != 1:
            raise RuntimeError(f"E053 missing global sink: {commodity}")
    total_mismatch = sum(per_commodity.values())
    positive_count = sum(value > 0 for value in per_commodity.values())
    encoded_positive = sum(
        int(solver.Value(variable)) for variable in positive_vars.values()
    )
    if positive_count != encoded_positive:
        raise RuntimeError("E053 positive-variable/per-commodity mismatch")
    if objective_kind == "positive_count" and int(result["optimizer_objective"]) != positive_count:
        raise RuntimeError("E053 positive objective mismatch")
    if objective_kind == "total_mismatch" and int(result["optimizer_objective"]) != total_mismatch:
        raise RuntimeError("E053 total objective mismatch")

    binding_model = built["binding_model"]
    binding_model._solver = solver
    binding_model._status = status
    selection = binding_model.extract_selection()
    port_specs = binding_model.extract_port_specs()
    result.update(
        {
            "total_mismatch": total_mismatch,
            "positive_commodity_count": positive_count,
            "zero_mismatch_commodities": sorted(
                commodity for commodity, value in per_commodity.items() if value == 0
            ),
            "per_commodity": per_commodity,
            "operation_by_block": operation_by_block,
            "pose_idx_by_block": pose_idx_by_block,
            "selected_pattern_by_block": selected_pattern_by_block,
            "joint_selection": selection,
            "joint_selection_digest": stable_digest(selection),
            "joint_port_specs": port_specs,
            "joint_port_specs_digest": stable_digest(port_specs),
        }
    )
    return result


def compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"joint_selection", "joint_port_specs", "selected_pattern_by_block"}
    }


def materialize_and_replay(
    base: Mapping[str, Any],
    expanded: Mapping[str, Any],
    lex: Mapping[str, Any],
    *,
    optimum_positive_count: int,
    required_zero_commodities: Sequence[str],
) -> dict[str, Any]:
    e041 = base["e041"]
    e014 = import_module("zmd_e053_e014", E014_RUNNER)
    child = e041.realize_mode_blocks(
        parent=base["best_solution"],
        blocks=expanded["blocks"],
        operation_by_block=lex["operation_by_block"],
        pose_idx_by_block=lex["pose_idx_by_block"],
        selected_ids_by_block=expanded["selected_ids_by_block"],
        pools=base["inputs"]["pools"],
        e014=e014,
    )
    parent_occupied, _ = e014.base_occupancy(
        base["best_solution"], base["inputs"]["pools"]
    )
    child_occupied, _ = e014.base_occupancy(child, base["inputs"]["pools"])
    if child_occupied != parent_occupied:
        raise RuntimeError("E053 lex realization changed occupied geometry")
    power = e014.build_power_semantics(base["e001"], base["stack"], base["inputs"])
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
        raise RuntimeError("E053 lex realization broke power")

    fixed_state = e041.fixed_state_for_solution(
        solution=child,
        blocks=expanded["blocks"],
        selected_ids_by_block=expanded["selected_ids_by_block"],
        pools=base["inputs"]["pools"],
    )
    replay_built = build_joint(
        base,
        expanded,
        fixed_state=fixed_state,
        warm_solution=child,
        warm_endpoint={"selection": lex["joint_selection"]},
    )
    replay_positive, replay_total = base["e051"].attach_positive_variables(
        replay_built,
        prefix="e053_replay",
    )
    replay_built["binding_model"].model.Add(
        cp_model.LinearExpr.Sum(list(replay_positive.values()))
        == int(optimum_positive_count)
    )
    for commodity in required_zero_commodities:
        replay_built["binding_model"].model.Add(
            cp_model.LinearExpr.Sum(
                list(
                    replay_built["compiled"]["mismatch_vars"][commodity].values()
                )
            )
            == 0
        )
    replay_built["binding_model"].model.Minimize(replay_total)
    fixed_replay = solve_variant(
        replay_built,
        positive_vars=replay_positive,
        random_seed=53005,
        objective_kind="total_mismatch",
        seconds=90.0,
    )
    if fixed_replay["status"] != "OPTIMAL":
        raise RuntimeError("E053 fixed replay non-optimal")
    if int(fixed_replay["total_mismatch"]) != int(lex["total_mismatch"]):
        raise RuntimeError("E053 fixed replay total mismatch drift")
    if int(fixed_replay["positive_commodity_count"]) != int(
        lex["positive_commodity_count"]
    ):
        raise RuntimeError("E053 fixed replay positive-count drift")
    if not set(required_zero_commodities).issubset(
        set(fixed_replay["zero_mismatch_commodities"])
    ):
        raise RuntimeError("E053 fixed replay lost required zero commodity")

    from src.models.routing_subproblem import (
        RoutingPlacementCore,
        run_exact_routing_precheck,
    )
    from src.models.routing_binding_context import build_routing_binding_context

    routing_context = build_routing_binding_context(
        child,
        base["inputs"]["pools"],
        70,
        70,
    )
    placement_core = RoutingPlacementCore.from_occupied_cells(
        set(routing_context.occupied_cells),
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    precheck = run_exact_routing_precheck(
        placement_core=placement_core,
        port_specs=lex["joint_port_specs"],
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    if str(precheck.get("status")) == "front_blocked":
        raise RuntimeError("E053 lex joint ports fail front precheck")
    disconnected = {
        str(row.get("commodity", ""))
        for row in precheck.get("disconnected_commodities", [])
    }
    positive = {
        commodity
        for commodity, value in lex["per_commodity"].items()
        if int(value) > 0
    }
    if disconnected != positive:
        raise RuntimeError(
            "E053 joint objective/precheck mismatch: "
            f"positive={sorted(positive)} disconnected={sorted(disconnected)}"
        )

    dump_exclusive(
        BEST_WITNESS_PATH,
        {
            "schema": "zmd_zero_condition_e053_lex_joint_witness_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": lex["status"],
            "positive_commodity_count": int(lex["positive_commodity_count"]),
            "total_mismatch": int(lex["total_mismatch"]),
            "zero_mismatch_commodities": lex["zero_mismatch_commodities"],
            "per_commodity": lex["per_commodity"],
            "operation_by_block": lex["operation_by_block"],
            "pose_idx_by_block": lex["pose_idx_by_block"],
            "selected_pattern_by_block": lex["selected_pattern_by_block"],
            "joint_selection": lex["joint_selection"],
            "joint_port_specs": lex["joint_port_specs"],
            "precheck": {
                key: value for key, value in precheck.items() if key != "_analysis"
            },
            "ledger_effect": "none",
        },
    )
    dump_exclusive(
        BEST_ASSIGNMENT_PATH,
        {
            "schema": "zmd_zero_condition_e053_lex_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "LEXICOGRAPHIC_JOINT_OPTIMAL",
            "positive_commodity_count": int(lex["positive_commodity_count"]),
            "total_mismatch": int(lex["total_mismatch"]),
            "zero_mismatch_commodities": lex["zero_mismatch_commodities"],
            "operation_by_block": lex["operation_by_block"],
            "pose_idx_by_block": lex["pose_idx_by_block"],
            "solution": child,
        },
    )
    dump_exclusive(BEST_LAYOUT_PATH, base["e001"].solution_layout(child))
    return {
        "placement_digest": stable_digest(child),
        "fixed_replay": compact(fixed_replay),
        "production_precheck": {
            key: value for key, value in precheck.items() if key != "_analysis"
        },
        "witness_path": str(BEST_WITNESS_PATH.relative_to(ROOT)),
        "witness_sha256": sha256_file(BEST_WITNESS_PATH),
        "assignment_path": str(BEST_ASSIGNMENT_PATH.relative_to(ROOT)),
        "assignment_sha256": sha256_file(BEST_ASSIGNMENT_PATH),
        "layout_path": str(BEST_LAYOUT_PATH.relative_to(ROOT)),
        "layout_sha256": sha256_file(BEST_LAYOUT_PATH),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e051 = import_module("zmd_e053_e051", E051_RUNNER)
    base = e051.reconstruct_context()
    expanded = expanded_context(base)
    e041 = base["e041"]

    fixed_state = e041.fixed_state_for_solution(
        solution=base["best_solution"],
        blocks=expanded["blocks"],
        selected_ids_by_block=expanded["selected_ids_by_block"],
        pools=base["inputs"]["pools"],
    )
    calibration_built = build_joint(
        base,
        expanded,
        fixed_state=fixed_state,
        warm_solution=base["best_solution"],
        warm_endpoint=base["best_endpoint"],
    )
    with heartbeat("calibration"):
        calibration = e041.solve_mode_joint(
            calibration_built,
            time_limit_seconds=45.0,
            random_seed=53001,
        )
    if calibration["status"] != "OPTIMAL" or int(calibration["objective"]) != PRIMARY_PARENT:
        return {
            "schema": "zmd_zero_condition_e053_merged_6x4_first_zero_joint_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "MERGED_6X4_CALIBRATION_REJECTED",
            "identity": identity,
            "expanded_context": expanded,
            "calibration": compact(calibration),
            "decision": "REPAIR_MERGED_6X4_CONTEXT",
            "ledger_effect": "none",
        }

    sum_built = build_joint(
        base,
        expanded,
        fixed_state=None,
        warm_solution=base["best_solution"],
        warm_endpoint=base["best_endpoint"],
    )
    with heartbeat("sum_optimum"):
        sum_optimum = e041.solve_mode_joint(
            sum_built,
            time_limit_seconds=SOLVE_SECONDS,
            random_seed=53002,
        )
    if sum_optimum["status"] != "OPTIMAL":
        return {
            "schema": "zmd_zero_condition_e053_merged_6x4_first_zero_joint_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "MERGED_6X4_SUM_OPTIMUM_NONTERMINAL",
            "identity": identity,
            "expanded_context": expanded,
            "calibration": compact(calibration),
            "sum_optimum": compact(sum_optimum),
            "decision": "CONTINUE_SUM_OPTIMUM_BEFORE_LEXICOGRAPHIC_JUDGMENT",
            "ledger_effect": "none",
        }

    positive_built = build_joint(
        base,
        expanded,
        fixed_state=None,
        warm_solution=base["best_solution"],
        warm_endpoint=base["best_endpoint"],
    )
    positive_vars, _positive_total = e051.attach_positive_variables(
        positive_built,
        prefix="e053_positive",
    )
    positive_built["binding_model"].model.Minimize(
        cp_model.LinearExpr.Sum(list(positive_vars.values()))
    )
    positive_optimum = solve_variant(
        positive_built,
        positive_vars=positive_vars,
        random_seed=53003,
        objective_kind="positive_count",
    )
    if positive_optimum["status"] != "OPTIMAL":
        return {
            "schema": "zmd_zero_condition_e053_merged_6x4_first_zero_joint_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "MERGED_6X4_POSITIVE_COUNT_NONTERMINAL",
            "identity": identity,
            "expanded_context": expanded,
            "calibration": compact(calibration),
            "sum_optimum": compact(sum_optimum),
            "positive_optimum": compact(positive_optimum),
            "decision": "CONTINUE_POSITIVE_COUNT_SOLVE",
            "ledger_effect": "none",
        }

    min_positive = int(positive_optimum["positive_commodity_count"])
    lex_built = build_joint(
        base,
        expanded,
        fixed_state=None,
        warm_solution=base["best_solution"],
        warm_endpoint=base["best_endpoint"],
    )
    lex_positive, lex_total = e051.attach_positive_variables(
        lex_built,
        prefix="e053_lex",
    )
    lex_built["binding_model"].model.Add(
        cp_model.LinearExpr.Sum(list(lex_positive.values())) == min_positive
    )
    lex_built["binding_model"].model.Minimize(lex_total)
    lex_optimum = solve_variant(
        lex_built,
        positive_vars=lex_positive,
        random_seed=53004,
        objective_kind="total_mismatch",
    )
    if lex_optimum["status"] != "OPTIMAL":
        return {
            "schema": "zmd_zero_condition_e053_merged_6x4_first_zero_joint_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "MERGED_6X4_LEX_TOTAL_NONTERMINAL",
            "identity": identity,
            "expanded_context": expanded,
            "calibration": compact(calibration),
            "sum_optimum": compact(sum_optimum),
            "positive_optimum": compact(positive_optimum),
            "lex_optimum": compact(lex_optimum),
            "decision": "CONTINUE_LEX_TOTAL_SOLVE",
            "ledger_effect": "none",
        }

    materialized = materialize_and_replay(
        base,
        expanded,
        lex_optimum,
        optimum_positive_count=min_positive,
        required_zero_commodities=lex_optimum["zero_mismatch_commodities"],
    )
    routing_status = (
        "READY_COMPONENT_COMPATIBLE_BINDING"
        if min_positive == 0
        else "NOT_REACHED_POSITIVE_SHARED_MISMATCH"
    )
    if min_positive == 0:
        verdict = "MERGED_6X4_COMPONENT_COMPATIBLE_BINDING"
        decision = "ENTER_EXACT_ROUTING"
    elif min_positive < 19:
        verdict = "MERGED_6X4_FIRST_ZERO_FOUND"
        decision = "RECOMPUTE_RESIDUAL_WITH_POSITIVE_COUNT_PRIORITY"
    else:
        verdict = "MERGED_6X4_FIRST_ZERO_SATURATED"
        decision = "BUILD_NATIVE_SIMULTANEOUS_BODY_CONTEXT"

    return {
        "schema": "zmd_zero_condition_e053_merged_6x4_first_zero_joint_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "parent_objective": PRIMARY_PARENT,
        "expanded_context": {
            "context_digest": expanded["context_digest"],
            "block_count": len(expanded["blocks"]),
            "selected_instance_count": sum(
                len(values) for values in expanded["selected_ids_by_block"].values()
            ),
            "merged_6x4_size": len(expanded["selected_ids_by_block"]["6x4_merged"]),
            "added_instance_ids": expanded["added_instance_ids"],
            "mode_enabled_destination_count": sum(
                bool(row["mode_enabled"]) for row in expanded["mode_summary"]
            ),
            "exchangeability_audit": expanded["exchangeability"],
        },
        "calibration": compact(calibration),
        "sum_optimum": compact(sum_optimum),
        "positive_optimum": compact(positive_optimum),
        "lex_optimum": compact(lex_optimum),
        "target_commodity": {
            "name": TARGET_COMMODITY,
            "sum_optimum_value": sum_optimum["per_commodity"][TARGET_COMMODITY],
            "positive_optimum_value": positive_optimum["per_commodity"][TARGET_COMMODITY],
            "lex_optimum_value": lex_optimum["per_commodity"][TARGET_COMMODITY],
        },
        "materialized": materialized,
        "routing": {"status": routing_status},
        "decision": decision,
        "truth_boundary": (
            "E050 Seed C occupied geometry with the fourteen-body merged 6x4 "
            "assignment block and inherited bounded conditional contexts only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    outputs = (
        RESULT_PATH,
        FAILURE_PATH,
        BEST_WITNESS_PATH,
        BEST_ASSIGNMENT_PATH,
        BEST_LAYOUT_PATH,
    )
    if any(path.exists() for path in outputs):
        raise FileExistsError("refusing to overwrite E053 outputs")
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
                    "sum_optimum": {
                        "status": result["sum_optimum"]["status"],
                        "objective": result["sum_optimum"].get("objective"),
                        "positive": result["sum_optimum"].get(
                            "positive_commodity_count"
                        ),
                    },
                    "positive_optimum": {
                        "status": result["positive_optimum"]["status"],
                        "positive": result["positive_optimum"].get(
                            "positive_commodity_count"
                        ),
                        "total": result["positive_optimum"].get("total_mismatch"),
                        "zeros": result["positive_optimum"].get(
                            "zero_mismatch_commodities"
                        ),
                    },
                    "lex_optimum": {
                        "status": result["lex_optimum"]["status"],
                        "positive": result["lex_optimum"].get(
                            "positive_commodity_count"
                        ),
                        "total": result["lex_optimum"].get("total_mismatch"),
                        "zeros": result["lex_optimum"].get(
                            "zero_mismatch_commodities"
                        ),
                    },
                    "target": result["target_commodity"],
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
            "schema": "zmd_zero_condition_e053_merged_6x4_first_zero_joint_failure_v1",
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
