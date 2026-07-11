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
    ScopeIdentityPreimageV1,
    assumption_holds,
    capture_scope_identity_preimage_v1,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    compute_scope_identity_legacy_hashes,
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


def test_scope_identity_preimage_capture_is_canonical_and_legacy_compatible():
    state = BState(
        groups={},
        ghost_rect=(20, 21, 2, 3),
        ghost_cells=frozenset({(21, 22), (20, 21)}),
        exterior_blocks=frozenset({(7, 9), (1, 4)}),
    )

    preimage = capture_scope_identity_preimage_v1(state)

    assert preimage == ScopeIdentityPreimageV1(
        ghost_rect=(20, 21, 2, 3),
        blocked_cells=((1, 4), (7, 9), (20, 21), (21, 22)),
        exterior_blocks=((1, 4), (7, 9)),
    )
    assert compute_scope_identity_legacy_hashes(preimage) == (
        compute_ghost_rect_id(state.ghost_rect),
        compute_blocked_cells_hash(state),
        compute_exterior_blocks_hash(state),
    )


@pytest.mark.parametrize(
    ("kwargs", "expected_fragment"),
    [
        (
            {
                "ghost_rect": (1, 2, 3, 4),
                "blocked_cells": ((2, 0), (1, 0)),
                "exterior_blocks": (),
            },
            "sorted and unique",
        ),
        (
            {
                "ghost_rect": (1, 2, 3, 4),
                "blocked_cells": ((1, 0),),
                "exterior_blocks": ((2, 0),),
            },
            "subset",
        ),
        (
            {
                "ghost_rect": None,
                "blocked_cells": ((1, 0),),
                "exterior_blocks": (),
            },
            "cannot contain ghost cells",
        ),
    ],
)
def test_scope_identity_preimage_rejects_noncanonical_shapes(
    kwargs,
    expected_fragment,
):
    with pytest.raises(ValueError, match=expected_fragment):
        ScopeIdentityPreimageV1(**kwargs)


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


def test_scope_identity_preimage_serialization_roundtrip_and_legacy_default():
    state = make_state_with_crusher_on_left_baseline()
    cut = step_1_generate_region_capacity_combinatorial(
        state,
        "left_baseline",
        "boundary_storage_port",
        CANONICAL_RULES,
    )
    assert cut is not None
    assert cut.scope is not None
    preimage = capture_scope_identity_preimage_v1(state)
    cut_with_preimage = replace(
        cut,
        scope=replace(cut.scope, identity_preimage=preimage),
    )

    encoded = step_3_serialize(cut_with_preimage)
    restored = step_4_deserialize(encoded)
    assert restored.scope is not None
    assert restored.scope.identity_preimage == preimage

    legacy_document = json.loads(encoded)
    del legacy_document["scope"]["identity_preimage"]
    restored_legacy = step_4_deserialize(
        json.dumps(legacy_document, sort_keys=True).encode("utf-8")
    )
    assert restored_legacy.scope is not None
    assert restored_legacy.scope.identity_preimage is None


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


# ============================================================================
# B5a: typed step_6/step_7 attestation + typed single-entry scope currentness
#
# Pre-B5a step_6/step_7 took a raw (Cut, BState) and ran the legacy 6-step scope
# replay.  That role split: scope/artifact/source/exterior currentness is now the
# typed single entry (validate_and_compile_cut -> CutRejection stage="scope"),
# and step_6/step_7 collapse to a digest attestation over a CompiledCut +
# ValidatedStateSnapshot.  Raw geometric-evaluator coverage lives (unchanged) in
# test_family_region_capacity.py; the removed raw ghost/oracle HOLD branches are
# now covered by the typed differential suite (test_stage_b_region_capacity.py).
# ============================================================================


def _typed_bound_region_world(*, extra_exterior=frozenset()):
    """(snapshot, oracle F1 cut, sources) on the proven bound-region fixture."""
    from src.cuts.frozen_artifacts import build_frozen_artifact_bundle
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.cuts.state_snapshot import build_validated_state_snapshot
    from src.tests.cuts.test_stage_b_contracts import _bound_region_sources, _build_bundle

    sources = _bound_region_sources(BState, GroupState, ghost_rect=(0, 0, 3, 1))
    if extra_exterior:
        object.__setattr__(
            sources["state"], "exterior_blocks", frozenset(extra_exterior)
        )
    sources["state"].source_digest = compute_source_digest(sources["state"])
    bundle = _build_bundle(build_frozen_artifact_bundle, sources)
    snapshot = build_validated_state_snapshot(sources["state"], bundle)
    cut = generate_region_capacity_cuts(sources["state"], sources["canonical_rules"])[0]
    return snapshot, cut, sources


def _typed_scope_result(cut, snapshot):
    from src.cuts.typed_platform import (
        build_production_registry,
        cut_to_envelope_v1,
        validate_and_compile_cut,
    )

    return validate_and_compile_cut(
        cut_to_envelope_v1(cut), snapshot, build_production_registry()
    )


