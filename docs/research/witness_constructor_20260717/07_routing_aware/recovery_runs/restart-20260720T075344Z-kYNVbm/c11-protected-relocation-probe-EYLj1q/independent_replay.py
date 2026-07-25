#!/usr/bin/env python3
"""Pure-stdlib replay of the c11 removed-protected local witness."""

from __future__ import annotations

import ast
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RUN = ROOT / (
    "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm/c11-protected-relocation-probe-EYLj1q"
)
RESULT = RUN / "result.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
OUTPUT = RUN / "independent_replay.json"
EXPECTED = {
    RESULT: "7777f458f4b6856f7fde55d7a923c32c691cac1d0a1363e707905de05766a230",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
GRID_SIZE = 70
GRID = {(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)}
VERTICAL = (1, 12, 24, 36, 48, 59)
HORIZONTAL = (1, 36, 59)
POLE_AXES = (5, 17, 29, 41, 53, 65)
MODE_MAP = {
    "TB": "north_to_south",
    "BT": "south_to_north",
    "RL": "east_to_west",
    "LR": "west_to_east",
}
DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
REQUIREMENTS = {
    "manufacturing_3x3": (1, 1),
    "manufacturing_5x5": (1, 1),
    "manufacturing_6x4": (3, 1),
}
Cell = tuple[int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rect(anchor: Cell, width: int, height: int) -> set[Cell]:
    return {
        (x, y)
        for x in range(anchor[0], anchor[0] + width)
        for y in range(anchor[1], anchor[1] + height)
    }


def ring(body: set[Cell]) -> set[Cell]:
    xs = [x for x, _y in body]
    ys = [y for _x, y in body]
    return rect((min(xs) - 1, min(ys) - 1), max(xs) - min(xs) + 3, max(ys) - min(ys) + 3) - body


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


def component(start: Cell, free: set[Cell]) -> set[Cell]:
    require(start in free, f"representative blocked: {start}")
    return reachable({start}, free)


def boundary_anchors(gap: int) -> list[int]:
    return list(range(0, gap, 3)) + [gap + 1 + 3 * index for index in range(23 - gap // 3)]


def strict_modes(strict: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (str(template), str(mode["id"])): mode
        for template, record in strict["facility_templates"].items()
        for mode in record["modes"]
    }


def strict_access(mode: Mapping[str, Any], anchor: Cell) -> tuple[tuple[Cell, ...], tuple[Cell, ...]]:
    by_kind: dict[str, list[Cell]] = defaultdict(list)
    for port in mode["ports"]:
        dx, dy = DELTA[str(port["direction"])]
        body_cell = port["body_cell"]
        by_kind[str(port["kind"])].append(
            (anchor[0] + int(body_cell["x"]) + dx, anchor[1] + int(body_cell["y"]) + dy)
        )
    return tuple(sorted(by_kind["input"])), tuple(sorted(by_kind["output"]))


def main() -> int:
    require(not OUTPUT.exists(), f"refusing overwrite: {OUTPUT}")
    for path, expected in EXPECTED.items():
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    result = json.loads(RESULT.read_bytes())
    candidate = json.loads(CANDIDATE.read_bytes())
    strict = json.loads(STRICT.read_bytes())
    require(result["status"] == "OPTIMAL", "source result not optimal")
    require(result["component"] == 11 and result["target"] == [9, 1, 2], "source identity")
    origin = tuple(int(value) for value in result["origin"])
    require(origin == (2, 37), "source origin")

    core = rect((60, 60), 9, 9)
    backbone = (
        {(x, y) for x in VERTICAL for y in range(1, GRID_SIZE)}
        | {(x, y) for y in HORIZONTAL for x in range(1, GRID_SIZE)}
        | ring(core)
    ) - core
    removed_protected = rect((7, 36), 6, 7)
    require({tuple(cell) for cell in result["removed_protected_cells"]} == removed_protected, "removed protected drift")
    poles = {tuple(cell) for cell in result["all_35_pole_anchors"]}
    expected_poles = {(x, y) for x in POLE_AXES for y in POLE_AXES} - {(65, 65)}
    require(poles == expected_poles and len(poles) == 35, "baseline pole anchors")
    pole_mode = strict["facility_templates"][strict["power"]["pole_template"]]["modes"]
    require(len(pole_mode) == 1, "pole mode count")
    pole_width = int(pole_mode[0]["body"]["width"])
    pole_height = int(pole_mode[0]["body"]["height"])
    require((pole_width, pole_height) == (2, 2), "pole body dimensions")
    pole_cells = set().union(*(rect(anchor, pole_width, pole_height) for anchor in poles))
    require(len(pole_cells) == 140, "pole body collision")
    left = boundary_anchors(69)
    bottom = boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom for x in range(anchor, anchor + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(not fixed_body & backbone, "fixed/backbone collision")
    forbidden = fixed_body | backbone
    c11 = component((2, 37), GRID - forbidden)
    gateways = {cell for cell in c11 if any(adjacent in backbone for adjacent in neighbours(cell))}
    require(len(c11) == result["component_cells"] == 212, "component size")
    require(len(gateways) == result["gateway_cells"] == 60, "gateway size")

    power_rule = strict["power"]["coverage_from_pole_anchor"]
    power = {
        (x, y)
        for anchor in poles
        for x in range(max(0, anchor[0] + int(power_rule["x_min_offset"])), min(69, anchor[0] + int(power_rule["x_max_offset"])) + 1)
        for y in range(max(0, anchor[1] + int(power_rule["y_min_offset"])), min(69, anchor[1] + int(power_rule["y_max_offset"])) + 1)
    }
    modes = strict_modes(strict)
    candidate_by_signature: dict[tuple[str, str, frozenset[Cell]], list[Mapping[str, Any]]] = defaultdict(list)
    for template in REQUIREMENTS:
        for raw in candidate["facility_pools"][template]:
            body = frozenset((int(x), int(y)) for x, y in raw["occupied_cells"])
            candidate_by_signature[(template, MODE_MAP[str(raw["pose_params"]["port_mode"])], body)].append(raw)

    selected_keys = set()
    occupied: set[Cell] = set()
    selected_records = []
    template_counts = Counter()
    for index, raw in enumerate(result["selected"]):
        template = str(raw["template"])
        mode_id = str(raw["mode"])
        body = frozenset((origin[0] + int(x), origin[1] + int(y)) for x, y in raw["body"])
        matches = candidate_by_signature[(template, mode_id, body)]
        require(len(matches) == 1, f"candidate match {index}: {len(matches)}")
        candidate_pose = matches[0]
        anchor = (int(candidate_pose["anchor"]["x"]), int(candidate_pose["anchor"]["y"]))
        mode = modes[(template, mode_id)]
        require(body == rect(anchor, int(mode["body"]["width"]), int(mode["body"]["height"])), f"strict body {index}")
        strict_inputs, strict_outputs = strict_access(mode, anchor)
        candidate_inputs = tuple(sorted((int(row["x"]), int(row["y"])) for row in candidate_pose["input_port_cells"]))
        candidate_outputs = tuple(sorted((int(row["x"]), int(row["y"])) for row in candidate_pose["output_port_cells"]))
        require((candidate_inputs, candidate_outputs) == (strict_inputs, strict_outputs), f"candidate/strict ports {index}")
        available_inputs = tuple(cell for cell in strict_inputs if cell not in fixed_body)
        available_outputs = tuple(cell for cell in strict_outputs if cell not in fixed_body)
        declared_inputs = tuple(sorted((origin[0] + int(x), origin[1] + int(y)) for x, y in raw["inputs"]))
        declared_outputs = tuple(sorted((origin[0] + int(x), origin[1] + int(y)) for x, y in raw["outputs"]))
        require((declared_inputs, declared_outputs) == (available_inputs, available_outputs), f"declared ports {index}")
        require(body <= c11 and not body & forbidden, f"placement {index}")
        require(not occupied & body, f"body overlap {index}")
        require(body & power, f"power {index}")
        occupied.update(body)
        template_counts[template] += 1
        local_body = tuple(sorted((x - origin[0], y - origin[1]) for x, y in body))
        local_inputs = tuple((x - origin[0], y - origin[1]) for x, y in available_inputs)
        local_outputs = tuple((x - origin[0], y - origin[1]) for x, y in available_outputs)
        key = (template, mode_id, local_body, local_inputs, local_outputs)
        require(key not in selected_keys, f"duplicate selected key {index}")
        selected_keys.add(key)
        selected_records.append((key, template, available_inputs, available_outputs))
    require(template_counts == Counter({"manufacturing_3x3": 9, "manufacturing_5x5": 1, "manufacturing_6x4": 2}), "template counts")
    free = c11 - occupied
    main_cells = reachable(gateways, free)
    require(len(free) == result["residual_cells"] == 58, "residual size")
    require(main_cells == free and len(main_cells) == result["residual_main_cells"], "residual connectivity")

    active_counts: Counter[tuple[Any, str]] = Counter()
    for index, active in enumerate(result["selected_weak_active"]):
        key = ast.literal_eval(str(active["pose_key"]))
        require(key in selected_keys, f"active pose key {index}")
        kind = str(active["kind"])
        local_cell = tuple(int(value) for value in active["cell"])
        global_cell = (origin[0] + local_cell[0], origin[1] + local_cell[1])
        record = next(row for row in selected_records if row[0] == key)
        declared = record[2] if kind == "input" else record[3]
        require(global_cell in declared, f"active declared {index}")
        require(global_cell not in occupied, f"active blocked {index}")
        require(global_cell in main_cells or global_cell in backbone, f"active disconnected {index}")
        active_counts[(key, kind)] += 1
    for key, template, inputs, outputs in selected_records:
        need_inputs, need_outputs = REQUIREMENTS[template]
        require(active_counts[(key, "input")] == need_inputs, f"active input count {template}")
        require(active_counts[(key, "output")] == need_outputs, f"active output count {template}")
        require(sum(cell not in occupied and (cell in main_cells or cell in backbone) for cell in inputs) >= need_inputs, f"connected inputs {template}")
        require(sum(cell not in occupied and (cell in main_cells or cell in backbone) for cell in outputs) >= need_outputs, f"connected outputs {template}")

    baseline_free = GRID - fixed_body - backbone - removed_protected
    for representative in ((2, 60), (49, 60)):
        baseline_component = component(representative, baseline_free)
        relocated_component = component(representative, GRID - fixed_body - backbone)
        require(baseline_component == relocated_component, f"tail component changed {representative}")
        baseline_gateways = {cell for cell in baseline_component if any(adjacent in backbone for adjacent in neighbours(cell))}
        relocated_gateways = {cell for cell in relocated_component if any(adjacent in backbone for adjacent in neighbours(cell))}
        require(baseline_gateways == relocated_gateways, f"tail gateways changed {representative}")

    record = {
        "schema_version": "c11_removed_protected_independent_replay.v1",
        "status": "INDEPENDENT_REPLAY_ACCEPTED",
        "classification": "research_pure_stdlib_local_geometry_replay_no_router",
        "claim_boundary": (
            "This accepts the local c11 packing only after removing the current protected rectangle. "
            "It does not choose or validate a global replacement rectangle and is not a global layout."
        ),
        "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        "checks": {
            "canonical_candidate_and_strict_pose_parity": True,
            "body_nonoverlap_and_placement": True,
            "declared_fronts_recomputed": True,
            "exact_weak_active_counts": True,
            "all_weak_active_fronts_backbone_connected": True,
            "all_selected_bodies_powered": True,
            "all_residual_cells_connected": True,
            "baseline_35_poles_unique_in_grid_and_nonoverlapping": True,
            "c15_c16_free_domain_and_gateway_geometry_unchanged": True,
        },
        "selected_count": len(result["selected"]),
        "selected_body_cells": len(occupied),
        "residual_cells": len(free),
        "residual_main_cells": len(main_cells),
        "weak_active_count": len(result["selected_weak_active"]),
    }
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
