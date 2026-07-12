"""Append-only JSONL cut ledger — audit channel only (批E / RFC-003 rev2).

NON-CONSUMPTION ISOLATION (spec 08 D-1, owner-approved waiver 2026-07-12):
this ledger records cut lifecycle *facts* (audit, per-epoch dedup accounting,
rollback-drill evidence). Nothing read from disk by this module may ever feed
cut generation, validation, compilation, selection, or master application.
Restart re-qualification is regeneration through the typed chain (V82
philosophy), never ledger replay. Any future consumption role requires a new
spec + review round (08 spec §3 registers the deferred (a)-upgrade path).

Persistence protocol (spec 08 D-5/D-6):
- per-writer segment files, created O_CREAT|O_EXCL; a segment is NEVER
  re-opened for append — restart/rotation always starts a fresh segment;
- first line is a GENESIS event carrying writer identity + predecessor
  lineage (previous segment path/tail hash, recovery reason, solver context);
- per-segment monotonic ``seq`` + ``prev_event_hash`` chain (SHA-256 of the
  previous serialized line, GENESIS anchored to the declared predecessor);
- every event: single-line canonical JSON, write + flush (process-crash
  durability); APPLIED/POISONED/GENESIS/SEGMENT_SEAL/EPOCH_CLOSED are
  additionally fsync'd (power-loss durability for load-bearing events) and a
  failed write/flush/fsync raises ``LedgerWriteError`` — callers must treat
  that as poison + abort (spec 08 D-4), not as a skippable warning;
- GENERATED/REJECTED and other high-frequency events are best-effort
  telemetry under power loss: they must never support completeness or
  negative assertions (spec 08 D-6) — those accept ``complete`` segments only.

Reader tri-state (spec 08 D-6): ``complete`` (clean chain ending in
SEGMENT_SEAL) / ``truncated`` (clean prefix, crash-shaped tail at EOF) /
``corrupt`` (chain/seq/parse violation before EOF). Consumption always stops
at the last clean prefix; only ``complete`` segments support negative
("zero APPLIED") conclusions.

This module is deliberately outside the close-kernel floor/sink set: it is an
audit channel, not a proof channel (spec 08 §5). It must stay import-free of
oracle/registry/master modules so the non-consumption isolation is visible in
the import graph.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from src.io.strict_json import loads_strict_json

LEDGER_SCHEMA_VERSION = "cut-ledger-v1"

_GENESIS_ANCHOR = "0" * 64

#: Full event vocabulary (spec 08 D-7): RFC-003 §2 eight words + F5 shadow
#: variant + structural events.
EVENT_TYPES = frozenset(
    {
        "GENESIS",
        "GENERATED",
        "REJECTED",
        "VALIDATED",
        "SHADOW",
        "PREPARED",
        "APPLIED",
        "HELD",
        "QUARANTINED",
        "SUPERSEDED",
        "POISONED",
        "EPOCH_CLOSED",
        "SEGMENT_SEAL",
    }
)

#: Events whose loss under power failure is not acceptable (spec 08 D-6).
FSYNC_EVENT_TYPES = frozenset(
    {"GENESIS", "APPLIED", "POISONED", "EPOCH_CLOSED", "SEGMENT_SEAL"}
)


class LedgerWriteError(RuntimeError):
    """A ledger write/flush/fsync failed.

    Spec 08 D-4: the caller must poison + abort the surrounding solve — once
    the audit channel is broken no further trusted conclusions may be minted.
    """


class LedgerUsageError(ValueError):
    """The caller violated the ledger writing protocol (bad event, reuse
    after seal, unknown event type)."""


def _sha256_line(line_bytes: bytes) -> str:
    return hashlib.sha256(line_bytes).hexdigest()


def _canonical_event_line(event: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(event), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def default_writer_id() -> str:
    return f"{socket.gethostname()}-pid{os.getpid()}"


def _fsync_directory(directory: Path) -> None:
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class CutLedgerWriter:
    """Single-writer append-only segment (spec 08 D-5).

    One instance owns exactly one segment file for its whole life; ``seal()``
    (or the context manager exit) writes SEGMENT_SEAL and closes it. Creating
    a writer never touches an existing file (O_CREAT|O_EXCL scan).
    """

    def __init__(
        self,
        root_dir: Path,
        *,
        scope_id: str,
        genesis_context: Optional[Mapping[str, Any]] = None,
        writer_id: Optional[str] = None,
    ) -> None:
        if not scope_id or "/" in scope_id:
            raise LedgerUsageError(f"invalid scope_id: {scope_id!r}")
        self._writer_id = writer_id or default_writer_id()
        self._scope_id = scope_id
        self._dir = Path(root_dir) / scope_id
        self._dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        self._prev_hash = _GENESIS_ANCHOR
        self._sealed = False
        self._fd = -1
        self._path = self._create_segment_exclusive()
        _fsync_directory(self._dir)
        genesis: Dict[str, Any] = dict(genesis_context or {})
        genesis.setdefault("predecessor_segment", None)
        genesis.setdefault("predecessor_tail_hash", None)
        genesis.setdefault("recovery_reason", "fresh_start")
        self.append("GENESIS", genesis)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def writer_id(self) -> str:
        return self._writer_id

    @property
    def tail_hash(self) -> str:
        return self._prev_hash

    def _create_segment_exclusive(self) -> Path:
        for segment_seq in range(100_000):
            candidate = (
                self._dir / f"segment_{self._writer_id}_{segment_seq:05d}.jsonl"
            )
            try:
                self._fd = os.open(
                    str(candidate), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644
                )
            except FileExistsError:
                continue
            return candidate
        raise LedgerWriteError(
            f"could not allocate a fresh segment under {self._dir}"
        )

    def append(self, event_type: str, fields: Mapping[str, Any]) -> Dict[str, Any]:
        """Append one event; returns the full event dict as written."""
        if self._sealed:
            raise LedgerUsageError("segment already sealed; open a new segment")
        if event_type not in EVENT_TYPES:
            raise LedgerUsageError(f"unknown ledger event type: {event_type!r}")
        reserved = {"seq", "event", "prev_event_hash", "schema_version"}
        clash = reserved.intersection(fields)
        if clash:
            raise LedgerUsageError(f"caller may not set reserved fields: {clash}")
        event: Dict[str, Any] = dict(fields)
        event["schema_version"] = LEDGER_SCHEMA_VERSION
        event["event"] = event_type
        event["seq"] = self._seq
        event["prev_event_hash"] = self._prev_hash
        event.setdefault("writer_id", self._writer_id)
        event.setdefault("scope_id", self._scope_id)
        event.setdefault("wallclock_utc", time.time())
        line = _canonical_event_line(event)
        try:
            os.write(self._fd, line + b"\n")
            # os.write on a raw fd is unbuffered; the "flush" tier of D-6 is
            # already satisfied. fsync below is the power-loss tier.
            if event_type in FSYNC_EVENT_TYPES:
                os.fsync(self._fd)
        except OSError as exc:  # pragma: no cover - exercised via monkeypatch
            raise LedgerWriteError(f"ledger write failed: {exc}") from exc
        self._seq += 1
        self._prev_hash = _sha256_line(line)
        if event_type == "SEGMENT_SEAL":
            self._sealed = True
            try:
                os.close(self._fd)
            except OSError as exc:  # pragma: no cover
                raise LedgerWriteError(f"ledger close failed: {exc}") from exc
            self._fd = -1
        return event

    def seal(self, fields: Optional[Mapping[str, Any]] = None) -> None:
        if self._sealed:
            return
        self.append("SEGMENT_SEAL", dict(fields or {}))

    def __enter__(self) -> "CutLedgerWriter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is None:
            self.seal()
            return
        # Abnormal exit: do NOT write a seal (the segment must read as
        # truncated/unsealed evidence of the crash); just release the fd.
        if self._fd >= 0:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = -1
            self._sealed = True


@dataclass(frozen=True)
class SegmentReadResult:
    """Tri-state segment read (spec 08 D-6)."""

    status: str  # "complete" | "truncated" | "corrupt"
    events: Tuple[Dict[str, Any], ...]
    detail: str
    tail_hash: str
    bad_offset: Optional[int] = None

    @property
    def supports_negative_assertions(self) -> bool:
        return self.status == "complete"


def read_segment(path: Path) -> SegmentReadResult:
    """Read one segment fail-closed.

    Consumption stops at the first anomaly; the clean prefix before it is
    returned. An anomaly at EOF on the final line is ``truncated``
    (crash-shaped); an anomaly followed by further data is ``corrupt``.
    """
    raw = Path(path).read_bytes()
    lines = raw.split(b"\n")
    # A well-formed file ends with a trailing newline → last split item empty.
    trailing_complete = len(lines) >= 1 and lines[-1] == b""
    if trailing_complete:
        lines = lines[:-1]
    events: list[Dict[str, Any]] = []
    prev_hash = _GENESIS_ANCHOR
    offset = 0
    for index, line in enumerate(lines):
        is_last = index == len(lines) - 1
        crash_shaped = is_last and not trailing_complete

        def _stop(reason: str) -> SegmentReadResult:
            status = "truncated" if crash_shaped else "corrupt"
            return SegmentReadResult(
                status=status,
                events=tuple(events),
                detail=reason,
                tail_hash=prev_hash,
                bad_offset=offset,
            )

        try:
            parsed_any = loads_strict_json(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return _stop(f"line {index}: unparseable ({exc})")
        if not isinstance(parsed_any, dict):
            return _stop(f"line {index}: event is not an object")
        parsed: Dict[str, Any] = parsed_any
        if parsed.get("schema_version") != LEDGER_SCHEMA_VERSION:
            return _stop(f"line {index}: schema_version mismatch")
        if parsed.get("event") not in EVENT_TYPES:
            return _stop(f"line {index}: unknown event type")
        if index == 0 and parsed.get("event") != "GENESIS":
            return _stop("line 0: first event must be GENESIS")
        if parsed.get("seq") != index:
            return _stop(f"line {index}: seq {parsed.get('seq')!r} != {index}")
        if parsed.get("prev_event_hash") != prev_hash:
            # A chain mismatch at line k contradicts the *stored* line k-1:
            # either k-1's bytes were modified or k's prev field was forged.
            # Trust neither — drop the last accepted event from the prefix.
            if events:
                events.pop()
            return _stop(
                f"line {index}: prev_event_hash chain mismatch "
                "(predecessor unattested, dropped from prefix)"
            )
        # Re-serialize canonically to verify the stored line *is* the
        # canonical form the chain hashed (tamper via re-formatting shows up).
        if _canonical_event_line(parsed) != line:
            return _stop(f"line {index}: non-canonical line bytes")
        events.append(parsed)
        prev_hash = _sha256_line(line)
        offset += len(line) + 1
    if events and events[-1]["event"] == "SEGMENT_SEAL":
        return SegmentReadResult(
            status="complete",
            events=tuple(events),
            detail="sealed",
            tail_hash=prev_hash,
        )
    return SegmentReadResult(
        status="truncated",
        events=tuple(events),
        detail="no SEGMENT_SEAL (unsealed or crashed writer)",
        tail_hash=prev_hash,
    )


def read_scope(root_dir: Path, scope_id: str) -> Dict[str, SegmentReadResult]:
    """Read every segment of a scope, keyed by file name (audit view)."""
    scope_dir = Path(root_dir) / scope_id
    results: Dict[str, SegmentReadResult] = {}
    if not scope_dir.is_dir():
        return results
    for path in sorted(scope_dir.glob("segment_*.jsonl")):
        results[path.name] = read_segment(path)
    return results
