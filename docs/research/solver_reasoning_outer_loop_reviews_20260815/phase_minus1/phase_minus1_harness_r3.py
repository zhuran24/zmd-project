#!/usr/bin/env python3
"""Compact-journal Phase -1 harness.

The frozen Phase -1 protocol is unchanged.  This revision removes the r2
observer effect by using:

* a tiny atomic progress snapshot;
* append-only compact event JSONL;
* append-only feedback JSONL.

The actual consumer remains a full binding-selection nogood.  Local blocked-port
signatures are recorded only as uncompiled diagnostic family candidates.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import phase_minus1_harness as base  # noqa: E402

HARNESS_REVISION = "r3_compact_append_only_journals_v1"
PROGRESS_EVERY_N_FEEDBACKS = 10
LOCAL_SIGNATURE_EXAMPLE_LIMIT = 8


class CompactJournal:
    """Append JSON records with one kernel write per line."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
        self.count = 0

    def append(self, payload: Mapping[str, Any]) -> None:
        encoded = (
            json.dumps(
                base._json_safe(payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        written = os.write(self._fd, encoded)
        if written != len(encoded):
            raise OSError(f"short journal write: expected {len(encoded)}, wrote {written}")
        self.count += 1

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> CompactJournal:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb
        self.close()


@dataclass(frozen=True)
class JournalRead:
    records: tuple[Mapping[str, Any], ...]
    truncated_tail: bool
    malformed_complete_line: str | None


def _read_jsonl(path: Path) -> JournalRead:
    if not path.is_file():
        return JournalRead((), False, None)
    raw = path.read_bytes()
    truncated_tail = bool(raw and not raw.endswith(b"\n"))
    lines = raw.splitlines(keepends=True)
    records: list[Mapping[str, Any]] = []
    malformed: str | None = None
    for index, raw_line in enumerate(lines):
        complete = raw_line.endswith(b"\n")
        if not complete and index == len(lines) - 1:
            continue
        try:
            parsed = json.loads(raw_line.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            malformed = f"line {index + 1}: {type(exc).__name__}: {exc}"
            break
        if not isinstance(parsed, Mapping):
            malformed = f"line {index + 1}: record is not an object"
            break
        records.append(parsed)
    return JournalRead(tuple(records), truncated_tail, malformed)


def _journal_summary(path: Path) -> dict[str, Any]:
    read = _read_jsonl(path)
    return {
        "path": str(path),
        "sha256": base._sha256_file(path) if path.is_file() else None,
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "complete_record_count": len(read.records),
        "truncated_tail": read.truncated_tail,
        "malformed_complete_line": read.malformed_complete_line,
    }


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compact_progress(
    *,
    layout: base.LayoutInput,
    stage: str,
    started: float,
    counters: Mapping[str, int],
    timings: Mapping[str, float],
    event_count: int,
    feedback_record_count: int,
    last_event: Mapping[str, Any] | None = None,
    last_status: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_progress_v2",
        "research_only": True,
        "harness_revision": HARNESS_REVISION,
        "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
        "layout_id": layout.record["id"],
        "stratum": layout.record["stratum"],
        "split": layout.record["role"],
        "normalized_sha256": layout.normalized_sha256,
        "stage": stage,
        "elapsed_wall_seconds": time.perf_counter() - started,
        "updated_at_utc": _now_utc(),
        "counters": dict(counters),
        "timings": dict(timings),
        "event_record_count": event_count,
        "feedback_record_count": feedback_record_count,
    }
    if last_event is not None:
        payload["last_event"] = dict(last_event)
    if last_status is not None:
        payload["last_status"] = last_status
    return payload


def _write_progress(
    path: Path,
    *,
    layout: base.LayoutInput,
    stage: str,
    started: float,
    counters: Mapping[str, int],
    timings: Mapping[str, float],
    event_count: int,
    feedback_record_count: int,
    last_event: Mapping[str, Any] | None = None,
    last_status: str | None = None,
) -> None:
    base._write_json(
        path,
        _compact_progress(
            layout=layout,
            stage=stage,
            started=started,
            counters=counters,
            timings=timings,
            event_count=event_count,
            feedback_record_count=feedback_record_count,
            last_event=last_event,
            last_status=last_status,
        ),
    )


def _instance_facility_type(layout: base.LayoutInput, instance_id: str) -> str:
    entry = layout.solution.get(instance_id)
    if isinstance(entry, Mapping) and entry.get("facility_type"):
        return str(entry["facility_type"])
    if instance_id.startswith("pose_optional::"):
        parts = instance_id.split("::")
        if len(parts) >= 2:
            return parts[1]
    if instance_id == base.GHOST_RESERVED_OWNER_ID:
        return "ghost_rect"
    return "UNKNOWN"


def _instance_anchor(
    layout: base.LayoutInput,
    instance_id: str,
) -> tuple[int, int] | None:
    entry = layout.solution.get(instance_id)
    if not isinstance(entry, Mapping):
        return None
    anchor = entry.get("anchor")
    if not isinstance(anchor, Mapping):
        return None
    try:
        return int(anchor["x"]), int(anchor["y"])
    except Exception:
        return None


def _local_signature(
    layout: base.LayoutInput,
    *,
    subject_id: str,
    blocker_id: str,
    direction: str,
) -> str:
    subject_type = _instance_facility_type(layout, subject_id)
    blocker_type = _instance_facility_type(layout, blocker_id)
    subject_anchor = _instance_anchor(layout, subject_id)
    blocker_anchor = _instance_anchor(layout, blocker_id)
    if subject_anchor is None or blocker_anchor is None:
        relative = "NA"
    else:
        relative = (
            f"{blocker_anchor[0] - subject_anchor[0]},"
            f"{blocker_anchor[1] - subject_anchor[1]}"
        )
    return f"{subject_type}|{blocker_type}|{direction}|{relative}"


def _compact_blocked_precheck(
    *,
    layout: base.LayoutInput,
    selection: Mapping[str, Any],
    precheck: Mapping[str, Any],
    replay: Mapping[str, Any],
    event_index: int,
) -> dict[str, Any]:
    blocked_ports = precheck.get("blocked_ports", [])
    if not isinstance(blocked_ports, list):
        blocked_ports = []
    signature_counts: Counter[str] = Counter()
    commodity_counts: Counter[str] = Counter()
    conflict_union: set[str] = set()
    compact_examples: list[dict[str, Any]] = []

    sorted_ports = sorted(
        (item for item in blocked_ports if isinstance(item, Mapping)),
        key=lambda item: (
            str(item.get("instance_id", "")),
            str(item.get("dir", "")),
            str(item.get("commodity", "")),
            tuple(item.get("front_cell", []) or []),
        ),
    )
    for item in sorted_ports:
        subject_id = str(item.get("instance_id", ""))
        direction = str(item.get("dir", ""))
        commodity_counts[str(item.get("commodity", ""))] += 1
        blockers = sorted(str(value) for value in item.get("blocking_instance_ids", []))
        for blocker_id in blockers:
            conflict_union.add(subject_id)
            conflict_union.add(blocker_id)
            signature_counts[
                _local_signature(
                    layout,
                    subject_id=subject_id,
                    blocker_id=blocker_id,
                    direction=direction,
                )
            ] += 1
        if len(compact_examples) < LOCAL_SIGNATURE_EXAMPLE_LIMIT:
            compact_examples.append(
                {
                    "instance_id": subject_id,
                    "facility_type": _instance_facility_type(layout, subject_id),
                    "direction": direction,
                    "commodity": str(item.get("commodity", "")),
                    "front_cell": list(item.get("front_cell", []) or []),
                    "blocking_instance_ids": blockers,
                    "blocking_facility_types": [
                        _instance_facility_type(layout, blocker_id)
                        for blocker_id in blockers
                    ],
                }
            )

    signature_payload = dict(sorted(signature_counts.items()))
    replay_projection = base._precheck_projection(replay)
    precheck_projection = base._precheck_projection(precheck)
    replay_status = (
        "REPLAYED_IDENTICAL"
        if replay_projection == precheck_projection
        else "REPLAY_MISMATCH"
    )
    support_status = (
        "AVAILABLE_REPLAYED"
        if conflict_union and replay_status == "REPLAYED_IDENTICAL"
        else "AVAILABLE_NOT_REPLAYED"
        if conflict_union
        else "UNAVAILABLE"
    )
    precheck_status = str(precheck.get("status", ""))
    reason = (
        "routing_front_blocked"
        if precheck_status == "front_blocked"
        else "routing_relaxed_disconnected"
    )
    diagnostic_form = (
        "local_blocked_port_conflict_family_candidate"
        if precheck_status == "front_blocked"
        else "commodity_disconnection_family_candidate"
    )
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_event_v2",
        "record_type": "routing_precheck_failure",
        "event_index": event_index,
        "layout_id": layout.record["id"],
        "selection_digest": base._selection_digest(selection),
        "reason": reason,
        "gateSide": "routing_precheck",
        "feedbackForm": "point_nogood",
        "diagnosticCandidateForm": diagnostic_form,
        "eventCensorStatus": "UNCENSORED",
        "familyKey": f"{reason}|routing_precheck|point_nogood|UNCENSORED",
        "supportCoreStatus": support_status,
        "diagnosticReplayStatus": replay_status,
        "binding_selection_safe_reject": bool(
            precheck.get("binding_selection_safe_reject", False)
        ),
        "blocked_port_count": len(sorted_ports),
        "placement_conflict_union_size": len(conflict_union),
        "local_signature_count": len(signature_payload),
        "local_signature_counts": signature_payload,
        "local_signature_digest": base._canonical_digest(signature_payload),
        "commodity_counts": dict(sorted(commodity_counts.items())),
        "domain_stats": dict(precheck.get("domain_stats", {})),
        "examples": compact_examples,
    }


def _compact_routing_event(
    *,
    layout: base.LayoutInput,
    selection: Mapping[str, Any],
    routing_status: str,
    event_index: int,
    route_model: Any,
) -> dict[str, Any]:
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_event_v2",
        "record_type": "routing_solve_failure",
        "event_index": event_index,
        "layout_id": layout.record["id"],
        "selection_digest": base._selection_digest(selection),
        "reason": (
            "routing_model_infeasible"
            if routing_status == "INFEASIBLE"
            else "routing_solver_timeout"
        ),
        "gateSide": "routing_solve",
        "feedbackForm": "point_nogood" if routing_status == "INFEASIBLE" else "none",
        "diagnosticCandidateForm": "none",
        "eventCensorStatus": (
            "UNCENSORED" if routing_status == "INFEASIBLE" else "SOLVER_TIMEOUT_ROUTING"
        ),
        "familyKey": (
            "routing_model_infeasible|routing_solve|point_nogood|UNCENSORED"
            if routing_status == "INFEASIBLE"
            else "routing_solver_timeout|routing_solve|none|SOLVER_TIMEOUT_ROUTING"
        ),
        "supportCoreStatus": "UNAVAILABLE",
        "diagnosticReplayStatus": None,
        "routing_build_stats": dict(route_model.build_stats),
    }


def _feedback_applied_record(
    *,
    feedback_id: str,
    layout: base.LayoutInput,
    selection: Mapping[str, Any],
    producer: str,
    model: base.PortBindingModel,
    event_index: int,
) -> dict[str, Any]:
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_feedback_v2",
        "record_type": "feedback_applied",
        "feedback_id": feedback_id,
        "layout_id": layout.record["id"],
        "event_index": event_index,
        "producer": producer,
        "registry_status": "REGISTERED",
        "resolver_status": "RESOLVED",
        "consumer_status": "APPLIED",
        "scope": "current_fixed_layout_and_current_binding_selection",
        "feedbackForm": "point_nogood",
        "selection_digest": base._selection_digest(selection),
        "literal_count": base._selection_literal_count(model, selection),
    }


def _feedback_outcome_record(
    *,
    applied: Mapping[str, Any],
    next_status: str,
    next_selection: Mapping[str, Any] | None,
) -> dict[str, Any]:
    before_digest = str(applied["selection_digest"])
    after_digest = (
        base._selection_digest(next_selection) if next_selection is not None else None
    )
    effect = int(applied.get("literal_count", 0)) > 0 and (
        after_digest is None or after_digest != before_digest
    )
    if not effect:
        failure_class = "REACHED_NO_EFFECT"
        terminal_outcome = None
    elif next_status == "INFEASIBLE":
        failure_class = None
        terminal_outcome = "INFEASIBLE"
    else:
        failure_class = "EFFECT_NO_TERMINAL"
        terminal_outcome = None
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_feedback_v2",
        "record_type": "feedback_outcome",
        "feedback_id": applied["feedback_id"],
        "layout_id": applied["layout_id"],
        "event_index": applied["event_index"],
        "next_status": next_status,
        "next_selection_digest": after_digest,
        "effect": effect,
        "reachabilityFailureClass": failure_class,
        "terminalOutcome": terminal_outcome,
    }


