"""Phase 1.0 P1.2 test — CutStore + 6-dim watcher index.

Coverage:
- add_cut + watcher registration (cell/group/pose/commodity/region/ghost)
- GHOST_AGNOSTIC cut 不入 by_ghost_watcher
- quarantine_cut + held set state machine
- on_ghost_rect_changed dispatch with injected replay_fn
- watcher lookup helpers
- stats snapshot
"""
from __future__ import annotations

import pytest

from src.cuts.lifecycle import (
    AnonymousSlotRef,
    AttachDecision,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    GHOST_AGNOSTIC,
    GroupState,
    OracleCert,
)
from src.cuts.store import CutStore, QuarantineReason


def _make_state() -> BState:
    return BState(
        groups={
            "g1": GroupState("g1", demand=2, pose_domain=frozenset()),
        },
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"f1_v1"}),
    )


def _make_cut(
    cut_id: str = "cut-1",
    family: str = "region_capacity",
    ghost_id: str = GHOST_AGNOSTIC,
    use_literals: bool = False,
) -> Cut:
    """Construct a minimal valid Cut for store tests."""
    if family in ("region_capacity", "cutset", "component_reach",
                  "shape_packing_hall", "density_envelope"):
        if use_literals:
            raise ValueError("geometric family — literals not allowed")
        kw = {"geometric_payload": b'{"k":1}', "literals": None}
    else:
        kw = {
            "literals": (CutLiteral(AnonymousSlotRef("g1", 0), "p42"),),
            "geometric_payload": None,
        }
    scope = CutScope(
        ghost_rect_id=ghost_id,
        blocked_cells_hash="h_blocked",
        exterior_blocks_hash="h_exterior",
        source_digest="poc_source_digest",
        artifact_hashes={"canonical_rules.json": "h1"},
        oracle_abstraction_version="f1_v1",
        active_assumptions=(),
    )
    cert = OracleCert(cert_kind="test", cert_payload=b"p", cert_hash="ch")
    return Cut(
        cut_id=cut_id,
        family=family,  # type: ignore[arg-type]
        scope=scope,
        cert=cert,
        family_version="v1",
        validator_version="v1",
        **kw,  # type: ignore[arg-type]
    )


# ============================================================================
# add_cut + watcher registration
# ============================================================================

def test_add_cut_registers_all_watcher_dims():
    store = CutStore()
    cut = _make_cut("c1", family="region_capacity", ghost_id="ghost_v1")

    store.add_cut(initial_state="active", cut=
        cut,
        cell_keys=[(0, 0), (0, 1)],
        group_keys=["g1"],
        pose_keys=[("g1", "p42")],
        commodity_keys=["power"],
        region_keys=["region_left_baseline"],
    )

    assert store.cuts["c1"] is cut
    assert "c1" in store.cuts_affected_by_cell((0, 0))
    assert "c1" in store.cuts_affected_by_cell((0, 1))
    assert "c1" in store.cuts_affected_by_group("g1")
    assert "c1" in store.cuts_affected_by_pose("g1", "p42")
    assert "c1" in store.cuts_affected_by_commodity("power")
    assert "c1" in store.cuts_affected_by_region("region_left_baseline")
    assert "c1" in store.cuts_affected_by_ghost("ghost_v1")


def test_add_cut_ghost_agnostic_skips_by_ghost_watcher():
    """v3.2.2 §7: GHOST_AGNOSTIC cut (F1) 不入 by_ghost_watcher."""
    store = CutStore()
    cut = _make_cut("c1", family="region_capacity", ghost_id=GHOST_AGNOSTIC)
    store.add_cut(initial_state="active", cut=cut, cell_keys=[(0, 0)])
    assert (0, 0) in store.by_cell_watcher
    assert GHOST_AGNOSTIC not in store.by_ghost_watcher
    assert not store.cuts_affected_by_ghost(GHOST_AGNOSTIC)


def test_add_cut_duplicate_id_raises():
    store = CutStore()
    cut = _make_cut("dup")
    store.add_cut(initial_state="active", cut=cut)
    with pytest.raises(ValueError, match="已注册"):
        store.add_cut(initial_state="active", cut=cut)


