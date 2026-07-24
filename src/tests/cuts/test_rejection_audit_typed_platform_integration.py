"""Opt-in rejection-audit contracts for the unchanged typed cut entry."""

from __future__ import annotations

import inspect

import pytest

from src.cuts import rejection_audit as rejection_audit_module
from src.cuts import typed_platform
from src.cuts.rejection_audit import (
    AuditEmitOutcomeV1,
    CostUnit,
    DigestAvailability,
    EvidenceKind,
    PremiseVerdict,
    RejectionAuditIndexV1,
    RejectionRecordV1,
    RejectionSubjectKind,
    assumption_audit_digest_v1,
)
from src.cuts.state_snapshot import ValidatedStateSnapshot
from src.cuts.typed_platform import (
    CapabilityStage,
    CompiledCut,
    CutEnvelope,
    CutRejection,
    ExecutionPath,
    FamilyCapabilityRegistry,
    ShadowValidated,
    ValidateAndCompileResult,
    build_production_registry,
    cut_to_envelope_v1,
    validate_and_compile_cut,
    validate_and_compile_cut_audited,
)
from src.tests.cuts import test_stage_b_region_capacity as region_cases
from src.tests.cuts import test_stage_b_typed_platform as platform_cases


def _typed_fixture() -> tuple[
    CutEnvelope,
    ValidatedStateSnapshot,
    FamilyCapabilityRegistry,
]:
    state, snapshot = platform_cases._build_world()
    envelope = platform_cases._trusted_test_envelope(
        platform_cases._typed_probe_cut(state),
        snapshot,
    )
    plugin = platform_cases._OrderedPlugin(platform_cases._typed_probe_plan())
    return envelope, snapshot, platform_cases._typed_probe_registry(plugin)


def _registry_rejection_fixture() -> tuple[
    CutEnvelope,
    ValidatedStateSnapshot,
    FamilyCapabilityRegistry,
]:
    envelope, snapshot, _ = _typed_fixture()
    return (
        envelope,
        snapshot,
        FamilyCapabilityRegistry(capabilities={}, plugins={}),
    )


class _ExplodingSink:
    def emit(self, record: RejectionRecordV1) -> AuditEmitOutcomeV1:
        del record
        raise RuntimeError("audit transport unavailable")


def test_original_entry_signature_is_unchanged_and_audited_seam_is_opt_in() -> None:
    original = inspect.signature(validate_and_compile_cut)
    assert str(original) == (
        "(envelope: 'CutEnvelope', snapshot: 'ValidatedStateSnapshot', "
        "registry: 'FamilyCapabilityRegistry') -> 'ValidateAndCompileResult'"
    )
    assert tuple(original.parameters) == ("envelope", "snapshot", "registry")
    assert all(
        parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        and parameter.default is inspect.Parameter.empty
        for parameter in original.parameters.values()
    )

    audited = inspect.signature(validate_and_compile_cut_audited)
    assert tuple(audited.parameters) == (
        "envelope",
        "snapshot",
        "registry",
        "audit_sink",
    )
    assert audited.parameters["audit_sink"].kind is inspect.Parameter.KEYWORD_ONLY
    assert audited.parameters["audit_sink"].default is inspect.Parameter.empty


def test_compiled_and_shadow_results_emit_no_rejection_record() -> None:
    envelope, snapshot, registry = _typed_fixture()
    index = RejectionAuditIndexV1()

    compiled = validate_and_compile_cut_audited(
        envelope,
        snapshot,
        registry,
        audit_sink=index,
    )

    state, shadow_snapshot = platform_cases._build_world()
    shadow_envelope = platform_cases._trusted_test_envelope(
        platform_cases._make_pattern_cut(state),
        shadow_snapshot,
    )
    shadow_plugin = platform_cases._OrderedPlugin(
        platform_cases._plan(family="pattern_nogood")
    )
    shadow_capability = platform_cases._capability(
        family="pattern_nogood",
        mode="literal",
        stage=CapabilityStage.VALIDATED,
        execution_path=ExecutionPath.TYPED,
        compiler_version=None,
    )
    shadow_registry = platform_cases._registry(
        shadow_plugin,
        capability=shadow_capability,
    )
    shadow = validate_and_compile_cut_audited(
        shadow_envelope,
        shadow_snapshot,
        shadow_registry,
        audit_sink=index,
    )

    assert type(compiled) is CompiledCut
    assert type(shadow) is ShadowValidated
    assert index.records == ()


