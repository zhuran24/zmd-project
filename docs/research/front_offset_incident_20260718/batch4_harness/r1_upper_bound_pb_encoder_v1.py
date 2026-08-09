#!/usr/bin/env python3
"""Encode the residual band of the strict R1 ``(1326, 34)`` upper bound.

This research-only encoder deliberately reads only the clean-room strict bundle.
It first emits a provenance-bound size estimate, then requires that unchanged
estimate before it will exclusively create an OPB formula and its metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MODEL_SCHEMA = "r1_upper_bound_pb_v1"
METADATA_SCHEMA = "r1_upper_bound_pb_metadata_v1"
VAR_MAP_SCHEMA = "r1_upper_bound_pb_var_map_v1"
ESTIMATE_SCHEMA = "r1_upper_bound_pb_estimate_v1"
SEMANTICS = "r1_strict_upper_bound_1326_34_research"
HARNESS = "r1_upper_bound_pb_encoder_v1"
PLANNING_PROOF_BOUND_BYTES = 512 * 1024 * 1024
SCRATCH_PROOF_BYTES = 25_496_266
TARGET_AREA = 1326
TARGET_MIN_SIDE = 34

STRICT_ROOT = Path("docs/research/cleanroom_rederivation_20260718/strict/external")
INPUT_PATHS = {
    "problem_instance": STRICT_ROOT / "problem_instance.json",
    "problem_instance_schema": STRICT_ROOT / "problem_instance.schema.json",
    "problem_md": STRICT_ROOT / "problem.md",
    "sha256s": STRICT_ROOT / "SHA256SUMS",
}
EVIDENCE_PATHS = {
    "r1_strict_response": Path(
        "docs/research/cleanroom_rederivation_20260718/04_r1_strict_response_gpt_pro_verbatim.md"
    ),
    "r1_strict_judgment": Path(
        "docs/research/cleanroom_rederivation_20260718/05_r1_strict_judgment_20260720.md"
    ),
    "independent_recomputation": Path(
        "docs/research/cleanroom_rederivation_20260718/verify_r1_strict_bounds.py"
    ),
}


class EncoderError(ValueError):
    """Raised when the strict input cannot be translated without guessing."""


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


@dataclass(frozen=True, slots=True)
class BoundaryPattern:
    index: int
    g_left: int
    g_bottom: int
    q_cells: tuple[tuple[int, int], ...]


@dataclass(slots=True)
class DerivedModel:
    variables: list[dict[str, Any]]
    constraints: list[Constraint]
    patterns: tuple[BoundaryPattern, ...]
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


def load_bound_snapshots(project_root: Path) -> tuple[dict[str, Snapshot], dict[str, Snapshot]]:
    """Load only the hard-bound clean-room inputs and evidence files."""

    root = project_root.resolve()
    inputs = {key: _snapshot(key, root / path, root) for key, path in INPUT_PATHS.items()}
    evidence = {key: _snapshot(key, root / path, root) for key, path in EVIDENCE_PATHS.items()}
    loads_strict_json(inputs["problem_instance_schema"].text)
    _verify_sha256_manifest(inputs)
    return inputs, evidence


def _verify_sha256_manifest(inputs: Mapping[str, Snapshot]) -> None:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(inputs["sha256s"].text.splitlines(), 1):
        if not raw_line:
            continue
        parts = raw_line.split("  ")
        if len(parts) != 2 or len(parts[0]) != 64:
            raise EncoderError(f"malformed SHA256SUMS line {line_number}")
        digest, name = parts
        if name in entries:
            raise EncoderError(f"duplicate SHA256SUMS entry: {name}")
        entries[name] = digest
    for key in ("problem_instance", "problem_instance_schema", "problem_md"):
        snapshot = inputs[key]
        expected = entries.get(snapshot.path.name)
        if expected != snapshot.sha256:
            raise EncoderError(f"SHA256SUMS mismatch for {snapshot.path.name}")


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


def _port_count(template: Mapping[str, Any], kind: str, field: str) -> int:
    counts: set[int] = set()
    for index, raw_mode in enumerate(_array(template.get("modes"), f"{field}.modes")):
        mode = _object(raw_mode, f"{field}.modes[{index}]")
        ports = _array(mode.get("ports"), f"{field}.modes[{index}].ports")
        counts.add(sum(_object(port, f"{field}.port").get("kind") == kind for port in ports))
    if len(counts) != 1:
        raise EncoderError(f"{field} modes disagree on {kind} port count")
    return next(iter(counts))


def _anchors(gap: int, grid_size: int, count: int, body_span: int) -> tuple[int, ...]:
    result = tuple(range(0, gap, body_span)) + tuple(
        gap + 1 + body_span * index for index in range(count - gap // body_span)
    )
    if len(result) != count or any(anchor < 0 or anchor + body_span > grid_size for anchor in result):
        raise EncoderError(f"invalid derived boundary anchors for gap {gap}")
    return result


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


def derive_model(problem_payload: Any) -> DerivedModel:
    """Independently derive the deterministic residual-band PB model."""

    problem = _object(problem_payload, "problem_instance")
    _expect(problem.get("benchmark_id"), "factory_layout_optimality_benchmark_v1", "benchmark_id")
    _expect(problem.get("schema_version"), 1, "schema_version")

    grid = _object(problem.get("grid"), "grid")
    grid_width = _exact_int(grid.get("width"), "grid.width")
    grid_height = _exact_int(grid.get("height"), "grid.height")
    if (grid_width, grid_height) != (70, 70):
        raise EncoderError("the R1 derivation is hard-bound to the 70x70 strict instance")

    objective = _object(problem.get("objective"), "objective")
    _expect(objective.get("kind"), "max_lex_area_min_side", "objective.kind")
    _expect(objective.get("body_cells_only"), True, "objective.body_cells_only")
    minimum_side = _exact_int(objective.get("minimum_side"), "objective.minimum_side")
    _expect(minimum_side, 6, "objective.minimum_side")

    templates = _object(problem.get("facility_templates"), "facility_templates")
    required_instances = _array(problem.get("required_instances"), "required_instances")
    template_counts: Counter[str] = Counter()
    seen_ids: set[str] = set()
    for index, raw_instance in enumerate(required_instances):
        instance = _object(raw_instance, f"required_instances[{index}]")
        instance_id = instance.get("id")
        template_name = instance.get("template")
        if type(instance_id) is not str or not instance_id or instance_id in seen_ids:
            raise EncoderError(f"invalid or duplicate required instance id at index {index}")
        if type(template_name) is not str or template_name not in templates:
            raise EncoderError(f"unknown required template at index {index}")
        seen_ids.add(instance_id)
        template_counts[template_name] += 1

    body_areas = {
        name: _mode_body_area(_object(value, f"facility_templates.{name}"), f"facility_templates.{name}")
        for name, value in templates.items()
    }
    required_body_area = sum(template_counts[name] * body_areas[name] for name in template_counts)
    powered_instances = sum(
        count
        for name, count in template_counts.items()
        if _object(templates[name], f"facility_templates.{name}").get("requires_power") is True
    )

    power = _object(problem.get("power"), "power")
    coverage = _object(power.get("coverage_from_pole_anchor"), "power.coverage_from_pole_anchor")
    coverage_width = (
        _exact_int(coverage.get("x_max_offset"), "power.x_max_offset")
        - _exact_int(coverage.get("x_min_offset"), "power.x_min_offset")
        + 1
    )
    coverage_height = (
        _exact_int(coverage.get("y_max_offset"), "power.y_max_offset")
        - _exact_int(coverage.get("y_min_offset"), "power.y_min_offset")
        + 1
    )
    pole_template_name = power.get("pole_template")
    if type(pole_template_name) is not str or pole_template_name not in templates:
        raise EncoderError("power.pole_template is missing or unknown")
    pole_body_area = body_areas[pole_template_name]
    pole_coverage_cells = coverage_width * coverage_height
    minimum_power_poles = math.ceil(powered_instances / pole_coverage_cells)
    free_cell_cap = grid_width * grid_height - required_body_area - pole_body_area * minimum_power_poles

    boundary_template = _object(templates.get("boundary_storage_port"), "boundary template")
    _expect(boundary_template.get("placement_rule"), "matching_map_boundary", "boundary placement_rule")
    boundary_count = template_counts["boundary_storage_port"]
    boundary_span = 3
    boundary_per_edge = grid_width // boundary_span
    if boundary_count != 2 * boundary_per_edge:
        raise EncoderError("boundary count does not force 23 placements per edge")
    if _port_count(boundary_template, "output", "boundary template") != 1:
        raise EncoderError("each boundary storage mode must expose one output")

    core_template = _object(templates.get("protocol_core"), "protocol_core template")
    core_count = template_counts["protocol_core"]
    core_outputs = _port_count(core_template, "output", "protocol_core template")
    generic = _object(problem.get("generic_requirements"), "generic_requirements")
    raw_outputs = _object(generic.get("raw_outputs"), "generic_requirements.raw_outputs")
    raw_output_demand = sum(_exact_int(value, f"raw_outputs.{name}") for name, value in raw_outputs.items())
    raw_output_slots = boundary_count + core_count * core_outputs

    sentinels = _object(problem.get("sentinels"), "sentinels")
    expected_sentinels = {
        "manufacturing_instance_count": powered_instances,
        "required_body_area": required_body_area,
        "generic_raw_output_terminals": raw_output_demand,
        "required_instance_count": len(required_instances),
    }
    for field, value in expected_sentinels.items():
        _expect(sentinels.get(field), value, f"sentinels.{field}")

    expected_scalars = {
        "required_body_area": (required_body_area, 3544),
        "powered_instances": (powered_instances, 219),
        "pole_body_area": (pole_body_area, 4),
        "pole_coverage_cells": (pole_coverage_cells, 144),
        "minimum_power_poles": (minimum_power_poles, 2),
        "free_cell_cap": (free_cell_cap, 1348),
        "boundary_count": (boundary_count, 46),
        "core_outputs": (core_outputs, 6),
        "raw_output_demand": (raw_output_demand, 52),
        "raw_output_slots": (raw_output_slots, 52),
    }
    for field, (actual, expected) in expected_scalars.items():
        _expect(actual, expected, field)

    gaps = tuple(range(0, grid_width, boundary_span))
    gap_pairs = tuple((0, gap) for gap in gaps) + tuple((gap, 0) for gap in gaps if gap)
    patterns: list[BoundaryPattern] = []
    for index, (g_left, g_bottom) in enumerate(gap_pairs):
        left = _anchors(g_left, grid_height, boundary_per_edge, boundary_span)
        bottom = _anchors(g_bottom, grid_width, boundary_per_edge, boundary_span)
        q_cells = tuple(
            sorted({(1, anchor + 1) for anchor in left} | {(anchor + 1, 1) for anchor in bottom})
        )
        if len(q_cells) != boundary_count:
            raise EncoderError(f"boundary pattern {index} does not have 46 connector cells")
        patterns.append(BoundaryPattern(index, g_left, g_bottom, q_cells))
    if len(patterns) != 47:
        raise EncoderError("boundary pattern derivation did not yield 47 patterns")

    oriented_dimensions = tuple(
        (width, height)
        for width in range(minimum_side, grid_width)
        for height in range(minimum_side, grid_height)
        if width * height <= free_cell_cap
        and (
            width * height > TARGET_AREA
            or (width * height == TARGET_AREA and min(width, height) > TARGET_MIN_SIDE)
        )
    )
    if len(oriented_dimensions) != 22:
        raise EncoderError("residual lex-better band did not yield 22 oriented dimensions")

    variables: list[dict[str, Any]] = []
    for pattern in patterns:
        variables.append(
            {
                "id": len(variables) + 1,
                "name": f"pattern__g_left_{pattern.g_left:02d}__g_bottom_{pattern.g_bottom:02d}",
                "kind": "boundary_pattern",
                "pattern_index": pattern.index,
                "g_left": pattern.g_left,
                "g_bottom": pattern.g_bottom,
                "q_size": len(pattern.q_cells),
                "q_cells": [list(cell) for cell in pattern.q_cells],
            }
        )

    placement_index = 0
    for dimension_index, (width, height) in enumerate(oriented_dimensions):
        for x_value in range(1, grid_width - width + 1):
            for y_value in range(1, grid_height - height + 1):
                variables.append(
                    {
                        "id": len(variables) + 1,
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
    if placement_index != 16_702:
        raise EncoderError("residual band did not yield 16,702 placements")

    pattern_variables = variables[: len(patterns)]
    placement_variables = variables[len(patterns) :]
    constraints = [
        _canonical_constraint(((record["id"], 1) for record in pattern_variables), "=", 1),
        _canonical_constraint(((record["id"], 1) for record in placement_variables), "=", 1),
    ]
    nonzero_overlap_terms = 0
    for placement in placement_variables:
        x_value = int(placement["x"])
        y_value = int(placement["y"])
        width = int(placement["width"])
        height = int(placement["height"])
        terms: list[tuple[int, int]] = []
        for pattern, pattern_variable in zip(patterns, pattern_variables, strict=True):
            overlap = sum(
                x_value <= qx < x_value + width and y_value <= qy < y_value + height
                for qx, qy in pattern.q_cells
            )
            if overlap:
                terms.append((int(pattern_variable["id"]), overlap))
                nonzero_overlap_terms += 1
        terms.append((int(placement["id"]), -boundary_count))
        constraints.append(
            _canonical_constraint(terms, ">=", int(placement["area"]) - free_cell_cap)
        )

    counts = {
        "boundary_patterns": len(patterns),
        "oriented_dimensions": len(oriented_dimensions),
        "rectangle_placements": placement_index,
        "pattern_variables": len(pattern_variables),
        "rectangle_variables": len(placement_variables),
        "variables": len(variables),
        "equality_constraints": 2,
        "placement_feasibility_constraints": len(placement_variables),
        "constraints": len(constraints),
        "pattern_placement_pairs": len(patterns) * len(placement_variables),
        "nonzero_overlap_terms": nonzero_overlap_terms,
    }
    if counts["variables"] != 16_749 or counts["constraints"] != 16_704:
        raise EncoderError("unexpected final PB model size")

    derived_facts = {
        "grid": {"width": grid_width, "height": grid_height, "area": grid_width * grid_height},
        "objective": {
            "kind": objective["kind"],
            "minimum_side": minimum_side,
            "target_area": TARGET_AREA,
            "target_min_side": TARGET_MIN_SIDE,
        },
        "required_body_area": required_body_area,
        "powered_manufacturing_instances": powered_instances,
        "power": {
            "coverage_width": coverage_width,
            "coverage_height": coverage_height,
            "coverage_cells": pole_coverage_cells,
            "minimum_poles": minimum_power_poles,
            "pole_body_area": pole_body_area,
        },
        "free_cell_cap": {
            "value": free_cell_cap,
            "identity": "4900 - 3544 - 4 * 2 = 1348",
        },
        "boundary": {
            "required_instances": boundary_count,
            "per_edge": boundary_per_edge,
            "body_span": boundary_span,
            "gap_values": list(gaps),
            "pattern_count": len(patterns),
            "connector_cells_per_pattern": boundary_count,
        },
        "generic_raw_outputs": {
            "demand": raw_output_demand,
            "boundary_slots": boundary_count,
            "protocol_core_slots": core_count * core_outputs,
            "total_slots": raw_output_slots,
        },
        "residual_band": {
            "anchor_minimum": 1,
            "maximum_area": free_cell_cap,
            "oriented_dimensions": [list(pair) for pair in oriented_dimensions],
        },
    }
    return DerivedModel(
        variables=variables,
        constraints=constraints,
        patterns=tuple(patterns),
        oriented_dimensions=oriented_dimensions,
        derived_facts=derived_facts,
        counts=counts,
    )


def render_opb(model: DerivedModel) -> bytes:
    """Render the exact deterministic RoundingSat-compatible OPB bytes."""

    equal_count = sum(constraint.relation == "=" for constraint in model.constraints)
    lines = [
        (
            f"* #variable= {len(model.variables)} #constraint= {len(model.constraints)} "
            f"#equal= {equal_count} intsize= 64"
        ),
        (
            f"* model={MODEL_SCHEMA} generated_by={HARNESS} semantics={SEMANTICS} "
            f"target={TARGET_AREA},{TARGET_MIN_SIDE} coverage=residual_band_area_le_1348"
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


def _provenance_records(
    project_root: Path,
) -> tuple[dict[str, Snapshot], dict[str, Snapshot], dict[str, Any], dict[str, Any]]:
    inputs, evidence = load_bound_snapshots(project_root)
    input_records = {key: inputs[key].record() for key in sorted(inputs)}
    evidence_records = {key: evidence[key].record() for key in sorted(evidence)}
    return input_records, evidence_records, _file_record(Path(__file__), project_root), _git_snapshot(project_root)


def command_estimate(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    if args.proof_limit_bytes <= 0:
        raise EncoderError("--proof-limit-bytes must be positive")
    project_root = args.project_root.resolve()
    inputs, evidence = load_bound_snapshots(project_root)
    model = derive_model(loads_strict_json(inputs["problem_instance"].text))
    opb = render_opb(model)
    input_records = {key: inputs[key].record() for key in sorted(inputs)}
    evidence_records = {key: evidence[key].record() for key in sorted(evidence)}
    decision = "GO" if PLANNING_PROOF_BOUND_BYTES <= args.proof_limit_bytes else "NO_GO"
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
        "inputs": input_records,
        "evidence": evidence_records,
        "git_snapshot": _git_snapshot(project_root),
        "derived_facts": model.derived_facts,
        "counts": model.counts,
        "projected_outputs": {"opb_bytes": len(opb)},
        "proof_size_planning": {
            "bound_bytes": PLANNING_PROOF_BOUND_BYTES,
            "user_limit_bytes": args.proof_limit_bytes,
            "decision": decision,
            "basis": {
                "scratch_observed_proof_bytes": SCRATCH_PROOF_BYTES,
                "method": "conservative_round_up_to_512_mib_planning_envelope",
            },
        },
    }
    _exclusive_json(args.output, estimate)
    print(json.dumps({"decision": decision, "opb_bytes": len(opb), "output": str(args.output.resolve())}))
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
    planning = _object(estimate.get("proof_size_planning"), "estimate.proof_size_planning")
    if planning.get("decision") != "GO":
        raise EncoderError("estimate is not GO")
    if _exact_int(planning.get("bound_bytes"), "estimate proof bound") != PLANNING_PROOF_BOUND_BYTES:
        raise EncoderError("estimate proof planning bound drifted")
    current_inputs = {key: inputs[key].record() for key in sorted(inputs)}
    current_evidence = {key: evidence[key].record() for key in sorted(evidence)}
    checks = {
        "inputs": current_inputs,
        "evidence": current_evidence,
        "harness_source": _file_record(Path(__file__), project_root),
        "git_snapshot": _git_snapshot(project_root),
        "derived_facts": model.derived_facts,
        "counts": model.counts,
        "projected_outputs": {"opb_bytes": len(opb)},
    }
    for field, expected in checks.items():
        if estimate.get(field) != expected:
            raise EncoderError(f"estimate provenance/model drift: {field}")


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
    _exclusive_json(args.var_map_out, var_map)
    meta = {
        "schema_version": METADATA_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "semantics": SEMANTICS,
        "harness": HARNESS,
        "argv": _argv_record(argv),
        "project_root": str(project_root),
        "harness_source": _file_record(Path(__file__), project_root),
        "inputs": {key: inputs[key].record() for key in sorted(inputs)},
        "evidence": {key: evidence[key].record() for key in sorted(evidence)},
        "git_snapshot": _git_snapshot(project_root),
        "estimate": estimate_record,
        "derived_facts": model.derived_facts,
        "counts": model.counts,
        "outputs": {
            "opb": _file_record(args.opb_out, project_root),
            "var_map": _file_record(args.var_map_out, project_root),
            "metadata": {"path": str(args.meta_out.resolve())},
        },
        "claim_scope": {
            "out_of_band": {
                "inside_opb": False,
                "coverage": "lex-better rectangle dimensions with area greater than 1348",
                "basis": "free-cell cap lemma: 4900 - 3544 - 4 * 2 = 1348",
            },
            "residual_band": {
                "inside_opb": True,
                "coverage": "all 22 oriented lex-better dimensions with area at most 1348 and anchors x,y >= 1",
                "mechanism": "47 boundary patterns and exact rectangle/forced-connector union-cap constraints",
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
        },
        "proof_status": "translation_only_no_unsat_or_proof_claim",
    }
    _exclusive_json(args.meta_out, meta)
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
