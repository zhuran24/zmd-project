#!/usr/bin/env python3
"""Independent AB16 outer lock guardian and finite-containment protocol.

The guardian is a package-pinned runtime role in a cgroup distinct from the
whole-campaign outer unit.  It owns no controller, baseline, solver, Gate1, arm
or claim logic.  Its only irreversible capabilities are:

* receive duplicate descriptors for the exact three already-held formal locks
  over one ``AF_UNIX/SOCK_SEQPACKET`` connection;
* publish its own non-authorizing ready receipt through the existing
  ``ReceiptStore`` owner;
* independently validate the external formal selection;
* retain its lock copies while a finite, authority-derived residual-runtime
  port performs exact containment/absence replay;
* close its local copies exactly once after validated absence.

SCM_RIGHTS preserves the same open file descriptions, so the supervisor keeps
its original descriptors while the guardian holds duplicates.  Normal release
closes guardian copies first; the supervisor must then prove guardian
unit/cgroup/PID absence before closing its own copies.  A supervisor-side death
permanently removes success eligibility and leaves this guardian in
containment hold.  Simultaneous loss of both separately-cgrouped holders or a
reboot is the explicit external platform assumption recorded by the formal
launch authority; it can never yield a successful closeout.
"""

from __future__ import annotations

from array import array
from collections.abc import Callable, Mapping
import ctypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import importlib
import math
import os
from pathlib import Path
import select
import socket
import stat
import struct
import sys
import time
from typing import Any, Protocol

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import ab16_formal_launch_validator_v1 as launch_validator
from docs.research.noncert_cuts_ab16_20260724 import ab16_formal_success_verifier_v1 as success_verifier
from docs.research.noncert_cuts_ab16_20260724 import ab16_outer_closeout_state_v1 as closeout_state


LOCK_HANDOFF_SCHEMA = "noncert-cuts-ab16-outer-guardian-lock-handoff-v1"
GUARDIAN_ACTIVATION_SCHEMA = "noncert-cuts-ab16-outer-guardian-selection-activation-v1"
GUARDIAN_LEDGER_UPDATE_SCHEMA = "noncert-cuts-ab16-outer-guardian-ledger-update-v1"
GUARDIAN_PRESELECTION_CANCEL_SCHEMA = "noncert-cuts-ab16-outer-guardian-preselection-cancel-v1"
GUARDIAN_PRESELECTION_ACK_SCHEMA = "noncert-cuts-ab16-outer-guardian-preselection-ack-v1"
GUARDIAN_TERMINAL_SCHEMA = "noncert-cuts-ab16-outer-guardian-terminal-command-v1"
GUARDIAN_LOCK_CLOSE_SCHEMA = "noncert-cuts-ab16-outer-guardian-lock-close-v1"

MAX_FRAME_BYTES = 1024 * 1024
LOCK_COUNT = len(closeout_state.LOCK_PATHS)
PEER_CREDENTIAL_SIZE = struct.calcsize("3i")
MAX_CONTROL_POLL_SECONDS = 1.0
MAX_UNIX_PATHNAME_BYTES = 107
RENAME_NOREPLACE = 1
INOTIFY_MUTATION_MASK = (
    0x00000002  # IN_MODIFY
    | 0x00000004  # IN_ATTRIB
    | 0x00000008  # IN_CLOSE_WRITE
    | 0x00000040  # IN_MOVED_FROM
    | 0x00000080  # IN_MOVED_TO
    | 0x00000100  # IN_CREATE
    | 0x00000200  # IN_DELETE
    | 0x00000400  # IN_DELETE_SELF
    | 0x00000800  # IN_MOVE_SELF
    | 0x00002000  # IN_UNMOUNT
)
INOTIFY_LEAF_MUTATION_MASK = (
    0x00000002  # IN_MODIFY
    | 0x00000004  # IN_ATTRIB
    | 0x00000008  # IN_CLOSE_WRITE
    | 0x00000400  # IN_DELETE_SELF
    | 0x00000800  # IN_MOVE_SELF
    | 0x00002000  # IN_UNMOUNT
)
INOTIFY_SELF_MUTATION_MASK = (
    0x00000004  # IN_ATTRIB
    | 0x00000400  # IN_DELETE_SELF
    | 0x00000800  # IN_MOVE_SELF
    | 0x00002000  # IN_UNMOUNT
)

HANDOFF_FIELDS = frozenset(
    {
        "authority_scope",
        "campaign_root_identity",
        "control_socket_identity",
        "dual_holder_platform_assumption",
        "formal_admission_identity",
        "guardian_process_identity",
        "guardian_runtime_identity",
        "guardian_unit_identity",
        "lock_identities",
        "manager_epoch",
        "package_id",
        "schema_version",
        "status",
        "supervisor_process_identity",
    }
)

ACTIVATION_FIELDS = frozenset(
    {
        "campaign_root_identity",
        "formal_selection_identity",
        "guardian_ready_identity",
        "package_id",
        "schema_version",
        "status",
    }
)

PRESELECTION_CANCEL_FIELDS = frozenset(
    {
        "authority_scope",
        "campaign_root_identity",
        "formal_admission_identity",
        "guardian_ready_identity",
        "lock_identities",
        "package_id",
        "reason",
        "schema_version",
        "status",
    }
)

PRESELECTION_ACK_FIELDS = frozenset(
    {
        "authorizations",
        "campaign_root_identity",
        "close_effect",
        "errors",
        "formal_admission_identity",
        "formal_selection_absent",
        "guardian_ready_identity",
        "outcome",
        "outer_absence",
        "package_id",
        "reason",
        "schema_version",
        "status",
    }
)

TERMINAL_FIELDS = frozenset(
    {
        "campaign_root_identity",
        "command",
        "formal_selection_identity",
        "ledger",
        "ledger_message_identity",
        "package_id",
        "previous_message_identity",
        "reason",
        "schema_version",
        "status",
    }
)

LEDGER_UPDATE_FIELDS = frozenset(
    {
        "campaign_root_identity",
        "formal_selection_identity",
        "ledger",
        "ledger_message_identity",
        "package_id",
        "phase",
        "previous_message_identity",
        "schema_version",
        "sequence",
        "status",
    }
)

LEDGER_PHASES = closeout_state.GUARDIAN_LEDGER_PHASES

