"""Exact, research-only D6 joint placement/front/routing completion gate.

This module deliberately has no production imports and no command-line entry
point.  It consumes already decoded strict/framework/seed mappings, rebuilds a
self-contained local antecedent, and solves only that bounded antecedent.

The seed geometry is used exclusively through CP-SAT ``AddHint`` calls.  A
FEASIBLE result is only a local D6 certificate; INFEASIBLE closes only the
byte-bound antecedent rebuilt by :func:`build_d6_antecedent`; UNKNOWN has no
rejecting, cutting, lower-bound, or global force.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from ortools.sat.python import cp_model


ANTECEDENT_SCHEMA = "w0_d6_antecedent_v2"
GATE_RESULT_SCHEMA = "w0_d6_gate_result_v1"
CONFIGURATION_SCHEMA = "w0_d6_configuration_v1"
CERTIFICATE_SCHEMA = "w0_d6_local_certificate_v1"

COHORT = "w0_d6_swap_v3"
CLASS_ALLOCATION_PROFILE = "d6_6b_d9_6g_swap_v1"
PROJECT_LOCK_SHA256 = "aeadef3aded03099d18580a05454c90af11a4dd6859d7798516ced73d2df2b42"
PROTOCOL = {
    "cohort": COHORT,
    "class_allocation_profile": CLASS_ALLOCATION_PROFILE,
    "antecedent_schema": ANTECEDENT_SCHEMA,
    "config_payload_schema": "w0_d6_run_config_v3",
    "receipt_payload_schema": "w0_d6_receipt_payload_v3",
    "replay_receipt_schema": "w0_d6_replay_receipt_v3",
    "project_lock_sha256": PROJECT_LOCK_SHA256,
}

FEASIBLE_BOUNDARY = "feasible_only_for_the_exact_local_d6_antecedent"
INFEASIBLE_BOUNDARY = "infeasible_only_for_the_exact_local_d6_antecedent"
UNKNOWN_BOUNDARY = "unknown_no_rejection_cut_or_global_conclusion"

DIRECTIONS = ("N", "E", "S", "W")
DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
OPPOSITE = {"N": "S", "E": "W", "S": "N", "W": "E"}

LOCAL_BOUNDS = (14, 41, 28, 41)
TILES = ((1, 2), (2, 2))
TILE_TYPE_COUNTS = {
    (1, 2): {3: 5, 5: 3, 6: 1},
    (2, 2): {3: 5, 5: 1, 6: 2},
}
CLASS_ORDER = ("3I2", "3L", "3O2", "3O3", "5L", "5O2", "6B", "6F", "6G")
D6_BEFORE_CLASS_COUNTS = {
    "3I2": 0,
    "3L": 7,
    "3O2": 0,
    "3O3": 3,
    "5L": 2,
    "5O2": 2,
    "6B": 1,
    "6F": 0,
    "6G": 2,
}
D6_AFTER_CLASS_COUNTS = {
    "3I2": 0,
    "3L": 7,
    "3O2": 0,
    "3O3": 3,
    "5L": 2,
    "5O2": 2,
    "6B": 0,
    "6F": 0,
    "6G": 3,
}
D9_BEFORE_CLASS_COUNTS = {
    "3I2": 0,
    "3L": 18,
    "3O2": 0,
    "3O3": 0,
    "5L": 3,
    "5O2": 0,
    "6B": 0,
    "6F": 0,
    "6G": 3,
}
D9_AFTER_CLASS_COUNTS = {
    "3I2": 0,
    "3L": 18,
    "3O2": 0,
    "3O3": 0,
    "5L": 3,
    "5O2": 0,
    "6B": 1,
    "6F": 0,
    "6G": 2,
}
GLOBAL_CLASS_COUNTS = {
    "3I2": 6,
    "3L": 109,
    "3O2": 6,
    "3O3": 11,
    "5L": 32,
    "5O2": 17,
    "6B": 3,
    "6F": 3,
    "6G": 32,
}
# Only these six classes occur in D6.  Zero-count 6B remains in the modeled
# catalog so the before/after swap has one stable candidate universe.
CLASS_COUNTS = {
    class_name: D6_AFTER_CLASS_COUNTS[class_name]
    for class_name in ("3L", "3O3", "5L", "5O2", "6B", "6G")
}
# The selection rule is the only W0 mathematical vocabulary used to select
# anonymous classes.  Template and I/O counts are then checked and populated
# from strict operation_groups, never from a producer validation summary.
CLASS_SELECTORS = {
    "3L": ("manufacturing_3x3", 1, 1),
    "3O3": ("manufacturing_3x3", 1, 3),
    "5L": ("manufacturing_5x5", 1, 1),
    "5O2": ("manufacturing_5x5", 1, 2),
    "6G": ("manufacturing_6x4", 3, 1),
    "6B": ("manufacturing_6x4", 5, 1),
}
TYPE_BY_TEMPLATE = {
    "manufacturing_3x3": 3,
    "manufacturing_5x5": 5,
    "manufacturing_6x4": 6,
}
PROTECTED_ANCHOR = (29, 28)
PROTECTED_SIZE = (6, 7)
CYCLE_Y = 29
CYCLE_X_MIN = 14
CYCLE_X_MAX = 41
SEED_NARROW_X = (23, 24, 25, 30, 31, 32, 33, 34, 35, 36, 37)
D6_BEFORE_TOTALS = {"bodies": 17, "active_inputs": 25, "active_outputs": 25}
D6_AFTER_TOTALS = {"bodies": 17, "active_inputs": 23, "active_outputs": 25}
D9_BEFORE_TOTALS = {"bodies": 24, "active_inputs": 30, "active_outputs": 24}
D9_AFTER_TOTALS = {"bodies": 24, "active_inputs": 32, "active_outputs": 24}


class D6AntecedentError(ValueError):
    """The supplied mappings do not encode the exact D6 antecedent."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise D6AntecedentError(f"{label} must be an object with string keys")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise D6AntecedentError(f"{label} must be a list")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise D6AntecedentError(f"{label} must be an integer")
    return value


def _positive_integer(value: Any, label: str) -> int:
    result = _integer(value, label)
    if result <= 0:
        raise D6AntecedentError(f"{label} must be positive")
    return result


