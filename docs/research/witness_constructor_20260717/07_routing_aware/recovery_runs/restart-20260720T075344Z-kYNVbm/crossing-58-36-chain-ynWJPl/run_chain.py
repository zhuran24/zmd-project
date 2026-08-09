#!/usr/bin/env python3
"""Exact c9 then c10 chain for protected rectangle anchor (58,36)."""

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
RUN = RECOVERY / "crossing-58-36-chain-ynWJPl"
OLD_RUNNER = RECOVERY / "crossing-57-36-chain-PTcifg/run_c9_c10_chain.py"
PREFLIGHT_SCRIPT = RUN / "independent_c4_c5_preflight.py"
PREFLIGHT_RESULT = RUN / "independent_c4_c5_preflight.json"
EXPECTED_WRAPPER_INPUTS = {
    OLD_RUNNER: "3ed254ae4c33b570aa49de063d3bacb13b2b73a7d66b09e91a786dfb0842f549",
    PREFLIGHT_SCRIPT: "TBD_PREFLIGHT_SCRIPT",
    PREFLIGHT_RESULT: "TBD_PREFLIGHT_RESULT",
}
ANCHOR = (58, 36)
QUERIES = (
    (9, (49, 37), (49, 37), (7, 3, 2), 5),
    (10, (64, 37), (60, 37), (7, 2, 2), 6),
)


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


def main() -> int:
    for path, expected in EXPECTED_WRAPPER_INPUTS.items():
        require(not expected.startswith("TBD_"), f"unfrozen input hash for {path}")
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    preflight = json.loads(PREFLIGHT_RESULT.read_bytes())
    require(
        preflight["status"] == "C4_C5_FINAL_GEOMETRY_PREFLIGHT_PASS",
        f"c4/c5 preflight rejected: {preflight.get('status')}",
    )
    old = load_module("crossing_58_36_old_runner", OLD_RUNNER)
    source_expected = {
        path: digest
        for path, digest in old.EXPECTED.items()
        if path not in {old.PREFLIGHT_SCRIPT, old.PREFLIGHT_RESULT}
    }
    for path, expected in source_expected.items():
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    write_exclusive(
        RUN / "stage_00_start.json",
        {
            "schema_version": "crossing_58_36_chain_start.v1",
            "pid": os.getpid(),
            "protected_rect": {"anchor": list(ANCHOR), "width": 6, "height": 7},
            "queries": [
                {"component": component, "target": list(target)}
                for component, _representative, _origin, target, _hint_index in QUERIES
            ],
            "seconds_per_query": 240,
            "workers": 8,
            "input_sha256": {
                **{str(path): digest for path, digest in source_expected.items()},
                **{str(path): digest for path, digest in EXPECTED_WRAPPER_INPUTS.items()},
            },
        },
    )
    crossing = old.load_module("crossing_58_36_geometry", old.CROSSING)
    helper = old.load_module("crossing_58_36_helper", old.HELPER_SOURCE)
    query = old.load_module("crossing_58_36_query", old.QUERY_SOURCE)
    candidate = json.loads(old.CANDIDATE.read_bytes())
    strict = json.loads(old.STRICT.read_bytes())
    hint = json.loads(old.HINT.read_bytes())
    c5_source = json.loads(old.C5_RESULT.read_bytes())
    c11_source = json.loads(old.C11_RESULT.read_bytes())
    fixed = crossing.build_fixed(helper, strict, ANCHOR)
    require(len(set(fixed["protected"]) & set(fixed["backbone"])) == 12, "backbone overlap")
    require(len(set(fixed["protected"]) - set(fixed["backbone"])) == 30, "new forbidden count")
    require(
        old.existing_local_body_clear(c5_source, c5_source["query"]["selected"], fixed),
        "c5 source collision",
    )
    c11_origin = tuple(c11_source["origin"])
    c11_global = [
        {**raw, "body": [[c11_origin[0] + x, c11_origin[1] + y] for x, y in raw["body"]]}
        for raw in c11_source["selected"]
    ]
    require(old.existing_local_body_clear(c11_source, c11_global, fixed), "c11 source collision")
    attempts = []
    for attempt_index, (
        component_id,
        representative,
        expected_origin,
        target,
        hint_index,
    ) in enumerate(QUERIES, start=1):
        local_fixed = old.component_fixed(helper, fixed, representative, expected_origin)
        global_poses, domain_counts = helper.build_domain(candidate, helper.strict_modes(strict), local_fixed)
        origin = local_fixed["origin"]
        poses = tuple(old.localize_pose(helper, pose, origin) for pose in global_poses)
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
            20261020 + attempt_index,
            old.hint_keys(hint, hint_index),
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
        "schema_version": "crossing_58_36_c9_c10_chain.v1",
        "status": "C9_C10_LOCAL_CHAIN_FEASIBLE" if ready else "C9_C10_LOCAL_CHAIN_NOT_CLOSED",
        "classification": "research_local_weak_active_terminal_chain_no_router",
        "claim_boundary": (
            "Only c9/c10 local targets are classified under anchor (58,36). Existing c4/c5 and c11 "
            "rows are independently preflighted or collision-gated but require final combined replay. "
            "UNKNOWN gives no conclusion."
        ),
        "attempts": attempts,
    }
    write_exclusive(RUN / "summary.json", summary)
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
