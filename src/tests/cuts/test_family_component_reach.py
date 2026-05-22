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
from src.cuts.families.cutset import _free_cells
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
    commodity_id: str = None,
    state: BState = None,
) -> Cut:
    """commodity_id 默认 None (Phase 1.1 v1.1 minimum-viable spatial-only).
    GPT pro round 2 P0-4: cert 不准 carry 未验证的 commodity_id field —
    Phase 1.5+ 加 commodity registry verifier 后才允许.

    cert.src_component / sink_component bitset 默认从 state recomputed BFS 算
    (GPT pro round 2 cert 完整性 — cert 必 == BFS, validator 验严等).
    若 src_comp/sink_comp 显式传, 用传入值 (negative test 用).
    """
    if src_comp is None:
        if state is not None:
            free = _free_cells(state)
            src_comp = _bfs_component(src_cell, free) if src_cell in free else {src_cell}
        else:
            src_comp = {src_cell}
    if sink_comp is None:
        if state is not None:
            free = _free_cells(state)
            sink_comp = _bfs_component(sink_cell, free) if sink_cell in free else {sink_cell}
        else:
            sink_comp = {sink_cell}
    cert_dict = {
        "src_cell": list(src_cell),
        "sink_cell": list(sink_cell),
        "src_component_bitset_b64": _encode_bitset(src_comp),
        "sink_component_bitset_b64": _encode_bitset(sink_comp),
        "separator_cells": [],
        "blocking_facilities": [],
        "witness_path_attempt": None,
    }
    if commodity_id is not None:
        cert_dict["commodity_id"] = commodity_id
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
    """src + sink in disjoint components on disconnected free_cells.

    Step D 后: cert.src/sink_component 必 == BFS 重算 — 用 state.recompute 自动算.
    """
    # ghost 占 row x=35 (除 (0,35) (1,35)) → 70x70 grid split into top half (0-34) + bottom half (36-69)
    ghost = {(35, y) for y in range(70)}
    state = _make_state(ghost_cells=ghost)

    src_cell = (0, 0)
    sink_cell = (69, 0)
    cut = _make_component_reach_cut(
        src_cell=src_cell,
        sink_cell=sink_cell,
        state=state,  # auto-recompute BFS components for cert
    )
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


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
    """Cert claims disconnect (src_comp={src_cell}, sink_comp={sink_cell})
    但 current free_cells 全连通 → cert mismatch (under-claim src_comp) fire 先
    (step 4 cert完整性 catch). Sound violation 仍 detected, detail 不同 wording.
    """
    cut = _make_component_reach_cut(src_cell=(0, 0), sink_cell=(0, 1))
    state = _make_state()  # no blocks → all connected
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    # Either old "reconnect" detail OR new "cert mismatch" detail OK — 都是 sound violation
    assert "reconnect" in vr.detail or "reachable" in vr.detail \
        or "cert mismatch" in vr.detail, f"unexpected detail: {vr.detail}"


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
# GPT pro round 2 P0-4 — cert 完整性 (src_component == recomputed BFS)
# ============================================================================

def test_validator_unsound_src_component_mismatch_extra():
    """attacker cert.src_component over-claim (含 ghost cell 不在真 BFS).
    validator 必拒.

    fake_src_comp = top half BFS + (35, 5) (ghost cell, not in BFS). 不跟
    sink_comp (bottom half) 重叠 — 不会先 fire disjoint check.
    """
    ghost = {(35, y) for y in range(70)}
    state = _make_state(ghost_cells=ghost)
    src_cell = (0, 0)
    sink_cell = (69, 0)
    # cert over-claim: 真 BFS = top half (35*70=2450 cells), fake 加 (35, 5)
    # 这 cell 是 ghost row, BFS 不含 — 也不在 sink_comp (bottom half) 内
    fake_src_comp = {(x, y) for x in range(35) for y in range(70)} | {(35, 5)}
    cut = _make_component_reach_cut(
        src_cell=src_cell,
        sink_cell=sink_cell,
        src_comp=fake_src_comp,
        state=state,  # sink_comp 用 state recompute
    )
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "src_component cert mismatch" in vr.detail


