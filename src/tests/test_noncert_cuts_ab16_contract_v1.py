from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724" / "ab16_contract_v1.py"
SPEC = importlib.util.spec_from_file_location("noncert_cuts_ab16_contract_v1", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)


def _terminal(**changes: object) -> dict[str, object]:
    value = {
        "status": "UNKNOWN",
        "internal_budget_reached": True,
        "runner_completed": True,
        "process_exit_code": 0,
        "outer_timeout": False,
        "runtime_max_sec": False,
        "oom": False,
        "killed": False,
        "crashed": False,
        "limit_drift": False,
    }
    value.update(changes)
    return value


def _pair(
    control: int | float,
    treatment: int | float,
    *,
    direction: str = "lower_is_better",
    threshold: int | float = 1,
    threshold_rule: str = "at_least",
) -> dict[str, object]:
    return CONTRACT.pair_delta(
        {
            "control": control,
            "treatment": treatment,
            "direction": direction,
            "threshold": threshold,
            "threshold_rule": threshold_rule,
        }
    )


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ((0, 0, 0), CONTRACT.ORGANIC_NONACTIVATION),
        ((3, 0, 0), CONTRACT.NO_ORGANIC_APPLIED_CUT),
        ((3, 2, 0), CONTRACT.NO_ORGANIC_APPLIED_CUT),
        ((3, 2, 1), CONTRACT.ORGANIC_APPLIED),
    ],
)
def test_gca_classes_are_mutually_exclusive(
    counts: tuple[int, int, int],
    expected: str,
) -> None:
    result = CONTRACT.classify_cut_activity(dict(zip(("generated", "compiled", "applied"), counts, strict=True)))
    assert result["activation_class"] == expected


def test_gca_rejects_impossible_or_non_strict_counts() -> None:
    with pytest.raises(CONTRACT.ContractError, match="A <= C <= G"):
        CONTRACT.classify_cut_activity({"generated": 1, "compiled": 0, "applied": 1})
    with pytest.raises(CONTRACT.ContractError, match="exact nonnegative"):
        CONTRACT.classify_cut_activity({"generated": True, "compiled": 0, "applied": 0})
    with pytest.raises(CONTRACT.ContractError, match="exact key set"):
        CONTRACT.classify_cut_activity({"generated": 0, "compiled": 0, "applied": 0, "extra": 0})


def test_internal_budget_unknown_is_credible_but_never_mathematical() -> None:
    result = CONTRACT.classify_solver_terminal(_terminal())
    assert result == {
        "credibility_status": CONTRACT.CREDIBILITY_PASS,
        "solver_terminal_class": CONTRACT.BUDGET_CENSORED_UNKNOWN,
        "failure_reasons": [],
        "mathematical_claim_authorized": False,
    }


def test_outer_failure_precedes_internal_budget_unknown() -> None:
    result = CONTRACT.classify_solver_terminal(_terminal(outer_timeout=True, oom=True))
    assert result["credibility_status"] == CONTRACT.CREDIBILITY_INCOMPLETE
    assert result["solver_terminal_class"] is None
    assert result["failure_reasons"] == ["outer_timeout", "oom"]


def test_uncensored_unknown_and_dirty_exit_fail_closed() -> None:
    uncensored = CONTRACT.classify_solver_terminal(_terminal(internal_budget_reached=False))
    assert uncensored["failure_reasons"] == ["unknown_without_internal_budget_censor"]
    dirty = CONTRACT.classify_solver_terminal(_terminal(status="FEASIBLE", process_exit_code=7))
    assert dirty["credibility_status"] == CONTRACT.CREDIBILITY_INCOMPLETE


def test_pair_delta_keeps_raw_and_sign_normalized_values() -> None:
    lower = _pair(10, 7)
    assert lower["raw_treatment_minus_control"] == -3
    assert lower["benefit"] == 3
    assert lower["pair_band"] == CONTRACT.PAIR_BENEFIT

    higher = _pair(10, 7, direction="higher_is_better")
    assert higher["raw_treatment_minus_control"] == -3
    assert higher["benefit"] == -3
    assert higher["pair_band"] == CONTRACT.PAIR_REGRESSION


