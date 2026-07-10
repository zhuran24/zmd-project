"""Phase 1.0 P1.1 test — cut object lifecycle 9-step framework.

Migrated from docs/research/p3_b_design_v2_20260521/poc/test_b_core_lifecycle.py.
Phase 1 production adjustments vs PoC:

1. 9 family map (no symmetry_lift).
2. v3.2.2 dispatch: GHOST_AGNOSTIC cut verifies ``exterior_blocks_hash`` only;
   ghost-bound cut verifies full ``blocked_cells_hash``. Old PoC test
   ``test_attach_scope_ghost_agnostic_passes_step_2`` (expected QUARANTINE on
   ghost change) is **replaced** by two tests covering the dispatch branches:
   - GHOST_AGNOSTIC + exterior unchanged → ATTACH (新 cut 跨 ghost 复用语义)
   - GHOST_AGNOSTIC + exterior changed → QUARANTINE

Run:
    .venv/bin/python -m pytest src/tests/cuts/test_lifecycle.py -v -s
"""
from __future__ import annotations

import base64
import json
from dataclasses import replace

import pytest

from src.cuts.lifecycle import (
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
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    compute_source_digest,
    run_lifecycle,
    step_1_generate_region_capacity_combinatorial,
    step_3_serialize,
    step_4_deserialize,
    step_5_validate_region_capacity,
    step_6_attach_scope_check,
    step_7_evaluate_cut,
    _decode_region_bitset,
)


# ============================================================================
# F1 反例 fixture (red_fixtures/F1_boundary_saturation.md)
# ============================================================================

# Legacy PoC fixture (for step_1_generate_region_capacity_combinatorial which
# is the P1.0 framework reference — passes group→cells_per_pose dict directly).
# Production callers use state.facility_templates + state.instance_to_facility_type
# instead (Gap 8 修 path).
CANONICAL_RULES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "cells_per_pose": 3,
    },
    "crusher_blue_iron": {
        "placement_rule": "free",
        "cells_per_pose": 9,
    },
}

# NEW schema (Gap 8 修 path): facility_templates 对应 真 canonical_rules.json,
# instance_to_facility_type 对应 mandatory_exact_instances aggregate.
# PoC test 用 "boundary_storage_port" / "crusher_blue_iron" 作 group_id (legacy
# 沿用 PoC fixture 命名), 但 instance_to_facility_type 映射对了 schema.
FACILITY_TEMPLATES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "dimensions": {"w": 1, "h": 3},
    },
    "manufacturing_3x3": {
        "dimensions": {"w": 3, "h": 3},
    },
}
INSTANCE_TO_FACILITY_TYPE = {
    "boundary_storage_port": "boundary_storage_port",  # PoC legacy: gid = ft 名 重叠
    "crusher_blue_iron": "manufacturing_3x3",
}


def make_state_with_crusher_on_left_baseline() -> BState:
    """F1 反例: cap_R = 70 - 2 (exterior) = 68 < demand_R = 23 * 3 = 69 → 触发 cut."""
    return BState(
        groups={
            "boundary_storage_port": GroupState(
                group_id="boundary_storage_port",
                demand=23,
                pose_domain=frozenset(),
                selected_poses=[],
            ),
            "crusher_blue_iron": GroupState(
                group_id="crusher_blue_iron",
                demand=34,
                pose_domain=frozenset(),
                selected_poses=["p42"],  # Gap 12: List[PoseId] str
            ),
        },
        cell_owner={
            **{(x, y): ("crusher_blue_iron", 0) for x in range(3) for y in range(3)},
        },
        ghost_rect=None,
        ghost_cells=frozenset(),
        exterior_blocks=frozenset({(15, 0), (16, 0)}),
        artifact_hashes={
            "canonical_rules.json": "hash_v1",
            "candidate_placements.json": "hash_v2",
            "mandatory_exact_instances.json": "hash_v3",
        },
        available_oracle_versions=frozenset({"region_capacity_v1"}),
        canonical_rules=CANONICAL_RULES,  # PoC framework reference 用
        facility_templates=FACILITY_TEMPLATES,  # Gap 8: production helper 用
        instance_to_facility_type=INSTANCE_TO_FACILITY_TYPE,
    )


