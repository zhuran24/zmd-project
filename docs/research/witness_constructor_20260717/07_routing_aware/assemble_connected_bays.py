"""Assemble independently replayed bay selections into one strict geometry.

The bay solvers are deliberately outside this adapter.  This module consumes
their hash-pinned, fully explicit pose rows, replays every row against the
current strict/candidate inputs, restricts usable manufacturing fronts to the
single free component containing all fixed terminals, performs the exact
nine-signature b-matching, and then invokes the production dry routing
precheck.  No routing model is constructed here.

Both output files are exclusive-create and must remain inside this research
directory.  A rejected dry precheck emits only the report, never a geometry
input that could accidentally be launched.
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
from dataclasses import dataclass
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
from typing import Any, Mapping, Sequence


PREFIX = "docs.research.witness_constructor_20260717.07_routing_aware"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESEARCH_ROOT = Path(__file__).resolve().parent
EXPECTED_BASELINE_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
SELECTION_SCHEMA_VERSION = "connected_bay_selection.v2"
LEGACY_SELECTION_SCHEMA_VERSION = "connected_bay_selection.v1"
SELECTION_READY_STATUS = "CONNECTED_BAY_SELECTION_READY"
REPORT_SCHEMA_VERSION = "connected_bay_assembly_report.v1"
EXPECTED_COMPONENT_IDS = frozenset(range(17))
EXPECTED_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 132,
    "manufacturing_5x5": 49,
    "manufacturing_6x4": 38,
}
EXPECTED_MANUFACTURING_COUNT = 219
EXPECTED_POLE_COUNT = 35
EXPECTED_MANUFACTURING_BODY_CELLS = 3325
EXPECTED_MANUFACTURING_ACTIVE_PORTS = 574
EXPECTED_TOTAL_ACTIVE_PORTS = 628
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
_OPPOSITE_DIRECTION = {"N": "S", "E": "W", "S": "N", "W": "E"}

active_match = importlib.import_module(f"{PREFIX}.active_signature_match")
fixed_router = importlib.import_module(f"{PREFIX}.fixed_geometry_router")
geometry = importlib.import_module(f"{PREFIX}.geometry")
materializer = importlib.import_module(f"{PREFIX}.materialize_reduced_geometry")
strict_contract = importlib.import_module(f"{PREFIX}.strict_contract")

Cell = tuple[int, int]


class ConnectedBayAssemblyError(ValueError):
    """Stable fail-closed error for selection parsing or assembly replay."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str) -> None:
    raise ConnectedBayAssemblyError(code, message)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail("MALFORMED_OBJECT", label)
    return value


