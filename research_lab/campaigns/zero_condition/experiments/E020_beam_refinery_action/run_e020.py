#!/usr/bin/env python3
"""E020: replay the known-composing refinery-5343 action across eligible beam seeds."""

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
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E020_beam_refinery_action/run-001"
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
E018_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E018_fourth_member_stop_test/run-001/RESULT.json"
)
E019_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E019_beam_common_action/run-002/RESULT.json"
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
E019_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E019_beam_common_action/run_e019.py"
)

EXPECTED_HASHES: dict[Path, str] = {
    E013_RESULT: "99c029fe71c2835bd5d2f5cd16d00f324856d70ce305278e2bb3aa944cbf6fd1",
    E017_RESULT: "08626489854032d7a25097b6b2f1cfacb95444a14c680cee6e7886134f45588d",
    E017_PAIR_ASSIGNMENT: "aa92cf0328df49c3c2d058b96c0fd941ceba2436859823e15d85b0792d4c5403",
    E017_BEST_ASSIGNMENT: "d3c8aed026ddefefdf8da43a3096fac26e89703330dea0d047bc3f9172fd5768",
    E018_RESULT: "6155248779f6de3e9f17e3a13b07684aacb2c373650510d0b82a81d979a8a06b",
    E019_RESULT: "89f37256e282a7f716092d477495d8e6ec715015d32632c97ca133b0ce40d3e7",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E017_RUNNER: "106d7ee8830d3a45bf4115e064e65e059fdd86c4bd4b5c2acddaff55e203a2e0",
    E019_RUNNER: "8a0ef3dc09ab9903d0be5f0c6ab2a91ac2a5d6c09cd095480cc87df651e8df4b",
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
    "EXACT_MASTER_RANDOM_SEED": "262000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

SEED_OBJECTIVE = 176
SEED_COUNT = 12
BEAM_WIDTH = SEED_COUNT
COMMON_TARGET_LITERAL = (
    "mandatory::group::manufacturing_3x3::refinery_blue_iron::7::5343"
)
KNOWN_REPRESENTATIVE_OBJECTIVE = 174


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
        raise RuntimeError("E020 must run on research/main")
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
    if int(load_json(E018_RESULT)["best_objective"]) != KNOWN_REPRESENTATIVE_OBJECTIVE:
        raise RuntimeError("known representative fourth-step drift")
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
        raise RuntimeError("E020 common target absent from E013 budget-16 portfolio")
    return target


def seed_checkpoint_path(index: int) -> Path:
    return OUT / f"SEED_{index:02d}.json"


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e001 = import_module("zmd_e020_e001", E001_RUNNER)
    e002 = import_module("zmd_e020_e002", E002_RUNNER)
    e004 = import_module("zmd_e020_e004", E004_RUNNER)
    e014 = import_module("zmd_e020_e014", E014_RUNNER)
    e015 = import_module("zmd_e020_e015", E015_RUNNER)
    e017 = import_module("zmd_e020_e017", E017_RUNNER)
    e019 = import_module("zmd_e020_e019", E019_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    pair_solution = e017.load_pair_solution()
    target = target_manifest()
    seeds = e019.seed_records()
    if len(seeds) != SEED_COUNT:
        raise RuntimeError("E020 seed count drift")
    power = e014.build_power_semantics(e001, stack, inputs)

    representative_digest = stable_digest(load_json(E017_BEST_ASSIGNMENT)["solution"])
    parent_states: list[dict[str, Any]] = []
    child_states: list[dict[str, Any]] = []
    seed_runs: list[dict[str, Any]] = []
    eligible_seeds: list[dict[str, Any]] = []
    ineligible_seeds: list[dict[str, Any]] = []
    child_lookup: dict[tuple[int, str], tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {}

    for seed_index, seed in enumerate(seeds, 1):
        seed_solution = e017.reconstruct_candidate(
            arm={"target": seed["target"]},
            record=seed,
            pair_solution=pair_solution,
            inputs=inputs,
            e014=e014,
        )
        if stable_digest(seed_solution) != str(seed["candidate_solution_digest"]):
            raise RuntimeError(f"E020 seed reconstruction drift: {seed_index}")
        representative = str(seed["candidate_solution_digest"]) == representative_digest
        parent_states.append(
            e019.state_descriptor(
                source_kind="parent",
                seed_index=seed_index,
                placement_digest=str(seed["candidate_solution_digest"]),
                shared=seed["shared_binding"],
                provenance={
                    "seed_target_literal": str(seed["target"]["literal_key"]),
                    "seed_replacement_pose_idx": int(seed["pose_idx"]),
                    "seed_arm_index": int(seed["arm_index"]),
                    "representative_seed": representative,
                },
            )
        )

        target_instance = str(target["source_instance_ids"][0])
        current_pose = int(seed_solution[target_instance]["pose_idx"])
        if current_pose != int(target["pose_idx"]):
            ineligible_seeds.append(
                {
                    "seed_index": seed_index,
                    "representative_seed": representative,
                    "seed_target_literal": str(seed["target"]["literal_key"]),
                    "seed_replacement_pose_idx": int(seed["pose_idx"]),
                    "reason": "common_target_already_moved",
                    "current_common_target_pose_idx": current_pose,
                }
            )
            continue

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
            raise RuntimeError(f"E020 seed {seed_index} fails power semantics")

        checkpoint = seed_checkpoint_path(seed_index)
        if checkpoint.exists():
            arm = load_json(checkpoint)
            if str(arm.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E020 checkpoint: {checkpoint}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E020_SEED_START",
                        "seed_index": seed_index,
                        "representative_seed": representative,
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
            arm["schema"] = "zmd_zero_condition_e020_seed_expansion_v1"
            arm["seed_descriptor"] = {
                "seed_index": seed_index,
                "representative_seed": representative,
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
        eligible_seeds.append(
            {
                "seed_index": seed_index,
                "representative_seed": representative,
                "seed_target_literal": str(seed["target"]["literal_key"]),
                "seed_replacement_pose_idx": int(seed["pose_idx"]),
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
        for record in optimal:
            child_states.append(
                e019.state_descriptor(
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
                seed_solution,
            )

        print(
            json.dumps(
                {
                    "event": "E020_SEED_DONE",
                    "seed_index": seed_index,
                    "representative_seed": representative,
                    "alternatives": int(arm["alternative_count"]),
                    "status_counts": arm["status_counts"],
                    "best_child_objective": (
                        None if best is None else int(best["shared_binding"]["objective"])
                    ),
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    if len(eligible_seeds) != 8 or len(ineligible_seeds) != 4:
        raise RuntimeError(
            f"E020 eligibility drift: eligible={len(eligible_seeds)}, "
            f"ineligible={len(ineligible_seeds)}"
        )
    representative_rows = [row for row in eligible_seeds if row["representative_seed"]]
    if len(representative_rows) != 1:
        raise RuntimeError("E020 representative eligibility drift")
    if int(representative_rows[0]["best_child_objective"]) != KNOWN_REPRESENTATIVE_OBJECTIVE:
        raise RuntimeError("E020 failed to reproduce known representative objective 174")

    all_states = parent_states + child_states
    deduplicated = e019.deduplicate_states(all_states)
    retained = e019.retain_beam(deduplicated)
    manifest = {
        "schema": "zmd_zero_condition_e020_beam_state_manifest_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "seed_count": SEED_COUNT,
        "eligible_seed_count": len(eligible_seeds),
        "ineligible_seed_count": len(ineligible_seeds),
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
            "Research beam over twelve parents and one eligible common-action "
            "child family; retention is a search policy, not a completeness claim."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(BEAM_MANIFEST_PATH, manifest)

    optimal_children = sorted(child_states, key=e019.state_rank)
    if not optimal_children:
        raise RuntimeError("E020 has no base-binding-feasible child")
    best_child_state = optimal_children[0]
    lookup_key = (
        int(best_child_state["seed_index"]),
        str(best_child_state["placement_digest"]),
    )
    best_arm, best_record, best_seed_solution = child_lookup[lookup_key]
    best_solution = e017.reconstruct_candidate(
        arm=best_arm,
        record=best_record,
        pair_solution=best_seed_solution,
        inputs=inputs,
        e014=e014,
    )
    if stable_digest(best_solution) != str(best_child_state["placement_digest"]):
        raise RuntimeError("E020 best child reconstruction drift")
    best_detailed = e015.solve_shared_mismatch(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        random_seed=273000,
        include_boundaries=True,
    )
    if (
        str(best_detailed["status"]) != "OPTIMAL"
        or int(best_detailed["objective"]) != int(best_child_state["objective"])
    ):
        raise RuntimeError("E020 best detailed replay drift")
    dump_exclusive(
        BEST_ASSIGNMENT_PATH,
        {
            "schema": "zmd_zero_condition_e020_best_child_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "seed_index": int(best_child_state["seed_index"]),
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
        for row in eligible_seeds
        if row["best_child_objective"] is not None
    ]
    best_across_seeds = min(finite_best)
    worst_across_seeds = max(finite_best)
    objective_distribution = dict(sorted(Counter(finite_best).items()))
    improved_seed_count = sum(value < SEED_OBJECTIVE for value in finite_best)
    equal_seed_count = sum(value == SEED_OBJECTIVE for value in finite_best)
    worsened_seed_count = sum(value > SEED_OBJECTIVE for value in finite_best)

    if int(best_detailed["objective"]) == 0:
        verdict = "BEAM_REFINERY_ACTION_COMPONENT_FEASIBLE"
    elif worst_across_seeds > best_across_seeds:
        verdict = "KNOWN_ACTION_BRANCH_DIFFERENTIAL"
    elif best_across_seeds == KNOWN_REPRESENTATIVE_OBJECTIVE:
        verdict = "KNOWN_ACTION_ELIGIBILITY_CLASS_INVARIANT"
    else:
        verdict = "KNOWN_ACTION_UNEXPECTED_UNIFORM_RESPONSE"

    return {
        "schema": "zmd_zero_condition_e020_beam_refinery_action_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "power_semantics": power["summary"],
        "seed_objective": SEED_OBJECTIVE,
        "seed_count": SEED_COUNT,
        "eligible_seed_count": len(eligible_seeds),
        "ineligible_seed_count": len(ineligible_seeds),
        "common_target": json_safe(target),
        "eligible_seed_results": eligible_seeds,
        "ineligible_seed_results": ineligible_seeds,
        "branch_response": {
            "best_child_objective": best_across_seeds,
            "worst_child_objective": worst_across_seeds,
            "objective_range": worst_across_seeds - best_across_seeds,
            "best_objective_distribution": objective_distribution,
            "improved_seed_count": improved_seed_count,
            "equal_seed_count": equal_seed_count,
            "worsened_seed_count": worsened_seed_count,
            "representative_seed_best_child_objective": int(
                representative_rows[0]["best_child_objective"]
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
            "seed_index": int(best_child_state["seed_index"]),
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
            str(seed_checkpoint_path(int(row["seed_index"])).relative_to(ROOT))
            for row in eligible_seeds
        ],
        "decision_reading": {
            "branch_value_differential": worst_across_seeds > best_across_seeds,
            "action_equivalence_class_size": (
                len(eligible_seeds)
                if worst_across_seeds == best_across_seeds
                else None
            ),
            "statement": (
                "The known composing action has different exact continuation "
                "values across equal-score parents."
                if worst_across_seeds > best_across_seeds
                else "The known composing action is exact-value invariant across "
                "all eligible equal-score parents."
            ),
        },
        "truth_boundary": (
            "One common refinery target expanded independently from eight eligible "
            "objective-176 seeds. Other actions and simultaneous changes remain open."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E020 outputs under {OUT}")
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
            "schema": "zmd_zero_condition_e020_failure_v1",
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
