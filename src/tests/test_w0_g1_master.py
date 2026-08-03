"""W0 G1 stage B: the exact-cover master.

research-only.  Nothing here produces or consumes a bound.

Blueprint tests 18-22.  The instances are synthetic on purpose: a master whose
answers can only be checked by another solver is not checked at all, so every
case here is small enough to work out by hand and the expected answer is written
down, not derived from a second run.

The synthetic vocabulary is deliberately *not* the frozen one -- ``build_master``
and ``solve_master`` take ``demand`` and ``bucket_servable`` as parameters, so
these tests exercise the model without depending on the nine real classes.  The
real class table has its own red-line test in
``test_w0_g1_port_semantics.py``.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Dict, FrozenSet, Mapping, Sequence, Tuple

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from g1_exact_cover_master import (  # noqa: E402
    COLLAPSE_EQUIVALENCE,
    class_supply_pre_gate,
    SCALE_MAX_VARIABLES,
    MasterConfig,
    PatternRecord,
    RegionClassColumns,
    build_master,
    solve_master,
)

pytestmark = pytest.mark.evidence

#: Two synthetic capability buckets.  ``B1`` is the narrow one, ``B2`` can also
#: take the second class -- the same downward-closed shape the real buckets have.
SYNTHETIC_BUCKETS: Dict[str, FrozenSet[str]] = {
    "B1": frozenset({"K1"}),
    "B2": frozenset({"K1", "K2"}),
}

#: A second vocabulary where the two buckets share nothing.  Used where the point
#: is that a class has exactly one supplier, so an unreachable count can only be
#: blamed on that class -- with the overlapping vocabulary the master can always
#: shuffle a body from ``B2`` into ``K1`` and the accusation loses its edge.
DISJOINT_BUCKETS: Dict[str, FrozenSet[str]] = {
    "B1": frozenset({"K1"}),
    "B2": frozenset({"K2"}),
}


def _record(
    region_class: str,
    tag: str,
    buckets: Mapping[str, int],
    *,
    hole: bool = False,
    area: int = 0,
) -> PatternRecord:
    return PatternRecord(
        region_class=region_class,
        pattern_id=tag,
        bucket_counts=dict(buckets),
        hole=hole,
        body_count=sum(buckets.values()),
        origin="synthetic",
        body_area=area,
    )


def _columns(
    region_class: str,
    multiplicity: int,
    records: Sequence[PatternRecord],
) -> RegionClassColumns:
    regions: Tuple[Tuple[int, int], ...] = tuple(
        (0, index) for index in range(multiplicity)
    )
    return RegionClassColumns(
        region_class=region_class,
        multiplicity=multiplicity,
        regions=regions,
        complete=True,
        catalog_sha256=None,
        patterns=tuple(records),
    )


def _three_region_catalog() -> Dict[str, RegionClassColumns]:
    """Three regions across two classes, four patterns, one hole-carrying each.

    Region class ``A`` holds two regions and offers a two-body no-hole pattern or
    a two-body hole pattern; class ``B`` holds one region and offers the same
    shape with a single body.  Five bodies in total whatever is chosen.
    """
    return {
        "A": _columns(
            "A",
            2,
            [
                _record("A", "a1", {"B1": 2}),
                _record("A", "a2", {"B2": 2}, hole=True),
            ],
        ),
        "B": _columns(
            "B",
            1,
            [
                _record("B", "b1", {"B1": 1}),
                _record("B", "b2", {"B2": 1}, hole=True),
            ],
        ),
    }


# --------------------------------------------------------------------------
# 18
# --------------------------------------------------------------------------


def test_synthetic_catalog_has_exactly_the_hand_computed_solution() -> None:
    """[18] Five bodies, one hole, demand (K1, K2) = (3, 2): one selection works.

    By hand.  Let ``a2`` and ``b2`` be how many hole patterns each class takes;
    exactly one hole means ``a2 + b2 == 1``.

    * ``a2 = 0, b2 = 1``  -> B1 supply 4, and B1 only serves K1, so K1 >= 4 > 3.
    * ``a2 = 2``          -> two holes.
    * ``a2 = 1, b2 = 0``  -> B1 supply 3, B2 supply 2; B1 forces K1 = 3 exactly and
      the two B2 bodies must both go to K2.  That is the answer.
    """
    columns = _three_region_catalog()
    result = solve_master(
        columns,
        MasterConfig(max_time_in_seconds=30.0, workers=2),
        demand={"K1": 3, "K2": 2},
        bucket_servable=SYNTHETIC_BUCKETS,
    )
    assert result["status"] in {"OPTIMAL", "FEASIBLE"}, result
    taken = sorted(row["pattern_id"] for row in result["selection"])
    assert taken == ["a1", "a2", "b1"]
    assignment = {
        (row["bucket"], row["class"]): row["count"] for row in result["class_assignment"]
    }
    assert assignment == {("B1", "K1"): 3, ("B2", "K2"): 2}
    assert len(result["selection"]) == 3


# --------------------------------------------------------------------------
# 19
# --------------------------------------------------------------------------


def _parity_catalog() -> Dict[str, RegionClassColumns]:
    """Two regions, two patterns, bodies only ever arrive in pairs.

    With ``DISJOINT_BUCKETS`` each class has exactly one supplier and that
    supplier delivers two bodies at a time, so any odd demand is unreachable --
    a shortage with a single, nameable cause.
    """
    return {
        "R": _columns(
            "R",
            2,
            [
                _record("R", "p1", {"B1": 2}),
                _record("R", "p2", {"B2": 2}),
            ],
        )
    }


def test_a_class_demand_no_supply_can_reach_is_named_by_the_core() -> None:
    """[19] Bump one class's demand by one and the instance turns infeasible; the
    deletion core points at that class alone, not at the whole model."""
    columns = _parity_catalog()
    config = MasterConfig(max_time_in_seconds=30.0, workers=2, hole_count=0)

    feasible = solve_master(
        columns,
        config,
        demand={"K1": 2, "K2": 2},
        bucket_servable=DISJOINT_BUCKETS,
    )
    assert feasible["status"] in {"OPTIMAL", "FEASIBLE"}, feasible

    infeasible = solve_master(
        columns,
        config,
        demand={"K1": 3, "K2": 1},
        bucket_servable=DISJOINT_BUCKETS,
    )
    assert infeasible["status"] == "INFEASIBLE"
    assert infeasible["infeasibility_core"] == ["assume_class[K2]"], infeasible
    assert infeasible["infeasibility_core_detail"]["proved_minimal"] is True


def test_the_core_is_a_real_minimal_infeasible_subset() -> None:
    """[19b] The definition, executed.

    A deletion core is the set of families that *survived*: keeping only those is
    already infeasible, and letting go of any single one of them makes the
    instance satisfiable.  Both halves are checked, so a core that merely looked
    plausible cannot pass.
    """
    from ortools.sat.python import cp_model

    columns = _parity_catalog()
    config = MasterConfig(max_time_in_seconds=30.0, workers=2, hole_count=0)
    demand = {"K1": 3, "K2": 1}
    result = solve_master(
        columns, config, demand=demand, bucket_servable=DISJOINT_BUCKETS
    )
    core = list(result["infeasibility_core"])
    every = build_master(
        columns, config, demand=demand, bucket_servable=DISJOINT_BUCKETS
    ).families
    outside = [name for name in every if name not in set(core)]

    def status(dropped: Sequence[str]) -> object:
        built = build_master(
            columns,
            config,
            demand=demand,
            bucket_servable=DISJOINT_BUCKETS,
            dropped=dropped,
        )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_workers = 2
        return solver.solve(built.model)

    assert status(outside) == cp_model.INFEASIBLE
    for family in core:
        assert status(list(outside) + [family]) in (
            cp_model.OPTIMAL,
            cp_model.FEASIBLE,
        ), family


# --------------------------------------------------------------------------
# 20
# --------------------------------------------------------------------------


def test_exactly_one_hole_rejects_both_two_holes_and_none() -> None:
    """[20] C3 is an equality, in both directions."""
    config = MasterConfig(max_time_in_seconds=30.0, workers=2)

    only_holes = {
        "R": _columns(
            "R",
            2,
            [_record("R", "h1", {"B1": 1}, hole=True)],
        )
    }
    forced_two = solve_master(
        only_holes,
        config,
        demand={"K1": 2},
        bucket_servable=SYNTHETIC_BUCKETS,
    )
    assert forced_two["status"] == "INFEASIBLE"
    assert "assume_hole" in forced_two["infeasibility_core"], forced_two

    no_holes = {
        "R": _columns("R", 2, [_record("R", "n1", {"B1": 1})]),
    }
    forced_zero = solve_master(
        no_holes,
        config,
        demand={"K1": 2},
        bucket_servable=SYNTHETIC_BUCKETS,
    )
    assert forced_zero["status"] == "INFEASIBLE"
    assert "assume_hole" in forced_zero["infeasibility_core"], forced_zero


# --------------------------------------------------------------------------
# 21
# --------------------------------------------------------------------------


def test_collapsed_and_per_region_forms_agree(
) -> None:
    """[21, T-ARCHETYPE-COLLAPSE] The counting form and the boolean form decide
    the same instances, on a feasible case and an infeasible one alike."""
    assert COLLAPSE_EQUIVALENCE is True
    cases = (
        (_three_region_catalog(), SYNTHETIC_BUCKETS, {"K1": 3, "K2": 2}, 1, True),
        (_three_region_catalog(), SYNTHETIC_BUCKETS, {"K1": 5, "K2": 1}, 1, False),
        (_parity_catalog(), DISJOINT_BUCKETS, {"K1": 2, "K2": 2}, 0, True),
        (_parity_catalog(), DISJOINT_BUCKETS, {"K1": 3, "K2": 1}, 0, False),
    )
    for columns, buckets, demand, holes, expected in cases:
        answers = []
        for collapse in (True, False):
            result = solve_master(
                columns,
                MasterConfig(
                    collapse=collapse,
                    max_time_in_seconds=30.0,
                    workers=2,
                    hole_count=holes,
                ),
                demand=demand,
                bucket_servable=buckets,
            )
            assert result["status"] in {"OPTIMAL", "FEASIBLE", "INFEASIBLE"}, result
            answers.append(result["status"] != "INFEASIBLE")
            if result["status"] != "INFEASIBLE":
                # Both forms must hand back one pattern per region either way.
                assert len(result["selection"]) == sum(
                    block.multiplicity for block in columns.values()
                )
        assert answers[0] == answers[1] == expected, (demand, answers)


# --------------------------------------------------------------------------
# 22
# --------------------------------------------------------------------------


def test_scale_gate_stops_before_the_solver(monkeypatch: pytest.MonkeyPatch) -> None:
    """[22] An oversized model is reported, not solved.

    The gate is checked against the built proto, so the test builds a catalog
    that really does exceed the variable budget rather than faking the count.
    ``solve`` is monkeypatched to explode: if the gate ever lets an oversized
    model through, this test fails loudly instead of quietly taking 30 minutes.
    """
    from ortools.sat.python import cp_model

    def _explode(self: object, *args: object, **kwargs: object) -> None:
        raise AssertionError("the scale gate let an oversized model reach the solver")

    monkeypatch.setattr(cp_model.CpSolver, "solve", _explode)

    oversized = {
        "R": _columns(
            "R",
            2,
            [
                _record("R", f"p{index:05d}", {"B1": 1})
                for index in range(SCALE_MAX_VARIABLES + 10)
            ],
        )
    }
    result = solve_master(
        oversized,
        MasterConfig(max_time_in_seconds=30.0, workers=2, hole_count=0),
        demand={"K1": 2},
        bucket_servable=SYNTHETIC_BUCKETS,
    )
    assert result["status"] == "SCALE_ABORT"
    assert result["scale"]["num_variables"] > SCALE_MAX_VARIABLES
    assert result["stats"]["solved"] is False
    assert result["selection"] == []


def test_the_supply_pre_gate_reports_area_and_the_hole_penalty() -> None:
    """[24, T-SUPPLY-CEILING] The area rows, on a catalog with hand-set areas.

    The plain area ceiling takes each region class's densest pattern; the
    hole-aware one subtracts the cheapest price any region would pay for carrying
    the 42 body-free cells, because exactly one of them must.  Both directions are
    checked -- a class with no hole-carrying pattern must not contribute a penalty
    of zero and quietly disable the sharper row.
    """
    columns = {
        "A": _columns(
            "A",
            2,
            [
                _record("A", "a1", {"B1": 2}, area=50),
                _record("A", "a2", {"B1": 2}, hole=True, area=30),
            ],
        ),
        "B": _columns(
            "B",
            1,
            [_record("B", "b1", {"B1": 1}, area=40)],
        ),
    }
    report = class_supply_pre_gate(
        columns, demand={"K1": 5}, bucket_servable=SYNTHETIC_BUCKETS
    )
    rows = {entry["class"]: entry for entry in report["classes"]}
    # A contributes 50 twice, B contributes 40 once.
    assert rows["__body_area__"]["supply_ceiling"] == 140
    # Only A can carry the hole, and it costs 50 - 30 = 20.
    assert rows["__body_area_with_hole__"]["supply_ceiling"] == 120
    assert rows["__total_bodies__"]["supply_ceiling"] == 5


def test_the_target_menu_can_be_aimed_at_dense_targets() -> None:
    """[23, H-TARGET-MENU] ``min_bodies`` filters without touching the ordering.

    219 bodies over the 24 usable regions is 9.125 each, so a catalog whose
    densest pattern holds nine is short by arithmetic -- and the targets that
    would fix that sit hundreds of ranks out under the proportional-share
    ordering.  The filter is what lets a second generation pass aim there; it must
    remove targets and nothing else, so the filtered menu has to stay an exact
    order-preserving subsequence of the unfiltered one.
    """
    from g1_pattern_generator import build_target_menu
    from g1_region_model import REGION_CLASSES

    region = REGION_CLASSES["CLEAN"]
    everything = build_target_menu(region)
    dense = build_target_menu(region, min_bodies=10)
    assert dense, "CLEAN must admit targets of ten bodies or more"
    assert len(dense) < len(everything)
    assert all(target.body_total >= 10 for target in dense)
    expected = tuple(target for target in everything if target.body_total >= 10)
    assert dense == expected
    assert build_target_menu(region, min_bodies=1) == everything


def test_the_scale_gate_is_not_tripped_by_the_designed_envelope() -> None:
    """[22b] A thousand-column catalog -- the design point -- stays under the gate."""
    sized = {
        "R": _columns(
            "R",
            16,
            [_record("R", f"p{index:04d}", {"B1": 1}) for index in range(900)],
        )
    }
    built = build_master(
        sized,
        MasterConfig(hole_count=0),
        demand={"K1": 16},
        bucket_servable=SYNTHETIC_BUCKETS,
    )
    assert built.scale["num_variables"] < SCALE_MAX_VARIABLES
    assert built.scale["num_constraints"] < 200
