"""Phase 1.1 P1.6 test — Family 2 cutset (validator + stub oracle).

Coverage:
- validate_cutset: ok / unsound (cut_size mismatch / partition not disjoint /
  witness fail / non-free cell in partition / partition not enclosed / cut_edges
  set mismatch) / schema_err (malformed cert)
- evaluate_geometric_cutset: True when violated / False when not
- generate_cutset_cuts stub: returns []
- helpers: _cross_partition_edges + _free_cells + _has_patch_escape

GPT pro round 2 P0-3 fix: F2 spec §1a partition (A, B) of V 必含全 graph node,
否则流可绕过 patch → cut 假证. validator 加 partition enclosure + cut_edges
set 完整性 check.

Phase 1.5+ extends: patch_routing_core integration + max-flow LP witness check.
"""
from __future__ import annotations

import base64
import json


from src.cuts.families.cutset import (
    _cross_partition_edges,
    _free_cells,
    _has_patch_escape,
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


def _make_enclosed_state(
    patch: set, grid_size: int = 70, commodity_demand: int = 2,
    route_src: tuple = (0, 0), route_sink: tuple = (0, 1),
) -> BState:
    """让 free_cells == patch — ghost 覆盖 patch 外的全部 cell. Test 用 enclosed
    partition (spec §1a 严格要求, GPT pro round 2 P0-3 fix).

    GPT pro v4 P0 fix: commodity_demands registry 必 inject.
    GPT pro v5 P0-1 fix: commodity_routes registry 必 inject + route 必跨 partition
    (default src=(0,0)∈side_a, sink=(0,1)∈side_b).
    """
    all_cells = {(x, y) for x in range(grid_size) for y in range(grid_size)}
    ghost = all_cells - patch
    return BState(
        groups={"g": GroupState("g", demand=1, pose_domain=frozenset())},
        ghost_cells=frozenset(ghost),
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"cutset_v1"}),
        commodity_demands={"c1": commodity_demand},
        commodity_routes={"c1": {"src": route_src, "sink": route_sink}},
    )


def _make_cutset_cut(
    side_a: set,
    side_b: set,
    cut_size: int,
    commodity_demand: int,
    cut_edges: list = None,
) -> Cut:
    """Build F2 cut with cert. cut_edges 默认从 partition 自动推 (4-邻接相邻 pair)."""
    if cut_edges is None:
        cut_edges = []
        for a in side_a:
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                b = (a[0] + dx, a[1] + dy)
                if b in side_b:
                    e = [list(a), list(b)] if a <= b else [list(b), list(a)]
                    cut_edges.append(e)
    cert_dict = {
        "cert_kind": "menger_min_cut",
        "side_a_bitset_b64": _encode_bitset(side_a),
        "side_b_bitset_b64": _encode_bitset(side_b),
        "cut_edges": cut_edges,
        "cut_size": cut_size,
        "commodity_demand": commodity_demand,
        "contributing_commodities": ["c1"],
    }
    payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    scope = CutScope(
        ghost_rect_id="ghost_v1",
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


def test_free_cells_excludes_ghost_exterior_and_cell_owner():
    state = BState(
        groups={"g": GroupState("g", demand=1, pose_domain=frozenset())},
        ghost_cells=frozenset({(5, 5)}),
        exterior_blocks=frozenset({(2, 2)}),
        cell_owner={(0, 0): ("g", 0)},
    )
    free = _free_cells(state, grid_size=10)
    assert (5, 5) not in free
    assert (2, 2) not in free
    assert (0, 0) not in free
    assert (1, 1) in free


def test_has_patch_escape_detects_outside_free():
    """patch={(0,0)} + outside free (1,0) adjacent → escape."""
    patch = frozenset({(0, 0)})
    free_cells = frozenset({(0, 0), (1, 0)})
    assert _has_patch_escape(patch, free_cells) is True


def test_has_patch_escape_enclosed_no_escape():
    """patch == free_cells → no outside free → no escape."""
    patch = frozenset({(0, 0), (0, 1)})
    free_cells = frozenset({(0, 0), (0, 1)})
    assert _has_patch_escape(patch, free_cells) is False


# ============================================================================
# Validator
# ============================================================================

def test_validate_cutset_ok():
    """2x2 enclosed patch, partition disjoint, demand=2 > cut_size=2 — Menger 不充分,
    实际此 case witness fail (demand=2 ≤ cut=2). 我们要构造 demand > cut 的
    enclosed case.
    """
    # 1x2 enclosed patch: free={(0,0),(0,1)}. Partition A={(0,0)} B={(0,1)},
    # cut_edges=[(0,0)-(0,1)] cut_size=1. demand=2 > cut_size=1 ✓
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    state = _make_enclosed_state(patch={(0, 0), (0, 1)})
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=2)
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


