#!/usr/bin/env python3
"""Exact weak-active c10 query after shifting only its two lower-edge poles."""

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
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
RUN = RECOVERY / "edge-c10-20260720T085403Z-ZoIzWc"
QUERY_SOURCE = RECOVERY / "scripts/query_terminal_parent_triples_root.py"
GEOMETRY_SOURCE = RECOVERY / "scripts/c5_pole_phase_search.py"
HINT = RECOVERY / "inputs/reduced_targeted_allocation_p7_36_final.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED = {
    QUERY_SOURCE: "b8d0ab3b771b4ce4cd77cf5edd8d036a560f9b2126c542a549ae7c8caaf7042f",
    GEOMETRY_SOURCE: "c7053f9ff3adc41f6d5519c2d76e45b663de2cc4c8b21c53959cf8acff666620",
    HINT: "6c51a1ee5bef15e555242896a0a11da24c8f18746a215db53c277deee537ee80",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
TARGET = (9, 2, 2)
REPRESENTATIVE = (60, 37)
TOP_MOVED_FROM = {(x, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
TOP_MOVED_TO = {(x + 1, y) for x, y in TOP_MOVED_FROM}
EDGE_MOVED_FROM = {(65, 41), (65, 53)}
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


def build_fixed(helper: Any, strict: Mapping[str, Any], edge_x: int) -> dict[str, Any]:
    core = helper.rect(helper.CORE_ANCHOR, 9, 9)
    backbone = (
        {(x, y) for x in helper.VERTICAL_LANES for y in range(1, helper.GRID_SIZE)}
        | {(x, y) for y in helper.HORIZONTAL_LANES for x in range(1, helper.GRID_SIZE)}
        | helper.ring(core)
    ) - core
    protected = helper.rect(
        (helper.PROTECTED[0], helper.PROTECTED[1]),
        helper.PROTECTED[2],
        helper.PROTECTED[3],
    )
    baseline = {
        (x, y) for x in helper.POLE_AXES for y in helper.POLE_AXES
    } - {(65, 65)}
    edge_to = {(edge_x, y) for _x, y in EDGE_MOVED_FROM}
    pole_anchors = (baseline - TOP_MOVED_FROM - EDGE_MOVED_FROM) | TOP_MOVED_TO | edge_to
    require(len(pole_anchors) == 35, "pole count/uniqueness")
    require(all(0 <= x <= 68 and 0 <= y <= 68 for x, y in pole_anchors), "pole body outside grid")
    pole_cells = set().union(*(helper.rect(anchor, 2, 2) for anchor in pole_anchors))
    require(len(pole_cells) == 140, "pole bodies overlap")
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
    component = next(
        cells for cells in helper.components(helper.GRID - forbidden) if REPRESENTATIVE in cells
    )
    origin = (min(x for x, _y in component), min(y for _x, y in component))
    require(origin == REPRESENTATIVE, f"c10 origin drift: {origin}")
    gateways = {
        cell
        for cell in component
        if any(adjacent in backbone for adjacent in helper.neighbours(cell))
    }
    require(gateways, "c10 has no gateway")
    return {
        "backbone": backbone,
        "protected": protected,
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


def hint_keys(raw_hint: Mapping[str, Any]) -> set[Any]:
    component = next(row for row in raw_hint["components"] if int(row["component"]) == 10)
    return {
        (
            str(raw["template"]),
            str(raw["mode"]),
            tuple(tuple(int(value) for value in cell) for cell in raw["body"]),
            tuple(tuple(int(value) for value in cell) for cell in raw["inputs"]),
            tuple(tuple(int(value) for value in cell) for cell in raw["outputs"]),
        )
        for raw in component["selected"]
    }


def run_attempt(helper: Any, query: Any, candidate: Any, strict: Any, hint: Any, edge_x: int) -> dict[str, Any]:
    fixed = build_fixed(helper, strict, edge_x)
    global_poses, domain_counts = helper.build_domain(candidate, helper.strict_modes(strict), fixed)
    origin = fixed["origin"]
    poses = tuple(localize_pose(helper, pose, origin) for pose in global_poses)
    component_local = {(x - origin[0], y - origin[1]) for x, y in fixed["c5"]}
    gateways_local = {(x - origin[0], y - origin[1]) for x, y in fixed["gateways"]}
    outside_main_local = {
        (x - origin[0], y - origin[1])
        for x, y in set(fixed["backbone"]) | set(fixed["protected"])
    }
    result = query.solve_exact(
        poses,
        TARGET,
        component_local,
        gateways_local,
        outside_main_local,
        240.0,
        8,
        20260720 + edge_x,
        hint_keys(hint),
    )
    result.update(
        {
            "component": 10,
            "origin": list(origin),
            "edge_x": edge_x,
            "moved_from": [list(cell) for cell in sorted(EDGE_MOVED_FROM)],
            "moved_to": [list(cell) for cell in sorted((edge_x, y) for _x, y in EDGE_MOVED_FROM)],
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
        ), "selected target drift")
    return result


def main() -> int:
    require(RUN.is_dir(), f"missing run directory: {RUN}")
    for path, expected in EXPECTED.items():
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    write_exclusive(
        RUN / "stage_00_start.json",
        {
            "schema_version": "c10_edge_shift_start.v1",
            "pid": os.getpid(),
            "target": list(TARGET),
            "phase_order": [66, 67],
            "seconds_per_phase": 240,
            "workers": 8,
            "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        },
    )
    helper = load_module("c10_edge_geometry", GEOMETRY_SOURCE)
    query = load_module("c10_edge_parent_query", QUERY_SOURCE)
    candidate = json.loads(CANDIDATE.read_bytes())
    strict = json.loads(STRICT.read_bytes())
    hint = json.loads(HINT.read_bytes())
    rows = []
    for attempt_index, edge_x in enumerate((66, 67), start=1):
        result = run_attempt(helper, query, candidate, strict, hint, edge_x)
        result["attempt"] = attempt_index
        attempt_path = RUN / f"attempt_{attempt_index:02d}_c10_x{edge_x}_target_9_2_2.json"
        write_exclusive(attempt_path, result)
        rows.append({"edge_x": edge_x, "path": str(attempt_path), "sha256": sha256(attempt_path), **result})
        print(
            f"component=10 edge_x={edge_x} status={result['status']} "
            f"seconds={result['wall_time_seconds']:.3f}",
            flush=True,
        )
        if result["status"] in {"OPTIMAL", "FEASIBLE"}:
            break
        if result["status"] != "INFEASIBLE":
            break
    summary = {
        "schema_version": "c10_edge_shift_query.v1",
        "status": (
            "C10_EDGE_SHIFT_FEASIBLE"
            if any(row["status"] in {"OPTIMAL", "FEASIBLE"} for row in rows)
            else "C10_EDGE_SHIFT_NO_FEASIBLE_FOUND"
        ),
        "classification": "research_local_weak_active_terminal_query_no_router",
        "claim_boundary": (
            "Only c10 target (9,2,2) is queried under the listed 35-pole geometries. "
            "INFEASIBLE is exact; UNKNOWN gives no conclusion. No global assembly or routing conclusion."
        ),
        "attempts": rows,
    }
    write_exclusive(RUN / "summary.json", summary)
    return 0 if summary["status"] == "C10_EDGE_SHIFT_FEASIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