LOCK_CLOSE_FIELDS = frozenset(
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


class GuardianProtocolError(RuntimeError):
    """A guardian identity, protocol, lock, or containment invariant failed."""


class GuardianPeerClosed(GuardianProtocolError):
    """The supervisor connection closed before a terminal command was proved."""


class GuardianTerminationLatched(GuardianProtocolError):
    """SIGINT/SIGTERM was recorded while the guardian still held state."""


class _OwnedDescriptor:
    """Own one descriptor until it is explicitly transferred or closed."""

    __slots__ = ("_descriptor",)

    def __init__(self) -> None:
        self._descriptor: int | None = None

    @property
    def descriptor(self) -> int:
        if self._descriptor is None:
            raise RuntimeError("descriptor ownership is absent")
        return self._descriptor

    @property
    def owned(self) -> bool:
        return self._descriptor is not None

    def acquire(self, descriptor: int) -> int:
        if self._descriptor is not None:
            raise RuntimeError("descriptor ownership is already present")
        self._descriptor = descriptor
        return descriptor

    def release(self) -> int:
        descriptor = self.descriptor
        self._descriptor = None
        return descriptor

    def close(self) -> BaseException | None:
        descriptor = self.release()
        try:
            os.close(descriptor)
        except BaseException as exc:
            return exc
        return None

    def close_preserving(self, primary: BaseException) -> None:
        if self._descriptor is None:
            return
        cleanup_error = self.close()
        if cleanup_error is not None:
            primary.add_note(
                "descriptor cleanup failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )


def _closeout_helper_module() -> Any:
    """Load the existing owner; the formal loader already installs these aliases."""

    sys.modules.setdefault("ab16_authority_v2", authority)
    sys.modules.setdefault("ab16_outer_closeout_state_v1", closeout_state)
    return importlib.import_module(
        "docs.research.noncert_cuts_ab16_20260724."
        "ab16_outer_refunit_closeout_v1"
    )


class ResidualRuntimePort(Protocol):
    """Campaign-specific adapter backed by the existing closeout/helper owner."""

    def validate_ledger(self, value: Mapping[str, object]) -> Mapping[str, object]:
        """Return the same finite residual-runtime ledger after closed validation."""

    def contain_exact_once(self, ledger: Mapping[str, object]) -> Mapping[str, object]:
        """Attempt only pre-authorized exact stop/reset effects once."""

    def observe_exact_absence(self, ledger: Mapping[str, object]) -> Mapping[str, object]:
        """Observe only the exact unit/cgroup/PID-starttime ledger."""

    def validate_exact_absence(
        self,
        ledger: Mapping[str, object],
        observation: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Reject any incomplete, extra, or identity-drifted absence result."""


class WaitPort(Protocol):
    def __call__(self, seconds: float) -> None:
        """Wait without changing runtime or reference state."""


class PidfdOpenPort(Protocol):
    def __call__(self, pid: int, flags: int = 0) -> int:
        """Open one pidfd for the exact live supervisor PID."""


class PidfdExitPort(Protocol):
    def __call__(self, descriptor: int) -> bool:
        """Return true only after the process represented by one pidfd exited."""


@dataclass(frozen=True)
class ReceivedFrame:
    file_descriptors: tuple[int, ...]
    identity: dict[str, object]
    peer_pid: int
    record: dict[str, Any]


@dataclass
class GuardianEffects:
    """Monotone guardian-local proof/effect state."""

    handoff_attempted: bool = False
    handoff_received: bool = False
    ready_publication: closeout_state.PublicationEffect = field(
        default_factory=closeout_state.PublicationEffect
    )
    selection_activated: bool = False
    containment_attempted: bool = False
    terminal_command_received: bool = False
    supervisor_connection_closed: bool = False
    lock_close_attempted: bool = False
    lock_close_returned: bool = False
    success_eligible: bool = False
    irreversible_incomplete: bool = False
    errors: list[dict[str, str]] = field(default_factory=list)

    def fail(self, code: str, error: BaseException | str) -> dict[str, str]:
        item = closeout_state.failure(code, error)
        if item not in self.errors:
            self.errors.append(item)
        self.success_eligible = False
        self.irreversible_incomplete = True
        return item


SUPERVISOR_DEATH_FIELDS = frozenset(
    {
        "pidfd_exit_ready",
        "process_identity",
        "schema_version",
        "status",
    }
)


def pidfd_reports_exit(descriptor: int) -> bool:
    """Observe Linux pidfd readability without re-resolving a numeric PID."""

    if type(descriptor) is not int or descriptor < 0:
        raise GuardianProtocolError("supervisor pidfd is malformed")
    poller = select.poll()
    poller.register(descriptor, select.POLLIN | select.POLLERR | select.POLLHUP)
    events = poller.poll(0)
    if not events:
        return False
    if len(events) != 1 or events[0][0] != descriptor:
        raise GuardianProtocolError("supervisor pidfd poll identity drifted")
    flags = events[0][1]
    if flags & select.POLLNVAL:
        raise GuardianProtocolError("supervisor pidfd became invalid")
    if flags & select.POLLIN == 0:
        raise GuardianProtocolError("supervisor pidfd reported a non-exit event")
    return True


def open_supervisor_pidfd(pid: int, flags: int = 0) -> int:
    """Open a Linux pidfd through the external libc/kernel platform boundary."""

    if type(pid) is not int or pid <= 0 or flags != 0:
        raise GuardianProtocolError("supervisor pidfd open arguments are malformed")
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "pidfd_open", None)
    if function is None:
        raise GuardianProtocolError("external libc lacks pidfd_open")
    function.argtypes = (ctypes.c_int, ctypes.c_uint)
    function.restype = ctypes.c_int
    descriptor = int(function(pid, flags))
    if descriptor < 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    try:
        os.set_inheritable(descriptor, False)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


class SupervisorDeathWitness:
    """A non-racy pidfd bound to the handoff's exact PID/starttime identity."""

    def __init__(
        self,
        process_identity: Mapping[str, object],
        *,
        process_starttime_reader: Callable[[int], int],
        pidfd_opener: PidfdOpenPort = open_supervisor_pidfd,
        exit_observer: PidfdExitPort = pidfd_reports_exit,
    ) -> None:
        identity = launch_validator.validate_process_identity(
            process_identity,
            "guardian supervisor death witness",
        )
        pid = identity["pid"]
        if process_starttime_reader(pid) != identity["starttime"]:
            raise GuardianProtocolError(
                "supervisor identity drifted before pidfd acquisition"
            )
        descriptor = pidfd_opener(pid, 0)
        if type(descriptor) is not int or descriptor < 0:
            raise GuardianProtocolError("supervisor pidfd acquisition is malformed")
        try:
            if process_starttime_reader(pid) != identity["starttime"]:
                raise GuardianProtocolError(
                    "supervisor identity drifted across pidfd acquisition"
                )
        except BaseException:
            os.close(descriptor)
            raise
        self.process_identity = identity
        self.descriptor = descriptor
        self.exit_observer = exit_observer
        self.death_proved = False
        self.close_attempted = False
        self.close_returned = False

    def observe(self) -> dict[str, object] | None:
        """Return one monotone proof only when the exact pidfd reports exit."""

        if self.death_proved:
            return {
                "pidfd_exit_ready": True,
                "process_identity": dict(self.process_identity),
                "schema_version": "noncert-cuts-ab16-supervisor-death-v1",
                "status": "SUPERVISOR_DEATH_PROVED",
            }
        if not self.exit_observer(self.descriptor):
            return None
        self.death_proved = True
        return {
            "pidfd_exit_ready": True,
            "process_identity": dict(self.process_identity),
            "schema_version": "noncert-cuts-ab16-supervisor-death-v1",
            "status": "SUPERVISOR_DEATH_PROVED",
        }

    def arm_record(self) -> dict[str, object]:
        if self.close_attempted:
            raise GuardianProtocolError("supervisor pidfd is no longer armed")
        return launch_validator.validate_supervisor_death_watch(
            {
                "method": "linux-pidfd-open-v1",
                "process_identity": dict(self.process_identity),
                "status": "ARMED",
            },
            expected_process_identity=self.process_identity,
        )

    def close_once(self) -> None:
        if self.close_attempted:
            raise GuardianProtocolError("supervisor pidfd cannot be closed twice")
        self.close_attempted = True
        os.close(self.descriptor)
        self.close_returned = True


def _closed(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise GuardianProtocolError(f"{label} field set drifted")
    return dict(value)


def _message_identity(raw: bytes) -> dict[str, object]:
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def _ledger_identity(ledger: Mapping[str, object]) -> dict[str, object]:
    checked = closeout_state.validate_frozen_ledger(ledger)
    return _message_identity(authority.canonical_json(checked))


def _ledger_items(ledger: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    checked = closeout_state.validate_frozen_ledger(ledger)
    return {
        f"{item['source']}:{item['slot']}": item
        for item in [checked["outer"], *checked["children"]]
    }


def _canonical_record(value: Mapping[str, object], label: str) -> tuple[dict[str, Any], bytes]:
    record = dict(value)
    raw = authority.canonical_json(record)
    try:
        replay = authority.strict_loads(raw, label)
    except Exception as exc:
        raise GuardianProtocolError(f"{label} is not strict canonical JSON: {exc}") from exc
    if type(replay) is not dict or replay != record:
        raise GuardianProtocolError(f"{label} canonical replay drifted")
    return dict(replay), raw


def validate_supervisor_death_observation(
    value: object,
    *,
    expected_process_identity: Mapping[str, object],
) -> dict[str, object]:
    """Validate the sole pidfd-backed supervisor-death projection."""

    record = _closed(value, SUPERVISOR_DEATH_FIELDS, "supervisor death observation")
    process = launch_validator.validate_process_identity(
        record["process_identity"],
        "supervisor death process",
    )
    expected = launch_validator.validate_process_identity(
        expected_process_identity,
        "expected supervisor death process",
    )
    if (
        record["schema_version"] != "noncert-cuts-ab16-supervisor-death-v1"
        or record["status"] != "SUPERVISOR_DEATH_PROVED"
        or record["pidfd_exit_ready"] is not True
        or process != expected
    ):
        raise GuardianProtocolError("supervisor death observation drifted")
    result = dict(record)
    result["process_identity"] = process
    return result


def _socket_type(connection: socket.socket) -> None:
    if connection.family != socket.AF_UNIX:
        raise GuardianProtocolError("guardian connection is not AF_UNIX")
    if connection.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_SEQPACKET:
        raise GuardianProtocolError("guardian connection is not SOCK_SEQPACKET")


def _peer_pid(connection: socket.socket) -> int:
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, PEER_CREDENTIAL_SIZE)
    if len(raw) != PEER_CREDENTIAL_SIZE:
        raise GuardianProtocolError("guardian peer credentials are malformed")
    pid, uid, _gid = struct.unpack("3i", raw)
    if pid <= 0 or uid != os.getuid():
        raise GuardianProtocolError("guardian peer PID/UID identity drifted")
    return pid


def read_process_starttime(pid: int) -> int:
    """Read one Linux PID starttime from a single procfs descriptor."""

    if type(pid) is not int or pid <= 0:
        raise GuardianProtocolError("guardian process PID is malformed")
    path = Path(f"/proc/{pid}/stat")
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        raw = os.read(descriptor, 1 << 16)
        if os.read(descriptor, 1):
            raise GuardianProtocolError("guardian proc stat exceeds the fixed limit")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        raise GuardianProtocolError("guardian proc stat identity drifted")
    closing = raw.rfind(b")")
    if closing <= 0:
        raise GuardianProtocolError("guardian proc stat is malformed")
    fields = raw[closing + 2 :].decode("ascii", "strict").split()
    if len(fields) <= 19 or not fields[19].isdigit() or int(fields[19]) <= 0:
        raise GuardianProtocolError("guardian proc starttime is malformed")
    return int(fields[19])


def current_control_group() -> str:
    """Return this process' sole unified cgroup path."""

    descriptor = os.open(
        "/proc/self/cgroup",
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        raw = os.read(descriptor, 1 << 16)
        if os.read(descriptor, 1):
            raise GuardianProtocolError("guardian cgroup record exceeds the fixed limit")
    finally:
        os.close(descriptor)
    lines = raw.decode("ascii", "strict").splitlines()
    if len(lines) != 1 or not lines[0].startswith("0::"):
        raise GuardianProtocolError("guardian is not in one unified cgroup")
    try:
        return closeout_state.validate_control_group(lines[0][3:])
    except closeout_state.CloseoutStateError as exc:
        raise GuardianProtocolError(str(exc)) from exc


def control_socket_identity(path: Path | str) -> dict[str, object]:
    """Return the exact runtime identity of one owned AF_UNIX socket path."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    parent = _OwnedDescriptor()
    try:
        parent.acquire(_open_directory_no_symlinks(absolute.parent))
        result = _control_socket_identity_at(
            parent.descriptor,
            absolute,
        )
    except BaseException as exc:
        parent.close_preserving(exc)
        raise
    close_error = parent.close()
    if close_error is not None:
        raise GuardianProtocolError(
            "guardian control parent cleanup failed after identity read"
        ) from close_error
    return result


def _open_directory_no_symlinks(path: Path) -> int:
    """Open one absolute directory through descriptor-relative no-follow steps."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    if (
        not absolute.is_absolute()
        or not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
    ):
        raise GuardianProtocolError(
            "guardian control requires absolute descriptor-relative directory opens"
        )
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    current = _OwnedDescriptor()
    try:
        current.acquire(os.open(absolute.anchor, flags))
        for component in absolute.parts[1:]:
            following = _OwnedDescriptor()
            following.acquire(
                os.open(component, flags, dir_fd=current.descriptor)
            )
            close_error = current.close()
            if close_error is not None:
                following.close_preserving(close_error)
                raise GuardianProtocolError(
                    "guardian control ancestor descriptor close failed"
                ) from close_error
            current = following
        return current.release()
    except BaseException as exc:
        current.close_preserving(exc)
        if isinstance(exc, OSError):
            raise GuardianProtocolError(
                f"guardian control parent is unavailable or symlinked: {absolute}"
            ) from exc
        raise


def _open_absolute_directory_chain(
    path: Path,
) -> tuple[tuple[_OwnedDescriptor, ...], tuple[str, ...]]:
    """Retain every no-follow descriptor in one absolute directory path."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    if (
        not absolute.is_absolute()
        or not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
    ):
        raise GuardianProtocolError(
            "guardian control requires an absolute retained directory chain"
        )
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    chain: list[_OwnedDescriptor] = []
    components = tuple(absolute.parts[1:])
    try:
        root = _OwnedDescriptor()
        chain.append(root)
        root.acquire(os.open(absolute.anchor, flags))
        for component in components:
            retained_parent = chain[-1].descriptor
            following = _OwnedDescriptor()
            chain.append(following)
            following.acquire(
                os.open(
                    component,
                    flags,
                    dir_fd=retained_parent,
                )
            )
    except BaseException as exc:
        for owned in reversed(chain):
            owned.close_preserving(exc)
        if isinstance(exc, OSError):
            raise GuardianProtocolError(
                "guardian control absolute directory chain is unavailable or symlinked"
            ) from exc
        raise
    return tuple(chain), components


def _require_retained_directory_chain_join(
    chain: tuple[_OwnedDescriptor, ...],
    components: tuple[str, ...],
    parent_descriptor: int,
) -> os.stat_result:
    """Reopen every retained child and join the terminal parent identity."""

    if len(chain) != len(components) + 1 or not chain:
        raise GuardianProtocolError(
            "guardian control retained directory chain shape drifted"
        )
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    for index, component in enumerate(components):
        current = _OwnedDescriptor()
        try:
            current.acquire(
                os.open(
                    component,
                    flags,
                    dir_fd=chain[index].descriptor,
                )
            )
            expected = os.fstat(chain[index + 1].descriptor)
            observed = os.fstat(current.descriptor)
            if (observed.st_dev, observed.st_ino) != (
                expected.st_dev,
                expected.st_ino,
            ):
                raise GuardianProtocolError(
                    "guardian control retained directory chain identity drifted"
                )
        except BaseException as exc:
            current.close_preserving(exc)
            if isinstance(exc, OSError):
                raise GuardianProtocolError(
                    "guardian control retained directory chain replay failed"
                ) from exc
            raise
        close_error = current.close()
        if close_error is not None:
            raise GuardianProtocolError(
                "guardian control retained directory chain replay cleanup failed"
            ) from close_error
    retained_parent = os.fstat(chain[-1].descriptor)
    anchored_parent = os.fstat(parent_descriptor)
    if (retained_parent.st_dev, retained_parent.st_ino) != (
        anchored_parent.st_dev,
        anchored_parent.st_ino,
    ):
        raise GuardianProtocolError(
            "guardian control retained directory chain terminal drifted"
        )
    return anchored_parent


def _close_owned_descriptor_chain(
    chain: tuple[_OwnedDescriptor, ...],
) -> BaseException | None:
    primary: BaseException | None = None
    for owned in reversed(chain):
        close_error = owned.close()
        if close_error is None:
            continue
        if primary is None:
            primary = close_error
        else:
            primary.add_note(
                "additional descriptor cleanup failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
    return primary


def _close_owned_descriptor_chain_preserving(
    chain: tuple[_OwnedDescriptor, ...],
    primary: BaseException,
) -> None:
    for owned in reversed(chain):
        owned.close_preserving(primary)


def _descriptor_socket_address(parent_descriptor: int, name: str) -> str:
    """Return a short kernel pathname alias for one already-open parent."""

    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\x00" in name
    ):
        raise GuardianProtocolError("guardian control socket basename is invalid")
    proc_descriptor = Path(f"/proc/self/fd/{parent_descriptor}")
    try:
        direct = os.fstat(parent_descriptor)
        through_proc = os.stat(proc_descriptor)
    except OSError as exc:
        raise GuardianProtocolError(
            "guardian control descriptor alias is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(direct.st_mode)
        or direct.st_dev != through_proc.st_dev
        or direct.st_ino != through_proc.st_ino
    ):
        raise GuardianProtocolError("guardian control descriptor alias drifted")
    address = f"{proc_descriptor}/{name}"
    if len(os.fsencode(address)) > MAX_UNIX_PATHNAME_BYTES:
        raise GuardianProtocolError(
            "guardian control descriptor alias exceeds AF_UNIX pathname capacity"
        )
    return address


def _require_directory_join(
    absolute: Path,
    anchored_descriptor: int,
) -> os.stat_result:
    current = _OwnedDescriptor()
    try:
        current.acquire(_open_directory_no_symlinks(absolute))
        expected = os.fstat(anchored_descriptor)
        observed = os.fstat(current.descriptor)
        if (observed.st_dev, observed.st_ino) != (
            expected.st_dev,
            expected.st_ino,
        ):
            raise GuardianProtocolError(
                "guardian control absolute parent identity drifted"
            )
    except BaseException as exc:
        current.close_preserving(exc)
        raise
    close_error = current.close()
    if close_error is not None:
        raise GuardianProtocolError(
            "guardian control parent join cleanup failed"
        ) from close_error
    return expected


def _open_retired_leaf_descriptor(
    parent_descriptor: int,
    retirement: Path,
    *,
    expected_identity: Mapping[str, object] | None,
) -> _OwnedDescriptor:
    """Retain the exact retired inode through terminal verification."""

    if not hasattr(os, "O_PATH"):
        raise GuardianProtocolError(
            "guardian control retired verification requires Linux O_PATH"
        )
    leaf = _OwnedDescriptor()
    try:
        leaf.acquire(
            os.open(
                retirement.name,
                os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_descriptor,
            )
        )
        observed = os.fstat(leaf.descriptor)
        if not _socket_stat_matches_identity(observed, expected_identity):
            raise GuardianProtocolError(
                "guardian control retired descriptor identity drifted"
            )
    except BaseException as exc:
        leaf.close_preserving(exc)
        if isinstance(exc, OSError):
            raise GuardianProtocolError(
                "guardian control retired descriptor is unavailable"
            ) from exc
        raise
    return leaf


def _open_terminal_mutation_watch(
    directory_chain: tuple[_OwnedDescriptor, ...],
    retired_descriptor: int,
) -> _OwnedDescriptor:
    """Watch the absolute directory chain and retired inode until linearization."""

    watch = _OwnedDescriptor()
    try:
        if not directory_chain:
            raise GuardianProtocolError(
                "guardian control mutation-watch directory chain is empty"
            )
        libc = ctypes.CDLL(None, use_errno=True)
        initialize = getattr(libc, "inotify_init1", None)
        add_watch = getattr(libc, "inotify_add_watch", None)
        if initialize is None or add_watch is None:
            raise GuardianProtocolError(
                "external libc lacks directory mutation monitoring"
            )
        initialize.argtypes = (ctypes.c_int,)
        initialize.restype = ctypes.c_int
        add_watch.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint32,
        )
        add_watch.restype = ctypes.c_int
        descriptor = int(initialize(os.O_NONBLOCK | os.O_CLOEXEC))
        if descriptor < 0:
            error_number = ctypes.get_errno()
            raise OSError(error_number, os.strerror(error_number))
        watch.acquire(descriptor)
        watched: list[tuple[str, int, int]] = [
            (
                "terminal parent" if index == len(directory_chain) - 1 else "ancestor",
                owned.descriptor,
                (
                    INOTIFY_MUTATION_MASK
                    if index == len(directory_chain) - 1
                    else INOTIFY_SELF_MUTATION_MASK
                ),
            )
            for index, owned in enumerate(directory_chain)
        ]
        watched.append(
            (
                "retired leaf",
                retired_descriptor,
                INOTIFY_LEAF_MUTATION_MASK,
            )
        )
        for label, anchored_descriptor, mask in watched:
            alias = Path(f"/proc/self/fd/{anchored_descriptor}")
            anchored = os.fstat(anchored_descriptor)
            through_alias = os.stat(alias)
            if (
                anchored.st_dev != through_alias.st_dev
                or anchored.st_ino != through_alias.st_ino
                or (
                    label != "retired leaf"
                    and not stat.S_ISDIR(anchored.st_mode)
                )
                or (
                    label == "retired leaf"
                    and not stat.S_ISSOCK(anchored.st_mode)
                )
            ):
                raise GuardianProtocolError(
                    f"guardian control mutation-watch {label} alias drifted"
                )
            watch_descriptor = int(
                add_watch(
                    watch.descriptor,
                    os.fsencode(alias),
                    mask,
                )
            )
            if watch_descriptor < 0:
                error_number = ctypes.get_errno()
                raise OSError(error_number, os.strerror(error_number))
    except BaseException as exc:
        watch.close_preserving(exc)
        if isinstance(exc, OSError):
            raise GuardianProtocolError(
                "guardian control directory mutation watch is unavailable"
            ) from exc
        raise
    return watch


def _require_directory_mutation_watch_quiet(
    watch_descriptor: int,
) -> None:
    """Linearize success only when the kernel reports no queued mutation."""

    try:
        observed = os.read(watch_descriptor, 1 << 16)
    except BlockingIOError:
        # The nonblocking EAGAIN observation is the success linearization
        # point.  Earlier leaf/topology snapshots remain current there because
        # every intervening mutation would have queued an inotify event.
        return
    except BaseException as exc:
        raise GuardianProtocolError(
            "guardian control directory mutation watch is uncertain"
        ) from exc
    if observed:
        raise GuardianProtocolError(
            "guardian control parent or leaf changed during final verification"
        )
    raise GuardianProtocolError(
        "guardian control directory mutation watch closed unexpectedly"
    )


def _control_socket_identity_at(
    parent_descriptor: int,
    absolute: Path,
) -> dict[str, object]:
    try:
        observed = os.stat(
            absolute.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise GuardianProtocolError(
            f"guardian control socket is unavailable: {absolute}"
        ) from exc
    if (
        not stat.S_ISSOCK(observed.st_mode)
        or stat.S_ISLNK(observed.st_mode)
        or observed.st_uid != os.getuid()
        or stat.S_IMODE(observed.st_mode) != 0o600
    ):
        raise GuardianProtocolError(
            "guardian control socket type/owner/mode drifted"
        )
    return launch_validator.validate_control_socket_identity(
        {
            "device": observed.st_dev,
            "inode": observed.st_ino,
            "mode": stat.S_IMODE(observed.st_mode),
            "path": str(absolute),
            "uid": observed.st_uid,
        }
    )


def _guardian_control_retirement_path(absolute: Path) -> Path:
    """Return the sole fixed terminal name for one control socket."""

    return absolute.with_name(f"{absolute.name}.retired")


def _rename_noreplace_at(
    parent_descriptor: int,
    source_name: str,
    destination_name: str,
) -> None:
    """Atomically move one directory entry without replacing another."""

    if (
        type(parent_descriptor) is not int
        or parent_descriptor < 0
        or type(source_name) is not str
        or not source_name
        or "/" in source_name
        or type(destination_name) is not str
        or not destination_name
        or "/" in destination_name
        or source_name == destination_name
    ):
        raise GuardianProtocolError(
            "guardian control retirement arguments are malformed"
        )
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        raise GuardianProtocolError(
            "external libc lacks atomic no-overwrite rename"
        )
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    function.restype = ctypes.c_int
    result = int(
        function(
            parent_descriptor,
            os.fsencode(source_name),
            parent_descriptor,
            os.fsencode(destination_name),
            RENAME_NOREPLACE,
        )
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _socket_stat_matches_identity(
    observed: os.stat_result,
    expected_identity: Mapping[str, object] | None,
) -> bool:
    return bool(
        stat.S_ISSOCK(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode)
        and observed.st_uid == os.getuid()
        and (
            expected_identity is None
            or (
                observed.st_dev == expected_identity["device"]
                and observed.st_ino == expected_identity["inode"]
                and (
                    "mode" not in expected_identity
                    or stat.S_IMODE(observed.st_mode)
                    == expected_identity["mode"]
                )
            )
        )
    )


def _directory_mutation_signature(
    observed: os.stat_result,
) -> tuple[int, ...]:
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_mode,
        observed.st_nlink,
        observed.st_uid,
        observed.st_gid,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


def _restore_unverified_retirement(
    parent_descriptor: int,
    absolute: Path,
    retirement: Path,
    primary: BaseException,
) -> None:
    """Best-effort no-overwrite restore; never delete either occupant."""

    try:
        _rename_noreplace_at(
            parent_descriptor,
            retirement.name,
            absolute.name,
        )
    except BaseException as restore_error:
        primary.add_note(
            "guardian control unverified node remains at the retirement "
            f"path because no-overwrite restore failed: "
            f"{type(restore_error).__name__}: {restore_error}"
        )
        return
    try:
        os.fsync(parent_descriptor)
    except BaseException as restore_error:
        primary.add_note(
            "guardian control unverified node was restored to the canonical "
            "path but restoration durability is uncertain: "
            f"{type(restore_error).__name__}: {restore_error}"
        )


def _retire_bound_socket_at(
    parent_descriptor: int,
    absolute: Path,
    *,
    expected_identity: Mapping[str, object] | None,
) -> dict[str, object]:
    retirement = _guardian_control_retirement_path(absolute)
    try:
        observed = os.stat(
            absolute.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise GuardianProtocolError(
            "guardian control socket is unavailable before retirement"
        ) from exc
    if not _socket_stat_matches_identity(observed, expected_identity):
        raise GuardianProtocolError(
            "guardian control socket identity drifted before retirement"
        )
    try:
        _rename_noreplace_at(
            parent_descriptor,
            absolute.name,
            retirement.name,
        )
    except BaseException as exc:
        raise GuardianProtocolError(
            "guardian control socket atomic retirement failed"
        ) from exc
    try:
        retired = os.stat(
            retirement.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except BaseException as exc:
        primary = GuardianProtocolError(
            "guardian control retired entry could not be verified"
        )
        primary.__cause__ = exc
        _restore_unverified_retirement(
            parent_descriptor,
            absolute,
            retirement,
            primary,
        )
        raise primary
    if not _socket_stat_matches_identity(retired, expected_identity):
        primary = GuardianProtocolError(
            "guardian control retirement captured an unverified node"
        )
        _restore_unverified_retirement(
            parent_descriptor,
            absolute,
            retirement,
            primary,
        )
        raise primary
    try:
        os.stat(
            absolute.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        pass
    except BaseException as exc:
        raise GuardianProtocolError(
            "guardian control canonical path absence is uncertain after retirement"
        ) from exc
    else:
        raise GuardianProtocolError(
            "guardian control canonical path was replaced during retirement"
        )
    try:
        os.fsync(parent_descriptor)
    except BaseException as exc:
        raise GuardianProtocolError(
            "guardian control retirement durability is uncertain"
        ) from exc
    _require_directory_join(
        absolute.parent,
        parent_descriptor,
    )
    directory_chain, directory_components = _open_absolute_directory_chain(
        absolute.parent
    )
    try:
        retired_leaf = _open_retired_leaf_descriptor(
            parent_descriptor,
            retirement,
            expected_identity=expected_identity,
        )
    except BaseException as exc:
        _close_owned_descriptor_chain_preserving(directory_chain, exc)
        raise
    try:
        mutation_watch = _open_terminal_mutation_watch(
            directory_chain,
            retired_leaf.descriptor,
        )
    except BaseException as exc:
        retired_leaf.close_preserving(exc)
        _close_owned_descriptor_chain_preserving(directory_chain, exc)
        raise
    try:
        joined_parent = _require_directory_join(
            absolute.parent,
            parent_descriptor,
        )
        retained_chain_parent = _require_retained_directory_chain_join(
            directory_chain,
            directory_components,
            parent_descriptor,
        )
        joined_parent_signature = _directory_mutation_signature(joined_parent)
        retained_chain_parent_signature = _directory_mutation_signature(
            retained_chain_parent
        )
        final_parent_before = _directory_mutation_signature(
            os.fstat(parent_descriptor)
        )
        if (
            final_parent_before != joined_parent_signature
            or final_parent_before != retained_chain_parent_signature
        ):
            raise GuardianProtocolError(
                "guardian control parent changed across final absolute chain join"
            )
        try:
            final_retired = os.stat(
                retirement.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            final_retired_at_descriptor = os.fstat(retired_leaf.descriptor)
        except BaseException as exc:
            raise GuardianProtocolError(
                "guardian control retired entry is unavailable after durability sync"
            ) from exc
        if (
            not _socket_stat_matches_identity(final_retired, expected_identity)
            or (
                final_retired.st_dev,
                final_retired.st_ino,
                final_retired.st_mode,
                final_retired.st_uid,
            )
            != (
                retired.st_dev,
                retired.st_ino,
                retired.st_mode,
                retired.st_uid,
            )
            or (
                final_retired_at_descriptor.st_dev,
                final_retired_at_descriptor.st_ino,
                final_retired_at_descriptor.st_mode,
                final_retired_at_descriptor.st_uid,
            )
            != (
                retired.st_dev,
                retired.st_ino,
                retired.st_mode,
                retired.st_uid,
            )
        ):
            raise GuardianProtocolError(
                "guardian control retired identity drifted after durability sync"
            )
        try:
            os.stat(
                absolute.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        except BaseException as exc:
            raise GuardianProtocolError(
                "guardian control canonical path absence is uncertain after durability sync"
            ) from exc
        else:
            raise GuardianProtocolError(
                "guardian control canonical path was replaced during durability sync"
            )
        final_parent_after = _directory_mutation_signature(
            os.fstat(parent_descriptor)
        )
        if final_parent_after != final_parent_before:
            raise GuardianProtocolError(
                "guardian control parent changed during final retirement verification"
            )
        _require_directory_mutation_watch_quiet(mutation_watch.descriptor)
    except BaseException as exc:
        mutation_watch.close_preserving(exc)
        retired_leaf.close_preserving(exc)
        _close_owned_descriptor_chain_preserving(directory_chain, exc)
        raise
    close_error = mutation_watch.close()
    if close_error is not None:
        primary = GuardianProtocolError(
            "guardian control directory mutation watch cleanup failed"
        )
        primary.__cause__ = close_error
        retired_leaf.close_preserving(primary)
        _close_owned_descriptor_chain_preserving(directory_chain, primary)
        raise primary
    close_error = retired_leaf.close()
    if close_error is not None:
        primary = GuardianProtocolError(
            "guardian control retired descriptor cleanup failed"
        )
        primary.__cause__ = close_error
        _close_owned_descriptor_chain_preserving(directory_chain, primary)
        raise primary
    close_error = _close_owned_descriptor_chain(directory_chain)
    if close_error is not None:
        raise GuardianProtocolError(
            "guardian control retained directory chain cleanup failed"
        ) from close_error
    return launch_validator.validate_control_socket_identity(
        {
            "device": final_retired.st_dev,
            "inode": final_retired.st_ino,
            "mode": stat.S_IMODE(final_retired.st_mode),
            "path": str(retirement),
            "uid": final_retired.st_uid,
        }
    )


def _chmod_bound_socket_at(
    parent_descriptor: int,
    absolute: Path,
    *,
    expected_identity: Mapping[str, object],
) -> None:
    if not hasattr(os, "O_PATH"):
        raise GuardianProtocolError(
            "guardian control socket requires Linux O_PATH"
        )
    leaf = _OwnedDescriptor()
    try:
        leaf.acquire(
            os.open(
                absolute.name,
                os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_descriptor,
            )
        )
        before = os.fstat(leaf.descriptor)
        if (
            not stat.S_ISSOCK(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_dev != expected_identity["device"]
            or before.st_ino != expected_identity["inode"]
        ):
            raise GuardianProtocolError(
                "guardian control socket drifted before anchored chmod"
            )
        proc_leaf = Path(f"/proc/self/fd/{leaf.descriptor}")
        through_proc = os.stat(proc_leaf)
        if (
            through_proc.st_dev != before.st_dev
            or through_proc.st_ino != before.st_ino
        ):
            raise GuardianProtocolError(
                "guardian control socket descriptor alias drifted before chmod"
            )
        os.chmod(proc_leaf, 0o600)
        after = os.fstat(leaf.descriptor)
        at_parent = os.stat(
            absolute.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            after.st_dev != before.st_dev
            or after.st_ino != before.st_ino
            or at_parent.st_dev != before.st_dev
            or at_parent.st_ino != before.st_ino
            or stat.S_IMODE(after.st_mode) != 0o600
            or stat.S_IMODE(at_parent.st_mode) != 0o600
        ):
            raise GuardianProtocolError(
                "guardian control socket drifted across anchored chmod"
            )
    except BaseException as exc:
        leaf.close_preserving(exc)
        raise
    close_error = leaf.close()
    if close_error is not None:
        raise GuardianProtocolError(
            "guardian control socket descriptor cleanup failed after chmod"
        ) from close_error


class GuardianControlListener:
    """Supervisor-side pathname listener; it never carries inherited unit FDs."""

    def __init__(
        self,
        path: Path | str,
        *,
        retirement_path: Path | str | None = None,
    ) -> None:
        self.path = Path(os.path.abspath(os.fspath(path)))
        self.retirement_path = _guardian_control_retirement_path(self.path)
        if (
            retirement_path is not None
            and Path(os.path.abspath(os.fspath(retirement_path)))
            != self.retirement_path
        ):
            raise GuardianProtocolError(
                "guardian control retirement path differs from the fixed topology"
            )
        self.parent = _OwnedDescriptor()
        control: socket.socket | None = None
        self.accept_attempted = False
        self.bound = False
        self.bound_identity: dict[str, object] | None = None
        self.closed = False
        self.parent_release_attempted = False
        self.remove_attempted = False
        self.retired_identity: dict[str, object] | None = None
        try:
            self.parent.acquire(
                _open_directory_no_symlinks(self.path.parent)
            )
            parent_stat = os.fstat(self.parent.descriptor)
            self.parent_identity = (parent_stat.st_dev, parent_stat.st_ino)
            try:
                os.stat(
                    self.path.name,
                    dir_fd=self.parent.descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise GuardianProtocolError(
                    "guardian control socket path already exists"
                )
            try:
                os.stat(
                    self.retirement_path.name,
                    dir_fd=self.parent.descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise GuardianProtocolError(
                    "guardian control socket retirement path already exists"
                )
            control = socket.socket(
                socket.AF_UNIX,
                socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
            )
            address = _descriptor_socket_address(
                self.parent.descriptor,
                self.path.name,
            )
            control.bind(address)
            self.bound = True
            bound_stat = os.stat(
                self.path.name,
                dir_fd=self.parent.descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISSOCK(bound_stat.st_mode)
                or bound_stat.st_uid != os.getuid()
            ):
                raise GuardianProtocolError(
                    "guardian control bound pathname identity drifted"
                )
            bound_identity: dict[str, object] = {
                "device": bound_stat.st_dev,
                "inode": bound_stat.st_ino,
            }
            self.bound_identity = bound_identity
            if control.getsockname() != address:
                raise GuardianProtocolError(
                    "guardian control kernel pathname alias drifted"
                )
            _chmod_bound_socket_at(
                self.parent.descriptor,
                self.path,
                expected_identity=bound_identity,
            )
            control.listen(1)
            self.socket = control
            self.identity = _control_socket_identity_at(
                self.parent.descriptor,
                self.path,
            )
        except BaseException as exc:
            if control is not None:
                try:
                    control.close()
                except BaseException as cleanup_error:
                    exc.add_note(
                        "guardian control socket cleanup failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            if self.bound:
                try:
                    if self.bound_identity is None:
                        raise GuardianProtocolError(
                            "guardian control bound identity is unavailable; "
                            "pathname was not retired"
                        )
                    self.retired_identity = _retire_bound_socket_at(
                        self.parent.descriptor,
                        self.path,
                        expected_identity=self.bound_identity,
                    )
                except BaseException as cleanup_error:
                    exc.add_note(
                        "guardian control pathname retirement failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            self.parent.close_preserving(exc)
            raise

    def _require_parent_join(self) -> None:
        anchored = os.fstat(self.parent.descriptor)
        if (anchored.st_dev, anchored.st_ino) != self.parent_identity:
            raise GuardianProtocolError(
                "guardian control retained parent identity drifted"
            )
        _require_directory_join(
            self.path.parent,
            self.parent.descriptor,
        )

    def accept_once(
        self,
        *,
        expected_peer_process: Mapping[str, object],
        process_starttime_reader: Callable[[int], int],
    ) -> socket.socket:
        if self.accept_attempted:
            raise GuardianProtocolError("guardian control accept cannot be attempted twice")
        self.accept_attempted = True
        expected = launch_validator.validate_process_identity(
            expected_peer_process,
            "guardian listener peer",
        )
        self._require_parent_join()
        if (
            _control_socket_identity_at(
                self.parent.descriptor,
                self.path,
            )
            != self.identity
        ):
            raise GuardianProtocolError("guardian control socket changed before accept")
        try:
            connection, _address = self.socket.accept()
        except BaseException as exc:
            raise GuardianProtocolError(f"guardian control accept failed or is uncertain: {exc}") from exc
        try:
            _socket_type(connection)
            peer_pid = _peer_pid(connection)
            if (
                peer_pid != expected["pid"]
                or process_starttime_reader(peer_pid) != expected["starttime"]
            ):
                raise GuardianProtocolError("guardian control accepted the wrong process")
        except BaseException:
            connection.close()
            raise
        return connection

    def close_once(self) -> None:
        if self.closed:
            raise GuardianProtocolError("guardian control listener cannot close twice")
        self.closed = True
        self.socket.close()

    @property
    def parent_owned(self) -> bool:
        return self.parent.owned

    def abandon_parent_once(self) -> None:
        """Close the retained anchor without unlinking an unverified pathname."""

        if not self.closed:
            raise GuardianProtocolError(
                "guardian control parent cannot close before listener close"
            )
        if self.parent_release_attempted:
            raise GuardianProtocolError(
                "guardian control parent release cannot be attempted twice"
            )
        self.parent_release_attempted = True
        close_error = self.parent.close()
        if close_error is not None:
            raise GuardianProtocolError(
                "guardian control parent abandonment failed or is uncertain"
            ) from close_error

    def remove_path_once(self) -> dict[str, object]:
        if not self.closed:
            raise GuardianProtocolError("guardian control path cannot be removed before listener close")
        if self.remove_attempted:
            raise GuardianProtocolError("guardian control path removal cannot be attempted twice")
        if self.parent_release_attempted:
            raise GuardianProtocolError(
                "guardian control parent was already released"
            )
        self._require_parent_join()
        if (
            _control_socket_identity_at(
                self.parent.descriptor,
                self.path,
            )
            != self.identity
        ):
            raise GuardianProtocolError("guardian control socket changed before removal")
        self.remove_attempted = True
        primary: BaseException | None = None
        try:
            self.retired_identity = _retire_bound_socket_at(
                self.parent.descriptor,
                self.path,
                expected_identity=self.identity,
            )
            self.bound = False
        except BaseException as exc:
            primary = GuardianProtocolError(
                f"guardian control socket removal failed or is uncertain: {exc}"
            )
            primary.__cause__ = exc
        self.parent_release_attempted = True
        close_error = self.parent.close()
        if primary is not None:
            if close_error is not None:
                primary.add_note(
                    "guardian control parent cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
            raise primary
        if close_error is not None:
            raise GuardianProtocolError(
                "guardian control parent cleanup failed after retirement"
            ) from close_error
        assert self.retired_identity is not None
        return {
            "absent": True,
            "retired_identity": dict(self.retired_identity),
            "retired_path": str(self.retirement_path),
        }


def connect_guardian_control(path: Path | str) -> socket.socket:
    """Guardian-side one-shot connect to the pre-created supervisor listener."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    parent = _OwnedDescriptor()
    connection: socket.socket | None = None
    try:
        parent.acquire(_open_directory_no_symlinks(absolute.parent))
        before = _control_socket_identity_at(parent.descriptor, absolute)
        connection = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
        )
        connection.connect(
            _descriptor_socket_address(parent.descriptor, absolute.name)
        )
        _socket_type(connection)
        # The server's /proc/self/fd/N spelling is process-local, so its
        # getpeername() string is not authority.  The anchored inode join here
        # is followed by the existing SO_PEERCRED PID/starttime handoff join.
        if (
            _control_socket_identity_at(parent.descriptor, absolute)
            != before
        ):
            raise GuardianProtocolError("guardian control socket changed across connect")
        _require_directory_join(absolute.parent, parent.descriptor)
        close_error = parent.close()
        if close_error is not None:
            raise GuardianProtocolError(
                "guardian control parent cleanup failed after connect"
            ) from close_error
    except BaseException as exc:
        if connection is not None:
            try:
                connection.close()
            except BaseException as cleanup_error:
                exc.add_note(
                    "guardian control connection cleanup failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        parent.close_preserving(exc)
        raise
    if connection is None:
        raise GuardianProtocolError("guardian control connection is absent")
    return connection


def send_frame(
    connection: socket.socket,
    record: Mapping[str, object],
    *,
    file_descriptors: tuple[int, ...] = (),
) -> dict[str, object]:
    """Send one canonical packet once; a short/uncertain send is not retried."""

    _socket_type(connection)
    _checked, raw = _canonical_record(record, "guardian protocol frame")
    if not raw or len(raw) > MAX_FRAME_BYTES:
        raise GuardianProtocolError("guardian protocol frame size is invalid")
    ancillary: list[tuple[int, int, bytes]] = []
    if file_descriptors:
        if len(file_descriptors) != LOCK_COUNT or any(type(fd) is not int or fd < 0 for fd in file_descriptors):
            raise GuardianProtocolError("guardian handoff descriptor set is malformed")
        descriptor_bytes = array("i", file_descriptors).tobytes()
        ancillary.append((socket.SOL_SOCKET, socket.SCM_RIGHTS, descriptor_bytes))
    try:
        written = connection.sendmsg([raw], ancillary)
    except BaseException as exc:
        raise GuardianProtocolError(f"guardian frame send failed or is uncertain: {exc}") from exc
    if written != len(raw):
        raise GuardianProtocolError("guardian frame send was short and is uncertain")
    return _message_identity(raw)


def receive_frame(
    connection: socket.socket,
    *,
    expected_fd_count: int,
) -> ReceivedFrame:
    """Receive one packet and close received FDs on every validation failure."""

    _socket_type(connection)
    if expected_fd_count not in {0, LOCK_COUNT}:
        raise GuardianProtocolError("guardian expected descriptor count is invalid")
    ancillary_size = socket.CMSG_SPACE(LOCK_COUNT * array("i").itemsize)
    try:
        raw, ancillary, flags, _address = connection.recvmsg(MAX_FRAME_BYTES + 1, ancillary_size)
    except BaseException as exc:
        raise GuardianProtocolError(f"guardian frame receive failed: {exc}") from exc
    received: list[int] = []
    try:
        if not raw:
            raise GuardianPeerClosed("guardian supervisor connection closed")
        if len(raw) > MAX_FRAME_BYTES or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise GuardianProtocolError("guardian protocol frame was truncated")
        for level, kind, data in ancillary:
            if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                raise GuardianProtocolError("guardian protocol carried unexpected ancillary data")
            if len(data) % array("i").itemsize:
                raise GuardianProtocolError("guardian descriptor ancillary framing drifted")
            values = array("i")
            values.frombytes(data)
            received.extend(values.tolist())
        if len(received) != expected_fd_count:
            raise GuardianProtocolError("guardian descriptor count drifted")
        for descriptor in received:
            fcntl.fcntl(descriptor, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        value = authority.strict_loads(raw, "guardian protocol frame")
        if type(value) is not dict:
            raise GuardianProtocolError("guardian protocol frame is not one object")
        return ReceivedFrame(
            file_descriptors=tuple(received),
            identity=_message_identity(raw),
            peer_pid=_peer_pid(connection),
            record=dict(value),
        )
    except BaseException:
        for descriptor in received:
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise


def receive_frame_interruptible(
    connection: socket.socket,
    *,
    expected_fd_count: int,
    termination_records: list[dict[str, int]],
    poll_interval_seconds: float,
) -> ReceivedFrame:
    """Poll one frame while making the non-unwinding termination latch observable."""

    _socket_type(connection)
    if expected_fd_count not in {0, LOCK_COUNT}:
        raise GuardianProtocolError("guardian expected descriptor count is invalid")
    if (
        type(poll_interval_seconds) not in {float, int}
        or not math.isfinite(float(poll_interval_seconds))
        or poll_interval_seconds <= 0
    ):
        raise GuardianProtocolError("guardian control poll interval is invalid")
    timeout_ms = max(
        1,
        math.ceil(
            min(float(poll_interval_seconds), MAX_CONTROL_POLL_SECONDS) * 1000
        ),
    )
    descriptor = connection.fileno()
    poller = select.poll()
    poller.register(
        descriptor,
        select.POLLIN | select.POLLHUP | select.POLLERR | select.POLLNVAL,
    )
    while True:
        if termination_records:
            raise GuardianTerminationLatched(
                "guardian termination latch was recorded before frame receive"
            )
        try:
            events = poller.poll(timeout_ms)
        except InterruptedError:
            continue
        if termination_records:
            raise GuardianTerminationLatched(
                "guardian termination latch was recorded during frame receive"
            )
        if not events:
            continue
        observed = 0
        for ready_descriptor, event_mask in events:
            if ready_descriptor != descriptor:
                raise GuardianProtocolError(
                    "guardian control poll returned an unexpected descriptor"
                )
            observed |= event_mask
        if observed & select.POLLNVAL:
            raise GuardianProtocolError("guardian control descriptor became invalid")
        if not observed & (select.POLLIN | select.POLLHUP | select.POLLERR):
            raise GuardianProtocolError("guardian control poll returned unknown events")
        frame = receive_frame(connection, expected_fd_count=expected_fd_count)
        if not termination_records:
            return frame
        for received_descriptor in frame.file_descriptors:
            try:
                os.close(received_descriptor)
            except OSError:
                pass
        raise GuardianTerminationLatched(
            "guardian termination latch was recorded across frame receive"
        )


def build_lock_handoff_record(
    *,
    admission: Mapping[str, object],
    admission_identity: Mapping[str, object],
    expected_context: Mapping[str, object],
    guardian_process_identity: Mapping[str, object],
    guardian_unit_identity: Mapping[str, object],
    control_socket_identity: Mapping[str, object],
    lock_identities: object,
    supervisor_process_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build the exact non-authorizing descriptor-handoff frame."""

    context = launch_validator.validate_formal_context(expected_context)
    checked_admission = launch_validator.validate_admission(
        admission,
        expected_context=context,
    )
    checked_admission_identity = launch_validator.validate_detached_identity(
        admission_identity,
        "guardian handoff admission",
    )
    if (
        checked_admission_identity["path"] != context["formal_admission_path"]
        or checked_admission["guardian_launch_authorized"] is not True
    ):
        raise GuardianProtocolError("guardian handoff lacks its formal admission")
    return {
        "authority_scope": launch_validator.AUTHORITY_SCOPE,
        "campaign_root_identity": context["campaign_root_identity"],
        "control_socket_identity": launch_validator.validate_control_socket_identity(
            control_socket_identity
        ),
        "dual_holder_platform_assumption": launch_validator.DUAL_HOLDER_PLATFORM_ASSUMPTION,
        "formal_admission_identity": checked_admission_identity,
        "guardian_process_identity": launch_validator.validate_process_identity(
            guardian_process_identity,
            "guardian handoff process",
        ),
        "guardian_runtime_identity": context["guardian_runtime_identity"],
        "guardian_unit_identity": launch_validator.validate_guardian_unit_identity(
            guardian_unit_identity
        ),
        "lock_identities": launch_validator.validate_lock_identities(lock_identities),
        "manager_epoch": dict(context["manager_epoch"]),
        "package_id": context["package_id"],
        "schema_version": LOCK_HANDOFF_SCHEMA,
        "status": "LOCKS_DUPLICATED_NOT_LAUNCH_AUTHORITY",
        "supervisor_process_identity": launch_validator.validate_process_identity(
            supervisor_process_identity,
            "guardian handoff supervisor",
        ),
    }


def validate_lock_handoff_record(
    value: object,
    *,
    expected: Mapping[str, object],
) -> dict[str, object]:
    record = _closed(value, HANDOFF_FIELDS, "guardian lock handoff")
    expected_record = _closed(expected, HANDOFF_FIELDS, "expected guardian lock handoff")
    if (
        record != expected_record
        or record["schema_version"] != LOCK_HANDOFF_SCHEMA
        or record["status"] != "LOCKS_DUPLICATED_NOT_LAUNCH_AUTHORITY"
    ):
        raise GuardianProtocolError("guardian lock handoff identity drifted")
    return record


def validate_received_lock_handoff(
    value: object,
    *,
    admission: Mapping[str, object],
    admission_identity: Mapping[str, object],
    expected_context: Mapping[str, object],
    frame_peer_pid: int,
    process_starttime_reader: Callable[[int], int],
) -> dict[str, object]:
    """Independently validate one incoming handoff; never trust a caller copy."""

    context = launch_validator.validate_formal_context(expected_context)
    checked_admission = launch_validator.validate_admission(
        admission,
        expected_context=context,
    )
    checked_admission_identity = launch_validator.validate_detached_identity(
        admission_identity,
        "guardian incoming admission",
    )
    record = _closed(value, HANDOFF_FIELDS, "guardian incoming handoff")
    result = dict(record)
    result["campaign_root_identity"] = launch_validator.validate_detached_identity(
        record["campaign_root_identity"],
        "guardian incoming campaign root",
    )
    result["control_socket_identity"] = (
        launch_validator.validate_control_socket_identity(
            record["control_socket_identity"]
        )
    )
    result["formal_admission_identity"] = (
        launch_validator.validate_detached_identity(
            record["formal_admission_identity"],
            "guardian incoming formal admission",
        )
    )
    result["guardian_process_identity"] = (
        launch_validator.validate_process_identity(
            record["guardian_process_identity"],
            "guardian incoming process",
        )
    )
    result["supervisor_process_identity"] = (
        launch_validator.validate_process_identity(
            record["supervisor_process_identity"],
            "guardian incoming supervisor",
        )
    )
    result["guardian_runtime_identity"] = (
        launch_validator.validate_detached_identity(
            record["guardian_runtime_identity"],
            "guardian incoming runtime",
        )
    )
    result["guardian_unit_identity"] = (
        launch_validator.validate_guardian_unit_identity(
            record["guardian_unit_identity"]
        )
    )
    result["lock_identities"] = launch_validator.validate_lock_identities(
        record["lock_identities"]
    )
    guardian_process = result["guardian_process_identity"]
    supervisor_process = result["supervisor_process_identity"]
    guardian_unit = result["guardian_unit_identity"]
    observed_group = current_control_group()
    if (
        record["schema_version"] != LOCK_HANDOFF_SCHEMA
        or record["status"] != "LOCKS_DUPLICATED_NOT_LAUNCH_AUTHORITY"
        or record["authority_scope"] != launch_validator.AUTHORITY_SCOPE
        or result["campaign_root_identity"] != context["campaign_root_identity"]
        or record["package_id"] != context["package_id"]
        or record["dual_holder_platform_assumption"]
        != launch_validator.DUAL_HOLDER_PLATFORM_ASSUMPTION
        or result["formal_admission_identity"] != checked_admission_identity
        or checked_admission_identity["path"] != context["formal_admission_path"]
        or result["guardian_runtime_identity"]
        != context["guardian_runtime_identity"]
        or record["manager_epoch"] != context["manager_epoch"]
        or result["control_socket_identity"]
        != control_socket_identity(context["guardian_control_socket_path"])
        or guardian_process["pid"] != os.getpid()
        or process_starttime_reader(os.getpid()) != guardian_process["starttime"]
        or supervisor_process["pid"] != frame_peer_pid
        or process_starttime_reader(frame_peer_pid)
        != supervisor_process["starttime"]
        or guardian_process not in guardian_unit["processes"]
        or guardian_unit["control_group"] != observed_group
        or Path(observed_group).name != guardian_unit["unit_name"]
        or checked_admission["guardian_launch_authorized"] is not True
    ):
        raise GuardianProtocolError("guardian incoming handoff identity drifted")
    return result


def validate_preselection_cancel_record(
    value: object,
    *,
    guardian: OuterGuardian,
) -> dict[str, object]:
    """Validate one non-authorizing cancel before any formal selection."""

    record = _closed(
        value,
        PRESELECTION_CANCEL_FIELDS,
        "guardian preselection cancel",
    )
    admission_identity = launch_validator.validate_detached_identity(
        record["formal_admission_identity"],
        "preselection cancel formal admission",
    )
    ready_identity = launch_validator.validate_detached_identity(
        record["guardian_ready_identity"],
        "preselection cancel guardian ready",
    )
    locks = launch_validator.validate_lock_identities(record["lock_identities"])
    if (
        record["schema_version"] != GUARDIAN_PRESELECTION_CANCEL_SCHEMA
        or record["status"] != "CANCEL_WITHOUT_FORMAL_SELECTION"
        or record["authority_scope"] != launch_validator.AUTHORITY_SCOPE
        or record["campaign_root_identity"]
        != guardian.context["campaign_root_identity"]
        or record["package_id"] != guardian.context["package_id"]
        or admission_identity != guardian.admission_identity
        or ready_identity != guardian.ready_identity
        or locks != guardian._require_lease().evidence()  # noqa: SLF001
        or type(record["reason"]) is not str
        or not record["reason"]
        or guardian.selection_identity is not None
    ):
        raise GuardianProtocolError("guardian preselection cancel join drifted")
    return record


class GuardianLockLease:
    """Guardian copies of the supervisor's exact three locked descriptions."""

    def __init__(
        self,
        descriptors: tuple[int, ...],
        expected_identities: object,
    ) -> None:
        if len(descriptors) != LOCK_COUNT:
            raise GuardianProtocolError("guardian lock lease descriptor count drifted")
        self._descriptors = list(descriptors)
        self._expected = launch_validator.validate_lock_identities(expected_identities)
        self.close_attempted = False
        self.close_returned = False
        try:
            self.evidence()
        except BaseException:
            for descriptor in self._descriptors:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            self._descriptors.clear()
            raise

    @property
    def descriptors(self) -> tuple[int, ...]:
        return tuple(self._descriptors)

    def evidence(self) -> list[dict[str, object]]:
        if self.close_attempted or len(self._descriptors) != LOCK_COUNT:
            raise GuardianProtocolError("guardian lock copies are no longer provably held")
        result: list[dict[str, object]] = []
        for descriptor, expected in zip(self._descriptors, self._expected, strict=True):
            opened = os.fstat(descriptor)
            current = os.stat(expected["path"], follow_symlinks=False)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.getuid()
                or stat.S_IMODE(opened.st_mode) != 0o600
                or (opened.st_dev, opened.st_ino) != (expected["device"], expected["inode"])
                or (current.st_dev, current.st_ino) != (expected["device"], expected["inode"])
            ):
                raise GuardianProtocolError(f"guardian lock identity drifted: {expected['path']}")
            probe = os.open(
                expected["path"],
                os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            try:
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    fcntl.flock(probe, fcntl.LOCK_UN)
                    raise GuardianProtocolError(f"guardian lock is not exclusively held: {expected['path']}")
            finally:
                os.close(probe)
            result.append(dict(expected))
        return result

    def close_local_copies_once(self) -> dict[str, object]:
        """Close guardian copies; never claim that the global lock is released."""

        if self.close_attempted:
            raise GuardianProtocolError("guardian lock copies cannot be closed twice")
        identities = self.evidence()
        self.close_attempted = True
        errors: list[dict[str, str]] = []
        for descriptor in self._descriptors:
            try:
                os.close(descriptor)
            except BaseException as exc:
                errors.append(closeout_state.failure("GUARDIAN_LOCK_CLOSE_FAILED_OR_UNCERTAIN", exc))
        self._descriptors.clear()
        self.close_returned = not errors
        return {
            "errors": errors,
            "guardian_copies_closed": not errors,
            "lock_identities": identities,
            "supervisor_copies_must_remain_held": True,
        }


class ExistingCloseoutResidualPort:
    """Narrow adapter over the existing closeout effect and receipt owners."""

    def __init__(
        self,
        *,
        boundary: Any,
        lease: GuardianLockLease,
        formal_selection: Mapping[str, object],
        formal_selection_identity: Mapping[str, object],
        guardian_process_identity: Mapping[str, object],
        supervisor_process_identity: Mapping[str, object],
    ) -> None:
        self.boundary = boundary
        self.selection = dict(formal_selection)
        self.selection_identity = launch_validator.validate_detached_identity(
            formal_selection_identity,
            "guardian residual selection",
        )
        self.guardian_process_identity = (
            launch_validator.validate_process_identity(
                guardian_process_identity,
                "guardian residual guardian process",
            )
        )
        self.supervisor_process_identity = (
            launch_validator.validate_process_identity(
                supervisor_process_identity,
                "guardian residual supervisor process",
            )
        )
        if self.guardian_process_identity == self.supervisor_process_identity:
            raise GuardianProtocolError(
                "guardian residual process identities collapsed"
            )
        helper = _closeout_helper_module()
        self.helper = helper
        self.store = helper.ReceiptStore()
        descriptors = lease.descriptors
        if len(descriptors) != len(closeout_state.LOCK_PATHS):
            raise GuardianProtocolError("guardian residual port lacks three lock FDs")
        self.host = helper.PinnedHost(
            boundary,
            {
                path: descriptor
                for path, descriptor in zip(
                    closeout_state.LOCK_PATHS,
                    descriptors,
                    strict=True,
                )
            },
        )
        self.containment_attempted = False
        self.takeover_freeze_attempted = False
        self.takeover_ledger: dict[str, object] | None = None
        self.takeover_release_eligible: bool | None = None
        self.takeover_owned_unit_names: list[str] = []
        self.ownership_errors: list[dict[str, str]] = []

    def validate_ledger(
        self,
        value: Mapping[str, object],
    ) -> Mapping[str, object]:
        return closeout_state.validate_frozen_ledger(value)

    def _expected_receipt_common(self) -> dict[str, object]:
        return {
            "campaign_root_identity": self.boundary.context["root_identity"],
            "formal_selection_identity": self.selection_identity,
            "manager_epoch": self.boundary.root["manager_epoch"],
            "package_id": self.boundary.root["package"]["package_id"],
        }

    def _outer_prelaunch_resource_contract(
        self,
        *,
        unit_name: str,
    ) -> tuple[dict[str, object], list[dict[str, int]]]:
        campaign_root_identity = self.boundary.context["root_identity"]
        if (
            type(campaign_root_identity) is not dict
            or type(campaign_root_identity.get("sha256")) is not str
        ):
            raise GuardianProtocolError(
                "guardian residual campaign-root identity is malformed"
            )
        return (
            {
                "authority_id": self.selection_identity["sha256"],
                "disk_path": str(Path(self.boundary.campaign).absolute()),
                "kind": "FORMAL_OUTER_PRELAUNCH",
                "ordinal": 0,
                "scope_id": campaign_root_identity["sha256"],
                "sequence": 1,
                "slot": "",
                "target": unit_name,
            },
            [
                dict(self.supervisor_process_identity),
                dict(self.guardian_process_identity),
            ],
        )

    def _recorded_reference_verification(
        self,
        checked: Mapping[str, object],
    ) -> dict[str, str]:
        paths = self.selection["outer_spec"]["receipt_paths"]
        expected = self._expected_receipt_common()
        frozen_outer_identity = {
            name: checked["outer"][name]
            for name in (
                "control_group",
                "invocation_id",
                "processes",
                "unit_name",
            )
        }
        acquisition, _acquisition_identity = self.store.document(
            paths["reference_acquisition"],
            "guardian reference acquisition",
        )
        checked_acquisition = success_verifier.validate_reference_acquisition(
            acquisition,
            expected=expected,
            expected_outer_identity=frozen_outer_identity,
        )
        verification = checked_acquisition["reference_verification"]
        if (
            verification["manager_owner"]
            != self.boundary.root["manager_epoch"]["dbus_unique_owner"]
            or checked_acquisition["outer_identity"] != frozen_outer_identity
        ):
            raise GuardianProtocolError(
                "guardian outer/reference ownership identity drifted"
            )
        return {
            "client_unique_name": verification["connection_identity"],
            "manager_owner": verification["manager_owner"],
            "unit_name": verification["unit_name"],
        }

    def _ownership(self, ledger: Mapping[str, object]) -> list[str]:
        checked = closeout_state.validate_frozen_ledger(ledger)
        paths = self.selection["outer_spec"]["receipt_paths"]
        expected = self._expected_receipt_common()
        unit_name = str(self.selection["outer_spec"]["unit_name"])
        frozen_outer_identity = {
            name: checked["outer"][name]
            for name in (
                "control_group",
                "invocation_id",
                "processes",
                "unit_name",
            )
        }
        active_outer = bool(
            checked["outer"]["invocation_id"]
            or checked["outer"]["control_group"]
            or checked["outer"]["processes"]
        )
        resource_context, resource_allowlist = (
            self._outer_prelaunch_resource_contract(unit_name=unit_name)
        )
        owned: list[str] = []
        try:
            prelaunch, prelaunch_identity = self.store.document(
                paths["outer_prelaunch"],
                "guardian outer prelaunch",
            )
            checked_prelaunch = success_verifier.validate_outer_prelaunch(
                prelaunch,
                expected=expected,
                expected_allowed_same_uid_processes=resource_allowlist,
                expected_unit_name=unit_name,
                expected_lock_identities=self.host.lock_evidence(),
                expected_observation_context=resource_context,
            )
            started, _started_identity = self.store.document(
                paths["outer_start"],
                "guardian outer start",
            )
            checked_start = success_verifier.validate_outer_start(
                started,
                expected=expected,
                expected_resource_admission=checked_prelaunch[
                    "resource_admission"
                ],
                expected_unit_name=unit_name,
            )
            if (
                checked_start["launch_effect"]["outer_prelaunch_identity"]
                != prelaunch_identity
                or checked_prelaunch["outer_identity"]["unit_name"] != unit_name
                or checked_start["outer_identity"] != frozen_outer_identity
            ):
                raise GuardianProtocolError(
                    "guardian outer prelaunch/start identity join drifted"
                )
            if active_outer:
                owned.append(unit_name)
        except Exception as exc:
            self.ownership_errors.append(
                closeout_state.failure(
                    "GUARDIAN_OUTER_OWNERSHIP_IDENTITY_GAP",
                    exc,
                )
            )
        try:
            recorded_reference = self._recorded_reference_verification(checked)
        except Exception as exc:
            # Before RefUnit acquisition, outer ownership remains independently
            # proved but no child can be promoted from IDENTITY_GAP.
            self.ownership_errors.append(
                closeout_state.failure(
                    "GUARDIAN_CHILD_OWNERSHIP_IDENTITY_GAP",
                    exc,
                )
            )
            return owned
        owned.extend(self.helper.derive_child_containment_owned_unit_names(
            self.boundary,
            self.store,
            self.host,
            self.selection,
            checked,
            expected_allowed_same_uid_processes=resource_allowlist,
            recorded_reference_verification=recorded_reference,
        ))
        return owned

    def freeze_takeover_ledger(
        self,
        ledger: Mapping[str, object],
    ) -> dict[str, object]:
        """Observe the one finite selected ledger before peer-loss containment."""

        if self.takeover_freeze_attempted:
            raise GuardianProtocolError(
                "guardian takeover ledger cannot be frozen twice"
            )
        self.takeover_freeze_attempted = True
        checked = closeout_state.validate_frozen_ledger(ledger)
        try:
            recorded_reference = self._recorded_reference_verification(checked)
            targets = self.helper.build_child_ledger(
                self.boundary,
                self.store,
                self.host,
                None,
                self.selection,
                expected_allowed_same_uid_processes=[
                    dict(self.supervisor_process_identity),
                    dict(self.guardian_process_identity),
                ],
                recorded_reference_verification=recorded_reference,
            )
            result = self.helper.freeze_takeover_child_ledger(
                self.host,
                checked,
                targets,
            )
            checked = closeout_state.validate_frozen_ledger(result["ledger"])
            self.takeover_owned_unit_names = list(
                dict.fromkeys(
                    [
                        *result["owned_unit_names"],
                        *self._ownership(checked),
                    ]
                )
            )
            for item in closeout_state.validate_failure_list(
                result["errors"],
                "guardian takeover freeze errors",
            ):
                if item not in self.ownership_errors:
                    self.ownership_errors.append(item)
            self.takeover_release_eligible = True
        except Exception as exc:
            self.ownership_errors.append(
                closeout_state.failure(
                    "GUARDIAN_TAKEOVER_LEDGER_IDENTITY_GAP",
                    exc,
                )
            )
            # A partial or failed audit cannot prove which exact runtime
            # identities must disappear.  Preserve the old ledger only as
            # evidence; it is never a release credential.
            self.takeover_release_eligible = False
        self.takeover_ledger = checked
        return checked

    def contain_exact_once(
        self,
        ledger: Mapping[str, object],
    ) -> Mapping[str, object]:
        if self.containment_attempted:
            raise GuardianProtocolError(
                "guardian residual containment cannot be attempted twice"
            )
        self.containment_attempted = True
        checked = closeout_state.validate_frozen_ledger(ledger)
        if self.takeover_ledger is not None:
            if checked != self.takeover_ledger:
                raise GuardianProtocolError(
                    "guardian containment ledger drifted after takeover freeze"
                )
            if self.takeover_release_eligible is not True:
                raise GuardianProtocolError(
                    "guardian takeover audit is permanently release-ineligible"
                )
            owned = list(self.takeover_owned_unit_names)
        else:
            owned = self._ownership(checked)
        result = dict(self.helper.contain_frozen_ledger_once(
            self.host,
            checked,
            owned_unit_names=owned,
        ))
        result["errors"] = [
            *self.ownership_errors,
            *closeout_state.validate_failure_list(
                result["errors"],
                "guardian frozen containment errors",
            ),
        ]
        if self.ownership_errors:
            result["status"] = "CONSUMED_INCOMPLETE"
        return result

    def observe_exact_absence(
        self,
        ledger: Mapping[str, object],
    ) -> Mapping[str, object]:
        return self.host.observe_frozen_absence(
            closeout_state.validate_frozen_ledger(ledger)
        )

    def validate_exact_absence(
        self,
        ledger: Mapping[str, object],
        observation: Mapping[str, object],
    ) -> Mapping[str, object]:
        return closeout_state.validate_absence_observation(
            observation,
            ledger=ledger,
        )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _preselection_cancel(
    guardian: OuterGuardian,
    *,
    boundary: Any,
    reason: str,
    waiter: WaitPort,
    poll_interval_seconds: float,
) -> dict[str, object]:
    """Prove the unselected surface empty, then close guardian copies once."""

    if guardian.selection_identity is not None:
        raise GuardianProtocolError("preselection cancel crossed formal selection")
    if guardian.ready_identity is None:
        raise GuardianProtocolError("preselection cancel lacks guardian readiness")
    if type(reason) is not str or not reason:
        raise GuardianProtocolError("preselection cancel reason is malformed")
    helper = _closeout_helper_module()
    lease = guardian._require_lease()  # noqa: SLF001
    host = helper.PinnedHost(
        boundary,
        {
            path: descriptor
            for path, descriptor in zip(
                closeout_state.LOCK_PATHS,
                lease.descriptors,
                strict=True,
            )
        },
    )
    selection_path = Path(guardian.context["formal_selection_path"])
    outer_unit = str(guardian.context["outer_spec"]["unit_name"])
    while True:
        lease.evidence()
        if os.path.lexists(selection_path):
            raise GuardianProtocolError(
                "formal selection appeared during preselection cancel"
            )
        shown = host.show(outer_unit)
        if shown == closeout_state.ABSENT_SYSTEMD_STATE:
            break
        try:
            waiter(poll_interval_seconds)
        except BaseException as exc:
            guardian.effects.fail("PRESELECTION_CANCEL_WAITER_FAILED", exc)
            deadline = time.monotonic() + poll_interval_seconds
            while time.monotonic() < deadline:
                time.sleep(max(0.0, deadline - time.monotonic()))
    close_effect = lease.close_local_copies_once()
    try:
        guardian.close_supervisor_death_witness_once()
    except BaseException as exc:
        guardian.effects.fail("SUPERVISOR_PIDFD_CLOSE_FAILED_OR_UNCERTAIN", exc)
    errors = closeout_state.validate_failure_list(
        close_effect["errors"],
        "preselection guardian close errors",
    )
    record = {
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "campaign_root_identity": guardian.context["campaign_root_identity"],
        "close_effect": close_effect,
        "errors": [*guardian.effects.errors, *errors],
        "formal_admission_identity": guardian.admission_identity,
        "formal_selection_absent": True,
        "guardian_ready_identity": guardian.ready_identity,
        "outcome": "PERMANENT_INCOMPLETE",
        "outer_absence": {
            "formal_selection_path": str(selection_path),
            "load_state": "not-found",
            "unit_name": outer_unit,
        },
        "package_id": guardian.context["package_id"],
        "reason": reason,
        "schema_version": GUARDIAN_PRESELECTION_ACK_SCHEMA,
        "status": "PRESELECTION_CANCELLED",
    }
    return _closed(record, PRESELECTION_ACK_FIELDS, "preselection cancel ack")


def _permanent_peer_loss_hold(
    guardian: OuterGuardian,
    *,
    port: ExistingCloseoutResidualPort | None,
    waiter: WaitPort,
    poll_interval_seconds: float,
) -> dict[str, object]:
    """Hold through exact absence, then close locally as permanent INCOMPLETE."""

    ledger = guardian.latest_ledger
    announcement = {
        "errors": list(guardian.effects.errors),
        "ledger_update_count": guardian.ledger_update_count,
        "outcome": "CONSUMED_INCOMPLETE"
        if guardian.selection_identity is not None
        else "PRESELECTION_GUARDIAN_HOLD",
        "reason": "SUPERVISOR_CONNECTION_LOST_BEFORE_TERMINAL_CLOSE",
        "status": "CONTAINMENT_HOLD",
    }
    if guardian.selection_identity is not None:
        announcement["formal_selection_identity"] = guardian.selection_identity
    print(
        authority.canonical_json(announcement).decode("utf-8"),
        file=sys.stderr,
        flush=True,
    )
    supervisor_death = guardian.hold_until_supervisor_death(
        waiter=waiter,
        poll_interval_seconds=poll_interval_seconds,
    )
    if (
        ledger is not None
        and port is not None
        and guardian.selection_identity is not None
    ):
        takeover_ledger = port.freeze_takeover_ledger(ledger)
        if port.takeover_release_eligible is True:
            close_record = guardian.close_locks_after_absence(
                ledger=takeover_ledger,
                ledger_message_identity=_ledger_identity(takeover_ledger),
                port=port,
                waiter=waiter,
                poll_interval_seconds=poll_interval_seconds,
                contain=True,
            )
            print(
                authority.canonical_json(
                    {
                        "guardian_lock_close": close_record,
                        "outcome": "PERMANENT_INCOMPLETE",
                        "reason": "SUPERVISOR_CONNECTION_LOST",
                        "status": "CONTAINMENT_CLEARED_AFTER_HOLD",
                        "supervisor_death": supervisor_death,
                    }
                ).decode("utf-8"),
                file=sys.stderr,
                flush=True,
            )
            return close_record
        print(
            authority.canonical_json(
                {
                    "errors": list(port.ownership_errors),
                    "outcome": "PERMANENT_INCOMPLETE",
                    "reason": "GUARDIAN_TAKEOVER_FREEZE_UNPROVEN",
                    "status": "CONTAINMENT_HOLD_RELEASE_INELIGIBLE",
                    "supervisor_death": supervisor_death,
                }
            ).decode("utf-8"),
            file=sys.stderr,
            flush=True,
        )
    # A missing finite ledger or any structural/replay failure makes release
    # permanently ineligible.  Keep the process and all three lock FDs alive.
    while True:
        guardian._require_lease().evidence()  # noqa: SLF001
        try:
            waiter(poll_interval_seconds)
        except BaseException as exc:
            guardian.effects.fail("GUARDIAN_PEER_LOSS_WAITER_FAILED", exc)
            deadline = time.monotonic() + poll_interval_seconds
            while time.monotonic() < deadline:
                time.sleep(max(0.0, deadline - time.monotonic()))


def run_guardian_session(
    *,
    campaign_dir: Path,
    formal_admission_path: Path,
    control_socket_path: Path,
    ready_output_path: Path,
    waiter: WaitPort = time.sleep,
    poll_interval_seconds: float = 1.0,
) -> int:
    """Run the independent one-connection guardian protocol."""

    context = launch_validator.replay_formal_launch_context(
        authority,
        campaign_dir,
    )
    if (
        str(formal_admission_path.absolute())
        != context["formal_admission_path"]
        or str(control_socket_path.absolute())
        != context["guardian_control_socket_path"]
        or str(ready_output_path.absolute()) != context["guardian_ready_path"]
    ):
        raise GuardianProtocolError("guardian CLI path drifted from authority")
    boundary_replay = getattr(authority, "replay_formal_runtime_boundary", None)
    if not callable(boundary_replay):
        raise GuardianProtocolError(
            "package authority lacks formal runtime boundary replay"
        )
    boundary = boundary_replay(campaign_dir)
    if (
        Path(boundary.formal_dir) != Path(context["formal_attempt_dir"])
        or Path(boundary.campaign) != Path(context["campaign_dir"])
    ):
        raise GuardianProtocolError("guardian runtime boundary drifted")
    admission, admission_identity = launch_validator.read_canonical_record(
        formal_admission_path,
        expected_identity=None,
        label="guardian formal admission",
    )
    launch_validator.validate_admission(admission, expected_context=context)
    helper = _closeout_helper_module()
    latch = helper.TerminationLatch()
    latch.install()
    connection: socket.socket | None = None
    guardian: OuterGuardian | None = None
    port: ExistingCloseoutResidualPort | None = None
    completed = False
    try:
        connection = connect_guardian_control(control_socket_path)
        guardian = OuterGuardian(
            connection=connection,
            admission=admission,
            admission_identity=admission_identity,
            expected_context=context,
            expected_handoff=None,
            process_starttime_reader=read_process_starttime,
        )
        guardian.receive_lock_handoff(
            termination_records=latch.records,
            poll_interval_seconds=poll_interval_seconds,
        )
        guardian.publish_ready_once(
            helper.ReceiptStore(),
            created_at_utc=_utc_now(),
        )
        first_control = receive_frame_interruptible(
            connection,
            expected_fd_count=0,
            termination_records=latch.records,
            poll_interval_seconds=poll_interval_seconds,
        )
        if (
            first_control.record.get("schema_version")
            == GUARDIAN_PRESELECTION_CANCEL_SCHEMA
        ):
            cancel = validate_preselection_cancel_record(
                first_control.record,
                guardian=guardian,
            )
            ack = _preselection_cancel(
                guardian,
                boundary=boundary,
                reason=str(cancel["reason"]),
                waiter=waiter,
                poll_interval_seconds=poll_interval_seconds,
            )
            send_frame(connection, ack)
            connection.close()
            connection = None
            completed = True
            return 2
        guardian.receive_activation(first_control)
        if (
            guardian.selection_record is None
            or guardian.selection_identity is None
            or guardian.ready_record is None
        ):
            raise GuardianProtocolError("guardian activation did not retain selection")
        ready_record = guardian.ready_record
        port = ExistingCloseoutResidualPort(
            boundary=boundary,
            lease=guardian._require_lease(),  # noqa: SLF001
            formal_selection=guardian.selection_record,
            formal_selection_identity=guardian.selection_identity,
            guardian_process_identity=ready_record["guardian_process_identity"],
            supervisor_process_identity=ready_record["supervisor_process_identity"],
        )
        terminal: dict[str, object] | None = None
        while terminal is None:
            frame = receive_frame_interruptible(
                connection,
                expected_fd_count=0,
                termination_records=latch.records,
                poll_interval_seconds=poll_interval_seconds,
            )
            schema = frame.record.get("schema_version")
            if schema == GUARDIAN_LEDGER_UPDATE_SCHEMA:
                guardian.receive_ledger_update(frame)
            elif schema == GUARDIAN_TERMINAL_SCHEMA:
                terminal = guardian.validate_terminal_frame(frame)
            else:
                raise GuardianProtocolError(
                    "guardian received an unknown post-activation frame"
                )
        command = terminal["record"]["command"]
        contain = command == "ENTER_CONTAINMENT"
        if contain:
            guardian.effects.fail(
                "GUARDIAN_TERMINAL_CONTAINMENT_REQUESTED",
                str(terminal["record"]["reason"]),
            )
        close_record = guardian.close_locks_after_absence(
            ledger=terminal["ledger"],
            ledger_message_identity=terminal["record"]["ledger_message_identity"],
            port=port,
            waiter=waiter,
            poll_interval_seconds=poll_interval_seconds,
            contain=contain,
        )
        send_frame(connection, close_record)
        connection.close()
        connection = None
        completed = True
        return 0 if close_record["success_eligible"] is True else 2
    except BaseException as exc:
        if guardian is None or guardian.lease is None:
            raise GuardianProtocolError(
                f"guardian failed before the lock handoff completed: {exc}"
            ) from exc
        if guardian.lease.close_attempted:
            raise GuardianProtocolError(
                f"guardian failed after its local lock close was attempted: {exc}"
            ) from exc
        guardian.mark_supervisor_lost(exc)
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
            connection = None
        if guardian.selection_identity is None:
            try:
                supervisor_death = guardian.hold_until_supervisor_death(
                    waiter=waiter,
                    poll_interval_seconds=poll_interval_seconds,
                )
                ack = _preselection_cancel(
                    guardian,
                    boundary=boundary,
                    reason=f"SUPERVISOR_LOST_PRESELECTION:{type(exc).__name__}",
                    waiter=waiter,
                    poll_interval_seconds=poll_interval_seconds,
                )
            except BaseException as cancel_exc:
                guardian.effects.fail(
                    "PRESELECTION_CANCEL_FAILED_OR_UNCERTAIN",
                    cancel_exc,
                )
                _permanent_peer_loss_hold(
                    guardian,
                    port=None,
                    waiter=waiter,
                    poll_interval_seconds=poll_interval_seconds,
                )
                raise AssertionError("unproved preselection hold returned")
            print(
                authority.canonical_json(
                    {
                        "preselection_ack": ack,
                        "status": "PRESELECTION_CANCELLED_AFTER_PEER_LOSS",
                        "supervisor_death": supervisor_death,
                    }
                ).decode("utf-8"),
                file=sys.stderr,
                flush=True,
            )
            completed = True
            return 2
        close_record = _permanent_peer_loss_hold(
            guardian,
            port=port,
            waiter=waiter,
            poll_interval_seconds=poll_interval_seconds,
        )
        if close_record["success_eligible"] is not False:
            raise GuardianProtocolError(
                "peer-loss guardian close attempted to retain success eligibility"
            )
        completed = True
        return 2
    finally:
        if completed:
            latch.restore()
        if connection is not None and (guardian is None or guardian.lease is None):
            connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--formal-admission", type=Path, required=True)
    parser.add_argument("--control-socket", type=Path, required=True)
    parser.add_argument("--ready-output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return run_guardian_session(
            campaign_dir=args.campaign_dir,
            formal_admission_path=args.formal_admission,
            control_socket_path=args.control_socket,
            ready_output_path=args.ready_output,
        )
    except BaseException as exc:
        print(
            f"FAIL_CLOSED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 125


class OuterGuardian:
    """Monotone guardian session; no controller or experiment behavior."""

    def __init__(
        self,
        *,
        connection: socket.socket,
        admission: Mapping[str, object],
        admission_identity: Mapping[str, object],
        expected_context: Mapping[str, object],
        expected_handoff: Mapping[str, object] | None,
        process_starttime_reader: Callable[[int], int],
        pidfd_opener: PidfdOpenPort = open_supervisor_pidfd,
        pidfd_exit_observer: PidfdExitPort = pidfd_reports_exit,
    ) -> None:
        self.connection = connection
        self.context = launch_validator.validate_formal_context(expected_context)
        self.admission = launch_validator.validate_admission(
            admission,
            expected_context=self.context,
        )
        self.admission_identity = launch_validator.validate_detached_identity(
            admission_identity,
            "guardian formal admission",
        )
        self.expected_handoff = (
            validate_lock_handoff_record(
                expected_handoff,
                expected=expected_handoff,
            )
            if expected_handoff is not None
            else None
        )
        self.process_starttime_reader = process_starttime_reader
        self.pidfd_opener = pidfd_opener
        self.pidfd_exit_observer = pidfd_exit_observer
        self.effects = GuardianEffects()
        self.handoff_identity: dict[str, object] | None = None
        self.lease: GuardianLockLease | None = None
        self.ready_identity: dict[str, object] | None = None
        self.ready_record: dict[str, object] | None = None
        self.selection_identity: dict[str, object] | None = None
        self.selection_record: dict[str, object] | None = None
        self.last_control_identity: dict[str, object] | None = None
        self.latest_ledger: dict[str, object] | None = None
        self.ledger_update_count = 0
        self.supervisor_death_witness: SupervisorDeathWitness | None = None

    def receive_lock_handoff(
        self,
        *,
        termination_records: list[dict[str, int]] | None = None,
        poll_interval_seconds: float = MAX_CONTROL_POLL_SECONDS,
    ) -> dict[str, object]:
        if self.effects.handoff_attempted:
            raise GuardianProtocolError("guardian lock handoff cannot be attempted twice")
        self.effects.handoff_attempted = True
        frame: ReceivedFrame | None = None
        witness: SupervisorDeathWitness | None = None
        try:
            frame = (
                receive_frame(self.connection, expected_fd_count=LOCK_COUNT)
                if termination_records is None
                else receive_frame_interruptible(
                    self.connection,
                    expected_fd_count=LOCK_COUNT,
                    termination_records=termination_records,
                    poll_interval_seconds=poll_interval_seconds,
                )
            )
            record = (
                validate_lock_handoff_record(
                    frame.record,
                    expected=self.expected_handoff,
                )
                if self.expected_handoff is not None
                else validate_received_lock_handoff(
                    frame.record,
                    admission=self.admission,
                    admission_identity=self.admission_identity,
                    expected_context=self.context,
                    frame_peer_pid=frame.peer_pid,
                    process_starttime_reader=self.process_starttime_reader,
                )
            )
            supervisor = launch_validator.validate_process_identity(
                record["supervisor_process_identity"],
                "guardian supervisor process",
            )
            guardian = launch_validator.validate_process_identity(
                record["guardian_process_identity"],
                "guardian process",
            )
            if (
                frame.peer_pid != supervisor["pid"]
                or self.process_starttime_reader(frame.peer_pid) != supervisor["starttime"]
                or guardian["pid"] != os.getpid()
                or self.process_starttime_reader(os.getpid()) != guardian["starttime"]
                or control_socket_identity(self.context["guardian_control_socket_path"])
                != record["control_socket_identity"]
            ):
                raise GuardianProtocolError("guardian handoff process identity drifted")
            witness = SupervisorDeathWitness(
                supervisor,
                process_starttime_reader=self.process_starttime_reader,
                pidfd_opener=self.pidfd_opener,
                exit_observer=self.pidfd_exit_observer,
            )
            lease = GuardianLockLease(frame.file_descriptors, record["lock_identities"])
        except BaseException as exc:
            if frame is not None:
                for descriptor in frame.file_descriptors:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
            if witness is not None:
                try:
                    os.close(witness.descriptor)
                except OSError:
                    pass
            self.effects.fail("GUARDIAN_LOCK_HANDOFF_FAILED_OR_UNCERTAIN", exc)
            raise
        self.lease = lease
        self.expected_handoff = record
        self.handoff_identity = frame.identity
        self.supervisor_death_witness = witness
        self.effects.handoff_received = True
        return {"identity": frame.identity, "record": record}

    def _require_lease(self) -> GuardianLockLease:
        if not self.effects.handoff_received or self.lease is None:
            raise GuardianProtocolError("guardian lock handoff is not established")
        self.lease.evidence()
        return self.lease

    def build_ready_record(self, *, created_at_utc: str) -> dict[str, object]:
        lease = self._require_lease()
        witness = self.supervisor_death_witness
        if witness is None:
            raise GuardianProtocolError(
                "guardian readiness lacks the handoff-bound supervisor pidfd"
            )
        record = {
            "authority_scope": launch_validator.AUTHORITY_SCOPE,
            "authorizations": dict(launch_validator.FALSE_CLAIMS),
            "campaign_dir": self.context["campaign_dir"],
            "campaign_root_identity": self.context["campaign_root_identity"],
            "control_socket_identity": self.expected_handoff["control_socket_identity"],
            "created_at_utc": created_at_utc,
            "dual_holder_platform_assumption": launch_validator.DUAL_HOLDER_PLATFORM_ASSUMPTION,
            "formal_admission_identity": self.admission_identity,
            "formal_launch_authorized": False,
            "guardian_process_identity": self.expected_handoff["guardian_process_identity"],
            "guardian_runtime_identity": self.context["guardian_runtime_identity"],
            "guardian_unit_identity": self.expected_handoff["guardian_unit_identity"],
            "handoff_message_identity": self.handoff_identity,
            "lock_identities": lease.evidence(),
            "manager_epoch": self.context["manager_epoch"],
            "package_id": self.context["package_id"],
            "schema_version": launch_validator.GUARDIAN_READY_SCHEMA,
            "status": "READY",
            "success_eligible": False,
            "supervisor_death_watch": witness.arm_record(),
            "supervisor_process_identity": self.expected_handoff["supervisor_process_identity"],
        }
        return launch_validator.validate_guardian_ready(
            record,
            admission=self.admission,
            admission_identity=self.admission_identity,
            expected_context=self.context,
        )

    def publish_ready_once(
        self,
        store: Any,
        *,
        created_at_utc: str,
    ) -> dict[str, object]:
        """Use the existing ReceiptStore owner and preserve write uncertainty."""

        effect = self.effects.ready_publication
        effect.begin()
        record = self.build_ready_record(created_at_utc=created_at_utc)
        try:
            identity = store.publish(
                self.context["guardian_ready_path"],
                record,
                "outer guardian ready",
                publication=effect,
            )
        except BaseException as exc:
            effect.note_error(exc)
            self.effects.fail("GUARDIAN_READY_PUBLICATION_FAILED_OR_UNCERTAIN", exc)
            raise GuardianProtocolError("guardian ready publication failed or is uncertain") from exc
        if effect.recorded_identity != identity:
            self.effects.fail(
                "GUARDIAN_READY_READBACK_DRIFT",
                "ready publication did not record its returned identity",
            )
            raise GuardianProtocolError("guardian ready publication readback drifted")
        self.ready_record = record
        self.ready_identity = dict(identity)
        return {"identity": dict(identity), "record": record}

    def activate_selection(
        self,
        selection: Mapping[str, object],
        *,
        selection_identity: Mapping[str, object],
        attempt_consumption: Mapping[str, object],
        attempt_consumption_identity: Mapping[str, object],
    ) -> dict[str, object]:
        if self.effects.selection_activated:
            raise GuardianProtocolError("guardian formal selection cannot be activated twice")
        if self.ready_record is None or self.ready_identity is None:
            raise GuardianProtocolError("guardian selection activation lacks recorded readiness")
        checked_identity = launch_validator.validate_detached_identity(
            selection_identity,
            "guardian formal selection",
        )
        checked = launch_validator.validate_selection(
            selection,
            admission=self.admission,
            admission_identity=self.admission_identity,
            guardian_ready=self.ready_record,
            guardian_ready_identity=self.ready_identity,
            attempt_consumption=attempt_consumption,
            attempt_consumption_identity=attempt_consumption_identity,
            expected_context=self.context,
        )
        if checked_identity["path"] != self.context["formal_selection_path"]:
            raise GuardianProtocolError("guardian formal selection path drifted")
        self.selection_record = checked
        self.selection_identity = checked_identity
        self.effects.selection_activated = True
        self.effects.success_eligible = True
        return checked

    def receive_activation(
        self,
        frame: ReceivedFrame | None = None,
    ) -> dict[str, object]:
        """Receive one external selection activation and replay its marker."""

        if self.last_control_identity is not None:
            raise GuardianProtocolError("guardian activation cannot be received twice")
        if frame is None:
            frame = receive_frame(self.connection, expected_fd_count=0)
        record = _closed(frame.record, ACTIVATION_FIELDS, "guardian activation")
        selection_identity = launch_validator.validate_detached_identity(
            record["formal_selection_identity"],
            "guardian activation selection",
        )
        ready_identity = launch_validator.validate_detached_identity(
            record["guardian_ready_identity"],
            "guardian activation ready",
        )
        if (
            record["schema_version"] != GUARDIAN_ACTIVATION_SCHEMA
            or record["status"] != "ACTIVATE_SELECTED_IDENTITIES_ONLY"
            or record["campaign_root_identity"]
            != self.context["campaign_root_identity"]
            or record["package_id"] != self.context["package_id"]
            or ready_identity != self.ready_identity
            or selection_identity["path"] != self.context["formal_selection_path"]
        ):
            raise GuardianProtocolError("guardian activation identity drifted")
        selection, replayed_selection_identity = launch_validator.read_canonical_record(
            selection_identity["path"],
            expected_identity=selection_identity,
            label="guardian formal selection",
        )
        marker_identity = launch_validator.validate_detached_identity(
            selection["attempt_consumption_identity"],
            "guardian attempt consumption",
        )
        marker, replayed_marker_identity = launch_validator.read_canonical_record(
            marker_identity["path"],
            expected_identity=marker_identity,
            label="guardian attempt consumption",
        )
        if replayed_marker_identity != marker_identity:
            raise GuardianProtocolError("guardian attempt consumption identity drifted")
        checked = self.activate_selection(
            selection,
            selection_identity=replayed_selection_identity,
            attempt_consumption=marker,
            attempt_consumption_identity=marker_identity,
        )
        self.last_control_identity = frame.identity
        return {
            "identity": frame.identity,
            "record": record,
            "selection": checked,
        }

    def receive_ledger_update(self, frame: ReceivedFrame) -> dict[str, object]:
        """Accept one hash-chained complete ledger in fixed launch order."""

        if self.selection_identity is None or self.last_control_identity is None:
            raise GuardianProtocolError("guardian ledger update lacks activation")
        record = _closed(
            frame.record,
            LEDGER_UPDATE_FIELDS,
            "guardian ledger update",
        )
        sequence = record["sequence"]
        if type(sequence) is not int or sequence != self.ledger_update_count + 1:
            raise GuardianProtocolError("guardian ledger update sequence drifted")
        if sequence > len(LEDGER_PHASES) or record["phase"] != LEDGER_PHASES[sequence - 1]:
            raise GuardianProtocolError("guardian ledger update phase drifted")
        previous = launch_validator.validate_message_identity(
            record["previous_message_identity"],
            "guardian ledger previous message",
        )
        selection = launch_validator.validate_detached_identity(
            record["formal_selection_identity"],
            "guardian ledger selection",
        )
        ledger = closeout_state.validate_frozen_ledger(record["ledger"])
        ledger_identity = launch_validator.validate_message_identity(
            record["ledger_message_identity"],
            "guardian ledger payload",
        )
        if (
            record["schema_version"] != GUARDIAN_LEDGER_UPDATE_SCHEMA
            or record["status"] != "FINITE_LEDGER_UPDATE"
            or record["campaign_root_identity"]
            != self.context["campaign_root_identity"]
            or record["package_id"] != self.context["package_id"]
            or selection != self.selection_identity
            or previous != self.last_control_identity
            or ledger_identity != _ledger_identity(ledger)
        ):
            raise GuardianProtocolError("guardian ledger update join drifted")
        items = _ledger_items(ledger)
        phase = str(record["phase"])
        if phase == "outer:prelaunch":
            changed = {"outer:formal"}
            live = False
        elif phase == "gate1:prelaunch":
            changed = {f"gate1:{slot}" for slot in closeout_state.GATE1_SLOTS}
            live = False
        elif phase.endswith(":prelaunch"):
            changed = {phase.removesuffix(":prelaunch")}
            live = False
        elif phase.endswith(":live"):
            changed = {phase.removesuffix(":live")}
            live = True
        else:
            changed = {phase}
            live = phase == "outer:formal"
        if not changed <= set(items):
            raise GuardianProtocolError("guardian ledger phase escaped the finite identity set")
        previous_items = (
            _ledger_items(self.latest_ledger)
            if self.latest_ledger is not None
            else None
        )
        for key, current in items.items():
            active = bool(
                current["invocation_id"]
                or current["control_group"]
                or current["processes"]
            )
            if key in changed:
                if (
                    current["identity_complete"] is not True
                    or not current["unit_name"]
                    or active is not live
                ):
                    raise GuardianProtocolError(
                        "guardian ledger phase lacks its exact selected identity state"
                    )
                if live and not (
                    current["invocation_id"]
                    and current["control_group"]
                    and current["processes"]
                ):
                    raise GuardianProtocolError(
                        "guardian live ledger phase is not one complete runtime identity"
                    )
                if previous_items is not None:
                    previous = previous_items[key]
                    previous_active = bool(
                        previous["invocation_id"]
                        or previous["control_group"]
                        or previous["processes"]
                    )
                    if (
                        previous_active
                        or (
                            live
                            and previous["unit_name"] != current["unit_name"]
                        )
                        or (
                            not live
                            and previous["unit_name"] not in {"", current["unit_name"]}
                        )
                    ):
                        raise GuardianProtocolError(
                            "guardian ledger prelaunch/live predecessor drifted"
                        )
            elif previous_items is None:
                if active or current["unit_name"]:
                    raise GuardianProtocolError(
                        "first guardian ledger update smuggled a future identity"
                    )
            elif current != previous_items[key]:
                raise GuardianProtocolError(
                    "guardian ledger update changed a non-current identity"
                )
        if (
            phase == "outer:formal"
            and self.selection_record is not None
            and items["outer:formal"]["unit_name"]
            != self.selection_record["outer_spec"]["unit_name"]
        ) or ledger["child_audit_identity"] != {}:
            raise GuardianProtocolError(
                "guardian ledger update drifted from selected outer/audit state"
            )
        self.latest_ledger = ledger
        self.ledger_update_count = sequence
        self.last_control_identity = frame.identity
        return {"identity": frame.identity, "ledger": ledger, "record": record}

    def validate_terminal_frame(self, frame: ReceivedFrame) -> dict[str, object]:
        """Validate the sole terminal command and its final inline ledger."""

        if self.selection_identity is None or self.last_control_identity is None:
            raise GuardianProtocolError("guardian terminal command lacks activation")
        if self.effects.terminal_command_received:
            raise GuardianProtocolError("guardian terminal command cannot be received twice")
        record = _closed(frame.record, TERMINAL_FIELDS, "guardian terminal command")
        selection = launch_validator.validate_detached_identity(
            record["formal_selection_identity"],
            "guardian terminal selection",
        )
        previous = launch_validator.validate_message_identity(
            record["previous_message_identity"],
            "guardian terminal previous message",
        )
        ledger = closeout_state.validate_frozen_ledger(record["ledger"])
        child_audit_identity = ledger["child_audit_identity"]
        if child_audit_identity != {}:
            checked_child_audit_identity = (
                launch_validator.validate_detached_identity(
                    child_audit_identity,
                    "guardian terminal child audit",
                )
            )
            if (
                self.selection_record is None
                or checked_child_audit_identity["path"]
                != self.selection_record["child_audit_path"]
            ):
                raise GuardianProtocolError(
                    "guardian terminal child-audit identity drifted"
                )
        ledger_identity = launch_validator.validate_message_identity(
            record["ledger_message_identity"],
            "guardian terminal ledger",
        )
        if (
            record["schema_version"] != GUARDIAN_TERMINAL_SCHEMA
            or record["status"] != "TERMINAL_COMMAND"
            or record["command"] not in {"ENTER_CONTAINMENT", "NORMAL_RELEASE"}
            or type(record["reason"]) is not str
            or not record["reason"]
            or record["campaign_root_identity"]
            != self.context["campaign_root_identity"]
            or record["package_id"] != self.context["package_id"]
            or selection != self.selection_identity
            or previous != self.last_control_identity
            or ledger_identity != _ledger_identity(ledger)
            or (
                self.latest_ledger is not None
                and (
                    ledger["children"] != self.latest_ledger["children"]
                    or ledger["outer"] != self.latest_ledger["outer"]
                    or (
                        self.latest_ledger["child_audit_identity"] != {}
                        and ledger["child_audit_identity"]
                        != self.latest_ledger["child_audit_identity"]
                    )
                )
            )
            or (
                self.latest_ledger is None
                and any(
                    item["invocation_id"] or item["control_group"] or item["processes"]
                    for item in _ledger_items(ledger).values()
                )
            )
            or (
                record["command"] == "NORMAL_RELEASE"
                and ledger["child_audit_identity"] == {}
            )
        ):
            raise GuardianProtocolError("guardian terminal command join drifted")
        self.effects.terminal_command_received = True
        self.latest_ledger = ledger
        self.last_control_identity = frame.identity
        return {"identity": frame.identity, "ledger": ledger, "record": record}

    def receive_expected_control(
        self,
        expected_record: Mapping[str, object],
        *,
        fields: frozenset[str],
    ) -> dict[str, object]:
        try:
            frame = receive_frame(self.connection, expected_fd_count=0)
        except GuardianPeerClosed as exc:
            self.effects.supervisor_connection_closed = True
            self.effects.fail("SUPERVISOR_CONNECTION_CLOSED", exc)
            raise
        record = _closed(frame.record, fields, "guardian control frame")
        if record != dict(expected_record):
            self.effects.fail(
                "GUARDIAN_CONTROL_IDENTITY_DRIFT",
                "received control frame differs from the expected canonical frame",
            )
            raise GuardianProtocolError("guardian control frame identity drifted")
        return record

    def hold_until_absent(
        self,
        *,
        ledger: Mapping[str, object],
        port: ResidualRuntimePort,
        waiter: WaitPort = time.sleep,
        poll_interval_seconds: float = 1.0,
        contain: bool,
    ) -> dict[str, object]:
        """Never return while the exact finite ledger has residual runtime."""

        if type(poll_interval_seconds) is not float or poll_interval_seconds <= 0:
            raise GuardianProtocolError("guardian poll interval is invalid")
        lease = self._require_lease()
        try:
            checked_ledger = dict(port.validate_ledger(ledger))
        except BaseException as exc:
            self.effects.fail("GUARDIAN_LEDGER_VALIDATION_FAILED", exc)
            raise GuardianProtocolError("guardian cannot establish a finite ledger") from exc
        if contain:
            self.effects.success_eligible = False
            self.effects.irreversible_incomplete = True
            if self.effects.containment_attempted:
                raise GuardianProtocolError("guardian containment cannot be attempted twice")
            self.effects.containment_attempted = True
            try:
                containment = port.contain_exact_once(checked_ledger)
                if type(containment) is not dict:
                    raise GuardianProtocolError(
                        "guardian containment result is malformed"
                    )
                for item in closeout_state.validate_failure_list(
                    containment.get("errors"),
                    "guardian containment errors",
                ):
                    if item not in self.effects.errors:
                        self.effects.errors.append(item)
            except BaseException as exc:
                self.effects.fail("GUARDIAN_CONTAINMENT_FAILED_OR_UNCERTAIN", exc)
        while True:
            lease.evidence()
            try:
                raw = port.observe_exact_absence(checked_ledger)
                observation = dict(port.validate_exact_absence(checked_ledger, raw))
                if observation.get("all_absent") is True:
                    return observation
                if type(observation.get("all_absent")) is not bool:
                    raise GuardianProtocolError("guardian absence result lacks one boolean")
            except BaseException as exc:
                self.effects.fail("GUARDIAN_ABSENCE_OBSERVATION_FAILED", exc)
            try:
                waiter(poll_interval_seconds)
            except BaseException as exc:
                self.effects.fail("GUARDIAN_WAITER_FAILED", exc)
                deadline = time.monotonic() + poll_interval_seconds
                while time.monotonic() < deadline:
                    time.sleep(max(0.0, deadline - time.monotonic()))

    def hold_until_supervisor_death(
        self,
        *,
        waiter: WaitPort = time.sleep,
        poll_interval_seconds: float = 1.0,
    ) -> dict[str, object]:
        """Keep all lock copies until the handoff-bound pidfd proves peer death."""

        if type(poll_interval_seconds) is not float or poll_interval_seconds <= 0:
            raise GuardianProtocolError("guardian supervisor-death poll interval is invalid")
        lease = self._require_lease()
        witness = self.supervisor_death_witness
        if witness is None:
            self.effects.fail(
                "SUPERVISOR_PIDFD_IDENTITY_GAP",
                "handoff did not establish a non-racy supervisor pidfd",
            )
            while True:
                lease.evidence()
                try:
                    waiter(poll_interval_seconds)
                except BaseException as exc:
                    self.effects.fail("GUARDIAN_SUPERVISOR_DEATH_WAITER_FAILED", exc)
                    deadline = time.monotonic() + poll_interval_seconds
                    while time.monotonic() < deadline:
                        time.sleep(max(0.0, deadline - time.monotonic()))
        while True:
            lease.evidence()
            try:
                raw = witness.observe()
                if raw is not None:
                    return validate_supervisor_death_observation(
                        raw,
                        expected_process_identity=witness.process_identity,
                    )
            except BaseException as exc:
                self.effects.fail("SUPERVISOR_DEATH_OBSERVATION_FAILED", exc)
            try:
                waiter(poll_interval_seconds)
            except BaseException as exc:
                self.effects.fail("GUARDIAN_SUPERVISOR_DEATH_WAITER_FAILED", exc)
                deadline = time.monotonic() + poll_interval_seconds
                while time.monotonic() < deadline:
                    time.sleep(max(0.0, deadline - time.monotonic()))

    def close_locks_after_absence(
        self,
        *,
        ledger: Mapping[str, object],
        ledger_message_identity: Mapping[str, object],
        port: ResidualRuntimePort,
        waiter: WaitPort = time.sleep,
        poll_interval_seconds: float = 1.0,
        contain: bool,
    ) -> dict[str, object]:
        """Close guardian copies once; success remains only a candidate."""

        if self.selection_identity is None:
            raise GuardianProtocolError("guardian lock close lacks a formal selection")
        if self.effects.lock_close_attempted:
            raise GuardianProtocolError("guardian lock close cannot be attempted twice")
        observation = self.hold_until_absent(
            ledger=ledger,
            port=port,
            waiter=waiter,
            poll_interval_seconds=poll_interval_seconds,
            contain=contain,
        )
        self.effects.lock_close_attempted = True
        effect = self._require_lease().close_local_copies_once()
        self.effects.lock_close_returned = effect["guardian_copies_closed"] is True
        try:
            self.close_supervisor_death_witness_once()
        except BaseException as exc:
            self.effects.fail("SUPERVISOR_PIDFD_CLOSE_FAILED_OR_UNCERTAIN", exc)
        if not self.effects.lock_close_returned:
            self.effects.fail(
                "GUARDIAN_LOCK_CLOSE_FAILED_OR_UNCERTAIN",
                "one or more guardian lock close calls failed",
            )
        success_eligible = (
            self.effects.success_eligible
            and not contain
            and not self.effects.irreversible_incomplete
            and self.effects.lock_close_returned
        )
        record = {
            "absence_observation": observation,
            "authorizations": dict(launch_validator.FALSE_CLAIMS),
            "campaign_root_identity": self.context["campaign_root_identity"],
            "close_effect": effect,
            "errors": list(self.effects.errors),
            "formal_selection_identity": self.selection_identity,
            "frozen_ledger": closeout_state.validate_frozen_ledger(ledger),
            "ledger_message_identity": launch_validator.validate_message_identity(
                ledger_message_identity,
                "guardian ledger",
            ),
            "outcome": "SUCCESS_CANDIDATE" if success_eligible else "INCOMPLETE",
            "package_id": self.context["package_id"],
            "schema_version": GUARDIAN_LOCK_CLOSE_SCHEMA,
            "status": "GUARDIAN_COPIES_CLOSED",
            "success_eligible": success_eligible,
        }
        return _closed(record, LOCK_CLOSE_FIELDS, "guardian lock close")

    def close_supervisor_death_witness_once(self) -> None:
        """Close the pidfd only after no guardian takeover can remain necessary."""

        witness = self.supervisor_death_witness
        if witness is None:
            raise GuardianProtocolError("supervisor pidfd identity is unavailable")
        witness.close_once()

    def mark_supervisor_lost(self, error: BaseException | str) -> dict[str, str]:
        """Permanently enter containment eligibility; never regain success."""

        self.effects.supervisor_connection_closed = True
        return self.effects.fail("SUPERVISOR_LOST_GUARDIAN_TAKEOVER", error)


def build_activation_record(
    *,
    expected_context: Mapping[str, object],
    formal_selection_identity: Mapping[str, object],
    guardian_ready_identity: Mapping[str, object],
) -> dict[str, object]:
    context = launch_validator.validate_formal_context(expected_context)
    return {
        "campaign_root_identity": context["campaign_root_identity"],
        "formal_selection_identity": launch_validator.validate_detached_identity(
            formal_selection_identity,
            "guardian activation selection",
        ),
        "guardian_ready_identity": launch_validator.validate_detached_identity(
            guardian_ready_identity,
            "guardian activation ready",
        ),
        "package_id": context["package_id"],
        "schema_version": GUARDIAN_ACTIVATION_SCHEMA,
        "status": "ACTIVATE_SELECTED_IDENTITIES_ONLY",
    }


def build_preselection_cancel_record(
    *,
    expected_context: Mapping[str, object],
    formal_admission_identity: Mapping[str, object],
    guardian_ready_identity: Mapping[str, object],
    lock_identities: object,
    reason: str,
) -> dict[str, object]:
    """Build the sole no-selection cancel frame for the external supervisor."""

    context = launch_validator.validate_formal_context(expected_context)
    if type(reason) is not str or not reason:
        raise GuardianProtocolError("preselection cancel reason is malformed")
    return {
        "authority_scope": launch_validator.AUTHORITY_SCOPE,
        "campaign_root_identity": context["campaign_root_identity"],
        "formal_admission_identity": launch_validator.validate_detached_identity(
            formal_admission_identity,
            "preselection cancel admission",
        ),
        "guardian_ready_identity": launch_validator.validate_detached_identity(
            guardian_ready_identity,
            "preselection cancel ready",
        ),
        "lock_identities": launch_validator.validate_lock_identities(
            lock_identities
        ),
        "package_id": context["package_id"],
        "reason": reason,
        "schema_version": GUARDIAN_PRESELECTION_CANCEL_SCHEMA,
        "status": "CANCEL_WITHOUT_FORMAL_SELECTION",
    }


def build_ledger_update_record(
    *,
    expected_context: Mapping[str, object],
    formal_selection_identity: Mapping[str, object],
    ledger: Mapping[str, object],
    phase: str,
    previous_message_identity: Mapping[str, object],
    sequence: int,
) -> dict[str, object]:
    """Build one complete, hash-chained finite-ledger update."""

    context = launch_validator.validate_formal_context(expected_context)
    if (
        type(sequence) is not int
        or not 1 <= sequence <= len(LEDGER_PHASES)
        or phase != LEDGER_PHASES[sequence - 1]
    ):
        raise GuardianProtocolError("guardian ledger update order is invalid")
    checked_ledger = closeout_state.validate_frozen_ledger(ledger)
    current = _ledger_items(checked_ledger)[phase]
    activity = (
        bool(current["invocation_id"]),
        bool(current["control_group"]),
        bool(current["processes"]),
    )
    if (
        checked_ledger["child_audit_identity"] != {}
        or current["identity_complete"] is not True
        or not current["unit_name"]
        or len(set(activity)) != 1
    ):
        raise GuardianProtocolError(
            "guardian ledger update payload is not one active/inactive selected slot"
        )
    return {
        "campaign_root_identity": context["campaign_root_identity"],
        "formal_selection_identity": launch_validator.validate_detached_identity(
            formal_selection_identity,
            "guardian ledger update selection",
        ),
        "ledger": checked_ledger,
        "ledger_message_identity": _ledger_identity(checked_ledger),
        "package_id": context["package_id"],
        "phase": phase,
        "previous_message_identity": launch_validator.validate_message_identity(
            previous_message_identity,
            "guardian ledger update previous message",
        ),
        "schema_version": GUARDIAN_LEDGER_UPDATE_SCHEMA,
        "sequence": sequence,
        "status": "FINITE_LEDGER_UPDATE",
    }


def build_terminal_record(
    *,
    expected_context: Mapping[str, object],
    command: str,
    formal_selection_identity: Mapping[str, object],
    ledger: Mapping[str, object],
    previous_message_identity: Mapping[str, object],
    reason: str,
) -> dict[str, object]:
    context = launch_validator.validate_formal_context(expected_context)
    if command not in {"ENTER_CONTAINMENT", "NORMAL_RELEASE"}:
        raise GuardianProtocolError("guardian terminal command is invalid")
    if type(reason) is not str or not reason:
        raise GuardianProtocolError("guardian terminal reason is malformed")
    checked_ledger = closeout_state.validate_frozen_ledger(ledger)
    if command == "NORMAL_RELEASE" and checked_ledger["child_audit_identity"] == {}:
        raise GuardianProtocolError(
            "normal guardian release lacks finite child-audit identity"
        )
    return {
        "campaign_root_identity": context["campaign_root_identity"],
        "command": command,
        "formal_selection_identity": launch_validator.validate_detached_identity(
            formal_selection_identity,
            "guardian terminal selection",
        ),
        "ledger": checked_ledger,
        "ledger_message_identity": _ledger_identity(checked_ledger),
        "package_id": context["package_id"],
        "previous_message_identity": launch_validator.validate_message_identity(
            previous_message_identity,
            "guardian terminal previous message",
        ),
        "reason": reason,
        "schema_version": GUARDIAN_TERMINAL_SCHEMA,
        "status": "TERMINAL_COMMAND",
    }


if __name__ == "__main__":
    raise SystemExit(main())
