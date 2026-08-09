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

from dataclasses import dataclass
from typing import Any, Callable, Dict

from src.cuts.families.component_reach import validate_component_reach
from src.cuts.families.cutset import validate_cutset
from src.cuts.families.density_envelope import validate_density_envelope
from src.cuts.families.port_exposure import validate_port_exposure
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


LegacyDiagnosticValidator = Callable[[Cut, BState, JsonDict], ValidationResult]


# Typed single-entry families (RFC-001 §4.2): every one of these is routed
# through cut_to_envelope_v1 → validate_and_compile_cut and NEVER through a
# legacy validator or step_8.  pattern_nogood (F5) is here even though it only
# ever yields ShadowValidated — the single entry is still its sole gate.
TYPED_REPLAY_FAMILIES: frozenset[str] = frozenset(
    {"region_capacity", "pattern_nogood", "shape_packing_hall", "power_hitting_set"}
)

# Legacy diagnostic-only families: validator returns a ValidationResult that is
# projected into a DiagnosticResult; these NEVER reactivate a cut into the
# active store (store.py reactivate_cut call-surface is cut off for them).
LEGACY_DIAGNOSTIC_VALIDATORS: Dict[str, LegacyDiagnosticValidator] = {
    "cutset": validate_cutset,
    "port_exposure": validate_port_exposure,
    "component_reach": validate_component_reach,
    "density_envelope": validate_density_envelope,
}

# Machine pin: the two dispatch tables are disjoint and together cover exactly
# the eight live families (F8 power_grid_reach is retired, not a replay family).
_ALL_LIVE_REPLAY_FAMILIES: frozenset[str] = frozenset(
    {
        "cutset",
        "component_reach",
        "density_envelope",
        "pattern_nogood",
        "port_exposure",
        "power_hitting_set",
        "region_capacity",
        "shape_packing_hall",
    }
)
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
