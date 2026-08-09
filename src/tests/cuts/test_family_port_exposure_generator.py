"""F3 port_exposure generator tests (F3 special-case phase Stage 1).

Coverage:
- env gate: default-disabled → [] / enabled emits cuts
- happy path: 1 port front blocked by another facility → 1 cut emit
- multi-port: 2 ports of same facility both blocked → 2 distinct cuts
- ghost-occluded front: skip (spec §6 + §9 OQ#2)
- exterior-blocked front: skip (master constraint covers)
- out-of-grid front: skip
- free front: no cut emit
- no target_poses, empty cell_owner: []
- target_poses explicit override path
- generator↔validator接合: emit cut + validate → kind="ok"
- dedup: same (facility, port, blocker) emitted once
- fail-closed: candidate_placements None / instance_to_facility_type None → []

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md v1.0
- src/cuts/oracles/port_exposure_oracle.py
- src/cuts/families/port_exposure.py (validator)
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import pytest

from src.cuts.families.port_exposure import validate_port_exposure
from src.cuts.lifecycle import BState, Cell, GroupState
from src.cuts.oracles.port_exposure_oracle import (
    CERT_KIND,
    ORACLE_NAME,
    generate_port_exposure_cuts,
)


CANONICAL_RULES: Dict[str, Any] = {
    "crusher": {"placement_rule": "free", "cells_per_pose": 9},
    "refinery": {"placement_rule": "free", "cells_per_pose": 9},
}

_FACILITY_TEMPLATES = {
    "manufacturing_3x3": {"dimensions": {"w": 3, "h": 3}},
}
_INSTANCE_TO_FT = {
    "crusher": "manufacturing_3x3",
    "refinery": "manufacturing_3x3",
}

# 批 2 identity 语义 (front 错位事故 2026-07-18): pose 层 stored 口坐标本身 = 带子格
# (front), N/S/E/W 仅方向标签, 不再 +delta. 所以每个口都存在体外那一格上.
# Crusher pose "p7" occupies x∈[10..12] y∈[10..12], W 口带子格 = (9, 10) (体外西侧).
# Refinery pose "p3" occupies x∈[9..11] y∈[10..12] (overlap is fine — fixture).
# Refinery pose "p_east" anchored x=13 occupies x∈[13..15] y∈[10..12] — 占 p7_twoports
# E 口带子格 (13, 10), 作 east-direction 阻挡的第二个可放实体.
_CANDIDATE_PLACEMENTS: Dict[str, Any] = {
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
                    {"x": 9, "y": 10, "dir": "W", "commodity": "test"},
                ],
            },
            {
                "pose_id": "p7_twoports",
                "anchor": {"x": 10, "y": 10},
                "occupied_cells": [
                    [10, 10], [11, 10], [12, 10],
                    [10, 11], [11, 11], [12, 11],
                    [10, 12], [11, 12], [12, 12],
                ],
                "input_port_cells": [
                    # 批 2 identity: W 口带子格 = (9, 10) (体外西侧)
                    {"x": 9, "y": 10, "dir": "W", "commodity": "input"},
                ],
                "output_port_cells": [
                    # 批 2 identity: E 口带子格 = (13, 10) (体外东侧)
                    {"x": 13, "y": 10, "dir": "E", "commodity": "output"},
                ],
            },
            {
                "pose_id": "p7_freeport",
                "anchor": {"x": 30, "y": 30},
                "occupied_cells": [
                    [30, 30], [31, 30], [32, 30],
                    [30, 31], [31, 31], [32, 31],
                    [30, 32], [31, 32], [32, 32],
                ],
                "input_port_cells": [],
                "output_port_cells": [
                    # 批 2 identity: W 口带子格 = (29, 30) (体外西侧) = front
                    {"x": 29, "y": 30, "dir": "W", "commodity": "test"},
                ],
            },
            {
                "pose_id": "p7_edgeport",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [
                    [0, 0], [1, 0], [2, 0],
                    [0, 1], [1, 1], [2, 1],
                    [0, 2], [1, 2], [2, 2],
                ],
                "input_port_cells": [],
                "output_port_cells": [
                    # 批 2 identity: W 口带子格 = front = port = (-1, 0), 出 70x70 网格
                    {"x": -1, "y": 0, "dir": "W", "commodity": "test"},
                ],
            },
            {
                "pose_id": "p3",
                "anchor": {"x": 9, "y": 10},
                "occupied_cells": [
                    [9, 10], [10, 10], [11, 10],
                    [9, 11], [10, 11], [11, 11],
                    [9, 12], [10, 12], [11, 12],
                ],
                "input_port_cells": [],
                "output_port_cells": [],
            },
            {
                "pose_id": "p_east",
                "anchor": {"x": 13, "y": 10},
                "occupied_cells": [
                    [13, 10], [14, 10], [15, 10],
                    [13, 11], [14, 11], [15, 11],
                    [13, 12], [14, 12], [15, 12],
                ],
                "input_port_cells": [],
                "output_port_cells": [],
            },
        ],
    },
}


def _make_state(
    *,
    cell_owner: Dict[Cell, Tuple[str, int]] | None = None,
    crusher_poses: List[str] | None = None,
    refinery_poses: List[str] | None = None,
    ghost_cells: frozenset[Cell] = frozenset(),
    exterior_blocks: frozenset[Cell] = frozenset(),
    ghost_rect: Tuple[int, int, int, int] | None = (40, 40, 5, 5),
    candidate_placements: Any = _CANDIDATE_PLACEMENTS,
    instance_to_facility_type: Any = _INSTANCE_TO_FT,
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
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=exterior_blocks,
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"port_exposure_v1"}),
        canonical_rules=CANONICAL_RULES,
        facility_templates=_FACILITY_TEMPLATES,
        instance_to_facility_type=instance_to_facility_type,
        candidate_placements=candidate_placements,
    )


# ---- env gate -------------------------------------------------------------


def test_generator_default_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXACT_F3_GENERATOR_ENABLED", raising=False)
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner={(9, 10): ("refinery", 0)},
    )
    assert generate_port_exposure_cuts(state) == []


def test_generator_env_off_explicit_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "0")
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner={(9, 10): ("refinery", 0)},
    )
    assert generate_port_exposure_cuts(state) == []


# ---- happy path -----------------------------------------------------------


def test_generator_emits_cut_for_blocked_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """批 2 identity: crusher p7 W 口带子格 = front = (9,10), 被 refinery p3 占据."""
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    # cell_owner contains refinery occupied cells; the front cell (9,10) is
    # one of them. We also include the crusher cells for realism.
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11),
              (10, 12), (11, 12), (12, 12)]:
        cell_owner[c] = ("crusher", 0)
    for c in [(9, 10), (9, 11), (9, 12)]:
        cell_owner[c] = ("refinery", 0)
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner=cell_owner,
    )
    cuts = generate_port_exposure_cuts(state, iter_index=7)
    assert len(cuts) == 1
    cut = cuts[0]
    assert cut.family == "port_exposure"
    assert cut.oracle_name == ORACLE_NAME
    cert_dict = json.loads(cut.cert.cert_payload)
    assert cert_dict["cert_kind"] == CERT_KIND
    assert cert_dict["facility_group"] == "crusher"
    assert cert_dict["facility_pose_id"] == "p7"
    assert cert_dict["port_cell"] == [9, 10]  # 批 2 identity: port_cell == front_cell
    assert cert_dict["port_direction"] == "W"
    assert cert_dict["front_cell"] == [9, 10]
    assert cert_dict["blocking_facility"] == ["refinery", 0, "p3"]
    assert cert_dict["active_port_witness_b64"] is None
    # 2 literals per spec §4
    assert len(cut.literals) == 2
    groups = {(lit.slot_ref.group_id, lit.pose_id) for lit in cut.literals}
    assert groups == {("crusher", "p7"), ("refinery", "p3")}
    # cut_id provenance
    assert cut.cut_id.startswith("f3_7_")


def test_generator_multi_port_two_cuts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Facility with input W + output E port, both fronts blocked → 2 cuts."""
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    # crusher p7_twoports occupies x∈[10..12] y∈[10..12]
    for c in [(10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11),
              (10, 12), (11, 12), (12, 12)]:
        cell_owner[c] = ("crusher", 0)
    # refinery p3 blocks west front (9, 10)
    for c in [(9, 10), (9, 11), (9, 12)]:
        cell_owner[c] = ("refinery", 0)
    # refinery p_east at slot 1 blocks east front (13, 10)
    for c in [(13, 10), (14, 10), (15, 10), (13, 11), (14, 11), (15, 11),
              (13, 12), (14, 12), (15, 12)]:
        cell_owner[c] = ("refinery", 1)
    state = _make_state(
        crusher_poses=["p7_twoports"],
        refinery_poses=["p3", "p_east"],
        cell_owner=cell_owner,
    )
    cuts = generate_port_exposure_cuts(state)
    assert len(cuts) == 2
    dirs = sorted(json.loads(c.cert.cert_payload)["port_direction"] for c in cuts)
    assert dirs == ["E", "W"]