def _compact_binding_summary(model: base.PortBindingModel) -> dict[str, Any]:
    summary = model.extract_conflict_summary()
    empty_domains = model.extract_empty_binding_domain_instances()
    return {
        "empty_binding_domain_instances": list(empty_domains),
        "summary_digest": base._canonical_digest(base._json_safe(summary)),
        "summary_top_level_keys": sorted(str(key) for key in summary),
    }


def _layout_receipt(
    *,
    layout: base.LayoutInput,
    terminal_status: str,
    censor_status: str,
    final_reason: str,
    started: float,
    counters: Mapping[str, int],
    timings: Mapping[str, float],
    progress_path: Path,
    event_path: Path,
    feedback_path: Path,
    binding_summary: Mapping[str, Any],
    watchdog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v2",
        "research_only": True,
        "harness_revision": HARNESS_REVISION,
        "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
        "repository_head": base._git("rev-parse", "HEAD"),
        "layout_id": layout.record["id"],
        "stratum": layout.record["stratum"],
        "split": layout.record["role"],
        "normalized_sha256": layout.normalized_sha256,
        "pose_id_remaps": layout.pose_id_remaps,
        "ghost_rect": list(layout.ghost_rect),
        "ghost_source_receipt": layout.ghost_source_receipt,
        "source_identity_receipt": layout.source_identity_receipt,
        "terminalStatus": terminal_status,
        "censorStatus": censor_status,
        "finalReason": final_reason,
        "counters": dict(counters),
        "timings": dict(timings),
        "total_wall_seconds": time.perf_counter() - started,
        "progress_receipt": {
            "path": str(progress_path),
            "sha256": base._sha256_file(progress_path) if progress_path.is_file() else None,
        },
        "event_journal": _journal_summary(event_path),
        "feedback_journal": _journal_summary(feedback_path),
        "binding_summary": dict(binding_summary),
        "watchdog": dict(watchdog) if watchdog is not None else None,
        "solver_contract": {
            "binding_seconds": base.BINDING_SECONDS,
            "routing_seconds": base.ROUTING_SECONDS,
            "binding_workers": base.BINDING_WORKERS,
            "routing_workers": base.ROUTING_WORKERS,
            "cp_sat_random_seed": base.CP_SAT_RANDOM_SEED,
            "alternative_count_cap": None,
        },
    }


