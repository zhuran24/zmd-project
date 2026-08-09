"""Materialize one hash-pinned reduced-backbone placement result.

This research adapter translates the reduced worker's 219 anonymous
manufacturing poses into all 266 strict required instance IDs, adds the fixed
boundary/core poses and 35 power poles, and replays the result through the
production placement, binding, and routing-precheck APIs.  It deliberately
stops before constructing a routing grid or router model.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from typing import Any


PREFIX = "docs.research.witness_constructor_20260717.07_routing_aware"
PROJECT_ROOT = Path(__file__).resolve().parents[4]

fixed_router = importlib.import_module(f"{PREFIX}.fixed_geometry_router")
geometry = importlib.import_module(f"{PREFIX}.geometry")
shelf = importlib.import_module(f"{PREFIX}.shelf_constructor")
strict_contract = importlib.import_module(f"{PREFIX}.strict_contract")

RESULT_SCHEMA_VERSION = "reduced_backbone_front_result.v1"
RESULT_ACCEPTED_STATUS = "PLACEMENT_ACCEPTED_BY_LOCAL_AUDITS"
RELABEL_SCHEMA_VERSION = "reduced_nine_signature_relabel.v1"
RELABEL_READY_STATUS = "NINE_SIGNATURE_FRONT_CLEAR_GEOMETRY_READY"
STATIC_EVALUATOR_SHA256 = "b600c03b91175c22d550e38db4e0acc8fab0cc3a0c269872696ae7319f02fe55"
EXPECTED_REQUIRED_COUNTS = {
    "boundary_storage_port": 46,
    "manufacturing_3x3": 132,
    "manufacturing_5x5": 49,
    "manufacturing_6x4": 38,
    "protocol_core": 1,
}
MANUFACTURING_TEMPLATES = frozenset(
    {"manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4"}
)
EXPECTED_MANUFACTURING_COUNT = 219
EXPECTED_POLE_COUNT = 35
EXPECTED_MANUFACTURING_ACTIVE_PORTS = 574
EXPECTED_FIXED_ACTIVE_PORTS = 54
EXPECTED_TOTAL_ACTIVE_INCIDENCES = 628
FIXED_CORE_ANCHOR = (60, 60)
FIXED_BOUNDARY_PATTERN = geometry.BoundaryPattern(69, 0)
PROTECTED_RECTANGLE = geometry.Rect(7, 36, 6, 7)
PROTECTED_RECTANGLE_SHAPE = (6, 7)
BACKBONE_VERTICAL_LANES = (1, 12, 24, 36, 48, 59)
BACKBONE_HORIZONTAL_LANES = (1, 36, 59)
BACKBONE_CELL_COUNT = 622
FIXED_POLE_AXIS = (5, 17, 29, 41, 53, 65)
FIXED_POLE_ANCHORS = tuple(
    sorted(
        (
            (x, y)
            for x in FIXED_POLE_AXIS
            for y in FIXED_POLE_AXIS
            if (x, y) != (65, 65)
        ),
        key=lambda anchor: (anchor[1], anchor[0]),
    )
)

EXPECTED_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "plan",
        "input_hashes",
        "operation_expansion",
        "selected_poles",
        "fixed_geometry",
        "attempts",
        "cgroup_telemetry",
        "placements",
        "active_incidences",
        "active_unique_cells",
        "post_audits",
        "body_hint_audit",
        "protected_selection_audit",
    }
)
EXPECTED_FIXED_GEOMETRY_FIELDS = frozenset(
    {
        "core_anchor",
        "boundary_pattern",
        "protected_rectangle",
        "backbone_vertical_lane_levels",
        "backbone_horizontal_lane_levels",
        "backbone_cells",
    }
)
EXPECTED_PLACEMENT_FIELDS = frozenset(
    {
        "signature",
        "operation_id",
        "template",
        "pose_index",
        "pose_idx",
        "anchor",
        "mode",
        "candidate_mode",
        "active_ports",
    }
)
EXPECTED_ACTIVE_PORT_FIELDS = frozenset(
    {
        "port_id",
        "kind",
        "direction",
        "access",
        "component_kind",
        "component_side",
    }
)
EXPECTED_RELABEL_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "claim_boundary",
        "source",
        "fixed_geometry",
        "manufacturing_count",
        "manufacturing_body_cells",
        "manufacturing_active_incidences",
        "total_active_incidences_with_fixed",
        "signature_counts",
        "decomposition_audit",
        "clear_front_capacity_histograms",
        "placements",
    }
)
EXPECTED_RELABEL_PLACEMENT_FIELDS = frozenset(
    {
        "signature",
        "operation_id",
        "template",
        "pose_index",
        "anchor",
        "mode",
        "candidate_mode",
        "active_ports",
        "component",
    }
)
OPPOSITE_DIRECTION = {"N": "S", "E": "W", "S": "N", "W": "E"}


class ReducedGeometryMaterializerError(ValueError):
    """Stable fail-closed error raised by the reduced-result adapter."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class OperationInfo:
    operation_id: str
    template: str
    signature: str
    input_need: int
    output_need: int
    input_commodities: tuple[str, ...]
    output_commodities: tuple[str, ...]
    count: int


@dataclass(frozen=True)
class PoseInfo:
    pose_idx: int
    candidate_mode: str
    body_cells: frozenset[tuple[int, int]]
    input_front_cells: tuple[tuple[int, int], ...]
    output_front_cells: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ManufacturingPlacement:
    signature: str
    operation_id: str
    template: str
    pose_idx: int
    mode: str
    candidate_mode: str
    anchor: tuple[int, int]
    active_ports: tuple[tuple[str, str], ...]
    active_cells: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ExplicitPlacementBundle:
    """Normalized explicit geometry consumed by the strict materializer core."""

    placements: tuple[Mapping[str, Any], ...]
    pole_anchors: tuple[tuple[int, int], ...]
    core_anchor: tuple[int, int]
    boundary_pattern: tuple[int, int]
    protected_rectangle: tuple[int, int, int, int]
    backbone_vertical_lanes: tuple[int, ...]
    backbone_horizontal_lanes: tuple[int, ...]
    backbone_cell_count: int
    declared_operation_expansion: Mapping[str, Any] | None = None
    declared_signature_counts: Mapping[str, Any] | None = None


def _fail(code: str, message: str) -> None:
    raise ReducedGeometryMaterializerError(code, message)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail("MALFORMED_OBJECT", f"{label} must be an object with string keys")
    return value


