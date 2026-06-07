"""Tests for Family 7 power_hitting_set (P1.2B-F7).

Phase 1.2 single-case scope: cert_kind = "power_cover_emptyset_ghost" only.
cell_owner causation (multi-literal) deferred Phase 1.5+.

Coverage:
- Generator: default-disabled (env gate) / ghost-cleared CoverSet emits /
  cell_owner-only cleared SKIP (Phase 1.5+) / feasible (CoverSet non-empty) /
  non-powered facility SKIP.
- Validator: 7-phase (parse / cert_kind / scalars / ghost scope / group +
  needs_power / full CoverSet empty / ghost-only CoverSet empty).
- Adversarial: pole_shape!=2x2 / forged cert_kind / facility_pose !=
  cut.literals / cell_owner-only cleared cert / non-powered facility cert /
  ghost drift / exterior drift.
- Watcher keys.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Tuple

import pytest

from src.cuts.families.power_hitting_set import (
    validate_power_hitting_set,
    watcher_keys_power_hitting_set,
)
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
    compute_ghost_rect_id,
    compute_source_digest,
    evaluate_literal_multiset,
)
from src.cuts.oracles.power_cover_oracle import (
    generate_power_hitting_set_cuts,
)


_UNSET: Any = object()


def _3x3_pose_cells(anchor: Tuple[int, int]) -> List[List[int]]:
    x, y = anchor
    return sorted([[x + dx, y + dy] for dx in range(3) for dy in range(3)])


def _make_state(
    *,
    ghost_rect: Tuple[int, int, int, int] | None = (25, 25, 16, 16),
    ghost_cells: frozenset[Tuple[int, int]] | None = None,
    exterior_blocks: frozenset[Tuple[int, int]] | None = None,
    cell_owner: Dict[Tuple[int, int], Any] | None = None,
    pose_anchor: Tuple[int, int] = (30, 30),
    pose_id: str = "p_3x3_a",
    group_id: str = "crusher_blue_iron",
    instance_to_facility_type: Any = _UNSET,
    facility_templates: Any = _UNSET,
    candidate_placements: Any = _UNSET,
) -> BState:
    """Fixture: 3×3 facility at pose_anchor inside 16×16 ghost so CoverSet is empty."""
    if ghost_cells is None:
        # ghost rect (25, 25, 16, 16) → cells (25..40, 25..40)
        x, y, h, w = ghost_rect or (25, 25, 16, 16)
        ghost_cells = frozenset(
            (x + i, y + j) for i in range(h) for j in range(w)
        )
    if exterior_blocks is None:
        exterior_blocks = frozenset()
    if cell_owner is None:
        cell_owner = {}
    if instance_to_facility_type is _UNSET:
        instance_to_facility_type = {group_id: "manufacturing_3x3"}
    if facility_templates is _UNSET:
        facility_templates = {
            "manufacturing_3x3": {
                "dimensions": {"w": 3, "h": 3},
                "needs_power": True,
            },
            "power_pole": {
                "dimensions": {"w": 2, "h": 2},
                "needs_power": False,
                "power_coverage_radius": 5,
            },
        }
    if candidate_placements is _UNSET:
        candidate_placements = {
            "facility_pools": {
                "manufacturing_3x3": [
                    {
                        "pose_id": pose_id,
                        "anchor": list(pose_anchor),
                        "occupied_cells": _3x3_pose_cells(pose_anchor),
                        "input_port_cells": [],
                        "output_port_cells": [],
                    }
                ],
            },
        }
    groups = {
        group_id: GroupState(
            group_id=group_id,
            demand=1,
            pose_domain=frozenset({pose_id}),
            selected_poses=[],
        ),
    }
    # Source-of-truth canonical_rules (F7 forged-radius SoT fix, mirror F8): the
    # validator cross-checks cert.pole_radius against canonical
    # facility_templates.power_pole.power_coverage_radius. Mirror facility_templates
    # here so the cross-check finds R=5 (None when facility_templates is not a dict,
    # which the fail-closed test relies on).
    canonical_rules = (
        {"facility_templates": facility_templates}
        if isinstance(facility_templates, dict)
        else None
    )
    return BState(
        groups=groups,
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=exterior_blocks,
        cell_owner=cell_owner,
        candidate_placements=candidate_placements,
        instance_to_facility_type=instance_to_facility_type,
        facility_templates=facility_templates,
        canonical_rules=canonical_rules,
        available_oracle_versions=frozenset({"power_cover_v1"}),
        source_digest="test-source-digest",
    )


def _make_cert(
    state: BState,
    *,
    cert_kind: str = "power_cover_emptyset_ghost",
    facility_group: str = "crusher_blue_iron",
    facility_pose_id: str = "p_3x3_a",
    facility_cells: List[List[int]] | None = None,
    pole_radius: float = 5.0,
    pole_shape_canonical: str = "2x2_rigid",
    ghost_rect_repr: List[int] | None = None,
    exterior_blocks_digest: str | None = None,
) -> bytes:
    if facility_cells is None:
        facility_cells = _3x3_pose_cells((30, 30))
    if ghost_rect_repr is None:
        ghost_rect_repr = list(state.ghost_rect) if state.ghost_rect else [0, 0, 1, 1]
    if exterior_blocks_digest is None:
        exterior_blocks_digest = compute_exterior_blocks_hash(state)
    return canonical_bytes_for_cert({
        "cert_kind": cert_kind,
        "facility_group": facility_group,
        "facility_pose_id": facility_pose_id,
        "facility_cells": facility_cells,
        "pole_radius": pole_radius,
        "pole_shape_canonical": pole_shape_canonical,
        "ghost_rect_repr": ghost_rect_repr,
        "exterior_blocks_digest": exterior_blocks_digest,
    })


def _make_cut(
    cert_payload: bytes,
    state: BState,
    *,
    facility_group: str = "crusher_blue_iron",
    facility_pose_id: str = "p_3x3_a",
    scope_ghost_id: str | None = None,
) -> Cut:
    if scope_ghost_id is None:
        scope_ghost_id = compute_ghost_rect_id(state.ghost_rect)
    cert_hash = hashlib.sha256(cert_payload).hexdigest()
    scope = CutScope(
        ghost_rect_id=scope_ghost_id,
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest=compute_source_digest(state),
        oracle_abstraction_version="power_cover_v1",
    )
    return Cut(
        cut_id=f"f7_test_{cert_hash[:8]}",
        family="power_hitting_set",
        literals=(
            CutLiteral(
                slot_ref=AnonymousSlotRef(group_id=facility_group, slot_index=0),
                pose_id=facility_pose_id,
            ),
        ),
        geometric_payload=None,
        scope=scope,
        cert=OracleCert(
            cert_kind="power_cover_emptyset_ghost",
            cert_payload=cert_payload,
            cert_hash=cert_hash,
        ),
        family_version="v1.0",
        validator_version="v1.0",
        oracle_name="power_cover_v1",
        oracle_cert_hash=cert_hash,
    )


# ---- generator -------------------------------------------------------------


def test_generator_default_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXACT_F7_GENERATOR_ENABLED", raising=False)
    state = _make_state()
    cuts = generate_power_hitting_set_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        pole_radius=5.0,
    )
    assert cuts == []


def test_generator_emits_cut_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F7_GENERATOR_ENABLED", "1")
    state = _make_state()
    cuts = generate_power_hitting_set_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        pole_radius=5.0,
    )
    assert len(cuts) == 1
    cert_dict = json.loads(cuts[0].cert.cert_payload)
    assert cert_dict["cert_kind"] == "power_cover_emptyset_ghost"
    assert cert_dict["facility_group"] == "crusher_blue_iron"
    assert cert_dict["pole_shape_canonical"] == "2x2_rigid"


def test_generator_skips_cell_owner_only_clearance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ghost-only CoverSet non-empty but cell_owner pushes full CoverSet to ∅.

    Place a 3×3 facility at (0, 60). Without ghost there are plenty of pole
    anchor candidates around it. We then add cell_owner blocks at every cell
    within R=5 of the facility so full free-cells set leaves no valid 2×2
    pole anchor; ghost-only CoverSet (ignoring cell_owner) remains non-empty.
    """
    monkeypatch.setenv("EXACT_F7_GENERATOR_ENABLED", "1")
    facility_cells = {(0, 60), (0, 61), (0, 62), (1, 60), (1, 61), (1, 62),
                      (2, 60), (2, 61), (2, 62)}
    # Block all cells within radius 5 + pole footprint of facility_cells.
    cell_owner: Dict[Tuple[int, int], Any] = {}
    for px in range(0, 9):  # cover x=[0..8] which includes pole anchors near facility
        for py in range(54, 70):  # cover y near facility row
            if (px, py) not in facility_cells:
                cell_owner[(px, py)] = "blocker"
    state = _make_state(
        ghost_rect=(50, 0, 5, 5),
        ghost_cells=frozenset((50 + i, j) for i in range(5) for j in range(5)),
        cell_owner=cell_owner,
        pose_anchor=(0, 60),
    )
    cuts = generate_power_hitting_set_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        pole_radius=5.0,
    )
    # Full CoverSet ∅ (cell_owner blocks all near pole anchors) but ghost-only
    # CoverSet non-empty → cell_owner is the cause → Phase 1.2 SKIP.
    assert cuts == []


