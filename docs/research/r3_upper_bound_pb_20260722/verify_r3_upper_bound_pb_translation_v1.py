"""Independently verify the R3 ``(1190, 34)`` arithmetic PB translation.

This research gate intentionally shares no implementation code with the
encoder or the historical R3 recomputation.  It binds the strict input and R3
evidence, rederives the membrane and power-halo arithmetic, reconstructs every
oriented selector and OPB constraint, and fails closed on any discrepancy.
It verifies a translation only; it does not prove the geometric lemmas, a
witness, attainability, global optimality, or a solver/proof result.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SEMANTICS = "r3_strict_upper_bound_1190_34_arithmetic_given_geometry_v1"
MODEL_SCHEMA = "r3_upper_bound_pb_v1"
META_SCHEMA = "r3_upper_bound_pb_metadata_v1"
VAR_MAP_SCHEMA = "r3_upper_bound_pb_var_map_v1"
ESTIMATE_SCHEMA = "r3_upper_bound_pb_estimate_v1"
GATE_SCHEMA = "r3_upper_bound_pb_translation_gate_v1"
ENCODER_NAME = "r3_upper_bound_pb_encoder_v1"
ENCODER_SOURCE = Path(__file__).with_name("r3_upper_bound_pb_encoder_v1.py")

TARGET_AREA = 1190
TARGET_MIN_SIDE = 34
EXPECTED_GIT_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
EXPECTED_VARIABLES = 2074
EXPECTED_CONSTRAINTS = 2075
EXPECTED_EQUALITIES = 1
PROOF_LIMIT_BYTES = 5_000_000_000
MINIMUM_PLANNING_BYTES = 512 * 1024 * 1024

INPUT_PATHS = {
    "problem_instance": Path(
        "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    ),
    "problem_instance_schema": Path(
        "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.schema.json"
    ),
    "problem_md": Path(
        "docs/research/cleanroom_rederivation_20260718/strict/external/problem.md"
    ),
    "sha256s": Path(
        "docs/research/cleanroom_rederivation_20260718/strict/external/SHA256SUMS"
    ),
}
INPUT_SHA256 = {
    "problem_instance": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    "problem_instance_schema": "5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23",
    "problem_md": "c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f",
    "sha256s": "8810d5d6a80d92438628b7694216d3b3c6c1be50543072ec9c3bcf510d9c4d70",
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
EVIDENCE_SHA256 = {
    "r3_response": "f0670a76fbd57cabcd41d50823421921d336b50fd36da61e6ab5b2f408c4a700",
    "r3_judgment": "8651e8b5a6deb255824293dc2bad35394c7e5d4143cc82ff0ed674ab93adb89e",
    "r3_adversarial_verdict": "d48ba75040c61d042d091a893f0331b837ebc994d2b18ad429bcb9fef4856da0",
    "independent_recomputation": "589b87a086f2c25015b535c5c12d68b6842aaa1f16fe449bcb94e3a733bd076a",
}

REQUIRED_CHECKS = frozenset(
    {
        "strict_bundle_closed_and_hashed",
        "r3_evidence_closed_and_hashed",
        "encoder_provenance_match",
        "translation_inputs_closed_and_hashed",
        "metadata_reconstruction_match",
        "estimate_reconstruction_match",
        "variable_map_dense",
        "variable_map_exact",
        "opb_header_exact",
        "constraint_multiset_exact",
        "strict_sentinels_exact",
        "membrane_class_table_exact",
        "halo_certificate_exact",
        "lex_better_band_exact",
        "arithmetic_corpus_unsat",
        "semantic_canaries_pass",
    }
)

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

# Doubled weights for the 14 half-cell Chebyshev orbits in the R3 certificate.
HALO_DOUBLED_WEIGHTS = {
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

HEADER_RE = re.compile(
    r"^\*\s+#variable=\s+(\d+)\s+#constraint=\s+(\d+)\s+"
    r"#equal=\s+(\d+)\s+intsize=\s+(\d+)\s*$"
)
CONSTRAINT_RE = re.compile(r"^(.*?)\s+(>=|=)\s+([+-]?\d+)\s*;\s*$")
TERM_RE = re.compile(r"\s*([+-]\d+)\s+x([1-9]\d*)")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
ConstraintKey = tuple[str, int, tuple[tuple[int, int], ...]]


class GateError(ValueError):
    """Raised for malformed, incomplete, or inconsistent gate inputs."""


def _exact_int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise GateError(f"{field} must be an exact integer")
    return value


def _positive_int(value: Any, field: str) -> int:
    result = _exact_int(value, field)
    if result <= 0:
        raise GateError(f"{field} must be positive")
    return result


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
    """Compare parsed artifacts without Python's bool/int equality alias."""

    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _type_exact_equal(actual[key], expected[key]) for key in expected
        )
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


def _display_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(project_root.resolve()))
    except ValueError:
        return str(resolved)


