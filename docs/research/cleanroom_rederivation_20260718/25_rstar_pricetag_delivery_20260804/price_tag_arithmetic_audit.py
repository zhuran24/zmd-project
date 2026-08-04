#!/usr/bin/env python3
"""Reproduce arithmetic/enumeration counts used in the R-* price-tag report.

Inputs are transcribed only from 06_geometry_constants.md and
08_original_domain_baseline.md in the supplied research pack.  The script uses
only Python's standard library and does not solve the G1 master.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path
from typing import Iterable

GRID = 70
REGION = 14
REGIONS_PER_AXIS = 5
BASELINE_HASHES = {
    "rules/canonical_rules.json": "5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05",
    "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
}
BASELINE_POSES = {"M3": 17_952, "M5": 16_896, "M6": 16_900, "POLE": 4_761}
MANDATORY_COUNTS = {"M3": 132, "M5": 49, "M6": 38}


def cells(x: int, y: int, w: int, h: int) -> set[tuple[int, int]]:
    return {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}


def side_cells(x: int, y: int, w: int, h: int, side: str) -> set[tuple[int, int]]:
    if side == "N":
        return {(xx, y + h) for xx in range(x, x + w)}
    if side == "S":
        return {(xx, y - 1) for xx in range(x, x + w)}
    if side == "E":
        return {(x + w, yy) for yy in range(y, y + h)}
    if side == "W":
        return {(x - 1, yy) for yy in range(y, y + h)}
    raise ValueError(side)


def within_region(points: Iterable[tuple[int, int]], region: tuple[int, int]) -> bool:
    i, j = region
    return all(14 * i <= x <= 14 * i + 13 and 14 * j <= y <= 14 * j + 13 for x, y in points)


def build_fixed() -> tuple[set[tuple[int, int]], set[tuple[int, int]], set[tuple[int, int]], set[tuple[int, int]]]:
    fixed: set[tuple[int, int]] = set()
    boundary_fronts: set[tuple[int, int]] = set()
    for k in range(23):
        y = 1 + 3 * k
        fixed |= cells(0, y, 1, 3)
        boundary_fronts.add((1, 2 + 3 * k))
    for k in range(23):
        x = 1 + 3 * k
        fixed |= cells(x, 0, 3, 1)
        boundary_fronts.add((2 + 3 * k, 1))
    fixed |= cells(3, 59, 9, 9)
    core_inputs = {(2, 59 + idx) for idx in range(1, 8)} | {(12, 59 + idx) for idx in range(1, 8)}
    core_outputs = {(3 + idx, 68) for idx in (1, 4, 7)} | {(3 + idx, 58) for idx in (1, 4, 7)}
    return fixed, boundary_fronts, core_inputs, core_outputs


FIXED, BOUNDARY_FRONTS, CORE_INPUTS, CORE_OUTPUTS = build_fixed()
REQUIRED_OUTPUTS = BOUNDARY_FRONTS | CORE_OUTPUTS
ALL_FIXED_FRONTS = REQUIRED_OUTPUTS | CORE_INPUTS
PORTAL_LOCAL = {(13, 6), (13, 7), (0, 6), (0, 7), (6, 13), (7, 13), (6, 0), (7, 0)}
LIVE_STUBS_BY_REGION: dict[tuple[int, int], set[tuple[int, int]]] = {}
ALL_LIVE_STUBS: set[tuple[int, int]] = set()
for i, j in product(range(5), repeat=2):
    nominal = {(14 * i + x, 14 * j + y) for x, y in PORTAL_LOCAL}
    live = nominal - FIXED
    LIVE_STUBS_BY_REGION[(i, j)] = live
    ALL_LIVE_STUBS |= live
RIM_STUBS = {p for p in ALL_LIVE_STUBS if p[0] in (0, 69) or p[1] in (0, 69)}
INTERNAL_STUBS = ALL_LIVE_STUBS - RIM_STUBS


def mode_specs(template: str) -> list[tuple[str, int, int, str, str, int, int]]:
    if template in {"M3", "M5"}:
        d = 3 if template == "M3" else 5
        return [
            ("S_to_N", d, d, "S", "N", 1, 1),
            ("N_to_S", d, d, "N", "S", 1, 1),
            ("W_to_E", d, d, "W", "E", 1, 1),
            ("E_to_W", d, d, "E", "W", 1, 1),
        ]
    if template == "M6":
        return [
            ("6x4_S_to_N", 6, 4, "S", "N", 3, 1),
            ("6x4_N_to_S", 6, 4, "N", "S", 3, 1),
            ("4x6_W_to_E", 4, 6, "W", "E", 3, 1),
            ("4x6_E_to_W", 4, 6, "E", "W", 3, 1),
        ]
    raise ValueError(template)


def enumerate_single_machine_poses(template: str) -> list[dict[str, object]]:
    """Current local single-body domain before fixed-front/stub body masks.

    Premises: body and active fronts stay in one region; body avoids fixed
    furniture; the weakest actual class for the template has enough front cells
    when only fixed furniture is present.  No R-PAT-CONN test is applied here.
    """
    result: list[dict[str, object]] = []
    for i, j in product(range(5), repeat=2):
        ox, oy = 14 * i, 14 * j
        for mode, w, h, input_side, output_side, r_in, r_out in mode_specs(template):
            for x in range(ox, ox + 14 - w + 1):
                for y in range(oy, oy + 14 - h + 1):
                    body = cells(x, y, w, h)
                    in_front = side_cells(x, y, w, h, input_side)
                    out_front = side_cells(x, y, w, h, output_side)
                    if not within_region(in_front, (i, j)) or not within_region(out_front, (i, j)):
                        continue
                    if body & FIXED:
                        continue
                    if len(in_front - FIXED) < r_in or len(out_front - FIXED) < r_out:
                        continue
                    result.append({"region": (i, j), "mode": mode, "body": body})
    return result


def true_fixed_front_ok(body: set[tuple[int, int]]) -> bool:
    # All 52 outputs are consumed; at least two of the 14 core inputs must remain.
    return not (body & REQUIRED_OUTPUTS) and len(CORE_INPUTS - body) >= 2


def all_fixed_front_ok(body: set[tuple[int, int]]) -> bool:
    return not (body & ALL_FIXED_FRONTS)


def stub_ok(body: set[tuple[int, int]], region: tuple[int, int]) -> bool:
    return not (body & LIVE_STUBS_BY_REGION[region])


def body_and_front_pose_counts() -> dict[str, object]:
    # Exact template-level candidate-domain arithmetic from the frozen baseline.
    body_keep = {
        "M3": 25 * 12 * 12 * 4 - 4 * (5 * 12) * 2,
        "M5": 25 * 10 * 10 * 4 - 4 * (5 * 10) * 2,
        "M6": 25 * ((9 * 11 * 2) + (11 * 9 * 2)) - (2 * (5 * 9) * 2 + 2 * (5 * 9) * 2),
        "POLE": 25 * 13 * 13,
    }
    front_keep = {
        "M3": 25 * (12 * 10 * 2 + 10 * 12 * 2),
        "M5": 25 * (10 * 8 * 2 + 8 * 10 * 2),
        "M6": 25 * (9 * 9 * 2 + 9 * 9 * 2),
    }
    baseline_inc = sum(MANDATORY_COUNTS[t] * BASELINE_POSES[t] for t in MANDATORY_COUNTS)
    body_inc = sum(MANDATORY_COUNTS[t] * body_keep[t] for t in MANDATORY_COUNTS)
    front_inc = sum(MANDATORY_COUNTS[t] * front_keep[t] for t in MANDATORY_COUNTS)
    return {
        "per_template": {
            t: {
                "baseline": BASELINE_POSES[t],
                "body_in_region_keep": body_keep[t],
                "body_in_region_removed": BASELINE_POSES[t] - body_keep[t],
                **(
                    {
                        "front_in_region_keep": front_keep[t],
                        "front_increment_removed": body_keep[t] - front_keep[t],
                    }
                    if t in front_keep
                    else {}
                ),
            }
            for t in body_keep
        },
        "mandatory_instance_pose_incidences": {
            "baseline": baseline_inc,
            "after_body_in_region": body_inc,
            "body_removed": baseline_inc - body_inc,
            "body_removed_ratio": (baseline_inc - body_inc) / baseline_inc,
            "after_front_in_region": front_inc,
            "front_increment_removed": body_inc - front_inc,
            "front_increment_removed_ratio": (body_inc - front_inc) / body_inc,
            "body_plus_front_removed": baseline_inc - front_inc,
            "body_plus_front_removed_ratio": (baseline_inc - front_inc) / baseline_inc,
        },
    }


def portal_and_core_mask_counts() -> dict[str, object]:
    machine = {}
    pre_weighted = post_weighted = rim_recovered_weighted = 0
    for template in ("M3", "M5", "M6"):
        poses = enumerate_single_machine_poses(template)
        eligible = [p for p in poses if true_fixed_front_ok(p["body"]) and all_fixed_front_ok(p["body"])]
        post = [p for p in eligible if stub_ok(p["body"], p["region"])]
        rim_recovered = [
            p
            for p in eligible
            if not (p["body"] & INTERNAL_STUBS) and bool(p["body"] & RIM_STUBS)
        ]
        machine[template] = {
            "before_stubs": len(eligible),
            "after_stubs": len(post),
            "removed_by_stubs": len(eligible) - len(post),
            "recovered_if_only_rim_stubs_removed": len(rim_recovered),
        }
        n = MANDATORY_COUNTS[template]
        pre_weighted += n * len(eligible)
        post_weighted += n * len(post)
        rim_recovered_weighted += n * len(rim_recovered)

    poles = []
    for i, j in product(range(5), repeat=2):
        for x in range(14 * i, 14 * i + 13):
            for y in range(14 * j, 14 * j + 13):
                body = cells(x, y, 2, 2)
                if body & FIXED:
                    continue
                poles.append({"region": (i, j), "anchor": (x, y), "body": body})
    pole_eligible = [p for p in poles if true_fixed_front_ok(p["body"]) and all_fixed_front_ok(p["body"])]
    pole_post = [p for p in pole_eligible if stub_ok(p["body"], p["region"])]
    pole_rim_recovered = [
        p
        for p in pole_eligible
        if not (p["body"] & INTERNAL_STUBS) and bool(p["body"] & RIM_STUBS)
    ]

    core_poles = [p for p in poles if p["region"] == (0, 4)]
    core_true_and_stubs = [p for p in core_poles if true_fixed_front_ok(p["body"]) and stub_ok(p["body"], p["region"])]
    core_all_and_stubs = [p for p in core_true_and_stubs if all_fixed_front_ok(p["body"])]
    recovered_core_pole_anchors = sorted(
        p["anchor"] for p in core_true_and_stubs if not all_fixed_front_ok(p["body"])
    )
    core_machine_counts = {}
    for template in ("M3", "M5", "M6"):
        core = [p for p in enumerate_single_machine_poses(template) if p["region"] == (0, 4)]
        true_count = sum(true_fixed_front_ok(p["body"]) and stub_ok(p["body"], p["region"]) for p in core)
        all_count = sum(
            true_fixed_front_ok(p["body"])
            and all_fixed_front_ok(p["body"])
            and stub_ok(p["body"], p["region"])
            for p in core
        )
        core_machine_counts[template] = {"exact_54_front_semantics": true_count, "reserve_all_66": all_count}

    return {
        "live_stubs": {
            "nominal": 25 * 8,
            "swallowed_by_fixed_body": 20,
            "live": len(ALL_LIVE_STUBS),
            "internal": len(INTERNAL_STUBS),
            "board_rim": len(RIM_STUBS),
        },
        "manufacturing_single_pose_domain": {
            "per_template": machine,
            "weighted_before_stubs": pre_weighted,
            "weighted_after_stubs": post_weighted,
            "weighted_removed": pre_weighted - post_weighted,
            "weighted_removed_ratio": (pre_weighted - post_weighted) / pre_weighted,
            "weighted_recovered_if_only_rim_stubs_removed": rim_recovered_weighted,
        },
        "pole_single_pose_domain": {
            "before_stubs": len(pole_eligible),
            "after_stubs": len(pole_post),
            "removed_by_stubs": len(pole_eligible) - len(pole_post),
            "removed_ratio": (len(pole_eligible) - len(pole_post)) / len(pole_eligible),
            "recovered_if_only_rim_stubs_removed": len(pole_rim_recovered),
        },
        "core_front_overreserve_with_other_current_masks": {
            "manufacturing_pose_counts": core_machine_counts,
            "pole_anchors_exact_54_front_semantics": len(core_true_and_stubs),
            "pole_anchors_reserve_all_66": len(core_all_and_stubs),
            "pole_anchors_recovered": len(core_true_and_stubs) - len(core_all_and_stubs),
            "recovered_anchor_coordinates": recovered_core_pole_anchors,
        },
    }


def rectangle_counts() -> dict[str, object]:
    one_axis = sum(71 - w for w in range(6, 71))
    all_rectangles = one_axis**2
    current = 25 * ((14 - 6 + 1) * (14 - 7 + 1) + (14 - 7 + 1) * (14 - 6 + 1))
    same_shape_global = 2 * (70 - 6 + 1) * (70 - 7 + 1)
    local_all_shapes = 25 * (sum(15 - w for w in range(6, 15)) ** 2)
    # For 6x7, non-crossing x/y anchors are 45/40 and crossing are 20/24.
    # For 7x6 the two axes swap.
    one_seam_only = (20 * 40 + 45 * 24) + (24 * 45 + 40 * 20)
    two_perpendicular_seams = 20 * 24 + 24 * 20
    return {
        "all_original_min_side_ge_6": all_rectangles,
        "current_6x7_or_7x6_inside_one_region": current,
        "removed": all_rectangles - current,
        "retained_ratio": current / all_rectangles,
        "same_shape_anywhere": same_shape_global,
        "same_shape_removed_by_seam_rule": same_shape_global - current,
        "same_shape_crossing_exactly_one_seam": one_seam_only,
        "same_shape_crossing_two_perpendicular_seams": two_perpendicular_seams,
        "all_shapes_6_to_14_inside_one_region": local_all_shapes,
    }


def boundary_layout_counts() -> dict[str, object]:
    per_arm = math.comb(70 - 2 * 23, 23)
    no_corner = math.comb(69 - 2 * 23, 23)
    with_corner = math.comb(67 - 2 * 22, 22)
    paired = no_corner * no_corner + with_corner * no_corner + no_corner * with_corner
    return {
        "one_arm_23_disjoint_length3_sets": per_arm,
        "one_arm_without_corner": no_corner,
        "one_arm_with_corner": with_corner,
        "two_arm_nonoverlapping_geometric_arrangements": paired,
        "current_kept": 1,
        "excluded": paired - 1,
        "protocol_core_baseline_poses": 7_688,
        "protocol_core_current_kept": 1,
        "protocol_core_excluded": 7_687,
        "protocol_core_region_contained_poses_if_body_rule_extended": 25 * 6 * 6 * 2,
    }


def power_relation_counts() -> dict[str, object]:
    # One-axis coverage incidence sums for region-contained 2x2 pole anchors.
    total_per_region_axis = []
    local_per_region_axis = []
    for i in range(5):
        total = local = 0
        for a in range(13):
            x = 14 * i + a
            lo, hi = max(0, x - 5), min(69, x + 6)
            total += hi - lo + 1
            rlo, rhi = 14 * i, 14 * i + 13
            local += max(0, min(hi, rhi) - max(lo, rlo) + 1)
        total_per_region_axis.append(total)
        local_per_region_axis.append(local)
    total_axis = sum(total_per_region_axis)
    local_axis = sum(local_per_region_axis)
    cross_axis = total_axis - local_axis
    total_2d = total_axis**2
    local_2d = local_axis**2
    orthogonal_cross = 2 * local_axis * cross_axis
    diagonal_cross = cross_axis**2
    safe_anchor_axis_counts = [8, 3, 3, 3, 8]
    no_neighbor_reach_anchors = sum(safe_anchor_axis_counts) ** 2
    all_anchors = 25 * 13 * 13
    return {
        "one_axis_total_coverage_incidences": total_per_region_axis,
        "one_axis_same_region_incidences": local_per_region_axis,
        "total_pole_anchor_covered_cell_incidences": total_2d,
        "same_region_incidences": local_2d,
        "cross_region_incidences": total_2d - local_2d,
        "cross_region_ratio": (total_2d - local_2d) / total_2d,
        "orthogonal_neighbor_incidences": orthogonal_cross,
        "diagonal_neighbor_incidences": diagonal_cross,
        "region_contained_pole_anchors": all_anchors,
        "anchors_with_no_coverage_reach_into_another_region": no_neighbor_reach_anchors,
        "anchors_with_cross_region_reach": all_anchors - no_neighbor_reach_anchors,
    }


def main() -> None:
    result = {
        "schema": "w0_rstar_price_tag_arithmetic_audit_v1",
        "baseline_hashes": BASELINE_HASHES,
        "body_and_front": body_and_front_pose_counts(),
        "portal_and_core_masks": portal_and_core_mask_counts(),
        "hole_rectangle_witness_domain": rectangle_counts(),
        "boundary_layout": boundary_layout_counts(),
        "power_relation_domain": power_relation_counts(),
    }
    # Guard the most load-bearing numbers against accidental edits.
    assert result["body_and_front"]["mandatory_instance_pose_incidences"]["body_removed"] == 1_169_408
    assert result["body_and_front"]["mandatory_instance_pose_incidences"]["front_increment_removed"] == 386_560
    assert result["portal_and_core_masks"]["live_stubs"]["live"] == 180
    assert result["portal_and_core_masks"]["manufacturing_single_pose_domain"]["weighted_removed"] == 176_088
    assert result["portal_and_core_masks"]["core_front_overreserve_with_other_current_masks"]["pole_anchors_recovered"] == 8
    assert result["hole_rectangle_witness_domain"]["all_original_min_side_ge_6"] == 4_601_025
    assert result["boundary_layout"]["two_arm_nonoverlapping_geometric_arrangements"] == 47
    assert result["power_relation_domain"]["cross_region_incidences"] == 165_600
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    out = Path(__file__).with_name("price_tag_arithmetic_results.json")
    out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
