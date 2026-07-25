#!/usr/bin/env python3
"""Pure-stdlib final-pole replay of the retained c4 and c5 local rows."""

from __future__ import annotations

import ast
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import stat
from typing import Any, Mapping


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = ROOT / (
    "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
RUN = RECOVERY / "crossing-57-36-chain-PTcifg"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
C5_SOURCE = RECOVERY / "c5/c5_direct_winner_query.json"
C5_REPLAY = RECOVERY / "c5/independent_c5_direct_winner_replay_v2.json"
C4_SOURCE = RECOVERY / "fixed_bays/recovered_heavy_bays_20260720.json"
OUTPUT = RUN / "independent_c4_c5_preflight.json"
SUMS = RUN / "SHA256SUMS.preflight"
EXPECTED = {
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    C5_SOURCE: "3f1e2641e748bc7c6f2d5ad6aaf45adca3d4d15cb31d368439cc27480fb90c66",
    C5_REPLAY: "e062e5af4ad6063f099e7282cf2bf015212c16a3c7b998960bb364220642ef35",
    C4_SOURCE: "89772be8144f051b7e8d7b7b6cad518d82d75f9ce99d7f7f57f95b0660bba48a",
}
GRID_SIZE = 70
GRID = {(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)}
VERTICAL_LANES = (1, 12, 24, 36, 48, 59)
HORIZONTAL_LANES = (1, 36, 59)
CORE_ANCHOR = (60, 60)
PROTECTED_ANCHOR = (57, 36)
PROTECTED_SIZE = (6, 7)
MODE_MAP = {
    "TB": "north_to_south",
    "BT": "south_to_north",
    "RL": "east_to_west",
    "LR": "west_to_east",
}
DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
TEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")
REQUIREMENTS = {
    "manufacturing_3x3": Counter({"input": 1, "output": 1}),
    "manufacturing_5x5": Counter({"input": 1, "output": 1}),
    "manufacturing_6x4": Counter({"input": 3, "output": 1}),
}
EXPECTED_TARGETS = {4: (10, 4, 4), 5: (12, 3, 3)}
EXPECTED_BODY_CELLS = {4: 286, 5: 255}
EXPECTED_RESIDUAL_CELLS = {4: 42, 5: 73}
EXPECTED_ACTIVE_INCIDENCES = {4: 44, 5: 42}
Cell = tuple[int, int]


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pinned(path: Path) -> Any:
    metadata = path.lstat()
    require(stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode), f"bad file type: {path}")
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
    return rect((min(xs) - 1, min(ys) - 1), max(xs) - min(xs) + 3, max(ys) - min(ys) + 3) - body


def boundary_anchors(gap: int) -> list[int]:
    return list(range(0, gap, 3)) + [gap + 1 + 3 * index for index in range(23 - gap // 3)]


def neighbours(cell: Cell) -> tuple[Cell, Cell, Cell, Cell]:
    x, y = cell
    return ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))


def reachable(starts: set[Cell], free: set[Cell]) -> set[Cell]:
    seen = set(starts) & free
    queue = deque(seen)
    while queue:
        current = queue.popleft()
        for adjacent in neighbours(current):
            if adjacent in free and adjacent not in seen:
                seen.add(adjacent)
                queue.append(adjacent)
    return seen


def components(cells: set[Cell]) -> list[set[Cell]]:
    remaining = set(cells)
    result = []
    while remaining:
        component = reachable({min(remaining)}, remaining)
        result.append(component)
        remaining -= component
    return result


def strict_modes(strict: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (str(template), str(mode["id"])): mode
        for template, template_record in strict["facility_templates"].items()
        for mode in template_record["modes"]
    }


