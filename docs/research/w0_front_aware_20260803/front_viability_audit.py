#!/usr/bin/env python3
"""Independent front-viability audit for a W0 G1 geometry.

research-only.  Emits no authority, no bound, no ledger effect.  A PASS verdict
means "this geometry survives the cheap necessary conditions"; it is *not* a
witness and it registers nothing.  Only the G3 strict checker may touch a ledger.

Provenance and differences from the source script
-------------------------------------------------
Derived from ``seed_front_viability_audit.py``, the solver-free port-face audit
shipped inside ``zmd_lower_bound_unblock_20260730.7z``
(SHA-256 ``0c23cdde992ff08d110fad02440703e870f14fe07eeda51cc8eb4e865748fd61``) and
re-run by document 19 on 2026-08-03 to confirm the pinned-seed death sentence.
What is kept: the idea of a no-solver, per-body recomputation of whether each
machine's access cells are in grid, unoccupied, and numerous enough for a real
operation class; and the identity front semantics (one cell outside the body).

What differs, deliberately:

1. *Input*   -- the source read a fixed framework plus a pinned seed.  This reads
   any ``w0_g1_geometry_v1`` document, so it audits generated geometries too.
2. *Class table* -- the source consumed the framework's ``operation_classes``
   need vectors, which document 19 step 4 showed disagree with the repository.
   This derives the table on the spot from the frozen ``canonical_rules.json``
   recipes and ``mandatory_exact_instances.json`` census, using the repository's
   own slot arithmetic ``ceil(amount / ticks_per_cycle / belt_capacity)``.
3. *Scope*   -- added checks the source never made: fixed-furniture agreement,
   reserved front cells, power coverage and pole irredundancy, hole legality,
   free-space connectivity, and the authority flags.

Runtime contract (copied from the document 20 checker)
-------------------------------------------------------
Standard library only.  No ``ortools``, no ``src`` import, no sibling import --
this file is self-contained on purpose so it can run under ``python -I -S -B``
where the script directory is *not* on ``sys.path``.  The duplication of the
class-table arithmetic with ``g1_port_semantics`` is the point: an independent
re-derivation is worth more than a shared helper.

Reads only; writes only the file named by ``--output``.

Exit codes: 0 = PASS, 1 = issues found, 2 = the input could not be audited.

Usage
-----
    python -I -S -B front_viability_audit.py \\
        --geometry <g1_geometry.json> \\
        --rules rules/canonical_rules.json \\
        --instances data/preprocessed/mandatory_exact_instances.json \\
        --output <g1_audit.json>

    python -I -S -B front_viability_audit.py --self-test
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

AUDIT_SCHEMA = "w0_g1_audit_v1"
GEOMETRY_SCHEMA = "w0_g1_geometry_v1"
W0_PROFILE_ID = "w0_70x70_v1"

#: The pinned W0 fixed-furniture specification.  Only checked when the geometry
#: claims the W0 profile; other profiles are audited for self-consistency only.
W0_PINNED_SPEC: Dict[str, Any] = {
    "boundary": {"period": 3, "start": 1, "left": True, "bottom": True},
    "core": {
        "anchor": [3, 59],
        "size": [9, 9],
        "orientation": 1,
        "input_indices": [1, 2, 3, 4, 5, 6, 7],
        "output_indices": [1, 4, 7],
    },
}
W0_PINNED_GRID = [70, 70]

ISSUE_CODES: Tuple[str, ...] = (
    "authority_flag_violation",
    "body_out_of_grid",
    "body_overlap",
    "fixed_furniture_mismatch",
    "class_census_mismatch",
    "front_offset_violation",
    "front_out_of_grid",
    "front_blocked",
    "active_port_count_mismatch",
    "dead_body_present",
    "power_coverage_missing",
    "unforced_power_pole",
    "hole_invalid",
    "reserved_front_blocked",
    "free_space_disconnected",
)

Cell = Tuple[int, int]


class AuditInputError(Exception):
    """The document could not be audited at all (exit code 2)."""


# --------------------------------------------------------------------------
# strict json
# --------------------------------------------------------------------------


def _reject_duplicates(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    seen: Dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise AuditInputError(f"duplicate JSON key: {key!r}")
        seen[key] = value
    return seen


def _reject_constant(name: str) -> Any:
    raise AuditInputError(f"non-finite JSON constant: {name!r}")


def load_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AuditInputError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(
            text, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant
        )
    except json.JSONDecodeError as exc:
        raise AuditInputError(f"invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# class table, re-derived
# --------------------------------------------------------------------------


def _fraction(value: Any) -> Fraction:
    if isinstance(value, bool):
        raise AuditInputError("boolean is not a rate")
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    raise AuditInputError(f"cannot read {value!r} as a rate")


def slots(amount: Any, ticks: Any, belt_capacity: Any) -> int:
    rate = _fraction(amount) / _fraction(ticks)
    if rate <= 0:
        return 0
    capacity = _fraction(belt_capacity)
    if capacity <= 0:
        raise AuditInputError("belt_capacity_per_tick must be > 0")
    required = rate / capacity
    return -((-required.numerator) // required.denominator)


def derive_class_table(rules: Any, instances: Any) -> Dict[str, Dict[str, Any]]:
    """``class_id -> {template, r_in, r_out, count}`` from the frozen inputs."""
    try:
        belt = rules["globals"]["logistics"]["belt_capacity_per_tick"]
        recipes = rules["recipes"]
        templates = rules["facility_templates"]
    except (KeyError, TypeError) as exc:
        raise AuditInputError(f"rules document is missing required sections: {exc}") from exc
    if not isinstance(instances, list):
        raise AuditInputError("instances document must be a JSON array")

    counts: Dict[str, int] = {}
    for item in instances:
        if not isinstance(item, dict) or "operation_type" not in item:
            raise AuditInputError("instance entries need an operation_type")
        operation = str(item["operation_type"])
        counts[operation] = counts.get(operation, 0) + 1

    grouped: Dict[Tuple[str, int, int], List[str]] = {}
    for operation in sorted(counts):
        recipe = recipes.get(operation)
        if recipe is None:
            continue
        template = str(recipe["template"])
        if template not in templates:
            raise AuditInputError(f"recipe {operation} names unknown template {template}")
        if str(templates[template].get("port_rule")) not in {
            "opposite_parallel_sides",
            "long_sides",
        }:
            continue
        ticks = recipe["ticks_per_cycle"]
        r_in = sum(slots(a, ticks, belt) for a in dict(recipe["inputs"]).values())
        r_out = sum(slots(a, ticks, belt) for a in dict(recipe["outputs"]).values())
        grouped.setdefault((template, r_in, r_out), []).append(operation)

    table: Dict[str, Dict[str, Any]] = {}
    for (template, r_in, r_out), operations in sorted(grouped.items()):
        class_id = derived_class_id(templates, template, r_in, r_out)
        if class_id in table:
            raise AuditInputError(f"derived class id collision: {class_id}")
        table[class_id] = {
            "template": template,
            "r_in": r_in,
            "r_out": r_out,
            "count": sum(counts[op] for op in operations),
            "operations": sorted(operations),
        }
    return table


def derived_class_id(templates: Any, template: str, r_in: int, r_out: int) -> str:
    dimensions = templates[template]["dimensions"]
    tag = str(max(int(dimensions["w"]), int(dimensions["h"])))
    if r_in == 1 and r_out == 1:
        return f"{tag}L"
    if r_in == 1:
        return f"{tag}O{r_out}"
    if r_out == 1:
        return f"{tag}I{r_in}"
    return f"{tag}I{r_in}O{r_out}"


# --------------------------------------------------------------------------
# geometry primitives
# --------------------------------------------------------------------------

_OPPOSITE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}
_MODE_SIDES = {
    "TB": ("top", "bottom"),
    "BT": ("bottom", "top"),
    "RL": ("right", "left"),
    "LR": ("left", "right"),
}


def footprint(templates: Any, template: str, orientation: int) -> Tuple[int, int]:
    dimensions = templates[template]["dimensions"]
    width, height = int(dimensions["w"]), int(dimensions["h"])
    if str(templates[template].get("port_rule")) == "long_sides" and orientation == 1:
        return height, width
    return width, height


def cells_of(anchor: Sequence[int], size: Tuple[int, int]) -> Tuple[Cell, ...]:
    ax, ay = int(anchor[0]), int(anchor[1])
    width, height = size
    return tuple((ax + dx, ay + dy) for dx in range(width) for dy in range(height))


def side_fronts(anchor: Sequence[int], size: Tuple[int, int], side: str) -> Tuple[Cell, ...]:
    """First cell outside the body -- identity front semantics, no delta."""
    ax, ay = int(anchor[0]), int(anchor[1])
    width, height = size
    if side == "top":
        return tuple((ax + i, ay + height) for i in range(width))
    if side == "bottom":
        return tuple((ax + i, ay - 1) for i in range(width))
    if side == "left":
        return tuple((ax - 1, ay + i) for i in range(height))
    if side == "right":
        return tuple((ax + width, ay + i) for i in range(height))
    raise AuditInputError(f"unknown side {side!r}")


def legal_modes(templates: Any, template: str, orientation: int) -> Tuple[str, ...]:
    rule = str(templates[template].get("port_rule"))
    if rule == "opposite_parallel_sides":
        return ("TB", "BT", "RL", "LR")
    if rule == "long_sides":
        return ("TB", "BT") if orientation == 0 else ("RL", "LR")
    raise AuditInputError(f"template {template} has no manufacturing port rule")


# --------------------------------------------------------------------------
# fixed furniture regeneration
# --------------------------------------------------------------------------


def regenerate_fixed_furniture(spec: Any, grid: Tuple[int, int]) -> List[Dict[str, Any]]:
    width, height = grid
    items: List[Dict[str, Any]] = []
    boundary = spec.get("boundary")
    if boundary is not None:
        period = int(boundary["period"])
        start = int(boundary["start"])
        if period <= 0:
            raise AuditInputError("boundary period must be positive")
        if bool(boundary.get("left")):
            k = 0
            while start + period * k + 3 <= height:
                base = start + period * k
                items.append(
                    {
                        "kind": "boundary_storage_port",
                        "anchor": [0, base],
                        "size": [1, 3],
                        "orientation": 0,
                        "front_cells": [[1, base + 1]],
                    }
                )
                k += 1
        if bool(boundary.get("bottom")):
            k = 0
            while start + period * k + 3 <= width:
                base = start + period * k
                items.append(
                    {
                        "kind": "boundary_storage_port",
                        "anchor": [base, 0],
                        "size": [3, 1],
                        "orientation": 1,
                        "front_cells": [[base + 1, 1]],
                    }
                )
                k += 1
    core = spec.get("core")
    if core is not None:
        ax, ay = int(core["anchor"][0]), int(core["anchor"][1])
        cw, ch = int(core["size"][0]), int(core["size"][1])
        orientation = int(core["orientation"])
        inputs = [int(i) for i in core["input_indices"]]
        outputs = [int(i) for i in core["output_indices"]]
        fronts: List[List[int]] = []
        if orientation == 1:  # inputs east/west
            for index in inputs:
                fronts.append([ax - 1, ay + index])
                fronts.append([ax + cw, ay + index])
            for index in outputs:
                fronts.append([ax + index, ay + ch])
                fronts.append([ax + index, ay - 1])
        else:  # inputs north/south
            for index in inputs:
                fronts.append([ax + index, ay + ch])
                fronts.append([ax + index, ay - 1])
            for index in outputs:
                fronts.append([ax - 1, ay + index])
                fronts.append([ax + cw, ay + index])
        items.append(
            {
                "kind": "protocol_core",
                "anchor": [ax, ay],
                "size": [cw, ch],
                "orientation": orientation,
                "front_cells": sorted(fronts),
            }
        )
    return items


def _normalise_furniture(items: Iterable[Any]) -> List[Dict[str, Any]]:
    normalised: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise AuditInputError("fixed_furniture entries must be objects")
        missing = {"kind", "anchor", "size", "orientation", "front_cells"} - set(item)
        if missing:
            raise AuditInputError(f"fixed_furniture entry misses {sorted(missing)}")
        normalised.append(
            {
                "kind": str(item["kind"]),
                "anchor": [int(item["anchor"][0]), int(item["anchor"][1])],
                "size": [int(item["size"][0]), int(item["size"][1])],
                "orientation": int(item["orientation"]),
                "front_cells": sorted(
                    [int(cell[0]), int(cell[1])] for cell in item["front_cells"]
                ),
            }
        )
    normalised.sort(key=lambda entry: (entry["kind"], entry["anchor"], entry["size"]))
    return normalised


# --------------------------------------------------------------------------
# largest body-free rectangle (informational only)
# --------------------------------------------------------------------------


def max_body_free_rectangle(free: FrozenSet[Cell], grid: Tuple[int, int]) -> Dict[str, int]:
    width, height = grid
    best = (0, 0, 0, 0)  # area, min_side, w, h
    for x1 in range(width):
        column_ok = [True] * height
        for x2 in range(x1, width):
            run = 0
            for y in range(height):
                column_ok[y] = column_ok[y] and (x2, y) in free
                if column_ok[y]:
                    run += 1
                else:
                    run = 0
                if run:
                    w = x2 - x1 + 1
                    candidate = (w * run, min(w, run), w, run)
                    if candidate[:2] > best[:2]:
                        best = candidate
    return {"area": best[0], "min_side": best[1], "width": best[2], "height": best[3]}


def connected_components(free: FrozenSet[Cell]) -> List[Set[Cell]]:
    remaining = set(free)
    components: List[Set[Cell]] = []
    while remaining:
        seed = next(iter(remaining))
        stack = [seed]
        remaining.discard(seed)
        component = {seed}
        while stack:
            u, v = stack.pop()
            for neighbour in ((u + 1, v), (u - 1, v), (u, v + 1), (u, v - 1)):
                if neighbour in remaining:
                    remaining.discard(neighbour)
                    component.add(neighbour)
                    stack.append(neighbour)
        components.append(component)
    return components


# --------------------------------------------------------------------------
# the audit
# --------------------------------------------------------------------------


class Issues:
    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    def add(self, code: str, detail: str, **context: Any) -> None:
        if code not in ISSUE_CODES:
            raise AuditInputError(f"unregistered issue code {code!r}")
        entry: Dict[str, Any] = {"code": code, "detail": detail}
        entry.update({key: context[key] for key in sorted(context)})
        self.items.append(entry)

    def codes(self) -> List[str]:
        return sorted({item["code"] for item in self.items})


def audit(geometry: Any, rules: Any, instances: Any) -> Dict[str, Any]:
    issues = Issues()
    if not isinstance(geometry, dict):
        raise AuditInputError("geometry document must be an object")
    if geometry.get("schema") != GEOMETRY_SCHEMA:
        raise AuditInputError(
            f"geometry schema must be {GEOMETRY_SCHEMA!r}, got {geometry.get('schema')!r}"
        )

    authority = geometry.get("authority")
    if not isinstance(authority, dict) or authority != {
        "is_authoritative": False,
        "carries_bound": False,
        "ledger_effect": "none",
    }:
        issues.add(
            "authority_flag_violation",
            "geometry authority block must be exactly all-false / ledger_effect none",
            found=authority,
        )

    profile = geometry.get("layout_profile")
    if not isinstance(profile, dict):
        raise AuditInputError("geometry needs a layout_profile object")
    grid_raw = profile.get("grid")
    if not isinstance(grid_raw, list) or len(grid_raw) != 2:
        raise AuditInputError("layout_profile.grid must be [width, height]")
    grid = (int(grid_raw[0]), int(grid_raw[1]))
    spec = profile.get("fixed_furniture_spec")
    if not isinstance(spec, dict):
        raise AuditInputError("layout_profile.fixed_furniture_spec must be an object")
    profile_id = str(profile.get("profile_id"))

    try:
        templates = rules["facility_templates"]
    except (KeyError, TypeError) as exc:
        raise AuditInputError(f"rules has no facility_templates: {exc}") from exc
    class_table = derive_class_table(rules, instances)

    # ---- fixed furniture -------------------------------------------------
    if profile_id == W0_PROFILE_ID:
        if list(grid) != W0_PINNED_GRID:
            issues.add(
                "fixed_furniture_mismatch",
                f"profile {W0_PROFILE_ID} is pinned to a {W0_PINNED_GRID} grid",
                found=list(grid),
            )
        if spec != W0_PINNED_SPEC:
            issues.add(
                "fixed_furniture_mismatch",
                f"profile {W0_PROFILE_ID} spec differs from the pinned W0 framework",
                found=spec,
            )
    declared = _normalise_furniture(geometry.get("fixed_furniture", []))
    expected = _normalise_furniture(regenerate_fixed_furniture(spec, grid))
    if declared != expected:
        issues.add(
            "fixed_furniture_mismatch",
            "declared fixed furniture does not match the layout profile spec",
            declared_count=len(declared),
            expected_count=len(expected),
        )

    # ---- occupancy -------------------------------------------------------
    occupied: Dict[Cell, str] = {}
    powered: List[Tuple[str, Set[Cell]]] = []

    def occupy(name: str, cells: Iterable[Cell]) -> None:
        for cell in cells:
            if not (0 <= cell[0] < grid[0] and 0 <= cell[1] < grid[1]):
                issues.add(
                    "body_out_of_grid", f"{name} covers out-of-grid cell", cell=list(cell)
                )
                continue
            if cell in occupied:
                issues.add(
                    "body_overlap",
                    f"{name} overlaps {occupied[cell]}",
                    cell=list(cell),
                )
                continue
            occupied[cell] = name

    for index, item in enumerate(declared):
        name = f"{item['kind']}[{index}]"
        cells = cells_of(item["anchor"], (item["size"][0], item["size"][1]))
        occupy(name, cells)
        # Data driven, not assumed: under the frozen rules both the boundary
        # ports and the protocol core are needs_power=false, which is exactly why
        # the region model makes only decision bodies a power obligation.  Read
        # the flag so a rules change cannot silently drop the obligation.
        if bool(templates.get(item["kind"], {}).get("needs_power", False)):
            powered.append((name, set(cells)))

    placements = geometry.get("placements")
    if not isinstance(placements, list):
        raise AuditInputError("geometry.placements must be an array")
    parsed: List[Dict[str, Any]] = []
    for index, raw in enumerate(placements):
        if not isinstance(raw, dict):
            raise AuditInputError("placement entries must be objects")
        required = {
            "instance_id",
            "template",
            "orientation",
            "anchor",
            "mode",
            "operation_class",
            "active_input_fronts",
            "active_output_fronts",
        }
        missing = required - set(raw)
        if missing:
            raise AuditInputError(f"placement {index} misses {sorted(missing)}")
        template = str(raw["template"])
        if template not in templates:
            raise AuditInputError(f"placement {index} names unknown template {template}")
        orientation = int(raw["orientation"])
        size = footprint(templates, template, orientation)
        entry: Dict[str, Any] = {
            "instance_id": str(raw["instance_id"]),
            "template": template,
            "orientation": orientation,
            "anchor": [int(raw["anchor"][0]), int(raw["anchor"][1])],
            "size": size,
            "mode": str(raw["mode"]),
            "operation_class": str(raw["operation_class"]),
            "active_input_fronts": [
                (int(cell[0]), int(cell[1])) for cell in raw["active_input_fronts"]
            ],
            "active_output_fronts": [
                (int(cell[0]), int(cell[1])) for cell in raw["active_output_fronts"]
            ],
            "cells": cells_of([int(raw["anchor"][0]), int(raw["anchor"][1])], size),
        }
        parsed.append(entry)
        occupy(f"placement[{entry['instance_id']}]", entry["cells"])
        powered.append((entry["instance_id"], set(entry["cells"])))

    poles_raw = geometry.get("power_poles")
    if not isinstance(poles_raw, list):
        raise AuditInputError("geometry.power_poles must be an array")
    pole_template = templates.get("power_pole")
    if pole_template is None:
        raise AuditInputError("rules document has no power_pole template")
    pole_size = (
        int(pole_template["dimensions"]["w"]),
        int(pole_template["dimensions"]["h"]),
    )
    pole_radius = int(pole_template["power_coverage_radius"])
    poles: List[Tuple[str, FrozenSet[Cell]]] = []
    for index, raw in enumerate(poles_raw):
        if not isinstance(raw, dict) or "anchor" not in raw:
            raise AuditInputError("power_poles entries need an anchor")
        anchor = (int(raw["anchor"][0]), int(raw["anchor"][1]))
        name = f"power_pole[{index}]"
        occupy(name, cells_of(list(anchor), pole_size))
        stencil = frozenset(
            (x, y)
            for x in range(
                max(0, anchor[0] - pole_radius),
                min(grid[0], anchor[0] + pole_size[0] + pole_radius),
            )
            for y in range(
                max(0, anchor[1] - pole_radius),
                min(grid[1], anchor[1] + pole_size[1] + pole_radius),
            )
        )
        poles.append((name, stencil))

    occupied_cells = frozenset(occupied)
    free_cells = frozenset(
        (x, y)
        for x in range(grid[0])
        for y in range(grid[1])
        if (x, y) not in occupied_cells
    )

    # ---- class census ----------------------------------------------------
    census: Dict[str, int] = {}
    for entry in parsed:
        class_id = str(entry["operation_class"])
        census[class_id] = census.get(class_id, 0) + 1
    expected_census = {name: row["count"] for name, row in class_table.items()}
    if census != expected_census:
        issues.add(
            "class_census_mismatch",
            "operation class census differs from the derived class table",
            found=dict(sorted(census.items())),
            expected=dict(sorted(expected_census.items())),
        )

    # ---- per placement ---------------------------------------------------
    for entry in parsed:
        name = str(entry["instance_id"])
        row = class_table.get(str(entry["operation_class"]))
        if row is None:
            issues.add(
                "class_census_mismatch",
                f"{name} declares unknown operation class {entry['operation_class']}",
            )
            continue
        if row["template"] != entry["template"]:
            issues.add(
                "class_census_mismatch",
                f"{name} declares class {entry['operation_class']} on the wrong template",
                template=entry["template"],
                expected=row["template"],
            )
            continue
        allowed = legal_modes(templates, str(entry["template"]), int(entry["orientation"]))
        if entry["mode"] not in allowed:
            issues.add(
                "active_port_count_mismatch",
                f"{name} uses mode {entry['mode']} which this template/orientation "
                "does not offer",
                allowed=list(allowed),
            )
            continue
        in_side, out_side = _MODE_SIDES[str(entry["mode"])]
        body_anchor: Sequence[int] = entry["anchor"]
        body_size: Tuple[int, int] = entry["size"]
        legal_in = set(side_fronts(body_anchor, body_size, in_side))
        legal_out = set(side_fronts(body_anchor, body_size, out_side))
        for label, fronts, legal, side in (
            ("input", list(entry["active_input_fronts"]), legal_in, in_side),
            ("output", list(entry["active_output_fronts"]), legal_out, out_side),
        ):
            for cell in fronts:
                if cell not in legal:
                    detail = (
                        f"{name} {label} front {list(cell)} is not the first cell "
                        f"outside the {side} side"
                    )
                    issues.add(
                        "front_offset_violation",
                        detail,
                        second_cell_outside=cell in _second_cells(entry, side),
                    )
                    continue
                if not (0 <= cell[0] < grid[0] and 0 <= cell[1] < grid[1]):
                    issues.add(
                        "front_out_of_grid", f"{name} {label} front is off the board",
                        cell=list(cell),
                    )
                    continue
                if cell in occupied_cells:
                    issues.add(
                        "front_blocked",
                        f"{name} {label} front is covered by {occupied[cell]}",
                        cell=list(cell),
                    )
        for label, fronts, need in (
            ("input", list(entry["active_input_fronts"]), int(row["r_in"])),
            ("output", list(entry["active_output_fronts"]), int(row["r_out"])),
        ):
            if len(fronts) != need or len(set(fronts)) != len(fronts):
                issues.add(
                    "active_port_count_mismatch",
                    f"{name} declares {len(fronts)} distinct-checked {label} fronts, "
                    f"class {entry['operation_class']} needs {need}",
                )

        if _is_dead(entry, class_table, templates, occupied_cells, grid):
            issues.add(
                "dead_body_present",
                f"{name} can serve no operation class of its template",
                anchor=entry["anchor"],
                template=entry["template"],
            )

    # ---- reserved fronts -------------------------------------------------
    reserved = {
        (int(cell[0]), int(cell[1]))
        for item in declared
        for cell in item["front_cells"]
    }
    for cell in sorted(reserved):
        if not (0 <= cell[0] < grid[0] and 0 <= cell[1] < grid[1]):
            issues.add(
                "reserved_front_blocked",
                "fixed furniture front cell is off the board",
                cell=list(cell),
            )
        elif cell in occupied_cells:
            issues.add(
                "reserved_front_blocked",
                f"fixed furniture front cell is covered by {occupied[cell]}",
                cell=list(cell),
            )

    # ---- power -----------------------------------------------------------
    coverers: Dict[str, List[str]] = {}
    for instance_id, powered_cells in powered:
        hit = [name for name, stencil in poles if powered_cells & stencil]
        if not hit:
            issues.add(
                "power_coverage_missing", f"{instance_id} is not covered by any pole"
            )
        coverers[instance_id] = hit
    if len(poles) > len(powered):
        issues.add(
            "unforced_power_pole",
            f"{len(poles)} poles for {len(powered)} powered instances",
        )
    for name, _stencil in poles:
        served = [inst for inst, hit in coverers.items() if name in hit]
        if not served:
            issues.add("unforced_power_pole", f"{name} covers no powered instance")
        elif not any(coverers[inst] == [name] for inst in served):
            issues.add(
                "unforced_power_pole",
                f"{name} is never the sole coverer of any instance",
            )

    # ---- hole ------------------------------------------------------------
    hole = geometry.get("hole")
    hole_cells: Set[Any] = set()
    hole_summary: Optional[Dict[str, int]] = None
    if hole is None:
        issues.add("hole_invalid", "geometry declares no body-free hole")
    else:
        if not isinstance(hole, dict) or {"anchor", "width", "height"} - set(hole):
            raise AuditInputError("hole must be {anchor, width, height}")
        hx, hy = int(hole["anchor"][0]), int(hole["anchor"][1])
        hw, hh = int(hole["width"]), int(hole["height"])
        hole_summary = {"x": hx, "y": hy, "width": hw, "height": hh, "area": hw * hh,
                        "min_side": min(hw, hh)}
        if (hw, hh) not in ((6, 7), (7, 6)):
            issues.add("hole_invalid", f"hole is {hw}x{hh}, the G1 vocabulary is 6x7 or 7x6")
        if hw * hh < 42 or min(hw, hh) < 6:
            issues.add(
                "hole_invalid",
                f"hole is (area, min_side) = ({hw * hh}, {min(hw, hh)}), below (42, 6)",
            )
        hole_cells = set(cells_of([hx, hy], (hw, hh)))
        outside = [cell for cell in sorted(hole_cells)
                   if not (0 <= cell[0] < grid[0] and 0 <= cell[1] < grid[1])]
        if outside:
            issues.add("hole_invalid", "hole leaves the board", cell=list(outside[0]))
        blocked = sorted(hole_cells & occupied_cells)
        if blocked:
            issues.add(
                "hole_invalid",
                f"hole contains {len(blocked)} facility body cells",
                cell=list(blocked[0]),
            )

    # ---- free space ------------------------------------------------------
    components = connected_components(free_cells)
    anchors: Set[Any] = set(reserved) | hole_cells
    for entry in parsed:
        anchors.update(tuple(cell) for cell in entry["active_input_fronts"])
        anchors.update(tuple(cell) for cell in entry["active_output_fronts"])
    anchors = {cell for cell in anchors if cell in free_cells}
    hosting = [component for component in components if anchors & component]
    if len(hosting) > 1:
        issues.add(
            "free_space_disconnected",
            f"active fronts / reserved cells / hole span {len(hosting)} free-space "
            "components; G2 needs one corridor",
        )

    verdict = "PASS" if not issues.items else "FAIL"
    dead_count = sum(1 for item in issues.items if item["code"] == "dead_body_present")
    return {
        "schema": AUDIT_SCHEMA,
        "authority": {
            "is_authoritative": False,
            "carries_bound": False,
            "ledger_effect": "none",
        },
        "verdict": verdict,
        "issues": issues.items,
        "issue_codes": issues.codes(),
        "summary": {
            "grid": list(grid),
            "profile_id": profile_id,
            "manufacturing_placements": len(parsed),
            "dead_for_any_actual_class": dead_count,
            "class_census": dict(sorted(census.items())),
            "class_table": {
                name: {
                    "template": row["template"],
                    "r_in": row["r_in"],
                    "r_out": row["r_out"],
                    "count": row["count"],
                }
                for name, row in sorted(class_table.items())
            },
            "fixed_furniture": len(declared),
            "reserved_front_cells": len(reserved),
            "power": {
                "poles": len(poles),
                "powered_instances": len(powered),
                "irredundant": not any(
                    item["code"] == "unforced_power_pole" for item in issues.items
                ),
            },
            "hole": hole_summary,
            "free_space": {
                "components": len(components),
                "size": len(free_cells),
                "anchor_components": len(hosting),
            },
            "max_body_free_rectangle": max_body_free_rectangle(free_cells, grid),
        },
    }


def _second_cells(entry: Dict[str, Any], side: str) -> Set[Cell]:
    delta = {"top": (0, 1), "bottom": (0, -1), "left": (-1, 0), "right": (1, 0)}[side]
    return {
        (cell[0] + delta[0], cell[1] + delta[1])
        for cell in side_fronts(entry["anchor"], entry["size"], side)
    }


def _is_dead(
    entry: Dict[str, Any],
    class_table: Dict[str, Dict[str, Any]],
    templates: Any,
    occupied: FrozenSet[Cell],
    grid: Tuple[int, int],
) -> bool:
    """The document-19 necessary projection, recomputed from the final geometry."""
    free_counts: Dict[str, int] = {}
    for side in ("top", "bottom", "left", "right"):
        count = 0
        for cell in side_fronts(entry["anchor"], entry["size"], side):
            if not (0 <= cell[0] < grid[0] and 0 <= cell[1] < grid[1]):
                continue
            if cell in occupied:
                continue
            count += 1
        free_counts[side] = count
    for mode in legal_modes(templates, entry["template"], entry["orientation"]):
        in_side, out_side = _MODE_SIDES[mode]
        for row in class_table.values():
            if row["template"] != entry["template"]:
                continue
            if free_counts[in_side] >= row["r_in"] and free_counts[out_side] >= row["r_out"]:
                return False
    return True


# --------------------------------------------------------------------------
# self test
# --------------------------------------------------------------------------


def _toy_inputs(with_core: bool = False) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """A toy world exercising every structural check except the W0 pin itself.

    Two toy 3x3 recipes: a 1-in/1-out line and a 1-in/2-out splitter.  The
    boundary baselines are present (so reserved fronts are real cells), one pole
    powers both machines and a 7x6 hole sits in open space.  ``with_core=True``
    switches to a 24x24 board carrying a 9x9 protocol core, which is what makes
    the twenty core front cells a live reserve obligation.
    """
    rules = {
        "globals": {"logistics": {"belt_capacity_per_tick": 1.0}},
        "facility_templates": {
            "manufacturing_3x3": {
                "dimensions": {"w": 3, "h": 3},
                "port_rule": "opposite_parallel_sides",
                "needs_power": True,
            },
            "power_pole": {
                "dimensions": {"w": 2, "h": 2},
                "port_rule": "none",
                "needs_power": False,
                "power_coverage_radius": 5,
            },
            "boundary_storage_port": {
                "dimensions": {"w": 1, "h": 3},
                "port_rule": "inward_facing",
                "needs_power": False,
            },
            "protocol_core": {
                "dimensions": {"w": 9, "h": 9},
                "port_rule": "core_specific",
                "needs_power": False,
            },
        },
        "recipes": {
            "toy_line": {
                "template": "manufacturing_3x3",
                "ticks_per_cycle": 1,
                "inputs": {"a": 1},
                "outputs": {"b": 1},
            },
            "toy_split": {
                "template": "manufacturing_3x3",
                "ticks_per_cycle": 1,
                "inputs": {"b": 1},
                "outputs": {"c": 2},
            },
        },
    }
    instances = [
        {"instance_id": "toy_line_001", "operation_type": "toy_line"},
        {"instance_id": "toy_split_001", "operation_type": "toy_split"},
    ]
    side = 24 if with_core else 20
    profile_spec: Dict[str, Any] = {
        "boundary": {"period": 3, "start": 1, "left": True, "bottom": True},
        "core": (
            {
                "anchor": [12, 12],
                "size": [9, 9],
                "orientation": 1,
                "input_indices": [1, 2, 3, 4, 5, 6, 7],
                "output_indices": [1, 4, 7],
            }
            if with_core
            else None
        ),
    }
    geometry = {
        "schema": GEOMETRY_SCHEMA,
        "authority": {
            "is_authoritative": False,
            "carries_bound": False,
            "ledger_effect": "none",
        },
        "layout_profile": {
            "profile_id": f"toy_{side}x{side}_v1",
            "grid": [side, side],
            "fixed_furniture_spec": profile_spec,
        },
        "fixed_furniture": regenerate_fixed_furniture(profile_spec, (side, side)),
        "placements": [
            {
                "instance_id": "toy_line_001",
                "template": "manufacturing_3x3",
                "orientation": 0,
                "anchor": [3, 3],
                "mode": "TB",
                "operation_class": "3L",
                "provisional": True,
                "active_input_fronts": [[3, 6]],
                "active_output_fronts": [[3, 2]],
            },
            {
                "instance_id": "toy_split_001",
                "template": "manufacturing_3x3",
                "orientation": 0,
                "anchor": [8, 3],
                "mode": "BT",
                "operation_class": "3O2",
                "provisional": True,
                "active_input_fronts": [[8, 2]],
                "active_output_fronts": [[8, 6], [9, 6]],
            },
        ],
        "power_poles": [{"anchor": [6, 7]}],
        "hole": (
            {"anchor": [2, 15], "width": 7, "height": 6}
            if with_core
            else {"anchor": [10, 10], "width": 7, "height": 6}
        ),
    }
    return rules, instances, geometry


def self_test() -> int:
    for with_core in (False, True):
        rules, instances, geometry = _toy_inputs(with_core=with_core)
        report = audit(geometry, rules, instances)
        if report["verdict"] != "PASS" or report["issues"]:
            print(
                f"self-test FAILED: toy geometry (with_core={with_core}) did not pass",
                file=sys.stderr,
            )
            print(json.dumps(report["issues"], indent=2), file=sys.stderr)
            return 1
    rules, instances, geometry = _toy_inputs()
    # A single mutation must be caught: push one front to the retired second cell.
    broken = json.loads(json.dumps(geometry))
    broken["placements"][0]["active_input_fronts"] = [[3, 7]]
    negative = audit(broken, rules, instances)
    if "front_offset_violation" not in negative["issue_codes"]:
        print(
            "self-test FAILED: the second-cell-outside mutation was not caught",
            file=sys.stderr,
        )
        return 1
    print(
        "self-test OK: both toy geometries PASS, second-cell mutation rejected "
        f"({len(ISSUE_CODES)} issue codes registered)"
    )
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="W0 G1 independent front-viability audit")
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--rules", type=Path)
    parser.add_argument("--instances", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    missing = [
        name
        for name, value in (
            ("--geometry", args.geometry),
            ("--rules", args.rules),
            ("--instances", args.instances),
            ("--output", args.output),
        )
        if value is None
    ]
    if missing:
        print(f"missing required arguments: {', '.join(missing)}", file=sys.stderr)
        return 2

    try:
        geometry = load_json(args.geometry)
        rules = load_json(args.rules)
        instances = load_json(args.instances)
        report = audit(geometry, rules, instances)
    except AuditInputError as exc:
        print(f"audit input error: {exc}", file=sys.stderr)
        return 2

    report["inputs"] = {
        "geometry": {"path": str(args.geometry), "sha256": sha256_file(args.geometry)},
        "rules": {"path": str(args.rules), "sha256": sha256_file(args.rules)},
        "instances": {"path": str(args.instances), "sha256": sha256_file(args.instances)},
    }
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(args.output.parent), delete=False, newline="\n"
    )
    try:
        handle.write(payload)
        handle.close()
        os.replace(handle.name, args.output)
    except BaseException:
        handle.close()
        if os.path.exists(handle.name):
            os.unlink(handle.name)
        raise
    print(f"{report['verdict']}: {len(report['issues'])} issues -> {args.output}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
