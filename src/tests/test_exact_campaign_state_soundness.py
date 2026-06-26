from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.cut_manager import (
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNKNOWN,
)
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search import outer_search as outer_search_module
from src.search.certified_surface import certified_delivery_surface_artifact_paths
from src.search.exact_campaign import (
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    ExactCampaign,
    validate_exact_campaign_resume_state,
)
from src.search.outer_search import run_outer_search
from src.tests.certified_frontier_helpers import persist_forged_terminal_certified_state
from src.tests.test_v89_terminal_ghost_pick_protocol_validation import _write_project


def _certified_solution() -> dict[str, object]:
    return {
        "solid_001": {"facility_type": "solid", "pose_idx": 0},
        "ghost_pick": {
            "facility_type": "ghost_rect",
            "pose_idx": 1,
            "pose_id": "ghost_anchor::1,0",
            "anchor": {"x": 1, "y": 0},
        },
    }


def _forge_legacy_terminal_certified_stop(campaign: ExactCampaign) -> None:
    campaign.state["last_stop_reason"] = {
        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        "status": RUN_STATUS_CERTIFIED,
        "updated_at": "2026-03-16T00:00:00Z",
    }
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED


def test_candidate_strong_result_survives_rerun_and_requires_fresh_solution(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)

    campaign.mark_candidate_started(2, 3)
    campaign.mark_candidate_result(
        2,
        3,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )

    campaign.mark_candidate_started(2, 3)
    record_after_start = campaign.get_candidate_record(2, 3)
    assert record_after_start is not None
    assert record_after_start["status"] == RUN_STATUS_CERTIFIED
    assert record_after_start["solution"] == _certified_solution()

    with pytest.raises(ValueError, match="fresh solution"):
        campaign.mark_candidate_result(
            2,
            3,
            RUN_STATUS_CERTIFIED,
            proof_summary={"master_status": RUN_STATUS_CERTIFIED},
            exact_safe_cuts=[],
            loaded_exact_safe_cut_count=0,
            generated_exact_safe_cut_count=0,
        )

    campaign.mark_candidate_result(
        2,
        3,
        RUN_STATUS_UNKNOWN,
        proof_summary={"master_status": RUN_STATUS_UNKNOWN},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )

    record_after_weak_result = campaign.get_candidate_record(2, 3)
    assert record_after_weak_result is not None
    assert record_after_weak_result["status"] == RUN_STATUS_CERTIFIED
    assert record_after_weak_result["solution"] == _certified_solution()
    assert any(
        entry.get("event") == "CANDIDATE_STRONG_STATUS_DOWNGRADE_BLOCKED"
        and entry.get("incoming_status") == RUN_STATUS_UNKNOWN
        for entry in campaign.get_audit_log()
    )


def test_resume_rejects_non_certified_candidate_with_stale_solution(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 3)
    campaign.mark_candidate_result(
        2,
        3,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )

    campaign.state["candidates"]["2x3"]["status"] = RUN_STATUS_UNKNOWN

    assert (
        validate_exact_campaign_resume_state(
            campaign.state,
            campaign.artifact_hashes,
            project_root=project_root,
        )
        == "candidate_non_certified_solution_present:2x3"
    )


def test_resume_rejects_null_campaign_hours_without_crashing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.state["campaign_hours"] = None
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "campaign_hours_invalid"