def test_real_rejection_emits_complete_evidence_bound_record() -> None:
    envelope, snapshot, registry = _registry_rejection_fixture()
    index = RejectionAuditIndexV1()

    result = validate_and_compile_cut_audited(
        envelope,
        snapshot,
        registry,
        audit_sink=index,
    )

    assert result == CutRejection(
        stage="registry",
        reason="family is absent from registry",
        cut_id=envelope.cut_id,
    )
    record, = index.records
    assert record.adapter_id == "typed_platform.cut_rejection.v1"
    assert record.subject.kind is RejectionSubjectKind.CUT_ID
    assert record.subject.value == envelope.cut_id
    assert record.family == envelope.family
    assert record.reason_code == "registry"
    assert tuple(premise.premise_id for premise in record.premises) == (
        "family_registered",
        "schema_version_current",
        "scope_current",
        "proof_sound",
        "plan_sound",
    )
    assert tuple(premise.verdict for premise in record.premises) == (
        PremiseVerdict.VIOLATED,
        PremiseVerdict.UNAVAILABLE,
        PremiseVerdict.UNAVAILABLE,
        PremiseVerdict.UNAVAILABLE,
        PremiseVerdict.UNAVAILABLE,
    )
    assert record.instance_digest.availability is DigestAvailability.AVAILABLE
    assert record.instance_digest.digest == snapshot.source_digest
    assert record.state_digest.availability is DigestAvailability.AVAILABLE
    assert record.state_digest.digest == snapshot.digest
    assumption_pairs = tuple(
        (assumption.key, assumption.value)
        for assumption in envelope.scope.assumptions
    )
    assert record.assumption_digest.availability is DigestAvailability.AVAILABLE
    assert record.assumption_digest.digest == assumption_audit_digest_v1(
        assumption_pairs
    )
    assert tuple(reference.kind for reference in record.evidence_references) == (
        EvidenceKind.PROOF,
        EvidenceKind.SNAPSHOT,
    )
    assert record.evidence_references[0].content_digest.digest == envelope.proof_hash
    assert record.evidence_references[1].content_digest.digest == snapshot.digest
    assert len(record.cost.measures) == 1
    assert record.cost.measures[0].unit is CostUnit.WALL_TIME_NS
    assert record.cost.measures[0].value >= 0


@pytest.mark.parametrize(
    ("stage", "expected_verdicts"),
    (
        (
            "registry",
            (
                PremiseVerdict.VIOLATED,
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.UNAVAILABLE,
            ),
        ),
        (
            "envelope",
            (
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.VIOLATED,
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.UNAVAILABLE,
            ),
        ),
        (
            "scope",
            (
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.SATISFIED,
                PremiseVerdict.VIOLATED,
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.UNAVAILABLE,
            ),
        ),
        (
            "proof",
            (
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.SATISFIED,
                PremiseVerdict.SATISFIED,
                PremiseVerdict.VIOLATED,
                PremiseVerdict.UNAVAILABLE,
            ),
        ),
        (
            "plan",
            (
                PremiseVerdict.SATISFIED,
                PremiseVerdict.SATISFIED,
                PremiseVerdict.SATISFIED,
                PremiseVerdict.UNAVAILABLE,
                PremiseVerdict.VIOLATED,
            ),
        ),
    ),
)
def test_every_typed_rejection_stage_maps_to_one_complete_ordered_premise_vector(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected_verdicts: tuple[PremiseVerdict, ...],
) -> None:
    envelope, snapshot, registry = _typed_fixture()
    expected = CutRejection(
        stage=stage,
        reason=f"{stage} rejected",
        cut_id=envelope.cut_id,
    )

    def _reject(
        candidate_envelope: CutEnvelope,
        candidate_snapshot: ValidatedStateSnapshot,
        candidate_registry: FamilyCapabilityRegistry,
    ) -> ValidateAndCompileResult:
        del candidate_envelope, candidate_snapshot, candidate_registry
        return expected

    monkeypatch.setattr(typed_platform, "validate_and_compile_cut", _reject)
    index = RejectionAuditIndexV1()

    result = validate_and_compile_cut_audited(
        envelope,
        snapshot,
        registry,
        audit_sink=index,
    )

    assert result is expected
    record, = index.records
    assert len(record.premises) == 5
    assert tuple(premise.verdict for premise in record.premises) == (
        expected_verdicts
    )
    assert all(
        "not evaluated" not in (premise.unavailable_reason or "")
        for premise in record.premises
    )


def test_real_late_registry_rejection_does_not_invent_linear_trace() -> None:
    envelope, snapshot, _registry = _typed_fixture()
    capability = platform_cases._typed_probe_capability(
        stage=CapabilityStage.EXPERIMENTAL,
        compiler_version=None,
    )
    late_registry = FamilyCapabilityRegistry(
        capabilities={capability.name: capability},
        plugins={},
    )
    index = RejectionAuditIndexV1()

    result = validate_and_compile_cut_audited(
        envelope,
        snapshot,
        late_registry,
        audit_sink=index,
    )

    assert result == CutRejection(
        stage="registry",
        reason="experimental family has no complete typed chain",
        cut_id=envelope.cut_id,
    )
    record, = index.records
    assert record.premises[0].verdict is PremiseVerdict.VIOLATED
    assert all(
        premise.verdict is PremiseVerdict.UNAVAILABLE
        for premise in record.premises[1:]
    )
    assert all(
        "exact verdict" in (premise.unavailable_reason or "")
        for premise in record.premises[1:]
    )