def make_clean_state() -> BState:
    """No exterior_blocks → cap_R = 70 ≥ demand_R = 69 → 不触发 cut."""
    s = make_state_with_crusher_on_left_baseline()
    return BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=frozenset(),
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
    )


# ============================================================================
# Tests
# ============================================================================

def test_cut_post_init_mutual_exclusion():
    """literals XOR geometric_payload + 9 family map enforcement."""
    try:
        Cut(cut_id="x", family="region_capacity", literals=None, geometric_payload=None)
        assert False, "should have raised"
    except ValueError as e:
        assert "互斥" in str(e)

    try:
        Cut(
            cut_id="x", family="region_capacity",
            literals=(CutLiteral(AnonymousSlotRef("g", 0), 1),),
            geometric_payload=b"x",
        )
        assert False, "should have raised"
    except ValueError as e:
        assert "互斥" in str(e)

    # geometric family with literal mode → raise
    try:
        Cut(
            cut_id="x", family="region_capacity",
            literals=(CutLiteral(AnonymousSlotRef("g", 0), 1),),
        )
        assert False, "should have raised"
    except ValueError:
        pass


def test_cut_post_init_unknown_family_rejected():
    """9-family map enforce: 未知 family → raise."""
    try:
        Cut(cut_id="x", family="symmetry_lift", geometric_payload=b"x")  # 旧 PoC family
        assert False, "should have raised — symmetry_lift 不在 9 family"
    except ValueError as e:
        assert "9-family" in str(e) or "family" in str(e)


def test_ghost_agnostic_sentinel():
    assert compute_ghost_rect_id(None) == GHOST_AGNOSTIC


def test_blocked_cells_hash_deterministic():
    s = make_state_with_crusher_on_left_baseline()
    assert compute_blocked_cells_hash(s) == compute_blocked_cells_hash(s)


def test_exterior_blocks_hash_distinct_from_blocked_cells():
    """v3.2.2: 当 ghost 非空, exterior_blocks_hash ≠ blocked_cells_hash."""
    s = make_state_with_crusher_on_left_baseline()
    # add a ghost cell
    s_with_ghost = BState(
        groups=s.groups, cell_owner=s.cell_owner,
        ghost_rect=(20, 20, 3, 3),
        ghost_cells=frozenset({(20, 20), (20, 21), (20, 22)}),
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
    )
    assert compute_exterior_blocks_hash(s_with_ghost) != compute_blocked_cells_hash(s_with_ghost)


def test_f1_generator_triggers_when_baseline_overflow():
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    assert cut.family == "region_capacity"
    assert cut.geometric_payload is not None
    cert = json.loads(cut.geometric_payload)
    assert cert["cap_R"] == 68
    assert cert["demand_R"] == 69
    assert cert["gap"] == 1


def test_f1_generator_silent_when_no_overflow():
    s = make_clean_state()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is None


def test_full_lifecycle_round_trip():
    s = make_state_with_crusher_on_left_baseline()
    reports = run_lifecycle(s, s, "left_baseline", "boundary_storage_port", CANONICAL_RULES)
    for r in reports:
        print(f"  [{'OK' if r.ok else 'FAIL'}] {r.step}: {r.detail}")
    assert all(r.ok for r in reports), f"步 fail: {[r for r in reports if not r.ok]}"


def test_serialize_deserialize_roundtrip():
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
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
    assert cut2.scope.exterior_blocks_hash == cut.scope.exterior_blocks_hash  # v3.2.2


