"""W0 G1: the generator runs end to end and its output survives the loader.

research-only.  The only test in the batch that starts a real solver, kept small
on purpose: one region class, one menu target, a one-second ceiling probe.  Every
pattern it writes is read back through the catalog loader, which recomputes the
signature from scratch -- so this covers the generate/serialise/reload round trip
that stage B depends on.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import g1_pattern_evaluator as ev  # noqa: E402
import g1_pattern_generator as gen  # noqa: E402
from g1_pattern_schema import CatalogSpec, load_strict  # noqa: E402
from g1_region_model import REGION_CLASSES  # noqa: E402

pytestmark = pytest.mark.evidence


def test_pose_enumeration_respects_the_masks() -> None:
    """No candidate pose ever covers fixed furniture or a reserved cell."""
    region = REGION_CLASSES["CLEAN"]
    poses = gen.enumerate_body_poses(region)
    assert poses, "CLEAN must admit body poses"
    blocked = set(region.fixed_local) | set(region.reserved_local)
    for pose in poses:
        assert not set(pose.cells) & blocked
    for anchor in gen.enumerate_pole_poses(region):
        assert not set(ev.pole_cells(anchor)) & blocked


def test_core_region_admits_no_manufacturing_body() -> None:
    """Reserving all 20 core fronts leaves T[0,4] unable to host any machine.

    A structural fact of this restriction level, not a tuning artefact: all 219
    machines must fit into the other 24 regions.
    """
    assert gen.enumerate_body_poses(REGION_CLASSES["CORE"]) == ()


def test_target_menu_is_deterministic_and_area_feasible() -> None:
    """H-TARGET-MENU: same order every time, never over the free budget.

    The hole is charged ``42 - maxK``: forced-free cells are body-free anyway, so
    the part of the hole that lands on them costs the packing budget nothing.
    The old assertion charged a flat 42 and therefore locked in the over-strict
    filter it was supposed to be guarding.
    """
    region = REGION_CLASSES["CLEAN"]
    first = gen.build_target_menu(region)
    second = gen.build_target_menu(region)
    assert [t.as_json() for t in first] == [t.as_json() for t in second]
    assert first, "the menu must not be empty"
    budget = region.usable
    credit = gen.hole_forced_free_credit(region, spine=gen.BATCH_RUN_SPINE)
    for target in first:
        area = sum(
            gen.TEMPLATE_AREAS[template] * count for template, _level, count in target.counts
        )
        assert area + 4 + (gen.HOLE_CELLS - credit if target.hole else 0) <= budget


def test_hole_budget_credit_is_recomputed_per_class_and_per_lane() -> None:
    """[2b] ``maxK`` is measured from the masks, never a written-down constant.

    The recomputation is done here the long way -- intersect every legal hole
    placement with the forced-free set -- so the test fails if the production
    helper starts short-cutting.  The batch's operating lane is pinned at the
    same time: ``spine=False`` is what every number in this batch means.
    """
    assert gen.BATCH_RUN_SPINE is False
    assert gen.GeneratorConfig().spine is gen.BATCH_RUN_SPINE
    assert gen.HOLE_CELLS == 42

    expected_off = {"CLEAN": 2, "CORNER": 4, "BOTTOM_I1": 4, "LEFT_J3": 4, "CORE": 0}
    for name, region in REGION_CLASSES.items():
        forced = gen._forced_free(region, spine=False)
        brute = max(
            (
                len(
                    {
                        (anchor[0] + dx, anchor[1] + dy)
                        for dx in range(width)
                        for dy in range(height)
                    }
                    & forced
                )
                for anchor, width, height in gen.enumerate_hole_poses(region)
            ),
            default=0,
        )
        assert gen.hole_forced_free_credit(region, spine=False) == brute, name
        if name in expected_off:
            assert brute == expected_off[name], name
        # The hard-spine lane forces a whole row and column free, so the credit
        # can only grow -- and the CLI still has to be able to ask for it.
        assert gen.hole_forced_free_credit(region, spine=True) >= brute, name

    # A concrete consequence: with the credit applied, CLEAN admits menu targets
    # a flat 42-cell charge rejected.
    clean = REGION_CLASSES["CLEAN"]
    credit = gen.hole_forced_free_credit(clean, spine=False)
    assert credit > 0
    budget = clean.usable
    with_credit = [t for t in gen.build_target_menu(clean) if t.hole]
    recovered = [
        target
        for target in with_credit
        if sum(
            gen.TEMPLATE_AREAS[template] * count
            for template, _level, count in target.counts
        )
        + 4
        + gen.HOLE_CELLS
        > budget
    ]
    assert recovered, "the credit must actually let targets back into the menu"


def test_generate_reload_round_trip(tmp_path: Path) -> None:
    """One real CP-SAT target: catalog is written, then recomputed on load.

    The three second budgets are **timeouts, not workloads**: on an idle machine
    this test finishes in about 2.3s because both solves return early.  They are
    set far above that because the whole fast lane runs under ``pytest -n auto``
    on 24 logical cores, and a 2s solver cap starved by 23 sibling workers turns a
    solvable centre-band target into an empty catalog -- a wall-clock false red
    (observed 2026-08-03).  Raising the caps converts that into a slower pass and
    changes nothing about what is asserted.
    """
    config = gen.GeneratorConfig(
        budget_seconds=180.0,
        target_seconds=30.0,
        ceiling_seconds=15.0,
        solutions_per_target=1,
        max_derived_subsets=1,
        workers=4,
        seed=0,
        max_targets=1,
        max_bodies=3,
        region_classes=("CLEAN",),
    )
    manifest = gen.generate_catalog(config, output_dir=tmp_path, progress=False)

    assert manifest["schema"] == "w0_g1_catalog_manifest_v1"
    assert manifest["authority"]["carries_bound"] is False
    entry = manifest["catalogs"]["CLEAN"]
    assert entry["patterns"] >= 1, "the top sparse target must yield a pattern"
    assert entry["complete"] is False, "a one-target run is a truncated menu"

    # Alarm meters travel with the catalog, and meter 2 is zero on a written one.
    meters = entry["stats"]["alarm_meters"]
    assert meters["postcheck_divergence"]["count"] == 0
    assert "strip_dead_bodies" in meters["retired_paths"]
    assert manifest["connectivity"]["enforced"] == "in_model"

    catalog_path = tmp_path / "catalog" / "CLEAN.json"
    payload = load_strict(catalog_path)
    catalog = CatalogSpec.from_json(payload)
    assert catalog.region_class == "CLEAN"
    assert catalog.region_multiplicity == 16
    assert len(catalog.patterns) == entry["patterns"]

    signatures = set()
    for stored in catalog.patterns:
        evaluation = ev.load_pattern(stored, region_class="CLEAN")
        assert evaluation.ok
        assert ev.dead_for_any_actual_class(evaluation.bodies) == 0
        signatures.add(evaluation.signature)
    assert len(signatures) == len(catalog.patterns), "catalog must be signature-unique"

    manifest_payload = load_strict(tmp_path / "catalog" / "manifest.json")
    assert manifest_payload["catalogs"]["CLEAN"]["sha256"] == entry["sha256"]
    assert manifest_payload["frozen_inputs"]["rules"]["sha256"] == (
        "5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05"
    )


def test_arithmetic_pre_gate_reading_is_fail_closed(tmp_path: Path) -> None:
    """Supply over-counts, so only ``supply < demand`` may conclude anything."""
    config = gen.GeneratorConfig(region_classes=("CLEAN",))
    plenty = gen._arithmetic_pre_gate(
        {"CLEAN": {"upper_bound": 10_000, "proved_optimal": True}}, config
    )
    assert plenty["verdict"] == "INCONCLUSIVE", "one class measured is not all of them"

    everything = {
        name: {"upper_bound": 0, "proved_optimal": True}
        for name in REGION_CLASSES
    }
    starved = gen._arithmetic_pre_gate(everything, config)
    assert starved["body_area_demand"] == 3325
    assert starved["supply_upper_bound"] == 0
    assert starved["verdict"] == "INFEASIBLE_BY_AREA"

    generous = {
        name: {"upper_bound": 196, "proved_optimal": True} for name in REGION_CLASSES
    }
    ok = gen._arithmetic_pre_gate(generous, config)
    assert ok["verdict"] == "NOT_EXCLUDED_BY_AREA"
    assert "excludes nothing" in ok["reading"]


def test_derived_subsets_only_remove_bodies() -> None:
    """H-DERIVED-SUBSETS keeps the region class and never adds a body."""
    from g1_pattern_schema import BodySpec, PatternSpec, PoleSpec

    spec = PatternSpec(
        region_class="CLEAN",
        bodies=(
            BodySpec(bid=0, template="manufacturing_3x3", orientation=0, local_anchor=(1, 1)),
            BodySpec(bid=1, template="manufacturing_3x3", orientation=0, local_anchor=(1, 9)),
        ),
        poles=(PoleSpec(local_anchor=(4, 5)),),
        hole=None,
    )
    assert ev.evaluate_pattern(spec).ok
    derived = gen.derive_subsets(spec, 3)
    assert len(derived) == 2
    for child in derived:
        assert child.region_class == "CLEAN"
        assert len(child.bodies) == 1
        assert ev.evaluate_pattern(child).ok
        assert {b.local_anchor for b in child.bodies} < {
            b.local_anchor for b in spec.bodies
        }


# --------------------------------------------------------------------------
# connectivity is in the model, not a post-filter
# --------------------------------------------------------------------------


def _certificate_status(demanded, *, reading: str) -> str:
    """Solve the bare certificate over two 4-disconnected pairs of cells."""
    from ortools.sat.python import cp_model

    cells = [(0, 0), (0, 1), (5, 0), (5, 1)]
    model = cp_model.CpModel()
    conn = {cell: model.new_bool_var(f"c{cell}") for cell in cells}
    sources = gen._add_connectivity_certificate(
        model, conn, [(5, 0), (0, 0)], reading=reading
    )
    expected = ((0, 0),) if reading == gen.STRICT_READING else ((0, 0), (5, 0))
    assert sources == expected, "sources are sorted, and strict keeps only the first"
    for cell in demanded:
        model.add(conn[cell] == 1)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_workers = 2
    return solver.status_name(solver.solve(model))


def test_connectivity_certificate_is_single_source() -> None:
    """[3a] Two anchors in two pockets is infeasible, not "one component each".

    Directly on the certificate, with a hand-made free space: cells (0,0)-(0,1)
    and (5,0)-(5,1) are two 4-disconnected pairs.  A multi-source flow would send
    a unit into each pair and report FEASIBLE -- that is exactly the loose
    reading.  With one root, asking both pairs to be on the corridor is
    unsatisfiable.
    """
    strict = gen.STRICT_READING
    assert _certificate_status([(0, 0), (0, 1)], reading=strict) in {"OPTIMAL", "FEASIBLE"}
    assert _certificate_status([(0, 0), (5, 0)], reading=strict) == "INFEASIBLE"
    # The far pocket alone is unreachable from the root, so it cannot be lit up
    # even on its own.
    assert _certificate_status([(5, 1)], reading=strict) == "INFEASIBLE"


def test_the_loose_control_reading_is_the_retired_one() -> None:
    """[3a2] The control arm differs from the registered arm in exactly one way.

    Same certificate, same cells, sources switched from "the smallest live stub"
    to "every live stub": the two pockets that the registered reading refuses are
    accepted, which is the retired union-of-components reading and nothing else.
    That is what makes the paired control solve a measurement of the corridor
    constraint rather than of some other difference between two models.
    """
    loose = gen.LOOSE_READING
    assert _certificate_status([(0, 0), (5, 0)], reading=loose) in {"OPTIMAL", "FEASIBLE"}
    assert _certificate_status([(5, 1)], reading=loose) in {"OPTIMAL", "FEASIBLE"}
    with pytest.raises(ValueError, match="unknown R-PAT-CONN reading"):
        _certificate_status([(0, 0)], reading="whatever")


def test_solved_targets_survive_the_evaluator_unchanged() -> None:
    """[3b] Alarm meter 2: the model and the post-check are the same restriction.

    Every spec the solver returns is re-evaluated from scratch.  Under the old
    post-filter design a large share of them came back invalid (that was the
    design); now a single invalid one is an implementation bug, so this test
    asserts the strong form -- all of them, no exceptions, on real solves.
    """
    region = REGION_CLASSES["CLEAN"]
    menu = [t for t in gen.build_target_menu(region, max_bodies=3)][:4]
    poses = gen.enumerate_body_poses(region)
    poles = gen.enumerate_pole_poses(region)
    holes = gen.enumerate_hole_poses(region)
    config = gen.GeneratorConfig(target_seconds=10.0, workers=4, solutions_per_target=1)

    solved = 0
    for target in menu:
        specs, _elapsed, _status = gen._solve_target(
            region, target, poses, poles, holes, config
        )
        for spec in specs:
            evaluation = ev.evaluate_pattern(spec)
            assert evaluation.ok, (target.as_json(), evaluation.violations)
            assert ev.dead_for_any_actual_class(evaluation.bodies) == 0
            solved += 1
    assert solved >= 1, "the sparse head of the menu must still be solvable"


def test_postcheck_divergence_blocks_instead_of_being_counted() -> None:
    """[3c] Alarm meter 2 fails closed: a divergence raises, it does not tally.

    A pattern with no pole violates R-POWER-LOCAL, which the model cannot
    produce.  Handed in as solver output it must stop the run; handed in as a
    derived subset -- an ordinary guess -- it is merely refused and counted.
    """
    from g1_pattern_schema import BodySpec, PatternSpec

    broken = PatternSpec(
        region_class="CLEAN",
        bodies=(
            BodySpec(bid=0, template="manufacturing_3x3", orientation=0, local_anchor=(1, 1)),
        ),
        poles=(),
        hole=None,
    )
    accumulator = gen.CatalogAccumulator(region_class="CLEAN")
    stats = gen.GeneratorStats()
    with pytest.raises(gen.GeneratorBlocked, match="postcheck divergence"):
        gen._accept(broken, accumulator, stats, {}, from_solver=True)
    assert stats.postcheck_divergence == 1

    tolerant = gen.GeneratorStats()
    assert gen._accept(broken, accumulator, tolerant, {}, from_solver=False) is None
    assert tolerant.postcheck_divergence == 0
    assert tolerant.derived_rejected == 1


def test_loose_only_fronts_is_a_fail_closed_invariant_not_a_meter() -> None:
    """[3d] The retired accept-side meter is now a check that can only fail closed.

    Two halves.  First the quantity itself still measures something real: on the
    walled pattern -- which the evaluator refuses -- fourteen body fronts are
    reachable only under the retired reading.  Second, on the path it actually
    runs (accepted patterns) it is 0 by construction, which is why it is no
    longer a meter: an accepted pattern has every stub inside the one rooted
    component, so a non-zero reading would mean the evaluator drifted, and that
    goes through the ``GeneratorBlocked`` door rather than into a counter.
    """
    from g1_pattern_schema import BodySpec, PatternSpec, PoleSpec

    plain = PatternSpec(
        region_class="CLEAN",
        bodies=(
            BodySpec(bid=0, template="manufacturing_3x3", orientation=0, local_anchor=(1, 1)),
            BodySpec(bid=1, template="manufacturing_3x3", orientation=0, local_anchor=(1, 9)),
        ),
        poles=(PoleSpec(local_anchor=(4, 5)),),
        hole=None,
    )
    evaluation = ev.evaluate_pattern(plain)
    assert evaluation.ok
    assert gen.loose_only_fronts(evaluation) == 0

    # A wall along y = 1..5 cuts row 0 off, taking twelve bottom fronts and the
    # 5x5's two right-hand fronts with it: fourteen front cells the retired
    # reading would have counted.
    walled = PatternSpec(
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
    cut = ev.evaluate_pattern(walled)
    assert "R-PAT-CONN" in cut.violations
    assert gen.loose_only_fronts(cut) == 14

    # The door: an accepted pattern that somehow paid a loose-only front stops
    # the run the same way a post-check divergence does.  The invariant cannot be
    # violated for real -- ``evaluation.ok`` implies 0 -- so the probe is faked
    # here, which is the only way to exercise the branch at all.
    accumulator = gen.CatalogAccumulator(region_class="CLEAN")
    stats = gen.GeneratorStats()
    original = gen.loose_only_fronts
    try:
        gen.loose_only_fronts = lambda _evaluation: 3  # type: ignore[assignment]
        with pytest.raises(gen.GeneratorBlocked, match="loose-only fronts"):
            gen._accept(plain, accumulator, stats, {}, from_solver=True)
    finally:
        gen.loose_only_fronts = original  # type: ignore[assignment]
    assert stats.postcheck_divergence == 0, "this is the other door, not that one"
    assert not accumulator.by_signature, "nothing may be filed on the way out"


def _walled_region():
    """A region class whose *pinned* furniture splits it into two pockets.

    Column ``u = 6`` is fixed furniture from ``v = 0`` to ``v = 13``, so the free
    space is two 4-disconnected halves and each half keeps live portal stubs:
    (0,6) and (0,7) west, (13,6), (13,7), (7,0) and (7,13) east of the wall.  No
    packing can put them on one corridor -- the wall is not a decision -- so
    *every* target of this class is strict-infeasible, while the loose reading
    (one source per stub) is happy to call the two halves a corridor.

    That is the cleanest possible instance of what alarm meter 1 measures: a
    target removed by the single-corridor reading and by nothing else.  It is a
    fixture region rather than a shipped one because in the ten real classes the
    same situation only appears deep inside dense targets, where proving strict
    infeasibility costs minutes -- and a meter has to be tested on a model that
    finishes in milliseconds.
    """
    from g1_region_model import RegionClass

    return RegionClass(
        name="WALLED_FIXTURE",
        regions=((0, 0),),
        fixed_local=frozenset((6, v) for v in range(14)),
        reserved_local=frozenset(),
    )


def test_the_in_model_filter_is_measured_by_a_paired_loose_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[3g] Alarm meter 1 counts on the *rejected* side, through the real driver.

    Red before green.  The retired meter recounted fronts on every **accepted**
    pattern, and an accepted pattern pays no loose-only front by construction --
    so on a run like this one, where nothing is accepted at all, it read 0 no
    matter how much the restriction cost.  The replacement re-solves every
    strict-proved-infeasible target once under the loose reading, which is the
    only side of the run where the cost is visible.

    Everything below ``generate_catalog`` is the production path: the menu, the
    ceiling probe, the strict solve, the pairing branch, the accounting and the
    manifest.  Only the region class is a fixture, and it is one because the
    phenomenon has to be reproducible in milliseconds (see ``_walled_region``).
    """
    region = _walled_region()
    monkeypatch.setitem(gen.REGION_CLASSES, region.name, region)
    monkeypatch.setattr(
        gen, "REGION_CLASS_ORDER", tuple(gen.REGION_CLASS_ORDER) + (region.name,)
    )

    # The premise, asserted rather than assumed: two pockets, both with stubs.
    free = {
        (u, v) for u in range(14) for v in range(14) if (u, v) not in region.fixed_local
    }
    west = {cell for cell in free if cell[0] < 6}
    east = {cell for cell in free if cell[0] > 6}
    assert west | east == free, "the wall is the whole column"
    stubs = set(region.live_stubs)
    assert stubs & west and stubs & east, "each pocket keeps live stubs"

    config = gen.GeneratorConfig(
        budget_seconds=60.0,
        target_seconds=10.0,
        ceiling_seconds=5.0,
        solutions_per_target=1,
        max_derived_subsets=0,
        max_targets=1,
        max_bodies=1,
        region_classes=(region.name,),
    )
    manifest = gen.generate_catalog(config, output_dir=tmp_path, progress=False)

    entry = manifest["catalogs"][region.name]
    stats = entry["stats"]
    meter = stats["alarm_meters"]["in_model_filter"]
    control = meter["loose_control"]

    assert stats["targets_attempted"] == 1
    assert stats["targets_feasible"] == 0
    assert meter["targets_infeasible"] == 1, "the strict solve must PROVE it, not time out"
    assert control["strict_infeasible_loose_feasible"] == 1
    assert control["strict_infeasible_loose_infeasible"] == 0
    assert control["strict_infeasible_loose_unproved"] == 0
    assert set(control["control_status_counts"]) <= {"OPTIMAL", "FEASIBLE"}
    assert control["control_solve_seconds"] > 0

    # The old shape's blind spot, stated as an assertion: this run accepts no
    # pattern at all, so every accept-side counter is structurally zero here.
    assert entry["patterns"] == 0
    assert stats["solutions_found"] == 0
    assert stats["alarm_meters"]["postcheck_divergence"]["count"] == 0

    # A loose solution exists -- that is what the control just proved -- and none
    # of them may ever reach a catalog.
    written = json.loads(
        (tmp_path / "catalog" / f"{region.name}.json").read_text(encoding="utf-8")
    )
    assert written["patterns"] == []
    assert manifest["connectivity"]["enforced"] == "in_model"


