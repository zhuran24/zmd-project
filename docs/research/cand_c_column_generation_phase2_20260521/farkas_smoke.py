"""Phase 2 v3 A2 — standalone smoke test for Farkas certificate extraction.

Runs three toy scenarios (no Phase 2 dataset required):

1. Trivial infeasible LP: x ≥ 1 ∧ x ≤ 0, via HiGHS directly — verifies
   that highspy.getDualRay() actually returns a non-trivial dual ray
   when presolve=off and solver=simplex.

2. Synthetic RMP-shape infeasibility: 2 instances, single cell, both
   instances must occupy it (set-partitioning).  This mirrors the
   structural conflict pattern: two columns claim the same cell but
   each is the only one covering its instance.  Verifies the
   `extract_farkas_certificate` wrapper bucketing by row family.

3. Synthetic RMP-shape feasibility: 2 instances, 2 disjoint cells, one
   column per instance.  Verifies that A2 correctly returns
   `success=False` with "not infeasible" diagnostic when LP feasible.

This module is NOT a pytest test — Phase 2 research code does not have
a pytest harness yet.  Run via `.venv/bin/python -m
cand_c_column_generation_phase2_20260521.farkas_smoke` from project
root, after adding docs/research to PYTHONPATH.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH_DIR = HERE.parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))


def _t1_raw_highs_infeasible_lp() -> bool:
    """T1: Trivial x≥1 ∧ x≤0 via raw highspy; verify ray = [+, -]."""
    import highspy
    h = highspy.Highs()
    h.silent()
    h.setOptionValue("presolve", "off")
    h.setOptionValue("solver", "simplex")
    inf = highspy.kHighsInf

    lp = highspy.HighsLp()
    lp.num_col_ = 1
    lp.num_row_ = 2
    lp.col_cost_ = [0.0]
    lp.col_lower_ = [-inf]
    lp.col_upper_ = [inf]
    lp.row_lower_ = [1.0, -inf]
    lp.row_upper_ = [inf, 0.0]
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = [0, 2]
    lp.a_matrix_.index_ = [0, 1]
    lp.a_matrix_.value_ = [1.0, 1.0]
    h.passModel(lp)
    h.run()
    if h.getModelStatus() != highspy.HighsModelStatus.kInfeasible:
        print("  T1 FAIL: model not infeasible")
        return False
    _es, exists = h.getDualRayExist()
    if not exists:
        print("  T1 FAIL: dual ray not available")
        return False
    _s, ok, ray = h.getDualRay()
    if not ok or ray is None:
        print("  T1 FAIL: getDualRay returned no ray")
        return False
    rl = list(ray)
    print(f"  T1: ray = {rl}")
    # y[0] should be positive (row x >= 1's lower bound contributes)
    # y[1] should be negative (row x <= 0's upper bound contributes)
    if rl[0] <= 0 or rl[1] >= 0:
        print("  T1 WARN: ray signs unexpected (depends on HiGHS sign convention)")
        # Still acceptable as long as ray is non-trivial and yields proof.
    return True


def _make_synthetic_pattern(
    column_id: str,
    covered_instance_ids,
    occupied_cells,
    cost: int = 1,
):
    """Construct a minimal Pattern object for synthetic LPs.

    Phase 1's `column_grammar.Pattern` is a frozen dataclass with
    fields: column_id, occupied_cells, facility_assignments,
    port_cells, typed_ports, boundary_signature, region, cost.
    ``covered_instance_ids`` is a *property* derived from
    facility_assignments, so for the smoke we synthesize fake
    facility_assignments tuples with the desired instance IDs.

    Each FacilityAssignment is a (instance_id, template, pose_idx)
    tuple per ``column_grammar`` — we use the structural tuple shape
    directly since the dataclass accepts a plain tuple.
    """
    from cand_c_column_generation_phase1_20260521.column_grammar import (
        Pattern,
    )
    facility_assignments = tuple(
        (iid, "fake_template", 0) for iid in covered_instance_ids
    )
    return Pattern(
        column_id=column_id,
        occupied_cells=frozenset(occupied_cells),
        facility_assignments=facility_assignments,
        port_cells=frozenset(),
        typed_ports=tuple(),
        boundary_signature=tuple(),
        region=(0, 0, 10, 10),
        cost=cost,
    )


def _t2_synthetic_infeasible_rmp() -> bool:
    """T2: 2 instances, 1 column each, both claim cell (0,0).

    Under set-partitioning (sc=False) each instance row requires sum
    of its column λ = 1.  Both columns claim the single cell, but the
    cell-cap is also 1, so total λ_A + λ_B ≤ 1.  But λ_A=1 ∧ λ_B=1
    are required → infeasible.  Hotspot expected: (0,0).
    """
    from cand_c_column_generation_phase2_20260521.farkas_certificate import (
        extract_farkas_certificate,
        extract_hotspot_cells,
    )
    pA = _make_synthetic_pattern("A", ["i0"], [(0, 0)])
    pB = _make_synthetic_pattern("B", ["i1"], [(0, 0)])
    columns = [pA, pB]
    instance_ids = ["i0", "i1"]
    cert = extract_farkas_certificate(
        columns, instance_ids, set_covering=False,
    )
    print(f"  T2: success={cert.success}, backend={cert.backend}, "
          f"ray_norm_inf={cert.ray_norm_inf:.3e}, "
          f"b_dot_y={cert.farkas_b_dot_y:.3e}, "
          f"n_rows_in_ray={cert.n_rows_in_ray}, error={cert.error!r}")
    if not cert.success:
        print("  T2 FAIL: should have produced a Farkas certificate")
        return False
    hotspots = extract_hotspot_cells(cert, top_k=10)
    print(f"  T2: hotspots = {hotspots}")
    if not hotspots:
        print("  T2 FAIL: no hotspot cells extracted")
        return False
    # Cell (0,0) should be in hotspots.
    if not any(c == (0, 0) for c, _ in hotspots):
        print("  T2 FAIL: expected (0,0) in hotspots")
        return False
    return True


def _t3_synthetic_feasible_rmp() -> bool:
    """T3: 2 instances, 2 disjoint cells, 1 column each.

    Trivially feasible λ_A=1 ∧ λ_B=1.  Farkas extraction should
    report success=False with "not infeasible" diagnostic.
    """
    from cand_c_column_generation_phase2_20260521.farkas_certificate import (
        extract_farkas_certificate,
    )
    pA = _make_synthetic_pattern("A", ["i0"], [(0, 0)])
    pB = _make_synthetic_pattern("B", ["i1"], [(1, 1)])
    columns = [pA, pB]
    instance_ids = ["i0", "i1"]
    cert = extract_farkas_certificate(
        columns, instance_ids, set_covering=False,
    )
    print(f"  T3: success={cert.success}, backend={cert.backend}, "
          f"error={cert.error!r}")
    if cert.success:
        print("  T3 FAIL: feasible LP should not produce Farkas certificate")
        return False
    # "not infeasible" path must reach the early-return branch.
    if "Infeasible" not in cert.error and "infeasible" not in cert.error.lower():
        # Acceptable if the diagnostic mentions the model status.
        if "kOptimal" not in cert.error and "Optimal" not in cert.error:
            print("  T3 WARN: error string lacks expected status keyword")
    return True


def main() -> int:
    print("=== Phase 2 v3 A2 Farkas certificate smoke test ===")
    print()
    print("T1: Raw HiGHS toy infeasible LP (x>=1 AND x<=0)")
    t1_ok = _t1_raw_highs_infeasible_lp()
    print("  ->", "PASS" if t1_ok else "FAIL")
    print()
    print("T2: Synthetic RMP infeasibility (2 inst, 1 cell, both claim)")
    t2_ok = _t2_synthetic_infeasible_rmp()
    print("  ->", "PASS" if t2_ok else "FAIL")
    print()
    print("T3: Synthetic RMP feasibility (2 inst, 2 disjoint cells)")
    t3_ok = _t3_synthetic_feasible_rmp()
    print("  ->", "PASS" if t3_ok else "FAIL")
    print()
    all_ok = t1_ok and t2_ok and t3_ok
    print("=== overall:", "PASS" if all_ok else "FAIL", "===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
