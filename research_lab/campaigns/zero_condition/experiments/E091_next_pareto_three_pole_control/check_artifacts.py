#!/usr/bin/env python3
"""Artifact and derivation checks for E091's body/power control negative."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e091.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E091_next_pareto_three_pole_control/run-001"
)
RESULT = RUN / "RESULT.json"
POWER_RESULT = RUN / "POWER_RESULT.json"
POWER_DERIVATION = RUN / "POWER_DERIVATION.json"
POWER_DERIVED = RUN / "POWER_DERIVED.py"
OUTPUT = RUN / "ARTIFACT_CHECK.json"

EXPECTED = {
    RUNNER: "b6b47d529d640d017a5657f8ebcb0b626145bc9ba0e262704d1db972789d1905",
    RESULT: "c7e06307c81b72cd12fa3dd7070cd7b9c5586863d0c369651ad4d5ac9b30d3f1",
    POWER_RESULT: "4e9c05583ce43b910038493840d913af9ae2747ef31440b96ecd416be2b0a10c",
    POWER_DERIVATION: "9290669d603a23faf50e9d517229ab1b3d274cfece4b9486b186a21e892eaa0f",
    POWER_DERIVED: "7a8e555b90ecfd9741b8b1dd88d3d071e4432ce6999c96d91126b080d3597b1a",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, payload: Any) -> None:
    raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    require(not OUTPUT.exists(), "refusing to overwrite E091 artifact check")
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E091 artifact: {path}")
        require(sha256(path) == expected, f"E091 artifact identity drift: {path}")

    result = load(RESULT)
    power = load(POWER_RESULT)
    derivation = load(POWER_DERIVATION)
    require(
        result.get("verdict")
        == "CONTROL_PARTITION_THREE_POLE_BODY_POWER_INFEASIBLE",
        "E091 verdict drift",
    )
    require(
        result.get("decision") == "REASSESS_REMAINING_PARETO_BEAM_OR_POLE_BUDGET",
        "E091 decision drift",
    )
    require(result.get("front_stage") is None, "E091 front stage unexpectedly ran")
    control = result["control"]
    require(control["partition_id"] == "partition_97f9ba7e7ad710dc", "partition drift")
    require(control["corridor_y"] == 17, "corridor drift")
    require(control["module_low"] == "B" and control["module_high"] == "A", "side drift")
    require(control["stable_module"] == "A", "stable module drift")
    require(control["maximum_relocated_poles"] == 3, "pole cap drift")

    require(power.get("status") == "MASTER_INFEASIBLE", "power status drift")
    require(power.get("solver_status") == "INFEASIBLE", "solver status drift")
    require(power.get("partition_id") == control["partition_id"], "power partition drift")
    require(power.get("corridor_y") == 17, "power corridor drift")
    require(power.get("max_relocated_poles") == 3, "power pole cap drift")
    require(power.get("minimum_retained_current_poles") == 50, "power pole floor drift")
    require(power.get("body_candidate_count") == 14867, "body candidate count drift")
    require(power.get("pole_candidate_count") == 4316, "pole candidate count drift")
    require(not power.get("selected_manufacturing"), "negative carries body witness")
    require(not power.get("selected_poles"), "negative carries pole witness")

    changes = derivation["semantic_changes"]
    require(changes["partition_id"] == control["partition_id"], "derivation partition drift")
    require(changes["corridor_y"] == 17, "derivation corridor drift")
    require(changes["module_low"] == "B" and changes["module_high"] == "A", "derivation side drift")
    require(changes["stable_module"] == "A", "derivation stable module drift")
    require(changes["exact_pole_count"] == 53, "derivation pole count drift")
    require(changes["maximum_relocated_poles"] == 3, "derivation pole cap drift")
    require(changes["pure_feasibility"] is True, "derivation objective drift")
    require(changes["complete_boundary_disjunction"] is True, "boundary drift")
    require(changes["same_power_and_nonoverlap_semantics"] is True, "power semantics drift")

    source = POWER_DERIVED.read_text(encoding="utf-8")
    compile(source, str(POWER_DERIVED), "exec")
    require('context = detailed[TARGET_PARTITION_ID]' in source, "target selection missing")
    require('if module == "B" and max(ys) >= CORRIDOR_Y' in source, "low-side rule missing")
    require('if module == "A" and min(ys) <= CORRIDOR_Y' in source, "high-side rule missing")
    require('if row["module"] == "A"' in source, "stable-module remap missing")
    require('sum(current_pole_vars)' in source, "pole floor missing")
    require('solver.parameters.stop_after_first_solution = True' in source, "first-solution control missing")
    require('model.Maximize(' not in source, "power objective unexpectedly remains")

    payload = {
        "schema": "zmd_e091_control_body_power_artifact_check_v1",
        "status": "PASS",
        "classification": "EXACT_CONTEXTUAL_BODY_POWER_INFEASIBLE",
        "verdict": result["verdict"],
        "decision": result["decision"],
        "partition_id": control["partition_id"],
        "corridor_y": 17,
        "maximum_relocated_poles": 3,
        "solver_status": power["solver_status"],
        "elapsed_seconds": power["elapsed_seconds"],
        "branches": power["branches"],
        "conflicts": power["conflicts"],
        "front_stage_ran": False,
        "truth_boundary": (
            "Static derivation and terminal artifact replay. The exact negative is "
            "contextual to partition_97f9ba7e7ad710dc, y=17 and at most three pole "
            "relocations; it does not imply front or global infeasibility."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "classification": payload["classification"],
                "solver_status": payload["solver_status"],
                "elapsed_seconds": payload["elapsed_seconds"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256(OUTPUT),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
