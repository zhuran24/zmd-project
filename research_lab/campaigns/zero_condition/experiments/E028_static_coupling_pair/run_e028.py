#!/usr/bin/env python3
"""E028: exhaust the packaging/grinder simultaneous fixed-outside pair."""

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
OUT = ROOT / "research_lab/local/zero_condition/E028_static_coupling_pair/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
PAIR_PATH = OUT / "PAIR_RECORDS.json"

E024_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/RESULT.json"
)
E024_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E024_branch_specific_leader/run-001/BEST_BRANCH_CHILD_ASSIGNMENT.json"
)
E026_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E026_common_packaging_action/run-003/RESULT.json"
)
E027_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E027_final_unary_discriminator/run-002/RESULT.json"
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
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E027_final_unary_discriminator/run_e027.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "262800",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E024_RESULT: "a0a69a8c0f9c7f59d8924f9f13e0e277fe5f254a35aeaeb34c6c721becd4d17f",
    E024_ASSIGNMENT: "4f49e6dc8aaaf8e677596cd631f0eb34fc735612a4ff5a3e09dbb50836633018",
    E026_RESULT: "7dbb42b6c255fbc89a6a904364b861a7ef28eb8487ccabbfc305dbc291c8456e",
    E027_RESULT: "45474cd70c8fc1561c7e3b5d7a07fa889218ec6423941867ede4dbb9b03eb412",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
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

PARENT_OBJECTIVE = 168
PACKAGING_INSTANCE = "packaging_battery_003"
PACKAGING_POSE = 6189
GRINDER_INSTANCE = "grinder_dense_blue_iron_002"
GRINDER_POSE = 6049
EXPECTED_PAIR_COUNT = 47
MATERIAL_IMPROVEMENT = 2


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
        raise RuntimeError("E028 must run on research/main")
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
    e024 = load_json(E024_RESULT)
    if int(e024["best_child"]["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E024 objective drift")
    e026 = load_json(E026_RESULT)
    if e026.get("verdict") != "COMMON_PACKAGING_ACTION_STATIC_DOMAIN_REJECTED":
        raise RuntimeError("E026 static-coupling trigger drift")
    if e026.get("empty_domain_frequency", {}).get(
        "grinder_dense_blue_iron_002@6049"
    ) != 8:
        raise RuntimeError("E026 grinder blocker frequency drift")
    e027 = load_json(E027_RESULT)
    if e027.get("verdict") != "SERIAL_UNARY_SATURATION_SIGNAL":
        raise RuntimeError("E027 stop-rule trigger drift")
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


def load_parent_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E024_ASSIGNMENT)
    raw = assignment.get("solution")
    if not isinstance(raw, Mapping):
        raise RuntimeError("E024 assignment solution drift")
    solution = {
        str(instance_id): dict(row)
        for instance_id, row in raw.items()
        if isinstance(row, Mapping)
    }
    if len(solution) != 319:
        raise RuntimeError(f"E024 placement count drift: {len(solution)}")
    result = load_json(E024_RESULT)
    if stable_digest(solution) != str(result["best_child"]["placement_digest"]):
        raise RuntimeError("E024 placement digest drift")
    if int(solution[PACKAGING_INSTANCE]["pose_idx"]) != PACKAGING_POSE:
        raise RuntimeError("packaging current pose drift")
    if int(solution[GRINDER_INSTANCE]["pose_idx"]) != GRINDER_POSE:
        raise RuntimeError("grinder current pose drift")
    return solution


