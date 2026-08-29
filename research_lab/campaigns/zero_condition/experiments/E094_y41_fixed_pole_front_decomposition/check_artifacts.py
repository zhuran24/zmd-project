#!/usr/bin/env python3
"""Artifact and derivation checks for E094's censored fixed-anchor slice."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e094.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E094_y41_fixed_pole_front_decomposition/run-001"
)
RESULT = RUN / "RESULT.json"
DERIVATION = RUN / "DERIVATION.json"
DERIVED = RUN / "DERIVED_PRODUCER.py"
ARM1 = RUN / "arm-01-fixed_poles_fixed_boundary/RESULT.json"
ARM2 = RUN / "arm-02-fixed_poles_all_boundaries/RESULT.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"

EXPECTED = {
    RUNNER: "aa98723b507d1ac9699fba64e089dac205fd677df429e19b2cf6c8947e8ac29c",
    RESULT: "2f8903fd49b2cda2767c2fbb8b3c272d68b1483fc1ce5d4b02c06a22c48e5877",
    DERIVATION: "9318856706332e979348b26c95e0cbd67469e6442c8831c9dc5d908060ab47cc",
    DERIVED: "65c6cadc4d0f37266ca181761bec625bcfdf7d8be2b344136a6a14b5669ac4ce",
    ARM1: "474fd3db61ff7b02e4f58381ede70de37115a21152560a05d9506eb027482965",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, payload: Any) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    require(not OUTPUT.exists(), "refusing to overwrite E094 artifact check")
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E094 artifact: {path}")
        require(sha256(path) == expected, f"E094 artifact identity drift: {path}")
    require(not ARM2.exists(), "E094 all-boundary arm should not run after Arm-A UNKNOWN")

    result = load(RESULT)
    arm = load(ARM1)
    derivation = load(DERIVATION)
    require(result["verdict"] == "FIXED_POLE_BOUNDARY_FRONT_SLICE_CENSORED", "verdict drift")
    require(result["decision"] == "DECOMPOSE_BODY_FRONT_ASSIGNMENT_BEFORE_RELEASING_BOUNDARY_OR_POLES", "decision drift")
    require(result["arm_count"] == 1 and len(result["arms"]) == 1, "arm count drift")
    require(result["anchor"]["boundary_state_id"] == "boundary_macro_09", "anchor boundary drift")
    require(result["anchor"]["fixed_pole_count"] == 53, "anchor pole count drift")
    require(result["anchor"]["relocated_pole_count"] == 3, "anchor pole move drift")

    wrapped = result["arms"][0]
    require(wrapped["status"] == "UNKNOWN", "wrapper status drift")
    require(wrapped["solver_status"] == "UNKNOWN", "wrapper solver status drift")
    require(wrapped["controls"] == {
        "arm_id": "fixed_poles_fixed_boundary",
        "fix_boundary": True,
        "seconds": 120.0,
        "seed": 94001,
    }, "arm controls drift")
    require(wrapped["result_sha256"] == EXPECTED[ARM1], "arm hash drift")
    require(wrapped["selected_manufacturing_count"] == 0, "UNKNOWN carries body witness")
    require(wrapped["selected_pole_count"] == 0, "UNKNOWN carries pole witness")

    require(arm["status"] == "UNKNOWN" and arm["solver_status"] == "UNKNOWN", "producer status drift")
    require(arm["fixed_pole_set"] is True, "fixed pole restriction absent")
    require(arm["fixed_boundary"] is True, "fixed boundary restriction absent")
    require(len(arm["fixed_pole_pose_indices"]) == 53, "fixed pole list drift")
    require(arm["anchor_boundary_state_index"] == 8, "boundary index drift")
    require(arm["anchor_boundary_state_id"] == "boundary_macro_09", "boundary ID drift")
    require(arm["body_candidate_count"] == 14867, "body candidate drift")
    require(arm["pole_candidate_count"] == 4316, "pole candidate drift")
    require(arm["mode_class_variable_count"] == 92188, "mode-class drift")
    require(arm["model_variable_count"] == 116318, "model variable drift")
    require(arm["model_constraint_count"] == 228082, "model constraint drift")
    require(not arm.get("selected_manufacturing"), "producer UNKNOWN carries bodies")
    require(not arm.get("selected_poles"), "producer UNKNOWN carries poles")

    common = derivation["common_restriction"]
    require(common["fixed_pole_count"] == 53, "derivation pole count drift")
    require(common["relocated_pole_count"] == 3, "derivation pole move drift")
    require(common["same_y41_partition"] is True, "derivation partition drift")
    require(common["same_complete_front_class_semantics"] is True, "front semantics drift")
    require(common["same_power_and_nonoverlap"] is True, "power semantics drift")
    require(common["same_219_body_and_stable_E078_requirements"] is True, "body semantics drift")

    source = DERIVED.read_text(encoding="utf-8")
    compile(source, str(DERIVED), "exec")
    require("E090_" not in source and "zmd_e090" not in source, "stale namespace")
    require("fixed_pole_pose_indices" in source, "fixed pole constraints absent")
    require('model.Add(variable == int(index == hint_boundary))' in source, "fixed boundary constraints absent")
    require('PORTFOLIO_WITH_QUICK_RESTART_SEARCH' in source, "search control drift")
    require('model.Maximize(' not in source, "objective unexpectedly present")

    require(wrapped["telemetry"]["oom_delta"] in (None, 0), "OOM counter increased")
    require(wrapped["telemetry"]["oom_kill_delta"] in (None, 0), "OOM-kill counter increased")
    payload = {
        "schema": "zmd_e094_fixed_pole_front_artifact_check_v1",
        "status": "PASS",
        "classification": "CENSORED_FIXED_POLE_FIXED_BOUNDARY_FRONT_SLICE",
        "verdict": result["verdict"],
        "decision": result["decision"],
        "arm_count": 1,
        "producer_status": arm["status"],
        "elapsed_seconds": arm["elapsed_seconds"],
        "branches": arm["branches"],
        "conflicts": arm["conflicts"],
        "process_ru_maxrss_kib": wrapped["telemetry"]["process_after"]["ru_maxrss_kib"],
        "all_boundary_arm_ran": False,
        "truth_boundary": (
            "Artifact and derivation replay only. UNKNOWN remains censored. The "
            "slice fixes one exact pole set and boundary_macro_09 and proves no "
            "infeasibility or native-front witness."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(OUTPUT, payload)
    print(json.dumps({"status": payload["status"], "classification": payload["classification"], "producer_status": payload["producer_status"], "output_path": str(OUTPUT.relative_to(ROOT)), "output_sha256": sha256(OUTPUT)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
