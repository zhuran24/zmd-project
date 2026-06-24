from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.search.benders_loop as benders_loop_module
import src.search.outer_search as outer_search_module
from src.io.delivery_manifest import delivery_manifest_output_path
from src.io.output_schema import blueprint_output_path
from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_UNKNOWN, RUN_STATUS_UNPROVEN
from src.search.exact_campaign import (
    CANDIDATE_PROPOSED_STATUS,
    ExactCampaign,
    SUPERVISOR_PROPOSAL_STATE_KEY,
    has_terminal_full_frontier_certified_evidence,
    load_proposal_ready_marker,
)
from src.search.outer_search import run_outer_search
from src.tests.certified_frontier_helpers import (
    forge_legacy_terminal_certified_stop,
    write_closed_phase_review_gate,
)
from src.tests.test_exact_contract import _build_frontier_project


def _read_state(project_root: Path) -> dict:
    return json.loads(
        (project_root / "data" / "checkpoints" / "exact_campaign_state.json").read_text(
            encoding="utf-8"
        )
    )


def test_v62_partial_frontier_unknown_does_not_export_incumbent_as_certified(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=6, height=6)
    calls: list[tuple[int, int]] = []

    def fake_run_benders_for_ghost_rect(**kwargs):
        ghost_w = int(kwargs["ghost_w"])
        ghost_h = int(kwargs["ghost_h"])
        calls.append((ghost_w, ghost_h))
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_CERTIFIED,
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_CERTIFIED, {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": ghost_w * ghost_h},
            "placements": [],
            "objective": ghost_w * ghost_h,
        }

    fake_run_benders_for_ghost_rect.last_run_metadata = {}
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=9,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=False,
    )

    state = _read_state(project_root)
    manifest = json.loads(delivery_manifest_output_path(project_root).read_text(encoding="utf-8"))
    assert calls == [(6, 1)]
    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert state.get("final_status") == RUN_STATUS_UNKNOWN
    assert state.get("final_result") is None
    assert state.get("last_stop_reason", {}).get("reason") == "max_attempts_exhausted"
    assert manifest.get("best_certified_result") is None
    assert manifest.get("artifacts", {}).get("final_solution", {}).get("exists") is False
    assert not (project_root / "data" / "solutions" / "final_solution.json").exists()


def test_v62_outer_search_blocks_unsafe_master_domain_env_before_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=2, height=2)
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")

    def fail_if_session_constructed(*_args, **_kwargs):  # pragma: no cover - assertion path
        raise AssertionError("ExactSearchSession constructed before unsafe env guard")

    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        fail_if_session_constructed,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=4,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=False,
    )

    state = _read_state(project_root)
    stop = state.get("last_stop_reason", {})
    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    assert stop.get("reason") == "unsafe_certified_exact_master_domain_env"
    assert stop.get("status") == RUN_STATUS_UNPROVEN
    assert stop.get("blockers", [{}])[0].get("env") == "EXACT_USE_POSE_BOOL_MASTER"
    assert state.get("candidates") == {}


def test_v63_outer_search_blocks_ghost_anchor_filter_env_before_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=2, height=2)
    monkeypatch.setenv("EXACT_MASTER_GHOST_ANCHOR_FILTER", "0,0")

    def fail_if_session_constructed(*_args, **_kwargs):  # pragma: no cover - assertion path
        raise AssertionError("ExactSearchSession constructed before unsafe env guard")

    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        fail_if_session_constructed,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=4,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=False,
    )

    state = _read_state(project_root)
    stop = state.get("last_stop_reason", {})
    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    assert stop.get("reason") == "unsafe_certified_exact_master_domain_env"
    assert stop.get("status") == RUN_STATUS_UNPROVEN
    assert stop.get("blockers", [{}])[0].get("env") == "EXACT_MASTER_GHOST_ANCHOR_FILTER"
    assert state.get("candidates") == {}


