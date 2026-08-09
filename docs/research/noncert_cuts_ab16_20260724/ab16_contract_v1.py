"""Pure classification contract for the prospective non-certified AB16 suite.

The module has no I/O, process, solver, or systemd surface.  It provides
strict-JSON-compatible functions for preregistering and replaying the
credibility and outcome arithmetic of the sixteen-arm experiment.

Passing these functions never establishes cut-family soundness, SAT, UNSAT,
runtime usefulness outside the frozen configuration, or production
``CERTIFIED`` status.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy
import hashlib
import json
import math
from typing import Any


CONFIGURATIONS = (
    "region-capacity",
    "shape-packing-hall",
    "power-hitting-set",
    "bundle",
)
ORDERS = ("ab", "ba")
ARMS = ("control", "treatment")
ARM_SEQUENCE = tuple(
    f"{configuration}-{order}-{arm}"
    for configuration in CONFIGURATIONS
    for order, arms in (
        ("ab", ("control", "treatment")),
        ("ba", ("treatment", "control")),
    )
    for arm in arms
)

CREDIBILITY_PASS = "PASS"
CREDIBILITY_INCOMPLETE = "CREDIBILITY_INCOMPLETE"

ORGANIC_NONACTIVATION = "ORGANIC_NONACTIVATION"
NO_ORGANIC_APPLIED_CUT = "NO_ORGANIC_APPLIED_CUT"
ORGANIC_APPLIED = "ORGANIC_APPLIED"
BUDGET_CENSORED_UNKNOWN = "BUDGET_CENSORED_UNKNOWN"

PAIR_BENEFIT = "BENEFIT"
PAIR_NO_EFFECT = "NO_EFFECT"
PAIR_REGRESSION = "REGRESSION"

FIXED_CONFIGURATION_NO_EFFECT = "FIXED_CONFIGURATION_NO_EFFECT"
FIXED_CONFIGURATION_REGRESSION = "FIXED_CONFIGURATION_REGRESSION"
INCONSISTENT_FIXED_RUN_OBSERVATIONS = "INCONSISTENT_FIXED_RUN_OBSERVATIONS"
SINGLE_FAMILY_RUNTIME_EFFECT = "SINGLE_FAMILY_RUNTIME_EFFECT"
BUNDLE_RUNTIME_EFFECT = "BUNDLE_RUNTIME_EFFECT"
SUITE_COMPLETE = "AB16_FIXED_CONFIGURATION_SUITE_COMPLETE"

STATE_SCHEMA = "noncert-cuts-ab16-consumption-state-v2"
ATTEMPT_INPUT_SET_SCHEMA = "noncert-cuts-ab16-attempt-input-set-v1"
RESEARCH_ONLY_AUTHORIZATIONS = {
    "family_global_soundness_authorized": False,
    "global_claim_authorized": False,
    "mathematical_claim_authorized": False,
    "production_certified_authorized": False,
    "stage_b_promotion_authorized": False,
}
TERMINAL_STATUSES = frozenset(
    {
        "CERTIFIED",
        "FEASIBLE",
        "OPTIMAL",
        "INFEASIBLE",
        "UNKNOWN",
        "UNPROVEN",
        "MODEL_INVALID",
        "ERROR",
    }
)
OUTER_FAILURE_FIELDS = (
    "outer_timeout",
    "runtime_max_sec",
    "oom",
    "killed",
    "crashed",
    "limit_drift",
)


class ContractError(ValueError):
    """A strict contract input is malformed or semantically inconsistent."""


def _strict_mapping(
    value: object,
    expected_keys: set[str],
    label: str,
) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != expected_keys:
        raise ContractError(f"{label} must have the exact key set")
    return value


def _strict_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ContractError(f"{label} must be an exact boolean")
    return value


def _strict_nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ContractError(f"{label} must be an exact nonnegative integer")
    return value


def _strict_number(value: object, label: str) -> int | float:
    if type(value) not in {int, float} or not math.isfinite(value):
        raise ContractError(f"{label} must be a finite JSON number")
    return value


def _strict_nonempty_string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ContractError(f"{label} must be a non-empty string")
    return value


def _validate_json_value(value: object, label: str = "JSON value") -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ContractError(f"{label} contains a non-finite number")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json_value(item, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ContractError(f"{label} contains a non-string key")
            _validate_json_value(item, f"{label}.{key}")
        return
    raise ContractError(f"{label} is not strict JSON data")


def canonical_json_bytes(value: object) -> bytes:
    """Return canonical strict JSON bytes without a trailing newline."""

    _validate_json_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _strict_lower_hex(value: object, *, length: int, label: str) -> str:
    digest = _strict_nonempty_string(value, label)
    if len(digest) != length or any(character not in "0123456789abcdef" for character in digest):
        raise ContractError(f"{label} must be exactly {length} lowercase hex characters")
    return digest


def _content_identity_projection(value: object, label: str) -> dict[str, object]:
    identity = _strict_mapping(
        value,
        {"mode", "path", "sha256", "size_bytes"},
        label,
    )
    path = _strict_nonempty_string(identity["path"], f"{label}.path")
    if not path.startswith("/"):
        raise ContractError(f"{label}.path must be absolute")
    mode = _strict_nonnegative_int(identity["mode"], f"{label}.mode")
    if mode > 0o7777:
        raise ContractError(f"{label}.mode is outside the permission-bit range")
    return {
        "mode": mode,
        "sha256": _strict_lower_hex(
            identity["sha256"],
            length=64,
            label=f"{label}.sha256",
        ),
        "size_bytes": _strict_nonnegative_int(
            identity["size_bytes"],
            f"{label}.size_bytes",
        ),
    }


def _identity_map_projection(value: object, label: str) -> dict[str, dict[str, object]]:
    if type(value) is not dict or not value:
        raise ContractError(f"{label} must be an exact non-empty object")
    if any(type(role) is not str or not role for role in value):
        raise ContractError(f"{label} roles must be non-empty strings")
    projection: dict[str, dict[str, object]] = {}
    for role in sorted(value):
        projection[role] = _content_identity_projection(value[role], f"{label}.{role}")
    return projection


def attempt_input_set_sha256(
    *,
    preregistration_sha256: object,
    repository_head: object,
    strict_input_identities: object,
    tool_identities: object,
) -> str:
    """Hash the actual attempt inputs while excluding location-only paths."""

    projection = {
        "preregistration_sha256": _strict_lower_hex(
            preregistration_sha256,
            length=64,
            label="preregistration_sha256",
        ),
        "repository_head": _strict_lower_hex(
            repository_head,
            length=40,
            label="repository_head",
        ),
        "schema": ATTEMPT_INPUT_SET_SCHEMA,
        "strict_input_identities": _identity_map_projection(
            strict_input_identities,
            "strict_input_identities",
        ),
        "tool_identities": _identity_map_projection(
            tool_identities,
            "tool_identities",
        ),
    }
    return hashlib.sha256(canonical_json_bytes(projection)).hexdigest()


def strict_loads(raw: bytes) -> object:
    """Parse only canonical UTF-8 JSON with no duplicate object keys."""

    if type(raw) is not bytes or not raw:
        raise ContractError("strict JSON input must be non-empty bytes")

    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ContractError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(ContractError(f"invalid JSON constant: {token}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("strict JSON input is malformed") from exc
    if canonical_json_bytes(value) != raw:
        raise ContractError("strict JSON input is not canonical")
    return value


def classify_cut_activity(record: Mapping[str, object]) -> dict[str, object]:
    """Classify one G/C/A counter triple into exactly one activation class."""

    checked = _strict_mapping(
        record,
        {"generated", "compiled", "applied"},
        "cut activity",
    )
    generated = _strict_nonnegative_int(checked["generated"], "generated")
    compiled = _strict_nonnegative_int(checked["compiled"], "compiled")
    applied = _strict_nonnegative_int(checked["applied"], "applied")
    if not 0 <= applied <= compiled <= generated:
        raise ContractError("cut activity must satisfy 0 <= A <= C <= G")
    if generated == 0:
        activation_class = ORGANIC_NONACTIVATION
    elif applied == 0:
        activation_class = NO_ORGANIC_APPLIED_CUT
    else:
        activation_class = ORGANIC_APPLIED
    return {
        "activation_class": activation_class,
        "applied": applied,
        "compiled": compiled,
        "generated": generated,
    }


def classify_solver_terminal(record: Mapping[str, object]) -> dict[str, object]:
    """Separate a valid internal-budget UNKNOWN from outer credibility failures."""

    checked = _strict_mapping(
        record,
        {
            "status",
            "internal_budget_reached",
            "runner_completed",
            "process_exit_code",
            *OUTER_FAILURE_FIELDS,
        },
        "solver terminal",
    )
    status = checked["status"]
    if type(status) is not str or status not in TERMINAL_STATUSES:
        raise ContractError("solver terminal status is unsupported")
    internal_budget_reached = _strict_bool(
        checked["internal_budget_reached"],
        "internal_budget_reached",
    )
    runner_completed = _strict_bool(checked["runner_completed"], "runner_completed")
    process_exit_code = checked["process_exit_code"]
    if type(process_exit_code) is not int:
        raise ContractError("process_exit_code must be an exact integer")
    failures = [field for field in OUTER_FAILURE_FIELDS if _strict_bool(checked[field], field)]
    if failures:
        return {
            "credibility_status": CREDIBILITY_INCOMPLETE,
            "solver_terminal_class": None,
            "failure_reasons": failures,
            "mathematical_claim_authorized": False,
        }
    if not runner_completed or process_exit_code != 0:
        return {
            "credibility_status": CREDIBILITY_INCOMPLETE,
            "solver_terminal_class": None,
            "failure_reasons": ["runner_not_clean"],
            "mathematical_claim_authorized": False,
        }
    if status in {"UNKNOWN", "UNPROVEN"}:
        if not internal_budget_reached:
            return {
                "credibility_status": CREDIBILITY_INCOMPLETE,
                "solver_terminal_class": None,
                "failure_reasons": ["unknown_without_internal_budget_censor"],
                "mathematical_claim_authorized": False,
            }
        terminal_class = BUDGET_CENSORED_UNKNOWN
    elif status in {"MODEL_INVALID", "ERROR"}:
        return {
            "credibility_status": CREDIBILITY_INCOMPLETE,
            "solver_terminal_class": None,
            "failure_reasons": [status.lower()],
            "mathematical_claim_authorized": False,
        }
    else:
        if internal_budget_reached:
            return {
                "credibility_status": CREDIBILITY_INCOMPLETE,
                "solver_terminal_class": None,
                "failure_reasons": ["budget_censor_on_non_censored_terminal"],
                "mathematical_claim_authorized": False,
            }
        terminal_class = f"SOLVER_{status}_OBSERVATION"
    return {
        "credibility_status": CREDIBILITY_PASS,
        "solver_terminal_class": terminal_class,
        "failure_reasons": [],
        "mathematical_claim_authorized": False,
    }


def pair_delta(record: Mapping[str, object]) -> dict[str, object]:
    """Compute raw T-C delta and a sign-normalized benefit for one pair."""

    checked = _strict_mapping(
        record,
        {
            "control",
            "treatment",
            "direction",
            "threshold",
            "threshold_rule",
        },
        "pair metric",
    )
    control = _strict_number(checked["control"], "control")
    treatment = _strict_number(checked["treatment"], "treatment")
    threshold = _strict_number(checked["threshold"], "threshold")
    if threshold <= 0:
        raise ContractError("pair threshold must be positive")
    direction = checked["direction"]
    if direction not in {"higher_is_better", "lower_is_better"}:
        raise ContractError("pair direction is unsupported")
    threshold_rule = checked["threshold_rule"]
    if threshold_rule not in {"at_least", "strictly_greater"}:
        raise ContractError("pair threshold rule is unsupported")
    raw_delta = treatment - control
    benefit = raw_delta if direction == "higher_is_better" else -raw_delta
    crosses = (lambda value: value >= threshold) if threshold_rule == "at_least" else (lambda value: value > threshold)
    if crosses(benefit):
        band = PAIR_BENEFIT
    elif crosses(-benefit):
        band = PAIR_REGRESSION
    else:
        band = PAIR_NO_EFFECT
    return {
        "benefit": benefit,
        "control": control,
        "direction": direction,
        "pair_band": band,
        "raw_treatment_minus_control": raw_delta,
        "threshold": threshold,
        "threshold_rule": threshold_rule,
        "treatment": treatment,
    }


def _checked_pair_result(value: object, label: str) -> Mapping[str, Any]:
    checked = _strict_mapping(
        value,
        {
            "benefit",
            "control",
            "direction",
            "pair_band",
            "raw_treatment_minus_control",
            "threshold",
            "threshold_rule",
            "treatment",
        },
        label,
    )
    replayed = pair_delta(
        {
            "control": checked["control"],
            "treatment": checked["treatment"],
            "direction": checked["direction"],
            "threshold": checked["threshold"],
            "threshold_rule": checked["threshold_rule"],
        }
    )
    if dict(checked) != replayed:
        raise ContractError(f"{label} differs from pair arithmetic replay")
    return checked


def aggregate_pairs(record: Mapping[str, object]) -> dict[str, object]:
    """Aggregate the AB and BA repeats; mean is descriptive, worst gates claims."""

    checked = _strict_mapping(record, {"ab", "ba"}, "pair aggregate")
    ab = _checked_pair_result(checked["ab"], "AB pair")
    ba = _checked_pair_result(checked["ba"], "BA pair")
    for field in ("direction", "threshold_rule"):
        if ab[field] != ba[field]:
            raise ContractError("AB and BA pair metric contracts differ")
    benefits = {"ab": ab["benefit"], "ba": ba["benefit"]}
    raw = {
        "ab": ab["raw_treatment_minus_control"],
        "ba": ba["raw_treatment_minus_control"],
    }
    bands = {"ab": ab["pair_band"], "ba": ba["pair_band"]}
    if set(bands.values()) == {PAIR_BENEFIT}:
        repeat_class = "REPEATED_BENEFIT"
    elif set(bands.values()) == {PAIR_NO_EFFECT}:
        repeat_class = "REPEATED_NO_EFFECT"
    elif set(bands.values()) == {PAIR_REGRESSION}:
        repeat_class = "REPEATED_REGRESSION"
    else:
        repeat_class = "INCONSISTENT_REPEATS"
    return {
        "benefit_by_order": benefits,
        "mean_benefit": (benefits["ab"] + benefits["ba"]) / 2,
        "pair_band_by_order": bands,
        "raw_delta_by_order": raw,
        "repeat_class": repeat_class,
        "threshold_by_order": {
            "ab": ab["threshold"],
            "ba": ba["threshold"],
        },
        "worst_pair_benefit": min(benefits.values()),
    }


def bundle_nonadditivity(record: Mapping[str, object]) -> dict[str, object]:
    """Compute the preregisterable bundle-minus-sum diagnostic for AB and BA."""

    checked = _strict_mapping(
        record,
        set(CONFIGURATIONS),
        "bundle diagnostic",
    )
    values: dict[str, Mapping[str, Any]] = {}
    for configuration in CONFIGURATIONS:
        member = _strict_mapping(
            checked[configuration],
            {"ab", "ba"},
            f"{configuration} pair benefits",
        )
        values[configuration] = {order: _strict_number(member[order], f"{configuration}.{order}") for order in ORDERS}
    singles = CONFIGURATIONS[:-1]
    d_ab = values["bundle"]["ab"] - sum(values[name]["ab"] for name in singles)
    d_ba = values["bundle"]["ba"] - sum(values[name]["ba"] for name in singles)
    return {
        "D_AB": d_ab,
        "D_BA": d_ba,
        "basis": "sign_normalized_pair_benefit",
        "claim": "BUNDLE_NONADDITIVITY_DIAGNOSTIC",
        "interaction_identified": False,
        "mean_D": (d_ab + d_ba) / 2,
    }


def configuration_gate(record: Mapping[str, object]) -> dict[str, object]:
    """Apply credibility before any fixed-configuration outcome or effect claim."""

    checked = _strict_mapping(
        record,
        {
            "configuration",
            "same_manager_epoch",
            "pair_credibility",
            "pair_results",
            "primary_delta_by_order",
            "treatment_organic_applied",
        },
        "configuration gate",
    )
    configuration = checked["configuration"]
    if configuration not in CONFIGURATIONS:
        raise ContractError("configuration is unsupported")
    same_manager_epoch = _strict_bool(
        checked["same_manager_epoch"],
        "same_manager_epoch",
    )
    primary_delta = _strict_mapping(
        checked["primary_delta_by_order"],
        {"ab", "ba"},
        "primary delta",
    )
    for order in ORDERS:
        if type(primary_delta[order]) is not int or primary_delta[order] not in {
            -1,
            0,
            1,
        }:
            raise ContractError("primary delta must be an exact integer in {-1,0,1}")
    credibility = _strict_mapping(
        checked["pair_credibility"],
        {"ab", "ba"},
        "pair credibility",
    )
    for order in ORDERS:
        if credibility[order] not in {
            CREDIBILITY_PASS,
            CREDIBILITY_INCOMPLETE,
        }:
            raise ContractError("pair credibility value is unsupported")
    applied = _strict_mapping(
        checked["treatment_organic_applied"],
        {"ab", "ba"},
        "treatment activation",
    )
    applied = {order: _strict_bool(applied[order], f"{order} treatment activation") for order in ORDERS}
    aggregate = aggregate_pairs(
        _strict_mapping(
            checked["pair_results"],
            {"ab", "ba"},
            "configuration pair results",
        )
    )
    secondary_bands = aggregate["pair_band_by_order"]
    assert isinstance(secondary_bands, Mapping)
    claim_gate_bands = {
        order: (
            PAIR_BENEFIT
            if primary_delta[order] == 1
            else (PAIR_REGRESSION if primary_delta[order] == -1 else secondary_bands[order])
        )
        for order in ORDERS
    }
    decision_tiers = {
        order: (
            "primary_incumbent_presence" if primary_delta[order] != 0 else "secondary_cumulative_deterministic_time"
        )
        for order in ORDERS
    }
    if set(claim_gate_bands.values()) == {PAIR_BENEFIT}:
        repeat_class = "REPEATED_BENEFIT"
    elif set(claim_gate_bands.values()) == {PAIR_NO_EFFECT}:
        repeat_class = "REPEATED_NO_EFFECT"
    elif set(claim_gate_bands.values()) == {PAIR_REGRESSION}:
        repeat_class = "REPEATED_REGRESSION"
    else:
        repeat_class = "INCONSISTENT_REPEATS"
    aggregate = {
        **aggregate,
        "claim_gate_pair_band_by_order": claim_gate_bands,
        "decision_tier_by_order": decision_tiers,
        "primary_delta_by_order": dict(primary_delta),
        "repeat_class": repeat_class,
    }
    if not same_manager_epoch or any(credibility[order] != CREDIBILITY_PASS for order in ORDERS):
        reasons = []
        if not same_manager_epoch:
            reasons.append("manager_epoch_mismatch")
        reasons.extend(
            f"{order}_pair_credibility_incomplete" for order in ORDERS if credibility[order] != CREDIBILITY_PASS
        )
        return {
            "configuration": configuration,
            "credibility_status": CREDIBILITY_INCOMPLETE,
            "outcome_class": None,
            "strongest_claim": None,
            "failure_reasons": reasons,
            "pair_aggregate": aggregate,
        }
    if repeat_class == "REPEATED_BENEFIT":
        if all(applied.values()):
            outcome = BUNDLE_RUNTIME_EFFECT if configuration == "bundle" else SINGLE_FAMILY_RUNTIME_EFFECT
            strongest_claim = outcome
        else:
            outcome = INCONSISTENT_FIXED_RUN_OBSERVATIONS
            strongest_claim = None
    elif repeat_class == "REPEATED_NO_EFFECT":
        outcome = FIXED_CONFIGURATION_NO_EFFECT
        strongest_claim = outcome
    elif repeat_class == "REPEATED_REGRESSION":
        outcome = FIXED_CONFIGURATION_REGRESSION
        strongest_claim = outcome
    elif repeat_class == "INCONSISTENT_REPEATS":
        outcome = INCONSISTENT_FIXED_RUN_OBSERVATIONS
        strongest_claim = None
    else:
        raise ContractError("pair aggregate repeat class is unsupported")
    return {
        "configuration": configuration,
        "credibility_status": CREDIBILITY_PASS,
        "outcome_class": outcome,
        "strongest_claim": strongest_claim,
        "failure_reasons": [],
        "pair_aggregate": aggregate,
    }


def suite_gate(record: Mapping[str, object]) -> dict[str, object]:
    """Replay all four configuration gates and the descriptive bundle diagnostic.

    This function does not read arm evidence.  Its caller must first obtain
    one credibility-PASS record per arm from the independent arm gate.  The
    exact four configuration inputs are replayed here so a terminal report
    cannot substitute an arithmetic mean for the conservative two-pair rule
    or silently omit a configuration.
    """

    checked = _strict_mapping(
        record,
        {"configuration_records"},
        "suite gate",
    )
    raw_configurations = _strict_mapping(
        checked["configuration_records"],
        set(CONFIGURATIONS),
        "suite configuration records",
    )
    configurations: dict[str, dict[str, object]] = {}
    benefit_inputs: dict[str, dict[str, int | float]] = {}
    incomplete: list[str] = []
    for configuration in CONFIGURATIONS:
        raw = raw_configurations[configuration]
        if type(raw) is not dict or raw.get("configuration") != configuration:
            raise ContractError(f"suite configuration identity drifted for {configuration}")
        replayed = configuration_gate(raw)
        configurations[configuration] = replayed
        if replayed["credibility_status"] != CREDIBILITY_PASS:
            incomplete.append(configuration)
        aggregate = replayed["pair_aggregate"]
        assert isinstance(aggregate, Mapping)
        benefits = aggregate["benefit_by_order"]
        assert isinstance(benefits, Mapping)
        benefit_inputs[configuration] = {
            "ab": _strict_number(
                benefits["ab"],
                f"{configuration}.ab benefit",
            ),
            "ba": _strict_number(
                benefits["ba"],
                f"{configuration}.ba benefit",
            ),
        }
    diagnostic = bundle_nonadditivity(benefit_inputs)
    credibility = CREDIBILITY_INCOMPLETE if incomplete else CREDIBILITY_PASS
    return {
        "authorizations": {
            "family_global_soundness_authorized": False,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "stage_b_promotion_authorized": False,
        },
        "bundle_nonadditivity_diagnostic": diagnostic,
        "configuration_results": configurations,
        "credibility_status": credibility,
        "incomplete_configurations": incomplete,
        "status": (SUITE_COMPLETE if credibility == CREDIBILITY_PASS else CREDIBILITY_INCOMPLETE),
    }


def new_consumption_state() -> dict[str, object]:
    """Return the retryable initial state for the fixed sixteen slots."""

    return {
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "schema": STATE_SCHEMA,
        "next_index": 0,
        "slots": [
            {
                "attempt_count": 0,
                "slot": slot,
                "state": "PENDING",
            }
            for slot in ARM_SEQUENCE
        ],
    }


def _validate_consumption_state(value: object) -> Mapping[str, Any]:
    state = _strict_mapping(
        value,
        {"authorizations", "schema", "next_index", "slots"},
        "consumption state",
    )
    if state["schema"] != STATE_SCHEMA:
        raise ContractError("consumption state schema drifted")
    authorizations = _strict_mapping(
        state["authorizations"],
        set(RESEARCH_ONLY_AUTHORIZATIONS),
        "consumption state authorizations",
    )
    if authorizations != RESEARCH_ONLY_AUTHORIZATIONS:
        raise ContractError("consumption state may not grant authority")
    next_index = _strict_nonnegative_int(state["next_index"], "next_index")
    if next_index > len(ARM_SEQUENCE):
        raise ContractError("next_index is out of range")
    slots = state["slots"]
    if type(slots) is not list or len(slots) != len(ARM_SEQUENCE):
        raise ContractError("consumption slot set drifted")
    allowed_states = {"PENDING", "ACTIVE", "RETRYABLE", "COMPLETE"}
    for index, expected_slot in enumerate(ARM_SEQUENCE):
        member = _strict_mapping(
            slots[index],
            {"attempt_count", "slot", "state"},
            f"consumption slot {index}",
        )
        attempt_count = _strict_nonnegative_int(
            member["attempt_count"],
            f"consumption slot {index} attempt_count",
        )
        if (
            member["slot"] != expected_slot
            or member["state"] not in allowed_states
            or (member["state"] == "PENDING") is not (attempt_count == 0)
        ):
            raise ContractError("consumption slot identity/state drifted")
    if any(slots[index]["state"] != "COMPLETE" for index in range(next_index)):
        raise ContractError("consumption state lacks a complete prefix")
    if next_index == len(ARM_SEQUENCE):
        if any(member["state"] != "COMPLETE" for member in slots):
            raise ContractError("completed consumption state drifted")
        return state
    current_state = slots[next_index]["state"]
    if current_state not in {"PENDING", "ACTIVE", "RETRYABLE"}:
        raise ContractError("current consumption slot has an invalid state")
    if any(
        member["state"] != "PENDING" or member["attempt_count"] != 0
        for member in slots[next_index + 1 :]
    ):
        raise ContractError("a future arm slot was consumed out of order")
    return state


def transition_consumption_state(
    state: Mapping[str, object],
    event: Mapping[str, object],
) -> dict[str, object]:
    """Apply one fail-closed slot transition without mutating the input state."""

    checked_state = _validate_consumption_state(state)
    checked_event = _strict_mapping(
        event,
        {"attempt_ordinal", "event", "slot", "reason"},
        "consumption event",
    )
    index = checked_state["next_index"]
    if index == len(ARM_SEQUENCE):
        raise ContractError("all arm slots are already complete")
    slot = checked_event["slot"]
    if slot != ARM_SEQUENCE[index]:
        raise ContractError("event does not target the next preregistered arm slot")
    event_name = checked_event["event"]
    reason = checked_event["reason"]
    if event_name not in {
        "PRESELECTION_FAILURE",
        "SELECTION_CREATED",
        "ARM_CREDIBILITY_PASS",
        "ARM_CREDIBILITY_INCOMPLETE",
    }:
        raise ContractError("consumption event is unsupported")
    attempt_ordinal = _strict_nonnegative_int(
        checked_event["attempt_ordinal"],
        "attempt_ordinal",
    )
    if attempt_ordinal == 0:
        raise ContractError("attempt_ordinal must be positive")
    current_member = checked_state["slots"][index]
    current = current_member["state"]
    attempt_count = current_member["attempt_count"]
    result = copy.deepcopy(dict(checked_state))
    result_member = result["slots"][index]
    if event_name == "PRESELECTION_FAILURE":
        _strict_nonempty_string(reason, "preselection failure reason")
        if current not in {"PENDING", "RETRYABLE"} or attempt_ordinal != attempt_count + 1:
            raise ContractError("preselection failure attempt order drifted")
        result_member["attempt_count"] = attempt_ordinal
        result_member["state"] = "RETRYABLE"
    elif event_name == "SELECTION_CREATED":
        if (
            reason is not None
            or current not in {"PENDING", "RETRYABLE"}
            or attempt_ordinal != attempt_count + 1
        ):
            raise ContractError("selection creation state drifted")
        result_member["attempt_count"] = attempt_ordinal
        result_member["state"] = "ACTIVE"
    elif event_name == "ARM_CREDIBILITY_PASS":
        if reason is not None or current != "ACTIVE" or attempt_ordinal != attempt_count:
            raise ContractError("credible arm completion lacks the active attempt")
        result_member["state"] = "COMPLETE"
        result["next_index"] = index + 1
    else:
        _strict_nonempty_string(reason, "arm credibility failure reason")
        if current != "ACTIVE" or attempt_ordinal != attempt_count:
            raise ContractError("incomplete arm lacks the active attempt")
        result_member["state"] = "RETRYABLE"
    _validate_consumption_state(result)
    return result
