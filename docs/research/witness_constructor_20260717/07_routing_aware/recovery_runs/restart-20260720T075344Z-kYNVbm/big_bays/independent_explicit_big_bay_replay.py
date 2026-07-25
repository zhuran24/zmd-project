#!/usr/bin/env python3
"""Pure-stdlib replay for one explicit-geometry large-bay search result."""

from __future__ import annotations

import argparse
from collections import Counter
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
HELPER = HERE / "independent_periodic_big_bay_replay.py"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED = {
    HELPER: "59ae9ec52084f463833751ebd45fbadd6a7287a52da937c50cfd697ea78135c7",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
GRID_SIZE = 70
GRID = {(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)}
VERTICAL_LANES = (1, 12, 24, 36, 48, 59)
HORIZONTAL_LANES = (1, 36, 59)
CORE_ANCHOR = (60, 60)
BAY_ORIGINS = {"c0": (13, 2), "c1": (25, 2), "c2": (37, 2)}
Cell = tuple[int, int]


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


for pinned_path, expected_digest in EXPECTED.items():
    require(pinned_path.is_file(), f"missing pinned input: {pinned_path}")
    require(sha256(pinned_path) == expected_digest, f"hash drift: {pinned_path}")

sys.path.insert(0, str(HERE))
import independent_periodic_big_bay_replay as helper  # noqa: E402


def parse_cells(raw: Any, label: str) -> set[Cell]:
    require(isinstance(raw, list), f"{label} must be list")
    result = {(int(item[0]), int(item[1])) for item in raw}
    require(len(result) == len(raw), f"duplicate {label}")
    return result


def protected_cells(bundle: Mapping[str, Any]) -> set[Cell]:
    if "protected_cells" in bundle:
        result = parse_cells(bundle["protected_cells"], "protected_cells")
    else:
        raw = bundle.get("protected_rect")
        require(isinstance(raw, dict), "bundle protected geometry")
        anchor = raw.get("anchor")
        require(isinstance(anchor, list) and len(anchor) == 2, "protected_rect.anchor")
        result = helper.rect(
            (int(anchor[0]), int(anchor[1])),
            int(raw.get("width")),
            int(raw.get("height")),
        )
    require(len(result) == 42 and result <= GRID, "protected 42 in-grid cells")
    return result


def explicit_fixed(strict: Mapping[str, Any], bundle: Mapping[str, Any]) -> dict[str, Any]:
    require(
        bundle.get("schema_version")
        in {"final_pole_protected_bundle.v1", "routing_geometry_bundle.v1", "routing_geometry_bundle.v2"},
        "geometry bundle schema",
    )
    poles = parse_cells(bundle.get("all_35_pole_anchors"), "all_35_pole_anchors")
    require(len(poles) == 35 and len(poles) >= 9, "35-pole/P>=9 sentinel")
    pole_cells = set().union(*(helper.rect(anchor, 2, 2) for anchor in poles))
    require(len(pole_cells) == 140 and pole_cells <= GRID, "pole bodies")
    protected = protected_cells(bundle)
    core = helper.rect(CORE_ANCHOR, 9, 9)
    core_ring = helper.rect((59, 59), 11, 11) - core
    backbone = (
        {(x, y) for x in VERTICAL_LANES for y in range(1, GRID_SIZE)}
        | {(x, y) for y in HORIZONTAL_LANES for x in range(1, GRID_SIZE)}
        | core_ring
    ) - core
    left_anchors = helper.boundary_anchors(69)
    bottom_anchors = helper.boundary_anchors(0)
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
        for anchor in poles
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
    parts = helper.components(GRID - forbidden)
    bays = {}
    gateways = {}
    for bay_name, origin in BAY_ORIGINS.items():
        matches = [part for part in parts if origin in part]
        require(len(matches) == 1, f"{bay_name} component cardinality")
        part = matches[0]
        observed_origin = (min(x for x, _y in part), min(y for _x, y in part))
        require(observed_origin == origin, f"{bay_name} origin drift")
        bays[bay_name] = part
        gateways[bay_name] = {
            cell for cell in part if any(adjacent in backbone for adjacent in helper.neighbours(cell))
        }
        require(gateways[bay_name], f"{bay_name} gateways")
    return {
        "backbone": backbone,
        "protected": protected,
        "poles": poles,
        "pole_cells": pole_cells,
        "fixed_body": fixed_body,
        "power": power,
        "forbidden": forbidden,
        "bays": bays,
        "gateways": gateways,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-bundle", type=Path, required=True)
    parser.add_argument("--geometry-sha256", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(args.geometry_bundle.is_file() and sha256(args.geometry_bundle) == args.geometry_sha256, "geometry hash")
    require(args.source.is_file() and sha256(args.source) == args.source_sha256, "source hash")
    require(not args.output.exists(), f"refusing overwrite: {args.output}")
    bundle = json.loads(args.geometry_bundle.read_bytes())
    source = json.loads(args.source.read_bytes())
    candidate = json.loads(CANDIDATE.read_bytes())
    strict = json.loads(STRICT.read_bytes())
    require(all(isinstance(raw, dict) for raw in (bundle, source, candidate, strict)), "root maps")
    require(source.get("schema_version") == "explicit_final_geometry_big_bay_checkpoint.v1", "source schema")
    require(source.get("status") in {"OPTIMAL", "FEASIBLE"}, "source status")
    require(source.get("geometry_bundle_sha256") == args.geometry_sha256, "source geometry binding")
    bay_name = str(source.get("bay"))
    require(bay_name in BAY_ORIGINS, "source bay")
    origin = BAY_ORIGINS[bay_name]
    target = tuple(int(value) for value in source["target"])
    fixed = explicit_fixed(strict, bundle)
    modes = helper.strict_mode_map(strict)
    domain_map = helper.domain(candidate, modes, fixed, bay_name)

    selected_internal = []
    for row in source["selected"]:
        key = helper.source_key(row, origin)
        require(key in domain_map, "selected normalized key absent from canonical domain")
        pose = domain_map[key]
        require(int(row["pose_index"]) == int(pose["pose_index"]), "selected pose index parity")
        selected_internal.append(pose)
    totals = tuple(Counter(pose["template"] for pose in selected_internal)[name] for name in helper.TEMPLATES)
    require(totals == target, "exact template totals")
    occupied: set[Cell] = set()
    for pose in selected_internal:
        require(not occupied & pose["body"], "body overlap")
        require(pose["body"] <= fixed["bays"][bay_name], "body outside component")
        require(not pose["body"] & fixed["forbidden"], "body/fixed collision")
        require(bool(pose["body"] & fixed["power"]), "body unpowered")
        occupied |= pose["body"]
    free = fixed["bays"][bay_name] - occupied
    main = helper.reachable(fixed["gateways"][bay_name], free)
    outside_main = fixed["backbone"] | fixed["protected"]
    chosen = Counter()
    for terminal in source["selected_weak_active"]:
        selected_index = int(terminal["selected_index"])
        require(0 <= selected_index < len(selected_internal), "terminal selected index")
        kind = str(terminal["kind"])
        require(kind in {"input", "output"}, "terminal kind")
        cell = (int(terminal["cell"][0]), int(terminal["cell"][1]))
        available = selected_internal[selected_index][f"{kind}s"]
        require(cell in available, "terminal/canonical port parity")
        require(cell not in occupied, "active front occupied")
        require(cell in main or cell in outside_main, "active front disconnected")
        chosen[(selected_index, kind)] += 1
    for index, pose in enumerate(selected_internal):
        need_in, need_out = helper.REQUIREMENTS[str(pose["template"])]
        require(chosen[(index, "input")] == need_in, "exact active input count")
        require(chosen[(index, "output")] == need_out, "exact active output count")
    active_count = sum(chosen.values())
    require(active_count == int(source["selected_weak_active_count"]), "active count parity")
    require(parse_cells(source["all_35_pole_anchors"], "source poles") == fixed["poles"], "source pole parity")
    require(parse_cells(source["protected_cells"], "source protected") == fixed["protected"], "source protected parity")
    if source.get("all_residual_connected") is True:
        require(main == free, "all-residual flag drift")

    checks = {
        "geometry_bundle_hash_and_source_binding": True,
        "canonical_candidate_and_strict_mode_port_parity": True,
        "exact_template_totals": True,
        "selected_bodies_nonoverlapping_in_component_and_powered": True,
        "selected_active_front_counts_exact_clear_and_connected": True,
        "pole_count_35_collision_free_and_p_ge_9": True,
        "protected_region_42_cells_and_source_parity": True,
    }
    report = {
        "schema_version": "independent_explicit_big_bay_replay.v1",
        "status": "PASS",
        "classification": "research_pure_stdlib_explicit_geometry_replay_no_solver_no_router",
        "claim_boundary": "One local bay replay only; no global layout or commodity-routing conclusion.",
        "geometry_bundle": str(args.geometry_bundle.resolve()),
        "geometry_bundle_sha256": args.geometry_sha256,
        "source": str(args.source.resolve()),
        "source_sha256": args.source_sha256,
        "bay": bay_name,
        "origin": list(origin),
        "target": list(target),
        "connectivity_model": source["connectivity_model"],
        "counts": {
            "domain_pose_modes": len(domain_map),
            "component_cells": len(fixed["bays"][bay_name]),
            "gateway_cells": len(fixed["gateways"][bay_name]),
            "selected_facilities": len(selected_internal),
            "selected_body_cells": len(occupied),
            "selected_weak_active": active_count,
            "residual_cells": len(free),
            "residual_main_cells": len(main),
            "residual_pocket_cells": len(free - main),
        },
        "checks": checks,
    }
    require(all(checks.values()), "replay checks")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
