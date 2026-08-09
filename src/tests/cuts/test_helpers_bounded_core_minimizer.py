"""Tests for src/cuts/helpers/bounded_core_minimizer.py (P1.2B-F5).

Coverage:
- Soundness path (full INFEASIBLE → shrink / keep)
- Caller-contract violations (empty / full FEASIBLE / UNKNOWN initial)
- Budget exhaust (max_calls / max_seconds)
- Oracle UNKNOWN/TIMEOUT keep-literal semantics
- Oracle exception fail-closed
- Canonical sort determinism
- is_verified_infeasible invariant True
- Budget schema validation (bool/negative/zero)
"""
from __future__ import annotations

import time
from typing import List, Tuple

import pytest

from src.cuts.helpers.bounded_core_minimizer import (
    CoreMinimizeResult,
    CoreStoppedReason,
    LiteralAssignment,
    MinimizerBudget,
    OracleVerdict,
    VALID_ORACLE_VERDICTS,
    VALID_STOPPED_REASONS,
    canonical_sort_assignment,
    deletion_minimize_core,
)


# ---- fixtures --------------------------------------------------------------


def _lit(group: str, slot: int, pose: str) -> LiteralAssignment:
    return (group, slot, pose)


def _make_recording_oracle(verdict_map: dict[Tuple[LiteralAssignment, ...], OracleVerdict]):
    """Oracle that returns a fixed verdict per (canonical-sorted) input core."""
    calls: List[Tuple[LiteralAssignment, ...]] = []

    def oracle(core: Tuple[LiteralAssignment, ...]) -> OracleVerdict:
        calls.append(core)
        # Look up by canonical-sorted key so test definitions can ignore order
        key = canonical_sort_assignment(core)
        return verdict_map.get(key, "FEASIBLE")

    return oracle, calls


# ---- soundness path --------------------------------------------------------


def test_full_assignment_3_literals_minimal_all_essential():
    """Each literal essential: every trial (n-1) is FEASIBLE → no shrink, is_minimal=True."""
    a = _lit("g1", 0, "pA")
    b = _lit("g2", 0, "pB")
    c = _lit("g3", 0, "pC")
    full = (a, b, c)
    oracle, calls = _make_recording_oracle({full: "INFEASIBLE"})
    result = deletion_minimize_core(full, oracle, MinimizerBudget(max_calls=10, max_seconds=2.0))
    assert result.core == full
    assert result.is_minimal is True
    assert result.is_verified_infeasible is True
    assert result.stopped_reason == CoreStoppedReason.INFEASIBLE_VERIFIED
    assert result.size_before == 3
    assert result.size_after == 3
    # 1 initial verify + 3 trial deletions = 4 calls
    assert result.calls == 4


def test_shrink_to_minimum_subset():
    """Only {a, b} is INFEASIBLE; c is removable."""
    a = _lit("g1", 0, "pA")
    b = _lit("g2", 0, "pB")
    c = _lit("g3", 0, "pC")
    full = (a, b, c)
    ab = (a, b)
    oracle, _calls = _make_recording_oracle({full: "INFEASIBLE", ab: "INFEASIBLE"})
    result = deletion_minimize_core(full, oracle, MinimizerBudget(max_calls=10, max_seconds=2.0))
    # After removing c (reverse iter starts at c), trial = (a, b), oracle INFEASIBLE → shrink.
    # Then trial = (a) and (b) both default FEASIBLE → both essential, kept.
    assert result.core == ab
    assert result.size_after == 2
    assert result.is_minimal is True
    assert result.stopped_reason == CoreStoppedReason.INFEASIBLE_VERIFIED


def test_canonical_sort_deterministic_same_core_regardless_input_order():
    """Reverse-ordered input must yield the same core as sorted input."""
    a = _lit("g1", 0, "pA")
    b = _lit("g2", 0, "pB")
    full = (a, b)
    oracle1, _ = _make_recording_oracle({full: "INFEASIBLE"})
    r1 = deletion_minimize_core((a, b), oracle1)
    oracle2, _ = _make_recording_oracle({full: "INFEASIBLE"})
    r2 = deletion_minimize_core((b, a), oracle2)
    assert r1.core == r2.core


# ---- caller-contract violations -------------------------------------------


def test_empty_assignment_raises():
    oracle, _ = _make_recording_oracle({})
    with pytest.raises(ValueError, match="non-empty"):
        deletion_minimize_core((), oracle)