def _run_layout(
    layout: base.LayoutInput,
    frozen: base.FrozenInputs,
    *,
    progress_path: Path,
    event_path: Path,
    feedback_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    counters = {
        "binding_proposals": 0,
        "binding_solves": 0,
        "routing_prechecks": 0,
        "routing_solves": 0,
        "binding_routing_round_trips": 0,
    }
    timings = {
        "occupancy_build_seconds": 0.0,
        "binding_build_seconds": 0.0,
        "binding_solve_seconds": 0.0,
        "routing_precheck_seconds": 0.0,
        "routing_build_seconds": 0.0,
        "routing_solve_seconds": 0.0,
        "journal_seconds": 0.0,
        "progress_write_seconds": 0.0,
    }
    event_count = 0
    feedback_record_count = 0
    last_event_compact: dict[str, Any] | None = None

    progress_started = time.perf_counter()
    _write_progress(
        progress_path,
        layout=layout,
        stage="occupancy_build_started",
        started=started,
        counters=counters,
        timings=timings,
        event_count=event_count,
        feedback_record_count=feedback_record_count,
    )
    timings["progress_write_seconds"] += time.perf_counter() - progress_started

    stage_started = time.perf_counter()
    core = base._occupied_core(layout, frozen)
    timings["occupancy_build_seconds"] += time.perf_counter() - stage_started

    progress_started = time.perf_counter()
    _write_progress(
        progress_path,
        layout=layout,
        stage="binding_build_started",
        started=started,
        counters=counters,
        timings=timings,
        event_count=event_count,
        feedback_record_count=feedback_record_count,
    )
    timings["progress_write_seconds"] += time.perf_counter() - progress_started

    stage_started = time.perf_counter()
    model = base._new_binding_model(layout, frozen)
    timings["binding_build_seconds"] += time.perf_counter() - stage_started
    binding_summary = _compact_binding_summary(model)

    progress_started = time.perf_counter()
    _write_progress(
        progress_path,
        layout=layout,
        stage="binding_build_finished",
        started=started,
        counters=counters,
        timings=timings,
        event_count=event_count,
        feedback_record_count=feedback_record_count,
    )
    timings["progress_write_seconds"] += time.perf_counter() - progress_started

    terminal_status = "UNKNOWN"
    censor_status = "UNCENSORED"
    final_reason = "unknown_other"
    pending_feedback: MutableMapping[str, Any] | None = None

    with CompactJournal(event_path) as event_journal, CompactJournal(
        feedback_path
    ) as feedback_journal:
        while True:
            if counters["binding_solves"] % PROGRESS_EVERY_N_FEEDBACKS == 0:
                progress_started = time.perf_counter()
                _write_progress(
                    progress_path,
                    layout=layout,
                    stage="binding_solve_started",
                    started=started,
                    counters=counters,
                    timings=timings,
                    event_count=event_journal.count,
                    feedback_record_count=feedback_journal.count,
                    last_event=last_event_compact,
                )
                timings["progress_write_seconds"] += time.perf_counter() - progress_started

            solve_started = time.perf_counter()
            binding_status = str(model.solve(base.BINDING_SECONDS))
            timings["binding_solve_seconds"] += time.perf_counter() - solve_started
            counters["binding_solves"] += 1

            if pending_feedback is not None:
                next_selection = (
                    model.extract_selection() if binding_status == "FEASIBLE" else None
                )
                outcome = _feedback_outcome_record(
                    applied=pending_feedback,
                    next_status=binding_status,
                    next_selection=next_selection,
                )
                journal_started = time.perf_counter()
                feedback_journal.append(outcome)
                timings["journal_seconds"] += time.perf_counter() - journal_started
                feedback_record_count = feedback_journal.count
                pending_feedback = None

            if binding_status == "FEASIBLE":
                counters["binding_proposals"] += 1
                selection = model.extract_selection()
                port_specs = model.extract_port_specs()
                counters["routing_prechecks"] += 1
                pre_started = time.perf_counter()
                precheck = base.run_exact_routing_precheck(
                    placement_core=core,
                    port_specs=port_specs,
                )
                replay = base.run_exact_routing_precheck(
                    placement_core=core,
                    port_specs=port_specs,
                )
                timings["routing_precheck_seconds"] += time.perf_counter() - pre_started
                precheck_status = str(precheck.get("status", ""))

                if precheck_status in base.ROUTING_DOMAIN_PROOF_REJECT_STATUSES:
                    if not bool(precheck.get("binding_selection_safe_reject", False)):
                        raise base.ProtocolViolation(
                            f"precheck {precheck_status} did not authorize selection reject"
                        )
                    event_count += 1
                    compact_event = _compact_blocked_precheck(
                        layout=layout,
                        selection=selection,
                        precheck=precheck,
                        replay=replay,
                        event_index=event_count,
                    )
                    journal_started = time.perf_counter()
                    event_journal.append(compact_event)
                    timings["journal_seconds"] += time.perf_counter() - journal_started
                    last_event_compact = {
                        "event_index": event_count,
                        "familyKey": compact_event["familyKey"],
                        "blocked_port_count": compact_event["blocked_port_count"],
                        "placement_conflict_union_size": compact_event[
                            "placement_conflict_union_size"
                        ],
                        "local_signature_digest": compact_event[
                            "local_signature_digest"
                        ],
                    }
                    feedback_id = f"{layout.record['id']}:{event_count}"
                    applied = _feedback_applied_record(
                        feedback_id=feedback_id,
                        layout=layout,
                        selection=selection,
                        producer=f"routing_precheck:{precheck_status}",
                        model=model,
                        event_index=event_count,
                    )
                    model.add_nogood_cut(dict(selection))
                    journal_started = time.perf_counter()
                    feedback_journal.append(applied)
                    timings["journal_seconds"] += time.perf_counter() - journal_started
                    feedback_record_count = feedback_journal.count
                    pending_feedback = applied
                    counters["binding_routing_round_trips"] += 1
                    if counters["binding_routing_round_trips"] % PROGRESS_EVERY_N_FEEDBACKS == 0:
                        progress_started = time.perf_counter()
                        _write_progress(
                            progress_path,
                            layout=layout,
                            stage="organic_feedback_applied",
                            started=started,
                            counters=counters,
                            timings=timings,
                            event_count=event_journal.count,
                            feedback_record_count=feedback_journal.count,
                            last_event=last_event_compact,
                        )
                        timings["progress_write_seconds"] += (
                            time.perf_counter() - progress_started
                        )
                    continue

                if precheck_status != base.ROUTING_DOMAIN_STATUS_FEASIBLE:
                    raise base.ProtocolViolation(
                        f"unexpected routing precheck status: {precheck_status!r}"
                    )

                commodities = sorted(
                    {
                        str(spec["commodity"])
                        for spec in port_specs
                        if str(spec.get("commodity", ""))
                    }
                )
                route_model = base.RoutingSubproblem.from_placement_core(
                    core,
                    port_specs,
                    commodities,
                    domain_analysis=precheck["_analysis"],
                )
                route_build_started = time.perf_counter()
                route_model.build()
                timings["routing_build_seconds"] += (
                    time.perf_counter() - route_build_started
                )
                counters["routing_solves"] += 1
                progress_started = time.perf_counter()
                _write_progress(
                    progress_path,
                    layout=layout,
                    stage="routing_solve_started",
                    started=started,
                    counters=counters,
                    timings=timings,
                    event_count=event_journal.count,
                    feedback_record_count=feedback_journal.count,
                    last_event=last_event_compact,
                )
                timings["progress_write_seconds"] += time.perf_counter() - progress_started
                route_solve_started = time.perf_counter()
                routing_status = str(route_model.solve(base.ROUTING_SECONDS))
                timings["routing_solve_seconds"] += (
                    time.perf_counter() - route_solve_started
                )

                if routing_status == "FEASIBLE":
                    terminal_status = "FEASIBLE"
                    final_reason = "layout_feasible"
                    event_count += 1
                    terminal_event = {
                        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_event_v2",
                        "record_type": "layout_feasible",
                        "event_index": event_count,
                        "layout_id": layout.record["id"],
                        "reason": "layout_feasible",
                        "gateSide": "terminal",
                        "feedbackForm": "none",
                        "eventCensorStatus": "UNCENSORED",
                        "familyKey": "layout_feasible|terminal|none|UNCENSORED",
                        "route_count": len(route_model.extract_routes()),
                    }
                    event_journal.append(terminal_event)
                    break

                event_count += 1
                route_event = _compact_routing_event(
                    layout=layout,
                    selection=selection,
                    routing_status=routing_status,
                    event_index=event_count,
                    route_model=route_model,
                )
                event_journal.append(route_event)
                last_event_compact = {
                    "event_index": event_count,
                    "familyKey": route_event["familyKey"],
                }
                if routing_status == "INFEASIBLE":
                    feedback_id = f"{layout.record['id']}:{event_count}"
                    applied = _feedback_applied_record(
                        feedback_id=feedback_id,
                        layout=layout,
                        selection=selection,
                        producer="routing_solve:INFEASIBLE",
                        model=model,
                        event_index=event_count,
                    )
                    model.add_nogood_cut(dict(selection))
                    feedback_journal.append(applied)
                    pending_feedback = applied
                    counters["binding_routing_round_trips"] += 1
                    continue

                terminal_status = "UNKNOWN"
                censor_status = "SOLVER_TIMEOUT_ROUTING"
                final_reason = (
                    "routing_connectivity_guard_timeout"
                    if str(route_model.build_stats.get("last_solve", {}).get("status", ""))
                    == "CONNECTIVITY_GUARD_TIMEOUT"
                    else "routing_solver_timeout"
                )
                break

            if binding_status == "INFEASIBLE":
                terminal_status = "INFEASIBLE"
                empty_domains = model.extract_empty_binding_domain_instances()
                final_reason = (
                    "binding_empty_domain" if empty_domains else "binding_exhausted"
                )
                event_count += 1
                event_journal.append(
                    {
                        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_event_v2",
                        "record_type": "binding_terminal",
                        "event_index": event_count,
                        "layout_id": layout.record["id"],
                        "reason": final_reason,
                        "gateSide": "binding_solve",
                        "feedbackForm": "none",
                        "eventCensorStatus": "UNCENSORED",
                        "familyKey": f"{final_reason}|binding_solve|none|UNCENSORED",
                        "supportCoreStatus": (
                            "AVAILABLE_NOT_REPLAYED" if empty_domains else "UNAVAILABLE"
                        ),
                        "empty_binding_domain_instances": list(empty_domains),
                    }
                )
                break
            if binding_status == "INVALID_INPUT":
                terminal_status = "UNKNOWN"
                censor_status = "INVALID_INPUT"
                final_reason = "binding_invalid_input"
                break
            terminal_status = "UNKNOWN"
            censor_status = "SOLVER_TIMEOUT_BINDING"
            final_reason = "unknown_other"
            break

        event_count = event_journal.count
        feedback_record_count = feedback_journal.count

    binding_summary = _compact_binding_summary(model)
    progress_started = time.perf_counter()
    _write_progress(
        progress_path,
        layout=layout,
        stage="terminal_receipt_ready",
        started=started,
        counters=counters,
        timings=timings,
        event_count=event_count,
        feedback_record_count=feedback_record_count,
        last_event=last_event_compact,
        last_status=terminal_status,
    )
    timings["progress_write_seconds"] += time.perf_counter() - progress_started
    return _layout_receipt(
        layout=layout,
        terminal_status=terminal_status,
        censor_status=censor_status,
        final_reason=final_reason,
        started=started,
        counters=counters,
        timings=timings,
        progress_path=progress_path,
        event_path=event_path,
        feedback_path=feedback_path,
        binding_summary=binding_summary,
    )


def _timeout_receipt(
    *,
    record: Mapping[str, Any],
    progress_path: Path,
    event_path: Path,
    feedback_path: Path,
) -> dict[str, Any]:
    progress = base._read_json(progress_path) if progress_path.is_file() else {}
    if not isinstance(progress, Mapping):
        progress = {}
    event_summary = _journal_summary(event_path)
    feedback_summary = _journal_summary(feedback_path)
    journal_corrupt = bool(
        event_summary["malformed_complete_line"]
        or feedback_summary["malformed_complete_line"]
    )
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v2",
        "research_only": True,
        "harness_revision": HARNESS_REVISION,
        "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
        "repository_head": base._git("rev-parse", "HEAD"),
        "layout_id": record["id"],
        "stratum": record["stratum"],
        "split": record["role"],
        "normalized_sha256": record["normalized_sha256"],
        "terminalStatus": "UNKNOWN",
        "censorStatus": (
            "HARNESS_ERROR" if journal_corrupt else "WALL_TIMEOUT_END_TO_END"
        ),
        "finalReason": "unknown_other",
        "counters": dict(progress.get("counters", {})),
        "timings": dict(progress.get("timings", {})),
        "total_wall_seconds": base.LAYOUT_WATCHDOG_SECONDS,
        "progress_receipt": {
            "path": str(progress_path),
            "sha256": base._sha256_file(progress_path) if progress_path.is_file() else None,
        },
        "event_journal": event_summary,
        "feedback_journal": feedback_summary,
        "watchdog": {
            "seconds": base.LAYOUT_WATCHDOG_SECONDS,
            "action": "child_terminated",
            "last_observed_stage": progress.get("stage"),
            "partial_progress_preserved": bool(progress),
        },
        "journal_corruption": journal_corrupt,
    }