def _file_record(path: Path, project_root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"provenance file is missing: {resolved}")
    raw = resolved.read_bytes()
    return {
        "path": _display_path(resolved, project_root),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _validate_record(
    value: Any, expected_path: Path, project_root: Path, field: str
) -> dict[str, Any]:
    record = _mapping(value, field)
    expected = _file_record(expected_path, project_root)
    if not _type_exact_equal(dict(record), expected):
        raise GateError(f"{field} does not match the current pinned file")
    return expected


def _git_snapshot(project_root: Path) -> dict[str, Any]:
    head = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise GateError(f"unexpected Git revision: {head!r}")
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(project_root),
            "diff",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "HEAD",
            "--",
        ],
        check=True,
        capture_output=True,
    ).stdout
    status = subprocess.run(
        [
            "git",
            "-C",
            str(project_root),
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=normal",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return {
        "head": head,
        "tracked_dirty": bool(diff),
        "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "tracked_diff_size_bytes": len(diff),
        "status_dirty": bool(status),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "status_size_bytes": len(status),
    }


def _validate_git_snapshot(value: Any, field: str) -> dict[str, Any]:
    snapshot = _mapping(value, field)
    _closed(
        snapshot,
        {
            "head",
            "tracked_dirty",
            "tracked_diff_sha256",
            "tracked_diff_size_bytes",
            "status_dirty",
            "status_sha256",
            "status_size_bytes",
        },
        field,
    )
    head = snapshot.get("head")
    tracked_dirty = snapshot.get("tracked_dirty")
    tracked_digest = snapshot.get("tracked_diff_sha256")
    tracked_size = snapshot.get("tracked_diff_size_bytes")
    status_dirty = snapshot.get("status_dirty")
    status_digest = snapshot.get("status_sha256")
    status_size = snapshot.get("status_size_bytes")
    if type(head) is not str or re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise GateError(f"{field}.head is invalid")
    if type(tracked_dirty) is not bool:
        raise GateError(f"{field}.tracked_dirty must be boolean")
    if type(tracked_digest) is not str or SHA256_RE.fullmatch(tracked_digest) is None:
        raise GateError(f"{field}.tracked_diff_sha256 is invalid")
    if type(tracked_size) is not int or tracked_size < 0 or tracked_dirty is not (tracked_size > 0):
        raise GateError(f"{field} tracked dirty/size fields disagree")
    if type(status_dirty) is not bool:
        raise GateError(f"{field}.status_dirty must be boolean")
    if type(status_digest) is not str or SHA256_RE.fullmatch(status_digest) is None:
        raise GateError(f"{field}.status_sha256 is invalid")
    if type(status_size) is not int or status_size < 0 or status_dirty is not (status_size > 0):
        raise GateError(f"{field} status dirty/size fields disagree")
    return dict(snapshot)


def _bound_records(
    container: Mapping[str, Any],
    key: str,
    paths: Mapping[str, Path],
    pinned: Mapping[str, str],
    project_root: Path,
) -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    records = _mapping(container.get(key), key)
    if set(records) != set(paths) or set(pinned) != set(paths):
        raise GateError(f"{key} does not match the closed record set")
    raw_by_key: dict[str, bytes] = {}
    expected_records: dict[str, dict[str, Any]] = {}
    for name, relative_path in sorted(paths.items()):
        path = project_root / relative_path
        record = _validate_record(records[name], path, project_root, f"{key}.{name}")
        if record["sha256"] != pinned[name]:
            raise GateError(f"{key}.{name} differs from the pinned SHA-256")
        expected_records[name] = record
        raw_by_key[name] = path.read_bytes()
    return raw_by_key, expected_records


def _verify_sha256_manifest(raw: bytes, inputs: Mapping[str, bytes]) -> bool:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise GateError("SHA256SUMS is not ASCII") from exc
    entries: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match.group(2) in entries:
            raise GateError("SHA256SUMS is malformed or contains a duplicate")
        entries[match.group(2)] = match.group(1)
    required = {
        "problem.md": inputs["problem_md"],
        "problem_instance.json": inputs["problem_instance"],
        "problem_instance.schema.json": inputs["problem_instance_schema"],
    }
    expected_entries = {
        "R1_prompt.md": "5154e299b472e0f3c50507fa2820e86b480789f50e2608f4d8ca455cefb7c916",
        **{name: hashlib.sha256(data).hexdigest() for name, data in required.items()},
    }
    return _type_exact_equal(entries, expected_entries)


def _mode_area(templates: Mapping[str, Any], template_name: str) -> int:
    template = _mapping(templates.get(template_name), f"facility_templates.{template_name}")
    modes = _array(template.get("modes"), f"facility_templates.{template_name}.modes")
    if not modes:
        raise GateError(f"facility_templates.{template_name}.modes is empty")
    areas: set[int] = set()
    for index, raw_mode in enumerate(modes):
        mode = _mapping(raw_mode, f"{template_name}.modes[{index}]")
        body = _mapping(mode.get("body"), f"{template_name}.modes[{index}].body")
        areas.add(
            _positive_int(body.get("width"), "body.width")
            * _positive_int(body.get("height"), "body.height")
        )
    if len(areas) != 1:
        raise GateError(f"{template_name} modes do not have one common body area")
    return next(iter(areas))


def _needs_count(value: Any, field: str) -> int:
    if isinstance(value, Mapping):
        return sum(_positive_int(item, f"{field}.{key}") for key, item in value.items())
    return _exact_int(value, field)


def _validated_mode_ports(
    mode: Mapping[str, Any],
    directions: set[str],
    field: str,
) -> tuple[list[Mapping[str, Any]], int, int]:
    """Independently validate port coordinates, body edges, kinds, and uniqueness."""
    body = _mapping(mode.get("body"), f"{field}.body")
    width = _positive_int(body.get("width"), f"{field}.body.width")
    height = _positive_int(body.get("height"), f"{field}.body.height")
    ports = [
        _mapping(raw_port, f"{field}.ports[{index}]")
        for index, raw_port in enumerate(_array(mode.get("ports"), f"{field}.ports"))
    ]
    seen: set[tuple[int, int, str]] = set()
    for index, port in enumerate(ports):
        kind = port.get("kind")
        direction = port.get("direction")
        if kind not in {"input", "output"}:
            raise GateError(f"{field}.ports[{index}] has an invalid kind")
        if type(direction) is not str or direction not in directions:
            raise GateError(f"{field}.ports[{index}] has an invalid direction")
        cell = _mapping(port.get("body_cell"), f"{field}.ports[{index}].body_cell")
        x_value = _exact_int(cell.get("x"), f"{field}.ports[{index}].body_cell.x")
        y_value = _exact_int(cell.get("y"), f"{field}.ports[{index}].body_cell.y")
        if not (0 <= x_value < width and 0 <= y_value < height):
            raise GateError(f"{field}.ports[{index}] body cell is out of range")
        on_edge = {
            "N": y_value == height - 1,
            "E": x_value == width - 1,
            "S": y_value == 0,
            "W": x_value == 0,
        }[direction]
        if not on_edge:
            raise GateError(f"{field}.ports[{index}] is not on its declared body edge")
        geometry = (x_value, y_value, direction)
        if geometry in seen:
            raise GateError(f"{field} has duplicate physical port geometry {geometry}")
        seen.add(geometry)
    return ports, width, height


def _ceil_div(numerator: int, denominator: int) -> int:
    numerator = _exact_int(numerator, "ceil numerator")
    denominator = _positive_int(denominator, "ceil denominator")
    return -(-numerator // denominator)


def _halo_weight2(dx: int, dy: int, weights: Mapping[tuple[int, int], int]) -> int:
    first = abs(2 * dx - 1)
    second = abs(2 * dy - 1)
    return weights.get((max(first, second), min(first, second)), 0)


def _derive_halo(
    *,
    coverage: tuple[int, int, int, int],
    body_dimensions: Sequence[tuple[int, int]],
    powered_area: int,
    pole_body_dimensions: tuple[int, int],
    weights: Mapping[tuple[int, int], int] = HALO_DOUBLED_WEIGHTS,
) -> dict[str, Any]:
    x_min, x_max, y_min, y_max = coverage
    if coverage != (-5, 6, -5, 6):
        raise GateError("power coverage differs from the R3 halo premise")
    if pole_body_dimensions != (2, 2):
        raise GateError("pole body differs from the R3 2x2 premise")
    if any(type(value) is not int or value <= 0 for value in weights.values()):
        raise GateError("halo doubled weights must be positive integers")
    if len(weights) != 14:
        raise GateError("halo certificate does not contain exactly 14 weighted orbits")

    total_doubled = sum(
        _halo_weight2(dx, dy, weights)
        for dx in range(-12, 14)
        for dy in range(-12, 14)
    )
    pole_body = {
        (x, y)
        for x in range(pole_body_dimensions[0])
        for y in range(pole_body_dimensions[1])
    }
    counts: dict[str, int] = {}
    violations: list[dict[str, Any]] = []
    minimum_slack2: int | None = None
    for body_width, body_height in body_dimensions:
        checked = 0
        for anchor_x in range(x_min - body_width + 1, x_max + 1):
            for anchor_y in range(y_min - body_height + 1, y_max + 1):
                cells = [
                    (anchor_x + dx, anchor_y + dy)
                    for dx in range(body_width)
                    for dy in range(body_height)
                ]
                if not any(x_min <= x <= x_max and y_min <= y <= y_max for x, y in cells):
                    continue
                if any(cell in pole_body for cell in cells):
                    continue
                checked += 1
                weight2 = sum(_halo_weight2(x, y, weights) for x, y in cells)
                required2 = 2 * body_width * body_height
                slack2 = weight2 - required2
                minimum_slack2 = slack2 if minimum_slack2 is None else min(minimum_slack2, slack2)
                if slack2 < 0:
                    violations.append(
                        {
                            "body": [body_width, body_height],
                            "anchor": [anchor_x, anchor_y],
                            "weight2": weight2,
                            "required2": required2,
                        }
                    )
        counts[f"{body_width}x{body_height}"] = checked
    total_placements = sum(counts.values())
    total_weight = total_doubled // 2 if total_doubled % 2 == 0 else -1
    minimum_poles = _ceil_div(powered_area, total_weight)
    return {
        "orbit_count": len(weights),
        "doubled_weights": [
            {"a": a, "b": b, "weight2": weights[(a, b)]}
            for a, b in sorted(weights)
        ],
        "total_weight2": total_doubled,
        "total_weight": total_weight,
        "body_dimensions": [[width, height] for width, height in body_dimensions],
        "placement_counts": counts,
        "placement_count": total_placements,
        "violations": violations,
        "minimum_slack2": minimum_slack2,
        "powered_area": powered_area,
        "minimum_poles": minimum_poles,
    }


def _derive(instance: Any) -> dict[str, Any]:
    root = _mapping(instance, "problem_instance")
    if root.get("benchmark_id") != "factory_layout_optimality_benchmark_v1" or _exact_int(
        root.get("schema_version"), "schema_version"
    ) != 1:
        raise GateError("strict benchmark/schema identity changed")
    grid = _mapping(root.get("grid"), "grid")
    grid_width = _positive_int(grid.get("width"), "grid.width")
    grid_height = _positive_int(grid.get("height"), "grid.height")
    objective = _mapping(root.get("objective"), "objective")
    minimum_side = _positive_int(objective.get("minimum_side"), "objective.minimum_side")
    if (
        objective.get("kind") != "max_lex_area_min_side"
        or objective.get("body_cells_only") is not True
    ):
        raise GateError("unexpected strict objective semantics")
    if (grid_width, grid_height, minimum_side) != (70, 70, 6):
        raise GateError("strict grid or minimum-side bound changed")

    coordinate_system = _mapping(root.get("coordinate_system"), "coordinate_system")
    raw_directions = _array(coordinate_system.get("directions"), "coordinate_system.directions")
    if list(raw_directions) != ["N", "E", "S", "W"]:
        raise GateError("strict cardinal directions changed")
    directions = set(raw_directions)
    opposites = {"N": "S", "S": "N", "E": "W", "W": "E"}

    templates = _mapping(root.get("facility_templates"), "facility_templates")
    required = _array(root.get("required_instances"), "required_instances")
    groups_raw = root.get("operation_groups")
    groups_seq = _array(groups_raw, "operation_groups")
    groups: dict[str, Mapping[str, Any]] = {}
    for index, raw_group in enumerate(groups_seq):
        group = _mapping(raw_group, f"operation_groups[{index}]")
        group_id = group.get("id")
        if type(group_id) is not str or not group_id or group_id in groups:
            raise GateError("operation group ids must be unique non-empty strings")
        groups[group_id] = group

    template_counts: Counter[str] = Counter()
    ids: set[str] = set()
    required_area = 0
    powered_area = 0
    powered_instances: list[Mapping[str, Any]] = []
    manufacturing_instances = 0
    manufacturing_inputs = 0
    manufacturing_outputs = 0
    physical_port_specs = 0
    group_instance_ids: dict[str, list[str]] = {group_id: [] for group_id in groups}
    for index, raw_instance in enumerate(required):
        item = _mapping(raw_instance, f"required_instances[{index}]")
        instance_id = item.get("id")
        template_name = item.get("template")
        if type(instance_id) is not str or not instance_id or instance_id in ids:
            raise GateError("required instance ids must be unique non-empty strings")
        if type(template_name) is not str or template_name not in templates:
            raise GateError(f"required instance {instance_id} has an unknown template")
        ids.add(instance_id)
        template_counts[template_name] += 1
        area = _mode_area(templates, template_name)
        required_area += area
        template = _mapping(templates[template_name], f"template {template_name}")
        physical_counts = {
            len(_array(_mapping(mode, f"{template_name}.mode").get("ports"), f"{template_name}.ports"))
            for mode in _array(template.get("modes"), f"{template_name}.modes")
        }
        if len(physical_counts) != 1:
            raise GateError(f"{template_name} modes have inconsistent physical port counts")
        physical_port_specs += next(iter(physical_counts))
        if template.get("requires_power") is True:
            powered_instances.append(item)
            powered_area += area
        if template_name.startswith("manufacturing_"):
            manufacturing_instances += 1
            operation_id = item.get("operation")
            if type(operation_id) is not str or operation_id not in groups:
                raise GateError(f"manufacturing instance {instance_id} has unknown operation")
            group = groups[operation_id]
            if group.get("template") != template_name:
                raise GateError(f"manufacturing instance {instance_id} template/group mismatch")
            group_instance_ids[operation_id].append(instance_id)
            needs = _mapping(group.get("port_needs"), f"operation {operation_id}.port_needs")
            manufacturing_inputs += _needs_count(
                needs.get("inputs"), f"operation {operation_id}.inputs"
            )
            manufacturing_outputs += _needs_count(
                needs.get("outputs"), f"operation {operation_id}.outputs"
            )

    for group_id, group in groups.items():
        expected_ids = _array(group.get("instance_ids"), f"operation {group_id}.instance_ids")
        if list(expected_ids) != group_instance_ids[group_id]:
            raise GateError(f"operation {group_id} instance ordering/membership changed")
        if _exact_int(group.get("count"), f"operation {group_id}.count") != len(expected_ids):
            raise GateError(f"operation {group_id} count disagrees with instance ids")

    manufacturing_dimensions: set[tuple[int, int]] = set()
    manufacturing_spans: dict[str, int] = {}
    input_capacities: dict[str, int] = {}
    output_capacities: dict[str, int] = {}
    powered_template_names = {str(item["template"]) for item in powered_instances}
    for template_name, raw_template in templates.items():
        template = _mapping(raw_template, f"template {template_name}")
        input_counts: set[int] = set()
        output_counts: set[int] = set()
        side_spans: set[int] = set()
        for mode_index, raw_mode in enumerate(
            _array(template.get("modes"), f"{template_name}.modes")
        ):
            mode = _mapping(raw_mode, f"{template_name}.modes[{mode_index}]")
            field = f"{template_name}.modes[{mode_index}]"
            ports, body_width, body_height = _validated_mode_ports(
                mode, directions, field
            )
            input_ports = [port for port in ports if port.get("kind") == "input"]
            output_ports = [port for port in ports if port.get("kind") == "output"]
            input_counts.add(len(input_ports))
            output_counts.add(len(output_ports))
            if template_name.startswith("manufacturing_"):
                if template_name in powered_template_names:
                    manufacturing_dimensions.add((body_width, body_height))
                input_directions = {port.get("direction") for port in input_ports}
                output_directions = {port.get("direction") for port in output_ports}
                if (
                    len(input_directions) != 1
                    or len(output_directions) != 1
                    or opposites[next(iter(input_directions))] != next(iter(output_directions))
                ):
                    raise GateError(
                        f"manufacturing mode {template_name}/{mode.get('id')} "
                        "is not opposite-sided"
                    )
                output_direction = next(iter(output_directions))
                side_spans.add(
                    body_width if output_direction in {"N", "S"} else body_height
                )
        if len(input_counts) != 1 or len(output_counts) != 1:
            raise GateError(f"{template_name} modes disagree on kind-specific port counts")
        input_capacities[template_name] = next(iter(input_counts))
        output_capacities[template_name] = next(iter(output_counts))
        if template_name.startswith("manufacturing_"):
            if len(side_spans) != 1:
                raise GateError(
                    f"{template_name} modes disagree on the port-bearing side span"
                )
            manufacturing_spans[template_name] = next(iter(side_spans))

    class_table: Counter[tuple[int, int]] = Counter()
    for item in powered_instances:
        template_name = str(item["template"])
        operation = groups[str(item["operation"])]
        needs = _mapping(operation.get("port_needs"), "operation.port_needs")
        inputs_needed = _needs_count(needs.get("inputs"), "operation.inputs")
        outputs_needed = _needs_count(needs.get("outputs"), "operation.outputs")
        if inputs_needed > input_capacities[template_name]:
            raise GateError(f"operation {item['operation']} exceeds physical input capacity")
        if outputs_needed > output_capacities[template_name]:
            raise GateError(f"operation {item['operation']} exceeds physical output capacity")
        active_on_side = max(
            inputs_needed,
            outputs_needed,
        )
        class_table[(manufacturing_spans[template_name], active_on_side)] += 1
    boundary_instances = template_counts["boundary_storage_port"]
    boundary_template = _mapping(
        templates.get("boundary_storage_port"), "boundary_storage_port"
    )
    if boundary_template.get("placement_rule") != "matching_map_boundary":
        raise GateError("boundary storage placement rule changed")
    boundary_modes = _array(
        boundary_template.get("modes"),
        "boundary_storage_port.modes",
    )
    boundary_spans: set[int] = set()
    for mode_index, raw_mode in enumerate(boundary_modes):
        field = f"boundary_storage_port.modes[{mode_index}]"
        mode = _mapping(raw_mode, field)
        body = _mapping(mode.get("body"), "boundary_storage_port.body")
        ports = [
            _mapping(port, f"{field}.port")
            for port in _array(mode.get("ports"), f"{field}.ports")
        ]
        outputs = [port for port in ports if port.get("kind") == "output"]
        inputs = [port for port in ports if port.get("kind") == "input"]
        if len(outputs) != 1 or inputs:
            raise GateError("boundary storage must have exactly one output and no input")
        port = outputs[0]
        boundary_spans.add(
            _positive_int(body.get("width"), "boundary.width")
            if port.get("direction") in {"N", "S"}
            else _positive_int(body.get("height"), "boundary.height")
        )
    if boundary_spans != {3}:
        raise GateError("boundary storage port span changed")
    class_table[(next(iter(boundary_spans)), 1)] += boundary_instances

    excess = sum(
        multiplicity * max(0, 2 * active - span)
        for (span, active), multiplicity in class_table.items()
    )
    maximum_endpoint_extra = max(
        active - max(0, 2 * active - span) for span, active in class_table
    )
    directed_endpoints = 4 * 2
    endpoint_correction = directed_endpoints * maximum_endpoint_extra
    membrane_odd_constant = excess + endpoint_correction
    membrane_floor_constant = membrane_odd_constant // 2

    core_count = template_counts["protocol_core"]
    core_template = _mapping(templates.get("protocol_core"), "protocol_core")
    core_side_caps: set[int] = set()
    for raw_mode in _array(core_template.get("modes"), "protocol_core.modes"):
        mode = _mapping(raw_mode, "protocol_core.mode")
        direction_counts: Counter[str] = Counter(
            str(port.get("direction"))
            for port in (_mapping(value, "protocol_core.port") for value in _array(mode.get("ports"), "protocol_core.ports"))
            if port.get("kind") == "output"
        )
        if len(direction_counts) != 2:
            raise GateError("protocol core outputs are not split over exactly two sides")
        core_directions = tuple(direction_counts)
        if (
            opposites[core_directions[0]] != core_directions[1]
            or set(direction_counts.values()) != {3}
        ):
            raise GateError("protocol core outputs are not the strict opposite 3+3 split")
        core_side_caps.add(max(direction_counts.values()))
    if len(core_side_caps) != 1 or core_count != 1:
        raise GateError("protocol core side-cap premise changed")
    core_side_cap = next(iter(core_side_caps))

    generic = _mapping(root.get("generic_requirements"), "generic_requirements")
    raw_outputs = _mapping(generic.get("raw_outputs"), "generic_requirements.raw_outputs")
    final_inputs = _mapping(generic.get("final_inputs"), "generic_requirements.final_inputs")
    generic_raw_terminals = sum(_positive_int(value, f"raw_outputs.{key}") for key, value in raw_outputs.items())
    generic_final_terminals = sum(_positive_int(value, f"final_inputs.{key}") for key, value in final_inputs.items())
    active_outputs = manufacturing_outputs + generic_raw_terminals
    active_inputs = manufacturing_inputs + generic_final_terminals
    total_active_terminals = active_outputs + active_inputs
    interior_addition = core_side_cap + generic_final_terminals
    inside_constant = membrane_floor_constant + interior_addition
    terminal_numerator_constant = total_active_terminals - inside_constant

    power = _mapping(root.get("power"), "power")
    coverage = _mapping(power.get("coverage_from_pole_anchor"), "power.coverage")
    coverage_tuple = (
        _exact_int(coverage.get("x_min_offset"), "coverage.x_min_offset"),
        _exact_int(coverage.get("x_max_offset"), "coverage.x_max_offset"),
        _exact_int(coverage.get("y_min_offset"), "coverage.y_min_offset"),
        _exact_int(coverage.get("y_max_offset"), "coverage.y_max_offset"),
    )
    if power.get("required_rule") != "at_least_one_body_cell_covered":
        raise GateError("power coverage semantics changed")
    pole_template_name = power.get("pole_template")
    if type(pole_template_name) is not str:
        raise GateError("power pole template name is invalid")
    pole_modes = _array(_mapping(templates.get(pole_template_name), "power pole template").get("modes"), "power pole modes")
    pole_body = _mapping(_mapping(pole_modes[0], "power pole mode").get("body"), "power pole body")
    pole_dimensions = (
        _positive_int(pole_body.get("width"), "power pole width"),
        _positive_int(pole_body.get("height"), "power pole height"),
    )
    pole_area = _mode_area(templates, pole_template_name)
    halo = _derive_halo(
        coverage=coverage_tuple,
        body_dimensions=sorted(manufacturing_dimensions),
        powered_area=powered_area,
        pole_body_dimensions=pole_dimensions,
    )
    free_cell_cap = grid_width * grid_height - required_area - halo["minimum_poles"] * pole_area

    dimensions: list[tuple[int, int]] = []
    satisfying: list[tuple[int, int]] = []
    minimum_lhs: int | None = None
    minimizers: list[tuple[int, int]] = []
    area_ties: list[tuple[int, int]] = []
    for width in range(minimum_side, grid_width + 1):
        for height in range(minimum_side, grid_height + 1):
            area = width * height
            if area == TARGET_AREA:
                area_ties.append((width, height))
            if area > TARGET_AREA or (area == TARGET_AREA and min(width, height) > TARGET_MIN_SIDE):
                dimensions.append((width, height))
                lhs = area + _ceil_div(terminal_numerator_constant - width - height, 4)
                if lhs <= free_cell_cap:
                    satisfying.append((width, height))
                if minimum_lhs is None or lhs < minimum_lhs:
                    minimum_lhs = lhs
                    minimizers = [(width, height)]
                elif lhs == minimum_lhs:
                    minimizers.append((width, height))

    strict_sentinels = {
        "required_instances": len(required),
        "manufacturing_instances": manufacturing_instances,
        "required_body_area": required_area,
        "powered_manufacturing_area": powered_area,
        "manufacturing_input_terminals": manufacturing_inputs,
        "manufacturing_output_terminals": manufacturing_outputs,
        "generic_raw_output_terminals": generic_raw_terminals,
        "generic_final_input_terminals": generic_final_terminals,
        "active_input_terminals": active_inputs,
        "active_output_terminals": active_outputs,
        "total_active_terminals": total_active_terminals,
        "physical_port_specs": physical_port_specs,
        "operation_groups": len(groups),
        "commodities": len(_array(root.get("commodities"), "commodities")),
        "boundary_instances": boundary_instances,
        "protocol_core_instances": core_count,
        "pole_body_area": pole_area,
    }
    expected_sentinels = {
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
        "pole_body_area": 4,
    }
    declared_sentinels = _mapping(root.get("sentinels"), "sentinels")
    declared_expected = {
        "required_instance_count": 266,
        "manufacturing_instance_count": 219,
        "required_body_area": 3544,
        "manufacturing_input_terminals": 310,
        "manufacturing_output_terminals": 264,
        "generic_raw_output_terminals": 52,
        "generic_final_input_terminals": 2,
        "total_active_terminals": 628,
        "operation_group_count": 17,
        "commodity_count": 19,
    }
    if strict_sentinels != expected_sentinels or dict(declared_sentinels) != declared_expected:
        raise GateError("strict quantitative sentinels differ from the B0 baseline")
    if class_table != EXPECTED_CLASS_TABLE:
        raise GateError("membrane class table differs from the R3 certificate")
    if (
        excess,
        directed_endpoints,
        maximum_endpoint_extra,
        endpoint_correction,
        membrane_odd_constant,
        membrane_floor_constant,
        core_side_cap,
        interior_addition,
        inside_constant,
        terminal_numerator_constant,
    ) != (63, 8, 3, 24, 87, 43, 3, 5, 48, 580):
        raise GateError("membrane arithmetic differs from the R3 certificate")
    if (
        halo["orbit_count"] != 14
        or halo["total_weight2"] != 792
        or halo["total_weight"] != 396
        or halo["placement_counts"] != {"3x3": 180, "4x6": 220, "5x5": 220, "6x4": 220}
        or halo["placement_count"] != 840
        or halo["violations"]
        or halo["minimum_poles"] != 9
    ):
        raise GateError("power halo certificate differs from the R3 baseline")
    if free_cell_cap != 1320:
        raise GateError("free-cell cap is not 1320")
    if len(dimensions) != EXPECTED_VARIABLES or satisfying:
        raise GateError("lex-better oriented dimension band differs from B0")
    if minimum_lhs != 1322 or minimizers != [(19, 63), (63, 19)]:
        raise GateError("lex-better minimum LHS differs from B0")
    if area_ties != [(17, 70), (34, 35), (35, 34), (70, 17)]:
        raise GateError("area-1190 oriented tie set differs from B0")

    return {
        "grid_width": grid_width,
        "grid_height": grid_height,
        "minimum_side": minimum_side,
        "strict_sentinels": strict_sentinels,
        "class_table": class_table,
        "excess": excess,
        "directed_endpoints": directed_endpoints,
        "maximum_endpoint_extra": maximum_endpoint_extra,
        "endpoint_correction": endpoint_correction,
        "membrane_odd_constant": membrane_odd_constant,
        "membrane_floor_constant": membrane_floor_constant,
        "core_side_cap": core_side_cap,
        "generic_final_terminals": generic_final_terminals,
        "interior_addition": interior_addition,
        "inside_constant": inside_constant,
        "incidence_cap": len(opposites),
        "terminal_numerator_constant": terminal_numerator_constant,
        "halo": halo,
        "free_cell_cap": free_cell_cap,
        "dimensions": dimensions,
        "satisfying": satisfying,
        "minimum_lhs": minimum_lhs,
        "minimizers": minimizers,
        "area_ties": area_ties,
    }


def _build_expected(facts: Mapping[str, Any]) -> dict[str, Any]:
    variables: list[dict[str, Any]] = []
    constraints: Counter[ConstraintKey] = Counter()
    selector_ids: list[int] = []
    for width, height in facts["dimensions"]:
        variable_id = len(variables) + 1
        area = width * height
        lhs = area + _ceil_div(facts["terminal_numerator_constant"] - width - height, 4)
        coefficient = facts["free_cell_cap"] - lhs
        selector_ids.append(variable_id)
        variables.append(
            {
                "id": variable_id,
                "name": f"dimension__w_{width:02d}__h_{height:02d}",
                "kind": "oriented_dimension_selector",
                "width": width,
                "height": height,
                "area": area,
                "minimum_side": min(width, height),
                "lhs": lhs,
                "coefficient": coefficient,
            }
        )
        constraints[_constraint_key(((variable_id, coefficient),), ">=", 0)] += 1
    constraints[_constraint_key(((variable_id, 1) for variable_id in selector_ids), "=", 1)] += 1
    return {"variables": variables, "constraints": constraints, "selector_ids": selector_ids}


def _constraint_key(terms: Iterable[tuple[int, int]], relation: str, rhs: int) -> ConstraintKey:
    if relation not in {"=", ">="}:
        raise GateError(f"unsupported relation: {relation}")
    combined: Counter[int] = Counter()
    for variable, coefficient in terms:
        variable = _positive_int(variable, "constraint variable")
        coefficient = _exact_int(coefficient, "constraint coefficient")
        combined[variable] += coefficient
    canonical = tuple(sorted((variable, coefficient) for variable, coefficient in combined.items() if coefficient))
    if not canonical:
        raise GateError("constant-only PB constraint")
    return relation, _exact_int(rhs, "constraint rhs"), canonical


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
            raise GateError(f"malformed OPB term at line {line_number}")
        coefficient = int(term_match.group(1))
        variable = int(term_match.group(2))
        if coefficient == 0 or variable in seen:
            raise GateError(f"zero or duplicate OPB term at line {line_number}")
        seen.add(variable)
        terms.append((variable, coefficient))
        position = term_match.end()
    return _constraint_key(terms, relation, int(raw_rhs))


def _parse_opb(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"OPB is missing: {path}")
    raw = path.read_bytes()
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise GateError("OPB is not ASCII") from exc
    header: dict[str, int] | None = None
    comments: list[str] = []
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
                    raise GateError("OPB contains multiple competition headers")
                values = [int(value) for value in header_match.groups()]
                header = dict(zip(("variables", "constraints", "equal", "intsize"), values, strict=True))
            else:
                comments.append(line)
            continue
        key = _parse_constraint(line, line_number)
        constraints[key] += 1
        equality_count += key[0] == "="
        maximum_variable = max(maximum_variable, *(variable for variable, _ in key[2]))
    if header is None:
        raise GateError("OPB competition header is missing")
    return {
        "header": header,
        "comments": comments,
        "constraints": constraints,
        "constraint_count": sum(constraints.values()),
        "equal_count": equality_count,
        "maximum_variable": maximum_variable,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _multiset_hash(value: Counter[ConstraintKey]) -> str:
    digest = hashlib.sha256(b"r3-upper-bound-pb-constraint-multiset-v1\0")
    for (relation, rhs, terms), multiplicity in sorted(value.items()):
        payload = [
            relation,
            rhs,
            [[variable, coefficient] for variable, coefficient in terms],
            multiplicity,
        ]
        digest.update(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _multiset_diff(expected: Counter[ConstraintKey], actual: Counter[ConstraintKey]) -> dict[str, Any]:
    missing = expected - actual
    unexpected = actual - expected

    def examples(counter: Counter[ConstraintKey]) -> list[dict[str, Any]]:
        return [
            {
                "relation": key[0],
                "rhs": key[1],
                "terms": [[variable, coefficient] for variable, coefficient in key[2]],
                "multiplicity": count,
            }
            for key, count in sorted(counter.items())[:10]
        ]

    return {
        "missing_total": sum(missing.values()),
        "unexpected_total": sum(unexpected.values()),
        "missing_examples": examples(missing),
        "unexpected_examples": examples(unexpected),
    }


def _class_rows(class_table: Mapping[tuple[int, int], int]) -> list[dict[str, int]]:
    return [
        {"side_span": span, "active_side_cap": active, "multiplicity": class_table[(span, active)]}
        for span, active in sorted(class_table)
    ]


def _metadata_facts(facts: Mapping[str, Any]) -> dict[str, Any]:
    halo = facts["halo"]
    return {
        "grid": {
            "width": facts["grid_width"],
            "height": facts["grid_height"],
            "area": facts["grid_width"] * facts["grid_height"],
        },
        "objective": {
            "kind": "max_lex_area_min_side",
            "minimum_side": facts["minimum_side"],
            "target_area": TARGET_AREA,
            "target_min_side": TARGET_MIN_SIDE,
            "orientation": "ordered_width_height",
        },
        "strict_sentinels": facts["strict_sentinels"],
        "membrane": {
            "class_table": _class_rows(facts["class_table"]),
            "full_contact_excess": facts["excess"],
            "directed_endpoints": facts["directed_endpoints"],
            "maximum_endpoint_extra": facts["maximum_endpoint_extra"],
            "endpoint_correction": facts["endpoint_correction"],
            "twice_k_minus_l_cap": facts["membrane_odd_constant"],
            "manufacturing_boundary_additive_cap": facts["membrane_floor_constant"],
            "protocol_core_side_output_cap": facts["core_side_cap"],
            "generic_final_input_terminals": facts["generic_final_terminals"],
            "additional_inside_terminals": facts["interior_addition"],
            "inside_terminal_additive_cap": facts["inside_constant"],
            "outside_access_incidence_cap": facts["incidence_cap"],
            "outside_terminal_numerator_constant": facts["terminal_numerator_constant"],
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
            "value": facts["free_cell_cap"],
            "identity": "4900 - 3544 - 9 * 4 = 1320",
        },
        "lex_better_band": {
            "width_range": [facts["minimum_side"], facts["grid_width"]],
            "height_range": [facts["minimum_side"], facts["grid_height"]],
            "oriented": True,
            "predicate": "area > 1190 or (area == 1190 and min(width,height) > 34)",
            "dimension_count": len(facts["dimensions"]),
            "area_1190_oriented_pairs": [list(pair) for pair in facts["area_ties"]],
            "satisfying_dimension_count": len(facts["satisfying"]),
            "minimum_lhs": facts["minimum_lhs"],
            "minimum_lhs_dimensions": [list(pair) for pair in facts["minimizers"]],
        },
        "necessary_inequality": {
            "display": "wh + ceil((580-w-h)/4) <= 1320",
            "terminal_numerator_constant": facts["terminal_numerator_constant"],
            "divisor": facts["incidence_cap"],
            "rhs": facts["free_cell_cap"],
        },
    }


def _counts(facts: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, int]:
    return {
        "oriented_dimensions": len(facts["dimensions"]),
        "selector_variables": len(expected["variables"]),
        "variables": len(expected["variables"]),
        "equality_constraints": 1,
        "dimension_implication_constraints": len(facts["dimensions"]),
        "constraints": sum(expected["constraints"].values()),
        "satisfying_dimensions": len(facts["satisfying"]),
    }


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


def _band_for_bounds(minimum_side: int, maximum_side: int) -> list[tuple[int, int]]:
    return [
        (width, height)
        for width in range(minimum_side, maximum_side + 1)
        for height in range(minimum_side, maximum_side + 1)
        if width * height > TARGET_AREA
        or (width * height == TARGET_AREA and min(width, height) > TARGET_MIN_SIDE)
    ]


def _semantic_canaries(
    facts: Mapping[str, Any],
    expected_constraints: Counter[ConstraintKey],
    actual_constraints: Counter[ConstraintKey],
    *,
    opb_hash_matches_metadata: bool,
) -> dict[str, dict[str, Any]]:
    full_band = _band_for_bounds(6, 70)
    truncated_band = _band_for_bounds(6, 69)
    factor_pairs = [
        (width, height)
        for width in range(6, 71)
        for height in range(6, 71)
        if width * height == TARGET_AREA
    ]
    inclusive_tie_mutation = [
        pair for pair in factor_pairs if min(pair) >= TARGET_MIN_SIDE
    ]
    ceil_cases: dict[str, dict[str, int]] = {}
    ceil_pass = True
    for numerator in (-9, -5, -4, -1, 0, 1, 2, 3, 4, 5, 440, 511, 568):
        quotient, remainder = divmod(numerator, 4)
        independent = quotient + int(remainder != 0)
        actual = _ceil_div(numerator, 4)
        ceil_cases[str(numerator)] = {"actual": actual, "divmod_reconstruction": independent}
        ceil_pass &= actual == independent
    class_rows = _class_rows(facts["class_table"])
    mutated_classes = Counter(facts["class_table"])
    mutated_classes[(3, 1)] += 1
    endpoint_mutation = (facts["directed_endpoints"] - 1) * facts["maximum_endpoint_extra"]
    halo = facts["halo"]
    mutated_weights = dict(HALO_DOUBLED_WEIGHTS)
    mutated_weights[(3, 3)] -= 1
    mutated_halo = _derive_halo(
        coverage=(-5, 6, -5, 6),
        body_dimensions=[tuple(pair) for pair in halo["body_dimensions"]],
        powered_area=halo["powered_area"],
        pole_body_dimensions=(2, 2),
        weights=mutated_weights,
    )
    expected_multiset_hash = _multiset_hash(expected_constraints)
    actual_multiset_hash = _multiset_hash(actual_constraints)
    return {
        "dimension_boundaries_6_through_70_inclusive": {
            "pass": (
                full_band == facts["dimensions"]
                and len(full_band) == EXPECTED_VARIABLES
                and len(truncated_band) != EXPECTED_VARIABLES
                and any(70 in pair for pair in full_band)
            ),
            "full_count": len(full_band),
            "excluding_70_count": len(truncated_band),
        },
        "area_1190_tie_break_strict": {
            "pass": (
                factor_pairs == facts["area_ties"]
                and factor_pairs == [(17, 70), (34, 35), (35, 34), (70, 17)]
                and inclusive_tie_mutation == [(34, 35), (35, 34)]
                and not any(pair in facts["dimensions"] for pair in factor_pairs)
            ),
            "factor_pairs": [list(pair) for pair in factor_pairs],
            "would_enter_with_inclusive_tie_mutation": [list(pair) for pair in inclusive_tie_mutation],
        },
        "ceil_division_exact_integer": {
            "pass": ceil_pass,
            "cases": ceil_cases,
        },
        "membrane_class_table_resealed": {
            "pass": facts["class_table"] == EXPECTED_CLASS_TABLE and mutated_classes != EXPECTED_CLASS_TABLE,
            "classes": class_rows,
            "multiplicity_total": sum(facts["class_table"].values()),
        },
        "endpoint_correction_resealed": {
            "pass": (
                facts["directed_endpoints"] == 8
                and facts["maximum_endpoint_extra"] == 3
                and facts["endpoint_correction"] == 24
                and endpoint_mutation != facts["endpoint_correction"]
            ),
            "directed_endpoints": facts["directed_endpoints"],
            "maximum_extra": facts["maximum_endpoint_extra"],
            "correction": facts["endpoint_correction"],
        },
        "outside_access_incidence_cap_four": {
            "pass": facts["incidence_cap"] == 4 and facts["incidence_cap"] != 5,
            "orthogonal_directions": ["E", "N", "S", "W"],
            "cap": facts["incidence_cap"],
        },
        "power_halo_resealed": {
            "pass": (
                halo["orbit_count"] == 14
                and halo["total_weight"] == 396
                and halo["placement_count"] == 840
                and not halo["violations"]
                and halo["minimum_poles"] == 9
                and mutated_halo["total_weight2"] != halo["total_weight2"]
                and bool(mutated_halo["violations"])
                and mutated_halo["minimum_slack2"] < 0
            ),
            "orbit_count": halo["orbit_count"],
            "total_weight": halo["total_weight"],
            "placement_count": halo["placement_count"],
            "violation_count": len(halo["violations"]),
            "minimum_poles": halo["minimum_poles"],
            "mutated_violation_count": len(mutated_halo["violations"]),
            "mutated_minimum_slack2": mutated_halo["minimum_slack2"],
        },
        "opb_constraint_multiset_resealed": {
            "pass": (
                expected_constraints == actual_constraints
                and expected_multiset_hash == actual_multiset_hash
                and opb_hash_matches_metadata
            ),
            "expected_sha256": expected_multiset_hash,
            "actual_sha256": actual_multiset_hash,
            "opb_hash_matches_metadata": opb_hash_matches_metadata,
        },
    }


def verify(
    *,
    project_root: Path,
    opb_path: Path,
    meta_path: Path,
    var_map_path: Path,
    estimate_path: Path,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    meta_raw = meta_path.read_bytes()
    var_map_raw = var_map_path.read_bytes()
    estimate_raw = estimate_path.read_bytes()
    meta = _mapping(_strict_json(meta_raw, "metadata"), "metadata")
    var_map = _mapping(_strict_json(var_map_raw, "variable map"), "variable map")
    estimate = _mapping(_strict_json(estimate_raw, "estimate"), "estimate")
    if (
        meta.get("schema_version") != META_SCHEMA
        or meta.get("model_schema_version") != MODEL_SCHEMA
    ):
        raise GateError("metadata schema identity is invalid")
    if (
        var_map.get("schema_version") != VAR_MAP_SCHEMA
        or var_map.get("model_schema_version") != MODEL_SCHEMA
    ):
        raise GateError("variable-map schema identity is invalid")
    if (
        estimate.get("schema_version") != ESTIMATE_SCHEMA
        or estimate.get("model_schema_version") != MODEL_SCHEMA
    ):
        raise GateError("estimate schema identity is invalid")
    if any(payload.get("semantics") != SEMANTICS for payload in (meta, var_map, estimate)):
        raise GateError("translation semantics identity is invalid")

    metadata_keys = {
        "argv",
        "claim_scope",
        "counts",
        "derived_facts",
        "estimate",
        "evidence",
        "git_snapshot",
        "harness",
        "harness_source",
        "inputs",
        "model_schema_version",
        "outputs",
        "project_root",
        "proof_status",
        "schema_version",
        "semantics",
        "variable_map_schema_version",
    }
    estimate_keys = {
        "argv",
        "counts",
        "derived_facts",
        "evidence",
        "git_snapshot",
        "harness",
        "harness_source",
        "inputs",
        "metadata_schema_version",
        "model_schema_version",
        "project_root",
        "projected_outputs",
        "proof_size_planning",
        "schema_version",
        "semantics",
        "variable_map_schema_version",
    }

    input_raw, input_records = _bound_records(
        meta, "inputs", INPUT_PATHS, INPUT_SHA256, project_root
    )
    _estimate_input_raw, estimate_input_records = _bound_records(
        estimate, "inputs", INPUT_PATHS, INPUT_SHA256, project_root
    )
    _evidence_raw, evidence_records = _bound_records(
        meta, "evidence", EVIDENCE_PATHS, EVIDENCE_SHA256, project_root
    )
    _estimate_evidence_raw, estimate_evidence_records = _bound_records(
        estimate, "evidence", EVIDENCE_PATHS, EVIDENCE_SHA256, project_root
    )
    manifest_pass = _verify_sha256_manifest(input_raw["sha256s"], input_raw)
    instance = _strict_json(input_raw["problem_instance"], "problem_instance")
    _strict_json(input_raw["problem_instance_schema"], "problem_instance_schema")
    facts = _derive(instance)
    expected = _build_expected(facts)
    counts = _counts(facts, expected)
    derived_facts = _metadata_facts(facts)

    encoder_source = _validate_record(
        meta.get("harness_source"), ENCODER_SOURCE, project_root, "metadata.harness_source"
    )
    estimate_encoder_source = _validate_record(
        estimate.get("harness_source"),
        ENCODER_SOURCE,
        project_root,
        "estimate.harness_source",
    )
    encoder_snapshot = _validate_git_snapshot(meta.get("git_snapshot"), "metadata.git_snapshot")
    estimate_snapshot = _validate_git_snapshot(
        estimate.get("git_snapshot"), "estimate.git_snapshot"
    )
    current_snapshot = _git_snapshot(project_root)
    if current_snapshot["head"] != EXPECTED_GIT_HEAD:
        raise GateError("current Git HEAD differs from the pinned B0 baseline")
    if meta.get("harness") != ENCODER_NAME or estimate.get("harness") != ENCODER_NAME:
        raise GateError("encoder harness identity is invalid")

    outputs = _mapping(meta.get("outputs"), "metadata.outputs")
    if set(outputs) != {"opb", "var_map", "metadata"}:
        raise GateError("metadata.outputs is not closed")
    opb_record = _validate_record(
        outputs.get("opb"), opb_path, project_root, "metadata.outputs.opb"
    )
    var_map_record = _validate_record(
        outputs.get("var_map"), var_map_path, project_root, "metadata.outputs.var_map"
    )
    metadata_output = _mapping(outputs.get("metadata"), "metadata.outputs.metadata")
    if set(metadata_output) != {"path"}:
        raise GateError("metadata.outputs.metadata is not a closed path record")
    metadata_output_path = metadata_output.get("path")
    if (
        type(metadata_output_path) is not str
        or Path(metadata_output_path).resolve() != meta_path.resolve()
    ):
        raise GateError("metadata.outputs.metadata path mismatch")
    _validate_record(meta.get("estimate"), estimate_path, project_root, "metadata.estimate")

    variables = var_map.get("variables")
    if not isinstance(variables, list) or not all(isinstance(item, Mapping) for item in variables):
        raise GateError("variable map variables must be an object array")
    variable_ids = [item.get("id") for item in variables]
    variable_names = [item.get("name") for item in variables]
    dense = (
        all(type(variable_id) is int for variable_id in variable_ids)
        and variable_ids == list(range(1, len(variables) + 1))
        and all(type(name) is str and name for name in variable_names)
        and len(variable_names) == len(set(variable_names))
        and type(var_map.get("variable_count")) is int
        and var_map.get("variable_count") == len(variables)
    )
    var_map_exact = (
        set(var_map)
        == {
            "schema_version",
            "semantics",
            "model_schema_version",
            "variable_count",
            "variables",
        }
        and _type_exact_equal(variables, expected["variables"])
    )

    parsed = _parse_opb(opb_path)
    header_exact = (
        parsed["header"]
        == {
            "variables": EXPECTED_VARIABLES,
            "constraints": EXPECTED_CONSTRAINTS,
            "equal": EXPECTED_EQUALITIES,
            "intsize": 64,
        }
        and parsed["constraint_count"] == EXPECTED_CONSTRAINTS
        and parsed["equal_count"] == EXPECTED_EQUALITIES
        and parsed["maximum_variable"] == EXPECTED_VARIABLES
    )
    constraints_exact = parsed["constraints"] == expected["constraints"]

    metadata_argv = meta.get("argv")
    estimate_argv = estimate.get("argv")
    planning = _mapping(estimate.get("proof_size_planning"), "proof_size_planning")
    projected_outputs = _mapping(estimate.get("projected_outputs"), "projected_outputs")
    projected_opb_bytes = _exact_int(projected_outputs.get("opb_bytes"), "projected opb bytes")
    expected_planning_bound = max(MINIMUM_PLANNING_BYTES, 1024 * projected_opb_bytes)
    expected_planning = {
        "bound_bytes": expected_planning_bound,
        "user_limit_bytes": PROOF_LIMIT_BYTES,
        "decision": "GO",
        "basis": {
            "method": "max_512_mib_or_1024_times_projected_opb_bytes",
            "floor_bytes": MINIMUM_PLANNING_BYTES,
            "opb_multiplier": 1024,
            "projected_opb_bytes": projected_opb_bytes,
        },
    }
    planning_semantics_pass = (
        expected_planning_bound <= PROOF_LIMIT_BYTES
        and _type_exact_equal(dict(planning), expected_planning)
    )
    metadata_match = (
        set(meta) == metadata_keys
        and isinstance(metadata_argv, list)
        and bool(metadata_argv)
        and all(type(value) is str for value in metadata_argv)
        and _type_exact_equal(meta.get("derived_facts"), derived_facts)
        and _type_exact_equal(meta.get("counts"), counts)
        and meta.get("proof_status") == "translation_only_no_unsat_or_proof_claim"
        and meta.get("variable_map_schema_version") == VAR_MAP_SCHEMA
        and meta.get("project_root") == str(project_root)
        and _type_exact_equal(meta.get("claim_scope"), _claim_scope())
    )
    estimate_match = (
        set(estimate) == estimate_keys
        and isinstance(estimate_argv, list)
        and bool(estimate_argv)
        and all(type(value) is str for value in estimate_argv)
        and _type_exact_equal(estimate.get("derived_facts"), derived_facts)
        and _type_exact_equal(estimate.get("counts"), counts)
        and estimate.get("metadata_schema_version") == META_SCHEMA
        and estimate.get("variable_map_schema_version") == VAR_MAP_SCHEMA
        and estimate.get("project_root") == str(project_root)
        and set(projected_outputs) == {"opb_bytes"}
        and projected_opb_bytes == parsed["size_bytes"]
        and planning_semantics_pass
    )

    translation_inputs = {
        "estimate": _file_record(estimate_path, project_root),
        "meta": _file_record(meta_path, project_root),
        "opb": _file_record(opb_path, project_root),
        "var_map": _file_record(var_map_path, project_root),
    }
    opb_hash_matches_metadata = (
        translation_inputs["opb"]["sha256"] == parsed["sha256"] == opb_record["sha256"]
    )
    translation_hashes_pass = (
        translation_inputs["meta"]["sha256"] == hashlib.sha256(meta_raw).hexdigest()
        and translation_inputs["var_map"]["sha256"] == hashlib.sha256(var_map_raw).hexdigest()
        and translation_inputs["estimate"]["sha256"] == hashlib.sha256(estimate_raw).hexdigest()
        and opb_hash_matches_metadata
        and translation_inputs["var_map"] == var_map_record
    )
    canaries = _semantic_canaries(
        facts,
        expected["constraints"],
        parsed["constraints"],
        opb_hash_matches_metadata=opb_hash_matches_metadata,
    )
    canaries_pass = all(record.get("pass") is True for record in canaries.values())

    corpus_errors = [
        {
            "width": width,
            "height": height,
            "lhs": width * height
            + _ceil_div(facts["terminal_numerator_constant"] - width - height, 4),
        }
        for width, height in facts["dimensions"]
        if width * height
        + _ceil_div(facts["terminal_numerator_constant"] - width - height, 4)
        <= facts["free_cell_cap"]
    ]
    strict_sentinels_pass = facts["strict_sentinels"] == {
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
        "pole_body_area": 4,
    }
    membrane_pass = (
        facts["class_table"] == EXPECTED_CLASS_TABLE
        and facts["excess"] == 63
        and facts["endpoint_correction"] == 24
        and facts["membrane_floor_constant"] == 43
        and facts["inside_constant"] == 48
        and facts["terminal_numerator_constant"] == 580
        and facts["incidence_cap"] == 4
    )
    halo = facts["halo"]
    halo_pass = (
        halo["orbit_count"] == 14
        and halo["total_weight"] == 396
        and halo["placement_count"] == 840
        and halo["placement_counts"] == {"3x3": 180, "4x6": 220, "5x5": 220, "6x4": 220}
        and not halo["violations"]
        and halo["minimum_poles"] == 9
        and facts["free_cell_cap"] == 1320
    )
    band_pass = (
        len(facts["dimensions"]) == EXPECTED_VARIABLES
        and facts["area_ties"] == [(17, 70), (34, 35), (35, 34), (70, 17)]
        and facts["minimum_lhs"] == 1322
        and facts["minimizers"] == [(19, 63), (63, 19)]
    )
    corpus_pass = (
        len(facts["dimensions"]) == EXPECTED_VARIABLES
        and corpus_errors == []
        and all(item["coefficient"] < 0 for item in expected["variables"])
    )
    checks = {
        "strict_bundle_closed_and_hashed": (
            manifest_pass and input_records == estimate_input_records
        ),
        "r3_evidence_closed_and_hashed": evidence_records == estimate_evidence_records,
        "encoder_provenance_match": (
            _type_exact_equal(encoder_source, estimate_encoder_source)
            and _type_exact_equal(encoder_snapshot, estimate_snapshot)
            and _type_exact_equal(encoder_snapshot, current_snapshot)
        ),
        "translation_inputs_closed_and_hashed": translation_hashes_pass,
        "metadata_reconstruction_match": metadata_match,
        "estimate_reconstruction_match": estimate_match,
        "variable_map_dense": dense,
        "variable_map_exact": var_map_exact,
        "opb_header_exact": header_exact,
        "constraint_multiset_exact": constraints_exact,
        "strict_sentinels_exact": strict_sentinels_pass,
        "membrane_class_table_exact": membrane_pass,
        "halo_certificate_exact": halo_pass,
        "lex_better_band_exact": band_pass,
        "arithmetic_corpus_unsat": corpus_pass,
        "semantic_canaries_pass": canaries_pass,
    }
    if set(checks) != REQUIRED_CHECKS:
        raise AssertionError("gate check map drifted from REQUIRED_CHECKS")
    constraint_diff = _multiset_diff(expected["constraints"], parsed["constraints"])
    status = "PASS" if all(checks.values()) and corpus_errors == [] else "FAIL"
    return {
        "schema_version": GATE_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "metadata_schema_version": META_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "semantics": SEMANTICS,
        "status": status,
        "checks": checks,
        "encoder_git_snapshot": encoder_snapshot,
        "encoder_source": encoder_source,
        "gate_source": _file_record(Path(__file__), project_root),
        "git_snapshot": current_snapshot,
        "strict_inputs": input_records,
        "evidence": evidence_records,
        "translation_inputs": translation_inputs,
        "derived_facts": derived_facts,
        "counts": counts,
        "semantic_canaries": canaries,
        "corpus_count": len(facts["dimensions"]),
        "corpus_errors": corpus_errors,
        "minimum_lhs": facts["minimum_lhs"],
        "minimum_lhs_dimensions": [list(pair) for pair in facts["minimizers"]],
        "constraint_multiset_sha256": {
            "expected": _multiset_hash(expected["constraints"]),
            "actual": _multiset_hash(parsed["constraints"]),
        },
        "constraint_diff": constraint_diff,
        "theorem_coverage": _claim_scope(),
        "proof_status": "translation_gate_only_no_unsat_or_proof_claim",
    }


def _exclusive_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing gate output: {path}")
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
        raise FileExistsError(f"refusing to overwrite existing gate output: {args.output}")
    try:
        report = verify(
            project_root=args.project_root.resolve(),
            opb_path=args.opb.resolve(),
            meta_path=args.meta.resolve(),
            var_map_path=args.var_map.resolve(),
            estimate_path=args.estimate.resolve(),
        )
    except Exception as exc:
        report = {
            "schema_version": GATE_SCHEMA,
            "model_schema_version": MODEL_SCHEMA,
            "metadata_schema_version": META_SCHEMA,
            "variable_map_schema_version": VAR_MAP_SCHEMA,
            "semantics": SEMANTICS,
            "status": "FAIL",
            "checks": {name: False for name in sorted(REQUIRED_CHECKS)},
            "corpus_count": 0,
            "corpus_errors": [{"type": type(exc).__name__, "message": str(exc)}],
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "proof_status": "translation_gate_failed_no_unsat_or_proof_claim",
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
