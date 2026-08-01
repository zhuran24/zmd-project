#!/usr/bin/env python3
"""Research-only owner/supervisor coordinator for one formal AB16 attempt.

The coordinator owns no launch decision.  It keeps one externally identified
formal-launch owner alive across admission and selection, starts the
package-selected supervisor only after admission, and does not request
selection until the supervisor-published guardian-ready and attempt-consumption
records have been independently replayed.  The selected supervisor remains the
sole owner of the three formal locks and every unit lifecycle.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import stat
import sys
import threading
import time
from types import ModuleType
from typing import Any, cast

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_campaign_bootstrap_v2 as bootstrap,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_budget_broker_v1 as budget_broker,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_campaign_v1 as formal_campaign,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_launch_validator_v1 as launch_validator,
)


AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
LEGACY_REQUEST_SCHEMA = "noncert-cuts-ab16-formal-launch-owner-request-v1"
LEGACY_RESPONSE_SCHEMA = "noncert-cuts-ab16-formal-launch-owner-response-v1"
REQUEST_SCHEMA = "noncert-cuts-ab16-formal-launch-owner-request-v2"
RESPONSE_SCHEMA = "noncert-cuts-ab16-formal-launch-owner-response-v2"
FORMAL_SUPERVISOR_SESSION_SCHEMA = (
    "noncert-cuts-ab16-formal-supervisor-session-v1"
)
SESSION_ID = "formal-owner-session-a001"
PREREQUISITE_WAIT_SECONDS = 600.0
SUPERVISOR_WAIT_SECONDS = 64_800.0
POLL_SECONDS = 0.10
MAX_FRAME = 16 * 1024 * 1024
F_ADD_SEALS = 1033
F_GET_SEALS = 1034
REQUIRED_SEALS = 0x0001 | 0x0002 | 0x0004 | 0x0008
MFD_CLOEXEC = 0x0001
MFD_ALLOW_SEALING = 0x0002
CLEAN_ENV = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}


class FormalOrchestrationError(RuntimeError):
    """The external owner/supervisor join failed closed."""


def _formal_campaign_module() -> ModuleType:
    """Return the package-pinned supervisor bound during retained-FD load."""

    return formal_campaign


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message_identity(raw: bytes) -> dict[str, object]:
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _canonical_argument(value: Mapping[str, object]) -> str:
    return json.dumps(
        dict(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _process_starttime(pid: int) -> int:
    raw = Path(f"/proc/{pid}/stat").read_bytes()
    marker = raw.rfind(b") ")
    fields = raw[marker + 2 :].split() if marker >= 0 else []
    if len(fields) <= 19:
        raise FormalOrchestrationError("formal owner process identity is unreadable")
    return int(fields[19])


def _sealed_memfd(name: str, raw: bytes) -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    create = libc.memfd_create
    create.argtypes = (ctypes.c_char_p, ctypes.c_uint)
    create.restype = ctypes.c_int
    descriptor = int(
        create(
            os.fsencode(name),
            MFD_CLOEXEC | MFD_ALLOW_SEALING,
        )
    )
    if descriptor < 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short memfd write")
            view = view[written:]
        os.lseek(descriptor, 0, os.SEEK_SET)
        fcntl.fcntl(descriptor, F_ADD_SEALS, REQUIRED_SEALS)
        if fcntl.fcntl(descriptor, F_GET_SEALS) & REQUIRED_SEALS != REQUIRED_SEALS:
            raise OSError("memfd seal set drifted")
        return descriptor
    except BaseException as exc:
        try:
            os.close(descriptor)
        except BaseException as cleanup_exc:
            exc.add_note(
                "sealed memfd cleanup close failed: "
                f"{type(cleanup_exc).__name__}: {cleanup_exc}"
            )
        raise


def _read_frame(control: socket.socket, label: str) -> dict[str, Any]:
    raw = control.recv(MAX_FRAME + 1)
    if not raw or len(raw) > MAX_FRAME:
        raise FormalOrchestrationError(f"{label} frame is absent or oversized")
    try:
        value = authority.strict_loads(raw, label)
    except Exception as exc:
        raise FormalOrchestrationError(f"{label} frame is invalid: {exc}") from exc
    if type(value) is not dict or authority.canonical_json(value) != raw:
        raise FormalOrchestrationError(f"{label} frame is not one canonical object")
    return value


def _send_frame(control: socket.socket, value: Mapping[str, object]) -> None:
    raw = authority.canonical_json(dict(value))
    if control.send(raw) != len(raw):
        raise FormalOrchestrationError("formal owner request send was short")


@dataclass
class OwnerSession:
    """One persistent formal-launch owner process and its control channel."""

    pid: int
    control: socket.socket
    stderr_descriptor: int
    actor: dict[str, object]
    reaped: bool = False
    control_owned: bool = True

    def _close_control_once(self) -> BaseException | None:
        if not self.control_owned:
            return None
        self.control_owned = False
        try:
            self.control.close()
        except BaseException as exc:
            return exc
        return None

    def _close_stderr_once(self) -> BaseException | None:
        if self.stderr_descriptor < 0:
            return None
        descriptor = self.stderr_descriptor
        self.stderr_descriptor = -1
        try:
            os.close(descriptor)
        except BaseException as exc:
            return exc
        return None

    def _cleanup_reap(self) -> list[BaseException]:
        errors: list[BaseException] = []
        if self.reaped:
            return errors
        try:
            os.kill(self.pid, 9)
        except ProcessLookupError:
            pass
        except BaseException as exc:
            errors.append(exc)
        while not self.reaped:
            try:
                observed, _status = os.waitpid(self.pid, 0)
                if observed == self.pid:
                    self.reaped = True
                else:
                    errors.append(
                        FormalOrchestrationError(
                            "formal owner cleanup wait returned pid "
                            f"{observed}, expected {self.pid}"
                        )
                    )
                    break
            except InterruptedError:
                continue
            except ChildProcessError:
                self.reaped = True
            except BaseException as exc:
                errors.append(exc)
                break
        return errors

    def request(
        self,
        *,
        sequence: int,
        kind: str,
        draft: Mapping[str, object],
        expected_status: str = "PUBLISHED",
    ) -> dict[str, Any]:
        if self.reaped or _process_starttime(self.pid) != self.actor["starttime"]:
            raise FormalOrchestrationError("formal owner actor is no longer live")
        _send_frame(
            self.control,
            {
                "draft": dict(draft),
                "kind": kind,
                "schema_version": REQUEST_SCHEMA,
                "sequence": sequence,
            },
        )
        response = _read_frame(self.control, f"formal owner {kind}")
        if (
            set(response)
            != {
                "actor",
                "artifact_identity",
                "kind",
                "schema_version",
                "sequence",
                "status",
            }
            or response["schema_version"] != RESPONSE_SCHEMA
            or response["status"] != expected_status
            or response["sequence"] != sequence
            or response["kind"] != kind
            or response["actor"] != self.actor
        ):
            raise FormalOrchestrationError(
                f"formal owner {kind} response drifted"
            )
        return response

    def prepare_selection(
        self,
        draft: Mapping[str, object],
    ) -> dict[str, Any]:
        """Render and validate once without creating the selection path."""

        return self.request(
            sequence=2,
            kind="selection",
            draft=draft,
            expected_status="PREPARED",
        )

    def commit_prepared_selection(
        self,
        *,
        prepared_selection_identity: Mapping[str, object],
        preregistration_receipt_identity: Mapping[str, object],
        broker_binding_receipt_identity: Mapping[str, object],
    ) -> dict[str, Any]:
        """Publish only the exact bytes returned by PREPARE."""

        if self.reaped or _process_starttime(self.pid) != self.actor["starttime"]:
            raise FormalOrchestrationError(
                "formal owner died before selection commit"
            )
        _send_frame(
            self.control,
            {
                "broker_binding_receipt_identity": dict(
                    broker_binding_receipt_identity
                ),
                "kind": "selection-commit",
                "prepared_selection_identity": dict(
                    prepared_selection_identity
                ),
                "preregistration_receipt_identity": dict(
                    preregistration_receipt_identity
                ),
                "schema_version": REQUEST_SCHEMA,
                "sequence": 3,
            },
        )
        response = _read_frame(
            self.control,
            "formal owner selection commit",
        )
        if (
            set(response)
            != {
                "actor",
                "artifact_identity",
                "broker_binding_receipt_identity",
                "kind",
                "preregistration_receipt_identity",
                "schema_version",
                "sequence",
                "status",
            }
            or response["schema_version"] != RESPONSE_SCHEMA
            or response["status"] != "PUBLISHED"
            or response["sequence"] != 3
            or response["kind"] != "selection-commit"
            or response["actor"] != self.actor
            or response["artifact_identity"]
            != dict(prepared_selection_identity)
            or response["preregistration_receipt_identity"]
            != dict(preregistration_receipt_identity)
            or response["broker_binding_receipt_identity"]
            != dict(broker_binding_receipt_identity)
        ):
            raise FormalOrchestrationError(
                "formal owner selection COMMIT response drifted"
            )
        return response

    def complete_handoff(self) -> None:
        waited = -1
        status = -1
        stderr = b""
        failure: BaseException | None = None
        try:
            if (
                self.reaped
                or not self.control_owned
                or _process_starttime(self.pid) != self.actor["starttime"]
            ):
                raise FormalOrchestrationError(
                    "formal owner died before selection handoff"
                )
            _send_frame(
                self.control,
                {
                    "kind": "handoff-complete",
                    "schema_version": REQUEST_SCHEMA,
                    "sequence": 4,
                },
            )
            response = _read_frame(self.control, "formal owner handoff")
            if response != {
                "actor": self.actor,
                "schema_version": RESPONSE_SCHEMA,
                "sequence": 4,
                "status": "HANDOFF_COMPLETE",
            }:
                raise FormalOrchestrationError(
                    "formal owner handoff response drifted"
                )
            control_error = self._close_control_once()
            if control_error is not None:
                raise control_error
            while True:
                try:
                    waited, status = os.waitpid(self.pid, 0)
                    self.reaped = waited == self.pid
                    break
                except InterruptedError:
                    continue
            if not self.reaped:
                raise FormalOrchestrationError(
                    "formal owner handoff wait returned a different child"
                )
            stderr = os.read(self.stderr_descriptor, MAX_FRAME + 1)
            if os.waitstatus_to_exitcode(status) != 0 or stderr:
                raise FormalOrchestrationError(
                    "formal owner handoff exit drifted: "
                    f"status={status}, stderr={stderr!r}"
                )
        except BaseException as exc:
            failure = exc
            raise
        finally:
            cleanup_errors: list[BaseException] = []
            control_error = self._close_control_once()
            if control_error is not None:
                cleanup_errors.append(control_error)
            cleanup_errors.extend(self._cleanup_reap())
            stderr_error = self._close_stderr_once()
            if stderr_error is not None:
                cleanup_errors.append(stderr_error)
            if failure is not None:
                for cleanup_error in cleanup_errors:
                    failure.add_note(
                        "formal owner handoff cleanup failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            elif cleanup_errors:
                raise FormalOrchestrationError(
                    "formal owner handoff cleanup failed: "
                    f"{type(cleanup_errors[0]).__name__}: "
                    f"{cleanup_errors[0]}"
                ) from cleanup_errors[0]

    def close(self) -> None:
        errors: list[BaseException] = []
        control_error = self._close_control_once()
        if control_error is not None:
            errors.append(control_error)
        errors.extend(self._cleanup_reap())
        stderr_error = self._close_stderr_once()
        if stderr_error is not None:
            errors.append(stderr_error)
        if errors:
            raise FormalOrchestrationError(
                f"formal owner cleanup failed: {type(errors[0]).__name__}: "
                f"{errors[0]}"
            ) from errors[0]


@dataclass
class DelayedFormalLaunchOwnerProcess:
    """Package-loaded actor blocked until the broker registers its grant."""

    pid: int
    pidfd: int
    pidfd_method: str
    control: socket.socket | None
    release_descriptor: int
    actor: dict[str, object]
    released: bool = False
    control_transferred: bool = False

    def _control(self) -> socket.socket:
        if self.control is None:
            raise FormalOrchestrationError(
                "delayed formal owner control was already transferred"
            )
        return self.control

    def release_and_wait_ready(
        self,
        *,
        expected_grant: Mapping[str, object],
    ) -> dict[str, object]:
        if self.released:
            raise FormalOrchestrationError(
                "delayed formal owner cannot be released twice"
            )
        self.released = True
        descriptor = self.release_descriptor
        self.release_descriptor = -1
        try:
            if os.write(descriptor, b"1") != 1:
                raise FormalOrchestrationError(
                    "delayed formal owner release was short"
                )
        finally:
            os.close(descriptor)
        ready = _read_frame(
            self._control(),
            "delayed formal owner ready",
        )
        if (
            ready.get("schema_version") == RESPONSE_SCHEMA
            and ready.get("status") == "FAIL_CLOSED"
            and isinstance(ready.get("error"), str)
        ):
            raise FormalOrchestrationError(
                "delayed formal owner failed before READY: "
                f"{ready['error']}"
            )
        if (
            ready
            != {
                "actor": self.actor,
                "broker_grant": dict(expected_grant),
                "schema_version": RESPONSE_SCHEMA,
                "status": "BROKER_SESSION_RETAINED",
            }
        ):
            raise FormalOrchestrationError(
                "delayed formal owner READY drifted"
            )
        return dict(ready)

    def deliver_context(
        self,
        context: Mapping[str, object],
    ) -> dict[str, object]:
        if not self.released:
            raise FormalOrchestrationError(
                "delayed formal owner lacks its broker session"
            )
        raw = authority.canonical_json(dict(context))
        identity = _message_identity(raw)
        _send_frame(
            self._control(),
            {
                "context": dict(context),
                "context_identity": identity,
                "kind": "delayed-context",
                "schema_version": REQUEST_SCHEMA,
                "sequence": 1,
            },
        )
        response = _read_frame(
            self._control(),
            "delayed formal owner context acknowledgement",
        )
        if (
            response
            != {
                "actor": self.actor,
                "context_identity": identity,
                "schema_version": RESPONSE_SCHEMA,
                "sequence": 1,
                "status": "CONTEXT_RETAINED",
            }
        ):
            raise FormalOrchestrationError(
                "delayed formal owner context acknowledgement drifted"
            )
        return dict(response)

    def detach_control_descriptor(self) -> int:
        if (
            not self.released
            or self.control_transferred
            or self.control is None
        ):
            raise FormalOrchestrationError(
                "delayed formal owner control cannot be transferred"
            )
        self.control_transferred = True
        control = self.control
        self.control = None
        return control.detach()

    def close(self) -> None:
        primary: BaseException | None = None
        if self.release_descriptor >= 0:
            try:
                os.close(self.release_descriptor)
            except BaseException as exc:
                primary = exc
            self.release_descriptor = -1
        control = self.control
        self.control = None
        if control is not None:
            try:
                control.close()
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        f"delayed owner control close also failed: {exc}"
                    )
        try:
            while True:
                try:
                    observed, _status = os.waitpid(self.pid, 0)
                    if observed != self.pid:
                        raise FormalOrchestrationError(
                            "delayed owner wait returned a different PID"
                        )
                    break
                except InterruptedError:
                    continue
        except ChildProcessError:
            pass
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    f"delayed owner wait also failed: {exc}"
                )
        try:
            os.close(self.pidfd)
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    f"delayed owner pidfd close also failed: {exc}"
                )
        self.pidfd = -1
        if primary is not None:
            raise primary


@dataclass
class ClaimedOwnerSession:
    """One broker-relayed control FD for the already-running package actor."""

    owner: OwnerSession
    broker_client: Any
    claim_identity: dict[str, object]
    handoff_complete: bool = False

    @property
    def actor(self) -> dict[str, object]:
        return self.owner.actor

    @property
    def pid(self) -> int:
        return self.owner.pid

    @property
    def reaped(self) -> bool:
        return self.owner.reaped

    def deliver_context(
        self,
        context: Mapping[str, object],
    ) -> dict[str, object]:
        raw = authority.canonical_json(dict(context))
        identity = _message_identity(raw)
        _send_frame(
            self.owner.control,
            {
                "context": dict(context),
                "context_identity": identity,
                "kind": "delayed-context",
                "schema_version": REQUEST_SCHEMA,
                "sequence": 1,
            },
        )
        response = _read_frame(
            self.owner.control,
            "claimed formal owner context acknowledgement",
        )
        if response != {
            "actor": self.actor,
            "context_identity": identity,
            "schema_version": RESPONSE_SCHEMA,
            "sequence": 1,
            "status": "CONTEXT_RETAINED",
        }:
            raise FormalOrchestrationError(
                "claimed formal owner context acknowledgement drifted"
            )
        return dict(response)

    def request(self, **kwargs: object) -> dict[str, Any]:
        return self.owner.request(**kwargs)

    def register_formal_supervisor(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> dict[str, object]:
        expected_peer = payload.get("expected_peer")
        package_id = payload.get("package_id")
        if (
            type(expected_peer) is not dict
            or type(package_id) is not str
            or len(package_id) != 64
        ):
            raise FormalOrchestrationError(
                "formal supervisor registration payload drifted"
            )
        _send_frame(
            self.owner.control,
            {
                "expected_peer": dict(expected_peer),
                "kind": "supervisor-register",
                "package_id": package_id,
                "schema_version": REQUEST_SCHEMA,
                "sequence": 2,
            },
        )
        self.broker_client.native_helper.send_fd(
            self.owner.control.fileno(),
            pidfd,
        )
        response = _read_frame(
            self.owner.control,
            "claimed formal owner supervisor registration",
        )
        session = response.get("session")
        if (
            set(response)
            != {
                "actor",
                "schema_version",
                "sequence",
                "session",
                "status",
            }
            or response["actor"] != self.actor
            or response["schema_version"] != RESPONSE_SCHEMA
            or response["sequence"] != 2
            or response["status"] != "SUPERVISOR_REGISTERED"
            or type(session) is not dict
            or session.get("schema_version")
            != FORMAL_SUPERVISOR_SESSION_SCHEMA
            or session.get("expected_peer") != expected_peer
            or session.get("package_id") != package_id
            or session.get("owner_actor") != self.actor
        ):
            raise FormalOrchestrationError(
                "claimed formal owner supervisor registration drifted"
            )
        return dict(session)

    def prepare_selection(
        self,
        draft: Mapping[str, object],
    ) -> dict[str, Any]:
        return self.owner.prepare_selection(draft)

    def commit_prepared_selection(
        self,
        **kwargs: object,
    ) -> dict[str, Any]:
        return self.owner.commit_prepared_selection(**kwargs)

    def prepare_bound_selection(
        self,
        *,
        admission: Mapping[str, object],
        admission_identity: Mapping[str, object],
        guardian_ready: Mapping[str, object],
        guardian_ready_identity: Mapping[str, object],
        attempt_consumption: Mapping[str, object],
        attempt_consumption_identity: Mapping[str, object],
    ) -> dict[str, Any]:
        _send_frame(
            self.owner.control,
            {
                "admission": dict(admission),
                "admission_identity": dict(admission_identity),
                "attempt_consumption": dict(attempt_consumption),
                "attempt_consumption_identity": dict(
                    attempt_consumption_identity
                ),
                "guardian_ready": dict(guardian_ready),
                "guardian_ready_identity": dict(
                    guardian_ready_identity
                ),
                "kind": "selection-prepare",
                "schema_version": REQUEST_SCHEMA,
                "sequence": 3,
            },
        )
        response = _read_frame(
            self.owner.control,
            "claimed formal owner selection PREPARE",
        )
        if (
            response.get("status") == "FAIL_CLOSED"
            and type(response.get("error")) is str
        ):
            raise FormalOrchestrationError(
                "claimed formal owner selection PREPARE failed closed: "
                f"{response['error']}"
            )
        if (
            set(response)
            != {
                "actor",
                "artifact_identity",
                "kind",
                "manager_openfile_grant",
                "preregistration_receipt_identity",
                "schema_version",
                "sequence",
                "status",
            }
            or response["actor"] != self.actor
            or response["kind"] != "selection-prepare"
            or response["schema_version"] != RESPONSE_SCHEMA
            or response["sequence"] != 3
            or response["status"] != "PREPARED"
        ):
            raise FormalOrchestrationError(
                "claimed formal owner selection PREPARE drifted"
            )
        return response

    def commit_bound_selection(
        self,
        *,
        prepared_selection_identity: Mapping[str, object],
    ) -> dict[str, Any]:
        _send_frame(
            self.owner.control,
            {
                "kind": "selection-commit",
                "prepared_selection_identity": dict(
                    prepared_selection_identity
                ),
                "schema_version": REQUEST_SCHEMA,
                "sequence": 4,
            },
        )
        response = _read_frame(
            self.owner.control,
            "claimed formal owner selection COMMIT",
        )
        if (
            response.get("status") == "FAIL_CLOSED"
            and type(response.get("error")) is str
        ):
            raise FormalOrchestrationError(
                "claimed formal owner selection COMMIT failed closed: "
                f"{response['error']}"
            )
        if (
            set(response)
            != {
                "actor",
                "artifact_identity",
                "broker_binding_receipt_identity",
                "kind",
                "preregistration_receipt_identity",
                "schema_version",
                "sequence",
                "status",
            }
            or response["actor"] != self.actor
            or response["kind"] != "selection-commit"
            or response["schema_version"] != RESPONSE_SCHEMA
            or response["sequence"] != 4
            or response["status"] != "PUBLISHED"
        ):
            raise FormalOrchestrationError(
                "claimed formal owner selection COMMIT drifted"
            )
        return response

    def complete_handoff(self) -> None:
        _send_frame(
            self.owner.control,
            {
                "kind": "handoff-complete",
                "schema_version": REQUEST_SCHEMA,
                "sequence": 5,
            },
        )
        response = _read_frame(
            self.owner.control,
            "claimed formal owner handoff",
        )
        if response != {
            "actor": self.actor,
            "schema_version": RESPONSE_SCHEMA,
            "sequence": 5,
            "status": "HANDOFF_COMPLETE",
        }:
            raise FormalOrchestrationError(
                "claimed formal owner handoff response drifted"
            )
        self.handoff_complete = True

    def close(self) -> None:
        primary: BaseException | None = None
        control_error = self.owner._close_control_once()  # noqa: SLF001
        if control_error is not None:
            primary = control_error
        try:
            if self.handoff_complete:
                self.broker_client.close_session()
            else:
                self.broker_client.close()
        except BaseException as exc:
            if not self.broker_client.closed:
                try:
                    self.broker_client.close()
                except BaseException as cleanup_error:
                    exc.add_note(
                        "claim broker raw close also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "claim broker session close also failed: "
                    f"{type(exc).__name__}: {exc}"
                )
        if primary is not None:
            raise primary


@dataclass
class FormalLaunchClaimTransport:
    """Explicit single-use capability for claiming the delayed package actor."""

    broker_module: Any
    broker_parent_descriptor: int
    broker_endpoint_name: str
    broker_actor: Mapping[str, object]
    broker_nonce: str
    claim_descriptor: int
    claim_identity: Mapping[str, object]
    native_helper: Any
    consumed: bool = False

    def claim(
        self,
        _context: Mapping[str, object] | None = None,
    ) -> ClaimedOwnerSession:
        if self.consumed:
            raise FormalOrchestrationError(
                "formal-launch claim transport was already consumed"
            )
        # Consumption linearizes before the broker request.  Any transport,
        # reply, or ACK uncertainty is non-retriable.
        self.consumed = True
        return claim_delayed_formal_launch_owner(
            broker_module=self.broker_module,
            broker_parent_descriptor=self.broker_parent_descriptor,
            broker_endpoint_name=self.broker_endpoint_name,
            broker_actor=self.broker_actor,
            broker_nonce=self.broker_nonce,
            claim_descriptor=self.claim_descriptor,
            claim_identity=self.claim_identity,
            native_helper=self.native_helper,
        )


@dataclass
class ConnectedFormalLaunchClaimTransport:
    """Single-use FD8/FD9 transport supplied by the selected loader."""

    broker_module: Any
    broker_descriptor: int
    claim_descriptor: int
    claim_identity: Mapping[str, object]
    native_helper: Any
    consumed: bool = False

    def claim(
        self,
        context: Mapping[str, object] | None = None,
    ) -> ClaimedOwnerSession:
        if self.consumed:
            raise FormalOrchestrationError(
                "connected formal-launch claim was already consumed"
            )
        if context is None:
            raise FormalOrchestrationError(
                "connected formal-launch claim lacks validated context"
            )
        runtime = cast(
            Mapping[str, object],
            context["formal_budget_runtime"],
        )
        actor = cast(
            Mapping[str, object],
            runtime["broker_actor_identity"],
        )
        self.consumed = True
        return claim_delayed_formal_launch_owner_from_descriptor(
            broker_module=self.broker_module,
            broker_descriptor=self.broker_descriptor,
            broker_actor={
                "schema_version": self.broker_module.ACTOR_SCHEMA,
                **dict(actor),
            },
            broker_nonce=cast(str, runtime["broker_nonce"]),
            claim_descriptor=self.claim_descriptor,
            claim_identity=self.claim_identity,
            native_helper=self.native_helper,
        )


def formal_launch_claim_transport_from_fds(
    *,
    broker_descriptor: int,
    claim_descriptor: int,
    claim_identity: Mapping[str, object],
    native_helper: Any,
) -> ConnectedFormalLaunchClaimTransport:
    """Adopt only the selected loader's fixed FD8/FD9 capability pair."""

    if broker_descriptor != 8 or claim_descriptor != 9:
        raise FormalOrchestrationError(
            "selected formal-launch claim FD assignment drifted"
        )
    # The retained-FD loader binds this exact broker before executing the
    # orchestrator.  Never consult an ambient alias after that transition.
    broker_module = budget_broker
    broker_origin = getattr(broker_module, "__file__", None)
    expected_broker = Path(__file__).resolve().with_name(
        "ab16_budget_broker_v1.py"
    )
    if (
        type(broker_origin) is not str
        or Path(broker_origin).resolve(strict=True) != expected_broker
    ):
        raise FormalOrchestrationError(
            "selected formal-launch broker escaped the materialized snapshot"
        )
    return ConnectedFormalLaunchClaimTransport(
        broker_module=broker_module,
        broker_descriptor=broker_descriptor,
        claim_descriptor=claim_descriptor,
        claim_identity=dict(claim_identity),
        native_helper=native_helper,
    )


