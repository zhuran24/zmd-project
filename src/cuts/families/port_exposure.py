"""Family 3 port_exposure — production validator + literal-based evaluator.

Implements cut_family_specs/03_port_exposure.md v1.0 + Gap 9 修 (round 30):
ports lookup from candidate_placements.json pose layer, **不** canonical_rules
(canonical_rules 只 port_rule generation rule, 不 carry per-pose absolute coords).

Phase 1.1 P1.7 scope:
- ``validate_port_exposure(cut, state, canonical_rules)`` — 4 步 check:
  1. cert.front_cell == cert.port_cell + direction_offset (math correctness).
  2. blocking_facility 在 state.cell_owner[front_cell] (cause-blocking literal sound).
  3. port (port_cell, port_direction) 真存在 facility pose's ports (lookup via
     helpers.candidate_placements.pose_ports, Gap 9 fix — fail-closed if
     candidate_placements not injected).
  4. cut.literals ≥ 2 (facility pose + blocking pose, spec §4 form).
- ``evaluate_literal_port_exposure`` — delegates to evaluate_literal_multiset.

Direction encoding N/S/E/W per real candidate_placements.json data (Gap 9
correction — spec §4 wrote "up/down/left/right" but真 data 用 N/S/E/W).

Phase 1.5+ extends:
- Active port subset check (boundary_constraints LP).
- ghost-occluded front auto-prune.

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md v1.0
- state_machine_v2.md §5 (multiset semantics)
- data/preprocessed/candidate_placements.json — ports source-of-truth
"""
from __future__ import annotations

import json
import time
from typing import Dict

from src.cuts.helpers.candidate_placements import (
    DIRECTION_OFFSETS,
    direction_offset,
    pose_ports,
)
from src.cuts.lifecycle import BState, Cut, ValidationResult, evaluate_literal_multiset


def validate_port_exposure(
    cut: Cut,
    state: BState,
    canonical_rules: Dict,
) -> ValidationResult:
    """F3 port_exposure validator.

    Gap 9 修: ports lookup 经 helpers.candidate_placements.pose_ports (查真
    candidate_placements pose 层), 不查 canonical_rules.ports_by_pose
    (该字段不存在). 必须 state.candidate_placements inject, 否则 schema_err
    (fail-closed).
    """
    assert cut.cert is not None
    t0 = time.monotonic()
    try:
        cert_dict = json.loads(cut.cert.cert_payload)

        port_cell = tuple(cert_dict["port_cell"])
        port_direction = cert_dict["port_direction"]
        front_cell = tuple(cert_dict["front_cell"])
        blocking_group, blocking_slot, blocking_pose_id = cert_dict["blocking_facility"]
        facility_group = cert_dict["facility_group"]
        facility_pose_id = cert_dict["facility_pose_id"]

        # 1. direction encoding check (N/S/E/W)
        if port_direction not in DIRECTION_OFFSETS:
            return ValidationResult(
                kind="schema_err",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"unknown port_direction={port_direction!r} (expect N/S/E/W)",
            )

        # 2. front_cell math soundness
        dx, dy = direction_offset(port_direction)
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

        # 4. port 真存在 facility pose (Gap 9 fix)
        ports = pose_ports(state, facility_group, facility_pose_id)
        if ports is None:
            return ValidationResult(
                kind="schema_err",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"cannot locate pose {facility_group}::{facility_pose_id} — "
                    f"candidate_placements / instance_to_facility_type 未 inject"
                ),
            )
        # 验 (port_cell, direction) 在 pose's ports
        port_match = any(
            p.get("x") == port_cell[0]
            and p.get("y") == port_cell[1]
            and p.get("dir") == port_direction
            for p in ports
        )
        if not port_match:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"port ({port_cell}, {port_direction}) not in facility "
                    f"{facility_group}::{facility_pose_id} ports"
                ),
            )

        # 5. cut.literals schema (post_init enforce ≥ 1, F3 spec ≥ 2)
        assert cut.literals is not None and len(cut.literals) >= 2

        return ValidationResult(kind="ok", elapsed_seconds=time.monotonic() - t0)

    except Exception as e:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail=f"{type(e).__name__}: {e}",
        )


def evaluate_literal_port_exposure(cut: Cut, state: BState) -> bool:
    """F3 literal evaluator — delegates to multiset eval (state_machine_v2 §5)."""
    return evaluate_literal_multiset(cut, state)
