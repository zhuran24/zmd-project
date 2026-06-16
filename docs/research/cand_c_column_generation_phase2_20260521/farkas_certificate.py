"""Phase 2 v3 A2 — Farkas-certificate-guided Layer-2 retry (backup-of-backup).

Why A2 exists
=============

Phase 2 v2 sometimes ends with the iter-0 RMP LP returning INFEASIBLE
(160-/266-inst ramps).  Phase 2 v3's primary fix is A3 (set-covering
relaxation, `EXACT_CANDC_LP_SET_COVERING=1`, default ON).  A1
(alternative blueprint generator) is the secondary fix.  A2 is the
*backup-of-backup* for the case where, even under A3, an early iter
still flips INFEASIBLE — typically because the bootstrap column pool
exposes a structural conflict that set-covering relaxation alone
can't paper over.

When LP returns INFEASIBLE, the dual-simplex solver can emit a
**Farkas certificate** (a.k.a. dual ray) — a vector ``y`` over the
constraint rows such that

    yᵀ A  ≤  0   (component-wise)
    yᵀ b  >  0

This is a sound proof of LP infeasibility.  The cell-exclusivity rows
of the RMP carry the spatial signature: any row ``i`` with large
``|y_i|`` corresponds to a grid cell that is "over-demanded" by the
current column pool.  We call these "hotspot cells".

A2 strategy
-----------

1. On RMP INFEASIBLE, rebuild the *same* LP in HiGHS (with presolve
   off so the simplex actually completes and exposes the ray, instead
   of HiGHS presolve killing it early as INFEASIBLE without a ray).
2. Extract the dual ray.  Map back to cell-exclusivity rows and
   identify hotspot cells (``|y_i| ≥ τ``).  τ defaults to "top-K
   absolute coefficients" plus a hard floor on magnitude — see
   :func:`extract_hotspot_cells`.
3. Reuse :func:`alternative_blueprint_generator.generate_alternative_columns`
   with ``exclude_cells = hotspot cells`` to generate a fresh batch
   of multi-facility columns that physically avoid the hotspot.
4. Append them to the column pool and re-solve RMP.
5. Repeat up to ``EXACT_CANDC_A2_MAX_ROUNDS`` times.

Soundness
---------

A2 only **adds** columns to the RMP.  The integer reconstruction
phase (Ryan-Foster branching + integer_validator) still enforces
exact set-partition coverage downstream — A2 doesn't relax anything.
If A2 also fails (still INFEASIBLE after max rounds), behaviour is
identical to A2-disabled: the main loop hits the same INFEASIBLE
exit reason it would have hit anyway.  A3 is then expected to handle
it (set covering is already on).

Failure modes (documented in the parent prompt's "A2 failure mode"
section):

A. ortools GLOP cannot expose the Farkas certificate via the
   `pywraplp` Python wrapper (verified empirically: ``dual_value()``
   returns 0 on INFEASIBLE, the protobuf MPSolutionResponse has no
   ``dual_ray`` field).  Workaround: mirror the LP in HiGHS via
   ``highspy`` and call ``Highs.getDualRay()``.  This module
   implements the mirror.
B. Farkas certificate extracted but no significant hotspot cell
   (``|y_i| < ε`` everywhere).  A2 then degrades to a noop and the
   round count caps out without forbidden_cells; the main loop
   falls through to the INFEASIBLE exit (or to A3 set covering).
C. Hotspot cells extracted but generated alternatives still leave
   the LP INFEASIBLE.  Up to ``MAX_ROUNDS`` retries before giving
   up.

Env flags
---------

* ``EXACT_CANDC_A2_DUAL_GUIDED``           — 1/true/yes/on → enable (default off)
* ``EXACT_CANDC_A2_MAX_ROUNDS``            — max Farkas-retry rounds per
                                              INFEASIBLE event (default 5)
* ``EXACT_CANDC_A2_HOTSPOT_TOP_K``         — max hotspot cells per round
                                              (default 50)
* ``EXACT_CANDC_A2_HOTSPOT_MAG_FLOOR``     — minimum absolute dual
                                              coefficient to count a row
                                              as hotspot (default 1e-6)
* ``EXACT_CANDC_A2_ALTS_PER_ROUND``        — alternative columns to
                                              generate per round
                                              (default 10)

This module never touches ``src/``.  All inputs come from the existing
Phase 2 RMP column pool; outputs are extra ``Pattern`` columns appended
to that pool by the caller.
"""

