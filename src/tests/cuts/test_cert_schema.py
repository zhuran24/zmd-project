from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Mapping

import pytest

from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    AnonymousSlotRef,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    GroupState,
    OracleCert,
    canonical_bytes_for_cert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_source_digest,
)
from src.cuts.replay import replay_cut
from src.cuts.store import CutStore
from src.models.cut_manager import BendersCut


ORACLE_BY_FAMILY: Mapping[str, str] = {
    "region_capacity": "region_capacity_v1",
    "cutset": "cutset_v1",
    "port_exposure": "port_exposure_v1",
    "component_reach": "component_reach_v1",
    "pattern_nogood": "pattern_nogood_v1",
    "shape_packing_hall": "shape_packing_hall_v1",
    "power_hitting_set": "power_cover_v1",
    "power_grid_reach": "power_grid_reach_v1",
    "density_envelope": "density_envelope_v1",
}


LITERAL_FAMILIES = frozenset({
    "port_exposure",
    "pattern_nogood",
    "power_hitting_set",
})


def _base_state() -> BState:
    return BState(
        groups={
            "g": GroupState("g", demand=2, pose_domain=frozenset({"p"})),
            "h": GroupState("h", demand=2, pose_domain=frozenset({"q"})),
        },
        canonical_rules={},
        available_oracle_versions=frozenset(ORACLE_BY_FAMILY.values()),
    )


def _scope_for_state(state: BState, family: str) -> CutScope:
    return CutScope(
        ghost_rect_id=GHOST_AGNOSTIC,
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest=compute_source_digest(state),
        oracle_abstraction_version=ORACLE_BY_FAMILY[family],
        artifact_hashes=dict(state.artifact_hashes),
    )


def _minimal_payload(family: str) -> Dict[str, Any]:
    payload_by_family: Dict[str, Dict[str, Any]] = {
        "region_capacity": {
            "cert_kind": "region_capacity_combinatorial",
            "region_kind": "left_or_bottom_union",
            "region_cells_bitset_b64": "",
            "cap_R": 0,
            "demand_R": 1,
            "gap": 1,
            "contributing_groups": [],
            "cells_per_pose": {},
            "lp_dual_ray_b64": None,
            "lp_dual_objective": None,
        },
        "cutset": {
            "cert_kind": "menger_min_cut",
            "side_a_bitset_b64": "",
            "side_b_bitset_b64": "",
            "cut_edges": [],
            "cut_size": 0,
            "commodity_demand": 1,
            "contributing_commodities": ["c1"],
        },
        "port_exposure": {
            "cert_kind": "port_exposure_blocked",
            "facility_group": "g",
            "facility_pose_id": "p",
            "port_cell": [0, 0],
            "port_direction": "N",
            "front_cell": [0, 0],
            "blocking_facility": ["h", 0, "q"],
            "active_port_witness_b64": None,
        },
        "component_reach": {
            "cert_kind": "bfs_disconnect_witness",
            "commodity_id": "c1",
            "src_cell": [0, 0],
            "sink_cell": [0, 1],
            "src_component_bitset_b64": "",
            "sink_component_bitset_b64": "",
            "separator_cells": [],
            "blocking_facilities": [],
        },
        "pattern_nogood": {
            "cert_kind": "bounded_deletion_core",
            "sub_problem_oracle_name": "stub",
            "sub_problem_oracle_version": "v1",
            "forbidden_pose_pattern": [["g", 0, "p"]],
            "core_minimization": {
                "size_before": 1,
                "size_after": 1,
                "calls": 0,
                "stopped_reason": "INFEASIBLE_VERIFIED",
                "is_verified_infeasible": True,
            },
        },
        "shape_packing_hall": {
            "cert_kind": "hall_interval_witness",
            "region_kind": "left_baseline",
            "region_total_length": 70,
            "partition_lens": [1],
            "partition_offsets": [0],
            "pose_length": 2,
            "pose_shape_canonical": "1x2_rigid",
            "max_packable": [0],
            "total_packable": 0,
            "contributing_group": "g",
            "region_demand": 1,
            "group_demand": 2,
            "ghost_rect_repr": [0, 0, 1, 1],
            "exterior_blocks_digest": "",
        },
        "power_hitting_set": {
            "cert_kind": "power_cover_emptyset_ghost",
            "facility_group": "g",
            "facility_pose_id": "p",
            "facility_cells": [[0, 0]],
            "pole_radius": 1.0,
            "pole_shape_canonical": "2x2_rigid",
            "ghost_rect_repr": [0, 0, 1, 1],
            "exterior_blocks_digest": "",
        },
        "power_grid_reach": {
            "cert_kind": "power_pole_bfs_disconnect_ghost",
            "facility_group": "g",
            "facility_pose_id": "p",
            "facility_cells": [[0, 0]],
            "pole_jump_radius": 1.0,
            "pole_shape_canonical": "2x2_rigid",
            "protocol_core_cell": [0, 0],
            "ghost_rect_repr": [0, 0, 1, 1],
            "exterior_blocks_digest": "",
        },
        "density_envelope": {
            "cert_kind": "density_envelope_v1",
            "witness_kind": "area_capacity_overflow",
            "window_rect": [0, 0, 1, 1],
            "group_id": "g",
            "max_allowed_area": 0,
            "oracle_assignment_witness": [["g", "p"]],
            "ghost_rect_repr": [0, 0, 1, 1],
        },
    }
    return dict(payload_by_family[family])


