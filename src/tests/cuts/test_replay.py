"""Phase 1.0 P1.3 test — store-aware replay_cut + regression_sweep.

Coverage:
- replay_cut ATTACH path → reactivate (held → active)
- replay_cut HOLD path → store.hold_cut
- replay_cut QUARANTINE path → store.quarantine_cut + audit detail
- replay_cut on cut not in store → KeyError
- replay_cut post-attach validation: ok / unsound / timeout / schema_err
  branch with canonical_rules wired
- regression_sweep counts skipped_quarantined / ATTACH / HOLD / QUARANTINE
"""
from __future__ import annotations

import json

import pytest

from src.cuts.lifecycle import (
    BState,
    Cut,
    GroupState,
)
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
from src.cuts.replay import regression_sweep, replay_cut
from src.cuts.store import CutStore, QuarantineReason


CANONICAL_RULES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "cells_per_pose": 3,
    },
}
_FACILITY_TEMPLATES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "dimensions": {"w": 1, "h": 3},
    },
}
_INSTANCE_TO_FT = {"boundary_storage_port": "boundary_storage_port"}


def _mock_poses_in_union(n: int = 46):
    """生成 n mock pose, occupied 全在 union (left ∪ bottom). Step E P(g)⊆R 要."""
    poses = []
    for i in range(n):
        poses.append({
            "pose_id": f"mock_p_{i}",
            "anchor": {"x": 0, "y": i},
            "occupied_cells": [[0, i % 68], [0, (i + 1) % 68], [0, (i + 2) % 68]],
            "input_port_cells": [],
            "output_port_cells": [],
        })
    return poses


def _make_state(extra_block: bool = False) -> BState:
    extra = {(17, 0)} if extra_block else set()
    poses = _mock_poses_in_union(n=46)
    pose_domain = frozenset(p["pose_id"] for p in poses)
    return BState(
        groups={
            # 真 demand 46 (mandatory_exact_instances boundary_io count, Gap 7 fix);
            # PoC fixture 旧 23 是 half mock 已淘汰
            "boundary_storage_port": GroupState(
                "boundary_storage_port", demand=46, pose_domain=pose_domain,
            ),
        },
        ghost_rect=None,
        ghost_cells=frozenset(),
        exterior_blocks=frozenset({(15, 0), (16, 0)}) | extra,
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"region_capacity_v1"}),
        canonical_rules=CANONICAL_RULES,
        facility_templates=_FACILITY_TEMPLATES,
        instance_to_facility_type=_INSTANCE_TO_FT,
        candidate_placements={
            "facility_pools": {"boundary_storage_port": poses},
        },
    )


def test_add_cut_default_held_no_silent_attach():
    """GPT pro v5 P0-2 反例: 原 add_cut 直接 active 注册让 unsound cut 在 replay
    前能 is_active=True (silent attach window). Step N 修后 default held —
    add_cut 后必经 replay/reactivate gate 才 active.
    """
    s = _make_state()
    cuts = generate_region_capacity_cuts(s, CANONICAL_RULES)
    assert cuts
    cut = cuts[0]
    from src.cuts.store import CutStore
    store = CutStore()
    store.add_cut(cut)
    # 关键 assertion: add_cut 后 default held, 不 active
    assert not store.is_active(cut.cut_id), (
        "add_cut default 必 held — Step N P0-2 fix 防 silent attach"
    )
    assert cut.cut_id in store.held
    # legacy bypass: initial_state="active" 仍允 (test fixture)
    store2 = CutStore()
    store2.add_cut(cut, initial_state="active")
    assert store2.is_active(cut.cut_id)


def test_replay_canonical_rules_none_falls_back_to_state_then_hold():
    """GPT pro v4 P0 fix: replay_cut(canonical_rules=None) 原 silent ATTACH 绕过
    validator (任何 Step A-L 修都 bypass). 修后:
    - state.canonical_rules 已 inject → fallback 用它跑 validator
    - state.canonical_rules 也 None → HOLD (不 active, 等下次 caller 传 rules)
    """
    s = _make_state()  # 有 canonical_rules + facility_templates
    cuts = generate_region_capacity_cuts(s, CANONICAL_RULES)
    assert cuts
    cut = cuts[0]
    from src.cuts.store import CutStore
    store = CutStore()
    store.add_cut(cut)
    store.held.add(cut.cut_id)  # 模拟 held → 进入 replay ATTACH branch
    # Case A: caller 传 None, state.canonical_rules 非 None → fallback validator OK
    decision = replay_cut(cut, s, store, canonical_rules=None)
    assert decision == "ATTACH", f"state fallback 期望 ATTACH 得 {decision}"

    # Case B: caller 传 None + state.canonical_rules=None → HOLD (fail-closed)
    s_no_rules = BState(
        groups=s.groups, cell_owner=s.cell_owner, ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells, exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=None,  # 关键: 无 source
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
        candidate_placements=s.candidate_placements,
    )
    store2 = CutStore()
    store2.add_cut(cut)
    store2.held.add(cut.cut_id)
    decision = replay_cut(cut, s_no_rules, store2, canonical_rules=None)
    assert decision == "HOLD", f"无 source 期望 HOLD (fail-closed) 得 {decision}"
    assert cut.cut_id in store2.held
    assert cut.cut_id not in store2.quarantined


def _make_f1_cut(state: BState) -> Cut:
    """Use production oracle (Gap 6+7+8 fixed). Returns first cut emitted."""
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert cuts, "expected ≥ 1 cut from F1 oracle on this state"
    return cuts[0]


# ============================================================================
# replay_cut ATTACH path
# ============================================================================