def test_full_feasible_raises_value_error():
    a = _lit("g1", 0, "pA")
    oracle, _ = _make_recording_oracle({})  # default FEASIBLE
    with pytest.raises(ValueError, match="initial verify returned"):
        deletion_minimize_core((a,), oracle)


def test_full_unknown_raises_value_error():
    a = _lit("g1", 0, "pA")
    oracle, _ = _make_recording_oracle({(a,): "UNKNOWN"})
    with pytest.raises(ValueError, match="UNKNOWN"):
        deletion_minimize_core((a,), oracle)


def test_full_timeout_raises_value_error():
    a = _lit("g1", 0, "pA")
    oracle, _ = _make_recording_oracle({(a,): "TIMEOUT"})
    with pytest.raises(ValueError, match="TIMEOUT"):
        deletion_minimize_core((a,), oracle)


# ---- budget exhaust --------------------------------------------------------


def test_max_calls_exhausted_returns_last_verified():
    """max_calls=2: initial verify + 1 trial, then break before next trial."""
    a = _lit("g1", 0, "pA")
    b = _lit("g2", 0, "pB")
    c = _lit("g3", 0, "pC")
    full = (a, b, c)
    ab = (a, b)
    # First trial (remove c) → INFEASIBLE, shrink to (a, b). Now calls=2, == max_calls.
    # Next iter check budget → return last verified.
    oracle, _ = _make_recording_oracle({full: "INFEASIBLE", ab: "INFEASIBLE"})
    result = deletion_minimize_core(full, oracle, MinimizerBudget(max_calls=2, max_seconds=2.0))
    assert result.stopped_reason == CoreStoppedReason.MAX_CALLS
    assert result.is_minimal is False
    assert result.is_verified_infeasible is True
    assert result.core == ab  # last verified
    assert result.calls == 2


def test_max_seconds_exhausted_returns_last_verified():
    """Slow oracle exceeds max_seconds budget."""
    a = _lit("g1", 0, "pA")
    b = _lit("g2", 0, "pB")
    full = (a, b)

    def slow_oracle(core: Tuple[LiteralAssignment, ...]) -> OracleVerdict:
        time.sleep(0.05)
        return "INFEASIBLE" if canonical_sort_assignment(core) == full else "FEASIBLE"

    result = deletion_minimize_core(full, slow_oracle, MinimizerBudget(max_calls=10, max_seconds=0.01))
    assert result.stopped_reason == CoreStoppedReason.TIMEOUT
    assert result.is_minimal is False
    assert result.is_verified_infeasible is True
    # Must be last verified — at least the full assignment
    assert len(result.core) >= 1


# ---- oracle UNKNOWN/TIMEOUT keep-literal semantics ------------------------


def test_oracle_unknown_keeps_literal_continues():
    """UNKNOWN mid-loop: keep literal, continue minimizing other literals.

    is_minimal must be False because we cannot confirm essentiality.
    """
    a = _lit("g1", 0, "pA")
    b = _lit("g2", 0, "pB")
    c = _lit("g3", 0, "pC")
    full = (a, b, c)
    # First trial (remove c) → UNKNOWN, keep c. Then (remove b) → FEASIBLE, keep b.
    # Then (remove a) → FEASIBLE, keep a.
    verdict_map: dict[Tuple[LiteralAssignment, ...], OracleVerdict] = {
        full: "INFEASIBLE",
        (a, b): "UNKNOWN",  # remove c trial
    }
    oracle, _ = _make_recording_oracle(verdict_map)
    result = deletion_minimize_core(full, oracle, MinimizerBudget(max_calls=10, max_seconds=2.0))
    assert result.core == full  # nothing shrunken
    assert result.is_minimal is False  # had_inconclusive
    assert result.stopped_reason == CoreStoppedReason.INFEASIBLE_VERIFIED
    assert result.is_verified_infeasible is True


def test_oracle_timeout_verdict_keeps_literal_continues():
    """Oracle's own TIMEOUT verdict (not budget): keep literal, continue."""
    a = _lit("g1", 0, "pA")
    b = _lit("g2", 0, "pB")
    full = (a, b)
    verdict_map: dict[Tuple[LiteralAssignment, ...], OracleVerdict] = {
        full: "INFEASIBLE",
        (a,): "TIMEOUT",  # remove b trial
    }
    oracle, _ = _make_recording_oracle(verdict_map)
    result = deletion_minimize_core(full, oracle, MinimizerBudget(max_calls=10, max_seconds=2.0))
    assert result.core == full
    assert result.is_minimal is False
    assert result.stopped_reason == CoreStoppedReason.INFEASIBLE_VERIFIED


