from __future__ import annotations

import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lagrangian_accounting as la  # noqa: E402
import pricing_probe as pp  # noqa: E402

DUALS = HERE / "duals.json"
BUNDLE = HERE.parent / "pricing_exp" / "11_runnable"


def _mu(name: str):
    payload = json.loads(DUALS.read_text())
    return next(row for row in payload["duals"] if row["name"] == name)["mu_scaled"]


def _pi(name: str):
    payload = json.loads(DUALS.read_text())
    return next(row for row in payload["duals"] if row["name"] == name)["pi_scaled"]


def test_body_area_total_is_3325():
    assert sum(la.CLASS_DEMAND[c] * la.CLASS_AREA[c] for c in la.CLASS_ORDER) == 3325


def test_bucket_weight_elimination_vectors():
    assert list(la.bucket_weights(_mu("D0_AREA")).values()) == [9, 9, 9, 25, 25, 24, 24, 24]
    assert list(la.bucket_weights(_mu("D1_SCARCITY_PRICES")).values()) == [8, 8, 8, 23, 23, 22, 22, 22]
    assert list(la.bucket_weights(_mu("D2_SLACK_EDGE_SELECTIVE")).values()) == [-3, -3, 9, -5, 25, -6, -6, 24]


def test_dual_anchor_totals():
    pi0 = _pi("D0_AREA")
    assert la.bound_from_pricing(pi0, _mu("D0_AREA"), 0) == 3392
    assert la.bound_from_pricing(_pi("D1_SCARCITY_PRICES"), _mu("D1_SCARCITY_PRICES"), 15) == 3781
    assert la.bound_from_pricing(_pi("D2_SLACK_EDGE_SELECTIVE"), _mu("D2_SLACK_EDGE_SELECTIVE"), -20) == 7247


def test_negative_epsilon_is_not_clipped():
    pi = _pi("D0_AREA")
    eps = {f: 0 for f in la.FAMILY_ORDER}
    eps["CLEAN"] = -1
    assert la.bound_from_epsilon(pi, eps, _mu("D0_AREA"), 0) == 3376


def test_existing_hole_aware_branch_accounting():
    nohole = {
        "CLEAN": 146,
        **{f: 134 for f in la.BOUNDARY_FAMILIES},
        "CORNER": 118,
    }
    hole = {
        "CLEAN": 129,
        **la.BOUNDARY_HOLE_BASE,
        "CORNER": 85,
    }
    branches = la.hole_branch_bounds(nohole, hole)
    assert branches["hole@CLEAN"] == 3375
    assert branches["hole@LEFT_J1"] == 3387
    assert branches["hole@LEFT_J3"] == 3388
    assert branches["hole@CORNER"] == 3359
    assert branches["unified"] == 3388


def test_clean_multiplicity_leverage():
    pi = _pi("D0_AREA")
    mu = _mu("D0_AREA")
    for drop, expected in [(1, 3376), (2, 3360), (3, 3344), (4, 3328), (5, 3312)]:
        bounds = dict(pi)
        bounds["CLEAN"] -= drop
        assert la.bound_from_pricing(bounds, mu, 0) == expected


def test_probe_dual_specific_level_dominance():
    modules = pp.load_modules(BUNDLE)
    level_bucket = pp.derive_level_bucket(modules)

    d1 = pp.load_dual(DUALS, "D1_SCARCITY_PRICES")
    kept1 = pp._kept_levels(modules, pp.derive_bucket_weights(d1, modules), level_bucket)
    assert kept1 == {
        "manufacturing_3x3": {1},
        "manufacturing_5x5": {1},
        "manufacturing_6x4": {3},
    }

    d2 = pp.load_dual(DUALS, "D2_SLACK_EDGE_SELECTIVE")
    kept2 = pp._kept_levels(modules, pp.derive_bucket_weights(d2, modules), level_bucket)
    assert kept2 == {
        "manufacturing_3x3": {3},
        "manufacturing_5x5": {2},
        "manufacturing_6x4": {5},
    }


def test_all_duals_cover_every_mu_and_pi_coordinate():
    payload = json.loads(DUALS.read_text())
    for row in payload["duals"]:
        assert set(row["mu_scaled"]) == set(la.CLASS_ORDER)
        assert set(row["pi_scaled"]) == set(la.FAMILY_ORDER)
        assert all(value >= 0 for value in row["mu_scaled"].values())


def test_analyzer_marks_empty_manifest_incomplete():
    import analyze_protocol as ap
    duals = ap._dual_rows(DUALS)
    result = ap.decide({"stages": {}}, duals)
    assert result["verdict"] == "INCOMPLETE_NO_CALIBRATION"
    assert result["hybrid_bounds"]["D0_AREA"]["hybrid_bound"] == 3392
    assert result["D0_exactly_one_hole_cap3_scope"]["unified_bound"] == 3388


def test_clean_142_triggers_exact_hole_branch_certificate():
    import analyze_protocol as ap
    best = {
        ("D0_AREA", "CLEAN", False): {
            "certified_objective_bound_scaled": 142,
            "scale": 1,
        }
    }
    row = ap._d0_exactly_one_hole_bound(best)
    assert row["branches"]["hole@CLEAN"] == 3315
    assert row["branches"]["hole@LEFT_J3"] == 3324
    assert row["unified_bound"] == 3324