def test_validator_unsound_sink_component_mismatch_missing():
    """cert.sink_component under-claim (漏 cell) → unsound."""
    ghost = {(35, y) for y in range(70)}
    state = _make_state(ghost_cells=ghost)
    src_cell = (0, 0)
    sink_cell = (69, 0)
    # bottom half BFS 应 carry 35*70=2450 cells, cert 只 carry 1
    cut = _make_component_reach_cut(
        src_cell=src_cell,
        sink_cell=sink_cell,
        sink_comp={sink_cell},  # under-claim
        state=state,  # src_comp 用 state recompute
    )
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "sink_component cert mismatch" in vr.detail


def test_validator_unsound_separator_cell_in_free():
    """Gemini round 33 High fix: cert.separator_cells 必全在 cell_owner ∪ ghost
    (spec 04_component_reach.md line 148). attacker 放 free cell 进 separator
    → unsound.
    """
    ghost = {(35, y) for y in range(70)}
    state = _make_state(ghost_cells=ghost)
    src_cell = (0, 0)
    sink_cell = (69, 0)
    # 构 sound cut + 加 attacker 假 separator_cells (含 free cell (1, 1))
    cut_base = _make_component_reach_cut(
        src_cell=src_cell, sink_cell=sink_cell, state=state,
    )
    # 重写 cert 加 fake separator
    cert_dict = json.loads(cut_base.geometric_payload)
    cert_dict["separator_cells"] = [[1, 1]]  # (1,1) is FREE (not ghost not owned)
    payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    cut = Cut(
        cut_id="F4-sep-test",
        family="component_reach",
        literals=None,
        geometric_payload=payload,
        scope=cut_base.scope,
        cert=OracleCert(cert_kind="x", cert_payload=payload, cert_hash="ch"),
        family_version="v1.1",
        validator_version="v1.1",
    )
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "separator cell" in vr.detail
    assert "free_cells" in vr.detail


def test_validator_ok_separator_in_ghost_or_owner():
    """Sound case: separator_cells 全在 ghost 内 → validator OK."""
    ghost = {(35, y) for y in range(70)}
    state = _make_state(ghost_cells=ghost)
    src_cell = (0, 0)
    sink_cell = (69, 0)
    cut_base = _make_component_reach_cut(
        src_cell=src_cell, sink_cell=sink_cell, state=state,
    )
    cert_dict = json.loads(cut_base.geometric_payload)
    cert_dict["separator_cells"] = [[35, 0], [35, 5]]  # 都在 ghost row
    payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    cut = Cut(
        cut_id="F4-sep-ok",
        family="component_reach",
        literals=None,
        geometric_payload=payload,
        scope=cut_base.scope,
        cert=OracleCert(cert_kind="x", cert_payload=payload, cert_hash="ch"),
        family_version="v1.1",
        validator_version="v1.1",
    )
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


def test_validator_schema_err_commodity_id_not_yet_supported():
    """GPT pro round 2 P0-4: cert.commodity_id 在 Phase 1.5+ commodity registry
    verifier 落地前不准 carry (fail-closed, 防 attacker 塞 fake commodity).
    """
    ghost = {(35, y) for y in range(70)}
    state = _make_state(ghost_cells=ghost)
    cut = _make_component_reach_cut(
        src_cell=(0, 0), sink_cell=(69, 0),
        commodity_id="fake_commodity_xyz",  # attacker 塞
        state=state,
    )
    vr = validate_component_reach(cut, state, canonical_rules={})
    assert vr.kind == "schema_err", f"got {vr.kind}: {vr.detail}"
    assert "commodity_id" in vr.detail


# ============================================================================
# Oracle stub
# ============================================================================

def test_generate_component_reach_cuts_stub_returns_empty():
    state = _make_state()
    cuts = generate_component_reach_cuts(state, master_solution=None)
    assert cuts == []
