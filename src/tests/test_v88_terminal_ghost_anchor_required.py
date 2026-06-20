from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.io.serializer import build_blueprint_payload_from_certified_result
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.exact_campaign import (
    CAMPAIGN_SCHEMA_VERSION,
    PROOF_SUMMARY_SCHEMA_VERSION,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    ExactCampaign,
    _default_master_domain_contract,
    compute_exact_artifact_hashes,
    terminal_certified_final_result_violation_for_project,
)
from src.search.outer_search import _build_certified_result
from src.tests.verified_producer_test_support import seal_test_candidate_status


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _terminal_state_without_ghost_anchor(project_root: Path) -> tuple[dict, dict]:
    rules = {
        "globals": {
            "grid": {"width": 3, "height": 3},
            "empty_rectangle": {
                "objective": "max_lex_area_min_side",
                "min_side_admissibility": 1,
            },
        },
        "facility_templates": {
            "solid": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    facility_pools = {
        "solid": [
            {
                "pose_id": "solid_at_0_0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        ]
    }
    mandatory_instances = [
        {
            "instance_id": "solid_001",
            "facility_type": "solid",
            "operation_type": "",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(project_root / "rules" / "canonical_rules.json", rules)
    _write_json(project_root / "data" / "preprocessed" / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(project_root / "data" / "preprocessed" / "mandatory_exact_instances.json", mandatory_instances)
    _write_json(project_root / "data" / "preprocessed" / "generic_io_requirements.json", {"required_generic_inputs": {}, "required_generic_outputs": {}})

    placement_solution = {"solid_001": {"facility_type": "solid", "pose_idx": 0}}
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 3, "h": 2, "area": 6},
        "placement_solution": placement_solution,
        "search_stats": {},
    }
    candidate_generation = {
        "max_w": 3,
        "max_h": 3,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 8,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 8,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    records = {}
    for area, width, height in candidates:
        status = "CERTIFIED" if (width, height) == (3, 2) else "INFEASIBLE"
        record = {
            "ghost_rect": {"w": width, "h": height, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"test": "v88_missing_anchor"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            record["solution"] = placement_solution
        records[f"{width}x{height}"] = record

    state = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "solve_mode": "certified_exact",
        "campaign_hours": 1.0,
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:02Z",
        "artifact_hashes": compute_exact_artifact_hashes(project_root),
        "master_domain_contract": _default_master_domain_contract(),
        "proof_summary_schema_version": PROOF_SUMMARY_SCHEMA_VERSION,
        "reset_reason": None,
        "final_result": final_result,
        "final_status": "CERTIFIED",
        "last_stop_reason": {
            "status": "CERTIFIED",
            "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
            "updated_at": "2026-06-10T00:00:02Z",
        },
        "terminal_frontier_evidence": build_terminal_frontier_evidence(
            candidates=candidates,
            candidate_records=records,
            final_result=final_result,
            candidate_generation=candidate_generation,
        ),
        "declare_mode": "strict",
        "candidates": records,
    }
    return state, facility_pools


def test_terminal_project_validator_requires_ghost_anchor(tmp_path: Path) -> None:
    state, _facility_pools = _terminal_state_without_ghost_anchor(tmp_path)

    assert (
        terminal_certified_final_result_violation_for_project(state, project_root=tmp_path)
        == "terminal_certified_final_result_ghost_rect_anchor_missing"
    )


def test_certified_blueprint_builder_rejects_missing_ghost_anchor(tmp_path: Path) -> None:
    state, facility_pools = _terminal_state_without_ghost_anchor(tmp_path)

    with pytest.raises(ValueError, match="anchor_x and anchor_y"):
        build_blueprint_payload_from_certified_result(
            result=state["final_result"],
            facility_pools=facility_pools,
        )


def test_outer_search_certified_result_carries_ghost_anchor() -> None:
    result = _build_certified_result(
        candidate=(6, 3, 2),
        solution={
            "ghost_pick": {"anchor": {"x": 0, "y": 1}},
            "solid_001": {"facility_type": "solid", "pose_idx": 0},
        },
        attempts=1,
        solve_mode="certified_exact",
        campaign_resumed=False,
        frontier_peak_size=1,
        derived_pruned_candidates=0,
        frontier_selection_policy="unit-test",
        frontier_candidate_metrics={},
    )

    assert result["ghost_rect"] == {"w": 3, "h": 2, "area": 6, "anchor_x": 0, "anchor_y": 1}
    assert "ghost_pick" not in result["placement_solution"]


def test_terminal_solution_match_ignores_candidate_record_ghost_marker(tmp_path: Path) -> None:
    # ④b sink replay: the CERTIFIED 3x2 candidate must be re-derived by an
    # isolated solver before the validator accepts it.  The test's point is that
    # the candidate record's stored ghost_pick marker is ignored by the terminal
    # solution-match comparison; that must still hold once the claim survives a
    # real replay.  On this toy 3x3 project both 3x2 and 2x3 are genuinely
    # CERTIFIED (tied objective); the generation order makes 3x2 the best, which
    # matches final_result.
    state, _facility_pools = _terminal_state_without_ghost_anchor(tmp_path)
    placement_solution = state["final_result"]["placement_solution"]
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 3, "h": 2, "area": 6, "anchor_x": 0, "anchor_y": 1},
        "placement_solution": placement_solution,
        "search_stats": {},
    }
    candidate_generation = dict(state["terminal_frontier_evidence"]["candidate_generation"])
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    # Replay-consistent candidate set: keep only the genuinely-CERTIFIED tied
    # rectangles.  The 3x2 record carries an extra ghost_pick marker that the
    # terminal solution-match comparison must strip/ignore.
    candidate_records = {
        "3x2": {
            "ghost_rect": {"w": 3, "h": 2, "area": 6},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": "CERTIFIED",
            "solution": {
                **placement_solution,
                "ghost_pick": {
                    "facility_type": "ghost_rect",
                    "pose_idx": 1,
                    "pose_id": "ghost_anchor::0,1",
                    "anchor": {"x": 0, "y": 1},
                },
            },
            "proof_summary": {"test": "v88_ignore_ghost_marker"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        },
        "2x3": {
            "ghost_rect": {"w": 2, "h": 3, "area": 6},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": "CERTIFIED",
            "solution": dict(placement_solution),
            "proof_summary": {"test": "v88_ignore_ghost_marker"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        },
    }
    terminal_frontier_evidence = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=candidate_records,
        final_result=final_result,
        candidate_generation=candidate_generation,
    )

    campaign = ExactCampaign.load_or_create(tmp_path, campaign_hours=1.0, resume=False)
    campaign.state["final_result"] = final_result
    campaign.state["final_status"] = "CERTIFIED"
    campaign.state["last_stop_reason"] = {
        "status": "CERTIFIED",
        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        "updated_at": "2026-06-10T00:00:02Z",
    }
    campaign.state["terminal_frontier_evidence"] = terminal_frontier_evidence
    campaign.state["declare_mode"] = "strict"
    campaign.state["candidates"] = candidate_records
    seal_test_candidate_status(campaign, "3x2", "CERTIFIED")
    seal_test_candidate_status(campaign, "2x3", "CERTIFIED")

    assert (
        terminal_certified_final_result_violation_for_project(
            campaign.state,
            project_root=tmp_path,
            campaign_path=campaign.path,
        )
        is None
    )