def _string(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise D6AntecedentError(f"{label} must be a non-empty string")
    return value


def _pair(value: Any, label: str) -> tuple[int, int]:
    raw = _list(value, label)
    if len(raw) != 2:
        raise D6AntecedentError(f"{label} must contain exactly two integers")
    return _integer(raw[0], f"{label}[0]"), _integer(raw[1], f"{label}[1]")


def _canonical_json_bytes(value: Any) -> bytes:
    """Canonical JSON shared only inside this research module.

    The runner independently canonicalizes through the G3 public contract.
    Keeping this small copy here avoids making the gate's own hash assertion an
    independent acceptance surface.
    """

    def validate(item: Any, path: str) -> None:
        if item is None or type(item) in (bool, int, str):
            return
        if isinstance(item, list):
            for index, member in enumerate(item):
                validate(member, f"{path}[{index}]")
            return
        if isinstance(item, Mapping):
            for key, member in item.items():
                if type(key) is not str:
                    raise TypeError(f"{path} has a non-string key")
                validate(member, f"{path}.{key}")
            return
        raise TypeError(f"{path} contains non-canonical value {type(item).__name__}")

    validate(value, "$")
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _body_cells(anchor: tuple[int, int], width: int, height: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        (anchor[0] + dx, anchor[1] + dy)
        for dx in range(width)
        for dy in range(height)
    )


def compute_active_front(
    anchor: tuple[int, int],
    port: Mapping[str, Any],
) -> tuple[int, int]:
    """Compute an absolute active front from a strict physical mode port."""

    body_cell = _pair(port.get("body_cell"), "port.body_cell")
    direction = _string(port.get("direction"), "port.direction")
    if direction not in DIRECTIONS:
        raise D6AntecedentError(f"port.direction must be one of {DIRECTIONS}")
    delta = DELTA[direction]
    return (
        anchor[0] + body_cell[0] + delta[0],
        anchor[1] + body_cell[1] + delta[1],
    )


def _rect_cells(anchor: tuple[int, int], size: tuple[int, int]) -> set[tuple[int, int]]:
    return set(_body_cells(anchor, size[0], size[1]))


def _tile_bounds(tile: tuple[int, int]) -> tuple[int, int, int, int]:
    x_min = 14 * tile[0]
    y_min = 14 * tile[1]
    return x_min, x_min + 13, y_min, y_min + 13


def _inside_bounds(cell: tuple[int, int], bounds: tuple[int, int, int, int]) -> bool:
    return bounds[0] <= cell[0] <= bounds[1] and bounds[2] <= cell[1] <= bounds[3]


def _ordered_dirs(values: Sequence[str]) -> list[str]:
    value_set = set(values)
    return [direction for direction in DIRECTIONS if direction in value_set]


def build_legal_routing_patterns() -> dict[str, Any]:
    """Return the exact 44 ground and four elevated directed patterns."""

    ground: list[dict[str, Any]] = []
    for direction_in in DIRECTIONS:
        for direction_out in DIRECTIONS:
            if direction_out == direction_in:
                continue
            ground.append(
                {
                    "name": f"belt:{direction_in}>{direction_out}",
                    "component": "belt",
                    "in_dirs": [direction_in],
                    "out_dirs": [direction_out],
                }
            )
    for direction_in in DIRECTIONS:
        remaining = [direction for direction in DIRECTIONS if direction != direction_in]
        for degree in (2, 3):
            for directions_out in combinations(remaining, degree):
                ordered_out = _ordered_dirs(directions_out)
                ground.append(
                    {
                        "name": f"splitter:{direction_in}>{'+'.join(ordered_out)}",
                        "component": "splitter",
                        "in_dirs": [direction_in],
                        "out_dirs": ordered_out,
                    }
                )
    for direction_out in DIRECTIONS:
        remaining = [direction for direction in DIRECTIONS if direction != direction_out]
        for degree in (2, 3):
            for directions_in in combinations(remaining, degree):
                ordered_in = _ordered_dirs(directions_in)
                ground.append(
                    {
                        "name": f"merger:{'+'.join(ordered_in)}>{direction_out}",
                        "component": "merger",
                        "in_dirs": ordered_in,
                        "out_dirs": [direction_out],
                    }
                )
    elevated = [
        {
            "name": f"elevated:{direction_in}>{OPPOSITE[direction_in]}",
            "component": "elevated_straight",
            "in_dirs": [direction_in],
            "out_dirs": [OPPOSITE[direction_in]],
        }
        for direction_in in DIRECTIONS
    ]
    if len(ground) != 44 or len(elevated) != 4:
        raise AssertionError("routing pattern enumeration drifted")
    return {
        "ground": ground,
        "elevated": elevated,
        "crossing": "perpendicular_ground_and_elevated_straights_without_transfer",
    }


def _derive_mode_catalog(strict_instance: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    templates = _mapping(strict_instance.get("facility_templates"), "strict.facility_templates")
    result: dict[str, list[dict[str, Any]]] = {}
    for template_name in sorted(TYPE_BY_TEMPLATE):
        template = _mapping(templates.get(template_name), f"strict.facility_templates.{template_name}")
        if template.get("placement_rule") != "any_body_in_grid" or template.get("requires_power") is not True:
            raise D6AntecedentError(f"{template_name} strict placement/power rule drifted")
        raw_modes = _list(template.get("modes"), f"{template_name}.modes")
        modes: list[dict[str, Any]] = []
        mode_ids: set[str] = set()
        for mode_index, raw_mode in enumerate(raw_modes):
            mode = _mapping(raw_mode, f"{template_name}.modes[{mode_index}]")
            mode_id = _string(mode.get("id"), f"{template_name}.modes[{mode_index}].id")
            if mode_id in mode_ids:
                raise D6AntecedentError(f"{template_name} has duplicate mode {mode_id}")
            mode_ids.add(mode_id)
            body = _mapping(mode.get("body"), f"{template_name}.{mode_id}.body")
            width = _positive_integer(body.get("width"), f"{template_name}.{mode_id}.body.width")
            height = _positive_integer(body.get("height"), f"{template_name}.{mode_id}.body.height")
            ports: list[dict[str, Any]] = []
            port_ids: set[str] = set()
            for port_index, raw_port in enumerate(
                _list(mode.get("ports"), f"{template_name}.{mode_id}.ports")
            ):
                port = _mapping(raw_port, f"{template_name}.{mode_id}.ports[{port_index}]")
                port_id = _string(port.get("id"), f"{template_name}.{mode_id}.ports[{port_index}].id")
                if port_id in port_ids:
                    raise D6AntecedentError(f"{template_name}.{mode_id} has duplicate port {port_id}")
                port_ids.add(port_id)
                kind = port.get("kind")
                if kind not in ("input", "output"):
                    raise D6AntecedentError(f"{template_name}.{mode_id}.{port_id} has invalid kind")
                body_cell = _mapping(
                    port.get("body_cell"), f"{template_name}.{mode_id}.{port_id}.body_cell"
                )
                body_x = _integer(
                    body_cell.get("x"), f"{template_name}.{mode_id}.{port_id}.body_cell.x"
                )
                body_y = _integer(
                    body_cell.get("y"), f"{template_name}.{mode_id}.{port_id}.body_cell.y"
                )
                if not (0 <= body_x < width and 0 <= body_y < height):
                    raise D6AntecedentError(f"{template_name}.{mode_id}.{port_id} leaves body")
                direction = port.get("direction")
                if direction not in DIRECTIONS:
                    raise D6AntecedentError(f"{template_name}.{mode_id}.{port_id} direction drifted")
                ports.append(
                    {
                        "id": port_id,
                        "kind": kind,
                        "body_cell": [body_x, body_y],
                        "direction": direction,
                    }
                )
            modes.append(
                {
                    "id": mode_id,
                    "body": {"width": width, "height": height},
                    "ports": sorted(ports, key=lambda item: item["id"]),
                }
            )
        result[template_name] = sorted(modes, key=lambda item: item["id"])
    return result


def _derive_class_catalog(strict_instance: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_groups = _list(strict_instance.get("operation_groups"), "strict.operation_groups")
    derived_groups: list[dict[str, Any]] = []
    for group_index, raw_group in enumerate(raw_groups):
        group = _mapping(raw_group, f"strict.operation_groups[{group_index}]")
        group_id = _string(group.get("id"), f"strict.operation_groups[{group_index}].id")
        template = _string(
            group.get("template"), f"strict.operation_groups[{group_index}].template"
        )
        count = _positive_integer(
            group.get("count"), f"strict.operation_groups[{group_index}].count"
        )
        needs = _mapping(
            group.get("port_needs"), f"strict.operation_groups[{group_index}].port_needs"
        )
        inputs = _mapping(needs.get("inputs"), f"{group_id}.port_needs.inputs")
        outputs = _mapping(needs.get("outputs"), f"{group_id}.port_needs.outputs")
        input_count = sum(_positive_integer(value, f"{group_id}.inputs.{key}") for key, value in inputs.items())
        output_count = sum(
            _positive_integer(value, f"{group_id}.outputs.{key}") for key, value in outputs.items()
        )
        derived_groups.append(
            {
                "id": group_id,
                "template": template,
                "count": count,
                "input_count": input_count,
                "output_count": output_count,
            }
        )

    result: dict[str, dict[str, Any]] = {}
    for class_name, (template, input_count, output_count) in CLASS_SELECTORS.items():
        matching = sorted(
            (
                group
                for group in derived_groups
                if group["template"] == template
                and group["input_count"] == input_count
                and group["output_count"] == output_count
            ),
            key=lambda item: item["id"],
        )
        required_supply = max(
            D6_BEFORE_CLASS_COUNTS[class_name],
            D6_AFTER_CLASS_COUNTS[class_name],
        )
        if sum(group["count"] for group in matching) < required_supply:
            raise D6AntecedentError(f"strict operation_groups cannot supply class {class_name}")
        result[class_name] = {
            "template": template,
            "input_count": input_count,
            "output_count": output_count,
            "operation_group_ids": [group["id"] for group in matching],
        }
    return result


def _ordered_class_counts(values: Mapping[str, int]) -> dict[str, int]:
    if set(values) != set(CLASS_ORDER):
        raise D6AntecedentError("class ledger does not cover the exact class order")
    return {class_name: values[class_name] for class_name in CLASS_ORDER}


def _allocation_totals(
    class_counts: Mapping[str, Any],
    class_catalog: Mapping[str, Any],
    *,
    label: str,
) -> dict[str, int]:
    bodies = 0
    active_inputs = 0
    active_outputs = 0
    for class_name, count_raw in class_counts.items():
        count = _integer(count_raw, f"{label}.{class_name}")
        if count < 0:
            raise D6AntecedentError(f"{label}.{class_name} must be nonnegative")
        bodies += count
        if count == 0:
            continue
        class_data = _mapping(class_catalog.get(class_name), f"class_catalog.{class_name}")
        active_inputs += count * _integer(
            class_data.get("input_count"), f"class_catalog.{class_name}.input_count"
        )
        active_outputs += count * _integer(
            class_data.get("output_count"), f"class_catalog.{class_name}.output_count"
        )
    return {
        "bodies": bodies,
        "active_inputs": active_inputs,
        "active_outputs": active_outputs,
    }


def _build_class_ledger(class_catalog: Mapping[str, Any]) -> dict[str, Any]:
    d6_before = _allocation_totals(
        D6_BEFORE_CLASS_COUNTS,
        class_catalog,
        label="class_ledger.d6.before.class_counts",
    )
    d6_after = _allocation_totals(
        D6_AFTER_CLASS_COUNTS,
        class_catalog,
        label="class_ledger.d6.after.class_counts",
    )
    d9_before = _allocation_totals(
        D9_BEFORE_CLASS_COUNTS,
        class_catalog,
        label="class_ledger.d9.before.class_counts",
    )
    d9_after = _allocation_totals(
        D9_AFTER_CLASS_COUNTS,
        class_catalog,
        label="class_ledger.d9.after.class_counts",
    )
    expected_states = (
        ("D6 before", d6_before, D6_BEFORE_TOTALS),
        ("D6 after", d6_after, D6_AFTER_TOTALS),
        ("D9 before", d9_before, D9_BEFORE_TOTALS),
        ("D9 after", d9_after, D9_AFTER_TOTALS),
    )
    for label, actual, expected in expected_states:
        if actual != expected:
            raise D6AntecedentError(f"{label} allocation totals drifted: {actual}")

    if (
        _mapping(class_catalog.get("6B"), "class_catalog.6B").get("template")
        != _mapping(class_catalog.get("6G"), "class_catalog.6G").get("template")
    ):
        raise D6AntecedentError("D6/D9 transfer classes no longer share one template")
    for class_name in CLASS_ORDER:
        before = D6_BEFORE_CLASS_COUNTS[class_name] + D9_BEFORE_CLASS_COUNTS[class_name]
        after = D6_AFTER_CLASS_COUNTS[class_name] + D9_AFTER_CLASS_COUNTS[class_name]
        if before != after:
            raise D6AntecedentError(f"D6/D9 transfer does not conserve class {class_name}")

    global_counts = _ordered_class_counts(GLOBAL_CLASS_COUNTS)
    return {
        "class_order": list(CLASS_ORDER),
        "d6": {
            "before": {
                "class_counts": _ordered_class_counts(D6_BEFORE_CLASS_COUNTS),
                "totals": d6_before,
            },
            "after": {
                "class_counts": _ordered_class_counts(D6_AFTER_CLASS_COUNTS),
                "totals": d6_after,
            },
            "modeled_state": "after",
        },
        "d9": {
            "before": {
                "class_counts": _ordered_class_counts(D9_BEFORE_CLASS_COUNTS),
                "totals": d9_before,
            },
            "after": {
                "class_counts": _ordered_class_counts(D9_AFTER_CLASS_COUNTS),
                "totals": d9_after,
            },
            "role": "arithmetic_compensation_only_not_geometrically_modeled",
        },
        "global": {
            "before": global_counts,
            "after": dict(global_counts),
            "conserved": True,
        },
    }


def _expected_d6_totals(antecedent: Mapping[str, Any]) -> dict[str, int]:
    expected = _mapping(antecedent.get("expected_totals"), "antecedent.expected_totals")
    result = {
        key: _positive_integer(expected.get(key), f"antecedent.expected_totals.{key}")
        for key in ("bodies", "active_inputs", "active_outputs")
    }
    derived = _allocation_totals(
        _mapping(antecedent.get("class_counts"), "antecedent.class_counts"),
        _mapping(antecedent.get("class_catalog"), "antecedent.class_catalog"),
        label="antecedent.class_counts",
    )
    if result != derived:
        raise D6AntecedentError(
            f"antecedent expected_totals do not match modeled D6 class counts: {derived}"
        )
    return result


def _derive_fixed_geometry(
    strict_instance: Mapping[str, Any],
    framework: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    templates = _mapping(strict_instance.get("facility_templates"), "strict.facility_templates")
    pole_template = _mapping(templates.get("power_pole"), "strict.facility_templates.power_pole")
    pole_modes = _list(pole_template.get("modes"), "power_pole.modes")
    if len(pole_modes) != 1:
        raise D6AntecedentError("strict power_pole must have one fixed mode")
    pole_mode = _mapping(pole_modes[0], "power_pole.modes[0]")
    pole_body = _mapping(pole_mode.get("body"), "power_pole.fixed.body")
    if (
        pole_mode.get("id") != "fixed"
        or _pair([pole_body.get("width"), pole_body.get("height")], "power pole size") != (2, 2)
        or pole_mode.get("ports") != []
    ):
        raise D6AntecedentError("strict power_pole is not the required 2x2 portless body")

    power_cells = _mapping(framework.get("power_cells"), "framework.power_cells")
    if _pair(power_cells.get("ordinary_pole_local_anchor"), "ordinary pole local anchor") != (6, 6):
        raise D6AntecedentError("framework ordinary pole local anchor drifted")
    if _pair(power_cells.get("protected_cell"), "protected cell") != (2, 2):
        raise D6AntecedentError("framework protected cell drifted")
    if _pair(power_cells.get("protected_pole_local_anchor"), "protected pole local anchor") != (7, 7):
        raise D6AntecedentError("framework protected pole local anchor drifted")

    poles = [
        {"tile": [1, 2], "anchor": [20, 34], "size": [2, 2]},
        {"tile": [2, 2], "anchor": [35, 35], "size": [2, 2]},
    ]
    strict_power = _mapping(strict_instance.get("power"), "strict.power")
    offsets = _mapping(
        strict_power.get("coverage_from_pole_anchor"), "strict.power.coverage_from_pole_anchor"
    )
    power_rule = {
        "required_rule": _string(strict_power.get("required_rule"), "strict.power.required_rule"),
        "pole_template": _string(strict_power.get("pole_template"), "strict.power.pole_template"),
        "coverage_offsets": {
            key: _integer(offsets.get(key), f"strict.power.coverage_offsets.{key}")
            for key in ("x_min_offset", "x_max_offset", "y_min_offset", "y_max_offset")
        },
    }
    if (
        power_rule["required_rule"] != "at_least_one_body_cell_covered"
        or power_rule["pole_template"] != "power_pole"
    ):
        raise D6AntecedentError("strict power rule drifted")
    return poles, power_rule


def _validate_framework(
    strict_instance: Mapping[str, Any],
    framework: Mapping[str, Any],
    class_catalog: Mapping[str, Any],
) -> None:
    grid = _mapping(strict_instance.get("grid"), "strict.grid")
    if (_integer(grid.get("width"), "strict.grid.width"), _integer(grid.get("height"), "strict.grid.height")) != (
        70,
        70,
    ):
        raise D6AntecedentError("strict grid is not 70x70")
    coordinate = _mapping(strict_instance.get("coordinate_system"), "strict.coordinate_system")
    if (
        coordinate.get("directions") != list(DIRECTIONS)
        or coordinate.get("indexing") != "zero_based"
        or coordinate.get("origin") != "southwest"
        or coordinate.get("x_positive") != "east"
        or coordinate.get("y_positive") != "north"
    ):
        raise D6AntecedentError("strict coordinate system drifted")
    routing = _mapping(strict_instance.get("routing"), "strict.routing")
    expected_routing = {
        "component_cells_must_avoid_bodies": True,
        "crossing": "two_perpendicular_straight_channels_without_transfer",
        "throughput_in_scope": False,
        "terminal_input_requires_component_output": "opposite_terminal_direction",
        "terminal_output_requires_component_input": "opposite_terminal_direction",
    }
    for key, expected in expected_routing.items():
        if routing.get(key) != expected:
            raise D6AntecedentError(f"strict routing.{key} drifted")

    if framework.get("grid") != [70, 70]:
        raise D6AntecedentError("framework grid drifted")
    macrocells = _mapping(framework.get("routing_macrocells"), "framework.routing_macrocells")
    if macrocells.get("D6") != [[1, 2], [2, 2]]:
        raise D6AntecedentError("framework D6 macrocell drifted")
    tile_seed = _mapping(framework.get("tile_type_count_seed"), "framework.tile_type_count_seed")
    for tile, expected in TILE_TYPE_COUNTS.items():
        actual = tile_seed.get(f"{tile[0]},{tile[1]}")
        if actual != [expected[3], expected[5], expected[6]]:
            raise D6AntecedentError(f"framework tile counts drifted for {tile}")
    allocations = _mapping(
        framework.get("macrocell_class_allocation_seed"),
        "framework.macrocell_class_allocation_seed",
    )
    expected_rows = {f"D{index}" for index in range(1, 13)}
    if set(macrocells) != expected_rows or set(allocations) != expected_rows:
        raise D6AntecedentError("framework macrocell allocation row set drifted")
    global_counts = {class_name: 0 for class_name in CLASS_ORDER}
    for row_name in sorted(expected_rows, key=lambda value: int(value[1:])):
        row = _mapping(
            allocations.get(row_name),
            f"framework.macrocell_class_allocation_seed.{row_name}",
        )
        for class_name, count_raw in row.items():
            if class_name not in global_counts:
                raise D6AntecedentError(
                    f"framework {row_name} has unknown operation class {class_name}"
                )
            global_counts[class_name] += _positive_integer(
                count_raw,
                f"framework.macrocell_class_allocation_seed.{row_name}.{class_name}",
            )
    if global_counts != _ordered_class_counts(GLOBAL_CLASS_COUNTS):
        raise D6AntecedentError("framework global class allocation drifted")
    expected_d6 = {
        class_name: count
        for class_name, count in D6_BEFORE_CLASS_COUNTS.items()
        if count
    }
    expected_d9 = {
        class_name: count
        for class_name, count in D9_BEFORE_CLASS_COUNTS.items()
        if count
    }
    if allocations.get("D6") != expected_d6:
        raise D6AntecedentError("framework D6 class allocation drifted")
    if allocations.get("D9") != expected_d9:
        raise D6AntecedentError("framework D9 class allocation drifted")
    framework_classes = _mapping(framework.get("operation_classes"), "framework.operation_classes")
    if set(framework_classes) != set(CLASS_ORDER):
        raise D6AntecedentError("framework operation class set drifted")
    for class_name in CLASS_ORDER:
        framework_class = _mapping(
            framework_classes.get(class_name),
            f"framework.operation_classes.{class_name}",
        )
        if (
            _positive_integer(
                framework_class.get("count"),
                f"framework.operation_classes.{class_name}.count",
            )
            != GLOBAL_CLASS_COUNTS[class_name]
        ):
            raise D6AntecedentError(f"framework {class_name} global count drifted")
    size_by_template = {
        "manufacturing_3x3": "3x3",
        "manufacturing_5x5": "5x5",
        "manufacturing_6x4": "6x4 or 4x6",
    }
    for class_name, derived in class_catalog.items():
        framework_class = _mapping(
            framework_classes.get(class_name), f"framework.operation_classes.{class_name}"
        )
        if framework_class.get("size") != size_by_template[derived["template"]]:
            raise D6AntecedentError(f"framework {class_name} size drifted")
        if framework_class.get("need") != [derived["input_count"], derived["output_count"]]:
            raise D6AntecedentError(f"framework {class_name} need drifted")

    protected = _mapping(framework.get("protected_rectangle"), "framework.protected_rectangle")
    if (
        _pair(protected.get("anchor"), "framework.protected_rectangle.anchor") != PROTECTED_ANCHOR
        or _pair(protected.get("size"), "framework.protected_rectangle.size") != PROTECTED_SIZE
        or protected.get("body_only") is not True
    ):
        raise D6AntecedentError("framework protected body-only rectangle drifted")
    cycle = _mapping(framework.get("directed_cycle"), "framework.directed_cycle")
    expected_segment = {"from": [2, 29], "to": [68, 29], "direction": "E"}
    if expected_segment not in _list(cycle.get("segments"), "framework.directed_cycle.segments"):
        raise D6AntecedentError("framework eastbound y=29 cycle segment is absent")
    expected_attachment_rule = (
        "output branches enter distinct noncorner cells by a legal merger; input branches leave distinct "
        "noncorner cells by a legal splitter; no cell serves both roles"
    )
    if cycle.get("attachment_rule") != expected_attachment_rule:
        raise D6AntecedentError("framework cycle attachment rule drifted")


def _seed_hints_and_slots(
    seed: Mapping[str, Any],
    poles: Sequence[Mapping[str, Any]],
    power_rule: Mapping[str, Any],
    *,
    attachment_scope: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_placements = _list(seed.get("manufacturing_placements"), "seed.manufacturing_placements")
    selected: list[dict[str, Any]] = []
    occupied: set[tuple[int, int]] = set()
    protected_cells = _rect_cells(PROTECTED_ANCHOR, PROTECTED_SIZE)
    cycle_cells = {(x, CYCLE_Y) for x in range(CYCLE_X_MIN, CYCLE_X_MAX + 1)}
    pole_cells = {
        cell
        for pole in poles
        for cell in _body_cells(
            _pair(pole["anchor"], "pole.anchor"),
            _pair(pole["size"], "pole.size")[0],
            _pair(pole["size"], "pole.size")[1],
        )
    }
    offsets = _mapping(power_rule.get("coverage_offsets"), "power_rule.coverage_offsets")
    pole_by_tile = {
        _pair(pole["tile"], "pole.tile"): _pair(pole["anchor"], "pole.anchor") for pole in poles
    }
    for placement_index, raw_placement in enumerate(raw_placements):
        placement = _mapping(raw_placement, f"seed.manufacturing_placements[{placement_index}]")
        tile = _pair(placement.get("tile"), f"seed.manufacturing_placements[{placement_index}].tile")
        if tile not in TILES:
            continue
        type_code = _integer(
            placement.get("type"), f"seed.manufacturing_placements[{placement_index}].type"
        )
        anchor = _pair(
            placement.get("anchor"), f"seed.manufacturing_placements[{placement_index}].anchor"
        )
        size = _pair(placement.get("size"), f"seed.manufacturing_placements[{placement_index}].size")
        valid_sizes = {3: {(3, 3)}, 5: {(5, 5)}, 6: {(6, 4), (4, 6)}}.get(type_code)
        if valid_sizes is None or size not in valid_sizes:
            raise D6AntecedentError(f"seed D6 placement {placement_index} has invalid type/size")
        cells = set(_body_cells(anchor, size[0], size[1]))
        tile_bounds = _tile_bounds(tile)
        if not cells or any(not _inside_bounds(cell, tile_bounds) for cell in cells):
            raise D6AntecedentError(f"seed D6 placement {placement_index} leaves its tile")
        if cells & (protected_cells | cycle_cells | pole_cells | occupied):
            raise D6AntecedentError(f"seed D6 placement {placement_index} violates body geometry")
        pole_anchor = pole_by_tile[tile]
        coverage = {
            (x, y)
            for x in range(
                pole_anchor[0] + _integer(offsets["x_min_offset"], "x_min_offset"),
                pole_anchor[0] + _integer(offsets["x_max_offset"], "x_max_offset") + 1,
            )
            for y in range(
                pole_anchor[1] + _integer(offsets["y_min_offset"], "y_min_offset"),
                pole_anchor[1] + _integer(offsets["y_max_offset"], "y_max_offset") + 1,
            )
        }
        if not cells & coverage:
            raise D6AntecedentError(f"seed D6 placement {placement_index} lacks strict power coverage")
        occupied.update(cells)
        selected.append(
            {
                "tile": [tile[0], tile[1]],
                "type": type_code,
                "anchor": [anchor[0], anchor[1]],
                "size": [size[0], size[1]],
            }
        )
    selected.sort(key=lambda item: (item["tile"], item["type"], item["anchor"], item["size"]))
    if len(selected) != D6_AFTER_TOTALS["bodies"]:
        raise D6AntecedentError("seed does not contain exactly 17 D6 placements")
    for tile, counts in TILE_TYPE_COUNTS.items():
        for type_code, expected_count in counts.items():
            actual_count = sum(
                item["tile"] == [tile[0], tile[1]] and item["type"] == type_code for item in selected
            )
            if actual_count != expected_count:
                raise D6AntecedentError(f"seed type count drifted for tile={tile}, type={type_code}")

    if attachment_scope == "seed_narrow":
        expected_x = list(SEED_NARROW_X)
        slots_by_tile = _mapping(
            seed.get("eligible_attachment_slots_by_tile"),
            "seed.eligible_attachment_slots_by_tile",
        )
        actual_slots: list[dict[str, Any]] = []
        for tile in TILES:
            key = f"{tile[0]},{tile[1]}"
            for slot_index, raw_slot in enumerate(_list(slots_by_tile.get(key), f"seed slots {key}")):
                slot = _mapping(raw_slot, f"seed slots {key}[{slot_index}]")
                cycle = _pair(slot.get("cycle"), f"seed slots {key}[{slot_index}].cycle")
                branch = _pair(slot.get("branch"), f"seed slots {key}[{slot_index}].branch")
                actual_slots.append({"cycle": [cycle[0], cycle[1]], "branch": [branch[0], branch[1]]})
        actual_slots.sort(key=lambda item: (item["cycle"], item["branch"]))
        expected_slots = [
            {"cycle": [x, CYCLE_Y], "branch": [x, CYCLE_Y + 1]} for x in expected_x
        ]
        if actual_slots != expected_slots:
            raise D6AntecedentError("seed-narrow attachment slots drifted")
        slots = expected_slots
    elif attachment_scope == "all_legal_d6_slots":
        slots = [
            {"cycle": [x, CYCLE_Y], "branch": [x, CYCLE_Y + 1]}
            for x in range(CYCLE_X_MIN, CYCLE_X_MAX + 1)
        ]
    else:
        raise D6AntecedentError(f"unsupported attachment_scope: {attachment_scope}")
    return selected, slots


def build_d6_antecedent(
    strict_instance: Mapping[str, Any],
    framework: Mapping[str, Any],
    seed: Mapping[str, Any],
    *,
    attachment_scope: str = "all_legal_d6_slots",
) -> dict[str, Any]:
    """Rebuild the exact self-contained local D6 antecedent.

    ``seed.validation_summary.source_sha256`` is intentionally neither read nor
    emitted.  The caller binds actual bytes; this function binds only semantics.
    """

    strict_instance = _mapping(strict_instance, "strict")
    framework = _mapping(framework, "framework")
    seed = _mapping(seed, "seed")
    if attachment_scope != "all_legal_d6_slots":
        raise D6AntecedentError(
            "w0_d6_antecedent_v2 requires attachment_scope=all_legal_d6_slots"
        )
    class_catalog = _derive_class_catalog(strict_instance)
    mode_catalog = _derive_mode_catalog(strict_instance)
    _validate_framework(strict_instance, framework, class_catalog)
    poles, power_rule = _derive_fixed_geometry(strict_instance, framework)
    seed_hints, attachment_slots = _seed_hints_and_slots(
        seed,
        poles,
        power_rule,
        attachment_scope=attachment_scope,
    )
    class_ledger = _build_class_ledger(class_catalog)
    for class_name, class_data in class_catalog.items():
        template = class_data["template"]
        for mode in mode_catalog[template]:
            input_capacity = sum(port["kind"] == "input" for port in mode["ports"])
            output_capacity = sum(port["kind"] == "output" for port in mode["ports"])
            if (
                input_capacity < class_data["input_count"]
                or output_capacity < class_data["output_count"]
            ):
                raise D6AntecedentError(f"strict mode capacity cannot realize class {class_name}")

    antecedent = {
        "schema": ANTECEDENT_SCHEMA,
        "protocol": dict(PROTOCOL),
        "claim_boundary": "exact_local_d6_antecedent_only",
        "benchmark_id": _string(strict_instance.get("benchmark_id"), "strict.benchmark_id"),
        "class_transfer": {
            "profile": CLASS_ALLOCATION_PROFILE,
            "moves": [
                {"from": "D6", "to": "D9", "class": "6B", "count": 1},
                {"from": "D9", "to": "D6", "class": "6G", "count": 1},
            ],
        },
        "class_ledger": class_ledger,
        "attachment_scope": attachment_scope,
        "local_bounds": {
            "x_min": LOCAL_BOUNDS[0],
            "x_max": LOCAL_BOUNDS[1],
            "y_min": LOCAL_BOUNDS[2],
            "y_max": LOCAL_BOUNDS[3],
        },
        "tiles": [
            {
                "tile": [tile[0], tile[1]],
                "bounds": {
                    "x_min": _tile_bounds(tile)[0],
                    "x_max": _tile_bounds(tile)[1],
                    "y_min": _tile_bounds(tile)[2],
                    "y_max": _tile_bounds(tile)[3],
                },
                "type_counts": {
                    str(type_code): TILE_TYPE_COUNTS[tile][type_code] for type_code in (3, 5, 6)
                },
            }
            for tile in TILES
        ],
        "poles": poles,
        "protected_body_only_rect": {
            "anchor": [PROTECTED_ANCHOR[0], PROTECTED_ANCHOR[1]],
            "size": [PROTECTED_SIZE[0], PROTECTED_SIZE[1]],
        },
        "cycle": {
            "y": CYCLE_Y,
            "x_min": CYCLE_X_MIN,
            "x_max": CYCLE_X_MAX,
            "direction": "E",
            "attachment_slots": attachment_slots,
            "roles": {
                "none": {"in_dirs": ["W"], "out_dirs": ["E"]},
                "output_injection": {"in_dirs": ["W", "N"], "out_dirs": ["E"]},
                "input_tap": {"in_dirs": ["W"], "out_dirs": ["E", "N"]},
            },
        },
        "class_counts": {name: CLASS_COUNTS[name] for name in sorted(CLASS_COUNTS)},
        "class_catalog": {name: class_catalog[name] for name in sorted(class_catalog)},
        "mode_catalog": mode_catalog,
        "power_rule": power_rule,
        "routing_patterns": build_legal_routing_patterns(),
        "seed_hints": seed_hints,
        "seed_hint_policy": "add_hint_only_never_constraint",
        "expected_totals": dict(class_ledger["d6"]["after"]["totals"]),
    }
    if antecedent["class_counts"] != {
        name: class_ledger["d6"]["after"]["class_counts"][name]
        for name in sorted(CLASS_COUNTS)
    }:
        raise D6AntecedentError("modeled D6 class counts do not match class ledger after state")
    _canonical_json_bytes(antecedent)
    return antecedent


@dataclass(slots=True)
class _Candidate:
    index: int
    class_name: str
    template: str
    tile: tuple[int, int]
    anchor: tuple[int, int]
    mode: Mapping[str, Any]
    body_cells: tuple[tuple[int, int], ...]
    select: Any
    active_by_port: dict[str, Any]
    front_by_port: dict[str, tuple[int, int]]


@dataclass(slots=True)
class _ModelState:
    model: Any
    candidates: list[_Candidate]
    ground_patterns: dict[str, Mapping[str, Any]]
    elevated_patterns: dict[str, Mapping[str, Any]]
    ground_vars: dict[tuple[tuple[int, int], str], Any]
    elevated_vars: dict[tuple[tuple[int, int], str], Any]
    role_vars: dict[tuple[int, int], dict[str, Any]]
    flow_vars: dict[
        tuple[str, str, str, tuple[int, int], tuple[int, int]], Any
    ]
    cycle_absorptions: dict[tuple[int, int], Any]
    cycle_emissions: dict[tuple[int, int], Any]


def _all_local_cells(antecedent: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    bounds = _mapping(antecedent.get("local_bounds"), "antecedent.local_bounds")
    x_min = _integer(bounds.get("x_min"), "antecedent.local_bounds.x_min")
    x_max = _integer(bounds.get("x_max"), "antecedent.local_bounds.x_max")
    y_min = _integer(bounds.get("y_min"), "antecedent.local_bounds.y_min")
    y_max = _integer(bounds.get("y_max"), "antecedent.local_bounds.y_max")
    return tuple((x, y) for x in range(x_min, x_max + 1) for y in range(y_min, y_max + 1))


def _pattern_lookup(
    patterns: Mapping[str, Mapping[str, Any]],
    *,
    in_dirs: Sequence[str],
    out_dirs: Sequence[str],
) -> str:
    expected_in = _ordered_dirs(in_dirs)
    expected_out = _ordered_dirs(out_dirs)
    matching = [
        name
        for name, pattern in patterns.items()
        if pattern.get("in_dirs") == expected_in and pattern.get("out_dirs") == expected_out
    ]
    if len(matching) != 1:
        raise D6AntecedentError(
            f"expected one routing pattern for in={expected_in}, out={expected_out}; got {matching}"
        )
    return matching[0]


def _is_straight(pattern: Mapping[str, Any]) -> bool:
    inputs = pattern.get("in_dirs")
    outputs = pattern.get("out_dirs")
    return (
        pattern.get("component") in ("belt", "elevated_straight")
        and isinstance(inputs, list)
        and isinstance(outputs, list)
        and len(inputs) == 1
        and len(outputs) == 1
        and outputs[0] == OPPOSITE[inputs[0]]
    )


def _straight_orientation(pattern: Mapping[str, Any]) -> str:
    if not _is_straight(pattern):
        raise ValueError("pattern is not straight")
    return "horizontal" if pattern["in_dirs"][0] in ("E", "W") else "vertical"


def _candidate_geometry_domains(
    antecedent: Mapping[str, Any],
) -> tuple[
    dict[tuple[int, int], tuple[int, int, int, int]],
    dict[tuple[int, int], tuple[int, int]],
    set[tuple[int, int]],
    set[tuple[int, int]],
    dict[tuple[int, int], set[tuple[int, int]]],
]:
    tile_bounds: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for tile_raw in _list(antecedent.get("tiles"), "antecedent.tiles"):
        tile = _mapping(tile_raw, "antecedent.tiles[]")
        tile_key = _pair(tile.get("tile"), "antecedent.tiles[].tile")
        bounds = _mapping(tile.get("bounds"), "antecedent.tiles[].bounds")
        tile_bounds[tile_key] = (
            _integer(bounds.get("x_min"), "tile.bounds.x_min"),
            _integer(bounds.get("x_max"), "tile.bounds.x_max"),
            _integer(bounds.get("y_min"), "tile.bounds.y_min"),
            _integer(bounds.get("y_max"), "tile.bounds.y_max"),
        )
    pole_by_tile: dict[tuple[int, int], tuple[int, int]] = {}
    fixed_body_cells: set[tuple[int, int]] = set()
    for pole_raw in _list(antecedent.get("poles"), "antecedent.poles"):
        pole = _mapping(pole_raw, "antecedent.poles[]")
        tile = _pair(pole.get("tile"), "antecedent.poles[].tile")
        anchor = _pair(pole.get("anchor"), "antecedent.poles[].anchor")
        size = _pair(pole.get("size"), "antecedent.poles[].size")
        pole_by_tile[tile] = anchor
        fixed_body_cells.update(_body_cells(anchor, size[0], size[1]))
    protected = _mapping(
        antecedent.get("protected_body_only_rect"), "antecedent.protected_body_only_rect"
    )
    protected_cells = _rect_cells(
        _pair(protected.get("anchor"), "protected.anchor"),
        _pair(protected.get("size"), "protected.size"),
    )
    cycle = _mapping(antecedent.get("cycle"), "antecedent.cycle")
    cycle_y = _integer(cycle.get("y"), "antecedent.cycle.y")
    cycle_cells = {
        (x, cycle_y)
        for x in range(
            _integer(cycle.get("x_min"), "antecedent.cycle.x_min"),
            _integer(cycle.get("x_max"), "antecedent.cycle.x_max") + 1,
        )
    }
    power = _mapping(antecedent.get("power_rule"), "antecedent.power_rule")
    offsets = _mapping(power.get("coverage_offsets"), "antecedent.power_rule.coverage_offsets")
    coverage_by_tile: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for tile, anchor in pole_by_tile.items():
        coverage_by_tile[tile] = {
            (x, y)
            for x in range(
                anchor[0] + _integer(offsets.get("x_min_offset"), "power.x_min_offset"),
                anchor[0] + _integer(offsets.get("x_max_offset"), "power.x_max_offset") + 1,
            )
            for y in range(
                anchor[1] + _integer(offsets.get("y_min_offset"), "power.y_min_offset"),
                anchor[1] + _integer(offsets.get("y_max_offset"), "power.y_max_offset") + 1,
            )
        }
    return tile_bounds, pole_by_tile, fixed_body_cells, protected_cells | cycle_cells, coverage_by_tile


def _build_exact_model(antecedent: Mapping[str, Any]) -> _ModelState:
    model = cp_model.CpModel()
    expected_totals = _expected_d6_totals(antecedent)
    flow_bound = max(
        expected_totals["active_inputs"],
        expected_totals["active_outputs"],
    )
    local_cells = _all_local_cells(antecedent)
    local_cell_set = set(local_cells)
    tile_bounds, _pole_by_tile, fixed_body_cells, body_forbidden, coverage_by_tile = (
        _candidate_geometry_domains(antecedent)
    )
    class_counts = _mapping(antecedent.get("class_counts"), "antecedent.class_counts")
    class_catalog = _mapping(antecedent.get("class_catalog"), "antecedent.class_catalog")
    mode_catalog = _mapping(antecedent.get("mode_catalog"), "antecedent.mode_catalog")

    candidates: list[_Candidate] = []
    body_covering: dict[tuple[int, int], list[Any]] = defaultdict(list)
    active_front_constraints: list[tuple[Any, tuple[int, int]]] = []
    terminal_endpoints: dict[
        tuple[tuple[int, int], str, str], list[tuple[_Candidate, Mapping[str, Any], Any]]
    ] = defaultdict(list)
    by_class: dict[str, list[_Candidate]] = defaultdict(list)
    by_tile_type: dict[tuple[tuple[int, int], int], list[_Candidate]] = defaultdict(list)

    for class_name in sorted(class_counts):
        class_data = _mapping(class_catalog.get(class_name), f"class_catalog.{class_name}")
        template = _string(class_data.get("template"), f"class_catalog.{class_name}.template")
        input_count = _integer(
            class_data.get("input_count"), f"class_catalog.{class_name}.input_count"
        )
        output_count = _integer(
            class_data.get("output_count"), f"class_catalog.{class_name}.output_count"
        )
        type_code = TYPE_BY_TEMPLATE.get(template)
        if type_code is None:
            raise D6AntecedentError(f"class {class_name} has unsupported template {template}")
        for tile in TILES:
            if TILE_TYPE_COUNTS[tile][type_code] == 0:
                continue
            bounds = tile_bounds[tile]
            for raw_mode in _list(mode_catalog.get(template), f"mode_catalog.{template}"):
                mode = _mapping(raw_mode, f"mode_catalog.{template}[]")
                mode_id = _string(mode.get("id"), f"mode_catalog.{template}[].id")
                body = _mapping(mode.get("body"), f"mode_catalog.{template}.{mode_id}.body")
                width = _positive_integer(body.get("width"), f"{template}.{mode_id}.width")
                height = _positive_integer(body.get("height"), f"{template}.{mode_id}.height")
                ports = [
                    _mapping(port, f"mode_catalog.{template}.{mode_id}.ports[]")
                    for port in _list(mode.get("ports"), f"mode_catalog.{template}.{mode_id}.ports")
                ]
                for anchor_x in range(bounds[0], bounds[1] - width + 2):
                    for anchor_y in range(bounds[2], bounds[3] - height + 2):
                        anchor = (anchor_x, anchor_y)
                        body_cells = _body_cells(anchor, width, height)
                        body_cell_set = set(body_cells)
                        if body_cell_set & (fixed_body_cells | body_forbidden):
                            continue
                        if not body_cell_set & coverage_by_tile[tile]:
                            continue
                        index = len(candidates)
                        select = model.NewBoolVar(
                            f"body_{index}_{class_name}_{tile[0]}_{tile[1]}_"
                            f"{anchor_x}_{anchor_y}_{mode_id}"
                        )
                        active_by_port: dict[str, Any] = {}
                        front_by_port: dict[str, tuple[int, int]] = {}
                        candidate = _Candidate(
                            index=index,
                            class_name=class_name,
                            template=template,
                            tile=tile,
                            anchor=anchor,
                            mode=mode,
                            body_cells=body_cells,
                            select=select,
                            active_by_port=active_by_port,
                            front_by_port=front_by_port,
                        )
                        for port in ports:
                            port_id = _string(port.get("id"), f"{template}.{mode_id}.port.id")
                            kind = _string(port.get("kind"), f"{template}.{mode_id}.{port_id}.kind")
                            direction = _string(
                                port.get("direction"), f"{template}.{mode_id}.{port_id}.direction"
                            )
                            front = compute_active_front(anchor, port)
                            active = model.NewBoolVar(f"active_{index}_{port_id}")
                            model.Add(active <= select)
                            if front not in local_cell_set or front in fixed_body_cells:
                                model.Add(active == 0)
                            active_by_port[port_id] = active
                            front_by_port[port_id] = front
                            active_front_constraints.append((active, front))
                            component_side = OPPOSITE[direction]
                            terminal_endpoints[(front, component_side, kind)].append(
                                (candidate, port, active)
                            )
                        model.Add(
                            sum(
                                active_by_port[_string(port.get("id"), "port.id")]
                                for port in ports
                                if port.get("kind") == "input"
                            )
                            == input_count * select
                        )
                        model.Add(
                            sum(
                                active_by_port[_string(port.get("id"), "port.id")]
                                for port in ports
                                if port.get("kind") == "output"
                            )
                            == output_count * select
                        )
                        candidates.append(candidate)
                        by_class[class_name].append(candidate)
                        by_tile_type[(tile, type_code)].append(candidate)
                        for cell in body_cells:
                            body_covering[cell].append(select)

    for class_name, count_raw in class_counts.items():
        count = _integer(count_raw, f"class_counts.{class_name}")
        model.Add(sum(candidate.select for candidate in by_class[class_name]) == count)
    for tile, counts in TILE_TYPE_COUNTS.items():
        for type_code, count in counts.items():
            model.Add(
                sum(candidate.select for candidate in by_tile_type[(tile, type_code)]) == count
            )
    for cell in local_cells:
        if body_covering[cell]:
            model.Add(sum(body_covering[cell]) <= 1)
    for active, front in active_front_constraints:
        if front in body_covering:
            model.Add(active + sum(body_covering[front]) <= 1)

    # Seed geometry is advisory only.  Each actual tile/type/anchor is mapped
    # to one aggregate Boolean and appears solely in AddHint.
    for hint_index, raw_hint in enumerate(_list(antecedent.get("seed_hints"), "seed_hints")):
        hint = _mapping(raw_hint, f"seed_hints[{hint_index}]")
        tile = _pair(hint.get("tile"), f"seed_hints[{hint_index}].tile")
        type_code = _integer(hint.get("type"), f"seed_hints[{hint_index}].type")
        anchor = _pair(hint.get("anchor"), f"seed_hints[{hint_index}].anchor")
        matching = [
            candidate.select
            for candidate in by_tile_type[(tile, type_code)]
            if candidate.anchor == anchor
        ]
        if not matching:
            raise D6AntecedentError(
                f"seed hint {hint_index} has no legal tile/type/anchor candidate"
            )
        hint_used = model.NewBoolVar(f"seed_anchor_hint_{hint_index}")
        model.Add(hint_used == sum(matching))
        model.AddHint(hint_used, 1)

    routing_patterns = _mapping(antecedent.get("routing_patterns"), "routing_patterns")
    ground_patterns = {
        _string(pattern.get("name"), "ground pattern name"): _mapping(pattern, "ground pattern")
        for pattern in (
            _mapping(raw_pattern, "routing_patterns.ground[]")
            for raw_pattern in _list(routing_patterns.get("ground"), "routing_patterns.ground")
        )
    }
    elevated_patterns = {
        _string(pattern.get("name"), "elevated pattern name"): _mapping(
            pattern, "elevated pattern"
        )
        for pattern in (
            _mapping(raw_pattern, "routing_patterns.elevated[]")
            for raw_pattern in _list(routing_patterns.get("elevated"), "routing_patterns.elevated")
        )
    }
    if len(ground_patterns) != 44 or len(elevated_patterns) != 4:
        raise D6AntecedentError("antecedent routing pattern count drifted")
    ground_vars = {
        (cell, name): model.NewBoolVar(f"ground_{cell[0]}_{cell[1]}_{name}")
        for cell in local_cells
        for name in ground_patterns
    }
    elevated_vars = {
        (cell, name): model.NewBoolVar(f"elevated_{cell[0]}_{cell[1]}_{name}")
        for cell in local_cells
        for name in elevated_patterns
    }

    for cell in local_cells:
        ground_at_cell = [ground_vars[(cell, name)] for name in ground_patterns]
        elevated_at_cell = [elevated_vars[(cell, name)] for name in elevated_patterns]
        if cell in fixed_body_cells:
            model.Add(sum(ground_at_cell) == 0)
            model.Add(sum(elevated_at_cell) == 0)
        else:
            model.Add(sum(ground_at_cell) + sum(body_covering.get(cell, ())) <= 1)
            model.Add(sum(elevated_at_cell) + sum(body_covering.get(cell, ())) <= 1)
        for ground_name, ground_pattern in ground_patterns.items():
            for elevated_name, elevated_pattern in elevated_patterns.items():
                crossing_allowed = (
                    _is_straight(ground_pattern)
                    and _is_straight(elevated_pattern)
                    and _straight_orientation(ground_pattern)
                    != _straight_orientation(elevated_pattern)
                )
                if not crossing_allowed:
                    model.Add(
                        ground_vars[(cell, ground_name)]
                        + elevated_vars[(cell, elevated_name)]
                        <= 1
                    )

    cycle = _mapping(antecedent.get("cycle"), "antecedent.cycle")
    cycle_y = _integer(cycle.get("y"), "antecedent.cycle.y")
    cycle_x_min = _integer(cycle.get("x_min"), "antecedent.cycle.x_min")
    cycle_x_max = _integer(cycle.get("x_max"), "antecedent.cycle.x_max")
    attachment_cells = {
        _pair(_mapping(slot, "attachment slot").get("cycle"), "attachment slot cycle")
        for slot in _list(cycle.get("attachment_slots"), "cycle.attachment_slots")
    }
    straight_name = _pattern_lookup(ground_patterns, in_dirs=["W"], out_dirs=["E"])
    injection_name = _pattern_lookup(
        ground_patterns, in_dirs=["W", "N"], out_dirs=["E"]
    )
    tap_name = _pattern_lookup(ground_patterns, in_dirs=["W"], out_dirs=["E", "N"])
    role_vars: dict[tuple[int, int], dict[str, Any]] = {}
    for x in range(cycle_x_min, cycle_x_max + 1):
        cell = (x, cycle_y)
        if cell in attachment_cells:
            injection = model.NewBoolVar(f"role_output_injection_{x}_{cycle_y}")
            tap = model.NewBoolVar(f"role_input_tap_{x}_{cycle_y}")
            model.Add(injection + tap <= 1)
            model.Add(ground_vars[(cell, injection_name)] == injection)
            model.Add(ground_vars[(cell, tap_name)] == tap)
            model.Add(ground_vars[(cell, straight_name)] + injection + tap == 1)
            role_vars[cell] = {"output_injection": injection, "input_tap": tap}
        else:
            model.Add(ground_vars[(cell, straight_name)] == 1)
    model.Add(sum(roles["output_injection"] for roles in role_vars.values()) >= 1)
    model.Add(sum(roles["input_tap"] for roles in role_vars.values()) >= 1)

    def incidence(
        variables: Mapping[tuple[tuple[int, int], str], Any],
        patterns: Mapping[str, Mapping[str, Any]],
        cell: tuple[int, int],
        direction: str,
        kind: str,
    ) -> Any:
        return sum(
            variables[(cell, name)]
            for name, pattern in patterns.items()
            if direction in pattern[f"{kind}_dirs"]
        )

    endpoint_presence: dict[tuple[tuple[int, int], str, str], Any] = {}
    for endpoint, terminals in terminal_endpoints.items():
        presence = model.NewBoolVar(
            f"terminal_{endpoint[2]}_{endpoint[0][0]}_{endpoint[0][1]}_{endpoint[1]}"
        )
        # Same front/component-side/kind is one physical incidence.  Different
        # sides on the same front remain legal and can meet one merger/splitter.
        model.Add(presence == sum(active for _candidate, _port, active in terminals))
        endpoint_presence[endpoint] = presence

    edge_in_by_layer: dict[tuple[str, tuple[int, int], str], Any] = {}
    edge_out_by_layer: dict[tuple[str, tuple[int, int], str], Any] = {}
    for cell in local_cells:
        for direction in DIRECTIONS:
            delta = DELTA[direction]
            neighbor = (cell[0] + delta[0], cell[1] + delta[1])
            opposite = OPPOSITE[direction]
            boundary_in = int(
                cell == (cycle_x_min, cycle_y) and direction == "W"
            )
            boundary_out = int(
                cell == (cycle_x_max, cycle_y) and direction == "E"
            )
            terminal_output = endpoint_presence.get((cell, direction, "output"), 0)
            terminal_input = endpoint_presence.get((cell, direction, "input"), 0)
            source_here = terminal_output + boundary_in
            sink_here = terminal_input + boundary_out
            ground_in_here = incidence(
                ground_vars, ground_patterns, cell, direction, "in"
            )
            ground_out_here = incidence(
                ground_vars, ground_patterns, cell, direction, "out"
            )
            model.Add(source_here <= ground_in_here)
            model.Add(sink_here <= ground_out_here)
            ground_edge_in = ground_in_here - source_here
            ground_edge_out = ground_out_here - sink_here
            elevated_in_here = incidence(
                elevated_vars, elevated_patterns, cell, direction, "in"
            )
            elevated_out_here = incidence(
                elevated_vars, elevated_patterns, cell, direction, "out"
            )
            edge_in_by_layer[("ground", cell, direction)] = ground_edge_in
            edge_out_by_layer[("ground", cell, direction)] = ground_edge_out
            edge_in_by_layer[("elevated", cell, direction)] = elevated_in_here
            edge_out_by_layer[("elevated", cell, direction)] = elevated_out_here
            if neighbor in local_cell_set:
                neighbor_boundary_in = int(
                    neighbor == (cycle_x_min, cycle_y) and opposite == "W"
                )
                neighbor_boundary_out = int(
                    neighbor == (cycle_x_max, cycle_y) and opposite == "E"
                )
                source_neighbor = (
                    endpoint_presence.get((neighbor, opposite, "output"), 0)
                    + neighbor_boundary_in
                )
                sink_neighbor = (
                    endpoint_presence.get((neighbor, opposite, "input"), 0)
                    + neighbor_boundary_out
                )
                ground_neighbor_out = incidence(
                    ground_vars,
                    ground_patterns,
                    neighbor,
                    opposite,
                    "out",
                )
                ground_neighbor_in = incidence(
                    ground_vars,
                    ground_patterns,
                    neighbor,
                    opposite,
                    "in",
                )
                elevated_neighbor_out = incidence(
                    elevated_vars,
                    elevated_patterns,
                    neighbor,
                    opposite,
                    "out",
                )
                elevated_neighbor_in = incidence(
                    elevated_vars,
                    elevated_patterns,
                    neighbor,
                    opposite,
                    "in",
                )
                # Strict continuity and directed-edge balance aggregate the two
                # layers at a cell boundary.  Therefore a channel may change
                # layer between adjacent cells.  Transfer remains forbidden
                # between the two perpendicular channels of a same-cell cross.
                model.Add(
                    ground_edge_in + elevated_in_here
                    == ground_neighbor_out - sink_neighbor + elevated_neighbor_out
                )
                model.Add(
                    ground_edge_out + elevated_out_here
                    == ground_neighbor_in - source_neighbor + elevated_neighbor_in
                )
            else:
                model.Add(ground_edge_in + elevated_in_here == 0)
                model.Add(ground_edge_out + elevated_out_here == 0)

    flow_vars: dict[
        tuple[str, str, str, tuple[int, int], tuple[int, int]], Any
    ] = {}
    for polarity in ("OUT", "IN"):
        for cell in local_cells:
            for direction in DIRECTIONS:
                delta = DELTA[direction]
                neighbor = (cell[0] + delta[0], cell[1] + delta[1])
                if neighbor not in local_cell_set:
                    continue
                opposite = OPPOSITE[direction]
                for from_layer in ("ground", "elevated"):
                    for to_layer in ("ground", "elevated"):
                        flow = model.NewIntVar(
                            0,
                            flow_bound,
                            f"flow_{polarity}_{from_layer}_{to_layer}_"
                            f"{cell[0]}_{cell[1]}_{neighbor[0]}_{neighbor[1]}",
                        )
                        model.Add(
                            flow
                            <= flow_bound
                            * edge_out_by_layer[(from_layer, cell, direction)]
                        )
                        model.Add(
                            flow
                            <= flow_bound
                            * edge_in_by_layer[(to_layer, neighbor, opposite)]
                        )
                        flow_vars[
                            (polarity, from_layer, to_layer, cell, neighbor)
                        ] = flow

    output_sources_by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    input_sinks_by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for (front, _side, kind), terminals in terminal_endpoints.items():
        target = output_sources_by_cell if kind == "output" else input_sinks_by_cell
        target[front].extend(active for _candidate, _port, active in terminals)

    cycle_absorptions: dict[tuple[int, int], Any] = {}
    cycle_emissions: dict[tuple[int, int], Any] = {}
    for cell, roles in role_vars.items():
        absorption = model.NewIntVar(0, flow_bound, f"cycle_out_absorb_{cell[0]}_{cell[1]}")
        emission = model.NewIntVar(0, flow_bound, f"cycle_in_emit_{cell[0]}_{cell[1]}")
        model.Add(absorption <= flow_bound * roles["output_injection"])
        model.Add(absorption >= roles["output_injection"])
        model.Add(emission <= flow_bound * roles["input_tap"])
        model.Add(emission >= roles["input_tap"])
        cycle_absorptions[cell] = absorption
        cycle_emissions[cell] = emission
    model.Add(sum(cycle_absorptions.values()) == expected_totals["active_outputs"])
    model.Add(sum(cycle_emissions.values()) == expected_totals["active_inputs"])

    for polarity in ("OUT", "IN"):
        for layer in ("ground", "elevated"):
            for cell in local_cells:
                incoming = sum(
                    flow
                    for (
                        flow_polarity,
                        _from_layer,
                        to_layer,
                        _source,
                        target,
                    ), flow in flow_vars.items()
                    if flow_polarity == polarity
                    and to_layer == layer
                    and target == cell
                )
                outgoing = sum(
                    flow
                    for (
                        flow_polarity,
                        from_layer,
                        _to_layer,
                        source,
                        _target,
                    ), flow in flow_vars.items()
                    if flow_polarity == polarity
                    and from_layer == layer
                    and source == cell
                )
                if layer == "ground" and polarity == "OUT":
                    model.Add(
                        incoming + sum(output_sources_by_cell.get(cell, ()))
                        == outgoing + cycle_absorptions.get(cell, 0)
                    )
                elif layer == "ground":
                    model.Add(
                        incoming + cycle_emissions.get(cell, 0)
                        == outgoing + sum(input_sinks_by_cell.get(cell, ()))
                    )
                else:
                    # Separate conservation on each layer makes legal crossings
                    # transfer-free, rather than merely drawing perpendicular
                    # straight symbols at one coordinate.
                    model.Add(incoming == outgoing)

    return _ModelState(
        model=model,
        candidates=candidates,
        ground_patterns=ground_patterns,
        elevated_patterns=elevated_patterns,
        ground_vars=ground_vars,
        elevated_vars=elevated_vars,
        role_vars=role_vars,
        flow_vars=flow_vars,
        cycle_absorptions=cycle_absorptions,
        cycle_emissions=cycle_emissions,
    )


class _ReachabilityGuardError(RuntimeError):
    pass


def _node(layer: str, cell: tuple[int, int]) -> tuple[str, int, int]:
    return layer, cell[0], cell[1]


def _node_record(node: tuple[str, int, int]) -> dict[str, Any]:
    return {"cell": [node[1], node[2]], "layer": node[0]}


def _shortest_path_to_any(
    graph: Mapping[tuple[str, int, int], set[tuple[str, int, int]]],
    start: tuple[str, int, int],
    targets: set[tuple[str, int, int]],
) -> list[tuple[str, int, int]] | None:
    queue: deque[tuple[str, int, int]] = deque([start])
    parent: dict[tuple[str, int, int], tuple[str, int, int] | None] = {start: None}
    reached: tuple[str, int, int] | None = None
    while queue:
        current = queue.popleft()
        if current in targets:
            reached = current
            break
        for neighbor in sorted(graph.get(current, ())):
            if neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)
    if reached is None:
        return None
    path: list[tuple[str, int, int]] = []
    cursor: tuple[str, int, int] | None = reached
    while cursor is not None:
        path.append(cursor)
        cursor = parent[cursor]
    path.reverse()
    return path


def _selected_pattern(
    solver: Any,
    variables: Mapping[tuple[tuple[int, int], str], Any],
    patterns: Mapping[str, Mapping[str, Any]],
    cell: tuple[int, int],
) -> dict[str, Any] | None:
    selected = [name for name in patterns if solver.Value(variables[(cell, name)]) == 1]
    if len(selected) > 1:
        raise _ReachabilityGuardError(f"multiple transport patterns selected at {cell}")
    if not selected:
        return None
    pattern = patterns[selected[0]]
    return {
        "pattern": selected[0],
        "in_dirs": list(pattern["in_dirs"]),
        "out_dirs": list(pattern["out_dirs"]),
    }


def _extract_configuration(
    antecedent: Mapping[str, Any],
    antecedent_sha256: str,
    state: _ModelState,
    solver: Any,
) -> dict[str, Any]:
    expected_totals = _expected_d6_totals(antecedent)
    selected_candidates = [
        candidate for candidate in state.candidates if solver.Value(candidate.select) == 1
    ]
    selected_candidates.sort(
        key=lambda candidate: (
            candidate.class_name,
            candidate.tile,
            candidate.anchor,
            candidate.mode["id"],
        )
    )
    if len(selected_candidates) != expected_totals["bodies"]:
        raise _ReachabilityGuardError("solver selected an unexpected number of D6 bodies")

    bodies: list[dict[str, Any]] = []
    active_terminals: dict[str, list[dict[str, Any]]] = {"input": [], "output": []}
    for body_index, candidate in enumerate(selected_candidates):
        body_id = f"body_{body_index:03d}"
        active_ports: list[dict[str, Any]] = []
        active_inputs: list[str] = []
        active_outputs: list[str] = []
        for raw_port in _list(candidate.mode.get("ports"), "selected mode ports"):
            port = _mapping(raw_port, "selected mode port")
            port_id = _string(port.get("id"), "selected mode port id")
            if solver.Value(candidate.active_by_port[port_id]) != 1:
                continue
            kind = _string(port.get("kind"), f"selected port {port_id}.kind")
            direction = _string(port.get("direction"), f"selected port {port_id}.direction")
            body_cell = _pair(port.get("body_cell"), f"selected port {port_id}.body_cell")
            front = candidate.front_by_port[port_id]
            port_record = {
                "id": port_id,
                "kind": kind,
                "body_cell": [body_cell[0], body_cell[1]],
                "direction": direction,
                "front": [front[0], front[1]],
            }
            active_ports.append(port_record)
            if kind == "input":
                active_inputs.append(port_id)
            else:
                active_outputs.append(port_id)
            active_terminals[kind].append(
                {
                    "body_id": body_id,
                    "port_id": port_id,
                    "cell": [front[0], front[1]],
                    "amount": 1,
                }
            )
        bodies.append(
            {
                "id": body_id,
                "class": candidate.class_name,
                "template": candidate.template,
                "tile": [candidate.tile[0], candidate.tile[1]],
                "anchor": [candidate.anchor[0], candidate.anchor[1]],
                "mode": _string(candidate.mode.get("id"), "selected mode id"),
                "active_inputs": sorted(active_inputs),
                "active_outputs": sorted(active_outputs),
                "ports": sorted(active_ports, key=lambda item: item["id"]),
            }
        )
    active_terminals["input"].sort(
        key=lambda item: (item["body_id"], item["port_id"], item["cell"])
    )
    active_terminals["output"].sort(
        key=lambda item: (item["body_id"], item["port_id"], item["cell"])
    )
    if len(active_terminals["input"]) != expected_totals["active_inputs"]:
        raise _ReachabilityGuardError(
            f"selected body inputs do not total {expected_totals['active_inputs']}"
        )
    if len(active_terminals["output"]) != expected_totals["active_outputs"]:
        raise _ReachabilityGuardError(
            f"selected body outputs do not total {expected_totals['active_outputs']}"
        )

    local_cells = _all_local_cells(antecedent)
    transport: list[dict[str, Any]] = []
    for cell in sorted(local_cells):
        ground = _selected_pattern(
            solver, state.ground_vars, state.ground_patterns, cell
        )
        elevated = _selected_pattern(
            solver, state.elevated_vars, state.elevated_patterns, cell
        )
        if ground is not None or elevated is not None:
            transport.append(
                {
                    "cell": [cell[0], cell[1]],
                    "ground": ground,
                    "elevated": elevated,
                }
            )

    cycle_roles: list[dict[str, Any]] = []
    for cell, roles in sorted(state.role_vars.items()):
        if solver.Value(roles["output_injection"]) == 1:
            cycle_roles.append(
                {"cell": [cell[0], cell[1]], "role": "output_injection"}
            )
        elif solver.Value(roles["input_tap"]) == 1:
            cycle_roles.append({"cell": [cell[0], cell[1]], "role": "input_tap"})

    flow_payloads: dict[str, dict[str, Any]] = {}
    positive_graphs: dict[
        str, dict[tuple[str, int, int], set[tuple[str, int, int]]]
    ] = {}
    for polarity in ("OUT", "IN"):
        arcs: list[dict[str, Any]] = []
        graph: dict[tuple[str, int, int], set[tuple[str, int, int]]] = defaultdict(set)
        for (
            flow_polarity,
            from_layer,
            to_layer,
            source,
            target,
        ), variable in sorted(
            state.flow_vars.items(),
            key=lambda item: item[0],
        ):
            if flow_polarity != polarity:
                continue
            amount = int(solver.Value(variable))
            if amount <= 0:
                continue
            arcs.append(
                {
                    "from_layer": from_layer,
                    "to_layer": to_layer,
                    "from": [source[0], source[1]],
                    "to": [target[0], target[1]],
                    "amount": amount,
                }
            )
            graph[_node(from_layer, source)].add(_node(to_layer, target))
        positive_graphs[polarity] = graph
        flow_payloads[polarity] = {"arcs": arcs}

    cycle_absorptions = [
        {"cell": [cell[0], cell[1]], "amount": int(solver.Value(variable))}
        for cell, variable in sorted(state.cycle_absorptions.items())
        if solver.Value(variable) > 0
    ]
    cycle_emissions = [
        {"cell": [cell[0], cell[1]], "amount": int(solver.Value(variable))}
        for cell, variable in sorted(state.cycle_emissions.items())
        if solver.Value(variable) > 0
    ]
    if (
        sum(record["amount"] for record in cycle_absorptions)
        != expected_totals["active_outputs"]
    ):
        raise _ReachabilityGuardError("OUT cycle absorption total drifted")
    if (
        sum(record["amount"] for record in cycle_emissions)
        != expected_totals["active_inputs"]
    ):
        raise _ReachabilityGuardError("IN cycle emission total drifted")

    out_targets = {
        _node("ground", _pair(record["cell"], "cycle absorption cell"))
        for record in cycle_absorptions
    }
    out_reachability: list[dict[str, Any]] = []
    for terminal in active_terminals["output"]:
        start = _node("ground", _pair(terminal["cell"], "output terminal cell"))
        path = _shortest_path_to_any(positive_graphs["OUT"], start, out_targets)
        if path is None:
            raise _ReachabilityGuardError(
                f"OUT terminal {terminal['body_id']}:{terminal['port_id']} lacks an injection path"
            )
        out_reachability.append(
            {
                "body_id": terminal["body_id"],
                "port_id": terminal["port_id"],
                "path": [_node_record(path_node) for path_node in path],
                "sink": [path[-1][1], path[-1][2]],
            }
        )

    in_sources = {
        _node("ground", _pair(record["cell"], "cycle emission cell"))
        for record in cycle_emissions
    }
    reverse_in_graph: dict[
        tuple[str, int, int], set[tuple[str, int, int]]
    ] = defaultdict(set)
    for source, targets in positive_graphs["IN"].items():
        for target in targets:
            reverse_in_graph[target].add(source)
    in_reachability: list[dict[str, Any]] = []
    for terminal in active_terminals["input"]:
        target = _node("ground", _pair(terminal["cell"], "input terminal cell"))
        reverse_path = _shortest_path_to_any(reverse_in_graph, target, in_sources)
        if reverse_path is None:
            raise _ReachabilityGuardError(
                f"IN terminal {terminal['body_id']}:{terminal['port_id']} lacks a tap path"
            )
        path = list(reversed(reverse_path))
        in_reachability.append(
            {
                "body_id": terminal["body_id"],
                "port_id": terminal["port_id"],
                "path": [_node_record(path_node) for path_node in path],
                "source": [path[0][1], path[0][2]],
            }
        )

    flow_payloads["OUT"].update(
        {
            "terminal_emissions": active_terminals["output"],
            "cycle_absorptions": cycle_absorptions,
            "reachability": out_reachability,
        }
    )
    flow_payloads["IN"].update(
        {
            "cycle_emissions": cycle_emissions,
            "terminal_absorptions": active_terminals["input"],
            "reachability": in_reachability,
        }
    )
    configuration = {
        "schema": CONFIGURATION_SCHEMA,
        "antecedent_sha256": antecedent_sha256,
        "claim_boundary": FEASIBLE_BOUNDARY,
        "bodies": bodies,
        "transport": transport,
        "cycle_roles": cycle_roles,
        "flows": flow_payloads,
    }
    _canonical_json_bytes(configuration)
    return configuration


def _solver_statistics(
    solver: Any | None,
    *,
    workers: int,
    random_seed: int,
    max_time_ms: int,
) -> dict[str, Any]:
    if solver is None:
        return {
            "wall_time_ms": 0,
            "num_conflicts": 0,
            "num_branches": 0,
            "response_stats": "",
            "workers": workers,
            "random_seed": random_seed,
            "max_time_ms": max_time_ms,
        }
    return {
        "wall_time_ms": int(round(float(solver.WallTime()) * 1000)),
        "num_conflicts": int(solver.NumConflicts()),
        "num_branches": int(solver.NumBranches()),
        "response_stats": str(solver.ResponseStats()),
        "workers": workers,
        "random_seed": random_seed,
        "max_time_ms": max_time_ms,
    }


def _gate_result(
    *,
    status: str,
    status_detail: str,
    claim_boundary: str,
    antecedent_sha256: str,
    solver_statistics: Mapping[str, Any],
    configuration: Mapping[str, Any] | None = None,
    certificate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "schema": GATE_RESULT_SCHEMA,
        "status": status,
        "status_detail": status_detail,
        "claim_boundary": claim_boundary,
        "antecedent_sha256": antecedent_sha256,
        "solver_statistics": dict(solver_statistics),
        "configuration": dict(configuration) if configuration is not None else None,
        "certificate": dict(certificate) if certificate is not None else None,
    }
    _canonical_json_bytes(result)
    return result


def solve_d6_joint_completion(
    strict_instance: Mapping[str, Any],
    framework: Mapping[str, Any],
    seed: Mapping[str, Any],
    *,
    antecedent: Mapping[str, Any] | None = None,
    attachment_scope: str = "all_legal_d6_slots",
    workers: int = 1,
    random_seed: int = 0,
    max_time_seconds: float = 60.0,
) -> dict[str, Any]:
    """Solve one exact D6 local antecedent and return a bounded three-way result."""

    if type(workers) is not int or workers <= 0:
        raise ValueError("workers must be a positive integer")
    if type(random_seed) is not int or random_seed < 0:
        raise ValueError("random_seed must be a nonnegative integer")
    if (
        isinstance(max_time_seconds, bool)
        or not isinstance(max_time_seconds, (int, float))
        or not math.isfinite(float(max_time_seconds))
        or float(max_time_seconds) <= 0.0
    ):
        raise ValueError("max_time_seconds must be finite and positive")
    max_time_ms = max(1, int(round(float(max_time_seconds) * 1000)))

    rebuilt = build_d6_antecedent(
        strict_instance,
        framework,
        seed,
        attachment_scope=attachment_scope,
    )
    if antecedent is not None:
        supplied = _mapping(antecedent, "antecedent")
        _canonical_json_bytes(supplied)
        if supplied != rebuilt:
            raise D6AntecedentError("supplied antecedent does not equal independent rebuild")
        exact_antecedent: Mapping[str, Any] = supplied
    else:
        exact_antecedent = rebuilt
    antecedent_sha256 = _canonical_sha256(exact_antecedent)
    state = _build_exact_model(exact_antecedent)
    validation_error = state.model.Validate()
    if validation_error:
        return _gate_result(
            status="UNKNOWN",
            status_detail=f"cp_sat_model_invalid:{validation_error}",
            claim_boundary=UNKNOWN_BOUNDARY,
            antecedent_sha256=antecedent_sha256,
            solver_statistics=_solver_statistics(
                None,
                workers=workers,
                random_seed=random_seed,
                max_time_ms=max_time_ms,
            ),
        )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_time_seconds)
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = random_seed
    solver.parameters.stop_after_first_solution = True
    # Deliberately let KeyboardInterrupt propagate to the run supervisor.  The
    # supervisor owns the receipt-last interrupted UNKNOWN path and exit 130;
    # swallowing it here would misrecord an interruption as an ordinary solve.
    status = solver.Solve(state.model)

    statistics = _solver_statistics(
        solver,
        workers=workers,
        random_seed=random_seed,
        max_time_ms=max_time_ms,
    )
    if status == cp_model.INFEASIBLE:
        return _gate_result(
            status="INFEASIBLE",
            status_detail="cp_sat_proved_infeasible",
            claim_boundary=INFEASIBLE_BOUNDARY,
            antecedent_sha256=antecedent_sha256,
            solver_statistics=statistics,
        )
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _gate_result(
            status="UNKNOWN",
            status_detail=f"cp_sat_{solver.StatusName(status).lower()}",
            claim_boundary=UNKNOWN_BOUNDARY,
            antecedent_sha256=antecedent_sha256,
            solver_statistics=statistics,
        )

    try:
        configuration = _extract_configuration(
            exact_antecedent,
            antecedent_sha256,
            state,
            solver,
        )
    except _ReachabilityGuardError as exc:
        return _gate_result(
            status="UNKNOWN",
            status_detail=f"postsolve_reachability_guard_failed:{exc}",
            claim_boundary=UNKNOWN_BOUNDARY,
            antecedent_sha256=antecedent_sha256,
            solver_statistics=statistics,
        )
    configuration_sha256 = _canonical_sha256(configuration)
    certificate = {
        "schema": CERTIFICATE_SCHEMA,
        "status": "FEASIBLE",
        "claim_boundary": FEASIBLE_BOUNDARY,
        "antecedent_sha256": antecedent_sha256,
        "configuration_sha256": configuration_sha256,
    }
    return _gate_result(
        status="FEASIBLE",
        status_detail="cp_sat_feasible_and_reachability_guard_passed",
        claim_boundary=FEASIBLE_BOUNDARY,
        antecedent_sha256=antecedent_sha256,
        solver_statistics=statistics,
        configuration=configuration,
        certificate=certificate,
    )


__all__ = [
    "ANTECEDENT_SCHEMA",
    "CERTIFICATE_SCHEMA",
    "CLASS_ALLOCATION_PROFILE",
    "COHORT",
    "CONFIGURATION_SCHEMA",
    "D6AntecedentError",
    "FEASIBLE_BOUNDARY",
    "GATE_RESULT_SCHEMA",
    "INFEASIBLE_BOUNDARY",
    "PROJECT_LOCK_SHA256",
    "PROTOCOL",
    "UNKNOWN_BOUNDARY",
    "build_d6_antecedent",
    "build_legal_routing_patterns",
    "compute_active_front",
    "solve_d6_joint_completion",
]
