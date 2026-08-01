#!/usr/bin/env python3
"""Independent detached verifier for one terminal formal AB16 campaign.

This role consumes, but never constructs, the controller, outer lifecycle,
RefUnit, child cleanup, and guardian receipts while the exact supervisor locks
remain held.  It independently replays either the complete substantive success
chain or one permanent consumed-incomplete chain.  Only after those joins
succeed does it publish one O_EXCL 0444 pre-release receipt; a separate
terminal join must bind the later exact lock-release effect.

The verifier intentionally does not import the formal supervisor, controller,
outer receipt producer, or guardian runtime.  It reuses only the closeout
state owner's pure schema/structural validators; it never calls that owner's
effect, construction, or publication functions.  The normal-success schemas
and their pure validators live here so producers may validate proposed bytes
before publication without gaining access to final closeout publication.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, cast

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_launch_validator_v1 as launch_validator,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_outer_closeout_state_v1 as closeout_state,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_resource_admission_v1 as resource_admission,
)


AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
SUCCESS_RECEIPT_SCHEMA = "noncert-cuts-ab16-formal-pre-release-success-v3"
INCOMPLETE_RECEIPT_SCHEMA = "noncert-cuts-ab16-formal-detached-incomplete-v4"
FAILURE_RELEASE_SCHEMA = "noncert-cuts-ab16-formal-pre-release-failure-v4"
FAILURE_TERMINAL_RELEASE_SCHEMA = (
    "noncert-cuts-ab16-formal-failure-terminal-release-v5"
)
CONTAINMENT_GUARDIAN_ABSENCE_SCHEMA = (
    "noncert-cuts-ab16-containment-guardian-absence-v1"
)
CONTROLLER_RESULT_SCHEMA = "noncert-cuts-ab16-formal-controller-result-v3"
CONTROLLER_RESULT_NAME = "controller-result.json"
CHILD_AUDIT_SCHEMA = "noncert-cuts-ab16-formal-child-audit-v1"
GATE1_OWNERSHIP_SCHEMA = "noncert-cuts-ab16-formal-gate1-prelaunch-ownership-v1"
ARM_PRELAUNCH_SCHEMA = "noncert-cuts-ab16-formal-arm-prelaunch-v3"
GUARDIAN_LOCK_CLOSE_SCHEMA = "noncert-cuts-ab16-outer-guardian-lock-close-v2"
OUTER_PRELAUNCH_SCHEMA = "noncert-cuts-ab16-outer-formal-prelaunch-v3"
OUTER_START_SCHEMA = "noncert-cuts-ab16-outer-formal-start-v3"
FORMAL_CONTAINMENT_SCHEMA = "noncert-cuts-ab16-formal-containment-v2"
GUARDIAN_ABSENCE_SCHEMA = "noncert-cuts-ab16-formal-guardian-absence-v2"
DUAL_LOCK_RELEASE_SCHEMA = "noncert-cuts-ab16-formal-dual-lock-release-v4"
POST_ROOT_CLOSURE_EVIDENCE_SCHEMA = (
    "noncert-cuts-ab16-post-root-closure-evidence-v1"
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
UNIT_RE = re.compile(r"[A-Za-z0-9_.@:-]+\.service\Z")
INVOCATION_RE = re.compile(r"[0-9a-f]{32}\Z")
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,1023}\Z")

ARM_SEQUENCE = tuple(closeout_state.ARM_SEQUENCE)
GATE1_SLOTS = (
    "q-success",
    "q-postseal-fail",
    "forced-control",
    "forced-treatment",
)
EXPECTED_CHILD_ORDER = (
    *(("gate1", slot) for slot in GATE1_SLOTS),
    *(("arm", slot) for slot in ARM_SEQUENCE),
)
PRE_RELEASE_PHASES = (
    "outer_prelaunch",
    "outer_start",
    "outer_resource",
    "reference_acquisition",
    "outer_terminal",
    "observer",
    "pre_unref_cleanup",
)
FALSE_AUTHORIZATIONS = dict(launch_validator.FALSE_CLAIMS)
REFERENCE_FALSE_AUTHORIZATIONS = dict(closeout_state.FALSE_AUTHORIZATIONS)
ABSENT_SYSTEMD = {
    "ActiveState": "inactive",
    "ControlGroup": "",
    "InvocationID": "",
    "LoadState": "not-found",
    "MainPID": "0",
    "SubState": "dead",
}
ABSENCE_RECORD_FIELDS = frozenset(
    {
        "cgroup_absent",
        "control_group",
        "identity_complete",
        "processes",
        "processes_absent",
        "slot",
        "source",
        "systemctl",
        "unit_absent",
        "unit_name",
    }
)

COMMON_RECEIPT_FIELDS = frozenset(
    {
        "authority_scope",
        "authorizations",
        "campaign_root_identity",
        "created_at_utc",
        "formal_selection_identity",
        "manager_epoch",
        "package_id",
        "schema_version",
        "status",
    }
)
PHASE_PAYLOAD_FIELDS: dict[str, frozenset[str]] = {
    "outer_prelaunch": frozenset(
        {"outer_identity", "prelaunch_absence", "resource_admission"}
    ),
    "outer_start": frozenset(
        {"launch_effect", "outer_identity", "resource_admission"}
    ),
    "outer_resource": frozenset({"cgroup_limits", "outer_identity", "systemd_properties"}),
    "outer_terminal": frozenset({"outer_identity", "stable_terminal"}),
    "observer": frozenset({"heavy_absence", "outer_identity"}),
    "pre_unref_cleanup": frozenset(
        {
            "child_audit_identity",
            "heavy_absence",
            "observer_identity",
            "outer_cleanup",
            "outer_identity",
        }
    ),
    "post_unref_absence": frozenset(
        {"cgroup_absent", "load_state", "outer_identity", "pid_absent"}
    ),
    "guardian_absence": frozenset(
        {
            "cgroup_absent",
            "detached_success_identity",
            "guardian_close_identity",
            "guardian_identity",
            "pid_absent",
            "pre_unref_cleanup_identity",
            "systemctl",
            "unit_absent",
        }
    ),
    "supervisor_raw_lock_release": frozenset(
        {
            "detached_substantive_identity",
            "detached_substantive_kind",
            "failure_pre_release_identity",
            "guardian_absence_identity",
            "guardian_close_identity",
            "lock_identities",
            "outcome",
            "supervisor_release",
        }
    ),
    "dual_lock_release": frozenset(
        {
            "detached_success_identity",
            "guardian_absence_identity",
            "guardian_close_identity",
            "lock_identities",
            "post_unref_absence_identity",
            "post_root_closure",
            "reference_connection_close_identity",
            "reference_release_identity",
            "reference_terminal_identity",
            "supervisor_raw_lock_release_identity",
            "terminal_join",
        }
    ),
}
PHASE_SCHEMAS = {
    phase: f"noncert-cuts-ab16-formal-{phase.replace('_', '-')}-v1"
    for phase in PHASE_PAYLOAD_FIELDS
}
PHASE_SCHEMAS["dual_lock_release"] = (
    DUAL_LOCK_RELEASE_SCHEMA
)
PHASE_SCHEMAS["guardian_absence"] = (
    GUARDIAN_ABSENCE_SCHEMA
)
PHASE_SCHEMAS["supervisor_raw_lock_release"] = (
    closeout_state.SUPERVISOR_RAW_LOCK_RELEASE_SCHEMA
)
PHASE_SCHEMAS["outer_prelaunch"] = OUTER_PRELAUNCH_SCHEMA
PHASE_SCHEMAS["outer_start"] = OUTER_START_SCHEMA

CONTROLLER_RESULT_FIELDS = frozenset(
    {
        "arm_results",
        "authority_scope",
        "authorizations",
        "barrier_identity",
        "baseline",
        "campaign_root_identity",
        "formal_selection_identity",
        "gate1",
        "manifest_identity",
        "package_id",
        "schema_version",
        "status",
        "suite_selection_identity",
        "terminal_classification_identity",
    }
)
BASELINE_FIELDS = frozenset(
    {
        "admission_identity",
        "fixed_replay_identity",
        "incumbent_identity",
        "metadata_identity",
        "model_identity",
        "provenance_identity",
    }
)
ARM_RESULT_FIELDS = frozenset(
    {
        "arm_gate_identity",
        "consumption_identity",
        "ordinal",
        "pre_run_authority_identity",
        "prelaunch_receipt_identity",
        "prelaunch_request_identity",
        "resource_admission",
        "resource_terminal_identity",
        "selection_identity",
        "slot",
        "suite_terminal_identity",
    }
)
FAILURE_RELEASE_FIELDS = frozenset(
    {
        "attempt_directory_created",
        "attempt_marker_identity",
        "authority_scope",
        "authorizations",
        "b6_changed",
        "bounds_changed",
        "campaign_root_identity",
        "cleanup_evidence",
        "created_at_utc",
        "detached_success_output_identity",
        "formal_selection_identity",
        "incomplete_identity",
        "lock_identities",
        "lock_lifecycle",
        "lower_bound",
        "outcome",
        "package_id",
        "phase",
        "production_authority_changed",
        "production_certified",
        "reference_retained",
        "retry_eligible",
        "runtime_quiescent",
        "schema_version",
        "stage_b_changed",
        "status",
        "success_eligible",
        "upper_bound",
    }
)
FAILURE_TERMINAL_RELEASE_FIELDS = frozenset(
    {
        "authority_scope",
        "authorizations",
        "b6_changed",
        "bounds_changed",
        "campaign_root_identity",
        "created_at_utc",
        "detached_substantive_identity",
        "detached_substantive_kind",
        "failure_pre_release_identity",
        "formal_selection_identity",
        "guardian_absence_identity",
        "lock_identities",
        "lock_release_effect",
        "lower_bound",
        "outcome",
        "package_id",
        "phase",
        "production_authority_changed",
        "production_certified",
        "post_root_closure",
        "reference_completion",
        "retry_eligible",
        "schema_version",
        "stage_b_changed",
        "status",
        "success_eligible",
        "supervisor_raw_lock_release_identity",
        "terminal_join",
        "upper_bound",
    }
)
CLEANUP_EVIDENCE_FIELDS = frozenset(
    {
        "containment_clearance_identity",
        "containment_hold_identity",
        "containment_lock_release_identity",
        "containment_lock_release_publication",
        "errors",
        "frozen_ledger",
        "reference_state",
        "runtime_quiescence",
    }
)
DETACHED_SUCCESS_FIELDS = frozenset(
    {
        "authority_scope",
        "authorizations",
        "b6_changed",
        "bounds_changed",
        "campaign_root_identity",
        "child_audit_identity",
        "controller_result_identity",
        "created_at_utc",
        "formal_selection_identity",
        "lock_identities",
        "lock_lifecycle",
        "lower_bound",
        "package_id",
        "phase_receipt_identities",
        "production_authority_changed",
        "production_certified",
        "repository_head",
        "schema_version",
        "stage_b_changed",
        "status",
        "terminal_classification_identity",
        "upper_bound",
        "verdict",
    }
)
GENERIC_INCOMPLETE_FIELDS = closeout_state.BASE_FIELDS | frozenset(
    {
        "attempt_basis",
        "consumed",
        "effects",
        "failure",
        "formal_dir",
        "joins",
        "phase",
        "retry_eligible",
        "schema_version",
        "status",
    }
)
MARKERLESS_INCOMPLETE_FIELDS = closeout_state.BASE_FIELDS | frozenset(
    {
        "attempt_consumption_effect",
        "consumed",
        "failure",
        "formal_dir_identity",
        "marker_canonical_identity_recorded",
        "no_backfill",
        "phase",
        "retry_eligible",
        "schema_version",
        "status",
    }
)
FAILURE_GUARDIAN_ABSENCE_FIELDS = frozenset(
    {
        "authorizations",
        "campaign_root_identity",
        "errors",
        "formal_selection_identity",
        "frozen_ledger_sha256",
        "guardian_absence",
        "guardian_identity",
        "lower_bound",
        "outcome",
        "package_id",
        "production_certified",
        "schema_version",
        "status",
        "success_eligible",
        "upper_bound",
    }
)


class FormalSuccessVerificationError(RuntimeError):
    """One independent success join failed closed."""


def _closed(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise FormalSuccessVerificationError(f"{label} field set drifted")
    return dict(value)


def _utc(value: object, label: str) -> str:
    if type(value) is not str or not value.endswith("Z"):
        raise FormalSuccessVerificationError(f"{label} is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise FormalSuccessVerificationError(f"{label} is not canonical UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FormalSuccessVerificationError(f"{label} lacks a UTC offset")
    return value


def _identity(value: object, label: str) -> dict[str, object]:
    try:
        return launch_validator.validate_detached_identity(value, label)
    except Exception as exc:
        raise FormalSuccessVerificationError(f"{label} identity is invalid: {exc}") from exc


def _content_identity(value: object, label: str) -> dict[str, object]:
    record = _closed(
        value,
        frozenset({"sha256", "size_bytes"}),
        label,
    )
    if (
        type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or isinstance(record["size_bytes"], bool)
        or not isinstance(record["size_bytes"], int)
        or record["size_bytes"] <= 0
    ):
        raise FormalSuccessVerificationError(
            f"{label} content identity is malformed"
        )
    return record


def validate_post_root_closure_evidence(
    value: object,
    *,
    expected_branch: str,
    expected_terminal_join_sha256: str | None = None,
) -> dict[str, object]:
    """Validate the fixed outside-root closure/replay join independently."""

    record = _closed(
        value,
        frozenset(
            {
                "alternate_replay_identity",
                "alternate_replay_receipt_identity",
                "alternate_replay_source_identity",
                "branch",
                "closure_result_identity",
                "formal_manifest_identity",
                "primary_replay_identity",
                "primary_replay_receipt_identity",
                "primary_replay_source_identity",
                "reference_completion_identity",
                "schema_version",
                "state",
                "terminal_join_sha256",
            }
        ),
        "post-root closure evidence",
    )
    if expected_branch not in {"success", "incomplete"}:
        raise FormalSuccessVerificationError(
            "expected post-root closure branch is invalid"
        )
    for field in (
        "alternate_replay_identity",
        "alternate_replay_source_identity",
        "closure_result_identity",
        "primary_replay_identity",
        "primary_replay_source_identity",
        "reference_completion_identity",
    ):
        record[field] = _content_identity(
            record[field],
            f"post-root closure {field}",
        )
    for field in (
        "alternate_replay_receipt_identity",
        "formal_manifest_identity",
        "primary_replay_receipt_identity",
    ):
        record[field] = _identity(
            record[field],
            f"post-root closure {field}",
        )
    terminal_join = record["terminal_join_sha256"]
    if (
        record["schema_version"] != POST_ROOT_CLOSURE_EVIDENCE_SCHEMA
        or record["state"] != "CLOSED_ROOT_DUAL_REPLAY_ACCEPTED"
        or record["branch"] != expected_branch
        or type(terminal_join) is not str
        or SHA256_RE.fullmatch(terminal_join) is None
        or (
            expected_terminal_join_sha256 is not None
            and terminal_join != expected_terminal_join_sha256
        )
        or record["primary_replay_source_identity"]["sha256"]
        == record["alternate_replay_source_identity"]["sha256"]
        or record["primary_replay_receipt_identity"]["path"]
        == record["alternate_replay_receipt_identity"]["path"]
    ):
        raise FormalSuccessVerificationError(
            "post-root closure evidence discriminator or independence drifted"
        )
    return record


def _process(value: object, label: str) -> dict[str, int]:
    record = _closed(value, frozenset({"pid", "starttime"}), label)
    if (
        type(record["pid"]) is not int
        or record["pid"] <= 0
        or type(record["starttime"]) is not int
        or record["starttime"] <= 0
    ):
        raise FormalSuccessVerificationError(f"{label} process identity is malformed")
    return record


def validate_outer_identity(
    value: object,
    *,
    expected_unit_name: str,
    active: bool,
) -> dict[str, object]:
    """Pure exact outer unit/cgroup/PID-starttime validator."""

    record = _closed(
        value,
        frozenset({"control_group", "invocation_id", "processes", "unit_name"}),
        "outer identity",
    )
    if (
        type(record["unit_name"]) is not str
        or UNIT_RE.fullmatch(record["unit_name"]) is None
        or record["unit_name"] != expected_unit_name
        or type(record["invocation_id"]) is not str
        or type(record["control_group"]) is not str
        or type(record["processes"]) is not list
    ):
        raise FormalSuccessVerificationError("outer identity scalar fields drifted")
    processes = [
        _process(item, f"outer process {index}")
        for index, item in enumerate(record["processes"])
    ]
    if len({item["pid"] for item in processes}) != len(processes):
        raise FormalSuccessVerificationError("outer process identities are duplicated")
    if active:
        if (
            INVOCATION_RE.fullmatch(record["invocation_id"]) is None
            or not record["control_group"].startswith("/")
            or ".." in Path(record["control_group"]).parts
            or not processes
        ):
            raise FormalSuccessVerificationError("active outer identity is incomplete")
    elif record["invocation_id"] or record["control_group"] or processes:
        raise FormalSuccessVerificationError("prelaunch outer identity contains active state")
    result = dict(record)
    result["processes"] = processes
    return result


def _common(
    value: object,
    *,
    phase: str,
    expected: Mapping[str, object],
) -> dict[str, Any]:
    if phase not in PHASE_PAYLOAD_FIELDS:
        raise FormalSuccessVerificationError(f"unknown normal-success phase: {phase}")
    record = _closed(
        value,
        COMMON_RECEIPT_FIELDS | PHASE_PAYLOAD_FIELDS[phase],
        f"{phase} receipt",
    )
    record["campaign_root_identity"] = _identity(
        record["campaign_root_identity"],
        f"{phase} campaign root",
    )
    record["formal_selection_identity"] = _identity(
        record["formal_selection_identity"],
        f"{phase} formal selection",
    )
    _utc(record["created_at_utc"], f"{phase} created_at_utc")
    if (
        record["schema_version"] != PHASE_SCHEMAS[phase]
        or record["status"] != "PASS"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != expected["campaign_root_identity"]
        or record["formal_selection_identity"] != expected["formal_selection_identity"]
        or record["package_id"] != expected["package_id"]
        or record["manager_epoch"] != expected["manager_epoch"]
    ):
        raise FormalSuccessVerificationError(f"{phase} common authority join drifted")
    return record


def _lock_identities(value: object) -> list[dict[str, object]]:
    try:
        return launch_validator.validate_lock_identities(value)
    except Exception as exc:
        raise FormalSuccessVerificationError(f"formal lock identities are invalid: {exc}") from exc


def validate_outer_prelaunch(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_unit_name: str,
    expected_lock_identities: object,
    expected_observation_context: Mapping[str, object],
    expected_allowed_same_uid_processes: Sequence[Mapping[str, int]],
) -> dict[str, object]:
    record = _common(value, phase="outer_prelaunch", expected=expected)
    record["outer_identity"] = validate_outer_identity(
        record["outer_identity"],
        expected_unit_name=expected_unit_name,
        active=False,
    )
    absence = _closed(
        record["prelaunch_absence"],
        frozenset({"cgroup_absent", "load_state", "lock_identities", "pid_absent"}),
        "outer prelaunch absence",
    )
    absence["lock_identities"] = _lock_identities(absence["lock_identities"])
    if (
        absence["load_state"] != "not-found"
        or absence["cgroup_absent"] is not True
        or absence["pid_absent"] is not True
        or absence["lock_identities"] != _lock_identities(expected_lock_identities)
    ):
        raise FormalSuccessVerificationError("outer prelaunch absence/three-lock proof drifted")
    try:
        record["resource_admission"] = (
            resource_admission.validate_resource_admission_receipt(
                record["resource_admission"],
                expected_stage=resource_admission.FORMAL_ORGANIC_ARM,
                expected_lock_identities=absence["lock_identities"],
                expected_lock_identity_format=resource_admission.FORMAL_LOCK_IDENTITY_FORMAT,
                expected_observation_context=expected_observation_context,
                expected_allowed_same_uid_processes=expected_allowed_same_uid_processes,
            )
        )
    except resource_admission.ResourceAdmissionError as exc:
        raise FormalSuccessVerificationError(
            f"outer prelaunch resource admission drifted: {exc}"
        ) from exc
    record["prelaunch_absence"] = absence
    return record


def validate_outer_start(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_unit_name: str,
    expected_resource_admission: Mapping[str, object],
) -> dict[str, object]:
    record = _common(value, phase="outer_start", expected=expected)
    record["outer_identity"] = validate_outer_identity(
        record["outer_identity"],
        expected_unit_name=expected_unit_name,
        active=True,
    )
    effect = _closed(
        record["launch_effect"],
        frozenset({"attempted", "outer_prelaunch_identity", "recorded", "returned"}),
        "outer launch effect",
    )
    effect["outer_prelaunch_identity"] = _identity(
        effect["outer_prelaunch_identity"],
        "outer launch prelaunch",
    )
    if (
        effect["attempted"] is not True
        or effect["returned"] is not True
        or effect["recorded"] is not True
    ):
        raise FormalSuccessVerificationError("outer launch effect is not fully recorded")
    try:
        record["resource_admission"] = (
            resource_admission.validate_launch_resource_reevaluation(
                record["resource_admission"],
                expected_receipt=expected_resource_admission,
            )
        )
    except resource_admission.ResourceAdmissionError as exc:
        raise FormalSuccessVerificationError(
            f"outer launch resource reevaluation drifted: {exc}"
        ) from exc
    record["launch_effect"] = effect
    return record


def validate_outer_resource(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
    resource_contract: Mapping[str, object],
) -> dict[str, object]:
    record = _common(value, phase="outer_resource", expected=expected)
    record["outer_identity"] = validate_outer_identity(
        record["outer_identity"],
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    systemd = _closed(
        record["systemd_properties"],
        frozenset(
            {
                "collect_mode",
                "kill_mode",
                "memory_high_bytes",
                "memory_max_bytes",
                "memory_swap_max_bytes",
                "oom_policy",
                "outer_start_identity",
                "runtime_max_sec",
                "send_sigkill",
            }
        ),
        "outer systemd properties",
    )
    systemd["outer_start_identity"] = _identity(
        systemd["outer_start_identity"],
        "outer resource start",
    )
    limits = _closed(
        record["cgroup_limits"],
        frozenset({"memory_high_bytes", "memory_max_bytes", "memory_swap_max_bytes"}),
        "outer cgroup limits",
    )
    expected_systemd = {
        **dict(resource_contract),
        "outer_start_identity": systemd["outer_start_identity"],
    }
    expected_limits = {
        name: resource_contract[name]
        for name in (
            "memory_high_bytes",
            "memory_max_bytes",
            "memory_swap_max_bytes",
        )
    }
    if (
        record["outer_identity"] != dict(expected_outer_identity)
        or systemd != expected_systemd
        or limits != expected_limits
    ):
        raise FormalSuccessVerificationError("outer systemd/cgroup resource contract drifted")
    record["systemd_properties"] = systemd
    record["cgroup_limits"] = limits
    return record


def _reference_base(
    value: object,
    *,
    status: str,
    expected: Mapping[str, object],
    expected_unit_name: str,
) -> dict[str, Any]:
    """Parse one state-owned reference record without invoking its producer."""

    try:
        payload_fields = closeout_state.REFERENCE_FIELDS[status]
    except KeyError as exc:
        raise FormalSuccessVerificationError(f"unknown reference status: {status}") from exc
    fields = (
        closeout_state.BASE_FIELDS
        | frozenset({"schema_version", "status", "unit_name"})
        | payload_fields
    )
    record = _closed(value, fields, f"{status} reference lifecycle")
    record["campaign_root_identity"] = _identity(
        record["campaign_root_identity"],
        f"{status} reference campaign root",
    )
    expected_schema = (
        closeout_state.REFERENCE_ACQUISITION_SCHEMA_V2
        if status == "HELD"
        else closeout_state.REFERENCE_SCHEMA
    )
    if (
        record["schema_version"] != expected_schema
        or record["status"] != status
        or record["unit_name"] != expected_unit_name
        or record["authorizations"] != REFERENCE_FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != expected["campaign_root_identity"]
        or record["package_id"] != expected["package_id"]
        or record["upper_bound"] != [1188, 18]
        or record["lower_bound"] is not None
        or record["production_certified"] is not False
    ):
        raise FormalSuccessVerificationError(
            f"{status} reference lifecycle authority/base join drifted"
        )
    return record


def _reference_call(
    value: object,
    *,
    expected_manager_owner: str,
    expected_unit_name: str,
    label: str,
) -> dict[str, str]:
    record = _closed(
        value,
        frozenset(
            {
                "client_unique_name",
                "manager_owner_after",
                "manager_owner_before",
                "unit_name",
            }
        ),
        label,
    )
    if (
        any(type(record[field]) is not str or not record[field] for field in record)
        or not record["client_unique_name"].startswith(":")
        or record["manager_owner_before"] != expected_manager_owner
        or record["manager_owner_after"] != expected_manager_owner
        or record["unit_name"] != expected_unit_name
    ):
        raise FormalSuccessVerificationError(f"{label} identity drifted")
    return record


def _reference_connection(
    value: object,
    *,
    acquire_call: Mapping[str, object],
    expected_manager_owner: str,
    expected_unit_name: str,
) -> dict[str, str]:
    record = _closed(
        value,
        frozenset({"client_unique_name", "manager_owner", "unit_name"}),
        "RefUnit connection verification",
    )
    if (
        any(type(record[field]) is not str or not record[field] for field in record)
        or record["client_unique_name"] != acquire_call["client_unique_name"]
        or record["manager_owner"] != expected_manager_owner
        or record["unit_name"] != expected_unit_name
    ):
        raise FormalSuccessVerificationError("RefUnit connection verification drifted")
    return record


def _manager_epoch_capture(
    value: object,
    *,
    expected_manager_epoch: Mapping[str, object],
    transcript_validator: object | None,
) -> dict[str, object]:
    record = _closed(
        value,
        frozenset({"manager_epoch", "transcript"}),
        "RefUnit manager epoch capture",
    )
    if type(record["manager_epoch"]) is not dict or record["manager_epoch"] != dict(
        expected_manager_epoch
    ):
        raise FormalSuccessVerificationError("RefUnit manager epoch capture drifted")
    try:
        closeout_state.reject_none(record, "RefUnit manager epoch capture")
        if transcript_validator is not None:
            validator = getattr(
                transcript_validator,
                "validate_manager_epoch_capture_transcript",
            )
            validator(
                record["transcript"],
                expected_epoch=record["manager_epoch"],
            )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"RefUnit manager epoch transcript failed: {exc}"
        ) from exc
    return record


def validate_reference_acquisition(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
    expected_resource_identity: Mapping[str, object] | None = None,
    expected_lock_identities: object | None = None,
    transcript_validator: object | None = None,
) -> dict[str, object]:
    """Validate the state owner's HELD receipt and expose no writer path."""

    outer = validate_outer_identity(
        expected_outer_identity,
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    unit_name = str(outer["unit_name"])
    manager_epoch = expected.get("manager_epoch")
    if (
        type(manager_epoch) is not dict
        or type(manager_epoch.get("dbus_unique_owner")) is not str
        or not manager_epoch["dbus_unique_owner"]
    ):
        raise FormalSuccessVerificationError("RefUnit expected manager epoch lacks DBus owner")
    record = _reference_base(
        value,
        status="HELD",
        expected=expected,
        expected_unit_name=unit_name,
    )
    record["selection_identity"] = _identity(
        record["selection_identity"],
        "RefUnit formal selection",
    )
    record["resource_identity"] = _identity(
        record["resource_identity"],
        "RefUnit outer resource",
    )
    if (
        record["selection_identity"] != expected["formal_selection_identity"]
        or (
            expected_resource_identity is not None
            and record["resource_identity"] != dict(expected_resource_identity)
        )
    ):
        raise FormalSuccessVerificationError("RefUnit selection/resource identity join drifted")
    locks = _lock_identities(record["lock_evidence"])
    if (
        expected_lock_identities is not None
        and locks != _lock_identities(expected_lock_identities)
    ):
        raise FormalSuccessVerificationError("RefUnit three-lock identity join drifted")
    owner = str(manager_epoch["dbus_unique_owner"])
    call = _reference_call(
        record["acquire_call"],
        expected_manager_owner=owner,
        expected_unit_name=unit_name,
        label="RefUnit acquisition call",
    )
    verification = _reference_connection(
        record["connection_verification"],
        acquire_call=call,
        expected_manager_owner=owner,
        expected_unit_name=unit_name,
    )
    record["manager_epoch_capture"] = _manager_epoch_capture(
        record["manager_epoch_capture"],
        expected_manager_epoch=manager_epoch,
        transcript_validator=transcript_validator,
    )
    record["acquire_call"] = call
    record["connection_verification"] = verification
    record["lock_evidence"] = locks
    # Guardian ownership replay consumes this pure checked view.  These are
    # derived values, not fields accepted in the canonical state-owned receipt.
    record["outer_identity"] = outer
    record["reference_verification"] = verification
    return record


def _terminal_state(value: object, label: str) -> dict[str, str]:
    fields = frozenset(
        {
            "ActiveState",
            "CollectMode",
            "ControlGroup",
            "ExecMainCode",
            "ExecMainStatus",
            "InvocationID",
            "LoadState",
            "Result",
            "SubState",
        }
    )
    record = _closed(value, fields, label)
    if any(type(item) is not str for item in record.values()):
        raise FormalSuccessVerificationError(f"{label} contains a non-string systemd value")
    return record


def _validate_absence_observation(
    value: object,
    *,
    expected_frozen: Sequence[Mapping[str, object]],
    label: str,
) -> dict[str, object]:
    observation = _closed(value, frozenset({"all_absent", "records"}), label)
    records = observation["records"]
    if (
        observation["all_absent"] is not True
        or type(records) is not list
        or len(records) != len(expected_frozen)
    ):
        raise FormalSuccessVerificationError(f"{label} cardinality/status drifted")
    checked: list[dict[str, object]] = []
    for index, (raw, frozen) in enumerate(zip(records, expected_frozen, strict=True)):
        record = _closed(raw, ABSENCE_RECORD_FIELDS, f"{label} record {index}")
        if (
            frozen.get("identity_complete") is not True
            or record["source"] != frozen.get("source")
            or record["slot"] != frozen.get("slot")
            or record["unit_name"] != frozen.get("unit_name")
            or record["control_group"] != frozen.get("control_group")
            or record["processes"] != frozen.get("processes")
            or record["identity_complete"] is not True
            or record["unit_absent"] is not True
            or record["cgroup_absent"] is not True
            or record["processes_absent"] is not True
            or record["systemctl"] != ABSENT_SYSTEMD
        ):
            raise FormalSuccessVerificationError(
                f"{label} record {index} does not prove its frozen identity absent"
            )
        checked.append(record)
    return {"all_absent": True, "records": checked}


def validate_outer_terminal(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
) -> dict[str, object]:
    record = _common(value, phase="outer_terminal", expected=expected)
    record["outer_identity"] = validate_outer_identity(
        record["outer_identity"],
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    terminal = _closed(
        record["stable_terminal"],
        frozenset(
            {
                "child_audit_identity",
                "controller_result_identity",
                "first_systemd",
                "reference_acquisition_identity",
                "stability_hold_ns",
                "stable_systemd",
            }
        ),
        "outer stable terminal",
    )
    for field in (
        "child_audit_identity",
        "controller_result_identity",
        "reference_acquisition_identity",
    ):
        terminal[field] = _identity(terminal[field], f"outer terminal {field}")
    first = _terminal_state(terminal["first_systemd"], "outer first terminal")
    stable = _terminal_state(terminal["stable_systemd"], "outer stable terminal")
    if (
        record["outer_identity"] != dict(expected_outer_identity)
        or first != stable
        or stable["LoadState"] != "loaded"
        or stable["ActiveState"] != "inactive"
        or stable["SubState"] != "dead"
        or stable["Result"] != "success"
        or stable["ExecMainCode"] != "1"
        or stable["ExecMainStatus"] != "0"
        or stable["InvocationID"] != expected_outer_identity["invocation_id"]
        or stable["ControlGroup"] != expected_outer_identity["control_group"]
        or stable["CollectMode"] != "inactive-or-failed"
        or type(terminal["stability_hold_ns"]) is not int
        or terminal["stability_hold_ns"] <= 0
    ):
        raise FormalSuccessVerificationError("outer stable terminal evidence drifted")
    terminal["first_systemd"] = first
    terminal["stable_systemd"] = stable
    record["stable_terminal"] = terminal
    return record


def _heavy_absence(value: object, label: str) -> dict[str, object]:
    record = _closed(
        value,
        frozenset({"all_absent", "child_audit_identity", "outer_terminal_identity"}),
        label,
    )
    record["child_audit_identity"] = _identity(
        record["child_audit_identity"],
        f"{label} child audit",
    )
    record["outer_terminal_identity"] = _identity(
        record["outer_terminal_identity"],
        f"{label} outer terminal",
    )
    if record["all_absent"] is not True:
        raise FormalSuccessVerificationError(f"{label} did not prove all heavy identities absent")
    return record


def validate_observer(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
) -> dict[str, object]:
    record = _common(value, phase="observer", expected=expected)
    record["outer_identity"] = validate_outer_identity(
        record["outer_identity"],
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    record["heavy_absence"] = _heavy_absence(record["heavy_absence"], "observer heavy absence")
    if record["outer_identity"] != dict(expected_outer_identity):
        raise FormalSuccessVerificationError("observer outer identity drifted")
    return record


def validate_pre_unref_cleanup(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
) -> dict[str, object]:
    record = _common(value, phase="pre_unref_cleanup", expected=expected)
    record["outer_identity"] = validate_outer_identity(
        record["outer_identity"],
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    record["child_audit_identity"] = _identity(
        record["child_audit_identity"],
        "pre-Unref child audit",
    )
    record["observer_identity"] = _identity(
        record["observer_identity"],
        "pre-Unref observer",
    )
    record["heavy_absence"] = _heavy_absence(
        record["heavy_absence"],
        "pre-Unref heavy absence",
    )
    cleanup = _closed(
        record["outer_cleanup"],
        frozenset(
            {
                "cgroup_absent",
                "keeper_absent",
                "load_state",
                "outer_terminal_identity",
                "payload_absent",
                "unit_kept_loaded_by_reference",
            }
        ),
        "pre-Unref outer cleanup",
    )
    cleanup["outer_terminal_identity"] = _identity(
        cleanup["outer_terminal_identity"],
        "pre-Unref outer terminal",
    )
    if (
        record["outer_identity"] != dict(expected_outer_identity)
        or cleanup["payload_absent"] is not True
        or cleanup["keeper_absent"] is not True
        or cleanup["cgroup_absent"] is not True
        or cleanup["unit_kept_loaded_by_reference"] is not True
        or cleanup["load_state"] != "loaded"
    ):
        raise FormalSuccessVerificationError("pre-Unref cleanup did not preserve the referenced unit")
    record["outer_cleanup"] = cleanup
    return record


def validate_unref_call(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
    expected_acquisition_identity: Mapping[str, object],
    expected_client_unique_name: str,
    expected_observer_identity: Mapping[str, object],
    expected_pre_unref_cleanup_identity: Mapping[str, object],
) -> dict[str, object]:
    """Validate state-owned UNREF_RETURNED evidence before connection close."""

    outer = validate_outer_identity(
        expected_outer_identity,
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    manager_epoch = expected.get("manager_epoch")
    if (
        type(manager_epoch) is not dict
        or type(manager_epoch.get("dbus_unique_owner")) is not str
        or not manager_epoch["dbus_unique_owner"]
    ):
        raise FormalSuccessVerificationError("UnrefUnit expected manager epoch lacks DBus owner")
    record = _reference_base(
        value,
        status="UNREF_RETURNED",
        expected=expected,
        expected_unit_name=str(outer["unit_name"]),
    )
    for field in (
        "acquisition_identity",
        "observer_identity",
        "pre_unref_cleanup_identity",
    ):
        record[field] = _identity(record[field], f"UnrefUnit {field}")
    if (
        record["acquisition_identity"] != dict(expected_acquisition_identity)
        or record["observer_identity"] != dict(expected_observer_identity)
        or record["pre_unref_cleanup_identity"]
        != dict(expected_pre_unref_cleanup_identity)
    ):
        raise FormalSuccessVerificationError("UnrefUnit prerequisite identity join drifted")
    record["call"] = _reference_call(
        record["call"],
        expected_manager_owner=str(manager_epoch["dbus_unique_owner"]),
        expected_unit_name=str(outer["unit_name"]),
        label="UnrefUnit call",
    )
    if record["call"]["client_unique_name"] != expected_client_unique_name:
        raise FormalSuccessVerificationError(
            "UnrefUnit connection identity drifted from RefUnit acquisition"
        )
    return record


def validate_reference_release(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
    expected_acquisition_identity: Mapping[str, object],
    expected_unref_call_identity: Mapping[str, object],
    expected_observer_identity: Mapping[str, object],
    expected_pre_unref_cleanup_identity: Mapping[str, object],
    expected_raw_lock_release_identity: Mapping[str, object],
) -> dict[str, object]:
    """Validate exact-once Unref while the same connection remains open."""

    outer = validate_outer_identity(
        expected_outer_identity,
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    payload_fields = frozenset(
        {
            "acquisition_identity",
            "call",
            "connection_retained",
            "observer_identity",
            "pre_unref_cleanup_identity",
            "supervisor_raw_lock_release_identity",
            "unref_call_identity",
        }
    )
    record = _closed(
        value,
        closeout_state.BASE_FIELDS
        | frozenset({"schema_version", "status", "unit_name"})
        | payload_fields,
        "prospective reference release",
    )
    record["campaign_root_identity"] = _identity(
        record["campaign_root_identity"],
        "reference release campaign root",
    )
    for field in (
        "acquisition_identity",
        "observer_identity",
        "pre_unref_cleanup_identity",
        "supervisor_raw_lock_release_identity",
        "unref_call_identity",
    ):
        record[field] = _identity(record[field], f"reference release {field}")
    manager_epoch = expected.get("manager_epoch")
    if type(manager_epoch) is not dict:
        raise FormalSuccessVerificationError(
            "reference release expected manager epoch is malformed"
        )
    call = _reference_call(
        record["call"],
        expected_manager_owner=str(manager_epoch.get("dbus_unique_owner", "")),
        expected_unit_name=str(outer["unit_name"]),
        label="prospective UnrefUnit call",
    )
    if (
        record["schema_version"] != closeout_state.REFERENCE_RELEASE_SCHEMA_V2
        or record["status"] != "UNREF_RETURNED_CONNECTION_RETAINED"
        or record["unit_name"] != outer["unit_name"]
        or record["authorizations"] != REFERENCE_FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != expected["campaign_root_identity"]
        or record["package_id"] != expected["package_id"]
        or record["upper_bound"] != [1188, 18]
        or record["lower_bound"] is not None
        or record["production_certified"] is not False
        or record["acquisition_identity"] != dict(expected_acquisition_identity)
        or record["unref_call_identity"] != dict(expected_unref_call_identity)
        or record["observer_identity"] != dict(expected_observer_identity)
        or record["pre_unref_cleanup_identity"]
        != dict(expected_pre_unref_cleanup_identity)
        or record["supervisor_raw_lock_release_identity"]
        != dict(expected_raw_lock_release_identity)
        or record["connection_retained"] is not True
    ):
        raise FormalSuccessVerificationError(
            "reference release retained-connection join drifted"
        )
    record["call"] = call
    return record


def validate_post_unref_absence(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
) -> dict[str, object]:
    record = _common(value, phase="post_unref_absence", expected=expected)
    record["outer_identity"] = validate_outer_identity(
        record["outer_identity"],
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    load_state = _closed(
        record["load_state"],
        frozenset({"reference_release_identity", "value"}),
        "post-Unref load state",
    )
    load_state["reference_release_identity"] = _identity(
        load_state["reference_release_identity"],
        "post-Unref reference release",
    )
    if (
        record["outer_identity"] != dict(expected_outer_identity)
        or load_state["value"] != "not-found"
        or record["cgroup_absent"] is not True
        or record["pid_absent"] is not True
    ):
        raise FormalSuccessVerificationError("post-Unref unit/cgroup/PID absence failed")
    record["load_state"] = load_state
    return record


def _released_connection_verification(
    value: object,
    *,
    expected_client_unique_name: str,
    expected_manager_owner: str,
) -> dict[str, object]:
    record = _closed(
        value,
        frozenset(
            {
                "client_unique_name",
                "library_identity",
                "manager_owner",
                "reference_held",
            }
        ),
        "released RefUnit connection verification",
    )
    record["library_identity"] = _identity(
        record["library_identity"],
        "released RefUnit library",
    )
    if (
        record["client_unique_name"] != expected_client_unique_name
        or record["manager_owner"] != expected_manager_owner
        or record["reference_held"] is not False
    ):
        raise FormalSuccessVerificationError(
            "released RefUnit manager/client/reference state drifted"
        )
    return record


def validate_reference_terminal(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
    expected_acquisition_identity: Mapping[str, object],
    expected_release_identity: Mapping[str, object],
    expected_unref_call_identity: Mapping[str, object],
    expected_post_unref_absence_identity: Mapping[str, object],
    expected_client_unique_name: str,
) -> dict[str, object]:
    """Validate post-absence same-connection identity and library replay."""

    outer = validate_outer_identity(
        expected_outer_identity,
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    fields = frozenset(
        {
            "acquisition_identity",
            "connection_verification",
            "post_unref_absence_identity",
            "reference_release_identity",
            "unref_call_identity",
        }
    )
    record = _closed(
        value,
        closeout_state.BASE_FIELDS
        | frozenset({"schema_version", "status", "unit_name"})
        | fields,
        "prospective reference terminal",
    )
    record["campaign_root_identity"] = _identity(
        record["campaign_root_identity"],
        "reference terminal campaign root",
    )
    for field in fields - {"connection_verification"}:
        record[field] = _identity(record[field], f"reference terminal {field}")
    manager_epoch = expected.get("manager_epoch")
    if type(manager_epoch) is not dict:
        raise FormalSuccessVerificationError(
            "reference terminal manager epoch is malformed"
        )
    verification = _released_connection_verification(
        record["connection_verification"],
        expected_client_unique_name=expected_client_unique_name,
        expected_manager_owner=str(manager_epoch.get("dbus_unique_owner", "")),
    )
    if (
        record["schema_version"] != closeout_state.REFERENCE_TERMINAL_SCHEMA
        or record["status"] != "UNREFERENCED_CONNECTION_VERIFIED"
        or record["unit_name"] != outer["unit_name"]
        or record["authorizations"] != REFERENCE_FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != expected["campaign_root_identity"]
        or record["package_id"] != expected["package_id"]
        or record["upper_bound"] != [1188, 18]
        or record["lower_bound"] is not None
        or record["production_certified"] is not False
        or record["acquisition_identity"] != dict(expected_acquisition_identity)
        or record["reference_release_identity"] != dict(expected_release_identity)
        or record["unref_call_identity"] != dict(expected_unref_call_identity)
        or record["post_unref_absence_identity"]
        != dict(expected_post_unref_absence_identity)
    ):
        raise FormalSuccessVerificationError(
            "reference terminal predecessor join drifted"
        )
    record["connection_verification"] = verification
    return record


def validate_reference_connection_close(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_outer_identity: Mapping[str, object],
    expected_reference_terminal_identity: Mapping[str, object],
    expected_connection_verification: Mapping[str, object],
) -> dict[str, object]:
    """Validate the exact-once close receipt after the terminal record."""

    outer = validate_outer_identity(
        expected_outer_identity,
        expected_unit_name=str(expected_outer_identity["unit_name"]),
        active=True,
    )
    fields = frozenset(
        {
            "connection_close_attempts",
            "connection_close_returned",
            "connection_verification",
            "reference_terminal_identity",
        }
    )
    record = _closed(
        value,
        closeout_state.BASE_FIELDS
        | frozenset({"schema_version", "status", "unit_name"})
        | fields,
        "prospective reference connection close",
    )
    record["campaign_root_identity"] = _identity(
        record["campaign_root_identity"],
        "reference connection close campaign root",
    )
    record["reference_terminal_identity"] = _identity(
        record["reference_terminal_identity"],
        "reference connection close terminal",
    )
    expected_verification = dict(expected_connection_verification)
    record["connection_verification"] = _released_connection_verification(
        record["connection_verification"],
        expected_client_unique_name=str(
            expected_verification.get("client_unique_name", "")
        ),
        expected_manager_owner=str(
            expected_verification.get("manager_owner", "")
        ),
    )
    if (
        record["schema_version"]
        != closeout_state.REFERENCE_CONNECTION_CLOSE_SCHEMA
        or record["status"] != "CONNECTION_CLOSED"
        or record["unit_name"] != outer["unit_name"]
        or record["authorizations"] != REFERENCE_FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != expected["campaign_root_identity"]
        or record["package_id"] != expected["package_id"]
        or record["upper_bound"] != [1188, 18]
        or record["lower_bound"] is not None
        or record["production_certified"] is not False
        or record["connection_close_attempts"] != 1
        or record["connection_close_returned"] is not True
        or record["connection_verification"] != expected_verification
        or record["reference_terminal_identity"]
        != dict(expected_reference_terminal_identity)
    ):
        raise FormalSuccessVerificationError(
            "reference connection-close join drifted"
        )
    return record


def validate_guardian_absence(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_guardian_identity: Mapping[str, object],
    expected_guardian_close_identity: Mapping[str, object],
    expected_detached_success_identity: Mapping[str, object],
    expected_pre_unref_cleanup_identity: Mapping[str, object],
) -> dict[str, object]:
    """Prove the selected guardian absent before supervisor lock release."""

    record = _common(value, phase="guardian_absence", expected=expected)
    guardian = validate_outer_identity(
        record["guardian_identity"],
        expected_unit_name=str(expected_guardian_identity["unit_name"]),
        active=True,
    )
    expected_guardian = validate_outer_identity(
        expected_guardian_identity,
        expected_unit_name=str(expected_guardian_identity["unit_name"]),
        active=True,
    )
    record["detached_success_identity"] = _identity(
        record["detached_success_identity"],
        "guardian absence detached substantive basis",
    )
    record["pre_unref_cleanup_identity"] = _identity(
        record["pre_unref_cleanup_identity"],
        "guardian absence pre-Unref cleanup basis",
    )
    record["guardian_close_identity"] = _identity(
        record["guardian_close_identity"],
        "guardian absence lock close basis",
    )
    systemctl = _closed(
        record["systemctl"],
        frozenset(ABSENT_SYSTEMD),
        "guardian absence systemctl",
    )
    if (
        guardian != expected_guardian
        or record["guardian_close_identity"]
        != dict(expected_guardian_close_identity)
        or record["detached_success_identity"]
        != dict(expected_detached_success_identity)
        or record["pre_unref_cleanup_identity"]
        != dict(expected_pre_unref_cleanup_identity)
        or systemctl != ABSENT_SYSTEMD
        or record["unit_absent"] is not True
        or record["cgroup_absent"] is not True
        or record["pid_absent"] is not True
    ):
        raise FormalSuccessVerificationError(
            "guardian unit/cgroup/PID absence ordering drifted"
        )
    record["guardian_identity"] = guardian
    record["systemctl"] = systemctl
    return record


def validate_supervisor_raw_lock_release(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_lock_identities: object,
    expected_detached_substantive_identity: Mapping[str, object],
    expected_detached_substantive_kind: str,
    expected_failure_pre_release_identity: Mapping[str, object] | str,
    expected_guardian_absence_identity: Mapping[str, object],
    expected_guardian_close_identity: Mapping[str, object] | str,
) -> dict[str, object]:
    """Validate the raw three-lock release, not the final terminal join."""

    record = _closed(
        value,
        COMMON_RECEIPT_FIELDS
        | PHASE_PAYLOAD_FIELDS["supervisor_raw_lock_release"],
        "supervisor raw lock release",
    )
    record["campaign_root_identity"] = _identity(
        record["campaign_root_identity"],
        "raw release campaign root",
    )
    expected_selection = expected["formal_selection_identity"]
    if expected_selection == "absent":
        selection: dict[str, object] | str = "absent"
    else:
        selection = _identity(
            expected_selection,
            "expected raw release formal selection",
        )
    if selection != "absent":
        record["formal_selection_identity"] = _identity(
            record["formal_selection_identity"],
            "raw release formal selection",
        )
    _utc(record["created_at_utc"], "raw release created_at_utc")
    record["detached_substantive_identity"] = _identity(
        record["detached_substantive_identity"],
        "raw release detached replay",
    )
    record["guardian_absence_identity"] = _identity(
        record["guardian_absence_identity"],
        "raw release guardian absence",
    )
    if expected_guardian_close_identity == "combined-in-guardian-absence":
        guardian_close: dict[str, object] | str = (
            "combined-in-guardian-absence"
        )
    else:
        guardian_close = _identity(
            expected_guardian_close_identity,
            "expected raw release guardian close",
        )
    if expected_failure_pre_release_identity == "absent":
        failure_pre_release: dict[str, object] | str = "absent"
    else:
        failure_pre_release = _identity(
            expected_failure_pre_release_identity,
            "expected raw release pre-release failure",
        )
    record["lock_identities"] = _lock_identities(record["lock_identities"])
    release = _closed(
        record["supervisor_release"],
        frozenset(
            {
                "after_guardian_absence",
                "attempted",
                "recorded",
                "returned",
            }
        ),
        "raw supervisor lock release",
    )
    if (
        record["schema_version"]
        != closeout_state.SUPERVISOR_RAW_LOCK_RELEASE_SCHEMA
        or record["status"]
        != ("PASS" if expected_detached_substantive_kind == "success_v3" else "INCOMPLETE")
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != expected["campaign_root_identity"]
        or record["formal_selection_identity"] != selection
        or record["package_id"] != expected["package_id"]
        or record["manager_epoch"] != expected["manager_epoch"]
        or record["lock_identities"] != _lock_identities(expected_lock_identities)
        or record["detached_substantive_identity"]
        != dict(expected_detached_substantive_identity)
        or record["detached_substantive_kind"]
        != expected_detached_substantive_kind
        or record["failure_pre_release_identity"] != failure_pre_release
        or record["guardian_absence_identity"]
        != dict(expected_guardian_absence_identity)
        or record["guardian_close_identity"] != guardian_close
        or record["outcome"]
        != (
            "SUCCESS_CANDIDATE"
            if expected_detached_substantive_kind == "success_v3"
            else "INCOMPLETE"
        )
        or (
            expected_detached_substantive_kind == "success_v3"
            and failure_pre_release != "absent"
        )
        or (
            expected_detached_substantive_kind == "incomplete_v4"
            and type(failure_pre_release) is not dict
        )
        or any(value is not True for value in release.values())
    ):
        raise FormalSuccessVerificationError(
            "raw supervisor lock-release ordering drifted"
        )
    record["supervisor_release"] = release
    return record


def validate_dual_lock_release(
    value: object,
    *,
    expected: Mapping[str, object],
    expected_lock_identities: object,
    expected_detached_success_identity: Mapping[str, object],
    expected_guardian_absence_identity: Mapping[str, object],
    expected_guardian_close_identity: Mapping[str, object],
    expected_raw_lock_release_identity: Mapping[str, object],
    expected_reference_release_identity: Mapping[str, object],
    expected_post_unref_absence_identity: Mapping[str, object],
    expected_reference_terminal_identity: Mapping[str, object],
    expected_reference_connection_close_identity: Mapping[str, object],
    expected_post_root_closure: Mapping[str, object],
) -> dict[str, object]:
    record = _common(value, phase="dual_lock_release", expected=expected)
    record["detached_success_identity"] = _identity(
        record["detached_success_identity"],
        "detached substantive verification",
    )
    record["guardian_close_identity"] = _identity(
        record["guardian_close_identity"],
        "guardian lock close",
    )
    record["guardian_absence_identity"] = _identity(
        record["guardian_absence_identity"],
        "guardian absence",
    )
    for field, label in (
        ("supervisor_raw_lock_release_identity", "raw supervisor lock release"),
        ("reference_release_identity", "reference release"),
        ("post_unref_absence_identity", "post-Unref absence"),
        ("reference_terminal_identity", "reference terminal"),
        ("reference_connection_close_identity", "reference connection close"),
    ):
        record[field] = _identity(record[field], label)
    record["lock_identities"] = _lock_identities(record["lock_identities"])
    record["post_root_closure"] = validate_post_root_closure_evidence(
        record["post_root_closure"],
        expected_branch="success",
    )
    expected_closure = validate_post_root_closure_evidence(
        expected_post_root_closure,
        expected_branch="success",
    )
    terminal = _closed(
        record["terminal_join"],
        frozenset(
            {
                "detached_success_before_guardian_close",
                "formal_root_closed_before_outside_replays",
                "guardian_absence_before_supervisor_release",
                "locks_released_after_substantive_verification",
                "outside_replays_before_final_join",
                "post_unref_absence_before_reference_terminal",
                "raw_lock_release_before_unref",
                "recovery_disarmed_before_manifest",
                "broker_absent_before_manifest",
                "reference_terminal_before_connection_close",
                "reference_connection_close_before_final_join",
            }
        ),
        "formal terminal join",
    )
    if (
        record["lock_identities"] != _lock_identities(expected_lock_identities)
        or record["detached_success_identity"]
        != dict(expected_detached_success_identity)
        or record["guardian_absence_identity"]
        != dict(expected_guardian_absence_identity)
        or record["guardian_close_identity"]
        != dict(expected_guardian_close_identity)
        or record["supervisor_raw_lock_release_identity"]
        != dict(expected_raw_lock_release_identity)
        or record["reference_release_identity"]
        != dict(expected_reference_release_identity)
        or record["post_unref_absence_identity"]
        != dict(expected_post_unref_absence_identity)
        or record["reference_terminal_identity"]
        != dict(expected_reference_terminal_identity)
        or record["reference_connection_close_identity"]
        != dict(expected_reference_connection_close_identity)
        or record["post_root_closure"] != expected_closure
        or any(value is not True for value in terminal.values())
    ):
        raise FormalSuccessVerificationError("guardian/supervisor lock release ordering drifted")
    record["terminal_join"] = terminal
    return record


PHASE_VALIDATORS = {
    "outer_prelaunch": validate_outer_prelaunch,
    "outer_start": validate_outer_start,
    "outer_resource": validate_outer_resource,
    "outer_terminal": validate_outer_terminal,
    "observer": validate_observer,
    "pre_unref_cleanup": validate_pre_unref_cleanup,
    "post_unref_absence": validate_post_unref_absence,
    "guardian_absence": validate_guardian_absence,
    "supervisor_raw_lock_release": validate_supervisor_raw_lock_release,
    "dual_lock_release": validate_dual_lock_release,
}


def _read_record(
    path: Path | str,
    *,
    expected_identity: Mapping[str, object] | None,
    label: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    try:
        return launch_validator.read_canonical_record(
            path,
            expected_identity=expected_identity,
            label=label,
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(f"{label} replay failed: {exc}") from exc


def _load_selection(
    campaign_dir: Path,
    selection_path: Path,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    try:
        context = launch_validator.replay_formal_launch_context(authority, campaign_dir)
    except Exception as exc:
        raise FormalSuccessVerificationError(f"formal context replay failed: {exc}") from exc
    if selection_path != Path(str(context["formal_selection_path"])):
        raise FormalSuccessVerificationError("formal selection path differs from authority context")
    selection, selection_identity = _read_record(
        selection_path,
        expected_identity=None,
        label="formal selection",
    )
    prerequisite: dict[str, tuple[dict[str, Any], dict[str, object]]] = {}
    for field, label in (
        ("formal_admission_identity", "formal admission"),
        ("guardian_ready_identity", "guardian ready"),
        ("attempt_consumption_identity", "attempt consumption"),
    ):
        expected = _identity(selection.get(field), f"selection {field}")
        prerequisite[field] = _read_record(
            expected["path"],
            expected_identity=expected,
            label=label,
        )
    try:
        checked = launch_validator.validate_selection(
            selection,
            admission=prerequisite["formal_admission_identity"][0],
            admission_identity=prerequisite["formal_admission_identity"][1],
            guardian_ready=prerequisite["guardian_ready_identity"][0],
            guardian_ready_identity=prerequisite["guardian_ready_identity"][1],
            attempt_consumption=prerequisite["attempt_consumption_identity"][0],
            attempt_consumption_identity=prerequisite["attempt_consumption_identity"][1],
            expected_context=context,
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(f"formal selection replay failed: {exc}") from exc
    try:
        checked_guardian = launch_validator.validate_guardian_ready(
            prerequisite["guardian_ready_identity"][0],
            admission=prerequisite["formal_admission_identity"][0],
            admission_identity=prerequisite["formal_admission_identity"][1],
            expected_context=context,
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"guardian-ready replay failed: {exc}"
        ) from exc
    return context, checked, selection_identity, checked_guardian


def _state_base(
    value: Mapping[str, object],
    *,
    context: Mapping[str, object],
    label: str,
) -> None:
    if (
        value.get("authorizations") != closeout_state.FALSE_AUTHORIZATIONS
        or value.get("campaign_root_identity") != context["campaign_root_identity"]
        or value.get("package_id") != context["package_id"]
        or value.get("upper_bound") != [1188, 18]
        or value.get("lower_bound") is not None
        or value.get("production_certified") is not False
    ):
        raise FormalSuccessVerificationError(f"{label} crossed the research claim boundary")


def _recorded_publication_identity(
    effects: Mapping[str, object],
    key: str,
) -> dict[str, object]:
    publications = effects.get("publications")
    publication = publications.get(key) if type(publications) is dict else None
    if (
        type(publication) is not dict
        or publication.get("recorded") is not True
        or publication.get("returned") is not True
        or "recorded_identity" not in publication
        or "returned_identity" not in publication
    ):
        raise FormalSuccessVerificationError(f"{key} publication is not canonically recorded")
    recorded = _identity(publication["recorded_identity"], f"{key} publication")
    returned = _identity(publication["returned_identity"], f"{key} publication return")
    if recorded != returned:
        raise FormalSuccessVerificationError(f"{key} publication/readback identity drifted")
    return recorded


def _validate_phase_joins_and_effects(
    *,
    phase: str,
    joins: object,
    effects: Mapping[str, object],
) -> dict[str, object]:
    rule = closeout_state.INCOMPLETE_PHASES.get(phase)
    if rule is None:
        raise FormalSuccessVerificationError(f"unknown consumed-incomplete phase: {phase}")
    if type(joins) is not dict:
        raise FormalSuccessVerificationError("consumed-incomplete joins are not one object")
    proof_fields = set(closeout_state.PROOF_FIELDS)
    actual_proofs = set(joins) & proof_fields
    external = set(joins) - proof_fields
    if (
        not set(rule.required_proofs).issubset(actual_proofs)
        or not actual_proofs.issubset(rule.permitted_proofs)
        or external != set(rule.external_joins)
    ):
        raise FormalSuccessVerificationError(
            f"{phase} consumed-incomplete join boundary drifted"
        )
    checked: dict[str, object] = {}
    for name, value in joins.items():
        if name == "frozen_outer_identity":
            try:
                checked[name] = closeout_state.validate_frozen_identity(
                    value,
                    expected_source="outer",
                    expected_slot="formal",
                )
            except Exception as exc:
                raise FormalSuccessVerificationError(
                    f"{phase} frozen outer identity failed: {exc}"
                ) from exc
        else:
            checked[name] = _identity(value, f"{phase}.{name}")
    for name in rule.required_true_effects:
        if effects.get(name) is not True:
            raise FormalSuccessVerificationError(f"{phase} lacks true effect {name}")
    for name in rule.required_nonnull_effects:
        if effects.get(name) is None:
            raise FormalSuccessVerificationError(f"{phase} lacks returned effect {name}")
    for name, expected in rule.effect_equals:
        observed = effects.get(name)
        if type(observed) is not type(expected) or observed != expected:
            raise FormalSuccessVerificationError(
                f"{phase} effect {name} crossed its acquisition boundary"
            )
    for name in rule.required_publications:
        publications = effects.get("publications")
        publication = publications.get(name) if type(publications) is dict else None
        if type(publication) is not dict or publication.get("attempted") is not True:
            raise FormalSuccessVerificationError(
                f"{phase} lacks attempted publication {name}"
            )
    return checked


def validate_consumed_incomplete(
    value: object,
    *,
    context: Mapping[str, object],
    expected_identity: Mapping[str, object],
    expected_marker_identity: Mapping[str, object],
    expected_phase: str,
    expected_selection_identity: Mapping[str, object] | None,
) -> dict[str, object]:
    """Independently validate one marker-backed consumed-incomplete receipt."""

    record = _closed(value, GENERIC_INCOMPLETE_FIELDS, "consumed incomplete")
    _state_base(record, context=context, label="consumed incomplete")
    try:
        failure = closeout_state.validate_failure_record(
            record["failure"],
            "consumed incomplete",
        )
        effects = closeout_state._validate_effect_snapshot(  # noqa: SLF001
            record["effects"]
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"consumed-incomplete structural replay failed: {exc}"
        ) from exc
    basis = _closed(
        record["attempt_basis"],
        frozenset({"identity", "kind"}),
        "consumed incomplete attempt basis",
    )
    basis["identity"] = _identity(basis["identity"], "consumed incomplete marker")
    marker = _identity(expected_marker_identity, "expected attempt marker")
    identity = _identity(expected_identity, "expected consumed incomplete")
    joins = _validate_phase_joins_and_effects(
        phase=expected_phase,
        joins=record["joins"],
        effects=effects,
    )
    recorded_marker = _recorded_publication_identity(effects, "attempt-consumption")
    if (
        record["schema_version"] != closeout_state.INCOMPLETE_SCHEMA
        or record["status"] != "CONSUMED_INCOMPLETE"
        or record["phase"] != expected_phase
        or record["formal_dir"] != context["formal_attempt_dir"]
        or record["consumed"] is not True
        or record["retry_eligible"] is not False
        or basis["kind"] != "RECORDED"
        or basis["identity"] != marker
        or recorded_marker != marker
        or identity["path"]
        != str(
            Path(str(context["formal_attempt_dir"]))
            / f"incomplete-{expected_phase.lower().replace('_', '-')}.json"
        )
    ):
        raise FormalSuccessVerificationError(
            "consumed-incomplete marker/path/state join drifted"
        )
    if expected_selection_identity is None:
        if "selection_identity" in joins:
            raise FormalSuccessVerificationError(
                "selection-unrecorded incomplete includes a future selection join"
            )
    elif joins.get("selection_identity") != dict(expected_selection_identity):
        raise FormalSuccessVerificationError(
            "selected consumed-incomplete does not join formal selection"
        )
    record["attempt_basis"] = basis
    record["effects"] = effects
    record["failure"] = failure
    record["joins"] = joins
    return record


def _directory_identity(path: Path | str) -> dict[str, object]:
    absolute = Path(path).absolute()
    try:
        descriptor = os.open(
            absolute,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise FormalSuccessVerificationError(
            f"formal attempt directory cannot be opened stably: {exc}"
        ) from exc
    try:
        before = os.fstat(descriptor)
        current = os.stat(absolute, follow_symlinks=False)
    finally:
        os.close(descriptor)
    if (
        not stat.S_ISDIR(before.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)
    ):
        raise FormalSuccessVerificationError("formal attempt directory identity drifted")
    return {
        "device": before.st_dev,
        "gid": before.st_gid,
        "inode": before.st_ino,
        "mode": stat.S_IMODE(before.st_mode),
        "path": str(absolute),
        "uid": before.st_uid,
    }


def validate_markerless_incomplete(
    value: object,
    *,
    context: Mapping[str, object],
    expected_identity: Mapping[str, object],
    expected_phase: str,
) -> dict[str, object]:
    """Validate the sole markerless terminal without inventing future joins."""

    record = _closed(value, MARKERLESS_INCOMPLETE_FIELDS, "markerless incomplete")
    _state_base(record, context=context, label="markerless incomplete")
    try:
        effect = closeout_state._validate_publication_effect_record(  # noqa: SLF001
            record["attempt_consumption_effect"],
            "markerless attempt consumption",
        )
        failure = closeout_state.validate_failure_record(
            record["failure"],
            "markerless incomplete",
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"markerless structural replay failed: {exc}"
        ) from exc
    identity = _identity(expected_identity, "expected markerless incomplete")
    attempt = Path(str(context["formal_attempt_dir"]))
    if (
        record["schema_version"] != closeout_state.MARKERLESS_SCHEMA
        or record["status"]
        != closeout_state.FORMAL_MARKERLESS_INCOMPLETE
        or record["phase"] != expected_phase
        or expected_phase != "DIRECTORY_CREATED_MARKER_UNRECORDED"
        or record["consumed"] is not True
        or record["retry_eligible"] is not False
        or record["marker_canonical_identity_recorded"] is not False
        or record["no_backfill"] is not True
        or effect["attempted"] is not True
        or effect["recorded"] is not False
        or record["formal_dir_identity"] != _directory_identity(attempt)
        or identity["path"] != str(attempt / "markerless-incomplete.json")
        or os.path.lexists(attempt / "attempt-consumption.json")
    ):
        raise FormalSuccessVerificationError("markerless no-backfill/directory join drifted")
    record["attempt_consumption_effect"] = effect
    record["failure"] = failure
    return record


def validate_failure_guardian_absence(
    value: object,
    *,
    context: Mapping[str, object],
    expected_identity: Mapping[str, object],
    expected_selection_identity: Mapping[str, object] | None,
    expected_guardian_identity: Mapping[str, object] | None,
) -> dict[str, object]:
    """Validate the selected or preselection guardian's terminal absence."""

    record = _closed(
        value,
        FAILURE_GUARDIAN_ABSENCE_FIELDS,
        "failure guardian absence",
    )
    identity = _identity(expected_identity, "failure guardian absence")
    formal_selection: dict[str, object] | str
    if expected_selection_identity is None:
        formal_selection = "absent"
    else:
        formal_selection = dict(expected_selection_identity)
    guardian = validate_outer_identity(
        record["guardian_identity"],
        expected_unit_name=str(context["guardian_spec"]["unit_name"]),
        active=True,
    )
    if expected_guardian_identity is not None:
        expected_guardian = validate_outer_identity(
            expected_guardian_identity,
            expected_unit_name=str(context["guardian_spec"]["unit_name"]),
            active=True,
        )
        if guardian != expected_guardian:
            raise FormalSuccessVerificationError(
                "failure guardian identity drifted from formal selection"
            )
    absence = _closed(
        record["guardian_absence"],
        frozenset({"cgroup_absent", "pid_absent", "systemctl", "unit_absent"}),
        "failure guardian absence observation",
    )
    try:
        errors = closeout_state.validate_failure_list(
            record["errors"],
            "failure guardian absence",
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"failure guardian error list drifted: {exc}"
        ) from exc
    if (
        record["schema_version"] != CONTAINMENT_GUARDIAN_ABSENCE_SCHEMA
        or record["status"] != "GUARDIAN_ABSENT"
        or record["outcome"] != "INCOMPLETE"
        or record["success_eligible"] is not False
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != context["campaign_root_identity"]
        or record["package_id"] != context["package_id"]
        or record["formal_selection_identity"] != formal_selection
        or type(record["frozen_ledger_sha256"]) is not str
        or SHA256_RE.fullmatch(record["frozen_ledger_sha256"]) is None
        or record["upper_bound"] != [1188, 18]
        or record["lower_bound"] != "absent"
        or record["production_certified"] is not False
        or absence["systemctl"] != ABSENT_SYSTEMD
        or any(
            absence[field] is not True
            for field in ("unit_absent", "cgroup_absent", "pid_absent")
        )
        or identity["path"]
        != str(
            Path(str(context["formal_attempt_dir"]))
            / "containment-guardian-absence.json"
        )
    ):
        raise FormalSuccessVerificationError(
            "failure guardian absence/claim/path join drifted"
        )
    record["errors"] = errors
    record["guardian_absence"] = absence
    record["guardian_identity"] = guardian
    return record


def _cleanup_identity(
    value: object,
    label: str,
    *,
    allow_unrecorded: bool = False,
) -> dict[str, object] | str:
    if value == "absent":
        return "absent"
    if value == "unrecorded":
        if allow_unrecorded:
            return "unrecorded"
        raise FormalSuccessVerificationError(
            f"{label} was not canonically recorded"
        )
    return _identity(value, label)


def _validate_cleanup_evidence(
    value: object,
    *,
    context: Mapping[str, object],
    incomplete: Mapping[str, object],
    phase: str,
) -> dict[str, object]:
    """Replay locks-held failure cleanup without requiring RefUnit release."""

    record = _closed(value, CLEANUP_EVIDENCE_FIELDS, "failure cleanup evidence")
    try:
        ledger = closeout_state.validate_frozen_ledger(record["frozen_ledger"])
        child_audit = ledger["child_audit_identity"]
        if child_audit != {}:
            ledger["child_audit_identity"] = _identity(
                child_audit,
                "failure cleanup child audit",
            )
        reference_state = _closed(
            record["reference_state"],
            frozenset(
                {
                    "acquisition_identity",
                    "connection_verification",
                    "kind",
                    "terminal_identity",
                }
            ),
            "failure cleanup reference state",
        )
        kind = reference_state["kind"]
        if kind == "HELD":
            reference_state["acquisition_identity"] = _identity(
                reference_state["acquisition_identity"],
                "failure cleanup reference acquisition",
            )
            if (
                type(reference_state["connection_verification"]) is not dict
                or reference_state["terminal_identity"] != "absent"
            ):
                raise FormalSuccessVerificationError(
                    "held failure reference state is malformed"
                )
            retained = True
        elif kind == "NO_REFERENCE_OPENED":
            if (
                reference_state["acquisition_identity"] != "absent"
                or reference_state["connection_verification"] != "absent"
                or reference_state["terminal_identity"] != "absent"
            ):
                raise FormalSuccessVerificationError(
                    "no-reference failure state is malformed"
                )
            retained = False
        elif kind == "CONNECTION_UNCERTAIN_DROPPED":
            if (
                reference_state["connection_verification"] != "absent"
                or type(reference_state["terminal_identity"]) is not dict
            ):
                raise FormalSuccessVerificationError(
                    "uncertain failure reference state is malformed"
                )
            reference_state["terminal_identity"] = _identity(
                reference_state["terminal_identity"],
                "failure cleanup uncertain connection terminal",
            )
            if reference_state["acquisition_identity"] != "absent":
                reference_state["acquisition_identity"] = _identity(
                    reference_state["acquisition_identity"],
                    "failure cleanup uncertain acquisition",
                )
            retained = False
        else:
            raise FormalSuccessVerificationError(
                "failure cleanup reference state kind drifted"
            )
        quiescence = closeout_state.validate_runtime_quiescence(
            record["runtime_quiescence"],
            ledger=ledger,
            reference_retained=retained,
        )
        errors = closeout_state.validate_failure_list(
            record["errors"],
            "failure cleanup",
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"failure cleanup evidence replay failed: {exc}"
        ) from exc

    optional = {
        "containment_clearance_identity": _cleanup_identity(
            record["containment_clearance_identity"],
            "failure cleanup containment_clearance_identity",
        ),
        "containment_hold_identity": _cleanup_identity(
            record["containment_hold_identity"],
            "failure cleanup containment_hold_identity",
        ),
        "containment_lock_release_identity": _cleanup_identity(
            record["containment_lock_release_identity"],
            "failure cleanup containment_lock_release_identity",
            allow_unrecorded=True,
        ),
    }
    publication: dict[str, object] | str
    if record["containment_lock_release_publication"] == "absent":
        publication = "absent"
    else:
        try:
            publication = closeout_state._validate_publication_effect_record(  # noqa: SLF001
                record["containment_lock_release_publication"],
                "containment lock release",
            )
        except Exception as exc:
            raise FormalSuccessVerificationError(
                f"containment lock release publication replay failed: {exc}"
            ) from exc
    containment = phase in {
        "CONTAINMENT_HOLD",
        "BARRIER_FAILED_OR_UNCERTAIN_CONTAINMENT_HOLD",
    }
    if containment:
        hold_recorded = type(optional["containment_hold_identity"]) is dict
        clearance_recorded = type(optional["containment_clearance_identity"]) is dict
        lock_state = optional["containment_lock_release_identity"]
        if (
            not hold_recorded
            or not clearance_recorded
            or lock_state != "absent"
            or publication != "absent"
        ):
            raise FormalSuccessVerificationError(
                "containment pre-release cleanup topology drifted"
            )
    elif (
        any(item != "absent" for item in optional.values())
        or publication != "absent"
    ):
        raise FormalSuccessVerificationError(
            "direct failure cleanup includes containment-only evidence"
        )

    joins = incomplete.get("joins")
    if type(joins) is dict:
        if (
            "frozen_outer_identity" in joins
            and ledger["outer"] != joins["frozen_outer_identity"]
        ):
            raise FormalSuccessVerificationError(
                "failure cleanup outer ledger drifted from incomplete"
            )
        if (
            "child_audit_identity" in joins
            and ledger["child_audit_identity"] != joins["child_audit_identity"]
        ):
            raise FormalSuccessVerificationError(
                "failure cleanup child ledger drifted from incomplete"
            )
    elif containment:
        raise FormalSuccessVerificationError(
            "containment failure cleanup lacks incomplete joins"
        )

    if (
        record["frozen_ledger"] != ledger
        or record["runtime_quiescence"] != quiescence
        or record["errors"] != errors
        or record["reference_state"] != reference_state
    ):
        raise FormalSuccessVerificationError(
            "failure cleanup ledger/quiescence/reference join drifted"
        )
    if reference_state["kind"] == "NO_REFERENCE_OPENED":
        effects = incomplete.get("effects")
        if type(effects) is dict and (
            effects["acquire_attempted"] is not False
            or effects["connection_action"] != ""
        ):
            raise FormalSuccessVerificationError(
                "no-reference cleanup contradicts irreversible effects"
            )

    return {
        **optional,
        "containment_lock_release_publication": publication,
        "errors": errors,
        "frozen_ledger": ledger,
        "reference_state": reference_state,
        "runtime_quiescence": quiescence,
    }


def validate_pre_release_success(
    value: object,
    *,
    context: Mapping[str, object],
    selection_identity: Mapping[str, object],
    expected_lock_identities: object,
) -> dict[str, object]:
    """Validate the detached substantive replay without claiming lock release."""

    record = _closed(value, DETACHED_SUCCESS_FIELDS, "pre-release success")
    record["child_audit_identity"] = _identity(
        record["child_audit_identity"],
        "pre-release child audit",
    )
    record["controller_result_identity"] = _identity(
        record["controller_result_identity"],
        "pre-release controller result",
    )
    record["formal_selection_identity"] = _identity(
        record["formal_selection_identity"],
        "pre-release formal selection",
    )
    record["terminal_classification_identity"] = _identity(
        record["terminal_classification_identity"],
        "pre-release terminal classification",
    )
    phase_identities = _closed(
        record["phase_receipt_identities"],
        frozenset(PRE_RELEASE_PHASES),
        "pre-release phase identities",
    )
    record["phase_receipt_identities"] = {
        phase: _identity(phase_identities[phase], f"pre-release {phase}")
        for phase in PRE_RELEASE_PHASES
    }
    record["lock_identities"] = _lock_identities(record["lock_identities"])
    lifecycle = _closed(
        record["lock_lifecycle"],
        frozenset(
            {
                "guardian_close_is_next_required_step",
                "reference_connection_must_remain_open",
                "refunit_must_remain_held",
                "supervisor_lock_release_permitted",
                "supervisor_locks_must_remain_held",
            }
        ),
        "pre-release lock lifecycle",
    )
    _utc(record["created_at_utc"], "pre-release created_at_utc")
    if (
        record["schema_version"] != SUCCESS_RECEIPT_SCHEMA
        or record["status"] != "PRE_RELEASE_VERIFIED"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != context["campaign_root_identity"]
        or record["formal_selection_identity"] != dict(selection_identity)
        or record["package_id"] != context["package_id"]
        or record["repository_head"] != context["repository_head"]
        or record["lock_identities"]
        != _lock_identities(expected_lock_identities)
        or lifecycle["guardian_close_is_next_required_step"] is not True
        or lifecycle["reference_connection_must_remain_open"] is not True
        or lifecycle["refunit_must_remain_held"] is not True
        or lifecycle["supervisor_lock_release_permitted"] is not False
        or lifecycle["supervisor_locks_must_remain_held"] is not True
        or record["upper_bound"] != [1188, 18]
        or record["lower_bound"] != "absent"
        or record["production_certified"] is not False
        or record["b6_changed"] is not False
        or record["bounds_changed"] is not False
        or record["stage_b_changed"] is not False
        or record["production_authority_changed"] is not False
        or record["verdict"]
        != "AB16_FORMAL_SUBSTANTIVE_REPLAY_VERIFIED_LOCKS_STILL_REQUIRED"
    ):
        raise FormalSuccessVerificationError(
            "pre-release success crossed its claim or lock-lifecycle boundary"
        )
    record["lock_lifecycle"] = lifecycle
    return record


def _validate_prior_success_output(
    value: object,
    *,
    context: Mapping[str, object],
    phase: str,
    selection_identity: Mapping[str, object] | None,
    expected_lock_identities: object,
) -> dict[str, object] | str:
    """Bind, but never authorize from, a success output preceding failure."""

    path = Path(str(context["outer_spec"]["receipt_paths"]["detached_closeout"]))
    if value == "absent":
        if os.path.lexists(path):
            raise FormalSuccessVerificationError(
                "failure claims detached success absent but its path exists"
            )
        return "absent"
    if selection_identity is None:
        raise FormalSuccessVerificationError(
            "preselection failure cannot bind a detached success output"
        )
    identity = _identity(value, "prior detached success output")
    raw, read_identity = _read_record(
        path,
        expected_identity=identity,
        label="prior detached success output",
    )
    validate_pre_release_success(
        raw,
        context=context,
        selection_identity=selection_identity,
        expected_lock_identities=expected_lock_identities,
    )
    permitted_phases = {
        "DETACHED_SUCCESS_VERIFIER_FAILED_OR_UNCERTAIN",
        "GUARDIAN_CLOSE_NOT_ATTEMPTED",
        "GUARDIAN_CLOSE_FAILED_OR_UNCERTAIN",
        "GUARDIAN_ABSENCE_UNPROVED",
        "SUPERVISOR_LOCK_RELEASE_NOT_ATTEMPTED",
        "SUPERVISOR_LOCK_RELEASE_FAILED_OR_UNCERTAIN",
        "DUAL_LOCK_RELEASE_RECEIPT_NOT_ATTEMPTED",
        "DUAL_LOCK_RELEASE_RECEIPT_FAILED_OR_UNCERTAIN",
        "FINAL_SUCCESS_RETURN_FAILED_OR_UNCERTAIN",
    }
    if (
        phase not in permitted_phases
        or identity["path"] != str(path)
        or read_identity != identity
    ):
        raise FormalSuccessVerificationError(
            "prior detached success output crossed the consumed-failure boundary"
        )
    return identity


def validate_failure_release(
    value: object,
    *,
    context: Mapping[str, object],
    expected_identity: Mapping[str, object],
    expected_incomplete: Mapping[str, object],
    expected_incomplete_identity: Mapping[str, object],
    expected_marker_identity: Mapping[str, object] | None,
    expected_selection_identity: Mapping[str, object] | None,
    expected_lock_identities: object,
) -> dict[str, object]:
    """Validate the final producer aggregate without trusting its conclusions."""

    record = _closed(value, FAILURE_RELEASE_FIELDS, "formal failure release")
    identity = _identity(expected_identity, "formal failure release")
    incomplete = _identity(expected_incomplete_identity, "failure incomplete")
    locks = _lock_identities(record["lock_identities"])
    expected_locks = _lock_identities(expected_lock_identities)
    lifecycle = _closed(
        record["lock_lifecycle"],
        frozenset(
            {
                "detached_incomplete_is_next_required_step",
                "guardian_absence_required_after_detached",
                "raw_lock_release_required_after_guardian_absence",
                "reference_completion_required_after_raw_release",
                "supervisor_lock_release_permitted",
                "supervisor_locks_must_remain_held",
            }
        ),
        "pre-release failure lock lifecycle",
    )
    marker: dict[str, object] | str = (
        "absent"
        if expected_marker_identity is None
        else dict(expected_marker_identity)
    )
    selection: dict[str, object] | str = (
        "absent"
        if expected_selection_identity is None
        else dict(expected_selection_identity)
    )
    phase = record["phase"]
    if type(phase) is not str or not phase:
        raise FormalSuccessVerificationError("formal failure release phase is malformed")
    cleanup = _validate_cleanup_evidence(
        record["cleanup_evidence"],
        context=context,
        incomplete=expected_incomplete,
        phase=phase,
    )
    if cleanup["reference_state"]["kind"] == "HELD":
        if expected_selection_identity is None:
            raise FormalSuccessVerificationError(
                "held failure RefUnit lacks a formal selection"
            )
        acquisition_identity = cleanup["reference_state"][
            "acquisition_identity"
        ]
        acquisition_raw, acquisition_readback = _read_record(
            acquisition_identity["path"],
            expected_identity=acquisition_identity,
            label="failure retained reference acquisition",
        )
        outer = cleanup["frozen_ledger"]["outer"]
        expected_outer = {
            key: outer[key]
            for key in (
                "control_group",
                "invocation_id",
                "processes",
                "unit_name",
            )
        }
        acquisition = validate_reference_acquisition(
            acquisition_raw,
            expected={
                "campaign_root_identity": context["campaign_root_identity"],
                "formal_selection_identity": expected_selection_identity,
                "manager_epoch": context["manager_epoch"],
                "package_id": context["package_id"],
            },
            expected_outer_identity=expected_outer,
            expected_lock_identities=expected_locks,
            transcript_validator=None,
        )
        if (
            acquisition_readback != acquisition_identity
            or acquisition_identity["path"]
            != str(Path(str(context["formal_attempt_dir"])) / "reference-acquisition.json")
            or acquisition["connection_verification"]
            != cleanup["reference_state"]["connection_verification"]
        ):
            raise FormalSuccessVerificationError(
                "held failure RefUnit acquisition/connection join drifted"
            )
    prior_success = _validate_prior_success_output(
        record["detached_success_output_identity"],
        context=context,
        phase=phase,
        selection_identity=expected_selection_identity,
        expected_lock_identities=expected_lock_identities,
    )
    _utc(record["created_at_utc"], "formal failure release created_at_utc")
    if (
        record["schema_version"] != FAILURE_RELEASE_SCHEMA
        or record["status"] != "INCOMPLETE_PRE_RELEASE"
        or record["outcome"] != "INCOMPLETE"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != context["campaign_root_identity"]
        or record["package_id"] != context["package_id"]
        or record["formal_selection_identity"] != selection
        or record["attempt_marker_identity"] != marker
        or record["incomplete_identity"] != incomplete
        or record["attempt_directory_created"] is not True
        or record["runtime_quiescent"] is not True
        or record["reference_retained"]
        is not (
            cleanup["reference_state"]["kind"] == "HELD"
        )
        or record["retry_eligible"] is not False
        or record["success_eligible"] is not False
        or record["b6_changed"] is not False
        or record["bounds_changed"] is not False
        or record["production_authority_changed"] is not False
        or record["stage_b_changed"] is not False
        or record["upper_bound"] != [1188, 18]
        or record["lower_bound"] != "absent"
        or record["production_certified"] is not False
        or locks != expected_locks
        or lifecycle["detached_incomplete_is_next_required_step"] is not True
        or lifecycle["guardian_absence_required_after_detached"] is not True
        or lifecycle["raw_lock_release_required_after_guardian_absence"] is not True
        or lifecycle["reference_completion_required_after_raw_release"]
        is not record["reference_retained"]
        or lifecycle["supervisor_lock_release_permitted"] is not False
        or lifecycle["supervisor_locks_must_remain_held"] is not True
        or identity["path"]
        != str(Path(str(context["formal_attempt_dir"])) / "failure-release.json")
    ):
        raise FormalSuccessVerificationError(
            "pre-release failure authority/topology/lock join drifted"
        )
    record["cleanup_evidence"] = cleanup
    record["detached_success_output_identity"] = prior_success
    record["lock_identities"] = locks
    record["lock_lifecycle"] = lifecycle
    return record


def validate_failure_terminal_release(
    value: object,
    *,
    context: Mapping[str, object],
    expected_identity: Mapping[str, object],
    expected_lock_identities: object,
    expected_detached_substantive_identity: Mapping[str, object],
    expected_detached_substantive_kind: str,
    expected_failure_pre_release_identity: Mapping[str, object] | str,
    expected_selection_identity: Mapping[str, object] | None,
    expected_guardian_absence_identity: Mapping[str, object],
    expected_raw_lock_release_identity: Mapping[str, object],
    expected_reference_completion: Mapping[str, object],
    expected_post_root_closure: Mapping[str, object],
) -> dict[str, object]:
    """Validate the sole post-release INCOMPLETE terminal join."""

    record = _closed(
        value,
        FAILURE_TERMINAL_RELEASE_FIELDS,
        "formal failure terminal release",
    )
    identity = _identity(expected_identity, "formal failure terminal release")
    locks = _lock_identities(record["lock_identities"])
    expected_locks = _lock_identities(expected_lock_identities)
    effect = _closed(
        record["lock_release_effect"],
        frozenset({"lock_identities", "released"}),
        "failure terminal lock release effect",
    )
    effect["lock_identities"] = _lock_identities(effect["lock_identities"])
    detached = _identity(
        record["detached_substantive_identity"],
        "failure terminal detached substantive replay",
    )
    expected_detached = _identity(
        expected_detached_substantive_identity,
        "expected failure terminal detached substantive replay",
    )
    if expected_failure_pre_release_identity == "absent":
        failure_pre_release: dict[str, object] | str = "absent"
    else:
        failure_pre_release = _identity(
            expected_failure_pre_release_identity,
            "expected pre-release failure",
        )
    guardian_absence = _identity(
        expected_guardian_absence_identity,
        "expected failure guardian absence",
    )
    raw_release = _identity(
        expected_raw_lock_release_identity,
        "expected failure raw lock release",
    )
    completion = _closed(
        expected_reference_completion,
        frozenset(
            {
                "kind",
                "post_unref_absence_identity",
                "reference_connection_close_identity",
                "reference_release_identity",
                "reference_terminal_identity",
                "uncertainty_terminal",
            }
        ),
        "expected failure reference completion",
    )
    completion_kind = completion["kind"]
    closure_evidence = validate_post_root_closure_evidence(
        record["post_root_closure"],
        expected_branch="incomplete",
    )
    expected_closure_evidence = validate_post_root_closure_evidence(
        expected_post_root_closure,
        expected_branch="incomplete",
    )
    identity_fields = (
        "post_unref_absence_identity",
        "reference_connection_close_identity",
        "reference_release_identity",
        "reference_terminal_identity",
    )
    if completion_kind == "RECORDED_CONNECTION_CLOSED":
        for field in identity_fields:
            completion[field] = _identity(
                completion[field],
                f"failure reference completion {field}",
            )
        if completion["uncertainty_terminal"] != "absent":
            raise FormalSuccessVerificationError(
                "closed failure reference completion contains uncertainty"
            )
    elif completion_kind == "NO_REFERENCE_OPENED":
        if any(completion[field] != "absent" for field in identity_fields) or (
            completion["uncertainty_terminal"] != "absent"
        ):
            raise FormalSuccessVerificationError(
                "no-reference failure completion contains reference evidence"
            )
    elif completion_kind == "CONNECTION_UNCERTAIN":
        for field in identity_fields:
            if completion[field] not in {"absent", "unrecorded"}:
                completion[field] = _identity(
                    completion[field],
                    f"uncertain failure reference completion {field}",
                )
        if type(completion["uncertainty_terminal"]) is not dict:
            raise FormalSuccessVerificationError(
                "uncertain failure completion lacks terminal evidence"
            )
        completion["uncertainty_terminal"] = (
            closeout_state._validate_reference_terminal(  # noqa: SLF001
                completion["uncertainty_terminal"]
            )
        )
        if completion["uncertainty_terminal"]["kind"] in {
            "NO_REFERENCE_OPENED",
            "RECORDED",
        }:
            raise FormalSuccessVerificationError(
                "uncertain failure completion claims a certain terminal"
            )
    else:
        raise FormalSuccessVerificationError(
            "failure reference completion kind drifted"
        )
    selection: dict[str, object] | str = (
        "absent"
        if expected_selection_identity is None
        else dict(expected_selection_identity)
    )
    terminal_join = _closed(
        record["terminal_join"],
        frozenset(
            {
                "detached_substantive_before_guardian_absence",
                "formal_root_closed_before_outside_replays",
                "guardian_absence_before_raw_lock_release",
                "outside_replays_before_final_join",
                "raw_lock_release_before_reference_completion",
                "recovery_disarmed_before_manifest",
                "broker_absent_before_manifest",
                "reference_connection_close_before_final_join",
                "reference_uncertainty_is_terminal",
            }
        ),
        "failure terminal join",
    )
    attempt = Path(str(context["formal_attempt_dir"]))
    raw_path = str(
        context["outer_spec"]["receipt_paths"]["supervisor_raw_lock_release"]
    )
    if expected_detached_substantive_kind == "incomplete_v4":
        topology_valid = (
            type(failure_pre_release) is dict
            and failure_pre_release["path"] == str(attempt / "failure-release.json")
            and detached["path"]
            == str(attempt / "detached-incomplete-closeout.json")
            and guardian_absence["path"]
            == str(attempt / "containment-guardian-absence.json")
            and raw_release["path"] == raw_path
        )
    elif expected_detached_substantive_kind == "success_v3":
        topology_valid = (
            failure_pre_release == "absent"
            and detached["path"]
            == str(context["outer_spec"]["receipt_paths"]["detached_closeout"])
            and guardian_absence["path"]
            == str(context["outer_spec"]["receipt_paths"]["guardian_absence"])
            and raw_release["path"] == raw_path
        )
    else:
        topology_valid = False
    if completion_kind == "RECORDED_CONNECTION_CLOSED":
        topology_valid = topology_valid and all(
            completion[field]["path"]
            == str(context["outer_spec"]["receipt_paths"][path_key])
            for field, path_key in (
                ("post_unref_absence_identity", "post_unref_absence"),
                (
                    "reference_connection_close_identity",
                    "reference_connection_close",
                ),
                ("reference_release_identity", "reference_release"),
                ("reference_terminal_identity", "reference_terminal"),
            )
        )
    _utc(record["created_at_utc"], "formal failure terminal created_at_utc")
    if (
        record["schema_version"] != FAILURE_TERMINAL_RELEASE_SCHEMA
        or record["status"] != "INCOMPLETE_RELEASED"
        or record["outcome"] != "INCOMPLETE"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != context["campaign_root_identity"]
        or record["package_id"] != context["package_id"]
        or record["formal_selection_identity"] != selection
        or record["detached_substantive_identity"] != expected_detached
        or detached != expected_detached
        or record["detached_substantive_kind"]
        != expected_detached_substantive_kind
        or record["failure_pre_release_identity"] != failure_pre_release
        or record["guardian_absence_identity"] != guardian_absence
        or record["supervisor_raw_lock_release_identity"] != raw_release
        or record["reference_completion"] != completion
        or closure_evidence != expected_closure_evidence
        or topology_valid is not True
        or locks != expected_locks
        or effect["lock_identities"] != expected_locks
        or effect["released"] is not True
        or terminal_join["detached_substantive_before_guardian_absence"]
        is not True
        or terminal_join["guardian_absence_before_raw_lock_release"]
        is not True
        or terminal_join["raw_lock_release_before_reference_completion"]
        is not True
        or terminal_join["reference_connection_close_before_final_join"]
        is not (completion_kind == "RECORDED_CONNECTION_CLOSED")
        or terminal_join["reference_uncertainty_is_terminal"]
        is not (
            completion_kind in {"CONNECTION_UNCERTAIN", "NO_REFERENCE_OPENED"}
        )
        or terminal_join["formal_root_closed_before_outside_replays"]
        is not True
        or terminal_join["outside_replays_before_final_join"] is not True
        or terminal_join["recovery_disarmed_before_manifest"] is not True
        or terminal_join["broker_absent_before_manifest"] is not True
        or record["retry_eligible"] is not False
        or record["success_eligible"] is not False
        or record["b6_changed"] is not False
        or record["bounds_changed"] is not False
        or record["production_authority_changed"] is not False
        or record["stage_b_changed"] is not False
        or record["upper_bound"] != [1188, 18]
        or record["lower_bound"] != "absent"
        or record["production_certified"] is not False
        or identity["path"]
        != str(
            Path(str(context["formal_attempt_dir"]))
            / "failure-terminal-release.json"
        )
    ):
        raise FormalSuccessVerificationError(
            "failure terminal authority/topology/lock join drifted"
        )
    record["detached_substantive_identity"] = detached
    record["lock_identities"] = locks
    record["lock_release_effect"] = effect
    record["reference_completion"] = completion
    record["post_root_closure"] = closure_evidence
    record["terminal_join"] = terminal_join
    return record


def _validate_containment_failure_chain(
    *,
    context: Mapping[str, object],
    incomplete: Mapping[str, object],
    incomplete_identity: Mapping[str, object],
    guardian_absence: Mapping[str, object],
    guardian_absence_identity: Mapping[str, object],
    cleanup_evidence: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    """Replay the fixed hold/clearance records before any supervisor lock release."""

    attempt = Path(str(context["formal_attempt_dir"]))
    hold_expected = _identity(
        cleanup_evidence["containment_hold_identity"],
        "failure cleanup containment hold",
    )
    clearance_expected = _identity(
        cleanup_evidence["containment_clearance_identity"],
        "failure cleanup containment clearance",
    )
    fixed_paths = {
        "hold": attempt / "containment-hold.json",
        "clearance": attempt / "containment-cleared-after-hold.json",
    }
    if (
        hold_expected["path"] != str(fixed_paths["hold"])
        or clearance_expected["path"] != str(fixed_paths["clearance"])
    ):
        raise FormalSuccessVerificationError(
            "containment cleanup identity escaped fixed paths"
        )
    hold_raw, hold_identity = _read_record(
        fixed_paths["hold"],
        expected_identity=hold_expected,
        label="containment hold",
    )
    clearance_raw, clearance_identity = _read_record(
        fixed_paths["clearance"],
        expected_identity=clearance_expected,
        label="containment clearance",
    )
    hold_fields = closeout_state.BASE_FIELDS | frozenset(
        {
            "attempt_incomplete_identity",
            "errors",
            "experiment_progress_active",
            "failure",
            "frozen_ledger",
            "isolation_active",
            "lock_identities",
            "outcome",
            "poll_interval_seconds",
            "reference_terminal",
            "schema_version",
            "status",
            "success_eligible",
            "supervisor",
        }
    )
    clearance_fields = closeout_state.BASE_FIELDS | frozenset(
        {
            "containment_hold_identity",
            "final_observation",
            "lock_identities",
            "outcome",
            "schema_version",
            "status",
            "success_eligible",
        }
    )
    hold = _closed(hold_raw, hold_fields, "containment hold")
    clearance = _closed(clearance_raw, clearance_fields, "containment clearance")
    for label, record in (
        ("containment hold", hold),
        ("containment clearance", clearance),
    ):
        _state_base(record, context=context, label=label)
    effects = cast(Mapping[str, object], incomplete["effects"])
    joins = cast(Mapping[str, object], incomplete["joins"])
    try:
        ledger = closeout_state.validate_frozen_ledger(hold["frozen_ledger"])
        ledger["child_audit_identity"] = _identity(
            ledger["child_audit_identity"],
            "containment child audit",
        )
        observation = closeout_state.validate_absence_observation(
            clearance["final_observation"],
            ledger=ledger,
        )
        hold_errors = closeout_state.validate_failure_list(
            hold["errors"],
            "containment hold",
        )
        hold_failure = closeout_state.validate_failure_record(
            hold["failure"],
            "containment hold",
        )
        reference_terminal = closeout_state._validate_reference_terminal(  # noqa: SLF001
            hold["reference_terminal"]
        )
        closeout_state._validate_reference_terminal_joins(  # noqa: SLF001
            reference_terminal,
            effects=effects,
            joins=joins,
            errors=hold_errors,
        )
        supervisor = closeout_state._validate_supervisor(  # noqa: SLF001
            hold["supervisor"]
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"containment structural replay failed: {exc}"
        ) from exc
    hold_locks = _lock_identities(hold["lock_identities"])
    clearance_locks = _lock_identities(clearance["lock_identities"])
    ledger_sha = hashlib.sha256(authority.canonical_json(ledger)).hexdigest()
    if (
        hold["schema_version"] != closeout_state.HOLD_SCHEMA
        or hold["status"] != "CONTAINMENT_HOLD"
        or hold["attempt_incomplete_identity"] != dict(incomplete_identity)
        or hold_failure != incomplete["failure"]
        or hold["frozen_ledger"] != ledger
        or hold["errors"] != hold_errors
        or hold["reference_terminal"] != reference_terminal
        or hold["supervisor"] != supervisor
        or hold["experiment_progress_active"] is not False
        or hold["isolation_active"] is not True
        or hold["outcome"] != "INCOMPLETE"
        or hold["poll_interval_seconds"] != closeout_state.HOLD_POLL_SECONDS
        or hold["success_eligible"] is not False
        or ledger["child_audit_identity"] != joins.get("child_audit_identity")
        or ledger["outer"] != joins.get("frozen_outer_identity")
        or guardian_absence["frozen_ledger_sha256"] != ledger_sha
        or cleanup_evidence["frozen_ledger"] != ledger
        or cleanup_evidence["final_observation"] != observation
        or cleanup_evidence["reference_terminal"] != reference_terminal
        or any(item not in cleanup_evidence["errors"] for item in hold_errors)
        or clearance["schema_version"] != closeout_state.HOLD_CLEAR_SCHEMA
        or clearance["status"] != "CONTAINMENT_CLEARED_AFTER_HOLD"
        or clearance["containment_hold_identity"] != hold_identity
        or clearance["final_observation"] != observation
        or clearance["outcome"] != "INCOMPLETE"
        or clearance["success_eligible"] is not False
        or hold_locks != clearance_locks
        or cleanup_evidence["containment_lock_release_identity"] != "absent"
        or cleanup_evidence["containment_lock_release_publication"] != "absent"
        or hold_identity != hold_expected
        or clearance_identity != clearance_expected
    ):
        raise FormalSuccessVerificationError(
            "containment hold/clearance/guardian pre-release join drifted"
        )
    return {
        "containment_clearance": clearance_identity,
        "containment_hold": hold_identity,
    }


def validate_controller_result(
    value: object,
    *,
    context: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> dict[str, object]:
    record = _closed(value, CONTROLLER_RESULT_FIELDS, "formal controller result")
    if (
        record["schema_version"] != CONTROLLER_RESULT_SCHEMA
        or record["status"] != "PASS"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != context["campaign_root_identity"]
        or record["formal_selection_identity"] != dict(selection_identity)
        or record["package_id"] != context["package_id"]
    ):
        raise FormalSuccessVerificationError("formal controller result common join drifted")
    for field in (
        "barrier_identity",
        "manifest_identity",
        "suite_selection_identity",
        "terminal_classification_identity",
    ):
        record[field] = _identity(record[field], f"controller {field}")
    gate1 = _closed(
        record["gate1"],
        frozenset({"continuation_identity", "gate_identity", "unit_order"}),
        "controller Gate1 result",
    )
    gate1["continuation_identity"] = _identity(
        gate1["continuation_identity"],
        "controller Gate1 continuation",
    )
    gate1["gate_identity"] = _identity(gate1["gate_identity"], "controller Gate1 gate")
    if gate1["unit_order"] != list(GATE1_SLOTS):
        raise FormalSuccessVerificationError("controller Gate1 unit order drifted")
    baseline = _closed(record["baseline"], BASELINE_FIELDS, "controller baseline")
    for field in BASELINE_FIELDS:
        baseline[field] = _identity(baseline[field], f"controller baseline {field}")
    arms = record["arm_results"]
    if type(arms) is not list or len(arms) != len(ARM_SEQUENCE):
        raise FormalSuccessVerificationError("controller arm result count drifted")
    checked_arms: list[dict[str, object]] = []
    for ordinal, (slot, raw) in enumerate(zip(ARM_SEQUENCE, arms, strict=True), start=1):
        arm = _closed(raw, ARM_RESULT_FIELDS, f"controller arm {slot}")
        if arm["slot"] != slot or arm["ordinal"] != ordinal:
            raise FormalSuccessVerificationError(f"controller arm order drifted: {slot}")
        for field in ARM_RESULT_FIELDS - {
            "ordinal",
            "resource_admission",
            "slot",
            "suite_terminal_identity",
        }:
            arm[field] = _identity(arm[field], f"controller arm {slot}.{field}")
        prelaunch, _prelaunch_identity = _read_record(
            arm["prelaunch_receipt_identity"]["path"],
            expected_identity=arm["prelaunch_receipt_identity"],
            label=f"controller arm {slot} prelaunch receipt",
        )
        try:
            arm["resource_admission"] = (
                resource_admission.validate_launch_resource_reevaluation(
                    arm["resource_admission"],
                    expected_receipt=prelaunch["resource_admission"],
                )
            )
        except (KeyError, resource_admission.ResourceAdmissionError) as exc:
            raise FormalSuccessVerificationError(
                f"controller arm {slot} launch resource evidence drifted"
            ) from exc
        terminal = arm["suite_terminal_identity"]
        if terminal is None:
            if ordinal == len(ARM_SEQUENCE):
                raise FormalSuccessVerificationError("final controller arm lacks suite terminal")
        else:
            arm["suite_terminal_identity"] = _identity(
                terminal,
                f"controller arm {slot}.suite terminal",
            )
            if ordinal != len(ARM_SEQUENCE):
                raise FormalSuccessVerificationError("non-final controller arm has suite terminal")
        checked_arms.append(arm)
    if checked_arms[-1]["suite_terminal_identity"] != record["terminal_classification_identity"]:
        raise FormalSuccessVerificationError("controller terminal classification join drifted")
    record["gate1"] = gate1
    record["baseline"] = baseline
    record["arm_results"] = checked_arms
    return record


def _validate_child_audit(
    value: object,
    *,
    controller: Mapping[str, object],
) -> dict[str, object]:
    fields = frozenset(
        {
            "all_children_absent",
            "audit_errors",
            "authorizations",
            "containment_used",
            "final_observation",
            "frozen_children",
            "mode",
            "normal_replay",
            "records",
            "schema_version",
            "status",
        }
    )
    record = _closed(value, fields, "finite child audit")
    if (
        record["schema_version"] != CHILD_AUDIT_SCHEMA
        or record["status"] != "PASS"
        or record["all_children_absent"] is not True
        or record["containment_used"] is not False
        or record["mode"] != "NORMAL_REPLAY"
        or record["audit_errors"] != []
        or record["authorizations"] != REFERENCE_FALSE_AUTHORIZATIONS
    ):
        raise FormalSuccessVerificationError("finite child audit is not a normal all-absence replay")
    records = record["records"]
    frozen = record["frozen_children"]
    if (
        type(records) is not list
        or type(frozen) is not list
        or len(records) != len(EXPECTED_CHILD_ORDER)
        or len(frozen) != len(EXPECTED_CHILD_ORDER)
    ):
        raise FormalSuccessVerificationError("finite child audit cardinality drifted")
    for index, ((source, slot), item, frozen_item) in enumerate(
        zip(EXPECTED_CHILD_ORDER, records, frozen, strict=True)
    ):
        expected_fields = {
            "classification",
            "frozen_identity",
            "inner_path",
            "prelaunch_evidence",
            "prelaunch_owned",
            "slot",
            "source",
            "systemctl",
            "unit_name",
        }
        if type(item) is not dict or set(item) != expected_fields:
            raise FormalSuccessVerificationError(f"child audit record {index} field set drifted")
        if (
            item["source"] != source
            or item["slot"] != slot
            or item["classification"] != "ABSENT"
            or item["prelaunch_owned"] is not True
            or item["systemctl"] != ABSENT_SYSTEMD
            or item["frozen_identity"] != frozen_item
        ):
            raise FormalSuccessVerificationError(f"child audit record {source}/{slot} drifted")
    observation = _validate_absence_observation(
        record["final_observation"],
        expected_frozen=[
            *frozen,
            {
                "control_group": "",
                "identity_complete": True,
                "processes": [],
                "slot": "formal",
                "source": "outer",
                "unit_name": "",
            },
        ],
        label="child final observation",
    )
    record["final_observation"] = observation
    normal = _closed(
        record["normal_replay"],
        frozenset(
            {
                "arm_cleanup_replay",
                "gate1_continuation_identity",
                "gate1_detached_identities",
            }
        ),
        "child normal replay",
    )
    normal["gate1_continuation_identity"] = _identity(
        normal["gate1_continuation_identity"],
        "child Gate1 continuation",
    )
    if normal["gate1_continuation_identity"] != controller["gate1"]["continuation_identity"]:
        raise FormalSuccessVerificationError("child audit Gate1 continuation join drifted")
    arms = normal["arm_cleanup_replay"]
    if type(arms) is not dict or set(arms) != set(ARM_SEQUENCE):
        raise FormalSuccessVerificationError("child audit arm cleanup slot set drifted")
    for selected in controller["arm_results"]:
        replay = arms[selected["slot"]]
        if (
            type(replay) is not dict
            or set(replay)
            != {"consumption_id", "resource_replay_identity", "resource_terminal_identity"}
            or replay["resource_terminal_identity"] != selected["resource_terminal_identity"]
        ):
            raise FormalSuccessVerificationError(
                f"child audit arm cleanup join drifted: {selected['slot']}"
            )
    record["normal_replay"] = normal
    return record


def _validate_guardian_close(
    value: object,
    *,
    context: Mapping[str, object],
    selection_identity: Mapping[str, object],
    lock_identities: object,
    expected_frozen_children: Sequence[Mapping[str, object]],
    expected_outer_identity: Mapping[str, object],
    expected_child_audit_identity: Mapping[str, object],
) -> dict[str, object]:
    fields = frozenset(
        {
            "absence_observation",
            "authorizations",
            "campaign_root_identity",
            "close_effect",
            "errors",
            "formal_selection_identity",
            "frozen_ledger",
            "ledger_message_identity",
            "outcome",
            "package_id",
            "schema_version",
            "status",
            "success_eligible",
        }
    )
    record = _closed(value, fields, "guardian lock close")
    effect = _closed(
        record["close_effect"],
        frozenset(
            {
                "errors",
                "guardian_copies_closed",
                "lock_identities",
                "supervisor_copies_must_remain_held",
            }
        ),
        "guardian close effect",
    )
    effect["lock_identities"] = _lock_identities(effect["lock_identities"])
    try:
        ledger = closeout_state.validate_frozen_ledger(record["frozen_ledger"])
        ledger["child_audit_identity"] = _identity(
            ledger["child_audit_identity"],
            "guardian ledger child audit",
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"guardian frozen ledger failed: {exc}"
        ) from exc
    expected_outer = {
        "control_group": expected_outer_identity["control_group"],
        "identity_complete": True,
        "invocation_id": expected_outer_identity["invocation_id"],
        "ownership_classification": "OUTER_LIVE_VERIFIED",
        "processes": expected_outer_identity["processes"],
        "slot": "formal",
        "source": "outer",
        "unit_name": expected_outer_identity["unit_name"],
    }
    if (
        ledger["child_audit_identity"] != dict(expected_child_audit_identity)
        or ledger["children"] != list(expected_frozen_children)
        or ledger["outer"] != expected_outer
    ):
        raise FormalSuccessVerificationError(
            "guardian frozen ledger child/outer identity join drifted"
        )
    try:
        absence = closeout_state.validate_absence_observation(
            record["absence_observation"],
            ledger=ledger,
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"guardian absence observation failed: {exc}"
        ) from exc
    if (
        record["schema_version"] != GUARDIAN_LOCK_CLOSE_SCHEMA
        or record["status"] != "GUARDIAN_COPIES_CLOSED"
        or record["outcome"] != "SUCCESS_CANDIDATE"
        or record["success_eligible"] is not True
        or record["errors"] != []
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != context["campaign_root_identity"]
        or record["formal_selection_identity"] != dict(selection_identity)
        or record["package_id"] != context["package_id"]
        or effect["errors"] != []
        or effect["guardian_copies_closed"] is not True
        or effect["supervisor_copies_must_remain_held"] is not True
        or effect["lock_identities"] != _lock_identities(lock_identities)
    ):
        raise FormalSuccessVerificationError("guardian close/absence proof drifted")
    try:
        record["ledger_message_identity"] = launch_validator.validate_message_identity(
            record["ledger_message_identity"],
            "guardian ledger message",
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"guardian ledger message identity failed: {exc}"
        ) from exc
    ledger_bytes = authority.canonical_json(ledger)
    expected_ledger_message_identity = {
        "sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "size_bytes": len(ledger_bytes),
    }
    if record["ledger_message_identity"] != expected_ledger_message_identity:
        raise FormalSuccessVerificationError(
            "guardian ledger message identity does not bind frozen_ledger bytes"
        )
    record["close_effect"] = effect
    record["absence_observation"] = absence
    record["frozen_ledger"] = ledger
    return record


def _replay_controller_arms(
    *,
    campaign_dir: Path,
    controller: Mapping[str, object],
) -> None:
    for arm in controller["arm_results"]:
        slot = str(arm["slot"])
        for field in (
            "pre_run_authority_identity",
            "prelaunch_receipt_identity",
            "prelaunch_request_identity",
            "selection_identity",
        ):
            _read_record(
                arm[field]["path"],
                expected_identity=arm[field],
                label=f"{slot} {field}",
            )
        try:
            campaign_context = authority._campaign_context(campaign_dir)  # noqa: SLF001
            consumed = authority._load_consumption(  # noqa: SLF001
                campaign_context,
                slot=slot,
                required_credible=True,
            )
        except Exception as exc:
            raise FormalSuccessVerificationError(f"{slot} detached consumption replay failed: {exc}") from exc
        observed = _identity(
            authority.detached_identity(
                authority.snapshot_regular(arm["consumption_identity"]["path"])
            ),
            f"{slot} consumption",
        )
        if (
            observed != arm["consumption_identity"]
            or consumed["arm_gate_identity"] != arm["arm_gate_identity"]
            or consumed["resource_terminal_identity"] != arm["resource_terminal_identity"]
            or consumed["outcome"] != "CREDIBLE_TERMINAL"
        ):
            raise FormalSuccessVerificationError(f"{slot} controller/authority consumption join drifted")


def _publish_final_receipt(
    output: Path,
    record: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    identity = authority._write_exclusive(  # noqa: SLF001 - detached verifier is the sole writer
        output,
        authority.canonical_json(record),
        mode=0o444,
    )
    replay, replay_identity = _read_record(
        output,
        expected_identity=identity,
        label=label,
    )
    if replay != dict(record) or replay_identity != identity:
        raise FormalSuccessVerificationError(f"{label} readback drifted")
    return identity


def verify_incomplete(
    *,
    campaign_dir: Path | str,
    incomplete_release: Path | str,
) -> dict[str, object]:
    """Replay one permanent failure topology before supervisor lock release."""

    campaign = Path(campaign_dir).absolute()
    release_path = Path(incomplete_release).absolute()
    try:
        context = launch_validator.replay_formal_launch_context(authority, campaign)
        authority.replay_gate_approvals(campaign)
        authority.replay_repository_snapshot(campaign)
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"package/Gate-B/snapshot failure replay failed: {exc}"
        ) from exc
    attempt = Path(str(context["formal_attempt_dir"]))
    if release_path != attempt / "failure-release.json":
        raise FormalSuccessVerificationError(
            "failure-release path differs from the fixed formal attempt"
        )
    release_raw, release_identity = _read_record(
        release_path,
        expected_identity=None,
        label="formal failure release",
    )
    if type(release_raw) is not dict or set(release_raw) != set(FAILURE_RELEASE_FIELDS):
        raise FormalSuccessVerificationError("formal failure release field set drifted")

    raw_selection = release_raw["formal_selection_identity"]
    selection: dict[str, object] | None = None
    selection_identity: dict[str, object] | None = None
    if raw_selection != "absent":
        expected_selection = _identity(raw_selection, "failure formal selection")
        replayed_context, selection, selection_identity, _guardian_ready = _load_selection(
            campaign,
            Path(str(context["formal_selection_path"])),
        )
        if replayed_context != context or selection_identity != expected_selection:
            raise FormalSuccessVerificationError(
                "failure formal selection/package context join drifted"
            )
        expected_locks: object = selection["lock_identities"]
    else:
        if os.path.lexists(context["formal_selection_path"]):
            raise FormalSuccessVerificationError(
                "failure claims selection absent but the canonical path exists"
            )
        expected_locks = release_raw["lock_identities"]

    try:
        authority.replay(
            campaign,
            selection_required=selection_identity is not None,
        )
    except Exception as exc:
        raise FormalSuccessVerificationError(
            f"organic authority failure replay failed: {exc}"
        ) from exc

    raw_marker = release_raw["attempt_marker_identity"]
    marker_identity: dict[str, object] | None = None
    if raw_marker != "absent":
        marker_identity = _identity(raw_marker, "failure attempt marker")
        marker_raw, marker_read_identity = _read_record(
            marker_identity["path"],
            expected_identity=marker_identity,
            label="failure attempt marker",
        )
        try:
            launch_validator.validate_attempt_consumption(
                marker_raw,
                expected_context=context,
            )
        except Exception as exc:
            raise FormalSuccessVerificationError(
                f"failure attempt marker replay failed: {exc}"
            ) from exc
        if (
            marker_read_identity != marker_identity
            or marker_identity["path"] != str(attempt / "attempt-consumption.json")
        ):
            raise FormalSuccessVerificationError(
                "failure attempt marker path/identity drifted"
            )
        if (
            selection is not None
            and selection["attempt_consumption_identity"] != marker_identity
        ):
            raise FormalSuccessVerificationError(
                "formal selection/attempt marker identity drifted"
            )
    elif os.path.lexists(attempt / "attempt-consumption.json"):
        raise FormalSuccessVerificationError(
            "failure claims markerless consumption but the marker path exists"
        )

    incomplete_identity = _identity(
        release_raw["incomplete_identity"],
        "failure incomplete",
    )
    incomplete_raw, incomplete_read_identity = _read_record(
        incomplete_identity["path"],
        expected_identity=incomplete_identity,
        label="failure incomplete",
    )
    if incomplete_read_identity != incomplete_identity:
        raise FormalSuccessVerificationError("failure incomplete identity drifted")
    phase = release_raw["phase"]
    if type(phase) is not str or not phase:
        raise FormalSuccessVerificationError("failure phase is malformed")
    if marker_identity is None:
        incomplete = validate_markerless_incomplete(
            incomplete_raw,
            context=context,
            expected_identity=incomplete_identity,
            expected_phase=str(incomplete_raw.get("phase", "")),
        )
    else:
        incomplete = validate_consumed_incomplete(
            incomplete_raw,
            context=context,
            expected_identity=incomplete_identity,
            expected_marker_identity=marker_identity,
            expected_phase=str(incomplete_raw.get("phase", "")),
            expected_selection_identity=selection_identity,
        )

    release = validate_failure_release(
        release_raw,
        context=context,
        expected_identity=release_identity,
        expected_incomplete=incomplete,
        expected_incomplete_identity=incomplete_identity,
        expected_marker_identity=marker_identity,
        expected_selection_identity=selection_identity,
        expected_lock_identities=expected_locks,
    )
    final = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "b6_changed": False,
        "bounds_changed": False,
        "campaign_root_identity": context["campaign_root_identity"],
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "failure_phase": phase,
        "input_identities": {
            "attempt_consumption_identity": (
                marker_identity if marker_identity is not None else "absent"
            ),
            "failure_release_identity": release_identity,
            "formal_selection_identity": (
                selection_identity if selection_identity is not None else "absent"
            ),
            "incomplete_identity": incomplete_identity,
            "prior_detached_success_identity": release[
                "detached_success_output_identity"
            ],
        },
        "lower_bound": "absent",
        "package_id": context["package_id"],
        "production_authority_changed": False,
        "production_certified": False,
        "repository_head": context["repository_head"],
        "schema_version": INCOMPLETE_RECEIPT_SCHEMA,
        "stage_b_changed": False,
        "status": "PRE_RELEASE_VERIFIED_INCOMPLETE",
        "success_eligible": False,
        "upper_bound": [1188, 18],
        "verdict": (
            "AB16_FORMAL_INCOMPLETE_SUBSTANTIVE_REPLAY_VERIFIED_"
            "LOCKS_STILL_REQUIRED"
        ),
    }
    output = Path(
        str(context["outer_spec"]["receipt_paths"]["detached_incomplete_closeout"])
    )
    if output != attempt / "detached-incomplete-closeout.json":
        raise FormalSuccessVerificationError(
            "detached incomplete output escaped the preregistered attempt path"
        )
    identity = _publish_final_receipt(
        output,
        final,
        label="formal detached incomplete",
    )
    return {
        "detached_incomplete": final,
        "detached_incomplete_identity": identity,
        "status": "PRE_RELEASE_VERIFIED_INCOMPLETE",
    }


def verify_success(
    *,
    campaign_dir: Path | str,
    formal_selection: Path | str,
) -> dict[str, object]:
    """Replay substantive evidence before guardian close and lock release."""

    campaign = Path(campaign_dir).absolute()
    selection_path = Path(formal_selection).absolute()
    context, selection, selection_identity, guardian_ready = _load_selection(
        campaign,
        selection_path,
    )
    try:
        authority.replay_gate_approvals(campaign)
        authority.replay_repository_snapshot(campaign)
        authority.replay(campaign, selection_required=True)
        campaign_context = authority._campaign_context(campaign)  # noqa: SLF001
    except Exception as exc:
        raise FormalSuccessVerificationError(f"package/Gate-B/snapshot/organic replay failed: {exc}") from exc
    controller_path = Path(str(context["formal_attempt_dir"])) / CONTROLLER_RESULT_NAME
    controller_raw, controller_identity = _read_record(
        controller_path,
        expected_identity=None,
        label="formal controller result",
    )
    controller = validate_controller_result(
        controller_raw,
        context=context,
        selection_identity=selection_identity,
    )
    _replay_controller_arms(campaign_dir=campaign, controller=controller)

    expected_common = {
        "campaign_root_identity": context["campaign_root_identity"],
        "formal_selection_identity": selection_identity,
        "manager_epoch": context["manager_epoch"],
        "package_id": context["package_id"],
    }
    paths = selection["outer_spec"]["receipt_paths"]
    receipts: dict[str, dict[str, object]] = {}
    identities: dict[str, dict[str, object]] = {}

    def read_phase(phase: str) -> dict[str, Any]:
        raw, identity = _read_record(paths[phase], expected_identity=None, label=phase)
        identities[phase] = identity
        return raw

    prelaunch = validate_outer_prelaunch(
        read_phase("outer_prelaunch"),
        expected=expected_common,
        expected_unit_name=selection["outer_spec"]["unit_name"],
        expected_lock_identities=selection["lock_identities"],
        expected_observation_context={
            "authority_id": selection_identity["sha256"],
            "disk_path": str(Path(str(context["campaign_dir"])).absolute()),
            "kind": "FORMAL_OUTER_PRELAUNCH",
            "ordinal": 0,
            "scope_id": context["campaign_root_identity"]["sha256"],
            "sequence": 1,
            "slot": "",
            "target": selection["outer_spec"]["unit_name"],
        },
        expected_allowed_same_uid_processes=[
            guardian_ready["guardian_process_identity"]
        ],
    )
    receipts["outer_prelaunch"] = prelaunch
    start = validate_outer_start(
        read_phase("outer_start"),
        expected=expected_common,
        expected_unit_name=selection["outer_spec"]["unit_name"],
        expected_resource_admission=prelaunch["resource_admission"],
    )
    if start["launch_effect"]["outer_prelaunch_identity"] != identities["outer_prelaunch"]:
        raise FormalSuccessVerificationError("outer start/prelaunch identity join drifted")
    receipts["outer_start"] = start
    outer_identity = start["outer_identity"]
    resource = validate_outer_resource(
        read_phase("outer_resource"),
        expected=expected_common,
        expected_outer_identity=outer_identity,
        resource_contract=selection["outer_spec"]["resource_contract"],
    )
    if resource["systemd_properties"]["outer_start_identity"] != identities["outer_start"]:
        raise FormalSuccessVerificationError("outer resource/start identity join drifted")
    receipts["outer_resource"] = resource
    acquisition = validate_reference_acquisition(
        read_phase("reference_acquisition"),
        expected=expected_common,
        expected_outer_identity=outer_identity,
        expected_resource_identity=identities["outer_resource"],
        expected_lock_identities=selection["lock_identities"],
        transcript_validator=campaign_context["campaign_module"],
    )
    receipts["reference_acquisition"] = acquisition
    terminal = validate_outer_terminal(
        read_phase("outer_terminal"),
        expected=expected_common,
        expected_outer_identity=outer_identity,
    )
    terminal_payload = terminal["stable_terminal"]
    if (
        terminal_payload["controller_result_identity"] != controller_identity
        or terminal_payload["reference_acquisition_identity"] != identities["reference_acquisition"]
    ):
        raise FormalSuccessVerificationError("outer terminal/controller/RefUnit join drifted")
    child_audit_raw, child_audit_identity = _read_record(
        selection["child_audit_path"],
        expected_identity=terminal_payload["child_audit_identity"],
        label="finite child audit",
    )
    _validate_child_audit(child_audit_raw, controller=controller)
    receipts["outer_terminal"] = terminal
    observer = validate_observer(
        read_phase("observer"),
        expected=expected_common,
        expected_outer_identity=outer_identity,
    )
    if (
        observer["heavy_absence"]["child_audit_identity"] != child_audit_identity
        or observer["heavy_absence"]["outer_terminal_identity"] != identities["outer_terminal"]
    ):
        raise FormalSuccessVerificationError("observer heavy-absence join drifted")
    receipts["observer"] = observer
    pre_unref = validate_pre_unref_cleanup(
        read_phase("pre_unref_cleanup"),
        expected=expected_common,
        expected_outer_identity=outer_identity,
    )
    if (
        pre_unref["child_audit_identity"] != child_audit_identity
        or pre_unref["observer_identity"] != identities["observer"]
        or pre_unref["heavy_absence"] != observer["heavy_absence"]
        or pre_unref["outer_cleanup"]["outer_terminal_identity"] != identities["outer_terminal"]
    ):
        raise FormalSuccessVerificationError("pre-Unref cleanup/observer join drifted")
    receipts["pre_unref_cleanup"] = pre_unref
    if os.path.lexists(Path(str(context["formal_attempt_dir"])) / "unref-call.json"):
        raise FormalSuccessVerificationError(
            "pre-release verifier observed future receipt: unref_call"
        )
    for forbidden in (
        "guardian_lock_close",
        "guardian_absence",
        "supervisor_raw_lock_release",
        "reference_release",
        "post_unref_absence",
        "reference_terminal",
        "reference_connection_close",
        "dual_lock_release",
    ):
        if os.path.lexists(paths[forbidden]):
            raise FormalSuccessVerificationError(
                f"pre-release verifier observed future receipt: {forbidden}"
            )

    final = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "b6_changed": False,
        "bounds_changed": False,
        "campaign_root_identity": context["campaign_root_identity"],
        "child_audit_identity": child_audit_identity,
        "controller_result_identity": controller_identity,
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "formal_selection_identity": selection_identity,
        "lock_identities": _lock_identities(selection["lock_identities"]),
        "lock_lifecycle": {
            "guardian_close_is_next_required_step": True,
            "reference_connection_must_remain_open": True,
            "refunit_must_remain_held": True,
            "supervisor_lock_release_permitted": False,
            "supervisor_locks_must_remain_held": True,
        },
        "lower_bound": "absent",
        "package_id": context["package_id"],
        "phase_receipt_identities": {
            phase: identities[phase]
            for phase in PRE_RELEASE_PHASES
        },
        "production_authority_changed": False,
        "production_certified": False,
        "repository_head": context["repository_head"],
        "schema_version": SUCCESS_RECEIPT_SCHEMA,
        "stage_b_changed": False,
        "status": "PRE_RELEASE_VERIFIED",
        "terminal_classification_identity": controller["terminal_classification_identity"],
        "upper_bound": [1188, 18],
        "verdict": "AB16_FORMAL_SUBSTANTIVE_REPLAY_VERIFIED_LOCKS_STILL_REQUIRED",
    }
    final = validate_pre_release_success(
        final,
        context=context,
        selection_identity=selection_identity,
        expected_lock_identities=selection["lock_identities"],
    )
    output = Path(paths["detached_closeout"])
    identity = _publish_final_receipt(
        output,
        final,
        label="formal detached success",
    )
    return {
        "detached_success": final,
        "detached_success_identity": identity,
        "status": "PRE_RELEASE_VERIFIED",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--formal-selection", type=Path)
    mode.add_argument("--incomplete-release", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.formal_selection is not None:
            result = verify_success(
                campaign_dir=arguments.campaign_dir,
                formal_selection=arguments.formal_selection,
            )
        else:
            result = verify_incomplete(
                campaign_dir=arguments.campaign_dir,
                incomplete_release=arguments.incomplete_release,
            )
    except BaseException as exc:
        print(f"FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(authority.canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