def _claim_control_from_client(
    client: Any,
    *,
    claim_identity: Mapping[str, object],
) -> ClaimedOwnerSession:
    claimed, acknowledged = client.claim_formal_launch_owner_control()
    result = claimed.record.get("result")
    acknowledgement = acknowledged.record.get("result")
    if (
        type(result) is not dict
        or type(acknowledgement) is not dict
        or result.get("claim_identity") != dict(claim_identity)
        or acknowledgement
        != {
            "claim_identity": dict(claim_identity),
            "state": "CONTROL_FD_CLAIM_ACKNOWLEDGED",
        }
        or result.get("state")
        != "CONTROL_FD_TRANSFERRED_PENDING_ACK"
        or len(claimed.descriptors) != 1
        or type(result.get("owner_actor")) is not dict
    ):
        for received in claimed.descriptors:
            os.close(received)
        raise FormalOrchestrationError(
            "formal-launch owner claim response drifted"
        )
    control = socket.socket(fileno=claimed.descriptors[0])
    actor = dict(cast(Mapping[str, object], result["owner_actor"]))
    return ClaimedOwnerSession(
        owner=OwnerSession(
            pid=cast(int, actor["pid"]),
            control=control,
            stderr_descriptor=-1,
            actor=actor,
        ),
        broker_client=client,
        claim_identity=dict(claim_identity),
    )


