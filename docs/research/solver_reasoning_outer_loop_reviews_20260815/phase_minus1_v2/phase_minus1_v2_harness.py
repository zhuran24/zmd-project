#!/usr/bin/env python3
"""Phase -1 v2 high-budget death-spectrum harness.

Research-only.  This module reuses the v1/r3 fixed-placement binding/routing
implementation, but adds:

* three long-running full-layout arms;
* formal count-window saturation monitoring;
* six finite binding-domain slice calibrations;
* a bounded concurrent supervisor with per-arm receipts.

It never invokes master search, supervisor seal, publisher, or certified output
surfaces.  D3/D4 compilation and treatment remain disabled by protocol.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

HERE = Path(__file__).resolve().parent
V1_DIR = HERE.parent / "phase_minus1"
ROOT = HERE.parents[4]
for import_path in (str(V1_DIR), str(ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

import phase_minus1_harness as base  # noqa: E402
import phase_minus1_harness_r3 as r3  # noqa: E402

PROTOCOL_FREEZE_COMMIT = "6c9fc1f4201c2eb79f0ea87b4e5530cfe245897a"
MANIFEST_PATH = HERE / "corpus_manifest_v2.json"
PROTOCOL_PATH = HERE / "PHASE_MINUS1_V2_PROTOCOL.md"
HARNESS_REVISION = "phase_minus1_v2_high_budget_saturation_v1"

BINDING_SECONDS = 20.0
ROUTING_SECONDS = 30.0
BINDING_WORKERS = 1
ROUTING_WORKERS = 1
CP_SAT_RANDOM_SEED = 1
DEEP_MAX_WALL_SECONDS = 28800.0
SLICE_MAX_WALL_SECONDS = 2700.0
POLL_SECONDS = 5.0
TERMINATION_GRACE_SECONDS = 10.0

WINDOW_SIZE = 5000
MIN_COMPLETE_WINDOWS = 12
MIN_CUMULATIVE_EVENTS = 60000
REQUIRED_CONSECUTIVE_SATURATED = 3
MAX_NEW_ATOMIC_SIGNATURES = 0
MAX_NEW_EVENT_SHAPES = 2
MAX_NEW_EVENT_MASS_FRACTION = 0.005
MIN_EVENT_SHAPE_JACCARD = 0.95
MAX_EVENT_SHAPE_TVD = 0.05
MAX_GOOD_TURING_UNSEEN_MASS = 0.01

D3_D4_STATUS = "DEFERRED_BY_OWNER"


def _configure_v2_bindings() -> None:
    """Point the imported v1/r3 helpers at the v2 frozen protocol."""

    base.MANIFEST_PATH = MANIFEST_PATH
    base.PROTOCOL_PATH = PROTOCOL_PATH
    base.PROTOCOL_FREEZE_COMMIT = PROTOCOL_FREEZE_COMMIT
    base.BINDING_SECONDS = BINDING_SECONDS
    base.ROUTING_SECONDS = ROUTING_SECONDS
    base.BINDING_WORKERS = BINDING_WORKERS
    base.ROUTING_WORKERS = ROUTING_WORKERS
    base.CP_SAT_RANDOM_SEED = CP_SAT_RANDOM_SEED
    r3.HARNESS_REVISION = HARNESS_REVISION

    def _load_v2_manifest() -> dict[str, Any]:
        manifest = base._read_json(MANIFEST_PATH)
        if manifest.get("status") != "FROZEN_PRE_RUN_V2":
            raise base.ProtocolViolation(
                f"unexpected v2 manifest status: {manifest.get('status')!r}"
            )
        return manifest

    base._load_manifest = _load_v2_manifest  # type: ignore[assignment]


_configure_v2_bindings()


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    base._write_json(path, payload)


def _read_json(path: Path) -> Any:
    return base._read_json(path)


def _sha256_file(path: Path) -> str:
    return base._sha256_file(path)


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    return base._canonical_digest(payload)


def _load_manifest() -> dict[str, Any]:
    return base._load_manifest()


def _manifest_run(manifest: Mapping[str, Any], section: str, run_id: str) -> Mapping[str, Any]:
    matches = [
        item
        for item in manifest.get(section, [])
        if isinstance(item, Mapping) and str(item.get("run_id")) == run_id
    ]
    if len(matches) != 1:
        raise base.ProtocolViolation(
            f"run id {run_id!r} resolves to {len(matches)} records in {section}"
        )
    return matches[0]


def _assert_frozen_contract(manifest: Mapping[str, Any]) -> None:
    base._assert_protocol_ancestor()
    base._assert_clean_environment()
    execution = manifest.get("execution_contract")
    if not isinstance(execution, Mapping):
        raise base.ProtocolViolation("v2 execution_contract is missing")
    expected = {
        "binding_seconds": BINDING_SECONDS,
        "routing_seconds": ROUTING_SECONDS,
        "binding_workers": BINDING_WORKERS,
        "routing_workers": ROUTING_WORKERS,
        "cp_sat_random_seed": CP_SAT_RANDOM_SEED,
        "python_hash_seed": 0,
        "deep_parallelism": 3,
        "slice_parallelism": 1,
        "total_parallelism": 4,
        "alternative_count_cap": None,
    }
    for key, expected_value in expected.items():
        if execution.get(key) != expected_value:
            raise base.ProtocolViolation(
                f"v2 execution contract mismatch for {key}: "
                f"expected {expected_value!r}, got {execution.get(key)!r}"
            )
    saturation = execution.get("saturation")
    if not isinstance(saturation, Mapping):
        raise base.ProtocolViolation("v2 saturation contract is missing")
    saturation_expected = {
        "window_size_events": WINDOW_SIZE,
        "minimum_complete_windows": MIN_COMPLETE_WINDOWS,
        "minimum_cumulative_events": MIN_CUMULATIVE_EVENTS,
        "required_consecutive_saturated_windows": REQUIRED_CONSECUTIVE_SATURATED,
        "max_new_atomic_signatures": MAX_NEW_ATOMIC_SIGNATURES,
        "max_new_event_shapes": MAX_NEW_EVENT_SHAPES,
        "max_new_event_mass_fraction": MAX_NEW_EVENT_MASS_FRACTION,
        "minimum_event_shape_jaccard": MIN_EVENT_SHAPE_JACCARD,
        "maximum_event_shape_tvd": MAX_EVENT_SHAPE_TVD,
        "maximum_good_turing_unseen_mass": MAX_GOOD_TURING_UNSEEN_MASS,
    }
    for key, expected_value in saturation_expected.items():
        if saturation.get(key) != expected_value:
            raise base.ProtocolViolation(
                f"v2 saturation contract mismatch for {key}: "
                f"expected {expected_value!r}, got {saturation.get(key)!r}"
            )
    d3_d4 = manifest.get("d3_d4")
    if not isinstance(d3_d4, Mapping) or d3_d4.get("status") != D3_D4_STATUS:
        raise base.ProtocolViolation("D3/D4 must remain DEFERRED_BY_OWNER")
    if d3_d4.get("compilation_allowed") is not False:
        raise base.ProtocolViolation("D3 compilation must remain disabled")
    if d3_d4.get("treatment_allowed") is not False:
        raise base.ProtocolViolation("D4 treatment must remain disabled")


def _child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in base.FORBIDDEN_NONEMPTY_ENV:
        environment.pop(name, None)
    environment["EXACT_BINDING_CP_SAT_WORKERS"] = str(BINDING_WORKERS)
    environment["EXACT_ROUTING_CP_SAT_WORKERS"] = str(ROUTING_WORKERS)
    environment["PYTHONHASHSEED"] = "0"
    return environment


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def _distribution_tvd(left: Counter[str], right: Counter[str]) -> float:
    left_total = sum(left.values())
    right_total = sum(right.values())
    if left_total <= 0 and right_total <= 0:
        return 0.0
    keys = set(left) | set(right)
    return 0.5 * sum(
        abs(
            (left.get(key, 0) / left_total if left_total else 0.0)
            - (right.get(key, 0) / right_total if right_total else 0.0)
        )
        for key in keys
    )


def _event_shape_digest(event: Mapping[str, Any]) -> str:
    local_digest = event.get("local_signature_digest")
    if isinstance(local_digest, str) and local_digest:
        return local_digest
    return _canonical_digest(
        {
            "record_type": str(event.get("record_type", "")),
            "familyKey": str(event.get("familyKey", "")),
            "reason": str(event.get("reason", "")),
            "gateSide": str(event.get("gateSide", "")),
            "feedbackForm": str(event.get("feedbackForm", "")),
        }
    )


@dataclass
class SaturationTracker:
    window_path: Path
    window_size: int = WINDOW_SIZE
    cumulative_shape_counts: Counter[str] = field(default_factory=Counter)
    cumulative_atomic_signatures: set[str] = field(default_factory=set)
    current_shape_counts: Counter[str] = field(default_factory=Counter)
    current_atomic_signatures: set[str] = field(default_factory=set)
    current_actual_families: Counter[str] = field(default_factory=Counter)
    previous_shape_counts: Counter[str] | None = None
    complete_windows: list[dict[str, Any]] = field(default_factory=list)
    total_events: int = 0
    consecutive_saturated: int = 0

    def add(self, event: Mapping[str, Any]) -> dict[str, Any] | None:
        shape = _event_shape_digest(event)
        self.current_shape_counts[shape] += 1
        atomic = event.get("local_signature_counts")
        if isinstance(atomic, Mapping):
            self.current_atomic_signatures.update(str(key) for key in atomic)
        family = str(event.get("familyKey", ""))
        if family:
            self.current_actual_families[family] += 1
        self.total_events += 1
        if sum(self.current_shape_counts.values()) < self.window_size:
            return None
        return self._close_window()

    def _close_window(self) -> dict[str, Any]:
        window_index = len(self.complete_windows) + 1
        event_count = sum(self.current_shape_counts.values())
        before_shapes = set(self.cumulative_shape_counts)
        current_shapes = set(self.current_shape_counts)
        new_shapes = current_shapes - before_shapes
        new_shape_mass = sum(self.current_shape_counts[shape] for shape in new_shapes)
        new_atomic = self.current_atomic_signatures - self.cumulative_atomic_signatures

        previous_shapes = (
            set(self.previous_shape_counts) if self.previous_shape_counts is not None else set()
        )
        jaccard = (
            _jaccard(current_shapes, previous_shapes)
            if self.previous_shape_counts is not None
            else None
        )
        tvd = (
            _distribution_tvd(self.current_shape_counts, self.previous_shape_counts)
            if self.previous_shape_counts is not None
            else None
        )

        updated_cumulative = self.cumulative_shape_counts + self.current_shape_counts
        cumulative_event_count = sum(updated_cumulative.values())
        singleton_count = sum(count == 1 for count in updated_cumulative.values())
        unseen_mass = (
            singleton_count / cumulative_event_count if cumulative_event_count else 0.0
        )
        top10_mass = (
            sum(count for _shape, count in self.current_shape_counts.most_common(10))
            / event_count
            if event_count
            else 0.0
        )

        saturated = bool(
            self.previous_shape_counts is not None
            and len(new_atomic) <= MAX_NEW_ATOMIC_SIGNATURES
            and len(new_shapes) <= MAX_NEW_EVENT_SHAPES
            and (new_shape_mass / event_count if event_count else 0.0)
            <= MAX_NEW_EVENT_MASS_FRACTION
            and jaccard is not None
            and jaccard >= MIN_EVENT_SHAPE_JACCARD
            and tvd is not None
            and tvd <= MAX_EVENT_SHAPE_TVD
            and unseen_mass <= MAX_GOOD_TURING_UNSEEN_MASS
        )
        if saturated:
            self.consecutive_saturated += 1
        else:
            self.consecutive_saturated = 0

        record = {
            "schema_version": "zmd_phase_minus1_v2_saturation_window_v1",
            "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
            "window_index": window_index,
            "event_start_index": (window_index - 1) * self.window_size + 1,
            "event_end_index": window_index * self.window_size,
            "event_count": event_count,
            "event_shape_unique_count": len(current_shapes),
            "new_event_shape_count": len(new_shapes),
            "new_event_mass_fraction": (
                new_shape_mass / event_count if event_count else 0.0
            ),
            "atomic_signature_count": len(self.current_atomic_signatures),
            "new_atomic_signature_count": len(new_atomic),
            "event_shape_jaccard_vs_previous": jaccard,
            "event_shape_tvd_vs_previous": tvd,
            "cumulative_event_count": cumulative_event_count,
            "cumulative_event_shape_count": len(updated_cumulative),
            "cumulative_singleton_count": singleton_count,
            "good_turing_unseen_mass": unseen_mass,
            "top10_event_shape_mass": top10_mass,
            "actual_feedback_families": dict(
                sorted(self.current_actual_families.items())
            ),
            "saturated": saturated,
            "consecutive_saturated_windows": self.consecutive_saturated,
            "thresholds": {
                "max_new_atomic_signatures": MAX_NEW_ATOMIC_SIGNATURES,
                "max_new_event_shapes": MAX_NEW_EVENT_SHAPES,
                "max_new_event_mass_fraction": MAX_NEW_EVENT_MASS_FRACTION,
                "minimum_event_shape_jaccard": MIN_EVENT_SHAPE_JACCARD,
                "maximum_event_shape_tvd": MAX_EVENT_SHAPE_TVD,
                "maximum_good_turing_unseen_mass": MAX_GOOD_TURING_UNSEEN_MASS,
            },
        }
        with r3.CompactJournal(self.window_path) as journal:
            journal.append(record)

        self.complete_windows.append(record)
        self.cumulative_shape_counts = updated_cumulative
        self.cumulative_atomic_signatures.update(self.current_atomic_signatures)
        self.previous_shape_counts = Counter(self.current_shape_counts)
        self.current_shape_counts.clear()
        self.current_atomic_signatures.clear()
        self.current_actual_families.clear()
        return record

    def formal_endpoint_reached(self) -> bool:
        return bool(
            self.total_events >= MIN_CUMULATIVE_EVENTS
            and len(self.complete_windows) >= MIN_COMPLETE_WINDOWS
            and self.consecutive_saturated >= REQUIRED_CONSECUTIVE_SATURATED
        )

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": "zmd_phase_minus1_v2_saturation_summary_v1",
            "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
            "window_size_events": self.window_size,
            "total_complete_event_count": len(self.complete_windows) * self.window_size,
            "total_observed_event_count": self.total_events,
            "complete_window_count": len(self.complete_windows),
            "partial_tail_event_count": sum(self.current_shape_counts.values()),
            "cumulative_event_shape_count": len(self.cumulative_shape_counts),
            "cumulative_atomic_signature_count": len(self.cumulative_atomic_signatures),
            "consecutive_saturated_windows": self.consecutive_saturated,
            "formal_endpoint_reached": self.formal_endpoint_reached(),
            "last_three_windows": self.complete_windows[-3:],
        }


@dataclass
class JsonlTail:
    path: Path
    offset: int = 0
    buffer: bytes = b""
    malformed_complete_line: str | None = None
    truncated_tail: bool = False

    def poll(self) -> list[Mapping[str, Any]]:
        if not self.path.is_file():
            return []
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            chunk = handle.read()
            self.offset = handle.tell()
        if not chunk:
            return []
        payload = self.buffer + chunk
        parts = payload.split(b"\n")
        self.buffer = parts.pop()
        records: list[Mapping[str, Any]] = []
        for index, raw_line in enumerate(parts):
            if not raw_line:
                continue
            try:
                parsed = json.loads(raw_line.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                self.malformed_complete_line = (
                    f"tail record {index + 1}: {type(exc).__name__}: {exc}"
                )
                continue
            if not isinstance(parsed, Mapping):
                self.malformed_complete_line = f"tail record {index + 1}: not an object"
                continue
            records.append(parsed)
        return records

    def finish(self) -> list[Mapping[str, Any]]:
        records = self.poll()
        self.truncated_tail = bool(self.buffer)
        return records


@dataclass
class RunningTask:
    run_id: str
    kind: str
    record: Mapping[str, Any]
    directory: Path
    process: subprocess.Popen[str]
    log_handle: Any
    started_monotonic: float
    max_wall_seconds: float
    event_tail: JsonlTail | None = None
    saturation: SaturationTracker | None = None
    termination_reason: str | None = None


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + TERMINATION_GRACE_SECONDS
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.1)
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _deep_paths(directory: Path) -> dict[str, Path]:
    return {
        "output": directory / "layout_receipt.json",
        "progress": directory / "progress.json",
        "events": directory / "events.jsonl",
        "feedback": directory / "feedback.jsonl",
        "windows": directory / "saturation_windows.jsonl",
        "summary": directory / "saturation_summary.json",
        "log": directory / "full.log",
    }


def _slice_paths(directory: Path) -> dict[str, Path]:
    return {
        "output": directory / "slice_receipt.json",
        "progress": directory / "progress.json",
        "events": directory / "events.jsonl",
        "feedback": directory / "feedback.jsonl",
        "log": directory / "full.log",
    }


def _start_deep_task(
    *,
    manifest: Mapping[str, Any],
    run_record: Mapping[str, Any],
    output_root: Path,
) -> RunningTask:
    run_id = str(run_record["run_id"])
    directory = output_root / "deep" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    paths = _deep_paths(directory)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "deep-child",
        "--run-id",
        run_id,
        "--output",
        str(paths["output"]),
        "--progress",
        str(paths["progress"]),
        "--events",
        str(paths["events"]),
        "--feedback",
        str(paths["feedback"]),
    ]
    log_handle = paths["log"].open("w", encoding="utf-8")
    log_handle.write(f"started_at_utc={_now_utc()}\n")
    log_handle.write(f"command={command!r}\n")
    log_handle.flush()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=_child_environment(),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    return RunningTask(
        run_id=run_id,
        kind="deep",
        record=run_record,
        directory=directory,
        process=process,
        log_handle=log_handle,
        started_monotonic=time.monotonic(),
        max_wall_seconds=float(run_record["max_wall_seconds"]),
        event_tail=JsonlTail(paths["events"]),
        saturation=SaturationTracker(paths["windows"]),
    )


def _start_slice_task(
    *,
    run_record: Mapping[str, Any],
    output_root: Path,
) -> RunningTask:
    run_id = str(run_record["run_id"])
    directory = output_root / "slices" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    paths = _slice_paths(directory)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "slice-child",
        "--run-id",
        run_id,
        "--output",
        str(paths["output"]),
        "--progress",
        str(paths["progress"]),
        "--events",
        str(paths["events"]),
        "--feedback",
        str(paths["feedback"]),
    ]
    log_handle = paths["log"].open("w", encoding="utf-8")
    log_handle.write(f"started_at_utc={_now_utc()}\n")
    log_handle.write(f"command={command!r}\n")
    log_handle.flush()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=_child_environment(),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    return RunningTask(
        run_id=run_id,
        kind="slice",
        record=run_record,
        directory=directory,
        process=process,
        log_handle=log_handle,
        started_monotonic=time.monotonic(),
        max_wall_seconds=float(run_record["max_wall_seconds"]),
    )


def _journal_exact_counts(event_path: Path, feedback_path: Path) -> dict[str, Any]:
    event_read = r3._read_jsonl(event_path)
    feedback_read = r3._read_jsonl(feedback_path)
    event_families: Counter[str] = Counter()
    event_shapes: Counter[str] = Counter()
    atomic_signatures: set[str] = set()
    routing_solve_events = 0
    for event in event_read.records:
        event_families[str(event.get("familyKey", ""))] += 1
        event_shapes[_event_shape_digest(event)] += 1
        local = event.get("local_signature_counts")
        if isinstance(local, Mapping):
            atomic_signatures.update(str(key) for key in local)
        if event.get("record_type") in {"routing_solve_failure", "layout_feasible"}:
            routing_solve_events += 1
    feedback_pairs = r3._feedback_pairs(feedback_read.records)
    applied = sum("feedback_applied" in pair for pair in feedback_pairs.values())
    outcomes = sum("feedback_outcome" in pair for pair in feedback_pairs.values())
    effects = sum(
        bool(pair.get("feedback_outcome", {}).get("effect"))
        for pair in feedback_pairs.values()
        if "feedback_outcome" in pair
    )
    pending = sum(
        "feedback_applied" in pair and "feedback_outcome" not in pair
        for pair in feedback_pairs.values()
    )
    return {
        "event_record_count": len(event_read.records),
        "event_family_counts": dict(sorted(event_families.items())),
        "event_shape_unique_count": len(event_shapes),
        "atomic_signature_count": len(atomic_signatures),
        "routing_solve_event_count": routing_solve_events,
        "feedback_applied_count": applied,
        "feedback_outcome_count": outcomes,
        "feedback_effect_count": effects,
        "feedback_pending_count": pending,
        "event_journal": r3._journal_summary(event_path),
        "feedback_journal": r3._journal_summary(feedback_path),
    }


def _progress_payload(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        return {}
    payload = _read_json(path)
    return payload if isinstance(payload, Mapping) else {}


def _finalize_deep_task(task: RunningTask) -> None:
    assert task.event_tail is not None
    assert task.saturation is not None
    paths = _deep_paths(task.directory)
    for event in task.event_tail.finish():
        task.saturation.add(event)
    saturation_summary = task.saturation.summary()
    _write_json(paths["summary"], saturation_summary)

    child_payload: Mapping[str, Any] = {}
    if paths["output"].is_file():
        raw = _read_json(paths["output"])
        if isinstance(raw, Mapping):
            child_payload = raw
    progress = _progress_payload(paths["progress"])
    exact = _journal_exact_counts(paths["events"], paths["feedback"])
    elapsed = time.monotonic() - task.started_monotonic

    if task.termination_reason == "WINDOW_SATURATED":
        terminal_status = "UNKNOWN"
        censor_status = "WINDOW_SATURATED"
        final_reason = "formal_window_saturation_endpoint"
    elif task.termination_reason == "WALL_TIMEOUT_END_TO_END":
        terminal_status = "UNKNOWN"
        censor_status = "WALL_TIMEOUT_END_TO_END"
        final_reason = "deep_max_wall_reached"
    elif task.termination_reason == "HARNESS_ERROR":
        terminal_status = "UNKNOWN"
        censor_status = "HARNESS_ERROR"
        final_reason = "deep_child_missing_or_invalid_receipt"
    else:
        raw_terminal = str(child_payload.get("terminalStatus", "UNKNOWN"))
        raw_censor = str(child_payload.get("censorStatus", "HARNESS_ERROR"))
        raw_reason = str(child_payload.get("finalReason", "unknown_other"))
        if raw_censor == "UNCENSORED" and raw_terminal == "FEASIBLE":
            terminal_status = "FULL_LAYOUT_FEASIBLE"
            censor_status = "UNCENSORED"
            final_reason = raw_reason
        elif raw_censor == "UNCENSORED" and raw_terminal == "INFEASIBLE":
            terminal_status = "FULL_LAYOUT_BINDING_EXHAUSTED"
            censor_status = "UNCENSORED"
            final_reason = raw_reason
        else:
            terminal_status = raw_terminal
            censor_status = raw_censor
            final_reason = raw_reason

    journal_corrupt = bool(
        exact["event_journal"].get("malformed_complete_line")
        or exact["feedback_journal"].get("malformed_complete_line")
    )
    if journal_corrupt:
        terminal_status = "UNKNOWN"
        censor_status = "HARNESS_ERROR"
        final_reason = "journal_corruption"

    receipt = {
        "schema_version": "zmd_phase_minus1_v2_deep_receipt_v1",
        "research_only": True,
        "non_authorizing": True,
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "harness_revision": HARNESS_REVISION,
        "repository_head": base._git("rev-parse", "HEAD"),
        "run_id": task.run_id,
        "layout_id": task.record["layout_id"],
        "role": task.record["role"],
        "stratum": task.record["stratum"],
        "terminalStatus": terminal_status,
        "censorStatus": censor_status,
        "finalReason": final_reason,
        "elapsed_wall_seconds": elapsed,
        "max_wall_seconds": task.max_wall_seconds,
        "child_exit_code": task.process.returncode,
        "child_receipt": dict(child_payload),
        "progress_snapshot_lower_bound": dict(progress),
        "journal_derived_exact_counts": exact,
        "saturation": saturation_summary,
        "D3_status": D3_D4_STATUS,
        "D4_status": D3_D4_STATUS,
        "compilation_status": "DEFERRED_BY_OWNER",
        "consumer_status": "NOT_RUN",
    }
    _write_json(paths["output"], receipt)
    task.log_handle.write(
        f"finished_at_utc={_now_utc()}\n"
        f"child_exit_code={task.process.returncode}\n"
        f"terminalStatus={terminal_status}\n"
        f"censorStatus={censor_status}\n"
    )
    task.log_handle.flush()
    (task.directory / "EXIT_CODE").write_text(
        f"{0 if censor_status != 'HARNESS_ERROR' else 70}\n", encoding="utf-8"
    )
    (task.directory / ".DONE").touch()


def _finalize_slice_timeout(task: RunningTask) -> None:
    paths = _slice_paths(task.directory)
    progress = _progress_payload(paths["progress"])
    exact = _journal_exact_counts(paths["events"], paths["feedback"])
    receipt = {
        "schema_version": "zmd_phase_minus1_v2_slice_receipt_v1",
        "research_only": True,
        "non_authorizing": True,
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "harness_revision": HARNESS_REVISION,
        "repository_head": base._git("rev-parse", "HEAD"),
        "run_id": task.run_id,
        "layout_id": task.record["layout_id"],
        "target_product": int(task.record["target_product"]),
        "terminalStatus": "UNKNOWN",
        "censorStatus": "SLICE_WALL_TIMEOUT",
        "finalReason": "slice_max_wall_reached",
        "elapsed_wall_seconds": time.monotonic() - task.started_monotonic,
        "max_wall_seconds": task.max_wall_seconds,
        "progress_snapshot_lower_bound": dict(progress),
        "journal_derived_exact_counts": exact,
        "scope_warning": "restricted binding-domain slice only; not a full-layout conclusion",
        "D3_status": D3_D4_STATUS,
        "D4_status": D3_D4_STATUS,
    }
    _write_json(paths["output"], receipt)
    (task.directory / "EXIT_CODE").write_text("0\n", encoding="utf-8")
    (task.directory / ".DONE").touch()


def _close_task_log(task: RunningTask) -> None:
    try:
        task.log_handle.flush()
    finally:
        task.log_handle.close()


def _monitor_deep(task: RunningTask) -> bool:
    assert task.event_tail is not None
    assert task.saturation is not None
    new_events = task.event_tail.poll()
    for event in new_events:
        task.saturation.add(event)
    if task.saturation.formal_endpoint_reached() and task.process.poll() is None:
        task.termination_reason = "WINDOW_SATURATED"
        _terminate_process_group(task.process)
    elapsed = time.monotonic() - task.started_monotonic
    if elapsed >= task.max_wall_seconds and task.process.poll() is None:
        task.termination_reason = "WALL_TIMEOUT_END_TO_END"
        _terminate_process_group(task.process)
    if task.process.poll() is None:
        return False
    if task.termination_reason is None and not _deep_paths(task.directory)["output"].is_file():
        task.termination_reason = "HARNESS_ERROR"
    _finalize_deep_task(task)
    _close_task_log(task)
    return True


def _monitor_slice(task: RunningTask) -> bool:
    elapsed = time.monotonic() - task.started_monotonic
    if elapsed >= task.max_wall_seconds and task.process.poll() is None:
        task.termination_reason = "SLICE_WALL_TIMEOUT"
        _terminate_process_group(task.process)
    if task.process.poll() is None:
        return False
    paths = _slice_paths(task.directory)
    if task.termination_reason == "SLICE_WALL_TIMEOUT":
        _finalize_slice_timeout(task)
    elif not paths["output"].is_file():
        task.termination_reason = "HARNESS_ERROR"
        _finalize_slice_timeout(task)
    else:
        (task.directory / "EXIT_CODE").write_text(
            f"{task.process.returncode or 0}\n", encoding="utf-8"
        )
        (task.directory / ".DONE").touch()
    task.log_handle.write(f"finished_at_utc={_now_utc()}\n")
    task.log_handle.write(f"child_exit_code={task.process.returncode}\n")
    task.log_handle.flush()
    _close_task_log(task)
    return True


def _variable_groups(
    model: base.PortBindingModel,
    selection: Mapping[str, Any],
    conflict_ids: set[str],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    binding_selection = selection.get("binding_choice", {})
    generic_inputs = selection.get("generic_inputs", {})
    generic_outputs = selection.get("generic_outputs", {})

    for instance_id, vars_by_idx in model.binding_vars.items():
        selected = binding_selection.get(instance_id)
        if selected not in vars_by_idx:
            raise base.ProtocolViolation(
                f"selection missing binding choice for variable group {instance_id}"
            )
        category = 0 if str(instance_id) in conflict_ids else 1
        groups.append(
            {
                "kind": "binding_choice",
                "group_id": str(instance_id),
                "category": category,
                "cardinality": len(vars_by_idx),
                "selected_value": int(selected),
                "variables": vars_by_idx,
            }
        )
    for slot_id, vars_by_commodity in model.generic_input_vars.items():
        selected = generic_inputs.get(slot_id)
        if selected not in vars_by_commodity:
            raise base.ProtocolViolation(
                f"selection missing generic input choice for variable group {slot_id}"
            )
        groups.append(
            {
                "kind": "generic_input",
                "group_id": str(slot_id),
                "category": 2,
                "cardinality": len(vars_by_commodity),
                "selected_value": str(selected),
                "variables": vars_by_commodity,
            }
        )
    for slot_id, vars_by_commodity in model.generic_output_vars.items():
        selected = generic_outputs.get(slot_id)
        if selected not in vars_by_commodity:
            raise base.ProtocolViolation(
                f"selection missing generic output choice for variable group {slot_id}"
            )
        groups.append(
            {
                "kind": "generic_output",
                "group_id": str(slot_id),
                "category": 3,
                "cardinality": len(vars_by_commodity),
                "selected_value": str(selected),
                "variables": vars_by_commodity,
            }
        )
    groups.sort(
        key=lambda item: (
            int(item["category"]),
            int(item["cardinality"]),
            str(item["group_id"]),
        )
    )
    return groups


def _select_open_groups(
    groups: Sequence[Mapping[str, Any]],
    target_product: int,
) -> tuple[list[Mapping[str, Any]], int]:
    if target_product < 1:
        raise base.ProtocolViolation("slice target_product must be positive")
    product = 1
    selected: list[Mapping[str, Any]] = []
    for group in groups:
        cardinality = int(group["cardinality"])
        if cardinality <= 1:
            continue
        if product * cardinality <= target_product:
            selected.append(group)
            product *= cardinality
    return selected, product


def _freeze_closed_groups(
    model: base.PortBindingModel,
    groups: Sequence[Mapping[str, Any]],
    open_group_ids: set[tuple[str, str]],
) -> int:
    frozen_count = 0
    for group in groups:
        key = (str(group["kind"]), str(group["group_id"]))
        if key in open_group_ids:
            continue
        variables = group["variables"]
        selected_value = group["selected_value"]
        model.model.Add(variables[selected_value] == 1)
        frozen_count += 1
    return frozen_count


def _slice_progress(
    path: Path,
    *,
    run_id: str,
    layout_id: str,
    stage: str,
    started: float,
    counters: Mapping[str, int],
    extra: Mapping[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": "zmd_phase_minus1_v2_slice_progress_v1",
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "harness_revision": HARNESS_REVISION,
        "run_id": run_id,
        "layout_id": layout_id,
        "stage": stage,
        "elapsed_wall_seconds": time.perf_counter() - started,
        "updated_at_utc": _now_utc(),
        "counters": dict(counters),
    }
    if extra:
        payload["details"] = dict(extra)
    _write_json(path, payload)


def _run_slice_child(
    *,
    run_id: str,
    output_path: Path,
    progress_path: Path,
    event_path: Path,
    feedback_path: Path,
) -> int:
    manifest = _load_manifest()
    _assert_frozen_contract(manifest)
    run_record = _manifest_run(manifest, "slice_runs", run_id)
    layout_id = str(run_record["layout_id"])
    target_product = int(run_record["target_product"])
    record = base._record_by_id(manifest, layout_id)
    frozen = base._load_frozen_inputs(manifest)
    started = time.perf_counter()
    counters = {
        "binding_solves": 0,
        "binding_proposals": 0,
        "routing_prechecks": 0,
        "routing_solves": 0,
        "feedback_applied": 0,
    }
    try:
        layout = base._load_layout(record, manifest, frozen)
        core = base._occupied_core(layout, frozen)
        model = base._new_binding_model(layout, frozen)
        _slice_progress(
            progress_path,
            run_id=run_id,
            layout_id=layout_id,
            stage="base_binding_solve",
            started=started,
            counters=counters,
        )
        initial_status = str(model.solve(BINDING_SECONDS))
        counters["binding_solves"] += 1
        if initial_status != "FEASIBLE":
            receipt = {
                "schema_version": "zmd_phase_minus1_v2_slice_receipt_v1",
                "research_only": True,
                "non_authorizing": True,
                "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
                "harness_revision": HARNESS_REVISION,
                "repository_head": base._git("rev-parse", "HEAD"),
                "run_id": run_id,
                "layout_id": layout_id,
                "target_product": target_product,
                "terminalStatus": (
                    "SLICE_BINDING_EXHAUSTED"
                    if initial_status == "INFEASIBLE"
                    else "UNKNOWN"
                ),
                "censorStatus": (
                    "UNCENSORED"
                    if initial_status == "INFEASIBLE"
                    else "SLICE_SOLVER_TIMEOUT_BINDING"
                ),
                "finalReason": "base_binding_not_feasible",
                "initial_binding_status": initial_status,
                "counters": counters,
                "scope_warning": (
                    "restricted binding-domain slice only; not a full-layout conclusion"
                ),
                "D3_status": D3_D4_STATUS,
                "D4_status": D3_D4_STATUS,
            }
            _write_json(output_path, receipt)
            return 0

        initial_selection = model.extract_selection()
        initial_port_specs = model.extract_port_specs()
        initial_precheck = base.run_exact_routing_precheck(
            placement_core=core,
            port_specs=initial_port_specs,
        )
        conflict_ids = {
            str(item)
            for item in initial_precheck.get("placement_level_conflict_set", [])
        }
        groups = _variable_groups(model, initial_selection, conflict_ids)
        open_groups, actual_product = _select_open_groups(groups, target_product)
        open_ids = {
            (str(group["kind"]), str(group["group_id"])) for group in open_groups
        }
        frozen_group_count = _freeze_closed_groups(model, groups, open_ids)
        slice_spec = {
            "target_product": target_product,
            "actual_product_upper_bound": actual_product,
            "open_group_count": len(open_groups),
            "frozen_group_count": frozen_group_count,
            "open_groups": [
                {
                    "kind": group["kind"],
                    "group_id": group["group_id"],
                    "category": group["category"],
                    "cardinality": group["cardinality"],
                }
                for group in open_groups
            ],
            "selection_order_contract": (
                "conflict binding; other binding; generic input; generic output; "
                "then cardinality/group_id"
            ),
            "initial_precheck_status": str(initial_precheck.get("status", "")),
            "initial_conflict_instance_count": len(conflict_ids),
        }
        _slice_progress(
            progress_path,
            run_id=run_id,
            layout_id=layout_id,
            stage="slice_frozen",
            started=started,
            counters=counters,
            extra=slice_spec,
        )

        terminal_status = "UNKNOWN"
        censor_status = "UNCENSORED"
        final_reason = "unknown_other"
        pending_feedback: MutableMapping[str, Any] | None = None
        event_index = 0
        with r3.CompactJournal(event_path) as events, r3.CompactJournal(
            feedback_path
        ) as feedback:
            while True:
                binding_status = str(model.solve(BINDING_SECONDS))
                counters["binding_solves"] += 1
                if pending_feedback is not None:
                    next_selection = (
                        model.extract_selection() if binding_status == "FEASIBLE" else None
                    )
                    outcome = r3._feedback_outcome_record(
                        applied=pending_feedback,
                        next_status=binding_status,
                        next_selection=next_selection,
                    )
                    feedback.append(outcome)
                    pending_feedback = None

                if binding_status == "INFEASIBLE":
                    terminal_status = "SLICE_BINDING_EXHAUSTED"
                    final_reason = "restricted_binding_domain_exhausted"
                    break
                if binding_status != "FEASIBLE":
                    terminal_status = "UNKNOWN"
                    censor_status = "SLICE_SOLVER_TIMEOUT_BINDING"
                    final_reason = "slice_binding_timeout"
                    break

                counters["binding_proposals"] += 1
                selection = model.extract_selection()
                port_specs = model.extract_port_specs()
                counters["routing_prechecks"] += 1
                precheck = base.run_exact_routing_precheck(
                    placement_core=core,
                    port_specs=port_specs,
                )
                replay = base.run_exact_routing_precheck(
                    placement_core=core,
                    port_specs=port_specs,
                )
                precheck_status = str(precheck.get("status", ""))
                if precheck_status in base.ROUTING_DOMAIN_PROOF_REJECT_STATUSES:
                    if not bool(precheck.get("binding_selection_safe_reject", False)):
                        raise base.ProtocolViolation(
                            f"slice precheck {precheck_status} did not authorize reject"
                        )
                    event_index += 1
                    event = r3._compact_blocked_precheck(
                        layout=layout,
                        selection=selection,
                        precheck=precheck,
                        replay=replay,
                        event_index=event_index,
                    )
                    events.append(event)
                    feedback_id = f"{run_id}:{event_index}"
                    applied = r3._feedback_applied_record(
                        feedback_id=feedback_id,
                        layout=layout,
                        selection=selection,
                        producer=f"slice_routing_precheck:{precheck_status}",
                        model=model,
                        event_index=event_index,
                    )
                    model.add_nogood_cut(dict(selection))
                    feedback.append(applied)
                    pending_feedback = applied
                    counters["feedback_applied"] += 1
                elif precheck_status == base.ROUTING_DOMAIN_STATUS_FEASIBLE:
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
                    route_model.build()
                    counters["routing_solves"] += 1
                    routing_status = str(route_model.solve(ROUTING_SECONDS))
                    if routing_status == "FEASIBLE":
                        terminal_status = "SLICE_FEASIBLE"
                        final_reason = "restricted_slice_routing_feasible"
                        break
                    if routing_status == "TIMEOUT":
                        terminal_status = "UNKNOWN"
                        censor_status = "SLICE_SOLVER_TIMEOUT_ROUTING"
                        final_reason = "slice_routing_timeout"
                        break
                    if routing_status != "INFEASIBLE":
                        raise base.ProtocolViolation(
                            f"unexpected slice routing status: {routing_status}"
                        )
                    event_index += 1
                    event = r3._compact_routing_event(
                        layout=layout,
                        selection=selection,
                        routing_status=routing_status,
                        event_index=event_index,
                        route_model=route_model,
                    )
                    events.append(event)
                    feedback_id = f"{run_id}:{event_index}"
                    applied = r3._feedback_applied_record(
                        feedback_id=feedback_id,
                        layout=layout,
                        selection=selection,
                        producer="slice_routing_solve:INFEASIBLE",
                        model=model,
                        event_index=event_index,
                    )
                    model.add_nogood_cut(dict(selection))
                    feedback.append(applied)
                    pending_feedback = applied
                    counters["feedback_applied"] += 1
                else:
                    raise base.ProtocolViolation(
                        f"unexpected slice precheck status: {precheck_status!r}"
                    )

                if counters["feedback_applied"] % 10 == 0:
                    _slice_progress(
                        progress_path,
                        run_id=run_id,
                        layout_id=layout_id,
                        stage="slice_enumerating",
                        started=started,
                        counters=counters,
                        extra={
                            **slice_spec,
                            "event_record_count": events.count,
                            "feedback_record_count": feedback.count,
                        },
                    )

        exact = _journal_exact_counts(event_path, feedback_path)
        receipt = {
            "schema_version": "zmd_phase_minus1_v2_slice_receipt_v1",
            "research_only": True,
            "non_authorizing": True,
            "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
            "harness_revision": HARNESS_REVISION,
            "repository_head": base._git("rev-parse", "HEAD"),
            "run_id": run_id,
            "layout_id": layout_id,
            "stratum": record["stratum"],
            "target_product": target_product,
            "terminalStatus": terminal_status,
            "censorStatus": censor_status,
            "finalReason": final_reason,
            "slice_spec": slice_spec,
            "counters": counters,
            "journal_derived_exact_counts": exact,
            "elapsed_wall_seconds": time.perf_counter() - started,
            "scope_warning": (
                "restricted binding-domain slice only; not a full-layout conclusion"
            ),
            "D3_status": D3_D4_STATUS,
            "D4_status": D3_D4_STATUS,
            "compilation_status": "DEFERRED_BY_OWNER",
            "consumer_status": "NOT_RUN",
        }
        _write_json(output_path, receipt)
        _slice_progress(
            progress_path,
            run_id=run_id,
            layout_id=layout_id,
            stage="terminal_receipt_ready",
            started=started,
            counters=counters,
            extra={
                "terminalStatus": terminal_status,
                "censorStatus": censor_status,
            },
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        receipt = {
            "schema_version": "zmd_phase_minus1_v2_slice_receipt_v1",
            "research_only": True,
            "non_authorizing": True,
            "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
            "harness_revision": HARNESS_REVISION,
            "repository_head": base._git("rev-parse", "HEAD"),
            "run_id": run_id,
            "layout_id": layout_id,
            "target_product": target_product,
            "terminalStatus": "UNKNOWN",
            "censorStatus": "SLICE_HARNESS_ERROR",
            "finalReason": "slice_exception",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "counters": counters,
            "scope_warning": (
                "restricted binding-domain slice only; not a full-layout conclusion"
            ),
            "D3_status": D3_D4_STATUS,
            "D4_status": D3_D4_STATUS,
        }
        _write_json(output_path, receipt)
        return 70


def _run_deep_child(
    *,
    run_id: str,
    output_path: Path,
    progress_path: Path,
    event_path: Path,
    feedback_path: Path,
) -> int:
    manifest = _load_manifest()
    _assert_frozen_contract(manifest)
    run_record = _manifest_run(manifest, "deep_runs", run_id)
    layout_id = str(run_record["layout_id"])
    return r3._run_layout_command(
        layout_id,
        output_path,
        progress_path,
        event_path,
        feedback_path,
    )


def _aggregate_final(output_root: Path, manifest: Mapping[str, Any]) -> None:
    deep_receipts: list[Mapping[str, Any]] = []
    for run_record in manifest["deep_runs"]:
        path = output_root / "deep" / str(run_record["run_id"]) / "layout_receipt.json"
        if path.is_file():
            payload = _read_json(path)
            if isinstance(payload, Mapping):
                deep_receipts.append(payload)
    slice_receipts: list[Mapping[str, Any]] = []
    for run_record in manifest["slice_runs"]:
        path = output_root / "slices" / str(run_record["run_id"]) / "slice_receipt.json"
        if path.is_file():
            payload = _read_json(path)
            if isinstance(payload, Mapping):
                slice_receipts.append(payload)

    full_terminal = [
        item
        for item in deep_receipts
        if item.get("terminalStatus")
        in {"FULL_LAYOUT_FEASIBLE", "FULL_LAYOUT_BINDING_EXHAUSTED"}
    ]
    terminal_or_saturated = [
        item
        for item in deep_receipts
        if item.get("terminalStatus")
        in {"FULL_LAYOUT_FEASIBLE", "FULL_LAYOUT_BINDING_EXHAUSTED"}
        or item.get("censorStatus") == "WINDOW_SATURATED"
    ]
    covered_strata = {str(item.get("stratum")) for item in terminal_or_saturated}
    if full_terminal:
        evidence_class = "V2_FULL_LAYOUT_TERMINAL_OBSERVED"
    elif len(terminal_or_saturated) >= 2 and {
        "postmem_fcl_lift",
        "cross_line_fixed_layout",
    }.issubset(covered_strata):
        evidence_class = "V2_WINDOW_EVIDENCE_READY"
    else:
        evidence_class = "V2_WINDOW_EVIDENCE_INSUFFICIENT"

    exact_slice = [
        item
        for item in slice_receipts
        if item.get("terminalStatus")
        in {"SLICE_FEASIBLE", "SLICE_BINDING_EXHAUSTED"}
        and item.get("censorStatus") == "UNCENSORED"
    ]
    p1_exact = [
        item
        for item in exact_slice
        if int(item.get("target_product", -1)) == 1
    ]
    slice_corrupt = any(
        item.get("censorStatus") in {"SLICE_HARNESS_ERROR", "HARNESS_ERROR"}
        for item in slice_receipts
    )
    if len(exact_slice) >= 5 and len(p1_exact) == 2 and not slice_corrupt:
        slice_status = "PASS"
    elif slice_corrupt:
        slice_status = "FAIL"
    else:
        slice_status = "INCONCLUSIVE"

    summary = {
        "schema_version": "zmd_phase_minus1_v2_batch_summary_v1",
        "research_only": True,
        "non_authorizing": True,
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "harness_revision": HARNESS_REVISION,
        "repository_head": base._git("rev-parse", "HEAD"),
        "evidence_class": evidence_class,
        "slice_calibration_status": slice_status,
        "deep_receipts": [dict(item) for item in deep_receipts],
        "slice_receipts": [dict(item) for item in slice_receipts],
        "D3_status": D3_D4_STATUS,
        "D4_status": D3_D4_STATUS,
        "outer_loop_line_status": "NOT_DECIDED_BY_THIS_PROTOCOL",
        "completed_at_utc": _now_utc(),
    }
    _write_json(output_root / "V2_RUN_SUMMARY.json", summary)


def _run_batch(output_root: Path) -> int:
    manifest = _load_manifest()
    _assert_frozen_contract(manifest)
    frozen = base._load_frozen_inputs(manifest)

    admission = []
    for record in manifest["records"]:
        try:
            layout = base._load_layout(record, manifest, frozen)
            admission.append(
                {
                    "layout_id": record["id"],
                    "status": "ADMITTED",
                    "normalized_sha256": layout.normalized_sha256,
                    "ghost_rect": list(layout.ghost_rect),
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
    _write_json(
        output_root / "CORPUS_ADMISSION.json",
        {
            "schema_version": "zmd_phase_minus1_v2_admission_v1",
            "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
            "records": admission,
        },
    )
    if any(item["status"] != "ADMITTED" for item in admission):
        return 2

    running: dict[str, RunningTask] = {}
    completed: set[str] = set()
    for deep_record in manifest["deep_runs"]:
        task = _start_deep_task(
            manifest=manifest,
            run_record=deep_record,
            output_root=output_root,
        )
        running[task.run_id] = task

    slice_queue = list(manifest["slice_runs"])
    active_slice_id: str | None = None

    try:
        while running or slice_queue:
            if active_slice_id is None and slice_queue:
                slice_record = slice_queue.pop(0)
                task = _start_slice_task(
                    run_record=slice_record,
                    output_root=output_root,
                )
                running[task.run_id] = task
                active_slice_id = task.run_id

            finished_ids: list[str] = []
            for run_id, task in list(running.items()):
                finished = (
                    _monitor_deep(task)
                    if task.kind == "deep"
                    else _monitor_slice(task)
                )
                if finished:
                    finished_ids.append(run_id)
            for run_id in finished_ids:
                task = running.pop(run_id)
                completed.add(run_id)
                if active_slice_id == run_id:
                    active_slice_id = None
            time.sleep(POLL_SECONDS)
    except BaseException:
        for task in running.values():
            task.termination_reason = "EXTERNAL_INTERRUPT"
            _terminate_process_group(task.process)
            try:
                if task.kind == "deep":
                    _finalize_deep_task(task)
                else:
                    _finalize_slice_timeout(task)
            finally:
                _close_task_log(task)
        raise

    _aggregate_final(output_root, manifest)
    return 0


def _validate() -> int:
    manifest = _load_manifest()
    _assert_frozen_contract(manifest)
    frozen = base._load_frozen_inputs(manifest)
    records = []
    normalized_seen: set[str] = set()
    for record in manifest["records"]:
        layout = base._load_layout(record, manifest, frozen)
        if layout.normalized_sha256 in normalized_seen:
            raise base.ProtocolViolation(
                f"duplicate normalized layout: {layout.normalized_sha256}"
            )
        normalized_seen.add(layout.normalized_sha256)
        records.append(
            {
                "layout_id": record["id"],
                "status": "ADMITTED",
                "normalized_sha256": layout.normalized_sha256,
                "ghost_rect": list(layout.ghost_rect),
            }
        )
    payload = {
        "schema_version": "zmd_phase_minus1_v2_validation_v1",
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "records": records,
        "deep_runs": list(manifest["deep_runs"]),
        "slice_runs": list(manifest["slice_runs"]),
        "D3_status": D3_D4_STATUS,
        "D4_status": D3_D4_STATUS,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _selftest() -> int:
    temporary = Path(os.environ.get("TMPDIR", "/tmp")) / (
        f"zmd_phase1_v2_selftest_{os.getpid()}.jsonl"
    )
    try:
        tracker = SaturationTracker(temporary, window_size=10)
        # Window 1 establishes the baseline.  Later windows are identical and
        # should satisfy all frozen distribution criteria.
        for index in range(40):
            event = {
                "familyKey": "front|precheck|point|UNCENSORED",
                "record_type": "routing_precheck_failure",
                "local_signature_digest": "shape-a",
                "local_signature_counts": {"a|b|N|0,1": 1},
                "event_index": index + 1,
            }
            tracker.add(event)
        if len(tracker.complete_windows) != 4:
            raise AssertionError("selftest window count mismatch")
        if not all(
            window["saturated"] for window in tracker.complete_windows[1:]
        ):
            raise AssertionError("selftest stable windows were not saturated")

        dummy_groups = [
            {"cardinality": 4, "kind": "binding_choice", "group_id": "a"},
            {"cardinality": 4, "kind": "binding_choice", "group_id": "b"},
            {"cardinality": 4, "kind": "binding_choice", "group_id": "c"},
            {"cardinality": 4, "kind": "binding_choice", "group_id": "d"},
        ]
        selected, product = _select_open_groups(dummy_groups, 64)
        if product != 64 or len(selected) != 3:
            raise AssertionError("selftest slice product mismatch")
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "saturation_windows": len(tracker.complete_windows),
                    "slice_product": product,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        temporary.unlink(missing_ok=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    subparsers.add_parser("selftest")

    deep = subparsers.add_parser("deep-child")
    deep.add_argument("--run-id", required=True)
    deep.add_argument("--output", type=Path, required=True)
    deep.add_argument("--progress", type=Path, required=True)
    deep.add_argument("--events", type=Path, required=True)
    deep.add_argument("--feedback", type=Path, required=True)

    slice_child = subparsers.add_parser("slice-child")
    slice_child.add_argument("--run-id", required=True)
    slice_child.add_argument("--output", type=Path, required=True)
    slice_child.add_argument("--progress", type=Path, required=True)
    slice_child.add_argument("--events", type=Path, required=True)
    slice_child.add_argument("--feedback", type=Path, required=True)

    batch = subparsers.add_parser("batch")
    batch.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        return _validate()
    if args.command == "selftest":
        return _selftest()
    if args.command == "deep-child":
        return _run_deep_child(
            run_id=args.run_id,
            output_path=args.output.resolve(),
            progress_path=args.progress.resolve(),
            event_path=args.events.resolve(),
            feedback_path=args.feedback.resolve(),
        )
    if args.command == "slice-child":
        return _run_slice_child(
            run_id=args.run_id,
            output_path=args.output.resolve(),
            progress_path=args.progress.resolve(),
            event_path=args.events.resolve(),
            feedback_path=args.feedback.resolve(),
        )
    if args.command == "batch":
        return _run_batch(args.output_dir.resolve())
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
