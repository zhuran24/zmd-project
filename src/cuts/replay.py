"""Store-aware cut replay — B5a typed/legacy double-table (RFC-001 §4.2, PIC-6).

Replay is the high-level wrapper that re-evaluates a persisted cut against the
current state and mutates ``CutStore`` per decision.  B5a splits the historical
single ``FAMILY_VALIDATORS`` table into two mutually-exclusive, exhaustive
tables over the eight live families:

- **typed four** (region_capacity / pattern_nogood / shape_packing_hall /
  power_hitting_set): run the full typed single entry
  (``cut_to_envelope_v1`` → ``validate_and_compile_cut``) over the deep-frozen
  ``ValidatedStateSnapshot`` + production ``FamilyCapabilityRegistry`` carried by
  the ``ReplayContext``.  A ``CompiledCut``/``ShadowValidated`` yields an ATTACH
  decision (``reactivate_cut``) but **never applies to a master** (replay owns no
  master); a ``CutRejection`` maps to HOLD (scope-stale) or QUARANTINE.

- **legacy four** (cutset / port_exposure / component_reach / density_envelope):
  run the legacy diagnostic validator over ``context.legacy_state`` and return a
  ``DiagnosticResult``.  These families are diagnostic-only — they **never call
  ``store.reactivate_cut`` and never enter the active store** (RFC-001 §4.2 /
  risk 16).  A machine assertion pins the two tables disjoint + exhaustive so a
  legacy family can never reach the single entry or step_8.

Refs:
- docs/research/cut_framework_review_gpt56pro_20260710/03_stage_b_implementation_spec.md §4.2/§4.8
- PROJECT_LOCK.md §3A invariant 4 (HOLD vs Quarantine)
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, cast

from src.cuts.family_specs import (
    PRODUCTION_FAMILY_MANIFEST_V1,
    ReplayKind,
    ReplaySpec,
    StaticCallableRef,
)
from src.cuts.lifecycle import (
    AttachDecision,
    BState,
    Cut,
    JsonDict,
    ValidationResult,
    compute_source_digest,
    validate_cut_integrity,
)
from src.cuts.store import CutStore, QuarantineReason

if TYPE_CHECKING:
    from src.cuts.rejection_audit import RejectionAuditSinkV1


LegacyDiagnosticValidator = Callable[[Cut, BState, JsonDict], ValidationResult]


def _production_replay_specs() -> Dict[str, ReplaySpec]:
    """Project the checked manifest into the established replay table shape."""

    replay_specs: Dict[str, ReplaySpec] = {}
    for family, trust in PRODUCTION_FAMILY_MANIFEST_V1.trust_specs.items():
        if not trust.replay.is_available:
            continue
        replay_specs[family] = cast(
            ReplaySpec,
            trust.replay.require(
                family=family,
                capability="replay",
            ),
        )
    return replay_specs


_PRODUCTION_REPLAY_SPECS = _production_replay_specs()

# Typed single-entry families (RFC-001 §4.2): every one of these is routed
# through cut_to_envelope_v1 → validate_and_compile_cut and NEVER through a
# legacy validator or step_8.  pattern_nogood (F5) is here even though it only
# ever yields ShadowValidated — the single entry is still its sole gate.
TYPED_REPLAY_FAMILIES: frozenset[str] = frozenset(
    family
    for family, replay in _PRODUCTION_REPLAY_SPECS.items()
    if replay.kind is ReplayKind.TYPED_SINGLE_ENTRY
)

# Legacy diagnostic-only families: validator returns a ValidationResult that is
# projected into a DiagnosticResult; these NEVER reactivate a cut into the
# active store (store.py reactivate_cut call-surface is cut off for them).
def _legacy_diagnostic_validators() -> Dict[str, LegacyDiagnosticValidator]:
    validators: Dict[str, LegacyDiagnosticValidator] = {}
    for family, replay in _PRODUCTION_REPLAY_SPECS.items():
        if replay.kind is not ReplayKind.LEGACY_DIAGNOSTIC:
            continue
        if type(replay.entrypoint) is not StaticCallableRef:  # pragma: no cover - manifest gate
            raise TypeError(
                f"legacy replay family {family!r} lacks a static callable entrypoint"
            )
        validators[family] = cast(
            LegacyDiagnosticValidator,
            replay.entrypoint.target,
        )
    return validators


LEGACY_DIAGNOSTIC_VALIDATORS: Dict[str, LegacyDiagnosticValidator] = (
    _legacy_diagnostic_validators()
)

# Machine pin: the two dispatch tables are disjoint and together cover exactly
# the eight live families (F8 power_grid_reach is retired, not a replay family).
_ALL_LIVE_REPLAY_FAMILIES: frozenset[str] = frozenset(_PRODUCTION_REPLAY_SPECS)
assert TYPED_REPLAY_FAMILIES.isdisjoint(
    LEGACY_DIAGNOSTIC_VALIDATORS
), "typed and legacy replay tables must be disjoint"
assert (
    TYPED_REPLAY_FAMILIES | frozenset(LEGACY_DIAGNOSTIC_VALIDATORS)
    == _ALL_LIVE_REPLAY_FAMILIES
), "typed ∪ legacy replay tables must be exhaustive over the live families"


@dataclass(frozen=True)
class ReplayContext:
    """Immutable per-replay context (RFC-001 §4.8).

    ``snapshot``/``registry`` drive the typed single entry; ``legacy_state`` is
    the raw BState the legacy diagnostic validators still read.  Built once per
    replay trigger (campaign start / source rotate / ghost transition) via
    ``build_replay_context`` so the deep-frozen snapshot is not rebuilt per cut.
    """

    snapshot: Any
    registry: Any
    legacy_state: BState


@dataclass(frozen=True)
class DiagnosticResult:
    """Legacy-family replay outcome — audit-only, never activates a cut."""

    family: str
    cut_id: str
    outcome: str  # "ok" | "unsound" | "timeout" | "schema_err"
    detail: str = ""


def _safe_monotonic_ns() -> int | None:
    """Read the audited-path timer without giving it control-flow authority."""

    try:
        value = time.monotonic_ns()
    except Exception:
        return None
    return value if type(value) is int and value >= 0 else None


def _audit_text(value: object, *, fallback: str) -> str:
    """Normalize audit-only detail without rewriting established error text."""

    text = str(value).replace("\x00", "\\x00").strip()
    return text or fallback


def _assumption_audit_digest(cut: Cut) -> str | None:
    """Hash the legacy scope assumptions in an audit-only digest domain."""

    try:
        from src.cuts.rejection_audit import assumption_audit_digest_v1

        scope = cut.scope
        assumptions = None if scope is None else scope.active_assumptions
        if type(assumptions) is not tuple:
            return None
        projection: list[tuple[str, str]] = []
        for assumption in assumptions:
            key = getattr(assumption, "key", None)
            value = getattr(assumption, "value", None)
            if type(key) is not str or type(value) is not str:
                return None
            projection.append((key, value))
        return assumption_audit_digest_v1(tuple(projection))
    except Exception:
        return None


def _emit_replay_rejection_best_effort(
    *,
    cut: Cut,
    context: ReplayContext,
    audit_sink: object | None,
    audit_started_ns: int | None,
    reason_code: str,
    reason_detail: str,
    failure_point: str,
) -> None:
    """Build and emit one replay fact after an established terminal transition.

    Every operation in this helper is audit-only and exception-contained.  It
    is intentionally called only after ``hold_cut``/``quarantine_cut`` has
    completed, so neither record construction nor transport can change the cut
    decision or store mutation order.
    """

    if audit_sink is None:
        return
    try:
        from src.cuts.rejection_audit import (
            REJECTION_ADAPTER_SPECS_V1,
            AuditDigestEvidenceV1,
            CostUnit,
            EvidenceKind,
            EvidenceReferenceV1,
            PremiseVerdict,
            RejectionCostMeasureV1,
            RejectionCostV1,
            RejectionPremiseV1,
            RejectionRecordV1,
            RejectionSubjectKind,
            RejectionSubjectV1,
            emit_rejection_audit,
        )

        adapter = REJECTION_ADAPTER_SPECS_V1["replay.rejection_outcome.v1"]
        binding = adapter.reason_binding(reason_code)

        registered_observed = "cut_id found in store.cuts before replay dispatch"
        integrity_ok = "validate_cut_integrity returned None"
        adapter_ok = "cut_to_envelope_v1 returned a CutEnvelope"
        replay_failed = _audit_text(
            reason_detail,
            fallback=f"{reason_code} rejected replay validation",
        )

        if failure_point == "integrity":
            integrity_premise = RejectionPremiseV1(
                premise_id="cut_integrity",
                expected="validate_cut_integrity returns None",
                verdict=PremiseVerdict.VIOLATED,
                observed=replay_failed,
                unavailable_reason=None,
            )
            adapter_premise = RejectionPremiseV1(
                premise_id="adapter_representation_valid",
                expected="the typed adapter returns a valid CutEnvelope when used",
                verdict=PremiseVerdict.UNAVAILABLE,
                observed=None,
                unavailable_reason="integrity rejection occurred before adapter dispatch",
            )
            validation_premise = RejectionPremiseV1(
                premise_id="replay_validation",
                expected="replay validation permits attachment",
                verdict=PremiseVerdict.UNAVAILABLE,
                observed=None,
                unavailable_reason="replay validation did not run after integrity rejection",
            )
        elif failure_point == "adapter":
            integrity_premise = RejectionPremiseV1(
                premise_id="cut_integrity",
                expected="validate_cut_integrity returns None",
                verdict=PremiseVerdict.SATISFIED,
                observed=integrity_ok,
                unavailable_reason=None,
            )
            adapter_premise = RejectionPremiseV1(
                premise_id="adapter_representation_valid",
                expected="the typed adapter returns a valid CutEnvelope when used",
                verdict=PremiseVerdict.VIOLATED,
                observed=replay_failed,
                unavailable_reason=None,
            )
            validation_premise = RejectionPremiseV1(
                premise_id="replay_validation",
                expected="replay validation permits attachment",
                verdict=PremiseVerdict.UNAVAILABLE,
                observed=None,
                unavailable_reason="replay validation did not run after adapter rejection",
            )
        elif failure_point == "typed_validation":
            integrity_premise = RejectionPremiseV1(
                premise_id="cut_integrity",
                expected="validate_cut_integrity returns None",
                verdict=PremiseVerdict.SATISFIED,
                observed=integrity_ok,
                unavailable_reason=None,
            )
            adapter_premise = RejectionPremiseV1(
                premise_id="adapter_representation_valid",
                expected="the typed adapter returns a valid CutEnvelope when used",
                verdict=PremiseVerdict.SATISFIED,
                observed=adapter_ok,
                unavailable_reason=None,
            )
            validation_premise = RejectionPremiseV1(
                premise_id="replay_validation",
                expected="replay validation permits attachment",
                verdict=PremiseVerdict.VIOLATED,
                observed=replay_failed,
                unavailable_reason=None,
            )
        elif failure_point == "legacy_validation":
            integrity_premise = RejectionPremiseV1(
                premise_id="cut_integrity",
                expected="validate_cut_integrity returns None",
                verdict=PremiseVerdict.SATISFIED,
                observed=integrity_ok,
                unavailable_reason=None,
            )
            adapter_premise = RejectionPremiseV1(
                premise_id="adapter_representation_valid",
                expected="the typed adapter returns a valid CutEnvelope when used",
                verdict=PremiseVerdict.UNAVAILABLE,
                observed=None,
                unavailable_reason="legacy diagnostic replay has no typed adapter step",
            )
            validation_premise = RejectionPremiseV1(
                premise_id="replay_validation",
                expected="replay validation permits attachment",
                verdict=PremiseVerdict.VIOLATED,
                observed=replay_failed,
                unavailable_reason=None,
            )
        else:
            return

        premises = (
            RejectionPremiseV1(
                premise_id="cut_registered",
                expected="cut_id is registered in CutStore",
                verdict=PremiseVerdict.SATISFIED,
                observed=registered_observed,
                unavailable_reason=None,
            ),
            integrity_premise,
            adapter_premise,
            validation_premise,
        )

        snapshot = context.snapshot

        def _digest_evidence(value: object, *, unavailable_reason: str) -> AuditDigestEvidenceV1:
            try:
                return AuditDigestEvidenceV1.available(cast(str, value))
            except Exception:
                return AuditDigestEvidenceV1.unavailable(unavailable_reason)

        instance_digest = _digest_evidence(
            getattr(snapshot, "source_digest", None),
            unavailable_reason="current replay instance digest is unavailable",
        )
        state_digest = _digest_evidence(
            getattr(snapshot, "digest", None),
            unavailable_reason="current replay state digest is unavailable",
        )
        raw_assumption_digest = _assumption_audit_digest(cut)
        assumption_digest = (
            AuditDigestEvidenceV1.available(raw_assumption_digest)
            if raw_assumption_digest is not None
            else AuditDigestEvidenceV1.unavailable(
                "cut scope assumptions are unavailable at the replay seam"
            )
        )

        cert = cut.cert
        cert_payload = None if cert is None else cert.cert_payload
        if type(cert_payload) is bytes:
            evidence_digest = AuditDigestEvidenceV1.available(
                hashlib.sha256(cert_payload).hexdigest()
            )
        else:
            evidence_digest = AuditDigestEvidenceV1.unavailable(
                "cut certificate payload is unavailable at the replay seam"
            )
        evidence_references = (
            EvidenceReferenceV1(
                kind=EvidenceKind.CUT_STORE,
                reference=f"cut_store:{_audit_text(cut.cut_id, fallback='unknown-cut')}",
                content_digest=evidence_digest,
            ),
        )

        try:
            audit_finished_ns = _safe_monotonic_ns()
        except Exception:
            audit_finished_ns = None
        if (
            audit_started_ns is not None
            and audit_finished_ns is not None
            and audit_finished_ns >= audit_started_ns
        ):
            cost = RejectionCostV1(
                measures=(
                    RejectionCostMeasureV1(
                        unit=CostUnit.WALL_TIME_NS,
                        value=audit_finished_ns - audit_started_ns,
                    ),
                ),
            )
        else:
            cost = RejectionCostV1(
                measures=(),
                unavailable_reason="monotonic audited-path timing is unavailable",
            )

        record = RejectionRecordV1(
            subject=RejectionSubjectV1(
                kind=RejectionSubjectKind.CUT_ID,
                value=cut.cut_id,
            ),
            adapter_id=adapter.adapter_id,
            family=cut.family,
            reason_code=reason_code,
            reason_detail=_audit_text(reason_detail, fallback=reason_code),
            responsibility_scope=binding.responsibility_scope,
            disposition=binding.disposition,
            premises=premises,
            instance_digest=instance_digest,
            state_digest=state_digest,
            assumption_digest=assumption_digest,
            evidence_references=evidence_references,
            cost=cost,
        )
        emit_rejection_audit(record, cast(Any, audit_sink))
    except Exception:
        # Audit record construction and transport are non-authoritative.
        return


def build_replay_context(state: BState) -> ReplayContext:
    """Construct a ReplayContext from a raw BState (RFC-001 §4.8).

    The deep-frozen bundle + snapshot are built ONCE here (not per cut); a
    construction failure is a TCB fault and propagates fail-closed.
    """

    from src.cuts.frozen_artifacts import build_frozen_artifact_bundle
    from src.cuts.state_snapshot import build_validated_state_snapshot
    from src.cuts.typed_platform import build_production_registry

    if (
        state.canonical_rules is None
        or state.candidate_placements is None
        or state.facility_templates is None
        or state.instance_to_facility_type is None
    ):
        raise ValueError(
            "build_replay_context: state lacks a frozen-artifact source "
            "(canonical_rules/candidate_placements/facility_templates/"
            "instance_to_facility_type) — fail-closed"
        )
    bundle = build_frozen_artifact_bundle(
        canonical_rules=state.canonical_rules,
        candidate_placements=state.candidate_placements,
        facility_templates=state.facility_templates,
        instance_to_facility_type=state.instance_to_facility_type,
        artifact_hashes=state.artifact_hashes,
    )
    snapshot = build_validated_state_snapshot(state, bundle)
    return ReplayContext(
        snapshot=snapshot,
        registry=build_production_registry(),
        legacy_state=state,
    )


def replay_cut(
    cut: Cut,
    store: CutStore,
    context: ReplayContext,
    *,
    iter_index: int = -1,
) -> AttachDecision:
    """Re-evaluate one persisted cut and mutate the store per decision.

    Caller responsibility: ``cut`` must already be in ``store.cuts`` (brand-new
    cuts use the typed single entry directly).  Typed families run the full
    single entry (never applying to a master); legacy families run their
    diagnostic validator and are barred from ``reactivate_cut``.
    """

    if cut.cut_id not in store.cuts:
        raise KeyError(
            f"replay_cut: cut_id={cut.cut_id} 不在 store; "
            f"brand-new cut 应走 typed single entry (validate_and_compile_cut)."
        )

    integrity_error = validate_cut_integrity(cut)
    if integrity_error is not None:
        store.quarantine_cut(
            cut.cut_id,
            QuarantineReason(
                reason_code="cut_integrity_failed",
                detail=integrity_error,
                iter_index=iter_index,
            ),
        )
        return "QUARANTINE"

    if cut.family in TYPED_REPLAY_FAMILIES:
        return _replay_typed(cut, store, context, iter_index=iter_index)
    if cut.family in LEGACY_DIAGNOSTIC_VALIDATORS:
        return _replay_legacy_diagnostic(cut, store, context, iter_index=iter_index)
    # Machine tables are exhaustive over live families; anything else fail-closed.
    raise NotImplementedError(
        f"replay_cut: family={cut.family!r} is in neither the typed nor the "
        f"legacy diagnostic replay table (fail-closed)."
    )


def replay_cut_audited(
    cut: Cut,
    store: CutStore,
    context: ReplayContext,
    *,
    iter_index: int = -1,
    audit_sink: RejectionAuditSinkV1,
) -> AttachDecision:
    """Opt-in replay with a best-effort post-transition rejection sidecar."""

    try:
        audit_started_ns = _safe_monotonic_ns()
    except Exception:
        audit_started_ns = None
    decision = replay_cut(cut, store, context, iter_index=iter_index)
    if decision == "ATTACH":
        return decision

    if decision == "HOLD":
        # Legacy diagnostic "ok" is deliberately held and is not a rejection.
        if cut.family not in TYPED_REPLAY_FAMILIES:
            return decision
        # The frozen replay surface can return HOLD for a scope-stale cut that
        # was already quarantined, without performing a HOLD transition.  Do
        # not emit a sidecar disposition that contradicts the actual store.
        if cut.cut_id not in store.held or cut.cut_id in store.quarantined:
            return decision
        reason_code = "typed_rejected_scope"
        reason_detail = "typed replay rejected the current snapshot at scope stage"
        failure_point = "typed_validation"
    else:
        reason = store.quarantined.get(cut.cut_id)
        if reason is None:
            # An audited wrapper never invents a terminal fact not reflected by
            # the established CutStore transition.
            return decision
        reason_code = reason.reason_code
        reason_detail = reason.detail
        if reason_code == "cut_integrity_failed":
            failure_point = "integrity"
        elif reason_code == "typed_adapter_rejected":
            failure_point = "adapter"
        elif reason_code.startswith("typed_rejected_"):
            failure_point = "typed_validation"
        elif reason_code.startswith("legacy_diagnostic_"):
            failure_point = "legacy_validation"
        else:
            return decision

    _emit_replay_rejection_best_effort(
        cut=cut,
        context=context,
        audit_sink=audit_sink,
        audit_started_ns=audit_started_ns,
        reason_code=reason_code,
        reason_detail=reason_detail,
        failure_point=failure_point,
    )
    return decision


def _replay_typed(
    cut: Cut,
    store: CutStore,
    context: ReplayContext,
    *,
    iter_index: int,
) -> AttachDecision:
    """Typed-family replay: full single entry, ATTACH decision, never apply."""

    from src.cuts.typed_platform import (
        CompiledCut,
        CutRejection,
        ShadowValidated,
        cut_to_envelope_v1,
        validate_and_compile_cut,
    )

    try:
        envelope = cut_to_envelope_v1(cut)
    except (TypeError, ValueError) as exc:
        store.quarantine_cut(
            cut.cut_id,
            QuarantineReason(
                reason_code="typed_adapter_rejected",
                detail=str(exc),
                iter_index=iter_index,
            ),
        )
        return "QUARANTINE"

    result = validate_and_compile_cut(envelope, context.snapshot, context.registry)
    if isinstance(result, (CompiledCut, ShadowValidated)):
        # Validity re-affirmed for this snapshot — reactivate as store
        # bookkeeping ONLY.  Replay owns no master and NEVER applies (step_8);
        # a ShadowValidated (F5) therefore never becomes a master constraint.
        store.reactivate_cut(cut.cut_id)
        return "ATTACH"

    assert isinstance(result, CutRejection)
    if result.stage == "scope":
        # Scope-stale — may re-attach on a matching state later.
        if cut.cut_id not in store.quarantined:
            store.hold_cut(cut.cut_id)
        return "HOLD"
    store.quarantine_cut(
        cut.cut_id,
        QuarantineReason(
            reason_code=f"typed_rejected_{result.stage}",
            detail=result.reason,
            iter_index=iter_index,
        ),
    )
    return "QUARANTINE"


def _replay_legacy_diagnostic(
    cut: Cut,
    store: CutStore,
    context: ReplayContext,
    *,
    iter_index: int,
) -> AttachDecision:
    """Legacy-family replay: diagnostic validator only — never reactivate."""

    diagnostic = run_legacy_diagnostic(cut, context.legacy_state)
    if diagnostic.outcome == "ok":
        # Diagnostic-only: a legacy cut can never (re)enter the active store —
        # keep it held so it is not mistaken for an active constraint.
        if cut.cut_id not in store.quarantined:
            store.hold_cut(cut.cut_id)
        return "HOLD"

    reason_code_map = {
        "unsound": "legacy_diagnostic_unsound",
        "timeout": "legacy_diagnostic_timeout",
        "schema_err": "legacy_diagnostic_schema_err",
    }
    store.quarantine_cut(
        cut.cut_id,
        QuarantineReason(
            reason_code=reason_code_map.get(diagnostic.outcome, "legacy_diagnostic_error"),
            detail=diagnostic.detail,
            iter_index=iter_index,
        ),
    )
    return "QUARANTINE"


def run_legacy_diagnostic(cut: Cut, state: BState) -> DiagnosticResult:
    """Run one legacy diagnostic validator, projecting to a DiagnosticResult.

    ``canonical_rules`` come from ``state.canonical_rules`` (legacy validators
    read the raw BState); a state without rules fails closed as ``schema_err``
    (the validator cannot re-derive its cert without the rule source).
    """

    validator = LEGACY_DIAGNOSTIC_VALIDATORS[cut.family]
    canonical_rules = state.canonical_rules
    if canonical_rules is None:
        return DiagnosticResult(
            family=cut.family,
            cut_id=cut.cut_id,
            outcome="schema_err",
            detail="legacy diagnostic requires canonical_rules on the state (fail-closed)",
        )
    vr = validator(cut, state, canonical_rules)
    return DiagnosticResult(
        family=cut.family,
        cut_id=cut.cut_id,
        outcome=vr.kind,
        detail=vr.detail or "",
    )


def regression_sweep(
    store: CutStore,
    context: ReplayContext,
    *,
    iter_index: int = -1,
) -> Dict[str, int]:
    """Re-validate all non-quarantined cuts (cut_lifecycle_v2 §9).

    Triggered by campaign start, source-artifact rotation, or manual audit.
    Returns per-decision counts.  The snapshot in ``context`` is built once by
    the trigger (``build_replay_context``) — never rebuilt per cut.
    """
    counts: Dict[str, int] = {
        "ATTACH": 0,
        "HOLD": 0,
        "QUARANTINE": 0,
        "skipped_quarantined": 0,
    }
    for cut_id in list(store.cuts.keys()):
        if cut_id in store.quarantined:
            counts["skipped_quarantined"] += 1
            continue
        cut = store.cuts[cut_id]
        decision = replay_cut(cut, store, context, iter_index=iter_index)
        counts[decision] += 1
    return counts


def regression_sweep_audited(
    store: CutStore,
    context: ReplayContext,
    *,
    iter_index: int = -1,
    audit_sink: RejectionAuditSinkV1,
) -> Dict[str, int]:
    """Opt-in regression sweep emitting audited rejection records only."""

    counts: Dict[str, int] = {
        "ATTACH": 0,
        "HOLD": 0,
        "QUARANTINE": 0,
        "skipped_quarantined": 0,
    }
    for cut_id in list(store.cuts.keys()):
        if cut_id in store.quarantined:
            counts["skipped_quarantined"] += 1
            continue
        cut = store.cuts[cut_id]
        decision = replay_cut_audited(
            cut,
            store,
            context,
            iter_index=iter_index,
            audit_sink=audit_sink,
        )
        counts[decision] += 1
    return counts


# ---- Internal helpers -----------------------------------------------------

def _diagnose_quarantine(cut: Cut, state: BState) -> str:
    """Best-effort quarantine reason detail for a stale legacy-state replay."""
    if cut.scope is None:
        return "missing cut scope"
    from src.cuts.lifecycle import (
        GHOST_AGNOSTIC,
        compute_blocked_cells_hash,
        compute_exterior_blocks_hash,
        compute_ghost_rect_id,
    )

    current_digest = compute_source_digest(state)
    if cut.scope.source_digest != current_digest:
        return f"source_digest mismatch (cut={cut.scope.source_digest!r}, current={current_digest!r})"
    current_ghost_id = compute_ghost_rect_id(state.ghost_rect)
    is_ghost_agnostic = cut.scope.ghost_rect_id == GHOST_AGNOSTIC
    if is_ghost_agnostic:
        if cut.scope.exterior_blocks_hash != compute_exterior_blocks_hash(state):
            return "exterior_blocks_hash changed (GHOST_AGNOSTIC cut)"
    else:
        if cut.scope.ghost_rect_id == current_ghost_id and \
           cut.scope.blocked_cells_hash != compute_blocked_cells_hash(state):
            return "blocked_cells_hash changed (ghost-bound cut)"
    for fname, h in cut.scope.artifact_hashes.items():
        if state.artifact_hashes.get(fname) != h:
            return f"artifact {fname} hash mismatch"
    return "scope verify failed (unspecified branch)"
