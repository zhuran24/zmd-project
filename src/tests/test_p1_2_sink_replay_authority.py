"""P1.2 regression coverage for data-rooted sink-side proof authority."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import src.search.benders_loop as benders_loop_module
import src.search.exact_campaign as exact_campaign_module
import src.search.outer_search as outer_search_module
from src.io.delivery_manifest import (
    delivery_manifest_output_path,
    export_certified_delivery_manifest,
)
from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE
from src.search.benders_loop import run_benders_for_ghost_rect
from src.search.candidate_proof_replay import (
    CANDIDATE_PROOF_FIELD,
    build_candidate_replay_proof,
    project_candidate_records_for_sink,
)
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.certified_surface import evaluate_certified_delivery_surface
from src.search.exact_campaign import (
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    ExactCampaign,
    terminal_certified_final_result_violation_for_project,
)
from src.tests.verified_producer_test_support import seal_test_candidate_status


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _build_single_pose_project(root: Path, *, width: int = 2, height: int = 1) -> Path:
    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": width, "height": height},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "tiny_facility": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": False,
                }
            },
        },
    )
    poses = [
        {
            "pose_id": "tiny_corner",
            "anchor": {"x": 0, "y": 0},
            "pose_params": {"orientation": 0, "port_mode": "default"},
            "occupied_cells": [[0, 0]],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": None,
        }
    ]
    if width >= 3 and height >= 3:
        poses.append(
            {
                "pose_id": "tiny_center",
                "anchor": {"x": 1, "y": 1},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[1, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        )
    _write_json(
        root / "data" / "preprocessed" / "candidate_placements.json",
        {"facility_pools": {"tiny_facility": poses}},
    )
    instances = [
        {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "operation_type": "",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(
        root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        instances,
    )
    _write_json(
        root / "data" / "preprocessed" / "all_facility_instances.json",
        instances,
    )
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )
    return root


def _fake_solution(*, ghost_w: int, ghost_h: int) -> dict[str, Any]:
    return {
        "ghost_pick": {
            "instance_id": "ghost_pick",
            "facility_type": "ghost_rect",
            "pose_idx": 0,
            "pose_id": "ghost_anchor::0,0",
            "anchor": {"x": 0, "y": 0},
            "is_mandatory": False,
            "bound_type": "ghost_rect",
            "solve_mode": "certified_exact",
            "claimed_w": ghost_w,
            "claimed_h": ghost_h,
        },
        "tiny_001": {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "operation_type": "",
            "pose_idx": 0,
            "pose_id": "tiny_corner",
            "anchor": {"x": 0, "y": 0},
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_mode": "certified_exact",
        },
    }


def _write_false_certified_claim(campaign: ExactCampaign) -> None:
    solution = _fake_solution(ghost_w=2, ghost_h=1)
    proof = build_candidate_replay_proof(
        campaign,
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=solution,
    )
    campaign._mark_candidate_result_from_verified_producer(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=solution,
        candidate_proof=proof,
        proof_summary={"claim_source": "mutated_writer"},
    )


def _install_false_terminal_claim(campaign: ExactCampaign) -> dict[str, Any]:
    _write_false_certified_claim(campaign)
    final_result = {
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {
            "tiny_001": dict(_fake_solution(ghost_w=2, ghost_h=1)["tiny_001"])
        },
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"solve_mode": "certified_exact"},
    }
    candidate_generation = {
        "max_w": 2,
        "max_h": 1,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 2,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 2,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(
        **candidate_generation_kwargs(candidate_generation)
    )
    campaign.state["final_result"] = final_result
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=RUN_STATUS_CERTIFIED,
    )
    campaign.state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=campaign.state["candidates"],
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    campaign.save()
    return final_result


def _mutate_named_closure_cell(function: Any, name: str, value: Any) -> None:
    freevars = tuple(function.__code__.co_freevars)
    assert name in freevars
    closure = function.__closure__
    assert closure is not None
    closure[freevars.index(name)].cell_contents = value


def test_p1_2_mutating_verified_writer_closure_cell_cannot_publish_false_certified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_single_pose_project(tmp_path / "closure_cell")
    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)

    def validator(_status: str) -> bool:
        return False

    def verified_writer(
        self: ExactCampaign,
        ghost_w: int,
        ghost_h: int,
        status: str,
        **kwargs: Any,
    ) -> None:
        if not validator(status):
            raise PermissionError("writer validator rejected claim")
        self.mark_candidate_result(ghost_w, ghost_h, status, **kwargs)

    _mutate_named_closure_cell(verified_writer, "validator", lambda _status: True)
    monkeypatch.setattr(
        ExactCampaign,
        "_mark_candidate_result_from_verified_producer",
        verified_writer,
    )
    _write_false_certified_claim(campaign)

    projected, violations = project_candidate_records_for_sink(
        state=campaign.state,
        project_root=root,
        campaign_path=campaign.path,
        require_record_solution_match=True,
    )
    assert campaign.state["candidates"]["2x1"]["status"] == RUN_STATUS_CERTIFIED
    assert projected["2x1"]["status"] == "UNPROVEN"
    assert "status_mismatch" in violations["2x1"]
    assert "replayed=INFEASIBLE" in violations["2x1"]


def test_p1_2_forged_proof_bearing_infeasible_cannot_prune_better_feasible_candidate(
    tmp_path: Path,
) -> None:
    root = _build_single_pose_project(tmp_path / "false_infeasible", width=3, height=3)
    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)
    proof = build_candidate_replay_proof(campaign, 3, 2, RUN_STATUS_INFEASIBLE)
    campaign._mark_candidate_result_from_verified_producer(
        3,
        2,
        RUN_STATUS_INFEASIBLE,
        candidate_proof=proof,
        proof_summary={"claim_source": "forged_infeasible"},
    )
    candidates = generate_candidate_sizes(
        max_w=3,
        max_h=3,
        min_side=1,
        max_aspect_ratio=None,
        area_upper_bound=8,
        start_area=None,
    )

    frontier = outer_search_module._compute_exact_frontier_state(
        candidates,
        campaign,
        grid_w=3,
        grid_h=3,
    )
    assert any((w, h) == (3, 2) for _area, w, h in frontier["potential_domain"])
    assert campaign.state["candidates"]["3x2"]["status"] == "UNPROVEN"
    assert CANDIDATE_PROOF_FIELD not in campaign.state["candidates"]["3x2"]
    assert "status_mismatch" in frontier["sink_replay_violations"]["3x2"]
    assert "replayed=CERTIFIED" in frontier["sink_replay_violations"]["3x2"]


def test_p1_2_forged_certified_cannot_enter_terminal_manifest_or_public_surface(
    tmp_path: Path,
) -> None:
    root = _build_single_pose_project(tmp_path / "false_terminal")
    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)
    _install_false_terminal_claim(campaign)

    violation = terminal_certified_final_result_violation_for_project(
        campaign.state,
        project_root=root,
        campaign_path=campaign.path,
    )
    # The terminal sink may reject even earlier on a project/domain precheck;
    # either way the forged strong record never becomes publication authority.
    assert violation is not None

    manifest_path = delivery_manifest_output_path(root)
    with pytest.raises(ValueError):
        export_certified_delivery_manifest(
            project_root=root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )
    assert not manifest_path.exists()

    verdict = evaluate_certified_delivery_surface(
        project_root=root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )
    assert verdict.publishable is False
    assert verdict.campaign_terminal_full_frontier_valid is False


def test_p1_2_module_rebinding_monkeypatch_and_test_helper_do_not_grant_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_single_pose_project(tmp_path / "rebinding_helper", width=3, height=3)
    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)

    def rebound_outer_entry(target: ExactCampaign) -> None:
        target.mark_candidate_result(
            3,
            2,
            RUN_STATUS_INFEASIBLE,
            proof_summary={"claim_source": "rebound_outer_symbol"},
        )

    monkeypatch.setattr(outer_search_module, "run_outer_search", rebound_outer_entry)
    monkeypatch.setattr(
        benders_loop_module,
        "run_benders_for_ghost_rect",
        lambda **_kwargs: (RUN_STATUS_INFEASIBLE, None),
    )
    outer_search_module.run_outer_search(campaign)
    seal_test_candidate_status(campaign, "3x2", RUN_STATUS_INFEASIBLE)

    projected, violations = project_candidate_records_for_sink(
        state=campaign.state,
        project_root=root,
        campaign_path=campaign.path,
    )
    assert projected["3x2"]["status"] == "UNPROVEN"
    assert "replayed=CERTIFIED" in violations["3x2"]
    assert not hasattr(exact_campaign_module, "_grant_candidate_status_freshness_from_verified_producer")
    assert ExactCampaign._mark_candidate_result_from_verified_producer.__closure__ is None


def test_p1_2_strong_status_without_sink_replayable_proof_fails_closed(
    tmp_path: Path,
) -> None:
    root = _build_single_pose_project(tmp_path / "missing_proof", width=3, height=3)
    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_result(
        3,
        2,
        RUN_STATUS_INFEASIBLE,
        proof_summary={"claim_source": "no_replay_material"},
    )

    projected, violations = project_candidate_records_for_sink(
        state=campaign.state,
        project_root=root,
        campaign_path=campaign.path,
    )
    assert CANDIDATE_PROOF_FIELD not in campaign.state["candidates"]["3x2"]
    assert projected["3x2"]["status"] == "UNPROVEN"
    assert violations["3x2"] == "candidate_sink_replay_proof_missing:3x2"


def test_p1_2_legitimate_certified_exact_path_survives_all_sink_replays(
    tmp_path: Path,
) -> None:
    root = _build_single_pose_project(tmp_path / "legitimate")
    status, result = outer_search_module.run_outer_search(
        project_root=root,
        solve_mode="certified_exact",
        master_seconds=10.0,
        binding_seconds=10.0,
        routing_seconds=10.0,
        flow_seconds=10.0,
        benders_max_iter=10,
        campaign_hours=1.0,
        resume_campaign=False,
        area_upper_bound=2,
        min_side=1,
        parallel_processes=1,
        disable_master_warm_start=True,
    )
    assert status == RUN_STATUS_CERTIFIED
    assert isinstance(result, Mapping)

    campaign_path = root / "data" / "checkpoints" / "exact_campaign_state.json"
    state = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert state["candidates"]["1x1"]["status"] == RUN_STATUS_CERTIFIED
    assert CANDIDATE_PROOF_FIELD in state["candidates"]["1x1"]
    assert (
        terminal_certified_final_result_violation_for_project(
            state,
            project_root=root,
            campaign_path=campaign_path,
        )
        is None
    )

    manifest_path, manifest = export_certified_delivery_manifest(
        project_root=root,
        campaign_state=state,
        campaign_path=campaign_path,
    )
    assert manifest_path.exists()
    assert manifest["best_certified_result"]["search_status"] == RUN_STATUS_CERTIFIED
    verdict = evaluate_certified_delivery_surface(
        project_root=root,
        campaign_state=state,
        campaign_path=campaign_path,
        delivery_manifest=manifest,
    )
    assert verdict.publishable is True