def _cut_for_payload(family: str, payload_dict: Mapping[str, Any]) -> Cut:
    state = _base_state()
    payload = canonical_bytes_for_cert(dict(payload_dict))
    cert_hash = hashlib.sha256(payload).hexdigest()
    cert = OracleCert(
        cert_kind=str(payload_dict.get("cert_kind", "")),
        cert_payload=payload,
        cert_hash=cert_hash,
    )
    literals = (
        CutLiteral(AnonymousSlotRef("g", 0), "p"),
        CutLiteral(AnonymousSlotRef("h", 0), "q"),
    )
    return Cut(
        cut_id=f"schema-{family}",
        family=family,
        literals=literals if family in LITERAL_FAMILIES else None,
        geometric_payload=None if family in LITERAL_FAMILIES else payload,
        scope=_scope_for_state(state, family),
        cert=cert,
        family_version="v1",
        validator_version="v1",
        oracle_name=ORACLE_BY_FAMILY[family],
        oracle_cert_hash=cert_hash,
    )


def _replay_and_quarantine(cut: Cut) -> CutStore:
    state = _base_state()
    store = CutStore()
    store.add_cut(cut)

    decision = replay_cut(cut, state, store, canonical_rules={})

    assert decision == "QUARANTINE"
    assert not store.is_active(cut.cut_id)
    assert cut.cut_id in store.quarantined
    assert store.quarantined[cut.cut_id].reason_code == "validate_schema_err"
    return store


@pytest.mark.parametrize("family", sorted(ORACLE_BY_FAMILY))
def test_cert_payload_unknown_field_quarantines_without_attach(family: str) -> None:
    payload = _minimal_payload(family)
    payload["forged_future_proof_hint"] = "accept-me"
    cut = _cut_for_payload(family, payload)

    store = _replay_and_quarantine(cut)

    assert "unknown field" in store.quarantined[cut.cut_id].detail


@pytest.mark.parametrize(
    ("family", "wrong_kind"),
    [
        ("cutset", "bfs_disconnect_witness"),
        ("port_exposure", "menger_min_cut"),
        ("component_reach", "port_exposure_blocked"),
    ],
)
def test_f2_f3_f4_cert_kind_mismatch_quarantines(
    family: str,
    wrong_kind: str,
) -> None:
    payload = _minimal_payload(family)
    payload["cert_kind"] = wrong_kind
    cut = _cut_for_payload(family, payload)

    store = _replay_and_quarantine(cut)

    assert "cert_kind" in store.quarantined[cut.cut_id].detail


def test_benderscut_from_dict_rejects_unknown_proof_bearing_top_level_field() -> None:
    payload = {
        "schema_version": 1,
        "cut_type": "routing_dead_end",
        "conflict_set": {"x": 1},
        "iteration": 0,
        "metadata": {},
        "source_mode": "certified_exact",
        "exact_safe": True,
        "artifact_hashes": {},
        "proof_stage": None,
        "binding_exhausted": None,
        "routing_exhausted": None,
        "proof_summary": {},
        "created_at": None,
        "epsilon_stage": None,
        "condition_set": {},
        "forged_top_level_proof_hint": True,
    }

    with pytest.raises(ValueError, match="unknown top-level"):
        BendersCut.from_dict(payload)


def test_benderscut_from_dict_keeps_non_proof_unknown_field_behavior() -> None:
    payload = {
        "cut_type": "exploratory_note",
        "conflict_set": {"x": "kept-as-before"},
        "iteration": 0,
        "source_mode": "exploratory",
        "exact_safe": False,
        "forged_top_level_proof_hint": True,
    }

    cut = BendersCut.from_dict(payload)

    assert cut.cut_type == "exploratory_note"