def test_resume_rejects_torn_top_level_timestamp_and_metadata_fields(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)

    created_at_campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    created_at_campaign.state["created_at"] = None
    created_at_campaign.path.write_text(
        json.dumps(created_at_campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_created_at = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_created_at.resumed is False
    assert resumed_created_at.reset_reason == "created_at_invalid"

    updated_at_campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    updated_at_campaign.state["updated_at"] = []
    updated_at_campaign.path.write_text(
        json.dumps(updated_at_campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_updated_at = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_updated_at.resumed is False
    assert resumed_updated_at.reset_reason == "updated_at_invalid"


def test_resume_rejects_torn_reset_reason_and_nonterminal_evidence_shape(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)

    reset_reason_campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    reset_reason_campaign.state["reset_reason"] = []
    reset_reason_campaign.path.write_text(
        json.dumps(reset_reason_campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_reset_reason = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_reset_reason.resumed is False
    assert resumed_reset_reason.reset_reason == "reset_reason_invalid"

    evidence_campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    evidence_campaign.state["terminal_frontier_evidence"] = []
    evidence_campaign.path.write_text(
        json.dumps(evidence_campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_evidence = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_evidence.resumed is False
    assert resumed_evidence.reset_reason == "terminal_frontier_evidence_invalid"


def test_resume_rejects_torn_candidate_timestamp_shapes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)

    campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    campaign.mark_candidate_started(2, 3)
    campaign.mark_candidate_result(
        2,
        3,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["candidates"]["2x3"]["started_at"] = []
    campaign.path.write_text(
        json.dumps(campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_started_at = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_started_at.resumed is False
    assert resumed_started_at.reset_reason == "candidate_invalid_timestamp:2x3:started_at"

    campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    campaign.mark_candidate_started(2, 3)
    campaign.mark_candidate_result(
        2,
        3,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["candidates"]["2x3"]["finished_at"] = []
    campaign.path.write_text(
        json.dumps(campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_finished_at = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_finished_at.resumed is False
    assert resumed_finished_at.reset_reason == "candidate_invalid_timestamp:2x3:finished_at"


def _write_three_cell_project(root: Path) -> None:
    def write_json(path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")

    write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 3, "height": 1},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "solid": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    write_json(
        root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "solid": [
                    {
                        "pose_id": "solid_0",
                        "anchor": {"x": 0, "y": 0},
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    },
                    {
                        "pose_id": "solid_1",
                        "anchor": {"x": 1, "y": 0},
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                        "occupied_cells": [[1, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    },
                    {
                        "pose_id": "solid_2",
                        "anchor": {"x": 2, "y": 0},
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                        "occupied_cells": [[2, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    },
                ],
            },
        },
    )
    instances = [
        {
            "instance_id": "solid_001",
            "facility_type": "solid",
            "operation_type": "solid_op",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    write_json(root / "data" / "preprocessed" / "mandatory_exact_instances.json", instances)
    write_json(root / "data" / "preprocessed" / "all_facility_instances.json", instances)
    write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )


def test_resume_drops_infeasible_statuses_before_terminal_certified_reuse(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_three_cell_project(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    solution = {
        "solid_001": {
            "facility_type": "solid",
            "pose_idx": 1,
            "pose_id": "solid_1",
            "anchor": {"x": 1, "y": 0},
            "orientation": 0,
            "port_mode": "default",
        },
        "ghost_pick": {
            "facility_type": "ghost_rect",
            "pose_idx": 0,
            "pose_id": "ghost_anchor::0,0",
            "anchor": {"x": 0, "y": 0},
        },
    }

    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution=solution,
        proof_summary={"master_status": "FEASIBLE"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_INFEASIBLE,
        proof_summary={"master_status": "INFEASIBLE", "forged_demo": True},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {"solid_001": dict(solution["solid_001"])},
        "search_stats": {"campaign_resumed": True, "solve_mode": "certified_exact"},
    }
    campaign.state["final_result"] = final_result
    _forge_legacy_terminal_certified_stop(campaign)
    candidate_generation = {
        "max_w": 3,
        "max_h": 1,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 2,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 2,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    campaign.state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=campaign.state["candidates"],
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    # Forged terminal full-frontier CERTIFIED without a valid supervisor_seal is
    # rejected outright by _validate_resume_state, so the campaign is reset
    # rather than demoting candidates through the sanitizer path.
    assert resumed.resumed is False
    assert resumed.reset_reason == "supervisor_seal_invalid"
    assert resumed.get_candidate_record(2, 1) is None
    assert resumed.state["final_status"] is None
    assert resumed.state["final_result"] is None
    assert resumed.state.get("terminal_frontier_evidence") is None

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        resume_campaign=True,
        max_attempts=0,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None


def test_resume_drops_certified_statuses_before_terminal_certified_reuse(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project_certified_replay"
    _write_three_cell_project(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    solution = {
        "solid_001": {
            "facility_type": "solid",
            "pose_idx": 2,
            "pose_id": "solid_2",
            "anchor": {"x": 2, "y": 0},
            "orientation": 0,
            "port_mode": "default",
        },
        "ghost_pick": {
            "facility_type": "ghost_rect",
            "pose_idx": 0,
            "pose_id": "ghost_anchor::0,0",
            "anchor": {"x": 0, "y": 0},
        },
    }

    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=solution,
        proof_summary={"master_status": "FEASIBLE", "routing_status": "FEASIBLE"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {"solid_001": dict(solution["solid_001"])},
        "search_stats": {"campaign_resumed": True, "solve_mode": "certified_exact"},
    }
    campaign.state["final_result"] = final_result
    _forge_legacy_terminal_certified_stop(campaign)
    candidate_generation = {
        "max_w": 3,
        "max_h": 1,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 2,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 2,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    campaign.state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=campaign.state["candidates"],
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    # A checkpoint claiming terminal full-frontier CERTIFIED without a valid
    # supervisor_seal is forged terminal authority, not a normal resume state.
    # _validate_resume_state rejects it outright (seal violation), so the whole
    # campaign is reset rather than entering the candidate-demote sanitizer path.
    assert resumed.resumed is False
    assert resumed.reset_reason == "supervisor_seal_invalid"
    assert resumed.get_candidate_record(2, 1) is None
    assert resumed.state["final_status"] is None
    assert resumed.state["final_result"] is None
    assert resumed.state.get("terminal_frontier_evidence") is None


def test_resume_persists_demoted_state_and_clears_stale_delivery_surface_before_next_solve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project_resume_stale_surface"
    _write_three_cell_project(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    solution = {
        "solid_001": {
            "facility_type": "solid",
            "pose_idx": 2,
            "pose_id": "solid_2",
            "anchor": {"x": 2, "y": 0},
            "orientation": 0,
            "port_mode": "default",
        },
        "ghost_pick": {
            "facility_type": "ghost_rect",
            "pose_idx": 0,
            "pose_id": "ghost_anchor::0,0",
            "anchor": {"x": 0, "y": 0},
        },
    }
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=solution,
        proof_summary={"master_status": "FEASIBLE", "routing_status": "FEASIBLE"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {"solid_001": dict(solution["solid_001"])},
        "search_stats": {"campaign_resumed": True, "solve_mode": "certified_exact"},
    }
    campaign.state["final_result"] = final_result
    _forge_legacy_terminal_certified_stop(campaign)
    candidate_generation = {
        "max_w": 3,
        "max_h": 1,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 2,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 2,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    campaign.state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=campaign.state["candidates"],
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    persist_forged_terminal_certified_state(campaign)

    stale_surface_paths = certified_delivery_surface_artifact_paths(project_root)
    for artifact_path in stale_surface_paths:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps({"stale": True}), encoding="utf-8")

    class _DummyExactSession:
        artifact_hashes = dict(campaign.artifact_hashes)

    monkeypatch.setattr(
        outer_search_module,
        "_ensure_exact_session",
        lambda *args, **kwargs: _DummyExactSession(),
    )
    monkeypatch.setattr(
        outer_search_module,
        "_validate_certified_outer_domain_snapshot_matches_session",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        outer_search_module,
        "_evaluate_pre_master_precheck_best_effort",
        lambda *args, **kwargs: {"triggered": False, "status": None, "proof_summary": {}},
    )

    def _fake_run_benders_for_ghost_rect(*args: object, **kwargs: object) -> tuple[str, None]:
        # Forged terminal full-frontier CERTIFIED is reset outright by
        # _validate_resume_state, so the next solve runs on a fresh campaign.
        # Stale public surface left on disk is no longer authoritative (the
        # certified-surface verifier fails it closed); the reset path does not
        # eagerly delete it here.  (sanitizer demote/clear is covered separately
        # with a seal-irrelevant checkpoint that passes _validate_resume_state.)
        _fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {"master_status": RUN_STATUS_UNKNOWN},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_UNKNOWN, None

    _fake_run_benders_for_ghost_rect.last_run_metadata = {}
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        _fake_run_benders_for_ghost_rect,
    )

    status, result = outer_search_module.run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        resume_campaign=True,
        max_attempts=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    final_solution_path, optimal_blueprint_path, manifest_path = stale_surface_paths
    assert not final_solution_path.exists()
    assert not optimal_blueprint_path.exists()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["best_certified_result"] is None
    assert manifest_payload["campaign"]["final_status"] == RUN_STATUS_UNKNOWN
    assert manifest_payload["artifacts"]["final_solution"]["exists"] is False
    assert manifest_payload["artifacts"]["optimal_blueprint"]["exists"] is False
    resumed_state = json.loads(
        (project_root / "data" / "checkpoints" / "exact_campaign_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert resumed_state["final_status"] == RUN_STATUS_UNKNOWN
    assert resumed_state["final_result"] is None
    assert resumed_state["terminal_frontier_evidence"] is None
    assert resumed_state["candidates"]["2x1"]["status"] == RUN_STATUS_UNKNOWN
    assert "solution" not in resumed_state["candidates"]["2x1"]
