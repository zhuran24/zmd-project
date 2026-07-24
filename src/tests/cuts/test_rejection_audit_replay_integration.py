"""Audit-only replay/CutStore integration parity gates."""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
from dataclasses import fields
from typing import cast

import pytest

import src.cuts.replay as replay_module
from src.cuts.lifecycle import AttachDecision, Cut, OracleCert, compute_source_digest
from src.tests.cuts.rule_cut_evolution import rejection_adapters as adapters_module
from src.tests.cuts.rule_cut_evolution.rejection_adapters import (
    observe_quarantine_transition,
    observe_regression_sweep,
    observe_replay,
)
from src.tests.cuts.rule_cut_evolution.rejection_audit import (
    CostUnit,
    DigestAvailability,
    PremiseVerdict,
    RejectionAuditIndexV1,
    RejectionDisposition,
    RejectionPremiseV1,
    RejectionRecordV1,
)
from src.cuts.replay import (
    DiagnosticResult,
    ReplayContext,
    build_replay_context,
    regression_sweep,
    replay_cut,
)
from src.cuts.store import CutStore, QuarantineReason
from src.tests.cuts.test_family_cutset import _make_cutset_cut
from src.tests.cuts.test_replay import _f1_cut, _f1_state


class _RaisingSink:
    def emit(self, record: object) -> object:
        del record
        raise RuntimeError("audit sink failed")


def _scope_stale_world() -> tuple[Cut, ReplayContext]:
    generation_state = _f1_state()
    cut = _f1_cut(generation_state)
    replay_state = _f1_state()
    object.__setattr__(replay_state, "exterior_blocks", frozenset({(17, 0)}))
    replay_state.source_digest = compute_source_digest(replay_state)
    return cut, build_replay_context(replay_state)


def _integrity_drift_cut() -> tuple[Cut, ReplayContext]:
    state = _f1_state()
    cut = dataclasses.replace(_f1_cut(state), oracle_cert_hash="0" * 64)
    return cut, build_replay_context(state)


def _watcher_projection(store: CutStore) -> tuple[object, ...]:
    return (
        store.quarantined,
        store.held,
        dict(store.by_cell_watcher),
        dict(store.by_group_watcher),
        dict(store.by_pose_watcher),
        dict(store.by_commodity_watcher),
        dict(store.by_region_watcher),
        dict(store.by_ghost_watcher),
    )