# ============================================================================
# Quarantine / Hold state machine (cut_lifecycle_v2 §8)
# ============================================================================

def test_quarantine_removes_from_watchers():
    store = CutStore()
    cut = _make_cut("c1", ghost_id="ghost_v1")
    store.add_cut(initial_state="active", cut=cut, cell_keys=[(0, 0)], group_keys=["g1"])

    assert store.is_active("c1")

    store.quarantine_cut(
        "c1", QuarantineReason(reason_code="validate_unsound", detail="cap_R mismatch")
    )

    assert not store.is_active("c1")
    assert "c1" in store.quarantined
    assert "c1" not in store.cuts_affected_by_cell((0, 0))
    assert "c1" not in store.cuts_affected_by_group("g1")
    assert "c1" not in store.cuts_affected_by_ghost("ghost_v1")
    # cut 仍保留在 self.cuts (audit trail) per §8
    assert "c1" in store.cuts


def test_hold_keeps_watchers():
    """hold 不从 watcher 移除 — 等 ghost change 再次 trigger replay."""
    store = CutStore()
    cut = _make_cut("c1", ghost_id="ghost_v1")
    store.add_cut(initial_state="active", cut=cut, cell_keys=[(0, 0)])

    store.hold_cut("c1")
    assert "c1" in store.held
    assert not store.is_active("c1")
    # watcher 仍保留
    assert "c1" in store.cuts_affected_by_cell((0, 0))


def test_hold_then_reactivate():
    store = CutStore()
    cut = _make_cut("c1")
    store.add_cut(initial_state="active", cut=cut)
    store.hold_cut("c1")
    assert not store.is_active("c1")
    store.reactivate_cut("c1")
    assert store.is_active("c1")


def test_reactivate_missing_or_quarantined_raises():
    store = CutStore()
    with pytest.raises(KeyError, match="不在 store"):
        store.reactivate_cut("missing")

    cut = _make_cut("c1")
    store.add_cut(initial_state="active", cut=cut)
    store.quarantine_cut("c1", QuarantineReason(reason_code="x"))
    with pytest.raises(ValueError, match="quarantined"):
        store.reactivate_cut("c1")


def test_watcher_lookup_returns_copy_not_internal_set():
    store = CutStore()
    cut = _make_cut("c1")
    store.add_cut(initial_state="active", cut=cut, cell_keys=[(0, 0)])

    affected = store.cuts_affected_by_cell((0, 0))
    affected.clear()

    assert "c1" in store.cuts_affected_by_cell((0, 0))


def test_quarantine_then_hold_raises():
    """quarantine 是 terminal state — 不能再 hold."""
    store = CutStore()
    cut = _make_cut("c1")
    store.add_cut(initial_state="active", cut=cut)
    store.quarantine_cut("c1", QuarantineReason(reason_code="x"))
    with pytest.raises(ValueError, match="quarantined"):
        store.hold_cut("c1")


def test_quarantine_clears_held():
    store = CutStore()
    cut = _make_cut("c1")
    store.add_cut(initial_state="active", cut=cut)
    store.hold_cut("c1")
    store.quarantine_cut("c1", QuarantineReason(reason_code="x"))
    assert "c1" not in store.held


# ============================================================================
# on_ghost_rect_changed dispatch
# ============================================================================

def test_on_ghost_rect_changed_holds_old_ghost_cuts():
    """旧 ghost 关联 cuts → hold (不 quarantine)."""
    store = CutStore()
    cut_old = _make_cut("c_old", ghost_id="ghost_A")
    cut_new = _make_cut("c_new", ghost_id="ghost_B")
    store.add_cut(initial_state="active", cut=cut_old)
    store.add_cut(initial_state="active", cut=cut_new)

    def stub_replay(cut: Cut, state: BState) -> AttachDecision:
        return "ATTACH"

    state = _make_state()
    store.on_ghost_rect_changed("ghost_A", "ghost_B", state, unsafe_test_replay_fn=stub_replay, allow_unsafe_test_replay_fn=True)

    assert "c_old" in store.held
    assert store.is_active("c_new")


