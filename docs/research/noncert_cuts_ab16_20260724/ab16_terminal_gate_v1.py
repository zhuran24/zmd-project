#!/usr/bin/env python3
"""Credibility-first arm and terminal classification for the AB16 campaign.

This module is a pure gate: it starts no process, solver, systemd unit, or
experiment.  The campaign authority must first run the package-pinned
arithmetic and resource replay builders.  It then supplies both the immutable
receipts and the freshly replayed values here; byte-equal semantics are a
mandatory input to every non-incomplete arm result.

Passing this gate establishes only a credible observation for the fixed
campaign configuration.  It never establishes family-global soundness,
SAT/UNSAT, a project bound, a witness, Stage-B promotion, or production
``CERTIFIED`` status.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
import re
from typing import Any, Protocol


ARM_GATE_SCHEMA = "noncert-cuts-ab16-arm-credibility-gate-v1"
SUITE_GATE_SCHEMA = "noncert-cuts-ab16-terminal-classification-v1"
CONTROLLER_TERMINAL_SCHEMA = "noncert-cuts-ab16-controller-terminal-v1"
ARITHMETIC_SCHEMA = "noncert-cuts-ab16-independent-organic-arm-replay-v1"
ARITHMETIC_PURPOSE = "independent_organic_arm_event_and_arithmetic_replay"
RESOURCE_SCHEMA = "noncert-cuts-ab16-detached-resource-terminal-v1"
RESOURCE_PRETERMINAL_SCHEMA = "noncert-cuts-ab16-resource-verification-v1"
RESOURCE_PURPOSE = "PROSPECTIVE_AB16_ORGANIC_ARM_RESOURCE_AUTHORITY"

CREDIBILITY_PASS = "PASS"
CREDIBILITY_INCOMPLETE = "CREDIBILITY_INCOMPLETE"
BUDGET_CENSORED_UNKNOWN = "BUDGET_CENSORED_UNKNOWN"

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
    for order, ordered_arms in (
        ("ab", ("control", "treatment")),
        ("ba", ("treatment", "control")),
    )
    for arm in ordered_arms
)

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class GateError(ValueError):
    """A replayed receipt or terminal classification failed closed."""


class ContractModule(Protocol):
    """The package-pinned pure AB16 contract consumed by the suite gate."""

    CREDIBILITY_PASS: str

    def pair_delta(
        self,
        record: Mapping[str, object],
    ) -> dict[str, object]: ...

    def suite_gate(
        self,
        record: Mapping[str, object],
    ) -> dict[str, object]: ...


def _mapping(
    value: object,
    expected: set[str],
    label: str,
) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise GateError(f"{label} must have the exact key set")
    return value


def _identity(value: object, label: str) -> Mapping[str, Any]:
    record = _mapping(
        value,
        {"path", "sha256", "size_bytes"},
        label,
    )
    if (
        type(record["path"]) is not str
        or not record["path"].startswith("/")
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise GateError(f"{label} is not a detached byte identity")
    return record


def _number(value: object, label: str) -> int | float:
    if type(value) not in {int, float} or not math.isfinite(value):
        raise GateError(f"{label} must be a finite exact JSON number")
    return value


def _counter(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise GateError(f"{label} must be a nonnegative exact integer")
    return value


def _controller_terminal(
    value: object,
    *,
    experiment_contract: Mapping[str, Any],
    controller_proof_summary: Mapping[str, Any],
) -> dict[str, object]:
    """Independently replay the runner's budget-censor and metric arithmetic."""

    record = _mapping(
        value,
        {
            "budget_censor_evidence",
            "controller_completed",
            "controller_status",
            "cumulative_deterministic_time",
            "master_last_solve",
            "master_solve_history",
            "schema_version",
        },
        "controller terminal",
    )
    if (
        record["schema_version"] != CONTROLLER_TERMINAL_SCHEMA
        or record["controller_completed"] is not True
        or record["controller_status"] not in {"CERTIFIED", "INFEASIBLE", "UNKNOWN", "UNPROVEN"}
        or type(record["master_last_solve"]) is not dict
        or type(record["master_solve_history"]) is not list
    ):
        raise GateError("controller terminal scalar semantics drifted")
    budget_contract = experiment_contract.get("budget")
    if type(budget_contract) is not dict:
        raise GateError("experiment budget contract is absent")
    if type(controller_proof_summary) is not dict:
        raise GateError("controller proof summary is absent")

    history: list[dict[str, object]] = []
    cumulative = 0.0
    totals = {
        "binary_propagations": 0,
        "branches": 0,
        "conflicts": 0,
        "integer_propagations": 0,
    }
    for ordinal, raw in enumerate(
        record["master_solve_history"],
        start=1,
    ):
        item = _mapping(
            raw,
            {
                "binary_propagations",
                "branches",
                "conflicts",
                "deterministic_time",
                "integer_propagations",
                "ordinal",
                "requested_time_limit_seconds",
                "status",
                "user_time",
                "wall_time",
            },
            f"master solve history {ordinal}",
        )
        if (
            item["ordinal"] != ordinal
            or type(item["status"]) is not str
            or not item["status"]
            or _number(
                item["requested_time_limit_seconds"],
                "requested master time",
            )
            <= 0
        ):
            raise GateError("master solve history identity/status drifted")
        for field in totals:
            totals[field] += _counter(
                item[field],
                f"master solve {field}",
            )
        for field in ("deterministic_time", "user_time", "wall_time"):
            if _number(item[field], f"master solve {field}") < 0:
                raise GateError("master solve time is negative")
        cumulative += float(item["deterministic_time"])
        history.append(dict(item))
    reported_cumulative = _number(
        record["cumulative_deterministic_time"],
        "reported cumulative deterministic time",
    )
    if reported_cumulative < 0 or abs(cumulative - float(reported_cumulative)) > 1e-9:
        raise GateError("cumulative deterministic time replay failed")

    censor = _mapping(
        record["budget_censor_evidence"],
        {"internal_budget_reached", "kind", "limit", "observed"},
        "budget censor evidence",
    )
    internal = censor["internal_budget_reached"]
    if type(internal) is not bool:
        raise GateError("budget censor flag is not an exact boolean")
    controller_status = record["controller_status"]
    terminal_class: str | None
    failure_reasons: list[str] = []
    if not internal:
        if censor != {
            "internal_budget_reached": False,
            "kind": "none",
            "limit": None,
            "observed": {},
        }:
            raise GateError("non-censor evidence is not canonical")
        if controller_status in {"UNKNOWN", "UNPROVEN"}:
            terminal_class = None
            failure_reasons.append("controller_unknown_without_internal_budget_censor")
        else:
            terminal_class = f"CONTROLLER_{controller_status}_OBSERVATION"
    else:
        if controller_status not in {"UNKNOWN", "UNPROVEN"}:
            raise GateError("a certified/infeasible observation cannot be budget-censored")
        kind = censor["kind"]
        observed = censor["observed"]
        if type(observed) is not dict or not observed:
            raise GateError("budget censor observation is empty")
        expected_limit_name = {
            "binding_seconds": "binding_seconds",
            "master_seconds": "master_seconds",
            "max_iterations": "max_iterations",
            "routing_seconds": "routing_seconds",
        }.get(kind)
        if expected_limit_name is None:
            raise GateError("budget censor kind is unsupported")
        expected_limit = budget_contract.get(expected_limit_name)
        if type(expected_limit) not in {int, float} or censor["limit"] != expected_limit:
            raise GateError("budget censor limit differs from manifest")
        if kind == "max_iterations":
            expected_observed = {
                "benders_iterations": controller_proof_summary.get("benders_iterations"),
                "master_status": controller_proof_summary.get("master_status"),
            }
            if (
                expected_observed
                != {
                    "benders_iterations": expected_limit,
                    "master_status": "MAX_ITERATIONS",
                }
                or observed != expected_observed
            ):
                raise GateError("max-iterations censor evidence drifted")
        elif kind == "binding_seconds":
            expected_observed = {"binding_status": controller_proof_summary.get("binding_status")}
            if expected_observed != {"binding_status": "TIMEOUT"} or observed != expected_observed:
                raise GateError("binding censor evidence drifted")
        elif kind == "routing_seconds":
            expected_observed = {"routing_status": controller_proof_summary.get("routing_status")}
            if expected_observed != {"routing_status": "TIMEOUT"} or observed != expected_observed:
                raise GateError("routing censor evidence drifted")
        else:
            if not history:
                raise GateError("master-time censor lacks a master solve")
            last = history[-1]
            if (
                controller_proof_summary.get("master_status") != "UNKNOWN"
                or observed.get("master_status") != "UNKNOWN"
                or observed.get("solver_status") != "UNKNOWN"
                or observed.get("wall_time") != last["wall_time"]
                or last["status"] != "UNKNOWN"
                or last["requested_time_limit_seconds"] != expected_limit
                or float(last["wall_time"]) < float(expected_limit) * 0.99
            ):
                raise GateError("master-time censor evidence drifted")
        terminal_class = BUDGET_CENSORED_UNKNOWN

    return {
        "controller_status": controller_status,
        "credibility_status": (CREDIBILITY_INCOMPLETE if failure_reasons else CREDIBILITY_PASS),
        "failure_reasons": failure_reasons,
        "metrics": {
            "binary_propagations": totals["binary_propagations"],
            "branches": totals["branches"],
            "conflicts": totals["conflicts"],
            "cumulative_deterministic_time": cumulative,
            "integer_propagations": totals["integer_propagations"],
        },
        "solver_terminal_class": terminal_class,
    }


