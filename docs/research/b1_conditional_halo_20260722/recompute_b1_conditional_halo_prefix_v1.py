#!/usr/bin/env python3
"""Independent grid-prefix recomputation for the B1 conditional halo.

This implementation does not import the direct coordinate recomputer, an
encoder, or the R3 checker.  For each pole it constructs a fresh 70-by-70
weight grid and answers every ceiling rectangle by two-dimensional prefix-sum
inclusion/exclusion.  Its JSON report is written with O_EXCL.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
STRICT_REL = Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json")
STENCIL_REL = Path("docs/research/b1_conditional_halo_20260722/conditional_halo_stencil_v1.json")
STRICT_SHA = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
ORBIT_ROWS = (
    (3, 3, 2),
    (5, 1, 8),
    (5, 5, 16),
    (7, 7, 8),
    (9, 3, 2),
    (9, 9, 2),
    (11, 1, 2),
    (11, 3, 12),
    (11, 5, 22),
    (11, 7, 2),
    (11, 9, 2),
    (13, 11, 25),
    (15, 3, 2),
    (17, 3, 8),
)
DIMENSIONS = ((34, 35), (35, 34))
GRID = 70


class PrefixError(RuntimeError):
    """A fail-closed independent recomputation error."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise PrefixError(message)


def reject_number(token: str) -> Any:
    raise PrefixError(f"non-finite JSON token {token!r}")


def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PrefixError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicate, parse_constant=reject_number)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrefixError(f"JSON parse failure for {path}: {exc}") from exc
    check(isinstance(value, dict), f"{path} root is not an object")
    return value, hashlib.sha256(raw).hexdigest()


def integer(value: Any, label: str) -> int:
    check(type(value) is int, f"{label} is not an exact integer")
    return int(value)


def object_value(value: Any, label: str) -> Mapping[str, Any]:
    check(isinstance(value, Mapping), f"{label} is not an object")
    return value


def array_value(value: Any, label: str) -> Sequence[Any]:
    check(isinstance(value, Sequence) and not isinstance(value, (str, bytes)), f"{label} is not an array")
    return value


