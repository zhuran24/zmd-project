"""Family 3 port_exposure — production validator + literal-based evaluator.

Direction encoding N/S/E/W per real candidate_placements.json data.
"""
from __future__ import annotations

import time
from collections import Counter
from typing import Any, Dict, Literal, Tuple, cast

from src.cuts.helpers.candidate_placements import (
    DIRECTION_OFFSETS,
    direction_offset,
    find_pose,
    pose_ports,
)
from src.cuts.lifecycle import BState, Cell, Cut, ValidationResult, validate_cert_payload

ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


def _vr(kind: ValidationKind, t0: float, detail: str = "") -> ValidationResult:
    return ValidationResult(kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None)


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_non_empty_str(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be non-empty str")
    return value


def _parse_strict_int(value: object, field_name: str) -> int:
    if not _is_strict_int(value):
        raise ValueError(f"{field_name} must be int (bool/str rejected)")
    return cast(int, value)


def _cell(raw: object, *, grid_size: int = 70) -> Cell:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise ValueError(f"expected cell as a length-2 list/tuple, got {raw!r}")
    cell = (
        _parse_strict_int(raw[0], "cell.x"),
        _parse_strict_int(raw[1], "cell.y"),
    )
    if not (0 <= cell[0] < grid_size and 0 <= cell[1] < grid_size):
        raise ValueError(f"cell out of grid: {cell!r}")
    return cell


def _parse_blocking_facility(value: object) -> Tuple[str, int, str]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("blocking_facility must be [group, slot, pose_id]")
    return (
        _parse_non_empty_str(value[0], "blocking_facility[0]"),
        _parse_strict_int(value[1], "blocking_facility[1]"),
        _parse_non_empty_str(value[2], "blocking_facility[2]"),
    )


def _validate_front_cell_math(
    port_cell: Cell,
    port_direction: str,
    front_cell: Cell,
    t0: float,
) -> ValidationResult | None:
    if port_direction not in DIRECTION_OFFSETS:
        return _vr("schema_err", t0, f"unknown port_direction={port_direction!r} (expect N/S/E/W)")
    dx, dy = direction_offset(port_direction)
    expected_front = (port_cell[0] + dx, port_cell[1] + dy)
    if front_cell != expected_front:
        return _vr("unsound", t0, f"front_cell mismatch: cert={front_cell}, expected={expected_front}")
    return None


def _validate_blocking_binding(
    front_cell: Cell,
    blocking_group: str,
    blocking_slot: int,
    blocking_pose_id: str,
    state: BState,
    t0: float,
) -> ValidationResult | None:
    cell_owner_entry = state.cell_owner.get(front_cell)
    if cell_owner_entry != (blocking_group, blocking_slot):
        return _vr(
            "unsound",
            t0,
            f"blocking facility not at front_cell: cert={blocking_group}#{blocking_slot}, actual={cell_owner_entry}",
        )
    blocking_state = state.groups.get(blocking_group)
    if blocking_state is None:
        return _vr("unsound", t0, f"blocking group {blocking_group!r} not in state.groups")
    if blocking_slot < 0 or blocking_slot >= len(blocking_state.selected_poses):
        return _vr("unsound", t0, f"blocking_slot {blocking_slot} out of range")
    actual_blocking_pose_id = blocking_state.selected_poses[blocking_slot]
    if actual_blocking_pose_id != blocking_pose_id:
        return _vr(
            "unsound",
            t0,
            f"blocking_pose_id mismatch: cert={blocking_pose_id!r}, state.selected_poses[{blocking_slot}]={actual_blocking_pose_id!r}",
        )
    blocking_pose = find_pose(state, blocking_group, blocking_pose_id)
    if blocking_pose is None:
        return _vr("schema_err", t0, f"cannot locate blocking pose {blocking_group}::{blocking_pose_id}")
    occupied = {_cell(c) for c in blocking_pose.get("occupied_cells", [])}
    if front_cell not in occupied:
        return _vr("unsound", t0, f"front_cell {front_cell} not in blocking_pose {blocking_pose_id!r} occupied_cells")
    return None


def _validate_literal_multiset_binding(
    cut: Cut,
    facility_group: str,
    facility_pose_id: str,
    blocking_group: str,
    blocking_pose_id: str,
    t0: float,
) -> ValidationResult | None:
    expected_pairs: Counter[Tuple[str, str]] = Counter([
        (facility_group, facility_pose_id),
        (blocking_group, blocking_pose_id),
    ])
    actual_pairs: Counter[Tuple[str, str]] = Counter(
        (lit.slot_ref.group_id, lit.pose_id) for lit in (cut.literals or ())
    )
    if expected_pairs != actual_pairs:
        return _vr(
            "unsound",
            t0,
            f"cert ↔ literals multiset mismatch: cert={dict(expected_pairs)}, literals={dict(actual_pairs)}",
        )
    return None


def _validate_port_exists(
    state: BState,
    facility_group: str,
    facility_pose_id: str,
    port_cell: Cell,
    port_direction: str,
    t0: float,
) -> ValidationResult | None:
    ports = pose_ports(state, facility_group, facility_pose_id)
    if ports is None:
        return _vr("schema_err", t0, f"cannot locate pose {facility_group}::{facility_pose_id}")
    port_match = any(
        p.get("x") == port_cell[0]
        and p.get("y") == port_cell[1]
        and p.get("dir") == port_direction
        for p in ports
    )
    if not port_match:
        return _vr("unsound", t0, f"port ({port_cell}, {port_direction}) not in facility {facility_group}::{facility_pose_id} ports")
    return None


def validate_port_exposure(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """F3 port_exposure validator: cert geometry + blocker/literal binding."""
    t0 = time.monotonic()
    del canonical_rules
    if cut.cert is None:
        return _vr("schema_err", t0, "cut.cert is None (schema invariant violated)")
    if cut.literals is None or len(cut.literals) < 2:
        actual = 0 if cut.literals is None else len(cut.literals)
        return _vr("schema_err", t0, f"F3 spec §4: cut.literals 必 ≥ 2; actual={actual}")
    try:
        cert_dict = validate_cert_payload("port_exposure", cut.cert.cert_payload)
        port_cell = _cell(cert_dict.get("port_cell"))
        port_direction = _parse_non_empty_str(cert_dict.get("port_direction"), "port_direction")
        front_cell = _cell(cert_dict.get("front_cell"))
        blocking_group, blocking_slot, blocking_pose_id = _parse_blocking_facility(
            cert_dict.get("blocking_facility")
        )
        facility_group = _parse_non_empty_str(cert_dict.get("facility_group"), "facility_group")
        facility_pose_id = _parse_non_empty_str(cert_dict.get("facility_pose_id"), "facility_pose_id")

        for error in (
            _validate_front_cell_math(port_cell, port_direction, front_cell, t0),
            _validate_blocking_binding(front_cell, blocking_group, blocking_slot, blocking_pose_id, state, t0),
            _validate_literal_multiset_binding(cut, facility_group, facility_pose_id, blocking_group, blocking_pose_id, t0),
            _validate_port_exists(state, facility_group, facility_pose_id, port_cell, port_direction, t0),
        ):
            if error is not None:
                return error
        return _vr("ok", t0)
    except Exception as e:
        return _vr("schema_err", t0, f"{type(e).__name__}: {e}")
