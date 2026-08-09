from __future__ import annotations

import base64
import hashlib
import json
import uuid
from pathlib import Path

from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE
from src.search.candidate_proof_replay import canonical_digest
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.exact_campaign import (
    CAMPAIGN_INSTANCE_ID_KEY,
    CANDIDATE_PROPOSED_STATUS,
    DEFAULT_CAMPAIGN_FILENAME,
    PROPOSAL_READY_MARKER_AUTHORITY,
    SUPERVISOR_PROPOSAL_STATE_KEY,
    SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION,
    SUPERVISOR_SEAL_AUTHORITY,
    SUPERVISOR_SEAL_SCHEMA_VERSION,
    SUPERVISOR_SEAL_STATE_KEY,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    atomic_write_json,
)
from src.search.terminal_fixed_witness_verifier import canonical_state_bytes_for_fixed_witness
from src.search.pr2_l0_fixed_witness_core import verify_terminal_fixed_witness


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _write_project(root: Path) -> dict[str, list[dict[str, object]]]:
    ghost_cells = {(2, 2), (2, 3), (3, 2), (3, 3)}
    box_cells = [
        (x, y)
        for y in range(4)
        for x in range(4)
        if (x, y) not in ghost_cells and (x, y) != (0, 0)
    ]
    facility_pools: dict[str, list[dict[str, object]]] = {
        "solid": [
            {
                "pose_id": "solid_at_0_0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        ],
        "protocol_storage_box": [
            {
                "pose_id": f"box_at_{x}_{y}",
                "anchor": {"x": x, "y": y},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[x, y]],
                "input_port_cells": [
                    {"x": x, "y": y, "dir": direction}
                    for direction in ("N", "W", "S")
                ],
                "output_port_cells": [
                    {"x": x, "y": y, "dir": direction}
                    for direction in ("N", "E", "S")
                ],
            }
            for x, y in box_cells
        ],
    }
    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 4, "height": 4},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "solid": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": False,
                },
            },
            "commodity_metadata": {
                "demo_input": {"source_kind": "internal_only", "sink_kind": "generic_input"},
            },
        },
    )
    _write_json(
        root / "rules" / "preprocess_plan.json",
        {
            "utility_operations": {
                "box_sink": {
                    "facility_type": "protocol_storage_box",
                    "generic_input_slots": 3,
                }
            }
        },
    )
    _write_json(root / "data" / "preprocessed" / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(
        root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "solid_001",
                "facility_type": "solid",
                "operation_type": "",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    # With no mandatory provider, box_sink has 3 physical generic-input slots,
    # so this toy project requires one protocol box.
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_inputs": {"demo_input": 1}, "required_generic_outputs": {}},
    )
    return facility_pools


def _placement_solution(facility_pools: dict[str, list[dict[str, object]]]) -> dict[str, dict[str, object]]:
    solution: dict[str, dict[str, object]] = {
        "solid_001": {
            "facility_type": "solid",
            "pose_idx": 0,
            "pose_id": "solid_at_0_0",
            "anchor": {"x": 0, "y": 0},
            "instance_id": "solid_001",
            "operation_type": "",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_mode": "certified_exact",
        }
    }
    for pose_idx, pose in enumerate(facility_pools["protocol_storage_box"]):
        pose_id = str(pose["pose_id"])
        solution[f"pose_optional::protocol_storage_box::{pose_id}"] = {
            "facility_type": "protocol_storage_box",
            "pose_idx": int(pose_idx),
            "pose_id": pose_id,
            "anchor": dict(pose["anchor"]),
            "is_mandatory": False,
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        }
    return solution


def _candidate_record(
    ghost_w: int,
    ghost_h: int,
    status: str,
    *,
    solution: dict[str, object] | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": ghost_w * ghost_h},
        "attempts": 1,
        "started_at": "2026-06-11T00:00:00Z",
        "updated_at": "2026-06-11T00:00:01Z",
        "finished_at": "2026-06-11T00:00:01Z",
        "status": status,
        "proof_summary": {"test": "v94_terminal_protocol_storage_surplus"},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }
    if solution is not None:
        record["solution"] = solution
    return record


def _terminal_state(root: Path) -> dict[str, object]:
    facility_pools = _write_project(root)
    placement_solution = _placement_solution(facility_pools)
    final_result = {
        "search_status": RUN_STATUS_CERTIFIED,
        "ghost_rect": {"w": 2, "h": 2, "area": 4, "anchor_x": 2, "anchor_y": 2},
        "placement_solution": placement_solution,
        "search_stats": {"campaign_resumed": False},
    }
    candidate_generation = {
        "max_w": 4,
        "max_h": 4,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 14,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 14,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    certified_solution = dict(placement_solution)
    certified_solution["ghost_pick"] = {
        "pose_idx": 8,
        "pose_id": "ghost_anchor::2,2",
        "anchor": {"x": 2, "y": 2},
        "facility_type": "ghost_rect",
    }
    candidate_records: dict[str, object] = {}
    for _area, ghost_w, ghost_h in candidates:
        key = f"{ghost_w}x{ghost_h}"
        if (ghost_w, ghost_h) == (2, 2):
            certified_record = _candidate_record(
                ghost_w,
                ghost_h,
                RUN_STATUS_CERTIFIED,
                solution=certified_solution,
            )
            certified_record["candidate_proof"] = {
                "solution_digest": canonical_digest(certified_solution),
            }
            candidate_records[key] = certified_record
        else:
            candidate_records[key] = _candidate_record(ghost_w, ghost_h, RUN_STATUS_INFEASIBLE)
    return {
        "declare_mode": "strict",
        "final_status": RUN_STATUS_CERTIFIED,
        "last_stop_reason": {
            "status": RUN_STATUS_CERTIFIED,
            "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        },
        "final_result": final_result,
        "candidates": candidate_records,
        "terminal_frontier_evidence": build_terminal_frontier_evidence(
            candidates=candidates,
            candidate_records=candidate_records,
            final_result=final_result,
            candidate_generation=candidate_generation,
        ),
    }


def _build_certified_state_with_forged_seal(
    base_state: dict[str, object],
    project_root: Path,
) -> tuple[dict[str, object], Path]:
    """
    Build a structurally valid certified state with a hand-crafted supervisor_seal and
    write it to the canonical checkpoint path.

    The seal satisfies every structural gate in _supervisor_seal_state_violation so the
    validator proceeds past it to the content-level checks (including the surplus
    protocol-storage-box detection).  The seal carries no real proof authority; it is
    constructed here only so the test can exercise the content validator.

    Construction follows the inverse of the supervisor_seal() transition:
      1. Derive a proposal_state from the certified state (reverse the transition).
      2. Compute certified_state_sha256 over the certified payload (no seal block).
      3. Assemble the seal record; embed the proposal as proposal_authority_b64.
      4. Verify that _supervisor_certified_transition_violation(proposal, certified, seal)
         would accept (by construction the expected dict == certified_state).
    """
    campaign_instance_id = uuid.uuid4().hex  # 32 hex chars, satisfies _valid_campaign_instance_id
    run_id = "test-v94-surplus-seal"        # ASCII letters/digits, satisfies _valid_supervisor_proposal_run_id
    stop_ts = "2026-06-11T00:00:01Z"
    updated_at = "2026-06-11T00:00:02Z"
    sealed_at = "2026-06-11T00:00:03Z"

    # --- Certified state without seal ---
    # Must have: campaign_instance_id, updated_at, last_stop_reason.updated_at (all required by
    # _supervisor_certified_transition_violation timestamp checks).
    certified_last_stop: dict[str, object] = {
        "status": RUN_STATUS_CERTIFIED,
        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        "updated_at": stop_ts,
    }
    certified_final_result = dict(base_state["final_result"])  # type: ignore[arg-type]
    # search_status is already "CERTIFIED" in base_state["final_result"]

    certified_state_without_seal: dict[str, object] = {
        "declare_mode": base_state["declare_mode"],
        "final_status": base_state["final_status"],
        "final_result": certified_final_result,
        "candidates": base_state["candidates"],
        "terminal_frontier_evidence": base_state["terminal_frontier_evidence"],
        CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
        "last_stop_reason": certified_last_stop,
        "updated_at": updated_at,
    }

    # --- Proposal state (CANDIDATE_PROPOSED; the "before" side of the transition) ---
    # The transition sets final_status→CERTIFIED and final_result.search_status→CERTIFIED,
    # removes supervisor_proposal, adds supervisor_seal, last_stop_reason, updated_at.
    # So the proposal state carries those same data fields with CANDIDATE_PROPOSED status.
    proposal_final_result: dict[str, object] = {
        **certified_final_result,
        "search_status": CANDIDATE_PROPOSED_STATUS,
    }
    supervisor_proposal: dict[str, object] = {
        "schema_version": SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION,
        "authority": PROPOSAL_READY_MARKER_AUTHORITY,
        "run_id": run_id,
        CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
    }
    proposal_state: dict[str, object] = {
        "declare_mode": "strict",
        "final_status": CANDIDATE_PROPOSED_STATUS,
        "final_result": proposal_final_result,
        "candidates": base_state["candidates"],
        "terminal_frontier_evidence": base_state["terminal_frontier_evidence"],
        CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
        SUPERVISOR_PROPOSAL_STATE_KEY: supervisor_proposal,
    }

    # Serialise proposal with the same canonical encoder the validator will decode with.
    proposal_bytes = canonical_state_bytes_for_fixed_witness(proposal_state)
    proposal_sha256 = hashlib.sha256(proposal_bytes).hexdigest()
    proposal_b64 = base64.b64encode(proposal_bytes).decode("ascii")

    # Hash of the certified payload without the seal block (mirrors _certified_state_payload_sha256).
    certified_payload_sha256 = hashlib.sha256(
        canonical_state_bytes_for_fixed_witness(certified_state_without_seal)
    ).hexdigest()

    # --- Seal record ---
    seal_record: dict[str, object] = {
        "schema_version": SUPERVISOR_SEAL_SCHEMA_VERSION,
        "authority": SUPERVISOR_SEAL_AUTHORITY,
        "transition": "proposal_to_certified_v1",
        "proposal_run_id": run_id,
        "proposal_checkpoint_sha256": proposal_sha256,
        "proposal_authority_b64": proposal_b64,
        CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
        "certified_state_sha256": certified_payload_sha256,
        "sealed_at": sealed_at,
    }

    # --- Full certified state ---
    certified_state: dict[str, object] = {
        **certified_state_without_seal,
        SUPERVISOR_SEAL_STATE_KEY: seal_record,
    }

    # Write to canonical checkpoint path (atomic_write_json creates parent dirs).
    checkpoint_path = project_root / "data" / "checkpoints" / DEFAULT_CAMPAIGN_FILENAME
    atomic_write_json(checkpoint_path, certified_state)

    return certified_state, checkpoint_path


def test_terminal_fixed_witness_rejects_unbound_surplus_protocol_storage_boxes(
    tmp_path: Path,
) -> None:
    state = _terminal_state(tmp_path)

    verdict = verify_terminal_fixed_witness(state=state, project_root=tmp_path)

    assert verdict.publishable is False
    assert (
        verdict.reason
        == "terminal_fixed_witness_unbound_storage_box_violates_dominance_rule"
    )
    assert verdict.details["minimum_inevitable_unbound_storage_box_count"] == 10
