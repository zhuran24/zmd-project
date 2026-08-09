#!/usr/bin/env python3
"""Run the second x66/dy0 c5 count-closure target persistently."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASE_DRIVER = HERE / "run_target_13_4_4.py"
EXPECTED_BASE_DRIVER = "13f1382c8f630294b4aad529e13c2ea039faaa5ee7b3dbc8557c53b72c57996f"
START = HERE / "attempt_02_start.json"
OUTPUT = HERE / "attempt_02_x66_dy0_target_11_5_4.json"


def main() -> int:
    spec = importlib.util.spec_from_file_location("c5_count_closure_base", BASE_DRIVER)
    if spec is None or spec.loader is None:
        raise RuntimeError("base driver import failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.require(module.sha256(BASE_DRIVER) == EXPECTED_BASE_DRIVER, "base driver hash drift")
    module.require(not START.exists() and not OUTPUT.exists(), "refusing overwrite")
    helper = module.load_helper()
    helper.HINT_PATH = module.HINT
    helper.EXPECTED = {
        module.CANDIDATE: module.EXPECTED[module.CANDIDATE],
        module.STRICT: module.EXPECTED[module.STRICT],
        module.HINT: module.EXPECTED[module.HINT],
    }
    candidate = helper.load_pinned(module.CANDIDATE)
    strict = helper.load_pinned(module.STRICT)
    old = helper.load_pinned(module.HINT)
    fixed = helper.fixed_geometry(strict, 66, 0)
    poses, domain_counts = helper.build_domain(candidate, helper.strict_modes(strict), fixed)
    hints = helper.hint_body_modes(old, fixed["origin"])
    poles = module.final_poles(helper)
    changed_nonlocal = poles ^ set(fixed["pole_anchors"])
    module.require(all(x < 60 for x, _y in changed_nonlocal), "nonlocal-pole equivalence failed")
    target = (11, 5, 4)
    module.write_exclusive(
        START,
        {
            "schema_version": "c5_count_closure_start.v1",
            "target": list(target),
            "moved_x": 66,
            "uniform_y_shift": 0,
            "component_cells": len(fixed["c5"]),
            "domain_counts": domain_counts,
            "base_driver_sha256": EXPECTED_BASE_DRIVER,
        },
    )
    result = helper.solve_phase(poses, target, fixed, hints, 300.0, 8, 20260732)
    record = {
        "schema_version": "c5_count_closure_attempt.v1",
        "classification": "research_local_weak_terminal_parent_query_no_router",
        "claim_boundary": (
            "One c5 exact-count query with weakest active-terminal connectivity only; "
            "no global assembly or commodity-routing conclusion."
        ),
        "target": list(target),
        "phase": {"moved_x": 66, "uniform_y_shift": 0},
        "final_35_pole_anchors": [list(cell) for cell in sorted(poles)],
        "nonlocal_final_pole_changes_outside_c5": [list(cell) for cell in sorted(changed_nonlocal)],
        "component_cells": len(fixed["c5"]),
        "domain_counts": domain_counts,
        "result": result,
        "base_driver_sha256": EXPECTED_BASE_DRIVER,
    }
    module.write_exclusive(OUTPUT, record)
    print(json.dumps({"output": str(OUTPUT), "status": result["status"]}, sort_keys=True), flush=True)
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
