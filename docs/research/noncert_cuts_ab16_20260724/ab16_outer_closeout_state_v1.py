#!/usr/bin/env python3
"""Monotone receipt and RefUnit state for the one AB16 formal campaign.

This campaign-local module owns proof/effect state and no-overwrite receipts.
It does not launch or discover units.  A caller supplies the already frozen
finite child/outer ledger and the live three-lock owner.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import os
from pathlib import Path
import stat
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


class CloseoutStateError(RuntimeError):
    """A monotone AB16 closeout invariant failed closed."""


def failure(code: str, error: BaseException | str) -> dict[str, str]:
    detail = str(error) if isinstance(error, str) else f"{type(error).__name__}: {error}"
    return {"code": code, "detail": detail}


def reject_none(value: object, label: str) -> None:
    if value is None:
        raise CloseoutStateError(f"{label} contains an unproved null join")
    children = value.items() if type(value) is dict else enumerate(value) if type(value) is list else ()
    for key, item in children:
        reject_none(item, f"{label}.{key}")


def _same_epoch(boundary: Any, observed: object) -> bool:
    try:
        return bool(boundary.context["campaign_module"].same_manager_epoch(
            observed, boundary.root["manager_epoch"]
        ))
    except Exception:
        return False


@dataclass
class AttemptState:
    """Separate monotone proof facts from irreversible runtime effects."""

    directory_created: bool = False
    marker_identity: dict[str, object] | None = None
    selection_identity: dict[str, object] | None = None
    outer_prelaunch_identity: dict[str, object] | None = None
    outer_launch_returned: bool = False
    outer_start_identity: dict[str, object] | None = None
    resource_identity: dict[str, object] | None = None
    barrier_identity: dict[str, object] | None = None
    reference: Any | None = None
    acquire_attempted: bool = False
    acquire_return: dict[str, Any] | None = None
    acquire_identity: dict[str, object] | None = None
    release_attempted: bool = False
    release_return: dict[str, Any] | None = None
    unref_call_identity: dict[str, object] | None = None
    connection_action: str = ""
    reference_release_identity: dict[str, object] | None = None
    irreversible_incomplete: bool = False
    incomplete_identity: dict[str, object] | None = None
    hold_identity: dict[str, object] | None = None
    hold_clearance_identity: dict[str, object] | None = None
    hold_poll_count: int = 0
    lock_release_attempted: bool = False
    lock_release_return: dict[str, object] | None = None
    lock_release_identity: dict[str, object] | None = None
    errors: list[dict[str, str]] = field(default_factory=list)


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
        return {"identity": state.marker_identity, "kind": "RECORDED"}
    if state.directory_created:
        return {"directory_identity": _directory_identity(boundary.formal_dir),
                "kind": "DIRECTORY_CREATED_UNRECORDED"}
    raise CloseoutStateError("attempt has no consumed fact basis")


def _base(boundary: Any) -> dict[str, object]:
    return {
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "campaign_root_identity": boundary.context["root_identity"],
        "lower_bound": None,
        "package_id": boundary.root["package"]["package_id"],
        "production_certified": False,
        "upper_bound": [1188, 18],
    }


def publish_attempt_consumption(
    boundary: Any, state: AttemptState, store: Any, *, created_at_utc: str
) -> dict[str, object]:
    """Publish the sole marker, or permanently consume this markerless directory."""

    if not state.directory_created or state.marker_identity is not None:
        raise CloseoutStateError("attempt marker has the wrong predecessor")
    marker = {**_base(boundary), "consumed": True, "created_at_utc": created_at_utc,
              "formal_dir": str(boundary.formal_dir), "retry_eligible": False,
              "schema_version": CONSUMPTION_SCHEMA}
    try:
        state.marker_identity = store.publish(
            boundary.formal_dir / "attempt-consumption.json", marker, "formal attempt consumption"
        )
    except Exception as exc:
        state.irreversible_incomplete = True
        markerless = {
            **_base(boundary), "consumed": True, "failure": failure("ATTEMPT_MARKER_UNRECORDED", exc),
            "formal_dir_identity": _basis(boundary, state)["directory_identity"],
            "no_backfill": True, "phase": "DIRECTORY_CREATED_MARKER_UNRECORDED", "retry_eligible": False,
            "schema_version": MARKERLESS_SCHEMA, "status": "CONSUMED_INCOMPLETE",
        }
        identity = store.publish(
            boundary.formal_dir / "markerless-consumed-incomplete.json", markerless, "markerless consumed incomplete"
        )
        raise CloseoutStateError(f"formal directory is markerless and permanently consumed: {identity}") from exc
    return state.marker_identity


def publish_consumed_incomplete(
    boundary: Any,
    state: AttemptState,
    store: Any,
    *,
    phase: str,
    failure_record: Mapping[str, str],
    joins: Mapping[str, object],
    effects: Mapping[str, object],
) -> dict[str, object]:
    """Publish the one phase-appropriate incomplete receipt without future joins."""

    if state.incomplete_identity is not None:
        raise CloseoutStateError("consumed-incomplete receipt cannot be repeated")
    reject_none(dict(joins), "incomplete joins")
    state.irreversible_incomplete = True
    record = {**_base(boundary), "attempt_basis": _basis(boundary, state), "consumed": True,
              "effects": dict(effects), "failure": dict(failure_record), "formal_dir": str(boundary.formal_dir),
              "joins": dict(joins), "phase": phase, "retry_eligible": False,
              "schema_version": INCOMPLETE_SCHEMA, "status": "CONSUMED_INCOMPLETE"}
    path = boundary.formal_dir / f"incomplete-{phase.lower().replace('_', '-')}.json"
    state.incomplete_identity = store.publish(path, record, f"{phase} incomplete")
    return {"identity": state.incomplete_identity, "record": record}


def _reference_record(boundary: Any, status: str, unit_name: str, **fields: object) -> dict[str, object]:
    return {**_base(boundary), "schema_version": REFERENCE_SCHEMA, "status": status,
            "unit_name": unit_name, **fields}


def acquire_reference_once(
    boundary: Any, state: AttemptState, store: Any, reference: Any, *, unit_name: str,
    selection_identity: Mapping[str, Any], resource_identity: Mapping[str, Any],
    lock_evidence: Sequence[Mapping[str, Any]], manager_epoch_capture: Mapping[str, Any],
) -> dict[str, object]:
    if state.acquire_attempted or state.reference is not None:
        raise CloseoutStateError("RefUnit acquisition cannot be repeated")
    state.acquire_attempted, state.reference = True, reference
    owner = boundary.root["manager_epoch"]["dbus_unique_owner"]
    try:
        state.acquire_return = dict(reference.acquire(unit_name=unit_name, expected_manager_owner=owner))
        verification = reference.verify(expected_manager_owner=owner)
        if not _same_epoch(boundary, manager_epoch_capture["manager_epoch"]):
            raise CloseoutStateError("manager epoch drifted at RefUnit acquisition")
        record = _reference_record(
            boundary, "HELD", unit_name, acquire_call=state.acquire_return, connection_verification=verification,
            lock_evidence=list(lock_evidence),
            manager_epoch_capture=dict(manager_epoch_capture), resource_identity=dict(resource_identity),
            selection_identity=dict(selection_identity),
        )
        state.acquire_identity = store.publish(
            boundary.formal_dir / "reference-acquisition.json", record, "reference acquisition"
        )
        return {"identity": state.acquire_identity, "kind": "RECORDED"}
    except Exception as exc:
        code = ("REF_ACQUIRE_RETURNED_BUT_UNRECORDED" if state.acquire_return is not None
                else "REF_ACQUIRE_FAILED_OR_UNCERTAIN")
        state.errors.append(failure(code, exc))
        return {"failure": state.errors[-1], "kind": code}


def finalize_reference_once(
    boundary: Any, state: AttemptState, store: Any, *, unit_name: str, prove_unref: bool, reason: str
) -> dict[str, object]:
    """Perform exactly one legal Unref/close or one uncertainty abort/drop."""

    reference = state.reference
    if reference is None:
        return {"kind": "NO_REFERENCE_OPENED"}
    owner = boundary.root["manager_epoch"]["dbus_unique_owner"]
    if prove_unref:
        if state.acquire_identity is None or state.release_attempted:
            raise CloseoutStateError("canonical Unref lacks one recorded acquisition")
        state.release_attempted = True
        try:
            state.release_return = dict(reference.release(unit_name=unit_name, expected_manager_owner=owner))
            call = _reference_record(
                boundary, "UNREF_RETURNED", unit_name, acquisition_identity=state.acquire_identity,
                call=state.release_return,
            )
            state.unref_call_identity = store.publish(
                boundary.formal_dir / "unref-call.json", call, "Unref call"
            )
        except Exception as exc:
            reason = ("UNREF_RETURNED_BUT_UNRECORDED" if state.release_return is not None
                      else "UNREF_FAILED_OR_UNCERTAIN")
            state.errors.append(failure(reason, exc))
            prove_unref = False
    if not prove_unref:
        if state.connection_action:
            raise CloseoutStateError("reference terminal action was repeated")
        state.connection_action = "abort_close"
        returned = False
        try:
            released = bool(reference.abort_close())
            returned = True
            record = _reference_record(
                boundary, "CONSUMED_INCOMPLETE", unit_name, abort_close_returned_released=released,
                connection_drop_attempts=1, explicit_unref_proven=False, reason=reason)
            identity = store.publish(
                boundary.formal_dir / "reference-abort-close.json", record, "reference abort close"
            )
            return {"identity": identity, "kind": "UNREF_UNPROVEN_CONNECTION_DROPPED"}
        except Exception as exc:
            code = ("CONNECTION_DROPPED_RECEIPT_UNRECORDED" if returned
                    else "CONNECTION_DROP_FAILED_OR_UNCERTAIN")
            state.errors.append(failure(code, exc))
            return {"failure": state.errors[-1], "kind": code}
    if state.connection_action:
        raise CloseoutStateError("reference terminal action was repeated")
    state.connection_action = "close"
    try:
        reference.close()
    except Exception as exc:
        state.errors.append(failure("CONNECTION_CLOSE_FAILED_OR_UNCERTAIN", exc))
        return {"failure": state.errors[-1], "kind": "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN"}
    release = _reference_record(
        boundary, "RELEASED", unit_name, acquisition_identity=state.acquire_identity,
        connection_close_returned=True, unref_call_identity=state.unref_call_identity)
    try:
        state.reference_release_identity = store.publish(
            boundary.formal_dir / "reference-release.json", release, "reference release"
        )
    except Exception as exc:
        state.errors.append(failure("CONNECTION_CLOSED_RELEASE_UNRECORDED", exc))
        return {"failure": state.errors[-1], "kind": "CONNECTION_CLOSED_RELEASE_UNRECORDED"}
    return {"identity": state.reference_release_identity, "kind": "RECORDED"}


class ContainmentHoldCoordinator:
    """Keep the supervisor and all locks alive until exact absence is observed."""

    def __init__(self, boundary: Any, state: AttemptState, store: Any, port: Any, *,
                 waiter: Any, latch: Any | None = None) -> None:
        self.boundary, self.state, self.store, self.port = boundary, state, store, port
        self.waiter, self.latch = waiter, latch

    def _publish_hold(
        self, *, ledger: Mapping[str, object], failure_record: Mapping[str, str],
        reference_terminal: Mapping[str, object],
    ) -> dict[str, object]:
        record = {
            **_base(self.boundary), "attempt_incomplete_identity": self.state.incomplete_identity,
            "errors": list(self.state.errors), "experiment_progress_active": False,
            "failure": dict(failure_record), "frozen_ledger": dict(ledger), "isolation_active": True,
            "lock_identities": self.port.lock_evidence(), "outcome": "INCOMPLETE",
            "poll_interval_seconds": HOLD_POLL_SECONDS, "reference_terminal": dict(reference_terminal),
            "schema_version": HOLD_SCHEMA, "status": "CONTAINMENT_HOLD", "success_eligible": False,
            "supervisor": {
                "pid": os.getpid(),
                "starttime": self.boundary.context["campaign_module"]._read_proc_starttime(os.getpid()),  # noqa: SLF001
            },
        }
        self.state.hold_identity = self.store.publish(
            self.boundary.formal_dir / "containment-hold.json", record, "containment hold"
        )
        return {"identity": self.state.hold_identity, "record": record}

    def _announce_gap(self, code: str, error: BaseException | str) -> None:
        item = failure(code, error)
        self.state.errors.append(item)
        self.waiter.announce({"failure": item, "isolation_active": True,
                              "status": "CONTAINMENT_HOLD_EVIDENCE_GAP"})

    def enter(
        self, *, unit_name: str, failure_record: Mapping[str, str],
        ledger: Mapping[str, object], reference_reason: str,
    ) -> dict[str, object]:
        """Block through residual runtime, then release once and stay incomplete."""

        self.state.irreversible_incomplete = True
        reference_terminal = finalize_reference_once(
            self.boundary, self.state, self.store, unit_name=unit_name,
            prove_unref=self.state.acquire_identity is not None, reason=reference_reason)
        try:
            incomplete = publish_consumed_incomplete(
                self.boundary, self.state, self.store, phase="CONTAINMENT_HOLD",
                failure_record=failure_record,
                joins={"child_audit_identity": ledger["child_audit_identity"]},
                effects={"reference_terminal": reference_terminal})
            hold = self._publish_hold(
                ledger=ledger, failure_record=failure_record, reference_terminal=reference_terminal)
        except Exception as exc:
            self._announce_gap("CONTAINMENT_HOLD_PUBLICATION_FAILED", exc)
            incomplete, hold = {}, {}
        signaled = False
        while True:
            self.state.hold_poll_count += 1
            if self.latch and self.latch.records and not signaled:
                try:
                    record = {**_base(self.boundary), "containment_hold_identity": self.state.hold_identity,
                              "schema_version": HOLD_SCHEMA, "signals": list(self.latch.records),
                              "status": "CONTAINMENT_HOLD"}
                    self.store.publish(self.boundary.formal_dir / "containment-hold-signal.json",
                                       record, "containment hold signal")
                    signaled = True
                except Exception as exc:
                    self._announce_gap("HOLD_SIGNAL_PUBLICATION_FAILED", exc)
            try:
                locks = self.port.lock_evidence()
                observation = dict(self.port.observe_frozen_absence(ledger))
            except Exception as exc:
                self._announce_gap("CONTAINMENT_OBSERVATION_FAILED", exc)
                self.waiter.wait(HOLD_POLL_SECONDS)
                continue
            if observation.get("all_absent") is not True:
                self.waiter.announce({"isolation_active": True, "poll": self.state.hold_poll_count,
                                      "status": "CONTAINMENT_HOLD"})
                self.waiter.wait(HOLD_POLL_SECONDS)
                continue
            if not incomplete or not hold:
                self._announce_gap("CONTAINMENT_HOLD_EVIDENCE_GAP",
                                   "absence observed but prerequisite receipts are missing")
                self.waiter.wait(HOLD_POLL_SECONDS)
                continue
            try:
                clearance = {
                    **_base(self.boundary), "containment_hold_identity": self.state.hold_identity,
                    "final_observation": observation, "lock_identities": locks, "outcome": "INCOMPLETE",
                    "schema_version": HOLD_CLEAR_SCHEMA, "status": "CONTAINMENT_CLEARED_AFTER_HOLD",
                    "success_eligible": False}
                self.state.hold_clearance_identity = self.store.publish(
                    self.boundary.formal_dir / "containment-cleared-after-hold.json",
                    clearance,
                    "containment cleared after hold",
                )
            except Exception as exc:
                self._announce_gap("CONTAINMENT_CLEARANCE_PUBLICATION_FAILED", exc)
                self.waiter.wait(HOLD_POLL_SECONDS)
                continue
            break
        self.state.lock_release_attempted = True
        try:
            self.state.lock_release_return = dict(self.port.release_locks_once())
            release = {
                **_base(self.boundary), "containment_clearance_identity": self.state.hold_clearance_identity,
                "effect": self.state.lock_release_return, "schema_version": LOCK_RELEASE_SCHEMA,
                "status": "RELEASED"}
            self.state.lock_release_identity = self.store.publish(
                self.boundary.formal_dir / "lock-release.json", release, "formal lock release"
            )
        except Exception as exc:
            self.state.errors.append(failure("LOCK_RELEASE_FAILED_OR_UNRECORDED", exc))
            return {"errors": list(self.state.errors), "outcome": "INCOMPLETE",
                    "status": "CONSUMED_INCOMPLETE"}
        detached = {
            **_base(self.boundary), "containment_clearance_identity": self.state.hold_clearance_identity,
            "lock_release_identity": self.state.lock_release_identity,
            "original_incomplete_identity": self.state.incomplete_identity, "outcome": "INCOMPLETE",
            "schema_version": DETACHED_INCOMPLETE_SCHEMA, "status": "CONSUMED_INCOMPLETE",
            "success_eligible": False,
        }
        try:
            detached_identity = self.store.publish(
                self.boundary.formal_dir / "detached-incomplete.json", detached, "detached incomplete")
        except Exception as exc:
            self.state.errors.append(failure("DETACHED_INCOMPLETE_UNRECORDED", exc))
            detached_identity = {}
        return {"detached_identity": detached_identity, "errors": list(self.state.errors),
                "outcome": "INCOMPLETE", "status": "CONSUMED_INCOMPLETE"}
