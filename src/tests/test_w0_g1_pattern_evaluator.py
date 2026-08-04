"""W0 G1: the geometry -> capability kernel, including the 07-18 front regression.

research-only.  Two red lines live here: the front cell is the *first* cell
outside the body (never the second), and the catalog loader recomputes rather
than believes a stored signature.
"""

from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import g1_pattern_evaluator as ev  # noqa: E402
import g1_port_semantics as sem  # noqa: E402
from g1_pattern_schema import BodySpec, HoleSpec, PatternSpec, PoleSpec  # noqa: E402
from src.placement.placement_generator import gen_power_pole  # noqa: E402

pytestmark = pytest.mark.evidence


# --------------------------------------------------------------------------
# front semantics
# --------------------------------------------------------------------------


def test_front_is_the_first_cell_outside_the_body() -> None:
    """[11, RED LINE] 07-18 front-offset incident regression.

    A 3x3 at (10,10) occupies x,y in [10,12].  Its top fronts are y = 13 and its
    bottom fronts are y = 9 -- one cell out.  The retired ``front + delta``
    formula would give y = 14 and y = 8; those cells must appear nowhere.
    """
    anchor = (10, 10)
    top = ev.side_front_cells("manufacturing_3x3", 0, anchor, "top")
    bottom = ev.side_front_cells("manufacturing_3x3", 0, anchor, "bottom")
    left = ev.side_front_cells("manufacturing_3x3", 0, anchor, "left")
    right = ev.side_front_cells("manufacturing_3x3", 0, anchor, "right")

    assert top == ((10, 13), (11, 13), (12, 13))
    assert bottom == ((10, 9), (11, 9), (12, 9))
    assert left == ((9, 10), (9, 11), (9, 12))
    assert right == ((13, 10), (13, 11), (13, 12))

    second_top = ev.second_cell_outside("manufacturing_3x3", 0, anchor, "top")
    second_bottom = ev.second_cell_outside("manufacturing_3x3", 0, anchor, "bottom")
    assert second_top == ((10, 14), (11, 14), (12, 14))
    assert second_bottom == ((10, 8), (11, 8), (12, 8))
    assert not set(top) & set(second_top)
    assert not set(bottom) & set(second_bottom)
    assert ev.PORT_FRONT_IDENTITY is True


def test_front_arithmetic_matches_the_repository_generator() -> None:
    """[11b] Same numbers as ``get_edge_ports`` for every side and template."""
    from src.placement.placement_generator import get_edge_ports, get_port_front_cell

    for template, orientation in (
        ("manufacturing_3x3", 0),
        ("manufacturing_5x5", 0),
        ("manufacturing_6x4", 0),
        ("manufacturing_6x4", 1),
    ):
        width, height = ev.template_footprint(template, orientation)
        for side in ("top", "bottom", "left", "right"):
            mine = ev.side_front_cells(template, orientation, (20, 20), side)
            theirs = tuple(
                get_port_front_cell(port)
                for port in get_edge_ports(20, 20, width, height, side)
            )
            assert mine == theirs, (template, orientation, side)


# --------------------------------------------------------------------------
# capability buckets
# --------------------------------------------------------------------------


#: Anchors chosen so every side's front cells stay inside the 14x14 region --
#: ``is_front_usable`` enforces R-FRONT-IN-REGION, so an out-of-region front is
#: counted as blocked and the fixture would otherwise measure the wrong thing.
_CAPABILITY_ANCHORS = {
    ("manufacturing_3x3", 0): (5, 5),
    ("manufacturing_5x5", 0): (4, 4),
    ("manufacturing_6x4", 0): (4, 5),
    ("manufacturing_6x4", 1): (5, 4),
}