def claim_delayed_formal_launch_owner_from_descriptor(
    *,
    broker_module: Any,
    broker_descriptor: int,
    broker_actor: Mapping[str, object],
    broker_nonce: str,
    claim_descriptor: int,
    claim_identity: Mapping[str, object],
    native_helper: Any,
) -> ClaimedOwnerSession:
    """Consume one already-connected selected-loader broker descriptor."""

    client: Any | None = None
    try:
        client = broker_module.attach_formal_launch_claim_session(
            broker_descriptor,
            broker_actor=broker_actor,
            broker_nonce=broker_nonce,
            claim_descriptor=claim_descriptor,
            claim_identity=claim_identity,
            native_helper=native_helper,
        )
        return _claim_control_from_client(
            client,
            claim_identity=claim_identity,
        )
    except BaseException:
        if client is not None:
            client.close()
        raise


def claim_delayed_formal_launch_owner(
    *,
    broker_module: Any,
    broker_parent_descriptor: int,
    broker_endpoint_name: str,
    broker_actor: Mapping[str, object],
    broker_nonce: str,
    claim_descriptor: int,
    claim_identity: Mapping[str, object],
    native_helper: Any,
) -> ClaimedOwnerSession:
    """Claim the sole retained actor control FD without a plaintext token."""

    connection = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    client: Any | None = None
    try:
        connection.connect(
            f"/proc/self/fd/{broker_parent_descriptor}/"
            f"{broker_endpoint_name}"
        )
        descriptor = connection.detach()
        client = broker_module.attach_formal_launch_claim_session(
            descriptor,
            broker_actor=broker_actor,
            broker_nonce=broker_nonce,
            claim_descriptor=claim_descriptor,
            claim_identity=claim_identity,
            native_helper=native_helper,
        )
        return _claim_control_from_client(
            client,
            claim_identity=claim_identity,
        )
    except BaseException:
        connection.close()
        if client is not None:
            client.close()
        raise


