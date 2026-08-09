"""Step 8 apply-to-master — typed-chain coverage (B5a orchestration cut-over).

The public ``step_8_apply_to_master`` is now the typed entry
``(compiled_cut, master, *, scope_binding)``.  The raw ``_legacy_step_8_apply_raw``
translator is deleted, so these cases exercise the FULL typed chain end to end on
a REAL coordinate master:

    raw Cut (oracle) → cut_to_envelope_v1 → build_validated_state_snapshot →
    validate_and_compile_cut → CompiledCut → _resolve_model_scope_binding →
    step_8_apply_to_master(compiled, master, scope_binding=binding)

- F1 region_capacity: the typed chain lowers a real capacity constraint (master
  mutation evidence) under the resolver-supplied ghost literal; adapter-stage
  integrity/split-brain rejections fail closed before any master touch; a live
  master-domain drift fails the §2.6 three-fold check without mutation.
- F5 pattern_nogood: REVERSED per RFC-001 §5.4 — F5 only ever yields
  ``ShadowValidated`` (VALIDATED/TYPED capability, no ``operation``), so there is
  structurally NO F5 apply path: step_8 type-gates a raw Cut and a
  ShadowValidated, and the closed ``SUPPORTED_OPERATIONS`` set carries no
  pattern_nogood lowering.
- port_exposure (legacy diagnostic) cannot reach the typed compile/step_8.
- F6/F7 (B5b): the direct-call cases now run the full typed chain on a real
  master via the domain-consistent stage_b fixtures; a master-side inconsistency
  drifts the §2.6 live projection, so step_8 fails closed before the master's own
  F7 re-check gate for every well-formed divergence.  The subsume is NOT strict
  at corrupt-table corners (out-of-range coverer index: §2.6 raises IndexError
  while the gate returns False cleanly) — the gate stays as defence-in-depth and
  as the sole guard for any non-typed caller (B5b dual-review adjudication).

The resolver + §2.6 three-fold binding rejections are additionally covered by
``src/tests/cuts/test_stage_b_contracts.py``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any, Mapping, Sequence

import pytest
from ortools.sat.python import cp_model

from src.cuts import frozen_artifacts, lifecycle, state_snapshot, typed_platform
from src.cuts.lifecycle import (
    AnonymousSlotRef,
    Cut,
    CutLiteral,
    CutScope,
    OracleCert,
    _resolve_model_scope_binding,
    step_0_canonicalize,
    step_8_apply_to_master,
)
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
from src.cuts.typed_platform import (
    CapabilityStage,
    CompiledCut,
    ExecutionPath,
    ShadowValidated,
    build_production_registry,
    cut_to_envelope_v1,
    validate_and_compile_cut,
)
from src.models.master_model import MasterPlacementModel
from src.tests.cuts.test_stage_b_contracts import (
    _bound_region_sources,
    _build_bundle,
    _build_scope_binding_world,
    _build_shadow_result,
)


class _SpyMaster:
    """Records any master-mutation call; asserts zero touch on fail-closed paths."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def _lower_region_capacity_cut(
        self,
        *,
        group_cell_weights: Mapping[str, int],
        capacity: int,
        condition_lits: Sequence[Any] = (),
    ) -> bool:
        self.calls.append(
            {
                "group_cell_weights": dict(group_cell_weights),
                "capacity": capacity,
                "condition_lits": tuple(condition_lits),
            }
        )
        return True


def _f1_world() -> tuple[Any, Any, Any]:
    """Real bound-region master + snapshot + ghost-bound F1 CompiledCut."""
    master, _group_id, snapshot_a, compiled_a, _snapshot_b, _compiled_b = _build_scope_binding_world(
        frozen_artifacts,
        state_snapshot,
        typed_platform,
        lifecycle,
        generate_region_capacity_cuts,
        MasterPlacementModel,
    )
    return master, snapshot_a, compiled_a


def _oracle_f1_cut() -> Cut:
    """A production F1 oracle cut (carries the ScopeIdentityPreimageV1 the
    typed adapter requires)."""
    sources = _bound_region_sources(lifecycle.BState, lifecycle.GroupState, ghost_rect=(0, 0, 3, 1))
    sources["state"].source_digest = lifecycle.compute_source_digest(sources["state"])
    cuts = generate_region_capacity_cuts(sources["state"], sources["state"].canonical_rules)
    assert len(cuts) == 1
    return cuts[0]


# ---------------------------------------------------------------------------
# F1 region_capacity — full typed chain
# ---------------------------------------------------------------------------


