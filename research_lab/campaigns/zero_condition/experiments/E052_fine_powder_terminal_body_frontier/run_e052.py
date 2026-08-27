#!/usr/bin/env python3
"""E052: exact one-body first-zero frontier for fine_buckwheat_powder."""

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
import time
import traceback
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E052_fine_powder_terminal_body_frontier/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
PROPOSED_BLOCK_PATH = OUT / "PROPOSED_6X4_BLOCK.json"
TARGET_COMMODITY = "fine_buckwheat_powder"

E051_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E051_positive_commodity_frontier/"
    "run-001/RESULT.json"
)
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
E013_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E013_residual_boundary_coverage/run_e013.py"
)
E014_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E014_fixed_outside_mobility/run_e014.py"
)
E041_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E041_joint_port_mode_assignment/run_e041.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "282000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E051_RESULT: "7c0b50f8ce92e8e12e7be89a7e7e2f612facd650173abd823e4867ce9e984c04",
    E050_ASSIGNMENT: "8964829329cc98d4ea58d691854d6d81a9723248a6467d9a159d010bbcdabe55",
    E050_ENDPOINT: "04999122509a580c501eb0458d9909abf65dbd5075fd3f06b5ca928355be9b86",
    E051_RUNNER: "e287c3c4323494b894792435b44fe2c23458345ca2f7409b06309170e9c4ca87",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E041_RUNNER: "5731b294e5c3070617d3a29e8912e4f859da207c6f183354ad9c7194f2d54b06",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
}

