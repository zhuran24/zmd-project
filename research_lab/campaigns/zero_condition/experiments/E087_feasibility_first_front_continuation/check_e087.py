#!/usr/bin/env python3
"""Artifact and rule-growth checker for E087 run-001."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e087.py"
RUN = ROOT / "research_lab/local/zero_condition/E087_feasibility_first_front_continuation/run-001"
RESULT = RUN / "RESULT.json"
PRODUCER = RUN / "PRODUCER_RESULT.json"
CHECKPOINT = RUN / "CHECKPOINT.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
SOURCE_CHECKPOINT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E086_feasibility_first_front_proposer/run-001/CHECKPOINT.json"
)

EXPECTED = {
    RUNNER: "8ecc162b2e893a8db290544ed2632576dc7688a5c835bb611d3d631d386c0510",
    RESULT: "ff53ddd8311dd6c23d1785cee095d9611fd270f307d33d5b1323245d74b88460",
    PRODUCER: "5f692ce043bbf716f7825aab727edb2bcd1754626b83a49edec78a14774852c1",
    CHECKPOINT: "09c0c31d5874fe9689ecea7295be48edb3a765f0a605a475e44e5ef1a107d4e9",
    SOURCE_CHECKPOINT: "06cadbed6f61cb04c8c5445b778378bca336ddc2fa1f2f0804962c1ceb70933d",
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


def class_key(row: Mapping[str, Any]) -> tuple[str, str, tuple[tuple[int, int], ...]]:
    demands = tuple(
        (int(item["input_need"]), int(item["output_need"]))
        for item in row["demand_classes"]
    )
    return str(row["module"]), str(row["template"]), demands


def encode_counter(counter: Counter[tuple[str, str, tuple[tuple[int, int], ...]]]) -> dict[str, int]:
    return {
        f"{module}:{template}:"
        + "+".join(f"{inputs}i{outputs}o" for inputs, outputs in demands): int(count)
        for (module, template, demands), count in sorted(counter.items())
    }


def main() -> int:
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E087 artifact: {path}")
        require(sha256(path) == expected, f"E087 artifact identity drift: {path}")

    result = load(RESULT)
    producer = load(PRODUCER)
    checkpoint = load(CHECKPOINT)
    source_checkpoint = load(SOURCE_CHECKPOINT)

    require(result["verdict"] == "FRONT_CLOSURE_CONTINUES_TO_LEARN", "E087 verdict drift")
    require(
        result["decision"] == "REASSESS_RULE_GROWTH_AND_CONTINUE_OR_DECOMPOSE",
        "E087 decision drift",
    )
    require(producer["status"] == "ITERATION_LIMIT", "E087 producer status drift")
    require(producer["search_objective"] == "MAXIMIZE_RETAINED_CURRENT_FOOTPRINTS", "E087 objective drift")
    require(producer["fixed_retained_target"] is None, "E087 fixed retained target drift")
    require(int(producer["iteration_count"]) == 2, "E087 iteration count drift")
    require(int(producer["registered_front_candidate_count"]) == 181, "E087 front count drift")
    require(int(producer["operation_nogood_count"]) == 0, "E087 operation nogood drift")
    require("selected_manufacturing" not in producer, "E087 iteration-limit carried witness")

    records = list(producer["records"])
    require(len(records) == 2, "E087 record count drift")
    expected_records = (
        {
            "status": "FEASIBLE",
            "retained": 174,
            "bound": 185.0,
            "empty": 39,
            "new": 39,
            "total": 137,
            "boundary": "boundary_macro_39",
            "pole": "p_x59_y39_o0_m_omni",
        },
        {
            "status": "FEASIBLE",
            "retained": 165,
            "bound": 185.0,
            "empty": 44,
            "new": 44,
            "total": 181,
            "boundary": "boundary_macro_22",
            "pole": "p_x68_y56_o0_m_omni",
        },
    )
    new_indices: list[int] = []
    for row, expected in zip(records, expected_records, strict=True):
        require(row["master_status"] == expected["status"], "E087 master status drift")
        require(int(row["retained_current_footprints"]) == expected["retained"], "E087 retained drift")
        require(float(row["retained_best_bound"]) == expected["bound"], "E087 bound drift")
        require(row["operation_checker_status"] == "EMPTY_DOMAIN", "E087 checker status drift")
        require(int(row["operation_checker_empty_count"]) == expected["empty"], "E087 empty count drift")
        require(len(row["newly_registered_front_candidates"]) == expected["new"], "E087 new-rule count drift")
        require(int(row["registered_front_candidate_count"]) == expected["total"], "E087 cumulative count drift")
        require(row["selected_boundary_state_id"] == expected["boundary"], "E087 boundary drift")
        require(row["selected_replacement_pole"] == expected["pole"], "E087 pole drift")
        new_indices.extend(map(int, row["newly_registered_front_candidates"]))
    require(len(new_indices) == 83 and len(set(new_indices)) == 83, "E087 new-rule identity drift")

    source_stats = source_checkpoint["front_rule_stats"]
    final_stats = checkpoint["front_rule_stats"]
    source_rules = set(map(int, source_stats))
    final_rules = set(map(int, final_stats))
    require(len(source_rules) == 98, "E087 source rule count drift")
    require(len(final_rules) == 181, "E087 final rule count drift")
    require(final_rules - source_rules == set(new_indices), "E087 checkpoint growth mismatch")
    require(checkpoint["terminal"] == "ITERATION_LIMIT", "E087 checkpoint terminal drift")
    require(int(checkpoint["operation_nogood_count"]) == 0, "E087 checkpoint nogood drift")

    new_rows = [final_stats[str(index)] for index in sorted(final_rules - source_rules)]
    require(all(str(row["module"]) == "B" for row in new_rows), "E087 new rules are not all module B")
    source_a = sum(str(row["module"]) == "A" for row in source_stats.values())
    final_a = sum(str(row["module"]) == "A" for row in final_stats.values())
    require(source_a == 3 and final_a == 3, "E087 module-A rule count changed")

    final_classes = Counter(class_key(row) for row in final_stats.values())
    expected_classes = Counter(
        {
            ("B", "manufacturing_3x3", ((1, 1),)): 85,
            ("B", "manufacturing_6x4", ((3, 1),)): 67,
            ("B", "manufacturing_5x5", ((1, 1),)): 25,
            ("A", "manufacturing_5x5", ((1, 1),)): 2,
            ("B", "manufacturing_6x4", ((4, 1),)): 1,
            ("A", "manufacturing_6x4", ((3, 1),)): 1,
        }
    )
    require(final_classes == expected_classes, f"E087 class census drift: {final_classes}")

    before_events: Mapping[str, Any] = result["telemetry"]["cgroup_before"].get("memory_events") or {}
    after_events: Mapping[str, Any] = result["telemetry"]["cgroup_after"].get("memory_events") or {}
    oom_delta = int(after_events.get("oom", 0)) - int(before_events.get("oom", 0))
    oom_kill_delta = int(after_events.get("oom_kill", 0)) - int(before_events.get("oom_kill", 0))
    require(oom_delta == 0 and oom_kill_delta == 0, "E087 observed an OOM event")

    payload = {
        "schema": "zmd_e087_front_continuation_artifact_check_v1",
        "status": "PASS",
        "authority": "research_only_noncertified",
        "scientific_result": {
            "producer_status": "ITERATION_LIMIT",
            "front_operation_witness": False,
            "initial_front_rule_count": 98,
            "final_front_rule_count": 181,
            "new_front_rule_count": 83,
            "new_rules_all_module_b": True,
            "module_a_rule_count_before": 3,
            "module_a_rule_count_after": 3,
            "operation_nogood_count": 0,
            "candidate_retained_counts": [174, 165],
            "candidate_best_bounds": [185.0, 185.0],
            "candidate_empty_domain_counts": [39, 44],
            "final_rule_class_counts": encode_counter(final_classes),
        },
        "interpretation": {
            "empty_domain_count_improved_over_e086_last_candidate": False,
            "point_rule_growth_remains_large": True,
            "front_wall_localizes_to_module_b": True,
            "recommended_next_discriminator": (
                "exactly census the complete module-B candidate universe by canonical "
                "front-rule signature and measure whether the 178 registered B rules "
                "concentrate in a small signature family before another lazy solve"
            ),
        },
        "decision": "STOP_BLIND_LAZY_CONTINUATION_AND_BUILD_MODULE_B_RULE_SIGNATURE_ATLAS",
        "telemetry": {
            "elapsed_seconds": float(result["telemetry"]["elapsed_seconds"]),
            "process_ru_maxrss_kib": int(result["telemetry"]["process_after"]["ru_maxrss_kib"]),
            "oom_event_delta": oom_delta,
            "oom_kill_event_delta": oom_kill_delta,
        },
        "checked_artifacts": {
            display(path): {"sha256": expected, "size_bytes": path.stat().st_size}
            for path, expected in EXPECTED.items()
        },
        "truth_boundary": (
            "E087 does not prove lazy closure cannot converge. It shows that two more "
            "iterations add 83 entirely module-B candidate rules while empty-domain "
            "counts remain 39 and 44. This is sufficient to stop unexamined repetition "
            "and run a rule-language compression discriminator, not to refute the "
            "one-replacement language or the partition."
        ),
        "ledger_effect": "none",
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if OUTPUT.exists():
        require(OUTPUT.read_text(encoding="utf-8") == encoded, "existing E087 check drift")
    else:
        OUTPUT.write_text(encoded, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"],
                "new_front_rules": 83,
                "new_rules_all_module_b": True,
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
