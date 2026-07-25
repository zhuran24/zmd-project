#!/usr/bin/env python3
"""Rebuild strict counts for the R4 upper candidate without project imports."""

from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import sys

EXPECTED_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"


# fmt: off
def require(ok, message):
    if not ok:
        raise ValueError(message)


def one(values, message):
    require(len(values) == 1, message)
    return values.pop()


def area(template):
    return one({m["body"]["width"] * m["body"]["height"] for m in template["modes"]}, "body area changes")


def side(mode, port):
    body = mode["body"]
    return body["width"] if port["direction"] in "NS" else body["height"]


def corner(mode, port):
    body, cell = mode["body"], port["body_cell"]
    return cell["x"] in {0, body["width"] - 1} and cell["y"] in {0, body["height"] - 1}


def main():
    require(len(sys.argv) == 2, "usage: independent_r4_upper_counts_v1.py INSTANCE")
    path = pathlib.Path(sys.argv[1])
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == EXPECTED_SHA256, "strict instance SHA-256 mismatch")
    data = json.loads(raw)
    templates, groups, required = data["facility_templates"], data["operation_groups"], data["required_instances"]
    width, height = data["grid"]["width"], data["grid"]["height"]
    require((width, height, data["objective"]["minimum_side"]) == (70, 70, 6), "grid/objective drift")
    body_cells = sum(area(templates[item["template"]]) for item in required)
    powered_cells = sum(area(templates[item["template"]]) for item in required
                        if templates[item["template"]]["requires_power"])
    manufacturing = sum(group["count"] for group in groups)
    mfg_inputs = sum(group["count"] * sum(group["port_needs"]["inputs"].values()) for group in groups)
    mfg_outputs = sum(group["count"] * sum(group["port_needs"]["outputs"].values()) for group in groups)
    generic = data["generic_requirements"]
    raw_demand = sum(generic["raw_outputs"].values())
    final_inputs = sum(generic["final_inputs"].values())
    classes, marked_classes = collections.Counter(), collections.Counter()
    mfg_marks = 0
    for group in groups:
        template = templates[group["template"]]
        needs = {kind: sum(group["port_needs"][kind].values()) for kind in ("inputs", "outputs")}
        length = one({side(mode, port) for mode in template["modes"] for port in mode["ports"]},
                     "manufacturing side length changes")
        classes[length, max(needs.values())] += group["count"]
        for plural, kind in (("inputs", "input"), ("outputs", "output")):
            corner_counts = {sum(corner(mode, port) for port in mode["ports"] if port["kind"] == kind)
                             for mode in template["modes"]}
            require(corner_counts == {2}, "manufacturing corner count drift")
            marked_classes[length, max(0, needs[plural] - 2)] += group["count"]
        mode_marks = []
        for mode in template["modes"]:
            marks = 0
            for plural, kind in (("inputs", "input"), ("outputs", "output")):
                ports = [port for port in mode["ports"] if port["kind"] == kind]
                require(len(ports) >= needs[plural], "insufficient manufacturing ports")
                marks += max(0, needs[plural] - sum(corner(mode, port) for port in ports))
            mode_marks.append(marks)
        mfg_marks += group["count"] * one(set(mode_marks), "manufacturing marks change by mode")
    provider_slots, raw_noncorner = {}, 0
    for provider in generic["raw_output_providers"]:
        template = templates[provider]
        count = sum(item["template"] == provider for item in required)
        slots = one({sum(port["kind"] == "output" for port in mode["ports"])
                     for mode in template["modes"]}, "provider slots change")
        require(all(not corner(mode, port) for mode in template["modes"] for port in mode["ports"]
                    if port["kind"] == "output"), "raw output at corner")
        provider_slots[provider] = count * slots
        raw_noncorner += count * slots
    boundary_count = sum(item["template"] == "boundary_storage_port" for item in required)
    boundary = templates["boundary_storage_port"]
    boundary_side = one({side(mode, port) for mode in boundary["modes"] for port in mode["ports"]},
                        "boundary side changes")
    classes[boundary_side, 1] += boundary_count
    marked_classes[boundary_side, 1] += boundary_count
    expected_classes = {(3, 1): 155, (3, 2): 12, (3, 3): 11, (5, 1): 32,
                        (5, 2): 17, (6, 3): 32, (6, 4): 3, (6, 5): 3}
    require(dict(classes) == expected_classes, "side-class table drift")
    excess = sum(count * max(0, 2 * active - length)
                 for (length, active), count in classes.items())
    endpoint_extra = max(active - max(0, 2 * active - length) for length, active in classes)
    endpoint_contacts = 2 * len("NESW")
    endpoint_allowance = endpoint_contacts * endpoint_extra
    total_excess = excess + endpoint_allowance
    membrane_floor_constant = total_excess // 2
    core = templates["protocol_core"]
    core_face = max(sum(port["kind"] == "output" and port["direction"] == direction
                        for port in mode["ports"])
                    for mode in core["modes"] for direction in "NESW")
    marked_classes[9, core_face] += 2
    terminals = mfg_inputs + mfg_outputs + raw_demand + final_inputs
    marks = mfg_marks + raw_noncorner
    inside_addend = core_face + final_inputs
    k_in_offset = membrane_floor_constant + inside_addend
    outside_numerator = terminals - k_in_offset
    lam = {(3, 3): 2, (5, 1): 8, (5, 5): 16, (7, 7): 8, (9, 3): 2, (9, 9): 2,
           (11, 1): 2, (11, 3): 12, (11, 5): 22, (11, 7): 2, (11, 9): 2,
           (13, 11): 25, (15, 3): 2, (17, 3): 8}

    def weight(x, y):
        return lam.get(tuple(sorted((abs(2 * x - 1), abs(2 * y - 1)), reverse=True)), 0)

    weight_total = sum(weight(x, y) for x in range(-20, 21) for y in range(-20, 21))
    pole_body = {(0, 0), (0, 1), (1, 0), (1, 1)}
    coverage = data["power"]["coverage_from_pole_anchor"]
    dimensions = {(mode["body"]["width"], mode["body"]["height"]) for item in required
                  if templates[item["template"]]["requires_power"]
                  for mode in templates[item["template"]]["modes"]}
    eligible = {}
    for body_width, body_height in dimensions:
        count = 0
        for anchor_x in range(coverage["x_min_offset"] - body_width + 1, coverage["x_max_offset"] + 1):
            for anchor_y in range(coverage["y_min_offset"] - body_height + 1, coverage["y_max_offset"] + 1):
                cells = {(anchor_x + x, anchor_y + y) for x in range(body_width) for y in range(body_height)}
                if cells & pole_body:
                    continue
                count += 1
                require(sum(weight(x, y) for x, y in cells) >= 2 * len(cells), "halo inequality failed")
        eligible[f"{body_width}x{body_height}"] = count
    pole_template = templates[data["power"]["pole_template"]]
    pole_capacity = weight_total // 2
    minimum_poles = -(-powered_cells // pole_capacity)
    base = body_cells + minimum_poles * area(pole_template)
    actual = (len(required), manufacturing, body_cells, powered_cells, mfg_inputs, mfg_outputs,
              raw_demand, final_inputs, terminals, mfg_marks, raw_noncorner, marks)
    require(actual == (266, 219, 3544, 3325, 310, 264, 52, 2, 628, 58, 52, 110),
            "strict count sentinels drift")
    membrane = (excess, endpoint_contacts, endpoint_extra, endpoint_allowance, total_excess,
                membrane_floor_constant, core_face, inside_addend, k_in_offset, outside_numerator)
    require(membrane == (63, 8, 3, 24, 87, 43, 3, 5, 48, 580), "membrane constants drift")
    require(provider_slots == {"boundary_storage_port": 46, "protocol_core": 6}, "provider slots drift")
    require(weight_total == 792 and sum(eligible.values()) == 840, "halo totals drift")
    require(minimum_poles == 9 and base == 3580, "body budget drift")
    result = {
        "schema": "r4_independent_checker_output_v1", "checker_id": "upper_counts", "status": "PASS",
        "results": {
            "strict_identity": {"path": str(path.resolve()), "sha256": digest,
                                "grid": [width, height], "minimum_objective_side": 6},
            "body_power_halo": {"required_instances": len(required), "manufacturing_instances": manufacturing,
                                "required_body_cells": body_cells, "powered_body_cells": powered_cells,
                                "doubled_weight_total": weight_total, "eligible_placements": eligible,
                                "eligible_placement_total": sum(eligible.values()), "pole_capacity": pole_capacity,
                                "minimum_poles": minimum_poles, "pole_body_cells": area(pole_template),
                                "base_body_cells": base, "remaining_cells": width * height - base},
            "active_terminal_accounting": {"manufacturing_inputs": mfg_inputs,
                                           "manufacturing_outputs": mfg_outputs, "raw_outputs": raw_demand,
                                           "final_inputs": final_inputs, "total": terminals},
            "manufacturing_marks": {"total": mfg_marks},
            "raw_output_slots": {"demand": raw_demand, "providers": provider_slots,
                                 "noncorner_slots": raw_noncorner, "total_marks": marks},
            "marked_side_classes": [{"side": side_value, "marks": marked, "count": count}
                                    for (side_value, marked), count in sorted(marked_classes.items())],
            "ordinary_membrane": {"side_classes": [{"side": side_value, "active": active, "count": count}
                                                    for (side_value, active), count in sorted(classes.items())],
                                  "full_contact_excess": excess, "endpoint_increment": endpoint_extra,
                                  "maximum_endpoint_contacts": endpoint_contacts,
                                  "endpoint_allowance": endpoint_allowance,
                                  "total_doubled_excess": total_excess,
                                  "manufacturing_boundary_offset": membrane_floor_constant,
                                  "core_output_face": core_face, "final_input_addend": final_inputs,
                                  "inside_addend": inside_addend, "k_in_offset": k_in_offset,
                                  "outside_numerator": outside_numerator},
        },
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
# fmt: on


if __name__ == "__main__":
    main()