def test_validate_cutset_unsound_partition_not_disjoint():
    side_a = {(0, 0)}
    side_b = {(0, 0), (0, 1)}  # 重叠 (0,0)
    state = _make_enclosed_state(patch={(0, 0), (0, 1)})
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=2)
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "disjoint" in vr.detail


def test_validate_cutset_unsound_cut_size_mismatch():
    """cert.cut_size 谎报."""
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    state = _make_enclosed_state(patch={(0, 0), (0, 1)})
    # cut_edges 也跟着改 cut_size=999 (canonical mismatch 先 fire)
    cut = _make_cutset_cut(
        side_a, side_b, cut_size=999, commodity_demand=1000,
        cut_edges=[[list((0, 0)), list((0, 1))]] * 999,  # fake list, 让 size=999
    )
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "cut_size mismatch" in vr.detail


def test_validate_cutset_unsound_witness_fail():
    """demand ≤ cut_size → 没 Menger violation."""
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    state = _make_enclosed_state(patch={(0, 0), (0, 1)}, commodity_demand=1)
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=1)
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "witness fail" in vr.detail


def test_validate_cutset_unsound_partition_contains_non_free():
    """GPT pro round 2 P0-3 反例: attacker 把 ghost cell 塞进 partition,
    制造小 cut_size. validator 必拒.
    """
    # patch only includes (0,0), (0,1) free. attacker partitions also (5,5) into A,
    # 但 (5,5) 是 ghost.
    state = _make_enclosed_state(patch={(0, 0), (0, 1)})
    side_a = {(0, 0), (5, 5)}  # (5,5) is ghost!
    side_b = {(0, 1)}
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=2)
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "non-free cell" in vr.detail


def test_validate_cutset_unsound_partition_not_enclosed():
    """GPT pro round 2 P0-3 反例: free_cells 有 (1,0) 不在 partition 但 adjacent
    to A={(0,0)} → 流可走 (0,0)→(1,0)→...→(0,1) 绕过 partition. cut 假证.
    """
    # free = {(0,0), (0,1), (1,0)}, partition only includes {(0,0), (0,1)}
    state = _make_enclosed_state(patch={(0, 0), (0, 1), (1, 0)})
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=2)
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "not enclosed" in vr.detail


def test_validate_cutset_unsound_cut_edges_set_mismatch():
    """GPT pro round 2 cert 完整性: attacker cut_size 写 1 跟真 edges set 一致,
    但 cut_edges list 写 wrong edge (e.g. (0,0)-(0,2) 不存在). validator 必拒.
    """
    state = _make_enclosed_state(patch={(0, 0), (0, 1)})
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    # 真 edges = {((0,0), (0,1))}, attacker 写 ((0,0),(5,5))
    cut = _make_cutset_cut(
        side_a, side_b, cut_size=1, commodity_demand=2,
        cut_edges=[[list((0, 0)), list((5, 5))]],  # fake edge
    )
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "cut_edges set mismatch" in vr.detail


def test_validate_cutset_schema_err_missing_cut_edges():
    """cert 缺 cut_edges field → schema_err."""
    state = _make_enclosed_state(patch={(0, 0), (0, 1)})
    cert_dict = {
        "cert_kind": "menger_min_cut",
        "side_a_bitset_b64": _encode_bitset({(0, 0)}),
        "side_b_bitset_b64": _encode_bitset({(0, 1)}),
        # cut_edges missing
        "cut_size": 1,
        "commodity_demand": 2,
    }
    payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    scope = CutScope(
        ghost_rect_id="ghost_v1", blocked_cells_hash="h",
        exterior_blocks_hash="h", source_digest="poc_source_digest",
        artifact_hashes={}, oracle_abstraction_version="cutset_v1",
    )
    cert = OracleCert(cert_kind="x", cert_payload=payload, cert_hash="ch")
    cut = Cut(
        cut_id="F2-no-edges", family="cutset", literals=None,
        geometric_payload=payload, scope=scope, cert=cert,
        family_version="v1.0", validator_version="v1.0",
    )
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "cut_edges" in vr.detail


