"""Independently verify a corrected Batch 4 PB translation.

The verifier does not import the encoder.  It parses the emitted OPB, rebuilds
the dense variable map and every expected constraint from snapshotted inputs,
and compares the full constraint multisets.  Port directions are validated as
N/S/E/W while the literal stored ``(x, y)`` remains the front coordinate.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.io.strict_json import loads_strict_json  # noqa: E402
from src.models.binding_subproblem import load_generic_io_requirements_from_text  # noqa: E402
from src.models.port_binding import (  # noqa: E402
    routing_free_sink_commodities_from_generic_inputs,
    routing_visible_port_demands,
    supports_exact_pose_level_binding,
)
from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES  # noqa: E402


SEMANTICS = "reconstructed_new_baseline"
ALLOWED_DIRECTIONS = frozenset({"N", "S", "E", "W"})
HISTORICAL_V1_STATUS = {
    "valid_for_intended_relaxation": False,
    "independent_defects": [
        "v1 moved stored front coordinates by direction a second time",
        "v1 used front-clear RHS demand-minus-port-count instead of minus-port-count",
    ],
    "consequence": "v1 UNSAT or proof output cannot certify the intended relaxation",
}
EXPECTED_INPUT_KEYS = frozenset(
    {
        "candidate_placements",
        "mandatory_instances",
        "generic_io_requirements",
        "canonical_rules",
        "preprocess_plan",
        "operation_profiles_source",
        "port_binding_source",
    }
)
HEADER_PATTERN = re.compile(
    r"^\*\s+#variable=\s+(\d+)\s+#constraint=\s+(\d+)\s+"
    r"#equal=\s+(\d+)\s+intsize=\s+(\d+)\s*$"
)
CONSTRAINT_PATTERN = re.compile(r"^(.*?)\s+(>=|=)\s+([+-]?\d+)\s*;\s*$")
TERM_PATTERN = re.compile(r"\s*([+-]\d+)\s+x([1-9]\d*)")

ConstraintKey = tuple[str, int, tuple[tuple[int, int], ...]]


class GateError(ValueError):
    """Raised when the verification surface is malformed or incomplete."""


def _exact_int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise GateError(f"{field} must be an exact integer")
    return int(value)


def _positive_int(value: Any, field: str) -> int:
    parsed = _exact_int(value, field)
    if parsed <= 0:
        raise GateError(f"{field} must be positive")
    return parsed


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


def _validate_file_record(
    value: Any,
    *,
    expected_path: Path,
    project_root: Path,
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GateError(f"{field} must be an object")
    expected = _file_record(expected_path, project_root)
    if dict(value) != expected:
        raise GateError(f"{field} does not match the current pinned file")
    return expected


def _validate_git_snapshot(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "head",
        "tracked_dirty",
        "tracked_diff_sha256",
        "tracked_diff_size_bytes",
    }:
        raise GateError(f"{field} must be a closed Git snapshot object")
    head = value.get("head")
    diff_hash = value.get("tracked_diff_sha256")
    diff_size = value.get("tracked_diff_size_bytes")
    dirty = value.get("tracked_dirty")
    if type(head) is not str or re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise GateError(f"{field}.head must be a full lowercase Git object id")
    if type(diff_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", diff_hash) is None:
        raise GateError(f"{field}.tracked_diff_sha256 must be a full lowercase SHA-256")
    if type(diff_size) is not int or diff_size < 0:
        raise GateError(f"{field}.tracked_diff_size_bytes must be a non-negative exact integer")
    if type(dirty) is not bool or dirty is not (diff_size > 0):
        raise GateError(f"{field}.tracked_dirty disagrees with the tracked diff size")
    return dict(value)


def _git_snapshot(project_root: Path) -> dict[str, Any]:
    revision_result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    revision = revision_result.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise GateError(f"unexpected git revision: {revision!r}")
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
    tracked_diff = diff_result.stdout
    return {
        "head": revision,
        "tracked_dirty": bool(tracked_diff),
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "tracked_diff_size_bytes": len(tracked_diff),
    }


def _strict_json_bytes(raw: bytes, field: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GateError(f"{field} is not UTF-8") from exc
    return loads_strict_json(text)


def _resolve_recorded_path(raw_path: Any, project_root: Path, field: str) -> Path:
    if type(raw_path) is not str or not raw_path:
        raise GateError(f"{field}.path must be a non-empty string")
    path = Path(raw_path)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def _load_bound_inputs(
    meta: Mapping[str, Any], project_root: Path
) -> tuple[dict[str, bytes], dict[str, str]]:
    raw_inputs = meta.get("inputs")
    if not isinstance(raw_inputs, Mapping) or frozenset(raw_inputs) != EXPECTED_INPUT_KEYS:
        raise GateError("metadata inputs do not match the closed v2 input set")
    snapshots: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for key in sorted(EXPECTED_INPUT_KEYS):
        record = raw_inputs[key]
        if not isinstance(record, Mapping):
            raise GateError(f"metadata inputs.{key} must be an object")
        path = _resolve_recorded_path(record.get("path"), project_root, f"inputs.{key}")
        if not path.is_file():
            raise FileNotFoundError(f"bound input is missing: {path}")
        expected_hash = record.get("sha256")
        if type(expected_hash) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise GateError(f"inputs.{key}.sha256 is not a full lowercase SHA-256")
        raw = path.read_bytes()
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hash:
            raise GateError(f"bound input hash mismatch for {key}: {actual_hash} != {expected_hash}")
        if _exact_int(record.get("size_bytes"), f"inputs.{key}.size_bytes") != len(raw):
            raise GateError(f"bound input size mismatch for {key}")
        snapshots[key] = raw
        hashes[key] = actual_hash
    return snapshots, hashes


def _grid_size(canonical_rules: Any) -> tuple[int, int]:
    if not isinstance(canonical_rules, Mapping):
        raise GateError("canonical_rules must be an object")
    globals_payload = canonical_rules.get("globals")
    if not isinstance(globals_payload, Mapping):
        raise GateError("canonical_rules.globals must be an object")
    grid = globals_payload.get("grid")
    if not isinstance(grid, Mapping):
        raise GateError("canonical_rules.globals.grid must be an object")
    return (
        _positive_int(grid.get("width"), "canonical grid width"),
        _positive_int(grid.get("height"), "canonical grid height"),
    )


def _body_cell(value: Any, field: str) -> tuple[int, int]:
    if isinstance(value, Mapping):
        x_value, y_value = value.get("x"), value.get("y")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        x_value, y_value = value
    else:
        raise GateError(f"{field} must be [x, y] or an x/y object")
    return _exact_int(x_value, f"{field}.x"), _exact_int(y_value, f"{field}.y")


def _literal_front(value: Any, field: str) -> tuple[int, int]:
    if not isinstance(value, Mapping):
        raise GateError(f"{field} must be an object")
    direction = value.get("dir")
    if type(direction) is not str or direction not in ALLOWED_DIRECTIONS:
        raise GateError(f"{field}.dir must be one of N/S/E/W")
    return (
        _exact_int(value.get("x"), f"{field}.x"),
        _exact_int(value.get("y"), f"{field}.y"),
    )


def _constraint_key(
    terms: Iterable[tuple[int, int]], relation: str, rhs: int
) -> ConstraintKey:
    if relation not in {"=", ">="}:
        raise GateError(f"unsupported relation: {relation}")
    combined: Counter[int] = Counter()
    for variable, coefficient in terms:
        combined[_positive_int(variable, "constraint variable id")] += _exact_int(
            coefficient, "constraint coefficient"
        )
    canonical_terms = tuple(
        sorted((variable, coefficient) for variable, coefficient in combined.items() if coefficient)
    )
    if not canonical_terms:
        raise GateError("constant-only constraint encountered")
    return relation, _exact_int(rhs, "constraint rhs"), canonical_terms


def _demand_summary(
    instances: Sequence[Mapping[str, Any]], routing_free: frozenset[str]
) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    counts: Counter[str] = Counter()
    operations: defaultdict[str, list[str]] = defaultdict(list)
    instance_ids: set[str] = set()
    for index, instance in enumerate(instances):
        if not isinstance(instance, Mapping):
            raise GateError(f"mandatory_instances[{index}] must be an object")
        instance_id = instance.get("instance_id")
        if type(instance_id) is not str or not instance_id:
            raise GateError(f"mandatory_instances[{index}].instance_id must be non-empty")
        if instance_id in instance_ids:
            raise GateError(f"duplicate mandatory instance_id: {instance_id}")
        instance_ids.add(instance_id)
        if instance.get("is_mandatory") is not True:
            raise GateError(f"mandatory instance {instance_id} is not marked mandatory")
        template = instance.get("facility_type")
        operation = instance.get("operation_type")
        if type(template) is not str or not template:
            raise GateError(f"mandatory instance {instance_id} has invalid facility_type")
        if type(operation) is not str or not operation:
            raise GateError(f"mandatory instance {instance_id} has invalid operation_type")
        counts[template] += 1
        operations[template].append(operation)

    summaries: dict[str, dict[str, Any]] = {}
    for template in sorted(counts):
        known: list[tuple[int, int]] = []
        unknown: set[str] = set()
        for operation in operations[template]:
            if operation not in OPERATION_PORT_PROFILES:
                unknown.add(operation)
                continue
            try:
                if not supports_exact_pose_level_binding(operation):
                    unknown.add(operation)
                    continue
                demand = routing_visible_port_demands(operation, routing_free)
            except ValueError:
                unknown.add(operation)
                continue
            known.append((int(demand[0]), int(demand[1])))
        unique_known = sorted(set(known))
        if unknown or len(known) != counts[template]:
            selected: list[int] | None = None
            policy = "omitted_unknown_demand"
        elif not unique_known:
            selected = None
            policy = "omitted_no_known_demand"
        else:
            selected = [
                min(value[0] for value in unique_known),
                min(value[1] for value in unique_known),
            ]
            policy = (
                "componentwise_min_inconsistent"
                if len(unique_known) > 1
                else "consistent_known_demand"
            )
        summaries[template] = {
            "selected": selected,
            "policy": policy,
            "known_demands": [list(value) for value in unique_known],
            "unknown_operations": sorted(unknown),
        }
    return dict(sorted(counts.items())), summaries


def _reconstruct_expected(
    *,
    candidate_payload: Any,
    instances_payload: Any,
    generic_io_text: str,
    canonical_rules_text: str,
    preprocess_plan_payload: Any,
    ghost_width: int,
    ghost_height: int,
    project_root: Path,
) -> dict[str, Any]:
    if not isinstance(candidate_payload, Mapping):
        raise GateError("candidate_placements must be an object")
    pools_payload = candidate_payload.get("facility_pools")
    if not isinstance(pools_payload, Mapping):
        raise GateError("candidate_placements.facility_pools must be an object")
    if not isinstance(instances_payload, Sequence) or isinstance(instances_payload, (str, bytes)):
        raise GateError("mandatory_instances must be an array")
    if not isinstance(preprocess_plan_payload, Mapping):
        raise GateError("preprocess_plan must be an object")

    canonical_payload = loads_strict_json(canonical_rules_text)
    grid_width, grid_height = _grid_size(canonical_payload)
    ghost_width = _positive_int(ghost_width, "ghost width")
    ghost_height = _positive_int(ghost_height, "ghost height")
    if ghost_width > grid_width or ghost_height > grid_height:
        raise GateError("ghost rectangle must fit inside the canonical grid")

    io_requirements = load_generic_io_requirements_from_text(
        text=generic_io_text,
        project_root=project_root,
        canonical_rules_text=canonical_rules_text,
    )
    routing_free = routing_free_sink_commodities_from_generic_inputs(
        io_requirements["required_generic_inputs"]
    )
    template_counts, template_demands = _demand_summary(list(instances_payload), routing_free)
    pools: dict[str, Sequence[Any]] = {}
    for template, count in template_counts.items():
        pool = pools_payload.get(template)
        if not isinstance(pool, Sequence) or isinstance(pool, (str, bytes)) or not pool:
            raise GateError(f"candidate pool missing, empty, or invalid for {template}")
        if count > len(pool):
            raise GateError(f"mandatory count exceeds candidate pool for {template}")
        pools[template] = pool

    variables: list[dict[str, Any]] = []
    variable_names: set[str] = set()

    def allocate(name: str, kind: str, **fields: Any) -> int:
        if name in variable_names:
            raise GateError(f"duplicate reconstructed variable name: {name}")
        variable_names.add(name)
        variable_id = len(variables) + 1
        variables.append({"id": variable_id, "name": name, "kind": kind, **fields})
        return variable_id

    pose_variables: dict[tuple[str, int], int] = {}
    cover: defaultdict[tuple[int, int], list[int]] = defaultdict(list)
    front_rows: list[tuple[int, list[tuple[int, int]], list[tuple[int, int]], int, int]] = []
    forced_zero: list[int] = []

    for template in sorted(template_counts):
        selected = template_demands[template]["selected"]
        for pose_index, raw_pose in enumerate(pools[template]):
            if not isinstance(raw_pose, Mapping):
                raise GateError(f"candidate pose {template}[{pose_index}] must be an object")
            pose_variable = allocate(
                f"pose__{template}__{pose_index}",
                "pose",
                template=template,
                pose_index=pose_index,
            )
            pose_variables[(template, pose_index)] = pose_variable
            raw_body = raw_pose.get("occupied_cells")
            if not isinstance(raw_body, Sequence) or isinstance(raw_body, (str, bytes)):
                raise GateError(f"{template}[{pose_index}].occupied_cells must be an array")
            body = {
                _body_cell(value, f"{template}[{pose_index}].occupied_cells[{index}]")
                for index, value in enumerate(raw_body)
            }
            if not body:
                raise GateError(f"{template}[{pose_index}] has no occupied cells")
            for x_value, y_value in body:
                if not (0 <= x_value < grid_width and 0 <= y_value < grid_height):
                    raise GateError(f"{template}[{pose_index}] body cell is outside the grid")
            for body_cell in sorted(body):
                cover[body_cell].append(pose_variable)

            sides: list[list[tuple[int, int]]] = []
            for side_name in ("input_port_cells", "output_port_cells"):
                raw_ports = raw_pose.get(side_name) or []
                if not isinstance(raw_ports, Sequence) or isinstance(raw_ports, (str, bytes)):
                    raise GateError(f"{template}[{pose_index}].{side_name} must be an array")
                fronts = [
                    _literal_front(port, f"{template}[{pose_index}].{side_name}[{index}]")
                    for index, port in enumerate(raw_ports)
                ]
                sides.append(
                    [
                        (x_value, y_value)
                        for x_value, y_value in fronts
                        if 0 <= x_value < grid_width and 0 <= y_value < grid_height
                    ]
                )
            if selected is None:
                continue
            input_demand, output_demand = int(selected[0]), int(selected[1])
            if len(sides[0]) < input_demand or len(sides[1]) < output_demand:
                forced_zero.append(pose_variable)
            else:
                front_rows.append(
                    (pose_variable, sides[0], sides[1], input_demand, output_demand)
                )

    occupancy_variables: dict[tuple[int, int], int] = {}
    for x_value, y_value in sorted(cover):
        occupancy_variables[(x_value, y_value)] = allocate(
            f"occupancy__{x_value}__{y_value}",
            "occupancy",
            x=x_value,
            y=y_value,
        )
    ghost_variables: dict[tuple[int, int], int] = {}
    for anchor_x in range(grid_width - ghost_width + 1):
        for anchor_y in range(grid_height - ghost_height + 1):
            ghost_variables[(anchor_x, anchor_y)] = allocate(
                f"ghost__{anchor_x}__{anchor_y}",
                "ghost_anchor",
                anchor_x=anchor_x,
                anchor_y=anchor_y,
            )

    constraints: Counter[ConstraintKey] = Counter()
    category_counts: Counter[str] = Counter()

    def add(category: str, key: ConstraintKey) -> None:
        constraints[key] += 1
        category_counts[category] += 1

    for template, count in sorted(template_counts.items()):
        add(
            "template_count",
            _constraint_key(
                ((pose_variables[(template, index)], 1) for index in range(len(pools[template]))),
                "=",
                count,
            ),
        )
    for body_cell, coverers in sorted(cover.items()):
        occupancy = occupancy_variables[body_cell]
        add(
            "occupancy_channel",
            _constraint_key(
                [*((variable, 1) for variable in coverers), (occupancy, -1)], "=", 0
            ),
        )
    for variable in sorted(forced_zero):
        add("forced_zero", _constraint_key(((variable, 1),), "=", 0))
    for variable, input_fronts, output_fronts, input_demand, output_demand in front_rows:
        for side, fronts, demand in (
            ("input", input_fronts, input_demand),
            ("output", output_fronts, output_demand),
        ):
            if demand <= 0:
                continue
            terms = [(variable, -demand)]
            terms.extend(
                (occupancy_variables[front], -1)
                for front in fronts
                if front in occupancy_variables
            )
            add(
                f"front_clear_{side}",
                _constraint_key(terms, ">=", -len(fronts)),
            )
    add(
        "ghost_one_hot",
        _constraint_key(((variable, 1) for variable in ghost_variables.values()), "=", 1),
    )
    for (anchor_x, anchor_y), ghost in ghost_variables.items():
        for x_value in range(anchor_x, anchor_x + ghost_width):
            for y_value in range(anchor_y, anchor_y + ghost_height):
                occupancy = occupancy_variables.get((x_value, y_value))
                if occupancy is not None:
                    add(
                        "ghost_body_exclusion",
                        _constraint_key(((ghost, -1), (occupancy, -1)), ">=", -1),
                    )

    constraint_count = sum(constraints.values())
    equal_count = sum(count for (relation, _rhs, _terms), count in constraints.items() if relation == "=")
    stats = {
        "variables": len(variables),
        "constraints": constraint_count,
        "pose_variables": len(pose_variables),
        "occupancy_variables": len(occupancy_variables),
        "ghost_variables": len(ghost_variables),
        "forced_zero": len(forced_zero),
        **{key: category_counts[key] for key in sorted(category_counts)},
    }
    return {
        "variables": variables,
        "constraints": constraints,
        "equal_count": equal_count,
        "template_counts": template_counts,
        "template_demands": template_demands,
        "routing_free_sink_commodities": sorted(routing_free),
        "stats": stats,
        "grid": {"width": grid_width, "height": grid_height},
        "ghost": {"width": ghost_width, "height": ghost_height},
    }


def _parse_constraint_line(line: str, line_number: int) -> ConstraintKey:
    match = CONSTRAINT_PATTERN.fullmatch(line)
    if match is None:
        raise GateError(f"malformed OPB constraint at line {line_number}")
    lhs, relation, raw_rhs = match.groups()
    terms: list[tuple[int, int]] = []
    position = 0
    while position < len(lhs):
        term_match = TERM_PATTERN.match(lhs, position)
        if term_match is None:
            raise GateError(f"malformed OPB term at line {line_number}, column {position + 1}")
        raw_coefficient, raw_variable = term_match.groups()
        terms.append((int(raw_variable), int(raw_coefficient)))
        position = term_match.end()
    return _constraint_key(terms, relation, int(raw_rhs))


def _parse_opb(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"OPB file is missing: {path}")
    header: dict[str, int] | None = None
    constraints: Counter[ConstraintKey] = Counter()
    constraint_count = 0
    equal_count = 0
    maximum_variable = 0
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            digest.update(raw_line)
            try:
                line = raw_line.decode("ascii").rstrip("\n")
            except UnicodeDecodeError as exc:
                raise GateError(f"OPB is not ASCII at line {line_number}") from exc
            if not line.strip():
                continue
            if line.startswith("*"):
                header_match = HEADER_PATTERN.fullmatch(line)
                if header_match is not None:
                    if header is not None:
                        raise GateError("OPB contains more than one competition header")
                    variable_count, declared_constraints, declared_equal, intsize = (
                        int(value) for value in header_match.groups()
                    )
                    header = {
                        "variables": variable_count,
                        "constraints": declared_constraints,
                        "equal": declared_equal,
                        "intsize": intsize,
                    }
                continue
            key = _parse_constraint_line(line, line_number)
            constraints[key] += 1
            constraint_count += 1
            if key[0] == "=":
                equal_count += 1
            maximum_variable = max(maximum_variable, *(variable for variable, _ in key[2]))
    if header is None:
        raise GateError("OPB competition header is missing")
    return {
        "header": header,
        "constraints": constraints,
        "constraint_count": constraint_count,
        "equal_count": equal_count,
        "maximum_variable": maximum_variable,
        "sha256": digest.hexdigest(),
    }


def _multiset_hash(constraints: Counter[ConstraintKey]) -> str:
    digest = hashlib.sha256(b"front-clear-pb-constraint-multiset-v2\0")
    for (relation, rhs, terms), multiplicity in sorted(constraints.items()):
        record = [relation, rhs, [[variable, coefficient] for variable, coefficient in terms], multiplicity]
        digest.update(
            json.dumps(record, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _constraint_record(key: ConstraintKey, count: int) -> dict[str, Any]:
    relation, rhs, terms = key
    return {
        "relation": relation,
        "rhs": rhs,
        "terms": [[variable, coefficient] for variable, coefficient in terms],
        "multiplicity": count,
    }


def _multiset_diff(
    expected: Counter[ConstraintKey], actual: Counter[ConstraintKey], limit: int = 10
) -> dict[str, Any]:
    missing = expected - actual
    unexpected = actual - expected
    return {
        "missing_total": sum(missing.values()),
        "unexpected_total": sum(unexpected.values()),
        "missing_examples": [
            _constraint_record(key, count) for key, count in sorted(missing.items())[:limit]
        ],
        "unexpected_examples": [
            _constraint_record(key, count) for key, count in sorted(unexpected.items())[:limit]
        ],
    }


def _front_is_clear(
    port: Mapping[str, Any], occupied: set[tuple[int, int]], width: int, height: int
) -> bool:
    x_value, y_value = _literal_front(port, "coordinate_canary.port")
    return 0 <= x_value < width and 0 <= y_value < height and (x_value, y_value) not in occupied


def coordinate_canaries() -> dict[str, dict[str, Any]]:
    """Exercise the three coordinate cases that distinguish literal x/y semantics."""

    first_port = {"x": 1, "y": 1, "dir": "E"}
    first_blocked = not _front_is_clear(first_port, {(1, 1)}, 5, 5)
    adjacent_free = (2, 1) not in {(1, 1)}

    second_port = {"x": 1, "y": 1, "dir": "E"}
    first_free = _front_is_clear(second_port, {(2, 1)}, 5, 5)
    adjacent_blocked = (2, 1) in {(2, 1)}

    left_port = {"x": 2, "y": 2, "dir": "E"}
    right_port = {"x": 2, "y": 2, "dir": "W"}
    owner_bodies = {(1, 2), (3, 2)}
    opposite_shared = (
        _literal_front(left_port, "coordinate_canary.left")
        == _literal_front(right_port, "coordinate_canary.right")
        and _front_is_clear(left_port, owner_bodies, 5, 5)
        and _front_is_clear(right_port, owner_bodies, 5, 5)
    )

    return {
        "stored_blocked_adjacent_free": {
            "pass": first_blocked and adjacent_free,
            "stored_front": [1, 1],
            "occupied": [[1, 1]],
        },
        "stored_free_adjacent_blocked": {
            "pass": first_free and adjacent_blocked,
            "stored_front": [1, 1],
            "occupied": [[2, 1]],
        },
        "opposite_ports_share_middle_front": {
            "pass": opposite_shared,
            "stored_fronts": [[2, 2], [2, 2]],
            "directions": ["E", "W"],
            "owner_body_occupied": [[1, 2], [3, 2]],
            "service_reference_count": 2,
        },
    }


def verify(
    *,
    opb_path: Path,
    meta_path: Path,
    var_map_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    meta_raw = meta_path.read_bytes()
    var_map_raw = var_map_path.read_bytes()
    meta = _strict_json_bytes(meta_raw, "metadata")
    var_map = _strict_json_bytes(var_map_raw, "variable map")
    if not isinstance(meta, Mapping):
        raise GateError("metadata must be an object")
    if not isinstance(var_map, Mapping):
        raise GateError("variable map must be an object")
    if meta.get("schema_version") != "front_clear_pb_v2":
        raise GateError("metadata schema_version is not front_clear_pb_v2")
    if meta.get("semantics") != SEMANTICS or meta.get("harness") != "pb_encoder_v2":
        raise GateError("metadata does not identify the corrected reconstructed baseline")
    revision = meta.get("git_revision")
    if type(revision) is not str or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise GateError("metadata git_revision must be a full lowercase Git object id")
    encoder_git_snapshot = _validate_git_snapshot(
        meta.get("git_snapshot"), "metadata.git_snapshot"
    )
    if encoder_git_snapshot["head"] != revision:
        raise GateError("metadata git_revision disagrees with metadata.git_snapshot.head")
    encoder_source = _validate_file_record(
        meta.get("harness_source"),
        expected_path=Path(__file__).with_name("pb_encoder_v2.py"),
        project_root=project_root,
        field="metadata.harness_source",
    )
    if not isinstance(meta.get("argv"), list) or not all(type(value) is str for value in meta["argv"]):
        raise GateError("metadata argv must be a string array")
    if meta.get("execution") != {"random_seed": None, "workers": None}:
        raise GateError("translation-only execution must record null seed and workers")

    bound_snapshots, bound_hashes = _load_bound_inputs(meta, project_root)
    outputs = meta.get("outputs")
    if not isinstance(outputs, Mapping):
        raise GateError("metadata outputs must be an object")
    if hashlib.sha256(var_map_raw).hexdigest() != outputs.get("var_map_sha256"):
        raise GateError("variable-map hash does not match metadata")

    grid_record = meta.get("grid")
    ghost_record = meta.get("ghost")
    if not isinstance(grid_record, Mapping) or not isinstance(ghost_record, Mapping):
        raise GateError("metadata grid/ghost records must be objects")
    ghost_width = _positive_int(ghost_record.get("width"), "metadata ghost width")
    ghost_height = _positive_int(ghost_record.get("height"), "metadata ghost height")

    candidate_payload = _strict_json_bytes(
        bound_snapshots["candidate_placements"], "candidate placements"
    )
    instances_payload = _strict_json_bytes(
        bound_snapshots["mandatory_instances"], "mandatory instances"
    )
    preprocess_payload = _strict_json_bytes(
        bound_snapshots["preprocess_plan"], "preprocess plan"
    )
    generic_io_text = bound_snapshots["generic_io_requirements"].decode("utf-8")
    canonical_rules_text = bound_snapshots["canonical_rules"].decode("utf-8")
    expected = _reconstruct_expected(
        candidate_payload=candidate_payload,
        instances_payload=instances_payload,
        generic_io_text=generic_io_text,
        canonical_rules_text=canonical_rules_text,
        preprocess_plan_payload=preprocess_payload,
        ghost_width=ghost_width,
        ghost_height=ghost_height,
        project_root=project_root,
    )

    raw_variables = var_map.get("variables")
    if not isinstance(raw_variables, list) or not all(isinstance(value, Mapping) for value in raw_variables):
        raise GateError("variable map variables must be an object array")
    variable_ids = [value.get("id") for value in raw_variables]
    names = [value.get("name") for value in raw_variables]
    dense = (
        variable_ids == list(range(1, len(raw_variables) + 1))
        and all(type(name) is str and name for name in names)
        and len(set(names)) == len(names)
        and var_map.get("variable_count") == len(raw_variables)
    )
    var_map_exact = (
        var_map.get("schema_version") == "front_clear_pb_var_map_v2"
        and var_map.get("semantics") == SEMANTICS
        and raw_variables == expected["variables"]
    )

    parsed = _parse_opb(opb_path)
    if parsed["sha256"] != outputs.get("opb_sha256"):
        raise GateError("OPB hash does not match metadata")
    translation_inputs = {
        "meta": _file_record(meta_path, project_root),
        "opb": _file_record(opb_path, project_root),
        "var_map": _file_record(var_map_path, project_root),
    }
    if translation_inputs["meta"]["sha256"] != hashlib.sha256(meta_raw).hexdigest():
        raise GateError("metadata changed while the gate was running")
    if translation_inputs["var_map"]["sha256"] != hashlib.sha256(var_map_raw).hexdigest():
        raise GateError("variable map changed while the gate was running")
    if translation_inputs["opb"]["sha256"] != parsed["sha256"]:
        raise GateError("OPB changed while the gate was running")
    header = parsed["header"]
    expected_constraint_count = sum(expected["constraints"].values())
    header_counts = (
        header
        == {
            "variables": len(expected["variables"]),
            "constraints": expected_constraint_count,
            "equal": expected["equal_count"],
            "intsize": 64,
        }
        and parsed["constraint_count"] == expected_constraint_count
        and parsed["equal_count"] == expected["equal_count"]
        and parsed["maximum_variable"] <= len(expected["variables"])
    )
    constraints_exact = parsed["constraints"] == expected["constraints"]
    expected_hash = _multiset_hash(expected["constraints"])
    actual_hash = _multiset_hash(parsed["constraints"])
    canaries = coordinate_canaries()
    canaries_pass = all(record["pass"] is True for record in canaries.values())
    metadata_exact = (
        meta.get("grid") == expected["grid"]
        and meta.get("ghost") == expected["ghost"]
        and meta.get("template_counts") == expected["template_counts"]
        and meta.get("template_demands") == expected["template_demands"]
        and meta.get("routing_free_sink_commodities") == expected["routing_free_sink_commodities"]
        and meta.get("stats") == expected["stats"]
        and meta.get("harness_source") == encoder_source
        and meta.get("git_snapshot") == encoder_git_snapshot
        and meta.get("proof_status") == "translation_only_no_unsat_or_proof_claim"
        and meta.get("historical_v1_status") == HISTORICAL_V1_STATUS
    )
    checks = {
        "input_hashes_match": True,
        "encoder_provenance_match": True,
        "translation_input_hashes_match": True,
        "metadata_reconstruction_match": metadata_exact,
        "variable_map_dense": dense,
        "variable_map_exact": var_map_exact,
        "opb_header_counts_exact": header_counts,
        "constraint_multiset_exact": constraints_exact,
        "coordinate_canaries_pass": canaries_pass,
    }
    return {
        "schema_version": "front_clear_pb_translation_gate_v2",
        "semantics": SEMANTICS,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "generator_git_revision": revision,
        "encoder_source": encoder_source,
        "encoder_git_snapshot": encoder_git_snapshot,
        "gate_source": _file_record(Path(__file__), project_root),
        "git_snapshot": _git_snapshot(project_root),
        "translation_inputs": translation_inputs,
        "checks": checks,
        "coordinate_canaries": canaries,
        "input_sha256": bound_hashes,
        "counts": {
            "variables": len(expected["variables"]),
            "expected_constraints": expected_constraint_count,
            "actual_constraints": parsed["constraint_count"],
            "expected_equal_constraints": expected["equal_count"],
            "actual_equal_constraints": parsed["equal_count"],
        },
        "constraint_multiset_sha256": {
            "expected": expected_hash,
            "actual": actual_hash,
        },
        "constraint_diff": _multiset_diff(expected["constraints"], parsed["constraints"]),
        "proof_status": "translation_only_no_unsat_or_proof_claim",
        "historical_v1_status": HISTORICAL_V1_STATUS,
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
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing gate output: {args.output}")
    try:
        report = verify(
            opb_path=args.opb.resolve(),
            meta_path=args.meta.resolve(),
            var_map_path=args.var_map.resolve(),
            project_root=args.project_root.resolve(),
        )
    except Exception as exc:
        report = {
            "schema_version": "front_clear_pb_translation_gate_v2",
            "semantics": SEMANTICS,
            "status": "FAIL",
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "proof_status": "translation_only_no_unsat_or_proof_claim",
        }
    _exclusive_json(args.output, report)
    print(json.dumps({"status": report["status"], "output": str(args.output.resolve())}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
