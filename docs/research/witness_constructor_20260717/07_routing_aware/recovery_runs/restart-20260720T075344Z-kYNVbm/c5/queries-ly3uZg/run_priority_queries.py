#!/usr/bin/env python3
"""Run the ordered c5 custom-pole closure queries and persist every attempt.

This recovery-only driver imports the colocated geometry helper, constructs the
x=66, dy=0 fixed geometry and candidate domain once, then solves the requested
targets serially.  It never imports or launches the production router.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Sequence


RUN = Path(__file__).resolve().parent
HELPER = RUN / "c5_pole_phase_search.py"
SUMMARY = RUN / "priority_query_summary.json"
TARGETS = (
    (9, 5, 4),
    (12, 5, 3),
    (11, 4, 4),
    (11, 5, 3),
    (10, 5, 4),
)


class DriverError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DriverError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_helper() -> Any:
    spec = importlib.util.spec_from_file_location("persisted_c5_phase_helper", HELPER)
    require(spec is not None and spec.loader is not None, "helper import spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds-per-query", type=float, default=180.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    require(120.0 <= args.seconds_per_query <= 300.0, "seconds-per-query must be in [120, 300]")
    require(args.workers == 8, "this recovery run is pinned to 8 workers")
    require(not SUMMARY.exists(), f"refusing overwrite: {SUMMARY}")

    helper = load_helper()
    candidate = helper.load_pinned(helper.CANDIDATE_PATH)
    strict = helper.load_pinned(helper.STRICT_PATH)
    old = helper.load_pinned(helper.HINT_PATH)
    modes = helper.strict_modes(strict)
    fixed = helper.fixed_geometry(strict, 66, 0)
    poses, domain_counts = helper.build_domain(candidate, modes, fixed)
    hints = helper.hint_body_modes(old, fixed["origin"])
    moved = [[66, 5], [66, 17], [66, 29]]
    pole_anchors = [
        list(anchor)
        for anchor in sorted(fixed["pole_anchors"], key=lambda cell: (cell[1], cell[0]))
    ]

    attempts = []
    winner = None
    for attempt_index, target in enumerate(TARGETS, start=1):
        attempt_path = RUN / (
            f"attempt_{attempt_index:02d}_target_{target[0]}_{target[1]}_{target[2]}.json"
        )
        require(not attempt_path.exists(), f"refusing overwrite: {attempt_path}")
        result = helper.solve_phase(
            poses,
            target,
            fixed,
            hints,
            args.seconds_per_query,
            args.workers,
            20260720 + attempt_index,
        )
        result.update(
            {
                "attempt": attempt_index,
                "moved_x": 66,
                "uniform_y_shift": 0,
                "moved_pole_anchors": moved,
                "all_35_pole_anchors": pole_anchors,
                "c5_origin": list(fixed["origin"]),
                "domain_counts": domain_counts,
            }
        )
        record = {
            "schema_version": "c5_priority_query_attempt.v1",
            "classification": "research_local_custom_pole_query_no_router",
            "claim_boundary": (
                "Single c5 optional terminal-parent query under custom poles x=66, dy=0; "
                "no production router is built or solved."
            ),
            "helper": {"path": str(HELPER), "sha256": sha256(HELPER)},
            "inputs": {str(path): digest for path, digest in helper.EXPECTED.items()},
            "query": result,
        }
        write_json_exclusive(attempt_path, record)
        attempt_row = {
            "attempt": attempt_index,
            "target": list(target),
            "status": result["status"],
            "wall_time_seconds": result["wall_time_seconds"],
            "path": str(attempt_path),
            "sha256": sha256(attempt_path),
        }
        attempts.append(attempt_row)
        print(json.dumps(attempt_row, sort_keys=True), flush=True)
        if result["status"] in {"OPTIMAL", "FEASIBLE"}:
            winner = attempt_row
            break

    attempted_targets = {tuple(row["target"]) for row in attempts}
    summary = {
        "schema_version": "c5_priority_query_summary.v1",
        "status": "FIRST_FEASIBLE_FOUND" if winner is not None else "NO_FEASIBLE_FOUND_WITHIN_LIMITS",
        "classification": "research_serial_custom_pole_queries_no_router",
        "claim_boundary": (
            "Ordered c5 target queries with one shared x=66, dy=0 geometry/domain, "
            "8 workers and a per-query time limit. UNKNOWN gives no infeasibility conclusion."
        ),
        "driver": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "helper": {"path": str(HELPER), "sha256": sha256(HELPER)},
        "inputs": {str(path): digest for path, digest in helper.EXPECTED.items()},
        "seconds_per_query": args.seconds_per_query,
        "workers": args.workers,
        "fixed_geometry": {
            "moved_x": 66,
            "uniform_y_shift": 0,
            "moved_pole_anchors": moved,
            "all_35_pole_anchors": pole_anchors,
            "domain_counts": domain_counts,
        },
        "ordered_targets": [list(target) for target in TARGETS],
        "attempts": attempts,
        "unattempted": [
            {"target": list(target), "status": "NOT_RUN_AFTER_FIRST_FEASIBLE"}
            for target in TARGETS
            if target not in attempted_targets
        ],
        "winner": winner,
    }
    write_json_exclusive(SUMMARY, summary)
    print(json.dumps({"summary": str(SUMMARY), "status": summary["status"]}, sort_keys=True), flush=True)
    return 0 if winner is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
