"""Phase 1.1 P1.7 test — Family 3 port_exposure (literal-based, multiset eval).

Coverage:
- validate_port_exposure: ok / unsound (front_cell math wrong / blocking facility
  not at front_cell / port not in facility ports) / schema_err
- evaluate_literal_multiset: multiset subset match (state has 2 literals →
  True; missing 1 → False; slot permutation invariant)
- ``evaluate_literal_multiset`` (lifecycle generic):
  - 1 literal in 1 group: subset match
  - 2 literals same group: requires 2 selected_poses with same pose_id
  - 2 literals diff group: requires 1 in each
  - empty literals → False (no-op cut)
  - group not in state → False
  - state count short → False
  - slot index anonymity: slot=2 cut equivalent to slot=5 (per state_machine_v2 §5)
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace

from src.cuts.families.port_exposure import validate_port_exposure
from src.cuts.helpers.candidate_placements import _facility_pools_digest, find_pose
from src.cuts.oracles.port_exposure_oracle import generate_port_exposure_cuts
from src.cuts.lifecycle import (
    AnonymousSlotRef,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    GroupState,
    OracleCert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    compute_source_digest,
    evaluate_literal_multiset,
    step_6_attach_scope_check,
    step_7_evaluate_cut,
)
from src.cuts.replay import ReplayContext, replay_cut
from src.cuts.store import CutStore


CANONICAL_RULES = {
    "crusher": {
        "placement_rule": "free",
        "cells_per_pose": 9,
    },
    "refinery": {
        "placement_rule": "free",
        "cells_per_pose": 9,
    },
}

# Gap 8/9 schema: production state inject 这些
_FACILITY_TEMPLATES = {
    "manufacturing_3x3": {"dimensions": {"w": 3, "h": 3}},
}
_INSTANCE_TO_FT = {"crusher": "manufacturing_3x3", "refinery": "manufacturing_3x3"}
# Gap 9 + Gap 11 修: candidate_placements pose 层 ports + N/S/E/W = real grid
# convention (y=row up; N=(0,-1), W=(-1,0)). crusher pose "p7" 占 x∈[10..12]
# y∈[10..12]. port (10, 10, W): facility 左上 corner cell, W 朝外 → front=(9, 10).
_CANDIDATE_PLACEMENTS = {
    "facility_pools": {
        "manufacturing_3x3": [
            {
                "pose_id": "p7",
                "anchor": {"x": 10, "y": 10},
                "occupied_cells": [
                    [10, 10], [11, 10], [12, 10],
                    [10, 11], [11, 11], [12, 11],
                    [10, 12], [11, 12], [12, 12],
                ],
                "input_port_cells": [],
                "output_port_cells": [
                    {"x": 10, "y": 10, "dir": "W", "commodity": "test"},
                ],
            },
            {
                "pose_id": "p3",
                "anchor": {"x": 9, "y": 10},  # 占 front_cell (9, 10) of pose p7's port
                "occupied_cells": [
                    [9, 10], [10, 10], [11, 10],  # 跟 p7 重叠 (9,10) — Production
                    [9, 11], [10, 11], [11, 11],   # 这种重叠 master 不该选; 只 fixture 模拟
                    [9, 12], [10, 12], [11, 12],   # blocking
                ],
                "input_port_cells": [],
                "output_port_cells": [],
            },
        ],
    },
}


def _make_port_exposure_cert(
    *,
    facility_group: str = "crusher",
    facility_pose_id: str = "p7",  # Gap 10: PoseId=str
    port_cell: tuple = (10, 10),
    port_direction: str = "W",  # Gap 11 修: W=(-1, 0), front=(9, 10) outside facility
    front_cell: tuple = (9, 10),
    blocking_group: str = "refinery",
    blocking_slot: int = 0,
    blocking_pose_id: str = "p3",
) -> bytes:
    cert_dict = {
        "cert_kind": "port_exposure_blocked",
        "facility_group": facility_group,
        "facility_pose_id": facility_pose_id,
        "port_cell": list(port_cell),
        "port_direction": port_direction,
        "front_cell": list(front_cell),
        "blocking_facility": [blocking_group, blocking_slot, blocking_pose_id],
        "active_port_witness_b64": None,
    }
    return json.dumps(cert_dict, sort_keys=True).encode("utf-8")


def _make_port_exposure_cut(
    cert_payload: bytes,
    *,
    facility_group: str = "crusher",
    facility_pose_id: str = "p7",
    blocking_group: str = "refinery",
    blocking_slot: int = 0,
    blocking_pose_id: str = "p3",
    scope_state: BState | None = None,
) -> Cut:
    literals = (
        CutLiteral(slot_ref=AnonymousSlotRef(facility_group, 0), pose_id=facility_pose_id),
        CutLiteral(
            slot_ref=AnonymousSlotRef(blocking_group, blocking_slot),
            pose_id=blocking_pose_id,
        ),
    )
    scope = _scope_for_state(scope_state or _make_state())
    cert = OracleCert(
        cert_kind="port_exposure_blocked",
        cert_payload=cert_payload,
        cert_hash="ch",
    )
    return Cut(
        cut_id="F3-test",
        family="port_exposure",
        literals=literals,
        geometric_payload=None,
        scope=scope,
        cert=cert,
        family_version="v1.0",
        validator_version="v1.0",
    )



def _with_valid_integrity(cut: Cut) -> Cut:
    assert cut.cert is not None
    cert_hash = hashlib.sha256(cut.cert.cert_payload).hexdigest()
    return replace(
        cut,
        cert=OracleCert(
            cert_kind=cut.cert.cert_kind,
            cert_payload=cut.cert.cert_payload,
            cert_hash=cert_hash,
        ),
        oracle_cert_hash=cert_hash,
    )

def _make_state(
    *,
    crusher_poses: list = None,
    refinery_poses: list = None,
    cell_owner: dict = None,
) -> BState:
    return BState(
        groups={
            "crusher": GroupState(
                "crusher",
                demand=4,
                pose_domain=frozenset(),
                selected_poses=crusher_poses or [],
            ),
            "refinery": GroupState(
                "refinery",
                demand=4,
                pose_domain=frozenset(),
                selected_poses=refinery_poses or [],
            ),
        },
        cell_owner=cell_owner or {},
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"port_exposure_v1"}),
        canonical_rules=CANONICAL_RULES,
        facility_templates=_FACILITY_TEMPLATES,
        instance_to_facility_type=_INSTANCE_TO_FT,
        candidate_placements=_CANDIDATE_PLACEMENTS,
    )


def _scope_for_state(state: BState) -> CutScope:
    return CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest=compute_source_digest(state),
        artifact_hashes=dict(state.artifact_hashes),
        oracle_abstraction_version="port_exposure_v1",
    )


def _typed_attestation_pair():
    """(compiled_a, snapshot_a, snapshot_b) anchored on a region_capacity typed
    world.  port_exposure is a legacy-diagnostic family (no typed compile), so the
    lifecycle attestation guards — which now take a CompiledCut + snapshot — are
    exercised via a real region_capacity CompiledCut whose attestation binds one
    snapshot only.  snapshot_b differs by one incumbent selected pose, diverging
    the snapshot digest while leaving the source digest unchanged."""
    from src.cuts.frozen_artifacts import build_frozen_artifact_bundle
    from src.cuts.lifecycle import BState as _BState
    from src.cuts.lifecycle import GroupState as _GroupState
    from src.cuts.lifecycle import compute_source_digest as _source_digest
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.cuts.state_snapshot import build_validated_state_snapshot
    from src.cuts.typed_platform import (
        CompiledCut,
        build_production_registry,
        cut_to_envelope_v1,
        validate_and_compile_cut,
    )
    from src.tests.cuts.test_stage_b_contracts import _bound_region_sources, _build_bundle

    sources = _bound_region_sources(_BState, _GroupState, ghost_rect=(0, 0, 3, 1))
    group_id = next(iter(sources["state"].groups))
    sources["state"].source_digest = _source_digest(sources["state"])
    snapshot_a = build_validated_state_snapshot(
        sources["state"], _build_bundle(build_frozen_artifact_bundle, sources)
    )
    raw = generate_region_capacity_cuts(sources["state"], sources["canonical_rules"])[0]
    compiled_a = validate_and_compile_cut(
        cut_to_envelope_v1(raw), snapshot_a, build_production_registry()
    )
    assert isinstance(compiled_a, CompiledCut)

    drift = _bound_region_sources(_BState, _GroupState, ghost_rect=(0, 0, 3, 1))
    drift["state"].groups[group_id].selected_poses.append("boundary_pose_0")
    drift["state"].source_digest = _source_digest(drift["state"])
    snapshot_b = build_validated_state_snapshot(
        drift["state"], _build_bundle(build_frozen_artifact_bundle, drift)
    )
    assert snapshot_b.digest != snapshot_a.digest
    return compiled_a, snapshot_a, snapshot_b


# ============================================================================
# F3 specific: validate_port_exposure
# ============================================================================



def test_evaluate_literal_multiset_fails_closed_on_source_digest_drift():
    """Typed re-frame: the literal attach-time guard (evaluate_literal_multiset)
    fails closed when the compiled cut no longer attests to the current snapshot.
    Pre-B5a this walked cut.literals vs state.selected_poses; that raw multiset
    logic is gone (soundness is the single entry's validate_plan)."""
    compiled_a, snapshot_a, snapshot_b = _typed_attestation_pair()
    assert evaluate_literal_multiset(compiled_a, snapshot_a) is True
    assert evaluate_literal_multiset(compiled_a, snapshot_b) is False


def test_validate_port_exposure_rebuilds_pose_cache_after_facility_pool_replaced():
    state = _make_state(cell_owner={(9, 10): ("refinery", 0)}, refinery_poses=["p3"])
    state.candidate_placements = copy.deepcopy(_CANDIDATE_PLACEMENTS)

    old_pose = find_pose(state, "refinery", "p3")
    assert old_pose is not None
    assert [9, 10] in old_pose["occupied_cells"]

    old_pool = state.candidate_placements["facility_pools"]["manufacturing_3x3"]
    new_pool = [copy.deepcopy(old_pool[0]), copy.deepcopy(old_pool[1])]
    new_pool[1]["occupied_cells"] = [[40, 40]]
    state.candidate_placements["facility_pools"]["manufacturing_3x3"] = new_pool

    cut = _make_port_exposure_cut(_make_port_exposure_cert(), scope_state=state)
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)

    assert vr.kind == "unsound"
    assert "front_cell" in (vr.detail or "")