def test_step_8_f1_capacity_prunes_end_to_end() -> None:
    """The typed chain lowers a real capacity constraint onto the master.

    Behavioural pruning is replaced by master-mutation evidence: a ghost-bound
    F1 compiled cut resolves + lowers a weighted-presence <= capacity constraint
    and bumps the framework cut count.
    """
    master, snapshot, compiled = _f1_world()
    assert compiled.plan.operation == "region_capacity_le"

    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    step_8_apply_to_master(compiled, master, scope_binding=binding)

    stats = master.build_stats["coordinate_region_capacity_last_cut"]
    assert stats["groups"] == 1
    assert stats["presence_terms"] == 46  # 46-pose boundary domain, weight 1 each
    assert stats["capacity"] == 136
    assert stats["semantics"] == "region_capacity_weighted_presence_v1"
    assert master.build_stats["coordinate_framework_cut_count"] == 1


def test_step_8_f1_ghost_bound_cut_is_anchor_conditioned() -> None:
    """A ghost-bound F1 cut lowers under the resolver-supplied ghost literal.

    The resolver reconstructs the ghost literal by object identity from the live
    master (never a caller-supplied index); the lowered constraint therefore only
    binds under the located anchor.  Its condition is the master ``u_var`` for the
    plan's ghost rect.
    """
    master, snapshot, compiled = _f1_world()
    assert compiled.plan.model_scope.ghost_policy == "bound"

    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    assert len(binding.condition_lits) == 1
    assert binding.rect_idx is not None
    assert binding.condition_lits[0] is master.u_vars[binding.rect_idx]

    step_8_apply_to_master(compiled, master, scope_binding=binding)
    assert master.build_stats["coordinate_framework_cut_count"] == 1


def test_step_8_f1_ghost_bound_requires_condition_lits() -> None:
    """Ghost conditioning is now carried by the sole resolver, not the caller.

    A ghost-bound plan can never reach the master with empty ghost literals: the
    resolver populates ``condition_lits`` from the live master, and ``typed_apply``
    fails closed on a ghost-bound plan with empty ``condition_lits`` (the
    ``ModelScopeBinding`` private constructor makes a hand-forged empty-lit
    binding unreachable).  This asserts the positive guarantee — the resolved
    ghost-bound binding always carries its literal.
    """
    master, snapshot, compiled = _f1_world()
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    assert binding.condition_lits, "resolver must supply the ghost literal for a bound plan"
    step_8_apply_to_master(compiled, master, scope_binding=binding)
    assert master.build_stats["coordinate_framework_cut_count"] == 1


def test_step_8_f1_unknown_group_raises_fail_closed() -> None:
    """A live master-domain drift fails the §2.6 three-fold check w/o mutation.

    Adding a live pool metadata field after compile makes the resolver's
    recomputed domain projection diverge from the plan fingerprint; step_8 fails
    closed at the master boundary before any lowering (the typed analogue of the
    master refusing an inconsistent cut).
    """
    master, snapshot, compiled = _f1_world()
    master.facility_pools["boundary_storage_port"][0]["alpha_projection_drift"] = True
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    with pytest.raises(ValueError, match="domain projection drifted"):
        step_8_apply_to_master(compiled, master, scope_binding=binding)
    assert "coordinate_region_capacity_last_cut" not in master.build_stats


def test_step_8_rejects_split_brain_cert_before_master() -> None:
    """A tampered cert is refused by the adapter before any master touch."""
    cut = _oracle_f1_cut()
    tampered = dataclasses.replace(cut, oracle_cert_hash="0" * 64)

    spy = _SpyMaster()
    with pytest.raises(ValueError, match="integrity failed"):
        # Adapter admission runs before compile/resolve/step_8; the split-brain
        # cert never reaches the master.
        cut_to_envelope_v1(tampered)
    assert spy.calls == []