def build_arm_gate(
    *,
    selection: Mapping[str, Any],
    selection_identity: Mapping[str, Any],
    arm_result: Mapping[str, Any],
    arm_result_identity: Mapping[str, Any],
    arithmetic_receipt: Mapping[str, Any],
    arithmetic_receipt_identity: Mapping[str, Any],
    replayed_arithmetic_receipt: Mapping[str, Any],
    arithmetic_tool_identity: Mapping[str, Any],
    resource_receipt: Mapping[str, Any],
    resource_receipt_identity: Mapping[str, Any],
    replayed_resource_receipt: Mapping[str, Any],
    resource_preterminal_receipt: Mapping[str, Any],
    resource_preterminal_identity: Mapping[str, Any],
    replayed_resource_preterminal_receipt: Mapping[str, Any],
    resource_verifier_tool_identity: Mapping[str, Any],
    experiment_contract: Mapping[str, Any],
    gate_tool_identity: Mapping[str, Any],
) -> dict[str, object]:
    """Join one selected arm to two independently replayed PASS receipts."""

    selected_identity = dict(_identity(selection_identity, "selection identity"))
    result_identity = dict(_identity(arm_result_identity, "arm result identity"))
    arithmetic_identity = dict(
        _identity(
            arithmetic_receipt_identity,
            "arithmetic receipt identity",
        )
    )
    expected_arithmetic_tool = dict(
        _identity(
            arithmetic_tool_identity,
            "expected arithmetic replay tool identity",
        )
    )
    resource_identity = dict(
        _identity(
            resource_receipt_identity,
            "resource receipt identity",
        )
    )
    resource_preterminal_id = dict(
        _identity(
            resource_preterminal_identity,
            "resource preterminal identity",
        )
    )
    gate_identity = dict(_identity(gate_tool_identity, "arm gate tool identity"))
    expected_resource_tool = dict(
        _identity(
            resource_verifier_tool_identity,
            "expected resource verifier tool identity",
        )
    )
    if dict(arithmetic_receipt) != dict(replayed_arithmetic_receipt):
        raise GateError("arithmetic receipt differs from independent replay")
    if dict(resource_preterminal_receipt) != dict(replayed_resource_preterminal_receipt):
        raise GateError("preterminal resource receipt differs from independent replay")
    if dict(resource_receipt) != dict(replayed_resource_receipt):
        raise GateError("resource receipt differs from independent replay")

    slot = selection.get("slot")
    arm = selection.get("arm")
    result_authority = arm_result.get("authority_identities")
    if (
        type(slot) is not str
        or slot not in ARM_SEQUENCE
        or arm not in ARMS
        or type(result_authority) is not dict
        or selection.get("manifest_identity") != result_authority.get("manifest")
        or selected_identity != result_authority.get("selection")
        or arm_result.get("slot") != slot
        or arm_result.get("arm") != arm
        or arm_result.get("campaign_id") != selection.get("campaign_id")
        or arm_result.get("enabled_families") != selection.get("enabled_families")
        or arm_result.get("status") != "RAW_ARM_OBSERVATION_COMPLETE"
    ):
        raise GateError("arm result does not join its immutable selection")

    arithmetic = _mapping(
        arithmetic_receipt,
        {
            "applied_inequality_evaluations",
            "arm_incumbent_present",
            "arm_result_identity",
            "authorizations",
            "classification",
            "cut_activity",
            "cut_free_replay_identity",
            "cut_free_replay_status",
            "cut_free_replay_subject_identity",
            "enabled_families",
            "journal_identity",
            "ledger_identity",
            "lineage_summary",
            "manifest_identity",
            "purpose",
            "replay_tool_identity",
            "schema_version",
            "selection_identity",
            "slot",
            "status",
        },
        "arithmetic receipt",
    )
    arithmetic_authorizations = _mapping(
        arithmetic["authorizations"],
        {
            "family_global_soundness_authorized",
            "global_claim_authorized",
            "mathematical_claim_authorized",
            "production_certified_authorized",
            "runtime_effect_authorized",
        },
        "arithmetic authorizations",
    )
    arithmetic_required = {
        "arm_result_identity": result_identity,
        "enabled_families": selection.get("enabled_families"),
        "manifest_identity": selection.get("manifest_identity"),
        "selection_identity": selected_identity,
        "slot": slot,
    }
    if (
        arithmetic["schema_version"] != ARITHMETIC_SCHEMA
        or arithmetic["purpose"] != ARITHMETIC_PURPOSE
        or arithmetic["status"] != "PASS"
        or arithmetic["cut_free_replay_status"] != "PASS"
        or arithmetic["replay_tool_identity"] != expected_arithmetic_tool
        or type(arithmetic["arm_incumbent_present"]) is not bool
        or type(arithmetic["applied_inequality_evaluations"]) is not list
        or type(arithmetic["lineage_summary"]) is not dict
        or any(value is not False for value in arithmetic_authorizations.values())
        or any(arithmetic.get(field) != expected for field, expected in arithmetic_required.items())
    ):
        raise GateError("arithmetic receipt selection/result join failed")
    for field in (
        "cut_free_replay_identity",
        "cut_free_replay_subject_identity",
        "journal_identity",
        "ledger_identity",
    ):
        _identity(arithmetic[field], f"arithmetic {field}")
    activity = _mapping(
        arithmetic["cut_activity"],
        {"applied", "compiled", "generated"},
        "arithmetic cut activity",
    )
    generated = _counter(activity["generated"], "generated")
    compiled = _counter(activity["compiled"], "compiled")
    applied = _counter(activity["applied"], "applied")
    if not 0 <= applied <= compiled <= generated:
        raise GateError("arithmetic cut counts are non-monotone")
    expected_activation = (
        "ORGANIC_NONACTIVATION" if generated == 0 else ("NO_ORGANIC_APPLIED_CUT" if applied == 0 else "ORGANIC_APPLIED")
    )
    if arithmetic["classification"] != expected_activation:
        raise GateError("arithmetic activation classification drifted")
    evaluations = arithmetic["applied_inequality_evaluations"]
    if len(evaluations) != applied or any(
        type(evaluation) is not dict or evaluation.get("active") is not True or evaluation.get("violated") is not True
        for evaluation in evaluations
    ):
        raise GateError("arithmetic APPLIED evaluation coverage drifted")

    preterminal_resource = _mapping(
        resource_preterminal_receipt,
        {
            "authorizations",
            "derived",
            "inner_identity",
            "pre_run_authority_identity",
            "preterminal_identity",
            "payload_result_identity",
            "purpose",
            "runner_selection_identity",
            "schema_version",
            "slot",
            "status",
            "verdict",
            "verifier_tool_identity",
        },
        "preterminal resource receipt",
    )
    detached_resource = _mapping(
        resource_receipt,
        {
            "authorizations",
            "cleanup_identity",
            "derived",
            "detached_epoch_observation_identity",
            "inner_identity",
            "pre_run_authority_identity",
            "preterminal_identity",
            "purpose",
            "release_identity",
            "resource_verification_identity",
            "runner_selection_identity",
            "schema_version",
            "slot",
            "status",
            "terminal_identity",
            "verdict",
            "verifier_tool_identity",
        },
        "detached resource receipt",
    )
    preterminal_authorizations = _mapping(
        preterminal_resource["authorizations"],
        {
            "global_claim_authorized",
            "mathematical_claim_authorized",
            "production_certified_authorized",
            "release_keeper_authorized",
        },
        "preterminal resource authorizations",
    )
    detached_authorizations = _mapping(
        detached_resource["authorizations"],
        {
            "family_global_soundness_authorized",
            "global_claim_authorized",
            "mathematical_claim_authorized",
            "production_certified_authorized",
            "stage_b_promotion_authorized",
        },
        "detached resource authorizations",
    )
    if (
        preterminal_resource["schema_version"] != RESOURCE_PRETERMINAL_SCHEMA
        or preterminal_resource["purpose"] != RESOURCE_PURPOSE
        or preterminal_resource["status"] != "PASS"
        or preterminal_resource["verdict"] != "RESOURCE_PRETERMINAL_PASS"
        or preterminal_resource["slot"] != slot
        or preterminal_resource["runner_selection_identity"] != selected_identity
        or preterminal_resource["payload_result_identity"] != result_identity
        or preterminal_resource["verifier_tool_identity"] != expected_resource_tool
        or preterminal_authorizations
        != {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "release_keeper_authorized": True,
        }
        or detached_resource["schema_version"] != RESOURCE_SCHEMA
        or detached_resource["purpose"] != RESOURCE_PURPOSE
        or detached_resource["status"] != "PASS"
        or detached_resource["verdict"] != "RESOURCE_TERMINAL_CLEANUP_REPLAY_PASS"
        or detached_resource["slot"] != slot
        or detached_resource["runner_selection_identity"] != selected_identity
        or detached_resource["resource_verification_identity"] != resource_preterminal_id
        or detached_resource["pre_run_authority_identity"] != preterminal_resource["pre_run_authority_identity"]
        or detached_resource["inner_identity"] != preterminal_resource["inner_identity"]
        or detached_resource["preterminal_identity"] != preterminal_resource["preterminal_identity"]
        or detached_resource["verifier_tool_identity"] != preterminal_resource["verifier_tool_identity"]
        or detached_resource["derived"] != preterminal_resource["derived"]
        or any(value is not False for value in detached_authorizations.values())
    ):
        raise GateError("resource/terminal/result identity chain failed")
    for field in (
        "inner_identity",
        "pre_run_authority_identity",
        "preterminal_identity",
        "verifier_tool_identity",
    ):
        _identity(preterminal_resource[field], f"preterminal resource {field}")
    for field in (
        "cleanup_identity",
        "detached_epoch_observation_identity",
        "release_identity",
        "terminal_identity",
    ):
        _identity(detached_resource[field], f"detached resource {field}")

    proof = arm_result.get("raw_proof_summary")
    raw_terminal = arm_result.get("controller_terminal")
    if (
        type(proof) is not dict
        or type(raw_terminal) is not dict
        or type(proof.get("controller_last_proof_summary")) is not dict
        or proof.get("master_last_solve") != raw_terminal.get("master_last_solve")
    ):
        raise GateError("controller proof/last-solve join failed")
    terminal = _controller_terminal(
        raw_terminal,
        experiment_contract=experiment_contract,
        controller_proof_summary=proof["controller_last_proof_summary"],
    )
    if terminal["credibility_status"] != CREDIBILITY_PASS:
        raise GateError(";".join(terminal["failure_reasons"]))
    return {
        "activation_class": expected_activation,
        "arm_incumbent_present": arithmetic["arm_incumbent_present"],
        "arithmetic_receipt_identity": arithmetic_identity,
        "arm": arm,
        "arm_result_identity": result_identity,
        "authorizations": {
            "family_global_soundness_authorized": False,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "runtime_effect_authorized": False,
            "stage_b_promotion_authorized": False,
        },
        "credibility_status": CREDIBILITY_PASS,
        "cut_activity": {
            "applied": applied,
            "compiled": compiled,
            "generated": generated,
        },
        "cut_free_incumbent_verified": True,
        "enabled_families": list(selection.get("enabled_families", [])),
        "gate_tool_identity": gate_identity,
        "manifest_identity": selection.get("manifest_identity"),
        "metrics": terminal["metrics"],
        "resource_receipt_identity": resource_identity,
        "resource_preterminal_identity": resource_preterminal_id,
        "schema_version": ARM_GATE_SCHEMA,
        "selection_identity": selected_identity,
        "slot": slot,
        "solver_terminal_class": terminal["solver_terminal_class"],
        "status": "PASS",
    }


