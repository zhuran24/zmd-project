"""A 方案 anchor slicing 最小 filter 测试.

只覆盖 MasterPlacementModel.__init__ 新加的 ghost_anchor_filter 参数行为:
filter=None 全 anchor; filter=subset 只 build subset; filter=空集 立即 infeasible.

不验 from_exact_core 路径 (那条要 ExactSearchSession + canonical_rules + 全套
preprocess, RAM PoC script 跑那条; 单元测只验 legacy MasterPlacementModel)
"""

from __future__ import annotations

import pytest

from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import (
    EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV,
    EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE_ENV,
    EXACT_USE_POSE_BOOL_MASTER_ENV,
    _resolve_ghost_anchor_filter_from_env,
    run_benders_for_ghost_rect,
)


def _build_minimal_ghost_model(
    *,
    grid_width: int = 5,
    ghost_anchor_filter=None,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "miner": [
            {
                "pose_id": "pose_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
    }
    rules = {
        "globals": {"grid": {"width": int(grid_width), "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
        ghost_anchor_filter=ghost_anchor_filter,
    )


def test_ghost_anchor_filter_none_keeps_all_anchors() -> None:
    model = _build_minimal_ghost_model(grid_width=5, ghost_anchor_filter=None)
    model.build()

    ghost_stats = model.build_stats["ghost_rect"]
    assert ghost_stats["enabled"] is True
    assert ghost_stats["placements"] == 5
    assert ghost_stats["anchor_filter_applied"] is False
    assert ghost_stats["anchor_filter_skipped"] == 0
    assert len(model.u_vars) == 5
    anchors = {
        (int(domain["anchor"]["x"]), int(domain["anchor"]["y"]))
        for domain in model._ghost_domains
    }
    assert anchors == {(x, 0) for x in range(5)}


def test_ghost_anchor_filter_subset_only_builds_filtered_anchors() -> None:
    requested = {(1, 0), (3, 0)}
    model = _build_minimal_ghost_model(grid_width=5, ghost_anchor_filter=requested)
    model.build()

    ghost_stats = model.build_stats["ghost_rect"]
    assert ghost_stats["enabled"] is True
    assert ghost_stats["placements"] == 2
    assert ghost_stats["anchor_filter_applied"] is True
    assert ghost_stats["anchor_filter_skipped"] == 3
    assert len(model.u_vars) == 2
    anchors = {
        (int(domain["anchor"]["x"]), int(domain["anchor"]["y"]))
        for domain in model._ghost_domains
    }
    assert anchors == requested


def test_ghost_anchor_filter_empty_marks_model_infeasible() -> None:
    model = _build_minimal_ghost_model(grid_width=5, ghost_anchor_filter=set())
    model.build()

    ghost_stats = model.build_stats["ghost_rect"]
    assert ghost_stats["enabled"] is True
    assert ghost_stats["placements"] == 0
    assert ghost_stats["reason"] == "anchor_filter_empty"
    assert ghost_stats["anchor_filter_applied"] is True
    assert ghost_stats["anchor_filter_skipped"] == 5
    assert not model.u_vars


def test_ghost_anchor_filter_outside_grid_excludes_all_anchors() -> None:
    requested = {(99, 99)}
    model = _build_minimal_ghost_model(grid_width=5, ghost_anchor_filter=requested)
    model.build()

    ghost_stats = model.build_stats["ghost_rect"]
    assert ghost_stats["enabled"] is True
    assert ghost_stats["placements"] == 0
    assert ghost_stats["reason"] == "anchor_filter_excludes_all_anchors"
    assert ghost_stats["anchor_filter_skipped"] == 5


def test_env_parser_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, raising=False)
    assert _resolve_ghost_anchor_filter_from_env() is None


def test_env_parser_returns_none_when_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, "   ")
    assert _resolve_ghost_anchor_filter_from_env() is None


def test_env_parser_accepts_single_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, "0,0")
    assert _resolve_ghost_anchor_filter_from_env() == frozenset({(0, 0)})


def test_env_parser_accepts_multiple_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, "0,0;5,10;2,7")
    assert _resolve_ghost_anchor_filter_from_env() == frozenset({(0, 0), (5, 10), (2, 7)})


