from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.search.outer_search as outer_search_module
from src.io.delivery_manifest import delivery_manifest_output_path
from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_UNKNOWN, RUN_STATUS_UNPROVEN
from src.search.exact_campaign import ExactCampaign
from src.search.outer_search import run_outer_search
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