def strict_ports(mode: Mapping[str, Any], anchor: Cell) -> list[dict[str, Any]]:
    result = []
    for port in mode["ports"]:
        direction = str(port["direction"])
        dx, dy = DELTA[direction]
        body_cell = port["body_cell"]
        result.append(
            {
                "id": str(port["id"]),
                "kind": str(port["kind"]),
                "direction": direction,
                "access": (
                    anchor[0] + int(body_cell["x"]) + dx,
                    anchor[1] + int(body_cell["y"]) + dy,
                ),
            }
        )
    return sorted(result, key=lambda row: row["id"])


def final_poles() -> set[Cell]:
    baseline = {
        (x, y)
        for x in (5, 17, 29, 41, 53, 65)
        for y in (5, 17, 29, 41, 53, 65)
    } - {(65, 65)}
    moved_from = {(x, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
    moved_to = {(x + 1, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
    result = (baseline - moved_from) | moved_to
    require(len(result) == 35, "final pole count")
    require(not result & moved_from and moved_to <= result, "final pole phase")
    return result


def candidate_index(candidate: Mapping[str, Any]) -> dict[tuple[str, str, Cell, tuple[Cell, ...]], Mapping[str, Any]]:
    result = {}
    for template in TEMPLATES:
        for raw in candidate["facility_pools"][template]:
            candidate_mode = str(raw["pose_params"]["port_mode"])
            mode = MODE_MAP[candidate_mode]
            anchor = (int(raw["anchor"]["x"]), int(raw["anchor"]["y"]))
            body = tuple(sorted((int(item[0]), int(item[1])) for item in raw["occupied_cells"]))
            key = (template, mode, anchor, body)
            require(key not in result, f"duplicate candidate key: {key[:3]}")
            result[key] = raw
    return result


def globalize_cells(raw: Any, origin: Cell) -> tuple[Cell, ...]:
    return tuple((origin[0] + int(item[0]), origin[1] + int(item[1])) for item in raw)


def local_pose_key(raw: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(raw["template"]),
        str(raw["mode"]),
        tuple(tuple(int(value) for value in item) for item in raw["body"]),
        tuple(tuple(int(value) for value in item) for item in raw["inputs"]),
        tuple(tuple(int(value) for value in item) for item in raw["outputs"]),
    )


def main() -> int:
    require(not OUTPUT.exists(), f"refusing overwrite: {OUTPUT}")
    require(not SUMS.exists(), f"refusing overwrite: {SUMS}")
    candidate = load_pinned(CANDIDATE)
    strict = load_pinned(STRICT)
    c5_source = load_pinned(C5_SOURCE)
    c5_replay = load_pinned(C5_REPLAY)
    c4_source = load_pinned(C4_SOURCE)

    require(c5_source["status"] == "C5_DIRECT_QUERY_FEASIBLE", "c5 wrapper status")
    c5 = c5_source["query"]
    require(c5["status"] == "FEASIBLE" and c5["target"] == [12, 3, 3], "c5 selected status/target")
    require(c5_replay["status"] == "C5_POLE_PHASE_WINNER_INDEPENDENTLY_VERIFIED", "c5 replay status")
    require(EXPECTED[C5_SOURCE] in c5_replay["input_sha256"].values(), "c5 replay source hash")
    replay_winner = c5_replay["winner"]
    require(
        replay_winner["all_residual_connected"] is True
        and replay_winner["all_weak_active_connected"] is True
        and replay_winner["body_overlap_count"] == 0,
        "c5 prior replay checks",
    )
    c4 = c4_source["queries"][0]
    require(
        c4["component"] == 4
        and c4["origin"] == [49, 2]
        and c4["target"] == [10, 4, 4]
        and c4["status"] == "OPTIMAL",
        "c4 selected status/identity",
    )

    core = rect(CORE_ANCHOR, 9, 9)
    backbone = (
        {(x, y) for x in VERTICAL_LANES for y in range(1, GRID_SIZE)}
        | {(x, y) for y in HORIZONTAL_LANES for x in range(1, GRID_SIZE)}
        | ring(core)
    ) - core
    protected = rect(PROTECTED_ANCHOR, *PROTECTED_SIZE)
    require(len(protected) == 42 and len(protected & backbone) == 12, "protected/backbone overlap")
    poles = final_poles()
    pole_cells = set().union(*(rect(anchor, 2, 2) for anchor in poles))
    left_anchors = boundary_anchors(69)
    bottom_anchors = boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left_anchors for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom_anchors for x in range(anchor, anchor + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(len(pole_cells) == 140, "pole body overlap")
    require(not fixed_body & (backbone | protected), "fixed body collision")
    body_domain = GRID - fixed_body - backbone - protected
    body_components = components(body_domain)
    bay_cells = {
        4: next(cells for cells in body_components if (49, 2) in cells),
        5: next(cells for cells in body_components if (60, 2) in cells),
    }
    require((min(x for x, _y in bay_cells[4]), min(y for _x, y in bay_cells[4])) == (49, 2), "c4 origin")
    require((min(x for x, _y in bay_cells[5]), min(y for _x, y in bay_cells[5])) == (60, 2), "c5 origin")

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
    modes = strict_modes(strict)
    candidates = candidate_index(candidate)
    origins = {4: (49, 2), 5: (60, 2)}
    selected_rows = {4: c4["selected"], 5: c5["selected"]}
    decoded: dict[int, list[dict[str, Any]]] = {4: [], 5: []}
    occupied_by_bay: dict[int, set[Cell]] = {4: set(), 5: set()}
    coverage_by_bay: dict[int, list[int]] = {4: [], 5: []}
    template_counts: dict[int, Counter[str]] = {4: Counter(), 5: Counter()}

    for bay in (4, 5):
        origin = origins[bay]
        for index, selected in enumerate(selected_rows[bay]):
            template = str(selected["template"])
            mode_id = str(selected["mode"])
            body = (
                {tuple(int(value) for value in item) for item in selected["body"]}
                if bay == 5
                else set(globalize_cells(selected["body"], origin))
            )
            anchor = (min(x for x, _y in body), min(y for _x, y in body))
            if bay == 5:
                require(selected["anchor"] == list(anchor), f"c5 anchor {index}")
            key = (template, mode_id, anchor, tuple(sorted(body)))
            require(key in candidates, f"candidate lookup c{bay} row {index}")
            raw = candidates[key]
            if bay == 5:
                require(int(selected["pose_index"]) == candidate["facility_pools"][template].index(raw), f"c5 pose index {index}")
            strict_mode = modes[(template, mode_id)]
            require(
                body == rect(anchor, int(strict_mode["body"]["width"]), int(strict_mode["body"]["height"])),
                f"strict body c{bay} row {index}",
            )
            require(body <= bay_cells[bay], f"body outside c{bay} row {index}")
            require(not occupied_by_bay[bay] & body, f"body overlap c{bay} row {index}")
            occupied_by_bay[bay].update(body)
            ports = strict_ports(strict_mode, anchor)
            candidate_inputs = {(int(port["x"]), int(port["y"])) for port in raw["input_port_cells"]}
            candidate_outputs = {(int(port["x"]), int(port["y"])) for port in raw["output_port_cells"]}
            require(candidate_inputs == {port["access"] for port in ports if port["kind"] == "input"}, f"candidate inputs c{bay} row {index}")
            require(candidate_outputs == {port["access"] for port in ports if port["kind"] == "output"}, f"candidate outputs c{bay} row {index}")
            available = [port for port in ports if port["access"] not in fixed_body]
            inputs = tuple(sorted(port["access"] for port in available if port["kind"] == "input"))
            outputs = tuple(sorted(port["access"] for port in available if port["kind"] == "output"))
            selected_inputs = (
                tuple(sorted(tuple(int(value) for value in item) for item in selected["inputs"]))
                if bay == 5
                else tuple(sorted(globalize_cells(selected["inputs"], origin)))
            )
            selected_outputs = (
                tuple(sorted(tuple(int(value) for value in item) for item in selected["outputs"]))
                if bay == 5
                else tuple(sorted(globalize_cells(selected["outputs"], origin)))
            )
            require(inputs == selected_inputs and outputs == selected_outputs, f"strict selected ports c{bay} row {index}")
            covered = len(body & power)
            require(covered >= 1, f"unpowered c{bay} row {index}")
            coverage_by_bay[bay].append(covered)
            template_counts[bay][template] += 1
            decoded[bay].append(
                {
                    "template": template,
                    "inputs": inputs,
                    "outputs": outputs,
                    "local_key": local_pose_key(selected) if bay == 4 else None,
                }
            )
        require(
            tuple(template_counts[bay][template] for template in TEMPLATES) == EXPECTED_TARGETS[bay],
            f"template target c{bay}",
        )
        require(len(occupied_by_bay[bay]) == EXPECTED_BODY_CELLS[bay], f"body count c{bay}")

    all_manufacturing_body = occupied_by_bay[4] | occupied_by_bay[5]
    require(len(all_manufacturing_body) == sum(EXPECTED_BODY_CELLS.values()), "cross-bay body overlap")
    require(not all_manufacturing_body & fixed_body, "manufacturing/fixed body collision")
    require(not all_manufacturing_body & protected, "manufacturing/protected collision")

    main_by_bay: dict[int, set[Cell]] = {}
    gateway_counts = {}
    for bay in (4, 5):
        gateways = {
            item
            for item in bay_cells[bay]
            if any(adjacent in backbone for adjacent in neighbours(item))
        }
        residual = bay_cells[bay] - occupied_by_bay[bay]
        main = reachable(gateways, residual)
        require(main == residual and len(residual) == EXPECTED_RESIDUAL_CELLS[bay], f"residual BFS c{bay}")
        main_by_bay[bay] = main
        gateway_counts[bay] = len(gateways)

    outside_main = backbone | protected
    active_counts: dict[int, dict[int, Counter[str]]] = {
        4: defaultdict(Counter),
        5: defaultdict(Counter),
    }
    active_cells: dict[int, list[Cell]] = {4: [], 5: []}
    c4_key_to_index = {row["local_key"]: index for index, row in enumerate(decoded[4])}
    require(len(c4_key_to_index) == len(decoded[4]), "c4 local key duplicate")
    for active_index, active in enumerate(c4["selected_weak_active"]):
        parsed_key = ast.literal_eval(str(active["pose_key"]))
        require(parsed_key in c4_key_to_index, f"c4 active pose key {active_index}")
        selected_index = c4_key_to_index[parsed_key]
        kind = str(active["kind"])
        require(kind in {"input", "output"}, f"c4 active kind {active_index}")
        local_cell = tuple(int(value) for value in active["cell"])
        global_cell = (origins[4][0] + local_cell[0], origins[4][1] + local_cell[1])
        require(global_cell in decoded[4][selected_index][f"{kind}s"], f"c4 active port {active_index}")
        require(global_cell not in all_manufacturing_body | fixed_body, f"c4 active blocked {active_index}")
        require(global_cell in main_by_bay[4] or global_cell in outside_main, f"c4 active disconnected {active_index}")
        active_counts[4][selected_index][kind] += 1
        active_cells[4].append(global_cell)

    for active_index, active in enumerate(c5["selected_weak_active"]):
        selected_index = int(active["selected_index"])
        kind = str(active["kind"])
        port_index = int(active["port_index"])
        require(0 <= selected_index < len(decoded[5]) and kind in {"input", "output"}, f"c5 active identity {active_index}")
        choices = decoded[5][selected_index][f"{kind}s"]
        require(0 <= port_index < len(choices), f"c5 active port index {active_index}")
        active_cell = choices[port_index]
        require(list(active_cell) == active["cell"], f"c5 active cell {active_index}")
        require(active_cell not in all_manufacturing_body | fixed_body, f"c5 active blocked {active_index}")
        require(active_cell in main_by_bay[5] or active_cell in outside_main, f"c5 active disconnected {active_index}")
        active_counts[5][selected_index][kind] += 1
        active_cells[5].append(active_cell)

    for bay in (4, 5):
        require(len(active_cells[bay]) == EXPECTED_ACTIVE_INCIDENCES[bay], f"active incidence count c{bay}")
        require(
            all(active_counts[bay][index] == REQUIREMENTS[row["template"]] for index, row in enumerate(decoded[bay])),
            f"active multiplicities c{bay}",
        )

    checks = {
        "input_hashes_exact": True,
        "c5_prior_independent_replay_passed_and_pinned": True,
        "final_35_poles_unique_and_requested_top_shifts_exact": True,
        "pole_bodies_unique_and_fixed_geometry_collision_free": True,
        "protected_rectangle_is_6x7_at_57_36": True,
        "protected_backbone_overlap_is_12": True,
        "c4_c5_candidate_pose_and_strict_body_parity": True,
        "c4_c5_candidate_and_strict_port_parity": True,
        "c4_c5_exact_template_and_body_counts": True,
        "c4_c5_bodies_nonoverlapping_and_protected_clear": True,
        "every_selected_facility_has_power_coverage": True,
        "c4_c5_residual_cells_fully_reachable_from_backbone_gateways": True,
        "c4_c5_weak_active_fronts_clear_connected_and_exact_multiplicity": True,
    }
    result = {
        "schema_version": "crossing_57_36_independent_c4_c5_preflight.v1",
        "status": "C4_C5_FINAL_GEOMETRY_PREFLIGHT_PASS",
        "classification": "research_pure_stdlib_independent_replay_no_solver_no_router",
        "claim_boundary": (
            "Independent c4/c5 geometry preflight only: exact pinned source replay under the final 35 poles "
            "and relocated protected rectangle. No c9/c10 result, global 266-placement assembly, commodity "
            "routing, or complete-layout conclusion."
        ),
        "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        "geometry": {
            "pole_count": len(poles),
            "pole_body_cells": len(pole_cells),
            "protected_anchor": list(PROTECTED_ANCHOR),
            "protected_width": PROTECTED_SIZE[0],
            "protected_height": PROTECTED_SIZE[1],
            "protected_cells": len(protected),
            "protected_backbone_overlap": len(protected & backbone),
            "protected_nonbackbone_cells": len(protected - backbone),
        },
        "bays": {
            str(bay): {
                "origin": list(origins[bay]),
                "target": list(EXPECTED_TARGETS[bay]),
                "selected_facilities": len(decoded[bay]),
                "selected_body_cells": len(occupied_by_bay[bay]),
                "power_coverage_min_body_cells": min(coverage_by_bay[bay]),
                "power_coverage_max_body_cells": max(coverage_by_bay[bay]),
                "component_cells": len(bay_cells[bay]),
                "gateway_cells": gateway_counts[bay],
                "residual_cells": len(main_by_bay[bay]),
                "residual_reachable_cells": len(main_by_bay[bay]),
                "weak_active_incidences": len(active_cells[bay]),
            }
            for bay in (4, 5)
        },
        "combined": {
            "selected_facilities": sum(len(decoded[bay]) for bay in (4, 5)),
            "selected_body_cells": len(all_manufacturing_body),
            "body_overlap_count": 0,
            "body_protected_overlap_count": len(all_manufacturing_body & protected),
            "weak_active_incidences": sum(len(active_cells[bay]) for bay in (4, 5)),
        },
        "checks": checks,
    }
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    checker_hash = sha256(Path(__file__))
    output_hash = sha256(OUTPUT)
    with SUMS.open("x", encoding="ascii", newline="\n") as handle:
        handle.write(f"{checker_hash}  {Path(__file__).name}\n")
        handle.write(f"{output_hash}  {OUTPUT.name}\n")
    print(json.dumps({"status": result["status"], "output": str(OUTPUT), "sha256": output_hash}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