def test_find_pose_return_value_is_not_authoritative_mutation_channel():
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner={(9, 10): ("refinery", 0)},
    )
    state.candidate_placements = copy.deepcopy(_CANDIDATE_PLACEMENTS)
    source_pose = state.candidate_placements["facility_pools"]["manufacturing_3x3"][0]
    source_pose["output_port_cells"] = []

    returned_pose = find_pose(state, "crusher", "p7")
    assert returned_pose is not None
    returned_pose["output_port_cells"] = [
        {"x": 10, "y": 10, "dir": "W", "commodity": "test"},
    ]

    assert source_pose["output_port_cells"] == []


def test_port_exposure_generator_ignores_orphaned_same_digest_pose_cache(monkeypatch):
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner={(9, 10): ("refinery", 0)},
    )
    state.candidate_placements = copy.deepcopy(_CANDIDATE_PLACEMENTS)
    state.candidate_placements["facility_pools"]["manufacturing_3x3"][0]["output_port_cells"] = []
    source_digest = compute_source_digest(state)

    returned_pose = find_pose(state, "crusher", "p7")
    assert returned_pose is not None
    state.candidate_placements["facility_pools"] = copy.deepcopy(
        state.candidate_placements["facility_pools"]
    )
    assert compute_source_digest(state) == source_digest

    returned_pose["output_port_cells"] = [
        {"x": 10, "y": 10, "dir": "W", "commodity": "test"},
    ]
    assert (
        state.candidate_placements["facility_pools"]["manufacturing_3x3"][0]["output_port_cells"]
        == []
    )

    cuts = generate_port_exposure_cuts(
        state,
        target_poses=[("crusher", 0, "p7")],
    )
    assert cuts == []