def test_replay_attach_path_with_validator_ok():
    """ATTACH + canonical_rules + validator OK → reactivate from held."""
    state = _make_state()
    cut = _make_f1_cut(state)
    store = CutStore()
    store.add_cut(cut)
    store.hold_cut(cut.cut_id)  # 先入 held, replay 应 reactivate

    decision = replay_cut(cut, state, store, canonical_rules=CANONICAL_RULES)

    assert decision == "ATTACH"
    assert store.is_active(cut.cut_id)


def test_replay_attach_path_without_validator_phase1_0_framework():
    """Phase 1.0: canonical_rules=None → 跳过 post-attach validation, ATTACH."""
    state = _make_state()
    cut = _make_f1_cut(state)
    store = CutStore()
    store.add_cut(cut)
    store.hold_cut(cut.cut_id)

    decision = replay_cut(cut, state, store, canonical_rules=None)

    assert decision == "ATTACH"
    assert store.is_active(cut.cut_id)


# ============================================================================
# replay_cut QUARANTINE path
# ============================================================================

def test_replay_quarantine_when_exterior_blocks_hash_changed():
    """v3.2.2: GHOST_AGNOSTIC cut + exterior 变 → QUARANTINE."""
    gen_state = _make_state(extra_block=False)
    cut = _make_f1_cut(gen_state)
    store = CutStore()
    store.add_cut(cut)

    # replay state: exterior changed
    replay_state = _make_state(extra_block=True)
    decision = replay_cut(cut, replay_state, store, canonical_rules=CANONICAL_RULES)

    assert decision == "QUARANTINE"
    assert cut.cut_id in store.quarantined
    assert "exterior_blocks_hash" in store.quarantined[cut.cut_id].detail


def test_replay_quarantine_when_post_attach_validation_unsound():
    """ATTACH 通过 6 步 但 validator 验 cert tampered → QUARANTINE."""
    state = _make_state()
    cut = _make_f1_cut(state)
    # Tamper cert: cap_R=68 改 999
    assert cut.geometric_payload is not None
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = 999
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    assert cut.scope is not None and cut.cert is not None
    tampered_cut = Cut(
        cut_id=cut.cut_id,
        family=cut.family,
        literals=None,
        geometric_payload=tampered_payload,
        scope=cut.scope,
        cert=cut.cert,
        family_version=cut.family_version,
        validator_version=cut.validator_version,
    )
    store = CutStore()
    store.add_cut(tampered_cut)

    decision = replay_cut(tampered_cut, state, store, canonical_rules=CANONICAL_RULES)

    assert decision == "QUARANTINE"
    reason = store.quarantined[tampered_cut.cut_id]
    assert reason.reason_code == "post_attach_validation_unsound"
    assert "cap_R mismatch" in reason.detail


# ============================================================================
# replay_cut HOLD path
# ============================================================================

def test_replay_hold_when_oracle_version_unavailable():
    state = _make_state()
    cut = _make_f1_cut(state)
    store = CutStore()
    store.add_cut(cut)

    # state 没 oracle version
    state_no_oracle = BState(
        groups=state.groups,
        ghost_rect=state.ghost_rect,
        ghost_cells=state.ghost_cells,
        exterior_blocks=state.exterior_blocks,
        artifact_hashes=state.artifact_hashes,
        available_oracle_versions=frozenset(),
        canonical_rules=state.canonical_rules,
        facility_templates=state.facility_templates,
        instance_to_facility_type=state.instance_to_facility_type,
    )
    decision = replay_cut(cut, state_no_oracle, store, canonical_rules=CANONICAL_RULES)

    assert decision == "HOLD"
    assert cut.cut_id in store.held
    assert cut.cut_id not in store.quarantined


# ============================================================================
# Brand new cut precondition
# ============================================================================

def test_replay_cut_not_in_store_raises():
    state = _make_state()
    cut = _make_f1_cut(state)
    store = CutStore()
    # 没 add_cut

    with pytest.raises(KeyError, match="不在 store"):
        replay_cut(cut, state, store, canonical_rules=CANONICAL_RULES)


# ============================================================================
# regression_sweep
# ============================================================================

def test_regression_sweep_skips_quarantined():
    state = _make_state()
    cut_a = _make_f1_cut(state)
    cut_b = _make_f1_cut(state)
    # cut_id 重名 (F1 generator 用 time*1000 milisec 可能撞)
    cut_b_id = f"{cut_a.cut_id}-b"
    # Construct cut_b copy with different id
    assert cut_a.scope is not None and cut_a.cert is not None
    cut_b = Cut(
        cut_id=cut_b_id,
        family=cut_a.family,
        literals=None,
        geometric_payload=cut_a.geometric_payload,
        scope=cut_a.scope,
        cert=cut_a.cert,
        family_version=cut_a.family_version,
        validator_version=cut_a.validator_version,
    )
    store = CutStore()
    store.add_cut(cut_a)
    store.add_cut(cut_b)
    store.quarantine_cut(cut_a.cut_id, QuarantineReason(reason_code="prior"))

    counts = regression_sweep(store, state, canonical_rules=CANONICAL_RULES)

    assert counts["skipped_quarantined"] == 1
    assert counts["ATTACH"] == 1
    assert counts["QUARANTINE"] == 0
    assert counts["HOLD"] == 0


def test_regression_sweep_attach_all():
    state = _make_state()
    cut = _make_f1_cut(state)
    store = CutStore()
    store.add_cut(cut)

    counts = regression_sweep(store, state, canonical_rules=CANONICAL_RULES)

    assert counts["ATTACH"] == 1
    assert counts["skipped_quarantined"] == 0
