#!/usr/bin/env python3
"""Monotone receipt and RefUnit state for the one AB16 formal campaign.

This campaign-local module owns proof/effect state and no-overwrite closeout
receipts.  It does not launch or discover units.  A caller supplies the
already frozen finite child/outer ledger and the live three-lock owner.

The module is deliberately non-authorizing.  Its strongest terminal result is
``VERIFIED_INCOMPLETE`` and every record keeps all mathematical, production,
and bound-update authorizations false.

SIGINT and SIGTERM are expected to be latched by the owning supervisor.  Once
containment starts, observer, announcement, wait, and ledger-validation errors
are recorded without unwinding the three-lock hold.  SIGKILL, kernel/process
failure, and reboot can still close the process-owned lock descriptors; without
a durable quarantine or independent lock holder this foundation MUST NOT be
wired to formal authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
from typing import Any

CONSUMPTION_SCHEMA = "noncert-cuts-ab16-formal-attempt-consumption-v1"
MARKERLESS_SCHEMA = "noncert-cuts-ab16-formal-markerless-incomplete-v1"
INCOMPLETE_SCHEMA = "noncert-cuts-ab16-formal-consumed-incomplete-v1"
REFERENCE_SCHEMA = "noncert-cuts-ab16-formal-reference-lifecycle-v1"
HOLD_SCHEMA = "noncert-cuts-ab16-formal-containment-hold-v1"
HOLD_CLEAR_SCHEMA = "noncert-cuts-ab16-formal-containment-cleared-after-hold-v1"
LOCK_RELEASE_SCHEMA = "noncert-cuts-ab16-formal-lock-release-v1"
DETACHED_INCOMPLETE_SCHEMA = "noncert-cuts-ab16-formal-detached-incomplete-v1"
HOLD_POLL_SECONDS = 5.0
IDENTITY_SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
UNIT_RE = re.compile(r"[a-z0-9][a-z0-9_.@:-]{3,180}\.service\Z")
INVOCATION_RE = re.compile(r"[0-9a-f]{32}\Z")
GATE1_SLOTS = ("q-success", "q-postseal-fail", "forced-control", "forced-treatment")
CONFIGURATIONS = ("region-capacity", "shape-packing-hall", "power-hitting-set", "bundle")
ARM_SEQUENCE = tuple(
    f"{config}-{order}-{arm}"
    for config in CONFIGURATIONS
    for order, arms in (("ab", ("control", "treatment")), ("ba", ("treatment", "control")))
    for arm in arms
)
EXPECTED_CHILD_ORDER = (
    *(("gate1", slot) for slot in GATE1_SLOTS),
    *(("arm", slot) for slot in ARM_SEQUENCE),
)
GUARDIAN_LEDGER_PHASES = (
    "outer:prelaunch",
    "outer:formal",
    "gate1:prelaunch",
    *(f"gate1:{slot}:live" for slot in GATE1_SLOTS),
    *(
        phase
        for slot in ARM_SEQUENCE
        for phase in (f"arm:{slot}:prelaunch", f"arm:{slot}:live")
    ),
)
LOCK_PATHS = (
    "/tmp/zmd-pj-codex-heavy-validation.lock",
    "/run/user/1000/zmd_pj_prod_scale_solver.lock",
    "/run/user/1000/zmd-pj-prod-scale-solve.lock",
)
FROZEN_IDENTITY_FIELDS = {
    "control_group",
    "identity_complete",
    "invocation_id",
    "ownership_classification",
    "processes",
    "slot",
    "source",
    "unit_name",
}
ABSENT_SYSTEMD_STATE = {
    "ActiveState": "inactive",
    "ControlGroup": "",
    "InvocationID": "",
    "LoadState": "not-found",
    "MainPID": "0",
    "SubState": "dead",
}
ABSENCE_RECORD_FIELDS = {
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
FALSE_AUTHORIZATIONS = {
    key: False
    for key in (
        "b6_update_authorized",
        "bounds_update_authorized",
        "family_global_soundness_authorized",
        "global_claim_authorized",
        "lower_bound_update_authorized",
        "mathematical_claim_authorized",
        "production_certified_authorized",
        "sat_unsat_claim_authorized",
        "stage_b_promotion_authorized",
        "upper_bound_update_authorized",
        "witness_claim_authorized",
    )
}
BASE_FIELDS = frozenset(
    {
        "authorizations",
        "campaign_root_identity",
        "lower_bound",
        "package_id",
        "production_certified",
        "upper_bound",
    }
)
REFERENCE_PROOF_FIELDS = (
    "selection_identity",
    "outer_prelaunch_identity",
    "outer_start_identity",
    "resource_identity",
    "acquire_identity",
    "barrier_identity",
    "unref_call_identity",
    "reference_release_identity",
)
LATE_PROOF_FIELDS = (
    "observer_identity",
    "pre_unref_cleanup_identity",
    "post_unref_absence_identity",
    "guardian_close_identity",
    "guardian_absence_identity",
    "dual_lock_release_identity",
)
PROOF_FIELDS = (*REFERENCE_PROOF_FIELDS, *LATE_PROOF_FIELDS)


class CloseoutStateError(RuntimeError):
    """A monotone AB16 closeout invariant failed closed."""


def failure(code: str, error: BaseException | str) -> dict[str, str]:
    detail = str(error) if isinstance(error, str) else f"{type(error).__name__}: {error}"
    return {"code": code, "detail": detail}


def validate_failure_record(value: object, label: str) -> dict[str, str]:
    if (
        type(value) is not dict
        or set(value) != {"code", "detail"}
        or any(type(value[key]) is not str or not value[key] for key in value)
    ):
        raise CloseoutStateError(f"{label} failure schema drifted")
    return {"code": value["code"], "detail": value["detail"]}


def validate_failure_list(value: object, label: str) -> list[dict[str, str]]:
    if type(value) is not list:
        raise CloseoutStateError(f"{label} error list schema drifted")
    return [
        validate_failure_record(item, f"{label} error {index}")
        for index, item in enumerate(value)
    ]


def reject_none(value: object, label: str) -> None:
    """Reject nulls in proof joins, while leaving semantic nulls to their schema."""

    if value is None:
        raise CloseoutStateError(f"{label} contains an unproved null join")
    children = value.items() if type(value) is dict else enumerate(value) if type(value) is list else ()
    for key, item in children:
        reject_none(item, f"{label}.{key}")


def validate_identity_join(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict or not value:
        raise CloseoutStateError(f"{label} is not one nonempty identity object")
    reject_none(value, label)
    digest = value.get("sha256")
    if type(digest) is not str or IDENTITY_SHA_RE.fullmatch(digest) is None:
        raise CloseoutStateError(f"{label} lacks one exact SHA-256")
    return dict(value)


def validate_control_group(value: object) -> str:
    if type(value) is not str:
        raise CloseoutStateError("cgroup identity is not a string")
    pure = PurePosixPath(value)
    if not pure.is_absolute() or value == "/" or ".." in pure.parts:
        raise CloseoutStateError("cgroup is not one exact non-root absolute path")
    return value


def validate_process_identity(value: object, label: str) -> dict[str, int]:
    if (
        type(value) is not dict
        or set(value) != {"pid", "starttime"}
        or type(value["pid"]) is not int
        or type(value["starttime"]) is not int
        or value["pid"] <= 0
        or value["starttime"] <= 0
    ):
        raise CloseoutStateError(f"{label} is not one positive PID/starttime identity")
    return {"pid": value["pid"], "starttime": value["starttime"]}


def validate_frozen_identity(
    value: object,
    *,
    expected_source: str,
    expected_slot: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise CloseoutStateError("frozen runtime identity is not one object")
    complete = value.get("identity_complete")
    expected_fields = FROZEN_IDENTITY_FIELDS | (set() if complete is True else {"identity_error"})
    if type(complete) is not bool or set(value) != expected_fields:
        raise CloseoutStateError("frozen runtime identity field set drifted")
    if value["source"] != expected_source or value["slot"] != expected_slot:
        raise CloseoutStateError("frozen runtime source/slot order drifted")
    unit_name = value["unit_name"]
    control_group = value["control_group"]
    invocation = value["invocation_id"]
    processes = value["processes"]
    if (
        type(unit_name) is not str
        or (unit_name and UNIT_RE.fullmatch(unit_name) is None)
        or type(control_group) is not str
        or type(invocation) is not str
        or type(value["ownership_classification"]) is not str
        or type(processes) is not list
    ):
        raise CloseoutStateError("frozen runtime identity value types drifted")
    checked_processes = [
        validate_process_identity(item, f"{expected_source}/{expected_slot} process")
        for item in processes
    ]
    if len({item["pid"] for item in checked_processes}) != len(checked_processes):
        raise CloseoutStateError("frozen runtime process identities are duplicated")
    if complete is False:
        checked = dict(value)
        checked["identity_error"] = validate_failure_record(
            value["identity_error"],
            "incomplete frozen identity",
        )
        return checked
    if control_group:
        validate_control_group(control_group)
        if INVOCATION_RE.fullmatch(invocation) is None or not checked_processes:
            raise CloseoutStateError("active frozen identity lacks invocation/process ownership")
    elif invocation or checked_processes:
        raise CloseoutStateError("absent frozen identity contains active runtime identity")
    return dict(value)


def validate_frozen_ledger(ledger: Mapping[str, object]) -> dict[str, object]:
    """Own the fixed 4+16 child order and one outer frozen identity."""

    if type(ledger) is not dict or set(ledger) != {"child_audit_identity", "children", "outer"}:
        raise CloseoutStateError("frozen ledger field set drifted")
    children = ledger["children"]
    if type(children) is not list or len(children) != len(EXPECTED_CHILD_ORDER):
        raise CloseoutStateError("frozen child ledger cardinality drifted")
    checked_children = [
        validate_frozen_identity(item, expected_source=source, expected_slot=slot)
        for item, (source, slot) in zip(children, EXPECTED_CHILD_ORDER, strict=True)
    ]
    checked_outer = validate_frozen_identity(
        ledger["outer"],
        expected_source="outer",
        expected_slot="formal",
    )
    nonempty_units = [
        str(item["unit_name"])
        for item in [*checked_children, checked_outer]
        if item["unit_name"]
    ]
    if len(nonempty_units) != len(set(nonempty_units)):
        raise CloseoutStateError("frozen ledger contains a duplicate nonempty unit")
    return {
        # The helper also uses this structural validator before the child-audit
        # receipt exists.  Receipt-producing callers must validate this join.
        "child_audit_identity": ledger["child_audit_identity"],
        "children": checked_children,
        "outer": checked_outer,
    }


def validate_absence_observation(
    value: object,
    *,
    ledger: Mapping[str, object],
) -> dict[str, object]:
    """Bind all 20 child observations and the outer observation to one ledger."""

    checked_ledger = validate_frozen_ledger(ledger)
    if type(value) is not dict or set(value) != {"all_absent", "records"}:
        raise CloseoutStateError("frozen absence observation field set drifted")
    records = value["records"]
    expected_identities = [*checked_ledger["children"], checked_ledger["outer"]]
    if (
        value["all_absent"] is not True
        or type(records) is not list
        or len(records) != len(expected_identities)
    ):
        raise CloseoutStateError("frozen absence observation is not one exact all-absence")
    checked_records: list[dict[str, object]] = []
    for index, (record, identity) in enumerate(
        zip(records, expected_identities, strict=True)
    ):
        if type(record) is not dict or set(record) != ABSENCE_RECORD_FIELDS:
            raise CloseoutStateError(f"absence record {index} field set drifted")
        if (
            record["source"] != identity["source"]
            or record["slot"] != identity["slot"]
            or record["unit_name"] != identity["unit_name"]
            or record["control_group"] != identity["control_group"]
            or record["processes"] != identity["processes"]
            or record["identity_complete"] is not True
            or identity["identity_complete"] is not True
            or record["unit_absent"] is not True
            or record["cgroup_absent"] is not True
            or record["processes_absent"] is not True
            or record["systemctl"] != ABSENT_SYSTEMD_STATE
        ):
            raise CloseoutStateError(
                f"absence record {index} does not prove its frozen runtime identity"
            )
        checked_records.append(dict(record))
    return {"all_absent": True, "records": checked_records}


def same_epoch(boundary: Any, observed: object) -> bool:
    try:
        return bool(
            boundary.context["campaign_module"].same_manager_epoch(
                observed,
                boundary.root["manager_epoch"],
            )
        )
    except Exception:
        return False


@dataclass
class PublicationEffect:
    """Monotone proof/effect split for one canonical O_EXCL publication."""

    attempted: bool = False
    returned_identity: dict[str, object] | None = None
    recorded_identity: dict[str, object] | None = None
    error: dict[str, str] | None = None

    def begin(self) -> None:
        if self.attempted:
            raise CloseoutStateError("canonical publication cannot be attempted twice")
        self.attempted = True

    def note_returned(self, identity: Mapping[str, object]) -> None:
        if not self.attempted or self.returned_identity is not None:
            raise CloseoutStateError("canonical publication return is not monotone")
        self.returned_identity = validate_identity_join(identity, "publication return")

    def note_recorded(self, identity: Mapping[str, object]) -> None:
        checked = validate_identity_join(identity, "publication readback")
        if self.returned_identity != checked or self.recorded_identity is not None:
            raise CloseoutStateError("canonical publication readback does not join its return")
        self.recorded_identity = checked

    def note_error(self, error: BaseException) -> None:
        if self.error is None:
            self.error = failure("CANONICAL_PUBLICATION_FAILED_OR_UNCERTAIN", error)

    def record(self) -> dict[str, object]:
        result: dict[str, object] = {
            "attempted": self.attempted,
            "recorded": self.recorded_identity is not None,
            "returned": self.returned_identity is not None,
        }
        if self.returned_identity is not None:
            result["returned_identity"] = dict(self.returned_identity)
        if self.recorded_identity is not None:
            result["recorded_identity"] = dict(self.recorded_identity)
        if self.error is not None:
            result["error"] = dict(self.error)
        return result


@dataclass
class AttemptState:
    """Separate monotone proof facts from irreversible runtime effects."""

    directory_created: bool = False
    marker_identity: dict[str, object] | None = None
    selection_identity: dict[str, object] | None = None
    outer_prelaunch_identity: dict[str, object] | None = None
    outer_launch_attempted: bool = False
    outer_launch_return: dict[str, object] | None = None
    outer_start_identity: dict[str, object] | None = None
    resource_identity: dict[str, object] | None = None
    barrier_identity: dict[str, object] | None = None
    reference: Any | None = None
    acquire_attempted: bool = False
    acquire_returned: bool = False
    acquire_return: dict[str, str] | None = None
    acquire_identity: dict[str, object] | None = None
    release_attempted: bool = False
    release_returned: bool = False
    release_return: dict[str, str] | None = None
    unref_call_identity: dict[str, object] | None = None
    abort_close_attempted: bool = False
    abort_close_return: bool | None = None
    close_attempted: bool = False
    close_returned: bool = False
    connection_action: str = ""
    reference_release_identity: dict[str, object] | None = None
    observer_identity: dict[str, object] | None = None
    pre_unref_cleanup_identity: dict[str, object] | None = None
    post_unref_absence_identity: dict[str, object] | None = None
    guardian_close_attempted: bool = False
    guardian_close_return: dict[str, object] | None = None
    guardian_close_identity: dict[str, object] | None = None
    guardian_absence_identity: dict[str, object] | None = None
    detached_success_verifier_attempted: bool = False
    detached_success_verifier_return: dict[str, object] | None = None
    dual_lock_release_identity: dict[str, object] | None = None
    irreversible_incomplete: bool = False
    incomplete_identity: dict[str, object] | None = None
    hold_identity: dict[str, object] | None = None
    hold_clearance_identity: dict[str, object] | None = None
    hold_poll_count: int = 0
    containment_guardian_absence_attempted: bool = False
    containment_guardian_absence_identity: dict[str, object] | None = None
    lock_release_attempted: bool = False
    lock_release_return: dict[str, object] | None = None
    lock_release_identity: dict[str, object] | None = None
    publications: dict[str, PublicationEffect] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)

    def publication(self, key: str) -> PublicationEffect:
        if type(key) is not str or not key:
            raise CloseoutStateError("publication key is malformed")
        return self.publications.setdefault(key, PublicationEffect())


@dataclass(frozen=True)
class IncompletePhaseRule:
    required_proofs: tuple[str, ...]
    permitted_proofs: tuple[str, ...]
    external_joins: tuple[str, ...] = ()
    required_true_effects: tuple[str, ...] = ()
    required_nonnull_effects: tuple[str, ...] = ()
    effect_equals: tuple[tuple[str, object], ...] = ()
    required_publications: tuple[str, ...] = ()


NO_LATE_EFFECTS = (
    ("guardian_close_attempted", False),
    ("guardian_close_return", None),
    ("lock_release_attempted", False),
    ("lock_release_return", None),
    ("detached_success_verifier_attempted", False),
    ("detached_success_verifier_return", None),
)
NO_TERMINAL_EFFECTS = (
    ("release_attempted", False),
    ("release_returned", False),
    ("release_return", None),
    ("abort_close_attempted", False),
    ("abort_close_return", None),
    ("close_attempted", False),
    ("close_returned", False),
    ("connection_action", ""),
    *NO_LATE_EFFECTS,
)
NO_REFERENCE_EFFECTS = (
    ("acquire_attempted", False),
    ("acquire_returned", False),
    ("acquire_return", None),
    *NO_TERMINAL_EFFECTS,
)
NO_RUNTIME_EFFECTS = (
    ("outer_launch_attempted", False),
    ("outer_launch_return", None),
    *NO_REFERENCE_EFFECTS,
)


INCOMPLETE_PHASES = {
    "ATTEMPT_RECORDED_SELECTION_UNRECORDED": IncompletePhaseRule(
        (),
        (),
        effect_equals=NO_RUNTIME_EFFECTS,
    ),
    "SELECTION_RECORDED_OUTER_NOT_LAUNCHED": IncompletePhaseRule(
        ("selection_identity",),
        ("selection_identity",),
        effect_equals=NO_RUNTIME_EFFECTS,
    ),
    "OUTER_LAUNCH_FAILED_OR_UNCERTAIN": IncompletePhaseRule(
        ("selection_identity", "outer_prelaunch_identity"),
        ("selection_identity", "outer_prelaunch_identity"),
        required_true_effects=("outer_launch_attempted",),
        effect_equals=NO_REFERENCE_EFFECTS,
    ),
    "OUTER_STARTED_REF_UNACQUIRED": IncompletePhaseRule(
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity", "resource_identity"),
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity", "resource_identity"),
        required_true_effects=("outer_launch_attempted",),
        required_nonnull_effects=("outer_launch_return",),
        effect_equals=NO_REFERENCE_EFFECTS,
    ),
    "OUTER_STARTED_RESOURCE_UNRECORDED": IncompletePhaseRule(
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity"),
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity"),
        required_true_effects=("outer_launch_attempted",),
        required_nonnull_effects=("outer_launch_return",),
        effect_equals=NO_REFERENCE_EFFECTS,
    ),
    "REF_ACQUIRE_FAILED_OR_UNCERTAIN": IncompletePhaseRule(
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity", "resource_identity"),
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity", "resource_identity"),
        required_true_effects=("outer_launch_attempted", "acquire_attempted"),
        required_nonnull_effects=("outer_launch_return",),
        effect_equals=(
            ("acquire_returned", False),
            ("acquire_return", None),
            *NO_TERMINAL_EFFECTS,
        ),
    ),
    "REF_ACQUIRE_RETURNED_BUT_UNRECORDED": IncompletePhaseRule(
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity", "resource_identity"),
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity", "resource_identity"),
        required_true_effects=("outer_launch_attempted", "acquire_attempted", "acquire_returned"),
        required_nonnull_effects=("outer_launch_return", "acquire_return"),
        effect_equals=NO_TERMINAL_EFFECTS,
    ),
    "REFERENCE_HELD_PRE_UNREF_FAILURE": IncompletePhaseRule(
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
        ),
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
        ),
        required_true_effects=("acquire_attempted", "acquire_returned"),
        required_nonnull_effects=("outer_launch_return", "acquire_return"),
        effect_equals=NO_TERMINAL_EFFECTS,
    ),
    "UNREF_FAILED_OR_UNCERTAIN": IncompletePhaseRule(
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
            "barrier_identity",
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
            "barrier_identity",
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        external_joins=("frozen_outer_identity",),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
        ),
        required_nonnull_effects=("outer_launch_return", "acquire_return"),
        effect_equals=(
            ("release_returned", False),
            ("release_return", None),
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("close_attempted", False),
            ("close_returned", False),
            ("connection_action", ""),
            *NO_LATE_EFFECTS,
        ),
    ),
    "UNREF_RETURNED_BUT_UNRECORDED": IncompletePhaseRule(
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
            "barrier_identity",
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
            "barrier_identity",
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        external_joins=("frozen_outer_identity",),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("close_attempted", False),
            ("close_returned", False),
            ("connection_action", ""),
            *NO_LATE_EFFECTS,
        ),
    ),
    "ACQUIRE_UNPROVEN_CONNECTION_DROPPED": IncompletePhaseRule(
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity", "resource_identity"),
        ("selection_identity", "outer_prelaunch_identity", "outer_start_identity", "resource_identity"),
        external_joins=("frozen_outer_identity",),
        required_true_effects=("acquire_attempted", "abort_close_attempted"),
        required_nonnull_effects=("outer_launch_return",),
        effect_equals=(
            ("release_attempted", False),
            ("release_returned", False),
            ("release_return", None),
            ("close_attempted", False),
            ("close_returned", False),
            ("connection_action", "abort_close"),
        ),
    ),
    "UNREF_UNPROVEN_CONNECTION_DROPPED": IncompletePhaseRule(
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        external_joins=("frozen_outer_identity",),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "abort_close_attempted",
        ),
        required_nonnull_effects=("outer_launch_return", "acquire_return"),
        effect_equals=(
            ("close_attempted", False),
            ("close_returned", False),
            ("connection_action", "abort_close"),
            *NO_LATE_EFFECTS,
        ),
    ),
    "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN": IncompletePhaseRule(
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
            "unref_call_identity",
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        external_joins=("frozen_outer_identity",),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("close_returned", False),
            ("connection_action", "close"),
            *NO_LATE_EFFECTS,
        ),
    ),
    "CONNECTION_CLOSED_RELEASE_UNRECORDED": IncompletePhaseRule(
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
            "unref_call_identity",
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        external_joins=("frozen_outer_identity",),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            *NO_LATE_EFFECTS,
        ),
        required_publications=("reference-release",),
    ),
    "POST_UNREF_ABSENCE_UNPROVED": IncompletePhaseRule(
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
            "unref_call_identity",
            "reference_release_identity",
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        external_joins=("frozen_outer_identity",),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            *NO_LATE_EFFECTS,
        ),
    ),
    "CONTAINMENT_HOLD": IncompletePhaseRule(
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
            "barrier_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
        ),
        external_joins=("child_audit_identity", "frozen_outer_identity"),
        required_true_effects=("acquire_attempted", "acquire_returned"),
        required_nonnull_effects=("outer_launch_return", "acquire_return"),
        effect_equals=NO_LATE_EFFECTS,
    ),
    "BARRIER_FAILED_OR_UNCERTAIN_CONTAINMENT_HOLD": IncompletePhaseRule(
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
        ),
        (
            "selection_identity",
            "outer_prelaunch_identity",
            "outer_start_identity",
            "resource_identity",
            "acquire_identity",
            "unref_call_identity",
            "reference_release_identity",
        ),
        external_joins=("child_audit_identity", "frozen_outer_identity"),
        required_true_effects=("acquire_attempted", "acquire_returned"),
        required_nonnull_effects=("outer_launch_return", "acquire_return"),
        effect_equals=NO_LATE_EFFECTS,
        required_publications=("outer-barrier",),
    ),
    "GUARDIAN_CLOSE_NOT_ATTEMPTED": IncompletePhaseRule(
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
        ),
        external_joins=("child_audit_identity", "outer_terminal_identity"),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            *NO_LATE_EFFECTS,
        ),
    ),
    "GUARDIAN_CLOSE_FAILED_OR_UNCERTAIN": IncompletePhaseRule(
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
        ),
        external_joins=("child_audit_identity", "outer_terminal_identity"),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
            "guardian_close_attempted",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            ("lock_release_attempted", False),
            ("lock_release_return", None),
            ("detached_success_verifier_attempted", False),
            ("detached_success_verifier_return", None),
        ),
    ),
    "GUARDIAN_ABSENCE_UNPROVED": IncompletePhaseRule(
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
        ),
        external_joins=("child_audit_identity", "outer_terminal_identity"),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
            "guardian_close_attempted",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
            "guardian_close_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            ("lock_release_attempted", False),
            ("lock_release_return", None),
            ("detached_success_verifier_attempted", False),
            ("detached_success_verifier_return", None),
        ),
    ),
    "SUPERVISOR_LOCK_RELEASE_NOT_ATTEMPTED": IncompletePhaseRule(
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
            "guardian_absence_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
            "guardian_absence_identity",
        ),
        external_joins=("child_audit_identity", "outer_terminal_identity"),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
            "guardian_close_attempted",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
            "guardian_close_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            ("lock_release_attempted", False),
            ("lock_release_return", None),
            ("detached_success_verifier_attempted", False),
            ("detached_success_verifier_return", None),
        ),
    ),
    "SUPERVISOR_LOCK_RELEASE_FAILED_OR_UNCERTAIN": IncompletePhaseRule(
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
            "guardian_absence_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
            "guardian_absence_identity",
        ),
        external_joins=("child_audit_identity", "outer_terminal_identity"),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
            "guardian_close_attempted",
            "lock_release_attempted",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
            "guardian_close_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            ("detached_success_verifier_attempted", False),
            ("detached_success_verifier_return", None),
        ),
    ),
    "DUAL_LOCK_RELEASE_RECEIPT_NOT_ATTEMPTED": IncompletePhaseRule(
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
            "guardian_absence_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
            "guardian_absence_identity",
        ),
        external_joins=("child_audit_identity", "outer_terminal_identity"),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
            "guardian_close_attempted",
            "lock_release_attempted",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
            "guardian_close_return",
            "lock_release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            ("detached_success_verifier_attempted", False),
            ("detached_success_verifier_return", None),
        ),
    ),
    "DUAL_LOCK_RELEASE_RECEIPT_FAILED_OR_UNCERTAIN": IncompletePhaseRule(
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
            "guardian_absence_identity",
        ),
        (
            *REFERENCE_PROOF_FIELDS,
            "observer_identity",
            "pre_unref_cleanup_identity",
            "post_unref_absence_identity",
            "guardian_close_identity",
            "guardian_absence_identity",
        ),
        external_joins=("child_audit_identity", "outer_terminal_identity"),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
            "guardian_close_attempted",
            "lock_release_attempted",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
            "guardian_close_return",
            "lock_release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            ("detached_success_verifier_attempted", False),
            ("detached_success_verifier_return", None),
        ),
        required_publications=("dual-lock-release",),
    ),
    "DETACHED_SUCCESS_VERIFIER_NOT_ATTEMPTED": IncompletePhaseRule(
        (*PROOF_FIELDS,),
        (*PROOF_FIELDS,),
        external_joins=("child_audit_identity", "outer_terminal_identity"),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
            "guardian_close_attempted",
            "lock_release_attempted",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
            "guardian_close_return",
            "lock_release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
            ("detached_success_verifier_attempted", False),
            ("detached_success_verifier_return", None),
        ),
        required_publications=("dual-lock-release",),
    ),
    "DETACHED_SUCCESS_VERIFIER_FAILED_OR_UNCERTAIN": IncompletePhaseRule(
        (*PROOF_FIELDS,),
        (*PROOF_FIELDS,),
        external_joins=("child_audit_identity", "outer_terminal_identity"),
        required_true_effects=(
            "acquire_attempted",
            "acquire_returned",
            "release_attempted",
            "release_returned",
            "close_attempted",
            "close_returned",
            "guardian_close_attempted",
            "lock_release_attempted",
            "detached_success_verifier_attempted",
        ),
        required_nonnull_effects=(
            "outer_launch_return",
            "acquire_return",
            "release_return",
            "guardian_close_return",
            "lock_release_return",
        ),
        effect_equals=(
            ("abort_close_attempted", False),
            ("abort_close_return", None),
            ("connection_action", "close"),
        ),
        required_publications=("dual-lock-release",),
    ),
}


def _directory_identity(path: Path) -> dict[str, object]:
    opened = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        value = os.fstat(opened)
    finally:
        os.close(opened)
    if not stat.S_ISDIR(value.st_mode):
        raise CloseoutStateError("formal attempt path is not one directory")
    return {
        "device": value.st_dev,
        "gid": value.st_gid,
        "inode": value.st_ino,
        "mode": stat.S_IMODE(value.st_mode),
        "path": str(path),
        "uid": value.st_uid,
    }


def _basis(boundary: Any, state: AttemptState) -> dict[str, object]:
    if state.marker_identity is not None:
        return {
            "identity": validate_identity_join(state.marker_identity, "attempt marker"),
            "kind": "RECORDED",
        }
    if state.directory_created:
        return {
            "directory_identity": _directory_identity(boundary.formal_dir),
            "kind": "DIRECTORY_CREATED_UNRECORDED",
        }
    raise CloseoutStateError("attempt has no consumed fact basis")


def _base(boundary: Any) -> dict[str, object]:
    root_identity = validate_identity_join(
        boundary.context["root_identity"],
        "campaign root",
    )
    package_id = boundary.root["package"]["package_id"]
    if type(package_id) is not str or IDENTITY_SHA_RE.fullmatch(package_id) is None:
        raise CloseoutStateError("authority package ID is malformed")
    return {
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "campaign_root_identity": root_identity,
        "lower_bound": None,
        "package_id": package_id,
        "production_certified": False,
        "upper_bound": [1188, 18],
    }


def _validate_base_record(
    value: Mapping[str, object],
    *,
    expected_campaign_root_identity: Mapping[str, object],
    expected_package_id: str,
) -> None:
    checked_root = validate_identity_join(
        expected_campaign_root_identity,
        "expected campaign root",
    )
    if (
        type(expected_package_id) is not str
        or IDENTITY_SHA_RE.fullmatch(expected_package_id) is None
    ):
        raise CloseoutStateError("expected authority package ID is malformed")
    if (
        value.get("authorizations") != FALSE_AUTHORIZATIONS
        or value.get("campaign_root_identity") != checked_root
        or value.get("lower_bound") is not None
        or value.get("package_id") != expected_package_id
        or value.get("production_certified") is not False
        or value.get("upper_bound") != [1188, 18]
    ):
        raise CloseoutStateError("non-authorizing AB16 base fields drifted")


def _effect_snapshot(state: AttemptState) -> dict[str, object]:
    return {
        "abort_close_attempted": state.abort_close_attempted,
        "abort_close_return": state.abort_close_return,
        "acquire_attempted": state.acquire_attempted,
        "acquire_returned": state.acquire_returned,
        "acquire_return": dict(state.acquire_return) if state.acquire_return is not None else None,
        "close_attempted": state.close_attempted,
        "close_returned": state.close_returned,
        "connection_action": state.connection_action,
        "detached_success_verifier_attempted": state.detached_success_verifier_attempted,
        "detached_success_verifier_return": (
            dict(state.detached_success_verifier_return)
            if state.detached_success_verifier_return is not None
            else None
        ),
        "guardian_close_attempted": state.guardian_close_attempted,
        "guardian_close_return": (
            dict(state.guardian_close_return)
            if state.guardian_close_return is not None
            else None
        ),
        "lock_release_attempted": state.lock_release_attempted,
        "lock_release_return": (
            dict(state.lock_release_return)
            if state.lock_release_return is not None
            else None
        ),
        "outer_launch_attempted": state.outer_launch_attempted,
        "outer_launch_return": (
            dict(state.outer_launch_return) if state.outer_launch_return is not None else None
        ),
        "publications": {
            key: state.publications[key].record()
            for key in sorted(state.publications)
        },
        "release_attempted": state.release_attempted,
        "release_returned": state.release_returned,
        "release_return": dict(state.release_return) if state.release_return is not None else None,
    }


def _publish_once(
    state: AttemptState,
    store: Any,
    key: str,
    path: Path,
    value: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    effect = state.publication(key)
    effect.begin()
    try:
        identity = store.publish(path, value, label, publication=effect)
        checked = validate_identity_join(identity, f"{label} identity")
        if effect.returned_identity is None:
            effect.note_returned(checked)
        if effect.recorded_identity is None:
            effect.note_recorded(checked)
        if effect.recorded_identity != checked:
            raise CloseoutStateError(f"{label} proof/effect identity drifted")
        return checked
    except Exception as exc:
        effect.note_error(exc)
        raise


def begin_outer_launch(state: AttemptState) -> None:
    """Mark the irreversible launch call before invoking the runner."""

    if state.outer_launch_attempted:
        raise CloseoutStateError("outer launch cannot be attempted twice")
    if state.selection_identity is None or state.outer_prelaunch_identity is None:
        raise CloseoutStateError("outer launch lacks selection/prelaunch proof")
    state.outer_launch_attempted = True


def record_outer_launch_return(state: AttemptState, effect: Mapping[str, object]) -> None:
    """Record a returned launch effect without upgrading it to start proof."""

    if not state.outer_launch_attempted or state.outer_launch_return is not None:
        raise CloseoutStateError("outer launch return is not monotone")
    reject_none(dict(effect), "outer launch return")
    if not effect:
        raise CloseoutStateError("outer launch returned an empty effect")
    state.outer_launch_return = dict(effect)


def record_late_proof_once(
    state: AttemptState,
    name: str,
    identity: Mapping[str, object],
) -> dict[str, object]:
    """Record one late proof identity without fabricating a future join."""

    predecessors = {
        "observer_identity": ("acquire_identity", "barrier_identity"),
        "pre_unref_cleanup_identity": ("observer_identity",),
        "post_unref_absence_identity": (
            "pre_unref_cleanup_identity",
            "reference_release_identity",
        ),
        "guardian_close_identity": ("post_unref_absence_identity",),
        "guardian_absence_identity": ("guardian_close_identity",),
        "dual_lock_release_identity": ("guardian_absence_identity",),
    }
    if name not in predecessors:
        raise CloseoutStateError("late proof name is outside the fixed closeout order")
    if getattr(state, name) is not None:
        raise CloseoutStateError(f"{name} proof cannot be recorded twice")
    for predecessor in predecessors[name]:
        validate_identity_join(
            getattr(state, predecessor),
            f"{name} predecessor {predecessor}",
        )
    checked = validate_identity_join(identity, name)
    if name == "guardian_close_identity" and (
        not state.guardian_close_attempted
        or state.guardian_close_return is None
    ):
        raise CloseoutStateError("guardian close proof precedes its returned effect")
    if name == "dual_lock_release_identity":
        publication = state.publications.get("dual-lock-release")
        if (
            not state.lock_release_attempted
            or state.lock_release_return is None
            or publication is None
            or publication.recorded_identity != checked
        ):
            raise CloseoutStateError(
                "dual-lock release proof precedes its effect or canonical readback"
            )
    setattr(state, name, checked)
    return checked


def begin_guardian_close(state: AttemptState) -> None:
    if state.guardian_close_attempted:
        raise CloseoutStateError("guardian close cannot be attempted twice")
    validate_identity_join(
        state.post_unref_absence_identity,
        "guardian close post-Unref absence",
    )
    state.guardian_close_attempted = True


def record_guardian_close_return(
    state: AttemptState,
    effect: Mapping[str, object],
) -> None:
    if not state.guardian_close_attempted or state.guardian_close_return is not None:
        raise CloseoutStateError("guardian close return is not monotone")
    reject_none(dict(effect), "guardian close return")
    if not effect:
        raise CloseoutStateError("guardian close returned an empty effect")
    state.guardian_close_return = dict(effect)


def begin_supervisor_lock_release(state: AttemptState) -> None:
    if state.lock_release_attempted:
        raise CloseoutStateError("supervisor lock release cannot be attempted twice")
    validate_identity_join(
        state.guardian_absence_identity,
        "supervisor lock release guardian absence",
    )
    state.lock_release_attempted = True


def record_supervisor_lock_release_return(
    state: AttemptState,
    effect: Mapping[str, object],
) -> None:
    if not state.lock_release_attempted or state.lock_release_return is not None:
        raise CloseoutStateError("supervisor lock release return is not monotone")
    reject_none(dict(effect), "supervisor lock release return")
    if not effect:
        raise CloseoutStateError("supervisor lock release returned an empty effect")
    state.lock_release_return = dict(effect)


def begin_detached_success_verifier(state: AttemptState) -> None:
    if state.detached_success_verifier_attempted:
        raise CloseoutStateError("detached success verifier cannot be attempted twice")
    validate_identity_join(
        state.dual_lock_release_identity,
        "detached verifier dual-lock release",
    )
    state.detached_success_verifier_attempted = True


def record_detached_success_verifier_return(
    state: AttemptState,
    effect: Mapping[str, object],
) -> None:
    if (
        not state.detached_success_verifier_attempted
        or state.detached_success_verifier_return is not None
    ):
        raise CloseoutStateError("detached success verifier return is not monotone")
    reject_none(dict(effect), "detached success verifier return")
    if not effect:
        raise CloseoutStateError("detached success verifier returned an empty effect")
    state.detached_success_verifier_return = dict(effect)


def publish_attempt_consumption(
    boundary: Any,
    state: AttemptState,
    store: Any,
    *,
    created_at_utc: str,
) -> dict[str, object]:
    """Publish the sole marker, or permanently consume this markerless directory."""

    if not state.directory_created or state.marker_identity is not None:
        raise CloseoutStateError("attempt marker has the wrong predecessor")
    marker = {
        **_base(boundary),
        "consumed": True,
        "created_at_utc": created_at_utc,
        "formal_dir": str(boundary.formal_dir),
        "retry_eligible": False,
        "schema_version": CONSUMPTION_SCHEMA,
    }
    try:
        state.marker_identity = _publish_once(
            state,
            store,
            "attempt-consumption",
            boundary.formal_dir / "attempt-consumption.json",
            marker,
            "formal attempt consumption",
        )
    except Exception as exc:
        state.irreversible_incomplete = True
        markerless = {
            **_base(boundary),
            "attempt_consumption_effect": state.publication("attempt-consumption").record(),
            "consumed": True,
            "failure": failure("ATTEMPT_MARKER_FAILED_OR_UNCERTAIN", exc),
            "formal_dir_identity": _basis(boundary, state)["directory_identity"],
            "marker_canonical_identity_recorded": False,
            "no_backfill": True,
            "phase": "DIRECTORY_CREATED_MARKER_UNRECORDED",
            "retry_eligible": False,
            "schema_version": MARKERLESS_SCHEMA,
            "status": "CONSUMED_INCOMPLETE",
        }
        try:
            markerless_identity = _publish_once(
                state,
                store,
                "markerless-consumed-incomplete",
                boundary.formal_dir / "markerless-consumed-incomplete.json",
                markerless,
                "markerless consumed incomplete",
            )
        except Exception as markerless_error:
            state.errors.append(failure("MARKERLESS_RECEIPT_FAILED_OR_UNCERTAIN", markerless_error))
            raise CloseoutStateError(
                "formal directory is permanently consumed but its markerless receipt is unproved"
            ) from markerless_error
        raise CloseoutStateError(
            f"formal directory is markerless and permanently consumed: {markerless_identity}"
        ) from exc
    return state.marker_identity


def _phase_joins(
    state: AttemptState,
    phase: str,
    external_joins: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    rule = INCOMPLETE_PHASES.get(phase)
    if rule is None:
        raise CloseoutStateError(f"unknown consumed-incomplete phase: {phase}")
    if set(external_joins) != set(rule.external_joins):
        raise CloseoutStateError(f"{phase} external join field set drifted")
    joins: dict[str, object] = {}
    for name in PROOF_FIELDS:
        value = getattr(state, name)
        if name in rule.required_proofs and value is None:
            raise CloseoutStateError(f"{phase} lacks required proof {name}")
        if value is not None:
            if name not in rule.permitted_proofs:
                raise CloseoutStateError(f"{phase} includes future proof {name}")
            joins[name] = validate_identity_join(value, f"{phase}.{name}")
    for name, value in external_joins.items():
        if name == "frozen_outer_identity":
            joins[name] = validate_frozen_identity(
                value,
                expected_source="outer",
                expected_slot="formal",
            )
        elif name.endswith("_identity"):
            joins[name] = validate_identity_join(value, f"{phase}.{name}")
        else:
            reject_none(value, f"{phase}.{name}")
            joins[name] = dict(value) if type(value) is dict else value
    effect = _validate_effect_snapshot(_effect_snapshot(state))
    for name in rule.required_true_effects:
        if effect.get(name) is not True:
            raise CloseoutStateError(f"{phase} lacks true effect {name}")
    for name in rule.required_nonnull_effects:
        if effect.get(name) is None:
            raise CloseoutStateError(f"{phase} lacks returned effect {name}")
    for name, expected in rule.effect_equals:
        actual = effect.get(name)
        if type(actual) is not type(expected) or actual != expected:
            raise CloseoutStateError(f"{phase} effect {name} crossed its acquisition boundary")
    publications = effect["publications"]
    for name in rule.required_publications:
        publication = publications.get(name) if type(publications) is dict else None
        if type(publication) is not dict or publication.get("attempted") is not True:
            raise CloseoutStateError(f"{phase} lacks attempted publication {name}")
    return joins, effect


def publish_consumed_incomplete(
    boundary: Any,
    state: AttemptState,
    store: Any,
    *,
    phase: str,
    failure_record: Mapping[str, str],
    external_joins: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Publish exactly one phase-appropriate incomplete receipt."""

    if state.incomplete_identity is not None:
        raise CloseoutStateError("consumed-incomplete receipt cannot be repeated")
    if state.marker_identity is None:
        raise CloseoutStateError(
            "generic incomplete receipt requires the canonical attempt marker; "
            "markerless consumption has its own terminal schema"
        )
    checked_failure = validate_failure_record(
        failure_record,
        "consumed incomplete",
    )
    joins, effects = _phase_joins(state, phase, external_joins or {})
    state.irreversible_incomplete = True
    record = {
        **_base(boundary),
        "attempt_basis": _basis(boundary, state),
        "consumed": True,
        "effects": effects,
        "failure": checked_failure,
        "formal_dir": str(boundary.formal_dir),
        "joins": joins,
        "phase": phase,
        "retry_eligible": False,
        "schema_version": INCOMPLETE_SCHEMA,
        "status": "CONSUMED_INCOMPLETE",
    }
    path = boundary.formal_dir / f"incomplete-{phase.lower().replace('_', '-')}.json"
    state.incomplete_identity = _publish_once(
        state,
        store,
        "consumed-incomplete",
        path,
        record,
        f"{phase} incomplete",
    )
    return {"identity": state.incomplete_identity, "record": record}