def test_validator_catches_cap_R_tampering():
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = 999
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    tampered_cut = Cut(
        cut_id=cut.cut_id, family=cut.family,
        literals=None, geometric_payload=tampered_payload,
        scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )

    vr = step_5_validate_region_capacity(tampered_cut, s, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "cap_R mismatch" in vr.detail


def test_validator_catches_cells_per_pose_source_rotated():
    """Gemini round 14 finding #5 — cert.cells_per_pose 跟 source 不一致 → unsound."""
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    rotated_rules = {
        **CANONICAL_RULES,
        "boundary_storage_port": {
            **CANONICAL_RULES["boundary_storage_port"],
            "cells_per_pose": 2,
        },
    }
    vr = step_5_validate_region_capacity(cut, s, rotated_rules)
    assert vr.kind == "unsound"
    assert "cells_per_pose mismatch" in vr.detail


def test_attach_scope_ghost_agnostic_passes_when_exterior_unchanged():
    """v3.2.2 dispatch: GHOST_AGNOSTIC cut + ghost 变了但 exterior 没变 → ATTACH.

    PoC test 旧期望 QUARANTINE (v3.1 仍校验 blocked_cells_hash);
    v3.2.2 修: GHOST_AGNOSTIC 路径只校验 exterior_blocks_hash → cut 跨 ghost 复用.
    """
    gen_state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        gen_state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    assert cut.scope.ghost_rect_id == GHOST_AGNOSTIC

    # ghost 变, exterior_blocks 不变
    replay_state = BState(
        groups=gen_state.groups,
        cell_owner=gen_state.cell_owner,
        ghost_rect=(20, 20, 5, 5),
        ghost_cells=frozenset({(20, 20), (20, 21)}),
        exterior_blocks=gen_state.exterior_blocks,  # 不变
        artifact_hashes=gen_state.artifact_hashes,
        available_oracle_versions=gen_state.available_oracle_versions,
        canonical_rules=gen_state.canonical_rules,
        facility_templates=gen_state.facility_templates,
        instance_to_facility_type=gen_state.instance_to_facility_type,
    )
    decision = step_6_attach_scope_check(cut, replay_state)
    assert decision == "ATTACH", \
        f"v3.2.2 GHOST_AGNOSTIC + exterior unchanged 应 ATTACH, got {decision}"


def test_attach_scope_ghost_agnostic_quarantine_when_exterior_changed():
    """v3.2.2 dispatch: GHOST_AGNOSTIC cut + exterior 变 → QUARANTINE."""
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    new_exterior = s.exterior_blocks | {(17, 0)}
    replay_state = BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=new_exterior,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
    )
    decision = step_6_attach_scope_check(cut, replay_state)
    assert decision == "QUARANTINE"


def test_attach_scope_quarantines_cut_with_omitted_artifact_dependency():
    """A cut cannot opt out of a dependency by deleting its artifact key."""
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    assert cut.scope is not None

    incomplete_artifacts = dict(cut.scope.artifact_hashes)
    incomplete_artifacts.pop("canonical_rules.json")
    incomplete_cut = replace(
        cut,
        scope=replace(cut.scope, artifact_hashes=incomplete_artifacts),
    )

    assert step_6_attach_scope_check(incomplete_cut, state) == "QUARANTINE"


def test_attach_scope_quarantines_cut_with_unknown_artifact_dependency():
    """A cut cannot add a dependency absent from the authoritative state."""
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    assert cut.scope is not None

    extra_artifacts = {
        **cut.scope.artifact_hashes,
        "nonexistent-artifact.json": "untrusted-hash",
    }
    overreported_cut = replace(
        cut,
        scope=replace(cut.scope, artifact_hashes=extra_artifacts),
    )

    assert step_6_attach_scope_check(overreported_cut, state) == "QUARANTINE"


def test_attach_scope_accepts_complete_matching_artifact_snapshot():
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    assert cut.scope is not None
    assert cut.scope.artifact_hashes == state.artifact_hashes

    assert step_6_attach_scope_check(cut, state) == "ATTACH"