def test_on_ghost_rect_changed_new_ghost_quarantine_branch():
    """新 ghost cut replay 返 QUARANTINE → quarantine."""
    store = CutStore()
    cut_new = _make_cut("c_new", ghost_id="ghost_B")
    store.add_cut(initial_state="active", cut=cut_new)

    def stub_replay_quarantine(cut: Cut, state: BState) -> AttachDecision:
        return "QUARANTINE"

    state = _make_state()
    store.on_ghost_rect_changed(GHOST_AGNOSTIC, "ghost_B", state, unsafe_test_replay_fn=stub_replay_quarantine, allow_unsafe_test_replay_fn=True)

    assert "c_new" in store.quarantined
    assert "c_new" not in store.held


def test_on_ghost_rect_changed_new_ghost_hold_branch():
    """新 ghost cut replay 返 HOLD → 保 hold."""
    store = CutStore()
    cut_new = _make_cut("c_new", ghost_id="ghost_B")
    store.add_cut(initial_state="active", cut=cut_new)

    def stub_replay_hold(cut: Cut, state: BState) -> AttachDecision:
        return "HOLD"

    state = _make_state()
    store.on_ghost_rect_changed(GHOST_AGNOSTIC, "ghost_B", state, unsafe_test_replay_fn=stub_replay_hold, allow_unsafe_test_replay_fn=True)

    assert "c_new" in store.held
    assert "c_new" not in store.quarantined


def test_on_ghost_rect_changed_attach_branch_reactivates():
    """已 held 的 cut + new ghost replay ATTACH → 回 active."""
    store = CutStore()
    cut = _make_cut("c1", ghost_id="ghost_B")
    store.add_cut(initial_state="active", cut=cut)
    store.hold_cut("c1")

    def stub_replay(cut: Cut, state: BState) -> AttachDecision:
        return "ATTACH"

    state = _make_state()
    store.on_ghost_rect_changed(GHOST_AGNOSTIC, "ghost_B", state, unsafe_test_replay_fn=stub_replay, allow_unsafe_test_replay_fn=True)

    assert store.is_active("c1")
    assert "c1" not in store.held


def test_on_ghost_rect_changed_skips_already_quarantined():
    """已 quarantined cut 不重 replay (terminal state)."""
    store = CutStore()
    cut = _make_cut("c1", ghost_id="ghost_B")
    store.add_cut(initial_state="active", cut=cut)
    store.quarantine_cut("c1", QuarantineReason(reason_code="prior"))

    called = []

    def tracking_replay(cut: Cut, state: BState) -> AttachDecision:
        called.append(cut.cut_id)
        return "ATTACH"

    state = _make_state()
    store.on_ghost_rect_changed(GHOST_AGNOSTIC, "ghost_B", state, unsafe_test_replay_fn=tracking_replay, allow_unsafe_test_replay_fn=True)

    assert "c1" not in called, "quarantined cut 不该被 replay"


# ============================================================================
# Stats snapshot (ramp report 用)
# ============================================================================

def test_stats_snapshot():
    store = CutStore()
    cut_a = _make_cut("ca", family="region_capacity", ghost_id=GHOST_AGNOSTIC)
    cut_b = _make_cut("cb", family="port_exposure", ghost_id="ghost_v1",
                      use_literals=True)
    store.add_cut(initial_state="active", cut=cut_a, cell_keys=[(0, 0)], region_keys=["r1"])
    store.add_cut(initial_state="active", cut=
        cut_b, cell_keys=[(1, 1)], group_keys=["g1"], pose_keys=[("g1", "p42")]
    )
    store.hold_cut("ca")
    store.quarantine_cut("cb", QuarantineReason(reason_code="x"))

    s = store.stats()
    assert s["total_cuts"] == 2
    assert s["active"] == 0
    assert s["held"] == 1
    assert s["quarantined"] == 1
    assert s["by_cell_keys"] == 1  # cb 已 quarantine → 移; ca held 但 watcher 仍在
    assert s["by_ghost_keys"] == 0  # ca GHOST_AGNOSTIC; cb 已 quarantine 移走