def test_generator_skips_non_powered_facility(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F7_GENERATOR_ENABLED", "1")
    state = _make_state(
        facility_templates={
            "manufacturing_3x3": {
                "dimensions": {"w": 3, "h": 3},
                "needs_power": False,  # toggle to non-powered
            },
            "power_pole": {
                "dimensions": {"w": 2, "h": 2},
                "needs_power": False,
                "power_coverage_radius": 5,
            },
        },
    )
    cuts = generate_power_hitting_set_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        pole_radius=5.0,
    )
    assert cuts == []


def test_generator_no_target_poses_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F7_GENERATOR_ENABLED", "1")
    state = _make_state()
    cuts = generate_power_hitting_set_cuts(state, target_poses=None)
    assert cuts == []


def test_generator_ghost_none_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F7_GENERATOR_ENABLED", "1")
    state = _make_state(ghost_rect=None, ghost_cells=frozenset())
    cuts = generate_power_hitting_set_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        pole_radius=5.0,
    )
    assert cuts == []


# ---- validator: happy path -------------------------------------------------


def test_validator_happy_path() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "ok", f"detail={result.detail!r}"


# ---- validator: schema errors ---------------------------------------------


def test_validator_rejects_wrong_cert_kind() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, cert_kind="power_cover_emptyset_cell_owner")
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "schema_err"
    assert "cert_kind" in (result.detail or "")