def _sequence(value: object, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail("MALFORMED_ARRAY", f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        _fail("MALFORMED_STRING", f"{label} must be a nonempty string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("MALFORMED_INTEGER", f"{label} must be a literal integer")
    return int(value)


def _cell(value: object, label: str) -> tuple[int, int]:
    pair = _sequence(value, label)
    if len(pair) != 2:
        _fail("MALFORMED_CELL", f"{label} must have length two")
    return _integer(pair[0], f"{label}[0]"), _integer(pair[1], f"{label}[1]")


def _json_copy(value: object, label: str) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        _fail("NON_JSON_VALUE", f"{label}: {exc}")


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if set(value) != expected:
        _fail(
            "RESULT_SCHEMA",
            f"{label} fields differ; missing={sorted(expected - set(value))}, "
            f"extra={sorted(set(value) - expected)}",
        )


def _integer_tuple(value: object, label: str) -> tuple[int, ...]:
    return tuple(_integer(item, f"{label}[{index}]") for index, item in enumerate(_sequence(value, label)))


def _explicit_protected_rectangle(value: object) -> geometry.Rect:
    rectangle = _integer_tuple(value, "protected_rectangle")
    if len(rectangle) != 4:
        _fail("EXPLICIT_PROTECTED_RECTANGLE", "expected x, y, width, height")
    try:
        parsed = geometry.Rect(*rectangle)
    except geometry.GeometryContractError as exc:
        _fail("EXPLICIT_PROTECTED_RECTANGLE", str(exc))
    if (parsed.width, parsed.height) != PROTECTED_RECTANGLE_SHAPE:
        _fail(
            "EXPLICIT_PROTECTED_RECTANGLE",
            f"expected shape={PROTECTED_RECTANGLE_SHAPE!r}, observed={(parsed.width, parsed.height)!r}",
        )
    if not parsed.in_grid():
        _fail("EXPLICIT_PROTECTED_RECTANGLE", "rectangle is outside the 70x70 grid")
    return parsed


def _validate_result_envelope(
    root_value: object,
    *,
    snapshot: Any,
    telemetry_validator: Callable[[object], None],
) -> tuple[Mapping[str, Any], tuple[tuple[int, int], ...]]:
    root = _mapping(root_value, "reduced_result")
    _exact_fields(root, EXPECTED_RESULT_FIELDS, "reduced_result")
    if root.get("schema_version") != RESULT_SCHEMA_VERSION:
        _fail("RESULT_SCHEMA_VERSION", repr(root.get("schema_version")))
    if root.get("status") != RESULT_ACCEPTED_STATUS:
        _fail("RESULT_NOT_ACCEPTED", repr(root.get("status")))

    _mapping(root.get("plan"), "plan")
    _mapping(root.get("operation_expansion"), "operation_expansion")
    _sequence(root.get("attempts"), "attempts")
    _mapping(root.get("body_hint_audit"), "body_hint_audit")
    protected_audit = _mapping(root.get("protected_selection_audit"), "protected_selection_audit")
    if _integer_tuple(protected_audit.get("rectangle"), "protected_selection_audit.rectangle") != (
        PROTECTED_RECTANGLE.x,
        PROTECTED_RECTANGLE.y,
        PROTECTED_RECTANGLE.width,
        PROTECTED_RECTANGLE.height,
    ):
        _fail("RESULT_PROTECTED_RECTANGLE", "protected-selection rectangle differs")
    if _integer(
        protected_audit.get("fixed_body_collision_cells"),
        "protected_selection_audit.fixed_body_collision_cells",
    ) != 0:
        _fail("RESULT_PROTECTED_RECTANGLE", "protected rectangle collides with fixed body")

    hashes = _mapping(root.get("input_hashes"), "input_hashes")
    expected_hash_keys = {"strict_instance", "candidate_placements", "static_evaluator"}
    if set(hashes) != expected_hash_keys:
        _fail("RESULT_INPUT_HASH_FIELDS", "reduced result must carry exactly three input hashes")
    snapshot_hashes = _mapping(getattr(snapshot, "hashes", None), "snapshot.hashes")
    expected_hashes = {
        "strict_instance": _string(snapshot_hashes.get("strict_instance"), "snapshot.hashes.strict_instance"),
        "candidate_placements": _string(
            snapshot_hashes.get("candidate_poses"), "snapshot.hashes.candidate_poses"
        ),
        "static_evaluator": STATIC_EVALUATOR_SHA256,
    }
    observed_hashes = {key: _string(value, f"input_hashes.{key}") for key, value in hashes.items()}
    if observed_hashes != expected_hashes:
        _fail("RESULT_INPUT_DRIFT", f"expected={expected_hashes!r}, observed={observed_hashes!r}")

    fixed = _mapping(root.get("fixed_geometry"), "fixed_geometry")
    _exact_fields(fixed, EXPECTED_FIXED_GEOMETRY_FIELDS, "fixed_geometry")
    boundary = _mapping(fixed.get("boundary_pattern"), "fixed_geometry.boundary_pattern")
    if set(boundary) != {"left_gap", "bottom_gap"}:
        _fail("RESULT_FIXED_GEOMETRY", "boundary_pattern fields differ")
    observed_fixed = {
        "core_anchor": _cell(fixed.get("core_anchor"), "fixed_geometry.core_anchor"),
        "boundary_pattern": (
            _integer(boundary.get("left_gap"), "fixed_geometry.boundary_pattern.left_gap"),
            _integer(boundary.get("bottom_gap"), "fixed_geometry.boundary_pattern.bottom_gap"),
        ),
        "protected_rectangle": _integer_tuple(
            fixed.get("protected_rectangle"), "fixed_geometry.protected_rectangle"
        ),
        "backbone_vertical_lane_levels": _integer_tuple(
            fixed.get("backbone_vertical_lane_levels"), "fixed_geometry.backbone_vertical_lane_levels"
        ),
        "backbone_horizontal_lane_levels": _integer_tuple(
            fixed.get("backbone_horizontal_lane_levels"), "fixed_geometry.backbone_horizontal_lane_levels"
        ),
        "backbone_cells": _integer(fixed.get("backbone_cells"), "fixed_geometry.backbone_cells"),
    }
    expected_fixed = {
        "core_anchor": FIXED_CORE_ANCHOR,
        "boundary_pattern": (FIXED_BOUNDARY_PATTERN.left_gap, FIXED_BOUNDARY_PATTERN.bottom_gap),
        "protected_rectangle": (
            PROTECTED_RECTANGLE.x,
            PROTECTED_RECTANGLE.y,
            PROTECTED_RECTANGLE.width,
            PROTECTED_RECTANGLE.height,
        ),
        "backbone_vertical_lane_levels": BACKBONE_VERTICAL_LANES,
        "backbone_horizontal_lane_levels": BACKBONE_HORIZONTAL_LANES,
        "backbone_cells": BACKBONE_CELL_COUNT,
    }
    if observed_fixed != expected_fixed:
        _fail("RESULT_FIXED_GEOMETRY", f"expected={expected_fixed!r}, observed={observed_fixed!r}")

    raw_placements = _sequence(root.get("placements"), "placements")
    if len(raw_placements) != EXPECTED_MANUFACTURING_COUNT:
        _fail("RESULT_PLACEMENT_COUNT", f"expected 219, observed {len(raw_placements)}")
    if _integer(root.get("active_incidences"), "active_incidences") != EXPECTED_TOTAL_ACTIVE_INCIDENCES:
        _fail("RESULT_ACTIVE_INCIDENCES", repr(root.get("active_incidences")))
    active_unique = _integer(root.get("active_unique_cells"), "active_unique_cells")
    if not 0 <= active_unique <= EXPECTED_TOTAL_ACTIVE_INCIDENCES:
        _fail("RESULT_ACTIVE_UNIQUE_CELLS", repr(active_unique))

    audits = _mapping(root.get("post_audits"), "post_audits")
    expected_audits = {"local_component", "free_component", "fixed_power"}
    if set(audits) != expected_audits:
        _fail("RESULT_POST_AUDITS", "post-audit names differ")
    for name in sorted(expected_audits):
        audit = _mapping(audits[name], f"post_audits.{name}")
        if audit.get("passed") is not True:
            _fail("RESULT_POST_AUDIT_REJECTED", name)

    telemetry = _mapping(root.get("cgroup_telemetry"), "cgroup_telemetry")
    try:
        telemetry_validator(telemetry)
    except Exception as exc:  # noqa: BLE001 - fail-closed dependency boundary
        _fail("RESULT_CGROUP_TELEMETRY", f"{type(exc).__name__}: {exc}")

    poles = tuple(
        _cell(value, f"selected_poles[{index}]")
        for index, value in enumerate(_sequence(root.get("selected_poles"), "selected_poles"))
    )
    if len(poles) != EXPECTED_POLE_COUNT:
        _fail("RESULT_POLE_COUNT", f"expected 35, observed {len(poles)}")
    if len(set(poles)) != len(poles):
        _fail("RESULT_DUPLICATE_POLE", "selected pole anchors must be unique")
    return root, tuple(sorted(poles, key=lambda anchor: (anchor[1], anchor[0])))


def _validate_relabel_result_envelope(root_value: object) -> ExplicitPlacementBundle:
    root = _mapping(root_value, "relabel_result")
    _exact_fields(root, EXPECTED_RELABEL_FIELDS, "relabel_result")
    if root.get("schema_version") != RELABEL_SCHEMA_VERSION:
        _fail("RESULT_SCHEMA_VERSION", repr(root.get("schema_version")))
    if root.get("status") != RELABEL_READY_STATUS:
        _fail("RESULT_NOT_READY", repr(root.get("status")))
    _string(root.get("claim_boundary"), "claim_boundary")
    source = _mapping(root.get("source"), "source")
    if set(source) != {"path", "sha256"}:
        _fail("RESULT_SOURCE_FIELDS", "relabel source must contain path and sha256")
    _string(source.get("path"), "source.path")
    source_sha256 = _string(source.get("sha256"), "source.sha256")
    if len(source_sha256) != 64 or any(character not in "0123456789abcdef" for character in source_sha256):
        _fail("RESULT_SOURCE_HASH", repr(source_sha256))

    fixed = _mapping(root.get("fixed_geometry"), "fixed_geometry")
    if set(fixed) != {"backbone_cells", "fixed_terminal_count", "pole_count", "protected"}:
        _fail("RESULT_FIXED_GEOMETRY", "relabel fixed-geometry fields differ")
    if _integer(fixed.get("backbone_cells"), "fixed_geometry.backbone_cells") != BACKBONE_CELL_COUNT:
        _fail("RESULT_FIXED_GEOMETRY", "backbone cell count differs")
    if _integer(fixed.get("fixed_terminal_count"), "fixed_geometry.fixed_terminal_count") != EXPECTED_FIXED_ACTIVE_PORTS:
        _fail("RESULT_FIXED_GEOMETRY", "fixed terminal count differs")
    if _integer(fixed.get("pole_count"), "fixed_geometry.pole_count") != EXPECTED_POLE_COUNT:
        _fail("RESULT_FIXED_GEOMETRY", "pole count differs")
    protected = _integer_tuple(fixed.get("protected"), "fixed_geometry.protected")
    if protected != (
        PROTECTED_RECTANGLE.x,
        PROTECTED_RECTANGLE.y,
        PROTECTED_RECTANGLE.width,
        PROTECTED_RECTANGLE.height,
    ):
        _fail("RESULT_FIXED_GEOMETRY", "protected rectangle differs")

    expected_counts = {
        "manufacturing_count": EXPECTED_MANUFACTURING_COUNT,
        "manufacturing_body_cells": 3325,
        "manufacturing_active_incidences": EXPECTED_MANUFACTURING_ACTIVE_PORTS,
        "total_active_incidences_with_fixed": EXPECTED_TOTAL_ACTIVE_INCIDENCES,
    }
    for field, expected in expected_counts.items():
        if _integer(root.get(field), field) != expected:
            _fail("RESULT_COUNT", f"{field} differs from {expected}")
    declared_signature_counts = _mapping(root.get("signature_counts"), "signature_counts")
    _mapping(root.get("decomposition_audit"), "decomposition_audit")
    _mapping(root.get("clear_front_capacity_histograms"), "clear_front_capacity_histograms")

    raw_placements = _sequence(root.get("placements"), "placements")
    if len(raw_placements) != EXPECTED_MANUFACTURING_COUNT:
        _fail("RESULT_PLACEMENT_COUNT", f"expected 219, observed {len(raw_placements)}")
    normalized: list[Mapping[str, Any]] = []
    for index, raw_row in enumerate(raw_placements):
        row = _mapping(raw_row, f"placements[{index}]")
        _exact_fields(row, EXPECTED_RELABEL_PLACEMENT_FIELDS, f"placements[{index}]")
        component = _integer(row.get("component"), f"placements[{index}].component")
        if component < 0:
            _fail("PLACEMENT_COMPONENT", f"placements[{index}]")
        pose_index = _integer(row.get("pose_index"), f"placements[{index}].pose_index")
        normalized.append(
            {
                "signature": row.get("signature"),
                "operation_id": row.get("operation_id"),
                "template": row.get("template"),
                "pose_index": pose_index,
                "pose_idx": pose_index,
                "anchor": row.get("anchor"),
                "mode": row.get("mode"),
                "candidate_mode": row.get("candidate_mode"),
                "active_ports": row.get("active_ports"),
            }
        )
    return ExplicitPlacementBundle(
        placements=tuple(normalized),
        pole_anchors=FIXED_POLE_ANCHORS,
        core_anchor=FIXED_CORE_ANCHOR,
        boundary_pattern=(FIXED_BOUNDARY_PATTERN.left_gap, FIXED_BOUNDARY_PATTERN.bottom_gap),
        protected_rectangle=(
            PROTECTED_RECTANGLE.x,
            PROTECTED_RECTANGLE.y,
            PROTECTED_RECTANGLE.width,
            PROTECTED_RECTANGLE.height,
        ),
        backbone_vertical_lanes=BACKBONE_VERTICAL_LANES,
        backbone_horizontal_lanes=BACKBONE_HORIZONTAL_LANES,
        backbone_cell_count=BACKBONE_CELL_COUNT,
        declared_signature_counts=declared_signature_counts,
    )


def _normalize_result_source(
    result_value: object,
    *,
    snapshot: Any,
    telemetry_validator: Callable[[object], None],
) -> ExplicitPlacementBundle:
    root = _mapping(result_value, "result")
    schema = root.get("schema_version")
    if schema == RESULT_SCHEMA_VERSION:
        worker_root, poles = _validate_result_envelope(
            root,
            snapshot=snapshot,
            telemetry_validator=telemetry_validator,
        )
        return ExplicitPlacementBundle(
            placements=tuple(
                _mapping(value, f"placements[{index}]")
                for index, value in enumerate(_sequence(worker_root.get("placements"), "placements"))
            ),
            pole_anchors=poles,
            core_anchor=FIXED_CORE_ANCHOR,
            boundary_pattern=(FIXED_BOUNDARY_PATTERN.left_gap, FIXED_BOUNDARY_PATTERN.bottom_gap),
            protected_rectangle=(
                PROTECTED_RECTANGLE.x,
                PROTECTED_RECTANGLE.y,
                PROTECTED_RECTANGLE.width,
                PROTECTED_RECTANGLE.height,
            ),
            backbone_vertical_lanes=BACKBONE_VERTICAL_LANES,
            backbone_horizontal_lanes=BACKBONE_HORIZONTAL_LANES,
            backbone_cell_count=BACKBONE_CELL_COUNT,
            declared_operation_expansion=_mapping(
                worker_root.get("operation_expansion"), "operation_expansion"
            ),
        )
    if schema == RELABEL_SCHEMA_VERSION:
        return _validate_relabel_result_envelope(root)
    _fail("RESULT_SCHEMA_VERSION", repr(schema))


def _strict_modes(instance: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    modes: dict[tuple[str, str], Mapping[str, Any]] = {}
    templates = _mapping(instance.get("facility_templates"), "facility_templates")
    for template_id, raw_template in templates.items():
        template = _mapping(raw_template, f"facility_templates.{template_id}")
        for raw_mode in _sequence(template.get("modes"), f"facility_templates.{template_id}.modes"):
            mode = _mapping(raw_mode, f"facility_templates.{template_id}.mode")
            mode_id = _string(mode.get("id"), f"facility_templates.{template_id}.mode.id")
            key = (_string(template_id, "facility template id"), mode_id)
            if key in modes:
                _fail("DUPLICATE_STRICT_MODE", repr(key))
            modes[key] = mode
    return modes


def _operation_contract(
    instance: Mapping[str, Any],
) -> tuple[
    dict[str, OperationInfo],
    Counter[tuple[str, str]],
    dict[str, list[str]],
]:
    operations: dict[str, OperationInfo] = {}
    expected_pairs: Counter[tuple[str, str]] = Counter()
    expansion: dict[str, list[str]] = defaultdict(list)
    total_count = 0
    total_active_ports = 0
    commodity_values = [
        _string(value, f"commodities[{index}]")
        for index, value in enumerate(_sequence(instance.get("commodities"), "commodities"))
    ]
    if not commodity_values or len(commodity_values) != len(set(commodity_values)):
        _fail("OPERATION_COMMODITY_SET", "strict commodities must be nonempty and unique")
    strict_commodities = frozenset(commodity_values)
    for index, raw_group in enumerate(_sequence(instance.get("operation_groups"), "operation_groups")):
        group = _mapping(raw_group, f"operation_groups[{index}]")
        operation_id = _string(group.get("id"), f"operation_groups[{index}].id")
        if operation_id in operations:
            _fail("DUPLICATE_OPERATION", operation_id)
        template = _string(group.get("template"), f"operation_groups[{index}].template")
        if template not in MANUFACTURING_TEMPLATES:
            _fail("UNKNOWN_OPERATION_TEMPLATE", template)
        count = _integer(group.get("count"), f"operation_groups[{index}].count")
        if count <= 0:
            _fail("INVALID_OPERATION_COUNT", operation_id)
        needs = _mapping(group.get("port_needs"), f"operation_groups[{index}].port_needs")
        if set(needs) != {"inputs", "outputs"}:
            _fail("OPERATION_PORT_NEEDS", operation_id)

        totals: dict[str, int] = {}
        expanded_needs: dict[str, tuple[str, ...]] = {}
        for kind in ("inputs", "outputs"):
            commodity_needs = _mapping(needs.get(kind), f"operation_groups[{index}].port_needs.{kind}")
            expanded: list[str] = []
            for raw_commodity in sorted(commodity_needs):
                commodity = _string(raw_commodity, f"{operation_id}.{kind} commodity")
                if commodity not in strict_commodities:
                    _fail("UNKNOWN_OPERATION_COMMODITY", f"{operation_id}/{commodity}")
                count_value = _integer(
                    commodity_needs[raw_commodity], f"{operation_id}.{kind}.{commodity}"
                )
                if count_value <= 0:
                    _fail("NONPOSITIVE_OPERATION_NEED", f"{operation_id}/{kind}/{commodity}")
                expanded.extend([commodity] * count_value)
            totals[kind] = len(expanded)
            expanded_needs[kind] = tuple(expanded)
        signature = f"{template}__i{totals['inputs']}__o{totals['outputs']}"
        info = OperationInfo(
            operation_id=operation_id,
            template=template,
            signature=signature,
            input_need=totals["inputs"],
            output_need=totals["outputs"],
            input_commodities=expanded_needs["inputs"],
            output_commodities=expanded_needs["outputs"],
            count=count,
        )
        operations[operation_id] = info
        expected_pairs[(signature, operation_id)] += count
        expansion[signature].extend([operation_id] * count)
        total_count += count
        total_active_ports += count * (info.input_need + info.output_need)

    if len(operations) != 17 or total_count != EXPECTED_MANUFACTURING_COUNT:
        _fail("OPERATION_CONTRACT_COUNT", f"operations={len(operations)}, placements={total_count}")
    if len(expansion) != 9:
        _fail("OPERATION_SIGNATURE_COUNT", f"expected 9, observed {len(expansion)}")
    if total_active_ports != EXPECTED_MANUFACTURING_ACTIVE_PORTS:
        _fail("OPERATION_ACTIVE_PORT_COUNT", f"expected 574, observed {total_active_ports}")
    return operations, expected_pairs, dict(expansion)


def _candidate_pose_index(
    facility_pools: Mapping[str, Any],
) -> dict[tuple[str, str, int, int], tuple[int, Mapping[str, Any], str]]:
    result: dict[tuple[str, str, int, int], tuple[int, Mapping[str, Any], str]] = {}
    for candidate_template, raw_pool in facility_pools.items():
        candidate_template_id = _string(candidate_template, "candidate template id")
        strict_template = strict_contract.CANDIDATE_TEMPLATE_TO_STRICT.get(candidate_template_id)
        if strict_template is None:
            _fail("UNKNOWN_CANDIDATE_TEMPLATE", candidate_template_id)
        for pose_idx, raw_pose in enumerate(_sequence(raw_pool, f"facility_pools.{candidate_template_id}")):
            pose = _mapping(raw_pose, f"facility_pools.{candidate_template_id}[{pose_idx}]")
            params = _mapping(pose.get("pose_params"), f"facility_pools.{candidate_template_id}[{pose_idx}].pose_params")
            candidate_mode = _string(params.get("port_mode"), f"candidate pose {pose_idx} port_mode")
            strict_mode = strict_contract.CANDIDATE_MODE_TO_STRICT.get(candidate_mode)
            if strict_mode is None:
                _fail("UNKNOWN_CANDIDATE_MODE", candidate_mode)
            anchor_map = _mapping(pose.get("anchor"), f"candidate pose {pose_idx} anchor")
            anchor = (
                _integer(anchor_map.get("x"), f"candidate pose {pose_idx} anchor.x"),
                _integer(anchor_map.get("y"), f"candidate pose {pose_idx} anchor.y"),
            )
            key = (str(strict_template), str(strict_mode), anchor[0], anchor[1])
            if key in result:
                _fail("DUPLICATE_CANDIDATE_POSE", repr(key))
            result[key] = (pose_idx, pose, candidate_mode)
    return result


def _decode_pose(
    key: tuple[str, str, int, int],
    *,
    pose_index: Mapping[tuple[str, str, int, int], tuple[int, Mapping[str, Any], str]],
    strict_modes: Mapping[tuple[str, str], Mapping[str, Any]],
    cache: dict[tuple[str, str, int, int], PoseInfo],
) -> PoseInfo:
    cached = cache.get(key)
    if cached is not None:
        return cached
    candidate = pose_index.get(key)
    if candidate is None:
        _fail("POSE_NOT_IN_CURRENT_POOL", repr(key))
    mode = strict_modes.get((key[0], key[1]))
    if mode is None:
        _fail("UNKNOWN_STRICT_MODE", repr((key[0], key[1])))
    pose_idx, raw_pose, candidate_mode = candidate
    strict_geometry = geometry.strict_mode_geometry(mode, (key[2], key[3]))
    candidate_geometry = geometry.candidate_pose_geometry(raw_pose)
    if (
        strict_geometry.body_cells != candidate_geometry.body_cells
        or set(strict_geometry.input_front_cells) != set(candidate_geometry.input_front_cells)
        or set(strict_geometry.output_front_cells) != set(candidate_geometry.output_front_cells)
    ):
        _fail("STRICT_CANDIDATE_GEOMETRY_MISMATCH", repr(key))
    decoded = PoseInfo(
        pose_idx=pose_idx,
        candidate_mode=candidate_mode,
        body_cells=frozenset(strict_geometry.body_cells),
        input_front_cells=tuple(strict_geometry.input_front_cells),
        output_front_cells=tuple(strict_geometry.output_front_cells),
    )
    cache[key] = decoded
    return decoded


def _parse_manufacturing_placements(
    rows_value: object,
    *,
    operations: Mapping[str, OperationInfo],
    expected_pairs: Counter[tuple[str, str]],
    pose_index: Mapping[tuple[str, str, int, int], tuple[int, Mapping[str, Any], str]],
    strict_modes: Mapping[tuple[str, str], Mapping[str, Any]],
    pose_cache: dict[tuple[str, str, int, int], PoseInfo],
) -> tuple[ManufacturingPlacement, ...]:
    parsed: list[ManufacturingPlacement] = []
    observed_pairs: Counter[tuple[str, str]] = Counter()
    physical_poses: set[tuple[str, int]] = set()
    active_port_count = 0
    rows = _sequence(rows_value, "placements")
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row, f"placements[{index}]")
        _exact_fields(row, EXPECTED_PLACEMENT_FIELDS, f"placements[{index}]")
        signature = _string(row.get("signature"), f"placements[{index}].signature")
        operation_id = _string(row.get("operation_id"), f"placements[{index}].operation_id")
        template = _string(row.get("template"), f"placements[{index}].template")
        mode = _string(row.get("mode"), f"placements[{index}].mode")
        candidate_mode = _string(row.get("candidate_mode"), f"placements[{index}].candidate_mode")
        anchor = _cell(row.get("anchor"), f"placements[{index}].anchor")
        pose_idx = _integer(row.get("pose_idx"), f"placements[{index}].pose_idx")
        pose_index_value = _integer(row.get("pose_index"), f"placements[{index}].pose_index")
        if pose_idx < 0 or pose_index_value != pose_idx:
            _fail("PLACEMENT_POSE_INDEX", f"placements[{index}] has inconsistent pose indices")

        operation = operations.get(operation_id)
        if operation is None:
            _fail("PLACEMENT_UNKNOWN_OPERATION", operation_id)
        if operation.template != template or operation.signature != signature:
            _fail("PLACEMENT_OPERATION_MISMATCH", f"placements[{index}]")
        key = (template, mode, anchor[0], anchor[1])
        pose = _decode_pose(
            key,
            pose_index=pose_index,
            strict_modes=strict_modes,
            cache=pose_cache,
        )
        if pose.pose_idx != pose_idx or pose.candidate_mode != candidate_mode:
            _fail("PLACEMENT_CANDIDATE_MISMATCH", f"placements[{index}]")
        if strict_contract.CANDIDATE_MODE_TO_STRICT.get(candidate_mode) != mode:
            _fail("PLACEMENT_MODE_MAPPING", f"placements[{index}]")
        physical_key = (template, pose_idx)
        if physical_key in physical_poses:
            _fail("PLACEMENT_POSE_REUSED", repr(physical_key))
        physical_poses.add(physical_key)

        strict_mode = strict_modes[(template, mode)]
        ports: dict[str, Mapping[str, Any]] = {}
        for raw_port in _sequence(strict_mode.get("ports"), f"{template}/{mode}.ports"):
            port = _mapping(raw_port, f"{template}/{mode}.port")
            port_id = _string(port.get("id"), f"{template}/{mode}.port.id")
            if port_id in ports:
                _fail("DUPLICATE_STRICT_PORT", f"{template}/{mode}/{port_id}")
            ports[port_id] = port

        active_ids: set[str] = set()
        active_ports: list[tuple[str, str]] = []
        active_cells: list[tuple[int, int]] = []
        kinds: Counter[str] = Counter()
        for port_index, raw_active in enumerate(_sequence(row.get("active_ports"), f"placements[{index}].active_ports")):
            active = _mapping(raw_active, f"placements[{index}].active_ports[{port_index}]")
            _exact_fields(active, EXPECTED_ACTIVE_PORT_FIELDS, f"placements[{index}].active_ports[{port_index}]")
            port_id = _string(active.get("port_id"), f"placements[{index}].active_ports[{port_index}].port_id")
            if port_id in active_ids:
                _fail("PLACEMENT_ACTIVE_PORT_REUSED", f"placements[{index}]/{port_id}")
            active_ids.add(port_id)
            port = ports.get(port_id)
            if port is None:
                _fail("PLACEMENT_UNKNOWN_ACTIVE_PORT", f"placements[{index}]/{port_id}")
            kind = _string(active.get("kind"), f"placements[{index}].active_ports[{port_index}].kind")
            direction = _string(
                active.get("direction"), f"placements[{index}].active_ports[{port_index}].direction"
            )
            if kind not in {"input", "output"} or direction not in OPPOSITE_DIRECTION:
                _fail("PLACEMENT_ACTIVE_PORT_SEMANTICS", f"placements[{index}]/{port_id}")
            if port.get("kind") != kind or port.get("direction") != direction:
                _fail("PLACEMENT_ACTIVE_PORT_SEMANTICS", f"placements[{index}]/{port_id}")
            access = _cell(active.get("access"), f"placements[{index}].active_ports[{port_index}].access")
            expected_access = strict_contract.strict_port_access_cell(anchor, port)
            expected_component_kind = "input" if kind == "output" else "output"
            if (
                access != expected_access
                or active.get("component_kind") != expected_component_kind
                or active.get("component_side") != OPPOSITE_DIRECTION[direction]
            ):
                _fail("PLACEMENT_ACTIVE_ATTACHMENT", f"placements[{index}]/{port_id}")
            kinds[kind] += 1
            active_ports.append((port_id, kind))
            active_cells.append(access)

        if kinds != Counter({"input": operation.input_need, "output": operation.output_need}):
            _fail("PLACEMENT_ACTIVE_PORT_COUNT", f"placements[{index}]/{operation_id}")
        active_port_count += len(active_cells)
        observed_pairs[(signature, operation_id)] += 1
        parsed.append(
            ManufacturingPlacement(
                signature=signature,
                operation_id=operation_id,
                template=template,
                pose_idx=pose_idx,
                mode=mode,
                candidate_mode=candidate_mode,
                anchor=anchor,
                active_ports=tuple(active_ports),
                active_cells=tuple(active_cells),
            )
        )

    if observed_pairs != expected_pairs:
        missing = expected_pairs - observed_pairs
        extra = observed_pairs - expected_pairs
        _fail("PLACEMENT_OPERATION_MULTIPLICITY", f"missing={dict(missing)!r}, extra={dict(extra)!r}")
    if active_port_count != EXPECTED_MANUFACTURING_ACTIVE_PORTS:
        _fail("PLACEMENT_ACTIVE_PORT_TOTAL", f"expected 574, observed {active_port_count}")
    return tuple(parsed)


def _validate_declared_expansion(value: object, expected: Mapping[str, list[str]]) -> None:
    raw = _mapping(value, "operation_expansion")
    observed: dict[str, list[str]] = {}
    for signature, raw_operations in raw.items():
        signature_id = _string(signature, "operation_expansion signature")
        observed[signature_id] = [
            _string(value, f"operation_expansion.{signature_id}[{index}]")
            for index, value in enumerate(_sequence(raw_operations, f"operation_expansion.{signature_id}"))
        ]
    if observed != dict(expected):
        _fail("RESULT_OPERATION_EXPANSION", "declared expansion differs from strict recomputation")


def _validate_declared_signature_counts(value: object, operations: Mapping[str, OperationInfo]) -> None:
    raw = _mapping(value, "signature_counts")
    observed = {
        _string(signature, "signature_counts signature"): _integer(count, f"signature_counts.{signature}")
        for signature, count in raw.items()
    }
    expected: Counter[str] = Counter()
    for operation in operations.values():
        expected[operation.signature] += operation.count
    if observed != dict(expected):
        _fail("RESULT_SIGNATURE_COUNTS", f"expected={dict(expected)!r}, observed={observed!r}")


def _required_rows(instance: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows = tuple(
        _mapping(value, f"required_instances[{index}]")
        for index, value in enumerate(_sequence(instance.get("required_instances"), "required_instances"))
    )
    ids = [_string(row.get("id"), "required.id") for row in rows]
    if len(rows) != 266 or len(ids) != len(set(ids)):
        _fail("REQUIRED_ID_CONTRACT", f"count={len(rows)}, unique={len(set(ids))}")
    observed = Counter(_string(row.get("template"), "required.template") for row in rows)
    if dict(observed) != EXPECTED_REQUIRED_COUNTS:
        _fail("REQUIRED_TEMPLATE_COUNTS", f"expected={EXPECTED_REQUIRED_COUNTS!r}, observed={dict(observed)!r}")
    return rows


def _assign_required_ids(
    instance: Mapping[str, Any],
    manufacturing: Sequence[ManufacturingPlacement],
    operations: Mapping[str, OperationInfo],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    required_rows = _required_rows(instance)
    strict_by_group: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    worker_by_group: dict[tuple[str, str], list[ManufacturingPlacement]] = defaultdict(list)
    for required in required_rows:
        template = str(required["template"])
        if template in MANUFACTURING_TEMPLATES:
            strict_by_group[(template, _string(required.get("operation"), "required.operation"))].append(required)
    for placement in manufacturing:
        worker_by_group[(placement.template, placement.operation_id)].append(placement)
    if set(strict_by_group) != set(worker_by_group):
        _fail("REQUIRED_OPERATION_GROUP_SET", "worker groups differ from strict required groups")

    output: list[dict[str, Any]] = []
    manufacturing_bindings: dict[str, dict[str, str]] = {}
    for key in sorted(strict_by_group):
        strict_group = sorted(strict_by_group[key], key=lambda row: str(row["id"]))
        worker_group = sorted(
            worker_by_group[key],
            key=lambda row: (
                row.anchor[1],
                row.anchor[0],
                row.mode,
                row.pose_idx,
                row.signature,
            ),
        )
        if len(strict_group) != len(worker_group):
            _fail("REQUIRED_OPERATION_GROUP_COUNT", repr(key))
        for required, placement in zip(strict_group, worker_group, strict=True):
            operation = operations[placement.operation_id]
            input_port_ids = sorted(
                port_id for port_id, kind in placement.active_ports if kind == "input"
            )
            output_port_ids = sorted(
                port_id for port_id, kind in placement.active_ports if kind == "output"
            )
            if (
                len(input_port_ids) != len(operation.input_commodities)
                or len(output_port_ids) != len(operation.output_commodities)
            ):
                _fail("MANUFACTURING_BINDING_ARITY", str(required["id"]))
            selected = {
                port_id: commodity
                for port_id, commodity in (
                    *zip(input_port_ids, operation.input_commodities, strict=True),
                    *zip(output_port_ids, operation.output_commodities, strict=True),
                )
            }
            instance_id = str(required["id"])
            if instance_id in manufacturing_bindings:
                _fail("DUPLICATE_MANUFACTURING_BINDING_ID", instance_id)
            manufacturing_bindings[instance_id] = dict(sorted(selected.items()))
            output.append(
                {
                    "instance_id": instance_id,
                    "template": placement.template,
                    "mode": placement.mode,
                    "anchor": {"x": placement.anchor[0], "y": placement.anchor[1]},
                }
            )

    by_template = shelf._required_by_template(instance)
    boundary_required = by_template.get("boundary_storage_port", [])
    boundaries = geometry.place_boundary_instances(
        (str(row["id"]) for row in boundary_required),
        FIXED_BOUNDARY_PATTERN,
    )
    output.extend(
        {
            "instance_id": placement.instance_id,
            "template": "boundary_storage_port",
            "mode": placement.mode,
            "anchor": {"x": placement.anchor[0], "y": placement.anchor[1]},
        }
        for placement in boundaries
    )

    cores = by_template.get("protocol_core", [])
    if len(cores) != 1:
        _fail("REQUIRED_CORE_COUNT", f"expected 1, observed {len(cores)}")
    output.append(
        {
            "instance_id": _string(cores[0].get("id"), "protocol_core.id"),
            "template": "protocol_core",
            "mode": "inputs_north_south",
            "anchor": {"x": FIXED_CORE_ANCHOR[0], "y": FIXED_CORE_ANCHOR[1]},
        }
    )

    expected_ids = {str(row["id"]) for row in required_rows}
    output_ids = [str(row["instance_id"]) for row in output]
    if len(output) != 266 or len(output_ids) != len(set(output_ids)) or set(output_ids) != expected_ids:
        _fail("MATERIALIZED_REQUIRED_IDS", "required ID set is incomplete or duplicated")
    if (
        len(manufacturing_bindings) != EXPECTED_MANUFACTURING_COUNT
        or sum(len(value) for value in manufacturing_bindings.values())
        != EXPECTED_MANUFACTURING_ACTIVE_PORTS
    ):
        _fail(
            "MATERIALIZED_MANUFACTURING_BINDINGS",
            (
                f"instances={len(manufacturing_bindings)}, "
                f"ports={sum(len(value) for value in manufacturing_bindings.values())}"
            ),
        )
    output.sort(key=lambda row: str(row["instance_id"]))
    return output, dict(sorted(manufacturing_bindings.items()))


def _local_geometry_validation(
    *,
    instance: Mapping[str, Any],
    required: Sequence[Mapping[str, Any]],
    poles: Sequence[tuple[int, int]],
    manufacturing: Sequence[ManufacturingPlacement],
    operations: Mapping[str, OperationInfo],
    pose_index: Mapping[tuple[str, str, int, int], tuple[int, Mapping[str, Any], str]],
    strict_modes: Mapping[tuple[str, str], Mapping[str, Any]],
    pose_cache: dict[tuple[str, str, int, int], PoseInfo],
    protected_rectangle: geometry.Rect,
) -> dict[str, Any]:
    owner_by_cell: dict[tuple[int, int], str] = {}
    required_pose_by_id: dict[str, PoseInfo] = {}
    for index, placement in enumerate(required):
        anchor_map = _mapping(placement.get("anchor"), f"required[{index}].anchor")
        key = (
            _string(placement.get("template"), f"required[{index}].template"),
            _string(placement.get("mode"), f"required[{index}].mode"),
            _integer(anchor_map.get("x"), f"required[{index}].anchor.x"),
            _integer(anchor_map.get("y"), f"required[{index}].anchor.y"),
        )
        pose = _decode_pose(key, pose_index=pose_index, strict_modes=strict_modes, cache=pose_cache)
        instance_id = _string(placement.get("instance_id"), f"required[{index}].instance_id")
        required_pose_by_id[instance_id] = pose
        for cell in pose.body_cells:
            if not (0 <= cell[0] < 70 and 0 <= cell[1] < 70):
                _fail("BODY_OUT_OF_GRID", instance_id)
            previous = owner_by_cell.setdefault(cell, instance_id)
            if previous != instance_id:
                _fail("BODY_OVERLAP", f"{cell}: {previous}/{instance_id}")

    for index, anchor in enumerate(poles):
        key = ("power_pole", "fixed", anchor[0], anchor[1])
        pose = _decode_pose(key, pose_index=pose_index, strict_modes=strict_modes, cache=pose_cache)
        owner = f"research_power_pole_{index:03d}"
        for cell in pose.body_cells:
            if not (0 <= cell[0] < 70 and 0 <= cell[1] < 70):
                _fail("POLE_OUT_OF_GRID", repr(anchor))
            previous = owner_by_cell.setdefault(cell, owner)
            if previous != owner:
                _fail("POLE_BODY_OVERLAP", f"{cell}: {previous}/{owner}")

    occupied = frozenset(owner_by_cell)
    protected_hits = occupied & protected_rectangle.cells
    if protected_hits:
        _fail("PROTECTED_RECTANGLE_OCCUPIED", repr(sorted(protected_hits)[:8]))

    for placement in manufacturing:
        key = (placement.template, placement.mode, placement.anchor[0], placement.anchor[1])
        pose = pose_cache[key]
        if any(cell in occupied for cell in placement.active_cells):
            _fail("ACTIVE_FRONT_BLOCKED", repr(key))
        operation = operations[placement.operation_id]
        clear_inputs = sum(cell not in occupied for cell in pose.input_front_cells)
        clear_outputs = sum(cell not in occupied for cell in pose.output_front_cells)
        if clear_inputs < operation.input_need or clear_outputs < operation.output_need:
            _fail("ACTIVE_FRONT_CAPACITY", repr(key))

    templates = _mapping(instance.get("facility_templates"), "facility_templates")
    coverage = set().union(*(geometry.pole_coverage_cells(anchor) for anchor in poles))
    uncovered: list[str] = []
    powered_count = 0
    for placement in required:
        instance_id = str(placement["instance_id"])
        template_id = str(placement["template"])
        template = _mapping(templates.get(template_id), f"facility_templates.{template_id}")
        requires_power = template.get("requires_power")
        if type(requires_power) is not bool:
            _fail("TEMPLATE_POWER_FLAG", template_id)
        if requires_power:
            powered_count += 1
            if not (required_pose_by_id[instance_id].body_cells & coverage):
                uncovered.append(instance_id)
    if uncovered:
        _fail("POWER_UNCOVERED", repr(uncovered[:8]))

    return {
        "required_placement_count": len(required),
        "manufacturing_placement_count": len(manufacturing),
        "pole_count": len(poles),
        "occupied_body_cell_count": len(occupied),
        "powered_required_count": powered_count,
        "power_uncovered_count": 0,
        "manufacturing_active_port_count": sum(len(row.active_cells) for row in manufacturing),
        "fixed_active_port_count": EXPECTED_FIXED_ACTIVE_PORTS,
        "total_active_incidence_count": EXPECTED_TOTAL_ACTIVE_INCIDENCES,
        "protected_rectangle": [
            protected_rectangle.x,
            protected_rectangle.y,
            protected_rectangle.width,
            protected_rectangle.height,
        ],
    }


def materialize_explicit_bundle(
    bundle: ExplicitPlacementBundle,
    *,
    snapshot: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize a normalized explicit placement/fixed-metadata bundle."""

    expected_metadata = {
        "core_anchor": FIXED_CORE_ANCHOR,
        "boundary_pattern": (FIXED_BOUNDARY_PATTERN.left_gap, FIXED_BOUNDARY_PATTERN.bottom_gap),
        "backbone_vertical_lanes": BACKBONE_VERTICAL_LANES,
        "backbone_horizontal_lanes": BACKBONE_HORIZONTAL_LANES,
        "backbone_cell_count": BACKBONE_CELL_COUNT,
    }
    observed_metadata = {
        "core_anchor": bundle.core_anchor,
        "boundary_pattern": bundle.boundary_pattern,
        "backbone_vertical_lanes": bundle.backbone_vertical_lanes,
        "backbone_horizontal_lanes": bundle.backbone_horizontal_lanes,
        "backbone_cell_count": bundle.backbone_cell_count,
    }
    if observed_metadata != expected_metadata:
        _fail("EXPLICIT_FIXED_METADATA", f"expected={expected_metadata!r}, observed={observed_metadata!r}")
    protected_rectangle = _explicit_protected_rectangle(bundle.protected_rectangle)
    if len(bundle.placements) != EXPECTED_MANUFACTURING_COUNT:
        _fail("EXPLICIT_PLACEMENT_COUNT", f"expected 219, observed {len(bundle.placements)}")
    poles = tuple(sorted(bundle.pole_anchors, key=lambda anchor: (anchor[1], anchor[0])))
    if len(poles) != EXPECTED_POLE_COUNT or len(set(poles)) != EXPECTED_POLE_COUNT:
        _fail("EXPLICIT_POLE_COUNT", "explicit geometry requires 35 unique pole anchors")

    instance = _mapping(getattr(snapshot, "instance", None), "snapshot.instance")
    facility_pools = _mapping(getattr(snapshot, "facility_pools", None), "snapshot.facility_pools")
    strict_modes = _strict_modes(instance)
    operations, expected_pairs, expected_expansion = _operation_contract(instance)
    if bundle.declared_operation_expansion is not None:
        _validate_declared_expansion(bundle.declared_operation_expansion, expected_expansion)
    if bundle.declared_signature_counts is not None:
        _validate_declared_signature_counts(bundle.declared_signature_counts, operations)
    pose_index = _candidate_pose_index(facility_pools)
    pose_cache: dict[tuple[str, str, int, int], PoseInfo] = {}
    manufacturing = _parse_manufacturing_placements(
        bundle.placements,
        operations=operations,
        expected_pairs=expected_pairs,
        pose_index=pose_index,
        strict_modes=strict_modes,
        pose_cache=pose_cache,
    )
    required, manufacturing_bindings = _assign_required_ids(
        instance, manufacturing, operations
    )
    payload = {
        "schema_version": fixed_router.INPUT_SCHEMA_VERSION,
        "required_placements": required,
        "pole_anchors": [[anchor[0], anchor[1]] for anchor in poles],
        "manufacturing_port_bindings": manufacturing_bindings,
    }
    parsed = fixed_router.parse_geometry_payload(payload, minimum_poles=9)
    if len(parsed.required_placements) != 266 or len(parsed.pole_anchors) != EXPECTED_POLE_COUNT:
        _fail("ROUTER_INPUT_COUNTS", "router parser changed the full geometry counts")
    if parsed.manufacturing_port_bindings != manufacturing_bindings:
        _fail("ROUTER_INPUT_BINDINGS", "router parser changed manufacturing bindings")
    local_validation = _local_geometry_validation(
        instance=instance,
        required=required,
        poles=poles,
        manufacturing=manufacturing,
        operations=operations,
        pose_index=pose_index,
        strict_modes=strict_modes,
        pose_cache=pose_cache,
        protected_rectangle=protected_rectangle,
    )
    local_validation.update(
        {
            "manufacturing_binding_instance_count": len(manufacturing_bindings),
            "manufacturing_binding_port_count": sum(
                len(bindings) for bindings in manufacturing_bindings.values()
            ),
            "manufacturing_port_bindings_digest": fixed_router.canonical_digest(
                manufacturing_bindings
            ),
        }
    )
    return payload, local_validation


def materialize_reduced_payload(
    result_value: object,
    *,
    snapshot: Any,
    telemetry_validator: Callable[[object], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize a supported source result and validate its explicit geometry."""

    validator = telemetry_validator or shelf._validate_cgroup_telemetry
    bundle = _normalize_result_source(
        result_value,
        snapshot=snapshot,
        telemetry_validator=validator,
    )
    return materialize_explicit_bundle(bundle, snapshot=snapshot)


def _pole_records(anchors: Sequence[tuple[int, int]]) -> list[dict[str, Any]]:
    return [
        {
            "instance_id": f"research_power_pole_{index:03d}",
            "template": "power_pole",
            "mode": "fixed",
            "anchor": {"x": anchor[0], "y": anchor[1]},
        }
        for index, anchor in enumerate(anchors)
    ]


def dry_routing_precheck_only(
    payload: Mapping[str, Any],
    *,
    snapshot: Any,
    dependencies: Any,
) -> dict[str, Any]:
    """Replay production binding and precheck, then stop before router creation."""

    parsed = fixed_router.parse_geometry_payload(payload, minimum_poles=9)
    if len(parsed.required_placements) != 266 or len(parsed.pole_anchors) != EXPECTED_POLE_COUNT:
        _fail("DRY_PRECHECK_COUNTS", "dry precheck requires 266 placements and 35 poles")
    required = [dict(row) for row in parsed.required_placements]
    optional = _pole_records(parsed.pole_anchors)
    instance = _mapping(getattr(snapshot, "instance", None), "snapshot.instance")
    facility_pools = _mapping(getattr(snapshot, "facility_pools", None), "snapshot.facility_pools")
    grid = _mapping(instance.get("grid"), "instance.grid")
    width = _integer(grid.get("width"), "instance.grid.width")
    height = _integer(grid.get("height"), "instance.grid.height")
    if (width, height) != (70, 70):
        _fail("DRY_PRECHECK_GRID", repr((width, height)))

    placement_solution = dependencies.resolve_placement_solution(
        instance=instance,
        required_placements=required,
        optional_placements=optional,
        facility_pools=facility_pools,
    )
    expected_ids = {str(row["instance_id"]) for row in (*required, *optional)}
    if not isinstance(placement_solution, Mapping) or set(placement_solution) != expected_ids:
        _fail("DRY_POSE_REPLAY_IDS", "pose replay changed the placement ID set")

    context = dependencies.build_routing_context(placement_solution, facility_pools, width, height)
    occupied_cells = frozenset(getattr(context, "occupied_cells", ()))
    occupied_owner_by_cell = dict(getattr(context, "occupied_owner_by_cell", {}))
    component_by_cell = dict(getattr(context, "component_by_cell", {}))
    if set(occupied_owner_by_cell) != set(occupied_cells):
        _fail("DRY_OCCUPANCY_OWNER", "every occupied cell needs one owner")

    allowed_access_cells = frozenset(component_by_cell)
    selected_port_bindings, manufacturing_ids = fixed_router.select_port_bindings_for_geometry(
        parsed,
        instance=instance,
        required_placements=required,
        optional_placements=optional,
        allowed_access_cells=allowed_access_cells,
        choose_port_bindings=dependencies.choose_port_bindings,
        phase="dry_binding",
    )
    bound = dependencies.bind_placements(
        instance,
        required_placements=required,
        optional_placements=optional,
        selected_port_bindings=selected_port_bindings,
        allowed_access_cells=allowed_access_cells,
    )
    bound = _mapping(bound, "bound")
    bound_required = list(_sequence(bound.get("required_placements"), "bound.required_placements"))
    bound_optional = list(_sequence(bound.get("optional_placements"), "bound.optional_placements"))
    if len(bound_required) != len(required) or len(bound_optional) != len(optional):
        _fail("DRY_BOUND_COUNTS", "binding changed placement counts")
    fixed_router.assert_manufacturing_bindings_preserved(
        bound_required,
        expected=parsed.manufacturing_port_bindings,
        manufacturing_ids=manufacturing_ids,
        phase="dry_binding",
    )

    port_specs = [
        dict(spec)
        for spec in dependencies.derive_port_specs(
            instance,
            required_placements=bound_required,
            optional_placements=bound_optional,
        )
    ]
    commodities = [
        _string(value, f"commodities[{index}]")
        for index, value in enumerate(_sequence(instance.get("commodities"), "commodities"))
    ]
    if not commodities or len(commodities) != len(set(commodities)):
        _fail("DRY_COMMODITY_SET", "strict commodities must be nonempty and unique")
    active_commodities = sorted({str(spec.get("commodity", "")) for spec in port_specs})
    if active_commodities != sorted(commodities):
        _fail("DRY_ACTIVE_COMMODITIES", "bound port specs do not cover the strict commodity set")

    strict_occupied = frozenset(
        dependencies.occupied_body_cells(instance, [*bound_required, *bound_optional])
    )
    if strict_occupied != occupied_cells:
        _fail("DRY_OCCUPANCY_MISMATCH", "strict and candidate-pose occupancy differ")
    placement_core = dependencies.make_placement_core(
        occupied_cells,
        occupied_owner_by_cell=occupied_owner_by_cell,
    )
    precheck = dependencies.routing_precheck(
        placement_core=placement_core,
        port_specs=port_specs,
        occupied_owner_by_cell=occupied_owner_by_cell,
    )
    precheck = _mapping(precheck, "routing_precheck")
    status = precheck.get("status")
    safe_reject = precheck.get("binding_selection_safe_reject")
    if type(status) is not str or type(safe_reject) is not bool:
        _fail("DRY_PRECHECK_CONTRACT", "routing precheck status contract is malformed")
    analysis_ok = isinstance(precheck.get("_analysis"), Mapping)
    accepted = status == "feasible" and analysis_ok
    if accepted:
        classification = "ROUTING_PRECHECK_ACCEPTED"
    elif safe_reject and status in {"front_blocked", "relaxed_disconnected"}:
        classification = "ROUTING_PRECHECK_REJECTED"
    elif status == "feasible":
        classification = "ROUTING_PRECHECK_ANALYSIS_MISSING"
    else:
        classification = "ROUTING_PRECHECK_UNVERIFIED_STATUS"

    terminal_cells = {(int(spec["x"]), int(spec["y"])) for spec in port_specs}
    return {
        "accepted": accepted,
        "classification": classification,
        "pose_replay_placement_count": len(placement_solution),
        "bound_required_count": len(bound_required),
        "bound_pole_count": len(bound_optional),
        "occupied_body_cell_count": len(occupied_cells),
        "free_component_cell_count": len(component_by_cell),
        "port_spec_count": len(port_specs),
        "terminal_cell_count": len(terminal_cells),
        "commodity_count": len(commodities),
        "manufacturing_binding_instance_count": len(manufacturing_ids),
        "manufacturing_binding_port_count": sum(
            len(bindings) for bindings in parsed.manufacturing_port_bindings.values()
        ),
        "manufacturing_port_bindings_digest": fixed_router.canonical_digest(
            parsed.manufacturing_port_bindings
        ),
        "precheck_status": status,
        "binding_selection_safe_reject": safe_reject,
        "domain_stats": _json_copy(precheck.get("domain_stats", {}), "precheck.domain_stats"),
        "stopped_before_router_construction": True,
    }


def _write_exclusive(path: Path, payload: Mapping[str, Any]) -> tuple[Path, str]:
    try:
        raw = (
            json.dumps(
                payload,
                ensure_ascii=True,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        _fail("OUTPUT_NOT_JSON", str(exc))
    source = Path(path)
    try:
        parent = source.parent.resolve(strict=True)
    except OSError as exc:
        _fail("OUTPUT_PARENT", str(exc))
    if not parent.is_dir():
        _fail("OUTPUT_PARENT", str(parent))
    target = parent / source.name
    try:
        with target.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError:
        _fail("OUTPUT_ALREADY_EXISTS", str(target))
    except OSError as exc:
        _fail("OUTPUT_WRITE", str(exc))
    return target, hashlib.sha256(raw).hexdigest()


def materialize_reduced_result(
    *,
    result_path: Path,
    expected_result_sha256: str,
    output_path: Path,
    project_root: Path = PROJECT_ROOT,
    snapshot: Any | None = None,
    dependencies: Any | None = None,
    telemetry_validator: Callable[[object], None] | None = None,
) -> dict[str, Any]:
    """Hash-pin, materialize, dry-precheck, and exclusively publish one payload."""

    root_path = Path(project_root).resolve(strict=True)
    if not root_path.is_dir():
        _fail("PROJECT_ROOT", str(root_path))
    if str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))
    result_value = fixed_router.load_geometry_payload(
        Path(result_path),
        expected_sha256=expected_result_sha256,
    )
    current_snapshot = snapshot or fixed_router.load_production_input_snapshot(root_path)
    payload, local_validation = materialize_reduced_payload(
        result_value,
        snapshot=current_snapshot,
        telemetry_validator=telemetry_validator,
    )
    current_dependencies = dependencies or fixed_router.production_dependencies()
    dry_validation = dry_routing_precheck_only(
        payload,
        snapshot=current_snapshot,
        dependencies=current_dependencies,
    )
    report = {
        "status": "READY_TO_WRITE" if dry_validation["accepted"] else "REJECTED",
        "claim_boundary": "research_candidate_feasibility_only",
        "source_result": str(Path(result_path).resolve(strict=True)),
        "source_result_sha256": expected_result_sha256,
        "output": None,
        "output_sha256": None,
        "input_hashes": dict(sorted(current_snapshot.hashes.items())),
        "local_validation": local_validation,
        "dry_validation": dry_validation,
    }
    if not dry_validation["accepted"]:
        return report
    written_path, output_sha256 = _write_exclusive(Path(output_path), payload)
    report.update(
        {
            "status": "MATERIALIZED",
            "output": str(written_path),
            "output_sha256": output_sha256,
        }
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--worker-result", type=Path, required=True)
    parser.add_argument("--expected-worker-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = materialize_reduced_result(
            result_path=args.worker_result,
            expected_result_sha256=args.expected_worker_sha256,
            output_path=args.out,
            project_root=args.project_root,
        )
    except Exception as exc:  # noqa: BLE001 - one fail-closed CLI boundary
        raise SystemExit(f"{type(exc).__name__}: {exc}") from exc
    print(json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "ExplicitPlacementBundle",
    "FIXED_BOUNDARY_PATTERN",
    "FIXED_CORE_ANCHOR",
    "FIXED_POLE_ANCHORS",
    "PROTECTED_RECTANGLE",
    "PROTECTED_RECTANGLE_SHAPE",
    "RELABEL_SCHEMA_VERSION",
    "RESULT_SCHEMA_VERSION",
    "ReducedGeometryMaterializerError",
    "dry_routing_precheck_only",
    "materialize_explicit_bundle",
    "materialize_reduced_payload",
    "materialize_reduced_result",
]