def _capability(template: str, orientation: int, free_per_side: dict[str, int]):
    """Evaluate one body with exactly ``free_per_side[side]`` free front cells."""
    anchor = _CAPABILITY_ANCHORS[(template, orientation)]
    all_fronts = {
        side: ev.side_front_cells(template, orientation, anchor, side)
        for side in ev.SIDES
    }
    free: set[tuple[int, int]] = set()
    for side, count in free_per_side.items():
        free.update(all_fronts[side][:count])
    occupied = frozenset(
        cell for cells in all_fronts.values() for cell in cells
    ) - free
    return ev.evaluate_body(
        BodySpec(bid=0, template=template, orientation=orientation, local_anchor=anchor),
        occupied,
        frozenset(free),
    )


BUCKET_CASES = (
    # 3x3: cap = best max(n_X, n_Y) over pairs whose two sides are both non-empty
    ("manufacturing_3x3", 0, {"top": 1, "bottom": 1}, "M3_1i1o"),
    ("manufacturing_3x3", 0, {"top": 2, "bottom": 1}, "M3_1i2o+2i1o"),
    ("manufacturing_3x3", 0, {"top": 1, "bottom": 3}, "M3_1i3o+2i1o"),
    ("manufacturing_3x3", 0, {"left": 3, "right": 3}, "M3_1i3o+2i1o"),
    ("manufacturing_5x5", 0, {"top": 1, "bottom": 1}, "M5_1i1o"),
    ("manufacturing_5x5", 0, {"left": 1, "right": 4}, "M5_1i2o"),
    ("manufacturing_6x4", 0, {"top": 3, "bottom": 1}, "M6_3i1o"),
    ("manufacturing_6x4", 0, {"top": 1, "bottom": 4}, "M6_4i1o"),
    ("manufacturing_6x4", 1, {"left": 5, "right": 1}, "M6_5i1o"),
    ("manufacturing_6x4", 1, {"left": 1, "right": 6}, "M6_5i1o"),
)


@pytest.mark.parametrize(
    "template,orientation,free_per_side,expected", BUCKET_CASES,
    ids=[f"{c[3]}-{c[0][-3:]}-o{c[1]}" for c in BUCKET_CASES],
)
def test_bucket_and_servable_set(
    template: str, orientation: int, free_per_side: dict[str, int], expected: str
) -> None:
    """[12] Every live bucket is produced by a hand-built side profile."""
    evaluation = _capability(template, orientation, free_per_side)
    assert evaluation.bucket == expected
    assert set(evaluation.servable_classes) == set(sem.BUCKET_SERVABLE[expected])
    assert not evaluation.dead
    # The class witness must name a mode that really offers enough free fronts.
    for class_id, witness in evaluation.class_witness.items():
        row = sem.CLASS_BY_ID[class_id]
        assert len(witness["active_in"]) == row.r_in
        assert len(witness["active_out"]) == row.r_out


def test_all_eight_live_buckets_are_covered_by_the_cases() -> None:
    """[12b] The parametrisation is exhaustive over the derived bucket table."""
    assert {case[3] for case in BUCKET_CASES} == set(sem.BUCKET_SERVABLE)


def test_three_sided_enclosure_is_a_dead_body() -> None:
    """[13, NEGATIVE] Document 19's hand-checked fourth death sentence.

    A 3x3 walled in on three sides with only the south open: every mode puts
    inputs and outputs on opposite sides, so mode TB has no input, mode BT has no
    output and both horizontal modes are fully blocked.  No class survives.
    """
    evaluation = _capability(
        "manufacturing_3x3", 0, {"bottom": 3, "top": 0, "left": 0, "right": 0}
    )
    assert evaluation.dead
    assert evaluation.bucket is None
    assert evaluation.servable_classes == ()
    assert ev.dead_for_any_actual_class([evaluation]) == 1


