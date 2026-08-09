"""Step 8 — F6 shape_packing_hall master lowering via the typed chain (B5b).

B5b migrates these master-lowering cases off the deleted raw
``_legacy_step_8_apply_raw`` translator onto the full typed chain:

    oracle Cut → cut_to_envelope_v1 → build_validated_state_snapshot →
    validate_and_compile_cut → CompiledCut → _resolve_model_scope_binding →
    step_8_apply_to_master(compiled, master, scope_binding=binding)

The domain-consistent snapshot↔live-master fixture is the one proven equivalent
in ``test_stage_b_shape_packing_hall.py`` (``_build_world`` snapshot vs. the
``_build_tiny_master`` live projection — see
``test_f6_snapshot_and_live_master_rows_share_one_domain_projection_schema``), so
the resolver locates the (5,5,1,1) ghost at rect_idx 35 and lowers under its
u_var.  Per the B5a F1 precedent, behavioural pruning is asserted as
master-mutation evidence (build_stats), not solver runs — F6 solver behaviour is
already covered by ``test_real_master_f6_cut_is_dormant_until_its_anchor_is_pinned``.
"""

from __future__ import annotations

import dataclasses

import pytest

from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    _resolve_model_scope_binding,
    step_8_apply_to_master,
)
from src.cuts.state_snapshot import build_validated_state_snapshot
from src.cuts.typed_platform import (
    CompiledCut,
    CutRejection,
    build_production_registry,
    cut_to_envelope_v1,
    validate_and_compile_cut,
)
from src.tests.cuts.test_stage_b_shape_packing_hall import (
    _ALL_POSES,
    _FACILITY_TYPE,
    _build_tiny_master,
    _build_world,
    _compile_cut,
    _oracle_cut,
)


def test_step_8_f6_caps_left_baseline_under_pinned_anchor() -> None:
    """The typed chain lowers a left-baseline cap=1 under the resolved anchor.

    Only the two left-baseline poses are counted by the cap (bottom/interior are
    excluded); the resolver conditions the cut on the master u_var for the plan's
    (5,5,1,1) ghost (rect_idx 35 on the 6×6 master).
    """
    state, bundle = _build_world()
    _raw, snapshot, compiled = _compile_cut(state, bundle, region_kind="left_baseline", region_demand=2)
    assert compiled.plan.operation == "shape_packing_hall_le"

    master = _build_tiny_master(_ALL_POSES)
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    assert binding.rect_idx is not None
    assert binding.condition_lits[0] is master.u_vars[binding.rect_idx]

    step_8_apply_to_master(compiled, master, scope_binding=binding)
    stats = master.build_stats["coordinate_baseline_packing_last_cut"]
    assert stats["region_kind"] == "left_baseline"
    assert stats["capacity"] == 1
    # Only the two left-baseline poses are counted (not bottom, not interior).
    assert stats["presence_terms"] == 2
    assert master.build_stats["coordinate_framework_cut_count"] == 1


def test_step_8_f6_zero_caps_both_baselines_prune() -> None:
    """Both baselines capped at 0 lower as two conditioned constraints.

    ``all_baselines_blocked`` makes the oracle derive total_packable=0 naturally
    (hand-forging total_packable=0 is refused — the validator requires
    total_packable < region_demand); each cap-0 cut lowers under its resolved
    anchor, bumping the framework cut count to two.  Group ``demand`` stays at
    the fixture default (2) so the snapshot domain projection still matches the
    two-instance ``_build_tiny_master``; the cap-0 proof comes from the
    per-region_demand override, not from shrinking the group.
    """
    state, bundle = _build_world(all_baselines_blocked=True)
    _l_raw, snap_left, left = _compile_cut(state, bundle, region_kind="left_baseline", region_demand=1)
    _b_raw, snap_bottom, bottom = _compile_cut(state, bundle, region_kind="bottom_baseline", region_demand=1)
    assert left.plan.parameters["capacity"] == 0
    assert bottom.plan.parameters["capacity"] == 0

    master = _build_tiny_master(_ALL_POSES)
    for snapshot, compiled in ((snap_left, left), (snap_bottom, bottom)):
        binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
        step_8_apply_to_master(compiled, master, scope_binding=binding)

    assert master.build_stats["coordinate_framework_cut_count"] == 2
    # The last-applied (bottom) cut is a cap-0 baseline count constraint.
    assert master.build_stats["coordinate_baseline_packing_last_cut"]["capacity"] == 0


def test_step_8_f6_fail_closed_surfaces() -> None:
    """F6 fail-closed rejections now land at the adapter / compile / step_8 stages.

    Mirrors the F1 three-precedent split: the raw-API RuntimeError/ValueError
    surfaces move onto the typed chain, each rejected at its exact stage —
    split-brain cert at the adapter, agnostic scope at compile, live-master
    domain drift at the step_8 boundary (no master mutation).
    """
    state, bundle = _build_world()

    # (1) Split-brain cert → adapter integrity rejection, before any master.
    tampered = dataclasses.replace(
        _oracle_cut(state, region_kind="left_baseline", region_demand=2),
        oracle_cert_hash="0" * 64,
    )
    with pytest.raises(ValueError, match="integrity failed"):
        cut_to_envelope_v1(tampered)

    # (2) Agnostic scope → F6 is always ghost-bound (validator hard constraint),
    #     so an agnostic scope is refused at the common scope boundary during
    #     compile; it never becomes a CompiledCut and never reaches step_8.
    agnostic_raw = _oracle_cut(state, region_kind="left_baseline", region_demand=2)
    assert agnostic_raw.scope is not None
    agnostic = dataclasses.replace(
        agnostic_raw,
        scope=dataclasses.replace(agnostic_raw.scope, ghost_rect_id=GHOST_AGNOSTIC),
    )
    snapshot = build_validated_state_snapshot(state, bundle)
    agnostic_result = validate_and_compile_cut(cut_to_envelope_v1(agnostic), snapshot, build_production_registry())
    assert isinstance(agnostic_result, CutRejection)
    assert not isinstance(agnostic_result, CompiledCut)

    # (3) Live master-domain drift → the resolver's recomputed live projection
    #     diverges from the plan fingerprint; step_8 fails closed at the master
    #     boundary before any lowering (typed analogue of the master refusing an
    #     inconsistent cut).
    _raw, drift_snapshot, compiled = _compile_cut(state, bundle, region_kind="left_baseline", region_demand=2)
    master = _build_tiny_master(_ALL_POSES)
    master.facility_pools[_FACILITY_TYPE][0]["alpha_projection_drift"] = True
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, drift_snapshot, master)
    with pytest.raises(ValueError, match="domain projection drifted"):
        step_8_apply_to_master(compiled, master, scope_binding=binding)
    assert "coordinate_baseline_packing_last_cut" not in master.build_stats