def test_validate_cutset_schema_err_on_malformed():
    """Malformed cert → schema_err."""
    scope = CutScope(
        ghost_rect_id="ghost_v1",
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
    vr = validate_cutset(cut, _make_enclosed_state(patch=set()), canonical_rules={})
    assert vr.kind == "schema_err"


# ============================================================================
# evaluate_geometric
# ============================================================================

def test_evaluate_geometric_violation_true():
    """demand 100 > cut_size 1 → violate."""
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    state = _make_enclosed_state(patch={(0, 0), (0, 1)})
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=100)
    assert evaluate_geometric_cutset(cut, state) is True


def test_evaluate_geometric_no_violation_false():
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    state = _make_enclosed_state(patch={(0, 0), (0, 1)})
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=0)
    assert evaluate_geometric_cutset(cut, state) is False


# ============================================================================
# Oracle stub
# ============================================================================

def test_validate_cutset_schema_err_when_commodity_registry_missing():
    """GPT pro v4 P0 fix: F2 validator 必 require state.commodity_demands.
    None → schema_err (fail-closed Phase 1.1; Phase 1.5+ Oracle inject 后 unlock).
    """
    state = BState(
        groups={"g": GroupState("g", demand=1, pose_domain=frozenset())},
        ghost_cells=frozenset((x, y) for x in range(70) for y in range(70) if (x, y) not in {(0, 0), (0, 1)}),
        commodity_demands=None,  # 关键: 无 registry
    )
    side_a, side_b = {(0, 0)}, {(0, 1)}
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=2)
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "commodity_demands registry" in vr.detail


def test_validate_cutset_unsound_fake_commodity_demand():
    """GPT pro v4 P0 反例: attacker cert.commodity_demand=999, registry sum 远小.
    validator 必拒 (防 fake over-demand cut).
    """
    state = _make_enclosed_state(patch={(0, 0), (0, 1)}, commodity_demand=2)
    side_a, side_b = {(0, 0)}, {(0, 1)}
    # cert 写 999 但 registry "c1": 2
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=999)
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "commodity_demand mismatch" in vr.detail


def test_validate_cutset_unsound_fake_commodity_id():
    """attacker cert.contributing_commodities=['FAKE'] 不在 registry → reject."""
    state = _make_enclosed_state(patch={(0, 0), (0, 1)}, commodity_demand=2)
    side_a, side_b = {(0, 0)}, {(0, 1)}
    cert_dict = {
        "cert_kind": "menger_min_cut",
        "side_a_bitset_b64": _encode_bitset(side_a),
        "side_b_bitset_b64": _encode_bitset(side_b),
        "cut_edges": [[list((0, 0)), list((0, 1))]],
        "cut_size": 1,
        "commodity_demand": 2,
        "contributing_commodities": ["FAKE_NOT_IN_REGISTRY"],
    }
    payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    cut = Cut(
        cut_id="F2-fake-c", family="cutset", literals=None,
        geometric_payload=payload,
        scope=CutScope(
            ghost_rect_id="ghost_v1", blocked_cells_hash="h",
            exterior_blocks_hash="h", source_digest="poc_source_digest",
            artifact_hashes={"canonical_rules.json": "h1"},
            oracle_abstraction_version="cutset_v1",
        ),
        cert=OracleCert(cert_kind="menger_min_cut", cert_payload=payload, cert_hash="ch"),
        family_version="v1.0", validator_version="v1.0",
    )
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    # 走 6c (not in registry) 或 6e (demand mismatch) — Step N 现 6c 优先 fire
    assert (
        "not in commodity_demands registry" in vr.detail
        or "not in commodity_routes registry" in vr.detail
        or "commodity_demand mismatch" in vr.detail
    )