def test_port_exposure_generator_ignores_mutated_find_pose_return(monkeypatch):
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner={(9, 10): ("refinery", 0)},
    )
    state.candidate_placements = copy.deepcopy(_CANDIDATE_PLACEMENTS)
    state.candidate_placements["facility_pools"]["manufacturing_3x3"][0]["output_port_cells"] = []

    returned_pose = find_pose(state, "crusher", "p7")
    assert returned_pose is not None
    returned_pose["output_port_cells"] = [
        {"x": 10, "y": 10, "dir": "W", "commodity": "test"},
    ]

    cuts = generate_port_exposure_cuts(
        state,
        target_poses=[("crusher", 0, "p7")],
    )
    assert cuts == []


def test_validate_port_exposure_ignores_forged_runtime_pose_cache_with_matching_digest():
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner={(9, 10): ("refinery", 0)},
    )
    state.candidate_placements = copy.deepcopy(_CANDIDATE_PLACEMENTS)
    pool = state.candidate_placements["facility_pools"]["manufacturing_3x3"]
    real_p7_no_port = pool[0]
    real_p7_no_port["output_port_cells"] = []
    forged_p7_with_port = copy.deepcopy(real_p7_no_port)
    forged_p7_with_port["output_port_cells"] = [
        {"x": 10, "y": 10, "dir": "W", "commodity": "test"},
    ]
    source_digest = compute_source_digest(state)

    state.candidate_placements["__pose_id_cache_digest__"] = _facility_pools_digest(
        state.candidate_placements
    )
    state.candidate_placements["__pose_id_cache__"] = {
        ("manufacturing_3x3", "p7"): forged_p7_with_port,
        ("manufacturing_3x3", "p3"): pool[1],
    }
    assert compute_source_digest(state) == source_digest

    cut = _with_valid_integrity(
        _make_port_exposure_cut(_make_port_exposure_cert(), scope_state=state)
    )
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "not in facility" in (vr.detail or "")

    # port_exposure is a legacy-diagnostic family: replay routes it through the
    # legacy validator over context.legacy_state (snapshot/registry unused), and
    # an unsound cut is quarantined — it never (re)enters the active store.
    store = CutStore()
    store.add_cut(cut)
    context = ReplayContext(snapshot=None, registry=None, legacy_state=state)
    decision = replay_cut(cut, store, context)
    assert decision == "QUARANTINE"
    assert not store.is_active(cut.cut_id)