@pytest.mark.parametrize(
    "env_name",
    [
        "EXACT_LAZY_POWER_COMPLETION",
        "EXACT_POWER_PLACEMENT_SUBPROBLEM",
        "EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST",
    ],
)
def test_v64_outer_search_blocks_power_representation_env_before_session(
    tmp_path: Path,
    monkeypatch,
    env_name: str,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=2, height=2)
    monkeypatch.setenv(env_name, "1")

    def fail_if_session_constructed(*_args, **_kwargs):  # pragma: no cover - assertion path
        raise AssertionError("ExactSearchSession constructed before unsafe env guard")

    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        fail_if_session_constructed,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=4,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=False,
    )

    state = _read_state(project_root)
    stop = state.get("last_stop_reason", {})
    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    assert stop.get("reason") == "unsafe_certified_exact_master_domain_env"
    assert stop.get("status") == RUN_STATUS_UNPROVEN
    assert stop.get("blockers", [{}])[0].get("env") == env_name
    assert state.get("candidates") == {}

def test_v62_best_effort_exhaustion_blocks_before_final_solution_export(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    campaign = ExactCampaign.load_or_create(project_root, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={
            "ghost_rect": {"w": 1, "h": 1, "area": 1},
            "placements": [],
            "objective": 1,
        },
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["declare_mode"] = "best_effort"
    campaign.state["final_result"] = None
    campaign.state["final_status"] = None
    campaign.save()

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=1,
        parallel_processes=1,
        resume_campaign=True,
    )

    state = _read_state(project_root)
    stop = state.get("last_stop_reason", {})
    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    assert stop.get("reason") == "final_result_requires_strict_declare_mode"
    assert stop.get("status") == RUN_STATUS_UNPROVEN
    assert state.get("final_result") is None
    assert not (project_root / "data" / "solutions" / "final_solution.json").exists()


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("EXACT_POWER_FAMILY_LOOKUP_ENCODING", "linear_shell_guards"),
        ("EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING", "linear_minmax"),
        ("EXACT_POWER_COVERAGE_WITNESS_ENCODING", "block_element"),
        ("EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY", "selected_block"),
        ("EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE", "64"),
        ("EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES", "power_pole"),
        ("EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING", "delta"),
    ],
)
def test_v65_outer_search_blocks_power_witness_encoding_env_before_session(
    tmp_path: Path,
    monkeypatch,
    env_name: str,
    env_value: str,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=2, height=2)
    monkeypatch.setenv(env_name, env_value)

    def fail_if_session_constructed(*_args, **_kwargs):  # pragma: no cover - assertion path
        raise AssertionError("ExactSearchSession constructed before unsafe env guard")

    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        fail_if_session_constructed,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=4,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=False,
    )

    state = _read_state(project_root)
    stop = state.get("last_stop_reason", {})
    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    assert stop.get("reason") == "unsafe_certified_exact_master_domain_env"
    assert stop.get("status") == RUN_STATUS_UNPROVEN
    assert stop.get("blockers", [{}])[0].get("env") == env_name
    assert state.get("candidates") == {}


def test_v65_direct_exact_search_session_create_blocks_power_witness_env_before_project_load(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("EXACT_POWER_COVERAGE_WITNESS_ENCODING", "block_element")

    def fail_if_project_loaded(*_args, **_kwargs):  # pragma: no cover - assertion path
        raise AssertionError("project data loaded before unsafe env guard")

    monkeypatch.setattr(benders_loop_module, "load_project_data", fail_if_project_loaded)

    with pytest.raises(RuntimeError, match="EXACT_POWER_COVERAGE_WITNESS_ENCODING"):
        benders_loop_module.ExactSearchSession.create(
            tmp_path / "missing_project",
            solve_mode="certified_exact",
        )


def test_v65_unsafe_env_block_clears_resumed_terminal_final_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    campaign = ExactCampaign.load_or_create(project_root, resume=False)
    terminal_result = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {"placements": [], "objective": 1},
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {},
    }
    campaign.state["final_result"] = dict(terminal_result)
    forge_legacy_terminal_certified_stop(campaign)
    campaign.save()
    assert has_terminal_full_frontier_certified_evidence(campaign.state)

    monkeypatch.setenv("EXACT_POWER_COVERAGE_WITNESS_ENCODING", "block_element")

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=1,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=True,
    )

    state = _read_state(project_root)
    stop = state.get("last_stop_reason", {})
    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    assert state.get("final_result") is None
    assert state.get("final_status") == RUN_STATUS_UNPROVEN
    assert stop.get("reason") == "unsafe_certified_exact_master_domain_env"
    assert stop.get("status") == RUN_STATUS_UNPROVEN
    assert not has_terminal_full_frontier_certified_evidence(state)