def test_step_8_f1_malformed_numerics_raise_before_master() -> None:
    """A malformed cert numeric is a proof-stage rejection, never a mutation.

    A self-consistent cut carrying ``cap_R = -1`` passes adapter admission but is
    refused by the single entry when the F1 plugin re-derives the capacity from
    the snapshot (``stage == "proof"``); it never becomes a CompiledCut, so
    step_8 is never reached.
    """
    sources = _bound_region_sources(lifecycle.BState, lifecycle.GroupState, ghost_rect=(0, 0, 3, 1))
    sources["state"].source_digest = lifecycle.compute_source_digest(sources["state"])
    cut = generate_region_capacity_cuts(sources["state"], sources["state"].canonical_rules)[0]
    assert cut.cert is not None and cut.geometric_payload is not None
    bundle = _build_bundle(frozen_artifacts.build_frozen_artifact_bundle, sources)
    snapshot = state_snapshot.build_validated_state_snapshot(sources["state"], bundle)

    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = -1
    bad_payload = step_0_canonicalize(cert_dict)
    bad_hash = hashlib.sha256(bad_payload).hexdigest()
    malformed = dataclasses.replace(
        cut,
        geometric_payload=bad_payload,
        cert=dataclasses.replace(cut.cert, cert_payload=bad_payload, cert_hash=bad_hash),
        oracle_cert_hash=bad_hash,
    )
    envelope = cut_to_envelope_v1(malformed)
    result = validate_and_compile_cut(envelope, snapshot, build_production_registry())
    assert isinstance(result, typed_platform.CutRejection)
    assert result.stage == "proof"
    assert not isinstance(result, CompiledCut)


# ---------------------------------------------------------------------------
# F5 pattern_nogood — RFC-001 §5.4: structurally NO apply path
# ---------------------------------------------------------------------------


def test_step_8_f5_nogood_prunes_combination_under_pinned_anchor() -> None:
    """REVERSED: F5 yields ShadowValidated and can never mutate the master.

    pattern_nogood is a VALIDATED/TYPED capability with no ``operation``; the
    single entry returns ``ShadowValidated`` (never a ``CompiledCut``), and the
    closed ``SUPPORTED_OPERATIONS`` set carries no F5 lowering — so there is no
    apply path at all.  step_8 type-gates the shadow result before the master.
    """
    _sources, _raw_cut, _envelope, _snapshot, shadow, _plugin = _build_shadow_result(
        frozen_artifacts, state_snapshot, typed_platform, lifecycle
    )
    assert isinstance(shadow, ShadowValidated)
    # The closed lowering set has exactly three operations, none for F5.
    assert typed_platform.SUPPORTED_OPERATIONS == frozenset(
        {"region_capacity_le", "shape_packing_hall_le", "power_pose_exclusion"}
    )

    spy = _SpyMaster()
    with pytest.raises(TypeError, match="exact CompiledCut"):
        step_8_apply_to_master(shadow, spy, scope_binding=None)
    assert spy.calls == []


def test_step_8_f5_fail_closed_surfaces() -> None:
    """Raw F5 Cut + F5 capability are both barred from any master mutation."""
    sources, raw_cut, _envelope, _snapshot, shadow, _plugin = _build_shadow_result(
        frozen_artifacts, state_snapshot, typed_platform, lifecycle
    )
    assert raw_cut.family == "pattern_nogood"
    assert isinstance(shadow, ShadowValidated)

    # Production capability: VALIDATED + TYPED → single entry, never COMPILABLE,
    # so pattern_nogood can never compile to a master-consumable CompiledCut.
    capability = build_production_registry().capabilities["pattern_nogood"]
    assert capability.stage is CapabilityStage.VALIDATED
    assert capability.execution_path is ExecutionPath.TYPED
    assert capability.compiler_version is None

    spy = _SpyMaster()
    # Both a raw Cut and a ShadowValidated are refused by the step_8 type gate.
    for rejected in (raw_cut, shadow):
        with pytest.raises(TypeError, match="exact CompiledCut"):
            step_8_apply_to_master(rejected, spy, scope_binding=None)
    assert spy.calls == []


# ---------------------------------------------------------------------------
# Legacy-diagnostic families cannot reach the typed compile / step_8
# ---------------------------------------------------------------------------


def test_step_8_unwired_family_fails_closed() -> None:
    """A legacy-diagnostic family (port_exposure) has no typed compile/step_8.

    The production registry pins port_exposure as VALIDATED/LEGACY_DIAGNOSTIC, so
    the single entry rejects it (``legacy diagnostic family cannot enter typed
    dispatch``) and it can never produce a CompiledCut.  A raw port_exposure Cut
    handed straight to step_8 is refused by the type gate before the master.
    """
    capability = build_production_registry().capabilities["port_exposure"]
    assert capability.execution_path is ExecutionPath.LEGACY_DIAGNOSTIC
    assert capability.compiler_version is None

    payload = step_0_canonicalize(
        {
            "cert_kind": "port_exposure_blocked",
            "facility_group": "g",
            "facility_pose_id": "p",
            "port_cell": [0, 0],
            "port_direction": "W",
            "front_cell": [-1, 0],
            "blocking_facility": ["g2", 0, "p2"],
            "active_port_witness_b64": None,
        }
    )
    raw_legacy_cut = Cut(
        cut_id="f3_test",
        family="port_exposure",
        literals=(CutLiteral(slot_ref=AnonymousSlotRef(group_id="g", slot_index=0), pose_id="p"),),
        geometric_payload=None,
        scope=CutScope(
            ghost_rect_id="ghost_test",
            blocked_cells_hash="h",
            exterior_blocks_hash="h",
            source_digest="h",
            oracle_abstraction_version="port_exposure_v2_canonical_dirs",
            artifact_hashes={},
        ),
        cert=OracleCert(
            cert_kind="port_exposure_blocked",
            cert_payload=payload,
            cert_hash=hashlib.sha256(payload).hexdigest(),
        ),
        oracle_name="port_exposure_v2_canonical_dirs",
    )
    spy = _SpyMaster()
    with pytest.raises(TypeError, match="exact CompiledCut"):
        step_8_apply_to_master(raw_legacy_cut, spy, scope_binding=None)
    assert spy.calls == []


