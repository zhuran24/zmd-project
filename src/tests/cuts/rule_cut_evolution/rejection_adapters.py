"""Test/offline rejection observers over unchanged production APIs.

The observers in this module call the established typed, replay, and CutStore
entry points without adding parameters or branches to production code.  They
construct and emit audit records only after the production call returns or its
state transition completes.  TCB exceptions therefore propagate unchanged,
while record construction and sink failures cannot alter the returned result or
store state.

Benders is intentionally absent.  Its adapter row is declared/deferred in
``rejection_audit`` and this batch adds no production sink or emission path.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping
from typing import Any, cast

import src.cuts.replay as replay_module
import src.cuts.typed_platform as typed_platform
from src.cuts.lifecycle import AttachDecision, Cut
from src.cuts.replay import ReplayContext, TYPED_REPLAY_FAMILIES
from src.cuts.state_snapshot import ValidatedStateSnapshot
from src.cuts.store import CutStore, QuarantineReason
from src.cuts.typed_platform import (
    CutEnvelope,
    CutRejection,
    FamilyCapabilityRegistry,
    ValidateAndCompileResult,
)
from src.tests.cuts.rule_cut_evolution import rejection_audit as audit


def _safe_monotonic_ns() -> int | None:
    try:
        value = time.monotonic_ns()
    except Exception:
        return None
    return value if type(value) is int and value >= 0 else None


def _read_monotonic_ns() -> int | None:
    """Contain even a replaced/broken audit clock implementation."""

    try:
        return _safe_monotonic_ns()
    except Exception:
        return None


def _safe_text(value: object, *, fallback: str) -> str:
    try:
        text = str(value).replace("\x00", "\\x00").strip()
    except Exception:
        return fallback
    return text or fallback


def _digest_evidence(
    value: object,
    *,
    unavailable_reason: str,
) -> audit.AuditDigestEvidenceV1:
    try:
        return audit.AuditDigestEvidenceV1.available(cast(str, value))
    except Exception:
        return audit.AuditDigestEvidenceV1.unavailable(unavailable_reason)


def _assumption_digest(
    assumptions: object,
    *,
    unavailable_reason: str,
) -> audit.AuditDigestEvidenceV1:
    try:
        if type(assumptions) is not tuple:
            raise TypeError("assumptions are not an exact tuple")
        pairs = tuple(
            (
                cast(str, getattr(assumption, "key")),
                cast(str, getattr(assumption, "value")),
            )
            for assumption in assumptions
        )
        return audit.AuditDigestEvidenceV1.available(
            audit.assumption_audit_digest_v1(pairs)
        )
    except Exception:
        return audit.AuditDigestEvidenceV1.unavailable(unavailable_reason)


def _rejection_cost(started_ns: int | None) -> audit.RejectionCostV1:
    finished_ns = _read_monotonic_ns()
    if (
        started_ns is not None
        and finished_ns is not None
        and finished_ns >= started_ns
    ):
        return audit.RejectionCostV1(
            measures=(
                audit.RejectionCostMeasureV1(
                    unit=audit.CostUnit.WALL_TIME_NS,
                    value=finished_ns - started_ns,
                ),
            ),
        )
    return audit.RejectionCostV1(
        measures=(),
        unavailable_reason="monotonic audited-path timing is unavailable",
    )


def _premises(
    *,
    adapter_id: str,
    reason_code: str,
    reason_detail: str,
    expectations: Mapping[str, str],
) -> tuple[audit.RejectionPremiseV1, ...]:
    adapter = audit.REJECTION_ADAPTER_SPECS_V1[adapter_id]
    binding = adapter.reason_binding(reason_code)
    records: list[audit.RejectionPremiseV1] = []
    for premise_id, verdict in zip(
        adapter.required_premise_ids,
        binding.premise_verdicts,
        strict=True,
    ):
        expected = expectations[premise_id]
        if verdict is audit.PremiseVerdict.SATISFIED:
            records.append(
                audit.RejectionPremiseV1(
                    premise_id=premise_id,
                    expected=expected,
                    verdict=verdict,
                    observed="the terminal seam necessarily established this premise",
                    unavailable_reason=None,
                )
            )
        elif verdict is audit.PremiseVerdict.VIOLATED:
            records.append(
                audit.RejectionPremiseV1(
                    premise_id=premise_id,
                    expected=expected,
                    verdict=verdict,
                    observed=reason_detail,
                    unavailable_reason=None,
                )
            )
        else:
            records.append(
                audit.RejectionPremiseV1(
                    premise_id=premise_id,
                    expected=expected,
                    verdict=verdict,
                    observed=None,
                    unavailable_reason=(
                        "the unchanged terminal seam does not expose an exact "
                        f"verdict for {premise_id}"
                    ),
                )
            )
    return tuple(records)


_TYPED_EXPECTATIONS = {
    "family_registered": "the family is registered and eligible for typed dispatch",
    "schema_version_current": "the proof schema version matches the family capability",
    "scope_current": "the complete scope manifest matches the validated snapshot",
    "proof_sound": "the independent family verifier accepts the proof",
    "plan_sound": "the compiler and plan verifier accept the strengthening",
}


def _typed_record(
    *,
    envelope: CutEnvelope,
    snapshot: ValidatedStateSnapshot,
    rejection: CutRejection,
    started_ns: int | None,
) -> audit.RejectionRecordV1:
    adapter_id = "typed_platform.cut_rejection.v1"
    reason_detail = _safe_text(
        rejection.reason,
        fallback=f"{rejection.stage} rejection",
    )
    binding = audit.REJECTION_ADAPTER_SPECS_V1[adapter_id].reason_binding(
        rejection.stage
    )
    return audit.RejectionRecordV1(
        subject=audit.RejectionSubjectV1(
            kind=audit.RejectionSubjectKind.CUT_ID,
            value=rejection.cut_id,
        ),
        adapter_id=adapter_id,
        family=envelope.family,
        reason_code=rejection.stage,
        reason_detail=reason_detail,
        responsibility_scope=binding.responsibility_scope,
        disposition=binding.disposition,
        premises=_premises(
            adapter_id=adapter_id,
            reason_code=rejection.stage,
            reason_detail=reason_detail,
            expectations=_TYPED_EXPECTATIONS,
        ),
        instance_digest=_digest_evidence(
            snapshot.source_digest,
            unavailable_reason="validated snapshot source digest is unavailable",
        ),
        state_digest=_digest_evidence(
            snapshot.digest,
            unavailable_reason="validated snapshot state digest is unavailable",
        ),
        assumption_digest=_assumption_digest(
            envelope.scope.assumptions,
            unavailable_reason="complete scope assumption vector is unavailable",
        ),
        evidence_references=(
            audit.EvidenceReferenceV1(
                kind=audit.EvidenceKind.PROOF,
                reference=f"cut-proof:{rejection.cut_id}",
                content_digest=_digest_evidence(
                    envelope.proof_hash,
                    unavailable_reason="envelope proof digest is unavailable",
                ),
            ),
            audit.EvidenceReferenceV1(
                kind=audit.EvidenceKind.SNAPSHOT,
                reference=f"validated-state-snapshot:{rejection.cut_id}",
                content_digest=_digest_evidence(
                    snapshot.digest,
                    unavailable_reason="validated snapshot digest is unavailable",
                ),
            ),
        ),
        cost=_rejection_cost(started_ns),
    )


def observe_typed_validation(
    envelope: CutEnvelope,
    snapshot: ValidatedStateSnapshot,
    registry: FamilyCapabilityRegistry,
    *,
    audit_sink: audit.RejectionAuditSinkV1,
) -> ValidateAndCompileResult:
    """Observe the unchanged typed entry; emit only an established rejection."""

    started_ns = _read_monotonic_ns()
    result = typed_platform.validate_and_compile_cut(envelope, snapshot, registry)
    if type(result) is not CutRejection:
        return result
    try:
        record = _typed_record(
            envelope=envelope,
            snapshot=snapshot,
            rejection=result,
            started_ns=started_ns,
        )
        audit.emit_rejection_audit(record, audit_sink)
    except Exception:
        pass
    return result


_REPLAY_EXPECTATIONS = {
    "cut_registered": "cut_id is registered in CutStore",
    "cut_integrity": "validate_cut_integrity returns None",
    "adapter_representation_valid": (
        "the typed adapter returns a valid CutEnvelope when used"
    ),
    "replay_validation": "replay validation permits attachment",
}


def _cut_assumptions(cut: Cut) -> object:
    scope = cut.scope
    return None if scope is None else scope.active_assumptions


def _cut_evidence_digest(cut: Cut) -> audit.AuditDigestEvidenceV1:
    cert = cut.cert
    payload = None if cert is None else cert.cert_payload
    if type(payload) is bytes:
        return audit.AuditDigestEvidenceV1.available(
            hashlib.sha256(payload).hexdigest()
        )
    return audit.AuditDigestEvidenceV1.unavailable(
        "cut certificate payload is unavailable at the replay seam"
    )


def _replay_record(
    *,
    cut: Cut,
    context: ReplayContext,
    reason_code: str,
    reason_detail: str,
    started_ns: int | None,
) -> audit.RejectionRecordV1:
    adapter_id = "replay.rejection_outcome.v1"
    detail = _safe_text(reason_detail, fallback=reason_code)
    binding = audit.REJECTION_ADAPTER_SPECS_V1[adapter_id].reason_binding(
        reason_code
    )
    return audit.RejectionRecordV1(
        subject=audit.RejectionSubjectV1(
            kind=audit.RejectionSubjectKind.CUT_ID,
            value=cut.cut_id,
        ),
        adapter_id=adapter_id,
        family=cut.family,
        reason_code=reason_code,
        reason_detail=detail,
        responsibility_scope=binding.responsibility_scope,
        disposition=binding.disposition,
        premises=_premises(
            adapter_id=adapter_id,
            reason_code=reason_code,
            reason_detail=detail,
            expectations=_REPLAY_EXPECTATIONS,
        ),
        instance_digest=_digest_evidence(
            context.snapshot.source_digest,
            unavailable_reason="current replay instance digest is unavailable",
        ),
        state_digest=_digest_evidence(
            context.snapshot.digest,
            unavailable_reason="current replay state digest is unavailable",
        ),
        assumption_digest=_assumption_digest(
            _cut_assumptions(cut),
            unavailable_reason="cut scope assumptions are unavailable at the replay seam",
        ),
        evidence_references=(
            audit.EvidenceReferenceV1(
                kind=audit.EvidenceKind.CUT_STORE,
                reference=f"cut_store:{cut.cut_id}",
                content_digest=_cut_evidence_digest(cut),
            ),
        ),
        cost=_rejection_cost(started_ns),
    )


def _replay_rejection(
    *,
    cut: Cut,
    store: CutStore,
    decision: AttachDecision,
) -> tuple[str, str] | None:
    if decision == "ATTACH":
        return None
    if decision == "HOLD":
        if cut.family not in TYPED_REPLAY_FAMILIES:
            return None
        if cut.cut_id not in store.held or cut.cut_id in store.quarantined:
            return None
        return (
            "typed_rejected_scope",
            "typed replay rejected the current snapshot at scope stage",
        )
    reason = store.quarantined.get(cut.cut_id)
    if reason is None:
        return None
    adapter = audit.REJECTION_ADAPTER_SPECS_V1["replay.rejection_outcome.v1"]
    try:
        adapter.reason_binding(reason.reason_code)
    except KeyError:
        return None
    return reason.reason_code, reason.detail


def observe_replay(
    cut: Cut,
    store: CutStore,
    context: ReplayContext,
    *,
    iter_index: int = -1,
    audit_sink: audit.RejectionAuditSinkV1,
) -> AttachDecision:
    """Observe unchanged replay; emit only after its terminal state transition."""

    started_ns = _read_monotonic_ns()
    decision = replay_module.replay_cut(
        cut,
        store,
        context,
        iter_index=iter_index,
    )
    rejected = _replay_rejection(cut=cut, store=store, decision=decision)
    if rejected is None:
        return decision
    reason_code, reason_detail = rejected
    try:
        record = _replay_record(
            cut=cut,
            context=context,
            reason_code=reason_code,
            reason_detail=reason_detail,
            started_ns=started_ns,
        )
        audit.emit_rejection_audit(record, audit_sink)
    except Exception:
        pass
    return decision


def observe_regression_sweep(
    store: CutStore,
    context: ReplayContext,
    *,
    iter_index: int = -1,
    audit_sink: audit.RejectionAuditSinkV1,
) -> dict[str, int]:
    """Offline equivalent of ``regression_sweep`` using ``observe_replay``."""

    counts = {
        "ATTACH": 0,
        "HOLD": 0,
        "QUARANTINE": 0,
        "skipped_quarantined": 0,
    }
    for cut_id in list(store.cuts):
        if cut_id in store.quarantined:
            counts["skipped_quarantined"] += 1
            continue
        decision = observe_replay(
            store.cuts[cut_id],
            store,
            context,
            iter_index=iter_index,
            audit_sink=audit_sink,
        )
        counts[decision] += 1
    return counts


def observe_quarantine_transition(
    store: CutStore,
    cut_id: str,
    reason: QuarantineReason,
    *,
    rejection_record: audit.RejectionRecordV1,
    audit_sink: audit.RejectionAuditSinkV1,
) -> None:
    """Observe unchanged CutStore quarantine after its complete transition."""

    store.quarantine_cut(cut_id, reason)
    try:
        if type(rejection_record) is not audit.RejectionRecordV1:
            return
        if (
            rejection_record.adapter_id != "cut_store.quarantine_transition.v1"
            or rejection_record.reason_code != reason.reason_code
            or rejection_record.subject.kind
            is not audit.RejectionSubjectKind.CUT_ID
            or rejection_record.subject.value != cut_id
            or rejection_record.family != store.cuts[cut_id].family
            or rejection_record.reason_detail != reason.detail
        ):
            return
        audit.emit_rejection_audit(rejection_record, audit_sink)
    except Exception:
        pass


__all__ = [
    "observe_quarantine_transition",
    "observe_regression_sweep",
    "observe_replay",
    "observe_typed_validation",
]
