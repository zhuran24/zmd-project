"""W0 front-aware G1: master solution -> full 70x70 geometry.

research-only.  No authority, no bound, no ledger effect.

The master answers in the collapsed vocabulary -- how many regions of each class
take which pattern, and how many bodies of each capability bucket serve which
operation class.  This module turns that back into a board: concrete anchors,
concrete modes, concrete active front cells, a globally minimised pole set, a
concrete hole, and provisional instance identifiers.

Everything here is deterministic.  Given the same master result and the same
catalog the same board comes out, cell for cell:

* regions of a class are filled in ``(i, j)`` lexicographic order and the
  patterns dealt out in ``pattern_id`` order (the master already did this);
* bodies of a bucket are ordered by ``(region, local_anchor, template)`` and the
  classes assigned to that bucket are consumed in the frozen class order;
* poles are dropped in ``(x, y)`` order during minimisation;
* instances are matched to bodies by sorting both.

Pole minimisation (T-POLE-MINIMAL) runs **globally**, over all 25 regions at
once, after expansion.  ``R-POWER-LOCAL`` was a per-region restriction that
bought the master a constraint-free power story; once the board exists a pole in
a neighbouring region may already cover a machine, and the repository's
irredundancy predicate cares about the board, not about regions.  Removing poles
only frees cells, so no front witness and no hole can be invalidated by it.

Instance assignment is marked ``provisional``: document 17 keeps instance ids out
of the master to kill the permutation symmetry, and G2 is free to permute within
a class.  The class of each body is *not* provisional -- it is the master's
decision and the audit re-checks the census against the frozen table.

Runtime contract: stdlib only, no solver.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from g1_exact_cover_master import catalog_directories  # noqa: E402
from g1_pattern_evaluator import (  # noqa: E402
    body_cells,
    evaluate_pattern,
    minimize_poles,
    template_footprint,
)
from g1_pattern_schema import (  # noqa: E402
    GEOMETRY_SCHEMA,
    PatternSpec,
    RESEARCH_AUTHORITY,
    load_strict,
)
from g1_port_semantics import (  # noqa: E402
    CLASS_BY_ID,
    CLASS_ORDER,
    DEFAULT_INSTANCES_PATH,
    GRID_HEIGHT,
    GRID_WIDTH,
)
from g1_region_model import FIXED_FURNITURE, to_global  # noqa: E402

__all__ = [
    "W0_PROFILE_ID",
    "W0_FIXED_FURNITURE_SPEC",
    "ExpansionError",
    "expand_master_solution",
    "layout_profile",
    "fixed_furniture_json",
]

Cell = Tuple[int, int]

#: Must equal ``front_viability_audit.W0_PROFILE_ID`` / ``W0_PINNED_SPEC``.  The
#: audit regenerates the furniture from this spec and compares cell for cell, so
#: a drift here is caught by an independent process, not by agreement.
W0_PROFILE_ID = "w0_70x70_v1"
W0_FIXED_FURNITURE_SPEC: Dict[str, Any] = {
    "boundary": {"period": 3, "start": 1, "left": True, "bottom": True},
    "core": {
        "anchor": [3, 59],
        "size": [9, 9],
        "orientation": 1,
        "input_indices": [1, 2, 3, 4, 5, 6, 7],
        "output_indices": [1, 4, 7],
    },
}


class ExpansionError(RuntimeError):
    """Fail-closed: the master answer and the catalog do not fit together."""


def layout_profile() -> Dict[str, Any]:
    return {
        "profile_id": W0_PROFILE_ID,
        "grid": [GRID_WIDTH, GRID_HEIGHT],
        "fixed_furniture_spec": json.loads(json.dumps(W0_FIXED_FURNITURE_SPEC)),
    }


def fixed_furniture_json() -> List[Dict[str, Any]]:
    return [
        {
            "kind": item.kind,
            "anchor": list(item.anchor),
            "size": list(item.size),
            "orientation": item.orientation,
            "front_cells": [list(cell) for cell in item.front_cells],
        }
        for item in FIXED_FURNITURE
    ]


@dataclass(frozen=True)
class PlacedBody:
    """One expanded manufacturing body, before its class is known."""

    region: Tuple[int, int]
    region_class: str
    pattern_id: str
    bid: int
    template: str
    orientation: int
    anchor: Cell
    bucket: str
    local_anchor: Cell
    witness: Mapping[str, Mapping[str, Any]]

    @property
    def sort_key(self) -> Tuple[int, int, int, int, str]:
        return (
            self.region[0],
            self.region[1],
            self.local_anchor[0],
            self.local_anchor[1],
            self.template,
        )


def _pattern_index(directories: Sequence[Path], region_class: str) -> Dict[str, Any]:
    """Every stored pattern of one region class, across all catalog directories.

    The master may have been given a union of catalogs, so a selected pattern id
    can come from any of them.  First directory wins on collision, matching the
    loader's union rule -- and a collision means the same content address anyway.
    """
    index: Dict[str, Any] = {}
    for directory in directories:
        payload = load_strict(Path(directory) / f"{region_class}.json")
        for stored in payload["patterns"]:
            index.setdefault(str(stored["pattern_id"]), stored)
    return index


def _instances_by_operation(instances_path: Path | str) -> Dict[str, List[str]]:
    payload = load_strict(instances_path)
    if not isinstance(payload, list):
        raise ExpansionError("mandatory instances artifact must be a JSON array")
    grouped: Dict[str, List[str]] = {}
    for item in payload:
        grouped.setdefault(str(item["operation_type"]), []).append(
            str(item["instance_id"])
        )
    for operation in grouped:
        grouped[operation].sort()
    return grouped


def expand_master_solution(
    master_result: Mapping[str, Any],
    catalog_dirs: Path | str | Sequence[Path | str],
    *,
    instances_path: Path | str = DEFAULT_INSTANCES_PATH,
) -> Dict[str, Any]:
    """Expand a FEASIBLE/OPTIMAL master answer into ``w0_g1_geometry_v1``."""
    status = str(master_result.get("status"))
    if status not in {"OPTIMAL", "FEASIBLE"}:
        raise ExpansionError(f"master status {status!r} has nothing to expand")

    directories = catalog_directories(catalog_dirs)
    pattern_cache: Dict[str, Dict[str, Any]] = {}

    placed: List[PlacedBody] = []
    poles: List[Cell] = []
    hole: Optional[Dict[str, Any]] = None
    holes_seen = 0

    for row in master_result["selection"]:
        region = (int(row["region"][0]), int(row["region"][1]))
        region_class = str(row["region_class"])
        pattern_id = str(row["pattern_id"])
        if region_class not in pattern_cache:
            pattern_cache[region_class] = _pattern_index(directories, region_class)
        stored = pattern_cache[region_class].get(pattern_id)
        if stored is None:
            # The empty pattern is synthesised by the master loader, not stored.
            spec = PatternSpec(region_class=region_class, bodies=(), poles=(), hole=None)
            if spec.pattern_id != pattern_id:
                raise ExpansionError(
                    f"region {region} names pattern {pattern_id!r} which is neither in "
                    f"the {region_class} catalog nor the empty pattern"
                )
            evaluation = evaluate_pattern(spec)
        else:
            spec = PatternSpec.from_json(stored["spec"], what=f"pattern[{pattern_id}]")
            evaluation = evaluate_pattern(spec)
            if not evaluation.ok:
                raise ExpansionError(
                    f"pattern {pattern_id} violates {list(evaluation.violations)} on "
                    "re-evaluation during expansion"
                )
        for body in evaluation.bodies:
            if body.bucket is None:  # pragma: no cover - T-DEAD-BODY-ZERO forbids it
                raise ExpansionError(f"pattern {pattern_id} carries a dead body")
            placed.append(
                PlacedBody(
                    region=region,
                    region_class=region_class,
                    pattern_id=pattern_id,
                    bid=body.bid,
                    template=body.template,
                    orientation=body.orientation,
                    anchor=to_global(body.local_anchor, region[0], region[1]),
                    bucket=body.bucket,
                    local_anchor=body.local_anchor,
                    witness=body.class_witness,
                )
            )
        for anchor in evaluation.poles:
            poles.append(to_global(anchor, region[0], region[1]))
        if evaluation.hole is not None:
            holes_seen += 1
            origin = to_global(evaluation.hole.local_anchor, region[0], region[1])
            hole = {
                "anchor": list(origin),
                "width": evaluation.hole.width,
                "height": evaluation.hole.height,
                "region": list(region),
            }

    if holes_seen != 1:
        raise ExpansionError(
            f"the selection carries {holes_seen} holes; C3 asks for exactly one"
        )

    # ---- bucket -> class, deterministically -----------------------------
    wanted: Dict[str, List[str]] = {}
    for row in master_result["class_assignment"]:
        wanted.setdefault(str(row["bucket"]), []).extend(
            [str(row["class"])] * int(row["count"])
        )
    for bucket in wanted:
        wanted[bucket].sort(key=lambda class_id: CLASS_ORDER.index(class_id))

    by_bucket: Dict[str, List[PlacedBody]] = {}
    for unit in placed:
        by_bucket.setdefault(unit.bucket, []).append(unit)
    for bucket in by_bucket:
        by_bucket[bucket].sort(key=lambda item: item.sort_key)

    assigned: List[Tuple[PlacedBody, str]] = []
    for bucket in sorted(by_bucket):
        bodies = by_bucket[bucket]
        classes = wanted.get(bucket, [])
        if len(bodies) != len(classes):
            raise ExpansionError(
                f"bucket {bucket} holds {len(bodies)} bodies but the master assigned "
                f"{len(classes)} classes to it"
            )
        for unit, class_id in zip(bodies, classes):
            if class_id not in unit.witness:
                raise ExpansionError(
                    f"the body {unit.template}@{unit.anchor} in bucket {bucket} has no "
                    f"witness for class {class_id}"
                )
            assigned.append((unit, class_id))
    leftovers = set(wanted) - set(by_bucket)
    if leftovers:
        raise ExpansionError(
            f"the master assigned classes to buckets no body has: {sorted(leftovers)}"
        )

    # ---- provisional instance identifiers --------------------------------
    grouped_instances = _instances_by_operation(instances_path)
    per_class: Dict[str, List[str]] = {}
    for class_id in CLASS_ORDER:
        row = CLASS_BY_ID[class_id]
        pool: List[str] = []
        for operation in row.operations:
            pool.extend(grouped_instances.get(operation, ()))
        per_class[class_id] = sorted(pool)

    by_class: Dict[str, List[PlacedBody]] = {}
    for unit, class_id in assigned:
        by_class.setdefault(class_id, []).append(unit)
    for class_id in by_class:
        by_class[class_id].sort(key=lambda item: (item.anchor[0], item.anchor[1]))

    instance_of: Dict[Tuple[Tuple[int, int], int], str] = {}
    for class_id, bodies in by_class.items():
        pool = per_class.get(class_id, [])
        if len(pool) < len(bodies):
            raise ExpansionError(
                f"class {class_id} needs {len(bodies)} instance ids, the frozen census "
                f"offers {len(pool)}"
            )
        for unit, instance_id in zip(bodies, pool):
            instance_of[(unit.region, unit.bid)] = instance_id

    # ---- global pole minimisation (T-POLE-MINIMAL) -----------------------
    named_bodies = [
        (
            f"{unit.region[0]}_{unit.region[1]}_{unit.bid}",
            body_cells(unit.template, unit.orientation, unit.anchor),
        )
        for unit in placed
    ]
    clip = (0, 0, GRID_WIDTH, GRID_HEIGHT)
    minimal_poles = (
        minimize_poles(named_bodies, sorted(set(poles)), clip=clip)
        if named_bodies
        else ()
    )

    # ---- placements ------------------------------------------------------
    placements: List[Dict[str, Any]] = []
    for unit, class_id in sorted(assigned, key=lambda item: item[0].sort_key):
        witness = unit.witness[class_id]
        offset = (unit.region[0], unit.region[1])
        placements.append(
            {
                "instance_id": instance_of[(unit.region, unit.bid)],
                "template": unit.template,
                "orientation": unit.orientation,
                "anchor": list(unit.anchor),
                "size": list(template_footprint(unit.template, unit.orientation)),
                "mode": str(witness["mode"]),
                "operation_class": class_id,
                "provisional": True,
                "region": list(unit.region),
                "pattern_id": unit.pattern_id,
                "capability_bucket": unit.bucket,
                "active_input_fronts": [
                    list(to_global((int(cell[0]), int(cell[1])), *offset))
                    for cell in witness["active_in"]
                ],
                "active_output_fronts": [
                    list(to_global((int(cell[0]), int(cell[1])), *offset))
                    for cell in witness["active_out"]
                ],
            }
        )
    placements.sort(key=lambda entry: (entry["anchor"][0], entry["anchor"][1]))

    geometry: Dict[str, Any] = {
        "schema": GEOMETRY_SCHEMA,
        "authority": dict(RESEARCH_AUTHORITY),
        "layout_profile": layout_profile(),
        "fixed_furniture": fixed_furniture_json(),
        "placements": placements,
        "power_poles": [{"anchor": list(anchor)} for anchor in minimal_poles],
        "hole": None if hole is None else {
            "anchor": hole["anchor"],
            "width": hole["width"],
            "height": hole["height"],
        },
        "expansion": {
            "regions": len(master_result["selection"]),
            "bodies": len(placed),
            "poles_before_minimisation": len(sorted(set(poles))),
            "poles_after_minimisation": len(minimal_poles),
            "hole_region": None if hole is None else hole["region"],
            "instance_assignment": "provisional",
        },
    }
    return geometry


def summarise(geometry: Mapping[str, Any]) -> Dict[str, Any]:
    """Small human digest used by the CLI and the result document."""
    census: Dict[str, int] = {}
    for placement in geometry["placements"]:
        class_id = str(placement["operation_class"])
        census[class_id] = census.get(class_id, 0) + 1
    return {
        "placements": len(geometry["placements"]),
        "poles": len(geometry["power_poles"]),
        "class_census": dict(sorted(census.items())),
        "hole": geometry["hole"],
    }