def test_free_front_outside_the_portal_component_does_not_count() -> None:
    """[14] R-PAT-CONN: an isolated pocket is not a usable front."""
    anchor = _CAPABILITY_ANCHORS[("manufacturing_3x3", 0)]
    body = BodySpec(bid=0, template="manufacturing_3x3", orientation=0, local_anchor=anchor)
    fronts = {
        side: ev.side_front_cells("manufacturing_3x3", 0, anchor, side)
        for side in ev.SIDES
    }
    free = frozenset(cell for cells in fronts.values() for cell in cells)

    connected = ev.evaluate_body(body, frozenset(), free)
    assert connected.bucket == "M3_1i3o+2i1o"

    pocketed = ev.evaluate_body(body, frozenset(), frozenset())
    assert pocketed.dead, "fronts outside the portal component must not count"

    partial = ev.evaluate_body(
        body, frozenset(), frozenset(fronts["top"][:1] + fronts["bottom"][:1])
    )
    assert partial.bucket == "M3_1i1o"


def test_pole_stencil_matches_the_repository_generator() -> None:
    """[15] Coverage equals ``gen_power_pole`` including the board-edge clip."""
    poses = {
        (pose["anchor"]["x"], pose["anchor"]["y"]): {
            (cell[0], cell[1]) for cell in pose["power_coverage_cells"]
        }
        for pose in gen_power_pole()
    }
    for anchor in ((30, 30), (0, 0), (68, 68)):
        mine = ev.coverage_cells(anchor, clip=(0, 0, 70, 70))
        assert mine == poses[anchor], anchor
    # Unclipped stencil is the plain [a-5, a+6] x [b-5, b+6] box.
    assert ev.coverage_cells((30, 30)) == frozenset(
        (x, y) for x in range(25, 37) for y in range(25, 37)
    )
    assert ev.POLE_COVERAGE_RADIUS == 5


# --------------------------------------------------------------------------
# whole-pattern invariants
# --------------------------------------------------------------------------


def _clean_pattern(**overrides) -> PatternSpec:
    """A small legal CLEAN pattern used as the base for mutation tests."""
    base = {
        "region_class": "CLEAN",
        "bodies": (
            BodySpec(bid=0, template="manufacturing_3x3", orientation=0, local_anchor=(1, 1)),
            BodySpec(bid=1, template="manufacturing_3x3", orientation=0, local_anchor=(1, 9)),
        ),
        "poles": (PoleSpec(local_anchor=(4, 5)),),
        "hole": None,
    }
    base.update(overrides)
    return PatternSpec(**base)


def test_base_pattern_is_valid() -> None:
    evaluation = ev.evaluate_pattern(_clean_pattern())
    assert evaluation.ok, evaluation.violations
    assert sum(evaluation.bucket_counts.values()) == 2


HOLE_CASES = (
    ("intersects_body", HoleSpec(local_anchor=(0, 0), width=7, height=6)),
    ("leaves_region", HoleSpec(local_anchor=(9, 9), width=7, height=6)),
)


@pytest.mark.parametrize("label,hole", HOLE_CASES, ids=[c[0] for c in HOLE_CASES])
def test_illegal_holes_are_rejected(label: str, hole: HoleSpec) -> None:
    """[16] R-HOLE-IN-REGION: no body overlap, inside the region, on the corridor."""
    evaluation = ev.evaluate_pattern(_clean_pattern(hole=hole))
    assert "R-HOLE-IN-REGION" in evaluation.violations, label


def test_legal_hole_is_accepted() -> None:
    """[16b] A 7x6 hole in open space, reachable from the portal stubs.

    The body sits at (1,1) rather than (0,0) on purpose: a body flush against a
    region corner has two sides pointing out of the region, and R-FRONT-IN-REGION
    then makes it a dead body.
    """
    pattern = PatternSpec(
        region_class="CLEAN",
        bodies=(
            BodySpec(bid=0, template="manufacturing_3x3", orientation=0, local_anchor=(1, 1)),
        ),
        poles=(PoleSpec(local_anchor=(5, 5)),),
        hole=HoleSpec(local_anchor=(6, 7), width=7, height=6),
    )
    evaluation = ev.evaluate_pattern(pattern)
    assert evaluation.ok, evaluation.violations
    assert evaluation.signature[1] is True


