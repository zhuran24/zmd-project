#!/usr/bin/env python3
"""Independent, standard-library validator for a concrete benchmark layout.

This program validates feasibility and recomputes the best empty rectangle for
the submitted layout.  It intentionally does not validate an arbitrary claim
that the layout is globally optimal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


DIRECTIONS = ("N", "E", "S", "W")
DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
OPPOSITE = {"N": "S", "E": "W", "S": "N", "W": "E"}
CATEGORIES = {
    "J": "strict_json",
    "S": "document_shape",
    "I": "instance_integrity",
    "F": "facility_geometry",
    "P": "port_binding",
    "PW": "power",
    "R": "routing",
    "O": "objective",
}

# This validator is intentionally benchmark-specific.  Pinning the exact
# instance bytes prevents a self-consistent replacement instance and witness
# from being mistaken for an evaluation of the released benchmark.
EXPECTED_INSTANCE_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"


@dataclass(frozen=True)
class Issue:
    category: str
    pointer: str
    message: str


class ContractError(ValueError):
    def __init__(self, issue: Issue):
        super().__init__(issue.message)
        self.issue = issue


def _fail(category: str, pointer: str, message: str) -> None:
    raise ContractError(Issue(category, pointer, message))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("J", "/", f"duplicate object key: {key!r}")
        result[key] = value
    return result


def strict_json_loads(payload: bytes, *, label: str) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        _fail("J", "/", f"{label} is not UTF-8: {exc}")

    def reject_constant(token: str) -> None:
        _fail("J", "/", f"non-finite JSON number is forbidden: {token}")

    try:
        return json.loads(text, object_pairs_hook=_strict_object, parse_constant=reject_constant)
    except ContractError:
        raise
    except json.JSONDecodeError as exc:
        _fail("J", "/", f"{label} JSON syntax error at line {exc.lineno}, column {exc.colno}")


def _object(value: Any, pointer: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("S", pointer, "expected object")
    return value


def _array(value: Any, pointer: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("S", pointer, "expected array")
    return value


def _string(value: Any, pointer: str) -> str:
    if not isinstance(value, str):
        _fail("S", pointer, "expected string")
    return value


def _nonempty_string(value: Any, pointer: str) -> str:
    result = _string(value, pointer)
    if not result:
        _fail("S", pointer, "expected non-empty string")
    return result


def _integer(value: Any, pointer: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("S", pointer, "expected integer (booleans are not integers)")
    if minimum is not None and value < minimum:
        _fail("S", pointer, f"expected integer >= {minimum}")
    return value


def _boolean(value: Any, pointer: str) -> bool:
    if not isinstance(value, bool):
        _fail("S", pointer, "expected boolean")
    return value


def _keys(value: dict[str, Any], required: Iterable[str], optional: Iterable[str], pointer: str) -> None:
    required_set = set(required)
    allowed = required_set | set(optional)
    missing = sorted(required_set - value.keys())
    unknown = sorted(value.keys() - allowed)
    if missing:
        _fail("S", pointer, "missing fields: " + ", ".join(missing))
    if unknown:
        _fail("S", pointer, "unknown fields: " + ", ".join(unknown))


def _coord(value: Any, pointer: str) -> tuple[int, int]:
    obj = _object(value, pointer)
    _keys(obj, ("x", "y"), (), pointer)
    return _integer(obj["x"], pointer + "/x"), _integer(obj["y"], pointer + "/y")


def parse_instance(value: Any) -> dict[str, Any]:
    root = _object(value, "/")
    fields = (
        "schema_version", "benchmark_id", "coordinate_system", "grid", "objective", "commodities",
        "facility_templates", "operation_groups", "required_instances", "generic_requirements",
        "repeatable_auxiliaries", "routing", "power", "sentinels",
    )
    _keys(root, fields, (), "/")
    _integer(root["schema_version"], "/schema_version", minimum=1)
    _string(root["benchmark_id"], "/benchmark_id")

    coordinates = _object(root["coordinate_system"], "/coordinate_system")
    _keys(coordinates, ("origin", "indexing", "x_positive", "y_positive", "directions"), (), "/coordinate_system")
    for key in ("origin", "indexing", "x_positive", "y_positive"):
        _string(coordinates[key], f"/coordinate_system/{key}")
    for index, direction in enumerate(_array(coordinates["directions"], "/coordinate_system/directions")):
        _string(direction, f"/coordinate_system/directions/{index}")

    grid = _object(root["grid"], "/grid")
    _keys(grid, ("width", "height"), (), "/grid")
    _integer(grid["width"], "/grid/width", minimum=1)
    _integer(grid["height"], "/grid/height", minimum=1)

    objective = _object(root["objective"], "/objective")
    _keys(objective, ("kind", "minimum_side", "body_cells_only"), (), "/objective")
    _string(objective["kind"], "/objective/kind")
    _integer(objective["minimum_side"], "/objective/minimum_side", minimum=1)
    _boolean(objective["body_cells_only"], "/objective/body_cells_only")

    for index, commodity in enumerate(_array(root["commodities"], "/commodities")):
        _string(commodity, f"/commodities/{index}")

    templates = _object(root["facility_templates"], "/facility_templates")
    for template_id, raw_template in templates.items():
        _string(template_id, "/facility_templates")
        pointer = f"/facility_templates/{template_id}"
        template = _object(raw_template, pointer)
        _keys(template, ("requires_power", "placement_rule", "modes"), (), pointer)
        _boolean(template["requires_power"], pointer + "/requires_power")
        _string(template["placement_rule"], pointer + "/placement_rule")
        for mode_index, raw_mode in enumerate(_array(template["modes"], pointer + "/modes")):
            mp = f"{pointer}/modes/{mode_index}"
            mode = _object(raw_mode, mp)
            _keys(mode, ("id", "body", "ports"), (), mp)
            _string(mode["id"], mp + "/id")
            body = _object(mode["body"], mp + "/body")
            _keys(body, ("width", "height"), (), mp + "/body")
            _integer(body["width"], mp + "/body/width", minimum=1)
            _integer(body["height"], mp + "/body/height", minimum=1)
            for port_index, raw_port in enumerate(_array(mode["ports"], mp + "/ports")):
                pp = f"{mp}/ports/{port_index}"
                port = _object(raw_port, pp)
                _keys(port, ("id", "kind", "body_cell", "direction"), (), pp)
                _string(port["id"], pp + "/id")
                _string(port["kind"], pp + "/kind")
                _coord(port["body_cell"], pp + "/body_cell")
                _string(port["direction"], pp + "/direction")

    for group_index, raw_group in enumerate(_array(root["operation_groups"], "/operation_groups")):
        pointer = f"/operation_groups/{group_index}"
        group = _object(raw_group, pointer)
        _keys(group, ("id", "template", "count", "port_needs", "instance_ids"), (), pointer)
        _string(group["id"], pointer + "/id")
        _string(group["template"], pointer + "/template")
        _integer(group["count"], pointer + "/count", minimum=1)
        needs = _object(group["port_needs"], pointer + "/port_needs")
        _keys(needs, ("inputs", "outputs"), (), pointer + "/port_needs")
        for kind in ("inputs", "outputs"):
            need_map = _object(needs[kind], f"{pointer}/port_needs/{kind}")
            for commodity, count in need_map.items():
                _string(commodity, f"{pointer}/port_needs/{kind}")
                _integer(count, f"{pointer}/port_needs/{kind}/{commodity}", minimum=1)
        for item_index, instance_id in enumerate(_array(group["instance_ids"], pointer + "/instance_ids")):
            _string(instance_id, f"{pointer}/instance_ids/{item_index}")

    for index, raw_required in enumerate(_array(root["required_instances"], "/required_instances")):
        pointer = f"/required_instances/{index}"
        required = _object(raw_required, pointer)
        _keys(required, ("id", "template", "operation"), (), pointer)
        for key in ("id", "template", "operation"):
            _string(required[key], f"{pointer}/{key}")

    generic = _object(root["generic_requirements"], "/generic_requirements")
    _keys(generic, ("raw_outputs", "final_inputs", "raw_output_providers", "final_input_providers"), (), "/generic_requirements")
    for key in ("raw_outputs", "final_inputs"):
        mapping = _object(generic[key], f"/generic_requirements/{key}")
        for commodity, count in mapping.items():
            _string(commodity, f"/generic_requirements/{key}")
            _integer(count, f"/generic_requirements/{key}/{commodity}", minimum=1)
    for key in ("raw_output_providers", "final_input_providers"):
        for index, item in enumerate(_array(generic[key], f"/generic_requirements/{key}")):
            _string(item, f"/generic_requirements/{key}/{index}")

    for index, auxiliary in enumerate(_array(root["repeatable_auxiliaries"], "/repeatable_auxiliaries")):
        _string(auxiliary, f"/repeatable_auxiliaries/{index}")

    routing = _object(root["routing"], "/routing")
    routing_fields = (
        "component_kinds", "component_cells_must_avoid_bodies", "multi_commodity_sharing",
        "terminal_output_requires_component_input", "terminal_input_requires_component_output",
        "compatible_terminals_share_component", "crossing", "connectivity", "throughput_in_scope",
    )
    _keys(routing, routing_fields, (), "/routing")
    for index, kind in enumerate(_array(routing["component_kinds"], "/routing/component_kinds")):
        _string(kind, f"/routing/component_kinds/{index}")
    for key in ("component_cells_must_avoid_bodies", "multi_commodity_sharing", "compatible_terminals_share_component", "throughput_in_scope"):
        _boolean(routing[key], f"/routing/{key}")
    for key in ("terminal_output_requires_component_input", "terminal_input_requires_component_output", "crossing", "connectivity"):
        _string(routing[key], f"/routing/{key}")

    power = _object(root["power"], "/power")
    _keys(power, ("pole_template", "coverage_from_pole_anchor", "required_rule"), (), "/power")
    _string(power["pole_template"], "/power/pole_template")
    _string(power["required_rule"], "/power/required_rule")
    coverage = _object(power["coverage_from_pole_anchor"], "/power/coverage_from_pole_anchor")
    offsets = ("x_min_offset", "x_max_offset", "y_min_offset", "y_max_offset")
    _keys(coverage, offsets, (), "/power/coverage_from_pole_anchor")
    for key in offsets:
        _integer(coverage[key], f"/power/coverage_from_pole_anchor/{key}")

    sentinels = _object(root["sentinels"], "/sentinels")
    sentinel_fields = (
        "commodity_count", "operation_group_count", "manufacturing_instance_count", "required_instance_count",
        "required_body_area", "manufacturing_input_terminals", "manufacturing_output_terminals",
        "generic_raw_output_terminals", "generic_final_input_terminals", "total_active_terminals",
    )
    _keys(sentinels, sentinel_fields, (), "/sentinels")
    for key in sentinel_fields:
        _integer(sentinels[key], f"/sentinels/{key}", minimum=0)
    return root


def parse_witness(value: Any) -> dict[str, Any]:
    root = _object(value, "/")
    fields = ("schema_version", "instance_digest", "required_placements", "optional_placements", "route_components", "claimed_objective")
    _keys(root, fields, (), "/")
    _integer(root["schema_version"], "/schema_version", minimum=1)
    instance_digest = _string(root["instance_digest"], "/instance_digest")
    if (
        len(instance_digest) != 71
        or not instance_digest.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in instance_digest[7:])
    ):
        _fail("S", "/instance_digest", "expected sha256:<64 lowercase hex digits>")
    for field in ("required_placements", "optional_placements"):
        for index, raw_placement in enumerate(_array(root[field], f"/{field}")):
            pointer = f"/{field}/{index}"
            placement = _object(raw_placement, pointer)
            _keys(placement, ("instance_id", "template", "mode", "anchor", "port_bindings"), (), pointer)
            for key in ("instance_id", "template", "mode"):
                _nonempty_string(placement[key], f"{pointer}/{key}")
            _coord(placement["anchor"], pointer + "/anchor")
            bindings = _object(placement["port_bindings"], pointer + "/port_bindings")
            for port_id, commodity in bindings.items():
                _nonempty_string(port_id, pointer + "/port_bindings")
                if commodity is not None:
                    _string(commodity, f"{pointer}/port_bindings/{port_id}")

    for index, raw_component in enumerate(_array(root["route_components"], "/route_components")):
        pointer = f"/route_components/{index}"
        component = _object(raw_component, pointer)
        kind = _string(component.get("kind"), pointer + "/kind")
        if kind == "cross":
            _keys(component, ("cell", "kind", "channels"), (), pointer)
            _coord(component["cell"], pointer + "/cell")
            for channel_index, raw_channel in enumerate(_array(component["channels"], pointer + "/channels")):
                cp = f"{pointer}/channels/{channel_index}"
                channel = _object(raw_channel, cp)
                _keys(channel, ("inputs", "outputs", "commodities"), (), cp)
                _direction_list(channel["inputs"], cp + "/inputs")
                _direction_list(channel["outputs"], cp + "/outputs")
                _string_list(channel["commodities"], cp + "/commodities")
        else:
            _keys(component, ("cell", "kind", "inputs", "outputs", "commodities"), (), pointer)
            _coord(component["cell"], pointer + "/cell")
            _direction_list(component["inputs"], pointer + "/inputs")
            _direction_list(component["outputs"], pointer + "/outputs")
            _string_list(component["commodities"], pointer + "/commodities")

    objective = _object(root["claimed_objective"], "/claimed_objective")
    _keys(objective, ("rectangle", "area", "min_side"), (), "/claimed_objective")
    rectangle = _object(objective["rectangle"], "/claimed_objective/rectangle")
    _keys(rectangle, ("x", "y", "width", "height"), (), "/claimed_objective/rectangle")
    for key in ("x", "y"):
        _integer(rectangle[key], f"/claimed_objective/rectangle/{key}")
    for key in ("width", "height"):
        _integer(rectangle[key], f"/claimed_objective/rectangle/{key}", minimum=1)
    _integer(objective["area"], "/claimed_objective/area", minimum=0)
    _integer(objective["min_side"], "/claimed_objective/min_side", minimum=0)
    return root


def _direction_list(value: Any, pointer: str) -> list[str]:
    result = []
    for index, item in enumerate(_array(value, pointer)):
        result.append(_string(item, f"{pointer}/{index}"))
    return result


def _string_list(value: Any, pointer: str) -> list[str]:
    return _direction_list(value, pointer)


def _issue(issues: list[Issue], category: str, pointer: str, message: str) -> None:
    issues.append(Issue(category, pointer, message))


def _unique(values: list[Any]) -> bool:
    return len(values) == len(set(values))


def validate_instance(instance: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if instance["schema_version"] != 1:
        _issue(issues, "I", "/schema_version", "unsupported schema version")
    if instance["benchmark_id"] != "factory_layout_optimality_benchmark_v1":
        _issue(issues, "I", "/benchmark_id", "unexpected benchmark identifier")
    if instance["coordinate_system"] != {
        "origin": "southwest", "indexing": "zero_based", "x_positive": "east", "y_positive": "north", "directions": list(DIRECTIONS)
    }:
        _issue(issues, "I", "/coordinate_system", "coordinate contract differs from the benchmark")
    if instance["objective"] != {"kind": "max_lex_area_min_side", "minimum_side": 6, "body_cells_only": True}:
        _issue(issues, "I", "/objective", "objective contract differs from the benchmark")

    commodities = instance["commodities"]
    commodity_set = set(commodities)
    if not _unique(commodities):
        _issue(issues, "I", "/commodities", "commodity identifiers must be unique")

    templates = instance["facility_templates"]
    mode_areas: dict[str, int] = {}
    for template_id, template in templates.items():
        modes = template["modes"]
        mode_ids = [mode["id"] for mode in modes]
        if not modes or not _unique(mode_ids):
            _issue(issues, "I", f"/facility_templates/{template_id}/modes", "mode identifiers must be nonempty and unique")
            continue
        areas = set()
        for mode_index, mode in enumerate(modes):
            pointer = f"/facility_templates/{template_id}/modes/{mode_index}"
            width, height = mode["body"]["width"], mode["body"]["height"]
            areas.add(width * height)
            port_ids = [port["id"] for port in mode["ports"]]
            if not _unique(port_ids):
                _issue(issues, "I", pointer + "/ports", "port identifiers must be unique within a mode")
            for port_index, port in enumerate(mode["ports"]):
                pp = f"{pointer}/ports/{port_index}"
                x, y = port["body_cell"]["x"], port["body_cell"]["y"]
                direction = port["direction"]
                if port["kind"] not in ("input", "output"):
                    _issue(issues, "I", pp + "/kind", "port kind must be input or output")
                if direction not in DIRECTIONS:
                    _issue(issues, "I", pp + "/direction", "invalid direction")
                outward = (
                    (direction == "N" and y == height - 1 and 0 <= x < width)
                    or (direction == "S" and y == 0 and 0 <= x < width)
                    or (direction == "E" and x == width - 1 and 0 <= y < height)
                    or (direction == "W" and x == 0 and 0 <= y < height)
                )
                if not outward:
                    _issue(issues, "I", pp, "port body cell and direction are not outward-facing")
        if len(areas) != 1:
            _issue(issues, "I", f"/facility_templates/{template_id}/modes", "all modes of a template must have equal body area")
        else:
            mode_areas[template_id] = next(iter(areas))

    group_by_id: dict[str, dict[str, Any]] = {}
    group_instances: set[str] = set()
    manufacturing_count = input_terminals = output_terminals = 0
    for index, group in enumerate(instance["operation_groups"]):
        pointer = f"/operation_groups/{index}"
        group_id = group["id"]
        if group_id in group_by_id:
            _issue(issues, "I", pointer + "/id", "duplicate operation group")
        group_by_id[group_id] = group
        if group["template"] not in templates:
            _issue(issues, "I", pointer + "/template", "unknown template")
            continue
        ids = group["instance_ids"]
        if len(ids) != group["count"] or not _unique(ids):
            _issue(issues, "I", pointer + "/instance_ids", "instance identifiers must be unique and match count")
        duplicates = group_instances.intersection(ids)
        if duplicates:
            _issue(issues, "I", pointer + "/instance_ids", "instance identifier appears in multiple operation groups")
        group_instances.update(ids)
        needed_in = sum(group["port_needs"]["inputs"].values())
        needed_out = sum(group["port_needs"]["outputs"].values())
        for kind in ("inputs", "outputs"):
            if not set(group["port_needs"][kind]).issubset(commodity_set):
                _issue(issues, "I", pointer + f"/port_needs/{kind}", "unknown commodity in port needs")
        for mode_index, mode in enumerate(templates[group["template"]]["modes"]):
            available_in = sum(port["kind"] == "input" for port in mode["ports"])
            available_out = sum(port["kind"] == "output" for port in mode["ports"])
            if needed_in > available_in or needed_out > available_out:
                _issue(issues, "I", f"{pointer}/port_needs", f"needs exceed physical ports in mode {mode_index}")
        manufacturing_count += group["count"]
        input_terminals += group["count"] * needed_in
        output_terminals += group["count"] * needed_out

    required_by_id: dict[str, dict[str, Any]] = {}
    for index, required in enumerate(instance["required_instances"]):
        required_id = required["id"]
        if required_id in required_by_id:
            _issue(issues, "I", f"/required_instances/{index}/id", "duplicate required instance")
        required_by_id[required_id] = required
        if required["template"] not in templates:
            _issue(issues, "I", f"/required_instances/{index}/template", "unknown template")
        if required["operation"] in group_by_id:
            group = group_by_id[required["operation"]]
            if required_id not in group["instance_ids"] or required["template"] != group["template"]:
                _issue(issues, "I", f"/required_instances/{index}", "operation instance mapping is inconsistent")
    if not group_instances.issubset(required_by_id):
        _issue(issues, "I", "/required_instances", "manufacturing instance is missing from required list")

    generic = instance["generic_requirements"]
    generic_raw = sum(generic["raw_outputs"].values())
    generic_final = sum(generic["final_inputs"].values())
    for key in ("raw_outputs", "final_inputs"):
        if not set(generic[key]).issubset(commodity_set):
            _issue(issues, "I", f"/generic_requirements/{key}", "unknown generic commodity")
    auxiliaries = instance["repeatable_auxiliaries"]
    if not _unique(auxiliaries) or not set(auxiliaries).issubset(templates):
        _issue(issues, "I", "/repeatable_auxiliaries", "auxiliary templates must be unique and defined")

    expected = {
        "commodity_count": len(commodities),
        "operation_group_count": len(group_by_id),
        "manufacturing_instance_count": manufacturing_count,
        "required_instance_count": len(required_by_id),
        "required_body_area": sum(mode_areas.get(required["template"], 0) for required in required_by_id.values()),
        "manufacturing_input_terminals": input_terminals,
        "manufacturing_output_terminals": output_terminals,
        "generic_raw_output_terminals": generic_raw,
        "generic_final_input_terminals": generic_final,
        "total_active_terminals": input_terminals + output_terminals + generic_raw + generic_final,
    }
    for key, value in expected.items():
        if instance["sentinels"][key] != value:
            _issue(issues, "I", f"/sentinels/{key}", f"expected recomputed value {value}")
    return issues


@dataclass
class Terminal:
    instance_id: str
    port_id: str
    kind: str
    commodity: str
    access: tuple[int, int]
    direction: str
    pointer: str


@dataclass
class Placed:
    instance_id: str
    template_id: str
    mode: dict[str, Any]
    anchor: tuple[int, int]
    body_cells: set[tuple[int, int]]
    bindings: dict[str, str | None]
    pointer: str


@dataclass(frozen=True)
class Lane:
    node: tuple[int, int]
    cell: tuple[int, int]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    commodities: frozenset[str]


def _mode_index(instance: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (template_id, mode["id"]): mode
        for template_id, template in instance["facility_templates"].items()
        for mode in template["modes"]
    }


def _reachable(graph: dict[tuple[int, int], set[tuple[int, int]]], start: tuple[int, int]) -> set[tuple[int, int]]:
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in graph.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _best_empty_rectangle(width: int, height: int, occupied: set[tuple[int, int]], minimum_side: int) -> dict[str, int]:
    heights = [0] * width
    best = {"x": 0, "y": 0, "width": 0, "height": 0, "area": 0, "min_side": 0}
    best_key = (0, 0, 0, 0, 0, 0)
    for y in range(height):
        for x in range(width):
            heights[x] = 0 if (x, y) in occupied else heights[x] + 1
        stack: list[tuple[int, int]] = []
        for x in range(width + 1):
            current = heights[x] if x < width else 0
            start = x
            while stack and stack[-1][1] > current:
                left, rect_height = stack.pop()
                rect_width = x - left
                start = left
                if rect_width >= minimum_side and rect_height >= minimum_side:
                    area = rect_width * rect_height
                    min_side = min(rect_width, rect_height)
                    bottom = y - rect_height + 1
                    key = (area, min_side, -bottom, -left, rect_width, rect_height)
                    if key > best_key:
                        best_key = key
                        best = {
                            "x": left, "y": bottom, "width": rect_width, "height": rect_height,
                            "area": area, "min_side": min_side,
                        }
            if not stack or stack[-1][1] < current:
                stack.append((start, current))
    return best


def validate_layout(instance: dict[str, Any], witness: dict[str, Any], instance_digest: str) -> tuple[list[Issue], dict[str, int] | None]:
    issues = validate_instance(instance)
    if issues:
        return issues, None
    if witness["schema_version"] != 1:
        _issue(issues, "I", "/schema_version", "unsupported witness schema version")
    if witness["instance_digest"] != instance_digest:
        _issue(issues, "I", "/instance_digest", f"expected {instance_digest}")

    templates = instance["facility_templates"]
    modes = _mode_index(instance)
    required_by_id = {record["id"]: record for record in instance["required_instances"]}
    groups = {group["id"]: group for group in instance["operation_groups"]}
    commodities = set(instance["commodities"])
    repeatable = set(instance["repeatable_auxiliaries"])
    width, height = instance["grid"]["width"], instance["grid"]["height"]

    placed: list[Placed] = []
    seen_ids: set[str] = set()
    required_seen: set[str] = set()
    all_body_cells: set[tuple[int, int]] = set()
    owner_by_cell: dict[tuple[int, int], str] = {}

    for field, is_required in (("required_placements", True), ("optional_placements", False)):
        for index, placement in enumerate(witness[field]):
            pointer = f"/{field}/{index}"
            instance_id = placement["instance_id"]
            template_id = placement["template"]
            if instance_id in seen_ids:
                _issue(issues, "F", pointer + "/instance_id", "duplicate placement instance identifier")
                continue
            seen_ids.add(instance_id)
            if is_required:
                required_seen.add(instance_id)
                required = required_by_id.get(instance_id)
                if required is None:
                    _issue(issues, "F", pointer + "/instance_id", "identifier is not required")
                    continue
                if template_id != required["template"]:
                    _issue(issues, "F", pointer + "/template", "template differs from required instance")
            elif instance_id in required_by_id or template_id not in repeatable:
                _issue(issues, "F", pointer, "optional placement must have a new identifier and repeatable template")
                continue
            if template_id not in templates:
                _issue(issues, "F", pointer + "/template", "unknown template")
                continue
            mode = modes.get((template_id, placement["mode"]))
            if mode is None:
                _issue(issues, "F", pointer + "/mode", "unknown mode for template")
                continue
            anchor = (placement["anchor"]["x"], placement["anchor"]["y"])
            body_width, body_height = mode["body"]["width"], mode["body"]["height"]
            body_cells = {
                (anchor[0] + dx, anchor[1] + dy)
                for dx in range(body_width)
                for dy in range(body_height)
            }
            if any(not (0 <= x < width and 0 <= y < height) for x, y in body_cells):
                _issue(issues, "F", pointer + "/anchor", "facility body leaves the grid")
            rule = templates[template_id]["placement_rule"]
            if rule == "matching_map_boundary":
                valid = (placement["mode"] == "left_boundary" and anchor[0] == 0) or (
                    placement["mode"] == "bottom_boundary" and anchor[1] == 0
                )
                if not valid:
                    _issue(issues, "F", pointer + "/anchor", "boundary facility is not on the boundary matching its mode")
            for cell in body_cells:
                if cell in owner_by_cell:
                    _issue(issues, "F", pointer + "/anchor", f"body overlaps {owner_by_cell[cell]!r} at {cell}")
                else:
                    owner_by_cell[cell] = instance_id
            all_body_cells.update(body_cells)
            expected_ports = {port["id"] for port in mode["ports"]}
            actual_ports = set(placement["port_bindings"])
            if actual_ports != expected_ports:
                missing = sorted(expected_ports - actual_ports)
                extra = sorted(actual_ports - expected_ports)
                _issue(issues, "P", pointer + "/port_bindings", f"bindings must be complete; missing={missing}, extra={extra}")
            placed.append(Placed(instance_id, template_id, mode, anchor, body_cells, placement["port_bindings"], pointer))

    missing_required = sorted(set(required_by_id) - required_seen)
    if missing_required:
        _issue(issues, "F", "/required_placements", f"missing required instances: {missing_required[:5]}" + (" ..." if len(missing_required) > 5 else ""))

    terminals: list[Terminal] = []
    raw_counts: defaultdict[str, int] = defaultdict(int)
    final_counts: defaultdict[str, int] = defaultdict(int)
    for facility in placed:
        required = required_by_id.get(facility.instance_id)
        operation = required["operation"] if required else None
        bound_by_kind: dict[str, defaultdict[str, int]] = {"input": defaultdict(int), "output": defaultdict(int)}
        for port_index, port in enumerate(facility.mode["ports"]):
            port_id = port["id"]
            commodity = facility.bindings.get(port_id)
            if commodity is None:
                continue
            pointer = facility.pointer + f"/port_bindings/{port_id}"
            if commodity not in commodities:
                _issue(issues, "P", pointer, "unknown commodity")
                continue
            bound_by_kind[port["kind"]][commodity] += 1
            dx, dy = DELTA.get(port["direction"], (0, 0))
            access = (
                facility.anchor[0] + port["body_cell"]["x"] + dx,
                facility.anchor[1] + port["body_cell"]["y"] + dy,
            )
            if not (0 <= access[0] < width and 0 <= access[1] < height):
                _issue(issues, "P", pointer, f"active port access cell is outside grid: {access}")
            elif access in all_body_cells:
                _issue(issues, "P", pointer, f"active port access cell is occupied by a facility body: {access}")
            terminals.append(Terminal(facility.instance_id, port_id, port["kind"], commodity, access, port["direction"], pointer))

        if operation in groups:
            group = groups[operation]
            expected_input = group["port_needs"]["inputs"]
            expected_output = group["port_needs"]["outputs"]
            if dict(bound_by_kind["input"]) != expected_input:
                _issue(issues, "P", facility.pointer + "/port_bindings", f"input bindings must equal {expected_input}")
            if dict(bound_by_kind["output"]) != expected_output:
                _issue(issues, "P", facility.pointer + "/port_bindings", f"output bindings must equal {expected_output}")
        elif facility.template_id in instance["generic_requirements"]["raw_output_providers"]:
            for commodity, count in bound_by_kind["output"].items():
                raw_counts[commodity] += count
            if facility.template_id == "boundary_storage_port" and bound_by_kind["input"]:
                _issue(issues, "P", facility.pointer + "/port_bindings", "boundary provider has no active inputs")
            for commodity, count in bound_by_kind["input"].items():
                final_counts[commodity] += count
        elif facility.template_id == "storage_box":
            for commodity, count in bound_by_kind["input"].items():
                final_counts[commodity] += count
            if bound_by_kind["output"]:
                _issue(issues, "P", facility.pointer + "/port_bindings", "storage-box outputs must remain inactive")

    if dict(raw_counts) != instance["generic_requirements"]["raw_outputs"]:
        _issue(issues, "P", "/required_placements", f"generic raw outputs must equal {instance['generic_requirements']['raw_outputs']}")
    if dict(final_counts) != instance["generic_requirements"]["final_inputs"]:
        _issue(issues, "P", "/required_placements", f"generic final inputs must equal {instance['generic_requirements']['final_inputs']}")

    poles = [facility for facility in placed if facility.template_id == instance["power"]["pole_template"]]
    coverage = instance["power"]["coverage_from_pole_anchor"]
    for facility in placed:
        if not templates[facility.template_id]["requires_power"]:
            continue
        powered = any(
            any(
                pole.anchor[0] + coverage["x_min_offset"] <= x <= pole.anchor[0] + coverage["x_max_offset"]
                and pole.anchor[1] + coverage["y_min_offset"] <= y <= pole.anchor[1] + coverage["y_max_offset"]
                for x, y in facility.body_cells
            )
            for pole in poles
        )
        if not powered:
            _issue(issues, "PW", facility.pointer, "powered facility has no body cell covered by a power pole")

    lanes: list[Lane] = []
    lanes_by_cell: defaultdict[tuple[int, int], list[Lane]] = defaultdict(list)
    route_cells: set[tuple[int, int]] = set()
    for index, component in enumerate(witness["route_components"]):
        pointer = f"/route_components/{index}"
        cell = (component["cell"]["x"], component["cell"]["y"])
        if not (0 <= cell[0] < width and 0 <= cell[1] < height):
            _issue(issues, "R", pointer + "/cell", "route component leaves the grid")
        if cell in all_body_cells:
            _issue(issues, "R", pointer + "/cell", "route component overlaps a facility body")
        if cell in route_cells:
            _issue(issues, "R", pointer + "/cell", "more than one route component occupies the cell")
        route_cells.add(cell)
        kind = component["kind"]
        if kind == "cross":
            channels = component["channels"]
            if len(channels) != 2:
                _issue(issues, "R", pointer + "/channels", "cross requires exactly two channels")
            axes: list[frozenset[str]] = []
            for channel_index, channel in enumerate(channels):
                inputs, outputs = channel["inputs"], channel["outputs"]
                cp = f"{pointer}/channels/{channel_index}"
                if len(inputs) != 1 or len(outputs) != 1 or outputs[0] != OPPOSITE.get(inputs[0]):
                    _issue(issues, "R", cp, "cross channel must be straight with one input and opposite output")
                directions = inputs + outputs
                if any(direction not in DIRECTIONS for direction in directions) or not _unique(directions):
                    _issue(issues, "R", cp, "cross-channel directions must be valid and unique")
                channel_commodities = channel["commodities"]
                if (
                    not channel_commodities
                    or not _unique(channel_commodities)
                    or not set(channel_commodities).issubset(commodities)
                ):
                    _issue(issues, "R", cp + "/commodities", "commodities must be a nonempty unique subset of the instance")
                axes.append(frozenset(inputs + outputs))
                lane = Lane((index, channel_index), cell, tuple(inputs), tuple(outputs), frozenset(channel_commodities))
                lanes.append(lane)
                lanes_by_cell[cell].append(lane)
            if len(axes) == 2 and axes[0] == axes[1]:
                _issue(issues, "R", pointer + "/channels", "cross channels must be perpendicular")
        else:
            inputs, outputs = component["inputs"], component["outputs"]
            valid = kind in ("straight", "turn", "splitter", "merger")
            if not valid:
                _issue(issues, "R", pointer + "/kind", "unknown route component kind")
            elif kind == "straight" and not (len(inputs) == len(outputs) == 1 and outputs[0] == OPPOSITE.get(inputs[0])):
                _issue(issues, "R", pointer, "straight requires one input and opposite output")
            elif kind == "turn" and not (len(inputs) == len(outputs) == 1 and inputs[0] != outputs[0] and outputs[0] != OPPOSITE.get(inputs[0])):
                _issue(issues, "R", pointer, "turn requires one input and one perpendicular output")
            elif kind == "splitter" and not (len(inputs) == 1 and len(outputs) in (2, 3) and inputs[0] not in outputs):
                _issue(issues, "R", pointer, "splitter requires one input and two or three other outputs")
            elif kind == "merger" and not (len(outputs) == 1 and len(inputs) in (2, 3) and outputs[0] not in inputs):
                _issue(issues, "R", pointer, "merger requires two or three inputs and one other output")
            directions = inputs + outputs
            if any(direction not in DIRECTIONS for direction in directions) or not _unique(directions):
                _issue(issues, "R", pointer, "component directions must be valid and unique")
            component_commodities = component["commodities"]
            if not component_commodities or not _unique(component_commodities) or not set(component_commodities).issubset(commodities):
                _issue(issues, "R", pointer + "/commodities", "commodities must be a nonempty unique subset of the instance")
            lane = Lane((index, 0), cell, tuple(inputs), tuple(outputs), frozenset(component_commodities))
            lanes.append(lane)
            lanes_by_cell[cell].append(lane)

    source_nodes: defaultdict[str, list[tuple[Terminal, tuple[int, int]]]] = defaultdict(list)
    sink_nodes: defaultdict[str, list[tuple[Terminal, tuple[int, int]]]] = defaultdict(list)
    for terminal in terminals:
        required_direction = OPPOSITE[terminal.direction]
        candidates = [
            lane
            for lane in lanes_by_cell.get(terminal.access, ())
            if terminal.commodity in lane.commodities
            and required_direction in (lane.inputs if terminal.kind == "output" else lane.outputs)
        ]
        if not candidates:
            _issue(issues, "R", terminal.pointer, "active terminal has no direction-compatible route component")
            continue
        target = source_nodes if terminal.kind == "output" else sink_nodes
        target[terminal.commodity].extend((terminal, lane.node) for lane in candidates)

    graphs: dict[str, dict[tuple[int, int], set[tuple[int, int]]]] = {}
    for commodity in commodities:
        graph: defaultdict[tuple[int, int], set[tuple[int, int]]] = defaultdict(set)
        commodity_lanes = [lane for lane in lanes if commodity in lane.commodities]
        for lane in commodity_lanes:
            for direction in lane.outputs:
                dx, dy = DELTA[direction]
                neighbor_cell = (lane.cell[0] + dx, lane.cell[1] + dy)
                for neighbor in lanes_by_cell.get(neighbor_cell, ()):
                    if commodity in neighbor.commodities and OPPOSITE[direction] in neighbor.inputs:
                        graph[lane.node].add(neighbor.node)
        graphs[commodity] = graph

    for commodity in commodities:
        sources = source_nodes.get(commodity, [])
        sinks = sink_nodes.get(commodity, [])
        sink_node_set = {node for _, node in sinks}
        for terminal, node in sources:
            if not (_reachable(graphs[commodity], node) & sink_node_set):
                _issue(issues, "R", terminal.pointer, "active output cannot reach an active input of the same commodity")
        reachable_from_sources: set[tuple[int, int]] = set()
        for _, node in sources:
            reachable_from_sources.update(_reachable(graphs[commodity], node))
        for terminal, node in sinks:
            if node not in reachable_from_sources:
                _issue(issues, "R", terminal.pointer, "active input is not reached by an active output of the same commodity")

    minimum_side = instance["objective"]["minimum_side"]
    best = _best_empty_rectangle(width, height, all_body_cells, minimum_side)
    claimed = witness["claimed_objective"]
    rectangle = claimed["rectangle"]
    rect_x = rectangle["x"]
    rect_y = rectangle["y"]
    rect_width = rectangle["width"]
    rect_height = rectangle["height"]
    rectangle_in_grid = (
        0 <= rect_x < width
        and 0 <= rect_y < height
        and rect_width <= width - rect_x
        and rect_height <= height - rect_y
    )
    if not rectangle_in_grid:
        _issue(issues, "O", "/claimed_objective/rectangle", "claimed rectangle leaves the grid")
    else:
        claimed_cells = {
            (x, y)
            for x in range(rect_x, rect_x + rect_width)
            for y in range(rect_y, rect_y + rect_height)
        }
        if claimed_cells & all_body_cells:
            _issue(issues, "O", "/claimed_objective/rectangle", "claimed rectangle contains a facility body cell")
        expected_area = rect_width * rect_height
        expected_min_side = min(rect_width, rect_height)
        if expected_min_side < minimum_side:
            _issue(issues, "O", "/claimed_objective/rectangle", "claimed rectangle is inadmissibly narrow")
        if claimed["area"] != expected_area or claimed["min_side"] != expected_min_side:
            _issue(issues, "O", "/claimed_objective", "claimed score does not match rectangle dimensions")
    if (claimed["area"], claimed["min_side"]) != (best["area"], best["min_side"]):
        _issue(issues, "O", "/claimed_objective", f"claimed score is not the recomputed layout score {(best['area'], best['min_side'])}")
    return issues, best


def _report(status: str, issues: list[Issue], objective: dict[str, int] | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": status,
        "categories": CATEGORIES,
        "errors": [asdict(issue) for issue in issues],
    }
    if objective is not None:
        report["recomputed_objective"] = objective
    return report


def validate_bytes(
    instance_payload: bytes,
    witness_payload: bytes,
    *,
    expected_instance_sha256: str = EXPECTED_INSTANCE_SHA256,
) -> tuple[dict[str, Any], int]:
    actual_instance_sha256 = hashlib.sha256(instance_payload).hexdigest()
    if actual_instance_sha256 != expected_instance_sha256:
        return _report(
            "CONTRACT_ERROR",
            [Issue("I", "/", f"instance SHA-256 differs from released benchmark {expected_instance_sha256}")],
        ), 2
    try:
        instance = parse_instance(strict_json_loads(instance_payload, label="instance"))
        witness = parse_witness(strict_json_loads(witness_payload, label="witness"))
    except ContractError as exc:
        return _report("CONTRACT_ERROR", [exc.issue]), 2
    try:
        digest = "sha256:" + actual_instance_sha256
        issues, objective = validate_layout(instance, witness, digest)
        if issues:
            return _report("LAYOUT_INVALID", issues, objective), 1
        return _report("LAYOUT_FEASIBLE", [], objective), 0
    except Exception as exc:  # pragma: no cover - last-resort CLI fail-closed guard
        return _report("INTERNAL_ERROR", [Issue("S", "/", f"validator internal error: {type(exc).__name__}: {exc}")]), 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("witness", type=Path)
    parser.add_argument("--output", type=Path, help="optional path for the deterministic JSON report")
    args = parser.parse_args()
    try:
        instance_payload = args.instance.read_bytes()
        witness_payload = args.witness.read_bytes()
    except OSError as exc:
        report, code = _report("CONTRACT_ERROR", [Issue("J", "/", f"I/O error: {exc}")]), 2
    else:
        report, code = validate_bytes(instance_payload, witness_payload)
    rendered = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        except OSError as exc:
            print(json.dumps(_report("CONTRACT_ERROR", [Issue("J", "/", f"report I/O error: {exc}")]), sort_keys=True))
            return 2
    else:
        sys.stdout.write(rendered)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
