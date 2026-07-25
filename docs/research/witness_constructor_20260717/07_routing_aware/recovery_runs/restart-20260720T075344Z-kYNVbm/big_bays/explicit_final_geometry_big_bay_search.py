#!/usr/bin/env python3
"""Search one large-bay target against an explicit pole/protected bundle.

The bundle digest is mandatory on the command line and is copied into the
exclusive result checkpoint.  Weak active-terminal connectivity is the default;
the stronger all-residual model must be explicitly requested.  No production
router is imported or run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
HERE = RECOVERY / "big_bays"
ALL_RESIDUAL_SCRIPT = HERE / "big_bay_all_residual_search.py"
EXPECTED_ALL_RESIDUAL_SHA256 = "7d357c8ab1293698bd9381202890380aeb3464a3b6b5952cd5ab5df5803ef92a"
GRID_SIZE = 70
GRID = {(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)}
VERTICAL_LANES = (1, 12, 24, 36, 48, 59)
HORIZONTAL_LANES = (1, 36, 59)
CORE_ANCHOR = (60, 60)
CORE_SIZE = (9, 9)
BAY_ORIGINS = {"c0": (13, 2), "c1": (25, 2), "c2": (37, 2)}
Cell = tuple[int, int]


class SearchError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SearchError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


require(sha256(ALL_RESIDUAL_SCRIPT) == EXPECTED_ALL_RESIDUAL_SHA256, "pinned solver helper hash drift")
sys.path.insert(0, str(HERE))
import big_bay_all_residual_search as all_residual  # noqa: E402


def rect(anchor: Cell, width: int, height: int) -> set[Cell]:
    return {
        (x, y)
        for x in range(anchor[0], anchor[0] + width)
        for y in range(anchor[1], anchor[1] + height)
    }


def cells(raw: Any, label: str) -> set[Cell]:
    require(isinstance(raw, list), f"{label} must be a list")
    parsed = {(int(item[0]), int(item[1])) for item in raw}
    require(len(parsed) == len(raw), f"duplicate {label}")
    return parsed


def protected_cells(bundle: Mapping[str, Any]) -> set[Cell]:
    if "protected_cells" in bundle:
        result = cells(bundle["protected_cells"], "protected_cells")
    else:
        raw = bundle.get("protected_rect")
        require(isinstance(raw, dict), "bundle requires protected_cells or protected_rect")
        anchor_raw = raw.get("anchor")
        require(isinstance(anchor_raw, list) and len(anchor_raw) == 2, "protected_rect.anchor")
        result = rect(
            (int(anchor_raw[0]), int(anchor_raw[1])),
            int(raw.get("width")),
            int(raw.get("height")),
        )
    require(len(result) == 42 and result <= GRID, "protected region must contain 42 in-grid cells")
    return result


def boundary_anchors(gap: int) -> list[int]:
    return list(range(0, gap, 3)) + [gap + 1 + 3 * index for index in range(23 - gap // 3)]


def explicit_fixed(strict: Mapping[str, Any], bundle: Mapping[str, Any], bay_name: str) -> dict[str, Any]:
    require(
        bundle.get("schema_version")
        in {"final_pole_protected_bundle.v1", "routing_geometry_bundle.v1", "routing_geometry_bundle.v2"},
        "geometry bundle schema",
    )
    pole_anchors = cells(bundle.get("all_35_pole_anchors"), "all_35_pole_anchors")
    require(len(pole_anchors) == 35 and len(pole_anchors) >= 9, "35-pole/P>=9 sentinel")
    pole_cells = set().union(*(rect(anchor, 2, 2) for anchor in pole_anchors))
    require(len(pole_cells) == 140 and pole_cells <= GRID, "pole body overlap/out-of-grid")
    protected = protected_cells(bundle)
    core = rect(CORE_ANCHOR, CORE_SIZE[0], CORE_SIZE[1])
    core_ring = rect((59, 59), 11, 11) - core
    backbone = (
        {(x, y) for x in VERTICAL_LANES for y in range(1, GRID_SIZE)}
        | {(x, y) for y in HORIZONTAL_LANES for x in range(1, GRID_SIZE)}
        | core_ring
    ) - core
    left_anchors = boundary_anchors(69)
    bottom_anchors = boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left_anchors for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom_anchors for x in range(anchor, anchor + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(not pole_cells & (core | boundary | backbone | protected), "pole/fixed collision")
    require(not fixed_body & (backbone | protected), "fixed separator collision")
    power_rule = strict["power"]["coverage_from_pole_anchor"]
    power = {
        (x, y)
        for anchor in pole_anchors
        for x in range(
            max(0, anchor[0] + int(power_rule["x_min_offset"])),
            min(GRID_SIZE - 1, anchor[0] + int(power_rule["x_max_offset"])) + 1,
        )
        for y in range(
            max(0, anchor[1] + int(power_rule["y_min_offset"])),
            min(GRID_SIZE - 1, anchor[1] + int(power_rule["y_max_offset"])) + 1,
        )
    }
    forbidden = fixed_body | backbone | protected
    origin = BAY_ORIGINS[bay_name]
    parts = all_residual.geometry.components(GRID - forbidden)
    matches = [part for part in parts if origin in part]
    require(len(matches) == 1, f"{bay_name} component cardinality")
    component = matches[0]
    observed_origin = (min(x for x, _y in component), min(y for _x, y in component))
    require(observed_origin == origin, f"{bay_name} origin drift: {observed_origin}")
    gateways = {
        cell
        for cell in component
        if any(adjacent in backbone for adjacent in all_residual.geometry.neighbours(cell))
    }
    require(gateways, f"{bay_name} gateways")
    return {
        "core": core,
        "backbone": backbone,
        "protected": protected,
        "pole_anchors": pole_anchors,
        "pole_cells": pole_cells,
        "boundary": boundary,
        "fixed_body": fixed_body,
        "forbidden": forbidden,
        "power": power,
        "c5": component,
        "origin": origin,
        "gateways": gateways,
    }


def output_path(
    target: tuple[int, int, int],
    bay_name: str,
    model_name: str,
    bundle_digest: str,
    seconds: float,
) -> Path:
    target_text = "-".join(str(value) for value in target)
    return (
        HERE
        / "explicit_final_geometry_attempts"
        / bundle_digest[:12]
        / bay_name
        / f"t{target_text}_{model_name}_s{int(seconds)}.json"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-bundle", type=Path, required=True)
    parser.add_argument("--geometry-sha256", required=True)
    parser.add_argument("--bay", choices=tuple(BAY_ORIGINS), default="c0")
    parser.add_argument("--target", type=int, nargs=3, required=True)
    parser.add_argument("--model", choices=("optional-terminal", "all-residual"), default="optional-terminal")
    parser.add_argument("--seconds", type=float, default=240.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    require(args.geometry_bundle.is_file(), "geometry bundle missing")
    observed_bundle_digest = sha256(args.geometry_bundle)
    require(observed_bundle_digest == args.geometry_sha256, "geometry bundle hash mismatch")
    require(len(args.geometry_sha256) == 64, "geometry digest length")
    require(60.0 <= args.seconds <= 300.0, "seconds must be within [60,300]")
    require(args.workers == 8, "search is pinned to 8 workers")
    target = tuple(int(value) for value in args.target)
    require(len(target) == 3 and all(value >= 0 for value in target), "target")
    output = output_path(target, args.bay, args.model, observed_bundle_digest, args.seconds)
    require(not output.exists(), f"refusing overwrite: {output}")

    geometry = all_residual.geometry
    candidate = geometry.load_pinned(geometry.CANDIDATE_PATH)
    strict = geometry.load_pinned(geometry.STRICT_PATH)
    old = geometry.load_pinned(geometry.HINT_PATH)
    bundle = json.loads(args.geometry_bundle.read_bytes())
    require(isinstance(bundle, dict), "geometry bundle root")
    fixed = explicit_fixed(strict, bundle, args.bay)
    modes = geometry.base.strict_modes(strict)
    poses, domain_counts = geometry.base.build_domain(candidate, modes, fixed)
    hints = geometry.hint_body_modes(old, args.bay, fixed["origin"])
    if args.model == "optional-terminal":
        result = geometry.base.solve_phase(
            poses,
            target,
            fixed,
            hints,
            args.seconds,
            args.workers,
            20260722 + tuple(BAY_ORIGINS).index(args.bay),
        )
    else:
        result = all_residual.solve_all_residual(
            poses,
            target,
            fixed,
            hints,
            args.seconds,
            args.workers,
            20261722 + tuple(BAY_ORIGINS).index(args.bay),
        )
    result.update(
        {
            "schema_version": "explicit_final_geometry_big_bay_checkpoint.v1",
            "classification": "research_local_explicit_geometry_big_bay_query_no_router",
            "claim_boundary": "One local large-bay query under one hash-pinned geometry; no global layout or routing conclusion.",
            "geometry_bundle": str(args.geometry_bundle.resolve()),
            "geometry_bundle_sha256": observed_bundle_digest,
            "geometry_bundle_schema": bundle["schema_version"],
            "bay": args.bay,
            "component": tuple(BAY_ORIGINS).index(args.bay),
            "origin": list(fixed["origin"]),
            "target": list(target),
            "connectivity_model": args.model,
            "all_35_pole_anchors": [list(anchor) for anchor in sorted(fixed["pole_anchors"])],
            "protected_cells": [list(cell) for cell in sorted(fixed["protected"])],
            "domain_counts": domain_counts,
            "seconds_limit": args.seconds,
            "search_script_sha256": sha256(Path(__file__)),
            "pinned_solver_helper_sha256": EXPECTED_ALL_RESIDUAL_SHA256,
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "status": result["status"]}, sort_keys=True))
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
