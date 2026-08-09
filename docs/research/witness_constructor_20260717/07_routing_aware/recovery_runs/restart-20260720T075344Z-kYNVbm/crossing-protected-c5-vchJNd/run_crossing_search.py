#!/usr/bin/env python3
"""Search c5 with a 6x7 protected rectangle crossing lanes x=59/y=36."""

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
RUN = RECOVERY / "crossing-protected-c5-vchJNd"
BASE_RUNNER = RECOVERY / "relocated-protected-c5-aeSpkH/run_relocated_protected_c5.py"
HELPER_SOURCE = RECOVERY / "scripts/c5_pole_phase_search.py"
HINT = RECOVERY / "inputs/reduced_targeted_allocation_p7_36_final.json"
C11_RESULT = RECOVERY / "c11-protected-relocation-probe-EYLj1q/result.json"
C11_REPLAY = RECOVERY / "c11-protected-relocation-probe-EYLj1q/independent_replay.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED = {
    BASE_RUNNER: "0aa252a428df19fb75861c1d58213a79d64d4c21178e7aa077f41e05368d8741",
    HELPER_SOURCE: "c7053f9ff3adc41f6d5519c2d76e45b663de2cc4c8b21c53959cf8acff666620",
    HINT: "6c51a1ee5bef15e555242896a0a11da24c8f18746a215db53c277deee537ee80",
    C11_RESULT: "7777f458f4b6856f7fde55d7a923c32c691cac1d0a1363e707905de05766a230",
    C11_REPLAY: "acebbd65fc88638a2dea8c8d2ca8d584e34f9116fc8e72f17e1da3b8a2e2845c",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
