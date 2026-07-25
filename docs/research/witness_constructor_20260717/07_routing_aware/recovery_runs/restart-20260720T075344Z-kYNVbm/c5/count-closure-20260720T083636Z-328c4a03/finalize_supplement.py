#!/usr/bin/env python3
"""Write a no-overwrite summary for supplemental attempt 11."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ATTEMPT = HERE / "attempt_11_x66_dyp0_target_10_4_4.json"
RUNNER = HERE / "run_phase_target.py"
WRAPPER = HERE / "run_supplement_target_10_4_4.py"
SUMMARY = HERE / "supplement_summary.json"
SUMS = HERE / "SHA256SUMS.supplement"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_exclusive(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def main() -> int:
    if SUMMARY.exists() or SUMS.exists():
        raise RuntimeError("refusing overwrite")
    record = json.loads(ATTEMPT.read_bytes())
    if record["target"] != [10, 4, 4] or record["phase"] != {"moved_x": 66, "uniform_y_shift": 0}:
        raise RuntimeError("attempt identity drift")
    if record["result"]["status"] != "INFEASIBLE":
        raise RuntimeError("supplement is not exact infeasible")
    if record["static_capacity"]["component_cells"] != 328:
        raise RuntimeError("component drift")
    summary = {
        "schema_version": "c5_count_closure_supplement_summary.v1",
        "status": "SUPPLEMENT_TARGET_INFEASIBLE",
        "classification": "research_local_weak_terminal_count_closure_no_router",
        "claim_boundary": (
            "Exact infeasibility applies only to c5 x66/dy0 target (10,4,4) in the pinned "
            "candidate-pose and weakest active-terminal parent-forest model."
        ),
        "attempt": {
            "path": str(ATTEMPT),
            "sha256": sha256(ATTEMPT),
            "target": [10, 4, 4],
            "phase": record["phase"],
            "status": record["result"]["status"],
            "wall_time_seconds": record["result"]["wall_time_seconds"],
            "branches": record["result"]["branches"],
            "conflicts": record["result"]["conflicts"],
            "body_cells": 286,
            "residual_cells": 42,
        },
        "composable_selected": None,
        "independent_selected_replay": "NOT_APPLICABLE_NO_FEASIBLE_SELECTION",
        "scripts": [
            {"path": str(RUNNER), "sha256": sha256(RUNNER)},
            {"path": str(WRAPPER), "sha256": sha256(WRAPPER)},
        ],
    }
    write_exclusive(SUMMARY, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    paths = (ATTEMPT, RUNNER, WRAPPER, SUMMARY)
    write_exclusive(
        SUMS,
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(paths, key=lambda item: item.name)),
    )
    print(json.dumps({"summary": str(SUMMARY), "sha256": sha256(SUMMARY)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