def _sequence(value: object, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail("MALFORMED_ARRAY", label)
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        _fail("MALFORMED_STRING", label)
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        _fail("MALFORMED_INTEGER", label)
    return value


def _cell(value: object, label: str) -> Cell:
    pair = _sequence(value, label)
    if len(pair) != 2:
        _fail("MALFORMED_CELL", label)
    return _integer(pair[0], f"{label}[0]"), _integer(pair[1], f"{label}[1]")


def _exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        _fail("SCHEMA_FIELDS", f"{label}: expected={sorted(expected)!r}, observed={sorted(value)!r}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(payload: Mapping[str, Any], *, label: str) -> bytes:
    try:
        rendered = json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        _fail("OUTPUT_NOT_JSON", f"{label}: {exc}")
    return (rendered + "\n").encode("ascii")


def _regular_non_symlink(path: Path, label: str) -> Path:
    try:
        metadata = path.lstat()
    except OSError as exc:
        _fail("FILE_UNAVAILABLE", f"{label}: {exc}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        _fail("FILE_TYPE", f"{label} must be a regular non-symlink file")
    return path.resolve(strict=True)


@dataclass(frozen=True)
class SourceArtifact:
    path: Path
    sha256: str


@dataclass(frozen=True)
class SelectedPose:
    template: str
    mode: str
    body: tuple[Cell, ...]
    inputs: tuple[Cell, ...]
    outputs: tuple[Cell, ...]


@dataclass(frozen=True)
class BaySelection:
    component: int
    origin: Cell
    selected: tuple[SelectedPose, ...]


@dataclass(frozen=True)
class ConnectedBaySelection:
    claim_boundary: str
    baseline_head: str
    source_artifacts: tuple[SourceArtifact, ...]
    pole_anchors: tuple[Cell, ...]
    protected_rectangle: tuple[int, int, int, int]
    components: tuple[BaySelection, ...]


def _parse_pose(value: object, label: str) -> SelectedPose:
    row = _mapping(value, label)
    _exact_fields(row, {"template", "mode", "body", "inputs", "outputs"}, label)

    def cells(field: str, *, allow_empty: bool = False) -> tuple[Cell, ...]:
        parsed = tuple(
            _cell(raw, f"{label}.{field}[{index}]")
            for index, raw in enumerate(_sequence(row.get(field), f"{label}.{field}"))
        )
        if (not parsed and not allow_empty) or len(set(parsed)) != len(parsed):
            _fail("POSE_CELLS", f"{label}.{field}")
        return parsed

    return SelectedPose(
        template=_string(row.get("template"), f"{label}.template"),
        mode=_string(row.get("mode"), f"{label}.mode"),
        body=cells("body"),
        inputs=cells("inputs"),
        outputs=cells("outputs"),
    )


def parse_selection(
    value: object,
    *,
    selection_parent: Path,
    verify_source_artifacts: bool = True,
) -> ConnectedBaySelection:
    """Parse the exact handoff schema and optionally rehash all source rows."""

    root = _mapping(value, "selection")
    schema_version = root.get("schema_version")
    common_fields = {
        "schema_version",
        "status",
        "claim_boundary",
        "baseline_head",
        "source_artifacts",
        "pole_anchors",
        "components",
    }
    if schema_version == SELECTION_SCHEMA_VERSION:
        _exact_fields(root, common_fields | {"protected_rectangle"}, "selection")
        protected_raw = _sequence(root.get("protected_rectangle"), "protected_rectangle")
        if len(protected_raw) != 4:
            _fail("PROTECTED_RECTANGLE", "protected_rectangle must contain x, y, width, height")
        protected_rectangle = tuple(
            _integer(item, f"protected_rectangle[{index}]")
            for index, item in enumerate(protected_raw)
        )
    elif schema_version == LEGACY_SELECTION_SCHEMA_VERSION:
        _exact_fields(root, common_fields, "selection")
        protected_rectangle = (
            materializer.PROTECTED_RECTANGLE.x,
            materializer.PROTECTED_RECTANGLE.y,
            materializer.PROTECTED_RECTANGLE.width,
            materializer.PROTECTED_RECTANGLE.height,
        )
    else:
        _fail("SELECTION_SCHEMA", repr(schema_version))
    try:
        protected = geometry.Rect(*protected_rectangle)
    except geometry.GeometryContractError as exc:
        _fail("PROTECTED_RECTANGLE", str(exc))
    if (protected.width, protected.height) != materializer.PROTECTED_RECTANGLE_SHAPE:
        _fail(
            "PROTECTED_RECTANGLE",
            f"expected shape={materializer.PROTECTED_RECTANGLE_SHAPE!r}, observed={(protected.width, protected.height)!r}",
        )
    if not protected.in_grid():
        _fail("PROTECTED_RECTANGLE", "protected rectangle is outside the 70x70 grid")
    if root.get("status") != SELECTION_READY_STATUS:
        _fail("SELECTION_STATUS", repr(root.get("status")))
    baseline_head = _string(root.get("baseline_head"), "baseline_head")
    if baseline_head != EXPECTED_BASELINE_HEAD or _FULL_SHA_RE.fullmatch(baseline_head) is None:
        _fail("BASELINE_HEAD", baseline_head)

    sources: list[SourceArtifact] = []
    seen_source_paths: set[Path] = set()
    for index, raw in enumerate(_sequence(root.get("source_artifacts"), "source_artifacts")):
        row = _mapping(raw, f"source_artifacts[{index}]")
        _exact_fields(row, {"path", "sha256"}, f"source_artifacts[{index}]")
        raw_path = Path(_string(row.get("path"), f"source_artifacts[{index}].path"))
        source_path = raw_path if raw_path.is_absolute() else selection_parent / raw_path
        source_path = _regular_non_symlink(source_path, f"source_artifacts[{index}]")
        expected_sha = _string(row.get("sha256"), f"source_artifacts[{index}].sha256")
        if _SHA256_RE.fullmatch(expected_sha) is None:
            _fail("SOURCE_HASH", repr(expected_sha))
        if source_path in seen_source_paths:
            _fail("SOURCE_DUPLICATE", str(source_path))
        seen_source_paths.add(source_path)
        if verify_source_artifacts:
            observed = _sha256(source_path)
            if observed != expected_sha:
                _fail("SOURCE_HASH_MISMATCH", f"{source_path}: expected={expected_sha}, observed={observed}")
        sources.append(SourceArtifact(source_path, expected_sha))
    if not sources:
        _fail("SOURCE_EMPTY", "at least one source artifact is required")

    poles = tuple(
        _cell(raw, f"pole_anchors[{index}]")
        for index, raw in enumerate(_sequence(root.get("pole_anchors"), "pole_anchors"))
    )
    if len(poles) != EXPECTED_POLE_COUNT or len(set(poles)) != EXPECTED_POLE_COUNT:
        _fail("POLE_COUNT", f"expected {EXPECTED_POLE_COUNT} unique anchors")

    components: list[BaySelection] = []
    for index, raw in enumerate(_sequence(root.get("components"), "components")):
        row = _mapping(raw, f"components[{index}]")
        _exact_fields(row, {"component", "origin", "selected"}, f"components[{index}]")
        components.append(
            BaySelection(
                component=_integer(row.get("component"), f"components[{index}].component"),
                origin=_cell(row.get("origin"), f"components[{index}].origin"),
                selected=tuple(
                    _parse_pose(pose, f"components[{index}].selected[{pose_index}]")
                    for pose_index, pose in enumerate(
                        _sequence(row.get("selected"), f"components[{index}].selected")
                    )
                ),
            )
        )
    ids = [component.component for component in components]
    if frozenset(ids) != EXPECTED_COMPONENT_IDS or len(ids) != len(set(ids)):
        _fail("COMPONENT_IDS", repr(sorted(ids)))
    pose_count = sum(len(component.selected) for component in components)
    if pose_count != EXPECTED_MANUFACTURING_COUNT:
        _fail("PLACEMENT_COUNT", f"expected {EXPECTED_MANUFACTURING_COUNT}, observed {pose_count}")
    counts = Counter(pose.template for component in components for pose in component.selected)
    if dict(counts) != EXPECTED_TEMPLATE_COUNTS:
        _fail("TEMPLATE_COUNTS", f"expected={EXPECTED_TEMPLATE_COUNTS!r}, observed={dict(counts)!r}")
    return ConnectedBaySelection(
        claim_boundary=_string(root.get("claim_boundary"), "claim_boundary"),
        baseline_head=baseline_head,
        source_artifacts=tuple(sources),
        pole_anchors=tuple(sorted(poles, key=lambda cell: (cell[1], cell[0]))),
        protected_rectangle=protected_rectangle,
        components=tuple(sorted(components, key=lambda item: item.component)),
    )


def load_selection(path: Path, *, expected_sha256: str) -> ConnectedBaySelection:
    source = _regular_non_symlink(Path(path), "selection")
    parsed = fixed_router.load_geometry_payload(source, expected_sha256=expected_sha256)
    return parse_selection(parsed, selection_parent=source.parent)


def _global_cells(cells: Sequence[Cell], origin: Cell) -> tuple[Cell, ...]:
    return tuple((origin[0] + cell[0], origin[1] + cell[1]) for cell in cells)


def _reachable(start: Cell, free: set[Cell]) -> set[Cell]:
    if start not in free:
        _fail("FIXED_TERMINAL_BLOCKED", repr(start))
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for neighbour in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if neighbour in free and neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return seen


def _repository_head(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        _fail("GIT_HEAD", str(exc))
    head = result.stdout.strip()
    if head != EXPECTED_BASELINE_HEAD:
        _fail("GIT_HEAD", f"expected={EXPECTED_BASELINE_HEAD}, observed={head}")
    return head


def _strict_port_choices(
    strict_mode: Mapping[str, Any],
    anchor: Cell,
) -> tuple[dict[str, Any], ...]:
    choices: list[dict[str, Any]] = []
    for index, raw in enumerate(_sequence(strict_mode.get("ports"), "strict_mode.ports")):
        port = _mapping(raw, f"strict_mode.ports[{index}]")
        port_id = _string(port.get("id"), f"strict_mode.ports[{index}].id")
        kind = _string(port.get("kind"), f"strict_mode.ports[{index}].kind")
        direction = _string(port.get("direction"), f"strict_mode.ports[{index}].direction")
        if kind not in {"input", "output"} or direction not in _OPPOSITE_DIRECTION:
            _fail("PORT_SEMANTICS", f"{port_id}/{kind}/{direction}")
        access = strict_contract.strict_port_access_cell(anchor, port)
        choices.append(
            {
                "port_id": port_id,
                "kind": kind,
                "direction": direction,
                "access": access,
                "component_kind": "input" if kind == "output" else "output",
                "component_side": _OPPOSITE_DIRECTION[direction],
            }
        )
    if len({choice["port_id"] for choice in choices}) != len(choices):
        _fail("PORT_ID_DUPLICATE", repr(anchor))
    return tuple(sorted(choices, key=lambda choice: str(choice["port_id"])))


@dataclass(frozen=True)
class _ReplayPose:
    pose_id: str
    component: int
    template: str
    mode: str
    anchor: Cell
    pose_idx: int
    candidate_mode: str
    body: frozenset[Cell]
    port_choices: tuple[dict[str, Any], ...]


def _fixed_geometry_bodies(
    *,
    pole_anchors: Sequence[Cell],
    pose_index: Mapping[tuple[str, str, int, int], tuple[int, Mapping[str, Any], str]],
    strict_modes: Mapping[tuple[str, str], Mapping[str, Any]],
    pose_cache: dict[tuple[str, str, int, int], Any],
) -> tuple[frozenset[Cell], frozenset[Cell], frozenset[Cell]]:
    boundaries = geometry.place_boundary_instances(
        (f"boundary-{index:03d}" for index in range(46)),
        materializer.FIXED_BOUNDARY_PATTERN,
    )
    boundary_bodies = frozenset(cell for placement in boundaries for cell in placement.body_cells)
    boundary_fronts = frozenset(cell for placement in boundaries for cell in placement.front_cells)
    core_key = ("protocol_core", "inputs_north_south", *materializer.FIXED_CORE_ANCHOR)
    core = materializer._decode_pose(
        core_key,
        pose_index=pose_index,
        strict_modes=strict_modes,
        cache=pose_cache,
    )
    pole_bodies: set[Cell] = set()
    for anchor in pole_anchors:
        pole = materializer._decode_pose(
            ("power_pole", "fixed", anchor[0], anchor[1]),
            pose_index=pose_index,
            strict_modes=strict_modes,
            cache=pose_cache,
        )
        if pole_bodies & pole.body_cells:
            _fail("POLE_BODY_OVERLAP", repr(anchor))
        pole_bodies.update(pole.body_cells)
    fixed_required_bodies = boundary_bodies | core.body_cells
    fixed_fronts = boundary_fronts | frozenset((*core.input_front_cells, *core.output_front_cells))
    return fixed_required_bodies, frozenset(pole_bodies), fixed_fronts


def assemble_selection(
    selection: ConnectedBaySelection,
    *,
    snapshot: Any,
    dependencies: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Replay, signature-match, materialize, and dry-precheck one selection."""

    instance = _mapping(getattr(snapshot, "instance", None), "snapshot.instance")
    pools = _mapping(getattr(snapshot, "facility_pools", None), "snapshot.facility_pools")
    strict_modes = materializer._strict_modes(instance)
    pose_index = materializer._candidate_pose_index(pools)
    pose_cache: dict[tuple[str, str, int, int], Any] = {}
    replayed: list[_ReplayPose] = []
    manufacturing_bodies: set[Cell] = set()
    for component in selection.components:
        for local_index, selected in enumerate(component.selected):
            body = frozenset(_global_cells(selected.body, component.origin))
            inputs = frozenset(_global_cells(selected.inputs, component.origin))
            outputs = frozenset(_global_cells(selected.outputs, component.origin))
            anchor = (min(x for x, _y in body), min(y for _x, y in body))
            key = (selected.template, selected.mode, anchor[0], anchor[1])
            decoded = materializer._decode_pose(
                key,
                pose_index=pose_index,
                strict_modes=strict_modes,
                cache=pose_cache,
            )
            if decoded.body_cells != body:
                _fail("POSE_BODY_REPLAY", f"component={component.component}, index={local_index}")
            # Local bay workers may omit physical fronts already blocked by a
            # fixed body.  They may never invent a front; final availability is
            # recomputed below from the strict mode and combined occupancy.
            if not inputs <= frozenset(decoded.input_front_cells) or not outputs <= frozenset(
                decoded.output_front_cells
            ):
                _fail("POSE_FRONT_REPLAY", f"component={component.component}, index={local_index}")
            if manufacturing_bodies & body:
                _fail("MANUFACTURING_BODY_OVERLAP", f"component={component.component}, index={local_index}")
            manufacturing_bodies.update(body)
            replayed.append(
                _ReplayPose(
                    pose_id=f"c{component.component:02d}-p{local_index:03d}",
                    component=component.component,
                    template=selected.template,
                    mode=selected.mode,
                    anchor=anchor,
                    pose_idx=decoded.pose_idx,
                    candidate_mode=decoded.candidate_mode,
                    body=body,
                    port_choices=_strict_port_choices(strict_modes[(selected.template, selected.mode)], anchor),
                )
            )
    if len(manufacturing_bodies) != EXPECTED_MANUFACTURING_BODY_CELLS:
        _fail(
            "MANUFACTURING_BODY_COUNT",
            f"expected={EXPECTED_MANUFACTURING_BODY_CELLS}, observed={len(manufacturing_bodies)}",
        )

    fixed_required_bodies, pole_bodies, fixed_fronts = _fixed_geometry_bodies(
        pole_anchors=selection.pole_anchors,
        pose_index=pose_index,
        strict_modes=strict_modes,
        pose_cache=pose_cache,
    )
    required_bodies = frozenset(manufacturing_bodies) | fixed_required_bodies
    if len(required_bodies) != len(manufacturing_bodies) + len(fixed_required_bodies):
        _fail("FIXED_REQUIRED_OVERLAP", "manufacturing and fixed required bodies overlap")
    if required_bodies & pole_bodies:
        _fail("POLE_REQUIRED_OVERLAP", repr(sorted(required_bodies & pole_bodies)[:8]))
    occupied = required_bodies | pole_bodies
    if any(not (0 <= x < 70 and 0 <= y < 70) for x, y in occupied):
        _fail("BODY_OUT_OF_GRID", "occupied body cell outside 70x70")
    protected = geometry.Rect(*selection.protected_rectangle)
    protected_hits = occupied & protected.cells
    if protected_hits:
        _fail("PROTECTED_RECTANGLE_OCCUPIED", repr(sorted(protected_hits)[:8]))
    free = {(x, y) for x in range(70) for y in range(70)} - set(occupied)
    if not fixed_fronts or fixed_fronts & occupied:
        _fail("FIXED_FRONT_BLOCKED", repr(sorted(fixed_fronts & occupied)[:8]))
    main = _reachable(min(fixed_fronts), free)
    missing_fixed = fixed_fronts - main
    if missing_fixed:
        _fail("FIXED_FRONT_DISCONNECTED", repr(sorted(missing_fixed)[:8]))
    missing_protected = protected.cells - main
    if missing_protected:
        _fail("PROTECTED_RECTANGLE_DISCONNECTED", repr(sorted(missing_protected)[:8]))

    port_choice_by_pose_kind_cell: dict[tuple[str, str, Cell], dict[str, Any]] = {}
    pose_fronts: list[Any] = []
    capacity_histograms: dict[str, Counter[tuple[int, int]]] = {
        template: Counter() for template in EXPECTED_TEMPLATE_COUNTS
    }
    for pose in replayed:
        connected_inputs = tuple(
            choice for choice in pose.port_choices if choice["kind"] == "input" and choice["access"] in main
        )
        connected_outputs = tuple(
            choice for choice in pose.port_choices if choice["kind"] == "output" and choice["access"] in main
        )
        if any(choice["access"] in occupied for choice in (*connected_inputs, *connected_outputs)):
            _fail("CONNECTED_FRONT_BLOCKED", pose.pose_id)
        for choice in (*connected_inputs, *connected_outputs):
            key = (pose.pose_id, str(choice["kind"]), choice["access"])
            if key in port_choice_by_pose_kind_cell:
                _fail("PORT_ACCESS_DUPLICATE", repr(key))
            port_choice_by_pose_kind_cell[key] = choice
        input_cells = tuple(choice["access"] for choice in connected_inputs)
        output_cells = tuple(choice["access"] for choice in connected_outputs)
        capacity_histograms[pose.template][(len(input_cells), len(output_cells))] += 1
        pose_fronts.append(
            active_match.PoseFronts(
                pose_id=pose.pose_id,
                template=pose.template,
                input_fronts=input_cells,
                output_fronts=output_cells,
            )
        )

    operations, _expected_pairs, expansion_by_id = materializer._operation_contract(instance)
    signature_by_id: dict[str, Any] = {}
    expansion: dict[Any, tuple[str, ...]] = {}
    for operation in operations.values():
        signature = active_match.Signature(
            operation.template,
            operation.input_need,
            operation.output_need,
        )
        previous = signature_by_id.setdefault(operation.signature, signature)
        if previous != signature:
            _fail("SIGNATURE_DRIFT", operation.signature)
    for signature_id, operation_ids in expansion_by_id.items():
        expansion[signature_by_id[signature_id]] = tuple(operation_ids)
    matched = active_match.match_active_signatures(
        pose_fronts,
        facility_body_cells=required_bodies,
        pole_body_cells=pole_bodies,
        operation_expansion=expansion,
    )
    if not matched.ok:
        _fail("SIGNATURE_HALL_FAILURE", repr(matched.hall_failure))
    replay_by_id = {pose.pose_id: pose for pose in replayed}
    placements: list[dict[str, Any]] = []
    signature_counts: Counter[str] = Counter()
    active_port_count = 0
    for match in matched.matches:
        pose = replay_by_id[match.pose_id]
        if match.operation is None:
            _fail("OPERATION_MISSING", match.pose_id)
        operation = operations[match.operation]
        active_ports: list[dict[str, Any]] = []
        for kind, cells in (
            ("input", match.active_input_fronts),
            ("output", match.active_output_fronts),
        ):
            for cell in cells:
                choice = port_choice_by_pose_kind_cell[(pose.pose_id, kind, cell)]
                active_ports.append(
                    {
                        "port_id": choice["port_id"],
                        "kind": choice["kind"],
                        "direction": choice["direction"],
                        "access": [cell[0], cell[1]],
                        "component_kind": choice["component_kind"],
                        "component_side": choice["component_side"],
                    }
                )
                active_port_count += 1
        signature_counts[operation.signature] += 1
        placements.append(
            {
                "signature": operation.signature,
                "operation_id": operation.operation_id,
                "template": pose.template,
                "pose_index": pose.pose_idx,
                "pose_idx": pose.pose_idx,
                "anchor": [pose.anchor[0], pose.anchor[1]],
                "mode": pose.mode,
                "candidate_mode": pose.candidate_mode,
                "active_ports": active_ports,
            }
        )
    if active_port_count != EXPECTED_MANUFACTURING_ACTIVE_PORTS:
        _fail("ACTIVE_PORT_COUNT", f"expected={EXPECTED_MANUFACTURING_ACTIVE_PORTS}, observed={active_port_count}")

    bundle = materializer.ExplicitPlacementBundle(
        placements=tuple(placements),
        pole_anchors=selection.pole_anchors,
        core_anchor=materializer.FIXED_CORE_ANCHOR,
        boundary_pattern=(
            materializer.FIXED_BOUNDARY_PATTERN.left_gap,
            materializer.FIXED_BOUNDARY_PATTERN.bottom_gap,
        ),
        protected_rectangle=selection.protected_rectangle,
        backbone_vertical_lanes=materializer.BACKBONE_VERTICAL_LANES,
        backbone_horizontal_lanes=materializer.BACKBONE_HORIZONTAL_LANES,
        backbone_cell_count=materializer.BACKBONE_CELL_COUNT,
        declared_signature_counts=dict(signature_counts),
    )
    payload, local_validation = materializer.materialize_explicit_bundle(bundle, snapshot=snapshot)
    _assert_materializer_validation_counts(local_validation)
    dry_validation = materializer.dry_routing_precheck_only(
        payload,
        snapshot=snapshot,
        dependencies=dependencies,
    )
    _assert_dry_validation_counts(dry_validation)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "READY_TO_WRITE" if dry_validation["accepted"] else "DRY_PRECHECK_REJECTED",
        "claim_boundary": "research_fixed_geometry_candidate_only",
        "baseline_head": selection.baseline_head,
        "source_artifacts": [
            {"path": str(source.path), "sha256": source.sha256}
            for source in selection.source_artifacts
        ],
        "pole_count": len(selection.pole_anchors),
        "protected_rectangle": list(selection.protected_rectangle),
        "manufacturing_count": len(replayed),
        "manufacturing_body_cells": len(manufacturing_bodies),
        "occupied_body_cells": len(occupied),
        "main_free_component_cells": len(main),
        "fixed_terminal_front_cells": len(fixed_fronts),
        "manufacturing_active_ports": active_port_count,
        "signature_counts": dict(sorted(signature_counts.items())),
        "connected_front_capacity_histograms": {
            template: {
                f"{inputs},{outputs}": count
                for (inputs, outputs), count in sorted(histogram.items())
            }
            for template, histogram in sorted(capacity_histograms.items())
        },
        "local_validation": local_validation,
        "dry_validation": dry_validation,
        "geometry_output": None,
        "geometry_output_sha256": None,
    }
    return payload, report


def _require_output_scope(path: Path) -> Path:
    target = Path(path).resolve()
    try:
        target.relative_to(RESEARCH_ROOT.resolve(strict=True))
    except ValueError:
        _fail("OUTPUT_SCOPE", str(target))
    return target


def _exact_validation_count(
    validation: Mapping[str, Any],
    field: str,
    expected: int,
    *,
    code: str,
) -> None:
    observed = validation.get(field)
    if type(observed) is not int or observed != expected:
        _fail(code, f"{field}: expected={expected}, observed={observed!r}")


def _assert_materializer_validation_counts(value: object) -> None:
    validation = _mapping(value, "local_validation")
    _exact_validation_count(
        validation,
        "manufacturing_binding_instance_count",
        EXPECTED_MANUFACTURING_COUNT,
        code="LOCAL_BINDING_INSTANCE_COUNT",
    )
    _exact_validation_count(
        validation,
        "manufacturing_binding_port_count",
        EXPECTED_MANUFACTURING_ACTIVE_PORTS,
        code="LOCAL_BINDING_PORT_COUNT",
    )


def _assert_dry_validation_counts(value: object) -> None:
    validation = _mapping(value, "dry_validation")
    accepted = validation.get("accepted")
    if type(accepted) is not bool:
        _fail("DRY_ACCEPTED_FLAG", repr(accepted))
    if accepted:
        _exact_validation_count(
            validation,
            "port_spec_count",
            EXPECTED_TOTAL_ACTIVE_PORTS,
            code="DRY_TOTAL_PORT_COUNT",
        )


def _write_exclusive(path: Path, payload: Mapping[str, Any]) -> tuple[Path, str]:
    raw = _canonical_json_bytes(payload, label=str(path))
    target = _require_output_scope(path)
    parent = target.parent.resolve(strict=True)
    if not parent.is_dir():
        _fail("OUTPUT_PARENT", str(parent))
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
        _fail("OUTPUT_EXISTS", str(target))
    except OSError as exc:
        _fail("OUTPUT_WRITE", str(exc))
    return target, hashlib.sha256(raw).hexdigest()


def _fsync_directory(path: Path) -> None:
    directory_fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _cleanup_unpublished_pending(pending: Path, *, cause: BaseException) -> None:
    try:
        pending.unlink()
    except FileNotFoundError:
        return
    except OSError as cleanup_exc:
        _fail(
            "GEOMETRY_NOT_PUBLISHED_PENDING_CLEANUP",
            (
                f"final geometry was not published; pending={pending}; "
                f"cause={type(cause).__name__}: {cause}; cleanup={cleanup_exc}"
            ),
        )


def _stage_geometry(
    path: Path,
    payload: Mapping[str, Any],
) -> tuple[Path, Path, str]:
    """Durably stage canonical geometry bytes under a hidden same-dir name."""

    target = _require_output_scope(path)
    parent = target.parent.resolve(strict=True)
    if not parent.is_dir():
        _fail("OUTPUT_PARENT", str(parent))
    if target.exists():
        _fail("OUTPUT_EXISTS", str(target))
    raw = _canonical_json_bytes(payload, label=str(target))
    digest = hashlib.sha256(raw).hexdigest()
    pending = parent / (
        f".{target.name}.pending.{os.getpid()}.{secrets.token_hex(16)}"
    )
    try:
        with pending.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        _fail("GEOMETRY_PENDING_COLLISION", str(pending))
    except OSError as exc:
        _cleanup_unpublished_pending(pending, cause=exc)
        _fail("GEOMETRY_PENDING_WRITE", f"pending={pending}: {exc}")
    return pending, target, digest


def _publish_geometry_after_report(
    *,
    geometry_output: Path,
    geometry_payload: Mapping[str, Any],
    report_output: Path,
    report: dict[str, Any],
) -> dict[str, Any]:
    """Persist the commit record, then atomically expose geometry no-replace.

    The report is deliberately durable before the final geometry name can
    exist.  Once ``os.link`` succeeds, later errors explicitly say that the
    geometry is visible instead of misclassifying the transaction as
    unpublished.
    """

    pending, target, digest = _stage_geometry(geometry_output, geometry_payload)
    report["status"] = "MATERIALIZED"
    report["geometry_output"] = str(target)
    report["geometry_output_sha256"] = digest
    report["publication_protocol"] = "durable_report_then_atomic_geometry_hardlink_v1"
    report["publication_commit_condition"] = "final_geometry_exists_with_declared_sha256"
    try:
        _write_exclusive(report_output, report)
    except Exception as exc:
        _cleanup_unpublished_pending(pending, cause=exc)
        _fail(
            "REPORT_PERSISTENCE_UNCONFIRMED_GEOMETRY_NOT_PUBLISHED",
            f"final geometry was not published at {target}; report failure={type(exc).__name__}: {exc}",
        )

    try:
        os.link(pending, target)
    except FileExistsError as exc:
        _cleanup_unpublished_pending(pending, cause=exc)
        _fail(
            "GEOMETRY_LINK_EXISTS_REPORT_PERSISTED",
            f"report is durable but this run did not publish final geometry: {target}",
        )
    except OSError as exc:
        _cleanup_unpublished_pending(pending, cause=exc)
        _fail(
            "GEOMETRY_LINK_FAILED_REPORT_PERSISTED",
            f"report is durable but final geometry was not published: {target}: {exc}",
        )

    try:
        _fsync_directory(target.parent)
    except OSError as exc:
        try:
            pending.unlink()
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            _fail(
                "GEOMETRY_VISIBLE_FSYNC_AND_CLEANUP_FAILED",
                (
                    f"final geometry is visible at {target}, report is durable, directory fsync failed: {exc}; "
                    f"pending cleanup also failed: {cleanup_exc}"
                ),
            )
        _fail(
            "GEOMETRY_VISIBLE_DIRECTORY_FSYNC_FAILED",
            f"final geometry is visible at {target} and report is durable, but directory fsync failed: {exc}",
        )

    try:
        pending.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        _fail(
            "GEOMETRY_PUBLISHED_PENDING_CLEANUP",
            (
                f"final geometry is published and directory-synced at {target}; "
                f"report is durable; hidden pending cleanup failed at {pending}: {exc}"
            ),
        )
    return report


def assemble_selection_file(
    *,
    selection_path: Path,
    expected_selection_sha256: str,
    geometry_output_path: Path,
    report_output_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    root = Path(project_root).resolve(strict=True)
    _repository_head(root)
    geometry_output = _require_output_scope(geometry_output_path)
    report_output = _require_output_scope(report_output_path)
    if geometry_output == report_output:
        _fail("OUTPUT_COLLISION", str(geometry_output))
    if geometry_output.exists() or report_output.exists():
        _fail("OUTPUT_EXISTS", f"{geometry_output} / {report_output}")
    selection = load_selection(selection_path, expected_sha256=expected_selection_sha256)
    snapshot = fixed_router.load_production_input_snapshot(root)
    payload, report = assemble_selection(
        selection,
        snapshot=snapshot,
        dependencies=fixed_router.production_dependencies(),
    )
    if report["dry_validation"]["accepted"]:
        return _publish_geometry_after_report(
            geometry_output=geometry_output,
            geometry_payload=payload,
            report_output=report_output,
            report=report,
        )
    _write_exclusive(report_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--expected-selection-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = assemble_selection_file(
            selection_path=args.selection,
            expected_selection_sha256=args.expected_selection_sha256,
            geometry_output_path=args.out,
            report_output_path=args.report_out,
            project_root=args.project_root,
        )
    except Exception as exc:  # noqa: BLE001 - stable CLI fail-closed boundary
        raise SystemExit(f"{type(exc).__name__}: {exc}") from exc
    print(json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "BaySelection",
    "ConnectedBayAssemblyError",
    "ConnectedBaySelection",
    "LEGACY_SELECTION_SCHEMA_VERSION",
    "REPORT_SCHEMA_VERSION",
    "SELECTION_SCHEMA_VERSION",
    "SelectedPose",
    "SourceArtifact",
    "assemble_selection",
    "assemble_selection_file",
    "load_selection",
    "parse_selection",
]