from __future__ import annotations

import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from cand_c_column_generation_phase1_20260521.column_grammar import (  # type: ignore
    CellCoord,
    Pattern,
    RegionBBox,
)


# === Env flag helpers ===


def a2_enabled() -> bool:
    """Resolve A2 env flag.  Default OFF — A2 is backup-of-backup."""
    return os.environ.get("EXACT_CANDC_A2_DUAL_GUIDED", "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def max_rounds_per_event() -> int:
    return _env_int("EXACT_CANDC_A2_MAX_ROUNDS", 5)


def hotspot_top_k() -> int:
    return _env_int("EXACT_CANDC_A2_HOTSPOT_TOP_K", 50)


def hotspot_mag_floor() -> float:
    return _env_float("EXACT_CANDC_A2_HOTSPOT_MAG_FLOOR", 1e-6)


def alternatives_per_round() -> int:
    return _env_int("EXACT_CANDC_A2_ALTS_PER_ROUND", 10)


# === Farkas certificate extraction (HiGHS mirror) ===


@dataclass
class FarkasCertificate:
    """Outcome of Farkas extraction on an INFEASIBLE RMP snapshot.

    Fields:
        success: True iff a non-trivial dual ray was extracted.
        backend: which LP backend produced the ray ('highspy' or 'unavailable').
        cell_ray_coeffs: ray coefficient per cell row, mapping
            CellCoord -> float.  Sign convention: ``y_i > 0`` means the
            row's upper bound (cell cap = 1) participates in the proof
            of infeasibility, i.e. the cell is over-demanded.
        instance_ray_coeffs: ray coefficient per instance coverage row.
            (Kept for telemetry; A2 hotspot detection focuses on cells.)
        ray_norm_inf: max |y_i| across all rows.  If 0 the ray is trivial
            (HiGHS returned a degenerate ray); A2 treats this as a soft
            failure.
        n_rows_in_ray: number of constraint rows with |y_i| ≥ mag floor.
        farkas_b_dot_y: yᵀb actually computed back from the LP RHS.  A
            valid Farkas ray must have this > 0; we record it for the
            log so it's verifiable in postmortem.
        error: human-readable diagnostic if success=False.
    """

    success: bool = False
    backend: str = "unavailable"
    cell_ray_coeffs: Dict[CellCoord, float] = field(default_factory=dict)
    instance_ray_coeffs: Dict[str, float] = field(default_factory=dict)
    ray_norm_inf: float = 0.0
    n_rows_in_ray: int = 0
    farkas_b_dot_y: float = 0.0
    error: str = ""


def extract_farkas_certificate(
    columns: Sequence[Pattern],
    instance_ids: Sequence[str],
    *,
    set_covering: bool = True,
) -> FarkasCertificate:
    """Mirror the RMP LP in HiGHS and extract a Farkas certificate.

    Why HiGHS instead of GLOP: ortools `pywraplp` does not expose the
    dual ray on INFEASIBLE.  Verified empirically — ``dual_value()``
    returns 0.0, and the underlying protobuf MPSolutionResponse has no
    ray field.  HiGHS via highspy exposes ``getDualRay()`` provided
    ``presolve`` is OFF (otherwise HiGHS detects infeasibility in
    presolve and skips the simplex that would produce the ray).

    RMP shape mirrored exactly:
        min sum_k cost_k * λ_k
            subject to (per instance iid):
              if set_covering:  Σ_k [iid ∈ k] λ_k ≥ 1     (lower-bounded)
              else:             Σ_k [iid ∈ k] λ_k == 1   (equality)
            per cell (x,y):   Σ_k [(x,y) ∈ k] λ_k ≤ 1    (upper-bounded)
            0 ≤ λ_k ≤ 1

    The Farkas certificate then has one component per LP row.  We
    bucket them into:
      * instance rows  → instance_ray_coeffs[iid]
      * cell rows      → cell_ray_coeffs[(x,y)]

    Sign convention from HiGHS: y_i is such that for a row
    ``rl ≤ aᵀ x ≤ ru``, the contribution to yᵀb is
        max(y_i * rl, y_i * ru)    if y_i has a definite sign,
    HiGHS returns y in its convention; we record the raw values and
    derive hotspots from absolute magnitude.

    The fallback ``backend='unavailable'`` is returned if ``highspy``
    cannot be imported.  Caller should treat that as A2 not applicable
    and proceed.
    """
    cert = FarkasCertificate()

    # Reject empty pools — Farkas certificate not meaningful.
    if not columns:
        cert.error = "empty column pool"
        return cert

    try:
        import highspy
        import numpy as np
    except ImportError as e:
        cert.error = f"highspy unavailable: {e}"
        return cert

    inf = highspy.kHighsInf

    # Build LP in row-wise form first, then convert to CSC at the end.
    # Row ordering: [instance rows for iid in instance_ids] ++
    #               [cell rows for cell in all_cells, sorted lexicographically].
    instance_ids_list = list(instance_ids)
    iid_to_row: Dict[str, int] = {iid: i for i, iid in enumerate(instance_ids_list)}
    n_inst_rows = len(instance_ids_list)

    all_cells: Set[CellCoord] = set()
    for col in columns:
        all_cells.update(col.occupied_cells)
    cells_sorted = sorted(all_cells)
    cell_to_row: Dict[CellCoord, int] = {c: n_inst_rows + i for i, c in enumerate(cells_sorted)}
    n_cell_rows = len(cells_sorted)

    n_rows = n_inst_rows + n_cell_rows
    n_cols = len(columns)

    row_lower = [-inf] * n_rows
    row_upper = [inf] * n_rows
    for iid in instance_ids_list:
        r = iid_to_row[iid]
        row_lower[r] = 1.0
        row_upper[r] = inf if set_covering else 1.0
    for cell in cells_sorted:
        r = cell_to_row[cell]
        row_upper[r] = 1.0
        # row_lower stays -inf (no demand floor on cells)

    col_cost = [float(col.cost) for col in columns]
    col_lower = [0.0] * n_cols
    col_upper = [1.0] * n_cols

    # Build CSC arrays.  For each column k, list its row indices and
    # coefficients (all coefficients == 1.0 in RMP).
    a_start: List[int] = [0]
    a_index: List[int] = []
    a_value: List[float] = []
    for k, pat in enumerate(columns):
        # Instance rows for this column.
        col_rows: List[int] = []
        for iid in pat.covered_instance_ids:
            r = iid_to_row.get(iid)
            if r is not None:
                col_rows.append(r)
        for cell in pat.occupied_cells:
            r = cell_to_row.get(cell)
            if r is not None:
                col_rows.append(r)
        # Dedupe (a column should never list the same row twice but be safe).
        col_rows = sorted(set(col_rows))
        for r in col_rows:
            a_index.append(r)
            a_value.append(1.0)
        a_start.append(len(a_index))

    h = highspy.Highs()
    h.silent()
    h.setOptionValue("presolve", "off")    # critical: keep simplex active
    h.setOptionValue("solver", "simplex")  # ipm cannot produce dual ray

    lp = highspy.HighsLp()
    lp.num_col_ = n_cols
    lp.num_row_ = n_rows
    lp.col_cost_ = col_cost
    lp.col_lower_ = col_lower
    lp.col_upper_ = col_upper
    lp.row_lower_ = row_lower
    lp.row_upper_ = row_upper
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = a_start
    lp.a_matrix_.index_ = a_index
    lp.a_matrix_.value_ = a_value
    lp.sense_ = highspy.ObjSense.kMinimize

    h.passModel(lp)
    run_status = h.run()
    model_status = h.getModelStatus()

    if model_status != highspy.HighsModelStatus.kInfeasible:
        # HiGHS thinks the LP is feasible (or hit some other status).
        # That can happen if A3 set-covering rescued it under HiGHS but
        # GLOP earlier reported INFEASIBLE — numerical noise.  Either
        # way A2 has nothing to do.
        cert.error = (
            f"highs model status {model_status} != Infeasible "
            f"(run_status={run_status}) — nothing to certify"
        )
        cert.backend = "highspy"
        return cert

    exist_status, exists = h.getDualRayExist()
    if not exists:
        cert.error = (
            f"highs reports no dual ray available "
            f"(exist_status={exist_status}); presolve likely killed it"
        )
        cert.backend = "highspy"
        return cert

    ray_status, ray_ok, ray = h.getDualRay()
    if not ray_ok or ray is None:
        cert.error = f"getDualRay failed (status={ray_status}, ok={ray_ok})"
        cert.backend = "highspy"
        return cert

    y = np.asarray(ray, dtype=float)
    if y.shape[0] != n_rows:
        cert.error = (
            f"ray length {y.shape[0]} != expected n_rows {n_rows}"
        )
        cert.backend = "highspy"
        return cert

    # Bucket by row family.
    for iid, r in iid_to_row.items():
        cert.instance_ray_coeffs[iid] = float(y[r])
    for cell, r in cell_to_row.items():
        cert.cell_ray_coeffs[cell] = float(y[r])

    cert.ray_norm_inf = float(np.max(np.abs(y))) if y.size else 0.0

    floor = hotspot_mag_floor()
    cert.n_rows_in_ray = int(np.sum(np.abs(y) >= floor))

    # Compute yᵀb for postmortem.  For mixed bounded rows we pick the
    # side that yields a positive contribution (the proper Farkas
    # interpretation: y_i > 0 picks the lower bound, y_i < 0 picks the
    # upper bound).  This matches how HiGHS uses the certificate.
    b_dot_y = 0.0
    for r in range(n_rows):
        yi = float(y[r])
        if yi == 0.0:
            continue
        rl = row_lower[r]
        ru = row_upper[r]
        if yi > 0.0:
            if not math.isinf(rl):
                b_dot_y += yi * rl
        else:
            if not math.isinf(ru):
                b_dot_y += yi * ru
    cert.farkas_b_dot_y = b_dot_y

    cert.backend = "highspy"
    cert.success = cert.ray_norm_inf > 0.0
    if not cert.success:
        cert.error = "degenerate ray (norm_inf=0)"
    return cert


# === Hotspot extraction ===


def extract_hotspot_cells(
    cert: FarkasCertificate,
    *,
    top_k: Optional[int] = None,
    mag_floor: Optional[float] = None,
) -> List[Tuple[CellCoord, float]]:
    """Pick the top-K cells from the certificate sorted by ``|y_cell|``.

    Returns descending list of (cell, ray_coeff).  Filters out cells
    with ``|coeff| < mag_floor``.  If no cell makes the cut, returns
    empty list (A2 then degrades to noop for this round).
    """
    if not cert.success:
        return []
    k_cap = top_k if top_k is not None else hotspot_top_k()
    floor = mag_floor if mag_floor is not None else hotspot_mag_floor()
    ranked = [
        (cell, coeff)
        for cell, coeff in cert.cell_ray_coeffs.items()
        if abs(coeff) >= floor
    ]
    ranked.sort(key=lambda kv: -abs(kv[1]))
    return ranked[:k_cap]


# === A2 round runner ===


@dataclass
class A2RoundLog:
    """Aggregate telemetry across all A2 rounds attached to one INFEASIBLE event.

    Fields mirror the A1 RoundLog so the probe can serialize both the
    same way.
    """

    triggered: bool = False
    rounds_run: int = 0
    alternatives_total: int = 0
    wall_seconds_total: float = 0.0
    final_lp_status: str = "n/a"
    farkas_backend: str = "unavailable"
    farkas_attempts: int = 0
    farkas_successes: int = 0
    last_ray_norm_inf: float = 0.0
    last_n_hotspots: int = 0
    rounds: List[Dict[str, Any]] = field(default_factory=list)
    exit_reason: str = "not_triggered"


def run_a2_rounds(
    columns: List[Pattern],
    instance_ids: Sequence[str],
    instances: Sequence[Dict[str, Any]],
    pools: Mapping[str, Sequence[Any]],
    rmp_solver: Any,  # callable: (columns, instance_ids) -> Phase2RMPResult
    *,
    grid_w: int = 70,
    grid_h: int = 70,
    region_size: int = 12,
    stride: int = 6,
    set_covering: bool = True,
    log: Optional[Any] = None,
) -> A2RoundLog:
    """Drive up to N rounds of (Farkas extract -> alternatives -> resolve).

    Mutates ``columns`` in place — newly generated alternatives are
    appended.  Caller is responsible for re-running RMP / the main CG
    loop after this returns (the last RMP solve done inside is the
    one in ``a2_log.final_lp_status``).

    The driver short-circuits on:
      * Farkas certificate extraction fails (backend unavailable, no
        ray, degenerate ray) → exit_reason='farkas_failed'.
      * No new hotspots remaining → exit_reason='no_hotspots'.
      * Alternatives generated but RMP resolves still INFEASIBLE for
        ``MAX_ROUNDS`` rounds → exit_reason='still_infeasible'.
      * RMP resolves to OPTIMAL/FEASIBLE → exit_reason='restored'.

    All ``log`` arg formatting matches the A1 pattern from
    ``alternative_blueprint_generator.run_a1_rounds`` for consistency.
    """
    from cand_c_column_generation_phase2_20260521.alternative_blueprint_generator import (  # type: ignore
        generate_alternative_columns,
    )

    a2_log = A2RoundLog(triggered=True)
    cumulative_excludes: Set[CellCoord] = set()

    n_max_rounds = max_rounds_per_event()
    alts_cap = alternatives_per_round()

    for r in range(n_max_rounds):
        t_round = time.perf_counter()
        # Extract Farkas certificate against the *current* pool.
        a2_log.farkas_attempts += 1
        cert = extract_farkas_certificate(
            columns, instance_ids, set_covering=set_covering,
        )
        a2_log.farkas_backend = cert.backend
        if not cert.success:
            if log is not None:
                log(f"[A2] round {r}: Farkas extract failed — {cert.error}")
            a2_log.exit_reason = "farkas_failed"
            break
        a2_log.farkas_successes += 1
        a2_log.last_ray_norm_inf = cert.ray_norm_inf
        hotspots = extract_hotspot_cells(cert)
        a2_log.last_n_hotspots = len(hotspots)
        if not hotspots:
            if log is not None:
                log(
                    f"[A2] round {r}: no hotspot cells "
                    f"(ray_norm_inf={cert.ray_norm_inf:.3e}, "
                    f"n_rows_in_ray={cert.n_rows_in_ray})"
                )
            a2_log.exit_reason = "no_hotspots"
            break

        # Build exclusion set: this round's hotspots ∪ cumulative.
        round_excludes = {c for c, _coeff in hotspots}
        new_excludes = round_excludes | cumulative_excludes
        if new_excludes == cumulative_excludes:
            if log is not None:
                log(f"[A2] round {r}: no new hotspot cells added; abort")
            a2_log.exit_reason = "stalled_hotspots"
            break
        cumulative_excludes = new_excludes

        # Generate alternative blueprints avoiding hotspots.
        gen_res = generate_alternative_columns(
            instances, pools, cumulative_excludes,
            grid_w=grid_w, grid_h=grid_h,
            region_size=region_size, stride=stride,
            max_alternatives=alts_cap,
            rng_seed=0xA22026 + 1000 * r,
        )
        if not gen_res.columns:
            if log is not None:
                log(
                    f"[A2] round {r}: no feasible alternatives "
                    f"(regions_attempted={gen_res.n_regions_attempted}, "
                    f"hotspots={len(hotspots)})"
                )
            a2_log.exit_reason = "no_alternatives"
            break

        existing_ids = {c.column_id for c in columns}
        fresh = [c for c in gen_res.columns if c.column_id not in existing_ids]
        if not fresh:
            if log is not None:
                log(f"[A2] round {r}: all alternatives duplicates of existing pool")
            a2_log.exit_reason = "all_duplicates"
            break

        before = len(columns)
        columns.extend(fresh)
        a2_log.alternatives_total += len(fresh)

        # Re-solve RMP.
        rmp_res = rmp_solver(columns, instance_ids)
        round_wall = time.perf_counter() - t_round
        a2_log.wall_seconds_total += round_wall
        a2_log.final_lp_status = rmp_res.status_str
        a2_log.rounds.append({
            "round": r,
            "n_hotspots": len(hotspots),
            "ray_norm_inf": cert.ray_norm_inf,
            "farkas_b_dot_y": cert.farkas_b_dot_y,
            "n_alts_added": len(fresh),
            "pool_size_after": len(columns),
            "rmp_status_after": rmp_res.status_str,
            "round_wall_s": round_wall,
        })
        a2_log.rounds_run += 1
        if log is not None:
            log(
                f"[A2] round {r}: +{len(fresh)} alts ({before}->{len(columns)} cols, "
                f"hotspots={len(hotspots)}, ray_norm_inf={cert.ray_norm_inf:.3e}, "
                f"rmp_after={rmp_res.status_str}, wall={round_wall:.2f}s)"
            )
        if rmp_res.status_str in ("OPTIMAL", "FEASIBLE"):
            a2_log.exit_reason = "restored"
            break
    else:
        # Loop did all rounds without restoring.
        a2_log.exit_reason = "still_infeasible"

    return a2_log
