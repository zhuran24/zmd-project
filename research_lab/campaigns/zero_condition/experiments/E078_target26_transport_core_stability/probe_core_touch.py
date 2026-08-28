#!/usr/bin/env python3
"""E078 arm 3: ask whether any target-26 parent changes a reference core row."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

from ortools.sat.python import cp_model

HERE = Path(__file__).resolve().parent
SUPPORT = HERE / "probe_support_neighbors.py"


def load_support() -> Any:
    spec = importlib.util.spec_from_file_location("zmd_e078_support_for_core_touch", SUPPORT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SUPPORT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module.__name__] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    base = load_support()
    model, built, changed, _changed_sum = base.build_parent_model(
        prefix="e078_core_touch_parent"
    )
    model.Add(
        cp_model.LinearExpr.Sum([changed[row] for row in base.CORE_ROWS]) >= 1
    )
    run = base.solver(83001, 60.0)
    status = run.Solve(model)
    payload: dict[str, Any] = {
        "status": run.StatusName(status),
        "target": base.TARGET,
        "core_rows_local": list(base.CORE_ROWS),
        "stable_core_bodies": [
            {
                "destination_local": destination,
                "source_instance_id": str(
                    base.body_by_destination[destination]["source_instance_id"]
                ),
                "body_digest": str(
                    base.body_by_destination[destination]["body_digest"]
                ),
            }
            for destination in base.CORE_ROWS
        ],
        "core_touch_parent_exists": status in (cp_model.OPTIMAL, cp_model.FEASIBLE),
        "branches": int(run.NumBranches()),
        "conflicts": int(run.NumConflicts()),
        "wall_time": float(run.WallTime()),
    }
    if status == cp_model.INFEASIBLE:
        payload["verdict"] = "NO_PARENT_FACE_ASSIGNMENT_CHANGES_REFERENCE_CORE_ROWS"
    elif status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignment = base.selected_assignment(run, base.actual, built["x_vars"])
        payload["verdict"] = "CORE_ROW_COUNTEREXAMPLE_FOUND"
        payload["changed_core_rows"] = [
            row for row in base.CORE_ROWS if run.Value(changed[row]) == 1
        ]
        payload["counterexample_assignment_digest"] = base.e074.stable_digest(
            assignment
        )
    else:
        payload["verdict"] = "CORE_TOUCH_NONTERMINAL"
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