def test_attach_scope_ghost_bound_hold_when_ghost_changed():
    """v3.2.2 dispatch: ghost-bound cut + ghost 变 → HOLD (step 2 fail)."""
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    # 手工 construct ghost-bound cut (将 ghost_rect_id 改成具体值)
    ghost_bound_scope = CutScope(
        ghost_rect_id="ghost_specific_v1",
        blocked_cells_hash=cut.scope.blocked_cells_hash,
        exterior_blocks_hash=cut.scope.exterior_blocks_hash,
        source_digest=cut.scope.source_digest,
        artifact_hashes=cut.scope.artifact_hashes,
        oracle_abstraction_version=cut.scope.oracle_abstraction_version,
        active_assumptions=cut.scope.active_assumptions,
    )
    ghost_bound_cut = Cut(
        cut_id=cut.cut_id, family=cut.family,
        literals=None, geometric_payload=cut.geometric_payload,
        scope=ghost_bound_scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )

    replay_state_diff_ghost = BState(
        groups=s.groups, cell_owner=s.cell_owner,
        ghost_rect=(10, 10, 3, 3),
        ghost_cells=frozenset({(10, 10)}),
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
    )
    decision = step_6_attach_scope_check(ghost_bound_cut, replay_state_diff_ghost)
    assert decision == "HOLD"


def test_attach_scope_oracle_version_unavailable():
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    replay_state = BState(
        groups=s.groups, cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect, ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=frozenset(),
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
    )
    decision = step_6_attach_scope_check(cut, replay_state)
    assert decision == "HOLD"


def test_step_7_fails_closed_when_oracle_version_unavailable_before_replay_hold():
    """V31-family regression: Step 7 must mirror Step 6 HOLD on oracle version."""
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    replay_state = BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=frozenset(),
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
        candidate_placements=s.candidate_placements,
    )
    assert step_6_attach_scope_check(cut, replay_state) == "HOLD"
    assert step_7_evaluate_cut(cut, replay_state) is False


def test_step_7_fails_closed_when_active_assumption_no_longer_holds_before_replay_hold():
    """V31-family regression: assumption-expired cuts must not fire in Step 7."""
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    assert cut.scope is not None

    assumption_bound_cut = replace(
        cut,
        scope=replace(
            cut.scope,
            active_assumptions=(Assumption(key="unknown_key", value="v"),),
        ),
    )
    assert step_6_attach_scope_check(assumption_bound_cut, s) == "HOLD"
    assert step_7_evaluate_cut(assumption_bound_cut, s) is False


def test_evaluate_geometric_region_capacity_returns_true():
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    assert step_7_evaluate_cut(cut, s) is True


def test_step_7_dispatches_to_family_evaluator_for_stale_f1():
    """GPT pro v2 P0-1 regression: step_7_evaluate_cut 必 dispatch family evaluator,
    不准 region_capacity 硬编码 return True. 反例: F1 cut 在 oracle 时 demand > cap
    (True), state 变化让 cap >= demand 后 step_7 必返 False (跟 family evaluator 一致).
    """
    from src.cuts.families.region_capacity import evaluate_geometric_region_capacity
    s_init = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s_init, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    # 初始 state: demand > cap, evaluator + step_7 都 True
    assert evaluate_geometric_region_capacity(cut, s_init) is True
    assert step_7_evaluate_cut(cut, s_init) is True

    # 改 state 让 cap 增 (移除 exterior_blocks + ghost_cells) → demand <= cap → cut 失效
    from src.cuts.lifecycle import BState, GroupState
    s_recovered = BState(
        groups={
            gid: GroupState(
                group_id=gid, demand=g.demand, pose_domain=g.pose_domain,
                selected_poses=list(g.selected_poses),
            )
            for gid, g in s_init.groups.items()
        },
        cell_owner=dict(s_init.cell_owner),
        ghost_rect=None,
        ghost_cells=frozenset(),          # 清 ghost
        exterior_blocks=frozenset(),       # 清 exterior
        artifact_hashes=dict(s_init.artifact_hashes),
        available_oracle_versions=s_init.available_oracle_versions,
        canonical_rules=s_init.canonical_rules,
        facility_templates=s_init.facility_templates,
        instance_to_facility_type=s_init.instance_to_facility_type,
        candidate_placements=s_init.candidate_placements,
    )
    # family evaluator 真重算 sound:
    assert evaluate_geometric_region_capacity(cut, s_recovered) is False
    # step_7 必跟 family 一致 (P0-1 fix: 接 dispatch)
    assert step_7_evaluate_cut(cut, s_recovered) is False


