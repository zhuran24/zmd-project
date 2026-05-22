"""Phase 1.1 P1.6 test — Family 2 cutset (validator + stub oracle).

Coverage:
- validate_cutset: ok / unsound (cut_size mismatch / partition not disjoint /
  witness fail) / schema_err (malformed cert)
- evaluate_geometric_cutset: True when violated / False when not
- generate_cutset_cuts stub: returns []
- helpers: _cross_partition_edges + _free_cells

Phase 1.5+ extends: patch_routing_core integration + max-flow LP witness check.
"""
from __future__ import annotations

import base64
import json

import pytest

from src.cuts.families.cutset import (
    _cross_partition_edges,
    _decode_bitset,
    _free_cells,
    evaluate_geometric_cutset,
    validate_cutset,
)
from src.cuts.lifecycle import (
    BState,
    Cut,
    CutScope,
    GHOST_AGNOSTIC,
    GroupState,
    OracleCert,
)
from src.cuts.oracles.cutset_oracle import generate_cutset_cuts


def _encode_bitset(cells: set, grid_size: int = 70) -> str:
    arr = bytearray(grid_size * grid_size // 8 + 1)
    for x, y in cells:
        idx = x * grid_size + y
        arr[idx // 8] |= 1 << (idx % 8)
    return base64.b64encode(bytes(arr)).decode("ascii")


def _make_state(ghost_cells: set = None) -> BState:
    return BState(
        groups={"g": GroupState("g", demand=1, pose_domain=frozenset())},
        ghost_cells=frozenset(ghost_cells or set()),
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"cutset_v1"}),
    )


def _make_cutset_cut(
    side_a: set,
    side_b: set,
    cut_size: int,
    commodity_demand: int,
) -> Cut:
    cert_dict = {
        "side_a_bitset_b64": _encode_bitset(side_a),
        "side_b_bitset_b64": _encode_bitset(side_b),
        "cut_edges": [],  # not used by validator
        "cut_size": cut_size,
        "commodity_demand": commodity_demand,
        "gap": commodity_demand - cut_size,
        "contributing_commodities": ["c1"],
        "menger_witness_kind": "max_flow_LP",
        "witness_blob_b64": None,
    }
    payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    scope = CutScope(
        ghost_rect_id=GHOST_AGNOSTIC,
        blocked_cells_hash="h",
        exterior_blocks_hash="h",
        source_digest="poc_source_digest",
        artifact_hashes={"canonical_rules.json": "h1"},
        oracle_abstraction_version="cutset_v1",
    )
    cert = OracleCert(cert_kind="menger_min_cut", cert_payload=payload, cert_hash="ch")
    return Cut(
        cut_id="F2-test",
        family="cutset",
        literals=None,
        geometric_payload=payload,
        scope=scope,
        cert=cert,
        family_version="v1.0",
        validator_version="v1.0",
    )


# ============================================================================
# Helpers
# ============================================================================

def test_cross_partition_edges_basic():
    """A={(0,0),(1,0)} B={(0,1),(1,1)} → edges (0,0)-(0,1) and (1,0)-(1,1)."""
    side_a = frozenset({(0, 0), (1, 0)})
    side_b = frozenset({(0, 1), (1, 1)})
    free = frozenset({(0, 0), (1, 0), (0, 1), (1, 1)})
    edges = _cross_partition_edges(side_a, side_b, free)
    assert len(edges) == 2
    assert ((0, 0), (0, 1)) in edges
    assert ((1, 0), (1, 1)) in edges


def test_cross_partition_edges_skip_non_free():
    """非 free 的 cell 不算 edge."""
    side_a = frozenset({(0, 0)})
    side_b = frozenset({(0, 1)})
    free = frozenset({(0, 0)})  # (0,1) 不在 free
    edges = _cross_partition_edges(side_a, side_b, free)
    assert len(edges) == 0


def test_free_cells_excludes_ghost_and_cell_owner():
    state = BState(
        groups={"g": GroupState("g", demand=1, pose_domain=frozenset())},
        ghost_cells=frozenset({(5, 5)}),
        cell_owner={(0, 0): ("g", 0)},
    )
    free = _free_cells(state, grid_size=10)
    assert (5, 5) not in free
    assert (0, 0) not in free
    assert (1, 1) in free


# ============================================================================
# Validator
# ============================================================================

def test_validate_cutset_ok():
    """A={(0,0)} B={(0,1)} free 全, demand=2 cut_size=1 → unsound (demand=2 ≤ cut=1? no, 2>1 OK)."""
    # 2x2 graph minus 4 cells outside.
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=2)
    state = _make_state()
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "ok"


def test_validate_cutset_unsound_partition_not_disjoint():
    side_a = {(0, 0)}
    side_b = {(0, 0), (0, 1)}  # 重叠 (0,0)
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=2)
    state = _make_state()
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "disjoint" in vr.detail


def test_validate_cutset_unsound_cut_size_mismatch():
    """cert.cut_size 谎报."""
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    cut = _make_cutset_cut(side_a, side_b, cut_size=999, commodity_demand=1000)
    state = _make_state()
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "cut_size mismatch" in vr.detail


def test_validate_cutset_unsound_witness_fail():
    """demand ≤ cut_size → 没 Menger violation."""
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=1)
    state = _make_state()
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "witness fail" in vr.detail


def test_validate_cutset_schema_err_on_malformed():
    """Malformed cert → schema_err."""
    scope = CutScope(
        ghost_rect_id=GHOST_AGNOSTIC,
        blocked_cells_hash="h",
        exterior_blocks_hash="h",
        source_digest="poc_source_digest",
        artifact_hashes={},
        oracle_abstraction_version="cutset_v1",
    )
    cert = OracleCert(cert_kind="menger_min_cut", cert_payload=b"{}", cert_hash="ch")
    cut = Cut(
        cut_id="F2-malformed",
        family="cutset",
        literals=None,
        geometric_payload=b"{}",  # 缺 side_a_bitset_b64 等 fields
        scope=scope,
        cert=cert,
        family_version="v1.0",
        validator_version="v1.0",
    )
    vr = validate_cutset(cut, _make_state(), canonical_rules={})
    assert vr.kind == "schema_err"


# ============================================================================
# evaluate_geometric
# ============================================================================

def test_evaluate_geometric_violation_true():
    """demand 100 > cut_size 1 → violate."""
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=100)
    state = _make_state()
    assert evaluate_geometric_cutset(cut, state) is True


def test_evaluate_geometric_no_violation_false():
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=0)
    state = _make_state()
    assert evaluate_geometric_cutset(cut, state) is False


# ============================================================================
# Oracle stub
# ============================================================================

def test_generate_cutset_cuts_stub_returns_empty():
    state = _make_state()
    cuts = generate_cutset_cuts(state, master_solution=None)
    assert cuts == []
