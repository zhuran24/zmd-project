#!/usr/bin/env python3
"""Independently gate the B1 Q/membrane/halo build-only OPB translation.

This checker deliberately shares no code with the encoder or either B1
recomputation.  It rederives the strict boundary geometry, the complete
ceiling pattern/placement corpus, the variable order, and every OPB
constraint.  Passing this gate says only that the build-only artifacts encode
the admitted necessary inequality faithfully.  It is not a solver or proof
run and does not establish a witness, attainability, or optimality.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_RELATIVE_PATH = Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json")
STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"

ESTIMATE_SCHEMA = "b1_q_membrane_halo_band_estimate_v1"
METADATA_SCHEMA = "b1_q_membrane_halo_band_metadata_v1"
VARIABLE_MAP_SCHEMA = "b1_q_membrane_halo_band_var_map_v1"
GATE_SCHEMA = "b1_q_membrane_halo_band_translation_gate_v1"
MODEL_SCHEMA = "b1_q_membrane_halo_band_model_v1"
SEMANTICS = "b1_q_membrane_halo_band_build_only_v1"
ENCODER_HARNESS = "b1_q_membrane_halo_band_encoder_v1"
ENCODER_RELATIVE_PATH = Path("docs/research/b1_q_membrane_halo_20260722/b1_q_membrane_halo_band_encoder_v1.py")

GRID_SIDE = 70
MINIMUM_SIDE = 6
DIMENSIONS = ((34, 35), (35, 34))
MEMBRANE_NUMERATOR = 580
FREE_CELL_CAP = 1320
INCIDENCE_CAP = 4
EXPECTED_PATTERNS = 47
EXPECTED_PLACEMENTS = 2520
EXPECTED_VARIABLES = 2567
EXPECTED_CONSTRAINTS = 96
EXPECTED_EQUALITIES = 2
EXPECTED_EXCLUSIONS = 94
EXPECTED_PAIR_CORPUS = 118_440
EXPECTED_ALLOWED_PAIRS = 118_346
EXPECTED_ORIENTATION_SURVIVORS = {
    "34x35": 59_173,
    "35x34": 59_173,
}

GIB = 1024**3
EXPECTED_RESOURCE_CONTRACT = {
    "formal_run_authorized": False,
    "memory_high": "35GiB",
    "memory_high_bytes": 35 * GIB,
    "memory_max": "39GiB",
    "memory_max_bytes": 39 * GIB,
    "memory_swap_max": "16GiB",
    "memory_swap_max_bytes": 16 * GIB,
    "oom_policy": "continue",
    "proof_size_cap_bytes": 5_000_000_000,
    "disk_low_water": "10GiB",
    "disk_low_water_bytes": 10 * GIB,
    "worker_limit": 1,
}

HEADER_RE = re.compile(
    r"^\*\s+#variable=\s+(\d+)\s+#constraint=\s+(\d+)\s+"
    r"#equal=\s+(\d+)\s+intsize=\s+(\d+)\s*$"
)
CONSTRAINT_RE = re.compile(r"^(.*?)\s+(>=|=)\s+([+-]?\d+)\s*;\s*$")
TERM_RE = re.compile(r"\s*([+-]\d+)\s+x([1-9]\d*)")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
ConstraintKey = tuple[str, int, tuple[tuple[int, int], ...]]


class GateError(ValueError):
    """A build-only input is malformed or differs from the reconstructed model."""


def _exact_int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise GateError(f"{field} must be an exact integer")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GateError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise GateError(f"{field} must be an array")
    return value


def _closed(value: Mapping[str, Any], keys: Iterable[str], field: str) -> None:
    expected = set(keys)
    if set(value) != expected:
        raise GateError(f"{field} keys are not closed: {sorted(value)} != {sorted(expected)}")


def _type_exact_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(_type_exact_equal(actual[key], expected[key]) for key in expected)
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _type_exact_equal(left, right) for left, right in zip(actual, expected, strict=True)
        )
    return bool(actual == expected)


def _reject_constant(value: str) -> Any:
    raise GateError(f"non-finite JSON number is forbidden: {value}")


def _reject_float(value: str) -> Any:
    raise GateError(f"floating-point JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _strict_json(raw: bytes, field: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GateError(f"{field} is not UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except json.JSONDecodeError as exc:
        raise GateError(f"{field} is not valid JSON: {exc}") from exc


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_record(path: Path, project_root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"required artifact is missing: {resolved}")
    raw = resolved.read_bytes()
    try:
        display = str(resolved.relative_to(project_root.resolve()))
    except ValueError:
        display = str(resolved)
    return {"path": display, "sha256": _sha256(raw), "size_bytes": len(raw)}


def _ceil_div(value: int, divisor: int) -> int:
    return -(-value // divisor)


def _direction_step(direction: str) -> tuple[int, int]:
    try:
        return {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}[direction]
    except KeyError as exc:
        raise GateError(f"unknown port direction: {direction!r}") from exc


def _physical_output_count(mode: Mapping[str, Any], field: str) -> int:
    ports = _array(mode.get("ports"), f"{field}.ports")
    count = 0
    seen_access_offsets: set[tuple[int, int]] = set()
    body = _mapping(mode.get("body"), f"{field}.body")
    width = _exact_int(body.get("width"), f"{field}.body.width")
    height = _exact_int(body.get("height"), f"{field}.body.height")
    for index, raw_port in enumerate(ports):
        port = _mapping(raw_port, f"{field}.ports[{index}]")
        cell = _mapping(port.get("body_cell"), f"{field}.ports[{index}].body_cell")
        cell_x = _exact_int(cell.get("x"), f"{field}.ports[{index}].body_cell.x")
        cell_y = _exact_int(cell.get("y"), f"{field}.ports[{index}].body_cell.y")
        if not (0 <= cell_x < width and 0 <= cell_y < height):
            raise GateError(f"{field}.ports[{index}] body cell is outside the body")
        direction = port.get("direction")
        if type(direction) is not str:
            raise GateError(f"{field}.ports[{index}].direction must be a string")
        step_x, step_y = _direction_step(direction)
        access = (cell_x + step_x, cell_y + step_y)
        if access in seen_access_offsets:
            raise GateError(f"{field} has duplicate relative access offsets")
        seen_access_offsets.add(access)
        if port.get("kind") == "output":
            count += 1
    return count


def _derive_strict(instance: Any) -> dict[str, Any]:
    root = _mapping(instance, "strict instance")
    grid = _mapping(root.get("grid"), "grid")
    objective = _mapping(root.get("objective"), "objective")
    if (
        _exact_int(grid.get("width"), "grid.width"),
        _exact_int(grid.get("height"), "grid.height"),
        _exact_int(objective.get("minimum_side"), "objective.minimum_side"),
        objective.get("body_cells_only"),
    ) != (GRID_SIDE, GRID_SIDE, MINIMUM_SIDE, True):
        raise GateError("strict grid/objective contract drifted")

    templates = _mapping(root.get("facility_templates"), "facility_templates")
    boundary = _mapping(
        templates.get("boundary_storage_port"),
        "facility_templates.boundary_storage_port",
    )
    if boundary.get("placement_rule") != "matching_map_boundary":
        raise GateError("boundary placement rule drifted")
    modes = _array(boundary.get("modes"), "boundary_storage_port.modes")
    if len(modes) != 2:
        raise GateError("boundary template must have exactly two modes")

    mode_facts: dict[str, dict[str, Any]] = {}
    for index, raw_mode in enumerate(modes):
        mode = _mapping(raw_mode, f"boundary_storage_port.modes[{index}]")
        mode_id = mode.get("id")
        if type(mode_id) is not str or mode_id in mode_facts:
            raise GateError("boundary mode ids must be unique strings")
        body = _mapping(mode.get("body"), f"boundary mode {mode_id}.body")
        ports = _array(mode.get("ports"), f"boundary mode {mode_id}.ports")
        if len(ports) != 1:
            raise GateError(f"boundary mode {mode_id} must have exactly one port")
        port = _mapping(ports[0], f"boundary mode {mode_id}.port")
        if port.get("kind") != "output":
            raise GateError(f"boundary mode {mode_id} port is not an output")
        cell = _mapping(port.get("body_cell"), f"boundary mode {mode_id}.body_cell")
        direction = port.get("direction")
        if type(direction) is not str:
            raise GateError(f"boundary mode {mode_id} direction is invalid")
        step_x, step_y = _direction_step(direction)
        mode_facts[mode_id] = {
            "body": [
                _exact_int(body.get("width"), f"{mode_id}.body.width"),
                _exact_int(body.get("height"), f"{mode_id}.body.height"),
            ],
            "direction": direction,
            "body_cell": [
                _exact_int(cell.get("x"), f"{mode_id}.body_cell.x"),
                _exact_int(cell.get("y"), f"{mode_id}.body_cell.y"),
            ],
            "access_offset": [
                _exact_int(cell.get("x"), f"{mode_id}.body_cell.x") + step_x,
                _exact_int(cell.get("y"), f"{mode_id}.body_cell.y") + step_y,
            ],
        }
    expected_modes = {
        "left_boundary": {
            "body": [1, 3],
            "direction": "E",
            "body_cell": [0, 1],
            "access_offset": [1, 1],
        },
        "bottom_boundary": {
            "body": [3, 1],
            "direction": "N",
            "body_cell": [1, 0],
            "access_offset": [1, 1],
        },
    }
    if mode_facts != expected_modes:
        raise GateError(f"boundary modes/access offsets drifted: {mode_facts}")

    required = _array(root.get("required_instances"), "required_instances")
    boundary_count = sum(
        _mapping(item, f"required_instances[{index}]").get("template") == "boundary_storage_port"
        for index, item in enumerate(required)
    )
    core_count = sum(
        _mapping(item, f"required_instances[{index}]").get("template") == "protocol_core"
        for index, item in enumerate(required)
    )
    if (boundary_count, core_count) != (46, 1):
        raise GateError("raw-provider instance multiplicities drifted")

    core = _mapping(templates.get("protocol_core"), "facility_templates.protocol_core")
    core_outputs = {
        _physical_output_count(
            _mapping(mode, f"protocol_core.modes[{index}]"),
            f"protocol_core.modes[{index}]",
        )
        for index, mode in enumerate(_array(core.get("modes"), "protocol_core.modes"))
    }
    if core_outputs != {6}:
        raise GateError(f"protocol-core output capacity drifted: {core_outputs}")
    boundary_outputs = {
        _physical_output_count(
            _mapping(mode, f"boundary_storage_port.modes[{index}]"),
            f"boundary_storage_port.modes[{index}]",
        )
        for index, mode in enumerate(modes)
    }
    if boundary_outputs != {1}:
        raise GateError("boundary output capacity drifted")

    generic = _mapping(root.get("generic_requirements"), "generic_requirements")
    raw_outputs = _mapping(generic.get("raw_outputs"), "generic_requirements.raw_outputs")
    raw_demand = sum(_exact_int(value, f"generic_requirements.raw_outputs.{key}") for key, value in raw_outputs.items())
    providers = list(
        _array(
            generic.get("raw_output_providers"),
            "generic_requirements.raw_output_providers",
        )
    )
    if providers != ["boundary_storage_port", "protocol_core"]:
        raise GateError("raw-output provider set/order drifted")
    provider_capacity = boundary_count + next(iter(core_outputs))
    if (raw_demand, provider_capacity) != (52, 52):
        raise GateError(f"raw-provider saturation drifted: demand={raw_demand}, capacity={provider_capacity}")
    return {
        "grid": {"width": GRID_SIDE, "height": GRID_SIDE},
        "minimum_side": MINIMUM_SIDE,
        "boundary_modes": mode_facts,
        "boundary_instances": boundary_count,
        "protocol_core_instances": core_count,
        "boundary_output_capacity_each": 1,
        "protocol_core_output_capacity": next(iter(core_outputs)),
        "raw_output_demand": raw_demand,
        "raw_provider_capacity": provider_capacity,
        "saturation_identity": "52 = 46 * 1 + 6",
    }


def _anchors(gap: int) -> tuple[int, ...]:
    if gap not in range(0, GRID_SIDE, 3):
        raise GateError(f"invalid boundary gap: {gap}")
    result = tuple(3 * index + int(3 * index >= gap) for index in range(23))
    covered = {gap}
    for anchor in result:
        if not 0 <= anchor <= GRID_SIDE - 3:
            raise GateError("boundary anchor is out of range")
        body = set(range(anchor, anchor + 3))
        if covered & body:
            raise GateError("boundary anchor construction overlaps")
        covered |= body
    if covered != set(range(GRID_SIDE)):
        raise GateError("boundary gap construction does not tile the side")
    return result


def _patterns() -> list[dict[str, Any]]:
    gaps = tuple(range(0, GRID_SIDE, 3))
    pairs = [(0, bottom_gap) for bottom_gap in gaps]
    pairs.extend((left_gap, 0) for left_gap in gaps[1:])
    patterns: list[dict[str, Any]] = []
    for index, (left_gap, bottom_gap) in enumerate(pairs):
        left_anchors = _anchors(left_gap)
        bottom_anchors = _anchors(bottom_gap)
        q_cells = [(1, anchor + 1, "left") for anchor in left_anchors]
        q_cells.extend((anchor + 1, 1, "bottom") for anchor in bottom_anchors)
        coordinates = [(x, y) for x, y, _side in q_cells]
        if len(coordinates) != 46 or len(set(coordinates)) != 46:
            raise GateError("a legal pattern does not have 46 distinct Q cells")
        patterns.append(
            {
                "index": index,
                "left_gap": left_gap,
                "bottom_gap": bottom_gap,
                "left_anchors": list(left_anchors),
                "bottom_anchors": list(bottom_anchors),
                "q_cells": q_cells,
            }
        )
    if len(patterns) != EXPECTED_PATTERNS:
        raise GateError("47-pattern reconstruction failed")
    if len({(item["left_gap"], item["bottom_gap"]) for item in patterns}) != len(patterns):
        raise GateError("boundary pattern reconstruction contains a duplicate")
    return patterns


def _placements() -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    for orientation_index, (width, height) in enumerate(DIMENSIONS):
        for x_value in range(1, GRID_SIDE - width + 1):
            for y_value in range(1, GRID_SIDE - height + 1):
                result.append(
                    {
                        "index": len(result),
                        "orientation_index": orientation_index,
                        "width": width,
                        "height": height,
                        "x": x_value,
                        "y": y_value,
                        "area": width * height,
                    }
                )
    if len(result) != EXPECTED_PLACEMENTS:
        raise GateError(f"placement reconstruction count drifted: {len(result)}")
    return result


def _q_e(
    pattern: Mapping[str, Any],
    placement: Mapping[str, int],
    *,
    normal_offset: int = 1,
    include_endpoints: bool = True,
) -> tuple[int, int]:
    x_value = placement["x"]
    y_value = placement["y"]
    x_last = x_value + placement["width"] - 1
    y_last = y_value + placement["height"] - 1
    q_value = 0
    e_value = 0
    left_anchors = _array(pattern["left_anchors"], "pattern.left_anchors")
    bottom_anchors = _array(pattern["bottom_anchors"], "pattern.bottom_anchors")
    for anchor in left_anchors:
        tangential = _exact_int(anchor, "left anchor") + 1
        if x_value <= normal_offset <= x_last and y_value <= tangential <= y_last:
            q_value += 1
            if include_endpoints and tangential in {y_value, y_last}:
                e_value += 1
    for anchor in bottom_anchors:
        tangential = _exact_int(anchor, "bottom anchor") + 1
        if y_value <= normal_offset <= y_last and x_value <= tangential <= x_last:
            q_value += 1
            if include_endpoints and tangential in {x_value, x_last}:
                e_value += 1
    return q_value, e_value


def _lhs(
    placement: Mapping[str, int],
    q_value: int,
    e_value: int,
    *,
    divisor: int = INCIDENCE_CAP,
    round_up: bool = True,
) -> int:
    numerator = MEMBRANE_NUMERATOR - placement["width"] - placement["height"] + q_value // 2 + e_value
    quotient = _ceil_div(numerator, divisor) if round_up else numerator // divisor
    return placement["area"] + quotient


def _derive_band() -> dict[str, Any]:
    patterns = _patterns()
    placements = _placements()
    forbidden: list[dict[str, int]] = []
    orientation_candidates: Counter[str] = Counter()
    orientation_survivors: Counter[str] = Counter()
    q_e_digest = hashlib.sha256(b"b1-q-e-corpus-v1\0")
    endpoint_positive = 0
    for pattern in patterns:
        for placement in placements:
            key = f"{placement['width']}x{placement['height']}"
            orientation_candidates[key] += 1
            q_value, e_value = _q_e(pattern, placement)
            endpoint_positive += e_value > 0
            q_e_digest.update(f"{pattern['index']},{placement['index']},{q_value},{e_value}\n".encode("ascii"))
            lhs = _lhs(placement, q_value, e_value)
            if lhs <= FREE_CELL_CAP:
                orientation_survivors[key] += 1
            else:
                numerator = MEMBRANE_NUMERATOR - placement["width"] - placement["height"] + q_value // 2 + e_value
                forbidden.append(
                    {
                        "pattern_variable_id": pattern["index"] + 1,
                        "placement_variable_id": (EXPECTED_PATTERNS + placement["index"] + 1),
                        "pattern_index": pattern["index"],
                        "left_gap": pattern["left_gap"],
                        "bottom_gap": pattern["bottom_gap"],
                        "width": placement["width"],
                        "height": placement["height"],
                        "x": placement["x"],
                        "y": placement["y"],
                        "q": q_value,
                        "e": e_value,
                        "numerator": numerator,
                        "ceil_term": _ceil_div(numerator, INCIDENCE_CAP),
                        "lhs": lhs,
                        "rhs": FREE_CELL_CAP,
                    }
                )
    pair_corpus = len(patterns) * len(placements)
    allowed_pairs = pair_corpus - len(forbidden)
    if (
        pair_corpus,
        allowed_pairs,
        len(forbidden),
        dict(orientation_survivors),
    ) != (
        EXPECTED_PAIR_CORPUS,
        EXPECTED_ALLOWED_PAIRS,
        EXPECTED_EXCLUSIONS,
        EXPECTED_ORIENTATION_SURVIVORS,
    ):
        raise GateError("independent ceiling corpus differs from the admitted B1 result")
    return {
        "patterns": patterns,
        "placements": placements,
        "forbidden": forbidden,
        "pattern_count": len(patterns),
        "placement_count": len(placements),
        "pair_corpus": pair_corpus,
        "allowed_pairs": allowed_pairs,
        "orientation_candidates": dict(orientation_candidates),
        "orientation_survivors": dict(orientation_survivors),
        "q_e_corpus_sha256": q_e_digest.hexdigest(),
        "endpoint_positive_pairs": endpoint_positive,
    }


def _variables(band: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw_pattern in _array(band["patterns"], "band.patterns"):
        pattern = _mapping(raw_pattern, "pattern")
        index = _exact_int(pattern["index"], "pattern.index")
        result.append(
            {
                "id": len(result) + 1,
                "name": (
                    f"pattern__index_{index:02d}__left_gap_{pattern['left_gap']:02d}"
                    f"__bottom_gap_{pattern['bottom_gap']:02d}"
                ),
                "kind": "boundary_pattern_selector",
                "pattern_index": index,
                "left_gap": pattern["left_gap"],
                "bottom_gap": pattern["bottom_gap"],
            }
        )
    for raw_placement in _array(band["placements"], "band.placements"):
        placement = _mapping(raw_placement, "placement")
        result.append(
            {
                "id": len(result) + 1,
                "name": (
                    f"placement__w_{placement['width']:02d}__h_{placement['height']:02d}"
                    f"__x_{placement['x']:02d}__y_{placement['y']:02d}"
                ),
                "kind": "rectangle_placement_selector",
                "width": placement["width"],
                "height": placement["height"],
                "x": placement["x"],
                "y": placement["y"],
                "area": placement["area"],
                "minimum_side": min(placement["width"], placement["height"]),
            }
        )
    if len(result) != EXPECTED_VARIABLES:
        raise GateError("variable reconstruction count drifted")
    return result


def _constraint_key(terms: Iterable[tuple[int, int]], relation: str, rhs: int) -> ConstraintKey:
    if relation not in {"=", ">="}:
        raise GateError(f"unsupported OPB relation: {relation}")
    combined: Counter[int] = Counter()
    for variable, coefficient in terms:
        variable = _exact_int(variable, "constraint variable")
        coefficient = _exact_int(coefficient, "constraint coefficient")
        if variable <= 0:
            raise GateError("constraint variable ids must be positive")
        combined[variable] += coefficient
    canonical = tuple(sorted((variable, coefficient) for variable, coefficient in combined.items() if coefficient))
    if not canonical:
        raise GateError("constant-only OPB constraint is forbidden")
    return relation, _exact_int(rhs, "constraint rhs"), canonical


def _expected_constraints(band: Mapping[str, Any]) -> Counter[ConstraintKey]:
    constraints: Counter[ConstraintKey] = Counter()
    pattern_ids = range(1, EXPECTED_PATTERNS + 1)
    placement_ids = range(EXPECTED_PATTERNS + 1, EXPECTED_VARIABLES + 1)
    constraints[_constraint_key(((item, 1) for item in pattern_ids), "=", 1)] += 1
    constraints[_constraint_key(((item, 1) for item in placement_ids), "=", 1)] += 1
    for item in _array(band["forbidden"], "band.forbidden"):
        record = _mapping(item, "forbidden pair")
        pattern_variable = _exact_int(record["pattern_variable_id"], "pattern_variable_id")
        placement_variable = _exact_int(record["placement_variable_id"], "placement_variable_id")
        constraints[_constraint_key(((pattern_variable, -1), (placement_variable, -1)), ">=", -1)] += 1
    if sum(constraints.values()) != EXPECTED_CONSTRAINTS:
        raise GateError("expected constraint count drifted")
    return constraints


def _parse_constraint(line: str, line_number: int) -> ConstraintKey:
    match = CONSTRAINT_RE.fullmatch(line)
    if match is None:
        raise GateError(f"malformed OPB constraint at line {line_number}")
    lhs, relation, raw_rhs = match.groups()
    position = 0
    terms: list[tuple[int, int]] = []
    seen: set[int] = set()
    while position < len(lhs):
        term_match = TERM_RE.match(lhs, position)
        if term_match is None:
            raise GateError(f"malformed or nonlinear OPB token at line {line_number}")
        coefficient = int(term_match.group(1))
        variable = int(term_match.group(2))
        if coefficient == 0:
            raise GateError(f"zero OPB coefficient at line {line_number}")
        if variable in seen:
            raise GateError(f"duplicate OPB variable term at line {line_number}")
        seen.add(variable)
        terms.append((variable, coefficient))
        position = term_match.end()
    return _constraint_key(terms, relation, int(raw_rhs))


def _parse_opb(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise GateError("OPB must be ASCII") from exc
    header: dict[str, int] | None = None
    constraints: Counter[ConstraintKey] = Counter()
    equality_count = 0
    maximum_variable = 0
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if line.startswith("*"):
            header_match = HEADER_RE.fullmatch(line)
            if header_match is not None:
                if header is not None:
                    raise GateError("OPB has multiple competition headers")
                values = [int(value) for value in header_match.groups()]
                header = dict(
                    zip(
                        ("variables", "constraints", "equal", "intsize"),
                        values,
                        strict=True,
                    )
                )
            continue
        key = _parse_constraint(line, line_number)
        constraints[key] += 1
        equality_count += key[0] == "="
        maximum_variable = max(maximum_variable, *(variable for variable, _coefficient in key[2]))
    if header is None:
        raise GateError("OPB competition header is missing")
    return {
        "raw": raw,
        "sha256": _sha256(raw),
        "size_bytes": len(raw),
        "header": header,
        "constraints": constraints,
        "constraint_count": sum(constraints.values()),
        "equality_count": equality_count,
        "maximum_variable": maximum_variable,
    }


def _multiset_hash(value: Counter[ConstraintKey]) -> str:
    digest = hashlib.sha256(b"b1-q-membrane-halo-constraint-multiset-v1\0")
    for (relation, rhs, terms), multiplicity in sorted(value.items()):
        payload = [
            relation,
            rhs,
            [[variable, coefficient] for variable, coefficient in terms],
            multiplicity,
        ]
        digest.update(json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _multiset_diff(expected: Counter[ConstraintKey], actual: Counter[ConstraintKey]) -> dict[str, Any]:
    def _examples(value: Counter[ConstraintKey]) -> list[dict[str, Any]]:
        return [
            {
                "relation": key[0],
                "rhs": key[1],
                "terms": [[variable, coefficient] for variable, coefficient in key[2]],
                "multiplicity": count,
            }
            for key, count in sorted(value.items())[:10]
        ]

    missing = expected - actual
    unexpected = actual - expected
    return {
        "missing_total": sum(missing.values()),
        "unexpected_total": sum(unexpected.values()),
        "missing_examples": _examples(missing),
        "unexpected_examples": _examples(unexpected),
    }


def _counts() -> dict[str, int]:
    return {
        "boundary_patterns": EXPECTED_PATTERNS,
        "rectangle_placements": EXPECTED_PLACEMENTS,
        "pattern_placement_corpus": EXPECTED_PAIR_CORPUS,
        "surviving_pairs": EXPECTED_ALLOWED_PAIRS,
        "violating_pairs": EXPECTED_EXCLUSIONS,
        "pattern_selector_variables": EXPECTED_PATTERNS,
        "placement_selector_variables": EXPECTED_PLACEMENTS,
        "variables": EXPECTED_VARIABLES,
        "equality_constraints": EXPECTED_EQUALITIES,
        "pair_exclusion_constraints": EXPECTED_EXCLUSIONS,
        "constraints": EXPECTED_CONSTRAINTS,
    }


def _band_summary(band: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "objective_floor": {"area": 1190, "minimum_side": 34},
        "oriented_dimensions": [[width, height] for width, height in DIMENSIONS],
        "anchor_bounds": [
            {"width": 34, "height": 35, "x": [1, 36], "y": [1, 35]},
            {"width": 35, "height": 34, "x": [1, 35], "y": [1, 36]},
        ],
        "placements_by_orientation": {"34x35": 1260, "35x34": 1260},
        "surviving_pairs_by_orientation": dict(band["orientation_survivors"]),
    }


def _formula() -> dict[str, Any]:
    return {
        "display": "wh + ceil((580-w-h+floor(q/2)+e)/4) <= 1320",
        "q_definition": "cardinality of rectangle intersection with active boundary-access set Q_delta",
        "e_definition": "Q_delta contacts at a tangential rectangle endpoint",
        "membrane_constant": MEMBRANE_NUMERATOR,
        "incidence_cap": INCIDENCE_CAP,
        "free_cell_cap": FREE_CELL_CAP,
        "all_q_e_area_ceil_values_precomputed": True,
        "nonlinear_terms_in_opb_constraints": False,
    }


def _claim_scope() -> dict[str, Any]:
    return {
        "given_geometry": (
            "the reviewed B1 necessity lemma combining Q_delta contacts, membrane "
            "counting, and the nine-pole halo lower bound"
        ),
        "inside_opb": (
            "exactly one legal boundary pattern, exactly one ceiling-band rectangle "
            "placement, and all precomputed violating pattern-placement exclusions"
        ),
        "limitations": [
            "build-only diagnostic; no solver or proof checker was run",
            "does not establish a new upper bound",
            "does not provide a witness or prove attainability",
            "does not prove global optimality",
            "research artifact; not sealed and not production CERTIFIED evidence",
        ],
    }


def _semantic_canaries(
    band: Mapping[str, Any],
    expected_constraints: Counter[ConstraintKey],
    actual_constraints: Counter[ConstraintKey],
) -> dict[str, dict[str, Any]]:
    patterns = _array(band["patterns"], "band.patterns")
    placements = _array(band["placements"], "band.placements")

    def mutated_scan(
        *, normal_offset: int = 1, include_endpoints: bool = True, divisor: int = 4, round_up: bool = True
    ) -> tuple[int, str]:
        rejected = 0
        digest = hashlib.sha256(b"b1-q-e-corpus-v1\0")
        for raw_pattern in patterns:
            pattern = _mapping(raw_pattern, "pattern")
            for raw_placement in placements:
                placement = _mapping(raw_placement, "placement")
                q_value, e_value = _q_e(
                    pattern,
                    placement,
                    normal_offset=normal_offset,
                    include_endpoints=include_endpoints,
                )
                digest.update(f"{pattern['index']},{placement['index']},{q_value},{e_value}\n".encode("ascii"))
                if (
                    _lhs(
                        placement,
                        q_value,
                        e_value,
                        divisor=divisor,
                        round_up=round_up,
                    )
                    > FREE_CELL_CAP
                ):
                    rejected += 1
        return rejected, digest.hexdigest()

    q_offset_rejected, q_offset_digest = mutated_scan(normal_offset=0)
    endpoint_rejected, endpoint_digest = mutated_scan(include_endpoints=False)
    floor_rejected, _floor_digest = mutated_scan(round_up=False)
    cap5_rejected, _cap5_digest = mutated_scan(divisor=5)
    deleted = list(patterns[:-1])
    duplicated = [*patterns, patterns[-1]]
    pattern_mutations_rejected = (
        len(deleted) != EXPECTED_PATTERNS
        and len(duplicated) != EXPECTED_PATTERNS
        and len(
            {
                (item["left_gap"], item["bottom_gap"])
                for item in map(lambda value: _mapping(value, "pattern"), duplicated)
            }
        )
        != len(duplicated)
    )
    removed_constraint = expected_constraints.copy()
    exclusion = next(key for key in sorted(removed_constraint) if key[0] == ">=" and len(key[2]) == 2)
    removed_constraint[exclusion] -= 1
    if not removed_constraint[exclusion]:
        del removed_constraint[exclusion]
    resealed_mutation = expected_constraints.copy()
    resealed_mutation[_constraint_key(((1, -2), (48, -1)), ">=", -1)] += 1
    resealed_mutation[exclusion] -= 1
    if not resealed_mutation[exclusion]:
        del resealed_mutation[exclusion]
    expected_hash = _multiset_hash(expected_constraints)
    actual_hash = _multiset_hash(actual_constraints)
    return {
        "q_access_offset_resealed": {
            "pass": (q_offset_rejected != EXPECTED_EXCLUSIONS and q_offset_digest != band["q_e_corpus_sha256"]),
            "baseline_rejections": EXPECTED_EXCLUSIONS,
            "mutated_rejections": q_offset_rejected,
        },
        "pattern_set_resealed": {
            "pass": pattern_mutations_rejected,
            "baseline_count": len(patterns),
            "deleted_count": len(deleted),
            "duplicated_count": len(duplicated),
        },
        "endpoint_term_live": {
            "pass": (
                band["endpoint_positive_pairs"] > 0
                and endpoint_digest != band["q_e_corpus_sha256"]
                and endpoint_rejected == EXPECTED_EXCLUSIONS
            ),
            "endpoint_positive_pairs": band["endpoint_positive_pairs"],
            "mutated_rejections": endpoint_rejected,
            "note": "the q/e corpus changes even though this ceiling exclusion set happens not to",
        },
        "outer_ceiling_resealed": {
            "pass": floor_rejected != EXPECTED_EXCLUSIONS,
            "baseline_rejections": EXPECTED_EXCLUSIONS,
            "floor_mutation_rejections": floor_rejected,
        },
        "incidence_cap_four_resealed": {
            "pass": cap5_rejected != EXPECTED_EXCLUSIONS,
            "baseline_rejections": EXPECTED_EXCLUSIONS,
            "cap_five_rejections": cap5_rejected,
        },
        "removed_exclusion_detected": {
            "pass": removed_constraint != expected_constraints
            and sum(removed_constraint.values()) == EXPECTED_CONSTRAINTS - 1,
            "mutated_constraint_count": sum(removed_constraint.values()),
        },
        "constraint_multiset_resealed": {
            "pass": (
                expected_constraints == actual_constraints
                and expected_hash == actual_hash
                and _multiset_hash(resealed_mutation) != expected_hash
            ),
            "expected_sha256": expected_hash,
            "actual_sha256": actual_hash,
            "mutated_sha256": _multiset_hash(resealed_mutation),
        },
    }


def _record_shape(value: Any, field: str) -> dict[str, Any]:
    record = _mapping(value, field)
    _closed(record, {"path", "sha256", "size_bytes"}, field)
    path = record.get("path")
    digest = record.get("sha256")
    size = record.get("size_bytes")
    if type(path) is not str or not path:
        raise GateError(f"{field}.path must be a nonempty string")
    if type(digest) is not str or SHA256_RE.fullmatch(digest) is None:
        raise GateError(f"{field}.sha256 is invalid")
    if type(size) is not int or size <= 0:
        raise GateError(f"{field}.size_bytes must be positive")
    return dict(record)


def _string_argv(value: Any, field: str) -> bool:
    return isinstance(value, list) and bool(value) and all(type(item) is str and item for item in value)


def verify(
    *,
    project_root: Path,
    opb_path: Path,
    meta_path: Path,
    var_map_path: Path,
    estimate_path: Path,
    argv_record: Sequence[str],
) -> dict[str, Any]:
    project_root = project_root.resolve()
    strict_path = project_root / STRICT_RELATIVE_PATH
    strict_raw = strict_path.read_bytes()
    if _sha256(strict_raw) != STRICT_SHA256:
        raise GateError("strict problem-instance SHA-256 differs from the B1 pin")
    strict_facts = _derive_strict(_strict_json(strict_raw, "strict problem instance"))
    band = _derive_band()
    expected_variables = _variables(band)
    expected_constraints = _expected_constraints(band)
    expected_counts = _counts()
    expected_band = _band_summary(band)
    expected_formula = _formula()
    expected_claim = _claim_scope()

    estimate_raw = estimate_path.read_bytes()
    meta_raw = meta_path.read_bytes()
    var_map_raw = var_map_path.read_bytes()
    estimate = _mapping(_strict_json(estimate_raw, "estimate"), "estimate")
    metadata = _mapping(_strict_json(meta_raw, "metadata"), "metadata")
    var_map = _mapping(_strict_json(var_map_raw, "variable map"), "variable map")
    parsed = _parse_opb(opb_path)

    if estimate.get("schema_version") != ESTIMATE_SCHEMA:
        raise GateError("estimate schema identity is invalid")
    if metadata.get("schema_version") != METADATA_SCHEMA:
        raise GateError("metadata schema identity is invalid")
    if var_map.get("schema_version") != VARIABLE_MAP_SCHEMA:
        raise GateError("variable-map schema identity is invalid")

    # The exact artifact envelopes are intentionally closed.  This makes a
    # schema change an explicit review event instead of silently trusting an
    # unexamined field.
    _closed(
        estimate,
        {
            "argv",
            "band",
            "claim_scope",
            "counts",
            "decision",
            "encoder_script_sha256",
            "formula",
            "harness",
            "harness_source",
            "metadata_schema_version",
            "model_schema_version",
            "project_root",
            "projected_outputs",
            "resource_contract",
            "schema_version",
            "semantics",
            "status",
            "strict_instance",
            "variable_map_schema_version",
        },
        "estimate",
    )
    _closed(
        metadata,
        {
            "argv",
            "band_scan",
            "claim_scope",
            "counts",
            "encoder_script_sha256",
            "estimate",
            "estimate_schema_version",
            "formula",
            "harness",
            "harness_source",
            "model_schema_version",
            "outputs",
            "project_root",
            "proof_status",
            "resource_contract",
            "schema_version",
            "semantics",
            "status",
            "strict_instance",
            "variable_map_schema_version",
            "violating_pairs",
        },
        "metadata",
    )
    _closed(
        var_map,
        {
            "counts",
            "model_schema_version",
            "schema_version",
            "semantics",
            "status",
            "strict_instance_sha256",
            "variable_count",
            "variables",
        },
        "variable map",
    )

    strict_record = _mapping(estimate.get("strict_instance"), "estimate.strict_instance")
    _closed(strict_record, {"path", "sha256", "size_bytes"}, "estimate.strict_instance")
    expected_strict_record = _file_record(strict_path, project_root)
    if not _type_exact_equal(dict(strict_record), expected_strict_record):
        raise GateError("estimate strict-instance provenance mismatch")
    if not _type_exact_equal(metadata.get("strict_instance"), expected_strict_record):
        raise GateError("metadata strict-instance provenance mismatch")

    identity_payloads = (estimate, metadata, var_map)
    if any(payload.get("model_schema_version") != MODEL_SCHEMA for payload in identity_payloads):
        raise GateError("model schema identity is invalid")
    if any(payload.get("semantics") != SEMANTICS for payload in identity_payloads):
        raise GateError("build-only semantics identity is invalid")
    if estimate.get("metadata_schema_version") != METADATA_SCHEMA:
        raise GateError("estimate metadata-schema identity is invalid")
    if estimate.get("variable_map_schema_version") != VARIABLE_MAP_SCHEMA:
        raise GateError("estimate variable-map schema identity is invalid")
    if metadata.get("estimate_schema_version") != ESTIMATE_SCHEMA:
        raise GateError("metadata estimate-schema identity is invalid")
    if metadata.get("variable_map_schema_version") != VARIABLE_MAP_SCHEMA:
        raise GateError("metadata variable-map schema identity is invalid")

    encoder_sha = estimate.get("encoder_script_sha256")
    if type(encoder_sha) is not str or SHA256_RE.fullmatch(encoder_sha) is None:
        raise GateError("estimate encoder_script_sha256 is invalid")
    if metadata.get("encoder_script_sha256") != encoder_sha:
        raise GateError("encoder script SHA provenance differs across artifacts")
    estimate_source = _record_shape(estimate.get("harness_source"), "estimate.harness_source")
    metadata_source = _record_shape(metadata.get("harness_source"), "metadata.harness_source")
    expected_source_path = str(ENCODER_RELATIVE_PATH)
    current_encoder_source = _file_record(
        project_root / ENCODER_RELATIVE_PATH,
        project_root,
    )
    if (
        estimate_source != metadata_source
        or estimate_source != current_encoder_source
        or estimate_source["path"] != expected_source_path
        or estimate_source["sha256"] != encoder_sha
    ):
        raise GateError("encoder harness-source provenance is inconsistent")

    projected = _mapping(estimate.get("projected_outputs"), "estimate.projected_outputs")
    _closed(projected, {"opb_bytes"}, "estimate.projected_outputs")
    if _exact_int(projected.get("opb_bytes"), "projected_outputs.opb_bytes") != parsed["size_bytes"]:
        raise GateError("projected OPB byte count differs from the built OPB")

    estimate_record = _record_shape(metadata.get("estimate"), "metadata.estimate")
    outputs = _mapping(metadata.get("outputs"), "metadata.outputs")
    _closed(outputs, {"metadata", "opb", "var_map"}, "metadata.outputs")
    opb_record = _record_shape(outputs.get("opb"), "metadata.outputs.opb")
    var_map_record = _record_shape(outputs.get("var_map"), "metadata.outputs.var_map")
    metadata_output = _mapping(outputs.get("metadata"), "metadata.outputs.metadata")
    _closed(metadata_output, {"path"}, "metadata.outputs.metadata")
    expected_estimate_record = _file_record(estimate_path, project_root)
    expected_opb_record = _file_record(opb_path, project_root)
    expected_var_map_record = _file_record(var_map_path, project_root)
    expected_metadata_path = _file_record(meta_path, project_root)["path"]
    hash_checks = {
        "estimate": estimate_record == expected_estimate_record,
        "opb": opb_record == expected_opb_record and opb_record["sha256"] == parsed["sha256"],
        "var_map": var_map_record == expected_var_map_record,
        "metadata_path": metadata_output.get("path") == expected_metadata_path,
    }
    if not all(hash_checks.values()):
        raise GateError(f"metadata artifact hash mismatch: {hash_checks}")

    resource_match = all(
        _type_exact_equal(payload.get("resource_contract"), EXPECTED_RESOURCE_CONTRACT)
        for payload in (estimate, metadata)
    )
    claim_match = all(_type_exact_equal(payload.get("claim_scope"), expected_claim) for payload in (estimate, metadata))
    estimate_match = (
        estimate.get("status") == "PASS"
        and estimate.get("decision") == "BUILD_ONLY"
        and estimate.get("harness") == ENCODER_HARNESS
        and _string_argv(estimate.get("argv"), "estimate.argv")
        and estimate.get("project_root") == str(project_root)
        and _type_exact_equal(estimate.get("band"), expected_band)
        and _type_exact_equal(estimate.get("counts"), expected_counts)
        and _type_exact_equal(estimate.get("formula"), expected_formula)
        and resource_match
        and claim_match
    )
    metadata_match = (
        metadata.get("status") == "PASS"
        and metadata.get("harness") == ENCODER_HARNESS
        and _string_argv(metadata.get("argv"), "metadata.argv")
        and metadata.get("project_root") == str(project_root)
        and _type_exact_equal(metadata.get("band_scan"), expected_band)
        and _type_exact_equal(metadata.get("counts"), expected_counts)
        and _type_exact_equal(metadata.get("formula"), expected_formula)
        and _type_exact_equal(metadata.get("violating_pairs"), band["forbidden"])
        and metadata.get("proof_status") == "build_only_no_solver_or_proof"
        and resource_match
        and claim_match
    )

    variables = var_map.get("variables")
    dense = (
        isinstance(variables, list)
        and all(isinstance(item, Mapping) for item in variables)
        and [item.get("id") for item in variables] == list(range(1, EXPECTED_VARIABLES + 1))
        and len({item.get("name") for item in variables}) == EXPECTED_VARIABLES
    )
    variable_map_match = (
        var_map.get("status") == "PASS"
        and var_map.get("model_schema_version") == MODEL_SCHEMA
        and var_map.get("semantics") == SEMANTICS
        and var_map.get("strict_instance_sha256") == STRICT_SHA256
        and var_map.get("variable_count") == EXPECTED_VARIABLES
        and _type_exact_equal(var_map.get("counts"), expected_counts)
        and _type_exact_equal(variables, expected_variables)
    )

    header_match = parsed["header"] == {
        "variables": EXPECTED_VARIABLES,
        "constraints": EXPECTED_CONSTRAINTS,
        "equal": EXPECTED_EQUALITIES,
        "intsize": 64,
    }
    opb_shape_match = (
        parsed["constraint_count"] == EXPECTED_CONSTRAINTS
        and parsed["equality_count"] == EXPECTED_EQUALITIES
        and parsed["maximum_variable"] == EXPECTED_VARIABLES
    )
    constraints_match = parsed["constraints"] == expected_constraints
    constraint_diff = _multiset_diff(expected_constraints, parsed["constraints"])
    canaries = _semantic_canaries(band, expected_constraints, parsed["constraints"])
    canaries_pass = all(item.get("pass") is True for item in canaries.values())

    corpus_errors: list[dict[str, Any]] = []
    if len(band["forbidden"]) != EXPECTED_EXCLUSIONS:
        corpus_errors.append({"type": "forbidden_count", "actual": len(band["forbidden"])})
    if band["allowed_pairs"] != EXPECTED_ALLOWED_PAIRS:
        corpus_errors.append({"type": "allowed_count", "actual": band["allowed_pairs"]})
    if band["orientation_survivors"] != EXPECTED_ORIENTATION_SURVIVORS:
        corpus_errors.append({"type": "orientation_survivors", "actual": band["orientation_survivors"]})

    checks = {
        "strict_instance_closed_and_hashed": True,
        "strict_grid_modes_access_offsets_exact": True,
        "raw_provider_saturation_exact": True,
        "boundary_patterns_exact": band["pattern_count"] == EXPECTED_PATTERNS,
        "ceiling_placements_exact": band["placement_count"] == EXPECTED_PLACEMENTS,
        "q_e_allow_matrix_exact": corpus_errors == [],
        "artifact_hashes_exact": all(hash_checks.values()),
        "encoder_script_provenance_consistent": True,
        "estimate_reconstruction_exact": estimate_match,
        "metadata_reconstruction_exact": metadata_match,
        "variable_map_dense": dense,
        "variable_map_exact": variable_map_match,
        "resource_contract_exact": resource_match,
        "claim_scope_build_only": claim_match,
        "opb_header_exact": header_match and opb_shape_match,
        "constraint_multiset_exact": constraints_match,
        "semantic_mutation_canaries_pass": canaries_pass,
        "corpus_errors_empty": corpus_errors == [],
    }
    status = "PASS" if all(checks.values()) and corpus_errors == [] else "FAIL"
    return {
        "schema_version": GATE_SCHEMA,
        "status": status,
        "checks": checks,
        "strict_instance": expected_strict_record,
        "strict_facts": strict_facts,
        "translation_inputs": {
            "estimate": _file_record(estimate_path, project_root),
            "metadata": _file_record(meta_path, project_root),
            "opb": _file_record(opb_path, project_root),
            "var_map": _file_record(var_map_path, project_root),
        },
        "gate_provenance": {
            "source": _file_record(Path(__file__), project_root),
            "argv": list(argv_record),
            "project_root": str(project_root),
            "encoder_source_current": current_encoder_source,
        },
        "counts": expected_counts,
        "band_scan": expected_band,
        "formula": expected_formula,
        "constraint_multiset_sha256": {
            "expected": _multiset_hash(expected_constraints),
            "actual": _multiset_hash(parsed["constraints"]),
        },
        "constraint_diff": constraint_diff,
        "semantic_canaries": canaries,
        "corpus_errors": corpus_errors,
        "claim_scope": expected_claim,
        "proof_status": "translation_gate_only_no_solver_or_proof_run_no_unsat_claim",
    }


def _exclusive_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite gate output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--opb", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--var-map", type=Path, required=True)
    parser.add_argument("--estimate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite gate output: {args.output}")
    try:
        report = verify(
            project_root=args.project_root.resolve(),
            opb_path=args.opb.resolve(),
            meta_path=args.meta.resolve(),
            var_map_path=args.var_map.resolve(),
            estimate_path=args.estimate.resolve(),
            argv_record=[
                str(Path(__file__).resolve()),
                *(str(value) for value in (sys.argv[1:] if argv is None else argv)),
            ],
        )
    except Exception as exc:
        report = {
            "schema_version": GATE_SCHEMA,
            "status": "FAIL",
            "checks": {},
            "corpus_errors": [{"type": type(exc).__name__, "message": str(exc)}],
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "proof_status": "translation_gate_failed_no_solver_or_proof_claim",
        }
    _exclusive_json(args.output, report)
    print(
        json.dumps(
            {"status": report["status"], "output": str(args.output.resolve())},
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
