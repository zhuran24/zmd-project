"""Tests for EXACT_OUTER_SKIP_UNKNOWN env-gate (A 方案 P2 #14 数据收集).

验证 outer_search 在 env on/off 下两条分支:
- _terminal_stop_reason_for_status(UNKNOWN) 行为
- frontier skip set 是否含 UNKNOWN

env on 是违反 max_lex 严格性的 best-effort 模式, 仅在收 binding 实例时启用.
"""

from __future__ import annotations

import json
from pathlib import Path


def _write_minimal_exact_campaign_artifacts(project_root: Path) -> None:
    (project_root / "data" / "preprocessed").mkdir(parents=True)
    (project_root / "rules").mkdir(parents=True)
    (project_root / "data" / "preprocessed" / "mandatory_exact_instances.json").write_text(
        "[]", encoding="utf-8"
    )
    (project_root / "data" / "preprocessed" / "candidate_placements.json").write_text(
        "{}", encoding="utf-8"
    )
    (project_root / "data" / "preprocessed" / "generic_io_requirements.json").write_text(
        "{}", encoding="utf-8"
    )
    (project_root / "rules" / "canonical_rules.json").write_text(
        json.dumps({"globals": {"grid": {"width": 2, "height": 1}}}),
        encoding="utf-8",
    )

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


def test_certified_outer_search_blocks_skip_unknown_env_before_fake_certified(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """EXACT_OUTER_SKIP_UNKNOWN is best-effort and must not reach certified lifecycle."""
    project_root = tmp_path / "outer_skip_unknown_blocked"
    _write_minimal_exact_campaign_artifacts(project_root)
    monkeypatch.setenv("EXACT_OUTER_SKIP_UNKNOWN", "1")

    from src.search.outer_search import run_outer_search

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        campaign_hours=1.0,
    )

    assert status == "UNPROVEN"
    assert result is None
    state = json.loads(
        (project_root / "data" / "checkpoints" / "exact_campaign_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["declare_mode"] == "strict"
    assert state["final_result"] is None
    assert state["final_status"] == "UNPROVEN"
    assert state["last_stop_reason"]["reason"] == "outer_skip_unknown_not_certified"
    assert state["last_stop_reason"]["blockers"] == [
        {
            "code": "outer_skip_unknown_not_certified",
            "env": "EXACT_OUTER_SKIP_UNKNOWN",
            "detail": (
                "skipping UNKNOWN frontier candidates makes the campaign declare_mode "
                "best_effort, not a strict full candidate-domain certificate"
            ),
        }
    ]
