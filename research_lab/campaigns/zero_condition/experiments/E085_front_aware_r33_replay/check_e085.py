#!/usr/bin/env python3
"""Independent artifact checker for E085's landed r33 replay."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
RUN = ROOT / "research_lab/local/zero_condition/E085_front_aware_r33_replay/run-001"
RESULT = RUN / "RESULT.json"
PRODUCER = RUN / "PRODUCER_RESULT.json"
CHECKPOINT = RUN / "CHECKPOINT.json"
FAILURE = RUN / "FAILURE.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
SOURCE_CHECKPOINT = (
    ROOT / "research_lab/local/zero_condition/E084_front_benders_checkpoint.json"
)

EXPECTED = {
    RESULT: "8602a20c26dcb37742ec85a70cb619e402302807523b7a5006fa501cb1bb9a68",
    PRODUCER: "fffeac99595cb3f3a0c2b18b4fa48c49e570dfb843ae457a7c825e866f53a449",
    CHECKPOINT: "0648bf057670c454d1c55a73417d127867c597063362407fe732c4a1b4c6ad9d",
    FAILURE: "2ae27570b1110ef4755bb679de4c4a82958d455f421ae8e0e817d15016150f99",
    SOURCE_CHECKPOINT: "0648bf057670c454d1c55a73417d127867c597063362407fe732c4a1b4c6ad9d",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def timestamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing artifact: {path}")
        require(sha256(path) == expected, f"artifact identity drift: {path}")

    result = load(RESULT)
    producer = load(PRODUCER)
    checkpoint = load(CHECKPOINT)
    source_checkpoint = load(SOURCE_CHECKPOINT)
    failure = load(FAILURE)

    require(result["verdict"] == "R33_REPLAY_CENSORED", "wrapper verdict drift")
    require(
        result["decision"]
        == "DO_NOT_ADVANCE_RUNG_SELECT_SOLVER_DIVERSE_REPLAY_OR_EXPLICIT_BUDGET_CHANGE",
        "wrapper decision drift",
    )
    controls = result["controls"]
    require(int(controls["target_retained_current_footprints"]) == 186, "retained target drift")
    require(int(controls["target_moved_manufacturing_count"]) == 33, "moved target drift")
    require(float(controls["master_seconds"]) == 250.0, "master cap drift")
    require(int(controls["max_iterations"]) == 1, "iteration cap drift")

    wrapper_producer = result["producer"]
    require(wrapper_producer["status"] == "UNKNOWN", "wrapper producer status drift")
    require(wrapper_producer["result_sha256"] == EXPECTED[PRODUCER], "nested producer hash drift")
    require(wrapper_producer["checkpoint_sha256"] == EXPECTED[CHECKPOINT], "nested checkpoint hash drift")
    require(int(wrapper_producer["registered_front_candidate_count"]) == 34, "front rule count drift")
    require(int(wrapper_producer["operation_nogood_count"]) == 0, "operation nogood drift")
    require(int(wrapper_producer["selected_manufacturing_count"]) == 0, "UNKNOWN carried selection")

    require(producer["status"] == "UNKNOWN", "producer terminal drift")
    require(int(producer["target_retained_current_footprints"]) == 186, "producer retained drift")
    require(int(producer["target_moved_manufacturing_count"]) == 33, "producer moved drift")
    records = list(producer["records"])
    require(len(records) == 1, "producer record count drift")
    require(records[0]["master_status"] == "UNKNOWN", "producer record status drift")
    require(float(records[0]["elapsed_seconds"]) >= 249.0, "producer did not consume declared cap")
    require(int(producer["registered_front_candidate_count"]) == 34, "producer front rules drift")
    require(int(producer["operation_nogood_count"]) == 0, "producer nogood drift")
    require("selected_manufacturing" not in producer, "UNKNOWN producer carried witness")

    require(checkpoint == source_checkpoint, "UNKNOWN replay mutated copied checkpoint")
    require(int(checkpoint["registered_front_candidate_count"]) == 34, "checkpoint front count drift")
    require(int(checkpoint["operation_nogood_count"]) == 0, "checkpoint nogood drift")

    require(failure["status"] == "EXECUTION_FAILURE", "duplicate invocation failure status drift")
    require(failure["error"] == "FileExistsError", "duplicate invocation error drift")
    require("refusing to reuse E085 run directory" in failure["detail"], "unexpected later failure")
    require(
        timestamp(failure["created_at_utc"]) > timestamp(result["created_at_utc"]),
        "duplicate invocation did not occur after valid result",
    )

    telemetry = result["telemetry"]
    events_before: Mapping[str, Any] = telemetry["cgroup_before"].get("memory_events") or {}
    events_after: Mapping[str, Any] = telemetry["cgroup_after"].get("memory_events") or {}
    oom_delta = int(events_after.get("oom", 0)) - int(events_before.get("oom", 0))
    oom_kill_delta = int(events_after.get("oom_kill", 0)) - int(events_before.get("oom_kill", 0))
    require(oom_delta == 0 and oom_kill_delta == 0, "E085 observed an OOM event")

    payload = {
        "schema": "zmd_e085_front_aware_r33_artifact_check_v1",
        "status": "PASS",
        "authority": "research_only_noncertified",
        "classification": "CENSORED_UNKNOWN_NO_WITNESS",
        "decision": result["decision"],
        "target_retained_current_footprints": 186,
        "target_moved_manufacturing_count": 33,
        "producer_status": "UNKNOWN",
        "producer_elapsed_seconds": float(records[0]["elapsed_seconds"]),
        "process_ru_maxrss_kib": int(telemetry["process_after"]["ru_maxrss_kib"]),
        "oom_event_delta": oom_delta,
        "oom_kill_event_delta": oom_kill_delta,
        "later_duplicate_invocation": {
            "status": "REJECTED_BY_NO_OVERWRITE",
            "failure_path": display(FAILURE),
            "failure_sha256": EXPECTED[FAILURE],
            "supersedes_valid_result": False,
        },
        "checked_artifacts": {
            display(path): {"sha256": expected, "size_bytes": path.stat().st_size}
            for path, expected in EXPECTED.items()
        },
        "truth_boundary": (
            "This checker establishes artifact identity and censorship only. The r33 "
            "model produced no incumbent and no infeasibility proof. Absence of OOM "
            "does not identify the cause of search failure."
        ),
        "ledger_effect": "none",
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if OUTPUT.exists():
        require(
            OUTPUT.read_text(encoding="utf-8") == encoded,
            "existing artifact check disagrees with fresh replay",
        )
    else:
        OUTPUT.write_text(encoded, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "classification": payload["classification"],
                "producer_status": payload["producer_status"],
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
