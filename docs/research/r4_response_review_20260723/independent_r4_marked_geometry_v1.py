#!/usr/bin/env python3
"""Enumerate marked-terminal geometry and the R4 candidate's dimension scan."""

from __future__ import annotations

import hashlib
import itertools
import json
import pathlib
import sys

EXPECTED_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
STEPS = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}


# fmt: off
def require(ok, message):
    if not ok:
        raise ValueError(message)


def one(values, message):
    require(len(values) == 1, message)
    return values.pop()


def side(mode, port):
    body = mode["body"]
    return body["width"] if port["direction"] in "NS" else body["height"]


def area(template):
    return one({m["body"]["width"] * m["body"]["height"] for m in template["modes"]}, "body area changes")


def main():
    require(len(sys.argv) == 2, "usage: independent_r4_marked_geometry_v1.py INSTANCE")
    path = pathlib.Path(sys.argv[1])
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == EXPECTED_SHA256, "strict instance SHA-256 mismatch")
    data = json.loads(raw)
    templates, required = data["facility_templates"], data["required_instances"]
    width, height, minimum = data["grid"]["width"], data["grid"]["height"], data["objective"]["minimum_side"]
    require((width, height, minimum) == (70, 70, 6), "grid/objective drift")
    occurrences = []
    for template_name, template in templates.items():
        for mode in template["modes"]:
            body_width, body_height = mode["body"]["width"], mode["body"]["height"]
            keys = []
            for port in mode["ports"]:
                step_x, step_y = STEPS[port["direction"]]
                local_x, local_y = port["body_cell"]["x"], port["body_cell"]["y"]
                anchor_x, anchor_y = -step_x - local_x, -step_y - local_y
                cells = frozenset((anchor_x + x, anchor_y + y) for x in range(body_width) for y in range(body_height))
                noncorner = not (local_x in {0, body_width - 1} and local_y in {0, body_height - 1})
                occurrences.append((port["direction"], noncorner, cells))
                keys.append((local_x, local_y, port["direction"]))
            require(len(keys) == len(set(keys)), f"duplicate physical port key in {template_name}")
    by_direction = {direction: [item for item in occurrences if item[0] == direction] for direction in STEPS}
    local = {}
    for terminal_count in (3, 4):
        checked = nonoverlap = 0
        maximum_marks = -1
        for directions in itertools.combinations(STEPS, terminal_count):
            for choice in itertools.product(*(by_direction[direction] for direction in directions)):
                checked += 1
                bodies = [item[2] for item in choice]
                if any(bodies[left] & bodies[right] for left in range(terminal_count) for right in range(left)):
                    continue
                nonoverlap += 1
                marks = sum(item[1] for item in choice)
                maximum_marks = max(maximum_marks, marks)
                require(terminal_count + marks <= 4, "t(z)+m(z)<=4 counterexample")
        local[str(terminal_count)] = {"combinations_checked": checked, "nonoverlap_combinations": nonoverlap, "maximum_noncorner_marks": maximum_marks}
    patterns, mfg_marks, side_census = [], 0, 0
    for group in data["operation_groups"]:
        template = templates[group["template"]]
        for plural, kind in (("inputs", "input"), ("outputs", "output")):
            active = sum(group["port_needs"][plural].values())
            length = one({side(mode, port) for mode in template["modes"] for port in mode["ports"] if port["kind"] == kind}, "manufacturing side changes")
            marks = max(0, active - 2)
            patterns.append((length, marks))
            side_census += group["count"]
            mfg_marks += group["count"] * marks
    boundary_count = sum(item["template"] == "boundary_storage_port" for item in required)
    boundary = templates["boundary_storage_port"]
    boundary_side = one({side(mode, port) for mode in boundary["modes"] for port in mode["ports"]}, "boundary side changes")
    patterns.append((boundary_side, 1))
    side_census += boundary_count
    core_patterns, core_slots = set(), set()
    for mode in templates["protocol_core"]["modes"]:
        faces = {}
        for port in mode["ports"]:
            if port["kind"] == "output":
                faces.setdefault(port["direction"], []).append(port)
        require(sorted(map(len, faces.values())) == [3, 3], "core output split drift")
        core_slots.add(sum(map(len, faces.values())))
        core_patterns.update((side(mode, ports[0]), len(ports)) for ports in faces.values())
    require(core_patterns == {(9, 3)} and core_slots == {6}, "core output geometry drift")
    patterns.append((9, 3))
    side_census += 2
    raw_demand = sum(data["generic_requirements"]["raw_outputs"].values())
    raw_slots = boundary_count + one(core_slots, "core slots change")
    require((mfg_marks, raw_demand, raw_slots, side_census) == (58, 52, 52, 486), "mark census drift")
    require(all(2 * marks <= length for length, marks in patterns), "full-contact inequality")
    max_marks = max(marks for _, marks in patterns)
    max_side = max(length for length, marks in patterns if marks)
    require((max_marks, max_side) == (3, 9), "marked-side extrema drift")
    interval_checks = endpoint_checks = 0
    patterns = sorted(set(patterns))
    for edge in range(minimum, width + 1):
        partial = {0: [], edge - 1: []}
        for length, marks in patterns:
            for start in range(-length + 1, edge):
                overlap = [position for position in range(length) if 0 <= start + position < edge]
                full = len(overlap) == length
                for selected in itertools.combinations(range(length), marks):
                    exposed = sum(position in overlap for position in selected)
                    limit = len(overlap) if full else len(overlap) + max_marks
                    require(2 * exposed <= limit, "marked-contact inequality failed")
                    interval_checks += 1
                if not full and start < 0:
                    partial[0].append((start, start + length - 1))
                if not full and start + length > edge:
                    partial[edge - 1].append((start, start + length - 1))
        for endpoint, intervals in partial.items():
            for first, second in itertools.combinations(intervals, 2):
                require(first[0] <= endpoint <= first[1] and second[0] <= endpoint <= second[1], "endpoint overlap failed")
                endpoint_checks += 1
    require(boundary["placement_rule"] == "matching_map_boundary", "boundary rule drift")
    boundary_modes = {(mode["body"]["width"], mode["body"]["height"], mode["ports"][0]["direction"]) for mode in boundary["modes"]}
    require(boundary_modes == {(1, 3, "E"), (3, 1, "N")}, "boundary modes drift")
    anchors, chosen, next_free = list(range(width - 2)), [], 0
    for anchor in anchors:
        if anchor >= next_free:
            chosen.append(anchor)
            next_free = anchor + 3
    per_boundary = len(chosen)
    distributions = [left for left in range(boundary_count + 1) if left <= per_boundary and boundary_count - left <= per_boundary]
    require(per_boundary == 23 and distributions == [23], "boundary 23+23 drift")
    occupied = 3 * per_boundary
    body_cells = sum(area(templates[item["template"]]) for item in required)
    pole_cells = area(templates[data["power"]["pole_template"]])
    available = width * height - body_cells - 9 * pole_cells
    require((occupied, body_cells, pole_cells, available) == (69, 3544, 4, 1320), "body budget drift")
    def outside(short, long, marked):
        ordinary = -(-(580 - short - long) // 4)
        improved = -(-(678 - 2 * (short + long)) // 4)
        return max(ordinary, improved) if marked and short >= max_side else ordinary
    def scan(marked, boundary_rule):
        best, dimensions = (-1, -1), []
        for short in range(minimum, width + 1):
            for long in range(short, height + 1):
                if boundary_rule and long == height:
                    continue
                if short * long + outside(short, long, marked) > available:
                    continue
                objective = (short * long, short)
                if objective > best:
                    best, dimensions = objective, [[short, long]]
                elif objective == best:
                    dimensions.append([short, long])
        return best, dimensions
    old, old_dims = scan(False, False)
    marked, marked_dims = scan(True, False)
    final, final_dims = scan(True, True)
    require((old, old_dims) == ((1190, 34), [[34, 35]]), "old scan drift")
    require((marked, marked_dims) == ((1190, 17), [[17, 70]]), "marked scan drift")
    require((final, final_dims) == ((1188, 22), [[22, 54]]), "final scan drift")
    keys = {}
    for short, long in ((34, 35), (29, 41), (17, 70), (22, 54)):
        needed = outside(short, long, True)
        keys[f"{short}x{long}"] = {"objective": [short * long, short], "outside_cells": needed, "sum": short * long + needed, "full_span_rejected": long == height}
    better = [[short, long] for short in range(minimum, width + 1) for long in range(short, height + 1) if (short * long, short) > final and long < height and short * long + outside(short, long, True) <= available]
    require(not better, "lex-better dimension survived")
    result = {
        "schema": "r4_independent_checker_output_v1", "checker_id": "marked_geometry", "status": "PASS",
        "results": {
            "strict_identity": {"path": str(path.resolve()), "sha256": digest},
            "access_cell_enumeration": {"port_occurrences": len(occurrences), "enumeration": local, "inequality": "t_plus_m_le_4"},
            "marked_membrane": {"manufacturing_marks": mfg_marks, "raw_slots": raw_slots, "total_marks": mfg_marks + raw_slots, "maximum_marks_per_side": max_marks, "maximum_marked_side": max_side, "interval_checks": interval_checks, "endpoint_pair_checks": endpoint_checks, "maximum_partial_contacts": 8, "j_in_offset": 12},
            "boundary_packing": {"required_bodies": boundary_count, "anchors_per_side": len(anchors), "maximum_per_supported_boundary": per_boundary, "forced_distribution": [23, 23], "occupied_cells_per_boundary": occupied, "unoccupied_cells_per_boundary": width - occupied},
            "scan_key_cases": keys,
            "final_dimension_scan": {"old": {"objective": list(old), "dimensions": old_dims}, "marked_only": {"objective": list(marked), "dimensions": marked_dims}, "final": {"objective": list(final), "dimensions": final_dims}, "lex_better_survivors": better},
        },
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
# fmt: on


if __name__ == "__main__":
    main()
