#!/usr/bin/env python3
"""E095: exact product decomposition of the fixed y=41 native-front slice."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.preprocess.operation_profiles import get_operation_port_profile  # noqa: E402

DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001"
)
E094_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E094_y41_fixed_pole_front_decomposition/run-001/RESULT.json"
)
E094_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E094_y41_fixed_pole_front_decomposition/run-001/ARTIFACT_CHECK.json"
)
E094_DERIVED = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E094_y41_fixed_pole_front_decomposition/run-001/DERIVED_PRODUCER.py"
)
E094_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E094_y41_fixed_pole_front_decomposition/RESULT.txt"
)
ANCHOR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001/"
    "state-00-partition_90abd29523f2a0dc/RESULT.json"
)
FRONTIER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E081_axis_seam_recolor_frontier/run-001/AXIS_SEAM_FRONTIER.json"
)
PARENT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json"
)
MACRO = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E079_k47_boundary_macro/run-001/BOUNDARY_MACRO_V1.json"
)
CANDIDATES = HISTORY / "data/preprocessed/candidate_placements.json"
MANDATORY = HISTORY / "data/preprocessed/mandatory_exact_instances.json"
STRICT = (
    ROOT
    / "docs/research/cleanroom_rederivation_20260718/strict/external/"
    "problem_instance.json"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"

EXPECTED_HASHES = {
    E094_RESULT: "2f8903fd49b2cda2767c2fbb8b3c272d68b1483fc1ce5d4b02c06a22c48e5877",
    E094_CHECK: "9e70b8ec451bfb52f9376cabc075adbd2d76056b91d01613e4d94753b344d6f8",
    E094_DERIVED: "65c6cadc4d0f37266ca181761bec625bcfdf7d8be2b344136a6a14b5669ac4ce",
    E094_DURABLE: "eea15b5d1d2eff70dc005757e43aa97e8f398d17dbbff4a2272db0753aec655a",
    ANCHOR: "7bc3cc6ccd48f919e08561c7b32262da56f9f3853d5fbca313413add4bd87a78",
    FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    MANDATORY: "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
}

TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
EXPECTED_MANUFACTURING_COUNT = 219
EXPECTED_POLE_COUNT = 53
BOUNDARY_STATE_INDEX = 8
BOUNDARY_STATE_ID = "boundary_macro_09"
SEAM_Y = 41
STABLE_OPERATION_BY_ID = {
    "grinder_dense_source_001": "grinder_fine_buckwheat",
    "grinder_fine_buckwheat_002": "filling_capsule",
}
STABLE_CLASS_BY_BODY = {
    "da277903615efb73fbc9bb30716cae3b9b96654bed9905addebba0e27accf33d": (3, 1),
    "ef71d17d5e4db7bb4c3baeeee913780c753409802365896a67988bfcb43176be": (4, 1),
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def dump_exclusive(path: Path, payload: Any) -> None:
    raw = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def cell(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def in_grid(value: tuple[int, int]) -> bool:
    return 0 <= value[0] < 70 and 0 <= value[1] < 70


def collect_instances(value: Any) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}

    def visit(current: Any) -> None:
        if isinstance(current, Mapping):
            if "instance_id" in current and "facility_type" in current:
                instance_id = str(current["instance_id"])
                row = dict(current)
                prior = output.get(instance_id)
                if prior is not None and prior != row:
                    raise RuntimeError(f"mandatory instance collision: {instance_id}")
                output[instance_id] = row
            for member in current.values():
                visit(member)
        elif isinstance(current, Sequence) and not isinstance(
            current, (str, bytes, bytearray)
        ):
            for member in current:
                visit(member)

    visit(value)
    return output


def process_snapshot() -> dict[str, int]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "ru_maxrss_kib": int(usage.ru_maxrss),
        "minor_page_faults": int(usage.ru_minflt),
        "major_page_faults": int(usage.ru_majflt),
        "voluntary_context_switches": int(usage.ru_nvcsw),
        "involuntary_context_switches": int(usage.ru_nivcsw),
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E095 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E095 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E095 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    e094 = load_json(E094_RESULT)
    if e094.get("verdict") != "FIXED_POLE_BOUNDARY_FRONT_SLICE_CENSORED":
        raise RuntimeError("E095 trigger E094 verdict drift")
    if e094.get("decision") != (
        "DECOMPOSE_BODY_FRONT_ASSIGNMENT_BEFORE_RELEASING_BOUNDARY_OR_POLES"
    ):
        raise RuntimeError("E095 trigger E094 decision drift")
    if load_json(E094_CHECK).get("status") != "PASS":
        raise RuntimeError("E095 trigger E094 artifact check is not PASS")

    anchor = load_json(ANCHOR)
    if anchor.get("status") != "BODY_POWER_FEASIBLE":
        raise RuntimeError("E095 anchor is not BODY_POWER_FEASIBLE")
    if anchor.get("partition_id") != "partition_90abd29523f2a0dc":
        raise RuntimeError("E095 anchor partition drift")
    if int(anchor.get("selected_boundary_state_index", -1)) != BOUNDARY_STATE_INDEX:
        raise RuntimeError("E095 anchor boundary index drift")
    if anchor.get("selected_boundary_state_id") != BOUNDARY_STATE_ID:
        raise RuntimeError("E095 anchor boundary ID drift")
    if len(anchor.get("selected_poles", [])) != EXPECTED_POLE_COUNT:
        raise RuntimeError("E095 anchor pole cardinality drift")
    if len(anchor.get("selected_manufacturing", [])) != EXPECTED_MANUFACTURING_COUNT:
        raise RuntimeError("E095 anchor manufacturing cardinality drift")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def build_context() -> dict[str, Any]:
    pools = load_json(CANDIDATES)["facility_pools"]
    parent = load_json(PARENT)["solution"]
    macro = load_json(MACRO)
    strict = load_json(STRICT)
    anchor = load_json(ANCHOR)
    frontier = load_json(FRONTIER)
    detailed = {
        row["partition"]["partition_id"]: row
        for row in frontier["detailed_candidates"]
    }
    partition_row = detailed["partition_90abd29523f2a0dc"]
    partition = partition_row["partition"]
    corridor = partition_row["best_reference_preserving"]["corridor"]
    if not (
        corridor["axis"] == "y"
        and int(corridor["start"]) == SEAM_Y
        and int(corridor["end"]) == SEAM_Y
        and corridor["module_low"] == "A"
        and corridor["module_high"] == "B"
    ):
        raise RuntimeError(f"E095 corridor drift: {corridor}")

    module_operations = {
        "A": tuple(map(str, partition["module_a_operations"])),
        "B": tuple(map(str, partition["module_b_operations"])),
    }
    operation_to_module = {
        operation: module
        for module, operations in module_operations.items()
        for operation in operations
    }
    instances = collect_instances(load_json(MANDATORY))
    operation_counts = Counter(
        str(row["operation_type"])
        for row in instances.values()
        if str(row.get("operation_type", "")) in operation_to_module
    )
    if sum(operation_counts.values()) != EXPECTED_MANUFACTURING_COUNT:
        raise RuntimeError(f"E095 operation-count drift: {operation_counts}")

    class_operations: dict[tuple[str, str, int, int], list[str]] = defaultdict(list)
    class_counts: Counter[tuple[str, str, int, int]] = Counter()
    for operation, count in sorted(operation_counts.items()):
        profile = get_operation_port_profile(operation)
        if int(profile.generic_input_slots) or int(profile.generic_output_slots):
            raise RuntimeError(f"E095 generic manufacturing slot drift: {operation}")
        module = operation_to_module[operation]
        template = str(profile.facility_type)
        need_in = sum(int(value) for value in profile.input_slots.values())
        need_out = sum(int(value) for value in profile.output_slots.values())
        key = (module, template, need_in, need_out)
        class_operations[key].append(operation)
        class_counts[key] += int(count)
    if sum(class_counts.values()) != EXPECTED_MANUFACTURING_COUNT:
        raise RuntimeError("E095 class-count drift")

    for template in TEMPLATES:
        if strict["facility_templates"][template]["requires_power"] is not True:
            raise RuntimeError(f"E095 power rule drift: {template}")
    if strict["facility_templates"]["protocol_core"]["requires_power"] is not False:
        raise RuntimeError("E095 protocol-core power rule drift")

    current_manufacturing: dict[tuple[tuple[int, int], ...], dict[str, Any]] = {}
    core_body: set[tuple[int, int]] = set()
    core_fronts: set[tuple[int, int]] = set()
    stable_footprints: dict[str, tuple[tuple[int, int], ...]] = {}
    for instance_id, row in parent.items():
        template = str(row["facility_type"])
        pose = pools[template][int(row["pose_idx"])]
        body = tuple(sorted(cell(value) for value in pose["occupied_cells"]))
        if template.startswith("manufacturing_"):
            current_manufacturing[body] = {
                "instance_id": str(instance_id),
                "facility_type": template,
            }
            if instance_id in STABLE_OPERATION_BY_ID:
                stable_footprints[str(instance_id)] = body
        elif template == "protocol_core":
            core_body = set(body)
            core_fronts = {
                cell(value)
                for field in ("input_port_cells", "output_port_cells")
                for value in pose[field]
            }
    if len(current_manufacturing) != EXPECTED_MANUFACTURING_COUNT:
        raise RuntimeError("E095 current manufacturing count drift")
    if set(stable_footprints) != set(STABLE_OPERATION_BY_ID):
        raise RuntimeError("E095 stable footprint drift")
    if not core_body or not core_fronts:
        raise RuntimeError("E095 protocol-core geometry missing")

    pole_pose_indices = tuple(
        sorted(int(row["pose_index"]) for row in anchor["selected_poles"])
    )
    if len(pole_pose_indices) != EXPECTED_POLE_COUNT:
        raise RuntimeError("E095 fixed pole count drift")
    fixed_pole_body: set[tuple[int, int]] = set()
    fixed_coverage: set[tuple[int, int]] = set()
    for pose_index in pole_pose_indices:
        pose = pools["power_pole"][pose_index]
        body = {cell(value) for value in pose["occupied_cells"]}
        if fixed_pole_body & body:
            raise RuntimeError("E095 fixed poles overlap")
        fixed_pole_body |= body
        fixed_coverage |= {cell(value) for value in pose["power_coverage_cells"]}

    state = macro["states"][BOUNDARY_STATE_INDEX]
    if str(state["state_id"]) != BOUNDARY_STATE_ID:
        raise RuntimeError("E095 boundary state identity drift")
    boundary_body = {cell(value) for value in state["body_cells"]}
    boundary_fronts = {cell(value) for value in state["front_cells"]}
    boundary_reserved = boundary_body | boundary_fronts
    seam = {(x, SEAM_Y) for x in range(1, 69)}
    fixed_solid = core_body | fixed_pole_body | boundary_body
    fixed_forbidden = (
        core_body
        | core_fronts
        | fixed_pole_body
        | boundary_reserved
        | seam
    )

    body_modes: dict[str, dict[tuple[tuple[int, int], ...], tuple[int, ...]]] = {}
    for template in TEMPLATES:
        grouped: dict[tuple[tuple[int, int], ...], list[int]] = defaultdict(list)
        for pose_index, pose in enumerate(pools[template]):
            body = tuple(sorted(cell(value) for value in pose["occupied_cells"]))
            grouped[body].append(int(pose_index))
        body_modes[template] = {
            body: tuple(indices) for body, indices in grouped.items()
        }

    body_rows: list[dict[str, Any]] = []
    domain_counts: Counter[tuple[str, str]] = Counter()
    for module, side in (("A", "low"), ("B", "high")):
        for template in TEMPLATES:
            for body, mode_indices in body_modes[template].items():
                ys = [y for _x, y in body]
                if side == "low" and max(ys) >= SEAM_Y:
                    continue
                if side == "high" and min(ys) <= SEAM_Y:
                    continue
                if set(body) & fixed_forbidden:
                    continue
                body_rows.append(
                    {
                        "module": module,
                        "template": template,
                        "body": body,
                        "body_digest": stable_digest(body),
                        "mode_pose_indices": mode_indices,
                        "is_current": body in current_manufacturing,
                        "current_owner": current_manufacturing.get(body),
                    }
                )
                domain_counts[(module, template)] += 1

    hint_bodies = {
        str(row["module"]): set()
        for row in anchor["selected_manufacturing"]
    }
    hint_bodies = {"A": set(), "B": set()}
    for row in anchor["selected_manufacturing"]:
        module = str(row["module"])
        hint_bodies[module].add(
            tuple(sorted(cell(value) for value in row["body"]))
        )
    if sum(len(values) for values in hint_bodies.values()) != EXPECTED_MANUFACTURING_COUNT:
        raise RuntimeError("E095 hint manufacturing count drift")
    row_keys = {
        (str(row["module"]), tuple(row["body"]))
        for row in body_rows
    }
    unmatched_hint = [
        (module, body)
        for module, bodies in hint_bodies.items()
        for body in bodies
        if (module, body) not in row_keys
    ]
    if unmatched_hint:
        raise RuntimeError(f"E095 hint body remap drift: {unmatched_hint[:3]}")

    return {
        "pools": pools,
        "module_operations": module_operations,
        "operation_counts": operation_counts,
        "class_operations": dict(class_operations),
        "class_counts": class_counts,
        "body_rows": body_rows,
        "domain_counts": domain_counts,
        "fixed_solid": fixed_solid,
        "fixed_forbidden": fixed_forbidden,
        "fixed_coverage": fixed_coverage,
        "pole_pose_indices": pole_pose_indices,
        "boundary_state": state,
        "boundary_body": boundary_body,
        "boundary_fronts": boundary_fronts,
        "seam": seam,
        "stable_footprints": stable_footprints,
        "hint_bodies": hint_bodies,
    }


def all_front_cells(
    rows: Sequence[Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> set[tuple[int, int]]:
    output: set[tuple[int, int]] = set()
    for row in rows:
        template = str(row["template"])
        for pose_index in row["mode_pose_indices"]:
            pose = pools[template][int(pose_index)]
            for field in ("input_port_cells", "output_port_cells"):
                output.update(
                    value
                    for raw in pose[field]
                    for value in [cell(raw)]
                    if in_grid(value)
                )
    return output


def decomposition_audit(context: Mapping[str, Any]) -> dict[str, Any]:
    rows = context["body_rows"]
    a_rows = [row for row in rows if row["module"] == "A"]
    b_rows = [row for row in rows if row["module"] == "B"]
    a_body = {value for row in a_rows for value in row["body"]}
    b_body = {value for row in b_rows for value in row["body"]}
    a_front = all_front_cells(a_rows, context["pools"])
    b_front = all_front_cells(b_rows, context["pools"])
    cross_body = a_body & b_body
    a_front_b_body = a_front & b_body
    b_front_a_body = b_front & a_body
    front_front = a_front & b_front

    class_keys = list(context["class_counts"])
    class_module_values = {str(key[0]) for key in class_keys}
    module_local_counts = class_module_values == {"A", "B"}
    a_front_ys = [value[1] for value in a_front]
    b_front_ys = [value[1] for value in b_front]

    exact_product = (
        not cross_body
        and not a_front_b_body
        and not b_front_a_body
        and module_local_counts
        and bool(context["pole_pose_indices"])
        and str(context["boundary_state"]["state_id"]) == BOUNDARY_STATE_ID
    )
    if not exact_product:
        raise RuntimeError(
            "E095 product decomposition failed: "
            f"body={len(cross_body)} Afront/Bbody={len(a_front_b_body)} "
            f"Bfront/Abody={len(b_front_a_body)} classes={module_local_counts}"
        )

    return {
        "schema": "zmd_e095_y41_product_decomposition_audit_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "exact_product_for_native_front_layer": True,
        "module_candidate_counts": {
            "A": len(a_rows),
            "B": len(b_rows),
        },
        "module_template_domain_counts": {
            f"{module}:{template}": int(count)
            for (module, template), count in sorted(context["domain_counts"].items())
        },
        "module_body_union_cell_counts": {
            "A": len(a_body),
            "B": len(b_body),
        },
        "module_front_union_cell_counts": {
            "A": len(a_front),
            "B": len(b_front),
        },
        "module_front_y_ranges": {
            "A": [min(a_front_ys), max(a_front_ys)],
            "B": [min(b_front_ys), max(b_front_ys)],
        },
        "cross_body_cell_count": len(cross_body),
        "a_front_b_body_intersection_count": len(a_front_b_body),
        "b_front_a_body_intersection_count": len(b_front_a_body),
        "cross_front_front_intersection_count": len(front_front),
        "cross_front_front_cells": [list(value) for value in sorted(front_front)],
        "class_counts_module_local": module_local_counts,
        "fixed_pole_count": len(context["pole_pose_indices"]),
        "fixed_boundary_state_id": str(context["boundary_state"]["state_id"]),
        "reasoning": (
            "Opposite-module body variables cannot share a body cell or occupy a "
            "native front cell of the other module. Pole, boundary and core body "
            "occupancy are constants, and all count equations are module-indexed. "
            "Front/front coincidence is not constrained at this layer."
        ),
        "truth_boundary": (
            "Exact only for the fixed-pole, fixed-boundary native-front class layer; "
            "terminal uniqueness and commodity semantics can recouple the modules."
        ),
    }


def solver_for(seed: int, seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = int(seed)
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.randomize_search = True
    solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    solver.parameters.repair_hint = True
    solver.parameters.hint_conflict_limit = 2000
    solver.parameters.stop_after_first_solution = True
    return solver


def materialize_named_operations(
    *,
    module: str,
    selected_mode_rows: Sequence[Mapping[str, Any]],
    stable_indices: Mapping[str, int],
    operation_counts: Mapping[str, int],
    class_operations: Mapping[tuple[str, str, int, int], Sequence[str]],
) -> dict[int, str]:
    selected_by_class: dict[tuple[str, str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in selected_mode_rows:
        selected_by_class[tuple(row["class_key"])].append(dict(row))

    remaining = {
        operation: int(count)
        for operation, count in operation_counts.items()
        if operation in {
            value
            for key, operations in class_operations.items()
            if key[0] == module
            for value in operations
        }
    }
    output: dict[int, str] = {}
    if module == "B":
        for instance_id, operation in STABLE_OPERATION_BY_ID.items():
            body_index = int(stable_indices[instance_id])
            matches = [
                row
                for rows in selected_by_class.values()
                for row in rows
                if int(row["body_index"]) == body_index
            ]
            if len(matches) != 1:
                raise RuntimeError(f"E095 stable selected mode drift: {instance_id}")
            output[body_index] = operation
            remaining[operation] -= 1
            if remaining[operation] < 0:
                raise RuntimeError(f"E095 stable operation underflow: {operation}")

    for class_key in sorted(selected_by_class):
        rows = sorted(
            selected_by_class[class_key],
            key=lambda row: (str(row["body_digest"]), int(row["body_index"])),
        )
        free_rows = [row for row in rows if int(row["body_index"]) not in output]
        operations: list[str] = []
        for operation in sorted(class_operations[class_key]):
            operations.extend([operation] * int(remaining[operation]))
        if len(operations) != len(free_rows):
            raise RuntimeError(
                f"E095 class operation materialization mismatch {class_key}: "
                f"{len(operations)} != {len(free_rows)}"
            )
        for row, operation in zip(free_rows, operations, strict=True):
            output[int(row["body_index"])] = operation
            remaining[operation] -= 1
    if any(remaining.values()):
        raise RuntimeError(f"E095 unassigned operation counts: {remaining}")
    return output


def solve_module(
    *,
    context: Mapping[str, Any],
    module: str,
    seconds: float,
    seed: int,
) -> dict[str, Any]:
    rows = [dict(row) for row in context["body_rows"] if row["module"] == module]
    model = cp_model.CpModel()
    body_vars = [model.NewBoolVar(f"{module}_body_{index}") for index in range(len(rows))]

    body_vars_by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            body_vars_by_cell[value].append(body_vars[index])
    for terms in body_vars_by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    module_class_counts = {
        key: int(count)
        for key, count in context["class_counts"].items()
        if key[0] == module
    }
    mode_rows: list[dict[str, Any]] = []
    classes_by_body: dict[int, list[Any]] = defaultdict(list)
    classes_by_key: dict[tuple[str, str, int, int], list[Any]] = defaultdict(list)
    pools = context["pools"]
    fixed_solid = set(context["fixed_solid"])

    for body_index, row in enumerate(rows):
        template = str(row["template"])
        relevant = [
            key
            for key in module_class_counts
            if key[1] == template
        ]
        forced = STABLE_CLASS_BY_BODY.get(str(row["body_digest"]))
        for pose_index in row["mode_pose_indices"]:
            pose = pools[template][int(pose_index)]
            input_cells = tuple(cell(value) for value in pose["input_port_cells"])
            output_cells = tuple(cell(value) for value in pose["output_port_cells"])
            for class_key in relevant:
                _module, _template, need_in, need_out = class_key
                if forced is not None and (need_in, need_out) != forced:
                    continue
                if need_in > len(input_cells) or need_out > len(output_cells):
                    continue
                variable = model.NewBoolVar(
                    f"{module}_mc_{body_index}_{pose_index}_{need_in}_{need_out}"
                )
                classes_by_body[body_index].append(variable)
                classes_by_key[class_key].append(variable)
                mode_rows.append(
                    {
                        "body_index": body_index,
                        "body_digest": str(row["body_digest"]),
                        "pose_index": int(pose_index),
                        "class_key": class_key,
                        "need_in": int(need_in),
                        "need_out": int(need_out),
                        "input_cells": input_cells,
                        "output_cells": output_cells,
                        "variable": variable,
                    }
                )
        if classes_by_body[body_index]:
            model.Add(sum(classes_by_body[body_index]) == body_vars[body_index])
        else:
            model.Add(body_vars[body_index] == 0)

    for class_key, required in sorted(module_class_counts.items()):
        terms = classes_by_key[class_key]
        if len(terms) < required:
            raise RuntimeError(
                f"E095 {module} class domain shortage {class_key}: "
                f"{len(terms)} < {required}"
            )
        model.Add(sum(terms) == required)

    template_counts: Counter[str] = Counter()
    for (_module, template, _need_in, _need_out), count in module_class_counts.items():
        template_counts[template] += int(count)
    for template, required in sorted(template_counts.items()):
        model.Add(
            sum(
                body_vars[index]
                for index, row in enumerate(rows)
                if row["template"] == template
            )
            == required
        )

    for mode_row in mode_rows:
        variable = mode_row["variable"]
        for front_cells, need in (
            (mode_row["input_cells"], int(mode_row["need_in"])),
            (mode_row["output_cells"], int(mode_row["need_out"])),
        ):
            fixed_blocked = sum(
                (not in_grid(value)) or value in fixed_solid
                for value in front_cells
            )
            dynamic_terms = [
                body_var
                for value in front_cells
                if in_grid(value) and value not in fixed_solid
                for body_var in body_vars_by_cell.get(value, [])
            ]
            model.Add(
                fixed_blocked + sum(dynamic_terms)
                <= len(front_cells) - need + len(front_cells) * (1 - variable)
            )

    fixed_coverage = set(context["fixed_coverage"])
    disabled_unpowered = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & fixed_coverage:
            model.Add(body_vars[index] == 0)
            disabled_unpowered += 1

    stable_indices: dict[str, int] = {}
    if module == "B":
        for instance_id, footprint in context["stable_footprints"].items():
            matches = [
                index
                for index, row in enumerate(rows)
                if tuple(row["body"]) == footprint
                and row["template"] == "manufacturing_6x4"
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"E095 stable body remap drift {instance_id}: {matches}"
                )
            stable_indices[instance_id] = matches[0]
            model.Add(body_vars[matches[0]] == 1)

    hint_bodies = context["hint_bodies"][module]
    matched_hint = 0
    for index, row in enumerate(rows):
        selected = tuple(row["body"]) in hint_bodies
        model.AddHint(body_vars[index], int(selected))
        matched_hint += int(selected)
    required_module_bodies = sum(template_counts.values())
    if matched_hint != required_module_bodies:
        raise RuntimeError(
            f"E095 {module} hint remap drift: {matched_hint} != {required_module_bodies}"
        )

    validation = model.Validate()
    if validation:
        raise RuntimeError(f"E095 {module} model invalid: {validation}")
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(seed, seconds)
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    after = process_snapshot()
    solver_status = solver.StatusName(status)

    result: dict[str, Any] = {
        "schema": "zmd_e095_module_front_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "module": module,
        "status": solver_status,
        "solver_status": solver_status,
        "elapsed_seconds": elapsed,
        "seed": int(seed),
        "solve_seconds": float(seconds),
        "body_candidate_count": len(rows),
        "mode_class_variable_count": len(mode_rows),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "class_counts": {
            f"{key[0]}:{key[1]}:{key[2]}:{key[3]}": value
            for key, value in sorted(module_class_counts.items())
        },
        "template_counts": dict(sorted(template_counts.items())),
        "disabled_unpowered_candidate_count": disabled_unpowered,
        "stable_body_candidate_indices": stable_indices,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
        "truth_boundary": (
            "Exact module-local body, fixed-pole power and native-front class model "
            "under the E095 product audit. No terminal uniqueness or commodity semantics."
        ),
    }

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_body_indices = [
            index for index, variable in enumerate(body_vars) if solver.Value(variable)
        ]
        selected_modes = []
        for mode_row in mode_rows:
            if solver.Value(mode_row["variable"]):
                selected_modes.append(
                    {
                        "body_index": int(mode_row["body_index"]),
                        "body_digest": str(mode_row["body_digest"]),
                        "pose_index": int(mode_row["pose_index"]),
                        "class_key": list(mode_row["class_key"]),
                        "need_in": int(mode_row["need_in"]),
                        "need_out": int(mode_row["need_out"]),
                    }
                )
        if len(selected_body_indices) != required_module_bodies:
            raise RuntimeError(f"E095 {module} selected body count drift")
        if len(selected_modes) != required_module_bodies:
            raise RuntimeError(f"E095 {module} selected mode count drift")
        operation_by_body = materialize_named_operations(
            module=module,
            selected_mode_rows=selected_modes,
            stable_indices=stable_indices,
            operation_counts=context["operation_counts"],
            class_operations=context["class_operations"],
        )
        mode_by_body = {int(row["body_index"]): row for row in selected_modes}
        selected = []
        for body_index in selected_body_indices:
            row = rows[body_index]
            mode = mode_by_body[body_index]
            template = str(row["template"])
            pose_index = int(mode["pose_index"])
            selected.append(
                {
                    "module": module,
                    "body_index": body_index,
                    "template": template,
                    "body": [list(value) for value in row["body"]],
                    "body_digest": str(row["body_digest"]),
                    "is_current": bool(row["is_current"]),
                    "current_owner": row["current_owner"],
                    "operation": operation_by_body[body_index],
                    "pose_index": pose_index,
                    "pose_id": str(pools[template][pose_index]["pose_id"]),
                    "need_in": int(mode["need_in"]),
                    "need_out": int(mode["need_out"]),
                    "class_key": list(mode["class_key"]),
                }
            )
        result.update(
            {
                "selected_body_count": len(selected),
                "retained_current_body_count": sum(
                    bool(row["is_current"]) for row in selected
                ),
                "selected_manufacturing": selected,
                "selected_assignment_digest": stable_digest(selected),
            }
        )
    return result


def replay_combined(
    context: Mapping[str, Any],
    module_a: Mapping[str, Any],
    module_b: Mapping[str, Any],
) -> dict[str, Any]:
    selected = [
        *[dict(row) for row in module_a["selected_manufacturing"]],
        *[dict(row) for row in module_b["selected_manufacturing"]],
    ]
    if len(selected) != EXPECTED_MANUFACTURING_COUNT:
        raise RuntimeError("E095 combined body count drift")

    owner_by_cell: dict[tuple[int, int], str] = {
        value: "fixed_solid" for value in context["fixed_solid"]
    }
    for index, row in enumerate(selected):
        for value in map(cell, row["body"]):
            prior = owner_by_cell.get(value)
            if prior is not None:
                raise RuntimeError(
                    f"E095 combined body overlap at {value}: {prior}/{index}"
                )
            owner_by_cell[value] = f"manufacturing::{index}"
    occupied = set(owner_by_cell)

    observed_operations = Counter(str(row["operation"]) for row in selected)
    if observed_operations != context["operation_counts"]:
        raise RuntimeError(
            f"E095 combined operation count drift: {observed_operations}"
        )
    observed_classes = Counter(tuple(row["class_key"]) for row in selected)
    if observed_classes != context["class_counts"]:
        raise RuntimeError(f"E095 combined class count drift: {observed_classes}")

    unpowered: list[int] = []
    front_failures: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        body = {cell(value) for value in row["body"]}
        if not body & context["fixed_coverage"]:
            unpowered.append(index)
        pose = context["pools"][str(row["template"])][int(row["pose_index"])]
        input_cells = [cell(value) for value in pose["input_port_cells"]]
        output_cells = [cell(value) for value in pose["output_port_cells"]]
        free_inputs = [
            value for value in input_cells if in_grid(value) and value not in occupied
        ]
        free_outputs = [
            value for value in output_cells if in_grid(value) and value not in occupied
        ]
        if len(free_inputs) < int(row["need_in"]) or len(free_outputs) < int(
            row["need_out"]
        ):
            front_failures.append(
                {
                    "index": index,
                    "body_digest": row["body_digest"],
                    "free_inputs": len(free_inputs),
                    "need_in": int(row["need_in"]),
                    "free_outputs": len(free_outputs),
                    "need_out": int(row["need_out"]),
                }
            )
    if unpowered or front_failures:
        raise RuntimeError(
            f"E095 combined replay failed: unpowered={unpowered[:5]} "
            f"front={front_failures[:3]}"
        )

    stable_observed = {
        str(row.get("current_owner", {}).get("instance_id", "")): str(
            row["operation"]
        )
        for row in selected
        if isinstance(row.get("current_owner"), Mapping)
    }
    for instance_id, operation in STABLE_OPERATION_BY_ID.items():
        if stable_observed.get(instance_id) != operation:
            raise RuntimeError(
                f"E095 stable operation replay drift: {instance_id}: "
                f"{stable_observed.get(instance_id)} != {operation}"
            )

    return {
        "schema": "zmd_e095_combined_front_witness_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "partition_id": "partition_90abd29523f2a0dc",
        "seam": {"axis": "y", "coordinate": SEAM_Y},
        "boundary_state_index": BOUNDARY_STATE_INDEX,
        "boundary_state_id": BOUNDARY_STATE_ID,
        "pole_pose_indices": list(context["pole_pose_indices"]),
        "pole_set_digest": stable_digest(list(context["pole_pose_indices"])),
        "selected_manufacturing_count": len(selected),
        "operation_counts": dict(sorted(observed_operations.items())),
        "class_counts": {
            f"{key[0]}:{key[1]}:{key[2]}:{key[3]}": int(value)
            for key, value in sorted(observed_classes.items())
        },
        "selected_manufacturing": selected,
        "selected_assignment_digest": stable_digest(selected),
        "occupied_cell_count": len(occupied),
        "unpowered_count": 0,
        "front_failure_count": 0,
        "truth_boundary": (
            "Combined exact native-front class witness only. Terminal uniqueness, "
            "generic I/O, component compatibility and routing are not checked."
        ),
    }


def prepare(run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E095 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    context = build_context()
    audit = decomposition_audit(context)
    audit["identity"] = identity
    audit_path = run_dir / "DECOMPOSITION_AUDIT.json"
    dump_exclusive(audit_path, audit)
    return {
        "status": "PREPARED",
        "audit_path": display(audit_path),
        "audit_sha256": sha256_file(audit_path),
        "module_candidate_counts": audit["module_candidate_counts"],
    }


def solve_stage(
    *,
    run_dir: Path,
    module: str,
    seconds: float,
    seed: int,
) -> dict[str, Any]:
    verify_identity()
    audit_path = run_dir / "DECOMPOSITION_AUDIT.json"
    if load_json(audit_path).get("status") != "PASS":
        raise RuntimeError("E095 decomposition audit is not PASS")
    output = run_dir / f"MODULE_{module}_RESULT.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite E095 module result: {output}")
    result = solve_module(
        context=build_context(),
        module=module,
        seconds=seconds,
        seed=seed,
    )
    dump_exclusive(output, result)
    return {
        "status": result["status"],
        "module": module,
        "elapsed_seconds": result["elapsed_seconds"],
        "branches": result["branches"],
        "conflicts": result["conflicts"],
        "selected_body_count": result.get("selected_body_count", 0),
        "output_path": display(output),
        "output_sha256": sha256_file(output),
    }


def finalize(run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    result_path = run_dir / "RESULT.json"
    if result_path.exists():
        raise FileExistsError(f"refusing to overwrite E095 result: {result_path}")
    audit_path = run_dir / "DECOMPOSITION_AUDIT.json"
    audit = load_json(audit_path)
    if audit.get("status") != "PASS":
        raise RuntimeError("E095 decomposition audit is not PASS")
    module_results = {
        module: load_json(run_dir / f"MODULE_{module}_RESULT.json")
        for module in ("A", "B")
    }
    positive = {
        module: result["status"] in {"OPTIMAL", "FEASIBLE"}
        for module, result in module_results.items()
    }
    combined_path = run_dir / "COMBINED_WITNESS.json"
    combined: dict[str, Any] | None = None
    if all(positive.values()):
        combined = replay_combined(
            build_context(), module_results["A"], module_results["B"]
        )
        dump_exclusive(combined_path, combined)
        verdict = "Y41_FIXED_SKELETON_FRONT_PRODUCT_WITNESS_FOUND"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    else:
        statuses = {module: str(result["status"]) for module, result in module_results.items()}
        infeasible = [module for module, status in statuses.items() if status == "INFEASIBLE"]
        unknown = [
            module
            for module, status in statuses.items()
            if status not in {"OPTIMAL", "FEASIBLE", "INFEASIBLE"}
        ]
        if infeasible:
            label = "_".join(infeasible)
            verdict = f"Y41_FIXED_SKELETON_FRONT_INFEASIBLE_LOCALIZED_{label}"
            decision = f"DECOMPOSE_MODULE_{infeasible[0]}_BY_TEMPLATE_OR_BAY"
        elif len(unknown) == 1:
            verdict = f"MODULE_{unknown[0]}_FRONT_SUBMODEL_CENSORED"
            decision = f"DECOMPOSE_MODULE_{unknown[0]}_BY_TEMPLATE_OR_BAY"
        else:
            verdict = "BOTH_MODULE_FRONT_SUBMODELS_CENSORED"
            decision = "DECOMPOSE_BOTH_MODULES_SEPARATELY_BEFORE_RELEASING_SKELETON"

    result = {
        "schema": "zmd_e095_y41_module_product_decomposition_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "decomposition_audit": {
            "path": display(audit_path),
            "sha256": sha256_file(audit_path),
            "exact_product_for_native_front_layer": bool(
                audit["exact_product_for_native_front_layer"]
            ),
            "cross_body_cell_count": int(audit["cross_body_cell_count"]),
            "a_front_b_body_intersection_count": int(
                audit["a_front_b_body_intersection_count"]
            ),
            "b_front_a_body_intersection_count": int(
                audit["b_front_a_body_intersection_count"]
            ),
            "cross_front_front_intersection_count": int(
                audit["cross_front_front_intersection_count"]
            ),
        },
        "modules": {
            module: {
                "status": result["status"],
                "elapsed_seconds": result["elapsed_seconds"],
                "body_candidate_count": result["body_candidate_count"],
                "mode_class_variable_count": result["mode_class_variable_count"],
                "model_variable_count": result["model_variable_count"],
                "model_constraint_count": result["model_constraint_count"],
                "branches": result["branches"],
                "conflicts": result["conflicts"],
                "selected_body_count": result.get("selected_body_count", 0),
                "retained_current_body_count": result.get(
                    "retained_current_body_count"
                ),
                "path": display(run_dir / f"MODULE_{module}_RESULT.json"),
                "sha256": sha256_file(
                    run_dir / f"MODULE_{module}_RESULT.json"
                ),
            }
            for module, result in module_results.items()
        },
        "combined_witness": (
            {
                "path": display(combined_path),
                "sha256": sha256_file(combined_path),
                "status": combined["status"],
                "selected_manufacturing_count": combined[
                    "selected_manufacturing_count"
                ],
                "selected_assignment_digest": combined[
                    "selected_assignment_digest"
                ],
            }
            if combined is not None
            else None
        ),
        "truth_boundary": (
            "Exact factorization and module solves for one fixed y=41 pole/boundary "
            "native-front class problem. No terminal uniqueness, generic I/O, "
            "component binding, routing, throughput or whole-layout claim."
        ),
    }
    dump_exclusive(result_path, result)
    return {
        "verdict": verdict,
        "decision": decision,
        "module_statuses": {
            module: value["status"] for module, value in module_results.items()
        },
        "combined_witness": combined is not None,
        "result_path": display(result_path),
        "result_sha256": sha256_file(result_path),
    }


def failure_path(run_dir: Path, stage: str) -> Path:
    return run_dir / f"FAILURE_{stage.upper()}.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=("prepare", "solve", "finalize"),
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--module", choices=("A", "B"))
    parser.add_argument("--seconds", type=float, default=120.0)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    try:
        if args.stage == "prepare":
            output = prepare(run_dir)
        elif args.stage == "solve":
            if args.module is None or args.seed is None:
                raise RuntimeError("solve stage requires --module and --seed")
            output = solve_stage(
                run_dir=run_dir,
                module=args.module,
                seconds=float(args.seconds),
                seed=int(args.seed),
            )
        else:
            output = finalize(run_dir)
        print(json.dumps(output, ensure_ascii=False, sort_keys=True), flush=True)
        return 0
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        path = failure_path(run_dir, args.stage)
        failure = {
            "schema": "zmd_e095_execution_failure_v1",
            "created_at_utc": utc_now(),
            "stage": args.stage,
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not path.exists():
            dump_exclusive(path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
