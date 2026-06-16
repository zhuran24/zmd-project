"""Bounded deletion-based core minimizer (Phase 1.2 P1.2B-F5 F5 pattern_nogood).

Deletion-based bounded MUS minimizer with paranoid fail-closed contract:

- Input: full literal assignment (canonical-sortable triple), oracle callable
  returning a 4-value verdict, budget (max calls + max seconds).
- Output: ``CoreMinimizeResult`` with last-verified-INFEASIBLE core + audit.

Hard rules (per docs/项目说明/12_go_criteria.md §8.1.x acceptance A):

1. Full assignment must first verify INFEASIBLE; FEASIBLE/UNKNOWN/TIMEOUT
   responses raise ``ValueError`` (caller contract violation — caller already
   has an INFEASIBLE sub-problem result before invoking).
2. Each deletion trial: only ``INFEASIBLE`` shrinks the core.
3. ``FEASIBLE`` keeps the literal (essential) and continues.
4. ``UNKNOWN`` / ``TIMEOUT`` (oracle's own response) keeps the literal and
   continues — spec "fail-closed (保留旧 core)" means do not shrink, not stop.
   ``is_minimal`` reports ``False`` whenever any inconclusive reply occurred.
5. Oracle ``raise`` ends the loop early with ``EXCEPTION_FAIL_CLOSED``;
   never propagate the exception.
6. Budget exhaustion (calls or seconds) ends the loop early; return last
   verified core. Never return an unverified partial.

The minimizer's contract assumes the oracle is **untrusted** — sub-problem
adapters in ``src/cuts/oracles/pattern_nogood_oracle.py`` wrap the real
binding / routing / pcr_cut solvers behind a uniform ``OracleCallback``
interface.

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F5
- docs/项目说明/12_go_criteria.md §8.1.x acceptance A
- docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Literal, Tuple

from src.cuts.lifecycle import GroupId, PoseId


class CoreStoppedReason(str, Enum):
    """4-value closed set. Validator membership-checks at deserialize time."""

    INFEASIBLE_VERIFIED = "INFEASIBLE_VERIFIED"
    TIMEOUT = "TIMEOUT"
    MAX_CALLS = "MAX_CALLS"
    EXCEPTION_FAIL_CLOSED = "EXCEPTION_FAIL_CLOSED"


VALID_STOPPED_REASONS: frozenset[str] = frozenset(r.value for r in CoreStoppedReason)


OracleVerdict = Literal["INFEASIBLE", "FEASIBLE", "UNKNOWN", "TIMEOUT"]
VALID_ORACLE_VERDICTS: frozenset[str] = frozenset(("INFEASIBLE", "FEASIBLE", "UNKNOWN", "TIMEOUT"))


LiteralAssignment = Tuple[GroupId, int, PoseId]
"""Canonical sortable triple: (group_id, slot_index, pose_id).

