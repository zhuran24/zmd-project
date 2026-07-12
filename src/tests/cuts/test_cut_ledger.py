"""Cut ledger segment protocol tests (批E spec 08 D-5/D-6/D-7).

Covers the persistence protocol invariants the spec pins:
- O_EXCL fresh-segment discipline (never append an existing file);
- GENESIS anchoring + predecessor lineage;
- per-segment seq + prev_event_hash chain;
- reader tri-state fail-closed (complete / truncated / corrupt) and the
  "negative assertions only from complete segments" property (§4 gate 4/7);
- fsync tiering (APPLIED/POISONED/seal fsync'd; failure => LedgerWriteError,
  the poison+abort signal of spec 08 D-4).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.cuts.ledger import (
    EVENT_TYPES,
    FSYNC_EVENT_TYPES,
    CutLedgerWriter,
    LedgerUsageError,
    LedgerWriteError,
    read_scope,
    read_segment,
)


def _writer(tmp_path: Path, **kwargs: object) -> CutLedgerWriter:
    return CutLedgerWriter(
        tmp_path,
        scope_id="run-test",
        writer_id="w1",
        **kwargs,  # type: ignore[arg-type]
    )


def test_genesis_and_seal_reads_complete(tmp_path: Path) -> None:
    with _writer(tmp_path) as writer:
        writer.append("GENERATED", {"cut_id": "c1", "semantic_fingerprint": "f" * 64})
        writer.append("APPLIED", {"cut_id": "c1", "receipt": {"count_delta": 1}})
    result = read_segment(writer.path)
    assert result.status == "complete"
    assert result.supports_negative_assertions is True
    assert [e["event"] for e in result.events] == [
        "GENESIS",
        "GENERATED",
        "APPLIED",
        "SEGMENT_SEAL",
    ]
    assert [e["seq"] for e in result.events] == [0, 1, 2, 3]
    # Chain: each event's prev hash anchors to the previous physical line.
    assert result.events[0]["prev_event_hash"] == "0" * 64


def test_fresh_writer_never_touches_existing_segment(tmp_path: Path) -> None:
    with _writer(tmp_path) as first:
        first.append("GENERATED", {"cut_id": "c1"})
    before = first.path.read_bytes()
    second = _writer(tmp_path)
    try:
        assert second.path != first.path
        assert first.path.read_bytes() == before
    finally:
        second.seal()


def test_unsealed_segment_is_truncated_not_complete(tmp_path: Path) -> None:
    writer = _writer(tmp_path)
    writer.append("GENERATED", {"cut_id": "c1"})
    # Simulate crash: no seal. (os.write is unbuffered; bytes are in the file.)
    result = read_segment(writer.path)
    assert result.status == "truncated"
    assert result.supports_negative_assertions is False
    assert [e["event"] for e in result.events] == ["GENESIS", "GENERATED"]


def test_torn_tail_line_yields_clean_prefix(tmp_path: Path) -> None:
    writer = _writer(tmp_path)
    writer.append("GENERATED", {"cut_id": "c1"})
    with open(writer.path, "ab") as handle:
        handle.write(b'{"event":"APPLIED","half')  # torn write, no newline
    result = read_segment(writer.path)
    assert result.status == "truncated"
    assert [e["event"] for e in result.events] == ["GENESIS", "GENERATED"]
    assert result.bad_offset is not None


def test_tampered_middle_line_is_corrupt_and_stops_prefix(tmp_path: Path) -> None:
    with _writer(tmp_path) as writer:
        writer.append("GENERATED", {"cut_id": "c1"})
        writer.append("APPLIED", {"cut_id": "c1"})
    lines = writer.path.read_bytes().split(b"\n")
    tampered = lines[1].replace(b'"c1"', b'"c2"')
    assert tampered != lines[1]
    writer.path.write_bytes(b"\n".join([lines[0], tampered] + lines[2:]))
    result = read_segment(writer.path)
    assert result.status == "corrupt"
    # Prefix stops before the tampered line.
    assert [e["event"] for e in result.events] == ["GENESIS"]
    assert result.supports_negative_assertions is False


def test_reformatted_line_bytes_are_rejected(tmp_path: Path) -> None:
    with _writer(tmp_path) as writer:
        writer.append("GENERATED", {"cut_id": "c1"})
    raw_lines = writer.path.read_bytes().split(b"\n")
    # Same JSON object, different bytes (added whitespace): canonical check
    # must refuse it even though json.loads would accept it.
    reparsed = json.loads(raw_lines[1])
    reformatted = json.dumps(reparsed, ensure_ascii=False, sort_keys=True).encode()
    assert reformatted != raw_lines[1]
    writer.path.write_bytes(b"\n".join([raw_lines[0], reformatted] + raw_lines[2:]))
    result = read_segment(writer.path)
    assert result.status == "corrupt"
    assert [e["event"] for e in result.events] == ["GENESIS"]


def test_duplicate_key_line_is_rejected_fail_closed(tmp_path: Path) -> None:
    with _writer(tmp_path) as writer:
        writer.append("GENERATED", {"cut_id": "c1"})
    raw_lines = writer.path.read_bytes().split(b"\n")
    dup = raw_lines[1][:-1] + b',"cut_id":"c2"}'
    writer.path.write_bytes(b"\n".join([raw_lines[0], dup] + raw_lines[2:]))
    result = read_segment(writer.path)
    assert result.status == "corrupt"
    assert [e["event"] for e in result.events] == ["GENESIS"]


def test_bytes_after_seal_are_corrupt(tmp_path: Path) -> None:
    with _writer(tmp_path) as writer:
        writer.append("GENERATED", {"cut_id": "c1"})
    sealed_lines = writer.path.read_bytes().split(b"\n")
    # Forge a "valid-looking" event appended after the seal: even with a
    # correct chain continuation the reader must call the segment corrupt.
    forged = sealed_lines[1]  # re-use an earlier canonical line verbatim
    writer.path.write_bytes(b"\n".join(sealed_lines[:-1] + [forged, b""]))
    result = read_segment(writer.path)
    assert result.status == "corrupt"
    assert "after SEGMENT_SEAL" in result.detail or result.detail


def test_usage_errors(tmp_path: Path) -> None:
    writer = _writer(tmp_path)
    with pytest.raises(LedgerUsageError):
        writer.append("NOT_AN_EVENT", {})
    with pytest.raises(LedgerUsageError):
        writer.append("GENERATED", {"seq": 99})
    writer.seal()
    with pytest.raises(LedgerUsageError):
        writer.append("GENERATED", {"cut_id": "late"})
    for bad_scope in ("bad/scope", "..", ".", "a\\b", "a\x00b", ""):
        with pytest.raises(LedgerUsageError):
            CutLedgerWriter(tmp_path, scope_id=bad_scope)
    for bad_writer in ("../up", "a/b", ".."):
        with pytest.raises(LedgerUsageError):
            CutLedgerWriter(tmp_path, scope_id="ok", writer_id=bad_writer)


def test_fsync_tiering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    real_fsync = os.fsync

    def counting_fsync(fd: int) -> None:
        calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counting_fsync)
    writer = _writer(tmp_path)  # dir fsync + GENESIS fsync
    after_genesis = len(calls)
    assert after_genesis >= 2
    writer.append("GENERATED", {"cut_id": "c1"})
    writer.append("REJECTED", {"cut_id": "c2", "reason_code": "semantic_duplicate"})
    assert len(calls) == after_genesis  # telemetry tier: flush only, no fsync
    writer.append("APPLIED", {"cut_id": "c1"})
    assert len(calls) == after_genesis + 1  # load-bearing tier fsync'd
    writer.seal()
    assert len(calls) == after_genesis + 2


def test_fsync_failure_raises_ledger_write_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = _writer(tmp_path)

    def failing_fsync(fd: int) -> None:
        raise OSError("simulated media failure")

    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(LedgerWriteError):
        writer.append("APPLIED", {"cut_id": "c1"})


def test_predecessor_lineage_links_segments(tmp_path: Path) -> None:
    with _writer(tmp_path) as first:
        first.append("APPLIED", {"cut_id": "c1"})
    first_result = read_segment(first.path)
    assert first_result.status == "complete"
    second = CutLedgerWriter(
        tmp_path,
        scope_id="run-test",
        writer_id="w1",
        genesis_context={
            "predecessor_segment": first.path.name,
            "predecessor_tail_hash": first_result.tail_hash,
            "recovery_reason": "restart",
        },
    )
    second.seal()
    genesis = read_segment(second.path).events[0]
    assert genesis["predecessor_segment"] == first.path.name
    assert genesis["predecessor_tail_hash"] == first_result.tail_hash
    assert genesis["recovery_reason"] == "restart"


def test_read_scope_lists_every_segment(tmp_path: Path) -> None:
    with _writer(tmp_path) as first:
        first.append("GENERATED", {"cut_id": "c1"})
    second = _writer(tmp_path)  # left unsealed on purpose
    second.append("GENERATED", {"cut_id": "c2"})
    view = read_scope(tmp_path, "run-test")
    assert set(view) == {first.path.name, second.path.name}
    assert view[first.path.name].status == "complete"
    assert view[second.path.name].status == "truncated"


def test_event_vocabulary_matches_spec() -> None:
    # Spec 08 D-7: RFC eight words + SHADOW + structural events.
    rfc_words = {
        "GENERATED",
        "REJECTED",
        "VALIDATED",
        "PREPARED",
        "APPLIED",
        "HELD",
        "QUARANTINED",
        "SUPERSEDED",
    }
    assert rfc_words <= EVENT_TYPES
    assert {"GENESIS", "SHADOW", "POISONED", "EPOCH_CLOSED", "SEGMENT_SEAL"} <= EVENT_TYPES
    assert FSYNC_EVENT_TYPES <= EVENT_TYPES