def test_real_late_scope_rejection_marks_unexposed_proof_trace_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.cuts.families.region_capacity_typed as region_capacity_typed

    _state, raw_cut, snapshot, _compiled = region_cases._compile_production_cut()
    envelope = cut_to_envelope_v1(raw_cut)
    calls = 0

    def reject_late_scope(
        proof: object,
        assumptions: object,
    ) -> str:
        nonlocal calls
        del proof, assumptions
        calls += 1
        return "injected late assumption-completeness rejection"

    monkeypatch.setattr(
        region_capacity_typed,
        "validate_region_capacity_assumption_completeness",
        reject_late_scope,
    )
    index = RejectionAuditIndexV1()

    result = validate_and_compile_cut_audited(
        envelope,
        snapshot,
        build_production_registry(),
        audit_sink=index,
    )

    assert calls == 1
    assert result == CutRejection(
        stage="scope",
        reason="injected late assumption-completeness rejection",
        cut_id=envelope.cut_id,
    )
    record, = index.records
    premise_by_id = {
        premise.premise_id: premise for premise in record.premises
    }
    assert premise_by_id["scope_current"].verdict is PremiseVerdict.VIOLATED
    assert premise_by_id["proof_sound"].verdict is PremiseVerdict.UNAVAILABLE
    assert "exact verdict" in (
        premise_by_id["proof_sound"].unavailable_reason or ""
    )


def test_sink_failure_cannot_change_the_original_rejection() -> None:
    envelope, snapshot, registry = _registry_rejection_fixture()
    baseline = validate_and_compile_cut(envelope, snapshot, registry)

    result = validate_and_compile_cut_audited(
        envelope,
        snapshot,
        registry,
        audit_sink=_ExplodingSink(),
    )

    assert result == baseline


def test_audit_construction_failure_cannot_change_the_original_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope, snapshot, registry = _registry_rejection_fixture()
    baseline = validate_and_compile_cut(envelope, snapshot, registry)
    index = RejectionAuditIndexV1()

    def _explode_record(**values: object) -> RejectionRecordV1:
        del values
        raise RuntimeError("audit record construction unavailable")

    monkeypatch.setattr(
        rejection_audit_module,
        "RejectionRecordV1",
        _explode_record,
    )

    result = validate_and_compile_cut_audited(
        envelope,
        snapshot,
        registry,
        audit_sink=index,
    )

    assert result == baseline
    assert index.records == ()


def test_unavailable_clock_is_explicit_and_cannot_suppress_the_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope, snapshot, registry = _registry_rejection_fixture()
    index = RejectionAuditIndexV1()
    monkeypatch.setattr(typed_platform, "_typed_audit_monotonic_ns", lambda: None)

    result = validate_and_compile_cut_audited(
        envelope,
        snapshot,
        registry,
        audit_sink=index,
    )

    assert type(result) is CutRejection
    record, = index.records
    assert record.cost.measures == ()
    assert record.cost.unavailable_reason == (
        "monotonic audited-path timing is unavailable"
    )


def test_broken_audit_timer_cannot_preempt_the_original_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope, snapshot, registry = _registry_rejection_fixture()
    index = RejectionAuditIndexV1()

    def _broken_clock() -> int:
        raise RuntimeError("audit clock unavailable")

    monkeypatch.setattr(
        typed_platform,
        "_typed_audit_monotonic_ns",
        _broken_clock,
    )

    result = validate_and_compile_cut_audited(
        envelope,
        snapshot,
        registry,
        audit_sink=index,
    )

    assert result == validate_and_compile_cut(envelope, snapshot, registry)
    record, = index.records
    assert record.cost.measures == ()
    assert record.cost.unavailable_reason == (
        "monotonic audited-path timing is unavailable"
    )


def test_tcb_exception_propagates_by_identity_without_audit_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope, snapshot, registry = _typed_fixture()
    fault = RuntimeError("typed TCB fault")
    index = RejectionAuditIndexV1()

    def _raise_fault(
        candidate_envelope: CutEnvelope,
        candidate_snapshot: ValidatedStateSnapshot,
        candidate_registry: FamilyCapabilityRegistry,
    ) -> ValidateAndCompileResult:
        del candidate_envelope, candidate_snapshot, candidate_registry
        raise fault

    monkeypatch.setattr(
        typed_platform,
        "validate_and_compile_cut",
        _raise_fault,
    )

    with pytest.raises(RuntimeError) as raised:
        validate_and_compile_cut_audited(
            envelope,
            snapshot,
            registry,
            audit_sink=index,
        )

    assert raised.value is fault
    assert index.records == ()
