"""Phase 1.1 P1.8 test — Family 4 component_reach (geometric, BFS connectivity).

Coverage:
- validate_component_reach: ok / unsound (component 重叠 / src not in comp /
  sink not in comp / src not in free_cells / sink reachable via reconnect)
- evaluate_geometric_component_reach: True (disconnect) / False (reconnect)
- BFS helper: 4-conn / blocked / non-free start
- Oracle stub: returns []
"""
from __future__ import annotations

import base64
import json

from src.cuts.families.component_reach import (
    _bfs_component,
    evaluate_geometric_component_reach,
    validate_component_reach,
)
from src.cuts.lifecycle import (
    BState,
    Cut,
    CutScope,
    GHOST_AGNOSTIC,
    GroupState,
    OracleCert,
)
from src.cuts.oracles.component_reach_oracle import generate_component_reach_cuts


def _encode_bitset(cells: set, grid_size: int = 70) -> str:
    arr = bytearray(grid_size * grid_size // 8 + 1)
    for x, y in cells:
        idx = x * grid_size + y
        arr[idx // 8] |= 1 << (idx % 8)
    return base64.b64encode(bytes(arr)).decode("ascii")


def _make_state(
    *,
    ghost_cells: set = None,
    cell_owner: dict = None,
) -> BState:
    return BState(
        groups={"g": GroupState("g", demand=1, pose_domain=frozenset())},
        ghost_cells=frozenset(ghost_cells or set()),
        cell_owner=cell_owner or {},
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"component_reach_v1"}),
    )


def _make_component_reach_cut(
    *,
    src_cell: tuple = (0, 0),
    sink_cell: tuple = (0, 69),
    src_comp: set = None,
    sink_comp: set = None,
) -> Cut:
    if src_comp is None:
        src_comp = {src_cell}
    if sink_comp is None:
        sink_comp = {sink_cell}
    cert_dict = {
        "src_cell": list(src_cell),
        "sink_cell": list(sink_cell),
        "commodity_id": "c1",
        "src_component_bitset_b64": _encode_bitset(src_comp),
        "sink_component_bitset_b64": _encode_bitset(sink_comp),
        "separator_cells": [],
        "blocking_facilities": [],
        "witness_path_attempt": None,
    }
    payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    scope = CutScope(
        ghost_rect_id=GHOST_AGNOSTIC,
        blocked_cells_hash="h",
        exterior_blocks_hash="h",
        source_digest="poc_source_digest",
        artifact_hashes={"canonical_rules.json": "h1"},
        oracle_abstraction_version="component_reach_v1",
    )
    cert = OracleCert(
        cert_kind="bfs_disconnect_witness",
        cert_payload=payload,
        cert_hash="ch",
    )
    return Cut(
        cut_id="F4-test",
        family="component_reach",
        literals=None,
        geometric_payload=payload,
        scope=scope,
        cert=cert,
        family_version="v1.1",
        validator_version="v1.1",
    )


# ============================================================================
# BFS helper
# ============================================================================

def test_bfs_component_basic_reach():
    """3x3 grid all free → BFS reaches all."""
    free = frozenset((x, y) for x in range(3) for y in range(3))
    comp = _bfs_component((0, 0), free)
    assert comp == set(free)


def test_bfs_component_blocked_split():
    """grid with vertical block → 2 components."""
    # grid 3x3 minus (1,0),(1,1),(1,2) (middle column blocked)
    free = frozenset(
        (x, y) for x in range(3) for y in range(3) if x != 1
    )
    comp_a = _bfs_component((0, 0), free)
    assert comp_a == {(0, 0), (0, 1), (0, 2)}
    comp_b = _bfs_component((2, 0), free)
    assert comp_b == {(2, 0), (2, 1), (2, 2)}


def test_bfs_component_start_not_free():
    free = frozenset({(0, 0), (1, 0)})
    comp = _bfs_component((99, 99), free)
    assert comp == set()


# ============================================================================
# Validator
# ============================================================================

def test_validator_ok_when_disconnected():
    """src + sink in disjoint components on disconnected free_cells."""
    # ghost 占 row x=35 (除 (0,35) (1,35)) → 70x70 grid split into top half (0-34) + bottom half (36-69)
    # 实际更简单: ghost 占完整 row x=35 → 完全 split
    ghost = {(35, y) for y in range(70)}
    state = _make_state(ghost_cells=ghost)

    src_cell = (0, 0)
    sink_cell = (69, 0)
    # Cert bitset 应 carry top/bottom 半 components — 简单测 just 2 endpoints
    cut = _make_component_reach_cut(
        src_cell=src_cell,
        sink_cell=sink_cell,
        src_comp={src_cell},  # 简化 — validator only needs membership
        sink_comp={sink_cell},
    )
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "ok"


def test_validator_unsound_components_overlap():
    cut = _make_component_reach_cut(
        src_cell=(0, 0),
        sink_cell=(0, 1),
        src_comp={(0, 0), (0, 1)},  # 同一个 component
        sink_comp={(0, 0), (0, 1)},
    )
    state = _make_state()
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "重叠" in vr.detail


def test_validator_unsound_src_not_in_component():
    cut = _make_component_reach_cut(
        src_cell=(5, 5),
        sink_cell=(0, 1),
        src_comp={(60, 60)},  # 不含 src (5,5)
        sink_comp={(0, 1)},
    )
    state = _make_state()
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "src_cell" in vr.detail


def test_validator_unsound_when_reconnected():
    """Cert claims disconnect, but current free_cells reconnect → unsound."""
    cut = _make_component_reach_cut(src_cell=(0, 0), sink_cell=(0, 1))
    state = _make_state()  # no blocks → all connected
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "reconnect" in vr.detail or "reachable" in vr.detail


def test_validator_unsound_src_no_longer_free():
    cut = _make_component_reach_cut(src_cell=(5, 5), sink_cell=(50, 50))
    # ghost 包 src
    state = _make_state(ghost_cells={(5, 5)})
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "src_cell" in vr.detail


# ============================================================================
# evaluate_geometric
# ============================================================================

def test_evaluate_disconnected_true():
    ghost = {(35, y) for y in range(70)}
    state = _make_state(ghost_cells=ghost)
    cut = _make_component_reach_cut(src_cell=(0, 0), sink_cell=(69, 0))
    assert evaluate_geometric_component_reach(cut, state) is True


def test_evaluate_reconnected_false():
    state = _make_state()
    cut = _make_component_reach_cut(src_cell=(0, 0), sink_cell=(0, 1))
    assert evaluate_geometric_component_reach(cut, state) is False


def test_evaluate_endpoint_blocked_false():
    """src no longer free → False (cut should be quarantined separately)."""
    state = _make_state(ghost_cells={(0, 0)})
    cut = _make_component_reach_cut(src_cell=(0, 0), sink_cell=(0, 1))
    assert evaluate_geometric_component_reach(cut, state) is False


# ============================================================================
# Oracle stub
# ============================================================================

def test_generate_component_reach_cuts_stub_returns_empty():
    state = _make_state()
    cuts = generate_component_reach_cuts(state, master_solution=None)
    assert cuts == []
