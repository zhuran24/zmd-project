"""Benders rejection contract: declared/deferred, with no production emitter."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from src.cuts.ledger import CutLedgerWriter, read_segment
from src.models.cut_manager import CutManager
from src.search.benders_loop import LBBDController
from src.tests.cuts.rule_cut_evolution import rejection_adapters
from src.tests.cuts.rule_cut_evolution.rejection_audit import (
    PremiseVerdict,
    REJECTION_ADAPTER_SPECS_V1,
    RejectionAdapterStage,
)
from src.tests.test_batch_e_rfc003_gates import _attach
from src.tests.test_cut_framework_attach_wiring import _bound_region_world


def _region_controller(
    master: Any,
    *,
    project_root: Path,
    ledger: CutLedgerWriter | None = None,
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
        enabled_cut_families=["region_capacity"],
    )


def _rejected_events(writer: CutLedgerWriter) -> list[dict[str, Any]]:
    return [
        event
        for event in read_segment(writer.path).events
        if event["event"] == "REJECTED"
    ]


def test_benders_adapter_is_declared_deferred_and_has_no_observer() -> None:
    adapter = REJECTION_ADAPTER_SPECS_V1[
        "benders.framework_rejection_audit.v1"
    ]

    assert adapter.integration_stage is RejectionAdapterStage.DECLARED_DEFERRED
    assert adapter.source.module == "src.search.benders_loop"
    assert adapter.source.qualname == "LBBDController._maybe_attach_framework_cuts"
    assert "observe_benders" not in rejection_adapters.__all__
    assert tuple(binding.reason_code for binding in adapter.reason_bindings) == (
        "adapter",
        "registry",
        "envelope",
        "scope",
        "proof",
        "plan",
        "attach_timing",
        "semantic_duplicate",
    )
    assert all(
        any(verdict is not PremiseVerdict.SATISFIED for verdict in binding.premise_verdicts)
        for binding in adapter.reason_bindings
    )


def test_benders_production_api_and_attach_source_have_no_audit_sink() -> None:
    constructor = inspect.signature(LBBDController.__init__)
    attach_source = inspect.getsource(LBBDController._maybe_attach_framework_cuts)

    assert "rejection_audit_sink" not in constructor.parameters
    for forbidden in (
        "RejectionRecordV1",
        "emit_rejection_audit",
        "rejection_audit_sink",
        "rejection_record_v1",
    ):
        assert forbidden not in attach_source


def test_default_rejection_ledger_shape_has_no_sidecar_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.typed_platform as typed_platform

    class StrForbidden(ValueError):
        def __str__(self) -> str:
            raise AssertionError("production path touched offline audit detail")

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(
        tmp_path / "ledger",
        scope_id="audit-absent",
        writer_id="w1",
    )
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
    assert {
        "event",
        "cut_id",
        "reason_code",
        "trigger",
        "iteration",
        "epoch_instance_id",
        "epoch_semantic_digest",
    } <= set(event)
    assert "rejection_record_v1" not in event
    assert "audit_record_digest" not in event


def test_apply_tcb_fault_stays_poisoned_and_propagates_by_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.lifecycle as lifecycle

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(
        tmp_path / "ledger",
        scope_id="audit-poison",
        writer_id="w1",
    )
    controller = _region_controller(
        master,
        project_root=tmp_path / "controller",
        ledger=ledger,
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
    assert "audit_record_digest" not in poisoned[0]
    assert not any(event["event"] == "APPLIED" for event in events)
    assert int(master.build_stats.get("coordinate_framework_cut_count", 0)) == 0
