#!/usr/bin/env python3
"""Exact c9 then c10 chain for protected rectangle anchor (57,36)."""

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
RUN = RECOVERY / "crossing-57-36-chain-PTcifg"
CROSSING = RECOVERY / "crossing-protected-c5-vchJNd/run_crossing_search.py"
QUERY_SOURCE = RECOVERY / "scripts/query_terminal_parent_triples_root.py"
HELPER_SOURCE = RECOVERY / "scripts/c5_pole_phase_search.py"
HINT = RECOVERY / "fixed_bays/recovered_fast_bays_20260720.json"
C5_RESULT = RECOVERY / "c5/c5_direct_winner_query.json"
C5_REPLAY = RECOVERY / "c5/independent_c5_direct_winner_replay_v2.json"
C11_RESULT = RECOVERY / "c11-protected-relocation-probe-EYLj1q/result.json"
C11_REPLAY = RECOVERY / "c11-protected-relocation-probe-EYLj1q/independent_replay.json"
PREFLIGHT_SCRIPT = RUN / "independent_c4_c5_preflight.py"
PREFLIGHT_RESULT = RUN / "independent_c4_c5_preflight.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED = {
    CROSSING: "e417106b7753376312470a1203e15312badf2ba9551d81d3e466519a5860861d",
    QUERY_SOURCE: "b8d0ab3b771b4ce4cd77cf5edd8d036a560f9b2126c542a549ae7c8caaf7042f",
    HELPER_SOURCE: "c7053f9ff3adc41f6d5519c2d76e45b663de2cc4c8b21c53959cf8acff666620",
    HINT: "2f82e1bcec5012b892da1f9362245a3bfd5aa6af4a996fdfb01f367ec76b2a16",
    C5_RESULT: "3f1e2641e748bc7c6f2d5ad6aaf45adca3d4d15cb31d368439cc27480fb90c66",
    C5_REPLAY: "e062e5af4ad6063f099e7282cf2bf015212c16a3c7b998960bb364220642ef35",
    C11_RESULT: "7777f458f4b6856f7fde55d7a923c32c691cac1d0a1363e707905de05766a230",
    C11_REPLAY: "acebbd65fc88638a2dea8c8d2ca8d584e34f9116fc8e72f17e1da3b8a2e2845c",
    PREFLIGHT_SCRIPT: "3a2ffa8bbad6d82364690da17f744d33aca13ffeea7ee098dab45a71c5b76285",
    PREFLIGHT_RESULT: "c17cdfa628149803cfdfa5936f28a894190bd0a6b05985199a6f058b64a2462c",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
ANCHOR = (57, 36)
QUERIES = (
    (9, (49, 37), (49, 37), (7, 3, 2), 5),
    # (60,37) is inside the relocated rectangle.  (63,37) identifies the
    # remaining c10 body component; its coordinatewise local origin stays
    # (60,37) because lower rows still contain x=60 cells.
    (10, (63, 37), (60, 37), (7, 2, 2), 6),
)
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


def hint_keys(hint: Mapping[str, Any], query_index: int) -> set[Any]:
    row = hint["queries"][query_index]
    require(row["status"] == "OPTIMAL", f"hint query {query_index} status")
    return {
        (
            str(raw["template"]),
            str(raw["mode"]),
            tuple(tuple(cell) for cell in raw["body"]),
            tuple(tuple(cell) for cell in raw["inputs"]),
            tuple(tuple(cell) for cell in raw["outputs"]),
        )
        for raw in row["selected"]
    }


def component_fixed(
    helper: Any,
    fixed: Mapping[str, Any],
    representative: Cell,
    expected_origin: Cell,
) -> dict[str, Any]:
    components = helper.components(helper.GRID - set(fixed["forbidden"]))
    component = next(cells for cells in components if representative in cells)
    origin = (min(x for x, _y in component), min(y for _x, y in component))
    require(origin == expected_origin, f"component origin drift: {origin} != {expected_origin}")
    gateways = {
        cell
        for cell in component
        if any(adjacent in fixed["backbone"] for adjacent in helper.neighbours(cell))
    }
    require(gateways, f"component {representative} gateways")
    result = dict(fixed)
    result.update({"c5": component, "origin": origin, "gateways": gateways})
    return result


def existing_local_body_clear(source: Mapping[str, Any], selected: list[Mapping[str, Any]], fixed: Mapping[str, Any]) -> bool:
    occupied = {
        tuple(cell)
        for raw in selected
        for cell in raw["body"]
    }
    return not occupied & (set(fixed["protected"]) | set(fixed["fixed_body"]) | set(fixed["backbone"]))