def test_validate_cutset_unsound_ghost_agnostic_scope():
    """GPT pro v6 P0 反例: F2 scope.ghost_rect_id=GHOST_AGNOSTIC 错标. attacker
    构造 ghost-dependent cut 错标 GHOST_AGNOSTIC → store 不挂 by_ghost_watcher →
    ghost 变化不 invalidate → 失效 cut 残留 active. Phase 1.1 fail-closed reject.
    """
    state = _make_enclosed_state(patch={(0, 0), (0, 1)}, commodity_demand=2)
    side_a, side_b = {(0, 0)}, {(0, 1)}
    cert_dict = {
        "cert_kind": "menger_min_cut",
        "side_a_bitset_b64": _encode_bitset(side_a),
        "side_b_bitset_b64": _encode_bitset(side_b),
        "cut_edges": [[list((0, 0)), list((0, 1))]],
        "cut_size": 1, "commodity_demand": 2,
        "contributing_commodities": ["c1"],
    }
    payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    cut = Cut(
        cut_id="F2-mis-agnostic", family="cutset", literals=None,
        geometric_payload=payload,
        scope=CutScope(
            ghost_rect_id=GHOST_AGNOSTIC,  # 错标!
            blocked_cells_hash="h", exterior_blocks_hash="h",
            source_digest="poc_source_digest",
            artifact_hashes={"canonical_rules.json": "h1"},
            oracle_abstraction_version="cutset_v1",
        ),
        cert=OracleCert(cert_kind="menger_min_cut", cert_payload=payload, cert_hash="ch"),
        family_version="v1.0", validator_version="v1.0",
    )
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "GHOST_AGNOSTIC" in vr.detail


def test_validate_cutset_unsound_route_same_side_not_crossing():
    """GPT pro v5 P0-1 反例: cert.contributing_commodities=["c"], 但 commodity
    "c" 的 route src/sink 都在 side_a (不跨 A/B partition). 真 cross-partition
    demand=0, cert demand=2 是假证. validator 必拒.
    """
    state = _make_enclosed_state(
        patch={(0, 0), (0, 1)}, commodity_demand=2,
        route_src=(0, 0), route_sink=(0, 0),  # 都在 side_a
    )
    side_a, side_b = {(0, 0)}, {(0, 1)}
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=2)
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "route 不跨 partition" in vr.detail


def test_validate_cutset_unsound_duplicate_contributing_commodity():
    """GPT pro v5 P0-1 反例: cert.contributing_commodities=["c","c"] 把同 commodity
    重复列让 demand 被双算. spec §2 commodity 集合语义不是 multiset.
    """
    state = _make_enclosed_state(patch={(0, 0), (0, 1)}, commodity_demand=1)
    side_a, side_b = {(0, 0)}, {(0, 1)}
    # cert 写 ["c1","c1"] + demand=2, registry "c1"=1 — double-count 假证
    cert_dict = {
        "cert_kind": "menger_min_cut",
        "side_a_bitset_b64": _encode_bitset(side_a),
        "side_b_bitset_b64": _encode_bitset(side_b),
        "cut_edges": [[list((0, 0)), list((0, 1))]],
        "cut_size": 1, "commodity_demand": 2,
        "contributing_commodities": ["c1", "c1"],
    }
    payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    cut = Cut(
        cut_id="F2-dup-c", family="cutset", literals=None,
        geometric_payload=payload,
        scope=CutScope(
            ghost_rect_id="ghost_v1", blocked_cells_hash="h",
            exterior_blocks_hash="h", source_digest="poc_source_digest",
            artifact_hashes={"canonical_rules.json": "h1"},
            oracle_abstraction_version="cutset_v1",
        ),
        cert=OracleCert(cert_kind="menger_min_cut", cert_payload=payload, cert_hash="ch"),
        family_version="v1.0", validator_version="v1.0",
    )
    vr = validate_cutset(cut, state, canonical_rules={})
    assert vr.kind == "unsound", f"got {vr.kind}: {vr.detail}"
    assert "duplicate contributing commodity" in vr.detail


def test_generate_cutset_cuts_stub_returns_empty():
    state = _make_enclosed_state(patch=set())
    cuts = generate_cutset_cuts(state, master_solution=None)
    assert cuts == []


def test_validate_cutset_schema_err_bool_commodity_demand():
    side_a = {(0, 0)}
    side_b = {(0, 1)}
    state = _make_enclosed_state(patch={(0, 0), (0, 1)})
    cut = _make_cutset_cut(side_a, side_b, cut_size=1, commodity_demand=2)
    cert = json.loads(cut.geometric_payload)
    cert["commodity_demand"] = True
    payload = json.dumps(cert, sort_keys=True).encode("utf-8")
    tampered = Cut(
        cut_id=cut.cut_id,
        family=cut.family,
        literals=None,
        geometric_payload=payload,
        scope=cut.scope,
        cert=cut.cert,
        family_version=cut.family_version,
        validator_version=cut.validator_version,
    )

    vr = validate_cutset(tampered, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "commodity_demand" in vr.detail