slot_index participates in canonical sort for deterministic cert_hash but does
NOT participate in soundness binding (state_machine_v2 §5 multiset anonymity).
"""


OracleCallback = Callable[[Tuple[LiteralAssignment, ...]], OracleVerdict]


@dataclass(frozen=True)
class MinimizerBudget:
    """Hard-cap pair. Either threshold first ends the loop early."""

    max_calls: int = 64
    max_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.max_calls, int) or isinstance(self.max_calls, bool):
            raise ValueError(
                f"max_calls must be strict int, got {type(self.max_calls).__name__}"
            )
        if self.max_calls < 1:
            raise ValueError(f"max_calls must be >= 1, got {self.max_calls}")
        if isinstance(self.max_seconds, bool) or not isinstance(
            self.max_seconds, (int, float)
        ):
            raise ValueError(
                f"max_seconds must be float, got {type(self.max_seconds).__name__}"
            )
        if self.max_seconds <= 0.0:
            raise ValueError(f"max_seconds must be > 0.0, got {self.max_seconds}")


@dataclass(frozen=True)
class CoreMinimizeResult:
    """Last-verified-INFEASIBLE core + audit fields.

    Invariant: ``core`` is always derived from an INFEASIBLE oracle verdict —
    either the initial full-assignment verify or a strictly later shrink.
    ``is_verified_infeasible`` is True under every stopped_reason; the explicit
    field is schema-level paranoia (validator rejects ``False``).
    """

    core: Tuple[LiteralAssignment, ...]
    is_minimal: bool
    is_verified_infeasible: bool  # invariant True; validator rejects False
    calls: int
    elapsed_seconds: float
    stopped_reason: CoreStoppedReason
    size_before: int
    size_after: int


def canonical_sort_assignment(
    assignment: Tuple[LiteralAssignment, ...],
) -> Tuple[LiteralAssignment, ...]:
    """Sort by (group_id, slot_index, pose_id) lex + dedup.

    Dedup is defense-in-depth: caller may pass duplicates by accident; without
    dedup the minimizer's deletion loop would waste oracle calls re-evaluating
    the same trial_core after a FEASIBLE response (per Gemini F5 review #5).
    """
    sorted_tuple = tuple(sorted(assignment, key=lambda lit: (lit[0], lit[1], lit[2])))
    return tuple(dict.fromkeys(sorted_tuple))


def deletion_minimize_core(
    assignment: Tuple[LiteralAssignment, ...],
    oracle: OracleCallback,
    budget: MinimizerBudget = MinimizerBudget(),
) -> CoreMinimizeResult:
    """Deletion-based bounded MUS minimizer with paranoid fail-closed.

    Raises:
        ValueError: assignment empty, or the initial full-assignment oracle
            call returns anything other than INFEASIBLE (caller contract).
    """
    if not assignment:
        raise ValueError("deletion_minimize_core: assignment must be non-empty")

    sorted_assignment = canonical_sort_assignment(assignment)
    size_before = len(sorted_assignment)

    t0 = time.monotonic()
    initial_verdict = oracle(sorted_assignment)
    if initial_verdict != "INFEASIBLE":
        raise ValueError(
            f"deletion_minimize_core: initial verify returned {initial_verdict!r}, "
            f"expected INFEASIBLE (caller contract violated)"
        )

    current_core: Tuple[LiteralAssignment, ...] = sorted_assignment
    calls = 1
    had_inconclusive = False

    for lit in reversed(sorted_assignment):
        if calls >= budget.max_calls:
            return _build_result(
                current_core,
                is_minimal=False,
                calls=calls,
                t0=t0,
                stopped_reason=CoreStoppedReason.MAX_CALLS,
                size_before=size_before,
            )
        if time.monotonic() - t0 >= budget.max_seconds:
            return _build_result(
                current_core,
                is_minimal=False,
                calls=calls,
                t0=t0,
                stopped_reason=CoreStoppedReason.TIMEOUT,
                size_before=size_before,
            )
        if lit not in current_core:
            # Defensive: literal already removed in a prior iter. canonical_sort_assignment
            # now dedups input (Gemini F5 round 1 fix #5), so this branch is
            # effectively dead under normal calls; kept as a belt-and-suspenders
            # guard against future callers that bypass canonical_sort.
            continue
        trial_core = tuple(x for x in current_core if x != lit)
        if not trial_core:
            # Keep at least one literal (empty core has no meaning as a nogood).
            continue
        try:
            verdict = oracle(trial_core)
            if verdict not in VALID_ORACLE_VERDICTS:
                # Per Gemini F5 round 3 review #1: a buggy adapter returning
                # an out-of-closed-set verdict (e.g. "BOGUS") would otherwise
                # silently fall through — neither shrinking core nor flagging
                # had_inconclusive — and break the is_minimal contract. Treat
                # as adapter exception → fail-closed via EXCEPTION_FAIL_CLOSED.
                raise ValueError(
                    f"oracle returned invalid verdict {verdict!r}; "
                    f"expected one of {sorted(VALID_ORACLE_VERDICTS)}"
                )
        except Exception:  # noqa: BLE001 — fail-closed: oracle is untrusted
            return _build_result(
                current_core,
                is_minimal=False,
                calls=calls + 1,
                t0=t0,
                stopped_reason=CoreStoppedReason.EXCEPTION_FAIL_CLOSED,
                size_before=size_before,
            )
        calls += 1
        if verdict == "INFEASIBLE":
            current_core = trial_core
        elif verdict in ("UNKNOWN", "TIMEOUT"):
            had_inconclusive = True
        # FEASIBLE keeps literal silently; INFEASIBLE/FEASIBLE both are
        # decisive responses, only UNKNOWN/TIMEOUT lower is_minimal at end.

    return _build_result(
        current_core,
        is_minimal=not had_inconclusive,
        calls=calls,
        t0=t0,
        stopped_reason=CoreStoppedReason.INFEASIBLE_VERIFIED,
        size_before=size_before,
    )


def _build_result(
    core: Tuple[LiteralAssignment, ...],
    *,
    is_minimal: bool,
    calls: int,
    t0: float,
    stopped_reason: CoreStoppedReason,
    size_before: int,
) -> CoreMinimizeResult:
    return CoreMinimizeResult(
        core=core,
        is_minimal=is_minimal,
        is_verified_infeasible=True,
        calls=calls,
        elapsed_seconds=time.monotonic() - t0,
        stopped_reason=stopped_reason,
        size_before=size_before,
        size_after=len(core),
    )