def test_pair_threshold_supports_inclusive_and_strict_rules() -> None:
    assert _pair(10, 9, threshold=1)["pair_band"] == CONTRACT.PAIR_BENEFIT
    assert _pair(10, 9, threshold=1, threshold_rule="strictly_greater")["pair_band"] == CONTRACT.PAIR_NO_EFFECT


def test_pair_aggregate_reports_raw_mean_and_conservative_worst() -> None:
    aggregate = CONTRACT.aggregate_pairs(
        {
            "ab": _pair(10, 7, threshold=0.1),
            "ba": _pair(20, 18, threshold=0.2),
        }
    )
    assert aggregate["raw_delta_by_order"] == {"ab": -3, "ba": -2}
    assert aggregate["benefit_by_order"] == {"ab": 3, "ba": 2}
    assert aggregate["mean_benefit"] == 2.5
    assert aggregate["worst_pair_benefit"] == 2
    assert aggregate["threshold_by_order"] == {"ab": 0.1, "ba": 0.2}
    assert aggregate["repeat_class"] == "REPEATED_BENEFIT"


def test_bundle_diagnostic_computes_d_ab_and_d_ba() -> None:
    result = CONTRACT.bundle_nonadditivity(
        {
            "region-capacity": {"ab": 1, "ba": 2},
            "shape-packing-hall": {"ab": 3, "ba": 4},
            "power-hitting-set": {"ab": 5, "ba": 6},
            "bundle": {"ab": 12, "ba": 15},
        }
    )
    assert result["D_AB"] == 3
    assert result["D_BA"] == 3
    assert result["mean_D"] == 3
    assert result["interaction_identified"] is False


def _configuration_record(
    ab: dict[str, object],
    ba: dict[str, object],
    **changes: object,
) -> dict[str, object]:
    value = {
        "configuration": "region-capacity",
        "same_manager_epoch": True,
        "pair_credibility": {"ab": "PASS", "ba": "PASS"},
        "pair_results": {"ab": ab, "ba": ba},
        "primary_delta_by_order": {"ab": 0, "ba": 0},
        "treatment_organic_applied": {"ab": True, "ba": True},
    }
    value.update(changes)
    return value


def test_configuration_gate_is_credibility_first() -> None:
    ab = _pair(10, 7)
    ba = _pair(10, 8)
    result = CONTRACT.configuration_gate(
        _configuration_record(
            ab,
            ba,
            same_manager_epoch=False,
            pair_credibility={
                "ab": CONTRACT.CREDIBILITY_PASS,
                "ba": CONTRACT.CREDIBILITY_INCOMPLETE,
            },
        )
    )
    assert result["credibility_status"] == CONTRACT.CREDIBILITY_INCOMPLETE
    assert result["outcome_class"] is None
    assert result["strongest_claim"] is None


def test_configuration_runtime_effect_requires_both_organic_treatments() -> None:
    ab = _pair(10, 7)
    ba = _pair(10, 8)
    admitted = CONTRACT.configuration_gate(_configuration_record(ab, ba))
    assert admitted["outcome_class"] == CONTRACT.SINGLE_FAMILY_RUNTIME_EFFECT

    missing_activation = CONTRACT.configuration_gate(
        _configuration_record(
            ab,
            ba,
            treatment_organic_applied={"ab": True, "ba": False},
        )
    )
    assert missing_activation["outcome_class"] == CONTRACT.INCONSISTENT_FIXED_RUN_OBSERVATIONS
    assert missing_activation["strongest_claim"] is None


def test_configuration_gate_replays_pair_arithmetic_and_names_bundle_claim() -> None:
    ab = _pair(10, 7)
    ba = _pair(10, 8)
    bundle = CONTRACT.configuration_gate(_configuration_record(ab, ba, configuration="bundle"))
    assert bundle["outcome_class"] == CONTRACT.BUNDLE_RUNTIME_EFFECT

    drifted = dict(ab)
    drifted["benefit"] = 999
    with pytest.raises(CONTRACT.ContractError, match="arithmetic replay"):
        CONTRACT.configuration_gate(_configuration_record(drifted, ba))