def test_frozen_public_signatures_and_dataclass_fields_are_unchanged() -> None:
    replay_signature = inspect.signature(replay_cut)
    assert tuple(replay_signature.parameters) == (
        "cut",
        "store",
        "context",
        "iter_index",
    )
    assert replay_signature.parameters["iter_index"].kind is inspect.Parameter.KEYWORD_ONLY
    assert replay_signature.parameters["iter_index"].default == -1
    assert not hasattr(replay_module, "replay_cut_audited")
    assert not hasattr(replay_module, "regression_sweep_audited")

    sweep_signature = inspect.signature(regression_sweep)
    assert tuple(sweep_signature.parameters) == (
        "store",
        "context",
        "iter_index",
    )
    assert sweep_signature.parameters["iter_index"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sweep_signature.parameters["iter_index"].default == -1

    quarantine_signature = inspect.signature(CutStore.quarantine_cut)
    assert tuple(quarantine_signature.parameters) == ("self", "cut_id", "reason")
    assert tuple(field.name for field in fields(QuarantineReason)) == (
        "reason_code",
        "detail",
        "iter_index",
    )
    assert tuple(field.name for field in fields(CutStore)) == (
        "cuts",
        "by_cell_watcher",
        "by_group_watcher",
        "by_pose_watcher",
        "by_commodity_watcher",
        "by_region_watcher",
        "by_ghost_watcher",
        "quarantined",
        "held",
    )
    assert not hasattr(CutStore, "quarantine_cut_audited")


def test_offline_observer_scope_hold_emits_complete_record_after_transition() -> None:
    cut, context = _scope_stale_world()
    store = CutStore()
    store.add_cut(cut, cell_keys=((0, 0),))
    index = RejectionAuditIndexV1()

    decision = observe_replay(cut, store, context, audit_sink=index)

    assert decision == "HOLD"
    assert cut.cut_id in store.held
    assert cut.cut_id not in store.quarantined
    assert len(index.records) == 1
    record = index.records[0]
    assert record.subject.value == cut.cut_id
    assert record.family == cut.family
    assert record.reason_code == "typed_rejected_scope"
    assert record.disposition is RejectionDisposition.HOLD
    assert tuple(premise.premise_id for premise in record.premises) == (
        "cut_registered",
        "cut_integrity",
        "adapter_representation_valid",
        "replay_validation",
    )
    assert record.premises[-1].verdict is PremiseVerdict.VIOLATED
    assert record.instance_digest.digest == context.snapshot.source_digest
    assert record.state_digest.digest == context.snapshot.digest
    assert (
        record.assumption_digest.availability
        is DigestAvailability.AVAILABLE
    )
    assert tuple(measure.unit for measure in record.cost.measures) == (
        CostUnit.WALL_TIME_NS,
    )


def test_scope_result_for_already_quarantined_cut_emits_no_false_hold_record() -> None:
    cut, context = _scope_stale_world()
    store = CutStore()
    store.add_cut(cut, cell_keys=((0, 0),))
    original_reason = QuarantineReason(
        reason_code="cut_integrity_failed",
        detail="pre-existing terminal quarantine",
        iter_index=3,
    )
    store.quarantine_cut(cut.cut_id, original_reason)
    index = RejectionAuditIndexV1()

    decision = observe_replay(cut, store, context, audit_sink=index)

    assert decision == "HOLD"
    assert cut.cut_id not in store.held
    assert store.quarantined[cut.cut_id] == original_reason
    assert index.records == ()


def test_offline_observer_preserves_quarantine_and_watcher_mutation_parity() -> None:
    cut, context = _integrity_drift_cut()
    normal_store = CutStore()
    audited_store = CutStore()
    normal_store.add_cut(
        cut,
        cell_keys=((0, 0),),
        group_keys=("boundary_io",),
        region_keys=("left_or_bottom_union",),
    )
    audited_store.add_cut(
        cut,
        cell_keys=((0, 0),),
        group_keys=("boundary_io",),
        region_keys=("left_or_bottom_union",),
    )

    normal_decision = replay_cut(cut, normal_store, context, iter_index=7)
    index = RejectionAuditIndexV1()
    audited_decision = observe_replay(
        cut,
        audited_store,
        context,
        iter_index=7,
        audit_sink=index,
    )

    assert audited_decision == normal_decision == "QUARANTINE"
    assert _watcher_projection(audited_store) == _watcher_projection(normal_store)
    assert audited_store.quarantined[cut.cut_id] == QuarantineReason(
        reason_code="cut_integrity_failed",
        detail=normal_store.quarantined[cut.cut_id].detail,
        iter_index=7,
    )
    assert len(index.records) == 1
    record = index.records[0]
    assert record.reason_code == "cut_integrity_failed"
    assert record.disposition is RejectionDisposition.QUARANTINE
    assert record.premises[1].verdict is PremiseVerdict.VIOLATED


def test_adapter_rejection_uses_existing_reason_code() -> None:
    state = _f1_state()
    cut = dataclasses.replace(
        _f1_cut(state),
        is_quarantined=True,
        quarantine_reason="prior quarantine marker",
    )
    store = CutStore()
    store.add_cut(cut)
    index = RejectionAuditIndexV1()

    decision = observe_replay(
        cut,
        store,
        build_replay_context(state),
        audit_sink=index,
    )

    assert decision == "QUARANTINE"
    assert store.quarantined[cut.cut_id].reason_code == "typed_adapter_rejected"
    assert len(index.records) == 1
    assert index.records[0].reason_code == "typed_adapter_rejected"
    assert index.records[0].premises[2].verdict is PremiseVerdict.VIOLATED


def test_sink_and_record_build_failures_cannot_change_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cut, context = _integrity_drift_cut()
    sink_failure_store = CutStore()
    sink_failure_store.add_cut(cut, cell_keys=((0, 0),))

    assert (
        observe_replay(
            cut,
            sink_failure_store,
            context,
            audit_sink=_RaisingSink(),  # type: ignore[arg-type]
        )
        == "QUARANTINE"
    )
    assert cut.cut_id in sink_failure_store.quarantined
    assert not sink_failure_store.cuts_affected_by_cell((0, 0))

    build_failure_cut = dataclasses.replace(cut, cut_id=f"{cut.cut_id}-build-failure")
    build_failure_store = CutStore()
    build_failure_store.add_cut(build_failure_cut)
    index = RejectionAuditIndexV1()

    def _raise_during_record_build(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("record build failed")

    monkeypatch.setattr(
        adapters_module,
        "_assumption_digest",
        _raise_during_record_build,
    )
    assert (
        observe_replay(
            build_failure_cut,
            build_failure_store,
            context,
            audit_sink=index,
        )
        == "QUARANTINE"
    )
    assert build_failure_cut.cut_id in build_failure_store.quarantined
    assert index.records == ()


def test_attach_legacy_ok_and_unknown_family_emit_no_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _f1_state()
    context = build_replay_context(state)
    attach_cut = _f1_cut(state)
    attach_store = CutStore()
    attach_store.add_cut(attach_cut)
    attach_index = RejectionAuditIndexV1()
    assert (
        observe_replay(
            attach_cut,
            attach_store,
            context,
            audit_sink=attach_index,
        )
        == "ATTACH"
    )
    assert attach_index.records == ()

    legacy_cut = _make_cutset_cut(
        {(0, 0)},
        {(4, 0)},
        cut_size=1,
        commodity_demand=2,
    )
    assert legacy_cut.cert is not None
    correct_hash = hashlib.sha256(legacy_cut.cert.cert_payload).hexdigest()
    legacy_cut = dataclasses.replace(
        legacy_cut,
        cert=dataclasses.replace(legacy_cut.cert, cert_hash=correct_hash),
        oracle_cert_hash=correct_hash,
    )
    legacy_store = CutStore()
    legacy_store.add_cut(legacy_cut)
    legacy_index = RejectionAuditIndexV1()
    monkeypatch.setattr(
        replay_module,
        "run_legacy_diagnostic",
        lambda cut, state: DiagnosticResult(
            family=cut.family,
            cut_id=cut.cut_id,
            outcome="ok",
        ),
    )
    assert (
        observe_replay(
            legacy_cut,
            legacy_store,
            context,
            audit_sink=legacy_index,
        )
        == "HOLD"
    )
    assert legacy_index.records == ()

    unknown_store = CutStore()
    unknown_store.add_cut(attach_cut)
    unknown_index = RejectionAuditIndexV1()
    monkeypatch.setattr(replay_module, "TYPED_REPLAY_FAMILIES", frozenset())
    monkeypatch.setattr(replay_module, "LEGACY_DIAGNOSTIC_VALIDATORS", {})
    with pytest.raises(
        NotImplementedError,
        match="is in neither the typed nor the legacy diagnostic replay table",
    ):
        observe_replay(
            attach_cut,
            unknown_store,
            context,
            audit_sink=unknown_index,
        )
    assert attach_cut.cut_id in unknown_store.held
    assert attach_cut.cut_id not in unknown_store.quarantined
    assert unknown_index.records == ()


def test_typed_tcb_fault_propagates_without_record_or_store_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.typed_platform as typed_platform

    state = _f1_state()
    cut = _f1_cut(state)
    store = CutStore()
    store.add_cut(cut)
    index = RejectionAuditIndexV1()
    fault = RuntimeError("injected replay TCB fault")

    def raise_tcb(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise fault

    monkeypatch.setattr(typed_platform, "validate_and_compile_cut", raise_tcb)
    with pytest.raises(RuntimeError, match="injected replay TCB fault") as caught:
        observe_replay(
            cut,
            store,
            build_replay_context(state),
            audit_sink=index,
        )

    assert caught.value is fault
    assert cut.cut_id in store.held
    assert cut.cut_id not in store.quarantined
    assert index.records == ()


def test_offline_regression_observer_uses_same_counts_and_records_rejections() -> None:
    state = _f1_state()
    context = build_replay_context(state)
    attached_cut = _f1_cut(state)
    rejected_cut = dataclasses.replace(
        attached_cut,
        cut_id=f"{attached_cut.cut_id}-rejected",
        oracle_cert_hash="0" * 64,
    )
    store = CutStore()
    store.add_cut(attached_cut)
    store.add_cut(rejected_cut)
    index = RejectionAuditIndexV1()

    counts = observe_regression_sweep(store, context, audit_sink=index)

    assert counts == {
        "ATTACH": 1,
        "HOLD": 0,
        "QUARANTINE": 1,
        "skipped_quarantined": 0,
    }
    assert tuple(record.subject.value for record in index.records) == (
        rejected_cut.cut_id,
    )


def test_default_regression_sweep_preserves_public_replay_cut_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _f1_state()
    context = build_replay_context(state)
    cut = _f1_cut(state)
    store = CutStore()
    store.add_cut(cut)
    calls: list[tuple[str, int]] = []
    original = replay_module.replay_cut

    def replay_spy(
        candidate: Cut,
        candidate_store: CutStore,
        candidate_context: ReplayContext,
        *,
        iter_index: int = -1,
    ) -> AttachDecision:
        calls.append((candidate.cut_id, iter_index))
        return original(
            candidate,
            candidate_store,
            candidate_context,
            iter_index=iter_index,
        )

    monkeypatch.setattr(replay_module, "replay_cut", replay_spy)

    assert regression_sweep(store, context, iter_index=19) == {
        "ATTACH": 1,
        "HOLD": 0,
        "QUARANTINE": 0,
        "skipped_quarantined": 0,
    }
    assert calls == [(cut.cut_id, 19)]


def test_cut_store_observer_emits_only_matching_prebuilt_subject() -> None:
    cut, context = _integrity_drift_cut()
    source_store = CutStore()
    source_store.add_cut(cut)
    source_index = RejectionAuditIndexV1()
    assert (
        observe_replay(
            cut,
            source_store,
            context,
            audit_sink=source_index,
        )
        == "QUARANTINE"
    )
    replay_record = source_index.records[0]
    reason = source_store.quarantined[cut.cut_id]
    record = dataclasses.replace(
        replay_record,
        adapter_id="cut_store.quarantine_transition.v1",
        premises=(
            RejectionPremiseV1(
                premise_id="cut_registered",
                expected="cut_id is registered in CutStore",
                verdict=PremiseVerdict.SATISFIED,
                observed="cut_id found before quarantine transition",
                unavailable_reason=None,
            ),
            RejectionPremiseV1(
                premise_id="terminal_reason_stable",
                expected="quarantine reason uses a registered stable code",
                verdict=PremiseVerdict.SATISFIED,
                observed=reason.reason_code,
                unavailable_reason=None,
            ),
            RejectionPremiseV1(
                premise_id="transition_authorized",
                expected="caller established the quarantine transition preconditions",
                verdict=PremiseVerdict.UNAVAILABLE,
                observed=None,
                unavailable_reason=(
                    "audit wrapper does not independently re-prove caller authorization"
                ),
            ),
        ),
    )

    matching_store = CutStore()
    matching_store.add_cut(cut, cell_keys=((0, 0),))
    matching_index = RejectionAuditIndexV1()
    observe_quarantine_transition(
        matching_store,
        cut.cut_id,
        reason,
        rejection_record=record,
        audit_sink=matching_index,
    )
    assert cut.cut_id in matching_store.quarantined
    assert not matching_store.cuts_affected_by_cell((0, 0))
    assert matching_index.records == (record,)

    adapter_mismatch_store = CutStore()
    adapter_mismatch_store.add_cut(cut)
    adapter_mismatch_index = RejectionAuditIndexV1()
    observe_quarantine_transition(
        adapter_mismatch_store,
        cut.cut_id,
        reason,
        rejection_record=replay_record,
        audit_sink=adapter_mismatch_index,
    )
    assert cut.cut_id in adapter_mismatch_store.quarantined
    assert adapter_mismatch_index.records == ()

    reason_mismatch_store = CutStore()
    reason_mismatch_store.add_cut(cut)
    reason_mismatch_index = RejectionAuditIndexV1()
    observe_quarantine_transition(
        reason_mismatch_store,
        cut.cut_id,
        QuarantineReason(reason_code="typed_adapter_rejected"),
        rejection_record=record,
        audit_sink=reason_mismatch_index,
    )
    assert cut.cut_id in reason_mismatch_store.quarantined
    assert reason_mismatch_index.records == ()

    family_mismatch_store = CutStore()
    family_mismatch_store.add_cut(cut)
    family_mismatch_index = RejectionAuditIndexV1()
    observe_quarantine_transition(
        family_mismatch_store,
        cut.cut_id,
        reason,
        rejection_record=dataclasses.replace(
            record,
            family="shape_packing_hall",
        ),
        audit_sink=family_mismatch_index,
    )
    assert family_mismatch_store.quarantined[cut.cut_id] == reason
    assert family_mismatch_index.records == ()

    detail_mismatch_store = CutStore()
    detail_mismatch_store.add_cut(cut)
    detail_mismatch_index = RejectionAuditIndexV1()
    observe_quarantine_transition(
        detail_mismatch_store,
        cut.cut_id,
        reason,
        rejection_record=dataclasses.replace(
            record,
            reason_detail="different terminal detail",
        ),
        audit_sink=detail_mismatch_index,
    )
    assert detail_mismatch_store.quarantined[cut.cut_id] == reason
    assert detail_mismatch_index.records == ()

    other_cut = dataclasses.replace(cut, cut_id=f"{cut.cut_id}-other")
    mismatch_store = CutStore()
    mismatch_store.add_cut(other_cut)
    mismatch_index = RejectionAuditIndexV1()
    observe_quarantine_transition(
        mismatch_store,
        other_cut.cut_id,
        reason,
        rejection_record=record,
        audit_sink=mismatch_index,
    )
    assert other_cut.cut_id in mismatch_store.quarantined
    assert mismatch_index.records == ()


def test_cut_store_observer_propagates_transition_fault_before_audit() -> None:
    store = CutStore()
    index = RejectionAuditIndexV1()

    with pytest.raises(KeyError, match="missing-cut"):
        observe_quarantine_transition(
            store,
            "missing-cut",
            QuarantineReason(reason_code="cut_integrity_failed"),
            rejection_record=cast(RejectionRecordV1, object()),
            audit_sink=index,
        )

    assert store.quarantined == {}
    assert index.records == ()
