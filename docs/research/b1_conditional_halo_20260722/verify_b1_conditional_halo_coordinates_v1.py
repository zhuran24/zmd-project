#!/usr/bin/env python3
"""Direct coordinate recomputation for the B1 round-2 conditional halo.

The program expands the declarative 14-orbit stencil, rechecks the 840 local
placements, and visits the complete 2,520-by-4,761 ceiling corpus.  Rectangle
weights are accumulated by translating every clipped stencil cell into the
set of rectangle anchors that contain it.  No earlier checker or encoder is
imported.  The report is created with O_EXCL.
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


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_RELATIVE = Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json")
STENCIL_RELATIVE = Path("docs/research/b1_conditional_halo_20260722/conditional_halo_stencil_v1.json")
EXPECTED_STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
EXPECTED_ORBITS = (
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
GRID_SIZE = 70
CEILING_DIMENSIONS = ((34, 35), (35, 34))
EXPECTED_RECTANGLES = 2_520
EXPECTED_POLES = 4_761
EXPECTED_PAIRS = 11_997_720


class RecomputeError(RuntimeError):
    """A pinned input or mathematical invariant failed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecomputeError(message)


def _reject_constant(token: str) -> Any:
    raise RecomputeError(f"non-finite JSON token: {token}")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecomputeError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_json(path: Path) -> tuple[dict[str, Any], bytes, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=_object_pairs, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecomputeError(f"cannot parse {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} root must be an object")
    return value, raw, hashlib.sha256(raw).hexdigest()


def exact_int(value: Any, field: str) -> int:
    require(type(value) is int, f"{field} must be an exact integer")
    return int(value)


def as_mapping(value: Any, field: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{field} must be an object")
    return value


def as_sequence(value: Any, field: str) -> Sequence[Any]:
    require(isinstance(value, Sequence) and not isinstance(value, (str, bytes)), f"{field} must be an array")
    return value


def snapshot(path: Path, project_root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    require(resolved.is_file(), f"not a regular file: {resolved}")
    raw = resolved.read_bytes()
    try:
        display = resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        display = str(resolved)
    return {"path": display, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def mode_area(template: Mapping[str, Any], field: str) -> int:
    areas: set[int] = set()
    for index, raw_mode in enumerate(as_sequence(template.get("modes"), f"{field}.modes")):
        mode = as_mapping(raw_mode, f"{field}.modes[{index}]")
        body = as_mapping(mode.get("body"), f"{field}.modes[{index}].body")
        width = exact_int(body.get("width"), f"{field}.width")
        height = exact_int(body.get("height"), f"{field}.height")
        require(width > 0 and height > 0, f"{field} has nonpositive dimensions")
        areas.add(width * height)
    require(len(areas) == 1, f"{field} has mode-dependent area")
    return next(iter(areas))


def derive_strict_ledger(root: Mapping[str, Any]) -> dict[str, Any]:
    grid = as_mapping(root.get("grid"), "grid")
    require((grid.get("width"), grid.get("height")) == (70, 70), "grid drift")
    coordinates = as_mapping(root.get("coordinate_system"), "coordinate_system")
    require(
        (
            coordinates.get("indexing"),
            coordinates.get("origin"),
            coordinates.get("x_positive"),
            coordinates.get("y_positive"),
        )
        == ("zero_based", "southwest", "east", "north"),
        "coordinate-system drift",
    )
    templates = as_mapping(root.get("facility_templates"), "facility_templates")
    required = as_sequence(root.get("required_instances"), "required_instances")
    areas = {
        name: mode_area(as_mapping(value, f"template.{name}"), f"template.{name}") for name, value in templates.items()
    }
    require(areas.get("power_pole") == 4, "power-pole area drift")
    power = as_mapping(root.get("power"), "power")
    coverage = as_mapping(power.get("coverage_from_pole_anchor"), "power.coverage")
    require(
        coverage == {"x_max_offset": 6, "x_min_offset": -5, "y_max_offset": 6, "y_min_offset": -5},
        "coverage square drift",
    )
    require(power.get("pole_template") == "power_pole", "power-pole template drift")
    require(power.get("required_rule") == "at_least_one_body_cell_covered", "power rule drift")

    identifiers: set[str] = set()
    required_area = 0
    powered_area = 0
    powered_count = 0
    powered_shapes: set[tuple[int, int]] = set()
    for index, raw_item in enumerate(required):
        item = as_mapping(raw_item, f"required_instances[{index}]")
        identifier = item.get("id")
        template_name = item.get("template")
        require(type(identifier) is str and identifier and identifier not in identifiers, "bad/duplicate instance id")
        require(type(template_name) is str and template_name in templates, "unknown required template")
        identifiers.add(identifier)
        required_area += areas[template_name]
        template = as_mapping(templates[template_name], f"template.{template_name}")
        if template.get("requires_power") is True:
            require(template_name.startswith("manufacturing_"), "mandatory powered non-manufacturing instance")
            powered_count += 1
            powered_area += areas[template_name]
            for raw_mode in as_sequence(template.get("modes"), f"template.{template_name}.modes"):
                body = as_mapping(as_mapping(raw_mode, "powered mode").get("body"), "powered body")
                powered_shapes.add(
                    (exact_int(body.get("width"), "powered width"), exact_int(body.get("height"), "powered height"))
                )
    require(
        (len(required), required_area, powered_count, powered_area) == (266, 3544, 219, 3325),
        "strict area ledger drift",
    )
    require(powered_shapes == {(3, 3), (5, 5), (6, 4), (4, 6)}, f"powered shape drift: {powered_shapes}")
    return {
        "grid_area": 4_900,
        "required_instance_count": len(required),
        "required_body_area": required_area,
        "powered_mandatory_count": powered_count,
        "powered_mandatory_area": powered_area,
        "power_pole_body_area": areas["power_pole"],
        "powered_oriented_shapes": [list(shape) for shape in sorted(powered_shapes)],
    }


def derive_stencil(root: Mapping[str, Any]) -> tuple[tuple[tuple[int, int, int], ...], dict[str, Any]]:
    require(root.get("schema") == "b1_conditional_halo_stencil_v1", "stencil schema drift")
    require(root.get("evidence_cutoff") == "2026-07-22", "stencil cutoff drift")
    require(root.get("weight_units") == "doubled_integer", "stencil units drift")
    orbit_records = as_sequence(root.get("orbits"), "orbits")
    orbits = tuple(
        (
            exact_int(as_mapping(raw, "orbit").get("major_odd"), "major_odd"),
            exact_int(as_mapping(raw, "orbit").get("minor_odd"), "minor_odd"),
            exact_int(as_mapping(raw, "orbit").get("weight2"), "weight2"),
        )
        for raw in orbit_records
    )
    require(orbits == EXPECTED_ORBITS, "14-orbit table drift")
    weights = {(major, minor): weight for major, minor, weight in orbits}
    require(len(weights) == 14 and all(weight > 0 for weight in weights.values()), "invalid orbit table")
    support: list[tuple[int, int, int]] = []
    for dx in range(-20, 21):
        for dy in range(-20, 21):
            first, second = abs(2 * dx - 1), abs(2 * dy - 1)
            weight = weights.get((max(first, second), min(first, second)), 0)
            if weight:
                support.append((dx, dy, weight))
    require(len(support) == 96, "stencil support-cell count drift")
    require(sum(weight for _, _, weight in support) == 792, "stencil total doubled weight drift")
    require((min(x for x, _, _ in support), max(x for x, _, _ in support)) == (-8, 9), "stencil x support drift")
    require((min(y for _, y, _ in support), max(y for _, y, _ in support)) == (-8, 9), "stencil y support drift")
    expected = as_mapping(root.get("expected"), "expected")
    require(
        (
            expected.get("orbit_count"),
            expected.get("support_cell_count"),
            expected.get("total_weight2"),
            expected.get("total_weight"),
        )
        == (14, 96, 792, 396),
        "stencil expected sentinels drift",
    )
    conditional = as_mapping(root.get("conditional_halo"), "conditional_halo")
    require(
        (conditional.get("pole_quantifier"), conditional.get("rhs_original"), conditional.get("rhs_doubled"))
        == ("all_selected_poles", 3325, 6650),
        "conditional-halo statement drift",
    )
    return tuple(support), {
        "orbit_count": len(orbits),
        "support_cell_count": len(support),
        "support_dx": [-8, 9],
        "support_dy": [-8, 9],
        "total_weight2": 792,
        "total_weight": 396,
    }


def check_local_certificate(support: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    weights = {(x, y): weight for x, y, weight in support}
    pole_body = {(0, 0), (0, 1), (1, 0), (1, 1)}
    counts: dict[str, int] = {}
    minimum_slack: int | None = None
    for width, height in ((3, 3), (5, 5), (6, 4), (4, 6)):
        count = 0
        for anchor_x in range(-5 - width + 1, 7):
            for anchor_y in range(-5 - height + 1, 7):
                body = {(anchor_x + dx, anchor_y + dy) for dx in range(width) for dy in range(height)}
                if not any(-5 <= x <= 6 and -5 <= y <= 6 for x, y in body):
                    continue
                if body & pole_body:
                    continue
                count += 1
                slack = sum(weights.get(cell, 0) for cell in body) - 2 * width * height
                require(slack >= 0, f"local halo violation at {(width, height, anchor_x, anchor_y)}")
                minimum_slack = slack if minimum_slack is None else min(minimum_slack, slack)
        counts[f"{width}x{height}"] = count
    require(counts == {"3x3": 180, "5x5": 220, "6x4": 220, "4x6": 220}, f"840-placement corpus drift: {counts}")
    require(minimum_slack == 0, "local halo minimum slack drift")
    return {"placement_counts": counts, "placement_total": sum(counts.values()), "minimum_doubled_slack": minimum_slack}


def rectangles() -> tuple[tuple[int, int, int, int], ...]:
    result = tuple(
        (width, height, x, y)
        for width, height in CEILING_DIMENSIONS
        for x in range(1, GRID_SIZE - width + 1)
        for y in range(1, GRID_SIZE - height + 1)
    )
    require(len(result) == EXPECTED_RECTANGLES, f"ceiling rectangle count drift: {len(result)}")
    return result


def _range_add(diff: list[list[int]], x0: int, x1: int, y0: int, y1: int, weight: int) -> None:
    diff[x0][y0] += weight
    diff[x1 + 1][y0] -= weight
    diff[x0][y1 + 1] -= weight
    diff[x1 + 1][y1 + 1] += weight


def accumulate_orientation(clipped: tuple[tuple[int, int, int], ...], width: int, height: int) -> list[list[int]]:
    """Map each weighted cell directly to all containing rectangle anchors."""
    count_x, count_y = GRID_SIZE - width, GRID_SIZE - height
    diff = [[0] * (count_y + 1) for _ in range(count_x + 1)]
    for cell_x, cell_y, weight in clipped:
        low_x, high_x = max(1, cell_x - width + 1), min(cell_x, count_x)
        low_y, high_y = max(1, cell_y - height + 1), min(cell_y, count_y)
        if low_x <= high_x and low_y <= high_y:
            _range_add(diff, low_x - 1, high_x - 1, low_y - 1, high_y - 1, weight)
    for ix in range(count_x):
        running = 0
        for iy in range(count_y):
            running += diff[ix][iy]
            diff[ix][iy] = running + (diff[ix - 1][iy] if ix else 0)
    return [row[:count_y] for row in diff[:count_x]]


def scan_ceiling(support: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    rectangle_records = rectangles()
    rectangle_count_by_dimension = Counter((w, h) for w, h, _, _ in rectangle_records)
    require(rectangle_count_by_dimension == Counter({(34, 35): 1260, (35, 34): 1260}), "orientation count drift")

    digest = hashlib.sha256()
    orientation_digests = {dimension: hashlib.sha256() for dimension in CEILING_DIMENSIONS}
    c2_histogram: Counter[int] = Counter()
    clipped_histogram: Counter[int] = Counter()
    body_conflicts = 0
    nonzero_removed = 0
    nonzero_deficit = 0
    pair_count = 0
    c2_min: int | None = None
    c2_max: int | None = None
    per_orientation = {
        dimension: {
            "pair_count": 0,
            "body_intersection_pairs": 0,
            "nonzero_removed_pairs": 0,
            "nonzero_deficit_pairs": 0,
            "c2_min": None,
            "c2_max": None,
        }
        for dimension in CEILING_DIMENSIONS
    }

    for pole_x in range(69):
        for pole_y in range(69):
            clipped = tuple(
                (pole_x + dx, pole_y + dy, weight)
                for dx, dy, weight in support
                if 0 <= pole_x + dx < GRID_SIZE and 0 <= pole_y + dy < GRID_SIZE
            )
            clipped_total = sum(weight for _, _, weight in clipped)
            clipped_histogram[clipped_total] += 1
            for width, height in CEILING_DIMENSIONS:
                removed_grid = accumulate_orientation(clipped, width, height)
                stats = per_orientation[(width, height)]
                for x in range(1, GRID_SIZE - width + 1):
                    for y in range(1, GRID_SIZE - height + 1):
                        removed = removed_grid[x - 1][y - 1]
                        c2 = clipped_total - removed
                        body_intersects = (
                            pole_x < x + width and pole_x + 2 > x and pole_y < y + height and pole_y + 2 > y
                        )
                        record = f"{width},{height},{x},{y},{pole_x},{pole_y},{clipped_total},{removed},{c2},{int(body_intersects)}\n".encode()
                        digest.update(record)
                        orientation_digests[(width, height)].update(record)
                        pair_count += 1
                        stats["pair_count"] += 1
                        c2_histogram[c2] += 1
                        c2_min = c2 if c2_min is None else min(c2_min, c2)
                        c2_max = c2 if c2_max is None else max(c2_max, c2)
                        stats["c2_min"] = c2 if stats["c2_min"] is None else min(int(stats["c2_min"]), c2)
                        stats["c2_max"] = c2 if stats["c2_max"] is None else max(int(stats["c2_max"]), c2)
                        if removed:
                            nonzero_removed += 1
                            stats["nonzero_removed_pairs"] += 1
                        if c2 < 792:
                            nonzero_deficit += 1
                            stats["nonzero_deficit_pairs"] += 1
                        if body_intersects:
                            body_conflicts += 1
                            stats["body_intersection_pairs"] += 1
    require(pair_count == EXPECTED_PAIRS, f"ceiling pair count drift: {pair_count}")
    require(sum(clipped_histogram.values()) == EXPECTED_POLES, "pole-anchor histogram mass drift")
    require(sum(c2_histogram.values()) == EXPECTED_PAIRS, "C2 histogram mass drift")
    return {
        "objective": [1190, 34],
        "dimensions": [list(dimension) for dimension in CEILING_DIMENSIONS],
        "rectangle_anchor_domain": "x=1..70-w inclusive; y=1..70-h inclusive",
        "pole_anchor_domain": "qx=0..68 inclusive; qy=0..68 inclusive",
        "rectangle_count": EXPECTED_RECTANGLES,
        "rectangle_count_by_dimension": [
            {"width": w, "height": h, "count": rectangle_count_by_dimension[(w, h)]} for w, h in CEILING_DIMENSIONS
        ],
        "pole_anchor_count": EXPECTED_POLES,
        "pair_count": pair_count,
        "canonical_record_order": "qx,qy,dimension_order[(34,35),(35,34)],x,y",
        "canonical_record_format": "w,h,x,y,qx,qy,clipped_total2,removed_by_R2,C2,body_intersection\\n",
        "canonical_digest_sha256": digest.hexdigest(),
        "orientation_digests": [
            {"width": w, "height": h, "sha256": orientation_digests[(w, h)].hexdigest(), **per_orientation[(w, h)]}
            for w, h in CEILING_DIMENSIONS
        ],
        "clipped_total2_min": min(clipped_histogram),
        "clipped_total2_max": max(clipped_histogram),
        "c2_min": c2_min,
        "c2_max": c2_max,
        "body_intersection_pairs": body_conflicts,
        "nonzero_removed_pairs": nonzero_removed,
        "nonzero_deficit_pairs": nonzero_deficit,
        "clipped_total2_histogram": [
            {"value": value, "count": count} for value, count in sorted(clipped_histogram.items())
        ],
        "c2_histogram": [{"value": value, "count": count} for value, count in sorted(c2_histogram.items())],
    }


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    require(path.parent.is_dir(), f"output parent does not exist: {path.parent}")
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


def build_report(project_root: Path, stencil_path: Path) -> dict[str, Any]:
    strict_path = project_root / STRICT_RELATIVE
    strict, _, strict_sha = load_json(strict_path)
    require(strict_sha == EXPECTED_STRICT_SHA256, f"strict SHA drift: {strict_sha}")
    stencil, _, _ = load_json(stencil_path)
    ledger = derive_strict_ledger(strict)
    support, stencil_summary = derive_stencil(stencil)
    local = check_local_certificate(support)
    require(ledger["powered_mandatory_area"] * 2 == 6650, "doubled powered-area drift")
    require(-(-ledger["powered_mandatory_area"] // stencil_summary["total_weight"]) == 9, "P>=9 drift")
    ceiling = scan_ceiling(support)
    actual_p = {
        "status": "PROVED",
        "formula": "wh+ceil((580-w-h+floor(a_delta(R)/2)+e_delta(R))/4)+4*(P-9)<=1320",
        "minimum_selected_poles": 9,
        "ceiling_minimum_lhs_at_P9": 1318,
        "ceiling_minimum_lhs_at_P10": 1322,
        "ceiling_selected_poles": 9,
        "ceiling_exact_nine_is_derived_not_assumed": True,
    }
    return {
        "schema_version": "b1_conditional_halo_coordinate_recompute_v1",
        "evidence_cutoff": "2026-07-22",
        "status": "PASS",
        "scope": "geometry_only_pre_encoder",
        "algorithm": "direct_weighted_cell_to_rectangle_anchor_accumulation",
        "provenance": {
            "script": snapshot(Path(__file__), project_root),
            "strict_instance": snapshot(strict_path, project_root),
            "stencil": snapshot(stencil_path, project_root),
            "imports_or_executes_other_recomputer_encoder_or_r3_verifier": False,
        },
        "strict_ledger": ledger,
        "stencil": stencil_summary,
        "local_halo_certificate": local,
        "conditional_halo": {
            "status": "PROVED_BY_RECOMPUTED_LOCAL_CERTIFICATE",
            "rhs_original": 3325,
            "rhs_doubled": 6650,
            "pole_quantifier": "all_selected_poles",
            "cross_pole_stencil_overlap_subtracted": False,
            "optional_storage_box_omitted_as_safe_relaxation": True,
        },
        "actual_p_ledger": actual_p,
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


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--stencil", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        project_root = args.project_root.resolve(strict=True)
        stencil_path = (args.stencil or (project_root / STENCIL_RELATIVE)).resolve(strict=True)
        report = build_report(project_root, stencil_path)
        write_exclusive(args.output.resolve(), report)
    except (OSError, RecomputeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "PASS", "output": str(args.output), "pair_count": EXPECTED_PAIRS}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