TARGET = (12, 3, 3)
TOP_FROM = {(x, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
TOP_TO = {(x + 1, y) for x, y in TOP_FROM}
ANCHORS = tuple((x, y) for x in (57, 58, 59) for y in range(30, 37))
Cell = tuple[int, int]


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


def build_fixed(helper: Any, strict: Mapping[str, Any], anchor: Cell) -> dict[str, Any]:
    core = helper.rect(helper.CORE_ANCHOR, 9, 9)
    backbone = (
        {(x, y) for x in helper.VERTICAL_LANES for y in range(1, helper.GRID_SIZE)}
        | {(x, y) for y in helper.HORIZONTAL_LANES for x in range(1, helper.GRID_SIZE)}
        | helper.ring(core)
    ) - core
    protected = helper.rect(anchor, 6, 7)
    require(len(protected) == 42 and (59, 36) in protected, "protected crossing geometry")
    baseline = {
        (x, y) for x in helper.POLE_AXES for y in helper.POLE_AXES
    } - {(65, 65)}
    pole_anchors = (baseline - TOP_FROM) | TOP_TO
    require(len(pole_anchors) == 35, "pole count/uniqueness")
    pole_cells = set().union(*(helper.rect(pole, 2, 2) for pole in pole_anchors))
    require(len(pole_cells) == 140, "pole body overlap")
    left = helper.boundary_anchors(69)
    bottom = helper.boundary_anchors(0)
    boundary = (
        {(0, y) for start in left for y in range(start, start + 3)}
        | {(x, 0) for start in bottom for x in range(start, start + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(not protected & fixed_body, "protected/mandatory-or-aux-body collision")
    require(not pole_cells & (core | boundary | backbone), "pole/fixed collision")
    power_rule = strict["power"]["coverage_from_pole_anchor"]
    power = {
        (x, y)
        for pole in pole_anchors
        for x in range(max(0, pole[0] + int(power_rule["x_min_offset"])), min(69, pole[0] + int(power_rule["x_max_offset"])) + 1)
        for y in range(max(0, pole[1] + int(power_rule["y_min_offset"])), min(69, pole[1] + int(power_rule["y_max_offset"])) + 1)
    }
    forbidden = fixed_body | backbone | protected
    all_components = helper.components(helper.GRID - forbidden)
    c5 = next(component for component in all_components if (60, 2) in component)
    origin = (min(x for x, _y in c5), min(y for _x, y in c5))
    require(origin == (60, 2), f"c5 origin drift: {origin}")
    gateways = {
        cell
        for cell in c5
        if any(adjacent in backbone for adjacent in helper.neighbours(cell))
    }
    require(gateways, "c5 gateway")
    protected_main = helper.reachable(set(protected) & backbone, protected | backbone)
    require(protected <= protected_main, "protected rectangle is not in route-main union")
    return {
        "backbone": backbone,
        "protected": protected,
        "fixed_body": fixed_body,
        "forbidden": forbidden,
        "power": power,
        "pole_anchors": pole_anchors,
        "pole_cells": pole_cells,
        "core": core,
        "boundary": boundary,
        "c5": c5,
        "origin": origin,
        "gateways": gateways,
    }


def quadrant_losses(protected: set[Cell], backbone: set[Cell]) -> dict[str, int]:
    new = protected - backbone
    return {
        "upper_left": sum(x < 59 and y < 36 for x, y in new),
        "upper_right": sum(x > 59 and y < 36 for x, y in new),
        "lower_left": sum(x < 59 and y > 36 for x, y in new),
        "lower_right": sum(x > 59 and y > 36 for x, y in new),
    }


def main() -> int:
    for path, expected in EXPECTED.items():
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    write_exclusive(
        RUN / "stage_00_start.json",
        {
            "schema_version": "crossing_protected_c5_start.v1",
            "pid": os.getpid(),
            "candidate_anchors": [list(anchor) for anchor in ANCHORS],
            "target": list(TARGET),
            "seconds_per_phase": 240,
            "workers": 8,
            "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        },
    )
    base = load_module("crossing_protected_base", BASE_RUNNER)
    helper = load_module("crossing_protected_helper", HELPER_SOURCE)
    candidate = json.loads(CANDIDATE.read_bytes())
    strict = json.loads(STRICT.read_bytes())
    hint = json.loads(HINT.read_bytes())
    c11 = json.loads(C11_RESULT.read_bytes())
    modes = helper.strict_modes(strict)
    static_rows = []
    cached: dict[Cell, tuple[dict[str, Any], tuple[Any, ...], dict[str, int]]] = {}
    for anchor in ANCHORS:
        fixed = build_fixed(helper, strict, anchor)
        require(base.c11_selected_still_legal(c11, fixed), f"c11 selected invalidated by {anchor}")
        poses, domain_counts = helper.build_domain(candidate, modes, fixed)
        losses = quadrant_losses(set(fixed["protected"]), set(fixed["backbone"]))
        row = {
            "anchor": list(anchor),
            "protected_cells": 42,
            "backbone_overlap_cells": len(set(fixed["protected"]) & set(fixed["backbone"])),
            "new_body_forbidden_cells": len(set(fixed["protected"]) - set(fixed["backbone"])),
            "quadrant_new_forbidden": losses,
            "max_quadrant_new_forbidden": max(losses.values()),
            "c5_component_cells": len(fixed["c5"]),
            "c5_gateway_cells": len(fixed["gateways"]),
            "c5_pose_modes": domain_counts["pose_modes"],
            "domain_counts": domain_counts,
            "c11_selected_still_body_and_power_legal": True,
        }
        static_rows.append(row)
        cached[anchor] = (fixed, poses, domain_counts)
    static_rows.sort(
        key=lambda row: (
            0 if row["anchor"] == [57, 33] else 1,
            row["max_quadrant_new_forbidden"],
            -row["c5_pose_modes"],
            row["anchor"],
        )
    )
    write_exclusive(
        RUN / "static_ranking.json",
        {
            "schema_version": "crossing_protected_static_ranking.v1",
            "status": "STATIC_ENUMERATION_ACCEPTED",
            "ranking_policy": "suggested_57_33_first_then_minimax_quadrant_loss_then_c5_pose_capacity",
            "claim_boundary": "No CP status is inferred from static capacity ranking.",
            "rows": static_rows,
        },
    )
    attempts = []
    for attempt_index, static in enumerate(static_rows, start=1):
        anchor = tuple(static["anchor"])
        fixed, poses, _domain_counts = cached[anchor]
        result = helper.solve_phase(
            poses,
            TARGET,
            fixed,
            helper.hint_body_modes(hint, fixed["origin"]),
            240.0,
            8,
            20260900 + attempt_index,
        )
        result.update(
            {
                "attempt": attempt_index,
                "protected_rect": {"anchor": list(anchor), "width": 6, "height": 7},
                "protected_cells": [list(cell) for cell in sorted(fixed["protected"])],
                "all_35_pole_anchors": [list(cell) for cell in sorted(fixed["pole_anchors"])],
                "backbone_overlap_cells": static["backbone_overlap_cells"],
                "new_body_forbidden_cells": static["new_body_forbidden_cells"],
                "quadrant_new_forbidden": static["quadrant_new_forbidden"],
                "c11_selected_still_body_and_power_legal": True,
                "domain_counts": static["domain_counts"],
            }
        )
        path = RUN / f"attempt_{attempt_index:02d}_anchor_{anchor[0]}_{anchor[1]}.json"
        write_exclusive(path, result)
        attempts.append({"path": str(path), "sha256": sha256(path), **result})
        print(f"anchor={anchor} status={result['status']} seconds={result['wall_time_seconds']:.3f}", flush=True)
        if result["status"] in {"OPTIMAL", "FEASIBLE"}:
            bundle = {
                "schema_version": "routing_geometry_bundle.v1",
                "status": "LOCAL_C5_AND_C11_PACKINGS_AVAILABLE",
                "claim_boundary": (
                    "Pins auxiliary geometry and two independently replayable local packings only. "
                    "Other bay packings and global routing remain unvalidated."
                ),
                "baseline_head": "ea407fafaff56333bcf18066cecf890f0ef0c6da",
                "all_35_pole_anchors": result["all_35_pole_anchors"],
                "protected_rect": result["protected_rect"],
                "protected_cells": result["protected_cells"],
                "protected_backbone_overlap_cells": result["backbone_overlap_cells"],
                "protected_new_body_forbidden_cells": result["new_body_forbidden_cells"],
                "fixed_semantics": {
                    "grid_size": 70,
                    "vertical_backbone_lanes": list(helper.VERTICAL_LANES),
                    "horizontal_backbone_lanes": list(helper.HORIZONTAL_LANES),
                    "core_anchor": list(helper.CORE_ANCHOR),
                    "core_size": [9, 9],
                    "boundary_left_and_bottom": True,
                    "protected_may_overlap_backbone": True,
                    "protected_may_not_overlap_facility_or_aux_body": True,
                },
                "c5_result_path": str(path),
                "c5_result_sha256": sha256(path),
                "c11_result_path": str(C11_RESULT),
                "c11_result_sha256": EXPECTED[C11_RESULT],
                "c11_independent_replay_path": str(C11_REPLAY),
                "c11_independent_replay_sha256": EXPECTED[C11_REPLAY],
            }
            write_exclusive(RUN / "geometry_bundle.json", bundle)
            break
        if result["status"] != "INFEASIBLE":
            break
    winner = next((row for row in attempts if row["status"] in {"OPTIMAL", "FEASIBLE"}), None)
    summary = {
        "schema_version": "crossing_protected_c5_search.v1",
        "status": "CROSSING_PROTECTED_C5_FEASIBLE" if winner else "CROSSING_PROTECTED_C5_NO_FEASIBLE_FOUND",
        "classification": "research_local_weak_active_terminal_search_no_router",
        "claim_boundary": (
            "Only attempted crossing-protected geometries and c5 target (12,3,3) are classified. "
            "A local winner still requires independent replay and global assembly. UNKNOWN gives no conclusion."
        ),
        "static_ranking_sha256": sha256(RUN / "static_ranking.json"),
        "attempts": attempts,
        "winner_attempt": winner["attempt"] if winner else None,
    }
    write_exclusive(RUN / "summary.json", summary)
    return 0 if winner else 1


if __name__ == "__main__":
    raise SystemExit(main())
