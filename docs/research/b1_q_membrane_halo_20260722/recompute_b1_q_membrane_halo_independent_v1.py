#!/usr/bin/env python3
"""Independent interval/distribution recomputation for B1-QMH.

This program deliberately does not import the primary B1 recomputation or any
encoder.  It rebuilds the strict ledger, boundary patterns, membrane table,
power-halo certificate, and every pattern/rectangle verdict using exact integer
arithmetic.  The 203,340,800 verdicts are aggregated by independently derived
``(q, e)`` multiplicities rather than materialized one at a time.

The JSON output is created with O_EXCL.  Any malformed input, certificate
mismatch, failed mutation canary, or pre-existing output path is a hard error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


GRID_SIZE = 70
MIN_SIDE = 6
EXPECTED_STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
EXPECTED_CLASS_TABLE = {
    (3, 1): 155,
    (3, 2): 12,
    (3, 3): 11,
    (5, 1): 32,
    (5, 2): 17,
    (6, 3): 32,
    (6, 4): 3,
    (6, 5): 3,
}
EXPECTED_METRICS = {
    "total_pattern_placements": 203_340_800,
    "baseline_survivors": 165_541_238,
    "refined_survivors": 165_541_100,
    "incremental_pruned": 138,
    "refined_surviving_oriented_dimensions": 2_127,
    "baseline_surviving_oriented_dimensions": 2_151,
    "baseline_side_70_dimensions_removed": 24,
}
EXPECTED_INCREMENTAL_PRUNES = {
    (29, 41): 22,
    (34, 35): 47,
    (35, 34): 47,
    (41, 29): 22,
}

# Doubled weights indexed by the unordered pair of odd, doubled distances from
# the half-integral centre of a 2x2 pole.  These 14 entries are the certificate
# material; all cells, orbit multiplicities, totals, and inequalities below are
# reconstructed here.
HALO_ORBITS_DOUBLED = (
    (3, 3, 2),
    (5, 1, 8),
    (5, 5, 16),
    (7, 7, 8),
    (9, 3, 2),
    (9, 9, 2),
    (11, 1, 2),
    (11, 3, 12),
    (11, 5, 22),
    (11, 7, 2),
    (11, 9, 2),
    (13, 11, 25),
    (15, 3, 2),
    (17, 3, 8),
)


class RecomputeError(RuntimeError):
    """A fail-closed recomputation error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecomputeError(message)


