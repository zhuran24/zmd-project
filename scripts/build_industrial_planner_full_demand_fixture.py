"""Build a deterministic full-demand IndustrialPlanner recipe-capacity fixture.

This script keeps the existing 70x70 canonical manufacturing row packing, but
replaces the old hard-coded boundary request/slot lists with a base-aware search
that derives the explicit boundary proof surface from:

- the current generic I/O requirements artifact inputs/outputs,
- the selected base's foundation-bus geometry, and
- validator feedback from the real IndustrialPlanner exporter.

The planner stays intentionally honest about the current project boundaries:

- it does **not** change the canonical blueprint schema;
- it therefore refuses bases whose faithful edge geometry would require anchors
  beyond the canonical 70x70 contract; and
- it fails closed on bases that are too small for the full-demand manufacturing
  surface instead of silently emitting a partial fixture under a full-demand
  filename.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.industrial_planner.blueprint_validator import load_static_registries
from src.adapters.industrial_planner.export_blueprint import build_industrial_planner_export_bundle
from src.adapters.industrial_planner.mapping_registry import DEFAULT_BASE_ID
from src.preprocess.demand_solver import (
    generate_generic_io_requirements,
    generate_port_budget,
    solve_demands_exact,
)
from src.search.exact_campaign import atomic_write_json

_CANONICAL_GRID_SIZE = 70
_DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "full_demand_recipe_capacity_canonical_blueprint.json"
_FACILITY_SIZE_BY_TEMPLATE: dict[str, tuple[int, int]] = {
    "manufacturing_3x3": (3, 3),
    "manufacturing_5x5": (5, 5),
    "manufacturing_6x4": (6, 4),
}
_ROW_PLANS: tuple[tuple[str, tuple[int, ...], int, int], ...] = (
    ("manufacturing_3x3", (2, 6), 9, 20),
    ("manufacturing_3x3", (10, 14, 18, 22), 1, 23),
    ("manufacturing_5x5", (26, 32, 38, 44), 1, 13),
    ("manufacturing_6x4", (50, 55, 60, 65), 1, 11),
)
_REPORT_STATUS_SUCCESS = "proven_equivalent"
_REPORT_STATUS_INFEASIBLE = "infeasible"
_REPORT_STATUS_UNSUPPORTED = "unsupported_by_canonical_contract"
_SEARCH_OUTPUT_COMMODITY = "blue_iron_ore"


@dataclass(frozen=True)
class FullDemandFixturePlanReport:
    status: str
    base_id: str
    selected_base_placeable_size: int
    canonical_grid_size: int
    foundation_bus_edges: tuple[str, ...]
    required_recipe_facility_count: int
    required_recipe_area_cells: int
    required_boundary_output_slots: int
    required_boundary_input_slots: int
    selected_input_slots: tuple[int, ...] = ()
    selected_output_slots_by_edge: tuple[tuple[str, tuple[int, ...]], ...] = ()
    validation_probe_count: int = 0
    throughput_status: str | None = None
    validator_import_compatible: bool | None = None
    validator_layout_healthy: bool | None = None
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "base_id": self.base_id,
            "selected_base_placeable_size": self.selected_base_placeable_size,
            "canonical_grid_size": self.canonical_grid_size,
            "foundation_bus_edges": list(self.foundation_bus_edges),
            "required_recipe_facility_count": self.required_recipe_facility_count,
            "required_recipe_area_cells": self.required_recipe_area_cells,
            "required_boundary_output_slots": self.required_boundary_output_slots,
            "required_boundary_input_slots": self.required_boundary_input_slots,
            "selected_input_slots": list(self.selected_input_slots),
            "selected_output_slots_by_edge": {
                edge: list(positions)
                for edge, positions in self.selected_output_slots_by_edge
            },
            "selected_output_edge_counts": {
                edge: len(positions)
                for edge, positions in self.selected_output_slots_by_edge
            },
            "validation_probe_count": self.validation_probe_count,
            "throughput_status": self.throughput_status,
            "validator_import_compatible": self.validator_import_compatible,
            "validator_layout_healthy": self.validator_layout_healthy,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
            "error_message": self.error_message,
        }

    def to_markdown(self) -> str:
        lines = [
            "# IndustrialPlanner Full-Demand Fixture Planning Report",
            "",
            f"- Status: `{self.status}`",
            f"- Base id: `{self.base_id}`",
            f"- Selected base placeable size: {self.selected_base_placeable_size}",
            f"- Canonical grid size contract: {_CANONICAL_GRID_SIZE}×{_CANONICAL_GRID_SIZE}",
            f"- Foundation bus edges: {', '.join(self.foundation_bus_edges) if self.foundation_bus_edges else '(none)' }",
            f"- Required manufacturing facilities: {self.required_recipe_facility_count}",
            f"- Required manufacturing area cells: {self.required_recipe_area_cells}",
            f"- Required boundary output slots: {self.required_boundary_output_slots}",
            f"- Required boundary input slots: {self.required_boundary_input_slots}",
            f"- Validation probes used during planning: {self.validation_probe_count}",
        ]
        if self.selected_input_slots:
            lines.append(f"- Selected top-edge input slots: {', '.join(str(value) for value in self.selected_input_slots)}")
        if self.selected_output_slots_by_edge:
            lines.append("- Selected output slots by edge:")
            for edge, positions in self.selected_output_slots_by_edge:
                lines.append(f"  - {edge}: {', '.join(str(value) for value in positions)}")
        if self.throughput_status is not None:
            lines.append(f"- Final throughput status: `{self.throughput_status}`")
        if self.validator_import_compatible is not None:
            lines.append(f"- Final validator import-compatible: {self.validator_import_compatible}")
        if self.validator_layout_healthy is not None:
            lines.append(f"- Final validator layout-healthy: {self.validator_layout_healthy}")
        if self.error_message:
            lines.extend(["", "## Error", "", self.error_message])
        if self.notes:
            lines.extend(["", "## Notes", ""])
            for note in self.notes:
                lines.append(f"- {note}")
        if self.warnings:
            lines.extend(["", "## Warnings", ""])
            for warning in self.warnings:
                lines.append(f"- {warning}")
        lines.append("")
        return "\n".join(lines)


class FullDemandFixturePlanningError(RuntimeError):
    def __init__(self, report: FullDemandFixturePlanReport):
        super().__init__(report.error_message or report.status)
        self.report = report


def _canonical_rules_payload() -> dict[str, Any]:
    return json.loads((PROJECT_ROOT / "rules" / "canonical_rules.json").read_text(encoding="utf-8"))


def _current_boundary_requirements() -> tuple[tuple[str, ...], tuple[str, ...]]:
    flows, _ = solve_demands_exact()
    port_budget = generate_port_budget(flows)
    generic_io = generate_generic_io_requirements(flows, port_budget)
    output_commodities: list[str] = []
    for commodity_id, count in sorted(
        dict(generic_io.get("required_generic_outputs", {})).items()
    ):
        output_commodities.extend([str(commodity_id)] * int(count))
    input_commodities: list[str] = []
    for commodity_id, count in sorted(
        dict(generic_io.get("required_generic_inputs", {})).items()
    ):
        input_commodities.extend([str(commodity_id)] * int(count))
    return tuple(output_commodities), tuple(input_commodities)


def _required_recipe_counts() -> dict[str, int]:
    from fractions import Fraction

    def ceil_fraction(raw_value: Any) -> int:
        value = raw_value if isinstance(raw_value, Fraction) else Fraction(str(raw_value))
        return int((value.numerator + value.denominator - 1) // value.denominator)

    _, required_machine_runs = solve_demands_exact()
    return {
        recipe_id: ceil_fraction(raw_value)
        for recipe_id, raw_value in required_machine_runs.items()
        if ceil_fraction(raw_value) > 0
    }


def _required_recipe_area(recipe_rules: Mapping[str, Any], requirement_counts: Mapping[str, int]) -> int:
    area = 0
    for canonical_recipe_id, count in sorted(requirement_counts.items()):
        recipe_rule = dict(recipe_rules[canonical_recipe_id])
        facility_type = str(recipe_rule.get("template", ""))
        width, height = _FACILITY_SIZE_BY_TEMPLATE[facility_type]
        area += int(width * height * int(count))
    return area


def _foundation_bus_edges_for_base(base_id: str) -> tuple[str, ...]:
    registries = load_static_registries()
    base_def = registries.base_by_id.get(str(base_id))
    if not isinstance(base_def, Mapping):
        return ()
    edges: set[str] = set()
    for entry in base_def.get("foundationBuildings", ()):
        if not isinstance(entry, Mapping):
            continue
        type_id = str(entry.get("typeId", "")).strip()
        if type_id not in {"item_port_log_hongs_bus", "item_port_log_hongs_bus_source"}:
            continue
        origin = entry.get("origin") if isinstance(entry.get("origin"), Mapping) else {}
        origin_x = int(origin.get("x", 0))
        origin_y = int(origin.get("y", 0))
        if origin_y < 0:
            edges.add("top")
        if origin_x < 0:
            edges.add("left")
        if origin_y >= int(base_def.get("placeableSize", 0)):
            edges.add("bottom")
        if origin_x >= int(base_def.get("placeableSize", 0)):
            edges.add("right")
    return tuple(sorted(edges))


def _candidate_positions_for_edge(*, edge: str, lot_size: int, inside_facing: bool) -> tuple[int, ...]:
    if edge == "top":
        start = 10 if inside_facing else 9
        return tuple(range(start, lot_size - 3, 3))
    if edge == "left":
        start = 15 if inside_facing else 10
        return tuple(range(start, lot_size - 2, 3))
    if edge == "bottom":
        return tuple(range(1, lot_size - 3, 3))
    if edge == "right":
        return tuple(range(1, lot_size - 2, 3))
    raise ValueError(f"unsupported edge {edge!r}")


def _boundary_orientation(*, edge: str, inside_facing: bool, direction: str) -> int:
    if direction == "required_input":
        if edge != "top":
            raise ValueError("current full-demand input fixture planner only emits top-edge pure-input loaders")
        return 1
    orientation_by_edge_and_mode = {
        ("top", False): 1,
        ("top", True): 3,
        ("left", False): 0,
        ("left", True): 2,
        ("bottom", True): 1,
        ("right", True): 0,
    }
    return orientation_by_edge_and_mode[(edge, inside_facing)]


def _make_recipe_ports(
    *,
    anchor_x: int,
    anchor_y: int,
    width: int,
    height: int,
    input_ids: Sequence[str],
    output_ids: Sequence[str],
) -> list[dict[str, Any]]:
    ports: list[dict[str, Any]] = []
    if output_ids:
        output_start_x = anchor_x + (width - len(output_ids)) // 2
        for index, commodity_id in enumerate(output_ids):
            ports.append(
                {
                    "type": "output",
                    "x": output_start_x + index,
                    "y": anchor_y,
                    "dir": "N",
                    "commodity": commodity_id,
                }
            )
    if input_ids:
        input_start_x = anchor_x + max(0, (width - len(input_ids)) // 2)
        for index, commodity_id in enumerate(input_ids):
            ports.append(
                {
                    "type": "input",
                    "x": input_start_x + index,
                    "y": anchor_y + height - 1,
                    "dir": "S",
                    "commodity": commodity_id,
                }
            )
    return ports


def _build_recipe_facility(
    *,
    canonical_recipe_id: str,
    instance_index: int,
    anchor_x: int,
    anchor_y: int,
    recipe_rules: Mapping[str, Any],
) -> dict[str, Any]:
    recipe_rule = dict(recipe_rules[canonical_recipe_id])
    facility_type = str(recipe_rule["template"])
    width, height = _FACILITY_SIZE_BY_TEMPLATE[facility_type]
    input_ids = [str(item_id) for item_id in recipe_rule.get("inputs", {}).keys()]
    output_ids = [str(item_id) for item_id in recipe_rule.get("outputs", {}).keys()]
    return {
        "instance_id": f"mfg_{canonical_recipe_id}_{instance_index:03d}",
        "facility_type": facility_type,
        "anchor": {"x": int(anchor_x), "y": int(anchor_y)},
        "orientation": 0,
        "port_mode": "default",
        "active_ports": _make_recipe_ports(
            anchor_x=int(anchor_x),
            anchor_y=int(anchor_y),
            width=width,
            height=height,
            input_ids=input_ids,
            output_ids=output_ids,
        ),
    }


def _build_boundary_facility(
    *,
    direction: str,
    commodity_id: str,
    instance_index: int,
    edge: str,
    position: int,
    lot_size: int,
    inside_facing: bool,
) -> dict[str, Any]:
    if edge == "top":
        anchor_x, anchor_y = int(position), 0
    elif edge == "left":
        anchor_x, anchor_y = 0, int(position)
    elif edge == "bottom":
        anchor_x, anchor_y = int(position), int(lot_size - 1)
    elif edge == "right":
        anchor_x, anchor_y = int(lot_size - 1), int(position)
    else:
        raise ValueError(f"unsupported edge {edge!r}")
    port_type = "output" if direction == "required_output" else "input"
    return {
        "instance_id": f"boundary_{direction}_{commodity_id}_{instance_index:03d}",
        "facility_type": "boundary_storage_port",
        "anchor": {"x": anchor_x, "y": anchor_y},
        "orientation": _boundary_orientation(edge=edge, inside_facing=inside_facing, direction=direction),
        "port_mode": "default",
        "active_ports": [
            {
                "type": port_type,
                "x": anchor_x,
                "y": anchor_y,
                "dir": "N",
                "commodity": str(commodity_id),
            }
        ],
    }


def _build_manufacturing_facilities(recipe_rules: Mapping[str, Any]) -> list[dict[str, Any]]:
    requirement_counts = _required_recipe_counts()
    recipe_instances_by_template: dict[str, list[tuple[str, int]]] = {
        facility_type: []
        for facility_type in _FACILITY_SIZE_BY_TEMPLATE
    }
    for canonical_recipe_id, recipe_rule in sorted(recipe_rules.items()):
        facility_type = str(recipe_rule.get("template", ""))
        if facility_type not in recipe_instances_by_template:
            continue
        required_count = int(requirement_counts.get(canonical_recipe_id, 0))
        for instance_index in range(1, required_count + 1):
            recipe_instances_by_template[facility_type].append((canonical_recipe_id, instance_index))

    facilities: list[dict[str, Any]] = []
    cursors = {facility_type: 0 for facility_type in recipe_instances_by_template}
    for facility_type, row_y_values, row_start_x, row_capacity in _ROW_PLANS:
        row_instances = recipe_instances_by_template[facility_type]
        width = _FACILITY_SIZE_BY_TEMPLATE[facility_type][0]
        for row_y in row_y_values:
            anchor_x = int(row_start_x)
            for _ in range(int(row_capacity)):
                cursor = cursors[facility_type]
                if cursor >= len(row_instances):
                    break
                canonical_recipe_id, instance_index = row_instances[cursor]
                cursors[facility_type] = cursor + 1
                facilities.append(
                    _build_recipe_facility(
                        canonical_recipe_id=canonical_recipe_id,
                        instance_index=instance_index,
                        anchor_x=anchor_x,
                        anchor_y=int(row_y),
                        recipe_rules=recipe_rules,
                    )
                )
                anchor_x += width

    unplaced = {
        facility_type: len(instances) - cursors[facility_type]
        for facility_type, instances in recipe_instances_by_template.items()
        if len(instances) - cursors[facility_type] > 0
    }
    if unplaced:
        raise ValueError(f"row plan could not place all required recipe instances: {unplaced}")
    return facilities


def _base_blueprint_payload(*, manufacturing_facilities: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "metadata": {
            "version": "1.0.0",
            "solve_time_seconds": 0.0,
            "benders_iterations": 0,
            "export_timestamp": "2026-03-30T12:00:00Z",
        },
        "objective_achieved": {
            "empty_rect": {
                "w": 0,
                "h": 0,
                "anchor_x": 0,
                "anchor_y": 0,
                "score": 0.0,
            }
        },
        "facilities": list(manufacturing_facilities),
        "routing_network": {
            "L0_ground": {},
            "L1_elevated": {},
        },
    }


def _candidate_edge_sequence(*, foundation_bus_edges: Sequence[str], lot_size: int) -> tuple[tuple[str, bool, tuple[int, ...]], ...]:
    has_top_foundation = "top" in foundation_bus_edges
    has_left_foundation = "left" in foundation_bus_edges
    sequence: list[tuple[str, bool, tuple[int, ...]]] = []
    if has_top_foundation:
        sequence.append(("top", False, _candidate_positions_for_edge(edge="top", lot_size=lot_size, inside_facing=False)))
    if has_left_foundation:
        sequence.append(("left", False, _candidate_positions_for_edge(edge="left", lot_size=lot_size, inside_facing=False)))
    sequence.append(("bottom", True, _candidate_positions_for_edge(edge="bottom", lot_size=lot_size, inside_facing=True)))
    sequence.append(("right", True, _candidate_positions_for_edge(edge="right", lot_size=lot_size, inside_facing=True)))
    if not has_left_foundation:
        sequence.append(("left", True, _candidate_positions_for_edge(edge="left", lot_size=lot_size, inside_facing=True)))
    if not has_top_foundation:
        sequence.append(("top", True, _candidate_positions_for_edge(edge="top", lot_size=lot_size, inside_facing=True)))
    return tuple(sequence)


def _validation_accepts_fixture(
    *,
    blueprint_payload: Mapping[str, Any],
    base_id: str,
) -> tuple[bool, dict[str, Any]]:
    bundle = build_industrial_planner_export_bundle(
        blueprint_payload=blueprint_payload,
        base_id=base_id,
    )
    validation_report = dict(bundle["validation_report"])
    is_accepted = bool(validation_report.get("is_import_compatible")) and bool(validation_report.get("is_layout_healthy"))
    return is_accepted, bundle


def _plan_boundary_slots(
    *,
    base_id: str,
    manufacturing_facilities: Sequence[Mapping[str, Any]],
    output_commodities: Sequence[str],
    input_commodities: Sequence[str],
    lot_size: int,
    foundation_bus_edges: Sequence[str],
) -> tuple[tuple[int, ...], tuple[tuple[str, bool, int], ...], int]:
    base_payload = _base_blueprint_payload(manufacturing_facilities=manufacturing_facilities)
    validation_probe_count = 0

    top_probe_positions = _candidate_positions_for_edge(edge="top", lot_size=lot_size, inside_facing=False)
    selected_input_slots: list[int] = []
    input_facilities: list[dict[str, Any]] = []
    for position in reversed(top_probe_positions):
        if len(input_facilities) >= len(input_commodities):
            break
        candidate_facility = _build_boundary_facility(
            direction="required_input",
            commodity_id=str(input_commodities[len(input_facilities)]),
            instance_index=len(input_facilities) + 1,
            edge="top",
            position=int(position),
            lot_size=lot_size,
            inside_facing=False,
        )
        payload = dict(base_payload)
        payload["facilities"] = [*manufacturing_facilities, *input_facilities, candidate_facility]
        accepted, _ = _validation_accepts_fixture(blueprint_payload=payload, base_id=base_id)
        validation_probe_count += 1
        if accepted:
            input_facilities.append(candidate_facility)
            selected_input_slots.append(int(position))
    if len(input_facilities) != len(input_commodities):
        raise FullDemandFixturePlanningError(
            FullDemandFixturePlanReport(
                status=_REPORT_STATUS_INFEASIBLE,
                base_id=base_id,
                selected_base_placeable_size=lot_size,
                canonical_grid_size=_CANONICAL_GRID_SIZE,
                foundation_bus_edges=tuple(foundation_bus_edges),
                required_recipe_facility_count=len(manufacturing_facilities),
                required_recipe_area_cells=0,
                required_boundary_output_slots=len(output_commodities),
                required_boundary_input_slots=len(input_commodities),
                selected_input_slots=tuple(selected_input_slots),
                validation_probe_count=validation_probe_count,
                error_message=(
                    "could not recover enough validator-clean top-edge input slots "
                    f"for the {len(input_commodities)} required sink commodities"
                ),
                notes=(
                    "input-slot planning uses the real exporter plus validator feedback rather than a hard-coded slot list",
                ),
            )
        )

    selected_output_slots: list[tuple[str, bool, int]] = []
    edge_sequence = _candidate_edge_sequence(foundation_bus_edges=foundation_bus_edges, lot_size=lot_size)
    for edge, inside_facing, positions in edge_sequence:
        for position in positions:
            if len(selected_output_slots) >= len(output_commodities):
                break
            if edge == "top" and int(position) in selected_input_slots:
                continue
            candidate_facility = _build_boundary_facility(
                direction="required_output",
                commodity_id=_SEARCH_OUTPUT_COMMODITY,
                instance_index=len(selected_output_slots) + 1,
                edge=edge,
                position=int(position),
                lot_size=lot_size,
                inside_facing=inside_facing,
            )
            provisional_output_facilities = [
                _build_boundary_facility(
                    direction="required_output",
                    commodity_id=_SEARCH_OUTPUT_COMMODITY,
                    instance_index=index + 1,
                    edge=selected_edge,
                    position=selected_position,
                    lot_size=lot_size,
                    inside_facing=selected_inside_facing,
                )
                for index, (selected_edge, selected_inside_facing, selected_position) in enumerate(selected_output_slots)
            ]
            payload = dict(base_payload)
            payload["facilities"] = [
                *manufacturing_facilities,
                *input_facilities,
                *provisional_output_facilities,
                candidate_facility,
            ]
            accepted, _ = _validation_accepts_fixture(blueprint_payload=payload, base_id=base_id)
            validation_probe_count += 1
            if accepted:
                selected_output_slots.append((edge, inside_facing, int(position)))
        if len(selected_output_slots) >= len(output_commodities):
            break

    if len(selected_output_slots) != len(output_commodities):
        edge_counts = Counter(edge for edge, _, _ in selected_output_slots)
        raise FullDemandFixturePlanningError(
            FullDemandFixturePlanReport(
                status=_REPORT_STATUS_INFEASIBLE,
                base_id=base_id,
                selected_base_placeable_size=lot_size,
                canonical_grid_size=_CANONICAL_GRID_SIZE,
                foundation_bus_edges=tuple(foundation_bus_edges),
                required_recipe_facility_count=len(manufacturing_facilities),
                required_recipe_area_cells=0,
                required_boundary_output_slots=len(output_commodities),
                required_boundary_input_slots=len(input_commodities),
                selected_input_slots=tuple(sorted(selected_input_slots)),
                selected_output_slots_by_edge=tuple(
                    (edge_name, tuple(sorted(position for edge_name2, _, position in selected_output_slots if edge_name2 == edge_name)))
                    for edge_name in ("top", "left", "bottom", "right")
                    if edge_counts.get(edge_name, 0) > 0
                ),
                validation_probe_count=validation_probe_count,
                error_message=(
                    f"validator-clean search found only {len(selected_output_slots)} explicit output slots "
                    f"for {len(output_commodities)} required generic outputs"
                ),
                notes=(
                    "output-slot planning uses greedy edge search with exporter+validator feedback",
                ),
            )
        )

    return tuple(sorted(selected_input_slots)), tuple(selected_output_slots), validation_probe_count


def _assemble_boundary_facilities(
    *,
    selected_input_slots: Sequence[int],
    selected_output_slots: Sequence[tuple[str, bool, int]],
    input_commodities: Sequence[str],
    output_commodities: Sequence[str],
    lot_size: int,
) -> list[dict[str, Any]]:
    facilities: list[dict[str, Any]] = []
    input_instance_counts: defaultdict[str, int] = defaultdict(int)
    for commodity_id, position in zip(input_commodities, selected_input_slots):
        input_instance_counts[str(commodity_id)] += 1
        facilities.append(
            _build_boundary_facility(
                direction="required_input",
                commodity_id=str(commodity_id),
                instance_index=input_instance_counts[str(commodity_id)],
                edge="top",
                position=int(position),
                lot_size=lot_size,
                inside_facing=False,
            )
        )

    output_instance_counts: defaultdict[str, int] = defaultdict(int)
    for commodity_id, (edge, inside_facing, position) in zip(output_commodities, selected_output_slots):
        output_instance_counts[str(commodity_id)] += 1
        facilities.append(
            _build_boundary_facility(
                direction="required_output",
                commodity_id=str(commodity_id),
                instance_index=output_instance_counts[str(commodity_id)],
                edge=edge,
                position=int(position),
                lot_size=lot_size,
                inside_facing=inside_facing,
            )
        )
    return facilities


def plan_full_demand_recipe_capacity_fixture(
    *,
    base_id: str = DEFAULT_BASE_ID,
) -> tuple[dict[str, Any], FullDemandFixturePlanReport]:
    registries = load_static_registries()
    base_def = registries.base_by_id.get(str(base_id))
    if not isinstance(base_def, Mapping):
        raise FullDemandFixturePlanningError(
            FullDemandFixturePlanReport(
                status=_REPORT_STATUS_UNSUPPORTED,
                base_id=str(base_id),
                selected_base_placeable_size=0,
                canonical_grid_size=_CANONICAL_GRID_SIZE,
                foundation_bus_edges=(),
                required_recipe_facility_count=0,
                required_recipe_area_cells=0,
                required_boundary_output_slots=0,
                required_boundary_input_slots=0,
                error_message=f"unknown IndustrialPlanner base_id {base_id!r}",
            )
        )
    lot_size = int(base_def.get("placeableSize", 0))
    foundation_bus_edges = _foundation_bus_edges_for_base(str(base_id))
    recipe_rules = dict(_canonical_rules_payload().get("recipes", {}))
    requirement_counts = _required_recipe_counts()
    output_commodities, input_commodities = _current_boundary_requirements()
    required_recipe_area_cells = _required_recipe_area(recipe_rules, requirement_counts)
    required_recipe_facility_count = int(sum(requirement_counts.values()))

    if lot_size > _CANONICAL_GRID_SIZE:
        raise FullDemandFixturePlanningError(
            FullDemandFixturePlanReport(
                status=_REPORT_STATUS_UNSUPPORTED,
                base_id=str(base_id),
                selected_base_placeable_size=lot_size,
                canonical_grid_size=_CANONICAL_GRID_SIZE,
                foundation_bus_edges=tuple(foundation_bus_edges),
                required_recipe_facility_count=required_recipe_facility_count,
                required_recipe_area_cells=required_recipe_area_cells,
                required_boundary_output_slots=len(output_commodities),
                required_boundary_input_slots=len(input_commodities),
                error_message=(
                    f"selected base {base_id!r} uses placeableSize={lot_size}, but the canonical blueprint contract "
                    f"is capped at {_CANONICAL_GRID_SIZE}×{_CANONICAL_GRID_SIZE}; the planner refuses to fake boundary ports away from the true lot edge"
                ),
                notes=(
                    "this is an adapter-side fixture planner only; it does not widen the canonical blueprint schema",
                ),
            )
        )

    if required_recipe_area_cells > lot_size * lot_size:
        shortfall = required_recipe_area_cells - (lot_size * lot_size)
        raise FullDemandFixturePlanningError(
            FullDemandFixturePlanReport(
                status=_REPORT_STATUS_INFEASIBLE,
                base_id=str(base_id),
                selected_base_placeable_size=lot_size,
                canonical_grid_size=_CANONICAL_GRID_SIZE,
                foundation_bus_edges=tuple(foundation_bus_edges),
                required_recipe_facility_count=required_recipe_facility_count,
                required_recipe_area_cells=required_recipe_area_cells,
                required_boundary_output_slots=len(output_commodities),
                required_boundary_input_slots=len(input_commodities),
                error_message=(
                    f"selected base {base_id!r} cannot host the full-demand fixture: required manufacturing area "
                    f"{required_recipe_area_cells} exceeds lot area {lot_size * lot_size} by {shortfall} cells"
                ),
                notes=(
                    "the planner fails closed on smaller bases instead of silently emitting a partial fixture under a full-demand filename",
                ),
            )
        )

    manufacturing_facilities = _build_manufacturing_facilities(recipe_rules)
    max_anchor_x = max(int(facility["anchor"]["x"]) for facility in manufacturing_facilities)
    max_anchor_y = max(int(facility["anchor"]["y"]) for facility in manufacturing_facilities)
    if max(max_anchor_x, max_anchor_y) >= lot_size:
        raise FullDemandFixturePlanningError(
            FullDemandFixturePlanReport(
                status=_REPORT_STATUS_INFEASIBLE,
                base_id=str(base_id),
                selected_base_placeable_size=lot_size,
                canonical_grid_size=_CANONICAL_GRID_SIZE,
                foundation_bus_edges=tuple(foundation_bus_edges),
                required_recipe_facility_count=required_recipe_facility_count,
                required_recipe_area_cells=required_recipe_area_cells,
                required_boundary_output_slots=len(output_commodities),
                required_boundary_input_slots=len(input_commodities),
                error_message=(
                    f"selected base {base_id!r} is too small for the deterministic manufacturing row packing: "
                    f"max anchor reaches ({max_anchor_x},{max_anchor_y})"
                ),
            )
        )

    selected_input_slots, selected_output_slots, validation_probe_count = _plan_boundary_slots(
        base_id=str(base_id),
        manufacturing_facilities=manufacturing_facilities,
        output_commodities=output_commodities,
        input_commodities=input_commodities,
        lot_size=lot_size,
        foundation_bus_edges=foundation_bus_edges,
    )
    boundary_facilities = _assemble_boundary_facilities(
        selected_input_slots=selected_input_slots,
        selected_output_slots=selected_output_slots,
        input_commodities=input_commodities,
        output_commodities=output_commodities,
        lot_size=lot_size,
    )
    payload = _base_blueprint_payload(manufacturing_facilities=[*boundary_facilities, *manufacturing_facilities])
    final_bundle = build_industrial_planner_export_bundle(
        blueprint_payload=payload,
        base_id=str(base_id),
    )
    validation_report = dict(final_bundle["validation_report"])
    throughput_report = dict(final_bundle["throughput_report"])
    edge_positions: dict[str, list[int]] = defaultdict(list)
    for edge, _, position in selected_output_slots:
        edge_positions[str(edge)].append(int(position))
    report = FullDemandFixturePlanReport(
        status=str(throughput_report.get("status", _REPORT_STATUS_SUCCESS)),
        base_id=str(base_id),
        selected_base_placeable_size=lot_size,
        canonical_grid_size=_CANONICAL_GRID_SIZE,
        foundation_bus_edges=tuple(foundation_bus_edges),
        required_recipe_facility_count=required_recipe_facility_count,
        required_recipe_area_cells=required_recipe_area_cells,
        required_boundary_output_slots=len(output_commodities),
        required_boundary_input_slots=len(input_commodities),
        selected_input_slots=tuple(sorted(selected_input_slots)),
        selected_output_slots_by_edge=tuple(
            (edge_name, tuple(sorted(edge_positions.get(edge_name, ()))))
            for edge_name in ("top", "left", "bottom", "right")
            if edge_positions.get(edge_name)
        ),
        validation_probe_count=validation_probe_count,
        throughput_status=str(throughput_report.get("status")) if throughput_report.get("status") is not None else None,
        validator_import_compatible=bool(validation_report.get("is_import_compatible")),
        validator_layout_healthy=bool(validation_report.get("is_layout_healthy")),
        notes=(
            "boundary slot selection is derived from the current generic I/O artifact plus exporter+validator feedback",
            "the deterministic manufacturing row packing is still the checked-in 70x70 full-demand slice",
        ),
        warnings=tuple(str(entry) for entry in final_bundle.get("warnings", ()) if str(entry).strip()),
        error_message=None,
    )
    if (
        str(throughput_report.get("status")) != _REPORT_STATUS_SUCCESS
        or not bool(validation_report.get("is_import_compatible"))
        or not bool(validation_report.get("is_layout_healthy"))
    ):
        raise FullDemandFixturePlanningError(
            FullDemandFixturePlanReport(
                status=str(throughput_report.get("status") or _REPORT_STATUS_INFEASIBLE),
                base_id=str(base_id),
                selected_base_placeable_size=lot_size,
                canonical_grid_size=_CANONICAL_GRID_SIZE,
                foundation_bus_edges=tuple(foundation_bus_edges),
                required_recipe_facility_count=required_recipe_facility_count,
                required_recipe_area_cells=required_recipe_area_cells,
                required_boundary_output_slots=len(output_commodities),
                required_boundary_input_slots=len(input_commodities),
                selected_input_slots=report.selected_input_slots,
                selected_output_slots_by_edge=report.selected_output_slots_by_edge,
                validation_probe_count=validation_probe_count,
                throughput_status=str(throughput_report.get("status")) if throughput_report.get("status") is not None else None,
                validator_import_compatible=bool(validation_report.get("is_import_compatible")),
                validator_layout_healthy=bool(validation_report.get("is_layout_healthy")),
                warnings=tuple(str(entry) for entry in final_bundle.get("warnings", ()) if str(entry).strip()),
                error_message=(
                    "planned fixture did not satisfy the expected proven-equivalent / validator-clean success criteria"
                ),
                notes=report.notes,
            )
        )
    return payload, report


def build_full_demand_recipe_capacity_fixture(*, base_id: str = DEFAULT_BASE_ID) -> dict[str, Any]:
    payload, _ = plan_full_demand_recipe_capacity_fixture(base_id=base_id)
    return payload


def _write_optional_report(
    *,
    report: FullDemandFixturePlanReport,
    json_output: str | None,
    markdown_output: str | None,
) -> None:
    if json_output:
        atomic_write_json(Path(json_output), report.to_dict())
    if markdown_output:
        path = Path(markdown_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the deterministic full-demand IndustrialPlanner canonical fixture "
            "used for recipe-capacity audit regression coverage."
        )
    )
    parser.add_argument(
        "--base-id",
        default=DEFAULT_BASE_ID,
        help=(
            "IndustrialPlanner base id used for boundary-slot planning. "
            f"Defaults to {DEFAULT_BASE_ID!r}."
        ),
    )
    parser.add_argument(
        "--output",
        default=str(_DEFAULT_OUTPUT),
        help="Where to write the canonical fixture JSON.",
    )
    parser.add_argument(
        "--report-json",
        default=None,
        help="Optional path for the planning-report JSON.",
    )
    parser.add_argument(
        "--report-markdown",
        default=None,
        help="Optional path for the planning-report Markdown.",
    )
    args = parser.parse_args()

    try:
        payload, report = plan_full_demand_recipe_capacity_fixture(base_id=str(args.base_id))
    except FullDemandFixturePlanningError as exc:
        _write_optional_report(report=exc.report, json_output=args.report_json, markdown_output=args.report_markdown)
        print(exc.report.to_markdown())
        raise SystemExit(2)

    output_path = Path(args.output)
    atomic_write_json(output_path, payload)
    _write_optional_report(report=report, json_output=args.report_json, markdown_output=args.report_markdown)

    bundle = build_industrial_planner_export_bundle(blueprint_payload=payload, base_id=str(args.base_id))
    throughput_summary = bundle["throughput_report"]["summary"]
    print(f"fixture written: {output_path}")
    print(f"base id: {args.base_id}")
    print(f"facility count: {len(payload['facilities'])}")
    print(
        "throughput status: "
        f"{bundle['throughput_report']['status']} "
        f"(recipes proven={throughput_summary.get('proven_recipe_count', 0)}, "
        f"boundary proven/partial/insufficient="
        f"{throughput_summary.get('proven_boundary_commodity_count', 0)}/"
        f"{throughput_summary.get('partial_boundary_commodity_count', 0)}/"
        f"{throughput_summary.get('insufficient_boundary_commodity_count', 0)})"
    )
    print(
        "validator import/layout: "
        f"{bundle['validation_report']['is_import_compatible']}/"
        f"{bundle['validation_report']['is_layout_healthy']}"
    )
    print(
        "selected output edges: "
        + ", ".join(
            f"{edge}={len(positions)}"
            for edge, positions in report.selected_output_slots_by_edge
        )
    )


if __name__ == "__main__":
    main()