def _typed_attestation_pair():
    """(compiled_a, snapshot_a, snapshot_b) where compiled_a attests snapshot_a
    only.  snapshot_b differs by one incumbent selected pose, so its digest (which
    covers selected_poses) diverges while the source digest is unchanged."""
    from src.cuts.typed_platform import CompiledCut

    snapshot_a, cut, sources = _typed_bound_region_world()
    compiled_a = _typed_scope_result(cut, snapshot_a)
    assert isinstance(compiled_a, CompiledCut)

    from src.cuts.frozen_artifacts import build_frozen_artifact_bundle
    from src.cuts.state_snapshot import build_validated_state_snapshot
    from src.tests.cuts.test_stage_b_contracts import _bound_region_sources, _build_bundle

    group_id = next(iter(sources["state"].groups))
    drift = _bound_region_sources(BState, GroupState, ghost_rect=(0, 0, 3, 1))
    drift["state"].groups[group_id].selected_poses.append("boundary_pose_0")
    drift["state"].source_digest = compute_source_digest(drift["state"])
    bundle_b = _build_bundle(build_frozen_artifact_bundle, drift)
    snapshot_b = build_validated_state_snapshot(drift["state"], bundle_b)
    assert snapshot_b.digest != snapshot_a.digest
    return compiled_a, snapshot_a, snapshot_b


def test_attach_scope_quarantines_cut_with_omitted_artifact_dependency():
    """Typed scope currentness rejects a cut that drops an artifact dependency."""
    from src.cuts.typed_platform import CutRejection

    snapshot, cut, _sources = _typed_bound_region_world()
    trimmed = {k: v for k, v in cut.scope.artifact_hashes.items() if k != "canonical_rules"}
    incomplete = replace(cut, scope=replace(cut.scope, artifact_hashes=trimmed))
    result = _typed_scope_result(incomplete, snapshot)
    assert isinstance(result, CutRejection)
    assert result.stage == "scope"


def test_attach_scope_quarantines_cut_with_unknown_artifact_dependency():
    """Typed scope currentness rejects a cut that adds an unknown dependency."""
    from src.cuts.typed_platform import CutRejection

    snapshot, cut, _sources = _typed_bound_region_world()
    extra = {**cut.scope.artifact_hashes, "nonexistent-artifact.json": "0" * 64}
    overreported = replace(cut, scope=replace(cut.scope, artifact_hashes=extra))
    result = _typed_scope_result(overreported, snapshot)
    assert isinstance(result, CutRejection)
    assert result.stage == "scope"


def test_attach_scope_accepts_complete_matching_artifact_snapshot():
    """A matching cut compiles and its compiled form attests the snapshot."""
    from src.cuts.typed_platform import CompiledCut

    snapshot, cut, _sources = _typed_bound_region_world()
    compiled = _typed_scope_result(cut, snapshot)
    assert isinstance(compiled, CompiledCut)
    assert step_6_attach_scope_check(compiled, snapshot) == "ATTACH"
    assert step_7_evaluate_cut(compiled, snapshot) is True


def test_step_7_fails_closed_when_oracle_version_unavailable_before_replay_hold():
    """V31-family regression (typed re-frame): a compiled cut that no longer
    attests to the current snapshot must fail closed in step_6/step_7 before any
    attach -- the typed successor to the legacy oracle-version HOLD guard."""
    compiled_a, snapshot_a, snapshot_b = _typed_attestation_pair()
    assert step_6_attach_scope_check(compiled_a, snapshot_a) == "ATTACH"
    assert step_6_attach_scope_check(compiled_a, snapshot_b) == "QUARANTINE"
    assert step_7_evaluate_cut(compiled_a, snapshot_b) is False


def test_step_7_fails_closed_when_active_assumption_no_longer_holds_before_replay_hold():
    """V31-family regression (typed re-frame): an attestation mismatch (the
    successor to an expired active assumption) fails closed through the whole
    step_7 delegate chain before any attach."""
    from src.cuts.lifecycle import (
        evaluator_scope_matches_current_state,
        step_7_evaluation_attach_decision,
    )

    compiled_a, snapshot_a, snapshot_b = _typed_attestation_pair()
    assert step_7_evaluate_cut(compiled_a, snapshot_a) is True
    assert step_7_evaluation_attach_decision(compiled_a, snapshot_b) == "QUARANTINE"
    assert evaluator_scope_matches_current_state(compiled_a, snapshot_b) is False
    assert step_7_evaluate_cut(compiled_a, snapshot_b) is False



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
    """Typed re-frame: a source/exterior-drifted world both (a) rejects the cut
    at the typed single entry (CutRejection stage='scope') and (b) leaves any
    prior compiled cut non-attesting, so step_6/step_7 fail closed before attach.
    """
    from src.cuts.typed_platform import CompiledCut, CutRejection

    snapshot, cut, _sources = _typed_bound_region_world()
    compiled = _typed_scope_result(cut, snapshot)
    assert isinstance(compiled, CompiledCut)

    # A snapshot on a source-drifted state (extra exterior block changes the
    # source digest / exterior identity).
    drift_snapshot, _drift_cut, _drift_sources = _typed_bound_region_world(
        extra_exterior=frozenset({(40, 0)})
    )
    # Exterior blocks are outside the source-digest field set but inside the
    # snapshot identity, so the snapshot digest diverges (attestation drift).
    assert drift_snapshot.digest != snapshot.digest

    # (a) compiling the same cut against the drifted snapshot is rejected at scope.
    result = _typed_scope_result(cut, drift_snapshot)
    assert isinstance(result, CutRejection)
    assert result.stage == "scope"

    # (b) the already-compiled cut no longer attests the drifted snapshot.
    assert step_6_attach_scope_check(compiled, drift_snapshot) == "QUARANTINE"
    assert step_7_evaluate_cut(compiled, drift_snapshot) is False


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