def spawn_delayed_formal_launch_owner(
    *,
    broker_module: Any,
    broker_parent_descriptor: int,
    broker_endpoint_name: str,
    broker_actor: Mapping[str, object],
    broker_nonce: str,
    credential: str,
    native_helper: Any,
    session_id: str,
) -> DelayedFormalLaunchOwnerProcess:
    """Fork the package-loaded owner before releasing its broker grant.

    This entrypoint performs no publication, unit start, or solver work.  The
    child first blocks on a one-byte release.  The broker registers its exact
    PID/starttime/uid and pidfd grant, then releases it to authenticate and
    retain the sole control session.
    """

    parent, child = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    pid = os.fork()
    if pid == 0:
        parent.close()
        os.close(release_write)
        code = 125
        client: Any | None = None
        broker_connection: socket.socket | None = None
        broker_descriptor = -1
        try:
            broker_module.close_unlisted_descriptors(
                {
                    0,
                    1,
                    2,
                    broker_parent_descriptor,
                    child.fileno(),
                    release_read,
                }
            )
            broker_connection = socket.socket(
                socket.AF_UNIX,
                socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
            )
            broker_connection.connect(
                f"/proc/self/fd/{broker_parent_descriptor}/"
                f"{broker_endpoint_name}"
            )
            os.close(broker_parent_descriptor)
            broker_parent_descriptor = -1
            broker_descriptor = broker_connection.detach()
            broker_connection = None
            if os.read(release_read, 1) != b"1":
                raise FormalOrchestrationError(
                    "delayed formal owner release is absent"
                )
            os.close(release_read)
            release_read = -1
            client = broker_module.attach_registered_nonarm_session(
                broker_descriptor,
                broker_actor=broker_actor,
                broker_nonce=broker_nonce,
                credential=credential,
                role="formal-launch-owner",
                native_helper=native_helper,
            )
            broker_descriptor = -1
            actor = {
                "pid": os.getpid(),
                "role": launch_validator.OWNER_PUBLISHER_ROLE,
                "session_id": session_id,
                "starttime": _process_starttime(os.getpid()),
            }
            _send_frame(
                child,
                {
                    "actor": actor,
                    "broker_grant": client.grant.as_record(),
                    "schema_version": RESPONSE_SCHEMA,
                    "status": "BROKER_SESSION_RETAINED",
                },
            )
            request = _read_frame(
                child,
                "delayed formal owner context",
            )
            if (
                set(request)
                != {
                    "context",
                    "context_identity",
                    "kind",
                    "schema_version",
                    "sequence",
                }
                or request["schema_version"] != REQUEST_SCHEMA
                or request["kind"] != "delayed-context"
                or request["sequence"] != 1
                or type(request["context"]) is not dict
                or request["context_identity"]
                != _message_identity(
                    authority.canonical_json(request["context"])
                )
            ):
                raise FormalOrchestrationError(
                    "delayed formal owner context frame drifted"
                )
            checked_context = launch_validator.validate_formal_context(
                request["context"]
            )
            # Retain the validated object in this actor.  Formal admission is
            # released only by the later explicit lifecycle command; bootstrap
            # context delivery itself performs no heavy or authority action.
            retained_context = dict(checked_context)
            if not retained_context:
                raise FormalOrchestrationError(
                    "delayed formal owner context is empty"
                )
            _send_frame(
                child,
                {
                    "actor": actor,
                    "context_identity": request["context_identity"],
                    "schema_version": RESPONSE_SCHEMA,
                    "sequence": 1,
                    "status": "CONTEXT_RETAINED",
                },
            )
            prepared_raw: bytes | None = None
            prepared_identity: dict[str, object] | None = None
            manager_credential: str | None = None
            preregistration_receipt: dict[str, object] | None = None
            supervisor_session_issued = False

            def publish_launch_artifact(
                *,
                label: str,
                raw: bytes,
                expected_path: str,
            ) -> dict[str, object]:
                specification = client.request(
                    "GET_FORMAL_LAUNCH_ARTIFACT_SPEC",
                    {"label": label},
                ).record["result"]
                if type(specification) is not dict:
                    raise FormalOrchestrationError(
                        "formal-launch artifact specification is absent"
                    )
                root = Path(
                    str(
                        cast(
                            Mapping[str, object],
                            retained_context["formal_budget_runtime"],
                        )["formal_root_contract_identity"]["path"]  # type: ignore[index]
                    )
                ).parent
                target = root / str(specification["relative_path"])
                if target != Path(expected_path):
                    raise FormalOrchestrationError(
                        "formal-launch artifact path differs from broker policy"
                    )
                source = native_helper.create_memfd(
                    "ab16-formal-launch-artifact"
                )
                try:
                    offset = 0
                    while offset < len(raw):
                        count = os.pwrite(source, raw[offset:], offset)
                        if count <= 0:
                            raise FormalOrchestrationError(
                                "formal-launch memfd write made no progress"
                            )
                        offset += count
                    os.fsync(source)
                    if (
                        native_helper.install_final_seals(source)
                        != native_helper.final_seal_mask
                        or native_helper.get_seals(source)
                        != native_helper.final_seal_mask
                        or native_helper.has_writable_mapping(source)
                    ):
                        raise FormalOrchestrationError(
                            "formal-launch memfd seal verification failed"
                        )
                    publication = client.publish_descriptor(
                        {
                            "arm_slot": None,
                            "artifact_class": specification[
                                "artifact_class"
                            ],
                            "channel": None,
                            "expected_sha256": hashlib.sha256(
                                raw
                            ).hexdigest(),
                            "label": label,
                            "maximum_bytes": specification[
                                "maximum_bytes"
                            ],
                            "relative_path": specification[
                                "relative_path"
                            ],
                            "sequence": None,
                            "size_bytes": len(raw),
                        },
                        descriptor=source,
                    ).record["result"]
                finally:
                    os.close(source)
                if (
                    type(publication) is not dict
                    or publication.get("sha256")
                    != hashlib.sha256(raw).hexdigest()
                    or publication.get("size_bytes") != len(raw)
                ):
                    raise FormalOrchestrationError(
                        "formal-launch broker publication drifted"
                    )
                return {
                    "path": str(target),
                    "sha256": publication["sha256"],
                    "size_bytes": publication["size_bytes"],
                }

            while True:
                command = _read_frame(
                    child,
                    "delayed formal owner lifecycle command",
                )
                kind = command.get("kind")
                sequence = command.get("sequence")
                if (
                    kind == "admission"
                    and sequence == 1
                    and set(command)
                    == {"draft", "kind", "schema_version", "sequence"}
                ):
                    admission = launch_validator.validate_admission(
                        command["draft"],
                        expected_context=retained_context,
                    )
                    admission_raw = authority.canonical_json(admission)
                    identity = publish_launch_artifact(
                        label="formal launch admission",
                        raw=admission_raw,
                        expected_path=str(
                            retained_context["formal_admission_path"]
                        ),
                    )
                    _send_frame(
                        child,
                        {
                            "actor": actor,
                            "artifact_identity": identity,
                            "kind": "admission",
                            "schema_version": RESPONSE_SCHEMA,
                            "sequence": 1,
                            "status": "PUBLISHED",
                        },
                    )
                    continue
                if (
                    kind == "supervisor-register"
                    and sequence == 2
                    and set(command)
                    == {
                        "expected_peer",
                        "kind",
                        "package_id",
                        "schema_version",
                        "sequence",
                    }
                    and not supervisor_session_issued
                ):
                    expected_peer = command["expected_peer"]
                    package_id = command["package_id"]
                    if (
                        type(expected_peer) is not dict
                        or package_id != retained_context["package_id"]
                    ):
                        raise FormalOrchestrationError(
                            "formal supervisor registration binding drifted"
                        )
                    pidfd = native_helper.recv_fd(child.fileno())
                    try:
                        credential = secrets.token_hex(32)
                        response = client.register_bound_nonarm_grant(
                            {
                                "credential": credential,
                                "expected_peer": dict(expected_peer),
                                "role": "formal-supervisor",
                            },
                            pidfd=pidfd,
                        )
                    finally:
                        os.close(pidfd)
                    grant = response.record.get("result")
                    expected_grant = broker_module.build_session_grant(
                        credential=credential,
                        expected_peer=cast(
                            Mapping[str, object],
                            expected_peer,
                        ),
                        role="formal-supervisor",
                    ).as_record()
                    if grant != expected_grant:
                        raise FormalOrchestrationError(
                            "formal supervisor broker grant drifted"
                        )
                    supervisor_session_issued = True
                    session = {
                        "broker_actor": dict(client.actor),
                        "broker_grant": expected_grant,
                        "broker_nonce_sha256": hashlib.sha256(
                            broker_nonce.encode("ascii")
                        ).hexdigest(),
                        "credential": credential,
                        "expected_peer": dict(expected_peer),
                        "formal_budget_runtime_identity": (
                            _message_identity(
                                authority.canonical_json(
                                    retained_context[
                                        "formal_budget_runtime"
                                    ]
                                )
                            )
                        ),
                        "owner_actor": actor,
                        "package_id": package_id,
                        "schema_version": (
                            FORMAL_SUPERVISOR_SESSION_SCHEMA
                        ),
                    }
                    _send_frame(
                        child,
                        {
                            "actor": actor,
                            "schema_version": RESPONSE_SCHEMA,
                            "sequence": 2,
                            "session": session,
                            "status": "SUPERVISOR_REGISTERED",
                        },
                    )
                    continue
                if (
                    kind == "selection-prepare"
                    and sequence == 3
                    and set(command)
                    == {
                        "admission",
                        "admission_identity",
                        "attempt_consumption",
                        "attempt_consumption_identity",
                        "guardian_ready",
                        "guardian_ready_identity",
                        "kind",
                        "schema_version",
                        "sequence",
                    }
                    and supervisor_session_issued
                ):
                    grant, manager_credential, preregistration_receipt = (
                        preregister_formal_manager_grant(
                            retained_context,
                            attempt_consumption_identity=cast(
                                Mapping[str, object],
                                command["attempt_consumption_identity"],
                            ),
                            broker_client=client,
                        )
                    )
                    selection = build_selection_draft(
                        retained_context,
                        actor,
                        admission=cast(
                            Mapping[str, object],
                            command["admission"],
                        ),
                        admission_identity=cast(
                            Mapping[str, object],
                            command["admission_identity"],
                        ),
                        guardian_ready=cast(
                            Mapping[str, object],
                            command["guardian_ready"],
                        ),
                        guardian_ready_identity=cast(
                            Mapping[str, object],
                            command["guardian_ready_identity"],
                        ),
                        attempt_consumption=cast(
                            Mapping[str, object],
                            command["attempt_consumption"],
                        ),
                        attempt_consumption_identity=cast(
                            Mapping[str, object],
                            command["attempt_consumption_identity"],
                        ),
                        manager_openfile_grant=grant,
                    )
                    prepared_raw = authority.canonical_json(selection)
                    prepared_identity = {
                        "path": retained_context[
                            "formal_selection_path"
                        ],
                        **_message_identity(prepared_raw),
                    }
                    _send_frame(
                        child,
                        {
                            "actor": actor,
                            "artifact_identity": prepared_identity,
                            "kind": "selection-prepare",
                            "manager_openfile_grant": grant,
                            "preregistration_receipt_identity": (
                                _message_identity(
                                    authority.canonical_json(
                                        preregistration_receipt
                                    )
                                )
                            ),
                            "schema_version": RESPONSE_SCHEMA,
                            "sequence": 3,
                            "status": "PREPARED",
                        },
                    )
                    continue
                if (
                    kind == "selection-commit"
                    and sequence == 4
                    and set(command)
                    == {
                        "kind",
                        "prepared_selection_identity",
                        "schema_version",
                        "sequence",
                    }
                    and prepared_raw is not None
                    and prepared_identity is not None
                    and manager_credential is not None
                    and preregistration_receipt is not None
                    and supervisor_session_issued
                    and command["prepared_selection_identity"]
                    == prepared_identity
                ):
                    binding = client.bind_manager_openfile_selection(
                        {
                            "credential": manager_credential,
                            "selection_identity": prepared_identity,
                        }
                    ).record["result"]
                    if type(binding) is not dict:
                        raise FormalOrchestrationError(
                            "formal selection binding is absent"
                        )
                    identity = publish_launch_artifact(
                        label="formal selection",
                        raw=prepared_raw,
                        expected_path=str(
                            retained_context["formal_selection_path"]
                        ),
                    )
                    _send_frame(
                        child,
                        {
                            "actor": actor,
                            "artifact_identity": identity,
                            "broker_binding_receipt_identity": (
                                _message_identity(
                                    authority.canonical_json(binding)
                                )
                            ),
                            "kind": "selection-commit",
                            "preregistration_receipt_identity": (
                                _message_identity(
                                    authority.canonical_json(
                                        preregistration_receipt
                                    )
                                )
                            ),
                            "schema_version": RESPONSE_SCHEMA,
                            "sequence": 4,
                            "status": "PUBLISHED",
                        },
                    )
                    manager_credential = None
                    continue
                if (
                    kind == "handoff-complete"
                    and sequence == 5
                    and set(command)
                    == {"kind", "schema_version", "sequence"}
                    and prepared_raw is not None
                    and prepared_identity is not None
                    and manager_credential is None
                    and supervisor_session_issued
                ):
                    _send_frame(
                        child,
                        {
                            "actor": actor,
                            "schema_version": RESPONSE_SCHEMA,
                            "sequence": 5,
                            "status": "HANDOFF_COMPLETE",
                        },
                    )
                    code = 0
                    break
                raise FormalOrchestrationError(
                    "delayed formal owner lifecycle command drifted"
                )
        except BaseException:
            code = 125
            try:
                _send_frame(
                    child,
                    {
                        "error": (
                            f"{type(sys.exception()).__name__}: "
                            f"{sys.exception()}"
                        ),
                        "schema_version": RESPONSE_SCHEMA,
                        "status": "FAIL_CLOSED",
                    },
                )
            except BaseException:
                pass
        finally:
            if client is not None:
                try:
                    if code == 0:
                        client.close_session()
                    else:
                        client.close()
                except BaseException:
                    code = 125
                    if not client.closed:
                        try:
                            client.close()
                        except BaseException:
                            pass
            if release_read >= 0:
                try:
                    os.close(release_read)
                except BaseException:
                    pass
            if broker_descriptor >= 0:
                try:
                    os.close(broker_descriptor)
                except BaseException:
                    pass
            if broker_parent_descriptor >= 0:
                try:
                    os.close(broker_parent_descriptor)
                except BaseException:
                    pass
            if broker_connection is not None:
                try:
                    broker_connection.close()
                except BaseException:
                    pass
            try:
                child.close()
            except BaseException:
                pass
        os._exit(code)
    child.close()
    os.close(release_read)
    try:
        pidfd, pidfd_method = broker_module.open_pidfd(pid)
        actor = {
            "pid": pid,
            "role": launch_validator.OWNER_PUBLISHER_ROLE,
            "session_id": session_id,
            "starttime": _process_starttime(pid),
        }
        return DelayedFormalLaunchOwnerProcess(
            pid=pid,
            pidfd=pidfd,
            pidfd_method=pidfd_method,
            control=parent,
            release_descriptor=release_write,
            actor=actor,
        )
    except BaseException:
        parent.close()
        os.close(release_write)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        os.waitpid(pid, 0)
        raise