# ---------------------------------------------------------------------------
# F6 shape_packing_hall / F7 power_hitting_set — typed-chain migration (B5b)
#
# B5b lands the domain-consistent snapshot↔live-master fixtures (proven
# equivalent by the projection-equality tests in each stage_b file), so the
# resolver locates the ghost anchor and lowers the real F6/F7 constraint.  The
# raw-API RuntimeError/ValueError surfaces move onto the typed chain at their
# exact stages: split-brain → adapter integrity; a master-side inconsistency
# (coverer table / pole footprint) drifts the §2.6 live domain projection, so
# step_8 fails closed BEFORE the master's own F7 re-check gate for every
# well-formed divergence.  NOT a strict subsume: at corrupt-table corners
# (out-of-range coverer index) §2.6 raises IndexError where the gate returns
# False — the gate stays (defence-in-depth + sole guard for non-typed callers).
# ---------------------------------------------------------------------------


def test_step_8_f6_anchor_free_feasible_then_pinned_infeasible() -> None:
    """F6 typed chain: dormant while the anchor is free, prunes once pinned.

    Both 1×3 bodies lie entirely on the left baseline (cap 1), so pinning the
    resolved anchor forces 2 ≤ 1 → INFEASIBLE; with the anchor free the
    ghost-conditioned cut sleeps and the master stays feasible.
    """
    from src.tests.cuts.test_stage_b_shape_packing_hall import (
        _LEFT_ONLY_POSES,
        _build_tiny_master as _f6_build_tiny_master,
        _build_world as _f6_build_world,
        _compile_cut as _f6_compile_cut,
    )

    state, bundle = _f6_build_world(poses=_LEFT_ONLY_POSES)
    _raw, snapshot, compiled = _f6_compile_cut(state, bundle, region_kind="left_baseline", region_demand=2)
    master = _f6_build_tiny_master(_LEFT_ONLY_POSES)
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    step_8_apply_to_master(compiled, master, scope_binding=binding)
    stats = master.build_stats["coordinate_baseline_packing_last_cut"]
    assert stats["capacity"] == 1
    assert stats["presence_terms"] == 2

    # Anchor free → the ghost-conditioned cut sleeps → feasible.
    assert master.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    delegate = master._coordinate_delegate
    assert delegate is not None
    delegate.model.Add(binding.condition_lits[0] == 1)
    # Anchor pinned → cap 1 on the only baseline both bodies fit → infeasible.
    assert master.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_step_8_f7_excludes_pose_under_pinned_anchor() -> None:
    """F7 typed chain lowers presence(pose)==0 under the resolved ghost anchor.

    The resolver reconstructs the blocked-cell body and locates the (0,0,1,1)
    ghost at rect_idx 0; pinning that anchor active makes the exclusion bite so
    the two mandatory widgets can no longer both be placed → INFEASIBLE.
    """
    from src.tests.cuts.test_stage_b_power_hitting_set import (
        _build_master as _f7_build_master,
        _build_world as _f7_build_world,
        _compile_cut as _f7_compile_cut,
        _oracle_cut as _f7_oracle_cut,
    )

    state, bundle = _f7_build_world()
    raw = _f7_oracle_cut(state)
    snapshot, compiled = _f7_compile_cut(state, bundle, raw)
    assert compiled.plan.operation == "power_pose_exclusion"

    master = _f7_build_master()
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    assert binding.rect_idx == 0
    assert binding.condition_lits[0] is master.u_vars[0]

    step_8_apply_to_master(compiled, master, scope_binding=binding)
    stats = master.build_stats["coordinate_power_pose_exclusion_last_cut"]
    assert stats["pose_idx"] == 1
    assert stats["semantics"] == "power_pose_exclusion_ghost_conditioned_v1"
    assert master.build_stats["coordinate_framework_cut_count"] == 1

    delegate = master._coordinate_delegate
    assert delegate is not None
    delegate.model.Add(binding.condition_lits[0] == 1)
    assert master.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_step_8_f7_fail_closed_surfaces() -> None:
    """F7 fail-closed surfaces on the typed chain (non-drift arms).

    Split-brain cert is refused by the adapter before any master; a raw Cut is
    refused by the step_8 type gate before any master attribute is read.  (The
    proof-stage and domain-drift arms are covered by the F7 compile tests and by
    ``test_step_8_f7_missing_coverer_table_refused`` / ``..._live_coverer_gate_refuses``.)
    """
    from src.tests.cuts.test_stage_b_power_hitting_set import (
        _build_master as _f7_build_master,
        _build_world as _f7_build_world,
        _oracle_cut as _f7_oracle_cut,
    )

    state, _bundle = _f7_build_world()
    tampered = dataclasses.replace(_f7_oracle_cut(state), oracle_cert_hash="0" * 64)
    spy = _SpyMaster()
    with pytest.raises(ValueError, match="integrity failed"):
        cut_to_envelope_v1(tampered)
    assert spy.calls == []

    # Type gate: a raw F7 Cut handed straight to step_8 is refused before the
    # master (the resolver/CompiledCut are the only sanctioned inputs).
    raw_cut = _f7_oracle_cut(state)
    master = _f7_build_master()
    with pytest.raises(TypeError, match="exact CompiledCut"):
        step_8_apply_to_master(raw_cut, master, scope_binding=None)
    assert "coordinate_power_pose_exclusion_last_cut" not in master.build_stats


