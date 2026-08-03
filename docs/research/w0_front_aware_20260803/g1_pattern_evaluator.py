"""W0 front-aware G1: geometry -> capability, the single source of truth.

research-only.  No authority, no bound, no ledger effect.

Everything the master is allowed to know about a pattern is computed here:
which fronts are free, which capability bucket each body lands in, whether the
free space is one corridor, whether the poles cover the region, whether the hole
is legal.  The generator calls it to score its candidates and the catalog loader
calls it again to *recompute* -- a stored signature is never believed.  That is
the whole point of concentrating the semantics in one module: there is exactly
one place where "this body can serve class k" is decided.

Front semantics (T-FRONT-IDENTITY, owner ruling 2026-07-18)
-----------------------------------------------------------
A port's front cell is the **first cell outside the body**.  The retired
``front = port + delta`` formula (second cell outside) caused the 07-18 P0
incident; ``src/placement/placement_generator.get_edge_ports`` now yields the
front cell directly from the edge-normal arithmetic and
``get_port_front_cell`` is the identity.  This module reproduces that arithmetic
and never adds a delta.  ``src/tests/test_w0_g1_pattern_evaluator.py`` pins the
first-cell result and explicitly asserts the second cell is *not* used.

Registered restrictions enforced here
-------------------------------------
``R-PAT-CONN``     free fronts must lie in the portal-connected component
``R-POWER-LOCAL``  every body is covered by a pole of its own region
``T-DEAD-BODY``    a body serving no class is a dead body; patterns forbid them
``T-CAPABILITY-BUCKET``  bucket abstraction, lossless (see ``g1_port_semantics``)
``T-POLE-MINIMAL`` inclusion-minimal cover => the repo irredundancy predicate

Runtime contract: stdlib only, no solver.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from g1_pattern_schema import (
    BodySpec,
    HoleSpec,
    PatternSpec,
    RESEARCH_AUTHORITY,
    SchemaError,
    cells_json,
    mask_sha256,
    require_keys,
    require_research_authority,
    require_schema,
    PATTERN_SCHEMA,
)
from g1_port_semantics import (
    CLASS_TABLE,
    TEMPLATE_PORT_RULE,
    TEMPLATE_SIZES,
    bucket_id_for_servable,
)
from g1_region_model import (
    REGION_CLASSES,
    REGION_SIZE,
    RegionClass,
)

__all__ = [
    "PORT_FRONT_IDENTITY",
    "POLE_SIZE",
    "POLE_COVERAGE_RADIUS",
    "MAX_POLES_PER_REGION",
    "SIDES",
    "ModeSpec",
    "modes_for",
    "template_footprint",
    "body_cells",
    "side_front_cells",
    "is_front_usable",
    "portal_component",
    "power_local_ok",
    "dead_for_any_actual_class",
    "minimize_poles",
    "evaluate_body",
    "BodyEvaluation",
    "PatternEvaluation",
    "evaluate_pattern",
    "pattern_to_json",
    "load_pattern",
    "PatternRejected",
]

Cell = Tuple[int, int]

#: T-FRONT-IDENTITY.  ``True`` means: the stored port coordinate already *is* the
#: routable belt cell, one cell outside the body.  Never add a direction delta.
PORT_FRONT_IDENTITY = True

POLE_SIZE = 2
#: ``power_pole.power_coverage_radius`` in ``rules/canonical_rules.json``; the
#: 2x2 body at anchor (a,b) covers [a-5, a+6] x [b-5, b+6], clipped to the board.
POLE_COVERAGE_RADIUS = 5
#: Soft budget used by the generator; the evaluator rejects anything above it.
MAX_POLES_PER_REGION = 3

SIDES: Tuple[str, ...] = ("top", "bottom", "left", "right")


class PatternRejected(SchemaError):
    """A stored pattern disagrees with its recomputation -- fail closed."""


@dataclass(frozen=True)
class ModeSpec:
    """A port mode: ``XY`` means inputs on side X, outputs on side Y."""

    mode: str
    in_side: str
    out_side: str


_SQUARE_MODES: Tuple[ModeSpec, ...] = (
    ModeSpec("TB", "top", "bottom"),
    ModeSpec("BT", "bottom", "top"),
    ModeSpec("RL", "right", "left"),
    ModeSpec("LR", "left", "right"),
)
_RECT_MODES_O0: Tuple[ModeSpec, ...] = (
    ModeSpec("TB", "top", "bottom"),
    ModeSpec("BT", "bottom", "top"),
)
_RECT_MODES_O1: Tuple[ModeSpec, ...] = (
    ModeSpec("RL", "right", "left"),
    ModeSpec("LR", "left", "right"),
)


def modes_for(template: str, orientation: int) -> Tuple[ModeSpec, ...]:
    """The modes a placed body offers, mirroring ``placement_generator``.

    Squares (``opposite_parallel_sides``) are enumerated at orientation 0 only --
    rotation equivalence is absorbed by the four modes.  The 6x4 rectangle
    (``long_sides``) puts its ports on the two 6-cell sides, so orientation 0
    offers TB/BT and orientation 1 offers RL/LR.
    """
    rule = TEMPLATE_PORT_RULE[template]
    if rule == "opposite_parallel_sides":
        if orientation != 0:
            raise SchemaError(
                f"{template} is enumerated at orientation 0 only, got {orientation}"
            )
        return _SQUARE_MODES
    if rule == "long_sides":
        if orientation == 0:
            return _RECT_MODES_O0
        if orientation == 1:
            return _RECT_MODES_O1
        raise SchemaError(f"{template} orientation must be 0 or 1, got {orientation}")
    raise SchemaError(f"unsupported port rule {rule!r} for {template}")


def template_footprint(template: str, orientation: int) -> Tuple[int, int]:
    width, height = TEMPLATE_SIZES[template]
    if TEMPLATE_PORT_RULE[template] == "long_sides" and orientation == 1:
        return (height, width)
    return (width, height)


def body_cells(template: str, orientation: int, anchor: Cell) -> Tuple[Cell, ...]:
    width, height = template_footprint(template, orientation)
    ax, ay = anchor
    return tuple((ax + dx, ay + dy) for dx in range(width) for dy in range(height))


def pole_cells(anchor: Cell) -> Tuple[Cell, ...]:
    ax, ay = anchor
    return tuple(
        (ax + dx, ay + dy) for dx in range(POLE_SIZE) for dy in range(POLE_SIZE)
    )


def side_front_cells(
    template: str, orientation: int, anchor: Cell, side: str
) -> Tuple[Cell, ...]:
    """The front cells of one physical side -- first cell outside the body.

    Byte-for-byte the arithmetic of ``get_edge_ports``: top -> ``y + h``,
    bottom -> ``y - 1``, left -> ``x - 1``, right -> ``x + w``.
    """
    width, height = template_footprint(template, orientation)
    ax, ay = anchor
    if side == "top":
        return tuple((ax + index, ay + height) for index in range(width))
    if side == "bottom":
        return tuple((ax + index, ay - 1) for index in range(width))
    if side == "left":
        return tuple((ax - 1, ay + index) for index in range(height))
    if side == "right":
        return tuple((ax + width, ay + index) for index in range(height))
    raise SchemaError(f"unknown side {side!r}")


def second_cell_outside(
    template: str, orientation: int, anchor: Cell, side: str
) -> Tuple[Cell, ...]:
    """The retired ``front + delta`` cells.  Kept only so tests can assert we
    never emit them (07-18 front-offset incident regression anchor)."""
    delta = {"top": (0, 1), "bottom": (0, -1), "left": (-1, 0), "right": (1, 0)}[side]
    return tuple(
        (cell[0] + delta[0], cell[1] + delta[1])
        for cell in side_front_cells(template, orientation, anchor, side)
    )


def is_front_usable(
    cell: Cell,
    occupied: FrozenSet[Cell] | Set[Cell],
    component: FrozenSet[Cell] | Set[Cell],
) -> bool:
    """T-FRONT-FREE plus R-FRONT-IN-REGION plus R-PAT-CONN.

    A front counts only if it is inside its own region (so the master needs no
    seam variable), body-free, and reachable from the region's portal stubs (so
    the belt that will use it is on the global corridor).
    """
    u, v = cell
    if not (0 <= u < REGION_SIZE and 0 <= v < REGION_SIZE):
        return False
    if cell in occupied:
        return False
    return cell in component


def portal_component(
    free_cells: Iterable[Cell], seeds: Iterable[Cell]
) -> FrozenSet[Cell]:
    """The 4-connected component of ``free_cells`` reachable from ``seeds``.

    ``seeds`` are the region's live portal stubs.  R-PAT-CONN additionally
    requires every reserved fixed-furniture front to land in this component; the
    caller checks that.
    """
    free = set(free_cells)
    frontier = deque(cell for cell in seeds if cell in free)
    seen: Set[Cell] = set(frontier)
    while frontier:
        u, v = frontier.popleft()
        for neighbour in ((u + 1, v), (u - 1, v), (u, v + 1), (u, v - 1)):
            if neighbour in free and neighbour not in seen:
                seen.add(neighbour)
                frontier.append(neighbour)
    return frozenset(seen)


def coverage_cells(anchor: Cell, *, clip: Optional[Tuple[int, int, int, int]] = None) -> FrozenSet[Cell]:
    """Pole coverage stencil ``[a-5, a+6] x [b-5, b+6]``, optionally clipped.

    ``clip`` is ``(min_x, min_y, max_x_exclusive, max_y_exclusive)``.  Matches
    ``gen_power_pole``: a 2x2 body centred at ``(a+0.5, b+0.5)`` with radius 5.
    """
    ax, ay = anchor
    low_x, high_x = ax - POLE_COVERAGE_RADIUS, ax + POLE_SIZE + POLE_COVERAGE_RADIUS
    low_y, high_y = ay - POLE_COVERAGE_RADIUS, ay + POLE_SIZE + POLE_COVERAGE_RADIUS
    if clip is not None:
        min_x, min_y, max_x, max_y = clip
        low_x, high_x = max(low_x, min_x), min(high_x, max_x)
        low_y, high_y = max(low_y, min_y), min(high_y, max_y)
    return frozenset(
        (x, y) for x in range(low_x, high_x) for y in range(low_y, high_y)
    )


def power_local_ok(
    bodies_cells: Sequence[Tuple[int, Tuple[Cell, ...]]],
    poles: Sequence[Cell],
) -> bool:
    """R-POWER-LOCAL: every body has at least one cell inside some local pole."""
    stencils = [coverage_cells(anchor) for anchor in poles]
    for _bid, cells in bodies_cells:
        if not any(any(cell in stencil for cell in cells) for stencil in stencils):
            return False
    return True


def minimize_poles(
    bodies_cells: Sequence[Tuple[str, Sequence[Cell]]],
    poles: Sequence[Cell],
    *,
    clip: Optional[Tuple[int, int, int, int]] = None,
) -> Tuple[Cell, ...]:
    """T-POLE-MINIMAL: shrink a covering pole set to an inclusion-minimal one.

    Theorem.  If ``P`` covers every body and no proper subset does, then every
    pole in ``P`` is the *sole* coverer of some body, and those private bodies
    are pairwise distinct -- so ``|P| <= |bodies|``.  That is exactly the repo
    irredundancy predicate (``src/search/pr2_l0_artifact_core.py`` :1030-1041:
    poles <= powered instances, every pole covers something, every pole is some
    instance's unique coverer).  Proof: if pole ``p`` had no private body, every
    body it covers is also covered by another pole, so ``P \\ {p}`` still covers
    everything, contradicting minimality.  Distinctness holds because a body
    private to ``p`` is by definition covered by ``p`` alone.

    Deterministic: candidates are dropped in sorted ``(x, y)`` order, so the same
    input always yields the same minimal set.  Only poles are removed -- bodies
    and the hole are untouched, and freeing a pole's cells can only *add* free
    space, so no front witness is invalidated.
    """
    remaining = list(sorted(set(poles)))
    stencil_cache: Dict[Cell, FrozenSet[Cell]] = {
        anchor: coverage_cells(anchor, clip=clip) for anchor in remaining
    }
    body_cell_sets = [set(cells) for _name, cells in bodies_cells]

    def covers_all(candidates: Sequence[Cell]) -> bool:
        stencils = [stencil_cache[anchor] for anchor in candidates]
        for cells in body_cell_sets:
            if not any(cells & stencil for stencil in stencils):
                return False
        return True

    if not covers_all(remaining):
        raise ValueError("pole set does not cover every body; refusing to minimize")
    for anchor in sorted(set(poles)):
        trial = [item for item in remaining if item != anchor]
        if covers_all(trial):
            remaining = trial
    return tuple(remaining)


# --------------------------------------------------------------------------
# per-body capability
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ModeEvaluation:
    mode: str
    in_side: str
    out_side: str
    free_in_fronts: Tuple[Cell, ...]
    free_out_fronts: Tuple[Cell, ...]
    blocked_in_fronts: Tuple[Cell, ...]
    blocked_out_fronts: Tuple[Cell, ...]

    def as_json(self) -> Dict[str, object]:
        return {
            "mode": self.mode,
            "in_side": self.in_side,
            "out_side": self.out_side,
            "free_in_fronts": cells_json(self.free_in_fronts),
            "free_out_fronts": cells_json(self.free_out_fronts),
            "blocked_in_fronts": cells_json(self.blocked_in_fronts),
            "blocked_out_fronts": cells_json(self.blocked_out_fronts),
        }


@dataclass(frozen=True)
class BodyEvaluation:
    bid: int
    template: str
    orientation: int
    local_anchor: Cell
    bucket: Optional[str]
    servable_classes: Tuple[str, ...]
    mode_table: Tuple[ModeEvaluation, ...]
    class_witness: Mapping[str, Mapping[str, object]]

    @property
    def dead(self) -> bool:
        return self.bucket is None

    def as_json(self) -> Dict[str, object]:
        return {
            "bid": self.bid,
            "template": self.template,
            "orientation": self.orientation,
            "local_anchor": list(self.local_anchor),
            "size": list(template_footprint(self.template, self.orientation)),
            "bucket": self.bucket,
            "servable_classes": list(self.servable_classes),
            "mode_table": [mode.as_json() for mode in self.mode_table],
            "class_witness": {
                class_id: dict(witness)
                for class_id, witness in sorted(self.class_witness.items())
            },
        }


def evaluate_body(
    body: BodySpec,
    occupied: FrozenSet[Cell],
    component: FrozenSet[Cell],
) -> BodyEvaluation:
    mode_table: List[ModeEvaluation] = []
    for spec in modes_for(body.template, body.orientation):
        in_cells = side_front_cells(
            body.template, body.orientation, body.local_anchor, spec.in_side
        )
        out_cells = side_front_cells(
            body.template, body.orientation, body.local_anchor, spec.out_side
        )
        free_in = tuple(c for c in in_cells if is_front_usable(c, occupied, component))
        free_out = tuple(c for c in out_cells if is_front_usable(c, occupied, component))
        mode_table.append(
            ModeEvaluation(
                mode=spec.mode,
                in_side=spec.in_side,
                out_side=spec.out_side,
                free_in_fronts=free_in,
                free_out_fronts=free_out,
                blocked_in_fronts=tuple(c for c in in_cells if c not in free_in),
                blocked_out_fronts=tuple(c for c in out_cells if c not in free_out),
            )
        )

    servable: Set[str] = set()
    witness: Dict[str, Dict[str, object]] = {}
    for row in CLASS_TABLE:
        if row.template != body.template:
            continue
        for evaluation in mode_table:
            if (
                len(evaluation.free_in_fronts) >= row.r_in
                and len(evaluation.free_out_fronts) >= row.r_out
            ):
                servable.add(row.class_id)
                witness[row.class_id] = {
                    "mode": evaluation.mode,
                    "active_in": cells_json(evaluation.free_in_fronts[: row.r_in]),
                    "active_out": cells_json(evaluation.free_out_fronts[: row.r_out]),
                }
                break

    frozen_servable = frozenset(servable)
    bucket = (
        bucket_id_for_servable(body.template, frozen_servable, CLASS_TABLE)
        if frozen_servable
        else None
    )
    return BodyEvaluation(
        bid=body.bid,
        template=body.template,
        orientation=body.orientation,
        local_anchor=body.local_anchor,
        bucket=bucket,
        servable_classes=tuple(sorted(frozen_servable)),
        mode_table=tuple(mode_table),
        class_witness=witness,
    )


def dead_for_any_actual_class(evaluations: Iterable[BodyEvaluation]) -> int:
    """T-DEAD-BODY.  Count bodies that can serve no real operation class.

    The necessary projection document 19 used to sentence the pinned seed to
    death: no mode of this body offers ``(r_in, r_out)`` free front cells for any
    class of its template, therefore no class assignment, routing plan or
    commodity binding can rescue it.  G1's hard indicator is that this count is
    zero -- and here it is zero *by construction*, because a pattern containing a
    dead body is rejected outright rather than counted after the fact.
    """
    return sum(1 for evaluation in evaluations if evaluation.dead)


# --------------------------------------------------------------------------
# whole-pattern evaluation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PatternEvaluation:
    spec: PatternSpec
    region_class: str
    bodies: Tuple[BodyEvaluation, ...]
    poles: Tuple[Cell, ...]
    hole: Optional[HoleSpec]
    bucket_counts: Mapping[str, int]
    free_cells: FrozenSet[Cell]
    component: FrozenSet[Cell]
    violations: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def signature(self) -> Tuple[Tuple[Tuple[str, int], ...], bool]:
        """What the master sees.  Two patterns with equal signatures are
        interchangeable, which is the whole basis of catalog deduplication."""
        return (
            tuple(sorted(self.bucket_counts.items())),
            self.hole is not None,
        )

    @property
    def body_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for body in self.bodies:
            counts[body.template] = counts.get(body.template, 0) + 1
        return counts


INVARIANTS: Tuple[str, ...] = (
    "R-BODY-IN-REGION",
    "R-FRONT-IN-REGION",
    "R-PORTAL-FIXED",
    "R-CORE-FRONT-RESERVE",
    "R-PAT-CONN",
    "R-POWER-LOCAL",
    "R-HOLE-IN-REGION",
    "T-DEAD-BODY-ZERO",
)


def evaluate_pattern(
    spec: PatternSpec, *, region_class: Optional[RegionClass] = None
) -> PatternEvaluation:
    """Recompute every derived property of a pattern from its decision content."""
    region = region_class or REGION_CLASSES.get(spec.region_class)
    if region is None:
        raise SchemaError(f"unknown region class {spec.region_class!r}")

    violations: List[str] = []
    occupied: Set[Cell] = set(region.fixed_local)
    overlap = False
    out_of_region = False

    placed: List[Tuple[int, Tuple[Cell, ...]]] = []
    for body in spec.bodies:
        cells = body_cells(body.template, body.orientation, body.local_anchor)
        placed.append((body.bid, cells))
        for cell in cells:
            if not (0 <= cell[0] < REGION_SIZE and 0 <= cell[1] < REGION_SIZE):
                out_of_region = True
                continue
            if cell in occupied:
                overlap = True
            occupied.add(cell)
    for pole in spec.poles:
        for cell in pole_cells(pole.local_anchor):
            if not (0 <= cell[0] < REGION_SIZE and 0 <= cell[1] < REGION_SIZE):
                out_of_region = True
                continue
            if cell in occupied:
                overlap = True
            occupied.add(cell)
    if out_of_region or overlap:
        violations.append("R-BODY-IN-REGION")

    frozen_occupied = frozenset(occupied)
    free_cells = frozenset(
        (u, v)
        for u in range(REGION_SIZE)
        for v in range(REGION_SIZE)
        if (u, v) not in frozen_occupied
    )

    live_stubs = region.live_stubs
    if any(stub in frozen_occupied for stub in live_stubs):
        violations.append("R-PORTAL-FIXED")
    fixed_fronts = region.fixed_front_local
    if any(cell in frozen_occupied for cell in fixed_fronts):
        violations.append("R-CORE-FRONT-RESERVE")

    component = portal_component(free_cells, live_stubs)
    anchors = set(live_stubs) | set(fixed_fronts)
    if any(cell not in component for cell in anchors if cell in free_cells):
        violations.append("R-PAT-CONN")

    evaluations = tuple(
        evaluate_body(body, frozen_occupied, component) for body in spec.bodies
    )
    if dead_for_any_actual_class(evaluations):
        violations.append("T-DEAD-BODY-ZERO")
    if any(
        cell not in component
        for evaluation in evaluations
        for mode in evaluation.mode_table
        for cell in mode.free_in_fronts + mode.free_out_fronts
    ):  # pragma: no cover - is_front_usable already guarantees this
        violations.append("R-FRONT-IN-REGION")

    pole_anchors = tuple(pole.local_anchor for pole in spec.poles)
    power_ok = len(pole_anchors) <= MAX_POLES_PER_REGION
    if spec.bodies:
        # A region with machines needs at least one pole, never more poles than
        # machines (the global minimisation in stage B tightens this further).
        power_ok = power_ok and 1 <= len(pole_anchors) <= len(spec.bodies)
        power_ok = power_ok and power_local_ok(placed, pole_anchors)
    else:
        # Nothing to power: a pole here could never be forced.
        power_ok = power_ok and not pole_anchors
    if not power_ok:
        violations.append("R-POWER-LOCAL")

    if spec.hole is not None:
        hole_cells = set(spec.hole.cells)
        legal = all(
            0 <= cell[0] < REGION_SIZE and 0 <= cell[1] < REGION_SIZE
            for cell in hole_cells
        )
        if not legal or hole_cells & frozen_occupied or not hole_cells <= component:
            violations.append("R-HOLE-IN-REGION")

    bucket_counts: Dict[str, int] = {}
    for evaluation in evaluations:
        if evaluation.bucket is not None:
            bucket_counts[evaluation.bucket] = bucket_counts.get(evaluation.bucket, 0) + 1

    return PatternEvaluation(
        spec=spec,
        region_class=region.name,
        bodies=evaluations,
        poles=pole_anchors,
        hole=spec.hole,
        bucket_counts=bucket_counts,
        free_cells=free_cells,
        component=component,
        violations=tuple(dict.fromkeys(violations)),
    )


def pattern_to_json(
    evaluation: PatternEvaluation, *, generator: Optional[Mapping[str, object]] = None
) -> Dict[str, object]:
    """Serialise a validated pattern, decision content first, derived data after."""
    if not evaluation.ok:
        raise PatternRejected(
            f"refusing to serialise an invalid pattern: {list(evaluation.violations)}"
        )
    spec = evaluation.spec
    payload: Dict[str, object] = {
        "schema": PATTERN_SCHEMA,
        "authority": dict(RESEARCH_AUTHORITY),
        "region_class": spec.region_class,
        "pattern_id": spec.pattern_id,
        "spec": spec.as_json(),
        "signature": {
            "bucket_counts": dict(sorted(evaluation.bucket_counts.items())),
            "hole": evaluation.hole is not None,
        },
        "bodies": [body.as_json() for body in evaluation.bodies],
        "poles": [
            {"local_anchor": list(anchor), "covers_bids": _covered_bids(anchor, evaluation)}
            for anchor in evaluation.poles
        ],
        "hole": None if spec.hole is None else spec.hole.as_json(),
        "reserved_free": cells_json(sorted(REGION_CLASSES[spec.region_class].reserved_local)),
        "free_space": {
            "portal_component_size": len(evaluation.component),
            "portal_component_sha256": mask_sha256(evaluation.component),
        },
        "invariants": list(INVARIANTS),
        "generator": dict(generator or {}),
    }
    return payload


def _covered_bids(anchor: Cell, evaluation: PatternEvaluation) -> List[int]:
    stencil = coverage_cells(anchor)
    covered = []
    for body in evaluation.bodies:
        cells = body_cells(body.template, body.orientation, body.local_anchor)
        if any(cell in stencil for cell in cells):
            covered.append(body.bid)
    return sorted(covered)


def load_pattern(payload: object, *, region_class: Optional[str] = None) -> PatternEvaluation:
    """Parse a stored pattern and **recompute** everything it claims.

    Catalog loader iron rule: a stored signature is evidence of nothing.  If the
    recomputed bucket counts, hole flag, pattern id or portal component digest
    disagree with the file, the whole catalog is rejected -- no repair, no
    warning-and-continue.
    """
    obj = require_keys(
        payload,
        (
            "schema",
            "authority",
            "region_class",
            "pattern_id",
            "spec",
            "signature",
            "bodies",
            "poles",
            "hole",
            "reserved_free",
            "free_space",
            "invariants",
            "generator",
        ),
        what="pattern",
    )
    require_schema(obj, PATTERN_SCHEMA, what="pattern")
    require_research_authority(obj, what="pattern")
    spec = PatternSpec.from_json(obj["spec"], what="pattern.spec")
    if region_class is not None and spec.region_class != region_class:
        raise PatternRejected(
            f"pattern declares region class {spec.region_class!r}, catalog is "
            f"{region_class!r}"
        )
    if obj["region_class"] != spec.region_class:
        raise PatternRejected("pattern.region_class disagrees with pattern.spec")
    if obj["pattern_id"] != spec.pattern_id:
        raise PatternRejected(
            f"pattern_id {obj['pattern_id']!r} is not the content address of the spec "
            f"({spec.pattern_id!r})"
        )

    evaluation = evaluate_pattern(spec)
    if not evaluation.ok:
        raise PatternRejected(
            f"stored pattern violates {list(evaluation.violations)} on recomputation"
        )

    stored_signature = obj["signature"]
    recomputed = {
        "bucket_counts": dict(sorted(evaluation.bucket_counts.items())),
        "hole": evaluation.hole is not None,
    }
    if stored_signature != recomputed:
        raise PatternRejected(
            f"stored signature {stored_signature!r} != recomputed {recomputed!r}"
        )
    stored_free = obj["free_space"]
    if stored_free != {
        "portal_component_size": len(evaluation.component),
        "portal_component_sha256": mask_sha256(evaluation.component),
    }:
        raise PatternRejected("stored free_space digest != recomputed portal component")
    return evaluation