def _spawn_owner(context: Mapping[str, object]) -> OwnerSession:
    driver_raw = bootstrap.FORMAL_LAUNCH_OWNER_DRIVER_V2.encode("utf-8")
    publisher_raw = bootstrap.OWNER_OEXCL_PUBLISH_V1.encode("utf-8")
    driver_identity = _message_identity(driver_raw)
    publisher_identity = _message_identity(publisher_raw)
    if (
        context["formal_launch_owner_driver_identity"] != driver_identity
        or context["mechanical_oexcl_publisher_identity"] != publisher_identity
    ):
        raise FormalOrchestrationError(
            "formal owner literal identities differ from campaign context"
        )
    context_raw = authority.canonical_json(dict(context))
    context_identity = _message_identity(context_raw)
    campaign_module = _formal_campaign_module()
    selected = campaign_module._selected_identities(  # type: ignore[attr-defined]  # noqa: SLF001
        context["outer_spec"]
    )
    owned_descriptors: set[int] = set()
    owned_sockets: set[socket.socket] = set()
    parent: socket.socket | None = None
    child: socket.socket | None = None
    stderr_read = -1
    stderr_write = -1
    pid: int | None = None

    def own_descriptor(descriptor: int) -> int:
        owned_descriptors.add(descriptor)
        return descriptor

    def close_descriptor(descriptor: int) -> BaseException | None:
        if descriptor in owned_descriptors:
            # Remove before close: after an exceptional close the numeric FD
            # may already be reusable, so a retry could close an unrelated FD.
            owned_descriptors.remove(descriptor)
            try:
                os.close(descriptor)
            except BaseException as exc:
                return exc
        return None

    def close_socket(value: socket.socket) -> BaseException | None:
        if value in owned_sockets:
            owned_sockets.remove(value)
            try:
                value.close()
            except BaseException as exc:
                return exc
        return None

    def close_descriptors(values: Sequence[int]) -> BaseException | None:
        first_error: BaseException | None = None
        for descriptor in values:
            error = close_descriptor(descriptor)
            if first_error is None and error is not None:
                first_error = error
        return first_error

    def close_sockets(values: Sequence[socket.socket]) -> BaseException | None:
        first_error: BaseException | None = None
        for value in values:
            error = close_socket(value)
            if first_error is None and error is not None:
                first_error = error
        return first_error

    failure: BaseException | None = None
    try:
        descriptors = {
            3: own_descriptor(
                campaign_module._open_selected(  # type: ignore[attr-defined]  # noqa: SLF001
                    selected["python"],
                    "formal owner Python",
                )
            ),
            4: own_descriptor(
                _sealed_memfd("ab16-formal-owner-publisher", publisher_raw)
            ),
            5: own_descriptor(
                _sealed_memfd("ab16-formal-owner-context", context_raw)
            ),
        }
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        owned_sockets.update((parent, child))
        parent.settimeout(PREREQUISITE_WAIT_SECONDS)
        stderr_read, stderr_write = os.pipe2(os.O_CLOEXEC)
        own_descriptor(stderr_read)
        own_descriptor(stderr_write)
        high = {
            target: own_descriptor(
                fcntl.fcntl(source, fcntl.F_DUPFD_CLOEXEC, 32)
            )
            for target, source in {
                **descriptors,
                6: child.fileno(),
            }.items()
        }
        actions: list[tuple[Any, ...]] = [
            *(
                (os.POSIX_SPAWN_DUP2, high[target], target)
                for target in (3, 4, 5, 6)
            ),
            (os.POSIX_SPAWN_DUP2, stderr_write, 2),
            (os.POSIX_SPAWN_CLOSE, stderr_read),
        ]
        pid = os.posix_spawn(
            "/proc/self/fd/3",
            [
                str(selected["python"]["path"]),
                "-I",
                "-B",
                "-c",
                bootstrap.FORMAL_LAUNCH_OWNER_DRIVER_V2,
                SESSION_ID,
                _canonical_argument(context_identity),
                _canonical_argument(driver_identity),
            ],
            CLEAN_ENV,
            file_actions=actions,
        )
        cleanup_error = close_descriptors(tuple(high.values()))
        socket_error = close_socket(child)
        stderr_error = close_descriptor(stderr_write)
        selected_error = close_descriptors(tuple(descriptors.values()))
        for error in (
            cleanup_error,
            socket_error,
            stderr_error,
            selected_error,
        ):
            if error is not None:
                raise error
        ready = _read_frame(parent, "formal owner ready")
        actor = ready.get("actor")
        if (
            set(ready) != {"actor", "schema_version", "status"}
            or ready["schema_version"] != RESPONSE_SCHEMA
            or ready["status"] != "READY"
            or type(actor) is not dict
            or actor
            != {
                "pid": pid,
                "role": launch_validator.OWNER_PUBLISHER_ROLE,
                "session_id": SESSION_ID,
                "starttime": _process_starttime(pid),
            }
        ):
            raise FormalOrchestrationError(
                "formal owner ready identity drifted"
            )
        owned_sockets.remove(parent)
        owned_descriptors.remove(stderr_read)
        return OwnerSession(
            pid=pid,
            control=parent,
            stderr_descriptor=stderr_read,
            actor=dict(actor),
        )
    except BaseException as exc:
        failure = exc
        if pid is not None:
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                pass
            except BaseException:
                pass
            while True:
                try:
                    observed, _status = os.waitpid(pid, 0)
                    if observed != pid:
                        exc.add_note(
                            "formal owner cleanup wait returned pid "
                            f"{observed}, expected {pid}"
                        )
                    break
                except InterruptedError:
                    continue
                except ChildProcessError:
                    break
                except BaseException as cleanup_exc:
                    exc.add_note(
                        "formal owner cleanup wait failed: "
                        f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                    )
                    break
        raise
    finally:
        socket_cleanup_error = close_sockets(tuple(owned_sockets))
        descriptor_cleanup_error = close_descriptors(
            tuple(owned_descriptors)
        )
        cleanup_error = socket_cleanup_error or descriptor_cleanup_error
        if failure is None and cleanup_error is not None:
            raise cleanup_error