def test_v66_unsafe_env_block_clears_stale_certified_delivery_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    solutions_dir = project_root / "data" / "solutions"
    solutions_dir.mkdir(parents=True, exist_ok=True)
    blueprint_path = blueprint_output_path(project_root)
    blueprint_path.parent.mkdir(parents=True, exist_ok=True)
    final_solution_path = solutions_dir / "final_solution.json"
    manifest_path = delivery_manifest_output_path(project_root)

    final_solution_path.write_text(
        json.dumps({"stale": "certified-looking solution"}),
        encoding="utf-8",
    )
    blueprint_path.write_text(
        json.dumps({"stale": "certified-looking blueprint"}),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps({"best_certified_result": {"stale": True}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("EXACT_POWER_COVERAGE_WITNESS_ENCODING", "block_element")

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=1,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=True,
    )

    state = _read_state(project_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    assert state.get("final_result") is None
    assert state.get("final_status") == RUN_STATUS_UNPROVEN
    assert manifest.get("best_certified_result") is None
    assert manifest.get("campaign", {}).get("final_status") == RUN_STATUS_UNPROVEN
    assert manifest.get("artifacts", {}).get("final_solution", {}).get("exists") is False
    assert manifest.get("artifacts", {}).get("optimal_blueprint", {}).get("exists") is False
    assert not final_solution_path.exists()
    assert not blueprint_path.exists()


def test_v65_terminal_result_is_committed_before_final_solution_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    write_closed_phase_review_gate(project_root)

    def fake_run_benders_for_ghost_rect(**kwargs):
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_CERTIFIED,
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        # V79 起 terminal certified 的 placement_solution 必须是 instance 形状
        # (manifest 深校验会把 blueprint facility 反查回 facility_pools)。
        return RUN_STATUS_CERTIFIED, {
            "ghost_pick": {
                "pose_idx": 0,
                "pose_id": "ghost_rect_1x1_0_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "ghost_rect",
            }
        }

    fake_run_benders_for_ghost_rect.last_run_metadata = {}

    final_solution_export_calls: list[bool] = []

    def forbidden_final_solution_export(*_args, **_kwargs):
        final_solution_export_calls.append(True)
        raise AssertionError("producer must not export final_solution for proposal")

    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "_evaluate_pre_master_precheck_best_effort",
        lambda **kwargs: {"triggered": False, "status": None, "proof_summary": {}},
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )
    monkeypatch.setattr(
        outer_search_module,
        "_save_final_result",
        forbidden_final_solution_export,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=1,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=False,
    )

    assert status == CANDIDATE_PROPOSED_STATUS
    assert result is not None
    assert result["search_status"] == CANDIDATE_PROPOSED_STATUS
    assert final_solution_export_calls == []
    state = _read_state(project_root)
    assert state["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert state["last_stop_reason"]["status"] == CANDIDATE_PROPOSED_STATUS
    assert state.get("terminal_frontier_evidence") is not None
    assert not has_terminal_full_frontier_certified_evidence(state)
    run_id = state[SUPERVISOR_PROPOSAL_STATE_KEY]["run_id"]
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    marker, violation = load_proposal_ready_marker(
        campaign.proposal_ready_marker_path,
        checkpoint_path=campaign.path,
        expected_run_id=run_id,
    )
    assert violation is None
    assert marker is not None
    assert marker["exit_code"] == 0
    assert not (project_root / "data" / "solutions" / "final_solution.json").exists()


def test_v66_terminal_export_failure_clears_terminal_state_and_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    blueprint_path = blueprint_output_path(project_root)
    manifest_path = delivery_manifest_output_path(project_root)

    def fake_run_benders_for_ghost_rect(**kwargs):
        ghost_w = int(kwargs["ghost_w"])
        ghost_h = int(kwargs["ghost_h"])
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_CERTIFIED,
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_CERTIFIED, {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": ghost_w * ghost_h},
            "placements": [],
            "objective": ghost_w * ghost_h,
        }

    fake_run_benders_for_ghost_rect.last_run_metadata = {}

    final_solution_export_calls: list[bool] = []

    def fail_after_partial_export(project_root_arg, result, *, facility_pools):
        final_solution_export_calls.append(True)
        final_solution_path.parent.mkdir(parents=True, exist_ok=True)
        blueprint_path.parent.mkdir(parents=True, exist_ok=True)
        final_solution_path.write_text(
            json.dumps({"stale": "partial final solution"}),
            encoding="utf-8",
        )
        blueprint_path.write_text(
            json.dumps({"stale": "partial blueprint"}),
            encoding="utf-8",
        )
        raise RuntimeError("simulated final artifact export failure")

    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "_evaluate_pre_master_precheck_best_effort",
        lambda **kwargs: {"triggered": False, "status": None, "proof_summary": {}},
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )
    monkeypatch.setattr(
        outer_search_module,
        "_save_final_result",
        fail_after_partial_export,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=1,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=False,
    )

    state = _read_state(project_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stop = state.get("last_stop_reason", {})
    assert status == CANDIDATE_PROPOSED_STATUS
    assert result is not None
    assert result["search_status"] == CANDIDATE_PROPOSED_STATUS
    assert final_solution_export_calls == []
    assert stop.get("reason") == "search_exhausted_all_candidates"
    assert state.get("final_result") is not None
    assert state.get("final_status") == CANDIDATE_PROPOSED_STATUS
    assert not has_terminal_full_frontier_certified_evidence(state)
    assert manifest.get("best_certified_result") is None
    assert manifest.get("campaign", {}).get("final_status") == CANDIDATE_PROPOSED_STATUS
    assert manifest.get("artifacts", {}).get("final_solution", {}).get("exists") is False
    assert manifest.get("artifacts", {}).get("optimal_blueprint", {}).get("exists") is False
    assert not final_solution_path.exists()
    assert not blueprint_path.exists()


def test_v67_nonterminal_refresh_clears_stale_certified_delivery_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=2, height=2)
    solutions_dir = project_root / "data" / "solutions"
    solutions_dir.mkdir(parents=True, exist_ok=True)
    final_solution_path = solutions_dir / "final_solution.json"
    blueprint_path = blueprint_output_path(project_root)
    manifest_path = delivery_manifest_output_path(project_root)
    blueprint_path.parent.mkdir(parents=True, exist_ok=True)
    final_solution_path.write_text(
        json.dumps({"stale": "certified-looking solution"}),
        encoding="utf-8",
    )
    blueprint_path.write_text(
        json.dumps({"stale": "certified-looking blueprint"}),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps({"best_certified_result": {"stale": True}}),
        encoding="utf-8",
    )

    def fake_run_benders_for_ghost_rect(**kwargs):
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_UNKNOWN,
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_UNKNOWN, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {}
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "_evaluate_pre_master_precheck_best_effort",
        lambda **kwargs: {"triggered": False, "status": None, "proof_summary": {}},
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=1,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=False,
    )

    state = _read_state(project_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert state.get("final_status") == RUN_STATUS_UNKNOWN
    assert state.get("final_result") is None
    assert manifest.get("best_certified_result") is None
    assert manifest.get("artifacts", {}).get("final_solution", {}).get("exists") is False
    assert manifest.get("artifacts", {}).get("optimal_blueprint", {}).get("exists") is False
    assert not final_solution_path.exists()
    assert not blueprint_path.exists()


def test_v67_blocker_cleanup_removes_directory_artifact_and_refreshes_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    blueprint_path = blueprint_output_path(project_root)
    manifest_path = delivery_manifest_output_path(project_root)
    final_solution_path.mkdir(parents=True)
    blueprint_path.parent.mkdir(parents=True, exist_ok=True)
    blueprint_path.write_text(
        json.dumps({"stale": "certified-looking blueprint"}),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps({"best_certified_result": {"stale": True}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("EXACT_POWER_COVERAGE_WITNESS_ENCODING", "block_element")

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=1,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=True,
    )

    state = _read_state(project_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    assert state.get("final_status") == RUN_STATUS_UNPROVEN
    assert state.get("final_result") is None
    assert manifest.get("best_certified_result") is None
    assert manifest.get("campaign", {}).get("final_status") == RUN_STATUS_UNPROVEN
    assert manifest.get("artifacts", {}).get("final_solution", {}).get("exists") is False
    assert manifest.get("artifacts", {}).get("optimal_blueprint", {}).get("exists") is False
    assert not final_solution_path.exists()
    assert not blueprint_path.exists()


def test_v68_terminal_commit_failure_clears_stale_certified_delivery_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    blueprint_path = blueprint_output_path(project_root)
    manifest_path = delivery_manifest_output_path(project_root)
    final_solution_path.parent.mkdir(parents=True, exist_ok=True)
    blueprint_path.parent.mkdir(parents=True, exist_ok=True)
    final_solution_path.write_text(
        json.dumps({"stale": "certified-looking final solution"}),
        encoding="utf-8",
    )
    blueprint_path.write_text(
        json.dumps({"stale": "certified-looking blueprint"}),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps({"best_certified_result": {"stale": True}}),
        encoding="utf-8",
    )

    def fake_run_benders_for_ghost_rect(**kwargs):
        ghost_w = int(kwargs["ghost_w"])
        ghost_h = int(kwargs["ghost_h"])
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_CERTIFIED,
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_CERTIFIED, {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": ghost_w * ghost_h},
            "placements": [],
            "objective": ghost_w * ghost_h,
        }

    fake_run_benders_for_ghost_rect.last_run_metadata = {}

    def fail_terminal_commit(*_args, **_kwargs):
        raise RuntimeError("simulated terminal evidence guard failure")

    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "_evaluate_pre_master_precheck_best_effort",
        lambda **kwargs: {"triggered": False, "status": None, "proof_summary": {}},
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )
    monkeypatch.setattr(
        outer_search_module,
        "_commit_terminal_full_frontier_certified_result",
        fail_terminal_commit,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        min_side=1,
        area_upper_bound=1,
        max_attempts=1,
        parallel_processes=1,
        resume_campaign=False,
    )

    state = _read_state(project_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stop = state.get("last_stop_reason", {})
    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    assert stop.get("reason") == "terminal_certified_export_failed"
    assert stop.get("blockers", [{}])[0].get("exception_type") == "RuntimeError"
    assert state.get("final_result") is None
    assert state.get("final_status") == RUN_STATUS_UNPROVEN
    assert manifest.get("best_certified_result") is None
    assert manifest.get("campaign", {}).get("final_status") == RUN_STATUS_UNPROVEN
    assert manifest.get("artifacts", {}).get("final_solution", {}).get("exists") is False
    assert manifest.get("artifacts", {}).get("optimal_blueprint", {}).get("exists") is False
    assert not final_solution_path.exists()
    assert not blueprint_path.exists()

def test_v72_blocked_campaign_cleanup_runs_even_when_checkpoint_save_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    blueprint_path = blueprint_output_path(project_root)
    manifest_path = delivery_manifest_output_path(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    forge_legacy_terminal_certified_stop(campaign)
    campaign.save()
    final_solution_path.parent.mkdir(parents=True, exist_ok=True)
    blueprint_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    final_solution_path.write_text(json.dumps({"stale": "final_solution"}), encoding="utf-8")
    blueprint_path.write_text(json.dumps({"stale": "blueprint"}), encoding="utf-8")
    manifest_path.write_text(
        json.dumps({"best_certified_result": {"search_status": RUN_STATUS_CERTIFIED}}),
        encoding="utf-8",
    )

    def fail_save() -> None:
        raise OSError("simulated checkpoint save failure")

    monkeypatch.setattr(campaign, "save", fail_save)

    with pytest.raises(OSError, match="simulated checkpoint save failure"):
        outer_search_module._mark_certified_campaign_blocked(
            campaign,
            reason="simulated_blocker",
            blockers=[{"code": "simulated_blocker"}],
        )

    assert not final_solution_path.exists()
    assert not blueprint_path.exists()
    assert not manifest_path.exists()
