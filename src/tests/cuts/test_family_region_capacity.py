"""Phase 1.1 P1.5 + Gap 6 修后 test — Family 1 region_capacity union region.

Gap 6+7+8 (Gemini round 30) 修后 schema:
- region_kind = "left_or_bottom_union" (替 per-side)
- gid="boundary_io" 经 instance_to_facility_type → facility_type → facility_templates
- demand=46 (真 mandatory_exact_instances count)

Coverage:
- validate_region_capacity: 4 step check (cap_R / placement_rule / cells_per_pose
  source-of-truth / demand_R / witness)
- 5 unsound case: cap_R / demand_R / cells_per_pose rotated / placement_rule
  不映射 / witness fail
- 2 schema_err case: malformed cert / missing cells_per_pose / no facility_templates
- evaluate_geometric: returns True
- generate_region_capacity_cuts:
  - Union 数学: ghost ≥ 2 cells → trigger; ghost 单 cell on union → no trigger
  - GHOST_AGNOSTIC iff ghost ∩ union == ∅
"""
from __future__ import annotations

import json

from src.cuts.families.region_capacity import (
    evaluate_geometric_region_capacity,
    validate_region_capacity,
)
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    BState,
    Cut,
    GroupState,
)
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts


# Gap 8 修: gid 用真 operation_type, facility_templates 跟 真 canonical_rules schema 对齐
INSTANCE_TO_FT = {
    "boundary_io": "boundary_storage_port",
    "crusher_blue_iron": "manufacturing_3x3",
}
FACILITY_TEMPLATES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "dimensions": {"w": 1, "h": 3},  # 1 × 3 = 3 cells per pose
    },
    "manufacturing_3x3": {
        "dimensions": {"w": 3, "h": 3},
    },
}
# Legacy CANONICAL_RULES — 保留 args 兼容 (oracle sig stable)
CANONICAL_RULES = {"facility_templates": FACILITY_TEMPLATES}


def _mock_boundary_io_poses_in_union(n: int = 46):
    """生成 n 个 mock boundary_io pose, 占格全在 left ∪ bottom union 内 (sound).

    Phase 1.1 P1.5 + GPT pro round 2 P0-1 fix: all_poses_in_region strict check
    要 pose_domain 非空 + 每 pose occupied_cells ⊆ R. Mock 让 46 pose 都占 union
    内 cells, 让 oracle 把 group 当 contributing (P(g)⊆R 满足).

    真生产 boundary_io 14/54 pose 占 union 外 (e.g. (31,69)) — 真 P(g)⊄R, oracle
    严守不发 cut. 此 mock 故意构造 sound case 测 oracle path. 反例 case 见
    test_oracle_skips_when_group_not_P_in_R (新加).
    """
    poses = []
    for i in range(n):
        # 让每个 pose 占 (0, i)(0, i+1)(0, i+2) — bottom baseline 内, 3 cells
        poses.append({
            "pose_id": f"mock_p_{i}",
            "anchor": {"x": 0, "y": i},
            "occupied_cells": [[0, i % 68], [0, (i + 1) % 68], [0, (i + 2) % 68]],
            "input_port_cells": [],
            "output_port_cells": [],
        })
    return poses


def _make_state(
    *,
    boundary_exterior_blocks: int = 0,  # 在 left baseline 上 block 几个 cell
    ghost_rect: tuple = None,
    ghost_cells: set = None,
    boundary_io_poses: list = None,
) -> BState:
    """Default: demand=46 boundary_io, no blocks → cap=139 ≥ demand=138 → no cut.

    boundary_io_poses 默认 mock 46 pose 全在 union 内 (P(g)⊆R sound).
    若传 list 则用 — 测试 attacker 反例 (pose 在 R 外).
    """
    extra = {(15 + i, 0) for i in range(boundary_exterior_blocks)}
    if boundary_io_poses is None:
        boundary_io_poses = _mock_boundary_io_poses_in_union(n=46)
    pose_domain = frozenset(p["pose_id"] for p in boundary_io_poses)
    candidate_placements = {
        "facility_pools": {
            "boundary_storage_port": boundary_io_poses,
            "manufacturing_3x3": [],
        }
    }
    return BState(
        groups={
            "boundary_io": GroupState(
                "boundary_io", demand=46, pose_domain=pose_domain,
            ),
            "crusher_blue_iron": GroupState(
                "crusher_blue_iron", demand=34, pose_domain=frozenset(),
            ),
        },
        ghost_rect=ghost_rect,
        ghost_cells=frozenset(ghost_cells or set()),
        exterior_blocks=frozenset(extra),
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"region_capacity_v1"}),
        canonical_rules=CANONICAL_RULES,
        facility_templates=FACILITY_TEMPLATES,
        instance_to_facility_type=INSTANCE_TO_FT,
        candidate_placements=candidate_placements,
    )