def test_validator_rejects_pole_shape_not_2x2() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, pole_shape_canonical="1x1_rigid")
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "schema_err"
    assert "2x2_rigid" in (result.detail or "")


def test_validator_rejects_nonpositive_pole_radius() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, pole_radius=0.0)
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_forged_positive_pole_radius() -> None:
    # F7 forged-radius source-of-truth regression (mirror F8
    # test_validator_rejects_malicious_pole_jump_radius). A positive-but-non-canonical
    # radius passes the schema (> 0) but the CoverSet recompute would trust it: a tiny
    # radius empties the CoverSet and certifies a false-positive cut for a pose that is
    # genuinely powerable at canonical R=5. The SoT cross-check must reject it as unsound
    # before the recompute. (Without the fix this returns "ok" — the soundness hole.)
    state = _make_state()
    cert_payload = _make_cert(state, pole_radius=0.0001)
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound", f"detail={result.detail!r}"
    assert "pole_radius" in (result.detail or "")


def test_validator_rejects_missing_canonical_pole_radius() -> None:
    # Fail-closed: if state.canonical_rules lacks power_pole.power_coverage_radius the
    # SoT cross-check cannot verify the radius and must return unsound, not silently
    # accept. facility_templates omits power_pole so canonical lookup returns None.
    state = _make_state(
        facility_templates={
            "manufacturing_3x3": {"dimensions": {"w": 3, "h": 3}, "needs_power": True},
        }
    )
    cert_payload = _make_cert(state, pole_radius=5.0)
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound", f"detail={result.detail!r}"
    assert "source-of-truth" in (result.detail or "")


