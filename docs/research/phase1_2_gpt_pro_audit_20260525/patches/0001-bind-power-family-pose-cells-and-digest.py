#!/usr/bin/env python3
"""Patch Phase 1.2 F7/F8 pose-cell binding and oracle source_digest.

Usage:
    cd _phase1_2_pkg_v12/project
    python /path/to/0001-bind-power-family-pose-cells-and-digest.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()

ORACLES = [
    "src/cuts/oracles/component_reach_oracle.py",
    "src/cuts/oracles/cutset_oracle.py",
    "src/cuts/oracles/density_envelope_oracle.py",
    "src/cuts/oracles/pattern_nogood_oracle.py",
    "src/cuts/oracles/power_cover_oracle.py",
    "src/cuts/oracles/power_grid_reach_oracle.py",
    "src/cuts/oracles/shape_packing_hall_oracle.py",
]

for rel in ORACLES:
    path = ROOT / rel
    text = path.read_text()
    old = "source_digest = state.source_digest or compute_source_digest(state)"
    new = "source_digest = compute_source_digest(state)"
    if old in text:
        path.write_text(text.replace(old, new))

HELPER = """
def _validate_facility_cells_match_pose_registry(
    facility_cells: Tuple[Tuple[int, int], ...],
    cert_dict: Dict[str, Any],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    # Fail closed unless cert facility_cells exactly match the named pose.
    gid = cast(str, cert_dict["facility_group"])
    pose_id = cast(str, cert_dict["facility_pose_id"])

    if state.instance_to_facility_type is None:
        return _vr("unsound", t0, "state.instance_to_facility_type missing")
    facility_type = state.instance_to_facility_type.get(gid)
    if facility_type is None:
        return _vr("unsound", t0, f"facility_group {gid!r} has no facility_type mapping")

    placements = state.candidate_placements
    if not isinstance(placements, dict):
        return _vr("unsound", t0, "state.candidate_placements missing or malformed")
    pools = placements.get("facility_pools")
    if not isinstance(pools, dict):
        return _vr("unsound", t0, "candidate_placements.facility_pools missing or malformed")
    pool = pools.get(facility_type)
    if not isinstance(pool, list):
        return _vr(
            "unsound",
            t0,
            f"candidate_placements.facility_pools[{facility_type!r}] missing or malformed",
        )

    for entry in pool:
        if not isinstance(entry, dict) or entry.get("pose_id") != pose_id:
            continue
        occupied = entry.get("occupied_cells")
        if not isinstance(occupied, list) or not occupied:
            return _vr("unsound", t0, f"pose {pose_id!r} occupied_cells missing or malformed")
        actual_cells: List[Tuple[int, int]] = []
        seen: set[Tuple[int, int]] = set()
        for idx, raw in enumerate(occupied):
            if not isinstance(raw, (list, tuple)) or len(raw) != 2:
                return _vr("unsound", t0, f"occupied_cells[{idx}] malformed for pose {pose_id!r}")
            x_raw, y_raw = raw
            if not _is_strict_int(x_raw) or not _is_strict_int(y_raw):
                return _vr("unsound", t0, f"occupied_cells[{idx}] has non-int coords")
            cell = (cast(int, x_raw), cast(int, y_raw))
            if not (0 <= cell[0] < _GRID_SIZE and 0 <= cell[1] < _GRID_SIZE):
                return _vr("unsound", t0, f"occupied_cells[{idx}] out of grid: {cell!r}")
            if cell in seen:
                return _vr("unsound", t0, f"occupied_cells duplicate cell {cell!r}")
            seen.add(cell)
            actual_cells.append(cell)
        actual = tuple(sorted(actual_cells))
        if facility_cells != actual:
            return _vr(
                "unsound",
                t0,
                f"facility_cells do not match candidate_placements for {(gid, pose_id)!r}",
            )
        return None

    return _vr(
        "unsound",
        t0,
        f"facility_pose_id {pose_id!r} not found in candidate_placements for {facility_type!r}",
    )


"""

def insert_helper(path: Path, marker: str) -> None:
    text = path.read_text()
    if "_validate_facility_cells_match_pose_registry" in text:
        return
    if marker not in text:
        raise RuntimeError(f"marker not found in {path}: {marker}")
    path.write_text(text.replace(marker, HELPER + marker, 1))

f7 = ROOT / "src/cuts/families/power_hitting_set.py"
insert_helper(f7, "def _validate_coverset_empty(")
text = f7.read_text()
old = """        _validate_ghost_scope_binding(cut, cert_dict, state, t0),
        _validate_group_and_template(cert_dict, state, t0),
        _validate_coverset_empty(facility_cells, cert_dict, state, t0),
        _validate_coverset_ghost_only_empty(facility_cells, cert_dict, state, t0),
"""
new = """        _validate_ghost_scope_binding(cut, cert_dict, state, t0),
        _validate_group_and_template(cert_dict, state, t0),
        _validate_facility_cells_match_pose_registry(facility_cells, cert_dict, state, t0),
        _validate_coverset_empty(facility_cells, cert_dict, state, t0),
        _validate_coverset_ghost_only_empty(facility_cells, cert_dict, state, t0),
"""
if old in text:
    f7.write_text(text.replace(old, new, 1))

f8 = ROOT / "src/cuts/families/power_grid_reach.py"
insert_helper(f8, "def _build_full_free_mask(")
text = f8.read_text()
old = """        _validate_ghost_scope_binding(cut, cert_dict, state, t0),
        _validate_group_and_template(cert_dict, state, t0),
        _validate_source_of_truth_scalars(pc_anchor, cert_dict, state, t0),
        _validate_disconnect_witness(facility_cells, pc_anchor, cert_dict, state, t0),
        _validate_ghost_only_disconnect(facility_cells, pc_anchor, cert_dict, state, t0),
"""
new = """        _validate_ghost_scope_binding(cut, cert_dict, state, t0),
        _validate_group_and_template(cert_dict, state, t0),
        _validate_facility_cells_match_pose_registry(facility_cells, cert_dict, state, t0),
        _validate_source_of_truth_scalars(pc_anchor, cert_dict, state, t0),
        _validate_disconnect_witness(facility_cells, pc_anchor, cert_dict, state, t0),
        _validate_ghost_only_disconnect(facility_cells, pc_anchor, cert_dict, state, t0),
"""
if old in text:
    f8.write_text(text.replace(old, new, 1))

tf7 = ROOT / "src/tests/cuts/test_family_power_hitting_set.py"
text = tf7.read_text()
if "test_validator_unsound_when_facility_cells_do_not_match_pose_registry" not in text:
    marker = "def test_validator_unsound_ghost_agnostic_scope() -> None:\n"
    test = """def test_validator_unsound_when_facility_cells_do_not_match_pose_registry() -> None:
    state = _make_state(pose_anchor=(0, 0))
    state.groups["crusher_blue_iron"].selected_poses = ["p_3x3_a"]
    cert_payload = _make_cert(state)  # cert cells default to the old (30,30) footprint
    cut = _make_cut(cert_payload, state)
    result = validate_power_hitting_set(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "facility_cells" in (result.detail or "")


"""
    tf7.write_text(text.replace(marker, test + marker, 1))

tf8 = ROOT / "src/tests/cuts/test_family_power_grid_reach.py"
text = tf8.read_text()
if "test_validator_unsound_when_facility_cells_do_not_match_pose_registry" not in text:
    marker = "def test_validator_unsound_facility_group_not_in_state() -> None:\n"
    test = """def test_validator_unsound_when_facility_cells_do_not_match_pose_registry() -> None:
    state = _f5_fixture_state(
        ghost_rect=(30, 0, 10, 70),
        facility_anchor=(0, 0),
        pc_anchor=(10, 10),
        selected_poses=["p_3x3_a"],
    )
    cert_payload = _make_cert(state, facility_anchor=(60, 60), protocol_core_cell=[10, 10])
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "facility_cells" in (result.detail or "")


"""
    tf8.write_text(text.replace(marker, test + marker, 1))

scope_test = ROOT / "src/tests/cuts/test_oracle_scope_digest.py"
if not scope_test.exists():
    scope_test.write_text("""import os

from src.cuts.lifecycle import compute_source_digest
from src.cuts.oracles.power_cover_oracle import generate_power_hitting_set_cuts
from src.tests.cuts.test_family_power_hitting_set import _make_state


def test_oracle_scope_uses_computed_source_digest_even_if_state_field_is_stale() -> None:
    os.environ["EXACT_F7_GENERATOR_ENABLED"] = "1"
    try:
        state = _make_state()
        state.source_digest = "stale-human-note-not-canonical-digest"
        cuts = generate_power_hitting_set_cuts(
            state,
            target_poses=[("crusher_blue_iron", "p_3x3_a")],
            pole_radius=5.0,
            iter_index=0,
        )
        assert len(cuts) == 1
        assert cuts[0].scope.source_digest == compute_source_digest(state)
    finally:
        os.environ.pop("EXACT_F7_GENERATOR_ENABLED", None)
""")

print("Patched Phase 1.2 F7/F8 pose-cell binding and oracle source_digest.")
