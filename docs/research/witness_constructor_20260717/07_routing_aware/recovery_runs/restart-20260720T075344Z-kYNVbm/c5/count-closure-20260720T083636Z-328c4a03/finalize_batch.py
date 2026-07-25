#!/usr/bin/env python3
"""Fail-closed summary for the persistent c5 count-closure batch."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SUMMARY = HERE / "summary.json"
SUMS = HERE / "SHA256SUMS"
QUERIES = (
    ("attempt_01_x66_dy0_target_13_4_4.json", 66, 0, (13, 4, 4)),
    ("attempt_02_x66_dy0_target_11_5_4.json", 66, 0, (11, 5, 4)),
    ("attempt_03_x67_dyp0_target_13_4_4.json", 67, 0, (13, 4, 4)),
    ("attempt_04_x68_dyp0_target_13_4_4.json", 68, 0, (13, 4, 4)),
    ("attempt_05_x66_dym1_target_13_4_4.json", 66, -1, (13, 4, 4)),
    ("attempt_06_x66_dyp1_target_13_4_4.json", 66, 1, (13, 4, 4)),
    ("attempt_07_x67_dyp0_target_11_5_4.json", 67, 0, (11, 5, 4)),
    ("attempt_08_x68_dyp0_target_11_5_4.json", 68, 0, (11, 5, 4)),
    ("attempt_09_x66_dym1_target_11_5_4.json", 66, -1, (11, 5, 4)),
    ("attempt_10_x66_dyp1_target_11_5_4.json", 66, 1, (11, 5, 4)),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def expected_poles(moved_x: int, y_shift: int) -> set[tuple[int, int]]:
    axes = (5, 17, 29, 41, 53, 65)
    baseline = {(x, y) for x in axes for y in axes} - {(65, 65)}
    moved_from = {(x, y) for x in (17, 29, 41) for y in (5, 17, 29)} | {
        (65, y) for y in (5, 17, 29)
    }
    moved_to = {(x + 1, y) for x in (17, 29, 41) for y in (5, 17, 29)} | {
        (moved_x, y + y_shift) for y in (5, 17, 29)
    }
    return (baseline - moved_from) | moved_to


def write_exclusive(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def main() -> int:
    require(not SUMMARY.exists() and not SUMS.exists(), "refusing overwrite")
    rows = []
    statuses = []
    for filename, moved_x, y_shift, target in QUERIES:
        path = HERE / filename
        require(path.is_file() and not path.is_symlink(), f"missing regular result: {path}")
        record = json.loads(path.read_bytes())
        require(record["schema_version"] == "c5_count_closure_attempt.v1", "schema drift")
        require(tuple(record["target"]) == target, f"target drift: {filename}")
        require(record["phase"] == {"moved_x": moved_x, "uniform_y_shift": y_shift}, "phase drift")
        poles = {tuple(cell) for cell in record["final_35_pole_anchors"]}
        require(poles == expected_poles(moved_x, y_shift), f"pole drift: {filename}")
        require(len(poles) == 35, f"pole count drift: {filename}")
        result = record["result"]
        status = str(result["status"])
        require(status in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"}, "status drift")
        component_cells = int(
            record["component_cells"]
            if "component_cells" in record
            else record["static_capacity"]["component_cells"]
        )
        require(component_cells == 328, f"component size drift: {filename}")
        body_cells = 9 * target[0] + 25 * target[1] + 24 * target[2]
        rows.append(
            {
                "path": str(path),
                "sha256": sha256(path),
                "phase": record["phase"],
                "target": list(target),
                "target_body_cells": body_cells,
                "target_residual_cells": component_cells - body_cells,
                "status": status,
                "wall_time_seconds": float(result["wall_time_seconds"]),
                "branches": int(result["branches"]),
                "conflicts": int(result["conflicts"]),
            }
        )
        statuses.append(status)
    require(all(status == "INFEASIBLE" for status in statuses), "batch is not all exact infeasible")
    scripts = [HERE / name for name in ("run_target_13_4_4.py", "run_target_11_5_4.py", "run_phase_target.py")]
    summary = {
        "schema_version": "c5_count_closure_summary.v1",
        "status": "ALL_QUERIED_PHASE_TARGET_PAIRS_INFEASIBLE",
        "classification": "research_local_weak_terminal_count_closure_no_router",
        "claim_boundary": (
            "Exact infeasibility applies only to the listed c5 candidate-pose domains, pole phases, "
            "targets, and weakest active-terminal parent-forest model. It is not a global layout, "
            "commodity-routing, or unlisted-phase infeasibility conclusion."
        ),
        "query_count": len(rows),
        "unknown_count": 0,
        "feasible_count": 0,
        "composable_selected": None,
        "independent_selected_replay": "NOT_APPLICABLE_NO_FEASIBLE_SELECTION",
        "connected_capacity": {
            "status": "NO_SELECTED_POSES",
            "component_cells": 328,
            "target_13_4_4": {"body_cells": 313, "residual_cells": 15},
            "target_11_5_4": {"body_cells": 320, "residual_cells": 8},
        },
        "rows": rows,
        "scripts": [{"path": str(path), "sha256": sha256(path)} for path in scripts],
    }
    write_exclusive(SUMMARY, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    sum_paths = [*scripts, *(HERE / filename for filename, *_rest in QUERIES), SUMMARY]
    lines = [f"{sha256(path)}  {path.name}" for path in sorted(sum_paths, key=lambda item: item.name)]
    write_exclusive(SUMS, "\n".join(lines) + "\n")
    print(json.dumps({"summary": str(SUMMARY), "sha256": sha256(SUMMARY)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
