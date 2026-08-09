#!/usr/bin/env python3
"""Persistent optional-terminal searches for the three periodic large bays.

The CP model is reused from the pinned c5 research script.  This wrapper
rebuilds the complete 35-pole geometry, power mask, canonical pose domain, and
free-cell component for each phase.  Every completed phase is committed to an
exclusive checkpoint before the next solve starts, so a restart loses at most
the phase that was in flight.  No production router is imported or run.
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
HERE = RECOVERY / "big_bays"
ATTEMPTS = HERE / "attempts"
BASE_SCRIPT = RECOVERY / "scripts/c5_pole_phase_search.py"
CANDIDATE_PATH = ROOT / "data/preprocessed/candidate_placements.json"
STRICT_PATH = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
HINT_PATH = RECOVERY / "inputs/reduced_targeted_allocation_p7_36_final.json"
PRIMARY_OUTPUT = HERE / "big_bay_primary_search.json"
NEIGHBOUR_OUTPUT = HERE / "big_bay_neighbour_search.json"
EXPECTED = {
    BASE_SCRIPT: "c7053f9ff3adc41f6d5519c2d76e45b663de2cc4c8b21c53959cf8acff666620",
    CANDIDATE_PATH: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT_PATH: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    HINT_PATH: "6c51a1ee5bef15e555242896a0a11da24c8f18746a215db53c277deee537ee80",
}
GRID_SIZE = 70
GRID = {(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)}
POLE_AXES = (5, 17, 29, 41, 53, 65)
VERTICAL_LANES = (1, 12, 24, 36, 48, 59)
HORIZONTAL_LANES = (1, 36, 59)
CORE_ANCHOR = (60, 60)
PROTECTED = (7, 36, 6, 7)
POLE_ROWS = (5, 17, 29)
TEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")
Cell = tuple[int, int]


class SearchError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SearchError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def load_pinned(path: Path) -> Any:
    observed = sha256(path)
    require(observed == EXPECTED[path], f"hash drift for {path}: {observed}")
    return load_json(path)


for pinned_path in EXPECTED:
    require(pinned_path.is_file(), f"missing pinned input: {pinned_path}")
    require(sha256(pinned_path) == EXPECTED[pinned_path], f"hash drift for {pinned_path}")

sys.path.insert(0, str(BASE_SCRIPT.parent))
import c5_pole_phase_search as base  # noqa: E402


BAYS: dict[str, dict[str, Any]] = {
    "c0": {"component": 0, "origin": (13, 2), "pole_x": 17, "primary": (11, 5, 4)},
    "c1": {"component": 1, "origin": (25, 2), "pole_x": 29, "primary": (11, 5, 4)},
    "c2": {"component": 2, "origin": (37, 2), "pole_x": 41, "primary": (10, 5, 4)},
}
NEIGHBOUR_TARGETS: dict[str, tuple[tuple[int, int, int], ...]] = {
    "c0": ((13, 5, 4), (12, 5, 4), (9, 6, 4), (10, 6, 4)),
    "c1": ((13, 5, 4), (12, 5, 4), (9, 6, 4), (10, 6, 4)),
    "c2": ((12, 5, 4), (11, 5, 4), (8, 6, 4), (9, 6, 4)),
}


def rect(anchor: Cell, width: int, height: int) -> set[Cell]:
    return {
        (x, y)
        for x in range(anchor[0], anchor[0] + width)
        for y in range(anchor[1], anchor[1] + height)
    }


def neighbours(cell: Cell) -> tuple[Cell, Cell, Cell, Cell]:
    x, y = cell
    return ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))


def reachable(starts: set[Cell], free: set[Cell]) -> set[Cell]:
    seen = starts & free
    queue = deque(seen)
    while queue:
        cell = queue.popleft()
        for adjacent in neighbours(cell):
            if adjacent in free and adjacent not in seen:
                seen.add(adjacent)
                queue.append(adjacent)
    return seen


def components(cells: set[Cell]) -> list[set[Cell]]:
    remaining = set(cells)
    result = []
    while remaining:
        connected = reachable({min(remaining)}, remaining)
        result.append(connected)
        remaining -= connected
    return result


def boundary_anchors(gap: int) -> list[int]:
    return list(range(0, gap, 3)) + [gap + 1 + 3 * index for index in range(23 - gap // 3)]


def fixed_geometry(strict: Mapping[str, Any], bay_name: str, moved_x: int, y_shift: int) -> dict[str, Any]:
    bay = BAYS[bay_name]
    core = rect(CORE_ANCHOR, 9, 9)
    core_ring = rect((59, 59), 11, 11) - core
    backbone = (
        {(x, y) for x in VERTICAL_LANES for y in range(1, GRID_SIZE)}
        | {(x, y) for y in HORIZONTAL_LANES for x in range(1, GRID_SIZE)}
        | core_ring
    ) - core
    protected = rect((PROTECTED[0], PROTECTED[1]), PROTECTED[2], PROTECTED[3])
    baseline = {(x, y) for x in POLE_AXES for y in POLE_AXES} - {(65, 65)}
    moved_base = {(int(bay["pole_x"]), y) for y in POLE_ROWS}
    moved = {(moved_x, y + y_shift) for y in POLE_ROWS}
    pole_anchors = (baseline - moved_base) | moved
    require(len(pole_anchors) == 35 and len(pole_anchors) >= 9, "35-pole/P>=9 sentinel")
    pole_cells = set().union(*(rect(anchor, 2, 2) for anchor in pole_anchors))
    left_anchors = boundary_anchors(69)
    bottom_anchors = boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left_anchors for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom_anchors for x in range(anchor, anchor + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(len(pole_cells) == 140 and pole_cells <= GRID, "pole body overlap/out-of-grid")
    require(not pole_cells & (core | boundary | backbone | protected), "pole/fixed collision")
    require(not fixed_body & (backbone | protected), "fixed separator collision")
    power_rule = strict["power"]["coverage_from_pole_anchor"]
    power = {
        (x, y)
        for anchor in pole_anchors
        for x in range(
            max(0, anchor[0] + int(power_rule["x_min_offset"])),
            min(GRID_SIZE - 1, anchor[0] + int(power_rule["x_max_offset"])) + 1,
        )
        for y in range(
            max(0, anchor[1] + int(power_rule["y_min_offset"])),
            min(GRID_SIZE - 1, anchor[1] + int(power_rule["y_max_offset"])) + 1,
        )
    }
    forbidden = fixed_body | backbone | protected
    free_body = GRID - forbidden
    origin = tuple(int(value) for value in bay["origin"])
    component = next(part for part in components(free_body) if origin in part)
    observed_origin = (min(x for x, _y in component), min(y for _x, y in component))
    require(observed_origin == origin, f"{bay_name} origin drift: {observed_origin}")
    gateways = {cell for cell in component if any(adjacent in backbone for adjacent in neighbours(cell))}
    require(gateways, f"{bay_name} has no gateways")
    return {
        "core": core,
        "backbone": backbone,
        "protected": protected,
        "pole_anchors": pole_anchors,
        "pole_cells": pole_cells,
        "boundary": boundary,
        "fixed_body": fixed_body,
        "forbidden": forbidden,
        "power": power,
        "c5": component,
        "origin": origin,
        "gateways": gateways,
    }


def hint_body_modes(old: Mapping[str, Any], bay_name: str, origin: Cell) -> set[tuple[str, str, frozenset[Cell]]]:
    component_id = int(BAYS[bay_name]["component"])
    records = [record for record in old["components"] if int(record["component"]) == component_id]
    require(len(records) == 1, f"hint component cardinality for {bay_name}")
    return {
        (
            str(raw["template"]),
            str(raw["mode"]),
            frozenset((origin[0] + int(x), origin[1] + int(y)) for x, y in raw["body"]),
        )
        for raw in records[0]["selected"]
    }


def phase_order(pole_x: int) -> list[tuple[int, int]]:
    shifts = (0, -1, 1, -2, 2, -3, 3)
    return [(pole_x + dx, shift) for dx in (1, -1, 0) for shift in shifts]


def checkpoint_path(bay_name: str, target: tuple[int, int, int], moved_x: int, y_shift: int) -> Path:
    target_text = "-".join(str(value) for value in target)
    shift_text = f"p{y_shift}" if y_shift >= 0 else f"m{-y_shift}"
    return ATTEMPTS / bay_name / f"t{target_text}_x{moved_x}_dy{shift_text}.json"


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def validate_checkpoint(
    record: Mapping[str, Any],
    bay_name: str,
    target: tuple[int, int, int],
    moved_x: int,
    y_shift: int,
    seconds: float,
) -> dict[str, Any]:
    require(record.get("schema_version") == "big_bay_phase_checkpoint.v1", "checkpoint schema")
    require(record.get("bay") == bay_name, "checkpoint bay")
    require(tuple(record.get("target", ())) == target, "checkpoint target")
    require(int(record.get("moved_x")) == moved_x, "checkpoint moved_x")
    require(int(record.get("uniform_y_shift")) == y_shift, "checkpoint y_shift")
    require(float(record.get("seconds_limit")) == seconds, "checkpoint seconds")
    require(record.get("search_script_sha256") == sha256(Path(__file__)), "checkpoint script drift")
    return dict(record)


def run_phase(
    candidate: Mapping[str, Any],
    strict: Mapping[str, Any],
    old: Mapping[str, Any],
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
    bay_name: str,
    target: tuple[int, int, int],
    moved_x: int,
    y_shift: int,
    seconds: float,
    workers: int,
    seed: int,
) -> dict[str, Any]:
    path = checkpoint_path(bay_name, target, moved_x, y_shift)
    if path.exists():
        return validate_checkpoint(load_json(path), bay_name, target, moved_x, y_shift, seconds)
    fixed = fixed_geometry(strict, bay_name, moved_x, y_shift)
    poses, domain_counts = base.build_domain(candidate, modes, fixed)
    hints = hint_body_modes(old, bay_name, fixed["origin"])
    result = base.solve_phase(poses, target, fixed, hints, seconds, workers, seed)
    moved = sorted((moved_x, y + y_shift) for y in POLE_ROWS)
    result.update(
        {
            "schema_version": "big_bay_phase_checkpoint.v1",
            "classification": "research_local_optional_terminal_parent_query_no_router",
            "claim_boundary": "One local bay/phase only; no global layout or commodity-routing conclusion.",
            "bay": bay_name,
            "component": int(BAYS[bay_name]["component"]),
            "origin": list(fixed["origin"]),
            "target": list(target),
            "moved_x": moved_x,
            "uniform_y_shift": y_shift,
            "moved_pole_anchors": [list(anchor) for anchor in moved],
            "all_35_pole_anchors": [list(anchor) for anchor in sorted(fixed["pole_anchors"])],
            "domain_counts": domain_counts,
            "seconds_limit": seconds,
            "search_script_sha256": sha256(Path(__file__)),
            "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        }
    )
    write_exclusive(path, result)
    return result


def normalized_pose(row: Mapping[str, Any], origin: Cell) -> tuple[Any, ...]:
    def local(raw_cells: Sequence[Sequence[int]]) -> tuple[Cell, ...]:
        return tuple(sorted((int(cell[0]) - origin[0], int(cell[1]) - origin[1]) for cell in raw_cells))

    return (
        str(row["template"]),
        str(row["mode"]),
        local(row["body"]),
        local(row["inputs"]),
        local(row["outputs"]),
    )


def pose_normalized(pose: Any, origin: Cell) -> tuple[Any, ...]:
    return (
        pose.template,
        pose.mode,
        tuple(sorted((x - origin[0], y - origin[1]) for x, y in pose.body)),
        tuple(sorted((x - origin[0], y - origin[1]) for x, y in pose.inputs)),
        tuple(sorted((x - origin[0], y - origin[1]) for x, y in pose.outputs)),
    )


def derive_isomorphic_c1(
    source: Mapping[str, Any],
    candidate: Mapping[str, Any],
    strict: Mapping[str, Any],
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    require(source["bay"] == "c0" and tuple(source["target"]) == (11, 5, 4), "c0 source")
    dx = int(BAYS["c1"]["origin"][0]) - int(BAYS["c0"]["origin"][0])
    moved_x = int(source["moved_x"]) + dx
    y_shift = int(source["uniform_y_shift"])
    source_fixed = fixed_geometry(strict, "c0", int(source["moved_x"]), y_shift)
    target_fixed = fixed_geometry(strict, "c1", moved_x, y_shift)
    source_poses, _source_counts = base.build_domain(candidate, modes, source_fixed)
    target_poses, target_counts = base.build_domain(candidate, modes, target_fixed)
    source_keys = {pose_normalized(pose, source_fixed["origin"]) for pose in source_poses}
    target_map = {pose_normalized(pose, target_fixed["origin"]): pose for pose in target_poses}
    require(len(target_map) == len(target_poses), "c1 normalized pose collision")
    require(source_keys == set(target_map), "c0/c1 strict local-key domain isomorphism")
    selected = []
    selected_poses = []
    for row in source["selected"]:
        key = normalized_pose(row, source_fixed["origin"])
        require(key in target_map, "selected c0 pose absent from c1 domain")
        pose = target_map[key]
        selected_poses.append(pose)
        selected.append(
            {
                "template": pose.template,
                "mode": pose.mode,
                "pose_index": pose.pose_index,
                "anchor": list(pose.anchor),
                "body": [list(cell) for cell in sorted(pose.body)],
                "inputs": [list(cell) for cell in pose.inputs],
                "outputs": [list(cell) for cell in pose.outputs],
            }
        )
    occupied: set[Cell] = set()
    for pose in selected_poses:
        require(not occupied & pose.body, "derived c1 body overlap")
        require(bool(pose.body & target_fixed["power"]), "derived c1 unpowered body")
        occupied.update(pose.body)
    free = set(target_fixed["c5"]) - occupied
    main = reachable(set(target_fixed["gateways"]), free)
    outside_main = set(target_fixed["backbone"]) | set(target_fixed["protected"])
    active = []
    for raw in source["selected_weak_active"]:
        selected_index = int(raw["selected_index"])
        kind = str(raw["kind"])
        source_cell = (int(raw["cell"][0]), int(raw["cell"][1]))
        cell = (source_cell[0] + dx, source_cell[1])
        pose = selected_poses[selected_index]
        cells = pose.inputs if kind == "input" else pose.outputs
        require(cell in cells, "derived c1 terminal port mismatch")
        require(cell not in occupied and (cell in main or cell in outside_main), "derived c1 terminal disconnected")
        active.append(
            {
                "selected_index": selected_index,
                "kind": kind,
                "port_index": cells.index(cell),
                "cell": list(cell),
            }
        )
    observed = tuple(Counter(row["template"] for row in selected)[template] for template in TEMPLATES)
    require(observed == (11, 5, 4), "derived c1 target")
    moved = sorted((moved_x, y + y_shift) for y in POLE_ROWS)
    return {
        "schema_version": "big_bay_isomorphic_derivation.v1",
        "classification": "research_strict_local_key_translation_no_solver_no_router",
        "claim_boundary": "Local c0-to-c1 periodic translation only; no global layout or commodity-routing conclusion.",
        "status": "ISOMORPHIC_FEASIBLE",
        "bay": "c1",
        "source_bay": "c0",
        "source_checkpoint_sha256": sha256(checkpoint_path("c0", (11, 5, 4), int(source["moved_x"]), y_shift)),
        "translation": [dx, 0],
        "component": 1,
        "origin": list(target_fixed["origin"]),
        "target": [11, 5, 4],
        "moved_x": moved_x,
        "uniform_y_shift": y_shift,
        "moved_pole_anchors": [list(anchor) for anchor in moved],
        "all_35_pole_anchors": [list(anchor) for anchor in sorted(target_fixed["pole_anchors"])],
        "domain_counts": target_counts,
        "local_domain_keys": len(target_map),
        "strict_local_key_sets_equal": True,
        "component_cells": len(target_fixed["c5"]),
        "gateway_cells": len(target_fixed["gateways"]),
        "body_cells": len(occupied),
        "residual_cells": len(free),
        "residual_main_cells": len(main),
        "all_residual_connected": main == free,
        "selected_weak_active_count": len(active),
        "selected_weak_active": active,
        "selected": selected,
        "independent_verification": {
            "no_body_overlap": True,
            "exact_template_totals": True,
            "all_selected_bodies_powered": True,
            "all_selected_weak_active_connected": True,
            "strict_local_key_sets_equal": True,
        },
    }


def search_target(
    candidate: Mapping[str, Any],
    strict: Mapping[str, Any],
    old: Mapping[str, Any],
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
    bay_name: str,
    target: tuple[int, int, int],
    seconds: float,
    workers: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    rows = []
    pole_x = int(BAYS[bay_name]["pole_x"])
    for attempt_index, (moved_x, y_shift) in enumerate(phase_order(pole_x), start=1):
        row = run_phase(
            candidate,
            strict,
            old,
            modes,
            bay_name,
            target,
            moved_x,
            y_shift,
            seconds,
            workers,
            20260720 + int(BAYS[bay_name]["component"]) * 1000 + attempt_index,
        )
        rows.append(row)
        print(
            f"bay={bay_name} target={target} x={moved_x} dy={y_shift} "
            f"status={row['status']} seconds={float(row['wall_time_seconds']):.3f}",
            flush=True,
        )
        if row["status"] in {"OPTIMAL", "FEASIBLE"}:
            return row, rows
    return None, rows


def primary(
    candidate: Mapping[str, Any],
    strict: Mapping[str, Any],
    old: Mapping[str, Any],
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
    seconds: float,
    workers: int,
) -> int:
    require(not PRIMARY_OUTPUT.exists(), f"refusing overwrite: {PRIMARY_OUTPUT}")
    winners: dict[str, dict[str, Any]] = {}
    attempts: dict[str, list[dict[str, Any]]] = {}
    c0, attempts["c0"] = search_target(candidate, strict, old, modes, "c0", (11, 5, 4), seconds, workers)
    if c0 is not None:
        winners["c0"] = c0
        winners["c1"] = derive_isomorphic_c1(c0, candidate, strict, modes)
    c2, attempts["c2"] = search_target(candidate, strict, old, modes, "c2", (10, 5, 4), seconds, workers)
    if c2 is not None:
        winners["c2"] = c2
    complete = set(winners) == set(BAYS)
    record = {
        "schema_version": "big_bay_primary_search.v1",
        "status": "PRIMARY_TARGETS_FEASIBLE" if complete else "PRIMARY_TARGET_NOT_FOUND_WITHIN_PHASE_LIMITS",
        "classification": "research_local_large_bay_optional_terminal_search_no_router",
        "claim_boundary": "Three local large bays only; no global layout or commodity-routing conclusion.",
        "search_script_sha256": sha256(Path(__file__)),
        "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        "seconds_per_phase": seconds,
        "workers": workers,
        "phase_order": {
            name: [{"moved_x": x, "uniform_y_shift": dy} for x, dy in phase_order(int(bay["pole_x"]))]
            for name, bay in BAYS.items()
        },
        "winners": winners,
        "attempt_checkpoint_paths": {
            name: [str(checkpoint_path(name, tuple(row["target"]), int(row["moved_x"]), int(row["uniform_y_shift"]))) for row in rows]
            for name, rows in attempts.items()
        },
    }
    write_exclusive(PRIMARY_OUTPUT, record)
    return 0 if complete else 1


def neighbours_stage(
    candidate: Mapping[str, Any],
    strict: Mapping[str, Any],
    old: Mapping[str, Any],
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
    seconds: float,
    workers: int,
) -> int:
    require(PRIMARY_OUTPUT.is_file(), "primary output required before neighbours")
    require(not NEIGHBOUR_OUTPUT.exists(), f"refusing overwrite: {NEIGHBOUR_OUTPUT}")
    primary_record = load_json(PRIMARY_OUTPUT)
    require(primary_record.get("status") == "PRIMARY_TARGETS_FEASIBLE", "primary targets incomplete")
    winners: dict[str, list[dict[str, Any]]] = {}
    attempted: dict[str, list[list[int]]] = {}
    for bay_name in BAYS:
        winners[bay_name] = []
        attempted[bay_name] = []
        for target in NEIGHBOUR_TARGETS[bay_name]:
            winner, _rows = search_target(candidate, strict, old, modes, bay_name, target, seconds, workers)
            attempted[bay_name].append(list(target))
            if winner is not None:
                winners[bay_name].append(winner)
    record = {
        "schema_version": "big_bay_neighbour_search.v1",
        "status": "NEIGHBOUR_TARGET_CATALOG_COMPLETE",
        "classification": "research_local_large_bay_neighbour_catalog_no_router",
        "claim_boundary": "Local count-rebalancing catalog only; absent targets are not global infeasibility conclusions.",
        "primary_output_sha256": sha256(PRIMARY_OUTPUT),
        "search_script_sha256": sha256(Path(__file__)),
        "seconds_per_phase": seconds,
        "workers": workers,
        "attempted_targets": attempted,
        "winners": winners,
    }
    write_exclusive(NEIGHBOUR_OUTPUT, record)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("primary", "neighbours"))
    parser.add_argument("--seconds-per-phase", type=float, default=90.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    require(60.0 <= args.seconds_per_phase <= 120.0, "seconds-per-phase must be within [60,120]")
    require(args.workers == 8, "this recovery search is pinned to 8 workers")
    candidate = load_pinned(CANDIDATE_PATH)
    strict = load_pinned(STRICT_PATH)
    old = load_pinned(HINT_PATH)
    modes = base.strict_modes(strict)
    if args.stage == "primary":
        return primary(candidate, strict, old, modes, args.seconds_per_phase, args.workers)
    return neighbours_stage(candidate, strict, old, modes, args.seconds_per_phase, args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