def test_env_parser_tolerates_whitespace_and_empty_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, " ; 0 , 0 ; ; 1,2 ; ")
    assert _resolve_ghost_anchor_filter_from_env() == frozenset({(0, 0), (1, 2)})


def test_env_parser_rejects_missing_comma(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, "0;5,10")
    with pytest.raises(ValueError, match="expected 'x,y' pairs"):
        _resolve_ghost_anchor_filter_from_env()


def test_env_parser_rejects_non_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, "abc,def")
    with pytest.raises(ValueError, match="non-integer coordinate"):
        _resolve_ghost_anchor_filter_from_env()


def test_certified_exact_blocks_ghost_anchor_filter_env_before_candidate_terminal_status(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, "0,0")

    status, solution = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=tmp_path,
        solve_mode="certified_exact",
        max_iterations=1,
    )

    metadata = run_benders_for_ghost_rect.last_run_metadata
    assert status == "UNPROVEN"
    assert solution is None
    assert metadata["exact_safe_cuts"] == []
    assert metadata["generated_exact_safe_cut_count"] == 0
    blockers = metadata["proof_summary"]["blockers"]
    assert blockers == [
        {
            "code": "ghost_anchor_filter_not_certified",
            "env": EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV,
            "anchor_filter_count": 1,
            "detail": (
                "certified exact campaign candidates are full unfiltered "
                "ghost-anchor-domain claims"
            ),
        }
    ]


def test_certified_exact_blocks_pose_bool_master_env_before_session(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, raising=False)
    monkeypatch.setenv(EXACT_USE_POSE_BOOL_MASTER_ENV, "1")

    def _forbidden_session_factory(*_args, **_kwargs):  # pragma: no cover - failure sentinel
        raise AssertionError("certified exact domain env blocker must run before ExactSearchSession")

    monkeypatch.setattr(
        "src.search.benders_loop.create_exact_search_session",
        _forbidden_session_factory,
    )

    status, solution = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=tmp_path,
        solve_mode="certified_exact",
        max_iterations=1,
    )

    metadata = run_benders_for_ghost_rect.last_run_metadata
    assert status == "UNPROVEN"
    assert solution is None
    assert metadata["exact_safe_cuts"] == []
    assert metadata["generated_exact_safe_cut_count"] == 0
    assert metadata["proof_summary"]["master_status"] == "BLOCKED"
    blockers = metadata["proof_summary"]["blockers"]
    assert blockers == [
        {
            "code": "pose_bool_master_not_certified",
            "env": EXACT_USE_POSE_BOOL_MASTER_ENV,
            "value": "1",
            "detail": "pose-bool master does not construct the certified full ghost-anchor domain",
        }
    ]


def test_certified_exact_blocks_power_pole_slot_override_before_session(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, raising=False)
    monkeypatch.setenv(EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE_ENV, "1")

    def _forbidden_session_factory(*_args, **_kwargs):  # pragma: no cover - failure sentinel
        raise AssertionError("certified exact domain env blocker must run before ExactSearchSession")

    monkeypatch.setattr(
        "src.search.benders_loop.create_exact_search_session",
        _forbidden_session_factory,
    )

    status, solution = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=tmp_path,
        solve_mode="certified_exact",
        max_iterations=1,
    )

    metadata = run_benders_for_ghost_rect.last_run_metadata
    assert status == "UNPROVEN"
    assert solution is None
    assert metadata["exact_safe_cuts"] == []
    assert metadata["generated_exact_safe_cut_count"] == 0
    assert metadata["proof_summary"]["master_status"] == "BLOCKED"
    blockers = metadata["proof_summary"]["blockers"]
    assert blockers == [
        {
            "code": "power_pole_slot_upper_bound_override_not_certified",
            "env": EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE_ENV,
            "value": "1",
            "detail": "power-pole slot upper-bound override tightens the certified master domain",
        }
    ]