def test_validator_rejects_facility_cells_unsorted() -> None:
    state = _make_state()
    cells = _3x3_pose_cells((30, 30))
    cells[0], cells[-1] = cells[-1], cells[0]
    cert_payload = _make_cert(state, facility_cells=cells)
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_multi_literal() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    extra_lit = CutLiteral(
        slot_ref=AnonymousSlotRef(group_id="other_group", slot_index=0),
        pose_id="other_pose",
    )
    cut = Cut(
        cut_id=cut.cut_id, family=cut.family,
        literals=cut.literals + (extra_lit,),
        geometric_payload=None,
        scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
        oracle_name=cut.oracle_name, oracle_cert_hash=cut.oracle_cert_hash,
    )
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "schema_err"
    assert "Phase 1.2" in (result.detail or "")


# ---- validator: unsound ----------------------------------------------------


def test_validator_unsound_when_literals_disagree_with_cert() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state, facility_pose_id="other_pose")
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"


def test_validator_unsound_when_facility_cells_do_not_match_pose_registry() -> None:
    state = _make_state(pose_anchor=(0, 0))
    state.groups["crusher_blue_iron"].selected_poses = ["p_3x3_a"]
    cert_payload = _make_cert(state)  # cert cells default to the old (30,30) footprint
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "facility_cells" in (result.detail or "")


def test_validator_unsound_ghost_agnostic_scope() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state, scope_ghost_id=GHOST_AGNOSTIC)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "GHOST_AGNOSTIC" in (result.detail or "")


