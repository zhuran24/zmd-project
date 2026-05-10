"""Tests for P1 #7 main outer_search 三阶段 ε 调度.

Covers _determine_epsilon_stage 时间切分逻辑.
"""

from __future__ import annotations

import pytest

from src.search.outer_search import _determine_epsilon_stage


def test_stage_1_probe_default_25h(monkeypatch):
    """elapsed < 25h → ε=0.05 (probe stage)."""
    monkeypatch.delenv("EXACT_EPSILON_STAGE1_END_HOURS", raising=False)
    monkeypatch.delenv("EXACT_EPSILON_STAGE2_END_HOURS", raising=False)
    assert _determine_epsilon_stage(0.0) == 0.05
    assert _determine_epsilon_stage(3600.0) == 0.05  # 1h
    assert _determine_epsilon_stage(24 * 3600.0) == 0.05  # 24h
    # boundary: just before 25h
    assert _determine_epsilon_stage(24.99 * 3600.0) == 0.05


def test_stage_2_refinement_25_to_75h(monkeypatch):
    """25h ≤ elapsed < 75h → ε=0.01 (refinement)."""
    monkeypatch.delenv("EXACT_EPSILON_STAGE1_END_HOURS", raising=False)
    monkeypatch.delenv("EXACT_EPSILON_STAGE2_END_HOURS", raising=False)
    assert _determine_epsilon_stage(25 * 3600.0) == 0.01
    assert _determine_epsilon_stage(50 * 3600.0) == 0.01
    assert _determine_epsilon_stage(74.99 * 3600.0) == 0.01


def test_stage_3_certification_after_75h(monkeypatch):
    """elapsed ≥ 75h → ε=0.0 (final certification)."""
    monkeypatch.delenv("EXACT_EPSILON_STAGE1_END_HOURS", raising=False)
    monkeypatch.delenv("EXACT_EPSILON_STAGE2_END_HOURS", raising=False)
    assert _determine_epsilon_stage(75 * 3600.0) == 0.0
    assert _determine_epsilon_stage(168 * 3600.0) == 0.0
    assert _determine_epsilon_stage(1000 * 3600.0) == 0.0


def test_env_override_thresholds(monkeypatch):
    """EXACT_EPSILON_STAGE*_END_HOURS env 覆盖默认阈值."""
    monkeypatch.setenv("EXACT_EPSILON_STAGE1_END_HOURS", "5")
    monkeypatch.setenv("EXACT_EPSILON_STAGE2_END_HOURS", "10")
    # elapsed=4h (< 5) → stage 1
    assert _determine_epsilon_stage(4 * 3600.0) == 0.05
    # elapsed=7h (5-10) → stage 2
    assert _determine_epsilon_stage(7 * 3600.0) == 0.01
    # elapsed=12h (>10) → stage 3
    assert _determine_epsilon_stage(12 * 3600.0) == 0.0


def test_short_campaign_stays_in_stage_1(monkeypatch):
    """短跑 (e.g. 24h budget) elapsed < 25h 全程 stage 1, 符合预期."""
    monkeypatch.delenv("EXACT_EPSILON_STAGE1_END_HOURS", raising=False)
    monkeypatch.delenv("EXACT_EPSILON_STAGE2_END_HOURS", raising=False)
    # 24h elapsed = 86400s, < 25h
    assert _determine_epsilon_stage(86400.0) == 0.05


def test_invalid_env_falls_back_to_default(monkeypatch):
    """env 设了非数字 → fall back default 25/75."""
    monkeypatch.setenv("EXACT_EPSILON_STAGE1_END_HOURS", "not_a_number")
    monkeypatch.delenv("EXACT_EPSILON_STAGE2_END_HOURS", raising=False)
    # 默认 25h 阈值仍生效
    assert _determine_epsilon_stage(20 * 3600.0) == 0.05
    assert _determine_epsilon_stage(30 * 3600.0) == 0.01


def test_stage_passed_to_run_benders():
    """run_benders_for_ghost_rect 接受 epsilon_stage kwarg (signature 检查)."""
    import inspect
    from src.search.benders_loop import run_benders_for_ghost_rect
    sig = inspect.signature(run_benders_for_ghost_rect)
    assert "epsilon_stage" in sig.parameters
    assert sig.parameters["epsilon_stage"].default is None


def test_elapsed_seconds_helper_exists():
    """ExactCampaign.elapsed_seconds 方法已加 (P1 #7 main 依赖)."""
    from src.search.exact_campaign import ExactCampaign
    assert hasattr(ExactCampaign, "elapsed_seconds")
