"""Independently verify the R1 ``(1326, 34)`` research PB translation.

This gate deliberately shares no implementation code with the encoder or the
older Batch-4 PB harness.  It binds the strict research bundle, reconstructs
the complete variable map and OPB constraint multiset, and exhaustively checks
all 47 boundary-pattern by 16,702 rectangle-placement assignments.
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


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SEMANTICS = "r1_strict_upper_bound_1326_34_research"
MODEL_SCHEMA = "r1_upper_bound_pb_v1"
META_SCHEMA = "r1_upper_bound_pb_metadata_v1"
VAR_MAP_SCHEMA = "r1_upper_bound_pb_var_map_v1"
ESTIMATE_SCHEMA = "r1_upper_bound_pb_estimate_v1"
GATE_SCHEMA = "r1_upper_bound_pb_translation_gate_v1"
ENCODER_NAME = "r1_upper_bound_pb_encoder_v1"
ENCODER_SOURCE = Path(__file__).with_name("r1_upper_bound_pb_encoder_v1.py")

INPUT_PATHS = {
    "problem_instance": Path(
        "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    ),
    "problem_instance_schema": Path(
        "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.schema.json"
    ),
    "problem_md": Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem.md"),
    "sha256s": Path("docs/research/cleanroom_rederivation_20260718/strict/external/SHA256SUMS"),
}
EVIDENCE_PATHS = {
    "independent_recomputation": Path(
        "docs/research/cleanroom_rederivation_20260718/verify_r1_strict_bounds.py"
    ),
    "r1_strict_judgment": Path(
        "docs/research/cleanroom_rederivation_20260718/05_r1_strict_judgment_20260720.md"
    ),
    "r1_strict_response": Path(
        "docs/research/cleanroom_rederivation_20260718/04_r1_strict_response_gpt_pro_verbatim.md"
    ),
}
REQUIRED_CHECKS = frozenset(
    {
        "strict_bundle_closed_and_hashed",
        "encoder_provenance_match",
        "translation_inputs_closed_and_hashed",
        "metadata_reconstruction_match",
        "estimate_reconstruction_match",
        "variable_map_dense",
        "variable_map_exact",
        "opb_header_exact",
        "constraint_multiset_exact",
        "boundary_patterns_exhaustive",
        "lex_better_partition_exact",
        "two_stage_theorem_coverage_exact",
        "corpus_exhaustive_unsat",
        "semantic_canaries_pass",
    }
)

HEADER_RE = re.compile(
    r"^\*\s+#variable=\s+(\d+)\s+#constraint=\s+(\d+)\s+"
    r"#equal=\s+(\d+)\s+intsize=\s+(\d+)\s*$"
)
CONSTRAINT_RE = re.compile(r"^(.*?)\s+(>=|=)\s+([+-]?\d+)\s*;\s*$")
TERM_RE = re.compile(r"\s*([+-]\d+)\s+x([1-9]\d*)")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
ConstraintKey = tuple[str, int, tuple[tuple[int, int], ...]]
Cell = tuple[int, int]


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


def _reject_constant(value: str) -> Any:
    raise GateError(f"non-finite JSON number is forbidden: {value}")


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
    if dict(record) != expected:
        raise GateError(f"{field} does not match the current pinned file")
    return expected


def _git_snapshot(project_root: Path) -> dict[str, Any]:
    head_result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    head = head_result.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise GateError(f"unexpected Git revision: {head!r}")
    diff_result = subprocess.run(
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
    )
    diff = diff_result.stdout
    status_result = subprocess.run(
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
    )
    status = status_result.stdout
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
    dirty = snapshot.get("tracked_dirty")
    digest = snapshot.get("tracked_diff_sha256")
    size = snapshot.get("tracked_diff_size_bytes")
    status_dirty = snapshot.get("status_dirty")
    status_digest = snapshot.get("status_sha256")
    status_size = snapshot.get("status_size_bytes")
    if type(head) is not str or re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise GateError(f"{field}.head is invalid")
    if type(dirty) is not bool:
        raise GateError(f"{field}.tracked_dirty must be boolean")
    if type(digest) is not str or SHA256_RE.fullmatch(digest) is None:
        raise GateError(f"{field}.tracked_diff_sha256 is invalid")
    if type(size) is not int or size < 0 or dirty is not (size > 0):
        raise GateError(f"{field} dirty/size fields disagree")
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
    project_root: Path,
) -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    records = _mapping(container.get(key), key)
    if set(records) != set(paths):
        raise GateError(f"{key} does not match the closed record set")
    raw_by_key: dict[str, bytes] = {}
    expected_records: dict[str, dict[str, Any]] = {}
    for name, relative_path in sorted(paths.items()):
        path = project_root / relative_path
        expected_records[name] = _validate_record(records[name], path, project_root, f"{key}.{name}")
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
    return all(entries.get(name) == hashlib.sha256(data).hexdigest() for name, data in required.items())


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


def _port_count(templates: Mapping[str, Any], template_name: str, kind: str) -> int:
    template = _mapping(templates.get(template_name), f"facility_templates.{template_name}")
    counts: set[int] = set()
    for raw_mode in _array(template.get("modes"), f"{template_name}.modes"):
        mode = _mapping(raw_mode, f"{template_name}.mode")
        ports = _array(mode.get("ports"), f"{template_name}.mode.ports")
        counts.add(sum(_mapping(port, "port").get("kind") == kind for port in ports))
    if len(counts) != 1:
        raise GateError(f"{template_name} modes have inconsistent {kind} counts")
    return next(iter(counts))


def _anchors(gap: int, grid_extent: int, body_extent: int, per_edge: int) -> list[int]:
    before = list(range(0, gap, body_extent))
    after = [gap + 1 + body_extent * index for index in range(per_edge - len(before))]
    result = before + after
    if len(result) != per_edge or any(anchor < 0 or anchor + body_extent > grid_extent for anchor in result):
        raise GateError(f"invalid gap-derived anchors for gap {gap}")
    return result


def _q_sources(g_left: int, g_bottom: int, facts: Mapping[str, Any]) -> list[Cell]:
    extent = facts["grid_width"]
    per_edge = facts["boundary_per_edge"]
    body_extent = facts["boundary_body_extent"]
    left = [(1, anchor + 1) for anchor in _anchors(g_left, extent, body_extent, per_edge)]
    bottom = [(anchor + 1, 1) for anchor in _anchors(g_bottom, extent, body_extent, per_edge)]
    return left + bottom


def _derive(instance: Any) -> dict[str, Any]:
    root = _mapping(instance, "problem_instance")
    grid = _mapping(root.get("grid"), "grid")
    width = _positive_int(grid.get("width"), "grid.width")
    height = _positive_int(grid.get("height"), "grid.height")
    if width != height:
        raise GateError("R1 derivation requires a square grid")
    objective = _mapping(root.get("objective"), "objective")
    min_side = _positive_int(objective.get("minimum_side"), "objective.minimum_side")
    if objective.get("kind") != "max_lex_area_min_side" or objective.get("body_cells_only") is not True:
        raise GateError("unexpected strict objective semantics")
    templates = _mapping(root.get("facility_templates"), "facility_templates")
    required = _array(root.get("required_instances"), "required_instances")
    ids: set[str] = set()
    required_area = 0
    counts: Counter[str] = Counter()
    powered_count = 0
    for index, raw_instance in enumerate(required):
        item = _mapping(raw_instance, f"required_instances[{index}]")
        instance_id = item.get("id")
        template_name = item.get("template")
        if type(instance_id) is not str or not instance_id or instance_id in ids:
            raise GateError("required instance ids must be unique non-empty strings")
        if type(template_name) is not str or template_name not in templates:
            raise GateError(f"required instance {instance_id} has an unknown template")
        ids.add(instance_id)
        counts[template_name] += 1
        required_area += _mode_area(templates, template_name)
        if _mapping(templates[template_name], f"template {template_name}").get("requires_power") is True:
            powered_count += 1
    boundary_count = counts["boundary_storage_port"]
    protocol_core_count = counts["protocol_core"]
    boundary = _mapping(templates.get("boundary_storage_port"), "boundary_storage_port")
    boundary_modes = _array(boundary.get("modes"), "boundary_storage_port.modes")
    mode_by_id = {
        _mapping(mode, "boundary mode").get("id"): _mapping(mode, "boundary mode")
        for mode in boundary_modes
    }
    if set(mode_by_id) != {"left_boundary", "bottom_boundary"}:
        raise GateError("boundary mode set is not exactly left/bottom")
    left_body = _mapping(mode_by_id["left_boundary"].get("body"), "left body")
    bottom_body = _mapping(mode_by_id["bottom_boundary"].get("body"), "bottom body")
    if dict(left_body) != {"width": 1, "height": 3} or dict(bottom_body) != {"width": 3, "height": 1}:
        raise GateError("boundary bodies are not the strict 1x3/3x1 pair")
    for mode_name, expected_direction, expected_cell in (
        ("left_boundary", "E", {"x": 0, "y": 1}),
        ("bottom_boundary", "N", {"x": 1, "y": 0}),
    ):
        ports = _array(mode_by_id[mode_name].get("ports"), f"{mode_name}.ports")
        if len(ports) != 1:
            raise GateError(f"{mode_name} must have one port")
        port = _mapping(ports[0], f"{mode_name}.port")
        if (
            port.get("kind") != "output"
            or port.get("direction") != expected_direction
            or dict(_mapping(port.get("body_cell"), "port.body_cell")) != expected_cell
        ):
            raise GateError(f"{mode_name} output geometry changed")
    boundary_extent = 3
    edge_capacity = width // boundary_extent
    if boundary_count != 2 * edge_capacity:
        raise GateError("46 boundary bodies no longer force equal edge saturation")
    gaps = list(range(0, width, boundary_extent))
    patterns = [(0, gap) for gap in gaps] + [(gap, 0) for gap in gaps if gap != 0]

    power = _mapping(root.get("power"), "power")
    offsets = _mapping(power.get("coverage_from_pole_anchor"), "power.coverage")
    cover_width = _exact_int(offsets.get("x_max_offset"), "x_max_offset") - _exact_int(
        offsets.get("x_min_offset"), "x_min_offset"
    ) + 1
    cover_height = _exact_int(offsets.get("y_max_offset"), "y_max_offset") - _exact_int(
        offsets.get("y_min_offset"), "y_min_offset"
    ) + 1
    max_cover = cover_width * cover_height
    pole_template = power.get("pole_template")
    if type(pole_template) is not str or power.get("required_rule") != "at_least_one_body_cell_covered":
        raise GateError("unexpected strict power semantics")
    pole_area = _mode_area(templates, pole_template)
    pole_lower_bound = (powered_count + max_cover - 1) // max_cover
    cap = width * height - required_area - pole_lower_bound * pole_area

    generic = _mapping(root.get("generic_requirements"), "generic_requirements")
    raw_outputs = _mapping(generic.get("raw_outputs"), "generic_requirements.raw_outputs")
    raw_demand = sum(_positive_int(value, f"raw_outputs.{key}") for key, value in raw_outputs.items())
    boundary_outputs = boundary_count * _port_count(templates, "boundary_storage_port", "output")
    core_outputs = protocol_core_count * _port_count(templates, "protocol_core", "output")
    if boundary_outputs + core_outputs != raw_demand:
        raise GateError("raw output slots no longer equal raw output demand")

    lex_dimensions: list[tuple[int, int]] = []
    elementary: list[tuple[int, int]] = []
    residual: list[tuple[int, int]] = []
    for rect_width in range(min_side, width):
        for rect_height in range(min_side, height):
            area = rect_width * rect_height
            if area > 1326 or (area == 1326 and min(rect_width, rect_height) > 34):
                lex_dimensions.append((rect_width, rect_height))
                (elementary if area > cap else residual).append((rect_width, rect_height))
    facts = {
        "grid_width": width,
        "grid_height": height,
        "minimum_side": min_side,
        "required_body_area": required_area,
        "powered_required_instances": powered_count,
        "pole_max_covered_cells": max_cover,
        "pole_coverage_width": cover_width,
        "pole_coverage_height": cover_height,
        "pole_body_area": pole_area,
        "pole_lower_bound": pole_lower_bound,
        "free_cell_cap": cap,
        "boundary_instances": boundary_count,
        "boundary_per_edge": edge_capacity,
        "boundary_body_extent": boundary_extent,
        "boundary_output_slots": boundary_outputs,
        "protocol_core_output_slots": core_outputs,
        "raw_output_demand": raw_demand,
        "patterns": patterns,
        "lex_dimensions": lex_dimensions,
        "elementary_dimensions": elementary,
        "residual_dimensions": residual,
    }
    if (width, height, min_side, required_area, powered_count, max_cover, pole_area, pole_lower_bound, cap) != (
        70,
        70,
        6,
        3544,
        219,
        144,
        4,
        2,
        1348,
    ):
        raise GateError("strict quantitative baseline does not match R1")
    if (boundary_outputs, core_outputs, raw_demand) != (46, 6, 52):
        raise GateError("strict 52=46+6 slot identity does not match R1")
    if len(patterns) != 47 or len(elementary) != 1763 or len(residual) != 22:
        raise GateError("R1 pattern or lex-better dimension partition changed")
    return facts


def _build_expected(facts: Mapping[str, Any]) -> dict[str, Any]:
    variables: list[dict[str, Any]] = []
    pattern_ids: list[int] = []
    q_sets: list[frozenset[Cell]] = []
    for pattern_index, (g_left, g_bottom) in enumerate(facts["patterns"]):
        q_set = frozenset(_q_sources(g_left, g_bottom, facts))
        variable_id = len(variables) + 1
        pattern_ids.append(variable_id)
        q_sets.append(q_set)
        variables.append(
            {
                "id": variable_id,
                "name": f"pattern__g_left_{g_left:02d}__g_bottom_{g_bottom:02d}",
                "kind": "boundary_pattern",
                "pattern_index": pattern_index,
                "g_left": g_left,
                "g_bottom": g_bottom,
                "q_size": len(q_set),
                "q_cells": [[x, y] for x, y in sorted(q_set)],
            }
        )
    placement_ids: list[int] = []
    placements: list[tuple[int, int, int, int, int]] = []
    placement_index = 0
    for dimension_index, (width, height) in enumerate(facts["residual_dimensions"]):
        for x_value in range(1, facts["grid_width"] - width + 1):
            for y_value in range(1, facts["grid_height"] - height + 1):
                variable_id = len(variables) + 1
                placement_ids.append(variable_id)
                placements.append((variable_id, width, height, x_value, y_value))
                variables.append(
                    {
                        "id": variable_id,
                        "name": (
                            f"rectangle__w_{width:02d}__h_{height:02d}"
                            f"__x_{x_value:02d}__y_{y_value:02d}"
                        ),
                        "kind": "rectangle_placement",
                        "dimension_index": dimension_index,
                        "placement_index": placement_index,
                        "width": width,
                        "height": height,
                        "x": x_value,
                        "y": y_value,
                        "area": width * height,
                    }
                )
                placement_index += 1
    constraints: Counter[ConstraintKey] = Counter()
    constraints[_constraint_key(((value, 1) for value in pattern_ids), "=", 1)] += 1
    constraints[_constraint_key(((value, 1) for value in placement_ids), "=", 1)] += 1
    for variable_id, width, height, x_value, y_value in placements:
        terms: list[tuple[int, int]] = []
        for pattern_id, q_set in zip(pattern_ids, q_sets, strict=True):
            overlap = sum(
                x_value <= qx < x_value + width and y_value <= qy < y_value + height
                for qx, qy in q_set
            )
            if overlap:
                terms.append((pattern_id, overlap))
        terms.append((variable_id, -46))
        constraints[_constraint_key(terms, ">=", width * height - facts["free_cell_cap"])] += 1
    return {
        "variables": variables,
        "constraints": constraints,
        "pattern_ids": pattern_ids,
        "q_sets": q_sets,
        "placements": placements,
    }


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
    constraints: Counter[ConstraintKey] = Counter()
    equal_count = 0
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
            continue
        key = _parse_constraint(line, line_number)
        constraints[key] += 1
        equal_count += key[0] == "="
        maximum_variable = max(maximum_variable, *(variable for variable, _ in key[2]))
    if header is None:
        raise GateError("OPB competition header is missing")
    return {
        "header": header,
        "constraints": constraints,
        "constraint_count": sum(constraints.values()),
        "equal_count": equal_count,
        "maximum_variable": maximum_variable,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _multiset_hash(value: Counter[ConstraintKey]) -> str:
    digest = hashlib.sha256(b"r1-upper-bound-pb-constraint-multiset-v1\0")
    for (relation, rhs, terms), multiplicity in sorted(value.items()):
        payload = [relation, rhs, [[variable, coefficient] for variable, coefficient in terms], multiplicity]
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


def _metadata_facts(facts: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "grid": {
            "width": facts["grid_width"],
            "height": facts["grid_height"],
            "area": facts["grid_width"] * facts["grid_height"],
        },
        "objective": {
            "kind": "max_lex_area_min_side",
            "minimum_side": facts["minimum_side"],
            "target_area": 1326,
            "target_min_side": 34,
        },
        "required_body_area": facts["required_body_area"],
        "powered_manufacturing_instances": facts["powered_required_instances"],
        "power": {
            "coverage_width": facts["pole_coverage_width"],
            "coverage_height": facts["pole_coverage_height"],
            "coverage_cells": facts["pole_max_covered_cells"],
            "minimum_poles": facts["pole_lower_bound"],
            "pole_body_area": facts["pole_body_area"],
        },
        "free_cell_cap": {
            "value": facts["free_cell_cap"],
            "identity": "4900 - 3544 - 4 * 2 = 1348",
        },
        "generic_raw_outputs": {
            "boundary_slots": facts["boundary_output_slots"],
            "protocol_core_slots": facts["protocol_core_output_slots"],
            "total_slots": facts["boundary_output_slots"] + facts["protocol_core_output_slots"],
            "demand": facts["raw_output_demand"],
        },
        "boundary": {
            "required_instances": facts["boundary_instances"],
            "per_edge": facts["boundary_per_edge"],
            "body_span": facts["boundary_body_extent"],
            "gap_values": list(range(0, facts["grid_width"], facts["boundary_body_extent"])),
            "pattern_count": len(facts["patterns"]),
            "connector_cells_per_pattern": facts["boundary_output_slots"],
        },
        "residual_band": {
            "maximum_area": facts["free_cell_cap"],
            "anchor_minimum": 1,
            "oriented_dimensions": [
                [width, height] for width, height in facts["residual_dimensions"]
            ],
        },
    }


def _counts(facts: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, int]:
    nonzero_overlap_terms = sum(
        (len(terms) - 1) * multiplicity
        for (relation, _rhs, terms), multiplicity in expected["constraints"].items()
        if relation == ">="
    )
    return {
        "boundary_patterns": len(facts["patterns"]),
        "pattern_variables": len(facts["patterns"]),
        "oriented_dimensions": len(facts["residual_dimensions"]),
        "rectangle_placements": len(expected["placements"]),
        "rectangle_variables": len(expected["placements"]),
        "variables": len(expected["variables"]),
        "placement_feasibility_constraints": len(expected["placements"]),
        "constraints": sum(expected["constraints"].values()),
        "equality_constraints": 2,
        "nonzero_overlap_terms": nonzero_overlap_terms,
        "pattern_placement_pairs": len(facts["patterns"]) * len(expected["placements"]),
    }


def _claim_scope() -> dict[str, Any]:
    return {
        "out_of_band": {
            "inside_opb": False,
            "coverage": "lex-better rectangle dimensions with area greater than 1348",
            "basis": "free-cell cap lemma: 4900 - 3544 - 4 * 2 = 1348",
        },
        "residual_band": {
            "inside_opb": True,
            "coverage": (
                "all 22 oriented lex-better dimensions with area at most 1348 and anchors x,y >= 1"
            ),
            "mechanism": (
                "47 boundary patterns and exact rectangle/forced-connector union-cap constraints"
            ),
        },
        "combined_statement": (
            "the elementary out-of-band exclusion and the residual-band PB exclusion together cover "
            "the complete strict (1326,34) upper-bound lemma"
        ),
        "limitations": [
            "translation only; this metadata does not assert solver UNSAT or proof verification",
            "research artifact; not sealed CERTIFIED evidence",
            "does not restore any historical PB judgment outside PB-03",
        ],
    }


def _semantic_canaries(facts: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    gap_records: dict[str, Any] = {}
    for gap in (0, 3, 69):
        anchors = _anchors(gap, facts["grid_width"], 3, facts["boundary_per_edge"])
        gap_records[str(gap)] = {"anchors": anchors, "access_coordinates": [value + 1 for value in anchors]}
    transpose = all(
        frozenset((y, x) for x, y in set(_q_sources(left, bottom, facts)))
        == frozenset(_q_sources(bottom, left, facts))
        for left, bottom in facts["patterns"]
    )
    allowed_sources = _q_sources(0, 3, facts)
    synthetic_sources = _q_sources(3, 3, facts)
    single_and_set = (
        allowed_sources.count((1, 1)) == 1
        and len(set(allowed_sources)) == 46
        and synthetic_sources.count((1, 1)) == 2
        and len(set(synthetic_sources)) == 45
    )
    one_offset_bottom = (1, 0 + 1)
    double_offset_bottom = (1, 0 + 2)
    double_rejected = allowed_sources[23] == one_offset_bottom and allowed_sources[23] != double_offset_bottom
    return {
        "gap_anchors_0_3_69": {
            "pass": (
                gap_records["0"]["anchors"][0] == 1
                and gap_records["3"]["anchors"][0] == 0
                and gap_records["69"]["anchors"][-1] == 66
            ),
            "cases": gap_records,
        },
        "transpose_symmetry": {"pass": transpose},
        "one_one_single_offset_and_set_semantics": {
            "pass": single_and_set,
            "allowed_pattern_source_count": allowed_sources.count((1, 1)),
            "synthetic_collision_source_count": synthetic_sources.count((1, 1)),
            "synthetic_collision_set_size": len(set(synthetic_sources)),
        },
        "double_offset_rejected": {
            "pass": double_rejected,
            "one_offset": list(one_offset_bottom),
            "forbidden_double_offset": list(double_offset_bottom),
        },
    }


def _corpus(facts: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    count = 0
    minimum_union = facts["grid_width"] * facts["grid_height"]
    minimum_witness: list[int] | None = None
    for pattern_index, q_set in enumerate(expected["q_sets"]):
        for _variable_id, width, height, x_value, y_value in expected["placements"]:
            overlap = sum(
                x_value <= qx < x_value + width and y_value <= qy < y_value + height
                for qx, qy in q_set
            )
            union_lower_bound = width * height + 46 - overlap
            if union_lower_bound < minimum_union:
                minimum_union = union_lower_bound
                minimum_witness = [pattern_index, width, height, x_value, y_value, overlap]
            if overlap - 46 >= width * height - facts["free_cell_cap"] and len(errors) < 20:
                errors.append(
                    {
                        "pattern_index": pattern_index,
                        "rectangle": [width, height, x_value, y_value],
                        "overlap": overlap,
                    }
                )
            count += 1
    return {
        "corpus_count": count,
        "corpus_errors": errors,
        "satisfying_selected_pairs": len(errors),
        "minimum_union_lower_bound": minimum_union,
        "minimum_union_witness": minimum_witness,
    }


def verify(
    *,
    project_root: Path,
    opb_path: Path,
    meta_path: Path,
    var_map_path: Path,
    estimate_path: Path,
) -> dict[str, Any]:
    meta_raw = meta_path.read_bytes()
    var_map_raw = var_map_path.read_bytes()
    estimate_raw = estimate_path.read_bytes()
    meta = _mapping(_strict_json(meta_raw, "metadata"), "metadata")
    var_map = _mapping(_strict_json(var_map_raw, "variable map"), "variable map")
    estimate = _mapping(_strict_json(estimate_raw, "estimate"), "estimate")
    if meta.get("schema_version") != META_SCHEMA or meta.get("model_schema_version") != MODEL_SCHEMA:
        raise GateError("metadata schema identity is invalid")
    if var_map.get("schema_version") != VAR_MAP_SCHEMA or var_map.get("model_schema_version") != MODEL_SCHEMA:
        raise GateError("variable-map schema identity is invalid")
    if estimate.get("schema_version") != ESTIMATE_SCHEMA or estimate.get("model_schema_version") != MODEL_SCHEMA:
        raise GateError("estimate schema identity is invalid")
    if any(payload.get("semantics") != SEMANTICS for payload in (meta, var_map, estimate)):
        raise GateError("semantics identity is invalid")
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

    input_raw, input_records = _bound_records(meta, "inputs", INPUT_PATHS, project_root)
    _estimate_input_raw, estimate_input_records = _bound_records(estimate, "inputs", INPUT_PATHS, project_root)
    _evidence_raw, evidence_records = _bound_records(meta, "evidence", EVIDENCE_PATHS, project_root)
    _estimate_evidence_raw, estimate_evidence_records = _bound_records(
        estimate, "evidence", EVIDENCE_PATHS, project_root
    )
    strict_hashes_pass = _verify_sha256_manifest(input_raw["sha256s"], input_raw)
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
        estimate.get("harness_source"), ENCODER_SOURCE, project_root, "estimate.harness_source"
    )
    meta_snapshot = _validate_git_snapshot(meta.get("git_snapshot"), "metadata.git_snapshot")
    estimate_snapshot = _validate_git_snapshot(estimate.get("git_snapshot"), "estimate.git_snapshot")
    if meta_snapshot != estimate_snapshot:
        raise GateError("metadata and estimate Git snapshots disagree")
    if meta.get("harness") != ENCODER_NAME or estimate.get("harness") != ENCODER_NAME:
        raise GateError("encoder harness identity is invalid")

    outputs = _mapping(meta.get("outputs"), "metadata.outputs")
    if set(outputs) != {"opb", "var_map", "metadata"}:
        raise GateError("metadata.outputs is not closed")
    opb_record = _validate_record(outputs.get("opb"), opb_path, project_root, "metadata.outputs.opb")
    var_map_record = _validate_record(
        outputs.get("var_map"), var_map_path, project_root, "metadata.outputs.var_map"
    )
    metadata_output = _mapping(outputs.get("metadata"), "metadata.outputs.metadata")
    if set(metadata_output) != {"path"}:
        raise GateError("metadata.outputs.metadata is not a closed path record")
    metadata_output_path = metadata_output.get("path")
    if type(metadata_output_path) is not str or Path(metadata_output_path).resolve() != meta_path.resolve():
        raise GateError("metadata.outputs.metadata path mismatch")
    _validate_record(meta.get("estimate"), estimate_path, project_root, "metadata.estimate")

    variables = var_map.get("variables")
    if not isinstance(variables, list) or not all(isinstance(item, Mapping) for item in variables):
        raise GateError("variable map variables must be an object array")
    ids = [item.get("id") for item in variables]
    names = [item.get("name") for item in variables]
    dense = (
        ids == list(range(1, len(variables) + 1))
        and all(type(name) is str and name for name in names)
        and len(names) == len(set(names))
        and var_map.get("variable_count") == len(variables)
    )
    var_map_exact = (
        set(var_map) == {"schema_version", "semantics", "model_schema_version", "variable_count", "variables"}
        and variables == expected["variables"]
    )
    parsed = _parse_opb(opb_path)
    header_exact = (
        parsed["header"]
        == {"variables": 16749, "constraints": 16704, "equal": 2, "intsize": 64}
        and parsed["constraint_count"] == 16704
        and parsed["equal_count"] == 2
        and parsed["maximum_variable"] == 16749
    )
    constraints_exact = parsed["constraints"] == expected["constraints"]

    metadata_argv = meta.get("argv")
    estimate_argv = estimate.get("argv")
    planning = _mapping(estimate.get("proof_size_planning"), "proof_size_planning")
    metadata_match = (
        set(meta) == metadata_keys
        and isinstance(metadata_argv, list)
        and bool(metadata_argv)
        and all(type(value) is str for value in metadata_argv)
        and meta.get("derived_facts") == derived_facts
        and meta.get("counts") == counts
        and meta.get("proof_status") == "translation_only_no_unsat_or_proof_claim"
        and meta.get("model_schema_version") == MODEL_SCHEMA
        and meta.get("variable_map_schema_version") == VAR_MAP_SCHEMA
        and meta.get("project_root") == str(project_root)
        and meta.get("claim_scope") == _claim_scope()
    )
    estimate_match = (
        set(estimate) == estimate_keys
        and isinstance(estimate_argv, list)
        and bool(estimate_argv)
        and all(type(value) is str for value in estimate_argv)
        and estimate.get("derived_facts") == derived_facts
        and estimate.get("counts") == counts
        and estimate.get("metadata_schema_version") == META_SCHEMA
        and estimate.get("variable_map_schema_version") == VAR_MAP_SCHEMA
        and dict(planning)
        == {
            "basis": {
                "method": "conservative_round_up_to_512_mib_planning_envelope",
                "scratch_observed_proof_bytes": 25_496_266,
            },
            "bound_bytes": 536_870_912,
            "decision": "GO",
            "user_limit_bytes": 5_000_000_000,
        }
        and estimate.get("projected_outputs") == {"opb_bytes": 936_597}
        and estimate.get("project_root") == str(project_root)
    )
    canaries = _semantic_canaries(facts)
    canaries_pass = all(record.get("pass") is True for record in canaries.values())
    corpus = _corpus(facts, expected)
    corpus_pass = (
        corpus["corpus_count"] == 784_994
        and corpus["corpus_errors"] == []
        and corpus["minimum_union_lower_bound"] > 1348
    )
    patterns_pass = (
        len(facts["patterns"]) == 47
        and all(left == 0 or bottom == 0 for left, bottom in facts["patterns"])
        and all(len(q_set) == 46 for q_set in expected["q_sets"])
    )
    partition_pass = (
        len(facts["lex_dimensions"]) == 1785
        and len(facts["elementary_dimensions"]) == 1763
        and len(facts["residual_dimensions"]) == 22
        and len(expected["placements"]) == 16_702
        and set(facts["lex_dimensions"])
        == set(facts["elementary_dimensions"]) | set(facts["residual_dimensions"])
        and not (set(facts["elementary_dimensions"]) & set(facts["residual_dimensions"]))
    )
    two_stage_pass = (
        facts["free_cell_cap"] == 4900 - 3544 - 4 * 2 == 1348
        and all(width * height > 1348 for width, height in facts["elementary_dimensions"])
        and all(width * height <= 1348 for width, height in facts["residual_dimensions"])
        and corpus_pass
    )
    translation_inputs = {
        "estimate": _file_record(estimate_path, project_root),
        "meta": _file_record(meta_path, project_root),
        "opb": _file_record(opb_path, project_root),
        "var_map": _file_record(var_map_path, project_root),
    }
    translation_hashes_pass = (
        translation_inputs["meta"]["sha256"] == hashlib.sha256(meta_raw).hexdigest()
        and translation_inputs["var_map"]["sha256"] == hashlib.sha256(var_map_raw).hexdigest()
        and translation_inputs["estimate"]["sha256"] == hashlib.sha256(estimate_raw).hexdigest()
        and translation_inputs["opb"]["sha256"] == parsed["sha256"] == opb_record["sha256"]
        and translation_inputs["var_map"] == var_map_record
    )
    checks = {
        "strict_bundle_closed_and_hashed": (
            strict_hashes_pass
            and input_records == estimate_input_records
            and evidence_records == estimate_evidence_records
        ),
        "encoder_provenance_match": (
            encoder_source == estimate_encoder_source and meta_snapshot == estimate_snapshot
        ),
        "translation_inputs_closed_and_hashed": translation_hashes_pass,
        "metadata_reconstruction_match": metadata_match,
        "estimate_reconstruction_match": estimate_match,
        "variable_map_dense": dense,
        "variable_map_exact": var_map_exact,
        "opb_header_exact": header_exact,
        "constraint_multiset_exact": constraints_exact,
        "boundary_patterns_exhaustive": patterns_pass,
        "lex_better_partition_exact": partition_pass,
        "two_stage_theorem_coverage_exact": two_stage_pass,
        "corpus_exhaustive_unsat": corpus_pass,
        "semantic_canaries_pass": canaries_pass,
    }
    if set(checks) != REQUIRED_CHECKS:
        raise AssertionError("gate check map drifted from REQUIRED_CHECKS")
    return {
        "schema_version": GATE_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "semantics": SEMANTICS,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "encoder_git_snapshot": meta_snapshot,
        "encoder_source": encoder_source,
        "gate_source": _file_record(Path(__file__), project_root),
        "git_snapshot": _git_snapshot(project_root),
        "strict_inputs": input_records,
        "evidence": evidence_records,
        "translation_inputs": translation_inputs,
        "derived_facts": derived_facts,
        "counts": counts,
        "semantic_canaries": canaries,
        "corpus_count": corpus["corpus_count"],
        "corpus_errors": corpus["corpus_errors"],
        "minimum_union_lower_bound": corpus["minimum_union_lower_bound"],
        "minimum_union_witness": corpus["minimum_union_witness"],
        "constraint_multiset_sha256": {
            "expected": _multiset_hash(expected["constraints"]),
            "actual": _multiset_hash(parsed["constraints"]),
        },
        "constraint_diff": _multiset_diff(expected["constraints"], parsed["constraints"]),
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
            "semantics": SEMANTICS,
            "status": "FAIL",
            "checks": {name: False for name in sorted(REQUIRED_CHECKS)},
            "corpus_count": 0,
            "corpus_errors": [{"type": type(exc).__name__, "message": str(exc)}],
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "proof_status": "translation_gate_failed_no_unsat_or_proof_claim",
        }
    _exclusive_json(args.output, report)
    print(json.dumps({"status": report["status"], "output": str(args.output.resolve())}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