def test_configuration_classifies_no_effect_and_regression() -> None:
    assert (
        CONTRACT.configuration_gate(_configuration_record(_pair(10, 10), _pair(10, 10)))["outcome_class"]
        == CONTRACT.FIXED_CONFIGURATION_NO_EFFECT
    )

    assert (
        CONTRACT.configuration_gate(_configuration_record(_pair(10, 12), _pair(10, 11)))["outcome_class"]
        == CONTRACT.FIXED_CONFIGURATION_REGRESSION
    )

    primary_regression = _configuration_record(
        _pair(10, 10),
        _pair(10, 10),
        primary_delta_by_order={"ab": -1, "ba": -1},
    )
    assert CONTRACT.configuration_gate(primary_regression)["outcome_class"] == CONTRACT.FIXED_CONFIGURATION_REGRESSION


def test_primary_incumbent_delta_precedes_secondary_metric() -> None:
    primary_benefit = CONTRACT.configuration_gate(
        _configuration_record(
            _pair(10, 20),
            _pair(10, 20),
            primary_delta_by_order={"ab": 1, "ba": 1},
        )
    )
    assert primary_benefit["outcome_class"] == CONTRACT.SINGLE_FAMILY_RUNTIME_EFFECT
    assert primary_benefit["pair_aggregate"]["claim_gate_pair_band_by_order"] == {
        "ab": CONTRACT.PAIR_BENEFIT,
        "ba": CONTRACT.PAIR_BENEFIT,
    }
    assert primary_benefit["pair_aggregate"]["decision_tier_by_order"] == {
        "ab": "primary_incumbent_presence",
        "ba": "primary_incumbent_presence",
    }

    inconsistent = CONTRACT.configuration_gate(
        _configuration_record(
            _pair(10, 9),
            _pair(10, 9),
            primary_delta_by_order={"ab": 1, "ba": -1},
        )
    )
    assert inconsistent["outcome_class"] == CONTRACT.INCONSISTENT_FIXED_RUN_OBSERVATIONS
    assert inconsistent["strongest_claim"] is None


def test_primary_delta_is_strict_and_cannot_be_boolean() -> None:
    with pytest.raises(CONTRACT.ContractError, match="primary delta"):
        CONTRACT.configuration_gate(
            _configuration_record(
                _pair(10, 10),
                _pair(10, 10),
                primary_delta_by_order={"ab": True, "ba": 0},
            )
        )


def test_suite_gate_replays_all_configurations_and_bundle_diagnostic() -> None:
    records = {
        configuration: _configuration_record(
            _pair(10, 7),
            _pair(10, 8),
            configuration=configuration,
        )
        for configuration in CONTRACT.CONFIGURATIONS
    }
    result = CONTRACT.suite_gate({"configuration_records": records})
    assert result["credibility_status"] == CONTRACT.CREDIBILITY_PASS
    assert result["status"] == CONTRACT.SUITE_COMPLETE
    assert set(result["configuration_results"]) == set(CONTRACT.CONFIGURATIONS)
    assert result["bundle_nonadditivity_diagnostic"]["D_AB"] == -6
    assert result["bundle_nonadditivity_diagnostic"]["D_BA"] == -4
    assert all(value is False for value in result["authorizations"].values())


def test_suite_gate_is_credibility_first_and_rejects_omission() -> None:
    records = {
        configuration: _configuration_record(
            _pair(10, 10),
            _pair(10, 10),
            configuration=configuration,
        )
        for configuration in CONTRACT.CONFIGURATIONS
    }
    records["power-hitting-set"]["pair_credibility"] = {
        "ab": CONTRACT.CREDIBILITY_PASS,
        "ba": CONTRACT.CREDIBILITY_INCOMPLETE,
    }
    result = CONTRACT.suite_gate({"configuration_records": records})
    assert result["credibility_status"] == CONTRACT.CREDIBILITY_INCOMPLETE
    assert result["status"] == CONTRACT.CREDIBILITY_INCOMPLETE
    assert result["incomplete_configurations"] == ["power-hitting-set"]

    omitted = dict(records)
    omitted.pop("bundle")
    with pytest.raises(CONTRACT.ContractError, match="exact key set"):
        CONTRACT.suite_gate({"configuration_records": omitted})