def main() -> int:
    for path, expected in EXPECTED.items():
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    preflight = json.loads(PREFLIGHT_RESULT.read_bytes())
    require(
        preflight["status"] == "C4_C5_FINAL_GEOMETRY_PREFLIGHT_PASS",
        f"c4/c5 preflight rejected: {preflight.get('status')}",
    )
    write_exclusive(
        RUN / "stage_00_start.json",
        {
            "schema_version": "crossing_57_36_chain_start.v1",
            "pid": os.getpid(),
            "protected_rect": {"anchor": list(ANCHOR), "width": 6, "height": 7},
            "queries": [
                {"component": component, "target": list(target)}
                for component, _representative, _expected_origin, target, _hint_index in QUERIES
            ],
            "seconds_per_query": 240,
            "workers": 8,
            "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        },
    )
    crossing = load_module("crossing_57_36_geometry", CROSSING)
    helper = load_module("crossing_57_36_helper", HELPER_SOURCE)
    query = load_module("crossing_57_36_query", QUERY_SOURCE)
    candidate = json.loads(CANDIDATE.read_bytes())
    strict = json.loads(STRICT.read_bytes())
    hint = json.loads(HINT.read_bytes())
    c5_source = json.loads(C5_RESULT.read_bytes())
    c11_source = json.loads(C11_RESULT.read_bytes())
    fixed = crossing.build_fixed(helper, strict, ANCHOR)
    require(len(set(fixed["protected"]) & set(fixed["backbone"])) == 12, "backbone overlap")
    require(len(set(fixed["protected"]) - set(fixed["backbone"])) == 30, "new forbidden count")
    require(existing_local_body_clear(c5_source, c5_source["query"]["selected"], fixed), "c5 source collision")
    c11_origin = tuple(c11_source["origin"])
    c11_global = [
        {**raw, "body": [[c11_origin[0] + x, c11_origin[1] + y] for x, y in raw["body"]]}
        for raw in c11_source["selected"]
    ]
    require(existing_local_body_clear(c11_source, c11_global, fixed), "c11 source collision")
    attempts = []
    for attempt_index, (
        component_id,
        representative,
        expected_origin,
        target,
        hint_index,
    ) in enumerate(QUERIES, start=1):
        local_fixed = component_fixed(helper, fixed, representative, expected_origin)
        global_poses, domain_counts = helper.build_domain(candidate, helper.strict_modes(strict), local_fixed)
        origin = local_fixed["origin"]
        poses = tuple(localize_pose(helper, pose, origin) for pose in global_poses)
        component_local = {(x - origin[0], y - origin[1]) for x, y in local_fixed["c5"]}
        gateways_local = {(x - origin[0], y - origin[1]) for x, y in local_fixed["gateways"]}
        outside_main_local = {
            (x - origin[0], y - origin[1])
            for x, y in set(fixed["backbone"]) | set(fixed["protected"])
        }
        result = query.solve_exact(
            poses,
            target,
            component_local,
            gateways_local,
            outside_main_local,
            240.0,
            8,
            20261000 + attempt_index,
            hint_keys(hint, hint_index),
        )
        result.update(
            {
                "attempt": attempt_index,
                "component": component_id,
                "origin": list(origin),
                "protected_rect": {"anchor": list(ANCHOR), "width": 6, "height": 7},
                "protected_cells": [list(cell) for cell in sorted(fixed["protected"])],
                "all_35_pole_anchors": [list(cell) for cell in sorted(fixed["pole_anchors"])],
                "domain_counts": domain_counts,
            }
        )
        path = RUN / f"attempt_{attempt_index:02d}_c{component_id}.json"
        write_exclusive(path, result)
        attempts.append({"path": str(path), "sha256": sha256(path), **result})
        print(
            f"component={component_id} status={result['status']} seconds={result['wall_time_seconds']:.3f}",
            flush=True,
        )
        if result["status"] not in {"OPTIMAL", "FEASIBLE"}:
            break
    ready = len(attempts) == 2 and all(row["status"] in {"OPTIMAL", "FEASIBLE"} for row in attempts)
    summary = {
        "schema_version": "crossing_57_36_c9_c10_chain.v1",
        "status": "C9_C10_LOCAL_CHAIN_FEASIBLE" if ready else "C9_C10_LOCAL_CHAIN_NOT_CLOSED",
        "classification": "research_local_weak_active_terminal_chain_no_router",
        "claim_boundary": (
            "Only c9/c10 local targets are classified under anchor (57,36). Existing c4/c5 and c11 "
            "rows are collision-gated but require final independent replay. UNKNOWN gives no conclusion."
        ),
        "attempts": attempts,
    }
    write_exclusive(RUN / "summary.json", summary)
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