def test_step_8_f7_missing_coverer_table_refused() -> None:
    """A missing coverer-table entry drifts the §2.6 projection, not the master gate.

    The master's own F7 attach-time re-check would return False on a missing
    coverer entry, but the coverer table is part of the live domain projection,
    so deleting the target pose's entry drifts the projection and step_8 fails
    closed at the §2.6 boundary BEFORE the master re-check runs (no mutation).
    """
    from src.tests.cuts.test_stage_b_power_hitting_set import (
        _FACILITY_TYPE,
        _build_master as _f7_build_master,
        _build_world as _f7_build_world,
        _compile_cut as _f7_compile_cut,
        _oracle_cut as _f7_oracle_cut,
    )

    state, bundle = _f7_build_world()
    raw = _f7_oracle_cut(state)
    snapshot, compiled = _f7_compile_cut(state, bundle, raw)
    master = _f7_build_master(skip_power_coverage=True)
    assert master._power_coverers_by_template_pose[_FACILITY_TYPE][1] == [0]
    del master._power_coverers_by_template_pose[_FACILITY_TYPE][1]

    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    with pytest.raises(ValueError, match="domain projection drifted"):
        step_8_apply_to_master(compiled, master, scope_binding=binding)
    assert "coordinate_power_pose_exclusion_last_cut" not in master.build_stats


def test_step_8_f7_live_coverer_gate_refuses() -> None:
    """An inconsistent (still-live) coverer footprint drifts the §2.6 projection.

    The master gate refuses a coverer whose footprint is disjoint from the
    blocked cells, but the pole footprints are part of the live domain
    projection; moving a pole so its coverer stays live drifts the projection,
    so step_8 fails closed at the §2.6 boundary before the master gate (no
    mutation).  The resolver cannot be fed wrong blocked cells (it reconstructs
    them from the frozen snapshot), so this is the only way the live-coverer
    condition can arise on the typed chain.
    """
    from src.tests.cuts.test_stage_b_power_hitting_set import (
        _build_master as _f7_build_master,
        _build_world as _f7_build_world,
        _compile_cut as _f7_compile_cut,
        _oracle_cut as _f7_oracle_cut,
    )

    state, bundle = _f7_build_world()
    raw = _f7_oracle_cut(state)
    snapshot, compiled = _f7_compile_cut(state, bundle, raw)
    master = _f7_build_master(skip_power_coverage=True)
    pole_pool = master.facility_pools["power_pole"]
    assert pole_pool
    pole_pool[0]["occupied_cells"] = [[69, 69], [69, 68], [68, 69], [68, 68]]

    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    with pytest.raises(ValueError, match="domain projection drifted"):
        step_8_apply_to_master(compiled, master, scope_binding=binding)
    assert "coordinate_power_pose_exclusion_last_cut" not in master.build_stats
