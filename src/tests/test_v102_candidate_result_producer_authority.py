"""Regression coverage for proof-bearing candidate producer authority."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.search.exact_campaign as exact_campaign_module
from src.io.delivery_manifest import export_certified_delivery_manifest
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.certified_surface import (
    evaluate_certified_delivery_surface,
    save_certified_final_solution_and_blueprint,
)
from src.search.exact_campaign import (
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    ExactCampaign,
    _grant_candidate_status_freshness_from_verified_producer,
    _mark_candidate_status_fresh_for_current_process,
    has_valid_terminal_full_frontier_certified_evidence_for_project,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _build_toy_project(root: Path) -> dict[str, list[dict[str, object]]]:
    facility_pools: dict[str, list[dict[str, object]]] = {
        "T": [
            {
                "pose_id": "T_center",
                "anchor": {"x": 1, "y": 1},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[1, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
            },
            {
                "pose_id": "T_corner",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            },
        ]
    }
    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 3, "height": 3},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {"T": {"dimensions": {"w": 1, "h": 1}}},
        },
    )
    _write_json(
        root / "data" / "preprocessed" / "candidate_placements.json",
        {"facility_pools": facility_pools},
    )
    _write_json(
        root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "must_place",
                "facility_type": "T",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )
    return facility_pools


def test_public_candidate_writer_cannot_publish_forged_strong_frontier(
    tmp_path: Path,
) -> None:
    root = tmp_path / "forged_public_writer"
    facility_pools = _build_toy_project(root)
    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)

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
    candidates = generate_candidate_sizes(
        **candidate_generation_kwargs(candidate_generation)
    )
    certified_solution = {
        "ghost_pick": {
            "pose_idx": 0,
            "pose_id": "ghost_anchor::0,0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "ghost_rect",
        },
        "must_place": {
            "facility_type": "T",
            "pose_idx": 0,
            "pose_id": "T_center",
            "anchor": {"x": 1, "y": 1},
        },
    }
    for _area, ghost_w, ghost_h in candidates:
        if (ghost_w, ghost_h) == (3, 1):
            campaign.mark_candidate_result(
                ghost_w,
                ghost_h,
                "CERTIFIED",
                solution=certified_solution,
                proof_summary={"producer": "untrusted-public-writer"},
            )
        else:
            campaign.mark_candidate_result(
                ghost_w,
                ghost_h,
                "INFEASIBLE",
                proof_summary={"producer": "untrusted-public-writer"},
            )

    final_result = {
        "ghost_rect": {"w": 3, "h": 1, "area": 3, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {
            "must_place": {
                "facility_type": "T",
                "pose_idx": 0,
                "pose_id": "T_center",
                "anchor": {"x": 1, "y": 1},
            }
        },
        "search_status": "CERTIFIED",
    }
    campaign.state["final_result"] = final_result
    campaign.state["final_status"] = "CERTIFIED"
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status="CERTIFIED",
    )
    campaign.state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=campaign.state["candidates"],
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    campaign.save()
    save_certified_final_solution_and_blueprint(
        project_root=root,
        result=final_result,
        facility_pools=facility_pools,
    )

    # Ground-truth geometry: the mandatory 1x1 pose at (0,0) is disjoint from
    # a strictly better 3x2 ghost rectangle anchored at (0,1).
    assert set(map(tuple, facility_pools["T"][1]["occupied_cells"])).isdisjoint(
        {(x, y) for y in (1, 2) for x in range(3)}
    )
    assert campaign.state["candidates"]["3x2"]["status"] == "INFEASIBLE"

    assert not has_valid_terminal_full_frontier_certified_evidence_for_project(
        campaign.state,
        project_root=root,
    )
    assert campaign.best_certified_result() is None
    with pytest.raises(ValueError):
        export_certified_delivery_manifest(
            project_root=root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )
    surface = evaluate_certified_delivery_surface(
        project_root=root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )
    assert surface.publishable is False


def test_private_verified_producer_writer_rejects_caller_minted_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "forged_private_writer"
    _build_toy_project(root)
    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(3, 2)

    with pytest.raises(
        PermissionError,
        match="verified_candidate_producer_caller_not_run_outer_search",
    ):
        campaign._mark_candidate_result_from_verified_producer(
            3,
            2,
            "INFEASIBLE",
            proof_summary={"producer": "attacker-direct-private-method"},
        )

    assert campaign.state["candidates"]["3x2"]["status"] == "RUNNING"

    campaign.mark_candidate_result(
        3,
        2,
        "INFEASIBLE",
        proof_summary={"producer": "attacker-public-writer"},
    )
    with pytest.raises(
        PermissionError,
        match="verified_candidate_freshness_grant_caller_not_verified_writer",
    ):
        _grant_candidate_status_freshness_from_verified_producer(
            campaign,
            "3x2",
            "INFEASIBLE",
        )

    with pytest.raises(PermissionError, match="direct candidate freshness sealing"):
        _mark_candidate_status_fresh_for_current_process(
            campaign,
            "3x2",
            "INFEASIBLE",
        )


def test_freshness_registry_is_not_exposed_as_mutable_module_state() -> None:
    assert not hasattr(
        exact_campaign_module,
        "_FRESH_PROOF_BEARING_CANDIDATE_RECORDS_BY_STATE_ID",
    )
    assert not hasattr(exact_campaign_module, "_candidate_freshness_bucket")
    assert not hasattr(exact_campaign_module, "_candidate_record_freshness_token")
