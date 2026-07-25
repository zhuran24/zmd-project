#!/usr/bin/env python3
"""Run one persistent c5 weak-terminal query for target (13, 4, 4)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
RUN = RECOVERY / "c5/count-closure-20260720T083636Z-328c4a03"
HELPER = RECOVERY / "c5/queries-ly3uZg/c5_pole_phase_search.py"
HINT = RECOVERY / "inputs/reduced_targeted_allocation_p7_36_final.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
OUTPUT = RUN / "attempt_01_x66_dy0_target_13_4_4.json"
START = RUN / "attempt_01_start.json"
EXPECTED = {
    HELPER: "c7053f9ff3adc41f6d5519c2d76e45b663de2cc4c8b21c53959cf8acff666620",
    HINT: "6c51a1ee5bef15e555242896a0a11da24c8f18746a215db53c277deee537ee80",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_exclusive(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_helper() -> object:
    for path, expected in EXPECTED.items():
        require(sha256(path) == expected, f"hash drift: {path}")
    spec = importlib.util.spec_from_file_location("c5_count_closure_helper", HELPER)
    require(spec is not None and spec.loader is not None, "helper import failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def final_poles(helper: object) -> set[tuple[int, int]]:
    baseline = {
        (x, y) for x in helper.POLE_AXES for y in helper.POLE_AXES
    } - {(65, 65)}
    moved_from = {(x, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
    moved_to = {(x + 1, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
    result = (baseline - moved_from) | moved_to
    require(len(result) == 35, "final pole count")
    return result


def main() -> int:
    require(RUN.is_dir(), "run directory missing")
    require(not START.exists() and not OUTPUT.exists(), "refusing overwrite")
    helper = load_helper()
    helper.HINT_PATH = HINT
    helper.EXPECTED = {CANDIDATE: EXPECTED[CANDIDATE], STRICT: EXPECTED[STRICT], HINT: EXPECTED[HINT]}
    candidate = helper.load_pinned(CANDIDATE)
    strict = helper.load_pinned(STRICT)
    old = helper.load_pinned(HINT)
    modes = helper.strict_modes(strict)
    fixed = helper.fixed_geometry(strict, 66, 0)
    poses, domain_counts = helper.build_domain(candidate, modes, fixed)
    hints = helper.hint_body_modes(old, fixed["origin"])
    poles = final_poles(helper)
    local_poles = set(fixed["pole_anchors"])
    changed_nonlocal = poles ^ local_poles
    require(all(x < 60 for x, _y in changed_nonlocal), "nonlocal-pole equivalence failed")
    write_exclusive(
        START,
        {
            "schema_version": "c5_count_closure_start.v1",
            "target": [13, 4, 4],
            "moved_x": 66,
            "uniform_y_shift": 0,
            "component_cells": len(fixed["c5"]),
            "domain_counts": domain_counts,
            "final_35_pole_anchors": [list(cell) for cell in sorted(poles)],
            "source_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        },
    )
    result = helper.solve_phase(poses, (13, 4, 4), fixed, hints, 300.0, 8, 20260731)
    record = {
        "schema_version": "c5_count_closure_attempt.v1",
        "classification": "research_local_weak_terminal_parent_query_no_router",
        "claim_boundary": (
            "One c5 exact-count query with weakest active-terminal connectivity only; "
            "no global assembly or commodity-routing conclusion."
        ),
        "target": [13, 4, 4],
        "phase": {"moved_x": 66, "uniform_y_shift": 0},
        "final_35_pole_anchors": [list(cell) for cell in sorted(poles)],
        "nonlocal_final_pole_changes_outside_c5": [list(cell) for cell in sorted(changed_nonlocal)],
        "component_cells": len(fixed["c5"]),
        "domain_counts": domain_counts,
        "result": result,
        "source_sha256": {str(path): digest for path, digest in EXPECTED.items()},
    }
    write_exclusive(OUTPUT, record)
    print(json.dumps({"output": str(OUTPUT), "status": result["status"]}, sort_keys=True), flush=True)
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
