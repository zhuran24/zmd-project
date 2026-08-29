#!/usr/bin/env python3
"""Independent artifact checks for E090's censored three-pole discriminator."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e090.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E090_three_pole_front_discriminator/run-001"
)
RESULT = RUN / "RESULT.json"
PRODUCER = RUN / "PRODUCER_RESULT.json"
DERIVATION = RUN / "DERIVATION.json"
DERIVED = RUN / "DERIVED_PRODUCER.py"
OUTPUT = RUN / "ARTIFACT_CHECK.json"

EXPECTED = {
    RUNNER: "0fa1ccf6e0dba1118a4824d6395893a30283120b8526aaeb559481b259cd0db6",
    RESULT: "ff5398ee4064f01ded8d4b91d2ddc832fe52dceb4197c63dcad081bf52d89496",
    PRODUCER: "1a3725d8757fb055f85a04cc229e7ca3685bd21fd448ea0825fbd54da08329db",
    DERIVATION: "17e9f60551ebd751b609c8277eda1d54a1f46a1e499baa938f283b9ce03d556a",
    DERIVED: "93471f93743d15dc2835c7e1c5a0637a219942e2aab6c4e77c4dcf4828cde0fb",
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


def event_delta(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    key: str,
) -> int | None:
    if before is None or after is None:
        return None
    if key not in before or key not in after:
        return None
    return int(after[key]) - int(before[key])


def main() -> int:
    require(not OUTPUT.exists(), "refusing to overwrite E090 artifact check")
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E090 artifact: {path}")
        require(sha256(path) == expected, f"E090 artifact identity drift: {path}")

    result = load(RESULT)
    producer = load(PRODUCER)
    derivation = load(DERIVATION)

    require(
        result.get("verdict") == "THREE_POLE_FRONT_DISCRIMINATOR_CENSORED",
        "E090 wrapper verdict drift",
    )
    require(
        result.get("decision")
        == "MOVE_IDENTICAL_THREE_POLE_CONSUMER_TO_NEXT_E081_PARETO_PARTITION_AS_CONTROL",
        "E090 wrapper decision drift",
    )
    require(result["controls"]["max_relocated_poles"] == 3, "E090 pole cap drift")
    require(
        result["controls"]["minimum_retained_current_poles"] == 50,
        "E090 retained-pole floor drift",
    )
    require(result["controls"]["pure_feasibility"] is True, "E090 objective drift")
    require(
        result["controls"]["stop_after_first_solution"] is True,
        "E090 first-solution control drift",
    )

    require(producer.get("status") == "UNKNOWN", "E090 producer status drift")
    require(
        producer.get("solver_status") == "UNKNOWN",
        "E090 solver status drift",
    )
    require(
        int(producer.get("max_relocated_poles", -1)) == 3,
        "E090 producer pole cap drift",
    )
    require(
        int(producer.get("minimum_retained_current_poles", -1)) == 50,
        "E090 producer retained-pole floor drift",
    )
    require(
        int(producer.get("body_candidate_count", -1)) == 14867,
        "E090 body candidate count drift",
    )
    require(
        int(producer.get("pole_candidate_count", -1)) == 4316,
        "E090 pole candidate count drift",
    )
    require(
        int(producer.get("mode_class_variable_count", -1)) == 92188,
        "E090 mode-class count drift",
    )
    require(
        int(producer.get("model_variable_count", -1)) == 116318,
        "E090 model variable count drift",
    )
    require(
        int(producer.get("model_constraint_count", -1)) == 223719,
        "E090 model constraint count drift",
    )
    require(
        not producer.get("selected_manufacturing"),
        "E090 UNKNOWN unexpectedly carries manufacturing witness",
    )
    require(
        not producer.get("selected_poles"),
        "E090 UNKNOWN unexpectedly carries pole witness",
    )

    changes = derivation.get("semantic_changes", {})
    require(changes.get("same_y41_partition") is True, "E090 y41 identity drift")
    require(
        changes.get("complete_boundary_disjunction") is True,
        "E090 boundary language drift",
    )
    require(
        changes.get("same_body_front_class_semantics") is True,
        "E090 front semantics drift",
    )
    require(changes.get("same_power_semantics") is True, "E090 power drift")
    require(
        changes.get("pole_language") == "exactly_53_at_least_50_current",
        "E090 pole-language derivation drift",
    )
    require(changes.get("objective_removed") is True, "E090 objective removal drift")

    derived_source = DERIVED.read_text(encoding="utf-8")
    compile(derived_source, str(DERIVED), "exec")
    require(
        "sum(current_pole_vars)" in derived_source
        and ">= EXPECTED_POLE_COUNT - MAX_RELOCATED_POLES" in derived_source,
        "E090 derived pole budget missing",
    )
    require(
        "solver.parameters.stop_after_first_solution = True" in derived_source,
        "E090 first-solution control missing",
    )
    require("model.Maximize(" not in derived_source, "E090 objective still present")

    telemetry = result["telemetry"]
    before_events = telemetry["cgroup_before"].get("memory_events")
    after_events = telemetry["cgroup_after"].get("memory_events")
    oom_delta = event_delta(before_events, after_events, "oom")
    oom_kill_delta = event_delta(before_events, after_events, "oom_kill")
    require(oom_delta in (None, 0), f"E090 OOM counter increased: {oom_delta}")
    require(
        oom_kill_delta in (None, 0),
        f"E090 OOM-kill counter increased: {oom_kill_delta}",
    )
    require(
        int(telemetry["process_after"]["ru_maxrss_kib"]) >= 8_000_000,
        "E090 peak RSS unexpectedly low",
    )

    payload = {
        "schema": "zmd_e090_three_pole_front_artifact_check_v1",
        "status": "PASS",
        "classification": "CENSORED_UNKNOWN_NO_WITNESS",
        "verdict": result["verdict"],
        "decision": result["decision"],
        "producer_status": producer["status"],
        "solve_seconds": result["controls"]["solve_seconds"],
        "elapsed_seconds": producer["elapsed_seconds"],
        "branches": producer["branches"],
        "conflicts": producer["conflicts"],
        "ru_maxrss_kib": telemetry["process_after"]["ru_maxrss_kib"],
        "oom_delta": oom_delta,
        "oom_kill_delta": oom_kill_delta,
        "selected_manufacturing_count": 0,
        "selected_pole_count": 0,
        "truth_boundary": (
            "Artifact and derivation replay only. UNKNOWN remains censored and "
            "establishes no infeasibility or witness."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "classification": payload["classification"],
                "producer_status": payload["producer_status"],
                "ru_maxrss_kib": payload["ru_maxrss_kib"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256(OUTPUT),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
