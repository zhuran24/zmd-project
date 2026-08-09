#!/usr/bin/env python3
"""Probe c11 after locally removing the current protected-box obstacle."""

from __future__ import annotations

from collections import Counter
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
RUN = RECOVERY / "c11-protected-relocation-probe-EYLj1q"
QUERY_SOURCE = RECOVERY / "scripts/query_terminal_parent_triples_root.py"
HELPER_SOURCE = RECOVERY / "scripts/c5_pole_phase_search.py"
HINT = RECOVERY / "inputs/reduced_targeted_allocation_p7_36_final.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED = {
    QUERY_SOURCE: "b8d0ab3b771b4ce4cd77cf5edd8d036a560f9b2126c542a549ae7c8caaf7042f",
    HELPER_SOURCE: "c7053f9ff3adc41f6d5519c2d76e45b663de2cc4c8b21c53959cf8acff666620",
    HINT: "6c51a1ee5bef15e555242896a0a11da24c8f18746a215db53c277deee537ee80",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
TARGET = (9, 1, 2)
REPRESENTATIVE = (2, 37)
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


def build_fixed(helper: Any, strict: Mapping[str, Any]) -> dict[str, Any]:
    core = helper.rect(helper.CORE_ANCHOR, 9, 9)
    backbone = (
        {(x, y) for x in helper.VERTICAL_LANES for y in range(1, helper.GRID_SIZE)}
        | {(x, y) for y in helper.HORIZONTAL_LANES for x in range(1, helper.GRID_SIZE)}
        | helper.ring(core)
    ) - core
    removed_protected = helper.rect(
        (helper.PROTECTED[0], helper.PROTECTED[1]),
        helper.PROTECTED[2],
        helper.PROTECTED[3],
    )
    pole_anchors = {
        (x, y) for x in helper.POLE_AXES for y in helper.POLE_AXES
    } - {(65, 65)}
    pole_cells = set().union(*(helper.rect(anchor, 2, 2) for anchor in pole_anchors))
    require(len(pole_anchors) == 35 and len(pole_cells) == 140, "baseline pole geometry")
    left_anchors = helper.boundary_anchors(69)
    bottom_anchors = helper.boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left_anchors for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom_anchors for x in range(anchor, anchor + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(not fixed_body & backbone, "fixed/backbone collision")
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
    forbidden = fixed_body | backbone
    component = next(
        cells for cells in helper.components(helper.GRID - forbidden) if REPRESENTATIVE in cells
    )
    origin = (min(x for x, _y in component), min(y for _x, y in component))
    require(origin == REPRESENTATIVE, f"c11 origin drift: {origin}")
    gateways = {
        cell
        for cell in component
        if any(adjacent in backbone for adjacent in helper.neighbours(cell))
    }
    require(gateways, "c11 gateways")
    return {
        "backbone": backbone,
        "protected": set(),
        "removed_protected": removed_protected,
        "fixed_body": fixed_body,
        "forbidden": forbidden,
        "power": power,
        "pole_anchors": pole_anchors,
        "c5": component,
        "origin": origin,
        "gateways": gateways,
    }


def localize_pose(helper: Any, pose: Any, origin: Cell) -> Any:
    ox, oy = origin
    body = frozenset((x - ox, y - oy) for x, y in pose.body)
    inputs = tuple(sorted((x - ox, y - oy) for x, y in pose.inputs))
    outputs = tuple(sorted((x - ox, y - oy) for x, y in pose.outputs))
    key = (pose.template, pose.mode, tuple(sorted(body)), inputs, outputs)
    return helper.LocalPose(
        key=key,
        template=pose.template,
        mode=pose.mode,
        pose_index=pose.pose_index,
        anchor=(pose.anchor[0] - ox, pose.anchor[1] - oy),
        body=body,
        inputs=inputs,
        outputs=outputs,
    )


def baseline_hint_keys(raw_hint: Mapping[str, Any]) -> set[Any]:
    component = next(row for row in raw_hint["components"] if int(row["component"]) == 11)
    return {
        (
            str(raw["template"]),
            str(raw["mode"]),
            tuple(tuple(cell) for cell in raw["body"]),
            tuple(tuple(cell) for cell in raw["inputs"]),
            tuple(tuple(cell) for cell in raw["outputs"]),
        )
        for raw in component["selected"]
    }


def main() -> int:
    for path, expected in EXPECTED.items():
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    write_exclusive(
        RUN / "stage_00_start.json",
        {
            "schema_version": "c11_protected_relocation_probe_start.v1",
            "pid": os.getpid(),
            "target": list(TARGET),
            "seconds": 240,
            "workers": 8,
            "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        },
    )
    helper = load_module("c11_probe_helper", HELPER_SOURCE)
    query = load_module("c11_probe_query", QUERY_SOURCE)
    candidate = json.loads(CANDIDATE.read_bytes())
    strict = json.loads(STRICT.read_bytes())
    hint = json.loads(HINT.read_bytes())
    fixed = build_fixed(helper, strict)
    poses_global, domain_counts = helper.build_domain(candidate, helper.strict_modes(strict), fixed)
    origin = fixed["origin"]
    poses = tuple(localize_pose(helper, pose, origin) for pose in poses_global)
    component_local = {(x - origin[0], y - origin[1]) for x, y in fixed["c5"]}
    gateways_local = {(x - origin[0], y - origin[1]) for x, y in fixed["gateways"]}
    outside_main_local = {
        (x - origin[0], y - origin[1]) for x, y in fixed["backbone"]
    }
    result = query.solve_exact(
        poses,
        TARGET,
        component_local,
        gateways_local,
        outside_main_local,
        240.0,
        8,
        20260731,
        baseline_hint_keys(hint),
    )
    result.update(
        {
            "component": 11,
            "origin": list(origin),
            "removed_protected_cells": [list(cell) for cell in sorted(fixed["removed_protected"])],
            "replacement_protected_location": None,
            "all_35_pole_anchors": [list(cell) for cell in sorted(fixed["pole_anchors"])],
            "domain_counts": domain_counts,
        }
    )
    if result["status"] in {"OPTIMAL", "FEASIBLE"}:
        require(Counter(row["template"] for row in result["selected"]) == Counter(
            {
                "manufacturing_3x3": TARGET[0],
                "manufacturing_5x5": TARGET[1],
                "manufacturing_6x4": TARGET[2],
            }
        ), "target drift")
    write_exclusive(RUN / "result.json", result)
    summary = {
        "schema_version": "c11_protected_relocation_probe.v1",
        "status": result["status"],
        "classification": "research_local_geometry_probe_no_router",
        "claim_boundary": (
            "The current protected 6x7 obstacle is removed only from this local c11 query. "
            "No legal global replacement has been selected, so FEASIBLE would justify further "
            "relocation search but would not be an assemblable global layout. INFEASIBLE is only "
            "for this local geometry; UNKNOWN gives no conclusion."
        ),
        "result_path": str(RUN / "result.json"),
        "result_sha256": sha256(RUN / "result.json"),
    }
    write_exclusive(RUN / "summary.json", summary)
    print(f"component=11 status={result['status']} seconds={result['wall_time_seconds']:.3f}", flush=True)
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