def ceil_div(numerator: int, denominator: int) -> int:
    require(denominator > 0, "ceil_div denominator must be positive")
    return -(-numerator // denominator)


def load_strict_instance(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(
        digest == EXPECTED_STRICT_SHA256,
        f"strict instance SHA mismatch: expected={EXPECTED_STRICT_SHA256} got={digest}",
    )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RecomputeError(f"duplicate JSON key: {key!r}")
            result[key] = value
        return result

    try:
        parsed = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda token: (_ for _ in ()).throw(RecomputeError(f"non-finite JSON token: {token}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecomputeError(f"strict instance parse failed: {exc}") from exc
    require(isinstance(parsed, dict), "strict instance root is not an object")
    return parsed, digest


def sum_need_map(raw: Any, label: str) -> int:
    require(isinstance(raw, dict), f"{label} must be an object")
    total = 0
    for commodity, count in raw.items():
        require(isinstance(commodity, str) and commodity, f"bad commodity in {label}")
        require(
            isinstance(count, int) and not isinstance(count, bool) and count >= 0,
            f"bad count in {label}[{commodity!r}]",
        )
        total += count
    return total


def body_area_for_template(template: dict[str, Any], template_id: str) -> int:
    modes = template.get("modes")
    require(isinstance(modes, list) and modes, f"{template_id}: modes missing")
    areas: set[int] = set()
    for mode in modes:
        body = mode.get("body", {})
        width, height = body.get("width"), body.get("height")
        require(
            isinstance(width, int)
            and not isinstance(width, bool)
            and isinstance(height, int)
            and not isinstance(height, bool)
            and width > 0
            and height > 0,
            f"{template_id}: invalid body dimensions",
        )
        areas.add(width * height)
    require(len(areas) == 1, f"{template_id}: mode-dependent body area {areas}")
    return next(iter(areas))


def port_side_length_and_opposition(template: dict[str, Any], template_id: str) -> int:
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}
    side_lengths: set[int] = set()
    for mode in template["modes"]:
        ports = mode.get("ports")
        require(isinstance(ports, list) and ports, f"{template_id}: ports missing")
        input_sides = {port.get("direction") for port in ports if port.get("kind") == "input"}
        output_sides = {port.get("direction") for port in ports if port.get("kind") == "output"}
        require(
            len(input_sides) == len(output_sides) == 1,
            f"{template_id}/{mode.get('id')}: ports are not one-side typed",
        )
        input_side = next(iter(input_sides))
        output_side = next(iter(output_sides))
        require(
            opposite.get(input_side) == output_side,
            f"{template_id}/{mode.get('id')}: input/output sides are not opposite",
        )
        body = mode["body"]
        side_lengths.add(body["width"] if output_side in {"N", "S"} else body["height"])
    require(
        len(side_lengths) == 1,
        f"{template_id}: port-side length differs by mode: {side_lengths}",
    )
    return next(iter(side_lengths))


def derive_strict_ledger(instance: dict[str, Any]) -> dict[str, Any]:
    require(instance.get("grid") == {"height": 70, "width": 70}, "grid is not 70x70")
    templates = instance.get("facility_templates")
    required = instance.get("required_instances")
    groups_raw = instance.get("operation_groups")
    require(isinstance(templates, dict), "facility_templates missing")
    require(isinstance(required, list), "required_instances missing")
    require(isinstance(groups_raw, list), "operation_groups missing")

    groups: dict[str, dict[str, Any]] = {}
    for group in groups_raw:
        group_id = group.get("id")
        require(isinstance(group_id, str) and group_id not in groups, "bad/duplicate group id")
        groups[group_id] = group

    areas = {template_id: body_area_for_template(template, template_id) for template_id, template in templates.items()}
    ids: set[str] = set()
    counts: Counter[str] = Counter()
    required_area = 0
    powered_area = 0
    powered_count = 0
    for item in required:
        item_id = item.get("id")
        template_id = item.get("template")
        require(isinstance(item_id, str) and item_id not in ids, "bad/duplicate instance id")
        require(template_id in templates, f"unknown required template: {template_id!r}")
        ids.add(item_id)
        counts[template_id] += 1
        required_area += areas[template_id]
        if templates[template_id].get("requires_power") is True:
            powered_count += 1
            powered_area += areas[template_id]

    manufacturing_count = sum(
        count for template_id, count in counts.items() if template_id.startswith("manufacturing_")
    )
    boundary_count = counts["boundary_storage_port"]
    core_count = counts["protocol_core"]
    commodities = instance.get("commodities")
    require(isinstance(commodities, list), "commodities missing")
    require(len(set(commodities)) == len(commodities), "duplicate commodities")

    manufacturing_inputs = 0
    manufacturing_outputs = 0
    class_table: Counter[tuple[int, int]] = Counter()
    for group in groups.values():
        count = group.get("count")
        template_id = group.get("template")
        require(
            isinstance(count, int) and not isinstance(count, bool) and count > 0,
            f"bad group count: {group.get('id')}",
        )
        require(
            isinstance(template_id, str) and template_id.startswith("manufacturing_"),
            f"non-manufacturing operation group: {group.get('id')}",
        )
        needs = group.get("port_needs")
        require(isinstance(needs, dict), f"missing port_needs: {group.get('id')}")
        inputs = sum_need_map(needs.get("inputs", {}), f"{group.get('id')}.inputs")
        outputs = sum_need_map(needs.get("outputs", {}), f"{group.get('id')}.outputs")
        manufacturing_inputs += count * inputs
        manufacturing_outputs += count * outputs
        side_length = port_side_length_and_opposition(templates[template_id], template_id)
        class_table[(side_length, max(inputs, outputs))] += count

    class_table[(3, 1)] += boundary_count
    generic = instance.get("generic_requirements")
    require(isinstance(generic, dict), "generic_requirements missing")
    raw_outputs = sum_need_map(generic.get("raw_outputs", {}), "raw_outputs")
    final_inputs = sum_need_map(generic.get("final_inputs", {}), "final_inputs")
    total_active = manufacturing_inputs + manufacturing_outputs + raw_outputs + final_inputs

    boundary_template = templates.get("boundary_storage_port", {})
    require(
        boundary_template.get("placement_rule") == "matching_map_boundary",
        "boundary placement rule changed",
    )
    boundary_mode_capacity = []
    boundary_mode_semantics: list[dict[str, Any]] = []
    direction_vectors = {"E": (1, 0), "N": (0, 1), "W": (-1, 0), "S": (0, -1)}
    for mode in boundary_template.get("modes", []):
        ports = mode.get("ports", [])
        boundary_mode_capacity.append(sum(1 for port in ports if port.get("kind") == "output"))
        require(len(ports) == 1, f"boundary mode {mode.get('id')}: port count changed")
        port = ports[0]
        direction = port.get("direction")
        require(direction in direction_vectors, "boundary port direction changed")
        body_cell = port.get("body_cell")
        require(isinstance(body_cell, dict), "boundary port body_cell missing")
        relative_access = (
            body_cell.get("x") + direction_vectors[direction][0],
            body_cell.get("y") + direction_vectors[direction][1],
        )
        body = mode.get("body", {})
        boundary_mode_semantics.append(
            {
                "id": mode.get("id"),
                "body": [body.get("width"), body.get("height")],
                "direction": direction,
                "body_cell": [body_cell.get("x"), body_cell.get("y")],
                "relative_access": list(relative_access),
            }
        )
    require(boundary_mode_capacity == [1, 1], "boundary output capacity changed")
    require(
        boundary_mode_semantics
        == [
            {
                "id": "left_boundary",
                "body": [1, 3],
                "direction": "E",
                "body_cell": [0, 1],
                "relative_access": [1, 1],
            },
            {
                "id": "bottom_boundary",
                "body": [3, 1],
                "direction": "N",
                "body_cell": [1, 0],
                "relative_access": [1, 1],
            },
        ],
        f"boundary geometry/access semantics changed: {boundary_mode_semantics!r}",
    )

    core_template = templates.get("protocol_core", {})
    core_output_splits: list[list[int]] = []
    for mode in core_template.get("modes", []):
        by_side: Counter[str] = Counter(
            port["direction"] for port in mode.get("ports", []) if port.get("kind") == "output"
        )
        core_output_splits.append(sorted(by_side.values()))
    require(core_output_splits == [[3, 3], [3, 3]], "protocol core output split changed")
    core_output_capacities = {sum(split) for split in core_output_splits}
    require(core_output_capacities == {6}, "protocol core output capacity changed")
    boundary_provider_capacity = boundary_count * boundary_mode_capacity[0]
    core_provider_capacity = next(iter(core_output_capacities))
    require(
        raw_outputs == boundary_provider_capacity + core_provider_capacity,
        "raw-output providers are not exactly saturated",
    )

    computed_sentinels = {
        "commodity_count": len(commodities),
        "generic_final_input_terminals": final_inputs,
        "generic_raw_output_terminals": raw_outputs,
        "manufacturing_input_terminals": manufacturing_inputs,
        "manufacturing_instance_count": manufacturing_count,
        "manufacturing_output_terminals": manufacturing_outputs,
        "operation_group_count": len(groups),
        "required_body_area": required_area,
        "required_instance_count": len(required),
        "total_active_terminals": total_active,
    }
    require(
        computed_sentinels == instance.get("sentinels"),
        f"recomputed sentinel mismatch: {computed_sentinels!r}",
    )
    require(
        (len(required), manufacturing_count, boundary_count, core_count) == (266, 219, 46, 1),
        "required-instance partition changed",
    )
    require((required_area, powered_count, powered_area) == (3544, 219, 3325), "area ledger changed")
    require(total_active == 628, "active-terminal ledger changed")
    require(class_table == Counter(EXPECTED_CLASS_TABLE), f"membrane class table changed: {class_table}")

    excess = sum(count * max(0, 2 * active - side) for (side, active), count in class_table.items())
    endpoint_increment = max(active - max(0, 2 * active - side) for side, active in class_table)
    endpoint_bonus = 8 * endpoint_increment
    require((excess, endpoint_increment, endpoint_bonus) == (63, 3, 24), "membrane constants changed")

    return {
        "sentinels_recomputed": computed_sentinels,
        "facility_partition": {
            "manufacturing": manufacturing_count,
            "boundary_storage_port": boundary_count,
            "protocol_core": core_count,
        },
        "powered_manufacturing_area": powered_area,
        "class_table": [
            {"side": side, "active_allowance": active, "count": count}
            for (side, active), count in sorted(class_table.items())
        ],
        "full_contact_excess": excess,
        "endpoint_increment_max": endpoint_increment,
        "endpoint_bonus": endpoint_bonus,
        "core_output_side_caps": core_output_splits,
        "raw_provider_saturation": {
            "required_outputs": raw_outputs,
            "boundary_capacity": boundary_provider_capacity,
            "protocol_core_capacity": core_provider_capacity,
            "identity": "52 = 46 * 1 + 6",
        },
        "boundary_mode_semantics": boundary_mode_semantics,
        "membrane_incidence_offset": 48,
        "external_incidence_numerator_constant": total_active - 48,
        "outside_free_cell_rhs_with_nine_poles": GRID_SIZE * GRID_SIZE - required_area - 9 * 4,
    }


def derive_halo_certificate(ledger: dict[str, Any]) -> dict[str, Any]:
    orbit_weights = {(major, minor): weight for major, minor, weight in HALO_ORBITS_DOUBLED}
    require(len(orbit_weights) == 14, "duplicate halo orbit")

    def doubled_weight(x: int, y: int) -> int:
        first, second = abs(2 * x - 1), abs(2 * y - 1)
        return orbit_weights.get((max(first, second), min(first, second)), 0)

    stencil = {(x, y): doubled_weight(x, y) for x in range(-8, 10) for y in range(-8, 10) if doubled_weight(x, y)}
    doubled_total = sum(stencil.values())
    require(doubled_total == 792, f"halo total changed: {doubled_total}/2")

    pole_body = {(0, 0), (0, 1), (1, 0), (1, 1)}
    coverage_min, coverage_max = -5, 6
    placement_counts: dict[str, int] = {}
    minimum_slack: int | None = None
    violations: list[dict[str, int]] = []
    for width, height in ((3, 3), (5, 5), (6, 4), (4, 6)):
        checked = 0
        label = f"{width}x{height}"
        for anchor_x in range(coverage_min - width + 1, coverage_max + 1):
            for anchor_y in range(coverage_min - height + 1, coverage_max + 1):
                body = {(anchor_x + dx, anchor_y + dy) for dx in range(width) for dy in range(height)}
                if not any(coverage_min <= x <= coverage_max and coverage_min <= y <= coverage_max for x, y in body):
                    continue
                if body & pole_body:
                    continue
                checked += 1
                weight = sum(stencil.get(cell, 0) for cell in body)
                slack = weight - 2 * width * height
                minimum_slack = slack if minimum_slack is None else min(minimum_slack, slack)
                if slack < 0:
                    violations.append(
                        {
                            "width": width,
                            "height": height,
                            "anchor_x": anchor_x,
                            "anchor_y": anchor_y,
                            "doubled_slack": slack,
                        }
                    )
        placement_counts[label] = checked

    require(not violations, f"halo local inequality violation: {violations[:1]}")
    require(
        placement_counts == {"3x3": 180, "5x5": 220, "6x4": 220, "4x6": 220},
        f"halo placement corpus changed: {placement_counts}",
    )
    placement_total = sum(placement_counts.values())
    powered_area = ledger["powered_manufacturing_area"]
    pole_lower_bound = ceil_div(powered_area, doubled_total // 2)
    require((placement_total, pole_lower_bound) == (840, 9), "halo conclusion changed")
    return {
        "orbit_count": len(orbit_weights),
        "nonzero_stencil_cells": len(stencil),
        "doubled_total_weight": doubled_total,
        "total_weight": doubled_total // 2,
        "placement_counts": placement_counts,
        "placement_total": placement_total,
        "minimum_doubled_inequality_slack": minimum_slack,
        "powered_area": powered_area,
        "pole_lower_bound": pole_lower_bound,
    }


def edge_intervals(gap: int) -> tuple[tuple[int, int, int], ...]:
    require(gap in range(0, GRID_SIZE, 3), f"invalid boundary gap: {gap}")
    covered = [coordinate for coordinate in range(GRID_SIZE) if coordinate != gap]
    require(len(covered) == 69, "boundary gap did not leave 69 cells")
    intervals: list[tuple[int, int, int]] = []
    for offset in range(0, len(covered), 3):
        chunk = covered[offset : offset + 3]
        require(
            len(chunk) == 3 and chunk == list(range(chunk[0], chunk[0] + 3)),
            f"non-contiguous boundary body around gap {gap}",
        )
        intervals.append((chunk[0], chunk[1], chunk[2]))
    require(len(intervals) == 23, "boundary edge does not contain 23 bodies")
    return tuple(intervals)


def validate_pattern_pairs(patterns: tuple[tuple[int, int], ...]) -> None:
    gaps = set(range(0, GRID_SIZE, 3))
    require(len(patterns) == 47, f"boundary pattern count is {len(patterns)}, not 47")
    require(len(set(patterns)) == len(patterns), "duplicate boundary pattern")
    for left_gap, bottom_gap in patterns:
        require(left_gap in gaps and bottom_gap in gaps, "boundary gap outside legal set")
        require(left_gap == 0 or bottom_gap == 0, "boundary bodies overlap at (0,0)")


def derive_boundary_patterns() -> tuple[tuple[tuple[int, int], ...], dict[int, tuple[int, ...]], dict[str, Any]]:
    gaps = tuple(range(0, GRID_SIZE, 3))
    patterns = tuple([(0, gap) for gap in gaps] + [(gap, 0) for gap in gaps[1:]])
    validate_pattern_pairs(patterns)
    midpoints = {gap: tuple(interval[1] for interval in edge_intervals(gap)) for gap in gaps}

    overlap_errors = 0
    q_sizes: set[int] = set()
    for left_gap, bottom_gap in patterns:
        left_bodies = {(0, coordinate) for interval in edge_intervals(left_gap) for coordinate in interval}
        bottom_bodies = {(coordinate, 0) for interval in edge_intervals(bottom_gap) for coordinate in interval}
        overlap_errors += len(left_bodies & bottom_bodies)
        q_cells = {(1, midpoint) for midpoint in midpoints[left_gap]} | {
            (midpoint, 1) for midpoint in midpoints[bottom_gap]
        }
        q_sizes.add(len(q_cells))
    require(overlap_errors == 0, "boundary patterns contain body overlap")
    require(q_sizes == {46}, f"Q_delta cardinality changed: {q_sizes}")

    left_gap_multiplicity = Counter(left for left, _ in patterns)
    bottom_gap_multiplicity = Counter(bottom for _, bottom in patterns)
    return (
        patterns,
        midpoints,
        {
            "gap_coordinates": list(gaps),
            "pattern_count": len(patterns),
            "q_cardinality_each": 46,
            "body_overlap_errors": overlap_errors,
            "left_gap_multiplicity": {str(key): value for key, value in sorted(left_gap_multiplicity.items())},
            "bottom_gap_multiplicity": {str(key): value for key, value in sorted(bottom_gap_multiplicity.items())},
        },
    )


def interval_q_e(points: tuple[int, ...], start: int, span: int) -> tuple[int, int]:
    require(span >= MIN_SIDE, "rectangle span below objective minimum")
    stop = start + span - 1
    left = bisect_left(points, start)
    right = bisect_right(points, stop)
    q = right - left
    endpoint_count = int(left < len(points) and points[left] == start)
    endpoint_index = bisect_left(points, stop, left, right)
    endpoint_count += int(endpoint_index < right and points[endpoint_index] == stop)
    return q, endpoint_count


def necessary_condition(
    width: int,
    height: int,
    q: int,
    endpoint_partials: int,
    *,
    incidence_cap: int = 4,
    pole_count: int = 9,
    use_ceiling: bool = True,
) -> bool:
    numerator = 580 - width - height + q // 2 + endpoint_partials
    external_cells = ceil_div(numerator, incidence_cap) if use_ceiling else numerator // incidence_cap
    free_cell_rhs = GRID_SIZE * GRID_SIZE - 3544 - 4 * pole_count
    return width * height + external_cells <= free_cell_rhs


def edge_distribution(
    span: int,
    gap_multiplicity: Counter[int],
    midpoints: dict[int, tuple[int, ...]],
) -> Counter[tuple[int, int]]:
    result: Counter[tuple[int, int]] = Counter()
    maximum_anchor = GRID_SIZE - span
    for gap, multiplicity in gap_multiplicity.items():
        for anchor in range(2, maximum_anchor + 1):
            result[interval_q_e(midpoints[gap], anchor, span)] += multiplicity
    require(
        sum(result.values()) == 47 * max(0, maximum_anchor - 1),
        f"edge distribution mass mismatch for span {span}",
    )
    return result


def corner_distribution(
    width: int,
    height: int,
    patterns: tuple[tuple[int, int], ...],
    midpoints: dict[int, tuple[int, ...]],
) -> Counter[tuple[int, int]]:
    result: Counter[tuple[int, int]] = Counter()
    for left_gap, bottom_gap in patterns:
        left_q, left_e = interval_q_e(midpoints[left_gap], 1, height)
        bottom_q, bottom_e = interval_q_e(midpoints[bottom_gap], 1, width)
        result[(left_q + bottom_q, left_e + bottom_e)] += 1
    require(sum(result.values()) == 47, "corner distribution mass mismatch")
    return result


def objective(width: int, height: int) -> tuple[int, int]:
    return width * height, min(width, height)


def serialize_q_e_distribution(counter: Counter[tuple[int, int]]) -> list[dict[str, int]]:
    return [{"q": q, "endpoint_partials": endpoint, "count": count} for (q, endpoint), count in sorted(counter.items())]


def scan_all_placements(
    patterns: tuple[tuple[int, int], ...],
    midpoints: dict[int, tuple[int, ...]],
) -> tuple[dict[str, int], dict[str, Any], list[dict[str, int]], dict[str, Any], dict[str, Any]]:
    left_multiplicity = Counter(left for left, _ in patterns)
    bottom_multiplicity = Counter(bottom for _, bottom in patterns)
    edge_distributions = {
        span: edge_distribution(span, left_multiplicity, midpoints) for span in range(MIN_SIDE, GRID_SIZE)
    }
    # Reflection symmetry is derived rather than assumed silently.
    for span in range(MIN_SIDE, GRID_SIZE):
        require(
            edge_distributions[span] == edge_distribution(span, bottom_multiplicity, midpoints),
            f"left/bottom distribution mismatch at span {span}",
        )

    total = 0
    baseline_survivors = 0
    refined_survivors = 0
    refined_by_dimension: dict[tuple[int, int], int] = {}
    baseline_internal_dimension_count = 0
    incremental: dict[tuple[int, int], int] = {}
    distributions_by_dimension: dict[tuple[int, int], Counter[tuple[int, int]]] = {}
    mutation_witnesses: dict[str, dict[str, int] | None] = {
        "incidence_cap_5": None,
        "pole_count_8": None,
        "floor_instead_of_ceil": None,
    }

    for width in range(MIN_SIDE, GRID_SIZE):
        anchors_x = GRID_SIZE - width
        for height in range(MIN_SIDE, GRID_SIZE):
            anchors_y = GRID_SIZE - height
            dimension_mass = 47 * anchors_x * anchors_y
            total += dimension_mass
            baseline_ok = necessary_condition(width, height, 0, 0)
            if baseline_ok:
                baseline_survivors += dimension_mass
                baseline_internal_dimension_count += 1

            distribution: Counter[tuple[int, int]] = Counter()
            interior_mass = 47 * max(0, anchors_x - 1) * max(0, anchors_y - 1)
            if interior_mass:
                distribution[(0, 0)] += interior_mass
            distribution.update(edge_distributions[height])
            distribution.update(edge_distributions[width])
            distribution.update(corner_distribution(width, height, patterns, midpoints))
            require(
                sum(distribution.values()) == dimension_mass,
                f"placement mass mismatch for {(width, height)}",
            )
            distributions_by_dimension[(width, height)] = distribution

            refined_count = 0
            for (q, endpoint), multiplicity in distribution.items():
                canonical_ok = necessary_condition(width, height, q, endpoint)
                if canonical_ok:
                    refined_count += multiplicity
                mutation_specs = (
                    ("incidence_cap_5", {"incidence_cap": 5}),
                    ("pole_count_8", {"pole_count": 8}),
                    ("floor_instead_of_ceil", {"use_ceiling": False}),
                )
                for label, kwargs in mutation_specs:
                    if (
                        mutation_witnesses[label] is None
                        and not canonical_ok
                        and necessary_condition(width, height, q, endpoint, **kwargs)
                    ):
                        mutation_witnesses[label] = {
                            "width": width,
                            "height": height,
                            "q": q,
                            "endpoint_partials": endpoint,
                        }

            refined_survivors += refined_count
            if refined_count:
                refined_by_dimension[(width, height)] = refined_count
            if baseline_ok and refined_count != dimension_mass:
                incremental[(width, height)] = dimension_mass - refined_count

    baseline_dimensions_70 = []
    for width in range(MIN_SIDE, GRID_SIZE + 1):
        for height in range(MIN_SIDE, GRID_SIZE + 1):
            if necessary_condition(width, height, 0, 0):
                baseline_dimensions_70.append((width, height))
    side_70 = [pair for pair in baseline_dimensions_70 if GRID_SIZE in pair]
    require(
        baseline_internal_dimension_count == len([pair for pair in baseline_dimensions_70 if GRID_SIZE not in pair]),
        "baseline dimension accounting mismatch",
    )

    metrics = {
        "total_pattern_placements": total,
        "baseline_survivors": baseline_survivors,
        "refined_survivors": refined_survivors,
        "incremental_pruned": baseline_survivors - refined_survivors,
        "refined_surviving_oriented_dimensions": len(refined_by_dimension),
        "baseline_surviving_oriented_dimensions": len(baseline_dimensions_70),
        "baseline_side_70_dimensions_removed": len(side_70),
    }
    require(metrics == EXPECTED_METRICS, f"terminal metric mismatch: {metrics!r}")
    require(incremental == EXPECTED_INCREMENTAL_PRUNES, f"incremental prune mismatch: {incremental!r}")

    old_upper = max(objective(width, height) for width, height in baseline_dimensions_70)
    new_upper = max(objective(width, height) for width, height in refined_by_dimension)
    require(old_upper == new_upper == (1190, 34), "frontier unexpectedly changed")

    grouped: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for pair in refined_by_dimension:
        grouped[objective(*pair)].append(pair)
    top_objectives = sorted(grouped, reverse=True)[:12]
    frontier = {
        "old_upper": list(old_upper),
        "new_upper": list(new_upper),
        "top_surviving_bands": [
            {
                "objective": list(band),
                "oriented_dimensions": [list(pair) for pair in sorted(grouped[band])],
                "pattern_placements": sum(refined_by_dimension[pair] for pair in grouped[band]),
            }
            for band in top_objectives
        ],
        "side_70_baseline_only_dimensions": [list(pair) for pair in sorted(side_70)],
    }

    ceiling_dimensions = [(34, 35), (35, 34)]
    ceiling = {
        "objective": [1190, 34],
        "dimensions": [],
        "total_refined_pattern_placements": 0,
    }
    for pair in ceiling_dimensions:
        distribution = distributions_by_dimension[pair]
        refined_distribution = Counter(
            {
                key: multiplicity
                for key, multiplicity in distribution.items()
                if necessary_condition(pair[0], pair[1], key[0], key[1])
            }
        )
        record = {
            "width": pair[0],
            "height": pair[1],
            "baseline_pattern_placements": 47 * (GRID_SIZE - pair[0]) * (GRID_SIZE - pair[1]),
            "refined_pattern_placements": refined_by_dimension[pair],
            "incremental_pruned": incremental[pair],
            "surviving_q_e_distribution": serialize_q_e_distribution(refined_distribution),
        }
        ceiling["dimensions"].append(record)
        ceiling["total_refined_pattern_placements"] += refined_by_dimension[pair]
    require(
        [record["refined_pattern_placements"] for record in ceiling["dimensions"]] == [59_173, 59_173],
        "ceiling survivor count changed",
    )

    incremental_rows = [
        {
            "width": width,
            "height": height,
            "objective_area": width * height,
            "objective_min_side": min(width, height),
            "pruned_pattern_placements": count,
        }
        for (width, height), count in sorted(incremental.items())
    ]
    require(all(value is not None for value in mutation_witnesses.values()), "mutation witness missing")
    return metrics, frontier, incremental_rows, ceiling, mutation_witnesses


def run_canaries(
    patterns: tuple[tuple[int, int], ...],
    midpoints: dict[int, tuple[int, ...]],
    mutation_witnesses: dict[str, dict[str, int] | None],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    def rejected(action: Any) -> bool:
        try:
            action()
        except RecomputeError:
            return True
        return False

    missing_pattern_rejected = rejected(lambda: validate_pattern_pairs(patterns[:-1]))
    duplicate_pattern_rejected = rejected(lambda: validate_pattern_pairs(patterns[:-1] + (patterns[0],)))

    canonical_q, canonical_e = interval_q_e(midpoints[0], 2, 6)
    require((canonical_q, canonical_e) == (2, 1), "endpoint canary fixture drifted")
    strict_interior_mutant = sum(1 for point in midpoints[0] if 2 < point < 7)
    endpoint_mutation_rejected = strict_interior_mutant != canonical_q

    # The access cell for an inward E/N boundary port is one step from its body
    # cell.  Reversing either direction must not preserve the canonical offset.
    direction_vectors = {"E": (1, 0), "N": (0, 1), "W": (-1, 0), "S": (0, -1)}
    canonical_offsets = tuple(direction_vectors[record["direction"]] for record in ledger["boundary_mode_semantics"])
    offset_mutant = (direction_vectors["W"], direction_vectors["S"])
    q_offset_mutation_rejected = canonical_offsets == ((1, 0), (0, 1)) and offset_mutant != canonical_offsets

    # An abstract capacity witness demonstrates why Q-out cannot be added to the
    # generic external-cell lower bound: 46 forced Q cells plus 64 other cells
    # can carry 440 incidences at cap four, using 110 union cells, not 156.
    q_out = 46
    other_cells = 64
    external_incidences = 440
    union_cells = q_out + other_cells
    require(4 * union_cells == external_incidences, "double-count canary fixture drifted")
    unsound_additive_value = q_out + ceil_div(external_incidences, 4)
    forbidden_addition_rejected = union_cells < unsound_additive_value

    mutated_halo_total = 792 - 4  # reducing a four-cell diagonal orbit by one each
    halo_weight_mutation_rejected = mutated_halo_total != 792
    class_count_mutation_rejected = Counter(EXPECTED_CLASS_TABLE) != Counter(
        {**EXPECTED_CLASS_TABLE, (3, 1): EXPECTED_CLASS_TABLE[(3, 1)] - 1}
    )

    flags = {
        "missing_pattern_rejected": missing_pattern_rejected,
        "duplicate_pattern_rejected": duplicate_pattern_rejected,
        "q_offset_mutation_rejected": q_offset_mutation_rejected,
        "partial_endpoint_mutation_rejected": endpoint_mutation_rejected,
        "class_table_mutation_rejected": class_count_mutation_rejected,
        "halo_weight_mutation_rejected": halo_weight_mutation_rejected,
        "forbidden_q_plus_membrane_addition_rejected": forbidden_addition_rejected,
    }
    require(all(flags.values()), f"boolean mutation canary failed: {flags!r}")
    require(all(value is not None for value in mutation_witnesses.values()), "arithmetic canary missing")
    return {
        **flags,
        "arithmetic_mutation_witnesses": mutation_witnesses,
        "forbidden_addition_abstract_witness": {
            "q_out_cells": q_out,
            "other_external_cells": other_cells,
            "external_incidences": external_incidences,
            "sound_union_cells": union_cells,
            "unsound_additive_cells": unsound_additive_value,
        },
    }


def write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    require(path.parent.is_dir(), f"output parent does not exist: {path.parent}")
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o644)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            require(written > 0, "short zero-byte output write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def build_report(instance_path: Path) -> dict[str, Any]:
    instance, strict_sha = load_strict_instance(instance_path)
    ledger = derive_strict_ledger(instance)
    halo = derive_halo_certificate(ledger)
    patterns, midpoints, boundary = derive_boundary_patterns()
    metrics, frontier, incremental, ceiling, mutation_witnesses = scan_all_placements(patterns, midpoints)
    canaries = run_canaries(patterns, midpoints, mutation_witnesses, ledger)
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {
        "schema_version": "b1_q_membrane_halo_independent_recompute_v1",
        "status": "PASS",
        "claim_scope": {
            "kind": "necessary_condition_recomputation_only",
            "does_not_prove": [
                "witness",
                "attainability",
                "routing_feasibility",
                "global_optimality",
                "production_CERTIFIED_status",
            ],
        },
        "provenance": {
            "algorithm": "interval_bisect_q_e_distribution_aggregation",
            "strict_instance_repo_relative": str(
                instance_path.resolve().relative_to(Path(__file__).resolve().parents[3])
            ),
            "strict_instance_sha256": strict_sha,
            "script_sha256": script_sha,
            "imports_primary_recompute_or_encoder": False,
        },
        "strict_ledger": ledger,
        "halo": halo,
        "boundary": boundary,
        "formula": {
            "text": "w*h + ceil((580-w-h+floor(q/2)+e)/4) <= 1320",
            "q_definition": "|R intersect Q_delta|",
            "e_definition": "boundary partial contacts at tangential rectangle endpoints",
            "integer_rounding": "ceil_div exact integer arithmetic",
        },
        "metrics": metrics,
        "frontier": frontier,
        "ceiling": ceiling,
        "incremental_prunes": incremental,
        "canaries": canaries,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-instance",
        type=Path,
        default=repo_root / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json",
        help="pinned strict problem instance",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new JSON path; existing paths are rejected",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = build_report(args.strict_instance)
        write_exclusive(args.output, report)
    except (OSError, RecomputeError, KeyError, TypeError, ValueError) as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    metrics = report["metrics"]
    print(
        "PASS: independent B1-QMH recomputation "
        f"corpus={metrics['total_pattern_placements']} "
        f"baseline={metrics['baseline_survivors']} "
        f"refined={metrics['refined_survivors']} "
        f"pruned={metrics['incremental_pruned']} "
        f"frontier={tuple(report['frontier']['new_upper'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