def _make_dunder_facility_state(*, producer_port_cell: tuple[int, int] = (10, 10)) -> BState:
    cp = {
        "facility_pools": {
            "__manufacturing_3x3": [
                {
                    "pose_id": "p7",
                    "anchor": {"x": 10, "y": 10},
                    "occupied_cells": [[10, 10], [11, 10], [12, 10]],
                    "input_port_cells": [],
                    "output_port_cells": [
                        {
                            "x": producer_port_cell[0],
                            "y": producer_port_cell[1],
                            "dir": "W",
                            "commodity": "test",
                        },
                    ],
                }
            ],
            "blocker_ft": [
                {
                    "pose_id": "p3",
                    "anchor": {"x": 9, "y": 10},
                    "occupied_cells": [[9, 10]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                }
            ],
        }
    }
    return BState(
        groups={
            "crusher": GroupState(
                "crusher",
                demand=1,
                pose_domain=frozenset({"p7"}),
                selected_poses=["p7"],
            ),
            "refinery": GroupState(
                "refinery",
                demand=1,
                pose_domain=frozenset({"p3"}),
                selected_poses=["p3"],
            ),
        },
        cell_owner={(9, 10): ("refinery", 0)},
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"port_exposure_v1"}),
        canonical_rules={
            "facility_templates": {"__manufacturing_3x3": {}, "blocker_ft": {}}
        },
        facility_templates={"__manufacturing_3x3": {}, "blocker_ft": {}},
        instance_to_facility_type={
            "crusher": "__manufacturing_3x3",
            "refinery": "blocker_ft",
        },
        candidate_placements=cp,
    )