def _run_layout_command(
    layout_id: str,
    output: Path,
    progress: Path,
    events: Path,
    feedback: Path,
) -> int:
    manifest = base._load_manifest()
    frozen = base._load_frozen_inputs(manifest)
    base._assert_protocol_ancestor()
    base._assert_clean_environment()
    record = base._record_by_id(manifest, layout_id)
    try:
        layout = base._load_layout(record, manifest, frozen)
        result = _run_layout(
            layout,
            frozen,
            progress_path=progress,
            event_path=events,
            feedback_path=feedback,
        )
    except base.IneligibleInput as exc:
        result = {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v2",
            "research_only": True,
            "harness_revision": HARNESS_REVISION,
            "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
            "repository_head": base._git("rev-parse", "HEAD"),
            "layout_id": layout_id,
            "stratum": record["stratum"],
            "split": record["role"],
            "terminalStatus": "UNKNOWN",
            "censorStatus": "INELIGIBLE_INPUT",
            "finalReason": "unknown_other",
            "error": str(exc),
        }
    except base.ProtocolViolation:
        raise
    except Exception as exc:  # noqa: BLE001
        result = base._synthetic_error_result(record, f"{type(exc).__name__}: {exc}")
        result["harness_revision"] = HARNESS_REVISION
        result["traceback"] = traceback.format_exc()
    base._write_json(output, result)
    print(json.dumps({"layout_id": layout_id, "receipt": str(output)}, ensure_ascii=False))
    return 0


