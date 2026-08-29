#!/usr/bin/env python3
"""Artifact and derivation checks for E093's terminal admission replay."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e093.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E093_e080_seed_admission_replay/run-001"
)
RESULT = RUN / "RESULT.json"
DERIVATION = RUN / "DERIVATION.json"
DERIVED = RUN / "DERIVED_PRODUCER.py"
ARM1 = RUN / "arm-01-pseudo_cost_single_worker/RESULT.json"
ARM2 = RUN / "arm-02-quick_restart_portfolio/RESULT.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"

EXPECTED = {
    RUNNER: "d0b2e180a81c01c93f55db31bcb0b77772f77c7ea330ca7e3f12c05aa65969d2",
    RESULT: "0fe35a818735c79ebeffef1329e748b8c796b656a57d9f160a4cc72c200025ea",
    DERIVATION: "0358596e97d2ed0042ae45cd33573dd4313f187dd34f5b6a89fd2a825d92046c",
    DERIVED: "101e33554d9279e5fbc3175aefda5923d307325e0ef91b3f0f71e6daf657d298",
    ARM1: "86895fe1cac1ca83ddadd3fc71477ee8ae7193e23d1e73fa921bd306436225e6",
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
    require(not OUTPUT.exists(), "refusing to overwrite E093 artifact check")
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E093 artifact: {path}")
        require(sha256(path) == expected, f"E093 artifact identity drift: {path}")
    require(not ARM2.exists(), "E093 second arm should not exist after terminal arm 1")

    result = load(RESULT)
    arm = load(ARM1)
    derivation = load(DERIVATION)
    require(
        result.get("verdict") == "E080_SEED_THREE_POLE_BODY_POWER_INFEASIBLE",
        "E093 verdict drift",
    )
    require(
        result.get("decision")
        == "Y41_IS_SOLE_ADMITTED_SKELETON_CHOOSE_POLE_BUDGET_OR_FRONT_DECOMPOSITION",
        "E093 decision drift",
    )
    context = result["context"]
    require(context["partition_id"] == "partition_5a72220e0268a3c1", "partition drift")
    require(context["corridor_axis"] == "y" and context["corridor_coordinate"] == 21, "corridor drift")
    require(context["module_low"] == "B" and context["module_high"] == "A", "side drift")
    require(context["stable_module"] == "A", "stable module drift")
    require(context["maximum_relocated_poles"] == 3, "pole cap drift")
    require(context["minimum_retained_current_poles"] == 50, "pole floor drift")

    require(result["arm_count"] == 1, "E093 arm count drift")
    require(result["terminal_arm_id"] == "pseudo_cost_single_worker", "terminal arm drift")
    require(len(result["arms"]) == 1, "E093 arm list drift")
    wrapper_arm = result["arms"][0]
    require(wrapper_arm["result_sha256"] == EXPECTED[ARM1], "arm identity drift")
    require(wrapper_arm["status"] == "MASTER_INFEASIBLE", "wrapper arm status drift")
    require(wrapper_arm["solver_status"] == "INFEASIBLE", "wrapper solver status drift")
    controls = wrapper_arm["controls"]
    require(controls == {
        "arm_id": "pseudo_cost_single_worker",
        "seconds": 110.0,
        "workers": 1,
        "search_branching": "PSEUDO_COST_SEARCH",
        "symmetry_level": 0,
        "probing_level": 0,
        "randomize_search": False,
        "seed": 93001,
    }, "E093 arm controls drift")

    require(arm["status"] == "MASTER_INFEASIBLE", "producer status drift")
    require(arm["solver_status"] == "INFEASIBLE", "producer solver status drift")
    require(arm["partition_id"] == context["partition_id"], "producer partition drift")
    require(arm["corridor_axis"] == "y" and arm["corridor_coordinate"] == 21, "producer corridor drift")
    require(arm["module_low"] == "B" and arm["module_high"] == "A", "producer side drift")
    require(arm["stable_module"] == "A", "producer stable module drift")
    require(arm["max_relocated_poles"] == 3, "producer pole cap drift")
    require(arm["minimum_retained_current_poles"] == 50, "producer pole floor drift")
    require(arm["body_candidate_count"] == 14867, "body candidate count drift")
    require(arm["pole_candidate_count"] == 4315, "pole candidate count drift")
    require(arm["model_variable_count"] == 19229, "model variable count drift")
    require(arm["model_constraint_count"] == 19562, "model constraint count drift")
    require(not arm.get("selected_manufacturing"), "negative carries body witness")
    require(not arm.get("selected_poles"), "negative carries pole witness")

    require(derivation["feasible_set_changes"] == [], "E093 feasible-set change recorded")
    frozen = derivation["frozen_context"]
    require(frozen["partition_id"] == context["partition_id"], "derivation partition drift")
    require(frozen["corridor_coordinate"] == 21, "derivation corridor drift")
    require(frozen["exact_manufacturing_count"] == 219, "derivation body count drift")
    require(frozen["exact_pole_count"] == 53, "derivation pole count drift")
    require(frozen["maximum_relocated_poles"] == 3, "derivation pole cap drift")
    require(frozen["complete_boundary_disjunction"] is True, "derivation boundary drift")
    require(frozen["power_and_nonoverlap"] is True, "derivation power drift")

    source = DERIVED.read_text(encoding="utf-8")
    compile(source, str(DERIVED), "exec")
    require("E092_" not in source and "zmd_e092" not in source, "stale E092 namespace")
    require('E093_SEARCH_BRANCHING' in source, "search control absent")
    require('getattr(cp_model, branching_name)' in source, "branching dispatch absent")
    require('solver.parameters.stop_after_first_solution = True' in source, "first-solution control absent")
    require('model.Maximize(' not in source, "objective unexpectedly present")
    require('sum(current_pole_vars)' in source, "pole floor absent")

    oom_delta = wrapper_arm["telemetry"]["oom_delta"]
    oom_kill_delta = wrapper_arm["telemetry"]["oom_kill_delta"]
    require(oom_delta in (None, 0), f"OOM counter increased: {oom_delta}")
    require(oom_kill_delta in (None, 0), f"OOM-kill counter increased: {oom_kill_delta}")

    payload = {
        "schema": "zmd_e093_e080_seed_admission_artifact_check_v1",
        "status": "PASS",
        "classification": "EXACT_CONTEXTUAL_BODY_POWER_INFEASIBLE",
        "verdict": result["verdict"],
        "decision": result["decision"],
        "terminal_arm_id": result["terminal_arm_id"],
        "arm_count": 1,
        "solver_status": arm["solver_status"],
        "elapsed_seconds": arm["elapsed_seconds"],
        "branches": arm["branches"],
        "conflicts": arm["conflicts"],
        "process_ru_maxrss_kib": wrapper_arm["telemetry"]["process_after"]["ru_maxrss_kib"],
        "second_arm_ran": False,
        "truth_boundary": (
            "Static derivation and terminal artifact replay. The exact negative is "
            "contextual to partition_5a72220e0268a3c1/y=21 and the three-pole "
            "body/pole/power language. No native-front or downstream claim."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(OUTPUT, payload)
    print(json.dumps({"status": payload["status"], "classification": payload["classification"], "solver_status": payload["solver_status"], "elapsed_seconds": payload["elapsed_seconds"], "output_path": str(OUTPUT.relative_to(ROOT)), "output_sha256": sha256(OUTPUT)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