def test_assumption_unknown_key_fails_closed():
    s = make_state_with_crusher_on_left_baseline()
    unknown_assumption = Assumption(key="unknown_key", value="v")
    assert assumption_holds(s, unknown_assumption) is False


def test_source_digest_is_content_hash_and_ignores_runtime_pose_cache():
    s = make_state_with_crusher_on_left_baseline()
    digest_1 = compute_source_digest(s)

    # Runtime caches under "__*" must not change the cross-session source identity.
    cp = {"facility_pools": {}, "__pose_id_cache__": {("g", "p"): {"pose_id": "p"}}}
    s_with_cache = BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
        candidate_placements=cp,
    )
    s_no_cache = BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
        candidate_placements={"facility_pools": {}},
    )
    assert compute_source_digest(s_with_cache) == compute_source_digest(s_no_cache)

    changed = BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules={"boundary_storage_port": {"cells_per_pose": 99}},
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
    )
    assert compute_source_digest(changed) != digest_1

    # Caller-supplied stale digest must not mask a changed source payload.
    changed_with_stale_note = BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules={"boundary_storage_port": {"cells_per_pose": 99}},
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
        source_digest=digest_1,
    )
    assert compute_source_digest(changed_with_stale_note) != digest_1


def test_source_digest_tracks_authoritative_leading_dunder_keys_except_declared_runtime_caches():
    s = make_state_with_crusher_on_left_baseline()
    base_cp = {
        "facility_pools": {
            "__schema_valid_hidden_ft": [
                {
                    "pose_id": "p-hidden",
                    "occupied_cells": [[1, 1]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                }
            ]
        }
    }
    state_1 = BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules={
            "facility_templates": {
                "__schema_valid_hidden_ft": {"dimensions": {"w": 1, "h": 1}}
            }
        },
        facility_templates={"__schema_valid_hidden_ft": {"dimensions": {"w": 1, "h": 1}}},
        instance_to_facility_type={"g_hidden": "__schema_valid_hidden_ft"},
        candidate_placements=base_cp,
    )
    state_2 = BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules={
            "facility_templates": {
                "__schema_valid_hidden_ft": {"dimensions": {"w": 1, "h": 2}}
            }
        },
        facility_templates={"__schema_valid_hidden_ft": {"dimensions": {"w": 1, "h": 2}}},
        instance_to_facility_type={"g_hidden": "__schema_valid_hidden_ft"},
        candidate_placements={
            "facility_pools": {
                "__schema_valid_hidden_ft": [
                    {
                        "pose_id": "p-hidden",
                        "occupied_cells": [[1, 1], [1, 2]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                    }
                ]
            }
        },
    )
    assert compute_source_digest(state_2) != compute_source_digest(state_1)

    with_runtime_cache = BState(
        groups=state_1.groups,
        cell_owner=state_1.cell_owner,
        ghost_rect=state_1.ghost_rect,
        ghost_cells=state_1.ghost_cells,
        exterior_blocks=state_1.exterior_blocks,
        artifact_hashes=state_1.artifact_hashes,
        available_oracle_versions=state_1.available_oracle_versions,
        canonical_rules=state_1.canonical_rules,
        facility_templates=state_1.facility_templates,
        instance_to_facility_type=state_1.instance_to_facility_type,
        candidate_placements={
            **base_cp,
            "__pose_id_cache__": {
                ("__schema_valid_hidden_ft", "p-hidden"): {"pose_id": "p-hidden"}
            },
            "__pose_id_cache_digest__": "runtime-only",
        },
    )
    assert compute_source_digest(with_runtime_cache) == compute_source_digest(state_1)


