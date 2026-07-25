"""Geometry primitives for the routing-aware 70x70 research witness.

This module is deliberately research-only.  It contains no release-evidence or
release-surface code, and it treats the strict clean-room instance as the
semantic authority.  In particular, coordinates stored in
``candidate_placements.json`` under ``*_port_cells`` are already access/front
cells.  They must *not* be shifted by their direction a second time.

The helpers are deterministic and side-effect free except for ``GeometryTabu``,
which is an in-memory set used by the construction loop.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Iterable, Mapping, Sequence

Cell = tuple[int, int]
Anchor = tuple[int, int]

GRID_WIDTH = 70
GRID_HEIGHT = 70
BOUNDARY_BODY_LENGTH = 3
BOUNDARY_INSTANCE_COUNT = 46
POWER_X_MIN_OFFSET = -5
POWER_X_MAX_OFFSET = 6
POWER_Y_MIN_OFFSET = -5
POWER_Y_MAX_OFFSET = 6

_DIRECTION_DELTA: Mapping[str, Cell] = {
    "N": (0, 1),
    "S": (0, -1),
    "E": (1, 0),
    "W": (-1, 0),
}


class GeometryContractError(ValueError):
    """Raised when a geometry helper receives an inconsistent contract."""


def _exact_int(value: Any, field_name: str) -> int:
    if type(value) is not int:
        raise GeometryContractError(f"{field_name} must be an exact integer")
    return value


def _cell(value: Any, field_name: str) -> Cell:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        raise GeometryContractError(f"{field_name} must be a two-integer cell")
    return (_exact_int(value[0], f"{field_name}[0]"), _exact_int(value[1], f"{field_name}[1]"))


def cells_in_grid(cells: Iterable[Cell], *, width: int = GRID_WIDTH, height: int = GRID_HEIGHT) -> bool:
    """Return whether every cell is inside the half-open grid rectangle."""

    return all(0 <= x < width and 0 <= y < height for x, y in cells)


@dataclass(frozen=True, order=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        for name in ("x", "y", "width", "height"):
            _exact_int(getattr(self, name), f"Rect.{name}")
        if self.width <= 0 or self.height <= 0:
            raise GeometryContractError("rectangle dimensions must be positive")

    @property
    def cells(self) -> frozenset[Cell]:
        return frozenset(
            (x, y)
            for x in range(self.x, self.x + self.width)
            for y in range(self.y, self.y + self.height)
        )

    def in_grid(self, *, width: int = GRID_WIDTH, height: int = GRID_HEIGHT) -> bool:
        return self.x >= 0 and self.y >= 0 and self.x + self.width <= width and self.y + self.height <= height


# ---------------------------------------------------------------------------
# Exact 47-pattern boundary reduction
# ---------------------------------------------------------------------------


def boundary_gap_values() -> tuple[int, ...]:
    """The 24 possible uncovered coordinates on one length-70 boundary."""

    return tuple(range(0, GRID_HEIGHT, BOUNDARY_BODY_LENGTH))


def boundary_anchors(gap: int) -> tuple[int, ...]:
    """Return the 23 length-three body anchors leaving exactly ``gap`` free.

    Bodies before the gap start at ``0, 3, ...``.  Bodies after it start at
    ``gap + 1``; this one-cell phase shift is essential for the exact reduction.
    """

    gap = _exact_int(gap, "gap")
    if gap not in boundary_gap_values():
        raise GeometryContractError("boundary gap must be one of 0,3,...,69")
    anchors = tuple(range(0, gap, BOUNDARY_BODY_LENGTH)) + tuple(
        gap + 1 + BOUNDARY_BODY_LENGTH * k
        for k in range(23 - gap // BOUNDARY_BODY_LENGTH)
    )
    if len(anchors) != 23 or any(anchor < 0 or anchor > 67 for anchor in anchors):
        raise AssertionError("internal boundary-anchor construction failure")
    return anchors


@dataclass(frozen=True, order=True)
class BoundaryPattern:
    left_gap: int
    bottom_gap: int

    def __post_init__(self) -> None:
        if self.left_gap not in boundary_gap_values() or self.bottom_gap not in boundary_gap_values():
            raise GeometryContractError("boundary gaps must be in {0,3,...,69}")
        if self.left_gap != 0 and self.bottom_gap != 0:
            raise GeometryContractError("a legal pattern must leave the corner free on at least one edge")

    @property
    def pattern_id(self) -> str:
        return f"left-gap-{self.left_gap:02d}__bottom-gap-{self.bottom_gap:02d}"


def enumerate_boundary_patterns(
    *, preferred: BoundaryPattern | tuple[int, int] | None = None
) -> tuple[BoundaryPattern, ...]:
    """Enumerate the exact 47 patterns, optionally moving one pattern first."""

    patterns = tuple(
        [BoundaryPattern(0, gap) for gap in boundary_gap_values()]
        + [BoundaryPattern(gap, 0) for gap in boundary_gap_values() if gap != 0]
    )
    if len(patterns) != 47 or len(set(patterns)) != 47:
        raise AssertionError("the exact boundary reduction must contain 47 patterns")
    if preferred is None:
        return patterns
    if not isinstance(preferred, BoundaryPattern):
        preferred = BoundaryPattern(*preferred)
    return (preferred,) + tuple(pattern for pattern in patterns if pattern != preferred)


@dataclass(frozen=True)
class BoundaryPlacement:
    instance_id: str
    side: str
    mode: str
    anchor: Anchor
    body_cells: frozenset[Cell]
    front_cells: frozenset[Cell]


def place_boundary_instances(
    instance_ids: Iterable[str], pattern: BoundaryPattern
) -> tuple[BoundaryPlacement, ...]:
    """Assign 46 IDs to the pattern in stable ``left, bottom`` anchor order."""

    ids = tuple(sorted(str(instance_id) for instance_id in instance_ids))
    if len(ids) != BOUNDARY_INSTANCE_COUNT or len(set(ids)) != len(ids):
        raise GeometryContractError("boundary placement requires 46 distinct instance IDs")

    slots: list[tuple[int, int, str, str, Anchor, frozenset[Cell], frozenset[Cell]]] = []
    for anchor_y in boundary_anchors(pattern.left_gap):
        body = frozenset((0, y) for y in range(anchor_y, anchor_y + 3))
        slots.append((0, anchor_y, "left", "left_boundary", (0, anchor_y), body, frozenset({(1, anchor_y + 1)})))
    for anchor_x in boundary_anchors(pattern.bottom_gap):
        body = frozenset((x, 0) for x in range(anchor_x, anchor_x + 3))
        slots.append(
            (1, anchor_x, "bottom", "bottom_boundary", (anchor_x, 0), body, frozenset({(anchor_x + 1, 1)}))
        )
    slots.sort(key=lambda item: (item[0], item[1]))

    placements = tuple(
        BoundaryPlacement(
            instance_id=instance_id,
            side=slot[2],
            mode=slot[3],
            anchor=slot[4],
            body_cells=slot[5],
            front_cells=slot[6],
        )
        for instance_id, slot in zip(ids, slots, strict=True)
    )
    all_body = [cell for placement in placements for cell in placement.body_cells]
    if len(all_body) != 138 or len(set(all_body)) != 138:
        raise AssertionError("a legal boundary pattern must occupy 138 distinct cells")
    return placements


# ---------------------------------------------------------------------------
# Corridor templates and collision/front contracts
# ---------------------------------------------------------------------------


def _rect_ring(body: Rect) -> frozenset[Cell]:
    outer = Rect(body.x - 1, body.y - 1, body.width + 2, body.height + 2)
    return outer.cells - body.cells


def _internal_vertical_line(x: int, height: int) -> set[Cell]:
    return {(x, y) for y in range(1, height)}


def _internal_horizontal_line(y: int, width: int) -> set[Cell]:
    return {(x, y) for x in range(1, width)}


def four_connected(cells: Iterable[Cell]) -> bool:
    """Whether a nonempty cell set is connected by four-neighbour moves."""

    remaining = set(cells)
    if not remaining:
        return False
    start = min(remaining, key=lambda cell: (cell[1], cell[0]))
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for neighbour in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if neighbour in remaining and neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return len(seen) == len(remaining)


@dataclass(frozen=True)
class CorridorTemplate:
    name: str
    width: int
    height: int
    corridor_cells: frozenset[Cell]
    vertical_lanes: tuple[int, ...]
    horizontal_lanes: tuple[int, ...]
    cross_bays: frozenset[Cell]
    core_anchor: Anchor
    core_body_cells: frozenset[Cell]
    core_ring_cells: frozenset[Cell]
    protected_body_rect: Rect

    @property
    def body_reservation_cells(self) -> frozenset[Cell]:
        """Cells that mandatory/auxiliary bodies must leave empty."""

        return self.corridor_cells | self.protected_body_rect.cells


def generate_corridor_template(
    name: str,
    *,
    width: int = GRID_WIDTH,
    height: int = GRID_HEIGHT,
    core_anchor: Anchor = (55, 55),
    protected_anchor: Anchor = (3, 3),
) -> CorridorTemplate:
    """Generate one connected body-reserved routing scaffold.

    ``vertical_comb`` uses horizontal teeth spaced six cells apart;
    ``horizontal_comb`` is its exact transpose.  ``dual_spine_shelf`` uses two
    interior spines and wider shelves.  All three include the inner boundary
    buses (x=1/y=1), a one-cell ring around the 9x9 core, explicit straight
    crossing bays, and a protected body-empty rectangle.  Belts may still use
    cells in that protected rectangle.
    """

    width = _exact_int(width, "width")
    height = _exact_int(height, "height")
    if width < 14 or height < 14:
        raise GeometryContractError("corridor templates require a grid of at least 14x14")
    core_x, core_y = _cell(core_anchor, "core_anchor")
    protected_x, protected_y = _cell(protected_anchor, "protected_anchor")

    if name == "vertical_comb":
        vertical_lanes = tuple(sorted({1, width // 2}))
        horizontal_lanes = tuple(range(1, height, 6))
        protected = Rect(protected_x, protected_y, 6, 7)
    elif name == "horizontal_comb":
        vertical_lanes = tuple(range(1, width, 6))
        horizontal_lanes = tuple(sorted({1, height // 2}))
        protected = Rect(protected_x, protected_y, 7, 6)
    elif name == "dual_spine_shelf":
        vertical_lanes = tuple(sorted({1, width // 3, (2 * width) // 3}))
        horizontal_lanes = tuple(sorted({1, *range(12, height, 11)}))
        protected = Rect(protected_x, protected_y, 6, 7)
    else:
        raise GeometryContractError(
            "corridor template name must be vertical_comb, horizontal_comb, or dual_spine_shelf"
        )

    core_body = Rect(core_x, core_y, 9, 9)
    if not core_body.in_grid(width=width, height=height):
        raise GeometryContractError("the 9x9 core body must be inside the grid")
    if core_x == 0 or core_y == 0 or core_x + 9 >= width or core_y + 9 >= height:
        raise GeometryContractError("the core needs an in-grid one-cell routing ring")
    if not protected.in_grid(width=width, height=height):
        raise GeometryContractError("the protected rectangle must be inside the grid")
    if protected.cells & core_body.cells:
        raise GeometryContractError("the protected rectangle may not overlap the core body")

    corridor: set[Cell] = set()
    for x in vertical_lanes:
        if not 0 < x < width:
            raise GeometryContractError("vertical lanes must be on the inner grid")
        corridor.update(_internal_vertical_line(x, height))
    for y in horizontal_lanes:
        if not 0 < y < height:
            raise GeometryContractError("horizontal lanes must be on the inner grid")
        corridor.update(_internal_horizontal_line(y, width))

    # A lane is allowed to approach the core but never run through its body.
    corridor.difference_update(core_body.cells)
    core_ring = _rect_ring(core_body)
    corridor.update(core_ring)

    # Deterministically connect the lower-left ring corner to the nearest spine.
    ring_connector = (core_body.x - 1, core_body.y - 1)
    nearest_spine = min(vertical_lanes, key=lambda x: (abs(x - ring_connector[0]), x))
    lo, hi = sorted((nearest_spine, ring_connector[0]))
    corridor.update((x, ring_connector[1]) for x in range(lo, hi + 1))
    corridor.difference_update(core_body.cells)

    crosses = {
        (x, y)
        for x in vertical_lanes
        for y in horizontal_lanes
        if (x, y) not in core_body.cells
        and all(
            neighbour in corridor
            for neighbour in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
        )
    }
    if not cells_in_grid(corridor, width=width, height=height):
        raise AssertionError("corridor generation produced an out-of-grid cell")
    if corridor & core_body.cells:
        raise AssertionError("corridor generation crossed the core body")
    if not core_ring <= corridor or not four_connected(corridor):
        raise AssertionError("corridor and core ring must form one connected component")

    return CorridorTemplate(
        name=name,
        width=width,
        height=height,
        corridor_cells=frozenset(corridor),
        vertical_lanes=vertical_lanes,
        horizontal_lanes=horizontal_lanes,
        cross_bays=frozenset(crosses),
        core_anchor=(core_x, core_y),
        core_body_cells=core_body.cells,
        core_ring_cells=core_ring,
        protected_body_rect=protected,
    )


@dataclass(frozen=True)
class PoseGeometry:
    body_cells: frozenset[Cell]
    input_front_cells: tuple[Cell, ...]
    output_front_cells: tuple[Cell, ...]

    @property
    def all_front_cells(self) -> tuple[Cell, ...]:
        return self.input_front_cells + self.output_front_cells


def _candidate_ports(pose: Mapping[str, Any], field_name: str) -> tuple[Cell, ...]:
    ports = pose.get(field_name) or []
    result: list[Cell] = []
    for index, port in enumerate(ports):
        if not isinstance(port, Mapping):
            raise GeometryContractError(f"{field_name}[{index}] must be an object")
        # Identity front semantics: x/y are already the belt/access cell.
        result.append(
            (
                _exact_int(port.get("x"), f"{field_name}[{index}].x"),
                _exact_int(port.get("y"), f"{field_name}[{index}].y"),
            )
        )
    return tuple(result)


def candidate_pose_geometry(pose: Mapping[str, Any]) -> PoseGeometry:
    """Decode a current candidate-pool pose without double-offsetting fronts."""

    raw_body = pose.get("occupied_cells") or []
    body = frozenset(_cell(value, f"occupied_cells[{index}]") for index, value in enumerate(raw_body))
    if not body:
        raise GeometryContractError("candidate pose body must be nonempty")
    return PoseGeometry(
        body_cells=body,
        input_front_cells=_candidate_ports(pose, "input_port_cells"),
        output_front_cells=_candidate_ports(pose, "output_port_cells"),
    )


def strict_mode_geometry(mode: Mapping[str, Any], anchor: Anchor) -> PoseGeometry:
    """Decode strict relative body/port geometry at an anchor."""

    anchor_x, anchor_y = _cell(anchor, "anchor")
    body_record = mode.get("body")
    if not isinstance(body_record, Mapping):
        raise GeometryContractError("strict mode body must be an object")
    body_width = _exact_int(body_record.get("width"), "mode.body.width")
    body_height = _exact_int(body_record.get("height"), "mode.body.height")
    body = Rect(anchor_x, anchor_y, body_width, body_height).cells
    inputs: list[Cell] = []
    outputs: list[Cell] = []
    for index, port in enumerate(mode.get("ports") or []):
        if not isinstance(port, Mapping) or not isinstance(port.get("body_cell"), Mapping):
            raise GeometryContractError(f"mode.ports[{index}] is malformed")
        body_cell = port["body_cell"]
        bx = anchor_x + _exact_int(body_cell.get("x"), f"mode.ports[{index}].body_cell.x")
        by = anchor_y + _exact_int(body_cell.get("y"), f"mode.ports[{index}].body_cell.y")
        direction = str(port.get("direction"))
        if direction not in _DIRECTION_DELTA:
            raise GeometryContractError(f"mode.ports[{index}].direction is invalid")
        dx, dy = _DIRECTION_DELTA[direction]
        target = (bx + dx, by + dy)
        kind = str(port.get("kind"))
        if kind == "input":
            inputs.append(target)
        elif kind == "output":
            outputs.append(target)
        else:
            raise GeometryContractError(f"mode.ports[{index}].kind is invalid")
    return PoseGeometry(body, tuple(inputs), tuple(outputs))


@dataclass(frozen=True)
class CollisionReport:
    body_out_of_grid: frozenset[Cell]
    body_overlap: frozenset[Cell]
    body_on_reserved_front: frozenset[Cell]
    body_on_forbidden: frozenset[Cell]
    front_out_of_grid: frozenset[Cell]
    front_blocked_by_body: frozenset[Cell]

    @property
    def body_ok(self) -> bool:
        return not (
            self.body_out_of_grid
            or self.body_overlap
            or self.body_on_reserved_front
            or self.body_on_forbidden
        )

    @property
    def fronts_ok(self) -> bool:
        return not self.front_out_of_grid and not self.front_blocked_by_body

    @property
    def ok(self) -> bool:
        return self.body_ok and self.fronts_ok


def collision_report(
    pose: PoseGeometry,
    *,
    occupied_body_cells: Iterable[Cell] = (),
    reserved_active_front_cells: Iterable[Cell] = (),
    forbidden_body_cells: Iterable[Cell] = (),
    width: int = GRID_WIDTH,
    height: int = GRID_HEIGHT,
) -> CollisionReport:
    """Report body/front violations; front/front sharing remains legal."""

    occupied = set(occupied_body_cells)
    reserved_fronts = set(reserved_active_front_cells)
    forbidden = set(forbidden_body_cells)
    body = set(pose.body_cells)
    fronts = set(pose.all_front_cells)
    def in_grid(cell: Cell) -> bool:
        return 0 <= cell[0] < width and 0 <= cell[1] < height

    return CollisionReport(
        body_out_of_grid=frozenset(cell for cell in body if not in_grid(cell)),
        body_overlap=frozenset(body & occupied),
        body_on_reserved_front=frozenset(body & reserved_fronts),
        body_on_forbidden=frozenset(body & forbidden),
        front_out_of_grid=frozenset(cell for cell in fronts if not in_grid(cell)),
        front_blocked_by_body=frozenset(fronts & (occupied | body)),
    )


def g0_eligible(
    pose: PoseGeometry,
    corridor_cells: Iterable[Cell],
    *,
    occupied_body_cells: Iterable[Cell] = (),
    reserved_active_front_cells: Iterable[Cell] = (),
    forbidden_body_cells: Iterable[Cell] = (),
    width: int = GRID_WIDTH,
    height: int = GRID_HEIGHT,
) -> bool:
    """G0: placement is legal and every physical front lies on the corridor."""

    report = collision_report(
        pose,
        occupied_body_cells=occupied_body_cells,
        reserved_active_front_cells=reserved_active_front_cells,
        forbidden_body_cells=forbidden_body_cells,
        width=width,
        height=height,
    )
    return report.ok and set(pose.all_front_cells) <= set(corridor_cells)


@dataclass(frozen=True)
class G1Selection:
    input_front_cells: tuple[Cell, ...]
    output_front_cells: tuple[Cell, ...]

    @property
    def active_front_cells(self) -> tuple[Cell, ...]:
        return self.input_front_cells + self.output_front_cells


def select_g1_fronts(
    pose: PoseGeometry,
    corridor_cells: Iterable[Cell],
    *,
    required_inputs: int,
    required_outputs: int,
    occupied_body_cells: Iterable[Cell] = (),
    reserved_active_front_cells: Iterable[Cell] = (),
    forbidden_body_cells: Iterable[Cell] = (),
    width: int = GRID_WIDTH,
    height: int = GRID_HEIGHT,
) -> G1Selection | None:
    """G1: choose the required number of anonymous in/out fronts on corridor.

    The choice is row-major deterministic.  Existing front reservations do not
    block a front (two opposite ports may share one belt cell); facility bodies
    do block it.
    """

    required_inputs = _exact_int(required_inputs, "required_inputs")
    required_outputs = _exact_int(required_outputs, "required_outputs")
    if required_inputs < 0 or required_outputs < 0:
        raise GeometryContractError("G1 front requirements must be nonnegative")
    report = collision_report(
        pose,
        occupied_body_cells=occupied_body_cells,
        reserved_active_front_cells=reserved_active_front_cells,
        forbidden_body_cells=forbidden_body_cells,
        width=width,
        height=height,
    )
    if not report.body_ok:
        return None
    occupied = set(occupied_body_cells) | set(pose.body_cells)
    corridor = set(corridor_cells)

    def candidates(fronts: Sequence[Cell]) -> tuple[Cell, ...]:
        return tuple(
            sorted(
                (
                    cell
                    for cell in fronts
                    if 0 <= cell[0] < width
                    and 0 <= cell[1] < height
                    and cell not in occupied
                    and cell in corridor
                ),
                key=lambda cell: (cell[1], cell[0]),
            )
        )

    inputs = candidates(pose.input_front_cells)
    outputs = candidates(pose.output_front_cells)
    if len(inputs) < required_inputs or len(outputs) < required_outputs:
        return None
    return G1Selection(inputs[:required_inputs], outputs[:required_outputs])


def g1_eligible(*args: Any, **kwargs: Any) -> bool:
    """Boolean form of :func:`select_g1_fronts`."""

    return select_g1_fronts(*args, **kwargs) is not None


# ---------------------------------------------------------------------------
# Power-pole bay lattice and exact minimum set cover
# ---------------------------------------------------------------------------


def pole_footprint(anchor: Anchor) -> frozenset[Cell]:
    anchor_x, anchor_y = _cell(anchor, "pole_anchor")
    return frozenset(
        {(anchor_x, anchor_y), (anchor_x + 1, anchor_y), (anchor_x, anchor_y + 1), (anchor_x + 1, anchor_y + 1)}
    )


def pole_coverage_cells(
    anchor: Anchor, *, width: int = GRID_WIDTH, height: int = GRID_HEIGHT
) -> frozenset[Cell]:
    """The canonical clipped 12x12 ``[-5,+6]`` pole stencil."""

    anchor_x, anchor_y = _cell(anchor, "pole_anchor")
    return frozenset(
        (x, y)
        for x in range(max(0, anchor_x + POWER_X_MIN_OFFSET), min(width - 1, anchor_x + POWER_X_MAX_OFFSET) + 1)
        for y in range(max(0, anchor_y + POWER_Y_MIN_OFFSET), min(height - 1, anchor_y + POWER_Y_MAX_OFFSET) + 1)
    )


def pole_bay_lattice(
    *,
    width: int = GRID_WIDTH,
    height: int = GRID_HEIGHT,
    origin: Anchor = (0, 0),
    pitch: Anchor = (6, 6),
    forbidden_body_cells: Iterable[Cell] = (),
) -> tuple[Anchor, ...]:
    """Return a deterministic, pairwise-nonoverlapping 2x2 bay lattice."""

    origin_x, origin_y = _cell(origin, "origin")
    pitch_x, pitch_y = _cell(pitch, "pitch")
    if not 0 <= origin_x < pitch_x or not 0 <= origin_y < pitch_y:
        raise GeometryContractError("lattice origin must be in one pitch period")
    if pitch_x < 2 or pitch_y < 2:
        raise GeometryContractError("pole lattice pitch must keep 2x2 bays disjoint")
    forbidden = set(forbidden_body_cells)
    anchors = tuple(
        (x, y)
        for y in range(origin_y, height - 1, pitch_y)
        for x in range(origin_x, width - 1, pitch_x)
        if not (pole_footprint((x, y)) & forbidden)
    )
    footprints = [pole_footprint(anchor) for anchor in anchors]
    if any(left & right for left, right in combinations(footprints, 2)):
        raise AssertionError("generated pole bays must be pairwise disjoint")
    return anchors


@dataclass(frozen=True)
class PoleCoverResult:
    feasible: bool
    optimal: bool
    selected_anchors: tuple[Anchor, ...]
    uncovered_instance_ids: tuple[str, ...]
    candidate_count: int
    coverage_by_anchor: tuple[tuple[Anchor, tuple[str, ...]], ...]


def minimum_pole_set_cover(
    powered_body_cells: Mapping[str, Iterable[Cell]],
    candidate_anchors: Iterable[Anchor],
    *,
    blocked_body_cells: Iterable[Cell] = (),
    forbidden_pole_cells: Iterable[Cell] = (),
    width: int = GRID_WIDTH,
    height: int = GRID_HEIGHT,
) -> PoleCoverResult:
    """Solve an exact minimum-cardinality pole cover on a legal bay lattice.

    A facility is covered when at least one of its body cells lies in a selected
    pole's canonical stencil.  Candidate pole footprints that touch a facility,
    corridor, protected rectangle, or active front must be supplied through the
    two forbidden-cell sets and are removed before solving.

    The branch-and-bound exhausts this local bay-lattice subproblem.  Its
    ``optimal`` flag describes only that helper result; it is never promoted to
    a claim about the complete layout.  An uncoverable instance yields a
    deterministic infeasible result instead of a partial placement.
    """

    requirements: dict[str, frozenset[Cell]] = {}
    for instance_id, raw_cells in powered_body_cells.items():
        cells = frozenset(_cell(cell, f"powered_body_cells[{instance_id!r}]") for cell in raw_cells)
        if not cells or not cells_in_grid(cells, width=width, height=height):
            raise GeometryContractError(f"powered facility {instance_id!r} has invalid body cells")
        requirements[str(instance_id)] = cells
    if not requirements:
        return PoleCoverResult(True, True, (), (), 0, ())

    blocked = set(blocked_body_cells) | set(forbidden_pole_cells)
    anchors = tuple(sorted(set(_cell(anchor, "candidate_anchor") for anchor in candidate_anchors), key=lambda a: (a[1], a[0])))
    usable: list[Anchor] = []
    footprints: list[frozenset[Cell]] = []
    for anchor in anchors:
        footprint = pole_footprint(anchor)
        if not cells_in_grid(footprint, width=width, height=height) or footprint & blocked:
            continue
        usable.append(anchor)
        footprints.append(footprint)
    if any(left & right for left, right in combinations(footprints, 2)):
        raise GeometryContractError("minimum_pole_set_cover requires a pairwise-disjoint bay lattice")

    ids = tuple(sorted(requirements))
    coverage_masks: list[int] = []
    coverage_ids: list[tuple[str, ...]] = []
    for anchor in usable:
        stencil = pole_coverage_cells(anchor, width=width, height=height)
        covered = tuple(instance_id for instance_id in ids if requirements[instance_id] & stencil)
        coverage_ids.append(covered)
        mask = 0
        for instance_id in covered:
            mask |= 1 << ids.index(instance_id)
        coverage_masks.append(mask)

    coverers_by_bit: dict[int, tuple[int, ...]] = {}
    uncovered_ids: list[str] = []
    for bit, instance_id in enumerate(ids):
        coverers = tuple(index for index, mask in enumerate(coverage_masks) if mask & (1 << bit))
        coverers_by_bit[bit] = coverers
        if not coverers:
            uncovered_ids.append(instance_id)
    coverage_record = tuple((anchor, coverage_ids[index]) for index, anchor in enumerate(usable))
    if uncovered_ids:
        return PoleCoverResult(False, True, (), tuple(uncovered_ids), len(usable), coverage_record)

    full_mask = (1 << len(ids)) - 1

    # Deterministic greedy incumbent.  It is only an upper bound; the recursive
    # search below determines whether fewer poles suffice.
    greedy: list[int] = []
    greedy_uncovered = full_mask
    while greedy_uncovered:
        best_index = max(
            range(len(usable)),
            key=lambda index: ((coverage_masks[index] & greedy_uncovered).bit_count(), -index),
        )
        if not coverage_masks[best_index] & greedy_uncovered:
            raise AssertionError("coverable universe became uncoverable")
        greedy.append(best_index)
        greedy_uncovered &= ~coverage_masks[best_index]

    best: tuple[int, ...] = tuple(sorted(greedy))
    memo_depth: dict[int, int] = {}

    def search(uncovered: int, chosen: tuple[int, ...]) -> None:
        nonlocal best
        if not uncovered:
            normalized = tuple(sorted(chosen))
            if len(normalized) < len(best) or (len(normalized) == len(best) and normalized < best):
                best = normalized
            return
        if len(chosen) >= len(best):
            return
        previous_depth = memo_depth.get(uncovered)
        if previous_depth is not None and previous_depth <= len(chosen):
            return
        memo_depth[uncovered] = len(chosen)

        max_gain = max((mask & uncovered).bit_count() for mask in coverage_masks)
        lower_bound = (uncovered.bit_count() + max_gain - 1) // max_gain
        if len(chosen) + lower_bound >= len(best):
            return

        uncovered_bits = [bit for bit in range(len(ids)) if uncovered & (1 << bit)]
        pivot = min(uncovered_bits, key=lambda bit: (len(coverers_by_bit[bit]), bit))
        branches = sorted(
            coverers_by_bit[pivot],
            key=lambda index: (-(coverage_masks[index] & uncovered).bit_count(), usable[index][1], usable[index][0]),
        )
        for index in branches:
            search(uncovered & ~coverage_masks[index], chosen + (index,))

    search(full_mask, ())
    selected = tuple(usable[index] for index in best)
    return PoleCoverResult(True, True, selected, (), len(usable), coverage_record)


def storage_box_schedule(max_boxes: int = 2) -> tuple[int, ...]:
    """The witness policy: try zero boxes, then one, then two."""

    max_boxes = _exact_int(max_boxes, "max_boxes")
    if not 0 <= max_boxes <= 2:
        raise GeometryContractError("the research witness permits at most two storage boxes")
    return tuple(range(max_boxes + 1))


# ---------------------------------------------------------------------------
# Group quotient ordering and geometry tabu fingerprints
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationGroup:
    operation: str
    template: str
    instance_ids: tuple[str, ...]

    @property
    def multiplicity(self) -> int:
        return len(self.instance_ids)

    @property
    def group_id(self) -> str:
        return self.operation


def build_operation_groups(
    instances: Iterable[Mapping[str, Any]], *, include_special: bool = False
) -> tuple[OperationGroup, ...]:
    """Collapse required instances into deterministic operation groups.

    By default boundary I/O and protocol core are kept out of the quotient,
    matching the strict instance's 17 manufacturing operation groups.
    """

    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for index, instance in enumerate(instances):
        instance_id = instance.get("id", instance.get("instance_id"))
        operation = instance.get("operation", instance.get("operation_type"))
        template = instance.get("template", instance.get("facility_type"))
        if not all(isinstance(value, str) and value for value in (instance_id, operation, template)):
            raise GeometryContractError(f"instances[{index}] lacks id/operation/template")
        if not include_special and not str(template).startswith("manufacturing_"):
            continue
        grouped[(str(operation), str(template))].append(str(instance_id))
    return tuple(
        OperationGroup(operation, template, tuple(sorted(instance_ids)))
        for (operation, template), instance_ids in sorted(grouped.items())
    )


def pose_order_key(pose: Mapping[str, Any]) -> tuple[int, int, str, str, int]:
    """Stable ``(y,x,mode,pose_id,pose_idx)`` ordering for quotient poses."""

    anchor = pose.get("anchor")
    if isinstance(anchor, Mapping):
        x = _exact_int(anchor.get("x"), "pose.anchor.x")
        y = _exact_int(anchor.get("y"), "pose.anchor.y")
    else:
        x = _exact_int(pose.get("x"), "pose.x")
        y = _exact_int(pose.get("y"), "pose.y")
    params = pose.get("pose_params")
    param_mode = params.get("port_mode") if isinstance(params, Mapping) else None
    mode = str(pose.get("mode", pose.get("port_mode", param_mode or "")))
    pose_id = str(pose.get("pose_id", ""))
    raw_index = pose.get("pose_idx", -1)
    pose_index = _exact_int(raw_index, "pose.pose_idx")
    return (y, x, mode, pose_id, pose_index)


def deterministic_assign_group_poses(
    group: OperationGroup, poses: Iterable[Mapping[str, Any]]
) -> tuple[dict[str, Any], ...]:
    """Assign symmetric instance IDs after geometry, never during search."""

    ordered = tuple(sorted((dict(pose) for pose in poses), key=pose_order_key))
    if len(ordered) != group.multiplicity:
        raise GeometryContractError(
            f"group {group.group_id!r} needs {group.multiplicity} poses, got {len(ordered)}"
        )
    result: list[dict[str, Any]] = []
    for instance_id, pose in zip(group.instance_ids, ordered, strict=True):
        record = dict(pose)
        record["id"] = instance_id
        record.setdefault("operation", group.operation)
        record.setdefault("template", group.template)
        result.append(record)
    return tuple(result)


def _fingerprint_record(record: Mapping[str, Any], *, include_instance_ids: bool) -> dict[str, Any]:
    anchor = record.get("anchor")
    if isinstance(anchor, Mapping):
        x = _exact_int(anchor.get("x"), "placement.anchor.x")
        y = _exact_int(anchor.get("y"), "placement.anchor.y")
    else:
        x = _exact_int(record.get("x"), "placement.x")
        y = _exact_int(record.get("y"), "placement.y")
    params = record.get("pose_params")
    param_mode = params.get("port_mode") if isinstance(params, Mapping) else None
    normalized: dict[str, Any] = {
        "template": str(record.get("template", record.get("facility_type", ""))),
        "operation": str(record.get("operation", record.get("operation_type", ""))),
        "anchor": [x, y],
        "mode": str(record.get("mode", record.get("port_mode", param_mode or ""))),
    }
    if "pose_idx" in record:
        normalized["pose_idx"] = _exact_int(record["pose_idx"], "placement.pose_idx")
    if include_instance_ids:
        normalized["id"] = str(record.get("id", record.get("instance_id", "")))
    return normalized


def geometry_fingerprint(
    placements: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    *,
    include_instance_ids: bool = False,
) -> str:
    """Hash a geometry canonically; symmetric group IDs are ignored by default."""

    if isinstance(placements, Mapping):
        records: list[Mapping[str, Any]] = []
        for instance_id, placement in placements.items():
            record = dict(placement)
            record.setdefault("id", str(instance_id))
            records.append(record)
    else:
        records = list(placements)
    normalized = [_fingerprint_record(record, include_instance_ids=include_instance_ids) for record in records]
    normalized.sort(
        key=lambda record: (
            record["template"],
            record["operation"],
            record["anchor"][1],
            record["anchor"][0],
            record["mode"],
            record.get("pose_idx", -1),
            record.get("id", ""),
        )
    )
    raw = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


@dataclass
class GeometryTabu:
    """In-memory exact set of already-attempted geometry fingerprints."""

    fingerprints: set[str] = field(default_factory=set)

    def remember(
        self,
        placements: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
        *,
        include_instance_ids: bool = False,
    ) -> tuple[str, bool]:
        fingerprint = geometry_fingerprint(placements, include_instance_ids=include_instance_ids)
        is_new = fingerprint not in self.fingerprints
        self.fingerprints.add(fingerprint)
        return fingerprint, is_new

    def contains(
        self,
        placements: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
        *,
        include_instance_ids: bool = False,
    ) -> bool:
        return geometry_fingerprint(placements, include_instance_ids=include_instance_ids) in self.fingerprints
