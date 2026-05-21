"""Phase 2 Task 2 — Ryan-Foster branching for set-partitioning column generation.

Background (Ryan-Foster 1981, "An integer programming approach to scheduling"):
    For a set-partitioning master min c^T λ s.t. Aλ = 1, λ ∈ {0,1}^K
    where each column k covers a subset S_k of instances, the
    standard "most-fractional λ_k" branching is degenerate (forces λ_k=0
    on one side ⇒ no real branching on instance-pairs).  Ryan-Foster
    picks a *fractional pair* (i, j) — two instances both covered by
    some fractional column λ_k > 0 — and branches:
        same(i, j):       every column either covers {i, j} both, or
                          covers neither.  Pricing extra constraint:
                          z[i] == z[j] within any feasible column.
        different(i, j):  no column may cover both i and j.  Pricing
                          extra constraint: z[i] + z[j] <= 1.
    This pair-branching always reduces the fractional LP face and
    avoids the most-fractional-λ degeneracy.

Phase 2 implementation:
    - BranchDecision dataclass stores (i, j, kind) where kind ∈
      {"same", "diff"}.
    - BranchNode carries a list of decisions accumulated down the tree.
    - Inside pricing CP-SAT (`apply_ryan_foster_to_pricing`), we add
      hard constraints over the z[iid] aggregated booleans:
        "same" -> z[i] == z[j]
        "diff" -> z[i] + z[j] <= 1
    - Inside RMP LP (`apply_ryan_foster_to_rmp`), we force columns that
      violate a branch decision to λ_k = 0 (upper bound = 0).
    - Selecting the Ryan-Foster pair: scan fractional columns, find any
      (i, j) appearing together with the highest "imbalance score"
      (= |0.5 - frac_cover(i, j)| inverted, ranked smallest first).

Phase 1 m11 nodes on 5-80 inst stayed in 11/33/53 range with most-
fractional λ branching.  Phase 2 expects Ryan-Foster to halve nodes on
larger ramps (160/266 inst) by avoiding the degenerate-λ explosion.

The same/diff decisions are *not* lifted to RMP coverage directly —
RMP keeps the set-partition Aλ=1 unchanged.  Ryan-Foster compatibility
is enforced by zero-forcing the existing pool's incompatible columns
+ excluding them in *future* pricing rounds.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class BranchDecision:
    """Single Ryan-Foster decision.

    kind: "same" | "diff"
    i, j: instance ids (sorted lexicographically — canonical form).
    """

    i: str
    j: str
    kind: str  # "same" | "diff"

    @staticmethod
    def make(a: str, b: str, kind: str) -> "BranchDecision":
        lo, hi = (a, b) if a <= b else (b, a)
        return BranchDecision(i=lo, j=hi, kind=kind)


@dataclass
class BranchNode:
    """Tree node with accumulated Ryan-Foster decisions."""

    decisions: Tuple[BranchDecision, ...] = ()
    depth: int = 0

    def with_decision(self, dec: BranchDecision) -> "BranchNode":
        return BranchNode(decisions=self.decisions + (dec,), depth=self.depth + 1)

    def is_consistent(self) -> bool:
        """True iff decision set contains no contradiction (same+diff same pair)."""
        same: Set[Tuple[str, str]] = set()
        diff: Set[Tuple[str, str]] = set()
        for d in self.decisions:
            pair = (d.i, d.j)
            if d.kind == "same":
                if pair in diff:
                    return False
                same.add(pair)
            elif d.kind == "diff":
                if pair in same:
                    return False
                diff.add(pair)
        return True


# === Pair selection from fractional LP solution ===


def select_ryan_foster_pair(
    columns: Sequence[Any],            # Phase 1 Pattern
    lambda_values: Sequence[float],
    *,
    integer_tol: float = 1e-6,
    decisions: Sequence[BranchDecision] = (),
) -> Optional[Tuple[str, str]]:
    """Pick a fractional pair (i, j) to branch on.

    Algorithm (Ryan-Foster classic):
        1. Compute pair_frac[i, j] = sum over fractional λ_k where
           column k covers both i and j.
        2. Pick the pair with pair_frac closest to 0.5 (most balanced
           = strongest fractional resolution).
        3. Skip pairs that already have a same/diff decision on the
           path.

    Returns None if no fractional pair exists (LP is integer-feasible).
    """
    pair_sum: Dict[Tuple[str, str], float] = defaultdict(float)
    pair_count: Dict[Tuple[str, str], int] = defaultdict(int)
    decided: Set[Tuple[str, str]] = {(d.i, d.j) for d in decisions}

    for k, lam in enumerate(lambda_values):
        if lam <= integer_tol or lam >= 1.0 - integer_tol:
            continue
        cov = sorted({iid for (iid, _tpl, _p) in columns[k].facility_assignments})
        for i_idx in range(len(cov)):
            for j_idx in range(i_idx + 1, len(cov)):
                pair = (cov[i_idx], cov[j_idx])
                if pair in decided:
                    continue
                pair_sum[pair] += lam
                pair_count[pair] += 1

    if not pair_sum:
        return None
    # Pick pair whose fractional cover is closest to 0.5.
    best_pair: Optional[Tuple[str, str]] = None
    best_score = 1e9
    for pair, total in pair_sum.items():
        score = abs(total - 0.5)
        if score < best_score:
            best_score = score
            best_pair = pair
    return best_pair


# === Pruning RMP pool against accumulated decisions ===


def column_compatible_with_decisions(
    col: Any,
    decisions: Sequence[BranchDecision],
) -> bool:
    """True iff column respects all decisions."""
    if not decisions:
        return True
    cov = {iid for (iid, _tpl, _p) in col.facility_assignments}
    for d in decisions:
        i_in = d.i in cov
        j_in = d.j in cov
        if d.kind == "same":
            if i_in != j_in:
                return False
        elif d.kind == "diff":
            if i_in and j_in:
                return False
    return True


def column_pool_mask(
    columns: Sequence[Any],
    decisions: Sequence[BranchDecision],
) -> List[bool]:
    """Returns mask[k] = True iff column k is feasible under decisions."""
    return [column_compatible_with_decisions(c, decisions) for c in columns]


# === Pricing CP-SAT decoration ===


def apply_ryan_foster_to_pricing(
    model: Any,
    z_vars: Mapping[Tuple[str, int], Any],
    decisions: Sequence[BranchDecision],
) -> int:
    """Add Ryan-Foster constraints to the pricing CP-SAT model.

    z_vars: (iid, pose_idx) -> BoolVar
    For each instance iid we sum its z[iid, *] into a top-level "iid
    selected" bool (already implicit via at-most-one in pricing — we
    use sum >= 1 as proxy).  Then:
        same(i, j): sum_p z[i, p] == sum_p z[j, p]
        diff(i, j): sum_p z[i, p] + sum_p z[j, p] <= 1

    Returns number of constraints added.
    """
    if not decisions:
        return 0
    by_iid: Dict[str, List[Any]] = defaultdict(list)
    for (iid, _p), v in z_vars.items():
        by_iid[iid].append(v)
    added = 0
    for d in decisions:
        i_terms = by_iid.get(d.i, [])
        j_terms = by_iid.get(d.j, [])
        if not i_terms and not j_terms:
            continue
        i_sum = sum(i_terms) if i_terms else 0
        j_sum = sum(j_terms) if j_terms else 0
        if d.kind == "same":
            model.Add(i_sum == j_sum)
            added += 1
        elif d.kind == "diff":
            model.Add(i_sum + j_sum <= 1)
            added += 1
    return added


# === Branching statistics ===


@dataclass
class RyanFosterStats:
    """Telemetry collected by Phase 2 branch-and-price runs."""

    nodes_explored: int = 0
    integer_leaves_found: int = 0
    best_objective: float = float("inf")
    best_lambda: Optional[List[float]] = None
    timed_out: bool = False
    max_depth_reached: int = 0
    same_decisions: int = 0
    diff_decisions: int = 0
    incompatible_columns_pruned: int = 0


__all__ = [
    "BranchDecision",
    "BranchNode",
    "RyanFosterStats",
    "select_ryan_foster_pair",
    "column_compatible_with_decisions",
    "column_pool_mask",
    "apply_ryan_foster_to_pricing",
]
