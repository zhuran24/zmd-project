#!/usr/bin/env python3
"""Encode the R3 ``(1190, 34)`` upper-bound arithmetic layer as OPB.

This research-only encoder assumes the geometric membrane and power-halo
lemmas reviewed in the pinned R3 evidence.  It independently rebuilds their
strict-instance arithmetic, emits a provenance-bound in-memory size estimate,
and only encodes from an unchanged GO estimate.  It does not make a witness,
attainability, solver-UNSAT, proof-verification, or global-optimality claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_SCHEMA = "r3_upper_bound_pb_v1"
METADATA_SCHEMA = "r3_upper_bound_pb_metadata_v1"
VAR_MAP_SCHEMA = "r3_upper_bound_pb_var_map_v1"
ESTIMATE_SCHEMA = "r3_upper_bound_pb_estimate_v1"
SEMANTICS = "r3_strict_upper_bound_1190_34_arithmetic_given_geometry_v1"
HARNESS = "r3_upper_bound_pb_encoder_v1"

TARGET_AREA = 1_190
TARGET_MIN_SIDE = 34
MEMBRANE_EXTERNAL_CONSTANT = 580
MEMBRANE_INCIDENCE_CAP = 4
FREE_CELL_CAP = 1_320
PLANNING_FLOOR_BYTES = 512 * 1024 * 1024
PLANNING_OPB_MULTIPLIER = 1_024

STRICT_ROOT = Path("docs/research/cleanroom_rederivation_20260718/strict/external")
INPUT_PATHS = {
    "problem_instance": STRICT_ROOT / "problem_instance.json",
    "problem_instance_schema": STRICT_ROOT / "problem_instance.schema.json",
    "problem_md": STRICT_ROOT / "problem.md",
    "sha256s": STRICT_ROOT / "SHA256SUMS",
}
EVIDENCE_PATHS = {
    "r3_response": Path(
        "docs/research/cleanroom_rederivation_20260718/09_r3_response_gpt_pro_verbatim.md"
    ),
    "r3_judgment": Path(
        "docs/research/cleanroom_rederivation_20260718/10_r3_judgment_20260720.md"
    ),
    "r3_adversarial_verdict": Path(
        "docs/research/cleanroom_rederivation_20260718/11_r3_adversarial_verdict_20260720.md"
    ),
    "independent_recomputation": Path(
        "docs/research/cleanroom_rederivation_20260718/verify_r3_certificates.py"
    ),
}
EXPECTED_INPUT_SHA256 = {
    "problem_instance": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    "problem_instance_schema": "5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23",
    "problem_md": "c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f",
    "sha256s": "8810d5d6a80d92438628b7694216d3b3c6c1be50543072ec9c3bcf510d9c4d70",
}
EXPECTED_EVIDENCE_SHA256 = {
    "r3_response": "f0670a76fbd57cabcd41d50823421921d336b50fd36da61e6ab5b2f408c4a700",
    "r3_judgment": "8651e8b5a6deb255824293dc2bad35394c7e5d4143cc82ff0ed674ab93adb89e",
    "r3_adversarial_verdict": "d48ba75040c61d042d091a893f0331b837ebc994d2b18ad429bcb9fef4856da0",
    "independent_recomputation": "589b87a086f2c25015b535c5c12d68b6842aaa1f16fe449bcb94e3a733bd076a",
}

# Certificate data are doubled so every local halo check uses exact integers.
HALO_ORBIT_DOUBLED_WEIGHTS = {
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


class EncoderError(ValueError):
    """Raised when the strict arithmetic cannot be translated exactly."""


@dataclass(frozen=True, slots=True)
class Snapshot:
    key: str
    path: Path
    display_path: str
    raw: bytes
    sha256: str

    @property
    def text(self) -> str:
        return self.raw.decode("utf-8")

    def record(self) -> dict[str, Any]:
        return {
            "path": self.display_path,
            "sha256": self.sha256,
            "size_bytes": len(self.raw),
        }


@dataclass(frozen=True, slots=True)
class Constraint:
    terms: tuple[tuple[int, int], ...]
    relation: str
    rhs: int

    def render(self) -> str:
        body = " ".join(
            f"{'+' if coefficient >= 0 else ''}{coefficient} x{variable}"
            for variable, coefficient in self.terms
        )
        return f"{body} {self.relation} {self.rhs} ;"


class VariableRecord(dict[str, Any]):
    """JSON-object selector record with convenient typed dimension access."""

    @property
    def width(self) -> int:
        return int(self["width"])

    @property
    def height(self) -> int:
        return int(self["height"])


@dataclass(slots=True)
class DerivedModel:
    variables: list[VariableRecord]
    constraints: list[Constraint]
    oriented_dimensions: tuple[tuple[int, int], ...]
    derived_facts: dict[str, Any]
    counts: dict[str, int]


def _exact_int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise EncoderError(f"{field} must be an exact integer")
    return int(value)


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EncoderError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EncoderError(f"{field} must be an array")
    return value


def _expect(value: Any, expected: Any, field: str) -> None:
    if value != expected or type(value) is not type(expected):
        raise EncoderError(f"{field} must be {expected!r}, got {value!r}")


def _reject_constant(value: str) -> Any:
    raise EncoderError(f"non-finite JSON number is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EncoderError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def loads_strict_json(text: str) -> Any:
    """Load JSON while rejecting duplicate keys and non-finite numbers."""

    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise EncoderError(f"invalid JSON: {exc}") from exc


def _display_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(project_root.resolve()))
    except ValueError:
        return str(resolved)


def _snapshot(key: str, path: Path, project_root: Path) -> Snapshot:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"missing provenance file {key}: {resolved}")
    raw = resolved.read_bytes()
    return Snapshot(
        key=key,
        path=resolved,
        display_path=_display_path(resolved, project_root),
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def _verify_expected_hashes(
    snapshots: Mapping[str, Snapshot], expected: Mapping[str, str], label: str
) -> None:
    if set(snapshots) != set(expected):
        raise EncoderError(f"{label} provenance key set drifted")
    for key, expected_digest in expected.items():
        if snapshots[key].sha256 != expected_digest:
            raise EncoderError(f"{label} SHA256 mismatch for {key}")


def _verify_sha256_manifest(inputs: Mapping[str, Snapshot]) -> None:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(inputs["sha256s"].text.splitlines(), 1):
        if not raw_line:
            continue
        parts = raw_line.split("  ")
        if len(parts) != 2 or len(parts[0]) != 64:
            raise EncoderError(f"malformed SHA256SUMS line {line_number}")
        digest, name = parts
        if any(character not in "0123456789abcdef" for character in digest):
            raise EncoderError(f"invalid SHA256 digest on manifest line {line_number}")
        if name in entries:
            raise EncoderError(f"duplicate SHA256SUMS entry: {name}")
        entries[name] = digest
    expected_entries = {
        "R1_prompt.md": "5154e299b472e0f3c50507fa2820e86b480789f50e2608f4d8ca455cefb7c916",
        **{
            inputs[key].path.name: inputs[key].sha256
            for key in ("problem_instance", "problem_instance_schema", "problem_md")
        },
    }
    if entries != expected_entries:
        raise EncoderError("SHA256SUMS does not exactly match the four-entry strict manifest")


def load_bound_snapshots(project_root: Path) -> tuple[dict[str, Snapshot], dict[str, Snapshot]]:
    """Load and hash-close the strict bundle and the R3 review evidence."""

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root does not exist: {root}")
    inputs = {key: _snapshot(key, root / path, root) for key, path in INPUT_PATHS.items()}
    evidence = {key: _snapshot(key, root / path, root) for key, path in EVIDENCE_PATHS.items()}
    _verify_expected_hashes(inputs, EXPECTED_INPUT_SHA256, "strict input")
    _verify_expected_hashes(evidence, EXPECTED_EVIDENCE_SHA256, "R3 evidence")
    loads_strict_json(inputs["problem_instance_schema"].text)
    _verify_sha256_manifest(inputs)
    return inputs, evidence


def _mode_body_area(template: Mapping[str, Any], field: str) -> int:
    modes = _array(template.get("modes"), f"{field}.modes")
    if not modes:
        raise EncoderError(f"{field}.modes must not be empty")
    areas: set[int] = set()
    for index, raw_mode in enumerate(modes):
        mode = _object(raw_mode, f"{field}.modes[{index}]")
        body = _object(mode.get("body"), f"{field}.modes[{index}].body")
        width = _exact_int(body.get("width"), f"{field}.modes[{index}].body.width")
        height = _exact_int(body.get("height"), f"{field}.modes[{index}].body.height")
        if width <= 0 or height <= 0:
            raise EncoderError(f"{field} body dimensions must be positive")
        areas.add(width * height)
    if len(areas) != 1:
        raise EncoderError(f"{field} modes disagree on body area")
    return next(iter(areas))


def _mode_port_count(template: Mapping[str, Any], field: str) -> int:
    counts = {
        len(_array(_object(raw_mode, f"{field}.mode").get("ports"), f"{field}.mode.ports"))
        for raw_mode in _array(template.get("modes"), f"{field}.modes")
    }
    if len(counts) != 1:
        raise EncoderError(f"{field} modes disagree on physical port count")
    return next(iter(counts))


def _port_count(template: Mapping[str, Any], kind: str, field: str) -> int:
    counts: set[int] = set()
    for index, raw_mode in enumerate(_array(template.get("modes"), f"{field}.modes")):
        mode = _object(raw_mode, f"{field}.modes[{index}]")
        ports = _array(mode.get("ports"), f"{field}.modes[{index}].ports")
        counts.add(
            sum(_object(port, f"{field}.modes[{index}].port").get("kind") == kind for port in ports)
        )
    if len(counts) != 1:
        raise EncoderError(f"{field} modes disagree on {kind} port count")
    return next(iter(counts))


def _need_total(group: Mapping[str, Any], kind: str, field: str) -> int:
    needs = _object(group.get("port_needs"), f"{field}.port_needs")
    raw = needs.get(kind)
    if isinstance(raw, Mapping):
        total = 0
        for commodity, value in raw.items():
            if type(commodity) is not str or not commodity:
                raise EncoderError(f"{field}.{kind} has an invalid commodity key")
            amount = _exact_int(value, f"{field}.{kind}.{commodity}")
            if amount < 0:
                raise EncoderError(f"{field}.{kind}.{commodity} must be nonnegative")
            total += amount
        return total
    total = _exact_int(raw, f"{field}.{kind}")
    if total < 0:
        raise EncoderError(f"{field}.{kind} must be nonnegative")
    return total


def _port_side_span(mode: Mapping[str, Any], direction: str, field: str) -> int:
    body = _object(mode.get("body"), f"{field}.body")
    width = _exact_int(body.get("width"), f"{field}.body.width")
    height = _exact_int(body.get("height"), f"{field}.body.height")
    if direction in {"N", "S"}:
        return width
    if direction in {"E", "W"}:
        return height
    raise EncoderError(f"{field} has invalid direction {direction!r}")


def _validate_mode_ports(mode: Mapping[str, Any], directions: set[str], field: str) -> None:
    body = _object(mode.get("body"), f"{field}.body")
    width = _exact_int(body.get("width"), f"{field}.body.width")
    height = _exact_int(body.get("height"), f"{field}.body.height")
    seen: set[tuple[int, int, str]] = set()
    for index, raw_port in enumerate(_array(mode.get("ports"), f"{field}.ports")):
        port = _object(raw_port, f"{field}.ports[{index}]")
        direction = port.get("direction")
        if type(direction) is not str or direction not in directions:
            raise EncoderError(f"{field}.ports[{index}] has an invalid direction")
        cell = _object(port.get("body_cell"), f"{field}.ports[{index}].body_cell")
        x_value = _exact_int(cell.get("x"), f"{field}.ports[{index}].body_cell.x")
        y_value = _exact_int(cell.get("y"), f"{field}.ports[{index}].body_cell.y")
        if not (0 <= x_value < width and 0 <= y_value < height):
            raise EncoderError(f"{field}.ports[{index}] body cell is out of range")
        on_edge = {
            "N": y_value == height - 1,
            "E": x_value == width - 1,
            "S": y_value == 0,
            "W": x_value == 0,
        }[direction]
        if not on_edge:
            raise EncoderError(f"{field}.ports[{index}] is not on its declared body edge")
        physical_key = (x_value, y_value, direction)
        if physical_key in seen:
            raise EncoderError(f"{field} has duplicate physical port specification {physical_key}")
        seen.add(physical_key)


def _manufacturing_span(template: Mapping[str, Any], directions: set[str], field: str) -> int:
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}
    spans: set[int] = set()
    for index, raw_mode in enumerate(_array(template.get("modes"), f"{field}.modes")):
        mode = _object(raw_mode, f"{field}.modes[{index}]")
        _validate_mode_ports(mode, directions, f"{field}.modes[{index}]")
        ports = [_object(port, f"{field}.modes[{index}].port") for port in _array(mode["ports"], "ports")]
        input_directions = {port.get("direction") for port in ports if port.get("kind") == "input"}
        output_directions = {port.get("direction") for port in ports if port.get("kind") == "output"}
        if len(input_directions) != 1 or len(output_directions) != 1:
            raise EncoderError(f"{field} does not have single-sided input and output ports")
        input_direction = next(iter(input_directions))
        output_direction = next(iter(output_directions))
        if opposite.get(str(input_direction)) != output_direction:
            raise EncoderError(f"{field} input and output sides are not opposite")
        spans.add(_port_side_span(mode, str(output_direction), f"{field}.modes[{index}]"))
    if len(spans) != 1:
        raise EncoderError(f"{field} modes disagree on port-bearing side span")
    return next(iter(spans))


def _canonical_constraint(
    terms: Iterable[tuple[int, int]], relation: str, rhs: int
) -> Constraint:
    if relation not in {"=", ">="}:
        raise EncoderError(f"unsupported relation: {relation}")
    combined: Counter[int] = Counter()
    for variable, coefficient in terms:
        variable = _exact_int(variable, "constraint variable")
        coefficient = _exact_int(coefficient, "constraint coefficient")
        if variable <= 0:
            raise EncoderError("constraint variable IDs must be positive")
        combined[variable] += coefficient
    canonical = tuple(sorted((variable, value) for variable, value in combined.items() if value))
    if not canonical:
        raise EncoderError("constant-only constraints are not supported")
    return Constraint(canonical, relation, _exact_int(rhs, "constraint rhs"))


def ceil_div(numerator: int, denominator: int) -> int:
    """Return exact mathematical ceil(numerator / denominator)."""

    if denominator <= 0:
        raise EncoderError("ceil divisor must be positive")
    return -(-numerator // denominator)


def _halo_weight2(dx: int, dy: int) -> int:
    first = abs(2 * dx - 1)
    second = abs(2 * dy - 1)
    return HALO_ORBIT_DOUBLED_WEIGHTS.get((max(first, second), min(first, second)), 0)


def _derive_halo(
    powered_shapes: set[tuple[int, int]],
    coverage: Mapping[str, Any],
    pole_shape: tuple[int, int],
    powered_area: int,
) -> dict[str, Any]:
    x_min = _exact_int(coverage.get("x_min_offset"), "power.coverage.x_min_offset")
    x_max = _exact_int(coverage.get("x_max_offset"), "power.coverage.x_max_offset")
    y_min = _exact_int(coverage.get("y_min_offset"), "power.coverage.y_min_offset")
    y_max = _exact_int(coverage.get("y_max_offset"), "power.coverage.y_max_offset")
    if x_min > x_max or y_min > y_max:
        raise EncoderError("power coverage offsets are inverted")

    orbit_records = [
        {"major": major, "minor": minor, "doubled_weight": weight}
        for (major, minor), weight in sorted(HALO_ORBIT_DOUBLED_WEIGHTS.items())
    ]
    if any(
        record["major"] < record["minor"]
        or record["minor"] <= 0
        or record["major"] % 2 != 1
        or record["minor"] % 2 != 1
        or record["doubled_weight"] <= 0
        for record in orbit_records
    ):
        raise EncoderError("halo orbit table is malformed")
    maximum_orbit = max(HALO_ORBIT_DOUBLED_WEIGHTS)[0]
    support = range(-(maximum_orbit // 2), maximum_orbit // 2 + 2)
    total_doubled_weight = sum(_halo_weight2(dx, dy) for dx in support for dy in support)
    if total_doubled_weight % 2:
        raise EncoderError("halo total weight is not integral")
    total_weight = total_doubled_weight // 2

    pole_width, pole_height = pole_shape
    pole_body = {(x, y) for x in range(pole_width) for y in range(pole_height)}
    coverage_cells = {
        (x, y) for x in range(x_min, x_max + 1) for y in range(y_min, y_max + 1)
    }
    placement_counts: dict[str, int] = {}
    checked = 0
    violations = 0
    minimum_doubled_slack: int | None = None
    for width, height in sorted(powered_shapes):
        shape_checked = 0
        for anchor_x in range(x_min - width + 1, x_max + 1):
            for anchor_y in range(y_min - height + 1, y_max + 1):
                body = {
                    (anchor_x + x, anchor_y + y)
                    for x in range(width)
                    for y in range(height)
                }
                if not body.intersection(coverage_cells) or body.intersection(pole_body):
                    continue
                shape_checked += 1
                checked += 1
                doubled_slack = sum(_halo_weight2(x, y) for x, y in body) - 2 * width * height
                if doubled_slack < 0:
                    violations += 1
                if minimum_doubled_slack is None or doubled_slack < minimum_doubled_slack:
                    minimum_doubled_slack = doubled_slack
        placement_counts[f"{width}x{height}"] = shape_checked

    minimum_poles = ceil_div(powered_area, total_weight)
    expected_counts = {"3x3": 180, "4x6": 220, "5x5": 220, "6x4": 220}
    if placement_counts != expected_counts:
        raise EncoderError("halo placement-class counts drifted")
    _expect(len(orbit_records), 14, "halo orbit count")
    _expect(total_doubled_weight, 792, "halo doubled total weight")
    _expect(total_weight, 396, "halo total weight")
    _expect(checked, 840, "halo checked placements")
    _expect(violations, 0, "halo local inequality violations")
    _expect(minimum_poles, 9, "halo minimum pole count")
    return {
        "orbit_count": len(orbit_records),
        "doubled_weights": [
            {
                "a": record["major"],
                "b": record["minor"],
                "weight2": record["doubled_weight"],
            }
            for record in orbit_records
        ],
        "total_weight2": total_doubled_weight,
        "total_weight": total_weight,
        "body_dimensions": [list(pair) for pair in sorted(powered_shapes)],
        "placement_counts": placement_counts,
        "placement_count": checked,
        "violations": [] if violations == 0 else [{"count": violations}],
        "minimum_slack2": minimum_doubled_slack,
        "powered_area": powered_area,
        "minimum_poles": minimum_poles,
    }


def derive_model(problem_payload: Any) -> DerivedModel:
    """Independently rebuild the strict R3 arithmetic and exact PB model."""

    problem = _object(problem_payload, "problem_instance")
    _expect(problem.get("benchmark_id"), "factory_layout_optimality_benchmark_v1", "benchmark_id")
    _expect(problem.get("schema_version"), 1, "schema_version")

    grid = _object(problem.get("grid"), "grid")
    grid_width = _exact_int(grid.get("width"), "grid.width")
    grid_height = _exact_int(grid.get("height"), "grid.height")
    if (grid_width, grid_height) != (70, 70):
        raise EncoderError("the R3 derivation is hard-bound to the 70x70 strict instance")

    objective = _object(problem.get("objective"), "objective")
    _expect(objective.get("kind"), "max_lex_area_min_side", "objective.kind")
    _expect(objective.get("body_cells_only"), True, "objective.body_cells_only")
    minimum_side = _exact_int(objective.get("minimum_side"), "objective.minimum_side")
    _expect(minimum_side, 6, "objective.minimum_side")

    coordinate_system = _object(problem.get("coordinate_system"), "coordinate_system")
    raw_directions = _array(coordinate_system.get("directions"), "coordinate_system.directions")
    if list(raw_directions) != ["N", "E", "S", "W"]:
        raise EncoderError("strict cardinal directions drifted")
    directions = set(raw_directions)
    incidence_cap = len(directions)

    templates = _object(problem.get("facility_templates"), "facility_templates")
    body_areas: dict[str, int] = {}
    mode_port_counts: dict[str, int] = {}
    for name, raw_template in templates.items():
        if type(name) is not str:
            raise EncoderError("facility template names must be strings")
        template = _object(raw_template, f"facility_templates.{name}")
        body_areas[name] = _mode_body_area(template, f"facility_templates.{name}")
        mode_port_counts[name] = _mode_port_count(template, f"facility_templates.{name}")
        for index, raw_mode in enumerate(_array(template.get("modes"), f"{name}.modes")):
            _validate_mode_ports(_object(raw_mode, f"{name}.modes[{index}]"), directions, f"{name}.modes[{index}]")

    required_instances = _array(problem.get("required_instances"), "required_instances")
    template_counts: Counter[str] = Counter()
    instances_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw_instance in enumerate(required_instances):
        instance = _object(raw_instance, f"required_instances[{index}]")
        instance_id = instance.get("id")
        template_name = instance.get("template")
        if type(instance_id) is not str or not instance_id or instance_id in instances_by_id:
            raise EncoderError(f"invalid or duplicate required instance id at index {index}")
        if type(template_name) is not str or template_name not in templates:
            raise EncoderError(f"unknown required template at index {index}")
        instances_by_id[instance_id] = instance
        template_counts[template_name] += 1

    operation_groups_raw = _array(problem.get("operation_groups"), "operation_groups")
    operation_groups: dict[str, Mapping[str, Any]] = {}
    for index, raw_group in enumerate(operation_groups_raw):
        group = _object(raw_group, f"operation_groups[{index}]")
        group_id = group.get("id")
        if type(group_id) is not str or not group_id or group_id in operation_groups:
            raise EncoderError(f"invalid or duplicate operation group id at index {index}")
        group_template = group.get("template")
        if type(group_template) is not str or group_template not in templates:
            raise EncoderError(f"operation_groups[{index}] has an unknown template")
        instance_ids = _array(group.get("instance_ids"), f"operation_groups[{index}].instance_ids")
        count = _exact_int(group.get("count"), f"operation_groups[{index}].count")
        if len(instance_ids) != count or len(set(instance_ids)) != count:
            raise EncoderError(f"operation_groups[{index}] instance count/list mismatch")
        for instance_id in instance_ids:
            if type(instance_id) is not str or instance_id not in instances_by_id:
                raise EncoderError(f"operation_groups[{index}] references an unknown instance")
            instance = instances_by_id[instance_id]
            if instance.get("operation") != group_id or instance.get("template") != group_template:
                raise EncoderError(f"operation_groups[{index}] disagrees with required instance {instance_id}")
        operation_groups[group_id] = group

    powered_instances = [
        instance
        for instance in instances_by_id.values()
        if _object(templates[instance["template"]], f"templates.{instance['template']}").get("requires_power")
        is True
    ]
    for instance in powered_instances:
        operation = instance.get("operation")
        if type(operation) is not str or operation not in operation_groups:
            raise EncoderError(f"powered instance {instance['id']} lacks a known operation")

    required_body_area = sum(template_counts[name] * body_areas[name] for name in template_counts)
    powered_body_area = sum(body_areas[str(instance["template"])] for instance in powered_instances)
    physical_port_specs = sum(template_counts[name] * mode_port_counts[name] for name in template_counts)
    manufacturing_inputs = sum(
        _need_total(operation_groups[str(instance["operation"])], "inputs", str(instance["operation"]))
        for instance in powered_instances
    )
    manufacturing_outputs = sum(
        _need_total(operation_groups[str(instance["operation"])], "outputs", str(instance["operation"]))
        for instance in powered_instances
    )

    generic = _object(problem.get("generic_requirements"), "generic_requirements")
    raw_outputs = _object(generic.get("raw_outputs"), "generic_requirements.raw_outputs")
    final_inputs = _object(generic.get("final_inputs"), "generic_requirements.final_inputs")
    generic_raw_outputs = sum(
        _exact_int(value, f"generic_requirements.raw_outputs.{commodity}")
        for commodity, value in raw_outputs.items()
    )
    generic_final_inputs = sum(
        _exact_int(value, f"generic_requirements.final_inputs.{commodity}")
        for commodity, value in final_inputs.items()
    )
    active_inputs = manufacturing_inputs + generic_final_inputs
    active_outputs = manufacturing_outputs + generic_raw_outputs
    total_active_terminals = active_inputs + active_outputs

    commodities = _array(problem.get("commodities"), "commodities")
    if any(type(commodity) is not str or not commodity for commodity in commodities):
        raise EncoderError("commodities must be nonempty strings")
    if len(set(commodities)) != len(commodities):
        raise EncoderError("commodity names must be unique")

    sentinels = _object(problem.get("sentinels"), "sentinels")
    derived_sentinels = {
        "required_instance_count": len(required_instances),
        "manufacturing_instance_count": len(powered_instances),
        "required_body_area": required_body_area,
        "manufacturing_input_terminals": manufacturing_inputs,
        "manufacturing_output_terminals": manufacturing_outputs,
        "generic_raw_output_terminals": generic_raw_outputs,
        "generic_final_input_terminals": generic_final_inputs,
        "total_active_terminals": total_active_terminals,
        "operation_group_count": len(operation_groups),
        "commodity_count": len(commodities),
    }
    for field, value in derived_sentinels.items():
        _expect(sentinels.get(field), value, f"sentinels.{field}")
    expected_sentinels = {
        "required_instance_count": 266,
        "manufacturing_instance_count": 219,
        "required_body_area": 3_544,
        "manufacturing_input_terminals": 310,
        "manufacturing_output_terminals": 264,
        "generic_raw_output_terminals": 52,
        "generic_final_input_terminals": 2,
        "total_active_terminals": 628,
        "operation_group_count": 17,
        "commodity_count": 19,
    }
    for field, expected in expected_sentinels.items():
        _expect(derived_sentinels[field], expected, f"derived.{field}")
    _expect(powered_body_area, 3_325, "powered manufacturing body area")
    _expect(physical_port_specs, 1_804, "required physical port specifications")
    _expect(active_inputs, 312, "active input terminals")
    _expect(active_outputs, 316, "active output terminals")

    class_counts: Counter[tuple[int, int]] = Counter()
    powered_shapes: set[tuple[int, int]] = set()
    manufacturing_spans: dict[str, int] = {}
    for template_name in sorted({str(instance["template"]) for instance in powered_instances}):
        template = _object(templates[template_name], f"templates.{template_name}")
        manufacturing_spans[template_name] = _manufacturing_span(
            template, directions, f"templates.{template_name}"
        )
        for raw_mode in _array(template.get("modes"), f"templates.{template_name}.modes"):
            mode = _object(raw_mode, f"templates.{template_name}.mode")
            body = _object(mode.get("body"), f"templates.{template_name}.mode.body")
            powered_shapes.add(
                (
                    _exact_int(body.get("width"), "powered mode width"),
                    _exact_int(body.get("height"), "powered mode height"),
                )
            )
    for instance in powered_instances:
        operation = operation_groups[str(instance["operation"])]
        inputs_needed = _need_total(operation, "inputs", str(instance["operation"]))
        outputs_needed = _need_total(operation, "outputs", str(instance["operation"]))
        template_name = str(instance["template"])
        template = _object(templates[template_name], f"templates.{template_name}")
        if inputs_needed > _port_count(template, "input", template_name):
            raise EncoderError(f"operation {instance['operation']} exceeds template input capacity")
        if outputs_needed > _port_count(template, "output", template_name):
            raise EncoderError(f"operation {instance['operation']} exceeds template output capacity")
        class_counts[(manufacturing_spans[template_name], max(inputs_needed, outputs_needed))] += 1

    boundary_template = _object(templates.get("boundary_storage_port"), "boundary_storage_port")
    _expect(boundary_template.get("placement_rule"), "matching_map_boundary", "boundary placement_rule")
    boundary_spans: set[int] = set()
    for index, raw_mode in enumerate(_array(boundary_template.get("modes"), "boundary modes")):
        mode = _object(raw_mode, f"boundary modes[{index}]")
        outputs = [
            _object(port, f"boundary modes[{index}].port")
            for port in _array(mode.get("ports"), f"boundary modes[{index}].ports")
            if _object(port, f"boundary modes[{index}].port").get("kind") == "output"
        ]
        if len(outputs) != 1 or _port_count(boundary_template, "input", "boundary") != 0:
            raise EncoderError("boundary storage ports must have exactly one output and no input")
        boundary_spans.add(_port_side_span(mode, str(outputs[0].get("direction")), f"boundary mode {index}"))
    if boundary_spans != {3}:
        raise EncoderError("boundary storage port side span drifted")
    boundary_count = template_counts["boundary_storage_port"]
    class_counts[(next(iter(boundary_spans)), 1)] += boundary_count

    expected_class_counts = {
        (3, 1): 155,
        (3, 2): 12,
        (3, 3): 11,
        (5, 1): 32,
        (5, 2): 17,
        (6, 3): 32,
        (6, 4): 3,
        (6, 5): 3,
    }
    if dict(class_counts) != expected_class_counts:
        raise EncoderError("membrane class table drifted")
    class_records = [
        {
            "side_span": span,
            "active_side_cap": allowance,
            "multiplicity": class_counts[(span, allowance)],
        }
        for span, allowance in sorted(class_counts)
    ]
    full_contact_excess = sum(
        count * max(0, 2 * allowance - span)
        for (span, allowance), count in class_counts.items()
    )
    endpoint_contacts = 2 * len(directions)
    maximum_endpoint_extra = max(
        allowance - max(0, 2 * allowance - span) for span, allowance in class_counts
    )
    endpoint_allowance = endpoint_contacts * maximum_endpoint_extra
    total_excess = full_contact_excess + endpoint_allowance
    k_constant = total_excess // 2

    core_template = _object(templates.get("protocol_core"), "protocol_core")
    core_facing_caps: set[int] = set()
    for index, raw_mode in enumerate(_array(core_template.get("modes"), "protocol_core.modes")):
        mode = _object(raw_mode, f"protocol_core.modes[{index}]")
        output_counts = Counter(
            str(_object(port, f"protocol_core.modes[{index}].port").get("direction"))
            for port in _array(mode.get("ports"), f"protocol_core.modes[{index}].ports")
            if _object(port, f"protocol_core.modes[{index}].port").get("kind") == "output"
        )
        if len(output_counts) != 2 or set(output_counts.values()) != {3}:
            raise EncoderError("protocol core outputs do not split 3+3 across two sides")
        core_sides = set(output_counts)
        if not (core_sides == {"N", "S"} or core_sides == {"E", "W"}):
            raise EncoderError("protocol core output sides are not opposite")
        core_facing_caps.add(max(output_counts.values()))
    if core_facing_caps != {3} or template_counts["protocol_core"] != 1:
        raise EncoderError("protocol core facing-output allowance drifted")
    core_facing_cap = next(iter(core_facing_caps))
    u_extra = core_facing_cap + generic_final_inputs
    u_constant = k_constant + u_extra
    external_terminal_constant = total_active_terminals - u_constant

    if incidence_cap != MEMBRANE_INCIDENCE_CAP:
        raise EncoderError("terminal incidence cap drifted")
    _expect(full_contact_excess, 63, "membrane full-contact excess")
    _expect(endpoint_contacts, 8, "membrane endpoint contacts")
    _expect(maximum_endpoint_extra, 3, "membrane maximum endpoint extra")
    _expect(endpoint_allowance, 24, "membrane endpoint allowance")
    _expect(total_excess, 87, "membrane total excess")
    _expect(k_constant, 43, "membrane K constant")
    _expect(u_extra, 5, "membrane U extra")
    _expect(u_constant, 48, "membrane U constant")
    _expect(external_terminal_constant, MEMBRANE_EXTERNAL_CONSTANT, "membrane external constant")

    power = _object(problem.get("power"), "power")
    _expect(power.get("required_rule"), "at_least_one_body_cell_covered", "power.required_rule")
    pole_template_name = power.get("pole_template")
    if type(pole_template_name) is not str or pole_template_name not in templates:
        raise EncoderError("power.pole_template is missing or unknown")
    pole_template = _object(templates[pole_template_name], f"templates.{pole_template_name}")
    pole_shapes = {
        (
            _exact_int(_object(_object(mode, "pole mode").get("body"), "pole body").get("width"), "pole width"),
            _exact_int(_object(_object(mode, "pole mode").get("body"), "pole body").get("height"), "pole height"),
        )
        for mode in _array(pole_template.get("modes"), "pole modes")
    }
    if len(pole_shapes) != 1:
        raise EncoderError("pole modes disagree on body shape")
    pole_shape = next(iter(pole_shapes))
    pole_body_area = body_areas[pole_template_name]
    _expect(pole_body_area, 4, "pole body area")
    halo = _derive_halo(
        powered_shapes,
        _object(power.get("coverage_from_pole_anchor"), "power.coverage_from_pole_anchor"),
        pole_shape,
        powered_body_area,
    )
    free_cell_cap = grid_width * grid_height - required_body_area - halo["minimum_poles"] * pole_body_area
    _expect(free_cell_cap, FREE_CELL_CAP, "free-cell cap")

    all_dimensions = tuple(
        (width, height)
        for width in range(minimum_side, grid_width + 1)
        for height in range(minimum_side, grid_height + 1)
    )
    area_tie_dimensions = tuple(
        pair for pair in all_dimensions if pair[0] * pair[1] == TARGET_AREA
    )
    oriented_dimensions = tuple(
        (width, height)
        for width, height in all_dimensions
        if width * height > TARGET_AREA
        or (width * height == TARGET_AREA and min(width, height) > TARGET_MIN_SIDE)
    )

    def lhs(width: int, height: int) -> int:
        return width * height + ceil_div(
            external_terminal_constant - width - height, incidence_cap
        )

    satisfying_band = tuple(
        (width, height) for width, height in oriented_dimensions if lhs(width, height) <= free_cell_cap
    )
    minimum_band_lhs = min(lhs(width, height) for width, height in oriented_dimensions)
    minimum_band_dimensions = tuple(
        (width, height)
        for width, height in oriented_dimensions
        if lhs(width, height) == minimum_band_lhs
    )
    feasible_dimensions = tuple(
        (width, height) for width, height in all_dimensions if lhs(width, height) <= free_cell_cap
    )
    lexicographic_maximum = max(
        (width * height, min(width, height)) for width, height in feasible_dimensions
    )
    lexicographic_maximizers = tuple(
        (width, height)
        for width, height in feasible_dimensions
        if (width * height, min(width, height)) == lexicographic_maximum
    )

    _expect(
        area_tie_dimensions,
        ((17, 70), (34, 35), (35, 34), (70, 17)),
        "area-1190 oriented tie dimensions",
    )
    _expect(len(oriented_dimensions), 2_074, "lex-better oriented band size")
    _expect(len(satisfying_band), 0, "lex-better inequality satisfiers")
    _expect(minimum_band_lhs, 1_322, "minimum lex-better LHS")
    _expect(minimum_band_dimensions, ((19, 63), (63, 19)), "minimum-LHS dimensions")
    _expect(len(feasible_dimensions), 2_151, "inequality-feasible dimension count")
    _expect(lexicographic_maximum, (TARGET_AREA, TARGET_MIN_SIDE), "inequality lex maximum")
    _expect(lexicographic_maximizers, ((34, 35), (35, 34)), "inequality lex maximizers")

    variables: list[VariableRecord] = []
    for width, height in oriented_dimensions:
        lhs_value = lhs(width, height)
        variables.append(
            VariableRecord(
                {
                "id": len(variables) + 1,
                "name": f"dimension__w_{width:02d}__h_{height:02d}",
                "kind": "oriented_dimension_selector",
                "width": width,
                "height": height,
                "area": width * height,
                "minimum_side": min(width, height),
                "lhs": lhs_value,
                "coefficient": free_cell_cap - lhs_value,
                }
            )
        )

    constraints = [
        _canonical_constraint(((record["id"], 1) for record in variables), "=", 1),
        *(
            _canonical_constraint(((record["id"], record["coefficient"]),), ">=", 0)
            for record in variables
        ),
    ]
    counts = {
        "oriented_dimensions": len(oriented_dimensions),
        "selector_variables": len(variables),
        "variables": len(variables),
        "equality_constraints": 1,
        "dimension_implication_constraints": len(variables),
        "constraints": len(constraints),
        "satisfying_dimensions": len(satisfying_band),
    }
    expected_counts = {
        "oriented_dimensions": 2_074,
        "selector_variables": 2_074,
        "variables": 2_074,
        "equality_constraints": 1,
        "dimension_implication_constraints": 2_074,
        "constraints": 2_075,
        "satisfying_dimensions": 0,
    }
    if counts != expected_counts:
        raise EncoderError("unexpected final PB model size")

    metadata_sentinels = {
        "required_instances": len(required_instances),
        "manufacturing_instances": len(powered_instances),
        "required_body_area": required_body_area,
        "powered_manufacturing_area": powered_body_area,
        "manufacturing_input_terminals": manufacturing_inputs,
        "manufacturing_output_terminals": manufacturing_outputs,
        "generic_raw_output_terminals": generic_raw_outputs,
        "generic_final_input_terminals": generic_final_inputs,
        "active_input_terminals": active_inputs,
        "active_output_terminals": active_outputs,
        "total_active_terminals": total_active_terminals,
        "physical_port_specs": physical_port_specs,
        "operation_groups": len(operation_groups),
        "commodities": len(commodities),
        "boundary_instances": boundary_count,
        "protocol_core_instances": template_counts["protocol_core"],
        "pole_body_area": pole_body_area,
    }
    derived_facts = {
        "grid": {"width": grid_width, "height": grid_height, "area": grid_width * grid_height},
        "objective": {
            "kind": objective["kind"],
            "minimum_side": minimum_side,
            "target_area": TARGET_AREA,
            "target_min_side": TARGET_MIN_SIDE,
            "orientation": "ordered_width_height",
        },
        "strict_sentinels": metadata_sentinels,
        "membrane": {
            "class_table": class_records,
            "full_contact_excess": full_contact_excess,
            "directed_endpoints": endpoint_contacts,
            "maximum_endpoint_extra": maximum_endpoint_extra,
            "endpoint_correction": endpoint_allowance,
            "twice_k_minus_l_cap": total_excess,
            "manufacturing_boundary_additive_cap": k_constant,
            "protocol_core_side_output_cap": core_facing_cap,
            "generic_final_input_terminals": generic_final_inputs,
            "additional_inside_terminals": u_extra,
            "inside_terminal_additive_cap": u_constant,
            "outside_access_incidence_cap": incidence_cap,
            "outside_terminal_numerator_constant": external_terminal_constant,
        },
        "power_halo": {
            "orbit_count": halo["orbit_count"],
            "doubled_weights": halo["doubled_weights"],
            "total_weight2": halo["total_weight2"],
            "total_weight": halo["total_weight"],
            "body_dimensions": halo["body_dimensions"],
            "placement_counts": halo["placement_counts"],
            "placement_count": halo["placement_count"],
            "violation_count": len(halo["violations"]),
            "minimum_slack2": halo["minimum_slack2"],
            "powered_area": halo["powered_area"],
            "minimum_poles": halo["minimum_poles"],
        },
        "free_cell_cap": {
            "value": free_cell_cap,
            "identity": "4900 - 3544 - 9 * 4 = 1320",
        },
        "lex_better_band": {
            "width_range": [minimum_side, grid_width],
            "height_range": [minimum_side, grid_height],
            "oriented": True,
            "predicate": "area > 1190 or (area == 1190 and min(width,height) > 34)",
            "dimension_count": len(oriented_dimensions),
            "area_1190_oriented_pairs": [list(pair) for pair in area_tie_dimensions],
            "satisfying_dimension_count": len(satisfying_band),
            "minimum_lhs": minimum_band_lhs,
            "minimum_lhs_dimensions": [list(pair) for pair in minimum_band_dimensions],
        },
        "necessary_inequality": {
            "display": "wh + ceil((580-w-h)/4) <= 1320",
            "terminal_numerator_constant": external_terminal_constant,
            "divisor": incidence_cap,
            "rhs": free_cell_cap,
        },
    }
    return DerivedModel(
        variables=variables,
        constraints=constraints,
        oriented_dimensions=oriented_dimensions,
        derived_facts=derived_facts,
        counts=counts,
    )


def render_opb(model: DerivedModel) -> bytes:
    """Render deterministic, RoundingSat-compatible OPB bytes."""

    equal_count = sum(constraint.relation == "=" for constraint in model.constraints)
    lines = [
        (
            f"* #variable= {len(model.variables)} #constraint= {len(model.constraints)} "
            f"#equal= {equal_count} intsize= 64"
        ),
        (
            f"* model={MODEL_SCHEMA} generated_by={HARNESS} semantics={SEMANTICS} "
            "target=1190,34 given_inequality=wh+ceil((580-w-h)/4)<=1320"
        ),
        *(constraint.render() for constraint in model.constraints),
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def _file_record(path: Path, project_root: Path) -> dict[str, Any]:
    return _snapshot("file", path, project_root).record()


def _git_snapshot(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise EncoderError(f"unexpected git revision: {revision!r}")
    diff = subprocess.run(
        ["git", "-C", str(root), "diff", "--binary", "--full-index", "--no-ext-diff", "HEAD", "--"],
        check=True,
        capture_output=True,
    ).stdout
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "-z", "--untracked-files=normal"],
        check=True,
        capture_output=True,
    ).stdout
    return {
        "head": revision,
        "tracked_dirty": bool(diff),
        "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "tracked_diff_size_bytes": len(diff),
        "status_dirty": bool(status),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "status_size_bytes": len(status),
    }


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _argv_record(argv: Sequence[str] | None) -> list[str]:
    if argv is None:
        return list(sys.argv)
    return [str(Path(__file__).resolve()), *(str(value) for value in argv)]


def _records(snapshots: Mapping[str, Snapshot]) -> dict[str, dict[str, Any]]:
    return {key: snapshots[key].record() for key in sorted(snapshots)}


def _planning(opb_bytes: int, user_limit_bytes: int) -> dict[str, Any]:
    bound_bytes = max(PLANNING_FLOOR_BYTES, PLANNING_OPB_MULTIPLIER * opb_bytes)
    return {
        "bound_bytes": bound_bytes,
        "user_limit_bytes": user_limit_bytes,
        "decision": "GO" if bound_bytes <= user_limit_bytes else "NO_GO",
        "basis": {
            "method": "max_512_mib_or_1024_times_projected_opb_bytes",
            "floor_bytes": PLANNING_FLOOR_BYTES,
            "opb_multiplier": PLANNING_OPB_MULTIPLIER,
            "projected_opb_bytes": opb_bytes,
        },
    }


def command_estimate(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    if args.proof_limit_bytes <= 0:
        raise EncoderError("--proof-limit-bytes must be positive")
    project_root = args.project_root.resolve()
    inputs, evidence = load_bound_snapshots(project_root)
    model = derive_model(loads_strict_json(inputs["problem_instance"].text))
    opb = render_opb(model)
    planning = _planning(len(opb), args.proof_limit_bytes)
    estimate = {
        "schema_version": ESTIMATE_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "metadata_schema_version": METADATA_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "semantics": SEMANTICS,
        "harness": HARNESS,
        "argv": _argv_record(argv),
        "project_root": str(project_root),
        "harness_source": _file_record(Path(__file__), project_root),
        "inputs": _records(inputs),
        "evidence": _records(evidence),
        "git_snapshot": _git_snapshot(project_root),
        "derived_facts": model.derived_facts,
        "counts": model.counts,
        "projected_outputs": {"opb_bytes": len(opb)},
        "proof_size_planning": planning,
    }
    _exclusive_json(args.output.resolve(), estimate)
    print(
        json.dumps(
            {
                "decision": planning["decision"],
                "opb_bytes": len(opb),
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


def _load_estimate(path: Path, project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = _snapshot("estimate", path, project_root)
    payload = loads_strict_json(snapshot.text)
    if not isinstance(payload, dict):
        raise EncoderError("estimate must be a JSON object")
    return payload, snapshot.record()


def _check_estimate(
    estimate: Mapping[str, Any],
    *,
    project_root: Path,
    model: DerivedModel,
    opb: bytes,
    inputs: Mapping[str, Snapshot],
    evidence: Mapping[str, Snapshot],
) -> None:
    expected_keys = {
        "schema_version",
        "model_schema_version",
        "metadata_schema_version",
        "variable_map_schema_version",
        "semantics",
        "harness",
        "argv",
        "project_root",
        "harness_source",
        "inputs",
        "evidence",
        "git_snapshot",
        "derived_facts",
        "counts",
        "projected_outputs",
        "proof_size_planning",
    }
    if set(estimate) != expected_keys:
        raise EncoderError("estimate key set mismatch")
    expected_scalars = {
        "schema_version": ESTIMATE_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "metadata_schema_version": METADATA_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "semantics": SEMANTICS,
        "harness": HARNESS,
        "project_root": str(project_root.resolve()),
    }
    for field, expected in expected_scalars.items():
        if estimate.get(field) != expected:
            raise EncoderError(f"estimate {field} mismatch")
    estimate_argv = estimate.get("argv")
    if not isinstance(estimate_argv, list) or not estimate_argv or any(
        type(value) is not str for value in estimate_argv
    ):
        raise EncoderError("estimate argv must be a nonempty string array")
    planning = _object(estimate.get("proof_size_planning"), "estimate.proof_size_planning")
    user_limit = _exact_int(planning.get("user_limit_bytes"), "estimate user proof limit")
    expected_planning = _planning(len(opb), user_limit)
    if dict(planning) != expected_planning:
        raise EncoderError("estimate proof planning mismatch")
    if planning.get("decision") != "GO":
        raise EncoderError("estimate is not GO")
    checks = {
        "inputs": _records(inputs),
        "evidence": _records(evidence),
        "harness_source": _file_record(Path(__file__), project_root),
        "git_snapshot": _git_snapshot(project_root),
        "derived_facts": model.derived_facts,
        "counts": model.counts,
        "projected_outputs": {"opb_bytes": len(opb)},
    }
    for field, expected in checks.items():
        if estimate.get(field) != expected:
            raise EncoderError(f"estimate provenance/model drift: {field}")


def _claim_scope() -> dict[str, Any]:
    return {
        "given_geometric_lemmas": {
            "inside_opb": False,
            "coverage": "R3 membrane and power-halo geometric lemmas",
            "trust": "backed by the pinned R3 adversarial verdict and independent recomputation",
        },
        "arithmetic_band": {
            "inside_opb": True,
            "coverage": "all 2074 oriented 6<=w,h<=70 dimensions lexicographically better than (1190,34)",
            "mechanism": "exactly-one selector plus one transparent linear necessary-inequality implication per dimension",
        },
        "combined_statement": (
            "given the R3 geometric lemmas, the complete lex-better dimension band is arithmetically UNSAT"
        ),
        "limitations": [
            "translation only; this metadata does not assert solver UNSAT or proof verification",
            "does not prove the R3 geometric lemmas",
            "does not provide a witness or prove attainability or global optimality",
            "research artifact; not sealed or production CERTIFIED evidence",
        ],
    }


def command_encode(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    project_root = args.project_root.resolve()
    outputs = [args.opb_out.resolve(), args.meta_out.resolve(), args.var_map_out.resolve()]
    if len(set(outputs)) != len(outputs):
        raise EncoderError("OPB, metadata, and variable-map outputs must be distinct")
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError("refusing to overwrite existing output(s): " + ", ".join(existing))

    inputs, evidence = load_bound_snapshots(project_root)
    model = derive_model(loads_strict_json(inputs["problem_instance"].text))
    opb = render_opb(model)
    estimate, estimate_record = _load_estimate(args.estimate.resolve(), project_root)
    _check_estimate(
        estimate,
        project_root=project_root,
        model=model,
        opb=opb,
        inputs=inputs,
        evidence=evidence,
    )

    args.opb_out.parent.mkdir(parents=True, exist_ok=True)
    with args.opb_out.open("xb") as handle:
        handle.write(opb)
    var_map = {
        "schema_version": VAR_MAP_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "semantics": SEMANTICS,
        "variable_count": len(model.variables),
        "variables": model.variables,
    }
    _exclusive_json(args.var_map_out.resolve(), var_map)
    meta = {
        "schema_version": METADATA_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "semantics": SEMANTICS,
        "harness": HARNESS,
        "argv": _argv_record(argv),
        "project_root": str(project_root),
        "harness_source": _file_record(Path(__file__), project_root),
        "inputs": _records(inputs),
        "evidence": _records(evidence),
        "git_snapshot": _git_snapshot(project_root),
        "estimate": estimate_record,
        "derived_facts": model.derived_facts,
        "counts": model.counts,
        "outputs": {
            "opb": _file_record(args.opb_out, project_root),
            "var_map": _file_record(args.var_map_out, project_root),
            "metadata": {"path": str(args.meta_out.resolve())},
        },
        "claim_scope": _claim_scope(),
        "proof_status": "translation_only_no_unsat_or_proof_claim",
    }
    _exclusive_json(args.meta_out.resolve(), meta)
    print(
        json.dumps(
            {
                "status": "generated",
                "opb": str(args.opb_out.resolve()),
                "variables": model.counts["variables"],
                "constraints": model.counts["constraints"],
            },
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    estimate = subparsers.add_parser("estimate", help="derive and size the exact OPB in memory")
    estimate.add_argument("--project-root", type=Path, required=True)
    estimate.add_argument("--output", type=Path, required=True)
    estimate.add_argument("--proof-limit-bytes", type=int, required=True)
    estimate.set_defaults(func=command_estimate)

    encode = subparsers.add_parser("encode", help="encode only from an unchanged GO estimate")
    encode.add_argument("--project-root", type=Path, required=True)
    encode.add_argument("--estimate", type=Path, required=True)
    encode.add_argument("--opb-out", type=Path, required=True)
    encode.add_argument("--meta-out", type=Path, required=True)
    encode.add_argument("--var-map-out", type=Path, required=True)
    encode.set_defaults(func=command_encode)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.func(args, argv))


if __name__ == "__main__":
    raise SystemExit(main())