def test_source_digest_tracks_group_static_fields_but_not_selected_poses():
    s = make_state_with_crusher_on_left_baseline()
    digest_1 = compute_source_digest(s)

    selected_changed_groups = {
        gid: GroupState(
            group_id=gid,
            demand=g.demand,
            pose_domain=g.pose_domain,
            selected_poses=list(g.selected_poses) + (["p-new"] if gid == "crusher_blue_iron" else []),
        )
        for gid, g in s.groups.items()
    }
    selected_changed = BState(
        groups=selected_changed_groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
    )
    assert compute_source_digest(selected_changed) == digest_1

    demand_changed_groups = {
        gid: GroupState(
            group_id=gid,
            demand=(g.demand + 1 if gid == "boundary_storage_port" else g.demand),
            pose_domain=g.pose_domain,
            selected_poses=list(g.selected_poses),
        )
        for gid, g in s.groups.items()
    }
    demand_changed = BState(
        groups=demand_changed_groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
    )
    assert compute_source_digest(demand_changed) != digest_1

    domain_changed_groups = {
        gid: GroupState(
            group_id=gid,
            demand=g.demand,
            pose_domain=(frozenset({"p-domain"}) if gid == "crusher_blue_iron" else g.pose_domain),
            selected_poses=list(g.selected_poses),
        )
        for gid, g in s.groups.items()
    }
    domain_changed = BState(
        groups=domain_changed_groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
    )
    assert compute_source_digest(domain_changed) != digest_1


def test_step_7_fails_closed_on_source_digest_drift_before_replay_quarantine():
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None

    source_drift = BState(
        groups=s.groups,
        cell_owner=s.cell_owner,
        ghost_rect=s.ghost_rect,
        ghost_cells=s.ghost_cells,
        exterior_blocks=s.exterior_blocks,
        artifact_hashes=s.artifact_hashes,
        available_oracle_versions=s.available_oracle_versions,
        canonical_rules=s.canonical_rules,
        facility_templates=s.facility_templates,
        instance_to_facility_type=s.instance_to_facility_type,
        candidate_placements={"facility_pools": {"manufacturing_3x3": []}},
    )
    assert compute_source_digest(source_drift) != cut.scope.source_digest
    assert step_6_attach_scope_check(cut, source_drift) == "QUARANTINE"

    from src.cuts.families.region_capacity import evaluate_geometric_region_capacity

    assert evaluate_geometric_region_capacity(cut, source_drift) is True
    assert step_7_evaluate_cut(cut, source_drift) is False


def test_deserialize_rejects_cert_hash_mismatch():
    s = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        s, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    assert cut is not None
    blob = json.loads(step_3_serialize(cut).decode("utf-8"))
    blob["cert"]["cert_hash"] = "0" * 64

    with pytest.raises(ValueError, match="cert_hash mismatch"):
        step_4_deserialize(json.dumps(blob, sort_keys=True).encode("utf-8"))


def test_group_state_remaining_count_property():
    group = GroupState(
        group_id="g",
        demand=3,
        pose_domain=frozenset({"p1", "p2", "p3"}),
        selected_poses=["p1"],
    )
    assert group.remaining_count == 2


def test_deserialize_rejects_invalid_base64_payload_text():
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state, "left_baseline", "boundary_storage_port", CANONICAL_RULES
    )
    blob = json.loads(step_3_serialize(cut))
    blob["geometric_payload"] = "!!!!"

    with pytest.raises(ValueError, match="invalid base64"):
        step_4_deserialize(json.dumps(blob).encode("utf-8"))


def test_lifecycle_region_bitset_rejects_high_bits_outside_grid():
    arr = bytearray((70 * 70 + 7) // 8)
    arr[-1] = 0b10000000
    b64 = base64.b64encode(bytes(arr)).decode("ascii")

    with pytest.raises(ValueError, match="outside the grid"):
        _decode_region_bitset(b64)


def test_cut_post_init_rejects_non_cut_scope_object():
    with pytest.raises(ValueError, match="CutScope"):
        Cut(
            cut_id="bad-scope",
            family="region_capacity",
            literals=None,
            geometric_payload=b"{}",
            scope={"ghost_rect_id": "not-a-cut-scope"},
            cert=OracleCert(cert_kind="k", cert_payload=b"{}", cert_hash="h"),
        )