def _publisher(
    context: Mapping[str, object],
    actor: Mapping[str, object],
    *,
    kind: str,
) -> dict[str, object]:
    output = str(
        context[
            "formal_admission_path"
            if kind == "admission"
            else "formal_selection_path"
        ]
    )
    prerequisites = (
        []
        if kind == "admission"
        else [
            "--admission",
            str(context["formal_admission_path"]),
            "--guardian-ready",
            str(context["guardian_ready_path"]),
            "--attempt-consumption",
            str(Path(str(context["formal_attempt_dir"])) / "attempt-consumption.json"),
        ]
    )
    return {
        "actor": dict(actor),
        "argv": {
            "mechanical_publish": [
                "OWNER_OEXCL_PUBLISH_V1",
                Path(output).name,
            ],
            "render": [
                "formal-launch-authority",
                "--campaign-dir",
                str(context["campaign_dir"]),
                "--draft",
                launch_validator.OWNER_MEMFD_PATH,
                "--kind",
                kind,
                *prerequisites,
            ],
            "validate": [
                "formal-launch-validator",
                "--campaign-dir",
                str(context["campaign_dir"]),
                "--candidate",
                launch_validator.OWNER_MEMFD_PATH,
                "--kind",
                kind,
                *prerequisites,
            ],
        },
        "execution_strategy": launch_validator.OWNER_EXECUTION_STRATEGY,
        "formal_launch_owner_driver_identity": context[
            "formal_launch_owner_driver_identity"
        ],
        "mechanical_oexcl_publisher_identity": context[
            "mechanical_oexcl_publisher_identity"
        ],
        "output_mode": 0o444,
        "output_path": output,
        "python_identity": context["python_identity"],
        "renderer_identity": context["launch_renderer_identity"],
        "validator_identity": context["launch_validator_identity"],
    }


def build_admission_draft(
    context: Mapping[str, object],
    actor: Mapping[str, object],
) -> dict[str, object]:
    draft = {
        "admission_id": "formal-admission-a001",
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "baseline_launch_authorized": False,
        "campaign_dir": context["campaign_dir"],
        "campaign_root_identity": context["campaign_root_identity"],
        "controller_launch_authorized": False,
        "created_at_utc": _utc_now(),
        "formal_attempt_dir": context["formal_attempt_dir"],
        "formal_attempt_selected": False,
        "formal_selection_path": context["formal_selection_path"],
        "formal_selection_publication_authorized": True,
        "gate_b_approval_identity": context["gate_b_approval_identity"],
        "gate_b_epoch_observation_identity": context[
            "gate_b_epoch_observation_identity"
        ],
        "guardian_control_socket_path": context["guardian_control_socket_path"],
        "guardian_control_retired_socket_path": context[
            "guardian_control_retired_socket_path"
        ],
        "guardian_launch_authorized": True,
        "guardian_ready_path": context["guardian_ready_path"],
        "guardian_spec": context["guardian_spec"],
        "manager_epoch": context["manager_epoch"],
        "manager_epoch_observation_identity": context[
            "manager_epoch_observation_identity"
        ],
        "outer_launch_authorized": False,
        "package_id": context["package_id"],
        "package_manifest_identity": context["package_manifest_identity"],
        "package_seal_identity": context["package_seal_identity"],
        "publication_path": context["formal_admission_path"],
        "publisher": _publisher(context, actor, kind="admission"),
        "repository_head": context["repository_head"],
        "schema_version": launch_validator.FORMAL_ADMISSION_SCHEMA,
        "snapshot_materialization_identity": context[
            "snapshot_materialization_identity"
        ],
        "snapshot_root": context["snapshot_root"],
        "status": "ADMITTED",
    }
    return launch_validator.validate_admission(
        draft,
        expected_context=context,
    )