def test_preselection_stop_does_not_consume_slot() -> None:
    state = CONTRACT.new_consumption_state()
    stopped = CONTRACT.transition_consumption_state(
        state,
        {
            "event": "PRESELECTION_FAILURE",
            "slot": CONTRACT.ARM_SEQUENCE[0],
            "reason": "manager_epoch_mismatch",
        },
    )
    assert state["slots"][0]["state"] == "PENDING"
    assert stopped["slots"][0]["state"] == "PENDING"
    assert stopped["next_index"] == 0
    assert stopped["stopped"] is True


def test_postselection_failure_consumes_slot_and_stops_immediately() -> None:
    initial = CONTRACT.new_consumption_state()
    selected = CONTRACT.transition_consumption_state(
        initial,
        {
            "event": "SELECTION_CREATED",
            "slot": CONTRACT.ARM_SEQUENCE[0],
            "reason": None,
        },
    )
    stopped = CONTRACT.transition_consumption_state(
        selected,
        {
            "event": "ARM_CREDIBILITY_INCOMPLETE",
            "slot": CONTRACT.ARM_SEQUENCE[0],
            "reason": "outer_timeout",
        },
    )
    assert stopped["slots"][0]["state"] == "INCOMPLETE"
    assert stopped["slots"][1]["state"] == "PENDING"
    with pytest.raises(CONTRACT.ContractError, match="stopped campaign"):
        CONTRACT.transition_consumption_state(
            stopped,
            {
                "event": "SELECTION_CREATED",
                "slot": CONTRACT.ARM_SEQUENCE[1],
                "reason": None,
            },
        )


def test_consumption_state_rejects_out_of_order_future_mutation() -> None:
    state = CONTRACT.new_consumption_state()
    state["slots"][1]["state"] = "COMPLETE"
    with pytest.raises(CONTRACT.ContractError, match="future arm slot"):
        CONTRACT.transition_consumption_state(
            state,
            {
                "event": "SELECTION_CREATED",
                "slot": CONTRACT.ARM_SEQUENCE[0],
                "reason": None,
            },
        )


def test_credible_arm_advances_only_after_selection() -> None:
    state = CONTRACT.new_consumption_state()
    with pytest.raises(CONTRACT.ContractError, match="consumed selection"):
        CONTRACT.transition_consumption_state(
            state,
            {
                "event": "ARM_CREDIBILITY_PASS",
                "slot": CONTRACT.ARM_SEQUENCE[0],
                "reason": None,
            },
        )
    selected = CONTRACT.transition_consumption_state(
        state,
        {
            "event": "SELECTION_CREATED",
            "slot": CONTRACT.ARM_SEQUENCE[0],
            "reason": None,
        },
    )
    completed = CONTRACT.transition_consumption_state(
        selected,
        {
            "event": "ARM_CREDIBILITY_PASS",
            "slot": CONTRACT.ARM_SEQUENCE[0],
            "reason": None,
        },
    )
    assert completed["next_index"] == 1
    assert completed["slots"][0]["state"] == "COMPLETE"


def test_strict_json_rejects_duplicates_noncanonical_and_nan() -> None:
    value = {"a": [1, True, None], "b": "x"}
    raw = CONTRACT.canonical_json_bytes(value)
    assert CONTRACT.strict_loads(raw) == value
    with pytest.raises(CONTRACT.ContractError, match="duplicate"):
        CONTRACT.strict_loads(b'{"a":1,"a":2}')
    with pytest.raises(CONTRACT.ContractError, match="not canonical"):
        CONTRACT.strict_loads(b'{"b": "x", "a": [1, true, null]}')
    with pytest.raises(CONTRACT.ContractError, match="invalid JSON constant"):
        CONTRACT.strict_loads(b'{"a":NaN}')
    with pytest.raises(CONTRACT.ContractError, match="strict JSON data"):
        CONTRACT.canonical_json_bytes({"not_json": (1, 2)})


def test_contract_source_contains_no_process_or_solver_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = ("subprocess", "systemctl", "systemd-run", "CpSolver", "import os")
    assert all(token not in source for token in forbidden)
    assert json.loads(CONTRACT.canonical_json_bytes({"sequence": list(CONTRACT.ARM_SEQUENCE)}))["sequence"] == list(
        CONTRACT.ARM_SEQUENCE
    )
