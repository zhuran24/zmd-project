#!/usr/bin/env python3
"""E019: apply one common fourth action across the twelve E017 beam seeds."""

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
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E019_beam_common_action/run-002"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
BEAM_MANIFEST_PATH = OUT / "BEAM_STATE_MANIFEST.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_CHILD_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_CHILD_LAYOUT.json"

E013_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E013_residual_boundary_coverage/run-004/RESULT.json"
)
E017_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E017_third_member_portfolio/run-001/RESULT.json"
)
E017_PAIR_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E016_coupled_pair_search/run-001/BEST_PAIR_ASSIGNMENT.json"
)
E017_BEST_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E017_third_member_portfolio/run-001/BEST_TRIPLE_ASSIGNMENT.json"
)
E017_BEST_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E017_third_member_portfolio/run-001/BEST_TRIPLE_LAYOUT.json"
)
E018_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E018_fourth_member_stop_test/run-001/RESULT.json"
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

EXPECTED_HASHES: dict[Path, str] = {
    E013_RESULT: "99c029fe71c2835bd5d2f5cd16d00f324856d70ce305278e2bb3aa944cbf6fd1",
    E017_RESULT: "08626489854032d7a25097b6b2f1cfacb95444a14c680cee6e7886134f45588d",
    E017_PAIR_ASSIGNMENT: "aa92cf0328df49c3c2d058b96c0fd941ceba2436859823e15d85b0792d4c5403",
    E017_BEST_ASSIGNMENT: "d3c8aed026ddefefdf8da43a3096fac26e89703330dea0d047bc3f9172fd5768",
    E017_BEST_LAYOUT: "1631b107bfd481cba6fcbfeb59779fe729840d6adf31ecd1c994dc0741976926",
    E018_RESULT: "6155248779f6de3e9f17e3a13b07684aacb2c373650510d0b82a81d979a8a06b",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E017_RUNNER: "106d7ee8830d3a45bf4115e064e65e059fdd86c4bd4b5c2acddaff55e203a2e0",
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

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "261900",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

SEED_OBJECTIVE = 176
SEED_COUNT = 12
BEAM_WIDTH = SEED_COUNT
COMMON_TARGET_LITERAL = (
    "mandatory::group::manufacturing_6x4::grinder_fine_buckwheat::16::7754"
)


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
        raise RuntimeError("E019 must run on research/main")
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
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")
    e017 = load_json(E017_RESULT)
    seeds = [
        row
        for row in e017["top_candidates"]
        if int(row["shared_binding"]["objective"]) == SEED_OBJECTIVE
    ][:SEED_COUNT]
    if len(seeds) != SEED_COUNT:
        raise RuntimeError(f"E017 beam seed count drift: {len(seeds)}")
    if len({str(row["candidate_solution_digest"]) for row in seeds}) != SEED_COUNT:
        raise RuntimeError("E017 beam seeds are not placement-distinct")
    if int(load_json(E018_RESULT)["best_objective"]) != 174:
        raise RuntimeError("E018 stop-test result drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output("status", "--porcelain=v1", "--untracked-files=no"),
    }


def target_manifest() -> dict[str, Any]:
    e013 = load_json(E013_RESULT)
    portfolio = next(
        row
        for row in e013["max_coverage_by_literal_budget"]
        if int(row["budget"]) == 16
    )["selected_literal_details"]
    by_key = {str(row["literal_key"]): dict(row) for row in portfolio}
    target = by_key.get(COMMON_TARGET_LITERAL)
    if target is None:
        raise RuntimeError("E019 common target absent from E013 budget-16 portfolio")
    return target


def seed_records() -> list[dict[str, Any]]:
    e017 = load_json(E017_RESULT)
    seeds = [
        dict(row)
        for row in e017["top_candidates"]
        if int(row["shared_binding"]["objective"]) == SEED_OBJECTIVE
    ][:SEED_COUNT]
    return seeds


def seed_checkpoint_path(index: int) -> Path:
    return OUT / f"SEED_{index:02d}.json"


def state_descriptor(
    *,
    source_kind: str,
    seed_index: int,
    placement_digest: str,
    shared: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source_kind": source_kind,
        "seed_index": int(seed_index),
        "placement_digest": str(placement_digest),
        "binding_selection_digest": str(shared["selection_digest"]),
        "free_cell_set_digest": str(shared["morphology"]["free_cell_set_digest"]),
        "objective": int(shared["objective"]),
        "positive_commodity_count": int(shared["positive_commodity_count"]),
        "zero_mismatch_commodities": list(shared["zero_mismatch_commodities"]),
        "filtered_binding_option_count": int(shared["filtered_binding_option_count"]),
        "free_component_count": int(shared["morphology"]["free_component_count"]),
        "largest_free_component": int(shared["morphology"]["largest_free_component"]),
        "provenance": json_safe(provenance),
    }


def deduplicate_states(states: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for state in states:
        key = (
            str(state["placement_digest"]),
            str(state["binding_selection_digest"]),
        )
        grouped[key].append(state)
    deduplicated: list[dict[str, Any]] = []
    for key, members in sorted(grouped.items()):
        representative = min(
            members,
            key=lambda state: (
                int(state["objective"]),
                str(state["source_kind"]),
                int(state["seed_index"]),
                stable_digest(state["provenance"]),
            ),
        )
        row = dict(representative)
        row["state_id"] = stable_digest(
            {
                "placement_digest": key[0],
                "binding_selection_digest": key[1],
            }
        )
        row["merged_provenance_count"] = len(members)
        row["merged_provenance"] = [json_safe(member["provenance"]) for member in members]
        deduplicated.append(row)
    return deduplicated


def state_rank(state: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(state["objective"]),
        -len(state["zero_mismatch_commodities"]),
        -int(state["filtered_binding_option_count"]),
        int(state["free_component_count"]),
        -int(state["largest_free_component"]),
        str(
            state.get("state_id")
            or stable_digest(
                {
                    "placement_digest": state["placement_digest"],
                    "binding_selection_digest": state["binding_selection_digest"],
                }
            )
        ),
    )


def retain_beam(states: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted((dict(state) for state in states), key=state_rank)
    retained: list[dict[str, Any]] = []
    retained_ids: set[str] = set()
    seen_free: set[str] = set()
    seen_binding: set[str] = set()

    for state in ranked:
        free_digest = str(state["free_cell_set_digest"])
        if free_digest in seen_free:
            continue
        retained.append(state)
        retained_ids.add(str(state["state_id"]))
        seen_free.add(free_digest)
        seen_binding.add(str(state["binding_selection_digest"]))
        if len(retained) >= BEAM_WIDTH:
            return retained

    for state in ranked:
        state_id = str(state["state_id"])
        selection_digest = str(state["binding_selection_digest"])
        if state_id in retained_ids or selection_digest in seen_binding:
            continue
        retained.append(state)
        retained_ids.add(state_id)
        seen_binding.add(selection_digest)
        if len(retained) >= BEAM_WIDTH:
            return retained

    for state in ranked:
        state_id = str(state["state_id"])
        if state_id in retained_ids:
            continue
        retained.append(state)
        retained_ids.add(state_id)
        if len(retained) >= BEAM_WIDTH:
            break
    return retained


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e001 = import_module("zmd_e019_e001", E001_RUNNER)
    e002 = import_module("zmd_e019_e002", E002_RUNNER)
    e004 = import_module("zmd_e019_e004", E004_RUNNER)
    e014 = import_module("zmd_e019_e014", E014_RUNNER)
    e015 = import_module("zmd_e019_e015", E015_RUNNER)
    e017 = import_module("zmd_e019_e017", E017_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    pair_solution = e017.load_pair_solution()
    target = target_manifest()
    seeds = seed_records()
    power = e014.build_power_semantics(e001, stack, inputs)

    frozen_best_solution = load_json(E017_BEST_ASSIGNMENT)["solution"]
    representative_digest = stable_digest(frozen_best_solution)
    representative_seed_indices = [
        index
        for index, seed in enumerate(seeds, 1)
        if str(seed["candidate_solution_digest"]) == representative_digest
    ]
    if representative_seed_indices != [1]:
        raise RuntimeError(
            f"E017 representative seed identity drift: {representative_seed_indices}"
        )

    seed_runs: list[dict[str, Any]] = []
    parent_states: list[dict[str, Any]] = []
    child_states: list[dict[str, Any]] = []
    child_lookup: dict[tuple[int, str], tuple[dict[str, Any], dict[str, Any]]] = {}

    for seed_index, seed in enumerate(seeds, 1):
        seed_solution = e017.reconstruct_candidate(
            arm={"target": seed["target"]},
            record=seed,
            pair_solution=pair_solution,
            inputs=inputs,
            e014=e014,
        )
        if stable_digest(seed_solution) != str(seed["candidate_solution_digest"]):
            raise RuntimeError(f"E019 seed reconstruction drift: {seed_index}")
        occupied, _owner_by_cell = e014.base_occupancy(seed_solution, inputs["pools"])
        selected_poles = {
            int(row["pose_idx"])
            for row in seed_solution.values()
            if str(row["facility_type"]) == "power_pole"
        }
        if not e014.all_powered_facilities_covered(
            solution=seed_solution,
            selected_poles=selected_poles,
            powered_templates=power["powered_templates"],
            coverers=power["coverers"],
        ):
            raise RuntimeError(f"E019 seed {seed_index} fails power semantics")
        target_instance = str(target["source_instance_ids"][0])
        if int(seed_solution[target_instance]["pose_idx"]) != int(target["pose_idx"]):
            raise RuntimeError(f"E019 target already moved in seed {seed_index}")

        parent_states.append(
            state_descriptor(
                source_kind="parent",
                seed_index=seed_index,
                placement_digest=str(seed["candidate_solution_digest"]),
                shared=seed["shared_binding"],
                provenance={
                    "seed_target_literal": str(seed["target"]["literal_key"]),
                    "seed_replacement_pose_idx": int(seed["pose_idx"]),
                    "seed_arm_index": int(seed["arm_index"]),
                },
            )
        )

        checkpoint = seed_checkpoint_path(seed_index)
        if checkpoint.exists():
            arm = load_json(checkpoint)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E019 checkpoint: {checkpoint}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E019_SEED_START",
                        "seed_index": seed_index,
                        "seed_target": seed["target"]["literal_key"],
                        "seed_pose": seed["pose_idx"],
                        "common_target": COMMON_TARGET_LITERAL,
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            arm = e017.evaluate_arm(
                index=seed_index,
                target=target,
                pair_solution=seed_solution,
                occupied=occupied,
                selected_poles=selected_poles,
                inputs=inputs,
                power=power,
                e004=e004,
                e014=e014,
                e015=e015,
                runner_sha256=runner_sha256,
            )
            arm["schema"] = "zmd_zero_condition_e019_seed_expansion_v1"
            arm["seed_descriptor"] = {
                "seed_index": seed_index,
                "placement_digest": str(seed["candidate_solution_digest"]),
                "free_cell_set_digest": str(
                    seed["shared_binding"]["morphology"]["free_cell_set_digest"]
                ),
                "binding_selection_digest": str(seed["shared_binding"]["selection_digest"]),
                "seed_target_literal": str(seed["target"]["literal_key"]),
                "seed_replacement_pose_idx": int(seed["pose_idx"]),
            }
            dump_exclusive(checkpoint, arm)
        seed_runs.append(arm)

        optimal_records = [
            record
            for record in arm["candidate_records"]
            if str(record["shared_binding"]["status"]) == "OPTIMAL"
        ]
        for record in optimal_records:
            child_states.append(
                state_descriptor(
                    source_kind="child",
                    seed_index=seed_index,
                    placement_digest=str(record["candidate_solution_digest"]),
                    shared=record["shared_binding"],
                    provenance={
                        "parent_placement_digest": str(seed["candidate_solution_digest"]),
                        "seed_target_literal": str(seed["target"]["literal_key"]),
                        "seed_replacement_pose_idx": int(seed["pose_idx"]),
                        "common_target_literal": COMMON_TARGET_LITERAL,
                        "common_replacement_pose_idx": int(record["pose_idx"]),
                        "common_replacement_pose_id": str(record["pose_id"]),
                    },
                )
            )
            child_lookup[(seed_index, str(record["candidate_solution_digest"]))] = (
                arm,
                record,
            )

        objectives = [int(record["shared_binding"]["objective"]) for record in optimal_records]
        print(
            json.dumps(
                {
                    "event": "E019_SEED_DONE",
                    "seed_index": seed_index,
                    "alternatives": int(arm["alternative_count"]),
                    "status_counts": arm["status_counts"],
                    "best_child_objective": min(objectives) if objectives else None,
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    best_child_by_seed: list[dict[str, Any]] = []
    for seed_index, arm in enumerate(seed_runs, 1):
        optimal = [
            record
            for record in arm["candidate_records"]
            if str(record["shared_binding"]["status"]) == "OPTIMAL"
        ]
        ranked = sorted(
            optimal,
            key=lambda record: (
                int(record["shared_binding"]["objective"]),
                -int(record["shared_binding"]["filtered_binding_option_count"]),
                int(record["shared_binding"]["morphology"]["free_component_count"]),
                int(record["pose_idx"]),
            ),
        )
        best = ranked[0] if ranked else None
        best_child_by_seed.append(
            {
                "seed_index": seed_index,
                "representative_seed": seed_index == 1,
                "seed_target_literal": str(seeds[seed_index - 1]["target"]["literal_key"]),
                "seed_replacement_pose_idx": int(seeds[seed_index - 1]["pose_idx"]),
                "alternative_count": int(arm["alternative_count"]),
                "status_counts": arm["status_counts"],
                "best_child_objective": (
                    None if best is None else int(best["shared_binding"]["objective"])
                ),
                "delta_from_seed": (
                    None
                    if best is None
                    else int(best["shared_binding"]["objective"]) - SEED_OBJECTIVE
                ),
                "best_common_replacement_pose_idx": (
                    None if best is None else int(best["pose_idx"])
                ),
                "best_common_replacement_pose_id": (
                    None if best is None else str(best["pose_id"])
                ),
                "best_child_placement_digest": (
                    None if best is None else str(best["candidate_solution_digest"])
                ),
                "best_child_free_cell_set_digest": (
                    None
                    if best is None
                    else str(best["shared_binding"]["morphology"]["free_cell_set_digest"])
                ),
                "best_child_binding_selection_digest": (
                    None
                    if best is None
                    else str(best["shared_binding"]["selection_digest"])
                ),
            }
        )

    all_states = parent_states + child_states
    deduplicated = deduplicate_states(all_states)
    retained = retain_beam(deduplicated)
    manifest = {
        "schema": "zmd_zero_condition_e019_beam_state_manifest_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "seed_count": SEED_COUNT,
        "beam_width": BEAM_WIDTH,
        "common_target_literal": COMMON_TARGET_LITERAL,
        "input_state_count": len(all_states),
        "deduplicated_state_count": len(deduplicated),
        "distinct_placement_count": len(
            {str(state["placement_digest"]) for state in deduplicated}
        ),
        "distinct_free_cell_set_count": len(
            {str(state["free_cell_set_digest"]) for state in deduplicated}
        ),
        "distinct_binding_selection_count": len(
            {str(state["binding_selection_digest"]) for state in deduplicated}
        ),
        "retention_policy": (
            "rank exact shared objective, then preserve one state per free-cell "
            "digest, then one per binding-selection digest, then fill by rank"
        ),
        "retained_state_count": len(retained),
        "retained_states": retained,
        "all_deduplicated_states": deduplicated,
        "truth_boundary": (
            "Research beam over frozen parents and one common-action child family; "
            "retention is a search policy, not a completeness claim."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(BEAM_MANIFEST_PATH, manifest)

    optimal_children = sorted(child_states, key=state_rank)
    if not optimal_children:
        raise RuntimeError("E019 has no base-binding-feasible child")
    best_child_state = optimal_children[0]
    lookup_key = (
        int(best_child_state["seed_index"]),
        str(best_child_state["placement_digest"]),
    )
    best_arm, best_record = child_lookup[lookup_key]
    best_seed_index = int(best_child_state["seed_index"])
    best_seed_solution = e017.reconstruct_candidate(
        arm={"target": seeds[best_seed_index - 1]["target"]},
        record=seeds[best_seed_index - 1],
        pair_solution=pair_solution,
        inputs=inputs,
        e014=e014,
    )
    best_solution = e017.reconstruct_candidate(
        arm=best_arm,
        record=best_record,
        pair_solution=best_seed_solution,
        inputs=inputs,
        e014=e014,
    )
    if stable_digest(best_solution) != str(best_child_state["placement_digest"]):
        raise RuntimeError("E019 best child reconstruction drift")
    best_detailed = e015.solve_shared_mismatch(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        random_seed=272900,
        include_boundaries=True,
    )
    if (
        str(best_detailed["status"]) != "OPTIMAL"
        or int(best_detailed["objective"]) != int(best_child_state["objective"])
    ):
        raise RuntimeError("E019 best detailed replay drift")
    dump_exclusive(
        BEST_ASSIGNMENT_PATH,
        {
            "schema": "zmd_zero_condition_e019_best_child_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "seed_index": best_seed_index,
            "shared_mismatch_objective": int(best_detailed["objective"]),
            "common_target_literal": COMMON_TARGET_LITERAL,
            "common_replacement_pose_idx": int(best_record["pose_idx"]),
            "solution": best_solution,
        },
    )
    dump_exclusive(BEST_LAYOUT_PATH, e001.solution_layout(best_solution))

    if int(best_detailed["objective"]) == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}

    finite_best = [
        int(row["best_child_objective"])
        for row in best_child_by_seed
        if row["best_child_objective"] is not None
    ]
    best_across_seeds = min(finite_best)
    worst_across_seeds = max(finite_best)
    improved_seed_count = sum(value < SEED_OBJECTIVE for value in finite_best)
    equal_seed_count = sum(value == SEED_OBJECTIVE for value in finite_best)
    worsened_seed_count = sum(value > SEED_OBJECTIVE for value in finite_best)
    representative_best = int(best_child_by_seed[0]["best_child_objective"])

    if int(best_detailed["objective"]) == 0:
        verdict = "BEAM_COMMON_ACTION_COMPONENT_FEASIBLE"
    elif best_across_seeds < SEED_OBJECTIVE:
        verdict = "BEAM_BRANCH_DIFFERENTIAL_IMPROVEMENT"
    elif worst_across_seeds > best_across_seeds:
        verdict = "BEAM_BRANCH_DIFFERENTIAL_NO_GAIN"
    else:
        verdict = "COMMON_ACTION_BRANCH_INVARIANT"

    return {
        "schema": "zmd_zero_condition_e019_beam_common_action_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "power_semantics": power["summary"],
        "seed_objective": SEED_OBJECTIVE,
        "seed_count": SEED_COUNT,
        "representative_seed_index": 1,
        "common_target": json_safe(target),
        "best_child_by_seed": best_child_by_seed,
        "branch_response": {
            "best_child_objective": best_across_seeds,
            "worst_child_objective": worst_across_seeds,
            "objective_range": worst_across_seeds - best_across_seeds,
            "representative_seed_best_child_objective": representative_best,
            "representative_seed_delta": representative_best - SEED_OBJECTIVE,
            "improved_seed_count": improved_seed_count,
            "equal_seed_count": equal_seed_count,
            "worsened_seed_count": worsened_seed_count,
            "best_objective_distribution": dict(
                sorted(Counter(finite_best).items())
            ),
        },
        "total_alternative_count": sum(
            int(run["alternative_count"]) for run in seed_runs
        ),
        "status_counts": dict(
            sorted(
                Counter(
                    str(record["shared_binding"]["status"])
                    for run in seed_runs
                    for record in run["candidate_records"]
                ).items()
            )
        ),
        "child_state_count": len(child_states),
        "beam_manifest_path": str(BEAM_MANIFEST_PATH.relative_to(ROOT)),
        "beam_manifest_sha256": sha256_file(BEAM_MANIFEST_PATH),
        "beam_summary": {
            key: manifest[key]
            for key in (
                "input_state_count",
                "deduplicated_state_count",
                "distinct_placement_count",
                "distinct_free_cell_set_count",
                "distinct_binding_selection_count",
                "retained_state_count",
            )
        },
        "retained_beam": retained,
        "best_child": {
            "seed_index": best_seed_index,
            "objective": int(best_detailed["objective"]),
            "common_replacement_pose_idx": int(best_record["pose_idx"]),
            "common_replacement_pose_id": str(best_record["pose_id"]),
            "placement_digest": str(best_child_state["placement_digest"]),
            "free_cell_set_digest": str(best_child_state["free_cell_set_digest"]),
            "binding_selection_digest": str(best_child_state["binding_selection_digest"]),
            "assignment_path": str(BEST_ASSIGNMENT_PATH.relative_to(ROOT)),
            "assignment_sha256": sha256_file(BEST_ASSIGNMENT_PATH),
            "layout_path": str(BEST_LAYOUT_PATH.relative_to(ROOT)),
            "layout_sha256": sha256_file(BEST_LAYOUT_PATH),
            "shared_binding": best_detailed,
        },
        "routing": routing,
        "seed_checkpoint_paths": [
            str(seed_checkpoint_path(index).relative_to(ROOT))
            for index in range(1, SEED_COUNT + 1)
        ],
        "decision_reading": {
            "beam_required": (
                worst_across_seeds > best_across_seeds
                or best_across_seeds < representative_best
            ),
            "statement": (
                "Equal-score parent states have different continuation values "
                "under one identical common action."
                if worst_across_seeds > best_across_seeds
                else "The tested common action does not distinguish the beam seeds."
            ),
        },
        "truth_boundary": (
            "One common target literal expanded independently from twelve frozen "
            "objective-176 seeds. Other actions and simultaneous changes remain open."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E019 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "branch_response": result["branch_response"],
                    "status_counts": result["status_counts"],
                    "beam_summary": result["beam_summary"],
                    "best_child": {
                        key: result["best_child"][key]
                        for key in (
                            "seed_index",
                            "objective",
                            "common_replacement_pose_idx",
                            "placement_digest",
                        )
                    },
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
            "schema": "zmd_zero_condition_e019_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        OUT.mkdir(parents=True, exist_ok=True)
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
