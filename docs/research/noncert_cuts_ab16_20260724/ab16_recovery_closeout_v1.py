#!/usr/bin/env python3
"""Strict-once recovery closeout actor for the prospective AB16 budget cohort."""

from __future__ import annotations

from collections.abc import Mapping
import fcntl
import hashlib
import os
from pathlib import PurePosixPath
import secrets
import select
import socket
import stat
from typing import Final, Protocol, cast

if __package__:
    from . import ab16_budget_authority_v1 as budget
    from . import ab16_budget_broker_v1 as broker
else:
    import ab16_budget_authority_v1 as budget
    import ab16_budget_broker_v1 as broker


PACKAGE_ROLE: Final = "ab16-recovery-closeout-v1"
REQUEST_SCHEMA: Final = "noncert-cuts-ab16-recovery-request-v1"
RESPONSE_SCHEMA: Final = "noncert-cuts-ab16-recovery-response-v1"
ACTOR_SCHEMA: Final = "noncert-cuts-ab16-recovery-actor-v1"
DISARM_OBSERVATION_SCHEMA: Final = "noncert-cuts-ab16-recovery-disarm-observation-v1"
TAKEOVER_CLOSEOUT_SCHEMA: Final = (
    "noncert-cuts-ab16-recovery-takeover-consumed-incomplete-v1"
)
LOCK_CONSUMPTION_SCHEMA: Final = "noncert-cuts-ab16-recovery-lock-consumption-v1"
DISARM_INTENT_SCHEMA: Final = "noncert-cuts-ab16-recovery-disarm-intent-v1"
OWNER_HANDOFF_SCHEMA: Final = "noncert-cuts-ab16-recovery-owner-handoff-v1"
OWNER_OBSERVATION_SCHEMA: Final = (
    "noncert-cuts-ab16-recovery-owner-observation-v2"
)
PREPARED_RECOVERY_SCHEMA: Final = "noncert-cuts-ab16-prepared-recovery-v2"
UNUSED_CLOSEOUT_SCHEMA: Final = (
    "noncert-cuts-ab16-recovery-unused-closeout-v1"
)