def test_generator_skips_free_front(monkeypatch: pytest.MonkeyPatch) -> None:
    """Crusher p7 front (9, 10) free → no cut."""
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    # Only crusher placed; refinery not at front.
    for c in [(10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11),
              (10, 12), (11, 12), (12, 12)]:
        cell_owner[c] = ("crusher", 0)
    state = _make_state(
        crusher_poses=["p7"],
        cell_owner=cell_owner,
    )
    cuts = generate_port_exposure_cuts(state)
    assert cuts == []


# ---- ghost / exterior / boundary skips ------------------------------------


def test_generator_skips_ghost_occluded_front(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec §6 + §9 OQ#2: ghost-occluded front skip (master constraint covers).

    批 2 identity: crusher p7_freeport 的 W 口带子格 = front = (29, 30).
    Put front in ghost_cells → generator should skip (no cut emit).
    """
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(30, 30), (31, 30), (32, 30), (30, 31), (31, 31), (32, 31),
              (30, 32), (31, 32), (32, 32)]:
        cell_owner[c] = ("crusher", 0)
    # Put a refinery at (29, 30) to confirm without ghost mask we'd emit a cut.
    cell_owner[(29, 30)] = ("refinery", 0)
    ghost_cells = frozenset({(29, 30)})
    state = _make_state(
        crusher_poses=["p7_freeport"],
        refinery_poses=["p3"],
        cell_owner=cell_owner,
        ghost_cells=ghost_cells,
    )
    cuts = generate_port_exposure_cuts(state)
    assert cuts == []


def test_generator_skips_exterior_blocked_front(monkeypatch: pytest.MonkeyPatch) -> None:
    """exterior_blocks 占 front 也 skip (跨 ghost 同 spec §6 处理)."""
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(30, 30), (31, 30), (32, 30), (30, 31), (31, 31), (32, 31),
              (30, 32), (31, 32), (32, 32)]:
        cell_owner[c] = ("crusher", 0)
    cell_owner[(29, 30)] = ("refinery", 0)  # would block if not exterior
    exterior_blocks = frozenset({(29, 30)})
    state = _make_state(
        crusher_poses=["p7_freeport"],
        refinery_poses=["p3"],
        cell_owner=cell_owner,
        exterior_blocks=exterior_blocks,
    )
    cuts = generate_port_exposure_cuts(state)
    assert cuts == []


def test_generator_skips_out_of_grid_front(monkeypatch: pytest.MonkeyPatch) -> None:
    """批 2 identity: W 口带子格 = front = port = (-1, 0), 出 70x70 网格 → skip."""
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1),
              (0, 2), (1, 2), (2, 2)]:
        cell_owner[c] = ("crusher", 0)
    state = _make_state(
        crusher_poses=["p7_edgeport"],
        cell_owner=cell_owner,
    )
    cuts = generate_port_exposure_cuts(state)
    assert cuts == []


# ---- target_poses override + empty paths ----------------------------------


def test_generator_explicit_target_poses(monkeypatch: pytest.MonkeyPatch) -> None:
    """target_poses override skips cell_owner derivation."""
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(9, 10), (9, 11), (9, 12)]:
        cell_owner[c] = ("refinery", 0)
    # Crusher's cells NOT in cell_owner — derivation would skip it; explicit
    # target_poses still picks it up.
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner=cell_owner,
    )
    cuts = generate_port_exposure_cuts(
        state,
        target_poses=[("crusher", 0, "p7")],
    )
    assert len(cuts) == 1


def test_generator_empty_cell_owner_no_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    state = _make_state()
    cuts = generate_port_exposure_cuts(state)
    assert cuts == []


def test_generator_empty_target_poses_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit empty list is honored (vs None which falls back to derivation)."""
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11),
              (10, 12), (11, 12), (12, 12)]:
        cell_owner[c] = ("crusher", 0)
    for c in [(9, 10), (9, 11), (9, 12)]:
        cell_owner[c] = ("refinery", 0)
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner=cell_owner,
    )
    cuts = generate_port_exposure_cuts(state, target_poses=[])
    assert cuts == []


