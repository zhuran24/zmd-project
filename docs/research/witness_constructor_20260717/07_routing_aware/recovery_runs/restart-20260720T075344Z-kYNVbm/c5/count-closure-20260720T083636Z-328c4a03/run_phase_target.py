#!/usr/bin/env python3
"""Run one no-overwrite c5 pole-phase weak-terminal count query."""

from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Sequence


HERE = Path(__file__).resolve().parent
BASE_DRIVER = HERE / "run_target_13_4_4.py"
EXPECTED_BASE_DRIVER = "13f1382c8f630294b4aad529e13c2ea039faaa5ee7b3dbc8557c53b72c57996f"
TARGETS = {(13, 4, 4), (11, 5, 4)}


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("c5_count_closure_phase_base", BASE_DRIVER)
    if spec is None or spec.loader is None:
        raise RuntimeError("base driver import failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.require(module.sha256(BASE_DRIVER) == EXPECTED_BASE_DRIVER, "base driver hash drift")
    return module


def parse_target(raw: str) -> tuple[int, int, int]:
    target = tuple(int(value) for value in raw.split(","))
    if target not in TARGETS:
        raise argparse.ArgumentTypeError(f"unsupported target: {raw}")
    return target


def final_poles(helper: Any, moved_x: int, y_shift: int) -> set[tuple[int, int]]:
    baseline = {
        (x, y) for x in helper.POLE_AXES for y in helper.POLE_AXES
    } - {(65, 65)}
    big_from = {(x, y) for x in (17, 29, 41) for y in (5, 17, 29)}
    big_to = {(x + 1, y) for x in (17, 29, 41) for y in (5, 17, 29)}
    c5_from = {(65, y) for y in (5, 17, 29)}
    c5_to = {(moved_x, y + y_shift) for y in (5, 17, 29)}
    result = (baseline - big_from - c5_from) | big_to | c5_to
    if len(result) != 35:
        raise RuntimeError(f"final pole count: {len(result)}")
    return result


def coverage(helper: Any, strict: Any, anchors: set[tuple[int, int]]) -> set[tuple[int, int]]:
    rule = strict["power"]["coverage_from_pole_anchor"]
    return {
        (x, y)
        for anchor in anchors
        for x in range(
            max(0, anchor[0] + int(rule["x_min_offset"])),
            min(helper.GRID_SIZE - 1, anchor[0] + int(rule["x_max_offset"])) + 1,
        )
        for y in range(
            max(0, anchor[1] + int(rule["y_min_offset"])),
            min(helper.GRID_SIZE - 1, anchor[1] + int(rule["y_max_offset"])) + 1,
        )
    }


def phase_label(moved_x: int, y_shift: int) -> str:
    shift = f"p{y_shift}" if y_shift >= 0 else f"m{-y_shift}"
    return f"x{moved_x}_dy{shift}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--moved-x", type=int, choices=(66, 67, 68), required=True)
    parser.add_argument("--y-shift", type=int, choices=(-1, 0, 1), required=True)
    parser.add_argument("--target", type=parse_target, required=True)
    parser.add_argument("--seconds", type=float, default=300.0)
    args = parser.parse_args(argv)
    if args.attempt < 3 or not (1.0 <= args.seconds <= 600.0):
        raise RuntimeError("attempt/seconds contract")
    base = load_base()
    label = phase_label(args.moved_x, args.y_shift)
    target_label = "_".join(str(value) for value in args.target)
    stem = f"attempt_{args.attempt:02d}_{label}_target_{target_label}"
    start = HERE / f"{stem}_start.json"
    output = HERE / f"{stem}.json"
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
    fixed = helper.fixed_geometry(strict, args.moved_x, args.y_shift)
    poses, domain_counts = helper.build_domain(candidate, helper.strict_modes(strict), fixed)
    hints = helper.hint_body_modes(old, fixed["origin"])

    poles = final_poles(helper, args.moved_x, args.y_shift)
    local_poles = set(fixed["pole_anchors"])
    local_cells = set().union(*(helper.rect(anchor, 2, 2) for anchor in local_poles))
    final_cells = set().union(*(helper.rect(anchor, 2, 2) for anchor in poles))
    local_power = coverage(helper, strict, local_poles)
    final_power = coverage(helper, strict, poles)
    c5 = set(fixed["c5"])
    base.require(not (local_cells ^ final_cells) & c5, "nonlocal body delta reaches c5")
    base.require(not (local_power ^ final_power) & c5, "nonlocal power delta reaches c5")
    choices = Counter((pose.template, pose.body) for pose in poses)
    body_area = 9 * args.target[0] + 25 * args.target[1] + 24 * args.target[2]
    static = {
        "component_cells": len(c5),
        "target_body_cells": body_area,
        "target_residual_cells": len(c5) - body_area,
        "eligible_body_choices_by_template": {
            template: sum(key[0] == template for key in choices)
            for template in helper.TEMPLATES
        },
        "domain_counts": domain_counts,
        "nonlocal_combined35_body_delta_cells": len(local_cells ^ final_cells),
        "nonlocal_combined35_power_delta_cells": len(local_power ^ final_power),
        "c5_body_and_power_equivalent_after_big_moves": True,
    }
    base.write_exclusive(
        start,
        {
            "schema_version": "c5_count_closure_phase_start.v1",
            "attempt": args.attempt,
            "target": list(args.target),
            "phase": {"moved_x": args.moved_x, "uniform_y_shift": args.y_shift},
            "static_capacity": static,
            "final_35_pole_anchors": [list(cell) for cell in sorted(poles)],
            "base_driver_sha256": EXPECTED_BASE_DRIVER,
        },
    )
    result = helper.solve_phase(
        poses,
        args.target,
        fixed,
        hints,
        args.seconds,
        8,
        20260730 + args.attempt,
    )
    record = {
        "schema_version": "c5_count_closure_attempt.v1",
        "classification": "research_local_weak_terminal_parent_query_no_router",
        "claim_boundary": (
            "One c5 exact-count pole-phase query with weakest active-terminal connectivity only; "
            "no global assembly or commodity-routing conclusion."
        ),
        "attempt": args.attempt,
        "target": list(args.target),
        "phase": {"moved_x": args.moved_x, "uniform_y_shift": args.y_shift},
        "static_capacity": static,
        "final_35_pole_anchors": [list(cell) for cell in sorted(poles)],
        "result": result,
        "base_driver_sha256": EXPECTED_BASE_DRIVER,
    }
    base.write_exclusive(output, record)
    print(json.dumps({"output": str(output), "status": result["status"]}, sort_keys=True), flush=True)
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