def test_find_pose_cache_tracks_schema_valid_leading_dunder_facility_pool_replacement():
    state = _make_dunder_facility_state(producer_port_cell=(10, 10))
    old_pose = find_pose(state, "crusher", "p7")
    assert old_pose is not None
    assert old_pose["output_port_cells"][0]["x"] == 10

    replacement_pose = copy.deepcopy(old_pose)
    replacement_pose["output_port_cells"] = [
        {"x": 12, "y": 10, "dir": "W", "commodity": "test"},
    ]
    state.candidate_placements["facility_pools"]["__manufacturing_3x3"] = [replacement_pose]

    refreshed_pose = find_pose(state, "crusher", "p7")
    assert refreshed_pose is not None
    assert refreshed_pose["output_port_cells"][0]["x"] == 12


def test_step_7_fails_closed_on_schema_valid_leading_dunder_source_drift():
    """Typed re-frame: the port_exposure legacy validator still accepts the
    dunder-facility source (unchanged), and the lifecycle step_6/step_7 guards
    fail closed on an attestation mismatch — the successor to the raw leading-
    dunder source-drift QUARANTINE.  (Leading-dunder source-digest tracking
    itself is covered by test_source_digest_* in test_lifecycle.py.)"""
    source_state = _make_dunder_facility_state(producer_port_cell=(10, 10))
    cut = _make_port_exposure_cut(_make_port_exposure_cert(), scope_state=source_state)
    assert validate_port_exposure(cut, source_state, CANONICAL_RULES).kind == "ok"

    compiled_a, snapshot_a, snapshot_b = _typed_attestation_pair()
    assert step_6_attach_scope_check(compiled_a, snapshot_a) == "ATTACH"
    assert step_6_attach_scope_check(compiled_a, snapshot_b) == "QUARANTINE"
    assert step_7_evaluate_cut(compiled_a, snapshot_b) is False


def test_validate_port_exposure_ok():
    """Gap 11 修后: W=(-1,0), port (10,10) W → front (9, 10) outside facility."""
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(9, 10),
    )
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={(9, 10): ("refinery", 0)}, refinery_poses=["p3"])
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


def test_validate_port_exposure_unsound_front_cell_math():
    """cert.front_cell ≠ port_cell + direction offset, but still inside board."""
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(8, 10),  # 错，但在 70x70 内
    )
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={(8, 10): ("refinery", 0)}, refinery_poses=["p3"])
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "front_cell mismatch" in vr.detail


def test_validate_port_exposure_schema_err_out_of_grid_cell():
    """F3 cert cell 必须 fail-closed 到 70x70 board 内。"""
    cert_payload = _make_port_exposure_cert(
        port_cell=(70, 10), port_direction="W", front_cell=(69, 10),
    )
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={(69, 10): ("refinery", 0)}, refinery_poses=["p3"])
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "schema_err"
    assert "out of grid" in (vr.detail or "")


def test_validate_port_exposure_unsound_blocking_facility_absent():
    """cell_owner[front_cell] 不是 cert blocking_facility."""
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(9, 10),
        blocking_group="refinery", blocking_slot=0,
    )
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={})  # 不含 (9, 10)
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "blocking facility not at front" in vr.detail


def test_validate_port_exposure_schema_err_unknown_direction():
    cert_payload = _make_port_exposure_cert(port_direction="invalid")
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={(9, 10): ("refinery", 0)})
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "schema_err"


