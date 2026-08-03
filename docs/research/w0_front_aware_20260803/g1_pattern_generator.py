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

    sum_{c in side} used[c]  <=  |side| - required * selected

"at least ``required`` of this side's front cells stay body-free if this pose is
chosen".  No auxiliary variable, no reification.  A pose therefore commits to its
template, orientation, anchor, which side carries the wide port face, and the
capability level; the four/two same-anchor variants are mutually exclusive for
free through cell exclusivity.

H-GEN-OBJECTIVE (revised).  The blueprint proposed a linearised "free front
proxy" objective.  Once the front requirement is a *constraint* the proxy is
redundant, and pushing a cheap necessary condition out of the objective and into
the model is exactly the section 0b discipline this line exists to apply.  The
objective is now simply ``minimise sum(used)``: with body counts fixed by the
target, that minimises pole cells and maximises corridor, which is what the
connectivity filter wants.

Connectivity is deliberately *not* in the model (it is expensive there).  The
optional spine lane (H-SPINE-LANE) forces row 6 and column 6 body-free, which
makes every live portal stub connected by construction; the evaluator's
R-PAT-CONN check remains the real gate either way and the discard rate is
reported.

Runtime contract: stdlib + ortools.  Single solve at a time, workers <= 4, tiny
models (196 cells).  A prod-scale memory profile here would mean the model is
wrong -- stop rather than push through.
"""

from __future__ import annotations

import argparse
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
    "Pose",
    "Target",
    "GeneratorConfig",
    "enumerate_body_poses",
    "enumerate_pole_poses",
    "enumerate_hole_poses",
    "build_target_menu",
    "generate_catalog",
    "measure_packing_ceiling",
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
#: So the corridor preference is kept at weight 0: strip-and-derive recovers the
#: disconnected solutions more cheaply than biasing the packing does.  The
#: constant stays as the registered anchor and as the knob to re-run the A/B.
SPINE_LANE = "H-SPINE-LANE"
SPINE_OBJECTIVE_WEIGHT = 0

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
    spine: bool = False
    max_targets: Optional[int] = None
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
            "ceiling_seconds": self.ceiling_seconds,
            "region_classes": list(self.region_classes),
        }


@dataclass
class GeneratorStats:
    targets_attempted: int = 0
    targets_feasible: int = 0
    solutions_found: int = 0
    rejected_connectivity: int = 0
    rejected_dead_body: int = 0
    rejected_other: int = 0
    stripped_to_smaller: int = 0
    derived_subsets: int = 0
    duplicate_signatures: int = 0
    solve_seconds: float = 0.0
    violation_counts: Dict[str, int] = field(default_factory=dict)

    def as_json(self) -> Dict[str, object]:
        return {
            "targets_attempted": self.targets_attempted,
            "targets_feasible": self.targets_feasible,
            "solutions_found": self.solutions_found,
            "rejected_connectivity": self.rejected_connectivity,
            "rejected_dead_body": self.rejected_dead_body,
            "rejected_other": self.rejected_other,
            "stripped_to_smaller": self.stripped_to_smaller,
            "derived_subsets": self.derived_subsets,
            "duplicate_signatures": self.duplicate_signatures,
            "solve_seconds": round(self.solve_seconds, 3),
            "violation_counts": dict(sorted(self.violation_counts.items())),
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

_GLOBAL_SHARE: Dict[str, float] = {
    template: sum(row.count for row in CLASS_TABLE if row.template == template) / 25.0
    for template in MANUFACTURING_TEMPLATES
}


def build_target_menu(region: RegionClass, *, spine: bool = False) -> Tuple[Target, ...]:
    """H-TARGET-MENU.

    Enumerate ``(n3, n5, n6)`` count vectors that still fit the region's free
    budget, cross them with two level profiles (``min`` = every body at the
    cheapest level its template needs, ``max`` = every body at the richest) and
    the hole flag, then order by distance from the region's proportional share of
    the global 132 / 49 / 38 census.  Centre-band targets are therefore generated
    first and a budget cut-off leaves a deterministic, reproducible prefix.
    """
    budget = REGION_CELLS_LOCAL - len(region.fixed_local) - len(_forced_free(region, spine=spine))
    share = {
        template: _GLOBAL_SHARE[template] * (region.usable / 188.0)
        for template in MANUFACTURING_TEMPLATES
    }
    targets: List[Tuple[float, Target]] = []
    max_counts = {"manufacturing_3x3": 14, "manufacturing_5x5": 6, "manufacturing_6x4": 6}
    for n3 in range(max_counts["manufacturing_3x3"] + 1):
        for n5 in range(max_counts["manufacturing_5x5"] + 1):
            for n6 in range(max_counts["manufacturing_6x4"] + 1):
                if n3 + n5 + n6 == 0:
                    continue
                area = 9 * n3 + 25 * n5 + 24 * n6 + 4
                if area > budget:
                    continue
                for hole in (False, True):
                    if hole and area + 42 > budget:
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


def _solve_target(
    region: RegionClass,
    target: Target,
    poses: Sequence[Pose],
    pole_anchors: Sequence[Cell],
    hole_poses: Sequence[Tuple[Cell, int, int]],
    config: GeneratorConfig,
) -> Tuple[List[PatternSpec], float]:
    from ortools.sat.python import cp_model

    wanted: Dict[Tuple[str, int], int] = {
        (template, level): count for template, level, count in target.counts
    }
    usable_poses = [pose for pose in poses if (pose.template, pose.level) in wanted]
    if not usable_poses:
        return [], 0.0

    model = cp_model.CpModel()
    pose_vars = {
        pose.key: model.new_bool_var(f"p{index}") for index, pose in enumerate(usable_poses)
    }
    pole_vars = {
        anchor: model.new_bool_var(f"pole_{anchor[0]}_{anchor[1]}")
        for anchor in pole_anchors
    }
    forced_free = _forced_free(region, spine=config.spine)

    used: Dict[Cell, Any] = {}
    covering: Dict[Cell, List[Any]] = {}
    for u in range(REGION_SIZE):
        for v in range(REGION_SIZE):
            cell = (u, v)
            if cell in region.fixed_local:
                continue
            used[cell] = model.new_bool_var(f"u_{u}_{v}")
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

    # Capability: at least `required` free front cells on each committed side.
    for pose in usable_poses:
        variable = pose_vars[pose.key]
        for cells, required in (
            (pose.wide_variable_cells, pose.wide_required),
            (pose.narrow_variable_cells, pose.narrow_required),
        ):
            model.add(
                sum(used[cell] for cell in cells) + required * variable <= len(cells)
            )

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
                    model.add(used[cell] == 0).only_enforce_if(variable)
        if not hole_vars:
            return [], 0.0
        model.add_exactly_one(hole_vars.values())

    # H-GEN-OBJECTIVE.  Body area is fixed by the target, so ``sum(used)`` varies
    # only through pole cells: minimising it minimises poles and maximises
    # corridor.  ``SPINE_OBJECTIVE_WEIGHT`` is the measured-and-disabled corridor
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
    for _attempt in range(max(1, config.solutions_per_target)):
        start = time.monotonic()
        status = solver.solve(model)
        elapsed += time.monotonic() - start
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
    return found, elapsed


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


def strip_dead_bodies(spec: PatternSpec) -> Tuple[PatternSpec, bool]:
    """Drop bodies the evaluator judges dead, re-minimising poles each round.

    A dead body is not a wasted solve: removing it frees its cells and yields a
    smaller but legal pattern, which is exactly the low-count corner of the menu
    that is otherwise expensive to reach.
    """
    current = spec
    changed = False
    for _round in range(len(spec.bodies) + 1):
        evaluation = evaluate_pattern(current)
        dead = [body.bid for body in evaluation.bodies if body.dead]
        if not dead:
            return current, changed
        keep = [body for body in current.bodies if body.bid not in set(dead)]
        current = _repack(current, keep)
        changed = True
    return current, changed


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
) -> Optional[PatternEvaluation]:
    evaluation = evaluate_pattern(spec)
    if not evaluation.ok:
        for violation in evaluation.violations:
            stats.violation_counts[violation] = stats.violation_counts.get(violation, 0) + 1
        if "R-PAT-CONN" in evaluation.violations:
            stats.rejected_connectivity += 1
        elif "T-DEAD-BODY-ZERO" in evaluation.violations:
            stats.rejected_dead_body += 1
        else:
            stats.rejected_other += 1
        return None
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
        menu = build_target_menu(region, spine=config.spine)
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
        specs, elapsed = _solve_target(
            region, target, pose_cache[name], pole_cache[name], hole_cache[name], config
        )
        stats.solve_seconds += elapsed
        if specs:
            stats.targets_feasible += 1
        for index, spec in enumerate(specs):
            stats.solutions_found += 1
            meta = {
                "target": target.as_json(),
                "solution_index": index,
                "menu_rank": job_rank,
                "seed": config.seed,
                "spine": config.spine,
            }
            stripped, changed = strip_dead_bodies(spec)
            if changed:
                stats.stripped_to_smaller += 1
            evaluation = _accept(stripped, accumulators[name], stats, meta)
            if evaluation is None:
                continue
            for derived in derive_subsets(stripped, config.max_derived_subsets):
                stats.derived_subsets += 1
                _accept(derived, accumulators[name], stats, dict(meta, derived_from=stripped.pattern_id))
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
    try:
        from ortools.sat.python import cp_model

        return str(getattr(cp_model, "__version__", "unknown"))
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
        region_classes=tuple(args.region_classes or REGION_CLASS_ORDER),
    )
    manifest = generate_catalog(config, output_dir=args.output_dir)
    print(json.dumps({k: v for k, v in manifest.items() if k != "port_semantics"}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