def test_pattern_blocking_a_portal_stub_is_rejected() -> None:
    pattern = _clean_pattern(
        bodies=(
            BodySpec(bid=0, template="manufacturing_3x3", orientation=0, local_anchor=(5, 12)),
        ),
        poles=(PoleSpec(local_anchor=(9, 5)),),
    )
    evaluation = ev.evaluate_pattern(pattern)
    assert "R-PORTAL-FIXED" in evaluation.violations


#: A CLEAN pattern whose free space splits into **two** stub-bearing components.
#: The four bodies wall off row ``y = 0`` (which keeps the south stubs (6,0) and
#: (7,0)) from everything above it (which keeps the other six stubs).  Under the
#: retired multi-source reading ``portal_component`` returned the union of both
#: pockets and this pattern evaluated as legal; under the registered reading it
#: is an R-PAT-CONN violation.  Every cell here is checked by the assertions
#: below, so the fixture cannot rot into "some pattern that happens to fail".
_SPLIT_PATTERN = PatternSpec(
    region_class="CLEAN",
    bodies=(
        BodySpec(bid=0, template="manufacturing_5x5", orientation=0, local_anchor=(0, 1)),
        BodySpec(bid=1, template="manufacturing_3x3", orientation=0, local_anchor=(5, 1)),
        BodySpec(bid=2, template="manufacturing_3x3", orientation=0, local_anchor=(8, 1)),
        BodySpec(bid=3, template="manufacturing_3x3", orientation=0, local_anchor=(11, 1)),
    ),
    poles=(PoleSpec(local_anchor=(6, 6)),),
    hole=None,
)


def _free_components(free: frozenset) -> list[set]:
    remaining = set(free)
    found: list[set] = []
    while remaining:
        seed = next(iter(remaining))
        remaining.discard(seed)
        component = {seed}
        stack = [seed]
        while stack:
            u, v = stack.pop()
            for neighbour in ((u + 1, v), (u - 1, v), (u, v + 1), (u, v - 1)):
                if neighbour in remaining:
                    remaining.discard(neighbour)
                    component.add(neighbour)
                    stack.append(neighbour)
        found.append(component)
    return found


def test_two_stub_bearing_components_are_an_r_pat_conn_violation() -> None:
    """[14b] R-PAT-CONN strict: one corridor, not "one corridor per stub".

    Red before green: with the multi-source flood this exact pattern evaluated
    ``ok`` -- every live stub trivially lay in *some* stub-bearing component, so
    the check could not fire.  The premise of the test is asserted first (the
    free space really does split, and both halves really do hold live stubs), so
    a future change that merges the halves turns this into a loud failure rather
    than a silent tautology.
    """
    from g1_region_model import REGION_CLASSES

    evaluation = ev.evaluate_pattern(_SPLIT_PATTERN)
    components = _free_components(evaluation.free_cells)
    stubs = set(REGION_CLASSES["CLEAN"].live_stubs)
    hosting = [component for component in components if component & stubs]
    assert len(components) == 2, [len(c) for c in components]
    assert len(hosting) == 2, "the premise is two stub-bearing pockets"

    assert "R-PAT-CONN" in evaluation.violations
    assert not evaluation.ok
    # The returned component is one pocket, never the union of the two.
    assert evaluation.component in {frozenset(c) for c in hosting}
    assert len(evaluation.component) < len(evaluation.free_cells)


def test_portal_component_floods_from_one_canonical_root() -> None:
    """[14c] ``portal_component`` is single-source and deterministic."""
    free = frozenset({(0, 0), (0, 1), (5, 5), (5, 6)})
    seeds = ((5, 5), (0, 0))
    assert ev.component_root(free, seeds) == (0, 0)
    assert ev.portal_component(free, seeds) == frozenset({(0, 0), (0, 1)})
    # Same free space, same seeds, same answer -- order of ``seeds`` is irrelevant.
    assert ev.portal_component(free, ((0, 0), (5, 5))) == ev.portal_component(free, seeds)
    # No free seed at all: empty corridor, and the caller reports R-PAT-CONN.
    assert ev.component_root(free, ((9, 9),)) is None
    assert ev.portal_component(free, ((9, 9),)) == frozenset()


