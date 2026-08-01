#!/usr/bin/env python3
"""Prospective AB16 arm credibility and terminal classification gate.

This is a separately package-pinned v3 gate, not a schema alias for the
historical v2 gate.  It closes the prospective selection/result/budget
authority cohort before reusing the stable pure controller and pair arithmetic
from v2.  Every legacy-normalized input is constructed only after the v3
cohort has been accepted, and every published result is rebuilt as v3.

The result is research telemetry for the fixed 16-arm campaign only.  It does
not authorize a witness, cut, bound, production decision, certified result,
family-global soundness claim, or Stage-B promotion.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any, Protocol

from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_terminal_gate_v2 as _legacy,
)


ARM_GATE_SCHEMA = "noncert-cuts-ab16-arm-credibility-gate-v3"
SUITE_GATE_SCHEMA = "noncert-cuts-ab16-terminal-classification-v3"
SELECTION_SCHEMA = "noncert-cuts-ab16-organic-arm-selection-v2"
RESULT_SCHEMA = "noncert-cuts-ab16-organic-arm-result-v2"
ARITHMETIC_SCHEMA = "noncert-cuts-ab16-independent-organic-arm-replay-v2"
RESOURCE_SCHEMA = "noncert-cuts-ab16-detached-resource-terminal-v3"
RESOURCE_PRETERMINAL_SCHEMA = "noncert-cuts-ab16-resource-verification-v2"
CONTROLLER_TERMINAL_SCHEMA = "noncert-cuts-ab16-controller-terminal-v1"
ARITHMETIC_PURPOSE = "independent_organic_arm_event_and_arithmetic_replay"
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
    """A prospective receipt or terminal classification failed closed."""


class ContractModule(Protocol):
    """Package-pinned pure contract consumed by the suite gate."""

    CREDIBILITY_PASS: str

    def pair_delta(
        self,
        record: Mapping[str, object],
    ) -> dict[str, object]: ...

    def suite_gate(
        self,
        record: Mapping[str, object],
    ) -> dict[str, object]: ...


def _exact_mapping(
    value: object,
    expected: set[str],
    label: str,
) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise GateError(f"{label} must have the exact key set")
    return value


def _identity(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) not in (
        {"path", "sha256", "size_bytes"},
        {"mode", "path", "sha256", "size_bytes"},
    ):
        raise GateError(f"{label} must have one detached identity key set")
    record = value
    if (
        ("mode" in record and (type(record["mode"]) is not int or record["mode"] < 0))
        or type(record["path"]) is not str
        or not record["path"].startswith("/")
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise GateError(f"{label} is not a detached byte identity")
    return dict(record)


def _budget_binding(
    *,
    selection: Mapping[str, Any],
    arm_result: Mapping[str, Any],
    arithmetic_receipt: Mapping[str, Any],
) -> dict[str, object]:
    if selection.get("schema_version") != SELECTION_SCHEMA:
        raise GateError("prospective selection schema drifted")
    if arm_result.get("schema_version") != RESULT_SCHEMA:
        raise GateError("prospective arm-result schema drifted")
    if arithmetic_receipt.get("schema_version") != ARITHMETIC_SCHEMA:
        raise GateError("prospective arithmetic replay schema drifted")

    handoff = _exact_mapping(
        selection.get("budget_handoff"),
        {
            "arm_allocation_id",
            "broker_actor_identity",
            "broker_nonce",
            "broker_socket_path",
            "fixed_directory_layout",
            "fixed_maxima",
            "formal_budget_authority_identity",
            "native_helper_package_identity",
        },
        "selection budget handoff",
    )
    actor = _exact_mapping(
        handoff["broker_actor_identity"],
        {"pid", "pid_starttime", "uid"},
        "selection budget broker actor",
    )
    if any(type(actor[field]) is not int or actor[field] < 0 for field in actor):
        raise GateError("selection budget broker actor is invalid")
    allocation_id = handoff["arm_allocation_id"]
    broker_nonce = handoff["broker_nonce"]
    if (
        type(allocation_id) is not str
        or SHA256_RE.fullmatch(allocation_id) is None
        or type(broker_nonce) is not str
        or not broker_nonce
        or type(handoff["broker_socket_path"]) is not str
        or not handoff["broker_socket_path"].startswith("/")
        or type(handoff["fixed_directory_layout"]) is not dict
        or type(handoff["fixed_maxima"]) is not dict
        or not handoff["fixed_maxima"]
    ):
        raise GateError("selection budget handoff scalar semantics drifted")
    formal_identity = _identity(
        handoff["formal_budget_authority_identity"],
        "selection formal budget authority",
    )
    _identity(
        handoff["native_helper_package_identity"],
        "selection native helper package",
    )

    binding = _exact_mapping(
        arm_result.get("budget_authority_binding"),
        {
            "arm_allocation_id",
            "arm_slot",
            "broker_nonce",
            "broker_socket_fd",
            "filesystem_write_confinement",
            "formal_budget_authority_identity",
            "next_sequence",
        },
        "arm-result budget authority binding",
    )
    arithmetic_binding = _exact_mapping(
        arithmetic_receipt.get("budget_authority_binding"),
        set(binding),
        "arithmetic budget authority binding",
    )
    if dict(arithmetic_binding) != dict(binding):
        raise GateError("arithmetic/result budget authority binding drifted")
    if (
        binding["arm_allocation_id"] != allocation_id
        or binding["arm_slot"] != selection.get("slot")
        or binding["broker_nonce"] != broker_nonce
        or binding["formal_budget_authority_identity"] != formal_identity
        or type(binding["broker_socket_fd"]) is not int
        or binding["broker_socket_fd"] < 0
        or binding["filesystem_write_confinement"]
        != "landlock-read-only-worker-v1"
        or type(binding["next_sequence"]) is not int
        or binding["next_sequence"] <= 0
    ):
        raise GateError("selection/result budget authority join failed")
    return dict(binding)


def _legacy_arithmetic(value: Mapping[str, Any]) -> dict[str, object]:
    normalized = dict(value)
    normalized.pop("budget_authority_binding", None)
    normalized["schema_version"] = _legacy.ARITHMETIC_SCHEMA
    return normalized


def _legacy_resource(value: Mapping[str, Any]) -> dict[str, object]:
    normalized = dict(value)
    normalized["schema_version"] = _legacy.RESOURCE_SCHEMA
    return normalized


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
    """Join one prospective arm to its exact budget and replay cohort."""

    if dict(arithmetic_receipt) != dict(replayed_arithmetic_receipt):
        raise GateError("arithmetic receipt differs from independent replay")
    if dict(resource_receipt) != dict(replayed_resource_receipt):
        raise GateError("resource receipt differs from independent replay")
    if dict(resource_preterminal_receipt) != dict(
        replayed_resource_preterminal_receipt
    ):
        raise GateError(
            "preterminal resource receipt differs from independent replay"
        )
    if (
        resource_receipt.get("schema_version") != RESOURCE_SCHEMA
        or resource_preterminal_receipt.get("schema_version")
        != RESOURCE_PRETERMINAL_SCHEMA
    ):
        raise GateError("prospective resource replay cohort drifted")
    binding = _budget_binding(
        selection=selection,
        arm_result=arm_result,
        arithmetic_receipt=arithmetic_receipt,
    )

    try:
        replayed = _legacy.build_arm_gate(
            selection=selection,
            selection_identity=selection_identity,
            arm_result=arm_result,
            arm_result_identity=arm_result_identity,
            arithmetic_receipt=_legacy_arithmetic(arithmetic_receipt),
            arithmetic_receipt_identity=arithmetic_receipt_identity,
            replayed_arithmetic_receipt=_legacy_arithmetic(
                replayed_arithmetic_receipt
            ),
            arithmetic_tool_identity=arithmetic_tool_identity,
            resource_receipt=_legacy_resource(resource_receipt),
            resource_receipt_identity=resource_receipt_identity,
            replayed_resource_receipt=_legacy_resource(
                replayed_resource_receipt
            ),
            resource_preterminal_receipt=resource_preterminal_receipt,
            resource_preterminal_identity=resource_preterminal_identity,
            replayed_resource_preterminal_receipt=(
                replayed_resource_preterminal_receipt
            ),
            resource_verifier_tool_identity=resource_verifier_tool_identity,
            experiment_contract=experiment_contract,
            gate_tool_identity=gate_tool_identity,
        )
    except _legacy.GateError as exc:
        raise GateError(str(exc)) from exc
    if replayed.get("schema_version") != _legacy.ARM_GATE_SCHEMA:
        raise GateError("legacy pure gate returned an unexpected schema")
    result = dict(replayed)
    result["budget_authority_binding"] = binding
    result["schema_version"] = ARM_GATE_SCHEMA
    return result


def build_suite_gate(
    *,
    arm_gates: Sequence[Mapping[str, Any]],
    contract: ContractModule,
) -> dict[str, object]:
    """Classify all 16 prospective arms under one formal-root authority."""

    if type(arm_gates) is not list or len(arm_gates) != len(ARM_SEQUENCE):
        raise GateError("terminal suite requires exactly 16 arm gates")
    normalized: list[dict[str, object]] = []
    allocations: dict[str, str] = {}
    common_formal_identity: dict[str, object] | None = None
    expected_fields = {
        "activation_class",
        "arithmetic_receipt_identity",
        "arm",
        "arm_incumbent_present",
        "arm_result_identity",
        "authorizations",
        "budget_authority_binding",
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
    }
    for expected_slot, raw_gate in zip(ARM_SEQUENCE, arm_gates, strict=True):
        gate = _exact_mapping(
            raw_gate,
            expected_fields,
            f"{expected_slot} prospective arm gate",
        )
        if (
            gate["schema_version"] != ARM_GATE_SCHEMA
            or gate["slot"] != expected_slot
        ):
            raise GateError("prospective arm gate schema/order drifted")
        binding = _exact_mapping(
            gate["budget_authority_binding"],
            {
                "arm_allocation_id",
                "arm_slot",
                "broker_nonce",
                "broker_socket_fd",
                "filesystem_write_confinement",
                "formal_budget_authority_identity",
                "next_sequence",
            },
            f"{expected_slot} budget binding",
        )
        allocation_id = binding["arm_allocation_id"]
        if (
            binding["arm_slot"] != expected_slot
            or type(allocation_id) is not str
            or SHA256_RE.fullmatch(allocation_id) is None
            or allocation_id in allocations.values()
        ):
            raise GateError("prospective arm allocation identity drifted/reused")
        formal_identity = _identity(
            binding["formal_budget_authority_identity"],
            f"{expected_slot} formal budget authority",
        )
        if common_formal_identity is None:
            common_formal_identity = formal_identity
        elif formal_identity != common_formal_identity:
            raise GateError("terminal suite crosses a formal budget authority")
        allocations[expected_slot] = allocation_id
        legacy_gate = dict(gate)
        legacy_gate.pop("budget_authority_binding")
        legacy_gate["schema_version"] = _legacy.ARM_GATE_SCHEMA
        normalized.append(legacy_gate)
    try:
        replayed = _legacy.build_suite_gate(
            arm_gates=normalized,
            contract=contract,
        )
    except _legacy.GateError as exc:
        raise GateError(str(exc)) from exc
    if replayed.get("schema_version") != _legacy.SUITE_GATE_SCHEMA:
        raise GateError("legacy pure suite gate returned an unexpected schema")
    result = dict(replayed)
    result["arm_allocation_ids"] = allocations
    result["formal_budget_authority_identity"] = dict(
        common_formal_identity or {}
    )
    result["schema_version"] = SUITE_GATE_SCHEMA
    return result