def _validate_reference_call(
    value: object,
    *,
    label: str,
    unit_name: str,
    expected_owner: str,
) -> dict[str, str]:
    checked = _validate_reference_call_shape(value, label)
    if (
        checked["manager_owner_before"] != expected_owner
        or checked["manager_owner_after"] != expected_owner
        or checked["unit_name"] != unit_name
    ):
        raise CloseoutStateError(f"{label} identity drifted")
    return checked


def _validate_reference_verification(
    value: object,
    *,
    unit_name: str,
    expected_owner: str,
    expected_client: str,
) -> dict[str, str]:
    expected = {"client_unique_name", "manager_owner", "unit_name"}
    if type(value) is not dict or set(value) != expected or any(type(item) is not str for item in value.values()):
        raise CloseoutStateError("reference verification schema drifted")
    checked = dict(value)
    if (
        checked["client_unique_name"] != expected_client
        or checked["manager_owner"] != expected_owner
        or checked["unit_name"] != unit_name
    ):
        raise CloseoutStateError("reference verification identity drifted")
    return checked


def _validate_lock_evidence(value: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if type(value) not in {list, tuple} or len(value) != 3:
        raise CloseoutStateError("RefUnit acquisition does not bind exactly three locks")
    checked = []
    paths = set()
    for index, item in enumerate(value):
        if type(item) is not dict or set(item) != {"device", "inode", "path", "uid"}:
            raise CloseoutStateError(f"lock identity {index} schema drifted")
        reject_none(item, f"lock identity {index}")
        if (
            type(item["device"]) is not int
            or type(item["inode"]) is not int
            or type(item["uid"]) is not int
            or type(item["path"]) is not str
            or not item["path"]
            or item["path"] in paths
        ):
            raise CloseoutStateError(f"lock identity {index} is malformed or duplicated")
        paths.add(item["path"])
        checked.append(dict(item))
    if paths != set(LOCK_PATHS):
        raise CloseoutStateError("RefUnit acquisition lock path set drifted")
    return checked


def _validate_lock_release_effect(
    value: object,
    *,
    expected_locks: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    if type(value) is not dict or set(value) != {"lock_identities", "released"}:
        raise CloseoutStateError("formal lock release effect schema drifted")
    expected = _validate_lock_evidence(expected_locks)
    returned = _validate_lock_evidence(value["lock_identities"])
    if value["released"] is not True or returned != expected:
        raise CloseoutStateError("formal lock release effect does not match clearance")
    return {"lock_identities": returned, "released": True}


REFERENCE_FIELDS = {
    "HELD": frozenset(
        {
            "acquire_call",
            "connection_verification",
            "lock_evidence",
            "manager_epoch_capture",
            "resource_identity",
            "selection_identity",
        }
    ),
    "UNREF_RETURNED": frozenset(
        {
            "acquisition_identity",
            "call",
            "observer_identity",
            "pre_unref_cleanup_identity",
        }
    ),
    "UNREF_RETURNED_INCOMPLETE": frozenset(
        {"acquisition_identity", "call", "reason"}
    ),
    "CONSUMED_INCOMPLETE": frozenset(
        {
            "abort_close_returned_released",
            "connection_drop_attempts",
            "explicit_unref_proven",
            "reason",
        }
    ),
    "RELEASED": frozenset(
        {
            "acquisition_identity",
            "connection_close_returned",
            "unref_call_identity",
        }
    ),
}


def _reference_record(
    boundary: Any,
    status: str,
    unit_name: str,
    **fields: object,
) -> dict[str, object]:
    if status not in REFERENCE_FIELDS or set(fields) != set(REFERENCE_FIELDS[status]):
        raise CloseoutStateError(f"{status} reference receipt field set drifted")
    reject_none(fields, f"{status} reference receipt")
    record = {
        **_base(boundary),
        "schema_version": REFERENCE_SCHEMA,
        "status": status,
        "unit_name": unit_name,
        **fields,
    }
    if set(record) != BASE_FIELDS | {"schema_version", "status", "unit_name"} | REFERENCE_FIELDS[status]:
        raise CloseoutStateError(f"{status} reference receipt schema drifted")
    return record


def _validate_acquisition_predecessor(
    state: AttemptState,
    *,
    selection_identity: Mapping[str, Any],
    resource_identity: Mapping[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    if (
        not state.directory_created
        or state.marker_identity is None
        or state.irreversible_incomplete
        or state.barrier_identity is not None
    ):
        raise CloseoutStateError("RefUnit acquisition crossed the attempt/barrier boundary")
    for name in (
        "selection_identity",
        "outer_prelaunch_identity",
        "outer_start_identity",
        "resource_identity",
    ):
        validate_identity_join(getattr(state, name), f"RefUnit predecessor {name}")
    if not state.outer_launch_attempted or state.outer_launch_return is None:
        raise CloseoutStateError("RefUnit acquisition lacks the returned outer launch effect")
    checked_selection = validate_identity_join(selection_identity, "formal selection")
    checked_resource = validate_identity_join(resource_identity, "outer resource")
    if (
        checked_selection != state.selection_identity
        or checked_resource != state.resource_identity
    ):
        raise CloseoutStateError("RefUnit acquisition input identities drifted from attempt state")
    return checked_selection, checked_resource


def acquire_reference_once(
    boundary: Any,
    state: AttemptState,
    store: Any,
    reference: Any,
    *,
    unit_name: str,
    selection_identity: Mapping[str, Any],
    resource_identity: Mapping[str, Any],
    lock_evidence: Sequence[Mapping[str, Any]],
    manager_epoch_capture: Mapping[str, Any],
) -> dict[str, object]:
    if state.acquire_attempted or state.reference is not None:
        raise CloseoutStateError("RefUnit acquisition cannot be repeated")
    checked_selection, checked_resource = _validate_acquisition_predecessor(
        state,
        selection_identity=selection_identity,
        resource_identity=resource_identity,
    )
    state.acquire_attempted = True
    state.reference = reference
    owner = boundary.root["manager_epoch"]["dbus_unique_owner"]
    try:
        acquired = reference.acquire(unit_name=unit_name, expected_manager_owner=owner)
        state.acquire_returned = True
        state.acquire_return = dict(acquired) if type(acquired) is dict else None
        state.acquire_return = _validate_reference_call(
            acquired,
            label="RefUnit acquisition return",
            unit_name=unit_name,
            expected_owner=owner,
        )
        verification = _validate_reference_verification(
            reference.verify(expected_manager_owner=owner),
            unit_name=unit_name,
            expected_owner=owner,
            expected_client=state.acquire_return["client_unique_name"],
        )
        if type(manager_epoch_capture) is not dict or set(manager_epoch_capture) != {
            "manager_epoch",
            "transcript",
        }:
            raise CloseoutStateError("manager epoch capture schema drifted at RefUnit acquisition")
        if not same_epoch(boundary, manager_epoch_capture["manager_epoch"]):
            raise CloseoutStateError("manager epoch drifted at RefUnit acquisition")
        reject_none(manager_epoch_capture, "manager epoch capture")
        campaign = boundary.context["campaign_module"]
        campaign.validate_manager_epoch_capture_transcript(
            manager_epoch_capture["transcript"],
            expected_epoch=manager_epoch_capture["manager_epoch"],
        )
        checked_locks = _validate_lock_evidence(lock_evidence)
        record = _reference_record(
            boundary,
            "HELD",
            unit_name,
            acquire_call=state.acquire_return,
            connection_verification=verification,
            lock_evidence=checked_locks,
            manager_epoch_capture=dict(manager_epoch_capture),
            resource_identity=checked_resource,
            selection_identity=checked_selection,
        )
        state.acquire_identity = _publish_once(
            state,
            store,
            "reference-acquisition",
            boundary.formal_dir / "reference-acquisition.json",
            record,
            "reference acquisition",
        )
        return {"identity": state.acquire_identity, "kind": "RECORDED"}
    except Exception as exc:
        code = (
            "REF_ACQUIRE_RETURNED_BUT_UNRECORDED"
            if state.acquire_returned
            else "REF_ACQUIRE_FAILED_OR_UNCERTAIN"
        )
        state.errors.append(failure(code, exc))
        return {"failure": state.errors[-1], "kind": code}


def _abort_reference_once(
    boundary: Any,
    state: AttemptState,
    store: Any,
    *,
    unit_name: str,
    reason: str,
) -> dict[str, object]:
    if state.acquire_return is not None and state.acquire_return.get("unit_name") != unit_name:
        raise CloseoutStateError("reference abort unit drifted from RefUnit acquisition")
    if state.connection_action or state.abort_close_attempted or state.close_attempted:
        raise CloseoutStateError("reference terminal action was repeated")
    state.connection_action = "abort_close"
    state.abort_close_attempted = True
    try:
        state.abort_close_return = bool(state.reference.abort_close())
    except Exception as exc:
        state.errors.append(failure("CONNECTION_DROP_FAILED_OR_UNCERTAIN", exc))
        return {
            "failure": state.errors[-1],
            "kind": "CONNECTION_DROP_FAILED_OR_UNCERTAIN",
        }
    record = _reference_record(
        boundary,
        "CONSUMED_INCOMPLETE",
        unit_name,
        abort_close_returned_released=state.abort_close_return,
        connection_drop_attempts=1,
        explicit_unref_proven=False,
        reason=reason,
    )
    try:
        identity = _publish_once(
            state,
            store,
            "reference-abort-close",
            boundary.formal_dir / "reference-abort-close.json",
            record,
            "reference abort close",
        )
    except Exception as exc:
        state.errors.append(failure("CONNECTION_DROPPED_RECEIPT_UNRECORDED", exc))
        return {
            "failure": state.errors[-1],
            "kind": "CONNECTION_DROPPED_RECEIPT_UNRECORDED",
        }
    return {"identity": identity, "kind": "UNREF_UNPROVEN_CONNECTION_DROPPED"}


def finalize_reference_once(
    boundary: Any,
    state: AttemptState,
    store: Any,
    *,
    unit_name: str,
    prove_unref: bool,
    reason: str,
    observer_identity: Mapping[str, object] | None = None,
    pre_unref_cleanup_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Perform exactly one legal Unref/close or one uncertainty abort/drop."""

    normal_prerequisites = (
        observer_identity is not None,
        pre_unref_cleanup_identity is not None,
    )
    if normal_prerequisites[0] is not normal_prerequisites[1]:
        raise CloseoutStateError(
            "normal Unref requires observer and pre-Unref cleanup identities together"
        )
    if not prove_unref and any(normal_prerequisites):
        raise CloseoutStateError(
            "uncertain reference drop forbids normal Unref prerequisite identities"
        )
    if state.reference is None:
        if (
            state.acquire_attempted
            or state.acquire_returned
            or state.acquire_identity is not None
            or state.release_attempted
            or state.connection_action
        ):
            raise CloseoutStateError("reference object is absent after an irreversible reference effect")
        return {"kind": "NO_REFERENCE_OPENED"}
    if state.acquire_return is not None and state.acquire_return.get("unit_name") != unit_name:
        raise CloseoutStateError("reference terminal unit drifted from RefUnit acquisition")
    owner = boundary.root["manager_epoch"]["dbus_unique_owner"]
    if not prove_unref:
        return _abort_reference_once(
            boundary,
            state,
            store,
            unit_name=unit_name,
            reason=reason,
        )
    if state.acquire_identity is None or state.release_attempted:
        raise CloseoutStateError("canonical Unref lacks one recorded acquisition")
    checked_observer: dict[str, object] | None = None
    checked_cleanup: dict[str, object] | None = None
    if all(normal_prerequisites):
        checked_observer = validate_identity_join(
            observer_identity,
            "normal Unref observer",
        )
        checked_cleanup = validate_identity_join(
            pre_unref_cleanup_identity,
            "normal Unref pre-cleanup",
        )
        if (
            state.observer_identity not in (None, checked_observer)
            or state.pre_unref_cleanup_identity not in (None, checked_cleanup)
        ):
            raise CloseoutStateError("normal Unref prerequisite identity drifted")
    state.release_attempted = True
    try:
        released = state.reference.release(unit_name=unit_name, expected_manager_owner=owner)
        state.release_returned = True
        state.release_return = dict(released) if type(released) is dict else None
        state.release_return = _validate_reference_call(
            released,
            label="UnrefUnit return",
            unit_name=unit_name,
            expected_owner=owner,
        )
        if checked_observer is None or checked_cleanup is None:
            call = _reference_record(
                boundary,
                "UNREF_RETURNED_INCOMPLETE",
                unit_name,
                acquisition_identity=validate_identity_join(
                    state.acquire_identity,
                    "reference acquisition",
                ),
                call=state.release_return,
                reason=reason,
            )
        else:
            call = _reference_record(
                boundary,
                "UNREF_RETURNED",
                unit_name,
                acquisition_identity=validate_identity_join(
                    state.acquire_identity,
                    "reference acquisition",
                ),
                call=state.release_return,
                observer_identity=checked_observer,
                pre_unref_cleanup_identity=checked_cleanup,
            )
        state.unref_call_identity = _publish_once(
            state,
            store,
            "unref-call",
            boundary.formal_dir / "unref-call.json",
            call,
            "Unref call",
        )
        if checked_observer is not None and checked_cleanup is not None:
            state.observer_identity = dict(checked_observer)
            state.pre_unref_cleanup_identity = dict(checked_cleanup)
    except Exception as exc:
        reason = (
            "UNREF_RETURNED_BUT_UNRECORDED"
            if state.release_returned
            else "UNREF_FAILED_OR_UNCERTAIN"
        )
        state.errors.append(failure(reason, exc))
        return _abort_reference_once(
            boundary,
            state,
            store,
            unit_name=unit_name,
            reason=reason,
        )
    if state.connection_action or state.close_attempted:
        raise CloseoutStateError("reference terminal action was repeated")
    state.connection_action = "close"
    state.close_attempted = True
    try:
        state.reference.close()
        state.close_returned = True
    except Exception as exc:
        state.errors.append(failure("CONNECTION_CLOSE_FAILED_OR_UNCERTAIN", exc))
        return {
            "failure": state.errors[-1],
            "kind": "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN",
        }
    release = _reference_record(
        boundary,
        "RELEASED",
        unit_name,
        acquisition_identity=validate_identity_join(state.acquire_identity, "reference acquisition"),
        connection_close_returned=True,
        unref_call_identity=validate_identity_join(state.unref_call_identity, "Unref call"),
    )
    try:
        state.reference_release_identity = _publish_once(
            state,
            store,
            "reference-release",
            boundary.formal_dir / "reference-release.json",
            release,
            "reference release",
        )
    except Exception as exc:
        state.errors.append(failure("CONNECTION_CLOSED_RELEASE_UNRECORDED", exc))
        return {
            "failure": state.errors[-1],
            "kind": "CONNECTION_CLOSED_RELEASE_UNRECORDED",
        }
    return {"identity": state.reference_release_identity, "kind": "RECORDED"}


def _exact_record_fields(
    value: Mapping[str, object],
    expected: set[str] | frozenset[str],
    label: str,
) -> None:
    if type(value) is not dict or set(value) != set(expected):
        raise CloseoutStateError(f"{label} field set drifted")


def _validate_publication_effect_record(
    value: object,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise CloseoutStateError(f"{label} publication effect is not one object")
    expected = {"attempted", "recorded", "returned"}
    if value.get("returned") is True:
        expected.add("returned_identity")
    if value.get("recorded") is True:
        expected.add("recorded_identity")
    if "error" in value:
        expected.add("error")
    if set(value) != expected or any(
        type(value[name]) is not bool for name in ("attempted", "recorded", "returned")
    ):
        raise CloseoutStateError(f"{label} publication effect field set drifted")
    if (
        value["attempted"] is not True
        or (value["recorded"] is True and value["returned"] is not True)
    ):
        raise CloseoutStateError(f"{label} publication effect ordering drifted")
    checked = dict(value)
    if value["returned"] is True:
        checked["returned_identity"] = validate_identity_join(
            value["returned_identity"],
            f"{label} publication return",
        )
    if value["recorded"] is True:
        checked["recorded_identity"] = validate_identity_join(
            value["recorded_identity"],
            f"{label} publication readback",
        )
        if checked["recorded_identity"] != checked["returned_identity"]:
            raise CloseoutStateError(f"{label} publication identity drifted")
    if "error" in value:
        checked["error"] = validate_failure_record(
            value["error"],
            f"{label} publication",
        )
    return checked


def _validate_effect_snapshot(value: object) -> dict[str, object]:
    expected = {
        "abort_close_attempted",
        "abort_close_return",
        "acquire_attempted",
        "acquire_return",
        "acquire_returned",
        "close_attempted",
        "close_returned",
        "connection_action",
        "detached_success_verifier_attempted",
        "detached_success_verifier_return",
        "guardian_close_attempted",
        "guardian_close_return",
        "lock_release_attempted",
        "lock_release_return",
        "outer_launch_attempted",
        "outer_launch_return",
        "publications",
        "release_attempted",
        "release_return",
        "release_returned",
    }
    if type(value) is not dict or set(value) != expected:
        raise CloseoutStateError("consumed-incomplete effect field set drifted")
    for name in (
        "abort_close_attempted",
        "acquire_attempted",
        "acquire_returned",
        "close_attempted",
        "close_returned",
        "detached_success_verifier_attempted",
        "guardian_close_attempted",
        "lock_release_attempted",
        "outer_launch_attempted",
        "release_attempted",
        "release_returned",
    ):
        if type(value[name]) is not bool:
            raise CloseoutStateError(f"consumed-incomplete effect {name} is not boolean")
    if (
        value["connection_action"] not in {"", "abort_close", "close"}
        or (
            value["outer_launch_return"] is not None
            and value["outer_launch_attempted"] is not True
        )
        or (
            value["abort_close_return"] is not None
            and type(value["abort_close_return"]) is not bool
        )
        or (
            value["abort_close_return"] is not None
            and value["abort_close_attempted"] is not True
        )
        or (value["acquire_returned"] and not value["acquire_attempted"])
        or (value["release_returned"] and not value["release_attempted"])
        or (value["close_returned"] and not value["close_attempted"])
        or (
            value["guardian_close_return"] is not None
            and value["guardian_close_attempted"] is not True
        )
        or (
            value["lock_release_return"] is not None
            and value["lock_release_attempted"] is not True
        )
        or (
            value["detached_success_verifier_return"] is not None
            and value["detached_success_verifier_attempted"] is not True
        )
        or (
            value["abort_close_attempted"]
            is not (value["connection_action"] == "abort_close")
        )
        or (
            value["close_attempted"]
            is not (value["connection_action"] == "close")
        )
    ):
        raise CloseoutStateError("consumed-incomplete irreversible effect ordering drifted")
    if value["outer_launch_return"] is not None:
        if type(value["outer_launch_return"]) is not dict or not value["outer_launch_return"]:
            raise CloseoutStateError("outer launch return effect is malformed")
        reject_none(value["outer_launch_return"], "outer launch return effect")
    for name in (
        "guardian_close_return",
        "lock_release_return",
        "detached_success_verifier_return",
    ):
        returned = value[name]
        if returned is not None:
            if type(returned) is not dict or not returned:
                raise CloseoutStateError(f"{name} is malformed")
            reject_none(returned, name)
    for returned_name, return_name in (
        ("acquire_returned", "acquire_return"),
        ("release_returned", "release_return"),
    ):
        returned = value[returned_name]
        result = value[return_name]
        if returned is True:
            if type(result) is not dict:
                raise CloseoutStateError(f"{return_name} is absent after a returned call")
            _validate_reference_call_shape(result, return_name)
        elif result is not None:
            raise CloseoutStateError(f"{return_name} exists before its call returned")
    publications = value["publications"]
    if type(publications) is not dict or any(
        type(key) is not str or not key for key in publications
    ):
        raise CloseoutStateError("publication effect map is malformed")
    checked_publications = {
        key: _validate_publication_effect_record(item, key)
        for key, item in publications.items()
    }
    checked = dict(value)
    checked["publications"] = checked_publications
    return checked


def _validate_reference_call_shape(
    value: object,
    label: str,
) -> dict[str, str]:
    expected = {
        "client_unique_name",
        "manager_owner_after",
        "manager_owner_before",
        "unit_name",
    }
    if type(value) is not dict or set(value) != expected or any(
        type(value[name]) is not str or not value[name] for name in expected
    ):
        raise CloseoutStateError(f"{label} reference-call schema drifted")
    if (
        not value["client_unique_name"].startswith(":")
        or not value["manager_owner_before"].startswith(":")
        or value["manager_owner_before"] != value["manager_owner_after"]
        or UNIT_RE.fullmatch(value["unit_name"]) is None
    ):
        raise CloseoutStateError(f"{label} reference-call identity drifted")
    return dict(value)


def _validate_reference_terminal(value: object) -> dict[str, object]:
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise CloseoutStateError("containment reference terminal is malformed")
    kind = value["kind"]
    if kind == "NO_REFERENCE_OPENED":
        if set(value) != {"kind"}:
            raise CloseoutStateError(
                "no-reference containment terminal field set drifted"
            )
        return {"kind": kind}
    identity_kinds = {"RECORDED", "UNREF_UNPROVEN_CONNECTION_DROPPED"}
    failure_kinds = {
        "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN",
        "CONNECTION_CLOSED_RELEASE_UNRECORDED",
        "CONNECTION_DROP_FAILED_OR_UNCERTAIN",
        "CONNECTION_DROPPED_RECEIPT_UNRECORDED",
    }
    if kind in identity_kinds:
        if set(value) != {"identity", "kind"}:
            raise CloseoutStateError("containment reference identity terminal drifted")
        return {
            "identity": validate_identity_join(
                value["identity"],
                "containment reference terminal",
            ),
            "kind": kind,
        }
    if kind in failure_kinds:
        if set(value) != {"failure", "kind"}:
            raise CloseoutStateError("containment reference failure terminal drifted")
        return {
            "failure": validate_failure_record(
                value["failure"],
                "containment reference terminal",
            ),
            "kind": kind,
        }
    if kind == "REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN":
        if set(value) not in (
            {"failure", "kind"},
            {"connection_drop", "failure", "kind"},
        ):
            raise CloseoutStateError("containment recovery terminal field set drifted")
        checked: dict[str, object] = {
            "failure": validate_failure_record(
                value["failure"],
                "containment reference recovery",
            ),
            "kind": kind,
        }
        if "connection_drop" in value:
            dropped = _validate_reference_terminal(value["connection_drop"])
            if dropped["kind"] == "RECORDED":
                raise CloseoutStateError("containment recovery cannot regain success")
            checked["connection_drop"] = dropped
        return checked
    raise CloseoutStateError(f"unknown containment reference terminal: {kind}")


def _validate_supervisor(value: object) -> dict[str, int]:
    return validate_process_identity(value, "containment supervisor identity")


def _recorded_publication_identity(
    effects: Mapping[str, object],
    key: str,
) -> dict[str, object]:
    publications = effects["publications"]
    if type(publications) is not dict or key not in publications:
        raise CloseoutStateError(f"required {key} publication effect is absent")
    publication = publications[key]
    if (
        type(publication) is not dict
        or publication.get("recorded") is not True
        or "recorded_identity" not in publication
    ):
        raise CloseoutStateError(f"required {key} publication is not recorded")
    return validate_identity_join(
        publication["recorded_identity"],
        f"{key} publication",
    )


def _validate_attempt_basis(
    value: object,
    effects: Mapping[str, object],
) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != {"identity", "kind"}
        or value["kind"] != "RECORDED"
    ):
        raise CloseoutStateError("containment incomplete lacks its recorded attempt basis")
    identity = validate_identity_join(value["identity"], "attempt consumption")
    if identity != _recorded_publication_identity(effects, "attempt-consumption"):
        raise CloseoutStateError("attempt basis does not join its publication effect")
    return {"identity": identity, "kind": "RECORDED"}


def _validate_reference_terminal_joins(
    terminal: Mapping[str, object],
    *,
    effects: Mapping[str, object],
    joins: Mapping[str, object],
    errors: Sequence[Mapping[str, str]],
) -> None:
    kind = terminal["kind"]
    if kind == "RECORDED":
        if (
            effects["connection_action"] != "close"
            or effects["release_returned"] is not True
            or effects["close_returned"] is not True
            or terminal["identity"] != joins.get("reference_release_identity")
            or "unref_call_identity" not in joins
            or terminal["identity"]
            != _recorded_publication_identity(effects, "reference-release")
            or joins["unref_call_identity"]
            != _recorded_publication_identity(effects, "unref-call")
        ):
            raise CloseoutStateError("recorded reference terminal join drifted")
        return
    if kind == "UNREF_UNPROVEN_CONNECTION_DROPPED":
        if (
            effects["connection_action"] != "abort_close"
            or effects["abort_close_attempted"] is not True
            or terminal["identity"]
            != _recorded_publication_identity(
                effects,
                "reference-abort-close",
            )
        ):
            raise CloseoutStateError("abort-close reference terminal join drifted")
        return
    if kind == "REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN":
        if terminal["failure"] not in errors:
            raise CloseoutStateError("reference recovery failure is absent from hold errors")
        dropped = terminal.get("connection_drop")
        if dropped is not None:
            _validate_reference_terminal_joins(
                dropped,
                effects=effects,
                joins=joins,
                errors=errors,
            )
        return
    if kind in {
        "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN",
        "CONNECTION_CLOSED_RELEASE_UNRECORDED",
    } and (
        effects["connection_action"] != "close"
        or effects["close_attempted"] is not True
    ):
        raise CloseoutStateError("connection-close failure effect drifted")
    if kind in {
        "CONNECTION_DROP_FAILED_OR_UNCERTAIN",
        "CONNECTION_DROPPED_RECEIPT_UNRECORDED",
    } and (
        effects["connection_action"] != "abort_close"
        or effects["abort_close_attempted"] is not True
    ):
        raise CloseoutStateError("connection-drop failure effect drifted")
    if terminal["failure"] not in errors:
        raise CloseoutStateError("reference terminal failure is absent from hold errors")


def verify_detached_incomplete_chain(
    *,
    expected_campaign_root_identity: Mapping[str, object],
    expected_package_id: str,
    incomplete_record: Mapping[str, object],
    incomplete_identity: Mapping[str, object],
    hold_record: Mapping[str, object],
    hold_identity: Mapping[str, object],
    clearance_record: Mapping[str, object],
    clearance_identity: Mapping[str, object],
    lock_release_record: Mapping[str, object],
    lock_release_identity: Mapping[str, object],
) -> dict[str, object]:
    """Purely verify one frozen consumed-incomplete chain.

    This function performs no I/O and publishes nothing.  Its record/identity
    pairs must already come from the same package-pinned, same-FD snapshots;
    their byte binding is an external caller precondition.  A future package
    snapshot may invoke it in a detached process, but this foundation does not
    claim that an in-process call is detached evidence.
    """

    expected_root = validate_identity_join(
        expected_campaign_root_identity,
        "expected campaign root",
    )
    if (
        type(expected_package_id) is not str
        or IDENTITY_SHA_RE.fullmatch(expected_package_id) is None
    ):
        raise CloseoutStateError("expected package ID is malformed")
    identities = {
        "clearance_identity": validate_identity_join(clearance_identity, "clearance"),
        "hold_identity": validate_identity_join(hold_identity, "containment hold"),
        "incomplete_identity": validate_identity_join(incomplete_identity, "consumed incomplete"),
        "lock_release_identity": validate_identity_join(lock_release_identity, "lock release"),
    }
    incomplete_fields = BASE_FIELDS | {
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
    hold_fields = BASE_FIELDS | {
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
    clearance_fields = BASE_FIELDS | {
        "containment_hold_identity",
        "final_observation",
        "lock_identities",
        "outcome",
        "schema_version",
        "status",
        "success_eligible",
    }
    release_fields = BASE_FIELDS | {
        "containment_clearance_identity",
        "effect",
        "guardian_absence_identity",
        "schema_version",
        "status",
    }
    for value, fields, label in (
        (incomplete_record, incomplete_fields, "consumed incomplete"),
        (hold_record, hold_fields, "containment hold"),
        (clearance_record, clearance_fields, "containment clearance"),
        (lock_release_record, release_fields, "lock release"),
    ):
        _exact_record_fields(value, fields, label)
        _validate_base_record(
            value,
            expected_campaign_root_identity=expected_root,
            expected_package_id=expected_package_id,
        )
    checked_failure = validate_failure_record(
        incomplete_record["failure"],
        "consumed incomplete",
    )
    if (
        type(incomplete_record["formal_dir"]) is not str
        or not Path(incomplete_record["formal_dir"]).is_absolute()
    ):
        raise CloseoutStateError("consumed incomplete formal directory is malformed")
    effects = _validate_effect_snapshot(incomplete_record["effects"])
    attempt_basis = _validate_attempt_basis(
        incomplete_record["attempt_basis"],
        effects,
    )
    joins = incomplete_record["joins"]
    containment_phase = incomplete_record.get("phase")
    required_joins = {
        "acquire_identity",
        "child_audit_identity",
        "frozen_outer_identity",
        "outer_prelaunch_identity",
        "outer_start_identity",
        "resource_identity",
        "selection_identity",
    }
    if containment_phase == "CONTAINMENT_HOLD":
        required_joins.add("barrier_identity")
    permitted_joins = required_joins | {"reference_release_identity", "unref_call_identity"}
    if (
        type(joins) is not dict
        or not required_joins.issubset(joins)
        or not set(joins).issubset(permitted_joins)
    ):
        raise CloseoutStateError("detached incomplete proof join field set drifted")
    for name, value in joins.items():
        if name == "frozen_outer_identity":
            validate_frozen_identity(
                value,
                expected_source="outer",
                expected_slot="formal",
            )
        else:
            validate_identity_join(value, f"detached {name}")
    if joins["acquire_identity"] != _recorded_publication_identity(
        effects,
        "reference-acquisition",
    ):
        raise CloseoutStateError("reference acquisition join drifted")
    for join_name, publication_name in (
        ("unref_call_identity", "unref-call"),
        ("reference_release_identity", "reference-release"),
    ):
        if (
            join_name in joins
            and joins[join_name]
            != _recorded_publication_identity(effects, publication_name)
        ):
            raise CloseoutStateError(f"{join_name} publication join drifted")
    frozen_ledger = validate_frozen_ledger(hold_record["frozen_ledger"])
    frozen_ledger["child_audit_identity"] = validate_identity_join(
        frozen_ledger["child_audit_identity"],
        "detached child audit",
    )
    if (
        frozen_ledger["child_audit_identity"] != joins["child_audit_identity"]
        or frozen_ledger.get("outer") != joins["frozen_outer_identity"]
    ):
        raise CloseoutStateError("containment hold does not bind the incomplete frozen ledger")
    checked_hold_locks = _validate_lock_evidence(hold_record["lock_identities"])
    checked_clearance_locks = _validate_lock_evidence(clearance_record["lock_identities"])
    if checked_hold_locks != checked_clearance_locks:
        raise CloseoutStateError("containment lock identity changed before clearance")
    observation = validate_absence_observation(
        clearance_record["final_observation"],
        ledger=frozen_ledger,
    )
    hold_errors = validate_failure_list(hold_record["errors"], "containment hold")
    hold_failure = validate_failure_record(hold_record["failure"], "containment hold")
    reference_terminal = _validate_reference_terminal(
        hold_record["reference_terminal"]
    )
    supervisor = _validate_supervisor(hold_record["supervisor"])
    _validate_reference_terminal_joins(
        reference_terminal,
        effects=effects,
        joins=joins,
        errors=hold_errors,
    )
    lock_effect = _validate_lock_release_effect(
        lock_release_record["effect"],
        expected_locks=checked_clearance_locks,
    )
    guardian_absence_identity = validate_identity_join(
        lock_release_record["guardian_absence_identity"],
        "containment guardian absence",
    )
    if (
        incomplete_record.get("schema_version") != INCOMPLETE_SCHEMA
        or incomplete_record.get("status") != "CONSUMED_INCOMPLETE"
        or incomplete_record.get("phase")
        not in {
            "CONTAINMENT_HOLD",
            "BARRIER_FAILED_OR_UNCERTAIN_CONTAINMENT_HOLD",
        }
        or incomplete_record.get("consumed") is not True
        or incomplete_record.get("retry_eligible") is not False
        or incomplete_record.get("failure") != checked_failure
        or incomplete_record.get("attempt_basis") != attempt_basis
        or hold_record.get("schema_version") != HOLD_SCHEMA
        or hold_record.get("status") != "CONTAINMENT_HOLD"
        or hold_record.get("attempt_incomplete_identity") != identities["incomplete_identity"]
        or hold_failure != checked_failure
        or hold_record.get("frozen_ledger") != frozen_ledger
        or hold_record.get("errors") != hold_errors
        or hold_record.get("reference_terminal") != reference_terminal
        or hold_record.get("supervisor") != supervisor
        or hold_record.get("experiment_progress_active") is not False
        or hold_record.get("isolation_active") is not True
        or hold_record.get("outcome") != "INCOMPLETE"
        or type(hold_record.get("poll_interval_seconds")) is not float
        or hold_record.get("poll_interval_seconds") != HOLD_POLL_SECONDS
        or hold_record.get("success_eligible") is not False
        or clearance_record.get("schema_version") != HOLD_CLEAR_SCHEMA
        or clearance_record.get("status") != "CONTAINMENT_CLEARED_AFTER_HOLD"
        or clearance_record.get("containment_hold_identity") != identities["hold_identity"]
        or clearance_record.get("final_observation") != observation
        or clearance_record.get("outcome") != "INCOMPLETE"
        or clearance_record.get("success_eligible") is not False
        or clearance_record.get("lock_identities") != hold_record.get("lock_identities")
        or lock_release_record.get("schema_version") != LOCK_RELEASE_SCHEMA
        or lock_release_record.get("status") != "RELEASED"
        or lock_release_record.get("containment_clearance_identity") != identities["clearance_identity"]
        or lock_release_record.get("effect") != lock_effect
        or lock_release_record.get("guardian_absence_identity")
        != guardian_absence_identity
    ):
        raise CloseoutStateError("detached incomplete chain join drifted")
    return {
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "campaign_root_identity": expected_root,
        "input_identities": identities,
        "lower_bound": None,
        "outcome": "INCOMPLETE",
        "package_id": expected_package_id,
        "production_certified": False,
        "schema_version": DETACHED_INCOMPLETE_SCHEMA,
        "status": "VERIFIED_INCOMPLETE",
        "success_eligible": False,
        "upper_bound": [1188, 18],
    }


class ContainmentHoldCoordinator:
    """Keep the supervisor and all locks alive until exact absence is observed.

    This is process-local containment, not durable quarantine.  SIGKILL,
    supervisor death, kernel failure, and reboot remain external platform
    assumptions, so this class is non-authorizing until a separately approved
    formal controller closes that boundary.
    """

    def __init__(
        self,
        boundary: Any,
        state: AttemptState,
        store: Any,
        port: Any,
        *,
        waiter: Any,
        latch: Any | None = None,
    ) -> None:
        self.boundary = boundary
        self.state = state
        self.store = store
        self.port = port
        self.waiter = waiter
        self.latch = latch

    def _publish_hold(
        self,
        *,
        ledger: Mapping[str, object],
        failure_record: Mapping[str, str],
        reference_terminal: Mapping[str, object],
    ) -> dict[str, object]:
        if self.state.incomplete_identity is None:
            raise CloseoutStateError("containment hold lacks its consumed-incomplete proof")
        checked_ledger = validate_frozen_ledger(ledger)
        checked_ledger["child_audit_identity"] = validate_identity_join(
            checked_ledger["child_audit_identity"],
            "containment child audit",
        )
        checked_failure = validate_failure_record(
            failure_record,
            "containment hold",
        )
        checked_reference_terminal = _validate_reference_terminal(reference_terminal)
        checked_errors = validate_failure_list(self.state.errors, "containment hold")
        checked_locks = _validate_lock_evidence(self.port.lock_evidence())
        supervisor = _validate_supervisor(
            {
                "pid": os.getpid(),
                "starttime": self.boundary.context[
                    "campaign_module"
                ]._read_proc_starttime(  # noqa: SLF001
                    os.getpid()
                ),
            }
        )
        record = {
            **_base(self.boundary),
            "attempt_incomplete_identity": validate_identity_join(
                self.state.incomplete_identity,
                "attempt incomplete",
            ),
            "errors": checked_errors,
            "experiment_progress_active": False,
            "failure": checked_failure,
            "frozen_ledger": checked_ledger,
            "isolation_active": True,
            "lock_identities": checked_locks,
            "outcome": "INCOMPLETE",
            "poll_interval_seconds": HOLD_POLL_SECONDS,
            "reference_terminal": checked_reference_terminal,
            "schema_version": HOLD_SCHEMA,
            "status": "CONTAINMENT_HOLD",
            "success_eligible": False,
            "supervisor": supervisor,
        }
        self.state.hold_identity = _publish_once(
            self.state,
            self.store,
            "containment-hold",
            self.boundary.formal_dir / "containment-hold.json",
            record,
            "containment hold",
        )
        return {"identity": self.state.hold_identity, "record": record}

    def _append_error_once(self, code: str, error: BaseException | str) -> dict[str, str]:
        item = failure(code, error)
        if item not in self.state.errors:
            self.state.errors.append(item)
        return item

    def _safe_announce(self, event: Mapping[str, object]) -> None:
        try:
            self.waiter.announce(dict(event))
        except BaseException as exc:
            self._append_error_once("CONTAINMENT_ANNOUNCEMENT_FAILED", exc)

    def _safe_wait(self) -> None:
        try:
            self.waiter.wait(HOLD_POLL_SECONDS)
            return
        except BaseException as exc:
            self._append_error_once("CONTAINMENT_WAITER_FAILED", exc)
        deadline = time.monotonic() + HOLD_POLL_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            try:
                time.sleep(remaining)
            except BaseException as exc:
                self._append_error_once("CONTAINMENT_FALLBACK_WAIT_INTERRUPTED", exc)

    def _announce_gap(self, code: str, error: BaseException | str) -> None:
        item = self._append_error_once(code, error)
        self._safe_announce(
            {
                "failure": item,
                "isolation_active": True,
                "status": "CONTAINMENT_HOLD_EVIDENCE_GAP",
            }
        )

    def _latch_records(self) -> list[object]:
        if self.latch is None:
            return []
        try:
            return list(self.latch.records)
        except BaseException as exc:
            self._announce_gap("CONTAINMENT_SIGNAL_OBSERVATION_FAILED", exc)
            return []

    def _publish_signal_once(self, records: Sequence[object]) -> None:
        effect = self.state.publication("containment-hold-signal")
        if effect.attempted:
            return
        record = {
            **_base(self.boundary),
            "containment_hold_identity": self.state.hold_identity,
            "schema_version": HOLD_SCHEMA,
            "signals": list(records),
            "status": "CONTAINMENT_HOLD",
        }
        try:
            _publish_once(
                self.state,
                self.store,
                "containment-hold-signal",
                self.boundary.formal_dir / "containment-hold-signal.json",
                record,
                "containment hold signal",
            )
        except BaseException as exc:
            self._announce_gap("HOLD_SIGNAL_PUBLICATION_FAILED", exc)

    def enter(
        self,
        *,
        unit_name: str,
        failure_record: Mapping[str, str],
        ledger: Mapping[str, object],
        reference_reason: str,
        incomplete_phase: str = "CONTAINMENT_HOLD",
    ) -> dict[str, object]:
        """Block through residual runtime, then release once and stay incomplete.

        No recoverable observer-side exception is allowed to unwind this
        method while the exact three-lock lease is the only quarantine.
        """

        self.state.irreversible_incomplete = True
        if incomplete_phase not in {
            "CONTAINMENT_HOLD",
            "BARRIER_FAILED_OR_UNCERTAIN_CONTAINMENT_HOLD",
        }:
            raise CloseoutStateError(
                "containment coordinator received a non-containment phase"
            )
        checked_ledger: dict[str, object] | None = None
        try:
            checked_ledger = validate_frozen_ledger(ledger)
            checked_ledger["child_audit_identity"] = validate_identity_join(
                checked_ledger["child_audit_identity"],
                "containment child audit",
            )
        except BaseException as exc:
            self._announce_gap("CONTAINMENT_LEDGER_INVALID", exc)

        try:
            reference_terminal = finalize_reference_once(
                self.boundary,
                self.state,
                self.store,
                unit_name=unit_name,
                prove_unref=self.state.acquire_identity is not None,
                reason=reference_reason,
            )
        except BaseException as exc:
            item = self._append_error_once(
                "REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN",
                exc,
            )
            reference_terminal = {
                "failure": item,
                "kind": "REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN",
            }
            if (
                self.state.reference is not None
                and not self.state.connection_action
                and not self.state.abort_close_attempted
                and not self.state.close_attempted
            ):
                try:
                    reference_terminal["connection_drop"] = finalize_reference_once(
                        self.boundary,
                        self.state,
                        self.store,
                        unit_name=unit_name,
                        prove_unref=False,
                        reason="REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN",
                    )
                except BaseException as drop_error:
                    dropped = self._append_error_once(
                        "REFERENCE_CONNECTION_DROP_FAILED_OR_UNCERTAIN",
                        drop_error,
                    )
                    reference_terminal["connection_drop"] = {
                        "failure": dropped,
                        "kind": "CONNECTION_DROP_FAILED_OR_UNCERTAIN",
                    }

        incomplete: dict[str, object] = {}
        hold: dict[str, object] = {}
        if checked_ledger is not None:
            try:
                incomplete = publish_consumed_incomplete(
                    self.boundary,
                    self.state,
                    self.store,
                    phase=incomplete_phase,
                    failure_record=failure_record,
                    external_joins={
                        "child_audit_identity": checked_ledger[
                            "child_audit_identity"
                        ],
                        "frozen_outer_identity": checked_ledger["outer"],
                    },
                )
            except BaseException as exc:
                self._announce_gap(
                    "CONTAINMENT_INCOMPLETE_PUBLICATION_FAILED",
                    exc,
                )
        if incomplete and checked_ledger is not None:
            try:
                hold = self._publish_hold(
                    ledger=checked_ledger,
                    failure_record=failure_record,
                    reference_terminal=reference_terminal,
                )
            except BaseException as exc:
                self._announce_gap("CONTAINMENT_HOLD_PUBLICATION_FAILED", exc)

        clearance: dict[str, object] = {}
        while True:
            self.state.hold_poll_count += 1
            signal_records = self._latch_records()
            if signal_records and self.state.hold_identity is not None:
                try:
                    self._publish_signal_once(signal_records)
                except BaseException as exc:
                    self._announce_gap(
                        "HOLD_SIGNAL_PROCESSING_FAILED",
                        exc,
                    )
            if checked_ledger is None:
                self._announce_gap(
                    "CONTAINMENT_LEDGER_UNPROVEN",
                    "the finite child ledger cannot support absence",
                )
                self._safe_wait()
                continue
            try:
                locks = _validate_lock_evidence(self.port.lock_evidence())
                raw_observation = self.port.observe_frozen_absence(checked_ledger)
                if (
                    type(raw_observation) is not dict
                    or type(raw_observation.get("all_absent")) is not bool
                ):
                    raise CloseoutStateError(
                        "containment observer returned a malformed status"
                    )
            except BaseException as exc:
                self._announce_gap("CONTAINMENT_OBSERVATION_FAILED", exc)
                self._safe_wait()
                continue
            if raw_observation["all_absent"] is not True:
                self._safe_announce(
                    {
                        "isolation_active": True,
                        "poll": self.state.hold_poll_count,
                        "status": "CONTAINMENT_HOLD",
                    }
                )
                self._safe_wait()
                continue
            try:
                observation = validate_absence_observation(
                    raw_observation,
                    ledger=checked_ledger,
                )
                if (
                    hold
                    and locks != hold["record"]["lock_identities"]
                ):
                    raise CloseoutStateError(
                        "three-lock identity drifted during containment hold"
                    )
            except BaseException as exc:
                self._announce_gap(
                    "CONTAINMENT_ABSENCE_VALIDATION_FAILED",
                    exc,
                )
                self._safe_wait()
                continue
            if not incomplete or not hold:
                self._announce_gap(
                    "CONTAINMENT_HOLD_EVIDENCE_GAP",
                    "absence observed but prerequisite receipts are missing",
                )
                self._safe_wait()
                continue
            clearance_effect = self.state.publication("containment-clearance")
            if clearance_effect.attempted:
                code = (
                    "CONTAINMENT_CLEARANCE_UNCERTAIN"
                    if clearance_effect.recorded_identity is None
                    else "CONTAINMENT_CLEARANCE_ALREADY_RECORDED"
                )
                self._announce_gap(
                    code,
                    "clearance publication cannot be attempted again",
                )
                self._safe_wait()
                continue
            clearance_record = {
                **_base(self.boundary),
                "containment_hold_identity": validate_identity_join(
                    self.state.hold_identity,
                    "containment hold",
                ),
                "final_observation": observation,
                "lock_identities": locks,
                "outcome": "INCOMPLETE",
                "schema_version": HOLD_CLEAR_SCHEMA,
                "status": "CONTAINMENT_CLEARED_AFTER_HOLD",
                "success_eligible": False,
            }
            try:
                self.state.hold_clearance_identity = _publish_once(
                    self.state,
                    self.store,
                    "containment-clearance",
                    self.boundary.formal_dir
                    / "containment-cleared-after-hold.json",
                    clearance_record,
                    "containment cleared after hold",
                )
                clearance = {
                    "identity": self.state.hold_clearance_identity,
                    "record": clearance_record,
                }
            except BaseException as exc:
                self._announce_gap(
                    "CONTAINMENT_CLEARANCE_PUBLICATION_FAILED",
                    exc,
                )
                self._safe_wait()
                continue
            break

        if self.state.lock_release_attempted:
            self._append_error_once(
                "LOCK_RELEASE_REPEATED",
                "formal locks cannot be released twice",
            )
            return {
                "errors": list(self.state.errors),
                "outcome": "INCOMPLETE",
                "status": "CONSUMED_INCOMPLETE",
            }
        expected_release_locks = _validate_lock_evidence(
            clearance["record"]["lock_identities"]
        )
        if not self.state.containment_guardian_absence_attempted:
            self.state.containment_guardian_absence_attempted = True
            try:
                self.state.containment_guardian_absence_identity = (
                    validate_identity_join(
                        self.port.prepare_guardian_release(checked_ledger),
                        "containment guardian absence",
                    )
                )
            except BaseException as exc:
                self._announce_gap(
                    "CONTAINMENT_GUARDIAN_ABSENCE_FAILED_OR_UNCERTAIN",
                    exc,
                )
        if self.state.containment_guardian_absence_identity is None:
            self._safe_wait()
            while True:
                self._safe_announce(
                    {
                        "isolation_active": True,
                        "reason": "GUARDIAN_ABSENCE_EVIDENCE_UNCERTAIN",
                        "status": "CONTAINMENT_HOLD",
                    }
                )
                self._safe_wait()
        self.state.lock_release_attempted = True
        try:
            raw_release = self.port.release_locks_once()
            self.state.lock_release_return = _validate_lock_release_effect(
                raw_release,
                expected_locks=expected_release_locks,
            )
        except BaseException as exc:
            self._append_error_once("LOCK_RELEASE_FAILED_OR_UNCERTAIN", exc)
            return {
                "errors": list(self.state.errors),
                "outcome": "INCOMPLETE",
                "status": "CONSUMED_INCOMPLETE",
            }
        release = {
            **_base(self.boundary),
            "containment_clearance_identity": validate_identity_join(
                self.state.hold_clearance_identity,
                "containment clearance",
            ),
            "effect": self.state.lock_release_return,
            "guardian_absence_identity": validate_identity_join(
                self.state.containment_guardian_absence_identity,
                "containment guardian absence",
            ),
            "schema_version": LOCK_RELEASE_SCHEMA,
            "status": "RELEASED",
        }
        try:
            self.state.lock_release_identity = _publish_once(
                self.state,
                self.store,
                "lock-release",
                self.boundary.formal_dir / "lock-release.json",
                release,
                "formal lock release",
            )
        except BaseException as exc:
            self._append_error_once(
                "LOCK_RELEASE_RETURNED_BUT_UNRECORDED",
                exc,
            )
            return {
                "detached_replay_input": {
                    "clearance_identity": self.state.hold_clearance_identity,
                    "clearance_record": clearance["record"],
                    "guardian_absence_identity": (
                        self.state.containment_guardian_absence_identity
                    ),
                    "hold_identity": self.state.hold_identity,
                    "hold_record": hold["record"],
                    "incomplete_identity": self.state.incomplete_identity,
                    "incomplete_record": incomplete["record"],
                    "lock_release_effect": self.state.lock_release_return,
                    "lock_release_identity": "unrecorded",
                    "lock_release_publication": self.state.publication(
                        "lock-release"
                    ).record(),
                    "lock_release_record": release,
                },
                "detached_replay_required": True,
                "errors": list(self.state.errors),
                "outcome": "INCOMPLETE",
                "status": "CONSUMED_INCOMPLETE",
            }
        return {
            "detached_replay_input": {
                "clearance_identity": self.state.hold_clearance_identity,
                "clearance_record": clearance["record"],
                "hold_identity": self.state.hold_identity,
                "hold_record": hold["record"],
                "incomplete_identity": self.state.incomplete_identity,
                "incomplete_record": incomplete["record"],
                "lock_release_identity": self.state.lock_release_identity,
                "lock_release_record": release,
            },
            "detached_replay_required": True,
            "errors": list(self.state.errors),
            "outcome": "INCOMPLETE",
            "status": "CONSUMED_INCOMPLETE",
        }