def test_validator_unsound_when_cover_set_recompute_non_empty() -> None:
    """Build a cert claiming empty CoverSet while real recompute finds candidates.

    With ghost 1×1 far from facility, the facility's CoverSet is genuinely
    non-empty (many 2×2 pole anchor positions around it). The generator would
    not have emitted this cert, but an attacker / stale cert could —
    validator phase 6 catches via recompute.
    """
    state = _make_state(
        ghost_rect=(60, 60, 1, 1),
        ghost_cells=frozenset({(60, 60)}),
    )
    fake_cert = _make_cert(state)
    fake_cut = _make_cut(fake_cert, state)
    result = validate_power_hitting_set(fake_cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "cover_set recompute non-empty" in (result.detail or "")


def test_validator_unsound_when_cell_owner_only_clearance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ghost-only CoverSet non-empty → single-literal cert is bogus (cell_owner真因).

    Phase 7 catches: cert claims "power_cover_emptyset_ghost" but the
    ghost+exterior recompute (excluding cell_owner) finds candidates, meaning
    cell_owner is the true cause and the single-literal cut is unsound.
    Phase 1.5+ multi-literal handles this; Phase 1.2 must reject.

    Constructing a real state where the full-mask CoverSet is empty but the
    ghost-only mask is non-empty needs very specific cell_owner coverage.
    We exercise the validator branch via monkey-patch — phase 6 returns ∅
    (full free-cells cover_set), phase 7 returns non-∅ (ghost-only cover_set).
    """
    state = _make_state()  # default: ghost 25,25,16,16 → both CoverSets empty
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    from src.cuts.families import power_hitting_set as f7_mod

    call_state = {"count": 0}

    def _mock_cover(*args: Any, **_kwargs: Any) -> frozenset[Tuple[int, int]]:
        call_state["count"] += 1
        if call_state["count"] == 1:
            return frozenset()  # phase 6 (full free-cells): empty
        return frozenset({(0, 0)})  # phase 7 (ghost-only): non-empty

    monkeypatch.setattr(f7_mod, "compute_cover_set", _mock_cover)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "cell_owner" in (result.detail or "") or "true cause" in (result.detail or "")


def test_validator_unsound_facility_group_not_in_state() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, facility_group="fake_group")
    cut = _make_cut(cert_payload, state, facility_group="fake_group")
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"


def test_validator_unsound_pose_not_in_pose_domain() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, facility_pose_id="fake_pose")
    cut = _make_cut(cert_payload, state, facility_pose_id="fake_pose")
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"


def test_validator_unsound_when_needs_power_false() -> None:
    """needs_power=False facility cannot be subject of a F7 cut (adversary catch)."""
    state = _make_state(
        facility_templates={
            "manufacturing_3x3": {
                "dimensions": {"w": 3, "h": 3},
                "needs_power": False,
            },
        },
    )
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "needs_power" in (result.detail or "")


def test_validator_unsound_when_facility_templates_missing() -> None:
    state = _make_state(facility_templates=None)
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "facility_templates" in (result.detail or "")


def test_validator_unsound_ghost_drift() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    new_state = _make_state(ghost_rect=(10, 10, 2, 2),
                            ghost_cells=frozenset({(10, 10), (10, 11), (11, 10), (11, 11)}))
    result = validate_power_hitting_set(cut, new_state, canonical_rules={})
    assert result.kind == "unsound"


# ---- evaluator (literal multiset) ------------------------------------------


def test_evaluator_literal_multiset_when_pose_selected() -> None:
    state = _make_state()
    state.groups["crusher_blue_iron"].selected_poses.append("p_3x3_a")
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    assert evaluate_literal_multiset(cut, state) is True


def test_evaluator_literal_multiset_when_pose_not_selected() -> None:
    state = _make_state()
    # selected_poses empty → cut does not violate
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    assert evaluate_literal_multiset(cut, state) is False


def test_evaluator_literal_multiset_fails_closed_on_same_rect_ghost_cells_drift() -> None:
    """F7 is literal-based, but its proof scope is ghost-bound."""
    state = _make_state()
    state.groups["crusher_blue_iron"].selected_poses.append("p_3x3_a")
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    new_state = _make_state(ghost_cells=frozenset())
    new_state.groups["crusher_blue_iron"].selected_poses.append("p_3x3_a")
    assert compute_ghost_rect_id(new_state.ghost_rect) == cut.scope.ghost_rect_id
    assert compute_blocked_cells_hash(new_state) != cut.scope.blocked_cells_hash
    assert evaluate_literal_multiset(cut, new_state) is False


# ---- watcher keys ----------------------------------------------------------


def test_watcher_keys_returns_group_pose_cell() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    keys = watcher_keys_power_hitting_set(cut)
    assert keys["group_keys"] == ["crusher_blue_iron"]
    assert keys["pose_keys"] == [("crusher_blue_iron", "p_3x3_a")]
    assert len(keys["cell_keys"]) == 9  # 3×3 facility
    assert (30, 30) in keys["cell_keys"]


def test_watcher_keys_failsafe_on_malformed() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    garbled = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=cut.literals,
        geometric_payload=None,
        scope=cut.scope,
        cert=OracleCert(
            cert_kind="power_cover_emptyset_ghost",
            cert_payload=b"not json {{{",
            cert_hash=hashlib.sha256(b"not json {{{").hexdigest(),
        ),
        family_version=cut.family_version, validator_version=cut.validator_version,
        oracle_name=cut.oracle_name,
        oracle_cert_hash=hashlib.sha256(b"not json {{{").hexdigest(),
    )
    keys = watcher_keys_power_hitting_set(garbled)
    assert keys == {"group_keys": [], "pose_keys": [], "cell_keys": []}


def test_validator_unsound_when_pose_registry_has_duplicate_pose_id() -> None:
    candidate_placements = {
        "facility_pools": {
            "manufacturing_3x3": [
                {
                    "pose_id": "p_3x3_a",
                    "anchor": [30, 30],
                    "occupied_cells": _3x3_pose_cells((30, 30)),
                    "input_port_cells": [],
                    "output_port_cells": [],
                },
                {
                    "pose_id": "p_3x3_a",
                    "anchor": [0, 0],
                    "occupied_cells": _3x3_pose_cells((0, 0)),
                    "input_port_cells": [],
                    "output_port_cells": [],
                },
            ],
        },
    }
    state = _make_state(candidate_placements=candidate_placements)
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "not unique" in (result.detail or "")

# ---- adversarial source-of-truth template hardening -----------------------


def test_validator_rejects_power_pole_dimension_drift() -> None:
    """F7: helper/cert 2x2 pole footprint must match canonical_rules."""
    state = _make_state(
        facility_templates={
            "manufacturing_3x3": {"dimensions": {"w": 3, "h": 3}, "needs_power": True},
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 5,
            },
        },
    )
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "power_pole dimensions" in (result.detail or "") or "2x2" in (result.detail or "")
