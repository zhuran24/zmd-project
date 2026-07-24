"""Audit-only RejectionRecordV1 integration at Benders terminal seams."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from src.cuts.ledger import CutLedgerWriter, read_segment
from src.cuts.rejection_audit import (
    AuditEmitOutcomeV1,
    RejectionAuditSinkV1,
    RejectionAuditIndexV1,
    RejectionRecordV1,
    rejection_record_ledger_projection_v1,
)
from src.models.cut_manager import CutManager
from src.search.benders_loop import LBBDController
from src.tests.test_batch_e_rfc003_gates import _attach
from src.tests.test_cut_framework_attach_wiring import _bound_region_world


def _rejected_events(writer: CutLedgerWriter) -> list[dict[str, Any]]:
    return [
        event
        for event in read_segment(writer.path).events
        if event["event"] == "REJECTED"
    ]


def _region_controller(
    master: Any,
    *,
    project_root: Path,
    ledger: CutLedgerWriter | None = None,
    audit_sink: RejectionAuditSinkV1 | None = None,
) -> LBBDController:
    checkpoint_dir = project_root / "checkpoint"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return LBBDController(
        master=master,
        cut_manager=CutManager(
            checkpoint_dir=checkpoint_dir,
            solve_mode="certified_exact",
        ),
        project_root=project_root,
        solve_mode="certified_exact",
        cut_ledger=ledger,
        rejection_audit_sink=audit_sink,
        enabled_cut_families=["region_capacity"],
    )


def _only_record(index: RejectionAuditIndexV1) -> RejectionRecordV1:
    assert len(index.records) == 1
    return index.records[0]


def test_cut_rejection_uses_independent_sidecar_and_preserves_outer_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.typed_platform as typed_platform

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path / "ledger", scope_id="audit-scope", writer_id="w1")
    audit_index = RejectionAuditIndexV1()
    controller = _region_controller(
        master,
        project_root=tmp_path / "controller",
        ledger=ledger,
        audit_sink=audit_index,
    )
    rejection = typed_platform.CutRejection(
        stage="scope",
        reason="injected scope mismatch",
        cut_id="cut-under-test",
    )
    monkeypatch.setattr(
        typed_platform,
        "validate_and_compile_cut",
        lambda envelope, snapshot, registry: rejection,
    )

    assert _attach(controller, state, 1) == 0
    ledger.seal()

    event = _rejected_events(ledger)[0]
    assert event["cut_id"] == "cut-under-test"
    assert event["reason_code"] == "scope"
    assert event["reason"] == "injected scope mismatch"
    assert "rejection_record_v1" not in event
    record = cast(
        dict[str, Any],
        rejection_record_ledger_projection_v1(_only_record(audit_index)),
    )
    assert record["schema_version"] == 1
    assert record["adapter_id"] == "benders.framework_rejection_audit.v1"
    assert record["reason_code"] == "scope"
    assert record["reason_detail"] == event["reason"]
    assert record["subject"] == {"kind": "cut_id", "value": event["cut_id"]}
    assert len(str(record["audit_record_digest"])) == 64
    assert record["state_digest"]["availability"] == "available"
    assert record["instance_digest"]["availability"] == "available"
    assert record["assumption_digest"]["availability"] == "available"
    premise_by_id = {
        premise["premise_id"]: premise for premise in record["premises"]
    }
    assert premise_by_id["family_registered"]["verdict"] == "unavailable"
    assert premise_by_id["schema_version_current"]["verdict"] == "satisfied"
    assert premise_by_id["scope_current"]["verdict"] == "violated"
    assert premise_by_id["proof_sound"]["verdict"] == "unavailable"
    assert "not evaluated" not in (
        premise_by_id["proof_sound"]["unavailable_reason"] or ""
    )
    assert int(master.build_stats.get("coordinate_framework_cut_count", 0)) == 0
    stats = master.build_stats["cut_framework_attach_last"]
    assert stats["rejected"]["scope"] >= 1
    assert "rejection_record_v1" not in stats
    assert event["epoch_semantic_digest"] == stats["epoch_semantic_digest"]


def test_rejection_sidecar_is_independent_of_cut_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.typed_platform as typed_platform

    master, state, _group = _bound_region_world()
    audit_index = RejectionAuditIndexV1()
    controller = _region_controller(
        master,
        project_root=tmp_path / "controller",
        audit_sink=audit_index,
    )
    rejection = typed_platform.CutRejection(
        stage="proof",
        reason="independent verifier rejected proof",
        cut_id="cut-without-cut-ledger",
    )
    monkeypatch.setattr(
        typed_platform,
        "validate_and_compile_cut",
        lambda envelope, snapshot, registry: rejection,
    )

    assert _attach(controller, state, 1) == 0
    record = _only_record(audit_index)
    assert record.subject.value == "cut-without-cut-ledger"
    assert record.reason_code == "proof"
    assert int(master.build_stats.get("coordinate_framework_cut_count", 0)) == 0


def test_adapter_failure_keeps_outer_shape_and_records_full_premises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.typed_platform as typed_platform

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path / "ledger", scope_id="audit-adapter", writer_id="w1")
    audit_index = RejectionAuditIndexV1()
    controller = _region_controller(
        master,
        project_root=tmp_path / "controller",
        ledger=ledger,
        audit_sink=audit_index,
    )

    def reject_adapter(cut: Any) -> Any:
        del cut
        raise ValueError("injected adapter rejection")

    monkeypatch.setattr(typed_platform, "cut_to_envelope_v1", reject_adapter)
    assert _attach(controller, state, 1) == 0
    ledger.seal()

    event = _rejected_events(ledger)[0]
    assert event["reason_code"] == "adapter"
    assert "reason" not in event
    assert "rejection_record_v1" not in event
    record = cast(
        dict[str, Any],
        rejection_record_ledger_projection_v1(_only_record(audit_index)),
    )
    assert record["reason_code"] == "adapter"
    assert record["reason_detail"] == "injected adapter rejection"
    premise_ids = [premise["premise_id"] for premise in record["premises"]]
    assert premise_ids == [
        "cut_generated",
        "adapter_admitted",
        "family_registered",
        "schema_version_current",
        "scope_current",
        "proof_sound",
        "plan_sound",
        "semantic_unique",
        "attach_timing_current",
    ]
    assert record["premises"][0]["verdict"] == "satisfied"
    assert record["premises"][1]["verdict"] == "violated"
    assert all(
        premise["verdict"] == "unavailable"
        for premise in record["premises"][2:]
    )
    assert int(master.build_stats.get("coordinate_framework_cut_count", 0)) == 0


def test_semantic_duplicate_uses_existing_fingerprint_as_sidecar_key(
    tmp_path: Path,
) -> None:
    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path / "ledger", scope_id="audit-dedup", writer_id="w1")
    audit_index = RejectionAuditIndexV1()
    controller = _region_controller(
        master,
        project_root=tmp_path / "controller",
        ledger=ledger,
        audit_sink=audit_index,
    )

    first = _attach(controller, state, 1)
    second = _attach(controller, state, 2)
    ledger.seal()

    assert first >= 1
    assert second == 0
    duplicate = next(
        event
        for event in _rejected_events(ledger)
        if event["reason_code"] == "semantic_duplicate"
    )
    assert "rejection_record_v1" not in duplicate
    record = next(
        item
        for item in audit_index.records
        if item.reason_code == "semantic_duplicate"
    )
    assert record.subject.kind.value == "semantic_fingerprint"
    assert record.subject.value == duplicate["semantic_fingerprint"]
    premise_by_id = {premise.premise_id: premise for premise in record.premises}
    assert premise_by_id["plan_sound"].verdict.value == "satisfied"
    assert premise_by_id["semantic_unique"].verdict.value == "violated"
    assert premise_by_id["attach_timing_current"].verdict.value == "unavailable"
    assert len(record.cost.measures) == 1
    assert record.cost.measures[0].unit.value == "wall_time_ns"
    assert record.cost.measures[0].value >= 0


def test_raising_audit_sink_cannot_change_rejection_or_outer_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.typed_platform as typed_platform

    class RaisingSink:
        calls = 0

        def emit(self, record: RejectionRecordV1) -> AuditEmitOutcomeV1:
            del record
            self.calls += 1
            raise RuntimeError("audit transport failed")

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path / "ledger", scope_id="audit-failure", writer_id="w1")
    sink = RaisingSink()
    controller = _region_controller(
        master,
        project_root=tmp_path / "controller",
        ledger=ledger,
        audit_sink=sink,
    )
    rejection = typed_platform.CutRejection(
        stage="scope",
        reason="same terminal reason",
        cut_id="same-cut-id",
    )
    monkeypatch.setattr(
        typed_platform,
        "validate_and_compile_cut",
        lambda envelope, snapshot, registry: rejection,
    )

    assert _attach(controller, state, 1) == 0
    ledger.seal()

    assert sink.calls >= 1
    event = _rejected_events(ledger)[0]
    assert {
        key: event[key]
        for key in ("cut_id", "reason_code", "reason")
    } == {
        "cut_id": "same-cut-id",
        "reason_code": "scope",
        "reason": "same terminal reason",
    }
    assert "rejection_record_v1" not in event
    assert int(master.build_stats.get("coordinate_framework_cut_count", 0)) == 0


def test_default_path_never_stringifies_adapter_exception_for_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.typed_platform as typed_platform

    class StrForbidden(ValueError):
        def __str__(self) -> str:
            raise AssertionError("default path touched audit-only exception detail")

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path / "ledger", scope_id="audit-absent", writer_id="w1")
    controller = _region_controller(
        master,
        project_root=tmp_path / "controller",
        ledger=ledger,
    )

    def reject_adapter(cut: Any) -> Any:
        del cut
        raise StrForbidden()

    monkeypatch.setattr(typed_platform, "cut_to_envelope_v1", reject_adapter)
    assert _attach(controller, state, 1) == 0
    ledger.seal()
    event = _rejected_events(ledger)[0]
    assert event["reason_code"] == "adapter"
    assert "rejection_record_v1" not in event


def test_apply_tcb_fault_stays_poisoned_and_has_no_rejection_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.lifecycle as lifecycle

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path / "ledger", scope_id="audit-poison", writer_id="w1")
    audit_index = RejectionAuditIndexV1()
    controller = _region_controller(
        master,
        project_root=tmp_path / "controller",
        ledger=ledger,
        audit_sink=audit_index,
    )
    sentinel = RuntimeError("injected apply-chain fault")

    def explode(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise sentinel

    monkeypatch.setattr(lifecycle, "step_8_apply_to_master", explode)
    with pytest.raises(RuntimeError) as raised:
        _attach(controller, state, 1)
    assert raised.value is sentinel
    ledger.seal()

    events = read_segment(ledger.path).events
    poisoned = [event for event in events if event["event"] == "POISONED"]
    assert poisoned
    assert poisoned[0]["reason_code"] == "apply_chain_failure"
    assert "rejection_record_v1" not in poisoned[0]
    assert not audit_index.records
    assert not any(event["event"] == "APPLIED" for event in events)
    assert int(master.build_stats.get("coordinate_framework_cut_count", 0)) == 0