class RecoveryProtocolError(RuntimeError):
    """A recovery identity, liveness, or strict-once invariant failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class BrokerLivenessProtocol(Protocol):
    """Minimum package-broker identity retained by the recovery actor."""

    actor: Mapping[str, object]
    pidfd: int


def _exact_keys(value: Mapping[str, object], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise RecoveryProtocolError("FRAME_SHAPE_MISMATCH", f"{label} keys differ")


def _nonce(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecoveryProtocolError("INVALID_NONCE", "recovery nonce is invalid")
    return value


def _identity(descriptor: int) -> broker.DescriptorIdentity:
    return broker._identity(descriptor)  # noqa: SLF001


def _validate_recovery_purposes(
    closeout_extent: Mapping[str, object],
    lock_extent: Mapping[str, object],
) -> None:
    if (
        closeout_extent["artifact_class"] != "closeout"
        or closeout_extent["parent_path"] != "closeout"
        or closeout_extent["target_name"]
        != "formal-consumed-incomplete.json"
        or lock_extent["artifact_class"] != "metadata"
        or lock_extent["parent_path"] not in {"control", "locks"}
        or lock_extent["target_name"]
        != "recovery-takeover-consumption.json"
    ):
        raise RecoveryProtocolError(
            "RECOVERY_EXTENT_PURPOSE_DRIFT",
            "recovery authority is not the fixed closeout and once-lock pair",
        )


class RecoveryServer:
    """Own the sole recovery staging FD and takeover lock until one terminal action."""

    def __init__(
        self,
        connection: socket.socket,
        *,
        nonce: str,
        expected_peer: Mapping[str, int],
        broker_actor: Mapping[str, object],
        broker_pidfd: int,
        closeout_extent: object,
        closeout_parent_fd: int,
        closeout_fd: int,
        lock_extent: object,
        lock_fd: int,
    ) -> None:
        self.connection = connection
        self.nonce = _nonce(nonce)
        self.expected_peer = dict(expected_peer)
        self.broker_actor = dict(broker_actor)
        self.broker_pidfd: int | None = broker_pidfd
        self.closeout_extent = broker.validate_prepared_extent(closeout_extent)
        self.closeout_parent_fd: int | None = closeout_parent_fd
        self.closeout_fd: int | None = closeout_fd
        self.lock_extent = broker.validate_prepared_extent(lock_extent)
        self.lock_fd: int | None = lock_fd
        self.actor = {"schema_version": ACTOR_SCHEMA, **broker.process_identity()}
        self._terminal = False
        self._pending_disarm_digest: str | None = None
        self._pending_unused_identity: dict[str, object] | None = None
        _validate_recovery_purposes(
            self.closeout_extent,
            self.lock_extent,
        )
        parent_identity = broker._parent_identity(closeout_parent_fd)  # noqa: SLF001
        if parent_identity != self.closeout_extent["parent_identity"]:
            raise RecoveryProtocolError("PARENT_IDENTITY_DRIFT", "recovery closeout parent differs")
        if _identity(closeout_fd) != self.closeout_extent["staging_identity"]:
            raise RecoveryProtocolError("STAGING_IDENTITY_DRIFT", "recovery closeout extent differs")
        if _identity(lock_fd) != self.lock_extent["staging_identity"]:
            raise RecoveryProtocolError("LOCK_IDENTITY_DRIFT", "recovery takeover lock differs")

    def _require_peer(self, observed: Mapping[str, int]) -> None:
        for key in ("pid", "pid_starttime", "uid"):
            if observed[key] != self.expected_peer[key]:
                raise RecoveryProtocolError("PEER_IDENTITY_DRIFT", "recovery peer identity drifted")

    def _consume_actor_slot(self) -> dict[str, object]:
        assert self.lock_fd is not None
        return broker.consume_once_extent(
            self.lock_extent,
            descriptor=self.lock_fd,
            record={
                "schema_version": LOCK_CONSUMPTION_SCHEMA,
                "actor": dict(self.actor),
                "broker_actor": dict(self.broker_actor),
                "nonce": self.nonce,
                "state": "RECOVERY_ACTOR_ARMED",
            },
        )

    def _takeover(self, payload: Mapping[str, object]) -> dict[str, object]:
        _exact_keys(payload, {"consumption_state", "reason"}, label="recovery takeover")
        if payload["consumption_state"] != budget.FORMAL_CONSUMED_INCOMPLETE:
            raise RecoveryProtocolError(
                "RECOVERY_STATE_FORBIDDEN",
                "recovery may only publish formal-consumed-incomplete",
            )
        if not isinstance(payload["reason"], str) or not payload["reason"]:
            raise RecoveryProtocolError("FRAME_SHAPE_MISMATCH", "recovery reason is invalid")
        assert self.broker_pidfd is not None
        if not broker.pidfd_reports_exit(self.broker_pidfd):
            raise RecoveryProtocolError("BROKER_STILL_LIVE", "recovery takeover requires proved broker exit")
        terminal = {
            "schema_version": TAKEOVER_CLOSEOUT_SCHEMA,
            "authority": {
                "changes_certified_exact": False,
                "changes_cut_state": False,
                "changes_lower_bound": False,
                "changes_production": False,
                "changes_upper_bound": False,
                "research_only": True,
            },
            "broker_actor": dict(self.broker_actor),
            "consumption_state": budget.FORMAL_CONSUMED_INCOMPLETE,
            "reason": payload["reason"],
            "recovery_actor": dict(self.actor),
        }
        assert self.closeout_parent_fd is not None and self.closeout_fd is not None
        identity = broker.publish_preallocated_extent(
            self.closeout_extent,
            parent_fd=self.closeout_parent_fd,
            staging_fd=self.closeout_fd,
            raw=broker.canonical_json_bytes(terminal),
        )
        return {
            "closeout_identity": identity,
            "consumption_state": budget.FORMAL_CONSUMED_INCOMPLETE,
            "state": "STRICT_ONCE_TAKEOVER_PUBLISHED",
        }

    def _release_owned(self) -> None:
        errors: list[BaseException] = []
        if self.closeout_fd is not None:
            try:
                observed = os.fstat(self.closeout_fd)
                if stat.S_IMODE(observed.st_mode) == 0o600:
                    broker.consume_once_extent(
                        self.closeout_extent,
                        descriptor=self.closeout_fd,
                        record={
                            "schema_version": UNUSED_CLOSEOUT_SCHEMA,
                            "recovery_actor": dict(self.actor),
                            "state": "SEALED_ACTOR_EXIT_INCOMPLETE",
                        },
                    )
            except BaseException as exc:
                errors.append(exc)
        for attribute in ("closeout_fd", "closeout_parent_fd", "broker_pidfd"):
            descriptor = getattr(self, attribute)
            if descriptor is None:
                continue
            setattr(self, attribute, None)
            try:
                os.close(descriptor)
            except BaseException as exc:
                errors.append(exc)
        if self.lock_fd is not None:
            descriptor = self.lock_fd
            self.lock_fd = None
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            except BaseException as exc:
                errors.append(exc)
            try:
                os.close(descriptor)
            except BaseException as exc:
                errors.append(exc)
        if errors:
            primary = RecoveryProtocolError(
                "OWNERSHIP_RELEASE_UNCERTAIN",
                "recovery FD or takeover-lock release failed",
            )
            for error in errors:
                primary.add_note(f"{type(error).__name__}: {error}")
            raise primary

    def _unused_closeout(
        self,
        digest: str,
    ) -> tuple[dict[str, object], dict[str, object]]:
        record: dict[str, object] = {
            "schema_version": UNUSED_CLOSEOUT_SCHEMA,
            "actor": dict(self.actor),
            "broker_actor": dict(self.broker_actor),
            "disarm_intent_sha256": digest,
            "state": "UNUSED_CLOSEOUT_SEALED",
        }
        raw = broker.canonical_json_bytes(record)
        return (
            record,
            {
                "path": str(
                    PurePosixPath(
                        self.closeout_extent["parent_path"],
                        self.closeout_extent["staging_name"],
                    )
                ),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            },
        )

    def _prepare_disarm(self, payload: Mapping[str, object]) -> dict[str, object]:
        _exact_keys(payload, {"disarm_intent_sha256"}, label="recovery disarm")
        digest = payload["disarm_intent_sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise RecoveryProtocolError("FRAME_SHAPE_MISMATCH", "disarm intent digest is invalid")
        if self._pending_disarm_digest is not None:
            raise RecoveryProtocolError(
                "DISARM_ALREADY_PREPARED",
                "recovery disarm cannot be prepared twice",
            )
        _record, unused_closeout_identity = self._unused_closeout(digest)
        self._pending_disarm_digest = digest
        self._pending_unused_identity = unused_closeout_identity
        return {
            "schema_version": DISARM_OBSERVATION_SCHEMA,
            "actor": dict(self.actor),
            "broker_actor": dict(self.broker_actor),
            "disarm_intent_sha256": digest,
            "state": "DISARM_PREPARED_AWAITING_ACK",
            "unused_closeout_identity": unused_closeout_identity,
        }

    def _commit_disarm(self, payload: Mapping[str, object]) -> None:
        _exact_keys(payload, {"disarm_intent_sha256"}, label="recovery disarm acknowledgement")
        digest = payload["disarm_intent_sha256"]
        if (
            not isinstance(digest, str)
            or digest != self._pending_disarm_digest
            or self._pending_unused_identity is None
        ):
            raise RecoveryProtocolError(
                "DISARM_ACK_IDENTITY_DRIFT",
                "recovery disarm acknowledgement differs from the prepared intent",
            )
        record, predicted_identity = self._unused_closeout(digest)
        if predicted_identity != self._pending_unused_identity:
            raise RecoveryProtocolError(
                "DISARM_ACK_IDENTITY_DRIFT",
                "recovery disarm prediction drifted before commit",
            )
        assert self.closeout_fd is not None
        observed_identity = broker.consume_once_extent(
            self.closeout_extent,
            descriptor=self.closeout_fd,
            record=record,
        )
        if observed_identity != predicted_identity:
            raise RecoveryProtocolError(
                "DISARM_PUBLICATION_IDENTITY_DRIFT",
                "recovery disarm publication differs from its acknowledged identity",
            )

    def _validate_request(
        self,
        frame: broker.ReceivedFrame,
        *,
        action: str,
        sequence: int,
    ) -> dict[str, object]:
        self._require_peer(frame.peer)
        record = frame.record
        _exact_keys(
            record,
            {"action", "nonce", "payload", "schema_version", "sequence"},
            label="recovery request",
        )
        if (
            record["schema_version"] != REQUEST_SCHEMA
            or _nonce(record["nonce"]) != self.nonce
            or record["sequence"] != sequence
            or record["action"] != action
            or type(record["payload"]) is not dict
        ):
            raise RecoveryProtocolError(
                "REQUEST_IDENTITY_DRIFT",
                "recovery request identity drifted",
            )
        return dict(cast(Mapping[str, object], record["payload"]))

    def _wait_for_control_or_broker_exit(
        self,
        poller: select.poll,
        *,
        control_registered: bool,
    ) -> tuple[broker.ReceivedFrame | None, bool]:
        connection_fd = self.connection.fileno()
        assert self.broker_pidfd is not None
        while True:
            events = dict(poller.poll())
            connection_events = events.get(connection_fd, 0)
            if control_registered and connection_events & select.POLLIN:
                try:
                    return broker.receive_frame(self.connection), True
                except BaseException:
                    poller.unregister(connection_fd)
                    control_registered = False
            if (
                control_registered
                and connection_events & (select.POLLHUP | select.POLLERR)
            ):
                poller.unregister(connection_fd)
                control_registered = False
            broker_events = events.get(self.broker_pidfd, 0)
            if broker_events & (select.POLLIN | select.POLLHUP | select.POLLERR):
                return None, control_registered
            if broker.pidfd_reports_exit(self.broker_pidfd):
                return None, control_registered

    def _autonomous_takeover(self, *, phase: str) -> int:
        self._takeover(
            {
                "consumption_state": budget.FORMAL_CONSUMED_INCOMPLETE,
                "reason": (
                    "persistent budget broker exited before recovery "
                    f"disarm acknowledgement ({phase})"
                ),
            }
        )
        self._release_owned()
        self._terminal = True
        return 0

    def run(self) -> int:
        lock_identity = self._consume_actor_slot()
        broker.send_frame(
            self.connection,
            {
                "schema_version": RESPONSE_SCHEMA,
                "action": "READY",
                "actor": dict(self.actor),
                "lock_consumption": lock_identity,
                "nonce": self.nonce,
                "result": {"state": "ARMED"},
                "sequence": 0,
                "status": "PASS",
            },
        )
        try:
            poller = select.poll()
            poller.register(
                self.connection.fileno(),
                select.POLLIN | select.POLLHUP | select.POLLERR,
            )
            assert self.broker_pidfd is not None
            poller.register(
                self.broker_pidfd,
                select.POLLIN | select.POLLHUP | select.POLLERR,
            )
            frame, control_registered = self._wait_for_control_or_broker_exit(
                poller,
                control_registered=True,
            )
            if frame is None:
                return self._autonomous_takeover(phase="before-terminal-request")
            self._require_peer(frame.peer)
            record = frame.record
            _exact_keys(
                record,
                {"action", "nonce", "payload", "schema_version", "sequence"},
                label="recovery request",
            )
            if (
                record["schema_version"] != REQUEST_SCHEMA
                or _nonce(record["nonce"]) != self.nonce
                or record["sequence"] != 1
                or type(record["payload"]) is not dict
            ):
                raise RecoveryProtocolError("REQUEST_IDENTITY_DRIFT", "recovery request identity drifted")
            action = record["action"]
            if action == "TAKEOVER":
                result = self._takeover(dict(record["payload"]))
            elif action == "DISARM":
                result = self._prepare_disarm(dict(record["payload"]))
                try:
                    broker.send_frame(
                        self.connection,
                        {
                            "schema_version": RESPONSE_SCHEMA,
                            "action": action,
                            "actor": dict(self.actor),
                            "nonce": self.nonce,
                            "result": result,
                            "sequence": 1,
                            "status": "PASS",
                        },
                    )
                except BaseException:
                    control_registered = False
                    try:
                        poller.unregister(self.connection.fileno())
                    except KeyError:
                        pass
                acknowledgement, _control_registered = (
                    self._wait_for_control_or_broker_exit(
                        poller,
                        control_registered=control_registered,
                    )
                )
                if acknowledgement is None:
                    return self._autonomous_takeover(
                        phase="after-disarm-prepare",
                    )
                acknowledgement_payload = self._validate_request(
                    acknowledgement,
                    action="DISARM_ACK",
                    sequence=2,
                )
                self._commit_disarm(acknowledgement_payload)
                self._release_owned()
                self._terminal = True
                return 0
            else:
                raise RecoveryProtocolError("UNKNOWN_ACTION", f"unknown recovery action: {action!r}")
            self._release_owned()
            self._terminal = True
            broker.send_frame(
                self.connection,
                {
                    "schema_version": RESPONSE_SCHEMA,
                    "action": action,
                    "actor": dict(self.actor),
                    "nonce": self.nonce,
                    "result": result,
                    "sequence": 1,
                    "status": "PASS",
                },
            )
            return 0
        except BaseException as exc:
            try:
                broker.send_frame(
                    self.connection,
                    {
                        "schema_version": RESPONSE_SCHEMA,
                        "action": "FAIL_CLOSED",
                        "actor": dict(self.actor),
                        "code": getattr(exc, "code", type(exc).__name__),
                        "nonce": self.nonce,
                        "result": {"message": str(exc)},
                        "sequence": 1,
                        "status": "FAIL_CLOSED",
                    },
                )
            except BaseException:
                pass
            return 2
        finally:
            try:
                self._release_owned()
            except BaseException:
                self._terminal = False


class RecoveryProcess:
    def __init__(
        self,
        *,
        pid: int,
        pidfd: int,
        pidfd_method: str,
        connection: socket.socket,
        nonce: str,
        actor: Mapping[str, object],
    ) -> None:
        self.pid = pid
        self.pidfd = pidfd
        self.pidfd_method = pidfd_method
        self.connection = connection
        self.nonce = nonce
        self.actor = dict(actor)
        self._waited = False
        self._terminal_attempted = False

    def terminal(self, action: str, payload: Mapping[str, object]) -> dict[str, object]:
        if self._terminal_attempted:
            raise RecoveryProtocolError(
                "TERMINAL_ALREADY_ATTEMPTED",
                "recovery terminal control cannot be retried",
            )
        self._terminal_attempted = True
        return _terminal_exchange(
            connection=self.connection,
            nonce=self.nonce,
            actor=self.actor,
            action=action,
            payload=payload,
        )

    def wait(self) -> int:
        if self._waited:
            raise RecoveryProtocolError("PROCESS_ALREADY_WAITED", "recovery cannot be waited twice")
        _pid, status = os.waitpid(self.pid, 0)
        self._waited = True
        if os.WIFEXITED(status):
            return os.WEXITSTATUS(status)
        return 128 + os.WTERMSIG(status)

    def close(self) -> None:
        self.connection.close()
        os.close(self.pidfd)


def _terminal_exchange(
    *,
    connection: socket.socket,
    nonce: str,
    actor: Mapping[str, object],
    action: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    broker.send_frame(
        connection,
        {
            "schema_version": REQUEST_SCHEMA,
            "action": action,
            "nonce": nonce,
            "payload": dict(payload),
            "sequence": 1,
        },
    )
    response = broker.receive_frame(connection)
    record = response.record
    if (
        record.get("schema_version") != RESPONSE_SCHEMA
        or record.get("status") != "PASS"
        or record.get("action") != action
        or record.get("nonce") != nonce
        or record.get("sequence") != 1
        or record.get("actor") != actor
    ):
        raise RecoveryProtocolError(
            "RESPONSE_IDENTITY_DRIFT",
            "recovery response identity drifted",
        )
    result = record.get("result")
    if type(result) is not dict:
        raise RecoveryProtocolError(
            "RESPONSE_IDENTITY_DRIFT",
            "recovery result is not one object",
        )
    checked = dict(result)
    if action == "DISARM":
        if (
            checked.get("schema_version") != DISARM_OBSERVATION_SCHEMA
            or checked.get("actor") != actor
            or checked.get("disarm_intent_sha256")
            != payload.get("disarm_intent_sha256")
            or checked.get("state") != "DISARM_PREPARED_AWAITING_ACK"
            or type(checked.get("unused_closeout_identity")) is not dict
        ):
            raise RecoveryProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "prepared recovery disarm response identity drifted",
            )
        broker.send_frame(
            connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "DISARM_ACK",
                "nonce": nonce,
                "payload": dict(payload),
                "sequence": 2,
            },
        )
        checked["state"] = "DISARMED_WITHOUT_TAKEOVER"
    return checked


class DetachedRecoveryProcess:
    """Supervisor-side pidfd/control handle for a broker-forked recovery actor."""

    def __init__(
        self,
        *,
        pidfd: int,
        connection: socket.socket,
        nonce: str,
        actor: Mapping[str, object],
        pidfd_method: str,
        source_identity: Mapping[str, object],
    ) -> None:
        actor_pid = actor.get("pid")
        if isinstance(actor_pid, bool) or not isinstance(actor_pid, int):
            raise RecoveryProtocolError(
                "ACTOR_IDENTITY_DRIFT",
                "detached recovery actor PID is invalid",
            )
        self.pid = actor_pid
        self.pidfd = pidfd
        self.connection = connection
        self.nonce = nonce
        self.actor = dict(actor)
        self.pidfd_method = pidfd_method
        self.source_identity = dict(source_identity)
        self._exit_proved = False
        self._terminal_attempted = False

    def terminal(
        self,
        action: str,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        if self._terminal_attempted:
            raise RecoveryProtocolError(
                "TERMINAL_ALREADY_ATTEMPTED",
                "detached recovery terminal control cannot be retried",
            )
        self._terminal_attempted = True
        return _terminal_exchange(
            connection=self.connection,
            nonce=self.nonce,
            actor=self.actor,
            action=action,
            payload=payload,
        )

    def prove_exit(self, *, timeout_milliseconds: int = 5000) -> None:
        if self._exit_proved:
            raise RecoveryProtocolError(
                "PROCESS_ALREADY_WAITED",
                "detached recovery exit cannot be proved twice",
            )
        poller = select.poll()
        poller.register(self.pidfd, select.POLLIN | select.POLLHUP)
        if not poller.poll(timeout_milliseconds):
            raise RecoveryProtocolError(
                "RECOVERY_EXIT_NOT_PROVED",
                "detached recovery pidfd did not report terminal exit",
            )
        self._exit_proved = True

    def close(self) -> None:
        self.connection.close()
        os.close(self.pidfd)


def attach_broker_forked_recovery(
    handoff: Mapping[str, object],
    descriptors: tuple[int, ...],
) -> DetachedRecoveryProcess:
    """Accept only one exact broker-produced recovery actor handoff."""

    expected = {
        "actor",
        "broker_actor",
        "control_descriptor_identity",
        "nonce",
        "pidfd_method",
        "prepared_recovery_identity",
        "role",
        "role_source_identity",
        "schema_version",
    }
    if set(handoff) != expected or len(descriptors) != 2:
        for descriptor in descriptors:
            os.close(descriptor)
        raise RecoveryProtocolError(
            "BROKER_HANDOFF_SHAPE_DRIFT",
            "broker recovery handoff shape or FD count differs",
        )
    control_fd, pidfd = descriptors
    connection: socket.socket | None = None
    try:
        actor = handoff["actor"]
        broker_actor = handoff["broker_actor"]
        source_identity = handoff["role_source_identity"]
        prepared_identity = handoff["prepared_recovery_identity"]
        control_identity = handoff["control_descriptor_identity"]
        if (
            handoff["schema_version"] != OWNER_HANDOFF_SCHEMA
            or handoff["role"] != PACKAGE_ROLE
            or type(actor) is not dict
            or set(actor) != {"schema_version", "pid", "pid_starttime", "uid"}
            or actor["schema_version"] != ACTOR_SCHEMA
            or actor["uid"] != os.getuid()
            or actor["pid_starttime"]
            != broker.process_starttime(int(actor["pid"]))
            or type(broker_actor) is not dict
            or type(source_identity) is not dict
            or set(source_identity) != {"sha256", "size_bytes"}
            or type(prepared_identity) is not dict
            or set(prepared_identity) != {"sha256", "size_bytes"}
            or type(control_identity) is not dict
            or control_identity != broker._identity(control_fd)  # noqa: SLF001
            or not isinstance(handoff["pidfd_method"], str)
        ):
            raise RecoveryProtocolError(
                "BROKER_HANDOFF_IDENTITY_DRIFT",
                "broker recovery handoff identity differs",
            )
        nonce = _nonce(handoff["nonce"])
        connection = socket.socket(fileno=control_fd)
        broker._socket_type(connection)  # noqa: SLF001
        return DetachedRecoveryProcess(
            pidfd=pidfd,
            connection=connection,
            nonce=nonce,
            actor=actor,
            pidfd_method=handoff["pidfd_method"],
            source_identity=source_identity,
        )
    except BaseException:
        if connection is None:
            os.close(control_fd)
        else:
            connection.close()
        os.close(pidfd)
        raise


def prepared_recovery_identity(
    prepared_result: Mapping[str, object],
) -> dict[str, object]:
    """Bind the exact PREPARE_RECOVERY result without inventing a path."""

    if prepared_result.get("schema_version") == PREPARED_RECOVERY_SCHEMA:
        _exact_keys(
            prepared_result,
            {"schema_version", "closeout", "lock"},
            label="prepared recovery result",
        )
        for label in ("closeout", "lock"):
            transfer = prepared_result[label]
            if type(transfer) is not dict or set(transfer) != {
                "extent",
                "ownership_handoff",
                "reservation_record",
            }:
                raise RecoveryProtocolError(
                    "FRAME_SHAPE_MISMATCH",
                    f"prepared recovery {label} transfer differs",
                )
            broker.validate_prepared_extent(transfer["extent"])
    else:
        _exact_keys(
            prepared_result,
            {"closeout_extent", "lock_extent"},
            label="prepared recovery result",
        )
        broker.validate_prepared_extent(
            prepared_result["closeout_extent"]
        )
        broker.validate_prepared_extent(prepared_result["lock_extent"])
    raw = broker.canonical_json_bytes(dict(prepared_result))
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _spawn_recovery(
    *,
    broker_process: BrokerLivenessProtocol,
    prepared_result: Mapping[str, object],
    descriptors: tuple[int, ...],
    nonce: str | None = None,
    native_helper: broker.NativeHelperProtocol | None = None,
) -> RecoveryProcess:
    if len(descriptors) != 3:
        raise RecoveryProtocolError("FD_COUNT_MISMATCH", "recovery requires parent, closeout, and lock FDs")
    prepared_recovery_identity(prepared_result)
    if prepared_result.get("schema_version") == PREPARED_RECOVERY_SCHEMA:
        closeout_record = cast(
            Mapping[str, object],
            prepared_result["closeout"],
        )
        lock_record = cast(
            Mapping[str, object],
            prepared_result["lock"],
        )
        closeout_extent = closeout_record["extent"]
        lock_extent = lock_record["extent"]
    else:
        closeout_extent = prepared_result["closeout_extent"]
        lock_extent = prepared_result["lock_extent"]
    _validate_recovery_purposes(
        broker.validate_prepared_extent(closeout_extent),
        broker.validate_prepared_extent(lock_extent),
    )
    closeout_parent_fd, closeout_fd, lock_fd = descriptors
    expected_peer = broker.process_identity()
    session_nonce = secrets.token_hex(32) if nonce is None else _nonce(nonce)
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    broker_pidfd = os.dup(broker_process.pidfd)
    pid = os.fork()
    if pid == 0:
        parent.close()
        code = 2
        try:
            server = RecoveryServer(
                child,
                nonce=session_nonce,
                expected_peer=expected_peer,
                broker_actor=broker_process.actor,
                broker_pidfd=broker_pidfd,
                closeout_extent=closeout_extent,
                closeout_parent_fd=closeout_parent_fd,
                closeout_fd=closeout_fd,
                lock_extent=lock_extent,
                lock_fd=lock_fd,
            )
            retained_descriptors = {
                child.fileno(),
                broker_pidfd,
                closeout_parent_fd,
                closeout_fd,
                lock_fd,
            }
            if native_helper is not None:
                # Recovery is the package-pinned capability writer for one
                # fixed no-replace closeout leaf.  A deny-all-write Landlock
                # policy would forbid that sole renameat2 duty.  Instead, the
                # pinned native close_range primitive removes every ambient
                # descriptor (including stdio); only the fixed control,
                # broker-pidfd, closeout-parent/staging, and once-lock
                # capabilities survive initialization.
                native_helper.close_range_allowlist(
                    sorted(retained_descriptors)
                )
            broker.close_unlisted_descriptors(retained_descriptors)
            code = server.run()
        except BaseException:
            code = 2
        finally:
            try:
                child.close()
            except BaseException:
                pass
        os._exit(code)
    child_close_attempted = False
    parent_close_attempted = False
    parent_descriptor_entries = [
        ("recovery broker pidfd copy", broker_pidfd),
        *[
            (f"recovery transferred descriptor {index}", descriptor)
            for index, descriptor in enumerate(descriptors)
        ],
    ]
    parent_descriptor_close_attempted = [
        False for _entry in parent_descriptor_entries
    ]

    def close_parent_descriptors() -> None:
        primary: BaseException | None = None
        for index, (label, descriptor) in enumerate(
            parent_descriptor_entries
        ):
            if parent_descriptor_close_attempted[index]:
                continue
            parent_descriptor_close_attempted[index] = True
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        f"{label} close also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if primary is not None:
            raise primary

    pidfd = -1
    pidfd_method = ""
    try:
        child_close_attempted = True
        child.close()
        close_parent_descriptors()
        pidfd, pidfd_method = broker.open_pidfd(pid)
        ready = broker.receive_frame(parent)
        record = ready.record
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action") != "READY"
            or record.get("nonce") != session_nonce
            or record.get("sequence") != 0
        ):
            raise RecoveryProtocolError("READY_IDENTITY_DRIFT", "recovery READY identity drifted")
        actor = record.get("actor")
        if type(actor) is not dict or actor.get("pid") != pid or actor.get("pid_starttime") != broker.process_starttime(pid):
            raise RecoveryProtocolError("READY_IDENTITY_DRIFT", "recovery actor identity drifted")
        process = RecoveryProcess(
            pid=pid,
            pidfd=pidfd,
            pidfd_method=pidfd_method,
            connection=parent,
            nonce=session_nonce,
            actor=dict(actor),
        )
        pidfd = -1
        return process
    except BaseException as exc:
        if not child_close_attempted:
            child_close_attempted = True
            broker.preserve_spawn_cleanup_failure(
                exc,
                label="recovery child socket",
                cleanup=child.close,
            )
        broker.preserve_spawn_cleanup_failure(
            exc,
            label="recovery parent capabilities",
            cleanup=close_parent_descriptors,
        )
        if not parent_close_attempted:
            parent_close_attempted = True
            broker.preserve_spawn_cleanup_failure(
                exc,
                label="recovery parent control",
                cleanup=parent.close,
            )
        broker.terminate_and_reap_spawned_child(pid, primary=exc)
        if pidfd >= 0:
            owned_pidfd = pidfd
            pidfd = -1
            broker.preserve_spawn_cleanup_failure(
                exc,
                label="recovery pidfd",
                cleanup=lambda: os.close(owned_pidfd),
            )
        raise


def spawn_persistent_recovery(
    *,
    broker_process: BrokerLivenessProtocol,
    prepared_result: Mapping[str, object],
    descriptors: tuple[int, ...],
    package_authorization: broker.PackageRoleAuthorizationProtocol,
    nonce: str | None = None,
    native_helper: broker.NativeHelperProtocol | None = None,
) -> RecoveryProcess:
    """Start the package-pinned recovery role after independent verification.

    Package authorization is checked before any descriptor duplication,
    process creation, or ownership transfer.  Rejection therefore leaves the
    caller's three prepared descriptors untouched.
    """

    package_authorization.require_verified_role(PACKAGE_ROLE)
    if native_helper is None:
        raise RecoveryProtocolError(
            "NATIVE_HELPER_REQUIRED",
            "formal recovery requires the package-pinned Landlock helper",
        )
    return _spawn_recovery(
        broker_process=broker_process,
        prepared_result=prepared_result,
        descriptors=descriptors,
        nonce=nonce,
        native_helper=native_helper,
    )


def spawn_recovery_for_test(
    *,
    broker_process: BrokerLivenessProtocol,
    prepared_result: Mapping[str, object],
    descriptors: tuple[int, ...],
    nonce: str | None = None,
) -> RecoveryProcess:
    """Transfer prepared FDs into a zero-authority process-level recovery role."""

    return _spawn_recovery(
        broker_process=broker_process,
        prepared_result=prepared_result,
        descriptors=descriptors,
        nonce=nonce,
        native_helper=None,
    )


def disarm_intent_sha256(record: Mapping[str, object]) -> str:
    return hashlib.sha256(broker.canonical_json_bytes(dict(record))).hexdigest()


__all__ = [
    "ACTOR_SCHEMA",
    "DISARM_OBSERVATION_SCHEMA",
    "LOCK_CONSUMPTION_SCHEMA",
    "PACKAGE_ROLE",
    "REQUEST_SCHEMA",
    "RESPONSE_SCHEMA",
    "RecoveryProcess",
    "DetachedRecoveryProcess",
    "RecoveryProtocolError",
    "RecoveryServer",
    "TAKEOVER_CLOSEOUT_SCHEMA",
    "disarm_intent_sha256",
    "attach_broker_forked_recovery",
    "prepared_recovery_identity",
    "spawn_persistent_recovery",
    "spawn_recovery_for_test",
]
