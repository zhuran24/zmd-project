"""P1.3 → B5a — store-aware replay_cut + regression_sweep (typed/legacy double-table).

B5a (RFC-001 §4.2) rewired replay onto the typed single entry:

- typed families (region_capacity / pattern_nogood / shape_packing_hall /
  power_hitting_set) run ``cut_to_envelope_v1`` → ``validate_and_compile_cut``
  over a ``ReplayContext`` (deep-frozen snapshot + production registry) and
  **never apply to a master**.  A CompiledCut/ShadowValidated → ATTACH
  (reactivate); a CutRejection maps stage="scope" → HOLD, else → QUARANTINE.
- legacy families (cutset / port_exposure / component_reach / density_envelope)
  run their diagnostic validator and **never reactivate into the active store**.

The pre-B5a per-family ``FAMILY_VALIDATORS`` table + raw ``step_6_attach_scope_check
(cut, state)`` are gone; scope currentness now lives in the typed single entry.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from src.cuts.lifecycle import (
    BState,
    Cut,
    GroupState,
    OracleCert,
    compute_source_digest,
    validate_cut_integrity,
)
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
from src.cuts.replay import (
    LEGACY_DIAGNOSTIC_VALIDATORS,
    TYPED_REPLAY_FAMILIES,
    DiagnosticResult,
    build_replay_context,
    regression_sweep,
    replay_cut,
    run_legacy_diagnostic,
)
from src.cuts.store import CutStore, QuarantineReason
from src.tests.cuts.test_family_cutset import _make_cutset_cut
from src.tests.cuts.test_stage_b_contracts import _bound_region_sources


# ---------------------------------------------------------------------------
# Typed-consistent F1 fixtures: the single entry requires the eight production
# artifact dependencies (candidate_placements / canonical_rules / ... ), so the
# replay state must carry them and be geometrically consistent with the F1
# oracle.  ``_bound_region_sources`` (from the Stage-B contract tests) supplies
# exactly that world.
# ---------------------------------------------------------------------------


def _f1_state(*, group_id: str = "boundary_io") -> BState:
    sources = _bound_region_sources(BState, GroupState, ghost_rect=(0, 0, 3, 1), group_id=group_id)
    sources["state"].source_digest = compute_source_digest(sources["state"])
    return sources["state"]


def _f1_cut(state: BState) -> Cut:
    cuts = generate_region_capacity_cuts(state, state.canonical_rules)
    assert len(cuts) == 1, "expected exactly one F1 cut from the bound-region world"
    cut = cuts[0]
    assert cut.scope is not None and cut.cert is not None
    return cut


# ---------------------------------------------------------------------------
# add_cut invariants (unchanged by B5a — no replay involved)
# ---------------------------------------------------------------------------


def test_add_cut_illegal_initial_state_no_partial_mutation():
    """GPT pro v6 P0: add_cut verifies initial_state BEFORE mutation."""
    cut = _f1_cut(_f1_state())
    store = CutStore()
    with pytest.raises(ValueError, match="initial_state"):
        store.add_cut(cut, initial_state="pending")
    assert cut.cut_id not in store.cuts, "raise 后 cut 残留 self.cuts (silent attach)"
    assert not store.is_active(cut.cut_id)


def test_add_cut_default_held_no_silent_attach():
    """GPT pro v5 P0-2: add_cut default held — must go through replay gate."""
    cut = _f1_cut(_f1_state())
    store = CutStore()
    store.add_cut(cut)
    assert not store.is_active(cut.cut_id)
    assert cut.cut_id in store.held
    # legacy bypass: initial_state="active" still allowed (test fixture only)
    store2 = CutStore()
    store2.add_cut(cut, initial_state="active")
    assert store2.is_active(cut.cut_id)


# ---------------------------------------------------------------------------
# scope evidence is a snapshot, not a live alias (B5a: enforced by the typed
# scope-currentness check rather than the legacy step-6)
# ---------------------------------------------------------------------------


def test_cut_scope_artifact_hashes_snapshot_not_state_alias():
    """A cut's artifact scope is generation-time evidence, not a live BState dict.

    If a cut kept an alias to ``state.artifact_hashes``, source/artifact rotation
    would forge the "new" hash on both sides.  The typed replay must instead see
    the persisted (stale) evidence and fail closed — never silent ATTACH.
    """
    state = _f1_state()
    cut = _f1_cut(state)
    assert cut.scope.artifact_hashes is not state.artifact_hashes

    drifted = _f1_state()
    drifted_hashes = dict(drifted.artifact_hashes)
    drifted_hashes["canonical_rules"] = "e" * 64
    object.__setattr__(drifted, "artifact_hashes", drifted_hashes)
    drifted.source_digest = compute_source_digest(drifted)

    store = CutStore()
    store.add_cut(cut)
    decision = replay_cut(cut, store, build_replay_context(drifted))
    assert decision != "ATTACH"
    assert not store.is_active(cut.cut_id)


# ---------------------------------------------------------------------------
# replay_cut ATTACH path (typed single entry → CompiledCut → reactivate)
# ---------------------------------------------------------------------------


def test_replay_attach_path_with_validator_ok():
    """ATTACH: F1 cut re-compiles against the current snapshot → reactivate."""
    state = _f1_state()
    cut = _f1_cut(state)
    store = CutStore()
    store.add_cut(cut)
    store.hold_cut(cut.cut_id)

    decision = replay_cut(cut, store, build_replay_context(state))

    assert decision == "ATTACH"
    assert store.is_active(cut.cut_id)


def test_replay_attach_path_without_explicit_validator_rules_uses_state_fallback():
    """The canonical_rules kwarg is gone; the ReplayContext carries the snapshot
    (built once from the state).  A same-state replay still ATTACHes."""
    state = _f1_state()
    cut = _f1_cut(state)
    store = CutStore()
    store.add_cut(cut)
    store.hold_cut(cut.cut_id)

    context = build_replay_context(state)
    decision = replay_cut(cut, store, context)

    assert decision == "ATTACH"
    assert store.is_active(cut.cut_id)


# ---------------------------------------------------------------------------
# replay_cut HOLD path (typed CutRejection stage="scope" → not active, not quarantined)
# ---------------------------------------------------------------------------


def test_replay_hold_when_exterior_blocks_change():
    """B5a: an exterior change moves the state source digest; the persisted cut
    is scope-stale (CutRejection stage="scope") → HOLD, not QUARANTINE."""
    gen_state = _f1_state()
    cut = _f1_cut(gen_state)
    store = CutStore()
    store.add_cut(cut)

    replay_state = _f1_state()
    object.__setattr__(replay_state, "exterior_blocks", frozenset({(17, 0)}))
    replay_state.source_digest = compute_source_digest(replay_state)

    decision = replay_cut(cut, store, build_replay_context(replay_state))

    assert decision == "HOLD"
    assert cut.cut_id in store.held
    assert cut.cut_id not in store.quarantined
    assert not store.is_active(cut.cut_id)


def test_replay_hold_when_canonical_rules_lost():
    """B5a repurpose of the old oracle-version HOLD: a replay state that lost its
    canonical rules cannot even build a ReplayContext — the frozen-artifact
    source guard raises fail-closed (a TCB fault, never a silent ATTACH)."""
    gen_state = _f1_state()
    cut = _f1_cut(gen_state)
    store = CutStore()
    store.add_cut(cut)

    lossy = _f1_state()
    object.__setattr__(lossy, "canonical_rules", None)

    with pytest.raises(ValueError, match="lacks a frozen-artifact source"):
        build_replay_context(lossy)
    assert not store.is_active(cut.cut_id)
    assert cut.cut_id not in store.quarantined


# ---------------------------------------------------------------------------
# replay_cut QUARANTINE path (integrity + typed proof rejection)
# ---------------------------------------------------------------------------


def test_replay_quarantine_on_integrity_drift():
    """cert/oracle hash drift is caught by the integrity gate before dispatch."""
    state = _f1_state()
    cut = _f1_cut(state)
    tampered = dataclasses.replace(cut, oracle_cert_hash="0" * 64)
    store = CutStore()
    store.add_cut(tampered)

    decision = replay_cut(tampered, store, build_replay_context(state))

    assert decision == "QUARANTINE"
    assert store.quarantined[tampered.cut_id].reason_code == "cut_integrity_failed"
    assert not store.is_active(tampered.cut_id)


def test_replay_quarantine_when_post_attach_validation_unsound():
    """A cut that passes the adapter but whose cert contradicts the snapshot
    recomputation is rejected by the typed single entry at stage="proof"
    → QUARANTINE (reason_code typed_rejected_proof)."""
    state = _f1_state()
    cut = _f1_cut(state)
    assert cut.geometric_payload is not None and cut.cert is not None
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = 999
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    tampered_hash = hashlib.sha256(tampered_payload).hexdigest()
    tampered_cut = Cut(
        cut_id=cut.cut_id,
        family=cut.family,
        literals=None,
        geometric_payload=tampered_payload,
        scope=cut.scope,
        cert=OracleCert(
            cert_kind=cut.cert.cert_kind,
            cert_payload=tampered_payload,
            cert_hash=tampered_hash,
        ),
        family_version=cut.family_version,
        validator_version=cut.validator_version,
        oracle_cert_hash=tampered_hash,
    )
    store = CutStore()
    store.add_cut(tampered_cut)

    decision = replay_cut(tampered_cut, store, build_replay_context(state))

    assert decision == "QUARANTINE"
    reason = store.quarantined[tampered_cut.cut_id]
    assert reason.reason_code == "typed_rejected_proof"
    assert "cap_R" in reason.detail


# ---------------------------------------------------------------------------
# Brand-new cut precondition
# ---------------------------------------------------------------------------


def test_replay_cut_not_in_store_raises():
    state = _f1_state()
    cut = _f1_cut(state)
    store = CutStore()  # not added

    with pytest.raises(KeyError, match="不在 store"):
        replay_cut(cut, store, build_replay_context(state))


# ---------------------------------------------------------------------------
# B5a double-table (RFC-001 §4.2): disjoint + exhaustive; legacy never activates
# ---------------------------------------------------------------------------


def test_replay_double_table_is_disjoint_and_exhaustive():
    typed = set(TYPED_REPLAY_FAMILIES)
    legacy = set(LEGACY_DIAGNOSTIC_VALIDATORS)
    assert typed.isdisjoint(legacy)
    assert typed == {"region_capacity", "pattern_nogood", "shape_packing_hall", "power_hitting_set"}
    assert legacy == {"cutset", "port_exposure", "component_reach", "density_envelope"}
    # Exhaustive over the eight live families (F8 power_grid_reach is retired).
    assert typed | legacy == {
        "cutset",
        "component_reach",
        "density_envelope",
        "pattern_nogood",
        "port_exposure",
        "power_hitting_set",
        "region_capacity",
        "shape_packing_hall",
    }


def test_legacy_family_replay_never_reactivates_into_active_store():
    """A legacy diagnostic family (cutset) is routed to the diagnostic validator
    only — it can never re-enter the active store or reach the typed single
    entry / step_8 (RFC-001 §4.2 / risk 16)."""
    state = _f1_state()
    cutset_cut = _make_cutset_cut({(0, 0)}, {(4, 0)}, cut_size=1, commodity_demand=2)
    # Repair the fixture's placeholder hash so integrity passes and replay
    # reaches the LEGACY diagnostic path (not the integrity gate).
    correct_hash = hashlib.sha256(cutset_cut.cert.cert_payload).hexdigest()
    cutset_cut = dataclasses.replace(
        cutset_cut,
        cert=dataclasses.replace(cutset_cut.cert, cert_hash=correct_hash),
        oracle_cert_hash=correct_hash,
    )
    assert validate_cut_integrity(cutset_cut) is None
    assert cutset_cut.family in LEGACY_DIAGNOSTIC_VALIDATORS
    assert cutset_cut.family not in TYPED_REPLAY_FAMILIES

    store = CutStore()
    store.add_cut(cutset_cut)
    decision = replay_cut(cutset_cut, store, build_replay_context(state))

    assert decision in ("HOLD", "QUARANTINE")
    assert not store.is_active(cutset_cut.cut_id)
    if decision == "QUARANTINE":
        # Went through the legacy diagnostic path, not the typed/integrity paths.
        assert store.quarantined[cutset_cut.cut_id].reason_code.startswith("legacy_diagnostic_")


def test_run_legacy_diagnostic_returns_diagnostic_result_without_store_side_effects():
    state = _f1_state()
    cutset_cut = _make_cutset_cut({(0, 0)}, {(4, 0)}, cut_size=1, commodity_demand=2)
    result = run_legacy_diagnostic(cutset_cut, state)
    assert isinstance(result, DiagnosticResult)
    assert result.family == "cutset"
    assert result.outcome in ("ok", "unsound", "timeout", "schema_err")


# ---------------------------------------------------------------------------
# regression_sweep
# ---------------------------------------------------------------------------


def test_regression_sweep_skips_quarantined():
    state = _f1_state()
    cut_a = _f1_cut(state)
    assert cut_a.scope is not None and cut_a.cert is not None
    cut_b = Cut(
        cut_id=f"{cut_a.cut_id}-b",
        family=cut_a.family,
        literals=None,
        geometric_payload=cut_a.geometric_payload,
        scope=cut_a.scope,
        cert=cut_a.cert,
        family_version=cut_a.family_version,
        validator_version=cut_a.validator_version,
        oracle_cert_hash=cut_a.oracle_cert_hash,
    )
    store = CutStore()
    store.add_cut(cut_a)
    store.add_cut(cut_b)
    store.quarantine_cut(cut_a.cut_id, QuarantineReason(reason_code="prior"))

    counts = regression_sweep(store, build_replay_context(state))

    assert counts["skipped_quarantined"] == 1
    assert counts["ATTACH"] == 1
    assert counts["QUARANTINE"] == 0
    assert counts["HOLD"] == 0


def test_regression_sweep_attach_all():
    state = _f1_state()
    cut = _f1_cut(state)
    store = CutStore()
    store.add_cut(cut)

    counts = regression_sweep(store, build_replay_context(state))

    assert counts["ATTACH"] == 1
    assert counts["skipped_quarantined"] == 0
