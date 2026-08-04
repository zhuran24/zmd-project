"""W0 front-aware G1: target-driven local CP-SAT pattern generator.

research-only.  No authority, no bound, no ledger effect.

One 14x14 region at a time, one small CP-SAT model per *target*.  A target names
how many bodies of each template the region should hold, at what capability
level, and whether it carries the hole.  The model places bodies, poles and the
hole; the evaluator then recomputes the real capability and the catalog keeps one
representative per signature.

Capability collapses to a single integer (design note)
------------------------------------------------------
For a placed body let ``n_S`` be the number of free front cells on side ``S`` and
let a *pair* be the two opposite sides a mode may use.  Then

    cap = max over pairs with both sides non-empty of max(n_X, n_Y)

decides the whole servable set: a class ``(r_in, r_out)`` is servable iff some
mode covers it, and because every pair appears in both orders the binding
condition reduces to ``min >= 1`` and ``max >= max(r_in, r_out)``.  So the
generator does not need a capability objective at all -- it needs one linear
constraint per side:

    sum_{c in side} conn[c]  >=  required * selected

"at least ``required`` of this side's front cells are on the corridor if this
pose is chosen".  No auxiliary variable, no reification.  A pose therefore
commits to its template, orientation, anchor, which side carries the wide port
face, and the capability level; the four/two same-anchor variants are mutually
exclusive for free through cell exclusivity.  (Until the 2026-08-04 batch the
same constraint was written against ``used`` -- "stays body-free" -- which
counted fronts the belt could never reach; see the next section.)

H-GEN-OBJECTIVE (revised).  The blueprint proposed a linearised "free front
proxy" objective.  Once the front requirement is a *constraint* the proxy is
redundant, and pushing a cheap necessary condition out of the objective and into
the model is exactly the section 0b discipline this line exists to apply.  The
objective is now simply ``minimise sum(used)``: with body counts fixed by the
target, ``sum(used) = body area + 4 * poles``, so it minimises the pole count.

Connectivity is *inside* the model (2026-08-04 fix-and-rerun batch)
------------------------------------------------------------------
It used to be an after-the-fact filter: solve for packing, then let the
evaluator throw away whatever was disconnected.  That is the shape section 0b
calls a heuristic wearing a gate's clothes -- the solver spends its budget
generating patterns that are then discarded, and the discard rate is the only
thing you learn.  R-PAT-CONN is now an exact hard constraint of the CP-SAT model:

* ``conn[c]`` means "cell ``c`` is body-free and on the pattern's one corridor";
* ``conn[c] + used[c] <= 1`` ties it to the packing;
* every live portal stub and every reserved fixed-furniture front is forced
  ``conn = 1``, and so is every cell of the hole when a hole is placed;
* the capability requirement is written against ``conn`` rather than against
  "not occupied": ``sum_{c in side} conn[c] >= required * selected``;
* a single-commodity flow rooted at **one** stub certifies that the whole
  ``conn`` set hangs together.

The single root is the point.  Flowing from every stub at once certifies the
union of the stub-bearing components, which is precisely the loose reading the
2026-08-04 review found in the evaluator; one root is what makes the model say
"one corridor".  The root is the ``(x, y)``-smallest live stub, the same rule
``g1_pattern_evaluator.component_root`` uses, so model and post-check agree on
which corridor they are talking about.

Exactness (why nothing valid is lost).  model -> evaluator: ``conn`` is free and
root-reachable, hence a subset of the evaluator's component, so every front the
model counted is genuinely usable and every selected body is non-dead.
evaluator -> model: given any evaluator-valid pattern, set ``conn`` to the
evaluator's component and every constraint above holds.  The two feasible sets
project onto the same placements, so ``postcheck_divergence`` is 0 by
construction and a non-zero value is an implementation bug, not a finding.

Because a solved target can no longer contain a dead body, the strip-and-derive
recovery path is retired; see ``RETIRED_PATHS``.

Runtime contract: stdlib + ortools.  Single solve at a time, workers <= 4, tiny
models (196 cells plus ~700 flow arcs).  A prod-scale memory profile here would
mean the model is wrong -- stop rather than push through.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, field
import json
from pathlib import Path
import platform
import sys
import time
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from g1_pattern_evaluator import (  # noqa: E402
    MAX_POLES_PER_REGION,
    POLE_SIZE,
    SIDES,
    PatternEvaluation,
    body_cells,
    coverage_cells,
    evaluate_pattern,
    minimize_poles,
    pattern_to_json,
    pole_cells,
    side_front_cells,
    template_footprint,
)
from g1_pattern_schema import (  # noqa: E402
    BodySpec,
    CATALOG_SCHEMA,
    HoleSpec,
    PatternSpec,
    PoleSpec,
    RESEARCH_AUTHORITY,
    dump_canonical,
    mask_sha256,
    sha256_of_bytes,
)
from g1_port_semantics import (  # noqa: E402
    CLASS_TABLE,
    DEFAULT_INSTANCES_PATH,
    DEFAULT_RULES_PATH,
    MANUFACTURING_TEMPLATES,
    TEMPLATE_PORT_RULE,
    summary as port_summary,
)
from g1_region_model import (  # noqa: E402
    REGION_CLASS_ORDER,
    REGION_CLASSES,
    REGION_SIZE,
    RegionClass,
)

__all__ = [
    "TARGET_MENU",
    "FRONT_PROXY_OBJECTIVE",
    "SPINE_LANE",
    "BATCH_RUN_SPINE",
    "HOLE_CELLS",
    "RETIRED_PATHS",
    "GeneratorBlocked",
    "Pose",
    "Target",
    "GeneratorConfig",
    "enumerate_body_poses",
    "enumerate_pole_poses",
    "enumerate_hole_poses",
    "hole_forced_free_credit",
    "build_target_menu",
    "generate_catalog",
    "measure_packing_ceiling",
    "corridor_tax",
    "derive_subsets",
]

Cell = Tuple[int, int]

#: H-TARGET-MENU anchor: the ordered target menu and its centre-band priority.
TARGET_MENU = "H-TARGET-MENU"
#: H-GEN-OBJECTIVE anchor: minimise occupied cells (see module docstring).
FRONT_PROXY_OBJECTIVE = "H-GEN-OBJECTIVE"
#: H-SPINE-LANE anchor: the row 6 / column 6 corridor preference, measured and
#: then switched off.  A/B on CLEAN, 40 centre-band targets, 3 solutions each:
#:   * hard lane (27 of 188 usable cells forced free) -- the entire centre band
#:     of the menu turns infeasible;
#:   * soft lane (objective weight 3) -- 51 distinct valid signatures, best valid
#:     body area 118, 152s;
#:   * off (weight 0)                 -- 82 distinct valid signatures, best valid
#:     body area 134, 126s.
#: The corridor preference is kept at weight 0.  (The A/B was run when
#: connectivity was a post-filter and "strip-and-derive recovers the disconnected
#: solutions more cheaply" was the reason; connectivity is now a hard constraint,
#: so the lane is redundant rather than merely unhelpful.)  The constant stays as
#: the registered anchor and as the knob to re-run the A/B.
SPINE_LANE = "H-SPINE-LANE"
SPINE_OBJECTIVE_WEIGHT = 0

#: The batch's operating reading for the hard spine lane.  ``H-SPINE-LANE`` was
#: measured and switched off (see ``SPINE_LANE``), and every number this batch
#: quotes -- menu sizes, hole budgets, the per-class ``maxK`` credits -- is a
#: ``spine = False`` number.  The CLI keeps ``--hard-spine`` so the A/B can be
#: re-run, but a run that flips it is a different run and has to say so.
BATCH_RUN_SPINE = False

#: Capability levels per template, derived from the class table: a body at level
#: ``L`` has ``max(r_in, r_out) <= L`` reachable, so the levels are exactly the
#: distinct ``max(r_in, r_out)`` values the template's classes require.
TEMPLATE_LEVELS: Dict[str, Tuple[int, ...]] = {
    template: tuple(
        sorted({max(row.r_in, row.r_out) for row in CLASS_TABLE if row.template == template})
    )
    for template in MANUFACTURING_TEMPLATES
}

_TEMPLATE_ORIENTATIONS: Dict[str, Tuple[int, ...]] = {
    template: ((0, 1) if TEMPLATE_PORT_RULE[template] == "long_sides" else (0,))
    for template in MANUFACTURING_TEMPLATES
}

_OPPOSITE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}


def _pair_sides(template: str, orientation: int) -> Tuple[str, ...]:
    """Sides that may carry ports for this template/orientation."""
    if TEMPLATE_PORT_RULE[template] == "opposite_parallel_sides":
        return ("top", "bottom", "left", "right")
    return ("top", "bottom") if orientation == 0 else ("right", "left")


@dataclass(frozen=True)
class Pose:
    """A candidate body placement that has already committed to its port face."""

    template: str
    orientation: int
    anchor: Cell
    wide_side: str
    level: int
    cells: Tuple[Cell, ...]
    wide_variable_cells: Tuple[Cell, ...]
    narrow_variable_cells: Tuple[Cell, ...]
    wide_required: int
    narrow_required: int

    @property
    def key(self) -> Tuple[str, int, Cell, str, int]:
        return (self.template, self.orientation, self.anchor, self.wide_side, self.level)


@dataclass(frozen=True)
class Target:
    """One generator job: counts per (template, level) plus the hole flag."""

    region_class: str
    counts: Tuple[Tuple[str, int, int], ...]  # (template, level, count)
    hole: bool
    profile: str

    @property
    def body_total(self) -> int:
        return sum(count for _t, _l, count in self.counts)

    def as_json(self) -> Dict[str, object]:
        return {
            "region_class": self.region_class,
            "counts": [[t, level, count] for t, level, count in self.counts],
            "hole": self.hole,
            "profile": self.profile,
        }


@dataclass
class GeneratorConfig:
    budget_seconds: float = 5400.0
    target_seconds: float = 2.0
    solutions_per_target: int = 3
    max_derived_subsets: int = 3
    workers: int = 4
    seed: int = 0
    spine: bool = BATCH_RUN_SPINE
    max_targets: Optional[int] = None
    min_bodies: int = 1
    max_bodies: Optional[int] = None
    ceiling_seconds: float = 30.0
    region_classes: Tuple[str, ...] = REGION_CLASS_ORDER

    def as_json(self) -> Dict[str, object]:
        return {
            "budget_seconds": self.budget_seconds,
            "target_seconds": self.target_seconds,
            "solutions_per_target": self.solutions_per_target,
            "max_derived_subsets": self.max_derived_subsets,
            "workers": self.workers,
            "seed": self.seed,
            "spine": self.spine,
            "max_targets": self.max_targets,
            "min_bodies": self.min_bodies,
            "max_bodies": self.max_bodies,
            "ceiling_seconds": self.ceiling_seconds,
            "region_classes": list(self.region_classes),
        }


#: Code paths this batch retired, and why.  Reported verbatim in every manifest.
#: A retired path must announce itself: a counter that quietly reads 0 forever is
#: indistinguishable from a path that ran and found nothing, and the difference is
#: exactly what a reader of the manifest needs.
RETIRED_PATHS: Dict[str, str] = {
    "strip_dead_bodies": (
        "retired 2026-08-04: connectivity is a hard constraint of the target "
        "model, so a solved target cannot contain a dead body and there is "
        "nothing to strip.  The old counter (stripped_to_smaller) is gone rather "
        "than pinned at 0."
    ),
    "post_filter_connectivity_reject": (
        "retired 2026-08-04: R-PAT-CONN used to be enforced by discarding solved "
        "patterns (rejected_connectivity).  It is now in-model; the evaluator "
        "re-check that replaced it is postcheck_divergence, which must be 0."
    ),
}


class GeneratorBlocked(RuntimeError):
    """Meter 2 fired: the solver and the evaluator disagree.  Implementation bug.

    Not a finding and not a science terminal -- the in-model restriction and the
    post-check are supposed to be the same restriction, so a divergence means one
    of them is wrong.  Fail closed rather than write a catalog nobody can read.
    """


@dataclass
class GeneratorStats:
    """Per-region-class counters, including the batch's three alarm meters.

    The three meters are deliberately separate quantities and are never summed:

    1. ``in_model_filter`` -- what the strict connectivity constraint costs
       *inside* the CP model (the "corridor tax").  Measured per accepted pattern
       by recounting its fronts under the retired multi-source reading and taking
       the difference, plus the count of targets that the strict model could not
       satisfy at all.  This is a cost, not an error.
    2. ``postcheck_divergence`` -- solver-produced specs the evaluator refuses.
       Zero by the exactness argument in the module docstring; any non-zero value
       raises ``GeneratorBlocked`` on the spot.
    3. ``retired_paths`` -- see ``RETIRED_PATHS``.
    """

    targets_attempted: int = 0
    targets_feasible: int = 0
    solutions_found: int = 0
    rejected_dead_body: int = 0
    rejected_other: int = 0
    derived_subsets: int = 0
    derived_rejected: int = 0
    duplicate_signatures: int = 0
    solve_seconds: float = 0.0
    violation_counts: Dict[str, int] = field(default_factory=dict)
    # meter 1
    targets_infeasible: int = 0
    targets_unproved: int = 0
    corridor_tax_front_cells: int = 0
    patterns_paying_corridor_tax: int = 0
    target_status_counts: Dict[str, int] = field(default_factory=dict)
    # meter 2
    postcheck_divergence: int = 0

    def as_json(self) -> Dict[str, object]:
        return {
            "targets_attempted": self.targets_attempted,
            "targets_feasible": self.targets_feasible,
            "solutions_found": self.solutions_found,
            "rejected_dead_body": self.rejected_dead_body,
            "rejected_other": self.rejected_other,
            "derived_subsets": self.derived_subsets,
            "derived_rejected": self.derived_rejected,
            "duplicate_signatures": self.duplicate_signatures,
            "solve_seconds": round(self.solve_seconds, 3),
            "violation_counts": dict(sorted(self.violation_counts.items())),
            "alarm_meters": {
                "in_model_filter": {
                    "targets_infeasible": self.targets_infeasible,
                    "targets_unproved": self.targets_unproved,
                    "target_status_counts": dict(sorted(self.target_status_counts.items())),
                    "corridor_tax_front_cells": self.corridor_tax_front_cells,
                    "patterns_paying_corridor_tax": self.patterns_paying_corridor_tax,
                    "reading": (
                        "corridor tax = front cells the retired multi-source "
                        "reading would have counted and the registered "
                        "single-corridor reading does not. targets_infeasible = "
                        "the solver PROVED no pattern exists for that target; "
                        "targets_unproved = it ran out of time and proved "
                        "nothing. The two are never added together and a "
                        "timeout is never reported as a ceiling. All of this is "
                        "the cost of the restriction, not an error."
                    ),
                },
                "postcheck_divergence": {
                    "count": self.postcheck_divergence,
                    "reading": (
                        "solver-produced specs the evaluator refuses. Must be 0; "
                        "a non-zero value raises GeneratorBlocked at the moment "
                        "it happens, so a written catalog always carries 0."
                    ),
                },
                "retired_paths": dict(RETIRED_PATHS),
            },
        }


# --------------------------------------------------------------------------
# candidate enumeration
# --------------------------------------------------------------------------


def spine_cells(region: RegionClass) -> FrozenSet[Cell]:
    """H-SPINE-LANE: row 6 and column 6, minus whatever fixed furniture owns."""
    cells = {(6, v) for v in range(REGION_SIZE)} | {(u, 6) for u in range(REGION_SIZE)}
    return frozenset(cell for cell in cells if cell not in region.fixed_local)


def _forced_free(region: RegionClass, *, spine: bool) -> FrozenSet[Cell]:
    forced = set(region.reserved_local)
    if spine:
        forced |= spine_cells(region)
    return frozenset(forced)


def enumerate_body_poses(
    region: RegionClass, *, spine: bool = False
) -> Tuple[Pose, ...]:
    """Every body pose that could still be legal, with its front-side budgets."""
    blocked = set(region.fixed_local) | set(_forced_free(region, spine=spine))
    poses: List[Pose] = []
    for template in MANUFACTURING_TEMPLATES:
        for orientation in _TEMPLATE_ORIENTATIONS[template]:
            width, height = template_footprint(template, orientation)
            for ax in range(REGION_SIZE - width + 1):
                for ay in range(REGION_SIZE - height + 1):
                    cells = body_cells(template, orientation, (ax, ay))
                    if any(cell in blocked for cell in cells):
                        continue
                    for wide_side in _pair_sides(template, orientation):
                        narrow_side = _OPPOSITE[wide_side]
                        for level in TEMPLATE_LEVELS[template]:
                            pose = _build_pose(
                                region,
                                template,
                                orientation,
                                (ax, ay),
                                wide_side,
                                narrow_side,
                                level,
                                cells,
                            )
                            if pose is not None:
                                poses.append(pose)
    return tuple(poses)


def _build_pose(
    region: RegionClass,
    template: str,
    orientation: int,
    anchor: Cell,
    wide_side: str,
    narrow_side: str,
    level: int,
    cells: Tuple[Cell, ...],
) -> Optional[Pose]:
    sides: Dict[str, Tuple[Tuple[Cell, ...], int]] = {}
    for side, required in ((wide_side, level), (narrow_side, 1)):
        fronts = side_front_cells(template, orientation, anchor, side)
        variable: List[Cell] = []
        available = 0
        for cell in fronts:
            in_region = 0 <= cell[0] < REGION_SIZE and 0 <= cell[1] < REGION_SIZE
            if not in_region or cell in region.fixed_local:
                continue
            available += 1
            variable.append(cell)
        if available < required:
            return None
        sides[side] = (tuple(variable), required)
    return Pose(
        template=template,
        orientation=orientation,
        anchor=anchor,
        wide_side=wide_side,
        level=level,
        cells=cells,
        wide_variable_cells=sides[wide_side][0],
        narrow_variable_cells=sides[narrow_side][0],
        wide_required=level,
        narrow_required=1,
    )


def enumerate_pole_poses(region: RegionClass, *, spine: bool = False) -> Tuple[Cell, ...]:
    blocked = set(region.fixed_local) | set(_forced_free(region, spine=spine))
    anchors: List[Cell] = []
    for ax in range(REGION_SIZE - 1):
        for ay in range(REGION_SIZE - 1):
            if any(cell in blocked for cell in pole_cells((ax, ay))):
                continue
            anchors.append((ax, ay))
    return tuple(anchors)


def hole_forced_free_credit(region: RegionClass, *, spine: bool) -> int:
    """``maxK``: how many of a hole's 42 cells can be paid for by forced-free cells.

    A hole must be body-free, and so must every reserved cell (and, on the hard
    spine lane, every spine cell).  Where the two overlap the hole costs the
    packing budget nothing, so the area filter in ``build_target_menu`` may
    credit the overlap back.  The credit is the *maximum* overlap over the legal
    hole placements of this region class: any smaller value would drop targets
    that are in fact placeable, which is exactly the bug this replaces (the
    filter used to charge the full 42 cells unconditionally).

    Computed, never written down.  With ``spine=False`` it is 2 for ``CLEAN``,
    4 for the boundary and corner classes and 0 for ``CORE`` (which admits no
    hole pose at all); with ``spine=True`` it reaches 13-16.  Hard-coding either
    row would silently mis-filter the moment a mask or the lane changed.
    """
    forced = _forced_free(region, spine=spine)
    best = 0
    for anchor, width, height in enumerate_hole_poses(region):
        cells = {
            (anchor[0] + dx, anchor[1] + dy)
            for dx in range(width)
            for dy in range(height)
        }
        best = max(best, len(cells & forced))
    return best


def enumerate_hole_poses(region: RegionClass) -> Tuple[Tuple[Cell, int, int], ...]:
    """Hole placements that avoid fixed furniture.  Reserved cells are body-free
    anyway, so a hole may legally overlap them."""
    holes: List[Tuple[Cell, int, int]] = []
    for width, height in ((6, 7), (7, 6)):
        for ax in range(REGION_SIZE - width + 1):
            for ay in range(REGION_SIZE - height + 1):
                cells = [
                    (ax + dx, ay + dy) for dx in range(width) for dy in range(height)
                ]
                if any(cell in region.fixed_local for cell in cells):
                    continue
                holes.append(((ax, ay), width, height))
    return tuple(holes)


# --------------------------------------------------------------------------
# target menu
# --------------------------------------------------------------------------


REGION_CELLS_LOCAL = REGION_SIZE * REGION_SIZE
#: The G1 hole vocabulary is a 6x7 or a 7x6 rectangle, so a hole is always 42
#: cells.  Derived from ``enumerate_hole_poses``' shape list, not typed twice.
HOLE_CELLS = 6 * 7

_GLOBAL_SHARE: Dict[str, float] = {
    template: sum(row.count for row in CLASS_TABLE if row.template == template) / 25.0
    for template in MANUFACTURING_TEMPLATES
}


def build_target_menu(
    region: RegionClass,
    *,
    spine: bool = False,
    min_bodies: int = 1,
    max_bodies: Optional[int] = None,
) -> Tuple[Target, ...]:
    """H-TARGET-MENU.

    Enumerate ``(n3, n5, n6)`` count vectors that still fit the region's free
    budget, cross them with two level profiles (``min`` = every body at the
    cheapest level its template needs, ``max`` = every body at the richest) and
    the hole flag, then order by distance from the region's proportional share of
    the global 132 / 49 / 38 census.  Centre-band targets are therefore generated
    first and a budget cut-off leaves a deterministic, reproducible prefix.

    The hole is charged ``42 - maxK`` cells, not 42: forced-free cells are body
    free whether or not the hole covers them, so the overlap is already paid for
    (``hole_forced_free_credit``).  Charging the full 42 dropped targets that fit,
    which is the whole reason this batch re-generates the catalog.

    ``min_bodies`` drops every target below a body count (stage B knob, default 1
    = no filter).  The proportional-share ordering is right when the question is
    "what does an average region look like" and wrong when it is "can a region
    hold ten bodies at all": 219 bodies over the 24 usable regions needs 9.125 on
    average, so a catalog whose densest pattern holds nine is short by
    arithmetic, and the targets that would fix it sit hundreds of ranks out.
    Filtering, rather than reordering, keeps the registered ordering heuristic
    intact and makes the aimed run a separate, nameable pass.
    """
    budget = REGION_CELLS_LOCAL - len(region.fixed_local) - len(_forced_free(region, spine=spine))
    # The hole overlaps forced-free cells for free; see ``hole_forced_free_credit``.
    hole_cost = HOLE_CELLS - hole_forced_free_credit(region, spine=spine)
    share = {
        template: _GLOBAL_SHARE[template] * (region.usable / 188.0)
        for template in MANUFACTURING_TEMPLATES
    }
    targets: List[Tuple[float, Target]] = []
    max_counts = {"manufacturing_3x3": 14, "manufacturing_5x5": 6, "manufacturing_6x4": 6}
    for n3 in range(max_counts["manufacturing_3x3"] + 1):
        for n5 in range(max_counts["manufacturing_5x5"] + 1):
            for n6 in range(max_counts["manufacturing_6x4"] + 1):
                if n3 + n5 + n6 < max(1, min_bodies):
                    continue
                if max_bodies is not None and n3 + n5 + n6 > max_bodies:
                    continue
                area = 9 * n3 + 25 * n5 + 24 * n6 + 4
                if area > budget:
                    continue
                for hole in (False, True):
                    if hole and area + hole_cost > budget:
                        continue
                    for profile in ("min", "max"):
                        counts = []
                        for template, count in (
                            ("manufacturing_3x3", n3),
                            ("manufacturing_5x5", n5),
                            ("manufacturing_6x4", n6),
                        ):
                            if count == 0:
                                continue
                            levels = TEMPLATE_LEVELS[template]
                            level = levels[0] if profile == "min" else levels[-1]
                            counts.append((template, level, count))
                        score = (
                            abs(n3 - share["manufacturing_3x3"])
                            + abs(n5 - share["manufacturing_5x5"])
                            + abs(n6 - share["manufacturing_6x4"])
                            + (0.5 if hole else 0.0)
                            + (0.25 if profile == "max" else 0.0)
                        )
                        targets.append(
                            (
                                score,
                                Target(
                                    region_class=region.name,
                                    counts=tuple(counts),
                                    hole=hole,
                                    profile=profile,
                                ),
                            )
                        )
    targets.sort(key=lambda item: (round(item[0], 6), item[1].as_json()["counts"], item[1].profile, item[1].hole))
    return tuple(target for _score, target in targets)


# --------------------------------------------------------------------------
# CP-SAT per target
# --------------------------------------------------------------------------


def _neighbours(cell: Cell) -> Tuple[Cell, ...]:
    u, v = cell
    return ((u + 1, v), (u - 1, v), (u, v + 1), (u, v - 1))


def _add_connectivity_certificate(
    model: Any,
    conn: Mapping[Cell, Any],
    live_stubs: Sequence[Cell],
    *,
    corridor_capacity: Optional[int] = None,
) -> Optional[Cell]:
    """R-PAT-CONN, part 2: a single-commodity flow proves ``conn`` is one piece.

    One unit of flow is delivered to every ``conn`` cell from **one** source --
    the ``(x, y)``-smallest live stub, matching
    ``g1_pattern_evaluator.component_root``.  Flow may only travel between cells
    that are both on the corridor, so a ``conn`` cell that is not 4-connected to
    the root cannot be served and the model is infeasible.

    Sourcing from every stub at once would certify the *union* of the
    stub-bearing components instead -- the loose reading -- so the single root is
    load bearing, not a simplification.  Returns the root it used (``None`` when
    the class has no live stub at all, which no G1 region class has).

    ``corridor_capacity`` is an upper bound on ``|conn|``; the caller knows one
    that is much tighter than "every cell", because the target fixes the body
    area.  It only sizes the integer domains -- passing a bound that is too small
    would cut off legal corridors, so the caller derives it, never guesses.  The
    neighbour-support constraint is redundant against the flow but propagates far
    earlier, which is the difference between a two-second solve and a timeout.
    """
    cells = sorted(conn)
    if not cells:
        return None
    root = min(live_stubs) if live_stubs else None
    capacity = len(cells) if corridor_capacity is None else max(1, corridor_capacity)
    for cell in cells:
        if cell == root:
            continue
        support = [conn[n] for n in _neighbours(cell) if n in conn]
        model.add(conn[cell] <= sum(support))
    arcs: Dict[Tuple[Cell, Cell], Any] = {}
    for cell in cells:
        for neighbour in _neighbours(cell):
            if neighbour in conn:
                arcs[(cell, neighbour)] = model.new_int_var(
                    0, capacity, f"f_{cell[0]}_{cell[1]}_{neighbour[0]}_{neighbour[1]}"
                )
    for (tail, head), variable in arcs.items():
        model.add(variable <= capacity * conn[tail])
        model.add(variable <= capacity * conn[head])
    source = (
        model.new_int_var(0, capacity, "corridor_source") if root is not None else None
    )
    for cell in cells:
        inflow = [arcs[(n, cell)] for n in _neighbours(cell) if (n, cell) in arcs]
        outflow = [arcs[(cell, n)] for n in _neighbours(cell) if (cell, n) in arcs]
        injected = [source] if (root is not None and cell == root) else []
        model.add(sum(inflow) + sum(injected) - sum(outflow) == conn[cell])
    if root is None:  # pragma: no cover - every G1 region class has live stubs
        for cell in cells:
            model.add(conn[cell] == 0)
    return root


def _solve_target(
    region: RegionClass,
    target: Target,
    poses: Sequence[Pose],
    pole_anchors: Sequence[Cell],
    hole_poses: Sequence[Tuple[Cell, int, int]],
    config: GeneratorConfig,
) -> Tuple[List[PatternSpec], float, str]:
    from ortools.sat.python import cp_model

    wanted: Dict[Tuple[str, int], int] = {
        (template, level): count for template, level, count in target.counts
    }
    usable_poses = [pose for pose in poses if (pose.template, pose.level) in wanted]
    if not usable_poses:
        return [], 0.0, "NO_POSE"

    model = cp_model.CpModel()
    pose_vars = {
        pose.key: model.new_bool_var(f"p{index}") for index, pose in enumerate(usable_poses)
    }
    pole_vars = {
        anchor: model.new_bool_var(f"pole_{anchor[0]}_{anchor[1]}")
        for anchor in pole_anchors
    }
    forced_free = _forced_free(region, spine=config.spine)
    live_stubs = [cell for cell in region.live_stubs if cell not in region.fixed_local]
    fixed_fronts = [
        cell for cell in region.fixed_front_local if cell not in region.fixed_local
    ]

    used: Dict[Cell, Any] = {}
    conn: Dict[Cell, Any] = {}
    covering: Dict[Cell, List[Any]] = {}
    for u in range(REGION_SIZE):
        for v in range(REGION_SIZE):
            cell = (u, v)
            if cell in region.fixed_local:
                continue
            used[cell] = model.new_bool_var(f"u_{u}_{v}")
            conn[cell] = model.new_bool_var(f"c_{u}_{v}")
            covering[cell] = []
    for pose in usable_poses:
        variable = pose_vars[pose.key]
        for cell in pose.cells:
            covering[cell].append(variable)
    for anchor in pole_anchors:
        for cell in pole_cells(anchor):
            covering[cell].append(pole_vars[anchor])
    for cell, occupiers in covering.items():
        if occupiers:
            model.add_at_most_one(occupiers)
            model.add(sum(occupiers) == used[cell])
        else:
            model.add(used[cell] == 0)
        # A corridor cell is a body-free cell.
        model.add(conn[cell] + used[cell] <= 1)
    for cell in forced_free:
        if cell in used:
            model.add(used[cell] == 0)

    for key, count in wanted.items():
        template, level = key
        members = [
            pose_vars[pose.key]
            for pose in usable_poses
            if pose.template == template and pose.level == level
        ]
        model.add(sum(members) == count)

    # R-PAT-CONN, part 1: the anchors are on the corridor by construction.
    for cell in live_stubs:
        model.add(conn[cell] == 1)
    for cell in fixed_fronts:
        model.add(conn[cell] == 1)

    # Capability, written against the corridor: at least `required` of this
    # side's front cells are free *and reachable*, not merely free.
    for pose in usable_poses:
        variable = pose_vars[pose.key]
        for cells, required in (
            (pose.wide_variable_cells, pose.wide_required),
            (pose.narrow_variable_cells, pose.narrow_required),
        ):
            model.add(sum(conn[cell] for cell in cells) >= required * variable)

    # R-POWER-LOCAL: every selected body is covered by a selected local pole.
    stencils = {anchor: coverage_cells(anchor) for anchor in pole_anchors}
    for pose in usable_poses:
        coverers = [
            pole_vars[anchor]
            for anchor in pole_anchors
            if any(cell in stencils[anchor] for cell in pose.cells)
        ]
        model.add_bool_or(coverers + [pose_vars[pose.key].negated()])
    total_bodies = target.body_total
    model.add(sum(pole_vars.values()) >= 1)
    model.add(sum(pole_vars.values()) <= min(MAX_POLES_PER_REGION, total_bodies))

    hole_vars: Dict[Tuple[Cell, int, int], Any] = {}
    if target.hole:
        for spec in hole_poses:
            anchor, width, height = spec
            variable = model.new_bool_var(f"h_{anchor[0]}_{anchor[1]}_{width}x{height}")
            hole_vars[spec] = variable
            for dx in range(width):
                for dy in range(height):
                    cell = (anchor[0] + dx, anchor[1] + dy)
                    # R-HOLE-IN-REGION under the strict reading: the hole is not
                    # merely body-free, it is on the pattern's one corridor.
                    model.add(conn[cell] == 1).only_enforce_if(variable)
        if not hole_vars:
            return [], 0.0, "NO_HOLE_POSE"
        model.add_exactly_one(hole_vars.values())

    # The corridor can never be larger than what the target leaves free: the body
    # area is fixed by the target and at least one 2x2 pole is always placed.
    body_area = sum(
        TEMPLATE_AREAS[template] * count for template, _level, count in target.counts
    )
    _add_connectivity_certificate(
        model,
        conn,
        live_stubs,
        corridor_capacity=len(used) - body_area - POLE_SIZE * POLE_SIZE,
    )

    # H-GEN-OBJECTIVE.  Body area is fixed by the target, so ``sum(used)`` varies
    # only through pole cells: minimising it minimises poles.  (Before this batch
    # the second half of that sentence was "and maximises corridor, which is what
    # the connectivity filter wants"; the corridor is now a constraint, so the
    # objective is only about poles.)  The equivalent narrow form
    # ``minimise sum(pole_vars)`` was measured on twelve CLEAN targets and is
    # *worse* -- 11/12 solved instead of 12/12 under a 5s cap -- so the wide form
    # stays.  ``SPINE_OBJECTIVE_WEIGHT`` is the measured-and-disabled corridor
    # preference (see its definition for the A/B numbers).
    objective = sum(used.values())
    if SPINE_OBJECTIVE_WEIGHT:
        spine = spine_cells(region)
        objective = objective + SPINE_OBJECTIVE_WEIGHT * sum(
            used[cell] for cell in spine if cell in used
        )
    model.minimize(objective)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(config.target_seconds)
    solver.parameters.num_workers = int(config.workers)
    solver.parameters.random_seed = int(config.seed)
    solver.parameters.log_search_progress = False

    found: List[PatternSpec] = []
    elapsed = 0.0
    # The status of the *first* solve is the one that means something about the
    # target: later rounds are deliberately constrained to avoid the solutions
    # already returned, so their INFEASIBLE says "no more", not "none".
    first_status = "NOT_SOLVED"
    for attempt in range(max(1, config.solutions_per_target)):
        start = time.monotonic()
        status = solver.solve(model)
        elapsed += time.monotonic() - start
        if attempt == 0:
            first_status = solver.status_name(status)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        chosen = [pose for pose in usable_poses if solver.value(pose_vars[pose.key])]
        chosen_poles = [anchor for anchor in pole_anchors if solver.value(pole_vars[anchor])]
        hole_spec: Optional[HoleSpec] = None
        for spec, variable in hole_vars.items():
            if solver.value(variable):
                anchor, width, height = spec
                hole_spec = HoleSpec(local_anchor=anchor, width=width, height=height)
                break
        found.append(
            PatternSpec(
                region_class=region.name,
                bodies=tuple(
                    BodySpec(
                        bid=index,
                        template=pose.template,
                        orientation=pose.orientation,
                        local_anchor=pose.anchor,
                    )
                    for index, pose in enumerate(
                        sorted(chosen, key=lambda p: (p.anchor, p.template, p.orientation))
                    )
                ),
                poles=tuple(PoleSpec(local_anchor=anchor) for anchor in sorted(chosen_poles)),
                hole=hole_spec,
            )
        )
        # Forbid this exact selection so the next round returns something new.
        literals = [pose_vars[pose.key] for pose in chosen] + [
            pole_vars[anchor] for anchor in chosen_poles
        ]
        model.add_bool_or([literal.negated() for literal in literals])
    return found, elapsed, first_status


def measure_packing_ceiling(
    region: RegionClass, config: GeneratorConfig, *, seconds: float = 30.0
) -> Dict[str, object]:
    """Maximum manufacturing body area this region class can hold at all.

    One CP-SAT solve per region class with the counts left free and every body at
    its template's cheapest capability level -- so the answer *over*-estimates
    what the catalog can supply (it ignores free-space connectivity and lets
    every body be a level-1 body).  That is what makes it usable as a fail-closed
    arithmetic pre-gate: if

        sum over regions of ceiling(region)  <  3325

    then no catalog whatsoever can cover the 132 / 49 / 38 census under this
    restriction level and the exact-cover master is INFEASIBLE without being
    built.  When optimality is not proven within ``seconds`` the solver's best
    *bound* is reported and used, which keeps the pre-gate sound.
    """
    from ortools.sat.python import cp_model

    poses = [
        pose
        for pose in enumerate_body_poses(region, spine=config.spine)
        if pose.level == TEMPLATE_LEVELS[pose.template][0]
    ]
    pole_anchors = enumerate_pole_poses(region, spine=config.spine)
    if not poses:
        return {
            "best_found": 0,
            "upper_bound": 0,
            "status": "NO_POSE",
            "proved_optimal": True,
        }

    model = cp_model.CpModel()
    pose_vars = {pose.key: model.new_bool_var(f"p{i}") for i, pose in enumerate(poses)}
    pole_vars = {a: model.new_bool_var(f"pole{a}") for a in pole_anchors}
    covering: Dict[Cell, List[Any]] = {}
    used: Dict[Cell, Any] = {}
    for u in range(REGION_SIZE):
        for v in range(REGION_SIZE):
            cell = (u, v)
            if cell in region.fixed_local:
                continue
            used[cell] = model.new_bool_var(f"u{u}_{v}")
            covering[cell] = []
    for pose in poses:
        for cell in pose.cells:
            covering[cell].append(pose_vars[pose.key])
    for anchor in pole_anchors:
        for cell in pole_cells(anchor):
            covering[cell].append(pole_vars[anchor])
    for cell, occupiers in covering.items():
        if occupiers:
            model.add_at_most_one(occupiers)
            model.add(sum(occupiers) == used[cell])
        else:
            model.add(used[cell] == 0)
    for cell in _forced_free(region, spine=config.spine):
        if cell in used:
            model.add(used[cell] == 0)
    for pose in poses:
        variable = pose_vars[pose.key]
        for cells, required in (
            (pose.wide_variable_cells, pose.wide_required),
            (pose.narrow_variable_cells, pose.narrow_required),
        ):
            model.add(sum(used[c] for c in cells) + required * variable <= len(cells))
    stencils = {a: coverage_cells(a) for a in pole_anchors}
    for pose in poses:
        coverers = [
            pole_vars[a] for a in pole_anchors if any(c in stencils[a] for c in pose.cells)
        ]
        model.add_bool_or(coverers + [pose_vars[pose.key].negated()])
    model.add(sum(pole_vars.values()) <= MAX_POLES_PER_REGION)
    model.add(sum(pole_vars.values()) <= sum(pose_vars.values()))

    area = sum(
        len(pose.cells) * pose_vars[pose.key] for pose in poses
    )
    model.maximize(area)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_workers = int(config.workers)
    solver.parameters.random_seed = int(config.seed)
    status = solver.solve(model)
    name = solver.status_name(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"best_found": 0, "upper_bound": region.usable, "status": name,
                "proved_optimal": False}
    return {
        "best_found": int(solver.objective_value),
        "upper_bound": int(solver.best_objective_bound),
        "status": name,
        "proved_optimal": status == cp_model.OPTIMAL,
    }


# --------------------------------------------------------------------------
# post-processing
# --------------------------------------------------------------------------


def corridor_tax(evaluation: PatternEvaluation) -> int:
    """Alarm meter 1: front cells the retired loose reading would have counted.

    The registered reading admits one corridor; the retired one admitted the
    union of every stub-bearing free component.  The difference, counted over the
    pattern's own body fronts, is what the strict restriction costs this pattern.
    It is measured here rather than inferred from a second solve, so it is
    available on every run at no solver cost.
    """
    region = REGION_CLASSES[evaluation.spec.region_class]
    free = set(evaluation.free_cells)
    loose: set = set()
    frontier = deque(cell for cell in region.live_stubs if cell in free)
    loose.update(frontier)
    while frontier:
        u, v = frontier.popleft()
        for neighbour in ((u + 1, v), (u - 1, v), (u, v + 1), (u, v - 1)):
            if neighbour in free and neighbour not in loose:
                loose.add(neighbour)
                frontier.append(neighbour)
    extra = loose - set(evaluation.component)
    if not extra:
        return 0
    counted = 0
    for body in evaluation.bodies:
        for side in SIDES:
            for cell in side_front_cells(
                body.template, body.orientation, body.local_anchor, side
            ):
                if cell in extra:
                    counted += 1
    return counted


def _repack(spec: PatternSpec, keep: Sequence[BodySpec]) -> PatternSpec:
    bodies = tuple(
        BodySpec(
            bid=index,
            template=body.template,
            orientation=body.orientation,
            local_anchor=body.local_anchor,
        )
        for index, body in enumerate(
            sorted(keep, key=lambda b: (b.local_anchor, b.template, b.orientation))
        )
    )
    if not bodies:
        return PatternSpec(
            region_class=spec.region_class, bodies=(), poles=(), hole=spec.hole
        )
    named = [
        (
            f"b{body.bid}",
            body_cells(body.template, body.orientation, body.local_anchor),
        )
        for body in bodies
    ]
    anchors = [pole.local_anchor for pole in spec.poles]
    try:
        minimal = minimize_poles(named, anchors)
    except ValueError:
        minimal = tuple(anchors)
    return PatternSpec(
        region_class=spec.region_class,
        bodies=bodies,
        poles=tuple(PoleSpec(local_anchor=anchor) for anchor in minimal),
        hole=spec.hole,
    )


def derive_subsets(spec: PatternSpec, limit: int) -> Tuple[PatternSpec, ...]:
    """H-DERIVED-SUBSETS: cheap lower-count patterns by dropping one body.

    Removing a body only frees cells, so the survivors' capability can only rise;
    the evaluator recomputes it anyway.  Deterministic: the first ``limit`` bodies
    in ``(anchor, template)`` order are dropped in turn.
    """
    if limit <= 0 or len(spec.bodies) <= 1:
        return ()
    derived: List[PatternSpec] = []
    ordered = sorted(spec.bodies, key=lambda b: (b.local_anchor, b.template))
    for body in ordered[:limit]:
        keep = [item for item in spec.bodies if item.bid != body.bid]
        derived.append(_repack(spec, keep))
    return tuple(derived)


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


@dataclass
class CatalogAccumulator:
    region_class: str
    by_signature: Dict[object, Dict[str, object]] = field(default_factory=dict)

    def offer(self, evaluation: PatternEvaluation, generator_meta: Mapping[str, object]) -> bool:
        signature = evaluation.signature
        if signature in self.by_signature:
            return False
        self.by_signature[signature] = pattern_to_json(evaluation, generator=generator_meta)
        return True


def _accept(
    spec: PatternSpec,
    accumulator: CatalogAccumulator,
    stats: GeneratorStats,
    meta: Mapping[str, object],
    *,
    from_solver: bool,
) -> Optional[PatternEvaluation]:
    """Re-evaluate a candidate and file it, or account for why it was refused.

    ``from_solver`` marks specs the CP-SAT model itself produced.  Those carry
    every restriction as a hard constraint, so a refusal is alarm meter 2 --
    solver and evaluator disagreeing about the same rule -- and blocks the run.
    Derived subsets are ordinary candidates: they are cheap guesses, and a
    refusal there is bookkeeping, not a defect.
    """
    evaluation = evaluate_pattern(spec)
    if not evaluation.ok:
        for violation in evaluation.violations:
            stats.violation_counts[violation] = stats.violation_counts.get(violation, 0) + 1
        if from_solver:
            stats.postcheck_divergence += 1
            raise GeneratorBlocked(
                "postcheck divergence: the CP-SAT model produced a pattern the "
                f"evaluator refuses ({list(evaluation.violations)}); the in-model "
                "restriction and the post-check are supposed to be the same "
                f"restriction. spec={spec.as_json()!r} meta={dict(meta)!r}"
            )
        stats.derived_rejected += 1
        if "T-DEAD-BODY-ZERO" in evaluation.violations:
            stats.rejected_dead_body += 1
        else:
            stats.rejected_other += 1
        return None
    tax = corridor_tax(evaluation)
    if tax:
        stats.corridor_tax_front_cells += tax
        stats.patterns_paying_corridor_tax += 1
    if accumulator.offer(evaluation, meta):
        return evaluation
    stats.duplicate_signatures += 1
    return evaluation


def generate_catalog(
    config: GeneratorConfig,
    *,
    output_dir: Path,
    progress: bool = True,
) -> Dict[str, object]:
    """Run the whole menu under one global wall-clock budget and write catalogs."""
    started = time.monotonic()
    accumulators: Dict[str, CatalogAccumulator] = {}
    stats_by_class: Dict[str, GeneratorStats] = {}
    complete: Dict[str, bool] = {}

    jobs: List[Tuple[float, int, str, Target]] = []
    menus: Dict[str, Tuple[Target, ...]] = {}
    full_menu_size: Dict[str, int] = {}
    for name in config.region_classes:
        region = REGION_CLASSES[name]
        menu = build_target_menu(
            region,
            spine=config.spine,
            min_bodies=config.min_bodies,
            max_bodies=config.max_bodies,
        )
        full_menu_size[name] = len(menu)
        if config.max_targets is not None:
            menu = menu[: config.max_targets]
        menus[name] = menu
        accumulators[name] = CatalogAccumulator(region_class=name)
        stats_by_class[name] = GeneratorStats()
        complete[name] = True
        for rank, target in enumerate(menu):
            jobs.append((rank, REGION_CLASS_ORDER.index(name), name, target))
    # Round-robin by within-class rank: every class gets its centre band before
    # any class gets its outer band.
    jobs.sort(key=lambda job: (job[0], job[1]))

    pose_cache: Dict[str, Tuple[Pose, ...]] = {}
    pole_cache: Dict[str, Tuple[Cell, ...]] = {}
    hole_cache: Dict[str, Tuple[Tuple[Cell, int, int], ...]] = {}

    # Arithmetic pre-gate first: it is one solve per class and it can settle the
    # whole question before a single menu target is spent.
    ceilings: Dict[str, Dict[str, object]] = {}
    for name in config.region_classes:
        ceilings[name] = measure_packing_ceiling(
            REGION_CLASSES[name], config, seconds=config.ceiling_seconds
        )
        if progress:
            print(f"  [ceiling] {name}: {ceilings[name]}", flush=True)

    for job_rank, _class_index, name, target in jobs:
        if time.monotonic() - started > config.budget_seconds:
            # Budget exhausted.  Every class whose menu was not fully attempted is
            # marked incomplete; the deterministic job order makes the produced
            # prefix reproducible.
            break
        region = REGION_CLASSES[name]
        if name not in pose_cache:
            pose_cache[name] = enumerate_body_poses(region, spine=config.spine)
            pole_cache[name] = enumerate_pole_poses(region, spine=config.spine)
            hole_cache[name] = enumerate_hole_poses(region)
        stats = stats_by_class[name]
        stats.targets_attempted += 1
        specs, elapsed, status = _solve_target(
            region, target, pose_cache[name], pole_cache[name], hole_cache[name], config
        )
        stats.solve_seconds += elapsed
        stats.target_status_counts[status] = stats.target_status_counts.get(status, 0) + 1
        if specs:
            stats.targets_feasible += 1
        elif status == "INFEASIBLE":
            # Alarm meter 1: proved to have no pattern under the strict corridor.
            # Counted, not repaired -- it is the restriction's price.
            stats.targets_infeasible += 1
        else:
            # Ran out of time.  Emphatically *not* the same statement, and kept
            # in its own counter so no reader can read a timeout as a proof.
            stats.targets_unproved += 1
        for index, spec in enumerate(specs):
            stats.solutions_found += 1
            meta = {
                "target": target.as_json(),
                "solution_index": index,
                "menu_rank": job_rank,
                "seed": config.seed,
                "spine": config.spine,
            }
            evaluation = _accept(
                spec, accumulators[name], stats, meta, from_solver=True
            )
            if evaluation is None:  # pragma: no cover - from_solver raises instead
                continue
            for derived in derive_subsets(spec, config.max_derived_subsets):
                stats.derived_subsets += 1
                _accept(
                    derived,
                    accumulators[name],
                    stats,
                    dict(meta, derived_from=spec.pattern_id),
                    from_solver=False,
                )
        if progress and stats.targets_attempted % 25 == 0:
            print(
                f"  [{name}] rank {job_rank} attempted={stats.targets_attempted} "
                f"patterns={len(accumulators[name].by_signature)} "
                f"elapsed={time.monotonic() - started:.0f}s",
                flush=True,
            )

    for key in config.region_classes:
        if stats_by_class[key].targets_attempted < full_menu_size[key]:
            complete[key] = False

    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_dir = output_dir / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    manifest_entries: Dict[str, object] = {}
    for name in config.region_classes:
        region = REGION_CLASSES[name]
        patterns = [
            accumulators[name].by_signature[key]
            for key in sorted(
                accumulators[name].by_signature, key=lambda k: json.dumps(k, sort_keys=True, default=str)
            )
        ]
        payload = {
            "schema": CATALOG_SCHEMA,
            "authority": dict(RESEARCH_AUTHORITY),
            "region_class": name,
            "region_multiplicity": region.multiplicity,
            "fixed_mask_sha256": mask_sha256(region.fixed_local),
            "reserved_mask_sha256": mask_sha256(region.reserved_local),
            "complete": complete[name],
            "patterns": patterns,
        }
        digest = dump_canonical(catalog_dir / f"{name}.json", payload)
        manifest_entries[name] = {
            "sha256": digest,
            "patterns": len(patterns),
            "complete": complete[name],
            "multiplicity": region.multiplicity,
            "usable": region.usable,
            "menu_size": len(menus[name]),
            "full_menu_size": full_menu_size[name],
            "packing_ceiling": ceilings[name],
            "stats": stats_by_class[name].as_json(),
        }

    manifest = {
        "schema": "w0_g1_catalog_manifest_v1",
        "authority": dict(RESEARCH_AUTHORITY),
        "generated_wall_seconds": round(time.monotonic() - started, 3),
        "config": config.as_json(),
        "frozen_inputs": {
            "rules": _file_digest(DEFAULT_RULES_PATH),
            "instances": _file_digest(DEFAULT_INSTANCES_PATH),
        },
        "source_digest": _source_digest(),
        "port_semantics": port_summary(),
        "versions": {
            "python": platform.python_version(),
            "ortools": _ortools_version(),
        },
        "catalogs": manifest_entries,
        "arithmetic_pre_gate": _arithmetic_pre_gate(ceilings, config),
        # Alarm meter 3, run level: which code paths were retired and why.  A
        # reader must be able to tell "this never happened" from "this cannot
        # happen any more" without reading the source.
        "retired_paths": dict(RETIRED_PATHS),
        "connectivity": {
            "enforced": "in_model",
            "certificate": "single-commodity flow rooted at one live portal stub",
            "root_rule": "min(live_stubs), matching g1_pattern_evaluator.component_root",
            "reading": (
                "R-PAT-CONN is a hard constraint of every target model, not a "
                "post-filter. The evaluator re-check is a divergence detector "
                "(alarm meter 2), not the gate."
            ),
        },
    }
    dump_canonical(catalog_dir / "manifest.json", manifest)
    return manifest


def _arithmetic_pre_gate(
    ceilings: Mapping[str, Mapping[str, object]], config: GeneratorConfig
) -> Dict[str, object]:
    """Sum the per-class packing ceilings against the census body area.

    ``supply_upper_bound`` over-counts on purpose (connectivity ignored, every
    body at its cheapest level), so ``supply_upper_bound < demand`` is a sound
    INFEASIBLE verdict for the whole restriction level, not just for this
    catalog.  The converse says nothing.
    """
    demand = sum(
        row.count * TEMPLATE_AREAS[row.template] for row in CLASS_TABLE
    )
    supply = 0
    proved = True
    for name, ceiling in ceilings.items():
        multiplicity = REGION_CLASSES[name].multiplicity
        bound = int(str(ceiling["upper_bound"]))
        supply += bound * multiplicity
        proved = proved and bool(ceiling["proved_optimal"])
    covered = set(ceilings) == set(REGION_CLASS_ORDER)
    return {
        "body_area_demand": demand,
        "supply_upper_bound": supply,
        "slack": supply - demand,
        "all_classes_measured": covered,
        "all_ceilings_proved_optimal": proved,
        "verdict": (
            "INFEASIBLE_BY_AREA"
            if covered and supply < demand
            else ("INCONCLUSIVE" if not covered else "NOT_EXCLUDED_BY_AREA")
        ),
        "reading": (
            "supply_upper_bound over-counts (free-space connectivity ignored, every "
            "body at its cheapest capability level). supply < demand therefore "
            "excludes the whole restriction level; supply >= demand excludes nothing."
        ),
    }


TEMPLATE_AREAS: Dict[str, int] = {
    template: template_footprint(template, 0)[0] * template_footprint(template, 0)[1]
    for template in MANUFACTURING_TEMPLATES
}


def _file_digest(path: Path) -> Dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": str(path.relative_to(Path(__file__).resolve().parents[3])),
        "bytes": len(payload),
        "sha256": sha256_of_bytes(payload),
    }


def _source_digest() -> Dict[str, str]:
    here = Path(__file__).resolve().parent
    return {
        source.name: sha256_of_bytes(source.read_bytes())
        for source in sorted(here.glob("*.py"))
    }


def _ortools_version() -> str:
    """The solver version, from the two places that actually carry it.

    ``cp_model.__version__`` does not exist in ortools 9.x; reading it there is
    how the stage A manifest ended up recording ``"ortools": "unknown"``.  The
    imported package carries the version, the installed distribution repeats it.
    """
    try:
        import ortools

        version = str(getattr(ortools, "__version__", "") or "")
        if version:
            return version
        from importlib import metadata

        return metadata.version("ortools")
    except Exception:  # pragma: no cover - reported, never fatal
        return "unavailable"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--budget-seconds", type=float, default=5400.0)
    parser.add_argument("--target-seconds", type=float, default=2.0)
    parser.add_argument("--solutions-per-target", type=int, default=3)
    parser.add_argument("--max-derived-subsets", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-targets", type=int, default=None)
    parser.add_argument("--min-bodies", type=int, default=1)
    parser.add_argument("--max-bodies", type=int, default=None)
    parser.add_argument("--hard-spine", dest="spine", action="store_true")
    parser.add_argument(
        "--region-class", dest="region_classes", action="append", default=None
    )
    args = parser.parse_args(argv)

    config = GeneratorConfig(
        budget_seconds=args.budget_seconds,
        target_seconds=args.target_seconds,
        solutions_per_target=args.solutions_per_target,
        max_derived_subsets=args.max_derived_subsets,
        workers=args.workers,
        seed=args.seed,
        spine=args.spine,
        max_targets=args.max_targets,
        min_bodies=args.min_bodies,
        max_bodies=args.max_bodies,
        region_classes=tuple(args.region_classes or REGION_CLASS_ORDER),
    )
    manifest = generate_catalog(config, output_dir=args.output_dir)
    print(json.dumps({k: v for k, v in manifest.items() if k != "port_semantics"}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