# ============================================================================
# Oracle: generate_region_capacity_cuts — Union region 数学
# ============================================================================

def test_oracle_emits_cut_when_union_overflow_2_cells():
    """Gap 6 union: 2 exterior on left baseline → union cap=137 < demand=138 → cut."""
    state = _make_state(boundary_exterior_blocks=2)
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    cut = cuts[0]
    assert cut.family == "region_capacity"
    cert = json.loads(cut.geometric_payload)
    assert cert["region_kind"] == "left_or_bottom_union"
    # union cap = 70 + 70 - 1 (overlap (0,0)) - 2 (exterior) = 137
    assert cert["cap_R"] == 137
    assert cert["demand_R"] == 138  # 46 × 3
    assert cert["gap"] == 1


def test_oracle_silent_when_no_overflow_no_blocks():
    """0 ghost / exterior → union cap=139 ≥ demand=138 → no cut."""
    state = _make_state(boundary_exterior_blocks=0)
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert cuts == []


def test_oracle_silent_when_single_cell_block():
    """Gap 6 sound case: union ghost 单 cell → cap=138 == demand=138 (gap=0)
    → no cut (feasible 刚好够)."""
    state = _make_state(boundary_exterior_blocks=1)
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert cuts == []


def test_oracle_ghost_block_bottom_3_cells_triggers_FN_proof():
    """Gap 6 关键 case: ghost block 3 cells on bottom baseline → union cap=136
    < demand=138. union 形式 trigger (vs per-side 形式会 FN — per-side left
    cap=70 ≥ left demand=69 不 trigger 即便全局 INFEASIBLE)."""
    # ghost 占 (0, 30) (0, 31) (0, 32) — bottom baseline 3 cells
    state = _make_state(
        ghost_rect=(0, 30, 1, 3),
        ghost_cells={(0, 30), (0, 31), (0, 32)},
    )
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    cert = json.loads(cuts[0].geometric_payload)
    assert cert["cap_R"] == 136
    assert cert["demand_R"] == 138
    assert cert["gap"] == 2


def test_oracle_ghost_agnostic_when_ghost_disjoint_from_union():
    """Gap 6 GHOST_AGNOSTIC dispatch: ghost ∩ union == ∅ → AGNOSTIC scope."""
    state = _make_state(
        boundary_exterior_blocks=2,
        ghost_rect=(20, 20, 5, 5),
        ghost_cells={(20, 20), (21, 20)},  # not on left/bottom baseline
    )
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    assert cuts[0].scope.ghost_rect_id == GHOST_AGNOSTIC


def test_oracle_ghost_bound_when_ghost_intersects_union():
    state = _make_state(
        ghost_rect=(30, 0, 3, 1),
        ghost_cells={(30, 0), (31, 0), (32, 0)},
    )
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    assert cuts[0].scope.ghost_rect_id != GHOST_AGNOSTIC


# ============================================================================
# Validator: validate_region_capacity
# ============================================================================

def test_validator_ok_on_legit_cut():
    state = _make_state(boundary_exterior_blocks=2)
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    vr = validate_region_capacity(cuts[0], state, CANONICAL_RULES)
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


