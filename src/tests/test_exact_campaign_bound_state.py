"""Tests for P1 #7a (bound_state) + P1 #7d (bound regression guard)."""

from __future__ import annotations

import pytest

from src.search.exact_campaign import (
    ExactCampaign,
    _bound_state_defaults,
    _build_initial_state,
)


@pytest.fixture
def camp(tmp_path):
    """ExactCampaign with stubbed artifact hashes (avoid project_root deps)."""
    state = _build_initial_state(
        current_hashes={"stub": "0"},
        campaign_hours=1.0,
        reset_reason=None,
    )
    return ExactCampaign(
        project_root=tmp_path,
        path=tmp_path / "state.json",
        state=state,
        resumed=False,
        compatible_hashes=True,
    )


def test_bound_state_defaults_all_none():
    defaults = _bound_state_defaults()
    assert set(defaults.keys()) == {
        "lb", "ub", "gap", "epsilon_target", "prover", "observed_at", "model_hash"
    }
    for v in defaults.values():
        assert v is None


def test_get_candidate_bound_state_returns_defaults_for_missing(camp):

    bs = camp.get_candidate_bound_state(70, 70)
    assert bs == _bound_state_defaults()


def test_update_then_get_roundtrip(camp):

    camp.update_candidate_bound_state(
        70, 70, lb=100, ub=120, gap=0.2, epsilon_target=0.05,
        prover="master_cpsat", model_hash="hash_v1",
    )
    bs = camp.get_candidate_bound_state(70, 70)
    assert bs["lb"] == 100
    assert bs["ub"] == 120
    assert bs["gap"] == 0.2
    assert bs["epsilon_target"] == 0.05
    assert bs["prover"] == "master_cpsat"
    assert bs["model_hash"] == "hash_v1"
    assert bs["observed_at"] is not None


def test_partial_update_preserves_other_fields(camp):

    camp.update_candidate_bound_state(70, 70, lb=100, ub=120)
    camp.update_candidate_bound_state(70, 70, ub=110)  # only ub changes
    bs = camp.get_candidate_bound_state(70, 70)
    assert bs["lb"] == 100  # preserved
    assert bs["ub"] == 110  # updated


def test_bound_regression_appends_audit_event(camp):
    """P1 #7d: lb_new < lb_old - tol triggers BOUND_REGRESSION event."""

    camp.update_candidate_bound_state(70, 70, lb=100, model_hash="h1")
    audit = camp.update_candidate_bound_state(
        70, 70, lb=80, model_hash="h2", regression_tolerance=0
    )
    assert audit is not None
    assert audit["event"] == "BOUND_REGRESSION"
    assert audit["old_lb"] == 100
    assert audit["new_lb"] == 80
    assert audit["model_hash_old"] == "h1"
    assert audit["model_hash_new"] == "h2"
    log = camp.get_audit_log()
    assert len(log) == 1
    assert log[0] == audit


def test_bound_regression_within_tolerance_no_event(camp):

    camp.update_candidate_bound_state(70, 70, lb=100)
    audit = camp.update_candidate_bound_state(
        70, 70, lb=99, regression_tolerance=2
    )
    assert audit is None  # within tolerance
    assert camp.get_audit_log() == []


def test_lb_increase_is_not_regression(camp):

    camp.update_candidate_bound_state(70, 70, lb=100)
    audit = camp.update_candidate_bound_state(70, 70, lb=110)
    assert audit is None
    assert camp.get_audit_log() == []


def test_first_lb_set_is_not_regression(camp):
    """No prior lb → no regression event (nothing to compare)."""

    audit = camp.update_candidate_bound_state(70, 70, lb=50)
    assert audit is None


def test_candidate_default_includes_bound_state(camp):
    """New candidate started should have bound_state default-filled."""

    camp.mark_candidate_started(70, 70)
    record = camp.get_candidate_record(70, 70)
    assert "bound_state" in record
    assert record["bound_state"] == _bound_state_defaults()


def test_epsilon_certified_status_accepted(tmp_path):
    """P1 #7a: VALID_CANDIDATE_STATUSES 含 EPSILON_CERTIFIED."""
    from src.search.exact_campaign import VALID_CANDIDATE_STATUSES
    assert "EPSILON_CERTIFIED" in VALID_CANDIDATE_STATUSES