def build_suite_gate(
    *,
    arm_gates: Sequence[Mapping[str, Any]],
    contract: ContractModule,
) -> dict[str, object]:
    """Classify all 16 credible arms using the package-pinned pure contract."""

    if type(arm_gates) is not list or len(arm_gates) != len(ARM_SEQUENCE):
        raise GateError("terminal suite requires exactly 16 arm gates")
    by_slot: dict[str, Mapping[str, Any]] = {}
    common_manifest_identity: Mapping[str, Any] | None = None
    common_gate_tool_identity: Mapping[str, Any] | None = None
    for expected_slot, raw_arm_gate in zip(
        ARM_SEQUENCE,
        arm_gates,
        strict=True,
    ):
        arm_gate = _mapping(
            raw_arm_gate,
            {
                "activation_class",
                "arithmetic_receipt_identity",
                "arm",
                "arm_incumbent_present",
                "arm_result_identity",
                "authorizations",
                "credibility_status",
                "cut_activity",
                "cut_free_incumbent_verified",
                "enabled_families",
                "gate_tool_identity",
                "manifest_identity",
                "metrics",
                "resource_preterminal_identity",
                "resource_receipt_identity",
                "schema_version",
                "selection_identity",
                "slot",
                "solver_terminal_class",
                "status",
            },
            f"{expected_slot} arm gate",
        )
        authorizations = _mapping(
            arm_gate["authorizations"],
            {
                "family_global_soundness_authorized",
                "global_claim_authorized",
                "mathematical_claim_authorized",
                "production_certified_authorized",
                "runtime_effect_authorized",
                "stage_b_promotion_authorized",
            },
            f"{expected_slot} arm gate authorizations",
        )
        metrics = _mapping(
            arm_gate["metrics"],
            {
                "binary_propagations",
                "branches",
                "conflicts",
                "cumulative_deterministic_time",
                "integer_propagations",
            },
            f"{expected_slot} arm gate metrics",
        )
        expected_configuration, _expected_order, expected_arm = expected_slot.rsplit("-", 2)
        expected_families = (
            []
            if expected_arm == "control"
            else {
                "region-capacity": ["region_capacity"],
                "shape-packing-hall": ["shape_packing_hall"],
                "power-hitting-set": ["power_hitting_set"],
                "bundle": [
                    "region_capacity",
                    "shape_packing_hall",
                    "power_hitting_set",
                ],
            }[expected_configuration]
        )
        if (
            arm_gate["schema_version"] != ARM_GATE_SCHEMA
            or arm_gate.get("status") != "PASS"
            or arm_gate.get("credibility_status") != CREDIBILITY_PASS
            or arm_gate.get("slot") != expected_slot
            or arm_gate["arm"] != expected_arm
            or arm_gate["enabled_families"] != expected_families
            or type(arm_gate["arm_incumbent_present"]) is not bool
            or arm_gate["cut_free_incumbent_verified"] is not True
            or any(value is not False for value in authorizations.values())
            or _number(
                metrics["cumulative_deterministic_time"],
                f"{expected_slot} cumulative deterministic time",
            )
            < 0
            or any(
                _counter(metrics[field], f"{expected_slot} {field}") < 0
                for field in (
                    "binary_propagations",
                    "branches",
                    "conflicts",
                    "integer_propagations",
                )
            )
            or expected_slot in by_slot
        ):
            raise GateError("terminal suite contains an invalid/out-of-order arm gate")
        manifest_identity = _identity(
            arm_gate.get("manifest_identity"),
            f"{expected_slot} manifest identity",
        )
        gate_tool_identity = _identity(
            arm_gate.get("gate_tool_identity"),
            f"{expected_slot} gate tool identity",
        )
        if common_manifest_identity is None:
            common_manifest_identity = manifest_identity
            common_gate_tool_identity = gate_tool_identity
        elif manifest_identity != common_manifest_identity or gate_tool_identity != common_gate_tool_identity:
            raise GateError("terminal suite crosses a manifest or gate-tool identity")
        by_slot[expected_slot] = arm_gate

    configuration_records: dict[str, dict[str, object]] = {}
    for configuration in CONFIGURATIONS:
        pair_results: dict[str, dict[str, object]] = {}
        primary_delta_by_order: dict[str, int] = {}
        treatment_applied: dict[str, bool] = {}
        for order in ORDERS:
            control = by_slot[f"{configuration}-{order}-control"]
            treatment = by_slot[f"{configuration}-{order}-treatment"]
            control_metric = _number(
                control["metrics"]["cumulative_deterministic_time"],
                "control deterministic time",
            )
            treatment_metric = _number(
                treatment["metrics"]["cumulative_deterministic_time"],
                "treatment deterministic time",
            )
            threshold = max(0.000001, abs(float(control_metric)) * 0.01)
            pair_results[order] = contract.pair_delta(
                {
                    "control": control_metric,
                    "direction": "lower_is_better",
                    "threshold": threshold,
                    "threshold_rule": "at_least",
                    "treatment": treatment_metric,
                }
            )
            treatment_applied[order] = treatment["activation_class"] == "ORGANIC_APPLIED"
            primary_delta_by_order[order] = int(treatment["arm_incumbent_present"]) - int(
                control["arm_incumbent_present"]
            )
        configuration_records[configuration] = {
            "configuration": configuration,
            "pair_credibility": {
                "ab": CREDIBILITY_PASS,
                "ba": CREDIBILITY_PASS,
            },
            "pair_results": pair_results,
            "primary_delta_by_order": primary_delta_by_order,
            "same_manager_epoch": True,
            "treatment_organic_applied": treatment_applied,
        }
    replayed = contract.suite_gate({"configuration_records": configuration_records})
    if replayed.get("credibility_status") != contract.CREDIBILITY_PASS:
        raise GateError("pure suite contract did not admit all configurations")
    return {
        "arm_gate_slots": list(ARM_SEQUENCE),
        "authorizations": dict(replayed["authorizations"]),
        "bundle_nonadditivity_diagnostic": replayed["bundle_nonadditivity_diagnostic"],
        "configuration_results": replayed["configuration_results"],
        "credibility_status": CREDIBILITY_PASS,
        "gate_tool_identity": dict(common_gate_tool_identity or {}),
        "manifest_identity": dict(common_manifest_identity or {}),
        "schema_version": SUITE_GATE_SCHEMA,
        "status": "AB16_FIXED_CONFIGURATION_SUITE_COMPLETE",
    }