def build_selection_draft(
    context: Mapping[str, object],
    actor: Mapping[str, object],
    *,
    admission: Mapping[str, object],
    admission_identity: Mapping[str, object],
    guardian_ready: Mapping[str, object],
    guardian_ready_identity: Mapping[str, object],
    attempt_consumption: Mapping[str, object],
    attempt_consumption_identity: Mapping[str, object],
    manager_openfile_grant: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if manager_openfile_grant is None:
        raise FormalOrchestrationError(
            "prospective formal selection lacks its preregistered manager "
            "OpenFile grant"
        )
    outer_spec = cast(Mapping[str, object], context["outer_spec"])
    draft = {
        "arm_prelaunch_paths": outer_spec["arm_prelaunch_paths"],
        "attempt_consumption_identity": dict(attempt_consumption_identity),
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "baseline_identity": context["baseline_identity"],
        "baseline_launch_authorized": True,
        "campaign_dir": context["campaign_dir"],
        "campaign_root_identity": context["campaign_root_identity"],
        "child_audit_path": outer_spec["child_audit_path"],
        "consumed": True,
        "controller_identity": context["controller_identity"],
        "controller_launch_authorized": True,
        "created_at_utc": _utc_now(),
        "formal_admission_identity": dict(admission_identity),
        "formal_attempt_dir": context["formal_attempt_dir"],
        "formal_attempt_selected": True,
        "gate1_prelaunch_ownership_path": outer_spec[
            "gate1_prelaunch_ownership_path"
        ],
        "gate1_selection_identity": context["gate1_selection_identity"],
        "gate_b_approval_identity": context["gate_b_approval_identity"],
        "gate_b_epoch_observation_identity": context[
            "gate_b_epoch_observation_identity"
        ],
        "guardian_ready_identity": dict(guardian_ready_identity),
        "guardian_runtime_identity": guardian_ready["guardian_runtime_identity"],
        "guardian_spec": context["guardian_spec"],
        "guardian_unit_identity": guardian_ready["guardian_unit_identity"],
        "lock_identities": guardian_ready["lock_identities"],
        "manager_epoch": context["manager_epoch"],
        "manager_epoch_observation_identity": context[
            "manager_epoch_observation_identity"
        ],
        "outer_launch_authorized": True,
        "outer_spec": context["outer_spec"],
        "package_id": context["package_id"],
        "package_manifest_identity": context["package_manifest_identity"],
        "package_seal_identity": context["package_seal_identity"],
        "publication_path": context["formal_selection_path"],
        "publisher": _publisher(context, actor, kind="selection"),
        "repository_head": context["repository_head"],
        "retry_eligible": False,
        "schema_version": launch_validator.FORMAL_SELECTION_SCHEMA_V3,
        "selection_id": "formal-selection-a001",
        "snapshot_materialization_identity": context[
            "snapshot_materialization_identity"
        ],
        "snapshot_root": context["snapshot_root"],
        "status": "SELECTED",
    }
    draft["manager_openfile_grant"] = dict(manager_openfile_grant)
    return launch_validator.validate_selection(
        draft,
        admission=admission,
        admission_identity=admission_identity,
        guardian_ready=guardian_ready,
        guardian_ready_identity=guardian_ready_identity,
        attempt_consumption=attempt_consumption,
        attempt_consumption_identity=attempt_consumption_identity,
        expected_context=context,
    )


def preregister_formal_manager_grant(
    context: Mapping[str, object],
    *,
    attempt_consumption_identity: Mapping[str, object],
    broker_client: Any,
    credential: str | None = None,
) -> tuple[dict[str, object], str, dict[str, object]]:
    """Create the non-self-referential manager grant before PREPARE.

    The plaintext credential and broker response remain out of the selection.
    The immutable selection carries only the credential hash and the canonical
    result-message identity.  A later broker binding receipt joins that
    preregistration to the final PREPARE identity before COMMIT.
    """

    token = secrets.token_hex(32) if credential is None else credential
    if (
        not isinstance(token, str)
        or len(token) != 64
        or any(character not in "0123456789abcdef" for character in token)
    ):
        raise FormalOrchestrationError(
            "formal manager OpenFile credential is malformed"
        )
    manager_epoch_identity = _message_identity(
        authority.canonical_json(context["manager_epoch"])
    )
    response = broker_client.request(
        "PREREGISTER_MANAGER_OPENFILE_GRANT",
        {
            "attempt_consumption_identity": dict(
                attempt_consumption_identity
            ),
            "credential": token,
            "manager_epoch_identity": manager_epoch_identity,
            "selection_path": context["formal_selection_path"],
            "unit_name": cast(
                Mapping[str, object],
                context["outer_spec"],
            )["unit_name"],
        },
    )
    result = response.record.get("result")
    if (
        type(result) is not dict
        or result.get("state") != "UNBOUND"
        or result.get("credential_sha256")
        != hashlib.sha256(token.encode("ascii")).hexdigest()
        or result.get("selection_path")
        != context["formal_selection_path"]
        or result.get("manager_epoch_identity")
        != manager_epoch_identity
    ):
        raise FormalOrchestrationError(
            "formal manager OpenFile preregistration response drifted"
        )
    preregistration_identity = _message_identity(
        authority.canonical_json(result)
    )
    runtime = cast(
        Mapping[str, object],
        context["formal_budget_runtime"],
    )
    grant = {
        "attempt_consumption_identity": dict(
            attempt_consumption_identity
        ),
        "budget_profile_identity": context[
            "resource_budget_profile_identity"
        ],
        "credential_sha256": result["credential_sha256"],
        "formal_budget_runtime": dict(runtime),
        "formal_root_contract_identity": runtime[
            "formal_root_contract_identity"
        ],
        "formal_resource_calibration_bundle_identity": cast(
            Mapping[str, Mapping[str, object]],
            context["resource_calibration_authorization_bundles"],
        )["FORMAL_ORGANIC_ARM"]["identity"],
        "grant_id": "formal-manager-openfile-a001",
        "manager_epoch_identity": manager_epoch_identity,
        "preregistration_receipt_identity": preregistration_identity,
        "schema_version": launch_validator.MANAGER_OPENFILE_GRANT_SCHEMA,
        "selected_fd_transport": context["selected_fd_transport"],
        "selection_path": context["formal_selection_path"],
        "state": "PREREGISTERED_UNBOUND",
        "unit_name": cast(
            Mapping[str, object],
            context["outer_spec"],
        )["unit_name"],
    }
    return grant, token, dict(result)


def bind_and_commit_prepared_selection(
    *,
    owner: OwnerSession,
    broker_client: Any,
    selection_draft: Mapping[str, object],
    manager_credential: str,
    preregistration_receipt: Mapping[str, object],
) -> tuple[dict[str, Any], dict[str, object]]:
    """Linearize broker BIND between immutable PREPARE and COMMIT."""

    prepared = owner.prepare_selection(selection_draft)
    prepared_identity = cast(
        Mapping[str, object],
        prepared["artifact_identity"],
    )
    binding = broker_client.bind_manager_openfile_selection(
        {
            "credential": manager_credential,
            "selection_identity": dict(prepared_identity),
        }
    )
    binding_result = binding.record.get("result")
    if (
        type(binding_result) is not dict
        or binding_result.get("state") != "PREPARED_SELECTION_BOUND"
        or binding_result.get("selection_identity")
        != dict(prepared_identity)
        or binding_result.get("credential_sha256")
        != hashlib.sha256(
            manager_credential.encode("ascii")
        ).hexdigest()
    ):
        raise FormalOrchestrationError(
            "formal prepared-selection broker binding drifted"
        )
    preregistration_identity = _message_identity(
        authority.canonical_json(dict(preregistration_receipt))
    )
    binding_identity = _message_identity(
        authority.canonical_json(binding_result)
    )
    committed = owner.commit_prepared_selection(
        prepared_selection_identity=prepared_identity,
        preregistration_receipt_identity=preregistration_identity,
        broker_binding_receipt_identity=binding_identity,
    )
    return committed, dict(binding_result)


def _wait_record(
    path: Path,
    label: str,
    *,
    owner: OwnerSession,
    supervisor_alive: Callable[[], bool],
) -> tuple[dict[str, Any], dict[str, object]]:
    deadline = time.monotonic() + PREREQUISITE_WAIT_SECONDS
    while time.monotonic() <= deadline:
        if _process_starttime(owner.pid) != owner.actor["starttime"]:
            raise FormalOrchestrationError(
                f"formal owner died while waiting for {label}"
            )
        if not supervisor_alive():
            raise FormalOrchestrationError(
                f"formal supervisor exited before {label}"
            )
        try:
            observed = os.lstat(path)
        except FileNotFoundError:
            time.sleep(POLL_SECONDS)
            continue
        except OSError as exc:
            raise FormalOrchestrationError(
                f"{label} surface could not be inspected"
            ) from exc
        observed_mode = stat.S_IMODE(observed.st_mode)
        if stat.S_ISREG(observed.st_mode) and observed_mode == 0o444:
            return launch_validator.read_canonical_record(
                path,
                expected_identity=None,
                label=label,
            )
        if stat.S_ISREG(observed.st_mode) and observed_mode == 0o600:
            time.sleep(POLL_SECONDS)
            continue
        raise FormalOrchestrationError(
            f"{label} is not one completed readonly regular file"
        )
    raise FormalOrchestrationError(f"{label} did not appear before deadline")


def _verify_selected_self(context: Mapping[str, object]) -> None:
    """Require this executing module to be the loader-selected snapshot byte."""

    snapshot = authority.snapshot_regular(Path(__file__).resolve())
    actual = authority.detached_identity(snapshot)
    expected = launch_validator.validate_detached_identity(
        context["formal_orchestrator_identity"],
        "formal orchestrator selected identity",
    )
    actual_path = Path(str(actual["path"]))
    snapshot_root = Path(str(context["snapshot_root"]))
    if (
        actual["sha256"] != expected["sha256"]
        or actual["size_bytes"] != expected["size_bytes"]
        or not actual_path.is_relative_to(snapshot_root)
    ):
        raise FormalOrchestrationError(
            "formal orchestrator is not the package-selected snapshot byte"
        )


def orchestrate(
    campaign_dir: Path | str,
    *,
    claim_transport: (
        FormalLaunchClaimTransport
        | ConnectedFormalLaunchClaimTransport
    ),
) -> dict[str, object]:
    """Run one fixed admission-to-selection-to-supervisor lifecycle."""

    campaign = Path(campaign_dir).absolute()
    context = launch_validator.replay_formal_launch_context(authority, campaign)
    _verify_selected_self(context)
    owner = claim_transport.claim(context)
    supervisor_result: dict[str, object] = {}
    supervisor_error: list[BaseException] = []
    supervisor_returncode: list[int] = []
    supervisor_done = threading.Event()
    supervisor_cancel = threading.Event()

    def run_supervisor() -> None:
        try:
            campaign_module = _formal_campaign_module()
            selected_result = campaign_module.run_selected_direct_result(  # type: ignore[attr-defined]
                context=context,
                role="formal-supervisor",
                role_argv=("--campaign-dir", str(campaign)),
                timeout_seconds=SUPERVISOR_WAIT_SECONDS,
                cancel_requested=supervisor_cancel.is_set,
                formal_launch_claimant_registrar=owner,
            )
            if (
                selected_result.returncode not in {0, 2}
                or selected_result.stderr
            ):
                raise FormalOrchestrationError(
                    "formal supervisor exit contract drifted: "
                    f"exit={selected_result.returncode}, "
                    f"stderr={selected_result.stderr!r}"
                )
            value = authority.strict_loads(
                selected_result.stdout,
                "formal supervisor output",
            )
            canonical = authority.canonical_json(value)
            if type(value) is not dict or selected_result.stdout not in {
                canonical,
                canonical + b"\n",
            }:
                raise FormalOrchestrationError(
                    "formal supervisor output is not canonical"
                )
            supervisor_result.update(value)
            supervisor_returncode.append(selected_result.returncode)
        except BaseException as exc:
            supervisor_error.append(exc)
        finally:
            supervisor_done.set()

    supervisor_thread: threading.Thread | None = None
    failure: BaseException | None = None
    try:
        owner.deliver_context(context)
        admission_draft = build_admission_draft(context, owner.actor)
        admission_response = owner.request(
            sequence=1,
            kind="admission",
            draft=admission_draft,
        )
        admission, admission_identity = launch_validator.read_canonical_record(
            str(context["formal_admission_path"]),
            expected_identity=admission_response["artifact_identity"],
            label="formal launch admission",
        )
        launch_validator.validate_admission(
            admission,
            expected_context=context,
        )

        supervisor_thread = threading.Thread(
            target=run_supervisor,
            name="ab16-formal-supervisor",
            daemon=False,
        )
        supervisor_thread.start()

        def supervisor_alive() -> bool:
            if not supervisor_done.is_set():
                return True
            if supervisor_error:
                error = supervisor_error[0]
                raise FormalOrchestrationError(
                    "formal supervisor failed during prerequisite wait: "
                    f"{error}"
                ) from error
            return False

        guardian, guardian_identity = _wait_record(
            Path(str(context["guardian_ready_path"])),
            "outer guardian ready",
            owner=owner,
            supervisor_alive=supervisor_alive,
        )
        attempt, attempt_identity = _wait_record(
            Path(str(context["formal_attempt_dir"])) / "attempt-consumption.json",
            "formal attempt consumption",
            owner=owner,
            supervisor_alive=supervisor_alive,
        )
        prepared_selection = owner.prepare_bound_selection(
            admission=admission,
            admission_identity=admission_identity,
            guardian_ready=guardian,
            guardian_ready_identity=guardian_identity,
            attempt_consumption=attempt,
            attempt_consumption_identity=attempt_identity,
        )
        selection_response = owner.commit_bound_selection(
            prepared_selection_identity=cast(
                Mapping[str, object],
                prepared_selection["artifact_identity"],
            ),
        )
        selection, selection_identity = launch_validator.read_canonical_record(
            str(context["formal_selection_path"]),
            expected_identity=selection_response["artifact_identity"],
            label="formal launch selection",
        )
        launch_validator.validate_selection(
            selection,
            admission=admission,
            admission_identity=admission_identity,
            guardian_ready=guardian,
            guardian_ready_identity=guardian_identity,
            attempt_consumption=attempt,
            attempt_consumption_identity=attempt_identity,
            expected_context=context,
        )
        supervisor_thread.join(SUPERVISOR_WAIT_SECONDS)
        if supervisor_thread.is_alive():
            raise FormalOrchestrationError(
                "formal supervisor outlived its fixed orchestration deadline"
            )
        if supervisor_error:
            raise FormalOrchestrationError(
                f"formal supervisor failed: {supervisor_error[0]}"
            ) from supervisor_error[0]
        outcome = supervisor_result.get("outcome")
        expected_returncode = 0 if outcome == "VERIFIED" else 2
        if (
            outcome not in {"VERIFIED", "INCOMPLETE"}
            or supervisor_returncode != [expected_returncode]
            or supervisor_result.get("formal_selection_identity")
            != selection_identity
        ):
            raise FormalOrchestrationError(
                "formal supervisor result did not join the selected campaign"
            )
        # The supervisor independently replays the selection publisher's
        # PID/starttime before activating the guardian and formal units.  Keep
        # the same owner actor live until that complete supervisor lifecycle
        # has returned; local selection replay is not a consumption ack.
        owner.complete_handoff()
        return {
            "admission_identity": admission_identity,
            "authority_scope": AUTHORITY_SCOPE,
            "formal_selection_identity": selection_identity,
            "owner_actor": owner.actor,
            "owner_handoff_complete": True,
            "status": outcome,
            "supervisor_result": supervisor_result,
        }
    except BaseException as exc:
        failure = exc
        raise
    finally:
        cleanup_error: BaseException | None = None
        if supervisor_thread is not None and supervisor_thread.is_alive():
            supervisor_cancel.set()
            supervisor_thread.join(PREREQUISITE_WAIT_SECONDS)
            if supervisor_thread.is_alive():
                cleanup_error = FormalOrchestrationError(
                    "formal supervisor did not stop after coordinator cancellation"
                )
        try:
            owner.close()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
        if failure is None and cleanup_error is not None:
            raise cleanup_error


def launch_selected(campaign_dir: Path | str) -> dict[str, object]:
    """Enter the orchestrator only through the existing selected-byte loader."""

    campaign = Path(campaign_dir).absolute()
    context = launch_validator.replay_formal_launch_context(authority, campaign)
    campaign_module = _formal_campaign_module()
    selected_result = campaign_module.run_selected_direct_result(  # type: ignore[attr-defined]
        context=context,
        role="formal-orchestrator",
        role_argv=("--selected", "--campaign-dir", str(campaign)),
        timeout_seconds=SUPERVISOR_WAIT_SECONDS + PREREQUISITE_WAIT_SECONDS,
    )
    if (
        selected_result.returncode not in {0, 2}
        or selected_result.stderr
    ):
        raise FormalOrchestrationError(
            "selected formal orchestrator exit contract drifted: "
            f"exit={selected_result.returncode}, "
            f"stderr={selected_result.stderr!r}"
        )
    value = authority.strict_loads(
        selected_result.stdout,
        "selected formal orchestrator output",
    )
    canonical = authority.canonical_json(value)
    expected_status = "VERIFIED" if selected_result.returncode == 0 else "INCOMPLETE"
    if (
        type(value) is not dict
        or selected_result.stdout != canonical
        or value.get("status") != expected_status
        or value.get("authority_scope") != AUTHORITY_SCOPE
    ):
        raise FormalOrchestrationError(
            "selected formal orchestrator result contract drifted"
        )
    return dict(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    parser.add_argument("--selected", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    claim_transport: (
        FormalLaunchClaimTransport
        | ConnectedFormalLaunchClaimTransport
        | None
    ) = None,
) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.selected:
            if claim_transport is None:
                raise FormalOrchestrationError(
                    "selected formal orchestrator lacks its explicit claim transport"
                )
            result = orchestrate(
                arguments.campaign_dir,
                claim_transport=claim_transport,
            )
        else:
            if claim_transport is not None:
                raise FormalOrchestrationError(
                    "outer launcher received a selected claim transport"
                )
            result = launch_selected(arguments.campaign_dir)
    except BaseException as exc:
        print(
            f"FAIL_CLOSED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 125
    sys.stdout.buffer.write(authority.canonical_json(result))
    sys.stdout.buffer.flush()
    return 0 if result["status"] == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