def test_a_hole_off_the_corridor_is_rejected() -> None:
    """[16c] R-HOLE-IN-REGION rides on the same single component."""
    pattern = _clean_pattern(hole=HoleSpec(local_anchor=(6, 7), width=7, height=6))
    assert ev.evaluate_pattern(pattern).ok
    walled = ev.evaluate_pattern(_SPLIT_PATTERN)
    assert "R-PAT-CONN" in walled.violations


def test_pattern_without_power_is_rejected() -> None:
    evaluation = ev.evaluate_pattern(_clean_pattern(poles=()))
    assert "R-POWER-LOCAL" in evaluation.violations


def test_pattern_with_a_pole_out_of_reach_is_rejected() -> None:
    pattern = _clean_pattern(
        bodies=(
            BodySpec(bid=0, template="manufacturing_3x3", orientation=0, local_anchor=(0, 0)),
        ),
        poles=(PoleSpec(local_anchor=(12, 12)),),
    )
    evaluation = ev.evaluate_pattern(pattern)
    assert "R-POWER-LOCAL" in evaluation.violations


# --------------------------------------------------------------------------
# catalog loader
# --------------------------------------------------------------------------


def test_loader_recomputes_and_rejects_a_tampered_signature() -> None:
    """[17, RED LINE] A stored signature is evidence of nothing.

    Fail closed: the whole catalog is refused, never repaired and never accepted
    with a warning.
    """
    evaluation = ev.evaluate_pattern(_clean_pattern())
    payload = ev.pattern_to_json(evaluation, generator={"probe": True})
    assert ev.load_pattern(payload).signature == evaluation.signature

    tampered = copy.deepcopy(payload)
    tampered["signature"]["bucket_counts"] = {"M3_1i3o+2i1o": 99}
    with pytest.raises(ev.PatternRejected, match="stored signature"):
        ev.load_pattern(tampered)

    tampered = copy.deepcopy(payload)
    tampered["signature"]["hole"] = True
    with pytest.raises(ev.PatternRejected):
        ev.load_pattern(tampered)

    tampered = copy.deepcopy(payload)
    tampered["pattern_id"] = "0" * 16
    with pytest.raises(ev.PatternRejected, match="content address"):
        ev.load_pattern(tampered)

    tampered = copy.deepcopy(payload)
    tampered["free_space"]["portal_component_size"] += 1
    with pytest.raises(ev.PatternRejected, match="free_space"):
        ev.load_pattern(tampered)


def test_loader_rejects_an_authority_claim() -> None:
    """[17b] No artifact of this line may claim authority, even hand-edited."""
    payload = ev.pattern_to_json(ev.evaluate_pattern(_clean_pattern()))
    payload["authority"]["carries_bound"] = True
    with pytest.raises(Exception, match="carries_bound"):
        ev.load_pattern(payload)


def test_loader_rejects_a_pattern_that_no_longer_recomputes_as_legal() -> None:
    """[17c] Decision content that violates an invariant is refused on load."""
    payload = ev.pattern_to_json(ev.evaluate_pattern(_clean_pattern()))
    payload["spec"]["poles"] = []
    with pytest.raises(ev.PatternRejected):
        ev.load_pattern(payload)


def test_loader_rejects_unknown_and_missing_fields() -> None:
    payload = ev.pattern_to_json(ev.evaluate_pattern(_clean_pattern()))
    extra = copy.deepcopy(payload)
    extra["surprise"] = 1
    with pytest.raises(Exception, match="unknown fields"):
        ev.load_pattern(extra)

    missing = copy.deepcopy(payload)
    del missing["invariants"]
    with pytest.raises(Exception, match="missing required fields"):
        ev.load_pattern(missing)