def _run_injected(layout: base.LayoutInput, frozen: base.FrozenInputs) -> dict[str, Any]:
    started = time.perf_counter()
    model = base._new_binding_model(layout, frozen)
    first_status = str(model.solve(base.BINDING_SECONDS))
    if first_status != "FEASIBLE":
        return {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v2",
            "harness_revision": HARNESS_REVISION,
            "layout_id": layout.record["id"],
            "producer": "injected_selection_nogood",
            "first_status": first_status,
            "reachabilityFailureClass": "NOT_REACHED",
            "terminalOutcome": None,
            "wall_seconds": time.perf_counter() - started,
        }
    first_selection = model.extract_selection()
    applied = _feedback_applied_record(
        feedback_id=f"{layout.record['id']}:INJECTED",
        layout=layout,
        selection=first_selection,
        producer="injected_selection_nogood",
        model=model,
        event_index=0,
    )
    model.add_nogood_cut(dict(first_selection))
    second_status = str(model.solve(base.BINDING_SECONDS))
    second_selection = model.extract_selection() if second_status == "FEASIBLE" else None
    outcome = _feedback_outcome_record(
        applied=applied,
        next_status=second_status,
        next_selection=second_selection,
    )
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v2",
        "harness_revision": HARNESS_REVISION,
        "layout_id": layout.record["id"],
        "producer": "injected_selection_nogood",
        "first_status": first_status,
        "second_status": second_status,
        "applied": applied,
        "outcome": outcome,
        "wall_seconds": time.perf_counter() - started,
    }


