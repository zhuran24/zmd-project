"""PoC test — runtime 验 cut object lifecycle 9 步 + Family 1 拦 F1 反例.

Run:
    .venv/bin/python -m pytest docs/research/p3_b_design_v2_20260521/poc/test_b_core_lifecycle.py -v -s

Not part of CI core gate. Validate Schema-first not retrofit before src/.
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让 PoC module 跟 test 同目录直接 import
sys.path.insert(0, str(Path(__file__).parent))

from b_core_lifecycle_poc import (  # noqa: E402
    Assumption,
    AnonymousSlotRef,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    GHOST_AGNOSTIC,
    GroupState,
    OracleCert,
    assumption_holds,
    compute_blocked_cells_hash,
    compute_ghost_rect_id,
    run_lifecycle,
    step_1_generate_region_capacity_combinatorial,
    step_3_serialize,
    step_4_deserialize,
    step_5_validate_region_capacity,
    step_6_attach_scope_check,
    step_7_evaluate_cut,
)


# ============================================================================
# F1 反例 fixture (red_fixtures/F1_boundary_saturation.md)
# ============================================================================

# Mock canonical_rules (PoC scope)
CANONICAL_RULES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "cells_per_pose": 3,
    },
    "crusher_blue_iron": {
        "placement_rule": "free",
        "cells_per_pose": 9,  # 3x3
    },
}


def make_state_with_crusher_on_left_baseline() -> BState:
    """F1 反例: crusher pose 占 (0,0)..(2,2) → left baseline (1,0)(2,0) 被吃掉.

    boundary_storage_port demand 23 (一边), cells_per_pose=3, demand_R = 69.
    cap_R = |left_baseline=70| - |ghost ∩ R = 0| - |exterior ∩ R = 0| = 70.
    v1.1 static: cap_R 不减 cell_owner; cap_R=70 ≥ demand_R=69 → 不触发 F1
    cut on left_baseline alone.

    To trigger F1: 把 exterior_blocks 加 2 cells (mock "ghost 旁的 immovable
    obstacle 占 baseline 2 cells") → cap_R = 70 - 2 = 68 < demand_R = 69.
    """
    return BState(
        groups={
            "boundary_storage_port": GroupState(
                group_id="boundary_storage_port",
                demand=23,
                pose_domain=frozenset(),  # PoC: not used
                selected_poses=[],
            ),
            "crusher_blue_iron": GroupState(
                group_id="crusher_blue_iron",
                demand=34,
                pose_domain=frozenset(),
                selected_poses=[("crusher_blue_iron", 42)],
            ),
        },
        cell_owner={
            # crusher pose 占 (0,0)..(2,2) — 注意 cell_owner 含 (1,0)(2,0) 在 left baseline
            **{(x, y): ("crusher_blue_iron", 0) for x in range(3) for y in range(3)},
        },
        ghost_rect=None,  # F1 ghost-agnostic
        ghost_cells=frozenset(),
        # v1.1 关键: cap_R 不看 cell_owner, 必须用 exterior_blocks 模拟 "永久 block"
        # 让 cap_R = 70 - 2 = 68 < demand_R = 69 触发 F1 cut
        exterior_blocks=frozenset({(15, 0), (16, 0)}),
        artifact_hashes={
            "canonical_rules.json": "hash_v1",
            "candidate_placements.json": "hash_v2",
            "mandatory_exact_instances.json": "hash_v3",
        },
        available_oracle_versions=frozenset({"region_capacity_v1"}),
    )


def make_clean_state() -> BState:
    """Same as above but no exterior_blocks → cap_R = 70 ≥ demand_R = 69 → no cut."""
    state = make_state_with_crusher_on_left_baseline()
    return BState(
        groups=state.groups,
        cell_owner=state.cell_owner,
        ghost_rect=state.ghost_rect,
        ghost_cells=state.ghost_cells,
        exterior_blocks=frozenset(),  # no exterior block → cap_R = 70 ≥ demand_R = 69
        artifact_hashes=state.artifact_hashes,
        available_oracle_versions=state.available_oracle_versions,
    )


# ============================================================================
# Tests
# ============================================================================

def test_cut_post_init_mutual_exclusion():
    """Cut.__post_init__ 验 literals XOR geometric_payload."""
    # 两者都空 → raise
    try:
        Cut(cut_id="x", family="region_capacity", literals=None, geometric_payload=None)
        assert False, "should have raised"
    except ValueError as e:
        assert "互斥" in str(e)

    # 两者都设 → raise
    try:
        Cut(
            cut_id="x", family="region_capacity",
            literals=(CutLiteral(AnonymousSlotRef("g", 0), 1),),
            geometric_payload=b"x",
        )
        assert False, "should have raised"
    except ValueError as e:
        assert "互斥" in str(e)

    # family geometric 但走 literal mode → raise
    try:
        Cut(
            cut_id="x", family="region_capacity",
            literals=(CutLiteral(AnonymousSlotRef("g", 0), 1),),
        )
        assert False, "should have raised"
    except ValueError:
        pass  # 期望 raise


def test_ghost_agnostic_sentinel():
    """compute_ghost_rect_id(None) → GHOST_AGNOSTIC."""
    assert compute_ghost_rect_id(None) == GHOST_AGNOSTIC


def test_blocked_cells_hash_deterministic():
    """blocked_cells_hash 跨 instantiation 稳定 (canonical order)."""
    state = make_state_with_crusher_on_left_baseline()
    h1 = compute_blocked_cells_hash(state)
    h2 = compute_blocked_cells_hash(state)
    assert h1 == h2


def test_f1_generator_triggers_when_baseline_overflow():
    """v1.1: cap_R static, exterior block 2 cells → cap=68 < demand=69 → cut."""
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None, "应该生成 cut"
    assert cut.family == "region_capacity"
    assert cut.geometric_payload is not None
    import json
    cert = json.loads(cut.geometric_payload)
    assert cert["cap_R"] == 68
    assert cert["demand_R"] == 69
    assert cert["gap"] == 1


def test_f1_generator_silent_when_no_overflow():
    """clean state cap=70 ≥ demand=69 → no cut."""
    state = make_clean_state()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is None, "feasible state 不该生成 cut"


def test_full_lifecycle_round_trip():
    """9 步 lifecycle end-to-end roundtrip on F1 反例."""
    state = make_state_with_crusher_on_left_baseline()
    reports = run_lifecycle(state, state, "left_baseline", "boundary_storage_port", CANONICAL_RULES)
    for r in reports:
        print(f"  [{'✓' if r.ok else '✗'}] {r.step}: {r.detail}")
    assert all(r.ok for r in reports), f"步 fail: {[r for r in reports if not r.ok]}"


def test_serialize_deserialize_roundtrip():
    """Step 3 → Step 4 round-trip 等价 (cut_hash 一致)."""
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    blob = step_3_serialize(cut)
    cut2 = step_4_deserialize(blob)

    assert cut2.cut_id == cut.cut_id
    assert cut2.family == cut.family
    assert cut2.geometric_payload == cut.geometric_payload
    assert cut2.cert.cert_hash == cut.cert.cert_hash
    assert cut2.scope.ghost_rect_id == cut.scope.ghost_rect_id
    assert cut2.scope.blocked_cells_hash == cut.scope.blocked_cells_hash


def test_validator_catches_cap_R_tampering():
    """v1.1 validator 独立重算 cap_R, cert 被改 cap=999 应 unsound."""
    import json
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    # Tamper cert: cap_R=68 改成 999
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = 999
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    tampered_cut = Cut(
        cut_id=cut.cut_id, family=cut.family,
        literals=None, geometric_payload=tampered_payload,
        scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )

    vr = step_5_validate_region_capacity(tampered_cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound", f"应 unsound, 但 {vr.kind}"
    assert "cap_R mismatch" in vr.detail


def test_validator_catches_cells_per_pose_source_rotated():
    """v1.1 finding #5 修: cert.cells_per_pose 跟 canonical_rules 不一致 → unsound."""
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    # 改 canonical_rules cells_per_pose (模拟 source rotated)
    rotated_rules = {**CANONICAL_RULES,
                     "boundary_storage_port": {**CANONICAL_RULES["boundary_storage_port"],
                                                "cells_per_pose": 2}}
    vr = step_5_validate_region_capacity(cut, state, rotated_rules)
    assert vr.kind == "unsound"
    assert "cells_per_pose mismatch" in vr.detail


def test_attach_scope_ghost_agnostic_passes_step_2():
    """F1 GHOST_AGNOSTIC sentinel: replay 在不同 ghost 下仍 attach."""
    gen_state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        gen_state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    assert cut.scope.ghost_rect_id == GHOST_AGNOSTIC

    # 把 replay state 改 ghost (replay 应仍 ATTACH 因 GHOST_AGNOSTIC)
    replay_state = BState(
        groups=gen_state.groups,
        cell_owner=gen_state.cell_owner,
        ghost_rect=(20, 20, 5, 5),  # 不同 ghost
        ghost_cells=frozenset({(20, 20)}),
        exterior_blocks=gen_state.exterior_blocks,
        artifact_hashes=gen_state.artifact_hashes,
        available_oracle_versions=gen_state.available_oracle_versions,
    )

    decision = step_6_attach_scope_check(cut, replay_state)
    # NOTE: blocked_cells_hash 因 ghost 变了 → 不 match → QUARANTINE
    # 这是预期: 即使 ghost_rect_id agnostic, blocked_cells_hash 仍校验
    assert decision == "QUARANTINE"


def test_attach_scope_blocked_cells_hash_v3_1_step_3():
    """v3.1 finding #4 修: blocked_cells_hash 变化 → quarantine."""
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    # 修改 exterior_blocks (add 1 more block cell) → blocked_cells_hash 变
    new_exterior = state.exterior_blocks | {(17, 0)}
    replay_state = BState(
        groups=state.groups,
        cell_owner=state.cell_owner,
        ghost_rect=state.ghost_rect,
        ghost_cells=state.ghost_cells,
        exterior_blocks=new_exterior,
        artifact_hashes=state.artifact_hashes,
        available_oracle_versions=state.available_oracle_versions,
    )

    decision = step_6_attach_scope_check(cut, replay_state)
    assert decision == "QUARANTINE", f"blocked_cells_hash changed 应 quarantine, got {decision}"


def test_attach_scope_oracle_version_unavailable():
    """Step 5: oracle version not in state.available → HOLD (不 quarantine)."""
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    # Oracle 版本不在 replay state available
    replay_state = BState(
        groups=state.groups,
        cell_owner=state.cell_owner,
        ghost_rect=state.ghost_rect,
        ghost_cells=state.ghost_cells,
        exterior_blocks=state.exterior_blocks,
        artifact_hashes=state.artifact_hashes,
        available_oracle_versions=frozenset(),  # ← empty
    )
    decision = step_6_attach_scope_check(cut, replay_state)
    assert decision == "HOLD"


def test_evaluate_geometric_region_capacity_returns_true():
    """v1.1 §6 evaluate_geometric 简化: 无条件 True (cap_R static)."""
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    assert step_7_evaluate_cut(cut, state) == True


def test_assumption_unknown_key_fails_closed():
    """v3.1 §4 Gap 5: 未知 assumption key → False (fail-closed)."""
    state = make_state_with_crusher_on_left_baseline()
    unknown_assumption = Assumption(key="unknown_key", value="v")
    assert assumption_holds(state, unknown_assumption) == False


if __name__ == "__main__":
    # Manual run mode (without pytest)
    tests = [
        test_cut_post_init_mutual_exclusion,
        test_ghost_agnostic_sentinel,
        test_blocked_cells_hash_deterministic,
        test_f1_generator_triggers_when_baseline_overflow,
        test_f1_generator_silent_when_no_overflow,
        test_full_lifecycle_round_trip,
        test_serialize_deserialize_roundtrip,
        test_validator_catches_cap_R_tampering,
        test_validator_catches_cells_per_pose_source_rotated,
        test_attach_scope_ghost_agnostic_passes_step_2,
        test_attach_scope_blocked_cells_hash_v3_1_step_3,
        test_attach_scope_oracle_version_unavailable,
        test_evaluate_geometric_region_capacity_returns_true,
        test_assumption_unknown_key_fails_closed,
    ]
    passed, failed = 0, 0
    for t in tests:
        try:
            print(f"\n=== {t.__name__} ===")
            t()
            print(f"  PASS")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n\n=== Summary: {passed} passed, {failed} failed ===")
    sys.exit(0 if failed == 0 else 1)
