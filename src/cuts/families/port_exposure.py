"""Family 3 port_exposure — production validator + literal-based evaluator.

Implements cut_family_specs/03_port_exposure.md v1.0.

Phase 1.1 P1.7 scope (minimum viable):
- ``validate_port_exposure(cut, state, canonical_rules)`` — 4 步 check:
  1. port_cell + direction 是 facility's port (canonical_rules facility_pose lookup).
  2. front_cell = port_cell + direction offset (math correctness).
  3. blocking_facility 在 state.cell_owner[front_cell] (cause-blocking literal sound).
  4. cut.literals 含 (facility group, pose) + (blocking group, blocking pose) (schema).
- ``evaluate_literal_port_exposure(cut, state)`` — delegates to
  ``lifecycle.evaluate_literal_multiset`` per state_machine_v2 §5 (round 27 B3).

Phase 1.5+ extends (per spec §9 open questions):
- Active port subset check (boundary_constraints per-(cell, dir) net flow LP).
- ghost-occluded front auto-prune (master constraint covers).
- Multi-port cut (facility 多 port 同时 blocked → AND of literals).

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md v1.0
- state_machine_v2.md §5 (multiset semantics + slot anonymity)
"""
from __future__ import annotations

import json
import time
from typing import Dict, Tuple

from src.cuts.lifecycle import BState, Cut, ValidationResult, evaluate_literal_multiset


# Direction → (dx, dy) offset for grid neighbors.
_DIRECTION_OFFSETS: Dict[str, Tuple[int, int]] = {
    "up":    (-1, 0),
    "down":  ( 1, 0),
    "left":  ( 0, -1),
    "right": ( 0, 1),
}


def _direction_offset(direction: str) -> Tuple[int, int]:
    if direction not in _DIRECTION_OFFSETS:
        raise ValueError(f"unknown port_direction={direction!r}")
    return _DIRECTION_OFFSETS[direction]


def validate_port_exposure(
    cut: Cut,
    state: BState,
    canonical_rules: Dict,
) -> ValidationResult:
    """F3 port_exposure validator.

    Decodes cert from ``cut.cert.cert_payload`` (literal-based cuts carry cert
    in OracleCert.cert_payload, not geometric_payload — geometric_payload is
    None per __post_init__ XOR check).

    Verifies:
    1. ``port_cell + direction`` is in ``canonical_rules[facility_group]['ports'][pose_id]``
       (Phase 1.7 minimum-viable: skip if rules don't carry ports; Phase 1.5+
       加 canonical_rules ports lookup).
    2. ``front_cell == port_cell + direction_offset``.
    3. ``state.cell_owner.get(front_cell) == (blocking_group, blocking_slot)``.
    """
    assert cut.cert is not None
    t0 = time.monotonic()
    try:
        cert_dict = json.loads(cut.cert.cert_payload)

        port_cell = tuple(cert_dict["port_cell"])
        port_direction = cert_dict["port_direction"]
        front_cell = tuple(cert_dict["front_cell"])
        blocking_group, blocking_slot, blocking_pose_id = cert_dict["blocking_facility"]

        # 2. front_cell = port_cell + dir offset
        dx, dy = _direction_offset(port_direction)
        expected_front = (port_cell[0] + dx, port_cell[1] + dy)
        if tuple(front_cell) != expected_front:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"front_cell mismatch: cert={front_cell}, expected={expected_front}",
            )

        # 3. blocking_facility 在 state.cell_owner[front_cell]
        cell_owner_entry = state.cell_owner.get(front_cell)
        if cell_owner_entry != (blocking_group, blocking_slot):
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"blocking facility not at front_cell: "
                    f"cert={blocking_group}#{blocking_slot}, "
                    f"actual={cell_owner_entry}"
                ),
            )

        # 1. port_cell 是 facility 的 port (Phase 1.7 minimum: skip if rules
        # 不 carry ports lookup; Phase 1.5+ 加完整 check)
        # canonical_rules[facility_group]["ports_by_pose"][pose_id] → list of (cell, dir)
        facility_group = cert_dict["facility_group"]
        facility_pose_id = cert_dict["facility_pose_id"]
        group_entry = canonical_rules.get(facility_group)
        if isinstance(group_entry, dict):
            ports_by_pose = group_entry.get("ports_by_pose")
            if ports_by_pose is not None:
                pose_ports = ports_by_pose.get(facility_pose_id) or ports_by_pose.get(str(facility_pose_id))
                if pose_ports is not None:
                    if (list(port_cell), port_direction) not in pose_ports and \
                       (port_cell, port_direction) not in pose_ports:
                        return ValidationResult(
                            kind="unsound",
                            elapsed_seconds=time.monotonic() - t0,
                            detail=(
                                f"port ({port_cell}, {port_direction}) not in facility "
                                f"{facility_group}#{facility_pose_id} ports"
                            ),
                        )

        # 4. cut.literals schema check (post_init 已 enforce 非空 + XOR)
        assert cut.literals is not None and len(cut.literals) >= 2

        # Phase 1.5+: active_port_witness verify (cand C boundary_constraints LP).

        return ValidationResult(kind="ok", elapsed_seconds=time.monotonic() - t0)

    except Exception as e:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail=f"{type(e).__name__}: {e}",
        )


def evaluate_literal_port_exposure(cut: Cut, state: BState) -> bool:
    """F3 literal evaluator — delegates to multiset eval (state_machine_v2 §5).

    cut violated iff state.selected_poses contains both:
    (facility_group, facility_pose_id) AND (blocking_group, blocking_pose_id).
    """
    return evaluate_literal_multiset(cut, state)
