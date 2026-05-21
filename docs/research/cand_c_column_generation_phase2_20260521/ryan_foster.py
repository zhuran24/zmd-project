"""Phase 2 Task 2 — Ryan-Foster branching with telemetry + standard fallback.

This file was rewritten 2026-05-21 to address Phase 2 v1 (commit 73ea69a)
bug 2: `RF branching: nodes=N leaves=0 best_obj=inf` at the 80-inst and
80inst_routing_aware ramps.

What changed vs v1
==================

1. **Per-node telemetry** — every visited node now records
   `(decisions, lp_status, lp_obj, integer_feasible, pair_picked)` so
   we can diagnose leaves=0 post-hoc.  See `BranchNodeTrace`.

2. **Deeper default max_depth** — the caller can still cap at 5 for
   sanity but the diagnosis from Phase 2 v1 indicates depth 5 isn't
   enough for 80-inst (the LP needs ~7-9 Ryan-Foster decisions before
   the residual fractional pair set is empty).  Phase 2 v2 raises the
   default to 10.  Caller passes its own max_depth.

3. **At-depth-cap behaviour** — v1 silently abandoned a node at
   `depth >= max_depth` with no leaf recorded.  v2 instead falls back
   to *most-fractional λ rounding* (the v1 standard branching used in
   `phase1_probe.branch_and_price_depth_first`) on the surviving LP
   solution: if the LP is fractional at the depth cap, we attempt to
   round each fractional λ_k to its nearest integer (with cell-conflict
   resolution by greedy) and check whether the rounded vector is a
   feasible integer solution.  If yes — a leaf is recorded (with
   `leaf_kind="rounded_at_cap"`).  If no — the node is genuinely
   abandoned (recorded with `leaf_kind="abandoned_at_cap"`).

4. **Standard B&P fallback** — `branch_and_price_with_fallback` runs
   Ryan-Foster first; if leaves_found == 0 after the budget, it
   re-runs the v1 most-fractional standard branching from
   `phase1_probe.branch_and_price_depth_first` so m10 integer
   reconstruction still has a chance to pass and m14 still records
   "RF failed, std fallback used".

5. **Pool mask debug** — `column_pool_mask` now also returns a
   per-decision count summary so the probe can log "decision d killed
   N columns".

Schema notes
------------

`BranchDecision`, `BranchNode`, and `RyanFosterStats` keep their v1
fields (no breaking API changes for existing imports).  The new
telemetry is exposed via two added fields on `RyanFosterStats`:

    .node_traces: List[BranchNodeTrace]  (length <= nodes_explored)
    .leaves_kind_counts: Dict[str, int]  (e.g. {"natural": 2, "rounded_at_cap": 1})
    .fallback_used: bool                  (True if std B&P was triggered)
    .fallback_stats: Optional[Any]        (Phase 1 BranchStats if triggered)

`select_ryan_foster_pair` and `apply_ryan_foster_to_pricing` keep the
v1 signatures.  `column_compatible_with_decisions` + `column_pool_mask`
gain optional `return_summary=True` for diagnostics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


# === Branch decision + node primitives (v1-compatible) ===


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
    decisions: Tuple[BranchDecision, ...] = ()
    depth: int = 0

    def with_decision(self, dec: BranchDecision) -> "BranchNode":
        return BranchNode(decisions=self.decisions + (dec,), depth=self.depth + 1)

    def is_consistent(self) -> bool:
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


# === Pair selection ===


def select_ryan_foster_pair(
    columns: Sequence[Any],
    lambda_values: Sequence[float],
    *,
    integer_tol: float = 1e-6,
    decisions: Sequence[BranchDecision] = (),
) -> Optional[Tuple[str, str]]:
    """Pick a fractional pair (i, j) to branch on."""
    pair_sum: Dict[Tuple[str, str], float] = defaultdict(float)
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

    if not pair_sum:
        return None
    best_pair: Optional[Tuple[str, str]] = None
    best_score = 1e9
    for pair, total in pair_sum.items():
        score = abs(total - 0.5)
        if score < best_score:
            best_score = score
            best_pair = pair
    return best_pair


# === Pool masking ===


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
    *,
    return_summary: bool = False,
) -> Any:
    """Returns mask[k] = True iff column k is feasible under decisions.

    With return_summary=True returns (mask, summary_dict) where summary
    counts the killed columns per decision (for diagnostics).
    """
    mask = [column_compatible_with_decisions(c, decisions) for c in columns]
    if not return_summary:
        return mask
    # Count per-decision impact: how many columns each individual
    # decision kills (treated independently).
    summary: Dict[str, Any] = {
        "n_columns": len(columns),
        "n_kept": sum(mask),
        "n_killed": len(mask) - sum(mask),
        "per_decision": [],
    }
    for d in decisions:
        killed = sum(
            1 for c in columns if not column_compatible_with_decisions(c, [d])
        )
        summary["per_decision"].append({
            "i": d.i, "j": d.j, "kind": d.kind, "killed": killed,
        })
    return mask, summary


# === Pricing CP-SAT decoration ===


def apply_ryan_foster_to_pricing(
    model: Any,
    z_vars: Mapping[Tuple[str, int], Any],
    decisions: Sequence[BranchDecision],
) -> int:
    """Add Ryan-Foster constraints to the pricing CP-SAT model."""
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


# === Per-node telemetry ===


@dataclass
class BranchNodeTrace:
    node_idx: int
    depth: int
    n_decisions: int
    last_decision: Optional[Tuple[str, str, str]]  # (i, j, kind)
    lp_status: str
    lp_objective: float
    n_fractional_pairs: int
    pair_picked: Optional[Tuple[str, str]]
    is_integer_feasible: bool
    pool_kept: int
    pool_total: int
    pool_killed_by_last_decision: int
    leaf_kind: str  # "natural" | "rounded_at_cap" | "abandoned_at_cap" | "pruned" | "infeasible" | "interior"


@dataclass
class RyanFosterStats:
    nodes_explored: int = 0
    integer_leaves_found: int = 0
    best_objective: float = float("inf")
    best_lambda: Optional[List[float]] = None
    timed_out: bool = False
    max_depth_reached: int = 0
    same_decisions: int = 0
    diff_decisions: int = 0
    incompatible_columns_pruned: int = 0
    # Phase 2 v2 additions.
    node_traces: List[BranchNodeTrace] = field(default_factory=list)
    leaves_kind_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    fallback_used: bool = False
    fallback_stats: Optional[Any] = None


# === Rounded leaf attempt (depth-cap salvage) ===


def _attempt_rounded_leaf(
    columns: Sequence[Any],
    lambda_values: Sequence[float],
    instance_ids: Sequence[str],
) -> Optional[List[float]]:
    """Greedy round of fractional λ.

    Strategy:
        Sort fractional columns by λ_k descending.  Greedily set λ_k=1
        if (a) it covers at least one instance not yet covered, and
        (b) it doesn't conflict cell-wise with any already-selected
        column.  Set all other λ_k = 0.  Return the rounded vector iff
        every instance is covered exactly once; None otherwise.
    """
    n = len(columns)
    rounded = [0.0] * n
    # Already-integer-1 columns are accepted as-is.
    fixed_ones = [k for k in range(n) if lambda_values[k] >= 1.0 - 1e-6]
    for k in fixed_ones:
        rounded[k] = 1.0
    used_cells: Set[Tuple[int, int]] = set()
    covered: Set[str] = set()
    conflict_within_fixed = False
    for k in fixed_ones:
        cells = columns[k].occupied_cells
        if used_cells.intersection(cells):
            conflict_within_fixed = True
            break
        used_cells.update(cells)
        covered.update(columns[k].covered_instance_ids)
    if conflict_within_fixed:
        return None

    # Greedy on fractional columns.
    ordered = sorted(
        (k for k in range(n) if 1e-6 < lambda_values[k] < 1.0 - 1e-6),
        key=lambda k: -lambda_values[k],
    )
    for k in ordered:
        cells = columns[k].occupied_cells
        if used_cells.intersection(cells):
            continue
        iids = columns[k].covered_instance_ids
        new_iids = iids - covered
        if not new_iids:
            continue
        rounded[k] = 1.0
        used_cells.update(cells)
        covered.update(iids)
    # Validate: every instance exactly once + no duplicate cover.
    if not covered.issuperset(set(instance_ids)):
        return None
    # Check no instance covered twice.
    cover_counts: Dict[str, int] = defaultdict(int)
    for k in range(n):
        if rounded[k] >= 0.5:
            for iid in columns[k].covered_instance_ids:
                cover_counts[iid] += 1
    if any(v != 1 for iid, v in cover_counts.items() if iid in set(instance_ids)):
        return None
    return rounded


# === Main RF B&P (with telemetry + rounded-at-cap) ===


def branch_and_price_ryan_foster_v2(
    columns: Sequence[Any],
    instance_ids: Sequence[str],
    rmp_solver: Any,                # callable(columns, ids, decisions=...) -> RMPResult-like
    *,
    max_depth: int = 10,
    max_nodes: int = 1000,
    wall_budget_s: float = 60.0,
    integer_tol: float = 1e-6,
    capture_traces: bool = True,
    log: Optional[Any] = None,
) -> RyanFosterStats:
    """DFS B&P with v2 telemetry + rounded-at-cap salvage.

    The `rmp_solver` callable lets the caller pass any RMP function with
    a `decisions=` kwarg.  Phase 2 probe wraps `solve_rmp_phase2` for
    this.  Each call must return an object with attributes
    `.status_str`, `.objective`, and `.lambda_values`.
    """
    import time

    def _emit(msg: str) -> None:
        if log is not None:
            log(msg)

    stats = RyanFosterStats()
    t0 = time.perf_counter()
    stack: List[BranchNode] = [BranchNode(decisions=(), depth=0)]
    node_idx = 0
    while stack:
        if time.perf_counter() - t0 > wall_budget_s:
            stats.timed_out = True
            break
        if stats.nodes_explored >= max_nodes:
            break
        node = stack.pop()
        if not node.is_consistent():
            continue
        stats.nodes_explored += 1
        stats.max_depth_reached = max(stats.max_depth_reached, node.depth)

        # RMP solve at this node.
        rmp_res = rmp_solver(columns, instance_ids, decisions=node.decisions)
        last_dec = (
            (node.decisions[-1].i, node.decisions[-1].j, node.decisions[-1].kind)
            if node.decisions else None
        )

        # Pool diagnostics for the trace.
        if capture_traces:
            mask, summary = column_pool_mask(
                columns, node.decisions, return_summary=True,
            )
            pool_kept = summary["n_kept"]
            pool_total = summary["n_columns"]
            pool_killed_by_last = (
                summary["per_decision"][-1]["killed"]
                if summary["per_decision"] else 0
            )
        else:
            pool_kept = pool_total = pool_killed_by_last = -1

        if rmp_res.status_str not in ("OPTIMAL", "FEASIBLE"):
            if capture_traces:
                stats.node_traces.append(BranchNodeTrace(
                    node_idx=node_idx, depth=node.depth,
                    n_decisions=len(node.decisions),
                    last_decision=last_dec,
                    lp_status=rmp_res.status_str,
                    lp_objective=float("inf"),
                    n_fractional_pairs=0,
                    pair_picked=None,
                    is_integer_feasible=False,
                    pool_kept=pool_kept, pool_total=pool_total,
                    pool_killed_by_last_decision=pool_killed_by_last,
                    leaf_kind="infeasible",
                ))
            node_idx += 1
            continue

        # Count fractional pairs at this LP.
        n_frac_pairs = 0
        if capture_traces:
            ps: Set[Tuple[str, str]] = set()
            for k, lam in enumerate(rmp_res.lambda_values):
                if 1e-6 < lam < 1.0 - 1e-6:
                    cov = sorted({iid for (iid, _t, _p) in columns[k].facility_assignments})
                    for a in range(len(cov)):
                        for b in range(a + 1, len(cov)):
                            ps.add((cov[a], cov[b]))
            n_frac_pairs = len(ps)

        if rmp_res.objective >= stats.best_objective - 1e-9:
            if capture_traces:
                stats.node_traces.append(BranchNodeTrace(
                    node_idx=node_idx, depth=node.depth,
                    n_decisions=len(node.decisions),
                    last_decision=last_dec,
                    lp_status=rmp_res.status_str,
                    lp_objective=float(rmp_res.objective),
                    n_fractional_pairs=n_frac_pairs,
                    pair_picked=None,
                    is_integer_feasible=False,
                    pool_kept=pool_kept, pool_total=pool_total,
                    pool_killed_by_last_decision=pool_killed_by_last,
                    leaf_kind="pruned",
                ))
            node_idx += 1
            continue

        pair = select_ryan_foster_pair(
            columns, rmp_res.lambda_values,
            integer_tol=integer_tol, decisions=node.decisions,
        )
        if pair is None:
            # Natural integer leaf — no fractional pair remains.
            stats.integer_leaves_found += 1
            stats.leaves_kind_counts["natural"] += 1
            if rmp_res.objective < stats.best_objective:
                stats.best_objective = rmp_res.objective
                stats.best_lambda = list(rmp_res.lambda_values)
            if capture_traces:
                stats.node_traces.append(BranchNodeTrace(
                    node_idx=node_idx, depth=node.depth,
                    n_decisions=len(node.decisions),
                    last_decision=last_dec,
                    lp_status=rmp_res.status_str,
                    lp_objective=float(rmp_res.objective),
                    n_fractional_pairs=0,
                    pair_picked=None,
                    is_integer_feasible=True,
                    pool_kept=pool_kept, pool_total=pool_total,
                    pool_killed_by_last_decision=pool_killed_by_last,
                    leaf_kind="natural",
                ))
            node_idx += 1
            continue

        if node.depth >= max_depth:
            # Depth-cap salvage: try rounding the fractional λ.
            rounded = _attempt_rounded_leaf(
                columns, rmp_res.lambda_values, instance_ids,
            )
            if rounded is not None:
                # Cost of rounded solution.
                cost = sum(columns[k].cost for k in range(len(columns)) if rounded[k] >= 0.5)
                stats.integer_leaves_found += 1
                stats.leaves_kind_counts["rounded_at_cap"] += 1
                if cost < stats.best_objective:
                    stats.best_objective = float(cost)
                    stats.best_lambda = list(rounded)
                if capture_traces:
                    stats.node_traces.append(BranchNodeTrace(
                        node_idx=node_idx, depth=node.depth,
                        n_decisions=len(node.decisions),
                        last_decision=last_dec,
                        lp_status=rmp_res.status_str,
                        lp_objective=float(rmp_res.objective),
                        n_fractional_pairs=n_frac_pairs,
                        pair_picked=pair,
                        is_integer_feasible=False,
                        pool_kept=pool_kept, pool_total=pool_total,
                        pool_killed_by_last_decision=pool_killed_by_last,
                        leaf_kind="rounded_at_cap",
                    ))
            else:
                stats.leaves_kind_counts["abandoned_at_cap"] += 1
                if capture_traces:
                    stats.node_traces.append(BranchNodeTrace(
                        node_idx=node_idx, depth=node.depth,
                        n_decisions=len(node.decisions),
                        last_decision=last_dec,
                        lp_status=rmp_res.status_str,
                        lp_objective=float(rmp_res.objective),
                        n_fractional_pairs=n_frac_pairs,
                        pair_picked=pair,
                        is_integer_feasible=False,
                        pool_kept=pool_kept, pool_total=pool_total,
                        pool_killed_by_last_decision=pool_killed_by_last,
                        leaf_kind="abandoned_at_cap",
                    ))
            node_idx += 1
            continue

        # Branch: same first (LIFO push order — diff first explored).
        same_dec = BranchDecision.make(pair[0], pair[1], "same")
        diff_dec = BranchDecision.make(pair[0], pair[1], "diff")
        stats.same_decisions += 1
        stats.diff_decisions += 1
        stack.append(node.with_decision(same_dec))
        stack.append(node.with_decision(diff_dec))
        if capture_traces:
            stats.node_traces.append(BranchNodeTrace(
                node_idx=node_idx, depth=node.depth,
                n_decisions=len(node.decisions),
                last_decision=last_dec,
                lp_status=rmp_res.status_str,
                lp_objective=float(rmp_res.objective),
                n_fractional_pairs=n_frac_pairs,
                pair_picked=pair,
                is_integer_feasible=False,
                pool_kept=pool_kept, pool_total=pool_total,
                pool_killed_by_last_decision=pool_killed_by_last,
                leaf_kind="interior",
            ))
        node_idx += 1
    _emit(
        f"[RF v2] done nodes={stats.nodes_explored} "
        f"leaves={stats.integer_leaves_found} "
        f"leaves_kind={dict(stats.leaves_kind_counts)} "
        f"max_depth={stats.max_depth_reached}"
    )
    return stats


# === RF + standard fallback wrapper ===


def branch_and_price_with_fallback(
    columns: Sequence[Any],
    instance_ids: Sequence[str],
    rmp_solver_rf: Any,
    rmp_solver_std: Any,
    *,
    rf_max_depth: int = 10,
    rf_max_nodes: int = 1000,
    rf_wall_budget_s: float = 60.0,
    std_max_depth: int = 5,
    std_max_nodes: int = 1000,
    std_wall_budget_s: float = 60.0,
    log: Optional[Any] = None,
) -> RyanFosterStats:
    """Run RF B&P first; if leaves_found == 0, run std most-fractional.

    The std fallback uses Phase 1 `branch_and_price_depth_first` against
    the same column pool.  Its result is wired into RyanFosterStats's
    `.fallback_stats` for downstream m10/m14 reporting.
    """
    def _emit(msg: str) -> None:
        if log is not None:
            log(msg)

    rf_stats = branch_and_price_ryan_foster_v2(
        columns, instance_ids, rmp_solver_rf,
        max_depth=rf_max_depth, max_nodes=rf_max_nodes,
        wall_budget_s=rf_wall_budget_s, log=log,
    )
    if rf_stats.integer_leaves_found > 0:
        return rf_stats
    _emit(
        "[RF v2] leaves==0 after RF B&P, falling back to standard "
        "most-fractional branching"
    )
    # Import here to avoid module-level cycle.
    from cand_c_column_generation_phase1_20260521 import phase1_probe as p1  # type: ignore
    std_stats = p1.branch_and_price_depth_first(
        columns, instance_ids,
        max_depth=std_max_depth, max_nodes=std_max_nodes,
        wall_budget_s=std_wall_budget_s,
    )
    rf_stats.fallback_used = True
    rf_stats.fallback_stats = std_stats
    if std_stats.best_lambda is not None:
        if rf_stats.best_lambda is None or std_stats.best_objective < rf_stats.best_objective:
            rf_stats.best_objective = std_stats.best_objective
            rf_stats.best_lambda = list(std_stats.best_lambda)
            rf_stats.leaves_kind_counts["std_fallback"] += 1
            rf_stats.integer_leaves_found += std_stats.integer_leaves_found
    _emit(
        f"[RF v2] std fallback: nodes={std_stats.nodes_explored} "
        f"leaves={std_stats.integer_leaves_found} "
        f"best_obj={std_stats.best_objective}"
    )
    return rf_stats


__all__ = [
    "BranchDecision",
    "BranchNode",
    "BranchNodeTrace",
    "RyanFosterStats",
    "select_ryan_foster_pair",
    "column_compatible_with_decisions",
    "column_pool_mask",
    "apply_ryan_foster_to_pricing",
    "branch_and_price_ryan_foster_v2",
    "branch_and_price_with_fallback",
]