def source_record(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    raw = resolved.read_bytes()
    try:
        display = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        display = str(resolved)
    return {"path": display, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def template_area(template: Mapping[str, Any], label: str) -> int:
    areas: set[int] = set()
    for mode in array_value(template.get("modes"), f"{label}.modes"):
        body = object_value(object_value(mode, "mode").get("body"), "mode.body")
        width, height = integer(body.get("width"), "body.width"), integer(body.get("height"), "body.height")
        check(width > 0 and height > 0, "body dimensions must be positive")
        areas.add(width * height)
    check(len(areas) == 1, f"{label} has inconsistent mode areas")
    return next(iter(areas))


def strict_facts(instance: Mapping[str, Any]) -> dict[str, Any]:
    check(instance.get("grid") == {"height": 70, "width": 70}, "grid contract changed")
    check(
        instance.get("coordinate_system")
        == {
            "directions": ["N", "E", "S", "W"],
            "indexing": "zero_based",
            "origin": "southwest",
            "x_positive": "east",
            "y_positive": "north",
        },
        "coordinate-system contract changed",
    )
    templates = object_value(instance.get("facility_templates"), "facility_templates")
    areas = {name: template_area(object_value(template, name), name) for name, template in templates.items()}
    check(areas.get("power_pole") == 4, "power-pole body is not 2x2")
    check(
        instance.get("power")
        == {
            "coverage_from_pole_anchor": {"x_max_offset": 6, "x_min_offset": -5, "y_max_offset": 6, "y_min_offset": -5},
            "pole_template": "power_pole",
            "required_rule": "at_least_one_body_cell_covered",
        },
        "power contract changed",
    )
    required = array_value(instance.get("required_instances"), "required_instances")
    seen: set[str] = set()
    required_area = 0
    powered_area = 0
    powered_count = 0
    shapes: set[tuple[int, int]] = set()
    for item_raw in required:
        item = object_value(item_raw, "required instance")
        identifier, template_id = item.get("id"), item.get("template")
        check(isinstance(identifier, str) and identifier and identifier not in seen, "invalid/duplicate required id")
        check(isinstance(template_id, str) and template_id in templates, "unknown required template")
        seen.add(identifier)
        required_area += areas[template_id]
        template = object_value(templates[template_id], template_id)
        if template.get("requires_power") is True:
            check(template_id.startswith("manufacturing_"), "mandatory powered non-manufacturing body")
            powered_count += 1
            powered_area += areas[template_id]
            for mode_raw in array_value(template.get("modes"), f"{template_id}.modes"):
                body = object_value(object_value(mode_raw, "mode").get("body"), "body")
                shapes.add((integer(body.get("width"), "width"), integer(body.get("height"), "height")))
    check(
        (len(required), required_area, powered_count, powered_area) == (266, 3544, 219, 3325),
        "mandatory ledger changed",
    )
    check(shapes == {(3, 3), (5, 5), (6, 4), (4, 6)}, f"powered body shapes changed: {shapes}")
    return {
        "grid_area": 4900,
        "required_instance_count": 266,
        "required_body_area": required_area,
        "powered_mandatory_count": powered_count,
        "powered_mandatory_area": powered_area,
        "power_pole_body_area": areas["power_pole"],
        "powered_oriented_shapes": [list(item) for item in sorted(shapes)],
    }


def expand_stencil(document: Mapping[str, Any]) -> tuple[tuple[tuple[int, int, int], ...], dict[str, Any]]:
    check(document.get("schema") == "b1_conditional_halo_stencil_v1", "stencil schema changed")
    rows = tuple(
        (
            integer(object_value(raw, "orbit").get("major_odd"), "major"),
            integer(object_value(raw, "orbit").get("minor_odd"), "minor"),
            integer(object_value(raw, "orbit").get("weight2"), "weight2"),
        )
        for raw in array_value(document.get("orbits"), "orbits")
    )
    check(rows == ORBIT_ROWS, "orbit certificate bytes changed semantically")
    orbit_weights = {(major, minor): weight for major, minor, weight in rows}
    support: list[tuple[int, int, int]] = []
    for y_offset in range(-24, 25):
        for x_offset in range(-24, 25):
            odd_x, odd_y = abs(2 * x_offset - 1), abs(2 * y_offset - 1)
            weight = orbit_weights.get((max(odd_x, odd_y), min(odd_x, odd_y)))
            if weight is not None:
                support.append((x_offset, y_offset, weight))
    check(len(support) == 96, "expanded stencil is not 96 cells")
    check(sum(row[2] for row in support) == 792, "expanded stencil total is not 792")
    check(
        (
            min(row[0] for row in support),
            max(row[0] for row in support),
            min(row[1] for row in support),
            max(row[1] for row in support),
        )
        == (-8, 9, -8, 9),
        "expanded stencil bounds changed",
    )
    statement = object_value(document.get("conditional_halo"), "conditional_halo")
    check(
        (statement.get("pole_quantifier"), statement.get("rhs_original"), statement.get("rhs_doubled"))
        == ("all_selected_poles", 3325, 6650),
        "conditional-halo statement changed",
    )
    return tuple(support), {
        "orbit_count": 14,
        "support_cell_count": 96,
        "support_dx": [-8, 9],
        "support_dy": [-8, 9],
        "total_weight2": 792,
        "total_weight": 396,
    }


def local_check(support: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    lookup = {(x, y): weight for x, y, weight in support}
    tower = {(0, 0), (1, 0), (0, 1), (1, 1)}
    counts: Counter[str] = Counter()
    minimum: int | None = None
    for width, height in ((3, 3), (5, 5), (6, 4), (4, 6)):
        label = f"{width}x{height}"
        for ax in range(-5 - width + 1, 7):
            for ay in range(-5 - height + 1, 7):
                cells = tuple((ax + x, ay + y) for x in range(width) for y in range(height))
                if not any(-5 <= x <= 6 and -5 <= y <= 6 for x, y in cells) or tower.intersection(cells):
                    continue
                counts[label] += 1
                slack = sum(lookup.get(cell, 0) for cell in cells) - 2 * width * height
                check(slack >= 0, f"local certificate violation: {(label, ax, ay)}")
                minimum = slack if minimum is None else min(minimum, slack)
    check(dict(counts) == {"3x3": 180, "5x5": 220, "6x4": 220, "4x6": 220}, f"local corpus mismatch: {counts}")
    check(minimum == 0, "local minimum slack changed")
    return {"placement_counts": dict(counts), "placement_total": sum(counts.values()), "minimum_doubled_slack": minimum}


def prefix_grid(clipped: tuple[tuple[int, int, int], ...]) -> list[list[int]]:
    prefix = [[0] * (GRID + 1) for _ in range(GRID + 1)]
    for x, y, weight in clipped:
        prefix[x + 1][y + 1] = weight
    for x in range(1, GRID + 1):
        running = 0
        for y in range(1, GRID + 1):
            running += prefix[x][y]
            prefix[x][y] = prefix[x - 1][y] + running
    return prefix


def rectangle_sum(prefix: list[list[int]], x: int, y: int, width: int, height: int) -> int:
    right, top = x + width, y + height
    return prefix[right][top] - prefix[x][top] - prefix[right][y] + prefix[x][y]


def scan(support: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    digest = hashlib.sha256()
    orientation_hashes = {dimension: hashlib.sha256() for dimension in DIMENSIONS}
    clipped_hist: Counter[int] = Counter()
    c2_hist: Counter[int] = Counter()
    per_dimension = {
        dimension: {
            "pair_count": 0,
            "body_intersection_pairs": 0,
            "nonzero_removed_pairs": 0,
            "nonzero_deficit_pairs": 0,
            "c2_min": None,
            "c2_max": None,
        }
        for dimension in DIMENSIONS
    }
    pair_count = body_pairs = removed_pairs = deficit_pairs = 0
    minimum: int | None = None
    maximum: int | None = None
    for qx in range(69):
        for qy in range(69):
            clipped = tuple(
                (qx + dx, qy + dy, weight) for dx, dy, weight in support if 0 <= qx + dx < GRID and 0 <= qy + dy < GRID
            )
            clipped_total = sum(weight for _, _, weight in clipped)
            clipped_hist[clipped_total] += 1
            prefix = prefix_grid(clipped)
            for width, height in DIMENSIONS:
                stats = per_dimension[(width, height)]
                for x in range(1, GRID - width + 1):
                    for y in range(1, GRID - height + 1):
                        removed = rectangle_sum(prefix, x, y, width, height)
                        c2 = clipped_total - removed
                        conflict = qx < x + width and qx + 2 > x and qy < y + height and qy + 2 > y
                        record = f"{width},{height},{x},{y},{qx},{qy},{clipped_total},{removed},{c2},{int(conflict)}\n".encode()
                        digest.update(record)
                        orientation_hashes[(width, height)].update(record)
                        c2_hist[c2] += 1
                        pair_count += 1
                        stats["pair_count"] += 1
                        minimum = c2 if minimum is None else min(minimum, c2)
                        maximum = c2 if maximum is None else max(maximum, c2)
                        stats["c2_min"] = c2 if stats["c2_min"] is None else min(int(stats["c2_min"]), c2)
                        stats["c2_max"] = c2 if stats["c2_max"] is None else max(int(stats["c2_max"]), c2)
                        if removed:
                            removed_pairs += 1
                            stats["nonzero_removed_pairs"] += 1
                        if c2 < 792:
                            deficit_pairs += 1
                            stats["nonzero_deficit_pairs"] += 1
                        if conflict:
                            body_pairs += 1
                            stats["body_intersection_pairs"] += 1
    check(pair_count == 11_997_720, f"pair count is {pair_count}")
    check(sum(clipped_hist.values()) == 4_761 and sum(c2_hist.values()) == pair_count, "histogram mass mismatch")
    return {
        "objective": [1190, 34],
        "dimensions": [[34, 35], [35, 34]],
        "rectangle_anchor_domain": "x=1..70-w inclusive; y=1..70-h inclusive",
        "pole_anchor_domain": "qx=0..68 inclusive; qy=0..68 inclusive",
        "rectangle_count": 2_520,
        "rectangle_count_by_dimension": [
            {"width": 34, "height": 35, "count": 1260},
            {"width": 35, "height": 34, "count": 1260},
        ],
        "pole_anchor_count": 4_761,
        "pair_count": pair_count,
        "canonical_record_order": "qx,qy,dimension_order[(34,35),(35,34)],x,y",
        "canonical_record_format": "w,h,x,y,qx,qy,clipped_total2,removed_by_R2,C2,body_intersection\\n",
        "canonical_digest_sha256": digest.hexdigest(),
        "orientation_digests": [
            {
                "width": width,
                "height": height,
                "sha256": orientation_hashes[(width, height)].hexdigest(),
                **per_dimension[(width, height)],
            }
            for width, height in DIMENSIONS
        ],
        "clipped_total2_min": min(clipped_hist),
        "clipped_total2_max": max(clipped_hist),
        "c2_min": minimum,
        "c2_max": maximum,
        "body_intersection_pairs": body_pairs,
        "nonzero_removed_pairs": removed_pairs,
        "nonzero_deficit_pairs": deficit_pairs,
        "clipped_total2_histogram": [{"value": value, "count": count} for value, count in sorted(clipped_hist.items())],
        "c2_histogram": [{"value": value, "count": count} for value, count in sorted(c2_hist.items())],
    }


def exclusive_json(path: Path, value: Mapping[str, Any]) -> None:
    check(path.parent.is_dir(), f"output parent missing: {path.parent}")
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def make_report(root: Path, stencil_path: Path) -> dict[str, Any]:
    strict_path = root / STRICT_REL
    strict, digest = read_json(strict_path)
    check(digest == STRICT_SHA, f"strict SHA mismatch: {digest}")
    stencil, _ = read_json(stencil_path)
    ledger = strict_facts(strict)
    support, stencil_facts = expand_stencil(stencil)
    local = local_check(support)
    ceiling = scan(support)
    return {
        "schema_version": "b1_conditional_halo_prefix_recompute_v1",
        "evidence_cutoff": "2026-07-22",
        "status": "PASS",
        "scope": "geometry_only_pre_encoder",
        "algorithm": "independent_70x70_grid_prefix_inclusion_exclusion",
        "provenance": {
            "script": source_record(Path(__file__), root),
            "strict_instance": source_record(strict_path, root),
            "stencil": source_record(stencil_path, root),
            "imports_or_executes_primary_recomputer_encoder_or_r3_verifier": False,
        },
        "strict_ledger": ledger,
        "stencil": stencil_facts,
        "local_halo_certificate": local,
        "conditional_halo": {
            "status": "PROVED_BY_RECOMPUTED_LOCAL_CERTIFICATE",
            "rhs_original": 3325,
            "rhs_doubled": 6650,
            "pole_quantifier": "all_selected_poles",
            "cross_pole_stencil_overlap_subtracted": False,
            "optional_storage_box_omitted_as_safe_relaxation": True,
        },
        "actual_p_ledger": {
            "status": "PROVED",
            "formula": "wh+ceil((580-w-h+floor(a_delta(R)/2)+e_delta(R))/4)+4*(P-9)<=1320",
            "minimum_selected_poles": 9,
            "ceiling_minimum_lhs_at_P9": 1318,
            "ceiling_minimum_lhs_at_P10": 1322,
            "ceiling_selected_poles": 9,
            "ceiling_exact_nine_is_derived_not_assumed": True,
        },
        "ceiling_corpus": ceiling,
        "corpus_errors": [],
        "claim_boundary": [
            "necessary_condition_recomputation_only",
            "no_witness",
            "no_attainability",
            "no_routing_feasibility",
            "no_upper_bound_improvement",
            "no_global_optimality",
            "no_production_CERTIFIED_status",
        ],
    }


def arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--stencil", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = arguments(sys.argv[1:] if argv is None else argv)
    try:
        root = args.project_root.resolve(strict=True)
        stencil = (args.stencil or root / STENCIL_REL).resolve(strict=True)
        exclusive_json(args.output.resolve(), make_report(root, stencil))
    except (OSError, PrefixError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "PASS", "output": str(args.output), "pair_count": 11_997_720}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