def test_retired_paths_announce_themselves() -> None:
    """[3e] Alarm meter 3: a retired path is declared, never a silent zero."""
    assert "strip_dead_bodies" in gen.RETIRED_PATHS
    assert "post_filter_connectivity_reject" in gen.RETIRED_PATHS
    assert "corridor_tax_meter" in gen.RETIRED_PATHS
    for reason in gen.RETIRED_PATHS.values():
        assert reason.startswith("retired 2026-08-04"), reason
    assert not hasattr(gen, "strip_dead_bodies"), "the retired path must be gone"
    assert not hasattr(gen, "corridor_tax"), "the retired meter must be gone"
    stats = gen.GeneratorStats().as_json()
    assert "stripped_to_smaller" not in stats, "a pinned-at-zero counter is worse"
    assert "rejected_connectivity" not in stats
    meter_one = stats["alarm_meters"]["in_model_filter"]
    for gone in ("corridor_tax_front_cells", "patterns_paying_corridor_tax"):
        assert gone not in meter_one, "the fail-soft-zero counter must not linger"
    assert stats["alarm_meters"]["retired_paths"] == dict(gen.RETIRED_PATHS)


def test_generator_never_writes_outside_its_output_directory(tmp_path: Path) -> None:
    """The generator is a pure producer: everything lands under --output-dir."""
    config = gen.GeneratorConfig(
        budget_seconds=30.0,
        target_seconds=1.0,
        ceiling_seconds=1.0,
        solutions_per_target=1,
        max_derived_subsets=0,
        max_targets=1,
        region_classes=("CORE",),
    )
    gen.generate_catalog(config, output_dir=tmp_path, progress=False)
    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert written == ["catalog/CORE.json", "catalog/manifest.json"]
    core = json.loads((tmp_path / "catalog" / "CORE.json").read_text(encoding="utf-8"))
    assert core["patterns"] == [], "CORE can host nothing under this restriction level"