def replace_instance(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    instance_id: str,
    pose_idx: int,
    inputs: Mapping[str, Any],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    updated = {str(key): dict(value) for key, value in solution.items()}
    source = updated[instance_id]
    facility_type = str(source["facility_type"])
    pose = inputs["pools"][facility_type][int(pose_idx)]
    updated[instance_id] = e014.replacement_row(
        source=source,
        pose=pose,
        pose_idx=int(pose_idx),
        instance_id=instance_id,
    )
    return updated


def enumerate_pair_alternatives(
    *,
    parent_solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    selected_poles: set[int],
    power: Mapping[str, Any],
    e014: Any,
) -> list[dict[str, Any]]:
    occupied, _owner_by_cell = e014.base_occupancy(
        parent_solution,
        inputs["pools"],
    )
    packaging_row = parent_solution[PACKAGING_INSTANCE]
    grinder_row = parent_solution[GRINDER_INSTANCE]
    packaging_type = str(packaging_row["facility_type"])
    grinder_type = str(grinder_row["facility_type"])
    packaging_current_cells = e014.pose_cells(
        inputs["pools"], packaging_type, PACKAGING_POSE
    )
    grinder_current_cells = e014.pose_cells(
        inputs["pools"], grinder_type, GRINDER_POSE
    )
    fixed_occupied = set(
        occupied - packaging_current_cells - grinder_current_cells
    )

    packaging_candidates: list[tuple[int, frozenset[tuple[int, int]]]] = []
    for pose_idx, _pose in enumerate(inputs["pools"][packaging_type]):
        if pose_idx == PACKAGING_POSE:
            continue
        cells = e014.pose_cells(inputs["pools"], packaging_type, pose_idx)
        if cells & fixed_occupied:
            continue
        packaging_candidates.append((pose_idx, cells))

    grinder_candidates: list[tuple[int, frozenset[tuple[int, int]]]] = []
    for pose_idx, _pose in enumerate(inputs["pools"][grinder_type]):
        if pose_idx == GRINDER_POSE:
            continue
        cells = e014.pose_cells(inputs["pools"], grinder_type, pose_idx)
        if cells & fixed_occupied:
            continue
        grinder_candidates.append((pose_idx, cells))

    pairs: list[dict[str, Any]] = []
    for packaging_pose, packaging_cells in packaging_candidates:
        for grinder_pose, grinder_cells in grinder_candidates:
            if packaging_cells & grinder_cells:
                continue
            solution = replace_instance(
                solution=parent_solution,
                instance_id=PACKAGING_INSTANCE,
                pose_idx=packaging_pose,
                inputs=inputs,
                e014=e014,
            )
            solution = replace_instance(
                solution=solution,
                instance_id=GRINDER_INSTANCE,
                pose_idx=grinder_pose,
                inputs=inputs,
                e014=e014,
            )
            if not e014.all_powered_facilities_covered(
                solution=solution,
                selected_poles=selected_poles,
                powered_templates=power["powered_templates"],
                coverers=power["coverers"],
            ):
                continue
            packaging_pose_payload = inputs["pools"][packaging_type][packaging_pose]
            grinder_pose_payload = inputs["pools"][grinder_type][grinder_pose]
            pairs.append(
                {
                    "packaging_pose_idx": int(packaging_pose),
                    "packaging_pose_id": str(packaging_pose_payload["pose_id"]),
                    "packaging_anchor": json_safe(packaging_pose_payload["anchor"]),
                    "grinder_pose_idx": int(grinder_pose),
                    "grinder_pose_id": str(grinder_pose_payload["pose_id"]),
                    "grinder_anchor": json_safe(grinder_pose_payload["anchor"]),
                    "swaps_current_pose_cells": (
                        packaging_cells == grinder_current_cells
                        and grinder_cells == packaging_current_cells
                    ),
                    "solution": solution,
                }
            )
    pairs.sort(
        key=lambda row: (
            int(row["packaging_pose_idx"]),
            int(row["grinder_pose_idx"]),
        )
    )
    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise RuntimeError(f"E028 pair-domain drift: {len(pairs)}")
    return pairs


def compact_shared(shared: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": shared.get("status"),
        "objective": shared.get("objective"),
        "selection_digest": shared.get("selection_digest"),
        "port_specs_digest": shared.get("port_specs_digest"),
        "per_commodity": json_safe(shared.get("per_commodity", {})),
        "selected_components": json_safe(shared.get("selected_components", {})),
        "positive_commodity_count": shared.get("positive_commodity_count"),
        "zero_mismatch_commodities": json_safe(
            shared.get("zero_mismatch_commodities", [])
        ),
        "morphology": json_safe(shared.get("morphology", {})),
        "filtered_binding_option_count": shared.get(
            "filtered_binding_option_count"
        ),
        "empty_filtered_domains": json_safe(
            shared.get("empty_filtered_domains", [])
        ),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e001 = import_module("zmd_e028_e001", E001_RUNNER)
    e002 = import_module("zmd_e028_e002", E002_RUNNER)
    e004 = import_module("zmd_e028_e004", E004_RUNNER)
    e014 = import_module("zmd_e028_e014", E014_RUNNER)
    e015 = import_module("zmd_e028_e015", E015_RUNNER)
    e027 = import_module("zmd_e028_e027", E027_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent_solution = load_parent_solution()
    selected_poles = {
        int(row["pose_idx"])
        for row in parent_solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)
    if not e014.all_powered_facilities_covered(
        solution=parent_solution,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    ):
        raise RuntimeError("E028 parent fails exact power semantics")

    pairs = enumerate_pair_alternatives(
        parent_solution=parent_solution,
        inputs=inputs,
        selected_poles=selected_poles,
        power=power,
        e014=e014,
    )
    records: list[dict[str, Any]] = []
    solution_by_digest: dict[str, dict[str, Any]] = {}
    for index, pair in enumerate(pairs, 1):
        solution = pair["solution"]
        try:
            shared = e015.solve_shared_mismatch(
                solution=solution,
                inputs=inputs,
                e004=e004,
                random_seed=268000 + index,
                include_boundaries=False,
            )
        except RuntimeError as exc:
            if "empty binding domain" not in str(exc):
                raise
            diagnostic = e014.screen_component_interface(
                solution=solution,
                inputs=inputs,
                e001=e001,
                e002=e002,
            )
            if diagnostic.get("status") != "PORT_DOMAIN_EMPTY":
                raise RuntimeError(
                    "E028 empty-domain exception was not reproduced by ordered "
                    f"screen: {diagnostic.get('status')}"
                )
            shared = {
                "status": "PORT_DOMAIN_EMPTY",
                "objective": None,
                "detail": str(exc),
                "empty_filtered_domains": diagnostic.get(
                    "empty_filtered_domains", []
                ),
                "filtered_binding_option_count": diagnostic.get(
                    "filtered_binding_option_count"
                ),
                "front_blocked_patterns_pruned": diagnostic.get(
                    "front_blocked_patterns_pruned"
                ),
                "morphology": diagnostic.get("morphology"),
            }
        digest = stable_digest(solution)
        solution_by_digest[digest] = dict(solution)
        records.append(
            {
                **{key: value for key, value in pair.items() if key != "solution"},
                "candidate_solution_digest": digest,
                "shared_binding": compact_shared(shared),
            }
        )
        if index % 10 == 0:
            print(
                json.dumps(
                    {
                        "event": "E028_PAIR_PROGRESS",
                        "candidate": index,
                        "candidate_total": len(pairs),
                        "packaging_pose": pair["packaging_pose_idx"],
                        "grinder_pose": pair["grinder_pose_idx"],
                        "status": shared.get("status"),
                        "objective": shared.get("objective"),
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    pair_payload = {
        "schema": "zmd_zero_condition_e028_pair_records_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "parent_objective": PARENT_OBJECTIVE,
        "packaging_instance": PACKAGING_INSTANCE,
        "packaging_current_pose": PACKAGING_POSE,
        "grinder_instance": GRINDER_INSTANCE,
        "grinder_current_pose": GRINDER_POSE,
        "pair_count": len(records),
        "records": records,
        "ledger_effect": "none",
    }
    dump_exclusive(PAIR_PATH, pair_payload)

    status_counts = Counter(
        str(record["shared_binding"]["status"]) for record in records
    )
    optimal = [
        record for record in records if record["shared_binding"]["status"] == "OPTIMAL"
    ]
    unlocked_packaging_6186 = [
        record for record in records if int(record["packaging_pose_idx"]) == 6186
    ]
    unlocked_status = Counter(
        str(record["shared_binding"]["status"])
        for record in unlocked_packaging_6186
    )

    common = {
        "schema": "zmd_zero_condition_e028_static_coupling_pair_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "power_semantics": power["summary"],
        "parent_objective": PARENT_OBJECTIVE,
        "pair": {
            "packaging_instance": PACKAGING_INSTANCE,
            "packaging_current_pose": PACKAGING_POSE,
            "grinder_instance": GRINDER_INSTANCE,
            "grinder_current_pose": GRINDER_POSE,
        },
        "pair_count": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "packaging_6186_pair_count": len(unlocked_packaging_6186),
        "packaging_6186_status_counts": dict(sorted(unlocked_status.items())),
        "pair_records_path": str(PAIR_PATH.relative_to(ROOT)),
        "pair_records_sha256": sha256_file(PAIR_PATH),
        "truth_boundary": (
            "Exhaustive simultaneous replacements for two current instances with "
            "all outside placements and selected power poles fixed."
        ),
        "ledger_effect": "none",
    }

    if not optimal:
        empty_frequency = Counter(
            f"{row.get('instance_id')}@{row.get('pose_idx')}"
            for record in records
            for row in record["shared_binding"].get(
                "empty_filtered_domains", []
            )
        )
        return {
            **common,
            "verdict": "STATIC_COUPLING_PAIR_NO_BASE_FEASIBLE_CHILD",
            "optimal_candidate_count": 0,
            "objective_distribution": {},
            "empty_domain_frequency": dict(sorted(empty_frequency.items())),
            "best_child": None,
            "routing": {"status": "NOT_REACHED_NO_OPTIMAL_CHILD"},
            "decision": "DERIVE_NEXT_JOINT_OBJECT_FROM_STATIC_REJECTIONS",
        }

    ranked = sorted(
        optimal,
        key=lambda record: (
            int(record["shared_binding"]["objective"]),
            -int(record["shared_binding"]["filtered_binding_option_count"]),
            int(record["shared_binding"]["morphology"]["free_component_count"]),
            int(record["packaging_pose_idx"]),
            int(record["grinder_pose_idx"]),
        ),
    )
    best = ranked[0]
    best_solution = solution_by_digest[str(best["candidate_solution_digest"])]
    endpoint = e027.materialize_shared_endpoint(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=268999,
    )
    if int(endpoint["objective"]) != int(best["shared_binding"]["objective"]):
        raise RuntimeError("E028 materialized endpoint objective drift")

    assignment_path = OUT / "BEST_PAIR_ASSIGNMENT.json"
    layout_path = OUT / "BEST_PAIR_LAYOUT.json"
    endpoint_path = OUT / "BEST_PAIR_ENDPOINT.json"
    dump_exclusive(
        assignment_path,
        {
            "schema": "zmd_zero_condition_e028_best_pair_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "packaging_replacement_pose": int(best["packaging_pose_idx"]),
            "grinder_replacement_pose": int(best["grinder_pose_idx"]),
            "solution": best_solution,
        },
    )
    dump_exclusive(layout_path, e001.solution_layout(best_solution))
    dump_exclusive(endpoint_path, endpoint)

    objective = int(endpoint["objective"])
    delta = objective - PARENT_OBJECTIVE
    if objective == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        verdict = "STATIC_COUPLING_PAIR_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif delta <= -MATERIAL_IMPROVEMENT:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "SIMULTANEOUS_PAIR_MATERIAL_IMPROVEMENT"
        decision = "RETAIN_PAIR_CHILD_AND_RECOMPUTE_RESIDUAL_SURFACE"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "STATIC_PAIR_REPAIRS_DOMAIN_NOT_COMPONENT"
        decision = "MOVE_BINDING_VARIABLES_INTO_NEXT_JOINT_NEIGHBORHOOD"

    distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal
    )
    return {
        **common,
        "verdict": verdict,
        "optimal_candidate_count": len(optimal),
        "objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "best_child": {
            "objective": objective,
            "delta_from_parent": delta,
            "packaging_replacement_pose_idx": int(best["packaging_pose_idx"]),
            "packaging_replacement_pose_id": str(best["packaging_pose_id"]),
            "grinder_replacement_pose_idx": int(best["grinder_pose_idx"]),
            "grinder_replacement_pose_id": str(best["grinder_pose_id"]),
            "swaps_current_pose_cells": bool(best["swaps_current_pose_cells"]),
            "placement_digest": stable_digest(best_solution),
            "binding_selection_digest": endpoint["selection_digest"],
            "per_commodity": endpoint["per_commodity"],
            "positive_commodity_count": endpoint["positive_commodity_count"],
            "zero_mismatch_commodities": endpoint["zero_mismatch_commodities"],
            "morphology": endpoint["morphology"],
            "filtered_binding_option_count": endpoint[
                "filtered_binding_option_count"
            ],
            "assignment_path": str(assignment_path.relative_to(ROOT)),
            "assignment_sha256": sha256_file(assignment_path),
            "layout_path": str(layout_path.relative_to(ROOT)),
            "layout_sha256": sha256_file(layout_path),
            "endpoint_path": str(endpoint_path.relative_to(ROOT)),
            "endpoint_sha256": sha256_file(endpoint_path),
        },
        "routing": routing,
        "decision": decision,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists() or PAIR_PATH.exists():
        raise FileExistsError("refusing to overwrite E028 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "parent_objective": result["parent_objective"],
                    "pair_count": result["pair_count"],
                    "status_counts": result["status_counts"],
                    "packaging_6186_status_counts": result[
                        "packaging_6186_status_counts"
                    ],
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
            "schema": "zmd_zero_condition_e028_static_coupling_pair_failure_v1",
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
