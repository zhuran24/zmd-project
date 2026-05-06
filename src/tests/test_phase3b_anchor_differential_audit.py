from __future__ import annotations

from ortools.sat.python import cp_model

from src.search.phase3b_anchor_differential_audit import (
    _anchor_profile,
    _anchor_capacity_certificate,
    _compare_anchor_profiles,
)


def test_anchor_profile_counts_var_and_enforcement_references() -> None:
    model = cp_model.CpModel()
    u0 = model.NewBoolVar("u__0")
    u1 = model.NewBoolVar("u__1")
    active = model.NewBoolVar("active__slot")
    x = model.NewIntVar(0, 10, "cover_choice_x__slot")
    family_count = model.NewIntVar(0, 4, "power_pole_family_count__family_017")
    model.AddExactlyOne([u0, u1])
    model.Add(x >= 2).OnlyEnforceIf(u0)
    model.Add(active == 1).OnlyEnforceIf(u0)
    model.Add(family_count + u0 <= 3)
    proto = model.Proto()

    profile = _anchor_profile(proto, anchor_idx=0, u_var_index=u0.Index())

    assert profile["present"] is True
    assert profile["constraint_reference_count"] == 4
    assert profile["enforcement_reference_count"] == 2
    assert profile["var_reference_count"] == 2
    assert profile["neighbor_prefix_counts"]["u__"] == 1
    assert profile["neighbor_prefix_counts"]["active__"] == 1
    assert profile["neighbor_prefix_counts"]["cover_choice_"] == 1
    assert profile["neighbor_prefix_counts"]["power_pole_family_count__"] == 1
    assert profile["family_count_linear_reference_count"] == 1
    assert profile["family_count_name_counts"] == {"family_017": 1}
    family_ref = profile["family_count_linear_refs"][0]
    assert family_ref["linear_domain"] == [-9223372036854775808, 3]
    assert family_ref["family_count_terms"][0]["family_name"] == "family_017"
    assert family_ref["family_count_terms"][0]["domain"] == [0, 4]
    active_bound = family_ref["active_family_count_bounds"][0]
    assert active_bound["implied_upper_when_anchor_active"] == 2
    assert active_bound["upper_reduction_when_anchor_active"] == 2.0


def test_compare_anchor_profiles_reports_deltas() -> None:
    left = {
        "anchor_idx": 118,
        "present": True,
        "constraint_reference_count": 2,
        "enforcement_reference_count": 1,
        "var_reference_count": 1,
        "constraint_kind_counts": {"linear": 1, "exactly_one": 1},
        "neighbor_prefix_counts": {"active__": 1},
    }
    right = {
        "anchor_idx": 125,
        "present": True,
        "constraint_reference_count": 3,
        "enforcement_reference_count": 2,
        "var_reference_count": 1,
        "constraint_kind_counts": {"linear": 2, "exactly_one": 1},
        "neighbor_prefix_counts": {"active__": 1, "cover_choice_": 2},
    }

    comparison = _compare_anchor_profiles([left, right])

    assert comparison["comparable"] is True
    delta = comparison["comparisons"][0]
    assert delta["constraint_reference_delta"] == 1
    assert delta["enforcement_reference_delta"] == 1
    assert delta["constraint_kind_count_delta"] == {"linear": 1}
    assert delta["neighbor_prefix_count_delta"] == {"cover_choice_": 2}


def test_anchor_capacity_certificate_detects_exact_deficit() -> None:
    anchor_profile = {
        "family_count_linear_refs": [
            {
                "active_family_count_bounds": [
                    {
                        "family_name": "family_a",
                        "implied_upper_when_anchor_active": 1,
                    }
                ]
            }
        ]
    }
    capacity_profile = {
        "powered_template_demands": {"powered_box": 5},
        "families": [
            {
                "family_id": "family_a",
                "count_var_upper_bound": 3,
                "coefficients": {"powered_box": 2},
            },
            {
                "family_id": "family_b",
                "count_var_upper_bound": 1,
                "coefficients": {"powered_box": 1},
            },
        ],
    }

    certificate = _anchor_capacity_certificate(anchor_profile, capacity_profile)

    assert certificate["evaluated"] is True
    assert certificate["has_deficit"] is True
    template = certificate["template_certificates"][0]
    assert template["max_capacity"] == 3
    assert template["demand"] == 5
    assert template["slack"] == -2
    assert template["deficit"] is True
