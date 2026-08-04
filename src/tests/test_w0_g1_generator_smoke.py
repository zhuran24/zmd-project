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
        region_classes=("CLEAN",),
    )
    manifest = gen.generate_catalog(config, output_dir=tmp_path, progress=False)

    assert manifest["schema"] == "w0_g1_catalog_manifest_v1"
    assert manifest["authority"]["carries_bound"] is False
    entry = manifest["catalogs"]["CLEAN"]
    assert entry["patterns"] >= 1, "one centre-band target must yield a pattern"
    assert entry["complete"] is False, "a one-target run is a truncated menu"

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
