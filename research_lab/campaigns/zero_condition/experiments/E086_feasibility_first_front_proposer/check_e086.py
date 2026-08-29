#!/usr/bin/env python3
"""Artifact and semantic-scope checker for E086 run-001."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e086.py"
RUN = ROOT / "research_lab/local/zero_condition/E086_feasibility_first_front_proposer/run-001"
RESULT = RUN / "RESULT.json"
PRODUCER = RUN / "PRODUCER_RESULT.json"
CHECKPOINT = RUN / "CHECKPOINT.json"
DERIVATION = RUN / "DERIVATION.json"
DERIVED = RUN / "DERIVED_PRODUCER.py"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
SOURCE_CHECKPOINT = ROOT / "research_lab/local/zero_condition/E084_front_benders_checkpoint.json"

EXPECTED = {
    RUNNER: "d45bbad8f09dfea93316cdb4fd3538f4749875313ac38198c33624ce4086b374",
    RESULT: "fdb6ad438a05802c24f3a21d7eee5fe05b5bf738f41614e7af99476c887f1351",
    PRODUCER: "7c0db41332c3362725209774de29ab95baca792e6cacd53fdc068da40bec593c",
    CHECKPOINT: "06cadbed6f61cb04c8c5445b778378bca336ddc2fa1f2f0804962c1ceb70933d",
    DERIVATION: "9fde5be7a4bdda9427f1e0b09be7884b1abef731e211dcb3548b1aa3f8d88b87",
    DERIVED: "f78d6d6a1cffdb4d5f9e695c18ea60711befc3ad2129628845167ef2b3b8a8c7",
    SOURCE_CHECKPOINT: "0648bf057670c454d1c55a73417d127867c597063362407fe732c4a1b4c6ad9d",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_runner() -> Any:
    name = "zmd_e086_checker_runner"
    spec = importlib.util.spec_from_file_location(name, RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import E086 runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E086 artifact: {path}")
        require(sha256(path) == expected, f"E086 artifact identity drift: {path}")

    result = load(RESULT)
    producer = load(PRODUCER)
    checkpoint = load(CHECKPOINT)
    source_checkpoint = load(SOURCE_CHECKPOINT)
    derivation = load(DERIVATION)

    require(
        result["verdict"] == "FEASIBILITY_FIRST_PROPOSER_LEARNED_NEW_FRONT_KNOWLEDGE",
        "E086 wrapper verdict drift",
    )
    require(
        result["decision"] == "CONTINUE_FROM_E086_CHECKPOINT_IN_FRESH_SUCCESSOR",
        "E086 wrapper decision drift",
    )
    require(producer["status"] == "ITERATION_LIMIT", "E086 producer status drift")
    require(producer["search_objective"] == "MAXIMIZE_RETAINED_CURRENT_FOOTPRINTS", "E086 objective drift")
    require(producer["fixed_retained_target"] is None, "E086 retained target unexpectedly fixed")
    require(int(producer["iteration_count"]) == 2, "E086 iteration count drift")
    require(int(producer["registered_front_candidate_count"]) == 98, "E086 front count drift")
    require(int(producer["operation_nogood_count"]) == 0, "E086 operation nogood drift")
    require("selected_manufacturing" not in producer, "E086 iteration-limit result carried witness")

    records = list(producer["records"])
    require(len(records) == 2, "E086 record count drift")
    expected_records = (
        {
            "master_status": "OPTIMAL",
            "retained": 184,
            "bound": 184.0,
            "empty": 35,
            "new": 35,
            "front_total": 69,
            "boundary": "boundary_macro_27",
            "pole": "p_x52_y48_o0_m_omni",
        },
        {
            "master_status": "FEASIBLE",
            "retained": 181,
            "bound": 187.0,
            "empty": 29,
            "new": 29,
            "front_total": 98,
            "boundary": "boundary_macro_46",
            "pole": "p_x51_y42_o0_m_omni",
        },
    )
    all_new_indices: list[int] = []
    for row, expected in zip(records, expected_records, strict=True):
        require(row["master_status"] == expected["master_status"], "E086 master status drift")
        require(int(row["retained_current_footprints"]) == expected["retained"], "E086 retained drift")
        require(float(row["retained_best_bound"]) == expected["bound"], "E086 bound drift")
        require(int(row["operation_checker_empty_count"]) == expected["empty"], "E086 empty-domain count drift")
        require(row["operation_checker_status"] == "EMPTY_DOMAIN", "E086 checker status drift")
        require(len(row["newly_registered_front_candidates"]) == expected["new"], "E086 new-rule count drift")
        require(int(row["registered_front_candidate_count"]) == expected["front_total"], "E086 cumulative rule count drift")
        require(row["selected_boundary_state_id"] == expected["boundary"], "E086 boundary state drift")
        require(row["selected_replacement_pole"] == expected["pole"], "E086 replacement pole drift")
        all_new_indices.extend(map(int, row["newly_registered_front_candidates"]))
    require(len(all_new_indices) == 64, "E086 total new-rule count drift")
    require(len(set(all_new_indices)) == 64, "E086 duplicated newly registered rule")

    source_rules = set(map(int, source_checkpoint["front_rule_stats"]))
    final_rules = set(map(int, checkpoint["front_rule_stats"]))
    require(len(source_rules) == 34, "E086 source-rule cardinality drift")
    require(len(final_rules) == 98, "E086 final-rule cardinality drift")
    require(source_rules < final_rules, "E086 source rules are not a strict subset")
    require(final_rules - source_rules == set(all_new_indices), "E086 checkpoint growth does not match records")
    require(int(checkpoint["operation_nogood_count"]) == 0, "E086 checkpoint nogood drift")
    require(checkpoint["terminal"] == "ITERATION_LIMIT", "E086 checkpoint terminal drift")

    runner = load_runner()
    fresh_derived, fresh_patches = runner.derive_source()
    require(fresh_derived.encode("utf-8") == DERIVED.read_bytes(), "E086 derived source replay drift")
    require(len(fresh_patches) == 9, "E086 patch count drift")
    compile(fresh_derived, str(DERIVED), "exec", dont_inherit=True)
    require(derivation["derived_sha256"] == EXPECTED[DERIVED], "E086 derivation nested hash drift")
    require(len(derivation["patches"]) == 9, "E086 derivation patch list drift")

    semantic = derivation["semantic_preservation"]
    require(semantic["changed_feasible_set"] is False, "unexpected raw correction state")
    require(semantic["changed_hints_only"] is True, "unexpected raw hint marker state")
    # Those two self-descriptions are wrong: removing retained==186 broadens the
    # model from one rung to the full one-replacement language, and the objective,
    # seed family and solver parameters changed in addition to the hint.

    telemetry = result["telemetry"]
    before_events: Mapping[str, Any] = telemetry["cgroup_before"].get("memory_events") or {}
    after_events: Mapping[str, Any] = telemetry["cgroup_after"].get("memory_events") or {}
    oom_delta = int(after_events.get("oom", 0)) - int(before_events.get("oom", 0))
    oom_kill_delta = int(after_events.get("oom_kill", 0)) - int(before_events.get("oom_kill", 0))
    require(oom_delta == 0 and oom_kill_delta == 0, "E086 observed OOM event")

    payload = {
        "schema": "zmd_e086_feasibility_first_front_artifact_check_v1",
        "status": "PASS_WITH_SEMANTIC_CORRECTION",
        "authority": "research_only_noncertified",
        "corrected_scope": (
            "full bounded one-replacement y=41 feasibility-first language across all "
            "retained-current-footprint counts; not an r33-equivalent feasible set"
        ),
        "raw_self_description_corrections": {
            "semantic_preservation.changed_feasible_set": {
                "raw": False,
                "correct": True,
                "reason": "retained==186 was removed, broadening the model beyond one rung",
            },
            "semantic_preservation.changed_hints_only": {
                "raw": True,
                "correct": False,
                "reason": "objective, seed family and solver parameters also changed",
            },
            "wrapper.truth_boundary_not_the_stated_one_replacement_feasible_set": {
                "raw_implication": "same feasible set as E085",
                "correct": "same base y=41 one-replacement constraints but a broader retained-count language",
            },
        },
        "scientific_result": {
            "producer_status": "ITERATION_LIMIT",
            "first_candidate": {
                "retained_current_footprints": 184,
                "optimal_under_then_registered_69_rule_model": True,
                "empty_native_front_bodies": 35,
            },
            "second_candidate": {
                "retained_current_footprints": 181,
                "best_bound": 187.0,
                "empty_native_front_bodies": 29,
            },
            "initial_front_rule_count": 34,
            "final_front_rule_count": 98,
            "new_verified_body_local_front_rules": 64,
            "operation_nogood_count": 0,
            "front_operation_witness": False,
        },
        "decision": "CONTINUE_FROM_98_RULE_CHECKPOINT_WITH_CORRECTED_SCOPE",
        "telemetry": {
            "elapsed_seconds": float(telemetry["elapsed_seconds"]),
            "process_ru_maxrss_kib": int(telemetry["process_after"]["ru_maxrss_kib"]),
            "oom_event_delta": oom_delta,
            "oom_kill_event_delta": oom_kill_delta,
        },
        "checked_artifacts": {
            display(path): {"sha256": expected, "size_bytes": path.stat().st_size}
            for path, expected in EXPECTED.items()
        },
        "truth_boundary": (
            "E086 produced two body/pole/power candidates and 64 additional necessary "
            "body-local front rules. Both candidates failed before exact named-operation "
            "assignment because they contained empty front domains. No witness, terminal "
            "uniqueness, generic I/O, component binding, routing or throughput result exists."
        ),
        "ledger_effect": "none",
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if OUTPUT.exists():
        require(OUTPUT.read_text(encoding="utf-8") == encoded, "existing E086 check drift")
    else:
        OUTPUT.write_text(encoded, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "corrected_scope": payload["corrected_scope"],
                "new_front_rules": 64,
                "output_path": display(OUTPUT),
                "output_sha256": sha256(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