def test_validator_unsound_cap_R_tampered():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = 999
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    tampered = Cut(
        cut_id=cut.cut_id, family=cut.family,
        literals=None, geometric_payload=tampered_payload,
        scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )
    vr = validate_region_capacity(tampered, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "cap_R mismatch" in vr.detail


def test_validator_unsound_demand_R_tampered():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["demand_R"] = 9999
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    tampered = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=None,
        geometric_payload=tampered_payload, scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )
    vr = validate_region_capacity(tampered, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "demand_R mismatch" in vr.detail


def test_validator_unsound_cells_per_pose_source_rotated():
    """canonical_rules 改 dimensions → cells_per_pose 跟 cert 不一致 → unsound."""
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    # 改 state.facility_templates dimensions (模拟 source rotated)
    rotated_templates = {
        **FACILITY_TEMPLATES,
        "boundary_storage_port": {
            **FACILITY_TEMPLATES["boundary_storage_port"],
            "dimensions": {"w": 1, "h": 2},  # 改 3 → 2
        },
    }
    rotated_state = BState(
        groups=state.groups,
        ghost_rect=state.ghost_rect,
        ghost_cells=state.ghost_cells,
        exterior_blocks=state.exterior_blocks,
        artifact_hashes=state.artifact_hashes,
        available_oracle_versions=state.available_oracle_versions,
        canonical_rules=state.canonical_rules,
        facility_templates=rotated_templates,
        instance_to_facility_type=state.instance_to_facility_type,
        candidate_placements=state.candidate_placements,  # Step E: 保留, 让 P(g)⊆R 先 pass
    )
    vr = validate_region_capacity(cut, rotated_state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "cells_per_pose mismatch" in vr.detail


def test_validator_schema_err_missing_cells_per_pose():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    del cert_dict["cells_per_pose"]
    bad_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    bad_cut = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=None,
        geometric_payload=bad_payload, scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )
    vr = validate_region_capacity(bad_cut, state, CANONICAL_RULES)
    assert vr.kind == "schema_err"
    assert "cells_per_pose" in vr.detail


def test_validator_unsound_when_facility_templates_not_injected():
    """fail-closed: production state 必 inject facility_templates;
    None → helper 返 unknown → _group_falls_in_region False → unsound
    ('placement_rule 不映射'). validator 拒 cut.

    (技术上也可视为 schema_err — facility_templates 缺失是 schema 不全 — 但
    validator check order 让 placement_rule 路径先 hit; 行为 fail-closed
    一致, 都不 reactivate cut.)"""
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    state_no_ft = BState(
        groups=state.groups,
        ghost_rect=state.ghost_rect,
        ghost_cells=state.ghost_cells,
        exterior_blocks=state.exterior_blocks,
        artifact_hashes=state.artifact_hashes,
        available_oracle_versions=state.available_oracle_versions,
        canonical_rules=state.canonical_rules,
        facility_templates=None,
        instance_to_facility_type=None,
    )
    vr = validate_region_capacity(cut, state_no_ft, CANONICAL_RULES)
    assert vr.kind in ("unsound", "schema_err")
    assert "placement_rule" in vr.detail or "cells_per_pose" in vr.detail


# ============================================================================
# evaluate_geometric (v1.1 简化版)
# ============================================================================

def test_evaluate_geometric_returns_true():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    assert evaluate_geometric_region_capacity(cut, state) is True


# ============================================================================
# Active assumptions on emitted cut
# ============================================================================

def test_oracle_cut_carries_correct_assumptions():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    keys = {a.key for a in cut.scope.active_assumptions}
    assert "left_or_bottom_boundary_saturation" in keys
    assert "placement_rule" in keys
    placement_rule_assumptions = [
        a for a in cut.scope.active_assumptions if a.key == "placement_rule"
    ]
    assert len(placement_rule_assumptions) == 1
    # Gap 8: 真 group_id="boundary_io" (operation_type 真名)
    assert "boundary_io=left_or_bottom_boundary" in placement_rule_assumptions[0].value


# ============================================================================
# group_id misuse — production 该用 operation_type
# ============================================================================

def test_oracle_skips_free_placement_rule_groups():
    """crusher_blue_iron placement_rule='free' → 不该 contribute 到任何 region cut."""
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    contributing = json.loads(cut.geometric_payload)["contributing_groups"]
    gids = {c[0] for c in contributing}
    assert "boundary_io" in gids
    assert "crusher_blue_iron" not in gids


# ============================================================================
# GPT pro round 2 P0-1 — F1 demand 真 P(g) ⊆ R
# ============================================================================

def _mock_boundary_io_poses_partial_outside_union(n_in: int, n_out: int):
    """生成 mock pose: n_in 个在 union, n_out 个占 union 外 cell (反 GPT 反例)."""
    poses = []
    for i in range(n_in):
        poses.append({
            "pose_id": f"in_p_{i}",
            "anchor": {"x": 0, "y": i},
            "occupied_cells": [[0, i % 68], [0, (i + 1) % 68], [0, (i + 2) % 68]],
            "input_port_cells": [],
            "output_port_cells": [],
        })
    for i in range(n_out):
        # 占 (31, 69)/(32, 69)/(33, 69) — 不在 left baseline (x=0..69 y=0) 也
        # 不在 bottom baseline (x=0 y=0..69) — 真 GPT pro 反例 cell
        poses.append({
            "pose_id": f"out_p_{i}",
            "anchor": {"x": 31 + i, "y": 69},
            "occupied_cells": [[31, 69], [32, 69], [33, 69]],
            "input_port_cells": [],
            "output_port_cells": [],
        })
    return poses


def test_validator_unsound_duplicate_contributing_groups():
    """GPT pro v3 P0 反例: cert.contributing_groups 把同一 group 重复列, 让 demand_R
    被重复累加 → fake over-demand cut 误剪合法 state.

    反例: actual demand=46 (boundary_io), cap_R=139 - 2 exterior = 137 (合法).
    cert duplicate ("boundary_io", 138) 两次 → demand=276 > cap=137 → 假证.
    validator 必拒 duplicate group entry.
    """
    state = _make_state(boundary_exterior_blocks=2)
    # 先用 oracle 产 sound cut 然后改 cert duplicate
    sound_cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(sound_cut.geometric_payload)
    # 复制 boundary_io entry → contributing_groups 含 2 个相同 gid
    cert_dict["contributing_groups"] = [
        ["boundary_io", 138],
        ["boundary_io", 138],
    ]
    cert_dict["demand_R"] = 276
    cert_dict["gap"] = 276 - cert_dict["cap_R"]
    bad_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    bad_cut = Cut(
        cut_id=sound_cut.cut_id, family=sound_cut.family, literals=None,
        geometric_payload=bad_payload,
        scope=sound_cut.scope, cert=sound_cut.cert,
        family_version=sound_cut.family_version,
        validator_version=sound_cut.validator_version,
    )
    vr = validate_region_capacity(bad_cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "duplicate contributing group" in (vr.detail or "")


def test_validator_unsound_contributing_groups_tuple_demand_fake():
    """GPT pro v3 顺手补: cert tuple demand_in_cert 必 == group.demand × cpp.
    防 attacker 在 tuple 内 inflate demand 跟其他 field 配合伪造.
    """
    state = _make_state(boundary_exterior_blocks=2)
    sound_cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(sound_cut.geometric_payload)
    # tuple demand 写错 (真实 46*3=138, 改 999)
    cert_dict["contributing_groups"] = [["boundary_io", 999]]
    bad_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    bad_cut = Cut(
        cut_id=sound_cut.cut_id, family=sound_cut.family, literals=None,
        geometric_payload=bad_payload,
        scope=sound_cut.scope, cert=sound_cut.cert,
        family_version=sound_cut.family_version,
        validator_version=sound_cut.validator_version,
    )
    vr = validate_region_capacity(bad_cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "tuple demand mismatch" in (vr.detail or "")


def test_validator_unsound_gap_inconsistent():
    """gap consistency: cert.gap 必 == demand_R - cap_R."""
    state = _make_state(boundary_exterior_blocks=2)
    sound_cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(sound_cut.geometric_payload)
    cert_dict["gap"] = 99  # tampered (真 = 138 - 137 = 1)
    bad_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    bad_cut = Cut(
        cut_id=sound_cut.cut_id, family=sound_cut.family, literals=None,
        geometric_payload=bad_payload,
        scope=sound_cut.scope, cert=sound_cut.cert,
        family_version=sound_cut.family_version,
        validator_version=sound_cut.validator_version,
    )
    vr = validate_region_capacity(bad_cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "gap mismatch" in (vr.detail or "")


def test_oracle_skips_group_when_some_pose_outside_R():
    """GPT pro round 2 P0-1 反例: boundary_io 46 pose 中 14 个占 (31,69) 等 cell
    不在 left ∪ bottom union → 整 group 不 P(g)⊆R (spec §2b 严格) → oracle 不当
    contributing → 不发 cut.

    真生产 boundary_io 14/54 pose 落 union 外 (e.g. viewer::boundary_required_
    output_source_ore_005 占 (31,69)/(32,69)/(33,69)). Phase 1.1 v1.1 fail-closed.
    """
    # 46 pose: 32 in + 14 out — GPT 反例真数据 mirror
    poses = _mock_boundary_io_poses_partial_outside_union(n_in=32, n_out=14)
    state = _make_state(boundary_exterior_blocks=2, boundary_io_poses=poses)
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert cuts == [], (
        f"expect 0 cut (group not P(g)⊆R, fail-closed). got {len(cuts)} cuts"
    )


def test_evaluate_recomputes_cap_R_after_exterior_blocks_removed():
    """Gemini round 33 P0 fix: evaluate_geometric 必须真重算 cap_R, 不准无条件
    返 True. 反例: oracle 发 cut 时 cap_R=137 < demand=138 → cut violate. master
    回溯移除 2 exterior_blocks → cap_R 恢复 139 ≥ demand=138 → cut 不再 violate.
    evaluate 必须返 False (propagator skip, 不剪合法 state).
    """
    # 步骤 1: 初始 exterior_blocks=2, oracle 产 violating cut
    state_init = _make_state(boundary_exterior_blocks=2)
    cuts = generate_region_capacity_cuts(state_init, CANONICAL_RULES)
    assert len(cuts) == 1
    cut = cuts[0]
    assert evaluate_geometric_region_capacity(cut, state_init) is True

    # 步骤 2: state 变 — master 移除 exterior_blocks (回溯), cap_R 增 → cut 不再 violate
    state_recovered = _make_state(boundary_exterior_blocks=0)
    assert evaluate_geometric_region_capacity(cut, state_recovered) is False, \
        "exterior_blocks 移除后 cap_R 增 demand 不变, evaluate 必须 False (Sound)"


def test_validator_unsound_when_cert_carries_group_with_pose_outside_R():
    """Validator 端: attacker 手造 cert 含 boundary_io 当 contributing 但 真
    pose_domain 有 pose 在 R 外. validator 必查 P(g)⊆R 严格 — 不满足则 unsound.
    """
    # 先构 sound state + sound cut
    sound_state = _make_state(boundary_exterior_blocks=2)
    cuts = generate_region_capacity_cuts(sound_state, CANONICAL_RULES)
    assert len(cuts) == 1
    cut = cuts[0]
    # 改 state pose_domain 让 boundary_io 14 pose 落 union 外 — cert 仍 claim
    # boundary_io 是 contributing
    poses_bad = _mock_boundary_io_poses_partial_outside_union(n_in=32, n_out=14)
    bad_pose_domain = frozenset(p["pose_id"] for p in poses_bad)
    bad_candidate_placements = {
        "facility_pools": {
            "boundary_storage_port": poses_bad,
            "manufacturing_3x3": [],
        }
    }
    bad_state = BState(
        groups={
            "boundary_io": GroupState(
                "boundary_io", demand=46, pose_domain=bad_pose_domain,
            ),
            "crusher_blue_iron": GroupState(
                "crusher_blue_iron", demand=34, pose_domain=frozenset(),
            ),
        },
        ghost_rect=sound_state.ghost_rect,
        ghost_cells=sound_state.ghost_cells,
        exterior_blocks=sound_state.exterior_blocks,
        artifact_hashes=sound_state.artifact_hashes,
        available_oracle_versions=sound_state.available_oracle_versions,
        canonical_rules=sound_state.canonical_rules,
        facility_templates=sound_state.facility_templates,
        instance_to_facility_type=sound_state.instance_to_facility_type,
        candidate_placements=bad_candidate_placements,
    )
    vr = validate_region_capacity(cut, bad_state, CANONICAL_RULES)
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "P(g) ⊆ R" in (vr.detail or "")


def test_validator_schema_err_bool_numeric_fields_are_not_ints():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = True
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    tampered = Cut(
        cut_id=cut.cut_id,
        family=cut.family,
        literals=None,
        geometric_payload=tampered_payload,
        scope=cut.scope,
        cert=cut.cert,
        family_version=cut.family_version,
        validator_version=cut.validator_version,
    )

    vr = validate_region_capacity(tampered, state, CANONICAL_RULES)
    assert vr.kind == "schema_err"
    assert "cap_R" in vr.detail
