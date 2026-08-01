"""Focused zero-authority tests for explicit AB16 immutable writer adapters."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from docs.research.noncert_cuts_ab16_20260724.ab16_budgeted_writers_v1 import (
    AB16BudgetedCutLedgerWriter,
    AB16BudgetedCutManager,
)
from src.cuts.ledger import CutLedgerWriter, LedgerWriteError


class _Budget:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.fail_at = fail_at
        self.calls: list[dict[str, object]] = []

    def append_segment(
        self,
        channel: str,
        sequence: int,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
    ) -> dict[str, object]:
        assert len(raw) <= maximum_bytes
        if self.fail_at == sequence:
            raise RuntimeError("injected pre-write budget exhaustion")
        call = {
            "arm_slot": arm_slot,
            "artifact_class": artifact_class,
            "channel": channel,
            "maximum_bytes": maximum_bytes,
            "raw": raw,
            "sequence": sequence,
        }
        self.calls.append(call)
        return {
            "path": f"channels/{channel}/segment-{sequence:08d}.bin",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }


def test_cut_ledger_default_path_is_byte_compatible(tmp_path: Path) -> None:
    writer = CutLedgerWriter(tmp_path, scope_id="scope", writer_id="writer")
    writer.append("GENERATED", {"cut_id": "one"})
    writer.seal()
    assert writer.path.is_file()
    assert b'"event":"GENERATED"' in writer.path.read_bytes()


def test_budgeted_cut_ledger_never_creates_mutable_local_path(tmp_path: Path) -> None:
    budget = _Budget()
    writer = AB16BudgetedCutLedgerWriter(
        tmp_path / "must-remain-absent",
        scope_id="scope",
        writer_id="writer",
        immutable_budget=budget,
        budget_channel="arm-ledger",
        budget_segment_max_bytes=4096,
        budget_arm_slot="arm-01",
    )
    writer.append("GENERATED", {"cut_id": "one"})
    writer.seal()

    assert not (tmp_path / "must-remain-absent").exists()
    assert [call["sequence"] for call in budget.calls] == [0, 1, 2]
    assert [event["event"] for event in writer.recorded_events] == [
        "GENESIS",
        "GENERATED",
        "SEGMENT_SEAL",
    ]
    assert len(writer.immutable_segment_records) == 3


def test_budget_exhaustion_happens_before_ledger_state_advances(tmp_path: Path) -> None:
    budget = _Budget(fail_at=1)
    writer = AB16BudgetedCutLedgerWriter(
        tmp_path,
        scope_id="scope",
        writer_id="writer",
        immutable_budget=budget,
        budget_channel="arm-ledger",
        budget_segment_max_bytes=4096,
        budget_arm_slot="arm-01",
    )
    before_tail = writer.tail_hash
    with pytest.raises(LedgerWriteError, match="pre-write budget exhaustion"):
        writer.append("APPLIED", {"cut_id": "one"})
    assert writer.tail_hash == before_tail
    assert [event["event"] for event in writer.recorded_events] == ["GENESIS"]
    assert len(budget.calls) == 1


def test_budgeted_ledger_event_limit_precedes_broker_publication(
    tmp_path: Path,
) -> None:
    budget = _Budget()
    writer = AB16BudgetedCutLedgerWriter(
        tmp_path,
        scope_id="scope",
        writer_id="writer",
        immutable_budget=budget,
        budget_channel="arm-ledger",
        budget_segment_max_bytes=4096,
        budget_arm_slot="arm-01",
        budget_event_limits={"GENERATED": 1},
    )
    writer.append("GENERATED", {"cut_id": "one"})
    calls_before = len(budget.calls)
    records_before = len(writer.immutable_segment_records)
    tail_before = writer.tail_hash

    with pytest.raises(
        LedgerWriteError,
        match="event limit exhausted before publication",
    ):
        writer.append("GENERATED", {"cut_id": "two"})

    assert len(budget.calls) == calls_before
    assert len(writer.immutable_segment_records) == records_before
    assert [event["event"] for event in writer.recorded_events] == [
        "GENESIS",
        "GENERATED",
    ]
    assert writer.tail_hash == tail_before


def test_production_cut_ledger_does_not_expose_budget_options(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        CutLedgerWriter(
            tmp_path,
            scope_id="scope",
            immutable_budget=_Budget(),  # type: ignore[call-arg]
        )


def test_budgeted_cut_manager_publishes_immutable_segments_only(tmp_path: Path) -> None:
    budget = _Budget()
    manager = AB16BudgetedCutManager(
        checkpoint_dir=tmp_path / "must-remain-absent",
        immutable_budget=budget,
        budget_channel="runtime-cuts",
        budget_segment_max_bytes=4096,
        budget_arm_slot="arm-01",
    )
    assert manager.add_cut(
        [{"instance_id": "i", "pose_id": "p"}],
        "reason",
        "source",
    )
    assert not (tmp_path / "must-remain-absent").exists()
    assert len(manager.immutable_segment_records) == 1
    assert budget.calls[0]["artifact_class"] == "ledger"
    assert budget.calls[0]["sequence"] == 0


def test_budgeted_cut_manager_exhaustion_precedes_in_memory_registration(
    tmp_path: Path,
) -> None:
    budget = _Budget(fail_at=0)
    manager = AB16BudgetedCutManager(
        checkpoint_dir=tmp_path,
        immutable_budget=budget,
        budget_channel="runtime-cuts",
        budget_segment_max_bytes=4096,
        budget_arm_slot="arm-01",
    )
    conflict = [{"instance_id": "i", "pose_id": "p"}]
    with pytest.raises(RuntimeError, match="pre-write budget exhaustion"):
        manager.add_cut(conflict, "reason", "source")
    assert manager.get_all_cuts() == []
    assert manager.immutable_segment_records == ()


def test_budgeted_cut_manager_cannot_clear_or_reuse_channel(tmp_path: Path) -> None:
    manager = AB16BudgetedCutManager(
        checkpoint_dir=tmp_path,
        immutable_budget=_Budget(),
        budget_channel="runtime-cuts",
        budget_segment_max_bytes=4096,
        budget_arm_slot="arm-01",
    )
    with pytest.raises(RuntimeError, match="cannot be cleared"):
        manager.clear_all()
