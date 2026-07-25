#!/usr/bin/env python3
"""Pure-stdlib classification of the rejected small-bay closure targets."""

from __future__ import annotations

from collections import deque
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
FIXED = RECOVERY / "fixed_bays"
STRONG = FIXED / "final35_small_bay_closure"
WEAK = FIXED / "final35_weak_closure_20260720.json"
C10_WEAK = FIXED / "c10_old_target_9_2_2_20260720.json"
C9_SOURCE = FIXED / "final_unchanged_bays_20260720.json"
OUTPUT = FIXED / "small_bay_closure_classification_20260720.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED = {
    WEAK: "6f352c51ced4076b919cb1163f7e2afc12a8d2e7bb527f766563ae195446ff08",
    C10_WEAK: "3985ef8bb129319c80aad4d07376129a2344b42040c495148b9213d1b8434a39",
    C9_SOURCE: "cd6c99ddb64b1c505a1d1865817d935b0436ddaf0d7df2e3f7001b97723cd64a",
    STRONG / "summary.json": "2c9446afcb9af555623af84f019333fd77521f75b35b7d297220b7d191a96e7f",
    STRONG / "c10_target_9_2_2.json": "2d3952551fa1834c9b29486827d3f0c2459c5bb8b4929e3e38412f63b37843ca",
    STRONG / "c11_target_9_1_2.json": "8acde8d7a10ebcf3440d8f2437c2738dcda8562a181efb97e437e2fb734d3acf",
    STRONG / "c12_target_5_1_1.json": "baa8725b7b835d3b6bce7f60331065c9e3006c64b38a064ccedf255910255568",
    STRONG / "c13_target_5_1_1.json": "4cb3283e69d7fab55dcffc865f4bdd0fd789a181170a126ce1dc2c575ba7d235",
    STRONG / "c14_target_5_1_1.json": "f319ddbdfa35cceda217e000ff1a73aeea1c370471385b7bbbcf8d6256622db7",
    STRONG / "c15_target_4_2_0.json": "5d6e860fe828543e4488fe0cc25790f7fd2f8e4edb3d5b6897db80a7e109447c",
    STRONG / "c16_target_4_2_0.json": "c2ff69655ae6a9777341f1d67b6dc689a193d3304d13e16d1bb7c285f346eb7c",
    STRONG / "c4_target_11_4_4.json": "b721259c956432e191991cf8eaa67ca8f50946b5194ad7763eb48a81926b2c66",
    FIXED / "run_final35_small_bay_closure.py": (
        "552c597899a7911566d4ae4d26dfa31355cb780664d1c3b0221383cdef511bf8"
    ),
    FIXED / "run_final35_weak_closure.py": (
        "e6a0c6861f36d54dabcad9bd8181c69b0c1a6ad86b2f47f0cfae963cd51716b8"
    ),
    FIXED / "run_c10_old_query_persistent.py": (
        "be6c2f9c8e558e980f8f7965181e8cbadc7fdb4e0493767276acf247ee816535"
    ),
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
Cell = tuple[int, int]
GRID_SIZE = 70
GRID = {(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)}
REPRESENTATIVES: Mapping[int, Cell] = {
    4: (49, 2),
    9: (49, 37),
    10: (60, 37),
    11: (2, 37),
    12: (13, 60),
    13: (25, 60),
    14: (37, 60),
    15: (2, 60),
    16: (49, 60),
}
WEAK_EXPECTED = (
    (11, (9, 1, 2)),
    (12, (5, 1, 1)),
    (13, (5, 1, 1)),
    (14, (5, 1, 1)),
    (15, (4, 2, 0)),
    (16, (4, 2, 0)),
    (4, (11, 4, 4)),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pinned(path: Path) -> Any:
    observed = sha256(path)
    require(observed == EXPECTED[path], f"hash drift for {path}: {observed}")
    return json.loads(path.read_bytes())


def rect(anchor: Cell, width: int, height: int) -> set[Cell]:
    return {
        (x, y)
        for x in range(anchor[0], anchor[0] + width)
        for y in range(anchor[1], anchor[1] + height)
    }


def ring(body: set[Cell]) -> set[Cell]:
    xs = [x for x, _y in body]
    ys = [y for _x, y in body]
    return rect(
        (min(xs) - 1, min(ys) - 1),
        max(xs) - min(xs) + 3,
        max(ys) - min(ys) + 3,
    ) - body


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


def component_for(start: Cell, free: set[Cell]) -> set[Cell]:
    require(start in free, f"representative is not free: {start}")
    return reachable({start}, free)


def boundary_anchors(gap: int) -> list[int]:
    return list(range(0, gap, 3)) + [gap + 1 + 3 * index for index in range(23 - gap // 3)]


def pole_sets() -> tuple[set[Cell], set[Cell]]:
    axes = (5, 17, 29, 41, 53, 65)
    baseline = {(x, y) for x in axes for y in axes} - {(65, 65)}
    moved_from = {(x, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
    moved_to = {(x + 1, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
    final = (baseline - moved_from) | moved_to
    require(len(baseline) == len(final) == 35, "pole count")
    return baseline, final


def geometry(poles: set[Cell], strict: Mapping[str, Any]) -> dict[str, set[Cell]]:
    core = rect((60, 60), 9, 9)
    backbone = (
        {(x, y) for x in (1, 12, 24, 36, 48, 59) for y in range(1, GRID_SIZE)}
        | {(x, y) for y in (1, 36, 59) for x in range(1, GRID_SIZE)}
        | ring(core)
    ) - core
    protected = rect((7, 36), 6, 7)
    left = boundary_anchors(69)
    bottom = boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom for x in range(anchor, anchor + 3)}
    )
    pole_cells = set().union(*(rect(anchor, 2, 2) for anchor in poles))
    fixed_body = core | pole_cells | boundary
    power_rule = strict["power"]["coverage_from_pole_anchor"]
    power = {
        (x, y)
        for anchor in poles
        for x in range(
            max(0, anchor[0] + int(power_rule["x_min_offset"])),
            min(GRID_SIZE - 1, anchor[0] + int(power_rule["x_max_offset"])) + 1,
        )
        for y in range(
            max(0, anchor[1] + int(power_rule["y_min_offset"])),
            min(GRID_SIZE - 1, anchor[1] + int(power_rule["y_max_offset"])) + 1,
        )
    }
    require(len(pole_cells) == 140, "pole bodies overlap")
    require(not fixed_body & backbone, "fixed body/backbone collision")
    require(not fixed_body & protected, "fixed body/protected collision")
    return {
        "backbone": backbone,
        "protected": protected,
        "fixed_body": fixed_body,
        "power": power,
        "free": GRID - fixed_body - backbone - protected,
    }


def localized(cells: set[Cell]) -> tuple[Cell, set[Cell]]:
    origin = (min(x for x, _y in cells), min(y for _x, y in cells))
    return origin, {(x - origin[0], y - origin[1]) for x, y in cells}


def main() -> int:
    require(not OUTPUT.exists(), f"refusing overwrite: {OUTPUT}")
    for path in EXPECTED:
        require(sha256(path) == EXPECTED[path], f"hash drift for {path}: {sha256(path)}")
    strict = load_pinned(STRICT)
    _candidate = load_pinned(CANDIDATE)
    weak = load_pinned(WEAK)
    c10_weak = load_pinned(C10_WEAK)
    c9_source = load_pinned(C9_SOURCE)
    strong_records = {
        component: load_pinned(STRONG / f"c{component}_target_{target[0]}_{target[1]}_{target[2]}.json")
        for component, target in ((10, (9, 2, 2)), *WEAK_EXPECTED)
    }
    require(len(weak["queries"]) == len(WEAK_EXPECTED), "weak query count")
    weak_rows = []
    for query_index, ((component, target), row) in enumerate(zip(WEAK_EXPECTED, weak["queries"], strict=True)):
        require(int(row["component"]) == component, f"weak component {query_index}")
        require(tuple(row["target"]) == target, f"weak target {query_index}")
        require(row["status"] == "INFEASIBLE", f"weak status {query_index}")
        weak_rows.append(
            {
                "query_index": query_index,
                "component": component,
                "target": list(target),
                "status": row["status"],
                "wall_time_seconds": row["wall_time_seconds"],
            }
        )
    c10_row = c10_weak["queries"][0]
    require(c10_row["component"] == 10 and c10_row["target"] == [9, 2, 2], "c10 weak identity")
    require(c10_row["status"] == "INFEASIBLE", "c10 weak status")
    for component, record in strong_records.items():
        require(record["requested_component"] == component, f"strong component {component}")
        require(record["status"] == "INFEASIBLE", f"strong status {component}")

    baseline_poles, final_poles = pole_sets()
    baseline = geometry(baseline_poles, strict)
    final = geometry(final_poles, strict)
    equivalence_rows = []
    local_components: dict[int, tuple[set[Cell], set[Cell]]] = {}
    for component in (4, 9, 10, 11, 12, 13, 14, 15, 16):
        representative = REPRESENTATIVES[component]
        base_component = component_for(representative, baseline["free"])
        final_component = component_for(representative, final["free"])
        base_origin, base_local = localized(base_component)
        final_origin, final_local = localized(final_component)
        base_gateways = {
            cell for cell in base_component if any(adjacent in baseline["backbone"] for adjacent in neighbours(cell))
        }
        final_gateways = {
            cell for cell in final_component if any(adjacent in final["backbone"] for adjacent in neighbours(cell))
        }
        require(base_origin == final_origin, f"origin changed c{component}")
        require(base_local == final_local, f"component cells changed c{component}")
        require(base_gateways == final_gateways, f"gateways changed c{component}")
        require(
            (base_component & baseline["power"]) == (final_component & final["power"]),
            f"power mask changed c{component}",
        )
        equivalence_rows.append(
            {
                "component": component,
                "origin": list(base_origin),
                "component_cells": len(base_component),
                "gateway_cells": len(base_gateways),
                "free_cells_equal": True,
                "gateway_cells_equal": True,
                "power_mask_equal": True,
            }
        )
        local_components[component] = (base_local, base_gateways)

    c9_local, c9_gateways_global = local_components[9]
    c10_local, c10_gateways_global = local_components[10]
    c9_origin = REPRESENTATIVES[9]
    c10_origin = REPRESENTATIVES[10]
    c9_gateways = {(x - c9_origin[0], y - c9_origin[1]) for x, y in c9_gateways_global}
    c10_gateways = {(x - c10_origin[0], y - c10_origin[1]) for x, y in c10_gateways_global}
    c9_query = c9_source["queries"][0]
    require(c9_query["component"] == 9 and c9_query["target"] == [9, 2, 2], "c9 source identity")
    translated_fronts = [
        tuple(cell)
        for row in c9_query["selected"]
        for kind in ("inputs", "outputs")
        for cell in row[kind]
    ]
    outside_grid = {
        cell
        for cell in translated_fronts
        if not (0 <= c10_origin[0] + cell[0] < GRID_SIZE and 0 <= c10_origin[1] + cell[1] < GRID_SIZE)
    }
    require(c9_local != c10_local, "unexpected c9/c10 cell isomorphism")
    require(c9_gateways != c10_gateways, "unexpected c9/c10 gateway isomorphism")
    require(len(outside_grid) == 12, f"translated out-of-grid fronts {len(outside_grid)}")

    record = {
        "schema_version": "small_bay_closure_classification.v1",
        "status": "SMALL_BAY_V2_CLOSURE_REJECTED_BY_WEAK_MODEL",
        "classification": "research_pure_stdlib_artifact_and_geometry_classification_no_router_no_solver",
        "claim_boundary": (
            "The listed targets only are exact INFEASIBLE results in the recovered weak active-terminal "
            "model; the all-residual results are a strictly stronger, narrower classification. The final "
            "pole shifts leave every listed bay's local free cells, backbone gateways, and power mask "
            "unchanged, so the weak classifications apply to the final 35-pole geometry. No other target, "
            "global count closure, assembly, or commodity-routing conclusion is made."
        ),
        "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        "final_pole_anchors": [list(cell) for cell in sorted(final_poles)],
        "final_pole_count": len(final_poles),
        "geometry_equivalence": equivalence_rows,
        "weak_active_terminal_results": [
            {
                "query_index": "separate_c10_file:0",
                "component": 10,
                "target": [9, 2, 2],
                "status": c10_row["status"],
                "wall_time_seconds": c10_row["wall_time_seconds"],
            },
            *weak_rows,
        ],
        "all_residual_results": [
            {
                "component": component,
                "target": strong_records[component]["target"],
                "status": strong_records[component]["status"],
                "wall_time_seconds": strong_records[component]["wall_time_seconds"],
            }
            for component in (10, 11, 12, 13, 14, 15, 16, 4)
        ],
        "c9_to_c10_translation_audit": {
            "same_local_free_cells": False,
            "local_free_cell_symmetric_difference": len(c9_local ^ c10_local),
            "same_local_gateway_cells": False,
            "local_gateway_symmetric_difference": len(c9_gateways ^ c10_gateways),
            "translated_selected_fronts_outside_grid": len(outside_grid),
            "direct_translation_is_strict_isomorphism": False,
        },
        "combinable_selected_rows": [],
    }
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