def test_validate_port_exposure_cert_literal_multiset_mismatch():
    """GPT pro round 2 P0-2 反例: cert blocker pose=p013 但 cut.literals 写
    p014 (同 group 不同 pose). validator 必须 unsound — 不准拿 p013 证剪 p014.
    """
    # cert references blocker pose "p3"
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(9, 10),
        blocking_group="refinery", blocking_slot=0, blocking_pose_id="p3",
    )
    # but cut.literals 错放 "p99" (同 group 不同 pose)
    cut = Cut(
        cut_id="F3-mismatch",
        family="port_exposure",
        literals=(
            CutLiteral(slot_ref=AnonymousSlotRef("crusher", 0), pose_id="p7"),
            CutLiteral(slot_ref=AnonymousSlotRef("refinery", 0), pose_id="p99"),  # ✗
        ),
        geometric_payload=None,
        scope=_scope_for_state(_make_state()),
        cert=OracleCert(
            cert_kind="port_exposure_blocked",
            cert_payload=cert_payload,
            cert_hash="ch",
        ),
        family_version="v1.0", validator_version="v1.0",
    )
    state = _make_state(
        cell_owner={(9, 10): ("refinery", 0)},
        refinery_poses=["p3"],  # binding step 3b 需 selected_poses[0]==p3
    )
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "literals multiset mismatch" in (vr.detail or "")


def test_validate_port_exposure_slot_anonymity_in_binding():
    """slot_index 不参与 binding — (refinery, slot=0, p3) 跟 (refinery, slot=5, p3)
    在 multiset 比较里等价 (state_machine_v2 §5 slot anonymity).
    """
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(9, 10),
        blocking_group="refinery", blocking_slot=0, blocking_pose_id="p3",
    )
    # cut.literal blocking slot 写 5, cert blocking slot 写 0 — 仍应 ok
    cut = Cut(
        cut_id="F3-slot-anon",
        family="port_exposure",
        literals=(
            CutLiteral(slot_ref=AnonymousSlotRef("crusher", 2), pose_id="p7"),
            CutLiteral(slot_ref=AnonymousSlotRef("refinery", 5), pose_id="p3"),
        ),
        geometric_payload=None,
        scope=_scope_for_state(_make_state()),
        cert=OracleCert(
            cert_kind="port_exposure_blocked",
            cert_payload=cert_payload,
            cert_hash="ch",
        ),
        family_version="v1.0", validator_version="v1.0",
    )
    state = _make_state(cell_owner={(9, 10): ("refinery", 0)}, refinery_poses=["p3"])
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


def test_validate_port_exposure_one_literal_schema_err_python_O_safe():
    """GPT pro round 2 P0-2 反例: F3 spec §4 要求 ≥ 2 literal (facility + blocking).
    Validator 必须 explicit fail-closed 不靠 assert — `python -O` 下 assert 失效后
    一元 cut 也要走 schema_err (不是 ok). 这条 regression 在 -O 下也必跑.
    """
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(9, 10),
    )
    # Build cut with ONLY 1 literal (post_init 允许 ≥ 1, validator 必拒 < 2)
    cut = Cut(
        cut_id="F3-one-literal",
        family="port_exposure",
        literals=(CutLiteral(slot_ref=AnonymousSlotRef("crusher", 0), pose_id="p7"),),
        geometric_payload=None,
        scope=_scope_for_state(_make_state()),
        cert=OracleCert(
            cert_kind="port_exposure_blocked",
            cert_payload=cert_payload,
            cert_hash="ch",
        ),
        family_version="v1.0", validator_version="v1.0",
    )
    state = _make_state(cell_owner={(9, 10): ("refinery", 0)})
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "schema_err", f"-O 模式 1-literal 漏走 schema_err (got {vr.kind})"
    assert "cut.literals 必 ≥ 2" in (vr.detail or "")


# ============================================================================
# F3 evaluate
# ============================================================================

def test_port_exposure_oracle_stub_is_fail_closed():
    assert generate_port_exposure_cuts(_make_state(), master_solution={"unused": True}) == []


def test_validate_port_exposure_schema_err_bool_blocking_slot():
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(9, 10), blocking_slot=True
    )
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={(9, 10): ("refinery", 0)}, refinery_poses=["p3"])

    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "schema_err"
    assert "blocking_facility[1]" in vr.detail
