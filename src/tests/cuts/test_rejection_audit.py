"""Contract tests for the versioned rejection audit sidecar."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pytest

from src.cuts.lifecycle import Cut
from src.cuts.state_snapshot import ValidatedStateSnapshot
from src.cuts.store import QuarantineReason
from src.cuts.typed_platform import ConstraintPlan, CutEnvelope
import src.tests.cuts.rule_cut_evolution.rejection_audit as rejection_audit_module
from src.tests.cuts.rule_cut_evolution.rejection_audit import (
    AuditDigestEvidenceV1,
    AuditEmitOutcomeV1,
    AuditEmitStatus,
    CostUnit,
    DEFERRED_REJECTION_MIGRATIONS_V1,
    DigestAvailability,
    EvidenceKind,
    EvidenceReferenceV1,
    PremiseVerdict,
    REJECTION_ADAPTER_SPECS_V1,
    RejectionAdapterStage,
    RejectionAdapterSpecV1,
    RejectionAuditIndexV1,
    RejectionCostMeasureV1,
    RejectionCostV1,
    RejectionDisposition,
    RejectionPremiseV1,
    RejectionRecordV1,
    RejectionSubjectKind,
    RejectionSubjectV1,
    ResponsibilityScope,
    STABLE_REJECTION_REASON_CODES_V1,
    StaticAuditSymbolV1,
    assumption_audit_digest_v1,
    emit_rejection_audit,
    rejection_record_ledger_projection_v1,
)


_INSTANCE_DIGEST = "1" * 64
_STATE_DIGEST = "2" * 64
_EVIDENCE_DIGEST = "3" * 64
_SEMANTIC_FINGERPRINT = "4" * 64
_TYPED_ADAPTER_ID = "typed_platform.cut_rejection.v1"


def _premises(
    adapter_id: str,
    *,
    reason_code: str,
) -> tuple[RejectionPremiseV1, ...]:
    adapter = REJECTION_ADAPTER_SPECS_V1[adapter_id]
    verdicts = adapter.reason_binding(reason_code).premise_verdicts
    return tuple(
        RejectionPremiseV1(
            premise_id=premise_id,
            expected=f"{premise_id} must hold",
            verdict=verdict,
            observed=(
                None
                if verdict is PremiseVerdict.UNAVAILABLE
                else (
                    f"{premise_id} failed"
                    if verdict is PremiseVerdict.VIOLATED
                    else f"{premise_id} held"
                )
            ),
            unavailable_reason=(
                f"{premise_id} is not exposed at the terminal seam"
                if verdict is PremiseVerdict.UNAVAILABLE
                else None
            ),
        )
        for premise_id, verdict in zip(
            adapter.required_premise_ids,
            verdicts,
            strict=True,
        )
    )


def _record(
    *,
    subject: RejectionSubjectV1 | None = None,
    adapter_id: str = _TYPED_ADAPTER_ID,
    reason_code: str = "proof",
    reason_detail: str = "independent proof verifier rejected the premise",
) -> RejectionRecordV1:
    binding = REJECTION_ADAPTER_SPECS_V1[adapter_id].reason_binding(reason_code)
    return RejectionRecordV1(
        subject=(
            RejectionSubjectV1(
                kind=RejectionSubjectKind.CUT_ID,
                value="existing-cut-1",
            )
            if subject is None
            else subject
        ),
        adapter_id=adapter_id,
        family="region_capacity",
        reason_code=reason_code,
        reason_detail=reason_detail,
        responsibility_scope=binding.responsibility_scope,
        disposition=binding.disposition,
        premises=_premises(
            adapter_id,
            reason_code=reason_code,
        ),
        instance_digest=AuditDigestEvidenceV1.available(_INSTANCE_DIGEST),
        state_digest=AuditDigestEvidenceV1.available(_STATE_DIGEST),
        assumption_digest=AuditDigestEvidenceV1.unavailable(
            "the stable seam did not expose an assumption digest"
        ),
        evidence_references=(
            EvidenceReferenceV1(
                kind=EvidenceKind.PROOF,
                reference="proof-ledger:existing-cut-1",
                content_digest=AuditDigestEvidenceV1.available(_EVIDENCE_DIGEST),
            ),
        ),
        cost=RejectionCostV1(
            measures=(
                RejectionCostMeasureV1(
                    unit=CostUnit.WALL_TIME_NS,
                    value=17,
                ),
                RejectionCostMeasureV1(
                    unit=CostUnit.SOLVER_CALLS,
                    value=0,
                ),
            ),
        ),
    )


def test_rejection_record_is_versioned_immutable_deterministic_and_has_no_record_id() -> None:
    record = _record()
    duplicate = _record()

    assert record.schema_version == 1
    assert record.audit_record_digest == duplicate.audit_record_digest
    assert len(record.audit_record_digest) == 64
    assert record.subject.kind is RejectionSubjectKind.CUT_ID
    assert "record_id" not in {item.name for item in fields(RejectionRecordV1)}
    assert "authority_digest" not in {item.name for item in fields(RejectionRecordV1)}
    with pytest.raises(FrozenInstanceError):
        record.reason_code = "typed_rejected_plan"  # type: ignore[misc]

    semantic_record = _record(
        subject=RejectionSubjectV1(
            kind=RejectionSubjectKind.SEMANTIC_FINGERPRINT,
            value=_SEMANTIC_FINGERPRINT,
        )
    )
    assert semantic_record.audit_record_digest != record.audit_record_digest


def test_common_assumption_digest_and_ledger_projection_are_audit_only() -> None:
    first = assumption_audit_digest_v1((("b", "2"), ("a", "1")))
    reordered = assumption_audit_digest_v1((("a", "1"), ("b", "2")))
    assert first == reordered
    assert len(first) == 64

    record = _record()
    projection = rejection_record_ledger_projection_v1(record)
    assert projection["audit_record_digest"] == record.audit_record_digest
    assert projection["subject"] == {
        "kind": "cut_id",
        "value": "existing-cut-1",
    }
    assert "authority_digest" not in projection

    with pytest.raises(TypeError, match="exact tuple"):
        assumption_audit_digest_v1([])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="exact RejectionRecordV1"):
        rejection_record_ledger_projection_v1(object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kind", "value", "error_type"),
    [
        (RejectionSubjectKind.CUT_ID, "", ValueError),
        (RejectionSubjectKind.CUT_ID, " cut-1", ValueError),
        (RejectionSubjectKind.SEMANTIC_FINGERPRINT, "4" * 63, ValueError),
        (RejectionSubjectKind.SEMANTIC_FINGERPRINT, "G" * 64, ValueError),
        ("cut_id", "cut-1", TypeError),
    ],
)
def test_subject_accepts_only_existing_cut_key_shapes(
    kind: object,
    value: str,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        RejectionSubjectV1(
            kind=kind,  # type: ignore[arg-type]
            value=value,
        )


def test_digest_evidence_requires_exact_digest_or_honest_unavailability() -> None:
    available = AuditDigestEvidenceV1.available(_STATE_DIGEST)
    unavailable = AuditDigestEvidenceV1.unavailable("not exposed by the seam")
    assert available.availability is DigestAvailability.AVAILABLE
    assert unavailable.availability is DigestAvailability.UNAVAILABLE

    with pytest.raises(ValueError, match="64-hex"):
        AuditDigestEvidenceV1.available("not-a-digest")
    with pytest.raises(ValueError, match="cannot carry unavailable_reason"):
        AuditDigestEvidenceV1(
            availability=DigestAvailability.AVAILABLE,
            digest=_STATE_DIGEST,
            unavailable_reason="contradiction",
        )
    with pytest.raises(ValueError, match="cannot carry a digest"):
        AuditDigestEvidenceV1(
            availability=DigestAvailability.UNAVAILABLE,
            digest=_STATE_DIGEST,
            unavailable_reason="contradiction",
        )
    with pytest.raises(ValueError, match="unavailable_reason"):
        AuditDigestEvidenceV1(
            availability=DigestAvailability.UNAVAILABLE,
            digest=None,
            unavailable_reason=None,
        )


def test_premise_evidence_and_cost_contradictions_fail_closed() -> None:
    with pytest.raises(ValueError, match="cannot carry an observed"):
        RejectionPremiseV1(
            premise_id="proof_sound",
            expected="proof must be sound",
            verdict=PremiseVerdict.UNAVAILABLE,
            observed="unknown",
            unavailable_reason="checker unavailable",
        )
    with pytest.raises(ValueError, match="observed"):
        RejectionPremiseV1(
            premise_id="proof_sound",
            expected="proof must be sound",
            verdict=PremiseVerdict.VIOLATED,
            observed=None,
            unavailable_reason=None,
        )
    with pytest.raises(ValueError, match="unavailable_reason"):
        RejectionCostV1(measures=())
    with pytest.raises(ValueError, match="duplicate units"):
        RejectionCostV1(
            measures=(
                RejectionCostMeasureV1(CostUnit.WORK_UNITS, 1),
                RejectionCostMeasureV1(CostUnit.WORK_UNITS, 2),
            )
        )
    with pytest.raises(ValueError, match="non-negative exact int"):
        RejectionCostMeasureV1(CostUnit.SOLVER_CALLS, True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="content_digest"):
        EvidenceReferenceV1(
            kind=EvidenceKind.LOG,
            reference="log:1",
            content_digest=object(),  # type: ignore[arg-type]
        )


def test_record_rejects_unknown_or_contradictory_adapter_registration() -> None:
    record = _record()

    with pytest.raises(ValueError, match="unknown rejection adapter"):
        replace(record, adapter_id="unknown.adapter.v1")
    with pytest.raises(ValueError, match="no stable reason code"):
        replace(record, reason_code="typed_rejected_unknown")
    with pytest.raises(ValueError, match="responsibility scope contradicts"):
        replace(record, responsibility_scope=ResponsibilityScope.LOWERING)
    with pytest.raises(ValueError, match="disposition contradicts"):
        replace(record, disposition=RejectionDisposition.QUARANTINE)
    with pytest.raises(ValueError, match="complete ordered premise vector"):
        replace(record, premises=record.premises[:-1])
    with pytest.raises(ValueError, match="complete ordered premise vector"):
        replace(record, premises=tuple(reversed(record.premises)))
    with pytest.raises(ValueError, match="verdicts contradict"):
        replace(
            record,
            premises=(
                replace(
                    record.premises[0],
                    verdict=PremiseVerdict.SATISFIED,
                    observed="invented linear trace",
                    unavailable_reason=None,
                ),
                *record.premises[1:],
            ),
        )
    with pytest.raises(ValueError, match="violated or unavailable"):
        replace(
            record,
            premises=tuple(
                replace(
                    premise,
                    verdict=PremiseVerdict.SATISFIED,
                    observed="held",
                    unavailable_reason=None,
                )
                for premise in record.premises
            ),
        )
    with pytest.raises(ValueError, match="contains duplicates"):
        replace(
            record,
            evidence_references=record.evidence_references * 2,
        )


def test_static_adapter_registry_and_deferred_migration_boundary_are_closed() -> None:
    assert tuple(REJECTION_ADAPTER_SPECS_V1) == (
        "typed_platform.cut_rejection.v1",
        "benders.framework_rejection_audit.v1",
        "replay.rejection_outcome.v1",
        "cut_store.quarantine_transition.v1",
    )
    assert type(REJECTION_ADAPTER_SPECS_V1) is MappingProxyType
    assert {
        adapter_id: (adapter.source.module, adapter.source.qualname)
        for adapter_id, adapter in REJECTION_ADAPTER_SPECS_V1.items()
    } == {
        "typed_platform.cut_rejection.v1": (
            "src.tests.cuts.rule_cut_evolution.rejection_adapters",
            "observe_typed_validation",
        ),
        "benders.framework_rejection_audit.v1": (
            "src.search.benders_loop",
            "LBBDController._maybe_attach_framework_cuts",
        ),
        "replay.rejection_outcome.v1": (
            "src.tests.cuts.rule_cut_evolution.rejection_adapters",
            "observe_replay",
        ),
        "cut_store.quarantine_transition.v1": (
            "src.tests.cuts.rule_cut_evolution.rejection_adapters",
            "observe_quarantine_transition",
        ),
    }
    with pytest.raises(TypeError):
        REJECTION_ADAPTER_SPECS_V1["dynamic"] = (  # type: ignore[index]
            cast(RejectionAdapterSpecV1, object())
        )
    for adapter_id, adapter in REJECTION_ADAPTER_SPECS_V1.items():
        assert adapter.adapter_id == adapter_id
        assert adapter.audit_only is True
        assert not hasattr(adapter.source, "resolve")
        assert not hasattr(adapter.source, "target")
        assert adapter.source.module.startswith("src.")
        assert all(
            binding.reason_code in STABLE_REJECTION_REASON_CODES_V1
            for binding in adapter.reason_bindings
        )
        assert all(
            len(binding.premise_verdicts)
            == len(adapter.required_premise_ids)
            for binding in adapter.reason_bindings
        )
    assert (
        REJECTION_ADAPTER_SPECS_V1["benders.framework_rejection_audit.v1"].integration_stage
        is RejectionAdapterStage.DECLARED_DEFERRED
    )
    assert all(
        adapter.integration_stage is RejectionAdapterStage.OFFLINE_OBSERVER
        for adapter_id, adapter in REJECTION_ADAPTER_SPECS_V1.items()
        if adapter_id != "benders.framework_rejection_audit.v1"
    )
    assert REJECTION_ADAPTER_SPECS_V1[
        "typed_platform.cut_rejection.v1"
    ].reason_binding("scope").premise_verdicts == (
        PremiseVerdict.UNAVAILABLE,
        PremiseVerdict.SATISFIED,
        PremiseVerdict.VIOLATED,
        PremiseVerdict.UNAVAILABLE,
        PremiseVerdict.UNAVAILABLE,
    )
    assert tuple(
        binding.reason_code
        for binding in REJECTION_ADAPTER_SPECS_V1[
            "benders.framework_rejection_audit.v1"
        ].reason_bindings
    ) == (
        "adapter",
        "registry",
        "envelope",
        "scope",
        "proof",
        "plan",
        "attach_timing",
        "semantic_duplicate",
    )
    assert REJECTION_ADAPTER_SPECS_V1[
        "benders.framework_rejection_audit.v1"
    ].required_premise_ids == (
        "cut_generated",
        "adapter_admitted",
        "family_registered",
        "schema_version_current",
        "scope_current",
        "proof_sound",
        "plan_sound",
        "semantic_unique",
        "attach_timing_current",
    )
    assert REJECTION_ADAPTER_SPECS_V1[
        "benders.framework_rejection_audit.v1"
    ].reason_binding("scope").premise_verdicts == (
        PremiseVerdict.SATISFIED,
        PremiseVerdict.SATISFIED,
        PremiseVerdict.UNAVAILABLE,
        PremiseVerdict.SATISFIED,
        PremiseVerdict.VIOLATED,
        PremiseVerdict.UNAVAILABLE,
        PremiseVerdict.UNAVAILABLE,
        PremiseVerdict.UNAVAILABLE,
        PremiseVerdict.UNAVAILABLE,
    )
    replay_scope = REJECTION_ADAPTER_SPECS_V1[
        "replay.rejection_outcome.v1"
    ].reason_binding("typed_rejected_scope")
    assert replay_scope.disposition is RejectionDisposition.HOLD
    assert all(
        binding.disposition is RejectionDisposition.QUARANTINE
        for binding in REJECTION_ADAPTER_SPECS_V1[
            "cut_store.quarantine_transition.v1"
        ].reason_bindings
    )

    assert tuple(item.subsystem for item in DEFERRED_REJECTION_MIGRATIONS_V1) == (
        "binding",
        "routing",
        "power",
    )
    for migration in DEFERRED_REJECTION_MIGRATIONS_V1:
        assert migration.parity_vector_required is True
        assert migration.audit_only_required is True
        assert migration.authority_change_forbidden is True
        assert all(module.startswith("src.") for module in migration.source_modules)
        assert migration.migration_id not in REJECTION_ADAPTER_SPECS_V1


def test_append_only_index_supports_multiple_facts_without_overwrite() -> None:
    index = RejectionAuditIndexV1()
    first = _record()
    initial_digest = index.index_audit_digest

    appended = index.emit(first)
    assert appended.status is AuditEmitStatus.APPENDED
    assert index.records == (first,)
    assert index.records_for(first.subject) == (first,)
    assert index.index_audit_digest != initial_digest

    duplicate = index.emit(_record())
    assert duplicate.status is AuditEmitStatus.DUPLICATE
    assert index.records == (first,)
    assert duplicate.index_audit_digest == appended.index_audit_digest

    second = _record(reason_detail="a second observation of the same rejection")
    second_outcome = index.emit(second)
    assert second_outcome.status is AuditEmitStatus.APPENDED
    assert index.records == (first, second)
    assert index.records_for(first.subject) == (first, second)
    assert second_outcome.index_audit_digest != appended.index_audit_digest
    assert not hasattr(index, "delete")
    assert not hasattr(index, "replace")
    assert not hasattr(index, "promote")

    with pytest.raises(TypeError, match="exact RejectionRecordV1"):
        index.emit(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="exact RejectionSubjectV1"):
        index.records_for(object())  # type: ignore[arg-type]


def test_audit_sink_failure_is_explicit_and_does_not_change_caller_decision() -> None:
    record = _record()
    caller_decision = "QUARANTINE"

    class RaisingSink:
        def emit(self, emitted: RejectionRecordV1) -> AuditEmitOutcomeV1:
            assert emitted is record
            raise RuntimeError("audit transport unavailable")

    failed = emit_rejection_audit(record, RaisingSink())
    assert failed.status is AuditEmitStatus.FAILED
    assert failed.index_audit_digest is None
    assert failed.audit_record_digest == record.audit_record_digest
    assert failed.detail == "audit transport unavailable"
    assert caller_decision == "QUARANTINE"

    class WrongOutcomeSink:
        def emit(self, emitted: RejectionRecordV1) -> object:
            del emitted
            return object()

    wrong = emit_rejection_audit(
        record,
        WrongOutcomeSink(),  # type: ignore[arg-type]
    )
    assert wrong.status is AuditEmitStatus.FAILED
    assert "non-AuditEmitOutcomeV1" in wrong.detail
    assert caller_decision == "QUARANTINE"

    class UnprintableFailure(RuntimeError):
        def __str__(self) -> str:
            raise AssertionError("audit exception text unavailable")

    class UnprintableSink:
        def emit(self, emitted: RejectionRecordV1) -> AuditEmitOutcomeV1:
            del emitted
            raise UnprintableFailure()

    unprintable = emit_rejection_audit(record, UnprintableSink())
    assert unprintable.status is AuditEmitStatus.FAILED
    assert unprintable.detail == "UnprintableFailure"
    assert caller_decision == "QUARANTINE"

    index = RejectionAuditIndexV1()
    successful = emit_rejection_audit(record, index)
    assert successful.status is AuditEmitStatus.APPENDED
    assert caller_decision == "QUARANTINE"


def test_audit_types_are_not_added_to_any_existing_authority_wire() -> None:
    forbidden_fields = {"audit_record_digest", "rejection_record", "rejection_record_id"}
    for authority_type in (
        Cut,
        CutEnvelope,
        ConstraintPlan,
        ValidatedStateSnapshot,
        QuarantineReason,
    ):
        assert forbidden_fields.isdisjoint(item.name for item in fields(authority_type))

    source = Path(rejection_audit_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        module.startswith(
            (
                "src.cuts.lifecycle",
                "src.cuts.replay",
                "src.cuts.state_snapshot",
                "src.cuts.store",
                "src.cuts.typed_platform",
            )
        )
        for module in imported_modules
    )
    assert not any(
        token in exported_name
        for exported_name in rejection_audit_module.__all__
        for token in ("activate", "apply", "compile", "promote", "resolve")
    )


def test_static_audit_symbol_and_outcome_reject_malformed_claims() -> None:
    with pytest.raises(ValueError, match="below src"):
        StaticAuditSymbolV1(module="third_party.plugin", qualname="emit")
    with pytest.raises(ValueError, match="local or lambda"):
        StaticAuditSymbolV1(module="src.audit", qualname="<lambda>")
    with pytest.raises(ValueError, match="cannot claim an index audit digest"):
        AuditEmitOutcomeV1(
            status=AuditEmitStatus.FAILED,
            audit_record_digest=_EVIDENCE_DIGEST,
            index_audit_digest=_STATE_DIGEST,
            detail="failed",
        )
    with pytest.raises(ValueError, match="cannot carry failure detail"):
        AuditEmitOutcomeV1(
            status=AuditEmitStatus.APPENDED,
            audit_record_digest=_EVIDENCE_DIGEST,
            index_audit_digest=_STATE_DIGEST,
            detail="contradiction",
        )