# ---- oracle exception fail-closed -----------------------------------------


def test_oracle_raise_returns_last_verified():
    a = _lit("g1", 0, "pA")
    b = _lit("g2", 0, "pB")
    full = (a, b)
    call_count = {"n": 0}

    def raising_oracle(core: Tuple[LiteralAssignment, ...]) -> OracleVerdict:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "INFEASIBLE"  # initial verify
        raise RuntimeError("oracle blew up")

    result = deletion_minimize_core(full, raising_oracle, MinimizerBudget(max_calls=10, max_seconds=2.0))
    assert result.stopped_reason == CoreStoppedReason.EXCEPTION_FAIL_CLOSED
    assert result.is_minimal is False
    assert result.is_verified_infeasible is True
    assert result.core == canonical_sort_assignment(full)  # last verified = initial


# ---- is_verified_infeasible invariant -------------------------------------


@pytest.mark.parametrize(
    "stopped_reason",
    [r for r in CoreStoppedReason],
)
def test_is_verified_infeasible_always_true(stopped_reason):
    """is_verified_infeasible is invariant True under every stopped_reason."""
    # Construct each scenario and check the flag.
    a = _lit("g1", 0, "pA")
    full = (a,)
    if stopped_reason == CoreStoppedReason.INFEASIBLE_VERIFIED:
        oracle, _ = _make_recording_oracle({full: "INFEASIBLE"})
        r = deletion_minimize_core(full, oracle)
    elif stopped_reason == CoreStoppedReason.MAX_CALLS:
        oracle, _ = _make_recording_oracle({full: "INFEASIBLE"})
        r = deletion_minimize_core(full, oracle, MinimizerBudget(max_calls=1, max_seconds=2.0))
    elif stopped_reason == CoreStoppedReason.TIMEOUT:

        def slow(core):
            time.sleep(0.05)
            return "INFEASIBLE"

        r = deletion_minimize_core(full, slow, MinimizerBudget(max_calls=10, max_seconds=0.01))
    else:  # EXCEPTION_FAIL_CLOSED
        n = {"c": 0}

        def raising(core):
            n["c"] += 1
            if n["c"] == 1:
                return "INFEASIBLE"
            raise RuntimeError("boom")

        b = _lit("g2", 0, "pB")
        r = deletion_minimize_core((a, b), raising)
    assert r.is_verified_infeasible is True
    assert r.stopped_reason == stopped_reason


# ---- budget schema validation ---------------------------------------------


def test_budget_max_calls_zero_raises():
    with pytest.raises(ValueError, match=">= 1"):
        MinimizerBudget(max_calls=0, max_seconds=1.0)


def test_budget_max_calls_bool_raises():
    with pytest.raises(ValueError, match="strict int"):
        MinimizerBudget(max_calls=True, max_seconds=1.0)  # type: ignore[arg-type]


def test_budget_max_seconds_zero_raises():
    with pytest.raises(ValueError, match=r"> 0\.0"):
        MinimizerBudget(max_calls=1, max_seconds=0.0)


def test_budget_max_seconds_negative_raises():
    with pytest.raises(ValueError, match=r"> 0\.0"):
        MinimizerBudget(max_calls=1, max_seconds=-1.0)


def test_budget_max_seconds_bool_raises():
    with pytest.raises(ValueError, match="must be float"):
        MinimizerBudget(max_calls=1, max_seconds=True)  # type: ignore[arg-type]


# ---- helper / public constants --------------------------------------------


def test_valid_stopped_reasons_matches_enum():
    assert VALID_STOPPED_REASONS == frozenset(r.value for r in CoreStoppedReason)
    assert "EVIL_REASON" not in VALID_STOPPED_REASONS


def test_valid_oracle_verdicts_closed_set():
    assert VALID_ORACLE_VERDICTS == frozenset(("INFEASIBLE", "FEASIBLE", "UNKNOWN", "TIMEOUT"))


def test_canonical_sort_stable():
    a = _lit("g1", 0, "pA")
    b = _lit("g2", 0, "pB")
    c = _lit("g1", 1, "pA")
    sorted1 = canonical_sort_assignment((a, b, c))
    sorted2 = canonical_sort_assignment((c, b, a))
    assert sorted1 == sorted2
    # Lex order: (g1,0,pA) < (g1,1,pA) < (g2,0,pB)
    assert sorted1 == (a, c, b)
