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
from collections import Counter
from typing import Dict

from src.cuts.helpers.candidate_placements import (
    DIRECTION_OFFSETS,
    direction_offset,
    find_pose,
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

    GPT pro round 2: schema check 走 explicit if (不 assert) — `python -O`
    模式 assert 全删, 一元 literal 走过假证.
    """
    t0 = time.monotonic()
    # Explicit guards (post_init 保证 invariant, 但 python -O 下 assert 失效,
    # validator 入口必须独立验)
    if cut.cert is None:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail="cut.cert is None (schema invariant violated)",
        )
    if cut.literals is None or len(cut.literals) < 2:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail=(
                f"F3 spec §4: cut.literals 必 ≥ 2 (facility pose + blocking pose); "
                f"actual={0 if cut.literals is None else len(cut.literals)}"
            ),
        )
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

        # 3b. blocking_slot → selected_poses[slot] 真等 blocking_pose_id (GPT pro
        # v2 P0-2 fix). 反例: attacker cert blocking_slot=0 cell_owner check 通
        # (slot 0 真有占), 但 cert.blocking_pose_id="p_fake" 跟 selected_poses[0]
        # 实际 p_actual 不同. 缺这步 binding → 同 group 不同 pose 替换攻击成立.
        blocking_state = state.groups.get(blocking_group)
        if blocking_state is None:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"blocking group {blocking_group!r} not in state.groups",
            )
        if blocking_slot < 0 or blocking_slot >= len(blocking_state.selected_poses):
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"blocking_slot {blocking_slot} out of range "
                    f"(group {blocking_group!r} has {len(blocking_state.selected_poses)} selected_poses)"
                ),
            )
        actual_blocking_pose_id = blocking_state.selected_poses[blocking_slot]
        if actual_blocking_pose_id != blocking_pose_id:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"blocking_pose_id mismatch: cert={blocking_pose_id!r}, "
                    f"state.selected_poses[{blocking_slot}]={actual_blocking_pose_id!r}"
                ),
            )
        # 3c. front_cell ∈ occupied_cells(blocking_pose_id) — 防 attacker 让 cell_owner
        # mock 假占, 但 真实 blocking pose 不实际包含 front_cell.
        blocking_pose = find_pose(state, blocking_group, blocking_pose_id)
        if blocking_pose is None:
            return ValidationResult(
                kind="schema_err",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"cannot locate blocking pose {blocking_group}::{blocking_pose_id} — "
                    f"candidate_placements / instance_to_facility_type 未 inject"
                ),
            )
        occupied = {tuple(c) for c in blocking_pose.get("occupied_cells", [])}
        if tuple(front_cell) not in occupied:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"front_cell {front_cell} not in blocking_pose "
                    f"{blocking_pose_id!r} occupied_cells (实际不阻挡 port)"
                ),
            )

        # 4. cert ↔ cut.literals multiset 绑定 (GPT pro round 2 P0-2 fix).
        #
        # Adversarial 反例: cert blocker pose=p013 但 cut.literals 写 p014 (同
        # group 不同 pose) → 拿 p013 证错剪 p014. multiset 必须精确等. slot
        # 是 anonymous (state_machine_v2 §5), 不参与 binding — 只验 (group_id,
        # pose_id) multiset.
        expected_pairs: Counter = Counter([
            (facility_group, facility_pose_id),
            (blocking_group, blocking_pose_id),
        ])
        # Step A 入口已 guard literals not None & len >= 2 → mypy narrow 之后 deref 安全
        actual_pairs: Counter = Counter(
            (lit.slot_ref.group_id, lit.pose_id) for lit in cut.literals
        )
        if expected_pairs != actual_pairs:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"cert ↔ literals multiset mismatch: "
                    f"cert={dict(expected_pairs)}, literals={dict(actual_pairs)}"
                ),
            )

        # 5. port 真存在 facility pose (Gap 9 fix)
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

        # 5. cut.literals schema 已在入口 guard (python -O 安全)

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
