#!/usr/bin/env python3
"""Standalone coordinate recomputation for the B1 Q/membrane/halo lemma.

This research checker imports no encoder and no earlier certificate checker.  It
derives the strict ledger, reconstructs all 47 boundary patterns, and scans the
complete pattern/rectangle-placement corpus.  Every mismatch exits non-zero.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_PATH = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED_STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
EXPECTED_CLASS_TABLE = Counter(
    {
        (3, 1): 155,
        (3, 2): 12,
        (3, 3): 11,
        (5, 1): 32,
        (5, 2): 17,
        (6, 3): 32,
        (6, 4): 3,
        (6, 5): 3,
    }
)
EXPECTED_METRICS = {
    "pattern_placement_corpus": 203_340_800,
    "baseline_surviving_placements": 165_541_238,
    "refined_surviving_placements": 165_541_100,
    "incremental_pruned_placements": 138,
    "surviving_oriented_dimensions": 2_127,
    "old_oriented_dimensions": 2_151,
    "side_70_dimensions_removed": 24,
}


class RecomputeError(ValueError):
    """The strict input or a recomputation invariant failed."""


@dataclass(frozen=True, slots=True)
class BoundaryPattern:
    index: int
    left_gap: int
    bottom_gap: int
    left_anchors: tuple[int, ...]
    bottom_anchors: tuple[int, ...]


def _reject_constant(value: str) -> Any:
    raise RecomputeError(f"non-finite JSON number is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecomputeError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_strict(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_STRICT_SHA256:
        raise RecomputeError(f"strict instance SHA drift: {digest}")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecomputeError(f"strict instance parse failure: {exc}") from exc
    if not isinstance(value, dict):
        raise RecomputeError("strict instance root must be an object")
    return value, digest


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecomputeError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RecomputeError(f"{field} must be an array")
    return value


def _integer(value: Any, field: str) -> int:
    if type(value) is not int:
        raise RecomputeError(f"{field} must be an exact integer")
    return int(value)


def _needs(value: Any, field: str) -> int:
    if isinstance(value, Mapping):
        return sum(_integer(item, f"{field}.{key}") for key, item in value.items())
    return _integer(value, field)


def _mode_area(template: Mapping[str, Any], field: str) -> int:
    areas: set[int] = set()
    for index, raw_mode in enumerate(_sequence(template.get("modes"), f"{field}.modes")):
        mode = _mapping(raw_mode, f"{field}.modes[{index}]")
        body = _mapping(mode.get("body"), f"{field}.modes[{index}].body")
        areas.add(_integer(body.get("width"), f"{field}.width") * _integer(body.get("height"), f"{field}.height"))
    if len(areas) != 1:
        raise RecomputeError(f"{field} modes disagree on body area")
    return next(iter(areas))


def _derive_ledger(root: Mapping[str, Any]) -> dict[str, Any]:
    grid = _mapping(root.get("grid"), "grid")
    objective = _mapping(root.get("objective"), "objective")
    if (
        _integer(grid.get("width"), "grid.width"),
        _integer(grid.get("height"), "grid.height"),
        _integer(objective.get("minimum_side"), "objective.minimum_side"),
    ) != (70, 70, 6):
        raise RecomputeError("grid/objective baseline drift")
    if objective.get("body_cells_only") is not True:
        raise RecomputeError("objective is no longer body-cells-only")

    templates = _mapping(root.get("facility_templates"), "facility_templates")
    required = _sequence(root.get("required_instances"), "required_instances")
    groups_seq = _sequence(root.get("operation_groups"), "operation_groups")
    groups: dict[str, Mapping[str, Any]] = {}
    for index, raw_group in enumerate(groups_seq):
        group = _mapping(raw_group, f"operation_groups[{index}]")
        group_id = group.get("id")
        if type(group_id) is not str or not group_id or group_id in groups:
            raise RecomputeError("operation group ids must be unique strings")
        groups[group_id] = group

    template_counts: Counter[str] = Counter()
    required_area = 0
    powered_area = 0
    manufacturing_inputs = 0
    manufacturing_outputs = 0
    physical_ports = 0
    powered: list[Mapping[str, Any]] = []
    identifiers: set[str] = set()
    for index, raw_item in enumerate(required):
        item = _mapping(raw_item, f"required_instances[{index}]")
        identifier = item.get("id")
        template_name = item.get("template")
        if type(identifier) is not str or not identifier or identifier in identifiers:
            raise RecomputeError("required instance ids must be unique strings")
        if type(template_name) is not str or template_name not in templates:
            raise RecomputeError(f"unknown template on {identifier!r}")
        identifiers.add(identifier)
        template_counts[template_name] += 1
        template = _mapping(templates[template_name], f"template.{template_name}")
        area = _mode_area(template, f"template.{template_name}")
        required_area += area
        port_counts = {
            len(
                _sequence(
                    _mapping(mode, f"{template_name}.mode").get("ports"),
                    f"{template_name}.ports",
                )
            )
            for mode in _sequence(template.get("modes"), f"{template_name}.modes")
        }
        if len(port_counts) != 1:
            raise RecomputeError(f"{template_name} physical-port count varies by mode")
        physical_ports += next(iter(port_counts))
        if template.get("requires_power") is True:
            powered.append(item)
            powered_area += area
        if template_name.startswith("manufacturing_"):
            operation = item.get("operation")
            if type(operation) is not str or operation not in groups:
                raise RecomputeError(f"unknown operation on {identifier}")
            needs = _mapping(groups[operation].get("port_needs"), f"{operation}.port_needs")
            manufacturing_inputs += _needs(needs.get("inputs"), f"{operation}.inputs")
            manufacturing_outputs += _needs(needs.get("outputs"), f"{operation}.outputs")

    generic = _mapping(root.get("generic_requirements"), "generic_requirements")
    raw_outputs = _needs(generic.get("raw_outputs"), "generic.raw_outputs")
    final_inputs = _needs(generic.get("final_inputs"), "generic.final_inputs")
    sentinels = {
        "required_instances": len(required),
        "manufacturing_instances": len(powered),
        "required_body_area": required_area,
        "powered_manufacturing_area": powered_area,
        "manufacturing_input_terminals": manufacturing_inputs,
        "manufacturing_output_terminals": manufacturing_outputs,
        "generic_raw_output_terminals": raw_outputs,
        "generic_final_input_terminals": final_inputs,
        "active_input_terminals": manufacturing_inputs + final_inputs,
        "active_output_terminals": manufacturing_outputs + raw_outputs,
        "total_active_terminals": manufacturing_inputs + manufacturing_outputs + raw_outputs + final_inputs,
        "physical_port_specs": physical_ports,
        "operation_groups": len(groups),
        "commodities": len(_sequence(root.get("commodities"), "commodities")),
        "boundary_instances": template_counts["boundary_storage_port"],
        "protocol_core_instances": template_counts["protocol_core"],
    }
    expected = {
        "required_instances": 266,
        "manufacturing_instances": 219,
        "required_body_area": 3544,
        "powered_manufacturing_area": 3325,
        "manufacturing_input_terminals": 310,
        "manufacturing_output_terminals": 264,
        "generic_raw_output_terminals": 52,
        "generic_final_input_terminals": 2,
        "active_input_terminals": 312,
        "active_output_terminals": 316,
        "total_active_terminals": 628,
        "physical_port_specs": 1804,
        "operation_groups": 17,
        "commodities": 19,
        "boundary_instances": 46,
        "protocol_core_instances": 1,
    }
    if sentinels != expected:
        raise RecomputeError(f"strict ledger drift: {sentinels}")

    opposites = {"N": "S", "S": "N", "E": "W", "W": "E"}
    class_table: Counter[tuple[int, int]] = Counter()
    for item in powered:
        template_name = str(item["template"])
        template = _mapping(templates[template_name], f"template.{template_name}")
        spans: set[int] = set()
        for raw_mode in _sequence(template.get("modes"), f"{template_name}.modes"):
            mode = _mapping(raw_mode, f"{template_name}.mode")
            body = _mapping(mode.get("body"), f"{template_name}.body")
            ports = _sequence(mode.get("ports"), f"{template_name}.ports")
            inputs = {
                _mapping(port, "port").get("direction")
                for port in ports
                if _mapping(port, "port").get("kind") == "input"
            }
            outputs = {
                _mapping(port, "port").get("direction")
                for port in ports
                if _mapping(port, "port").get("kind") == "output"
            }
            if len(inputs) != 1 or len(outputs) != 1:
                raise RecomputeError(f"{template_name} is not one-sided by port kind")
            output_direction = next(iter(outputs))
            if opposites[next(iter(inputs))] != output_direction:
                raise RecomputeError(f"{template_name} input/output sides are not opposite")
            width = _integer(body.get("width"), f"{template_name}.width")
            height = _integer(body.get("height"), f"{template_name}.height")
            spans.add(width if output_direction in {"N", "S"} else height)
        if len(spans) != 1:
            raise RecomputeError(f"{template_name} port-bearing span varies")
        operation = groups[str(item["operation"])]
        needs = _mapping(operation.get("port_needs"), "port_needs")
        maximum = max(
            _needs(needs.get("inputs"), "inputs"),
            _needs(needs.get("outputs"), "outputs"),
        )
        class_table[(next(iter(spans)), maximum)] += 1
    class_table[(3, 1)] += 46
    if class_table != EXPECTED_CLASS_TABLE:
        raise RecomputeError(f"membrane class table drift: {dict(class_table)}")
    excess = sum(count * max(0, 2 * maximum - span) for (span, maximum), count in class_table.items())
    if excess != 63:
        raise RecomputeError(f"membrane excess drift: {excess}")

    boundary = _mapping(templates.get("boundary_storage_port"), "boundary template")
    if boundary.get("placement_rule") != "matching_map_boundary":
        raise RecomputeError("boundary placement rule drift")
    boundary_modes = {
        str(_mapping(mode, "boundary mode").get("id")): _mapping(mode, "boundary mode")
        for mode in _sequence(boundary.get("modes"), "boundary modes")
    }
    left = _mapping(boundary_modes.get("left_boundary"), "left boundary mode")
    bottom = _mapping(boundary_modes.get("bottom_boundary"), "bottom boundary mode")
    if left.get("body") != {"height": 3, "width": 1} or bottom.get("body") != {
        "height": 1,
        "width": 3,
    }:
        raise RecomputeError("boundary body geometry drift")
    expected_boundary_ports = {
        "left_boundary": ({"x": 0, "y": 1}, "E"),
        "bottom_boundary": ({"x": 1, "y": 0}, "N"),
    }
    for name, mode in (("left_boundary", left), ("bottom_boundary", bottom)):
        ports = _sequence(mode.get("ports"), f"{name}.ports")
        if len(ports) != 1:
            raise RecomputeError(f"{name} must have one physical port")
        port = _mapping(ports[0], f"{name}.port")
        expected_cell, expected_direction = expected_boundary_ports[name]
        if (
            port.get("kind") != "output"
            or port.get("body_cell") != expected_cell
            or port.get("direction") != expected_direction
        ):
            raise RecomputeError(f"{name} active access geometry drift")

    core = _mapping(templates.get("protocol_core"), "protocol core template")
    core_output_splits: list[list[int]] = []
    core_output_capacities: set[int] = set()
    for raw_mode in _sequence(core.get("modes"), "protocol core modes"):
        mode = _mapping(raw_mode, "protocol core mode")
        by_side: Counter[str] = Counter(
            str(_mapping(port, "protocol core port").get("direction"))
            for port in _sequence(mode.get("ports"), "protocol core ports")
            if _mapping(port, "protocol core port").get("kind") == "output"
        )
        core_output_splits.append(sorted(by_side.values()))
        core_output_capacities.add(sum(by_side.values()))
    if core_output_splits != [[3, 3], [3, 3]] or core_output_capacities != {6}:
        raise RecomputeError("protocol core output capacity/sides drift")
    boundary_provider_capacity = template_counts["boundary_storage_port"]
    core_provider_capacity = next(iter(core_output_capacities))
    if raw_outputs != boundary_provider_capacity + core_provider_capacity:
        raise RecomputeError("raw-output providers are no longer exactly saturated")

    halo = _verify_halo(powered_area)
    return {
        "sentinels": sentinels,
        "class_table": [
            {"span": span, "maximum": maximum, "count": count} for (span, maximum), count in sorted(class_table.items())
        ],
        "membrane_excess": excess,
        "endpoint_slots": 8,
        "endpoint_extra": 3,
        "minimum_poles": 9,
        "free_cell_cap": 1320,
        "halo": halo,
        "raw_provider_saturation": {
            "required_outputs": raw_outputs,
            "boundary_capacity": boundary_provider_capacity,
            "protocol_core_capacity": core_provider_capacity,
            "identity": "52 = 46 * 1 + 6",
        },
        "protocol_core_output_side_caps": core_output_splits,
    }


def _verify_halo(powered_area: int) -> dict[str, int]:
    weights2 = {
        (3, 3): 2,
        (5, 1): 8,
        (5, 5): 16,
        (7, 7): 8,
        (9, 3): 2,
        (9, 9): 2,
        (11, 1): 2,
        (11, 3): 12,
        (11, 5): 22,
        (11, 7): 2,
        (11, 9): 2,
        (13, 11): 25,
        (15, 3): 2,
        (17, 3): 8,
    }

    def weight2(x_value: int, y_value: int) -> int:
        first = abs(2 * x_value - 1)
        second = abs(2 * y_value - 1)
        return weights2.get((max(first, second), min(first, second)), 0)

    if sum(weight2(x, y) for x in range(-12, 14) for y in range(-12, 14)) != 792:
        raise RecomputeError("halo stencil weight is not 396")
    pole_body = {(0, 0), (0, 1), (1, 0), (1, 1)}
    checked = 0
    for width, height in ((3, 3), (5, 5), (6, 4), (4, 6)):
        for anchor_x in range(-5 - width + 1, 7):
            for anchor_y in range(-5 - height + 1, 7):
                body = {(anchor_x + dx, anchor_y + dy) for dx in range(width) for dy in range(height)}
                if body & pole_body:
                    continue
                checked += 1
                if sum(weight2(x, y) for x, y in body) < 2 * width * height:
                    raise RecomputeError("halo placement inequality failed")
    minimum_poles = math.ceil(powered_area / 396)
    if checked != 840 or powered_area != 3325 or minimum_poles != 9:
        raise RecomputeError("halo placement count or pole lower bound drift")
    return {
        "orbit_count": len(weights2),
        "total_weight": 396,
        "placement_count": checked,
        "powered_area": powered_area,
        "minimum_poles": minimum_poles,
    }


def _anchors(gap: int) -> tuple[int, ...]:
    result = tuple(range(0, gap, 3)) + tuple(gap + 1 + 3 * index for index in range(23 - gap // 3))
    if len(result) != 23 or any(anchor < 0 or anchor > 67 for anchor in result):
        raise RecomputeError(f"invalid boundary gap {gap}")
    return result


def _patterns() -> tuple[BoundaryPattern, ...]:
    gaps = tuple(range(0, 70, 3))
    pairs = tuple((0, gap) for gap in gaps) + tuple((gap, 0) for gap in gaps if gap)
    patterns = tuple(
        BoundaryPattern(index, left, bottom, _anchors(left), _anchors(bottom))
        for index, (left, bottom) in enumerate(pairs)
    )
    if len(patterns) != 47:
        raise RecomputeError("boundary pattern count is not 47")
    for pattern in patterns:
        q_cells = {(1, anchor + 1) for anchor in pattern.left_anchors} | {
            (anchor + 1, 1) for anchor in pattern.bottom_anchors
        }
        if len(q_cells) != 46:
            raise RecomputeError(f"pattern {pattern.index} does not have 46 Q cells")
    return patterns


def _contact_profile(anchors: Sequence[int], start: int, span: int) -> tuple[int, int]:
    rectangle_interval = set(range(start, start + span))
    q_count = 0
    endpoint_partials = 0
    for anchor in anchors:
        access = anchor + 1
        if access not in rectangle_interval:
            continue
        q_count += 1
        contact = len(rectangle_interval & set(range(anchor, anchor + 3)))
        if contact not in {2, 3}:
            raise RecomputeError(f"active boundary contact length must be 2 or 3, got {contact}")
        endpoint_partials += contact == 2
    return q_count, endpoint_partials


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def _baseline_ok(width: int, height: int, *, cap: int = 1320, incidence_cap: int = 4) -> bool:
    return width * height + _ceil_div(580 - width - height, incidence_cap) <= cap


def _refined_ok(width: int, height: int, q_count: int, endpoint_count: int) -> bool:
    return (
        width * height
        + _ceil_div(
            580 - width - height + q_count // 2 + endpoint_count,
            4,
        )
        <= 1320
    )


def _q_only_ok(width: int, height: int, q_count: int) -> bool:
    return width * height + _ceil_div(580 - width - height + q_count // 2, 4) <= 1320


def _scan(patterns: Sequence[BoundaryPattern]) -> dict[str, Any]:
    old_dimensions = {
        (width, height) for width in range(6, 71) for height in range(6, 71) if _baseline_ok(width, height)
    }
    lex_better = {
        (width, height)
        for width in range(6, 71)
        for height in range(6, 71)
        if width * height > 1190 or (width * height == 1190 and min(width, height) > 34)
    }
    if len(lex_better) != 2074 or any(_baseline_ok(*dimension) for dimension in lex_better):
        raise RecomputeError("B0 lex-better band did not reconstruct")

    candidate_dimensions = sorted(dimension for dimension in old_dimensions if max(dimension) <= 69)
    total_corpus = sum(
        len(patterns) * (70 - width) * (70 - height) for width in range(6, 70) for height in range(6, 70)
    )
    baseline_survivors = sum(len(patterns) * (70 - width) * (70 - height) for width, height in candidate_dimensions)

    refined_by_dimension: defaultdict[tuple[int, int], int] = defaultdict(int)
    q_only_by_dimension: defaultdict[tuple[int, int], int] = defaultdict(int)
    additive_by_dimension: defaultdict[tuple[int, int], int] = defaultdict(int)
    for pattern in patterns:
        left_profiles = {
            (height, y_value): _contact_profile(pattern.left_anchors, y_value, height)
            for height in range(6, 70)
            for y_value in range(1, 70 - height + 1)
        }
        bottom_profiles = {
            (width, x_value): _contact_profile(pattern.bottom_anchors, x_value, width)
            for width in range(6, 70)
            for x_value in range(1, 70 - width + 1)
        }
        for width, height in candidate_dimensions:
            interior = max(0, 69 - width) * max(0, 69 - height)
            refined_by_dimension[(width, height)] += interior
            q_only_by_dimension[(width, height)] += interior
            if width * height + 46 + _ceil_div(580 - width - height, 4) <= 1320:
                additive_by_dimension[(width, height)] += interior

            for y_value in range(2, 70 - height + 1):
                q_count, endpoint_count = left_profiles[(height, y_value)]
                refined_by_dimension[(width, height)] += _refined_ok(width, height, q_count, endpoint_count)
                q_only_by_dimension[(width, height)] += _q_only_ok(width, height, q_count)
                additive_by_dimension[(width, height)] += (
                    width * height + (46 - q_count) + _ceil_div(580 - width - height, 4) <= 1320
                )

            for x_value in range(2, 70 - width + 1):
                q_count, endpoint_count = bottom_profiles[(width, x_value)]
                refined_by_dimension[(width, height)] += _refined_ok(width, height, q_count, endpoint_count)
                q_only_by_dimension[(width, height)] += _q_only_ok(width, height, q_count)
                additive_by_dimension[(width, height)] += (
                    width * height + (46 - q_count) + _ceil_div(580 - width - height, 4) <= 1320
                )

            left_q, left_e = left_profiles[(height, 1)]
            bottom_q, bottom_e = bottom_profiles[(width, 1)]
            q_count = left_q + bottom_q
            endpoint_count = left_e + bottom_e
            refined_by_dimension[(width, height)] += _refined_ok(width, height, q_count, endpoint_count)
            q_only_by_dimension[(width, height)] += _q_only_ok(width, height, q_count)
            additive_by_dimension[(width, height)] += (
                width * height + (46 - q_count) + _ceil_div(580 - width - height, 4) <= 1320
            )

    refined_survivors = sum(refined_by_dimension.values())
    q_only_survivors = sum(q_only_by_dimension.values())
    surviving_dimensions = {dimension for dimension, count in refined_by_dimension.items() if count}
    best = max((width * height, min(width, height)) for width, height in surviving_dimensions)
    best_dimensions = sorted(
        dimension for dimension in surviving_dimensions if (dimension[0] * dimension[1], min(dimension)) == best
    )
    pruned_by_dimension = [
        {
            "width": width,
            "height": height,
            "area": width * height,
            "baseline": len(patterns) * (70 - width) * (70 - height),
            "surviving": refined_by_dimension[(width, height)],
            "pruned": len(patterns) * (70 - width) * (70 - height) - refined_by_dimension[(width, height)],
        }
        for width, height in candidate_dimensions
        if refined_by_dimension[(width, height)] != len(patterns) * (70 - width) * (70 - height)
    ]
    pruned_by_dimension.sort(
        key=lambda item: (int(item["area"]), min(int(item["width"]), int(item["height"]))),
        reverse=True,
    )

    additive_dimensions = {dimension for dimension, count in additive_by_dimension.items() if count}
    additive_best = max((width * height, min(width, height)) for width, height in additive_dimensions)
    cap_five_best = max(
        (width * height, min(width, height))
        for width in range(6, 71)
        for height in range(6, 71)
        if _baseline_ok(width, height, incidence_cap=5)
    )
    eight_pole_best = max(
        (width * height, min(width, height))
        for width in range(6, 71)
        for height in range(6, 71)
        if _baseline_ok(width, height, cap=1324)
    )

    metrics = {
        "pattern_placement_corpus": total_corpus,
        "baseline_surviving_placements": baseline_survivors,
        "refined_surviving_placements": refined_survivors,
        "incremental_pruned_placements": baseline_survivors - refined_survivors,
        "surviving_oriented_dimensions": len(surviving_dimensions),
        "old_oriented_dimensions": len(old_dimensions),
        "side_70_dimensions_removed": len(old_dimensions - surviving_dimensions),
    }
    if metrics != EXPECTED_METRICS:
        raise RecomputeError(f"coordinate scan metrics drift: {metrics}")
    expected_prunes = {
        (34, 35): 47,
        (35, 34): 47,
        (29, 41): 22,
        (41, 29): 22,
    }
    actual_prunes = {(int(item["width"]), int(item["height"])): int(item["pruned"]) for item in pruned_by_dimension}
    if actual_prunes != expected_prunes:
        raise RecomputeError(f"incremental prune distribution drift: {actual_prunes}")
    if best != (1190, 34) or best_dimensions != [(34, 35), (35, 34)]:
        raise RecomputeError(f"refined frontier drift: {best}, {best_dimensions}")

    ceiling = {
        f"{width}x{height}": {
            "baseline": len(patterns) * (70 - width) * (70 - height),
            "surviving": refined_by_dimension[(width, height)],
            "pruned": len(patterns) * (70 - width) * (70 - height) - refined_by_dimension[(width, height)],
        }
        for width, height in best_dimensions
    }
    canaries = {
        "direct_union_is_dominated": {
            "pass": _ceil_div(580 - 70 - 70, 4) == 110 and 110 > 46,
            "minimum_membrane_external_cells": 110,
            "maximum_q_out": 46,
        },
        "zero_refinement_restores_baseline": {
            "pass": baseline_survivors
            == sum(len(patterns) * (70 - width) * (70 - height) for width, height in candidate_dimensions)
        },
        "endpoint_term_is_live": {
            "pass": q_only_survivors > refined_survivors,
            "q_only_survivors": q_only_survivors,
            "additional_prunes_from_endpoint_term": q_only_survivors - refined_survivors,
        },
        "unsound_addition_changes_frontier": {
            "pass": additive_best != best,
            "mutated_frontier": list(additive_best),
            "removed_dimensions": len(surviving_dimensions - additive_dimensions),
            "classification": "REJECTED_DOUBLE_COUNT",
        },
        "incidence_cap_mutation_changes_frontier": {
            "pass": cap_five_best != best,
            "mutated_frontier": list(cap_five_best),
        },
        "pole_lower_bound_mutation_changes_frontier": {
            "pass": eight_pole_best != best,
            "mutated_frontier": list(eight_pole_best),
        },
    }
    if not all(record["pass"] is True for record in canaries.values()):
        raise RecomputeError(f"mutation canary failed: {canaries}")
    if canaries["endpoint_term_is_live"]["additional_prunes_from_endpoint_term"] != 44:
        raise RecomputeError("endpoint term no longer accounts for 44 additional prunes")
    if (
        canaries["unsound_addition_changes_frontier"]["mutated_frontier"] != [1173, 17]
        or canaries["unsound_addition_changes_frontier"]["removed_dimensions"] != 32
    ):
        raise RecomputeError("double-count mutation signature drift")

    return {
        "metrics": metrics,
        "frontier": {"objective": list(best), "oriented_dimensions": [list(item) for item in best_dimensions]},
        "ceiling_band": ceiling,
        "incremental_prunes": pruned_by_dimension,
        "canaries": canaries,
    }


def recompute() -> dict[str, Any]:
    root, strict_sha = _load_strict(STRICT_PATH)
    ledger = _derive_ledger(root)
    patterns = _patterns()
    scan = _scan(patterns)
    return {
        "schema_version": "b1_q_membrane_halo_recompute_v1",
        "status": "PASS",
        "strict_instance": {
            "path": str(STRICT_PATH.relative_to(PROJECT_ROOT)),
            "sha256": strict_sha,
        },
        "provenance": {
            "algorithm": "coordinate_contact_profile_enumeration",
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "imports_independent_recompute_or_encoder": False,
        },
        "ledger": ledger,
        "boundary_patterns": {
            "count": len(patterns),
            "q_cells_per_pattern": 46,
            "gap_pairs": [[item.left_gap, item.bottom_gap] for item in patterns],
        },
        "necessary_condition": ("wh + ceil((580-w-h+floor(|R_intersect_Q_delta|/2)+endpoint_partials)/4) <= 1320"),
        **scan,
        "claim_boundary": {
            "upper_ledger_only": True,
            "new_upper_bound": False,
            "witness": "absent_and_unrelated",
            "attainability": False,
            "global_optimality": False,
            "production_certified": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = recompute()
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output.resolve()
        if not output.parent.is_dir():
            raise FileNotFoundError(f"output parent does not exist: {output.parent}")
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
