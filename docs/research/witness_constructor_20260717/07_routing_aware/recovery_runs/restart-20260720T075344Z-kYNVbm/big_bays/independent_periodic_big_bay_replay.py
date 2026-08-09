#!/usr/bin/env python3
"""Pure-stdlib replay of one c0 packing translated across c0/c1/c2.

The replay simultaneously moves the three internal pole columns by +1, rebuilds
canonical pose domains from pinned inputs, compares normalized local-key sets,
and validates selected bodies, active fronts, power, and residual BFS.  It does
not import the search script, OR-Tools, a constructor, or a router.
"""

from __future__ import annotations

from collections import Counter, deque
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
HERE = RECOVERY / "big_bays"
SOURCE = HERE / "all_residual_attempts/c0/t10-5-4_x18_dyp0_s240.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
SELECTION = HERE / "periodic_big_bay_selection.json"
REPORT = HERE / "independent_periodic_big_bay_replay.json"
EXPECTED = {
    SOURCE: "b503237432847a59b2f9bf65359c2344269dc9addccaa28490030a582e6d8e92",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
GRID_SIZE = 70
GRID = {(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)}
VERTICAL_LANES = (1, 12, 24, 36, 48, 59)
HORIZONTAL_LANES = (1, 36, 59)
POLE_AXES = (5, 17, 29, 41, 53, 65)
MOVED_COLUMNS = {17: 18, 29: 30, 41: 42}
MOVED_ROWS = (5, 17, 29)
CORE_ANCHOR = (60, 60)
PROTECTED = (7, 36, 6, 7)
BAYS = {"c0": (13, 2), "c1": (25, 2), "c2": (37, 2)}
TEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")
REQUIREMENTS = {
    "manufacturing_3x3": (1, 1),
    "manufacturing_5x5": (1, 1),
    "manufacturing_6x4": (3, 1),
}
MODE_MAP = {
    "TB": "north_to_south",
    "BT": "south_to_north",
    "RL": "east_to_west",
    "LR": "west_to_east",
}
DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
Cell = tuple[int, int]


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    observed = sha256(path)
    require(observed == EXPECTED[path], f"hash drift for {path}: {observed}")
    return json.loads(path.read_bytes())


def cells(raw: Sequence[Sequence[int]]) -> set[Cell]:
    result = {(int(item[0]), int(item[1])) for item in raw}
    require(len(result) == len(raw), "duplicate cell")
    return result


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


def components(all_cells: set[Cell]) -> list[set[Cell]]:
    remaining = set(all_cells)
    result = []
    while remaining:
        part = reachable({min(remaining)}, remaining)
        result.append(part)
        remaining -= part
    return result


def boundary_anchors(gap: int) -> list[int]:
    return list(range(0, gap, 3)) + [gap + 1 + 3 * index for index in range(23 - gap // 3)]


def strict_mode_map(strict: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (str(template), str(mode["id"])): mode
        for template, record in strict["facility_templates"].items()
        for mode in record["modes"]
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
                "access": (
                    anchor[0] + int(body_cell["x"]) + dx,
                    anchor[1] + int(body_cell["y"]) + dy,
                ),
            }
        )
    return sorted(result, key=lambda row: row["id"])


def fixed_geometry(strict: Mapping[str, Any], *, combined: bool, single_column: int | None = None) -> dict[str, Any]:
    core = rect(CORE_ANCHOR, 9, 9)
    core_ring = rect((59, 59), 11, 11) - core
    backbone = (
        {(x, y) for x in VERTICAL_LANES for y in range(1, GRID_SIZE)}
        | {(x, y) for y in HORIZONTAL_LANES for x in range(1, GRID_SIZE)}
        | core_ring
    ) - core
    protected = rect((PROTECTED[0], PROTECTED[1]), PROTECTED[2], PROTECTED[3])
    baseline = {(x, y) for x in POLE_AXES for y in POLE_AXES} - {(65, 65)}
    if combined:
        require(single_column is None, "combined/single-column conflict")
        removed = {(x, y) for x in MOVED_COLUMNS for y in MOVED_ROWS}
        added = {(MOVED_COLUMNS[x], y) for x in MOVED_COLUMNS for y in MOVED_ROWS}
    else:
        require(single_column in MOVED_COLUMNS, "single moved column")
        removed = {(int(single_column), y) for y in MOVED_ROWS}
        added = {(MOVED_COLUMNS[int(single_column)], y) for y in MOVED_ROWS}
    poles = (baseline - removed) | added
    require(len(poles) == 35 and len(poles) >= 9, "35-pole/P>=9 sentinel")
    pole_cells = set().union(*(rect(anchor, 2, 2) for anchor in poles))
    left_anchors = boundary_anchors(69)
    bottom_anchors = boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left_anchors for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom_anchors for x in range(anchor, anchor + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(len(pole_cells) == 140 and pole_cells <= GRID, "pole bodies")
    require(not pole_cells & (core | boundary | backbone | protected), "pole/fixed collision")
    require(not fixed_body & (backbone | protected), "fixed separator collision")
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
    forbidden = fixed_body | backbone | protected
    free_parts = components(GRID - forbidden)
    bays = {}
    gateways = {}
    for bay_name, origin in BAYS.items():
        matches = [part for part in free_parts if origin in part]
        require(len(matches) == 1, f"{bay_name} component cardinality")
        part = matches[0]
        observed_origin = (min(x for x, _y in part), min(y for _x, y in part))
        require(observed_origin == origin, f"{bay_name} origin drift")
        bays[bay_name] = part
        gateways[bay_name] = {cell for cell in part if any(adjacent in backbone for adjacent in neighbours(cell))}
        require(gateways[bay_name], f"{bay_name} gateways")
    return {
        "backbone": backbone,
        "protected": protected,
        "poles": poles,
        "pole_cells": pole_cells,
        "fixed_body": fixed_body,
        "power": power,
        "forbidden": forbidden,
        "bays": bays,
        "gateways": gateways,
    }


def local_cells(raw: Sequence[Sequence[int]], origin: Cell) -> tuple[Cell, ...]:
    return tuple(sorted((int(cell[0]) - origin[0], int(cell[1]) - origin[1]) for cell in raw))


def domain(
    candidate: Mapping[str, Any],
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
    fixed: Mapping[str, Any],
    bay_name: str,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    origin = BAYS[bay_name]
    component = fixed["bays"][bay_name]
    result: dict[tuple[Any, ...], dict[str, Any]] = {}
    for template in TEMPLATES:
        for pose_index, raw in enumerate(candidate["facility_pools"][template]):
            body = cells(raw["occupied_cells"])
            if body & fixed["forbidden"] or not body <= component or not body & fixed["power"]:
                continue
            mode_id = MODE_MAP[str(raw["pose_params"]["port_mode"])]
            mode = modes[(template, mode_id)]
            anchor = (int(raw["anchor"]["x"]), int(raw["anchor"]["y"]))
            require(
                body == rect(anchor, int(mode["body"]["width"]), int(mode["body"]["height"])),
                "candidate/strict body parity",
            )
            ports = strict_ports(mode, anchor)
            candidate_inputs = {(int(port["x"]), int(port["y"])) for port in raw["input_port_cells"]}
            candidate_outputs = {(int(port["x"]), int(port["y"])) for port in raw["output_port_cells"]}
            require(
                candidate_inputs == {port["access"] for port in ports if port["kind"] == "input"},
                "candidate/strict input parity",
            )
            require(
                candidate_outputs == {port["access"] for port in ports if port["kind"] == "output"},
                "candidate/strict output parity",
            )
            available = [port for port in ports if port["access"] not in fixed["fixed_body"]]
            inputs = tuple(sorted(port["access"] for port in available if port["kind"] == "input"))
            outputs = tuple(sorted(port["access"] for port in available if port["kind"] == "output"))
            need_in, need_out = REQUIREMENTS[template]
            if len(inputs) < need_in or len(outputs) < need_out:
                continue
            require(
                all(
                    cell in component or cell in fixed["backbone"] or cell in fixed["protected"]
                    for cell in (*inputs, *outputs)
                ),
                "front locality",
            )
            key = (
                template,
                mode_id,
                tuple(sorted((x - origin[0], y - origin[1]) for x, y in body)),
                tuple(sorted((x - origin[0], y - origin[1]) for x, y in inputs)),
                tuple(sorted((x - origin[0], y - origin[1]) for x, y in outputs)),
            )
            require(key not in result, f"normalized domain key collision in {bay_name}")
            result[key] = {
                "template": template,
                "mode": mode_id,
                "pose_index": pose_index,
                "anchor": anchor,
                "body": body,
                "inputs": inputs,
                "outputs": outputs,
            }
    return result


def source_key(row: Mapping[str, Any], origin: Cell) -> tuple[Any, ...]:
    return (
        str(row["template"]),
        str(row["mode"]),
        local_cells(row["body"], origin),
        local_cells(row["inputs"], origin),
        local_cells(row["outputs"], origin),
    )


def materialize_bay(
    bay_name: str,
    source: Mapping[str, Any],
    fixed: Mapping[str, Any],
    domain_map: Mapping[tuple[Any, ...], Mapping[str, Any]],
) -> dict[str, Any]:
    source_origin = BAYS["c0"]
    origin = BAYS[bay_name]
    dx = origin[0] - source_origin[0]
    selected = []
    selected_internal = []
    for source_row in source["selected"]:
        key = source_key(source_row, source_origin)
        require(key in domain_map, f"source selected key absent in {bay_name}")
        pose = domain_map[key]
        if bay_name == "c0":
            require(int(source_row["pose_index"]) == int(pose["pose_index"]), "source pose index parity")
        selected_internal.append(pose)
        selected.append(
            {
                "template": pose["template"],
                "mode": pose["mode"],
                "pose_index": pose["pose_index"],
                "anchor": list(pose["anchor"]),
                "body": [list(cell) for cell in sorted(pose["body"])],
                "inputs": [list(cell) for cell in pose["inputs"]],
                "outputs": [list(cell) for cell in pose["outputs"]],
            }
        )
    occupied: set[Cell] = set()
    for pose in selected_internal:
        require(not occupied & pose["body"], f"{bay_name} selected body overlap")
        require(bool(pose["body"] & fixed["power"]), f"{bay_name} selected body unpowered")
        require(not pose["body"] & fixed["forbidden"], f"{bay_name} body/fixed collision")
        occupied |= pose["body"]
    component = fixed["bays"][bay_name]
    free = component - occupied
    main = reachable(fixed["gateways"][bay_name], free)
    require(main == free, f"{bay_name} residual pocket")
    outside_main = fixed["backbone"] | fixed["protected"]
    active = []
    chosen = Counter()
    for raw in source["selected_weak_active"]:
        selected_index = int(raw["selected_index"])
        require(0 <= selected_index < len(selected_internal), "active selected index")
        kind = str(raw["kind"])
        require(kind in {"input", "output"}, "active kind")
        source_cell = (int(raw["cell"][0]), int(raw["cell"][1]))
        cell = (source_cell[0] + dx, source_cell[1])
        available = selected_internal[selected_index][f"{kind}s"]
        require(cell in available, f"{bay_name} active candidate/front parity")
        require(cell not in occupied, f"{bay_name} active front occupied")
        require(cell in main or cell in outside_main, f"{bay_name} active front disconnected")
        active.append(
            {
                "selected_index": selected_index,
                "kind": kind,
                "port_index": available.index(cell),
                "cell": list(cell),
            }
        )
        chosen[(selected_index, kind)] += 1
    for index, pose in enumerate(selected_internal):
        need_in, need_out = REQUIREMENTS[str(pose["template"])]
        require(chosen[(index, "input")] == need_in, f"{bay_name} exact active input count")
        require(chosen[(index, "output")] == need_out, f"{bay_name} exact active output count")
    totals = tuple(Counter(pose["template"] for pose in selected_internal)[template] for template in TEMPLATES)
    require(totals == (10, 5, 4), f"{bay_name} template totals")
    return {
        "origin": list(origin),
        "translation_from_c0": [dx, 0],
        "target": list(totals),
        "component_cells": len(component),
        "gateway_cells": len(fixed["gateways"][bay_name]),
        "selected_facilities": len(selected),
        "selected_body_cells": len(occupied),
        "residual_cells": len(free),
        "residual_reachable_cells": len(main),
        "all_residual_connected": True,
        "selected_weak_active_count": len(active),
        "selected_weak_active": active,
        "selected": selected,
    }


def write_or_match(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        require(path.read_text(encoding="utf-8") == encoded, f"existing output content drift: {path}")
        return
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)


def main() -> int:
    source = load(SOURCE)
    candidate = load(CANDIDATE)
    strict = load(STRICT)
    require(isinstance(source, dict) and isinstance(candidate, dict) and isinstance(strict, dict), "root maps")
    require(source["schema_version"] == "big_bay_all_residual_checkpoint.v1", "source schema")
    require(source["status"] in {"OPTIMAL", "FEASIBLE"}, "source status")
    require(source["bay"] == "c0" and tuple(source["target"]) == (10, 5, 4), "source query")
    require(int(source["moved_x"]) == 18 and int(source["uniform_y_shift"]) == 0, "source phase")
    require(bool(source["all_residual_connected"]), "source residual flag")
    modes = strict_mode_map(strict)

    standalone_c0 = fixed_geometry(strict, combined=False, single_column=17)
    combined = fixed_geometry(strict, combined=True)
    standalone_domain = domain(candidate, modes, standalone_c0, "c0")
    domains = {bay_name: domain(candidate, modes, combined, bay_name) for bay_name in BAYS}
    standalone_keys = set(standalone_domain)
    require(standalone_keys == set(domains["c0"]), "combined pole move changed c0 domain")
    require(all(set(domain_map) == standalone_keys for domain_map in domains.values()), "periodic local-key sets differ")
    require(len(standalone_keys) == 1858, "pinned normalized domain cardinality")

    bays = {
        bay_name: materialize_bay(bay_name, source, combined, domains[bay_name])
        for bay_name in BAYS
    }
    all_bodies: set[Cell] = set()
    all_fronts: set[Cell] = set()
    for bay_name, record in bays.items():
        body = set().union(*(cells(row["body"]) for row in record["selected"]))
        require(not all_bodies & body, f"cross-bay body overlap at {bay_name}")
        all_bodies |= body
        for terminal in record["selected_weak_active"]:
            all_fronts.add((int(terminal["cell"][0]), int(terminal["cell"][1])))
    require(not all_bodies & combined["fixed_body"], "selected/fixed-body collision")
    require(not all_fronts & all_bodies, "global selected active front occupied")
    observed_poles = combined["poles"]
    expected_poles = (
        ({(x, y) for x in POLE_AXES for y in POLE_AXES} - {(65, 65)})
        - {(x, y) for x in MOVED_COLUMNS for y in MOVED_ROWS}
    ) | {(new_x, y) for new_x in MOVED_COLUMNS.values() for y in MOVED_ROWS}
    require(observed_poles == expected_poles, "combined 35-pole set")

    aggregate = tuple(sum(record["target"][index] for record in bays.values()) for index in range(3))
    require(aggregate == (30, 15, 12), "aggregate template totals")
    selection = {
        "schema_version": "periodic_big_bay_selection.v1",
        "status": "THREE_PERIODIC_BIG_BAYS_REPLAYED",
        "classification": "research_local_selection_no_router",
        "claim_boundary": "Only c0/c1/c2 local selections and combined poles; no global layout or commodity-routing conclusion.",
        "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        "combined_moved_columns": {str(old): new for old, new in MOVED_COLUMNS.items()},
        "all_35_pole_anchors": [list(anchor) for anchor in sorted(observed_poles)],
        "pole_count": len(observed_poles),
        "normalized_local_domain_keys_per_bay": len(standalone_keys),
        "aggregate_target": list(aggregate),
        "aggregate_selected_facilities": sum(record["selected_facilities"] for record in bays.values()),
        "aggregate_selected_body_cells": len(all_bodies),
        "aggregate_selected_weak_active": sum(record["selected_weak_active_count"] for record in bays.values()),
        "bays": bays,
    }
    write_or_match(SELECTION, selection)
    report = {
        "schema_version": "independent_periodic_big_bay_replay.v1",
        "status": "PASS",
        "classification": "research_pure_stdlib_independent_local_replay_no_solver_no_router",
        "claim_boundary": (
            "Pure-stdlib replay of three local periodic bays and their combined 35-pole geometry only; "
            "no global layout or commodity-routing conclusion."
        ),
        "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        "selection_sha256": sha256(SELECTION),
        "checks": {
            "canonical_candidate_pose_parity": True,
            "strict_template_mode_and_port_parity": True,
            "standalone_to_combined_c0_domain_equal": True,
            "three_normalized_local_key_sets_equal": True,
            "combined_35_poles_unique_collision_free_and_p_ge_9": True,
            "exact_per_bay_target_10_5_4": True,
            "exact_aggregate_target_30_15_12": True,
            "all_selected_bodies_nonoverlapping_and_powered": True,
            "all_selected_active_front_counts_exact_clear_and_connected": True,
            "all_three_residual_cell_sets_fully_backbone_connected": True,
        },
        "counts": {
            "pole_count": len(observed_poles),
            "normalized_local_domain_keys_per_bay": len(standalone_keys),
            "selected_facilities": selection["aggregate_selected_facilities"],
            "selected_body_cells": len(all_bodies),
            "selected_weak_active": selection["aggregate_selected_weak_active"],
            "residual_cells": sum(record["residual_cells"] for record in bays.values()),
        },
    }
    require(all(report["checks"].values()), "replay checks")
    write_or_match(REPORT, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
