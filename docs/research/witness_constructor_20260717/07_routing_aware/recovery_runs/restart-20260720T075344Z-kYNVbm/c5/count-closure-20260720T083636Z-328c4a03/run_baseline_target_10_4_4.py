#!/usr/bin/env python3
"""Run baseline c5 pole phase x65/dy0 for target (10, 4, 4)."""

from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys
from typing import Sequence


HERE = Path(__file__).resolve().parent
BASE_DRIVER = HERE / "run_target_13_4_4.py"
EXPECTED_BASE_DRIVER = "13f1382c8f630294b4aad529e13c2ea039faaa5ee7b3dbc8557c53b72c57996f"


def load_base() -> object:
    spec = importlib.util.spec_from_file_location("c5_baseline_target_base", BASE_DRIVER)
    if spec is None or spec.loader is None:
        raise RuntimeError("base driver import failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.require(module.sha256(BASE_DRIVER) == EXPECTED_BASE_DRIVER, "base driver hash drift")
    return module


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=int, choices=(12, 13), default=12)
    parser.add_argument("--moved-x", type=int, choices=(64, 65), default=65)
    args = parser.parse_args(argv)
    label = f"attempt_{args.attempt:02d}_x{args.moved_x}_dyp0_target_10_4_4"
    start = HERE / f"{label}_start.json"
    output = HERE / f"{label}.json"
    base = load_base()
    base.require(not start.exists() and not output.exists(), "refusing overwrite")
    helper = base.load_helper()
    helper.HINT_PATH = base.HINT
    helper.EXPECTED = {
        base.CANDIDATE: base.EXPECTED[base.CANDIDATE],
        base.STRICT: base.EXPECTED[base.STRICT],
        base.HINT: base.EXPECTED[base.HINT],
    }
    candidate = helper.load_pinned(base.CANDIDATE)
    strict = helper.load_pinned(base.STRICT)
    old = helper.load_pinned(base.HINT)
    fixed = helper.fixed_geometry(strict, args.moved_x, 0)
    poses, domain_counts = helper.build_domain(candidate, helper.strict_modes(strict), fixed)
    hints = helper.hint_body_modes(old, fixed["origin"])
    baseline = {
        (x, y) for x in helper.POLE_AXES for y in helper.POLE_AXES
    } - {(65, 65)}
    big_from = {(x, y) for x in (17, 29, 41) for y in (5, 17, 29)}
    big_to = {(x + 1, y) for x in (17, 29, 41) for y in (5, 17, 29)}
    c5_from = {(65, y) for y in (5, 17, 29)}
    c5_to = {(args.moved_x, y) for y in (5, 17, 29)}
    final_poles = (baseline - big_from - c5_from) | big_to | c5_to
    base.require(len(final_poles) == 35, "final pole count")
    changed_nonlocal = final_poles ^ set(fixed["pole_anchors"])
    base.require(all(x < 60 for x, _y in changed_nonlocal), "nonlocal-pole equivalence failed")
    target = (10, 4, 4)
    body_choices = Counter((pose.template, pose.body) for pose in poses)
    static = {
        "component_cells": len(fixed["c5"]),
        "target_body_cells": 286,
        "target_residual_cells": len(fixed["c5"]) - 286,
        "eligible_body_choices_by_template": {
            template: sum(key[0] == template for key in body_choices)
            for template in helper.TEMPLATES
        },
        "domain_counts": domain_counts,
        "big_pole_changes_outside_c5": True,
    }
    base.write_exclusive(
        start,
        {
            "schema_version": "c5_count_closure_phase_start.v1",
            "attempt": args.attempt,
            "target": list(target),
            "phase": {"moved_x": args.moved_x, "uniform_y_shift": 0},
            "static_capacity": static,
            "final_35_pole_anchors": [list(cell) for cell in sorted(final_poles)],
            "base_driver_sha256": EXPECTED_BASE_DRIVER,
        },
    )
    result = helper.solve_phase(poses, target, fixed, hints, 300.0, 8, 20260730 + args.attempt)
    record = {
        "schema_version": "c5_count_closure_attempt.v1",
        "classification": "research_local_weak_terminal_parent_query_no_router",
        "claim_boundary": (
            "One c5 baseline-pole exact-count query with weakest active-terminal connectivity only; "
            "no global assembly or commodity-routing conclusion."
        ),
        "attempt": args.attempt,
        "target": list(target),
        "phase": {"moved_x": args.moved_x, "uniform_y_shift": 0},
        "static_capacity": static,
        "final_35_pole_anchors": [list(cell) for cell in sorted(final_poles)],
        "result": result,
        "base_driver_sha256": EXPECTED_BASE_DRIVER,
    }
    base.write_exclusive(output, record)
    print(json.dumps({"output": str(output), "status": result["status"]}, sort_keys=True), flush=True)
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