def _run_injected_command(layout_id: str, output: Path) -> int:
    manifest = base._load_manifest()
    frozen = base._load_frozen_inputs(manifest)
    base._assert_protocol_ancestor()
    base._assert_clean_environment()
    record = base._record_by_id(manifest, layout_id)
    try:
        layout = base._load_layout(record, manifest, frozen)
        result = _run_injected(layout, frozen)
    except Exception as exc:  # noqa: BLE001
        result = {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v2",
            "harness_revision": HARNESS_REVISION,
            "layout_id": layout_id,
            "producer": "injected_selection_nogood",
            "reachabilityFailureClass": "NOT_REACHED",
            "terminalOutcome": None,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    base._write_json(output, result)
    return 0


def _feedback_pairs(records: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    for record in records:
        feedback_id = str(record.get("feedback_id", ""))
        if not feedback_id:
            continue
        pair = pairs.setdefault(feedback_id, {})
        pair[str(record.get("record_type", "unknown"))] = dict(record)
    return pairs


def _aggregate(output_dir: Path, manifest: Mapping[str, Any]) -> None:
    results: list[Mapping[str, Any]] = []
    for record in manifest["records"]:
        receipt_path = output_dir / "layouts" / f"{record['id']}.json"
        if receipt_path.is_file():
            payload = base._read_json(receipt_path)
            if isinstance(payload, Mapping):
                results.append(payload)
                continue
        results.append(base._synthetic_error_result(record, "missing layout receipt"))

    terminal_counts = Counter(str(item.get("terminalStatus", "UNKNOWN")) for item in results)
    censor_counts = Counter(str(item.get("censorStatus", "HARNESS_ERROR")) for item in results)
    uncensored = [item for item in results if item.get("censorStatus") == "UNCENSORED"]

    actual_family_layouts: dict[str, set[str]] = defaultdict(set)
    actual_family_strata: dict[str, set[str]] = defaultdict(set)
    actual_family_splits: dict[str, set[str]] = defaultdict(set)
    discovery_family_layouts: dict[str, set[str]] = defaultdict(set)
    discovery_family_strata: dict[str, set[str]] = defaultdict(set)
    discovery_family_supports: dict[str, set[str]] = defaultdict(set)
    discovery_family_replays: dict[str, set[str]] = defaultdict(set)

    signature_layouts: dict[str, set[str]] = defaultdict(set)
    signature_strata: dict[str, set[str]] = defaultdict(set)
    signature_splits: dict[str, set[str]] = defaultdict(set)
    signature_event_presence: Counter[str] = Counter()
    signature_total_blocked: Counter[str] = Counter()
    signature_discovery_layouts: dict[str, set[str]] = defaultdict(set)
    signature_discovery_strata: dict[str, set[str]] = defaultdict(set)

    organic_applied = 0
    organic_outcomes = 0
    organic_effects = 0
    organic_failure_classes: Counter[str] = Counter()
    pending_feedbacks = 0
    last_stage_counts: Counter[str] = Counter()
    per_layout_journal: dict[str, dict[str, Any]] = {}
    per_layout_exact: dict[str, dict[str, Any]] = {}
    total_event_records = 0
    total_selection_bearing_events = 0
    total_routing_solve_events = 0

    for result in results:
        layout_id = str(result["layout_id"])
        stratum = str(result["stratum"])
        split = str(result["split"])
        progress_path = output_dir / "progress" / f"{layout_id}.progress.json"
        progress = base._read_json(progress_path) if progress_path.is_file() else {}
        if not isinstance(progress, Mapping):
            progress = {}
        last_stage_counts[str(progress.get("stage") or "missing_progress")] += 1

        event_path = output_dir / "events" / f"{layout_id}.events.jsonl"
        feedback_path = output_dir / "feedback" / f"{layout_id}.feedback.jsonl"
        event_read = _read_jsonl(event_path)
        feedback_read = _read_jsonl(feedback_path)
        per_layout_journal[layout_id] = {
            "event_journal": _journal_summary(event_path),
            "feedback_journal": _journal_summary(feedback_path),
        }

        event_records = event_read.records
        total_event_records += len(event_records)
        selection_digests = {
            str(event["selection_digest"])
            for event in event_records
            if event.get("selection_digest")
        }
        local_signature_digests = Counter(
            str(event["local_signature_digest"])
            for event in event_records
            if event.get("local_signature_digest")
        )
        signature_layout_presence: Counter[str] = Counter()
        precheck_failure_count = 0
        routing_solve_event_count = 0
        for event in event_records:
            if event.get("selection_digest"):
                total_selection_bearing_events += 1
            if event.get("record_type") == "routing_precheck_failure":
                precheck_failure_count += 1
            if event.get("record_type") in {"routing_solve_failure", "layout_feasible"}:
                routing_solve_event_count += 1
            for signature in event.get("local_signature_counts", {}):
                signature_layout_presence[str(signature)] += 1
        total_routing_solve_events += routing_solve_event_count
        dominant_digest_count = (
            local_signature_digests.most_common(1)[0][1]
            if local_signature_digests
            else 0
        )
        per_layout_exact[layout_id] = {
            "event_record_count": len(event_records),
            "unique_selection_digest_count": len(selection_digests),
            "precheck_failure_event_count": precheck_failure_count,
            "routing_solve_event_count": routing_solve_event_count,
            "routing_precheck_count_exact": (
                precheck_failure_count + routing_solve_event_count
            ),
            "unique_local_signature_digest_count": len(local_signature_digests),
            "selection_to_local_digest_ratio": (
                len(selection_digests) / len(local_signature_digests)
                if local_signature_digests
                else None
            ),
            "dominant_local_digest_count": dominant_digest_count,
            "dominant_local_digest_share": (
                dominant_digest_count / len(event_records) if event_records else None
            ),
            "stable_local_signature_count": sum(
                count == len(event_records)
                for count in signature_layout_presence.values()
            ),
            "local_signature_count": len(signature_layout_presence),
        }

        seen_family: set[str] = set()
        for event in event_records:
            family_key = str(event.get("familyKey", ""))
            if family_key and family_key not in seen_family:
                seen_family.add(family_key)
                actual_family_layouts[family_key].add(layout_id)
                actual_family_strata[family_key].add(stratum)
                actual_family_splits[family_key].add(split)
                if split == "discovery" and result.get("censorStatus") == "UNCENSORED":
                    discovery_family_layouts[family_key].add(layout_id)
                    discovery_family_strata[family_key].add(stratum)
                    discovery_family_supports[family_key].add(
                        str(event.get("supportCoreStatus", "UNAVAILABLE"))
                    )
                    replay = event.get("diagnosticReplayStatus")
                    if replay:
                        discovery_family_replays[family_key].add(str(replay))

            signature_counts = event.get("local_signature_counts")
            if isinstance(signature_counts, Mapping):
                for raw_signature, raw_count in signature_counts.items():
                    signature = str(raw_signature)
                    count = int(raw_count)
                    signature_event_presence[signature] += 1
                    signature_total_blocked[signature] += count
                    signature_layouts[signature].add(layout_id)
                    signature_strata[signature].add(stratum)
                    signature_splits[signature].add(split)
                    if split == "discovery":
                        signature_discovery_layouts[signature].add(layout_id)
                        signature_discovery_strata[signature].add(stratum)
        pairs = _feedback_pairs(feedback_read.records)
        layout_applied = 0
        layout_outcomes = 0
        layout_effects = 0
        layout_pending = 0
        for pair in pairs.values():
            if "feedback_applied" in pair:
                organic_applied += 1
                layout_applied += 1
            outcome = pair.get("feedback_outcome")
            if outcome is None:
                pending_feedbacks += 1
                layout_pending += 1
                continue
            organic_outcomes += 1
            layout_outcomes += 1
            effect = bool(outcome.get("effect"))
            organic_effects += effect
            layout_effects += effect
            failure_class = outcome.get("reachabilityFailureClass")
            organic_failure_classes[str(failure_class)] += 1
        per_layout_exact[layout_id].update(
            {
                "feedback_applied_count": layout_applied,
                "feedback_outcome_count": layout_outcomes,
                "feedback_effect_count": layout_effects,
                "feedback_pending_at_censor_count": layout_pending,
            }
        )

    actual_families = []
    eligible_families = []
    for key in sorted(actual_family_layouts):
        reason, gate_side, feedback_form, event_censor = key.split("|", 3)
        discovery_layout_count = len(discovery_family_layouts[key])
        discovery_strata_count = len(discovery_family_strata[key])
        supports = sorted(discovery_family_supports[key])
        replays = sorted(discovery_family_replays[key])
        eligible = (
            len(uncensored) >= 6
            and discovery_layout_count >= 3
            and discovery_strata_count >= 2
            and feedback_form not in {"point_nogood", "none"}
            and "AVAILABLE_REPLAYED" in supports
            and "REPLAYED_IDENTICAL" in replays
        )
        family = {
            "familyKey": key,
            "reason": reason,
            "gateSide": gate_side,
            "feedbackForm": feedback_form,
            "eventCensorStatus": event_censor,
            "layout_ids": sorted(actual_family_layouts[key]),
            "layout_count": len(actual_family_layouts[key]),
            "strata": sorted(actual_family_strata[key]),
            "strata_count": len(actual_family_strata[key]),
            "splits": sorted(actual_family_splits[key]),
            "uncensored_discovery_layout_ids": sorted(discovery_family_layouts[key]),
            "uncensored_discovery_layout_count": discovery_layout_count,
            "uncensored_discovery_strata": sorted(discovery_family_strata[key]),
            "support_core_statuses": supports,
            "diagnostic_replay_statuses": replays,
            "eligible_for_d3": eligible,
        }
        actual_families.append(family)
        if eligible:
            eligible_families.append(family)
    eligible_families.sort(
        key=lambda item: (-int(item["uncensored_discovery_layout_count"]), item["familyKey"])
    )

    diagnostic_candidates = []
    for signature in signature_layouts:
        diagnostic_candidates.append(
            {
                "signature": signature,
                "layout_ids": sorted(signature_layouts[signature]),
                "layout_count": len(signature_layouts[signature]),
                "strata": sorted(signature_strata[signature]),
                "strata_count": len(signature_strata[signature]),
                "splits": sorted(signature_splits[signature]),
                "event_presence_count": signature_event_presence[signature],
                "total_blocked_port_relations": signature_total_blocked[signature],
                "discovery_layout_ids": sorted(signature_discovery_layouts[signature]),
                "discovery_layout_count": len(signature_discovery_layouts[signature]),
                "discovery_strata": sorted(signature_discovery_strata[signature]),
                "discovery_strata_count": len(signature_discovery_strata[signature]),
                "compilation_status": "NOT_COMPILED",
                "eligible_for_d3": False,
                "eligibility_note": (
                    "Diagnostic local family candidate only; current consumer applies a full selection point nogood."
                ),
            }
        )
    diagnostic_candidates.sort(
        key=lambda item: (
            -int(item["discovery_layout_count"]),
            -int(item["discovery_strata_count"]),
            -int(item["event_presence_count"]),
            -int(item["total_blocked_port_relations"]),
            str(item["signature"]),
        )
    )

    progress_precheck_lower_bounds = {
        str(item["layout_id"]): int(
            dict(item.get("counters", {})).get("routing_prechecks", 0)
        )
        for item in results
    }
    unique_progress_precheck_values = sorted(set(progress_precheck_lower_bounds.values()))
    uniform_progress_precheck_value = (
        unique_progress_precheck_values[0]
        if len(unique_progress_precheck_values) == 1
        else None
    )

    layout_receipts = []
    for item in results:
        layout_id = str(item["layout_id"])
        progress_lower_bound = dict(item.get("counters", {}))
        journal_exact = dict(per_layout_exact.get(layout_id, {}))
        exact_prechecks = int(journal_exact.get("routing_precheck_count_exact", 0))
        lower_prechecks = int(progress_lower_bound.get("routing_prechecks", 0))
        exact_feedback_applied = int(
            journal_exact.get("feedback_applied_count", 0)
        )
        lower_feedback_applied = int(
            progress_lower_bound.get("binding_routing_round_trips", 0)
        )
        layout_receipts.append(
            {
                "layout_id": layout_id,
                "stratum": item["stratum"],
                "split": item["split"],
                "terminalStatus": item.get("terminalStatus"),
                "censorStatus": item.get("censorStatus"),
                "finalReason": item.get("finalReason"),
                "progress_counters_lower_bound": progress_lower_bound,
                "journal_derived_counts": journal_exact,
                "counter_reconciliation": {
                    "routing_prechecks_progress_lower_bound": lower_prechecks,
                    "routing_prechecks_journal_exact": exact_prechecks,
                    "routing_prechecks_after_last_progress_snapshot": max(
                        0,
                        exact_prechecks - lower_prechecks,
                    ),
                    "feedback_applied_progress_lower_bound": (
                        lower_feedback_applied
                    ),
                    "feedback_applied_journal_exact": exact_feedback_applied,
                    "feedback_applied_after_last_progress_snapshot": max(
                        0,
                        exact_feedback_applied - lower_feedback_applied,
                    ),
                },
                "timings": item.get("timings", {}),
                "total_wall_seconds": item.get("total_wall_seconds"),
                "journals": per_layout_journal.get(layout_id, {}),
            }
        )

    spectrum = {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_d1_v2",
        "aggregation_revision": "postrun_exact_journal_counts_v2",
        "research_only": True,
        "harness_revision": HARNESS_REVISION,
        "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
        "repository_head": base._git("rev-parse", "HEAD"),
        "layout_count": len(results),
        "uncensored_terminal_count": len(uncensored),
        "minimum_uncensored_required": 6,
        "total_event_records": total_event_records,
        "total_selection_bearing_events": total_selection_bearing_events,
        "total_routing_solve_events": total_routing_solve_events,
        "counter_semantics": {
            "progress_counters_lower_bound": {
                "source": (
                    "the last atomic progress snapshot copied into the parent "
                    "watchdog receipt"
                ),
                "write_cadence": (
                    f"every {PROGRESS_EVERY_N_FEEDBACKS} completed feedback "
                    "round-trips, plus major stage transitions"
                ),
                "meaning": (
                    "a periodic lower bound at the last completed snapshot, not "
                    "the terminal event count"
                ),
                "uniform_value_warning": (
                    "equal values across layouts can be a snapshot-cadence artifact; "
                    "the observed 840 values mean each child passed the 840 checkpoint "
                    "before watchdog termination, not that each child executed exactly "
                    "840 prechecks"
                ),
            },
            "journal_derived_counts_exact": {
                "source": (
                    "complete newline-terminated records in the append-only event "
                    "and feedback JSONL journals"
                ),
                "meaning": (
                    "the exact durable count before process termination; these counts "
                    "are authoritative for D1/D2 event totals"
                ),
                "tail_policy": (
                    "an incomplete final line is excluded; any malformed complete "
                    "line is reported as journal corruption"
                ),
            },
        },
        "progress_snapshot_observation": {
            "routing_precheck_lower_bounds_by_layout": (
                progress_precheck_lower_bounds
            ),
            "uniform_routing_precheck_lower_bound": (
                uniform_progress_precheck_value
            ),
            "interpretation": (
                "This field describes the watchdog snapshot cadence only. Compare "
                "each value with layout_receipts[].journal_derived_counts."
            ),
        },
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "censor_counts": dict(sorted(censor_counts.items())),
        "actual_feedback_families": actual_families,
        "d3_eligible_families": eligible_families,
        "d3_triggered": bool(eligible_families),
        "diagnostic_local_family_candidates": diagnostic_candidates[:100],
        "diagnostic_candidate_count": len(diagnostic_candidates),
        "last_observed_stage_counts": dict(sorted(last_stage_counts.items())),
        "layout_receipts": layout_receipts,
    }
    base._write_json(output_dir / "D1_DEATH_SPECTRUM.json", spectrum)

    injected_path = output_dir / "D2_INJECTED.json"
    injected = base._read_json(injected_path) if injected_path.is_file() else None
    d2 = {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_d2_v2",
        "research_only": True,
        "harness_revision": HARNESS_REVISION,
        "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
        "organic_feedback_applied_count": organic_applied,
        "organic_feedback_outcome_count": organic_outcomes,
        "organic_feedback_effect_count": organic_effects,
        "organic_feedback_pending_at_censor_count": pending_feedbacks,
        "organic_reachability_failure_classes": dict(
            sorted(organic_failure_classes.items())
        ),
        "injected": injected,
        "injected_effect": bool(
            isinstance(injected, Mapping)
            and isinstance(injected.get("outcome"), Mapping)
            and injected["outcome"].get("effect")
        ),
        "required_failure_classes": sorted(base.REACHABILITY_FAILURE_CLASSES),
    }
    base._write_json(output_dir / "D2_REACHABILITY_MANIFEST.json", d2)

    lines = [
        "# Phase -1 r3 batch summary",
        "",
        f"- Protocol freeze: `{base.PROTOCOL_FREEZE_COMMIT}`.",
        f"- Harness: `{HARNESS_REVISION}`.",
        f"- Layouts: `{len(results)}`; uncensored terminal: `{len(uncensored)}` / minimum `6`.",
        f"- Terminal counts: `{dict(sorted(terminal_counts.items()))}`.",
        f"- Censor counts: `{dict(sorted(censor_counts.items()))}`.",
        f"- Actual feedback families: `{len(actual_families)}`; D3 eligible: `{len(eligible_families)}`.",
        f"- Diagnostic local family candidates: `{len(diagnostic_candidates)}`; all remain `NOT_COMPILED`.",
        f"- Organic feedback applied/outcomes/effects/pending: `{organic_applied}` / `{organic_outcomes}` / `{organic_effects}` / `{pending_feedbacks}`.",
        f"- Injected effect: `{d2['injected_effect']}`.",
        f"- Exact journal events: `{total_event_records}`; routing-solve events: `{total_routing_solve_events}`.",
        "",
        "## Layouts",
        "",
        "| ID | split | terminal | censor | exact prechecks | routing solves | unique local digests | stable signatures | journal s | wall s |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in spectrum["layout_receipts"]:
        exact = item.get("journal_derived_counts", {})
        timings = item.get("timings", {})
        wall = item.get("total_wall_seconds")
        wall_text = f"{float(wall):.2f}" if isinstance(wall, (int, float)) else "—"
        lines.append(
            f"| `{item['layout_id']}` | `{item['split']}` | `{item['terminalStatus']}` | "
            f"`{item['censorStatus']}` | {int(exact.get('precheck_failure_event_count', 0))} | "
            f"{int(exact.get('routing_solve_event_count', 0))} | "
            f"{int(exact.get('unique_local_signature_digest_count', 0))} | "
            f"{int(exact.get('stable_local_signature_count', 0))} | "
            f"{float(timings.get('journal_seconds', 0.0)):.3f} | {wall_text} |"
        )
    lines.extend(("", "## Leading diagnostic local signatures", ""))
    for candidate in diagnostic_candidates[:20]:
        lines.append(
            f"- `{candidate['signature']}`: discovery layouts "
            f"`{candidate['discovery_layout_count']}`, strata "
            f"`{candidate['discovery_strata_count']}`, event presence "
            f"`{candidate['event_presence_count']}`; `NOT_COMPILED`."
        )
    base._write_text(output_dir / "BATCH_SUMMARY.md", "\n".join(lines) + "\n")


def _run_batch(output_dir: Path) -> int:
    manifest = base._load_manifest()
    frozen = base._load_frozen_inputs(manifest)
    base._assert_protocol_ancestor()
    base._assert_clean_environment()
    excluded_receipts = base._validate_excluded_candidates(manifest, frozen)

    admission = []
    normalized_seen: set[str] = set()
    for record in manifest["records"]:
        try:
            layout = base._load_layout(record, manifest, frozen)
            if layout.normalized_sha256 in normalized_seen:
                raise base.IneligibleInput(
                    f"duplicate normalized digest in admitted corpus: {layout.normalized_sha256}"
                )
            normalized_seen.add(layout.normalized_sha256)
            admission.append(
                {
                    "layout_id": record["id"],
                    "status": "ADMITTED",
                    "normalized_sha256": layout.normalized_sha256,
                }
            )
        except Exception as exc:  # noqa: BLE001
            admission.append(
                {
                    "layout_id": record["id"],
                    "status": "INELIGIBLE_INPUT",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    base._write_json(
        output_dir / "CORPUS_ADMISSION.json",
        {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_admission_v1",
            "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
            "harness_revision": HARNESS_REVISION,
            "admitted_records": admission,
            "excluded_records": excluded_receipts,
        },
    )
    if any(item["status"] != "ADMITTED" for item in admission):
        return 2

    layout_dir = output_dir / "layouts"
    progress_dir = output_dir / "progress"
    event_dir = output_dir / "events"
    feedback_dir = output_dir / "feedback"
    log_dir = output_dir / "layout_logs"
    for directory in (layout_dir, progress_dir, event_dir, feedback_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    environment = base._child_environment()
    script = Path(__file__).resolve()
    for record in manifest["records"]:
        layout_id = str(record["id"])
        output_path = layout_dir / f"{layout_id}.json"
        progress_path = progress_dir / f"{layout_id}.progress.json"
        event_path = event_dir / f"{layout_id}.events.jsonl"
        feedback_path = feedback_dir / f"{layout_id}.feedback.jsonl"
        log_path = log_dir / f"{layout_id}.log"
        command = [
            sys.executable,
            str(script),
            "layout",
            "--layout-id",
            layout_id,
            "--output",
            str(output_path),
            "--progress",
            str(progress_path),
            "--events",
            str(event_path),
            "--feedback",
            str(feedback_path),
        ]
        started = time.perf_counter()
        with log_path.open("w", encoding="utf-8") as log_handle:
            log_handle.write(f"command={command!r}\n")
            log_handle.flush()
            try:
                completed = subprocess.run(
                    command,
                    cwd=base.ROOT,
                    env=environment,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=base.LAYOUT_WATCHDOG_SECONDS,
                    text=True,
                )
            except subprocess.TimeoutExpired:
                base._write_json(
                    output_path,
                    _timeout_receipt(
                        record=record,
                        progress_path=progress_path,
                        event_path=event_path,
                        feedback_path=feedback_path,
                    ),
                )
                log_handle.write(
                    f"watchdog_timeout_seconds={base.LAYOUT_WATCHDOG_SECONDS}\n"
                )
            else:
                log_handle.write(f"child_exit_code={completed.returncode}\n")
                if completed.returncode != 0 and not output_path.is_file():
                    base._write_json(
                        output_path,
                        base._synthetic_error_result(
                            record,
                            f"child exited {completed.returncode} without receipt",
                        ),
                    )
            log_handle.write(f"parent_wall_seconds={time.perf_counter() - started:.6f}\n")

    injection_path = output_dir / "D2_INJECTED.json"
    injection_log = output_dir / "D2_INJECTED.log"
    injection_command = [
        sys.executable,
        str(script),
        "inject",
        "--layout-id",
        "POSTMEM-00",
        "--output",
        str(injection_path),
    ]
    with injection_log.open("w", encoding="utf-8") as log_handle:
        try:
            completed = subprocess.run(
                injection_command,
                cwd=base.ROOT,
                env=environment,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=base.INJECTED_WATCHDOG_SECONDS,
                text=True,
            )
        except subprocess.TimeoutExpired:
            base._write_json(
                injection_path,
                {
                    "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v2",
                    "harness_revision": HARNESS_REVISION,
                    "layout_id": "POSTMEM-00",
                    "producer": "injected_selection_nogood",
                    "reachabilityFailureClass": "NOT_REACHED",
                    "terminalOutcome": None,
                    "censorStatus": "WALL_TIMEOUT_END_TO_END",
                },
            )
        else:
            log_handle.write(f"child_exit_code={completed.returncode}\n")

    _aggregate(output_dir, manifest)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")

    layout = subparsers.add_parser("layout")
    layout.add_argument("--layout-id", required=True)
    layout.add_argument("--output", type=Path, required=True)
    layout.add_argument("--progress", type=Path, required=True)
    layout.add_argument("--events", type=Path, required=True)
    layout.add_argument("--feedback", type=Path, required=True)

    inject = subparsers.add_parser("inject")
    inject.add_argument("--layout-id", required=True)
    inject.add_argument("--output", type=Path, required=True)

    batch = subparsers.add_parser("batch")
    batch.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        return base._validate_corpus()
    if args.command == "layout":
        return _run_layout_command(
            args.layout_id,
            args.output.resolve(),
            args.progress.resolve(),
            args.events.resolve(),
            args.feedback.resolve(),
        )
    if args.command == "inject":
        return _run_injected_command(args.layout_id, args.output.resolve())
    if args.command == "batch":
        return _run_batch(args.output_dir.resolve())
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
