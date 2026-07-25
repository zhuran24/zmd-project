#!/usr/bin/env python3
"""Summarize no-overwrite baseline/x64 c5 supplemental attempts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_baseline_target_10_4_4.py"
SUMMARY = HERE / "supplement_baseline_phase_summary.json"
SUMS = HERE / "SHA256SUMS.supplement-baseline-phase"
ATTEMPTS = (
    (HERE / "attempt_12_x65_dyp0_target_10_4_4.json", 12, 65),
    (HERE / "attempt_13_x64_dyp0_target_10_4_4.json", 13, 64),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_poles(moved_x: int) -> set[tuple[int, int]]:
    axes = (5, 17, 29, 41, 53, 65)
    baseline = {(x, y) for x in axes for y in axes} - {(65, 65)}
    big_from = {(x, y) for x in (17, 29, 41) for y in (5, 17, 29)}
    big_to = {(x + 1, y) for x in (17, 29, 41) for y in (5, 17, 29)}
    c5_from = {(65, y) for y in (5, 17, 29)}
    c5_to = {(moved_x, y) for y in (5, 17, 29)}
    return (baseline - big_from - c5_from) | big_to | c5_to


def write_exclusive(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def main() -> int:
    if SUMMARY.exists() or SUMS.exists():
        raise RuntimeError("refusing overwrite")
    rows = []
    for path, attempt, moved_x in ATTEMPTS:
        record = json.loads(path.read_bytes())
        if record["attempt"] != attempt or record["target"] != [10, 4, 4]:
            raise RuntimeError(f"identity drift: {path}")
        if record["phase"] != {"moved_x": moved_x, "uniform_y_shift": 0}:
            raise RuntimeError(f"phase drift: {path}")
        if record["result"]["status"] != "INFEASIBLE":
            raise RuntimeError(f"non-terminal status: {path}")
        if record["static_capacity"]["component_cells"] != 328:
            raise RuntimeError(f"component drift: {path}")
        if {tuple(cell) for cell in record["final_35_pole_anchors"]} != expected_poles(moved_x):
            raise RuntimeError(f"pole drift: {path}")
        rows.append(
            {
                "path": str(path),
                "sha256": sha256(path),
                "attempt": attempt,
                "phase": record["phase"],
                "target": [10, 4, 4],
                "status": "INFEASIBLE",
                "wall_time_seconds": record["result"]["wall_time_seconds"],
                "branches": record["result"]["branches"],
                "conflicts": record["result"]["conflicts"],
                "body_cells": 286,
                "residual_cells": 42,
            }
        )
    summary = {
        "schema_version": "c5_count_closure_baseline_phase_supplement.v1",
        "status": "BASELINE_AND_X64_TARGET_INFEASIBLE",
        "classification": "research_local_weak_terminal_count_closure_no_router",
        "claim_boundary": (
            "Exact infeasibility applies only to c5 target (10,4,4), x65/x64 dy0 pole phases, "
            "and the pinned weakest active-terminal parent-forest candidate domain."
        ),
        "rows": rows,
        "unknown_count": 0,
        "feasible_count": 0,
        "composable_selected": None,
        "independent_selected_replay": "NOT_APPLICABLE_NO_FEASIBLE_SELECTION",
        "runner": {"path": str(RUNNER), "sha256": sha256(RUNNER)},
    }
    write_exclusive(SUMMARY, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    paths = [RUNNER, SUMMARY, *(path for path, _attempt, _moved_x in ATTEMPTS)]
    write_exclusive(
        SUMS,
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(paths, key=lambda item: item.name)),
    )
    print(json.dumps({"summary": str(SUMMARY), "sha256": sha256(SUMMARY)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