# ---- fail-closed data missing ---------------------------------------------


def test_generator_candidate_placements_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner={(9, 10): ("refinery", 0)},
        candidate_placements=None,
    )
    assert generate_port_exposure_cuts(state) == []


def test_generator_instance_to_facility_type_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner={(9, 10): ("refinery", 0)},
        instance_to_facility_type=None,
    )
    assert generate_port_exposure_cuts(state) == []


# ---- dedup ----------------------------------------------------------------


def test_generator_dedup_via_cell_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """cell_owner has 9 cells mapped to (crusher, 0); derivation should produce
    a single (crusher, 0, p7) triple — one cut, not nine.
    """
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11),
              (10, 12), (11, 12), (12, 12)]:
        cell_owner[c] = ("crusher", 0)
    for c in [(9, 10), (9, 11), (9, 12)]:
        cell_owner[c] = ("refinery", 0)
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner=cell_owner,
    )
    cuts = generate_port_exposure_cuts(state)
    # crusher has 1 port; only 1 cut despite 9 cell_owner entries for (crusher,0).
    assert len(cuts) == 1


# ---- generator ↔ validator integration -----------------------------------


def test_generator_output_passes_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cut emitted by generator must validate ok against the same state."""
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11),
              (10, 12), (11, 12), (12, 12)]:
        cell_owner[c] = ("crusher", 0)
    for c in [(9, 10), (9, 11), (9, 12)]:
        cell_owner[c] = ("refinery", 0)
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
        cell_owner=cell_owner,
    )
    cuts = generate_port_exposure_cuts(state)
    assert len(cuts) == 1
    vr = validate_port_exposure(cuts[0], state, CANONICAL_RULES)
    assert vr.kind == "ok", f"validator got {vr.kind}: {vr.detail}"


# ---- self-blocker defensive guard -----------------------------------------


def test_self_blocker_does_not_emit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Self-blocker (blocker == target same group+pose) should not emit cut.

    NIT defensive guard per GPT v17 四审 Reviewer B F3 finding.

    Construct an inconsistent BState where ``cell_owner`` claims crusher slot 0
    occupies its OWN port front cell (9,10). Normal BState would never allow
    this (the pose geometry forbids it), but the generator should fail-closed
    and skip rather than emit a self-referential cut.
    """
    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")
    # Crusher p7's footprint cells + its own port front cell (9,10) all claimed
    # by the same (crusher, slot 0) — geometrically impossible, but we test
    # the guard.
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11),
              (10, 12), (11, 12), (12, 12),
              (9, 10)]:  # port front cell, also "owned" by self
        cell_owner[c] = ("crusher", 0)
    state = _make_state(
        crusher_poses=["p7"],
        cell_owner=cell_owner,
    )
    cuts = generate_port_exposure_cuts(state)
    assert cuts == [], (
        f"self-blocker guard failed: expected 0 cuts, got {len(cuts)}"
    )
