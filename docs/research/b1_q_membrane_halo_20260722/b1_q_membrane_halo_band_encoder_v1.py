#!/usr/bin/env python3
"""Build-only OPB encoder for the B1 Q/membrane/halo ceiling band.

The encoder binds itself to the strict instance, reconstructs all 47 legal
boundary patterns and all 2,520 placements of the two oriented ``(1190, 34)``
ceiling rectangles, and emits a transparent selector model.  It deliberately
does not invoke a solver or proof checker and does not authorize a formal run.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_RELATIVE_PATH = Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json")
EXPECTED_STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"

MODEL_SCHEMA = "b1_q_membrane_halo_band_model_v1"
ESTIMATE_SCHEMA = "b1_q_membrane_halo_band_estimate_v1"
METADATA_SCHEMA = "b1_q_membrane_halo_band_metadata_v1"
VAR_MAP_SCHEMA = "b1_q_membrane_halo_band_var_map_v1"
SEMANTICS = "b1_q_membrane_halo_band_build_only_v1"
HARNESS = "b1_q_membrane_halo_band_encoder_v1"

GRID_SIZE = 70
MINIMUM_RECTANGLE_SIDE = 6
OBJECTIVE_AREA = 1_190
OBJECTIVE_MINIMUM_SIDE = 34
ORIENTED_DIMENSIONS = ((34, 35), (35, 34))
MEMBRANE_CONSTANT = 580
INCIDENCE_CAP = 4
FREE_CELL_CAP = 1_320

EXPECTED_COUNTS = {
    "boundary_patterns": 47,
    "rectangle_placements": 2_520,
    "pattern_placement_corpus": 118_440,
    "surviving_pairs": 118_346,
    "violating_pairs": 94,
    "pattern_selector_variables": 47,
    "placement_selector_variables": 2_520,
    "variables": 2_567,
    "equality_constraints": 2,
    "pair_exclusion_constraints": 94,
    "constraints": 96,
}

RESOURCE_CONTRACT = {
    "formal_run_authorized": False,
    "memory_high": "35GiB",
    "memory_high_bytes": 35 * 1024**3,
    "memory_max": "39GiB",
    "memory_max_bytes": 39 * 1024**3,
    "memory_swap_max": "16GiB",
    "memory_swap_max_bytes": 16 * 1024**3,
    "oom_policy": "continue",
    "proof_size_cap_bytes": 5_000_000_000,
    "disk_low_water": "10GiB",
    "disk_low_water_bytes": 10 * 1024**3,
    "worker_limit": 1,
}


class EncoderError(ValueError):
    """The strict input, pinned estimate, or derived model failed closed."""


@dataclass(frozen=True, slots=True)
class Snapshot:
    path: Path
    display_path: str
    raw: bytes
    sha256: str

    def record(self) -> dict[str, Any]:
        return {
            "path": self.display_path,
            "sha256": self.sha256,
            "size_bytes": len(self.raw),
        }


@dataclass(frozen=True, slots=True)
class BoundaryPattern:
    index: int
    left_gap: int
    bottom_gap: int
    left_access: tuple[int, ...]
    bottom_access: tuple[int, ...]
    variable_id: int

    def variable_record(self) -> dict[str, Any]:
        return {
            "id": self.variable_id,
            "name": (
                f"pattern__index_{self.index:02d}__left_gap_{self.left_gap:02d}__bottom_gap_{self.bottom_gap:02d}"
            ),
            "kind": "boundary_pattern_selector",
            "pattern_index": self.index,
            "left_gap": self.left_gap,
            "bottom_gap": self.bottom_gap,
        }


@dataclass(frozen=True, slots=True)
class RectanglePlacement:
    width: int
    height: int
    x: int
    y: int
    variable_id: int

    def variable_record(self) -> dict[str, Any]:
        return {
            "id": self.variable_id,
            "name": (f"placement__w_{self.width:02d}__h_{self.height:02d}__x_{self.x:02d}__y_{self.y:02d}"),
            "kind": "rectangle_placement_selector",
            "width": self.width,
            "height": self.height,
            "x": self.x,
            "y": self.y,
            "area": self.width * self.height,
            "minimum_side": min(self.width, self.height),
        }


@dataclass(frozen=True, slots=True)
class PairViolation:
    pattern: BoundaryPattern
    placement: RectanglePlacement
    q: int
    e: int
    numerator: int
    ceil_term: int
    lhs: int

    def record(self) -> dict[str, Any]:
        return {
            "pattern_variable_id": self.pattern.variable_id,
            "placement_variable_id": self.placement.variable_id,
            "pattern_index": self.pattern.index,
            "left_gap": self.pattern.left_gap,
            "bottom_gap": self.pattern.bottom_gap,
            "width": self.placement.width,
            "height": self.placement.height,
            "x": self.placement.x,
            "y": self.placement.y,
            "q": self.q,
            "e": self.e,
            "numerator": self.numerator,
            "ceil_term": self.ceil_term,
            "lhs": self.lhs,
            "rhs": FREE_CELL_CAP,
        }


@dataclass(frozen=True, slots=True)
class BandModel:
    patterns: tuple[BoundaryPattern, ...]
    placements: tuple[RectanglePlacement, ...]
    violations: tuple[PairViolation, ...]
    counts: dict[str, int]
    band: dict[str, Any]

    @property
    def variables(self) -> list[dict[str, Any]]:
        return [
            *(pattern.variable_record() for pattern in self.patterns),
            *(placement.variable_record() for placement in self.placements),
        ]


def _reject_constant(value: str) -> Any:
    raise EncoderError(f"non-finite JSON number is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EncoderError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _loads_strict_json(raw: bytes, field: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EncoderError(f"{field} JSON parse failure: {exc}") from exc


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EncoderError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EncoderError(f"{field} must be an array")
    return value


def _exact_int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise EncoderError(f"{field} must be an exact integer")
    return int(value)


def _expect(value: Any, expected: Any, field: str) -> None:
    if value != expected or type(value) is not type(expected):
        raise EncoderError(f"{field} must be {expected!r}, got {value!r}")


def _display_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _snapshot(path: Path, project_root: Path) -> Snapshot:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise EncoderError(f"provenance path is not a regular file: {resolved}")
    raw = resolved.read_bytes()
    return Snapshot(
        path=resolved,
        display_path=_display_path(resolved, project_root),
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def _load_and_validate_strict(project_root: Path) -> tuple[Snapshot, Mapping[str, Any]]:
    snapshot = _snapshot(project_root / STRICT_RELATIVE_PATH, project_root)
    if snapshot.sha256 != EXPECTED_STRICT_SHA256:
        raise EncoderError(f"strict instance SHA256 drift: {snapshot.sha256}")
    root = _object(_loads_strict_json(snapshot.raw, "strict instance"), "strict instance")

    _expect(root.get("benchmark_id"), "factory_layout_optimality_benchmark_v1", "benchmark_id")
    _expect(root.get("schema_version"), 1, "schema_version")
    grid = _object(root.get("grid"), "grid")
    _expect(_exact_int(grid.get("width"), "grid.width"), GRID_SIZE, "grid.width")
    _expect(_exact_int(grid.get("height"), "grid.height"), GRID_SIZE, "grid.height")
    objective = _object(root.get("objective"), "objective")
    _expect(objective.get("kind"), "max_lex_area_min_side", "objective.kind")
    _expect(objective.get("body_cells_only"), True, "objective.body_cells_only")
    _expect(
        _exact_int(objective.get("minimum_side"), "objective.minimum_side"),
        MINIMUM_RECTANGLE_SIDE,
        "objective.minimum_side",
    )

    coordinate_system = _object(root.get("coordinate_system"), "coordinate_system")
    _expect(
        list(_array(coordinate_system.get("directions"), "coordinate directions")),
        ["N", "E", "S", "W"],
        "coordinate directions",
    )
    _expect(coordinate_system.get("indexing"), "zero_based", "coordinate indexing")
    _expect(coordinate_system.get("origin"), "southwest", "coordinate origin")
    _expect(coordinate_system.get("x_positive"), "east", "coordinate x axis")
    _expect(coordinate_system.get("y_positive"), "north", "coordinate y axis")
    direction_vectors = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}

    templates = _object(root.get("facility_templates"), "facility_templates")
    boundary = _object(templates.get("boundary_storage_port"), "boundary_storage_port")
    _expect(boundary.get("placement_rule"), "matching_map_boundary", "boundary placement rule")
    modes: dict[str, Mapping[str, Any]] = {}
    for index, raw_mode in enumerate(_array(boundary.get("modes"), "boundary modes")):
        mode = _object(raw_mode, f"boundary modes[{index}]")
        mode_id = mode.get("id")
        if type(mode_id) is not str or not mode_id or mode_id in modes:
            raise EncoderError("boundary mode IDs must be unique nonempty strings")
        modes[mode_id] = mode
    if set(modes) != {"left_boundary", "bottom_boundary"}:
        raise EncoderError("boundary mode set drifted")

    expected_modes = {
        "left_boundary": {
            "body": {"width": 1, "height": 3},
            "body_cell": {"x": 0, "y": 1},
            "direction": "E",
            "access_offset": (1, 1),
        },
        "bottom_boundary": {
            "body": {"width": 3, "height": 1},
            "body_cell": {"x": 1, "y": 0},
            "direction": "N",
            "access_offset": (1, 1),
        },
    }
    boundary_output_caps: set[int] = set()
    for mode_id, expected in expected_modes.items():
        mode = modes[mode_id]
        if dict(_object(mode.get("body"), f"{mode_id}.body")) != expected["body"]:
            raise EncoderError(f"{mode_id} body geometry drifted")
        ports = _array(mode.get("ports"), f"{mode_id}.ports")
        boundary_output_caps.add(sum(_object(port, f"{mode_id}.port").get("kind") == "output" for port in ports))
        if len(ports) != 1:
            raise EncoderError(f"{mode_id} must have exactly one port")
        port = _object(ports[0], f"{mode_id}.port")
        if port.get("kind") != "output":
            raise EncoderError(f"{mode_id} port must be an output")
        body_cell = _object(port.get("body_cell"), f"{mode_id}.port.body_cell")
        cell = {
            "x": _exact_int(body_cell.get("x"), f"{mode_id}.port.body_cell.x"),
            "y": _exact_int(body_cell.get("y"), f"{mode_id}.port.body_cell.y"),
        }
        direction = port.get("direction")
        if cell != expected["body_cell"] or direction != expected["direction"]:
            raise EncoderError(f"{mode_id} port geometry/direction drifted")
        vector = direction_vectors[str(direction)]
        access_offset = (cell["x"] + vector[0], cell["y"] + vector[1])
        if access_offset != expected["access_offset"]:
            raise EncoderError(f"{mode_id} active access offset drifted")
    if boundary_output_caps != {1}:
        raise EncoderError("boundary per-instance output capacity drifted")

    required = _array(root.get("required_instances"), "required_instances")
    identifiers: set[str] = set()
    template_counts: dict[str, int] = {}
    for index, raw_instance in enumerate(required):
        instance = _object(raw_instance, f"required_instances[{index}]")
        identifier = instance.get("id")
        template_name = instance.get("template")
        if type(identifier) is not str or not identifier or identifier in identifiers:
            raise EncoderError("required instance IDs must be unique nonempty strings")
        if type(template_name) is not str or template_name not in templates:
            raise EncoderError(f"required_instances[{index}] has an unknown template")
        identifiers.add(identifier)
        template_counts[template_name] = template_counts.get(template_name, 0) + 1
    if template_counts.get("boundary_storage_port") != 46:
        raise EncoderError("boundary instance count drifted")
    if template_counts.get("protocol_core") != 1:
        raise EncoderError("protocol-core instance count drifted")

    generic = _object(root.get("generic_requirements"), "generic_requirements")
    _expect(
        list(_array(generic.get("raw_output_providers"), "raw output providers")),
        ["boundary_storage_port", "protocol_core"],
        "raw output providers",
    )
    raw_outputs = _object(generic.get("raw_outputs"), "generic raw outputs")
    raw_demand = 0
    for commodity, value in raw_outputs.items():
        if type(commodity) is not str or not commodity:
            raise EncoderError("raw-output commodity names must be nonempty strings")
        demand = _exact_int(value, f"raw output {commodity}")
        if demand < 0:
            raise EncoderError(f"raw output {commodity} must be nonnegative")
        raw_demand += demand

    protocol_core = _object(templates.get("protocol_core"), "protocol_core")
    core_output_caps = {
        sum(
            _object(port, "protocol_core.port").get("kind") == "output"
            for port in _array(_object(mode, "protocol_core.mode").get("ports"), "protocol_core.ports")
        )
        for mode in _array(protocol_core.get("modes"), "protocol_core.modes")
    }
    if core_output_caps != {6}:
        raise EncoderError("protocol-core output capacity drifted")
    boundary_capacity = template_counts["boundary_storage_port"] * next(iter(boundary_output_caps))
    core_capacity = template_counts["protocol_core"] * next(iter(core_output_caps))
    if (raw_demand, boundary_capacity, core_capacity) != (52, 46, 6):
        raise EncoderError("raw-provider saturation components drifted")
    if raw_demand != boundary_capacity + core_capacity:
        raise EncoderError("raw-provider saturation identity no longer closes")
    return snapshot, root


def _ceil_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise EncoderError("ceil denominator must be positive")
    return -(-numerator // denominator)


def _edge_anchors(gap: int) -> tuple[int, ...]:
    if gap not in range(0, GRID_SIZE, 3):
        raise EncoderError(f"invalid boundary gap: {gap}")
    covered = [coordinate for coordinate in range(GRID_SIZE) if coordinate != gap]
    anchors: list[int] = []
    for offset in range(0, len(covered), 3):
        chunk = covered[offset : offset + 3]
        if len(chunk) != 3 or chunk != list(range(chunk[0], chunk[0] + 3)):
            raise EncoderError(f"boundary bodies are not contiguous around gap {gap}")
        anchors.append(chunk[0])
    if len(anchors) != 23:
        raise EncoderError(f"boundary gap {gap} did not produce 23 bodies")
    return tuple(anchors)


def _derive_patterns() -> tuple[BoundaryPattern, ...]:
    gaps = tuple(range(0, GRID_SIZE, 3))
    gap_pairs = tuple((0, gap) for gap in gaps) + tuple((gap, 0) for gap in gaps[1:])
    patterns: list[BoundaryPattern] = []
    for index, (left_gap, bottom_gap) in enumerate(gap_pairs):
        left_anchors = _edge_anchors(left_gap)
        bottom_anchors = _edge_anchors(bottom_gap)
        left_body = {(0, anchor + offset) for anchor in left_anchors for offset in range(3)}
        bottom_body = {(anchor + offset, 0) for anchor in bottom_anchors for offset in range(3)}
        if left_body & bottom_body:
            raise EncoderError(f"boundary pattern {index} overlaps at the southwest corner")
        left_access = tuple(anchor + 1 for anchor in left_anchors)
        bottom_access = tuple(anchor + 1 for anchor in bottom_anchors)
        q_cells = {(1, coordinate) for coordinate in left_access} | {(coordinate, 1) for coordinate in bottom_access}
        if len(q_cells) != 46:
            raise EncoderError(f"boundary pattern {index} does not have 46 distinct Q cells")
        if any(not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE) for x, y in q_cells):
            raise EncoderError(f"boundary pattern {index} Q cell left the grid")
        if q_cells & (left_body | bottom_body):
            raise EncoderError(f"boundary pattern {index} Q cell intersects boundary body")
        patterns.append(
            BoundaryPattern(
                index=index,
                left_gap=left_gap,
                bottom_gap=bottom_gap,
                left_access=left_access,
                bottom_access=bottom_access,
                variable_id=index + 1,
            )
        )
    if len(patterns) != 47:
        raise EncoderError("legal boundary-pattern corpus is not 47")
    return tuple(patterns)


def _derive_placements(first_variable_id: int) -> tuple[RectanglePlacement, ...]:
    placements: list[RectanglePlacement] = []
    for width, height in ORIENTED_DIMENSIONS:
        if width * height != OBJECTIVE_AREA or min(width, height) != OBJECTIVE_MINIMUM_SIDE:
            raise EncoderError("ceiling-band oriented dimensions drifted")
        for x in range(1, GRID_SIZE - width + 1):
            for y in range(1, GRID_SIZE - height + 1):
                placements.append(
                    RectanglePlacement(
                        width=width,
                        height=height,
                        x=x,
                        y=y,
                        variable_id=first_variable_id + len(placements),
                    )
                )
    if len(placements) != 2_520:
        raise EncoderError("ceiling-band placement corpus is not 2520")
    return tuple(placements)


def _contact_profile(pattern: BoundaryPattern, placement: RectanglePlacement) -> tuple[int, int]:
    q_count = 0
    endpoint_partials = 0
    if placement.x == 1:
        low = placement.y
        high = placement.y + placement.height - 1
        for coordinate in pattern.left_access:
            if low <= coordinate <= high:
                q_count += 1
                endpoint_partials += coordinate in {low, high}
    if placement.y == 1:
        low = placement.x
        high = placement.x + placement.width - 1
        for coordinate in pattern.bottom_access:
            if low <= coordinate <= high:
                q_count += 1
                endpoint_partials += coordinate in {low, high}
    if not (0 <= endpoint_partials <= q_count <= 46):
        raise EncoderError("invalid q/e contact profile")
    return q_count, endpoint_partials


def _derive_model() -> BandModel:
    patterns = _derive_patterns()
    placements = _derive_placements(len(patterns) + 1)
    violations: list[PairViolation] = []
    survivors_by_orientation = {f"{width}x{height}": 0 for width, height in ORIENTED_DIMENSIONS}
    corpus = 0
    for pattern in patterns:
        for placement in placements:
            corpus += 1
            q_count, endpoint_partials = _contact_profile(pattern, placement)
            numerator = MEMBRANE_CONSTANT - placement.width - placement.height + q_count // 2 + endpoint_partials
            ceil_term = _ceil_div(numerator, INCIDENCE_CAP)
            lhs = placement.width * placement.height + ceil_term
            if lhs <= FREE_CELL_CAP:
                survivors_by_orientation[f"{placement.width}x{placement.height}"] += 1
            else:
                violations.append(
                    PairViolation(
                        pattern=pattern,
                        placement=placement,
                        q=q_count,
                        e=endpoint_partials,
                        numerator=numerator,
                        ceil_term=ceil_term,
                        lhs=lhs,
                    )
                )

    counts = {
        "boundary_patterns": len(patterns),
        "rectangle_placements": len(placements),
        "pattern_placement_corpus": corpus,
        "surviving_pairs": sum(survivors_by_orientation.values()),
        "violating_pairs": len(violations),
        "pattern_selector_variables": len(patterns),
        "placement_selector_variables": len(placements),
        "variables": len(patterns) + len(placements),
        "equality_constraints": 2,
        "pair_exclusion_constraints": len(violations),
        "constraints": 2 + len(violations),
    }
    if counts != EXPECTED_COUNTS:
        raise EncoderError(f"unexpected build-only model counts: {counts!r}")
    if survivors_by_orientation != {"34x35": 59_173, "35x34": 59_173}:
        raise EncoderError(f"orientation survivor counts drifted: {survivors_by_orientation!r}")
    if [violation.pattern.index for violation in violations] != sorted(
        violation.pattern.index for violation in violations
    ):
        raise EncoderError("pair exclusions are not in deterministic pattern order")
    previous = (-1, -1)
    for violation in violations:
        current = (violation.pattern.index, violation.placement.variable_id)
        if current <= previous:
            raise EncoderError("pair exclusions are not in deterministic placement order")
        previous = current

    placements_by_orientation = {
        f"{width}x{height}": sum(placement.width == width and placement.height == height for placement in placements)
        for width, height in ORIENTED_DIMENSIONS
    }
    band = {
        "objective_floor": {"area": OBJECTIVE_AREA, "minimum_side": OBJECTIVE_MINIMUM_SIDE},
        "oriented_dimensions": [list(pair) for pair in ORIENTED_DIMENSIONS],
        "anchor_bounds": [
            {
                "width": width,
                "height": height,
                "x": [1, GRID_SIZE - width],
                "y": [1, GRID_SIZE - height],
            }
            for width, height in ORIENTED_DIMENSIONS
        ],
        "placements_by_orientation": placements_by_orientation,
        "surviving_pairs_by_orientation": survivors_by_orientation,
    }
    return BandModel(
        patterns=patterns,
        placements=placements,
        violations=tuple(violations),
        counts=counts,
        band=band,
    )


def _formula() -> dict[str, Any]:
    return {
        "display": "wh + ceil((580-w-h+floor(q/2)+e)/4) <= 1320",
        "q_definition": "cardinality of rectangle intersection with active boundary-access set Q_delta",
        "e_definition": "Q_delta contacts at a tangential rectangle endpoint",
        "membrane_constant": MEMBRANE_CONSTANT,
        "incidence_cap": INCIDENCE_CAP,
        "free_cell_cap": FREE_CELL_CAP,
        "all_q_e_area_ceil_values_precomputed": True,
        "nonlinear_terms_in_opb_constraints": False,
    }


def _claim_scope() -> dict[str, Any]:
    return {
        "inside_opb": (
            "exactly one legal boundary pattern, exactly one ceiling-band rectangle placement, "
            "and all precomputed violating pattern-placement exclusions"
        ),
        "given_geometry": (
            "the reviewed B1 necessity lemma combining Q_delta contacts, membrane counting, "
            "and the nine-pole halo lower bound"
        ),
        "limitations": [
            "build-only diagnostic; no solver or proof checker was run",
            "does not establish a new upper bound",
            "does not provide a witness or prove attainability",
            "does not prove global optimality",
            "research artifact; not sealed and not production CERTIFIED evidence",
        ],
    }


def _render_sum(variable_ids: Sequence[int]) -> str:
    if not variable_ids:
        raise EncoderError("cannot render an empty exactly-one constraint")
    return " ".join(f"+1 x{variable_id}" for variable_id in variable_ids) + " = 1 ;"


def _render_opb(model: BandModel) -> bytes:
    lines = [
        (
            f"* #variable= {model.counts['variables']} #constraint= {model.counts['constraints']} "
            f"#equal= {model.counts['equality_constraints']} intsize= 64"
        ),
        (
            f"* model={MODEL_SCHEMA} generated_by={HARNESS} semantics={SEMANTICS} "
            "formula=wh+ceil((580-w-h+floor(q/2)+e)/4)<=1320_precomputed"
        ),
        _render_sum([pattern.variable_id for pattern in model.patterns]),
        _render_sum([placement.variable_id for placement in model.placements]),
        *(
            f"-1 x{violation.pattern.variable_id} -1 x{violation.placement.variable_id} >= -1 ;"
            for violation in model.violations
        ),
    ]
    if len(lines) != 2 + model.counts["constraints"]:
        raise EncoderError("rendered OPB constraint count drifted")
    return ("\n".join(lines) + "\n").encode("ascii")


def _argv_record(argv: Sequence[str] | None) -> list[str]:
    tail = list(sys.argv[1:] if argv is None else argv)
    return [str(Path(__file__).resolve()), *(str(value) for value in tail)]


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _source_record(project_root: Path) -> dict[str, Any]:
    return _snapshot(Path(__file__), project_root).record()


def _estimate_payload(
    *,
    argv_record: list[str],
    project_root: Path,
    strict: Snapshot,
    model: BandModel,
    opb: bytes,
) -> dict[str, Any]:
    source = _source_record(project_root)
    return {
        "schema_version": ESTIMATE_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "metadata_schema_version": METADATA_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "status": "PASS",
        "decision": "BUILD_ONLY",
        "semantics": SEMANTICS,
        "harness": HARNESS,
        "argv": argv_record,
        "project_root": str(project_root.resolve()),
        "harness_source": source,
        "encoder_script_sha256": source["sha256"],
        "strict_instance": strict.record(),
        "formula": _formula(),
        "band": model.band,
        "counts": model.counts,
        "projected_outputs": {"opb_bytes": len(opb)},
        "resource_contract": RESOURCE_CONTRACT,
        "claim_scope": _claim_scope(),
    }


def _validate_estimate(
    payload: Any,
    *,
    project_root: Path,
    strict: Snapshot,
    model: BandModel,
    opb: bytes,
) -> Mapping[str, Any]:
    estimate = _object(payload, "estimate")
    argv = _array(estimate.get("argv"), "estimate.argv")
    if not argv or any(type(value) is not str for value in argv):
        raise EncoderError("estimate.argv must be a nonempty string array")
    if argv[0] != str(Path(__file__).resolve()) or len(argv) < 2 or argv[1] != "estimate":
        raise EncoderError("estimate.argv is not an estimate invocation of this harness")
    expected = _estimate_payload(
        argv_record=list(argv),
        project_root=project_root,
        strict=strict,
        model=model,
        opb=opb,
    )
    if dict(estimate) != expected:
        raise EncoderError("pinned estimate does not match the current source/input/model bytes")
    return estimate


def _validate_sha256_argument(value: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise EncoderError("--estimate-sha256 must be a lowercase 64-character SHA256 digest")
    return value


def command_estimate(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    project_root = args.project_root.resolve(strict=True)
    if not project_root.is_dir():
        raise EncoderError("--project-root must be a directory")
    strict, _ = _load_and_validate_strict(project_root)
    model = _derive_model()
    opb = _render_opb(model)
    payload = _estimate_payload(
        argv_record=_argv_record(argv),
        project_root=project_root,
        strict=strict,
        model=model,
        opb=opb,
    )
    _exclusive_json(args.output.resolve(), payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "decision": "BUILD_ONLY",
                "opb_bytes": len(opb),
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


def command_encode(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    project_root = args.project_root.resolve(strict=True)
    if not project_root.is_dir():
        raise EncoderError("--project-root must be a directory")
    estimate_path = args.estimate.resolve(strict=True)
    outputs = [args.opb_out.resolve(), args.meta_out.resolve(), args.var_map_out.resolve()]
    if len(set(outputs)) != len(outputs):
        raise EncoderError("OPB, metadata, and variable-map outputs must be distinct")
    if estimate_path in outputs:
        raise EncoderError("estimate path must be distinct from all encode outputs")
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError("refusing to overwrite existing output(s): " + ", ".join(existing))

    strict, _ = _load_and_validate_strict(project_root)
    model = _derive_model()
    opb = _render_opb(model)
    estimate_snapshot = _snapshot(estimate_path, project_root)
    expected_estimate_sha = _validate_sha256_argument(args.estimate_sha256)
    if estimate_snapshot.sha256 != expected_estimate_sha:
        raise EncoderError(
            f"pinned estimate SHA256 mismatch: expected {expected_estimate_sha}, got {estimate_snapshot.sha256}"
        )
    _validate_estimate(
        _loads_strict_json(estimate_snapshot.raw, "estimate"),
        project_root=project_root,
        strict=strict,
        model=model,
        opb=opb,
    )

    args.opb_out.parent.mkdir(parents=True, exist_ok=True)
    with args.opb_out.open("xb") as handle:
        handle.write(opb)
    var_map = {
        "schema_version": VAR_MAP_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "status": "PASS",
        "semantics": SEMANTICS,
        "strict_instance_sha256": strict.sha256,
        "counts": model.counts,
        "variable_count": model.counts["variables"],
        "variables": model.variables,
    }
    _exclusive_json(args.var_map_out.resolve(), var_map)
    opb_record = _snapshot(args.opb_out, project_root).record()
    var_map_record = _snapshot(args.var_map_out, project_root).record()
    source = _source_record(project_root)
    metadata = {
        "schema_version": METADATA_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "estimate_schema_version": ESTIMATE_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "status": "PASS",
        "semantics": SEMANTICS,
        "harness": HARNESS,
        "argv": _argv_record(argv),
        "project_root": str(project_root),
        "harness_source": source,
        "encoder_script_sha256": source["sha256"],
        "strict_instance": strict.record(),
        "estimate": estimate_snapshot.record(),
        "formula": _formula(),
        "band_scan": model.band,
        "counts": model.counts,
        "resource_contract": RESOURCE_CONTRACT,
        "violating_pairs": [violation.record() for violation in model.violations],
        "outputs": {
            "opb": opb_record,
            "var_map": var_map_record,
            "metadata": {"path": _display_path(args.meta_out, project_root)},
        },
        "proof_status": "build_only_no_solver_or_proof",
        "claim_scope": _claim_scope(),
    }
    _exclusive_json(args.meta_out.resolve(), metadata)
    print(
        json.dumps(
            {
                "status": "PASS",
                "decision": "BUILD_ONLY",
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

    estimate = subparsers.add_parser("estimate", help="rebuild and size the OPB without writing it")
    estimate.add_argument("--project-root", type=Path, required=True)
    estimate.add_argument("--output", type=Path, required=True)
    estimate.set_defaults(func=command_estimate)

    encode = subparsers.add_parser("encode", help="encode from an explicitly hash-pinned estimate")
    encode.add_argument("--project-root", type=Path, required=True)
    encode.add_argument("--estimate", type=Path, required=True)
    encode.add_argument("--estimate-sha256", required=True)
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
