#!/usr/bin/env python3
"""Search c5 with the 6x7 protected rectangle relocated beside backbone x=59."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = ROOT / (
    "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
RUN = RECOVERY / "relocated-protected-c5-aeSpkH"
HELPER_SOURCE = RECOVERY / "scripts/c5_pole_phase_search.py"
HINT = RECOVERY / "inputs/reduced_targeted_allocation_p7_36_final.json"
C11_RESULT = RECOVERY / "c11-protected-relocation-probe-EYLj1q/result.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED = {
    HELPER_SOURCE: "c7053f9ff3adc41f6d5519c2d76e45b663de2cc4c8b21c53959cf8acff666620",
    HINT: "6c51a1ee5bef15e555242896a0a11da24c8f18746a215db53c277deee537ee80",
    C11_RESULT: "7777f458f4b6856f7fde55d7a923c32c691cac1d0a1363e707905de05766a230",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
TARGET = (12, 3, 3)
PHASE_Y = (10, 18, 26, 29)
TOP_FROM = {(x, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
TOP_TO = {(x + 1, y) for x, y in TOP_FROM}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def build_fixed(helper: Any, strict: Mapping[str, Any], protected_y: int) -> dict[str, Any]:
    core = helper.rect(helper.CORE_ANCHOR, 9, 9)
    backbone = (
        {(x, y) for x in helper.VERTICAL_LANES for y in range(1, helper.GRID_SIZE)}
        | {(x, y) for y in helper.HORIZONTAL_LANES for x in range(1, helper.GRID_SIZE)}
        | helper.ring(core)
    ) - core
    protected = helper.rect((60, protected_y), 6, 7)
    require(len(protected) == 42, "protected rectangle size")
    require(all((59, y) in backbone for y in range(protected_y, protected_y + 7)), "protected not backbone-adjacent")
    baseline = {
        (x, y) for x in helper.POLE_AXES for y in helper.POLE_AXES
    } - {(65, 65)}
    pole_anchors = (baseline - TOP_FROM) | TOP_TO
    require(len(pole_anchors) == 35, "pole count/uniqueness")
    pole_cells = set().union(*(helper.rect(anchor, 2, 2) for anchor in pole_anchors))
    require(len(pole_cells) == 140, "pole body overlap")
    left_anchors = helper.boundary_anchors(69)
    bottom_anchors = helper.boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left_anchors for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom_anchors for x in range(anchor, anchor + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(not protected & (fixed_body | backbone), "protected/fixed collision")
    require(not pole_cells & (core | boundary | backbone), "pole/fixed collision")
    power_rule = strict["power"]["coverage_from_pole_anchor"]
    power = {
        (x, y)
        for anchor in pole_anchors
        for x in range(
            max(0, anchor[0] + int(power_rule["x_min_offset"])),
            min(helper.GRID_SIZE - 1, anchor[0] + int(power_rule["x_max_offset"])) + 1,
        )
        for y in range(
            max(0, anchor[1] + int(power_rule["y_min_offset"])),
            min(helper.GRID_SIZE - 1, anchor[1] + int(power_rule["y_max_offset"])) + 1,
        )
    }
    forbidden = fixed_body | backbone | protected
    components = helper.components(helper.GRID - forbidden)
    eligible_components = [
        component
        for component in components
        if component & {(x, y) for x in range(60, 70) for y in range(2, 36)}
        and any(
            any(adjacent in backbone for adjacent in helper.neighbours(cell))
            for cell in component
        )
    ]
    require(eligible_components, "no backbone-connected c5 body component")
    # Do not union split pieces. Pick the component containing the fixed c5
    # representative; y=2 was excluded from the phase order for this reason.
    c5 = next(component for component in eligible_components if (60, 2) in component)
    origin = (min(x for x, _y in c5), min(y for _x, y in c5))
    require(origin == (60, 2), f"c5 origin drift: {origin}")
    gateways = {
        cell
        for cell in c5
        if any(adjacent in backbone for adjacent in helper.neighbours(cell))
    }
    require(gateways, "c5 gateways")
    return {
        "backbone": backbone,
        "protected": protected,
        "fixed_body": fixed_body,
        "forbidden": forbidden,
        "power": power,
        "pole_anchors": pole_anchors,
        "pole_cells": pole_cells,
        "boundary": boundary,
        "core": core,
        "c5": c5,
        "origin": origin,
        "gateways": gateways,
        "c5_component_count": len(eligible_components),
    }


def c11_selected_still_legal(c11: Mapping[str, Any], fixed: Mapping[str, Any]) -> bool:
    origin = tuple(int(value) for value in c11["origin"])
    occupied = {
        (origin[0] + int(x), origin[1] + int(y))
        for row in c11["selected"]
        for x, y in row["body"]
    }
    return (
        not occupied & (set(fixed["fixed_body"]) | set(fixed["backbone"]) | set(fixed["protected"]))
        and all(body & set(fixed["power"]) for body in (
            {
                (origin[0] + int(x), origin[1] + int(y))
                for x, y in row["body"]
            }
            for row in c11["selected"]
        ))
    )


def main() -> int:
    for path, expected in EXPECTED.items():
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    write_exclusive(
        RUN / "stage_00_start.json",
        {
            "schema_version": "relocated_protected_c5_start.v1",
            "pid": os.getpid(),
            "target": list(TARGET),
            "phase_y": list(PHASE_Y),
            "seconds_per_phase": 240,
            "workers": 8,
            "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        },
    )
    helper = load_module("relocated_c5_helper", HELPER_SOURCE)
    candidate = json.loads(CANDIDATE.read_bytes())
    strict = json.loads(STRICT.read_bytes())
    hint = json.loads(HINT.read_bytes())
    c11 = json.loads(C11_RESULT.read_bytes())
    modes = helper.strict_modes(strict)
    attempts = []
    for attempt_index, protected_y in enumerate(PHASE_Y, start=1):
        fixed = build_fixed(helper, strict, protected_y)
        require(c11_selected_still_legal(c11, fixed), "c11 selected invalidated")
        poses, domain_counts = helper.build_domain(candidate, modes, fixed)
        result = helper.solve_phase(
            poses,
            TARGET,
            fixed,
            helper.hint_body_modes(hint, fixed["origin"]),
            240.0,
            8,
            20260800 + attempt_index,
        )
        result.update(
            {
                "attempt": attempt_index,
                "protected_rect": {"anchor": [60, protected_y], "width": 6, "height": 7},
                "protected_cells": [list(cell) for cell in sorted(fixed["protected"])],
                "all_35_pole_anchors": [list(cell) for cell in sorted(fixed["pole_anchors"])],
                "c5_origin": list(fixed["origin"]),
                "c5_body_component_count": fixed["c5_component_count"],
                "c11_selected_still_body_and_power_legal": True,
                "domain_counts": domain_counts,
            }
        )
        path = RUN / f"attempt_{attempt_index:02d}_protected_y{protected_y}_target_12_3_3.json"
        write_exclusive(path, result)
        attempts.append({"path": str(path), "sha256": sha256(path), **result})
        print(
            f"protected_y={protected_y} status={result['status']} "
            f"seconds={result['wall_time_seconds']:.3f}",
            flush=True,
        )
        if result["status"] in {"OPTIMAL", "FEASIBLE"}:
            break
        if result["status"] != "INFEASIBLE":
            break
    winner = next((row for row in attempts if row["status"] in {"OPTIMAL", "FEASIBLE"}), None)
    summary = {
        "schema_version": "relocated_protected_c5_search.v1",
        "status": "RELOCATED_PROTECTED_C5_FEASIBLE" if winner else "RELOCATED_PROTECTED_C5_NO_FEASIBLE_FOUND",
        "classification": "research_local_weak_active_terminal_search_no_router",
        "claim_boundary": (
            "Only the listed x=60 protected-rectangle phases and c5 target (12,3,3) are queried. "
            "A local feasible row still requires independent replay and global assembly. UNKNOWN gives no conclusion."
        ),
        "attempts": attempts,
        "winner_attempt": winner["attempt"] if winner else None,
    }
    write_exclusive(RUN / "summary.json", summary)
    return 0 if winner else 1


if __name__ == "__main__":
    raise SystemExit(main())