TARGET_INSTANCE_IDS = (
    "grinder_fine_buckwheat_004",
    "grinder_fine_buckwheat_005",
    "grinder_fine_buckwheat_006",
    "filling_capsule_001",
    "filling_capsule_002",
    "filling_capsule_003",
)
GRID_W = 70
GRID_H = 70


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
    endpoint = load_json(E050_ENDPOINT)
    if result_51.get("verdict") != "FIRST_ZERO_INFEASIBLE_IN_BOUNDED_JOINT_CONTEXT":
        raise RuntimeError("E052 E051 trigger verdict drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != 139:
        raise RuntimeError("E052 E050 endpoint drift")
    if int(endpoint["per_commodity"][TARGET_COMMODITY]) != 1:
        raise RuntimeError("E052 target commodity drift")
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


def target_payload(
    *,
    instance_id: str,
    solution: Mapping[str, Mapping[str, Any]],
    group_by_instance: Mapping[str, str],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    e014: Any,
) -> dict[str, Any]:
    row = solution[instance_id]
    facility_type = str(row["facility_type"])
    pose_idx = int(row["pose_idx"])
    return {
        "literal_key": f"mandatory::{group_by_instance[instance_id]}::{pose_idx}",
        "kind": "mandatory_group_pose",
        "consumer_id": group_by_instance[instance_id],
        "facility_type": facility_type,
        "operation_type": str(row["operation_type"]),
        "pose_idx": pose_idx,
        "pose_id": str(row["pose_id"]),
        "occupied_cells": [
            list(cell)
            for cell in sorted(e014.pose_cells(pools, facility_type, pose_idx))
        ],
        "source_instance_ids": [instance_id],
        "anchor": json_safe(row["anchor"]),
    }


def mode_component_audit(
    *,
    instance_id: str,
    solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e041: Any,
) -> dict[str, Any]:
    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_binding_context import build_routing_binding_context

    row = solution[instance_id]
    facility_type = str(row["facility_type"])
    operation_type = str(row["operation_type"])
    current_pose_idx = int(row["pose_idx"])
    body = e041.body_cells(
        pools=inputs["pools"],
        facility_type=facility_type,
        pose_idx=current_pose_idx,
    )
    modes = [
        pose_idx
        for pose_idx in range(len(inputs["pools"][facility_type]))
        if e041.body_cells(
            pools=inputs["pools"],
            facility_type=facility_type,
            pose_idx=pose_idx,
        )
        == body
    ]
    side = "output_ports" if operation_type == "grinder_fine_buckwheat" else "input_ports"
    rows: list[dict[str, Any]] = []
    for pose_idx in modes:
        pose = inputs["pools"][facility_type][pose_idx]
        candidate = {str(key): dict(value) for key, value in solution.items()}
        replacement = dict(candidate[instance_id])
        replacement["pose_idx"] = int(pose_idx)
        replacement["pose_id"] = str(pose["pose_id"])
        replacement["anchor"] = json_safe(pose["anchor"])
        candidate[instance_id] = replacement
        routing_context = build_routing_binding_context(
            candidate,
            inputs["pools"],
            GRID_W,
            GRID_H,
        )
        plan = inputs["plan"]
        generic = inputs["generic"]
        binding_model = PortBindingModel(
            placement_solution=candidate,
            facility_pools=inputs["pools"],
            instances=inputs["instances"],
            project_root=HISTORY_ROOT,
            required_generic_outputs=generic.get("required_generic_outputs", {}),
            required_generic_inputs=generic.get("required_generic_inputs", {}),
            generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
            generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
            utility_operation_by_template=plan["utility_operation_by_template"],
            canonical_rules_payload=inputs["rules"],
            routing_context=routing_context,
        )
        binding_model.build()
        domain = binding_model.binding_domains.get(instance_id, [])
        front_cells: set[tuple[int, int]] = set()
        components: set[int] = set()
        pattern_component_sets: set[tuple[int, ...]] = set()
        for pattern in domain:
            pattern_components: set[int] = set()
            for port in pattern[side]:
                if str(port.get("commodity")) != TARGET_COMMODITY:
                    continue
                cell = (int(port["x"]), int(port["y"]))
                front_cells.add(cell)
                component = routing_context.component_by_cell.get(cell)
                if component is not None:
                    component_int = int(component)
                    components.add(component_int)
                    pattern_components.add(component_int)
            pattern_component_sets.add(tuple(sorted(pattern_components)))
        rows.append(
            {
                "pose_idx": int(pose_idx),
                "pose_id": str(pose["pose_id"]),
                "is_current": int(pose_idx) == current_pose_idx,
                "domain_count": len(domain),
                "empty_domain": not domain,
                "target_front_cells": [list(cell) for cell in sorted(front_cells)],
                "target_components": sorted(components),
                "pattern_component_sets": [
                    list(value) for value in sorted(pattern_component_sets)
                ],
            }
        )
    return {
        "instance_id": instance_id,
        "facility_type": facility_type,
        "operation_type": operation_type,
        "current_pose_idx": current_pose_idx,
        "mode_count": len(modes),
        "modes": rows,
    }


def solve_target_candidate(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e004: Any,
) -> dict[str, Any]:
    from src.models.routing_binding_context import build_routing_binding_context
    from src.models.routing_subproblem import RoutingPlacementCore

    routing_context = build_routing_binding_context(
        solution,
        inputs["pools"],
        GRID_W,
        GRID_H,
    )
    placement_core = RoutingPlacementCore.from_occupied_cells(
        set(routing_context.occupied_cells),
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    try:
        result = e004.solve_commodity(
            commodity=TARGET_COMMODITY,
            solution=solution,
            instances=inputs["instances"],
            pools=inputs["pools"],
            rules=inputs["rules"],
            generic=inputs["generic"],
            plan=inputs["plan"],
            routing_context=routing_context,
            placement_core=placement_core,
        )
    except RuntimeError as exc:
        return {
            "status": "PORT_DOMAIN_OR_INTERFACE_REJECTED",
            "detail": str(exc),
            "minimum_mismatch_count": None,
        }
    return {
        "status": str(result["status"]),
        "minimum_mismatch_count": result.get("minimum_mismatch_count"),
        "selection_digest": result.get("selection_digest"),
        "selected_components": result.get("selected_components"),
        "mismatch_boundaries": result.get("mismatch_boundaries"),
        "production_precheck_status": result.get("production_precheck_status"),
        "production_precheck_reports_target": result.get(
            "production_precheck_reports_target"
        ),
        "support_summary": result.get("support_summary"),
        "build_seconds": result.get("build_seconds"),
        "solve_seconds": result.get("solve_seconds"),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e051 = import_module("zmd_e052_e051", E051_RUNNER)
    e013 = import_module("zmd_e052_e013", E013_RUNNER)
    e014 = import_module("zmd_e052_e014", E014_RUNNER)
    context = e051.reconstruct_context()
    e004 = context["e004"]
    e041 = context["e041"]
    e004.SOLVE_CAP_SECONDS = 20.0
    inputs = context["inputs"]
    solution = context["best_solution"]
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(mandatory, list):
        raise RuntimeError("E052 mandatory instances are not a list")
    group_by_instance = e013.group_mapping(mandatory)

    base_target = solve_target_candidate(
        solution=solution,
        inputs=inputs,
        e004=e004,
    )
    if base_target.get("status") != "OPTIMAL" or int(
        base_target["minimum_mismatch_count"]
    ) != 1:
        raise RuntimeError("E052 base target minimum drift")

    occupancy, _ = e014.base_occupancy(solution, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(
        context["e001"], context["stack"], inputs
    )

    mode_audits: list[dict[str, Any]] = []
    arm_results: list[dict[str, Any]] = []
    zero_candidates: list[dict[str, Any]] = []
    for arm_index, instance_id in enumerate(TARGET_INSTANCE_IDS, 1):
        mode_audits.append(
            mode_component_audit(
                instance_id=instance_id,
                solution=solution,
                inputs=inputs,
                e041=e041,
            )
        )
        target = target_payload(
            instance_id=instance_id,
            solution=solution,
            group_by_instance=group_by_instance,
            pools=inputs["pools"],
            e014=e014,
        )
        alternatives = e014.enumerate_alternatives(
            target=target,
            base_solution=solution,
            pools=inputs["pools"],
            occupied=occupancy,
            selected_poles=selected_poles,
            powered_templates=power["powered_templates"],
            coverers=power["coverers"],
        )
        candidate_rows: list[dict[str, Any]] = []
        for candidate_index, candidate in enumerate(alternatives, 1):
            started = time.monotonic()
            target_result = solve_target_candidate(
                solution=candidate["solution"],
                inputs=inputs,
                e004=e004,
            )
            row = {
                "candidate_index": candidate_index,
                "pose_idx": int(candidate["pose_idx"]),
                "pose_id": str(candidate["pose_id"]),
                "anchor": json_safe(candidate["anchor"]),
                "same_footprint": bool(candidate["same_footprint"]),
                "target_result": target_result,
                "candidate_solution_digest": stable_digest(candidate["solution"]),
                "elapsed_seconds": time.monotonic() - started,
            }
            candidate_rows.append(row)
            if (
                target_result.get("status") == "OPTIMAL"
                and int(target_result["minimum_mismatch_count"]) == 0
            ):
                zero_candidates.append(
                    {
                        "arm_index": arm_index,
                        "instance_id": instance_id,
                        **row,
                    }
                )
        minima = [
            int(row["target_result"]["minimum_mismatch_count"])
            for row in candidate_rows
            if row["target_result"].get("minimum_mismatch_count") is not None
        ]
        arm_results.append(
            {
                "arm_index": arm_index,
                "instance_id": instance_id,
                "target": target,
                "alternative_count": len(alternatives),
                "same_footprint_alternative_count": sum(
                    bool(row["same_footprint"]) for row in candidate_rows
                ),
                "body_alternative_count": sum(
                    not bool(row["same_footprint"]) for row in candidate_rows
                ),
                "status_counts": dict(
                    sorted(
                        Counter(
                            str(row["target_result"]["status"])
                            for row in candidate_rows
                        ).items()
                    )
                ),
                "minimum_target_mismatch": min(minima) if minima else None,
                "zero_candidate_count": sum(
                    row["target_result"].get("minimum_mismatch_count") == 0
                    for row in candidate_rows
                ),
                "candidate_rows": candidate_rows,
            }
        )
        print(
            json.dumps(
                {
                    "event": "E052_ARM_DONE",
                    "arm": arm_index,
                    "instance_id": instance_id,
                    "alternatives": len(alternatives),
                    "minimum": arm_results[-1]["minimum_target_mismatch"],
                    "zero_count": arm_results[-1]["zero_candidate_count"],
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    merged_block = next(
        block for block in context["blocks"] if str(block["block_id"]) == "6x4_merged"
    )
    current_selected = set(context["selected_ids_by_block"]["6x4_merged"])
    relevant_inside = sorted(set(TARGET_INSTANCE_IDS) & current_selected)
    relevant_outside = sorted(set(TARGET_INSTANCE_IDS) - current_selected)
    proposed_selected = sorted(
        current_selected | set(relevant_outside),
        key=lambda instance_id: (
            int(solution[instance_id]["pose_idx"]),
            instance_id,
        ),
    )
    operation_counts = Counter(
        str(solution[instance_id]["operation_type"])
        for instance_id in proposed_selected
    )
    proposed_block = {
        "schema": "zmd_zero_condition_e052_proposed_6x4_block_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "source_block_id": str(merged_block["block_id"]),
        "facility_type": "manufacturing_6x4",
        "current_selected_instance_ids": sorted(current_selected),
        "relevant_inside_instance_ids": relevant_inside,
        "relevant_outside_instance_ids": relevant_outside,
        "proposed_selected_instance_ids": proposed_selected,
        "proposed_destination_count": len(proposed_selected),
        "operation_multiset": dict(sorted(operation_counts.items())),
        "pose_rows": [
            {
                "instance_id": instance_id,
                "operation_type": str(solution[instance_id]["operation_type"]),
                "pose_idx": int(solution[instance_id]["pose_idx"]),
                "pose_id": str(solution[instance_id]["pose_id"]),
                "anchor": json_safe(solution[instance_id]["anchor"]),
            }
            for instance_id in proposed_selected
        ],
        "reason": (
            "Expose the three right-edge fine-powder source bodies and the missing "
            "capsule sink body to one operation-assignment context before adding "
            "another body relocation language."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(PROPOSED_BLOCK_PATH, proposed_block)

    if zero_candidates:
        verdict = "ONE_BODY_FIRST_ZERO_FOUND"
        decision = "REVALUE_ZERO_BEARING_GEOMETRIES_WITH_JOINT_MIDDLE"
    elif relevant_outside:
        verdict = "ONE_BODY_FIRST_ZERO_INFEASIBLE_ASSIGNMENT_BLOCK_INCOMPLETE"
        decision = "MERGE_RELEVANT_6X4_BODIES_INTO_ASSIGNMENT_CONTEXT"
    else:
        verdict = "ONE_BODY_FIRST_ZERO_INFEASIBLE_FULL_RELEVANT_BLOCK"
        decision = "BUILD_NATIVE_SIMULTANEOUS_BODY_CONTEXT"

    return {
        "schema": "zmd_zero_condition_e052_fine_powder_terminal_body_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "target_commodity": TARGET_COMMODITY,
        "base_target_result": base_target,
        "mode_audits": mode_audits,
        "arm_results": arm_results,
        "total_alternative_count": sum(
            int(row["alternative_count"]) for row in arm_results
        ),
        "total_body_alternative_count": sum(
            int(row["body_alternative_count"]) for row in arm_results
        ),
        "zero_candidate_count": len(zero_candidates),
        "zero_candidates": zero_candidates,
        "assignment_membership": {
            "current_6x4_block_size": len(current_selected),
            "relevant_inside_instance_ids": relevant_inside,
            "relevant_outside_instance_ids": relevant_outside,
        },
        "proposed_block_path": str(PROPOSED_BLOCK_PATH.relative_to(ROOT)),
        "proposed_block_sha256": sha256_file(PROPOSED_BLOCK_PATH),
        "decision": decision,
        "truth_boundary": (
            "Six target instances and every placement-/power-valid fixed-outside "
            "pose alternative on E050 Seed C only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists() or PROPOSED_BLOCK_PATH.exists():
        raise FileExistsError("refusing to overwrite E052 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "total_alternatives": result["total_alternative_count"],
                    "body_alternatives": result["total_body_alternative_count"],
                    "zero_candidates": result["zero_candidate_count"],
                    "arm_minima": {
                        row["instance_id"]: row["minimum_target_mismatch"]
                        for row in result["arm_results"]
                    },
                    "relevant_outside": result["assignment_membership"][
                        "relevant_outside_instance_ids"
                    ],
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
            "schema": "zmd_zero_condition_e052_fine_powder_terminal_body_frontier_failure_v1",
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
