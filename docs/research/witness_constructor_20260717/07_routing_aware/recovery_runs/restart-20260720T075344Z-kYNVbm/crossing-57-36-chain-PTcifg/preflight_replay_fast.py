#!/usr/bin/env python3
"""Pure-stdlib c4 replay and c5 geometry-equivalence replay for anchor (57,36)."""

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
    "restart-20260720T075344Z-kYNVbm/crossing-57-36-chain-PTcifg"
)
RECOVERY = RUN.parent
C4 = RECOVERY / "fixed_bays/recovered_heavy_bays_20260720.json"
C5 = RECOVERY / "c5/c5_direct_winner_query.json"
C5_REPLAY = RECOVERY / "c5/independent_c5_direct_winner_replay_v2.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
OUTPUT = RUN / "preflight_replay_fast.json"
EXPECTED = {
    C4: "89772be8144f051b7e8d7b7b6cad518d82d75f9ce99d7f7f57f95b0660bba48a",
    C5: "3f1e2641e748bc7c6f2d5ad6aaf45adca3d4d15cb31d368439cc27480fb90c66",
    C5_REPLAY: "e062e5af4ad6063f099e7282cf2bf015212c16a3c7b998960bb364220642ef35",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
GRID = {(x, y) for x in range(70) for y in range(70)}
MODE_MAP = {"TB": "north_to_south", "BT": "south_to_north", "RL": "east_to_west", "LR": "west_to_east"}
DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
NEEDS = {"manufacturing_3x3": (1, 1), "manufacturing_5x5": (1, 1), "manufacturing_6x4": (3, 1)}
Cell = tuple[int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rect(anchor: Cell, width: int, height: int) -> set[Cell]:
    return {(x, y) for x in range(anchor[0], anchor[0] + width) for y in range(anchor[1], anchor[1] + height)}


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
    require(start in free, f"blocked representative {start}")
    return reachable({start}, free)


def boundary_anchors(gap: int) -> list[int]:
    return list(range(0, gap, 3)) + [gap + 1 + 3 * index for index in range(23 - gap // 3)]


def geometry(strict: Mapping[str, Any], poles: set[Cell], protected: set[Cell]) -> dict[str, set[Cell]]:
    core = rect((60, 60), 9, 9)
    ring = rect((59, 59), 11, 11) - core
    backbone = (
        {(x, y) for x in (1, 12, 24, 36, 48, 59) for y in range(1, 70)}
        | {(x, y) for y in (1, 36, 59) for x in range(1, 70)}
        | ring
    ) - core
    pole_cells = set().union(*(rect(anchor, 2, 2) for anchor in poles))
    left = boundary_anchors(69)
    bottom = boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom for x in range(anchor, anchor + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(len(poles) == 35 and len(pole_cells) == 140, "pole geometry")
    require(not protected & fixed_body, "protected/body collision")
    require(not fixed_body & backbone, "fixed/backbone collision")
    rule = strict["power"]["coverage_from_pole_anchor"]
    power = {
        (x, y)
        for anchor in poles
        for x in range(max(0, anchor[0] + int(rule["x_min_offset"])), min(69, anchor[0] + int(rule["x_max_offset"])) + 1)
        for y in range(max(0, anchor[1] + int(rule["y_min_offset"])), min(69, anchor[1] + int(rule["y_max_offset"])) + 1)
    }
    return {"fixed_body": fixed_body, "backbone": backbone, "protected": protected, "power": power}


def strict_modes(strict: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {(template, mode["id"]): mode for template, record in strict["facility_templates"].items() for mode in record["modes"]}


def strict_access(mode: Mapping[str, Any], anchor: Cell) -> tuple[tuple[Cell, ...], tuple[Cell, ...]]:
    by_kind: dict[str, list[Cell]] = defaultdict(list)
    for port in mode["ports"]:
        dx, dy = DELTA[port["direction"]]
        body = port["body_cell"]
        by_kind[port["kind"]].append((anchor[0] + int(body["x"]) + dx, anchor[1] + int(body["y"]) + dy))
    return tuple(sorted(by_kind["input"])), tuple(sorted(by_kind["output"]))


def replay_c4(c4: Mapping[str, Any], candidate: Mapping[str, Any], strict: Mapping[str, Any], geo: Mapping[str, set[Cell]]) -> dict[str, int]:
    row = c4["queries"][0]
    require(row["component"] == 4 and row["target"] == [10, 4, 4] and row["status"] == "OPTIMAL", "c4 source")
    origin = tuple(row["origin"])
    require(origin == (49, 2), "c4 origin")
    free_domain = GRID - geo["fixed_body"] - geo["backbone"] - geo["protected"]
    cells = component((49, 2), free_domain)
    gateways = {cell for cell in cells if any(adjacent in geo["backbone"] for adjacent in neighbours(cell))}
    modes = strict_modes(strict)
    lookup: dict[tuple[str, str, frozenset[Cell]], list[Mapping[str, Any]]] = defaultdict(list)
    for template in NEEDS:
        for raw in candidate["facility_pools"][template]:
            body = frozenset(tuple(cell) for cell in raw["occupied_cells"])
            lookup[(template, MODE_MAP[raw["pose_params"]["port_mode"]], body)].append(raw)
    occupied: set[Cell] = set()
    keys = {}
    counts = Counter()
    for selected in row["selected"]:
        template = selected["template"]
        mode_id = selected["mode"]
        body = frozenset((origin[0] + x, origin[1] + y) for x, y in selected["body"])
        matches = lookup[(template, mode_id, body)]
        require(len(matches) == 1, "c4 candidate match")
        raw = matches[0]
        anchor = (int(raw["anchor"]["x"]), int(raw["anchor"]["y"]))
        mode = modes[(template, mode_id)]
        require(body == rect(anchor, int(mode["body"]["width"]), int(mode["body"]["height"])), "c4 strict body")
        inputs, outputs = strict_access(mode, anchor)
        require(inputs == tuple(sorted((int(p["x"]), int(p["y"])) for p in raw["input_port_cells"])), "c4 candidate inputs")
        require(outputs == tuple(sorted((int(p["x"]), int(p["y"])) for p in raw["output_port_cells"])), "c4 candidate outputs")
        available_inputs = tuple(cell for cell in inputs if cell not in geo["fixed_body"])
        available_outputs = tuple(cell for cell in outputs if cell not in geo["fixed_body"])
        declared_inputs = tuple(sorted((origin[0] + x, origin[1] + y) for x, y in selected["inputs"]))
        declared_outputs = tuple(sorted((origin[0] + x, origin[1] + y) for x, y in selected["outputs"]))
        require((available_inputs, available_outputs) == (declared_inputs, declared_outputs), "c4 declared ports")
        require(body <= cells and not body & occupied and body & geo["power"], "c4 body legality")
        occupied.update(body)
        local_key = (
            template,
            mode_id,
            tuple(sorted((x - origin[0], y - origin[1]) for x, y in body)),
            tuple((x - origin[0], y - origin[1]) for x, y in available_inputs),
            tuple((x - origin[0], y - origin[1]) for x, y in available_outputs),
        )
        keys[local_key] = (template, available_inputs, available_outputs)
        counts[template] += 1
    require(counts == Counter({"manufacturing_3x3": 10, "manufacturing_5x5": 4, "manufacturing_6x4": 4}), "c4 counts")
    residual = cells - occupied
    main = reachable(gateways, residual)
    require(main == residual and len(main) == row["residual_main_cells"], "c4 residual BFS")
    active = Counter()
    for item in row["selected_weak_active"]:
        key = ast.literal_eval(item["pose_key"])
        require(key in keys, "c4 active key")
        kind = item["kind"]
        local = tuple(item["cell"])
        global_cell = (origin[0] + local[0], origin[1] + local[1])
        declared = keys[key][1 if kind == "input" else 2]
        require(global_cell in declared and global_cell not in occupied, "c4 active front")
        require(global_cell in main or global_cell in geo["backbone"] or global_cell in geo["protected"], "c4 active connectivity")
        active[(key, kind)] += 1
    for key, (template, _inputs, _outputs) in keys.items():
        need_in, need_out = NEEDS[template]
        require(active[(key, "input")] == need_in and active[(key, "output")] == need_out, "c4 active count")
    return {"selected": len(row["selected"]), "body_cells": len(occupied), "residual_cells": len(residual), "active": len(row["selected_weak_active"])}


def main() -> int:
    require(not OUTPUT.exists(), f"refusing overwrite: {OUTPUT}")
    for path, expected in EXPECTED.items():
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    c4 = json.loads(C4.read_bytes())
    c5 = json.loads(C5.read_bytes())
    c5_replay = json.loads(C5_REPLAY.read_bytes())
    candidate = json.loads(CANDIDATE.read_bytes())
    strict = json.loads(STRICT.read_bytes())
    require(c5_replay["status"] == "C5_POLE_PHASE_WINNER_INDEPENDENTLY_VERIFIED", "c5 replay source")
    baseline = {(x, y) for x in (5, 17, 29, 41, 53, 65) for y in (5, 17, 29, 41, 53, 65)} - {(65, 65)}
    moved_from = {(x, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
    final_poles = (baseline - moved_from) | {(x + 1, y) for x, y in moved_from}
    protected = rect((57, 36), 6, 7)
    geo = geometry(strict, final_poles, protected)
    require(len(protected) == 42 and len(protected & geo["backbone"]) == 12, "protected overlap")
    c4_result = replay_c4(c4, candidate, strict, geo)
    c5_selected = c5["query"]["selected"]
    c5_bodies = {tuple(cell) for row in c5_selected for cell in row["body"]}
    require(not c5_bodies & (protected | geo["fixed_body"] | geo["backbone"]), "c5 collision")
    c5_component = component((60, 2), GRID - geo["fixed_body"] - geo["backbone"] - protected)
    source_poles = {tuple(cell) for cell in c5["query"]["all_35_pole_anchors"]}
    source_geo = geometry(strict, source_poles, rect((7, 36), 6, 7))
    source_component = component((60, 2), GRID - source_geo["fixed_body"] - source_geo["backbone"] - source_geo["protected"])
    require(c5_component == source_component, "c5 component geometry changed")
    require((c5_component & geo["power"]) == (source_component & source_geo["power"]), "c5 power mask changed")
    record = {
        "schema_version": "crossing_57_36_c4_c5_preflight_replay.v1",
        "status": "C4_C5_PREFLIGHT_REPLAY_ACCEPTED",
        "classification": "research_pure_stdlib_geometry_and_local_witness_replay_no_solver_no_router",
        "claim_boundary": (
            "Accepts c4 directly and carries the already-independent c5 witness only through exact local geometry/power equivalence. "
            "c9/c10 and global assembly remain separate."
        ),
        "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        "protected_rect": {"anchor": [57, 36], "width": 6, "height": 7},
        "protected_cells": 42,
        "protected_backbone_overlap_cells": 12,
        "protected_new_body_forbidden_cells": 30,
        "pole_count": len(final_poles),
        "c4": c4_result,
        "c5": {"selected": len(c5_selected), "body_cells": len(c5_bodies), "local_component_geometry_equal": True, "local_power_mask_equal": True},
    }
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
