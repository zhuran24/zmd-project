"""W0 G1 stage B: master answer -> 70x70 geometry, end to end.

research-only.  Nothing here produces or consumes a bound.

The catalog these tests run against is built here, from the evaluator, and lives
in ``tmp_path``: the real stage A catalog is a runtime artifact under
``.artifacts/`` and a test that needed it would be a test that cannot run on a
fresh checkout.  What is *not* synthetic is everything the expansion touches --
the real region model, the real fixed furniture, the real frozen class table and
instance census, and the real independent audit in its own isolated process.

The board these tests expand is deliberately almost empty (one region carries two
3x3 bodies and the hole; the other twenty-four take the empty pattern), which is
what makes the audit assertion sharp: the *only* thing the auditor may complain
about is the class census, because a two-body board obviously is not the 219-body
census.  Every other check -- front offsets, front freedom, power coverage, pole
irredundancy, reserved fronts, hole legality, free-space connectivity -- has to
come back clean, and that is the real subject of the test.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from g1_exact_cover_master import MasterConfig, load_catalogs, solve_master  # noqa: E402
from g1_expand_solution import (  # noqa: E402
    W0_FIXED_FURNITURE_SPEC,
    W0_PROFILE_ID,
    expand_master_solution,
)
from g1_pattern_evaluator import (  # noqa: E402
    coverage_cells,
    evaluate_pattern,
    pattern_to_json,
    second_cell_outside,
    side_front_cells,
)
from g1_pattern_schema import (  # noqa: E402
    CATALOG_SCHEMA,
    GEOMETRY_SCHEMA,
    RESEARCH_AUTHORITY,
    BodySpec,
    HoleSpec,
    PatternSpec,
    PoleSpec,
    dump_canonical,
    mask_sha256,
)
from g1_region_model import REGION_CLASS_ORDER, REGION_CLASSES  # noqa: E402
import run_g1  # noqa: E402

pytestmark = pytest.mark.evidence

#: A hand-checked legal CLEAN pattern: two 3x3 bodies, one pole covering both, a
#: 6x7 hole in the corner of the region.  Every derived property is recomputed by
#: the evaluator when the catalog is loaded, so these coordinates are an input,
#: never a claim.
SEED_BODIES = ((0, 8), (3, 7))
SEED_POLE = (0, 11)
SEED_HOLE = ((0, 0), 6, 7)

_MODE_SIDES = {
    "TB": ("top", "bottom"),
    "BT": ("bottom", "top"),
    "RL": ("right", "left"),
    "LR": ("left", "right"),
}


def _seed_pattern() -> PatternSpec:
    return PatternSpec(
        region_class="CLEAN",
        bodies=tuple(
            BodySpec(
                bid=index,
                template="manufacturing_3x3",
                orientation=0,
                local_anchor=anchor,
            )
            for index, anchor in enumerate(SEED_BODIES)
        ),
        poles=(PoleSpec(local_anchor=SEED_POLE),),
        hole=HoleSpec(
            local_anchor=SEED_HOLE[0], width=SEED_HOLE[1], height=SEED_HOLE[2]
        ),
    )


def _write_catalog(directory: Path) -> Path:
    """One real CLEAN pattern; every other region class gets an empty file."""
    catalog = directory / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    evaluation = evaluate_pattern(_seed_pattern())
    assert evaluation.ok, evaluation.violations
    for name in REGION_CLASS_ORDER:
        region = REGION_CLASSES[name]
        patterns: List[Dict[str, Any]] = []
        if name == "CLEAN":
            patterns.append(pattern_to_json(evaluation, generator={"source": "test"}))
        dump_canonical(
            catalog / f"{name}.json",
            {
                "schema": CATALOG_SCHEMA,
                "authority": dict(RESEARCH_AUTHORITY),
                "region_class": name,
                "region_multiplicity": region.multiplicity,
                "fixed_mask_sha256": mask_sha256(region.fixed_local),
                "reserved_mask_sha256": mask_sha256(region.reserved_local),
                "complete": True,
                "patterns": patterns,
            },
        )
    return catalog


def _solved(catalog: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    columns = load_catalogs(catalog)
    master = solve_master(
        columns,
        MasterConfig(max_time_in_seconds=60.0, workers=2),
        demand={"3L": 2},
    )
    assert master["status"] in {"OPTIMAL", "FEASIBLE"}, master
    geometry = expand_master_solution(master, catalog)
    return master, geometry


@pytest.fixture(scope="module")
def expanded(tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Any]:
    directory = tmp_path_factory.mktemp("w0g1expand")
    catalog = _write_catalog(directory)
    master, geometry = _solved(catalog)
    return {"catalog": catalog, "master": master, "geometry": geometry}


def test_the_master_places_the_only_hole_pattern_exactly_once(
    expanded: Dict[str, Any]
) -> None:
    """[E1] 25 regions, one of them carrying the seed pattern, the rest empty."""
    master = expanded["master"]
    assert len(master["selection"]) == 25
    regions = {tuple(row["region"]) for row in master["selection"]}
    assert len(regions) == 25
    assert master["class_assignment"] == [
        {"bucket": "M3_1i3o+2i1o", "class": "3L", "count": 2}
    ]


def test_expansion_puts_two_real_bodies_on_the_board(
    expanded: Dict[str, Any]
) -> None:
    """[E2] Local coordinates became global ones and the hole came with them."""
    geometry = expanded["geometry"]
    assert geometry["schema"] == GEOMETRY_SCHEMA
    assert geometry["authority"] == RESEARCH_AUTHORITY
    assert geometry["layout_profile"]["profile_id"] == W0_PROFILE_ID
    assert geometry["layout_profile"]["fixed_furniture_spec"] == W0_FIXED_FURNITURE_SPEC
    assert len(geometry["fixed_furniture"]) == 47
    assert len(geometry["placements"]) == 2
    hole = geometry["hole"]
    assert (hole["width"], hole["height"]) == (SEED_HOLE[1], SEED_HOLE[2])
    origin = tuple(geometry["expansion"]["hole_region"])
    assert hole["anchor"] == [14 * origin[0], 14 * origin[1]]
    for placement in geometry["placements"]:
        assert placement["operation_class"] == "3L"
        assert placement["provisional"] is True
        assert placement["instance_id"]


def test_active_fronts_are_the_first_cell_outside_the_body(
    expanded: Dict[str, Any]
) -> None:
    """[E3, RED LINE] The 07-18 front-offset incident, pinned on the expanded
    board: every active front is the first cell outside, and no active front is
    ever the retired second cell."""
    for placement in expanded["geometry"]["placements"]:
        anchor = (int(placement["anchor"][0]), int(placement["anchor"][1]))
        template = str(placement["template"])
        orientation = int(placement["orientation"])
        in_side, out_side = _MODE_SIDES[str(placement["mode"])]
        for key, side in (
            ("active_input_fronts", in_side),
            ("active_output_fronts", out_side),
        ):
            first = set(side_front_cells(template, orientation, anchor, side))
            second = set(second_cell_outside(template, orientation, anchor, side))
            cells = {(int(c[0]), int(c[1])) for c in placement[key]}
            assert cells, (placement["instance_id"], key)
            assert cells <= first
            assert not (cells & (second - first))


def test_the_pole_set_is_globally_minimal(expanded: Dict[str, Any]) -> None:
    """[E4, T-POLE-MINIMAL] One pole for two bodies, and it is load bearing:
    removing it leaves a body unpowered."""
    geometry = expanded["geometry"]
    poles = [tuple(entry["anchor"]) for entry in geometry["power_poles"]]
    assert len(poles) == 1
    assert geometry["expansion"]["poles_after_minimisation"] == 1
    stencil = coverage_cells(poles[0], clip=(0, 0, 70, 70))
    for placement in geometry["placements"]:
        cells = {
            (int(placement["anchor"][0]) + dx, int(placement["anchor"][1]) + dy)
            for dx in range(int(placement["size"][0]))
            for dy in range(int(placement["size"][1]))
        }
        assert cells & stencil


def test_the_independent_audit_only_faults_the_census(
    expanded: Dict[str, Any], tmp_path: Path
) -> None:
    """[E5] The whole geometry pipeline, checked by the stdlib-only auditor in its
    own ``-I -S -B`` process.  A two-body board must fail the 219-body census and
    must fail nothing else."""
    geometry_path = tmp_path / "g1_geometry.json"
    geometry_path.write_text(
        json.dumps(expanded["geometry"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths = run_g1.RunPaths(
        catalog=expanded["catalog"],
        rules=run_g1.DEFAULT_RULES_PATH,
        instances=run_g1.DEFAULT_INSTANCES_PATH,
    )
    report, observation = run_g1._run_audit(geometry_path, paths, timeout=300.0)
    assert report, observation
    assert {"-I", "-S", "-B"} <= set(observation["argv"])
    assert report["issue_codes"] == ["class_census_mismatch"], report["issues"]
    assert report["summary"]["dead_for_any_actual_class"] == 0
    assert report["summary"]["manufacturing_placements"] == 2
    assert report["summary"]["power"]["irredundant"] is True
    assert report["summary"]["hole"]["area"] == 42
    assert report["summary"]["free_space"]["anchor_components"] == 1
