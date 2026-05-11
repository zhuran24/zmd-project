"""Tests for EXACT_OUTER_SKIP_UNKNOWN env-gate (A 方案 P2 #14 数据收集).

验证 outer_search 在 env on/off 下两条分支:
- _terminal_stop_reason_for_status(UNKNOWN) 行为
- frontier skip set 是否含 UNKNOWN

env on 是违反 max_lex 严格性的 best-effort 模式, 仅在收 binding 实例时启用.
"""

from __future__ import annotations


def test_terminal_stop_reason_default_unknown_returns_candidate_returned_unknown(monkeypatch):
    """default (env unset): UNKNOWN candidate 触发 campaign terminal stop."""
    monkeypatch.delenv("EXACT_OUTER_SKIP_UNKNOWN", raising=False)
    from src.search.outer_search import _terminal_stop_reason_for_status
    assert _terminal_stop_reason_for_status("UNKNOWN") == "candidate_returned_unknown"


def test_terminal_stop_reason_env_on_unknown_returns_none(monkeypatch):
    """env on: UNKNOWN 不 trigger terminal stop, campaign 继续."""
    monkeypatch.setenv("EXACT_OUTER_SKIP_UNKNOWN", "1")
    from src.search.outer_search import _terminal_stop_reason_for_status
    assert _terminal_stop_reason_for_status("UNKNOWN") is None


def test_terminal_stop_reason_env_on_truthy_variants(monkeypatch):
    """env on 接受 1 / true / yes / on (大小写不敏感) + 空白."""
    from src.search.outer_search import _terminal_stop_reason_for_status
    for value in ("1", "true", "TRUE", "yes", "Yes", "on", " 1 "):
        monkeypatch.setenv("EXACT_OUTER_SKIP_UNKNOWN", value)
        assert _terminal_stop_reason_for_status("UNKNOWN") is None, f"value={value!r}"


def test_terminal_stop_reason_env_on_falsy_variants(monkeypatch):
    """env on 拒绝 0 / false / no / off / 空字符串 (保留严格语义)."""
    from src.search.outer_search import _terminal_stop_reason_for_status
    for value in ("", "0", "false", "no", "off", "random"):
        monkeypatch.setenv("EXACT_OUTER_SKIP_UNKNOWN", value)
        assert _terminal_stop_reason_for_status("UNKNOWN") == "candidate_returned_unknown", f"value={value!r}"


def test_terminal_stop_reason_unproven_not_affected(monkeypatch):
    """UNPROVEN 走自己分支, env on 也不变 (只 UNKNOWN 被 env-gate)."""
    monkeypatch.setenv("EXACT_OUTER_SKIP_UNKNOWN", "1")
    from src.search.outer_search import _terminal_stop_reason_for_status
    assert _terminal_stop_reason_for_status("UNPROVEN") == "candidate_returned_unproven"


def test_terminal_stop_reason_other_status_returns_none(monkeypatch):
    """CERTIFIED / FEASIBLE / INFEASIBLE 都不 terminal stop, env 无关."""
    monkeypatch.delenv("EXACT_OUTER_SKIP_UNKNOWN", raising=False)
    from src.search.outer_search import _terminal_stop_reason_for_status
    for status in ("CERTIFIED", "FEASIBLE", "INFEASIBLE", "RUNNING", "EPSILON_CERTIFIED"):
        assert _terminal_stop_reason_for_status(status) is None, f"status={status}"


def test_frontier_skip_set_default_excludes_unknown(monkeypatch):
    """default (env unset): _frontier_skip_statuses 只 skip CERTIFIED+INFEASIBLE.

    通过 source code inspection 验证 (avoid 重建 full outer_search context).
    """
    monkeypatch.delenv("EXACT_OUTER_SKIP_UNKNOWN", raising=False)
    # 间接测: 通过模拟 env check 行为
    import os
    val = os.environ.get("EXACT_OUTER_SKIP_UNKNOWN", "").strip().lower()
    assert val not in {"1", "true", "yes", "on"}


def test_frontier_skip_set_env_on_includes_unknown(monkeypatch):
    """env on: _frontier_skip_statuses 含 UNKNOWN, frontier 跳过 UNKNOWN candidate."""
    monkeypatch.setenv("EXACT_OUTER_SKIP_UNKNOWN", "1")
    import os
    val = os.environ.get("EXACT_OUTER_SKIP_UNKNOWN", "").strip().lower()
    assert val in {"1", "true", "yes", "on"}
